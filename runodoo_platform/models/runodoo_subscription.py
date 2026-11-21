"""Hosting subscriptions (SPEC-portal-sso §3.2–3.4). Odoo CE has no sale_subscription: one record per customer
plan, a daily cron posts the next invoice and e-mails it with its pay link; paying it (any payment provider,
Paymob on the live site) extends the platform account. No saved cards: nothing is charged automatically."""
import logging
from datetime import datetime, time as dtime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .platform_api import PlatformError

_logger = logging.getLogger(__name__)


class RunodooSubscription(models.Model):
    _name = 'runodoo.subscription'
    _description = 'Hosting subscription'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    partner_id = fields.Many2one('res.partner', "Customer", required=True, index=True, tracking=True,
                                 help="Stored as the commercial partner (company, or the person without one)")
    product_id = fields.Many2one('product.product', "Plan", required=True, tracking=True,
                                 domain=[('oh_plan', '!=', False)])
    period = fields.Selection(related='product_id.oh_period', store=True)
    discount = fields.Float(
        "Discount (%)", tracking=True,
        default=lambda self: self.env['runodoo.platform.api']._discount(),
        help="Taken off every invoice of this subscription: the plan discount when it started (Settings → Run Odoo).")
    coupon_id = fields.Many2one('runodoo.coupon', "Coupon", readonly=True, tracking=True, index='btree_not_null',
                                help="Typed when the plan was chosen: its discount covers the first invoices.")
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([('draft', "Draft"), ('active', "Active"), ('past_due', "Past due"),
                              ('cancelled', "Cancelled")], default='draft', required=True, tracking=True)
    paid_until = fields.Date("Paid until", readonly=True, tracking=True)
    next_invoice_date = fields.Date("Next invoice", tracking=True)
    suspended_for_payment = fields.Boolean(readonly=True, copy=False)
    invoice_ids = fields.One2many('account.move', 'runodoo_subscription_id', "Invoices", readonly=True)
    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.depends('partner_id', 'product_id')
    def _compute_name(self):
        for sub in self:
            sub.name = f"{sub.partner_id.display_name or '?'} — {sub.product_id.display_name or '?'}"

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for sub in self:
            sub.invoice_count = len(sub.invoice_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id'):
                vals['partner_id'] = self.env['res.partner'].browse(vals['partner_id']).commercial_partner_id.id
        return super().create(vals_list)

    # ---------- periods ----------
    def _step(self):
        return relativedelta(years=1) if self.period == 'year' else relativedelta(months=1)

    def _open_invoice(self):
        return self.invoice_ids.filtered(lambda m: m.state == 'posted' and m.payment_state not in
                                         ('paid', 'in_payment', 'reversed'))

    # ---------- actions ----------
    def action_start(self):
        """Activate and send the first invoice (the platform is extended when it is paid)."""
        for sub in self:
            if sub.state != 'draft':
                continue
            if self.search_count([('partner_id', '=', sub.partner_id.id), ('state', 'in', ('active', 'past_due')),
                                  ('id', '!=', sub.id)]):
                raise UserError(_("%s already has an active hosting subscription: change its plan instead.",
                                  sub.partner_id.display_name))
            sub.write({'state': 'active', 'next_invoice_date': fields.Date.context_today(sub)})
            sub._create_invoice()
        return True

    def action_cancel(self):
        """No more invoices; the platform account runs until its paid period (+ grace) ends, then the platform's
        own expiry rules apply (data deleted 30 days later)."""
        open_invoices = self.mapped(lambda s: s._open_invoice())
        open_invoices.filtered(lambda m: m.amount_residual == m.amount_total).button_draft()
        open_invoices.filtered(lambda m: m.state == 'draft').button_cancel()
        self.write({'state': 'cancelled', 'next_invoice_date': False})
        return True

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('runodoo_subscription_id', '=', self.id)]
        action['context'] = {'default_move_type': 'out_invoice'}
        return action

    def _invoice_discount(self):
        """The coupon's discount on its first `months` invoices (0 = all), else the subscription's own."""
        coupon = self.coupon_id
        done = len(self.invoice_ids.filtered(lambda m: m.state != 'cancel'))
        if coupon and (not coupon.months or done < coupon.months):
            return coupon.discount
        return self.discount

    def _create_invoice(self):
        self.ensure_one()
        if self._open_invoice():
            return self._open_invoice()[:1]
        start = self.paid_until or fields.Date.context_today(self)
        end = start + self._step()
        plan = self.product_id
        currency = plan.oh_currency_id or self.company_id.currency_id
        move = self.env['account.move'].sudo().with_company(self.company_id).create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'currency_id': currency.id,
            'invoice_origin': self.name,
            'runodoo_subscription_id': self.id,
            'runodoo_period_end': end,
            'invoice_line_ids': [fields.Command.create({
                'product_id': plan.id,
                'name': _("%(plan)s hosting, %(start)s – %(end)s", plan=plan.name, start=start, end=end),
                'quantity': 1,
                # the plan's price is in its own currency (e.g. USD): never converted from the company currency
                'price_unit': plan.lst_price,
                'discount': self._invoice_discount(),   # shown on the invoice: list price, then the discount
            })],
        })
        move.action_post()
        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if template and self.partner_id.email:
            template.sudo().send_mail(move.id)
        self.next_invoice_date = end
        return move

    # ---------- platform ----------
    def _grace(self):
        return timedelta(days=self.env['runodoo.platform.api']._int_param('grace_days', 7))

    def _paid(self, move):
        """An invoice of this subscription is paid: extend the period and the platform account."""
        self.ensure_one()
        end = move.runodoo_period_end or (fields.Date.context_today(self) + self._step())
        if not self.paid_until or end > self.paid_until:
            self.paid_until = end
        if self.state == 'past_due':
            self.state = 'active'
        if not self.next_invoice_date or self.next_invoice_date < self.paid_until:
            self.next_invoice_date = self.paid_until if self.state == 'active' else False
        expires = datetime.combine(self.paid_until, dtime()) + self._grace() + timedelta(days=1)
        product = self.product_id.product_tmpl_id
        try:
            self.partner_id._oh_set_plan(product.oh_plan, product._oh_limits(), expires, key=f"inv{move.id}")
            self.suspended_for_payment = False
        except PlatformError as e:  # retried by the daily cron (_cron_sync_paid)
            _logger.warning("platform update after payment of %s failed: %s", move.name, e)
            self.message_post(body=_("Platform update failed, will retry: %s", e))

    # ---------- crons ----------
    @api.model
    def _cron_invoice(self):
        today = fields.Date.context_today(self)
        for sub in self.search([('state', 'in', ('active', 'past_due')), ('next_invoice_date', '<=', today)]):
            try:
                with self.env.cr.savepoint():
                    sub._create_invoice()
            except Exception:
                _logger.exception("invoicing %s failed", sub.name)

    @api.model
    def _cron_overdue(self):
        """Overdue more than grace_days ⇒ past_due + platform account suspended (once)."""
        today = fields.Date.context_today(self)
        grace = self.env['runodoo.platform.api']._int_param('grace_days', 7)
        for sub in self.search([('state', 'in', ('active', 'past_due')), ('suspended_for_payment', '=', False)]):
            late = sub._open_invoice().filtered(
                lambda m: (m.invoice_date_due or m.invoice_date) + timedelta(days=grace) < today)
            if not late:
                continue
            sub.state = 'past_due'
            try:
                sub.partner_id._oh_suspend(_("payment overdue (%s)", late[0].name), key=f"inv{late[0].id}")
                sub.suspended_for_payment = True
                sub.partner_id._oh_notify(
                    _("Your Run Odoo account is suspended"),
                    _("Invoice %s is more than %s days overdue, so your environments are stopped. Pay it from your "
                      "account page and they start again.", late[0].name, grace))
            except PlatformError as e:
                _logger.warning("suspending %s failed: %s", sub.name, e)

    @api.model
    def _cron_sync_paid(self):
        """Retry platform updates that failed right after a payment (platform down at that moment)."""
        for sub in self.search([('state', '=', 'active'), ('paid_until', '!=', False)]):
            partner = sub.partner_id
            if partner.oh_account_id and partner.oh_status != 'suspended' and partner.oh_plan == \
                    sub.product_id.oh_plan:
                continue
            paid = sub.invoice_ids.filtered(lambda m: m.payment_state in ('paid', 'in_payment'))
            if paid:
                sub._paid(paid.sorted('runodoo_period_end')[-1])

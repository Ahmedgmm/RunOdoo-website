"""Events from odoo-host (SPEC-portal-sso §6), stored by POST /runodoo/hooks and handled by a cron (never inline)."""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from .platform_api import PlatformError
from .res_partner import iso

_logger = logging.getLogger(__name__)
ATTEMPTS = 5


class RunodooPlatformEvent(models.Model):
    _name = 'runodoo.platform.event'
    _description = 'Platform event'
    _order = 'delivery_id desc'

    delivery_id = fields.Integer("Delivery", required=True, readonly=True)
    event = fields.Char(required=True, readonly=True, index=True)
    account_id = fields.Integer("Platform account", readonly=True)
    external_ref = fields.Char(readonly=True)
    at = fields.Char("Created (UTC)", readonly=True)
    data = fields.Json(readonly=True)
    partner_id = fields.Many2one('res.partner', readonly=True, index='btree_not_null')
    state = fields.Selection([('new', "New"), ('done', "Done"), ('ignored', "Ignored"), ('error', "Error")],
                             default='new', required=True, index=True)
    attempts = fields.Integer(readonly=True)
    error = fields.Text(readonly=True)

    _delivery_uniq = models.Constraint('UNIQUE(delivery_id)', "Each platform delivery is stored once.")

    @api.model
    def _store(self, payload):
        """Idempotent on the delivery id (the platform retries until it gets a 2xx)."""
        delivery = int(payload.get('id') or 0)
        if not delivery or not payload.get('event'):
            return False
        if self.sudo().search_count([('delivery_id', '=', delivery)]):
            return True
        self.sudo().create({
            'delivery_id': delivery, 'event': payload['event'], 'account_id': payload.get('account_id') or 0,
            'external_ref': payload.get('external_ref'), 'at': payload.get('at'), 'data': payload.get('data') or {},
        })
        cron = self.env.ref('runodoo_platform.ir_cron_platform_events', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()
        return True

    def _partner(self):
        Partner = self.env['res.partner'].sudo()
        partner = Partner.browse()
        ref = self.external_ref or ''
        if ref.startswith('ro-p') and ref[4:].isdigit():
            partner = Partner.browse(int(ref[4:])).exists()
        if not partner and self.account_id:
            partner = Partner.search([('oh_account_id', '=', self.account_id)], limit=1)
        return partner

    @api.model
    def _cron_process(self):
        for ev in self.search([('state', 'in', ('new', 'error')), ('attempts', '<', ATTEMPTS)],
                              order='delivery_id', limit=200):
            tries = ev.attempts + 1
            try:
                with self.env.cr.savepoint():
                    ev.write({'state': ev._handle() or 'done', 'attempts': tries, 'error': False})
            except Exception as e:  # noqa: BLE001 — keep going, retried next run
                _logger.exception("platform event %s failed", ev.delivery_id)
                ev.write({'state': 'error', 'error': str(e)[:2000], 'attempts': tries})

    def action_retry(self):
        self.write({'state': 'new', 'attempts': 0})
        self._cron_process()

    # ---------- handlers ----------
    def _handle(self):
        partner = self._partner()
        self.partner_id = partner
        if not partner:
            return 'ignored'
        d = self.data or {}
        handler = getattr(self, '_on_' + self.event.replace('.', '_'), None)
        if handler:
            handler(partner, d)
        else:
            partner._oh_sync(force=True)   # unknown / informational: refresh the cached state
        return 'done'

    def _on_account_created(self, partner, d):
        api_ = self.env['runodoo.platform.api']
        partner._oh_apply(api_.call('GET', f"/accounts/{self.account_id}"))   # errors ⇒ retried
        if partner.oh_plan == 'trial':   # trial length counts from sign-up, not from the invite
            days = api_._int_param('trial_days', 15)
            try:
                acct = api_.call('PATCH', f"/accounts/{self.account_id}",
                                 {'limits': {'expires_at': iso(fields.Datetime.now() + timedelta(days=days))}},
                                 idempotency_key=f"trial-expiry-{self.account_id}")
                partner._oh_apply(acct)
            except PlatformError as e:
                raise RuntimeError(f"setting the trial expiry failed: {e}") from e
        partner._oh_notify(_("Your Run Odoo account is ready"),
                           _("You are connected as @%s. Open the control panel from your account page: "
                             "every Git branch becomes its own Odoo environment.", d.get('login') or '?'))

    def _on_usage(self, partner, d):
        partner.oh_usage = d

    def _on_account_expiring(self, partner, d):
        partner._oh_sync(force=True)
        partner._oh_notify(_("Your Run Odoo plan ends in %s days", d.get('days', '?')),
                           _("Your plan ends on %s UTC. Choose a plan on your account page to keep your "
                             "environments running.", (d.get('expires_at') or '')[:16]))

    def _on_account_expired(self, partner, d):
        partner._oh_sync(force=True)
        partner._oh_notify(_("Your Run Odoo plan has ended"),
                           _("Your environments are stopped. Your data is kept until %s UTC — choose a plan to "
                             "continue.", (d.get('delete_after') or '')[:16]))

    def _on_account_suspended(self, partner, d):
        partner._oh_sync(force=True)

    def _on_account_resumed(self, partner, d):
        partner._oh_sync(force=True)
        partner._oh_notify(_("Your Run Odoo account is active again"),
                           _("Thank you — your environments can start again."))

    def _on_account_reactivated(self, partner, d):
        partner._oh_sync(force=True)

    def _on_account_over_limit(self, partner, d):
        partner._oh_sync(force=True)
        over = ", ".join(d.get('limits') or []) or "?"
        partner._oh_notify(_("Your Run Odoo account is over its plan limits"),
                           _("Over: %s. Nothing is deleted, but new environments and builds are refused until "
                             "you remove some or choose a bigger plan.", over))

    def _on_account_deletion_warning(self, partner, d):
        partner._oh_sync(force=True)
        partner._oh_notify(_("Your Run Odoo data will be deleted soon"),
                           _("Your account's data is deleted on %s UTC. Choose a plan on your account page to "
                             "keep it.", (d.get('delete_after') or '')[:16]))

    def _on_account_deleting(self, partner, d):
        partner._oh_sync(force=True)
        partner._oh_notify(_("Your Run Odoo account is being deleted"),
                           _("Your account and its data are deleted on %s UTC.", (d.get('delete_after') or '')[:16]))

    def _on_account_deleted(self, partner, d):
        partner.write({'oh_account_id': 0, 'oh_status': 'deleted', 'oh_state': 'deleted', 'oh_usage': False})
        partner._oh_notify(_("Your Run Odoo account was deleted"),
                           _("Your hosting account and its data are deleted. Your invoices stay available on your "
                             "account page."))

    def _on_project_access_lost(self, partner, d):
        partner._oh_notify(_("Run Odoo lost access to %s", d.get('project', '?')),
                           _("The GitHub repository of project %s can no longer be read (App uninstalled or access "
                             "removed). Its environments keep running; on unpaid plans it is deleted on %s UTC unless "
                             "access comes back.", d.get('project', '?'), (d.get('delete_after') or '')[:16]))

    def _on_project_deletion_warning(self, partner, d):
        partner._oh_notify(_("Project %s will be deleted soon", d.get('project', '?')),
                           _("Project %s has no repository access and is deleted on %s UTC.",
                             d.get('project', '?'), (d.get('delete_after') or '')[:16]))

    def _on_project_deleted(self, partner, d):
        partner._oh_notify(_("Project %s was deleted", d.get('project', '?')),
                           _("Project %s was deleted (no repository access).", d.get('project', '?')))

    def _on_server_unreachable(self, partner, d):
        partner._oh_notify(_("Your server cannot be reached"),
                           _("The platform cannot reach your linked server %s.", d.get('name') or d.get('server')))

    def _on_server_reachable(self, partner, d):
        pass

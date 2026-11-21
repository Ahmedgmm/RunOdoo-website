"""Coupon codes typed when a plan is chosen on /my/platform. The coupon's discount replaces the subscription's
own discount on its first `months` invoices (0 = every invoice). A 100 % coupon makes a 0.00 invoice, which Odoo
marks paid when it is posted: the plan starts at once, without any payment."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RunodooCoupon(models.Model):
    _name = 'runodoo.coupon'
    _description = 'Hosting coupon code'
    _order = 'id desc'

    name = fields.Char("Code", required=True, help="What the customer types (not case-sensitive).")
    discount = fields.Float("Discount (%)", required=True, default=100)
    months = fields.Integer("Invoices discounted", default=1,
                            help="How many invoices of the subscription get this discount (0 = all of them).")
    product_ids = fields.Many2many('product.product', string="Plans", domain=[('oh_plan', '!=', False)],
                                   help="Empty = every plan.")
    max_uses = fields.Integer("Max uses", default=1, help="0 = unlimited.")
    valid_until = fields.Date("Valid until")
    active = fields.Boolean(default=True)
    subscription_ids = fields.One2many('runodoo.subscription', 'coupon_id', "Used by", readonly=True)
    use_count = fields.Integer("Used", compute='_compute_use_count')
    note = fields.Char("Note", help="Who it is for (internal).")

    _code_uniq = models.Constraint('unique(name)', "This coupon code exists already.")

    @api.depends('subscription_ids')
    def _compute_use_count(self):
        for coupon in self:
            coupon.use_count = len(coupon.subscription_ids)

    @api.constrains('discount', 'months', 'max_uses')
    def _check_numbers(self):
        for coupon in self:
            if not 0 < coupon.discount <= 100:
                raise ValidationError(_("A coupon's discount is between 0 and 100 %."))
            if coupon.months < 0 or coupon.max_uses < 0:
                raise ValidationError(_("Coupon numbers can't be negative."))

    @api.model
    def _clean(self, code):
        return (code or '').strip().upper()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = self._clean(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('name'):
            vals['name'] = self._clean(vals['name'])
        return super().write(vals)

    @api.model
    def _find(self, code, product):
        """→ (coupon, None) or (empty, error message) for `code` typed with `product`."""
        coupon = self.sudo().search([('name', '=', self._clean(code))], limit=1)
        if not coupon:
            return self.browse(), _("Unknown coupon code.")
        if coupon.valid_until and coupon.valid_until < fields.Date.context_today(self):
            return self.browse(), _("This coupon code has expired.")
        if coupon.max_uses and coupon.use_count >= coupon.max_uses:
            return self.browse(), _("This coupon code has been used already.")
        if coupon.product_ids and product not in coupon.product_ids:
            return self.browse(), _("This coupon code is not valid for the %s plan.", product.name)
        return coupon, None

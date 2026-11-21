import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .platform_api import LIMIT_KEYS


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    oh_plan = fields.Char(
        "Hosting plan", help="Plan name sent to the platform (e.g. starter, pro). Set ⇒ this product is a hosting "
                             "plan customers can subscribe to on /my/platform.")
    oh_period = fields.Selection([('month', "Monthly"), ('year', "Yearly")], "Billing period", default='month')
    oh_limits = fields.Text(
        "Plan limits (JSON)", default='{}',
        help="Platform limits for this plan, e.g. {\"max_projects\": 3, \"max_envs\": 6, \"allow_production\": true}. "
             "Leave a key out for the platform's trial default. expires_at is set from the paid period.")

    @api.constrains('oh_limits')
    def _check_oh_limits(self):
        for product in self:
            limits = product._oh_limits()
            unknown = set(limits) - LIMIT_KEYS
            if unknown:
                raise ValidationError(_("Unknown platform limit keys: %s", ", ".join(sorted(unknown))))
            if 'expires_at' in limits:
                raise ValidationError(_("Don't set expires_at on a plan: it follows the paid period."))

    def _oh_limits(self):
        self.ensure_one()
        try:
            limits = json.loads(self.oh_limits or '{}')
        except ValueError as e:
            raise ValidationError(_("Plan limits must be JSON: %s", e)) from None
        if not isinstance(limits, dict):
            raise ValidationError(_("Plan limits must be a JSON object."))
        return limits

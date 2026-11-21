import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .platform_api import LIMIT_KEYS

# what a plan sells, as readable fields → the platform's limit keys. Memory / CPU are never sold or shown: the
# platform sizes each environment from its workers (odoo-host limits.worker_size).
PLAN_FIELDS = {
    'oh_workers': 'workers', 'oh_storage_gb': 'disk_gb', 'oh_projects': 'max_projects',
    'oh_collaborators': 'max_collaborators', 'oh_backup_days': 'backup_retention_days',
}


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    oh_plan = fields.Char(
        "Hosting plan", help="Plan name sent to the platform (e.g. starter, pro). Set ⇒ this product is a hosting "
                             "plan: listed on /pricing and on /my/platform.")
    oh_period = fields.Selection([('month', "Monthly"), ('year', "Yearly")], "Billing period", default='month')
    oh_currency_id = fields.Many2one(
        'res.currency', "Plan currency", default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help="The sales price of a plan is in this currency: /pricing shows it and invoices are made in it.")
    oh_workers = fields.Integer("Workers", default=1,
                                help="Odoo workers for production (together). Each worker serves more users at once.")
    oh_storage_gb = fields.Integer("Storage (GB)", default=10, help="Database + files + code, all environments.")
    oh_projects = fields.Integer("Projects", default=1, help="Separate Odoo systems (each with its own production).")
    oh_production = fields.Boolean("Production", default=True, help="Off ⇒ only development / staging.")
    oh_staging_envs = fields.Integer("Staging / dev environments", default=1,
                                     help="Branches next to production, per account (always 1 worker each).")
    oh_collaborators = fields.Integer("Collaborators", default=2, help="GitHub users who may work on the projects.")
    oh_backup_days = fields.Integer("Backups kept (days)", default=7)
    oh_features = fields.Text("Extra lines", help="One per line, shown under the limits on the pricing page "
                                                  "(e.g. Daily backups, Free SSL).")
    oh_highlight = fields.Boolean("Highlight", help="Show this plan as the recommended one.")
    oh_limits = fields.Text(
        "Extra limits (JSON)", default='{}',
        help="Advanced: other platform limits, merged over the fields above, e.g. {\"build_minutes_per_day\": 120}. "
             "expires_at is set from the paid period.")

    @api.constrains('oh_limits', 'oh_workers', 'oh_storage_gb', 'oh_projects', 'oh_staging_envs', 'oh_production',
                    'oh_collaborators', 'oh_backup_days')
    def _check_oh_limits(self):
        for product in self:
            extra = product._oh_extra_limits()
            unknown = set(extra) - LIMIT_KEYS
            if unknown:
                raise ValidationError(_("Unknown platform limit keys: %s", ", ".join(sorted(unknown))))
            if 'expires_at' in extra:
                raise ValidationError(_("Don't set expires_at on a plan: it follows the paid period."))
            if product.oh_plan and (product.oh_workers < 1 or product.oh_projects < 1 or product.oh_storage_gb < 1):
                raise ValidationError(_("A plan needs at least 1 worker, 1 project and 1 GB of storage."))
            if product.oh_plan and product.oh_production and product.oh_workers < product.oh_projects:
                raise ValidationError(_("Give a plan at least one worker per project: every production needs one."))
            if min(product.oh_staging_envs, product.oh_collaborators, product.oh_backup_days) < 0:
                raise ValidationError(_("Plan numbers can't be negative."))

    def _oh_extra_limits(self):
        self.ensure_one()
        try:
            limits = json.loads(self.oh_limits or '{}')
        except ValueError as e:
            raise ValidationError(_("Plan limits must be JSON: %s", e)) from None
        if not isinstance(limits, dict):
            raise ValidationError(_("Plan limits must be a JSON object."))
        return limits

    def _oh_limits(self):
        """The limits sent to the platform for this plan."""
        self.ensure_one()
        limits = {key: self[name] for name, key in PLAN_FIELDS.items()}
        prod = 1 if self.oh_production else 0
        envs = self.oh_projects * prod + self.oh_staging_envs
        limits.update(allow_production=self.oh_production, max_envs=envs, max_running_envs=envs)
        limits.update(self._oh_extra_limits())
        return limits

    def _oh_lines(self):
        """What the pricing page lists for this plan (never memory or CPU)."""
        self.ensure_one()
        plural = lambda n, one, many: f"{n} {one if n == 1 else many}"  # noqa: E731
        lines = [plural(self.oh_workers, _("worker"), _("workers")),
                 _("%s GB storage", self.oh_storage_gb),
                 plural(self.oh_projects, _("project"), _("projects")) if self.oh_production
                 else _("No production (testing only)"),
                 plural(self.oh_staging_envs, _("staging / dev environment"), _("staging / dev environments")),
                 plural(self.oh_collaborators, _("collaborator"), _("collaborators")),
                 _("Backups kept %s days", self.oh_backup_days)]
        lines += [line.strip() for line in (self.oh_features or '').splitlines() if line.strip()]
        return lines

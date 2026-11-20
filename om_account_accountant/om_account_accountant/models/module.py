from odoo import models
from odoo.modules.module import get_manifest


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    def button_immediate_upgrade(self):
        modules = self
        if 'om_account_accountant' in self.mapped('name'):
            # Upgrading the suite in Apps also reloads its installed companion modules.
            dependencies = get_manifest('om_account_accountant').get('depends', [])
            modules |= self.search([('name', 'in', dependencies), ('state', '=', 'installed')])
        return super(IrModuleModule, modules).button_immediate_upgrade()

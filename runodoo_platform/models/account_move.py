from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    runodoo_subscription_id = fields.Many2one('runodoo.subscription', "Hosting subscription", index='btree_not_null',
                                              copy=False, readonly=True)
    runodoo_period_end = fields.Date("Hosting paid until", copy=False, readonly=True)

    def _invoice_paid_hook(self):
        res = super()._invoice_paid_hook()
        for move in self.filtered('runodoo_subscription_id'):
            move.runodoo_subscription_id.sudo()._paid(move)
        return res

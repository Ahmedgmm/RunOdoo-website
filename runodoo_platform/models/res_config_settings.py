from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    runodoo_api_url = fields.Char("Platform URL", config_parameter='runodoo_platform.api_url',
                                  help="Control panel base URL, e.g. https://app.runodoo.online")
    runodoo_api_key = fields.Char("API key", config_parameter='runodoo_platform.api_key',
                                  help="X-OH-Key from `odoohost api-client create` (scopes read,provision,sso)")
    runodoo_api_secret = fields.Char("API HMAC secret", config_parameter='runodoo_platform.api_secret')
    runodoo_webhook_secret = fields.Char("Webhook secret", config_parameter='runodoo_platform.webhook_secret',
                                         help="Same as /etc/odoohost/provisioning-webhook.secret on odoo-host")
    runodoo_trial_days = fields.Integer("Trial days", config_parameter='runodoo_platform.trial_days', default=15)
    runodoo_discount = fields.Float(
        "Plan discount (%)", config_parameter='runodoo_platform.discount_percent', default=0,
        help="Taken off every plan's price for new subscriptions (0 = none). A subscription keeps the discount it "
             "started with. /pricing shows the plan price struck through.")
    runodoo_discount_label = fields.Char("Discount label", config_parameter='runodoo_platform.discount_label',
                                         default="Launch offer")
    runodoo_grace_days = fields.Integer("Days overdue before suspend", config_parameter='runodoo_platform.grace_days',
                                        default=7)

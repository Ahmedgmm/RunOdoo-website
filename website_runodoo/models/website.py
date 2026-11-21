from odoo import api, models
from odoo.tools import BinaryBytes, file_open

FAVICON = 'website_runodoo/static/src/img/favicon.png'
LOGO = 'website_runodoo/static/src/img/runodoo-logo.png'


class Website(models.Model):
    _inherit = 'website'

    @api.model
    def _runodoo_apply_branding(self):
        """Set the Runodoo favicon + logo on the default website, and allow free sign-up.

        Called from data/website_data.xml on every install/upgrade. A <record> can't do it:
        base.default_website is a noupdate record, so upgrades silently skip it.
        """
        website = self.env.ref('base.default_website', raise_if_not_found=False) or self.search([], limit=1)
        if not website:
            return
        with file_open(FAVICON, 'rb') as f:
            favicon = f.read()
        with file_open(LOGO, 'rb') as f:
            logo = f.read()
        website.write({
            'favicon': BinaryBytes(favicon, filename='favicon.png'),
            'logo': BinaryBytes(logo, filename='runodoo-logo.png'),
            'auth_signup_uninvited': 'b2c',   # free sign-up on /web/signup: the trial starts there
        })

    def _runodoo_pricing(self):
        """Hosting plans for /pricing and the homepage, straight from the plan products (runodoo_platform): one card
        per plan name, its monthly price first and the yearly one beside it. Memory / CPU are never listed."""
        products = self.env['product.template'].sudo().search(
            [('oh_plan', '!=', False), ('sale_ok', '=', True)], order='sequence, list_price, id')
        cards = {}
        for p in products:
            card = cards.setdefault(p.oh_plan, {'plan': p.oh_plan, 'month': None, 'year': None})
            if not card[p.oh_period or 'month']:
                card[p.oh_period or 'month'] = p
        out = []
        for card in cards.values():
            main = card['month'] or card['year']
            out.append({**card, 'main': main, 'name': main.name, 'lines': main._oh_lines(),
                        'highlight': any(p and p.oh_highlight for p in (card['month'], card['year'])),
                        'currency': main.oh_currency_id or main.currency_id})
        return out

    def _runodoo_trial_days(self):
        return self.env['runodoo.platform.api'].sudo()._int_param('trial_days', 15)

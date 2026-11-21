from odoo import api, models
from odoo.tools import BinaryBytes, file_open

FAVICON = 'website_runodoo/static/src/img/favicon.png'
LOGO = 'website_runodoo/static/src/img/runodoo-logo.png'
REPORT_BRANDING = '1'   # bump to re-apply _runodoo_apply_report_branding on the next upgrade


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
        self._runodoo_apply_report_branding(website.company_id, logo)

    @api.model
    def _runodoo_apply_report_branding(self, company, logo):
        """Invoices / documents: Runodoo logo, layout and colours on the website's company.

        Applied once per REPORT_BRANDING version (a config parameter remembers it), so later changes made in
        Settings → Document Layout survive module upgrades. Name/website/footer only fill blanks or defaults.
        """
        icp = self.env['ir.config_parameter'].sudo()
        if not company or icp.get_str('website_runodoo.report_branding') == REPORT_BRANDING:
            return
        vals = {
            'logo': BinaryBytes(logo, filename='runodoo-logo.png'),
            'external_report_layout_id': self.env.ref('website_runodoo.external_layout_runodoo').id,
            'primary_color': '#0b3558',
            'secondary_color': '#006bff',
            'report_tables_id': 'light',
        }
        if company.name in (False, '', 'My Company'):
            vals['name'] = 'Runodoo'
        if not company.website:
            vals['website'] = 'https://www.runodoo.online'
        if not company.report_footer or not str(company.report_footer).strip():
            vals['report_footer'] = ('Thank you for hosting with Runodoo. '
                                     'Questions about this invoice? www.runodoo.online/contactus')
        company.write(vals)
        icp.set_str('website_runodoo.report_branding', REPORT_BRANDING)

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
        api = self.env['runodoo.platform.api'].sudo()
        pct = api._discount()
        out = []
        for card in cards.values():
            main = card['month'] or card['year']
            off = lambda p: p and round(p.list_price * (100 - pct) / 100, 2)  # noqa: E731
            out.append({**card, 'main': main, 'name': main.name, 'lines': main._oh_lines(),
                        'pct': pct, 'label': api._param('discount_label', 'Launch offer') if pct else '',
                        'price': off(main), 'year_price': off(card['year']) if card['month'] else None,
                        'highlight': any(p and p.oh_highlight for p in (card['month'], card['year'])),
                        'currency': main.oh_currency_id or main.currency_id})
        return out

    def _runodoo_trial_days(self):
        return self.env['runodoo.platform.api'].sudo()._int_param('trial_days', 15)

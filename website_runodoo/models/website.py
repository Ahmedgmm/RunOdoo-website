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

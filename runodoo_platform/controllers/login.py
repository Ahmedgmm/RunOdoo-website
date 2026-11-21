"""Customers (portal users) land on /my/platform after sign-in and sign-up — the page with the big
"Open control panel" button. Employees keep going to the backend."""
from odoo.addons.web.controllers.utils import is_user_internal
from odoo.addons.website.controllers.main import Website


class RunodooLogin(Website):

    def _login_redirect(self, uid, redirect=None):
        if not redirect and not is_user_internal(uid):
            redirect = '/my/platform'
        return super()._login_redirect(uid, redirect=redirect)

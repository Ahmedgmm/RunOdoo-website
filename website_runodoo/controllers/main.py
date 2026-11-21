from odoo import http
from odoo.http import request


class RunodooPricing(http.Controller):

    @http.route('/pricing', type='http', auth='public', website=True, sitemap=True)
    def pricing(self, **kw):
        return request.render('website_runodoo.pricing', {})

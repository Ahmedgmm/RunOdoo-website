"""Portal: /my/platform (plan, status, usage, invoices, Open control panel), trial sign-up, plan purchase;
POST /runodoo/hooks for platform events (SPEC-portal-sso §3–§6)."""
import json
import logging
from urllib.parse import quote

from odoo import _, http
from odoo.http import request

from ..models.platform_api import PlatformError, verify

_logger = logging.getLogger(__name__)
HOOK_PATH = '/runodoo/hooks'
MAX_HOOK_BODY = 256 * 1024


class RunodooPortal(http.Controller):

    def _partner(self):
        return request.env.user.partner_id.commercial_partner_id.sudo()

    def _back(self, error=None, notice=None):
        url = '/my/platform'
        if error:
            url += '?error=' + quote(str(error)[:300])
        elif notice:
            url += '?notice=' + quote(notice)
        return request.redirect(url)

    @http.route('/my/platform', type='http', auth='user', website=True)
    def platform(self, error=None, notice=None, **kw):
        partner = self._partner()
        if request.env['runodoo.platform.api'].sudo()._configured():
            partner._oh_sync()
        subs = request.env['runodoo.subscription'].sudo().search([('partner_id', '=', partner.id)])
        active = subs.filtered(lambda s: s.state in ('active', 'past_due'))[:1]
        plans = request.env['product.product'].sudo().search(
            [('oh_plan', '!=', False), ('sale_ok', '=', True), ('active', '=', True)], order='list_price')
        unpaid = active._open_invoice() if active else request.env['account.move']
        return request.render('runodoo_platform.portal_my_platform', {
            'page_name': 'runodoo_platform', 'partner': partner, 'subscription': active, 'plans': plans,
            'unpaid': unpaid, 'error': error, 'notice': notice, 'usage': partner.oh_usage or {},
            'limits': partner.oh_limits or {}, 'connected': bool(partner.oh_account_id),
            'can_open': bool(partner.oh_account_id) and partner.oh_status == 'active',
            'live_invite': partner._oh_live_invite(),
            'trial_days': request.env['runodoo.platform.api'].sudo()._int_param('trial_days', 15),
            # an active subscription keeps its own discount; new ones get the current offer
            'discount': active.discount if active else request.env['runodoo.platform.api'].sudo()._discount(),
        })

    @http.route('/my/platform/open', type='http', auth='user', website=True, methods=['POST'])
    def open_panel(self, **kw):
        """One-time login link (60 s) → auto-submitting form to {panel}/sso; the token never goes in a URL."""
        partner = self._partner()
        if not partner.oh_account_id:
            return self._back(_("Connect GitHub first."))
        try:
            link = partner._oh_login_link()
        except PlatformError as e:
            if e.status == 409:   # suspended / deleting / not signed up
                partner._oh_sync(force=True)
            return self._back(e.args[0] if e.args else _("The control panel cannot be opened right now."))
        resp = request.render('runodoo_platform.portal_platform_handoff', {'url': link['url'], 'token': link['token']})
        resp.headers['Cache-Control'] = 'no-store'
        resp.headers['Referrer-Policy'] = 'no-referrer'
        return resp

    @http.route('/my/platform/trial', type='http', auth='user', website=True, methods=['POST'])
    def start_trial(self, **kw):
        partner = self._partner()
        if partner.oh_account_id:
            return self._back(notice=_("Your account is already connected."))
        try:
            url = partner._oh_start_trial()
        except PlatformError as e:
            return self._back(e.args[0] if e.args else None)
        if not url:   # an existing account was found and linked
            return self._back(notice=_("Your account is connected."))
        return request.redirect(url, local=False)

    @http.route('/my/platform/connect', type='http', auth='user', website=True, methods=['POST'])
    def connect(self, **kw):
        """Continue a sign-up whose invite link is still valid."""
        partner = self._partner()
        if partner.oh_account_id or not partner._oh_live_invite():
            return self._back()
        return request.redirect(partner.oh_signup_url, local=False)

    @http.route('/my/platform/subscribe', type='http', auth='user', website=True, methods=['POST'])
    def subscribe(self, product_id=None, **kw):
        """Choose a plan: new subscription + first invoice, then straight to the invoice's pay page."""
        partner = self._partner()
        Sub = request.env['runodoo.subscription'].sudo()
        try:
            product = request.env['product.product'].sudo().browse(int(product_id or 0)).exists()
        except ValueError:
            product = None
        if not product or not product.oh_plan or not product.sale_ok:
            return self._back(_("Unknown plan."))
        current = Sub.search([('partner_id', '=', partner.id), ('state', 'in', ('active', 'past_due'))], limit=1)
        if current:
            if current.product_id == product:
                return self._back(notice=_("You are already on this plan."))
            return self._back(_("To change your plan, contact us: plan changes are applied from the next period."))
        sub = Sub.create({'partner_id': partner.id, 'product_id': product.id})
        sub.action_start()
        invoice = sub._open_invoice()[:1]
        return request.redirect(invoice.get_portal_url() if invoice else '/my/platform')

    # ---------- platform → Odoo ----------
    @http.route(HOOK_PATH, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def hooks(self, **kw):
        body = request.httprequest.get_data(cache=False)
        if len(body) > MAX_HOOK_BODY:
            return request.make_json_response({'error': 'too large'}, status=413)
        secret = request.env['runodoo.platform.api'].sudo()._param('webhook_secret')
        if not verify(secret, 'POST', HOOK_PATH, request.httprequest.headers, body):
            _logger.warning("platform hook: bad signature from %s", request.httprequest.remote_addr)
            return request.make_json_response({'error': 'bad signature'}, status=401)
        try:
            payload = json.loads(body)
        except ValueError:
            return request.make_json_response({'error': 'bad json'}, status=400)
        if not isinstance(payload, dict) or not request.env['runodoo.platform.event'].sudo()._store(payload):
            return request.make_json_response({'error': 'bad event'}, status=400)
        return request.make_json_response({'ok': True})

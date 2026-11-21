"""Link between a customer (commercial partner) and its odoo-host account. external_ref = "ro-p<partner id>",
stable for life; e-mail addresses are never used for matching (SPEC-portal-sso §2)."""
import logging
import time
from datetime import timedelta

from odoo import _, fields, models

from .platform_api import PlatformError

_logger = logging.getLogger(__name__)

INVITE_DAYS = 14
SYNC_EVERY = timedelta(minutes=10)


def iso(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    oh_account_id = fields.Integer("Platform account", copy=False, readonly=True, index=True)
    oh_login = fields.Char("GitHub login", copy=False, readonly=True)
    oh_plan = fields.Char("Platform plan", copy=False, readonly=True)
    oh_status = fields.Char("Platform status", copy=False, readonly=True,
                            help="pending / active / suspended / deleting (the platform's account status)")
    oh_state = fields.Char("Platform state", copy=False, readonly=True,
                           help="active / expired / suspended / deleting, as the platform computes it")
    oh_expires_at = fields.Char("Platform expiry (UTC)", copy=False, readonly=True)
    oh_delete_after = fields.Char("Data deleted after (UTC)", copy=False, readonly=True)
    oh_limits = fields.Json("Platform limits", copy=False, readonly=True)
    oh_usage = fields.Json("Platform usage", copy=False, readonly=True)
    oh_over_limit = fields.Json("Over limits", copy=False, readonly=True)
    oh_signup_url = fields.Char("Sign-up link", copy=False, readonly=True, groups='base.group_system')
    oh_signup_expires = fields.Datetime("Sign-up link expires", copy=False, readonly=True)
    oh_synced_at = fields.Datetime("Synced with platform", copy=False, readonly=True)

    # ---------- identity ----------
    def _oh_partner(self):
        return self.commercial_partner_id.sudo()

    def _oh_ref(self):
        return f"ro-p{self.commercial_partner_id.id}"

    def _oh_api(self):
        return self.env['runodoo.platform.api'].sudo()

    # ---------- state from the platform ----------
    def _oh_apply(self, acct):
        """Store an account object (GET /accounts/{id}, PATCH responses …) on the partner."""
        self.ensure_one()
        partner = self._oh_partner()
        vals = {
            'oh_account_id': acct.get('id'), 'oh_login': acct.get('login'), 'oh_plan': acct.get('plan'),
            'oh_status': acct.get('status'), 'oh_state': acct.get('state'), 'oh_expires_at': acct.get('expires_at'),
            'oh_delete_after': acct.get('delete_after'), 'oh_limits': acct.get('limits'),
            'oh_usage': acct.get('usage'), 'oh_over_limit': acct.get('over_limit') or [],
            'oh_synced_at': fields.Datetime.now(),
        }
        if acct.get('id'):
            vals.update(oh_signup_url=False, oh_signup_expires=False)
        partner.write(vals)

    def _oh_sync(self, force=False):
        """Refresh from the platform (best effort: an unreachable platform keeps the cached values)."""
        partner = self._oh_partner()
        if not force and partner.oh_synced_at and partner.oh_synced_at > fields.Datetime.now() - SYNC_EVERY:
            return partner
        try:
            if partner.oh_account_id:
                acct = self._oh_api().call('GET', f"/accounts/{partner.oh_account_id}")
            else:
                found = self._oh_api().call('GET', f"/accounts?external_ref={self._oh_ref()}").get('accounts')
                acct = found[0] if found else None
        except PlatformError as e:
            if e.status == 404 and partner.oh_account_id:  # deleted on the platform
                partner.write({'oh_account_id': 0, 'oh_status': 'deleted', 'oh_state': 'deleted'})
            _logger.info("platform sync of %s: %s", self._oh_ref(), e)
            return partner
        if acct:
            partner._oh_apply(acct)
        return partner

    # ---------- sign-up ----------
    def _oh_live_invite(self):
        partner = self._oh_partner()
        return bool(partner.oh_signup_url and partner.oh_signup_expires
                    and partner.oh_signup_expires > fields.Datetime.now())

    def _oh_invite(self, plan, limits):
        """An invite code bound to this partner (one live invite at a time) → its sign-up URL."""
        partner = self._oh_partner()
        if partner.oh_account_id:
            return None
        if partner._oh_live_invite():
            return partner.oh_signup_url
        body = {'plan': plan, 'limits': limits, 'external_ref': self._oh_ref(), 'expires_in_days': INVITE_DAYS}
        try:
            res = self._oh_api().call('POST', '/invites', body,
                                      idempotency_key=f"invite-{self._oh_ref()}-{plan}-{int(time.time())}")
        except PlatformError as e:
            if e.status == 409:  # an account with this external_ref exists: link it
                partner._oh_sync(force=True)
                return None
            raise
        partner.write({'oh_signup_url': res['signup_url'],
                       'oh_signup_expires': fields.Datetime.now() + timedelta(days=INVITE_DAYS) - timedelta(hours=1),
                       'oh_status': 'invited'})
        return res['signup_url']

    def _oh_start_trial(self):
        """Free trial (no card): the trial length is set when the account is created (event account.created),
        so an invite used on day 10 still gives the full trial."""
        return self._oh_invite('trial', {})

    # ---------- plan / billing state ----------
    def _oh_set_plan(self, plan, limits, expires, key):
        """Paid period: plan + limits + expiry; resumes an account suspended for non-payment."""
        partner = self._oh_partner()
        if not partner.oh_account_id:
            return partner._oh_invite(plan, {**limits, 'expires_at': iso(expires)})
        acct = self._oh_api().call('PATCH', f"/accounts/{partner.oh_account_id}",
                                   {'plan': plan, 'limits': {**limits, 'expires_at': iso(expires)}},
                                   idempotency_key=f"plan-{key}")
        if acct.get('status') == 'suspended':
            acct = self._oh_api().call('POST', f"/accounts/{partner.oh_account_id}/resume", {},
                                       idempotency_key=f"resume-{key}")
        partner._oh_apply(acct)
        return None

    def _oh_suspend(self, reason, key):
        partner = self._oh_partner()
        if not partner.oh_account_id:
            return
        try:
            acct = self._oh_api().call('POST', f"/accounts/{partner.oh_account_id}/suspend", {'reason': reason},
                                       idempotency_key=f"suspend-{key}")
        except PlatformError as e:
            if e.status == 409:   # already suspended / deleting
                return
            raise
        partner._oh_apply(acct)

    def _oh_login_link(self):
        """→ {url, token}: one-time (60 s) sign-in to the control panel as this account's owner."""
        partner = self._oh_partner()
        if not partner.oh_account_id:
            raise PlatformError(_("Connect GitHub first."))
        return self._oh_api().call('POST', f"/accounts/{partner.oh_account_id}/login-links", {},
                                   idempotency_key=f"link-{partner.oh_account_id}-{time.time_ns()}")

    # ---------- notices ----------
    def _oh_notify(self, subject, body):
        template = self.env.ref('runodoo_platform.mail_template_platform_notice', raise_if_not_found=False)
        partner = self._oh_partner()
        if template and partner.email:
            template.sudo().with_context(oh_subject=subject, oh_body=body).send_mail(partner.id)

    def action_oh_sync(self):
        for partner in self:
            partner._oh_sync(force=True)

"""Client for the odoo-host provisioning API (docs/SPEC-multitenant.md §13.2, docs/SPEC-portal-sso.md).

Every request is signed: X-OH-Key, X-OH-Timestamp, X-OH-Signature = hex HMAC-SHA256(secret,
METHOD "\\n" PATH[?QUERY] "\\n" TIMESTAMP "\\n" BODY); mutating calls carry an Idempotency-Key. Incoming events
(POST /runodoo/hooks) are signed the same way with the webhook secret."""
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import urlsplit

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PARAM = 'runodoo_platform.'
SKEW = 300
TIMEOUT = 15
# limit keys the platform accepts (odoohost/limits.py KEYS)
LIMIT_KEYS = {
    'expires_at', 'max_projects', 'max_envs', 'max_running_envs', 'allow_production', 'max_collaborators', 'mem_mb',
    'cpus', 'disk_gb', 'backup_retention_days', 'mail_per_day', 'idle_stop_minutes', 'build_minutes_per_day',
    'enterprise', 'custom_domains', 'max_servers', 'workers',
}


def sign(secret, method, path, timestamp, body):
    msg = f"{method.upper()}\n{path}\n{timestamp}\n".encode() + body
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify(secret, method, path, headers, body, now=None):
    """True when an incoming request carries a valid signature and a fresh timestamp."""
    ts = headers.get('X-OH-Timestamp', '')
    sig = headers.get('X-OH-Signature', '')
    if not secret or not ts.isdigit() or abs((now or time.time()) - int(ts)) > SKEW:
        return False
    return hmac.compare_digest(sign(secret, method, path, ts, body), sig)


class PlatformError(UserError):
    def __init__(self, message, status=None, payload=None):
        super().__init__(message)
        self.status, self.payload = status, payload or {}


class RunodooPlatformApi(models.AbstractModel):
    _name = 'runodoo.platform.api'
    _description = 'Run Odoo platform API client'

    @api.model
    def _param(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_str(PARAM + key, default) or default

    @api.model
    def _discount(self):
        """Current plan discount in % (0–90) for new subscriptions (Settings → Run Odoo)."""
        try:
            pct = float(self._param('discount_percent', '0'))
        except ValueError:
            return 0.0
        return min(max(pct, 0.0), 90.0)

    @api.model
    def _int_param(self, key, default):
        return self.env['ir.config_parameter'].sudo().get_int(PARAM + key, default) or default

    @api.model
    def _configured(self):
        return bool(self._param('api_url') and self._param('api_key') and self._param('api_secret'))

    @api.model
    def call(self, method, path, body=None, idempotency_key=None):
        """→ decoded JSON. Raises PlatformError (status + payload) on any non-2xx or network failure."""
        if not self._configured():
            raise PlatformError(_("The Run Odoo platform API is not configured (Settings → Run Odoo)."))
        base = self._param('api_url').rstrip('/')
        url = f"{base}/api/v1{path}"
        raw = json.dumps(body).encode() if body is not None else b''
        ts = str(int(time.time()))
        signed_path = urlsplit(url).path + (f"?{urlsplit(url).query}" if urlsplit(url).query else '')
        headers = {
            'X-OH-Key': self._param('api_key'),
            'X-OH-Timestamp': ts,
            'X-OH-Signature': sign(self._param('api_secret'), method, signed_path, ts, raw),
            'Content-Type': 'application/json',
        }
        if method.upper() != 'GET':
            if not idempotency_key or not 8 <= len(idempotency_key) <= 200:
                raise ValueError("Idempotency-Key: 8-200 characters")
            headers['Idempotency-Key'] = idempotency_key
        try:
            resp = requests.request(method.upper(), url, data=raw or None, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as e:
            _logger.warning("platform API %s %s failed: %s", method, path, e)
            raise PlatformError(_("The hosting platform cannot be reached right now. Try again in a minute.")) from e
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 300:
            msg = payload.get('error') or f"HTTP {resp.status_code}"
            _logger.info("platform API %s %s → %s %s", method, path, resp.status_code, msg)
            raise PlatformError(msg, status=resp.status_code, payload=payload)
        return payload

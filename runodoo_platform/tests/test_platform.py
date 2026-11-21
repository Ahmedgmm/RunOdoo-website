import json
import time
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.platform_api import sign, verify

API = 'odoo.addons.runodoo_platform.models.platform_api.RunodooPlatformApi.call'
# computed with odoohost.lifecycle.sign (the platform side) — both must agree byte for byte
VECTOR = 'fcbfe90a1820441f757632ff196b0fa0a405aac9c7eff65d040c46d61370d240'


class FakePlatform:
    """Records calls; answers like the provisioning API."""

    def __init__(self, account_id=42):
        self.calls, self.account_id = [], account_id
        self.acct = {'id': account_id, 'login': 'buyer', 'plan': 'trial', 'status': 'active', 'state': 'active',
                     'expires_at': None, 'limits': {}, 'usage': {}, 'over_limit': []}

    def __call__(self, method, path, body=None, idempotency_key=None):
        self.calls.append((method, path, body, idempotency_key))
        if path == '/invites':
            return {'code': 'c0de', 'signup_url': 'https://panel.test/signup?code=c0de', 'expires_at': 'x'}
        if path.endswith('/login-links'):
            return {'url': 'https://panel.test/sso', 'token': 'tok123', 'expires_at': int(time.time()) + 60}
        if method == 'PATCH':
            self.acct.update(plan=body.get('plan') or self.acct['plan'],
                             expires_at=(body.get('limits') or {}).get('expires_at'))
        if path.endswith('/suspend'):
            self.acct['status'] = 'suspended'
        if path.endswith('/resume'):
            self.acct['status'] = 'active'
        return dict(self.acct)


@tagged('post_install', '-at_install')
class TestPlatform(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Buyer Co', 'email': 'buyer@example.com',
                                                     'is_company': True})
        cls.plan = cls.env['product.product'].create({
            'name': 'Starter', 'type': 'service', 'list_price': 100, 'oh_plan': 'starter', 'oh_period': 'month',
            'oh_limits': '{"max_projects": 3, "allow_production": true}'})

    def test_signature_matches_platform(self):
        self.assertEqual(sign('s3cret', 'POST', '/runodoo/hooks', '1700000000', b'{"id": 1}'), VECTOR)
        headers = {'X-OH-Timestamp': '1700000000', 'X-OH-Signature': VECTOR}
        self.assertTrue(verify('s3cret', 'POST', '/runodoo/hooks', headers, b'{"id": 1}', now=1700000100))
        self.assertFalse(verify('s3cret', 'POST', '/runodoo/hooks', headers, b'{"id": 1}', now=1700000400))
        self.assertFalse(verify('other', 'POST', '/runodoo/hooks', headers, b'{"id": 1}', now=1700000100))
        self.assertFalse(verify('', 'POST', '/runodoo/hooks', headers, b'{"id": 1}', now=1700000100))

    def test_plan_limits_validated(self):
        with self.assertRaises(Exception):
            self.plan.product_tmpl_id.oh_limits = '{"bogus": 1}'
        with self.assertRaises(Exception):
            self.plan.product_tmpl_id.oh_limits = '{"expires_at": null}'

    def test_plan_fields_become_limits(self):
        tmpl = self.plan.product_tmpl_id
        tmpl.write({'oh_workers': 2, 'oh_storage_gb': 20, 'oh_projects': 2, 'oh_staging_envs': 3,
                    'oh_collaborators': 5, 'oh_backup_days': 14, 'oh_limits': '{"build_minutes_per_day": 120}'})
        self.assertEqual(tmpl._oh_limits(), {
            'workers': 2, 'disk_gb': 20, 'max_projects': 2, 'max_collaborators': 5, 'backup_retention_days': 14,
            'allow_production': True, 'max_envs': 5, 'max_running_envs': 5, 'build_minutes_per_day': 120})
        lines = ' | '.join(tmpl._oh_lines())
        self.assertIn('2 workers', lines)
        self.assertIn('20 GB storage', lines)
        self.assertNotIn('MB', lines)
        with self.assertRaises(Exception):
            tmpl.oh_workers = 0
        with self.assertRaises(Exception):
            tmpl.oh_workers = 1        # 2 projects need 2 workers

    def test_shipped_plans_and_usd_invoice(self):
        plans = self.env['product.template'].browse([
            self.env.ref(f'runodoo_platform.plan_{p}{y}').id for p in ('starter', 'business', 'pro') for y in ('', '_yearly')])
        self.assertEqual(sorted(set(plans.mapped('oh_projects'))), [1, 3, 5])
        self.assertTrue(all(p.oh_workers >= p.oh_projects for p in plans))
        usd = self.env.ref('base.USD')
        starter = self.env.ref('runodoo_platform.plan_starter').product_variant_id
        sub = self.env['runodoo.subscription'].create({'partner_id': self.partner.id, 'product_id': starter.id})
        with patch(API, side_effect=FakePlatform()):
            sub.action_start()
        move = sub._open_invoice()
        self.assertEqual((move.currency_id, move.amount_total), (usd, 29))   # USD, no conversion, no tax

    def test_trial_invite_then_account_created(self):
        fake = FakePlatform()
        with patch(API, side_effect=fake):
            url = self.partner._oh_start_trial()
            self.assertEqual(url, 'https://panel.test/signup?code=c0de')
            self.assertEqual(fake.calls[0][2]['external_ref'], f"ro-p{self.partner.id}")
            self.assertEqual(self.partner._oh_start_trial(), url)          # one live invite
            self.assertEqual(len(fake.calls), 1)
            Event = self.env['runodoo.platform.event']
            payload = {'id': 7, 'event': 'account.created', 'account_id': 42, 'external_ref': f"ro-p{self.partner.id}",
                       'data': {'login': 'buyer', 'github_id': 9}}
            self.assertTrue(Event._store(payload))
            self.assertTrue(Event._store(payload))                         # redelivery stored once
            self.assertEqual(Event.search_count([('delivery_id', '=', 7)]), 1)
            Event._cron_process()
        ev = Event.search([('delivery_id', '=', 7)])
        self.assertEqual(ev.state, 'done', ev.error)
        self.assertEqual(self.partner.oh_account_id, 42)
        self.assertFalse(self.partner.oh_signup_url)
        patch_call = [c for c in fake.calls if c[0] == 'PATCH']
        self.assertTrue(patch_call and patch_call[0][2]['limits']['expires_at'], "trial expiry set from sign-up")

    def test_unknown_partner_ignored(self):
        Event = self.env['runodoo.platform.event']
        Event._store({'id': 8, 'event': 'usage', 'account_id': 999, 'external_ref': 'ro-p999999', 'data': {}})
        Event._cron_process()
        self.assertEqual(Event.search([('delivery_id', '=', 8)]).state, 'ignored')

    def test_paid_invoice_extends_and_overdue_suspends(self):
        self.partner.oh_account_id = 42
        fake = FakePlatform()
        with patch(API, side_effect=fake):
            sub = self.env['runodoo.subscription'].create({'partner_id': self.partner.id,
                                                            'product_id': self.plan.id})
            sub.action_start()
            move = sub._open_invoice()
            self.assertEqual(len(move), 1)
            self.assertEqual(move.amount_untaxed, 100)
            self.env['account.payment.register'].with_context(active_model='account.move', active_ids=move.ids) \
                .create({})._create_payments()
            self.assertIn(move.payment_state, ('paid', 'in_payment'))
            self.assertTrue(sub.paid_until)
            patches = [c for c in fake.calls if c[0] == 'PATCH']
            self.assertEqual(patches[-1][2]['plan'], 'starter')
            self.assertEqual(patches[-1][2]['limits']['max_projects'], 3)
            # next period: invoice, never paid, overdue past grace → suspended once
            sub.next_invoice_date = sub.paid_until
            move2 = sub._create_invoice()
            move2.invoice_date_due = move2.invoice_date.replace(year=move2.invoice_date.year - 1)
            sub._cron_overdue()
            sub._cron_overdue()
        self.assertEqual(sub.state, 'past_due')
        self.assertTrue(sub.suspended_for_payment)
        self.assertEqual(len([c for c in fake.calls if c[1].endswith('/suspend')]), 1)


@tagged('post_install', '-at_install')
class TestHooks(HttpCase):

    def test_hook_requires_signature(self):
        self.env['ir.config_parameter'].sudo().set_str('runodoo_platform.webhook_secret', 's3cret')
        body = json.dumps({'id': 99, 'event': 'usage', 'account_id': 1, 'external_ref': None, 'data': {}}).encode()
        ts = str(int(time.time()))
        r = self.url_open('/runodoo/hooks', data=body, headers={'X-OH-Timestamp': ts, 'X-OH-Signature': 'bad',
                                                                 'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 401)
        r = self.url_open('/runodoo/hooks', data=body, headers={
            'X-OH-Timestamp': ts, 'X-OH-Signature': sign('s3cret', 'POST', '/runodoo/hooks', ts, body),
            'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(self.env['runodoo.platform.event'].sudo().search_count([('delivery_id', '=', 99)]))

    def test_open_panel_posts_token_in_body(self):
        user = self.env['res.users'].create({'name': 'Portal P', 'login': 'portal_p', 'password': 'portal_p_pw1',
                                             'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        user.partner_id.oh_account_id = 42
        user.partner_id.oh_status = 'active'
        self.authenticate('portal_p', 'portal_p_pw1')
        with patch(API, side_effect=FakePlatform()):
            page = self.url_open('/my/platform')
            self.assertIn('Open control panel', page.text)
            csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
            r = self.url_open('/my/platform/open', data={'csrf_token': csrf}, allow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('action="https://panel.test/sso"', r.text)
        self.assertIn('name="token" value="tok123"', r.text)
        self.assertNotIn('tok123', r.url)


@tagged('post_install', '-at_install')
class TestAuthPages(HttpCase):

    def test_split_layout_and_open_signup(self):
        for path, title in (('/web/login', 'Welcome back'), ('/web/signup', 'Start your free trial'),
                            ('/web/reset_password', 'Reset your password')):
            r = self.url_open(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn('class="su-split"', r.text, path)
            self.assertIn(title, r.text, path)
            self.assertIn('name="csrf_token"', r.text, path)       # Odoo's own form is inside
        self.assertIn('name="confirm_password"', self.url_open('/web/signup').text)

    def test_portal_user_lands_on_platform_page(self):
        self.env['res.users'].create({'name': 'Portal Q', 'login': 'portal_q', 'password': 'portal_q_pw1',
                                      'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        page = self.url_open('/web/login')
        csrf = page.text.split('name="csrf_token" value="')[1].split('"')[0]
        r = self.url_open('/web/login', data={'login': 'portal_q', 'password': 'portal_q_pw1', 'csrf_token': csrf},
                          allow_redirects=False)
        self.assertIn(r.status_code, (302, 303))
        self.assertTrue(r.headers['Location'].endswith('/my/platform'), r.headers['Location'])

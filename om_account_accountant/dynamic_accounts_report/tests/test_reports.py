import base64
import io
import zipfile
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.reports import REPORTS


@tagged('post_install', '-at_install')
class TestDynamicReports(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.report = cls.env['dynamic.accounting.report']
        cls.receivable = cls.env['account.account'].create({
            'name': 'DAR test receivable', 'code': 'DAR110', 'account_type': 'asset_receivable',
            'reconcile': True, 'company_ids': [Command.set(cls.company.ids)]})
        cls.income = cls.env['account.account'].create({
            'name': 'DAR test income', 'code': 'DAR400', 'account_type': 'income',
            'company_ids': [Command.set(cls.company.ids)]})
        cls.journal = cls.env['account.journal'].create({
            'name': 'DAR Test', 'code': 'DART', 'type': 'general', 'company_id': cls.company.id})
        cls.partner = cls.env['res.partner'].create({'name': 'DAR Duplicate'})
        cls.partner2 = cls.env['res.partner'].create({'name': 'DAR Duplicate'})
        cls.invoice = cls._entry(date(2026, 1, 10), 100, cls.partner)
        cls.payment = cls._entry(date(2026, 2, 10), -40, cls.partner)
        debit = cls.invoice.line_ids.filtered(lambda l: l.account_id == cls.receivable)
        credit = cls.payment.line_ids.filtered(lambda l: l.account_id == cls.receivable)
        cls.env['account.partial.reconcile'].create({'debit_move_id': debit.id,
            'credit_move_id': credit.id, 'amount': 40,
            'debit_amount_currency': 40, 'credit_amount_currency': 40})
        cls.second = cls._entry(date(2026, 1, 11), 25, cls.partner2)

    @classmethod
    def _entry(cls, when, amount, partner):
        move = cls.env['account.move'].create({'journal_id': cls.journal.id, 'date': when,
            'line_ids': [Command.create({'name': 'DAR fixture', 'partner_id': partner.id,
                'account_id': cls.receivable.id, 'date_maturity': when,
                'debit': max(amount, 0), 'credit': max(-amount, 0)}),
                Command.create({'name': 'DAR offset', 'account_id': cls.income.id,
                'debit': max(-amount, 0), 'credit': max(amount, 0)})]})
        move.action_post()
        return move

    def options(self, report='aged_receivable', **kwargs):
        return dict({'report': report, 'company_id': self.company.id,
                     'date_from': '2026-01-01', 'date_to': '2026-02-28',
                     'journal_ids': self.journal.ids}, **kwargs)

    def test_every_report_and_advanced_action(self):
        for name in REPORTS:
            with self.subTest(report=name):
                options = self.options(name)
                report = self.report.get_report(options)
                self.assertTrue(report['columns'])
                self.assertEqual(report['currency'], self.company.currency_id.name)
                self.assertTrue(self.report.legacy_action(options)['res_model'])
                action = self.report.export_xlsx(options)
                record_id = int(action['url'].split('/')[4])
                wizard = self.report.browse(record_id)
                with zipfile.ZipFile(io.BytesIO(bytes(wizard.export_file))) as book:
                    self.assertIn('xl/worksheets/sheet1.xml', book.namelist())
                pdf_action = self.report.export_pdf(options)
                content, _kind = self.env['ir.actions.report']._render_qweb_html(
                    'dynamic_accounts_report.action_report_pdf', pdf_action['context']['active_ids'], data=pdf_action['data'])
                self.assertIn(report['title'].encode(), content)

    def test_historical_partial_payment_and_duplicate_names(self):
        current = self.report.get_report(self.options())
        self.assertEqual(len(current['rows']), 2)
        self.assertEqual(sorted(r['values'][-1] for r in current['rows']), [25, 60])
        historic = self.report.get_report(self.options(date_to='2026-01-31'))
        self.assertEqual(sorted(r['values'][-1] for r in historic['rows']), [25, 100])
        self.assertEqual(sum(r['values'][1] for r in historic['rows']), 125)

    def test_reconciled_after_cutoff(self):
        payment = self._entry(date(2026, 3, 10), -60, self.partner)
        (self.invoice.line_ids | self.payment.line_ids | payment.line_ids).filtered(
            lambda l: l.account_id == self.receivable).reconcile()
        report = self.report.get_report(self.options(date_to='2026-01-31'))
        self.assertEqual(sorted(r['values'][-1] for r in report['rows']), [25, 100])

    def test_trial_opening_and_comparison_month_end(self):
        options = self.options('trial_balance', date_from='2026-02-01', comparison_count=1,
                               comparison_type='month')
        report = self.report.get_report(options)
        row = next(row for row in report['rows'] if row['key'] == str(self.receivable.id))
        self.assertEqual(row['values'], [125, 0, 40, 85, 125])
        parsed = self.report._options(self.options('profit_loss', date_from='2026-03-01', date_to='2026-03-31'))
        self.assertEqual(self.report._period(parsed, 1), (date(2026, 2, 1), date(2026, 2, 28)))

    def test_access_and_invalid_options(self):
        user = self.env['res.users'].create({'name': 'DAR No Accounting', 'login': 'dar_no_accounting',
            'group_ids': [Command.set([self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.report.with_user(user).get_report(self.options())
        with self.assertRaises(ValidationError):
            self.report.get_report(self.options('general_ledger', date_from='2026-03-01'))
        other = self.env['res.company'].create({'name': 'DAR Other Company'})
        with self.assertRaises(AccessError):
            self.report.with_context(allowed_company_ids=self.company.ids).get_report(self.options(company_id=other.id))
        # A permitted other company must still be reported separately.
        other_report = self.report.with_context(allowed_company_ids=[other.id]).get_report(
            self.options(company_id=other.id))
        self.assertEqual(other_report['rows'], [])

    def test_billing_reports_keep_existing_access(self):
        user = self.env['res.users'].create({'name': 'DAR Billing', 'login': 'dar_billing',
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'group_ids': [Command.set([self.env.ref('account.group_account_invoice').id])]})
        for name in ('partner_ledger', 'aged_receivable', 'aged_payable'):
            self.assertTrue(self.report.with_user(user).get_report(self.options(name))['columns'])
        with self.assertRaises(AccessError):
            self.report.with_user(user).get_report(self.options('general_ledger'))

    def test_comparisons_financial_totals_and_empty_historical_aging(self):
        report = self.report.get_report(self.options('profit_loss', comparison_count=2))
        self.assertEqual(len(report['columns']), 3)
        self.assertTrue(all(len(row['values']) == 3 for row in report['rows']))
        total = next(row for row in report['rows'] if row['label'] == 'Profit and Loss')
        self.assertEqual(total['values'][0], 85)
        aging = self.report.get_report(self.options(date_to='2025-01-31'))
        self.assertFalse(aging['rows'])
        self.assertEqual(aging['totals'], [0] * 7)

    def test_archived_parent_hierarchy_is_preserved_without_reactivation(self):
        grandparent = self.env['account.account'].create({
            'name': 'DAR Heading', 'code': 'DARH', 'account_type': 'asset_current',
            'company_ids': [Command.set(self.company.ids)]})
        parent = grandparent.copy({'name': 'DAR Subheading', 'code': 'DARS', 'parent_id': grandparent.id})
        self.receivable.parent_id = parent
        (grandparent | parent).active = False
        result = self.report.get_report(self.options('trial_balance', display_account='movement'))
        row = next(r for r in result['rows'] if r['key'] == str(self.receivable.id))
        self.assertEqual([item['id'] for item in row['account_path']], [grandparent.id, parent.id, self.receivable.id])
        self.assertEqual([item['active'] for item in row['account_path']], [False, False, True])
        self.assertFalse(grandparent.active)
        self.assertFalse(parent.active)
        self.assertEqual(row['values'], [0, 125, 40, 85])
        self.assertEqual(result['totals'], [0, 165, 165, 0])

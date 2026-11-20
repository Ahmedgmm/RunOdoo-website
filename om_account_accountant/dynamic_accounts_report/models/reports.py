# LGPL-3. Reporting integration for the Odoo Mates accounting suite.
import io

import xlsxwriter
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.safe_eval import safe_eval
from odoo.tools.binary import BinaryBytes

REPORTS = {
    'profit_loss': 'Profit and Loss', 'balance_sheet': 'Balance Sheet',
    'general_ledger': 'General Ledger', 'trial_balance': 'Trial Balance',
    'partner_ledger': 'Partner Ledger', 'aged_receivable': 'Aged Receivable',
    'aged_payable': 'Aged Payable', 'cash_book': 'Cash Book',
    'bank_book': 'Bank Book', 'tax': 'Tax Report',
}
LEGACY = {
    'profit_loss': 'accounting_pdf_reports.action_account_report_pl',
    'balance_sheet': 'accounting_pdf_reports.action_account_report_bs',
    'general_ledger': 'accounting_pdf_reports.action_account_general_ledger_menu',
    'trial_balance': 'accounting_pdf_reports.action_account_balance_menu',
    'partner_ledger': 'accounting_pdf_reports.action_account_partner_ledger_menu',
    'aged_receivable': 'accounting_pdf_reports.action_account_aged_receivable',
    'aged_payable': 'accounting_pdf_reports.action_account_aged_payable',
    'cash_book': 'om_account_daily_reports.action_account_cashbook_menu',
    'bank_book': 'om_account_daily_reports.action_account_bankbook_menu',
    'tax': 'accounting_pdf_reports.action_account_tax_report',
}


class DynamicAccountingReport(models.TransientModel):
    _name = 'dynamic.accounting.report'
    _description = 'Dynamic Accounting Report'

    export_file = fields.Binary(attachment=False)
    export_filename = fields.Char()

    @api.model
    def _check_reporting_access(self, report=None):
        billing_report = report is None or report in ('partner_ledger', 'aged_receivable', 'aged_payable')
        if not (self.env.user.has_group('account.group_account_readonly')
                or billing_report and self.env.user.has_group('account.group_account_invoice')):
            raise AccessError(_('Accounting report access is required.'))
        self.env['account.move.line'].check_access('read')

    @api.model
    def _options(self, options):
        self._check_reporting_access((options or {}).get('report'))
        result = dict(options or {})
        if result.get('report') not in REPORTS:
            raise ValidationError(_('Unknown report.'))
        today = fields.Date.context_today(self)
        result['date_from'] = fields.Date.to_date(result.get('date_from') or today.replace(day=1))
        result['date_to'] = fields.Date.to_date(result.get('date_to') or today)
        if result['report'].startswith('aged_'):
            result['date_from'] = result['date_to'].replace(day=1)
        if result['date_from'] > result['date_to']:
            raise ValidationError(_('Start date must be on or before end date.'))
        company_id = int(result.get('company_id') or self.env.company.id)
        # Never let caller-supplied company ids broaden the user's allowed companies.
        if company_id not in self.env.companies.ids:
            raise AccessError(_('Select an allowed company.'))
        result['company_id'] = company_id
        result['include_draft'] = bool(result.get('include_draft'))
        result['comparison_count'] = min(12, max(0, int(result.get('comparison_count') or 0)))
        if result.get('comparison_type', 'month') not in ('month', 'quarter', 'year'):
            raise ValidationError(_('Invalid comparison period.'))
        for key, model in [('journal_ids', 'account.journal'), ('account_ids', 'account.account'),
                           ('partner_ids', 'res.partner'), ('analytic_ids', 'account.analytic.account')]:
            ids = [int(value) for value in result.get(key, [])]
            records = self.env[model].browse(ids).exists()
            records.check_access('read')
            result[key] = records.ids
        return result

    @api.model
    def get_defaults(self):
        self._check_reporting_access()
        today = fields.Date.context_today(self)
        return {
            'date_from': str(today.replace(day=1)), 'date_to': str(today),
            'company_id': self.env.company.id,
            'companies': [{'id': c.id, 'name': c.name} for c in self.env.companies],
        }

    def _domain(self, options, start=None, end=None):
        domain = [('company_id', '=', options['company_id']),
                  ('parent_state', 'in', ['posted', 'draft'] if options['include_draft'] else ['posted']),
                  ('display_type', 'not in', ['line_section', 'line_note'])]
        if start:
            domain.append(('date', '>=', start))
        if end:
            domain.append(('date', '<=', end))
        for key, field in [('journal_ids', 'journal_id'), ('account_ids', 'account_id'),
                           ('partner_ids', 'partner_id')]:
            if options[key]:
                domain.append((field, 'in', options[key]))
        if options['analytic_ids']:
            domain.append(('analytic_distribution', 'in', options['analytic_ids']))
        if options['report'] == 'partner_ledger':
            domain.append(('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']))
        if options['report'] in ('bank_book', 'cash_book'):
            domain.append(('journal_id.type', '=', 'bank' if options['report'] == 'bank_book' else 'cash'))
        return domain

    def _period(self, options, offset):
        months = {'month': 1, 'quarter': 3, 'year': 12}[options.get('comparison_type', 'month')]
        start, end = options['date_from'], options['date_to']
        shifted_start = start - relativedelta(months=months * offset)
        shifted_end = end - relativedelta(months=months * offset)
        # Preserve whole calendar months, including February and leap years.
        if end == fields.Date.end_of(end, 'month'):
            shifted_end = fields.Date.end_of(shifted_end, 'month')
        return shifted_start, shifted_end

    def _row(self, key, label, values, children=None, domain=None, level=0):
        return {'key': str(key), 'label': label, 'values': values, 'children': children or [],
                'domain': domain or [], 'level': level}

    def _detail(self, line, values):
        return dict(self._row('line-%s' % line.id,
                             '%s · %s · %s' % (line.date, line.move_id.name, line.name or ''), values),
                    move_id=line.move_id.id,
                    foreign_amount=line.amount_currency,
                    foreign_currency=line.currency_id.name,
                    analytic=line.format_analytic_distribution(line.analytic_distribution))

    def _ledger(self, options):
        is_partner = options['report'] == 'partner_ledger'
        is_trial = options['report'] == 'trial_balance'
        domain = self._domain(options, end=options['date_to'])
        order = 'date, move_id, id'
        if options.get('sortby') == 'journal_partner':
            order = 'journal_id, partner_id, date, id'
        lines = self.env['account.move.line'].search(domain, order=order)
        groups = {}
        for line in lines:
            record = line.partner_id if is_partner else line.account_id
            key = record.id or 0
            label = record.display_name if record else _('Unknown Partner')
            group = groups.setdefault(key, {'label': label, 'opening': 0, 'debit': 0, 'credit': 0, 'lines': []})
            if line.date < options['date_from']:
                group['opening'] += line.balance
            else:
                group['debit'] += line.debit
                group['credit'] += line.credit
                group['lines'].append(line)
        if options['report'] in ('trial_balance', 'general_ledger') and options.get('display_account', 'all') == 'all':
            account_domain = [('company_ids', 'in', [options['company_id']])]
            if options['account_ids']:
                account_domain.append(('id', 'in', options['account_ids']))
            for account in self.env['account.account'].search(account_domain):
                groups.setdefault(account.id, {'label': account.display_name, 'opening': 0, 'debit': 0, 'credit': 0, 'lines': []})
        # Trial balance comparison columns show each period independently.
        comparisons = {}
        if is_trial:
            for offset in range(1, options['comparison_count'] + 1):
                start, end = self._period(options, offset)
                totals = self.env['account.move.line']._read_group(
                    self._domain(options, start, end), ['account_id'], ['balance:sum'])
                comparisons[offset] = {account.id: balance for account, balance in totals}
        rows = []
        for key, group in sorted(groups.items(), key=lambda item: item[1]['label']):
            opening = group['opening']
            closing = opening + group['debit'] - group['credit']
            if options.get('display_account') == 'not_zero' and self.env.company.currency_id.is_zero(closing):
                continue
            if options.get('display_account') == 'movement' and not group['lines']:
                continue
            values = [opening, group['debit'], group['credit'], closing]
            values += [comparisons[i].get(key, 0) for i in comparisons]
            detail = []
            running = opening if options.get('initial_balance', True) else 0
            if options.get('initial_balance', True):
                detail.append(self._row('opening-%s' % key, _('Opening Balance'), [opening, 0, 0, opening]))
            for line in group['lines']:
                running += line.balance
                detail.append(self._detail(line, [0, line.debit, line.credit, running]))
            row_domain = self._domain(options, options['date_from'], options['date_to'])
            row_domain.append(('partner_id' if is_partner else 'account_id', '=', key or False))
            row = self._row(key, group['label'], values, detail if not is_trial else [], row_domain)
            if is_trial:
                account = self.env['account.account'].with_context(active_test=False).browse(key)
                ancestors = account.parent_ids.with_context(active_test=False).sorted(
                    key=lambda parent: len(parent.parent_path or ''))
                ancestors.check_access('read')
                row['account_path'] = [
                    {'id': parent.id, 'label': '%s %s' % (parent.code or '', parent.name),
                     'active': parent.active}
                    for parent in ancestors if parent.id != account.id]
                row['account_path'].append({'id': account.id,
                    'label': '%s %s' % (account.code or '', account.name), 'active': account.active})
            rows.append(row)
        return [_('Opening Balance'), _('Debit'), _('Credit'), _('Closing Balance')] + [
            '%s – %s' % self._period(options, offset) for offset in comparisons], rows

    def _financial(self, options):
        # Reuse the installed suite's report tree, signs and retained-earnings setup.
        xmlid = 'accounting_pdf_reports.account_financial_report_profitandloss0' if options['report'] == 'profit_loss' else 'accounting_pdf_reports.account_financial_report_balancesheet0'
        report = self.env.ref(xmlid)
        rows = []
        columns = []
        for offset in range(options['comparison_count'] + 1):
            start, end = self._period(options, offset)
            context = self._report_context(options, start, end)
            # Balance Sheet is cumulative; P&L is activity within the selected period.
            if options['report'] == 'balance_sheet':
                context.update(date_from=False, strict_range=False)
            form = {'account_report_id': [report.id, report.name], 'enable_filter': False,
                    'debit_credit': False, 'used_context': context}
            values = self.env['report.accounting_pdf_reports.report_financial'].with_context(**context).get_account_lines(form)
            columns.append('%s – %s' % (start, end) if options['report'] == 'profit_loss' else str(end))
            if offset == 0:
                for index, value in enumerate(values):
                    domain = self._domain(options, start if options['report'] == 'profit_loss' else None, end)
                    if value.get('account_id'):
                        domain.append(('account_id', '=', value['account_id']))
                    rows.append(self._row(index, value['name'], [value['balance']],
                                          domain=domain if value.get('account_id') else [], level=value['level']))
            if offset == 0:
                identities = [(v['type'], v['report_id'], v.get('account_id'), v['name'], v['level']) for v in values]
            else:
                mapping = {(v['type'], v['report_id'], v.get('account_id'), v['name'], v['level']): v['balance'] for v in values}
                for row, identity in zip(rows, identities):
                    row['values'].append(mapping.pop(identity, 0))
                for identity, balance in mapping.items():
                    rows.append(self._row('comparison-%s-%s' % (offset, len(rows)), identity[3], [0] * offset + [balance], level=identity[4]))
                    identities.append(identity)
        order = {node.id: index for index, node in enumerate(report._get_children_by_order())}
        rows = [row for identity, row in sorted(zip(identities, rows),
                key=lambda pair: (order[pair[0][1]], pair[0][0] == 'account', pair[0][3]))]
        return columns, rows

    def _report_context(self, options, start, end):
        return dict(self.env.context, company_id=options['company_id'],
                    company_ids=[options['company_id']], allowed_company_ids=[options['company_id']],
                    journal_ids=options['journal_ids'],
                    account_ids=self.env['account.account'].browse(options['account_ids']),
                    partner_ids=self.env['res.partner'].browse(options['partner_ids']),
                    analytic_account_ids=self.env['account.analytic.account'].browse(options['analytic_ids']),
                    date_from=start, date_to=end, strict_range=True,
                    state='all' if options['include_draft'] else 'posted')

    def _aging(self, options):
        # ORM reads preserve record rules; reconstruct balances as of the selected date.
        kind = 'asset_receivable' if options['report'] == 'aged_receivable' else 'liability_payable'
        sign = 1 if kind == 'asset_receivable' else -1
        domain = self._domain(options, end=options['date_to']) + [('account_id.account_type', '=', kind)]
        lines = self.env['account.move.line'].search(domain, order='date_maturity, date, id')
        groups = {}
        for line in lines:
            balance = line.balance
            balance += sum(p.amount for p in line.matched_debit_ids if p.max_date <= options['date_to'])
            balance -= sum(p.amount for p in line.matched_credit_ids if p.max_date <= options['date_to'])
            balance *= sign
            if line.company_id.currency_id.is_zero(balance):
                continue
            days = (options['date_to'] - (line.date_maturity or line.date)).days
            bucket = 0 if days <= 0 else min(5, (days - 1) // 30 + 1)
            values = [0.0] * 6
            values[bucket] = balance
            values.append(balance)
            partner = line.partner_id
            group = groups.setdefault(partner.id or 0, {'label': partner.display_name or _('Unknown Partner'), 'values': [0.0] * 7, 'children': []})
            group['values'] = [a + b for a, b in zip(group['values'], values)]
            group['children'].append(self._detail(line, values))
        return [_('Not Due'), '1–30', '31–60', '61–90', '91–120', '120+', _('Total')], [
            self._row(key, value['label'], value['values'], value['children'])
            for key, value in sorted(groups.items(), key=lambda item: item[1]['label'])]

    def _tax(self, options):
        columns, rows, identities = [], [], []
        for offset in range(options['comparison_count'] + 1):
            start, end = self._period(options, offset)
            context = self._report_context(options, start, end)
            self.env.flush_all()
            groups = self.env['report.accounting_pdf_reports.report_tax'].with_context(**context).get_lines({
                'date_from': start, 'date_to': end, 'target_move': context['state'], 'used_context': context})
            mapping = {}
            for group, taxes in groups.items():
                for index, tax in enumerate(taxes):
                    # The installed tax engine supplies actual posted tax amounts, including refunds.
                    identity = (group, tax['name'], tax['id'])
                    mapping[identity] = [tax['net'], tax['tax']]
            columns.extend([_('Base (%s)') % end, _('Tax (%s)') % end])
            for row, identity in zip(rows, identities):
                row['values'].extend(mapping.pop(identity, [0, 0]))
            for identity, values in mapping.items():
                rows.append(self._row(len(rows), '%s · %s' % (identity[0], identity[1]), [0] * (offset * 2) + values))
                identities.append(identity)
        return columns, rows

    @api.model
    def get_report(self, options):
        options = self._options(options)
        company = self.env['res.company'].browse(options['company_id'])
        scoped = self.with_company(company).with_context(allowed_company_ids=[company.id])
        if options['report'] in ('profit_loss', 'balance_sheet'):
            columns, rows = scoped._financial(options)
        elif options['report'].startswith('aged_'):
            columns, rows = scoped._aging(options)
        elif options['report'] == 'tax':
            columns, rows = scoped._tax(options)
        else:
            columns, rows = scoped._ledger(options)
        totals = []
        if options['report'] not in ('profit_loss', 'balance_sheet', 'tax'):
            totals = [sum(row['values'][index] for row in rows) for index in range(len(columns))]
        return {'totals': totals, 'title': REPORTS[options['report']], 'company': company.name,
                'currency': company.currency_id.name, 'digits': company.currency_id.decimal_places,
                'columns': columns, 'rows': rows,
                'date_from': str(options['date_from']), 'date_to': str(options['date_to'])}

    @api.model
    def legacy_action(self, options):
        options = self._options(options)
        action = self.env['ir.actions.actions']._for_xml_id(LEGACY[options['report']])
        original_context = action.get('context') or {}
        if isinstance(original_context, str):
            original_context = safe_eval(original_context, {'uid': self.env.uid, 'context': dict(self.env.context)})
        action['context'] = dict(self.env.context, **original_context)
        action['context'].update(default_date_from=str(options['date_from']),
                                 default_date_to=str(options['date_to']),
                                 default_company_id=options['company_id'])
        return action

    @api.model
    def export_xlsx(self, options):
        report = self.get_report(options)
        output = io.BytesIO()
        book = xlsxwriter.Workbook(output, {'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False})
        sheet = book.add_worksheet('Report')
        heading = book.add_format({'bold': True, 'bg_color': '#E7EEF5'})
        amount = book.add_format({'num_format': '#,##0.' + '0' * report['digits']})
        sheet.write(0, 0, report['title'], heading)
        sheet.write(1, 0, '%s | %s | %s – %s' % (report['company'], report['currency'], report['date_from'], report['date_to']))
        sheet.write_row(3, 0, [_('Description')] + report['columns'], heading)
        index = 4
        for row in report['rows']:
            for item in [row] + row['children']:
                sheet.write(index, 0, item['label'])
                for col, value in enumerate(item['values'], 1):
                    sheet.write_number(index, col, value or 0, amount)
                if item.get('move_id'):
                    sheet.write(index, len(report['columns']) + 1, item['foreign_currency'])
                    sheet.write_number(index, len(report['columns']) + 2, item['foreign_amount'], amount)
                index += 1
        if report['totals']:
            sheet.write(index, 0, _('Total'), heading)
            for col, value in enumerate(report['totals'], 1):
                sheet.write_number(index, col, value, amount)
        sheet.freeze_panes(4, 1)
        sheet.set_column(0, 0, 65)
        sheet.set_column(1, len(report['columns']) + 2, 20)
        book.close()
        wizard = self.create({'export_file': BinaryBytes(output.getvalue()),
                              'export_filename': '%s.xlsx' % report['title']})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/dynamic.accounting.report/%s/export_file/%s?download=true' % (wizard.id, wizard.export_filename), 'target': 'download'}

    @api.model
    def export_pdf(self, options):
        report = self.get_report(options)
        company_id = int(options.get('company_id') or self.env.company.id)
        return self.env.ref('dynamic_accounts_report.action_report_pdf').with_context(
            allowed_company_ids=[company_id], landscape=True).report_action(
            self.create({}), data={'report_data': report}, config=False)


class DynamicReportPDF(models.AbstractModel):
    _name = 'report.dynamic_accounts_report.report_pdf'
    _description = 'Dynamic Accounting PDF'

    def _get_report_values(self, docids, data=None):
        self.env['dynamic.accounting.report']._check_reporting_access()
        return {'report': data['report_data'], 'docs': self.env['dynamic.accounting.report'].browse(docids or self.env.context.get('active_ids', []))}

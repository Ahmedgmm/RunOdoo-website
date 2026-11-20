import { Component, onWillStart, proxy, useProps } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { MultiRecordSelector } from '@web/core/record_selectors/multi_record_selector';
import { ControlPanel } from '@web/search/control_panel/control_panel';
import { Dropdown } from '@web/core/dropdown/dropdown';
import { useDropdownState } from '@web/core/dropdown/dropdown_hooks';
import { standardActionServiceProps } from '@web/webclient/actions/action_plugin';

export class DynamicReports extends Component {
    static template = 'dynamic_accounts_report.Reports';
    static components = { MultiRecordSelector, ControlPanel, Dropdown };
    props = useProps(standardActionServiceProps);

    setup() {
        this.orm = useService('orm');
        this.action = useService('action');
        this.state = proxy({
            options: { report: this.props.action.params.report, date_from: '', date_to: '',
                company_id: false, journal_ids: [], account_ids: [], partner_ids: [], analytic_ids: [],
                hierarchy: true, include_draft: false, initial_balance: true, display_account: 'all', sortby: 'date',
                comparison_count: 0, comparison_type: 'month' },
            mobileFilters: false, companies: [], report: null, expanded: {}, search: '', busy: false, error: '',
        });
        this.filterMenus = Object.fromEntries(['date', 'comparison', 'journals', 'accounts', 'partners', 'analytic', 'options', 'company'].map(key => [key, useDropdownState()]));
        this.sequence = 0;
        onWillStart(async () => {
            const defaults = await this.orm.call('dynamic.accounting.report', 'get_defaults', []);
            this.state.companies = defaults.companies;
            Object.assign(this.state.options, { date_from: defaults.date_from, date_to: defaults.date_to,
                company_id: defaults.company_id });
            await this.load();
        });
    }
    get isTrial() { return this.state.options.report === 'trial_balance'; }
    shortDate(value) { return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value + 'T12:00:00')); }
    get dateLabel() { return this.isAging ? 'As of ' + this.shortDate(this.state.options.date_to) : this.shortDate(this.state.options.date_from) + ' – ' + this.shortDate(this.state.options.date_to); }
    get comparisonLabel() { const n = this.state.options.comparison_count; return n ? n + ' previous ' + this.state.options.comparison_type + (n > 1 ? 's' : '') : 'No comparison'; }
    async applyComparison() { if (!this.state.options.comparison_count) { this.state.options.comparison_count = 1; } await this.applyFilters(); }
    async selectPreset(value) { this.preset({ target: { value } }); await this.applyFilters(); }
    async selectOption(key, value) { this.setOption(key, value); await this.applyFilters(); }
    get periodPresets() { return [['month', 'This month'], ['last_month', 'Last month'], ['quarter', 'This quarter'], ['last_quarter', 'Last quarter'], ['year', 'This calendar year'], ['last_year', 'Last calendar year']]; }
    get selectedFilterCount() { return ['journal_ids', 'account_ids', 'partner_ids', 'analytic_ids'].reduce((count, key) => count + this.state.options[key].length, 0); }
    trialValues(values) { return [Math.max(values[0], 0), Math.max(-values[0], 0), values[1], values[2], Math.max(values[3], 0), Math.max(-values[3], 0), ...values.slice(4)]; }
    get tableColumns() { return this.isTrial ? ['Debit', 'Credit', 'Debit', 'Credit', 'Debit', 'Credit', ...this.state.report.columns.slice(4).map(() => 'Balance')] : this.state.report.columns; }
    get tableTotals() { return this.isTrial ? this.tableColumns.map((_, i) => this.state.report.rows.reduce((sum, row) => sum + this.trialValues(row.values)[i], 0)) : this.state.report.totals; }
    setOption(key, value) { this.state.options[key] = key === 'comparison_count' ? Number(value) : value; }
    setSearch(value) { this.state.search = value; }
    closeFilters() { Object.values(this.filterMenus).forEach(menu => menu.close()); }
    async applyFilters() { this.closeFilters(); await this.load(); }
    async openAdvanced() { this.closeFilters(); await this.advanced(); }
    get companyDomain() { return [['company_id', '=', this.state.options.company_id]]; }
    get accountDomain() { return [['company_ids', 'in', [this.state.options.company_id]]]; }
    get isAging() { return this.state.options.report.startsWith('aged_'); }
    get canCompare() { return ['profit_loss', 'balance_sheet', 'trial_balance', 'tax'].includes(this.state.options.report); }
    get hierarchyRoots() {
        const nodes = new Map();
        for (const row of this.state.report?.rows || []) {
            const path = row.account_path?.length ? row.account_path : [{ id: row.key, label: row.label }];
            const values = this.trialValues(row.values);
            let parent = null;
            for (const part of path) {
                const key = 'account-' + part.id;
                if (!nodes.has(key)) {
                    const domain = row.domain.filter(term => !(Array.isArray(term) && term[0] === 'account_id'));
                    nodes.set(key, { key, label: part.label, values: values.map(() => 0), children: [],
                        branch: [], domain: [...domain, ['account_id', 'child_of', part.id]], level: 0 });
                }
                const node = nodes.get(key);
                node.values = node.values.map((amount, i) => amount + values[i]);
                if (parent && !parent.branch.some(child => child.key === key)) {
                    parent.branch.push(node); node.parentKey = parent.key;
                }
                parent = node;
            }
        }
        const sort = nodes => nodes.sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
        for (const node of nodes.values()) { sort(node.branch); }
        return sort([...nodes.values()].filter(node => !node.parentKey));
    }
    get rows() {
        const query = this.state.search.trim().toLowerCase();
        if (this.isTrial && this.state.options.hierarchy) {
            const matches = node => node.label.toLowerCase().includes(query) || node.branch.some(matches);
            const visible = [];
            const visit = (node, level, ancestorMatches = false) => {
                const ownMatch = !!query && node.label.toLowerCase().includes(query);
                if (query && !ancestorMatches && !matches(node)) { return; }
                visible.push({ ...node, level, tree: true, treeChildren: node.branch.length,
                    open: !!query || !!this.state.expanded[node.key] });
                if (query || this.state.expanded[node.key]) {
                    node.branch.forEach(child => visit(child, level + 1, ancestorMatches || ownMatch));
                }
            };
            this.hierarchyRoots.forEach(node => visit(node, 0));
            return visible;
        }
        return (this.state.report?.rows || []).filter(row => !query || row.label.toLowerCase().includes(query)
            || row.children.some(child => child.label.toLowerCase().includes(query)))
            .map(row => this.isTrial ? { ...row, values: this.trialValues(row.values) } : row);
    }
    options() { return JSON.parse(JSON.stringify(this.state.options)); }
    async load() {
        const sequence = ++this.sequence;
        this.state.busy = true;
        this.state.error = '';
        try {
            const report = await this.orm.call('dynamic.accounting.report', 'get_report', [this.options()]);
            if (sequence === this.sequence) { this.state.report = report; }
        } catch (error) {
            if (sequence === this.sequence) {
                this.state.error = error.data?.message || error.message || 'The report could not be loaded.';
            }
        } finally {
            if (sequence === this.sequence) { this.state.busy = false; }
        }
    }
    async changeCompany(event) {
        this.state.options.company_id = Number(event.target.value);
        for (const key of ['journal_ids', 'account_ids', 'partner_ids', 'analytic_ids']) { this.state.options[key] = []; }
        await this.load();
    }
    preset(event) {
        const now = new Date();
        let start, end;
        const value = event.target.value;
        const y = now.getFullYear(), m = now.getMonth();
        if (value === 'custom') { return; }
        if (value === 'month') { start = new Date(y, m, 1); end = new Date(y, m + 1, 0); }
        if (value === 'last_month') { start = new Date(y, m - 1, 1); end = new Date(y, m, 0); }
        if (value === 'quarter') { const q = Math.floor(m / 3) * 3; start = new Date(y, q, 1); end = new Date(y, q + 3, 0); }
        if (value === 'last_quarter') { const q = Math.floor(m / 3) * 3; start = new Date(y, q - 3, 1); end = new Date(y, q, 0); }
        if (value === 'year') { start = new Date(y, 0, 1); end = new Date(y, 11, 31); }
        if (value === 'last_year') { start = new Date(y - 1, 0, 1); end = new Date(y - 1, 11, 31); }
        const iso = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
        this.state.options.date_from = iso(start); this.state.options.date_to = iso(end);
    }
    format(value) {
        return new Intl.NumberFormat(undefined, { minimumFractionDigits: this.state.report?.digits || 2,
            maximumFractionDigits: this.state.report?.digits || 2 }).format(value || 0);
    }
    toggle(row) { this.state.expanded[row.key] = !this.state.expanded[row.key]; }
    unfold() {
        if (this.isTrial && this.state.options.hierarchy) {
            const visit = node => { this.state.expanded[node.key] = true; node.branch.forEach(visit); };
            this.hierarchyRoots.forEach(visit);
        } else { for (const row of this.rows) { this.state.expanded[row.key] = true; } }
    }
    toggleMobileFilters() { this.state.mobileFilters = !this.state.mobileFilters; }
    toggleHierarchy() { this.state.options.hierarchy = !this.state.options.hierarchy; this.state.expanded = {}; }
    fold() { this.state.expanded = {}; }
    openMove(moveId) { return this.action.doAction({ type: 'ir.actions.act_window', res_model: 'account.move',
        res_id: moveId, views: [[false, 'form']], target: 'current' }); }
    openItems(row) {
        return this.action.doAction({ type: 'ir.actions.act_window', name: row.label, res_model: 'account.move.line',
            views: [[false, 'list'], [false, 'form']], domain: row.domain,
            context: { allowed_company_ids: [this.state.options.company_id] } });
    }
    async advanced() {
        const action = await this.orm.call('dynamic.accounting.report', 'legacy_action', [this.options()]);
        return this.action.doAction(action);
    }
    async exportReport(method) {
        this.state.busy = true; this.state.error = '';
        try {
            const action = await this.orm.call('dynamic.accounting.report', method, [this.options()]);
            await this.action.doAction(action);
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.busy = false; }
    }
}
registry.category('actions').add('dynamic_accounts_report.reports', DynamicReports);

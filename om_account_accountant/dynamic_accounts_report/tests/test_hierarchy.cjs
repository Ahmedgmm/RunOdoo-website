// Exercise the actual presentation logic without starting an Odoo service.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../static/src/reports.js'), 'utf8')
    .replace(/^import .*;\n/gm, '')
    .replace('export class DynamicReports', 'class DynamicReports')
    .replace(/registry.category\('actions'\).add.*;/, '') + '\nglobalThis.Reports = DynamicReports;';
const sandbox = { standardActionServiceProps: {}, Component: class {}, MultiRecordSelector: class {}, ControlPanel: class {}, Dropdown: class {}, useProps: () => ({}) };
vm.runInNewContext(source, sandbox);
const report = new sandbox.Reports();
const row = (id, values, path) => ({ key: String(id), label: path.at(-1).label, values,
    account_path: path, domain: [['company_id', '=', 1], ['account_id', '=', id]], children: [] });
const root = {id: 10, label: '100 Assets', active: false};
const group = {id: 11, label: '110 Fixed Assets', active: false};
report.state = { options: {report: 'trial_balance', hierarchy: true}, expanded: {}, search: '',
    report: { columns: ['Opening', 'Debit', 'Credit', 'Closing'], rows: [
        row(1, [100, 50, 0, 150], [root, group, {id: 1, label: '111 Equipment'}]),
        row(2, [-30, 0, 10, -40], [root, group, {id: 2, label: '112 Depreciation'}]),
        row(11, [0, 5, 0, 5], [root, group]),
        row(3, [0, 0, 20, -20], [{id: 3, label: '200 Payables'}]),
    ] }};
assert.equal(report.rows.length, 2, 'Only roots are initially visible');
const assets = report.hierarchyRoots[0];
assert.deepEqual(Array.from(assets.values), [100, 30, 55, 10, 155, 40], 'Parents sum signed debit/credit columns, including direct postings exactly once');
assert.deepEqual(Array.from(report.tableTotals), [100, 30, 55, 30, 155, 60], 'Grand total excludes subtotal duplication');
report.toggle(assets);
assert.equal(report.rows.length, 3, 'Expanding a root reveals its next level');
report.unfold();
assert.equal(report.rows.length, 5, 'Expand all visits nested groups');
report.fold();
assert.equal(report.rows.length, 2);
report.state.search = 'Equipment';
assert.deepEqual(Array.from(report.rows, row => row.label), ['100 Assets', '110 Fixed Assets', '111 Equipment'], 'Search reveals matching children with ancestors');
report.state.search = 'Fixed Assets';
assert.equal(report.rows.length, 4, 'A matching parent keeps all descendants');
report.state.search = '';
report.toggleHierarchy();
assert.equal(report.rows.length, 4, 'Flat view retains original account rows');
console.log('Hierarchy checks passed: archived headings, direct postings, subtotals, totals, nested expansion, search and flat view.');

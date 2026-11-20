{
    'name': 'Dynamic Accounting Reports',
    'version': '20.0.1.0.0',
    'category': 'Accounting',
    'author': 'RunOdoo',
    'summary': 'Interactive financial reports, comparisons, drill-down, PDF and Excel',
    'license': 'LGPL-3',
    'depends': ['accounting_pdf_reports', 'analytic', 'om_account_daily_reports'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': ['security/ir.access.csv', 'views/reports.xml', 'report/report.xml'],
    'assets': {'web.assets_backend': [
        'dynamic_accounts_report/static/src/reports.js',
        'dynamic_accounts_report/static/src/reports.xml',
        'dynamic_accounts_report/static/src/reports.scss',
    ]},
    'installable': True,
    'application': False,
}

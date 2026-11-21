{
    'name': 'Runodoo Website',
    'summary': 'Runodoo.online animated homepage (Living Stack scroll journey).',
    'version': '20.0.1.6.0',
    'category': 'Website/Website',
    'author': 'Run Odoo',
    'license': 'LGPL-3',
    'depends': ['website', 'auth_signup', 'account', 'runodoo_platform'],   # plan products → /pricing
    'data': [
        'views/report_layout.xml',
        'data/website_data.xml',
        'views/homepage.xml',
        'views/auth_templates.xml',
        'views/pages.xml',
        'views/pricing.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_runodoo/static/src/scss/home.scss',
            'website_runodoo/static/src/scss/pages.scss',
            'website_runodoo/static/src/scss/pricing.scss',
        ],
        'web.report_assets_common': [
            'website_runodoo/static/src/scss/report.scss',
        ],
    },
    'installable': True,
    'application': False,
}

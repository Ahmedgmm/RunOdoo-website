{
    'name': 'Runodoo Website',
    'summary': 'Runodoo.online animated homepage (Living Stack scroll journey).',
    'version': '20.0.1.5.0',
    'category': 'Website/Website',
    'author': 'Run Odoo',
    'license': 'LGPL-3',
    'depends': ['website', 'auth_signup', 'runodoo_platform'],   # plan products → /pricing
    'data': [
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
    },
    'installable': True,
    'application': False,
}

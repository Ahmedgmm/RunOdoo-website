{
    'name': 'Runodoo Website',
    'summary': 'Runodoo.online animated homepage (Living Stack scroll journey).',
    'version': '20.0.1.2.0',
    'category': 'Website/Website',
    'author': 'Run Odoo',
    'license': 'LGPL-3',
    'depends': ['website', 'auth_signup'],
    'data': [
        'data/website_data.xml',
        'views/homepage.xml',
        'views/auth_templates.xml',
        'views/pages.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_runodoo/static/src/scss/home.scss',
            'website_runodoo/static/src/scss/pages.scss',
        ],
    },
    'installable': True,
    'application': False,
}

{
    'name': 'Runodoo Website',
    'summary': 'Runodoo.online animated homepage (Living Stack scroll journey).',
    'version': '20.0.1.0.2',
    'category': 'Website/Website',
    'license': 'LGPL-3',
    'depends': ['website'],
    'data': [
        'data/website_data.xml',
        'views/homepage.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'website_runodoo/static/src/scss/home.scss',
        ],
    },
    'installable': True,
    'application': False,
}

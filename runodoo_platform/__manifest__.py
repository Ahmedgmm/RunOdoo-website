{
    'name': 'Run Odoo Platform',
    'summary': 'Customer portal for runodoo.online: plans, subscriptions, invoices and one-click access to the '
               'control panel (odoo-host provisioning API).',
    'description': 'See docs/SPEC-portal-sso.md in the runodoo project.',
    'version': '20.0.1.2.0',
    'category': 'Website/Website',
    'author': 'Run Odoo',
    'license': 'LGPL-3',
    # payment: any installed provider pays the invoices (Paymob on the live site)
    'depends': ['portal', 'account_payment', 'auth_signup', 'website'],
    'data': [
        'security/ir.access.csv',
        'data/ir_config_parameter.xml',
        'data/mail_templates.xml',
        'data/ir_cron.xml',
        'data/plans.xml',
        'views/res_config_settings_views.xml',
        'views/product_views.xml',
        'views/res_partner_views.xml',
        'views/subscription_views.xml',
        'views/event_views.xml',
        'views/menus.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
}

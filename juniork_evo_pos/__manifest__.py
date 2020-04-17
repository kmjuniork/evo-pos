{
    'name': 'EVO POS',
    'version': '0.1.0',
    'category': 'Core',
    'author': 'Sithu Aung',
    'website': 'http://juniork.co',
    'summary': 'EVO POS ODOO INTEGRATION',
    'support': 'info@juniork.co',
    'description': """
EVO POS FOR ODOO
====================
This module is juniork evo pos integration to odoo.
""",
    'depends': [
        'web', 'sale', 'product', 'hr', 'account'
    ],
    'data': [
        "data/hr_employee_data.xml",
        "data/res_partner_data.xml",
        "views/res_users_views.xml",
        "views/product_template_views.xml",
        "views/pos_category_views.xml",
        "views/res_partner_views.xml",
        "views/hr_views.xml",
        "views/sale_order_views.xml",
        "views/account_invoice_views.xml",
        "views/account_views.xml",
        "views/product_category_views.xml",
        "views/res_config_settings_views.xml",
        "views/stock_move_views.xml",
    ],
    'images': [],
    'installable': True,
    'auto_install': False,
}

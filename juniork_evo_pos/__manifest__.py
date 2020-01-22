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
        'web', 'sale', 'product', 'accounting_pdf_reports'
    ],
    'data': [
        "views/res_users_views.xml",
        "views/product_template_views.xml",
    ],
    'images': [],
    'installable': True,
    'auto_install': False,
}

# -*- coding: utf-8 -*-
{
    'name': "mlkgp-custom_sale",

    'summary': """
        Personnalisation du module Sale pour MLK Grand Paris""",

    'description': """
        Personnalisation du module Sale pour MLK Grand Paris :
        - Associé un devis à une opportunité sans le mode debug - modification possble uniquement par une manager.
    """,
    'license': 'LGPL-3',
    'author': "PERROTTECH",
    'website': "http://www.perrot.tech",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sales',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['sale',
                'sale_crm'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

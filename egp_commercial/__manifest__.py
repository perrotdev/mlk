{
    'name': "EGP - Suite commerciale",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Méta-addon d'installation de la suite commerciale EGP",
    'description': """
Méta-addon EGP
==============

Installe la suite commerciale EGP décrite par la spécification « Référentiel
Contacts, Pistes et Opportunités — Odoo 19 ». Il ne contient aucune logique
métier (§1.4).
""",
    'author': 'PERROTTECH',
    'website': 'https://www.perrottech.fr',
    'license': 'LGPL-3',
    'depends': [
        'egp_master_data',
        'egp_crm',
        'egp_crm_rental',
        'egp_crm_sale_project',
    ],
    'data': [],
    'installable': True,
    'application': True,
}

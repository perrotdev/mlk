{
    'name': "EGP - Référentiel Contacts et listes métier",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Référentiel unique Organisations/Contacts et listes métier administrables EGP",
    'description': """
Référentiel Contacts EGP
========================

Implémente la section 5 (Contacts) et la section 8 (Référentiels configurables)
de la spécification « Référentiel Contacts, Pistes et Opportunités — Odoo 19 ».

- extension de ``res.partner`` avec les données permanentes EGP ;
- patron commun ``egp.reference.mixin`` pour toutes les listes administrables ;
- référentiels métier (types de structure, activités, relations, statuts, ...) ;
- règles de qualité, complétude et gouvernance des données.
""",
    'author': 'PERROTTECH',
    'website': 'https://www.perrottech.fr',
    'license': 'LGPL-3',
    'depends': [
        'contacts',
        'crm',
        'utm',
        'base_vat',
        'phone_validation',
    ],
    'data': [
        'security/egp_master_data_groups.xml',
        'security/ir.model.access.csv',
        'security/egp_master_data_rules.xml',
        'data/res.partner.industry.csv',
        'data/egp.structure.type.csv',
        'data/egp.business.activity.csv',
        'data/egp.partner.relation.csv',
        'data/egp.client.status.csv',
        'data/egp.company.size.csv',
        'data/egp.contact.department.csv',
        'data/egp.contact.channel.csv',
        'data/egp.event.type.csv',
        'data/egp.market.segment.csv',
        'data/egp.lead.temperature.csv',
        'data/egp.maturity.level.csv',
        'data/egp.opportunity.type.csv',
        'data/egp.event.configuration.csv',
        'data/egp.catering.type.csv',
        'data/egp.technical.level.csv',
        'data/egp.animation.type.csv',
        'data/egp.admin.status.csv',
        'data/utm_data.xml',
        'data/ir_cron_data.xml',
        'views/egp_reference_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
        'views/egp_master_data_menus.xml',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
    ],
    'installable': True,
    'application': False,
}

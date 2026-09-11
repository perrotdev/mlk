{
    'name': "EGP - Pistes et Opportunités",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Prospection sortante, qualification, conversion et cycle de vente EGP",
    'description': """
Pistes et Opportunités EGP
==========================

Implémente les sections 6 (Pistes) et 7 (Opportunités) de la spécification
« Référentiel Contacts, Pistes et Opportunités — Odoo 19 ».

Les pistes et opportunités restent portées par le modèle natif ``crm.lead`` :
la conversion conserve le même enregistrement, son chatter, ses activités et
ses pièces jointes.

Périmètre volontairement exclu : les espaces, la disponibilité et les
engagements de location sont portés par l'addon ``egp_crm_rental``, dont
l'architecture dépend des décisions EGP-DEC-010A et EGP-DEC-020.
""",
    'author': 'PERROTTECH',
    'website': 'https://www.perrottech.fr',
    'license': 'LGPL-3',
    'depends': [
        'egp_master_data',
        'calendar',
        'base_automation',
    ],
    'data': [
        'security/egp_crm_groups.xml',
        'security/ir.model.access.csv',
        'security/egp_crm_rules.xml',
        'data/crm_team_data.xml',
        'data/crm_stage_data.xml',
        'data/crm_lost_reason_data.xml',
        'data/ir_cron_data.xml',
        'views/crm_stage_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_opportunity_views.xml',
        'views/egp_crm_menus.xml',
    ],
    'demo': [
        'demo/crm_lead_demo.xml',
    ],
    'installable': True,
    'application': False,
}

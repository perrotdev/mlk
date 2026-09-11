{
    'name': "EGP - Interfaces Ventes, Projet et Facturation",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Suivi des devis, création orchestrée du projet événementiel et indicateurs financiers",
    'description': """
Interfaces Ventes / Projet / Facturation EGP
============================================

Implémente les sections 7.9 à 7.11 et 10.6 à 10.7 de la spécification :

- suivi des devis liés à l'opportunité et relance configurable (EGP-RG-040) ;
- création idempotente du projet événementiel à la confirmation de la commande
  (EGP-RG-039, EGP-RG-041) ;
- transfert contrôlé des données CRM vers le Projet (EGP-RG-041A) et action
  explicite de mise à jour ultérieure (EGP-RG-041B) ;
- remontée en lecture seule des indicateurs Ventes et Facturation.
""",
    'author': 'PERROTTECH',
    'website': 'https://www.perrottech.fr',
    'license': 'LGPL-3',
    'depends': [
        'egp_crm',
        'sale_crm',
        'sale_project',
    ],
    'data': [
        'views/crm_lead_views.xml',
        'views/project_project_views.xml',
    ],
    'installable': True,
    'application': False,
}

{
    'name': "EGP - Espaces, disponibilité et options de location",
    'version': '19.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': "Intégration du CRM EGP avec Location et Planning pour les espaces événementiels",
    'description': """
Espaces et disponibilité EGP
============================

Implémente les sections 7.3.1 et 7.6 de la spécification, sur la base de
l'architecture arrêtée par EGP-DEC-010A :

- un espace commercialisable est un **produit de location de type Service**
  (``rent_ok = True``) rattaché à un **Rôle Planning** ;
- chaque salle physique est un **Matériel** Planning (``resource.resource`` de
  type ``material``) rattaché à ce Rôle ;
- le pont natif ``sale_renting_planning`` assure l'affectation d'une salle
  libre, le contrôle de disponibilité et la synchronisation des périodes.

Aucun modèle ``egp.space`` n'est créé, et aucune capacité n'est stockée sur le
catalogue : le nombre de personnes et la configuration de salle sont des
caractéristiques de l'événement portées par ``crm.lead`` (EGP-DEC-049).
""",
    'author': 'PERROTTECH',
    'website': 'https://www.perrottech.fr',
    'license': 'LGPL-3',
    'depends': [
        'egp_crm',
        'sale_crm',
        'sale_renting_planning',
    ],
    'data': [
        'data/ir_cron_data.xml',
        'views/crm_lead_views.xml',
        'views/egp_crm_rental_menus.xml',
    ],
    'demo': [
        'demo/crm_lead_rental_demo.xml',
    ],
    'installable': True,
    'application': False,
}

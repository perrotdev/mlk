# -*- coding: utf-8 -*-
"""
Script de migration pour supprimer le module mlkgp-custom_sale
qui a un nom invalide (tiret au lieu d'underscore)
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Supprime le module mlkgp-custom_sale qui a un nom invalide.
    Ce module doit être supprimé car Odoo 19 n'accepte plus les tirets dans les noms de modules.
    """
    _logger.info("Migration: Suppression du module mlkgp-custom_sale avec nom invalide")
    
    # Supprimer les dépendances du module
    cr.execute("""
        DELETE FROM ir_module_module_dependency 
        WHERE module_id IN (
            SELECT id FROM ir_module_module WHERE name = 'mlkgp-custom_sale'
        )
    """)
    _logger.info("Dépendances du module mlkgp-custom_sale supprimées")
    
    # Supprimer le module lui-même
    cr.execute("""
        DELETE FROM ir_module_module 
        WHERE name = 'mlkgp-custom_sale'
    """)
    _logger.info("Module mlkgp-custom_sale supprimé de la base de données")

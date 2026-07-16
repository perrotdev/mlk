# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Hook exécuté automatiquement après l'installation du module.
    Supprime le module mlkgp-custom_sale qui a un nom invalide.
    """
    _logger.info("=== Post-init hook: Nettoyage du module mlkgp-custom_sale ===")
    
    try:
        # Supprimer les dépendances du module
        env.cr.execute("""
            DELETE FROM ir_module_module_dependency 
            WHERE module_id IN (
                SELECT id FROM ir_module_module WHERE name = 'mlkgp-custom_sale'
            )
        """)
        _logger.info("Dépendances du module mlkgp-custom_sale supprimées")
        
        # Supprimer le module lui-même
        env.cr.execute("""
            DELETE FROM ir_module_module 
            WHERE name = 'mlkgp-custom_sale'
        """)
        _logger.info("Module mlkgp-custom_sale supprimé de la base de données")
        
        env.cr.commit()
        _logger.info("=== Nettoyage terminé avec succès ===")
    except Exception as e:
        _logger.error(f"Erreur lors du nettoyage: {e}")


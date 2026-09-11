from odoo import models


class CrmLead2opportunityPartner(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner'

    def _convert_and_allocate(self, leads, user_ids, team_id=False):
        """§3.5 — L'assistant natif calcule sa propre équipe par défaut à
        partir du vendeur choisi (``crm.team._get_default_team_id``) et la
        réapplique après la conversion, écrasant l'équipe Commercial EGP déjà
        positionnée par ``crm.lead.convert_opportunity()``. Ce recalcul de
        ``team_id`` déclenche à son tour un repli de l'étape sur une étape
        globale native faute de stage ``OPP_*`` pour cette équipe étrangère.
        Une seule équipe commerciale existe pour les opportunités : on la
        force donc systématiquement ici.
        """
        egp_team = self.env.ref('egp_crm.crm_team_egp_commercial', raise_if_not_found=False)
        if egp_team:
            team_id = egp_team.id
        return super()._convert_and_allocate(leads, user_ids, team_id=team_id)

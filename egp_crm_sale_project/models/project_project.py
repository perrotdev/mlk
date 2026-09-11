from odoo import _, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    egp_lead_id = fields.Many2one(
        'crm.lead', string="Opportunité", index='btree_not_null',
        ondelete='restrict', copy=False, readonly=True)
    egp_sale_order_id = fields.Many2one(
        'sale.order', string="Commande d'origine", index='btree_not_null',
        ondelete='restrict', copy=False, readonly=True)
    egp_end_customer_id = fields.Many2one('res.partner', string="Client final / bénéficiaire")
    egp_secondary_contact_ids = fields.Many2many(
        'res.partner', 'egp_project_secondary_contact_rel', 'project_id', 'partner_id',
        string="Contacts secondaires")

    # Instantané des données de production reprises du CRM (EGP-RG-041A)
    egp_event_type_id = fields.Many2one('egp.event.type', string="Type d'événement", ondelete='restrict')
    egp_market_segment_id = fields.Many2one('egp.market.segment', string="Segment de marché", ondelete='restrict')
    egp_participant_count = fields.Integer(string="Nombre de personnes")
    egp_event_start = fields.Datetime(string="Début de l'événement")
    egp_event_end = fields.Datetime(string="Fin de l'événement")
    egp_setup_required = fields.Boolean(string="Montage prévu")
    egp_setup_start = fields.Datetime(string="Début du montage")
    egp_teardown_required = fields.Boolean(string="Démontage prévu")
    egp_teardown_end = fields.Datetime(string="Fin du démontage")
    egp_configuration_id = fields.Many2one('egp.event.configuration', string="Configuration", ondelete='restrict')
    egp_constraints = fields.Html(string="Contraintes")
    egp_client_objectives = fields.Html(string="Objectifs du client")
    egp_catering_required = fields.Boolean(string="Restauration")
    egp_av_required = fields.Boolean(string="Technique audiovisuelle")
    egp_furniture_required = fields.Boolean(string="Mobilier spécifique")
    egp_animation_required = fields.Boolean(string="Animation")
    egp_security_required = fields.Boolean(string="Sécurité")
    egp_reception_required = fields.Boolean(string="Accueil")
    egp_parking_required = fields.Boolean(string="Parking")

    def action_egp_update_from_crm(self):
        """EGP-RG-041B — Rafraîchissement explicite, jamais silencieux."""
        for project in self:
            if not project.egp_lead_id:
                raise UserError(_("Ce projet n'est rattaché à aucune opportunité."))
            lead = project.egp_lead_id
            values = {}
            for fname in lead._egp_crm_to_project_fields():
                value = lead[fname]
                values[fname] = value.id if isinstance(value, models.Model) else value
            project.write(values)
            project.message_post(body=_(
                "Données de production rafraîchies depuis l'opportunité %s.", lead.display_name))
        return True

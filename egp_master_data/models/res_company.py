from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Paramètres administrables EGP-PAR-001 à EGP-PAR-012 (spécification §10.2)
    egp_first_call_delay_days = fields.Integer(
        string="Délai du premier appel (jours)", default=1)
    egp_lead_inactivity_days = fields.Integer(
        string="Délai d'inactivité d'une piste (jours)", default=15)
    egp_quotation_follow_up_days = fields.Integer(
        string="Délai de relance après envoi d'un devis (jours)", default=5)
    egp_option_notice_days = fields.Integer(
        string="Préavis avant fin d'option (jours)", default=2)
    egp_option_escalation_days = fields.Integer(
        string="Délai d'escalade après option expirée (jours)", default=1)
    egp_dormant_customer_delay_months = fields.Integer(
        string="Délai de passage client dormant (mois)", default=12)
    egp_regular_customer_min_events = fields.Integer(
        string="Nombre minimal d'événements pour « Client régulier »", default=0)
    egp_regular_customer_window_months = fields.Integer(
        string="Fenêtre glissante « Client régulier » (mois)", default=12)

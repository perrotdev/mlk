from odoo import _, api, fields, models

# EGP-RG-041A : liste versionnée des données transférées du CRM vers le Projet.
# Les informations commerciales sensibles (marge, concurrence, stratégie, notes
# de management) en sont volontairement absentes.
# Les espaces sont transférés par un pont dédié : ils dépendent de Location,
# absent des dépendances de cet addon (EGP-DEC-010A).
CRM_TO_PROJECT_FIELDS = [
    'egp_event_type_id',
    'egp_market_segment_id',
    'egp_participant_count',
    'egp_event_start',
    'egp_event_end',
    'egp_setup_required',
    'egp_setup_start',
    'egp_teardown_required',
    'egp_teardown_end',
    'egp_configuration_id',
    'egp_constraints',
    'egp_client_objectives',
    'egp_catering_required',
    'egp_av_required',
    'egp_furniture_required',
    'egp_animation_required',
    'egp_security_required',
    'egp_reception_required',
    'egp_parking_required',
]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def _egp_crm_to_project_fields(self):
        """Point d'extension pour les addons ajoutant des données de production."""
        return list(CRM_TO_PROJECT_FIELDS)

    # ------------------------------------------------------------------
    # Indicateurs d'intégration — §7.11, tous en lecture seule
    # ------------------------------------------------------------------
    egp_quotation_count = fields.Integer(
        string="Devis", compute='_compute_egp_sale_indicators', compute_sudo=True)
    egp_order_count = fields.Integer(
        string="Commandes", compute='_compute_egp_sale_indicators', compute_sudo=True)
    egp_signed_revenue = fields.Monetary(
        string="CA signé", currency_field='company_currency',
        compute='_compute_egp_sale_indicators', compute_sudo=True)
    egp_invoiced_revenue = fields.Monetary(
        string="CA facturé", currency_field='company_currency',
        compute='_compute_egp_invoice_indicators', compute_sudo=True)
    egp_paid_revenue = fields.Monetary(
        string="CA encaissé", currency_field='company_currency',
        compute='_compute_egp_invoice_indicators', compute_sudo=True)
    egp_first_quotation_sent_date = fields.Datetime(
        string="Date de premier envoi de devis", readonly=True, copy=False)
    egp_project_ids = fields.One2many(
        'project.project', 'egp_lead_id', string="Projets liés")
    egp_main_project_id = fields.Many2one(
        'project.project', string="Projet principal", readonly=True, copy=False,
        index='btree_not_null')
    egp_project_status = fields.Selection(
        related='egp_main_project_id.last_update_status', string="Statut production", readonly=True)

    @api.depends('order_ids.state', 'order_ids.amount_untaxed')
    def _compute_egp_sale_indicators(self):
        for lead in self:
            orders = lead.order_ids
            confirmed = orders.filtered(lambda order: order.state == 'sale')
            lead.egp_quotation_count = len(orders.filtered(lambda order: order.state in ('draft', 'sent')))
            lead.egp_order_count = len(confirmed)
            lead.egp_signed_revenue = sum(confirmed.mapped('amount_untaxed'))

    @api.depends('order_ids.invoice_ids.state', 'order_ids.invoice_ids.amount_untaxed_signed')
    def _compute_egp_invoice_indicators(self):
        for lead in self:
            invoices = lead.order_ids.invoice_ids.filtered(
                lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund'))
            lead.egp_invoiced_revenue = sum(invoices.mapped('amount_untaxed_signed'))
            lead.egp_paid_revenue = sum(
                invoice.amount_total_signed - invoice.amount_residual_signed for invoice in invoices)

    def _egp_stage_transition_errors(self, stage):
        """§7.12 — Passer en négociation suppose une proposition envoyée et tracée."""
        errors = super()._egp_stage_transition_errors(stage)
        if stage.egp_code == 'OPP_NEGOTIATION' and not self.order_ids.filtered(
                lambda order: order.state in ('sent', 'sale')):
            errors.append(_("Au moins un devis doit avoir été envoyé au client."))
        if stage.egp_code in ('OPP_WON', 'OPP_DEPOSIT_PAID', 'OPP_EVENT_DONE', 'OPP_CLOSED') \
                and not self.order_ids.filtered(lambda order: order.state == 'sale'):
            errors.append(_("Une commande confirmée est requise pour cette étape."))
        return errors

    def action_egp_view_projects(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Projets événementiels"),
            'res_model': 'project.project',
            'view_mode': 'list,form',
            'domain': [('egp_lead_id', '=', self.id)],
        }

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_quotation_send(self):
        action = super().action_quotation_send()
        self._egp_schedule_quotation_follow_up()
        return action

    def action_confirm(self):
        res = super().action_confirm()
        self._egp_create_event_projects()
        return res

    # ------------------------------------------------------------------
    # EGP-RG-040 — Une seule relance active par opportunité
    # ------------------------------------------------------------------
    def _egp_schedule_quotation_follow_up(self):
        summary = _("Relancer le devis")
        for order in self.filtered('opportunity_id'):
            lead = order.opportunity_id
            if not lead.egp_first_quotation_sent_date:
                lead.egp_first_quotation_sent_date = fields.Datetime.now()
            # La relance de la version précédente est neutralisée avant d'en créer une nouvelle.
            lead.activity_ids.filtered(lambda activity: activity.summary == summary).unlink()
            delay = order.company_id.egp_quotation_follow_up_days or 5
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(order) + relativedelta(days=delay),
                summary=summary,
                note=_("Relancer le client sur le devis %s.", order.name),
                user_id=(lead.user_id or order.user_id or self.env.user).id,
            )

    # ------------------------------------------------------------------
    # EGP-RG-039 / EGP-RG-041 — Création idempotente du projet événementiel
    # ------------------------------------------------------------------
    def _egp_create_event_projects(self):
        Project = self.env['project.project']
        for order in self.filtered(lambda record: record.opportunity_id and record.state == 'sale'):
            lead = order.opportunity_id
            existing = Project.search([('egp_lead_id', '=', lead.id)], limit=1)
            if existing:
                if not lead.egp_main_project_id:
                    lead.egp_main_project_id = existing
                if not order.project_id:
                    order.project_id = existing
                continue
            project = Project.create(order._egp_prepare_project_values())
            lead.egp_main_project_id = project
            if not order.project_id:
                order.project_id = project
            lead.message_post(body=_(
                "Projet événementiel %(project)s créé depuis la commande %(order)s.",
                project=project.display_name, order=order.name,
            ))
            project.message_post(body=_(
                "Données de production reprises de l'opportunité %s.", lead.display_name))

    def _egp_prepare_project_values(self):
        self.ensure_one()
        lead = self.opportunity_id
        values = {
            'name': lead.name,
            'partner_id': lead.partner_id.id,
            'company_id': self.company_id.id,
            'egp_lead_id': lead.id,
            'egp_sale_order_id': self.id,
            'egp_end_customer_id': lead.egp_end_customer_id.id,
            'egp_secondary_contact_ids': [(6, 0, lead.egp_secondary_contact_ids.ids)],
        }
        for fname in lead._egp_crm_to_project_fields():
            value = lead[fname]
            values[fname] = value.id if isinstance(value, models.Model) else value
        if lead.egp_event_start:
            values['date_start'] = fields.Date.to_date(lead.egp_occupancy_start or lead.egp_event_start)
        if lead.egp_event_end:
            values['date'] = fields.Date.to_date(lead.egp_occupancy_end or lead.egp_event_end)
        return values

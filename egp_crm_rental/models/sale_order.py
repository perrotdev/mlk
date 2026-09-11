from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    egp_rental_dates_synced = fields.Boolean(
        string="Dates de location synchronisées", compute='_compute_egp_rental_dates_synced',
        help="Faux lorsque les dates de location divergent de la période qualifiée "
             "sur l'opportunité liée (EGP-RG-034D).")

    @api.depends('opportunity_id.egp_occupancy_start', 'opportunity_id.egp_occupancy_end',
                 'rental_start_date', 'rental_return_date', 'is_rental_order')
    def _compute_egp_rental_dates_synced(self):
        for order in self:
            start, end = order._egp_get_expected_rental_dates()
            order.egp_rental_dates_synced = not start or not end or (
                order.rental_start_date == start and order.rental_return_date == end
            )

    def _egp_get_expected_rental_dates(self):
        """Période qualifiée sur l'opportunité, montage et démontage inclus."""
        self.ensure_one()
        lead = self.opportunity_id
        if not lead or not self.is_rental_order:
            return False, False
        return (
            lead.egp_occupancy_start or lead.egp_event_start,
            lead.egp_occupancy_end or lead.egp_event_end,
        )

    # ------------------------------------------------------------------
    # EGP-RG-034B — Reprise des données de qualification à la création
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._egp_apply_qualification_defaults()
        return orders

    def _egp_apply_qualification_defaults(self):
        """N'alimente que la création initiale : aucune saisie manuelle n'est écrasée."""
        for order in self.filtered(lambda record: record.opportunity_id and record.state == 'draft'):
            lead = order.opportunity_id
            start, end = lead.egp_occupancy_start or lead.egp_event_start, \
                lead.egp_occupancy_end or lead.egp_event_end
            values = {}
            if start and not order.rental_start_date:
                values['rental_start_date'] = start
            if end and not order.rental_return_date:
                values['rental_return_date'] = end
            if values:
                order.write(values)
            if lead.egp_space_ids and not order.order_line:
                order._egp_create_space_lines()

    def _egp_create_space_lines(self):
        """Une ligne de location par espace envisagé, modifiable ensuite librement."""
        self.ensure_one()
        lead = self.opportunity_id
        note = _(
            "Événement : %(participants)s personne(s), configuration %(configuration)s.",
            participants=lead.egp_participant_count or _("non précisé"),
            configuration=lead.egp_configuration_id.name or _("non précisée"),
        )
        self.env['sale.order.line'].create([
            {
                'order_id': self.id,
                'product_id': space.id,
                'is_rental': True,
                'name': f"{space.display_name}\n{note}",
            }
            for space in lead.egp_space_ids
        ])

    # ------------------------------------------------------------------
    # EGP-RG-034D — Mise à jour explicite des dates, jamais silencieuse
    # ------------------------------------------------------------------
    def action_egp_sync_rental_dates(self):
        self.ensure_one()
        start, end = self._egp_get_expected_rental_dates()
        if not start or not end:
            return False
        self.write({'rental_start_date': start, 'rental_return_date': end})
        self.message_post(body=_(
            "Dates de location alignées sur la période qualifiée de l'opportunité %s.",
            self.opportunity_id.display_name,
        ))
        return True

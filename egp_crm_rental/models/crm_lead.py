from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# Un espace commercialisable est un produit de location de type Service
# rattaché à un Rôle Planning (EGP-DEC-010A, §7.3.1).
SPACE_PRODUCT_DOMAIN = [('rent_ok', '=', True), ('type', '=', 'service')]


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ------------------------------------------------------------------
    # Espaces envisagés — intention commerciale, sans engagement (§7.6)
    # ------------------------------------------------------------------
    egp_space_ids = fields.Many2many(
        'product.product', 'egp_lead_space_rel', 'lead_id', 'product_id',
        string="Espaces souhaités", domain=SPACE_PRODUCT_DOMAIN,
        help="Expression d'un besoin commercial : la sélection ne réserve rien "
             "et ne consomme aucune disponibilité.")
    egp_main_space_id = fields.Many2one(
        'product.product', string="Espace principal", domain=SPACE_PRODUCT_DOMAIN,
        index='btree_not_null', ondelete='restrict', tracking=True)

    # ------------------------------------------------------------------
    # Options commerciales — §7.6, phase de maintien d'option
    # ------------------------------------------------------------------
    egp_option_active = fields.Boolean(string="Option en cours", tracking=True, copy=False)
    egp_option_start = fields.Datetime(string="Début d'option", copy=False)
    egp_option_end = fields.Datetime(
        string="Fin d'option", index='btree_not_null', tracking=True, copy=False)
    egp_option_space_ids = fields.Many2many(
        'product.product', 'egp_lead_option_space_rel', 'lead_id', 'product_id',
        string="Espaces sous option", domain=SPACE_PRODUCT_DOMAIN)
    egp_option_status = fields.Selection(
        [
            ('none', "Aucune option"),
            ('active', "Option active"),
            ('expiring', "Option proche de l'échéance"),
            ('expired', "Option expirée"),
            ('confirmed', "Option confirmée"),
            ('released', "Option libérée"),
        ],
        string="État d'option", default='none', index=True, readonly=True, copy=False,
        help="Les états « proche de l'échéance » et « expirée » dépendent du temps : "
             "ils sont rafraîchis par tâche planifiée (EGP-DEC-044).")
    egp_option_decision_date = fields.Datetime(
        string="Date de décision sur option", readonly=True, copy=False)
    egp_option_notes = fields.Text(string="Commentaire sur l'option")
    egp_option_urgency = fields.Selection(
        [
            ('ok', "Plus de 2 semaines"),
            ('warning', "Entre 2 semaines et 3 jours"),
            ('urgent', "Moins de 3 jours"),
            ('expired', "Expirée"),
        ],
        string="Urgence de l'option", compute='_compute_egp_option_urgency',
        help="Calculé à l'affichage (non stocké) pour colorer le badge Kanban : "
             "aucune tâche planifiée n'est nécessaire pour ce seul usage visuel.")

    # ------------------------------------------------------------------
    # Reflet en lecture des engagements de location — §7.6
    # ------------------------------------------------------------------
    egp_space_booking_ids = fields.Many2many(
        'planning.slot', string="Réservations de location",
        compute='_compute_egp_space_bookings', compute_sudo=True)
    egp_space_booking_count = fields.Integer(
        string="Réservations", compute='_compute_egp_space_bookings', compute_sudo=True)
    egp_space_availability_state = fields.Selection(
        [
            ('unknown', "Non évaluée"),
            ('available', "Disponible"),
            ('partial', "Partiellement disponible"),
            ('conflict', "Indisponible"),
        ],
        string="Disponibilité des espaces", compute='_compute_egp_space_availability_state',
        help="Indicateur informatif calculé à la volée depuis les créneaux Planning. "
             "Il ne pose ni option ni réservation (EGP-RG-034C).")

    # ==================================================================
    # CALCULS
    # ==================================================================
    def _compute_egp_space_bookings(self):
        """Les créneaux Planning issus des commandes de location liées à l'affaire."""
        for lead in self:
            slots = lead.order_ids.order_line.planning_slot_ids
            lead.egp_space_booking_ids = slots
            lead.egp_space_booking_count = len(slots)

    @api.depends('egp_option_active', 'egp_option_end')
    def _compute_egp_option_urgency(self):
        now = fields.Datetime.now()
        for lead in self:
            if not lead.egp_option_active or not lead.egp_option_end:
                lead.egp_option_urgency = False
                continue
            remaining = lead.egp_option_end - now
            if remaining <= timedelta(0):
                lead.egp_option_urgency = 'expired'
            elif remaining <= timedelta(days=3):
                lead.egp_option_urgency = 'urgent'
            elif remaining <= timedelta(days=14):
                lead.egp_option_urgency = 'warning'
            else:
                lead.egp_option_urgency = 'ok'

    def _compute_egp_space_availability_state(self):
        """EGP-RG-034C — Interrogation à la volée, jamais un référentiel parallèle."""
        for lead in self:
            lead.egp_space_availability_state = lead._egp_evaluate_space_availability()

    def _egp_evaluate_space_availability(self):
        self.ensure_one()
        start = self.egp_occupancy_start or self.egp_event_start
        end = self.egp_occupancy_end or self.egp_event_end
        if not self.egp_space_ids or not start or not end:
            return 'unknown'
        available_count = sum(
            1 for space in self.egp_space_ids
            if self._egp_get_available_resources(space, start, end)
        )
        if not available_count:
            return 'conflict'
        if available_count < len(self.egp_space_ids):
            return 'partial'
        return 'available'

    @api.model
    def _egp_get_available_resources(self, space, start, end):
        """Matériels du Rôle de l'espace libres sur la période demandée.

        Reprend la logique native de ``sale_renting_planning`` : un matériel est
        indisponible s'il porte déjà un créneau chevauchant ou un congé de
        ressource sur la période.
        """
        role = space.planning_role_id
        resources = role.resource_ids
        if not resources:
            return self.env['resource.resource']
        busy_slots = self.env['planning.slot'].sudo().search([
            ('resource_id', 'in', resources.ids),
            ('start_datetime', '<=', end),
            ('end_datetime', '>=', start),
        ])
        leaves = self.env['resource.calendar.leaves'].sudo().search([
            ('resource_id', 'in', resources.ids),
            ('date_from', '<=', end),
            ('date_to', '>=', start),
        ])
        unavailable = busy_slots.resource_id | leaves.resource_id
        return resources - unavailable

    # ==================================================================
    # CONTRAINTES
    # ==================================================================
    @api.constrains('egp_space_ids', 'egp_main_space_id')
    def _check_egp_main_space(self):
        """EGP-FLD-OPP-020 — L'espace principal appartient aux espaces envisagés."""
        for lead in self.filtered('egp_main_space_id'):
            if lead.egp_main_space_id not in lead.egp_space_ids:
                raise ValidationError(_(
                    "L'espace principal « %(space)s » doit figurer parmi les espaces envisagés.",
                    space=lead.egp_main_space_id.display_name,
                ))

    @api.constrains('egp_option_active', 'egp_option_start', 'egp_option_end', 'egp_option_space_ids')
    def _check_egp_option(self):
        """EGP-RG-032 — Une option incomplète est refusée."""
        for lead in self.filtered('egp_option_active'):
            if not lead.egp_option_start or not lead.egp_option_end:
                raise ValidationError(_("Une option active exige une date de début et une date de fin."))
            if lead.egp_option_end <= lead.egp_option_start:
                raise ValidationError(_("La fin d'option doit être postérieure à son début."))
            if not lead.egp_option_space_ids:
                raise ValidationError(_("Une option active exige au moins un espace."))

    @api.onchange('egp_space_ids')
    def _onchange_egp_space_ids(self):
        """Un espace unique devient l'espace principal ; un retrait le remet à blanc."""
        for lead in self:
            if len(lead.egp_space_ids) == 1:
                lead.egp_main_space_id = lead.egp_space_ids
            elif lead.egp_main_space_id not in lead.egp_space_ids:
                lead.egp_main_space_id = False

    # ==================================================================
    # SURCHARGES ORM
    # ==================================================================
    def write(self, vals):
        if vals.get('egp_option_active') is False:
            vals.setdefault('egp_option_status', 'released')
            vals.setdefault('egp_option_decision_date', fields.Datetime.now())
        elif vals.get('egp_option_active') is True:
            vals.setdefault('egp_option_status', 'active')
        return super().write(vals)

    # ==================================================================
    # ACTIONS
    # ==================================================================
    def action_egp_option_confirm(self):
        self.ensure_one()
        self.write({
            'egp_option_status': 'confirmed',
            'egp_option_decision_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Option confirmée."))

    def action_egp_option_release(self):
        self.ensure_one()
        self.write({
            'egp_option_active': False,
            'egp_option_status': 'released',
            'egp_option_decision_date': fields.Datetime.now(),
        })
        self.message_post(body=_("Option libérée."))

    def action_egp_check_space_availability(self):
        """EGP-RG-034C — Ouvre le Planning natif filtré sur les espaces et la période."""
        self.ensure_one()
        if not self.egp_space_ids:
            raise UserError(_("Sélectionnez d'abord les espaces envisagés."))
        roles = self.egp_space_ids.planning_role_id
        if not roles:
            raise UserError(_(
                "Aucun rôle Planning n'est rattaché aux espaces envisagés : "
                "la disponibilité ne peut pas être vérifiée."))
        action = self.env['ir.actions.actions']._for_xml_id(
            'planning.planning_action_schedule_by_resource')
        action['domain'] = [('role_id', 'in', roles.ids)]
        start = self.egp_occupancy_start or self.egp_event_start
        if start:
            action['context'] = dict(
                self.env.context,
                initialDate=fields.Datetime.to_string(start),
                search_default_group_by_resource=1,
            )
        return action

    def action_egp_view_space_bookings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Réservations de location"),
            'res_model': 'planning.slot',
            'view_mode': 'gantt,list,form',
            'domain': [('id', 'in', self.egp_space_booking_ids.ids)],
        }

    # ==================================================================
    # TÂCHES PLANIFIÉES — EGP-DEC-044
    # ==================================================================
    @api.model
    def _cron_egp_update_option_status(self, batch_size=5000):
        """EGP-RG-033 — États d'option dépendant du temps et rappels avant échéance."""
        now = fields.Datetime.now()
        leads = self.search([
            ('egp_option_active', '=', True),
            ('egp_option_status', 'in', ('active', 'expiring')),
        ], limit=batch_size)
        summary = _("Décision attendue sur l'option")
        for lead in leads:
            if not lead.egp_option_end:
                continue
            notice = lead.company_id.egp_option_notice_days or self.env.company.egp_option_notice_days
            if lead.egp_option_end <= now:
                lead.egp_option_status = 'expired'
                lead.message_post(body=_("L'option est arrivée à échéance sans décision."))
            elif lead.egp_option_end - relativedelta(days=notice or 0) <= now:
                lead.egp_option_status = 'expiring'
                if not lead.activity_ids.filtered(lambda activity: activity.summary == summary):
                    lead.activity_schedule(
                        'mail.mail_activity_data_todo',
                        date_deadline=fields.Date.to_date(lead.egp_option_end),
                        summary=summary,
                        user_id=(lead.user_id or self.env.user).id,
                    )
        return True

    @api.model
    def _cron_egp_escalate_expired_options(self, batch_size=5000):
        """EGP-RG-033 — Escalade à la Responsable commerciale après expiration."""
        managers = self.env.ref('egp_crm.group_egp_sales_manager', raise_if_not_found=False)
        if not managers or not managers.user_ids:
            return True
        now = fields.Datetime.now()
        leads = self.search([
            ('egp_option_active', '=', True),
            ('egp_option_status', '=', 'expired'),
        ], limit=batch_size)
        for lead in leads:
            delay = lead.company_id.egp_option_escalation_days or self.env.company.egp_option_escalation_days
            if not lead.egp_option_end or lead.egp_option_end + relativedelta(days=delay or 0) > now:
                continue
            lead.message_post(
                body=_("Option expirée sans décision : arbitrage attendu."),
                partner_ids=managers.user_ids.partner_id.ids,
            )
        return True

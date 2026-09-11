import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Sources autorisées pour une piste de prospection sortante (EGP-RG-001, §8.8).
OUTBOUND_SOURCE_XMLIDS = [
    'egp_master_data.utm_source_egp_reactivation',
    'egp_master_data.utm_source_egp_research',
    'egp_master_data.utm_source_egp_adn_data',
]

# EGP-DEC-029 : seuls ces champs sont modifiables par l'ADV (§11.9.1).
ADV_ALLOWED_FIELDS = {
    'egp_admin_status_id',
    'egp_admin_complete',
    'egp_admin_complete_date',
    'egp_admin_closure_date',
    'egp_adv_notes',
    'message_follower_ids',
    'message_ids',
    'activity_ids',
}

# Champs dont la modification est réservée aux rôles d'encadrement (§11.9).
RESTRICTED_FIELDS = {
    'user_id',
    'team_id',
    'company_id',
    'type',
    'egp_prospector_id',
    'egp_framework_parent_id',
    'egp_duplicate_override',
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ------------------------------------------------------------------
    # Identification et origine — §6.3.1
    # ------------------------------------------------------------------
    egp_prospector_id = fields.Many2one(
        'res.users', string="Prospecteur d'origine", index='btree_not_null',
        tracking=True, domain="[('share', '=', False)]",
        help="Conservé après conversion, contrairement au responsable courant.")
    egp_creation_mode = fields.Selection(
        [
            ('outbound', "Prospection sortante"),
            ('inbound_direct', "Demande entrante directe"),
            ('legacy_unknown', "Historique indéterminé"),
            ('other', "Autre"),
        ],
        string="Mode de création", index=True, copy=False)
    egp_secondary_contact_ids = fields.Many2many(
        'res.partner', 'egp_lead_secondary_contact_rel', 'lead_id', 'partner_id',
        string="Contacts secondaires")
    egp_adn_data_ref = fields.Char(string="Référence ADN Data", copy=False, index='btree_not_null')
    # Champs de commodité : le type de structure et le secteur appartiennent à
    # l'organisation (res.partner), mais sont exigés par la qualification
    # (§6.4). Les exposer ici évite d'obliger le Prospecteur à ouvrir la fiche
    # Contact pour compléter un critère bloquant la conversion. Le suivi est
    # désactivé : ces valeurs sont déjà tracées sur la fiche Contact, et un
    # champ related hérite sinon silencieusement du tracking de sa cible.
    egp_org_structure_type_id = fields.Many2one(
        related='partner_id.commercial_partner_id.egp_structure_type_id',
        string="Type de structure de l'organisation", readonly=False, tracking=False)
    egp_org_industry_id = fields.Many2one(
        related='partner_id.commercial_partner_id.industry_id',
        string="Secteur d'activité de l'organisation", readonly=False, tracking=False)

    # ------------------------------------------------------------------
    # Qualification du besoin — §6.3.2
    # ------------------------------------------------------------------
    egp_event_type_id = fields.Many2one(
        'egp.event.type', string="Type d'événement",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_market_segment_id = fields.Many2one(
        'egp.market.segment', string="Segment de marché",
        index='btree_not_null', ondelete='restrict')
    egp_participant_count = fields.Integer(string="Nombre de personnes")
    egp_annual_event_count = fields.Integer(
        string="Nombre d'événements annuels",
        help="Volume annuel estimé du prospect : indicateur de potentiel récurrent.")
    egp_event_period_note = fields.Char(string="Date ou période pressentie")
    egp_event_start = fields.Datetime(string="Début de l'événement", index='btree_not_null', tracking=True)
    egp_event_end = fields.Datetime(string="Fin de l'événement", tracking=True)
    egp_event_calendar_title = fields.Char(
        string="Titre calendrier", compute='_compute_egp_event_calendar_title',
        help="« Titre - Client », utilisé comme titre des événements du calendrier EGP-VIEW-OPP-004.")
    egp_client_budget = fields.Monetary(string="Budget client", currency_field='company_currency')
    egp_need_description = fields.Html(string="Description du besoin")
    egp_constraints = fields.Html(string="Contraintes")
    egp_client_objectives = fields.Html(string="Objectifs du client")

    # ------------------------------------------------------------------
    # Qualification commerciale et signaux — §6.3.3
    # ------------------------------------------------------------------
    egp_temperature_id = fields.Many2one(
        'egp.lead.temperature', string="Température",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_is_grand_account = fields.Boolean(string="Grand compte", tracking=True)
    egp_is_framework_potential = fields.Boolean(string="Contrat cadre potentiel", tracking=True)
    egp_is_tender = fields.Boolean(string="Appel d'offres", tracking=True)
    egp_is_multisite = fields.Boolean(string="Besoin multisites", tracking=True)
    egp_is_recurring_event = fields.Boolean(string="Événements récurrents", tracking=True)
    egp_has_multiple_needs = fields.Boolean(string="Besoins multiples", tracking=True)

    # ------------------------------------------------------------------
    # État de qualification — §6.3.4
    # ------------------------------------------------------------------
    egp_qualification_state = fields.Selection(
        [
            ('incomplete', "Qualification incomplète"),
            ('ready', "Prête à convertir"),
            ('converted', "Convertie"),
        ],
        string="État de qualification", compute='_compute_egp_qualification',
        store=True, index=True, tracking=True)
    egp_missing_qualification = fields.Text(
        string="Critères manquants", compute='_compute_egp_qualification')
    egp_qualified_date = fields.Datetime(string="Date de qualification", readonly=True, copy=False)
    egp_follow_up_date = fields.Date(string="Date de prochaine relance", tracking=True)
    egp_inactive_days = fields.Integer(
        string="Inactivité (jours)", readonly=True, copy=False,
        help="Mis à jour par tâche planifiée : cet indicateur dépend de l'écoulement du temps.")
    egp_is_inactive = fields.Boolean(
        string="Piste inactive", readonly=True, index='btree_not_null', copy=False)
    egp_duplicate_override = fields.Boolean(string="Dérogation doublon", copy=False, tracking=True)
    egp_duplicate_override_reason = fields.Text(string="Justification de la dérogation", copy=False)
    egp_duplicate_need_ids = fields.Many2many(
        'crm.lead', string="Dossiers en doublon potentiel",
        compute='_compute_egp_duplicate_need_ids', compute_sudo=True)
    egp_duplicate_need_count = fields.Integer(
        string="Doublons de besoin", compute='_compute_egp_duplicate_need_ids', compute_sudo=True)

    # ------------------------------------------------------------------
    # Identification de l'opportunité — §7.2
    # ------------------------------------------------------------------
    egp_opportunity_type_id = fields.Many2one(
        'egp.opportunity.type', string="Type d'opportunité",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_opportunity_type_code = fields.Char(
        related='egp_opportunity_type_id.code', string="Code type d'opportunité")
    egp_framework_parent_id = fields.Many2one(
        'crm.lead', string="Contrat cadre", index='btree_not_null',
        ondelete='restrict', tracking=True,
        domain="[('type', '=', 'opportunity'), ('egp_opportunity_type_id.code', '=', 'FRAMEWORK')]")
    egp_framework_child_ids = fields.One2many(
        'crm.lead', 'egp_framework_parent_id', string="Événements sous contrat")
    egp_intermediation_type = fields.Selection(
        [
            ('direct', "Vente directe"),
            ('agency', "Agence contractante"),
            ('introducer', "Apporteur d'affaire"),
        ],
        string="Type d'intermédiation", default='direct', tracking=True)
    egp_end_customer_id = fields.Many2one(
        'res.partner', string="Client final / bénéficiaire",
        domain="[('is_company', '=', True)]", index='btree_not_null')
    egp_end_customer_contact_id = fields.Many2one(
        'res.partner', string="Contact du client final",
        domain="[('parent_id', '=', egp_end_customer_id)]")
    egp_business_introducer_id = fields.Many2one(
        'res.partner', string="Apporteur d'affaire", index='btree_not_null', tracking=True)

    # ------------------------------------------------------------------
    # Bloc Événement — §7.3
    # ------------------------------------------------------------------
    egp_configuration_id = fields.Many2one(
        'egp.event.configuration', string="Configuration", ondelete='restrict')
    egp_setup_required = fields.Boolean(string="Montage prévu")
    egp_teardown_required = fields.Boolean(string="Démontage prévu")
    egp_setup_start = fields.Datetime(string="Début du montage")
    egp_teardown_end = fields.Datetime(string="Fin du démontage")
    egp_occupancy_start = fields.Datetime(
        string="Début d'occupation", compute='_compute_egp_occupancy', store=True)
    egp_occupancy_end = fields.Datetime(
        string="Fin d'occupation", compute='_compute_egp_occupancy', store=True)
    egp_sold_day_count = fields.Float(
        string="Journées vendues", compute='_compute_egp_occupancy', store=True, digits=(6, 2))

    # ------------------------------------------------------------------
    # Bloc Prestations — §7.4
    # ------------------------------------------------------------------
    egp_catering_required = fields.Boolean(string="Restauration souhaitée")
    egp_catering_type_ids = fields.Many2many(
        'egp.catering.type', 'egp_lead_catering_type_rel', 'lead_id', 'catering_type_id',
        string="Types de restauration")
    egp_av_required = fields.Boolean(string="Technique audiovisuelle")
    egp_technical_level_id = fields.Many2one(
        'egp.technical.level', string="Niveau technique", ondelete='restrict')
    egp_furniture_required = fields.Boolean(string="Mobilier spécifique")
    egp_furniture_notes = fields.Text(string="Description du mobilier")
    egp_animation_required = fields.Boolean(string="Animation souhaitée")
    egp_animation_type_ids = fields.Many2many(
        'egp.animation.type', 'egp_lead_animation_type_rel', 'lead_id', 'animation_type_id',
        string="Types d'animation")
    egp_security_required = fields.Boolean(string="Sécurité")
    egp_reception_required = fields.Boolean(string="Accueil")
    egp_parking_required = fields.Boolean(string="Parking")
    egp_other_service_notes = fields.Html(string="Autres prestations")

    # ------------------------------------------------------------------
    # Qualification commerciale — §7.5
    # ------------------------------------------------------------------
    egp_maturity_id = fields.Many2one(
        'egp.maturity.level', string="Niveau de maturité",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_competition_notes = fields.Text(string="Concurrence")
    egp_competitor_id = fields.Many2one('res.partner', string="Concurrent retenu")
    egp_decision_date = fields.Date(string="Date de décision estimée")
    egp_blocking_reasons = fields.Html(string="Motifs de blocage")
    egp_risk_notes = fields.Html(string="Risques identifiés")
    egp_management_notes = fields.Html(
        string="Notes de management",
        groups='egp_crm.group_egp_sales_manager')
    egp_is_at_risk = fields.Boolean(
        string="Dossier à risque", compute='_compute_egp_is_at_risk',
        help="Un risque a été documenté sur ce dossier (§9.4, EGP-VIEW-OPP-001).")
    egp_is_deposit_pending = fields.Boolean(
        string="Acompte en attente", compute='_compute_egp_is_deposit_pending',
        help="Opportunité gagnée dont l'acompte n'a pas encore été enregistré (§9.4, EGP-VIEW-OPP-001).")

    # Les espaces, l'option commerciale et la disponibilité de location sont
    # portés par l'addon egp_crm_rental (EGP-DEC-010A) : ils requièrent
    # product.product / planning.role, absents des dépendances de ce module.

    # ------------------------------------------------------------------
    # Contrat cadre — §7.8
    # ------------------------------------------------------------------
    egp_framework_start_date = fields.Date(string="Début du contrat cadre")
    egp_framework_end_date = fields.Date(string="Fin du contrat cadre")
    egp_framework_reference = fields.Char(string="Référence du contrat")
    egp_framework_target_amount = fields.Monetary(
        string="Montant cible du contrat", currency_field='company_currency')
    egp_framework_target_event_count = fields.Integer(string="Nombre d'événements cible")
    egp_framework_event_count = fields.Integer(
        string="Événements réalisés", compute='_compute_egp_framework_totals')
    egp_framework_signed_amount = fields.Monetary(
        string="CA cumulé des filles", currency_field='company_currency',
        compute='_compute_egp_framework_totals')

    # ------------------------------------------------------------------
    # Suivi administratif ADV — §7.11.1
    # ------------------------------------------------------------------
    egp_admin_status_id = fields.Many2one(
        'egp.admin.status', string="Statut administratif", ondelete='restrict', tracking=True)
    egp_admin_complete = fields.Boolean(string="Dossier administratif complet", tracking=True)
    egp_admin_complete_date = fields.Date(string="Date de complétude administrative")
    egp_admin_closure_date = fields.Date(string="Date de clôture administrative")
    egp_adv_notes = fields.Html(string="Notes ADV")

    # ==================================================================
    # CALCULS
    # ==================================================================
    @api.depends(
        'type', 'partner_id', 'contact_name', 'partner_name', 'email_from', 'phone',
        'egp_event_type_id', 'egp_participant_count', 'egp_event_period_note',
        'egp_event_start', 'egp_need_description', 'egp_temperature_id',
        'partner_id.commercial_partner_id.egp_structure_type_id',
        'partner_id.commercial_partner_id.industry_id',
    )
    def _compute_egp_qualification(self):
        for lead in self:
            if lead.type == 'opportunity':
                lead.egp_qualification_state = 'converted'
                lead.egp_missing_qualification = False
                continue
            missing = lead._egp_get_missing_qualification()
            lead.egp_qualification_state = 'incomplete' if missing else 'ready'
            lead.egp_missing_qualification = "\n".join(f"• {label}" for label in missing) or False

    def _egp_get_missing_qualification(self):
        """EGP-RG-020 — Critères obligatoires avant conversion (§6.4)."""
        self.ensure_one()
        organisation = self.partner_id.commercial_partner_id
        missing = []
        if not organisation and not self.partner_name:
            missing.append(_("Organisation identifiée"))
        if not self.partner_id and not self.contact_name:
            missing.append(_("Contact principal ou nom d'interlocuteur"))
        if not self.email_from and not self.phone:
            missing.append(_("Au moins un téléphone ou un e-mail"))
        if organisation and not organisation.egp_structure_type_id:
            missing.append(_("Type de structure de l'organisation"))
        if organisation and not organisation.industry_id:
            missing.append(_("Secteur d'activité de l'organisation"))
        if not self.egp_event_type_id:
            missing.append(_("Type d'événement"))
        if self.egp_participant_count <= 0:
            missing.append(_("Nombre de personnes"))
        if not self.egp_event_start and not self.egp_event_period_note:
            missing.append(_("Date, période ou horizon de l'événement"))
        if not self.egp_need_description:
            missing.append(_("Description du besoin"))
        if not self.egp_temperature_id:
            missing.append(_("Température"))
        return missing

    @api.depends('egp_risk_notes')
    def _compute_egp_is_at_risk(self):
        for lead in self:
            lead.egp_is_at_risk = bool(lead.egp_risk_notes)

    @api.depends('stage_id.egp_code')
    def _compute_egp_is_deposit_pending(self):
        for lead in self:
            lead.egp_is_deposit_pending = lead.stage_id.egp_code == 'OPP_WON'

    @api.depends('name', 'partner_id.name')
    def _compute_egp_event_calendar_title(self):
        for lead in self:
            lead.egp_event_calendar_title = (
                f"{lead.name} - {lead.partner_id.name}" if lead.partner_id else lead.name
            )

    @api.depends('egp_event_start', 'egp_event_end', 'egp_setup_start', 'egp_teardown_end',
                 'egp_setup_required', 'egp_teardown_required')
    def _compute_egp_occupancy(self):
        for lead in self:
            start = lead.egp_setup_start if lead.egp_setup_required and lead.egp_setup_start else lead.egp_event_start
            end = lead.egp_teardown_end if lead.egp_teardown_required and lead.egp_teardown_end else lead.egp_event_end
            lead.egp_occupancy_start = start
            lead.egp_occupancy_end = end
            if start and end and end > start:
                lead.egp_sold_day_count = (end - start).total_seconds() / 86400.0
            else:
                lead.egp_sold_day_count = 0.0

    @api.depends('egp_framework_child_ids.active', 'egp_framework_child_ids.expected_revenue',
                 'egp_framework_child_ids.stage_id.is_won')
    def _compute_egp_framework_totals(self):
        for lead in self:
            children = lead.egp_framework_child_ids.filtered('active')
            won_children = children.filtered(lambda child: child.stage_id.is_won)
            lead.egp_framework_event_count = len(children)
            lead.egp_framework_signed_amount = sum(won_children.mapped('expected_revenue'))

    def _compute_egp_duplicate_need_ids(self):
        """§6.7 — Autre dossier actif portant le même besoin sur la même organisation."""
        for lead in self:
            duplicates = lead._egp_find_duplicate_needs()
            lead.egp_duplicate_need_ids = duplicates
            lead.egp_duplicate_need_count = len(duplicates)

    def _egp_find_duplicate_needs(self):
        self.ensure_one()
        organisation = self.partner_id.commercial_partner_id
        if not organisation or not self.egp_event_type_id:
            return self.browse()
        domain = [
            ('id', '!=', self.id or 0),
            ('active', '=', True),
            ('won_status', '!=', 'lost'),
            ('partner_id.commercial_partner_id', '=', organisation.id),
            ('egp_event_type_id', '=', self.egp_event_type_id.id),
        ]
        if self.egp_event_start and self.egp_event_end:
            domain += [
                ('egp_event_start', '<', self.egp_event_end),
                ('egp_event_end', '>', self.egp_event_start),
            ]
        elif self.egp_event_start:
            domain.append(('egp_event_start', '=', self.egp_event_start))
        return self.sudo().search(domain)

    # ==================================================================
    # CONTRAINTES
    # ==================================================================
    @api.constrains('egp_event_start', 'egp_event_end', 'egp_setup_start', 'egp_teardown_end')
    def _check_egp_event_dates(self):
        """EGP-RG-030 — Cohérence des dates d'événement, de montage et de démontage."""
        for lead in self:
            if lead.egp_event_start and lead.egp_event_end and lead.egp_event_end <= lead.egp_event_start:
                raise ValidationError(_("La fin de l'événement doit être postérieure à son début."))
            if lead.egp_setup_start and lead.egp_event_start and lead.egp_setup_start > lead.egp_event_start:
                raise ValidationError(_("Le début du montage doit précéder le début de l'événement."))
            if lead.egp_teardown_end and lead.egp_event_end and lead.egp_teardown_end < lead.egp_event_end:
                raise ValidationError(_("La fin du démontage doit suivre la fin de l'événement."))

    @api.constrains('type', 'source_id')
    def _check_egp_lead_source(self):
        """EGP-RG-001 — Une piste ne porte que des sources de prospection sortante."""
        allowed_ids = self._egp_get_outbound_source_ids()
        if not allowed_ids:
            return
        for lead in self.filtered(lambda record: record.type == 'lead' and record.source_id):
            if lead.source_id.id not in allowed_ids:
                raise ValidationError(_(
                    "La source « %(source)s » correspond à une demande entrante : "
                    "créez directement une opportunité plutôt qu'une piste.",
                    source=lead.source_id.name,
                ))

    @api.constrains('egp_opportunity_type_id', 'egp_framework_parent_id', 'partner_id')
    def _check_egp_framework_consistency(self):
        """EGP-RG-035 et EGP-RG-036 — Cohérence mère/filles du contrat cadre."""
        for lead in self:
            parent = lead.egp_framework_parent_id
            if not parent:
                continue
            if parent.egp_opportunity_type_id.code != 'FRAMEWORK':
                raise ValidationError(_("L'opportunité mère doit être de type « Contrat cadre »."))
            if lead.egp_opportunity_type_id.code == 'FRAMEWORK':
                raise ValidationError(_("Un contrat cadre ne peut pas être rattaché à un autre contrat cadre."))
            if (lead.partner_id.commercial_partner_id
                    and parent.partner_id.commercial_partner_id
                    and lead.partner_id.commercial_partner_id != parent.partner_id.commercial_partner_id):
                raise ValidationError(_(
                    "Une opportunité fille doit porter la même entité commerciale que son contrat cadre."))

    @api.constrains('egp_duplicate_override', 'egp_duplicate_override_reason')
    def _check_egp_duplicate_override(self):
        for lead in self.filtered('egp_duplicate_override'):
            if not lead.egp_duplicate_override_reason:
                raise ValidationError(_("Une dérogation au contrôle de doublon exige une justification."))

    @api.constrains('egp_end_customer_id', 'egp_end_customer_contact_id')
    def _check_egp_end_customer_contact(self):
        for lead in self.filtered('egp_end_customer_contact_id'):
            contact = lead.egp_end_customer_contact_id
            if lead.egp_end_customer_id and contact.commercial_partner_id != lead.egp_end_customer_id:
                raise ValidationError(_("Le contact du client final doit être rattaché au client final."))

    # ==================================================================
    # SURCHARGES ORM
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        self._egp_check_creation_allowed()
        for vals in vals_list:
            self._egp_prepare_creation_values(vals)
        leads = super().create(vals_list)
        leads._egp_check_duplicate_need()
        leads._egp_schedule_first_call()
        return leads

    @api.model
    def _egp_check_creation_allowed(self):
        """§11.6 — L'ADV ne crée pas de dossier commercial."""
        if self.env.su or self.env.context.get('egp_internal_write'):
            return
        user = self.env.user
        if user.has_group('egp_crm.group_egp_adv') and not (
                user.has_group('egp_crm.group_egp_sales_manager')
                or user.has_group('egp_crm.group_egp_salesperson')
                or user.has_group('base.group_system')):
            raise UserError(_("Le rôle ADV ne peut pas créer de piste ni d'opportunité."))

    def _egp_prepare_creation_values(self, vals):
        """EGP-AUTO-LEAD-001 — Origine, prospecteur et équipe positionnés à la création."""
        lead_type = vals.get('type') or 'opportunity'
        if not vals.get('egp_creation_mode'):
            vals['egp_creation_mode'] = 'outbound' if lead_type == 'lead' else 'inbound_direct'
        if lead_type == 'lead':
            if not vals.get('egp_prospector_id'):
                vals['egp_prospector_id'] = vals.get('user_id') or self.env.user.id
            if not vals.get('team_id'):
                team = self.env.ref('egp_crm.crm_team_egp_outbound', raise_if_not_found=False)
                if team:
                    vals['team_id'] = team.id

    def write(self, vals):
        self._egp_check_field_access(vals)
        if 'stage_id' in vals:
            self._egp_check_stage_transition(self.env['crm.stage'].browse(vals['stage_id']))
        res = super().write(vals)
        if 'team_id' in vals and 'stage_id' not in vals:
            self._egp_realign_stage_with_team()
        if 'stage_id' in vals:
            self._egp_track_qualification_date()
        if any(vals.get(signal) for signal in self._egp_strategic_signal_fields()):
            self._egp_notify_strategic_signals(vals)
        if {'egp_event_type_id', 'egp_event_start', 'egp_event_end', 'partner_id'} & set(vals):
            self._egp_check_duplicate_need()
        return res

    def _egp_realign_stage_with_team(self):
        """§3.5 — Filet de sécurité après un changement d'équipe.

        Le natif ne recalcule `stage_id` que via la dépendance `@api.depends`
        de `_compute_stage_id` ; l'assistant de conversion enchaîne plusieurs
        écritures de `team_id` (la sienne, puis celle de `_handle_salesmen_
        assignment`) et certains chemins (fusion de pistes en doublon,
        réaffectation manuelle en masse) peuvent laisser une étape qui
        n'appartient plus à l'équipe. On réaligne donc explicitement ici,
        plutôt que de dépendre d'un recalcul natif difficile à garantir sur
        tous les appelants.

        Le seul changement de `type` (avant même que `team_id` soit repositionné
        sur l'équipe EGP) suffit à faire retomber `_compute_stage_id` natif sur
        une étape générique sans équipe (`team_ids` vide, ex. « Nouveau »). Le
        garde natif (`lead.stage_id.team_ids and ...`) considère alors la piste
        comme toujours valide puisqu'une étape sans équipe ne contredit jamais
        `team_id` : on ne doit donc pas reprendre cette condition ici, sous
        peine de rester bloqué sur cette étape générique malgré une équipe EGP
        déjà positionnée.
        """
        for lead in self:
            if lead.team_id and lead.team_id not in lead.stage_id.team_ids:
                stage = lead._stage_find(domain=[('fold', '=', False)])
                if stage:
                    lead.stage_id = stage.id

    def unlink(self):
        """§11.11 — La suppression est refusée aux rôles métier, manager compris."""
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "La suppression d'une piste ou d'une opportunité est interdite. "
                "Utilisez la perte avec motif, ou l'archivage pour les erreurs et doublons."))
        return super().unlink()

    # ==================================================================
    # SÉCURITÉ APPLICATIVE — §11.9
    # ==================================================================
    def _egp_check_field_access(self, vals):
        if self.env.su or self.env.context.get('egp_internal_write'):
            return
        if self.env.user.has_group('base.group_system'):
            return
        user = self.env.user
        is_manager = user.has_group('egp_crm.group_egp_sales_manager')
        if not is_manager and user.has_group('egp_crm.group_egp_adv'):
            forbidden = set(vals) - ADV_ALLOWED_FIELDS
            if forbidden:
                raise UserError(_(
                    "Le rôle ADV ne peut modifier que les informations administratives. "
                    "Champs refusés : %(fields)s",
                    fields=", ".join(sorted(forbidden)),
                ))
            return
        if not is_manager:
            forbidden = RESTRICTED_FIELDS & set(vals)
            if forbidden:
                raise UserError(_(
                    "Seule la Responsable commerciale peut modifier : %(fields)s",
                    fields=", ".join(sorted(forbidden)),
                ))

    # ==================================================================
    # QUALIFICATION, ÉTAPES ET CONVERSION
    # ==================================================================
    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """§3.5 — N'affiche que les étapes de l'équipe active dans le Kanban.

        Le natif ajoute toujours les étapes sans équipe (``team_ids = False``,
        ex. les étapes de démonstration Odoo) en plus de celles de l'équipe
        courante. EGP rattache systématiquement ses étapes à une équipe : ce
        repli natif ne doit donc pas mélanger les pipelines Piste/Opportunité
        avec des étapes génériques qui n'appartiennent à aucun des deux.
        """
        team_id = self.env.context.get('default_team_id')
        if not team_id:
            return super()._read_group_stage_ids(stages, domain)
        search_domain = ['|', ('id', 'in', stages.ids), ('team_ids', 'in', team_id)]
        stage_ids = stages.sudo()._search(search_domain, order=stages._order)
        return stages.browse(stage_ids)

    def _stage_find(self, team_id=False, domain=None, order='sequence, id', limit=1):
        """§3.5 — Même repli que `_read_group_stage_ids` (EGP-DEC-050 bis).

        Le natif recherche `['|', ('team_ids', '=', False), ('team_ids', 'in', ...)]`
        et retourne la première étape par séquence : comme les étapes globales
        Odoo (« Nouveau », séquence 1) ont une séquence plus basse que nos
        étapes `OPP_*`/`LEAD_*`, une piste convertie ou une opportunité créée
        se retrouvait affectée à l'étape native au lieu de `OPP_NEW`. On
        restreint donc strictement aux étapes de l'équipe quand elle est
        connue, avec repli natif uniquement si aucune étape d'équipe n'existe.
        """
        team_ids = set()
        if team_id:
            team_ids.add(team_id)
        for lead in self:
            if lead.team_id:
                team_ids.add(lead.team_id.id)
        if not team_ids:
            return super()._stage_find(team_id=team_id, domain=domain, order=order, limit=limit)
        search_domain = [('team_ids', 'in', list(team_ids))]
        if domain:
            search_domain += list(domain)
        stage = self.env['crm.stage'].search(search_domain, order=order, limit=limit)
        return stage or super()._stage_find(team_id=team_id, domain=domain, order=order, limit=limit)

    def _egp_track_qualification_date(self):
        """EGP-FLD-LEAD-142 — Date du premier passage à l'étape « Qualifiée »."""
        for lead in self:
            if lead.stage_id.egp_code == 'LEAD_QUALIFIED' and not lead.egp_qualified_date:
                lead.egp_qualified_date = fields.Datetime.now()

    def _egp_check_stage_transition(self, stage):
        """EGP-DEC-026/027 — Contrôles bloquants des transitions d'étape (§7.12)."""
        if self.env.su or not stage:
            return
        for lead in self:
            errors = lead._egp_stage_transition_errors(stage)
            if errors:
                raise UserError(_(
                    "Passage à l'étape « %(stage)s » impossible pour « %(lead)s » :\n%(errors)s",
                    stage=stage.name,
                    lead=lead.display_name,
                    errors="\n".join(f"• {error}" for error in errors),
                ))

    def _egp_stage_transition_errors(self, stage):
        """Point d'extension : les addons Ventes/Projet ajoutent leurs contrôles."""
        self.ensure_one()
        errors = []
        code = stage.egp_code
        if code == 'LEAD_FOLLOW_UP' and not (self.egp_follow_up_date or self.activity_ids):
            errors.append(_("Une date de relance ou une activité planifiée est requise."))
        if code == 'LEAD_QUALIFIED':
            errors += self._egp_get_missing_qualification()
        if code in ('OPP_QUALIFIED', 'OPP_PROPOSAL'):
            if not self.partner_id:
                errors.append(_("Le client doit être identifié."))
            if not self.egp_event_type_id:
                errors.append(_("Le type d'événement est obligatoire."))
            if not self.egp_event_start and not self.egp_event_period_note:
                errors.append(_("Une date ou une période d'événement est obligatoire."))
            if self.egp_participant_count <= 0:
                errors.append(_("Le nombre de personnes est obligatoire."))
            if not self.egp_need_description:
                errors.append(_("Le besoin doit être qualifié."))
        if code in ('OPP_WON', 'OPP_DEPOSIT_PAID', 'OPP_EVENT_DONE', 'OPP_CLOSED'):
            if not self.egp_event_start or not self.egp_event_end:
                errors.append(_("Les dates précises de l'événement sont obligatoires avant confirmation."))
        if code == 'OPP_CLOSED':
            if not self.egp_admin_complete:
                errors.append(_("Le dossier administratif doit être complet."))
            if not self.egp_admin_closure_date:
                errors.append(_("La date de clôture administrative est obligatoire."))
        return errors

    def _egp_check_convertible(self):
        """EGP-RG-020 — Contrôle serveur bloquant appliqué aussi aux imports et à l'API."""
        for lead in self.filtered(lambda record: record.type == 'lead'):
            missing = lead._egp_get_missing_qualification()
            if missing:
                raise UserError(_(
                    "La piste « %(lead)s » ne peut pas être convertie. Critères manquants :\n%(missing)s",
                    lead=lead.display_name,
                    missing="\n".join(f"• {label}" for label in missing),
                ))
            if lead.egp_duplicate_need_count and not lead.egp_duplicate_override:
                raise UserError(_(
                    "Un dossier actif porte déjà ce besoin pour cette organisation. "
                    "Rattachez-vous au dossier existant ou demandez une dérogation à la "
                    "Responsable commerciale."))

    def convert_opportunity(self, partner, user_ids=False, team_id=False):
        """EGP-RG-021 — La conversion native conserve le même enregistrement."""
        self._egp_check_convertible()
        if not team_id:
            team = self.env.ref('egp_crm.crm_team_egp_commercial', raise_if_not_found=False)
            team_id = team.id if team else False
        # La conversion native réaffecte type, équipe et responsable : opération
        # légitime que le garde-fou de champs restreints ne doit pas bloquer.
        leads = self.with_context(egp_internal_write=True)
        res = super(CrmLead, leads).convert_opportunity(partner, user_ids=user_ids, team_id=team_id)
        opportunity_type = self.env['egp.opportunity.type']._get_by_code('ONE_OFF_EVENT')
        for lead in leads:
            if not lead.egp_opportunity_type_id and opportunity_type:
                lead.egp_opportunity_type_id = opportunity_type
        leads._egp_schedule_commercial_qualification()
        return res

    # ==================================================================
    # DOUBLONS DE BESOIN — §6.7
    # ==================================================================
    def _egp_check_duplicate_need(self):
        """EGP-DEC-013 — Blocage sur organisation + type d'événement + période."""
        if self.env.su:
            return
        for lead in self:
            if lead.egp_duplicate_override or not lead.active:
                continue
            duplicates = lead._egp_find_duplicate_needs()
            if duplicates:
                raise UserError(_(
                    "Un dossier actif porte déjà ce besoin : %(records)s.\n"
                    "Poursuivez sur le dossier existant ou demandez une dérogation à la "
                    "Responsable commerciale.",
                    records=", ".join(duplicates.mapped('display_name')),
                ))

    def action_egp_view_duplicate_needs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Dossiers en doublon potentiel"),
            'res_model': 'crm.lead',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.egp_duplicate_need_ids.ids)],
        }

    # ==================================================================
    # CONTRAT CADRE — §7.8
    # ==================================================================
    def action_egp_create_framework_event(self):
        """EGP-RG-037 — Créer une opportunité fille en héritant des seules données générales."""
        self.ensure_one()
        if self.egp_opportunity_type_id.code != 'FRAMEWORK':
            raise UserError(_("Cette action n'est disponible que sur une opportunité de type « Contrat cadre »."))
        child_type = self.env['egp.opportunity.type']._get_by_code('FRAMEWORK_EVENT')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Nouvel événement sous contrat cadre"),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'context': {
                'default_type': 'opportunity',
                'default_egp_framework_parent_id': self.id,
                'default_egp_opportunity_type_id': child_type.id if child_type else False,
                'default_partner_id': self.partner_id.id,
                'default_egp_secondary_contact_ids': [(6, 0, self.egp_secondary_contact_ids.ids)],
                'default_egp_end_customer_id': self.egp_end_customer_id.id,
                'default_egp_intermediation_type': self.egp_intermediation_type,
                'default_user_id': self.user_id.id,
                'default_team_id': self.team_id.id,
                'default_company_id': self.company_id.id,
                'default_source_id': self.source_id.id,
                'default_medium_id': self.medium_id.id,
                'default_egp_market_segment_id': self.egp_market_segment_id.id,
                'default_egp_is_grand_account': self.egp_is_grand_account,
                'default_egp_is_tender': self.egp_is_tender,
                'default_egp_is_multisite': self.egp_is_multisite,
                'default_egp_is_recurring_event': self.egp_is_recurring_event,
            },
        }

    def action_egp_view_framework_children(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("Événements sous contrat cadre"),
            'res_model': 'crm.lead',
            'view_mode': 'list,kanban,form',
            'domain': [('egp_framework_parent_id', '=', self.id)],
            'context': {'default_egp_framework_parent_id': self.id, 'default_type': 'opportunity'},
        }

    # ==================================================================
    # ACTIVITÉS ET NOTIFICATIONS
    # ==================================================================
    @api.model
    def _egp_strategic_signal_fields(self):
        return [
            'egp_is_grand_account', 'egp_is_framework_potential', 'egp_is_tender',
            'egp_is_multisite', 'egp_is_recurring_event', 'egp_has_multiple_needs',
        ]

    def _egp_notify_strategic_signals(self, vals):
        """EGP-AUTO-LEAD-007 — Une seule notification par activation d'un signal."""
        managers = self.env.ref('egp_crm.group_egp_sales_manager', raise_if_not_found=False)
        if not managers or not managers.user_ids:
            return
        activated = [
            self._fields[fname].get_description(self.env)['string']
            for fname in self._egp_strategic_signal_fields() if vals.get(fname)
        ]
        if not activated:
            return
        body = _("Signal stratégique activé : %(signals)s", signals=", ".join(activated))
        for lead in self:
            lead.message_post(
                body=body,
                partner_ids=managers.user_ids.partner_id.ids,
            )

    def _egp_schedule_first_call(self):
        """EGP-AUTO-LEAD-002 — Activité « Premier appel » créée une seule fois."""
        for lead in self.filtered(lambda record: record.type == 'lead' and not record.activity_ids):
            delay = lead.company_id.egp_first_call_delay_days or self.env.company.egp_first_call_delay_days
            lead.activity_schedule(
                'mail.mail_activity_data_call',
                date_deadline=fields.Date.context_today(lead) + relativedelta(days=delay or 1),
                summary=_("Premier appel de prospection"),
                user_id=(lead.egp_prospector_id or lead.user_id or self.env.user).id,
            )

    def _egp_schedule_commercial_qualification(self):
        """EGP-AUTO-LEAD-011 — Activité initiale du Commercial après attribution."""
        summary = _("Qualification commerciale")
        for lead in self:
            if lead.activity_ids.filtered(lambda activity: activity.summary == summary):
                continue
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(lead) + relativedelta(days=2),
                summary=summary,
                user_id=(lead.user_id or self.env.user).id,
            )

    # ==================================================================
    # TÂCHES PLANIFIÉES — EGP-DEC-044
    # ==================================================================
    @api.model
    def _cron_egp_update_lead_inactivity(self, batch_size=5000):
        """EGP-AUTO-LEAD-005/006 — Inactivité des pistes, rafraîchie par lot."""
        leads = self.search([('type', '=', 'lead'), ('active', '=', True)], limit=batch_size)
        today = fields.Date.context_today(self)
        for lead in leads:
            reference = lead.date_last_stage_update or lead.create_date
            inactive_days = (today - reference.date()).days if reference else 0
            threshold = lead.company_id.egp_lead_inactivity_days or self.env.company.egp_lead_inactivity_days
            is_inactive = bool(threshold) and inactive_days >= threshold and not lead.activity_ids
            if lead.egp_inactive_days != inactive_days or lead.egp_is_inactive != is_inactive:
                lead.write({'egp_inactive_days': inactive_days, 'egp_is_inactive': is_inactive})
        return True

    @api.model
    def _cron_egp_missing_activity_alerts(self, batch_size=5000):
        """EGP-FR-022 — Les étapes gagnées sont exclues de l'obligation d'activité."""
        leads = self.search([
            ('type', '=', 'opportunity'),
            ('active', '=', True),
            ('won_status', '=', 'pending'),
            ('stage_id.is_won', '=', False),
            ('activity_ids', '=', False),
        ], limit=batch_size)
        summary = _("Planifier la prochaine action commerciale")
        for lead in leads:
            lead.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=fields.Date.context_today(lead),
                summary=summary,
                user_id=(lead.user_id or self.env.user).id,
            )
        return True

    # ==================================================================
    # OUTILS
    # ==================================================================
    @api.model
    def _egp_get_outbound_source_ids(self):
        source_ids = []
        for xml_id in OUTBOUND_SOURCE_XMLIDS:
            source = self.env.ref(xml_id, raise_if_not_found=False)
            if source:
                source_ids.append(source.id)
        return source_ids

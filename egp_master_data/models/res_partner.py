from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

# EGP-FLD-CON-114 / EGP-RG-006 : champs essentiels servant au taux de complétude.
COMPANY_COMPLETENESS_FIELDS = [
    'name', 'egp_structure_type_id', 'industry_id', 'egp_activity_id',
    'egp_primary_relation_id', 'egp_client_status_id', 'user_id',
    'street', 'zip', 'city', 'country_id', 'phone', 'email',
    'egp_main_contact_id',
]
CONTACT_COMPLETENESS_FIELDS = [
    'name', 'parent_id', 'function', 'egp_department_id', 'email', 'phone', 'lang',
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Champs complémentaires Organisation — spécification §5.3.1
    # ------------------------------------------------------------------
    egp_trade_name = fields.Char(string="Nom commercial", index='trigram')
    egp_structure_type_id = fields.Many2one(
        'egp.structure.type', string="Type de structure",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_activity_id = fields.Many2one(
        'egp.business.activity', string="Activité principale",
        index='btree_not_null', ondelete='restrict', tracking=True,
        domain="[('industry_id', '=?', industry_id)]")
    egp_company_size_id = fields.Many2one(
        'egp.company.size', string="Taille d'entreprise", ondelete='restrict')
    egp_primary_relation_id = fields.Many2one(
        'egp.partner.relation', string="Relation principale avec EGP",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_relation_ids = fields.Many2many(
        'egp.partner.relation', 'egp_partner_relation_rel', 'partner_id', 'relation_id',
        string="Relations complémentaires")
    egp_client_status_id = fields.Many2one(
        'egp.client.status', string="Statut de cycle client",
        index='btree_not_null', ondelete='restrict', tracking=True)
    egp_is_grand_account = fields.Boolean(string="Grand compte", tracking=True)
    egp_is_regular_customer = fields.Boolean(
        string="Client régulier", readonly=True, copy=False,
        help="Recalculé périodiquement par tâche planifiée (EGP-RG-018A) : "
             "cet indicateur dépend d'une fenêtre glissante et non d'une simple dépendance de champ.")
    egp_has_active_framework = fields.Boolean(
        string="Contrat cadre actif", compute='_compute_egp_has_active_framework')
    egp_main_contact_id = fields.Many2one(
        'res.partner', string="Contact principal", ondelete='set null',
        domain="[('parent_id', '=', id), ('is_company', '=', False)]")
    egp_region_id = fields.Many2one(
        'egp.administrative.region', string="Région administrative",
        compute='_compute_egp_region_id', store=True, readonly=False,
        index='btree_not_null', ondelete='set null')
    egp_completeness_rate = fields.Float(
        string="Taux de complétude", compute='_compute_egp_completeness',
        aggregator='avg', digits=(5, 2))
    egp_is_incomplete = fields.Boolean(
        string="Fiche à compléter", compute='_compute_egp_completeness')
    egp_missing_data = fields.Char(
        string="Informations manquantes", compute='_compute_egp_completeness')

    # ------------------------------------------------------------------
    # Champs complémentaires Contact personne — spécification §5.3.2
    # ------------------------------------------------------------------
    egp_mobile = fields.Char(string="Mobile")
    egp_department_id = fields.Many2one(
        'egp.contact.department', string="Service / département", ondelete='restrict')
    egp_preferred_channel_id = fields.Many2one(
        'egp.contact.channel', string="Canal de contact préféré", ondelete='restrict')
    egp_contact_role_ids = fields.Many2many(
        'res.partner.category', 'egp_partner_contact_role_rel', 'partner_id', 'category_id',
        string="Rôles de contact")
    egp_departure_date = fields.Date(string="Date de départ")
    egp_archive_reason = fields.Char(string="Motif d'archivage", copy=False)

    # ------------------------------------------------------------------
    # Calculs
    # ------------------------------------------------------------------
    @api.depends('state_id.egp_region_id')
    def _compute_egp_region_id(self):
        for partner in self:
            partner.egp_region_id = partner.state_id.egp_region_id

    def _compute_egp_has_active_framework(self):
        """EGP-FLD-CON-111 : présence d'une opportunité mère « Contrat cadre » active."""
        self.egp_has_active_framework = False
        commercial_partners = self.mapped('commercial_partner_id')
        if not commercial_partners:
            return
        grouped = self.env['crm.lead'].sudo()._read_group(
            [
                ('type', '=', 'opportunity'),
                ('active', '=', True),
                ('partner_id.commercial_partner_id', 'in', commercial_partners.ids),
                ('egp_opportunity_type_id.code', '=', 'FRAMEWORK'),
            ],
            groupby=['partner_id'],
            aggregates=['__count'],
        )
        partner_ids_with_framework = {
            partner.commercial_partner_id.id for partner, __ in grouped
        }
        for partner in self:
            partner.egp_has_active_framework = (
                partner.commercial_partner_id.id in partner_ids_with_framework
            )

    @api.depends_context('lang')
    @api.depends(lambda self: tuple(set(COMPANY_COMPLETENESS_FIELDS + CONTACT_COMPLETENESS_FIELDS)))
    def _compute_egp_completeness(self):
        """EGP-RG-006 : indicateur de qualité, volontairement non stocké (§5.3.1)."""
        for partner in self:
            fnames = COMPANY_COMPLETENESS_FIELDS if partner.is_company else CONTACT_COMPLETENESS_FIELDS
            missing = [fname for fname in fnames if not partner[fname]]
            partner.egp_completeness_rate = 100.0 * (len(fnames) - len(missing)) / len(fnames)
            partner.egp_is_incomplete = bool(missing)
            partner.egp_missing_data = ", ".join(
                self._fields[fname].get_description(self.env)['string'] for fname in missing
            )

    # ------------------------------------------------------------------
    # Contraintes de cohérence — spécification §5.4
    # ------------------------------------------------------------------
    @api.constrains('industry_id', 'egp_activity_id')
    def _check_egp_activity_industry(self):
        """EGP-RG-012 — L'activité doit appartenir au secteur de l'organisation."""
        for partner in self:
            activity = partner.egp_activity_id
            if activity and activity.industry_id != partner.industry_id:
                raise ValidationError(_(
                    "L'activité « %(activity)s » appartient au secteur « %(activity_industry)s » "
                    "et ne peut pas être utilisée avec le secteur « %(industry)s ».",
                    activity=activity.name,
                    activity_industry=activity.industry_id.name,
                    industry=partner.industry_id.name or _("non renseigné"),
                ))

    @api.constrains('egp_main_contact_id')
    def _check_egp_main_contact(self):
        """EGP-RG-013 — Le contact principal est un enfant actif de l'organisation."""
        for partner in self:
            contact = partner.egp_main_contact_id
            if contact and (contact.parent_id != partner or not contact.active):
                raise ValidationError(_(
                    "Le contact principal doit être un contact actif rattaché à « %(partner)s ».",
                    partner=partner.display_name,
                ))

    @api.onchange('industry_id')
    def _onchange_industry_id(self):
        """EGP-RG-012 — Un changement de secteur efface une activité devenue incompatible."""
        for partner in self:
            if partner.egp_activity_id and partner.egp_activity_id.industry_id != partner.industry_id:
                partner.egp_activity_id = False

    # ------------------------------------------------------------------
    # Gouvernance : archivage et suppression — spécification §5.4 / §11.11
    # ------------------------------------------------------------------
    def write(self, vals):
        if vals.get('active') is False:
            self._check_egp_archive_allowed(vals)
        return super().write(vals)

    def _check_egp_archive_allowed(self, vals):
        """EGP-FLD-CON-127 — Motif obligatoire pour archiver une fiche déjà utilisée."""
        if self.env.su:
            return
        for partner in self:
            if not partner._egp_has_business_history():
                continue
            if not (vals.get('egp_archive_reason') or partner.egp_archive_reason):
                raise UserError(_(
                    "La fiche « %(partner)s » possède un historique commercial : "
                    "un motif d'archivage est obligatoire.",
                    partner=partner.display_name,
                ))

    def _egp_has_business_history(self):
        self.ensure_one()
        return bool(self.env['crm.lead'].sudo().with_context(active_test=False).search_count(
            ['|', ('partner_id', '=', self.id), ('partner_id', 'child_of', self.id)], limit=1
        ))

    def unlink(self):
        """EGP-RG-019 — La suppression reste réservée à l'Administrateur Odoo."""
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "La suppression d'un contact est interdite : archivez la fiche ou "
                "fusionnez les doublons afin de préserver l'historique."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Normalisation téléphonique
    # ------------------------------------------------------------------
    @api.model
    def _phone_get_number_fields(self):
        fnames = super()._phone_get_number_fields()
        if 'egp_mobile' in self._fields and 'egp_mobile' not in fnames:
            fnames = ['egp_mobile'] + fnames
        return fnames

    # ------------------------------------------------------------------
    # Actions et automatisations
    # ------------------------------------------------------------------
    def action_egp_create_reactivation_lead(self):
        """EGP-RG-025 — Créer une piste de réactivation depuis une fiche Contact."""
        self.ensure_one()
        contact = self if not self.is_company else (self.egp_main_contact_id or self)
        source = self.env.ref('egp_master_data.utm_source_egp_reactivation', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Nouvelle piste de réactivation"),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_type': 'lead',
                'default_partner_id': contact.id,
                'default_email_from': contact.email or self.email,
                'default_phone': contact.phone or self.phone,
                'default_source_id': source.id if source else False,
                'default_user_id': self.env.user.id,
                'default_egp_prospector_id': self.env.user.id,
                'default_egp_creation_mode': 'outbound',
            },
        }

    @api.model
    def _cron_egp_update_regular_customers(self, batch_size=2000):
        """EGP-RG-018A — Recalcul par lot du booléen « Client régulier ».

        Le champ dépend d'une fenêtre glissante : il ne peut pas être un champ
        calculé stocké (EGP-DEC-044).
        """
        Lead = self.env['crm.lead'].sudo()
        for company in self.env['res.company'].search([]):
            threshold = company.egp_regular_customer_min_events
            window = company.egp_regular_customer_window_months
            if not threshold or not window:
                continue
            start_date = fields.Datetime.now() - relativedelta(months=window)
            grouped = Lead._read_group(
                [
                    ('type', '=', 'opportunity'),
                    ('company_id', '=', company.id),
                    ('stage_id.is_won', '=', True),
                    ('date_closed', '>=', start_date),
                ],
                groupby=['partner_id'],
                aggregates=['__count'],
            )
            regular_ids = {
                partner.commercial_partner_id.id
                for partner, count in grouped
                if partner and count >= threshold
            }
            candidates = self.sudo().with_context(active_test=False).search([
                '|', ('egp_is_regular_customer', '=', True), ('id', 'in', list(regular_ids)),
            ], limit=batch_size)
            (candidates.filtered(lambda p: p.id in regular_ids)).egp_is_regular_customer = True
            (candidates.filtered(lambda p: p.id not in regular_ids)).egp_is_regular_customer = False
        return True

    @api.model
    def _cron_egp_update_dormant_customers(self, batch_size=2000):
        """EGP-AUTO-CON-013 — Passage automatique au statut « Client dormant »."""
        Status = self.env['egp.client.status']
        active_status = Status._get_by_code('ACTIVE_CUSTOMER')
        dormant_status = Status._get_by_code('DORMANT_CUSTOMER')
        if not active_status or not dormant_status:
            return True
        Lead = self.env['crm.lead'].sudo()
        for company in self.env['res.company'].search([]):
            months = company.egp_dormant_customer_delay_months
            if not months:
                continue
            limit_date = fields.Datetime.now() - relativedelta(months=months)
            partners = self.sudo().search([
                ('is_company', '=', True),
                ('egp_client_status_id', '=', active_status.id),
            ], limit=batch_size)
            for partner in partners:
                recent = Lead.search_count([
                    ('partner_id', 'child_of', partner.id),
                    ('stage_id.is_won', '=', True),
                    ('date_closed', '>=', limit_date),
                ], limit=1)
                if not recent:
                    partner.egp_client_status_id = dormant_status
        return True

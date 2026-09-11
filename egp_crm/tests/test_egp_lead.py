from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'egp')
class TestEgpLead(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organisation = cls.env['res.partner'].create({
            'name': "Agence Alpha",
            'is_company': True,
            'industry_id': cls.env.ref('egp_master_data.industry_egp_events').id,
            'egp_activity_id': cls.env.ref('egp_master_data.activity_egp_event_agency').id,
            'egp_structure_type_id': cls.env.ref('egp_master_data.structure_type_company').id,
        })
        cls.contact = cls.env['res.partner'].create({
            'name': "Camille Martin",
            'parent_id': cls.organisation.id,
            'email': "camille.martin@example.com",
            'phone': "+33 1 23 45 67 89",
        })
        cls.event_type = cls.env.ref('egp_master_data.event_type_cocktail')
        cls.temperature = cls.env.ref('egp_master_data.lead_temperature_hot')

    def _create_qualified_lead(self, _user=None, **values):
        vals = {
            'name': "Cocktail annuel Alpha",
            'type': 'lead',
            'partner_id': self.contact.id,
            'source_id': self.env.ref('egp_master_data.utm_source_egp_research').id,
            'egp_event_type_id': self.event_type.id,
            'egp_participant_count': 120,
            'egp_event_period_note': "Automne",
            'egp_need_description': "<p>Cocktail de fin d'année</p>",
            'egp_temperature_id': self.temperature.id,
        }
        vals.update(values)
        CrmLead = self.env['crm.lead'].with_user(_user) if _user else self.env['crm.lead']
        return CrmLead.create(vals)

    def test_lead_creation_defaults(self):
        """EGP-TST-LEAD-001 — Type, équipe, prospecteur et origine positionnés."""
        lead = self._create_qualified_lead()
        self.assertEqual(lead.type, 'lead')
        self.assertEqual(lead.egp_creation_mode, 'outbound')
        self.assertEqual(lead.egp_prospector_id, self.env.user)
        self.assertEqual(lead.team_id, self.env.ref('egp_crm.crm_team_egp_outbound'))

    def test_first_call_activity_is_created_once(self):
        """EGP-TST-LEAD-002 — L'activité « Premier appel » n'est créée qu'une fois."""
        lead = self._create_qualified_lead()
        calls = lead.activity_ids.filtered(
            lambda activity: activity.activity_type_id == self.env.ref('mail.mail_activity_data_call'))
        self.assertEqual(len(calls), 1)

    def test_inbound_source_is_refused_on_a_lead(self):
        """EGP-TST-LEAD-004 — Une source entrante impose une opportunité directe."""
        with self.assertRaises(ValidationError):
            self._create_qualified_lead(
                source_id=self.env.ref('egp_master_data.utm_source_egp_web_form').id)

    def test_conversion_requires_complete_qualification(self):
        """EGP-TST-LEAD-006 — Conversion refusée tant qu'un critère manque."""
        lead = self._create_qualified_lead(egp_temperature_id=False)
        self.assertEqual(lead.egp_qualification_state, 'incomplete')
        with self.assertRaises(UserError):
            lead.convert_opportunity(self.contact)

    def test_conversion_keeps_the_same_record(self):
        """EGP-TST-LEAD-007/008 — Même identifiant, champs EGP et chatter conservés."""
        lead = self._create_qualified_lead()
        lead.message_post(body="Premier échange téléphonique")
        message_count = len(lead.message_ids)
        lead_id = lead.id
        self.assertEqual(lead.egp_qualification_state, 'ready')

        lead.convert_opportunity(self.contact)

        self.assertEqual(lead.id, lead_id)
        self.assertEqual(lead.type, 'opportunity')
        self.assertTrue(lead.date_conversion)
        self.assertEqual(lead.egp_prospector_id, self.env.user)
        self.assertEqual(lead.egp_event_type_id, self.event_type)
        self.assertGreaterEqual(len(lead.message_ids), message_count)
        self.assertEqual(lead.team_id, self.env.ref('egp_crm.crm_team_egp_commercial'))
        self.assertEqual(lead.egp_opportunity_type_id.code, 'ONE_OFF_EVENT')

    def test_conversion_sets_stage_to_opp_new(self):
        """§3.5 — La conversion doit affecter l'étape OPP_NEW, jamais une étape native."""
        lead = self._create_qualified_lead()
        lead.convert_opportunity(self.contact)
        self.assertEqual(lead.stage_id, self.env.ref('egp_crm.crm_stage_egp_opp_new'))
        self.assertEqual(lead.stage_id.egp_code, 'OPP_NEW')

    def test_duplicate_need_is_blocked(self):
        """EGP-TST-LEAD-013 — Même organisation, même type d'événement, période chevauchante."""
        # `_egp_check_duplicate_need` court-circuite en mode superuser (env.su) :
        # il faut un utilisateur non-admin pour exercer réellement le contrôle.
        user = self.env['res.users'].create({
            'name': "Commercial EGP",
            'login': 'egp_lead_duplicate_salesperson',
            'group_ids': [(4, self.env.ref('egp_crm.group_egp_salesperson').id)],
        })
        start = fields.Datetime.to_datetime('2026-11-20 18:00:00')
        end = fields.Datetime.to_datetime('2026-11-20 23:00:00')
        self._create_qualified_lead(egp_event_start=start, egp_event_end=end)
        with self.assertRaises(UserError):
            self._create_qualified_lead(
                name="Deuxième cocktail", egp_event_start=start, egp_event_end=end, _user=user)

    def test_duplicate_override_allows_creation(self):
        """EGP-TST-LEAD-014 — Dérogation manager avec justification obligatoire."""
        user = self.env['res.users'].create({
            'name': "Responsable commerciale",
            'login': 'egp_lead_duplicate_manager',
            'group_ids': [(4, self.env.ref('egp_crm.group_egp_sales_manager').id)],
        })
        start = fields.Datetime.to_datetime('2026-11-20 18:00:00')
        end = fields.Datetime.to_datetime('2026-11-20 23:00:00')
        self._create_qualified_lead(egp_event_start=start, egp_event_end=end)
        lead = self._create_qualified_lead(
            name="Deuxième cocktail",
            egp_event_start=start,
            egp_event_end=end,
            egp_duplicate_override=True,
            egp_duplicate_override_reason="Deux plateaux distincts confirmés par le client",
            _user=user,
        )
        self.assertTrue(lead.id)

    def test_event_dates_consistency(self):
        """EGP-RG-030 — La fin de l'événement suit son début."""
        with self.assertRaises(ValidationError):
            self._create_qualified_lead(
                egp_event_start=fields.Datetime.to_datetime('2026-11-20 18:00:00'),
                egp_event_end=fields.Datetime.to_datetime('2026-11-20 10:00:00'),
            )

    def test_occupancy_covers_setup_and_teardown(self):
        """EGP-TST-OPP-026 — L'occupation va du montage au démontage."""
        lead = self._create_qualified_lead(
            egp_event_start=fields.Datetime.to_datetime('2026-11-20 18:00:00'),
            egp_event_end=fields.Datetime.to_datetime('2026-11-20 23:00:00'),
            egp_setup_required=True,
            egp_setup_start=fields.Datetime.to_datetime('2026-11-20 08:00:00'),
            egp_teardown_required=True,
            egp_teardown_end=fields.Datetime.to_datetime('2026-11-21 02:00:00'),
        )
        self.assertEqual(lead.egp_occupancy_start, fields.Datetime.to_datetime('2026-11-20 08:00:00'))
        self.assertEqual(lead.egp_occupancy_end, fields.Datetime.to_datetime('2026-11-21 02:00:00'))
        self.assertAlmostEqual(lead.egp_sold_day_count, 0.75, places=2)

    # EGP-TST-OPP-006 (option sans échéance) est couvert dans egp_crm_rental,
    # seul addon portant les champs d'option (EGP-DEC-010A).

    def test_framework_child_must_share_the_commercial_entity(self):
        """EGP-TST-OPP-015 — Une fille d'un autre client est refusée."""
        framework = self.env['crm.lead'].create({
            'name': "Contrat cadre Alpha",
            'type': 'opportunity',
            'partner_id': self.contact.id,
            'egp_opportunity_type_id': self.env.ref('egp_master_data.opportunity_type_framework').id,
        })
        other_contact = self.env['res.partner'].create({
            'name': "Contact Beta",
            'parent_id': self.env['res.partner'].create({'name': "Beta", 'is_company': True}).id,
        })
        with self.assertRaises(ValidationError):
            self.env['crm.lead'].create({
                'name': "Événement Beta",
                'type': 'opportunity',
                'partner_id': other_contact.id,
                'egp_framework_parent_id': framework.id,
                'egp_opportunity_type_id': self.env.ref(
                    'egp_master_data.opportunity_type_framework_event').id,
            })

    def test_closing_stage_requires_administrative_completion(self):
        """EGP-TST-OPP-022 — Contrôles administratifs à la clôture."""
        opportunity = self.env['crm.lead'].create({
            'name': "Événement Alpha",
            'type': 'opportunity',
            'partner_id': self.contact.id,
            'egp_event_start': fields.Datetime.to_datetime('2026-11-20 18:00:00'),
            'egp_event_end': fields.Datetime.to_datetime('2026-11-20 23:00:00'),
        })
        user = self.env['res.users'].create({
            'name': "Commercial EGP",
            'login': 'egp_lead_salesperson',
            'group_ids': [(4, self.env.ref('egp_crm.group_egp_sales_manager').id)],
        })
        closed_stage = self.env.ref('egp_crm.crm_stage_egp_opp_closed')
        with self.assertRaises(UserError):
            opportunity.with_user(user).write({'stage_id': closed_stage.id})

    def test_lead_cannot_be_deleted(self):
        """EGP-TST-SEC-010 — Suppression interdite, y compris au manager."""
        lead = self._create_qualified_lead()
        user = self.env['res.users'].create({
            'name': "Responsable",
            'login': 'egp_lead_manager',
            'group_ids': [(4, self.env.ref('egp_crm.group_egp_sales_manager').id)],
        })
        with self.assertRaises(UserError):
            lead.with_user(user).unlink()

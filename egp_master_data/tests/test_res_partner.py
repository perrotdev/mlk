from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'egp')
class TestEgpResPartner(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.industry_events = cls.env.ref('egp_master_data.industry_egp_events')
        cls.industry_culture = cls.env.ref('egp_master_data.industry_egp_culture')
        cls.activity_event_agency = cls.env.ref('egp_master_data.activity_egp_event_agency')
        cls.company_partner = cls.env['res.partner'].create({
            'name': "Agence Alpha",
            'is_company': True,
            'industry_id': cls.industry_events.id,
            'egp_activity_id': cls.activity_event_agency.id,
        })

    def test_activity_must_match_industry(self):
        """EGP-TST-CON-003 — refus d'une activité d'un autre secteur."""
        with self.assertRaises(ValidationError):
            self.company_partner.industry_id = self.industry_culture

    def test_onchange_industry_clears_incompatible_activity(self):
        partner = self.company_partner.new({
            'name': "Agence Beta",
            'is_company': True,
            'industry_id': self.industry_events.id,
            'egp_activity_id': self.activity_event_agency.id,
        })
        partner.industry_id = self.industry_culture
        partner._onchange_industry_id()
        self.assertFalse(partner.egp_activity_id)

    def test_main_contact_must_be_a_child(self):
        """EGP-TST-CON-007 — le contact principal appartient à l'organisation."""
        other_contact = self.env['res.partner'].create({'name': "Contact externe"})
        with self.assertRaises(ValidationError):
            self.company_partner.egp_main_contact_id = other_contact

    def test_completeness_reports_missing_data(self):
        """EGP-TST-CON-015 — le taux de complétude reflète les champs essentiels."""
        self.assertTrue(self.company_partner.egp_is_incomplete)
        self.assertLess(self.company_partner.egp_completeness_rate, 100.0)
        self.assertIn("Relation principale avec EGP", self.company_partner.egp_missing_data)

    def test_archive_requires_reason_when_history_exists(self):
        """EGP-TST-CON-009 — motif obligatoire pour archiver une fiche utilisée."""
        self.env['crm.lead'].create({
            'name': "Piste Alpha",
            'type': 'lead',
            'partner_id': self.company_partner.id,
        })
        user = self.env['res.users'].create({
            'name': "Responsable",
            'login': 'egp_partner_manager',
            'group_ids': [(4, self.env.ref('sales_team.group_sale_manager').id)],
        })
        partner = self.company_partner.with_user(user)
        with self.assertRaises(UserError):
            partner.action_archive()
        partner.write({'active': False, 'egp_archive_reason': "Organisation dissoute"})
        self.assertFalse(partner.active)

    def test_unlink_is_forbidden_for_business_users(self):
        """EGP-RG-019 — la suppression reste réservée à l'Administrateur Odoo."""
        user = self.env['res.users'].create({
            'name': "Commercial",
            'login': 'egp_partner_user',
            'group_ids': [(4, self.env.ref('sales_team.group_sale_manager').id)],
        })
        with self.assertRaises(UserError):
            self.company_partner.with_user(user).unlink()

    def test_mobile_is_a_phone_field(self):
        self.assertIn('egp_mobile', self.env['res.partner']._phone_get_number_fields())

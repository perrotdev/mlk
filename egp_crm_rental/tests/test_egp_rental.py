from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'egp')
class TestEgpCrmRental(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env['planning.role'].create({
            'name': "Grande salle",
            'sync_shift_rental': True,
        })
        cls.room_a = cls.env['resource.resource'].create({
            'name': "Salle A",
            'resource_type': 'material',
        })
        cls.role.resource_ids = cls.room_a
        # EGP-DEC-010A : un espace est un produit de location de type Service.
        cls.space = cls.env['product.product'].create({
            'name': "Grande salle",
            'type': 'service',
            'rent_ok': True,
            'planning_role_id': cls.role.id,
        })
        cls.other_space = cls.env['product.product'].create({
            'name': "Salon",
            'type': 'service',
            'rent_ok': True,
        })
        cls.lead = cls.env['crm.lead'].create({
            'name': "Cocktail Alpha",
            'type': 'opportunity',
            'egp_event_start': fields.Datetime.to_datetime('2026-11-20 18:00:00'),
            'egp_event_end': fields.Datetime.to_datetime('2026-11-20 23:00:00'),
        })

    def test_main_space_must_belong_to_wanted_spaces(self):
        """EGP-TST-OPP-027 — L'espace principal appartient aux espaces envisagés."""
        self.lead.egp_space_ids = self.space
        with self.assertRaises(ValidationError):
            self.lead.egp_main_space_id = self.other_space

    def test_single_space_becomes_main_space(self):
        lead = self.lead.new({'egp_space_ids': [(6, 0, self.space.ids)]})
        lead._onchange_egp_space_ids()
        # En contexte onchange, egp_main_space_id est un NewId : on compare son origine réelle.
        self.assertEqual(lead.egp_main_space_id._origin, self.space)

    def test_selecting_a_space_creates_no_commitment(self):
        """EGP-TST-OPP-023 — La sélection d'un espace ne réserve rien."""
        self.lead.egp_space_ids = self.space
        self.assertFalse(self.lead.egp_space_booking_ids)
        self.assertEqual(self.lead.egp_space_availability_state, 'available')

    def test_availability_reports_a_conflict(self):
        """EGP-RG-034C — Un créneau existant rend la salle indisponible."""
        self.env['planning.slot'].create({
            'resource_id': self.room_a.id,
            'role_id': self.role.id,
            'start_datetime': fields.Datetime.to_datetime('2026-11-20 08:00:00'),
            'end_datetime': fields.Datetime.to_datetime('2026-11-21 02:00:00'),
        })
        self.lead.egp_space_ids = self.space
        self.assertEqual(self.lead.egp_space_availability_state, 'conflict')

    def test_availability_is_unknown_without_period(self):
        lead = self.env['crm.lead'].create({
            'name': "Sans dates",
            'type': 'opportunity',
            'egp_space_ids': [(6, 0, self.space.ids)],
        })
        self.assertEqual(lead.egp_space_availability_state, 'unknown')

    def test_option_requires_dates_and_spaces(self):
        """EGP-TST-OPP-006 — Une option incomplète est refusée."""
        with self.assertRaises(ValidationError):
            self.lead.egp_option_active = True

    def test_option_release_keeps_history(self):
        """EGP-TST-OPP-025 — La libération trace la décision sans perdre l'historique."""
        self.lead.write({
            'egp_space_ids': [(6, 0, self.space.ids)],
            'egp_option_active': True,
            'egp_option_start': fields.Datetime.to_datetime('2026-10-01 09:00:00'),
            'egp_option_end': fields.Datetime.to_datetime('2026-10-15 18:00:00'),
            'egp_option_space_ids': [(6, 0, self.space.ids)],
        })
        self.assertEqual(self.lead.egp_option_status, 'active')

        self.lead.action_egp_option_release()

        self.assertFalse(self.lead.egp_option_active)
        self.assertEqual(self.lead.egp_option_status, 'released')
        self.assertTrue(self.lead.egp_option_decision_date)
        self.assertEqual(self.lead.egp_option_space_ids, self.space)

    def test_option_expires_by_cron(self):
        """EGP-DEC-044 — L'expiration dépend du temps et relève du cron."""
        self.lead.write({
            'egp_space_ids': [(6, 0, self.space.ids)],
            'egp_option_active': True,
            'egp_option_start': fields.Datetime.to_datetime('2020-01-01 09:00:00'),
            'egp_option_end': fields.Datetime.to_datetime('2020-01-15 18:00:00'),
            'egp_option_space_ids': [(6, 0, self.space.ids)],
        })
        self.env['crm.lead']._cron_egp_update_option_status()
        self.assertEqual(self.lead.egp_option_status, 'expired')

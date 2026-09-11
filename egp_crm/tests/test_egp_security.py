from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'egp')
class TestEgpCrmSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.prospector = Users.create({
            'name': "Prospecteur EGP",
            'login': 'egp_sec_prospector',
            'group_ids': [(6, 0, [cls.env.ref('egp_crm.group_egp_prospector').id])],
        })
        cls.other_prospector = Users.create({
            'name': "Autre Prospecteur",
            'login': 'egp_sec_prospector_2',
            'group_ids': [(6, 0, [cls.env.ref('egp_crm.group_egp_prospector').id])],
        })
        cls.salesperson = Users.create({
            'name': "Commercial EGP",
            'login': 'egp_sec_salesperson',
            'group_ids': [(6, 0, [cls.env.ref('egp_crm.group_egp_salesperson').id])],
        })
        cls.adv = Users.create({
            'name': "ADV EGP",
            'login': 'egp_sec_adv',
            'group_ids': [(6, 0, [cls.env.ref('egp_crm.group_egp_adv').id])],
        })
        cls.lead = cls.env['crm.lead'].create({
            'name': "Piste confidentielle",
            'type': 'lead',
            'egp_prospector_id': cls.prospector.id,
            'user_id': cls.prospector.id,
        })
        cls.opportunity = cls.env['crm.lead'].create({
            'name': "Opportunité confidentielle",
            'type': 'opportunity',
            'user_id': cls.salesperson.id,
        })

    def test_prospector_does_not_see_other_leads(self):
        """EGP-TST-SEC-001 — Aucun résultat sur les pistes d'un autre Prospecteur."""
        leads = self.env['crm.lead'].with_user(self.other_prospector).search(
            [('id', '=', self.lead.id)])
        self.assertFalse(leads)

    def test_salesperson_does_not_see_leads(self):
        """EGP-TST-SEC-002/003 — Le Commercial n'accède pas aux pistes."""
        with self.assertRaises(AccessError):
            self.lead.with_user(self.salesperson).read(['name'])

    def test_adv_cannot_modify_commercial_fields(self):
        """EGP-TST-SEC-006 — L'ADV est limité à la liste blanche administrative."""
        with self.assertRaises(UserError):
            self.opportunity.with_user(self.adv).write({'expected_revenue': 10000})

    def test_adv_can_modify_administrative_fields(self):
        """EGP-TST-SEC-007 — Les champs administratifs restent ouverts à l'ADV."""
        status = self.env.ref('egp_master_data.admin_status_complete')
        self.opportunity.with_user(self.adv).write({'egp_admin_status_id': status.id})
        self.assertEqual(self.opportunity.egp_admin_status_id, status)

    def test_adv_cannot_create_a_lead(self):
        """§11.6 — L'ADV ne crée pas de dossier commercial."""
        with self.assertRaises(UserError):
            self.env['crm.lead'].with_user(self.adv).create({
                'name': "Opportunité ADV",
                'type': 'opportunity',
            })

    def test_salesperson_cannot_reassign_an_opportunity(self):
        """§11.9 — Le changement de Commercial est réservé à l'encadrement."""
        with self.assertRaises(UserError):
            self.opportunity.with_user(self.salesperson).write({'user_id': self.adv.id})

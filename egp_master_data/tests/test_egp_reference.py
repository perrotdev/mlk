from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'egp')
class TestEgpReference(TransactionCase):

    def test_code_is_unique_per_company(self):
        self.env['egp.structure.type'].create({'name': "Test A", 'code': 'TEST_UNIQ'})
        with self.assertRaises(ValidationError):
            self.env['egp.structure.type'].create({'name': "Test B", 'code': 'TEST_UNIQ'})

    def test_code_is_immutable_for_business_users(self):
        """EGP-TST-CON-013 — le code reste stable une fois la valeur créée."""
        structure_type = self.env['egp.structure.type'].create({'name': "Test", 'code': 'TEST_IMMUT'})
        user = self.env['res.users'].create({
            'name': "Référentiel Admin",
            'login': 'egp_ref_admin',
            'group_ids': [(4, self.env.ref('egp_master_data.group_egp_reference_admin').id)],
        })
        with self.assertRaises(UserError):
            structure_type.with_user(user).write({'code': 'OTHER'})

    def test_reference_values_cannot_be_deleted(self):
        structure_type = self.env['egp.structure.type'].create({'name': "Test", 'code': 'TEST_DEL'})
        user = self.env['res.users'].create({
            'name': "Référentiel Admin",
            'login': 'egp_ref_admin_del',
            'group_ids': [(4, self.env.ref('egp_master_data.group_egp_reference_admin').id)],
        })
        with self.assertRaises(UserError):
            structure_type.with_user(user).unlink()

    def test_event_type_hierarchy(self):
        event_type = self.env.ref('egp_master_data.event_type_cocktail')
        self.assertEqual(event_type.parent_id.code, 'EVT_RECEPTION')
        self.assertTrue(event_type.complete_name.endswith("Cocktail"))

    def test_get_by_code(self):
        self.assertEqual(
            self.env['egp.opportunity.type']._get_by_code('FRAMEWORK'),
            self.env.ref('egp_master_data.opportunity_type_framework'),
        )

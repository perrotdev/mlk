from odoo import fields, models


class CrmStage(models.Model):
    _inherit = 'crm.stage'

    egp_code = fields.Char(
        string="Code EGP", index='btree_not_null', copy=False,
        help="Identifiant stable utilisé par les contrôles de transition. "
             "La logique métier ne s'appuie jamais sur le libellé de l'étape.")

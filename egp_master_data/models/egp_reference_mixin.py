from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class EgpReferenceMixin(models.AbstractModel):
    """Patron commun des référentiels administrables EGP (spécification §8.1).

    Chaque référentiel porte un ``code`` anglais stable utilisé par le code
    métier, un libellé traduit administrable et un archivage sans perte de lien.
    """

    _name = 'egp.reference.mixin'
    _description = "EGP Reference Mixin"
    _order = 'sequence, name, id'

    name = fields.Char(string="Libellé", required=True, translate=True)
    code = fields.Char(
        string="Code", required=True, index=True, copy=False,
        help="Identifiant technique stable. Il ne doit plus être modifié une fois la valeur utilisée.")
    sequence = fields.Integer(string="Séquence", default=10)
    active = fields.Boolean(string="Actif", default=True)
    description = fields.Text(string="Définition", translate=True)
    company_id = fields.Many2one(
        'res.company', string="Société", index=True,
        help="Laisser vide pour une valeur commune à toutes les sociétés.")
    color = fields.Integer(string="Couleur")

    @api.constrains('code', 'company_id', 'active')
    def _check_code_unique(self):
        for record in self.filtered('code'):
            duplicate = self.with_context(active_test=False).search_count([
                ('id', '!=', record.id),
                ('code', '=', record.code),
                ('company_id', '=', record.company_id.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "Le code « %(code)s » est déjà utilisé pour ce référentiel.",
                    code=record.code,
                ))

    def write(self, vals):
        if 'code' in vals and not self.env.su and not self.env.user.has_group('base.group_system'):
            changed = self.filtered(lambda record: record.code != vals['code'])
            if changed:
                raise UserError(_(
                    "Le code d'une valeur de référentiel est immuable. "
                    "Archivez la valeur et créez-en une nouvelle."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group('base.group_system'):
            raise UserError(_(
                "Les valeurs de référentiel ne se suppriment pas : archivez-les "
                "afin de conserver les enregistrements historiques qui les utilisent."))
        return super().unlink()

    @api.model
    def _get_by_code(self, code):
        """Retourne la valeur du référentiel correspondant au code stable donné."""
        return self.with_context(active_test=False).search([('code', '=', code)], limit=1)

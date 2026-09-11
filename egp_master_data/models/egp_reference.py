from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class EgpStructureType(models.Model):
    """EGP-REF-101 — Type juridique ou organisationnel d'une organisation."""

    _name = 'egp.structure.type'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Type de structure"


class EgpBusinessActivity(models.Model):
    """EGP-REF-102 — Activité principale, toujours rattachée à un secteur."""

    _name = 'egp.business.activity'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Activité principale"
    _order = 'industry_id, sequence, name, id'

    industry_id = fields.Many2one(
        'res.partner.industry', string="Secteur d'activité",
        required=True, index=True, ondelete='restrict')


class EgpPartnerRelation(models.Model):
    """EGP-REF-103 — Nature de la relation entre l'organisation et EGP."""

    _name = 'egp.partner.relation'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Relation avec EGP"


class EgpClientStatus(models.Model):
    """EGP-REF-104 — Cycle de vie du client, distinct des segmentations."""

    _name = 'egp.client.status'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Statut de cycle client"


class EgpCompanySize(models.Model):
    """EGP-REF-105 — Taille d'entreprise."""

    _name = 'egp.company.size'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Taille d'entreprise"


class EgpContactDepartment(models.Model):
    """EGP-REF-106 — Service ou département d'un contact."""

    _name = 'egp.contact.department'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Service / département"


class EgpContactChannel(models.Model):
    """EGP-REF-107 — Canal de contact préféré."""

    _name = 'egp.contact.channel'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Canal de contact préféré"


class EgpAdministrativeRegion(models.Model):
    """EGP-REF-108 — Région administrative, déduite du département."""

    _name = 'egp.administrative.region'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Région administrative"

    state_ids = fields.One2many(
        'res.country.state', 'egp_region_id', string="Départements")


class EgpEventType(models.Model):
    """EGP-REF-109 — Taxonomie hiérarchique des types d'événement (§8.10)."""

    _name = 'egp.event.type'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Type d'événement"
    _parent_store = True
    _order = 'complete_name, sequence, id'

    parent_id = fields.Many2one(
        'egp.event.type', string="Catégorie", index=True, ondelete='restrict')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('egp.event.type', 'parent_id', string="Sous-types")
    complete_name = fields.Char(
        string="Nom complet", compute='_compute_complete_name',
        recursive=True, store=True)

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for event_type in self:
            if event_type.parent_id:
                event_type.complete_name = f"{event_type.parent_id.complete_name} / {event_type.name}"
            else:
                event_type.complete_name = event_type.name

    @api.constrains('parent_id')
    def _check_parent_recursion(self):
        if self._has_cycle():
            raise ValidationError(_("Une catégorie de type d'événement ne peut pas se contenir elle-même."))


class EgpMarketSegment(models.Model):
    """EGP-REF-119 — Segment de marché adressé par l'affaire (§8.11)."""

    _name = 'egp.market.segment'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Segment de marché"


class EgpEventConfiguration(models.Model):
    """EGP-REF-111 — Configuration de salle."""

    _name = 'egp.event.configuration'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Configuration de salle"


class EgpCateringType(models.Model):
    """EGP-REF-112 — Type de prestation de restauration."""

    _name = 'egp.catering.type'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Type de restauration"


class EgpTechnicalLevel(models.Model):
    """EGP-REF-113 — Niveau de prestation audiovisuelle et technique."""

    _name = 'egp.technical.level'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Niveau technique"


class EgpAnimationType(models.Model):
    """EGP-REF-114 — Type d'animation."""

    _name = 'egp.animation.type'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Type d'animation"


class EgpLeadTemperature(models.Model):
    """EGP-REF-115 — Température commerciale d'une piste ou opportunité."""

    _name = 'egp.lead.temperature'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Température"


class EgpMaturityLevel(models.Model):
    """EGP-REF-116 — Niveau de maturité commerciale."""

    _name = 'egp.maturity.level'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Niveau de maturité"


class EgpOpportunityType(models.Model):
    """EGP-REF-117 — Type d'opportunité (ponctuel, contrat cadre, fille)."""

    _name = 'egp.opportunity.type'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Type d'opportunité"


class EgpAdminStatus(models.Model):
    """EGP-REF-118 — Statut administratif d'une opportunité, piloté par l'ADV."""

    _name = 'egp.admin.status'
    _inherit = ['egp.reference.mixin']
    _description = "EGP Statut administratif"


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    egp_region_id = fields.Many2one(
        'egp.administrative.region', string="Région administrative EGP",
        index='btree_not_null', ondelete='set null')

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    egp_first_call_delay_days = fields.Integer(
        related='company_id.egp_first_call_delay_days', readonly=False)
    egp_lead_inactivity_days = fields.Integer(
        related='company_id.egp_lead_inactivity_days', readonly=False)
    egp_quotation_follow_up_days = fields.Integer(
        related='company_id.egp_quotation_follow_up_days', readonly=False)
    egp_option_notice_days = fields.Integer(
        related='company_id.egp_option_notice_days', readonly=False)
    egp_option_escalation_days = fields.Integer(
        related='company_id.egp_option_escalation_days', readonly=False)
    egp_dormant_customer_delay_months = fields.Integer(
        related='company_id.egp_dormant_customer_delay_months', readonly=False)
    egp_regular_customer_min_events = fields.Integer(
        related='company_id.egp_regular_customer_min_events', readonly=False)
    egp_regular_customer_window_months = fields.Integer(
        related='company_id.egp_regular_customer_window_months', readonly=False)

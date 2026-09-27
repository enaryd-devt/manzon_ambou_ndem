# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AssociationMembershipFee(models.Model):
    _name = "association.membership.fee"
    _description = "Frais d'adhésion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Libellé", required=True, tracking=True)
    member_id = fields.Many2one("association.member", string="Membre", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="member_id.company_id", store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie", required=True, ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True)
    amount = fields.Monetary(string="Montant exigible", currency_field="currency_id", required=True, tracking=True)
    amount_paid = fields.Monetary(string="Montant réglé", currency_field="currency_id", default=0.0, readonly=True)
    amount_remaining = fields.Monetary(string="Reste à régler", currency_field="currency_id", compute="_compute_amount_remaining", store=True)
    state = fields.Selection([("due", "À régler"), ("paid", "Réglé"), ("cancelled", "Annulé")], string="Statut", default="due", required=True, tracking=True)

    @api.depends("amount", "amount_paid", "state")
    def _compute_amount_remaining(self):
        for record in self:
            record.amount_remaining = 0.0 if record.state == "cancelled" else max((record.amount or 0.0) - (record.amount_paid or 0.0), 0.0)

    def register_payment(self, amount):
        for record in self:
            settled = min(amount or 0.0, record.amount_remaining or 0.0)
            if settled:
                paid = (record.amount_paid or 0.0) + settled
                record.write({"amount_paid": paid, "state": "paid" if paid >= (record.amount or 0.0) - 0.01 else "due"})
        return True

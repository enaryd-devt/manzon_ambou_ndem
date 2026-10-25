# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssociationMembershipFee(models.Model):
    _name = "association.membership.fee"
    _description = "Créance membre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(string="Libellé", required=True, tracking=True)
    fee_type = fields.Selection(
        [("membership", "Frais d'adhésion"), ("adjustment", "Ajustement de situation")],
        string="Type",
        required=True,
        default="membership",
        tracking=True,
    )
    member_id = fields.Many2one("association.member", string="Membre", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one(related="member_id.company_id", store=True, readonly=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie", required=True, ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True)
    amount = fields.Monetary(string="Montant exigible", currency_field="currency_id", required=True, tracking=True)
    amount_paid = fields.Monetary(string="Montant réglé", currency_field="currency_id", default=0.0, readonly=True)
    amount_remaining = fields.Monetary(string="Reste à régler", currency_field="currency_id", compute="_compute_amount_remaining", store=True)
    state = fields.Selection([
        ("draft", "Brouillon"),
        ("due", "À régler"),
        ("paid", "Réglé"),
        ("cancelled", "Annulé"),
    ], string="Statut", default="due", required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        """An adjustment must be explicitly validated before collection."""
        for vals in vals_list:
            if (
                vals.get("fee_type") == "adjustment"
                and not self.env.context.get("allow_adjustment_state_change")
            ):
                vals["state"] = "draft"
        return super().create(vals_list)

    def write(self, vals):
        protected_fields = {"name", "fee_type", "member_id", "fund_id", "amount", "company_id"}
        for record in self:
            if record.fee_type != "adjustment":
                continue
            if record.state != "draft" and protected_fields.intersection(vals):
                raise UserError(_(
                    "Un ajustement validé ne peut plus être modifié."
                ))
            if (
                "state" in vals
                and vals["state"] != record.state
                and not self.env.context.get("allow_adjustment_state_change")
            ):
                raise UserError(_(
                    "Utilisez le bouton de validation pour modifier le statut de l'ajustement."
                ))
        return super().write(vals)

    def action_validate_adjustment(self):
        for record in self:
            if record.fee_type != "adjustment" or record.state != "draft":
                continue
            if record.amount <= 0:
                raise ValidationError(_("Le montant de l'ajustement doit être supérieur à zéro."))
            record.with_context(allow_adjustment_state_change=True).write({"state": "due"})
        return True

    @api.depends("amount", "amount_paid", "state")
    def _compute_amount_remaining(self):
        for record in self:
            record.amount_remaining = 0.0 if record.state == "cancelled" else max((record.amount or 0.0) - (record.amount_paid or 0.0), 0.0)

    def register_payment(self, amount):
        for record in self:
            settled = min(amount or 0.0, record.amount_remaining or 0.0)
            if settled:
                paid = (record.amount_paid or 0.0) + settled
                record.with_context(allow_adjustment_state_change=True).write({
                    "amount_paid": paid,
                    "state": "paid" if paid >= (record.amount or 0.0) - 0.01 else "due",
                })
        return True

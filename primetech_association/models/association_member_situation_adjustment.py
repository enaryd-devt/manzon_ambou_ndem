# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .association_membership_fee import (
    PAYMENT_PRIORITY_DEFAULT,
    PAYMENT_PRIORITY_HELP,
    PAYMENT_PRIORITY_SELECTION,
)


class AssociationMemberSituationAdjustment(models.Model):
    _name = "association.member.situation.adjustment"
    _description = "Ajustement de situation des membres"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "adjustment_date desc, id desc"

    name = fields.Char(string="Référence", required=True, default=lambda self: _("Nouvel ajustement"), tracking=True)
    adjustment_date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    company_id = fields.Many2one("res.company", string="Société", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    fund_id = fields.Many2one(
        "association.fund", string="Compte de trésorerie", required=True,
        ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True,
    )
    payment_priority = fields.Selection(
        PAYMENT_PRIORITY_SELECTION, string="Priorité de règlement",
        default=PAYMENT_PRIORITY_DEFAULT, required=True, tracking=True,
        help="Appliquée aux créances générées. " + PAYMENT_PRIORITY_HELP,
    )
    line_ids = fields.One2many("association.member.situation.adjustment.line", "adjustment_id", string="Membres concernés", copy=True)
    amount_total = fields.Monetary(string="Montant total", currency_field="currency_id", compute="_compute_amounts", store=True)
    amount_paid = fields.Monetary(string="Montant encaissé", currency_field="currency_id", compute="_compute_amounts", store=True)
    amount_remaining = fields.Monetary(string="Reste à encaisser", currency_field="currency_id", compute="_compute_amounts", store=True)
    state = fields.Selection([("draft", "Brouillon"), ("validated", "Validé")], default="draft", required=True, tracking=True)

    @api.depends("line_ids.amount", "line_ids.fee_id.amount_paid", "line_ids.fee_id.amount_remaining")
    def _compute_amounts(self):
        for record in self:
            record.amount_total = sum(record.line_ids.mapped("amount"))
            record.amount_paid = sum(record.line_ids.mapped("fee_id.amount_paid"))
            record.amount_remaining = sum(record.line_ids.mapped("fee_id.amount_remaining"))

    def write(self, vals):
        protected = {"name", "adjustment_date", "fund_id", "company_id", "line_ids", "payment_priority"}
        if protected.intersection(vals) and any(record.state != "draft" for record in self):
            raise UserError(_("Un document d'ajustement validé ne peut plus être modifié."))
        return super().write(vals)

    def action_validate(self):
        Fee = self.env["association.membership.fee"]
        for record in self:
            if record.state != "draft":
                continue
            if not record.line_ids:
                raise ValidationError(_("Ajoutez au moins un membre à ajuster."))
            invalid_lines = record.line_ids.filtered(lambda line: line.amount <= 0)
            if invalid_lines:
                raise ValidationError(_("Chaque ligne d'ajustement doit avoir un montant supérieur à zéro."))
            for line in record.line_ids:
                fee = Fee.with_context(allow_adjustment_state_change=True).create({
                    "name": line.name or record.name,
                    "fee_type": "adjustment",
                    "member_id": line.member_id.id,
                    "fund_id": record.fund_id.id,
                    "amount": line.amount,
                    "payment_priority": record.payment_priority,
                    "state": "due",
                })
                line.write({"fee_id": fee.id})
            record.write({"state": "validated"})
        return True


class AssociationMemberSituationAdjustmentLine(models.Model):
    _name = "association.member.situation.adjustment.line"
    _description = "Ligne d'ajustement de situation"
    _order = "sequence, id"

    adjustment_id = fields.Many2one("association.member.situation.adjustment", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="adjustment_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="adjustment_id.currency_id", readonly=True)
    member_id = fields.Many2one("association.member", string="Membre", required=True, ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True), ('state', '=', 'active')]" )
    name = fields.Char(string="Motif / libellé", required=True)
    amount = fields.Monetary(string="Montant à ajouter", currency_field="currency_id", required=True)
    fee_id = fields.Many2one("association.membership.fee", string="Créance générée", readonly=True, ondelete="restrict")

    _sql_constraints = [
        ("member_once_per_adjustment", "unique(adjustment_id, member_id)", "Un membre ne peut apparaître qu'une fois dans le même document d'ajustement."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        adjustment_ids = [vals.get("adjustment_id") for vals in vals_list if vals.get("adjustment_id")]
        adjustments = self.env["association.member.situation.adjustment"].browse(adjustment_ids)
        if any(adjustment.state != "draft" for adjustment in adjustments):
            raise UserError(_("Impossible d'ajouter une ligne à un ajustement validé."))
        return super().create(vals_list)

    def write(self, vals):
        protected = {"member_id", "name", "amount", "sequence"}
        if protected.intersection(vals) and any(line.adjustment_id.state != "draft" for line in self):
            raise UserError(_("Les lignes d'un ajustement validé ne peuvent plus être modifiées."))
        return super().write(vals)

    def unlink(self):
        if any(line.adjustment_id.state != "draft" for line in self):
            raise UserError(_("Les lignes d'un ajustement validé ne peuvent plus être supprimées."))
        return super().unlink()

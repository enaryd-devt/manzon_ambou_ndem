# -*- coding: utf-8 -*-

##############################################################################
#
#    PrimeTech Association Management
#    Copyright (C) 2026 PrimeTech Services
#
#    Author: PrimeTech Services
#    License LGPL-3
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMemberAccount(models.Model):
    _name = "association.member.account"
    _description = "Compte financier membre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "member_id, id"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="member_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Numéro de compte",
        readonly=True,
        copy=False,
        default="Nouveau",
        tracking=True,
        index=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        readonly=True,
        store=True,
    )

    image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo",
        readonly=True,
    )

    # ==========================================================
    # SOLDE
    # ==========================================================

    balance = fields.Monetary(
        string="Solde disponible",
        currency_field="currency_id",
        compute="_compute_balance",
    )

    total_credit = fields.Monetary(
        string="Total crédité",
        currency_field="currency_id",
        compute="_compute_balance",
    )

    total_debit = fields.Monetary(
        string="Total débité",
        currency_field="currency_id",
        compute="_compute_balance",
    )

    # ==========================================================
    # RELATIONS
    # ==========================================================

    transaction_ids = fields.One2many(
        comodel_name="association.member.account.transaction",
        inverse_name="account_id",
        string="Mouvements",
    )

    transaction_count = fields.Integer(
        string="Nombre de mouvements",
        compute="_compute_transaction_count",
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_member_account_member_unique",
            "unique(member_id)",
            "Un membre ne peut avoir qu'un seul compte financier interne.",
        ),
        (
            "association_member_account_name_unique",
            "unique(name)",
            "Le numéro du compte membre doit être unique.",
        ),
    ]

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.member.account"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # SOLDE
    # ==========================================================

    @api.depends(
        "transaction_ids.state",
        "transaction_ids.transaction_type",
        "transaction_ids.amount",
    )
    def _compute_balance(self):
        for record in self:
            validated_transactions = record.transaction_ids.filtered(
                lambda transaction: transaction.state == "validated"
            )

            credit_transactions = validated_transactions.filtered(
                lambda transaction: transaction.transaction_type == "credit"
            )

            debit_transactions = validated_transactions.filtered(
                lambda transaction: transaction.transaction_type == "debit"
            )

            total_credit = sum(credit_transactions.mapped("amount"))
            total_debit = sum(debit_transactions.mapped("amount"))

            record.total_credit = total_credit
            record.total_debit = total_debit
            record.balance = total_credit - total_debit

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    # ==========================================================
    # ACTIONS
    # ==========================================================

    def action_view_transactions(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvements du compte membre"),
            "res_model": "association.member.account.transaction",
            "view_mode": "list,form",
            "domain": [
                ("account_id", "=", self.id),
            ],
            "context": {
                "default_account_id": self.id,
            },
        }
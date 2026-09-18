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


class AssociationFund(models.Model):
    _name = "association.fund"
    _description = "Compte financier de l'association"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, name, id"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
        tracking=True,
    )

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    color = fields.Integer(
        string="Couleur",
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Nom du compte",
        required=True,
        tracking=True,
        index=True,
    )

    code = fields.Char(
        string="Référence",
        readonly=True,
        copy=False,
        default="Nouveau",
        tracking=True,
        index=True,
    )

    fund_type = fields.Selection(
        selection=[
            ("bank", "Compte bancaire"),
            ("cash", "Compte caisse"),
            ("mobile_money", "Mobile Money"),
            ("fund", "Compte fonds"),
            ("insurance", "Compte assurance"),
            ("other", "Autre compte financier"),
        ],
        string="Type de compte",
        required=True,
        default="bank",
        tracking=True,
        index=True,
    )

    # ==========================================================
    # INFORMATIONS FINANCIÈRES
    # ==========================================================

    institution_name = fields.Char(
        string="Banque / Opérateur",
        tracking=True,
    )

    account_number = fields.Char(
        string="Numéro de compte",
        tracking=True,
        copy=False,
    )

    account_holder = fields.Char(
        string="Titulaire du compte",
        tracking=True,
    )

    initial_balance = fields.Monetary(
        string="Solde initial",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
    )

    current_balance = fields.Monetary(
        string="Solde actuel",
        currency_field="currency_id",
        compute="_compute_current_balance",
    )

    total_in = fields.Monetary(
        string="Total des entrées",
        currency_field="currency_id",
        compute="_compute_current_balance",
    )

    total_out = fields.Monetary(
        string="Total des sorties",
        currency_field="currency_id",
        compute="_compute_current_balance",
    )

    # ==========================================================
    # RESPONSABLE
    # ==========================================================

    responsible_id = fields.Many2one(
        comodel_name="association.member",
        string="Responsable",
        domain=[
            (
                "active",
                "=",
                True,
            ),
        ],
        tracking=True,
    )

    # ==========================================================
    # RELATIONS
    # ==========================================================

    transaction_ids = fields.One2many(
        comodel_name="association.fund.transaction",
        inverse_name="fund_id",
        string="Mouvements",
    )

    transaction_count = fields.Integer(
        string="Nombre de mouvements",
        compute="_compute_transaction_count",
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    description = fields.Text(
        string="Description",
    )

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_fund_code_unique",
            "unique(code)",
            "La référence du compte financier doit être unique.",
        ),
    ]

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "Nouveau") == "Nouveau":
                vals["code"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.fund"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # CALCUL DU SOLDE
    # ==========================================================

    @api.depends(
        "initial_balance",
        "transaction_ids.state",
        "transaction_ids.transaction_type",
        "transaction_ids.amount",
    )
    def _compute_current_balance(self):
        for record in self:
            validated_transactions = record.transaction_ids.filtered(
                lambda transaction: transaction.state == "validated"
            )

            incoming_transactions = validated_transactions.filtered(
                lambda transaction: transaction.transaction_type == "in"
            )

            outgoing_transactions = validated_transactions.filtered(
                lambda transaction: transaction.transaction_type == "out"
            )

            total_in = sum(incoming_transactions.mapped("amount"))
            total_out = sum(outgoing_transactions.mapped("amount"))

            record.total_in = total_in
            record.total_out = total_out

            record.current_balance = (
                (record.initial_balance or 0.0)
                + total_in
                - total_out
            )

    @api.depends("transaction_ids")
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains("fund_type", "account_number")
    def _check_account_number(self):
        for record in self:
            if (
                record.fund_type == "bank"
                and not record.account_number
            ):
                raise ValidationError(
                    _(
                        "Le numéro de compte est obligatoire "
                        "pour un compte bancaire."
                    )
                )

    # ==========================================================
    # ACTIONS
    # ==========================================================

    def action_view_transactions(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvements financiers"),
            "res_model": "association.fund.transaction",
            "view_mode": "list,form",
            "domain": [
                ("fund_id", "=", self.id),
            ],
            "context": {
                "default_fund_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

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
from odoo.exceptions import UserError, ValidationError


class AssociationFundTransaction(models.Model):
    _name = "association.fund.transaction"
    _description = "Mouvement financier"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transaction_date desc, id desc"

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
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="fund_id.currency_id",
        readonly=True,
        store=True,
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Référence",
        readonly=True,
        copy=False,
        default="Nouveau",
        tracking=True,
        index=True,
    )

    description = fields.Char(
        string="Libellé",
        required=True,
        tracking=True,
    )

    transaction_date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    # ==========================================================
    # COMPTE FINANCIER
    # ==========================================================

    fund_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte financier",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    transaction_type = fields.Selection(
        selection=[
            ("in", "Entrée"),
            ("out", "Sortie"),
        ],
        string="Type de mouvement",
        required=True,
        default="in",
        tracking=True,
        index=True,
    )

    amount = fields.Monetary(
        string="Montant",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )

    # ==========================================================
    # ORIGINE
    # ==========================================================

    origin_model = fields.Char(
        string="Modèle d'origine",
        readonly=True,
        copy=False,
    )

    origin_res_id = fields.Integer(
        string="ID d'origine",
        readonly=True,
        copy=False,
    )

    origin_reference = fields.Char(
        string="Document d'origine",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # ==========================================================
    # ÉTAT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("validated", "Validé"),
            ("cancelled", "Annulé"),
        ],
        string="Statut",
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement membre",
        ondelete="restrict",
        index=True,
        readonly=True,
    )
    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_fund_transaction_amount_positive",
            "CHECK(amount > 0)",
            "Le montant du mouvement doit être strictement supérieur à zéro.",
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
                        "association.fund.transaction"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains("fund_id", "company_id")
    def _check_fund_company(self):
        for record in self:
            if (
                record.fund_id
                and record.company_id
                and record.fund_id.company_id != record.company_id
            ):
                raise ValidationError(
                    _(
                        "Le compte financier et le mouvement "
                        "doivent appartenir à la même Filiale."
                    )
                )

    # ==========================================================
    # WORKFLOW
    # ==========================================================

    def action_validate(self):
        for record in self:
            if record.state != "draft":
                continue

            if (
                record.transaction_type == "out"
                and record.amount > record.fund_id.current_balance
            ):
                raise ValidationError(
                    _(
                        "Solde insuffisant sur le compte financier %s.\n\n"
                        "Solde disponible : %s\n"
                        "Montant demandé : %s"
                    )
                    % (
                        record.fund_id.display_name,
                        record.fund_id.current_balance,
                        record.amount,
                    )
                )

            record.write({
                "state": "validated",
            })

        return True

    def action_cancel(self):
        for record in self:
            if record.state == "cancelled":
                continue

            record.write({
                "state": "cancelled",
            })

        return True

    def action_reset_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise UserError(
                    _(
                        "Seul un mouvement annulé peut être "
                        "remis en brouillon."
                    )
                )

            record.write({
                "state": "draft",
            })

        return True

    # ==========================================================
    # PROTECTION
    # ==========================================================

    def unlink(self):
        for record in self:
            if record.state == "validated":
                raise UserError(
                    _(
                        "Un mouvement financier validé "
                        "ne peut pas être supprimé.\n\n"
                        "Annulez le mouvement ou créez "
                        "un mouvement correctif."
                    )
                )

        return super().unlink()
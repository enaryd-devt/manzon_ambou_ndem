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
from odoo.exceptions import ValidationError, UserError


class AssociationIncome(models.Model):
    _name = "association.income"
    _description = "Recette"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "income_date desc, id desc"

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

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Référence",
        required=True,
        copy=False,
        readonly=True,
        default="Nouveau",
        tracking=True,
        index=True,
    )

    income_date = fields.Date(
        string="Date de la recette",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    income_type = fields.Selection(
        selection=[
            ("sale", "Vente"),
            ("service", "Prestation de service"),
            ("event", "Événement"),
            ("rental", "Location"),
            ("interest", "Intérêts"),
            ("refund", "Remboursement reçu"),
            ("other", "Autre recette"),
        ],
        string="Type de recette",
        required=True,
        default="other",
        tracking=True,
        index=True,
    )

    # ==========================================================
    # ORIGINE DE LA RECETTE
    # ==========================================================

    source_name = fields.Char(
        string="Origine / Provenance",
        required=True,
        tracking=True,
    )

    description = fields.Text(
        string="Description",
    )

    external_reference = fields.Char(
        string="Référence externe",
        tracking=True,
    )

    # ==========================================================
    # MONTANT
    # ==========================================================

    amount = fields.Monetary(
        string="Montant",
        currency_field="currency_id",
        required=True,
        default=0.0,
        tracking=True,
    )

    payment_method = fields.Selection(
        selection=[
            ("cash", "Espèces"),
            ("bank", "Virement bancaire"),
            ("cheque", "Chèque"),
            ("mobile_money", "Mobile Money"),
            ("other", "Autre"),
        ],
        string="Mode d'encaissement",
        required=True,
        default="cash",
        tracking=True,
    )

    # ==========================================================
    # COMPTE FINANCIER
    # ==========================================================

    fund_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte financier de réception",
        required=False,
        ondelete="restrict",
        tracking=True,
        index=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    fund_transaction_id = fields.Many2one(
        comodel_name="association.fund.transaction",
        string="Mouvement financier",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    # ==========================================================
    # STATUT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("validated", "Validée"),
            ("cancelled", "Annulée"),
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

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_income_amount_positive",
            "CHECK(amount >= 0)",
            "Le montant de la recette ne peut pas être négatif.",
        ),
    ]

    # ==========================================================
    # CRÉATION
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            if vals.get("name", "Nouveau") == "Nouveau":

                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.income"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # CONTRAINTES MÉTIER
    # ==========================================================

    @api.constrains(
        "amount",
    )
    def _check_amount(self):
        for record in self:

            if record.amount < 0:

                raise ValidationError(
                    _(
                        "Le montant de la recette "
                        "ne peut pas être négatif."
                    )
                )

    @api.constrains(
        "fund_id",
        "company_id",
    )
    def _check_fund_company(self):
        for record in self:

            if (
                record.fund_id
                and record.fund_id.company_id
                != record.company_id
            ):

                raise ValidationError(
                    _(
                        "Le compte financier et la recette "
                        "doivent appartenir à la même Filiale."
                    )
                )

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def action_validate(self):

        FundTransaction = self.env[
            "association.fund.transaction"
        ]

        for record in self:

            if record.state != "draft":
                continue

            if record.amount <= 0:

                raise UserError(
                    _(
                        "Le montant de la recette "
                        "doit être supérieur à zéro."
                    )
                )

            if not record.fund_id:

                raise UserError(
                    _(
                        "Vous devez sélectionner le compte financier "
                        "qui reçoit la recette."
                    )
                )

            if record.fund_transaction_id:

                raise UserError(
                    _(
                        "Un mouvement financier est déjà lié "
                        "à cette recette."
                    )
                )

            transaction = FundTransaction.create(
                {
                    "fund_id": record.fund_id.id,
                    "company_id": record.company_id.id,
                    "transaction_date": record.income_date,
                    "description": _(
                        "Recette %s - %s"
                    )
                    % (
                        record.name,
                        record.source_name,
                    ),
                    "transaction_type": "in",
                    "amount": record.amount,
                    "origin_reference": record.name,
                    "origin_model": record._name,
                    "origin_res_id": record.id,
                }
            )

            transaction.action_validate()

            record.write(
                {
                    "fund_transaction_id": transaction.id,
                    "state": "validated",
                }
            )

        return True

    # ==========================================================
    # ANNULATION
    # ==========================================================

    def action_cancel(self):

        for record in self:

            if record.state == "cancelled":
                continue

            if (
                record.fund_transaction_id
                and record.fund_transaction_id.state
                != "cancelled"
            ):

                record.fund_transaction_id.action_cancel()

            record.state = "cancelled"

        return True

    # ==========================================================
    # REMISE EN BROUILLON
    # ==========================================================

    def action_reset_draft(self):

        for record in self:

            if record.state != "cancelled":
                continue

            record.state = "draft"

        return True

    # ==========================================================
    # VOIR LE MOUVEMENT FINANCIER
    # ==========================================================

    def action_view_fund_transaction(self):

        self.ensure_one()

        if not self.fund_transaction_id:

            raise UserError(
                _(
                    "Aucun mouvement financier "
                    "n'est lié à cette recette."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvement financier"),
            "res_model": "association.fund.transaction",
            "view_mode": "form",
            "res_id": self.fund_transaction_id.id,
            "target": "current",
        }

    # ==========================================================
    # PROTECTION DES MODIFICATIONS
    # ==========================================================

    def write(self, vals):

        protected_fields = {
            "company_id",
            "income_date",
            "income_type",
            "source_name",
            "amount",
            "payment_method",
            "fund_id",
        }

        if protected_fields.intersection(vals):

            for record in self:

                if record.state == "validated":

                    raise UserError(
                        _(
                            "Une recette validée ne peut plus être "
                            "modifiée. Annulez-la avant toute correction."
                        )
                    )

        return super().write(vals)

    # ==========================================================
    # PROTECTION SUPPRESSION
    # ==========================================================

    def unlink(self):

        for record in self:

            if record.state == "validated":

                raise UserError(
                    _(
                        "Une recette validée ne peut pas être supprimée."
                    )
                )

            if record.fund_transaction_id:

                raise UserError(
                    _(
                        "Cette recette possède déjà un mouvement financier "
                        "et ne peut plus être supprimée."
                    )
                )

        return super().unlink()
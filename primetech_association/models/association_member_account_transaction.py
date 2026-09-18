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


class AssociationMemberAccountTransaction(models.Model):
    _name = "association.member.account.transaction"
    _description = "Mouvement de compte membre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transaction_date desc, id desc"

    # ==========================================================
    # ORIGINE DU MOUVEMENT
    # ==========================================================

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement d'origine",
        ondelete="restrict",
        index=True,
        readonly=True,
        copy=False,
        tracking=True,
    )
    
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
        related="account_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="account_id.currency_id",
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

    transaction_date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    description = fields.Char(
        string="Libellé",
        required=True,
        tracking=True,
    )

    # ==========================================================
    # COMPTE MEMBRE
    # ==========================================================

    account_id = fields.Many2one(
        comodel_name="association.member.account",
        string="Compte membre",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    member_id = fields.Many2one(
        related="account_id.member_id",
        string="Membre",
        readonly=True,
        store=True,
    )

    transaction_type = fields.Selection(
        selection=[
            ("credit", "Crédit"),
            ("debit", "Débit"),
        ],
        string="Type de mouvement",
        required=True,
        default="credit",
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

    origin_type = fields.Selection(
        selection=[
            ("payment_surplus", "Surplus de paiement"),
            ("subscription_payment", "Paiement de cotisation"),
            ("voluntary_deposit", "Dépôt volontaire"),
            ("refund", "Remboursement"),
            ("adjustment", "Ajustement"),
            ("other", "Autre"),
        ],
        string="Origine",
        required=True,
        default="other",
        tracking=True,
    )

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

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_member_account_transaction_amount_positive",
            "CHECK(amount > 0)",
            "Le montant du mouvement doit être supérieur à zéro.",
        ),
        (
            "association_member_account_transaction_payment_unique",
            "unique(payment_id)",
            (
                "Le surplus de ce paiement a déjà été "
                "affecté à un compte membre."
            ),
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
                        "association.member.account.transaction"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # WORKFLOW
    # ==========================================================

    def action_validate(self):
        for record in self:
            if record.state != "draft":
                continue

            if (
                record.transaction_type == "debit"
                and record.amount > record.account_id.balance
            ):
                raise ValidationError(
                    _(
                        "Le solde du compte membre est insuffisant.\n\n"
                        "Solde disponible : %s\n"
                        "Montant demandé : %s"
                    )
                    % (
                        record.account_id.balance,
                        record.amount,
                    )
                )

            record.write({
                "state": "validated",
            })

        return True

    def action_cancel(self):
        for record in self:
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
                        "Un mouvement validé du compte membre "
                        "ne peut pas être supprimé.\n\n"
                        "Utilisez un mouvement correctif."
                    )
                )

        return super().unlink()
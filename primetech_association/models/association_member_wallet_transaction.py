# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMemberWalletTransaction(models.Model):
    _name = "association.member.wallet.transaction"
    _description = "Mouvement du compte membre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transaction_date desc, id desc"

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Référence",
        default=lambda self: _("Nouveau"),
        required=True,
        copy=False,
        readonly=True,
    )

    wallet_id = fields.Many2one(
        comodel_name="association.member.wallet",
        string="Compte membre",
        required=True,
        ondelete="cascade",
        index=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        related="wallet_id.member_id",
        store=True,
        readonly=True,
        index=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="wallet_id.company_id",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="wallet_id.currency_id",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # MOUVEMENT
    # ==========================================================

    transaction_type = fields.Selection(
        selection=[
            ("credit", "Crédit"),
            ("debit", "Débit"),
        ],
        string="Type",
        required=True,
        tracking=True,
    )

    amount = fields.Monetary(
        string="Montant",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )

    transaction_date = fields.Datetime(
        string="Date",
        default=fields.Datetime.now,
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
            ("refund", "Remboursement"),
            ("manual", "Opération manuelle"),
        ],
        string="Origine",
        required=True,
        default="manual",
        tracking=True,
    )

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement",
        ondelete="restrict",
    )

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion",
        ondelete="restrict",
    )

    description = fields.Char(
        string="Description",
        required=True,
    )

    signed_amount = fields.Monetary(
        string="Mouvement",
        currency_field="currency_id",
        compute="_compute_signed_amount",
        store=True,
    )

    # ==========================================================
    # ÉTAT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("confirmed", "Confirmé"),
            ("cancelled", "Annulé"),
        ],
        string="Statut",
        default="draft",
        required=True,
        tracking=True,
    )


    # ==========================================================
    # MONTANT SIGNÉ
    # ==========================================================

    @api.depends(
        "transaction_type",
        "amount",
        "state",
    )
    def _compute_signed_amount(self):

        for record in self:

            amount = record.amount or 0.0

            if record.state != "confirmed":

                record.signed_amount = 0.0

            elif record.transaction_type == "credit":

                record.signed_amount = amount

            elif record.transaction_type == "debit":

                record.signed_amount = -amount

            else:

                record.signed_amount = 0.0

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            if vals.get(
                "name",
                _("Nouveau"),
            ) == _("Nouveau"):

                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.member.wallet.transaction"
                    )
                    or _("Nouveau")
                )

        return super().create(vals_list)

    # ==========================================================
    # CONTRÔLE
    # ==========================================================

    @api.constrains("amount")
    def _check_amount(self):

        for record in self:

            if record.amount <= 0:

                raise ValidationError(
                    _(
                        "Le montant du mouvement doit être "
                        "strictement supérieur à zéro."
                    )
                )

    # ==========================================================
    # CONFIRMER
    # ==========================================================

    def action_confirm(self):

        for record in self:

            if record.state != "draft":
                continue

            if (
                record.transaction_type == "debit"
                and record.amount > record.wallet_id.balance
            ):

                raise ValidationError(
                    _(
                        "Le solde du compte membre est insuffisant."
                    )
                )

            record.state = "confirmed"

        return True

    # ==========================================================
    # ANNULER
    # ==========================================================

    def action_cancel(self):

        for record in self:

            if record.state == "confirmed":

                record.state = "cancelled"

        return True
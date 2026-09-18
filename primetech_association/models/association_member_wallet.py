# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AssociationMemberWallet(models.Model):
    _name = "association.member.wallet"
    _description = "Compte financier du membre"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "member_id"

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Compte",
        compute="_compute_name",
        store=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        ondelete="cascade",
        index=True,
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
        store=True,
        readonly=True,
    )

    # ==========================================================
    # SOLDE
    # ==========================================================

    balance = fields.Monetary(
        string="Solde disponible",
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
        tracking=True,
    )

    total_credit = fields.Monetary(
        string="Total des crédits",
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
    )

    total_debit = fields.Monetary(
        string="Total des débits",
        currency_field="currency_id",
        compute="_compute_balance",
        store=True,
    )

    # ==========================================================
    # MOUVEMENTS
    # ==========================================================

    transaction_ids = fields.One2many(
        comodel_name="association.member.wallet.transaction",
        inverse_name="wallet_id",
        string="Mouvements",
    )

    transaction_count = fields.Integer(
        string="Nombre de mouvements",
        compute="_compute_transaction_count",
    )

    # ==========================================================
    # ÉTAT
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    

    # ==========================================================
    # CONTRAINTE
    # ==========================================================

    _sql_constraints = [
        (
            "association_member_wallet_member_unique",
            "unique(member_id)",
            "Un membre ne peut avoir qu'un seul compte financier.",
        ),
    ]

    # ==========================================================
    # NOM
    # ==========================================================

    @api.depends(
        "member_id",
        "member_id.name",
        "member_id.member_code",
    )
    def _compute_name(self):
        for record in self:

            if not record.member_id:
                record.name = _("Compte membre")
                continue

            record.name = _(
                "Compte %(code)s - %(member)s"
            ) % {
                "code":
                    record.member_id.member_code or "-",

                "member":
                    record.member_id.name or "",
            }

    # ==========================================================
    # SOLDE
    # ==========================================================

    @api.depends(
        "transaction_ids",
        "transaction_ids.amount",
        "transaction_ids.transaction_type",
        "transaction_ids.state",
    )
    def _compute_balance(self):

        for record in self:

            confirmed_transactions = (
                record.transaction_ids.filtered(
                    lambda transaction:
                        transaction.state == "confirmed"
                )
            )

            credits = confirmed_transactions.filtered(
                lambda transaction:
                    transaction.transaction_type == "credit"
            )

            debits = confirmed_transactions.filtered(
                lambda transaction:
                    transaction.transaction_type == "debit"
            )

            total_credit = sum(
                credits.mapped("amount")
            )

            total_debit = sum(
                debits.mapped("amount")
            )

            record.total_credit = total_credit
            record.total_debit = total_debit

            record.balance = (
                total_credit - total_debit
            )

    # ==========================================================
    # COMPTEUR
    # ==========================================================

    def _compute_transaction_count(self):

        for record in self:

            record.transaction_count = len(
                record.transaction_ids
            )

    # ==========================================================
    # ACTION MOUVEMENTS
    # ==========================================================

    def action_view_transactions(self):

        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvements du compte"),
            "res_model":
                "association.member.wallet.transaction",
            "view_mode": "list,form",
            "domain": [
                ("wallet_id", "=", self.id),
            ],
            "context": {
                "default_wallet_id": self.id,
            },
        }
    

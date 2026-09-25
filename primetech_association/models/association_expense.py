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


class AssociationExpense(models.Model):
    _name = "association.expense"
    _description = "Dépense"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "expense_date desc, id desc"

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

    expense_date = fields.Date(
        string="Date de la dépense",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    expense_type = fields.Selection(
        selection=[
            ("purchase", "Achat"),
            ("operation", "Fonctionnement"),
            ("transport", "Transport"),
            ("communication", "Communication"),
            ("event", "Événement"),
            ("assistance", "Assistance / Aide"),
            ("maintenance", "Entretien / Maintenance"),
            ("rent", "Loyer"),
            ("salary", "Rémunération"),
            ("bank_fee", "Frais bancaires"),
            ("refund", "Remboursement"),
            ("other", "Autre dépense"),
        ],
        string="Type de dépense",
        required=True,
        default="operation",
        tracking=True,
        index=True,
    )

    # ==========================================================
    # OBJET DE LA DÉPENSE
    # ==========================================================

    subject = fields.Char(
        string="Objet de la dépense",
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
    # BÉNÉFICIAIRE
    # ==========================================================

    beneficiary_type = fields.Selection(
        selection=[
            ("member", "Membre"),
            ("external", "Bénéficiaire externe"),
            ("supplier", "Fournisseur"),
            ("other", "Autre"),
        ],
        string="Type de bénéficiaire",
        required=True,
        default="external",
        tracking=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre bénéficiaire",
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    beneficiary_name = fields.Char(
        string="Nom du bénéficiaire",
        tracking=True,
    )

    beneficiary_phone = fields.Char(
        string="Téléphone",
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
        string="Mode de décaissement",
        required=True,
        default="cash",
        tracking=True,
    )

    # ==========================================================
    # COMPTE FINANCIER
    # ==========================================================

    fund_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte financier de décaissement",
        ondelete="restrict",
        tracking=True,
        index=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    fund_balance = fields.Monetary(
        string="Solde disponible",
        currency_field="currency_id",
        compute="_compute_fund_balance",
    )

    fund_transaction_id = fields.Many2one(
        comodel_name="association.fund.transaction",
        string="Mouvement financier",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    # ==========================================================
    # JUSTIFICATIF
    # ==========================================================

    attachment = fields.Binary(
        string="Justificatif",
        attachment=True,
    )

    attachment_filename = fields.Char(
        string="Nom du justificatif",
    )

    receipt_number = fields.Char(
        string="N° reçu / facture",
        tracking=True,
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
    # CALCUL DU SOLDE DU COMPTE FINANCIER
    # ==========================================================

    @api.depends(
        "fund_id",
        "fund_id.transaction_ids",
        "fund_id.transaction_ids.amount",
        "fund_id.transaction_ids.transaction_type",
        "fund_id.transaction_ids.state",
    )
    def _compute_fund_balance(self):

        for record in self:

            if not record.fund_id:

                record.fund_balance = 0.0

                continue

            transactions = record.fund_id.transaction_ids.filtered(
                lambda transaction: transaction.state == "validated"
            )

            total_in = sum(
                transactions.filtered(
                    lambda transaction: (
                        transaction.transaction_type == "in"
                    )
                ).mapped("amount")
            )

            total_out = sum(
                transactions.filtered(
                    lambda transaction: (
                        transaction.transaction_type == "out"
                    )
                ).mapped("amount")
            )

            record.fund_balance = total_in - total_out

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
            "association_expense_amount_positive",
            "CHECK(amount >= 0)",
            "Le montant de la dépense ne peut pas être négatif.",
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
                        "association.expense"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # ONCHANGE BÉNÉFICIAIRE
    # ==========================================================

    @api.onchange("beneficiary_type")
    def _onchange_beneficiary_type(self):

        for record in self:

            if record.beneficiary_type == "member":

                record.beneficiary_name = False
                record.beneficiary_phone = False

            else:

                record.member_id = False

    # ==========================================================
    # ONCHANGE MEMBRE
    # ==========================================================

    @api.onchange("member_id")
    def _onchange_member_id(self):

        for record in self:

            if not record.member_id:
                continue

            if (
                record.member_id.company_id
                != record.company_id
            ):

                record.member_id = False

                return {
                    "warning": {
                        "title": _("Filiale incorrecte"),
                        "message": _(
                            "Le membre sélectionné n'appartient pas "
                            "à la Filiale de cette dépense."
                        ),
                    }
                }

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
                        "Le montant de la dépense "
                        "ne peut pas être négatif."
                    )
                )

    @api.constrains(
        "beneficiary_type",
        "member_id",
        "beneficiary_name",
    )
    def _check_beneficiary(self):

        for record in self:

            if (
                record.beneficiary_type == "member"
                and not record.member_id
            ):

                raise ValidationError(
                    _(
                        "Vous devez sélectionner "
                        "le membre bénéficiaire."
                    )
                )

            if (
                record.beneficiary_type != "member"
                and not record.beneficiary_name
            ):

                raise ValidationError(
                    _(
                        "Vous devez renseigner "
                        "le nom du bénéficiaire."
                    )
                )

    @api.constrains(
        "member_id",
        "company_id",
    )
    def _check_member_company(self):

        for record in self:

            if (
                record.member_id
                and record.member_id.company_id
                != record.company_id
            ):

                raise ValidationError(
                    _(
                        "Le membre et la dépense doivent appartenir "
                        "à la même Filiale."
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
                        "Le compte financier et la dépense "
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
                        "Le montant de la dépense "
                        "doit être supérieur à zéro."
                    )
                )

            if not record.fund_id:

                raise UserError(
                    _(
                        "Vous devez sélectionner le compte financier "
                        "qui finance cette dépense."
                    )
                )

            if record.fund_transaction_id:

                raise UserError(
                    _(
                        "Un mouvement financier est déjà lié "
                        "à cette dépense."
                    )
                )

            # ==================================================
            # CONTRÔLE DU SOLDE
            # ==================================================

            if record.fund_balance < record.amount:

                raise UserError(
                    _(
                        "Solde insuffisant sur le compte financier "
                        "'%(fund)s'.\n\n"
                        "Solde disponible : %(balance).2f %(currency)s\n"
                        "Montant demandé : %(amount).2f %(currency)s"
                    )
                    % {
                        "fund": record.fund_id.display_name,
                        "balance": record.fund_balance,
                        "amount": record.amount,
                        "currency": record.currency_id.name,
                    }
                )

            # ==================================================
            # CRÉATION DU MOUVEMENT FINANCIER
            # ==================================================

            transaction = FundTransaction.create(
                {
                    "fund_id": record.fund_id.id,
                    "company_id": record.company_id.id,
                    "transaction_date": record.expense_date,
                    "description": _(
                        "Dépense %s - %s"
                    )
                    % (
                        record.name,
                        record.subject,
                    ),
                    "transaction_type": "out",
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
                    "n'est lié à cette dépense."
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

    def action_print_receipt(self):
        """Print the A5 disbursement receipt once the expense is validated."""
        self.ensure_one()
        if self.state != "validated":
            raise UserError(_("Le reçu est disponible après validation de la dépense."))
        return self.env.ref(
            "primetech_association.action_report_expense_receipt"
        ).report_action(self)

    # ==========================================================
    # PROTECTION DES MODIFICATIONS
    # ==========================================================

    def write(self, vals):

        protected_fields = {
            "company_id",
            "expense_date",
            "expense_type",
            "subject",
            "beneficiary_type",
            "member_id",
            "beneficiary_name",
            "amount",
            "payment_method",
            "fund_id",
        }

        if protected_fields.intersection(vals):

            for record in self:

                if record.state == "validated":

                    raise UserError(
                        _(
                            "Une dépense validée ne peut plus être "
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
                        "Une dépense validée ne peut pas être supprimée."
                    )
                )

            if record.fund_transaction_id:

                raise UserError(
                    _(
                        "Cette dépense possède déjà un mouvement financier "
                        "et ne peut plus être supprimée."
                    )
                )

        return super().unlink()

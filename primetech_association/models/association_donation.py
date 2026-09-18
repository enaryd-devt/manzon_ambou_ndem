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


class AssociationDonation(models.Model):
    _name = "association.donation"
    _description = "Don"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "donation_date desc, id desc"

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

    donation_date = fields.Date(
        string="Date du don",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    donation_type = fields.Selection(
        selection=[
            ("financial", "Don financier"),
            ("in_kind", "Don en nature"),
        ],
        string="Type de don",
        required=True,
        default="financial",
        tracking=True,
    )

    # ==========================================================
    # DONATEUR
    # ==========================================================

    donor_type = fields.Selection(
        selection=[
            ("member", "Membre"),
            ("external", "Donateur externe"),
            ("anonymous", "Anonyme"),
        ],
        string="Type de donateur",
        required=True,
        default="member",
        tracking=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre donateur",
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    donor_name = fields.Char(
        string="Nom du donateur",
        tracking=True,
    )

    donor_phone = fields.Char(
        string="Téléphone",
    )

    donor_email = fields.Char(
        string="E-mail",
    )

    # ==========================================================
    # DON FINANCIER
    # ==========================================================

    amount = fields.Monetary(
        string="Montant du don",
        currency_field="currency_id",
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
        string="Mode de réception",
        default="cash",
        tracking=True,
    )

    fund_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte financier de réception",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
    )

    external_reference = fields.Char(
        string="Référence externe",
        tracking=True,
    )

    # ==========================================================
    # DON EN NATURE
    # ==========================================================

    item_description = fields.Text(
        string="Description du bien",
    )

    quantity = fields.Float(
        string="Quantité",
        default=1.0,
    )

    estimated_value = fields.Monetary(
        string="Valeur estimée",
        currency_field="currency_id",
        default=0.0,
        tracking=True,
    )

    # ==========================================================
    # MOUVEMENT FINANCIER
    # ==========================================================

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
            ("validated", "Validé"),
            ("cancelled", "Annulé"),
        ],
        string="Statut",
        default="draft",
        required=True,
        tracking=True,
        index=True,
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
            "association_donation_amount_positive",
            "CHECK(amount >= 0)",
            "Le montant du don ne peut pas être négatif.",
        ),
        (
            "association_donation_estimated_value_positive",
            "CHECK(estimated_value >= 0)",
            "La valeur estimée ne peut pas être négative.",
        ),
        (
            "association_donation_quantity_positive",
            "CHECK(quantity >= 0)",
            "La quantité ne peut pas être négative.",
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
                        "association.donation"
                    )
                    or "Nouveau"
                )

        return super().create(vals_list)

    # ==========================================================
    # ONCHANGE DONATEUR
    # ==========================================================

    @api.onchange("donor_type")
    def _onchange_donor_type(self):
        for record in self:
            if record.donor_type == "member":
                record.donor_name = False
                record.donor_phone = False
                record.donor_email = False

            elif record.donor_type == "external":
                record.member_id = False

            elif record.donor_type == "anonymous":
                record.member_id = False
                record.donor_name = False
                record.donor_phone = False
                record.donor_email = False

    # ==========================================================
    # ONCHANGE MEMBRE
    # ==========================================================

    @api.onchange("member_id")
    def _onchange_member_id(self):
        for record in self:
            if (
                record.member_id
                and record.member_id.company_id
                != record.company_id
            ):
                record.member_id = False

                return {
                    "warning": {
                        "title": _("Filiale incorrecte"),
                        "message": _(
                            "Le membre sélectionné n'appartient pas "
                            "à la Filiale du don."
                        ),
                    }
                }

    # ==========================================================
    # CONTRAINTES MÉTIER
    # ==========================================================

    @api.constrains(
        "donor_type",
        "member_id",
        "donor_name",
    )
    def _check_donor(self):
        for record in self:
            if (
                record.donor_type == "member"
                and not record.member_id
            ):
                raise ValidationError(
                    _(
                        "Vous devez sélectionner le membre donateur."
                    )
                )

            if (
                record.donor_type == "external"
                and not record.donor_name
            ):
                raise ValidationError(
                    _(
                        "Vous devez renseigner le nom du donateur externe."
                    )
                )

    @api.constrains(
        "donation_type",
        "amount",
        "fund_id",
        "item_description",
        "quantity",
    )
    def _check_donation_information(self):
        for record in self:
            if record.donation_type == "financial":
                if record.amount <= 0:
                    raise ValidationError(
                        _(
                            "Le montant du don financier "
                            "doit être supérieur à zéro."
                        )
                    )

            if record.donation_type == "in_kind":
                if not record.item_description:
                    raise ValidationError(
                        _(
                            "Vous devez décrire le bien reçu."
                        )
                    )

                if record.quantity <= 0:
                    raise ValidationError(
                        _(
                            "La quantité du don en nature "
                            "doit être supérieure à zéro."
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
                        "Le membre et le don doivent appartenir "
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
                        "Le compte financier et le don doivent appartenir "
                        "à la même Filiale."
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

            if record.donation_type == "financial":
                if not record.fund_id:
                    raise UserError(
                        _(
                            "Vous devez sélectionner le compte financier "
                            "qui reçoit le don."
                        )
                    )

                if record.amount <= 0:
                    raise UserError(
                        _(
                            "Le montant du don doit être supérieur à zéro."
                        )
                    )

                transaction = FundTransaction.create(
                    {
                        "fund_id": record.fund_id.id,
                        "company_id": record.company_id.id,
                        "transaction_date": record.donation_date,
                        "description": _(
                            "Don %s"
                        )
                        % record.name,
                        "transaction_type": "in",
                        "amount": record.amount,
                        "origin_reference": record.name,
                        "origin_model": record._name,
                        "origin_res_id": record.id,
                    }
                )

                transaction.action_validate()

                record.fund_transaction_id = transaction.id

            record.state = "validated"

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
                and record.fund_transaction_id.state != "cancelled"
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
                    "Aucun mouvement financier n'est lié à ce don."
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
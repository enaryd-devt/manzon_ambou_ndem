# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


# ==============================================================
# ASSISTANT DE CLÔTURE DU CYCLE
# ==============================================================


class AssociationSubscriptionCycleCloseWizard(
    models.TransientModel
):

    _name = "association.subscription.cycle.close.wizard"
    _description = (
        "Assistant de clôture d'un cycle de cotisation"
    )

    # ==========================================================
    # CYCLE
    # ==========================================================

    period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle",
        required=True,
        readonly=True,
        ondelete="cascade",
    )

    meeting_subscription_session_id = fields.Many2one(
        comodel_name="association.meeting.subscription.session",
        string="Session de cotisation en réunion",
        readonly=True,
        ondelete="restrict",
    )

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        related="period_id.subscription_id",
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="period_id.company_id",
        readonly=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="period_id.currency_id",
        readonly=True,
    )

    # ==========================================================
    # STATISTIQUES DU CYCLE
    # ==========================================================

    expected_amount = fields.Monetary(
        string="Montant attendu",
        related="period_id.expected_amount",
        currency_field="currency_id",
        readonly=True,
    )

    collected_amount = fields.Monetary(
        string="Cagnotte collectée",
        related="period_id.collected_amount",
        currency_field="currency_id",
        readonly=True,
    )

    penalty_collected_amount = fields.Monetary(
        string="Pénalités reversées",
        related="period_id.penalty_collected_amount",
        currency_field="currency_id",
        readonly=True,
    )

    allocated_amount = fields.Monetary(
        string="Déjà attribué",
        related="period_id.allocated_amount",
        currency_field="currency_id",
        readonly=True,
    )

    available_amount = fields.Monetary(
        string="Cagnotte disponible",
        related="period_id.available_amount",
        currency_field="currency_id",
        readonly=True,
    )

    member_count = fields.Integer(
        string="Membres",
        related="period_id.member_count",
        readonly=True,
    )

    paid_member_count = fields.Integer(
        string="Payés",
        related="period_id.paid_member_count",
        readonly=True,
    )

    partial_member_count = fields.Integer(
        string="Paiements partiels",
        related="period_id.partial_member_count",
        readonly=True,
    )

    unpaid_member_count = fields.Integer(
        string="Non payés",
        related="period_id.unpaid_member_count",
        readonly=True,
    )

    recovery_rate = fields.Float(
        string="Taux de recouvrement",
        related="period_id.recovery_rate",
        readonly=True,
    )

    # ==========================================================
    # DÉCISION
    # ==========================================================

    has_beneficiaries = fields.Selection(
        selection=[
            (
                "yes",
                "Oui, il y a un ou plusieurs bénéficiaires",
            ),
            (
                "no",
                "Non, aucun bénéficiaire",
            ),
        ],
        string=(
            "Y a-t-il un ou plusieurs bénéficiaires ?"
        ),
    )

    # ==========================================================
    # DESTINATION TRÉSORERIE
    # ==========================================================

    fund_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte financier de destination",
        domain=(
            "[('company_id', '=', company_id), "
            "('active', '=', True)]"
        ),
    )

    treasury_amount = fields.Monetary(
        string="Montant à approvisionner",
        compute="_compute_treasury_amount",
        currency_field="currency_id",
        readonly=True,
    )

    # ==========================================================
    # LIGNES D'ATTRIBUTION
    # ==========================================================

    allocation_line_ids = fields.One2many(
        comodel_name=(
            "association.subscription."
            "cycle.close.wizard.line"
        ),
        inverse_name="wizard_id",
        string="Attributions",
    )

    existing_allocation_ids = fields.One2many(
        comodel_name="association.subscription.allocation",
        compute="_compute_existing_allocation_ids",
        string="Attributions déjà enregistrées",
        readonly=True,
    )

    # ==========================================================
    # TOTAUX DU WIZARD
    # ==========================================================

    wizard_allocated_amount = fields.Monetary(
        string="Nouvelles attributions",
        compute="_compute_wizard_totals",
        currency_field="currency_id",
    )

    remaining_amount = fields.Monetary(
        string="Reliquat",
        compute="_compute_wizard_totals",
        currency_field="currency_id",
    )

    allocation_complete = fields.Boolean(
        string="Affectation complète",
        compute="_compute_wizard_totals",
    )

    @api.depends(
        "period_id.allocation_ids",
        "period_id.allocation_ids.state",
    )
    def _compute_existing_allocation_ids(self):
        for wizard in self:
            wizard.existing_allocation_ids = (
                wizard.period_id.allocation_ids.filtered(
                    lambda allocation: allocation.state in (
                        "confirmed",
                        "paid",
                    )
                )
            )


    # ==========================================================
    # MONTANT À APPROVISIONNER
    # ==========================================================

    @api.depends(
        "has_beneficiaries",
        "available_amount",
        "wizard_allocated_amount",
    )
    def _compute_treasury_amount(self):

        for wizard in self:

            if wizard.has_beneficiaries == "no":

                wizard.treasury_amount = (
                    wizard.available_amount or 0.0
                )

            elif wizard.has_beneficiaries == "yes":

                wizard.treasury_amount = max(
                    (
                        wizard.available_amount or 0.0
                    )
                    -
                    (
                        wizard.wizard_allocated_amount or 0.0
                    ),
                    0.0,
                )

            else:

                wizard.treasury_amount = 0.0

    # ==========================================================
    # CALCUL DES TOTAUX
    # ==========================================================

    @api.depends(
        "allocation_line_ids",
        "allocation_line_ids.amount",
        "available_amount",
    )
    def _compute_wizard_totals(self):

        for wizard in self:

            wizard_amount = sum(
                wizard.allocation_line_ids.mapped(
                    "amount"
                )
            )

            available_amount = (
                wizard.available_amount or 0.0
            )

            wizard.wizard_allocated_amount = (
                wizard_amount
            )

            wizard.remaining_amount = max(
                available_amount - wizard_amount,
                0.0,
            )

            wizard.allocation_complete = bool(
                available_amount > 0
                and
                abs(
                    available_amount - wizard_amount
                ) < 0.01
            )

    # ==========================================================
    # ONCHANGE DÉCISION
    # ==========================================================

    @api.onchange("has_beneficiaries")
    def _onchange_has_beneficiaries(self):

        for wizard in self:

            if wizard.has_beneficiaries == "no":

                wizard.allocation_line_ids = [
                    (5, 0, 0)
                ]

    
    # ==========================================================
    # APPROVISIONNER LE COMPTE FINANCIER
    # ==========================================================

    def _create_treasury_transaction(self, amount):

        self.ensure_one()

        if amount <= 0:
            return self.env[
                "association.fund.transaction"
            ]

        if self.period_id.state != "running":
            raise ValidationError(
                _(
                    "Le reliquat ne peut être versé que lors de la "
                    "clôture d'un cycle en cours."
                )
            )

        if not self.fund_id:

            raise ValidationError(
                _(
                    "Sélectionnez le compte financier "
                    "qui doit recevoir le montant restant."
                )
            )

        if (
            self.fund_id.company_id
            != self.company_id
        ):

            raise ValidationError(
                _(
                    "Le compte financier sélectionné "
                    "n'appartient pas à la même filiale "
                    "que le cycle de cotisation."
                )
            )

        FundTransaction = self.env["association.fund.transaction"]
        transaction = FundTransaction.search([
            ("origin_model", "=", "association.subscription.period"),
            ("origin_res_id", "=", self.period_id.id),
            ("transaction_type", "=", "in"),
            ("state", "!=", "cancelled"),
        ], limit=1)
        if transaction:
            return transaction

        transaction = FundTransaction.create({
            "company_id":
                self.company_id.id,

            "fund_id":
                self.fund_id.id,

            "transaction_type":
                "in",

            "amount":
                amount,

            "description":
                _(
                    "Approvisionnement cotisation - %(subscription)s - "
                    "%(cycle)s"
                )
                % {
                    "subscription":
                        self.subscription_id.display_name,

                    "cycle":
                        self.period_id.display_name,
                },

            "transaction_date":
                fields.Date.context_today(self),

            "origin_model":
                "association.subscription.period",

            "origin_res_id":
                self.period_id.id,

            "origin_reference":
                self.period_id.display_name,
        })

        transaction.action_validate()

        self.period_id.settled_amount = (
            self.period_id.settled_amount or 0.0
        ) + amount

        if self.meeting_subscription_session_id:
            self.meeting_subscription_session_id.meeting_id.write({
                "pot_settlement_fund_id": self.fund_id.id,
                "pot_settlement_transaction_id": transaction.id,
            })

        return transaction
    
    
    # ==========================================================
    # CONTRÔLE DES ATTRIBUTIONS
    # ==========================================================

    def _check_allocation_lines(self):

        self.ensure_one()

        if not self.allocation_line_ids:

            raise ValidationError(
                _(
                    "Vous avez indiqué qu'il existe "
                    "un ou plusieurs bénéficiaires.\n\n"
                    "Ajoutez au moins une attribution."
                )
            )

        beneficiary_ids = (
            self.allocation_line_ids
            .mapped("beneficiary_id")
            .ids
        )

        if len(beneficiary_ids) != len(
            self.allocation_line_ids
        ):

            raise ValidationError(
                _(
                    "Un même bénéficiaire ne peut pas "
                    "être ajouté plusieurs fois."
                )
            )

        for line in self.allocation_line_ids:

            if not line.beneficiary_id:

                raise ValidationError(
                    _(
                        "Toutes les lignes doivent avoir "
                        "un bénéficiaire."
                    )
                )

            if line.amount <= 0:

                raise ValidationError(
                    _(
                        "Le montant attribué à %(member)s "
                        "doit être strictement supérieur "
                        "à zéro."
                    )
                    % {
                        "member":
                            line.beneficiary_id.display_name,
                    }
                )

        if (
            self.wizard_allocated_amount
            > self.available_amount
        ):

            raise ValidationError(
                _(
                    "Le montant total attribué dépasse "
                    "la cagnotte disponible.\n\n"
                    "Cagnotte disponible : %(available).2f\n"
                    "Montant attribué : %(allocated).2f"
                )
                % {
                    "available":
                        self.available_amount,

                    "allocated":
                        self.wizard_allocated_amount,
                }
            )

        return True
    # ==========================================================
    # CRÉATION DES ATTRIBUTIONS
    # ==========================================================

    def _create_allocations(self):

        self.ensure_one()

        Allocation = self.env[
            "association.subscription.allocation"
        ]

        created_allocations = Allocation

        for line in self.allocation_line_ids:

            allocation = Allocation.create({
                "period_id":
                    self.period_id.id,

                "meeting_subscription_session_id":
                    self.meeting_subscription_session_id.id,

                "beneficiary_id":
                    line.beneficiary_id.id,

                "amount":
                    line.amount,

                "allocation_method":
                    line.allocation_method,

                "decision_note":
                    line.decision_note,
            })

            allocation.action_confirm()

            created_allocations |= allocation

        return created_allocations

    # ==========================================================
    # TERMINER RÉELLEMENT LE CYCLE
    # ==========================================================

    def _finalize_period(self):

        self.ensure_one()

        period = self.period_id
        subscription = self.subscription_id

        period.invalidate_recordset([
            "collected_amount",
            "allocated_amount",
            "available_amount",
            "beneficiary_count",
        ])

        period.modified([
            "collected_amount",
            "allocated_amount",
            "available_amount",
            "beneficiary_count",
        ])

        if period.available_amount > 0.01:

            raise ValidationError(
                _(
                    "Le cycle ne peut pas être terminé.\n\n"
                    "Un montant de %(amount).2f reste "
                    "encore disponible dans la cagnotte."
                )
                % {
                    "amount":
                        period.available_amount,
                }
            )

        period.write({
            "state": "closed",
        })

        subscription.line_ids.write({
            "amount_received": 0.0,
        })

        subscription.invalidate_recordset([
            "current_period_id",
            "period_count",
        ])

        subscription.modified([
            "current_period_id",
            "period_count",
        ])

        subscription.line_ids.invalidate_recordset([
            "amount_due",
            "amount_paid",
            "balance",
            "payment_state",
            "payment_date",
        ])

        subscription.line_ids.modified([
            "amount_due",
            "amount_paid",
            "balance",
            "payment_state",
            "payment_date",
        ])

        period.message_post(
            body=_(
                "Le cycle %(cycle)s a été terminé "
                "après traitement complet de la cagnotte."
            )
            % {
                "cycle":
                    period.display_name,
            }
        )

        return True

    # ==========================================================
    # CONFIRMER ET TERMINER LE CYCLE
    # ==========================================================

    def action_confirm_close(self):

        self.ensure_one()

        period = self.period_id
        subscription = self.subscription_id

        # ======================================================
        # CONTRÔLES GÉNÉRAUX
        # ======================================================

        if not period:

            raise UserError(
                _(
                    "Aucun cycle n'est sélectionné."
                )
            )

        if period.state != "running":

            raise UserError(
                _(
                    "Seul un cycle en cours "
                    "peut être terminé."
                )
            )

        if not self.has_beneficiaries:

            raise ValidationError(
                _(
                    "Indiquez s'il existe ou non "
                    "un bénéficiaire pour ce cycle."
                )
            )

        # Penalties are never part of the distributable pot. Make sure each
        # collected supplement has its dedicated financial transaction before
        # any allocation or treasury settlement is performed.
        period._ensure_penalty_fund_transfers()

        # ======================================================
        # CAS 1
        # BÉNÉFICIAIRES
        # ======================================================

        if self.has_beneficiaries == "yes":

            self._check_allocation_lines()

            # --------------------------------------------------
            # CRÉATION DES ATTRIBUTIONS
            # --------------------------------------------------

            self._create_allocations()

            # --------------------------------------------------
            # RECALCUL DU CYCLE
            # --------------------------------------------------

            period.invalidate_recordset([
                "allocated_amount",
                "available_amount",
                "beneficiary_count",
            ])

            period.modified([
                "allocated_amount",
                "available_amount",
                "beneficiary_count",
            ])

            # --------------------------------------------------
            # RELIQUAT
            # --------------------------------------------------

            remaining_amount = (
                period.available_amount or 0.0
            )

            if remaining_amount > 0.01:

                self._create_treasury_transaction(
                    remaining_amount
                )

        # ======================================================
        # CAS 2
        # AUCUN BÉNÉFICIAIRE
        # ======================================================

        elif self.has_beneficiaries == "no":

            amount_to_transfer = (
                period.available_amount or 0.0
            )

            if amount_to_transfer > 0.01:

                self._create_treasury_transaction(
                    amount_to_transfer
                )

        # A cycle can only be locked once every collected amount has either
        # been attributed or transferred to the financial account chosen in
        # this assistant.  This protects against closing a session with a
        # residual temporary cash balance.
        period.invalidate_recordset(["available_amount", "settled_amount"])
        if (period.available_amount or 0.0) > 0.01:
            raise ValidationError(
                _(
                    "Le reliquat de la caisse temporaire doit être attribué "
                    "ou versé sur le compte financier sélectionné avant la clôture."
                )
            )

        # ======================================================
        # CLÔTURE DU CYCLE
        # ======================================================

        period.write({
            "state": "closed",
        })

        if self.meeting_subscription_session_id:
            self.meeting_subscription_session_id.action_mark_closed()

        # ======================================================
        # NETTOYAGE DU MONTANT DE SAISIE
        # ======================================================

        subscription.line_ids.write({
            "amount_received": 0.0,
        })

        # ======================================================
        # ACTUALISATION DE LA COTISATION
        # ======================================================

        subscription.invalidate_recordset([
            "current_period_id",
            "period_count",
        ])

        subscription.modified([
            "current_period_id",
            "period_count",
        ])

        subscription.line_ids.invalidate_recordset([
            "amount_due",
            "amount_paid",
            "balance",
            "payment_state",
            "payment_date",
        ])

        subscription.line_ids.modified([
            "amount_due",
            "amount_paid",
            "balance",
            "payment_state",
            "payment_date",
        ])

        # ======================================================
        # MESSAGE
        # ======================================================

        period.message_post(
            body=_(
                "Le cycle %(cycle)s a été terminé.\n\n"
                "Montant collecté : %(collected).2f\n"
                "Pénalités reversées (non attribuables) : "
                "%(penalties).2f\n"
                "Montant attribué : %(allocated).2f\n"
                "Montant transféré en trésorerie : "
                "%(treasury).2f"
            )
            % {
                "cycle":
                    period.display_name,

                "collected":
                    period.collected_amount,

                "penalties":
                    period.penalty_collected_amount,

                "allocated":
                    period.allocated_amount,

                "treasury":
                    self.treasury_amount,
            }
        )

        # ======================================================
        # RETOUR SUR LA RÉUNION
        # ======================================================

        if self.meeting_subscription_session_id:
            next_action = {
                "type": "ir.actions.client",
                "tag": "primetech_refresh_subscription_table",
                "params": {
                    "subscription_id": subscription.id,
                    "meeting_id": self.meeting_subscription_session_id.meeting_id.id,
                    "origin": "meeting",
                    "close_dialog": True,
                },
            }
        else:
            next_action = {
                "type": "ir.actions.act_window",
                "name": subscription.display_name,
                "res_model": "association.subscription",
                "res_id": subscription.id,
                # This action is nested in display_notification.params.next.
                # Nested actions are not normalized by the server action
                # endpoint, so the web client requires an explicit views
                # array when it preprocesses the action.
                "views": [[False, "form"]],
                "target": "current",
            }

        if period.penalty_collected_amount > 0:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Pénalités reversées"),
                    "message": _(
                        "%(amount).2f %(currency)s de pénalités ont été "
                        "exclus de la cagnotte attribuable et reversés sur "
                        "le compte des pénalités."
                    ) % {
                        "amount": period.penalty_collected_amount,
                        "currency": period.currency_id.name or "",
                    },
                    "type": "success",
                    "sticky": True,
                    "next": next_action,
                },
            }
        return next_action

    # ==============================================================
    # LIGNE D'ATTRIBUTION DU WIZARD
    # ==============================================================


    class AssociationSubscriptionCycleCloseWizardLine(
        models.TransientModel
    ):

        _name = (
            "association.subscription."
            "cycle.close.wizard.line"
        )

        _description = (
            "Ligne d'attribution de clôture "
            "d'un cycle de cotisation"
        )

        # ==========================================================
        # WIZARD
        # ==========================================================

        wizard_id = fields.Many2one(
            comodel_name=(
                "association.subscription."
                "cycle.close.wizard"
            ),
            string="Assistant",
            required=True,
            ondelete="cascade",
        )

        period_id = fields.Many2one(
            comodel_name="association.subscription.period",
            related="wizard_id.period_id",
            readonly=True,
        )

        subscription_id = fields.Many2one(
            comodel_name="association.subscription",
            related="wizard_id.subscription_id",
            readonly=True,
        )

        currency_id = fields.Many2one(
            comodel_name="res.currency",
            related="wizard_id.currency_id",
            readonly=True,
        )

        # ==========================================================
        # BÉNÉFICIAIRE
        # ==========================================================

        beneficiary_id = fields.Many2one(
            comodel_name="association.member",
            string="Bénéficiaire",
            required=True,
            domain=[
                ("active", "=", True),
            ],
        )

        # ==========================================================
        # ATTRIBUTION
        # ==========================================================

        amount = fields.Monetary(
            string="Montant attribué",
            currency_field="currency_id",
            required=True,
            default=0.0,
        )

        allocation_method = fields.Selection(
            selection=[
                ("rotation", "Rotation"),
                ("planned", "Ordre planifié"),
                (
                    "meeting_decision",
                    "Décision de la réunion",
                ),
                ("draw", "Tirage au sort"),
                ("priority", "Besoin prioritaire"),
                ("other", "Autre"),
            ],
            string="Mode d'attribution",
            required=True,
            default="meeting_decision",
        )

        decision_note = fields.Char(
            string="Observation",
        )

        # ==========================================================
        # CONTRÔLE
        # ==========================================================

        @api.constrains("amount")
        def _check_amount(self):

            for line in self:

                if line.amount < 0:

                    raise ValidationError(
                        _(
                            "Le montant attribué "
                            "ne peut pas être négatif."
                        )
                    )

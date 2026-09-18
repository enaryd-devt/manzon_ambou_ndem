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


class AssociationPaymentSurplusWizard(models.TransientModel):
    _name = "association.payment.surplus.wizard"
    _description = "Traitement du surplus de paiement"

    # ==========================================================
    # PAIEMENT
    # ==========================================================

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement",
        required=True,
        readonly=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        related="payment_id.member_id",
        readonly=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="payment_id.company_id",
        readonly=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="payment_id.currency_id",
        readonly=True,
    )

    # ==========================================================
    # MONTANTS
    # ==========================================================

    payment_amount = fields.Monetary(
        string="Montant reçu",
        currency_field="currency_id",
        related="payment_id.amount",
        readonly=True,
    )

    allocated_amount = fields.Monetary(
        string="Montant affecté aux cotisations",
        currency_field="currency_id",
        related="payment_id.allocated_amount",
        readonly=True,
    )

    surplus_amount = fields.Monetary(
        string="Surplus disponible",
        currency_field="currency_id",
        compute="_compute_surplus_amount",
        readonly=True,
    )

    # ==========================================================
    # TRAITEMENT
    # ==========================================================

    payment_wizard_id = fields.Many2one(
        comodel_name="association.subscription.payment.wizard",
        string="Assistant de paiement d'origine",
        readonly=True,
        ondelete="set null",
    )
    
    surplus_action = fields.Selection(
        selection=[
            (
                "member_account",
                "Approvisionner le compte du membre",
            ),
            (
                "refund",
                "Rembourser le membre",
            ),
        ],
        string="Traitement du surplus",
        required=True,
        default="member_account",
    )

    note = fields.Text(
        string="Observation",
    )

    # ==========================================================
    # CALCUL DU SURPLUS
    # ==========================================================

    @api.depends(
        "payment_id.amount",
        "payment_id.allocated_amount",
    )
    def _compute_surplus_amount(self):
        for record in self:
            if not record.payment_id:
                record.surplus_amount = 0.0
                continue

            record.surplus_amount = max(
                (
                    record.payment_id.amount
                    - record.payment_id.allocated_amount
                ),
                0.0,
            )

    def action_process_surplus(self):
        self.ensure_one()

        payment = self.payment_id

        # ==========================================================
        # CONTRÔLES
        # ==========================================================

        if not payment:
            raise UserError(
                _("Aucun paiement n'est associé.")
            )

        if not self.member_id:
            raise ValidationError(
                _("Aucun membre n'est associé au paiement.")
            )

        if self.surplus_amount <= 0:
            raise ValidationError(
                _("Aucun surplus positif n'est disponible.")
            )

        if not self.surplus_action:
            raise ValidationError(
                _(
                    "Veuillez sélectionner le traitement "
                    "à appliquer au surplus."
                )
            )

        # ==========================================================
        # TRAITEMENT DU SURPLUS
        # ==========================================================

        if self.surplus_action == "member_account":

            self._credit_member_account(
                self.surplus_amount
            )

        elif self.surplus_action == "refund":

            self._refund_member(
                self.surplus_amount
            )

        else:

            raise ValidationError(
                _(
                    "Le traitement du surplus sélectionné "
                    "n'est pas valide."
                )
            )

        # ==========================================================
        # INVALIDATION DU PAIEMENT
        # ==========================================================

        payment.invalidate_recordset([
            "allocated_amount",
        ])

        payment.modified([
            "allocated_amount",
        ])

        # ==========================================================
        # ACTUALISATION DES COTISATIONS
        # ==========================================================

        if hasattr(
            payment,
            "_invalidate_subscription_lines",
        ):

            payment._invalidate_subscription_lines()

        # ==========================================================
        # INVALIDATION DES LIGNES DE COTISATION
        # ==========================================================

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        subscription_lines = SubscriptionLine.search([
            (
                "member_id",
                "=",
                self.member_id.id,
            ),
        ])

        if subscription_lines:

            fields_to_refresh = [
                field_name
                for field_name in [
                    "amount_paid",
                    "balance",
                    "payment_state",
                    "payment_date",
                ]
                if field_name in SubscriptionLine._fields
            ]

            if fields_to_refresh:

                subscription_lines.invalidate_recordset(
                    fields_to_refresh
                )

                subscription_lines.modified(
                    fields_to_refresh
                )

        # ==========================================================
        # MESSAGE DE TRAÇABILITÉ
        # ==========================================================

        payment.message_post(
            body=_(
                "Le surplus de %(amount).2f %(currency)s "
                "a été traité avec succès."
            )
            % {
                "amount":
                    self.surplus_amount,

                "currency":
                    self.currency_id.name or "",
            }
        )

        # ==========================================================
        # FERMETURE DU WIZARD
        # ==========================================================

        return {
            "type": "ir.actions.act_window_close",
        }


    # ==========================================================
    # CRÉDITER LE COMPTE MEMBRE
    # ==========================================================

    def _credit_member_account(self, amount):
        self.ensure_one()

        MemberAccount = self.env[
            "association.member.account"
        ]

        AccountTransaction = self.env[
            "association.member.account.transaction"
        ]

        # ======================================================
        # CONTRÔLES
        # ======================================================

        if amount <= 0:
            raise ValidationError(
                _(
                    "Le montant à créditer doit être "
                    "strictement supérieur à zéro."
                )
            )

        if not self.member_id:
            raise ValidationError(
                _("Aucun membre n'est défini.")
            )

        if not self.company_id:
            raise ValidationError(
                _("Aucune filiale n'est définie.")
            )

        # ======================================================
        # CONTRÔLE DU DOUBLE CRÉDIT
        # ======================================================

        existing_transaction = AccountTransaction.search(
            [
                (
                    "payment_id",
                    "=",
                    self.payment_id.id,
                ),
            ],
            limit=1,
        )

        if existing_transaction:
            raise ValidationError(
                _(
                    "Le surplus de ce paiement a déjà été "
                    "affecté au compte du membre."
                )
            )

        # ======================================================
        # RECHERCHE DU COMPTE MEMBRE
        # ======================================================

        member_account = MemberAccount.search(
            [
                (
                    "member_id",
                    "=",
                    self.member_id.id,
                ),
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
            ],
            limit=1,
        )

        # ======================================================
        # CRÉATION AUTOMATIQUE DU COMPTE
        # ======================================================

        if not member_account:
            member_account = MemberAccount.create({
                "member_id": self.member_id.id,
            })

        # ======================================================
        # CRÉATION DU MOUVEMENT
        # ======================================================

        transaction = AccountTransaction.create({
            "account_id":
                member_account.id,

            "transaction_type":
                "credit",

            "amount":
                amount,

            "transaction_date":
                fields.Date.context_today(self),

            "payment_id":
                self.payment_id.id,

            "origin_type":
                "payment_surplus",

            "origin_model":
                "association.payment",

            "origin_res_id":
                self.payment_id.id,

            "origin_reference":
                self.payment_id.display_name,

            "description":
                _(
                    "Surplus du paiement %(payment)s"
                )
                % {
                    "payment":
                        self.payment_id.display_name,
                },
        })

        # ======================================================
        # VALIDATION DU MOUVEMENT
        # ======================================================

        transaction.action_validate()

        # ======================================================
        # MESSAGE
        # ======================================================

        self.payment_id.message_post(
            body=_(
                "Le surplus de %(amount).2f %(currency)s "
                "a été crédité sur le compte du membre "
                "%(member)s."
            )
            % {
                "amount":
                    amount,

                "currency":
                    self.currency_id.name or "",

                "member":
                    self.member_id.display_name,
            }
        )

        return member_account

    # ==========================================================
    # REMBOURSER LE MEMBRE
    # ==========================================================

    def _refund_member(self, amount):
        self.ensure_one()

        if amount <= 0:
            raise ValidationError(
                _(
                    "Le montant à rembourser doit être "
                    "strictement supérieur à zéro."
                )
            )

        self.payment_id.message_post(
            body=_(
                "Le surplus de %(amount).2f %(currency)s "
                "a été remboursé au membre %(member)s."
            )
            % {
                "amount":
                    amount,

                "currency":
                    self.currency_id.name or "",

                "member":
                    self.member_id.display_name,
            }
        )

        return True

    def action_confirm(self):
        self.ensure_one()

        payment = self.payment_id.exists()

        if not payment:
            raise UserError(
                _("Aucun paiement n'est associé à cet assistant.")
            )

        if payment.surplus_processed:
            raise UserError(
                _("Le surplus de ce paiement a déjà été traité.")
            )

        # ==========================================================
        # CONTRÔLE DU SURPLUS
        # ==========================================================

        if self.surplus_amount <= 0:
            raise ValidationError(
                _("Aucun surplus positif n'est disponible.")
            )

        # ==========================================================
        # RÉCUPÉRER LES LIGNES DE COTISATION AVANT TRAITEMENT
        # ==========================================================

        payment.invalidate_recordset([
            "line_ids",
            "state",
        ])

        subscription_lines = (
            payment.line_ids
            .mapped("subscription_line_id")
            .exists()
        )

        subscriptions = (
            subscription_lines
            .mapped("subscription_id")
            .exists()
        )

        # ==========================================================
        # RÉCUPÉRER LA LIGNE PRINCIPALE
        # ==========================================================

        subscription_line = (
            subscription_lines[:1]
            if subscription_lines
            else False
        )

        subscription = (
            subscription_line.subscription_id
            if subscription_line
            else False
        )

        # ==========================================================
        # RÉCUPÉRER LA RÉUNION
        # ==========================================================

        meeting = False

        if "meeting_id" in payment._fields:
            meeting = payment.meeting_id

        # ==========================================================
        # TRAITEMENT : CRÉDITER LE COMPTE MEMBRE
        # ==========================================================

        if self.surplus_action == "member_account":

            MemberAccount = self.env[
                "association.member.account"
            ]

            AccountTransaction = self.env[
                "association.member.account.transaction"
            ]

            member_account = MemberAccount.search(
                [
                    (
                        "member_id",
                        "=",
                        self.member_id.id,
                    ),
                    (
                        "company_id",
                        "=",
                        payment.company_id.id,
                    ),
                ],
                limit=1,
            )

            # ======================================================
            # CRÉATION DU COMPTE MEMBRE
            # ======================================================

            if not member_account:

                member_account = MemberAccount.create({
                    "member_id":
                        self.member_id.id,

                    "company_id":
                        payment.company_id.id,
                })

            # ======================================================
            # CRÉATION DE LA TRANSACTION
            # ======================================================

            transaction = AccountTransaction.create({
                "account_id":
                    member_account.id,

                "transaction_type":
                    "credit",

                "amount":
                    self.surplus_amount,

                "transaction_date":
                    fields.Datetime.now(),

                "payment_id":
                    payment.id,

                "description":
                    _(
                        "Surplus du paiement %(payment)s "
                        "crédité au compte du membre %(member)s"
                    )
                    % {
                        "payment":
                            payment.display_name,

                        "member":
                            self.member_id.display_name,
                    },
            })

            # ======================================================
            # VALIDATION TRANSACTION
            # ======================================================

            if hasattr(
                transaction,
                "action_validate",
            ):

                transaction.action_validate()

            elif hasattr(
                transaction,
                "action_post",
            ):

                transaction.action_post()

            elif hasattr(
                transaction,
                "action_confirm",
            ):

                transaction.action_confirm()

            # ======================================================
            # MESSAGE
            # ======================================================

            payment.message_post(
                body=_(
                    "Surplus de %(amount).2f %(currency)s "
                    "crédité au compte du membre %(member)s."
                )
                % {
                    "amount":
                        self.surplus_amount,

                    "currency":
                        self.currency_id.name or "",

                    "member":
                        self.member_id.display_name,
                }
            )

        # ==========================================================
        # TRAITEMENT : REMBOURSEMENT
        # ==========================================================

        elif self.surplus_action == "refund":

            payment.message_post(
                body=_(
                    "Surplus de %(amount).2f %(currency)s "
                    "remboursé au membre %(member)s."
                )
                % {
                    "amount":
                        self.surplus_amount,

                    "currency":
                        self.currency_id.name or "",

                    "member":
                        self.member_id.display_name,
                }
            )

        else:

            raise ValidationError(
                _(
                    "Veuillez sélectionner le traitement "
                    "à appliquer au surplus."
                )
            )

        # ==========================================================
        # MARQUER LE SURPLUS COMME TRAITÉ
        #
        # IMPORTANT :
        # on l'écrit réellement sur le paiement.
        # ==========================================================

        if "surplus_processed" in payment._fields:

            payment.write({
                "surplus_processed": True,
                "processed_surplus_amount": self.surplus_amount,
                "surplus_action": self.surplus_action,
                "refund_amount": (
                    self.surplus_amount
                    if self.surplus_action == "refund"
                    else 0.0
                ),
            })

        # ==========================================================
        # RELECTURE DU PAIEMENT
        # ==========================================================

        self.env.flush_all()

        payment.invalidate_recordset([
            "state",
            "line_ids",
            "allocated_amount",
        ])

        # ==========================================================
        # FINALISER LE PAIEMENT
        # ==========================================================

        if payment.state == "draft":

            payment.action_collect()

            self.env.flush_all()

            payment.invalidate_recordset([
                "state",
            ])

        if payment.state == "collected":

            action = payment.with_context(
                surplus_processed=True,
            ).action_confirm()

            # ======================================================
            # RELECTURE DU PAIEMENT
            # ======================================================

            self.env.flush_all()

            payment.invalidate_recordset([
                "state",
                "line_ids",
                "allocated_amount",
            ])

            # ======================================================
            # CONTRÔLE FINAL
            # ======================================================

            if payment.state != "confirmed":

                raise ValidationError(
                    _(
                        "Le paiement n'a pas pu être finalisé.\n\n"
                        "État actuel : %(state)s"
                    )
                    % {
                        "state":
                            payment.state,
                    }
                )

            # ======================================================
            # REPRENDRE LE WIZARD DE PAIEMENT D'ORIGINE
            # ======================================================

            payment_wizard = (
                self.payment_wizard_id.exists()
            )

            if payment_wizard:
                if not payment_wizard.payment_id:
                    payment_wizard.payment_id = payment.id

                return (
                    payment_wizard
                    .action_resume_after_surplus()
                )

            # ======================================================
            # FALLBACK
            # ======================================================

            return {
                "type":
                    "ir.actions.act_window_close",
            }


            # ======================================================
            # NE PAS RETOURNER UNE NOUVELLE ACTION SURPLUS
            # ======================================================

            if isinstance(action, dict):

                payment.invalidate_recordset([
                    "state",
                ])

        # ==========================================================
        # RELECTURE APRÈS VALIDATION
        # ==========================================================

        self.env.flush_all()

        payment.invalidate_recordset([
            "state",
            "line_ids",
            "allocated_amount",
        ])

        # ==========================================================
        # CONTRÔLE FINAL
        # ==========================================================

        if payment.state != "confirmed":

            raise ValidationError(
                _(
                    "Le paiement n'a pas pu être finalisé.\n\n"
                    "État actuel : %(state)s"
                )
                % {
                    "state":
                        payment.state,
                }
            )

        # ==========================================================
        # ACTUALISER LES LIGNES DE COTISATION
        # ==========================================================

        self.env.flush_all()

        for line in subscription_lines:

            refresh_fields = [
                field_name
                for field_name in (
                    "payment_line_ids",
                    "amount_due",
                    "amount_paid",
                    "balance",
                    "payment_state",
                    "payment_date",
                )
                if field_name in line._fields
            ]

            if refresh_fields:

                line.invalidate_recordset(
                    refresh_fields
                )

            # ======================================================
            # RECALCUL RÉEL
            # ======================================================

            if hasattr(
                line,
                "_refresh_after_payment",
            ):

                line._refresh_after_payment()

            elif hasattr(
                line,
                "_compute_current_cycle_payment",
            ):

                line._compute_current_cycle_payment()

            # ======================================================
            # SIGNALER LES MODIFICATIONS
            # ======================================================

            modified_fields = [
                field_name
                for field_name in (
                    "amount_paid",
                    "balance",
                    "payment_state",
                    "payment_date",
                )
                if field_name in line._fields
            ]

            if modified_fields:

                line.modified(
                    modified_fields
                )

        # ==========================================================
        # ACTUALISER LES COTISATIONS PARENTES
        # ==========================================================

        for current_subscription in subscriptions:

            current_subscription.invalidate_recordset()

            for method_name in (
                "_compute_statistics",
                "_compute_payment_count",
                "_compute_financial_amounts",
                "_compute_payment_statistics",
            ):

                if hasattr(
                    current_subscription,
                    method_name,
                ):

                    getattr(
                        current_subscription,
                        method_name,
                    )()

        # ==========================================================
        # FLUSH FINAL
        # ==========================================================

        self.env.flush_all()

        # ==========================================================
        # RAFRAÎCHISSEMENT DU TABLEAU PARENT
        #
        # MÊME ACTION QUE LE WIZARD DE PAIEMENT NORMAL
        # ==========================================================

        return {
            "type":
                "ir.actions.client",

            "tag":
                "primetech_refresh_subscription_table",

            "params": {
                "subscription_id": (
                    subscription.id
                    if subscription
                    else False
                ),

                "subscription_line_id": (
                    subscription_line.id
                    if subscription_line
                    else False
                ),

                "field_name":
                    "line_ids",

                "origin": (
                    "meeting"
                    if meeting
                    else "subscription"
                ),

                "meeting_id": (
                    meeting.id
                    if meeting
                    else False
                ),
            },
        }

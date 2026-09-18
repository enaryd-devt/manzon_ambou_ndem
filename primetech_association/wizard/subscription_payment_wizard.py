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


class AssociationSubscriptionPaymentWizard(models.TransientModel):
    _name = "association.subscription.payment.wizard"
    _description = "Paiement rapide d'une cotisation"

    # ==========================================================
    # ORIGINE
    # ==========================================================

    origin = fields.Selection(
        selection=[
            ("subscription", "Cotisation"),
            ("meeting", "Réunion"),
        ],
        string="Origine",
        required=True,
        readonly=True,
        default="subscription",
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        readonly=True,
    )

    # ==========================================================
    # COTISATION
    # ==========================================================

    subscription_line_id = fields.Many2one(
        comodel_name="association.subscription.line",
        string="Cotisation du membre",
        required=True,
        readonly=True,
    )

    subscription_id = fields.Many2one(
        related="subscription_line_id.subscription_id",
        string="Cotisation",
        readonly=True,
    )

    # ==========================================================
    # CYCLE
    # ==========================================================

    period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle",
        readonly=True,
    )

    # ==========================================================
    # RÉUNION
    # ==========================================================

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion",
        readonly=True,
    )

    # ==========================================================
    # DEVISE
    # ==========================================================

    currency_id = fields.Many2one(
        related="subscription_line_id.currency_id",
        readonly=True,
    )

    # ==========================================================
    # SITUATION FINANCIÈRE
    # ==========================================================

    amount_due = fields.Monetary(
        string="Montant dû",
        currency_field="currency_id",
        readonly=True,
    )

    amount_paid = fields.Monetary(
        string="Déjà payé",
        currency_field="currency_id",
        readonly=True,
    )

    balance = fields.Monetary(
        string="Reste à payer",
        currency_field="currency_id",
        readonly=True,
    )

    # ==========================================================
    # PAIEMENT
    # ==========================================================

    amount_received = fields.Monetary(
        string="Montant reçu",
        currency_field="currency_id",
        required=True,
    )

    payment_method = fields.Selection(
        selection=[
            ("cash", "Espèces"),
            ("bank", "Banque"),
            ("mobile_money", "Mobile Money"),
            ("other", "Autre"),
        ],
        string="Mode de paiement",
        required=True,
        default="cash",
    )

    receipt_account_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte de versement",
        readonly=True,
    )

    payment_reference = fields.Char(
        string="Référence",
    )

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement généré",
        readonly=True,
    )

    # ==========================================================
    # DEFAULT GET
    # ==========================================================

    @api.model
    def default_get(self, fields_list):

        values = super().default_get(fields_list)

        subscription_line_id = self.env.context.get(
            "default_subscription_line_id"
        )

        if not subscription_line_id:
            return values

        subscription_line = self.env[
            "association.subscription.line"
        ].browse(
            subscription_line_id
        )

        if not subscription_line.exists():
            return values

        subscription = (
            subscription_line.subscription_id
        )

        # ======================================================
        # PREMIER CYCLE NON SOLDÉ
        # ======================================================

        PaymentLine = self.env[
            "association.payment.line"
        ]

        requested_period_id = (
            self.env.context.get(
                "default_subscription_period_id"
            )
            or self.env.context.get(
                "default_period_id"
            )
        )

        period = self.env[
            "association.subscription.period"
        ]

        if requested_period_id:

            requested_period = period.browse(
                requested_period_id
            ).exists()

            if (
                requested_period
                and requested_period.subscription_id == subscription
                and requested_period.company_id
                == subscription_line.company_id
                and requested_period.state
                in (
                    "running",
                    "closed",
                )
            ):

                period = requested_period

        if not period:

            periods = PaymentLine._get_unsettled_periods_for_line(
                subscription_line
            )

            period = periods[:1]

        if not period:

            raise ValidationError(
                _(
                    "Aucun cycle en cours ou terminé avec "
                    "un solde restant n'a été trouvé pour "
                    "la cotisation %(subscription)s."
                )
                % {
                    "subscription":
                        subscription.display_name,
                }
            )

        # ======================================================
        # RECALCUL
        # ======================================================

        amount_due = PaymentLine._get_period_due_for_line(
            subscription_line,
            period,
        )

        amount_paid = PaymentLine._get_period_paid_for_line(
            subscription_line,
            period,
        )

        balance = max(
            amount_due - amount_paid,
            0.0,
        )

        # ======================================================
        # VALEURS
        # ======================================================

        default_amount_received = self.env.context.get(
            "default_amount_received"
        )

        amount_received = (
            balance
            if default_amount_received in (
                None,
                False,
            )
            else min(
                max(
                    default_amount_received
                    or 0.0,
                    0.0,
                ),
                balance,
            )
        )

        values.update(
            {
                "member_id":
                    subscription_line.member_id.id,

                "subscription_line_id":
                    subscription_line.id,

                "period_id":
                    period.id,

                "amount_due":
                    amount_due,

                "amount_paid":
                    amount_paid,

                "balance":
                    balance,

                "amount_received":
                    amount_received,

                "receipt_account_id":
                    subscription.receipt_account_id.id,

                "origin":
                    self.env.context.get(
                        "default_origin",
                        "subscription",
                    ),

                "meeting_id":
                    self.env.context.get(
                        "default_meeting_id",
                    ),
            }
        )

        return values

    # ==========================================================
    # ACTUALISER LA LIGNE DE COTISATION
    # ==========================================================

    def _refresh_subscription_data(self):

        self.ensure_one()

        subscription_line = (
            self.subscription_line_id
        )

        if not subscription_line:
            return True

        # ======================================================
        # VIDER LE CACHE ORM
        # ======================================================

        self.env.flush_all()

        subscription_line.invalidate_recordset()

        # ======================================================
        # RECALCULER LA LIGNE
        # ======================================================

        subscription_line._compute_current_cycle_payment()

        # ======================================================
        # CHAMPS MODIFIÉS
        # ======================================================

        subscription_line.modified(
            [
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ]
        )

        # ======================================================
        # COTISATION
        # ======================================================

        subscription = (
            subscription_line.subscription_id
        )

        if subscription:

            subscription.invalidate_recordset()

            statistics_fields = [
                field_name
                for field_name in (
                    "line_count",
                    "paid_member_count",
                    "partial_member_count",
                    "unpaid_member_count",
                    "total_amount_due",
                    "total_amount_paid",
                    "total_balance",
                    "progress_percent",
                    "payment_count",
                )
                if field_name in subscription._fields
            ]

            if statistics_fields:

                subscription.modified(
                    statistics_fields
                )

        # ======================================================
        # CYCLE
        # ======================================================

        period = self.period_id

        if period:

            period.invalidate_recordset()

            period_fields = [
                field_name
                for field_name in (
                    "collected_amount",
                    "allocated_amount",
                    "available_amount",
                    "member_count",
                    "paid_member_count",
                    "partial_member_count",
                    "unpaid_member_count",
                    "recovery_rate",
                )
                if field_name in period._fields
            ]

            if period_fields:

                period.modified(
                    period_fields
                )

        # ======================================================
        # FLUSH FINAL
        # ======================================================

        self.env.flush_all()

        return True
    
    # ==========================================================
    # CRÉER LE MOUVEMENT DU COMPTE DE VERSEMENT
    # ==========================================================

    
  
    
    def _refresh_payment_subscription_lines(self, payment):
        self.ensure_one()

        if not payment:
            return True

        # ==========================================================
        # FLUSH ORM
        # ==========================================================

        self.env.flush_all()

        # ==========================================================
        # RECHARGER LES AFFECTATIONS DU PAIEMENT
        # ==========================================================

        payment.invalidate_recordset([
            "line_ids",
            "allocated_amount",
        ])

        payment_lines = payment.line_ids

        if not payment_lines:
            return True

        # ==========================================================
        # RÉCUPÉRER TOUTES LES LIGNES DE COTISATION AFFECTÉES
        # ==========================================================

        subscription_lines = payment_lines.mapped(
            "subscription_line_id"
        ).exists()

        if not subscription_lines:
            return True

        # ==========================================================
        # INVALIDATION DES LIGNES
        # ==========================================================

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
            if field_name
            in self.env[
                "association.subscription.line"
            ]._fields
        ]

        if refresh_fields:
            subscription_lines.invalidate_recordset(
                refresh_fields
            )

        # ==========================================================
        # RECALCUL INDIVIDUEL
        #
        # IMPORTANT :
        # on recalcule chaque ligne réellement affectée
        # ==========================================================

        for subscription_line in subscription_lines:

            if hasattr(
                subscription_line,
                "_compute_current_cycle_payment",
            ):
                subscription_line._compute_current_cycle_payment()

        # ==========================================================
        # SIGNALER LES CHAMPS MODIFIÉS
        # ==========================================================

        modified_fields = [
            field_name
            for field_name in (
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            )
            if field_name
            in self.env[
                "association.subscription.line"
            ]._fields
        ]

        if modified_fields:
            subscription_lines.modified(
                modified_fields
            )

        # ==========================================================
        # ACTUALISER LES COTISATIONS PARENTES
        # ==========================================================

        subscriptions = subscription_lines.mapped(
            "subscription_id"
        ).exists()

        subscription_fields = [
            field_name
            for field_name in (
                "line_count",
                "paid_member_count",
                "partial_member_count",
                "unpaid_member_count",
                "total_amount_due",
                "total_amount_paid",
                "total_balance",
                "progress_percent",
                "payment_count",
            )
            if field_name
            in self.env[
                "association.subscription"
            ]._fields
        ]

        if subscriptions:

            if subscription_fields:

                subscriptions.invalidate_recordset(
                    subscription_fields
                )

                subscriptions.modified(
                    subscription_fields
                )

        # ==========================================================
        # ACTUALISER LES CYCLES
        # ==========================================================

        periods = subscription_lines.mapped(
            "subscription_id.current_period_id"
        ).exists()

        period_fields = [
            field_name
            for field_name in (
                "collected_amount",
                "allocated_amount",
                "available_amount",
                "member_count",
                "paid_member_count",
                "partial_member_count",
                "unpaid_member_count",
                "recovery_rate",
            )
            if field_name
            in self.env[
                "association.subscription.period"
            ]._fields
        ]

        if periods:

            if period_fields:

                periods.invalidate_recordset(
                    period_fields
                )

                periods.modified(
                    period_fields
                )

        # ==========================================================
        # FLUSH FINAL
        # ==========================================================

        self.env.flush_all()

        return True
    
    # ==========================================================
    # ACTION - VALIDER LE PAIEMENT
    # ==========================================================

    def action_validate_payment(self):
        self.ensure_one()

        amount_received = self.amount_received or 0.0
        if amount_received <= 0:
            raise ValidationError(
                _("Le montant reçu doit être strictement supérieur à zéro.")
            )

        subscription_line = self.subscription_line_id.exists()
        if not subscription_line:
            raise ValidationError(_("Aucune cotisation n'est sélectionnée."))

        subscription = subscription_line.subscription_id
        member = subscription_line.member_id

        if not subscription:
            raise ValidationError(
                _("Aucune cotisation n'est associée à la ligne du membre.")
            )
        if not member:
            raise ValidationError(
                _("Aucun membre n'est associé à la ligne de cotisation.")
            )

        # ======================================================
        # CYCLE À RÉGLER
        # ======================================================

        PaymentLine = self.env[
            "association.payment.line"
        ]

        period = self.period_id

        if not period:

            period = PaymentLine._get_unsettled_periods_for_line(
                subscription_line
            )[:1]

        if (
            period
            and period.state not in (
                "running",
                "closed",
            )
        ):
            period = False

        if (
            period
            and period.subscription_id != subscription
        ):
            period = False

        if (
            period
            and period.company_id != subscription_line.company_id
        ):
            period = False

        if not period:
            raise ValidationError(
                _(
                    "Aucun cycle en cours ou terminé avec "
                    "un solde restant n'a été trouvé pour la cotisation "
                    "%(subscription)s."
                )
                % {"subscription": subscription.display_name}
            )

        self.period_id = period
        self.member_id = member
        self.receipt_account_id = False

        # ======================================================
        # RECALCUL AVANT PAIEMENT
        # ======================================================

        self.env.flush_all()

        amount_due = PaymentLine._get_period_due_for_line(
            subscription_line,
            period,
        )

        amount_paid = PaymentLine._get_period_paid_for_line(
            subscription_line,
            period,
        )

        remaining_due = max(
            amount_due - amount_paid,
            0.0,
        )
        if remaining_due <= 0:
            raise ValidationError(
                _(
                    "La cotisation du membre %(member)s est déjà "
                    "entièrement payée pour le cycle %(period)s."
                )
                % {
                    "member": member.display_name,
                    "period": period.display_name,
                }
            )

        allocated_amount = min(amount_received, remaining_due)
        surplus_amount = max(amount_received - allocated_amount, 0.0)

        # ======================================================
        # CRÉATION DU PAIEMENT ET DE L'AFFECTATION
        # ======================================================

        payment_values = {
            "member_id": member.id,
            "payment_date": fields.Date.context_today(self),
            "amount": amount_received,
            "payment_source": (
                "meeting_cash" if self.meeting_id else "external"
            ),
            "has_allocations": True,
            # Le compte de versement est choisi uniquement pendant la
            # clôture du cycle. Il ne fait pas partie de l'encaissement.
            "receipt_account_id": False,
            "payment_method": self.payment_method or "cash",
            "payment_reference": (
                self.payment_reference
                or _(
                    "Paiement cotisation %(subscription)s - %(period)s"
                )
                % {
                    "subscription": subscription.display_name,
                    "period": period.display_name,
                }
            ),
            "company_id": subscription_line.company_id.id,
            "state": "draft",
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "subscription_line_id": subscription_line.id,
                        "subscription_id": subscription.id,
                        "subscription_period_id": period.id,
                        "amount_paid": allocated_amount,
                    },
                ),
            ],
        }

        Payment = self.env["association.payment"]

        if "subscription_period_id" in Payment._fields:
            payment_values["subscription_period_id"] = period.id

        if self.meeting_id and "meeting_id" in Payment._fields:
            payment_values["meeting_id"] = self.meeting_id.id

        payment = Payment.create(payment_values)
        self.payment_id = payment.id
        self.env.flush_all()

        payment.invalidate_recordset(["line_ids", "state"])

        payment_line = payment.line_ids.filtered(
            lambda line:
                line.subscription_line_id.id == subscription_line.id
        )[:1]

        if not payment_line:
            raise ValidationError(
                _(
                    "Erreur technique : l'affectation n'est pas reliée "
                    "à la cotisation courante du membre."
                )
            )

        if (payment_line.amount_paid or 0.0) <= 0:
            raise ValidationError(
                _("Erreur technique : le montant affecté est nul.")
            )

        # ======================================================
        # ENCAISSEMENT ET VALIDATION
        # ======================================================

        if payment.state == "draft":
            payment.action_collect()

        payment.invalidate_recordset(["state"])

        if payment.state != "collected":
            raise ValidationError(
                _(
                    "Le paiement n'a pas pu être encaissé. "
                    "État actuel : %(state)s"
                )
                % {"state": payment.state}
            )

        # ======================================================
        # ENCAISSEMENT
        # ======================================================

        if payment.state == "draft":

            payment.action_collect()

        self.env.flush_all()

        payment.invalidate_recordset([
            "state",
            "line_ids",
            "allocated_amount",
        ])

        # ======================================================
        # CONTRÔLE ENCAISSEMENT
        # ======================================================

        if payment.state != "collected":

            raise ValidationError(
                _(
                    "Le paiement n'a pas pu être encaissé.\n\n"
                    "État actuel : %(state)s"
                )
                % {
                    "state":
                        payment.state,
                }
            )

        # ======================================================
        # VALIDATION
        # ======================================================

        action = payment.action_confirm()

        # ======================================================
        # IMPORTANT : SURPLUS
        #
        # action_confirm() retourne une action lorsqu'un
        # traitement complémentaire est nécessaire.
        #
        # Dans le cas du surplus :
        #
        # state = collected
        #
        # C'EST NORMAL.
        #
        # Le wizard de surplus terminera la validation.
        # ======================================================

        if isinstance(action, dict):
            if (
                action.get("res_model")
                == "association.payment.surplus.wizard"
            ):
                context = dict(
                    action.get("context")
                    or {}
                )
                context[
                    "default_payment_wizard_id"
                ] = self.id
                action[
                    "context"
                ] = context

            return action

        # ======================================================
        # PAIEMENT SANS SURPLUS
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
                    "Le paiement n'a pas pu être validé.\n\n"
                    "État actuel : %(state)s"
                )
                % {
                    "state":
                        payment.state,
                }
            )

        # Le mouvement financier est centralisé dans
        # association.payment.action_confirm(). En réunion, aucun
        # compte financier n'est mouvementé avant le règlement final
        # de la caisse temporaire.

        # ======================================================
        # RECALCUL CENTRALISÉ DE LA LIGNE
        # ======================================================

        if hasattr(subscription_line, "_refresh_after_payment"):
            subscription_line._refresh_after_payment()
        else:
            subscription_line.invalidate_recordset([
                "payment_line_ids",
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])
            subscription_line._compute_current_cycle_payment()
            subscription_line.modified([
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])
            self.env.flush_all()

        # ======================================================
        # RECALCUL DES AGRÉGATS
        # ======================================================

        self._refresh_payment_subscription_lines(payment)

        self.env[
            "association.member.subscription.cycle.report"
        ]._refresh_open_reports_for_payment(payment)

        subscription.invalidate_recordset()
        if hasattr(subscription, "_compute_statistics"):
            subscription._compute_statistics()
        if hasattr(subscription, "_compute_payment_count"):
            subscription._compute_payment_count()

        period.invalidate_recordset()
        for method_name in (
            "_compute_financial_amounts",
            "_compute_payment_statistics",
            "_compute_statistics",
        ):
            if hasattr(period, method_name):
                getattr(period, method_name)()

        self.env.flush_all()

        # ======================================================
        # SURPLUS
        # ======================================================

        if surplus_amount > 0:

            SurplusWizard = self.env[
                "association.payment.surplus.wizard"
            ]

            surplus_values = {
                "payment_id":
                    payment.id,
            }

            # ==================================================
            # WIZARD DE PAIEMENT D'ORIGINE
            # ==================================================

            if "payment_wizard_id" in SurplusWizard._fields:

                surplus_values["payment_wizard_id"] = self.id

            # ==================================================
            # MEMBRE
            # ==================================================

            if "member_id" in SurplusWizard._fields:

                surplus_values["member_id"] = member.id

            # ==================================================
            # MONTANT REÇU
            # ==================================================

            if "received_amount" in SurplusWizard._fields:

                surplus_values["received_amount"] = (
                    amount_received
                )

            if "payment_amount" in SurplusWizard._fields:

                surplus_values["payment_amount"] = (
                    amount_received
                )

            # ==================================================
            # MONTANT AFFECTÉ
            # ==================================================

            if "allocated_amount" in SurplusWizard._fields:

                surplus_values["allocated_amount"] = (
                    allocated_amount
                )

            # ==================================================
            # SURPLUS
            # ==================================================

            if "surplus_amount" in SurplusWizard._fields:

                surplus_values["surplus_amount"] = (
                    surplus_amount
                )

            # ==================================================
            # CRÉATION DU WIZARD SURPLUS
            # ==================================================

            surplus_wizard = SurplusWizard.create(
                surplus_values
            )

            # ==================================================
            # OUVERTURE
            # ==================================================

            return {
                "type":
                    "ir.actions.act_window",

                "name":
                    _("Gestion du surplus"),

                "res_model":
                    "association.payment.surplus.wizard",

                "res_id":
                    surplus_wizard.id,

                "view_mode":
                    "form",

                "target":
                    "new",
            }

        # ======================================================
        # RAFRAÎCHISSEMENT DU TABLEAU PARENT
        # ======================================================

        self.amount_received = 0.0

        return {
            "type": "ir.actions.client",
            "tag": "primetech_refresh_subscription_table",
            "params": {
                "subscription_id": subscription.id,
                "subscription_line_id": subscription_line.id,
                "field_name": "line_ids",
                "origin": self.origin,
                "meeting_id": (
                    self.meeting_id.id
                    if self.meeting_id
                    else False
                ),
            },
        }
    
    # ==========================================================
    # REPRISE APRÈS TRAITEMENT DU SURPLUS
    # ==========================================================

    def action_resume_after_surplus(self):
        self.ensure_one()

        # ======================================================
        # PAIEMENT
        # ======================================================

        payment = self.payment_id.exists()

        if not payment:

            raise ValidationError(
                _(
                    "Le paiement associé au traitement "
                    "du surplus est introuvable."
                )
            )

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
        # CONTRÔLE
        # ======================================================

        if payment.state != "confirmed":

            raise ValidationError(
                _(
                    "Le paiement n'est pas encore validé.\n\n"
                    "État actuel : %(state)s"
                )
                % {
                    "state":
                        payment.state,
                }
            )

        # ======================================================
        # LIGNE DE COTISATION
        # ======================================================

        subscription_line = self.subscription_line_id

        if not subscription_line:

            subscription_lines = (
                payment.line_ids
                .mapped("subscription_line_id")
                .exists()
            )

            subscription_line = (
                subscription_lines[:1]
                if subscription_lines
                else False
            )

        # ======================================================
        # COTISATION
        # ======================================================

        subscription = (
            subscription_line.subscription_id
            if subscription_line
            else self.subscription_id
        )

        # ======================================================
        # CYCLE
        # ======================================================

        period = (
            subscription.current_period_id
            if subscription
            else False
        )

        # ======================================================
        # RECALCUL DE LA LIGNE
        # ======================================================

        if subscription_line:

            if hasattr(
                subscription_line,
                "_refresh_after_payment",
            ):

                subscription_line._refresh_after_payment()

            else:

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
                    if field_name
                    in subscription_line._fields
                ]

                if refresh_fields:

                    subscription_line.invalidate_recordset(
                        refresh_fields
                    )

                if hasattr(
                    subscription_line,
                    "_compute_current_cycle_payment",
                ):

                    subscription_line._compute_current_cycle_payment()

                modified_fields = [
                    field_name
                    for field_name in (
                        "amount_paid",
                        "balance",
                        "payment_state",
                        "payment_date",
                    )
                    if field_name
                    in subscription_line._fields
                ]

                if modified_fields:

                    subscription_line.modified(
                        modified_fields
                    )

        # ======================================================
        # RECALCUL CENTRALISÉ
        #
        # ON REPREND EXACTEMENT LE HELPER DU WIZARD PAIEMENT
        # ======================================================

        self._refresh_payment_subscription_lines(
            payment
        )

        self.env[
            "association.member.subscription.cycle.report"
        ]._refresh_open_reports_for_payment(payment)

        # ======================================================
        # COTISATION
        # ======================================================

        if subscription:

            subscription.invalidate_recordset()

            if hasattr(
                subscription,
                "_compute_statistics",
            ):

                subscription._compute_statistics()

            if hasattr(
                subscription,
                "_compute_payment_count",
            ):

                subscription._compute_payment_count()

        # ======================================================
        # CYCLE
        # ======================================================

        if period:

            period.invalidate_recordset()

            for method_name in (
                "_compute_financial_amounts",
                "_compute_payment_statistics",
                "_compute_statistics",
            ):

                if hasattr(
                    period,
                    method_name,
                ):

                    getattr(
                        period,
                        method_name,
                    )()

        # ======================================================
        # FLUSH FINAL
        # ======================================================

        self.env.flush_all()

        # ======================================================
        # RÉINITIALISER LE MONTANT DU WIZARD
        # ======================================================

        self.amount_received = 0.0

        # ======================================================
        # RAFRAÎCHISSEMENT NORMAL DU TABLEAU
        #
        # EXACTEMENT COMME action_validate_payment()
        # ======================================================

        return {
            "type":
                "ir.actions.client",

            "tag":
                "primetech_refresh_subscription_table",

            "params": {
                "subscription_id":
                    (
                        subscription.id
                        if subscription
                        else False
                    ),

                "subscription_line_id":
                    (
                        subscription_line.id
                        if subscription_line
                        else False
                    ),

                "field_name":
                    "line_ids",

                "origin":
                    self.origin,

                "meeting_id":
                    (
                        self.meeting_id.id
                        if self.meeting_id
                        else False
                    ),
            },
        }

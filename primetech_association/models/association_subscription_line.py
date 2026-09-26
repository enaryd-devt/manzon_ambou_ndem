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


from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationSubscriptionLine(models.Model):
    _name = "association.subscription.line"
    _description = "Membre participant à une cotisation"
    _order = "member_id, id"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="subscription_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="subscription_id.currency_id",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # COTISATION
    # ==========================================================

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        required=True,
        ondelete="cascade",
        index=True,
    )

    subscription_state = fields.Selection(
        related="subscription_id.state",
        string="Statut de la cotisation",
        store=True,
        readonly=True,
    )

    subscription_type = fields.Selection(
        related="subscription_id.subscription_type",
        string="Type de cotisation",
        store=True,
        readonly=True,
    )

    current_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle courant",
        related="subscription_id.current_period_id",
        readonly=True,
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        ondelete="restrict",
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        store=True,
        readonly=True,
    )

    image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo du membre",
        readonly=True,
    )

    category_id = fields.Many2one(
        comodel_name="association.member.category",
        related="member_id.category_id",
        string="Catégorie",
        store=True,
        readonly=True,
    )

    function_id = fields.Many2one(
        comodel_name="association.member.function",
        related="member_id.function_id",
        string="Fonction",
        store=True,
        readonly=True,
    )

    phone = fields.Char(
        related="member_id.phone",
        string="Téléphone",
        readonly=True,
    )

    # ==========================================================
    # MONTANT DU CYCLE COURANT
    # ==========================================================

    amount_due = fields.Monetary(
        string="Montant dû",
        currency_field="currency_id",
        compute="_compute_current_cycle_payment",
        store=True,
    )

    amount_paid = fields.Monetary(
        string="Montant payé",
        currency_field="currency_id",
        compute="_compute_current_cycle_payment",
        store=True,
    )

    balance = fields.Monetary(
        string="Reste à payer",
        currency_field="currency_id",
        compute="_compute_current_cycle_payment",
        store=True,
    )

    payment_state = fields.Selection(
        selection=[
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État du paiement",
        compute="_compute_current_cycle_payment",
        store=True,
        index=True,
    )

    payment_date = fields.Date(
        string="Date du dernier paiement",
        compute="_compute_current_cycle_payment",
        store=True,
    )

    cycle_amount_due = fields.Monetary(
        string="Montant dû du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_amount_paid = fields.Monetary(
        string="Montant payé du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_base_amount_due = fields.Monetary(
        string="Cotisation due du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_contribution_paid_amount = fields.Monetary(
        string="Cotisation payée du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_subscription_balance_amount = fields.Monetary(
        string="Reste cotisation du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_balance = fields.Monetary(
        string="Reste du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_payment_state = fields.Selection(
        selection=[
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État du cycle",
        compute="_compute_cycle_report_values",
    )

    cycle_penalty_amount = fields.Monetary(
        string="Pénalité du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_penalty_paid_amount = fields.Monetary(
        string="Pénalité payée du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_penalty_balance_amount = fields.Monetary(
        string="Reste pénalité du cycle",
        currency_field="currency_id",
        compute="_compute_cycle_report_values",
    )

    cycle_is_late = fields.Boolean(
        string="En retard",
        compute="_compute_cycle_report_values",
    )

    cycle_late_days = fields.Integer(
        string="Jours de retard",
        compute="_compute_cycle_report_values",
    )

    cycle_last_payment_date = fields.Date(
        string="Dernier paiement du cycle",
        compute="_compute_cycle_report_values",
    )

    amount_received = fields.Monetary(
        string="Montant reçu",
        currency_field="currency_id",
        default=0.0,
        copy=False,
    )


    # ==========================================================
    # COMPTE DE VERSEMENT
    # ==========================================================

    receipt_account_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte de versement",
        domain="["
            "('company_id', '=', company_id), "
            "('active', '=', True)"
            "]",
        copy=False,
    )

    # ==========================================================
    # PAIEMENTS
    # ==========================================================

    payment_line_ids = fields.One2many(
        comodel_name="association.payment.line",
        inverse_name="subscription_line_id",
        string="Lignes de paiement",
        readonly=True,
    )

    # ==========================================================
    # COMPTE FINANCIER DU MEMBRE
    # ==========================================================

    member_account_balance = fields.Monetary(
        string="Solde compte membre",
        currency_field="currency_id",
        compute="_compute_member_account_balance",
    )
    has_member_account = fields.Boolean(
        string="Compte membre disponible", compute="_compute_member_account_balance",
    )

    temporary_member_account_balance = fields.Monetary(
        string="Solde temporaire du compte",
        currency_field="currency_id",
        compute="_compute_temporary_member_account_balance",
        help="Solde disponible après déduction des règlements de réunion en attente de validation finale.",
    )

    @api.depends(
        "member_account_balance",
        "payment_line_ids.amount_paid",
        "payment_line_ids.payment_id.state",
        "payment_line_ids.payment_id.defer_member_account_debit",
    )
    def _compute_temporary_member_account_balance(self):
        for line in self:
            deferred_amount = sum(line.payment_line_ids.filtered(
                lambda payment_line: payment_line.payment_id.state == "confirmed"
                and payment_line.payment_id.defer_member_account_debit
            ).mapped("amount_paid"))
            line.temporary_member_account_balance = max(
                (line.member_account_balance or 0.0) - deferred_amount,
                0.0,
            )

    # ==========================================================
    # PÉNALITÉ DU MEMBRE
    # ==========================================================

    penalty_amount = fields.Monetary(
        string="Pénalité",
        currency_field="currency_id",
        default=0.0,
        readonly=True,
    )

    penalty_applied = fields.Boolean(
        string="Pénalité appliquée",
        default=False,
        readonly=True,
    )

    penalty_date = fields.Date(
        string="Date de pénalité",
        readonly=True,
    )

    penalty_reason = fields.Char(
        string="Motif de pénalité",
        readonly=True,
    )

    penalty_deadline = fields.Date(
        string="Date limite",
        compute="_compute_penalty_deadline",
    )

    penalty_grace_days_remaining = fields.Integer(
        string="Grâce restante (jours)",
        compute="_compute_penalty_grace_days_remaining",
        help=(
            "Compteur individuel calculé depuis l'échéance du cycle. "
            "La pénalité est appliquée dès qu'il atteint zéro."
        ),
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
            "association_subscription_line_member_unique",
            "unique(subscription_id, member_id)",
            "Un membre ne peut participer qu'une seule fois "
            "à la même cotisation.",
        ),
    ]

    @api.depends(
        "subscription_id.amount",
        "subscription_id.current_period_id",
        "subscription_id.current_period_id.period_start_date",
        "subscription_id.current_period_id.period_end_date",
        "penalty_amount",
        "payment_line_ids",
        "payment_line_ids.amount_paid",
        "payment_line_ids.payment_id",
        "payment_line_ids.payment_id.state",
        "payment_line_ids.payment_id.payment_date",
        "payment_line_ids.payment_id.subscription_period_id",
        "payment_line_ids.subscription_period_id",
    )
    def _compute_current_cycle_payment(self):

        PaymentLine = self.env[
            "association.payment.line"
        ]

        for record in self:

            amount_due = 0.0
            amount_paid = 0.0
            payment_date = False

            subscription = record.subscription_id

            # ======================================================
            # RECHERCHE DU CYCLE RÉELLEMENT ACTIF
            # ======================================================

            period = self.env[
                "association.subscription.period"
            ].search(
                [
                    (
                        "subscription_id",
                        "=",
                        subscription.id,
                    ),
                    (
                        "state",
                        "=",
                        "running",
                    ),
                    (
                        "company_id",
                        "=",
                        record.company_id.id,
                    ),
                ],
                order="sequence desc, id desc",
                limit=1,
            )

            # ======================================================
            # AUCUN CYCLE ACTIF
            # ======================================================

            if not period:

                record.amount_due = 0.0
                record.amount_paid = 0.0
                record.balance = 0.0
                record.payment_date = False
                record.payment_state = "not_paid"

                continue

            # ======================================================
            # MONTANT DÛ
            # ======================================================

            amount_due = (
                subscription.amount or 0.0
            ) + (record.penalty_amount or 0.0)

            # ======================================================
            # DOMAINE DE RECHERCHE DES AFFECTATIONS
            # ======================================================

            domain = [
                (
                    "subscription_line_id",
                    "=",
                    record.id,
                ),
                (
                    "payment_id.state",
                    "=",
                    "confirmed",
                ),
            ]

            # ======================================================
            # FILTRAGE PAR CYCLE RÉEL
            # ======================================================

            domain += [
                "|",
                ("subscription_period_id", "=", period.id),
                "&",
                ("subscription_period_id", "=", False),
                ("payment_id.subscription_period_id", "=", period.id),
            ]

            # ======================================================
            # RECHERCHE DIRECTE
            # ======================================================

            payment_lines = PaymentLine.search(
                domain
            )

            # ======================================================
            # MONTANT PAYÉ
            # ======================================================

            amount_paid = sum(
                payment_lines.mapped(
                    "amount_paid"
                )
            )

            # ======================================================
            # DATE DU DERNIER PAIEMENT
            # ======================================================

            payment_dates = [
                payment.payment_date
                for payment
                in payment_lines.mapped(
                    "payment_id"
                )
                if payment.payment_date
            ]

            if payment_dates:

                payment_date = max(
                    payment_dates
                )

            # ======================================================
            # RESTE À PAYER
            # ======================================================

            balance = max(
                amount_due - amount_paid,
                0.0,
            )

            # ======================================================
            # AFFECTATION
            # ======================================================

            record.amount_due = amount_due

            record.amount_paid = amount_paid

            record.balance = balance

            record.payment_date = payment_date

            # ======================================================
            # ÉTAT DU PAIEMENT
            # ======================================================

            if amount_paid <= 0:

                record.payment_state = (
                    "not_paid"
                )

            elif amount_paid < amount_due:

                record.payment_state = (
                    "partial"
                )

            else:

                record.payment_state = (
                    "paid"
                )

    @api.depends_context("subscription_period_report_id")
    @api.depends(
        "subscription_id.amount",
        "subscription_id.current_period_id",
        "penalty_amount",
        "payment_line_ids",
        "payment_line_ids.amount_paid",
        "payment_line_ids.payment_id",
        "payment_line_ids.payment_id.state",
        "payment_line_ids.payment_id.payment_date",
        "payment_line_ids.payment_id.subscription_period_id",
        "payment_line_ids.subscription_period_id",
    )
    def _compute_cycle_report_values(self):

        PaymentLine = self.env[
            "association.payment.line"
        ]

        Period = self.env[
            "association.subscription.period"
        ]

        context_period_id = self.env.context.get(
            "subscription_period_report_id"
        )

        context_period = (
            Period.browse(context_period_id).exists()
            if context_period_id
            else Period
        )

        for record in self:

            period = context_period

            if (
                not period
                or period.subscription_id
                != record.subscription_id
            ):

                period = record.subscription_id.current_period_id

            record.cycle_amount_due = 0.0
            record.cycle_amount_paid = 0.0
            record.cycle_base_amount_due = 0.0
            record.cycle_contribution_paid_amount = 0.0
            record.cycle_subscription_balance_amount = 0.0
            record.cycle_balance = 0.0
            record.cycle_payment_state = "not_paid"
            record.cycle_penalty_amount = 0.0
            record.cycle_penalty_paid_amount = 0.0
            record.cycle_penalty_balance_amount = 0.0
            record.cycle_is_late = False
            record.cycle_late_days = 0
            record.cycle_last_payment_date = False

            if not period:
                continue

            amount_due = PaymentLine._get_period_due_for_line(
                record,
                period,
            )

            amount_paid = PaymentLine._get_period_paid_for_line(
                record,
                period,
            )

            breakdown = PaymentLine._get_period_amount_breakdown_for_line(
                record,
                period,
                current_amount=0.0,
                already_paid=amount_paid,
            )

            payment_lines = PaymentLine.search(
                [
                    (
                        "subscription_line_id",
                        "=",
                        record.id,
                    ),
                    (
                        "payment_id.state",
                        "=",
                        "confirmed",
                    ),
                    "|",
                    (
                        "subscription_period_id",
                        "=",
                        period.id,
                    ),
                    "&",
                    (
                        "subscription_period_id",
                        "=",
                        False,
                    ),
                    (
                        "payment_id.subscription_period_id",
                        "=",
                        period.id,
                    ),
                ]
            )

            payment_dates = [
                payment.payment_date
                for payment in payment_lines.mapped("payment_id")
                if payment.payment_date
            ]

            last_payment_date = (
                max(payment_dates)
                if payment_dates
                else False
            )

            balance = max(
                amount_due - amount_paid,
                0.0,
            )

            today = fields.Date.context_today(record)

            late_days = (
                max(
                    (
                        (
                            last_payment_date
                            or today
                        )
                        - period.due_date
                    ).days,
                    0,
                )
                if period.due_date
                else 0
            )

            record.cycle_amount_due = amount_due
            record.cycle_amount_paid = amount_paid
            record.cycle_base_amount_due = breakdown[
                "base_amount_due"
            ]
            record.cycle_contribution_paid_amount = breakdown[
                "contribution_paid_amount"
            ]
            record.cycle_subscription_balance_amount = breakdown[
                "subscription_balance_amount"
            ]
            record.cycle_balance = balance
            record.cycle_penalty_amount = breakdown[
                "penalty_due_amount"
            ]
            record.cycle_penalty_paid_amount = breakdown[
                "penalty_paid_amount"
            ]
            record.cycle_penalty_balance_amount = breakdown[
                "penalty_balance_amount"
            ]
            record.cycle_last_payment_date = last_payment_date
            record.cycle_late_days = late_days
            record.cycle_is_late = bool(
                late_days > 0
            )

            if amount_paid <= 0:

                record.cycle_payment_state = "not_paid"

            elif balance > 0.01:

                record.cycle_payment_state = "partial"

            else:

                record.cycle_payment_state = "paid"

    def _refresh_after_payment(self):

        lines = self.exists()

        if not lines:
            return True

        # ======================================================
        # FLUSH COMPLET
        # ======================================================

        self.env.flush_all()

        # ======================================================
        # INVALIDATION DU CACHE
        # ======================================================

        lines.invalidate_recordset()

        # ======================================================
        # RECALCUL DES LIGNES
        # ======================================================

        lines._compute_current_cycle_payment()

        # ======================================================
        # CHAMPS RECALCULÉS
        # ======================================================

        modified_fields = [
            field_name
            for field_name in (
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            )
            if field_name in lines._fields
        ]

        if modified_fields:

            lines.modified(
                modified_fields
            )

        # ======================================================
        # COTISATIONS PARENTES
        # ======================================================

        subscriptions = lines.mapped(
            "subscription_id"
        ).exists()

        if subscriptions:

            subscriptions.invalidate_recordset()

            if hasattr(
                subscriptions,
                "_compute_statistics",
            ):

                subscriptions._compute_statistics()

            if hasattr(
                subscriptions,
                "_compute_payment_count",
            ):

                subscriptions._compute_payment_count()

        # ======================================================
        # CYCLES ACTIFS
        # ======================================================

        periods = self.env[
            "association.subscription.period"
        ].search(
            [
                (
                    "subscription_id",
                    "in",
                    subscriptions.ids,
                ),
                (
                    "state",
                    "=",
                    "running",
                ),
            ]
        )

        if periods:

            periods.invalidate_recordset()

            for method_name in (
                "_compute_financial_amounts",
                "_compute_payment_statistics",
                "_compute_statistics",
            ):

                if hasattr(
                    periods,
                    method_name,
                ):

                    getattr(
                        periods,
                        method_name,
                    )()

        # ======================================================
        # FLUSH FINAL
        # ======================================================

        self.env.flush_all()

        return True

    # ==========================================================
    # DATE LIMITE DE PAIEMENT
    # ==========================================================

    @api.depends(
        "subscription_id.current_period_id.due_date",
        "subscription_id.penalty_grace_days",
    )
    def _compute_penalty_deadline(self):

        for line in self:

            line.penalty_deadline = False

            period = (
                line.subscription_id.current_period_id
            )

            if not period or not period.due_date:
                continue

            grace_days = (
                line.subscription_id.penalty_grace_days
                or 0
            )

            line.penalty_deadline = (
                period.due_date
                + timedelta(days=grace_days)
            )

    @api.depends("penalty_deadline", "penalty_applied")
    def _compute_penalty_grace_days_remaining(self):
        today = fields.Date.context_today(self)
        for line in self:
            if line.penalty_applied or not line.penalty_deadline:
                line.penalty_grace_days_remaining = 0
            else:
                line.penalty_grace_days_remaining = max(
                    (line.penalty_deadline - today).days,
                    0,
                )
        

    # ==========================================================
    # APPLIQUER LA PÉNALITÉ
    # ==========================================================

    def _apply_late_penalty(self, force=False):

        today = fields.Date.context_today(self)

        for line in self:

            subscription = line.subscription_id

            if not subscription.penalty_enabled:
                continue

            if line.penalty_applied:
                continue

            if not line.penalty_deadline:
                continue

            if not force and today < line.penalty_deadline:
                continue

            if line.payment_state == "paid":
                continue

            penalty_amount = subscription._calculate_penalty_amount(line.balance)

            if penalty_amount <= 0:
                continue

            period = subscription.current_period_id

            line.write(
                {
                    "penalty_amount":
                        penalty_amount,

                    "penalty_applied":
                        True,

                    "penalty_date":
                        today,

                    "penalty_reason":
                        _(
                            "Pénalité appliquée après "
                            "dépassement du délai de grâce."
                        ),
                }
            )

            if period:
                self.env[
                    "association.subscription.penalty.recap"
                ]._sync_for_line_period(
                    line,
                    period,
                )

        self._compute_current_cycle_payment()
        return True

    @api.model
    def _cron_apply_due_penalties(self):
        today = fields.Date.context_today(self)
        lines = self.search([
            ("subscription_id.state", "=", "running"),
            ("subscription_id.penalty_enabled", "=", True),
            ("penalty_applied", "=", False),
        ])
        overdue_lines = lines.filtered(
            lambda line: line.penalty_deadline
            and line.penalty_deadline <= today
            and line.payment_state != "paid"
        )
        overdue_lines._apply_late_penalty()
        periods = overdue_lines.mapped(
            "subscription_id.current_period_id"
        ).exists()
        if periods:
            periods._apply_late_penalty()
        return True

    # ==========================================================
    # SOLDE DU COMPTE MEMBRE
    # ==========================================================

    @api.depends("member_id", "company_id")
    def _compute_member_account_balance(self):
        Account = self.env[
            "association.member.account"
        ]

        for record in self:
            record.member_account_balance = 0.0
            record.has_member_account = False

            if not record.member_id:
                continue

            account = Account.search(
                [
                    (
                        "member_id",
                        "=",
                        record.member_id.id,
                    ),
                    (
                        "company_id",
                        "=",
                        record.company_id.id,
                    ),
                ],
                limit=1,
            )

            if account:
                record.has_member_account = True
                record.member_account_balance = (
                    account.balance or 0.0
                )

    # ==========================================================
    # CONTRÔLE DU CYCLE DE PAIEMENT
    # ==========================================================

    def _check_payment_cycle(self):
        self.ensure_one()

        subscription = self.subscription_id

        if not subscription:
            raise UserError(
                _(
                    "Aucune cotisation n'est associée "
                    "à cette ligne."
                )
            )

        # ======================================================
        # RECHERCHE DIRECTE DU CYCLE EN COURS
        #
        # IMPORTANT :
        # Ne pas dépendre uniquement de current_period_id.
        # On recherche directement dans la base.
        # ======================================================

        period = self.env[
            "association.subscription.period"
        ].search(
            [
                (
                    "subscription_id",
                    "=",
                    subscription.id,
                ),
                (
                    "state",
                    "=",
                    "running",
                ),
            ],
            order="sequence desc, id desc",
            limit=1,
        )

        if not period:
            raise UserError(
                _(
                    "Aucun cycle de cotisation en cours "
                    "n'a été trouvé pour %(subscription)s."
                )
                % {
                    "subscription":
                        subscription.display_name,
                }
            )

        # ======================================================
        # CONTRÔLE DU PAIEMENT DU MEMBRE
        # ======================================================

        if self.payment_state == "paid":
            raise ValidationError(
                _(
                    "Le membre %(member)s a déjà réglé "
                    "sa cotisation pour le cycle %(cycle)s."
                )
                % {
                    "member":
                        self.member_id.display_name,

                    "cycle":
                        period.display_name,
                }
            )

        if self.balance <= 0:
            raise ValidationError(
                _(
                    "Cette cotisation ne présente "
                    "aucun reste à payer."
                )
            )

        return period



    def action_create_payment(self):

        self.ensure_one()

        meeting_id = self.env.context.get("default_meeting_id")

        return {
            "type": "ir.actions.act_window",
            "name": _("Encaissement global du membre") if meeting_id else _("Paiement de cotisation"),
            "res_model":
                "association.subscription.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_origin":
                    "meeting" if meeting_id else "subscription",

                "default_subscription_line_id":
                    self.id,

                "default_meeting_id": meeting_id or False,
            },
        }   
    # ==========================================================
    # PAYER DEPUIS LE COMPTE MEMBRE
    # ==========================================================

    def action_pay_from_member_account(self):
        self.ensure_one()

        if not self.env.context.get("skip_member_account_confirmation"):
            wizard = self.env[
                "association.member.account.subscription.payment.wizard"
            ].create({"subscription_line_id": self.id})
            return {
                "type": "ir.actions.act_window",
                "name": _("Utiliser le compte membre"),
                "res_model": wizard._name,
                "res_id": wizard.id,
                "view_mode": "form",
                "target": "new",
            }

        MemberAccount = self.env[
            "association.member.account"
        ]

        Payment = self.env[
            "association.payment"
        ]

        PaymentLine = self.env[
            "association.payment.line"
        ]

        # ======================================================
        # CONTRÔLES
        # ======================================================

        if not self.exists():
            raise ValidationError(
                _(
                    "La ligne de cotisation n'existe plus."
                )
            )

        if not self.member_id:
            raise ValidationError(
                _(
                    "Aucun membre n'est associé "
                    "à cette ligne de cotisation."
                )
            )

        if not self.subscription_id:
            raise ValidationError(
                _(
                    "Aucune cotisation n'est associée "
                    "à cette ligne."
                )
            )

        # ======================================================
        # CYCLE À RÉGLER
        # ======================================================

        period = PaymentLine._get_unsettled_periods_for_line(
            self
        )[:1]

        if not period:
            raise ValidationError(
                _(
                    "Aucun cycle en cours ou terminé avec "
                    "un solde restant n'a été trouvé pour "
                    "la cotisation %(subscription)s."
                )
                % {
                    "subscription":
                        self.subscription_id.display_name,
                }
            )

        # ======================================================
        # RECALCUL AVANT PAIEMENT
        # ======================================================

        self.env.flush_all()

        amount_due = PaymentLine._get_period_due_for_line(
            self,
            period,
        )

        amount_paid = PaymentLine._get_period_paid_for_line(
            self,
            period,
        )

        # ======================================================
        # MONTANT À PAYER
        # ======================================================

        amount_to_pay = max(
            amount_due - amount_paid,
            0.0,
        )

        if amount_to_pay <= 0:
            raise ValidationError(
                _(
                    "La cotisation de %(member)s est déjà "
                    "entièrement payée pour le cycle %(period)s."
                )
                % {
                    "member":
                        self.member_id.display_name,

                    "period":
                        period.display_name,
                }
            )

        # ======================================================
        # COMPTE MEMBRE
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
                (
                    "active",
                    "=",
                    True,
                ),
            ],
            limit=1,
        )

        if not member_account:
            raise ValidationError(
                _(
                    "Le membre %(member)s ne possède pas "
                    "de compte financier actif."
                )
                % {
                    "member":
                        self.member_id.display_name,
                }
            )

        # ======================================================
        # SOLDE DU COMPTE
        # ======================================================

        member_account.invalidate_recordset(
            [
                "balance",
                "total_credit",
                "total_debit",
            ]
        )

        available_balance = (
            member_account.balance or 0.0
        )

        if available_balance <= 0:
            raise ValidationError(
                _(
                    "Le compte membre ne dispose d'aucun solde disponible."
                )
            )

        # A member-account payment can settle only the available amount.  The
        # remaining balance stays due and the line becomes ``partial`` after
        # confirmation, exactly like an external partial payment.
        amount_to_pay = min(amount_to_pay, available_balance)

        # ======================================================
        # DATE DU PAIEMENT
        # ======================================================

        payment_date = fields.Date.context_today(self)

        # When this action is triggered from a meeting, keep the payment in
        # the exact session/cycle displayed by that meeting.  Without these
        # links the payment is confirmed but is ignored by the cycle and
        # session statistics, so the table keeps showing an unpaid member.
        meeting = self.env["association.meeting"].browse(
            self.env.context.get("default_meeting_id")
        ).exists()
        session = meeting.subscription_session_ids.filtered(
            lambda item: item.subscription_id == self.subscription_id
            and item.period_id == period
        )[:1] if meeting else self.env["association.meeting.subscription.session"]

        # ======================================================
        # CRÉATION DU PAIEMENT
        #
        # IMPORTANT :
        # LA LIGNE D'AFFECTATION EST CRÉÉE DIRECTEMENT
        # DANS line_ids
        # ======================================================

        payment = Payment.create(
            {
                "member_id":
                    self.member_id.id,

                "payment_date":
                    payment_date,

                "amount":
                    amount_to_pay,

                "payment_source":
                    "member_account",

                "member_account_id":
                    member_account.id,

                "meeting_id": self.env.context.get(
                    "default_meeting_id"
                ),

                "meeting_subscription_session_id": session.id,

                "subscription_period_id": period.id,

                "defer_member_account_debit": bool(session),

                "has_allocations":
                    True,

                "payment_method":
                    "bank",

                "payment_reference":
                    _(
                        "Paiement compte membre - "
                        "%(subscription)s - %(period)s"
                    )
                    % {
                        "subscription":
                            self.subscription_id.display_name,

                        "period":
                            period.display_name,
                    },

                "company_id":
                    self.company_id.id,

                # ==================================================
                # CRÉATION DIRECTE DE L'AFFECTATION
                # ==================================================

                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "subscription_line_id":
                                self.id,

                            "subscription_id":
                                self.subscription_id.id,

                            "subscription_period_id":
                                period.id,

                            "amount_paid":
                                amount_to_pay,
                        },
                    ),
                ],
            }
        )

        # ======================================================
        # FLUSH DU PAIEMENT ET DES LIGNES
        # ======================================================

        self.env.flush_all()

        # ======================================================
        # RÉCUPÉRATION DE LA LIGNE DEPUIS LE PAIEMENT
        #
        # NE PLUS FAIRE PaymentLine.search(...)
        # ======================================================

        payment.invalidate_recordset(
            [
                "line_ids",
            ]
        )

        payment_lines = payment.line_ids

        if not payment_lines:
            raise ValidationError(
                _(
                    "Erreur technique : aucune ligne "
                    "d'affectation n'a été créée sur le paiement."
                )
            )

        # ======================================================
        # RECHERCHE DANS LES LIGNES DU PAIEMENT
        # ======================================================

        payment_line = payment_lines.filtered(
            lambda line:
                line.subscription_line_id.id == self.id
        )[:1]

        if not payment_line:
            raise ValidationError(
                _(
                    "Erreur technique : la ligne d'affectation "
                    "créée n'est pas reliée à la cotisation "
                    "du membre."
                )
            )

        if (
            payment_line.amount_paid or 0.0
        ) <= 0:
            raise ValidationError(
                _(
                    "Erreur technique : le montant affecté "
                    "à la cotisation est nul."
                )
            )

        # ======================================================
        # VALIDATION MÉTIER CENTRALISÉE
        #
        # ``association.payment`` is the single source of truth for payment
        # confirmation: it debits the member account once, recalculates the
        # subscription line and invalidates the meeting statistics.
        # ======================================================
        payment.action_collect()
        payment.action_confirm()
        payment.invalidate_recordset(["state"])
        if payment.state != "confirmed":
            raise ValidationError(
                _("Le paiement depuis le compte membre n'a pas pu être validé.")
            )

        # ======================================================
        # FLUSH
        # ======================================================

        self.env.flush_all()

        # ======================================================
        # RAFRAÎCHISSEMENT DE LA LIGNE PAYÉE
        # ======================================================

        subscription_line = self.browse(
            self.id
        ).exists()

        subscription_line._refresh_after_payment()

        # ======================================================
        # COTISATION
        # ======================================================

        subscription = self.subscription_id

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
            if field_name in subscription._fields
        ]

        if subscription_fields:

            subscription.invalidate_recordset(
                subscription_fields
            )

        # ======================================================
        # RECALCUL DES STATISTIQUES
        # ======================================================

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
                "beneficiary_count",
            )
            if field_name in period._fields
        ]

        if period_fields:

            period.invalidate_recordset(
                period_fields
            )

        # ======================================================
        # RECALCUL DU CYCLE
        # ======================================================

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
        # COMPTE MEMBRE
        # ======================================================

        member_account.invalidate_recordset(
            [
                "balance",
                "total_credit",
                "total_debit",
            ]
        )

        if meeting:
            meeting_fields = [
                "subscription_line_ids",
                "collection_count",
                "collection_paid_count",
                "collection_pending_count",
                "collection_total",
                "pot_collected_amount",
                "pot_allocated_amount",
                "pot_available_amount",
                "pot_beneficiary_count",
            ]
            meeting.invalidate_recordset(meeting_fields)
            meeting.modified(meeting_fields)

        self.env.flush_all()

        # ======================================================
        # MESSAGE
        # ======================================================

        subscription.message_post(
            body=_(
                "Paiement de %(amount).2f %(currency)s "
                "effectué depuis le compte membre de "
                "%(member)s pour le cycle %(period)s."
            )
            % {
                "amount":
                    amount_to_pay,

                "currency":
                    self.currency_id.name or "",

                "member":
                    self.member_id.display_name,

                "period":
                    period.display_name,
            }
        )

        # ======================================================
        # ACTUALISATION DU TABLEAU DES MEMBRES UNIQUEMENT
        # ======================================================

        # Refresh the active Cotisations tab without navigating away from the
        # meeting or reloading the complete browser page.
        return {
            "type": "ir.actions.client",
            "tag": "primetech_refresh_subscription_table",
            "params": {
                "subscription_id": self.subscription_id.id,
                "subscription_line_id": self.id,
                "field_name": "subscription_line_ids",
                "origin": "meeting",
                "meeting_id": meeting.id,
                # The confirmation wizard must close once the central payment
                # workflow succeeds, then the meeting Cotisations tab reloads.
                "close_dialog": True,
            },
        }
    
    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # A member added while a grace period is already at zero must not
        # wait for the next daily cron execution.
        records.mapped("subscription_id").filtered(
            "penalty_enabled"
        )._refresh_penalty_lines()

        return records

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "member_id",
        "subscription_id",
    )
    def _check_member_company(self):
        for record in self:
            if not (
                record.member_id
                and record.subscription_id
            ):
                continue

            if (
                record.member_id.company_id
                != record.subscription_id.company_id
            ):
                raise ValidationError(
                    _(
                        "Le membre et la cotisation doivent "
                        "appartenir à la même filiale."
                    )
                )

            if record.member_id.state != "active" or not record.member_id.active:
                raise ValidationError(_("Seuls les membres actifs peuvent participer à une cotisation."))

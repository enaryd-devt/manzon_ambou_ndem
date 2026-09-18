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


class AssociationPaymentLine(models.Model):
    _name = "association.payment.line"
    _description = "Ligne d'affectation de paiement"
    _order = "id"

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
        related="payment_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="payment_id.currency_id",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # PAIEMENT
    # ==========================================================

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement",
        required=True,
        ondelete="cascade",
        index=True,
    )

    payment_date = fields.Date(
        related="payment_id.payment_date",
        string="Date de paiement",
        store=True,
        readonly=True,
    )

    amount_received = fields.Monetary(
        string="Montant reçu",
        currency_field="currency_id",
        default=0.0,
        copy=False,
    )

    # ==========================================================
    # COTISATIONS ÉLIGIBLES
    # ==========================================================

    eligible_subscription_ids = fields.Many2many(
        comodel_name="association.subscription",
        string="Cotisations disponibles",
        compute="_compute_eligible_subscription_ids",
    )


    # ==========================================================
    # COTISATION CHOISIE PAR L'UTILISATEUR
    # ==========================================================

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        ondelete="restrict",
        index=True,
        domain="[('id', 'in', eligible_subscription_ids)]",
    )

    eligible_period_ids = fields.Many2many(
        comodel_name="association.subscription.period",
        string="Cycles disponibles",
        compute="_compute_eligible_period_ids",
    )

    subscription_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle de cotisation",
        ondelete="restrict",
        index=True,
        domain="[('id', 'in', eligible_period_ids)]",
        help="Cycle non payé ou partiellement payé concerné par cette affectation.",
    )


    # ==========================================================
    # LIGNE TECHNIQUE DU MEMBRE
    # ==========================================================

    subscription_line_id = fields.Many2one(
        comodel_name="association.subscription.line",
        string="Ligne de cotisation",
        ondelete="restrict",
        index=True,
        copy=False,
    )

    member_id = fields.Many2one(
        related="payment_id.member_id",
        string="Membre",
        store=True,
        readonly=True,
    )

    member_code = fields.Char(
        related="payment_id.member_id.member_code",
        string="Code membre",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # MONTANTS
    # ==========================================================

    amount_due = fields.Monetary(
        string="Montant dû",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    amount_already_paid = fields.Monetary(
        string="Déjà payé",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    balance_before_payment = fields.Monetary(
        string="Reste avant paiement",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    amount_paid = fields.Monetary(
        string="Montant affecté",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )

    balance_after_payment = fields.Monetary(
        string="Reste après paiement",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    base_amount_due = fields.Monetary(
        string="Cotisation due",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    contribution_paid_amount = fields.Monetary(
        string="Part cotisation",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    subscription_balance_amount = fields.Monetary(
        string="Reste cotisation",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    penalty_due_amount = fields.Monetary(
        string="Pénalité due",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    penalty_paid_amount = fields.Monetary(
        string="Part pénalité",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    penalty_balance_amount = fields.Monetary(
        string="Reste pénalité",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
        readonly=True,
    )

    # ==========================================================
    # PÉNALITÉ DE RETARD
    # ==========================================================

    is_late = fields.Boolean(
        string="Paiement en retard",
        compute="_compute_penalty_information",
    )

    late_days = fields.Integer(
        string="Jours de retard",
        compute="_compute_penalty_information",
    )

    penalty_amount = fields.Monetary(
        string="Pénalité de retard",
        currency_field="currency_id",
        default=0.0,
    )

    total_with_penalty = fields.Monetary(
        string="Total avec pénalité",
        currency_field="currency_id",
        compute="_compute_total_with_penalty",
    )

    # ==========================================================
    # ÉTAT DE L'AFFECTATION
    # ==========================================================

    allocation_state = fields.Selection(
        selection=[
            ("draft", "À valider"),
            ("partial", "Paiement partiel"),
            ("confirmed", "Affecté"),
            ("cancelled", "Annulé"),
        ],
        string="État de l'affectation",
        compute="_compute_allocation_state",
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # OUTILS - SITUATION D'UN MEMBRE PAR CYCLE
    # ==========================================================

    def _get_period_base_due_for_line(self, subscription_line, period):
        """Return the subscription capital expected for one cycle."""

        if not subscription_line or not period:
            return 0.0

        subscription = subscription_line.subscription_id

        if not subscription:
            return 0.0

        return (
            subscription.amount
            or 0.0
        )

    def _get_period_penalty_due_for_line(self, subscription_line, period):
        """Return the penalty expected for one member on one cycle."""

        if not subscription_line or not period:
            return 0.0

        subscription = subscription_line.subscription_id

        if not subscription:
            return 0.0

        current_period = subscription.current_period_id

        if (
            current_period
            and period.id == current_period.id
        ):

            return (
                subscription_line.penalty_amount
                or 0.0
            )

        latest_closed_period = subscription.period_ids.filtered(
            lambda item: item.state == "closed"
        ).sorted(
            key=lambda item: (
                item.sequence,
                item.id,
            ),
            reverse=True,
        )[:1]

        if (
            subscription_line.penalty_applied
            and latest_closed_period
            and latest_closed_period.id == period.id
        ):

            return (
                subscription_line.penalty_amount
                or 0.0
            )

        if not self.env.context.get(
            "ignore_subscription_penalty_recap"
        ):

            recap = self.env[
                "association.subscription.penalty.recap"
            ].with_context(
                active_test=False
            ).search(
                [
                    (
                        "subscription_line_id",
                        "=",
                        subscription_line.id,
                    ),
                    (
                        "subscription_period_id",
                        "=",
                        period.id,
                    ),
                ],
                limit=1,
            )

            if recap and recap.penalty_due_amount > 0:

                return (
                    recap.penalty_due_amount
                    or 0.0
                )

        snapshot = self.env[
            "association.meeting.subscription.snapshot"
        ].search(
            [
                (
                    "session_id.period_id",
                    "=",
                    period.id,
                ),
                (
                    "member_id",
                    "=",
                    subscription_line.member_id.id,
                ),
            ],
            order="id desc",
            limit=1,
        )

        if snapshot and snapshot.penalty_amount > 0:

            return (
                snapshot.penalty_amount
                or 0.0
            )

        paid_amount = self._get_period_paid_for_line(
            subscription_line,
            period,
        )

        base_due = self._get_period_base_due_for_line(
            subscription_line,
            period,
        )

        return max(
            paid_amount - base_due,
            0.0,
        )

    def _get_period_due_for_line(self, subscription_line, period):
        """Return the total amount expected for one member on one cycle."""

        base_due = self._get_period_base_due_for_line(
            subscription_line,
            period,
        )

        penalty_due = self._get_period_penalty_due_for_line(
            subscription_line,
            period,
        )

        return (
            base_due
            + penalty_due
        )

    def _get_period_paid_for_line(
        self,
        subscription_line,
        period,
        exclude_line=None,
        exclude_payment=None,
    ):
        """Return confirmed allocations already made on the selected cycle."""

        if not subscription_line or not period:
            return 0.0

        domain = [
            (
                "subscription_line_id",
                "=",
                subscription_line.id,
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

        if exclude_line and exclude_line.id:
            domain.append(
                (
                    "id",
                    "!=",
                    exclude_line.id,
                )
            )

        if exclude_payment and exclude_payment.id:
            domain.append(
                (
                    "payment_id",
                    "!=",
                    exclude_payment.id,
                )
            )

        payment_lines = self.search(domain)

        return sum(
            payment_lines.mapped("amount_paid")
        )

    def _get_unsettled_periods_for_line(
        self,
        subscription_line,
        excluded_period_ids=None,
    ):
        """Return running or closed cycles that still have a balance."""

        Period = self.env[
            "association.subscription.period"
        ]

        if not subscription_line:
            return Period

        subscription = subscription_line.subscription_id

        if not subscription:
            return Period

        excluded_period_ids = set(
            excluded_period_ids
            or []
        )

        periods = Period.search(
            [
                (
                    "subscription_id",
                    "=",
                    subscription.id,
                ),
                (
                    "company_id",
                    "=",
                    subscription_line.company_id.id,
                ),
                (
                    "state",
                    "in",
                    [
                        "running",
                        "closed",
                    ],
                ),
            ],
            order="sequence asc, id asc",
        )

        available = Period

        for period in periods:

            if period.id in excluded_period_ids:
                continue

            amount_due = self._get_period_due_for_line(
                subscription_line,
                period,
            )

            already_paid = self._get_period_paid_for_line(
                subscription_line,
                period,
            )

            if (
                amount_due > 0
                and already_paid < amount_due - 0.01
            ):
                available |= period

        return available

    def _get_period_amount_breakdown_for_line(
        self,
        subscription_line,
        period,
        current_amount=0.0,
        already_paid=None,
        exclude_line=None,
        exclude_payment=None,
    ):
        """Split payments between subscription capital and penalty."""

        base_due = self._get_period_base_due_for_line(
            subscription_line,
            period,
        )

        penalty_due = self._get_period_penalty_due_for_line(
            subscription_line,
            period,
        )

        if already_paid is None:

            already_paid = self._get_period_paid_for_line(
                subscription_line,
                period,
                exclude_line=exclude_line,
                exclude_payment=exclude_payment,
            )

        current_amount = (
            current_amount
            or 0.0
        )

        total_paid = (
            already_paid
            + current_amount
        )

        contribution_before = min(
            already_paid,
            base_due,
        )

        contribution_total = min(
            total_paid,
            base_due,
        )

        contribution_current = max(
            contribution_total
            - contribution_before,
            0.0,
        )

        penalty_before = min(
            max(
                already_paid
                - base_due,
                0.0,
            ),
            penalty_due,
        )

        penalty_total = min(
            max(
                total_paid
                - base_due,
                0.0,
            ),
            penalty_due,
        )

        penalty_current = max(
            penalty_total
            - penalty_before,
            0.0,
        )

        amount_due = (
            base_due
            + penalty_due
        )

        return {
            "amount_due": amount_due,
            "base_amount_due": base_due,
            "penalty_due_amount": penalty_due,
            "amount_paid": total_paid,
            "contribution_paid_amount": contribution_total,
            "contribution_current_amount": contribution_current,
            "subscription_balance_amount": max(
                base_due
                - contribution_total,
                0.0,
            ),
            "penalty_paid_amount": penalty_total,
            "penalty_current_amount": penalty_current,
            "penalty_balance_amount": max(
                penalty_due
                - penalty_total,
                0.0,
            ),
            "balance": max(
                amount_due
                - total_paid,
                0.0,
            ),
        }

    def _set_amount_from_available_payment(self, balance):
        for record in self:
            payment = record.payment_id

            if not payment:
                continue

            other_allocations = sum(
                payment.line_ids
                .filtered(
                    lambda line: line != record
                )
                .mapped("amount_paid")
            )

            available_amount = max(
                (
                    payment.amount
                    or 0.0
                )
                - other_allocations,
                0.0,
            )

            record.amount_paid = min(
                balance,
                available_amount,
            )


    # ==========================================================
    # CALCUL DES COTISATIONS ÉLIGIBLES
    # ==========================================================

    @api.depends(
        "payment_id",
        "payment_id.member_id",
        "payment_id.company_id",
        "payment_id.line_ids.subscription_id",
        "payment_id.line_ids.subscription_period_id",
    )
    def _compute_eligible_subscription_ids(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for record in self:

            # ======================================================
            # INITIALISATION
            # ======================================================

            record.eligible_subscription_ids = False

            payment = record.payment_id

            if not payment:
                continue

            if not payment.member_id:
                continue

            if not payment.company_id:
                continue

            # ======================================================
            # LIGNES DE COTISATION DU MEMBRE
            #
            # RÈGLE :
            #
            # 1. LE MEMBRE APPARTIENT À LA COTISATION
            # 2. UN CYCLE EN COURS OU TERMINÉ RESTE À RÉGLER
            # 3. MÊME FILIALE
            # ======================================================

            subscription_lines = SubscriptionLine.search(
                [
                    (
                        "member_id",
                        "=",
                        payment.member_id.id,
                    ),
                    (
                        "subscription_id.company_id",
                        "=",
                        payment.company_id.id,
                    ),
                ]
            )

            if not subscription_lines:
                continue

            # ======================================================
            # EXCLURE UNIQUEMENT LES CYCLES DÉJÀ CHOISIS
            # DANS LE MÊME PAIEMENT
            # ======================================================

            selected_periods_by_subscription = {}

            for selected_line in payment.line_ids.filtered(
                lambda line: (
                    line != record
                    and line.subscription_id
                    and line.subscription_period_id
                )
            ):

                selected_periods_by_subscription.setdefault(
                    selected_line.subscription_id.id,
                    set(),
                ).add(
                    selected_line.subscription_period_id.id
                )

            eligible_lines = self.env[
                "association.subscription.line"
            ]

            for subscription_line in subscription_lines:

                excluded_period_ids = (
                    selected_periods_by_subscription.get(
                        subscription_line.subscription_id.id,
                        set(),
                    )
                )

                if self._get_unsettled_periods_for_line(
                    subscription_line,
                    excluded_period_ids,
                ):

                    eligible_lines |= subscription_line

            # ======================================================
            # RÉSULTAT
            # ======================================================

            record.eligible_subscription_ids = (
                eligible_lines.mapped(
                    "subscription_id"
                )
            )
    # ==========================================================
    # RÉSOLUTION DE LA LIGNE DE COTISATION
    # ==========================================================

    @api.depends(
        "subscription_id",
        "payment_id.member_id",
        "payment_id.company_id",
        "payment_id.line_ids.subscription_id",
        "payment_id.line_ids.subscription_period_id",
        "subscription_line_id",
        "subscription_line_id.payment_line_ids.amount_paid",
        "subscription_line_id.payment_line_ids.payment_id.state",
        "subscription_line_id.payment_line_ids.subscription_period_id",
    )
    def _compute_eligible_period_ids(self):
        """Offer running or closed cycles with a remaining balance."""

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for record in self:

            record.eligible_period_ids = False

            if not record.subscription_id:
                continue

            if not record.payment_id.member_id:
                continue

            if not record.payment_id.company_id:
                continue

            subscription_line = record.subscription_line_id

            if not subscription_line:

                subscription_line = SubscriptionLine.search(
                    [
                        (
                            "subscription_id",
                            "=",
                            record.subscription_id.id,
                        ),
                        (
                            "member_id",
                            "=",
                            record.payment_id.member_id.id,
                        ),
                        (
                            "company_id",
                            "=",
                            record.payment_id.company_id.id,
                        ),
                    ],
                    limit=1,
                )

            if not subscription_line:
                continue

            selected_period_ids = (
                record.payment_id.line_ids
                .filtered(
                    lambda line: (
                        line != record
                        and line.subscription_id
                        == record.subscription_id
                        and line.subscription_period_id
                    )
                )
                .mapped("subscription_period_id")
                .ids
            )

            available = self._get_unsettled_periods_for_line(
                subscription_line,
                selected_period_ids,
            )

            if (
                record.subscription_period_id
                and record.subscription_period_id.state in (
                    "running",
                    "closed",
                )
                and record.subscription_period_id.subscription_id
                == record.subscription_id
            ):

                available |= record.subscription_period_id

            record.eligible_period_ids = available

    def _resolve_subscription_line(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for record in self:

            if not record.subscription_id:
                record.subscription_line_id = False
                continue

            if not record.payment_id.member_id:
                record.subscription_line_id = False
                continue

            subscription_line = SubscriptionLine.search(
                [
                    (
                        "subscription_id",
                        "=",
                        record.subscription_id.id,
                    ),
                    (
                        "member_id",
                        "=",
                        record.payment_id.member_id.id,
                    ),
                    (
                        "company_id",
                        "=",
                        record.payment_id.company_id.id,
                    ),
                ],
                limit=1,
            )

            if not subscription_line:
                raise ValidationError(
                    _(
                        "Le membre %(member)s n'est pas inscrit "
                        "à la cotisation %(subscription)s."
                    )
                    % {
                        "member":
                            record.payment_id.member_id.display_name,

                        "subscription":
                            record.subscription_id.display_name,
                    }
                )

            record.subscription_line_id = (
                subscription_line
            )

            if (
                record.subscription_period_id
                and record.subscription_period_id.subscription_id
                != record.subscription_id
            ):
                raise ValidationError(_("Le cycle sélectionné ne correspond pas à la cotisation."))

            if (
                record.subscription_period_id
                and record.subscription_period_id.state
                not in (
                    "running",
                    "closed",
                )
            ):
                raise ValidationError(
                    _(
                        "Le cycle sélectionné doit être en cours "
                        "ou terminé."
                    )
                )

            if not record.subscription_period_id:

                periods = self._get_unsettled_periods_for_line(
                    subscription_line
                )

                record.subscription_period_id = (
                    periods[:1]
                    if periods
                    else False
                )

        return True


    @api.model_create_multi
    def create(self, vals_list):

        records = super().create(vals_list)

        records._resolve_subscription_line()

        return records


    def write(self, vals):

        result = super().write(vals)

        if (
            "subscription_id" in vals
            or "payment_id" in vals
            or "subscription_period_id" in vals
        ):
            self._resolve_subscription_line()

        return result
    
    # ==========================================================
    # ONCHANGE - COTISATION
    # ==========================================================

    @api.onchange("subscription_id")
    def _onchange_subscription_id(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for record in self:

            # ======================================================
            # RÉINITIALISATION
            # ======================================================

            record.subscription_line_id = False
            record.subscription_period_id = False
            record.amount_paid = 0.0

            if not record.subscription_id:
                continue

            payment = record.payment_id

            if not payment:
                continue

            if not payment.member_id:
                continue

            # ======================================================
            # RECHERCHER LA LIGNE DU MEMBRE
            # ======================================================

            subscription_line = SubscriptionLine.search(
                [
                    (
                        "subscription_id",
                        "=",
                        record.subscription_id.id,
                    ),
                    (
                        "member_id",
                        "=",
                        payment.member_id.id,
                    ),
                    (
                        "subscription_id.company_id",
                        "=",
                        payment.company_id.id,
                    ),
                ],
                limit=1,
            )

            if not subscription_line:

                subscription_name = (
                    record.subscription_id.display_name
                )

                member_name = (
                    payment.member_id.display_name
                )

                record.subscription_id = False

                return {
                    "warning": {
                        "title":
                            _("Membre non inscrit"),

                        "message":
                            _(
                                "Le membre %(member)s "
                                "n'appartient pas à la cotisation "
                                "%(subscription)s."
                            )
                            % {
                                "member":
                                    member_name,

                                "subscription":
                                    subscription_name,
                            },
                    }
                }

            # ======================================================
            # LIEN TECHNIQUE
            # ======================================================

            record.subscription_line_id = (
                subscription_line
            )

            periods = self._get_unsettled_periods_for_line(
                subscription_line
            )

            if not periods:

                subscription_name = (
                    record.subscription_id.display_name
                )

                record.subscription_id = False
                record.subscription_line_id = False

                return {
                    "warning": {
                        "title":
                            _("Cotisation soldée"),

                        "message":
                            _(
                                "Aucun cycle en cours ou terminé "
                                "avec un solde restant n'a été "
                                "trouvé pour la cotisation "
                                "%(subscription)s."
                            )
                            % {
                                "subscription":
                                    subscription_name,
                            },
                    }
                }

            record.subscription_period_id = periods[:1]

            amount_due = self._get_period_due_for_line(
                subscription_line,
                record.subscription_period_id,
            )

            already_paid = self._get_period_paid_for_line(
                subscription_line,
                record.subscription_period_id,
            )

            balance = max(
                amount_due - already_paid,
                0.0,
            )

            # ======================================================
            # AFFECTATION AUTOMATIQUE
            # ======================================================

            record._set_amount_from_available_payment(
                balance
            )
    
    # ==========================================================
    # CALCUL DES MONTANTS DE L'AFFECTATION
    # ==========================================================

    @api.depends(
        "subscription_line_id",
        "subscription_id",
        "subscription_id.amount",
        "subscription_id.current_period_id",
        "subscription_line_id.penalty_amount",
        "subscription_line_id.payment_line_ids.amount_paid",
        "subscription_line_id.payment_line_ids.payment_id.state",
        "subscription_line_id.payment_line_ids.payment_id.subscription_period_id",
        "amount_paid",
        "payment_id.state",
        "subscription_period_id",
        "subscription_period_id.state",
    )
    def _compute_payment_amounts(self):

        for record in self:

            # ======================================================
            # INITIALISATION OBLIGATOIRE
            # ======================================================

            record.amount_due = 0.0
            record.amount_already_paid = 0.0
            record.balance_before_payment = 0.0
            record.balance_after_payment = 0.0
            record.base_amount_due = 0.0
            record.contribution_paid_amount = 0.0
            record.subscription_balance_amount = 0.0
            record.penalty_due_amount = 0.0
            record.penalty_paid_amount = 0.0
            record.penalty_balance_amount = 0.0

            # ======================================================
            # PAS ENCORE DE LIGNE TECHNIQUE
            # ======================================================

            if not record.subscription_line_id:
                continue

            subscription_line = record.subscription_line_id

            # ======================================================
            # PAIEMENTS DÉJÀ CONFIRMÉS
            # ======================================================

            amount_already_paid = record._get_period_paid_for_line(
                subscription_line,
                record.subscription_period_id,
                exclude_line=record,
            )

            # ======================================================
            # RESTE AVANT LE PAIEMENT COURANT
            # ======================================================

            current_amount = (
                record.amount_paid
                or 0.0
            )

            breakdown = record._get_period_amount_breakdown_for_line(
                subscription_line,
                record.subscription_period_id,
                current_amount=current_amount,
                already_paid=amount_already_paid,
            )

            amount_due = breakdown[
                "amount_due"
            ]

            balance_before = max(
                amount_due - amount_already_paid,
                0.0,
            )

            # ======================================================
            # AFFECTATION
            # ======================================================

            record.amount_due = (
                amount_due
            )

            record.amount_already_paid = (
                amount_already_paid
            )

            record.balance_before_payment = (
                balance_before
            )

            record.balance_after_payment = max(
                balance_before - current_amount,
                0.0,
            )

            record.base_amount_due = breakdown[
                "base_amount_due"
            ]

            record.contribution_paid_amount = breakdown[
                "contribution_current_amount"
            ]

            record.subscription_balance_amount = max(
                breakdown[
                    "subscription_balance_amount"
                ],
                0.0,
            )

            record.penalty_due_amount = breakdown[
                "penalty_due_amount"
            ]

            record.penalty_paid_amount = breakdown[
                "penalty_current_amount"
            ]

            record.penalty_balance_amount = max(
                breakdown[
                    "penalty_balance_amount"
                ],
                0.0,
            )

    # ==========================================================
    # COTISATIONS ÉLIGIBLES À L'AFFECTATION
    # ==========================================================

    @api.depends(
        "payment_id",
        "payment_id.member_id",
        "payment_id.company_id",
        "payment_id.line_ids",
        "payment_id.line_ids.subscription_line_id",
    )
    def _compute_eligible_subscription_line_ids(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for record in self:

            # ======================================================
            # INITIALISATION
            # ======================================================

            record.eligible_subscription_line_ids = False

            payment = record.payment_id

            if not payment or not payment.member_id:
                continue

            # ======================================================
            # RECHERCHE DES COTISATIONS DU MEMBRE
            # ======================================================

            subscription_lines = SubscriptionLine.search([
                (
                    "member_id",
                    "=",
                    payment.member_id.id,
                ),
                (
                    "company_id",
                    "=",
                    payment.company_id.id,
                ),
            ])

            # ======================================================
            # FORCER LE RECALCUL DE LA SITUATION DU CYCLE COURANT
            # ======================================================

            if subscription_lines:

                subscription_lines.invalidate_recordset([
                    "amount_due",
                    "amount_paid",
                    "balance",
                    "payment_state",
                ])

            # ======================================================
            # CONSERVER UNIQUEMENT LES IMPAYÉES / PARTIELLES
            # ======================================================

            eligible_lines = subscription_lines.filtered(
                lambda line: (
                    line.subscription_id
                    and line.subscription_id.current_period_id
                    and line.payment_state in (
                        "not_paid",
                        "partial",
                    )
                    and (line.balance or 0.0) > 0.0
                )
            )

            # ======================================================
            # EXCLURE LES COTISATIONS DÉJÀ AJOUTÉES AU PAIEMENT
            # ======================================================

            already_selected_ids = (
                payment.line_ids
                .filtered(
                    lambda line:
                        line != record
                        and line.subscription_line_id
                )
                .mapped("subscription_line_id")
                .ids
            )

            eligible_lines = eligible_lines.filtered(
                lambda line:
                    line.id not in already_selected_ids
            )

            # ======================================================
            # RÉSULTAT
            # ======================================================

            record.eligible_subscription_line_ids = (
                eligible_lines
            )
    
    
    
    # ==========================================================
    # CALCUL DU RETARD ET DE LA PÉNALITÉ
    # ==========================================================

    @api.depends(
        "payment_id.payment_date",
        "payment_id.state",
        "subscription_period_id",
        "subscription_line_id",
        "subscription_line_id.subscription_id",
        "subscription_line_id.subscription_id.period_ids",
        "subscription_line_id.subscription_id.period_ids.state",
        "subscription_line_id.subscription_id.period_ids.due_date",
        "subscription_line_id.subscription_id.period_ids.sequence",
        "amount_paid",
    )
    def _compute_penalty_information(self):

        for record in self:

            # ======================================================
            # INITIALISATION OBLIGATOIRE DE TOUS LES CHAMPS COMPUTE
            # ======================================================

            record.is_late = False
            record.late_days = 0
            record.penalty_amount = 0.0

            # ======================================================
            # LIGNE DE COTISATION
            # ======================================================

            subscription_line = (
                record.subscription_line_id
            )

            if not subscription_line:
                continue

            # ======================================================
            # COTISATION
            # ======================================================

            subscription = (
                subscription_line.subscription_id
            )

            if not subscription:
                continue

            # ======================================================
            # DATE DU PAIEMENT
            # ======================================================

            payment_date = (
                record.payment_id.payment_date
                or fields.Date.context_today(record)
            )

            # ======================================================
            # CYCLE EXPLICITEMENT LIÉ AU PAIEMENT
            # ======================================================

            period = record.subscription_period_id

            # ======================================================
            # COMPATIBILITÉ AVEC LES ANCIENS PAIEMENTS
            # ======================================================

            if not period:

                periods = subscription.period_ids.filtered(
                    lambda item: (
                        item.state in (
                            "running",
                            "closed",
                        )
                        and item.period_start_date
                        and item.period_end_date
                        and item.period_start_date
                        <= payment_date
                        <= item.period_end_date
                    )
                )

                # ==================================================
                # SI AUCUN CYCLE PAR DATE
                # PRENDRE LE CYCLE EN COURS
                # ==================================================

                if not periods:

                    periods = (
                        subscription.period_ids.filtered(
                            lambda item:
                                item.state == "running"
                        )
                    )

                if not periods:
                    continue

                period = periods.sorted(
                    key=lambda item: (
                        item.sequence,
                        item.id,
                    ),
                    reverse=True,
                )[0]

            # ======================================================
            # DATE D'ÉCHÉANCE
            # ======================================================

            due_date = period.due_date

            if not due_date:
                continue

            # ======================================================
            # CALCUL DU NOMBRE DE JOURS DE RETARD
            # ======================================================

            late_days = max(
                (
                    payment_date - due_date
                ).days,
                0,
            )

            record.late_days = late_days

            # ======================================================
            # ÉTAT DU RETARD
            # ======================================================

            record.is_late = bool(
                late_days > 0
            )

            if not record.is_late:
                continue

            # ======================================================
            # CALCUL DE LA PÉNALITÉ
            # ======================================================

            penalty_amount = 0.0

            # ------------------------------------------------------
            # PÉNALITÉ FIXE
            # ------------------------------------------------------

            if (
                hasattr(
                    subscription,
                    "penalty_type",
                )
                and subscription.penalty_type == "fixed"
            ):

                penalty_amount = (
                    subscription.penalty_amount
                    or 0.0
                )

            # ------------------------------------------------------
            # PÉNALITÉ EN POURCENTAGE
            # ------------------------------------------------------

            elif (
                hasattr(
                    subscription,
                    "penalty_type",
                )
                and subscription.penalty_type
                == "percentage"
            ):

                penalty_rate = (
                    subscription.penalty_rate
                    or 0.0
                )

                penalty_amount = (
                    (record.amount_paid or 0.0)
                    * penalty_rate
                    / 100.0
                )

            # ======================================================
            # AFFECTATION DE LA PÉNALITÉ
            # ======================================================

            record.penalty_amount = (
                penalty_amount
            )
    
    # ==========================================================
    # TOTAL AVEC PÉNALITÉ
    # ==========================================================

    @api.depends(
        "amount_paid",
        "contribution_paid_amount",
        "penalty_paid_amount",
    )
    def _compute_total_with_penalty(self):
        for record in self:
            record.total_with_penalty = (
                (record.contribution_paid_amount or 0.0)
                + (record.penalty_paid_amount or 0.0)
            )

    # ==========================================================
    # ÉTAT DE L'AFFECTATION
    # ==========================================================

    @api.depends(
        "payment_id.state",
        "amount_paid",
        "balance_after_payment",
    )
    def _compute_allocation_state(self):
        for record in self:

            if record.payment_id.state == "cancelled":

                record.allocation_state = "cancelled"

            elif record.payment_id.state != "confirmed":

                record.allocation_state = "draft"

            elif record.balance_after_payment > 0:

                record.allocation_state = "partial"

            else:

                record.allocation_state = "confirmed"

    # ==========================================================
    # ONCHANGE - COTISATION À RÉGLER
    # ==========================================================

    @api.onchange("subscription_line_id")
    def _onchange_subscription_line_id(self):

        for record in self:

            # ======================================================
            # RÉINITIALISATION
            # ======================================================

            record.amount_paid = 0.0

            if not record.subscription_line_id:
                continue

            if not record.subscription_id:
                record.subscription_id = (
                    record.subscription_line_id.subscription_id
                )

            if (
                record.subscription_period_id
                and (
                    record.subscription_period_id.subscription_id
                    != record.subscription_id
                    or record.subscription_period_id.state
                    not in (
                        "running",
                        "closed",
                    )
                )
            ):

                record.subscription_period_id = False

            if not record.subscription_period_id:

                periods = record._get_unsettled_periods_for_line(
                    record.subscription_line_id
                )

                record.subscription_period_id = (
                    periods[:1]
                    if periods
                    else False
                )

            # ======================================================
            # RESTE À PAYER SUR LE CYCLE
            # ======================================================

            amount_due = record._get_period_due_for_line(
                record.subscription_line_id,
                record.subscription_period_id,
            )

            already_paid = record._get_period_paid_for_line(
                record.subscription_line_id,
                record.subscription_period_id,
            )

            balance = max(
                amount_due - already_paid,
                0.0,
            )

            # ======================================================
            # AFFECTATION AUTOMATIQUE
            # ======================================================

            record._set_amount_from_available_payment(
                balance
            )

    @api.onchange("subscription_period_id")
    def _onchange_subscription_period_id(self):

        for record in self:

            record.amount_paid = 0.0

            if not record.subscription_period_id:
                continue

            if not record.subscription_line_id:
                record._resolve_subscription_line()

            if not record.subscription_line_id:
                continue

            amount_due = record._get_period_due_for_line(
                record.subscription_line_id,
                record.subscription_period_id,
            )

            already_paid = record._get_period_paid_for_line(
                record.subscription_line_id,
                record.subscription_period_id,
            )

            balance = max(
                amount_due - already_paid,
                0.0,
            )

            record._set_amount_from_available_payment(
                balance
            )
    
    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "amount_paid",
        "penalty_amount",
    )
    def _check_amounts(self):
        for record in self:

            if record.amount_paid < 0:
                raise ValidationError(
                    _(
                        "Le montant affecté ne peut pas "
                        "être négatif."
                    )
                )

            if record.penalty_amount < 0:
                raise ValidationError(
                    _(
                        "La pénalité de retard ne peut pas "
                        "être négative."
                    )
                )


    # ==========================================================
    # CONTRÔLE FILIALE
    # ==========================================================

    @api.constrains(
        "payment_id",
        "subscription_line_id",
    )
    def _check_company(self):
        for record in self:

            if (
                record.payment_id
                and record.subscription_line_id
                and record.payment_id.company_id
                != record.subscription_line_id.company_id
            ):
                raise ValidationError(
                    _(
                        "Le paiement et la cotisation doivent "
                        "appartenir à la même Filiale."
                    )
                )
            
    # ==========================================================
    # PROTECTION DE SUPPRESSION
    # ==========================================================

    def unlink(self):
        for record in self:

            if (
                record.payment_id
                and record.payment_id.state == "confirmed"
            ):
                raise ValidationError(
                    _(
                        "Impossible de supprimer cette ligne.\n\n"
                        "Le paiement est déjà confirmé et le montant "
                        "a été affecté à la cotisation.\n\n"
                        "Vous devez d'abord annuler le paiement."
                    )
                )

        return super().unlink()

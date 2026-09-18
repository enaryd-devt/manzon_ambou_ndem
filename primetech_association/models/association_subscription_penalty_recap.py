# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class AssociationSubscriptionPenaltyRecap(models.Model):
    _name = "association.subscription.penalty.recap"
    _description = "Récapitulatif des pénalités de cotisation"
    _order = "payment_state, member_id, subscription_period_id desc, id desc"

    active = fields.Boolean(
        string="Actif",
        default=True,
        index=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        readonly=True,
        required=True,
        index=True,
        ondelete="cascade",
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        readonly=True,
        store=True,
    )

    subscription_line_id = fields.Many2one(
        comodel_name="association.subscription.line",
        string="Ligne de cotisation",
        readonly=True,
        required=True,
        index=True,
        ondelete="cascade",
    )

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        readonly=True,
        required=True,
        index=True,
        ondelete="cascade",
    )

    subscription_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle",
        readonly=True,
        required=True,
        index=True,
        ondelete="cascade",
    )

    period_state = fields.Selection(
        related="subscription_period_id.state",
        string="Statut du cycle",
        readonly=True,
        store=True,
    )

    company_id = fields.Many2one(
        related="subscription_id.company_id",
        string="Filiale",
        readonly=True,
        store=True,
    )

    currency_id = fields.Many2one(
        related="subscription_id.currency_id",
        string="Devise",
        readonly=True,
        store=True,
    )

    base_amount_due = fields.Monetary(
        string="Cotisation due",
        currency_field="currency_id",
        readonly=True,
    )

    contribution_paid_amount = fields.Monetary(
        string="Cotisation payée",
        currency_field="currency_id",
        readonly=True,
    )

    subscription_balance_amount = fields.Monetary(
        string="Reste cotisation",
        currency_field="currency_id",
        readonly=True,
    )

    penalty_due_amount = fields.Monetary(
        string="Pénalité due",
        currency_field="currency_id",
        readonly=True,
    )

    penalty_paid_amount = fields.Monetary(
        string="Pénalité payée",
        currency_field="currency_id",
        readonly=True,
    )

    penalty_balance_amount = fields.Monetary(
        string="Reste pénalité",
        currency_field="currency_id",
        readonly=True,
    )

    total_amount_due = fields.Monetary(
        string="Total dû",
        currency_field="currency_id",
        readonly=True,
    )

    total_amount_paid = fields.Monetary(
        string="Total payé",
        currency_field="currency_id",
        readonly=True,
    )

    total_balance = fields.Monetary(
        string="Reste total",
        currency_field="currency_id",
        readonly=True,
    )

    subscription_payment_state = fields.Selection(
        selection=[
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État cotisation",
        readonly=True,
    )

    payment_state = fields.Selection(
        selection=[
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État pénalité",
        readonly=True,
    )

    last_payment_date = fields.Date(
        string="Dernier paiement",
        readonly=True,
    )

    _sql_constraints = [
        (
            "association_subscription_penalty_recap_unique",
            "unique(subscription_line_id, subscription_period_id)",
            "Un récapitulatif existe déjà pour ce membre et ce cycle.",
        ),
    ]

    @api.model
    def _get_finance_group_xmlids(self):
        return (
            "primetech_association.group_association_meeting_treasurer",
            "primetech_association.group_association_manager",
            "primetech_association.group_association_admin",
        )

    def _check_can_register_payment(self):
        if not any(
            self.env.user.has_group(xmlid)
            for xmlid in self._get_finance_group_xmlids()
        ):
            raise AccessError(
                _(
                    "Seul le trésorier, le responsable ou "
                    "l'administrateur peut enregistrer ce règlement."
                )
            )

    @api.model
    def _get_payment_domain(self, subscription_line, period):
        return [
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

    @api.model
    def _prepare_values_for_line_period(self, subscription_line, period):
        PaymentLine = self.env[
            "association.payment.line"
        ].with_context(
            ignore_subscription_penalty_recap=True
        )

        payment_lines = PaymentLine.search(
            self._get_payment_domain(
                subscription_line,
                period,
            )
        )

        paid_amount = sum(
            payment_lines.mapped("amount_paid")
        )

        breakdown = PaymentLine._get_period_amount_breakdown_for_line(
            subscription_line,
            period,
            current_amount=0.0,
            already_paid=paid_amount,
        )

        base_due = breakdown[
            "base_amount_due"
        ]

        penalty_due = max(
            breakdown[
                "penalty_due_amount"
            ],
            max(
                paid_amount - base_due,
                0.0,
            ),
        )

        contribution_paid = min(
            paid_amount,
            base_due,
        )

        penalty_paid = min(
            max(
                paid_amount - base_due,
                0.0,
            ),
            penalty_due,
        )

        subscription_balance = max(
            base_due - contribution_paid,
            0.0,
        )

        penalty_balance = max(
            penalty_due - penalty_paid,
            0.0,
        )

        total_due = (
            base_due
            + penalty_due
        )

        total_balance = max(
            total_due
            - paid_amount,
            0.0,
        )

        payment_dates = [
            payment.payment_date
            for payment in payment_lines.mapped("payment_id")
            if payment.payment_date
        ]

        if contribution_paid <= 0:
            subscription_payment_state = "not_paid"
        elif subscription_balance > 0.01:
            subscription_payment_state = "partial"
        else:
            subscription_payment_state = "paid"

        if penalty_paid <= 0:
            payment_state = "not_paid"
        elif penalty_balance > 0.01:
            payment_state = "partial"
        else:
            payment_state = "paid"

        return {
            "active": bool(
                penalty_due > 0
                or penalty_paid > 0
            ),
            "member_id": subscription_line.member_id.id,
            "subscription_line_id": subscription_line.id,
            "subscription_id": subscription_line.subscription_id.id,
            "subscription_period_id": period.id,
            "base_amount_due": base_due,
            "contribution_paid_amount": contribution_paid,
            "subscription_balance_amount": subscription_balance,
            "penalty_due_amount": penalty_due,
            "penalty_paid_amount": penalty_paid,
            "penalty_balance_amount": penalty_balance,
            "total_amount_due": total_due,
            "total_amount_paid": paid_amount,
            "total_balance": total_balance,
            "subscription_payment_state": subscription_payment_state,
            "payment_state": payment_state,
            "last_payment_date": (
                max(payment_dates)
                if payment_dates
                else False
            ),
        }

    @api.model
    def _sync_for_line_period(self, subscription_line, period):
        if not subscription_line or not period:
            return self

        existing = self.with_context(
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

        values = self._prepare_values_for_line_period(
            subscription_line,
            period,
        )

        if existing:
            existing.write(values)
            return existing

        if not values.get("active"):
            return self

        return self.create(values)

    @api.model
    def _sync_for_lines_period(self, subscription_lines, period):
        recaps = self

        for subscription_line in subscription_lines:

            for cycle in period:

                recaps |= self._sync_for_line_period(
                    subscription_line,
                    cycle,
                )

        return recaps

    @api.model
    def _sync_member(self, member):
        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        Period = self.env[
            "association.subscription.period"
        ]

        recaps = self

        for subscription_line in SubscriptionLine.search(
            [
                (
                    "member_id",
                    "=",
                    member.id,
                ),
                (
                    "active",
                    "=",
                    True,
                ),
            ]
        ):
            periods = Period.search(
                [
                    (
                        "subscription_id",
                        "=",
                        subscription_line.subscription_id.id,
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

            recaps |= self._sync_for_lines_period(
                subscription_line,
                periods,
            )

        return recaps

    @api.model
    def _sync_all(self):
        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        Period = self.env[
            "association.subscription.period"
        ]

        recaps = self

        subscription_lines = SubscriptionLine.search(
            [
                (
                    "active",
                    "=",
                    True,
                ),
            ]
        )

        periods_by_subscription = {}

        for period in Period.search(
            [
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
        ):
            periods_by_subscription.setdefault(
                period.subscription_id.id,
                self.env["association.subscription.period"],
            )
            periods_by_subscription[
                period.subscription_id.id
            ] |= period

        for subscription_line in subscription_lines:
            recaps |= self._sync_for_lines_period(
                subscription_line,
                periods_by_subscription.get(
                    subscription_line.subscription_id.id,
                    self.env["association.subscription.period"],
                ),
            )

        return recaps

    def action_register_payment(self):
        self.ensure_one()
        self._check_can_register_payment()

        if self.total_balance <= 0:
            raise ValidationError(
                _("Cette cotisation ne présente aucun reste à payer.")
            )

        Payment = self.env["association.payment"]

        payment_methods = Payment._get_payment_method_selection()

        payment_method = (
            payment_methods[0][0]
            if payment_methods
            else "cash"
        )

        payment = Payment.create(
            {
                "member_id": self.member_id.id,
                "payment_date": fields.Date.context_today(self),
                "amount": self.total_balance,
                "payment_source": "external",
                "subscription_period_id": self.subscription_period_id.id,
                "has_allocations": True,
                "payment_method": payment_method,
                "payment_reference": _(
                    "Règlement cotisation - %(subscription)s - %(period)s"
                )
                % {
                    "subscription": self.subscription_id.display_name,
                    "period": self.subscription_period_id.display_name,
                },
                "company_id": self.company_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "subscription_line_id":
                                self.subscription_line_id.id,
                            "subscription_id": self.subscription_id.id,
                            "subscription_period_id":
                                self.subscription_period_id.id,
                            "amount_paid": self.total_balance,
                        },
                    ),
                ],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Règlement de cotisation"),
            "res_model": "association.payment",
            "view_mode": "form",
            "res_id": payment.id,
            "target": "current",
        }

    @api.model
    def action_open_global(self):
        self._sync_all()

        return {
            "type": "ir.actions.act_window",
            "name": _("Pénalités de cotisation"),
            "res_model": "association.subscription.penalty.recap",
            "view_mode": "list,form",
            "views": [
                (
                    self.env.ref(
                        "primetech_association.view_subscription_penalty_recap_list"
                    ).id,
                    "list",
                ),
                (
                    self.env.ref(
                        "primetech_association.view_subscription_penalty_recap_form"
                    ).id,
                    "form",
                ),
            ],
            "search_view_id": self.env.ref(
                "primetech_association.view_subscription_penalty_recap_search"
            ).id,
            "domain": [
                (
                    "active",
                    "=",
                    True,
                ),
            ],
            "context": {
                "search_default_group_payment_state": 1,
                "create": False,
                "edit": False,
                "delete": False,
            },
        }

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class AssociationMemberSubscriptionCycleReport(models.TransientModel):
    _name = "association.member.subscription.cycle.report"
    _description = "Situation financière du membre"
    _order = "situation_type, subscription_id, period_sequence, subscription_period_id, id"

    situation_type = fields.Selection(
        selection=[
            ("subscription", "Cotisation"),
            ("recovery", "Recouvrement"),
            ("penalty", "Sanction financière"),
            ("membership", "Frais d'adhésion"),
            ("adjustment", "Ajustement de situation"),
        ],
        string="Type",
        default="subscription",
        required=True,
        readonly=True,
    )

    label = fields.Char(
        string="Élément",
        readonly=True,
    )

    membership_fee_id = fields.Many2one(
        comodel_name="association.membership.fee",
        string="Frais / ajustement",
        readonly=True,
    )

    penalty_id = fields.Many2one(
        comodel_name="association.penalty",
        string="Sanction",
        readonly=True,
    )

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        readonly=True,
        required=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        readonly=True,
        store=True,
    )

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        readonly=True,
    )

    subscription_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle",
        readonly=True,
    )

    cycle_label = fields.Char(
        string="Cycle",
        compute="_compute_cycle_label",
        readonly=True,
    )

    subscription_line_id = fields.Many2one(
        comodel_name="association.subscription.line",
        string="Ligne de cotisation",
        readonly=True,
    )

    period_sequence = fields.Integer(
        related="subscription_period_id.sequence",
        string="N° cycle",
        readonly=True,
        store=True,
    )

    period_state = fields.Selection(
        related="subscription_period_id.state",
        string="Statut du cycle",
        readonly=True,
        store=True,
    )

    @api.depends("situation_type", "subscription_period_id", "subscription_period_id.name")
    def _compute_cycle_label(self):
        for report in self:
            if report.subscription_period_id:
                report.cycle_label = report.subscription_period_id.display_name
            elif report.situation_type in ("subscription", "recovery"):
                report.cycle_label = _("Sans cycle")
            else:
                report.cycle_label = False

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        readonly=True,
    )

    currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Devise",
        readonly=True,
        store=True,
    )

    amount_due = fields.Monetary(
        string="Total dû",
        currency_field="currency_id",
        readonly=True,
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

    amount_paid = fields.Monetary(
        string="Total réglé",
        currency_field="currency_id",
        readonly=True,
    )

    balance = fields.Monetary(
        string="Reste total",
        currency_field="currency_id",
        readonly=True,
    )

    payment_state = fields.Selection(
        selection=[
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État du paiement",
        readonly=True,
    )

    last_payment_date = fields.Date(
        string="Dernier paiement",
        readonly=True,
    )

    @api.model
    def _refresh_open_reports_for_payment(self, payment):
        payment = payment.exists()

        if not payment:
            return True

        PaymentLine = self.env[
            "association.payment.line"
        ]

        for current_payment in payment:
            fee_reports = self.search([
                ("create_uid", "=", self.env.uid),
                ("member_id", "=", current_payment.member_id.id),
                ("membership_fee_id", "!=", False),
            ])
            for report in fee_reports:
                fee = report.membership_fee_id.sudo()
                paid = fee.amount_paid or 0.0
                balance = fee.amount_remaining or 0.0
                report.write({
                    "amount_paid": paid,
                    "balance": balance,
                    "payment_state": (
                        "paid" if balance <= 0.01
                        else "partial" if paid > 0.01 else "not_paid"
                    ),
                })

            for payment_line in current_payment.line_ids.filtered(
                "subscription_line_id"
            ):
                subscription_line = payment_line.subscription_line_id
                period = (
                    payment_line.subscription_period_id
                    or current_payment.subscription_period_id
                )

                if not subscription_line or not period:
                    continue

                reports = self.search(
                    [
                        (
                            "create_uid",
                            "=",
                            self.env.uid,
                        ),
                        (
                            "member_id",
                            "=",
                            subscription_line.member_id.id,
                        ),
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
                    ]
                )

                if not reports:
                    continue

                amount_paid_total = (
                    PaymentLine._get_period_paid_for_line(
                        subscription_line,
                        period,
                    )
                )

                breakdown = (
                    PaymentLine._get_period_amount_breakdown_for_line(
                        subscription_line,
                        period,
                        current_amount=0.0,
                        already_paid=amount_paid_total,
                    )
                )

                amount_paid = (
                    breakdown["contribution_paid_amount"]
                    + breakdown["penalty_paid_amount"]
                )

                balance = max(
                    breakdown["subscription_balance_amount"]
                    + breakdown["penalty_balance_amount"],
                    0.0,
                )

                if amount_paid <= 0:
                    payment_state = "not_paid"
                elif balance > 0.01:
                    payment_state = "partial"
                else:
                    payment_state = "paid"

                last_payment_line = PaymentLine.search(
                    [
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
                    ],
                    order="payment_date desc, id desc",
                    limit=1,
                )

                reports.write(
                    {
                        "amount_due": (
                            breakdown["base_amount_due"]
                            + breakdown["penalty_due_amount"]
                        ),

                        "base_amount_due":
                            breakdown[
                                "base_amount_due"
                            ],

                        "contribution_paid_amount":
                            amount_paid,

                        "subscription_balance_amount":
                            balance,

                        "penalty_due_amount":
                            breakdown[
                                "penalty_due_amount"
                            ],

                        "penalty_paid_amount":
                            breakdown[
                                "penalty_paid_amount"
                            ],

                        "penalty_balance_amount":
                            breakdown[
                                "penalty_balance_amount"
                            ],

                        "amount_paid":
                            amount_paid,

                        "balance":
                            balance,

                        "payment_state":
                            payment_state,

                        "last_payment_date":
                            (
                                last_payment_line.payment_id.payment_date
                                if last_payment_line
                                else False
                            ),
                    }
                )

        return True

    def _check_can_register_payment(self):
        if not any(
            self.env.user.has_group(xmlid)
            for xmlid in (
                "primetech_association.group_association_meeting_treasurer",
                "primetech_association.group_association_manager",
                "primetech_association.group_association_admin",
            )
        ):
            raise AccessError(
                _(
                    "Seul le trésorier, le responsable ou "
                    "l'administrateur peut enregistrer ce règlement."
                )
            )

    def action_register_payment(self):
        self.ensure_one()
        self._check_can_register_payment()

        if self.balance <= 0:
            raise ValidationError(
                _("Cet élément ne présente aucun reste à payer.")
            )

        # Sanctions, membership fees and adjustments are not attached to a
        # subscription: collect them through the member global payment,
        # which applies the usual priority order.
        if not self.subscription_line_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Règlement de la situation du membre"),
                "res_model": "association.subscription.payment.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_origin": "member",
                    "default_member_id": self.member_id.id,
                },
            }

        return {
            "type": "ir.actions.act_window",
            "name": _("Encaissement de cotisation"),
            "res_model": "association.subscription.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_origin": "subscription",
                "default_subscription_line_id":
                    self.subscription_line_id.id,
                "default_subscription_period_id":
                    self.subscription_period_id.id,
                "default_amount_received":
                    self.balance,
            },
        }

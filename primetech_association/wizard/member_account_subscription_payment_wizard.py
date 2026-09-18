# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MemberAccountSubscriptionPaymentWizard(models.TransientModel):
    _name = "association.member.account.subscription.payment.wizard"
    _description = "Confirmation paiement cotisation depuis compte membre"

    subscription_line_id = fields.Many2one(
        "association.subscription.line", required=True, readonly=True,
        ondelete="cascade", string="Cotisation du membre",
    )
    member_id = fields.Many2one(related="subscription_line_id.member_id", readonly=True)
    currency_id = fields.Many2one(related="subscription_line_id.currency_id", readonly=True)
    period_id = fields.Many2one(
        "association.subscription.period",
        compute="_compute_account_balance",
        readonly=True,
        string="Cycle à régler",
    )
    amount_due = fields.Monetary(
        compute="_compute_account_balance",
        currency_field="currency_id",
        readonly=True,
    )
    account_balance = fields.Monetary(
        compute="_compute_account_balance", currency_field="currency_id", readonly=True,
    )
    amount_to_pay = fields.Monetary(
        compute="_compute_account_balance", currency_field="currency_id", readonly=True,
    )

    @api.depends("subscription_line_id", "subscription_line_id.member_id")
    def _compute_account_balance(self):
        Account = self.env["association.member.account"]
        PaymentLine = self.env["association.payment.line"]
        for wizard in self:
            period = PaymentLine._get_unsettled_periods_for_line(
                wizard.subscription_line_id
            )[:1]

            amount_due = 0.0

            if period:
                due = PaymentLine._get_period_due_for_line(
                    wizard.subscription_line_id,
                    period,
                )
                paid = PaymentLine._get_period_paid_for_line(
                    wizard.subscription_line_id,
                    period,
                )
                amount_due = max(
                    due - paid,
                    0.0,
                )

            account = Account.search([
                ("member_id", "=", wizard.member_id.id),
                ("company_id", "=", wizard.subscription_line_id.company_id.id),
                ("active", "=", True),
            ], limit=1)
            wizard.period_id = period
            wizard.amount_due = amount_due
            wizard.account_balance = account.balance if account else 0.0
            wizard.amount_to_pay = min(
                wizard.account_balance or 0.0,
                wizard.amount_due or 0.0,
            )

    def action_confirm(self):
        self.ensure_one()
        # Do not validate the non-stored display computation here.  The
        # subscription-line workflow rereads the account balance under the
        # transaction lock immediately before creating the payment; that is
        # the authoritative validation and avoids a stale wizard cache.
        return self.subscription_line_id.with_context(
            skip_member_account_confirmation=True,
        ).action_pay_from_member_account()

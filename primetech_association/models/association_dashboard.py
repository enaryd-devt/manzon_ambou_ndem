# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class AssociationDashboard(models.AbstractModel):
    _name = "association.dashboard"
    _description = "Tableau de bord Association"

    # ==========================================================
    # DONNÉES DU TABLEAU DE BORD
    # ==========================================================

    @api.model
    def get_dashboard_data(self, options=None):

        if self.env.user.has_group("primetech_association.group_association_member"):
            return self._get_member_portal_data()

        company = self.env.company
        today = fields.Date.context_today(self)
        options = options or {}
        period = options.get("period", "all")
        months = int(options.get("months", 6) or 6)
        months = months if months in (3, 6, 12) else 6
        date_from = False
        if period == "month":
            date_from = today.replace(day=1)
        elif period == "quarter":
            date_from = today - relativedelta(months=3)
        elif period == "semester":
            date_from = today.replace(month=1, day=1) if today.month <= 6 else today.replace(month=7, day=1)
        elif period == "year":
            date_from = today.replace(month=1, day=1)
        elif period == "custom":
            date_from = fields.Date.to_date(options.get("date_from")) if options.get("date_from") else False
        date_to = fields.Date.to_date(options.get("date_to")) if options.get("date_to") else False

        Member = self.env["association.member"]
        Meeting = self.env["association.meeting"]
        Payment = self.env["association.payment"]
        Subscription = self.env["association.subscription"]
        Fund = self.env["association.fund"]
        Penalty = self.env["association.penalty"]
        Expense = self.env["association.expense"]
        FundTransaction = self.env["association.fund.transaction"]

        # ======================================================
        # MEMBRES
        # ======================================================

        member_domain = [
            ("company_id", "=", company.id),
        ]

        active_member_domain = member_domain + [
            ("state", "=", "active"),
        ]

        member_count = Member.search_count(
            member_domain
        )

        active_member_count = Member.search_count(
            active_member_domain
        )

        member_categories = []
        for group in Member.read_group(
            member_domain,
            ["category_id"],
            ["category_id"],
            lazy=False,
        ):
            category = group.get("category_id")
            member_categories.append({
                "name": category[1] if category else "Sans catégorie",
                "count": group["__count"],
                "percentage": round(
                    group["__count"] * 100 / member_count
                ) if member_count else 0,
            })
        member_categories.sort(
            key=lambda item: item["count"], reverse=True
        )

        # ======================================================
        # RÉUNIONS
        # ======================================================

        meeting_domain = [
            ("company_id", "=", company.id),
        ]

        upcoming_meeting_domain = meeting_domain + [
            ("meeting_date", ">=", today),
            (
                "state",
                "in",
                [
                    "draft",
                    "confirmed",
                ],
            ),
        ]

        upcoming_meeting_count = Meeting.search_count(
            upcoming_meeting_domain
        )

        next_meeting = Meeting.search(
            upcoming_meeting_domain,
            order="meeting_date asc, id asc",
            limit=1,
        )

        upcoming_meetings = Meeting.search(
            upcoming_meeting_domain,
            order="meeting_date asc, id asc",
            limit=4,
        )

        # ======================================================
        # DERNIÈRE RÉUNION / PRÉSENCES
        # ======================================================

        last_meeting = Meeting.search(
            meeting_domain,
            order="meeting_date desc, id desc",
            limit=1,
        )

        last_attendance_count = 0

        if last_meeting:

            attendance_lines = last_meeting.attendance_ids

            Attendance = self.env[
                "association.attendance"
            ]

            if "state" in Attendance._fields:

                present_states = {
                    "present",
                    "late",
                }

                last_attendance_count = len(
                    attendance_lines.filtered(
                        lambda line:
                        line.state in present_states
                    )
                )

        # ======================================================
        # COTISATIONS
        # ======================================================

        subscription_domain = [
            ("company_id", "=", company.id),
        ]

        subscription_count = Subscription.search_count(
            subscription_domain
        )

        pending_subscription_count = 0

        if (
            "association.subscription.line"
            in self.env
        ):

            SubscriptionLine = self.env[
                "association.subscription.line"
            ]

            pending_subscription_count = (
                SubscriptionLine.search_count(
                    [
                        (
                            "company_id",
                            "=",
                            company.id,
                        ),
                        (
                            "payment_state",
                            "!=",
                            "paid",
                        ),
                    ]
                )
            )

        # ======================================================
        # ENCAISSEMENTS
        # ======================================================

        payment_domain = [
            ("company_id", "=", company.id),
        ]
        if date_from:
            payment_domain.append(("payment_date", ">=", date_from))
        if date_to:
            payment_domain.append(("payment_date", "<=", date_to))

        payment_count = Payment.search_count(
            payment_domain
        )

        confirmed_payments = Payment.search(
            payment_domain + [
                (
                    "state",
                    "in",
                    [
                        "confirmed",
                        "collected",
                    ],
                ),
            ]
        )

        payment_total = sum(
            confirmed_payments.mapped("amount")
        )

        month_start = today.replace(day=1)
        payment_months = []
        month_names = [
            "Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin",
            "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc.",
        ]
        for offset in range(months - 1, -1, -1):
            start = month_start - relativedelta(months=offset)
            end = start + relativedelta(months=1)
            monthly_payments = Payment.search(payment_domain + [
                ("state", "in", ["collected", "confirmed"]),
                ("payment_date", ">=", start),
                ("payment_date", "<", end),
            ])
            payment_months.append({
                "month": month_names[start.month - 1],
                "amount": sum(monthly_payments.mapped("amount")),
                "count": len(monthly_payments),
            })

        expense_domain = [
            ("company_id", "=", company.id),
            ("state", "=", "validated"),
        ]
        if date_from:
            expense_domain.append(("expense_date", ">=", date_from))
        if date_to:
            expense_domain.append(("expense_date", "<=", date_to))
        validated_expenses = Expense.search(expense_domain)
        expense_total = sum(validated_expenses.mapped("amount"))
        expense_labels = dict(
            Expense._fields["expense_type"]._description_selection(self.env)
        )
        expense_totals = {}
        for expense in validated_expenses:
            expense_totals[expense.expense_type] = (
                expense_totals.get(expense.expense_type, 0.0)
                + expense.amount
            )
        expense_breakdown = [
            {
                "name": expense_labels.get(code, code or "Autre"),
                "amount": amount,
                "percentage": round(amount * 100 / expense_total)
                if expense_total else 0,
            }
            for code, amount in sorted(
                expense_totals.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
        ]

        # ======================================================
        # TRÉSORERIE
        # ======================================================

        fund_domain = [
            ("company_id", "=", company.id),
            ("active", "=", True),
        ]

        funds = Fund.search(
            fund_domain
        )

        # This is the liquidity actually available now: opening balances plus
        # validated entries minus validated exits, restricted to active funds.
        # It is deliberately not filtered by the dashboard period.
        treasury_balance = sum(funds.mapped("current_balance"))
        # Compatibility correction for meetings settled under the former
        # workflow: admission fees were credited directly to a fund although
        # the same cash still remained in the meeting pot.  They are not
        # liquid funds until the meeting makes its consolidated settlement.
        legacy_meeting_fee_receipts = FundTransaction.search([
            ("company_id", "=", company.id),
            ("origin_model", "=", "association.membership.fee"),
            ("state", "=", "validated"),
            ("fund_id.active", "=", True),
            ("payment_id.meeting_id", "!=", False),
            ("payment_id.meeting_id.pot_settlement_state", "!=", "settled"),
        ])
        treasury_balance -= sum(legacy_meeting_fee_receipts.mapped("amount"))

        # ======================================================
        # SITUATION FINANCIÈRE : UNE UNIQUE SOURCE COMPTABLE
        # ======================================================
        # Payments and expenses are operational documents.  The treasury
        # transaction is their validated accounting impact and prevents the
        # dashboard from showing a payment twice or an unvalidated expense.
        financial_domain = [
            ("company_id", "=", company.id),
            ("state", "=", "validated"),
        ]
        if date_from:
            financial_domain.append(("transaction_date", ">=", date_from))
        if date_to:
            financial_domain.append(("transaction_date", "<=", date_to))
        financial_transactions = FundTransaction.search(financial_domain)
        financial_in = sum(financial_transactions.filtered(
            lambda transaction: transaction.transaction_type == "in"
        ).mapped("amount"))
        financial_out = sum(financial_transactions.filtered(
            lambda transaction: transaction.transaction_type == "out"
        ).mapped("amount"))

        # ======================================================
        # DISCIPLINE
        # ======================================================

        penalty_domain = [
            ("company_id", "=", company.id),
        ]

        penalty_count = Penalty.search_count(
            penalty_domain
        )

        pending_penalty_count = Penalty.search_count(
            penalty_domain + [
                (
                    "state",
                    "in",
                    [
                        "draft",
                        "validated",
                        "executed",
                    ],
                ),
            ]
        )

        active_penalties = Penalty.search(
            penalty_domain + [
                ("state", "in", ["validated", "executed"]),
            ]
        )
        penalty_amount_remaining = sum(
            active_penalties.mapped("amount_remaining")
        )

        recent_penalties = Penalty.search(
            penalty_domain,
            order="incident_date desc, id desc",
            limit=5,
        )
        penalty_state_labels = dict(
            Penalty._fields["state"]._description_selection(self.env)
        )
        penalty_type_labels = dict(
            Penalty._fields["penalty_type"]._description_selection(self.env)
        )
        recent_penalty_values = [
            {
                "id": penalty.id,
                "name": penalty.name or "",
                "member": penalty.member_id.display_name or "",
                "type": penalty_type_labels.get(
                    penalty.penalty_type, penalty.penalty_type or ""
                ),
                "state": penalty_state_labels.get(
                    penalty.state, penalty.state or ""
                ),
                "state_code": penalty.state or "",
                "amount_remaining": penalty.amount_remaining or 0.0,
                "date": penalty.incident_date.strftime("%d/%m/%Y")
                if penalty.incident_date
                else "",
            }
            for penalty in recent_penalties
        ]

        # ======================================================
        # DERNIERS ENCAISSEMENTS
        # ======================================================

        recent_payments = Payment.search(
            payment_domain,
            order="payment_date desc, id desc",
            limit=5,
        )

        recent_payment_values = []

        for payment in recent_payments:

            recent_payment_values.append(
                {
                    "id":
                        payment.id,

                    "name":
                        payment.name or "",

                    "member":
                        (
                            payment.member_id.display_name
                            if payment.member_id
                            else ""
                        ),

                    "amount":
                        payment.amount or 0.0,

                    "state":
                        payment.state or "",

                    "date":
                        (
                            payment.payment_date.strftime(
                                "%d/%m/%Y"
                            )
                            if payment.payment_date
                            else ""
                        ),
                }
            )

        recent_members = Member.search(
            member_domain,
            order="join_date desc, id desc",
            limit=5,
        )
        recent_member_values = [
            {
                "id": member.id,
                "name": member.display_name or "",
                "state": dict(Member._fields["state"]._description_selection(self.env)).get(
                    member.state, member.state or ""
                ),
                "date": member.join_date.strftime("%d/%m/%Y")
                if member.join_date
                else "",
            }
            for member in recent_members
        ]

        upcoming_meeting_values = [
            {
                "id": meeting.id,
                "title": meeting.title or meeting.name or "",
                "date": meeting.meeting_date.strftime("%d/%m/%Y")
                if meeting.meeting_date
                else "",
                "time": dict(Meeting._fields["start_time"]._description_selection(self.env)).get(
                    meeting.start_time, meeting.start_time or ""
                ),
            }
            for meeting in upcoming_meetings
        ]

        # ======================================================
        # PROCHAINE RÉUNION
        # ======================================================

        next_meeting_value = False

        if next_meeting:

            next_meeting_value = {
                "id":
                    next_meeting.id,

                "name":
                    next_meeting.name or "",

                "date":
                    (
                        next_meeting.meeting_date.strftime(
                            "%d/%m/%Y"
                        )
                        if next_meeting.meeting_date
                        else ""
                    ),

                "location":
                    (
                        next_meeting.location
                        if hasattr(
                            next_meeting,
                            "location",
                        )
                        else ""
                    ),

                "state":
                    next_meeting.state or "",
            }

        # ======================================================
        # RÉSULTAT
        # ======================================================

        return {
            "user_name": self.env.user.name,
            "company": {
                "id":
                    company.id,

                "name":
                    company.display_name,
            },

            "members": {
                "total":
                    member_count,

                "active":
                    active_member_count,

                "categories": member_categories[:5],
            },

            "meetings": {
                "upcoming":
                    upcoming_meeting_count,

                "last_attendance":
                    last_attendance_count,
            },

            "subscriptions": {
                "total":
                    subscription_count,

                "pending":
                    pending_subscription_count,
            },

            "payments": {
                "count":
                    payment_count,

                "total":
                    payment_total,

                "monthly": payment_months,
            },

            "expenses": {
                "total": expense_total,
                "breakdown": expense_breakdown,
            },

            "treasury": {
                "balance":
                    treasury_balance,
            },

            "financial": {
                "in": financial_in,
                "out": financial_out,
                "net": financial_in - financial_out,
                "transaction_count": len(financial_transactions),
            },

            "penalties": {
                "total":
                    penalty_count,

                "pending":
                    pending_penalty_count,

                "active": len(active_penalties),

                "amount_remaining": penalty_amount_remaining,

                "recent": recent_penalty_values,
            },

            "recent_payments":
                recent_payment_values,

            "recent_members": recent_member_values,

            "upcoming_meetings": upcoming_meeting_values,

            "next_meeting":
                next_meeting_value,

            "currency": {
                "symbol":
                    company.currency_id.symbol or "",

                "position":
                    company.currency_id.position or "after",
            },
        }

    @api.model
    def _get_member_portal_data(self):
        """Small, read-only data set for an ordinary member."""
        company = self.env.company
        Member = self.env["association.member"].sudo()
        Payment = self.env["association.payment"].sudo()
        Penalty = self.env["association.penalty"].sudo()
        Fund = self.env["association.fund"].sudo()
        MemberAccount = self.env["association.member.account"].sudo()
        SubscriptionLine = self.env["association.subscription.line"].sudo()
        member = Member.search([
            ("user_id", "=", self.env.user.id), ("company_id", "=", company.id),
        ], limit=1)
        funds = Fund.search([("company_id", "=", company.id), ("active", "=", True)]).sorted(
            key=lambda fund: fund.current_balance or 0.0,
            reverse=True,
        )
        member_state_labels = dict(
            Member._fields["state"]._description_selection(self.env)
        )
        values = {
            "member_portal": True,
            "user_name": self.env.user.name,
            "user_id": self.env.user.id,
            "avatar_version": fields.Datetime.to_string(self.env.user.write_date) if self.env.user.write_date else "",
            "member_theme": self.env.user.association_member_theme or "system",
            "company": {"name": company.display_name},
            "currency": {"symbol": company.currency_id.symbol or ""},
            "member": False,
            "treasury_accounts": [],
            "directory": [],
            "shared_minutes": [],
            "shared_recovery_reports": [],
            "upcoming_meetings": [],
            "association_finance": {
                "expenses": {"total": 0.0, "count": 0, "items": []},
                "donations": {"total": 0.0, "count": 0, "items": []},
                "incomes": {"total": 0.0, "count": 0, "items": []},
            },
        }
        if not member:
            return values
        if member.state != "active" or not member.active:
            values["member"] = {
                "id": member.id,
                "name": member.display_name,
                "code": member.member_code or "",
                "is_active": False,
                "state": member_state_labels.get(member.state, member.state or ""),
            }
            return values

        # The member portal exposes only accounting documents that have been
        # validated.  Draft and cancelled documents stay strictly internal.
        Expense = self.env["association.expense"].sudo()
        Donation = self.env["association.donation"].sudo()
        Income = self.env["association.income"].sudo()
        expense_records = Expense.search([
            ("company_id", "=", company.id), ("state", "=", "validated"),
        ], order="expense_date desc, id desc")
        donation_records = Donation.search([
            ("company_id", "=", company.id), ("state", "=", "validated"),
        ], order="donation_date desc, id desc")
        income_records = Income.search([
            ("company_id", "=", company.id), ("state", "=", "validated"),
        ], order="income_date desc, id desc")
        donation_type_labels = dict(
            Donation._fields["donation_type"]._description_selection(self.env)
        )
        values["association_finance"] = {
            "expenses": {
                "total": sum(expense_records.mapped("amount")),
                "count": len(expense_records),
                "items": [{
                    "id": expense.id,
                    "name": expense.subject or expense.display_name,
                    "date": fields.Date.to_string(expense.expense_date) if expense.expense_date else "",
                    "amount": expense.amount or 0.0,
                } for expense in expense_records[:200]],
            },
            "donations": {
                "total": sum(
                    donation.amount if donation.donation_type == "financial"
                    else donation.estimated_value
                    for donation in donation_records
                ),
                "count": len(donation_records),
                "items": [{
                    "id": donation.id,
                    "name": donation.member_id.display_name or donation.donor_name or donation.display_name,
                    "date": fields.Date.to_string(donation.donation_date) if donation.donation_date else "",
                    "amount": (
                        donation.amount if donation.donation_type == "financial"
                        else donation.estimated_value
                    ) or 0.0,
                    "type": donation_type_labels.get(donation.donation_type, donation.donation_type or ""),
                } for donation in donation_records[:200]],
            },
            "incomes": {
                "total": sum(income_records.mapped("amount")),
                "count": len(income_records),
                "items": [{
                    "id": income.id,
                    "name": income.source_name or income.display_name,
                    "date": fields.Date.to_string(income.income_date) if income.income_date else "",
                    "amount": income.amount or 0.0,
                } for income in income_records[:200]],
            },
        }

        values["treasury_accounts"] = [{
            "id": fund.id,
            "name": fund.display_name,
            "balance": fund.current_balance,
        } for fund in funds]
        values["directory"] = [{
            "id": item.id,
            "name": item.display_name,
            "code": item.member_code or "",
            "state": member_state_labels.get(item.state, item.state or ""),
        } for item in Member.search([("company_id", "=", company.id), ("active", "=", True)], order="name")]
        Meeting = self.env["association.meeting"].sudo()
        values["upcoming_meetings"] = [{
            "id": meeting.id,
            "title": meeting.title or meeting.name or _("Réunion"),
            "date": fields.Date.to_string(meeting.meeting_date) if meeting.meeting_date else "",
        } for meeting in Meeting.search([
            ("company_id", "=", company.id),
            ("meeting_date", ">=", fields.Date.context_today(self)),
            ("state", "in", ("draft", "confirmed")),
        ], order="meeting_date, id", limit=3)]
        values["shared_minutes"] = [{
            "id": meeting.id,
            "title": meeting.title or meeting.name,
            "date": fields.Date.to_string(meeting.meeting_date) if meeting.meeting_date else "",
            "has_attachment": bool(meeting.minutes_attachment),
        } for meeting in Meeting.search([
            ("company_id", "=", company.id), ("minutes_shared", "=", True), ("minutes_approved", "=", True),
        ], order="meeting_date desc, id desc")]
        Session = self.env["association.meeting.subscription.session"].sudo()
        values["shared_recovery_reports"] = [{
            "id": session.id,
            "title": _("Rapport de recouvrement - %s") % (
                session.period_id.display_name or session.subscription_id.display_name or "",
            ),
            "date": fields.Date.to_string(session.closed_at.date()) if session.closed_at else "",
            "meeting": session.meeting_id.title or session.meeting_id.name or "",
        } for session in Session.search([
            ("company_id", "=", company.id), ("state", "=", "closed"),
            ("report_shared", "=", True),
        ], order="closed_at desc, id desc")]
        payments = Payment.search([("member_id", "=", member.id)], order="payment_date desc, id desc")
        # Ordinary members only see sanctions that have been formally validated
        # or executed. Draft and lifted/cancelled records stay internal.
        penalties = Penalty.search([
            ("member_id", "=", member.id),
            ("state", "in", ["validated", "executed"]),
        ], order="incident_date desc, id desc")
        member_account = MemberAccount.search([("member_id", "=", member.id)], limit=1)
        subscription_lines = SubscriptionLine.search([
            ("member_id", "=", member.id),
            ("active", "=", True), ("subscription_id.active", "=", True),
        ], order="subscription_id, id")
        payment_state_labels = dict(
            SubscriptionLine._fields["payment_state"]._description_selection(self.env)
        )
        financial_sanctions = penalties.filtered(
            lambda penalty: penalty.penalty_type == "fine" and (penalty.amount_remaining or 0.0) > 0
        )
        active_alert_sanctions = penalties.filtered(
            lambda penalty: not (
                penalty.penalty_type == "fine"
                and (penalty.amount_remaining or 0.0) <= 0.01
            )
        )
        def _member_penalty_state_label(penalty):
            if penalty.penalty_type == "fine" and (penalty.amount_remaining or 0.0) <= 0.01:
                return _("Levée")
            return _("En cours")
        Period = self.env["association.subscription.period"].sudo()
        PaymentLine = self.env["association.payment.line"].sudo()
        closed_cycles_due = recovery_due = no_cycle_due = cycle_penalties_due = 0.0
        for line in subscription_lines:
            periods = Period.search([
                ("subscription_id", "=", line.subscription_id.id),
            ], order="sequence, id")
            closed_periods = periods.filtered(lambda period: period.state == "closed")
            if periods:
                # A running period is deliberately not yet due to the member.
                for period in closed_periods:
                    paid = PaymentLine._get_period_paid_for_line(line, period)
                    breakdown = PaymentLine._get_period_amount_breakdown_for_line(
                        line, period, current_amount=0.0, already_paid=paid,
                    )
                    closed_cycles_due += max(breakdown["subscription_balance_amount"], 0.0)
                    cycle_penalties_due += max(breakdown["penalty_balance_amount"], 0.0)
            else:
                amount_due = (
                    line.recovery_amount if line.subscription_id.subscription_type == "recovery"
                    else line.subscription_id.amount
                ) or 0.0
                balance = max(amount_due - (line.amount_paid or 0.0), 0.0)
                if line.subscription_id.subscription_type == "recovery":
                    recovery_due += balance
                else:
                    no_cycle_due += balance
        subscription_penalty_count = len(subscription_lines.filtered(
            lambda line: (line.cycle_penalty_amount or 0.0) > 0
        ))
        values["member"] = {
            "id": member.id, "name": member.display_name, "code": member.member_code or "",
            "is_active": True,
            "account_balance": member_account.balance if member_account else 0.0,
            "account_name": member_account.name if member_account else "",
            "financial_situation": {
                "total_due": closed_cycles_due + recovery_due + no_cycle_due + cycle_penalties_due + sum(financial_sanctions.mapped("amount_remaining")),
                "label": _("Montant total dû"),
                "closed_cycles": closed_cycles_due,
                "recoveries": recovery_due,
                "without_cycle": no_cycle_due,
                "penalties": cycle_penalties_due + sum(financial_sanctions.mapped("amount_remaining")),
            },
            "payments_total": sum(payments.filtered(lambda p: p.state in ("collected", "confirmed")).mapped("amount")),
            "payment_count": len(payments),
            "penalty_count": len(penalties),
            "payments": [{"id": p.id, "name": p.name or "", "date": fields.Date.to_string(p.payment_date) if p.payment_date else "", "amount": p.amount, "state": p.state or ""} for p in payments],
            "financial_penalties": [{"id": p.id, "name": p.display_name, "amount": p.amount_remaining or 0.0, "state": _member_penalty_state_label(p)} for p in financial_sanctions],
            "financial_alert": {
                # A settled fine is a lifted sanction and must no longer
                # trigger the member alert.
                "sanction_count": len(active_alert_sanctions),
                "penalty_count": subscription_penalty_count,
            },
            "sanctions": [{
                "id": p.id,
                "name": p.display_name,
                "amount": (
                    p.amount_remaining
                    if (p.amount_remaining or 0.0) > 0.01
                    else (p.amount or 0.0)
                ) if p.penalty_type == "fine" else False,
                "state": _member_penalty_state_label(p),
                "type": _("Financière") if p.penalty_type == "fine" else _("Disciplinaire"),
                "type_code": "financial" if p.penalty_type == "fine" else "disciplinary",
                "is_lifted": p.penalty_type == "fine" and (p.amount_remaining or 0.0) <= 0.01,
                "is_active_alert": p in active_alert_sanctions,
            } for p in penalties],
            "subscriptions": [{
                "id": line.id,
                "name": line.subscription_id.display_name or "Cotisation",
                "cycle": line.current_period_id.display_name or "",
                "contribution_due": line.cycle_base_amount_due or 0.0,
                "penalty_due": line.cycle_penalty_amount or 0.0,
                "total_due": line.cycle_amount_due or line.amount_due or 0.0,
                "paid": line.amount_paid or 0.0,
                "balance": line.balance or 0.0,
                "state": payment_state_labels.get(line.payment_state, line.payment_state or ""),
            } for line in subscription_lines],
        }
        return values

    @api.model
    def set_member_theme(self, theme):
        """Save the mobile theme for the currently authenticated member."""
        allowed_themes = {"system", "ocean", "emerald", "violet", "sunset", "black"}
        if theme not in allowed_themes:
            return False
        user = self.env.user
        if not user.has_group("primetech_association.group_association_member"):
            return False
        # An ordinary member cannot write res.users directly.  The target is
        # always the authenticated user and only this harmless preference is
        # changed, so the elevation remains narrowly scoped.
        user.sudo().write({"association_member_theme": theme})
        return theme

    @api.model
    def update_member_profile_image(self, image):
        """Allow an ordinary member to update only their own profile photo."""
        user = self.env.user
        if not user.has_group("primetech_association.group_association_member"):
            return False
        if not image or not isinstance(image, str):
            return False
        user.sudo().write({"image_1920": image})
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", user.id),
            ("company_id", "=", self.env.company.id),
        ], limit=1)
        if member:
            member.write({"image_1920": image})
        # The browser caches /web/image aggressively.  Returning the write
        # timestamp lets the client request the refreshed avatar immediately.
        user.invalidate_recordset(["write_date"])
        return {
            "avatar_version": fields.Datetime.to_string(user.write_date) if user.write_date else "",
        }

    @api.model
    def get_member_global_finance_detail(self, document_type, document_id):
        """Return one validated association finance document to a member."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], limit=1)
        model_by_type = {
            "expense": "association.expense",
            "donation": "association.donation",
            "income": "association.income",
        }
        model = model_by_type.get(document_type)
        if not member or not model or not document_id:
            return False
        document = self.env[model].sudo().search([
            ("id", "=", document_id),
            ("company_id", "=", company.id),
            ("state", "=", "validated"),
        ], limit=1)
        if not document:
            return False
        if document_type == "expense":
            return {
                "title": document.subject or document.display_name,
                "category": dict(document._fields["expense_type"]._description_selection(self.env)).get(
                    document.expense_type, document.expense_type or ""
                ),
                "date": fields.Date.to_string(document.expense_date) if document.expense_date else "",
                "amount": document.amount or 0.0,
                "description": document.description or "",
            }
        if document_type == "donation":
            amount = document.amount if document.donation_type == "financial" else document.estimated_value
            donor = document.member_id.display_name or document.donor_name or _("Donateur anonyme")
            return {
                "title": donor,
                "category": dict(document._fields["donation_type"]._description_selection(self.env)).get(
                    document.donation_type, document.donation_type or ""
                ),
                "date": fields.Date.to_string(document.donation_date) if document.donation_date else "",
                "amount": amount or 0.0,
                "description": document.description or "",
            }
        return {
            "title": document.source_name or document.display_name,
            "category": dict(document._fields["income_type"]._description_selection(self.env)).get(
                document.income_type, document.income_type or ""
            ),
            "date": fields.Date.to_string(document.income_date) if document.income_date else "",
            "amount": document.amount or 0.0,
            "description": document.description or "",
        }

    @api.model
    def get_member_penalty_detail(self, penalty_id):
        """Return a member's own disciplinary record to the read-only dialog."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id), ("company_id", "=", company.id),
        ], limit=1)
        penalty = self.env["association.penalty"].sudo().search([
            ("id", "=", penalty_id), ("member_id", "=", member.id),
            ("state", "in", ["validated", "executed"]),
        ], limit=1)
        if not penalty:
            return False
        type_labels = dict(penalty._fields["penalty_type"]._description_selection(self.env))
        incident_labels = dict(penalty._fields["incident_type"]._description_selection(self.env))
        state_labels = dict(penalty._fields["state"]._description_selection(self.env))
        return {
            "id": penalty.id,
            "name": penalty.display_name or "",
            "is_financial": penalty.penalty_type == "fine",
            "type": type_labels.get(penalty.penalty_type, penalty.penalty_type or ""),
            "state": state_labels.get(penalty.state, penalty.state or ""),
            "incident": incident_labels.get(penalty.incident_type, penalty.incident_type or ""),
            "date": fields.Datetime.to_string(penalty.incident_date) if penalty.incident_date else "",
            "description": penalty.penalty_description or "",
            "incident_description": penalty.incident_description or "",
            "amount": penalty.amount or 0.0,
            "paid": penalty.amount_paid or 0.0,
            "remaining": penalty.amount_remaining or 0.0,
        }

    @api.model
    def get_member_subscription_detail(self, subscription_line_id):
        """Return one participating subscription to the member's JS dialog."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id), ("company_id", "=", company.id),
        ], limit=1)
        line = self.env["association.subscription.line"].sudo().search([
            ("id", "=", subscription_line_id), ("member_id", "=", member.id),
        ], limit=1)
        if not line:
            return False
        labels = dict(line._fields["payment_state"]._description_selection(self.env))
        return {
            "id": line.id,
            "name": line.subscription_id.display_name or "Cotisation",
            "cycle": line.current_period_id.display_name or "",
            "state": labels.get(line.payment_state, line.payment_state or ""),
            "contribution_due": line.cycle_base_amount_due or 0.0,
            "penalty_due": line.cycle_penalty_amount or 0.0,
            "total_due": line.cycle_amount_due or line.amount_due or 0.0,
            "paid": line.amount_paid or 0.0,
            "balance": line.balance or 0.0,
            "last_payment_date": fields.Date.to_string(line.payment_date) if line.payment_date else "",
        }

    @api.model
    def get_member_treasury_detail(self, fund_id):
        """Provide a transparency view of a treasury account to members."""
        company = self.env.company
        fund = self.env["association.fund"].sudo().search([
            ("id", "=", fund_id), ("company_id", "=", company.id),
        ], limit=1)
        if not fund:
            return False
        Transaction = self.env["association.fund.transaction"].sudo()
        transactions = Transaction.search([
            ("fund_id", "=", fund.id), ("state", "=", "validated"),
        ], order="transaction_date desc, id desc", limit=30)
        return {
            "id": fund.id,
            "name": fund.display_name,
            "balance": fund.current_balance or 0.0,
            "transactions": [{
                "id": transaction.id,
                "date": fields.Date.to_string(transaction.transaction_date) if transaction.transaction_date else "",
                "description": transaction.description or transaction.name or "Mouvement de trésorerie",
                "type": transaction.transaction_type,
                "amount": transaction.amount or 0.0,
            } for transaction in transactions],
        }

    @api.model
    def get_member_payment_detail(self, payment_id):
        """Return only the selected member's payment data for the JS dialog."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("company_id", "=", company.id),
        ], limit=1)
        payment = self.env["association.payment"].sudo().search([
            ("id", "=", payment_id),
            ("member_id", "=", member.id),
        ], limit=1)
        if not payment:
            return False
        method_labels = dict(
            payment._fields["payment_method"]._description_selection(self.env)
        )
        return {
            "id": payment.id,
            "reference": payment.name or "",
            "date": fields.Date.to_string(payment.payment_date) if payment.payment_date else "",
            "amount": payment.amount or 0.0,
            "method": method_labels.get(payment.payment_method, payment.payment_method or ""),
            "external_reference": payment.payment_reference or "",
            "account": payment.receipt_account_id.display_name or "",
            "description": payment.description or "",
            "allocations": [{
                "name": line.subscription_id.display_name or line.subscription_line_id.subscription_id.display_name or "Cotisation",
                "amount": line.amount_paid or 0.0,
                "balance": line.balance_after_payment or 0.0,
            } for line in payment.line_ids],
        }

    @api.model
    def get_member_payment_receipt_download_action(self, payment_id):
        """Return a receipt action only for the logged-in member's payment."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], limit=1)
        if not member:
            return False
        payment = self.env["association.payment"].sudo().search([
            ("id", "=", payment_id),
            ("member_id", "=", member.id),
            ("state", "in", ["collected", "confirmed"]),
        ], limit=1)
        if not payment:
            return False
        return self.env.ref(
            "primetech_association.action_report_payment_receipt"
        ).report_action(payment)

    @api.model
    def get_member_minutes_preview(self, meeting_id):
        """Return a shared meeting minute only to its active ordinary member."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], limit=1)
        if not member:
            return False

        meeting = self.env["association.meeting"].sudo().search([
            ("id", "=", meeting_id),
            ("company_id", "=", company.id),
            ("minutes_shared", "=", True),
            ("minutes_approved", "=", True),
        ], limit=1)
        if not meeting:
            return False
        return {
            "id": meeting.id,
            "title": meeting.title or meeting.name or _("Procès-verbal"),
            "date": fields.Date.to_string(meeting.meeting_date) if meeting.meeting_date else "",
            "content": meeting.minutes or _("Le contenu de ce procès-verbal n’est pas disponible."),
            "has_attachment": bool(meeting.minutes_attachment),
        }

    @api.model
    def get_member_minutes_download_action(self, meeting_id):
        """Build the server PDF action for a minute visible to this member."""
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
        ], limit=1)
        if not member:
            return False
        meeting = self.env["association.meeting"].sudo().search([
            ("id", "=", meeting_id),
            ("company_id", "=", company.id),
            ("minutes_shared", "=", True),
            ("minutes_approved", "=", True),
        ], limit=1)
        if not meeting:
            return False
        return self.env.ref(
            "primetech_association.action_report_meeting_minutes"
        ).report_action(meeting)

    @api.model
    def _get_shared_recovery_session(self, session_id):
        company = self.env.company
        member = self.env["association.member"].sudo().search([
            ("user_id", "=", self.env.user.id), ("company_id", "=", company.id),
            ("state", "=", "active"), ("active", "=", True),
        ], limit=1)
        if not member:
            return self.env["association.meeting.subscription.session"]
        return self.env["association.meeting.subscription.session"].sudo().search([
            ("id", "=", session_id), ("company_id", "=", company.id),
            ("state", "=", "closed"), ("report_shared", "=", True),
        ], limit=1)

    @api.model
    def get_member_recovery_report_preview(self, session_id):
        session = self._get_shared_recovery_session(session_id)
        if not session:
            return False
        return {
            "id": session.id,
            "title": _("Rapport de recouvrement - %s") % (
                session.period_id.display_name or session.subscription_id.display_name or "",
            ),
            "date": fields.Date.to_string(session.closed_at.date()) if session.closed_at else "",
            "meeting": session.meeting_id.title or session.meeting_id.name or "",
            "expected": session.closed_expected_amount or 0.0,
            "collected": session.closed_collected_amount or 0.0,
            "participants": len(session.snapshot_ids),
            "currency": session.currency_id.symbol or "",
        }

    @api.model
    def get_member_recovery_report_download_action(self, session_id):
        session = self._get_shared_recovery_session(session_id)
        if not session:
            return False
        return self.env.ref(
            "primetech_association.action_report_meeting_subscription_session"
        ).report_action(session)

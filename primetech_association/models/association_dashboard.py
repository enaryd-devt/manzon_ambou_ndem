# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


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
        ]

        funds = Fund.search(
            fund_domain
        )

        treasury_balance = 0.0

        # ------------------------------------------------------
        # DÉTECTION DU CHAMP DE SOLDE
        # ------------------------------------------------------

        if "balance" in Fund._fields:

            treasury_balance = sum(
                funds.mapped("balance")
            )

        elif "current_balance" in Fund._fields:

            treasury_balance = sum(
                funds.mapped("current_balance")
            )

        elif "amount" in Fund._fields:

            treasury_balance = sum(
                funds.mapped("amount")
            )

        else:

            # ==================================================
            # CALCUL DEPUIS LES MOUVEMENTS FINANCIERS
            # ==================================================

            if (
                "association.fund.transaction"
                in self.env
            ):

                FundTransaction = self.env[
                    "association.fund.transaction"
                ]

                transaction_domain = []

                if "company_id" in FundTransaction._fields:

                    transaction_domain.append(
                        (
                            "company_id",
                            "=",
                            company.id,
                        )
                    )

                transactions = FundTransaction.search(
                    transaction_domain
                )

                for transaction in transactions:

                    # ------------------------------------------
                    # IGNORER LES MOUVEMENTS NON VALIDÉS
                    # ------------------------------------------

                    if "state" in FundTransaction._fields:

                        if transaction.state in (
                            "draft",
                            "cancel",
                            "cancelled",
                        ):

                            continue

                    # ------------------------------------------
                    # MONTANT
                    # ------------------------------------------

                    amount = transaction.amount or 0.0

                    # ------------------------------------------
                    # TYPE DE MOUVEMENT
                    # ------------------------------------------

                    transaction_type = False

                    if "transaction_type" in FundTransaction._fields:

                        transaction_type = (
                            transaction.transaction_type
                        )

                    elif "type" in FundTransaction._fields:

                        transaction_type = (
                            transaction.type
                        )

                    # ------------------------------------------
                    # CALCUL
                    # ------------------------------------------

                    if transaction_type in (
                        "debit",
                        "expense",
                        "out",
                        "withdrawal",
                    ):

                        treasury_balance -= amount

                    else:

                        treasury_balance += amount

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
        funds = Fund.search([("company_id", "=", company.id), ("active", "=", True)], order="sequence, name")
        values = {
            "member_portal": True,
            "user_name": self.env.user.name,
            "company": {"name": company.display_name},
            "currency": {"symbol": company.currency_id.symbol or ""},
            "member": False,
            "treasury_accounts": [{"id": fund.id, "name": fund.display_name, "balance": fund.current_balance} for fund in funds],
            "directory": [{"id": item.id, "name": item.display_name, "code": item.member_code or ""} for item in Member.search([("company_id", "=", company.id), ("active", "=", True)], order="name")],
        }
        if not member:
            return values
        payments = Payment.search([("member_id", "=", member.id)], order="payment_date desc, id desc")
        penalties = Penalty.search([("member_id", "=", member.id)], order="id desc")
        member_account = MemberAccount.search([("member_id", "=", member.id)], limit=1)
        subscription_lines = SubscriptionLine.search([
            ("member_id", "=", member.id),
            ("active", "=", True),
        ], order="subscription_id, id")
        payment_state_labels = dict(
            SubscriptionLine._fields["payment_state"]._description_selection(self.env)
        )
        values["member"] = {
            "id": member.id, "name": member.display_name, "code": member.member_code or "",
            "account_balance": member_account.balance if member_account else 0.0,
            "account_name": member_account.name if member_account else "",
            "payments_total": sum(payments.filtered(lambda p: p.state in ("collected", "confirmed")).mapped("amount")),
            "payment_count": len(payments), "penalty_count": len(penalties),
            "payments": [{"id": p.id, "name": p.name or "", "date": fields.Date.to_string(p.payment_date) if p.payment_date else "", "amount": p.amount, "state": p.state or ""} for p in payments],
            "penalties": [{"id": p.id, "name": p.display_name, "amount": p.amount_remaining if "amount_remaining" in p._fields else 0.0, "state": p.state or ""} for p in penalties],
            "subscriptions": [{
                "id": line.id,
                "name": line.subscription_id.display_name or "Cotisation",
                "cycle": line.current_period_id.display_name or "",
                "due": line.amount_due or 0.0,
                "paid": line.amount_paid or 0.0,
                "balance": line.balance or 0.0,
                "state": payment_state_labels.get(line.payment_state, line.payment_state or ""),
            } for line in subscription_lines],
        }
        return values

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

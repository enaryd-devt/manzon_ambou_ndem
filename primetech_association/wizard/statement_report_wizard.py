# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_amount


class AssociationStatementReportWizard(models.TransientModel):
    _name = "association.statement.report.wizard"
    _description = "Assistant de rapports et relevés"

    def _can_use_discipline_reports(self):
        return (
            self.env.user.has_group(
                "primetech_association.group_association_manager"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_admin"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_meeting_president"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_meeting_censor"
            )
        )

    def _get_report_type_selection(self):
        selection = [
            ("member_account", "Relevé de compte membre"),
            ("fund", "Relevé de compte de trésorerie"),
            ("committee", "Bureau exécutif"),
        ]
        if self._can_use_discipline_reports():
            selection.extend([
                ("discipline_member", "Discipline et sanctions par membre"),
                (
                    "discipline_global",
                    "Rapport global de discipline et sanctions",
                ),
            ])
        return selection

    report_type = fields.Selection(
        selection="_get_report_type_selection",
        required=True,
        default="member_account",
        string="Document",
    )
    date_from = fields.Date(string="Du", required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date(string="Au", required=True, default=fields.Date.context_today)
    member_id = fields.Many2one("association.member", string="Membre")
    member_account_id = fields.Many2one("association.member.account", string="Compte membre", domain="[('member_id', '=', member_id)]")
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie")
    committee_id = fields.Many2one("association.committee", string="Bureau exécutif")

    def _check_parameters(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_("La date de début doit précéder la date de fin."))
        if (
            self.report_type.startswith("discipline")
            and not self._can_use_discipline_reports()
        ):
            raise ValidationError(
                _("Vous n'êtes pas autorisé à imprimer ce rapport.")
            )
        required = {
            "member_account": self.member_account_id,
            "fund": self.fund_id,
            "committee": self.committee_id,
            "discipline_member": self.member_id,
        }
        if self.report_type in required and not required[self.report_type]:
            raise ValidationError(_("Sélectionnez l'élément à imprimer."))

    def action_print(self):
        self._check_parameters()
        return self.env.ref("primetech_association.action_report_statement").report_action(self)

    def is_account_report(self):
        self.ensure_one()
        return self.report_type in (
            "member_account",
            "fund",
        )

    def _get_report_currency(self):
        self.ensure_one()

        if self.report_type == "member_account" and self.member_account_id:
            return self.member_account_id.currency_id

        if self.report_type == "fund" and self.fund_id:
            return self.fund_id.currency_id

        return self.env.company.currency_id

    def _format_report_amount(self, amount, blank_if_zero=False):
        self.ensure_one()

        amount = amount or 0.0

        if blank_if_zero and not amount:
            return ""

        return format_amount(
            self.env,
            amount,
            self._get_report_currency() or self.env.company.currency_id,
        )

    def _get_account_opening_balance(self):
        self.ensure_one()

        if self.report_type == "member_account":
            transactions = self.env[
                "association.member.account.transaction"
            ].search(
                [
                    (
                        "account_id",
                        "=",
                        self.member_account_id.id,
                    ),
                    (
                        "transaction_date",
                        "<",
                        self.date_from,
                    ),
                    (
                        "state",
                        "=",
                        "validated",
                    ),
                ]
            )

            credit = sum(
                transactions.filtered(
                    lambda line: line.transaction_type == "credit"
                ).mapped("amount")
            )
            debit = sum(
                transactions.filtered(
                    lambda line: line.transaction_type == "debit"
                ).mapped("amount")
            )

            return credit - debit

        if self.report_type == "fund":
            transactions = self.env[
                "association.fund.transaction"
            ].search(
                [
                    (
                        "fund_id",
                        "=",
                        self.fund_id.id,
                    ),
                    (
                        "transaction_date",
                        "<",
                        self.date_from,
                    ),
                    (
                        "state",
                        "=",
                        "validated",
                    ),
                ]
            )

            credit = sum(
                transactions.filtered(
                    lambda line: line.transaction_type == "in"
                ).mapped("amount")
            )
            debit = sum(
                transactions.filtered(
                    lambda line: line.transaction_type == "out"
                ).mapped("amount")
            )

            return (
                (self.fund_id.initial_balance or 0.0)
                + credit
                - debit
            )

        return 0.0

    def _get_account_report_lines(self):
        self.ensure_one()

        rows = []
        balance = self._get_account_opening_balance()

        rows.append(
            {
                "date":
                    self.date_from,

                "reference":
                    "",

                "description":
                    _("Solde initial"),

                "debit":
                    "",

                "credit":
                    "",

                "balance":
                    self._format_report_amount(balance),

                "is_opening":
                    True,
            }
        )

        for line in self.get_lines():
            amount = line.amount or 0.0

            if self.report_type == "member_account":
                debit_amount = (
                    amount
                    if line.transaction_type == "debit"
                    else 0.0
                )
                credit_amount = (
                    amount
                    if line.transaction_type == "credit"
                    else 0.0
                )

            else:
                debit_amount = (
                    amount
                    if line.transaction_type == "out"
                    else 0.0
                )
                credit_amount = (
                    amount
                    if line.transaction_type == "in"
                    else 0.0
                )

            balance += credit_amount - debit_amount

            rows.append(
                {
                    "date":
                        line.transaction_date,

                    "reference":
                        line.name or "",

                    "description":
                        line.description or "",

                    "debit":
                        self._format_report_amount(
                            debit_amount,
                            blank_if_zero=True,
                        ),

                    "credit":
                        self._format_report_amount(
                            credit_amount,
                            blank_if_zero=True,
                        ),

                    "balance":
                        self._format_report_amount(balance),

                    "is_opening":
                        False,
                }
            )

        return rows

    def _get_discipline_report_lines(self):
        self.ensure_one()

        Penalty = self.env["association.penalty"]
        penalty_type_labels = dict(
            Penalty._fields["penalty_type"]._description_selection(self.env)
        )
        penalty_state_labels = dict(
            Penalty._fields["state"]._description_selection(self.env)
        )
        payment_state_labels = dict(
            Penalty._fields["payment_state"]._description_selection(self.env)
        )

        rows = []

        for line in self.get_lines():
            penalty_type = penalty_type_labels.get(
                line.penalty_type,
                line.penalty_type or "",
            )
            penalty_state = penalty_state_labels.get(
                line.state,
                line.state or "",
            )
            payment_state = payment_state_labels.get(
                line.payment_state,
                line.payment_state or "",
            )

            description_parts = [
                part
                for part in [
                    penalty_type,
                    line.penalty_description,
                ]
                if part
            ]

            if line.penalty_type == "fine":
                value = "%s - %s" % (
                    self._format_report_amount(line.amount),
                    payment_state,
                )
            else:
                value = "%s - %s" % (
                    _("Non payable"),
                    penalty_state,
                )

            rows.append(
                {
                    "date":
                        line.incident_date,

                    "reference":
                        line.member_id.display_name or line.name or "",

                    "description":
                        " - ".join(description_parts),

                    "value":
                        value,
                }
            )

        return rows

    def get_lines(self):
        self.ensure_one()
        if self.report_type == "member_account":
            return self.env["association.member.account.transaction"].search([
                ("account_id", "=", self.member_account_id.id),
                ("transaction_date", ">=", self.date_from), ("transaction_date", "<=", self.date_to),
                ("state", "=", "validated"),
            ], order="transaction_date,id")
        if self.report_type == "fund":
            return self.env["association.fund.transaction"].search([
                ("fund_id", "=", self.fund_id.id),
                ("transaction_date", ">=", self.date_from), ("transaction_date", "<=", self.date_to),
                ("state", "=", "validated"),
            ], order="transaction_date,id")
        if self.report_type.startswith("discipline"):
            domain = [("incident_date", ">=", self.date_from), ("incident_date", "<=", self.date_to)]
            if self.report_type == "discipline_member":
                domain.append(("member_id", "=", self.member_id.id))
            return self.env["association.penalty"].search(domain, order="incident_date,id")
        return self.committee_id.member_line_ids

    def get_report_lines(self):
        if self.is_account_report():
            return self._get_account_report_lines()

        if self.report_type.startswith("discipline"):
            return self._get_discipline_report_lines()

        rows = []
        for line in self.get_lines():
            date_or_number = (
                getattr(line, "transaction_date", False)
                or getattr(line, "incident_date", False)
                or getattr(line, "sequence", "")
            )
            member = getattr(line, "member_id", False)
            function = getattr(line, "function_id", False)
            rows.append({
                "date": date_or_number,
                "reference": member.display_name if member else getattr(line, "name", ""),
                "description": (
                    getattr(line, "description", False)
                    or getattr(line, "penalty_description", False)
                    or (function.display_name if function else "")
                ),
                "value": (
                    getattr(line, "amount", False)
                    or getattr(line, "penalty_amount", False)
                    or getattr(line, "state", "")
                ),
            })
        return rows

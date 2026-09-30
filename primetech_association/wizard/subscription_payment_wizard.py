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
from odoo.tools import html_escape


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

    use_member_account = fields.Boolean(
        string="Régler depuis le compte membre",
        default=False,
    )

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement généré",
        readonly=True,
    )
    global_due_amount = fields.Monetary(
        string="Total à régler", currency_field="currency_id", readonly=True,
    )
    global_lines_html = fields.Html(string="Recouvrements en cours", readonly=True)

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
        payment_origin = self.env.context.get("default_origin", "subscription")

        if subscription.state != "running":
            raise ValidationError(
                _("La cotisation %(subscription)s n'est pas en cours et ne peut pas être réglée.")
                % {"subscription": subscription.display_name}
            )

        # ======================================================
        # PREMIER CYCLE NON SOLDÉ
        # ======================================================

        PaymentLine = self.env[
            "association.payment.line"
        ]

        # Un recouvrement est une dette unique par membre : il ne possède
        # volontairement aucun cycle. Les montants calculés sur la ligne
        # servent directement à initialiser l'assistant.
        if (
            subscription.subscription_type == "recovery"
            and payment_origin != "meeting"
        ):
            amount_due = subscription_line.amount_due or 0.0
            amount_paid = subscription_line.amount_paid or 0.0
            balance = subscription_line.balance or 0.0
            if balance <= 0.01:
                raise ValidationError(_("Ce recouvrement ne présente aucun reste à payer."))
            values.update({
                "member_id": subscription_line.member_id.id,
                "subscription_line_id": subscription_line.id,
                "period_id": False,
                "amount_due": amount_due,
                "amount_paid": amount_paid,
                "balance": balance,
                "amount_received": self.env.context.get("default_amount_received", balance),
                "receipt_account_id": subscription.receipt_account_id.id,
                "origin": self.env.context.get("default_origin", "subscription"),
                "meeting_id": self.env.context.get("default_meeting_id") or False,
            })
            return values

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
                and requested_period.state == "running"
            ):

                period = requested_period

        if not period:

            periods = PaymentLine._get_unsettled_periods_for_line(
                subscription_line
            )

            period = periods[:1]

        if not period and payment_origin != "meeting":
            raise ValidationError(
                _(
                    "Aucun cycle en cours avec "
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

        if period:
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
        else:
            amount_due = 0.0
            amount_paid = 0.0
            balance = 0.0

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

        # During a meeting, the member is called once: load every unpaid
        # subscription/cycle, including penalties, into the same payment.
        global_due = 0.0
        global_rows = []
        if payment_origin in ("meeting", "subscription"):
            Penalty = self.env["association.penalty"]
            priority_penalties = Penalty.search([
                ("member_id", "=", subscription_line.member_id.id),
                ("company_id", "=", subscription_line.company_id.id),
                ("penalty_type", "=", "fine"),
                ("state", "in", ("validated", "executed")),
                ("amount_remaining", ">", 0),
            ], order="recovery_priority asc, incident_date asc, id asc")
            for penalty in priority_penalties:
                global_due += penalty.amount_remaining or 0.0
                label = "Sanction financière"
                global_rows.append("<tr class='table-warning'><td>%s</td><td>%s</td><td class='text-end'>%.2f</td></tr>" % (
                    html_escape(label),
                    html_escape(penalty.penalty_description or penalty.display_name),
                    penalty.amount_remaining or 0.0,
                ))
            MembershipFee = self.env["association.membership.fee"]
            membership_fees = MembershipFee.search([
                ("member_id", "=", subscription_line.member_id.id),
                ("company_id", "=", subscription_line.company_id.id),
                ("state", "=", "due"),
                ("amount_remaining", ">", 0),
            ])
            for fee in membership_fees:
                global_due += fee.amount_remaining or 0.0
                global_rows.append("<tr class='table-info'><td>Frais d’adhésion</td><td>%s</td><td class='text-end'>%.2f</td></tr>" % (
                    html_escape(fee.name), fee.amount_remaining or 0.0,
                ))
            if payment_origin == "meeting":
                SubscriptionLine = self.env["association.subscription.line"]
                lines = SubscriptionLine.search([
                    ("member_id", "=", subscription_line.member_id.id),
                    ("company_id", "=", subscription_line.company_id.id),
                    ("active", "=", True),
                    ("subscription_id.active", "=", True),
                    ("subscription_id.state", "=", "running"),
                ])
            else:
                lines = subscription_line
            if payment_origin == "meeting":
                # The global meeting assistant deliberately hides the technical
                # cycles.  The same complete balance used by the treasury line
                # is exposed as a responsibility by contribution instead.
                Situation = self.env["association.meeting.member.situation"]
                for line in lines:
                    balance = Situation._get_subscription_line_balance(line)
                    if balance <= 0.01:
                        continue
                    global_due += balance
                    category = (
                        "Recouvrement"
                        if line.subscription_id.subscription_type == "recovery"
                        else "Cotisation"
                    )
                    global_rows.append(
                        "<tr><td>%s</td><td>%s</td><td class='text-end'>%.2f</td></tr>"
                        % (
                            html_escape(category),
                            html_escape(line.subscription_id.display_name),
                            balance,
                        )
                    )
            else:
                for line in lines:
                    if line.subscription_id.subscription_type == "recovery":
                        balance = line.balance or 0.0
                        if balance > 0.01:
                            global_due += balance
                            global_rows.append("<tr><td>%s</td><td>Échéance : %s</td><td class='text-end'>%.2f</td></tr>" % (
                                html_escape(line.subscription_id.display_name or "Recouvrement"),
                                line.subscription_id.due_date or "-", balance,
                            ))
                        continue
                    for line_period in PaymentLine._get_unsettled_periods_for_line(line):
                        due = PaymentLine._get_period_due_for_line(line, line_period)
                        paid = PaymentLine._get_period_paid_for_line(line, line_period)
                        balance = max(due - paid, 0.0)
                        if balance > 0.01:
                            global_due += balance
                            global_rows.append("<tr><td>%s</td><td>%s</td><td class='text-end'>%.2f</td></tr>" % (
                                html_escape(line.subscription_id.display_name or "Cotisation"),
                                html_escape(line_period.display_name or "Cycle"), balance,
                            ))
            amount_received = global_due if default_amount_received in (None, False) else max(default_amount_received or 0.0, 0.0)
        values.update(
            {
                "member_id":
                    subscription_line.member_id.id,

                "subscription_line_id":
                    subscription_line.id,

                "period_id":
                    period.id if period else False,

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
                "global_due_amount": global_due,
                "global_lines_html": ("<table class='table table-sm'><thead><tr><th>Créance</th><th>Détail</th><th class='text-end'>Reste à régler</th></tr></thead><tbody>%s</tbody></table><small class='text-muted'>Ordre de règlement : sanctions, frais d’activation, puis cotisations.</small>" % "".join(global_rows)) if global_rows else False,
            }
        )

        if global_rows:
            values["global_lines_html"] = (
                "<table class='table table-sm'><thead><tr><th>Créance</th><th>Détail</th>"
                "<th class='text-end'>Reste à régler</th></tr></thead><tbody>%s</tbody></table>"
                "<small class='text-muted'>Ordre de règlement : sanctions, frais d’adhésion, puis cotisations.</small>"
            ) % "".join(global_rows)
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

    def _action_validate_prioritized_payment(self):
        """Collect all outstanding dues for one member during a meeting."""
        self.ensure_one()
        if not self.member_id or not self.subscription_line_id:
            raise ValidationError(_("Le membre et la cotisation sont obligatoires."))
        company = self.meeting_id.company_id if self.meeting_id else self.subscription_line_id.company_id
        amount_received = self.amount_received or 0.0
        if amount_received <= 0:
            raise ValidationError(_("Le montant reçu doit être strictement supérieur à zéro."))
        PaymentLine = self.env["association.payment.line"]
        SubscriptionLine = self.env["association.subscription.line"]
        Penalty = self.env["association.penalty"]
        payment_source = "meeting_cash" if self.meeting_id else "external"
        member_account = False
        if self.use_member_account:
            member_account = self.env["association.member.account"].search([
                ("member_id", "=", self.member_id.id),
                ("company_id", "=", company.id),
                ("active", "=", True),
            ], limit=1)
            if not member_account or (member_account.balance or 0.0) <= 0:
                raise ValidationError(_("Le compte membre ne dispose d’aucun solde disponible."))
            amount_received = min(amount_received, member_account.balance or 0.0)
            payment_source = "member_account"
        remaining = amount_received
        allocation_values = []
        priority_allocations = []

        # Ordre impératif : sanctions disciplinaires financières, puis frais
        # d'activation, avant la moindre cotisation.
        priority_penalties = Penalty.search([
            ("member_id", "=", self.member_id.id),
            ("company_id", "=", company.id),
            ("penalty_type", "=", "fine"),
            ("state", "in", ("validated", "executed")),
            ("amount_remaining", ">", 0),
        ], order="recovery_priority asc, incident_date asc, id asc")
        for penalty in priority_penalties:
            if remaining <= 0:
                break
            allocated = min(remaining, penalty.amount_remaining or 0.0)
            if allocated > 0:
                priority_allocations.append({"penalty_id": penalty.id, "amount": allocated})
                remaining -= allocated

        # The mandated order only applies to payments collected in a meeting:
        # sanctions, subscription cycles (oldest first), then recoveries.
        # Membership fees must not consume an amount before that sequence.
        is_meeting_payment = self.origin == "meeting" and bool(self.meeting_id)
        membership_fee_allocations = []
        MembershipFee = self.env["association.membership.fee"]
        membership_fees = MembershipFee.search([
            ("member_id", "=", self.member_id.id),
            ("company_id", "=", company.id),
            ("state", "=", "due"),
            ("amount_remaining", ">", 0),
        ], order="id asc")
        # Preserve the established allocation order outside a meeting.
        if not is_meeting_payment:
            for fee in membership_fees:
                if remaining <= 0:
                    break
                allocated = min(remaining, fee.amount_remaining or 0.0)
                if allocated > 0:
                    membership_fee_allocations.append({"membership_fee_id": fee.id, "amount": allocated})
                    remaining -= allocated

        candidates = []
        if self.origin == "meeting":
            lines = SubscriptionLine.search([
                ("member_id", "=", self.member_id.id),
                ("company_id", "=", company.id), ("active", "=", True),
                ("subscription_id.state", "=", "running"),
            ])
        else:
            lines = self.subscription_line_id
        for line in lines:
            if line.subscription_id.subscription_type == "recovery":
                if line.balance > 0.01:
                    # Les recouvrements individuels viennent après les
                    # cycles périodiques pour un encaissement en réunion.
                    recovery_priority = 1 if is_meeting_payment else 0
                    candidates.append((recovery_priority, line.subscription_id.due_date or fields.Date.today(), line.id, line, False, line.balance))
                continue
            for period in PaymentLine._get_unsettled_periods_for_line(line):
                due = PaymentLine._get_period_due_for_line(line, period)
                paid = PaymentLine._get_period_paid_for_line(line, period)
                balance = max(due - paid, 0.0)
                if balance > 0.01:
                    cycle_priority = 0 if is_meeting_payment else 1
                    candidates.append((cycle_priority, period.due_date or fields.Date.today(), line.id, line, period, balance))
        for _priority, _date, _line_id, line, period, balance in sorted(candidates, key=lambda item: (item[0], item[1], item[2], item[4].id if item[4] else 0)):
            if remaining <= 0:
                break
            allocated = min(remaining, balance)
            allocation_values.append((0, 0, {
                "subscription_line_id": line.id,
                "subscription_id": line.subscription_id.id,
                "subscription_period_id": period.id if period else False,
                "amount_paid": allocated,
            }))
            remaining -= allocated
        # Fees are settled last in a meeting: they are neither sanctions nor
        # subscription cycles, and must not preempt recovery subscriptions.
        if is_meeting_payment:
            for fee in membership_fees:
                if remaining <= 0:
                    break
                allocated = min(remaining, fee.amount_remaining or 0.0)
                if allocated > 0:
                    membership_fee_allocations.append({"membership_fee_id": fee.id, "amount": allocated})
                    remaining -= allocated
        if not allocation_values and not priority_allocations and not membership_fee_allocations:
            raise ValidationError(_("Aucun recouvrement non soldé n’a été trouvé pour ce membre."))
        Payment = self.env["association.payment"]
        payment = Payment.create({
            "member_id": self.member_id.id,
            "company_id": company.id,
            "meeting_id": self.meeting_id.id if self.meeting_id else False,
            "payment_date": fields.Date.context_today(self),
            "amount": amount_received,
            "payment_source": payment_source,
            "member_account_id": member_account.id if member_account else False,
            "payment_method": self.payment_method or "cash",
            "payment_reference": self.payment_reference or (
                _("Encaissement global en réunion %s") % self.meeting_id.name
                if self.meeting_id else
                _("Paiement priorisé de la cotisation %s") % self.subscription_line_id.subscription_id.display_name
            ),
            "has_allocations": True,
            "priority_allocation_amount": sum(item["amount"] for item in priority_allocations),
            "priority_allocation_payload": priority_allocations,
            "membership_fee_allocation_amount": sum(item["amount"] for item in membership_fee_allocations),
            "membership_fee_allocation_payload": membership_fee_allocations,
            "line_ids": allocation_values,
        })
        self.payment_id = payment.id
        payment.action_collect()
        return payment.action_confirm()

    def action_validate_payment(self):
        self.ensure_one()

        if self.origin in ("meeting", "subscription"):
            return self._action_validate_prioritized_payment()

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
        if subscription.state != "running":
            raise ValidationError(
                _("La cotisation %(subscription)s n'est pas en cours et ne peut pas être réglée.")
                % {"subscription": subscription.display_name}
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
            and period.state not in ("running", "closed")
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
                    "Aucun cycle en cours avec "
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

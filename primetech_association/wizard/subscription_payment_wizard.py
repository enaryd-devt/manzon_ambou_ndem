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
            ("member", "Situation du membre"),
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
        comodel_name="res.currency",
        compute="_compute_currency_id",
    )

    @api.depends("subscription_line_id", "member_id")
    def _compute_currency_id(self):
        # A member-level payment (fees, adjustments) has no subscription line.
        for wizard in self:
            wizard.currency_id = (
                wizard.subscription_line_id.currency_id
                or wizard.member_id.company_id.currency_id
                or self.env.company.currency_id
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

    # L'utilisateur choisit l'ordre de règlement des créances par
    # glisser-déposer, y compris lors d'un encaissement en réunion.
    allocation_line_ids = fields.One2many(
        comodel_name="association.subscription.payment.wizard.line",
        inverse_name="wizard_id",
        string="Ordre de règlement",
    )

    # ==========================================================
    # DEFAULT GET
    # ==========================================================

    @api.model
    def default_get(self, fields_list):
        values = self._get_default_payment_values(fields_list)
        meeting_id = values.get("meeting_id") or self.env.context.get("default_meeting_id")
        member = self.env["association.member"].browse(values.get("member_id")).exists()
        if not member or not values.get("origin"):
            return values
        subscription_line = self.env["association.subscription.line"].browse(
            values.get("subscription_line_id")
        ).exists()
        company = subscription_line.company_id or member.company_id or self.env.company
        items = self._get_outstanding_items(
            member,
            company,
            values["origin"],
            subscription_line,
            is_meeting_payment=bool(meeting_id),
        )
        values["allocation_line_ids"] = [
            (0, 0, {
                "sequence": (index + 1) * 10,
                "kind": item["kind"],
                "detail": item["detail"],
                "balance": item["balance"],
                "penalty_id": item.get("penalty") and item["penalty"].id,
                "membership_fee_id": item.get("fee") and item["fee"].id,
                "subscription_line_id": item.get("line") and item["line"].id,
                "period_id": item.get("period") and item["period"].id,
            })
            for index, item in enumerate(items)
        ]
        return values

    @api.model
    def _get_outstanding_items(self, member, company, origin, subscription_line=False, is_meeting_payment=False):
        """Return the member's outstanding dues in the automatic order.

        Financial sanctions come first, then each due follows its payment
        priority (« Très haute » first) defined on the subscription, the
        membership fee or the adjustment.  At equal priority the standard
        order applies:
        - in a meeting: cycles, recoveries, membership fees, adjustments;
        - outside a meeting: membership fees, recoveries, cycles, adjustments.
        """
        PaymentLine = self.env["association.payment.line"]
        items = []
        penalties = self.env["association.penalty"].search([
            ("member_id", "=", member.id),
            ("company_id", "=", company.id),
            ("penalty_type", "=", "fine"),
            ("state", "in", ("validated", "executed")),
            ("amount_remaining", ">", 0),
        ], order="recovery_priority asc, incident_date asc, id asc")
        for rank, penalty in enumerate(penalties):
            items.append({
                "key": (0, rank), "kind": "penalty", "penalty": penalty,
                "balance": penalty.amount_remaining or 0.0,
                "detail": penalty.penalty_description or penalty.display_name,
            })

        if is_meeting_payment:
            standard_rank = {"cycle": 0, "recovery": 1, "membership": 2, "adjustment": 3}
        else:
            standard_rank = {"membership": 0, "recovery": 1, "cycle": 2, "adjustment": 3}
        fees = self.env["association.membership.fee"].search([
            ("member_id", "=", member.id),
            ("company_id", "=", company.id),
            ("state", "=", "due"),
            ("amount_remaining", ">", 0),
        ], order="id asc")
        for fee in fees:
            kind = "adjustment" if fee.fee_type == "adjustment" else "membership"
            items.append({
                "key": (1, int(fee.payment_priority or 3), standard_rank[kind], fields.Date.to_date(fee.create_date), fee.id, 0),
                "kind": kind, "fee": fee, "balance": fee.amount_remaining or 0.0,
                "detail": fee.name,
            })

        if origin in ("meeting", "member"):
            lines = self.env["association.subscription.line"].search([
                ("member_id", "=", member.id),
                ("company_id", "=", company.id), ("active", "=", True),
                ("subscription_id.state", "=", "running"),
            ])
        else:
            lines = subscription_line or self.env["association.subscription.line"]
        for line in lines:
            subscription = line.subscription_id
            priority = int(subscription.payment_priority or 3)
            if subscription.subscription_type == "recovery":
                if line.balance > 0.01:
                    items.append({
                        "key": (1, priority, standard_rank["recovery"], subscription.due_date or fields.Date.today(), line.id, 0),
                        "kind": "recovery", "line": line, "period": False, "balance": line.balance,
                        "detail": subscription.display_name,
                    })
                continue
            for period in PaymentLine._get_unsettled_periods_for_line(line):
                due = PaymentLine._get_period_due_for_line(line, period)
                paid = PaymentLine._get_period_paid_for_line(line, period)
                balance = max(due - paid, 0.0)
                if balance > 0.01:
                    items.append({
                        "key": (1, priority, standard_rank["cycle"], period.due_date or fields.Date.today(), line.id, period.id),
                        "kind": "cycle", "line": line, "period": period, "balance": balance,
                        "detail": "%s — %s" % (subscription.display_name, period.display_name),
                    })
        return sorted(items, key=lambda item: item["key"])

    @api.model
    def _get_item_identity(self, item):
        return (
            item["kind"],
            item["penalty"].id if item.get("penalty") else 0,
            item["fee"].id if item.get("fee") else 0,
            item["line"].id if item.get("line") else 0,
            item["period"].id if item.get("period") else 0,
        )

    @api.model
    def _get_default_payment_values(self, fields_list):

        values = super().default_get(fields_list)

        subscription_line_id = self.env.context.get(
            "default_subscription_line_id"
        )

        if not subscription_line_id:
            if self.env.context.get("default_origin") == "member":
                values.update(self._prepare_member_situation_values())
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
                fee_label = "Ajustement de situation" if fee.fee_type == "adjustment" else "Frais d’adhésion"
                global_rows.append("<tr class='table-info'><td>%s</td><td>%s</td><td class='text-end'>%.2f</td></tr>" % (
                    fee_label,
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
                # The cycle is not a field to manipulate in the global
                # assistant.  It remains visible in the situation table so
                # the treasurer can understand each contribution balance.
                Situation = self.env["association.meeting.member.situation"]
                for line in lines:
                    subscription = line.subscription_id
                    if subscription.subscription_type == "recovery":
                        balance = Situation._get_subscription_line_balance(line)
                        if balance > 0.01:
                            global_due += balance
                            global_rows.append(
                                "<tr><td>Recouvrement</td><td>%s</td>"
                                "<td class='text-end'>%.2f</td></tr>"
                                % (html_escape(subscription.display_name), balance)
                            )
                        continue

                    periods = PaymentLine._get_unsettled_periods_for_line(line)
                    if periods:
                        for line_period in periods:
                            due = PaymentLine._get_period_due_for_line(line, line_period)
                            paid = PaymentLine._get_period_paid_for_line(line, line_period)
                            balance = max(due - paid, 0.0)
                            if balance <= 0.01:
                                continue
                            global_due += balance
                            global_rows.append(
                                "<tr><td>%s</td><td>%s — %s</td>"
                                "<td class='text-end'>%.2f</td></tr>"
                                % (
                                    html_escape(subscription.display_name),
                                    html_escape("Cycle"),
                                    html_escape(line_period.display_name),
                                    balance,
                                )
                            )
                        continue

                    # Contributions without cycles are shown as one global
                    # responsibility.  The helper avoids any conversion of a
                    # cancelled/draft cycle into a debt.
                    balance = Situation._get_subscription_line_balance(line)
                    if balance > 0.01:
                        global_due += balance
                        global_rows.append(
                            "<tr><td>%s</td><td>Sans cycle</td>"
                            "<td class='text-end'>%.2f</td></tr>"
                            % (html_escape(subscription.display_name), balance)
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
                "global_lines_html": ("<table class='table table-sm'><thead><tr><th>Créance</th><th>Détail</th><th class='text-end'>Reste à régler</th></tr></thead><tbody>%s</tbody></table><small class='text-muted'>Ordre de règlement : sanctions d’abord, puis selon la priorité de règlement de chaque créance.</small>" % "".join(global_rows)) if global_rows else False,
            }
        )

        if global_rows:
            values["global_lines_html"] = (
                "<table class='table table-sm'><thead><tr><th>Créance</th><th>Détail</th>"
                "<th class='text-end'>Reste à régler</th></tr></thead><tbody>%s</tbody></table>"
                "<small class='text-muted'>Ordre de règlement : sanctions d’abord, puis selon la priorité de règlement de chaque créance.</small>"
            ) % "".join(global_rows)
        return values

    @api.model
    def _prepare_member_situation_values(self):
        """Initialise a global payment from the member situation.

        Used to collect membership fees and situation adjustments, even when
        the member has no running subscription to anchor the payment.
        """
        member = self.env["association.member"].browse(
            self.env.context.get("default_member_id")
        ).exists()
        if not member:
            raise ValidationError(_("Aucun membre n'est sélectionné."))
        # Only what the allocation can actually settle: a closed subscription
        # no longer accepts payments.
        items = [
            item for item in member._get_financial_situation_items(only_outstanding=True)
            if not item.get("subscription_id")
            or self.env["association.subscription"].sudo().browse(item["subscription_id"]).state == "running"
        ]
        global_due = sum(item["balance"] for item in items)
        if global_due <= 0.01:
            raise ValidationError(_("La situation de ce membre est déjà réglée."))
        type_labels = dict(
            self.env["association.member.subscription.cycle.report"]._fields["situation_type"].selection
        )
        rows = "".join(
            "<tr><td>%s</td><td>%s</td><td class='text-end'>%.2f</td></tr>" % (
                html_escape(type_labels.get(item["situation_type"], "")),
                html_escape(item["label"]),
                item["balance"],
            )
            for item in items
        )
        default_amount_received = self.env.context.get("default_amount_received")
        return {
            "origin": "member",
            "member_id": member.id,
            "meeting_id": self.env.context.get("default_meeting_id") or False,
            "amount_due": global_due,
            "balance": global_due,
            "amount_received": (
                global_due if default_amount_received in (None, False)
                else max(default_amount_received or 0.0, 0.0)
            ),
            "global_due_amount": global_due,
            "global_lines_html": (
                "<table class='table table-sm'><thead><tr><th>Créance</th><th>Détail</th>"
                "<th class='text-end'>Reste à régler</th></tr></thead><tbody>%s</tbody></table>"
                "<small class='text-muted'>Ordre de règlement : sanctions d’abord, "
                "puis selon la priorité de règlement de chaque créance.</small>"
            ) % rows,
        }

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
        is_member_payment = self.origin == "member"
        if not self.member_id or not (self.subscription_line_id or is_member_payment):
            raise ValidationError(_("Le membre et la cotisation sont obligatoires."))
        company = (
            self.meeting_id.company_id
            or self.subscription_line_id.company_id
            or self.member_id.company_id
        )
        amount_received = self.amount_received or 0.0
        if amount_received <= 0:
            raise ValidationError(_("Le montant reçu doit être strictement supérieur à zéro."))
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
        membership_fee_allocations = []

        # Les soldes sont relus au moment de la validation. L'ordre choisi
        # dans l'assistant s'applique aussi en réunion ; une créance apparue
        # depuis l'ouverture passe en dernier.
        is_meeting_payment = bool(self.meeting_id)
        items = self._get_outstanding_items(
            self.member_id, company, self.origin, self.subscription_line_id, is_meeting_payment,
        )
        if self.allocation_line_ids:
            chosen_rank = {
                wizard_line._get_item_identity_from_line(): rank
                for rank, wizard_line in enumerate(self.allocation_line_ids.sorted(lambda l: (l.sequence, l.id)))
            }
            items.sort(key=lambda item: chosen_rank.get(self._get_item_identity(item), len(chosen_rank)))

        for candidate in items:
            if remaining <= 0:
                break
            allocated = min(remaining, candidate["balance"])
            if allocated <= 0:
                continue
            if candidate.get("penalty"):
                priority_allocations.append({"penalty_id": candidate["penalty"].id, "amount": allocated})
            elif candidate.get("fee"):
                membership_fee_allocations.append({"membership_fee_id": candidate["fee"].id, "amount": allocated})
            else:
                line = candidate["line"]
                allocation_values.append((0, 0, {
                    "subscription_line_id": line.id,
                    "subscription_id": line.subscription_id.id,
                    "subscription_period_id": candidate["period"].id if candidate["period"] else False,
                    "amount_paid": allocated,
                }))
            remaining -= allocated
        if not allocation_values and not priority_allocations and not membership_fee_allocations:
            raise ValidationError(_("Aucun recouvrement non soldé n’a été trouvé pour ce membre."))
        Payment = self.env["association.payment"]
        payment = Payment.create({
            "member_id": self.member_id.id,
            "company_id": company.id,
            "meeting_id": self.meeting_id.id if self.meeting_id else False,
            # Keeps the payment in the session closing report.
            "meeting_subscription_session_id": self.meeting_id.subscription_session_id.id if self.meeting_id else False,
            "payment_date": fields.Date.context_today(self),
            "amount": amount_received,
            "payment_source": payment_source,
            "member_account_id": member_account.id if member_account else False,
            "payment_method": self.payment_method or "cash",
            "payment_reference": self.payment_reference or (
                _("Encaissement global en réunion %s") % self.meeting_id.name
                if self.meeting_id else
                _("Règlement de la situation de %s") % self.member_id.display_name
                if is_member_payment else
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

        if self.origin in ("meeting", "subscription", "member"):
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


class AssociationSubscriptionPaymentWizardLine(models.TransientModel):
    _name = "association.subscription.payment.wizard.line"
    _description = "Ordre de règlement d'un encaissement"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        comodel_name="association.subscription.payment.wizard",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Ordre", default=10)
    kind = fields.Selection(
        selection=[
            ("penalty", "Sanction financière"),
            ("membership", "Frais d’adhésion"),
            ("adjustment", "Ajustement de situation"),
            ("recovery", "Recouvrement"),
            ("cycle", "Cycle de cotisation"),
        ],
        string="Créance",
        readonly=True,
    )
    detail = fields.Char(string="Détail", readonly=True)
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    balance = fields.Monetary(string="Reste à régler", currency_field="currency_id", readonly=True)
    amount_allocated = fields.Monetary(
        string="Montant affecté",
        currency_field="currency_id",
        compute="_compute_amount_allocated",
    )
    penalty_id = fields.Many2one("association.penalty", readonly=True)
    membership_fee_id = fields.Many2one("association.membership.fee", readonly=True)
    subscription_line_id = fields.Many2one("association.subscription.line", readonly=True)
    period_id = fields.Many2one("association.subscription.period", readonly=True)

    @api.depends(
        "sequence", "balance",
        "wizard_id.amount_received",
        "wizard_id.allocation_line_ids.sequence",
    )
    def _compute_amount_allocated(self):
        # Aperçu : le montant reçu est consommé ligne par ligne, dans l'ordre
        # affiché, exactement comme lors de la validation.
        allocated = {}
        for wizard in self.mapped("wizard_id"):
            remaining = wizard.amount_received or 0.0
            for line in wizard.allocation_line_ids.sorted(lambda l: l.sequence):
                amount = min(max(remaining, 0.0), line.balance or 0.0)
                allocated[line] = amount
                remaining -= amount
        for line in self:
            line.amount_allocated = allocated.get(line, 0.0)

    def _get_item_identity_from_line(self):
        self.ensure_one()
        return (
            self.kind,
            self.penalty_id.id or 0,
            self.membership_fee_id.id or 0,
            self.subscription_line_id.id or 0,
            self.period_id.id or 0,
        )

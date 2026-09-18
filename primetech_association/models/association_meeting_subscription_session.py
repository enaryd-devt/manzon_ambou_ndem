# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationMeetingSubscriptionSession(models.Model):
    """A single subscription cycle handled during a meeting.

    A meeting may contain several of these sessions, but a subscription cycle
    can only be handled once in that meeting.  This keeps cash collection,
    settlement and the audit trail isolated from the other subscriptions.
    """

    _name = "association.meeting.subscription.session"
    _description = "Session de cotisation en réunion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    meeting_id = fields.Many2one(
        "association.meeting", required=True, ondelete="cascade", index=True,
        string="Réunion", tracking=True,
    )
    company_id = fields.Many2one(
        related="meeting_id.company_id", store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", readonly=True,
    )
    subscription_id = fields.Many2one(
        "association.subscription", required=True, ondelete="restrict",
        string="Cotisation", tracking=True, index=True,
    )
    period_id = fields.Many2one(
        "association.subscription.period", ondelete="restrict",
        string="Cycle de cotisation", tracking=True, index=True,
        domain="[('subscription_id', '=', subscription_id), ('state', '=', 'running')]",
    )
    state = fields.Selection([
        ("draft", "Brouillon"),
        ("collecting", "En encaissement"),
        ("decision", "En décision de clôture"),
        ("closed", "Clôturée"),
        ("cancelled", "Annulée"),
    ], default="draft", required=True, tracking=True, index=True)
    collection_ids = fields.One2many(
        "association.meeting.collection", "session_id", string="Encaissements",
    )
    payment_ids = fields.One2many(
        "association.payment", "meeting_subscription_session_id",
        string="Paiements", readonly=True,
    )
    snapshot_ids = fields.One2many(
        "association.meeting.subscription.snapshot", "session_id",
        string="Situation figée du cycle", readonly=True, copy=False,
    )
    payment_count = fields.Integer(
        compute="_compute_payment_summary", string="Encaissements validés",
    )
    payment_total = fields.Monetary(
        compute="_compute_payment_summary", currency_field="currency_id",
        string="Total des encaissements",
    )
    allocation_ids = fields.One2many(
        "association.subscription.allocation", "meeting_subscription_session_id",
        string="Bénéficiaires", readonly=True,
    )
    collected_amount = fields.Monetary(
        compute="_compute_statistics", currency_field="currency_id", string="Collecté",
    )
    pending_count = fields.Integer(compute="_compute_statistics", string="En attente")
    paid_count = fields.Integer(compute="_compute_statistics", string="Payés")
    expected_amount = fields.Monetary(
        compute="_compute_statistics", currency_field="currency_id", string="Montant attendu",
    )
    closed_expected_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, copy=False,
    )
    closed_collected_amount = fields.Monetary(
        currency_field="currency_id", readonly=True, copy=False,
    )
    closed_paid_count = fields.Integer(readonly=True, copy=False)
    closed_partial_count = fields.Integer(readonly=True, copy=False)
    closed_unpaid_count = fields.Integer(readonly=True, copy=False)
    closed_penalty_amount = fields.Monetary(currency_field="currency_id", readonly=True, copy=False)
    closed_allocated_amount = fields.Monetary(currency_field="currency_id", readonly=True, copy=False)
    closed_pending_count = fields.Integer(readonly=True, copy=False)
    closed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    closed_at = fields.Datetime(readonly=True, copy=False)
    closure_note = fields.Text(string="Décision de clôture", readonly=True, copy=False)

    _sql_constraints = [
        (
            "meeting_subscription_period_unique",
            "unique(meeting_id, subscription_id, period_id)",
            "Cette cotisation et ce cycle sont déjà traités dans cette réunion.",
        ),
    ]

    @api.constrains("subscription_id", "period_id", "meeting_id")
    def _check_session_values(self):
        for session in self:
            if not session.period_id:
                continue
            if session.period_id.subscription_id != session.subscription_id:
                raise ValidationError(
                    _("Le cycle sélectionné ne correspond pas à la cotisation.")
                )
            if session.period_id.company_id != session.meeting_id.company_id:
                raise ValidationError(
                    _("Le cycle et la réunion doivent appartenir à la même filiale.")
                )

    @api.onchange("subscription_id")
    def _onchange_subscription_id(self):
        for session in self:
            session.period_id = session.subscription_id.current_period_id
            if session.subscription_id and not session.period_id:
                return {
                    "warning": {
                        "title": _("Aucun cycle en cours"),
                        "message": _(
                            "Le dernier cycle est terminé. Cliquez sur « Démarrer le cycle suivant » pour ouvrir un nouveau cycle dans cette nouvelle réunion."
                        ),
                    }
                }

    def action_start_next_cycle(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Le cycle suivant ne peut être démarré que depuis une session brouillon."))
        if not self.subscription_id:
            raise ValidationError(_("Sélectionnez une cotisation avant de démarrer son cycle."))
        previous_session = self.meeting_id.subscription_session_ids.filtered(
            lambda session: session != self
            and session.subscription_id == self.subscription_id
            and session.state == "closed"
        )
        if previous_session:
            raise UserError(
                _(
                    "Cette cotisation a déjà été clôturée dans cette réunion. Créez une nouvelle réunion avant de démarrer le cycle suivant."
                )
            )
        if self.subscription_id.current_period_id:
            self.period_id = self.subscription_id.current_period_id
            return True
        self.subscription_id.action_open_next_period()
        self.period_id = self.subscription_id.current_period_id
        return True

    @api.depends(
        "collection_ids.state",
        "collection_ids.payment_id.amount",
        "collection_ids.initial_due_amount",
    )
    def _compute_statistics(self):
        for session in self:
            paid_lines = session.collection_ids.filtered(
                lambda line: line.state == "paid"
            )
            session.pending_count = len(session.collection_ids.filtered(
                lambda line: line.state == "pending"
            ))
            session.paid_count = len(paid_lines)
            session.collected_amount = sum(paid_lines.mapped("payment_id.amount"))
            session.expected_amount = sum(
                session.collection_ids.mapped("initial_due_amount")
            )

    @api.depends("payment_ids.amount", "payment_ids.state")
    def _compute_payment_summary(self):
        """Expose the definitive receipts once a session has been closed.

        Payments are linked to the session when they are created.  Keeping the
        summary on the session makes the receipts immediately available in the
        closed-session tab without relying on the still-editable collection
        lines.
        """
        for session in self:
            confirmed_payments = session.payment_ids.filtered(
                lambda payment: payment.state in ("collected", "confirmed")
            )
            session.payment_count = len(confirmed_payments)
            session.payment_total = sum(confirmed_payments.mapped("amount"))

    def action_start_collection(self):
        for session in self:
            if session.meeting_id.state == "closed":
                raise UserError(_("La réunion est déjà clôturée."))
            if not session.period_id:
                raise ValidationError(_("Démarrez ou sélectionnez un cycle de cotisation."))
            if session.period_id.state != "running":
                raise ValidationError(_("Seul un cycle en cours peut être encaissé."))
            if session.state == "draft":
                session.state = "collecting"
        return True

    def action_generate_members(self):
        Collection = self.env["association.meeting.collection"]
        for session in self:
            if session.state not in ("draft", "collecting"):
                raise UserError(_("La session n'est plus ouverte aux encaissements."))
            session.action_start_collection()
            lines = self.env["association.subscription.line"].search([
                ("subscription_id", "=", session.subscription_id.id),
                ("balance", ">", 0),
                ("active", "=", True),
            ], order="member_id")
            existing_ids = set(session.collection_ids.mapped("subscription_line_id").ids)
            values = []
            sequence = max(session.collection_ids.mapped("sequence"), default=0) + 10
            for line in lines:
                if line.id not in existing_ids:
                    values.append({
                        "meeting_id": session.meeting_id.id,
                        "session_id": session.id,
                        "subscription_id": session.subscription_id.id,
                        "subscription_line_id": line.id,
                        "sequence": sequence,
                    })
                    sequence += 10
            if not values:
                raise UserError(_("Aucun membre en attente de paiement n'a été trouvé."))
            Collection.create(values)
        return True

    def action_collect_all(self):
        for session in self:
            if session.state != "collecting":
                raise UserError(_("La session doit être en encaissement."))
            lines = session.collection_ids.filtered(
                lambda line: line.state == "pending" and line.amount > 0
            )
            if not lines:
                raise UserError(_("Saisissez au moins un montant à encaisser."))
            lines.action_collect()
        return True

    def action_open_settlement(self):
        self.ensure_one()
        if self.state not in ("draft", "collecting", "decision"):
            raise UserError(_("La session ne peut pas être clôturée dans son état actuel."))
        if self.pending_count:
            raise ValidationError(_("Validez ou annulez tous les encaissements en attente."))
        if self.period_id.state != "running":
            raise ValidationError(_("Le cycle de cotisation n'est plus en cours."))

        if (self.period_id.available_amount or 0.0) <= 0.01:
            self._close_without_treasury_transfer()
            return {
                "type": "ir.actions.client",
                "tag": "primetech_refresh_subscription_table",
                "params": {
                    "subscription_id": self.subscription_id.id,
                    "meeting_id": self.meeting_id.id,
                    "origin": "meeting",
                    "close_dialog": False,
                },
            }

        self.state = "decision"
        # The close wizard is instantiated inside ``action_close``.  Pass the
        # session in the environment *before* calling it, otherwise adding
        # defaults only to the returned action cannot link that already
        # created wizard to the meeting session.
        action = self.period_id.with_context(
            self.env.context,
            default_meeting_subscription_session_id=self.id,
        ).action_close()
        return action

    def _close_without_treasury_transfer(self):
        """Close an empty or fully allocated temporary meeting cash directly."""
        self.ensure_one()
        if self.period_id.available_amount > 0.01:
            raise ValidationError(_("Un reliquat doit être traité avant la clôture."))
        self.period_id.write({"state": "closed"})
        self.subscription_id.line_ids.write({"amount_received": 0.0})
        self.subscription_id.invalidate_recordset(["current_period_id", "period_count"])
        self.subscription_id.modified(["current_period_id", "period_count"])
        self.action_mark_closed()
        self.period_id.message_post(
            body=_(
                "Le cycle a été terminé sans versement en trésorerie : la caisse temporaire est nulle ou entièrement attribuée."
            )
        )
        return True

    def action_mark_closed(self):
        for session in self:
            # Older allocations created from the meeting did not carry the
            # session link. Attach the allocations of this exact meeting and
            # period before freezing the closure totals and PDF data.
            allocations = session.period_id.allocation_ids.filtered(
                lambda allocation: allocation.meeting_id == session.meeting_id
                and not allocation.meeting_subscription_session_id
            )
            if allocations:
                allocations.write({
                    "meeting_subscription_session_id": session.id,
                })
            session._create_cycle_snapshot()
            snapshots = session.snapshot_ids
            paid = snapshots.filtered(lambda item: item.payment_state == "paid")
            partial = snapshots.filtered(lambda item: item.payment_state == "partial")
            unpaid = snapshots.filtered(lambda item: item.payment_state == "not_paid")
            session.write({
                "state": "closed",
                "closed_by_id": self.env.user.id,
                "closed_at": fields.Datetime.now(),
                "closed_expected_amount": sum(snapshots.mapped("amount_due")),
                "closed_collected_amount": sum(snapshots.mapped("amount_paid")),
                "closed_paid_count": len(paid),
                "closed_partial_count": len(partial),
                "closed_unpaid_count": len(unpaid),
                "closed_penalty_amount": sum(snapshots.mapped("penalty_amount")),
                "closed_allocated_amount": sum(session.allocation_ids.mapped("amount")),
                "closed_pending_count": session.pending_count,
            })
            # Keep the selected subscription and period on the meeting.  This
            # lets the Cotisations tab keep displaying this closed session and
            # makes its PDF report directly accessible after closure.
            session.meeting_id.invalidate_recordset([
                "subscription_session_id",
                "subscription_report_available",
                "subscription_line_ids",
            ])
            # The cycle settlement has already attributed or transferred its
            # entire temporary cash before this method is called.  Mark the
            # meeting cash as settled as well, otherwise the generic meeting
            # close check incorrectly blocks the user despite a closed
            # subscription session and a zero remaining cycle balance.
            sessions_settled = all(
                item.state == "closed"
                and (item.period_id.available_amount or 0.0) <= 0.01
                for item in session.meeting_id.subscription_session_ids
            )
            if sessions_settled:
                session.meeting_id.write({"pot_settlement_state": "settled"})
            # Member-account payments made during a meeting remain temporary
            # until the session is finalised.  Debit them once the allocations
            # and treasury settlement have been completed.
            deferred_payments = session.payment_ids.filtered(
                lambda payment: payment.state == "confirmed"
                and payment.payment_source == "member_account"
                and payment.defer_member_account_debit
            )
            for payment in deferred_payments:
                payment._debit_member_account()
                payment.write({"defer_member_account_debit": False})
        return True

    def _create_cycle_snapshot(self):
        """Freeze every member's amounts for this exact period.

        Subscription-line computed values follow the *current* cycle and are
        therefore not safe historical data after the next cycle starts.
        """
        self.ensure_one()
        if self.snapshot_ids:
            return True
        PaymentLine = self.env["association.payment.line"]
        values = []
        for line in self.subscription_id.line_ids.filtered("active"):
            payment_lines = PaymentLine.search([
                ("subscription_line_id", "=", line.id),
                ("payment_id.subscription_period_id", "=", self.period_id.id),
                ("payment_id.state", "in", ("collected", "confirmed")),
            ])
            due = (self.subscription_id.amount or 0.0) + (line.penalty_amount or 0.0)
            paid = sum(payment_lines.mapped("amount_paid"))
            balance = max(due - paid, 0.0)
            values.append({
                "session_id": self.id, "member_id": line.member_id.id,
                "member_name": line.member_id.display_name,
                "member_code": line.member_code, "amount_due": due,
                "amount_paid": paid, "balance": balance,
                "penalty_amount": line.penalty_amount,
                "payment_state": "paid" if balance <= 0.01 else ("partial" if paid else "not_paid"),
            })
        self.env["association.meeting.subscription.snapshot"].create(values)
        self.collection_ids.action_freeze_cycle_snapshot()
        return True

    def action_print_report(self):
        self.ensure_one()
        if self.state != "closed":
            raise UserError(_("Le rapport définitif est disponible après la clôture."))
        return self.env.ref(
            "primetech_association.action_report_meeting_subscription_session"
        ).report_action(self)

    def write(self, vals):
        protected_fields = set(vals) - {"message_follower_ids", "message_ids"}
        if protected_fields:
            for session in self:
                if session.state == "closed" and vals.get("state") != "closed":
                    raise UserError(
                        _("Une session clôturée est verrouillée et ne peut plus être modifiée.")
                    )
        return super().write(vals)

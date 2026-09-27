# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMeetingMemberSituation(models.Model):
    """One treasury row per active member called during a meeting.

    The row deliberately does not belong to one subscription: a member is
    called once and the payment wizard distributes the amount by priority.
    """
    _name = "association.meeting.member.situation"
    _description = "Situation de recouvrement d'un membre en réunion"
    _order = "member_id"

    meeting_id = fields.Many2one("association.meeting", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="meeting_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    member_id = fields.Many2one("association.member", required=True, ondelete="restrict", index=True)
    member_code = fields.Char(related="member_id.member_code", readonly=True)
    image_128 = fields.Image(related="member_id.image_128", readonly=True)
    amount_due = fields.Monetary(string="Situation à régler", currency_field="currency_id", compute="_compute_situation")
    amount_paid_in_meeting = fields.Monetary(string="Réglé en séance", currency_field="currency_id", compute="_compute_situation")
    payment_state = fields.Selection([("not_paid", "Non réglé"), ("partial", "Partiellement réglé"), ("paid", "Réglé")], compute="_compute_situation")
    has_member_account = fields.Boolean(compute="_compute_situation")

    _sql_constraints = [
        ("meeting_member_situation_unique", "unique(meeting_id, member_id)", "Ce membre est déjà présent dans la trésorerie de la réunion."),
    ]

    @api.depends("member_id", "meeting_id.meeting_payment_ids.state", "meeting_id.meeting_payment_ids.amount")
    def _compute_situation(self):
        PaymentLine = self.env["association.payment.line"]
        Penalty = self.env["association.penalty"]
        Fee = self.env["association.membership.fee"]
        SubscriptionLine = self.env["association.subscription.line"]
        Account = self.env["association.member.account"]
        for rec in self:
            rec.amount_due = 0.0
            rec.amount_paid_in_meeting = 0.0
            rec.payment_state = "paid"
            rec.has_member_account = False
            if not rec.member_id:
                continue
            company = rec.company_id
            rec.has_member_account = bool(Account.search_count([("member_id", "=", rec.member_id.id), ("company_id", "=", company.id), ("active", "=", True)]))
            due = sum(Penalty.search([("member_id", "=", rec.member_id.id), ("company_id", "=", company.id), ("penalty_type", "=", "fine"), ("recovery_origin", "=", "sanction"), ("state", "in", ("validated", "executed")), ("amount_remaining", ">", 0)]).mapped("amount_remaining"))
            due += sum(Fee.search([("member_id", "=", rec.member_id.id), ("company_id", "=", company.id), ("state", "=", "due"), ("amount_remaining", ">", 0)]).mapped("amount_remaining"))
            lines = SubscriptionLine.search([("member_id", "=", rec.member_id.id), ("company_id", "=", company.id), ("active", "=", True), ("subscription_id.state", "=", "running")])
            for line in lines:
                for period in PaymentLine._get_unsettled_periods_for_line(line):
                    due += max(PaymentLine._get_period_due_for_line(line, period) - PaymentLine._get_period_paid_for_line(line, period), 0.0)
            paid = sum(rec.meeting_id.meeting_payment_ids.filtered(lambda p: p.member_id == rec.member_id and p.state == "confirmed").mapped("amount"))
            rec.amount_due = due
            rec.amount_paid_in_meeting = paid
            rec.payment_state = "paid" if due <= 0.01 else ("partial" if paid > 0.01 else "not_paid")

    def action_create_payment(self):
        self.ensure_one()
        if self.amount_due <= 0.01:
            raise ValidationError(_("La situation de ce membre est déjà réglée."))
        # The existing wizard uses a subscription line as technical anchor;
        # it then expands the collection to every due item for this member.
        line = self.env["association.subscription.line"].search([
            ("member_id", "=", self.member_id.id),
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
            ("subscription_id.state", "=", "running"),
        ], order="id", limit=1)
        if not line:
            raise ValidationError(_("Ce membre n'a aucune cotisation en cours à régler. Les sanctions et frais restent consultables dans sa situation."))
        return {
            "type": "ir.actions.act_window", "name": _("Encaissement global du membre"),
            "res_model": "association.subscription.payment.wizard", "view_mode": "form", "target": "new",
            "context": {"default_origin": "meeting", "default_meeting_id": self.meeting_id.id, "default_member_id": self.member_id.id, "default_subscription_line_id": line.id},
        }

    def action_pay_from_member_account(self):
        action = self.action_create_payment()
        action["context"]["default_use_member_account"] = True
        return action

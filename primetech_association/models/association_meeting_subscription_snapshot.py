# -*- coding: utf-8 -*-

from odoo import fields, models


class AssociationMeetingSubscriptionSnapshot(models.Model):
    """Immutable member situation captured when a meeting session is closed."""

    _name = "association.meeting.subscription.snapshot"
    _description = "Instantané de cotisation en réunion"
    _order = "member_name, id"

    session_id = fields.Many2one(
        "association.meeting.subscription.session", required=True,
        ondelete="cascade", index=True,
    )
    member_id = fields.Many2one("association.member", ondelete="restrict", readonly=True)
    member_name = fields.Char(readonly=True)
    member_code = fields.Char(readonly=True)
    currency_id = fields.Many2one(related="session_id.currency_id", readonly=True)
    amount_due = fields.Monetary(currency_field="currency_id", readonly=True)
    amount_paid = fields.Monetary(currency_field="currency_id", readonly=True)
    balance = fields.Monetary(currency_field="currency_id", readonly=True)
    penalty_amount = fields.Monetary(currency_field="currency_id", readonly=True)
    payment_state = fields.Selection([
        ("not_paid", "Non payé"), ("partial", "Partiellement payé"),
        ("paid", "Payé"),
    ], readonly=True)

    _sql_constraints = [
        ("session_member_unique", "unique(session_id, member_id)",
         "Un instantané existe déjà pour ce membre et cette session."),
    ]

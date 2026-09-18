# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationMeetingSubscriptionCycleStartWizard(models.TransientModel):
    _name = "association.meeting.subscription.cycle.start.wizard"
    _description = "Démarrer un cycle de cotisation pour une réunion"

    meeting_id = fields.Many2one(
        "association.meeting", required=True, readonly=True, ondelete="cascade",
        string="Nouvelle réunion",
    )
    subscription_id = fields.Many2one(
        "association.subscription", required=True, readonly=True, ondelete="restrict",
        string="Cotisation",
    )

    def action_start_next_cycle(self):
        self.ensure_one()
        if self.meeting_id.state == "closed":
            raise UserError(_("La réunion est déjà clôturée."))
        if self.meeting_id.subscription_session_ids.filtered(
            lambda session: session.subscription_id == self.subscription_id
            and session.state == "closed"
        ):
            raise ValidationError(
                _("Cette cotisation a déjà été clôturée dans cette réunion. Créez une nouvelle réunion.")
            )

        period = self.subscription_id.current_period_id
        if not period:
            self.subscription_id.action_open_next_period()
            period = self.subscription_id.current_period_id
        if not period or period.state != "running":
            raise ValidationError(_("Le nouveau cycle n'a pas pu être démarré."))

        session = self.env["association.meeting.subscription.session"].create({
            "meeting_id": self.meeting_id.id,
            "subscription_id": self.subscription_id.id,
            "period_id": period.id,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "association.meeting.subscription.session",
            "res_id": session.id,
            "view_mode": "form",
            "target": "current",
        }

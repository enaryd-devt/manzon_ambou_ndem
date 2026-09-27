# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMeetingCycleFinishWizard(models.TransientModel):
    _name = "association.meeting.cycle.finish.wizard"
    _description = "Terminer un cycle de cotisation"

    meeting_id = fields.Many2one("association.meeting", string="Réunion", required=True, readonly=True)
    period_id = fields.Many2one(related="meeting_id.subscription_period_id", string="Cycle", readonly=True)
    currency_id = fields.Many2one(related="meeting_id.currency_id", readonly=True)
    available_amount = fields.Monetary(related="meeting_id.pot_available_amount", string="Montant disponible", currency_field="currency_id", readonly=True)
    apply_penalties = fields.Boolean(string="Appliquer les pénalités aux impayés", default=False)
    allocation_line_ids = fields.One2many("association.meeting.cycle.finish.line", "wizard_id", string="Affectations")
    allocated_amount = fields.Monetary(string="Total à affecter", currency_field="currency_id", compute="_compute_allocated_amount")

    @api.depends("allocation_line_ids.amount")
    def _compute_allocated_amount(self):
        for wizard in self:
            wizard.allocated_amount = sum(wizard.allocation_line_ids.mapped("amount"))

    def action_confirm(self):
        self.ensure_one()
        if not self.period_id or self.period_id.state != "running":
            raise ValidationError(_("Le cycle doit être en cours."))
        if abs((self.available_amount or 0.0) - (self.allocated_amount or 0.0)) > 0.01:
            raise ValidationError(_("Le total des affectations doit être exactement égal au montant disponible."))
        for line in self.allocation_line_ids:
            if line.amount <= 0:
                raise ValidationError(_("Chaque montant d'affectation doit être supérieur à zéro."))
            if line.destination == "beneficiary":
                if not line.beneficiary_id:
                    raise ValidationError(_("Sélectionnez le bénéficiaire."))
                allocation = self.env["association.subscription.allocation"].create({
                    "period_id": self.period_id.id, "meeting_id": self.meeting_id.id,
                    "meeting_subscription_session_id": self.meeting_id.subscription_session_id.id,
                    "beneficiary_id": line.beneficiary_id.id, "amount": line.amount,
                    "allocation_method": "meeting_decision", "decision_note": line.note,
                })
                allocation.action_confirm()
            else:
                if not line.fund_id:
                    raise ValidationError(_("Sélectionnez le compte de trésorerie."))
                if line.fund_id.company_id != self.meeting_id.company_id:
                    raise ValidationError(_("Le compte de trésorerie doit appartenir à la société de la réunion."))
                transaction = self.env["association.fund.transaction"].create({
                    "company_id": self.meeting_id.company_id.id, "fund_id": line.fund_id.id,
                    "transaction_type": "in", "amount": line.amount,
                    "transaction_date": fields.Date.context_today(self),
                    "description": _("Versement de la caisse de séance %(meeting)s") % {"meeting": self.meeting_id.display_name},
                    "origin_model": "association.meeting", "origin_res_id": self.meeting_id.id,
                    "origin_reference": self.meeting_id.name,
                })
                transaction.action_validate()
                self.period_id.settled_amount += line.amount
        if self.apply_penalties:
            self.period_id._get_subscription_lines()._apply_late_penalty(force=True)
        self.period_id.invalidate_recordset(["available_amount"])
        self.meeting_id.invalidate_recordset([
            "pot_collected_amount", "pot_allocated_amount", "pot_available_amount",
        ])
        session = self.meeting_id.subscription_session_ids.filtered(
            lambda item: item.period_id == self.period_id
        )[:1]
        if session:
            session._close_without_treasury_transfer()
            self.meeting_id._broadcast_live_sync()
            return {"type": "ir.actions.client", "tag": "soft_reload"}
        return self.meeting_id.action_close_subscription_cycle()


class AssociationMeetingCycleFinishLine(models.TransientModel):
    _name = "association.meeting.cycle.finish.line"
    _description = "Affectation de caisse de séance"

    wizard_id = fields.Many2one("association.meeting.cycle.finish.wizard", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="wizard_id.currency_id", readonly=True)
    company_id = fields.Many2one(related="wizard_id.meeting_id.company_id", readonly=True)
    destination = fields.Selection([("beneficiary", "Bénéficiaire"), ("treasury", "Compte de trésorerie")], required=True, default="treasury")
    beneficiary_id = fields.Many2one("association.member", string="Bénéficiaire", domain="[('company_id', '=', company_id), ('state', '=', 'active')]")
    # The company related value is not always available on an unsaved inline
    # wizard row.  Show active accounts, then enforce the company server-side.
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie", domain="[('active', '=', True)]")
    amount = fields.Monetary(string="Montant", required=True, currency_field="currency_id")
    note = fields.Char(string="Observation")

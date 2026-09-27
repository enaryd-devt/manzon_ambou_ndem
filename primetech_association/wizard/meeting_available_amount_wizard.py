# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMeetingAvailableAmountWizard(models.TransientModel):
    _name = "association.meeting.available.amount.wizard"
    _description = "Affectation du montant disponible de séance"

    meeting_id = fields.Many2one("association.meeting", string="Réunion", required=True, readonly=True)
    period_id = fields.Many2one(related="meeting_id.subscription_period_id", string="Cycle", readonly=True)
    company_id = fields.Many2one(related="meeting_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="meeting_id.currency_id", readonly=True)
    collected_amount = fields.Monetary(related="meeting_id.pot_collected_amount", string="Total collecté", currency_field="currency_id", readonly=True)
    expense_amount = fields.Monetary(related="meeting_id.expense_total", string="Dépenses de séance", currency_field="currency_id", readonly=True)
    available_amount = fields.Monetary(related="meeting_id.pot_available_amount", string="Montant disponible", currency_field="currency_id", readonly=True)
    destination = fields.Selection([("beneficiary", "Remettre à un bénéficiaire"), ("treasury", "Verser en trésorerie")], string="Destination", required=True, default="beneficiary")
    beneficiary_id = fields.Many2one("association.member", string="Bénéficiaire", domain="[('company_id', '=', company_id), ('state', '=', 'active')]")
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie", domain="[('company_id', '=', company_id), ('active', '=', True)]")
    amount = fields.Monetary(string="Montant à affecter", currency_field="currency_id", required=True)
    note = fields.Char(string="Observation")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        meeting = self.env["association.meeting"].browse(self.env.context.get("default_meeting_id")).exists()
        if meeting:
            values.update({"meeting_id": meeting.id, "amount": meeting.pot_available_amount or 0.0})
        return values

    def action_confirm(self):
        self.ensure_one()
        if not self.period_id or self.period_id.state != "running":
            raise ValidationError(_("Le cycle de cotisation doit être en cours."))
        if self.amount <= 0 or self.amount > (self.available_amount or 0.0):
            raise ValidationError(_("Le montant doit être supérieur à zéro et ne pas dépasser le montant disponible."))
        if self.destination == "beneficiary":
            if not self.beneficiary_id:
                raise ValidationError(_("Sélectionnez le bénéficiaire."))
            allocation = self.env["association.subscription.allocation"].create({
                "period_id": self.period_id.id,
                "meeting_id": self.meeting_id.id,
                "meeting_subscription_session_id": self.meeting_id.subscription_session_id.id,
                "beneficiary_id": self.beneficiary_id.id,
                "amount": self.amount,
                "allocation_method": "meeting_decision",
                "decision_note": self.note,
            })
            allocation.action_confirm()
            label = self.beneficiary_id.display_name
        else:
            if not self.fund_id:
                raise ValidationError(_("Sélectionnez le compte de trésorerie."))
            transaction = self.env["association.fund.transaction"].create({
                "company_id": self.company_id.id,
                "fund_id": self.fund_id.id,
                "transaction_type": "in",
                "amount": self.amount,
                "transaction_date": fields.Date.context_today(self),
                "description": _("Versement de la caisse de séance %(meeting)s") % {"meeting": self.meeting_id.display_name},
                "origin_model": "association.meeting",
                "origin_res_id": self.meeting_id.id,
                "origin_reference": self.meeting_id.name,
            })
            transaction.action_validate()
            self.period_id.settled_amount = (self.period_id.settled_amount or 0.0) + self.amount
            label = self.fund_id.display_name
        self.meeting_id.message_post(body=_("Montant disponible affecté : %(amount).2f %(currency)s vers %(destination)s.") % {"amount": self.amount, "currency": self.currency_id.name or "", "destination": label})
        self.meeting_id._broadcast_live_sync()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

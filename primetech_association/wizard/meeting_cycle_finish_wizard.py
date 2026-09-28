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
        treasury_lines = self.allocation_line_ids.filtered(
            lambda line: line.destination == "treasury" and line.amount > 0
        )
        treasury_funds = treasury_lines.mapped("fund_id")
        if len(treasury_funds) > 1:
            raise ValidationError(_(
                "Pour garantir un versement unique, choisissez un seul compte de trésorerie."
            ))
        treasury_amount = sum(treasury_lines.mapped("amount"))
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
            elif line.destination == "treasury":
                if not line.fund_id:
                    raise ValidationError(_("Sélectionnez le compte de trésorerie."))
                if line.fund_id.company_id != self.meeting_id.company_id:
                    raise ValidationError(_("Le compte de trésorerie doit appartenir à la société de la réunion."))
                # Les lignes de trésorerie sont regroupées après la boucle.
        if treasury_amount:
            fund = treasury_funds[:1]
            self.meeting_id._cancel_legacy_membership_fee_receipts()
            transaction = self.env["association.fund.transaction"].create({
                "company_id": self.meeting_id.company_id.id,
                "fund_id": fund.id,
                "transaction_type": "in",
                "amount": treasury_amount,
                "transaction_date": fields.Date.context_today(self),
                "description": _("Versement consolidé de la caisse de séance %(meeting)s") % {"meeting": self.meeting_id.display_name},
                "origin_model": "association.meeting",
                "origin_res_id": self.meeting_id.id,
                "origin_reference": self.meeting_id.name,
            })
            transaction.action_validate()
            self.period_id.settled_amount += treasury_amount
            self.meeting_id.write({
                "pot_settlement_state": "settled",
                "pot_settlement_fund_id": fund.id,
                "pot_settlement_transaction_id": transaction.id,
            })
        self.period_id.invalidate_recordset(["available_amount"])
        self.meeting_id.invalidate_recordset([
            "pot_collected_amount", "pot_allocated_amount", "pot_available_amount",
        ])
        session = self.meeting_id.subscription_session_ids.filtered(
            lambda item: item.period_id == self.period_id
        )[:1]
        if self.apply_penalties:
            # Do not apply penalties silently from the meeting.  The
            # treasurer is taken to the running subscription, where the
            # penalty configuration and affected members are visible.  The
            # session id is kept in context: finalising the cycle from there
            # returns through the existing meeting refresh action.
            if session:
                session.write({"state": "decision"})
            return {
                "type": "ir.actions.act_window",
                "name": _("Appliquer les pénalités et terminer le cycle"),
                "res_model": "association.subscription",
                "res_id": self.period_id.subscription_id.id,
                "view_mode": "form",
                "views": [[False, "form"]],
                "target": "current",
                "context": {
                    "default_meeting_subscription_session_id": session.id if session else False,
                    "default_return_meeting_id": self.meeting_id.id,
                    "default_return_meeting_tab": "subscription",
                    "from_meeting_cycle_finish": True,
                },
            }
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

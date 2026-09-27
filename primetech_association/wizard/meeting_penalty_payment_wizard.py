# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMeetingPenaltyPaymentWizard(models.TransientModel):
    _name = "association.meeting.penalty.payment.wizard"
    _description = "Encaissement d'une sanction en séance"

    penalty_id = fields.Many2one("association.penalty", string="Sanction financière", required=True, readonly=True)
    meeting_id = fields.Many2one(related="penalty_id.meeting_id", readonly=True)
    member_id = fields.Many2one(related="penalty_id.member_id", readonly=True)
    company_id = fields.Many2one(related="penalty_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="penalty_id.currency_id", readonly=True)
    amount_remaining = fields.Monetary(related="penalty_id.amount_remaining", currency_field="currency_id", readonly=True)
    amount_received = fields.Monetary(string="Montant encaissé", currency_field="currency_id", required=True)
    payment_method = fields.Selection([
        ("cash", "Espèces"), ("bank", "Virement bancaire"),
        ("mobile_money", "Mobile Money"), ("other", "Autre"),
    ], string="Mode de paiement", required=True, default="cash")
    payment_reference = fields.Char(string="Référence")

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        penalty = self.env["association.penalty"].browse(self.env.context.get("default_penalty_id")).exists()
        if penalty:
            values.setdefault("penalty_id", penalty.id)
            values.setdefault("amount_received", penalty.amount_remaining)
        return values

    def action_confirm(self):
        self.ensure_one()
        penalty = self.penalty_id
        meeting = self.meeting_id
        if not penalty or penalty.penalty_type != "fine" or penalty.recovery_origin != "sanction":
            raise ValidationError(_("La sanction financière sélectionnée n'est pas valide."))
        if penalty.state not in ("validated", "executed") or penalty.amount_remaining <= 0.01:
            raise ValidationError(_("Cette sanction est déjà réglée ou n'est plus exigible."))
        if not meeting or meeting.state != "in_progress" or meeting.pot_settlement_state != "open":
            raise ValidationError(_("Le recouvrement de la réunion est fermé : cette sanction ne peut plus être encaissée à la table."))
        amount = self.amount_received or 0.0
        if amount <= 0.0:
            raise ValidationError(_("Le montant encaissé doit être strictement supérieur à zéro."))
        if amount > penalty.amount_remaining + 0.01:
            raise ValidationError(_("Le montant ne peut pas dépasser le reste de la sanction."))

        payment = self.env["association.payment"].create({
            "member_id": penalty.member_id.id,
            "company_id": penalty.company_id.id,
            "meeting_id": meeting.id,
            "payment_date": fields.Date.context_today(self),
            "amount": amount,
            "payment_source": "meeting_cash",
            "payment_method": self.payment_method,
            "payment_reference": self.payment_reference or _("Règlement de la sanction %s" % penalty.display_name),
            "has_allocations": True,
            "priority_allocation_amount": amount,
            "priority_allocation_payload": [{"penalty_id": penalty.id, "amount": amount}],
        })
        payment.action_collect()
        payment.action_confirm()
        meeting.invalidate_recordset(["pot_collected_amount", "pot_available_amount", "treasury_member_situation_ids"])
        return {"type": "ir.actions.client", "tag": "soft_reload"}

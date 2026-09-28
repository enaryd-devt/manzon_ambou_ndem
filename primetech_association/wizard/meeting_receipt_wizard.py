# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AssociationMeetingReceiptWizard(models.TransientModel):
    _name = "association.meeting.receipt.wizard"
    _description = "Saisie d’une recette de séance"

    meeting_id = fields.Many2one("association.meeting", required=True, readonly=True)
    company_id = fields.Many2one(related="meeting_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="meeting_id.currency_id", readonly=True)
    contributor_type = fields.Selection(
        [("member", "Membre"), ("external", "Contributeur externe")],
        string="Contributeur", required=True, default="member",
    )
    member_id = fields.Many2one(
        "association.member", string="Membre",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    contributor_name = fields.Char(string="Nom du contributeur externe")
    amount = fields.Monetary(string="Montant reçu", currency_field="currency_id", required=True)
    reason = fields.Text(string="Raison / motif", required=True)
    payment_method = fields.Selection(
        [("cash", "Espèces"), ("mobile_money", "Mobile Money"),
         ("bank", "Virement"), ("other", "Autre")],
        string="Mode de réception", required=True, default="cash",
    )

    def action_confirm(self):
        self.ensure_one()
        if self.meeting_id.state != "in_progress":
            raise ValidationError(_("Une recette ne peut être enregistrée que pendant une réunion en cours."))
        if self.amount <= 0:
            raise ValidationError(_("Le montant de la recette doit être strictement positif."))
        if self.contributor_type == "member" and not self.member_id:
            raise ValidationError(_("Sélectionnez le membre qui a versé la recette."))
        if self.contributor_type == "external" and not (self.contributor_name or "").strip():
            raise ValidationError(_("Saisissez le nom du contributeur externe."))
        receipt = self.env["association.meeting.receipt"].create({
            "meeting_id": self.meeting_id.id,
            "receipt_date": self.meeting_id.meeting_date,
            "contributor_type": self.contributor_type,
            "member_id": self.member_id.id,
            "contributor_name": (self.contributor_name or "").strip(),
            "amount": self.amount,
            "reason": self.reason.strip(),
            "payment_method": self.payment_method,
        })
        self.meeting_id.message_post(body=_(
            "Recette de séance enregistrée : %(amount).2f %(currency)s reçus de %(contributor)s."
        ) % {
            "amount": receipt.amount,
            "currency": self.currency_id.name or "",
            "contributor": receipt.contributor_display,
        })
        self.meeting_id._broadcast_live_sync()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AssociationMeetingReceipt(models.Model):
    _name = "association.meeting.receipt"
    _description = "Recette de séance"
    _order = "receipt_date desc, id desc"
    _rec_name = "contributor_display"

    meeting_id = fields.Many2one(
        "association.meeting", string="Réunion", required=True,
        ondelete="cascade", index=True, readonly=True,
    )
    company_id = fields.Many2one(
        related="meeting_id.company_id", store=True, readonly=True,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True,
    )
    receipt_date = fields.Date(
        string="Date", required=True, default=fields.Date.context_today,
    )
    contributor_type = fields.Selection(
        [("member", "Membre"), ("external", "Contributeur externe")],
        string="Contributeur", required=True, default="member",
    )
    member_id = fields.Many2one(
        "association.member", string="Membre", ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    contributor_name = fields.Char(string="Nom du contributeur")
    contributor_display = fields.Char(
        string="Contributeur", compute="_compute_contributor_display", store=True,
    )
    amount = fields.Monetary(
        string="Montant reçu", currency_field="currency_id", required=True,
    )
    reason = fields.Text(string="Raison / motif", required=True)
    payment_method = fields.Selection(
        [("cash", "Espèces"), ("mobile_money", "Mobile Money"),
         ("bank", "Virement"), ("other", "Autre")],
        string="Mode de réception", required=True, default="cash",
    )
    state = fields.Selection(
        [("confirmed", "Confirmée"), ("cancelled", "Annulée")],
        string="État", required=True, default="confirmed", readonly=True,
    )

    @api.depends("contributor_type", "member_id", "contributor_name")
    def _compute_contributor_display(self):
        for receipt in self:
            receipt.contributor_display = (
                receipt.member_id.display_name if receipt.contributor_type == "member"
                else receipt.contributor_name
            ) or ""

    @api.constrains("meeting_id", "contributor_type", "member_id", "contributor_name", "amount", "reason")
    def _check_receipt(self):
        for receipt in self:
            if receipt.meeting_id.state != "in_progress":
                raise ValidationError(_("Une recette ne peut être enregistrée que pendant une réunion en cours."))
            if receipt.amount <= 0:
                raise ValidationError(_("Le montant de la recette doit être strictement positif."))
            if not receipt.reason or not receipt.reason.strip():
                raise ValidationError(_("Veuillez saisir la raison ou le motif de la recette."))
            if receipt.contributor_type == "member" and not receipt.member_id:
                raise ValidationError(_("Sélectionnez le membre qui a versé la recette."))
            if receipt.contributor_type == "external" and not (receipt.contributor_name or "").strip():
                raise ValidationError(_("Saisissez le nom du contributeur externe."))


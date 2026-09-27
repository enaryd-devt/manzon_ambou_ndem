# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AssociationSubscriptionMemberAddWizard(models.TransientModel):
    _name = "association.subscription.member.add.wizard"
    _description = "Ajout d’un membre à une cotisation en cours"

    subscription_id = fields.Many2one(
        "association.subscription", string="Cotisation", required=True, readonly=True,
    )
    company_id = fields.Many2one(related="subscription_id.company_id", readonly=True)
    member_id = fields.Many2one(
        "association.member", string="Membre", required=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    include_past_periods = fields.Boolean(
        string="Ajouter les cycles passés à payer",
        default=False,
        help="Les cycles terminés non réglés seront placés avant le cycle courant pour ce membre.",
    )

    def action_confirm(self):
        self.ensure_one()
        if self.subscription_id.state != "running":
            raise ValidationError(_("Le membre ne peut être ajouté que sur une cotisation en cours."))
        existing = self.env["association.subscription.line"].search([
            ("subscription_id", "=", self.subscription_id.id),
            ("member_id", "=", self.member_id.id),
        ], limit=1)
        if existing:
            raise ValidationError(_("Ce membre participe déjà à cette cotisation."))
        self.env["association.subscription.line"].create({
            "subscription_id": self.subscription_id.id,
            "member_id": self.member_id.id,
            "include_past_periods": self.include_past_periods,
        })
        return {"type": "ir.actions.client", "tag": "soft_reload"}

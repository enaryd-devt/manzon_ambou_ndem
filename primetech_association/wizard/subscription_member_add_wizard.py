# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AssociationSubscriptionMemberAddWizard(models.TransientModel):
    _name = "association.subscription.member.add.wizard"
    _description = "Ajout d’un membre à une cotisation en cours"

    subscription_id = fields.Many2one(
        "association.subscription", string="Cotisation", required=True, readonly=True,
    )
    company_id = fields.Many2one(related="subscription_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="subscription_id.currency_id", readonly=True)
    subscription_type = fields.Selection(related="subscription_id.subscription_type", readonly=True)
    member_id = fields.Many2one(
        "association.member", string="Membre", required=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    include_past_periods = fields.Boolean(
        string="Ajouter les cycles passés à payer",
        default=False,
        help="Les cycles terminés non réglés seront placés avant le cycle courant pour ce membre.",
    )
    recovery_amount = fields.Monetary(
        string="Montant individuel à recouvrer",
        currency_field="currency_id",
        help="Montant dû par ce membre pour ce recouvrement sans cycle.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        subscription_id = values.get("subscription_id") or self.env.context.get(
            "default_subscription_id"
        )
        subscription = self.env["association.subscription"].browse(subscription_id).exists()
        if subscription and subscription.subscription_type == "recovery":
            values.setdefault("recovery_amount", subscription.amount or 0.0)
        return values

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
        if (
            self.subscription_id.subscription_type == "recovery"
            and (self.recovery_amount or 0.0) <= 0.0
        ):
            raise ValidationError(_(
                "Le montant individuel du recouvrement doit être strictement positif."
            ))
        line_values = {
            "subscription_id": self.subscription_id.id,
            "member_id": self.member_id.id,
            "include_past_periods": self.include_past_periods,
        }
        if self.subscription_id.subscription_type == "recovery":
            line_values["recovery_amount"] = self.recovery_amount
        self.env["association.subscription.line"].with_context(
            allow_running_member_add=True,
        ).create(line_values)
        return {"type": "ir.actions.client", "tag": "soft_reload"}

# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AssociationMemberSituationWizard(models.TransientModel):
    """Consultation rapide de la situation d'un membre depuis le tableau de bord."""

    _name = "association.member.situation.wizard"
    _description = "Consultation rapide de la situation d'un membre"

    member_id = fields.Many2one(
        "association.member", string="Membre",
        domain="[('company_id', 'in', [False, current_company_id])]",
    )
    currency_id = fields.Many2one(related="member_id.company_id.currency_id")
    situation_balance = fields.Monetary(
        string="Reste à payer", currency_field="currency_id",
        compute="_compute_situation",
    )
    situation_html = fields.Html(
        string="Situation", sanitize=False, compute="_compute_situation",
    )

    @api.depends("member_id")
    def _compute_situation(self):
        for wizard in self:
            member = wizard.member_id
            if not member:
                wizard.situation_balance = 0.0
                wizard.situation_html = False
                continue
            items = member._get_financial_situation_items()
            wizard.situation_balance = sum(item["balance"] for item in items)
            wizard.situation_html = member._render_financial_situation_html(items)

    def _get_member(self):
        self.ensure_one()
        if not self.member_id:
            raise UserError(_("Sélectionnez un membre."))
        return self.member_id

    def action_view_detail(self):
        return self._get_member().action_view_subscriptions()

    def action_print_situation_report(self):
        return self._get_member().action_print_situation_report()

    def action_register_payment(self):
        return self._get_member().action_register_situation_payment()

    def action_open_member(self):
        member = self._get_member()
        return {
            "type": "ir.actions.act_window",
            "name": member.display_name,
            "res_model": "association.member",
            "res_id": member.id,
            "view_mode": "form",
            "target": "current",
        }

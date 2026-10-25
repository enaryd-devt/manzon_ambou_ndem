# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class AssociationPenaltyLiftWizard(models.TransientModel):
    _name = "association.penalty.lift.wizard"
    _description = "Levée de sanction"

    penalty_id = fields.Many2one("association.penalty", string="Sanction", required=True, readonly=True)
    member_id = fields.Many2one(related="penalty_id.member_id", string="Membre", readonly=True)
    reason = fields.Text(string="Motif de levée", required=True)

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise ValidationError(_("Le motif de levée est obligatoire."))
        self.penalty_id.write({"lift_reason": self.reason.strip()})
        self.penalty_id.action_lift()
        return {"type": "ir.actions.act_window_close"}

from odoo import _, fields, models
from odoo.exceptions import UserError


class AssociationMeetingExpenseWizard(models.TransientModel):
    _name = "association.meeting.expense.wizard"
    _description = "Saisie simplifiée d’une dépense de séance"

    meeting_id = fields.Many2one("association.meeting", required=True, readonly=True)
    currency_id = fields.Many2one(related="meeting_id.currency_id", readonly=True)
    available_amount = fields.Monetary(related="meeting_id.pot_available_amount", currency_field="currency_id", readonly=True)
    expense_kind = fields.Selection([
        ("beverages", "Boissons"), ("catering", "Repas / restauration"), ("supplies", "Fournitures de séance"), ("other", "Autre"),
    ], string="Nature", required=True, default="beverages")
    beneficiary_name = fields.Char(string="Fournisseur / bénéficiaire", required=True)
    amount = fields.Monetary(string="Montant", currency_field="currency_id", required=True)
    note = fields.Char(string="Précision")

    def action_confirm(self):
        self.ensure_one()
        if self.amount <= 0:
            raise UserError(_("Le montant de la dépense doit être supérieur à zéro."))
        if self.amount > self.available_amount:
            raise UserError(_("La dépense dépasse l’argent actuellement collecté pendant cette séance."))
        labels = dict(self._fields["expense_kind"]._description_selection(self.env))
        expense = self.env["association.expense"].create({
            "meeting_id": self.meeting_id.id,
            "company_id": self.meeting_id.company_id.id,
            "expense_date": self.meeting_id.meeting_date,
            "expense_type": "event",
            "subject": _("%s – réunion %s") % (labels[self.expense_kind], self.meeting_id.name),
            "beneficiary_type": "external",
            "beneficiary_name": self.beneficiary_name,
            "amount": self.amount,
            "payment_method": "cash",
            "description": self.note or False,
        })
        expense.action_validate()
        return {"type": "ir.actions.client", "tag": "soft_reload"}


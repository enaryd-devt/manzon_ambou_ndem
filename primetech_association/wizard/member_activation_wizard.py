from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AssociationMemberActivationWizard(models.TransientModel):
    _name = "association.member.activation.wizard"
    _description = "Activation d’un membre"

    member_id = fields.Many2one("association.member", required=True, readonly=True)
    company_id = fields.Many2one(related="member_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie", required=True,
                              domain="[('company_id', '=', company_id), ('active', '=', True)]")
    registration_fee_amount = fields.Monetary(string="Frais d’inscription", currency_field="currency_id", required=True, default=0.0)
    insurance_fee_amount = fields.Monetary(string="Frais d’assurance", currency_field="currency_id", required=True, default=0.0)
    forfait_recovery_fee_amount = fields.Monetary(string="Recouvrement forfaitaire", currency_field="currency_id", required=True, default=0.0)
    working_capital_catchup_amount = fields.Monetary(string="Rattrapage fonds de roulement échu", currency_field="currency_id", required=True, default=0.0)
    jogging_provided = fields.Boolean(string="Jogging apporté")
    traditional_outfit_provided = fields.Boolean(string="Tenue traditionnelle apportée")
    sport_jersey_provided = fields.Boolean(string="Maillot de sport apporté")
    committee_beer_case_provided = fields.Boolean(string="Casier de bière – Comité apporté")
    ag_beer_case_provided = fields.Boolean(string="Casier de bière – AG apporté")
    total_fee_amount = fields.Monetary(string="Total des frais", currency_field="currency_id", compute="_compute_total")

    def _compute_total(self):
        for wizard in self:
            wizard.total_fee_amount = sum((wizard.registration_fee_amount, wizard.insurance_fee_amount, wizard.forfait_recovery_fee_amount, wizard.working_capital_catchup_amount))

    def action_confirm(self):
        self.ensure_one()
        fees = (self.registration_fee_amount, self.insurance_fee_amount, self.forfait_recovery_fee_amount, self.working_capital_catchup_amount)
        if any(amount <= 0 for amount in fees):
            raise ValidationError(_("Chaque frais d’adhésion doit avoir un montant strictement positif."))
        if not all((self.jogging_provided, self.traditional_outfit_provided, self.sport_jersey_provided, self.committee_beer_case_provided, self.ag_beer_case_provided)):
            raise ValidationError(_("Confirmez tous les biens apportés avant d’activer le membre."))
        values = {name: getattr(self, name) for name in (
            "registration_fee_amount", "insurance_fee_amount", "forfait_recovery_fee_amount", "working_capital_catchup_amount",
            "jogging_provided", "traditional_outfit_provided", "sport_jersey_provided", "committee_beer_case_provided", "ag_beer_case_provided",
        )}
        self.member_id.write(values)
        transaction = self.env["association.fund.transaction"].create({
            "fund_id": self.fund_id.id, "company_id": self.company_id.id,
            "transaction_type": "in", "amount": self.total_fee_amount,
            "description": _("Frais d’adhésion – %s") % self.member_id.display_name,
            "origin_model": "association.member", "origin_res_id": self.member_id.id,
            "origin_reference": self.member_id.member_code or self.member_id.display_name,
            "note": _("Inscription : %(registration)s ; Assurance : %(insurance)s ; "
                      "Recouvrement forfaitaire : %(recovery)s ; Rattrapage fonds de roulement : %(catchup)s") % {
                          "registration": self.registration_fee_amount,
                          "insurance": self.insurance_fee_amount,
                          "recovery": self.forfait_recovery_fee_amount,
                          "catchup": self.working_capital_catchup_amount,
                      },
        })
        transaction.action_validate()
        self.member_id.with_context(confirm_membership_activation=True).action_activate()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

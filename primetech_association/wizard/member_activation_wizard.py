from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AssociationMemberActivationWizard(models.TransientModel):
    _name = "association.member.activation.wizard"
    _description = "Activation d’un membre"

    member_id = fields.Many2one("association.member", required=True, readonly=True)
    company_id = fields.Many2one(related="member_id.company_id", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    fund_id = fields.Many2one("association.fund", string="Compte de trésorerie des frais d’adhésion", required=True,
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
    jogging_amount = fields.Monetary(string="Montant du jogging", currency_field="currency_id", required=True, default=0.0)
    traditional_outfit_amount = fields.Monetary(string="Montant de la tenue traditionnelle", currency_field="currency_id", required=True, default=0.0)
    sport_jersey_amount = fields.Monetary(string="Montant du maillot de sport", currency_field="currency_id", required=True, default=0.0)
    committee_beer_case_amount = fields.Monetary(string="Montant du casier de bière – Comité", currency_field="currency_id", required=True, default=0.0)
    ag_beer_case_amount = fields.Monetary(string="Montant du casier de bière – AG", currency_field="currency_id", required=True, default=0.0)
    total_fee_amount = fields.Monetary(string="Total des frais", currency_field="currency_id", compute="_compute_total")

    def _compute_total(self):
        for wizard in self:
            wizard.total_fee_amount = sum((
                wizard.registration_fee_amount, wizard.insurance_fee_amount,
                wizard.forfait_recovery_fee_amount, wizard.working_capital_catchup_amount,
                wizard.jogging_amount, wizard.traditional_outfit_amount,
                wizard.sport_jersey_amount, wizard.committee_beer_case_amount,
                wizard.ag_beer_case_amount,
            ))

    def action_confirm(self):
        self.ensure_one()
        fees = (
            self.registration_fee_amount, self.insurance_fee_amount,
            self.forfait_recovery_fee_amount, self.working_capital_catchup_amount,
            self.jogging_amount, self.traditional_outfit_amount,
            self.sport_jersey_amount, self.committee_beer_case_amount,
            self.ag_beer_case_amount,
        )
        if any(amount <= 0 for amount in fees):
            raise ValidationError(_("Chaque frais d’adhésion doit avoir un montant strictement positif."))
        values = {name: getattr(self, name) for name in (
            "registration_fee_amount", "insurance_fee_amount", "forfait_recovery_fee_amount", "working_capital_catchup_amount",
            "jogging_provided", "traditional_outfit_provided", "sport_jersey_provided", "committee_beer_case_provided", "ag_beer_case_provided",
            "jogging_amount", "traditional_outfit_amount", "sport_jersey_amount", "committee_beer_case_amount", "ag_beer_case_amount",
        )}
        self.member_id.write(values)
        MembershipFee = self.env["association.membership.fee"]
        fees = (
            (_("Frais d’inscription"), self.registration_fee_amount),
            (_("Frais d’assurance"), self.insurance_fee_amount),
            (_("Recouvrement forfaitaire"), self.forfait_recovery_fee_amount),
            (_("Rattrapage des fonds de roulement échus"), self.working_capital_catchup_amount),
            (_("Jogging"), self.jogging_amount),
            (_("Tenue traditionnelle"), self.traditional_outfit_amount),
            (_("Maillot de sport"), self.sport_jersey_amount),
            (_("Casier de bière – Comité"), self.committee_beer_case_amount),
            (_("Casier de bière – AG"), self.ag_beer_case_amount),
        )
        for label, amount in fees:
            MembershipFee.create({
                "member_id": self.member_id.id,
                "fund_id": self.fund_id.id,
                "name": label,
                "amount": amount,
            })
        self.member_id.with_context(confirm_membership_activation=True).action_activate()
        return {"type": "ir.actions.client", "tag": "soft_reload"}

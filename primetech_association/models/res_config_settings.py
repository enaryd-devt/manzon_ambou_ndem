# -*- coding: utf-8 -*-

##############################################################################
#
#    PrimeTech Association Management
#
##############################################################################

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    association_name = fields.Char(
        string="Association Name",
        config_parameter="primetech_association.association_name",
    )

    membership_prefix = fields.Char(
        string="Membership Number Prefix",
        default="MEM",
        config_parameter="primetech_association.membership_prefix",
    )

    membership_card_validity = fields.Integer(
        string="Membership Card Validity (Months)",
        default=12,
        config_parameter="primetech_association.membership_card_validity",
    )

    # Fields prefixed with ``default_`` have a special meaning on
    # res.config.settings: Odoo treats them as defaults for another model and
    # consequently requires a ``default_model`` attribute.  This setting is a
    # regular system parameter, so keep the existing parameter key while using
    # a non-reserved field name.
    subscription_default_amount = fields.Float(
        string="Default Subscription Amount",
        default=0.0,
        config_parameter="primetech_association.default_subscription_amount",
    )

    allow_partial_payment = fields.Boolean(
        string="Allow Partial Payments",
        default=True,
        config_parameter="primetech_association.allow_partial_payment",
    )

    require_member_photo = fields.Boolean(
        string="Require Member Photo",
        default=False,
        config_parameter="primetech_association.require_member_photo",
    )

    automatic_member_number = fields.Boolean(
        string="Automatic Member Number",
        default=True,
        config_parameter="primetech_association.automatic_member_number",
    )

    settlement_fund_id = fields.Many2one(
        "association.fund", string="Compte de règlement par défaut",
        config_parameter="primetech_association.default_settlement_fund_id",
    )
    settlement_policy = fields.Selection([
        ("decision", "Décision à la clôture"),
        ("treasury", "Verser le reliquat en trésorerie"),
    ], string="Traitement du reliquat", default="decision",
       config_parameter="primetech_association.settlement_policy")
    require_session_settlement = fields.Boolean(
        string="Exiger le règlement des sessions avant la clôture",
        default=True,
        config_parameter="primetech_association.require_session_settlement",
    )
    settlement_tolerance = fields.Float(
        string="Tolérance de règlement", default=0.01,
        config_parameter="primetech_association.settlement_tolerance",
    )
    allow_member_account_payment = fields.Boolean(
        string="Autoriser le paiement depuis le compte membre", default=True,
        config_parameter="primetech_association.allow_member_account_payment",
    )
    member_account_debit_timing = fields.Selection([
        ("finalization", "À la finalisation du cycle"),
        ("immediate", "À la confirmation du paiement"),
    ], string="Débit du compte membre", default="finalization",
       config_parameter="primetech_association.member_account_debit_timing")
    surplus_policy = fields.Selection([
        ("ask", "Demander à chaque surplus"),
        ("credit", "Créditer le compte membre"),
        ("refund", "Rembourser le surplus"),
    ], string="Traitement par défaut des surplus", default="ask",
       config_parameter="primetech_association.surplus_policy")
    payment_reference_prefix = fields.Char(
        string="Préfixe des références de paiement", default="PAY",
        config_parameter="primetech_association.payment_reference_prefix",
    )
    payment_method_cash = fields.Boolean(
        string="Espèces", default=True,
        config_parameter="primetech_association.payment_method_cash",
    )
    payment_method_bank = fields.Boolean(
        string="Virement bancaire", default=True,
        config_parameter="primetech_association.payment_method_bank",
    )
    payment_method_cheque = fields.Boolean(
        string="Chèque", default=True,
        config_parameter="primetech_association.payment_method_cheque",
    )
    payment_method_mobile_money = fields.Boolean(
        string="Mobile Money", default=True,
        config_parameter="primetech_association.payment_method_mobile_money",
    )
    payment_method_other = fields.Boolean(
        string="Autre", default=True,
        config_parameter="primetech_association.payment_method_other",
    )
    report_footer = fields.Char(
        string="Pied de page des rapports",
        config_parameter="primetech_association.report_footer",
    )
    late_penalty_amount = fields.Float(
        string="Sanction financière par retard",
        config_parameter="primetech_association.late_penalty_amount",
        help="Montant automatiquement appliqué à chaque retard. Laissez 0 pour désactiver.",
    )
    consecutive_absence_penalty_amount = fields.Float(
        string="Montant de base après deux absences",
        config_parameter="primetech_association.consecutive_absence_penalty_amount",
        help="Deux absences consécutives appliquent ce montant, trois absences le double, etc.",
    )

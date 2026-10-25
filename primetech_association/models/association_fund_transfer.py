# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AssociationFundTransfer(models.Model):
    _name = "association.fund.transfer"
    _description = "Transfert entre comptes de trésorerie"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "transfer_date desc, id desc"

    name = fields.Char(string="Référence", readonly=True, copy=False, default="Nouveau", tracking=True)
    company_id = fields.Many2one("res.company", string="Société", required=True, default=lambda self: self.env.company, readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id", readonly=True)
    transfer_date = fields.Date(string="Date", required=True, default=fields.Date.context_today, tracking=True)
    source_fund_id = fields.Many2one("association.fund", string="Compte source", required=True, ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True)
    destination_fund_id = fields.Many2one("association.fund", string="Compte destination", required=True, ondelete="restrict", domain="[('company_id', '=', company_id), ('active', '=', True)]", tracking=True)
    source_balance = fields.Monetary(related="source_fund_id.current_balance", string="Solde disponible", currency_field="currency_id", readonly=True)
    destination_balance = fields.Monetary(related="destination_fund_id.current_balance", string="Solde actuel", currency_field="currency_id", readonly=True)
    amount = fields.Monetary(string="Montant à transférer", currency_field="currency_id", required=True, tracking=True)
    description = fields.Char(string="Libellé", required=True, default="Transfert interne", tracking=True)
    note = fields.Html(string="Observation")
    state = fields.Selection([("draft", "Brouillon"), ("validated", "Validé"), ("cancelled", "Annulé")], default="draft", required=True, tracking=True)
    source_transaction_id = fields.Many2one("association.fund.transaction", string="Sortie générée", readonly=True, copy=False, ondelete="restrict")
    destination_transaction_id = fields.Many2one("association.fund.transaction", string="Entrée générée", readonly=True, copy=False, ondelete="restrict")
    transaction_count = fields.Integer(string="Mouvements générés", compute="_compute_transaction_count")

    _sql_constraints = [
        ("fund_transfer_positive_amount", "CHECK(amount > 0)", "Le montant du transfert doit être supérieur à zéro."),
    ]

    @api.depends("source_transaction_id", "destination_transaction_id")
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.source_transaction_id | record.destination_transaction_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = self.env["ir.sequence"].next_by_code("association.fund.transfer") or "Nouveau"
        return super().create(vals_list)

    @api.constrains("source_fund_id", "destination_fund_id")
    def _check_distinct_funds(self):
        for record in self:
            if record.source_fund_id and record.source_fund_id == record.destination_fund_id:
                raise ValidationError(_("Le compte source et le compte destination doivent être différents."))

    def write(self, vals):
        protected = {"transfer_date", "source_fund_id", "destination_fund_id", "amount", "description", "note", "company_id"}
        if protected.intersection(vals) and any(record.state != "draft" for record in self):
            raise UserError(_("Un transfert validé ne peut plus être modifié."))
        return super().write(vals)

    def action_validate(self):
        Transaction = self.env["association.fund.transaction"]
        for record in self:
            if record.state != "draft":
                continue
            if record.amount > record.source_fund_id.current_balance:
                raise ValidationError(_(
                    "Solde insuffisant sur le compte source.\n\nSolde disponible : %(available)s\nMontant demandé : %(amount)s"
                ) % {"available": record.source_fund_id.current_balance, "amount": record.amount})
            source = Transaction.create({
                "fund_id": record.source_fund_id.id,
                "transaction_type": "out",
                "amount": record.amount,
                "transaction_date": record.transfer_date,
                "description": _("Transfert vers %(fund)s - %(reference)s") % {"fund": record.destination_fund_id.display_name, "reference": record.name},
                "company_id": record.company_id.id,
                "origin_model": record._name,
                "origin_res_id": record.id,
                "origin_reference": record.name,
            })
            destination = Transaction.create({
                "fund_id": record.destination_fund_id.id,
                "transaction_type": "in",
                "amount": record.amount,
                "transaction_date": record.transfer_date,
                "description": _("Transfert depuis %(fund)s - %(reference)s") % {"fund": record.source_fund_id.display_name, "reference": record.name},
                "company_id": record.company_id.id,
                "origin_model": record._name,
                "origin_res_id": record.id,
                "origin_reference": record.name,
            })
            source.action_validate()
            destination.action_validate()
            record.write({
                "source_transaction_id": source.id,
                "destination_transaction_id": destination.id,
                "state": "validated",
            })
        return True

    def action_cancel(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Seul un transfert en brouillon peut être annulé."))
            record.write({"state": "cancelled"})
        return True

    def action_view_transactions(self):
        self.ensure_one()
        transaction_ids = (self.source_transaction_id | self.destination_transaction_id).ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Mouvements générés"),
            "res_model": "association.fund.transaction",
            "view_mode": "list,form",
            "domain": [("id", "in", transaction_ids)],
            "context": {"create": False},
        }

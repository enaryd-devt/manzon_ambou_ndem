# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError

class AssociationMeetingCollectionSurplusWizard(models.TransientModel):
    _name = 'association.meeting.collection.surplus.wizard'
    _description = "Traitement du surplus d'encaissement en réunion"

    collection_id = fields.Many2one('association.meeting.collection', required=True, readonly=True)
    member_id = fields.Many2one(related='collection_id.member_id', readonly=True)
    currency_id = fields.Many2one(related='collection_id.currency_id', readonly=True)
    amount_received = fields.Monetary(currency_field='currency_id', readonly=True)
    amount_to_pay = fields.Monetary(currency_field='currency_id', readonly=True)
    surplus_amount = fields.Monetary(currency_field='currency_id', readonly=True)
    surplus_action = fields.Selection([('refund', 'Rembourser le surplus'), ('credit_account', 'Approvisionner le compte du membre')], required=True, default='credit_account')

    def action_process(self):
        self.ensure_one()
        collection = self.collection_id
        if self.surplus_amount <= 0:
            raise UserError(_('Aucun surplus à traiter.'))
        collection._process_cash_collection(self.amount_to_pay)
        if self.surplus_action == 'credit_account':
            Account = self.env['association.member.account']
            account = Account.search([('member_id', '=', collection.member_id.id)], limit=1)
            if not account:
                account = Account.create({'member_id': collection.member_id.id, 'company_id': collection.company_id.id})
            transaction = self.env['association.member.account.transaction'].create({
                'account_id': account.id, 'transaction_type': 'credit', 'amount': self.surplus_amount,
                'transaction_date': fields.Date.context_today(self),
                'description': _('Surplus encaissement %s - réunion %s') % (collection.subscription_id.display_name, collection.meeting_id.display_name),
            })
            if hasattr(transaction, 'action_confirm'):
                transaction.action_confirm()
        collection.write({
            'processed_surplus_amount': self.surplus_amount,
            'surplus_action': self.surplus_action,
        })
        collection.meeting_id.message_post(body=_('Surplus de %.2f %s : %s.') % (self.surplus_amount, collection.currency_id.name or '', dict(self._fields['surplus_action'].selection).get(self.surplus_action)))
        return {'type': 'ir.actions.act_window_close'}

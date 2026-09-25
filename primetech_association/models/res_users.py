# -*- coding: utf-8 -*-
"""Association roles exposed directly on user accounts.

Odoo only exposes automatically generated boolean group controls in developer
mode. Meeting roles are independent groups, so these fields provide a safe,
server-side editing surface for Settings administrators.
"""

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


CORE_GROUP_XMLIDS = {
    'member': 'primetech_association.group_association_member',
    'user': 'primetech_association.group_association_user',
    'manager': 'primetech_association.group_association_manager',
    'admin': 'primetech_association.group_association_admin',
}

MEETING_ROLE_XMLIDS = {
    'association_meeting_president': 'primetech_association.group_association_meeting_president',
    'association_meeting_secretary': 'primetech_association.group_association_meeting_secretary',
    'association_meeting_vice_president': 'primetech_association.group_association_meeting_vice_president',
    'association_meeting_vice_secretary': 'primetech_association.group_association_meeting_vice_secretary',
    'association_accountant': 'primetech_association.group_association_accountant',
    'association_meeting_treasurer': 'primetech_association.group_association_meeting_treasurer',
    'association_meeting_censor': 'primetech_association.group_association_meeting_censor',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    association_member_id = fields.Many2one(
        'association.member',
        string='Membre associé',
        compute='_compute_association_member_id',
        inverse='_inverse_association_member_id',
        help="Fiche membre reliée à ce compte utilisateur.",
    )

    association_access_level = fields.Selection(
        [
            ('member', 'Membre ordinaire'),
            ('user', 'Utilisateur Association'),
            ('manager', 'Responsable Association'),
            ('admin', 'Administrateur Association'),
        ],
        string='Niveau d’accès Association',
        compute='_compute_association_access_level',
        inverse='_inverse_association_access_level',
        help='Le niveau le plus élevé est conservé. Les droits inférieurs sont accordés par implication.',
    )
    association_meeting_president = fields.Boolean(
        string='Président de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_president',
    )
    association_meeting_secretary = fields.Boolean(
        string='Secrétaire de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_secretary',
    )
    association_meeting_vice_president = fields.Boolean(
        string='Vice-président de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_vice_president',
    )
    association_meeting_vice_secretary = fields.Boolean(
        string='Vice-secrétaire de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_vice_secretary',
    )
    association_accountant = fields.Boolean(
        string='Comptable Association', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_accountant',
    )
    association_meeting_treasurer = fields.Boolean(
        string='Trésorier de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_treasurer',
    )
    association_meeting_censor = fields.Boolean(
        string='Censeur de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_censor',
    )

    def _compute_association_member_id(self):
        """Expose the member link on the user card without duplicating data."""
        members_by_user = {}
        if self.ids:
            members = self.env['association.member'].search([
                ('user_id', 'in', self.ids),
            ])
            members_by_user = {member.user_id.id: member for member in members}
        for user in self:
            user.association_member_id = members_by_user.get(user.id)

    def _inverse_association_member_id(self):
        Member = self.env['association.member']
        for user in self:
            selected_member = user.association_member_id
            if selected_member and selected_member.user_id and selected_member.user_id != user:
                raise ValidationError(
                    "Ce membre est déjà lié à un autre compte utilisateur."
                )
            linked_members = Member.search([
                ('user_id', '=', user.id),
                ('id', '!=', selected_member.id),
            ])
            linked_members.user_id = False
            if selected_member:
                selected_member.user_id = user.id

    @api.model
    def _association_group(self, xmlid):
        """Resolve an optional group without breaking a partial module upgrade."""
        return self.env.ref(xmlid, raise_if_not_found=False)

    @api.model
    def _association_core_groups(self):
        return self.env['res.groups'].browse([
            group.id for group in (self._association_group(xmlid) for xmlid in CORE_GROUP_XMLIDS.values()) if group
        ])

    @api.depends('groups_id')
    def _compute_association_access_level(self):
        groups_by_level = {
            level: self._association_group(xmlid)
            for level, xmlid in CORE_GROUP_XMLIDS.items()
        }
        for user in self:
            effective_group_ids = set((user.groups_id | user.groups_id.trans_implied_ids).ids)
            if groups_by_level['admin'] and groups_by_level['admin'].id in effective_group_ids:
                user.association_access_level = 'admin'
            elif groups_by_level['manager'] and groups_by_level['manager'].id in effective_group_ids:
                user.association_access_level = 'manager'
            elif groups_by_level['user'] and groups_by_level['user'].id in effective_group_ids:
                user.association_access_level = 'user'
            elif groups_by_level['member'] and groups_by_level['member'].id in effective_group_ids:
                user.association_access_level = 'member'
            else:
                user.association_access_level = False

    def _inverse_association_access_level(self):
        core_groups = self._association_core_groups()
        core_group_ids = set(core_groups.ids)
        for user in self:
            commands = [Command.unlink(group.id) for group in user.groups_id if group.id in core_group_ids]
            selected_group = self._association_group(CORE_GROUP_XMLIDS.get(user.association_access_level)) if user.association_access_level else False
            if selected_group:
                commands.append(Command.link(selected_group.id))
            if commands:
                user.groups_id = commands

    @api.depends('groups_id')
    def _compute_association_meeting_roles(self):
        groups_by_field = {
            field_name: self._association_group(xmlid)
            for field_name, xmlid in MEETING_ROLE_XMLIDS.items()
        }
        for user in self:
            for field_name, group in groups_by_field.items():
                setattr(user, field_name, bool(group and group in user.groups_id))

    def _set_association_meeting_role(self, field_name):
        group = self._association_group(MEETING_ROLE_XMLIDS[field_name])
        if not group:
            return
        for user in self:
            is_assigned = group in user.groups_id
            is_requested = bool(user[field_name])
            if is_requested and not is_assigned:
                user.groups_id = [Command.link(group.id)]
            elif not is_requested and is_assigned:
                user.groups_id = [Command.unlink(group.id)]

    def _inverse_association_meeting_president(self):
        self._set_association_meeting_role('association_meeting_president')

    def _inverse_association_meeting_secretary(self):
        self._set_association_meeting_role('association_meeting_secretary')

    def _inverse_association_meeting_vice_president(self):
        self._set_association_meeting_role('association_meeting_vice_president')

    def _inverse_association_meeting_vice_secretary(self):
        self._set_association_meeting_role('association_meeting_vice_secretary')

    def _inverse_association_accountant(self):
        self._set_association_meeting_role('association_accountant')

    def _inverse_association_meeting_treasurer(self):
        self._set_association_meeting_role('association_meeting_treasurer')

    def _inverse_association_meeting_censor(self):
        self._set_association_meeting_role('association_meeting_censor')

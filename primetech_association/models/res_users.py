# -*- coding: utf-8 -*-
"""Association roles exposed directly on user accounts.

Odoo only exposes automatically generated boolean group controls in developer
mode. Meeting roles are independent groups, so these fields provide a safe,
server-side editing surface for Settings administrators.
"""

from odoo import Command, api, fields, models


CORE_GROUP_XMLIDS = {
    'user': 'primetech_association.group_association_user',
    'manager': 'primetech_association.group_association_manager',
    'admin': 'primetech_association.group_association_admin',
}

MEETING_ROLE_XMLIDS = {
    'association_meeting_president': 'primetech_association.group_association_meeting_president',
    'association_meeting_secretary': 'primetech_association.group_association_meeting_secretary',
    'association_meeting_treasurer': 'primetech_association.group_association_meeting_treasurer',
    'association_meeting_censor': 'primetech_association.group_association_meeting_censor',
}


class ResUsers(models.Model):
    _inherit = 'res.users'

    association_access_level = fields.Selection(
        [
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
    association_meeting_treasurer = fields.Boolean(
        string='Trésorier de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_treasurer',
    )
    association_meeting_censor = fields.Boolean(
        string='Censeur de réunion', compute='_compute_association_meeting_roles',
        inverse='_inverse_association_meeting_censor',
    )

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
            effective_groups = user.groups_id.trans_implied_ids
            if groups_by_level['admin'] and groups_by_level['admin'] in effective_groups:
                user.association_access_level = 'admin'
            elif groups_by_level['manager'] and groups_by_level['manager'] in effective_groups:
                user.association_access_level = 'manager'
            elif groups_by_level['user'] and groups_by_level['user'] in effective_groups:
                user.association_access_level = 'user'
            else:
                user.association_access_level = False

    def _inverse_association_access_level(self):
        core_groups = self._association_core_groups()
        for user in self:
            commands = [Command.unlink(group.id) for group in user.groups_id & core_groups]
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

    def _inverse_association_meeting_treasurer(self):
        self._set_association_meeting_role('association_meeting_treasurer')

    def _inverse_association_meeting_censor(self):
        self._set_association_meeting_role('association_meeting_censor')

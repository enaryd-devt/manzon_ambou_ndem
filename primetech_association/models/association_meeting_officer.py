# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AssociationMeetingOfficer(models.Model):
    _name = "association.meeting.officer"
    _description = "Membre du bureau spécial de séance"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    meeting_id = fields.Many2one(
        "association.meeting",
        string="Réunion",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="meeting_id.company_id",
        store=True,
        readonly=True,
    )
    member_id = fields.Many2one(
        "association.member",
        string="Membre",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
    )
    role = fields.Selection(
        [
            ("chairperson", "Président de séance"),
            ("secretary", "Secrétaire de séance"),
            ("treasurer", "Trésorier de séance"),
            ("assessor", "Assesseur"),
            ("other", "Autre fonction"),
        ],
        string="Rôle pendant la séance",
        required=True,
        default="assessor",
    )
    note = fields.Char(string="Observation")

    _sql_constraints = [
        (
            "meeting_special_officer_member_unique",
            "unique(meeting_id, member_id)",
            "Un membre ne peut apparaître qu'une fois dans le bureau spécial.",
        ),
    ]

    @api.constrains("meeting_id", "role")
    def _check_unique_key_roles(self):
        for officer in self:
            if officer.role not in ("chairperson", "secretary"):
                continue
            duplicate = self.search_count([
                ("meeting_id", "=", officer.meeting_id.id),
                ("role", "=", officer.role),
                ("id", "!=", officer.id),
            ])
            if duplicate:
                raise ValidationError(
                    "Le président et le secrétaire doivent être uniques."
                )

    @api.onchange("role", "member_id")
    def _onchange_sync_meeting_responsible(self):
        for officer in self:
            if not officer.meeting_id or not officer.member_id:
                continue
            if officer.role == "chairperson":
                officer.meeting_id.chairperson_id = officer.member_id
            elif officer.role == "secretary":
                officer.meeting_id.secretary_id = officer.member_id

    def _sync_meeting_responsibles(self):
        for meeting in self.mapped("meeting_id"):
            if meeting.committee_mode != "special":
                continue
            officers = meeting.special_officer_ids
            chairperson = officers.filtered(
                lambda officer: officer.role == "chairperson"
            )[:1].member_id
            secretary = officers.filtered(
                lambda officer: officer.role == "secretary"
            )[:1].member_id
            meeting.write({
                "chairperson_id": chairperson.id,
                "secretary_id": secretary.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        officers = super().create(vals_list)
        officers._sync_meeting_responsibles()
        return officers

    def write(self, vals):
        result = super().write(vals)
        if {"member_id", "role", "meeting_id"}.intersection(vals):
            self._sync_meeting_responsibles()
        return result

    def unlink(self):
        meetings = self.mapped("meeting_id")
        result = super().unlink()
        for meeting in meetings:
            if meeting.committee_mode != "special":
                continue
            officers = meeting.special_officer_ids
            chairperson = officers.filtered(
                lambda officer: officer.role == "chairperson"
            )[:1].member_id
            secretary = officers.filtered(
                lambda officer: officer.role == "secretary"
            )[:1].member_id
            meeting.write({
                "chairperson_id": chairperson.id,
                "secretary_id": secretary.id,
            })
        return result

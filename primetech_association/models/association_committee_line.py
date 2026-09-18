# -*- coding: utf-8 -*-

##############################################################################
#
#    PrimeTech Association Management
#    Copyright (C) 2026 PrimeTech Services
#
#    Author: PrimeTech Services
#    License LGPL-3
#
##############################################################################

from odoo import api, fields, models


class AssociationCommitteeLine(models.Model):
    _name = "association.committee.line"
    _description = "Membre du Bureau Exécutif"
    _order = "sequence, id"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    # ==========================================================
    # BUREAU EXÉCUTIF
    # ==========================================================

    committee_id = fields.Many2one(
        comodel_name="association.committee",
        string="Bureau Exécutif",
        required=True,
        ondelete="cascade",
        index=True,
    )

    company_id = fields.Many2one(
        related="committee_id.company_id",
        string="Filiale",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        ondelete="restrict",
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        store=True,
        readonly=True,
    )

    image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo du membre",
        readonly=True,
    )

    category_id = fields.Many2one(
        related="member_id.category_id",
        string="Catégorie",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # FONCTION
    # ==========================================================

    function_id = fields.Many2one(
        comodel_name="association.member.function",
        string="Fonction",
        required=True,
        ondelete="restrict",
        index=True,
    )

    # ==========================================================
    # HABILITATIONS
    # ==========================================================

    is_signatory = fields.Boolean(
        string="Signataire autorisé",
        default=False,
    )

    is_financial = fields.Boolean(
        string="Responsable financier",
        default=False,
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Char(
        string="Observation",
    )

    # ==========================================================
    # ONCHANGE
    # ==========================================================

    @api.onchange("member_id")
    def _onchange_member_id(self):
        for rec in self:
            if (
                rec.member_id
                and rec.member_id.function_id
                and not rec.function_id
            ):
                rec.function_id = rec.member_id.function_id

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.mapped("committee_id")._sync_committee_mandates(
            members=lines.mapped("member_id")
        )
        return lines

    def write(self, vals):
        members = self.mapped("member_id")
        committees = self.mapped("committee_id")
        result = super().write(vals)
        members |= self.mapped("member_id")
        committees |= self.mapped("committee_id")
        committees._sync_committee_mandates(members=members)
        return result

    def unlink(self):
        members = self.mapped("member_id")
        committees = self.mapped("committee_id")
        result = super().unlink()
        committees._sync_committee_mandates(members=members)
        return result

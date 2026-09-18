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

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AssociationMemberFunction(models.Model):
    _name = "association.member.function"
    _description = "Fonction de membre"
    _order = "sequence, name, id"
    _rec_name = "name"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="cascade",
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Fonction",
        required=True,
        index=True,
        translate=True,
    )

    # ==========================================================
    # MEMBRES
    # ==========================================================

    member_ids = fields.One2many(
        comodel_name="association.member",
        inverse_name="function_id",
        string="Membres",
        readonly=True,
    )

    member_count = fields.Integer(
        string="Nombre de membres",
        compute="_compute_member_count",
    )

    # ==========================================================
    # CALCULS
    # ==========================================================

    @api.depends("member_ids")
    def _compute_member_count(self):

        for function in self:

            function.member_count = len(
                function.member_ids
            )

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "name",
        "company_id",
    )
    def _check_unique_name(self):

        for function in self:

            if not function.name:
                continue

            domain = [
                (
                    "name",
                    "=ilike",
                    function.name.strip(),
                ),
                (
                    "company_id",
                    "=",
                    function.company_id.id,
                ),
                (
                    "id",
                    "!=",
                    function.id,
                ),
            ]

            existing_function = self.search(
                domain,
                limit=1,
            )

            if existing_function:

                raise ValidationError(
                    _(
                        "La fonction '%(function)s' existe "
                        "déjà pour la filiale '%(company)s'."
                    )
                    % {
                        "function": function.name,
                        "company": function.company_id.display_name,
                    }
                )

    # ==========================================================
    # CRUD
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            if vals.get("name"):
                vals["name"] = vals["name"].strip()

        return super().create(vals_list)

    def write(self, vals):

        if vals.get("name"):
            vals["name"] = vals["name"].strip()

        return super().write(vals)

    # ==========================================================
    # ACTIONS
    # ==========================================================

    def action_view_members(self):

        self.ensure_one()

        action = self.env[
            "ir.actions.actions"
        ]._for_xml_id(
            "primetech_association.action_association_member"
        )

        action["domain"] = [
            (
                "function_id",
                "=",
                self.id,
            )
        ]

        action["context"] = {
            "default_function_id": self.id,
            "default_company_id": self.company_id.id,
        }

        return action
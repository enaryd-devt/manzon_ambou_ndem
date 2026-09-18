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


class AssociationMemberCategory(models.Model):
    _name = "association.member.category"
    _description = "Catégorie de membre"
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
        string="Catégorie",
        required=True,
        index=True,
        translate=True,
    )

    # ==========================================================
    # MEMBRES
    # ==========================================================

    member_ids = fields.One2many(
        comodel_name="association.member",
        inverse_name="category_id",
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
        for category in self:
            category.member_count = len(category.member_ids)

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "name",
        "company_id",
    )
    def _check_unique_name(self):

        for category in self:

            if not category.name:
                continue

            domain = [
                (
                    "name",
                    "=ilike",
                    category.name.strip(),
                ),
                (
                    "company_id",
                    "=",
                    category.company_id.id,
                ),
                (
                    "id",
                    "!=",
                    category.id,
                ),
            ]

            existing_category = self.search(
                domain,
                limit=1,
            )

            if existing_category:

                raise ValidationError(
                    _(
                        "La catégorie '%(category)s' existe "
                        "déjà pour la filiale '%(company)s'."
                    )
                    % {
                        "category": category.name,
                        "company": category.company_id.display_name,
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
                "category_id",
                "=",
                self.id,
            )
        ]

        action["context"] = {
            "default_category_id": self.id,
            "default_company_id": self.company_id.id,
        }

        return action
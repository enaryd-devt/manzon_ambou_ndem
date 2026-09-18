# -*- coding: utf-8 -*-
##############################################################################
#
# PrimeTech Association Management
# Copyright (C) 2026 PrimeTech Services
#
# Licence LGPL-3
#
##############################################################################

from odoo import fields, models


class AssociationSkill(models.Model):
    _name = "association.skill"
    _description = "Compétence"
    _order = "sequence, name"

    # ==========================================================
    # INFORMATIONS GÉNÉRALES
    # ==========================================================

    name = fields.Char(
        string="Nom de la compétence",
        required=True,
        index=True,
    )

    code = fields.Char(
        string="Code",
        index=True,
    )

    description = fields.Text(
        string="Description",
    )

    # ==========================================================
    # PARAMÈTRES
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
    )

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    color = fields.Integer(
        string="Couleur",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Société",
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )

    # ==========================================================
    # MEMBRES
    # ==========================================================

    member_ids = fields.Many2many(
        "association.member",
        string="Membres",
    )

    member_count = fields.Integer(
        string="Nombre de membres",
        compute="_compute_member_count",
    )

    # ==========================================================
    # CALCULS
    # ==========================================================

    def _compute_member_count(self):
        for competence in self:
            competence.member_count = len(competence.member_ids)
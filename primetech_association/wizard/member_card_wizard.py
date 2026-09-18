# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationCardGenerationWizard(models.TransientModel):
    _name = "association.card.generation.wizard"
    _description = "Assistant de génération des cartes de membre"

    generation_scope = fields.Selection(
        selection=[
            ("selected", "Membres sélectionnés"),
            ("all_active", "Tous les membres actifs de la filiale"),
        ],
        string="Membres à traiter",
        default="selected",
        required=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        required=True,
        default=lambda self: self.env.company,
    )

    member_ids = fields.Many2many(
        comodel_name="association.member",
        string="Membres",
    )

    issue_date = fields.Date(
        string="Date d'émission",
        required=True,
        default=fields.Date.context_today,
    )

    validity_months = fields.Integer(
        string="Validité en mois",
        required=True,
        default=lambda self: self._default_validity_months(),
    )

    existing_card_policy = fields.Selection(
        selection=[
            ("skip", "Ignorer les membres ayant déjà une carte active"),
            ("replace", "Annuler la carte active et générer une nouvelle"),
        ],
        string="Si une carte active existe",
        default="skip",
        required=True,
    )

    activate_cards = fields.Boolean(
        string="Activer les cartes générées",
        default=True,
    )

    print_cards = fields.Boolean(
        string="Imprimer après génération",
        default=True,
    )

    note = fields.Text(
        string="Note interne",
        help="Note ajoutée aux cartes générées.",
    )

    @api.model
    def _default_validity_months(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "primetech_association.membership_card_validity",
                default="12",
            )
        )

        try:
            return max(int(value or 12), 1)
        except (TypeError, ValueError):
            return 12

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)

        if self.env.context.get("active_model") == "association.card":
            cards = self.env["association.card"].browse(
                self.env.context.get("active_ids", [])
            )
            members = cards.mapped("member_id")

            if members:
                values["generation_scope"] = "selected"
                values["member_ids"] = [(6, 0, members.ids)]

        return values

    @api.constrains("validity_months")
    def _check_validity_months(self):
        for wizard in self:
            if wizard.validity_months <= 0:
                raise ValidationError(
                    _("La durée de validité doit être supérieure à zéro.")
                )

    def _get_target_members(self):
        self.ensure_one()

        Member = self.env["association.member"]

        if self.generation_scope == "all_active":
            return Member.search(
                [
                    ("company_id", "=", self.company_id.id),
                    ("state", "=", "active"),
                ],
                order="name,id",
            )

        return self.member_ids.filtered(
            lambda member:
                member.company_id == self.company_id
                and member.state == "active"
        )

    def _get_report_action(self):
        return self.env.ref(
            "primetech_association.action_report_member_card",
            raise_if_not_found=False,
        )

    def action_generate_cards(self):
        self.ensure_one()

        members = self._get_target_members()

        if not members:
            raise UserError(
                _(
                    "Aucun membre actif n'a été sélectionné "
                    "pour la génération des cartes."
                )
            )

        Card = self.env["association.card"]
        generated_cards = Card
        skipped_members = self.env["association.member"]

        for member in members:
            active_cards = Card.search(
                [
                    ("member_id", "=", member.id),
                    ("company_id", "=", self.company_id.id),
                    ("state", "=", "active"),
                ]
            )

            if active_cards and self.existing_card_policy == "skip":
                skipped_members |= member
                continue

            if active_cards and self.existing_card_policy == "replace":
                active_cards.filtered(
                    lambda card: not card.cancellation_reason
                ).write(
                    {
                        "cancellation_reason":
                            _(
                                "Carte annulée automatiquement lors "
                                "d'une nouvelle génération."
                            ),
                    }
                )
                active_cards.action_cancel()

            generated_cards |= Card.create(
                {
                    "member_id": member.id,
                    "company_id": self.company_id.id,
                    "issue_date": self.issue_date,
                    "validity_months": self.validity_months,
                    "note": self.note or False,
                }
            )

        if not generated_cards:
            raise UserError(
                _(
                    "Aucune carte n'a été générée.\n\n"
                    "%s membre(s) possèdent déjà une carte active."
                )
                % len(skipped_members)
            )

        if self.activate_cards:
            generated_cards.action_issue()

        if self.print_cards:
            report_action = self._get_report_action()

            if not report_action:
                raise UserError(
                    _(
                        "Le rapport de carte membre n'est pas disponible. "
                        "Vérifiez la configuration du rapport."
                    )
                )

            return report_action.report_action(generated_cards)

        return {
            "type": "ir.actions.act_window",
            "name": _("Cartes générées"),
            "res_model": "association.card",
            "view_mode": "list,form",
            "domain": [("id", "in", generated_cards.ids)],
            "target": "current",
        }

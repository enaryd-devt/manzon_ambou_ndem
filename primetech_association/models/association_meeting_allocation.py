# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class AssociationSubscriptionAllocation(models.Model):
    _name = "association.subscription.allocation"
    _description = "Attribution de cagnotte de cotisation"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
    ]
    _order = "allocation_date desc, id desc"

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Référence",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nouveau"),
        tracking=True,
    )

    # ==========================================================
    # CYCLE / COTISATION
    # ==========================================================

    period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle de cotisation",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        related="period_id.subscription_id",
        store=True,
        readonly=True,
        index=True,
    )

    # ==========================================================
    # RÉUNION D'ORIGINE
    # ==========================================================

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion d'attribution",
        tracking=True,
        ondelete="restrict",
        index=True,
    )

    meeting_subscription_session_id = fields.Many2one(
        comodel_name="association.meeting.subscription.session",
        string="Session de cotisation",
        ondelete="restrict",
        index=True,
        readonly=True,
        copy=False,
    )

    # ==========================================================
    # BÉNÉFICIAIRE
    # ==========================================================

    beneficiary_id = fields.Many2one(
        comodel_name="association.member",
        string="Bénéficiaire",
        required=True,
        tracking=True,
        index=True,
    )

    beneficiary_image_128 = fields.Image(
        string="Photo",
        related="beneficiary_id.image_128",
        readonly=True,
    )

    # ==========================================================
    # SOCIÉTÉ / DEVISE
    # ==========================================================

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="period_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="period_id.currency_id",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # ATTRIBUTION
    # ==========================================================

    amount = fields.Monetary(
        string="Montant attribué",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )

    allocation_date = fields.Datetime(
        string="Date d'attribution",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
        index=True,
    )

    allocation_method = fields.Selection(
        selection=[
            ("rotation", "Rotation"),
            ("planned", "Ordre planifié"),
            ("meeting_decision", "Décision de la réunion"),
            ("draw", "Tirage au sort"),
            ("priority", "Besoin prioritaire"),
            ("other", "Autre"),
        ],
        string="Mode d'attribution",
        required=True,
        default="meeting_decision",
        tracking=True,
    )

    decision_note = fields.Text(
        string="Décision / Observation",
        tracking=True,
    )

    # ==========================================================
    # ÉTAT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("confirmed", "Confirmée"),
            ("paid", "Remise effectuée"),
            ("cancelled", "Annulée"),
        ],
        string="Statut",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:

            if vals.get(
                "name",
                _("Nouveau"),
            ) == _("Nouveau"):

                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.subscription.allocation"
                    )
                    or _("Nouveau")
                )

        records = super().create(vals_list)

        for record in records:

            if record.meeting_id:

                record.message_post(
                    body=_(
                        "Attribution créée depuis la réunion "
                        "%(meeting)s pour le bénéficiaire "
                        "%(beneficiary)s."
                    )
                    % {
                        "meeting":
                            record.meeting_id.display_name,
                        "beneficiary":
                            record.beneficiary_id.display_name,
                    }
                )

        return records

    # ==========================================================
    # CONTRÔLE DU MONTANT
    # ==========================================================

    @api.constrains("amount")
    def _check_amount(self):

        for record in self:

            if record.amount <= 0:

                raise ValidationError(
                    _(
                        "Le montant attribué doit être "
                        "strictement supérieur à zéro."
                    )
                )

    # ==========================================================
    # CONTRÔLE DU BÉNÉFICIAIRE
    # ==========================================================

    @api.constrains(
        "beneficiary_id",
        "period_id",
    )
    def _check_beneficiary(self):

        for record in self:

            if (
                not record.beneficiary_id
                or not record.period_id
            ):
                continue

            subscription = (
                record.period_id.subscription_id
            )

            if not subscription:
                continue

            subscription_line = self.env[
                "association.subscription.line"
            ].search(
                [
                    (
                        "subscription_id",
                        "=",
                        subscription.id,
                    ),
                    (
                        "member_id",
                        "=",
                        record.beneficiary_id.id,
                    ),
                ],
                limit=1,
            )

            if not subscription_line:

                raise ValidationError(
                    _(
                        "Le membre %(member)s ne participe pas "
                        "à la cotisation %(subscription)s."
                    )
                    % {
                        "member":
                            record
                            .beneficiary_id
                            .display_name,
                        "subscription":
                            subscription.display_name,
                    }
                )
    
    # ==========================================================
    # CONTRÔLE RÉUNION / CYCLE
    # ==========================================================

    @api.constrains(
        "meeting_id",
        "period_id",
    )
    def _check_meeting_period(self):

        for record in self:

            if (
                not record.meeting_id
                or not record.period_id
            ):
                continue

            meeting_period = (
                record.meeting_id.subscription_period_id
            )

            if (
                meeting_period
                and meeting_period != record.period_id
            ):

                raise ValidationError(
                    _(
                        "Le cycle de l'attribution ne correspond "
                        "pas au cycle de cotisation chargé dans "
                        "la réunion."
                    )
                )

    # ==========================================================
    # CONFIRMER
    # ==========================================================

    def action_confirm(self):

        for record in self:

            if record.state != "draft":
                continue

            if not record.period_id:

                raise UserError(
                    _(
                        "Aucun cycle de cotisation n'est associé "
                        "à cette attribution."
                    )
                )

            available_amount = (
                record.period_id.available_amount or 0.0
            )

            if record.amount > available_amount:

                raise ValidationError(
                    _(
                        "La cagnotte disponible est insuffisante."
                        "\n\n"
                        "Disponible : %(available)s"
                        "\n"
                        "Montant demandé : %(amount)s"
                    )
                    % {
                        "available": available_amount,
                        "amount": record.amount,
                    }
                )

            record.write(
                {
                    "state": "confirmed",
                }
            )

            record.message_post(
                body=_(
                    "Attribution de %(amount)s confirmée "
                    "pour %(beneficiary)s."
                )
                % {
                    "amount": record.amount,
                    "beneficiary":
                        record.beneficiary_id.display_name,
                }
            )

        return True

    # ==========================================================
    # REMISE AU BÉNÉFICIAIRE
    # ==========================================================

    def action_mark_paid(self):

        for record in self:

            if record.state != "confirmed":

                raise ValidationError(
                    _(
                        "L'attribution doit être confirmée "
                        "avant la remise au bénéficiaire."
                    )
                )

            record.write(
                {
                    "state": "paid",
                }
            )

            record.message_post(
                body=_(
                    "La cagnotte de %(amount)s a été remise "
                    "à %(beneficiary)s."
                )
                % {
                    "amount": record.amount,
                    "beneficiary":
                        record.beneficiary_id.display_name,
                }
            )

        return True

    # ==========================================================
    # ANNULER
    # ==========================================================

    def action_cancel(self):

        for record in self:

            if record.state == "paid":

                raise ValidationError(
                    _(
                        "Une cagnotte déjà remise ne peut "
                        "pas être annulée directement."
                    )
                )

            if record.state == "cancelled":
                continue

            record.write(
                {
                    "state": "cancelled",
                }
            )

            record.message_post(
                body=_(
                    "L'attribution de cagnotte a été annulée."
                )
            )

        return True

    # ==========================================================
    # REMETTRE EN BROUILLON
    # ==========================================================

    def action_reset_draft(self):

        for record in self:

            if record.state != "cancelled":

                raise ValidationError(
                    _(
                        "Seule une attribution annulée peut être "
                        "remise en brouillon."
                    )
                )

            record.write(
                {
                    "state": "draft",
                }
            )

        return True

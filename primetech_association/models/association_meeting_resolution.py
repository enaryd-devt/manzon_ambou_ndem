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
from odoo.exceptions import ValidationError, UserError


class AssociationMeetingResolution(models.Model):
    _name = "association.meeting.resolution"
    _description = "Résolution de réunion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "meeting_id, sequence, id"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
        tracking=True,
    )

    sequence = fields.Integer(
        string="Séquence",
        default=10,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        related="meeting_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    # ==========================================================
    # RÉUNION
    # ==========================================================

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
    )

    meeting_state = fields.Selection(
        related="meeting_id.state",
        string="Statut de la réunion",
        readonly=True,
        store=True,
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Titre de la résolution",
        required=True,
        tracking=True,
    )

    description = fields.Html(
        string="Texte de la résolution",
        required=True,
        tracking=True,
    )

    resolution_type = fields.Selection(
        selection=[
            ("decision", "Décision"),
            ("recommendation", "Recommandation"),
            ("authorization", "Autorisation"),
            ("financial", "Décision financière"),
            ("disciplinary", "Décision disciplinaire"),
            ("election", "Élection / Nomination"),
            ("amendment", "Modification des statuts"),
            ("other", "Autre"),
        ],
        string="Type de résolution",
        required=True,
        default="decision",
        tracking=True,
        index=True,
    )

    # ==========================================================
    # MODE DE DÉCISION
    # ==========================================================

    decision_method = fields.Selection(
        selection=[
            ("consensus", "Consensus"),
            ("show_of_hands", "Vote à main levée"),
            ("secret_ballot", "Vote à bulletin secret"),
            ("voice_vote", "Vote oral"),
            ("other", "Autre"),
        ],
        string="Mode de décision",
        required=True,
        default="show_of_hands",
        tracking=True,
    )

    majority_type = fields.Selection(
        selection=[
            ("simple", "Majorité simple"),
            ("absolute", "Majorité absolue"),
            ("two_thirds", "Majorité des deux tiers"),
            ("three_quarters", "Majorité des trois quarts"),
            ("unanimity", "Unanimité"),
            ("custom", "Majorité personnalisée"),
        ],
        string="Majorité requise",
        required=True,
        default="simple",
        tracking=True,
    )

    custom_majority_percentage = fields.Float(
        string="Majorité personnalisée (%)",
        default=50.0,
        tracking=True,
    )

    required_percentage = fields.Float(
        string="Pourcentage requis (%)",
        compute="_compute_required_percentage",
    )

    # ==========================================================
    # VOTES
    # ==========================================================

    votes_for = fields.Integer(
        string="Voix pour",
        default=0,
        tracking=True,
    )

    votes_against = fields.Integer(
        string="Voix contre",
        default=0,
        tracking=True,
    )

    abstentions = fields.Integer(
        string="Abstentions",
        default=0,
        tracking=True,
    )

    blank_votes = fields.Integer(
        string="Votes blancs / nuls",
        default=0,
        tracking=True,
    )

    total_votes = fields.Integer(
        string="Total des votes",
        compute="_compute_vote_statistics",
    )

    valid_votes = fields.Integer(
        string="Suffrages exprimés",
        compute="_compute_vote_statistics",
    )

    approval_percentage = fields.Float(
        string="Taux d'approbation (%)",
        compute="_compute_vote_statistics",
    )

    # ==========================================================
    # RÉSULTAT
    # ==========================================================

    result = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("adopted", "Adoptée"),
            ("rejected", "Rejetée"),
        ],
        string="Résultat",
        compute="_compute_result",
        store=True,
        tracking=True,
    )

    decision_date = fields.Date(
        string="Date de décision",
        readonly=True,
        tracking=True,
    )

    # ==========================================================
    # EXÉCUTION
    # ==========================================================

    responsible_id = fields.Many2one(
        comodel_name="association.member",
        string="Responsable de l'exécution",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    deadline = fields.Date(
        string="Échéance",
        tracking=True,
    )

    execution_state = fields.Selection(
        selection=[
            ("not_started", "Non commencée"),
            ("in_progress", "En cours"),
            ("done", "Réalisée"),
            ("cancelled", "Annulée"),
        ],
        string="État d'exécution",
        required=True,
        default="not_started",
        tracking=True,
    )

    execution_note = fields.Html(
        string="Compte rendu d'exécution",
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # CALCUL DU POURCENTAGE REQUIS
    # ==========================================================

    @api.depends(
        "majority_type",
        "custom_majority_percentage",
    )
    def _compute_required_percentage(self):

        percentages = {
            "simple": 50.0,
            "absolute": 50.0,
            "two_thirds": 66.6667,
            "three_quarters": 75.0,
            "unanimity": 100.0,
        }

        for record in self:

            if record.majority_type == "custom":

                record.required_percentage = (
                    record.custom_majority_percentage
                )

            else:

                record.required_percentage = percentages.get(
                    record.majority_type,
                    50.0,
                )

    # ==========================================================
    # STATISTIQUES DES VOTES
    # ==========================================================

    @api.depends(
        "votes_for",
        "votes_against",
        "abstentions",
        "blank_votes",
    )
    def _compute_vote_statistics(self):

        for record in self:

            record.total_votes = (
                record.votes_for
                + record.votes_against
                + record.abstentions
                + record.blank_votes
            )

            record.valid_votes = (
                record.votes_for
                + record.votes_against
            )

            if record.valid_votes:

                record.approval_percentage = (
                    record.votes_for
                    / record.valid_votes
                ) * 100

            else:

                record.approval_percentage = 0.0

    # ==========================================================
    # RÉSULTAT DE LA RÉSOLUTION
    # ==========================================================

    @api.depends(
        "decision_method",
        "votes_for",
        "votes_against",
        "abstentions",
        "blank_votes",
        "approval_percentage",
        "required_percentage",
        "majority_type",
    )
    def _compute_result(self):

        for record in self:

            if record.decision_method == "consensus":

                record.result = "pending"

                continue

            if record.total_votes <= 0:

                record.result = "pending"

                continue

            if record.majority_type == "simple":

                record.result = (
                    "adopted"
                    if record.votes_for > record.votes_against
                    else "rejected"
                )

            elif record.majority_type == "unanimity":

                record.result = (
                    "adopted"
                    if (
                        record.votes_for > 0
                        and record.votes_against == 0
                    )
                    else "rejected"
                )

            else:

                record.result = (
                    "adopted"
                    if (
                        record.approval_percentage
                        >= record.required_percentage
                    )
                    else "rejected"
                )

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "votes_for",
        "votes_against",
        "abstentions",
        "blank_votes",
    )
    def _check_vote_values(self):

        for record in self:

            if (
                record.votes_for < 0
                or record.votes_against < 0
                or record.abstentions < 0
                or record.blank_votes < 0
            ):

                raise ValidationError(
                    _(
                        "Le nombre de voix ne peut pas être négatif."
                    )
                )

    @api.constrains("custom_majority_percentage")
    def _check_custom_majority_percentage(self):

        for record in self:

            if (
                record.majority_type == "custom"
                and not (
                    0
                    < record.custom_majority_percentage
                    <= 100
                )
            ):

                raise ValidationError(
                    _(
                        "La majorité personnalisée doit être "
                        "supérieure à 0 et inférieure ou égale à 100."
                    )
                )

    @api.constrains(
        "responsible_id",
        "company_id",
    )
    def _check_responsible_company(self):

        for record in self:

            if (
                record.responsible_id
                and record.responsible_id.company_id
                != record.company_id
            ):

                raise ValidationError(
                    _(
                        "Le responsable de l'exécution et la résolution "
                        "doivent appartenir à la même Filiale."
                    )
                )

    @api.constrains(
        "votes_for",
        "votes_against",
        "abstentions",
        "blank_votes",
        "meeting_id",
    )
    def _check_total_votes(self):

        for record in self:

            if not record.meeting_id:
                continue

            eligible_voters = (
                record.meeting_id.present_count
                + record.meeting_id.late_count
            )

            if (
                eligible_voters
                and record.total_votes > eligible_voters
            ):

                raise ValidationError(
                    _(
                        "Le nombre total de votes (%(votes)s) "
                        "ne peut pas dépasser le nombre de membres "
                        "présents ou retardataires (%(members)s)."
                    )
                    % {
                        "votes": record.total_votes,
                        "members": eligible_voters,
                    }
                )

    # ==========================================================
    # MARQUER COMME RÉALISÉE
    # ==========================================================

    def action_mark_done(self):

        for record in self:

            if record.result != "adopted":

                raise UserError(
                    _(
                        "Seule une résolution adoptée "
                        "peut être marquée comme réalisée."
                    )
                )

            record.execution_state = "done"

        return True

    # ==========================================================
    # PROTECTION DES VOTES
    # ==========================================================

    def write(self, vals):

        vote_fields = {
            "votes_for",
            "votes_against",
            "abstentions",
            "blank_votes",
            "decision_method",
            "majority_type",
            "custom_majority_percentage",
        }

        if vote_fields.intersection(vals):

            for record in self:

                if record.meeting_state == "closed":

                    raise UserError(
                        _(
                            "Les votes d'une réunion clôturée "
                            "ne peuvent plus être modifiés."
                        )
                    )

        return super().write(vals)

    # ==========================================================
    # PROTECTION SUPPRESSION
    # ==========================================================

    def unlink(self):

        for record in self:

            if record.meeting_state == "closed":

                raise UserError(
                    _(
                        "Une résolution d'une réunion clôturée "
                        "ne peut pas être supprimée."
                    )
                )

        return super().unlink()
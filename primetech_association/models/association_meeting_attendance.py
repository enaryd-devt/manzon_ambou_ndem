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


class AssociationAttendance(models.Model):
    _name = "association.attendance"
    _description = "Présence à une réunion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "meeting_id desc, sequence, member_id, id"

    # ==========================================================
    # OUTILS HORAIRES
    # ==========================================================

    @api.model
    def _get_hour_selection(self):
        """Liste d'heures de 00:00 à 23:55 par pas de 5 minutes."""
        return [
            (f"{hour:02d}:{minute:02d}", f"{hour:02d}:{minute:02d}")
            for hour in range(24)
            for minute in range(0, 60, 5)
        ]

    @staticmethod
    def _time_to_minutes(value):
        """Convertit HH:MM en minutes et tolère une ancienne valeur Float."""
        if value in (False, None, ""):
            return None

        if isinstance(value, (int, float)):
            return int(round(float(value) * 60))

        try:
            hour, minute = str(value).split(":", 1)
            return int(hour) * 60 + int(minute)
        except (ValueError, TypeError, AttributeError):
            return None

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
        readonly=True,
        store=True,
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
        tracking=True,
        index=True,
    )

    meeting_state = fields.Selection(
        related="meeting_id.state",
        string="Statut de la réunion",
        readonly=True,
        store=True,
    )

    meeting_date = fields.Date(
        related="meeting_id.meeting_date",
        string="Date de réunion",
        readonly=True,
        store=True,
    )

    meeting_type = fields.Selection(
        related="meeting_id.meeting_type",
        string="Type de réunion",
        readonly=True,
        store=True,
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        ondelete="restrict",
        tracking=True,
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        readonly=True,
        store=True,
    )

    image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo",
        readonly=True,
    )

    category_id = fields.Many2one(
        related="member_id.category_id",
        string="Catégorie",
        readonly=True,
        store=True,
    )

    function_id = fields.Many2one(
        related="member_id.function_id",
        string="Fonction",
        readonly=True,
        store=True,
    )

    phone = fields.Char(
        related="member_id.phone",
        string="Téléphone",
        readonly=True,
    )

    # ==========================================================
    # CONVOCATION
    # ==========================================================

    invited = fields.Boolean(
        string="Convoqué",
        default=True,
        tracking=True,
    )

    convocation_confirmed = fields.Boolean(
        string="Convocation confirmée",
        default=False,
        tracking=True,
    )

    confirmation_date = fields.Datetime(
        string="Date de confirmation",
        readonly=True,
        tracking=True,
    )

    # ==========================================================
    # PRÉSENCE
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("present", "Présent"),
            ("late", "En retard"),
            ("absent", "Absent"),
        ],
        string="État de présence",
        required=True,
        default="pending",
        tracking=True,
        index=True,
    )

    arrival_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure d'arrivée",
        tracking=True,
    )

    departure_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure de départ",
        tracking=True,
    )



    early_departure = fields.Boolean(
        string="Départ anticipé",
        compute="_compute_early_departure",
        store=True,
    )

    # ==========================================================
    # ABSENCE
    # ==========================================================

    absence_reason = fields.Text(
        string="Motif d'absence",
        tracking=True,
    )

    justification = fields.Binary(
        string="Justificatif d'absence",
        attachment=True,
    )

    justification_filename = fields.Char(
        string="Nom du justificatif",
    )

    absence_validated = fields.Boolean(
        string="Justification validée",
        default=False,
        tracking=True,
    )

    absence_validated_by = fields.Many2one(
        comodel_name="res.users",
        string="Justification validée par",
        readonly=True,
    )

    absence_validation_date = fields.Datetime(
        string="Date de validation",
        readonly=True,
    )

    # ==========================================================
    # SIGNATURE / VALIDATION
    # ==========================================================

    presence_confirmed = fields.Boolean(
        string="Présence confirmée",
        default=False,
        tracking=True,
    )

    presence_confirmed_by = fields.Many2one(
        comodel_name="res.users",
        string="Présence confirmée par",
        readonly=True,
    )

    presence_confirmation_date = fields.Datetime(
        string="Date de confirmation de présence",
        readonly=True,
    )

    signature = fields.Binary(
        string="Signature",
        attachment=True,
    )

    # ==========================================================
    # DROIT DE VOTE
    # ==========================================================

    voting_eligible = fields.Boolean(
        string="Droit de vote",
        default=True,
        tracking=True,
    )

    voting_block_reason = fields.Char(
        string="Motif de suspension du vote",
        tracking=True,
    )

    # ==========================================================
    # SANCTION
    # ==========================================================

    penalty_required = fields.Boolean(
        string="Sanction à prévoir",
        default=False,
        tracking=True,
    )

    penalty_reason = fields.Char(
        string="Motif de sanction",
        tracking=True,
    )
    automatic_penalty_ids = fields.One2many(
        "association.penalty", "attendance_id", string="Sanctions automatiques", readonly=True,
    )

    def _apply_automatic_discipline(self):
        """Apply the association's configurable disciplinary grid once per attendance."""
        Penalty = self.env["association.penalty"]
        params = self.env["ir.config_parameter"].sudo()
        late_amount = float(params.get_param("primetech_association.late_penalty_amount", 0.0) or 0.0)
        absence_base = float(params.get_param("primetech_association.consecutive_absence_penalty_amount", 0.0) or 0.0)
        for attendance in self:
            if attendance.is_excused or attendance.state not in ("late", "absent"):
                automatic_penalties = attendance.automatic_penalty_ids.filtered(
                    lambda penalty: penalty.state not in ("cancelled", "lifted")
                )
                if automatic_penalties:
                    automatic_penalties.action_cancel()
                    attendance.penalty_required = False
                    attendance.penalty_reason = False
                continue
            existing = Penalty.search_count([
                ("attendance_id", "=", attendance.id), ("state", "!=", "cancelled"),
            ])
            if existing:
                continue
            values = {
                "meeting_id": attendance.meeting_id.id,
                "member_id": attendance.member_id.id,
                "attendance_id": attendance.id,
                "automatic": True,
                "incident_date": fields.Datetime.now(),
                "state": "validated",
                "validated_by": self.env.user.id,
                "validation_date": fields.Datetime.now(),
            }
            if attendance.state == "late":
                if late_amount <= 0:
                    continue
                values.update({
                    "incident_type": "late", "penalty_type": "fine", "amount": late_amount,
                    "incident_description": _("Retard à la réunion du %s.") % attendance.meeting_date,
                    "penalty_description": _("Sanction automatique pour retard."),
                })
            else:
                previous = self.search([
                    ("member_id", "=", attendance.member_id.id),
                    ("state", "=", "absent"), ("is_excused", "=", False),
                    ("meeting_date", "<", attendance.meeting_date),
                ], order="meeting_date desc, id desc")
                consecutive = 1
                expected_date = attendance.meeting_date
                for line in previous:
                    # Every recorded absence immediately before this one counts;
                    # a present/late attendance breaks the consecutive sequence.
                    later = self.search_count([
                        ("member_id", "=", attendance.member_id.id),
                        ("meeting_date", ">", line.meeting_date),
                        ("meeting_date", "<", expected_date),
                        ("state", "in", ["present", "late"]),
                    ])
                    if later:
                        break
                    consecutive += 1
                    expected_date = line.meeting_date
                if consecutive == 1:
                    values.update({
                        "incident_type": "unjustified_absence", "penalty_type": "blame",
                        "incident_description": _("Absence non justifiée à la réunion du %s.") % attendance.meeting_date,
                        "penalty_description": _("Blâme automatique pour une première absence consécutive."),
                    })
                elif absence_base > 0:
                    values.update({
                        "incident_type": "unjustified_absence", "penalty_type": "fine",
                        "amount": absence_base * (consecutive - 1),
                        "incident_description": _("%s absences consécutives non justifiées.") % consecutive,
                        "penalty_description": _("Sanction automatique : %s × montant de base.") % (consecutive - 1),
                    })
                else:
                    continue
            Penalty.create(values)
            attendance.write({"penalty_required": True, "penalty_reason": values["penalty_description"]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._apply_automatic_discipline()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {"state", "is_excused", "meeting_id", "member_id"}.intersection(vals):
            self._apply_automatic_discipline()
        return result

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Observations",
    )

    # ==========================================================
    # POINTAGE RAPIDE
    # ==========================================================

    is_present = fields.Boolean(
        string="Présent",
        compute="_compute_attendance_checks",
        inverse="_inverse_is_present",
    )

    is_absent = fields.Boolean(
        string="Absent",
        compute="_compute_attendance_checks",
        inverse="_inverse_is_absent",
    )

    is_late = fields.Boolean(
        string="Retard",
        compute="_compute_attendance_checks",
        inverse="_inverse_is_late",
    )

    is_excused = fields.Boolean(
        string="Justifié",
        default=False,
        tracking=True,
    )

    late_minutes = fields.Integer(
        string="Minutes de retard",
        compute="_compute_late_duration",
        store=True,
    )

    late_duration = fields.Char(
        string="Durée du retard",
        compute="_compute_late_duration",
        store=True,
    )



    # ==========================================================
    # SYNCHRONISATION VISUELLE DU POINTAGE
    # ==========================================================

    @api.depends("state")
    def _compute_attendance_checks(self):

        for record in self:

            record.is_present = (
                record.state == "present"
            )

            record.is_absent = (
                record.state == "absent"
            )

            record.is_late = (
                record.state == "late"
            )


    # ==========================================================
    # PRÉSENT
    # ==========================================================

    def _inverse_is_present(self):

        for record in self:

            if record.is_present:

                record.state = "present"

                record.arrival_time = False
                record.departure_time = False

                record.is_excused = False
                record.absence_reason = False

            elif record.state == "present":

                record.state = "pending"


    # ==========================================================
    # ABSENT
    # ==========================================================

    def _inverse_is_absent(self):

        for record in self:

            if record.is_absent:

                record.state = "absent"

                record.arrival_time = False
                record.departure_time = False

            elif record.state == "absent":

                record.state = "pending"

                record.is_excused = False
                record.absence_reason = False


    # ==========================================================
    # RETARD
    # ==========================================================

    def _inverse_is_late(self):

        for record in self:

            if record.is_late:

                record.state = "late"

                record.arrival_time = False

            elif record.state == "late":

                record.state = "pending"

                record.arrival_time = False

                record.is_excused = False
                record.absence_reason = False


    # ==========================================================
    # ACTUALISATION DU POINTAGE
    # ==========================================================

    @api.onchange(
        "is_present",
        "is_absent",
        "is_late",
        "is_excused",
        "arrival_time",
        "absence_reason",
    )
    def _onchange_attendance_refresh(self):

        for record in self:

            # --------------------------------------------------
            # PRÉSENT
            # --------------------------------------------------

            if record.is_present:

                record.state = "present"

                record.arrival_time = False

                record.is_excused = False
                record.absence_reason = False

                continue

            # --------------------------------------------------
            # RETARD
            # --------------------------------------------------

            if record.is_late:

                record.state = "late"

                if record.arrival_time:

                    arrival = record._time_to_minutes(
                        record.arrival_time
                    )

                    start = record._time_to_minutes(
                        record.meeting_id.start_time
                    )

                    if (
                        arrival is not None
                        and start is not None
                    ):

                        record.late_minutes = max(
                            arrival - start,
                            0,
                        )

                continue

            # --------------------------------------------------
            # ABSENT
            # --------------------------------------------------

            if record.is_absent:

                record.state = "absent"

                record.arrival_time = False
                record.departure_time = False

                continue

            # --------------------------------------------------
            # EN ATTENTE
            # --------------------------------------------------

            record.state = "pending"

            record.arrival_time = False

            record.is_excused = False
            record.absence_reason = False


    # ==========================================================
    # JUSTIFICATION
    # ==========================================================

    @api.onchange("is_excused")
    def _onchange_is_excused(self):

        for record in self:

            if not record.is_excused:

                record.absence_reason = False
                return

            if record.state not in (
                "absent",
                "late",
            ):

                record.is_excused = False

                return


    # ==========================================================
    # HEURE D'ARRIVÉE
    # ==========================================================

    @api.onchange("arrival_time")
    def _onchange_arrival_time(self):

        for record in self:

            if record.state != "late":
                continue

            if not record.arrival_time:
                continue

            if not record.meeting_id:
                continue

            arrival = record._time_to_minutes(
                record.arrival_time
            )

            start = record._time_to_minutes(
                record.meeting_id.start_time
            )

            if (
                arrival is None
                or start is None
            ):
                continue

            record.late_minutes = max(
                arrival - start,
                0,
            )

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_attendance_meeting_member_unique",
            "unique(meeting_id, member_id)",
            "Un membre ne peut apparaître qu'une seule fois "
            "dans la liste de présence d'une réunion.",
        ),
    ]

    # ==========================================================
    # CALCUL DE LA DURÉE DU RETARD
    # ==========================================================

    @api.depends(
        "state",
        "arrival_time",
        "meeting_id.start_time",
    )
    def _compute_late_duration(self):

        for record in self:

            record.late_minutes = 0
            record.late_duration = False

            # --------------------------------------------------
            # UNIQUEMENT POUR UN RETARD
            # --------------------------------------------------

            if record.state != "late":
                continue

            if not record.arrival_time:
                continue

            if not record.meeting_id:
                continue

            # --------------------------------------------------
            # CONVERSION DES HEURES EN MINUTES
            # --------------------------------------------------

            arrival_minutes = record._time_to_minutes(
                record.arrival_time
            )

            start_minutes = record._time_to_minutes(
                record.meeting_id.start_time
            )

            if (
                arrival_minutes is None
                or start_minutes is None
            ):
                continue

            # --------------------------------------------------
            # CALCUL DU RETARD
            # --------------------------------------------------

            delay_minutes = max(
                arrival_minutes - start_minutes,
                0,
            )

            record.late_minutes = delay_minutes

            # --------------------------------------------------
            # AFFICHAGE LISIBLE
            # --------------------------------------------------

            hours = delay_minutes // 60
            minutes = delay_minutes % 60

            if hours and minutes:

                record.late_duration = _(
                    "%(hours)s h %(minutes)s min"
                ) % {
                    "hours": hours,
                    "minutes": minutes,
                }

            elif hours:

                record.late_duration = _(
                    "%(hours)s h"
                ) % {
                    "hours": hours,
                }

            else:

                record.late_duration = _(
                    "%(minutes)s min"
                ) % {
                    "minutes": minutes,
                }
                
    # ==========================================================
    # DÉPART ANTICIPÉ
    # ==========================================================

    @api.depends("departure_time", "meeting_id.end_time")
    def _compute_early_departure(self):
        for record in self:
            record.early_departure = False
            departure = record._time_to_minutes(record.departure_time)
            end = record._time_to_minutes(record.meeting_id.end_time)

            if departure is None or end is None:
                continue

            record.early_departure = departure < end

    # ==========================================================
    # ONCHANGE ÉTAT
    # ==========================================================

    @api.onchange("state")
    def _onchange_state(self):
        for record in self:
            if record.state in ("present", "late"):
                record.absence_reason = False
                record.absence_validated = False
                record.absence_validated_by = False
                record.absence_validation_date = False

            if record.state in ("absent", "excused", "pending"):
                record.arrival_time = False
                record.departure_time = False
                record.presence_confirmed = False
                record.presence_confirmed_by = False
                record.presence_confirmation_date = False

            if record.state != "excused":
                record.absence_validated = False
                record.absence_validated_by = False
                record.absence_validation_date = False

    # ==========================================================
    # ONCHANGE HEURE D'ARRIVÉE
    # ==========================================================

    @api.onchange("arrival_time")
    def _onchange_arrival_time(self):
        for record in self:
            if not record.arrival_time or not record.meeting_id:
                continue

            arrival = record._time_to_minutes(record.arrival_time)
            start = record._time_to_minutes(record.meeting_id.start_time)

            if arrival is None or start is None:
                continue

            record.state = "late" if arrival > start else "present"

    # ==========================================================
    # CONFIRMER LA CONVOCATION
    # ==========================================================

    def action_confirm_convocation(self):
        for record in self:

            record.write(
                {
                    "convocation_confirmed": True,
                    "confirmation_date": fields.Datetime.now(),
                }
            )

        return True

    # ==========================================================
    # MARQUER PRÉSENT
    # ==========================================================

    def action_mark_present(self):
        for record in self:

            if record.meeting_state not in (
                "convoked",
                "in_progress",
            ):
                raise UserError(
                    _(
                        "La présence ne peut être enregistrée "
                        "que pour une réunion convoquée ou en cours."
                    )
                )

            record.write(
                {
                    "state": "present",
                    "presence_confirmed": True,
                    "presence_confirmed_by": self.env.user.id,
                    "presence_confirmation_date": (
                        fields.Datetime.now()
                    ),
                }
            )

        return True

    # ==========================================================
    # MARQUER EN RETARD
    # ==========================================================

    def action_mark_late(self):
        for record in self:

            if record.meeting_state not in (
                "convoked",
                "in_progress",
            ):
                raise UserError(
                    _(
                        "Le retard ne peut être enregistré "
                        "que pour une réunion convoquée ou en cours."
                    )
                )

            record.write(
                {
                    "state": "late",
                    "presence_confirmed": True,
                    "presence_confirmed_by": self.env.user.id,
                    "presence_confirmation_date": (
                        fields.Datetime.now()
                    ),
                }
            )

        return True

    # ==========================================================
    # MARQUER ABSENT
    # ==========================================================

    def action_mark_absent(self):
        for record in self:

            record.write(
                {
                    "state": "absent",
                    "presence_confirmed": False,
                    "presence_confirmed_by": False,
                    "presence_confirmation_date": False,
                }
            )

        return True

    # ==========================================================
    # ABSENCE JUSTIFIÉE
    # ==========================================================

    def action_mark_excused(self):
        for record in self:

            if not record.absence_reason:
                raise UserError(
                    _(
                        "Vous devez renseigner le motif "
                        "de l'absence avant de la marquer "
                        "comme justifiée."
                    )
                )

            record.state = "excused"

        return True

    # ==========================================================
    # VALIDER LA JUSTIFICATION
    # ==========================================================

    def action_validate_absence(self):
        for record in self:

            if record.state != "excused":
                raise UserError(
                    _(
                        "Seule une absence justifiée "
                        "peut être validée."
                    )
                )

            if not record.absence_reason:
                raise UserError(
                    _(
                        "Le motif de l'absence est obligatoire."
                    )
                )

            record.write(
                {
                    "absence_validated": True,
                    "absence_validated_by": self.env.user.id,
                    "absence_validation_date": (
                        fields.Datetime.now()
                    ),
                }
            )

        return True

    # ==========================================================
    # CONFIRMER LA PRÉSENCE
    # ==========================================================

    def action_confirm_presence(self):
        for record in self:

            if record.state not in (
                "present",
                "late",
            ):
                raise UserError(
                    _(
                        "Seuls les membres présents ou retardataires "
                        "peuvent confirmer leur présence."
                    )
                )

            record.write(
                {
                    "presence_confirmed": True,
                    "presence_confirmed_by": self.env.user.id,
                    "presence_confirmation_date": (
                        fields.Datetime.now()
                    ),
                }
            )

        return True

    # ==========================================================
    # CONTRÔLE MEMBRE / FILIALE
    # ==========================================================

    @api.constrains(
        "member_id",
        "meeting_id",
    )
    def _check_member_company(self):
        for record in self:

            if (
                record.member_id
                and record.meeting_id
                and record.member_id.company_id
                != record.meeting_id.company_id
            ):
                raise ValidationError(
                    _(
                        "Le membre et la réunion doivent appartenir "
                        "à la même Filiale."
                    )
                )

            if record.member_id and (record.member_id.state != "active" or not record.member_id.active):
                raise ValidationError(_("Un membre non actif ne peut pas participer à une réunion."))

    # ==========================================================
    # CONTRÔLE DES HEURES
    # ==========================================================

    @api.constrains("arrival_time", "departure_time")
    def _check_attendance_times(self):
        for record in self:
            arrival = record._time_to_minutes(record.arrival_time)
            departure = record._time_to_minutes(record.departure_time)

            if (
                arrival is not None
                and departure is not None
                and departure < arrival
            ):
                raise ValidationError(
                    _(
                        "L'heure de départ ne peut pas être "
                        "antérieure à l'heure d'arrivée."
                    )
                )

    # ==========================================================
    # CONTRÔLE ABSENCE JUSTIFIÉE
    # ==========================================================

    @api.constrains(
        "state",
        "absence_reason",
        "absence_validated",
    )
    def _check_excused_absence(self):
        for record in self:

            if (
                record.state == "excused"
                and record.absence_validated
                and not record.absence_reason
            ):
                raise ValidationError(
                    _(
                        "Le motif est obligatoire pour "
                        "valider une absence justifiée."
                    )
                )

    # ==========================================================
    # DROIT DE VOTE
    # ==========================================================

    @api.constrains(
        "voting_eligible",
        "voting_block_reason",
    )
    def _check_voting_block_reason(self):
        for record in self:

            if (
                not record.voting_eligible
                and not record.voting_block_reason
            ):
                raise ValidationError(
                    _(
                        "Vous devez préciser le motif de suspension "
                        "du droit de vote."
                    )
                )
            
    
    def _check_meeting_not_closed(self):

        closed_records = self.filtered(
            lambda record:
                record.meeting_id
                and record.meeting_id.state == "closed"
        )

        if closed_records:

            raise UserError(
                _(
                    "La réunion est terminée et verrouillée.\n\n"
                    "Cette information ne peut plus "
                    "être modifiée."
                )
            )

    # ==========================================================
    # PROTECTION RÉUNION CLÔTURÉE
    # ==========================================================

    def write(self, vals):

        protected_fields = {
            "meeting_id",
            "member_id",
            "state",
            "arrival_time",
            "departure_time",
            "absence_reason",
            "voting_eligible",
        }

        if protected_fields.intersection(vals):

            for record in self:

                if record.meeting_state == "closed":
                    raise UserError(
                        _(
                            "La liste de présence d'une réunion "
                            "clôturée ne peut plus être modifiée."
                        )
                    )
        self._check_meeting_not_closed()

        return super().write(vals)

    # ==========================================================
    # PROTECTION SUPPRESSION
    # ==========================================================

    def unlink(self):

        for record in self:

            if record.meeting_state == "closed":
                raise UserError(
                    _(
                        "Une présence liée à une réunion clôturée "
                        "ne peut pas être supprimée."
                    )
                )
        self._check_meeting_not_closed()

        return super().unlink()

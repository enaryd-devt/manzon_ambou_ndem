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

# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

class AssociationMeeting(models.Model):
    _name = "association.meeting"
    _description = "Réunion de l'association"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "meeting_date desc, id desc"

    # ==========================================================
    # TECHNIQUE
    # ==========================================================

    active = fields.Boolean(
        string="Actif",
        default=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Filiale",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Référence",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: _("Nouveau"),
        index=True,
    )

    title = fields.Char(
        string="Objet de la réunion",
        required=True,
        tracking=True,
    )

    meeting_type = fields.Selection(
        selection=[
            ("ordinary", "Réunion ordinaire"),
            ("extraordinary", "Réunion extraordinaire"),
            ("ago", "Assemblée Générale Ordinaire"),
            ("age", "Assemblée Générale Extraordinaire"),
            ("executive", "Réunion du Bureau Exécutif"),
            ("commission", "Réunion de commission"),
            ("other", "Autre réunion"),
        ],
        string="Type de réunion",
        required=True,
        default="ordinary",
        tracking=True,
        index=True,
    )



    # ==========================================================
    # DATE ET HORAIRES
    # ==========================================================

    meeting_date = fields.Date(
        string="Date de réunion",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    location = fields.Char(
        string="Lieu",
        required=True,
        tracking=True,
    )

    start_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure prévue",
        tracking=True,
    )

    actual_start_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure effective de début",
        tracking=True,
    )

    end_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure de fin",
        tracking=True,
    )

    # ==========================================================
    # RESPONSABLES
    # ==========================================================

    committee_mode = fields.Selection(
        [("official", "Bureau exécutif mandaté"),
         ("special", "Bureau spécial de séance")],
        string="Bureau de la séance",
        required=True,
        default="official",
        tracking=True,
    )

    committee_id = fields.Many2one(
        "association.committee",
        string="Bureau exécutif",
        domain="[('id', 'in', available_committee_ids)]",
        tracking=True,
        ondelete="restrict",
    )

    available_committee_ids = fields.Many2many(
        "association.committee",
        compute="_compute_available_committee_ids",
        string="Bureaux disponibles",
    )

    special_officer_ids = fields.One2many(
        "association.meeting.officer",
        "meeting_id",
        string="Bureau spécial de séance",
        copy=True,
    )

    eligible_officer_ids = fields.Many2many(
        "association.member",
        compute="_compute_eligible_officer_ids",
        string="Responsables disponibles",
    )

    official_committee_line_ids = fields.Many2many(
        comodel_name="association.committee.line",
        string="Composition du bureau mandaté",
        compute="_compute_official_committee_line_ids",
    )

    chairperson_id = fields.Many2one(
        comodel_name="association.member",
        string="Président de séance",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    secretary_id = fields.Many2one(
        comodel_name="association.member",
        string="Secrétaire de séance",
        ondelete="restrict",
        tracking=True,
        domain="[('company_id', '=', company_id)]",
    )

    special_treasurer_id = fields.Many2one(
        comodel_name="association.member",
        string="Trésorier de séance",
        ondelete="restrict",
        tracking=True,
        domain="[('id', 'in', eligible_officer_ids)]",
    )

    special_censor_id = fields.Many2one(
        comodel_name="association.member",
        string="Censeur de séance",
        ondelete="restrict",
        tracking=True,
        domain="[('id', 'in', eligible_officer_ids)]",
    )

    @api.depends(
        "committee_mode",
        "committee_id.member_line_ids.member_id",
        "special_officer_ids.member_id",
    )
    def _compute_eligible_officer_ids(self):
        for meeting in self:
            if meeting.committee_mode == "official":
                meeting.eligible_officer_ids = (
                    meeting.committee_id.member_line_ids.mapped("member_id")
                )
            else:
                meeting.eligible_officer_ids = (
                    self.env["association.member"].search([
                        ("company_id", "=", meeting.company_id.id),
                        ("state", "=", "active"),
                        ("active", "=", True),
                    ])
                )

    @api.depends(
        "committee_mode",
        "committee_id",
        "committee_id.member_line_ids",
        "committee_id.member_line_ids.function_id",
    )
    def _compute_official_committee_line_ids(self):
        for meeting in self:
            meeting.official_committee_line_ids = (
                meeting.committee_id.member_line_ids
                if meeting.committee_mode == "official"
                else False
            )

    @api.depends("company_id", "meeting_date")
    def _compute_available_committee_ids(self):
        Committee = self.env["association.committee"]
        for meeting in self:
            meeting_date = meeting.meeting_date or fields.Date.context_today(
                meeting
            )
            meeting.available_committee_ids = Committee.search([
                ("company_id", "=", meeting.company_id.id),
                ("state", "=", "running"),
                ("start_date", "<=", meeting_date),
                ("end_date", ">=", meeting_date),
            ])

    @api.onchange(
        "committee_mode", "committee_id", "special_officer_ids",
        "chairperson_id", "secretary_id", "special_treasurer_id",
        "special_censor_id",
    )
    def _onchange_meeting_committee(self):
        for meeting in self:
            if meeting.committee_mode == "official" and meeting.committee_id:
                chairperson, secretary = meeting._get_official_responsibles(
                    meeting.committee_id
                )
                meeting.chairperson_id = chairperson
                meeting.secretary_id = secretary

            eligible = meeting.eligible_officer_ids
            if meeting.chairperson_id not in eligible:
                meeting.chairperson_id = False
            if meeting.secretary_id not in eligible:
                meeting.secretary_id = False
            if meeting.special_treasurer_id not in eligible:
                meeting.special_treasurer_id = False
            if meeting.special_censor_id not in eligible:
                meeting.special_censor_id = False

            meeting._refresh_responsible_attendances_onchange()

    def _get_official_responsibles(self, committee):
        """Return the mandated chairperson and secretary for a committee."""
        lines = committee.member_line_ids.sorted(
            key=lambda line: (line.sequence, line.id)
        )

        def member_for_role(keywords):
            candidate = lines.filtered(
                lambda line: any(
                    keyword in (line.function_id.name or "").lower()
                    for keyword in keywords
                )
            )[:1]
            return candidate.member_id if candidate else False

        chairperson = member_for_role(["président", "president"])
        secretary = member_for_role(["secrétaire", "secretaire"])
        if not chairperson and lines:
            chairperson = lines[0].member_id
        if not secretary:
            secretary = next(
                (line.member_id for line in lines if line.member_id != chairperson),
                chairperson,
            )
        return chairperson, secretary

    def _refresh_responsible_attendances_onchange(self):
        """Refresh roll-call rows for the selected office mode.

        Keeping both calls in a dedicated class method also prevents an
        attendance call from accidentally being left outside the onchange
        block when this section is extended or merged.
        """
        for meeting in self:
            if meeting.committee_mode == "official":
                meeting._onchange_add_committee_attendances()
            else:
                meeting._onchange_add_special_responsible_attendances()

    def _onchange_add_special_responsible_attendances(self):
        Attendance = self.env["association.attendance"]
        for meeting in self.filtered(lambda item: item.committee_mode == "special"):
            existing_ids = set(meeting.attendance_ids.mapped("member_id").ids)
            selected = (
                meeting.chairperson_id
                | meeting.secretary_id
                | meeting.special_treasurer_id
                | meeting.special_censor_id
            )
            new_lines = Attendance.browse()
            sequence = max(meeting.attendance_ids.mapped("sequence"), default=0) + 1
            for member in selected:
                if member.id not in existing_ids:
                    new_lines += Attendance.new({
                        "member_id": member.id,
                        "sequence": sequence,
                        "invited": True,
                        "state": "pending",
                    })
                    existing_ids.add(member.id)
                    sequence += 1
            meeting.attendance_ids += new_lines

    def _sync_special_responsible_attendances(self):
        Attendance = self.env["association.attendance"]
        for meeting in self.filtered(lambda item: item.committee_mode == "special"):
            existing_ids = set(meeting.attendance_ids.mapped("member_id").ids)
            sequence = max(meeting.attendance_ids.mapped("sequence"), default=0) + 1
            values_list = []
            for member in (
                meeting.chairperson_id
                | meeting.secretary_id
                | meeting.special_treasurer_id
                | meeting.special_censor_id
            ):
                if member.id not in existing_ids:
                    values_list.append({
                        "meeting_id": meeting.id,
                        "member_id": member.id,
                        "sequence": sequence,
                        "invited": True,
                        "state": "pending",
                    })
                    existing_ids.add(member.id)
                    sequence += 1
            if values_list:
                Attendance.create(values_list)
        return True

    def _committee_attendance_member_values(self):
        self.ensure_one()
        if self.committee_mode != "official" or not self.committee_id:
            return []
        members = self.committee_id.member_line_ids.sorted(
            key=lambda line: (line.sequence, line.id)
        ).mapped("member_id").filtered(
            lambda member: member.active and member.company_id == self.company_id
        )
        start_sequence = max(self.attendance_ids.mapped("sequence"), default=0) + 1
        return [
            {
                "member_id": member.id,
                "sequence": start_sequence + index,
                "invited": True,
                "state": "pending",
            }
            for index, member in enumerate(members)
        ]

    def _onchange_add_committee_attendances(self):
        """Display selected executive committee members in the roll call."""
        Attendance = self.env["association.attendance"]
        for meeting in self:
            existing_ids = set(meeting.attendance_ids.mapped("member_id").ids)
            new_lines = Attendance.browse()
            for values in meeting._committee_attendance_member_values():
                if values["member_id"] not in existing_ids:
                    new_lines += Attendance.new(values)
                    existing_ids.add(values["member_id"])
            meeting.attendance_ids += new_lines

    def _sync_committee_attendances(self):
        """Persist missing executive committee members without duplicates."""
        Attendance = self.env["association.attendance"]
        for meeting in self.filtered("committee_id"):
            existing_ids = set(meeting.attendance_ids.mapped("member_id").ids)
            values_list = [
                {"meeting_id": meeting.id, **values}
                for values in meeting._committee_attendance_member_values()
                if values["member_id"] not in existing_ids
            ]
            if values_list:
                Attendance.create(values_list)
        return True

    @api.constrains(
        "committee_mode", "committee_id", "special_officer_ids",
        "chairperson_id", "secretary_id", "special_treasurer_id",
        "special_censor_id", "meeting_date", "state",
    )
    def _check_meeting_committee(self):
        for meeting in self:
            if meeting.committee_mode == "official":
                if meeting.state != "draft" and not meeting.committee_id:
                    raise ValidationError(_(
                        "Sélectionnez le bureau exécutif mandaté pour la séance."
                    ))
                if not meeting.committee_id:
                    continue
                if meeting.meeting_date and not (
                    meeting.committee_id.start_date
                    <= meeting.meeting_date
                    <= meeting.committee_id.end_date
                ):
                    raise ValidationError(_(
                        "La date de réunion est hors du mandat du bureau "
                        "exécutif sélectionné."
                    ))
            elif meeting.committee_mode == "special":
                # In special mode the chairperson and secretary may be any
                # active member of the company; adding duplicate officer
                # rows is therefore optional.
                pass
            if meeting.state != "draft":
                if not meeting.chairperson_id or not meeting.secretary_id:
                    raise ValidationError(_(
                        "Définissez le président et le secrétaire de séance."
                    ))
            if meeting.committee_mode == "special":
                responsible_ids = [
                    member.id for member in (
                        meeting.chairperson_id,
                        meeting.secretary_id,
                        meeting.special_treasurer_id,
                        meeting.special_censor_id,
                    ) if member
                ]
                if len(responsible_ids) != len(set(responsible_ids)):
                    raise ValidationError(_(
                        "Chaque responsabilité du bureau spécial doit être "
                        "attribuée à un membre différent."
                    ))
                if any(
                    member and member not in meeting.eligible_officer_ids
                    for member in (
                        meeting.chairperson_id,
                        meeting.secretary_id,
                        meeting.special_treasurer_id,
                        meeting.special_censor_id,
                    )
                ):
                    raise ValidationError(_(
                        "Les responsables de séance doivent appartenir au "
                        "bureau sélectionné."
                    ))

    # ==========================================================
    # CONVOCATION
    # ==========================================================

    convocation_date = fields.Date(
        string="Date de convocation",
        tracking=True,
    )

    convocation_method = fields.Selection(
        selection=[
            ("physical", "Convocation physique"),
            ("phone", "Appel téléphonique"),
            ("sms", "SMS"),
            ("whatsapp", "WhatsApp"),
            ("email", "E-mail"),
            ("mixed", "Plusieurs moyens"),
        ],
        string="Mode de convocation",
        default="whatsapp",
        tracking=True,
    )

    convocation_note = fields.Html(
        string="Informations de convocation",
    )

    # ==========================================================
    # ORDRE DU JOUR
    # ==========================================================

    agenda = fields.Html(
        string="Ordre du jour",
        default=lambda self: self._default_agenda_template(),
    )

    can_edit_agenda = fields.Boolean(
        string="Peut modifier l'ordre du jour",
        compute="_compute_can_edit_agenda",
    )

    @api.model
    def _default_agenda_template(self):
        return _(
            "<ol>"
            "<li>Ouverture de la séance et mot de bienvenue</li>"
            "<li>Vérification des présences et du quorum</li>"
            "<li>Lecture et adoption de l'ordre du jour</li>"
            "<li>Lecture et adoption du procès-verbal précédent</li>"
            "<li>Point sur les cotisations et la situation financière</li>"
            "<li>Examen des points inscrits et décisions</li>"
            "<li>Divers</li>"
            "<li>Clôture de la séance</li>"
            "</ol>"
        )

    @api.depends_context("uid")
    def _compute_can_edit_agenda(self):
        can_edit = (
            self.env.user.has_group(
                "primetech_association.group_association_meeting_secretary"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_meeting_president"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_manager"
            )
            or self.env.user.has_group(
                "primetech_association.group_association_admin"
            )
        )
        for meeting in self:
            meeting.can_edit_agenda = can_edit

    # ==========================================================
    # PRÉSENCES
    # ==========================================================

    attendance_ids = fields.One2many(
        comodel_name="association.attendance",
        inverse_name="meeting_id",
        string="Liste d'appel",
    )

    invited_count = fields.Integer(
        string="Convoqués",
        compute="_compute_attendance_statistics",
        store=True,
    )

    pending_count = fields.Integer(
        string="En attente",
        compute="_compute_attendance_statistics",
        store=True,
    )

    present_count = fields.Integer(
        string="Présents",
        compute="_compute_attendance_statistics",
        store=True,
    )

    late_count = fields.Integer(
        string="Retards",
        compute="_compute_attendance_statistics",
        store=True,
    )

    absent_count = fields.Integer(
        string="Absents",
        compute="_compute_attendance_statistics",
        store=True,
    )

    excused_count = fields.Integer(
        string="Absences justifiées",
        compute="_compute_attendance_statistics",
        store=True,
    )

    attendance_percentage = fields.Float(
        string="Taux de présence",
        compute="_compute_attendance_statistics",
        store=True,
    )

    # ==========================================================
    # QUORUM
    # ==========================================================

    quorum_required = fields.Boolean(
        string="Quorum obligatoire",
        default=True,
        tracking=True,
    )

    quorum_percentage = fields.Float(
        string="Quorum requis (%)",
        default=50.0,
        tracking=True,
    )

    quorum_count = fields.Integer(
        string="Minimum requis",
        compute="_compute_quorum",
        store=True,
    )

    quorum_reached = fields.Boolean(
        string="Quorum atteint",
        compute="_compute_quorum",
        store=True,
    )

    # ==========================================================
    # RÉSOLUTIONS
    # ==========================================================

    resolution_ids = fields.One2many(
        comodel_name="association.meeting.resolution",
        inverse_name="meeting_id",
        string="Résolutions",
    )

    resolution_count = fields.Integer(
        string="Nombre de résolutions",
        compute="_compute_resolution_count",
    )

    # ==========================================================
    # PROCÈS-VERBAL
    # ==========================================================

    minutes = fields.Html(
        string="Procès-verbal",
       
    )

    minutes_approved = fields.Boolean(
        string="Procès-verbal approuvé",
        default=False,
        tracking=True,
    )

    minutes_approval_date = fields.Datetime(
        string="Date d'approbation du PV",
        readonly=True,
        tracking=True,
    )
    minutes_shared = fields.Boolean(string="PV partagé aux membres", default=False, tracking=True)
    minutes_attachment = fields.Binary(string="Procès-verbal à télécharger", attachment=True)
    minutes_attachment_filename = fields.Char(string="Nom du fichier du PV")

    description = fields.Html(
        string="Description de la réunion",
        help="Informations générales complémentaires sur la réunion.",
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # STATUT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("convoked", "Convoquée"),
            ("in_progress", "En cours"),
            ("closed", "Clôturée"),
            ("cancelled", "Annulée"),
        ],
        string="Statut",
        required=True,
        default="draft",
        tracking=True,
        index=True,
    )


    penalty_ids = fields.One2many(
        comodel_name="association.penalty",
        inverse_name="meeting_id",
        string="Sanctions et incidents",
    )
    expense_ids = fields.One2many("association.expense", "meeting_id", string="Dépenses de réunion")
    expense_total = fields.Monetary(string="Dépenses de réunion", compute="_compute_meeting_expenses", currency_field="currency_id")

    @api.depends("expense_ids.amount", "expense_ids.state")
    def _compute_meeting_expenses(self):
        for meeting in self:
            meeting.expense_total = sum(meeting.expense_ids.filtered(lambda expense: expense.state == "validated").mapped("amount"))

    def action_create_meeting_expense(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Dépense de séance"),
            "res_model": "association.meeting.expense.wizard", "view_mode": "form", "target": "new",
            "context": {"default_meeting_id": self.id},
        }

    def action_share_minutes(self):
        for meeting in self:
            if not meeting.minutes_approved:
                raise UserError(_("Le procès-verbal doit être approuvé avant son partage."))
            meeting.write({"minutes_shared": True})
            meeting.message_post(body=_("Le procès-verbal a été partagé avec les membres ordinaires."))
        return True

    penalty_count = fields.Integer(
        string="Nombre de sanctions",
        compute="_compute_penalty_count",
    )

    # ==========================================================
    # PRÉPARATION DU PROCÈS-VERBAL
    # ==========================================================

    minutes_prepared = fields.Boolean(
        string="Procès-verbal préparé",
        default=False,
        tracking=True,
    )

    minutes_preparation_date = fields.Datetime(
        string="Date de préparation du PV",
        readonly=True,
        tracking=True,
    )

    minutes_prepared_by = fields.Many2one(
        comodel_name="res.users",
        string="Procès-verbal préparé par",
        readonly=True,
        tracking=True,
    )

    penalty_draft_count = fields.Integer(
        string="Sanctions en attente",
        compute="_compute_penalty_dashboard",
    )

    actual_end_time = fields.Selection(
        selection="_get_hour_selection",
        string="Heure effective de clôture",
        tracking=True,
    )

    # ==========================================================
    # COTISATIONS / ENCAISSEMENTS DE LA RÉUNION
    # ==========================================================

    collection_subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation à encaisser",
        tracking=True,
        index=True,
    )

    collection_ids = fields.One2many(
        comodel_name="association.meeting.collection",
        inverse_name="meeting_id",
        string="Encaissements de cotisations",
        copy=False,
    )

    subscription_session_ids = fields.One2many(
        comodel_name="association.meeting.subscription.session",
        inverse_name="meeting_id",
        string="Sessions de cotisation",
        copy=False,
    )

    meeting_payment_ids = fields.One2many(
        comodel_name="association.payment",
        inverse_name="meeting_id",
        string="Paiements issus de la réunion",
        readonly=True,
        copy=False,
    )

    collection_count = fields.Integer(
        string="Nombre de membres",
        compute="_compute_collection_statistics",
    )

    collection_paid_count = fields.Integer(
        string="Membres encaissés",
        compute="_compute_collection_statistics",
    )

    collection_pending_count = fields.Integer(
        string="En attente",
        compute="_compute_collection_statistics",
    )

    collection_total = fields.Monetary(
        string="Total encaissé",
        currency_field="currency_id",
        compute="_compute_collection_statistics",
    )

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        tracking=True,
    )

    subscription_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle de cotisation",
        readonly=True,
        tracking=True,
    )

    subscription_session_id = fields.Many2one(
        comodel_name="association.meeting.subscription.session",
        compute="_compute_subscription_session",
        string="Session de cotisation chargée",
        readonly=True,
    )

    subscription_report_available = fields.Boolean(
        compute="_compute_subscription_session",
        string="Rapport de cotisation disponible",
    )

    subscription_snapshot_ids = fields.Many2many(
        "association.meeting.subscription.snapshot",
        compute="_compute_subscription_session", string="Situation figée du cycle",
        readonly=True,
    )

    subscription_line_ids = fields.One2many(
        comodel_name="association.subscription.line",
        compute="_compute_subscription_line_ids",
        string="Cotisations des membres",
    )

    @api.depends(
        "subscription_id",
        "subscription_period_id",
        "subscription_session_ids.subscription_id",
        "subscription_session_ids.period_id",
        "subscription_session_ids.state",
    )
    def _compute_subscription_session(self):
        """Expose the session that supplies the data shown in the tab.

        The meeting may contain several subscription sessions.  The
        ``Cotisations`` tab is intentionally scoped to the subscription and
        cycle selected by the user, rather than silently switching to the
        subscription's latest global cycle.
        """
        for meeting in self:
            session = meeting.subscription_session_ids.filtered(
                lambda item: item.subscription_id == meeting.subscription_id
                and item.period_id == meeting.subscription_period_id
            )[:1]
            meeting.subscription_session_id = session
            meeting.subscription_report_available = bool(
                session and session.state == "closed"
            )
            meeting.subscription_snapshot_ids = session.snapshot_ids

    # ==========================================================
    # STATISTIQUES DE LA CAGNOTTE
    # ==========================================================

    pot_collected_amount = fields.Monetary(
        string="Cagnotte collectée",
        compute="_compute_pot_statistics",
        currency_field="currency_id",
    )

    pot_allocated_amount = fields.Monetary(
        string="Cagnotte attribuée",
        compute="_compute_pot_statistics",
        currency_field="currency_id",
    )

    pot_available_amount = fields.Monetary(
        string="Cagnotte disponible",
        compute="_compute_pot_statistics",
        currency_field="currency_id",
    )

    pot_beneficiary_count = fields.Integer(
        string="Bénéficiaires",
        compute="_compute_pot_statistics",
    )

    pot_settlement_state = fields.Selection(
        [("open", "Caisse temporaire ouverte"),
         ("settled", "Caisse soldée")],
        string="Règlement de la caisse",
        default="open",
        required=True,
        copy=False,
        tracking=True,
    )

    pot_settlement_fund_id = fields.Many2one(
        "association.fund",
        string="Compte de versement final",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        copy=False,
        tracking=True,
    )

    pot_settlement_transaction_id = fields.Many2one(
        "association.fund.transaction",
        string="Mouvement de versement final",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    allocation_ids = fields.One2many(
        comodel_name="association.subscription.allocation",
        related="subscription_period_id.allocation_ids",
        string="Bénéficiaires",
        readonly=True,
    )

    # ==========================================================
    # SAISIE ATTRIBUTION DE CAGNOTTE
    # ==========================================================

    pot_beneficiary_id = fields.Many2one(
        comodel_name="association.member",
        string="Bénéficiaire",
        tracking=True,
    )

    pot_allocation_amount = fields.Monetary(
        string="Montant à attribuer",
        currency_field="currency_id",
    )

    pot_allocation_method = fields.Selection(
        selection=[
            ("rotation", "Rotation"),
            ("planned", "Ordre planifié"),
            (
                "meeting_decision",
                "Décision de la réunion",
            ),
            ("draw", "Tirage au sort"),
            ("priority", "Besoin prioritaire"),
            ("other", "Autre"),
        ],
        string="Mode d'attribution",
        default="meeting_decision",
    )

    pot_allocation_note = fields.Text(
        string="Décision / Observation",
    )

    # ==========================================================
    # DISPONIBILITÉ DU CYCLE SUIVANT
    # ==========================================================

    can_open_next_subscription_cycle = fields.Boolean(
        string="Peut ouvrir le cycle suivant",
        compute="_compute_can_open_next_subscription_cycle",
    )

    # ==========================================================
    # CALCUL - DISPONIBILITÉ DU CYCLE SUIVANT
    # ==========================================================

    @api.depends(
        "subscription_id",
        "subscription_id.state",
        "subscription_id.period_ids",
        "subscription_id.period_ids.state",
    )
    def _compute_can_open_next_subscription_cycle(self):

        for meeting in self:

            meeting.can_open_next_subscription_cycle = False

            subscription = meeting.subscription_id

            if not subscription:
                continue

            # ======================================================
            # COTISATION ACTIVE UNIQUEMENT
            # ======================================================

            if subscription.state != "running":
                continue

            # ======================================================
            # CYCLE EN COURS
            # ======================================================

            running_period = (
                subscription.period_ids.filtered(
                    lambda period:
                        period.state == "running"
                )
            )

            if running_period:
                continue

            # ======================================================
            # DERNIER CYCLE TERMINÉ
            # ======================================================

            closed_period = (
                subscription.period_ids.filtered(
                    lambda period:
                        period.state == "closed"
                )
            )

            if not closed_period:
                continue

            # ======================================================
            # LE CYCLE SUIVANT PEUT ÊTRE OUVERT
            # ======================================================

            meeting.can_open_next_subscription_cycle = True

    # ==========================================================
    # CALCUL DES STATISTIQUES DE LA CAGNOTTE
    # ==========================================================

    @api.depends(
        "subscription_line_ids.payment_state",
        "subscription_line_ids.amount_paid",
        "meeting_payment_ids.state",
        "meeting_payment_ids.amount",
        "meeting_payment_ids.processed_surplus_amount",
        "meeting_payment_ids.surplus_action",
        "allocation_ids",
        "allocation_ids.amount",
        "allocation_ids.beneficiary_id",
        "allocation_ids.state",
        "pot_settlement_state",
        "expense_ids.amount",
        "expense_ids.state",
    )
    def _compute_pot_statistics(self):

        for meeting in self:

            meeting.pot_collected_amount = 0.0
            meeting.pot_allocated_amount = 0.0
            meeting.pot_available_amount = 0.0
            meeting.pot_beneficiary_count = 0

            allocations = meeting.allocation_ids.filtered(
                lambda allocation: allocation.meeting_id == meeting
                and allocation.state in ("confirmed", "paid")
                and allocation.beneficiary_id
            )

            collected_amount = sum(
                payment.amount
                - (
                    payment.processed_surplus_amount
                    if payment.surplus_action == "refund"
                    else 0.0
                )
                for payment in meeting.meeting_payment_ids
                if payment.state == "confirmed"
            )
            # Les anciens encaissements créés avant l'ajout du lien
            # ``meeting_id`` restent visibles dans la réunion. Ce repli
            # permet de présenter leur montant dans les indicateurs du cycle.
            if not meeting.meeting_payment_ids.filtered(
                lambda payment: payment.state == "confirmed"
            ):
                collected_amount = sum(
                    meeting.subscription_line_ids.mapped("amount_paid")
                )
            allocated_amount = sum(allocations.mapped("amount"))

            meeting.pot_collected_amount = collected_amount
            meeting.pot_allocated_amount = allocated_amount
            meeting.pot_available_amount = max(
                collected_amount - allocated_amount - meeting.expense_total, 0.0
            )
            if meeting.pot_settlement_state == "settled":
                meeting.pot_available_amount = 0.0

            meeting.pot_beneficiary_count = len(
                allocations.mapped(
                    "beneficiary_id"
                )
            )



    # ==========================================================
    # CALCUL DU NOMBRE DE BÉNÉFICIAIRES
    # ==========================================================

    @api.depends(
        "subscription_period_id",
        "allocation_ids",
        "allocation_ids.beneficiary_id",
        "allocation_ids.state",
    )
    def _compute_pot_beneficiary_count(self):

        for meeting in self:

            meeting.pot_beneficiary_count = 0

            if not meeting.subscription_period_id:
                continue

            allocations = meeting.allocation_ids.filtered(
                lambda allocation:
                    allocation.state
                    in (
                        "confirmed",
                        "paid",
                    )
                    and allocation.beneficiary_id
            )

            meeting.pot_beneficiary_count = len(
                allocations.mapped("beneficiary_id")
            )


    # ==========================================================
    # ACTUALISER LE CYCLE DE COTISATION
    # ==========================================================

    def action_refresh_subscription_cycle(self):
        Period = self.env[
            "association.subscription.period"
        ]

        for meeting in self:

            if not meeting.subscription_id:
                raise UserError(
                    _(
                        "Veuillez sélectionner une cotisation "
                        "avant d'actualiser le cycle."
                    )
                )

            # A session selected in the meeting is the source of truth for
            # this tab.  It may differ from the subscription's current cycle
            # when the meeting is displaying an already closed session.
            session = meeting._get_subscription_session_for_subscription(
                meeting.subscription_id
            )
            if session:
                meeting.subscription_period_id = session.period_id.id
                meeting._sync_subscription_attendances()
                return {"type": "ir.actions.client", "tag": "reload"}

            # ==================================================
            # RECHERCHE DU CYCLE RÉELLEMENT EN COURS
            # ==================================================

            period = Period.search(
                [
                    (
                        "subscription_id",
                        "=",
                        meeting.subscription_id.id,
                    ),
                    (
                        "state",
                        "=",
                        "running",
                    ),
                ],
                order="sequence desc, id desc",
                limit=1,
            )

            if not period:
                # The meeting must remain the working screen.  Create the
                # next period through the subscription business method rather
                # than opening the cycle-start wizard.
                meeting.subscription_id.action_open_next_period()
                meeting.subscription_id.invalidate_recordset([
                    "current_period_id", "period_count",
                ])
                period = meeting.subscription_id.current_period_id
                if not period or period.state != "running":
                    raise ValidationError(
                        _("Le nouveau cycle de cotisation n'a pas pu être démarré.")
                    )

            # ==================================================
            # ATTACHER LE CYCLE À LA RÉUNION
            # ==================================================

            meeting.subscription_period_id = period.id
            meeting._sync_subscription_attendances()
            self.env["association.meeting.subscription.session"].create({
                "meeting_id": meeting.id,
                "subscription_id": meeting.subscription_id.id,
                "period_id": period.id,
            })

            # ==================================================
            # INVALIDER LES DONNÉES DE LA RÉUNION
            # ==================================================

            meeting.invalidate_recordset([
                "subscription_period_id",
                "subscription_line_ids",
                "pot_collected_amount",
                "pot_allocated_amount",
                "pot_available_amount",
                "allocation_ids",
            ])

            # ==================================================
            # INVALIDER LA COTISATION
            # ==================================================

            meeting.subscription_id.invalidate_recordset([
                "current_period_id",
                "period_count",
            ])

            meeting.message_post(
                body=_(
                    "Le cycle %(cycle)s a été actualisé "
                    "dans la réunion."
                )
                % {
                    "cycle":
                        period.display_name,
                }
            )

        return False
    
    # ==========================================================
    # TERMINER LE CYCLE DE COTISATION COURANT
    # ==========================================================

    def action_close_subscription_cycle(self):

        for meeting in self:

            period = meeting.subscription_period_id

            if not period:

                raise ValidationError(
                    _(
                        "Aucun cycle de cotisation n'est "
                        "rattaché à cette réunion."
                    )
                )

            if period.state == "closed":

                raise ValidationError(
                    _(
                        "Le cycle de cotisation est déjà terminé."
                    )
                )

            if period.state != "running":

                raise ValidationError(
                    _(
                        "Seul un cycle en cours peut être terminé."
                    )
                )

            # ==================================================
            # VÉRIFIER LES ENCAISSEMENTS EN COURS
            # ==================================================

            pending_collections = (
                meeting.collection_ids.filtered(
                    lambda line:
                        line.state == "pending"
                        and (line.amount or 0.0) > 0
                )
            )

            if pending_collections:

                raise ValidationError(
                    _(
                        "Impossible de terminer le cycle.\n\n"
                        "%(count)s encaissement(s) saisi(s) "
                        "ne sont pas encore validé(s)."
                    )
                    % {
                        "count": len(
                            pending_collections
                        ),
                    }
                )

            # ==================================================
            # TERMINER LE CYCLE
            # ==================================================

            session = meeting.subscription_session_ids.filtered(
                lambda item: item.period_id == period
            )[:1]
            if session:
                return session.action_open_settlement()

            # Compatibility for historical meetings that have no session.
            # A zero temporary balance must never open the closing wizard.
            if (period.available_amount or 0.0) <= 0.01:
                period.write({"state": "closed"})
                period.subscription_id.line_ids.write({
                    "amount_received": 0.0,
                })
                period.subscription_id.invalidate_recordset([
                    "current_period_id",
                    "period_count",
                ])
                return {
                    "type": "ir.actions.client",
                    "tag": "reload",
                }

            return period.action_close()

            # ==================================================
            # ACTUALISER LA RÉUNION
            # ==================================================

            meeting.invalidate_recordset([
                "subscription_period_id",
                "subscription_line_ids",
                "pot_collected_amount",
                "pot_allocated_amount",
                "pot_available_amount",
                "allocation_ids",
            ])

        return {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }
    
    # ==========================================================
    # ACTION - OUVRIR LE CYCLE SUIVANT DEPUIS LA RÉUNION
    # ==========================================================

    def action_open_next_subscription_cycle(self):

        self.ensure_one()

        # ======================================================
        # CONTRÔLE DE LA RÉUNION
        # ======================================================

        if self.state == "closed":

            raise UserError(
                _(
                    "Impossible d'ouvrir un nouveau cycle "
                    "depuis une réunion clôturée."
                )
            )

        # ======================================================
        # CONTRÔLE DE LA COTISATION
        # ======================================================

        subscription = self.subscription_id

        if not subscription:

            raise ValidationError(
                _(
                    "Sélectionnez une cotisation avant "
                    "d'ouvrir le cycle suivant."
                )
            )

        if subscription.state != "running":

            raise ValidationError(
                _(
                    "La cotisation %(subscription)s "
                    "n'est pas en cours."
                )
                % {
                    "subscription":
                        subscription.display_name,
                }
            )

        # ======================================================
        # VÉRIFICATION D'UN CYCLE DÉJÀ EN COURS
        # ======================================================

        running_period = (
            subscription.period_ids.filtered(
                lambda period:
                    period.state == "running"
            )
        )

        if running_period:

            current_period = running_period.sorted(
                key=lambda period: (
                    period.sequence,
                    period.id,
                ),
                reverse=True,
            )[0]

            # --------------------------------------------------
            # CHARGER LE CYCLE EXISTANT DANS LA RÉUNION
            # --------------------------------------------------

            self.subscription_period_id = (
                current_period.id
            )

            return {
                "type":
                    "ir.actions.client",

                "tag":
                    "reload",
            }

        # ======================================================
        # OUVERTURE VIA LA MÉTHODE MÉTIER DE LA COTISATION
        # ======================================================

        subscription.action_open_next_period()

        # ======================================================
        # RECALCUL DU CYCLE COURANT
        # ======================================================

        subscription.invalidate_recordset([
            "current_period_id",
            "period_count",
        ])

        # ======================================================
        # RÉCUPÉRATION DU NOUVEAU CYCLE
        # ======================================================

        new_period = (
            subscription.period_ids.filtered(
                lambda period:
                    period.state == "running"
            )
        )

        if not new_period:

            raise ValidationError(
                _(
                    "Le cycle suivant a été créé, mais aucun "
                    "cycle en cours n'a pu être chargé."
                )
            )

        new_period = new_period.sorted(
            key=lambda period: (
                period.sequence,
                period.id,
            ),
            reverse=True,
        )[0]

        # ======================================================
        # ASSOCIATION DU CYCLE À LA RÉUNION
        # ======================================================

        self.subscription_period_id = (
            new_period.id
        )

        # ======================================================
        # NETTOYAGE DES MONTANTS DE SAISIE
        # ======================================================

        subscription.line_ids.write({
            "amount_received": 0.0,
        })

        # ======================================================
        # INVALIDATION DES DONNÉES DU NOUVEAU CYCLE
        # ======================================================

        subscription.line_ids.invalidate_recordset([
            "amount_due",
            "amount_paid",
            "balance",
            "payment_state",
            "payment_date",
        ])

        # ======================================================
        # MESSAGE
        # ======================================================

        self.message_post(
            body=_(
                "Le cycle %(cycle)s de la cotisation "
                "%(subscription)s a été ouvert et chargé "
                "dans la réunion."
            )
            % {
                "cycle":
                    new_period.display_name,

                "subscription":
                    subscription.display_name,
            }
        )

        # ======================================================
        # ACTUALISATION DE LA RÉUNION
        # ======================================================

        return {
            "type":
                "ir.actions.client",

            "tag":
                "reload",
        }

    
    # ==========================================================
    # ATTRIBUER LA CAGNOTTE
    # ==========================================================

    def action_allocate_subscription_pot(self):
        self.ensure_one()


        period = self.subscription_period_id

        if not period:
            raise ValidationError(
                _(
                    "Aucun cycle de cotisation n'est "
                    "sélectionné pour cette réunion."
                )
            )

        if period.state != "running":
            raise ValidationError(
                _(
                    "Le cycle %(period)s n'est pas en cours."
                )
                % {
                    "period": period.display_name,
                }
            )

        if not self.pot_beneficiary_id:
            raise ValidationError(
                _(
                    "Veuillez sélectionner un bénéficiaire."
                )
            )

        amount = self.pot_allocation_amount or 0.0

        if amount <= 0:
            raise ValidationError(
                _(
                    "Veuillez saisir un montant à attribuer "
                    "strictement supérieur à zéro."
                )
            )

        available_amount = self.pot_available_amount or 0.0

        if amount > available_amount:
            raise ValidationError(
                _(
                    "Le montant attribué dépasse la cagnotte "
                    "disponible.\n\n"
                    "Disponible : %(available).2f\n"
                    "Montant demandé : %(amount).2f"
                )
                % {
                    "available": available_amount,
                    "amount": amount,
                }
            )

        # ======================================================
        # RECHERCHE DE LA LIGNE DU MEMBRE DANS LA COTISATION
        # ======================================================

        subscription_line = self.env[
            "association.subscription.line"
        ].search(
            [
                (
                    "subscription_id",
                    "=",
                    period.subscription_id.id,
                ),
                (
                    "member_id",
                    "=",
                    self.pot_beneficiary_id.id,
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
                        self.pot_beneficiary_id.display_name,
                    "subscription":
                        period.subscription_id.display_name,
                }
            )

        # ======================================================
        # CRÉATION DE L'ATTRIBUTION
        # ======================================================

        session = self.subscription_session_id or self.subscription_session_ids.filtered(
            lambda item: item.period_id == period
        )[:1]

        allocation = self.env[
            "association.subscription.allocation"
        ].create(
            {
                "period_id": period.id,
                "meeting_id": self.id,
                "meeting_subscription_session_id": session.id,
                "beneficiary_id":
                    self.pot_beneficiary_id.id,
                "amount": amount,
                "allocation_method":
                    self.pot_allocation_method
                    or "meeting_decision",
                "decision_note":
                    self.pot_allocation_note,
            }
        )

        # ======================================================
        # CONFIRMATION DE L'ATTRIBUTION
        # ======================================================

        allocation.action_confirm()

        beneficiary_name = (
            self.pot_beneficiary_id.display_name
        )

        # ======================================================
        # HISTORIQUE RÉUNION
        # ======================================================

        self.message_post(
            body=_(
                "Cagnotte attribuée à %(member)s : "
                "%(amount).2f %(currency)s."
            )
            % {
                "member": beneficiary_name,
                "amount": amount,
                "currency": self.currency_id.name or "",
            }
        )

        # ======================================================
        # NETTOYAGE DE LA ZONE DE SAISIE
        # ======================================================

        self.write(
            {
                "pot_beneficiary_id": False,
                "pot_allocation_amount": 0.0,
                "pot_allocation_method":
                    "meeting_decision",
                "pot_allocation_note": False,
            }
        )

        # ======================================================
        # ACTUALISATION DU FORMULAIRE DE RÉUNION
        # ======================================================

        return {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }

    def action_settle_meeting_pot(self):
        """Finalize the meeting cycle and settle its temporary cash.

        This is the single meeting action for cycle closure: it opens the
        decision flow, validates allocations, transfers any residual to the
        selected financial account, then locks the cycle and its session.
        """
        self.ensure_one()
        if not self.subscription_period_id:
            raise ValidationError(
                _("Aucun cycle de cotisation n'est sélectionné.")
            )
        if self.subscription_period_id.state != "running":
            raise ValidationError(
                _("Le cycle de cotisation doit être en cours.")
            )
        return self.action_close_subscription_cycle()

    @api.depends(
        "subscription_id",
        "subscription_period_id",
    )
    def _compute_subscription_line_ids(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for meeting in self:

            if (
                not meeting.subscription_id
                or not meeting.subscription_period_id
            ):
                meeting.subscription_line_ids = False
                continue

            meeting.subscription_line_ids = (
                SubscriptionLine.search(
                    [
                        (
                            "subscription_id",
                            "=",
                            meeting.subscription_id.id,
                        ),
                    ],
                    order="sequence asc, id asc",
                )
            )
    
    @api.onchange("subscription_id")
    def _onchange_subscription_id(self):

        for meeting in self:

            meeting.subscription_period_id = False

            if not meeting.subscription_id:
                meeting.attendance_ids = [(5, 0, 0)]
                continue

            session = meeting._get_subscription_session_for_subscription(
                meeting.subscription_id
            )
            meeting.subscription_period_id = (
                session.period_id if session else meeting.subscription_id.current_period_id
            )
            meeting._onchange_load_subscription_attendances()

    def _attendance_member_values(self):
        self.ensure_one()
        members = self.subscription_id.line_ids.mapped("member_id").filtered(
            lambda member: member.active and member.company_id == self.company_id
        )
        return [
            {
                "member_id": member.id,
                "sequence": sequence,
                "invited": True,
                "state": "pending",
            }
            for sequence, member in enumerate(members, start=1)
        ]

    def _onchange_load_subscription_attendances(self):
        """Immediately display the selected subscription's roll call."""
        for meeting in self:
            meeting.attendance_ids = [
                (5, 0, 0),
                *(
                    (0, 0, values)
                    for values in meeting._attendance_member_values()
                ),
            ] if meeting.subscription_id else [(5, 0, 0)]

    def _sync_subscription_attendances(self):
        """Persist missing roll-call rows without duplicating existing ones."""
        Attendance = self.env["association.attendance"]
        for meeting in self.filtered("subscription_id"):
            existing_ids = set(meeting.attendance_ids.mapped("member_id").ids)
            values_list = [
                {"meeting_id": meeting.id, **values}
                for values in meeting._attendance_member_values()
                if values["member_id"] not in existing_ids
            ]
            if values_list:
                Attendance.create(values_list)
        return True

    def _get_subscription_session_for_subscription(self, subscription):
        """Return the session cycle that must be loaded for a subscription."""
        self.ensure_one()
        sessions = self.subscription_session_ids.filtered(
            lambda item: item.subscription_id == subscription and item.period_id
        )
        active_sessions = sessions.filtered(
            lambda item: item.state in ("draft", "collecting", "decision")
        )
        return (active_sessions or sessions).sorted(
            key=lambda item: (item.sequence, item.id), reverse=True
        )[:1]

    def action_print_subscription_report(self):
        """Print the report of the session currently loaded in this tab."""
        self.ensure_one()
        session = self.subscription_session_id
        if not session or session.state != "closed":
            raise UserError(_("Le rapport est disponible après la clôture du cycle."))
        return session.action_print_report()

    # ==========================================================
    # STATISTIQUES DES ENCAISSEMENTS
    # ==========================================================

    @api.depends(
        "subscription_line_ids",
        "subscription_line_ids.payment_state",
        "subscription_line_ids.amount_paid",
    )
    def _compute_collection_statistics(self):

        for meeting in self:

            # ==================================================
            # INITIALISATION OBLIGATOIRE DE TOUS LES CHAMPS
            # ==================================================

            meeting.collection_count = 0
            meeting.collection_paid_count = 0
            meeting.collection_pending_count = 0
            meeting.collection_total = 0.0

            # ==================================================
            # RÉCUPÉRATION DES LIGNES
            # ==================================================

            collection_lines = meeting.subscription_line_ids

            if not collection_lines:
                continue

            # ==================================================
            # LIGNES EN ATTENTE
            # ==================================================

            pending_lines = collection_lines.filtered(
                lambda line: line.payment_state != "paid"
            )

            # ==================================================
            # LIGNES ENCAISSÉES
            # ==================================================

            paid_lines = collection_lines.filtered(
                lambda line: line.payment_state == "paid"
            )

            # ==================================================
            # AFFECTATION DE TOUS LES CHAMPS CALCULÉS
            # ==================================================

            meeting.collection_count = len(
                collection_lines
            )

            meeting.collection_pending_count = len(
                pending_lines
            )

            meeting.collection_paid_count = len(
                paid_lines
            )

            meeting.collection_total = sum(
                paid_lines.mapped("amount_paid")
            )


    # ==========================================================
    # GÉNÉRER LES MEMBRES DE LA COTISATION
    # ==========================================================

    def action_generate_collection_members(self):

        Collection = self.env[
            "association.meeting.collection"
        ]

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        for meeting in self:

            # ==================================================
            # CONTRÔLE DE LA RÉUNION
            # ==================================================

            if meeting.state == "closed":

                raise UserError(
                    _(
                        "Impossible de générer les membres.\n\n"
                        "La réunion est déjà clôturée."
                    )
                )

            # ==================================================
            # CONTRÔLE DE LA COTISATION
            # ==================================================

            if not meeting.collection_subscription_id:

                raise UserError(
                    _(
                        "Veuillez sélectionner une cotisation "
                        "avant de générer les membres."
                    )
                )

            # ==================================================
            # RECHERCHE DES LIGNES DE COTISATION
            # ==================================================

            subscription_lines = SubscriptionLine.search(
                [
                    (
                        "subscription_id",
                        "=",
                        meeting.collection_subscription_id.id,
                    ),
                    (
                        "balance",
                        ">",
                        0,
                    ),
                ],
                order="member_id",
            )

            # ==================================================
            # AUCUN MEMBRE
            # ==================================================

            if not subscription_lines:

                raise UserError(
                    _(
                        "Aucun membre en attente de paiement "
                        "n'a été trouvé pour la cotisation %(subscription)s."
                    )
                    % {
                        "subscription":
                            meeting.collection_subscription_id.display_name,
                    }
                )

            # ==================================================
            # LIGNES DÉJÀ GÉNÉRÉES
            # ==================================================

            existing_subscription_line_ids = set(
                meeting.collection_ids.mapped(
                    "subscription_line_id"
                ).ids
            )

            # ==================================================
            # PRÉPARATION DES NOUVELLES LIGNES
            # ==================================================

            values_list = []

            sequence = (
                max(
                    meeting.collection_ids.mapped("sequence"),
                    default=0,
                )
                + 10
            )

            for subscription_line in subscription_lines:

                if (
                    subscription_line.id
                    in existing_subscription_line_ids
                ):
                    continue

                values_list.append(
                    {
                        "meeting_id": meeting.id,
                        "sequence": sequence,
                        "subscription_id":
                            meeting.collection_subscription_id.id,
                        "subscription_line_id":
                            subscription_line.id,
                        "amount": 0.0,
                        "payment_method": "cash",
                        "state": "pending",
                    }
                )

                sequence += 10

            # ==================================================
            # AUCUNE NOUVELLE LIGNE
            # ==================================================

            if not values_list:

                raise UserError(
                    _(
                        "Tous les membres concernés par cette "
                        "cotisation sont déjà présents dans "
                        "la liste d'encaissement."
                    )
                )

            # ==================================================
            # CRÉATION DES LIGNES
            # ==================================================

            Collection.create(values_list)

            # ==================================================
            # MESSAGE CHATTER
            # ==================================================

            meeting.message_post(
                body=_(
                    "%(count)s membre(s) ont été généré(s) "
                    "en attente d'encaissement pour la "
                    "cotisation %(subscription)s."
                )
                % {
                    "count": len(values_list),
                    "subscription":
                        meeting.collection_subscription_id.display_name,
                }
            )

        return True


    def action_pay_subscription(self):

        self.ensure_one()

        if not self.subscription_line_id:
            raise ValidationError(
                _("Aucune cotisation n'est associée.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Paiement depuis la réunion"),
            "res_model":
                "association.subscription.payment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_origin":
                    "meeting",

                "default_subscription_line_id":
                    self.subscription_line_id.id,

                "default_meeting_id":
                    self.meeting_id.id,
            },
        }
    # ==========================================================
    # ENCAISSER TOUTES LES LIGNES SAISIES
    # ==========================================================

    def action_collect_all(self):

        for meeting in self:

            if meeting.state == "closed":

                raise UserError(
                    _(
                        "Impossible d'effectuer les encaissements.\n\n"
                        "La réunion est clôturée."
                    )
                )

            lines_to_collect = meeting.collection_ids.filtered(
                lambda line:
                    line.state == "pending"
                    and line.amount > 0
            )

            if not lines_to_collect:

                raise UserError(
                    _(
                        "Aucun montant à encaisser.\n\n"
                        "Veuillez saisir le montant reçu pour "
                        "au moins un membre."
                    )
                )

            collected_count = 0

            for collection_line in lines_to_collect:

                collection_line.action_collect()

                collected_count += 1

            meeting.message_post(
                body=_(
                    "%(count)s encaissement(s) ont été "
                    "validé(s) pendant la réunion."
                )
                % {
                    "count": collected_count,
                }
            )

        return True


    # ==========================================================
    # APPLIQUER LES SANCTIONS EN ATTENTE
    # ==========================================================

    def action_apply_draft_penalties(self):

        for meeting in self:

            if meeting.state == "closed":

                raise UserError(
                    _(
                        "Impossible d'appliquer les sanctions.\n\n"
                        "La réunion est clôturée."
                    )
                )

            draft_penalties = meeting.penalty_ids.filtered(
                lambda penalty:
                    penalty.state == "draft"
            )

            if not draft_penalties:

                raise UserError(
                    _(
                        "Aucune sanction en attente à appliquer."
                    )
                )

            draft_count = len(draft_penalties)

            draft_penalties.action_validate()

            meeting.message_post(
                body=_(
                    "%(count)s sanction(s) ont été appliquée(s) "
                    "pendant la réunion."
                )
                % {
                    "count": draft_count,
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }


    # ==========================================================
    # SÉLECTION COMPLÈTE DES HEURES
    # ==========================================================

    @api.model
    def _get_hour_selection(self):

        return [
            (
                "%02d:%02d" % (hour, minute),
                "%02d:%02d" % (hour, minute),
            )
            for hour in range(24)
            for minute in range(60)
        ]

    
    @api.depends(
        "penalty_ids",
        "penalty_ids.state",
    )
    def _compute_penalty_dashboard(self):

        for meeting in self:

            meeting.penalty_draft_count = len(
                meeting.penalty_ids.filtered(
                    lambda penalty:
                        penalty.state == "draft"
                )
            )


    # ==========================================================
    # PRÉPARER LE PROCÈS-VERBAL
    # ==========================================================

    def action_prepare_minutes(self):

        for meeting in self:

            # Le procès-verbal est une photographie de la réunion. Il est
            # donc toujours préparé avec les données disponibles au moment du
            # clic : heure, liste d'appel et décisions peuvent être complétées
            # ultérieurement dans le contenu généré.

            # ==================================================
            # FORMATAGE DE LA DATE
            # ==================================================

            meeting_date = ""

            if meeting.meeting_date:

                meeting_date = fields.Date.to_date(
                    meeting.meeting_date
                ).strftime("%d/%m/%Y")

            # ==================================================
            # FORMATAGE DES HEURES
            # ==================================================

            start_time = (
                meeting.actual_start_time
                or meeting.start_time
                or ""
            )

            end_time = meeting.actual_end_time or ""

            # ==================================================
            # PRÉSENTS
            # ==================================================

            present_members = meeting.attendance_ids.filtered(
                lambda attendance:
                    attendance.state == "present"
            )

            present_lines = []

            for attendance in present_members:

                member_name = (
                    attendance.member_id.display_name
                    if attendance.member_id
                    else _("Membre non renseigné")
                )

                present_lines.append(
                    "<li>%s</li>"
                    % member_name
                )

            present_html = (
                "<ul>%s</ul>"
                % "".join(present_lines)
                if present_lines
                else (
                    "<p>"
                    "Aucun membre présent enregistré."
                    "</p>"
                )
            )

            # ==================================================
            # RETARDATAIRES
            # ==================================================

            late_members = meeting.attendance_ids.filtered(
                lambda attendance:
                    attendance.state == "late"
            )

            late_lines = []

            for attendance in late_members:

                member_name = (
                    attendance.member_id.display_name
                    if attendance.member_id
                    else _("Membre non renseigné")
                )

                late_lines.append(
                    (
                        "<li>"
                        "<strong>%s</strong>"
                        " — arrivée à %s"
                        " (%s minute(s) de retard)"
                        "</li>"
                    )
                    % (
                        member_name,
                        attendance.arrival_time or "",
                        attendance.late_minutes or 0,
                    )
                )

            late_html = (
                "<ul>%s</ul>"
                % "".join(late_lines)
                if late_lines
                else "<p>Aucun retard enregistré.</p>"
            )

            # ==================================================
            # ABSENTS
            # ==================================================

            absent_members = meeting.attendance_ids.filtered(
                lambda attendance:
                    attendance.state == "absent"
            )

            absent_lines = []

            for attendance in absent_members:

                member_name = (
                    attendance.member_id.display_name
                    if attendance.member_id
                    else _("Membre non renseigné")
                )

                absent_lines.append(
                    "<li>%s</li>"
                    % member_name
                )

            absent_html = (
                "<ul>%s</ul>"
                % "".join(absent_lines)
                if absent_lines
                else (
                    "<p>"
                    "Aucune absence injustifiée enregistrée."
                    "</p>"
                )
            )

            # ==================================================
            # ABSENCES JUSTIFIÉES
            # ==================================================

            excused_members = meeting.attendance_ids.filtered(
                lambda attendance:
                    attendance.state == "excused"
            )

            excused_lines = []

            for attendance in excused_members:

                member_name = (
                    attendance.member_id.display_name
                    if attendance.member_id
                    else _("Membre non renseigné")
                )

                absence_reason = (
                    attendance.absence_reason
                    or _("Motif non précisé")
                )

                excused_lines.append(
                    (
                        "<li>"
                        "<strong>%s</strong>"
                        "<br/>"
                        "<span>"
                        "Motif : %s"
                        "</span>"
                        "</li>"
                    )
                    % (
                        member_name,
                        absence_reason,
                    )
                )

            excused_html = (
                "<ul>%s</ul>"
                % "".join(excused_lines)
                if excused_lines
                else (
                    "<p>"
                    "Aucune absence justifiée enregistrée."
                    "</p>"
                )
            )

            # ==================================================
            # SANCTIONS / INCIDENTS À INCLURE DANS LE PV
            # ==================================================

            penalties = meeting.penalty_ids.filtered(
                lambda penalty:
                    penalty.include_in_minutes
                    and penalty.state in (
                        "validated",
                        "executed",
                        "lifted",
                    )
            )

            penalty_html_lines = []

            severity_selection = dict(
                meeting.penalty_ids._fields[
                    "severity"
                ].selection
            )

            incident_selection = dict(
                meeting.penalty_ids._fields[
                    "incident_type"
                ].selection
            )

            penalty_type_selection = dict(
                meeting.penalty_ids._fields[
                    "penalty_type"
                ].selection
            )

            for index, penalty in enumerate(
                penalties,
                start=1,
            ):

                member_name = (
                    penalty.member_id.display_name
                    if penalty.member_id
                    else _("Membre non renseigné")
                )

                incident_label = incident_selection.get(
                    penalty.incident_type,
                    _("Incident non défini"),
                )

                severity_label = severity_selection.get(
                    penalty.severity,
                    _("Non définie"),
                )

                penalty_type_label = (
                    penalty_type_selection.get(
                        penalty.penalty_type,
                        _("Sanction non définie"),
                    )
                )

                incident_description = (
                    penalty.incident_description
                    or _("Aucune précision")
                )

                penalty_description = (
                    penalty.penalty_description
                    or _("Décision non précisée")
                )

                # ==============================================
                # INFORMATIONS COMPLÉMENTAIRES
                # ==============================================

                additional_information = []

                # ==============================================
                # SANCTION FINANCIÈRE
                # ==============================================

                if penalty.penalty_type == "fine":

                    formatted_amount = (
                        "{:,.0f}".format(
                            penalty.amount or 0.0
                        )
                        .replace(",", " ")
                    )

                    currency_name = (
                        penalty.currency_id.name
                        if penalty.currency_id
                        else ""
                    )

                    additional_information.append(
                        (
                            "<li>"
                            "<strong>"
                            "Montant de la sanction :"
                            "</strong> "
                            "%s %s"
                            "</li>"
                        )
                        % (
                            formatted_amount,
                            currency_name,
                        )
                    )

                # ==============================================
                # SUSPENSION
                # ==============================================

                if (
                    penalty.penalty_type == "suspension"
                    and penalty.suspension_days
                ):

                    additional_information.append(
                        (
                            "<li>"
                            "<strong>"
                            "Durée de suspension :"
                            "</strong> "
                            "%s jour(s)"
                            "</li>"
                        )
                        % penalty.suspension_days
                    )

                # ==============================================
                # ACTION CORRECTIVE
                # ==============================================

                if penalty.corrective_action_required:

                    corrective_action = (
                        penalty.corrective_action
                        or _("Action non précisée")
                    )

                    additional_information.append(
                        (
                            "<li>"
                            "<strong>"
                            "Action requise pour la levée :"
                            "</strong> "
                            "%s"
                            "</li>"
                        )
                        % corrective_action
                    )

                    if penalty.corrective_deadline:

                        deadline = fields.Date.to_date(
                            penalty.corrective_deadline
                        ).strftime("%d/%m/%Y")

                        additional_information.append(
                            (
                                "<li>"
                                "<strong>"
                                "Date limite :"
                                "</strong> "
                                "%s"
                                "</li>"
                            )
                            % deadline
                        )

                # ==============================================
                # MENTION SPÉCIFIQUE PV
                # ==============================================

                if penalty.minutes_note:

                    additional_information.append(
                        (
                            "<li>"
                            "<strong>"
                            "Mention au procès-verbal :"
                            "</strong> "
                            "%s"
                            "</li>"
                        )
                        % penalty.minutes_note
                    )

                additional_html = ""

                if additional_information:

                    additional_html = (
                        "<ul>%s</ul>"
                        % "".join(
                            additional_information
                        )
                    )

                # ==============================================
                # BLOC SANCTION
                # ==============================================

                penalty_html_lines.append(
                    (
                        "<div "
                        "style='"
                        "margin-bottom: 16px; "
                        "padding: 12px; "
                        "border-left: 4px solid #875A7B; "
                        "background-color: #f8f9fa;"
                        "'>"
                        "<p>"
                        "<strong>"
                        "%s. Membre concerné : %s"
                        "</strong>"
                        "</p>"

                        "<p>"
                        "<strong>Incident :</strong> %s"
                        "<br/>"
                        "<strong>Niveau de gravité :</strong> %s"
                        "</p>"

                        "<p>"
                        "<strong>Faits constatés :</strong>"
                        "<br/>"
                        "%s"
                        "</p>"

                        "<p>"
                        "<strong>Sanction décidée :</strong> %s"
                        "<br/>"
                        "<strong>Décision disciplinaire :</strong>"
                        "<br/>"
                        "%s"
                        "</p>"

                        "%s"

                        "</div>"
                    )
                    % (
                        index,
                        member_name,
                        incident_label,
                        severity_label,
                        incident_description,
                        penalty_type_label,
                        penalty_description,
                        additional_html,
                    )
                )

            penalties_html = (
                "".join(penalty_html_lines)
                if penalty_html_lines
                else (
                    "<p>"
                    "Aucun incident ou sanction disciplinaire "
                    "n'a été retenu pour le procès-verbal."
                    "</p>"
                )
            )

            # ==================================================
            # RÉSOLUTIONS
            # ==================================================

            resolution_lines = []

            for resolution in meeting.resolution_ids:

                resolution_name = (
                    resolution.name
                    or _("Résolution sans titre")
                )

                resolution_description = (
                    resolution.description
                    or _("Aucune description")
                )

                resolution_lines.append(
                    (
                        "<li>"
                        "<strong>%s</strong>"
                        "<br/>"
                        "%s"
                        "</li>"
                    )
                    % (
                        resolution_name,
                        resolution_description,
                    )
                )

            resolution_html = (
                "<ol>%s</ol>"
                % "".join(resolution_lines)
                if resolution_lines
                else (
                    "<p>"
                    "Aucune résolution enregistrée."
                    "</p>"
                )
            )

            # ==================================================
            # GÉNÉRATION DU PROCÈS-VERBAL
            # ==================================================

            minutes_content = """
                <div>

                    <h2 style="text-align: center;">
                        PROCÈS-VERBAL DE RÉUNION
                    </h2>

                    <p>
                        La séance s'est tenue le
                        <strong>%s</strong>,
                        au lieu suivant :
                        <strong>%s</strong>.
                    </p>

                    <h3>1. Ouverture de la séance</h3>

                    <p>
                        La séance a été ouverte à
                        <strong>%s</strong>.
                    </p>

                    <p>
                        [Compléter les circonstances d'ouverture
                        de la séance et identifier, si nécessaire,
                        la personne ayant présidé la réunion.]
                    </p>

                    <h3>2. Situation des présences</h3>

                    <h4>2.1 Membres présents</h4>

                    %s

                    <h4>2.2 Membres en retard</h4>

                    %s

                    <h4>2.3 Membres absents</h4>

                    %s

                    <h4>2.4 Absences justifiées</h4>

                    %s

                    <h3>3. Déroulement de la séance</h3>

                    <p>
                        [Décrire les différents points abordés,
                        les interventions importantes et les
                        échanges ayant marqué la séance.]
                    </p>

                    <h3>
                        4. Incidents et décisions disciplinaires
                    </h3>

                    %s

                    <p>
                        Les sanctions validées ci-dessus restent
                        soumises à un suivi administratif après
                        la clôture de la présente réunion jusqu'à
                        leur exécution, leur régularisation ou
                        leur levée officielle.
                    </p>

                    <h3>5. Résolutions et décisions</h3>

                    %s

                    <h3>6. Questions diverses</h3>

                    <p>
                        [Renseigner les questions diverses
                        examinées au cours de la séance.]
                    </p>

                    <h3>7. Clôture de la séance</h3>

                    <p>
                        Aucun autre point n'étant inscrit
                        à l'ordre du jour, la séance a été
                        clôturée à
                        <strong>%s</strong>.
                    </p>

                    <p>
                        Le présent procès-verbal retrace les
                        principaux faits, décisions et résolutions
                        intervenus au cours de la séance.
                    </p>

                </div>
            """ % (
                meeting_date,
                meeting.location or _("Lieu non précisé"),
                start_time,
                present_html,
                late_html,
                absent_html,
                excused_html,
                penalties_html,
                resolution_html,
                end_time,
            )

            # ==================================================
            # ENREGISTREMENT
            # ==================================================

            meeting.write(
                {
                    "minutes": minutes_content,
                    "minutes_prepared": True,
                    "minutes_preparation_date": (
                        fields.Datetime.now()
                    ),
                    "minutes_prepared_by": (
                        self.env.user.id
                    ),
                }
            )

            meeting.message_post(
                body=_(
                    "La trame du procès-verbal a été préparée "
                    "par %s.<br/>"
                    "Les sanctions validées et marquées pour "
                    "inclusion au procès-verbal ont été intégrées."
                )
                % self.env.user.display_name
            )

        return True
    

    @api.depends("penalty_ids")
    def _compute_penalty_count(self):

        for record in self:

            record.penalty_count = len(
                record.penalty_ids
            )

    

    minutes_penalty_summary = fields.Html(
        string="Incidents et sanctions du procès-verbal",
        compute="_compute_minutes_penalty_summary",
    )

    @api.depends(
        "penalty_ids",
        "penalty_ids.member_id",
        "penalty_ids.incident_type",
        "penalty_ids.incident_description",
        "penalty_ids.penalty_type",
        "penalty_ids.penalty_description",
        "penalty_ids.minutes_note",
        "penalty_ids.include_in_minutes",
        "penalty_ids.state",
    )
    def _compute_minutes_penalty_summary(self):

        for meeting in self:

            lines = []

            penalties = meeting.penalty_ids.filtered(
                lambda penalty:
                    penalty.include_in_minutes
                    and penalty.state != "cancelled"
            )

            for penalty in penalties:

                member_name = (
                    penalty.member_id.display_name
                    or ""
                )

                incident_label = dict(
                    penalty._fields[
                        "incident_type"
                    ].selection
                ).get(
                    penalty.incident_type,
                    ""
                )

                penalty_label = dict(
                    penalty._fields[
                        "penalty_type"
                    ].selection
                ).get(
                    penalty.penalty_type,
                    ""
                )

                if penalty.minutes_note:

                    content = penalty.minutes_note

                else:

                    content = (
                        "<p>"
                        "<strong>%s</strong> — %s"
                        "<br/>"
                        "%s"
                        "<br/>"
                        "<strong>Décision :</strong> %s — %s"
                        "</p>"
                    ) % (
                        member_name,
                        incident_label,
                        penalty.incident_description or "",
                        penalty_label,
                        penalty.penalty_description or "",
                    )

                lines.append(content)

            meeting.minutes_penalty_summary = (
                "".join(lines)
                if lines
                else
                "<p>Aucun incident disciplinaire enregistré.</p>"
            )

    # ==========================================================
    # CRÉATION
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:

            if (
                vals.get("committee_id")
                and vals.get("committee_mode", "official") == "official"
            ):
                committee = self.env["association.committee"].browse(
                    vals["committee_id"]
                )
                chairperson, secretary = self._get_official_responsibles(
                    committee
                )
                vals["chairperson_id"] = chairperson.id
                vals["secretary_id"] = secretary.id

            if vals.get("name", _("Nouveau")) == _("Nouveau"):

                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.meeting"
                    )
                    or _("Nouveau")
                )

        meetings = super().create(vals_list)
        Session = self.env["association.meeting.subscription.session"]
        for meeting in meetings.filtered("subscription_id"):
            period = meeting.subscription_id.current_period_id
            if period:
                meeting.subscription_period_id = period.id
                Session.create({
                    "meeting_id": meeting.id,
                    "subscription_id": meeting.subscription_id.id,
                    "period_id": period.id,
                })
            meeting._sync_subscription_attendances()
        meetings._sync_committee_attendances()
        meetings._sync_special_responsible_attendances()
        return meetings

    # ==========================================================
    # STATISTIQUES DE PRÉSENCE
    # ==========================================================

    @api.depends(
        "attendance_ids",
        "attendance_ids.invited",
        "attendance_ids.state",
    )
    def _compute_attendance_statistics(self):

        for record in self:

            attendances = record.attendance_ids

            invited = attendances.filtered(
                lambda line: line.invited
            )

            record.invited_count = len(invited)

            record.pending_count = len(
                invited.filtered(
                    lambda line: line.state == "pending"
                )
            )

            record.present_count = len(
                invited.filtered(
                    lambda line: line.state == "present"
                )
            )

            record.late_count = len(
                invited.filtered(
                    lambda line: line.state == "late"
                )
            )

            record.absent_count = len(
                invited.filtered(
                    lambda line: line.state == "absent"
                )
            )

            record.excused_count = len(
                invited.filtered(
                    lambda line: line.state == "excused"
                )
            )

            physically_present = (
                record.present_count
                + record.late_count
            )

            if record.invited_count:

                record.attendance_percentage = (
                    physically_present
                    / record.invited_count
                ) * 100

            else:

                record.attendance_percentage = 0.0

    
    
    # ==========================================================
    # QUORUM
    # ==========================================================

    @api.depends(
        "quorum_required",
        "quorum_percentage",
        "invited_count",
        "present_count",
        "late_count",
    )
    def _compute_quorum(self):

        for record in self:

            if not record.quorum_required:

                record.quorum_count = 0
                record.quorum_reached = True
                continue

            if not record.invited_count:

                record.quorum_count = 0
                record.quorum_reached = False
                continue

            required = (
                record.invited_count
                * record.quorum_percentage
                / 100
            )

            record.quorum_count = int(required)

            if required > record.quorum_count:
                record.quorum_count += 1

            physically_present = (
                record.present_count
                + record.late_count
            )

            record.quorum_reached = (
                physically_present
                >= record.quorum_count
            )

    # ==========================================================
    # NOMBRE DE RÉSOLUTIONS
    # ==========================================================

    @api.depends("resolution_ids")
    def _compute_resolution_count(self):

        for record in self:
            record.resolution_count = len(
                record.resolution_ids
            )

    # ==========================================================
    # ACTION - GÉNÉRER LA LISTE D'APPEL
    # ==========================================================

    def action_generate_attendances(self):

        Attendance = self.env[
            "association.attendance"
        ]

        for record in self:

            # ======================================================
            # CONTRÔLE DE L'ÉTAT
            # ======================================================

            if record.state == "closed":

                raise UserError(
                    _(
                        "Impossible de modifier la liste d'appel "
                        "d'une réunion clôturée."
                    )
                )

            # ======================================================
            # CONTRÔLE DE LA COTISATION
            # ======================================================

            if not record.subscription_id:

                raise ValidationError(
                    _(
                        "Veuillez sélectionner une cotisation "
                        "avant de générer la liste d'appel."
                    )
                )

            # ======================================================
            # MEMBRES DE LA COTISATION
            # ======================================================

            subscription_lines = (
                record.subscription_id.line_ids
            )

            if not subscription_lines:

                raise ValidationError(
                    _(
                        "La cotisation %(subscription)s "
                        "ne contient aucun membre participant."
                    )
                    % {
                        "subscription":
                            record.subscription_id.display_name,
                    }
                )

            members = (
                subscription_lines
                .mapped("member_id")
                .filtered(
                    lambda member: (
                        member
                        and member.active
                        and member.state == "active"
                        and member.company_id
                        == record.company_id
                    )
                )
            )

            if not members:

                raise ValidationError(
                    _(
                        "Aucun membre actif de la cotisation "
                        "%(subscription)s n'a été trouvé."
                    )
                    % {
                        "subscription":
                            record.subscription_id.display_name,
                    }
                )

            # ======================================================
            # MEMBRES DÉJÀ PRÉSENTS
            # ======================================================

            existing_member_ids = set(
                record.attendance_ids
                .mapped("member_id")
                .ids
            )

            # ======================================================
            # PRÉPARATION DES NOUVELLES LIGNES
            # ======================================================

            values_list = []

            sequence = (
                max(
                    record.attendance_ids.mapped(
                        "sequence"
                    ),
                    default=0,
                )
                + 1
            )

            for member in members:

                if member.id in existing_member_ids:
                    continue

                values_list.append({
                    "meeting_id":
                        record.id,

                    "member_id":
                        member.id,

                    "sequence":
                        sequence,

                    "invited":
                        True,

                    "state":
                        "pending",
                })

                sequence += 1

            # ======================================================
            # AUCUN NOUVEAU MEMBRE
            # ======================================================

            if not values_list:

                raise UserError(
                    _(
                        "Tous les membres de la cotisation "
                        "%(subscription)s sont déjà présents "
                        "dans la liste d'appel."
                    )
                    % {
                        "subscription":
                            record.subscription_id.display_name,
                    }
                )

            # ======================================================
            # CRÉATION
            # ======================================================

            Attendance.create(
                values_list
            )

            # ======================================================
            # CHATTER
            # ======================================================

            record.message_post(
                body=_(
                    "%(count)s membre(s) de la cotisation "
                    "%(subscription)s ont été ajoutés "
                    "à la liste d'appel."
                )
                % {
                    "count":
                        len(values_list),

                    "subscription":
                        record.subscription_id.display_name,
                }
            )

        return True
    
    # ==========================================================
    # CONVOQUER
    # ==========================================================

    def action_convocate(self):

        for record in self:

            if not record.attendance_ids:

                raise UserError(
                    _(
                        "Vous devez générer ou ajouter les membres "
                        "avant de convoquer la réunion."
                    )
                )

            if not record.agenda:

                raise UserError(
                    _(
                        "Vous devez renseigner l'ordre du jour "
                        "avant de convoquer la réunion."
                    )
                )

            record.write(
                {
                    "state": "convoked",
                    "convocation_date": (
                        record.convocation_date
                        or fields.Date.context_today(record)
                    ),
                }
            )

        return True

    # ==========================================================
    # NORMALISER UNE HEURE POUR LA SÉLECTION
    # ==========================================================

    def _normalize_selection_time(self, hour, minute):

        minute = int(minute)

        # Arrondi inférieur au pas de 5 minutes
        normalized_minute = (minute // 5) * 5

        return "%02d:%02d" % (
            int(hour),
            normalized_minute,
        )

    # ==========================================================
    # ACTION - DÉMARRER LA SÉANCE
    # ==========================================================

    def action_start_meeting(self):

        for meeting in self:

            # ==================================================
            # CONTRÔLE DE L'ÉTAT
            # ==================================================

            if meeting.state == "in_progress":

                raise UserError(
                    _("La séance est déjà en cours.")
                )

            if meeting.state == "closed":

                raise UserError(
                    _(
                        "Impossible de démarrer la séance.\n\n"
                        "Cette réunion est déjà clôturée."
                    )
                )

            if meeting.state == "cancelled":

                raise UserError(
                    _(
                        "Impossible de démarrer la séance.\n\n"
                        "Cette réunion est annulée."
                    )
                )

            # ==================================================
            # HEURE LOCALE COURANTE
            # ==================================================

            current_datetime = fields.Datetime.context_timestamp(
                meeting,
                fields.Datetime.now(),
            )

            actual_start_time = "%02d:%02d" % (
                current_datetime.hour,
                current_datetime.minute,
            )

            # ==================================================
            # DÉMARRER LA SÉANCE
            # ==================================================

            meeting.write(
                {
                    "state": "in_progress",
                    "actual_start_time": actual_start_time,
                }
            )

            # ==================================================
            # CHATTER
            # ==================================================

            meeting.message_post(
                body=_(
                    "La séance a été démarrée à %s."
                )
                % actual_start_time
            )

        return True
    
    # ==========================================================
    # ACTION - CLÔTURER LA RÉUNION
    # ==========================================================

    def action_close_meeting(self):

        for meeting in self:

            # ==================================================
            # CONTRÔLE DU STATUT
            # ==================================================

            if meeting.state != "in_progress":

                raise UserError(
                    _(
                        "Seule une réunion en cours "
                        "peut être clôturée."
                    )
                )

            # ==================================================
            # CONTRÔLE DE LA LISTE D'APPEL
            # ==================================================

            pending_attendances = (
                meeting.attendance_ids.filtered(
                    lambda attendance:
                        attendance.state == "pending"
                )
            )

            if pending_attendances:

                raise ValidationError(
                    _(
                        "%(count)s membre(s) n'ont pas encore "
                        "été pointés.\n\n"
                        "Veuillez terminer la liste d'appel "
                        "avant de clôturer la réunion."
                    )
                    % {
                        "count": len(pending_attendances),
                    }
                )

            if (
                meeting.pot_collected_amount > 0
                and meeting.pot_settlement_state != "settled"
            ):
                raise ValidationError(
                    _(
                        "La caisse temporaire de cotisation n'est pas "
                        "encore soldée. Remettez les attributions puis "
                        "utilisez « Solder et verser le reliquat » avant "
                        "de clôturer la réunion."
                    )
                )

            # ==================================================
            # CONTRÔLE DU PROCÈS-VERBAL
            # ==================================================

            if not meeting.minutes_prepared:

                raise ValidationError(
                    _(
                        "Le procès-verbal n'a pas encore été préparé.\n\n"
                        "Veuillez préparer le procès-verbal "
                        "avant de clôturer la réunion."
                    )
                )

            # ==================================================
            # HEURE EFFECTIVE DE CLÔTURE
            # ==================================================

            if not meeting.actual_end_time:

                current_datetime = (
                    fields.Datetime.context_timestamp(
                        meeting,
                        fields.Datetime.now(),
                    )
                )

                current_minutes = (
                    current_datetime.hour * 60
                    + current_datetime.minute
                )

                available_times = dict(
                    meeting._fields[
                        "actual_end_time"
                    ].selection(meeting)
                )

                selected_time = False
                minimum_difference = None

                for time_value in available_times:

                    try:

                        hour, minute = map(
                            int,
                            time_value.split(":"),
                        )

                    except (
                        ValueError,
                        AttributeError,
                    ):

                        continue

                    time_minutes = (
                        hour * 60
                        + minute
                    )

                    difference = abs(
                        time_minutes
                        - current_minutes
                    )

                    if (
                        minimum_difference is None
                        or difference < minimum_difference
                    ):

                        minimum_difference = difference
                        selected_time = time_value

                if selected_time:

                    meeting.actual_end_time = (
                        selected_time
                    )

            # ==================================================
            # VERROUILLAGE DE LA RÉUNION
            # ==================================================

            meeting.write(
                {
                    "state": "closed",
                }
            )

            # ==================================================
            # MESSAGE
            # ==================================================

            meeting.message_post(
                body=_(
                    "La réunion a été clôturée et verrouillée."
                )
            )

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
    

    # ==========================================================
    # WRITE - VERROUILLAGE DES RÉUNIONS TERMINÉES
    # ==========================================================

    def write(self, vals):

        vals = dict(vals)
        committee_mode = vals.get(
            "committee_mode",
            self[:1].committee_mode if self else "official",
        )
        if vals.get("committee_id") and committee_mode == "official":
            committee = self.env["association.committee"].browse(
                vals["committee_id"]
            )
            chairperson, secretary = self._get_official_responsibles(committee)
            vals["chairperson_id"] = chairperson.id
            vals["secretary_id"] = secretary.id
        elif (
            len(self) == 1
            and committee_mode == "official"
            and self.committee_id
            and (
                not self.chairperson_id
                or not self.secretary_id
                or "state" in vals
            )
        ):
            chairperson, secretary = self._get_official_responsibles(
                self.committee_id
            )
            vals["chairperson_id"] = chairperson.id
            vals["secretary_id"] = secretary.id
        if vals.get("subscription_id"):
            subscription = self.env["association.subscription"].browse(
                vals["subscription_id"]
            )
            sessions_by_meeting = {
                meeting.id: meeting._get_subscription_session_for_subscription(
                    subscription
                )
                for meeting in self
            }
            periods = {
                (sessions_by_meeting[meeting.id].period_id.id
                 if sessions_by_meeting[meeting.id]
                 else subscription.current_period_id.id)
                for meeting in self
                if (sessions_by_meeting[meeting.id] or subscription.current_period_id)
            }
            # A multi-record write cannot safely assign several session cycles
            # in one call.  Applying it record by record preserves the cycle
            # selected in each meeting's Sessions de cotisation tab.
            if len(periods) > 1:
                return all(
                    meeting.write(vals)
                    for meeting in self
                )
            if periods:
                vals["subscription_period_id"] = periods.pop()

        protected_fields = {
            "meeting_date",
            "start_time",
            "end_time",
            "actual_end_time",
            "meeting_type",
            "location",
            "president_id",
            "secretary_id",
            "subscription_id",
            "subscription_period_id",
            "attendance_ids",
            "collection_ids",
        }

        closed_meetings = self.filtered(
            lambda meeting:
                meeting.state == "closed"
        )

        if (
            closed_meetings
            and protected_fields.intersection(vals)
        ):

            raise UserError(
                _(
                    "Une réunion terminée est verrouillée.\n\n"
                    "Ses informations ne peuvent plus "
                    "être modifiées."
                )
            )

        result = super().write(vals)

        if vals.get("subscription_id"):
            Session = self.env["association.meeting.subscription.session"]
            for meeting in self:
                session = meeting._get_subscription_session_for_subscription(
                    meeting.subscription_id
                )
                period = session.period_id if session else meeting.subscription_period_id
                if not period:
                    continue
                session = Session.search([
                    ("meeting_id", "=", meeting.id),
                    ("subscription_id", "=", meeting.subscription_id.id),
                    ("period_id", "=", period.id),
                ], limit=1)
                if not session:
                    Session.create({
                        "meeting_id": meeting.id,
                        "subscription_id": meeting.subscription_id.id,
                        "period_id": period.id,
                    })

            self._sync_subscription_attendances()

        if "committee_id" in vals or "committee_mode" in vals:
            self._sync_committee_attendances()

        if {
            "committee_mode", "chairperson_id", "secretary_id",
            "special_treasurer_id", "special_censor_id",
        }.intersection(vals):
            self._sync_special_responsible_attendances()

        return result
    
    
    # ==========================================================
    # APPROUVER LE PROCÈS-VERBAL
    # ==========================================================

    def action_approve_minutes(self):
        """Freeze the existing minutes as-is, without workflow prerequisites."""
        self.write({
            "minutes_approved": True,
            "minutes_approval_date": fields.Datetime.now(),
        })

        return True
    
    # ==========================================================
    # ANNULER
    # ==========================================================

    def action_cancel(self):

        for record in self:

            if record.state == "closed":

                raise UserError(
                    _(
                        "Une réunion clôturée "
                        "ne peut pas être annulée."
                    )
                )

            record.state = "cancelled"

        return True

    # ==========================================================
    # REMETTRE EN BROUILLON
    # ==========================================================

    def action_reset_draft(self):

        for record in self:

            if record.state != "cancelled":

                raise UserError(
                    _(
                        "Seule une réunion annulée "
                        "peut être remise en brouillon."
                    )
                )

            record.state = "draft"

        return True

    # ==========================================================
    # IMPRESSION DU PROCÈS-VERBAL
    # ==========================================================

    def action_print_minutes(self):

        self.ensure_one()

        return self.env.ref(
            "primetech_association.action_report_meeting_minutes"
        ).report_action(self)

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains("quorum_percentage")
    def _check_quorum_percentage(self):

        for record in self:

            if not 0 < record.quorum_percentage <= 100:

                raise ValidationError(
                    _(
                        "Le pourcentage de quorum doit être "
                        "supérieur à 0 et inférieur ou égal à 100."
                    )
                )

    @api.constrains(
        "chairperson_id",
        "secretary_id",
        "company_id",
    )
    def _check_responsible_company(self):

        for record in self:

            members = (
                record.chairperson_id
                | record.secretary_id
            )

            for member in members:

                if member.company_id != record.company_id:

                    raise ValidationError(
                        _(
                            "Les responsables de séance "
                            "doivent appartenir à la même Filiale "
                            "que la réunion."
                        )
                    )
                
    # ==========================================================
    # IMPRIMER LE PROCÈS-VERBAL
    # ==========================================================

    def action_print_minutes(self):

        self.ensure_one()

        if not self.minutes_prepared:

            raise UserError(
                _(
                    "Impossible d'imprimer le procès-verbal.\n\n"
                    "Le procès-verbal n'a pas encore été préparé.\n\n"
                    "Utilisez d'abord l'action "
                    "« Préparer le procès-verbal »."
                )
            )

        if not self.minutes:

            raise UserError(
                _(
                    "Impossible d'imprimer le procès-verbal.\n\n"
                    "Le contenu du procès-verbal est vide."
                )
            )

        return self.env.ref(
            "primetech_association.action_report_meeting_minutes"
        ).report_action(self)

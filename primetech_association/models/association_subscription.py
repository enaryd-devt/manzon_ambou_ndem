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

from datetime import timedelta

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationSubscription(models.Model):
    _name = "association.subscription"
    _description = "Cotisation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

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
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Devise",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    color = fields.Integer(
        string="Couleur",
    )

    # ==========================================================
    # IDENTIFICATION
    # ==========================================================

    name = fields.Char(
        string="Intitulé de la cotisation",
        required=True,
        tracking=True,
        translate=True,
        help="Exemple : Cotisation journalière 10 000 FCFA",
    )

    code = fields.Char(
        string="Référence",
        copy=False,
        readonly=True,
        default=lambda self: _("Nouveau"),
        tracking=True,
        index=True,
    )

    description = fields.Text(
        string="Description",
        translate=True,
    )

    # ==========================================================
    # PARAMÉTRAGE DE LA COTISATION
    # ==========================================================

    subscription_type = fields.Selection(
        selection=[
            ("registration", "Droit d'adhésion"),
            ("daily", "Cotisation journalière"),
            ("weekly", "Cotisation hebdomadaire"),
            ("biweekly", "Cotisation bihebdomadaire"),
            ("monthly", "Cotisation mensuelle"),
            ("bimonthly", "Cotisation bimensuelle"),
            ("quarterly", "Cotisation trimestrielle"),
            ("annual", "Cotisation annuelle"),
            ("special", "Cotisation spéciale"),
        ],
        string="Type de cotisation",
        required=True,
        default="monthly",
        tracking=True,
    )

    date = fields.Date(
        string="Date de création",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
        index=True,
    )

    period_start_date = fields.Date(
        string="Date de début",
        tracking=True,
    )

    period_end_date = fields.Date(
        string="Date de fin",
        tracking=True,
    )

    due_date = fields.Date(
        string="Première échéance",
        tracking=True,
        index=True,
    )

    due_timing = fields.Selection(
        selection=[
            ("period_start", "Au début de chaque période"),
            ("period_end", "À la fin de chaque période"),
            ("custom_days", "Nombre de jours après le début"),
        ],
        string="Règle d'échéance",
        required=True,
        default="period_end",
        tracking=True,
        help=(
            "La période est calculée selon le type de cotisation "
            "(journalière, hebdomadaire, mensuelle, etc.), puis cette "
            "règle détermine sa date d'échéance."
        ),
    )

    due_days_after_start = fields.Integer(
        string="Jours après le début",
        default=0,
        tracking=True,
    )

    amount = fields.Monetary(
        string="Montant par membre",
        currency_field="currency_id",
        required=True,
        default=0.0,
        tracking=True,
    )

    # ==========================================================
    # STATUT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("confirmed", "Confirmée"),
            ("running", "En cours"),
            ("closed", "Clôturée"),
            ("cancelled", "Annulée"),
        ],
        string="Statut",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # ==========================================================
    # MEMBRES PARTICIPANTS
    # ==========================================================

    line_ids = fields.One2many(
        comodel_name="association.subscription.line",
        inverse_name="subscription_id",
        string="Membres participants",
        copy=True,
    )

    # ==========================================================
    # CYCLES
    # ==========================================================

    period_ids = fields.One2many(
        comodel_name="association.subscription.period",
        inverse_name="subscription_id",
        string="Historique des cycles",
        copy=False,
    )

    period_count = fields.Integer(
        string="Nombre de cycles",
        compute="_compute_period_statistics",
    )

    current_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle courant",
        compute="_compute_period_statistics",
    )

    # ==========================================================
    # STATISTIQUES
    # ==========================================================

    line_count = fields.Integer(
        string="Nombre de membres",
        compute="_compute_statistics",
    )

    paid_member_count = fields.Integer(
        string="Membres à jour",
        compute="_compute_statistics",
    )

    partial_member_count = fields.Integer(
        string="Paiements partiels",
        compute="_compute_statistics",
    )

    unpaid_member_count = fields.Integer(
        string="Membres non payés",
        compute="_compute_statistics",
    )

    total_amount_due = fields.Monetary(
        string="Montant total attendu",
        currency_field="currency_id",
        compute="_compute_statistics",
    )

    total_amount_paid = fields.Monetary(
        string="Montant total payé",
        currency_field="currency_id",
        compute="_compute_statistics",
    )

    total_balance = fields.Monetary(
        string="Reste total à payer",
        currency_field="currency_id",
        compute="_compute_statistics",
    )

    progress_percent = fields.Float(
        string="Taux de recouvrement",
        compute="_compute_statistics",
    )

    payment_count = fields.Integer(
        string="Nombre de paiements",
        compute="_compute_payment_count",
    )

    # ==========================================================
    # GESTION DES PÉNALITÉS
    # ==========================================================

    penalty_enabled = fields.Boolean(
        string="Activer les pénalités",
        default=False,
    )

    penalty_grace_days = fields.Integer(
        string="Délai de grâce (jours)",
        default=0,
        help=(
            "Nombre de jours accordés après l'échéance du cycle. "
            "À 0, la pénalité est immédiate. À 2, elle est appliquée "
            "le jour où le compteur calculé depuis l'échéance atteint 0."
        ),
    )

    penalty_type = fields.Selection(
        selection=[
            ("fixed", "Montant fixe"),
            ("percentage", "Pourcentage"),
        ],
        string="Type de pénalité",
        default="fixed",
    )

    penalty_amount = fields.Monetary(
        string="Montant de la pénalité",
        currency_field="currency_id",
        default=0.0,
    )

    penalty_rate = fields.Float(
        string="Taux de pénalité (%)",
        default=0.0,
    )

    penalty_distribution = fields.Selection(
        selection=[
            ("equitable", "Équitable (pénalité complète)"),
            ("prorata", "Au prorata du montant restant dû"),
        ],
        string="Répartition de la pénalité",
        default="equitable",
        required=True,
        help=(
            "En mode équitable, tout membre encore redevable reçoit la "
            "pénalité complète. Au prorata, la pénalité est réduite "
            "selon la part de cotisation restant à payer."
        ),
    )

    penalty_account_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte dédié aux pénalités",
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        tracking=True,
        copy=False,
        help="Compte financier qui reçoit uniquement les suppléments encaissés au titre des pénalités.",
    )

    # ==========================================================
    # COMPTE DE VERSEMENT
    # ==========================================================

    receipt_account_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte de versement",
        domain="["
            "('company_id', '=', company_id), "
            "('active', '=', True)"
            "]",
        tracking=True,
        copy=False,
        help=(
            "Compte financier dans lequel seront versés "
            "les encaissements de cette cotisation."
        ),
    )

    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # CONTRÔLE DES PÉNALITÉS
    # ==========================================================

    @api.constrains(
        "penalty_grace_days",
        "penalty_amount",
        "penalty_rate",
    )
    def _check_penalty_values(self):

        for record in self:

            if record.penalty_grace_days < 0:
                raise ValidationError(
                    _(
                        "Le délai de grâce ne peut pas "
                        "être négatif."
                    )
                )

            if record.penalty_amount < 0:
                raise ValidationError(
                    _(
                        "Le montant de la pénalité ne peut pas "
                        "être négatif."
                    )
                )

            if record.penalty_rate < 0:
                raise ValidationError(
                    _(
                        "Le taux de pénalité ne peut pas "
                        "être négatif."
                    )
                )

    def _refresh_penalty_lines(self):
        """Synchronize member rows immediately with the penalty definition."""
        today = fields.Date.context_today(self)
        for subscription in self:
            lines = subscription.line_ids
            # Disabling the rule cancels the penalty debt still displayed on
            # every member row.  Confirmed payments are left untouched; only
            # the amount still due is recalculated from the base contribution.
            if not subscription.penalty_enabled:
                lines.write({
                    "penalty_amount": 0.0,
                    "penalty_applied": False,
                    "penalty_date": False,
                    "penalty_reason": False,
                })
                lines._compute_penalty_deadline()
                lines._compute_current_cycle_payment()
                periods = subscription.period_ids.filtered(
                    lambda period: period.state == "running"
                )
                if periods:
                    self.env["association.subscription.penalty.recap"]._sync_for_lines_period(
                        lines, periods
                    )
                    periods._apply_late_penalty()
                continue

            # An applied penalty is a locked debt: later configuration
            # changes must never rewrite the amount owed by the member.
            configurable_lines = lines.filtered(lambda line: not line.penalty_applied)
            configurable_lines.write({
                "penalty_amount": 0.0,
                "penalty_applied": False,
                "penalty_date": False,
                "penalty_reason": False,
            })
            configurable_lines._compute_penalty_deadline()
            # Recompute the base balance without the previous penalty before
            # deciding whether each member is paid, partial or still due.
            configurable_lines._compute_current_cycle_payment()
            if not subscription.penalty_enabled:
                continue
            due_lines = configurable_lines.filtered(
                lambda line: line.payment_state != "paid"
                and line.penalty_deadline
                and (
                    subscription.penalty_grace_days == 0
                    or line.penalty_deadline <= today
                )
            )
            due_lines._apply_late_penalty(
                force=subscription.penalty_grace_days == 0
            )
            lines._compute_penalty_grace_days_remaining()
        return True

    def _calculate_penalty_amount(self, outstanding):
        """Return the amount to lock for an unpaid base balance."""
        self.ensure_one()
        base_amount = self.amount or 0.0
        outstanding = min(max(outstanding or 0.0, 0.0), base_amount)
        if not base_amount or not outstanding:
            return 0.0

        ratio = (
            outstanding / base_amount
            if self.penalty_distribution == "prorata"
            else 1.0
        )
        if self.penalty_type == "fixed":
            return (self.penalty_amount or 0.0) * ratio
        return base_amount * (self.penalty_rate or 0.0) / 100.0 * ratio

    def action_lock_due_penalties(self):
        """Lock penalties whose grace deadline has been reached."""
        today = fields.Date.context_today(self)
        locked_count = 0
        for subscription in self:
            if not subscription.penalty_enabled:
                raise UserError(_(
                    "Activez les pénalités avant de lancer leur verrouillage."
                ))
            lines = subscription.line_ids.filtered(
                lambda line: not line.penalty_applied
                and line.payment_state != "paid"
                and line.penalty_deadline
                and line.penalty_deadline <= today
            )
            lines._apply_late_penalty()
            locked_count += len(lines.filtered("penalty_applied"))
            periods = lines.mapped("subscription_id.current_period_id").exists()
            if periods:
                periods._apply_late_penalty()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Pénalités verrouillées"),
                "message": _("%(count)s pénalité(s) ont été verrouillées.")
                % {"count": locked_count},
                "type": "success" if locked_count else "warning",
                "sticky": False,
            },
        }

    @api.onchange(
        "penalty_enabled",
        "penalty_grace_days",
        "penalty_type",
        "penalty_amount",
        "penalty_rate",
        "penalty_distribution",
    )
    def _onchange_penalty_configuration(self):
        """Refresh the embedded member table before the form is saved."""
        today = fields.Date.context_today(self)
        for subscription in self:
            for line in subscription.line_ids:
                if not subscription.penalty_enabled:
                    line.penalty_amount = 0.0
                    line.penalty_applied = False
                    line.penalty_date = False
                    line.penalty_reason = False
                    line._compute_penalty_deadline()
                    line._compute_current_cycle_payment()
                    line._compute_penalty_grace_days_remaining()
                    continue
                # Once applied, the penalty is part of the member's locked
                # debt and must not change with subsequent form edits.
                if line.penalty_applied:
                    continue
                line.penalty_amount = 0.0
                line.penalty_applied = False
                line.penalty_date = False
                line.penalty_reason = False
                line._compute_penalty_deadline()
                line._compute_current_cycle_payment()
                is_due = (
                    subscription.penalty_enabled
                    and line.payment_state != "paid"
                    and line.penalty_deadline
                    and (
                        subscription.penalty_grace_days == 0
                        or line.penalty_deadline <= today
                    )
                )
                if is_due:
                    line.penalty_amount = subscription._calculate_penalty_amount(
                        line.balance
                    )
                    line.penalty_applied = line.penalty_amount > 0
                    line.penalty_date = today if line.penalty_applied else False
                line._compute_current_cycle_payment()
                line._compute_penalty_grace_days_remaining()

    def write(self, vals):
        penalty_fields = {
            "penalty_enabled",
            "penalty_grace_days",
            "penalty_type",
            "penalty_amount",
            "penalty_rate",
            "penalty_distribution",
        }
        result = super().write(vals)
        if penalty_fields.intersection(vals):
            self._refresh_penalty_lines()
        return result

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_subscription_code_company_unique",
            "unique(code, company_id)",
            "La référence de la cotisation doit être unique par société.",
        ),
        (
            "association_subscription_amount_positive",
            "CHECK(amount >= 0)",
            "Le montant de la cotisation ne peut pas être négatif.",
        ),
    ]

    # ==========================================================
    # CALCUL DES CYCLES
    # ==========================================================

    @api.depends(
        "period_ids",
        "period_ids.state",
        "period_ids.sequence",
    )
    def _compute_period_statistics(self):

        for subscription in self:

            periods = subscription.period_ids

            subscription.period_count = len(periods)

            running_period = periods.filtered(
                lambda period:
                    period.state == "running"
            )

            if running_period:

                subscription.current_period_id = (
                    running_period.sorted(
                        key=lambda period:
                            (
                                period.sequence,
                                period.id,
                            ),
                        reverse=True,
                    )[0]
                )

            else:

                subscription.current_period_id = False
    # ==========================================================
    # CALCUL DES STATISTIQUES
    # ==========================================================

    @api.depends(
        "line_ids",
        "line_ids.amount_due",
        "line_ids.amount_paid",
        "line_ids.balance",
        "line_ids.payment_state",
    )
    def _compute_statistics(self):
        for record in self:
            lines = record.line_ids

            record.line_count = len(lines)

            record.paid_member_count = len(
                lines.filtered(
                    lambda line: line.payment_state == "paid"
                )
            )

            record.partial_member_count = len(
                lines.filtered(
                    lambda line: line.payment_state == "partial"
                )
            )

            record.unpaid_member_count = len(
                lines.filtered(
                    lambda line: line.payment_state == "not_paid"
                )
            )

            record.total_amount_due = sum(
                lines.mapped("amount_due")
            )

            record.total_amount_paid = sum(
                lines.mapped("amount_paid")
            )

            record.total_balance = sum(
                lines.mapped("balance")
            )

            if record.total_amount_due > 0:
                record.progress_percent = (
                    record.total_amount_paid
                    / record.total_amount_due
                ) * 100
            else:
                record.progress_percent = 0.0

    # ==========================================================
    # NOMBRE DE PAIEMENTS
    # ==========================================================

    @api.depends(
        "line_ids.payment_line_ids.payment_id",
    )
    def _compute_payment_count(self):
        for record in self:
            payments = record.line_ids.mapped(
                "payment_line_ids.payment_id"
            )

            record.payment_count = len(payments)

    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", _("Nouveau")) == _("Nouveau"):
                vals["code"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.subscription"
                    )
                    or _("Nouveau")
                )

        return super().create(vals_list)

    # ==========================================================
    # CONTRAINTES
    # ==========================================================

    @api.constrains(
        "period_start_date",
        "period_end_date",
    )
    def _check_subscription_period(self):
        for record in self:
            if (
                record.period_start_date
                and record.period_end_date
                and record.period_end_date
                < record.period_start_date
            ):
                raise ValidationError(
                    _(
                        "La date de fin ne peut pas être "
                        "antérieure à la date de début."
                    )
                )

    @api.constrains(
        "line_ids",
        "line_ids.member_id",
    )
    def _check_duplicate_members(self):
        for record in self:
            member_ids = record.line_ids.mapped(
                "member_id"
            ).ids

            if len(member_ids) != len(set(member_ids)):
                raise ValidationError(
                    _(
                        "Un membre ne peut apparaître qu'une seule "
                        "fois dans la même cotisation."
                    )
                )

    # ==========================================================
    # ONCHANGE
    # ==========================================================

    @api.onchange("amount")
    def _onchange_amount(self):
        for record in self:
            if record.state == "draft":
                for line in record.line_ids:
                    line.amount_due = record.amount

    # ==========================================================
    # GÉNÉRER LES MEMBRES
    # ==========================================================

    def action_generate_members(self):
        Member = self.env["association.member"]

        for record in self:
            if record.state != "draft":
                raise UserError(
                    _(
                        "Les membres peuvent uniquement être générés "
                        "sur une cotisation en brouillon."
                    )
                )

            existing_member_ids = set(
                record.line_ids.mapped("member_id").ids
            )

            members = Member.search([
                ("active", "=", True),
                ("state", "=", "active"),
                ("company_id", "=", record.company_id.id),
            ])

            values_list = []

            for member in members:
                if member.id in existing_member_ids:
                    continue

                values_list.append({
                    "subscription_id": record.id,
                    "member_id": member.id,
                    "amount_due": record.amount,
                })

            if not values_list:
                raise UserError(
                    _(
                        "Tous les membres actifs sont déjà présents "
                        "dans cette cotisation."
                    )
                )

            self.env[
                "association.subscription.line"
            ].create(values_list)

            record.message_post(
                body=_(
                    "%(count)s membre(s) ajouté(s) "
                    "à la cotisation."
                )
                % {
                    "count": len(values_list),
                }
            )

        return True

   
   
    # ==========================================================
    # CONFIRMER
    # ==========================================================

    def action_confirm(self):
        for record in self:
            if not record.line_ids:
                raise ValidationError(
                    _(
                        "Vous devez ajouter au moins un membre "
                        "avant de confirmer la cotisation."
                    )
                )

            if record.amount <= 0:
                raise ValidationError(
                    _(
                        "Le montant de la cotisation doit être "
                        "strictement supérieur à zéro."
                    )
                )

            record.state = "confirmed"

            record.message_post(
                body=_("La cotisation a été confirmée.")
            )

        return True

    # ==========================================================
    # DÉMARRER LA COTISATION
    # ==========================================================

    def action_start(self):

        for record in self:

            if record.state != "confirmed":

                raise UserError(
                    _(
                        "Seule une cotisation confirmée "
                        "peut être démarrée."
                    )
                )

            if not record.line_ids:

                raise ValidationError(
                    _(
                        "La cotisation ne contient aucun membre."
                    )
                )

            record.write({
                "state": "running",
            })

            period = record._create_first_period()

            if period.state == "draft":

                period.action_start()

            record.invalidate_recordset([
                "current_period_id",
                "period_count",
            ])

            record.message_post(
                body=_(
                    "La cotisation a été démarrée avec "
                    "le cycle %(cycle)s."
                )
                % {
                    "cycle": period.display_name,
                }
            )

        return True
    # ==========================================================
    # PRÉPARATION DU PROCHAIN CYCLE
    # ==========================================================

    def _prepare_next_period_values(self):
        self.ensure_one()

        last_period = self.period_ids.sorted(
            key=lambda period: (
                period.sequence,
                period.id,
            ),
            reverse=True,
        )[:1]

        sequence = (
            last_period.sequence + 1
            if last_period
            else 1
        )

        if last_period:
            start_date = (
                last_period.period_end_date
                + relativedelta(days=1)
            )
        else:
            start_date = (
                self.period_start_date
                or self.date
                or fields.Date.context_today(self)
            )

        if self.subscription_type == "daily":
            end_date = start_date

        elif self.subscription_type == "weekly":
            end_date = (
                start_date
                + relativedelta(days=6)
            )

        elif self.subscription_type == "biweekly":
            end_date = (
                start_date
                + relativedelta(days=13)
            )

        elif self.subscription_type == "monthly":
            end_date = (
                start_date
                + relativedelta(months=1, days=-1)
            )

        elif self.subscription_type == "bimonthly":
            end_date = (
                start_date
                + relativedelta(months=2, days=-1)
            )

        elif self.subscription_type == "quarterly":
            end_date = (
                start_date
                + relativedelta(months=3, days=-1)
            )

        elif self.subscription_type == "annual":
            end_date = (
                start_date
                + relativedelta(years=1, days=-1)
            )

        else:
            end_date = start_date

        return {
            "subscription_id": self.id,
            "sequence": sequence,
            "period_start_date": start_date,
            "period_end_date": end_date,
            "due_date": self._get_period_due_date(start_date, end_date),
            "state": "draft",
        }


    # ==========================================================
    # CALCUL DES DATES DU PROCHAIN CYCLE
    # ==========================================================

    def _get_next_cycle_dates(
        self,
        previous_period=False,
    ):

        self.ensure_one()

        if previous_period:

            start_date = (
                previous_period.period_end_date
                + timedelta(days=1)
            )

        else:

            start_date = (
                self.period_start_date
                or self.date
                or fields.Date.context_today(self)
            )

        subscription_type = self.subscription_type

        if subscription_type == "daily":

            end_date = start_date

        elif subscription_type == "weekly":

            end_date = (
                start_date
                + timedelta(days=6)
            )

        elif subscription_type == "biweekly":

            end_date = (
                start_date
                + timedelta(days=13)
            )

        elif subscription_type == "monthly":

            end_date = (
                start_date
                + relativedelta(months=1)
                - timedelta(days=1)
            )

        elif subscription_type == "bimonthly":

            end_date = (
                start_date
                + relativedelta(months=2)
                - timedelta(days=1)
            )

        elif subscription_type == "quarterly":

            end_date = (
                start_date
                + relativedelta(months=3)
                - timedelta(days=1)
            )

        elif subscription_type == "annual":

            end_date = (
                start_date
                + relativedelta(years=1)
                - timedelta(days=1)
            )

        else:

            end_date = (
                self.period_end_date
                or start_date
            )

        due_date = (
            self.due_date
            if not previous_period and self.due_date
            else self._get_period_due_date(start_date, end_date)
        )

        return (
            start_date,
            end_date,
            due_date,
        )

    def _get_period_due_date(self, start_date, end_date):
        """Return the deadline configured for a type-derived period."""
        self.ensure_one()
        if self.due_timing == "period_start":
            return start_date
        if self.due_timing == "custom_days":
            due_date = start_date + timedelta(
                days=max(self.due_days_after_start or 0, 0)
            )
            return min(due_date, end_date)
        return end_date

    @api.constrains("due_days_after_start")
    def _check_due_days_after_start(self):
        for subscription in self:
            if subscription.due_days_after_start < 0:
                raise ValidationError(
                    _("Le nombre de jours avant échéance ne peut être négatif.")
                )

    # ==========================================================
    # CRÉER LE PREMIER CYCLE
    # ==========================================================

    def _create_first_period(self):

        self.ensure_one()

        if self.period_ids:

            return self.period_ids.sorted(
                key=lambda period:
                    (
                        period.sequence,
                        period.id,
                    ),
                reverse=True,
            )[0]

        (
            start_date,
            end_date,
            due_date,
        ) = self._get_next_cycle_dates()

        period = self.env[
            "association.subscription.period"
        ].create({
            "subscription_id": self.id,
            "sequence": 1,
            "period_start_date": start_date,
            "period_end_date": end_date,
            "due_date": due_date,
            "state": "draft",
        })

        return period

    # ==========================================================
    # ACTION - TERMINER LE CYCLE COURANT
    # ==========================================================

    def action_close_current_period(self):
        self.ensure_one()

        # ======================================================
        # CONTRÔLE DE LA COTISATION
        # ======================================================

        if self.state != "running":
            raise UserError(
                _(
                    "Seule une cotisation en cours "
                    "peut terminer son cycle courant."
                )
            )

        # ======================================================
        # RECHERCHE DU CYCLE COURANT
        # ======================================================

        current_periods = self.period_ids.filtered(
            lambda period:
                period.state == "running"
        )

        if not current_periods:
            raise ValidationError(
                _(
                    "Aucun cycle en cours n'a été trouvé "
                    "pour cette cotisation."
                )
            )

        if len(current_periods) > 1:
            raise ValidationError(
                _(
                    "Plusieurs cycles en cours ont été détectés.\n\n"
                    "Une cotisation ne peut avoir qu'un seul "
                    "cycle actif."
                )
            )

        current_period = current_periods[0]

        # ======================================================
        # OUVRIR LE WORKFLOW DE CLÔTURE DU CYCLE
        # ======================================================
        #
        # IMPORTANT :
        # on retourne directement l'action du cycle.
        #
        # Il ne faut :
        # - ni fermer le cycle ici
        # - ni réinitialiser les membres ici
        # - ni recharger la vue ici
        #
        # Le wizard doit d'abord demander :
        # bénéficiaire OUI / NON.
        # ======================================================

        return current_period.action_close()

    # ==========================================================
    # ACTION - OUVRIR LE CYCLE SUIVANT
    # ==========================================================

    def action_open_next_period(self):

        Period = self.env[
            "association.subscription.period"
        ]

        for subscription in self:

            if subscription.state != "running":

                raise UserError(
                    _(
                        "La cotisation doit être en cours "
                        "pour ouvrir le cycle suivant."
                    )
                )

            # --------------------------------------------------
            # INTERDIRE SI UN CYCLE EST ENCORE ACTIF
            # --------------------------------------------------

            running_period = subscription.period_ids.filtered(
                lambda period:
                    period.state == "running"
            )

            if running_period:

                raise ValidationError(
                    _(
                        "Le cycle %(cycle)s est encore en cours.\n\n"
                        "Cliquez d'abord sur « Terminer le cycle »."
                    )
                    % {
                        "cycle":
                            running_period[0].display_name,
                    }
                )

            # --------------------------------------------------
            # DERNIER CYCLE TERMINÉ
            # --------------------------------------------------

            closed_periods = subscription.period_ids.filtered(
                lambda period:
                    period.state == "closed"
            )

            if not closed_periods:

                raise ValidationError(
                    _(
                        "Aucun cycle terminé n'a été trouvé."
                    )
                )

            previous_period = closed_periods.sorted(
                key=lambda period: (
                    period.sequence,
                    period.id,
                ),
                reverse=True,
            )[0]

            # --------------------------------------------------
            # CALCUL DES DATES
            # --------------------------------------------------

            (
                start_date,
                end_date,
                due_date,
            ) = subscription._get_next_cycle_dates(
                previous_period=previous_period,
            )

            next_sequence = (
                previous_period.sequence + 1
            )

            # --------------------------------------------------
            # CRÉATION DU NOUVEAU CYCLE
            # --------------------------------------------------

            new_period = Period.create({
                "subscription_id":
                    subscription.id,

                "sequence":
                    next_sequence,

                "period_start_date":
                    start_date,

                "period_end_date":
                    end_date,

                "due_date":
                    due_date,

                "state":
                    "draft",
            })

            # --------------------------------------------------
            # DÉMARRER LE CYCLE
            # --------------------------------------------------

            new_period.action_start()

            # --------------------------------------------------
            # RÉINITIALISER LES SAISIES DU TABLEAU
            # --------------------------------------------------

            subscription.line_ids.write({
                "amount_received": 0.0,
            })

            # --------------------------------------------------
            # ACTUALISER LE CYCLE COURANT
            # --------------------------------------------------

            subscription.invalidate_recordset([
                "current_period_id",
                "period_count",
            ])

            subscription.modified([
                "current_period_id",
                "period_count",
            ])

            # --------------------------------------------------
            # FORCER LE RECALCUL DES MEMBRES
            # --------------------------------------------------

            subscription.line_ids.invalidate_recordset([
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])

            subscription.line_ids.modified([
                "amount_due",
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])

            subscription.message_post(
                body=_(
                    "Le %(cycle)s a été ouvert.\n\n"
                    "Le tableau des membres a été initialisé "
                    "pour le nouveau cycle."
                )
                % {
                    "cycle":
                        new_period.display_name,
                }
            )

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
    # ==========================================================
    # CLÔTURER LA COTISATION
    # ==========================================================

    def action_close(self):
        for record in self:
            if record.state != "running":
                raise UserError(
                    _(
                        "Seule une cotisation en cours "
                        "peut être clôturée."
                    )
                )

            open_period = record.period_ids.filtered(
                lambda period: period.state in (
                    "draft",
                    "running",
                )
            )

            if open_period:
                raise UserError(
                    _(
                        "Impossible de clôturer la cotisation.\n\n"
                        "Un cycle est encore ouvert."
                    )
                )

            record.state = "closed"

            record.message_post(
                body=_("La cotisation a été clôturée.")
            )

        return True

    # ==========================================================
    # ACTION - PASSER AU CYCLE SUIVANT
    # ==========================================================

    def action_open_next_cycle(self):

        Period = self.env[
            "association.subscription.period"
        ]

        for subscription in self:

            # ==================================================
            # CONTRÔLE DE LA COTISATION
            # ==================================================

            if subscription.state != "running":

                raise UserError(
                    _(
                        "Seule une cotisation en cours "
                        "peut passer au cycle suivant."
                    )
                )

            if subscription.subscription_type in (
                "registration",
                "special",
            ):

                raise ValidationError(
                    _(
                        "Ce type de cotisation ne permet pas "
                        "la génération automatique de cycles."
                    )
                )

            # ==================================================
            # CYCLE COURANT
            # ==================================================

            current_period = Period.search(
                [
                    (
                        "subscription_id",
                        "=",
                        subscription.id,
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

            if not current_period:

                raise ValidationError(
                    _(
                        "Aucun cycle en cours n'a été trouvé "
                        "pour cette cotisation."
                    )
                )

            # ==================================================
            # TERMINER LE CYCLE COURANT
            # ==================================================

            current_period.action_close()

            # ==================================================
            # PROCHAIN NUMÉRO
            # ==================================================

            next_sequence = (
                current_period.sequence + 1
            )

            # ==================================================
            # DATE DE DÉBUT
            # ==================================================

            start_date = (
                current_period.period_end_date
                + relativedelta(days=1)
            )

            # ==================================================
            # CALCUL DE LA PÉRIODE
            # ==================================================

            subscription_type = (
                subscription.subscription_type
            )

            if subscription_type == "daily":

                end_date = start_date

            elif subscription_type == "weekly":

                end_date = (
                    start_date
                    + relativedelta(days=6)
                )

            elif subscription_type == "biweekly":

                end_date = (
                    start_date
                    + relativedelta(days=13)
                )

            elif subscription_type == "monthly":

                end_date = (
                    start_date
                    + relativedelta(months=1)
                    - relativedelta(days=1)
                )

            elif subscription_type == "bimonthly":

                end_date = (
                    start_date
                    + relativedelta(months=2)
                    - relativedelta(days=1)
                )

            elif subscription_type == "quarterly":

                end_date = (
                    start_date
                    + relativedelta(months=3)
                    - relativedelta(days=1)
                )

            elif subscription_type == "annual":

                end_date = (
                    start_date
                    + relativedelta(years=1)
                    - relativedelta(days=1)
                )

            else:

                raise ValidationError(
                    _(
                        "Impossible de déterminer "
                        "la durée du prochain cycle."
                    )
                )

            # ==================================================
            # CRÉATION DU NOUVEAU CYCLE
            # ==================================================

            new_period = Period.create(
                {
                    "subscription_id":
                        subscription.id,

                    "sequence":
                        next_sequence,

                    "period_start_date":
                        start_date,

                    "period_end_date":
                        end_date,

                    "due_date": subscription._get_period_due_date(
                        start_date, end_date
                    ),

                    "state":
                        "draft",
                }
            )

            # ==================================================
            # DÉMARRER LE NOUVEAU CYCLE
            # ==================================================

            new_period.action_start()

            # ==================================================
            # INVALIDER LE CYCLE COURANT
            # ==================================================

            subscription.invalidate_recordset(
                [
                    "current_period_id",
                    "period_count",
                ]
            )

            # ==================================================
            # RECALCUL DES LIGNES
            # ==================================================

            subscription.line_ids.invalidate_recordset(
                [
                    "amount_due",
                    "amount_paid",
                    "balance",
                    "payment_state",
                    "payment_date",
                ]
            )

            # ==================================================
            # MESSAGE
            # ==================================================

            subscription.message_post(
                body=_(
                    "Le %(old_cycle)s a été terminé.\n"
                    "Le %(new_cycle)s est maintenant en cours.\n\n"
                    "Nouvelle période : %(start)s au %(end)s."
                )
                % {
                    "old_cycle":
                        current_period.display_name,

                    "new_cycle":
                        new_period.display_name,

                    "start":
                        fields.Date.to_string(
                            start_date
                        ),

                    "end":
                        fields.Date.to_string(
                            end_date
                        ),
                }
            )

        # ======================================================
        # ACTUALISER L'INTERFACE
        # ======================================================

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
    
    
    
    # ==========================================================
    # ANNULER
    # ==========================================================

    def action_cancel(self):
        for record in self:
            if record.state == "closed":
                raise UserError(
                    _(
                        "Une cotisation clôturée ne peut pas "
                        "être annulée directement."
                    )
                )

            running_period = record.period_ids.filtered(
                lambda period: period.state == "running"
            )

            if running_period:
                raise UserError(
                    _(
                        "Impossible d'annuler la cotisation.\n\n"
                        "Un cycle est actuellement en cours."
                    )
                )

            record.state = "cancelled"

            record.message_post(
                body=_("La cotisation a été annulée.")
            )

        return True

    # ==========================================================
    # REMETTRE EN BROUILLON
    # ==========================================================

    def action_reset_draft(self):
        for record in self:
            if record.state not in (
                "confirmed",
                "cancelled",
            ):
                raise UserError(
                    _(
                        "Seule une cotisation confirmée ou annulée "
                        "peut être remise en brouillon."
                    )
                )

            if record.period_ids:
                raise UserError(
                    _(
                        "Impossible de remettre cette cotisation "
                        "en brouillon car elle possède déjà "
                        "un historique de cycles."
                    )
                )

            record.state = "draft"

            record.message_post(
                body=_(
                    "La cotisation a été remise en brouillon."
                )
            )

        return True

    # ==========================================================
    # VOIR LES PAIEMENTS
    # ==========================================================

    def action_view_payments(self):
        self.ensure_one()

        payments = self.line_ids.mapped(
            "payment_line_ids.payment_id"
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Paiements"),
            "res_model": "association.payment",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", payments.ids),
            ],
            "context": {
                "default_subscription_id": self.id,
            },
        }

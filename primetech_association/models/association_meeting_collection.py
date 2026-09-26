# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AssociationMeetingCollection(models.Model):

    _name = "association.meeting.collection"
    _description = "Encaissement de cotisation en réunion"
    _order = "sequence, member_id"
    _rec_name = "member_id"

    # ==========================================================
    # RÉUNION
    # ==========================================================

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion",
        required=True,
        ondelete="cascade",
        index=True,
    )

    session_id = fields.Many2one(
        comodel_name="association.meeting.subscription.session",
        string="Session de cotisation",
        ondelete="cascade",
        index=True,
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        Session = self.env["association.meeting.subscription.session"]
        for vals in vals_list:
            session_id = vals.get("session_id")
            if session_id and Session.browse(session_id).state in ("closed", "cancelled"):
                raise UserError(_("La session de cotisation est verrouillée."))
        records = super().create(vals_list)
        for record in records:
            if record.subscription_id.state != "running":
                raise UserError(_("Seules les cotisations en cours peuvent être encaissées en réunion."))
            if not record.initial_due_amount:
                record.initial_due_amount = record.amount_due
        return records

    sequence = fields.Integer(
        string="Ordre",
        default=10,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        related="meeting_id.company_id",
        string="Société",
        store=True,
        readonly=True,
    )

    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="company_id.currency_id",
        string="Devise",
        store=True,
        readonly=True,
    )

    meeting_state = fields.Selection(
        related="meeting_id.state",
        string="État de la réunion",
        readonly=True,
    )

    # ==========================================================
    # COTISATION
    # ==========================================================

    subscription_id = fields.Many2one(
        comodel_name="association.subscription",
        string="Cotisation",
        required=True,
        ondelete="restrict",
        index=True,
    )

    subscription_line_id = fields.Many2one(
        comodel_name="association.subscription.line",
        string="Ligne de cotisation",
        required=True,
        ondelete="restrict",
        index=True,
    )
    period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle de cotisation",
        compute="_compute_period_id",
        store=True,
        readonly=True,
        index=True,
    )

    due_date = fields.Date(
        related="period_id.due_date",
        string="Échéance",
        readonly=True,
        store=True,
    )

    amount_due = fields.Monetary(
        related="subscription_line_id.amount_due",
        string="Montant dû",
        currency_field="currency_id",
        readonly=True,
    )

    initial_due_amount = fields.Monetary(
        string="Dû au début de la séance",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    frozen_amount_paid = fields.Monetary(
        string="Réglé à la clôture du cycle",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    frozen_balance = fields.Monetary(
        string="Reste à la clôture du cycle",
        currency_field="currency_id",
        readonly=True,
        copy=False,
    )

    frozen_payment_state = fields.Selection(
        [
            ("not_paid", "Non payé"),
            ("partial", "Partiellement payé"),
            ("paid", "Payé"),
        ],
        string="État à la clôture du cycle",
        readonly=True,
        copy=False,
    )

    balance = fields.Monetary(
        related="subscription_line_id.balance",
        string="Reste à payer",
        currency_field="currency_id",
        readonly=True,
    )

    payment_state = fields.Selection(
        related="subscription_line_id.payment_state",
        string="État cotisation",
        readonly=True,
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        related="subscription_line_id.member_id",
        string="Membre",
        store=True,
        readonly=True,
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="N° membre",
        store=True,
        readonly=True,
    )

    member_image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo",
        readonly=True,
    )

    category_id = fields.Many2one(
        related="member_id.category_id",
        string="Catégorie",
        store=True,
        readonly=True,
    )

    # ==========================================================
    # ENCAISSEMENT
    # ==========================================================

    amount = fields.Monetary(
        string="Montant reçu",
        currency_field="currency_id",
        default=0.0,
    )

    amount_paid = fields.Monetary(
        string="Déjà payé",
        related="subscription_line_id.amount_paid",
        currency_field="currency_id",
        readonly=True,
    )

    payment_method = fields.Selection(
        selection=[
            ("cash", "Espèces"),
            ("bank", "Virement bancaire"),
            ("cheque", "Chèque"),
            ("mobile_money", "Mobile Money"),
            ("other", "Autre"),
        ],
        string="Mode de paiement",
        default="cash",
        required=True,
    )

    payment_reference = fields.Char(
        string="Référence",
    )

    collection_date = fields.Datetime(
        string="Date d'encaissement",
        readonly=True,
        copy=False,
    )

    # ==========================================================
    # PAIEMENT
    # ==========================================================

    payment_id = fields.Many2one(
        comodel_name="association.payment",
        string="Paiement",
        readonly=True,
        copy=False,
        ondelete="restrict",
    )

    allocated_amount = fields.Monetary(
        string="Montant affecté",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    remaining_amount = fields.Monetary(
        string="Surplus",
        currency_field="currency_id",
        compute="_compute_payment_amounts",
    )

    processed_surplus_amount = fields.Monetary(
        string="Surplus traité",
        currency_field="currency_id",
        default=0.0,
        readonly=True,
        copy=False,
    )

    surplus_action = fields.Selection(
        [("refund", "Remboursé"),
         ("credit_account", "Crédité au compte membre")],
        string="Destination du surplus",
        readonly=True,
        copy=False,
    )

    # ==========================================================
    # VALIDATION
    # ==========================================================

    validated_by = fields.Many2one(
        comodel_name="res.users",
        string="Encaissé par",
        readonly=True,
        copy=False,
    )

    validation_date = fields.Datetime(
        string="Date de validation",
        readonly=True,
        copy=False,
    )

    # ==========================================================
    # ÉTAT
    # ==========================================================

    state = fields.Selection(
        selection=[
            ("pending", "En attente"),
            ("paid", "Encaissé"),
            ("cancelled", "Annulé"),
        ],
        string="Statut",
        default="pending",
        required=True,
        index=True,
    )

    note = fields.Text(
        string="Observation",
    )
    # ==========================================================
    # SOLDE RÉEL DU COMPTE MEMBRE
    # ==========================================================

    member_account_balance = fields.Monetary(
        string="Solde réel du compte",
        currency_field="currency_id",
        compute="_compute_member_account_balance",
        store=False,
    )


    def _compute_member_account_balance(self):

        Account = self.env[
            "association.member.account"
        ]

        for record in self:

            # ======================================================
            # VALEUR PAR DÉFAUT
            # ======================================================

            record.member_account_balance = 0.0

            # ======================================================
            # CONTRÔLE DU MEMBRE
            # ======================================================

            if not record.member_id:
                continue

            # ======================================================
            # RECHERCHE DU COMPTE RÉEL DU MEMBRE
            # ======================================================

            domain = [
                (
                    "member_id",
                    "=",
                    record.member_id.id,
                ),
            ]

            if record.company_id:

                domain.append(
                    (
                        "company_id",
                        "=",
                        record.company_id.id,
                    )
                )

            account = Account.search(
                domain,
                limit=1,
            )

            # ======================================================
            # LECTURE DU SOLDE ACTUEL
            # ======================================================

            if account:

                account.invalidate_recordset([
                    "balance",
                ])

                record.member_account_balance = (
                    account.balance or 0.0
                )

    @api.depends(
        "subscription_id",
        "subscription_id.period_ids",
        "subscription_id.period_ids.state",
        "subscription_id.period_ids.sequence",
    )
    def _compute_period_id(self):

        for record in self:

            record.period_id = False

            if not record.subscription_id:
                continue

            running_periods = (
                record.subscription_id.period_ids.filtered(
                    lambda period:
                        period.state == "running"
                )
            )

            if not running_periods:
                continue

            record.period_id = running_periods.sorted(
                key=lambda period: (
                    period.sequence,
                    period.id,
                ),
                reverse=True,
            )[0]


    @api.depends("member_id")
    def _compute_member_account_balance(self):
        Account = self.env["association.member.account"]

        for record in self:

            record.member_account_balance = 0.0

            if not record.member_id:
                continue

            account = Account.search(
                [
                    (
                        "member_id",
                        "=",
                        record.member_id.id,
                    ),
                ],
                limit=1,
            )

            if account:
                record.member_account_balance = (
                    account.balance or 0.0
                )


    # ==========================================================
    # ACTION - PAYER
    # ==========================================================
    def action_create_payment(self):
        self.ensure_one()

        if not self.member_id:
            raise UserError(
                _("Aucun membre n'est défini.")
            )

        if not self.subscription_line_id:
            raise UserError(
                _(
                    "Aucune cotisation n'est associée "
                    "à cette ligne."
                )
            )

        if self.subscription_id.state != "running":
            raise UserError(
                _(
                    "La cotisation %(subscription)s n'est pas en cours et ne peut pas être encaissée."
                )
                % {"subscription": self.subscription_id.display_name}
            )

        amount_received = self.amount or 0.0
        current_balance = self.balance or 0.0

        if amount_received <= 0:
            raise ValidationError(
                _(
                    "Le montant reçu doit être "
                    "strictement supérieur à zéro."
                )
            )

        if current_balance <= 0:
            raise UserError(
                _("Cette cotisation est déjà réglée.")
            )

        # ==========================================================
        # SURPLUS
        # ==========================================================

        if amount_received > current_balance:

            surplus_amount = (
                amount_received - current_balance
            )

            return {
                "type": "ir.actions.act_window",
                "name": _("Traitement du surplus"),
                "res_model":
                    "association.meeting.collection.surplus.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_collection_id": self.id,
                    "default_amount_received":
                        amount_received,
                    "default_amount_to_pay":
                        current_balance,
                    "default_surplus_amount":
                        surplus_amount,
                },
            }

        # ==========================================================
        # PAIEMENT NORMAL
        # ==========================================================

        self._process_cash_collection(
            amount_received
        )

        # PAS DE RELOAD
        return False
    
    def _process_cash_collection(
        self,
        amount_to_pay,
    ):
        self.ensure_one()

        if amount_to_pay <= 0:
            raise ValidationError(
                _(
                    "Le montant à encaisser doit être "
                    "supérieur à zéro."
                )
            )

        payment = self.env[
            "association.payment"
        ].create(
            {
                "name": _("Nouveau"),

                "member_id":
                    self.member_id.id,

                "payment_date":
                    fields.Date.context_today(self),

                "amount":
                    amount_to_pay,

                "payment_method":
                    self.payment_method or "cash",

                "payment_reference":
                    self.payment_reference,

                "company_id":
                    self.company_id.id,

                "payment_source": "meeting_cash",

                "meeting_id": self.meeting_id.id,

                "meeting_subscription_session_id": self.session_id.id,

                "has_allocations": True,

                "description":
                    _(
                        "Encaissement de %(subscription)s "
                        "pendant la réunion %(meeting)s"
                    )
                    % {
                        "subscription":
                            self.subscription_id.display_name,

                        "meeting":
                            self.meeting_id.display_name,
                    },

                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "subscription_line_id":
                                self.subscription_line_id.id,

                            "amount_paid":
                                amount_to_pay,
                        },
                    ),
                ],
            }
        )

        payment.action_collect()
        payment.action_confirm()

        self.write(
            {
                "payment_id":
                    payment.id,

                "collection_date":
                    fields.Datetime.now(),

                "validated_by":
                    self.env.user.id,

                "validation_date":
                    fields.Datetime.now(),

                "state":
                    "paid",

                "amount":
                    0.0,
            }
        )

        self.meeting_id.message_post(
            body=_(
                "Cotisation encaissée pour "
                "%(member)s : "
                "%(amount).2f %(currency)s."
            )
            % {
                "member":
                    self.member_id.display_name,

                "amount":
                    amount_to_pay,

                "currency":
                    self.currency_id.name or "",
            }
        )

        return payment
    # ==========================================================
    # ACTION - PAYER AVEC LE COMPTE DU MEMBRE
    # ==========================================================

    def action_pay_from_member_account(self):
        self.ensure_one()

        if not self.member_id:
            raise UserError(
                _("Aucun membre n'est défini.")
            )

        if not self.subscription_line_id:
            raise UserError(
                _(
                    "Aucune cotisation n'est associée "
                    "à cette ligne."
                )
            )

        balance = self.balance or 0.0

        if balance <= 0:
            raise UserError(
                _("Cette cotisation est déjà réglée.")
            )

        Account = self.env[
            "association.member.account"
        ]

        account = Account.search(
            [
                (
                    "member_id",
                    "=",
                    self.member_id.id,
                ),
            ],
            limit=1,
        )

        if not account:
            raise UserError(
                _(
                    "Le membre %s ne possède "
                    "aucun compte membre."
                )
                % self.member_id.display_name
            )

        account_balance = account.balance or 0.0

        if account_balance <= 0:
            raise UserError(
                _(
                    "Le compte du membre ne dispose "
                    "d'aucun solde disponible."
                )
            )

        amount_to_pay = min(
            account_balance,
            balance,
        )

        payment = self.env[
            "association.payment"
        ].create(
            {
                "name": _("Nouveau"),
                "member_id": self.member_id.id,
                "payment_date": fields.Date.context_today(
                    self
                ),
                "amount": amount_to_pay,
                "payment_method": "bank",
                "company_id": self.company_id.id,
                "payment_source": "member_account",
                "member_account_id": account.id,
                "meeting_id": self.meeting_id.id,
                "meeting_subscription_session_id": self.session_id.id,
                "defer_member_account_debit": bool(self.session_id),
                "has_allocations": True,
            }
        )

        self.env[
            "association.payment.line"
        ].create(
            {
                "payment_id": payment.id,
                "subscription_line_id":
                    self.subscription_line_id.id,
                "amount_paid": amount_to_pay,
            }
        )

        payment.action_collect()
        payment.action_confirm()

        self.write({
            "payment_id": payment.id,
            "collection_date": fields.Datetime.now(),
            "validated_by": self.env.user.id,
            "validation_date": fields.Datetime.now(),
            "state": "paid",
            "amount": 0.0,
        })

        self.meeting_id.message_post(
            body=_(
                "Cotisation réglée depuis le compte de %(member)s : %(amount).2f %(currency)s."
            ) % {
                "member": self.member_id.display_name,
                "amount": amount_to_pay,
                "currency": self.currency_id.name or "",
            }
        )

        return False

    def action_freeze_cycle_snapshot(self):
        """Preserve the collection state shown for the closed meeting cycle."""
        for record in self:
            record.write({
                "frozen_amount_paid": record.subscription_line_id.amount_paid,
                "frozen_balance": record.subscription_line_id.balance,
                "frozen_payment_state": record.subscription_line_id.payment_state,
            })
        return True
    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "meeting_subscription_line_unique",
            "unique(meeting_id, subscription_line_id)",
            "Ce membre existe déjà pour cette cotisation "
            "dans la réunion.",
        ),
    ]

    # ==========================================================
    # CALCUL DES MONTANTS
    # ==========================================================

    @api.depends(
        "amount",
        "balance",
        "state",
    )
    def _compute_payment_amounts(self):

        for record in self:

            record.allocated_amount = 0.0
            record.remaining_amount = 0.0

            if record.amount <= 0:
                continue

            record.allocated_amount = min(
                record.amount,
                record.balance,
            )

            record.remaining_amount = max(
                record.amount - record.balance,
                0.0,
            )

    # ==========================================================
    # CONTRÔLE DU MONTANT
    # ==========================================================

    @api.constrains("amount")
    def _check_amount(self):

        for record in self:

            if record.amount < 0:

                raise ValidationError(
                    _(
                        "Le montant reçu ne peut pas être négatif."
                    )
                )

    # ==========================================================
    # ACTION - ENCAISSER
    # ==========================================================

    def action_collect(self):

        Payment = self.env["association.payment"]

        for record in self:

            # ==================================================
            # CONTRÔLE DU STATUT
            # ==================================================

            if record.state != "pending":

                raise UserError(
                    _(
                        "Seuls les encaissements en attente "
                        "peuvent être traités."
                    )
                )

            # ==================================================
            # PAIEMENT EXISTANT
            # ==================================================

            if record.payment_id:

                raise UserError(
                    _(
                        "Un paiement existe déjà pour "
                        "cet encaissement."
                    )
                )

            # ==================================================
            # CONTRÔLE DU MONTANT SAISI
            # ==================================================

            amount_received = record.amount or 0.0

            if amount_received <= 0:

                raise ValidationError(
                    _(
                        "Le montant reçu doit être "
                        "strictement supérieur à zéro."
                    )
                )

            # ==================================================
            # CONTRÔLE DU MEMBRE
            # ==================================================

            if not record.member_id:

                raise ValidationError(
                    _(
                        "Aucun membre n'est défini "
                        "pour cet encaissement."
                    )
                )

            # ==================================================
            # CONTRÔLE DE LA COTISATION
            # ==================================================

            if not record.subscription_line_id:

                raise ValidationError(
                    _(
                        "Aucune cotisation n'est liée "
                        "à cet encaissement."
                    )
                )

            subscription_line = record.subscription_line_id

            # ==================================================
            # CONTRÔLE DU RESTE À PAYER
            # ==================================================

            current_balance = subscription_line.balance or 0.0

            if current_balance <= 0:

                raise ValidationError(
                    _(
                        "La cotisation du membre %(member)s "
                        "est déjà entièrement soldée."
                    )
                    % {
                        "member":
                            record.member_id.display_name,
                    }
                )

            if amount_received > current_balance:
                raise ValidationError(
                    _(
                        "Le montant reçu pour %(member)s contient un "
                        "surplus de %(surplus).2f %(currency)s. Utilisez "
                        "le bouton Payer sur sa ligne afin de choisir "
                        "entre remboursement et crédit du compte membre."
                    ) % {
                        "member": record.member_id.display_name,
                        "surplus": amount_received - current_balance,
                        "currency": record.currency_id.name or "",
                    }
                )

            # ==================================================
            # MONTANT À AFFECTER À LA COTISATION
            # ==================================================

            amount_to_allocate = min(
                amount_received,
                current_balance,
            )

            if amount_to_allocate <= 0:

                raise ValidationError(
                    _(
                        "Le montant à affecter à la cotisation "
                        "doit être supérieur à zéro."
                    )
                )

            # ==================================================
            # CRÉATION DU PAIEMENT AVEC LA LIGNE DIRECTEMENT
            # ==================================================

            payment = Payment.create(
                {
                    "company_id":
                        record.company_id.id,

                    "payment_source": "meeting_cash",

                    "meeting_id": record.meeting_id.id,
                    "meeting_subscription_session_id": record.session_id.id,

                    "has_allocations": True,

                    "member_id":
                        record.member_id.id,

                    "payment_date":
                        fields.Date.context_today(record),

                    "amount":
                        amount_to_allocate,

                    "payment_method":
                        record.payment_method,

                    "payment_reference":
                        record.payment_reference,

                    "description":
                        _(
                            "Encaissement de %(subscription)s "
                            "pendant la réunion %(meeting)s"
                        )
                        % {
                            "subscription":
                                record.subscription_id.display_name,

                            "meeting":
                                record.meeting_id.display_name,
                        },

                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "subscription_line_id":
                                    subscription_line.id,

                                "amount_paid":
                                    amount_to_allocate,
                            },
                        ),
                    ],
                }
            )

            # ==================================================
            # VÉRIFICATION DU PAIEMENT CRÉÉ
            # ==================================================

            if not payment:

                raise UserError(
                    _(
                        "Le paiement n'a pas pu être créé."
                    )
                )

            if payment.amount <= 0:

                payment.unlink()

                raise ValidationError(
                    _(
                        "Le montant du paiement généré "
                        "est invalide."
                    )
                )

            if not payment.line_ids:

                payment.unlink()

                raise ValidationError(
                    _(
                        "Aucune affectation de cotisation "
                        "n'a été générée."
                    )
                )

            # ==================================================
            # CONFIRMATION DU PAIEMENT
            # ==================================================

            payment.action_collect()
            payment.action_confirm()

            # ==================================================
            # VALIDATION DE L'ENCAISSEMENT
            # ==================================================

            record.write(
                {
                    "payment_id":
                        payment.id,

                    "collection_date":
                        fields.Datetime.now(),

                    "validated_by":
                        self.env.user.id,

                    "validation_date":
                        fields.Datetime.now(),

                    "state":
                        "paid",
                }
            )

            # ==================================================
            # MESSAGE DANS LA RÉUNION
            # ==================================================

            record.meeting_id.message_post(
                body=_(
                    "Cotisation encaissée pour %(member)s : "
                    "%(amount).2f %(currency)s."
                )
                % {
                    "member":
                        record.member_id.display_name,

                    "amount":
                        amount_to_allocate,

                    "currency":
                        record.currency_id.name or "",
                }
            )

        return True
    
    # ==========================================================
    # OUVRIR LE PAIEMENT
    # ==========================================================

    def action_open_payment(self):

        self.ensure_one()

        if not self.payment_id:

            raise UserError(
                _(
                    "Aucun paiement n'est lié "
                    "à cet encaissement."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Paiement"),
            "res_model": "association.payment",
            "view_mode": "form",
            "res_id": self.payment_id.id,
            "target": "current",
        }

    # ==========================================================
    # ANNULER UNE LIGNE EN ATTENTE
    # ==========================================================

    def action_cancel(self):

        for record in self:

            if record.state == "paid":

                raise UserError(
                    _(
                        "Un encaissement déjà validé "
                        "ne peut pas être annulé ici."
                    )
                )

            record.state = "cancelled"

        return True

    # ==========================================================
    # REMETTRE EN ATTENTE
    # ==========================================================

    def action_set_pending(self):

        for record in self:

            if record.payment_id:

                raise UserError(
                    _(
                        "Impossible de remettre cette ligne "
                        "en attente car un paiement existe."
                    )
                )

            record.state = "pending"

        return True

    # ==========================================================
    # PROTECTION DES ENCAISSEMENTS VALIDÉS
    # ==========================================================

    def write(self, vals):

        protected_fields = {
            "meeting_id",
            "subscription_id",
            "subscription_line_id",
            "amount",
            "payment_method",
            "payment_reference",
        }

        if protected_fields.intersection(vals):

            for record in self:

                if record.state == "paid":

                    raise UserError(
                        _(
                            "Un encaissement validé "
                            "ne peut plus être modifié."
                        )
                    )
        self._check_meeting_not_closed()
        self._check_session_is_open()

        return super().write(vals)

    # ==========================================================
    # PROTECTION SUPPRESSION
    # ==========================================================

    def unlink(self):

        for record in self:

            if record.state == "paid":

                raise UserError(
                    _(
                        "Un encaissement validé "
                        "ne peut pas être supprimé."
                    )
                )
        self._check_meeting_not_closed()
        self._check_session_is_open()

        return super().unlink()

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
                    "Cette information ne peut plus être modifiée."
                )
            )

    def _check_session_is_open(self):
        locked_records = self.filtered(
            lambda record: record.session_id
            and record.session_id.state in ("closed", "cancelled")
        )

        if locked_records:
            raise UserError(_("La session de cotisation est verrouillée."))

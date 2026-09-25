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
from odoo.exceptions import UserError, ValidationError


class AssociationPayment(models.Model):
    _name = "association.payment"
    _description = "Paiement d'association"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "payment_date desc, id desc"
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
        tracking=True,
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
        string="Référence du paiement",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nouveau"),
        tracking=True,
        index=True,
    )

    description = fields.Text(
        string="Description",
    )

    # ==========================================================
    # MEMBRE
    # ==========================================================

    member_id = fields.Many2one(
        comodel_name="association.member",
        string="Membre",
        required=True,
        tracking=True,
        ondelete="restrict",
        index=True,
    )

    member_code = fields.Char(
        related="member_id.member_code",
        string="Code membre",
        readonly=True,
        store=True,
    )

    member_image_128 = fields.Image(
        related="member_id.image_128",
        string="Photo du membre",
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

    # ==========================================================
    # PAIEMENT
    # ==========================================================

    payment_date = fields.Date(
        string="Date de paiement",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
        index=True,
    )

    amount = fields.Monetary(
        string="Montant du paiement",
        currency_field="currency_id",
        required=True,
        default=0.0,
        tracking=True,
    )

    allocated_amount = fields.Monetary(
        string="Montant affecté",
        currency_field="currency_id",
        compute="_compute_payment_totals",
    )

    remaining_amount = fields.Monetary(
        string="Montant non affecté",
        currency_field="currency_id",
        compute="_compute_payment_totals",
    )

    payment_method = fields.Selection(
        selection="_get_payment_method_selection",
        string="Mode de paiement",
        required=True,
        default="cash",
        tracking=True,
        index=True,
    )

    @api.model
    def _get_payment_method_selection(self):
        parameters = self.env["ir.config_parameter"].sudo()
        methods = [
            ("cash", _("Espèces")),
            ("bank", _("Virement bancaire")),
            ("cheque", _("Chèque")),
            ("mobile_money", _("Mobile Money")),
            ("other", _("Autre")),
        ]
        return [
            (code, label)
            for code, label in methods
            if str(parameters.get_param(
                f"primetech_association.payment_method_{code}", "True"
            )).lower() not in ("false", "0")
        ] or [("cash", _("Espèces"))]

    payment_reference = fields.Char(
        string="Référence externe",
        tracking=True,
        help=(
            "Référence Mobile Money, numéro de chèque, "
            "référence bancaire ou autre référence externe."
        ),
    )

    state = fields.Selection(
        selection=[
            ("draft", "Brouillon"),
            ("collected", "Encaissé"),
            ("confirmed", "Validé"),
            ("cancelled", "Annulé"),
        ],
        string="Statut",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # ==========================================================
    # LIGNES DE PAIEMENT
    # ==========================================================

    line_ids = fields.One2many(
        comodel_name="association.payment.line",
        inverse_name="payment_id",
        string="Affectations du paiement",
        copy=True,
    )

    line_count = fields.Integer(
        string="Nombre de lignes",
        compute="_compute_payment_totals",
    )


    # ==========================================================
    # CYCLE DE COTISATION
    # ==========================================================

    subscription_period_id = fields.Many2one(
        comodel_name="association.subscription.period",
        string="Cycle de cotisation",
        ondelete="restrict",
        readonly=True,
        copy=False,
        index=True,
    )
    
    # ==========================================================
    # ORIGINE DU PAIEMENT
    # ==========================================================

    payment_source = fields.Selection(
        selection=[
            ("external", "Versement du membre"),
            ("member_account", "Compte membre"),
            (
                "meeting_cash",
                "Caisse temporaire de réunion",
            ),
        ],
        string="Origine du paiement",
        required=True,
        default="external",
        tracking=True,
    )

    meeting_id = fields.Many2one(
        comodel_name="association.meeting",
        string="Réunion d'encaissement",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )

    meeting_subscription_session_id = fields.Many2one(
        comodel_name="association.meeting.subscription.session",
        string="Session de cotisation en réunion",
        readonly=True,
        copy=False,
        ondelete="restrict",
        index=True,
    )

    member_account_id = fields.Many2one(
        comodel_name="association.member.account",
        string="Compte membre",
        domain="[('member_id', '=', member_id)]",
        tracking=True,
    )

    defer_member_account_debit = fields.Boolean(
        string="Débit compte membre à la finalisation",
        default=False, readonly=True, copy=False,
        help="Le débit est conservé temporairement dans la session de réunion et exécuté à sa finalisation.",
    )

    member_account_balance = fields.Monetary(
        string="Solde du compte membre",
        currency_field="currency_id",
        compute="_compute_member_account_balance",
    )

    # ==========================================================
    # COMPTE DE VERSEMENT
    # ==========================================================

    receipt_account_id = fields.Many2one(
        comodel_name="association.fund",
        string="Compte de versement",
        domain="[('active', '=', True), ('company_id', '=', company_id)]",
        tracking=True,
        index=True,
    )

    receipt_account_type = fields.Selection(
        related="receipt_account_id.fund_type",
        string="Type de compte",
        readonly=True,
    )

    receipt_account_balance = fields.Monetary(
        related="receipt_account_id.current_balance",
        string="Solde du compte",
        currency_field="currency_id",
        readonly=True,
    )

    # ==========================================================
    # AFFECTATION
    # ==========================================================

    has_allocations = fields.Boolean(
        string="Affecter à des cotisations",
        default=False,
        tracking=True,
    )

    # ==========================================================
    # SURPLUS
    # ==========================================================

    surplus_processed = fields.Boolean(
        string="Surplus traité",
        default=False,
        copy=False,
    )

    refund_amount = fields.Monetary(
        string="Montant remboursé",
        currency_field="currency_id",
        default=0.0,
        readonly=True,
        copy=False,
    )

    processed_surplus_amount = fields.Monetary(
        string="Surplus traité",
        currency_field="currency_id",
        default=0.0,
        readonly=True,
        copy=False,
    )

    surplus_action = fields.Selection(
        [("member_account", "Crédité au compte membre"),
         ("refund", "Remboursé")],
        string="Destination du surplus",
        readonly=True,
        copy=False,
    )
    # ==========================================================
    # NOTES
    # ==========================================================

    note = fields.Html(
        string="Notes internes",
    )

    # ==========================================================
    # CRÉATION DU MOUVEMENT DU COMPTE DE VERSEMENT
    # ==========================================================

    def _create_receipt_fund_transaction(self):

        Transaction = self.env[
            "association.fund.transaction"
        ]

        for record in self:

            # Les cotisations sont d'abord conservées dans la caisse du
            # cycle. Elles ne doivent jamais créer un mouvement de trésorerie
            # au moment de l'encaissement, quelle que soit leur origine.
            # Seul l'assistant de clôture du cycle verse le reliquat décidé.
            if (
                record.payment_source != "external"
                or record.subscription_period_id
                or record.has_allocations
                or record.line_ids
            ):
                continue

            if not record.receipt_account_id:
                raise ValidationError(
                    _(
                        "Vous devez sélectionner "
                        "un compte de versement."
                    )
                )

            existing_transaction = Transaction.search(
                [
                    (
                        "payment_id",
                        "=",
                        record.id,
                    ),
                    (
                        "transaction_type",
                        "=",
                        "in",
                    ),
                ],
                limit=1,
            )

            if existing_transaction:
                continue

            amount_to_deposit = record.amount
            if record.surplus_action == "refund":
                amount_to_deposit -= record.processed_surplus_amount

            if amount_to_deposit <= 0:
                continue

            transaction = Transaction.create(
                {
                    "fund_id": record.receipt_account_id.id,
                    "transaction_type": "in",
                    "amount": amount_to_deposit,
                    "transaction_date": record.payment_date,
                    "description": _(
                        "Encaissement paiement %s - %s"
                    )
                    % (
                        record.name,
                        record.member_id.display_name,
                    ),
                    "company_id": record.company_id.id,
                    "payment_id": record.id,
                }
            )

            transaction.action_validate()

        return True

    def _create_penalty_fund_transactions(self):
        """Track the penalty supplement separately from subscription capital."""
        Transaction = self.env["association.fund.transaction"]
        created_transactions = Transaction
        for payment in self:
            amounts_by_account = {}
            previous_paid_by_cycle = {}
            processed_paid_by_cycle = {}
            for line in payment.line_ids.filtered("subscription_line_id"):
                subscription_line = line.subscription_line_id
                subscription = subscription_line.subscription_id
                account = subscription.penalty_account_id
                period = (
                    line.subscription_period_id
                    or payment.subscription_period_id
                )
                if not period:
                    continue
                cycle_key = (
                    subscription_line.id,
                    period.id,
                )
                if cycle_key not in previous_paid_by_cycle:
                    previous_paid_by_cycle[cycle_key] = (
                        line._get_period_paid_for_line(
                            subscription_line,
                            period,
                            exclude_payment=payment,
                        )
                    )
                    processed_paid_by_cycle[cycle_key] = 0.0
                already_paid = (
                    previous_paid_by_cycle[cycle_key]
                    + processed_paid_by_cycle[cycle_key]
                )
                breakdown = line._get_period_amount_breakdown_for_line(
                    subscription_line,
                    period,
                    current_amount=line.amount_paid or 0.0,
                    already_paid=already_paid,
                )
                penalty_due = breakdown[
                    "penalty_due_amount"
                ]
                if penalty_due <= 0:
                    processed_paid_by_cycle[cycle_key] += (
                        line.amount_paid
                        or 0.0
                    )
                    continue
                supplement = breakdown[
                    "penalty_current_amount"
                ]
                if supplement and not account:
                    raise ValidationError(_(
                        "Configurez le compte dédié aux pénalités sur la "
                        "cotisation %(subscription)s avant d'encaisser "
                        "le supplément de pénalité."
                    ) % {"subscription": subscription.display_name})
                if supplement:
                    details = amounts_by_account.setdefault(account, {
                        "amount": 0.0,
                        "subscriptions": self.env["association.subscription"],
                        "periods": self.env["association.subscription.period"],
                    })
                    details["amount"] += supplement
                    details["subscriptions"] |= subscription
                    details["periods"] |= period
                processed_paid_by_cycle[cycle_key] += (
                    line.amount_paid
                    or 0.0
                )
            for account, details in amounts_by_account.items():
                existing = Transaction.search([
                    ("origin_model", "=", "association.payment.penalty"),
                    ("origin_res_id", "=", payment.id),
                    ("fund_id", "=", account.id),
                    ("state", "!=", "cancelled"),
                ], limit=1)
                if existing:
                    continue
                subscription_names = ", ".join(
                    details["subscriptions"].mapped("display_name")
                )
                period_names = ", ".join(
                    details["periods"].mapped("display_name")
                )
                transaction = Transaction.create({
                    "fund_id": account.id,
                    "transaction_type": "in",
                    "amount": details["amount"],
                    "transaction_date": payment.payment_date,
                    "description": _(
                        "Pénalité encaissée - Membre : %(member)s - "
                        "Cotisation : %(subscription)s - Cycle : %(period)s - "
                        "Paiement : %(payment)s"
                    ) % {
                        "member": payment.member_id.display_name,
                        "subscription": subscription_names,
                        "period": period_names,
                        "payment": payment.name,
                    },
                    "company_id": payment.company_id.id,
                    "payment_id": payment.id,
                    "origin_model": "association.payment.penalty",
                    "origin_res_id": payment.id,
                    "origin_reference": payment.name,
                })
                transaction.action_validate()
                created_transactions |= transaction
        return created_transactions

    # ==========================================================
    # SOLDE DU COMPTE MEMBRE
    # ==========================================================

    @api.depends(
        "member_id",
        "member_account_id",
    )
    def _compute_member_account_balance(self):

        for record in self:

            record.member_account_balance = 0.0

            account = record.member_account_id

            if not account and record.member_id:

                account = self.env[
                    "association.member.account"
                ].search(
                    [
                        (
                            "member_id",
                            "=",
                            record.member_id.id,
                        ),
                        (
                            "company_id",
                            "=",
                            record.company_id.id,
                        ),
                    ],
                    limit=1,
                )

            if account:

                record.member_account_balance = (
                    account.balance or 0.0
                )

    # ==========================================================
    # CONTRAINTES SQL
    # ==========================================================

    _sql_constraints = [
        (
            "association_payment_name_company_unique",
            "unique(name, company_id)",
            "La référence du paiement doit être unique par filiale.",
        ),
        (
            "association_payment_amount_positive",
            "CHECK(amount >= 0)",
            "Le montant du paiement ne peut pas être négatif.",
        ),
    ]

    # ==========================================================
    # CALCUL DES TOTAUX
    # ==========================================================

    @api.depends(
        "amount",
        "line_ids",
        "line_ids.amount_paid",
    )
    def _compute_payment_totals(self):

        for record in self:

            allocated_amount = sum(
                record.line_ids.mapped(
                    "amount_paid"
                )
            )

            record.line_count = len(
                record.line_ids
            )

            record.allocated_amount = (
                allocated_amount
            )

            record.remaining_amount = max(
                (record.amount or 0.0)
                - allocated_amount,
                0.0,
            )

    # ==========================================================
    # ONCHANGE - MEMBRE
    # ==========================================================

    @api.onchange("member_id")
    def _onchange_member_id(self):

        for record in self:

            record.line_ids = [
                (5, 0, 0)
            ]

            record.member_account_id = False
            record.receipt_account_id = False

            if not record.member_id:
                continue

            record.company_id = (
                record.member_id.company_id
            )

            account = self.env[
                "association.member.account"
            ].search(
                [
                    (
                        "member_id",
                        "=",
                        record.member_id.id,
                    ),
                    (
                        "company_id",
                        "=",
                        record.member_id.company_id.id,
                    ),
                ],
                limit=1,
            )

            if account:

                record.member_account_id = account


    # ==========================================================
    # ONCHANGE - ORIGINE DU PAIEMENT
    # ==========================================================

    @api.onchange("payment_source")
    def _onchange_payment_source(self):

        for record in self:

            # --------------------------------------------------
            # VERSEMENT EXTERNE
            # --------------------------------------------------

            if record.payment_source == "external":

                record.member_account_id = False

                # L'utilisateur choisira le compte financier
                # qui reçoit réellement le versement.
                record.receipt_account_id = False

                continue

            # --------------------------------------------------
            # COMPTE MEMBRE
            # --------------------------------------------------

            if record.payment_source == "member_account":

                # Aucun compte de trésorerie ne doit être utilisé.
                record.receipt_account_id = False

                # Une cotisation depuis le compte membre
                # doit obligatoirement être affectée.
                record.has_allocations = True

                # Recherche automatique du compte du membre.
                account = False

                if record.member_id:

                    account = self.env[
                        "association.member.account"
                    ].search(
                        [
                            (
                                "member_id",
                                "=",
                                record.member_id.id,
                            ),
                            (
                                "company_id",
                                "=",
                                record.company_id.id,
                            ),
                        ],
                        limit=1,
                    )

                record.member_account_id = account

                continue

            # --------------------------------------------------
            # AUCUNE ORIGINE
            # --------------------------------------------------

            record.receipt_account_id = False
            record.member_account_id = False
            record.has_allocations = False
    # ==========================================================
    # ONCHANGE - AFFECTATIONS
    # ==========================================================

    @api.onchange("has_allocations")
    def _onchange_has_allocations(self):

        for record in self:

            if not record.has_allocations:

                record.line_ids = [
                    (5, 0, 0)
                ]


    # ==========================================================
    # CONTRÔLE DE L'ORIGINE DU PAIEMENT
    # ==========================================================

    def _check_payment_source_values(self):

        for record in self:

            if record.payment_source == "external":

                if (
                    not record.subscription_period_id
                    and not record.has_allocations
                    and not record.receipt_account_id
                ):

                    raise ValidationError(
                        _(
                            "Vous devez sélectionner "
                            "le compte de versement."
                        )
                    )

            elif (
                record.payment_source
                == "member_account"
            ):

                if not record.member_account_id:

                    raise ValidationError(
                        _(
                            "Aucun compte membre "
                            "n'est disponible."
                        )
                    )

                if record.receipt_account_id:

                    raise ValidationError(
                        _(
                            "Un paiement depuis le compte "
                            "membre ne peut pas utiliser "
                            "un compte de trésorerie."
                        )
                    )

                if (
                    record.member_account_id.balance
                    < record.amount
                ):

                    raise ValidationError(
                        _(
                            "Solde du compte membre "
                            "insuffisant.\n\n"
                            "Disponible : %(balance).2f "
                            "%(currency)s"
                        )
                        % {
                            "balance":
                                record.member_account_id.balance,

                            "currency":
                                record.currency_id.name
                                or "",
                        }
                    )

            elif record.payment_source == "meeting_cash":

                if not record.meeting_id:
                    raise ValidationError(
                        _(
                            "Un encaissement temporaire doit être "
                            "rattaché à une réunion."
                        )
                    )

                if record.receipt_account_id:
                    raise ValidationError(
                        _(
                            "La caisse temporaire de réunion ne peut "
                            "pas mouvementer directement un compte "
                            "financier."
                        )
                    )
                
    def _limit_member_account_payment_to_balance(self):
        """Allow a member account to settle a subscription only up to its balance."""
        for record in self:
            if record.payment_source != "member_account":
                continue
            available_amount = record.member_account_id.balance or 0.0
            if available_amount <= 0:
                continue
            if record.amount <= available_amount:
                continue

            amount_left = available_amount
            for line in record.line_ids.sorted(key=lambda line: line.id):
                line_amount = min(line.amount_paid or 0.0, amount_left)
                line.write({"amount_paid": line_amount})
                amount_left -= line_amount

            record.write({"amount": available_amount})

    # ==========================================================
    # DÉBITER LE COMPTE MEMBRE
    # ==========================================================

    def _debit_member_account(self):

        for record in self:

            if (
                record.payment_source
                != "member_account"
            ):
                continue

            account = record.member_account_id

            if not account:

                raise ValidationError(
                    _("Compte membre introuvable.")
                )

            transaction = self.env[
                "association.member.account.transaction"
            ].create(
                {
                    "account_id":
                        account.id,

                    "transaction_type":
                        "debit",

                    "amount":
                        record.amount,

                    "transaction_date":
                        record.payment_date,

                    "description":
                        _(
                            "Paiement %(payment)s"
                        )
                        % {
                            "payment":
                                record.name,
                        },
                }
            )

            if hasattr(
                transaction,
                "action_confirm",
            ):

                transaction.action_confirm()
    
    
    # ==========================================================
    # INVALIDATION DES COTISATIONS ET CYCLES
    # ==========================================================

    def _invalidate_subscription_lines(self):

        # ======================================================
        # LIGNES DE COTISATION
        # ======================================================

        subscription_lines = self.line_ids.mapped(
            "subscription_line_id"
        )

        if subscription_lines:

            subscription_lines.invalidate_recordset([
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])

            subscription_lines.modified([
                "amount_paid",
                "balance",
                "payment_state",
                "payment_date",
            ])

        # ======================================================
        # CYCLES DE COTISATION CONCERNÉS
        # ======================================================

        periods = self.env[
            "association.subscription.period"
        ]

        subscriptions = subscription_lines.mapped(
            "subscription_id"
        )

        if subscriptions:

            periods = self.env[
                "association.subscription.period"
            ].search([
                (
                    "subscription_id",
                    "in",
                    subscriptions.ids,
                ),
                (
                    "state",
                    "=",
                    "running",
                ),
            ])

        # ======================================================
        # INVALIDATION DES STATISTIQUES DE CAGNOTTE
        # ======================================================

        if periods:

            period_fields = [
                field_name
                for field_name in (
                    "collected_amount",
                    "allocated_amount",
                    "available_amount",
                    "member_count",
                    "paid_member_count",
                    "partial_member_count",
                    "unpaid_member_count",
                    "recovery_rate",
                    "beneficiary_count",
                )
                if field_name in periods._fields
            ]

            if period_fields:

                periods.invalidate_recordset(
                    period_fields
                )

                periods.modified(
                    period_fields
                )

        return True
    # ==========================================================
    # CREATE
    # ==========================================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nouveau")) == _("Nouveau"):
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "association.payment"
                    )
                    or _("Nouveau")
                )

        return super().create(vals_list)

    # ==========================================================
    # ONCHANGE MEMBRE
    # ==========================================================

    @api.onchange("member_id")
    def _onchange_member_id(self):
        for record in self:
            if record.member_id:
                record.company_id = record.member_id.company_id

            record.line_ids = [(5, 0, 0)]


    # ==========================================================
    # ONCHANGE
    # ==========================================================

    @api.onchange(
        "line_ids",
        "line_ids.amount_paid",
    )
    def _onchange_line_ids(self):

        # Le montant du paiement représente
        # le montant réellement reçu du membre.
        #
        # Il ne doit jamais être remplacé automatiquement
        # par le montant affecté aux cotisations.

        return

    # ==========================================================
    # CONTRAINTES MÉTIER
    # ==========================================================

    @api.constrains("member_id", "company_id")
    def _check_member_company(self):
        for record in self:
            if (
                record.member_id
                and record.company_id
                and record.member_id.company_id
                != record.company_id
            ):
                raise ValidationError(
                    _(
                        "Le membre et le paiement doivent appartenir "
                        "à la même filiale."
                    )
                )

    @api.constrains(
        "amount",
        "line_ids",
        "line_ids.amount_paid",
    )
    def _check_allocated_amount(self):
        for record in self:
            allocated_amount = sum(
                record.line_ids.mapped("amount_paid")
            )

            if allocated_amount > record.amount:
                raise ValidationError(
                    _(
                        "Le montant total affecté (%(allocated)s) "
                        "ne peut pas dépasser le montant du paiement "
                        "(%(amount)s)."
                    )
                    % {
                        "allocated": allocated_amount,
                        "amount": record.amount,
                    }
                )

    # ==========================================================
    # CRÉDITER ET VALIDER LE COMPTE MEMBRE
    # ==========================================================

    def _credit_member_account(
        self,
        amount,
        description=False,
    ):

        self.ensure_one()

        amount = amount or 0.0

        # ======================================================
        # CONTRÔLE DU MONTANT
        # ======================================================

        if amount <= 0:
            return False

        if not self.member_id:
            raise ValidationError(
                _(
                    "Aucun membre n'est associé "
                    "au paiement."
                )
            )

        # ======================================================
        # MODÈLES
        # ======================================================

        Account = self.env[
            "association.member.account"
        ]

        Transaction = self.env[
            "association.member.account.transaction"
        ]

        # ======================================================
        # RECHERCHE DU COMPTE MEMBRE
        # ======================================================

        account = Account.search(
            [
                (
                    "member_id",
                    "=",
                    self.member_id.id,
                ),
                (
                    "company_id",
                    "=",
                    self.company_id.id,
                ),
            ],
            limit=1,
        )

        # ======================================================
        # CRÉATION DU COMPTE SI NÉCESSAIRE
        # ======================================================

        if not account:

            account = Account.create(
                {
                    "member_id":
                        self.member_id.id,

                    "company_id":
                        self.company_id.id,
                }
            )

        # ======================================================
        # ÉVITER LE DOUBLE CRÉDIT
        # ======================================================

        existing_transaction = Transaction.search(
            [
                (
                    "account_id",
                    "=",
                    account.id,
                ),
                (
                    "payment_id",
                    "=",
                    self.id,
                ),
                (
                    "transaction_type",
                    "=",
                    "credit",
                ),
            ],
            limit=1,
        )

        if existing_transaction:

            return existing_transaction

        # ======================================================
        # CRÉATION DU MOUVEMENT DE CRÉDIT
        # ======================================================

        transaction = Transaction.create(
            {
                "account_id":
                    account.id,

                "transaction_type":
                    "credit",

                "amount":
                    amount,

                "transaction_date":
                    fields.Datetime.now(),

                "payment_id":
                    self.id,

                "description":
                    description
                    or _(
                        "Approvisionnement depuis "
                        "le paiement %(payment)s"
                    )
                    % {
                        "payment":
                            self.display_name,
                    },
            }
        )

        # ======================================================
        # VALIDATION RÉELLE DU MOUVEMENT
        #
        # ON UTILISE LE WORKFLOW DISPONIBLE
        # SUR LE MODÈLE DE TRANSACTION
        # ======================================================

        if hasattr(
            transaction,
            "action_validate",
        ):

            transaction.action_validate()

        elif hasattr(
            transaction,
            "action_post",
        ):

            transaction.action_post()

        elif hasattr(
            transaction,
            "action_confirm",
        ):

            transaction.action_confirm()

        # ======================================================
        # VÉRIFICATION DU MOUVEMENT
        # ======================================================

        transaction.invalidate_recordset()

        # ======================================================
        # ACTUALISATION DU COMPTE
        # ======================================================

        account.invalidate_recordset()

        if "balance" in account._fields:

            account.invalidate_recordset(
                [
                    "balance",
                ]
            )

            account.modified(
                [
                    "balance",
                ]
            )

        # ======================================================
        # ACTUALISATION DU MEMBRE
        # ======================================================

        self.member_id.invalidate_recordset()

        if "balance" in self.member_id._fields:

            self.member_id.invalidate_recordset(
                [
                    "balance",
                ]
            )

        return transaction
    
    # ==========================================================
    # ACTION - CHARGER LES COTISATIONS DISPONIBLES
    # ==========================================================

    def action_generate_subscription_lines(self):

        SubscriptionLine = self.env[
            "association.subscription.line"
        ]

        PaymentLine = self.env[
            "association.payment.line"
        ]

        for record in self:

            if record.state != "draft":
                raise UserError(
                    _(
                        "Les cotisations peuvent uniquement "
                        "être chargées sur un paiement "
                        "en brouillon."
                    )
                )

            if not record.member_id:
                raise UserError(
                    _("Veuillez sélectionner un membre.")
                )

            # ======================================================
            # COTISATIONS AUXQUELLES LE MEMBRE APPARTIENT
            # ======================================================

            subscription_lines = SubscriptionLine.search(
                [
                    (
                        "member_id",
                        "=",
                        record.member_id.id,
                    ),
                    (
                        "subscription_id.company_id",
                        "=",
                        record.company_id.id,
                    ),
                ]
            )

            # ======================================================
            # CONSERVER LES CYCLES EN COURS OU TERMINÉS NON SOLDÉS
            # ======================================================

            existing_pairs = {
                (
                    line.subscription_line_id.id,
                    line.subscription_period_id.id,
                )
                for line in record.line_ids
                if (
                    line.subscription_line_id
                    and line.subscription_period_id
                )
            }

            new_lines = []

            for subscription_line in subscription_lines:

                periods = PaymentLine._get_unsettled_periods_for_line(
                    subscription_line
                )

                for period in periods:

                    pair = (
                        subscription_line.id,
                        period.id,
                    )

                    if pair in existing_pairs:
                        continue

                    existing_pairs.add(pair)

                    new_lines.append(
                        (
                            0,
                            0,
                            {
                                "subscription_line_id":
                                    subscription_line.id,

                                "subscription_id":
                                    subscription_line.subscription_id.id,

                                "subscription_period_id":
                                    period.id,

                                "amount_paid":
                                    0.0,
                            },
                        )
                    )

            if not new_lines:
                raise UserError(
                    _(
                        "Aucune cotisation disponible n'a été "
                        "trouvée pour le membre %(member)s.\n\n"
                        "Le membre doit appartenir à la cotisation "
                        "et posséder au moins un cycle en cours ou "
                        "terminé avec un solde restant."
                    )
                    % {
                        "member":
                            record.member_id.display_name,
                    }
                )

            record.write({
                "line_ids": new_lines,
            })

            record.message_post(
                body=_(
                    "%(count)s cycle(s) de cotisation non soldé(s) "
                    "chargé(s) pour %(member)s."
                )
                % {
                    "count":
                        len(new_lines),

                    "member":
                        record.member_id.display_name,
                }
            )

        return True

    # ==========================================================
    # ACTION - RÉPARTITION AUTOMATIQUE
    # ==========================================================

    def action_auto_allocate(self):
        for record in self:
            if record.state != "draft":
                raise UserError(
                    _(
                        "La répartition automatique est uniquement "
                        "possible sur un paiement en brouillon."
                    )
                )

            if record.amount <= 0:
                raise UserError(
                    _(
                        "Le montant du paiement doit être supérieur "
                        "à zéro."
                    )
                )

            if not record.line_ids:
                raise UserError(
                    _(
                        "Chargez d'abord les cotisations du membre."
                    )
                )

            remaining_amount = record.amount

            lines = record.line_ids.sorted(
                key=lambda line: (
                    (
                        line.subscription_period_id.due_date
                        if line.subscription_period_id
                        else fields.Date.today()
                    ),
                    line.id or 0,
                )
            )

            for line in lines:
                balance_to_pay = max(
                    line.balance_before_payment or 0.0,
                    0.0,
                )

                amount_to_allocate = min(
                    remaining_amount,
                    balance_to_pay,
                )

                line.amount_paid = amount_to_allocate

                remaining_amount -= amount_to_allocate

                if remaining_amount <= 0:
                    remaining_amount = 0.0

            record.message_post(
                body=_(
                    "Le montant du paiement a été réparti "
                    "automatiquement sur les cotisations."
                )
            )

        return True

    
    # ==========================================================
    # ACTION - ENCAISSER
    # ==========================================================

    def action_collect(self):

        for record in self:

            # ======================================================
            # CONTRÔLES
            # ======================================================

            if record.state != "draft":

                raise UserError(
                    _(
                        "Seul un paiement en brouillon "
                        "peut être encaissé."
                    )
                )

            if not record.member_id:

                raise ValidationError(
                    _("Veuillez sélectionner un membre.")
                )

            if record.amount <= 0:

                raise ValidationError(
                    _(
                        "Le montant reçu doit être "
                        "strictement supérieur à zéro."
                    )
                )

            record._limit_member_account_payment_to_balance()

            # ======================================================
            # PASSAGE ENCAISSÉ
            #
            # IMPORTANT :
            # AUCUN IMPACT COTISATION
            # AUCUN IMPACT COMPTE MEMBRE
            # ======================================================

            record.write(
                {
                    "state": "collected",
                }
            )

            record.message_post(
                body=_(
                    "Encaissement enregistré.<br/>"
                    "Montant reçu : %(amount).2f %(currency)s.<br/>"
                    "Le paiement est en attente de validation."
                )
                % {
                    "amount":
                        record.amount,

                    "currency":
                        record.currency_id.name or "",
                }
            )

        return True    
    
    # ==========================================================
    # ACTION - VALIDER LE PAIEMENT
    # ==========================================================

    def action_confirm(self):

        for record in self:

            # ======================================================
            # CONTRÔLE ÉTAT
            # SEUL UN PAIEMENT ENCAISSÉ PEUT ÊTRE VALIDÉ
            # ======================================================

            if record.state != "collected":

                raise UserError(
                    _(
                        "Seul un paiement encaissé "
                        "peut être validé."
                    )
                )

            record._limit_member_account_payment_to_balance()

            # ======================================================
            # CONTRÔLE MONTANT
            # ======================================================

            if record.amount <= 0:

                raise ValidationError(
                    _(
                        "Le montant du paiement doit être "
                        "strictement supérieur à zéro."
                    )
                )

            # ======================================================
            # LIGNES DE COTISATION CHOISIES
            # ======================================================

            subscription_lines = (
                record.line_ids
                .mapped("subscription_line_id")
                .filtered(lambda line: line)
            )

            # ======================================================
            # MONTANT AFFECTÉ
            # ======================================================

            allocated_amount = sum(
                record.line_ids.mapped(
                    "amount_paid"
                )
            )

            # ======================================================
            # CONTRÔLE DU MONTANT AFFECTÉ
            # ======================================================

            if allocated_amount < 0:

                raise ValidationError(
                    _(
                        "Le montant affecté ne peut pas "
                        "être négatif."
                    )
                )

            if allocated_amount > record.amount:

                raise ValidationError(
                    _(
                        "Le montant affecté aux cotisations "
                        "ne peut pas dépasser le montant "
                        "du paiement."
                    )
                )

            # ======================================================
            # CONTRÔLE DES AFFECTATIONS
            # ======================================================

            if record.has_allocations:

                if not record.line_ids:

                    raise ValidationError(
                        _(
                            "Vous avez choisi d'affecter "
                            "le paiement à des cotisations, "
                            "mais aucune cotisation "
                            "n'a été sélectionnée."
                        )
                    )

                invalid_lines = (
                    record.line_ids.filtered(
                        lambda line: (
                            not line.subscription_line_id
                            or
                            (line.amount_paid or 0.0) <= 0
                        )
                    )
                )

                if invalid_lines:

                    raise ValidationError(
                        _(
                            "Chaque ligne d'affectation doit "
                            "contenir une cotisation et un "
                            "montant strictement supérieur "
                            "à zéro."
                        )
                    )

            # ======================================================
            # CONTRÔLE DES COTISATIONS
            # ======================================================

            allocated_by_cycle = {}

            for line in record.line_ids:

                subscription_line = (
                    line.subscription_line_id
                )

                if not subscription_line:
                    continue

                subscription = (
                    subscription_line.subscription_id
                )

                period = line.subscription_period_id

                # ==================================================
                # CONTRÔLE DU CYCLE
                # ==================================================

                if not period:

                    raise ValidationError(
                        _(
                            "Sélectionnez le cycle à régler "
                            "pour la cotisation "
                            "%(subscription)s."
                        )
                        % {
                            "subscription":
                                subscription.display_name,
                        }
                    )

                if period.state not in (
                    "running",
                    "closed",
                ):

                    raise ValidationError(
                        _(
                            "Le cycle %(cycle)s de la "
                            "cotisation %(subscription)s "
                            "n'est ni en cours ni terminé."
                        )
                        % {
                            "cycle":
                                period.display_name,

                            "subscription":
                                subscription.display_name,
                        }
                    )

                # ==================================================
                # PAIEMENTS DÉJÀ VALIDÉS DU CYCLE
                #
                # IMPORTANT :
                # Le paiement actuel est exclu.
                # ==================================================

                already_paid = line._get_period_paid_for_line(
                    subscription_line,
                    period,
                    exclude_payment=record,
                )

                # ==================================================
                # MONTANT TOTAL DÛ SUR LE CYCLE SÉLECTIONNÉ
                # ==================================================

                total_due = line._get_period_due_for_line(
                    subscription_line,
                    period,
                )

                # ==================================================
                # RESTE RÉEL AVANT LE PAIEMENT ACTUEL
                # ==================================================

                remaining_amount = max(
                    total_due - already_paid,
                    0.0,
                )

                # ==================================================
                # COTISATION DÉJÀ RÉGLÉE
                # ==================================================

                if remaining_amount <= 0:

                    raise ValidationError(
                        _(
                            "La cotisation %(subscription)s "
                            "est déjà réglée pour le cycle "
                            "%(cycle)s."
                        )
                        % {
                            "subscription":
                                subscription.display_name,

                            "cycle":
                                period.display_name,
                        }
                    )

                # ==================================================
                # CONTRÔLE DU MONTANT AFFECTÉ
                # ==================================================

                if (
                    line.amount_paid or 0.0
                ) > remaining_amount:

                    raise ValidationError(
                        _(
                            "Le montant affecté à %(member)s "
                            "dépasse le reste à payer.\n\n"
                            "Cotisation : %(subscription)s\n"
                            "Montant dû : "
                            "%(total_due).2f %(currency)s\n"
                            "Déjà payé : "
                            "%(already_paid).2f %(currency)s\n"
                            "Reste à payer : "
                            "%(balance).2f %(currency)s"
                        )
                        % {
                            "member":
                                subscription_line
                                .member_id
                                .display_name,

                            "subscription":
                                subscription.display_name,

                            "total_due":
                                total_due,

                            "already_paid":
                                already_paid,

                            "balance":
                                remaining_amount,

                            "currency":
                                record.currency_id.name
                                or "",
                        }
                    )

                cycle_key = (
                    subscription_line.id,
                    period.id,
                )

                allocated_by_cycle[cycle_key] = (
                    allocated_by_cycle.get(
                        cycle_key,
                        0.0,
                    )
                    + (line.amount_paid or 0.0)
                )

                if allocated_by_cycle[cycle_key] > remaining_amount + 0.01:

                    raise ValidationError(
                        _(
                            "Le total affecté à %(member)s dépasse "
                            "le reste à payer pour le cycle %(cycle)s.\n\n"
                            "Cotisation : %(subscription)s\n"
                            "Total affecté : "
                            "%(allocated).2f %(currency)s\n"
                            "Reste à payer : "
                            "%(balance).2f %(currency)s"
                        )
                        % {
                            "member":
                                subscription_line.member_id.display_name,

                            "cycle":
                                period.display_name,

                            "subscription":
                                subscription.display_name,

                            "allocated":
                                allocated_by_cycle[cycle_key],

                            "balance":
                                remaining_amount,

                            "currency":
                                record.currency_id.name
                                or "",
                        }
                    )

            # ======================================================
            # CONTRÔLE ORIGINE DU PAIEMENT
            #
            # - externe
            # - compte membre
            # ======================================================

            record._check_payment_source_values()

            # ======================================================
            # CALCUL DU SURPLUS
            # ======================================================

            surplus_amount = max(
                (record.amount or 0.0)
                - allocated_amount,
                0.0,
            )

            # ======================================================
            # TRAITEMENT DU SURPLUS
            #
            # Si le paiement comporte des affectations
            # et qu'un reste existe, le wizard doit obligatoirement
            # déterminer sa destination.
            # ======================================================

            if (
                record.has_allocations
                and surplus_amount > 0
                and not record.surplus_processed
            ):

                return {
                    "type": "ir.actions.act_window",
                    "name": _("Traitement du surplus"),
                    "res_model":
                        "association.payment.surplus.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {
                        "default_payment_id":
                            record.id,

                        "default_surplus_amount":
                            surplus_amount,
                    },
                }

            # ======================================================
            # CRÉATION DU MOUVEMENT DU COMPTE DE VERSEMENT
            #
            # Cette méthode doit gérer uniquement les versements
            # externes destinés à un compte financier.
            # ======================================================

            record._create_receipt_fund_transaction()

            # ======================================================
            # VALIDATION DU PAIEMENT
            #
            # À PARTIR D'ICI LE PAIEMENT DEVIENT COMPTABILISÉ
            # DANS LES COTISATIONS.
            # ======================================================

            record.write(
                {
                    "state": "confirmed",
                }
            )
            penalty_transactions = record._create_penalty_fund_transactions()

            SubscriptionPenaltyRecap = self.env[
                "association.subscription.penalty.recap"
            ]

            for line in record.line_ids.filtered("subscription_line_id"):

                period = (
                    line.subscription_period_id
                    or record.subscription_period_id
                )

                if period:

                    SubscriptionPenaltyRecap._sync_for_line_period(
                        line.subscription_line_id,
                        period,
                    )

            # ======================================================
            # PAIEMENT DEPUIS LE COMPTE MEMBRE
            #
            # Le membre paie ses cotisations uniquement depuis
            # son compte membre.
            # ======================================================

            if (
                record.payment_source == "member_account"
                and not record.defer_member_account_debit
            ):

                record._debit_member_account()

            # ======================================================
            # VERSEMENT EXTERNE SANS AFFECTATION
            #
            # Aucun règlement de cotisation.
            # Le montant approvisionne directement le compte membre.
            # ======================================================

            if (
                record.payment_source == "external"
                and not record.has_allocations
            ):

                record._credit_member_account(
                    record.amount
                )

            # ======================================================
            # ACTUALISATION DES LIGNES DE COTISATION
            #
            # Le paiement est maintenant CONFIRMED.
            # Le compute peut donc le prendre en compte.
            # ======================================================

            if subscription_lines:

                subscription_lines.invalidate_recordset(
                    [
                        "amount_due",
                        "amount_paid",
                        "balance",
                        "payment_state",
                        "payment_date",
                    ]
                )

                subscription_lines.modified(
                    [
                        "amount_due",
                        "amount_paid",
                        "balance",
                        "payment_state",
                        "payment_date",
                    ]
                )

            if record.meeting_id:
                meeting_fields = [
                    "collection_count",
                    "collection_paid_count",
                    "collection_pending_count",
                    "collection_total",
                    "pot_collected_amount",
                    "pot_allocated_amount",
                    "pot_available_amount",
                    "pot_beneficiary_count",
                ]
                record.meeting_id.invalidate_recordset(meeting_fields)
                record.meeting_id.modified(meeting_fields)

            # ======================================================
            # IMPORTANT
            # NE PAS RECRÉDITER AUTOMATIQUEMENT LE SURPLUS
            #
            # Le surplus a déjà été traité par le wizard :
            #
            # - compte membre
            # - compte financier
            # - remboursement
            #
            # L'ancien bloc :
            #
            # if surplus_amount > 0:
            #     record._credit_member_account(surplus_amount)
            #
            # EST SUPPRIMÉ.
            #
            # Sinon le surplus serait crédité deux fois.
            # ======================================================

            # ======================================================
            # MESSAGE
            # ======================================================

            message = _(
                "Le paiement a été validé."
            )

            if record.has_allocations:

                message += _(
                    "<br/>Montant affecté aux cotisations : "
                    "%(amount).2f %(currency)s"
                ) % {
                    "amount":
                        allocated_amount,

                    "currency":
                        record.currency_id.name
                        or "",
                }

            if surplus_amount > 0:

                message += _(
                    "<br/>Surplus traité : "
                    "%(amount).2f %(currency)s"
                ) % {
                    "amount":
                        surplus_amount,

                    "currency":
                        record.currency_id.name
                        or "",
                }

            penalty_transferred = sum(penalty_transactions.mapped("amount"))
            if penalty_transferred > 0:
                message += _(
                    "<br/>Pénalité automatiquement reversée sur le "
                    "compte dédié : %(amount).2f %(currency)s"
                ) % {
                    "amount": penalty_transferred,
                    "currency": record.currency_id.name or "",
                }

            record.message_post(
                body=message
            )

        return True 
        
    
    
    # ==========================================================
    # ACTION - ANNULER
    # ==========================================================

    def action_cancel(self):
        for record in self:
            if record.state == "cancelled":
                continue

            record.write({
                "state": "cancelled",
            })

            penalty_transactions = self.env[
                "association.fund.transaction"
            ].search([
                ("origin_model", "=", "association.payment.penalty"),
                ("origin_res_id", "=", record.id),
                ("state", "!=", "cancelled"),
            ])
            penalty_transactions.action_cancel()

            record._invalidate_subscription_lines()

            SubscriptionPenaltyRecap = self.env[
                "association.subscription.penalty.recap"
            ]

            for line in record.line_ids.filtered("subscription_line_id"):

                period = (
                    line.subscription_period_id
                    or record.subscription_period_id
                )

                if period:

                    SubscriptionPenaltyRecap._sync_for_line_period(
                        line.subscription_line_id,
                        period,
                    )

            record.message_post(
                body=_(
                    "Le paiement a été annulé."
                )
            )

        return True

    # ==========================================================
    # ACTION - REMETTRE EN BROUILLON
    # ==========================================================

    def action_reset_draft(self):
        for record in self:
            if record.state != "cancelled":
                raise UserError(
                    _(
                        "Seul un paiement annulé peut être "
                        "remis en brouillon."
                    )
                )

            record.write({
                "state": "draft",
            })

            record._invalidate_subscription_lines()

            record.message_post(
                body=_(
                    "Le paiement a été remis en brouillon."
                )
            )

        return True

    # ==========================================================
    # CONTRÔLE DU MONTANT
    # ==========================================================

    @api.constrains("amount")
    def _check_amount(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(
                    _(
                        "Le montant du paiement ne peut pas "
                        "être négatif."
                    )
                )

    # ==========================================================
    # WRITE
    # ==========================================================

    def write(self, vals):
        protected_fields = {
            "member_id",
            "company_id",
            "payment_date",
            "amount",
            "payment_method",
            "payment_reference",
            "line_ids",
        }

        if protected_fields.intersection(vals):
            confirmed_records = self.filtered(
                lambda record: record.state == "confirmed"
            )

            if confirmed_records:
                raise UserError(
                    _(
                        "Un paiement confirmé ne peut plus "
                        "être modifié."
                    )
                )

        return super().write(vals)
    
    # ==========================================================
    # ACTION - VOIR LES AFFECTATIONS
    # ==========================================================

    def action_view_payment_lines(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Affectations du paiement"),
            "res_model": "association.payment.line",
            "view_mode": "list,form",
            "domain": [
                (
                    "payment_id",
                    "=",
                    self.id,
                ),
            ],
            "context": {
                "default_payment_id": self.id,
                "create": self.state == "draft",
            },
        }

    def action_print_receipt(self):
        """Print the A5 receipt of a collected or validated receipt."""
        self.ensure_one()
        if self.state not in ("collected", "confirmed"):
            raise UserError(_("Le reçu est disponible après l'encaissement."))
        return self.env.ref(
            "primetech_association.action_report_payment_receipt"
        ).report_action(self)

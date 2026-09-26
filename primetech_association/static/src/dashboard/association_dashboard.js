/** @odoo-module **/

import {
    Component,
    markup,
    onWillStart,
    useState,
} from "@odoo/owl";

import {
    registry,
} from "@web/core/registry";

import {
    useService,
} from "@web/core/utils/hooks";


export class AssociationDashboard extends Component {

    static template =
        "primetech_association.AssociationDashboard";

    setup() {

        this.orm = useService("orm");

        this.action = useService("action");

        this.state = useState({

            loading: true,

            data: {
                company: {},
                members: {},
                meetings: {},
                subscriptions: {},
                payments: {},
                expenses: {breakdown: []},
                treasury: {},
                penalties: {recent: []},
                recent_payments: [],
                next_meeting: false,
                upcoming_meetings: [],
                recent_members: [],
                currency: {},
                paymentDetail: false,
                penaltyDetail: false,
                subscriptionDetail: false,
                treasuryDetail: false,
                minutesPreview: false,
            },
            filters: {period: "all", months: 6, date_from: "", date_to: ""},

        });

        onWillStart(
            async () => {

                await this.loadDashboard();

            }
        );

    }


    // =========================================================
    // CHARGEMENT
    // =========================================================

    async loadDashboard() {

        this.state.loading = true;

        try {

            const data = await this.orm.call(
                "association.dashboard",
                "get_dashboard_data",
                [this.state.filters],
            );

            this.state.data = data;

        } finally {

            this.state.loading = false;

        }

    }

    onPeriodChange(ev) {
        this.state.filters.period = ev.target.value;
        return this.loadDashboard();
    }

    onCustomDateChange(ev) {
        this.state.filters[ev.target.name] = ev.target.value;
        if (this.state.filters.period === "custom") {
            return this.loadDashboard();
        }
    }

    onMonthsChange(ev) {
        this.state.filters.months = Number(ev.target.value);
        return this.loadDashboard();
    }


    // =========================================================
    // FORMAT MONTANT
    // =========================================================

    formatAmount(amount) {

        const value = Number(
            amount || 0
        );

        return new Intl.NumberFormat(
            "fr-FR",
            {
                maximumFractionDigits: 0,
            }
        ).format(value);

    }

    todayLabel() {
        return new Intl.DateTimeFormat("fr-FR", {
            day: "2-digit", month: "short", year: "numeric",
        }).format(new Date());
    }

    get memberPercent() {
        const total = Number(this.state.data.members.total || 0);
        return total ? Math.round((Number(this.state.data.members.active || 0) / total) * 100) : 0;
    }

    get expensePrimaryPercent() {
        const first = (this.state.data.expenses.breakdown || [])[0];
        return first ? Number(first.percentage || 0) : 0;
    }

    get kpis() {
        const data = this.state.data;
        return [
            {label: "Membres actifs", value: this.formatAmount(data.members.active), icon: "fa-users", color: "purple", note: "Effectif actuel", action: "members"},
            {label: "Total membres", value: this.formatAmount(data.members.total), icon: "fa-user-plus", color: "green", note: "Base des adhérents", action: "members"},
            {label: "Cotisations collectées", value: this.formatAmount(data.payments.total), currency: true, icon: "fa-handshake-o", color: "orange", note: "Paiements confirmés", action: "payments"},
            {label: "Trésorerie", value: this.formatAmount(data.treasury.balance), currency: true, icon: "fa-credit-card", color: "blue", note: "Solde disponible", action: "treasury"},
            {label: "Événements", value: this.formatAmount(data.meetings.upcoming), icon: "fa-calendar", color: "purple", note: "À venir", action: "meetings"},
            {label: "Pénalités à traiter", value: this.formatAmount(data.penalties.pending), icon: "fa-gavel", color: "red", note: "À régulariser", negative: true, action: "penalties"},
        ];
    }

    get chartBars() {
        const months = this.state.data.payments.monthly || [];
        const maximum = Math.max(...months.map((item) => Number(item.amount)), 1);
        return months.map((item) => ({
            ...item,
            height: Math.max(3, Math.round(Number(item.amount) * 100 / maximum)),
        }));
    }

    get sections() {
        return this.state.data.members.categories || [];
    }


    // =========================================================
    // NAVIGATION
    // =========================================================

    async openAction(xmlId) {

        await this.action.doAction(xmlId);

    }

    openKpi(actionName) {
        const actions = {
            meetings: () => this.openMeetings(),
            members: () => this.openMembers(),
            payments: () => this.openPayments(),
            penalties: () => this.openPenalties(),
            treasury: () => this.openTreasury(),
        };
        return actions[actionName]?.();
    }

    onInteractiveKeydown(ev, callback) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            callback();
        }
    }


    openMembers() {

        return this.openAction(
            "primetech_association.action_association_member"
        );

    }

    createMember() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Nouveau membre",
            res_model: "association.member",
            views: [[false, "form"]],
            target: "current",
        });
    }


    openMeetings() {

        return this.openAction(
            "primetech_association.action_meeting"
        );

    }


    openSubscriptions() {

        return this.openAction(
            "primetech_association.action_subscription"
        );

    }


    openPayments() {

        return this.openAction(
            "primetech_association.action_payment"
        );

    }

    openExpenses() {
        return this.openAction(
            "primetech_association.action_expense"
        );
    }


    openTreasury() {

        return this.openAction(
            "primetech_association.action_association_fund"
        );

    }


    openPenalties() {

        return this.openAction(
            "primetech_association.action_penalty"
        );

    }

    openPenalty(penaltyId) {
        if (!penaltyId) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Sanction disciplinaire",
            res_model: "association.penalty",
            res_id: penaltyId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openMember(memberId) {
        return this.openRecord("association.member", memberId, "Membre");
    }

    openPayment(paymentId) {
        return this.openRecord("association.payment", paymentId, "Paiement");
    }

    get memberFinancialAlertLabel() {
        const alert = this.state.data.member?.financial_alert || {};
        const labels = [];
        const sanctions = Number(alert.sanction_count || 0);
        const penalties = Number(alert.penalty_count || 0);
        if (sanctions) {
            labels.push(`${sanctions} sanction${sanctions > 1 ? "s" : ""}`);
        }
        if (penalties) {
            labels.push(`${penalties} pénalité${penalties > 1 ? "s" : ""}`);
        }
        return labels.join(" · ");
    }

    get memberSanctionAlertLabel() {
        const count = Number(this.state.data.member?.financial_alert?.sanction_count || 0);
        return count ? `${count} sanction${count > 1 ? "s" : ""}` : "";
    }

    get memberPenaltyAlertLabel() {
        const count = Number(this.state.data.member?.financial_alert?.penalty_count || 0);
        return count ? `${count} pénalité${count > 1 ? "s" : ""}` : "";
    }

    async openMemberPayment(paymentId) {
        if (!paymentId) {
            return;
        }
        this.state.paymentDetail = await this.orm.call(
            "association.dashboard", "get_member_payment_detail", [paymentId]
        );
    }

    closeMemberPayment() {
        this.state.paymentDetail = false;
    }

    async openMemberPenalty(penaltyId) {
        if (!penaltyId) {
            return;
        }
        this.state.penaltyDetail = await this.orm.call(
            "association.dashboard", "get_member_penalty_detail", [penaltyId]
        );
    }

    closeMemberPenalty() {
        this.state.penaltyDetail = false;
    }

    async openMemberSubscription(subscriptionLineId) {
        this.state.subscriptionDetail = await this.orm.call(
            "association.dashboard", "get_member_subscription_detail", [subscriptionLineId]
        );
    }

    closeMemberSubscription() {
        this.state.subscriptionDetail = false;
    }

    async openMemberTreasury(fundId) {
        this.state.treasuryDetail = await this.orm.call(
            "association.dashboard", "get_member_treasury_detail", [fundId]
        );
    }

    closeMemberTreasury() {
        this.state.treasuryDetail = false;
    }

    async downloadSharedMinutes(meeting) {
        if (!meeting?.id) {
            return;
        }
        const reportAction = await this.orm.call(
            "association.dashboard", "get_member_minutes_download_action", [meeting.id]
        );
        if (reportAction) {
            return this.action.doAction(reportAction);
        }
    }

    async openMemberMinutes(meetingId) {
        if (!meetingId) {
            return;
        }
        const preview = await this.orm.call(
            "association.dashboard", "get_member_minutes_preview", [meetingId]
        );
        this.state.minutesPreview = preview && {
            ...preview,
            content: markup(preview.content || ""),
        };
    }

    closeMemberMinutes() {
        this.state.minutesPreview = false;
    }

    scrollToMemberSanctions() {
        const targets = document.querySelectorAll(".member_financial_sanction_target");
        document.querySelector(".member_sanctions_panel")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
        targets.forEach((target) => {
            target.classList.add("member_financial_sanction_focus");
            setTimeout(() => target.classList.remove("member_financial_sanction_focus"), 2200);
        });
    }

    scrollToMemberFinancialItem() {
        const alert = this.state.data.member?.financial_alert || {};
        if (Number(alert.penalty_count || 0)) {
            return this.scrollToMemberSubscriptionPenalties();
        }
        this.scrollToMemberSanctions();
    }

    scrollToMemberSubscriptionPenalties() {
        const targets = document.querySelectorAll(".member_subscription_penalty_target");
        document.querySelector(".member_subscriptions_panel")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
        });
        targets.forEach((target) => {
            target.classList.add("member_subscription_penalty_focus");
            setTimeout(() => target.classList.remove("member_subscription_penalty_focus"), 2200);
        });
    }

    openRecord(model, recordId, name) {
        if (!recordId) {
            return;
        }
        return this.action.doAction({
            type: "ir.actions.act_window",
            name,
            res_model: model,
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
        });
    }


    openMeeting(meetingId) {

        if (!meetingId) {
            return;
        }

        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Réunion",
            res_model: "association.meeting",
            res_id: meetingId,
            views: [
                [
                    false,
                    "form",
                ],
            ],
            target: "current",
        });

    }

}


registry
    .category("actions")
    .add(
        "primetech_association.dashboard",
        AssociationDashboard
    );

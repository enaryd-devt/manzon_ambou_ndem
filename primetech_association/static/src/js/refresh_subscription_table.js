/** @odoo-module **/

import { registry } from "@web/core/registry";

const actionRegistry = registry.category("actions");


async function refreshSubscriptionTable(env, action) {

    const params = action.params || {};

    const subscriptionId =
        params.subscription_id;

    const meetingId = params.meeting_id;
    const closeDialog = params.close_dialog !== false;

    const actionService =
        env.services.action;


    // =========================================================
    // FERMER LE WIZARD
    // =========================================================

    if (closeDialog) {
        await actionService.doAction({
            type: "ir.actions.act_window_close",
        });
    }


    // =========================================================
    // ATTENDRE LE RETOUR AU FORMULAIRE
    // =========================================================

    await new Promise(
        (resolve) => setTimeout(resolve, 150)
    );


    // =========================================================
    // CONTRÔLEUR PARENT
    // =========================================================

    const controller =
        actionService.currentController;

    if (
        !controller
        || !controller.model
        || !controller.model.root
    ) {
        return;
    }


    const model =
        controller.model;

    const root =
        model.root;


    // =========================================================
    // LISTE DE RECAP DES COTISATIONS DU MEMBRE
    // =========================================================

    if (root.resModel === "association.member.subscription.cycle.report") {
        if (typeof root.load === "function") {
            await root.load();
        } else if (typeof model.load === "function") {
            await model.load();
        }

        model.notify();
        return;
    }


    // =========================================================
    // FORMULAIRE COTISATION OU RÉUNION
    // =========================================================

    const isSubscriptionForm = root.resModel === "association.subscription";
    const isMeetingForm = root.resModel === "association.meeting";

    if (!isSubscriptionForm && !isMeetingForm) {
        return;
    }


    if (isSubscriptionForm &&
        subscriptionId
        && root.resId
        && root.resId !== subscriptionId
    ) {
        return;
    }

    if (isMeetingForm && meetingId && root.resId && root.resId !== meetingId) {
        return;
    }


    // =========================================================
    // RELECTURE ORM DU RECORD PARENT
    //
    // PAS DE RELOAD NAVIGATEUR
    // PAS DE RECHARGEMENT D'ACTION
    //
    // OWL RELIT LES VALEURS DU FORMULAIRE
    // ET MET À JOUR L'ONGLET COTISATIONS SANS RECHARGEMENT GLOBAL
    // =========================================================

    await root.load();


    // =========================================================
    // NOTIFIER OWL
    // =========================================================

    model.notify();
}


actionRegistry.add(
    "primetech_refresh_subscription_table",
    refreshSubscriptionTable
);

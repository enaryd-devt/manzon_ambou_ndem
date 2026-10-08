/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

patch(NavBar.prototype, {
    get isAssociationMemberOnly() {
        return Boolean(session.primetech_association_member_only);
    },

    _openAppMenuSidebar() {
        if (this.isAssociationMemberOnly) {
            return;
        }
        return super._openAppMenuSidebar(...arguments);
    },
});

/**
 * Keep the web-client application navigation hidden for the whole session of
 * an ordinary member, including before the dashboard's RPC has completed.
 */
registry.category("services").add("primetech_member_navigation_lock", {
    start() {
        if (session.primetech_association_member_only) {
            document.body.classList.add("o_association_member_only");
        }
    },
});

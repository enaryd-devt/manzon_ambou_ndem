/** @odoo-module **/

import { registry } from "@web/core/registry";

const meetingLiveSync = {
    dependencies: ["bus_service", "action", "orm"],
    start(env, { bus_service, action, orm }) {
        let saveTimer;

        const getActiveMeeting = () => {
            const root = action.currentController?.model?.root;
            return root?.resModel === "association.meeting" && root.resId ? root : false;
        };

        const persistAndBroadcast = async () => {
            const root = getActiveMeeting();
            if (!root) {
                return;
            }
            try {
                // Every field and editable-list change is persisted before
                // notifying the other users currently viewing the meeting.
                if (root.isDirty && typeof root.save === "function") {
                    await root.save();
                }
                await orm.call("association.meeting", "action_broadcast_live_sync", [[root.resId]]);
            } catch {
                // Native Odoo validation keeps the error handling in the form.
            }
        };

        const schedulePersist = (delay = 700) => {
            window.clearTimeout(saveTimer);
            saveTimer = window.setTimeout(persistAndBroadcast, delay);
        };

        document.addEventListener("input", () => schedulePersist(900), true);
        document.addEventListener("change", () => schedulePersist(350), true);
        document.addEventListener("click", (event) => {
            if (event.target.closest("button")) {
                schedulePersist(650);
            }
        }, true);

        bus_service.addChannel("primetech_association_meeting_sync");
        bus_service.addEventListener("notification", async ({ detail: notifications }) => {
            for (const notification of notifications) {
                if (notification.type !== "primetech_association_meeting_sync") {
                    continue;
                }
                const meetingId = notification.payload?.meeting_id;
                const root = action.currentController?.model?.root;
                if (
                    root?.resModel === "association.meeting" &&
                    root.resId === meetingId &&
                    notification.payload?.sender_id !== env.services.user?.userId &&
                    !root.isDirty
                ) {
                    await root.load();
                    action.currentController.model.notify();
                }
            }
        });
    },
};

registry.category("services").add(
    "primetech_association_meeting_live_sync",
    meetingLiveSync,
);

/** @odoo-module **/

import { onMounted, onWillDestroy, useState } from "@odoo/owl";
import { AppsBar } from "@muk_web_appsbar/webclient/appsbar/appsbar";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { useBus } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { NavBar } from "@web/webclient/navbar/navbar";

const TOGGLE_EVENT = "ALGORITHMA:NAVIGATION-TOGGLE";
const STATE_EVENT = "ALGORITHMA:NAVIGATION-STATE";
const SIDEBAR_TYPES = ["large", "small", "invisible"];

function sidebarType() {
    const root = document.querySelector(".o_web_client");
    return SIDEBAR_TYPES.find((type) => root?.classList.contains(`mk_sidebar_type_${type}`));
}

function storageKey() {
    return session.db && user.userId
        ? `algorithma.navigation.sidebar.v1:${encodeURIComponent(session.db)}:${user.userId}`
        : null;
}

function initialCollapsed(key, type) {
    try {
        const saved = key && browser.localStorage.getItem(key);
        if (saved === "collapsed" || saved === "expanded") {
            return saved === "collapsed";
        }
    } catch {
        // The controls still work when browser storage is unavailable.
    }
    return type === "small";
}

function toggleLabel(collapsed) {
    return collapsed ? _t("Navigation ausklappen") : _t("Navigation einklappen");
}

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.algorithmaOriginalSidebarType = sidebarType();
        this.algorithmaSidebarStorageKey = storageKey();
        this.algorithmaSidebarState = useState({
            collapsed: initialCollapsed(
                this.algorithmaSidebarStorageKey, this.algorithmaOriginalSidebarType
            ),
        });
        useBus(this.env.bus, TOGGLE_EVENT, () => this.algorithmaToggleSidebar());
        onMounted(() => this.algorithmaApplySidebarState());
        onWillDestroy(() => {
            const root = document.querySelector(".o_web_client");
            if (root && this.algorithmaOriginalSidebarType) {
                root.classList.remove(...SIDEBAR_TYPES.map((type) => `mk_sidebar_type_${type}`));
                root.classList.add(`mk_sidebar_type_${this.algorithmaOriginalSidebarType}`);
            }
        });
    },

    get algorithmaSidebarToggleLabel() {
        return toggleLabel(this.algorithmaSidebarState.collapsed);
    },

    algorithmaToggleSidebar() {
        // Respect MuK's saved invisible preference; do not reveal a hidden bar.
        if (!["large", "small"].includes(this.algorithmaOriginalSidebarType)) {
            return;
        }
        this.algorithmaSidebarState.collapsed = !this.algorithmaSidebarState.collapsed;
        this.algorithmaApplySidebarState();
        try {
            if (this.algorithmaSidebarStorageKey) {
                browser.localStorage.setItem(
                    this.algorithmaSidebarStorageKey,
                    this.algorithmaSidebarState.collapsed ? "collapsed" : "expanded"
                );
            }
        } catch {
            // Persistence is optional; keep the current session's state.
        }
    },

    algorithmaApplySidebarState() {
        const collapsed = this.algorithmaSidebarState.collapsed;
        const root = document.querySelector(".o_web_client");
        // Clean up the earlier full-hide behavior when a browser loads this version.
        root?.classList.remove("algorithma_sidebar_hidden");
        const panel = document.getElementById("algorithma-apps-sidebar");
        if (panel) {
            panel.inert = false;
            panel.removeAttribute("aria-hidden");
        }
        if (root && ["large", "small"].includes(this.algorithmaOriginalSidebarType)) {
            root.classList.toggle("mk_sidebar_type_small", collapsed);
            root.classList.toggle("mk_sidebar_type_large", !collapsed);
        }
        this.env.bus.trigger(STATE_EVENT, { collapsed });
    },
});

patch(AppsBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.algorithmaSidebarControlState = useState({
            collapsed: initialCollapsed(storageKey(), sidebarType()),
        });
        useBus(this.env.bus, STATE_EVENT, ({ detail }) => {
            this.algorithmaSidebarControlState.collapsed = detail.collapsed;
        });
    },

    get algorithmaSidebarControlLabel() {
        return toggleLabel(this.algorithmaSidebarControlState.collapsed);
    },

    algorithmaRequestSidebarToggle() {
        this.env.bus.trigger(TOGGLE_EVENT);
    },
});

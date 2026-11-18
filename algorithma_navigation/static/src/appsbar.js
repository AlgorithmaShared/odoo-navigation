/** @odoo-module **/

import { onWillDestroy, onWillStart, useState } from "@odoo/owl";
import { AppsBar } from "@muk_web_appsbar/webclient/appsbar/appsbar";
import { usePopover } from "@web/core/popover/popover_hook";
import { NavigationFlyout } from "./group_flyout";
import { browser } from "@web/core/browser/browser";
import { user } from "@web/core/user";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { groupApps, parseCollapsedGroupKeys, standaloneApps, visibleApps } from "./group_apps";

patch(AppsBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.algorithmaNavigationOrm = useService("orm");
        this.algorithmaNavigationStorageKey = session.db && user.userId
            ? `algorithma.navigation.groups.v1:${encodeURIComponent(session.db)}:${user.userId}`
            : null;
        let collapsedKeys = [];
        try {
            if (this.algorithmaNavigationStorageKey) {
                collapsedKeys = parseCollapsedGroupKeys(
                    browser.localStorage.getItem(this.algorithmaNavigationStorageKey)
                );
            }
        } catch {
            // Navigation also works when browser storage is unavailable.
        }
        this.algorithmaNavigationState = useState({ groups: [], hiddenMenuIds: [], groupingEnabled: true, collapsedKeys, flyoutKey: null });
        this.algorithmaFlyout = usePopover(NavigationFlyout, {
            position: "right-start",
            animation: false,
            arrow: false,
            closeOnEscape: false,
            setActiveElement: false,
            popoverClass: "algorithma_nav_popover",
            onClose: () => {
                this.algorithmaNavigationState.flyoutKey = null;
                this.algorithmaCancelFlyoutClose();
            },
            onPositioned: () => {
                if (this.algorithmaFlyoutFocusRequested) {
                    this.algorithmaFocusFlyout();
                }
            },
        });
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => {
            this.algorithmaCloseFlyout();
            this.algorithmaOpenActiveGroup();
        });
        useBus(this.env.bus, "ALGORITHMA:NAVIGATION-STATE", () => this.algorithmaCloseFlyout());
        const closeOnResize = () => this.algorithmaCloseFlyout();
        const closeOnEscape = (event) => {
            if (event.key === "Escape" && this.algorithmaFlyout.isOpen) {
                event.preventDefault();
                const panel = document.getElementById("algorithma-flyout-" + this.algorithmaNavigationState.flyoutKey);
                this.algorithmaCloseFlyout(Boolean(panel?.contains(document.activeElement)));
            }
        };
        window.addEventListener("resize", closeOnResize);
        window.addEventListener("keydown", closeOnEscape);
        onWillDestroy(() => {
            window.removeEventListener("resize", closeOnResize);
            window.removeEventListener("keydown", closeOnEscape);
            this.algorithmaCancelFlyoutClose();
        });
        onWillStart(async () => {
            try {
                // Menu visibility is presentation only; native app permissions still apply.
                const config = await this.algorithmaNavigationOrm.call(
                    "algorithma.navigation.group", "get_sidebar_config", []
                );
                this.algorithmaNavigationState.groups = Array.isArray(config?.groups) ? config.groups : [];
                this.algorithmaNavigationState.hiddenMenuIds = Array.isArray(config?.hidden_menu_ids)
                    ? config.hidden_menu_ids : [];
                this.algorithmaNavigationState.groupingEnabled = config?.grouping_enabled !== false;
                this.algorithmaOpenActiveGroup();
            } catch {
                this.algorithmaNavigationState.groups = [];
                this.algorithmaNavigationState.hiddenMenuIds = [];
            }
        });
    },

    get algorithmaNavigationApps() {
        return visibleApps(this.appMenuService.getAppsMenuItems(), this.algorithmaNavigationState.hiddenMenuIds);
    },

    get algorithmaNavigationStandaloneApps() {
        return standaloneApps(this.algorithmaNavigationApps, this.algorithmaNavigationGroups);
    },

    get algorithmaNavigationGroups() {
        return groupApps(
            this.algorithmaNavigationApps,
            this.algorithmaNavigationState.groups,
            this.algorithmaNavigationState.groupingEnabled
        );
    },

    algorithmaGroupIsActive(section) {
        return section.apps.some((app) => app.id === this.appMenuService.getCurrentApp()?.id);
    },

    algorithmaCancelFlyoutClose() {
        browser.clearTimeout(this.algorithmaFlyoutCloseTimer);
    },

    algorithmaScheduleFlyoutClose() {
        this.algorithmaCancelFlyoutClose();
        this.algorithmaFlyoutCloseTimer = browser.setTimeout(() => {
            const panel = document.getElementById("algorithma-flyout-" + this.algorithmaNavigationState.flyoutKey);
            if (this.algorithmaFlyoutTarget?.matches(":hover") || panel?.matches(":hover") ||
                panel?.contains(document.activeElement) || this.algorithmaFlyoutTarget === document.activeElement) {
                return;
            }
            this.algorithmaCloseFlyout();
        }, 180);
    },

    algorithmaCloseFlyout(restoreFocus = false) {
        this.algorithmaCancelFlyoutClose();
        const target = this.algorithmaFlyoutTarget;
        this.algorithmaFlyout?.close();
        this.algorithmaNavigationState.flyoutKey = null;
        this.algorithmaFlyoutFocusRequested = false;
        if (restoreFocus && target?.isConnected) {
            target.focus();
        }
    },

    algorithmaFocusFlyout() {
        const link = document.getElementById(
            "algorithma-flyout-" + this.algorithmaNavigationState.flyoutKey
        )?.querySelector('[role="menuitem"]');
        this.algorithmaFlyoutFocusRequested = !link;
        link?.focus();
    },

    algorithmaOpenFlyout(section, target, focusFirst = false) {
        this.algorithmaCancelFlyoutClose();
        if (this.algorithmaNavigationState.flyoutKey === section.key && this.algorithmaFlyout.isOpen) {
            if (focusFirst) {
                this.algorithmaFocusFlyout();
            }
            return;
        }
        this.algorithmaCloseFlyout();
        this.algorithmaFlyoutTarget = target;
        this.algorithmaNavigationState.flyoutKey = section.key;
        this.algorithmaFlyoutFocusRequested = focusFirst;
        this.algorithmaFlyout.open(target, {
            section,
            activeId: this.appMenuService.getCurrentApp()?.id,
            focusFirst,
            onEnter: () => this.algorithmaCancelFlyoutClose(),
            onLeave: () => this.algorithmaScheduleFlyoutClose(),
            onClose: (restoreFocus) => this.algorithmaCloseFlyout(restoreFocus),
            onSelect: (app) => {
                this.algorithmaCloseFlyout();
                return this._onAppClick(app);
            },
        });
    },

    algorithmaFlyoutKeydown(event, section) {
        if (["ArrowRight", "ArrowDown", "ArrowUp"].includes(event.key)) {
            event.preventDefault();
            this.algorithmaOpenFlyout(section, event.currentTarget, true);
        } else if (["Escape", "ArrowLeft"].includes(event.key)) {
            event.preventDefault();
            this.algorithmaCloseFlyout(true);
        }
    },

    algorithmaToggleGroup(key) {
        const collapsed = this.algorithmaNavigationState.collapsedKeys;
        this.algorithmaNavigationState.collapsedKeys = collapsed.includes(key)
            ? collapsed.filter((existing) => existing !== key)
            : [...collapsed, key];
        this.algorithmaSaveCollapsedGroups();
    },

    algorithmaOpenActiveGroup() {
        const activeId = this.appMenuService.getCurrentApp()?.id;
        const activeGroup = this.algorithmaNavigationGroups.find(
            (group) => group.apps.some((app) => app.id === activeId)
        );
        if (activeGroup && this.algorithmaNavigationState.collapsedKeys.includes(activeGroup.key)) {
            this.algorithmaNavigationState.collapsedKeys = this.algorithmaNavigationState.collapsedKeys.filter(
                (key) => key !== activeGroup.key
            );
            this.algorithmaSaveCollapsedGroups();
        }
    },

    algorithmaSaveCollapsedGroups() {
        try {
            if (this.algorithmaNavigationStorageKey) {
                browser.localStorage.setItem(this.algorithmaNavigationStorageKey, JSON.stringify({
                    version: 1,
                    collapsed: this.algorithmaNavigationState.collapsedKeys,
                }));
            }
        } catch {
            // Persistence is optional; the current session keeps its state.
        }
    },
});

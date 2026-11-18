/** @odoo-module **/

import { Component, onMounted, t, useProps } from "@odoo/owl";

/** Popup app links keep MuK's app objects and selection callback unchanged. */
export class NavigationFlyout extends Component {
    static template = "algorithma_navigation.NavigationFlyout";
    props = useProps({
        section: t.object(),
        activeId: t.any().optional(),
        focusFirst: t.boolean(),
        onEnter: t.function(),
        onLeave: t.function(),
        onClose: t.function(),
        onSelect: t.function(),
    });

    setup() {
        onMounted(() => {
            if (this.props.focusFirst) {
                document.getElementById(this.menuId)?.querySelector('[role="menuitem"]')?.focus();
            }
        });
    }

    get menuId() {
        return "algorithma-flyout-" + this.props.section.key;
    }

    onKeydown(event) {
        if (["Escape", "ArrowLeft"].includes(event.key)) {
            event.preventDefault();
            event.stopPropagation();
            this.props.onClose(true);
            return;
        }
        if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const links = [...event.currentTarget.querySelectorAll('[role="menuitem"]')];
        const current = links.indexOf(document.activeElement);
        let index;
        if (event.key === "Home") {
            index = 0;
        } else if (event.key === "End") {
            index = links.length - 1;
        } else {
            index = (current + (event.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
        }
        links[index]?.focus();
    }

    onFocusOut(event) {
        if (!event.currentTarget.contains(event.relatedTarget)) {
            this.props.onLeave();
        }
    }
}

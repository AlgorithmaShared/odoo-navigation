/** @odoo-module **/
// =============================================================================
// Navigation editor: arrange app groups directly in the sidebar
//
// What it does
//   Settings administrators switch the sidebar into an edit mode. There they
//   - drag apps into a group, between groups, or out of every group,
//   - drag groups to change their order,
//   - create, rename and delete groups, and open the colour/symbol form.
//
// Flow
//   1. The pencil button in the sidebar toggles `algorithmaNavigationEditor.active`.
//   2. <NavigationEditor/> loads every group (empty ones too) from
//      `get_sidebar_editor_config`.
//   3. Each drop changes the layout at once on screen and is stored with
//      `save_sidebar_layout`. Saves run one after another.
//   4. The server answer refreshes the editor and the normal sidebar.
//
// The arrangement is shared by all users of the database. The server refuses
// everyone except settings administrators; the pencil is only a convenience.
// =============================================================================

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { AppsBar } from "@muk_web_appsbar/webclient/appsbar/appsbar";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { Mutex } from "@web/core/utils/concurrency";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { useSortable } from "@web/core/utils/sortable_owl";
// Load the grouping patch first: the editor builds on its state and methods.
import "./appsbar";
import { editorSections, layoutPayload, moveApp, moveGroup } from "./group_apps";

// ===== CONSTANTS =====

const GROUP_MODEL = "algorithma.navigation.group";
const SIDEBAR_STATE_EVENT = "ALGORITHMA:NAVIGATION-STATE";

// ===== EDITOR COMPONENT =====

export class NavigationEditor extends Component {
    static template = "algorithma_navigation.NavigationEditor";
    static props = {
        // Apps the administrator may see; apps hidden from the sidebar are left out.
        apps: Array,
        // Called with the fresh sidebar configuration after every stored change.
        onConfigChanged: Function,
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.rootRef = useRef("root");
        this.renameInputRef = useRef("renameInput");
        // Saves run strictly one after another so a later drop never loses to an earlier one.
        this.saveQueue = new Mutex();
        this.pendingSaves = 0;
        this.state = useState({
            sections: [],
            ungrouped: [],
            renamingGroupId: null,
            renameValue: "",
        });

        onWillStart(async () => {
            const editorConfig = await this.orm.call(GROUP_MODEL, "get_sidebar_editor_config", []);
            this.showLayout(editorSections(this.props.apps, editorConfig.editor_groups));
        });

        // Apps: sortable inside a group and across all drop zones.
        useSortable({
            ref: this.rootRef,
            elements: ".algorithma_nav_edit_app",
            groups: ".algorithma_nav_dropzone",
            connectGroups: true,
            cursor: "grabbing",
            placeholderClasses: ["visible", "algorithma_nav_drop_placeholder"],
            onDrop: (dropParams) => this.onAppDrop(dropParams),
        });
        // Groups: sortable by their grip only, so the buttons in the header stay clickable.
        useSortable({
            ref: this.rootRef,
            elements: ".algorithma_nav_edit_group",
            handle: ".algorithma_nav_edit_grip",
            cursor: "grabbing",
            placeholderClasses: ["visible", "algorithma_nav_drop_placeholder"],
            onDrop: (dropParams) => this.onGroupDrop(dropParams),
        });

        // Put the cursor into the name field as soon as a rename starts.
        useEffect(
            (renameInput) => {
                if (renameInput) {
                    renameInput.focus();
                    renameInput.select();
                }
            },
            () => [this.renameInputRef.el]
        );
    }

    // ----- layout state -----

    get layout() {
        return { sections: this.state.sections, ungrouped: this.state.ungrouped };
    }

    showLayout(layout) {
        this.state.sections = layout.sections;
        this.state.ungrouped = layout.ungrouped;
    }

    /** Refresh the editor and the normal sidebar from a server answer. */
    applyEditorConfig(editorConfig) {
        this.showLayout(editorSections(this.props.apps, editorConfig.editor_groups));
        this.props.onConfigChanged(editorConfig.config);
    }

    async reload() {
        this.applyEditorConfig(await this.orm.call(GROUP_MODEL, "get_sidebar_editor_config", []));
    }

    /** Show a changed layout at once, then store it. */
    storeLayout(layout) {
        this.showLayout(layout);
        const { groups, ungrouped_menu_ids } = layoutPayload(layout);
        this.pendingSaves++;
        return this.saveQueue.exec(async () => {
            try {
                const editorConfig = await this.orm.call(
                    GROUP_MODEL, "save_sidebar_layout", [groups, ungrouped_menu_ids]
                );
                this.pendingSaves--;
                // While further drops wait to be stored, their newer layout stays on screen.
                if (this.pendingSaves === 0) {
                    this.applyEditorConfig(editorConfig);
                }
            } catch (error) {
                this.pendingSaves--;
                // Drop the change that was not stored, then let Odoo report the error.
                await this.reload();
                throw error;
            }
        });
    }

    // ----- drag and drop -----

    /** An app was dropped: `parent` is the drop zone, `previous` the row above it. */
    onAppDrop({ element, group: sourceDropzone, parent: targetDropzone, previous }) {
        const targetGroupId = Number(targetDropzone?.dataset.groupId) || null;
        if (!targetGroupId && sourceDropzone === targetDropzone) {
            // Apps without a group keep the native order; there is nothing to store.
            return;
        }
        // Skip helper rows such as the "drop here" hint.
        while (previous && !previous.dataset.menuId) {
            previous = previous.previousElementSibling;
        }
        const previousMenuId = previous ? Number(previous.dataset.menuId) : null;
        const menuId = Number(element.dataset.menuId);
        return this.storeLayout(moveApp(this.layout, menuId, targetGroupId, previousMenuId));
    }

    /** A group was dropped: `previous` is the group above it, if any. */
    onGroupDrop({ element, previous }) {
        while (previous && !previous.dataset.groupId) {
            previous = previous.previousElementSibling;
        }
        const previousGroupId = previous ? Number(previous.dataset.groupId) : null;
        const groupId = Number(element.dataset.groupId);
        return this.storeLayout(moveGroup(this.layout, groupId, previousGroupId));
    }

    // ----- groups: create, rename, delete, style -----

    async addGroup() {
        const [groupId] = await this.orm.create(GROUP_MODEL, [{
            name: _t("Neue Gruppe"),
            sequence: (this.state.sections.length + 1) * 10,
        }]);
        await this.reload();
        this.startRename(groupId);
    }

    startRename(groupId) {
        const section = this.state.sections.find((candidate) => candidate.id === groupId);
        if (section) {
            this.state.renameValue = section.name;
            this.state.renamingGroupId = groupId;
        }
    }

    cancelRename() {
        this.state.renamingGroupId = null;
    }

    async commitRename() {
        const groupId = this.state.renamingGroupId;
        const section = this.state.sections.find((candidate) => candidate.id === groupId);
        const newName = this.state.renameValue.trim();
        this.state.renamingGroupId = null;
        // An empty or unchanged name keeps the old one.
        if (!section || !newName || newName === section.name) {
            return;
        }
        await this.orm.write(GROUP_MODEL, [groupId], { name: newName });
        await this.reload();
    }

    onRenameKeydown(event) {
        if (event.key === "Enter") {
            event.preventDefault();
            return this.commitRename();
        }
        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            this.cancelRename();
        }
    }

    deleteGroup(section) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Gruppe löschen"),
            body: _t(
                "Die Gruppe „%s“ wird gelöscht. Ihre Apps bleiben erhalten und erscheinen danach ohne Gruppe.",
                section.name
            ),
            confirmLabel: _t("Löschen"),
            confirmClass: "btn-danger",
            cancelLabel: _t("Abbrechen"),
            confirm: async () => {
                await this.orm.unlink(GROUP_MODEL, [section.id]);
                await this.reload();
            },
            cancel: () => {},
        });
    }

    /** Colour and symbol are edited in the existing group form. */
    openGroupStyle(section) {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Farbe und Symbol"),
                res_model: GROUP_MODEL,
                res_id: section.id,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.reload() }
        );
    }
}

// ===== SIDEBAR INTEGRATION =====

patch(AppsBar, {
    components: { ...AppsBar.components, NavigationEditor },
});

patch(AppsBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.algorithmaNavigationEditor = useState({ active: false });
        // Editing needs the wide sidebar: leave the edit mode when it is collapsed.
        useBus(this.env.bus, SIDEBAR_STATE_EVENT, ({ detail }) => {
            if (detail.collapsed) {
                this.algorithmaNavigationEditor.active = false;
            }
        });
    },

    /** The server checks the same right again on every editor call. */
    get algorithmaCanEditNavigation() {
        return Boolean(user.isSystem) && this.algorithmaNavigationState.groupingEnabled;
    },

    get algorithmaNavigationEditorLabel() {
        return this.algorithmaNavigationEditor.active
            ? _t("Anordnen beenden")
            : _t("Gruppen und Apps anordnen");
    },

    algorithmaToggleNavigationEditor() {
        this.algorithmaCloseFlyout();
        this.algorithmaNavigationEditor.active = !this.algorithmaNavigationEditor.active;
    },
});

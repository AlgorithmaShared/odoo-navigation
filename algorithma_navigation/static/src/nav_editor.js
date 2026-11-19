/** @odoo-module **/
// =============================================================================
// Navigation editor: arrange app groups directly in the sidebar
//
// What it does
//   Every internal user switches the sidebar into an edit mode. There they
//   - drag apps into a group, between groups, or out of every group,
//   - drag groups to change their order,
//   - create, rename, colour and delete groups.
//
// Two layers ("scope")
//   personal  the user's own arrangement. It is stored per user on the server
//             and replaces the default for that user only. Its groups live
//             inside the stored layout.
//   default   the shared arrangement for everyone without an own one. Only
//             settings administrators may edit it; its groups are records.
//
// Flow
//   1. The pencil button in the sidebar toggles `algorithmaNavigationEditor.active`.
//   2. <NavigationEditor/> loads the layer to edit from `get_sidebar_editor_config`.
//      A user without an own arrangement starts from the default.
//   3. Each change shows at once and is stored: the whole personal layout with
//      `save_personal_sidebar_layout`, or the default with `save_sidebar_layout`
//      and plain record writes. Saves run one after another.
//   4. The server answer refreshes the editor and the normal sidebar.
//
// The server checks every call again; the buttons here are only a convenience.
// =============================================================================

import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { AppsBar } from "@muk_web_appsbar/webclient/appsbar/appsbar";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { Mutex } from "@web/core/utils/concurrency";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { useSortable } from "@web/core/utils/sortable_owl";
// Load the grouping patch first: the editor builds on its state and methods.
import "./appsbar";
import {
    addGroup, editorSections, GROUP_COLOR_PRESETS, GROUP_ICON_KEYS, layoutPayload, moveApp,
    moveGroup, personalLayoutPayload, removeGroup, renameGroup, styleGroup,
} from "./group_apps";

// ===== CONSTANTS =====

const GROUP_MODEL = "algorithma.navigation.group";
const SIDEBAR_STATE_EVENT = "ALGORITHMA:NAVIGATION-STATE";
const SCOPE_PERSONAL = "personal";
const SCOPE_DEFAULT = "default";

// Names of the group symbols, as in the group form.
const GROUP_ICON_LABELS = {
    home: _t("Haus"), briefcase: _t("Aktentasche"), folder: _t("Ordner"), receipt: _t("Beleg"),
    users: _t("Personen"), settings: _t("Einstellungen"), calendar: _t("Kalender"),
    building: _t("Gebäude"), chart: _t("Diagramm"), truck: _t("Fahrzeug"), star: _t("Stern"),
    heart: _t("Herz"),
};

// ===== EDITOR COMPONENT =====

export class NavigationEditor extends Component {
    static template = "algorithma_navigation.NavigationEditor";
    static props = {
        // Apps the user may see; apps hidden from the sidebar are left out.
        apps: Array,
        // Called with the fresh sidebar configuration after every stored change.
        onConfigChanged: Function,
        onClose: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.rootRef = useRef("root");
        this.renameInputRef = useRef("renameInput");
        // Saves run strictly one after another so a later drop never loses to an earlier one.
        this.saveQueue = new Mutex();
        this.pendingSaves = 0;
        this.colorPresets = GROUP_COLOR_PRESETS;
        this.iconChoices = GROUP_ICON_KEYS.map((key) => ({ key, label: GROUP_ICON_LABELS[key] || key }));
        this.state = useState({
            sections: [],
            ungrouped: [],
            scope: SCOPE_PERSONAL,
            hasPersonalLayout: false,
            canEditDefault: false,
            renamingGroupId: null,
            renameValue: "",
            // Group whose colour and symbol choices are open, if any.
            stylingGroupId: null,
        });

        onWillStart(async () => {
            // No scope wish: the server picks the layer this user usually edits.
            this.showEditorConfig(await this.fetchEditorConfig(null));
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

    // ----- which layer is edited -----

    get isPersonal() {
        return this.state.scope === SCOPE_PERSONAL;
    }

    get hintText() {
        if (!this.isPersonal) {
            return _t("Standard für alle Benutzer ohne eigene Anordnung.");
        }
        return this.state.hasPersonalLayout
            ? _t("Deine eigene Anordnung. Sie gilt nur für dich.")
            : _t("Das ist der Standard. Mit deiner ersten Änderung entsteht deine eigene Anordnung.");
    }

    fetchEditorConfig(scope) {
        return this.orm.call(GROUP_MODEL, "get_sidebar_editor_config", [], { scope });
    }

    /** Administrators switch between their own arrangement and the default for everyone. */
    async switchScope(scope) {
        if (scope === this.state.scope) {
            return;
        }
        this.state.renamingGroupId = null;
        this.state.stylingGroupId = null;
        this.applyEditorConfig(await this.fetchEditorConfig(scope));
    }

    // ----- layout state -----

    get layout() {
        return { sections: this.state.sections, ungrouped: this.state.ungrouped };
    }

    showLayout(layout) {
        this.state.sections = layout.sections;
        this.state.ungrouped = layout.ungrouped;
    }

    /** Show a server answer in the editor. */
    showEditorConfig(editorConfig) {
        this.showLayout(editorSections(this.props.apps, editorConfig.editor_groups));
        this.state.scope = editorConfig.scope === SCOPE_DEFAULT ? SCOPE_DEFAULT : SCOPE_PERSONAL;
        this.state.hasPersonalLayout = Boolean(editorConfig.has_personal_layout);
        this.state.canEditDefault = Boolean(editorConfig.can_edit_default);
    }

    /** Refresh the editor and the normal sidebar from a server answer. */
    applyEditorConfig(editorConfig) {
        this.showEditorConfig(editorConfig);
        this.props.onConfigChanged(editorConfig.config);
    }

    async reload() {
        this.applyEditorConfig(await this.fetchEditorConfig(this.state.scope));
    }

    /** Show a changed layout at once, then store it in the layer that is edited. */
    storeLayout(layout) {
        this.showLayout(layout);
        let method, args;
        if (this.isPersonal) {
            method = "save_personal_sidebar_layout";
            args = [personalLayoutPayload(layout)];
        } else {
            const { groups, ungrouped_menu_ids } = layoutPayload(layout);
            method = "save_sidebar_layout";
            args = [groups, ungrouped_menu_ids];
        }
        this.pendingSaves++;
        return this.saveQueue.exec(async () => {
            try {
                const editorConfig = await this.orm.call(GROUP_MODEL, method, args);
                this.pendingSaves--;
                // While further changes wait to be stored, their newer layout stays on screen.
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

    // ----- groups: create, rename, delete -----
    // Personal groups are part of the stored layout; default groups are records.

    async addGroup() {
        const name = _t("Neue Gruppe");
        let groupId;
        if (this.isPersonal) {
            const added = addGroup(this.layout, name);
            groupId = added.groupId;
            await this.storeLayout(added.layout);
        } else {
            [groupId] = await this.orm.create(GROUP_MODEL, [{
                name, sequence: (this.state.sections.length + 1) * 10,
            }]);
            await this.reload();
        }
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
        if (this.isPersonal) {
            await this.storeLayout(renameGroup(this.layout, groupId, newName));
        } else {
            await this.orm.write(GROUP_MODEL, [groupId], { name: newName });
            await this.reload();
        }
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
                if (this.isPersonal) {
                    await this.storeLayout(removeGroup(this.layout, section.id));
                } else {
                    await this.orm.unlink(GROUP_MODEL, [section.id]);
                    await this.reload();
                }
            },
            cancel: () => {},
        });
    }

    // ----- groups: colour and symbol -----

    toggleStylePanel(section) {
        this.state.stylingGroupId = this.state.stylingGroupId === section.id ? null : section.id;
    }

    /** `style` holds the colour, the symbol, or both; what is left out stays as it is. */
    async setGroupStyle(section, style) {
        const color = "color" in style ? style.color : section.color;
        const icon = "icon" in style ? style.icon : section.icon;
        if (this.isPersonal) {
            await this.storeLayout(styleGroup(this.layout, section.id, { color, icon }));
        } else {
            await this.orm.write(GROUP_MODEL, [section.id], { color: color || false, icon: icon || false });
            await this.reload();
        }
    }

    // ----- back to the default -----

    resetPersonalLayout() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Auf Standard zurücksetzen"),
            body: _t("Deine eigene Anordnung wird gelöscht. Du siehst danach wieder den Standard."),
            confirmLabel: _t("Zurücksetzen"),
            confirmClass: "btn-danger",
            cancelLabel: _t("Abbrechen"),
            confirm: async () => {
                this.state.renamingGroupId = null;
                this.state.stylingGroupId = null;
                this.applyEditorConfig(
                    await this.orm.call(GROUP_MODEL, "reset_personal_sidebar_layout", [])
                );
            },
            cancel: () => {},
        });
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

    /** Every user may arrange the own sidebar while grouping is switched on. */
    get algorithmaCanEditNavigation() {
        return this.algorithmaNavigationState.groupingEnabled;
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

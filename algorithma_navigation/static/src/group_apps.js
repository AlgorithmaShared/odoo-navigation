/** @odoo-module **/

export const GROUP_ICON_KEYS = Object.freeze([
    "home", "briefcase", "folder", "receipt", "users", "settings",
    "calendar", "building", "chart", "truck", "star", "heart",
]);

export function sanitizeGroupColor(value) {
    return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value)
        ? value.toUpperCase() : false;
}

export function sanitizeGroupIcon(value) {
    return GROUP_ICON_KEYS.includes(value) ? value : false;
}

/** Hide only exact, positive integer menu IDs; keep original app objects/order. */
export function visibleApps(apps, hiddenMenuIds) {
    const hidden = new Set((Array.isArray(hiddenMenuIds) ? hiddenMenuIds : [])
        .filter((id) => Number.isInteger(id) && id > 0));
    return apps.filter((app) => !hidden.has(app.id));
}

/** Only validated hex values become CSS; arbitrary server strings stay out. */
export function groupStyle(value) {
    const color = sanitizeGroupColor(value);
    if (!color) {
        return "";
    }
    const rgb = [1, 3, 5].map((start) => parseInt(color.slice(start, start + 2), 16)).join(",");
    return `--algorithma-group-accent:${color};--algorithma-group-tint:rgba(${rgb},0.10);--algorithma-group-hover:rgba(${rgb},0.18)`;
}

/**
 * Group the existing MuK app objects in the configured menu_ids order. The first
 * group owns duplicate assignments; no app object is changed. Unassigned apps
 * stay outside groups, and disabling grouping leaves the configuration intact.
 */
export function groupApps(apps, groups, groupingEnabled = true) {
    if (groupingEnabled === false || !Array.isArray(groups) || !groups.length) {
        return [];
    }
    const seenApps = new Set();
    const uniqueApps = apps.filter((app) => {
        if (seenApps.has(app.id)) {
            return false;
        }
        seenApps.add(app.id);
        return true;
    });
    const assigned = new Set();
    const appsById = new Map(uniqueApps.map((app) => [app.id, app]));
    const seenGroups = new Set();
    const result = [];
    for (const group of groups) {
        if (
            !group || !Number.isInteger(group.id) || group.id <= 0 ||
            typeof group.name !== "string" || !group.name.trim() ||
            !Array.isArray(group.menu_ids) || seenGroups.has(group.id)
        ) {
            continue;
        }
        seenGroups.add(group.id);
        const matchedApps = [];
        for (const menuId of group.menu_ids) {
            const app = appsById.get(menuId);
            if (app && !assigned.has(menuId)) {
                assigned.add(menuId);
                matchedApps.push(app);
            }
        }
        if (matchedApps.length) {
            const color = sanitizeGroupColor(group.color);
            result.push({
                key: `group-${group.id}`, name: group.name, apps: matchedApps,
                color, icon: sanitizeGroupIcon(group.icon), style: groupStyle(color),
            });
        }
    }
    return result;
}

/** Unassigned apps follow configured groups, retaining native MuK order/objects. */
export function standaloneApps(apps, sections) {
    const assigned = new Set(sections.flatMap((section) => section.apps.map((app) => app.id)));
    const seen = new Set();
    return apps.filter((app) => {
        if (assigned.has(app.id) || seen.has(app.id)) {
            return false;
        }
        seen.add(app.id);
        return true;
    });
}

// ===== SIDEBAR EDITOR (drag and drop) =====
// Pure layout helpers for the editor. A layout is
//   { sections: [{ id, key, name, apps, color, icon, style }], ungrouped: [app] }
// Every helper returns a new layout and never changes the app objects.

/**
 * Build the editor layout: every configured group, empty ones included, with
 * its visible apps, followed by the apps that belong to no group.
 */
export function editorSections(apps, editorGroups) {
    const seenAppIds = new Set();
    const uniqueApps = apps.filter((app) => {
        if (seenAppIds.has(app.id)) {
            return false;
        }
        seenAppIds.add(app.id);
        return true;
    });
    const appsById = new Map(uniqueApps.map((app) => [app.id, app]));
    const assignedAppIds = new Set();
    const seenGroupIds = new Set();
    const sections = [];
    for (const group of Array.isArray(editorGroups) ? editorGroups : []) {
        if (
            !group || !Number.isInteger(group.id) || group.id <= 0 ||
            typeof group.name !== "string" || !group.name.trim() ||
            !Array.isArray(group.menu_ids) || seenGroupIds.has(group.id)
        ) {
            continue;
        }
        seenGroupIds.add(group.id);
        const groupApps = [];
        for (const menuId of group.menu_ids) {
            const app = appsById.get(menuId);
            if (app && !assignedAppIds.has(menuId)) {
                assignedAppIds.add(menuId);
                groupApps.push(app);
            }
        }
        const color = sanitizeGroupColor(group.color);
        sections.push({
            id: group.id, key: `group-${group.id}`, name: group.name, apps: groupApps,
            color, icon: sanitizeGroupIcon(group.icon), style: groupStyle(color),
        });
    }
    return { sections, ungrouped: uniqueApps.filter((app) => !assignedAppIds.has(app.id)) };
}

/**
 * Move one app into a group, right after `previousMenuId` (or to the top when
 * there is none). Without a target group the app leaves every group.
 */
export function moveApp(layout, menuId, targetGroupId, previousMenuId) {
    let movedApp = null;
    const withoutMovedApp = (apps) => apps.filter((app) => {
        if (app.id === menuId) {
            movedApp = app;
            return false;
        }
        return true;
    });
    const sections = layout.sections.map((section) => ({ ...section, apps: withoutMovedApp(section.apps) }));
    const ungrouped = withoutMovedApp(layout.ungrouped);
    if (!movedApp) {
        return layout;
    }
    if (targetGroupId === null || targetGroupId === undefined) {
        return { sections, ungrouped: [...ungrouped, movedApp] };
    }
    const targetSection = sections.find((section) => section.id === targetGroupId);
    if (!targetSection) {
        return layout;
    }
    const previousIndex = targetSection.apps.findIndex((app) => app.id === previousMenuId);
    targetSection.apps = [
        ...targetSection.apps.slice(0, previousIndex + 1), movedApp,
        ...targetSection.apps.slice(previousIndex + 1),
    ];
    return { sections, ungrouped };
}

/** Move one group right after `previousGroupId`, or to the top when there is none. */
export function moveGroup(layout, groupId, previousGroupId) {
    const movedSection = layout.sections.find((section) => section.id === groupId);
    if (!movedSection) {
        return layout;
    }
    const otherSections = layout.sections.filter((section) => section.id !== groupId);
    const previousIndex = otherSections.findIndex((section) => section.id === previousGroupId);
    return {
        sections: [
            ...otherSections.slice(0, previousIndex + 1), movedSection,
            ...otherSections.slice(previousIndex + 1),
        ],
        ungrouped: layout.ungrouped,
    };
}

/** Arguments for the server method save_sidebar_layout: ids only, in display order. */
export function layoutPayload(layout) {
    return {
        groups: layout.sections.map((section) => ({
            id: section.id, menu_ids: section.apps.map((app) => app.id),
        })),
        ungrouped_menu_ids: layout.ungrouped.map((app) => app.id),
    };
}

// ----- personal arrangement: groups live inside the layout, not on the server -----

/** Colours offered in the editor; the same set as in the group form. */
export const GROUP_COLOR_PRESETS = Object.freeze([
    "#2563EB", "#7C3AED", "#0D9488", "#16A34A", "#D97706", "#DC2626", "#DB2777", "#64748B",
]);

/** Add an empty group at the end. Returns the new layout and the number of the new group. */
export function addGroup(layout, name) {
    const groupId = Math.max(0, ...layout.sections.map((section) => section.id)) + 1;
    const newSection = {
        id: groupId, key: `group-${groupId}`, name, apps: [], color: false, icon: false, style: "",
    };
    return { layout: { sections: [...layout.sections, newSection], ungrouped: layout.ungrouped }, groupId };
}

/** Give a group another name. */
export function renameGroup(layout, groupId, name) {
    return {
        sections: layout.sections.map((section) => section.id === groupId ? { ...section, name } : section),
        ungrouped: layout.ungrouped,
    };
}

/** Remove a group; its apps stay and move to the apps without a group. */
export function removeGroup(layout, groupId) {
    const removedSection = layout.sections.find((section) => section.id === groupId);
    if (!removedSection) {
        return layout;
    }
    return {
        sections: layout.sections.filter((section) => section.id !== groupId),
        ungrouped: [...layout.ungrouped, ...removedSection.apps],
    };
}

/** Set colour and symbol of a group; anything but the known values clears them. */
export function styleGroup(layout, groupId, { color, icon }) {
    const cleanColor = sanitizeGroupColor(color);
    return {
        sections: layout.sections.map((section) => section.id === groupId
            ? { ...section, color: cleanColor, icon: sanitizeGroupIcon(icon), style: groupStyle(cleanColor) }
            : section),
        ungrouped: layout.ungrouped,
    };
}

/** Argument for save_personal_sidebar_layout: the whole personal arrangement. */
export function personalLayoutPayload(layout) {
    return layout.sections.map((section) => ({
        id: section.id, name: section.name, color: section.color || false, icon: section.icon || false,
        menu_ids: section.apps.map((app) => app.id),
    }));
}

/** Invalid, obsolete or unavailable browser storage simply starts expanded. */
export function parseCollapsedGroupKeys(raw) {
    try {
        const stored = JSON.parse(raw);
        if (
            stored?.version !== 1 || !Array.isArray(stored.collapsed) ||
            !stored.collapsed.every((key) => typeof key === "string" && /^(group-[1-9]\d*|other)$/.test(key))
        ) {
            return [];
        }
        return [...new Set(stored.collapsed)];
    } catch {
        return [];
    }
}

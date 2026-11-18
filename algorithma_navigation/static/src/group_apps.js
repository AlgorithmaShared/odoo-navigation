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

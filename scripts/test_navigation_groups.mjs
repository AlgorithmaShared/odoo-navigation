/** Run with node scripts/test_navigation_groups.mjs. */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../algorithma_navigation/static/src/group_apps.js", import.meta.url), "utf8");
const {
    groupApps, standaloneApps, visibleApps, parseCollapsedGroupKeys, GROUP_ICON_KEYS,
    sanitizeGroupColor, sanitizeGroupIcon, groupStyle,
    editorSections, moveApp, moveGroup, layoutPayload,
} = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);
let checks = 0;
function check(name, run) { run(); checks++; console.log(`PASS ${name}`); }

const app = (id) => Object.freeze({ id, label: `App ${id}`, href: `/odoo/${id}`, webIconData: `icon-${id}` });
const apps = Object.freeze([app(3), app(1), app(4), app(2)]);
const group = (id, menu_ids, name = `Group ${id}`) => ({ id, name, menu_ids });

check("configured app order overrides original order, objects and icons remain identical", () => {
    const result = groupApps(apps, [group(10, [2, 1])]);
    assert.deepEqual(result[0].apps.map((a) => a.id), [2, 1]);
    assert.equal(result[0].apps[0], apps[3]);
    assert.equal(result[0].apps[1], apps[1]);
    assert.equal(result.length, 1);
    assert.deepEqual(standaloneApps(apps, result).map((a) => a.id), [3, 4]);
});
check("every accessible app occurs exactly once despite duplicate assignments", () => {
    const result = groupApps([...apps, apps[0]], [group(10, [1, 1, 2]), group(20, [1, 3])]);
    const ids = [...result.flatMap((g) => g.apps), ...standaloneApps([...apps, apps[0]], result)].map((a) => a.id);
    assert.equal(ids.length, 4);
    assert.deepEqual([...ids].sort(), [1, 2, 3, 4]);
    assert.deepEqual(result[1].apps.map((a) => a.id), [3]);
});
check("hidden or nonexistent configured apps and empty groups never create app links", () => {
    const result = groupApps(apps, [group(30, [999]), group(10, [1, 999])]);
    assert.equal(result.length, 1);
    assert.equal(result[0].key, "group-10");
    assert.equal(result.flatMap((g) => g.apps).some((a) => a.id === 999), false);
});
check("unconfigured, empty or malformed configuration leaves the original flat list", () => {
    for (const config of [null, [], {}, [group(1, [999])], [group(0, [1])], [group(1, [1], " ")]]) {
        assert.deepEqual(groupApps(apps, config), []);
    }
    assert.deepEqual(groupApps([], [group(1, [1])]), []);
});
check("group ordering is administrator ordering and complete assignment has no fallback", () => {
    const result = groupApps(apps, [group(20, [3, 4]), group(10, [1, 2])]);
    assert.deepEqual(result.map((g) => g.key), ["group-20", "group-10"]);
    assert.deepEqual(result.flatMap((g) => g.apps.map((a) => a.id)), [3, 4, 1, 2]);
});
check("storage accepts only current, well-formed collapse preferences", () => {
    assert.deepEqual(parseCollapsedGroupKeys('{"version":1,"collapsed":["group-10","other","group-10"]}'), ["group-10", "other"]);
    for (const raw of [null, "", "broken", "{}", '{"version":2,"collapsed":[]}',
        '{"version":1,"collapsed":["__proto__"]}', '{"version":1,"collapsed":[1]}']) {
        assert.deepEqual(parseCollapsedGroupKeys(raw), []);
    }
});
check("group styles accept complete hex colors and only the twelve supplied icon keys", () => {
    assert.equal(sanitizeGroupColor("#aB12fF"), "#AB12FF");
    assert.equal(GROUP_ICON_KEYS.length, 12);
    for (const icon of GROUP_ICON_KEYS) assert.equal(sanitizeGroupIcon(icon), icon);
    for (const value of [false, null, "", "#fff", "red", "#123456;display:none", {}, 123]) {
        assert.equal(sanitizeGroupColor(value), false);
        assert.equal(groupStyle(value), "");
    }
    for (const value of [false, null, "", "__proto__", "<svg>", "calendar;display:none", {}]) {
        assert.equal(sanitizeGroupIcon(value), false);
    }
    assert.equal(groupStyle("#aB12fF"), "--algorithma-group-accent:#AB12FF;--algorithma-group-tint:rgba(171,18,255,0.10);--algorithma-group-hover:rgba(171,18,255,0.18)");
});
check("group presentation stays isolated from original application icons and direct apps", () => {
    const result = groupApps(apps, [{ ...group(10, [1]), color: "#aB12fF", icon: "calendar" }]);
    assert.equal(result[0].color, "#AB12FF");
    assert.equal(result[0].icon, "calendar");
    assert.equal(result[0].apps[0], apps[1]);
    assert.equal(result[0].apps[0].webIconData, "icon-1");
    const standalone = standaloneApps(apps, result);
    assert.deepEqual(standalone.map((item) => item.id), [3, 4, 2]);
    assert.equal(standalone[0], apps[0]);
    assert.equal(standalone[0].webIconData, "icon-3");
    assert.equal(result.some((section) => section.key === "other"), false);
    const neutral = groupApps(apps, [{ ...group(10, [1]), color: "url(bad)", icon: "unknown" }]);
    assert.equal(neutral[0].color, false);
    assert.equal(neutral[0].icon, false);
    assert.equal(neutral[0].style, "");
});
check("hidden menu IDs preserve order and object identity, rejecting malformed IDs", () => {
    const result = visibleApps(apps, [1, 1, 999, "3", true, 0, -4, 2.5, null]);
    assert.deepEqual(result.map((item) => item.id), [3, 4, 2]);
    assert.equal(result[0], apps[0]);
    assert.equal(result[1], apps[2]);
    for (const invalid of [null, {}, "1,2"]) {
        assert.deepEqual(visibleApps(apps, invalid), apps);
    }
});
check("hidden assigned and unassigned apps stay absent from every group", () => {
    const visible = visibleApps(apps, [1, 4]);
    const result = groupApps(visible, [group(10, [1]), group(20, [2, 3, 4])]);
    assert.deepEqual(result.map((section) => section.key), ["group-20"]);
    assert.deepEqual(result[0].apps.map((item) => item.id), [2, 3]);
});
check("empty groups never restore hidden apps in the filtered flat fallback", () => {
    const visible = visibleApps(apps, [1, 2]);
    assert.deepEqual(groupApps(visible, [group(10, [1, 2])]), []);
    assert.deepEqual(visible.map((item) => item.id), [3, 4]);
    assert.deepEqual(groupApps(visible, []), []);
    const none = visibleApps(apps, [1, 2, 3, 4]);
    assert.deepEqual(none, []);
    assert.deepEqual(groupApps(none, [group(10, [1, 2])]), []);
});
check("disabled grouping restores native app order and preserves hidden-app filtering and configuration", () => {
    const configured = Object.freeze([Object.freeze(group(10, Object.freeze([2, 1])))]);
    const visible = visibleApps(apps, [4]);
    const sections = groupApps(visible, configured, false);
    assert.deepEqual(sections, []);
    assert.deepEqual(standaloneApps(visible, sections), [apps[0], apps[1], apps[3]]);
    const enabled = groupApps(visible, configured, true);
    assert.deepEqual(enabled[0].apps, [apps[3], apps[1]]);
    assert.deepEqual(standaloneApps(visible, enabled), [apps[0]]);
});
check("removing an app assignment makes it a direct app without a catch-all group", () => {
    const before = groupApps(apps, [group(10, [2, 1]), group(20, [3, 4])]);
    assert.deepEqual(standaloneApps(apps, before), []);
    const after = groupApps(apps, [group(10, [2]), group(20, [3, 4])]);
    assert.deepEqual(after.map((section) => section.key), ["group-10", "group-20"]);
    assert.deepEqual(standaloneApps(apps, after), [apps[1]]);
    assert.deepEqual(standaloneApps(apps, []), apps);
});
check("all-unassigned and all-hidden configurations remain flat without duplicate links", () => {
    const duplicateApps = [...apps, apps[0]];
    assert.deepEqual(standaloneApps(duplicateApps, []), apps);
    const hidden = visibleApps(duplicateApps, [1, 2, 3, 4]);
    const grouped = groupApps(hidden, [group(10, [1, 2])]);
    assert.deepEqual(standaloneApps(hidden, grouped), []);
});

// ===== SIDEBAR EDITOR (drag and drop) =====
// Layout used below: group 10 = [app 1, app 2], group 20 = [], apps 3 and 4 without a group.
const editorGroups = Object.freeze([
    Object.freeze({ id: 10, name: "First", menu_ids: Object.freeze([1, 2]), color: "#aB12fF", icon: "calendar" }),
    Object.freeze({ id: 20, name: "Empty", menu_ids: Object.freeze([]), color: false, icon: false }),
]);
const appIds = (list) => list.map((item) => item.id);
const sectionAppIds = (layout) => layout.sections.map((section) => appIds(section.apps));

check("editor layout keeps empty groups, native order of ungrouped apps and original app objects", () => {
    const layout = editorSections(apps, editorGroups);
    assert.deepEqual(layout.sections.map((section) => section.key), ["group-10", "group-20"]);
    assert.deepEqual(sectionAppIds(layout), [[1, 2], []]);
    assert.deepEqual(appIds(layout.ungrouped), [3, 4]);
    assert.equal(layout.sections[0].apps[0], apps[1]);
    assert.equal(layout.sections[0].color, "#AB12FF");
    assert.equal(layout.sections[0].icon, "calendar");
    assert.equal(layout.sections[1].style, "");
});
check("editor layout ignores malformed groups, unknown apps and duplicate assignments", () => {
    const layout = editorSections([...apps, apps[0]], [
        null, { id: 0, name: "Zero", menu_ids: [1] }, { id: 5, name: " ", menu_ids: [1] },
        { id: 10, name: "First", menu_ids: [1, 999, 1] }, { id: 10, name: "Again", menu_ids: [2] },
        { id: 30, name: "Second", menu_ids: [1, 2] },
    ]);
    assert.deepEqual(layout.sections.map((section) => section.id), [10, 30]);
    assert.deepEqual(sectionAppIds(layout), [[1], [2]]);
    assert.deepEqual(appIds(layout.ungrouped), [3, 4]);
    for (const invalid of [null, {}, "groups"]) {
        assert.deepEqual(editorSections(apps, invalid), { sections: [], ungrouped: [...apps] });
    }
});
check("moving an app places it after the given app, at the top, into an empty group or out of all groups", () => {
    const layout = editorSections(apps, editorGroups);
    assert.deepEqual(sectionAppIds(moveApp(layout, 3, 10, 1)), [[1, 3, 2], []]);
    assert.deepEqual(sectionAppIds(moveApp(layout, 3, 10, null)), [[3, 1, 2], []]);
    assert.deepEqual(sectionAppIds(moveApp(layout, 1, 10, 2)), [[2, 1], []]);
    assert.deepEqual(sectionAppIds(moveApp(layout, 2, 20, null)), [[1], [2]]);
    const ungroupedLayout = moveApp(layout, 1, null, null);
    assert.deepEqual(sectionAppIds(ungroupedLayout), [[2], []]);
    assert.deepEqual(appIds(ungroupedLayout.ungrouped), [3, 4, 1]);
    assert.equal(moveApp(layout, 3, 10, 1).sections[0].apps[1], apps[0]);
});
check("moving an app never changes the previous layout and ignores unknown apps or groups", () => {
    const layout = editorSections(apps, editorGroups);
    const snapshot = JSON.stringify(layoutPayload(layout));
    moveApp(layout, 3, 10, 1);
    moveApp(layout, 1, null, null);
    moveGroup(layout, 20, null);
    assert.equal(JSON.stringify(layoutPayload(layout)), snapshot);
    assert.equal(moveApp(layout, 999, 10, null), layout);
    assert.equal(moveApp(layout, 1, 999, null), layout);
    assert.equal(moveGroup(layout, 999, null), layout);
});
check("moving a group places it after the given group or at the top", () => {
    const layout = editorSections(apps, [...editorGroups, { id: 30, name: "Third", menu_ids: [3] }]);
    const groupIds = (result) => result.sections.map((section) => section.id);
    assert.deepEqual(groupIds(moveGroup(layout, 30, null)), [30, 10, 20]);
    assert.deepEqual(groupIds(moveGroup(layout, 10, 30)), [20, 30, 10]);
    assert.deepEqual(groupIds(moveGroup(layout, 10, 20)), [20, 10, 30]);
    assert.deepEqual(sectionAppIds(moveGroup(layout, 30, null)), [[3], [1, 2], []]);
});
check("layout payload sends only ids, in display order", () => {
    const layout = moveGroup(moveApp(editorSections(apps, editorGroups), 4, 20, null), 20, null);
    assert.deepEqual(layoutPayload(layout), {
        groups: [{ id: 20, menu_ids: [4] }, { id: 10, menu_ids: [1, 2] }],
        ungrouped_menu_ids: [3],
    });
});
console.log(`${checks} navigation checks passed.`);

# Algorithma Navigation

Adds configurable, collapsible application groups to the existing MuK AppsBar.
The original application icons and actions continue to be used. This module
groups the user's accessible root applications for display; it does not change
their Odoo menu parents or grant business access.

Version `18.0.1.3.0` makes grouping optional. Administrators can disable it
for every user in the database without deleting group assignments. Individual
ungrouped apps appear directly after the groups, including as individual icons
in the compact rail. The half-size, centered sidebar logo is retained.

## Configuration

Use **Settings → General Settings → Navigation → Apps gruppieren** to enable or
disable grouping for all users of this database. Saving an unchecked setting
persists across reloads. Disabling grouping shows visible apps in native MuK
order; existing group assignments and hidden-app choices remain stored.

Use **Settings → Navigation → App-Zuordnungen** to assign an app to a group,
clear its group to show it directly, or hide it from the sidebar. Applications
without an assignment and apps in archived or deleted groups also appear
directly after the active groups. There is no automatic **Weitere Apps** section.
Deleting a group leaves its app rows and hiding choices intact. Configured
ordering applies within groups; direct apps retain native MuK order.

Manage group names, order, optional colors and symbols under **Settings →
Navigation → App Groups**. Installation supplies editable starter groups for
standard apps already installed. Empty or inaccessible groups are omitted.
Reload the web client after saving changes.

Each user/browser remembers collapsed groups separately for each database. A
newly selected application opens its group. The compact group rail exposes each group's unhidden permitted apps through its flyout, independently of desktop group collapse.

Use the **Navigation** arrow at the top of the sidebar, or the button beside
Odoo's app switcher, to switch between the full grouped navigation and a
46-pixel group rail. Hover or click a group symbol to open its apps in a flyout;
the flyout preserves native app icons, names and actions. Enter, Space or Arrow
Right opens the list, arrow keys move between apps, and Escape closes it and
returns focus. The pointer can move from a group into its flyout without closing
it. Expanding restores group names and existing group-collapse choices.

The width preference is remembered separately per browser, database and user;
MuK's saved user setting is unchanged. Controls appear from 992 pixels wide.
Medium-width screens use the same compact group rail; phones keep Odoo's existing
app navigation. The hidden-sidebar preference, home view and fullscreen remain
respected. Enter and Space activate either button.

## Installation and removal

Depends only on `muk_web_appsbar`; install separately in each tenant database.
The supported runtime for this package is Odoo 18. A MuK/Odoo major-version
upgrade requires checking the component API and tests again. Uninstalling removes
this module's group configuration and restores MuK's normal flat application
list. It does not uninstall the business applications.

## Checks

Run the Odoo tests with `--test-enable --test-tags=/algorithma_navigation` in an
isolated database. The backend suite covers visibility, administrator-only
configuration, duplicate assignments, sequence and preservation of native menus.
Run the pure grouping/storage checks with
`node scripts/test_navigation_groups.mjs` from the repository
root. Browser validation must include grouped links, persistence, active-app
opening, compact/medium layouts and the administrator form.

Version `18.0.1.2.0` passed nineteen backend tests, eleven shared helper checks
and seven Chromium workflows. The checks cover permitted and hidden app
filtering, compact group flyouts, hover and keyboard interaction, native app
links/icons, and sidebar collapse. Hidden apps remain absent when their group
is empty or archived and when the filtered flat fallback is shown.

Earlier version 18.0.1.1.0 passed fifteen backend tests, eight pure helper checks and ten
Chromium workflow checks. These cover color presets and custom hex values,
saving/reloading and clearing styles, twelve symbol choices and previews,
whole-sidebar persistence, compact/mobile layouts and restricted-user access.
An actual 1.0.0-to-1.1.0 upgrade preserved existing configuration. No browser
JavaScript or asset-loading errors occurred.

Earlier version `18.0.1.1.1` changed the sidebar controls only. Eight focused Odoo 18
browser workflows verified both buttons, the 224/46-pixel layouts, app links,
tooltips and keyboard focus, reload/group-state persistence, native Small and
Invisible preferences, and medium/mobile/home/fullscreen behavior. No browser
JavaScript or asset errors occurred; Python model code was unchanged in that version.

## Credits and license

LGPL-3. The sidebar markup is adapted from MuK AppsBar by MuK IT GmbH and
Mathias Markl, also LGPL-3. MuK source files are not overwritten. Original
project: <https://github.com/muk-it/odoo-modules>.
The twelve original inline SVG symbols are MIT-licensed; their notice is in
`static/src/group_icons.LICENSE`. They use no external font or CDN.

## Group colors and symbols

Each group can have an optional `#RRGGBB` color and one of twelve built-in
symbols. Administrators select them in the group form; the original app icons
are unchanged. Clearing a style uses the sidebar's neutral appearance.
The API returns `color` and `icon`, using `false` for an unset value.

The 1.1.0 upgrade fills missing style fields on the six initial groups only.
Existing colors, symbols, group names, sequences, active flags and app
assignments are preserved. User-created groups are not restyled.

## Hiding apps from the sidebar

An administrator can select **In Seitenleiste ausblenden** on each assigned app
under **Settings → Navigation → App Groups**. This hides the app from the sidebar
for all users while preserving native app permissions, menus, actions and other
access paths. An ungrouped app can be managed directly in **App-Zuordnungen**;
its group is optional. Hiding remains effective with grouping switched off and
when a group is archived, deleted or cleared. Clearing the checkbox or deleting
the assignment shows the permitted app again after reloading the web client.

The new `get_sidebar_config()` API returns `groups` with the unchanged
`get_sidebar_groups()` payload and `hidden_menu_ids` restricted to the caller's
permitted active root menus. It also returns `grouping_enabled` (default `true`)
from the database-wide setting. Portal and public users cannot call either API.

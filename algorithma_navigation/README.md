# Algorithma Navigation for Odoo 20

Adds configurable, collapsible application groups to MuK AppsBar. The original
application objects, icons and actions remain in use. Grouping only changes the
sidebar presentation; it does not change menu parents or grant business access.

Version `20.0.1.4.0` adds arranging by drag and drop, see the next section.
Version `20.0.1.3.0` made grouping optional. Administrators can disable it
for every user in the database without deleting group assignments. Individual
ungrouped apps appear directly after the groups, including as individual icons
in the compact rail. The half-size, centered sidebar logo is retained.

## Arranging the navigation by drag and drop

Version `20.0.1.4.0` adds an edit mode to the wide sidebar. Every internal user
may use it while **Apps gruppieren** is switched on.

- Click the **pencil** next to **Navigation**. The sidebar shows every group,
  empty ones included, and a box **Ohne Gruppe** for apps without a group.
- **Drag an app** onto another position, into another group, or into **Ohne
  Gruppe**. Apps without a group keep their native MuK order.
- **Drag a group** by its grip to change the order of the groups.
- **Neue Gruppe** creates a group and lets you type its name at once. The
  buttons in a group header rename it, choose its colour and symbol, or delete
  it. Deleting a group keeps its apps; they appear without a group.
- Every change is stored immediately. **Fertig** or the check mark leaves the
  edit mode.

### An own arrangement per user, and a default for everyone

Two layers exist:

- **Own arrangement.** Each user arranges the own sidebar. It is stored per
  user on the server, so it follows the user to every device, and it replaces
  the default for that user only. A user without an own arrangement starts
  from the default; the first change creates the own one. **Auf Standard
  zurücksetzen** drops it again.
- **Default.** The arrangement for everyone without an own one. Only settings
  administrators may change it. In the editor they switch between **Für mich**
  and **Für alle**. An administrator without an own arrangement edits the
  default, as before.

What to know:

- Access rights are untouched: a user only ever sees and arranges apps that
  user may open. Apps an administrator hid with **In Seitenleiste ausblenden**
  stay hidden for everyone and do not appear in the editor.
- A user with an own arrangement no longer follows later changes of the
  default. Newly installed apps appear under **Ohne Gruppe** for that user.
- A user who starts from the default gets the default groups that hold at
  least one app that user may open. Other default groups, empty ones
  included, are shown to administrators only.
- Changes to the default reach other users after reloading the web client.
- The editor needs a pointer; with the keyboard, administrators use
  **App-Zuordnungen** for the default. On the 46-pixel rail, on medium screens
  and on phones the pencil is not shown.

Server methods behind the editor, all on `algorithma.navigation.group`:

- `get_sidebar_editor_config(scope=None)` returns the layer to edit;
  `scope` is `"personal"`, `"default"` (administrators only) or empty.
- `save_personal_sidebar_layout(groups)` stores the caller's own arrangement:
  a list of `{"id", "name", "color", "icon", "menu_ids"}` in display order.
  It lives in the model `algorithma.navigation.user.layout`, one row per user.
- `reset_personal_sidebar_layout()` drops the caller's own arrangement.
- `save_sidebar_layout(groups, ungrouped_menu_ids)` stores the default and
  refuses everyone except settings administrators. Assignments that are not
  mentioned stay untouched.

The same version declares the `close` property of the group flyout, which Odoo
passes to every popover; without it the flyout raised an error in developer mode.

## Sidebar colours

Since version `20.0.1.4.0` a light sidebar is the default look of this module:
background `#D9DDE2`, text `#272C31`, highlight `#BCCDF0`. The values live in
`static/src/scss/primary_variables.scss` and can be changed there or overridden
by an earlier primary-variables file (`$algorithma-nav-default-background`,
`$algorithma-nav-default-text`, `$algorithma-nav-default-active`).

- The default replaces **MuK's stock colours only**. As soon as an administrator
  picks other AppsBar colours in the MuK theme settings, those are used. The MuK
  settings form keeps showing MuK's stock values while the default is active.
- To keep MuK's stock dark sidebar, set `$algorithma-nav-default-palette: false`
  in an earlier primary-variables file, or change one of the two MuK colours.
- Group headers, app lists and rail icons choose their colours from the sidebar
  background: light greys on a light sidebar, tints of the text colour on a
  dark one.

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

Collapse preferences are stored per database, user and browser. Selecting an app
opens its group; a user can then collapse it again. The small sidebar and medium
screen layout expose unhidden permitted apps in group flyouts, including closed groups.

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

## Version and implementation

This package is for **Odoo 20** and depends on `muk_web_appsbar`. Install it
separately for each tenant database. Do not load the Odoo 18 variant alongside it.

The frontend targets MuK AppsBar **20.0.1.2.8**. It uses Owl 3's `proxy` state and
MuK's `appMenuService.selectApp` API. Field widgets use `useProps`, and shared
icons receive explicit Owl 3 template parameters. The server returns ordered
group names and menu IDs; app data and icon URLs come from the existing MuK menu service. Nested
group lists omit MuK 20's additional list padding in the compact sidebar.
The group chevron uses inline SVG because Odoo 20 no longer provides the old
Font Awesome glyph; application icons remain unchanged.

Uninstalling removes this add-on's configuration and restores MuK's flat sidebar.
It does not remove business applications. A later Odoo or MuK major version
requires its own compatibility check.

## Validation

Version `20.0.1.4.0` passed 40 native Odoo tests and 23 helper checks on Odoo 20.0 with MuK AppsBar 20.0.1.2.8. Drag and drop, group creation, renaming, colouring and deletion, the own arrangement of an administrator and of an ordinary user, and resetting to the default were exercised by hand in a browser; this repository contains no automated browser test for them.

Validated on Odoo **20.0-20261102**, PostgreSQL 16 and MuK AppsBar
**20.0.1.2.8** with the full MuK theme. Version `20.0.1.2.0` passed nineteen
backend tests, eleven shared helper checks and fifteen Chromium workflows.
The checks cover permitted and hidden app filtering, compact group flyouts,
hover and keyboard interaction, native app links/icons, and sidebar collapse.
Hidden apps remain absent when their group is empty or archived and when the
filtered flat fallback is shown. Odoo 20 validation used an isolated database;
it is not a production deployment or an Odoo 18 database migration.

Earlier version 20.0.1.1.0 passed fifteen backend
tests, eight shared helper checks and fourteen real Chromium workflows. These
covered color presets and custom values, all twelve SVG symbols and previews,
their rendered path geometry, save/reload/clear, whole-sidebar collapse and
persistence, keyboard focus, content width, compact/mobile layouts, restricted
users and flat fallback.
An actual 1.0.0-to-1.1.0 upgrade preserved all seven existing groups, three app
assignments and 230 native menus; the six initial groups received their missing
styles. No browser JavaScript, console or asset-loading errors occurred. This
validation is not a production Odoo 20 deployment or an Odoo 18 database
migration.

Earlier version `20.0.1.1.1` changed the sidebar controls only. Nine focused Odoo 20
browser workflows verified both buttons, the 224/46-pixel layouts, app links,
tooltips and keyboard focus, reload/group-state persistence, native Small
preferences, and medium/mobile/home/fullscreen behavior. No browser JavaScript,
console or asset errors occurred; Python model code was unchanged in that version.

## Credits and license

LGPL-3. The sidebar link markup is adapted from MuK AppsBar by MuK IT GmbH and
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

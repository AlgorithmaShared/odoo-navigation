# Algorithma Navigation for Odoo 19

Adds optional application groups and standalone application links to MuK
AppsBar. Original application objects, icons, actions and Odoo access rights
remain in use. Grouping changes the sidebar presentation without changing
native menu parents or granting business access.

This `19.0` package targets Odoo 19 and module version `19.0.1.3.0`. Use only
the matching Odoo branch and MuK AppsBar major version. This addon does not
perform an Odoo database migration.

## Configuration

Use **Settings → General Settings → Navigation → Apps gruppieren** to enable
or disable grouping for every user in the database. Disabling grouping shows
all permitted, nonhidden apps in native MuK order. Existing groups,
assignments, styling and hidden-app choices remain stored for re-enabling.

Use **Settings → Navigation → App-Zuordnungen** to select an app's group,
leave **Gruppe** empty to display that app directly, or hide it from the
sidebar. Unassigned apps and apps in archived or deleted groups appear
directly after the active groups, in native MuK order. There is no automatic
**Weitere Apps** section. Deleting a group preserves its app assignments and
hidden-app choices, with their group cleared.

Manage group names, order, optional colors and symbols under **Settings →
Navigation → App-Gruppen**. Six editable starter groups assign only standard
apps already installed. Empty or inaccessible groups are omitted. Group and
app ordering apply within groups; direct apps retain native MuK order.

Each group may use a complete `#RRGGBB` color and one of twelve bundled line
symbols. The form provides color presets, a native picker and symbol previews.
Clearing either field restores the neutral grey appearance; application icons
remain unchanged. A configured MuK sidebar logo remains centered at half its
available width. This module includes no customer logo.

Save and reload the web client after changing configuration.

## Compact navigation

The **Navigation** arrow and navbar button switch between the full sidebar
and a 46-pixel compact rail. Groups and direct apps can coexist: hover or click
a group symbol to open its permitted apps in a flyout, or click a direct
app's native icon to open it. With grouping disabled, the compact rail shows
native app icons only.

On group symbols, Enter, Space or Arrow Right opens the flyout. Arrow keys
move between apps; Escape closes the flyout and returns focus. The pointer
can move from a group into its flyout without closing it. Flyouts retain
native app icons, names and actions.

Group collapse and sidebar-width preferences are local to each database,
user and browser. Opening an app expands its group; expanding the sidebar
restores group-collapse choices. MuK's saved user setting is unchanged.
Controls appear from 992 pixels wide, medium screens use compact navigation,
and phones keep native app navigation. Hidden-sidebar, home, fullscreen and
editor exceptions remain respected.

## Hiding apps

Administrators can enable **In Seitenleiste ausblenden** for an app under
**App-Zuordnungen**. This applies to every user, including direct apps,
archived groups and globally disabled grouping. It changes presentation only:
native app permissions, menus, actions and other access paths remain intact.
Clearing the checkbox or deleting an assignment shows the permitted app
again after reloading.

Only Settings administrators can edit configuration. The internal-user API
returns active groups intersected with permitted native root menus, hidden
permitted menu IDs and the database-wide `grouping_enabled` flag. The frontend
also filters against MuK's actual app list. Portal and public users cannot
call either navigation API.

## Installation and removal

Install the matching `muk_web_appsbar` and its dependencies, add this
repository directory to Odoo's addons path, update the apps list and install
`algorithma_navigation` separately in each tenant database. No MuK source files
are overwritten. No Algorithma theme-fix module is required.

Uninstalling removes this module's configuration and frontend extension,
restoring MuK's normal flat sidebar. Business applications remain installed.

## Odoo 19 implementation

The frontend uses Odoo 19's Owl 2 `useState` API, MuK AppsBar's native
`_onAppClick` method and the native menu service. The navbar insertion point,
standard field props and positioned popover hooks retain their Odoo 19 APIs.
This branch does not use the Owl 3-specific implementation from Odoo 20.

The server uses Odoo 19 `models.Constraint` and `group_ids`. Its configuration
API still uses `get_param`/`set_param`; the grouping setting preserves an explicit
`False` value so an unchecked, enabled-by-default setting survives reloads.

## Validation

Validated against Odoo **19.0-20261112**, PostgreSQL 16 and the official MuK
`19.0` branch pinned at commit `76019c27433db57276e206bd7b923a9699f9b5bd`
(AppsBar **19.0.1.1.14**). Version **19.0.1.3.0** passed:

- 25 native navigation tests on a fresh isolated database.
- 14 standalone grouping and storage checks.
- 12 Chromium workflows covering native configuration saves/reloads, group
  removal, direct apps, compact hover and keyboard flyouts, central hiding,
  ordinary-user permissions, and the color/symbol widgets.
- Seven computed contrast checks for neutral and colored group headers,
  hover/active rows, and compact icons on MuK's native dark sidebar. The checked
  text and icon states met their contrast thresholds; screenshots were also
  inspected visually.

The Odoo 19 styles keep group labels readable on their light surfaces and use
native sidebar text colors for compact group icons. Colored headers tint an
opaque light base. Direct native app rows retain MuK's appearance.

No browser JavaScript or asset-loading errors occurred. This validation does
not perform a production deployment or an Odoo database migration.

Run the standalone grouping and storage checks with:

```sh
node scripts/test_navigation_groups.mjs
```

Run native regression tests in an isolated database with
`--test-enable --test-tags=/algorithma_navigation`. Browser validation must
cover native app links and icons, optional grouping, direct apps, global
hiding, real settings saves/reloads, compact flyouts, keyboard navigation,
medium/mobile layouts and ordinary-user permissions.

## Credits and license

LGPL-3. The sidebar markup is adapted from MuK AppsBar by MuK IT GmbH and
Mathias Markl, also LGPL-3. Original project:
<https://github.com/muk-it/odoo-modules>.

The twelve original inline SVG symbols have an MIT license in
`static/src/group_icons.LICENSE`. The complete LGPL/GPL texts and icon notice
are included. Symbols require no external font or CDN.

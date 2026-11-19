# Algorithma Navigation for Odoo 18

Configurable application groups for [MuK AppsBar](https://github.com/muk-it/odoo-modules). Native app icons, actions and access rights are preserved.

## Versions

| Odoo | Branch | Status |
| --- | --- | --- |
| 18 | `18.0` | Tested; module version `18.0.1.4.0` |
| 19 | `19.0` | Tested; module version `19.0.1.4.0` |
| 20 | `20.0` | Tested; module version `20.0.1.4.0` |

This branch contains **Odoo 18 only**. Check out the matching branch for your server. This addon does not perform an Odoo database migration.

## Features

- Editable app groups with optional colors and twelve bundled symbols.
- **Arrange directly in the sidebar:** click the pencil next to **Navigation** and drag apps into groups, between groups or out of every group, drag groups to reorder them, and create, rename, colour or delete groups on the spot.
- **An own arrangement for every user:** each user arranges the own sidebar; it is stored per user and replaces the default for that user only. Administrators also keep the default for everyone without an own arrangement.
- Central **Apps gruppieren** setting to switch grouping on or off without deleting assignments.
- A light sidebar as the default look. Colours chosen in the MuK theme settings still win, and groups stay readable on a dark sidebar too.
- Apps with an empty group appear directly after the groups, without a catch-all group.
- A compact 46-pixel rail with group hover/click/keyboard flyouts and separate icons for ungrouped apps.
- Administrators can hide individual sidebar apps for all users. This changes presentation, not access permissions.
- Group collapse and sidebar width are remembered per browser, user and database.

## Installation

1. Use this repository's `18.0` branch with Odoo 18.
2. Install the matching MuK `muk_web_appsbar` and its dependencies from the MuK repository.
3. Add this repository directory to Odoo's addons path, update the apps list and install `algorithma_navigation`.
4. Install and configure the addon separately in each tenant database.

No MuK source files need to be edited.

## Configuration

- **Settings → General Settings → Navigation → Apps gruppieren** controls grouping for the entire database.
- **Settings → Navigation → App-Gruppen** manages groups and their styles.
- **Settings → Navigation → App-Zuordnungen** assigns apps, leaves individual apps ungrouped, or hides them from the sidebar.
- The **pencil** next to **Navigation** in the wide sidebar opens the drag and drop editor. Every user edits the own arrangement there; administrators switch between **Für mich** and **Für alle** (the default). Every change is saved at once.

Changes made in the drag and drop editor show at once for the person who made them; changes to the default reach other users after reloading. Save and reload the web client after changes in the settings lists. Existing assignments and hidden-app choices survive switching grouping off and on. Original app permissions still apply.

## Validation

Version `18.0.1.4.0` passed 39 native Odoo tests and 23 helper checks on Odoo 18.0 with MuK AppsBar 18.0.1.1.6. Drag and drop, group creation, renaming, colouring and deletion, the own arrangement of an administrator and of an ordinary user, and resetting to the default were exercised by hand in a browser; this repository contains no automated browser test for them.

For version `1.3.0`: The Odoo 18, 19 and 20 variants each passed 25 native navigation tests. Isolated Chromium validation covered eight workflows on Odoo 18, twelve on Odoo 19 and eight on Odoo 20. Odoo 20 also passed two native web tests. The workflows cover the settings save/reload cycle, direct ungrouped apps, group flyouts, central hiding and ordinary-user permissions. Odoo 19 additionally includes rendered contrast checks for neutral and colored group headers, app rows and compact icons.

Run the standalone helper checks from this repository root:

```sh
node scripts/test_navigation_groups.mjs
```

These 23 checks require only Node.js. Native Odoo regression tests are in `algorithma_navigation/tests`; run them in an isolated database with `--test-enable --test-tags=/algorithma_navigation`.

See [the module README](algorithma_navigation/README.md) for further configuration and version notes.

## License and credits

LGPL-3. The sidebar markup includes adaptations of MuK AppsBar by MuK IT GmbH and Mathias Markl. The original twelve inline SVG symbols have a separate MIT notice in `algorithma_navigation/static/src/group_icons.LICENSE`. The complete LGPL/GPL and icon notices are included.

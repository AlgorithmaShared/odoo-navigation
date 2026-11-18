# Algorithma Navigation for Odoo 20

Configurable application groups for [MuK AppsBar](https://github.com/muk-it/odoo-modules). Native app icons, actions and access rights are preserved.

## Versions

| Odoo | Branch | Status |
| --- | --- | --- |
| 18 | `18.0` | Tested; module version `18.0.1.3.0` |
| 19 | `19.0` | Tested; module version `19.0.1.3.0` |
| 20 | `20.0` | Tested; module version `20.0.1.3.0` |

This branch contains **Odoo 20 only**. Check out the matching branch for your server. This addon does not perform an Odoo database migration.

## Features

- Editable app groups with optional colors and twelve bundled symbols.
- Central **Apps gruppieren** setting to switch grouping on or off without deleting assignments.
- Apps with an empty group appear directly after the groups, without a catch-all group.
- A compact 46-pixel rail with group hover/click/keyboard flyouts and separate icons for ungrouped apps.
- Administrators can hide individual sidebar apps for all users. This changes presentation, not access permissions.
- Group collapse and sidebar width are remembered per browser, user and database.

## Installation

1. Use this repository's `20.0` branch with Odoo 20.
2. Install the matching MuK `muk_web_appsbar` and its dependencies from the MuK repository.
3. Add this repository directory to Odoo's addons path, update the apps list and install `algorithma_navigation`.
4. Install and configure the addon separately in each tenant database.

No MuK source files need to be edited.

## Configuration

- **Settings → General Settings → Navigation → Apps gruppieren** controls grouping for the entire database.
- **Settings → Navigation → App-Gruppen** manages groups and their styles.
- **Settings → Navigation → App-Zuordnungen** assigns apps, leaves individual apps ungrouped, or hides them from the sidebar.

Save and reload the web client after configuration changes. Existing assignments and hidden-app choices survive switching grouping off and on. Original app permissions still apply.

## Validation

The Odoo 18, 19 and 20 variants each passed 25 native navigation tests. Isolated Chromium validation covered eight workflows on Odoo 18, twelve on Odoo 19 and eight on Odoo 20. Odoo 20 also passed two native web tests. The workflows cover the settings save/reload cycle, direct ungrouped apps, group flyouts, central hiding and ordinary-user permissions. Odoo 19 additionally includes rendered contrast checks for neutral and colored group headers, app rows and compact icons.

Run the standalone helper checks from this repository root:

```sh
node scripts/test_navigation_groups.mjs
```

These 14 checks require only Node.js. Native Odoo regression tests are in `algorithma_navigation/tests`; run them in an isolated database with `--test-enable --test-tags=/algorithma_navigation`.

See [the module README](algorithma_navigation/README.md) for further configuration and version notes.

## License and credits

LGPL-3. The sidebar markup includes adaptations of MuK AppsBar by MuK IT GmbH and Mathias Markl. The original twelve inline SVG symbols have a separate MIT notice in `algorithma_navigation/static/src/group_icons.LICENSE`. The complete LGPL/GPL and icon notices are included.

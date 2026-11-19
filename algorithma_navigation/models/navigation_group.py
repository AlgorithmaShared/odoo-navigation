import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


GROUPING_ENABLED_PARAM = "algorithma_navigation.grouping_enabled"


GROUP_ICONS = [
    ("home", "Haus"), ("briefcase", "Aktentasche"), ("folder", "Ordner"),
    ("receipt", "Beleg"), ("users", "Personen"), ("settings", "Einstellungen"),
    ("calendar", "Kalender"), ("building", "Gebäude"), ("chart", "Diagramm"),
    ("truck", "Fahrzeug"), ("star", "Stern"), ("heart", "Herz"),
]

DEFAULT_GROUP_STYLES = (
    ("group_everyday", "#2563EB", "home"),
    ("group_sales", "#059669", "chart"),
    ("group_operations", "#D97706", "briefcase"),
    ("group_finance", "#7C3AED", "receipt"),
    ("group_people", "#DB2777", "users"),
    ("group_system", "#64748B", "settings"),
)


class NavigationGroup(models.Model):
    _name = "algorithma.navigation.group"
    _description = "App-Gruppe"
    _order = "sequence, id"

    name = fields.Char(string="Name", required=True, translate=True)
    sequence = fields.Integer(string="Reihenfolge", default=10)
    active = fields.Boolean(string="Aktiv", default=True)
    color = fields.Char(string="Farbe", help="Optionale Farbe im Format #RRGGBB.")
    icon = fields.Selection(GROUP_ICONS, string="Gruppensymbol")
    item_ids = fields.One2many(
        "algorithma.navigation.item", "group_id", string="Apps", copy=False,
    )

    @api.constrains("name")
    def _check_name(self):
        for group in self:
            if not (group.name or "").strip():
                raise ValidationError(_("Eine App-Gruppe benötigt einen Namen."))

    @api.constrains("color")
    def _check_color(self):
        for group in self:
            if group.color and not re.fullmatch(r"#[0-9a-fA-F]{6}", group.color):
                raise ValidationError(_("Bitte eine Farbe im Format #RRGGBB angeben, zum Beispiel #2563EB."))

    @api.model
    def _fill_default_group_styles(self):
        """Upgrade existing defaults without changing administrator choices."""
        changed = 0
        for xmlid, color, icon in DEFAULT_GROUP_STYLES:
            group = self.env.ref("algorithma_navigation." + xmlid, raise_if_not_found=False)
            if not group or not group.exists():
                continue
            values = {}
            if not group.color:
                values["color"] = color
            if not group.icon:
                values["icon"] = icon
            if values:
                group.write(values)
                changed += 1
        return changed

    @api.model
    def _get_sidebar_visible_root_ids(self):
        """Evaluate native menu permissions before reading configuration."""

        if not self.env.su and not self.env.user.has_group("base.group_user"):
            raise AccessError(_("Die App-Navigation ist nur für interne Benutzer verfügbar."))
        menu_model = self.env["ir.ui.menu"].with_context(
            **{"ir.ui.menu.full_list": False, "active_test": True}
        )
        return set(menu_model.get_user_roots().ids)

    @api.model
    def get_sidebar_groups(self):
        """Return ordered groups with app IDs permitted to the caller.

        Keep this API compatible: presentation-only hiding is exposed separately
        by get_sidebar_config(). Caller context cannot bypass menu permissions.
        """
        visible_roots = self._get_sidebar_visible_root_ids()
        result = []
        groups = self.sudo().with_context(active_test=True).search([("active", "=", True)])
        for group in groups:
            items = group.item_ids.sorted(key=lambda item: (item.sequence, item.id))
            menu_ids = [item.menu_id.id for item in items if item.menu_id.id in visible_roots]
            if menu_ids:
                result.append({
                    "id": group.id, "name": group.name, "menu_ids": menu_ids,
                    "color": group.color or False, "icon": group.icon or False,
                })
        return result

    @api.model
    def get_sidebar_config(self):
        """Return sidebar preferences without granting or revoking app access."""
        visible_roots = self._get_sidebar_visible_root_ids()
        hidden_items = self.env["algorithma.navigation.item"].sudo().with_context(
            active_test=True
        ).search([
            ("hidden", "=", True), ("menu_id", "in", sorted(visible_roots)),
        ])
        return {
            "groups": self.get_sidebar_groups(),
            "grouping_enabled": self.env["ir.config_parameter"].sudo().get_bool(
                GROUPING_ENABLED_PARAM, True,
            ),
            # Include assignments in archived groups: archiving changes grouping,
            # not an administrator's explicit choice to hide an app.
            "hidden_menu_ids": hidden_items.mapped("menu_id").ids,
        }

    # ------------------------------------------------------------------
    # Sidebar editor: arrange groups and apps by drag and drop
    # ------------------------------------------------------------------
    # The arrangement is shared by every user of the database, so only
    # settings administrators may read the editor data or store a layout.
    # No sudo() is used for writing: the model access rights apply as well.

    @api.model
    def _check_sidebar_editor_access(self):
        """Refuse everyone except settings administrators."""
        if not self.env.su and not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Nur Administratoren können die Navigation anordnen."))

    @api.model
    def get_sidebar_editor_config(self):
        """Return the data the sidebar editor works on.

        Unlike get_sidebar_groups(), empty groups are included so that apps can
        be dragged into a group that was just created.
        """
        self._check_sidebar_editor_access()
        visible_roots = self._get_sidebar_visible_root_ids()
        editor_groups = []
        # Archived groups are not part of the navigation, whatever the caller context says.
        for group in self.with_context(active_test=True).search([]):
            items = group.item_ids.sorted(key=lambda item: (item.sequence, item.id))
            editor_groups.append({
                "id": group.id, "name": group.name,
                "menu_ids": [item.menu_id.id for item in items if item.menu_id.id in visible_roots],
                "color": group.color or False, "icon": group.icon or False,
            })
        return {"editor_groups": editor_groups, "config": self.get_sidebar_config()}

    @api.model
    def _validate_sidebar_layout(self, groups, ungrouped_menu_ids):
        """Check the shape of a layout sent by the browser.

        :return: (list of (group record, ordered menu ids), list of ungrouped menu ids)
        """
        def is_record_id(value):
            # bool is a subclass of int in Python; it is never a valid record id.
            return type(value) is int and value > 0

        invalid = ValidationError(_("Die Anordnung der Navigation ist ungültig. Bitte die Seite neu laden."))
        if not isinstance(groups, list) or not isinstance(ungrouped_menu_ids, list):
            raise invalid
        group_ids, grouped_menu_ids = [], []
        for entry in groups:
            if (
                not isinstance(entry, dict) or not is_record_id(entry.get("id"))
                or not isinstance(entry.get("menu_ids"), list)
                or not all(is_record_id(menu_id) for menu_id in entry["menu_ids"])
            ):
                raise invalid
            group_ids.append(entry["id"])
            grouped_menu_ids.extend(entry["menu_ids"])
        if not all(is_record_id(menu_id) for menu_id in ungrouped_menu_ids):
            raise invalid
        all_menu_ids = grouped_menu_ids + ungrouped_menu_ids
        # Every group and every app may appear only once in a layout.
        if len(set(group_ids)) != len(group_ids) or len(set(all_menu_ids)) != len(all_menu_ids):
            raise invalid
        group_records = self.browse(group_ids).exists()
        menus = self.env["ir.ui.menu"].with_context(
            **{"ir.ui.menu.full_list": True}
        ).browse(all_menu_ids).exists()
        if len(group_records) != len(group_ids) or len(menus) != len(all_menu_ids):
            raise invalid
        if any(menu.parent_id for menu in menus):
            raise ValidationError(_("Es können nur Apps mit einem Hauptmenü zugeordnet werden, keine Untermenüs."))
        layout = [(self.browse(entry["id"]), entry["menu_ids"]) for entry in groups]
        return layout, ungrouped_menu_ids

    @api.model
    def save_sidebar_layout(self, groups, ungrouped_menu_ids=None):
        """Store the arrangement made by drag and drop in the sidebar.

        :param groups: groups in display order, each ``{"id": group id,
            "menu_ids": app ids in display order}``
        :param ungrouped_menu_ids: apps that were dragged out of every group
        :return: the fresh editor data, see get_sidebar_editor_config()

        Assignments that are not mentioned (hidden apps, apps the caller
        cannot see) stay exactly as they are, including their hidden flag.
        """
        self._check_sidebar_editor_access()
        layout, ungrouped_menu_ids = self._validate_sidebar_layout(groups, ungrouped_menu_ids or [])
        Item = self.env["algorithma.navigation.item"]
        mentioned_menu_ids = [menu_id for _group, menu_ids in layout for menu_id in menu_ids] + ungrouped_menu_ids
        item_by_menu_id = {
            item.menu_id.id: item for item in Item.search([("menu_id", "in", mentioned_menu_ids)])
        }
        for group_position, (group, menu_ids) in enumerate(layout, start=1):
            group.sequence = group_position * 10
            for app_position, menu_id in enumerate(menu_ids, start=1):
                values = {"group_id": group.id, "sequence": app_position * 10}
                item = item_by_menu_id.get(menu_id)
                if item:
                    item.write(values)
                else:
                    Item.create(dict(values, menu_id=menu_id))
        for menu_id in ungrouped_menu_ids:
            # Keep the row: it may carry the "hidden" choice of an administrator.
            item = item_by_menu_id.get(menu_id)
            if item and item.group_id:
                item.group_id = False
        return self.get_sidebar_editor_config()


class NavigationItem(models.Model):
    _name = "algorithma.navigation.item"
    _description = "App-Zuordnung"
    _order = "sequence, id"
    _rec_name = "menu_id"

    group_id = fields.Many2one(
        "algorithma.navigation.group", string="Gruppe", ondelete="set null", index=True,
        help="Ohne Gruppe erscheint die App direkt in der Seitenleiste. "
             "Das Ausblenden bleibt unabhängig von der Gruppenzuordnung erhalten.",
    )
    menu_id = fields.Many2one(
        "ir.ui.menu", string="App", required=True, ondelete="cascade", index=True,
        domain=[("parent_id", "=", False)],
    )
    sequence = fields.Integer(string="Reihenfolge", default=10)
    hidden = fields.Boolean(
        string="In Seitenleiste ausblenden", default=False,
        help="Blendet diese App für alle Benutzer aus der Seitenleiste aus. "
             "Ihre App-Berechtigungen und andere Zugriffswege bleiben erhalten.",
    )

    _menu_unique = models.Constraint(
        "UNIQUE(menu_id)",
        "Eine App kann nur einer Gruppe zugeordnet werden. Entfernen Sie zuerst die bestehende Zuordnung.",
    )

    @api.constrains("menu_id")
    def _check_root_menu(self):
        for item in self:
            if item.menu_id.parent_id:
                raise ValidationError(_("Es können nur Apps mit einem Hauptmenü zugeordnet werden, keine Untermenüs."))

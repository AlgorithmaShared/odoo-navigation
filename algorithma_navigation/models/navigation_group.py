import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


GROUPING_ENABLED_PARAM = "algorithma_navigation.grouping_enabled"
GROUP_COLOR_PATTERN = r"#[0-9a-fA-F]{6}"
# Limits for a personal arrangement, to keep one user's stored layout small.
PERSONAL_LAYOUT_MAX_GROUPS = 100
PERSONAL_GROUP_NAME_MAX_LENGTH = 100


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
            if group.color and not re.fullmatch(GROUP_COLOR_PATTERN, group.color):
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
        personal_layout = self._get_personal_layout_record()
        if personal_layout:
            # A personal arrangement replaces the shared groups for this user only.
            return self._clean_personal_groups(personal_layout.layout, visible_roots, keep_empty=False)
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
    # Two layers exist:
    #   default   the shared arrangement kept in this model. Only settings
    #             administrators may change it.
    #   personal  one arrangement per user (algorithma.navigation.user.layout).
    #             Every internal user may keep one. It replaces the default
    #             for that user only and never changes access rights.
    # Personal layouts are read and written through sudo() and are always
    # bound to the calling user. The default is written without sudo(), so
    # the model access rights apply as well.

    @api.model
    def _is_sidebar_administrator(self):
        return self.env.su or self.env.user.has_group("base.group_system")

    @api.model
    def _check_sidebar_editor_access(self):
        """Refuse everyone except settings administrators (shared default)."""
        if not self._is_sidebar_administrator():
            raise AccessError(_("Nur Administratoren können die Navigation für alle anordnen."))

    @api.model
    def _get_personal_layout_record(self):
        """The personal arrangement of the calling user, if any."""
        return self.env["algorithma.navigation.user.layout"].sudo().search(
            [("user_id", "=", self.env.uid)], limit=1,
        )

    @api.model
    def _clean_personal_groups(self, stored_groups, visible_roots, keep_empty):
        """Turn a stored personal layout into the payload shape of shared groups.

        Stored data is checked again on every read: unknown or meanwhile
        inaccessible apps are dropped, and nothing but validated colours and
        symbols reaches the browser.
        """
        icon_keys = {key for key, _label in GROUP_ICONS}
        result, seen_group_ids, seen_menu_ids = [], set(), set()
        for entry in stored_groups if isinstance(stored_groups, list) else []:
            if not isinstance(entry, dict):
                continue
            group_id, name = entry.get("id"), entry.get("name")
            if (
                type(group_id) is not int or group_id <= 0 or group_id in seen_group_ids
                or not isinstance(name, str) or not name.strip()
            ):
                continue
            seen_group_ids.add(group_id)
            menu_ids = []
            for menu_id in entry.get("menu_ids") or []:
                if type(menu_id) is int and menu_id in visible_roots and menu_id not in seen_menu_ids:
                    seen_menu_ids.add(menu_id)
                    menu_ids.append(menu_id)
            if not menu_ids and not keep_empty:
                continue
            color, icon = entry.get("color"), entry.get("icon")
            result.append({
                "id": group_id, "name": name, "menu_ids": menu_ids,
                "color": color if isinstance(color, str) and re.fullmatch(GROUP_COLOR_PATTERN, color) else False,
                "icon": icon if icon in icon_keys else False,
            })
        return result

    @api.model
    def _get_shared_editor_groups(self, visible_roots, keep_empty):
        """The active shared groups the editor starts from.

        :param keep_empty: also return groups without any app the caller may
            open. Administrators need them to drag apps into a new group.
            For everyone else such a group stays out: they learn the name of
            a default group only when it holds one of their apps.
        """
        editor_groups = []
        # Archived groups are not part of the navigation, whatever the caller context says.
        for group in self.sudo().with_context(active_test=True).search([]):
            items = group.item_ids.sorted(key=lambda item: (item.sequence, item.id))
            menu_ids = [item.menu_id.id for item in items if item.menu_id.id in visible_roots]
            if not menu_ids and not keep_empty:
                continue
            editor_groups.append({
                "id": group.id, "name": group.name, "menu_ids": menu_ids,
                "color": group.color or False, "icon": group.icon or False,
            })
        return editor_groups

    @api.model
    def _resolve_sidebar_editor_scope(self, scope):
        """Decide which layer the editor works on: "default" or "personal"."""
        if scope == "default":
            self._check_sidebar_editor_access()
            return "default"
        if scope == "personal":
            return "personal"
        if scope not in (None, False):
            raise ValidationError(_("Unbekannter Bereich für die Navigation."))
        # No wish given: an administrator without a personal arrangement keeps
        # editing the shared default, everyone else their own arrangement.
        if self._is_sidebar_administrator() and not self._get_personal_layout_record():
            return "default"
        return "personal"

    @api.model
    def get_sidebar_editor_config(self, scope=None):
        """Return the data the sidebar editor works on.

        :param scope: "default" (administrators only), "personal", or None to
            let the server choose, see _resolve_sidebar_editor_scope().

        Unlike get_sidebar_groups(), empty groups are included so that apps can
        be dragged into a group that was just created. A user without a
        personal arrangement starts from the shared default; an ordinary user
        gets only the default groups that hold an app that user may open.
        """
        visible_roots = self._get_sidebar_visible_root_ids()
        scope = self._resolve_sidebar_editor_scope(scope)
        personal_layout = self._get_personal_layout_record()
        if scope == "personal" and personal_layout:
            editor_groups = self._clean_personal_groups(personal_layout.layout, visible_roots, keep_empty=True)
        else:
            editor_groups = self._get_shared_editor_groups(
                visible_roots, keep_empty=self._is_sidebar_administrator(),
            )
        return {
            "editor_groups": editor_groups,
            "config": self.get_sidebar_config(),
            "scope": scope,
            "has_personal_layout": bool(personal_layout),
            "can_edit_default": self._is_sidebar_administrator(),
        }

    # ----- shared default (administrators) -----

    @api.model
    def _validate_sidebar_layout(self, groups, ungrouped_menu_ids):
        """Check the shape of a default layout sent by the browser.

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
        """Store the shared default arrangement made by drag and drop.

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
        return self.get_sidebar_editor_config("default")

    # ----- personal arrangement (every internal user, own layout only) -----

    @api.model
    def _validate_personal_layout(self, groups, visible_roots):
        """Check a personal layout sent by the browser and return what is stored.

        A personal group lives only inside the layout: it has a number that is
        unique within the layout, a name, an optional colour and symbol, and
        the apps in display order. Only apps the user may open are accepted.
        """
        invalid = ValidationError(_("Die Anordnung der Navigation ist ungültig. Bitte die Seite neu laden."))
        icon_keys = {key for key, _label in GROUP_ICONS}
        if not isinstance(groups, list) or len(groups) > PERSONAL_LAYOUT_MAX_GROUPS:
            raise invalid
        cleaned, seen_group_ids, seen_menu_ids = [], set(), set()
        for entry in groups:
            if not isinstance(entry, dict):
                raise invalid
            group_id, name, menu_ids = entry.get("id"), entry.get("name"), entry.get("menu_ids")
            color, icon = entry.get("color") or False, entry.get("icon") or False
            if (
                type(group_id) is not int or group_id <= 0 or group_id in seen_group_ids
                or not isinstance(name, str) or not name.strip()
                or len(name.strip()) > PERSONAL_GROUP_NAME_MAX_LENGTH
                or not isinstance(menu_ids, list)
                or (color and not (isinstance(color, str) and re.fullmatch(GROUP_COLOR_PATTERN, color)))
                or (icon and icon not in icon_keys)
            ):
                raise invalid
            seen_group_ids.add(group_id)
            for menu_id in menu_ids:
                if type(menu_id) is not int or menu_id in seen_menu_ids or menu_id not in visible_roots:
                    raise invalid
                seen_menu_ids.add(menu_id)
            cleaned.append({
                "id": group_id, "name": name.strip(), "color": color, "icon": icon, "menu_ids": list(menu_ids),
            })
        return cleaned

    @api.model
    def save_personal_sidebar_layout(self, groups):
        """Store the calling user's own arrangement; nobody else is affected.

        :param groups: every personal group in display order, each ``{"id",
            "name", "color", "icon", "menu_ids"}``. Apps outside every group
            simply appear without a group.
        :return: the fresh editor data, see get_sidebar_editor_config()
        """
        visible_roots = self._get_sidebar_visible_root_ids()
        cleaned_groups = self._validate_personal_layout(groups, visible_roots)
        personal_layout = self._get_personal_layout_record()
        if personal_layout:
            personal_layout.layout = cleaned_groups
        else:
            self.env["algorithma.navigation.user.layout"].sudo().create({
                "user_id": self.env.uid, "layout": cleaned_groups,
            })
        return self.get_sidebar_editor_config("personal")

    @api.model
    def reset_personal_sidebar_layout(self):
        """Drop the calling user's own arrangement and show the default again."""
        self._get_sidebar_visible_root_ids()
        self._get_personal_layout_record().unlink()
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


class NavigationUserLayout(models.Model):
    """One personal sidebar arrangement per user.

    The layout is a list of personal groups, see
    NavigationGroup._validate_personal_layout(). It is only reached through
    the methods of algorithma.navigation.group, which bind it to the caller.
    """
    _name = "algorithma.navigation.user.layout"
    _description = "Persönliche App-Anordnung"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users", string="Benutzer", required=True, ondelete="cascade", index=True,
    )
    layout = fields.Json(string="Anordnung")

    _user_unique = models.Constraint(
        "UNIQUE(user_id)",
        "Jeder Benutzer hat höchstens eine persönliche Anordnung.",
    )

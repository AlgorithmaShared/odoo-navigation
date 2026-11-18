import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import str2bool


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
            "grouping_enabled": str2bool(
                self.env["ir.config_parameter"].sudo().get_param(
                    GROUPING_ENABLED_PARAM, "True"
                ), True,
            ),
            # Include assignments in archived groups: archiving changes grouping,
            # not an administrator's explicit choice to hide an app.
            "hidden_menu_ids": hidden_items.mapped("menu_id").ids,
        }


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

import importlib.util
from pathlib import Path
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .. import hooks
from ..models.navigation_group import GROUPING_ENABLED_PARAM


@tagged("post_install", "-at_install")
class TestNavigationGroups(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Group = cls.env["algorithma.navigation.group"]
        cls.Item = cls.env["algorithma.navigation.item"]
        cls.env["ir.config_parameter"].sudo().set_bool(GROUPING_ENABLED_PARAM, None)
        internal = cls.env.ref("base.group_user")
        cls.internal_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Navigation Reader", "login": "navigation-test-reader",
            "group_ids": [Command.set([internal.id])],
        })
        cls.portal_user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Navigation Portal", "login": "navigation-test-portal",
            "group_ids": [Command.set([cls.env.ref("base.group_portal").id])],
        })
        cls.hidden_role = cls.env["res.groups"].create({"name": "Navigation Hidden Role"})
        cls.partner_action = cls.env["ir.actions.act_window"].create({
            "name": "Navigation Test Contacts", "res_model": "res.partner", "view_mode": "list,form",
        })
        cls.visible_menu = cls.env["ir.ui.menu"].create({
            "name": "Navigation Visible", "action": "ir.actions.act_window,%s" % cls.partner_action.id,
            "group_ids": [Command.set([internal.id])], "sequence": 910,
        })
        cls.second_menu = cls.visible_menu.copy({"name": "Navigation Second", "sequence": 920})
        cls.hidden_menu = cls.visible_menu.copy({
            "name": "Navigation Hidden", "group_ids": [Command.set([cls.hidden_role.id])],
        })
        cls.child_menu = cls.visible_menu.copy({"name": "Navigation Child", "parent_id": cls.visible_menu.id})
        cls.group = cls.Group.create({"name": "Navigation Test Group", "sequence": 900})
        cls.line = cls.Item.create({"group_id": cls.group.id, "menu_id": cls.visible_menu.id, "sequence": 20})

    def _payload(self, **context):
        return self.Group.with_user(self.internal_user).with_context(**context).get_sidebar_groups()

    def _config(self, **context):
        return self.Group.with_user(self.internal_user).with_context(**context).get_sidebar_config()

    def test_internal_api_allowed_without_configuration_read_access(self):
        payload = {group["id"]: group for group in self._payload()}
        self.assertEqual(payload[self.group.id]["menu_ids"], [self.visible_menu.id])
        self.assertEqual(set(payload[self.group.id]), {"id", "name", "menu_ids", "color", "icon"})
        with self.assertRaises(AccessError):
            self.group.with_user(self.internal_user).read(["name"])
        with self.assertRaises(AccessError):
            self.line.with_user(self.internal_user).read(["menu_id"])
        with self.assertRaises(AccessError):
            self.Group.with_user(self.internal_user).create({"name": "Forbidden"})
        with self.assertRaises(AccessError):
            self.group.with_user(self.internal_user).write({"name": "Forbidden"})
        with self.assertRaises(AccessError):
            self.line.with_user(self.internal_user).write({"hidden": True})
        with self.assertRaises(AccessError):
            self.line.with_user(self.internal_user).unlink()

    def test_portal_and_public_users_cannot_call_api(self):
        for user in (self.portal_user, self.env.ref("base.public_user")):
            for method in ("get_sidebar_groups", "get_sidebar_config"):
                with self.subTest(user=user.login, method=method), self.assertRaises(AccessError):
                    getattr(self.Group.with_user(user), method)()

    def test_hidden_apps_preserve_legacy_payload_and_native_menu_access(self):
        self.assertFalse(self.line.hidden)
        original_payload = self._payload()
        menu_fields = ["name", "parent_id", "action", "sequence", "web_icon", "active", "group_ids"]
        original_menu = self.visible_menu.read(menu_fields)
        original_assignment = self.line.read(["group_id", "menu_id", "sequence"])
        self.assertEqual(self._config(), {
            "groups": original_payload, "hidden_menu_ids": [], "grouping_enabled": True,
        })
        self.line.hidden = True
        config = self._config()
        self.assertEqual(config, {
            "groups": original_payload, "hidden_menu_ids": [self.visible_menu.id],
            "grouping_enabled": True,
        })
        self.assertEqual(self.visible_menu.read(menu_fields), original_menu)
        self.assertEqual(self.line.read(["group_id", "menu_id", "sequence"]), original_assignment)
        self.assertIn(self.visible_menu.id, self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids)
        self.line.hidden = False
        self.assertEqual(self._config()["hidden_menu_ids"], [])

    def test_sidebar_config_never_exposes_unauthorized_hidden_apps(self):
        self.line.hidden = True
        self.Item.create({"group_id": self.group.id, "menu_id": self.hidden_menu.id, "hidden": True})
        action = self.env["ir.actions.act_window"].create({
            "name": "Hidden Protected Config", "res_model": "algorithma.navigation.group", "view_mode": "list",
        })
        protected_menu = self.env["ir.ui.menu"].create({
            "name": "Hidden Protected Root", "action": "ir.actions.act_window,%s" % action.id,
        })
        self.Item.create({"group_id": self.group.id, "menu_id": protected_menu.id, "hidden": True})
        config = self._config(**{"ir.ui.menu.full_list": True, "active_test": False})
        self.assertEqual(config["hidden_menu_ids"], [self.visible_menu.id])
        self.assertNotIn(self.hidden_menu.id, [menu for group in config["groups"] for menu in group["menu_ids"]])
        self.assertNotIn(protected_menu.id, [menu for group in config["groups"] for menu in group["menu_ids"]])

    def test_hiding_survives_archiving_until_assignment_is_removed(self):
        self.line.hidden = True
        self.group.active = False
        config = self._config(active_test=False)
        self.assertNotIn(self.group.id, [group["id"] for group in config["groups"]])
        self.assertEqual(config["hidden_menu_ids"], [self.visible_menu.id])
        self.line.unlink()
        self.assertEqual(self._config()["hidden_menu_ids"], [])
        self.assertIn(self.visible_menu.id, self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids)

    def test_hidden_inactive_or_reparented_apps_are_not_exposed(self):
        self.line.hidden = True
        self.visible_menu.active = False
        self.assertNotIn(self.visible_menu.id, self._config(active_test=False)["hidden_menu_ids"])
        self.visible_menu.active = True
        self.visible_menu.parent_id = self.second_menu
        self.assertNotIn(self.visible_menu.id, self._config()["hidden_menu_ids"])
        self.assertEqual(self.visible_menu.parent_id, self.second_menu)

    def test_hidden_roots_and_their_empty_groups_are_not_exposed(self):
        hidden_group = self.Group.create({"name": "Secret Group"})
        self.Item.create({"group_id": hidden_group.id, "menu_id": self.hidden_menu.id})
        payload = self._payload(**{"ir.ui.menu.full_list": True, "active_test": False})
        self.assertNotIn(hidden_group.id, [group["id"] for group in payload])
        self.assertNotIn(self.hidden_menu.id, [menu for group in payload for menu in group["menu_ids"]])

    def test_model_access_hides_menu_even_without_menu_groups(self):
        action = self.env["ir.actions.act_window"].create({
            "name": "Protected Config", "res_model": "algorithma.navigation.group", "view_mode": "list",
        })
        menu = self.env["ir.ui.menu"].create({
            "name": "Protected Root", "action": "ir.actions.act_window,%s" % action.id,
        })
        self.Item.create({"group_id": self.group.id, "menu_id": menu.id})
        payload = {group["id"]: group for group in self._payload()}
        self.assertEqual(payload[self.group.id]["menu_ids"], [self.visible_menu.id])

    def test_group_and_app_sequence_are_respected(self):
        earlier = self.Group.create({"name": "First Group", "sequence": 800})
        self.Item.create({"group_id": earlier.id, "menu_id": self.second_menu.id})
        payload = self._payload()
        relevant = [group["id"] for group in payload if group["id"] in (earlier.id, self.group.id)]
        self.assertEqual(relevant, [earlier.id, self.group.id])
        self.Item.search([("group_id", "=", earlier.id)]).write({"group_id": self.group.id, "sequence": 10})
        payload = {group["id"]: group for group in self._payload()}
        self.assertEqual(payload[self.group.id]["menu_ids"], [self.second_menu.id, self.visible_menu.id])

    def test_archive_or_delete_assignment_leaves_app_available_for_fallback(self):
        self.group.active = False
        self.assertNotIn(self.group.id, [group["id"] for group in self._payload(active_test=False)])
        self.assertIn(self.visible_menu.id, self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids)
        self.group.active = True
        self.line.unlink()
        self.assertNotIn(self.group.id, [group["id"] for group in self._payload()])
        self.assertIn(self.visible_menu.id, self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids)

    def test_inactive_app_is_not_exposed_by_rpc_context(self):
        self.visible_menu.active = False
        self.assertNotIn(self.group.id, [group["id"] for group in self._payload(active_test=False)])

    def test_app_can_only_belong_to_one_group(self):
        another = self.Group.create({"name": "Another Group"})
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Item.create({"group_id": another.id, "menu_id": self.visible_menu.id})

    def test_submenus_cannot_be_assigned(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Item.create({"group_id": self.group.id, "menu_id": self.child_menu.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.line.menu_id = self.child_menu

    def test_later_menu_reparenting_does_not_leak_or_change_odoo_structure(self):
        self.visible_menu.parent_id = self.second_menu
        self.assertNotIn(self.group.id, [group["id"] for group in self._payload()])
        self.assertEqual(self.visible_menu.parent_id, self.second_menu)

    def test_deleting_group_keeps_assignment_and_hiding_preference(self):
        self.line.hidden = True
        self.group.unlink()
        self.assertTrue(self.line.exists())
        self.line.invalidate_recordset(["group_id"])
        self.assertFalse(self.line.group_id)
        self.assertTrue(self.line.hidden)
        self.assertEqual(self._config()["hidden_menu_ids"], [self.visible_menu.id])
        self.assertTrue(self.visible_menu.exists())
        self.assertFalse(self.visible_menu.parent_id)

    def test_optional_group_preserves_hidden_app_without_native_menu_changes(self):
        menu_fields = ["name", "parent_id", "action", "sequence", "active", "group_ids"]
        original_menu = self.visible_menu.read(menu_fields)
        self.line.write({"group_id": False, "hidden": True})
        config = self._config()
        self.assertNotIn(self.group.id, [group["id"] for group in config["groups"]])
        self.assertEqual(config["hidden_menu_ids"], [self.visible_menu.id])
        self.assertEqual(self.visible_menu.read(menu_fields), original_menu)
        self.assertIn(self.visible_menu.id, self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids)
        self.line.hidden = False
        self.assertEqual(self._config()["hidden_menu_ids"], [])
        ungrouped = self.Item.create({"menu_id": self.second_menu.id, "hidden": True})
        self.assertFalse(ungrouped.group_id)
        self.assertEqual(self._config()["hidden_menu_ids"], [self.second_menu.id])

    def test_global_grouping_setting_persists_false_and_preserves_configuration(self):
        self.line.hidden = True
        group_fields = ["name", "sequence", "active", "color", "icon"]
        item_fields = ["group_id", "menu_id", "sequence", "hidden"]
        before_groups = self.Group.with_context(active_test=False).search([]).read(group_fields)
        before_items = self.Item.search([]).read(item_fields)
        before_payload = self._payload()
        before_roots = self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids
        field_name = "algorithma_navigation_grouping_enabled"
        Settings = self.env["res.config.settings"]
        self.assertTrue(Settings.default_get([field_name])[field_name])
        settings = Settings.create({field_name: False})
        settings.set_values()
        self.assertIs(self.env["ir.config_parameter"].get_bool(GROUPING_ENABLED_PARAM), False)
        self.assertFalse(Settings.default_get([field_name])[field_name])
        self.assertFalse(self._config()["grouping_enabled"])
        self.assertFalse(self.Group.get_sidebar_config()["grouping_enabled"])
        self.assertEqual(self._config()["hidden_menu_ids"], [self.visible_menu.id])
        self.assertEqual(self._payload(), before_payload)
        self.assertEqual(self.env["ir.ui.menu"].with_user(self.internal_user).get_user_roots().ids, before_roots)
        self.assertEqual(self.Group.with_context(active_test=False).search([]).read(group_fields), before_groups)
        self.assertEqual(self.Item.search([]).read(item_fields), before_items)
        settings.write({field_name: True})
        settings.set_values()
        self.assertTrue(Settings.default_get([field_name])[field_name])
        self.assertTrue(self._config()["grouping_enabled"])
        self.assertEqual(self._payload(), before_payload)
        self.assertEqual(self.Item.search([]).read(item_fields), before_items)

    def test_hiding_survives_disabled_grouping_for_ungrouped_and_archived_apps(self):
        self.line.write({"group_id": False, "hidden": True})
        self.Item.create({"group_id": self.group.id, "menu_id": self.second_menu.id, "hidden": True})
        self.group.active = False
        self.env["ir.config_parameter"].set_bool(GROUPING_ENABLED_PARAM, False)
        config = self._config(active_test=False)
        self.assertFalse(config["grouping_enabled"])
        self.assertNotIn(self.group.id, [group["id"] for group in config["groups"]])
        self.assertEqual(set(config["hidden_menu_ids"]), {self.visible_menu.id, self.second_menu.id})

    def test_only_administrators_can_manage_global_grouping_and_assignments(self):
        Settings = self.env["res.config.settings"]
        field_name = "algorithma_navigation_grouping_enabled"
        settings = Settings.create({field_name: False})
        with self.assertRaises(AccessError):
            settings.with_user(self.internal_user).set_values()
        with self.assertRaises(AccessError):
            settings.with_user(self.internal_user).read([field_name])
        with self.assertRaises(AccessError):
            self.Item.with_user(self.internal_user).create({"menu_id": self.second_menu.id})
        menu = self.env.ref("algorithma_navigation.menu_navigation_items")
        self.assertEqual(menu.group_ids, self.env.ref("base.group_system"))
        self.assertNotIn(menu.id, self.env["ir.ui.menu"].with_user(self.internal_user)._visible_menu_ids())

    def test_standalone_assignment_remains_unique_and_rejects_submenus(self):
        self.line.group_id = False
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Item.create({"menu_id": self.visible_menu.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Item.create({"menu_id": self.child_menu.id})

    def test_default_seed_is_idempotent_and_preserves_admin_choices(self):
        for name, menu in (("seed_existing", self.visible_menu), ("seed_new", self.second_menu), ("seed_child", self.child_menu)):
            self.env["ir.model.data"].create({
                "module": "algorithma_navigation", "name": name, "model": "ir.ui.menu", "res_id": menu.id,
            })
        default = self.env.ref("algorithma_navigation.group_everyday")
        default.name = "Admin Renamed This Group"
        original_parent = self.second_menu.parent_id
        seed = (("group_everyday", (
            "algorithma_navigation.seed_existing", "algorithma_navigation.seed_new",
            "algorithma_navigation.seed_child", "algorithma_navigation.missing_app",
        )),)
        with patch.object(hooks, "DEFAULT_GROUP_APPS", seed):
            hooks.post_init_hook(self.env)
            count = self.Item.search_count([])
            hooks.post_init_hook(self.env)
        self.assertEqual(self.Item.search_count([]), count)
        self.assertEqual(self.line.group_id, self.group)
        self.assertEqual(self.Item.search([("menu_id", "=", self.second_menu.id)]).group_id, default)
        self.assertFalse(self.Item.search([("menu_id", "=", self.child_menu.id)]))
        self.assertEqual(default.name, "Admin Renamed This Group")
        self.assertEqual(self.second_menu.parent_id, original_parent)

    def test_default_seed_does_not_regroup_an_explicit_standalone_app(self):
        self.env["ir.model.data"].create({
            "module": "algorithma_navigation", "name": "seed_standalone",
            "model": "ir.ui.menu", "res_id": self.visible_menu.id,
        })
        self.line.write({"group_id": False, "hidden": True})
        before = self.line.read(["group_id", "menu_id", "sequence", "hidden"])
        seed = (("group_everyday", ("algorithma_navigation.seed_standalone",)),)
        with patch.object(hooks, "DEFAULT_GROUP_APPS", seed):
            hooks.post_init_hook(self.env)
            hooks.post_init_hook(self.env)
        self.assertEqual(self.line.read(["group_id", "menu_id", "sequence", "hidden"]), before)
        self.assertEqual(self.Item.search_count([("menu_id", "=", self.visible_menu.id)]), 1)

    def test_style_validation_and_api_payload(self):
        self.group.write({"color": "#aB12fF", "icon": "calendar"})
        payload = {group["id"]: group for group in self._payload()}[self.group.id]
        self.assertEqual(payload["color"], "#aB12fF")
        self.assertEqual(payload["icon"], "calendar")
        for color in ("#fff", "red", "123456", "#1234567", " #123456", "#123456\n", "#GGGGGG", "#123456;display:none"):
            with self.subTest(color=color), self.assertRaises(ValidationError), self.cr.savepoint():
                self.group.color = color
        with self.assertRaises(ValueError), self.cr.savepoint():
            self.group.icon = "arbitrary-html"
        self.group.write({"color": False, "icon": False})
        payload = {group["id"]: group for group in self._payload()}[self.group.id]
        self.assertIs(payload["color"], False)
        self.assertIs(payload["icon"], False)

    def test_new_install_defaults_have_styles(self):
        everyday = self.env.ref("algorithma_navigation.group_everyday")
        system = self.env.ref("algorithma_navigation.group_system")
        self.assertEqual((everyday.color, everyday.icon), ("#2563EB", "home"))
        self.assertEqual((system.color, system.icon), ("#64748B", "settings"))

    def test_style_migration_preserves_existing_configuration(self):
        everyday = self.env.ref("algorithma_navigation.group_everyday")
        sales = self.env.ref("algorithma_navigation.group_sales")
        finance = self.env.ref("algorithma_navigation.group_finance")
        everyday.write({"name": "Eigene Navigation", "sequence": 777, "active": False, "color": False, "icon": False})
        sales.write({"color": "#abcdef", "icon": False})
        finance.write({"color": False, "icon": "heart"})
        self.line.group_id = everyday
        before_items = self.Item.search([]).read(["group_id", "menu_id", "sequence"])
        path = Path(__file__).resolve().parents[1] / "migrations" / "20.0.1.1.0" / "post-migrate.py"
        spec = importlib.util.spec_from_file_location("navigation_style_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, "20.0.1.0.0")
        self.assertEqual((everyday.color, everyday.icon), ("#2563EB", "home"))
        self.assertEqual((sales.color, sales.icon), ("#abcdef", "chart"))
        self.assertEqual((finance.color, finance.icon), ("#7C3AED", "heart"))
        self.assertEqual((everyday.name, everyday.sequence, everyday.active), ("Eigene Navigation", 777, False))
        self.assertEqual(self.Item.search([]).read(["group_id", "menu_id", "sequence"]), before_items)
        self.assertFalse(self.group.color)
        self.assertFalse(self.group.icon)
        self.assertEqual(self.Group._fill_default_group_styles(), 0)

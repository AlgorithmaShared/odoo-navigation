"""Tests for the personal sidebar arrangement of a user.

Covered here:
- a user without an own arrangement starts from the shared default,
- default groups without an app of the user stay unknown to that user,
- an own arrangement replaces the default for its owner only,
- saving twice keeps one row per user; resetting returns to the default,
- apps an administrator hid stay hidden; apps a user lost later are dropped,
- later changes of the default do not reach users with an own arrangement,
- which layer the editor opens for administrators and for ordinary users,
- malformed personal layouts are refused before anything is stored.
"""
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

# Name of the access-groups field on users and menus in this Odoo version.
GROUPS_FIELD = "group_ids"


@tagged("post_install", "-at_install")
class TestNavigationPersonal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Group = cls.env["algorithma.navigation.group"]
        cls.Item = cls.env["algorithma.navigation.item"]
        cls.Layout = cls.env["algorithma.navigation.user.layout"]
        internal_group = cls.env.ref("base.group_user")
        system_group = cls.env.ref("base.group_system")
        cls.restricted_role = cls.env["res.groups"].create({"name": "Navigation Personal Restricted"})

        # ----- users: one administrator, two ordinary employees, one portal user -----
        Users = cls.env["res.users"].with_context(no_reset_password=True)

        def create_user(name, login, groups):
            return Users.create({"name": name, "login": login, GROUPS_FIELD: [Command.set(groups.ids)]})

        cls.admin_user = create_user("Personal Admin", "navigation-personal-admin", internal_group | system_group)
        cls.alice = create_user("Personal Alice", "navigation-personal-alice", internal_group)
        cls.bob = create_user("Personal Bob", "navigation-personal-bob", internal_group)
        cls.portal_user = create_user("Personal Portal", "navigation-personal-portal", cls.env.ref("base.group_portal"))

        # ----- apps: three every employee may open, one restricted, one submenu -----
        contacts_action = cls.env["ir.actions.act_window"].create({
            "name": "Navigation Personal Contacts", "res_model": "res.partner", "view_mode": "list,form",
        })

        def create_app(name, sequence, groups):
            return cls.env["ir.ui.menu"].create({
                "name": name, "action": "ir.actions.act_window,%s" % contacts_action.id,
                GROUPS_FIELD: [Command.set(groups.ids)], "sequence": sequence,
            })

        cls.app_a = create_app("Personal App A", 960, internal_group)
        cls.app_b = create_app("Personal App B", 970, internal_group)
        cls.app_c = create_app("Personal App C", 980, internal_group)
        cls.restricted_app = create_app("Personal Restricted App", 990, cls.restricted_role)
        cls.submenu = cls.app_a.copy({"name": "Personal Submenu", "parent_id": cls.app_a.id})

        # ----- shared default: one group with two apps, one empty group, and one
        #       group that only holds an app ordinary employees may not open -----
        cls.default_group = cls.Group.create({"name": "Personal Default", "sequence": 930, "color": "#2563EB"})
        cls.default_empty_group = cls.Group.create({"name": "Personal Default Empty", "sequence": 940})
        cls.default_restricted_group = cls.Group.create({"name": "Personal Default Restricted", "sequence": 950})
        cls.item_a = cls.Item.create({"group_id": cls.default_group.id, "menu_id": cls.app_a.id, "sequence": 10})
        cls.item_b = cls.Item.create({"group_id": cls.default_group.id, "menu_id": cls.app_b.id, "sequence": 20})
        cls.Item.create({
            "group_id": cls.default_restricted_group.id, "menu_id": cls.restricted_app.id, "sequence": 10,
        })

    # ----- helpers -----

    def _as(self, user):
        return self.Group.with_user(user)

    def _sidebar(self, user):
        """Groups the user sees in the sidebar, by group number."""
        return {group["id"]: group for group in self._as(user).get_sidebar_groups()}

    def _personal_layout(self):
        """A valid personal layout: one styled group with two apps, one empty group."""
        return [
            {"id": 1, "name": "  Mine  ", "color": "#16A34A", "icon": "star",
             "menu_ids": [self.app_c.id, self.app_a.id]},
            {"id": 2, "name": "Later", "color": False, "icon": False, "menu_ids": []},
        ]

    # ----- starting point -----

    def test_user_without_own_arrangement_starts_from_the_default(self):
        editor_config = self._as(self.alice).get_sidebar_editor_config()
        self.assertEqual(editor_config["scope"], "personal")
        self.assertFalse(editor_config["has_personal_layout"])
        self.assertFalse(editor_config["can_edit_default"])
        # The names of the twelve group symbols travel with the editor data.
        self.assertEqual(len(editor_config["icon_labels"]), 12)
        self.assertEqual(editor_config["icon_labels"]["home"], "Home")
        groups = {group["id"]: group for group in editor_config["editor_groups"]}
        self.assertEqual(groups[self.default_group.id]["menu_ids"], [self.app_a.id, self.app_b.id])
        self.assertEqual(groups[self.default_group.id]["color"], "#2563EB")
        self.assertEqual(self._sidebar(self.alice)[self.default_group.id]["menu_ids"], [self.app_a.id, self.app_b.id])
        self.assertFalse(self.Layout.search([("user_id", "=", self.alice.id)]))

    def test_default_groups_without_an_own_app_stay_unknown_to_ordinary_users(self):
        unknown_groups = self.default_empty_group | self.default_restricted_group
        for scope in (None, "personal"):
            with self.subTest(user="alice", scope=scope):
                editor_config = self._as(self.alice).get_sidebar_editor_config(scope)
                editor_group_ids = [group["id"] for group in editor_config["editor_groups"]]
                self.assertIn(self.default_group.id, editor_group_ids)
                self.assertFalse(set(editor_group_ids) & set(unknown_groups.ids))
                # Not even the names travel to the browser.
                for unknown_group in unknown_groups:
                    self.assertNotIn(unknown_group.name, str(editor_config))
                # The editor starts from exactly the groups of the user's sidebar.
                self.assertEqual(editor_group_ids, [group["id"] for group in editor_config["config"]["groups"]])
        # Administrators arrange the default: they get every group, in both layers.
        for scope in ("default", "personal"):
            with self.subTest(user="admin", scope=scope):
                editor_config = self._as(self.admin_user).get_sidebar_editor_config(scope)
                editor_group_ids = {group["id"] for group in editor_config["editor_groups"]}
                self.assertTrue(set(unknown_groups.ids) <= editor_group_ids)

    # ----- own arrangement -----

    def test_own_arrangement_replaces_the_default_for_its_owner_only(self):
        default_before = self._sidebar(self.bob)
        editor_config = self._as(self.alice).save_personal_sidebar_layout(self._personal_layout())
        self.assertEqual(editor_config["scope"], "personal")
        self.assertTrue(editor_config["has_personal_layout"])
        self.assertEqual(editor_config["editor_groups"], [
            {"id": 1, "name": "Mine", "menu_ids": [self.app_c.id, self.app_a.id], "color": "#16A34A", "icon": "star"},
            {"id": 2, "name": "Later", "menu_ids": [], "color": False, "icon": False},
        ])
        # The sidebar leaves out the empty group and no longer shows the default groups.
        self.assertEqual(self._as(self.alice).get_sidebar_groups(), [
            {"id": 1, "name": "Mine", "menu_ids": [self.app_c.id, self.app_a.id], "color": "#16A34A", "icon": "star"},
        ])
        self.assertEqual(editor_config["config"], self._as(self.alice).get_sidebar_config())
        # Nobody else is affected, and the shared default is untouched.
        self.assertEqual(self._sidebar(self.bob), default_before)
        self.assertEqual((self.item_a.group_id, self.item_b.group_id), (self.default_group, self.default_group))
        own_rows = self.Layout.search([("user_id", "in", (self.alice | self.bob | self.admin_user).ids)])
        self.assertEqual(own_rows.user_id, self.alice)

    def test_saving_again_keeps_one_row_and_reset_returns_to_the_default(self):
        self._as(self.alice).save_personal_sidebar_layout(self._personal_layout())
        self._as(self.alice).save_personal_sidebar_layout([
            {"id": 7, "name": "Only", "color": False, "icon": "heart", "menu_ids": [self.app_b.id]},
        ])
        self.assertEqual(self.Layout.search_count([("user_id", "=", self.alice.id)]), 1)
        self.assertEqual(list(self._sidebar(self.alice)), [7])
        editor_config = self._as(self.alice).reset_personal_sidebar_layout()
        self.assertFalse(editor_config["has_personal_layout"])
        self.assertEqual(editor_config["scope"], "personal")
        self.assertFalse(self.Layout.search([("user_id", "=", self.alice.id)]))
        self.assertIn(self.default_group.id, self._sidebar(self.alice))
        # Resetting without an own arrangement is harmless.
        self.assertFalse(self._as(self.alice).reset_personal_sidebar_layout()["has_personal_layout"])

    def test_hidden_and_lost_apps_stay_out_of_an_own_arrangement(self):
        self._as(self.alice).save_personal_sidebar_layout(self._personal_layout())
        # An administrator hides app A for everyone: it stays hidden, own arrangement or not.
        self.item_a.hidden = True
        self.assertIn(self.app_a.id, self._as(self.alice).get_sidebar_config()["hidden_menu_ids"])
        # Alice loses access to app C: it disappears from her groups without touching the stored layout.
        self.app_c.write({GROUPS_FIELD: [Command.set(self.restricted_role.ids)]})
        self.assertEqual(self._sidebar(self.alice)[1]["menu_ids"], [self.app_a.id])
        editor_groups = self._as(self.alice).get_sidebar_editor_config()["editor_groups"]
        self.assertEqual([group["menu_ids"] for group in editor_groups], [[self.app_a.id], []])

    def test_default_changes_do_not_reach_users_with_an_own_arrangement(self):
        self._as(self.alice).save_personal_sidebar_layout(self._personal_layout())
        own_before = self._as(self.alice).get_sidebar_groups()
        self._as(self.admin_user).save_sidebar_layout(
            [{"id": self.default_group.id, "menu_ids": [self.app_c.id]}], [self.app_a.id, self.app_b.id],
        )
        self.assertEqual(self._as(self.alice).get_sidebar_groups(), own_before)
        self.assertEqual(self._sidebar(self.bob)[self.default_group.id]["menu_ids"], [self.app_c.id])

    # ----- which layer the editor opens -----

    def test_editor_layer_for_administrators_and_ordinary_users(self):
        admin = self._as(self.admin_user)
        # Without an own arrangement an administrator keeps editing the default.
        editor_config = admin.get_sidebar_editor_config()
        self.assertEqual((editor_config["scope"], editor_config["can_edit_default"]), ("default", True))
        # On request the administrator edits an own arrangement, starting from the default.
        editor_config = admin.get_sidebar_editor_config("personal")
        self.assertEqual((editor_config["scope"], editor_config["has_personal_layout"]), ("personal", False))
        self.assertIn(self.default_group.id, [group["id"] for group in editor_config["editor_groups"]])
        # With an own arrangement the editor opens on it; the default stays reachable.
        admin.save_personal_sidebar_layout(self._personal_layout())
        self.assertEqual(admin.get_sidebar_editor_config()["scope"], "personal")
        editor_config = admin.get_sidebar_editor_config("default")
        self.assertEqual(editor_config["scope"], "default")
        self.assertIn(self.default_group.id, [group["id"] for group in editor_config["editor_groups"]])
        # Ordinary users never reach the default layer, and unknown layers are refused.
        with self.assertRaises(AccessError):
            self._as(self.alice).get_sidebar_editor_config("default")
        with self.assertRaises(ValidationError):
            self._as(self.alice).get_sidebar_editor_config("everyone")

    def test_portal_and_public_users_have_no_own_arrangement(self):
        for user in (self.portal_user, self.env.ref("base.public_user")):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self._as(user).get_sidebar_editor_config("personal")
                with self.assertRaises(AccessError):
                    self._as(user).save_personal_sidebar_layout([])
                with self.assertRaises(AccessError):
                    self._as(user).reset_personal_sidebar_layout()
        self.assertFalse(self.Layout.search([("user_id", "in", (self.portal_user | self.env.ref("base.public_user")).ids)]))

    # ----- validation -----

    def test_malformed_personal_layouts_are_refused_before_anything_is_stored(self):
        app_a, app_b = self.app_a.id, self.app_b.id

        def group(**changes):
            return dict({"id": 1, "name": "Mine", "color": False, "icon": False, "menu_ids": [app_a]}, **changes)

        malformed_layouts = [
            "groups",                                               # not a list
            ["group"],                                              # entry is not an object
            [group(id="1")],                                        # group number is text
            [group(id=True)],                                       # group number is a boolean
            [group(id=0)],                                          # group number is not positive
            [group(), group(menu_ids=[app_b])],                     # group number used twice
            [group(name="   ")],                                    # empty name
            [group(name=5)],                                        # name is not text
            [group(name="x" * 101)],                                # name too long
            [group(menu_ids="apps")],                               # apps are not a list
            [group(menu_ids=[str(app_a)])],                         # app id is text
            [group(menu_ids=[app_a, app_a])],                       # app listed twice
            [group(), group(id=2, menu_ids=[app_a])],               # app in two groups
            [group(menu_ids=[self.restricted_app.id])],             # app the user may not open
            [group(menu_ids=[self.submenu.id])],                    # submenu instead of app
            [group(menu_ids=[2147483000])],                         # app does not exist
            [group(color="red")],                                   # colour is not #RRGGBB
            [group(color="#16A34A;display:none")],                  # colour with trailing CSS
            [group(icon="<svg>")],                                  # unknown symbol
            [group(id=number) for number in range(1, 102)],         # too many groups
        ]
        for layout in malformed_layouts:
            with self.subTest(layout=str(layout)[:80]), self.assertRaises(ValidationError):
                self._as(self.alice).save_personal_sidebar_layout(layout)
        self.assertFalse(self.Layout.search([("user_id", "=", self.alice.id)]))
        self.assertIn(self.default_group.id, self._sidebar(self.alice))

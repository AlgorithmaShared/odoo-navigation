"""Tests for the sidebar editor API, shared default (arranging by drag and drop).

The personal arrangement of a user is covered in test_navigation_personal.py.

Covered here:
- only settings administrators may read or store the shared default,
- the editor data lists empty groups and leaves out archived ones,
- a stored layout sets the order of groups and of apps inside each group,
- dragging an app out of every group keeps its "hidden" choice,
- assignments the browser did not mention stay exactly as they were,
- malformed layouts are refused before anything is written.
"""
from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNavigationEditor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Group = cls.env["algorithma.navigation.group"]
        cls.Item = cls.env["algorithma.navigation.item"]
        internal_group = cls.env.ref("base.group_user")
        system_group = cls.env.ref("base.group_system")

        # ----- users: one administrator, one ordinary employee, one portal user -----
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.admin_user = Users.create({
            "name": "Navigation Editor Admin", "login": "navigation-editor-admin",
            "groups_id": [Command.set([internal_group.id, system_group.id])],
        })
        cls.internal_user = Users.create({
            "name": "Navigation Editor Reader", "login": "navigation-editor-reader",
            "groups_id": [Command.set([internal_group.id])],
        })
        cls.portal_user = Users.create({
            "name": "Navigation Editor Portal", "login": "navigation-editor-portal",
            "groups_id": [Command.set([cls.env.ref("base.group_portal").id])],
        })

        # ----- three apps (root menus) every employee may open, plus one submenu -----
        contacts_action = cls.env["ir.actions.act_window"].create({
            "name": "Navigation Editor Contacts", "res_model": "res.partner", "view_mode": "list,form",
        })

        def create_app(name, sequence):
            return cls.env["ir.ui.menu"].create({
                "name": name, "action": "ir.actions.act_window,%s" % contacts_action.id,
                "groups_id": [Command.set([internal_group.id])], "sequence": sequence,
            })

        cls.app_a = create_app("Editor App A", 930)
        cls.app_b = create_app("Editor App B", 940)
        cls.app_c = create_app("Editor App C", 950)
        cls.submenu = cls.app_a.copy({"name": "Editor Submenu", "parent_id": cls.app_a.id})

        # ----- groups: one with two apps, one without assignments, one never used -----
        cls.group_one = cls.Group.create({"name": "Editor One", "sequence": 900})
        cls.group_two = cls.Group.create({"name": "Editor Two", "sequence": 910})
        cls.empty_group = cls.Group.create({"name": "Editor Empty", "sequence": 920})
        cls.item_a = cls.Item.create({"group_id": cls.group_one.id, "menu_id": cls.app_a.id, "sequence": 10})
        cls.item_b = cls.Item.create({"group_id": cls.group_one.id, "menu_id": cls.app_b.id, "sequence": 20})

    # ----- helpers -----

    def _as_admin(self):
        return self.Group.with_user(self.admin_user)

    def _editor_groups(self, **context):
        editor_config = self._as_admin().with_context(**context).get_sidebar_editor_config()
        return {group["id"]: group for group in editor_config["editor_groups"]}

    # ----- reading the editor data -----

    def test_editor_data_lists_empty_groups_and_skips_archived_ones(self):
        groups = self._editor_groups()
        self.assertEqual(groups[self.group_one.id]["menu_ids"], [self.app_a.id, self.app_b.id])
        self.assertEqual(groups[self.empty_group.id]["menu_ids"], [])
        self.assertEqual(set(groups[self.empty_group.id]), {"id", "name", "menu_ids", "color", "icon"})
        editor_config = self._as_admin().get_sidebar_editor_config()
        self.assertEqual(editor_config["config"], self._as_admin().get_sidebar_config())
        self.empty_group.active = False
        self.assertNotIn(self.empty_group.id, self._editor_groups())
        self.assertNotIn(self.empty_group.id, self._editor_groups(active_test=False))

    def test_only_administrators_may_edit_the_shared_default(self):
        layout = [{"id": self.group_two.id, "menu_ids": [self.app_a.id, self.app_b.id]}]
        for user in (self.internal_user, self.portal_user, self.env.ref("base.public_user")):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.Group.with_user(user).get_sidebar_editor_config("default")
                with self.assertRaises(AccessError):
                    self.Group.with_user(user).save_sidebar_layout(layout, [])
        # Portal and public users get no editor at all, not even for themselves.
        for user in (self.portal_user, self.env.ref("base.public_user")):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                self.Group.with_user(user).get_sidebar_editor_config()
        self.assertEqual(self.item_a.group_id, self.group_one)
        self.assertEqual(self.item_b.group_id, self.group_one)

    # ----- storing a layout -----

    def test_layout_sets_group_order_and_app_order(self):
        editor_config = self._as_admin().save_sidebar_layout([
            {"id": self.group_two.id, "menu_ids": [self.app_b.id, self.app_c.id]},
            {"id": self.empty_group.id, "menu_ids": []},
            {"id": self.group_one.id, "menu_ids": [self.app_a.id]},
        ], [])
        own_group_ids = (self.group_one.id, self.group_two.id, self.empty_group.id)
        stored_order = [group["id"] for group in editor_config["editor_groups"] if group["id"] in own_group_ids]
        self.assertEqual(stored_order, [self.group_two.id, self.empty_group.id, self.group_one.id])
        groups = {group["id"]: group for group in editor_config["editor_groups"]}
        self.assertEqual(groups[self.group_two.id]["menu_ids"], [self.app_b.id, self.app_c.id])
        self.assertEqual(groups[self.group_one.id]["menu_ids"], [self.app_a.id])
        # App B was moved by updating its existing row; app C got a new one.
        self.assertEqual(self.item_b.group_id, self.group_two)
        self.assertEqual(self.Item.search_count([("menu_id", "=", self.app_c.id)]), 1)
        # Ordinary users see the new arrangement; the empty group stays invisible to them.
        sidebar = {
            group["id"]: group["menu_ids"]
            for group in self.Group.with_user(self.internal_user).get_sidebar_groups()
        }
        self.assertEqual(sidebar[self.group_two.id], [self.app_b.id, self.app_c.id])
        self.assertEqual(sidebar[self.group_one.id], [self.app_a.id])
        self.assertNotIn(self.empty_group.id, sidebar)

    def test_ungrouping_keeps_the_hidden_choice(self):
        self.item_a.hidden = True
        self._as_admin().save_sidebar_layout(
            [{"id": self.group_one.id, "menu_ids": [self.app_b.id]}], [self.app_a.id],
        )
        self.assertTrue(self.item_a.exists())
        self.assertFalse(self.item_a.group_id)
        self.assertTrue(self.item_a.hidden)
        # An app that never had an assignment needs none to stay ungrouped.
        self._as_admin().save_sidebar_layout(
            [{"id": self.group_one.id, "menu_ids": [self.app_b.id]}], [self.app_c.id],
        )
        self.assertFalse(self.Item.search([("menu_id", "=", self.app_c.id)]))

    def test_unmentioned_assignments_stay_untouched(self):
        item_c = self.Item.create({
            "group_id": self.group_two.id, "menu_id": self.app_c.id, "sequence": 70, "hidden": True,
        })
        self._as_admin().save_sidebar_layout(
            [{"id": self.group_one.id, "menu_ids": [self.app_b.id, self.app_a.id]}], [],
        )
        self.assertEqual((item_c.group_id, item_c.sequence, item_c.hidden), (self.group_two, 70, True))
        self.assertEqual(self.group_two.sequence, 910)
        self.assertEqual((self.item_b.sequence, self.item_a.sequence), (10, 20))

    def test_malformed_layouts_are_refused_before_any_change(self):
        one, app_a, app_b = self.group_one.id, self.app_a.id, self.app_b.id
        unknown_id = 2147483000
        malformed_layouts = [
            ("groups", []),                                                   # groups is not a list
            ([{"id": one}], []),                                              # menu_ids missing
            ([{"id": str(one), "menu_ids": [app_a]}], []),                    # group id is text
            ([{"id": True, "menu_ids": [app_a]}], []),                        # group id is a boolean
            ([{"id": one, "menu_ids": [0]}], []),                             # app id is not positive
            ([{"id": one, "menu_ids": [app_a, app_a]}], []),                  # app listed twice
            ([{"id": one, "menu_ids": [app_a]}, {"id": one, "menu_ids": [app_b]}], []),  # group listed twice
            ([{"id": one, "menu_ids": [app_a]}], [app_a]),                    # grouped and ungrouped at once
            ([{"id": one, "menu_ids": [app_a]}], "ungrouped"),                # ungrouped is not a list
            ([{"id": unknown_id, "menu_ids": [app_a]}], []),                  # group does not exist
            ([{"id": one, "menu_ids": [unknown_id]}], []),                    # app does not exist
            ([{"id": one, "menu_ids": [self.submenu.id]}], []),               # submenu instead of app
        ]
        for groups, ungrouped_menu_ids in malformed_layouts:
            with self.subTest(groups=groups, ungrouped_menu_ids=ungrouped_menu_ids):
                with self.assertRaises(ValidationError):
                    self._as_admin().save_sidebar_layout(groups, ungrouped_menu_ids)
        self.assertEqual((self.item_a.group_id, self.item_a.sequence), (self.group_one, 10))
        self.assertEqual((self.item_b.group_id, self.item_b.sequence), (self.group_one, 20))
        self.assertEqual(self.group_one.sequence, 900)

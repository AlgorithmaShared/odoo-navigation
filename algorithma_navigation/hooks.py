"""Install-time defaults only: preserve every subsequent admin choice."""


DEFAULT_GROUP_APPS = (
    ("group_everyday", (
        "mail.menu_root_discuss", "calendar.mail_menu_calendar",
        "contacts.menu_contacts", "project_todo.menu_todo_todos",
    )),
    ("group_sales", (
        "crm.crm_menu_root", "sale.sale_menu_root", "website.main_menu",
        "utm.menu_link_tracker_root",
    )),
    ("group_operations", (
        "project.menu_main_pm", "fieldservice.root", "hr_timesheet.timesheet_menu_root",
        "stock.menu_stock_root", "purchase.menu_purchase_root", "mrp.menu_mrp_root",
    )),
    ("group_finance", ("account.menu_finance", "hr_expense.menu_hr_expense_root")),
    ("group_people", ("hr.menu_hr_root", "hr_holidays.menu_hr_holidays_root", "fleet.menu_root")),
    ("group_system", ("base.menu_management", "base.menu_administration")),
)


def post_init_hook(env):
    """Assign installed root apps once, skipping missing or assigned menus."""
    items = env["algorithma.navigation.item"].sudo()
    assigned = set(items.search([]).mapped("menu_id").ids)
    for group_xmlid, menu_xmlids in DEFAULT_GROUP_APPS:
        group = env.ref("algorithma_navigation." + group_xmlid, raise_if_not_found=False)
        if not group:
            continue
        for position, menu_xmlid in enumerate(menu_xmlids, start=1):
            menu = env.ref(menu_xmlid, raise_if_not_found=False)
            if not menu or menu._name != "ir.ui.menu" or menu.parent_id or menu.id in assigned:
                continue
            items.create({"group_id": group.id, "menu_id": menu.id, "sequence": position * 10})
            assigned.add(menu.id)

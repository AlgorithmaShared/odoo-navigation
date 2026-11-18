from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if version:
        env = api.Environment(cr, SUPERUSER_ID, {})
        env["algorithma.navigation.group"]._fill_default_group_styles()

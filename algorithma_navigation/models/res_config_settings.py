from odoo import fields, models, _
from odoo.exceptions import AccessError

from .navigation_group import GROUPING_ENABLED_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    algorithma_navigation_grouping_enabled = fields.Boolean(
        string="Group apps", default=True,
        config_parameter=GROUPING_ENABLED_PARAM, groups="base.group_system",
        help="Applies to all users of this database. Without grouping the "
             "visible apps are shown directly. Existing groups and "
             "hidden apps stay stored.",
    )

    def set_values(self):
        if not self.env.is_admin():
            raise AccessError(_("Only administrators can configure the navigation."))
        self.ensure_one()
        super().set_values()
        # Odoo 20's native typed Boolean parameter API persists False itself.

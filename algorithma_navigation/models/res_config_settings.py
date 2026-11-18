from odoo import fields, models, _
from odoo.exceptions import AccessError

from .navigation_group import GROUPING_ENABLED_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    algorithma_navigation_grouping_enabled = fields.Boolean(
        string="Apps gruppieren", default=True,
        config_parameter=GROUPING_ENABLED_PARAM, groups="base.group_system",
        help="Gilt für alle Benutzer dieser Datenbank. Ohne Gruppierung werden "
             "die sichtbaren Apps direkt angezeigt. Vorhandene Gruppen und "
             "ausgeblendete Apps bleiben gespeichert.",
    )

    def set_values(self):
        if not self.env.is_admin():
            raise AccessError(_("Nur Administratoren können die Navigation konfigurieren."))
        self.ensure_one()
        super().set_values()
        # Odoo 20's native typed Boolean parameter API persists False itself.

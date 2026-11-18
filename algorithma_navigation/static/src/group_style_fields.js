/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { GROUP_ICON_KEYS, groupStyle, sanitizeGroupColor, sanitizeGroupIcon } from "./group_apps";

export class GroupColorField extends Component {
    static template = "algorithma_navigation.GroupColorField";
    static props = { ...standardFieldProps };

    get value() {
        return sanitizeGroupColor(this.props.record.data[this.props.name]);
    }

    get presets() {
        return ["#2563EB", "#7C3AED", "#0D9488", "#16A34A", "#D97706", "#DC2626", "#DB2777", "#64748B"];
    }

    get previewStyle() {
        return groupStyle(this.value);
    }

    get previewIcon() {
        return sanitizeGroupIcon(this.props.record.data.icon);
    }

    get previewName() {
        return this.props.record.data.name || _t("Vorschau");
    }

    setColor(value) {
        if (!this.props.readonly) {
            return this.props.record.update({ [this.props.name]: sanitizeGroupColor(value) });
        }
    }

    onColorChange(event) {
        return this.setColor(event.target.value);
    }
}

export class GroupIconField extends Component {
    static template = "algorithma_navigation.GroupIconField";
    static props = { ...standardFieldProps };

    get value() {
        return sanitizeGroupIcon(this.props.record.data[this.props.name]);
    }

    get options() {
        const labels = new Map(this.props.record.fields[this.props.name].selection);
        return GROUP_ICON_KEYS.map((key) => ({ key, label: labels.get(key) || key }));
    }

    get currentLabel() {
        return this.options.find((option) => option.key === this.value)?.label || _t("Kein Symbol");
    }

    setIcon(value) {
        if (!this.props.readonly) {
            return this.props.record.update({ [this.props.name]: sanitizeGroupIcon(value) });
        }
    }
}

registry.category("fields").add("algorithma_group_color", {
    component: GroupColorField,
    displayName: _t("Gruppenfarbe"),
    supportedTypes: ["char"],
});

registry.category("fields").add("algorithma_group_icon", {
    component: GroupIconField,
    displayName: _t("Gruppensymbol"),
    supportedTypes: ["selection"],
});

"""Projects 7.19 — ProjectCustomField forms."""
import json

from django import forms

from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import (
    ProjectCustomField,
    _validate_custom_field_json,
)


class ProjectCustomFieldForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for defining custom fields and validation rules."""

    choices_list_raw = forms.CharField(
        label="Dropdown Choices (one per line or JSON array)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea", "placeholder": "Option A\nOption B\nOption C"}),
        required=False,
        strip=False,
        help_text="Required when Field Type is 'Single Select Dropdown' or 'Multi-Select Choices'.",
    )
    visibility_rule_raw = forms.CharField(
        label="Conditional Visibility Rule (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-sm", "placeholder": '{"depends_on": "methodology", "operator": "equals", "value": "agile"}'}),
        required=False,
        strip=False,
        help_text="Optional rule dict controlling when this field is shown in the form canvas.",
    )

    class Meta:
        model = ProjectCustomField
        fields = [
            "name",
            "field_key",
            "label",
            "target_entity",
            "field_type",
            "form_section",
            "description",
            "placeholder",
            "default_value",
            "is_required",
            "min_value",
            "max_value",
            "regex_pattern",
            "display_order",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Client Compliance Tier"}),
            "field_key": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. client_compliance_tier"}),
            "label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Compliance Tier (ISO/SOC2)"}),
            "target_entity": forms.Select(attrs={"class": "form-select"}),
            "field_type": forms.Select(attrs={"class": "form-select"}),
            "form_section": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "placeholder": forms.TextInput(attrs={"class": "form-input"}),
            "default_value": forms.TextInput(attrs={"class": "form-input"}),
            "min_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "max_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "regex_pattern": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": r"^SOC2-[A-Z0-9]+$"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.choices_list:
                if isinstance(self.instance.choices_list, list):
                    self.initial["choices_list_raw"] = "\n".join(str(c) for c in self.instance.choices_list)
                else:
                    self.initial["choices_list_raw"] = json.dumps(self.instance.choices_list, indent=2)
            if self.instance.visibility_rule:
                self.initial["visibility_rule_raw"] = json.dumps(self.instance.visibility_rule, indent=2)

    def clean_choices_list_raw(self):
        raw = self.cleaned_data.get("choices_list_raw", "")
        if len(raw.encode("utf-8")) > 16384:
            raise forms.ValidationError("Choices JSON exceeds the 16,384-byte limit.")
        val = raw.strip()
        if not val:
            return []
        if val.startswith("["):
            try:
                parsed = json.loads(val)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise forms.ValidationError(f"Invalid JSON: {exc}")
            if not isinstance(parsed, list):
                raise forms.ValidationError("Choices JSON must be an array of option strings.")
            return parsed
        return [line.strip() for line in val.splitlines() if line.strip()]

    def clean_visibility_rule_raw(self):
        raw = self.cleaned_data.get("visibility_rule_raw", "")
        if len(raw.encode("utf-8")) > 16384:
            raise forms.ValidationError("Visibility rule exceeds the 16,384-byte limit.")
        val = raw.strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")
        if not isinstance(parsed, dict):
            raise forms.ValidationError("Visibility rule must be a JSON object/dict.")
        return parsed

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get("field_type")
        choices = cleaned_data.get("choices_list_raw") or []
        if any(not isinstance(value, str) or not value.strip() for value in choices):
            self.add_error("choices_list_raw", "Every choice must be a non-empty string.")
        elif len({value.strip() for value in choices}) != len(choices):
            self.add_error("choices_list_raw", "Choices must be unique.")
        if field_type in ("select", "multiselect") and not choices:
            self.add_error("choices_list_raw", "Dropdown or Multi-Select fields must specify at least one choice option.")
        min_value = cleaned_data.get("min_value")
        max_value = cleaned_data.get("max_value")
        if min_value is not None and max_value is not None and min_value > max_value:
            self.add_error("max_value", "Maximum value cannot be lower than the minimum value.")
        choices_valid = (
            isinstance(choices, list)
            and all(isinstance(value, str) and bool(value.strip()) for value in choices)
            and len({value.strip() for value in choices}) == len(choices)
        )
        visibility_rule = cleaned_data.get("visibility_rule_raw")
        visibility_valid = isinstance(visibility_rule, dict)
        if choices_valid:
            try:
                _validate_custom_field_json(choices, "Choices")
            except forms.ValidationError as exc:
                choices_valid = False
                self.add_error("choices_list_raw", exc.messages[0])
        if visibility_valid:
            try:
                _validate_custom_field_json(visibility_rule, "Visibility rule")
            except forms.ValidationError as exc:
                visibility_valid = False
                self.add_error("visibility_rule_raw", exc.messages[0])
        self.instance.choices_list = choices if choices_valid else (
            ["invalid-choice"] if field_type in ("select", "multiselect") else []
        )
        self.instance.visibility_rule = visibility_rule if visibility_valid else {}
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.choices_list = self.cleaned_data.get("choices_list_raw", [])
        instance.visibility_rule = self.cleaned_data.get("visibility_rule_raw", {})
        if commit:
            instance.save()
        return instance

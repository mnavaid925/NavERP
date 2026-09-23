"""Projects 7.19 — ProjectCustomField forms."""
import json
from decimal import Decimal

from django import forms

from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models.MasterDataConfiguration.ProjectCustomFields import ProjectCustomField


class ProjectCustomFieldForm(TenantUniqueMixin, TenantModelForm):
    """Admin/PM form for defining custom fields and validation rules."""

    choices_list_raw = forms.CharField(
        label="Dropdown Choices (one per line or JSON array)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea", "placeholder": "Option A\nOption B\nOption C"}),
        required=False,
        help_text="Required when Field Type is 'Single Select Dropdown' or 'Multi-Select Choices'.",
    )
    visibility_rule_raw = forms.CharField(
        label="Conditional Visibility Rule (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-sm", "placeholder": '{"depends_on": "methodology", "operator": "equals", "value": "agile"}'}),
        required=False,
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
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
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
        val = self.cleaned_data.get("choices_list_raw", "").strip()
        if not val:
            return []
        if val.startswith("["):
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, list):
                    raise forms.ValidationError("Choices JSON must be an array of option strings.")
                return parsed
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON: {exc}")
        return [line.strip() for line in val.splitlines() if line.strip()]

    def clean_visibility_rule_raw(self):
        val = self.cleaned_data.get("visibility_rule_raw", "").strip()
        if not val:
            return {}
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Visibility rule must be a JSON object/dict.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned_data = super().clean()
        field_type = cleaned_data.get("field_type")
        choices = cleaned_data.get("choices_list_raw") or []
        if field_type in ("select", "multiselect") and not choices:
            self.add_error("choices_list_raw", "Dropdown or Multi-Select fields must specify at least one choice option.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.choices_list = self.cleaned_data.get("choices_list_raw", [])
        instance.visibility_rule = self.cleaned_data.get("visibility_rule_raw", {})
        if commit:
            instance.save()
        return instance

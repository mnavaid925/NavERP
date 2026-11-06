import json
from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportParameters import ReportParameter
from apps.core.forms import TenantModelForm


class ReportParameterForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReportParameter
        fields = [
            "report",
            "parameter_name",
            "prompt_label",
            "parameter_type",
            "default_value",
            "choices_source",
            "choices_config_json",
            "validation_regex",
            "help_text",
            "prompt_order",
            "is_required",
            "is_hidden",
            "is_active",
        ]
        widgets = {
            "report": forms.Select(attrs={"class": "form-select"}),
            "parameter_name": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. start_date, department_id"}),
            "prompt_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Fiscal Period Start Date"}),
            "parameter_type": forms.Select(attrs={"class": "form-select"}),
            "default_value": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. current_year, active, today"}),
            "choices_source": forms.Select(attrs={"class": "form-select"}),
            "choices_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": '[{"value": "posted", "label": "Posted Only"}, {"value": "all", "label": "All Entries"}]'}),
            "validation_regex": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}),
            "help_text": forms.TextInput(attrs={"class": "form-input", "placeholder": "Guidance displayed below prompt input in viewer"}),
            "prompt_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_hidden": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "parameter_name" in self.fields:
            self.fields["parameter_name"].required = False
        if "choices_config_json" in self.fields:
            self.fields["choices_config_json"].required = False

        if self.tenant is not None:
            self.fields["report"].queryset = ReportDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean_choices_config_json(self):
        val = self.cleaned_data.get("choices_config_json")
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return val or []

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["report"])
        prompt_label = cleaned_data.get("prompt_label")
        parameter_name = cleaned_data.get("parameter_name")
        if not parameter_name and prompt_label:
            cleaned_data["parameter_name"] = slugify(prompt_label).replace("-", "_")[:60]
        return cleaned_data

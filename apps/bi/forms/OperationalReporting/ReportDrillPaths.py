import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportDrillPaths import ReportDrillPath
from apps.core.forms import TenantModelForm


class ReportDrillPathForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReportDrillPath
        fields = [
            "source_report",
            "source_field",
            "drill_label",
            "target_type",
            "target_report",
            "target_url_pattern",
            "parameter_mapping_json",
            "sort_order",
            "is_enabled",
        ]
        widgets = {
            "source_report": forms.Select(attrs={"class": "form-select"}),
            "source_field": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. customer_code, account_id"}),
            "drill_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. View Customer Invoices"}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "target_report": forms.Select(attrs={"class": "form-select"}),
            "target_url_pattern": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. /crm/accounts/{customer_id}/"}),
            "parameter_mapping_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '{"customer_code": "target_customer_id"}'}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "parameter_mapping_json" in self.fields:
            self.fields["parameter_mapping_json"].required = False
        if "target_url_pattern" in self.fields:
            self.fields["target_url_pattern"].required = False

        if self.tenant is not None:
            report_qs = ReportDefinition.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["source_report"].queryset = report_qs
            self.fields["target_report"].queryset = report_qs
            self.fields["target_report"].empty_label = "— None (Direct ERP URL / External) —"

    def clean_parameter_mapping_json(self):
        val = self.cleaned_data.get("parameter_mapping_json")
        if isinstance(val, str) and val.strip():
            try:
                return json.loads(val)
            except Exception as e:
                raise forms.ValidationError(f"Invalid JSON: {e}")
        return val or {}

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["source_report", "target_report"])
        return cleaned_data

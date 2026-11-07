import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfig
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class EmbeddedAnalyticsConfigForm(TenantUniqueMixin, TenantModelForm):
    default_rls_attributes_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
        label="Default RLS Attributes (JSON)",
        help_text='JSON dictionary of attribute constraints, e.g. {"region": "North America", "tier": "Enterprise"}',
    )

    class Meta:
        model = EmbeddedAnalyticsConfig
        fields = [
            "name",
            "slug",
            "description",
            "target_type",
            "dashboard",
            "report",
            "semantic_model",
            "embedding_mode",
            "auth_mode",
            "status",
            "allowed_origins",
            "theme_mode",
            "primary_color",
            "accent_color",
            "custom_css",
            "enable_rls_filter",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "embedding_mode": forms.Select(attrs={"class": "form-select"}),
            "auth_mode": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "allowed_origins": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "theme_mode": forms.Select(attrs={"class": "form-select"}),
            "primary_color": forms.TextInput(attrs={"type": "color", "class": "form-input h-10 w-20 p-1"}),
            "accent_color": forms.TextInput(attrs={"type": "color", "class": "form-input h-10 w-20 p-1"}),
            "custom_css": forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
            "enable_rls_filter": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["report"].queryset = ReportDefinition.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")

        if self.instance and self.instance.pk:
            if self.instance.default_rls_attributes:
                self.fields["default_rls_attributes_raw"].initial = json.dumps(
                    self.instance.default_rls_attributes, indent=2
                )
            else:
                self.fields["default_rls_attributes_raw"].initial = "{}"
        else:
            self.fields["default_rls_attributes_raw"].initial = "{}"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["dashboard", "report", "semantic_model"])

        raw_rls = cleaned_data.get("default_rls_attributes_raw", "").strip()
        if raw_rls:
            try:
                parsed = json.loads(raw_rls)
                if not isinstance(parsed, dict):
                    self.add_error("default_rls_attributes_raw", "RLS attributes must be a JSON object (dictionary).")
                else:
                    self.instance.default_rls_attributes = parsed
            except json.JSONDecodeError as exc:
                self.add_error("default_rls_attributes_raw", f"Invalid JSON syntax: {exc}")
        else:
            self.instance.default_rls_attributes = {}

        target_type = cleaned_data.get("target_type")
        dashboard = cleaned_data.get("dashboard")
        report = cleaned_data.get("report")
        semantic_model = cleaned_data.get("semantic_model")

        if target_type == "dashboard" and not dashboard:
            self.add_error("dashboard", "Please select a Dashboard for Dashboard target type.")
        elif target_type == "report" and not report:
            self.add_error("report", "Please select an Operational Report for Report target type.")
        elif target_type == "semantic_model" and not semantic_model:
            self.add_error("semantic_model", "Please select a Semantic Model for Semantic Model target type.")

        return cleaned_data

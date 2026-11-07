import json

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.EmbeddedMobileBi.MobileBiConfigurations import MobileBiConfiguration
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.core.forms import TenantModelForm

User = get_user_model()


class MobileBiConfigurationForm(TenantUniqueMixin, TenantModelForm):
    pinned_dashboard_ids_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        label="Pinned Dashboard IDs (JSON Array)",
        help_text="JSON list of BiDashboard IDs pre-fetched for offline access, e.g. [1, 2, 5]",
    )
    pinned_report_ids_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        label="Pinned Report IDs (JSON Array)",
        help_text="JSON list of ReportDefinition IDs pre-fetched for offline access, e.g. [3, 8]",
    )

    class Meta:
        model = MobileBiConfiguration
        fields = [
            "name",
            "target_user",
            "is_default_profile",
            "status",
            "offline_caching_enabled",
            "cache_max_age_hours",
            "max_cache_storage_mb",
            "sync_on_wifi_only",
            "touch_layout_preset",
            "enable_push_insights",
            "push_digest_frequency",
            "require_biometric_lock",
            "inactivity_lock_minutes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "target_user": forms.Select(attrs={"class": "form-select"}),
            "is_default_profile": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "offline_caching_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "cache_max_age_hours": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "max_cache_storage_mb": forms.NumberInput(attrs={"class": "form-input", "min": 10}),
            "sync_on_wifi_only": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "touch_layout_preset": forms.Select(attrs={"class": "form-select"}),
            "enable_push_insights": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "push_digest_frequency": forms.Select(attrs={"class": "form-select"}),
            "require_biometric_lock": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "inactivity_lock_minutes": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_user"].queryset = User.objects.filter(tenant=self.tenant).order_by("username")

        if self.instance and self.instance.pk:
            if self.instance.pinned_dashboard_ids:
                self.fields["pinned_dashboard_ids_raw"].initial = json.dumps(
                    self.instance.pinned_dashboard_ids, indent=2
                )
            else:
                self.fields["pinned_dashboard_ids_raw"].initial = "[]"

            if self.instance.pinned_report_ids:
                self.fields["pinned_report_ids_raw"].initial = json.dumps(
                    self.instance.pinned_report_ids, indent=2
                )
            else:
                self.fields["pinned_report_ids_raw"].initial = "[]"
        else:
            self.fields["pinned_dashboard_ids_raw"].initial = "[]"
            self.fields["pinned_report_ids_raw"].initial = "[]"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_user"])

        raw_dashboards = cleaned_data.get("pinned_dashboard_ids_raw", "").strip()
        if raw_dashboards:
            try:
                parsed_dash = json.loads(raw_dashboards)
                if not isinstance(parsed_dash, list) or not all(isinstance(x, int) for x in parsed_dash):
                    self.add_error("pinned_dashboard_ids_raw", "Must be a JSON array of numeric integer IDs.")
                elif self.tenant and parsed_dash:
                    valid_dash_ids = set(
                        BiDashboard.objects.filter(tenant=self.tenant, id__in=parsed_dash).values_list("id", flat=True)
                    )
                    invalid_dash_ids = set(parsed_dash) - valid_dash_ids
                    if invalid_dash_ids:
                        self.add_error(
                            "pinned_dashboard_ids_raw",
                            f"The following dashboard IDs do not exist in your tenant: {sorted(invalid_dash_ids)}",
                        )
                    else:
                        self.instance.pinned_dashboard_ids = parsed_dash
                else:
                    self.instance.pinned_dashboard_ids = parsed_dash
            except json.JSONDecodeError as exc:
                self.add_error("pinned_dashboard_ids_raw", f"Invalid JSON syntax: {exc}")
        else:
            self.instance.pinned_dashboard_ids = []

        raw_reports = cleaned_data.get("pinned_report_ids_raw", "").strip()
        if raw_reports:
            try:
                parsed_rep = json.loads(raw_reports)
                if not isinstance(parsed_rep, list) or not all(isinstance(x, int) for x in parsed_rep):
                    self.add_error("pinned_report_ids_raw", "Must be a JSON array of numeric integer IDs.")
                elif self.tenant and parsed_rep:
                    valid_rep_ids = set(
                        ReportDefinition.objects.filter(tenant=self.tenant, id__in=parsed_rep).values_list("id", flat=True)
                    )
                    invalid_rep_ids = set(parsed_rep) - valid_rep_ids
                    if invalid_rep_ids:
                        self.add_error(
                            "pinned_report_ids_raw",
                            f"The following report IDs do not exist in your tenant: {sorted(invalid_rep_ids)}",
                        )
                    else:
                        self.instance.pinned_report_ids = parsed_rep
                else:
                    self.instance.pinned_report_ids = parsed_rep
            except json.JSONDecodeError as exc:
                self.add_error("pinned_report_ids_raw", f"Invalid JSON syntax: {exc}")
        else:
            self.instance.pinned_report_ids = []

        return cleaned_data

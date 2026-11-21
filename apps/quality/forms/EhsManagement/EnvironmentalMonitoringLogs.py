from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation

User = get_user_model()


class EnvironmentalMonitoringLogForm(TenantModelForm):
    class Meta:
        model = EnvironmentalMonitoringLog
        fields = [
            "sampling_point_id",
            "sampling_timestamp",
            "org_unit",
            "cleanroom_class",
            "operational_state",
            "monitoring_category",
            "parameter_name",
            "measured_value",
            "unit_of_measure",
            "target_nominal_value",
            "lower_alert_limit",
            "upper_alert_limit",
            "lower_action_limit",
            "upper_action_limit",
            "excursion_details",
            "immediate_containment_action",
            "sampled_by",
            "verified_by",
            "measurement_instrument",
            "process_deviation",
            "non_conformance_report",
            "capa_investigation",
            "notes",
        ]
        widgets = {
            "sampling_point_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CR-ISO7-AIRLOCK-01"}),
            "sampling_timestamp": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "cleanroom_class": forms.Select(attrs={"class": "form-select"}),
            "operational_state": forms.Select(attrs={"class": "form-select"}),
            "monitoring_category": forms.Select(attrs={"class": "form-select"}),
            "parameter_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Non-Viable Particles >= 0.5 um"}),
            "measured_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "unit_of_measure": forms.Select(attrs={"class": "form-select"}),
            "target_nominal_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "lower_alert_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "upper_alert_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "lower_action_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "upper_action_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "excursion_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Describe excursion cause, batch impact, and environmental context"}),
            "immediate_containment_action": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Air purge initiated, production line paused, fogging/sanitization scheduled"}),
            "sampled_by": forms.Select(attrs={"class": "form-select"}),
            "verified_by": forms.Select(attrs={"class": "form-select"}),
            "measurement_instrument": forms.Select(attrs={"class": "form-select"}),
            "process_deviation": forms.Select(attrs={"class": "form-select"}),
            "non_conformance_report": forms.Select(attrs={"class": "form-select"}),
            "capa_investigation": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["sampled_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["verified_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["measurement_instrument"].queryset = CalibrationGage.objects.filter(
                tenant=self.tenant
            ).order_by("gage_id", "name")
            self.fields["process_deviation"].queryset = ProcessDeviation.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["non_conformance_report"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["capa_investigation"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("number")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "org_unit",
                "sampled_by",
                "verified_by",
                "measurement_instrument",
                "process_deviation",
                "non_conformance_report",
                "capa_investigation",
            ],
        )
        lower_alert = cleaned_data.get("lower_alert_limit")
        upper_alert = cleaned_data.get("upper_alert_limit")
        if lower_alert is not None and upper_alert is not None and lower_alert > upper_alert:
            self.add_error("lower_alert_limit", "Lower alert limit cannot exceed upper alert limit.")

        lower_action = cleaned_data.get("lower_action_limit")
        upper_action = cleaned_data.get("upper_action_limit")
        if lower_action is not None and upper_action is not None and lower_action > upper_action:
            self.add_error("lower_action_limit", "Lower action limit cannot exceed upper action limit.")

        return cleaned_data

from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport

User = get_user_model()


class SafetyIncidentForm(TenantModelForm):
    class Meta:
        model = SafetyIncident
        fields = [
            "title",
            "incident_date",
            "report_date",
            "incident_type",
            "severity",
            "org_unit",
            "location_details",
            "reported_by",
            "affected_person",
            "affected_party_name",
            "affected_party_type",
            "nature_of_injury",
            "body_part_affected",
            "medical_treatment_level",
            "is_osha_recordable",
            "osha_classification",
            "lost_workdays_count",
            "restricted_workdays_count",
            "date_returned_to_work",
            "ppe_compliance_status",
            "ppe_notes",
            "immediate_actions_taken",
            "lead_investigator",
            "root_cause_category",
            "investigation_findings",
            "capa_investigation",
            "non_conformance_report",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Eyewash splash incident during solvent bath transfer"}),
            "incident_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "report_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "incident_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "location_details": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Cleanroom B Airlock 3 / Gowning station"}),
            "reported_by": forms.Select(attrs={"class": "form-select"}),
            "affected_person": forms.Select(attrs={"class": "form-select"}),
            "affected_party_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Fill if contractor, temporary worker, or visitor"}),
            "affected_party_type": forms.Select(attrs={"class": "form-select"}),
            "nature_of_injury": forms.Select(attrs={"class": "form-select"}),
            "body_part_affected": forms.Select(attrs={"class": "form-select"}),
            "medical_treatment_level": forms.Select(attrs={"class": "form-select"}),
            "is_osha_recordable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "osha_classification": forms.Select(attrs={"class": "form-select"}),
            "lost_workdays_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "restricted_workdays_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "date_returned_to_work": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "ppe_compliance_status": forms.Select(attrs={"class": "form-select"}),
            "ppe_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Detail PPE donned, damaged, or absent during incident"}),
            "immediate_actions_taken": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "First aid rendered, area evacuated, machine lock-out performed"}),
            "lead_investigator": forms.Select(attrs={"class": "form-select"}),
            "root_cause_category": forms.Select(attrs={"class": "form-select"}),
            "investigation_findings": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed root cause findings and sequence of events"}),
            "capa_investigation": forms.Select(attrs={"class": "form-select"}),
            "non_conformance_report": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["reported_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["affected_person"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["lead_investigator"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["capa_investigation"].queryset = CapaInvestigation.objects.filter(
                tenant=self.tenant
            ).order_by("number")
            self.fields["non_conformance_report"].queryset = NonConformanceReport.objects.filter(
                tenant=self.tenant
            ).order_by("number")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            [
                "org_unit",
                "reported_by",
                "affected_person",
                "lead_investigator",
                "capa_investigation",
                "non_conformance_report",
            ],
        )
        return cleaned_data

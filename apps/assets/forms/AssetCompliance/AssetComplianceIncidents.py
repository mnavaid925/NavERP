from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetCompliance.AssetComplianceAudits import AssetComplianceAudit
from apps.assets.models.AssetCompliance.AssetComplianceIncidents import AssetComplianceIncident
from apps.assets.models.AssetCompliance.AssetPermitLicenses import AssetPermitLicense
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()


class AssetComplianceIncidentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetComplianceIncident
        fields = [
            "title",
            "incident_date",
            "discovery_date",
            "incident_type",
            "severity",
            "asset",
            "permit",
            "audit",
            "enforcement_agency",
            "citation_reference",
            "fine_assessed",
            "fine_paid",
            "fine_payment_date",
            "root_cause",
            "root_cause_analysis",
            "corrective_action_plan",
            "assigned_investigator",
            "target_resolution_date",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EPA Title V Exceedance — Boiler #2 NOX Emission Spike"}),
            "incident_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "discovery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "incident_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "permit": forms.Select(attrs={"class": "form-select"}),
            "audit": forms.Select(attrs={"class": "form-select"}),
            "enforcement_agency": forms.Select(attrs={"class": "form-select"}),
            "citation_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. OSHA-CIT-2026-1184"}),
            "fine_assessed": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "fine_paid": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "fine_payment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "root_cause": forms.Select(attrs={"class": "form-select"}),
            "root_cause_analysis": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Investigation findings, failure mode, and contributing factors..."}),
            "corrective_action_plan": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Mandated CAPA steps to prevent recurrence and restore compliance..."}),
            "assigned_investigator": forms.Select(attrs={"class": "form-select"}),
            "target_resolution_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["permit"].queryset = AssetPermitLicense.objects.filter(tenant=self.tenant)
            self.fields["audit"].queryset = AssetComplianceAudit.objects.filter(tenant=self.tenant)
            self.fields["enforcement_agency"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["assigned_investigator"].queryset = User.objects.filter(tenant=self.tenant)
        if "status" in self.fields:
            self.fields["status"].choices = [
                (k, v) for k, v in AssetComplianceIncident.STATUS_CHOICES if k not in ["resolved", "closed"]
            ]
        if "fine_assessed" in self.fields:
            self.fields["fine_assessed"].required = False
            self.fields["fine_assessed"].initial = Decimal("0.00")
        if "fine_paid" in self.fields:
            self.fields["fine_paid"].required = False
            self.fields["fine_paid"].initial = Decimal("0.00")

    def clean_status(self):
        status = self.cleaned_data.get("status")
        if status in ["resolved", "closed"]:
            raise forms.ValidationError("Status cannot be set to Resolved or Closed directly. Use the resolution and closure workflows.")
        return status

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["asset", "permit", "audit", "enforcement_agency", "assigned_investigator"])
        fine_assessed = cleaned.get("fine_assessed")
        if fine_assessed is None:
            cleaned["fine_assessed"] = Decimal("0.00")
            fine_assessed = cleaned["fine_assessed"]

        fine_paid = cleaned.get("fine_paid")
        if fine_paid is None:
            cleaned["fine_paid"] = Decimal("0.00")
            fine_paid = cleaned["fine_paid"]

        if fine_paid is not None and fine_assessed is not None and fine_paid > fine_assessed:
            self.add_error("fine_paid", "Fine paid cannot exceed fine assessed.")
        return cleaned

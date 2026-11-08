from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetInventoryTracking.AssetIncidentReports import AssetIncidentReport
from apps.core.models import Party
from apps.scm.models import Asset, Location

User = get_user_model()


class AssetIncidentReportForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetIncidentReport
        fields = [
            "title",
            "asset",
            "incident_type",
            "severity",
            "incident_date",
            "last_known_location",
            "location_details",
            "custodian_at_loss",
            "investigator",
            "police_report_filed",
            "police_report_number",
            "police_precinct",
            "police_filing_date",
            "insurance_claim_filed",
            "insurance_carrier",
            "insurance_claim_number",
            "estimated_loss_value",
            "insurance_claimed_amount",
            "insurance_settled_amount",
            "incident_description",
            "investigation_findings",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "reported_by",
            "write_off_authorized_by",
            "write_off_date",
            "resolution_action",
            "write_off_notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Stolen Fluke Thermal Imager from Van #12"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "incident_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "incident_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "last_known_location": forms.Select(attrs={"class": "form-select"}),
            "location_details": forms.TextInput(attrs={"class": "form-input", "placeholder": "Specific job site, vehicle, or bay"}),
            "custodian_at_loss": forms.Select(attrs={"class": "form-select"}),
            "investigator": forms.Select(attrs={"class": "form-select"}),
            "police_report_filed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "police_report_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "Case # 2026-PD-8910"}),
            "police_precinct": forms.TextInput(attrs={"class": "form-input", "placeholder": "Metropolitan Police Dept - District 4"}),
            "police_filing_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "insurance_claim_filed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "insurance_carrier": forms.TextInput(attrs={"class": "form-input", "placeholder": "Travelers / Hartford Equipment Policy"}),
            "insurance_claim_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "CLM-2026-0049"}),
            "estimated_loss_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "insurance_claimed_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "insurance_settled_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "incident_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed circumstances, witness statements, time discovered..."}),
            "investigation_findings": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Internal investigation summary, security camera footage review..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("number")
            self.fields["last_known_location"].queryset = Location.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
            self.fields["custodian_at_loss"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["investigator"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["asset", "last_known_location", "custodian_at_loss"])

        # Amounts >= 0
        for field in ["estimated_loss_value", "insurance_claimed_amount", "insurance_settled_amount"]:
            val = cleaned_data.get(field)
            if val is not None and val < Decimal("0.00"):
                self.add_error(field, "Amount cannot be negative.")

        return cleaned_data

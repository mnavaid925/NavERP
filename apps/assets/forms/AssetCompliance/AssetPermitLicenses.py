from django import forms

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetCompliance.AssetPermitLicenses import AssetPermitLicense
from apps.core.models import Party
from apps.scm.models import Asset


class AssetPermitLicenseForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetPermitLicense
        fields = [
            "permit_name",
            "permit_number",
            "permit_type",
            "asset",
            "issuing_authority",
            "issue_date",
            "effective_date",
            "expiration_date",
            "renewal_lead_days",
            "renewal_fee",
            "operating_conditions",
            "status",
        ]
        widgets = {
            "permit_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Stationary Source Air Emissions Permit (Title V)"}),
            "permit_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EPA-AIR-2026-9042"}),
            "permit_type": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "issuing_authority": forms.Select(attrs={"class": "form-select"}),
            "issue_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "renewal_lead_days": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "renewal_fee": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "operating_conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Permitted hours, emissions caps, fluid volume limits, monitoring rules..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["issuing_authority"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["asset", "issuing_authority"])
        return cleaned

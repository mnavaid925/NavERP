from django import forms

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetMaintenanceRequest
from apps.assets.models.AssetWarrantyInsurance.AssetWarranties import AssetWarranty
from apps.assets.models.AssetWarrantyInsurance.AssetWarrantyClaims import AssetWarrantyClaim
from apps.core.models import Document
from apps.scm.models import Asset as OperationalAsset


class AssetWarrantyClaimForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetWarrantyClaim
        fields = [
            "title",
            "warranty",
            "fixed_asset",
            "operational_asset",
            "maintenance_request",
            "incident_date",
            "operating_meter_at_failure",
            "defect_description",
            "warrantor_claim_reference",
            "currency",
            "claimed_amount",
            "deductible_applied",
            "resolution_type",
            "part_return_status",
            "rma_tracking_number",
            "settlement_notes",
            "supporting_document",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Spindle Bearing Premature Failure Claim"}),
            "warranty": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "maintenance_request": forms.Select(attrs={"class": "form-select"}),
            "incident_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "operating_meter_at_failure": forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 2450"}),
            "defect_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed defect physical symptoms, root cause, diagnostic codes..."}),
            "warrantor_claim_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. OEM-RMA-84912"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "claimed_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "deductible_applied": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "resolution_type": forms.Select(attrs={"class": "form-select"}),
            "part_return_status": forms.Select(attrs={"class": "form-select"}),
            "rma_tracking_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1Z9999999999999999"}),
            "settlement_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Settlement or vendor response commentary..."}),
            "supporting_document": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["warranty"].queryset = AssetWarranty.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.filter(tenant=self.tenant)
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["supporting_document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        claimed = cleaned_data.get("claimed_amount") or 0
        deductible = cleaned_data.get("deductible_applied") or 0
        if deductible > claimed:
            self.add_error("deductible_applied", "Deductible applied cannot exceed total claimed amount.")

        reject_foreign(
            self,
            cleaned_data,
            [
                "warranty",
                "fixed_asset",
                "operational_asset",
                "maintenance_request",
                "supporting_document",
            ],
        )
        return cleaned_data

from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModification

User = get_user_model()


class AssetLeaseModificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetLeaseModification
        fields = [
            "lease_contract",
            "modification_type",
            "request_date",
            "effective_date",
            "prior_lease_liability",
            "revised_lease_liability",
            "prior_rou_asset_value",
            "revised_rou_asset_value",
            "gain_loss_on_modification",
            "impairment_loss_recognized",
            "revised_term_months",
            "revised_payment_amount",
            "revised_discount_rate_pct",
            "requested_by",
            "status",
            "justification",
            "notes",
        ]
        widgets = {
            "lease_contract": forms.Select(attrs={"class": "form-select"}),
            "modification_type": forms.Select(attrs={"class": "form-select"}),
            "request_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "prior_lease_liability": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "revised_lease_liability": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "prior_rou_asset_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "revised_rou_asset_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "gain_loss_on_modification": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "impairment_loss_recognized": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "revised_term_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "revised_payment_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "revised_discount_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "min": "0"}),
            "requested_by": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Business justification for lease modification..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Technical accounting notes and audit references..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["lease_contract"].queryset = AssetLeaseContract.objects.filter(
                tenant=self.tenant
            ).order_by("-id")
            self.fields["requested_by"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["lease_contract", "requested_by"])

        rate = cleaned.get("revised_discount_rate_pct")
        if rate is not None and (rate < 0 or rate > 100):
            self.add_error("revised_discount_rate_pct", "Discount rate must be between 0% and 100%.")

        term = cleaned.get("revised_term_months")
        if term is not None and (term < 1 or term > 600):
            self.add_error("revised_term_months", "Revised lease term must be between 1 and 600 months.")

        non_negative_fields = [
            "prior_lease_liability",
            "revised_lease_liability",
            "prior_rou_asset_value",
            "revised_rou_asset_value",
            "impairment_loss_recognized",
            "revised_payment_amount",
        ]
        for f in non_negative_fields:
            val = cleaned.get(f)
            if val is not None and val < 0:
                self.add_error(f, "Amount cannot be negative.")

        return cleaned

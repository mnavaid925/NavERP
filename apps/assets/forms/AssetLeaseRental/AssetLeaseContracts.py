from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.core.models import Party
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()


class AssetLeaseContractForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetLeaseContract
        fields = [
            "title",
            "master_lease_agreement_ref",
            "lessor",
            "asset",
            "category",
            "fixed_asset",
            "inception_date",
            "commencement_date",
            "expiration_date",
            "first_payment_date",
            "early_termination_notice_date",
            "lease_term_months",
            "economic_life_months",
            "payment_amount",
            "payment_frequency",
            "payment_timing",
            "discount_rate_pct",
            "fair_market_value",
            "initial_direct_costs",
            "lease_incentives",
            "residual_value_guarantee",
            "purchase_option_price",
            "transfer_of_ownership",
            "has_purchase_option",
            "is_specialized_asset",
            "classification",
            "classification_overridden",
            "classification_notes",
            "status",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Master Lease Schedule for CNC Machining Center"}),
            "master_lease_agreement_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. MLA-2026-CAT-088"}),
            "lessor": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "inception_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "commencement_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expiration_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "first_payment_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "early_termination_notice_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "lease_term_months": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "600"}),
            "economic_life_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "payment_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "payment_frequency": forms.Select(attrs={"class": "form-select"}),
            "payment_timing": forms.Select(attrs={"class": "form-select"}),
            "discount_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "min": "0"}),
            "fair_market_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "initial_direct_costs": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "lease_incentives": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "residual_value_guarantee": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "purchase_option_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "transfer_of_ownership": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "has_purchase_option": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_specialized_asset": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "classification": forms.Select(attrs={"class": "form-select"}),
            "classification_overridden": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "classification_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Technical accounting notes or statutory classification details..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Administrative conditions, renewal options, or insurance terms..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["lessor"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["category"].queryset = AssetCategory.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["lessor", "asset", "category", "fixed_asset"])

        commencement = cleaned.get("commencement_date")
        expiration = cleaned.get("expiration_date")
        if commencement and expiration and expiration < commencement:
            self.add_error("expiration_date", "Expiration date cannot precede commencement date.")

        term = cleaned.get("lease_term_months")
        if term is not None and (term < 1 or term > 600):
            self.add_error("lease_term_months", "Lease term must be between 1 and 600 months (50 years max).")

        rate = cleaned.get("discount_rate_pct")
        if rate is not None and (rate < 0 or rate > 100):
            self.add_error("discount_rate_pct", "Discount rate must be between 0% and 100%.")

        non_negative_fields = [
            "payment_amount",
            "fair_market_value",
            "initial_direct_costs",
            "lease_incentives",
            "residual_value_guarantee",
            "purchase_option_price",
        ]
        for f in non_negative_fields:
            val = cleaned.get(f)
            if val is not None and val < 0:
                self.add_error(f, "Amount cannot be negative.")

        return cleaned

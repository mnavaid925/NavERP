from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion


class CouponPromotionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CouponPromotion
        fields = [
            "code",
            "name",
            "discount_type",
            "discount_value",
            "min_spend",
            "max_discount_amount",
            "usage_limit_total",
            "usage_limit_per_customer",
            "is_stackable",
            "loyalty_tier_required",
            "customer",
            "valid_from",
            "valid_to",
            "is_active",
        ]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input font-mono uppercase", "placeholder": "e.g. SUMMER20"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Summer 2026 Kickoff"}),
            "discount_type": forms.Select(attrs={"class": "form-select"}),
            "discount_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "min_spend": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "max_discount_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "usage_limit_total": forms.NumberInput(attrs={"class": "form-input", "min": "1", "placeholder": "Unlimited"}),
            "usage_limit_per_customer": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_stackable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "loyalty_tier_required": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "valid_from": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "valid_to": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean_code(self):
        code = self.cleaned_data.get("code", "")
        if code:
            code = code.strip().upper()
        return code

    def clean_discount_value(self):
        val = self.cleaned_data.get("discount_value")
        dtype = self.cleaned_data.get("discount_type")
        if val is not None:
            if val < Decimal("0.0000"):
                raise forms.ValidationError("Discount value cannot be negative.")
            if dtype == "percentage" and val > Decimal("100.0000"):
                raise forms.ValidationError("Percentage discount cannot exceed 100%.")
        return val

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["customer"])

        valid_from = cleaned.get("valid_from")
        valid_to = cleaned.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            self.add_error("valid_to", "Expiration date (valid_to) must be after activation date (valid_from).")

        return cleaned

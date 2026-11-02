from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bQuoteRequests import B2bQuoteRequest


class B2bQuoteRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = B2bQuoteRequest
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "submitted_at",
            "quoted_at",
            "accepted_at",
            "converted_order",
            "line_items_data",
        ]
        widgets = {
            "company": forms.Select(attrs={"class": "form-select"}),
            "requested_by": forms.Select(attrs={"class": "form-select"}),
            "assigned_sales_rep": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "target_budget": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "50000.00"}),
            "original_subtotal": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "45000.00"}),
            "quoted_discount_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "10.00"}),
            "quoted_total": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "40500.00"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "3200.00"}),
            "shipping_estimate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "850.00"}),
            "target_delivery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "valid_until": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "buyer_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Customer specifications..."}),
            "merchant_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Internal margin assessment..."}),
            "rejection_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Reason if declined..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        User = get_user_model()
        if self.tenant:
            self.fields["company"].queryset = B2bCompanyAccount.objects.filter(tenant=self.tenant)
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["requested_by"].queryset = User.objects.filter(is_active=True)
        self.fields["assigned_sales_rep"].queryset = User.objects.filter(is_active=True)

    def clean_target_budget(self):
        val = self.cleaned_data.get("target_budget")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Target budget cannot be negative.")
        return val

    def clean_quoted_discount_percent(self):
        val = self.cleaned_data.get("quoted_discount_percent")
        if val is not None and (val < Decimal("0.00") or val > Decimal("100.00")):
            raise forms.ValidationError("Discount percentage must be between 0% and 100%.")
        return val

    def clean_original_subtotal(self):
        val = self.cleaned_data.get("original_subtotal")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Subtotal cannot be negative.")
        return val

    def clean_quoted_total(self):
        val = self.cleaned_data.get("quoted_total")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Quoted total cannot be negative.")
        return val

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["company"])
        return cleaned

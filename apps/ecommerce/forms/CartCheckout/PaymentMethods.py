from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig


class PaymentMethodConfigForm(TenantModelForm):
    class Meta:
        model = PaymentMethodConfig
        fields = [
            "name",
            "provider",
            "method_category",
            "environment",
            "is_active",
            "display_order",
            "fee_type",
            "fee_amount",
            "min_order_amount",
            "max_order_amount",
            "supported_currencies",
            "instructions",
            "supports_refunds",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Credit / Debit Card (Stripe)"}),
            "provider": forms.Select(attrs={"class": "form-select"}),
            "method_category": forms.Select(attrs={"class": "form-select"}),
            "environment": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "fee_type": forms.Select(attrs={"class": "form-select"}),
            "fee_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "min_order_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional minimum"}),
            "max_order_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional maximum"}),
            "supported_currencies": forms.TextInput(attrs={"class": "form-input", "placeholder": "USD,EUR,GBP"}),
            "instructions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "supports_refunds": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def clean_supported_currencies(self):
        val = self.cleaned_data.get("supported_currencies", "")
        if val:
            parts = [p.strip().upper() for p in val.split(",") if p.strip()]
            return ",".join(parts)
        return "USD"

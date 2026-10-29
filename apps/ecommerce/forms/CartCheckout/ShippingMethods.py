from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig


class ShippingMethodConfigForm(TenantModelForm):
    class Meta:
        model = ShippingMethodConfig
        fields = [
            "name",
            "code",
            "carrier",
            "calculation_type",
            "base_rate",
            "cost_per_kg",
            "free_shipping_threshold",
            "estimated_days_min",
            "estimated_days_max",
            "destination_countries",
            "is_active",
            "sort_order",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Standard Ground Delivery"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "GROUND"}),
            "carrier": forms.Select(attrs={"class": "form-select"}),
            "calculation_type": forms.Select(attrs={"class": "form-select"}),
            "base_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_per_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "free_shipping_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional e.g. 75.00"}),
            "estimated_days_min": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "estimated_days_max": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "destination_countries": forms.TextInput(attrs={"class": "form-input", "placeholder": "US,CA"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean_code(self):
        code = self.cleaned_data.get("code", "")
        return code.strip().upper()

import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.scm.models.InventoryManagement.Items import Item


class ProductVariantForm(TenantUniqueMixin, TenantModelForm):
    option_values_raw = forms.CharField(
        required=False,
        label="Option Dimensions (JSON or Key=Value pairs)",
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea",
                "rows": 2,
                "placeholder": 'e.g. {"Size": "L", "Color": "Navy"} or Size=L, Color=Navy',
            }
        ),
        help_text="Provide option attributes as JSON or comma-separated Key=Value pairs.",
    )

    class Meta:
        model = ProductVariant
        fields = [
            "product",
            "sku",
            "name",
            "barcode",
            "price",
            "compare_at_price",
            "cost_price",
            "item",
            "weight_kg",
            "image_url",
            "is_active",
            "sort_order",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "sku": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TSH-NAVY-L"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Navy / Large"}),
            "barcode": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 012345678905"}),
            "price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "compare_at_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "weight_kg": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "image_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://example.com/variant.jpg"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "sort_order" in self.fields and not self.instance.pk:
            self.fields["sort_order"].initial = 0
        if self.tenant:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["item"].empty_label = "-- None (Not linked to warehouse stock) --"

        if self.instance and self.instance.pk and self.instance.option_values:
            self.fields["option_values_raw"].initial = json.dumps(self.instance.option_values)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["product", "item"])

        raw = cleaned_data.get("option_values_raw", "").strip()
        parsed_options = {}
        if raw:
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    val = json.loads(raw)
                    if isinstance(val, dict):
                        parsed_options = val
                    else:
                        self.add_error("option_values_raw", "JSON root must be an object dictionary.")
                except json.JSONDecodeError:
                    self.add_error("option_values_raw", "Invalid JSON format.")
            else:
                # Comma separated Key=Value pairs
                for part in raw.split(","):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        parsed_options[k.strip()] = v.strip()
                    elif ":" in part:
                        k, v = part.split(":", 1)
                        parsed_options[k.strip()] = v.strip()

        cleaned_data["option_values"] = parsed_options
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "option_values" in self.cleaned_data:
            instance.option_values = self.cleaned_data["option_values"]
        if commit:
            instance.save()
        return instance

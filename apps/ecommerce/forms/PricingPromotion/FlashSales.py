from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.PricingPromotion.FlashSales import FlashSale
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class FlashSaleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FlashSale
        fields = [
            "title",
            "status",
            "product",
            "variant",
            "category",
            "discount_percentage",
            "flash_price",
            "inventory_cap",
            "max_units_per_order",
            "start_time",
            "end_time",
            "badge_label",
            "banner_bg_color",
            "terms_and_conditions",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Midnight Lightning Deal - 40% Off Audio"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "discount_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "flash_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "Optional override"}),
            "inventory_cap": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "max_units_per_order": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "start_time": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "end_time": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "badge_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "FLASH DEAL"}),
            "banner_bg_color": forms.TextInput(attrs={"class": "form-input", "placeholder": "#ef4444"}),
            "terms_and_conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant).select_related("product")
            self.fields["category"].queryset = StoreCategory.objects.filter(tenant=self.tenant)

    def clean_inventory_cap(self):
        cap = self.cleaned_data.get("inventory_cap")
        if cap is not None and cap < 1:
            raise forms.ValidationError("Promotional inventory cap must be at least 1 unit.")
        return cap

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant", "category"])

        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "Flash sale end time must be after start time.")

        inventory_cap = cleaned.get("inventory_cap")
        max_units = cleaned.get("max_units_per_order")
        if inventory_cap and max_units and max_units > inventory_cap:
            self.add_error("max_units_per_order", "Maximum units per order cannot exceed total inventory cap.")

        return cleaned

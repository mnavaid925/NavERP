from decimal import Decimal

from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitor
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class CompetitorPriceMonitorForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CompetitorPriceMonitor
        fields = [
            "competitor_name",
            "product",
            "variant",
            "competitor_url",
            "competitor_price",
            "competitor_currency",
            "is_in_stock",
            "match_strategy",
            "beat_by_value",
            "min_margin_pct",
            "floor_price",
            "status",
            "notes",
        ]
        widgets = {
            "competitor_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Amazon, Walmart, BestBuy"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "competitor_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "competitor_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "competitor_currency": forms.TextInput(attrs={"class": "form-input", "placeholder": "USD"}),
            "is_in_stock": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "match_strategy": forms.Select(attrs={"class": "form-select"}),
            "beat_by_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "min_margin_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "floor_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "Optional absolute floor"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant).select_related("product")

    def clean_competitor_price(self):
        val = self.cleaned_data.get("competitor_price")
        if val is not None and val < Decimal("0.0000"):
            raise forms.ValidationError("Competitor price cannot be negative.")
        return val

    def clean_competitor_currency(self):
        code = self.cleaned_data.get("competitor_currency", "USD")
        if code:
            code = code.strip().upper()
            if len(code) != 3:
                raise forms.ValidationError("Competitor currency code must be exactly 3 characters.")
        return code

    def clean_min_margin_pct(self):
        val = self.cleaned_data.get("min_margin_pct")
        if val is not None and val < Decimal("0.00"):
            raise forms.ValidationError("Minimum margin percentage cannot be negative.")
        return val

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant"])

        variant = cleaned.get("variant")
        product = cleaned.get("product")
        if variant and not product:
            cleaned["product"] = variant.product

        return cleaned

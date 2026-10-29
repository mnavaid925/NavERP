from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.PricingPromotion.DynamicPriceRules import DynamicPriceRule
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class DynamicPriceRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DynamicPriceRule
        fields = [
            "name",
            "rule_type",
            "adjustment_value",
            "scope",
            "category",
            "product",
            "variant",
            "customer_segment",
            "loyalty_tier",
            "min_quantity",
            "country_code",
            "currency_code",
            "valid_from",
            "valid_to",
            "priority",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. VIP 15% Off Outerwear"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "adjustment_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "scope": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "customer_segment": forms.Select(attrs={"class": "form-select"}),
            "loyalty_tier": forms.Select(attrs={"class": "form-select"}),
            "min_quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "country_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US (optional)"}),
            "currency_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "USD"}),
            "valid_from": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "valid_to": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["category"].queryset = StoreCategory.objects.filter(tenant=self.tenant)
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant).select_related("product")

    def clean_adjustment_value(self):
        val = self.cleaned_data.get("adjustment_value")
        rule_type = self.cleaned_data.get("rule_type")
        if val is not None:
            if val < Decimal("0.0000"):
                raise forms.ValidationError("Adjustment value cannot be negative.")
            if rule_type == "percentage_discount" and val > Decimal("100.0000"):
                raise forms.ValidationError("Percentage discount cannot exceed 100%.")
        return val

    def clean_country_code(self):
        code = self.cleaned_data.get("country_code", "")
        if code:
            code = code.strip().upper()
            if len(code) != 2:
                raise forms.ValidationError("Country code must be exactly 2 characters (ISO 3166-1 alpha-2).")
        return code

    def clean_currency_code(self):
        code = self.cleaned_data.get("currency_code", "USD")
        if code:
            code = code.strip().upper()
            if len(code) != 3:
                raise forms.ValidationError("Currency code must be exactly 3 characters.")
        return code

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["category", "product", "variant"])

        scope = cleaned.get("scope")
        category = cleaned.get("category")
        product = cleaned.get("product")
        variant = cleaned.get("variant")

        if scope == "category" and not category:
            self.add_error("category", "Please select a Store Category for this category-scoped rule.")
        elif scope == "product" and not product:
            self.add_error("product", "Please select a Catalog Product for this product-scoped rule.")
        elif scope == "variant" and not variant:
            self.add_error("variant", "Please select a Product Variant for this variant-scoped rule.")

        valid_from = cleaned.get("valid_from")
        valid_to = cleaned.get("valid_to")
        if valid_from and valid_to and valid_to <= valid_from:
            self.add_error("valid_to", "Expiration date (valid_to) must be after activation date (valid_from).")

        return cleaned

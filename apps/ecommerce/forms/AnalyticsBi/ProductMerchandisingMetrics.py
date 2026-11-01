from django import forms

from apps.ecommerce.forms._common import TenantModelForm, reject_foreign
from apps.ecommerce.models.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetric
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class ProductMerchandisingMetricForm(TenantModelForm):
    class Meta:
        model = ProductMerchandisingMetric
        fields = [
            "product",
            "variant",
            "period_start",
            "period_end",
            "velocity_tier",
            "units_sold",
            "gross_revenue",
            "cost_of_goods",
            "gross_margin_pct",
            "refunds_count",
            "return_rate_pct",
            "page_views_count",
            "add_to_cart_count",
            "conversion_rate_pct",
            "inventory_turnover_ratio",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "period_end": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "velocity_tier": forms.Select(attrs={"class": "form-select"}),
            "units_sold": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "gross_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_of_goods": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "gross_margin_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "refunds_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "return_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "page_views_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "add_to_cart_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "conversion_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "inventory_turnover_ratio": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["variant"].queryset = ProductVariant.objects.filter(
                tenant=self.tenant
            ).order_by("sku")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant"])
        return cleaned

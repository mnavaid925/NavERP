from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductRelationships import ProductRelationship


class ProductRelationshipForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductRelationship
        fields = [
            "source_product",
            "target_product",
            "relationship_type",
            "discount_pct",
            "is_active",
            "sort_order",
            "notes",
        ]
        widgets = {
            "source_product": forms.Select(attrs={"class": "form-select"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "relationship_type": forms.Select(attrs={"class": "form-select"}),
            "discount_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input"}),
            "notes": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Recommended combo for seasonal promo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            prods = CatalogProduct.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["source_product"].queryset = prods
            self.fields["target_product"].queryset = prods

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["source_product", "target_product"])

        src = cleaned_data.get("source_product")
        tgt = cleaned_data.get("target_product")
        if src and tgt and src == tgt:
            raise ValidationError({"target_product": "Target product must be different from source product."})

        return cleaned_data

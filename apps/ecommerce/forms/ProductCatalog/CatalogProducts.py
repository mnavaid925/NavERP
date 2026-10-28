from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.scm.models.InventoryManagement.Items import Item


class CatalogProductForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CatalogProduct
        fields = [
            "name",
            "slug",
            "item",
            "primary_category",
            "categories",
            "status",
            "visibility",
            "brand",
            "short_description",
            "description",
            "hero_image_url",
            "video_url",
            "is_featured",
            "is_digital",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Classic Cotton Crewneck T-Shirt"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. classic-cotton-crewneck"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "primary_category": forms.Select(attrs={"class": "form-select"}),
            "categories": forms.SelectMultiple(attrs={"class": "form-select", "size": "4"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
            "brand": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Studio"}),
            "short_description": forms.TextInput(attrs={"class": "form-input", "placeholder": "Brief summary for product card listings"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Full marketing copy and specs..."}),
            "hero_image_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://example.com/product-hero.jpg"}),
            "video_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://youtube.com/watch?v=..."}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_digital": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "meta_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "SEO Title tag"}),
            "meta_description": forms.TextInput(attrs={"class": "form-input", "placeholder": "SEO Meta description tag"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            cats = StoreCategory.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["primary_category"].queryset = cats
            self.fields["primary_category"].empty_label = "-- Select Primary Category --"
            self.fields["categories"].queryset = cats

            items = Item.objects.filter(tenant=self.tenant)
            self.fields["item"].queryset = items
            self.fields["item"].empty_label = "-- None (Multi-variant or Standalone) --"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["primary_category", "item", "categories"])
        return cleaned_data

from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class StoreCategoryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StoreCategory
        fields = [
            "name",
            "slug",
            "parent",
            "description",
            "image_url",
            "display_order",
            "is_active",
            "include_in_menu",
            "meta_title",
            "meta_description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Mens Apparel"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. mens-apparel"}),
            "parent": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Category description..."}),
            "image_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://example.com/category-banner.jpg"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "include_in_menu": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "meta_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "SEO Title"}),
            "meta_description": forms.TextInput(attrs={"class": "form-input", "placeholder": "SEO Description"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            qs = StoreCategory.objects.filter(tenant=self.tenant, is_active=True)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = qs
            self.fields["parent"].empty_label = "-- Root Category (No Parent) --"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["parent"])
        return cleaned_data

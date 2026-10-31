from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ReviewUgc.VisualUgcMedia import VisualUgcMedia


class VisualUgcMediaForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = VisualUgcMedia
        fields = [
            "media_type",
            "media_url",
            "thumbnail_url",
            "caption",
            "uploader_name",
            "uploader_handle",
            "tagged_product",
            "tagged_variant",
            "rights_status",
            "is_shoppable",
            "is_published",
            "display_order",
        ]
        widgets = {
            "media_type": forms.Select(attrs={"class": "form-select"}),
            "media_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://example.com/images/ugc-photo.jpg"}
            ),
            "thumbnail_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://example.com/images/ugc-thumb.jpg"}
            ),
            "caption": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Customer quote or photo caption..."}
            ),
            "uploader_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Sarah Jenkins"}
            ),
            "uploader_handle": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "@sarah_styles"}
            ),
            "tagged_product": forms.Select(attrs={"class": "form-select"}),
            "tagged_variant": forms.Select(attrs={"class": "form-select"}),
            "rights_status": forms.Select(attrs={"class": "form-select"}),
            "is_shoppable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_published": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "display_order": forms.NumberInput(
                attrs={"class": "form-input", "min": 0}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["tagged_product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["tagged_variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)
        self.fields["tagged_variant"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["tagged_product", "tagged_variant"])
        return cleaned

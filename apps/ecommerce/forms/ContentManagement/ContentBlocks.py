from django import forms
from django.core.exceptions import ValidationError

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ContentManagement.ContentBlocks import ContentBlock
from apps.ecommerce.models.ContentManagement.MediaAssets import MediaAsset
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class ContentBlockForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ContentBlock
        fields = [
            "name",
            "block_type",
            "headline",
            "subheadline",
            "body_text",
            "media_asset",
            "cta_label",
            "cta_url",
            "target_category",
            "target_product",
            "bg_color_class",
            "text_color_class",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Internal name (e.g. Summer Homepage Hero)"}
            ),
            "block_type": forms.Select(attrs={"class": "form-select"}),
            "headline": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Customer-facing prominent headline"}
            ),
            "subheadline": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Supporting subheading or tagline"}
            ),
            "body_text": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Descriptive text or bullet highlights"}
            ),
            "media_asset": forms.Select(attrs={"class": "form-select"}),
            "cta_label": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Shop Now, Explore Collection"}
            ),
            "cta_url": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. /category/summer-sale/ or /products/item-1/"}
            ),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "bg_color_class": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "bg-slate-50, bg-indigo-900, etc."}
            ),
            "text_color_class": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "text-slate-900, text-white, etc."}
            ),
            "sort_order": forms.NumberInput(
                attrs={"class": "form-input", "min": 0}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["headline"].required = False
        self.fields["subheadline"].required = False
        self.fields["body_text"].required = False
        self.fields["media_asset"].required = False
        self.fields["cta_label"].required = False
        self.fields["cta_url"].required = False
        self.fields["target_category"].required = False
        self.fields["target_product"].required = False

        if self.tenant:
            self.fields["media_asset"].queryset = MediaAsset.objects.filter(tenant=self.tenant)
            self.fields["target_category"].queryset = StoreCategory.objects.filter(tenant=self.tenant)
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)

    def clean_cta_url(self):
        url = self.cleaned_data.get("cta_url", "").strip()
        if not url:
            return url
        allowed_prefixes = ("/", "#", "http://", "https://")
        if not any(url.startswith(prefix) for prefix in allowed_prefixes):
            raise ValidationError("Target CTA URL must begin with '/', '#', 'http://', or 'https://'.")
        if "javascript:" in url.lower():
            raise ValidationError("Target CTA URL cannot contain JavaScript URIs.")
        return url

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["media_asset", "target_category", "target_product"])
        return cleaned

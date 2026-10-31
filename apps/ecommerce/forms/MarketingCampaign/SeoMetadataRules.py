from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.MarketingCampaign.SeoMetadataRules import SeoMetadataRule
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class SeoMetadataRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SeoMetadataRule
        fields = [
            "name",
            "rule_type",
            "target_category",
            "target_product",
            "url_path_pattern",
            "meta_title_template",
            "meta_description_template",
            "json_ld_schema_type",
            "canonical_url_override",
            "og_title",
            "og_description",
            "og_image_url",
            "robots_directive",
            "sitemap_included",
            "sitemap_priority",
            "sitemap_changefreq",
            "target_keyword",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Footwear Category Meta Rule"}
            ),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "url_path_pattern": forms.TextInput(
                attrs={"class": "form-input font-mono text-sm", "placeholder": "/categories/footwear/*"}
            ),
            "meta_title_template": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "{product_name} - Buy Online | {site_name}"}
            ),
            "meta_description_template": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Discover {product_name} by {brand} in {category}. Premium quality with fast shipping for only ${price}.",
                }
            ),
            "json_ld_schema_type": forms.Select(attrs={"class": "form-select"}),
            "canonical_url_override": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://store.navstore.com/products/shoes"}
            ),
            "og_title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Social share card headline"}
            ),
            "og_description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 2, "placeholder": "Social snippet summary"}
            ),
            "og_image_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://cdn.store.com/images/og-share.jpg"}
            ),
            "robots_directive": forms.Select(attrs={"class": "form-select"}),
            "sitemap_included": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "sitemap_priority": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.05", "min": "0.00", "max": "1.00", "placeholder": "0.80"}
            ),
            "sitemap_changefreq": forms.Select(attrs={"class": "form-select"}),
            "target_keyword": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. running shoes, leather boots"}
            ),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_category"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_category", "target_product"])
        return cleaned_data

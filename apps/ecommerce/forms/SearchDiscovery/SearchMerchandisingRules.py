from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRule


class SearchMerchandisingRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SearchMerchandisingRule
        fields = [
            "name",
            "rule_type",
            "trigger_query",
            "match_type",
            "target_category",
            "action_type",
            "boosted_product",
            "boost_weight",
            "pin_position",
            "redirect_url",
            "banner_title",
            "banner_body",
            "banner_image_url",
            "banner_link_url",
            "priority",
            "start_date",
            "end_date",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Pin Hero Sneaker on Query 'shoes'"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "trigger_query": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. running shoes"}),
            "match_type": forms.Select(attrs={"class": "form-select"}),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "boosted_product": forms.Select(attrs={"class": "form-select"}),
            "boost_weight": forms.NumberInput(attrs={"class": "form-input", "min": "-100", "max": "100"}),
            "pin_position": forms.NumberInput(attrs={"class": "form-input", "min": "1", "max": "50", "placeholder": "1"}),
            "redirect_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "/catalog/clearance/"}),
            "banner_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 20% Off Spring Collection"}),
            "banner_body": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Use code SPRING20 at checkout."}),
            "banner_image_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "banner_link_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "/category/spring-sale/"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "start_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "end_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_category"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant
            )
            self.fields["boosted_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            )
            self.fields["target_category"].empty_label = "-- Select Category (if Category Rule) --"
            self.fields["boosted_product"].empty_label = "-- Select Target Product (if Product Action) --"

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["target_category", "boosted_product"])
        return cleaned

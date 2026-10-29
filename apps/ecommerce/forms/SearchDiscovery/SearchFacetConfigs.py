from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.SearchDiscovery.SearchFacetConfigs import SearchFacetConfig


class SearchFacetConfigForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SearchFacetConfig
        fields = [
            "name",
            "code",
            "source_type",
            "option_key",
            "widget_type",
            "filter_logic",
            "display_order",
            "is_collapsed_by_default",
            "max_values_shown",
            "is_searchable",
            "category_scope",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Brand"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. brand"}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "option_key": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Size or Color (if Variant Option)"}
            ),
            "widget_type": forms.Select(attrs={"class": "form-select"}),
            "filter_logic": forms.Select(attrs={"class": "form-select"}),
            "display_order": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "is_collapsed_by_default": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "max_values_shown": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_searchable": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
            "category_scope": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(
                attrs={"class": "form-checkbox rounded text-primary"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["category_scope"].queryset = StoreCategory.objects.filter(
                tenant=self.tenant
            )
            self.fields["category_scope"].empty_label = "Global (All Categories)"

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["category_scope"])
        return cleaned

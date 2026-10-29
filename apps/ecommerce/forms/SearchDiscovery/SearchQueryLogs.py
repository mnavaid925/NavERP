from django import forms

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.SearchDiscovery.SearchQueryLogs import SearchQueryLog


class SearchQueryLogForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SearchQueryLog
        fields = [
            "query_text",
            "results_count",
            "is_zero_result",
            "sort_order",
            "redirected_to",
            "clicked_product",
            "click_position",
            "session_key",
            "customer",
        ]
        widgets = {
            "query_text": forms.TextInput(attrs={"class": "form-input"}),
            "results_count": forms.NumberInput(attrs={"class": "form-input"}),
            "is_zero_result": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "sort_order": forms.TextInput(attrs={"class": "form-input"}),
            "redirected_to": forms.TextInput(attrs={"class": "form-input"}),
            "clicked_product": forms.Select(attrs={"class": "form-select"}),
            "click_position": forms.NumberInput(attrs={"class": "form-input"}),
            "session_key": forms.TextInput(attrs={"class": "form-input"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["clicked_product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant
            )

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["customer", "clicked_product"])
        return cleaned


class SearchQueryLogFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "Search query text, reference..."}
        ),
    )
    is_zero_result = forms.ChoiceField(
        required=False,
        choices=[
            ("", "All Queries"),
            ("true", "Zero Results Only (Null-Result)"),
            ("false", "Successful Searches (>0 Results)"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sort_order = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Sort order"}),
    )

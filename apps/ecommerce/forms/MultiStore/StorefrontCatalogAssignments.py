from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.MultiStore.StorefrontCatalogAssignments import StorefrontCatalogAssignment
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.accounting.models.GeneralLedger.Currencies import Currency


class StorefrontCatalogAssignmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StorefrontCatalogAssignment
        exclude = ["tenant", "number", "created_at", "updated_at"]
        widgets = {
            "storefront": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "is_visible": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "custom_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Override display title on this storefront"}),
            "custom_price": forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 49.99 (leave blank for base price)", "step": "0.01"}),
            "custom_currency": forms.Select(attrs={"class": "form-select"}),
            "storefront_badge": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Exclusive, Web Only"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "placeholder": "0"}),
            "publish_status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["storefront"].queryset = StorefrontInstance.objects.filter(tenant=tenant)
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=tenant)
            self.fields["custom_currency"].queryset = Currency.objects.filter(tenant=tenant)

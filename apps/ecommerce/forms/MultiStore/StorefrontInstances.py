from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.accounting.models.GeneralLedger.Currencies import Currency


class StorefrontInstanceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StorefrontInstance
        exclude = ["tenant", "number", "created_at", "updated_at"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Apex US Flagship Store"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. apex-us"}),
            "store_type": forms.Select(attrs={"class": "form-select"}),
            "brand_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Apex Athletics"}),
            "primary_domain": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. shop.apexathletics.com"}),
            "custom_domains": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "e.g. us.apexathletics.com, buy.apexathletics.com"}),
            "default_currency": forms.Select(attrs={"class": "form-select"}),
            "supported_currencies": forms.TextInput(attrs={"class": "form-input", "placeholder": "USD,EUR,GBP"}),
            "default_locale": forms.TextInput(attrs={"class": "form-input", "placeholder": "en-US"}),
            "supported_locales": forms.TextInput(attrs={"class": "form-input", "placeholder": "en-US,es-ES,de-DE,fr-FR"}),
            "root_category": forms.Select(attrs={"class": "form-select"}),
            "default_fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "theme_identifier": forms.TextInput(attrs={"class": "form-input", "placeholder": "default-slate"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "checkout_mode": forms.Select(attrs={"class": "form-select"}),
            "ssl_certificate_status": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Storefront target market and brand positioning notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["root_category"].queryset = StoreCategory.objects.filter(tenant=tenant)
            self.fields["default_fulfillment_center"].queryset = FulfillmentCenter.objects.filter(tenant=tenant)
        self.fields["default_currency"].queryset = Currency.objects.filter(is_active=True)
        self.fields["default_currency"].empty_label = None

    def clean_primary_domain(self):
        domain = self.cleaned_data.get("primary_domain", "").strip().lower()
        if not domain:
            raise forms.ValidationError("Primary domain cannot be empty.")
        if "://" in domain:
            domain = domain.split("://")[-1]
        domain = domain.split("/")[0]
        return domain

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Storefront name is required.")
        return name

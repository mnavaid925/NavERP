from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorProductListings import VendorProductListing
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class VendorProductListingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = VendorProductListing
        exclude = [
            "tenant",
            "number",
            "reviewed_at",
            "reviewed_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "seller_sku": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. APX-HEAD-01"}),
            "barcode": forms.TextInput(attrs={"class": "form-input", "placeholder": "UPC / EAN"}),
            "condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Pristine open box, full accessories"}),
            "asking_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "compare_at_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "available_quantity": forms.NumberInput(attrs={"class": "form-input"}),
            "low_stock_threshold": forms.NumberInput(attrs={"class": "form-input"}),
            "lead_time_days": forms.NumberInput(attrs={"class": "form-input"}),
            "moderation_status": forms.Select(attrs={"class": "form-select"}),
            "compliance_status": forms.Select(attrs={"class": "form-select"}),
            "moderator_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "rejection_reason": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Missing copyright documentation"}),
            "submitted_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["vendor"].queryset = MarketplaceVendor.objects.filter(tenant=self.tenant).order_by("store_name")
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant).order_by("title")
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant).order_by("name")


class ListingModerationForm(forms.Form):
    moderation_status = forms.ChoiceField(
        choices=VendorProductListing.MODERATION_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    compliance_status = forms.ChoiceField(
        choices=VendorProductListing.COMPLIANCE_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    moderator_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Internal compliance remarks..."}),
    )
    rejection_reason = forms.CharField(
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Reason code if rejecting..."}),
    )

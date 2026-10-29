from django import forms

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerWishlists import CustomerWishlist, CustomerWishlistItem
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class CustomerWishlistForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerWishlist
        fields = [
            "customer",
            "name",
            "slug",
            "visibility",
            "is_default",
            "notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Birthday Gifts, Tech Setup"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-slug"}),
            "visibility": forms.Select(attrs={"class": "form-select"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["customer"])
        return cleaned


class CustomerWishlistItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerWishlistItem
        fields = [
            "wishlist",
            "product",
            "variant",
            "desired_quantity",
            "priority",
            "comment",
        ]
        widgets = {
            "wishlist": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "desired_quantity": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "comment": forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional personal note"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["wishlist"].queryset = CustomerWishlist.objects.filter(tenant=self.tenant)
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["wishlist", "product", "variant"])
        return cleaned

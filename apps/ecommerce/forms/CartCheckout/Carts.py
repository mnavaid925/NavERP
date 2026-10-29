from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.ecommerce.models.CartCheckout.Carts import Cart, CartItem
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class CartForm(TenantModelForm):
    class Meta:
        model = Cart
        fields = [
            "customer",
            "session_key",
            "email",
            "status",
            "currency",
            "coupon_code",
            "notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "session_key": forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional browser session key"}),
            "email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "customer@example.com"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.TextInput(attrs={"class": "form-input", "placeholder": "USD"}),
            "coupon_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "PROMO10"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["customer"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="customer",
            ).distinct()


class CartItemForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ["product", "variant", "quantity", "unit_price", "total_price"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=tenant)

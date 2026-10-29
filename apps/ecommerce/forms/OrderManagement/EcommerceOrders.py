from decimal import Decimal

from django import forms

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Address import Address
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder, EcommerceOrderLine
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class EcommerceOrderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = EcommerceOrder
        fields = [
            "customer",
            "guest_email",
            "currency",
            "status",
            "payment_status",
            "fulfillment_status",
            "fraud_risk_level",
            "fraud_score",
            "address_verification_status",
            "inventory_reservation_status",
            "discount_amount",
            "shipping_amount",
            "tax_amount",
            "applied_coupon",
            "shipping_name",
            "shipping_address_line1",
            "shipping_city",
            "shipping_state",
            "shipping_postal_code",
            "shipping_country",
            "billing_name",
            "billing_address_line1",
            "billing_city",
            "billing_state",
            "billing_postal_code",
            "billing_country",
            "customer_notes",
            "internal_notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "guest_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "buyer@example.com"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "payment_status": forms.Select(attrs={"class": "form-select"}),
            "fulfillment_status": forms.Select(attrs={"class": "form-select"}),
            "fraud_risk_level": forms.Select(attrs={"class": "form-select"}),
            "fraud_score": forms.NumberInput(attrs={"class": "form-input", "min": "0", "max": "100"}),
            "address_verification_status": forms.Select(attrs={"class": "form-select"}),
            "inventory_reservation_status": forms.Select(attrs={"class": "form-select"}),
            "discount_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "shipping_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "applied_coupon": forms.Select(attrs={"class": "form-select"}),
            "shipping_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Full recipient name"}),
            "shipping_address_line1": forms.TextInput(attrs={"class": "form-input", "placeholder": "123 Commerce St"}),
            "shipping_city": forms.TextInput(attrs={"class": "form-input", "placeholder": "City"}),
            "shipping_state": forms.TextInput(attrs={"class": "form-input", "placeholder": "State/Province"}),
            "shipping_postal_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Postal/ZIP code"}),
            "shipping_country": forms.TextInput(attrs={"class": "form-input", "placeholder": "Country"}),
            "billing_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Billing contact name"}),
            "billing_address_line1": forms.TextInput(attrs={"class": "form-input", "placeholder": "Billing address"}),
            "billing_city": forms.TextInput(attrs={"class": "form-input", "placeholder": "City"}),
            "billing_state": forms.TextInput(attrs={"class": "form-input", "placeholder": "State/Province"}),
            "billing_postal_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Postal/ZIP code"}),
            "billing_country": forms.TextInput(attrs={"class": "form-input", "placeholder": "Country"}),
            "customer_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "internal_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["applied_coupon"].queryset = CouponPromotion.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["customer", "applied_coupon"])
        return cleaned


class EcommerceOrderLineForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = EcommerceOrderLine
        fields = [
            "product",
            "variant",
            "sku",
            "product_name",
            "quantity",
            "unit_price",
            "unit_discount",
            "status",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "sku": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "product_name": forms.TextInput(attrs={"class": "form-input"}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "unit_discount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant"])
        return cleaned

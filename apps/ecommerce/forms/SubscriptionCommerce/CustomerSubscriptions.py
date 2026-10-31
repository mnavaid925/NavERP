from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan


class CustomerSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerSubscription
        fields = [
            "customer_profile",
            "plan",
            "product",
            "variant",
            "status",
            "quantity",
            "unit_price",
            "recurring_discount_pct",
            "started_at",
            "next_billing_date",
            "next_delivery_date",
            "paused_until",
            "shipping_address_line",
            "payment_method_ref",
            "cancellation_reason",
        ]
        widgets = {
            "customer_profile": forms.Select(attrs={"class": "form-select"}),
            "plan": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "1", "min": 1}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0.00", "step": "0.01", "min": 0}
            ),
            "recurring_discount_pct": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "0.00", "step": "0.01", "min": 0, "max": 100}
            ),
            "started_at": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"}
            ),
            "next_billing_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "next_delivery_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "paused_until": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "shipping_address_line": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. 123 Main St, Springfield, IL 62701"}
            ),
            "payment_method_ref": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. tok_visa_4242 or card_ending_1234"}
            ),
            "cancellation_reason": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Documented reason if customer cancels"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer_profile"].queryset = CustomerAccountProfile.objects.filter(
                tenant=self.tenant
            ).order_by("email")
            self.fields["plan"].queryset = SubscriptionPlan.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["product"].queryset = CatalogProduct.objects.filter(
                tenant=self.tenant, status="active"
            ).order_by("name")
            self.fields["variant"].queryset = ProductVariant.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("sku")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["customer_profile", "plan", "product", "variant"])
        return cleaned

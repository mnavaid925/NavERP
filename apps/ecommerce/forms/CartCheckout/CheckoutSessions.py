from django import forms

from apps.accounting.models import TaxCode
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.ecommerce.models.CartCheckout.Carts import Cart
from apps.ecommerce.models.CartCheckout.CheckoutSessions import CheckoutSession
from apps.ecommerce.models.CartCheckout.PaymentMethods import PaymentMethodConfig
from apps.ecommerce.models.CartCheckout.ShippingMethods import ShippingMethodConfig


class CheckoutSessionForm(TenantModelForm):
    class Meta:
        model = CheckoutSession
        fields = [
            "cart",
            "customer",
            "email",
            "phone",
            "flow_type",
            "current_step",
            "status",
            "shipping_name",
            "shipping_address_line1",
            "shipping_address_line2",
            "shipping_city",
            "shipping_state",
            "shipping_postal_code",
            "shipping_country",
            "billing_same_as_shipping",
            "billing_name",
            "billing_address_line1",
            "billing_city",
            "billing_state",
            "billing_postal_code",
            "billing_country",
            "shipping_method",
            "payment_method",
            "tax_code",
            "tax_jurisdiction",
            "tax_rate",
            "is_tax_exempt",
            "tax_exemption_number",
            "subtotal_amount",
            "discount_amount",
            "shipping_amount",
            "tax_amount",
            "total_amount",
            "payment_status",
            "expires_at",
        ]
        widgets = {
            "cart": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "phone": forms.TextInput(attrs={"class": "form-input"}),
            "flow_type": forms.Select(attrs={"class": "form-select"}),
            "current_step": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "shipping_name": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_address_line1": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_address_line2": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_city": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_state": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_postal_code": forms.TextInput(attrs={"class": "form-input"}),
            "shipping_country": forms.TextInput(attrs={"class": "form-input", "maxlength": 2}),
            "billing_same_as_shipping": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "billing_name": forms.TextInput(attrs={"class": "form-input"}),
            "billing_address_line1": forms.TextInput(attrs={"class": "form-input"}),
            "billing_city": forms.TextInput(attrs={"class": "form-input"}),
            "billing_state": forms.TextInput(attrs={"class": "form-input"}),
            "billing_postal_code": forms.TextInput(attrs={"class": "form-input"}),
            "billing_country": forms.TextInput(attrs={"class": "form-input", "maxlength": 2}),
            "shipping_method": forms.Select(attrs={"class": "form-select"}),
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "tax_code": forms.Select(attrs={"class": "form-select"}),
            "tax_jurisdiction": forms.TextInput(attrs={"class": "form-input"}),
            "tax_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "is_tax_exempt": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "tax_exemption_number": forms.TextInput(attrs={"class": "form-input"}),
            "subtotal_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "discount_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "shipping_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "total_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "payment_status": forms.Select(attrs={"class": "form-select"}),
            "expires_at": forms.DateTimeInput(
                attrs={"class": "form-input", "type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "billing_country" in self.fields:
            self.fields["billing_country"].required = False
        if self.tenant:
            self.fields["cart"].queryset = Cart.objects.filter(tenant=self.tenant)
            self.fields["customer"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="customer",
            ).distinct()
            self.fields["shipping_method"].queryset = ShippingMethodConfig.objects.filter(
                tenant=self.tenant
            )
            self.fields["payment_method"].queryset = PaymentMethodConfig.objects.filter(
                tenant=self.tenant
            )
            self.fields["tax_code"].queryset = TaxCode.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("billing_same_as_shipping"):
            if not cleaned.get("billing_country"):
                cleaned["billing_country"] = cleaned.get("shipping_country") or "US"
                self.instance.billing_country = cleaned["billing_country"]
            if not cleaned.get("billing_name"):
                cleaned["billing_name"] = cleaned.get("shipping_name", "")
                self.instance.billing_name = cleaned["billing_name"]
            if not cleaned.get("billing_address_line1"):
                cleaned["billing_address_line1"] = cleaned.get("shipping_address_line1", "")
                self.instance.billing_address_line1 = cleaned["billing_address_line1"]
            if not cleaned.get("billing_city"):
                cleaned["billing_city"] = cleaned.get("shipping_city", "")
                self.instance.billing_city = cleaned["billing_city"]
            if not cleaned.get("billing_state"):
                cleaned["billing_state"] = cleaned.get("shipping_state", "")
                self.instance.billing_state = cleaned["billing_state"]
            if not cleaned.get("billing_postal_code"):
                cleaned["billing_postal_code"] = cleaned.get("shipping_postal_code", "")
                self.instance.billing_postal_code = cleaned["billing_postal_code"]
        elif not cleaned.get("billing_country"):
            cleaned["billing_country"] = "US"
            self.instance.billing_country = "US"
        return cleaned

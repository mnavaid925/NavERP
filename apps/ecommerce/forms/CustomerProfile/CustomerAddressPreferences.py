from django import forms

from apps.core.models.Address import Address
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAddressPreferences import CustomerAddressPreference


class CustomerAddressPreferenceForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerAddressPreference
        fields = [
            "customer",
            "address",
            "label",
            "is_default_shipping",
            "is_default_billing",
            "recipient_name",
            "contact_phone",
            "delivery_instructions",
            "preferred_delivery_window",
            "requires_signature",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "address": forms.Select(attrs={"class": "form-select"}),
            "label": forms.TextInput(attrs={"class": "form-input", "placeholder": "Home, Office, Warehouse"}),
            "is_default_shipping": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "is_default_billing": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "recipient_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Attention / Recipient Name"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+1 555-0188"}),
            "delivery_instructions": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Gate code, leave behind porch pillar, etc."}
            ),
            "preferred_delivery_window": forms.Select(attrs={"class": "form-select"}),
            "requires_signature": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["address"].queryset = Address.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["customer", "address"])
        return cleaned

from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.scm.models.InventoryManagement.Locations import Location


class FulfillmentCenterForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FulfillmentCenter
        fields = [
            "name",
            "code",
            "center_type",
            "location",
            "priority",
            "is_active",
            "supports_pick_pack_ship",
            "supports_customer_pickup",
            "daily_cutoff_time",
            "address_line1",
            "city",
            "state",
            "postal_code",
            "country",
            "contact_email",
            "contact_phone",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. West Coast Distribution Hub"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. DC-WEST-01"}),
            "center_type": forms.Select(attrs={"class": "form-select"}),
            "location": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "daily_cutoff_time": forms.TimeInput(attrs={"class": "form-input", "type": "time"}),
            "address_line1": forms.TextInput(attrs={"class": "form-input", "placeholder": "Street Address"}),
            "city": forms.TextInput(attrs={"class": "form-input"}),
            "state": forms.TextInput(attrs={"class": "form-input"}),
            "postal_code": forms.TextInput(attrs={"class": "form-input"}),
            "country": forms.TextInput(attrs={"class": "form-input"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "operations@example.com"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+1 555-0199"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["priority"].help_text = "Priority for automated order routing and fulfillment (1 is highest priority)."
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["location"].queryset = Location.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["location"])
        return cleaned

from django import forms
from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistration


class MobileDeviceRegistrationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MobileDeviceRegistration
        exclude = ["tenant", "number", "created_at", "updated_at", "last_active_at", "badge_count"]
        widgets = {
            "customer_profile": forms.Select(attrs={"class": "form-select"}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "device_uuid": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"}),
            "device_platform": forms.Select(attrs={"class": "form-select"}),
            "device_model": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. iPhone 15 Pro, Pixel 8"}),
            "os_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. iOS 17.4.1"}),
            "app_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 1.2.0"}),
            "push_token": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "Device push token string"}),
            "push_provider": forms.Select(attrs={"class": "form-select"}),
            "location_permission": forms.Select(attrs={"class": "form-select"}),
            "last_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "40.712776"}),
            "last_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "-74.005974"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["customer_profile"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant)
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["customer_profile", "party"])
        return cleaned

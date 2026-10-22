"""Sales 8.16 — MobileDeviceSession forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import tenant_users
from apps.sales.models.MobileSales.MobileDeviceSessions import (
    PLATFORM_CHOICES,
    SYNC_STATUS_CHOICES,
    MobileDeviceSession,
)


class MobileDeviceSessionForm(TenantModelForm):
    class Meta:
        model = MobileDeviceSession
        fields = [
            "user",
            "device_uuid",
            "device_name",
            "platform",
            "app_version",
            "push_token",
            "is_active",
            "is_trusted",
            "last_sync_status",
        ]
        widgets = {
            "user": forms.Select(attrs={"class": "form-select"}),
            "device_uuid": forms.TextInput(attrs={"class": "form-input", "placeholder": "Device UUID or client token"}),
            "device_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. iPhone 15 Pro, Pixel 8"}),
            "platform": forms.Select(attrs={"class": "form-select"}),
            "app_version": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 3.2.0"}),
            "push_token": forms.TextInput(attrs={"class": "form-input", "placeholder": "APNs / FCM token string"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox h-4 w-4 text-primary"}),
            "is_trusted": forms.CheckboxInput(attrs={"class": "form-checkbox h-4 w-4 text-primary"}),
            "last_sync_status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["user"].queryset = tenant_users(self.tenant)


class MobileDeviceSessionFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Search device name, UUID, user..."}),
    )
    platform = forms.ChoiceField(
        choices=[("", "All Platforms")] + list(PLATFORM_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    last_sync_status = forms.ChoiceField(
        choices=[("", "All Sync Statuses")] + list(SYNC_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["user"].queryset = tenant_users(tenant)

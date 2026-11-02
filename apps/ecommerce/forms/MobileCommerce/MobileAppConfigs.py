import re
from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.MobileCommerce.MobileAppConfigs import MobileAppConfig


class MobileAppConfigForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MobileAppConfig
        exclude = ["tenant", "number", "created_at", "updated_at"]
        widgets = {
            "app_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "NavERP Mobile Store"}),
            "short_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "NavERP Store"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "theme_color": forms.TextInput(attrs={"class": "form-input h-10 w-28 p-1", "type": "color"}),
            "background_color": forms.TextInput(attrs={"class": "form-input h-10 w-28 p-1", "type": "color"}),
            "display_mode": forms.Select(attrs={"class": "form-select"}),
            "orientation": forms.Select(attrs={"class": "form-select"}),
            "start_url": forms.TextInput(attrs={"class": "form-input"}),
            "scope": forms.TextInput(attrs={"class": "form-input"}),
            "icon_192_url": forms.TextInput(attrs={"class": "form-input"}),
            "icon_512_url": forms.TextInput(attrs={"class": "form-input"}),
            "offline_cache_strategy": forms.Select(attrs={"class": "form-select"}),
            "offline_fallback_html": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
            "min_ios_version": forms.TextInput(attrs={"class": "form-input"}),
            "min_android_version": forms.TextInput(attrs={"class": "form-input"}),
            "apple_pay_merchant_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "merchant.com.example.store"}),
            "google_pay_gateway_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "example-gateway-id"}),
        }

    def clean_theme_color(self):
        val = self.cleaned_data.get("theme_color", "").strip()
        if val and not val.startswith("#"):
            val = "#" + val
        if val and not re.match(r"^#[0-9A-Fa-f]{6}$", val):
            raise forms.ValidationError("Theme color must be a valid 6-character hex color (e.g. #2563EB).")
        return val

    def clean_background_color(self):
        val = self.cleaned_data.get("background_color", "").strip()
        if val and not val.startswith("#"):
            val = "#" + val
        if val and not re.match(r"^#[0-9A-Fa-f]{6}$", val):
            raise forms.ValidationError("Background color must be a valid 6-character hex color (e.g. #FFFFFF).")
        return val

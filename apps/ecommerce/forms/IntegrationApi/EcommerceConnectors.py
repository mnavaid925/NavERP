import ipaddress
from urllib.parse import urlparse
from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.IntegrationApi.EcommerceConnectors import EcommerceConnector


class EcommerceConnectorForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = EcommerceConnector
        exclude = [
            "tenant",
            "number",
            "health_status",
            "last_health_check_at",
            "last_error_message",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. NetSuite ERP Production"}
            ),
            "category": forms.Select(attrs={"class": "form-select"}),
            "provider": forms.Select(attrs={"class": "form-select"}),
            "auth_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "base_url": forms.TextInput(
                attrs={
                    "class": "form-input font-mono",
                    "placeholder": "https://api.external-system.com/v1",
                }
            ),
            "api_version": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "v1"}
            ),
            "api_key": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "API key or client ID"}
            ),
            "api_secret": forms.PasswordInput(
                render_value=False,
                attrs={"class": "form-input font-mono", "placeholder": "••••••••••••••••"},
            ),
            "account_id": forms.TextInput(
                attrs={
                    "class": "form-input font-mono",
                    "placeholder": "External Account / Merchant ID",
                }
            ),
            "is_sandbox": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "timeout_seconds": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "30"}
            ),
            "rate_limit_per_minute": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "120"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Connector configuration notes, authentication instructions...",
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Connector name is required.")
        return name

    def clean_base_url(self):
        url = self.cleaned_data.get("base_url", "").strip()
        if not url:
            return url
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise forms.ValidationError("Base API endpoint URL must begin with https:// or http://.")
        hostname = parsed.hostname
        if not hostname:
            raise forms.ValidationError("Base API endpoint URL must include a valid host.")
        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            raise forms.ValidationError("Localhost and loopback endpoints are not allowed.")
        if hostname_lower.endswith(".internal") or hostname_lower.endswith(".local") or hostname_lower == "instance-data":
            raise forms.ValidationError("Internal and metadata endpoints are not allowed.")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise forms.ValidationError(f"Private, loopback, or metadata destination IP addresses ({ip}) are not allowed.")
        except ValueError:
            pass
        return url

    def clean_api_secret(self):
        val = self.cleaned_data.get("api_secret", "").strip()
        if not val and self.instance and self.instance.pk:
            return self.instance.api_secret
        return val

    def clean_timeout_seconds(self):
        val = self.cleaned_data.get("timeout_seconds")
        if val is not None:
            if val < 1:
                raise forms.ValidationError("Timeout must be at least 1 second.")
            if val > 300:
                raise forms.ValidationError("Timeout cannot exceed 300 seconds (5 minutes).")
        return val

    def clean_rate_limit_per_minute(self):
        val = self.cleaned_data.get("rate_limit_per_minute")
        if val is not None and val < 1:
            raise forms.ValidationError("Rate limit must be at least 1 request/minute.")
        return val

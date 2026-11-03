import ipaddress
import json
import secrets
from urllib.parse import urlparse
from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.IntegrationApi.WebhookSubscriptions import WebhookSubscription


class WebhookSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = WebhookSubscription
        exclude = [
            "tenant",
            "number",
            "consecutive_failures",
            "last_delivery_at",
            "last_status_code",
            "last_error_message",
            "total_delivered_count",
            "total_failed_count",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. External OMS Order Created Webhook",
                }
            ),
            "target_url": forms.URLInput(
                attrs={
                    "class": "form-input font-mono",
                    "placeholder": "https://api.external.com/webhooks/orders",
                }
            ),
            "event_topic": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "secret_key": forms.PasswordInput(
                render_value=False,
                attrs={
                    "class": "form-input font-mono",
                    "placeholder": "HMAC secret key (auto-generated if left blank)",
                },
            ),
            "payload_format": forms.Select(attrs={"class": "form-select"}),
            "custom_headers": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 3,
                    "placeholder": '{"X-Custom-Auth": "SecretToken123"}',
                }
            ),
            "max_consecutive_failures": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "5"}
            ),
            "is_verify_ssl": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Integration notes and destination system details...",
                }
            ),
        }

    def clean_target_url(self):
        url = self.cleaned_data.get("target_url", "").strip()
        if not url:
            raise forms.ValidationError("Target HTTPS endpoint URL is required.")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise forms.ValidationError("Target URL must begin with https:// or http://.")
        hostname = parsed.hostname
        if not hostname:
            raise forms.ValidationError("Target URL must include a valid host.")
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

    def clean_custom_headers(self):
        val = self.cleaned_data.get("custom_headers", "").strip()
        if val:
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, dict):
                    raise forms.ValidationError("Custom headers must be a JSON object / dictionary.")
            except json.JSONDecodeError as e:
                raise forms.ValidationError(f"Invalid JSON in custom headers: {e}")

            hop_by_hop = {
                "connection",
                "keep-alive",
                "proxy-authenticate",
                "proxy-authorization",
                "te",
                "trailer",
                "transfer-encoding",
                "upgrade",
                "host",
                "content-length",
            }
            for k, v in parsed.items():
                if not isinstance(k, str) or not isinstance(v, (str, int, float)):
                    raise forms.ValidationError(f"Header '{k}' key and value must be strings.")
                k_str = str(k).strip()
                v_str = str(v).strip()
                if "\r" in k_str or "\n" in k_str or "\r" in v_str or "\n" in v_str:
                    raise forms.ValidationError("CRLF carriage returns and newlines are not permitted in headers.")
                if k_str.lower() in hop_by_hop:
                    raise forms.ValidationError(f"Hop-by-hop header '{k_str}' cannot be overridden.")
        return val or "{}"

    def clean_secret_key(self):
        val = self.cleaned_data.get("secret_key", "").strip()
        if not val:
            if self.instance and self.instance.pk and self.instance.secret_key:
                return self.instance.secret_key
            val = f"whsec_{secrets.token_hex(24)}"
        return val

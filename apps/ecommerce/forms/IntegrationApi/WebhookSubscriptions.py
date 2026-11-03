import json
import secrets
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
        if not url.startswith("https://") and not url.startswith("http://"):
            raise forms.ValidationError("Target URL must begin with https:// or http://.")
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
        return val or "{}"

    def clean_secret_key(self):
        val = self.cleaned_data.get("secret_key", "").strip()
        if not val:
            if self.instance and self.instance.pk and self.instance.secret_key:
                return self.instance.secret_key
            val = f"whsec_{secrets.token_hex(24)}"
        return val

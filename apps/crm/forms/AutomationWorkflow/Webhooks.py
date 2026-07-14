"""CRM 1.10 Automation & Workflow Engine — Webhooks forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Webhook,
)


class WebhookForm(TenantModelForm):
    """1.10 Webhook endpoint. ``secret`` is WRITE-ONLY — rendered via PasswordInput(render_value=False)
    so the stored value is never shipped to the browser; blank on edit keeps the existing secret."""

    class Meta:
        model = Webhook
        fields = ["name", "target_url", "trigger_entity", "trigger_event", "secret",
                  "is_active", "headers", "description"]
        widgets = {"secret": forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
                   "headers": forms.Textarea(attrs={"rows": 3})}

    def clean_secret(self):
        secret = self.cleaned_data.get("secret", "")
        if not secret and self.instance and self.instance.pk:
            return self.instance.secret  # blank on edit → keep the stored secret (never round-tripped)
        return secret

    def clean_headers(self):
        # Validate the custom-headers JSON now so the (deferred) HTTP sender can't be fed a non-dict,
        # non-string, or CRLF-injected header value (header injection / serialization crash) — security-review.
        headers = self.cleaned_data.get("headers") or {}
        if not isinstance(headers, dict):
            raise forms.ValidationError("Headers must be a JSON object (key/value pairs).")
        for k, v in headers.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise forms.ValidationError("All header keys and values must be strings.")
            if any(ch in k or ch in v for ch in ("\r", "\n")):
                raise forms.ValidationError("Header keys/values must not contain newlines (CRLF).")
        return headers

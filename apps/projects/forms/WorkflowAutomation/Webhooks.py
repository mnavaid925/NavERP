"""Projects 7.17 — ProjectWebhookEndpoint forms."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.WorkflowAutomation.Webhooks import ProjectWebhookEndpoint


class ProjectWebhookEndpointForm(TenantModelForm):
    """Form for creating and updating ProjectWebhookEndpoint instances."""

    class Meta:
        model = ProjectWebhookEndpoint
        fields = [
            "project",
            "name",
            "target_url",
            "is_active",
            "event_types",
            "custom_headers",
        ]
        widgets = {
            "target_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://hooks.zapier.com/hooks/catch/..."}),
            "event_types": forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-sm"}),
            "custom_headers": forms.Textarea(attrs={"rows": 2, "class": "form-textarea font-mono text-sm"}),
        }

    def clean_event_types(self):
        val = self.cleaned_data.get("event_types")
        parsed = []
        if isinstance(val, str):
            val = val.strip()
            if not val:
                raise ValidationError("At least one event type must be selected.")
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, list):
                    raise ValidationError("Event types must be a JSON array of strings.")
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON for event types: {e}")
        elif isinstance(val, list):
            parsed = val

        if not parsed:
            raise ValidationError("At least one event type must be selected.")
        return parsed

    def clean_custom_headers(self):
        val = self.cleaned_data.get("custom_headers")
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return {}
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, dict):
                    raise ValidationError("Custom headers must be a JSON object (key-value dictionary).")
                return parsed
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON for custom headers: {e}")
        return val or {}

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned


class WebhookTestPingForm(forms.Form):
    """Form for dispatching a simulated or live test ping to a webhook endpoint."""

    event_type = forms.CharField(
        max_length=100,
        initial="test.ping",
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    custom_payload = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-sm", "placeholder": '{"test": true, "message": "Ping from NavERP"}'}),
        required=False,
    )

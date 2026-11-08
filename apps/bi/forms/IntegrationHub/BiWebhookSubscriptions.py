import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.IntegrationHub.BiWebhookSubscriptions import BiWebhookSubscription
from apps.core.forms import TenantModelForm


class BiWebhookSubscriptionForm(TenantUniqueMixin, TenantModelForm):
    event_types_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '[\n  "kpi.threshold_breached",\n  "report.execution_completed",\n  "anomaly.detected"\n]',
            }
        ),
        label="Subscribed Event Types (JSON Array)",
        help_text='JSON list of event identifiers: ["kpi.threshold_breached", "report.execution_completed", "anomaly.detected"]',
    )

    custom_headers_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "Authorization": "Bearer ext_token_...",\n  "X-Custom-Env": "production"\n}',
            }
        ),
        label="Custom HTTP Headers (JSON Object)",
        help_text="Optional headers dispatched with webhook POST requests",
    )

    class Meta:
        model = BiWebhookSubscription
        fields = [
            "name",
            "endpoint_url",
            "payload_format",
            "max_retries",
            "timeout_seconds",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Slack Incident Webhook"}
            ),
            "endpoint_url": forms.URLInput(
                attrs={"class": "form-input font-mono", "placeholder": "https://hooks.slack.com/services/..."}
            ),
            "payload_format": forms.Select(attrs={"class": "form-select"}),
            "max_retries": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10}),
            "timeout_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 60}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.event_types:
                self.fields["event_types_raw"].initial = json.dumps(
                    self.instance.event_types, indent=2
                )
            if self.instance.custom_headers:
                self.fields["custom_headers_raw"].initial = json.dumps(
                    self.instance.custom_headers, indent=2
                )

    def clean_event_types_raw(self):
        data = self.cleaned_data.get("event_types_raw", "").strip()
        if not data:
            return ["kpi.threshold_breached"]
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, list):
                raise ValidationError("Subscribed event types must be a JSON array of strings.")
            return [str(item).strip() for item in parsed if item]
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON syntax in event types: {err}")

    def clean_custom_headers_raw(self):
        data = self.cleaned_data.get("custom_headers_raw", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Custom headers must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON syntax in custom headers: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.event_types = self.cleaned_data.get("event_types_raw") or []
        instance.custom_headers = self.cleaned_data.get("custom_headers_raw") or {}
        if commit:
            instance.save()
        return instance

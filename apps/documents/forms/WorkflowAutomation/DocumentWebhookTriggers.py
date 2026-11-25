import json

from django import forms
from django.core.exceptions import ValidationError

from apps.core.models import ConnectorDefinition
from apps.documents.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTrigger,
)
from apps.documents.services.workflow_automation import (
    validate_dms_webhook_url,
    validate_flat_headers,
)


def _parse_json_dict(val, label):
    if val is None or val == "":
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON for {label}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValidationError(f"{label} must be a JSON object.")
        return parsed
    raise ValidationError(f"{label} must be a JSON object.")


class DocumentWebhookTriggerForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentWebhookTrigger
        fields = [
            "name",
            "description",
            "direction",
            "trigger_event",
            "process_definition",
            "connector_ref",
            "target_url",
            "http_method",
            "payload_format",
            "custom_headers",
            "payload_template_json",
            "filter_document_type",
            "retry_policy_max",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ERP Legal Contract Sync Callback"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "trigger_event": forms.Select(attrs={"class": "form-select"}),
            "process_definition": forms.Select(attrs={"class": "form-select"}),
            "connector_ref": forms.Select(attrs={"class": "form-select"}),
            "target_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://hooks.example.com/dms-events"}),
            "http_method": forms.Select(attrs={"class": "form-select"}),
            "payload_format": forms.Select(attrs={"class": "form-select"}),
            "custom_headers": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "payload_template_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "filter_document_type": forms.Select(attrs={"class": "form-select"}),
            "retry_policy_max": forms.NumberInput(attrs={"class": "form-input", "min": "0", "max": "20"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("code", "-version_number")
            self.fields["connector_ref"].queryset = ConnectorDefinition.objects.filter(
                tenant=self.tenant
            ).order_by("category", "name")
        else:
            self.fields["process_definition"].queryset = DocumentProcessDefinition.objects.none()
            self.fields["connector_ref"].queryset = ConnectorDefinition.objects.none()
        for opt in (
            "description",
            "process_definition",
            "connector_ref",
            "target_url",
            "custom_headers",
            "payload_template_json",
            "filter_document_type",
        ):
            self.fields[opt].required = False

    def clean_target_url(self):
        raw = (self.cleaned_data.get("target_url") or "").strip()
        if raw:
            return validate_dms_webhook_url(raw)
        return raw

    def clean_custom_headers(self):
        parsed = _parse_json_dict(self.cleaned_data.get("custom_headers"), "custom headers")
        return validate_flat_headers(parsed)

    def clean_payload_template_json(self):
        return _parse_json_dict(self.cleaned_data.get("payload_template_json"), "payload template")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["process_definition", "connector_ref"])
        direction = cleaned.get("direction")
        target_url = cleaned.get("target_url")
        if direction in ("outbound_webhook", "middleware_callback") and not target_url:
            self.add_error(
                "target_url",
                "Target URL is required for outbound webhooks and middleware callbacks.",
            )
        return cleaned


class WebhookTestPingForm(forms.Form):
    event_override = forms.CharField(
        required=False,
        max_length=60,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Optional event name override"}),
    )
    document = forms.ModelChoiceField(
        queryset=Document.objects.none(),
        required=False,
        empty_label="Sample Payload (No Document)",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["document"].queryset = Document.objects.filter(
                tenant=tenant
            ).order_by("-created_at", "title")
        else:
            self.fields["document"].queryset = Document.objects.none()

"""Projects 7.18 — ConnectorFieldMapping forms."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models.IntegrationApiHub.FieldMappings import ConnectorFieldMapping


class ConnectorFieldMappingForm(TenantUniqueMixin, TenantModelForm):
    """Form for creating and updating ConnectorFieldMapping instances."""

    class Meta:
        model = ConnectorFieldMapping
        fields = [
            "connector",
            "local_field",
            "remote_field",
            "direction",
            "transform",
            "value_map",
            "default_value",
            "is_key",
            "is_required",
            "notes",
        ]
        widgets = {
            "value_map": forms.Textarea(
                attrs={"rows": 3, "class": "form-textarea font-mono text-sm", "placeholder": '{"done": "completed"}'}
            ),
        }

    def clean_value_map(self):
        val = self.cleaned_data.get("value_map")
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return {}
            try:
                parsed = json.loads(val)
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON for value map: {e}")
            if not isinstance(parsed, dict):
                raise ValidationError("Value map must be a JSON object (key-value dictionary).")
            return parsed
        return val or {}

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["connector"])
        return cleaned

"""core — 0.13 forms (integration & API management)."""
import json

from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ApiCredential,
    ConnectorDefinition,
    MappingTemplate,
    RateLimitPolicy,
    SyncSchedule,
)


class ApiCredentialForm(TenantModelForm):
    """Issuing and editing a credential. The KEY is never a form field.

    A key is generated server-side and shown once (`ApiCredential.issue`); a form field for it would
    invite an operator to choose a guessable one, and an edit form that could set it would let a key be
    rotated without the old plaintext ever being invalidated deliberately.
    """

    class Meta:
        model = ApiCredential
        fields = ["label", "kind", "scopes", "is_active", "expires_at"]

    def clean_scopes(self):
        raw = (self.cleaned_data.get("scopes") or "").replace(",", " ")
        scopes = [s.strip() for s in raw.split() if s.strip()]
        for scope in scopes:
            if "." not in scope:
                raise forms.ValidationError(
                    "Scopes look like 'resource.action' (e.g. projects.read). Got: %s" % scope)
        return " ".join(scopes)


class RateLimitPolicyForm(TenantModelForm):
    class Meta:
        model = RateLimitPolicy
        fields = ["name", "credential", "max_requests", "window", "is_active", "notes"]

    def clean_max_requests(self):
        value = self.cleaned_data["max_requests"]
        if value < 1:
            raise forms.ValidationError("A limit of zero requests is not a limit.")
        return value


class ConnectorDefinitionForm(TenantModelForm):
    class Meta:
        model = ConnectorDefinition
        fields = ["name", "vendor", "category", "description", "engine_label", "is_installed",
                  "is_active", "notes"]

    def clean_engine_label(self):
        """Refuse a label naming no model — a catalogue entry whose engine cannot be resolved is a
        dead link, and a typo would make it silently unfollowable."""
        label = (self.cleaned_data.get("engine_label") or "").strip()
        if not label:
            return ""
        from django.apps import apps as django_apps
        try:
            app_label, model_name = label.split(".")
            django_apps.get_model(app_label, model_name)
        except (ValueError, LookupError):
            raise forms.ValidationError("No such model. Use app_label.Model.")
        return label


class MappingTemplateForm(TenantModelForm):
    """`mappings` is redeclared as a CharField because the model field is a JSONField, whose form
    field would reject a JSON document in `to_python` before any `clean_*` could run."""

    mappings = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 8}),
        help_text='JSON list, e.g. [{"from": "PO1", "to": "number"}]',
    )

    class Meta:
        model = MappingTemplate
        fields = ["name", "direction", "source_format", "target_label", "mappings", "is_active",
                  "notes"]

    def clean_mappings(self):
        raw = (self.cleaned_data.get("mappings") or "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise forms.ValidationError("That is not valid JSON: %s" % exc)
        if not isinstance(parsed, list):
            raise forms.ValidationError("Mappings must be a JSON list of rows.")
        for row in parsed:
            if not isinstance(row, dict):
                raise forms.ValidationError("Each mapping row must be a JSON object.")
        return parsed


class SyncScheduleForm(TenantModelForm):
    class Meta:
        model = SyncSchedule
        fields = ["name", "direction", "transport", "frequency", "entity_label",
                  "mapping_template", "connector", "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        # A schedule with a mapping template for the wrong direction is a mapping that will never
        # apply. Refused rather than saved as a schedule that silently does nothing.
        template = cleaned.get("mapping_template")
        direction = cleaned.get("direction")
        if template is not None and direction and template.direction != direction:
            self.add_error("mapping_template",
                           "That template is %s, but this schedule is %s."
                           % (template.get_direction_display(), direction))
        return cleaned

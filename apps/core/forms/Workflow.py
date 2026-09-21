"""core — 0.11 forms (workflow administration).

`BusinessRuleForm.condition` and `.action_payload` are redeclared as CharFields ON PURPOSE. The model
fields are JSONFields, and a `forms.JSONField` validates the input as JSON in `to_python` — BEFORE any
`clean_*` runs — which is the trap that made two 0.10 forms silently unusable. Here the operator is
editing JSON, so the JSON has to be the input; but the PARSING must happen in `clean`, where it can
produce a readable error instead of a raw form-field rejection.
"""
import json

from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ApprovalLimit,
    BusinessRule,
    BusinessRuleLog,
    SlaRule,
    WorkflowDefinition,
    WorkflowStep,
)


class WorkflowDefinitionForm(TenantModelForm):
    class Meta:
        model = WorkflowDefinition
        fields = ["name", "module_slug", "engine_label", "description", "owner_role", "is_active",
                  "target_hours"]

    def clean_engine_label(self):
        """A label that names no model is refused — the whole point of the registry is that it can be
        checked against something, and a typo would silently make the process unmonitorable."""
        label = (self.cleaned_data.get("engine_label") or "").strip()
        if not label:
            return ""
        from django.apps import apps as django_apps
        try:
            app_label, model_name = label.split(".")
            django_apps.get_model(app_label, model_name)
        except (ValueError, LookupError):
            raise forms.ValidationError("No such model. Use app_label.Model, e.g. crm.ApprovalRequest.")
        return label


class WorkflowStepForm(TenantModelForm):
    class Meta:
        model = WorkflowStep
        fields = ["definition", "sequence", "name", "approver_role", "is_parallel",
                  "threshold_amount", "notes"]

    def __init__(self, *args, definition=None, **kwargs):
        super().__init__(*args, **kwargs)
        if definition is not None:
            self.fields["definition"].initial = definition
            self.fields["definition"].disabled = True


class ApprovalLimitForm(TenantModelForm):
    class Meta:
        model = ApprovalLimit
        fields = ["module_slug", "role", "max_amount", "currency_code", "notes"]


class SlaRuleForm(TenantModelForm):
    class Meta:
        model = SlaRule
        fields = ["name", "module_slug", "engine_label", "hours", "action", "escalate_to_role",
                  "is_active", "notes"]


class BusinessRuleForm(TenantModelForm):
    condition = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 5}),
        help_text='JSON, e.g. {"all": [{"field": "amount", "op": "gt", "value": 10000}]}',
    )
    action_payload = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="JSON the action needs, e.g. {\"role_id\": 3} for notify_role.",
    )

    class Meta:
        model = BusinessRule
        fields = ["name", "module_slug", "trigger", "condition", "action", "action_payload",
                  "priority", "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Render the stored dict back as editable JSON.
        for name in ("condition", "action_payload"):
            if self.instance and self.instance.pk and not self.is_bound:
                self.fields[name].initial = json.dumps(getattr(self.instance, name) or {}, indent=2)

    def _parse(self, field_name):
        raw = (self.cleaned_data.get(field_name) or "").strip()
        if not raw:
            return {} if field_name == "condition" else {}
        try:
            parsed = json.loads(raw)
        except ValueError as exc:
            raise forms.ValidationError(f"{field_name} is not valid JSON: {exc}")
        if not isinstance(parsed, dict):
            raise forms.ValidationError(f"{field_name} must be a JSON object.")
        return parsed

    def clean(self):
        cleaned = super().clean()
        for name in ("condition", "action_payload"):
            if name in self.errors:
                continue
            try:
                cleaned[name] = self._parse(name)
            except forms.ValidationError as exc:
                self.add_error(name, exc)
        # An empty condition matches NOTHING by design, so a rule saved with one would never fire.
        # That is a footgun, not a default, so it is refused here.
        if not self.errors and not cleaned.get("condition"):
            self.add_error("condition", "A rule needs a condition — an empty one never matches.")
        return cleaned

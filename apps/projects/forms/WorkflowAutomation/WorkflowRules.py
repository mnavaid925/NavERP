"""Projects 7.17 — ProjectWorkflowRule forms."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.projects.forms._common import TenantModelForm, _reject_foreign
from apps.projects.models.WorkflowAutomation.WorkflowRules import ProjectWorkflowRule


class ProjectWorkflowRuleForm(TenantModelForm):
    """Form for creating and updating ProjectWorkflowRule instances."""

    class Meta:
        model = ProjectWorkflowRule
        fields = [
            "name",
            "description",
            "project",
            "is_active",
            "trigger_entity",
            "trigger_event",
            "trigger_field",
            "trigger_value",
            "conditions",
            "actions",
            "owner",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "trigger_entity": forms.Select(attrs={"class": "form-select"}),
            "trigger_event": forms.Select(attrs={"class": "form-select"}),
            "conditions": forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-sm"}),
            "actions": forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-sm"}),
        }

    def clean_conditions(self):
        val = self.cleaned_data.get("conditions")
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return []
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, list):
                    raise ValidationError("Conditions must be a JSON array of condition objects.")
                return parsed
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON for conditions: {e}")
        return val or []

    def clean_actions(self):
        val = self.cleaned_data.get("actions")
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return []
            try:
                parsed = json.loads(val)
                if not isinstance(parsed, list):
                    raise ValidationError("Actions must be a JSON array of action objects.")
                return parsed
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON for actions: {e}")
        return val or []

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project"])
        return cleaned


class WorkflowRuleTestForm(forms.Form):
    """Form to test simulated execution of a workflow rule against a target record."""

    target_id = forms.IntegerField(
        required=True,
        label="Test Record ID",
        widget=forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 42"}),
    )

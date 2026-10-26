"""Sales 8.17 — SalesProcessDefinition forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    SalesProcessDefinition,
    validate_process_conditions,
    validate_process_nodes,
)


class SalesProcessDefinitionForm(TenantModelForm):
    class Meta:
        model = SalesProcessDefinition
        fields = [
            "name", "description", "status", "target_entity", "trigger_event",
            "trigger_field", "trigger_value", "conditions", "nodes",
            "max_enrollments", "priority", "is_active",
        ]
        widgets = {
            "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
                "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
            "nodes": forms.Textarea(attrs={"class": "form-textarea", "rows": 7,
                "placeholder": '[{"seq": 1, "type": "notify", "params": {}}]'}),
        }

    def clean_conditions(self):
        return validate_process_conditions(self.cleaned_data.get("conditions") or [], is_catch_all=True)

    def clean_nodes(self):
        return validate_process_nodes(self.cleaned_data.get("nodes") or [])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("trigger_event") == "field_value":
            if not cleaned.get("trigger_field"):
                self.add_error("trigger_field", "A field-value trigger needs a trigger field.")
            if not cleaned.get("trigger_value"):
                self.add_error("trigger_value", "A field-value trigger needs a comparison value.")
        return cleaned

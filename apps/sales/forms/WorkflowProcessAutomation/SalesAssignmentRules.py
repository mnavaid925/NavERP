"""Sales 8.17 — SalesAssignmentRule forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.crm.models import Territory
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign, tenant_users
from apps.sales.models.WorkflowProcessAutomation.SalesAssignmentRules import SalesAssignmentRule
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    validate_process_conditions,
)


class SalesAssignmentRuleForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit form for the assignment-rule register.

    System/derived fields are structurally unrenderable (L22): ``tenant``, auto ``number``,
    ``cursor``, ``last_assigned_owner``, ``last_assigned_at``, ``created_at``, ``updated_at``
    are omitted from ``Meta.fields``. The form path is authoritative for the mode guards
    (L49-addendum) — the model ``clean()`` repeats them for non-form writers.
    """

    class Meta:
        model = SalesAssignmentRule
        fields = [
            "name", "target_entity", "match_mode", "conditions", "is_catch_all",
            "assignment_mode", "default_owner", "eligible_owners", "fallback_owner",
            "territory", "max_open_records", "escalate_after_hours", "escalate_to",
            "priority", "is_active",
        ]
        widgets = {
            "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
                "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["default_owner"].queryset = tenant_users(self.tenant)
            self.fields["fallback_owner"].queryset = tenant_users(self.tenant)
            self.fields["escalate_to"].queryset = tenant_users(self.tenant)
            self.fields["eligible_owners"].queryset = tenant_users(self.tenant)
            self.fields["territory"].queryset = Territory.objects.filter(tenant=self.tenant, is_active=True)

    def clean_conditions(self):
        return validate_process_conditions(
            self.cleaned_data.get("conditions") or [],
            self.cleaned_data.get("is_catch_all"),
        )

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["default_owner", "fallback_owner", "escalate_to", "territory"])
        mode = cleaned.get("assignment_mode")
        if mode == "fixed_owner" and not cleaned.get("default_owner"):
            self.add_error("default_owner", "A fixed-owner rule needs a default owner.")
        if mode == "round_robin" and not cleaned.get("eligible_owners"):
            self.add_error("eligible_owners", "A round-robin rule needs eligible owners.")
        if mode == "load_balanced" and not cleaned.get("eligible_owners"):
            self.add_error("eligible_owners", "A load-balanced rule needs eligible owners.")
        if mode == "territory_manager":
            territory = cleaned.get("territory")
            if not territory:
                self.add_error("territory", "A territory-manager rule needs a territory.")
            elif not territory.manager_id:
                self.add_error("territory", "The selected territory has no manager.")
        if mode == "escalate_manager":
            if not cleaned.get("escalate_to"):
                self.add_error("escalate_to", "An escalation rule needs an escalation target.")
            if not cleaned.get("escalate_after_hours"):
                self.add_error("escalate_after_hours", "An escalation rule needs an escalation window.")
        return cleaned

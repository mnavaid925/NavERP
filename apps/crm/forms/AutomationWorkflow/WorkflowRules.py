"""CRM 1.10 Automation & Workflow Engine — WorkflowRules forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    WorkflowRule,
)


class WorkflowRuleForm(TenantModelForm):
    class Meta:
        model = WorkflowRule
        fields = ["name", "is_active", "trigger_entity", "trigger_event", "trigger_field",
                  "trigger_value", "conditions", "actions", "delay_value", "delay_unit", "owner"]
        widgets = {"conditions": forms.Textarea(attrs={"rows": 4}),
                   "actions": forms.Textarea(attrs={"rows": 4})}

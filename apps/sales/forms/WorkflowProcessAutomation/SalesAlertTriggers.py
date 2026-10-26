"""Sales 8.17 — SalesAlertTrigger forms."""
from django import forms

from apps.accounts.models import Role
from apps.core.forms import TenantModelForm
from apps.core.models.Notification import NotificationRule
from apps.sales.forms._common import _reject_foreign, tenant_users
from apps.sales.models.WorkflowProcessAutomation.SalesAlertTriggers import SalesAlertTrigger
from apps.sales.models.WorkflowProcessAutomation.SalesProcessDefinitions import (
    validate_process_conditions,
)


class SalesAlertTriggerForm(TenantModelForm):
    """Create/edit form for the notification & alert engine triggers.

    System/derived fields are structurally unrenderable (L22): ``tenant``, auto ``number``,
    ``last_evaluated_at``, ``last_fired_at``, ``fire_count``, ``created_at``, ``updated_at``
    are omitted from ``Meta.fields``. The form path is authoritative for the audience guards;
    the model ``clean()`` repeats them for non-form writers.
    """

    class Meta:
        model = SalesAlertTrigger
        fields = [
            "name", "alert_type", "target_entity", "conditions", "inactivity_days",
            "severity", "audience_kind", "audience_role", "audience_users",
            "notification_rule", "cooldown_hours", "priority", "is_active",
        ]
        widgets = {
            "conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 5,
                "placeholder": '[{"field": "status", "operator": "eq", "value": "open"}]'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["audience_role"].queryset = Role.objects.filter(tenant=self.tenant)
            self.fields["audience_users"].queryset = tenant_users(self.tenant)
            self.fields["notification_rule"].queryset = NotificationRule.objects.filter(tenant=self.tenant)

    def clean_conditions(self):
        return validate_process_conditions(
            self.cleaned_data.get("conditions") or [],
            is_catch_all=True,
        )

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["audience_role", "notification_rule"])
        audience_kind = cleaned.get("audience_kind")
        if audience_kind == "role" and not cleaned.get("audience_role"):
            self.add_error("audience_role", "A role-audience trigger needs a role.")
        if audience_kind == "user" and not cleaned.get("audience_users"):
            self.add_error("audience_users", "A user-audience trigger needs at least one recipient.")
        if cleaned.get("alert_type") in {"deal_inactivity", "sla_breach"} and not cleaned.get("inactivity_days"):
            self.add_error("inactivity_days", "An inactivity trigger needs a day window.")
        return cleaned

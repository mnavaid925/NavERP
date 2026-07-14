"""CRM 1.5 Activity & Communication Management — Tasks forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmTask,
)


class CrmTaskForm(TenantModelForm):
    class Meta:
        model = CrmTask
        # recurrence_parent + completed_at are system-set (L20/L22) → excluded.
        fields = ["subject", "type", "priority", "status", "due_date", "owner", "party",
                  "related_opportunity", "related_case", "description",
                  "recurrence", "recurrence_interval", "recurrence_until"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Both have model defaults (a simple to-do needs no recurrence choice) — optional on the
        # form; clean_* below coerces a blank submission back to the model default.
        self.fields["recurrence"].required = False
        self.fields["recurrence_interval"].required = False

    def clean_recurrence(self):
        return self.cleaned_data.get("recurrence") or "none"

    def clean_recurrence_interval(self):
        return self.cleaned_data.get("recurrence_interval") or 1

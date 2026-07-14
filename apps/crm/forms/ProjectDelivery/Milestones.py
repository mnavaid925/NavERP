"""CRM 1.8 Project & Delivery Management — Milestones forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmMilestone,
)


class CrmMilestoneForm(TenantModelForm):
    class Meta:
        model = CrmMilestone
        fields = ["project", "title", "kind", "status", "assignee", "start_date",
                  "due_date", "order", "parent", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A milestone can't be its own parent.
        if self.instance and self.instance.pk:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)

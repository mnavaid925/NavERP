"""HRM 3.27 Communication Hub — HelpdeskTickets forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    HelpdeskTicket,
)


class HelpdeskTicketForm(TenantModelForm):
    # status / assignee / sla_policy / all timestamps / CSAT are workflow-owned (set by the action
    # views); employee (the requester) is resolved server-side by _ss_child_create.
    class Meta:
        model = HelpdeskTicket
        fields = ["subject", "description", "category", "priority"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "category" in self.fields:
            self.fields["category"].queryset = (
                HelpdeskCategory.objects.filter(tenant=self.tenant, is_active=True).order_by("department", "name"))

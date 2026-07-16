"""HRM 3.27 Communication Hub — Grievances forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Grievance,
    HRPolicy,
)


class GrievanceForm(TenantModelForm):
    # employee (complainant) is resolved server-side by the create view; status/investigator/resolution/
    # resolved_at are workflow-set by the admin actions.
    class Meta:
        model = Grievance
        fields = ["category", "severity", "subject", "description", "is_anonymous", "related_policy"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "related_policy" in self.fields:
            self.fields["related_policy"].queryset = (
                HRPolicy.objects.filter(tenant=self.tenant, status="published").order_by("title"))

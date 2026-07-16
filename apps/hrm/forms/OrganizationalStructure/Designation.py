"""HRM 3.2 Organizational Structure — Designation forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    JobGrade,
)


class DesignationForm(TenantModelForm):
    class Meta:
        model = Designation
        fields = ["name", "job_grade", "department", "min_salary", "mid_salary", "max_salary",
                  "grade", "budgeted_headcount", "is_active", "description", "requirements"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offer only active grades for selection (base form already scopes to tenant).
        if self.tenant is not None:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True)
                .order_by("level_order", "name"))
            self.fields["department"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))

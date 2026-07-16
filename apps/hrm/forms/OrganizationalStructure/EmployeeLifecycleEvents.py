"""HRM 3.2 Organizational Structure — EmployeeLifecycleEvents forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeLifecycleEvent,
    EmployeeProfile,
)


class EmployeeLifecycleEventForm(TenantModelForm):
    # SECURITY: `initiated_by` is excluded — stamped from request.user in the create view, never
    # settable via the form.
    class Meta:
        model = EmployeeLifecycleEvent
        fields = ["employee", "event_type", "effective_date", "reason",
                  "from_designation", "to_designation", "from_department", "to_department",
                  "from_location", "to_location", "from_job_title", "to_job_title",
                  "from_salary", "to_salary", "from_manager", "to_manager",
                  "from_employee_type", "to_employee_type", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            employees = (EmployeeProfile.objects.filter(tenant=self.tenant)
                         .select_related("party").order_by("party__name"))
            for fld in ("employee", "from_manager", "to_manager"):
                self.fields[fld].queryset = employees
            designations = (Designation.objects.filter(tenant=self.tenant, is_active=True)
                            .order_by("name"))
            for fld in ("from_designation", "to_designation"):
                self.fields[fld].queryset = designations
            departments = OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name")
            for fld in ("from_department", "to_department"):
                self.fields[fld].queryset = departments

"""CRM 1.8 Project & Delivery Management — Timesheets forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Timesheet,
)


class TimesheetForm(TenantModelForm):
    class Meta:
        model = Timesheet
        # WARNING: status + approved_by are system-managed and excluded from the form. status
        # advances ONLY through the timesheet_submit (owner) / timesheet_approve|reject
        # (@tenant_admin_required) action views — accepting it from POST would let a member
        # self-approve their own timesheet (mirrors the Expense workflow).
        fields = ["project", "milestone", "employee", "client", "date", "hours",
                  "description", "is_billable"]

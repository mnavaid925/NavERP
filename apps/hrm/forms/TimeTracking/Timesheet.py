"""HRM 3.11 Time Tracking — Timesheet forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Timesheet,
)


# ----------------------------------------------------------------------- 3.11 Time Tracking
class TimesheetForm(TenantModelForm):
    # status/approver/approved_at/decision_note/rejected_reason + derived total/billable hours are
    # workflow-set in the view, never on the form (no self-approve via crafted POST).
    class Meta:
        model = Timesheet
        fields = ["employee", "period_start", "period_end"]

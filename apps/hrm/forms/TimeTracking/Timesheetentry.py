"""HRM 3.11 Time Tracking — Timesheetentry forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TimesheetEntry,
)


class TimesheetEntryForm(TenantModelForm):
    # `timesheet` is set from the view/URL context (inline child on the timesheet hub), not the form.
    class Meta:
        model = TimesheetEntry
        fields = ["date", "project", "task_description", "hours", "is_billable", "billable_rate", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

"""HRM 3.11 Time Tracking — Overtimerequest forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OvertimeRequest,
)


class OvertimeRequestForm(TenantModelForm):
    class Meta:
        model = OvertimeRequest
        fields = ["employee", "timesheet", "date", "hours_claimed", "multiplier", "payout_method", "reason"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

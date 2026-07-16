"""HRM 3.18 Goal Setting — Goalcheckin forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    GoalCheckIn,
)


class GoalCheckInForm(TenantModelForm):
    # key_result + created_by are set from the URL/request in the view; number is auto-assigned.
    class Meta:
        model = GoalCheckIn
        fields = ["checkin_date", "value_at_checkin", "confidence", "is_milestone_event", "comment"]
        widgets = {
            "checkin_date": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

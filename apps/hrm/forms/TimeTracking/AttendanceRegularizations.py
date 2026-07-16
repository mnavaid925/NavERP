"""HRM 3.11 Time Tracking — AttendanceRegularizations forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRegularization,
)


class AttendanceRegularizationForm(TenantModelForm):
    class Meta:
        model = AttendanceRegularization
        # status / approver / approved_at / decision_note are workflow-set in the view, not on the form.
        fields = ["employee", "attendance_record", "date", "reason_type",
                  "requested_check_in", "requested_check_out", "reason"]
        widgets = {
            "requested_check_in": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "requested_check_out": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "reason": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

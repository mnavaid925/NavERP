"""HRM 3.11 Time Tracking — Shifts forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Shift,
)


class ShiftForm(TenantModelForm):
    class Meta:
        model = Shift
        fields = ["name", "start_time", "end_time", "grace_minutes", "is_default", "is_active"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
        }

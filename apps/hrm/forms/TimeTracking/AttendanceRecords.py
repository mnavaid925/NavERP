"""HRM 3.11 Time Tracking — AttendanceRecords forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
)


class AttendanceRecordForm(TenantModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ["employee", "date", "check_in", "check_out", "shift", "status", "source",
                  "latitude", "longitude", "geofence", "notes"]
        widgets = {
            "check_in": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "check_out": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
        }

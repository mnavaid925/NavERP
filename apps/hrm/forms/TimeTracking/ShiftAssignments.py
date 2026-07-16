"""HRM 3.11 Time Tracking — ShiftAssignments forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ShiftAssignment,
)


class ShiftAssignmentForm(TenantModelForm):
    class Meta:
        model = ShiftAssignment
        fields = ["employee", "shift", "effective_from", "effective_to"]

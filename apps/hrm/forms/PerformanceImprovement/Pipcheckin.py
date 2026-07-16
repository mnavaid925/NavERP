"""HRM 3.21 Performance Improvement — Pipcheckin forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PIPCheckIn,
)


class PIPCheckInForm(TenantModelForm):
    # `pip` is set from the URL in the nested create view; `number`/`completed_at` are auto/workflow.
    class Meta:
        model = PIPCheckIn
        fields = ["checkin_date", "progress_rating", "progress_notes"]
        widgets = {
            "checkin_date": forms.DateInput(attrs={"type": "date"}),
            "progress_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

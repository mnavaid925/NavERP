"""HRM 3.19 Performance Review — Calibrations forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PerformanceReview,
)


class CalibrationForm(TenantModelForm):
    # A narrow, privileged form — the ONLY write path to calibrated_rating (the general edit form
    # must never expose it). tenant= kwarg kept for signature consistency (no FK to scope).
    class Meta:
        model = PerformanceReview
        fields = ["calibrated_rating", "potential_rating", "calibration_notes"]
        widgets = {
            "calibration_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

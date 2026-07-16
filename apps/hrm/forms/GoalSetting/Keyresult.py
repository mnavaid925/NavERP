"""HRM 3.18 Goal Setting — Keyresult forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    KeyResult,
)


class KeyResultForm(TenantModelForm):
    # objective is set from the URL in the nested create view; progress/health are derived.
    class Meta:
        model = KeyResult
        fields = ["title", "metric_type", "start_value", "target_value", "current_value",
                  "is_milestone_event", "unit", "weight", "status"]

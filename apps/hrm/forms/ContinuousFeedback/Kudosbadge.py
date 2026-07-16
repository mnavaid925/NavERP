"""HRM 3.20 Continuous Feedback — Kudosbadge forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    KudosBadge,
)


# ------------------------------------------------------------------------- 3.20 Continuous Feedback
class KudosBadgeForm(TenantModelForm):
    # Small catalog (like GoalPeriodForm) — no in-module FK to scope; tenant= kept for signature parity.
    class Meta:
        model = KudosBadge
        fields = ["name", "description", "icon", "color", "linked_value", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

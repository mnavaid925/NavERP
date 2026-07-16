"""HRM 3.27 Communication Hub — FlexibleWorkArrangements forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    FlexibleWorkArrangement,
)


class FlexibleWorkArrangementForm(TenantModelForm):
    # status/approver/approved_at/decision_note are workflow-set; employee is resolved by _ss_child_create.
    class Meta:
        model = FlexibleWorkArrangement
        fields = ["arrangement_type", "start_date", "end_date", "days_per_week_remote", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before the start date.")
        atype = cleaned.get("arrangement_type")
        days = cleaned.get("days_per_week_remote")
        if atype in ("remote", "hybrid"):
            if days is None:
                self.add_error("days_per_week_remote", "Required for a remote or hybrid arrangement.")
            elif not (1 <= days <= 5):
                self.add_error("days_per_week_remote", "Enter a value between 1 and 5.")
        elif days is not None:
            self.add_error("days_per_week_remote",
                           "Only applies to a remote or hybrid arrangement — leave it blank.")
        return cleaned

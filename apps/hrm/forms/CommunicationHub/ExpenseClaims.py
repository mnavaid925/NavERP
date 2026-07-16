"""HRM 3.27 Communication Hub — ExpenseClaims forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseClaim,
)


class ExpenseClaimForm(TenantModelForm):
    # status / approvers / timestamps / payment are workflow-owned (set by the action views);
    # employee is resolved server-side by _ss_child_create/_ss_child_edit, not on the form.
    class Meta:
        model = ExpenseClaim
        fields = ["title", "purpose", "period_start", "period_end", "currency"]
        widgets = {"purpose": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before period start.")
        return cleaned

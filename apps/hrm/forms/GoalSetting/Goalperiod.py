"""HRM 3.18 Goal Setting — Goalperiod forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    GoalPeriod,
)


# ------------------------------------------------------------------------- 3.18 Goal Setting
class GoalPeriodForm(TenantModelForm):
    # GoalPeriod has no in-module FKs; the tenant= kwarg is kept for signature consistency.
    # `status` is workflow-owned (create starts "draft"; only the @tenant_admin_required
    # activate/close actions change it) — NOT a directly-editable field, else a regular user
    # could POST status=active/closed and bypass the admin gate.
    class Meta:
        model = GoalPeriod
        fields = ["name", "period_type", "start_date", "end_date", "description"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

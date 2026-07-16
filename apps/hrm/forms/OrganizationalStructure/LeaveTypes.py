"""HRM 3.2 Organizational Structure — LeaveTypes forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveType,
)


class LeaveTypeForm(TenantModelForm):
    class Meta:
        model = LeaveType
        fields = ["name", "code", "is_paid", "accrual_rule", "accrual_days", "max_balance",
                  "max_carry_forward", "encashable", "is_active"]

"""HRM 3.14 Payroll Processing — Payrollcycle forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PayrollCycle,
)


# ----------------------------------------------------------------------- 3.14 Payroll Processing
class PayrollCycleForm(TenantModelForm):
    # status / submitted_by / approved_by / accounting_payroll_run are workflow-owned (set by the
    # generate/submit/approve/reject/lock actions), never form fields.
    class Meta:
        model = PayrollCycle
        fields = ["period_start", "period_end", "pay_date", "cycle_type", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

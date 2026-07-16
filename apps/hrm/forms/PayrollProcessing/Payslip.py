"""HRM 3.14 Payroll Processing — Payslip forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Payslip,
)


class PayslipForm(TenantModelForm):
    # Only the manual inputs — gross/deductions/net/lop_amount are derived by recompute() (called by the
    # view after save); on_hold/hold_reason go through the dedicated hold/release actions.
    class Meta:
        model = Payslip
        fields = ["days_worked", "lop_days", "arrears_amount", "bonus_amount"]

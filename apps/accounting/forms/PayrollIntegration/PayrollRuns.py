"""Accounting 2.8 Payroll Integration — PayrollRuns forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    PayrollRun,
)


class PayrollRunForm(TenantModelForm):
    class Meta:
        model = PayrollRun
        # net_pay is derived in save(); status/journal_entry owned by the post action.
        fields = ["period_start", "period_end", "pay_date", "headcount", "gross_wages",
                  "employee_tax", "employer_tax", "benefits", "deductions"]

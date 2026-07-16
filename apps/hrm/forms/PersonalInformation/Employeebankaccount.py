"""HRM 3.25 Personal Information — Employeebankaccount forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeBankAccount,
)


class EmployeeBankAccountForm(TenantModelForm):
    class Meta:
        model = EmployeeBankAccount
        fields = ["bank_name", "account_holder_name", "account_number", "routing_number",
                  "account_type", "is_salary_account", "split_percentage", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

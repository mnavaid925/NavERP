"""Accounting 2.13 Budgeting & Planning — Budgets forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Budget,
)


class BudgetForm(TenantModelForm):
    class Meta:
        model = Budget
        fields = ["name", "fiscal_period", "version", "status", "notes"]

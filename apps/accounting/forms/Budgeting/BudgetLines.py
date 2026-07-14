"""Accounting 2.13 Budgeting & Planning — BudgetLines forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    BudgetLine,
)


class BudgetLineForm(TenantModelForm):
    class Meta:
        model = BudgetLine
        fields = ["budget", "gl_account", "org_unit", "amount"]

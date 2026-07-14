"""Accounting 2.9 Project/Job Costing — Projects forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Project,
)


class ProjectForm(TenantModelForm):
    class Meta:
        model = Project
        fields = ["name", "client", "org_unit", "billing_method", "budget_amount", "start_date",
                  "end_date", "status", "notes"]

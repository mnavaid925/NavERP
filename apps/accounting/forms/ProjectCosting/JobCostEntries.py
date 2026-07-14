"""Accounting 2.9 Project/Job Costing — JobCostEntries forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    JobCostEntry,
)


class JobCostEntryForm(TenantModelForm):
    class Meta:
        model = JobCostEntry
        fields = ["project", "entry_date", "kind", "amount", "gl_account", "description"]

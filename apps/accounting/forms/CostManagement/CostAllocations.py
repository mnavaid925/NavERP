"""Accounting 2.7 Inventory & Cost Management — CostAllocations forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    CostAllocation,
)


class CostAllocationForm(TenantModelForm):
    class Meta:
        model = CostAllocation
        fields = ["description", "allocation_date", "amount", "source_account", "target_account",
                  "target_org_unit"]

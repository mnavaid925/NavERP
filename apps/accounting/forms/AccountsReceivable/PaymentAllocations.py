"""Accounting 2.4 Accounts Receivable — PaymentAllocations forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    PaymentAllocation,
)


class PaymentAllocationForm(TenantModelForm):
    class Meta:
        model = PaymentAllocation
        fields = ["payment", "invoice", "bill", "allocated_amount", "discount_taken"]

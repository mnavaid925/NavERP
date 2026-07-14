"""Accounting 2.11 Tax — TaxReturns forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    TaxReturn,
)


class TaxReturnForm(TenantModelForm):
    class Meta:
        model = TaxReturn
        fields = ["tax_code", "period_start", "period_end", "taxable_amount", "tax_due", "status",
                  "filed_date", "due_date", "notes"]

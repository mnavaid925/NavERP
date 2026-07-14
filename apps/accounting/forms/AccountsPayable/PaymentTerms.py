"""Accounting 2.3 Accounts Payable — PaymentTerms forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    PaymentTerm,
)


class PaymentTermForm(TenantModelForm):
    class Meta:
        model = PaymentTerm
        fields = ["name", "days_due", "discount_pct", "discount_days", "is_active"]

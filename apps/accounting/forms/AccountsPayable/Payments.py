"""Accounting 2.3 Accounts Payable — Payments forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    Payment,
)


class PaymentForm(TenantModelForm):
    class Meta:
        model = Payment
        fields = ["direction", "party", "bank_account", "payment_method", "payment_date",
                  "amount", "currency", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)

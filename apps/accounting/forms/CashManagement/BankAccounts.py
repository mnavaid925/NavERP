"""Accounting 2.5 Cash Management — BankAccounts forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    BankAccount,
)


class BankAccountForm(TenantModelForm):
    class Meta:
        model = BankAccount
        fields = ["name", "account_number_last4", "bank_name", "currency", "gl_account",
                  "opening_balance", "opening_balance_date", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)

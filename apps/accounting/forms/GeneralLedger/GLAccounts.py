"""Accounting 2.2 General Ledger — GLAccounts forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    GLAccount,
)


class GLAccountForm(TenantModelForm):
    class Meta:
        model = GLAccount
        fields = ["code", "name", "account_type", "parent", "is_active", "description"]

"""Accounting 2.10 Multi-Entity & Consolidation — IntercompanyTransactions forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    IntercompanyTransaction,
)


class IntercompanyTransactionForm(TenantModelForm):
    class Meta:
        model = IntercompanyTransaction
        # `eliminated` (the consolidation-elimination marker) is NOT user-editable here — it is
        # toggled only via the @tenant_admin_required `intercompany_toggle_eliminated` action so a
        # member can't silently change the consolidated picture (security review).
        fields = ["description", "transaction_date", "amount", "from_org_unit", "to_org_unit",
                  "due_from_account", "due_to_account"]

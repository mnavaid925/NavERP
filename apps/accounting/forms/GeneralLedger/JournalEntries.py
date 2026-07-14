"""Accounting 2.2 General Ledger — JournalEntries forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.forms._common import _active_currencies
from apps.accounting.models import (
    JournalEntry,
    JournalLine,
)


class JournalEntryForm(TenantModelForm):
    class Meta:
        model = JournalEntry
        # status/posted_at/created_by/approved_by/reversal_of are controlled by the action views.
        fields = ["entry_type", "entry_date", "description", "reference", "fiscal_period"]


class JournalLineForm(TenantModelForm):
    class Meta:
        model = JournalLine
        fields = ["gl_account", "debit", "credit", "description", "party", "org_unit",
                  "currency", "amount_foreign", "exchange_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


# Inline line-item formsets (create + edit share these). ``form_kwargs={'tenant': ...}`` is passed
# by the view so each child form scopes its own FK dropdowns to the tenant.
JournalLineFormSet = inlineformset_factory(
    JournalEntry, JournalLine, form=JournalLineForm, extra=2, can_delete=True,
)

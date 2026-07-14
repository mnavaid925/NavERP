"""Accounting 2.5 Cash Management — Reconciliation forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    JournalLine,
    ReconciliationMatch,
)


class ReconciliationMatchForm(TenantModelForm):
    class Meta:
        model = ReconciliationMatch
        fields = ["bank_transaction", "payment", "journal_line", "is_confirmed"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `journal_line` has no direct tenant field (tenant lives on its parent entry), so the
        # TenantModelForm auto-scoper misses it — scope it explicitly to block cross-tenant IDOR
        # via a crafted POST (security review H3).
        if self.tenant is not None:
            self.fields["journal_line"].queryset = JournalLine.objects.filter(entry__tenant=self.tenant)

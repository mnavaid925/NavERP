"""Accounting 2.2 General Ledger — AccountLedger views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    GLAccount,
    JournalLine,
    ZERO,
)


@login_required
def gl_account_ledger(request, account_pk):
    account = get_object_or_404(GLAccount, pk=account_pk, tenant=request.tenant)
    lines = (JournalLine.objects.filter(gl_account=account, entry__status="posted")
             .select_related("entry").order_by("entry__entry_date", "id"))
    running = ZERO
    rows = []
    for ln in lines:
        delta = (ln.debit - ln.credit) if account.normal_balance == "debit" else (ln.credit - ln.debit)
        running += delta
        rows.append({"line": ln, "running": running})
    return render(request, "accounting/ledger/gl_account_ledger.html", {"obj": account, "rows": rows})

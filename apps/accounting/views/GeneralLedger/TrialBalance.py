"""Accounting 2.2 General Ledger — TrialBalance views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    JournalLine,
    ZERO,
)


@login_required
def trial_balance(request):
    tenant = request.tenant
    rows, total_debit, total_credit = [], ZERO, ZERO
    if tenant is not None:
        agg = (
            JournalLine.objects.filter(entry__tenant=tenant, entry__status="posted")
            .values("gl_account", "gl_account__code", "gl_account__name", "gl_account__normal_balance")
            .annotate(debit=Sum("debit"), credit=Sum("credit"))
            .order_by("gl_account__code")
        )
        for r in agg:
            debit, credit = r["debit"] or ZERO, r["credit"] or ZERO
            balance = debit - credit
            rows.append({
                "code": r["gl_account__code"], "name": r["gl_account__name"],
                "debit": debit, "credit": credit,
                "balance_debit": balance if balance > 0 else ZERO,
                "balance_credit": -balance if balance < 0 else ZERO,
            })
            total_debit += debit
            total_credit += credit
    return render(request, "accounting/ledger/trial_balance.html", {
        "rows": rows, "total_debit": total_debit, "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    })

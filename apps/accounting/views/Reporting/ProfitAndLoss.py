"""Accounting 2.12 Reporting & Compliance — ProfitAndLoss views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _account_balances
from apps.accounting.models import (
    ZERO,
)


@login_required
def profit_and_loss(request):
    income = expense = []
    total_income = total_expense = ZERO
    if request.tenant is not None:
        rows = _account_balances(request.tenant)
        income = [r for r in rows if r["type"] == "income"]
        expense = [r for r in rows if r["type"] == "expense"]
        total_income = sum((r["balance"] for r in income), ZERO)
        total_expense = sum((r["balance"] for r in expense), ZERO)
    return render(request, "accounting/reports/profit_and_loss.html", {
        "income": income, "expense": expense, "total_income": total_income,
        "total_expense": total_expense, "net_income": total_income - total_expense,
    })

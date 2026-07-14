"""Accounting 2.12 Reporting & Compliance — BalanceSheet views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _account_balances
from apps.accounting.models import (
    ZERO,
)


@login_required
def balance_sheet(request):
    assets = liabilities = equity = []
    total_assets = total_liabilities = total_equity = net_income = ZERO
    if request.tenant is not None:
        rows = _account_balances(request.tenant)
        assets = [r for r in rows if r["type"] == "asset"]
        liabilities = [r for r in rows if r["type"] == "liability"]
        equity = [r for r in rows if r["type"] == "equity"]
        income = sum((r["balance"] for r in rows if r["type"] == "income"), ZERO)
        expense = sum((r["balance"] for r in rows if r["type"] == "expense"), ZERO)
        net_income = income - expense
        total_assets = sum((r["balance"] for r in assets), ZERO)
        total_liabilities = sum((r["balance"] for r in liabilities), ZERO)
        total_equity = sum((r["balance"] for r in equity), ZERO)
    return render(request, "accounting/reports/balance_sheet.html", {
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "total_assets": total_assets, "total_liabilities": total_liabilities,
        "total_equity": total_equity, "net_income": net_income,
        "total_liab_equity": total_liabilities + total_equity + net_income,
        "balanced": total_assets == (total_liabilities + total_equity + net_income),
    })

"""Accounting 2.13 Budgeting & Planning — BudgetVariance views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _account_balances
from apps.accounting.models import (
    Budget,
    ZERO,
)


@login_required
@require_POST
def budget_delete(request, pk):
    return crud_delete(request, model=Budget, pk=pk, success_url="accounting:budget_list")


@login_required
def budget_variance(request):
    """Budget vs. posted actuals for a chosen budget (?budget=pk, default = latest)."""
    if request.tenant is None:
        return render(request, "accounting/budget/variance.html",
                      {"budgets": [], "selected": None, "rows": [], "total_budget": ZERO,
                       "total_actual": ZERO, "total_variance": ZERO})
    # Evaluate the budget list once (was re-queried for the dropdown + pk lookup + fallback — perf I5).
    budgets = list(Budget.objects.filter(tenant=request.tenant).select_related("fiscal_period"))
    bp = request.GET.get("budget", "")
    selected = next((b for b in budgets if str(b.pk) == bp), None) if bp.isdigit() else None
    if selected is None and budgets:
        selected = budgets[0]
    rows, total_budget, total_actual = [], ZERO, ZERO
    if selected is not None:
        balances = {r["code"]: r["balance"] for r in _account_balances(request.tenant)}
        for line in selected.lines.select_related("gl_account", "org_unit"):
            actual = balances.get(line.gl_account.code, ZERO)
            rows.append({"line": line, "actual": actual, "variance": (line.amount or ZERO) - actual})
            total_budget += line.amount or ZERO
            total_actual += actual
    return render(request, "accounting/budget/variance.html", {
        "budgets": budgets, "selected": selected, "rows": rows,
        "total_budget": total_budget, "total_actual": total_actual,
        "total_variance": total_budget - total_actual,
    })

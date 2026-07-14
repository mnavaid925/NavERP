"""Accounting 2.13 Budgeting & Planning — Budgets views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Budget,
    ZERO,
)
from apps.accounting.forms import (
    BudgetForm,
)


# =============================================================== 2.13 Budgeting & Planning
@login_required
def budget_list(request):
    return crud_list(
        request, Budget.objects.filter(tenant=request.tenant).select_related("fiscal_period"),
        "accounting/budget/list.html",
        search_fields=["number", "name"],
        filters=[("status", "status", False), ("version", "version", False)],
        extra_context={"status_choices": Budget.STATUS_CHOICES, "version_choices": Budget.VERSION_CHOICES},
    )


@login_required
def budget_create(request):
    return crud_create(request, form_class=BudgetForm, template="accounting/budget/form.html",
                       success_url="accounting:budget_list")


@login_required
def budget_detail(request, pk):
    obj = get_object_or_404(Budget.objects.select_related("fiscal_period"), pk=pk, tenant=request.tenant)
    # Lines are fully fetched, so sum them in Python instead of a second aggregate query (perf I4).
    lines = list(obj.lines.select_related("gl_account", "org_unit"))
    total = sum((ln.amount or ZERO for ln in lines), ZERO)
    return render(request, "accounting/budget/detail.html", {"obj": obj, "lines": lines, "total": total})


@login_required
def budget_edit(request, pk):
    return crud_edit(request, model=Budget, pk=pk, form_class=BudgetForm,
                     template="accounting/budget/form.html", success_url="accounting:budget_list")

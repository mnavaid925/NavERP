"""Accounting 2.13 Budgeting & Planning — BudgetLines views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    BudgetLine,
)
from apps.accounting.forms import (
    BudgetLineForm,
)


# --------------------------------------------------------------- Budget lines
@login_required
def budget_line_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before adding budget lines.")
        return redirect("accounting:budget_list")
    initial = {}
    bp = request.GET.get("budget", "")
    if bp.isdigit():
        initial["budget"] = bp
    if request.method == "POST":
        form = BudgetLineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Budget line added.")
            return redirect("accounting:budget_detail", pk=obj.budget_id)
    else:
        form = BudgetLineForm(tenant=request.tenant, initial=initial)
    return render(request, "accounting/budget/line/form.html", {"form": form, "is_edit": False})


@login_required
def budget_line_edit(request, pk):
    line = get_object_or_404(BudgetLine, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = BudgetLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Budget line updated.")
            return redirect("accounting:budget_detail", pk=obj.budget_id)
    else:
        form = BudgetLineForm(instance=line, tenant=request.tenant)
    return render(request, "accounting/budget/line/form.html", {"form": form, "obj": line, "is_edit": True})


@login_required
@require_POST
def budget_line_delete(request, pk):
    line = get_object_or_404(BudgetLine, pk=pk, tenant=request.tenant)
    budget_pk = line.budget_id
    line.delete()
    write_audit_log(request.user, line, "delete")
    messages.success(request, "Budget line removed.")
    return redirect("accounting:budget_detail", pk=budget_pk)

"""HRM 3.34 Expense Management — Expensecategory views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseCategory,
    ExpenseClaimLine,
)
from apps.hrm.forms import (
    ExpenseCategoryForm,
)


@login_required
def expensecategory_list(request):
    return crud_list(request,
                     # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
                     ExpenseCategory.objects.filter(tenant=request.tenant)
                     .annotate(line_total=Count("claim_lines")).order_by("name"),
                     "hrm/expenses/expensecategory/list.html", search_fields=["name", "code"],
                     filters=[("is_active", "is_active", False)])


@tenant_admin_required
def expensecategory_create(request):
    return crud_create(request, form_class=ExpenseCategoryForm,
                       template="hrm/expenses/expensecategory/form.html",
                       success_url="hrm:expensecategory_list")


@login_required
def expensecategory_detail(request, pk):
    return crud_detail(request, model=ExpenseCategory, pk=pk,
                       template="hrm/expenses/expensecategory/detail.html",
                       extra_context={"line_count": ExpenseClaimLine.objects.filter(
                           tenant=request.tenant, category_id=pk).count()})


@tenant_admin_required
def expensecategory_edit(request, pk):
    return crud_edit(request, model=ExpenseCategory, pk=pk, form_class=ExpenseCategoryForm,
                     template="hrm/expenses/expensecategory/form.html",
                     success_url="hrm:expensecategory_list")


@tenant_admin_required
@require_POST
def expensecategory_delete(request, pk):
    if ExpenseClaimLine.objects.filter(tenant=request.tenant, category_id=pk).exists():
        messages.error(request, "This category is used by existing expense lines and can't be deleted.")
        return redirect("hrm:expensecategory_detail", pk=pk)
    return crud_delete(request, model=ExpenseCategory, pk=pk, success_url="hrm:expensecategory_list")

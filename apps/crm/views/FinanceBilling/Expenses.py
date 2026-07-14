"""CRM 1.7 Finance & Billing Management — Expenses views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Expense,
)
from apps.crm.forms import (
    ExpenseForm,
)


# ------------------------------------------------------------ 1.7 Expenses
@login_required
def expense_list(request):
    return crud_list(
        request,
        Expense.objects.filter(tenant=request.tenant).select_related(
            "opportunity", "project", "submitted_by", "approved_by"),
        "crm/finance/expense/list.html",
        search_fields=["number", "description", "opportunity__name"],
        filters=[("status", "status", False), ("category", "category", False)],
        extra_context={"status_choices": Expense.STATUS_CHOICES,
                       "category_choices": Expense.CATEGORY_CHOICES},
    )


@login_required
def expense_create(request):
    # Custom create (not crud_create) so submitted_by is system-set to the current user and
    # status stays the model default "draft" — neither is accepted from the form.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ExpenseForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.submitted_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("crm:expense_list")
    else:
        form = ExpenseForm(tenant=request.tenant)
    return render(request, "crm/finance/expense/form.html", {"form": form, "is_edit": False})


@login_required
def expense_detail(request, pk):
    obj = get_object_or_404(
        Expense.objects.select_related("opportunity", "project", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/finance/expense/detail.html", {"obj": obj})


@login_required
def expense_edit(request, pk):
    return crud_edit(request, model=Expense, pk=pk, form_class=ExpenseForm,
                     template="crm/finance/expense/form.html", success_url="crm:expense_list")


@login_required
@require_POST
def expense_delete(request, pk):
    return crud_delete(request, model=Expense, pk=pk, success_url="crm:expense_list")


@login_required
@require_POST
def expense_submit(request, pk):
    # The owner submits their own draft expense for approval (draft -> submitted).
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Expense {obj.number} submitted for approval.")
    return redirect("crm:expense_detail", pk=obj.pk)


@tenant_admin_required  # approving is a privileged action — a manager/admin, not the submitter
@require_POST
def expense_approve(request, pk):
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    obj.status = "approved"
    obj.approved_by = request.user
    obj.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Expense {obj.number} approved.")
    return redirect("crm:expense_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged action — a manager/admin, not the submitter
@require_POST
def expense_reject(request, pk):
    obj = get_object_or_404(Expense, pk=pk, tenant=request.tenant)
    obj.status = "rejected"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Expense {obj.number} rejected.")
    return redirect("crm:expense_detail", pk=obj.pk)

"""HRM 3.34 Expense Management — Expenseclaimline views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseClaim,
    ExpenseClaimLine,
)
from apps.hrm.forms import (
    ExpenseClaimLineForm,
)
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child


@login_required
@require_POST
def expenseclaimline_add(request, claim_pk):
    claim = get_object_or_404(ExpenseClaim, pk=claim_pk, tenant=request.tenant)
    if not _can_manage_own_child(request, claim):
        raise PermissionDenied("This claim belongs to another employee.")
    if claim.status != "draft":
        messages.error(request, "Lines can only be added while the claim is a draft.")
        return redirect("hrm:expenseclaim_detail", pk=claim.pk)
    form = ExpenseClaimLineForm(request.POST, request.FILES,
                               instance=ExpenseClaimLine(tenant=request.tenant, claim=claim),
                               tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, claim, "update", {"action": "line_add"})
        messages.success(request, "Expense line added.")
    else:
        messages.error(request, "; ".join(f"{fld}: {errs[0]}" for fld, errs in form.errors.items()))
    return redirect("hrm:expenseclaim_detail", pk=claim.pk)


@login_required
def expenseclaimline_edit(request, pk):
    line = get_object_or_404(ExpenseClaimLine.objects.select_related("claim"), pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, line.claim):
        raise PermissionDenied("This claim belongs to another employee.")
    if line.claim.status != "draft":
        messages.error(request, "Lines can only be edited while the claim is a draft.")
        return redirect("hrm:expenseclaim_detail", pk=line.claim_id)
    if request.method == "POST":
        form = ExpenseClaimLineForm(request.POST, request.FILES, instance=line, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, line.claim, "update", {"action": "line_edit"})
            messages.success(request, "Expense line updated.")
            return redirect("hrm:expenseclaim_detail", pk=line.claim_id)
    else:
        form = ExpenseClaimLineForm(instance=line, tenant=request.tenant)
    return render(request, "hrm/expenses/expenseclaimline/form.html",
                  {"form": form, "obj": line, "claim": line.claim, "is_edit": True})


@login_required
@require_POST
def expenseclaimline_delete(request, pk):
    line = get_object_or_404(ExpenseClaimLine.objects.select_related("claim"), pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, line.claim):
        raise PermissionDenied("This claim belongs to another employee.")
    if line.claim.status != "draft":
        messages.error(request, "Lines can only be removed while the claim is a draft.")
        return redirect("hrm:expenseclaim_detail", pk=line.claim_id)
    claim_pk = line.claim_id
    line.delete()
    write_audit_log(request.user, line.claim, "update", {"action": "line_delete"})
    messages.success(request, "Expense line removed.")
    return redirect("hrm:expenseclaim_detail", pk=claim_pk)

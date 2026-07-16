"""HRM 3.34 Expense Management — Expenseclaim views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.ExpenseManagement._helpers import _get_own_claim
from apps.hrm.models import (
    ExpenseClaim,
)
from apps.hrm.forms import (
    ExpenseClaimForm,
    ExpenseClaimLineForm,
)
from apps.hrm.views.ExpenseManagement._helpers import _get_own_claim
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child, _ss_child_create, _ss_child_delete, _ss_child_edit, _ss_employees, _ss_scope
from apps.hrm.views.RequestManagement._helpers import _is_own_hr_request


@login_required
def expenseclaim_list(request):
    is_admin = _is_admin(request.user)
    qs = _ss_scope(request, ExpenseClaim.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "currency").prefetch_related("lines__category"))
    return crud_list(request, qs, "hrm/expenses/expenseclaim/list.html",
                     search_fields=["number", "title"],
                     filters=[("status", "status", False), ("employee", "employee_id", is_admin)],
                     extra_context={"status_choices": ExpenseClaim.STATUS_CHOICES, "is_admin": is_admin,
                                    "employees": _ss_employees(request) if is_admin else None})


@login_required
def expenseclaim_create(request):
    return _ss_child_create(request, ExpenseClaimForm, "hrm/expenses/expenseclaim/form.html",
                            "hrm:expenseclaim_list")


@login_required
def expenseclaim_detail(request, pk):
    obj = get_object_or_404(
        ExpenseClaim.objects.select_related("employee__party", "currency", "manager_approver",
                                            "finance_approver").prefetch_related("lines__category"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This claim belongs to another employee.")
    return render(request, "hrm/expenses/expenseclaim/detail.html", {
        "obj": obj, "lines": obj.lines.all(), "is_admin": _is_admin(request.user),
        "is_own": _is_own_hr_request(request, obj),
        "line_form": ExpenseClaimLineForm(tenant=request.tenant) if obj.status == "draft" else None,
        "payment_method_choices": ExpenseClaim.PAYMENT_METHOD_CHOICES})


@login_required
def expenseclaim_edit(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This claim belongs to another employee.")
    if obj.status != "draft":
        messages.error(request, "Only a draft claim can be edited.")
        return redirect("hrm:expenseclaim_detail", pk=obj.pk)
    return _ss_child_edit(request, ExpenseClaim, pk, ExpenseClaimForm,
                          "hrm/expenses/expenseclaim/form.html", "hrm:expenseclaim_detail")


@login_required
@require_POST
def expenseclaim_delete(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This claim belongs to another employee.")
    if obj.status != "draft":
        messages.error(request, "Only a draft claim can be deleted.")
        return redirect("hrm:expenseclaim_detail", pk=obj.pk)
    return _ss_child_delete(request, ExpenseClaim, pk, "hrm:expenseclaim_list")


@login_required
@require_POST
def expenseclaim_submit(request, pk):
    obj = _get_own_claim(request, pk)
    if obj.status != "draft":
        messages.error(request, "Only a draft claim can be submitted.")
    elif obj.line_count == 0:
        messages.error(request, "Add at least one expense line before submitting.")
    else:
        obj.status = "submitted"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, "Claim submitted for approval.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def expenseclaim_manager_approve(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You cannot approve your own claim.")
    elif obj.status != "submitted":
        messages.error(request, "Only a submitted claim can receive manager approval.")
    else:
        obj.status = "manager_approved"
        obj.manager_approver = request.user
        obj.manager_approved_at = timezone.now()
        obj.save(update_fields=["status", "manager_approver", "manager_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "manager_approve"})
        messages.success(request, "Claim manager-approved.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def expenseclaim_approve(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You cannot approve your own claim.")
    elif obj.status != "manager_approved":
        messages.error(request, "Only a manager-approved claim can receive finance approval.")
    else:
        obj.status = "approved"
        obj.finance_approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "finance_approver", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, "Claim approved by finance.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def expenseclaim_reject(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    reason = (request.POST.get("rejection_reason") or "").strip()
    if _is_own_hr_request(request, obj):
        messages.error(request, "You cannot reject your own claim.")
    elif not reason:
        messages.error(request, "A reason is required to reject a claim.")
    elif obj.status not in ("submitted", "manager_approved"):
        messages.error(request, "Only a submitted or manager-approved claim can be rejected.")
    else:
        fields = ["status", "rejection_reason", "updated_at"]
        if obj.status == "submitted":
            obj.manager_approver = request.user
            obj.manager_approved_at = timezone.now()
            fields += ["manager_approver", "manager_approved_at"]
        else:
            obj.finance_approver = request.user
            obj.approved_at = timezone.now()
            fields += ["finance_approver", "approved_at"]
        obj.status = "rejected"
        obj.rejection_reason = reason[:2000]
        obj.save(update_fields=fields)
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Claim rejected.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)


@login_required
@require_POST
def expenseclaim_cancel(request, pk):
    obj = _get_own_claim(request, pk)
    if obj.status not in ExpenseClaim.OPEN_STATUSES:
        messages.error(request, "Only a draft or submitted claim can be cancelled.")
    else:
        obj.status = "cancelled"
        note = (request.POST.get("rejection_reason") or "").strip()
        obj.rejection_reason = note[:2000]
        obj.save(update_fields=["status", "rejection_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, "Claim cancelled.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def expenseclaim_reimburse(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    method = (request.POST.get("payment_method") or "").strip()
    if _is_own_hr_request(request, obj):
        messages.error(request, "You cannot mark your own claim as reimbursed.")
    elif obj.status != "approved":
        messages.error(request, "Only an approved claim can be marked reimbursed.")
    elif method not in dict(ExpenseClaim.PAYMENT_METHOD_CHOICES):
        messages.error(request, "Select a valid payment method.")
    else:
        obj.status = "reimbursed"
        obj.payment_method = method
        obj.payment_reference = (request.POST.get("payment_reference") or "").strip()[:100]
        obj.reimbursed_at = timezone.now()
        obj.save(update_fields=["status", "payment_method", "payment_reference", "reimbursed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reimburse"})
        messages.success(request, "Claim marked reimbursed.")
    return redirect("hrm:expenseclaim_detail", pk=obj.pk)

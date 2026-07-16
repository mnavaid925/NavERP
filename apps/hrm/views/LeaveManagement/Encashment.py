"""HRM 3.10 Leave Management — Encashment views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    LeaveAllocation,
    LeaveEncashment,
    LeaveType,
)
from apps.hrm.forms import (
    LeaveEncashmentForm,
)


# ============================================================ Leave Encashment (3.10)
@login_required
def leaveencashment_list(request):
    return crud_list(
        request,
        LeaveEncashment.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type", "approver"),
        "hrm/leave/encashment/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveEncashment.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant, encashable=True).order_by("name")},
    )


@login_required
def leaveencashment_create(request):
    return crud_create(request, form_class=LeaveEncashmentForm,
                       template="hrm/leave/encashment/form.html", success_url="hrm:leaveencashment_list")


@login_required
def leaveencashment_detail(request, pk):
    obj = get_object_or_404(
        LeaveEncashment.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type, year=obj.year).first()
    return render(request, "hrm/leave/encashment/detail.html", {"obj": obj, "allocation": allocation})


@login_required
def leaveencashment_edit(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status not in LeaveEncashment.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending encashment can be edited.")
        return redirect("hrm:leaveencashment_detail", pk=obj.pk)
    return crud_edit(request, model=LeaveEncashment, pk=pk, form_class=LeaveEncashmentForm,
                     template="hrm/leave/encashment/form.html", success_url="hrm:leaveencashment_list")


@login_required
@require_POST
def leaveencashment_delete(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status not in LeaveEncashment.OPEN_STATUSES:
        messages.error(request, "A decided encashment cannot be deleted — cancel it instead.")
        return redirect("hrm:leaveencashment_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Encashment deleted.")
    return redirect("hrm:leaveencashment_list")


@login_required
@require_POST
def leaveencashment_submit(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Encashment {obj.number} submitted for approval.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # approving an encashment consumes leave balance — privileged manager/admin action
@require_POST
def leaveencashment_approve(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        alloc = (LeaveAllocation.objects
                 .filter(tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type, year=obj.year)
                 .first())
        available = alloc.balance if alloc else Decimal("0")
        # Re-check balance at approval time — a pending request could exceed the balance if another
        # encashment was approved after it was raised.
        if obj.days > available:
            messages.error(request, f"Cannot approve — only {available} day(s) available to encash.")
            return redirect("hrm:leaveencashment_detail", pk=obj.pk)
        with transaction.atomic():
            obj.status = "approved"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
            obj.save(update_fields=["status", "approver", "approved_at", "decision_note", "updated_at"])
            # Encashment consumes leave: record it in encashed_days (NOT by shrinking allocated_days,
            # which the accrual engine recomputes — that would silently restore the cashed-out days).
            if alloc:
                alloc.encashed_days = (alloc.encashed_days or Decimal("0")) + obj.days
                alloc.save(update_fields=["encashed_days", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "days_consumed": str(obj.days)})
        messages.success(request, f"Encashment {obj.number} approved ({obj.days} day(s) consumed).")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged manager/admin action
@require_POST
def leaveencashment_reject(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Encashment {obj.number} rejected.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # recording the payout is a privileged finance/admin action
@require_POST
def leaveencashment_mark_paid(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "approved":
        obj.status = "paid"
        obj.paid_on = timezone.localdate()
        obj.payment_reference = request.POST.get("payment_reference", "").strip()[:100]
        obj.save(update_fields=["status", "paid_on", "payment_reference", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_paid", "reference": obj.payment_reference})
        messages.success(request, f"Encashment {obj.number} marked paid.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@login_required
@require_POST
def leaveencashment_cancel(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    # Cancellable only before a decision — an approved one already consumed balance (final).
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Encashment {obj.number} cancelled.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)

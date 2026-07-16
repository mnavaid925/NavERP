"""HRM 3.10 Leave Management — Request views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
)
from apps.hrm.forms import (
    LeaveRequestForm,
)


# ============================================================ Leave Requests (3.10)
@login_required
def leaverequest_list(request):
    return crud_list(
        request,
        LeaveRequest.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type", "approver"),
        "hrm/leave/request/list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveRequest.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def leaverequest_create(request):
    return crud_create(request, form_class=LeaveRequestForm, template="hrm/leave/request/form.html",
                       success_url="hrm:leaverequest_list")


@login_required
def leaverequest_detail(request, pk):
    obj = get_object_or_404(
        LeaveRequest.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
        year=obj.start_date.year).first()
    return render(request, "hrm/leave/request/detail.html", {
        "obj": obj,
        "allocation": allocation,
    })


@login_required
def leaverequest_edit(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    # Only an open (draft/pending) request is editable — a decided one is locked.
    if obj.status not in LeaveRequest.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending leave request can be edited.")
        return redirect("hrm:leaverequest_detail", pk=obj.pk)
    return crud_edit(request, model=LeaveRequest, pk=pk, form_class=LeaveRequestForm,
                     template="hrm/leave/request/form.html", success_url="hrm:leaverequest_list")


@login_required
@require_POST
def leaverequest_delete(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "A decided leave request cannot be deleted — cancel it instead.")
        return redirect("hrm:leaverequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Leave request deleted.")
    return redirect("hrm:leaverequest_list")


@login_required
@require_POST
def leaverequest_submit(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Leave request {obj.number} submitted for approval.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@tenant_admin_required  # approving leave is a privileged manager/admin action, not self-service
@require_POST
def leaverequest_approve(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        # Approval mutates two models (the request + its attendance rows); wrap them so an
        # interrupted approve can't leave the request approved while attendance stays unsynced.
        # Mirrors the inverse leaverequest_cancel, which already runs under transaction.atomic().
        with transaction.atomic():
            obj.status = "approved"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
            # Reflect the approval on any existing attendance rows in the leave window.
            touched = AttendanceRecord.objects.filter(
                tenant=request.tenant, employee=obj.employee,
                date__gte=obj.start_date, date__lte=obj.end_date).update(status="on_leave")
        write_audit_log(request.user, obj, "update", {
            "action": "approve",
            "attendance_set_on_leave": f"{obj.start_date}..{obj.end_date} ({touched} rows)"})
        messages.success(request, f"Leave request {obj.number} approved.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@tenant_admin_required  # rejecting leave is a privileged manager/admin action
@require_POST
def leaverequest_reject(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.rejected_reason = request.POST.get("rejected_reason", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "rejected_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Leave request {obj.number} rejected.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@login_required
@require_POST
def leaverequest_cancel(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending", "approved"):
        was_approved = obj.status == "approved"
        with transaction.atomic():
            obj.status = "cancelled"
            obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()[:2000]
            obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
            # Undo the on-leave marking that approval applied, so attendance reports stay correct
            # (inverse of leaverequest_approve). Only touch rows we put into on_leave.
            reverted = 0
            if was_approved:
                reverted = AttendanceRecord.objects.filter(
                    tenant=request.tenant, employee=obj.employee, status="on_leave",
                    date__gte=obj.start_date, date__lte=obj.end_date).update(status="present")
        write_audit_log(request.user, obj, "update", {
            "action": "cancel", "attendance_reverted_rows": reverted})
        messages.success(request, f"Leave request {obj.number} cancelled.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)

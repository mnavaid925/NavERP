"""HRM 3.9 Attendance Management — Regularization views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    AttendanceRecord,
    AttendanceRegularization,
    EmployeeProfile,
)
from apps.hrm.forms import (
    AttendanceRegularizationForm,
)


# ============================================================ Attendance Regularization (3.9)
@login_required
def attendanceregularization_list(request):
    return crud_list(
        request,
        AttendanceRegularization.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "attendance_record", "approver"),
        "hrm/attendance/regularization/list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("reason_type", "reason_type", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": AttendanceRegularization.STATUS_CHOICES,
                       "reason_type_choices": AttendanceRegularization.REASON_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def attendanceregularization_create(request):
    return crud_create(request, form_class=AttendanceRegularizationForm,
                       template="hrm/attendance/regularization/form.html",
                       success_url="hrm:attendanceregularization_list")


@login_required
def attendanceregularization_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRegularization.objects.select_related("employee__party", "attendance_record", "approver"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/regularization/detail.html", {"obj": obj})


@login_required
def attendanceregularization_edit(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    # Only an open (draft/pending) request is editable — a decided one is locked.
    if obj.status not in AttendanceRegularization.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending regularization can be edited.")
        return redirect("hrm:attendanceregularization_detail", pk=obj.pk)
    return crud_edit(request, model=AttendanceRegularization, pk=pk, form_class=AttendanceRegularizationForm,
                     template="hrm/attendance/regularization/form.html",
                     success_url="hrm:attendanceregularization_list")


@login_required
@require_POST
def attendanceregularization_delete(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "A decided regularization cannot be deleted — cancel it instead.")
        return redirect("hrm:attendanceregularization_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Regularization deleted.")
    return redirect("hrm:attendanceregularization_list")


@login_required
@require_POST
def attendanceregularization_submit(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Regularization {obj.number} submitted for approval.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@tenant_admin_required  # approving a regularization rewrites an attendance punch — privileged action
@require_POST
def attendanceregularization_approve(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        with transaction.atomic():
            # Resolve the punch to correct: the explicitly linked one, else an existing row for
            # (employee, date), else materialise a fresh regularized punch (handles a request raised
            # before any attendance row existed — the workflow always produces a corrected record).
            rec = obj.attendance_record
            if rec is None:
                rec = (AttendanceRecord.objects
                       .filter(tenant=request.tenant, employee=obj.employee, date=obj.date)
                       .first())
                if rec is None:
                    rec = AttendanceRecord(tenant=request.tenant, employee=obj.employee, date=obj.date)
            if obj.requested_check_in is not None:
                rec.check_in = obj.requested_check_in
            if obj.requested_check_out is not None:
                rec.check_out = obj.requested_check_out
            rec.status = "regularized"
            rec.source = "manual"
            rec.save()  # save() recomputes hours_worked + assigns an ATT- number when newly created
            obj.status = "approved"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
            obj.attendance_record = rec  # link back so the audit trail records which punch was fixed
            obj.save(update_fields=["status", "approver", "approved_at", "decision_note",
                                    "attendance_record", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "applied": f"record {rec.number} → regularized"})
        messages.success(request, f"Regularization {obj.number} approved (record {rec.number} → regularized).")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged manager/admin action
@require_POST
def attendanceregularization_reject(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Regularization {obj.number} rejected.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@login_required
@require_POST
def attendanceregularization_cancel(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    # Cancellable only before a decision — an approved one already rewrote the punch (final).
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Regularization {obj.number} cancelled.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)

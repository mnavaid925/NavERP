"""HRM 3.11 Time Tracking — Overtimerequest views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    OvertimeRequest,
)
from apps.hrm.forms import (
    OvertimeRequestForm,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


# ============================================================ Overtime Requests (3.11)
@login_required
def overtimerequest_list(request):
    qs = (OvertimeRequest.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "approver", "timesheet"))
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return crud_list(
        request, qs, "hrm/timetracking/overtimerequest/list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("payout_method", "payout_method", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": OvertimeRequest.STATUS_CHOICES,
                       "payout_choices": OvertimeRequest.PAYOUT_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def overtimerequest_create(request):
    return crud_create(request, form_class=OvertimeRequestForm,
                       template="hrm/timetracking/overtimerequest/form.html", success_url="hrm:overtimerequest_list")


@login_required
def overtimerequest_detail(request, pk):
    obj = get_object_or_404(
        OvertimeRequest.objects.select_related("employee__party", "approver", "timesheet"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/timetracking/overtimerequest/detail.html", {"obj": obj})


@login_required
def overtimerequest_edit(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in OvertimeRequest.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending overtime request can be edited.")
        return redirect("hrm:overtimerequest_detail", pk=obj.pk)
    return crud_edit(request, model=OvertimeRequest, pk=pk, form_class=OvertimeRequestForm,
                     template="hrm/timetracking/overtimerequest/form.html", success_url="hrm:overtimerequest_list")


@login_required
@require_POST
def overtimerequest_delete(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in OvertimeRequest.OPEN_STATUSES:
        messages.error(request, "A decided overtime request cannot be deleted — cancel it instead.")
        return redirect("hrm:overtimerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Overtime request deleted.")
    return redirect("hrm:overtimerequest_list")


@login_required
@require_POST
def overtimerequest_submit(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Overtime request {obj.number} submitted for approval.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@tenant_admin_required  # approving overtime is a privileged manager/admin action
@require_POST
def overtimerequest_approve(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "approved_at", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"Overtime request {obj.number} approved.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@tenant_admin_required  # rejecting overtime is a privileged manager/admin action
@require_POST
def overtimerequest_reject(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Overtime request {obj.number} rejected.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@login_required
@require_POST
def overtimerequest_cancel(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Overtime request {obj.number} cancelled.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)

"""HRM 3.12 Holiday Management — Floatingholidayelection views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    FloatingHolidayElection,
    PublicHoliday,
)
from apps.hrm.forms import (
    FloatingHolidayElectionForm,
)


# ============================================================ Floating Holiday Elections (3.12)
@login_required
def floatingholidayelection_list(request):
    return crud_list(
        request,
        FloatingHolidayElection.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "holiday", "policy"),
        "hrm/holiday/floatingholidayelection/list.html",
        search_fields=["employee__party__name", "holiday__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("holiday", "holiday_id", True)],
        extra_context={
            "status_choices": FloatingHolidayElection.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "holidays": (PublicHoliday.objects.filter(tenant=request.tenant, is_optional=True)
                         .order_by("date")),
        },
    )


@login_required
def floatingholidayelection_create(request):
    return crud_create(request, form_class=FloatingHolidayElectionForm,
                       template="hrm/holiday/floatingholidayelection/form.html",
                       success_url="hrm:floatingholidayelection_list")


@login_required
def floatingholidayelection_detail(request, pk):
    obj = get_object_or_404(
        FloatingHolidayElection.objects.select_related(
            "employee__party", "holiday", "policy", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/floatingholidayelection/detail.html", {"obj": obj})


@login_required
def floatingholidayelection_edit(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    # Only a pending election is editable — a decided (approved/rejected) one is locked so a direct
    # POST can't silently rewrite the employee/holiday/note of a record that's already been decided.
    if obj.status != "pending":
        messages.error(request, "Only a pending floating-holiday election can be edited.")
        return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)
    return crud_edit(request, model=FloatingHolidayElection, pk=pk, form_class=FloatingHolidayElectionForm,
                     template="hrm/holiday/floatingholidayelection/form.html",
                     success_url="hrm:floatingholidayelection_list")


@login_required
@require_POST
def floatingholidayelection_delete(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    # A decided election is locked — its approval history must not be silently deleted via a direct POST.
    if obj.status != "pending":
        messages.error(request, "A decided floating-holiday election cannot be deleted.")
        return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)
    return crud_delete(request, model=FloatingHolidayElection, pk=pk,
                       success_url="hrm:floatingholidayelection_list")


@tenant_admin_required  # approving a floating-holiday election is a privileged manager/admin action
@require_POST
def floatingholidayelection_approve(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approved_by = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, "Floating-holiday election approved.")
    return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)


@tenant_admin_required  # rejecting a floating-holiday election is a privileged manager/admin action
@require_POST
def floatingholidayelection_reject(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approved_by = request.user
        reason = request.POST.get("note", "").strip()[:2000]
        if reason:
            obj.note = reason
        obj.save(update_fields=["status", "approved_by", "note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Floating-holiday election rejected.")
    return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)

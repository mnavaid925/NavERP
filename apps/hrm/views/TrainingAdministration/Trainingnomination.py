"""HRM 3.24 Training Administration — Trainingnomination views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TrainingAdministration._helpers import _can_decide_nomination
from apps.hrm.models import (
    EmployeeProfile,
    TrainingNomination,
    TrainingSession,
)
from apps.hrm.forms import (
    TrainingNominationForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.TrainingAdministration._helpers import _can_decide_nomination


@login_required
def trainingnomination_list(request):
    qs = (TrainingNomination.objects.filter(tenant=request.tenant)
          .select_related("session__course", "employee__party"))
    return crud_list(
        request, qs.order_by("-created_at"),
        "hrm/trainingadmin/trainingnomination/list.html",
        search_fields=("number", "session__course__title", "employee__party__name", "justification"),
        filters=[("status", "status", False), ("nomination_type", "nomination_type", False),
                 ("session", "session_id", True), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": TrainingNomination.STATUS_CHOICES,
            "nomination_type_choices": TrainingNomination.NOMINATION_TYPE_CHOICES,
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingnomination_create(request):
    return crud_create(request, form_class=TrainingNominationForm,
                       template="hrm/trainingadmin/trainingnomination/form.html",
                       success_url="hrm:trainingnomination_list")


@login_required
def trainingnomination_detail(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related(
            "session__course", "employee__party", "employee__employment", "nominated_by__party", "approver__party"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingnomination/detail.html", {
        "obj": obj, "can_decide": _can_decide_nomination(request, obj), "is_admin": _is_admin(request.user)})


@login_required
def trainingnomination_edit(request, pk):
    obj = get_object_or_404(TrainingNomination, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be edited.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingNomination, pk=pk, form_class=TrainingNominationForm,
                     template="hrm/trainingadmin/trainingnomination/form.html",
                     success_url="hrm:trainingnomination_list")


@login_required
@require_POST
def trainingnomination_delete(request, pk):
    obj = get_object_or_404(TrainingNomination, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "waitlisted"):
        messages.error(request, "A decided nomination can't be deleted — cancel or withdraw it instead.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingNomination, pk=pk, success_url="hrm:trainingnomination_list")


@login_required
@require_POST
def trainingnomination_approve(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    if not _can_decide_nomination(request, obj):
        messages.error(request, "Only a tenant admin or the nominee's manager can decide this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be approved.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if not obj.session.is_full:
        obj.status = "approved"
    elif obj.session.waitlist_enabled:
        obj.status = "waitlisted"
        messages.info(request, "The session is full — the nominee was waitlisted.")
    else:
        messages.error(request, "The session is full and waitlisting is disabled.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.approver = _current_employee_profile(request)
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve", "status": obj.status})
    messages.success(request, f"Nomination {obj.number} {obj.get_status_display().lower()}.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_reject(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    if not _can_decide_nomination(request, obj):
        messages.error(request, "Only a tenant admin or the nominee's manager can decide this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "waitlisted"):
        messages.error(request, "Only a pending or waitlisted nomination can be rejected.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.rejected_reason = request.POST.get("rejected_reason", "").strip()
    obj.approver = _current_employee_profile(request)
    obj.save(update_fields=["status", "rejected_reason", "approver", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Nomination {obj.number} rejected.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def trainingnomination_waitlist(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party"),
        pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be waitlisted.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "waitlisted"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "waitlist"})
    messages.success(request, f"Nomination {obj.number} waitlisted.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_cancel(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    can_cancel = _can_decide_nomination(request, obj) or (
        profile is not None and obj.nominated_by_id == profile.pk)
    if not can_cancel:
        messages.error(request, "Only the nominator, the nominee's manager, or an admin can cancel this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "approved", "waitlisted"):
        messages.error(request, "This nomination can't be cancelled in its current state.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()
    obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Nomination {obj.number} cancelled.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_withdraw(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (profile is not None and profile.pk == obj.employee_id):
        messages.error(request, "Only the nominee can withdraw their own nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "approved", "waitlisted"):
        messages.error(request, "This nomination can't be withdrawn in its current state.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "withdrawn"
    obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()
    obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "withdraw"})
    messages.success(request, f"Nomination {obj.number} withdrawn.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)

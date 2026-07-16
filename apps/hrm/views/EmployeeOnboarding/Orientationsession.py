"""HRM 3.3 Employee Onboarding — Orientationsession views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    OrientationSession,
)
from apps.hrm.forms import (
    OrientationSessionForm,
)


# ============================================================ Orientation Sessions (3.3)
@login_required
def orientationsession_list(request):
    return crud_list(
        request,
        OrientationSession.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "program", "facilitator"),
        "hrm/onboarding/orientationsession/list.html",
        search_fields=["title", "location", "facilitator__username", "facilitator_name"],
        filters=[("employee", "employee_id", True), ("session_type", "session_type", False),
                 ("attendance_status", "attendance_status", False)],
        extra_context={"type_choices": OrientationSession.SESSION_TYPE_CHOICES,
                       "attendance_choices": OrientationSession.ATTENDANCE_STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def orientationsession_create(request):
    return crud_create(request, form_class=OrientationSessionForm,
                       template="hrm/onboarding/orientationsession/form.html",
                       success_url="hrm:orientationsession_list")


@login_required
def orientationsession_detail(request, pk):
    obj = get_object_or_404(
        OrientationSession.objects.select_related("employee__party", "program", "facilitator"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/orientationsession/detail.html", {"obj": obj})


@login_required
def orientationsession_edit(request, pk):
    return crud_edit(request, model=OrientationSession, pk=pk, form_class=OrientationSessionForm,
                     template="hrm/onboarding/orientationsession/form.html",
                     success_url="hrm:orientationsession_list")


@login_required
@require_POST
def orientationsession_delete(request, pk):
    return crud_delete(request, model=OrientationSession, pk=pk,
                       success_url="hrm:orientationsession_list")


@login_required
@require_POST
def orientationsession_mark_attended(request, pk):
    obj = get_object_or_404(OrientationSession, pk=pk, tenant=request.tenant)
    # A cancelled session is immutable — don't let attendance be back-filled onto it.
    if obj.attendance_status == "cancelled":
        messages.error(request, "A cancelled session cannot be marked attended.")
    elif obj.attendance_status != "attended":
        obj.attendance_status = "attended"
        obj.save(update_fields=["attendance_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_attended"})
        messages.success(request, f"Session '{obj.title}' marked attended.")
    return redirect("hrm:orientationsession_detail", pk=obj.pk)


@login_required
@require_POST
def orientationsession_mark_missed(request, pk):
    obj = get_object_or_404(OrientationSession, pk=pk, tenant=request.tenant)
    if obj.attendance_status == "cancelled":
        messages.error(request, "A cancelled session cannot be marked missed.")
    elif obj.attendance_status != "missed":
        obj.attendance_status = "missed"
        obj.save(update_fields=["attendance_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_missed"})
        messages.success(request, f"Session '{obj.title}' marked missed.")
    return redirect("hrm:orientationsession_detail", pk=obj.pk)

"""HRM 3.24 Training Administration — Trainingfeedback views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.TrainingAdministration._helpers import _can_manage_feedback
from apps.hrm.models import (
    TrainingAttendance,
    TrainingFeedback,
    TrainingSession,
)
from apps.hrm.forms import (
    TrainingFeedbackForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin
from apps.hrm.views.TrainingAdministration._helpers import _can_manage_feedback


@login_required
def trainingfeedback_create(request, attendance_pk):
    """Nested under an attendance record. The form's (tenant, attendance) duplicate guard queries the
    DB directly, so setting instance.attendance before validation is enough."""
    attendance = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course", "employee__party"),
        pk=attendance_pk, tenant=request.tenant)
    # Only the attendee (or an admin) may leave feedback for their own attendance.
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == attendance.employee_id)):
        messages.error(request, "Only the attendee or a tenant admin can leave feedback for this attendance.")
        return redirect("hrm:trainingattendance_detail", pk=attendance.pk)
    if request.method == "POST":
        form = TrainingFeedbackForm(
            request.POST, instance=TrainingFeedback(tenant=request.tenant, attendance=attendance),
            tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Feedback submitted.")
            return redirect("hrm:trainingattendance_detail", pk=attendance.pk)
    else:
        form = TrainingFeedbackForm(
            instance=TrainingFeedback(tenant=request.tenant, attendance=attendance), tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingfeedback/form.html",
                  {"form": form, "is_edit": False, "attendance": attendance})


@login_required
def trainingfeedback_list(request):
    qs = (TrainingFeedback.objects.filter(tenant=request.tenant)
          .select_related("attendance__session__course", "attendance__employee__party"))
    profile = _current_employee_profile(request)
    return crud_list(
        request, qs.order_by("-created_at"),
        "hrm/trainingadmin/trainingfeedback/list.html",
        search_fields=("attendance__session__course__title", "comments"),
        filters=[("would_recommend", "would_recommend", False), ("session", "attendance__session_id", True)],
        extra_context={
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def trainingfeedback_detail(request, pk):
    profile = _current_employee_profile(request)
    return crud_detail(request, model=TrainingFeedback, pk=pk,
                       template="hrm/trainingadmin/trainingfeedback/detail.html",
                       select_related=("attendance__session__course", "attendance__employee__party"),
                       extra_context={"is_admin": _is_admin(request.user),
                                      "current_profile_id": profile.pk if profile is not None else None})


@login_required
def trainingfeedback_edit(request, pk):
    obj = get_object_or_404(TrainingFeedback.objects.select_related("attendance"), pk=pk, tenant=request.tenant)
    if not _can_manage_feedback(request, obj):
        messages.error(request, "Only the attendee or a tenant admin can edit this feedback.")
        return redirect("hrm:trainingfeedback_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingFeedback, pk=pk, form_class=TrainingFeedbackForm,
                     template="hrm/trainingadmin/trainingfeedback/form.html",
                     success_url="hrm:trainingfeedback_list")


@login_required
@require_POST
def trainingfeedback_delete(request, pk):
    obj = get_object_or_404(TrainingFeedback.objects.select_related("attendance"), pk=pk, tenant=request.tenant)
    if not _can_manage_feedback(request, obj):
        messages.error(request, "Only the attendee or a tenant admin can delete this feedback.")
        return redirect("hrm:trainingfeedback_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingFeedback, pk=pk, success_url="hrm:trainingfeedback_list")

"""HRM 3.24 Training Administration — Trainingattendance views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    TrainingAttendance,
    TrainingSession,
)
from apps.hrm.forms import (
    TrainingAttendanceForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ TrainingAttendance (3.24 Attendance)
@login_required
def trainingattendance_list(request):
    qs = (TrainingAttendance.objects.filter(tenant=request.tenant)
          .select_related("session__course", "employee__party"))
    return crud_list(
        request, qs.order_by("-session__start_datetime", "employee__party__name"),
        "hrm/trainingadmin/trainingattendance/list.html",
        search_fields=("session__course__title", "employee__party__name", "notes"),
        filters=[("attendance_status", "attendance_status", False),
                 ("completion_status", "completion_status", False),
                 ("session", "session_id", True), ("employee", "employee_id", True)],
        extra_context={
            "attendance_status_choices": TrainingAttendance.ATTENDANCE_STATUS_CHOICES,
            "completion_status_choices": TrainingAttendance.COMPLETION_STATUS_CHOICES,
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingattendance_create(request):
    return crud_create(request, form_class=TrainingAttendanceForm,
                       template="hrm/trainingadmin/trainingattendance/form.html",
                       success_url="hrm:trainingattendance_list")


@login_required
def trainingattendance_detail(request, pk):
    obj = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course", "employee__party", "nomination"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    return render(request, "hrm/trainingadmin/trainingattendance/detail.html", {
        "obj": obj, "is_admin": _is_admin(request.user),
        "current_profile_id": profile.pk if profile is not None else None,
        "feedback": obj.feedback.first()})


@login_required
def trainingattendance_edit(request, pk):
    return crud_edit(request, model=TrainingAttendance, pk=pk, form_class=TrainingAttendanceForm,
                     template="hrm/trainingadmin/trainingattendance/form.html",
                     success_url="hrm:trainingattendance_list")


@login_required
@require_POST
def trainingattendance_delete(request, pk):
    obj = get_object_or_404(TrainingAttendance, pk=pk, tenant=request.tenant)
    # Deleting would CASCADE its feedback and orphan (SET_NULL) any issued certificate — block it.
    if obj.feedback.exists() or obj.certificates_issued.exists():
        messages.error(request, "This attendance record has feedback or a certificate linked — remove those first.")
        return redirect("hrm:trainingattendance_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingAttendance, pk=pk, success_url="hrm:trainingattendance_list")

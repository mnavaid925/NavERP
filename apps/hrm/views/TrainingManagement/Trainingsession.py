"""HRM 3.22 Training Management — Trainingsession views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    TrainingCourse,
    TrainingSession,
)
from apps.hrm.forms import (
    TrainingSessionForm,
)


# ------------------------------------------------------------ TrainingSession (3.22 Classroom/Virtual/External)
@login_required
def trainingsession_list(request):
    # currency is only rendered on the detail page, not this list — keep it off the list JOIN.
    qs = (TrainingSession.objects.filter(tenant=request.tenant)
          .select_related("course", "instructor_employee__party", "external_vendor"))
    return crud_list(
        request, qs.order_by("-start_datetime", "number"),
        "hrm/training/trainingsession/list.html",
        search_fields=("number", "course__title", "venue_name", "instructor_employee__party__name",
                       "external_instructor_name", "external_vendor__name"),
        filters=[("status", "status", False), ("delivery_mode", "delivery_mode", False),
                 ("course", "course_id", True), ("instructor_employee", "instructor_employee_id", True)],
        extra_context={
            "status_choices": TrainingSession.STATUS_CHOICES,
            "delivery_mode_choices": TrainingSession.DELIVERY_MODE_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
            "instructors": (EmployeeProfile.objects.filter(tenant=request.tenant)
                            .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingsession_create(request):
    return crud_create(request, form_class=TrainingSessionForm,
                       template="hrm/training/trainingsession/form.html",
                       success_url="hrm:trainingsession_list")


@login_required
def trainingsession_detail(request, pk):
    obj = get_object_or_404(
        TrainingSession.objects.select_related(
            "course", "instructor_employee__party", "external_vendor", "currency"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/training/trainingsession/detail.html", {
        "obj": obj,
        # 3.24 cross-touch — this session's nominations + attendance roster.
        "nominations": obj.nominations.select_related("employee__party").all(),
        "attendance": obj.attendance_records.select_related("employee__party").all(),
    })


@login_required
def trainingsession_edit(request, pk):
    return crud_edit(request, model=TrainingSession, pk=pk, form_class=TrainingSessionForm,
                     template="hrm/training/trainingsession/form.html", success_url="hrm:trainingsession_list")


@login_required
@require_POST
def trainingsession_delete(request, pk):
    obj = get_object_or_404(TrainingSession, pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            write_audit_log(request.user, obj, "delete")
            obj.delete()
    except ProtectedError:
        # 3.24 added TrainingNomination.session + TrainingAttendance.session as PROTECT children.
        messages.error(request, "This session has nominations or attendance records and can't be deleted. "
                                "Remove those first.")
        return redirect("hrm:trainingsession_detail", pk=obj.pk)
    messages.success(request, "Deleted successfully.")
    return redirect("hrm:trainingsession_list")

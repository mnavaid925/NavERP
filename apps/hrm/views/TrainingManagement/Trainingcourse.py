"""HRM 3.22 Training Management — Trainingcourse views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingCourse,
)
from apps.hrm.forms import (
    TrainingCourseForm,
)


# ------------------------------------------------------------ TrainingCourse (3.22 Training Catalog)
@login_required
def trainingcourse_list(request):
    qs = (TrainingCourse.objects.filter(tenant=request.tenant)
          .select_related("prerequisite_course")
          .annotate(session_count=Count("sessions", distinct=True)))
    return crud_list(
        request, qs.order_by("title"),
        "hrm/training/trainingcourse/list.html",
        search_fields=("number", "title", "description"),
        filters=[("category", "category", False), ("provider_type", "provider_type", False),
                 ("delivery_mode", "delivery_mode", False), ("is_certification", "is_certification", False),
                 ("is_active", "is_active", False)],
        extra_context={
            "category_choices": TrainingCourse.CATEGORY_CHOICES,
            "provider_type_choices": TrainingCourse.PROVIDER_TYPE_CHOICES,
            "delivery_mode_choices": TrainingCourse.DELIVERY_MODE_CHOICES,
        },
    )


@login_required
def trainingcourse_create(request):
    return crud_create(request, form_class=TrainingCourseForm,
                       template="hrm/training/trainingcourse/form.html",
                       success_url="hrm:trainingcourse_list")


@login_required
def trainingcourse_detail(request, pk):
    obj = get_object_or_404(
        TrainingCourse.objects.select_related("prerequisite_course"), pk=pk, tenant=request.tenant)
    # The sessions sub-table shows the instructor (or external name), not the vendor — no external_vendor JOIN.
    sessions = (obj.sessions.select_related("instructor_employee__party")
                .order_by("-start_datetime")[:20])
    return render(request, "hrm/training/trainingcourse/detail.html", {
        "obj": obj,
        "sessions": sessions,
        "unlocks": obj.unlocks.order_by("title"),   # courses that require THIS one as a prerequisite
        "content_items": obj.content_items.all(),   # 3.23 LMS lessons (Meta-ordered by sequence)
    })


@login_required
def trainingcourse_edit(request, pk):
    return crud_edit(request, model=TrainingCourse, pk=pk, form_class=TrainingCourseForm,
                     template="hrm/training/trainingcourse/form.html", success_url="hrm:trainingcourse_list")


@login_required
@require_POST
def trainingcourse_delete(request, pk):
    obj = get_object_or_404(TrainingCourse, pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            write_audit_log(request.user, obj, "delete")
            obj.delete()
    except ProtectedError:
        # course is PROTECT-referenced by TrainingSession (3.22) AND by LearningPathItem / LearningProgress
        # (3.23) — name all three so the admin knows what to clear first, not just sessions.
        messages.error(request, "This course is referenced by training sessions, learning paths, learner "
                                 "progress, or certificates and can't be deleted. Remove those references first.")
        return redirect("hrm:trainingcourse_detail", pk=obj.pk)
    messages.success(request, "Deleted successfully.")
    return redirect("hrm:trainingcourse_list")

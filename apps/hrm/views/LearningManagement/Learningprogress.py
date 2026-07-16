"""HRM 3.23 Learning Management (LMS) — Learningprogress views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    LearningPath,
    LearningProgress,
    TrainingCourse,
)
from apps.hrm.forms import (
    LearningProgressForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ------------------------------------------------------------ LearningProgress (3.23 Progress Tracking)
@login_required
def learningprogress_list(request):
    qs = (LearningProgress.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "course", "learning_path"))
    return crud_list(
        request, qs.order_by("-updated_at"),
        "hrm/lms/learningprogress/list.html",
        search_fields=("employee__party__name", "course__title"),
        filters=[("status", "status", False), ("course", "course_id", True),
                 ("employee", "employee_id", True), ("learning_path", "learning_path_id", True)],
        extra_context={
            "status_choices": LearningProgress.STATUS_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "paths": LearningPath.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningprogress_create(request):
    return crud_create(request, form_class=LearningProgressForm,
                       template="hrm/lms/learningprogress/form.html", success_url="hrm:learningprogress_list")


@login_required
def learningprogress_detail(request, pk):
    return crud_detail(request, model=LearningProgress, pk=pk,
                       template="hrm/lms/learningprogress/detail.html",
                       select_related=("employee__party", "course", "learning_path"),
                       extra_context={"is_admin": _is_admin(request.user)})   # gate the admin-only Issue-Certificate


@login_required
def learningprogress_edit(request, pk):
    return crud_edit(request, model=LearningProgress, pk=pk, form_class=LearningProgressForm,
                     template="hrm/lms/learningprogress/form.html", success_url="hrm:learningprogress_list")


@login_required
@require_POST
def learningprogress_delete(request, pk):
    return crud_delete(request, model=LearningProgress, pk=pk, success_url="hrm:learningprogress_list")

"""HRM 3.23 Learning Management (LMS) — TeamProgress views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningProgress,
    TrainingCourse,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile


# ------------------------------------------------------------ Team progress rollup (3.23, manager view)
@login_required
def learning_team_progress(request):
    """Manager rollup — the logged-in manager's own + direct-reports' learning progress (reuses the
    3.18 goal-ownership reporting-line filter). Optional ?status=/?course= GET filters."""
    profile = _current_employee_profile(request)
    if profile is None:
        messages.error(request, "Your account isn't linked to an employee profile.")
        return redirect("dashboard:home")
    qs = (LearningProgress.objects.filter(tenant=request.tenant)
          .filter(Q(employee=profile) | Q(employee__employment__manager=profile.party))
          .select_related("employee__party", "course", "learning_path"))
    status = request.GET.get("status", "").strip()
    course = request.GET.get("course", "").strip()
    if status:
        qs = qs.filter(status=status)
    if course.isdigit():
        qs = qs.filter(course_id=int(course))
    qs = qs.order_by("employee__party__name", "course__title")
    rows = list(qs)
    summary = {
        "total": len(rows),
        "completed": sum(1 for r in rows if r.status == "completed"),
        "in_progress": sum(1 for r in rows if r.status == "in_progress"),
    }
    return render(request, "hrm/lms/team_progress.html", {
        "progress_rows": rows,
        "summary": summary,
        "status_choices": LearningProgress.STATUS_CHOICES,
        "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
    })

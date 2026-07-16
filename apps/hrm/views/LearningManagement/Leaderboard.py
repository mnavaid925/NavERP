"""HRM 3.23 Learning Management (LMS) — Leaderboard views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.LearningManagement._helpers import _lms_level_for_points
from apps.hrm.models import (
    LearningProgress,
)
from apps.hrm.views.LearningManagement._helpers import _lms_level_for_points


@login_required
def learning_leaderboard(request):
    """Gamification leaderboard — learners ranked by total points (summed over their LearningProgress),
    with a computed level tier. A DERIVED aggregate query, not a stored table."""
    rows = list(
        LearningProgress.objects.filter(tenant=request.tenant)
        .values("employee_id", "employee__party__name")
        .annotate(total_points=Sum("points_earned"),
                  courses_completed=Count("id", filter=Q(status="completed")),
                  courses_enrolled=Count("id"))
        .order_by("-total_points", "employee__party__name"))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
        row["level"] = _lms_level_for_points(row["total_points"] or 0)
    return render(request, "hrm/lms/leaderboard.html", {"leaderboard_rows": rows})

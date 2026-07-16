"""HRM 3.24 Training Administration — Budget views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CostCenterProfile,
    TrainingSession,
)


# ------------------------------------------------------------ Training Budget (3.24, computed view)
@login_required
def training_budget(request):
    """Computed training-cost view (no model) — the year's training spend (estimated vs actual, and
    by course) vs the allocated cost-center budget for that year. Aggregates over TrainingSession
    costs (3.22) + CostCenterProfile.budget_annual (3.2)."""
    tenant = request.tenant
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", "") or today.year)
    except (TypeError, ValueError):
        year = today.year
    years = sorted({d.year for d in TrainingSession.objects.filter(tenant=tenant).dates("start_datetime", "year")},
                   reverse=True)
    if today.year not in years:
        years = sorted(set(years + [today.year]), reverse=True)

    sessions = TrainingSession.objects.filter(tenant=tenant, start_datetime__year=year)
    totals = sessions.aggregate(estimated=Sum("estimated_cost"), actual=Sum("actual_cost"))
    allocated = (CostCenterProfile.objects.filter(tenant=tenant, budget_year=year)
                 .aggregate(total=Sum("budget_annual"))["total"]) or Decimal("0")
    by_course = list(sessions.values("course__title")
                     .annotate(sessions=Count("id"), estimated=Sum("estimated_cost"), actual=Sum("actual_cost"))
                     .order_by("-actual"))
    total_actual = totals["actual"] or Decimal("0")
    utilization = round(float(total_actual) / float(allocated) * 100, 1) if allocated else None
    return render(request, "hrm/trainingadmin/budget.html", {
        "year": year, "years": years,
        "total_estimated": totals["estimated"] or Decimal("0"),
        "total_actual": total_actual,
        "total_allocated": allocated,
        "utilization": utilization,
        "by_course": by_course,
    })

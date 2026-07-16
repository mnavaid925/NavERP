"""HRM 3.40 Workforce Planning — GapAnalysis views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    WorkforcePlan,
    WorkforcePlanLine,
)


# ---- Derived views (no models) ------------------------------------------------------------------
@tenant_admin_required
def workforce_gap_analysis(request):
    """Gap Analysis — current vs planned headcount per department across the ACTIVE/APPROVED plans
    (optionally scoped to one plan via ?plan=<id>). Aggregated in SQL, not per-row Python."""
    lines = (WorkforcePlanLine.objects.filter(tenant=request.tenant,
                                              plan__status__in=("active", "approved"))
             .select_related("org_unit", "plan"))
    plan_id = request.GET.get("plan", "").strip()
    if plan_id.isdigit():
        lines = lines.filter(plan_id=int(plan_id))

    # Group by org_unit_id (NOT name) — core.OrgUnit doesn't enforce unique names, so two distinct
    # departments that happen to share a name ("Support" under Eng vs under Sales) must stay separate
    # rows; grouping by name alone would silently merge them and mask one dept's reduction.
    rows = (lines.values("org_unit_id", "org_unit__name")
            .annotate(current=Coalesce(Sum("current_headcount"), 0),
                      planned=Coalesce(Sum("planned_headcount"), 0))
            .order_by("org_unit__name"))
    departments = []
    total_current = total_planned = 0
    for r in rows:
        gap = r["planned"] - r["current"]
        total_current += r["current"]
        total_planned += r["planned"]
        departments.append({"name": r["org_unit__name"] or "Unassigned",
                            "current": r["current"], "planned": r["planned"], "gap": gap})
    return render(request, "hrm/workforce/gap_analysis.html", {
        "departments": departments, "total_current": total_current, "total_planned": total_planned,
        "total_gap": total_planned - total_current,
        "plans": WorkforcePlan.objects.filter(tenant=request.tenant,
                                              status__in=("active", "approved")).order_by("-created_at")})

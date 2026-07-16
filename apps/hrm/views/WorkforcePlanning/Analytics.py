"""HRM 3.40 Workforce Planning — Analytics views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    EmployeeSkill,
    WorkforcePlan,
    WorkforcePlanLine,
)


@tenant_admin_required
def workforce_analytics(request):
    """Workforce Analytics — headcount + skills-coverage metrics derived from the plans and the skills
    inventory. All aggregates run in SQL."""
    plans = WorkforcePlan.objects.filter(tenant=request.tenant)
    skills = EmployeeSkill.objects.filter(tenant=request.tenant)

    # Resolve each choice code to its display label HERE — a Django template can't index a dict by a
    # variable key, so the row has to carry its own label.
    hiring_labels = dict(WorkforcePlanLine.HIRING_TYPE_CHOICES)
    category_labels = dict(EmployeeSkill.SKILL_CATEGORY_CHOICES)

    hiring_mix = [
        {**row, "label": hiring_labels.get(row["hiring_type"], row["hiring_type"])}
        for row in WorkforcePlanLine.objects.filter(tenant=request.tenant,
                                                    plan__status__in=("active", "approved"))
        .values("hiring_type").annotate(n=Count("id")).order_by("-n")]
    top_skills = list(skills.values("skill_name")
                      .annotate(n=Count("id")).order_by("-n", "skill_name")[:10])
    by_category = [
        {**row, "label": category_labels.get(row["skill_category"], row["skill_category"])}
        for row in skills.values("skill_category").annotate(n=Count("id")).order_by("-n")]

    headcount = EmployeeProfile.objects.filter(tenant=request.tenant).count()
    critical = skills.filter(is_critical_skill=True).count()
    certified = skills.filter(is_certified=True).count()
    covered = skills.values("employee_id").distinct().count()

    return render(request, "hrm/workforce/analytics.html", {
        "headcount": headcount,
        "plan_count": plans.count(),
        "active_plan_count": plans.filter(status__in=("active", "approved")).count(),
        "skill_count": skills.count(),
        "critical_skill_count": critical,
        "certified_skill_count": certified,
        "employees_with_skills": covered,
        # Coverage: employees who have at least one skill recorded.
        "skill_coverage_percent": (round(covered / headcount * 100, 1) if headcount else 0),
        "hiring_mix": hiring_mix,
        "top_skills": top_skills,
        "by_category": by_category,
    })

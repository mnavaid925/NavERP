"""CRM 1.6 Analytics & Reporting — Overview views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Campaign,
    Case,
    CrmTask,
    Lead,
    Opportunity,
)


# ===================================================== Analytics & Reporting overview (1.6)
@login_required
def overview(request):
    tenant = request.tenant
    stats = {"open_leads": 0, "pipeline": 0, "weighted": 0, "win_rate": 0,
             "open_cases": 0, "open_tasks": 0, "active_campaigns": 0}
    stage_rows, rating_rows, recent_opps = [], [], []
    if tenant is not None:
        leads = Lead.objects.filter(tenant=tenant)
        opps = Opportunity.objects.filter(tenant=tenant)
        cases = Case.objects.filter(tenant=tenant)

        stats["open_leads"] = leads.exclude(status__in=["converted", "unqualified"]).count()
        # DB-side pipeline + weighted-forecast sums (no full-row fetch).
        agg = opps.filter(stage__in=Opportunity.OPEN_STAGES).aggregate(
            pipeline=Sum("amount"),
            weighted=Sum(F("amount") * F("probability"),
                         output_field=DecimalField(max_digits=18, decimal_places=2)),
        )
        stats["pipeline"] = agg["pipeline"] or 0
        stats["weighted"] = (agg["weighted"] or 0) / 100
        # Win rate: won and closed counts in a single annotated pass.
        close_agg = opps.aggregate(
            won=Count("id", filter=Q(stage="closed_won")),
            closed=Count("id", filter=Q(stage__in=["closed_won", "closed_lost"])),
        )
        stats["win_rate"] = round(close_agg["won"] / close_agg["closed"] * 100) if close_agg["closed"] else 0
        stats["open_cases"] = cases.filter(status__in=Case.OPEN_STATUSES).count()
        stats["open_tasks"] = CrmTask.objects.filter(tenant=tenant, status__in=CrmTask.OPEN_STATUSES).count()
        stats["active_campaigns"] = Campaign.objects.filter(tenant=tenant, status="active").count()

        stage_rows = list(opps.values("stage").annotate(c=Count("id")).order_by("stage"))
        rating_rows = list(leads.values("rating").annotate(c=Count("id")).order_by("rating"))
        recent_opps = list(opps.select_related("account", "owner").order_by("-created_at")[:8])

    stage_display = dict(Opportunity.STAGE_CHOICES)
    rating_display = dict(Lead.RATING_CHOICES)
    context = {
        "stats": stats,
        "recent_opps": recent_opps,
        "chart_stage_labels": [stage_display.get(r["stage"], r["stage"]) for r in stage_rows],
        "chart_stage_data": [r["c"] for r in stage_rows],
        "chart_rating_labels": [rating_display.get(r["rating"], r["rating"]) for r in rating_rows],
        "chart_rating_data": [r["c"] for r in rating_rows],
    }
    return render(request, "crm/overview.html", context)

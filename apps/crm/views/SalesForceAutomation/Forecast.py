"""CRM 1.2 Sales Force Automation — Forecast views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    SalesQuota,
)


# ------------------------------------------------------------ Forecast dashboard (1.2)
@login_required
def forecast(request):
    """Weighted-pipeline-by-forecast-category + quota-attainment dashboard (DB-side aggregates)."""
    tenant = request.tenant
    cats, quotas = [], []
    totals = {"pipeline": 0, "weighted": 0, "won": 0, "target": 0}
    if tenant is not None:
        opps = Opportunity.objects.filter(tenant=tenant)
        cat_display = dict(Opportunity.FORECAST_CATEGORY_CHOICES)
        for r in opps.values("forecast_category").annotate(
                count=Count("id"), total=Sum("amount"),
                weighted=Sum(F("amount") * F("probability"),
                             output_field=DecimalField(max_digits=18, decimal_places=2))
        ).order_by("forecast_category"):
            cats.append({"label": cat_display.get(r["forecast_category"], r["forecast_category"]),
                         "count": r["count"], "total": r["total"] or 0,
                         "weighted": (r["weighted"] or 0) / 100})
        open_agg = opps.filter(stage__in=Opportunity.OPEN_STAGES).aggregate(
            pipeline=Sum("amount"),
            weighted=Sum(F("amount") * F("probability"),
                         output_field=DecimalField(max_digits=18, decimal_places=2)))
        totals["pipeline"] = open_agg["pipeline"] or 0
        totals["weighted"] = (open_agg["weighted"] or 0) / 100
        totals["won"] = opps.filter(stage="closed_won").aggregate(t=Sum("amount"))["t"] or 0
        # Quota attainment: closed-won booked per (owner, territory) in one grouped query. A
        # territory-scoped quota matches its (owner, territory) bucket; a null-territory quota
        # matches the owner's total across all territories.
        won = opps.filter(stage="closed_won").values_list("owner", "territory").annotate(t=Sum("amount"))
        won_by_owner_terr = {(o, terr): (t or 0) for o, terr, t in won}
        won_by_owner = {}
        for (o, terr), t in won_by_owner_terr.items():
            won_by_owner[o] = won_by_owner.get(o, 0) + t
        for q in SalesQuota.objects.filter(tenant=tenant).select_related("owner", "territory"):
            if q.territory_id:
                attained = won_by_owner_terr.get((q.owner_id, q.territory_id), 0)
            else:
                attained = won_by_owner.get(q.owner_id, 0)
            target = q.target_amount or 0
            totals["target"] += target
            quotas.append({"q": q, "attained": attained,
                           "pct": max(0, round(float(attained) / float(target) * 100)) if target else 0})
    return render(request, "crm/sales/forecast.html", {
        "cats": cats, "quotas": quotas, "totals": totals,
        "chart_labels": [c["label"] for c in cats],
        "chart_data": [float(c["total"]) for c in cats],
    })

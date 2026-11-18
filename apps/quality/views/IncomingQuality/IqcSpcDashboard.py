from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import render

from apps.core.models import Party
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)


@login_required
def iqc_spc_dashboard(request):
    lots_qs = IncomingInspectionLot.objects.filter(tenant=request.tenant)

    kpis = lots_qs.aggregate(
        total_lots=Count("id"),
        accepted_lots=Count(
            "id",
            filter=Q(usage_decision__in=("accepted", "skip_lot_passed", "accepted_with_deviation")),
        ),
        avg_cpk=Avg("spc_cpk"),
        out_of_control_count=Count(
            "id",
            filter=Q(spc_out_of_control=True) | Q(spc_cpk__lt=1.33, spc_cpk__isnull=False),
        ),
        crit=Sum("critical_defects"),
        maj=Sum("major_defects"),
        min_def=Sum("minor_defects"),
    )

    total_lots = kpis["total_lots"] or 0
    accepted_lots = kpis["accepted_lots"] or 0
    acceptance_rate = round((accepted_lots / total_lots * 100), 1) if total_lots > 0 else 100.0

    avg_cpk = round(float(kpis["avg_cpk"]), 2) if kpis["avg_cpk"] is not None else None
    out_of_control_count = kpis["out_of_control_count"] or 0

    recent_alerts = list(
        lots_qs.filter(
            Q(spc_out_of_control=True) | Q(spc_cpk__lt=1.33, spc_cpk__isnull=False)
        )
        .select_related("supplier", "inspection_plan")
        .order_by("-created_at")[:10]
    )

    defect_pareto = {
        "critical": kpis["crit"] or 0,
        "major": kpis["maj"] or 0,
        "minor": kpis["min_def"] or 0,
    }

    # Supplier leaderboard
    suppliers_raw = (
        lots_qs.values("supplier_id", "supplier__name")
        .annotate(
            total=Count("id"),
            accepted=Count(
                "id",
                filter=Q(usage_decision__in=("accepted", "skip_lot_passed", "accepted_with_deviation")),
            ),
            avg_cpk=Avg("spc_cpk"),
        )
        .order_by("-total")[:8]
    )

    supplier_leaderboard = []
    for s in suppliers_raw:
        s_total = s["total"]
        s_acc = s["accepted"]
        s_rate = round((s_acc / s_total * 100), 1) if s_total > 0 else 0
        s_cpk = round(float(s["avg_cpk"]), 2) if s["avg_cpk"] else None
        supplier_leaderboard.append({
            "name": s["supplier__name"] or "Unknown Supplier",
            "total_lots": s_total,
            "acceptance_rate": s_rate,
            "avg_cpk": s_cpk,
        })

    context = {
        "lots_inspected_count": total_lots,
        "acceptance_rate": acceptance_rate,
        "avg_cpk": avg_cpk,
        "out_of_control_count": out_of_control_count,
        "recent_alerts": recent_alerts,
        "supplier_leaderboard": supplier_leaderboard,
        "defect_pareto": defect_pareto,
    }
    return render(request, "quality/incoming_quality/spc_dashboard.html", context)

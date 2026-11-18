from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.shortcuts import render

from apps.quality.models.InProcessQuality.FirstArticleInspections import FirstArticleInspection
from apps.quality.models.InProcessQuality.InProcessInspections import InProcessInspection
from apps.quality.models.InProcessQuality.LayeredProcessAudits import LayeredProcessAudit
from apps.quality.models.InProcessQuality.ProcessParameterLogs import ProcessParameterLog


@login_required
def spc_dashboard(request):
    tenant = request.tenant

    total_inspections = InProcessInspection.objects.filter(tenant=tenant).count()
    fai_pending_release_count = FirstArticleInspection.objects.filter(
        tenant=tenant,
        status__in=["draft", "in_inspection"],
        release_verdict="pending",
    ).count()
    active_ooc_oos_count = ProcessParameterLog.objects.filter(
        tenant=tenant,
        excursion_status__in=["out_of_control", "out_of_spec"],
    ).count()

    avg_lpa_val = LayeredProcessAudit.objects.filter(
        tenant=tenant,
        status="completed",
    ).aggregate(avg=Avg("compliance_percentage"))["avg"] or Decimal("0.00")
    avg_lpa_compliance = round(avg_lpa_val, 1)

    recent_inspections = InProcessInspection.objects.filter(
        tenant=tenant
    ).select_related("work_center").order_by("-created_at")[:5]

    recent_fais = FirstArticleInspection.objects.filter(
        tenant=tenant
    ).select_related("work_center").order_by("-created_at")[:5]

    recent_excursions = ProcessParameterLog.objects.filter(
        tenant=tenant,
        excursion_status__in=["out_of_control", "out_of_spec"],
    ).select_related("work_center").order_by("-recorded_at")[:5]

    recent_lpas = LayeredProcessAudit.objects.filter(
        tenant=tenant
    ).select_related("work_center", "auditor").order_by("-scheduled_date")[:5]

    context = {
        "total_inspections": total_inspections,
        "fai_pending_release_count": fai_pending_release_count,
        "active_ooc_oos_count": active_ooc_oos_count,
        "avg_lpa_compliance": avg_lpa_compliance,
        "recent_inspections": recent_inspections,
        "recent_fais": recent_fais,
        "recent_excursions": recent_excursions,
        "recent_lpas": recent_lpas,
    }
    return render(
        request,
        "quality/inprocessquality/spc_dashboard.html",
        context,
    )

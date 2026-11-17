import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.views._common import quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def capa_tracking_board(request):
    base_qs = quality_scope(CapaInvestigation.objects.all(), request).select_related(
        "lead_investigator", "quality_owner", "department"
    )

    active_capas = list(
        base_qs.exclude(status__in=["closed", "voided"]).order_by("created_at")
    )
    today = timezone.now().date()

    tier_0_30 = []
    tier_31_60 = []
    tier_61_90 = []
    tier_90_plus = []
    overdue_capas = []

    total_days = 0
    for capa in active_capas:
        days = (today - capa.created_at.date()).days
        total_days += days
        if days <= 30:
            tier_0_30.append(capa)
        elif days <= 60:
            tier_31_60.append(capa)
        elif days <= 90:
            tier_61_90.append(capa)
        else:
            tier_90_plus.append(capa)

        if capa.is_overdue:
            overdue_capas.append(capa)

    escalated_capas = [c for c in active_capas if c.is_escalated]
    avg_cycle = round(total_days / len(active_capas), 1) if active_capas else 0

    stats = {
        "total_active": len(active_capas),
        "overdue_count": len(overdue_capas),
        "escalated_count": len(escalated_capas),
        "avg_cycle_days": avg_cycle,
    }

    context = {
        "tier_0_30": tier_0_30,
        "tier_31_60": tier_31_60,
        "tier_61_90": tier_61_90,
        "tier_90_plus": tier_90_plus,
        "escalated_capas": escalated_capas,
        "overdue_capas": overdue_capas,
        "stats": stats,
    }
    return render(request, "quality/capamanagement/capa_tracking_board.html", context)


@login_required
def capa_tracking_board_export(request):
    qs = quality_scope(CapaInvestigation.objects.all(), request).exclude(
        status__in=["closed", "voided"]
    ).select_related("lead_investigator", "quality_owner")

    today = timezone.now().date()
    response = HttpResponse(content_type="text/csv")
    filename = f"CAPA_Tracking_Board_{today.strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "CAPA Number",
        "Title",
        "Aging Tier",
        "Days Open",
        "Risk Priority",
        "Status",
        "Lead Investigator",
        "Target Closure Date",
        "Is Overdue",
        "Is Escalated",
    ])

    for c in qs:
        days = (today - c.created_at.date()).days
        if days <= 30:
            tier = "0-30 Days"
        elif days <= 60:
            tier = "31-60 Days"
        elif days <= 90:
            tier = "61-90 Days"
        else:
            tier = ">90 Days (Critical Aging)"

        writer.writerow([
            csv_safe(c.number),
            csv_safe(c.title),
            csv_safe(tier),
            csv_safe(days),
            csv_safe(c.get_risk_priority_display()),
            csv_safe(c.get_status_display()),
            csv_safe(c.lead_investigator.username if c.lead_investigator else ""),
            csv_safe(c.target_closure_date),
            csv_safe("Yes" if c.is_overdue else "No"),
            csv_safe("Yes" if c.is_escalated else "No"),
        ])

    write_audit_log(request.user, CapaInvestigation(), "export", tenant=request.tenant)
    return response

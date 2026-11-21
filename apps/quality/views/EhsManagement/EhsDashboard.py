import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import EnvironmentalMonitoringLog
from apps.quality.models.EhsManagement.HazardousMaterials import HazardousMaterial
from apps.quality.models.EhsManagement.SafetyIncidents import SafetyIncident
from apps.quality.models.EhsManagement.WasteDisposalManifests import WasteDisposalManifest
from apps.quality.views._common import _csv_safe, quality_scope


@login_required
def ehs_dashboard(request):
    today = timezone.now().date()
    ninety_days_from_now = today + timedelta(days=90)
    ninety_days_ago = today - timedelta(days=90)

    # 1. Hazardous Materials Metrics
    materials_qs = quality_scope(HazardousMaterial.objects.all(), request)
    mat_agg = materials_qs.aggregate(
        active_count=Count("id", filter=Q(status="active")),
        expiring_sds_count=Count(
            "id",
            filter=Q(sds_expiry_date__isnull=False, sds_expiry_date__lte=ninety_days_from_now),
        ),
    )
    active_materials_count = mat_agg["active_count"]
    expiring_sds_count = mat_agg["expiring_sds_count"]
    expiring_sds_list = materials_qs.filter(
        sds_expiry_date__isnull=False, sds_expiry_date__lte=ninety_days_from_now
    ).order_by("sds_expiry_date")[:5]

    # 2. Safety Incidents & OSHA 300 Metrics
    incidents_qs = quality_scope(SafetyIncident.objects.all(), request)
    inc_agg = incidents_qs.aggregate(
        total_count=Count("id"),
        osha_count=Count("id", filter=Q(is_osha_recordable=True)),
        dart_count=Count("id", filter=Q(lost_workdays_count__gt=0) | Q(restricted_workdays_count__gt=0)),
        total_lost=Sum("lost_workdays_count"),
        total_restricted=Sum("restricted_workdays_count"),
    )
    total_incidents_count = inc_agg["total_count"]
    osha_recordable_count = inc_agg["osha_count"]
    dart_cases_count = inc_agg["dart_count"]
    total_lost_days = inc_agg["total_lost"] or 0
    total_restricted_days = inc_agg["total_restricted"] or 0

    recent_incidents = incidents_qs.select_related("org_unit", "reported_by").order_by("-incident_date")[:5]

    severity_counts = incidents_qs.values("severity").annotate(count=Count("id"))
    incidents_by_severity = {item["severity"]: item["count"] for item in severity_counts}

    # 3. Cleanroom Environmental Monitoring Excursions
    env_qs = quality_scope(EnvironmentalMonitoringLog.objects.all(), request)
    active_excursions_qs = env_qs.filter(
        evaluation_status__in=["alert_exceeded", "action_exceeded"]
    ).order_by("-sampling_timestamp")
    active_excursions_count = active_excursions_qs.count()
    recent_excursions = active_excursions_qs.select_related("org_unit", "sampled_by")[:5]

    # 4. Waste Disposal Manifests & 90-Day Accumulation
    manifests_qs = quality_scope(WasteDisposalManifest.objects.all(), request)
    man_agg = manifests_qs.aggregate(
        pending_count=Count("id", filter=Q(status__in=["draft", "scheduled", "in_transit"])),
        overdue_count=Count(
            "id",
            filter=Q(
                status__in=["draft", "scheduled"],
                accumulation_start_date__lt=ninety_days_ago,
            ),
        ),
    )
    pending_manifests_count = man_agg["pending_count"]
    overdue_accumulation_count = man_agg["overdue_count"]
    pending_manifests = manifests_qs.filter(
        status__in=["draft", "scheduled", "in_transit"]
    ).select_related("generator_org_unit", "transporter", "tsdf_facility").order_by("accumulation_start_date")[:5]

    type_counts = manifests_qs.values("manifest_type").annotate(count=Count("id"))
    manifests_by_type = {item["manifest_type"]: item["count"] for item in type_counts}

    context = {
        "active_materials_count": active_materials_count,
        "expiring_sds_count": expiring_sds_count,
        "total_incidents_count": total_incidents_count,
        "osha_recordable_count": osha_recordable_count,
        "dart_cases_count": dart_cases_count,
        "total_lost_days": total_lost_days,
        "total_restricted_days": total_restricted_days,
        "active_excursions_count": active_excursions_count,
        "pending_manifests_count": pending_manifests_count,
        "overdue_accumulation_count": overdue_accumulation_count,
        "recent_incidents": recent_incidents,
        "recent_excursions": recent_excursions,
        "expiring_sds_list": expiring_sds_list,
        "pending_manifests": pending_manifests,
        "incidents_by_severity": incidents_by_severity,
        "manifests_by_type": manifests_by_type,
    }
    return render(request, "quality/ehsmanagement/ehs_dashboard.html", context)


@login_required
def ehs_dashboard_export(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="ehs_dashboard_kpis_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    today = timezone.now().date()
    ninety_days_from_now = today + timedelta(days=90)
    ninety_days_ago = today - timedelta(days=90)

    materials_qs = quality_scope(HazardousMaterial.objects.all(), request)
    incidents_qs = quality_scope(SafetyIncident.objects.all(), request)
    env_qs = quality_scope(EnvironmentalMonitoringLog.objects.all(), request)
    manifests_qs = quality_scope(WasteDisposalManifest.objects.all(), request)

    mat_agg = materials_qs.aggregate(
        active_count=Count("id", filter=Q(status="active")),
        expiring_count=Count("id", filter=Q(sds_expiry_date__lte=ninety_days_from_now)),
    )
    inc_agg = incidents_qs.aggregate(
        total_count=Count("id"),
        osha_count=Count("id", filter=Q(is_osha_recordable=True)),
        dart_count=Count("id", filter=Q(lost_workdays_count__gt=0) | Q(restricted_workdays_count__gt=0)),
        total_lost=Sum("lost_workdays_count"),
        total_restricted=Sum("restricted_workdays_count"),
    )
    env_agg = env_qs.aggregate(
        excursion_count=Count("id", filter=Q(evaluation_status__in=["alert_exceeded", "action_exceeded"])),
    )
    man_agg = manifests_qs.aggregate(
        pending_count=Count("id", filter=Q(status__in=["draft", "scheduled", "in_transit"])),
        overdue_count=Count(
            "id",
            filter=Q(
                status__in=["draft", "scheduled"],
                accumulation_start_date__lt=ninety_days_ago,
            ),
        ),
    )

    writer = csv.writer(response)
    writer.writerow(["EHS Metric KPI", "Value"])
    writer.writerow(["Active Hazardous Chemicals", _csv_safe(mat_agg["active_count"])])
    writer.writerow(["Expiring / Overdue SDSs (90d)", _csv_safe(mat_agg["expiring_count"])])
    writer.writerow(["Total Workplace Incidents Logged", _csv_safe(inc_agg["total_count"])])
    writer.writerow(["OSHA 300 Recordable Incidents", _csv_safe(inc_agg["osha_count"])])
    writer.writerow(["DART Incidents (Lost/Restricted Time)", _csv_safe(inc_agg["dart_count"])])
    writer.writerow(["Total Days Away From Work", _csv_safe(inc_agg["total_lost"] or 0)])
    writer.writerow(["Total Restricted / Transfer Days", _csv_safe(inc_agg["total_restricted"] or 0)])
    writer.writerow(["Cleanroom Environmental Excursions", _csv_safe(env_agg["excursion_count"])])
    writer.writerow(["Pending Waste Manifests In Transit / TSDF", _csv_safe(man_agg["pending_count"])])
    writer.writerow(["Overdue Waste Accumulations (>90d)", _csv_safe(man_agg["overdue_count"])])
    return response

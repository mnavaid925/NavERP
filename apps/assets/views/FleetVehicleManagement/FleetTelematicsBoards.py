"""Fleet Telematics, Live GPS Dispatch and Operations Command Board view (11.19)."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.assets.models.FleetVehicleManagement.FleetVehicles import FleetVehicle
from apps.assets.models.FleetVehicleManagement.VehicleDriverAssignments import VehicleDriverAssignment
from apps.assets.models.FleetVehicleManagement.VehicleFuelLogs import VehicleFuelLog
from apps.assets.models.FleetVehicleManagement.VehicleServiceSchedules import VehicleServiceSchedule
from apps.assets.views._common import assets_scope


@login_required
def fleet_telematics_board(request):
    """Interactive command dashboard for real-time fleet GPS tracking, safety, and operational readiness."""
    vehicles_qs = assets_scope(FleetVehicle.objects, request)
    today = timezone.now().date()

    aggregates = vehicles_qs.aggregate(
        total_vehicles=Count("id"),
        active_in_service=Count("id", filter=Q(status="active_in_service")),
        in_shop=Count("id", filter=Q(status="in_shop_maintenance")),
        moving_count=Count("id", filter=Q(engine_state="moving_normal")),
        idling_count=Count("id", filter=Q(engine_state="idling")),
        geofence_breach_count=Count("id", filter=Q(geofence_status="geofence_breach_alert")),
        expired_compliance_count=Count("id", filter=Q(compliance_status="expired_non_compliant")),
    )

    schedules_qs = assets_scope(VehicleServiceSchedule.objects, request)
    overdue_service_count = schedules_qs.filter(
        Q(status="overdue") | Q(next_due_date__lt=today)
    ).count()

    vehicles_display_qs = vehicles_qs
    q = request.GET.get("q", "").strip()
    if q:
        vehicles_display_qs = vehicles_display_qs.filter(
            Q(name__icontains=q)
            | Q(license_plate__icontains=q)
            | Q(vin__icontains=q)
            | Q(number__icontains=q)
        )
    engine_state_param = request.GET.get("engine_state", "").strip()
    if engine_state_param:
        vehicles_display_qs = vehicles_display_qs.filter(engine_state=engine_state_param)
    status_param = request.GET.get("status", "").strip()
    if status_param:
        vehicles_display_qs = vehicles_display_qs.filter(status=status_param)

    recent_vehicles = (
        vehicles_display_qs.select_related("primary_driver__party", "org_unit")
        .order_by("-last_telemetry_at", "-updated_at")[:10]
    )

    high_risk_drivers = (
        assets_scope(VehicleDriverAssignment.objects, request)
        .filter(status="active", safety_tier__in=["high_risk", "needs_coaching"])
        .select_related("driver__party", "vehicle")
        .order_by("safety_score")[:5]
    )

    recent_fuel_logs = (
        assets_scope(VehicleFuelLog.objects, request)
        .select_related("vehicle", "driver__party")
        .order_by("-fuel_date")[:5]
    )

    upcoming_services = (
        schedules_qs.filter(status__in=["overdue", "due_soon", "active_tracking"])
        .select_related("vehicle", "service_vendor")
        .order_by("next_due_date")[:5]
    )

    context = {
        "total_vehicles": aggregates["total_vehicles"] or 0,
        "active_in_service": aggregates["active_in_service"] or 0,
        "active_telematics_count": aggregates["active_in_service"] or 0,
        "in_shop": aggregates["in_shop"] or 0,
        "moving_count": aggregates["moving_count"] or 0,
        "idling_count": aggregates["idling_count"] or 0,
        "speeding_count": 0,
        "geofence_breach_count": aggregates["geofence_breach_count"] or 0,
        "geofence_alerts_count": aggregates["geofence_breach_count"] or 0,
        "overdue_service_count": overdue_service_count,
        "expired_compliance_count": aggregates["expired_compliance_count"] or 0,
        "recent_vehicles": recent_vehicles,
        "high_risk_drivers": high_risk_drivers,
        "recent_fuel_logs": recent_fuel_logs,
        "upcoming_services": upcoming_services,
        "maintenance_queue": upcoming_services,
    }
    return render(request, "assets/fleetvehiclemanagement/fleet_telematics_board.html", context)

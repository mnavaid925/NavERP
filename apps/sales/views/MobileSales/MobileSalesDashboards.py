"""Sales 8.16 — MobileSalesDashboard executive view."""
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.sales.models.MobileSales.FieldCheckIns import FieldCheckIn
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.MobileSales.MobileDealAlerts import MobileDealAlert
from apps.sales.models.MobileSales.MobileDeviceSessions import MobileDeviceSession


@login_required
def mobile_sales_dashboard(request):
    tenant = request.tenant
    today = timezone.localdate()

    # Routes today
    routes_today = FieldSalesRoute.objects.filter(tenant=tenant, route_date=today).select_related("sales_rep")
    total_routes_today = routes_today.count()

    total_stops_today = routes_today.aggregate(total=Sum("total_stops"))["total"] or 0
    completed_stops_today = routes_today.aggregate(completed=Sum("completed_stops"))["completed"] or 0
    pending_stops_today = max(0, total_stops_today - completed_stops_today)

    # Check-ins & geofence compliance
    checkins_today = FieldCheckIn.objects.filter(tenant=tenant, check_in_at__date=today)
    total_checkins_today = checkins_today.count()
    verified_checkins_today = checkins_today.filter(is_geofence_verified=True).count()

    if total_checkins_today > 0:
        geofence_compliance_pct = int(round((verified_checkins_today / total_checkins_today) * 100))
    else:
        # Fall back to all-time compliance if no visits today
        all_checkins = FieldCheckIn.objects.filter(tenant=tenant)
        all_count = all_checkins.count()
        if all_count > 0:
            geofence_compliance_pct = int(round((all_checkins.filter(is_geofence_verified=True).count() / all_count) * 100))
        else:
            geofence_compliance_pct = 100

    active_routes = routes_today.filter(status__in=["scheduled", "in_progress"])[:5]
    recent_checkins = (
        FieldCheckIn.objects.filter(tenant=tenant)
        .select_related("party", "sales_rep", "resulting_quote", "route")
        .order_by("-check_in_at")[:8]
    )
    urgent_alerts = (
        MobileDealAlert.objects.filter(tenant=tenant, is_read=False, urgency__in=["urgent", "high"])
        .select_related("recipient", "related_quote", "related_opportunity")
        .order_by("-created_at")[:6]
    )
    active_devices = (
        MobileDeviceSession.objects.filter(tenant=tenant, is_active=True, is_trusted=True)
        .select_related("user")
        .order_by("-last_sync_at")[:6]
    )

    context = {
        "total_routes_today": total_routes_today,
        "completed_stops_today": completed_stops_today,
        "pending_stops_today": pending_stops_today,
        "geofence_compliance_pct": geofence_compliance_pct,
        "active_routes": active_routes,
        "recent_checkins": recent_checkins,
        "urgent_alerts": urgent_alerts,
        "active_devices": active_devices,
    }
    return render(request, "sales/mobilesales/dashboard/mobile_sales_dashboard.html", context)

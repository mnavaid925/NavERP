from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.MobileAssetManagement.AssetGeofenceEvents import AssetGeofenceEventForm
from apps.assets.models.MobileAssetManagement.AssetGeofenceEvents import AssetGeofenceEvent
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def asset_geofence_event_list(request):
    qs = assets_scope(
        AssetGeofenceEvent.objects.select_related("asset", "acknowledged_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(fence_name__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(resolution_notes__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    event_type_filter = request.GET.get("event_type", "").strip()
    if event_type_filter:
        qs = qs.filter(event_type=event_type_filter)

    severity_filter = request.GET.get("severity", "").strip()
    if severity_filter:
        qs = qs.filter(severity=severity_filter)

    metrics = AssetGeofenceEvent.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        open_alerts=Count("id", filter=Q(status="open_alert")),
        critical=Count("id", filter=Q(severity="critical")),
        resolved=Count("id", filter=Q(status="resolved")),
    )
    total_events = metrics["total"]
    open_alerts_count = metrics["open_alerts"]
    critical_breaches_count = metrics["critical"]
    resolved_count = metrics["resolved"]

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/mobileassetmanagement/asset_geofence_event/list.html",
        {
            "events": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "event_type_choices": AssetGeofenceEvent.EVENT_TYPE_CHOICES,
            "severity_choices": AssetGeofenceEvent.SEVERITY_CHOICES,
            "status_choices": AssetGeofenceEvent.STATUS_CHOICES,
            "total_events": total_events,
            "open_alerts_count": open_alerts_count,
            "critical_breaches_count": critical_breaches_count,
            "resolved_count": resolved_count,
        },
    )


@login_required
def asset_geofence_event_create(request):
    if request.method == "POST":
        form = AssetGeofenceEventForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            event = form.save(commit=False)
            event.tenant = request.tenant
            event.save()
            write_audit_log(request.user, event, "create", tenant=request.tenant)
            messages.success(request, f"Geofence alert {event.number} logged successfully.")
            return redirect("assets:asset_geofence_event_detail", pk=event.pk)
    else:
        initial = {"detected_at": timezone.now()}
        form = AssetGeofenceEventForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/mobileassetmanagement/asset_geofence_event/form.html",
        {"form": form, "title": "Log Geofence Event"},
    )


@login_required
def asset_geofence_event_detail(request, pk):
    event = assets_object(
        request,
        AssetGeofenceEvent,
        pk,
        select_related=["asset", "acknowledged_by"],
    )
    return render(
        request,
        "assets/mobileassetmanagement/asset_geofence_event/detail.html",
        {"event": event},
    )


@login_required
def asset_geofence_event_edit(request, pk):
    event = assets_object(request, AssetGeofenceEvent, pk)
    if request.method == "POST":
        form = AssetGeofenceEventForm(request.POST, instance=event, tenant=request.tenant)
        if form.is_valid():
            event = form.save(commit=False)
            if event.status == "resolved" and not event.acknowledged_by_id:
                event.acknowledged_by = request.user
                event.acknowledged_at = timezone.now()
            event.save()
            write_audit_log(request.user, event, "update", tenant=request.tenant)
            messages.success(request, f"Geofence alert {event.number} updated successfully.")
            return redirect("assets:asset_geofence_event_detail", pk=event.pk)
    else:
        form = AssetGeofenceEventForm(instance=event, tenant=request.tenant)

    return render(
        request,
        "assets/mobileassetmanagement/asset_geofence_event/form.html",
        {"form": form, "event": event, "title": f"Edit Geofence Alert: {event.number}"},
    )


@login_required
@require_POST
def asset_geofence_event_delete(request, pk):
    event = assets_object(request, AssetGeofenceEvent, pk)
    number = event.number
    write_audit_log(request.user, event, "delete", tenant=request.tenant)
    event.delete()
    messages.success(request, f"Geofence alert {number} deleted successfully.")
    return redirect("assets:asset_geofence_event_list")

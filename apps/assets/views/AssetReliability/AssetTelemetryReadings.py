from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetReliability.AssetTelemetryReadings import AssetTelemetryReadingForm
from apps.assets.models import AssetMaintenanceRequest
from apps.assets.models.AssetReliability.AssetTelemetryReadings import AssetTelemetryReading
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_telemetry_reading_list(request):
    qs = assets_scope(
        AssetTelemetryReading.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "recorded_by",
            "triggered_maintenance_request",
        ),
        request,
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(sensor_identifier__icontains=q)
            | Q(alert_notes__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__tag_code__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    # Filters
    threshold_filter = request.GET.get("threshold_status", "").strip()
    if threshold_filter:
        qs = qs.filter(threshold_status=threshold_filter)

    metric_filter = request.GET.get("metric_type", "").strip()
    if metric_filter:
        qs = qs.filter(metric_type=metric_filter)

    source_filter = request.GET.get("source", "").strip()
    if source_filter:
        qs = qs.filter(source=source_filter)

    anomaly_filter = request.GET.get("is_anomaly", "").strip()
    if anomaly_filter == "1":
        qs = qs.filter(is_anomaly=True)
    elif anomaly_filter == "0":
        qs = qs.filter(is_anomaly=False)

    # Summary KPI counts over tenant
    tenant_base = AssetTelemetryReading.objects.filter(tenant=request.tenant)
    total_readings = tenant_base.count()
    critical_reading_count = tenant_base.filter(threshold_status="critical").count()
    anomaly_reading_count = tenant_base.filter(Q(is_anomaly=True) | Q(threshold_status="anomaly_detected")).count()
    normal_reading_count = tenant_base.filter(threshold_status="normal").count()

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "telemetry_readings": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "source_choices": AssetTelemetryReading.SOURCE_CHOICES,
        "metric_type_choices": AssetTelemetryReading.METRIC_TYPE_CHOICES,
        "threshold_status_choices": AssetTelemetryReading.THRESHOLD_STATUS_CHOICES,
        "total_readings": total_readings,
        "critical_reading_count": critical_reading_count,
        "anomaly_reading_count": anomaly_reading_count,
        "normal_reading_count": normal_reading_count,
    }
    return render(request, "assets/assetreliability/asset_telemetry_reading/list.html", context)


@login_required
def asset_telemetry_reading_detail(request, pk):
    reading = assets_object(
        request,
        AssetTelemetryReading,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "recorded_by",
            "triggered_maintenance_request",
        ],
    )
    return render(
        request,
        "assets/assetreliability/asset_telemetry_reading/detail.html",
        {"reading": reading},
    )


@login_required
def asset_telemetry_reading_create(request):
    if request.method == "POST":
        form = AssetTelemetryReadingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            reading = form.save(commit=False)
            reading.tenant = request.tenant
            if not reading.recorded_by:
                reading.recorded_by = request.user
            reading.save()
            write_audit_log(request.user, reading, "create", tenant=request.tenant)
            messages.success(request, f"Telemetry Reading {reading.number} recorded successfully.")
            return redirect("assets:asset_telemetry_reading_detail", pk=reading.pk)
    else:
        initial = {"recorded_at": timezone.now()}
        form = AssetTelemetryReadingForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/assetreliability/asset_telemetry_reading/form.html",
        {"form": form, "reading": None, "is_edit": False},
    )


@login_required
def asset_telemetry_reading_edit(request, pk):
    reading = assets_object(request, AssetTelemetryReading, pk)
    if request.method == "POST":
        form = AssetTelemetryReadingForm(request.POST, instance=reading, tenant=request.tenant)
        if form.is_valid():
            reading = form.save()
            write_audit_log(request.user, reading, "update", tenant=request.tenant)
            messages.success(request, f"Telemetry Reading {reading.number} updated successfully.")
            return redirect("assets:asset_telemetry_reading_detail", pk=reading.pk)
    else:
        form = AssetTelemetryReadingForm(instance=reading, tenant=request.tenant)

    return render(
        request,
        "assets/assetreliability/asset_telemetry_reading/form.html",
        {"form": form, "reading": reading, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def asset_telemetry_reading_delete(request, pk):
    reading = assets_object(request, AssetTelemetryReading, pk)
    number = reading.number
    write_audit_log(request.user, reading, "delete", tenant=request.tenant)
    reading.delete()
    messages.success(request, f"Telemetry Reading {number} deleted successfully.")
    return redirect("assets:asset_telemetry_reading_list")


@login_required
@require_POST
def asset_telemetry_reading_trigger_request(request, pk):
    reading = assets_object(request, AssetTelemetryReading, pk)
    if reading.triggered_maintenance_request:
        messages.info(request, f"Maintenance Request {reading.triggered_maintenance_request.number} already exists.")
        return redirect("assets:asset_maintenance_request_detail", pk=reading.triggered_maintenance_request.pk)

    urgency = "critical" if reading.threshold_status == "critical" else "high"
    is_breakdown = reading.threshold_status == "critical"

    req = AssetMaintenanceRequest.objects.create(
        tenant=request.tenant,
        title=f"Telemetry Alert ({reading.get_metric_type_display()}): {reading.reading_value} {reading.metric_unit}",
        fixed_asset=reading.fixed_asset,
        operational_asset=reading.operational_asset,
        requester=request.user,
        request_type="breakdown_repair" if is_breakdown else "preventive_inspection",
        urgency=urgency,
        is_breakdown=is_breakdown,
        symptom_description=(
            f"Automated alert triggered from telemetry reading {reading.number}.\n"
            f"Sensor ID: {reading.sensor_identifier or 'Unspecified'}\n"
            f"Metric: {reading.get_metric_type_display()}\n"
            f"Measured Value: {reading.reading_value} {reading.metric_unit} (Baseline: {reading.baseline_value or 'N/A'})\n"
            f"Deviation: {reading.deviation_percentage or 0}%\n"
            f"Threshold Status: {reading.get_threshold_status_display()}\n"
            f"Notes: {reading.alert_notes}"
        ),
    )
    reading.triggered_maintenance_request = req
    reading.save(update_fields=["triggered_maintenance_request", "updated_at"])
    write_audit_log(request.user, reading, "update", tenant=request.tenant)
    write_audit_log(request.user, req, "create", tenant=request.tenant)

    messages.success(request, f"Created Maintenance Request {req.number} from Telemetry Reading {reading.number}.")
    return redirect("assets:asset_maintenance_request_detail", pk=req.pk)


@login_required
@require_POST
def asset_telemetry_reading_flag_anomaly(request, pk):
    reading = assets_object(request, AssetTelemetryReading, pk)
    reading.is_anomaly = True
    reading.threshold_status = "anomaly_detected"
    if not reading.anomaly_confidence:
        reading.anomaly_confidence = 95.0
    reading.save(update_fields=["is_anomaly", "threshold_status", "anomaly_confidence", "updated_at"])
    write_audit_log(request.user, reading, "update", tenant=request.tenant)
    messages.warning(request, f"Reading {reading.number} flagged as Anomaly Detected.")
    return redirect("assets:asset_telemetry_reading_detail", pk=reading.pk)

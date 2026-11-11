from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.IntegrationApiHub.AssetTelemetryStreams import (
    AssetTelemetryStreamForm,
)
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import (
    AssetMaintenanceRequest,
)
from apps.assets.models.AssetReliability.AssetTelemetryReadings import (
    AssetTelemetryReading,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
)
from apps.assets.models.IntegrationApiHub.AssetTelemetryStreams import (
    AssetTelemetryStream,
)
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.scm.models import Asset


@login_required
def stream_list(request):
    """List tenant-scoped IoT/SCADA Telemetry Streams with KPI counts and filters."""
    base_qs = assets_scope(
        AssetTelemetryStream.objects.select_related(
            "connector",
            "operational_asset",
            "fixed_asset",
            "steward",
            "last_telemetry_reading",
            "latest_maintenance_request",
        ),
        request,
    )

    kpis = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(stream_status="active")),
        faulted=Count("id", filter=Q(stream_status="faulted")),
        auto_cbm=Count("id", filter=Q(auto_trigger_maintenance=True)),
    )

    qs = base_qs
    q = (request.GET.get("q") or "").strip()
    connector_id = (request.GET.get("connector") or "").strip()
    asset_id = (request.GET.get("operational_asset") or "").strip()
    stream_protocol = (request.GET.get("stream_protocol") or "").strip()
    stream_status = (request.GET.get("stream_status") or "").strip()

    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(stream_name__icontains=q)
            | Q(tag_address__icontains=q)
            | Q(connector__number__icontains=q)
            | Q(connector__name__icontains=q)
        )
    if connector_id.isdigit():
        qs = qs.filter(connector_id=int(connector_id))
    if asset_id.isdigit():
        qs = qs.filter(operational_asset_id=int(asset_id))
    if stream_protocol in dict(AssetTelemetryStream.STREAM_PROTOCOL_CHOICES):
        qs = qs.filter(stream_protocol=stream_protocol)
    if stream_status in dict(AssetTelemetryStream.STREAM_STATUS_CHOICES):
        qs = qs.filter(stream_status=stream_status)

    paginator = Paginator(qs.order_by("number"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    connectors = assets_scope(AssetIntegrationConnector.objects.all(), request).order_by(
        "number"
    )
    assets_list = assets_scope(Asset.objects.all(), request).order_by("code")

    context = {
        "streams": page_obj,
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": kpis["total"] or 0,
        "active_count": kpis["active"] or 0,
        "faulted_count": kpis["faulted"] or 0,
        "auto_cbm_count": kpis["auto_cbm"] or 0,
        "connectors": connectors,
        "assets_list": assets_list,
        "protocol_choices": AssetTelemetryStream.STREAM_PROTOCOL_CHOICES,
        "status_choices": AssetTelemetryStream.STREAM_STATUS_CHOICES,
        "search_query": q,
    }
    return render(
        request,
        "assets/integrationapihub/asset_telemetry_stream/list.html",
        context,
    )


@login_required
def stream_create(request):
    """Create a new Asset Telemetry Stream."""
    if request.tenant is None:
        messages.error(
            request,
            "An active tenant workspace is required to create a telemetry stream.",
        )
        return redirect("assets:asset_telemetry_stream_list")
    if request.method == "POST":
        form = AssetTelemetryStreamForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                stream = form.save(commit=False)
                stream.tenant = request.tenant
                stream.save()
                write_audit_log(
                    request.user,
                    stream,
                    "create",
                    changes={
                        "number": stream.number,
                        "connector": stream.connector.number,
                        "tag_address": stream.tag_address,
                    },
                    tenant=request.tenant,
                )
            messages.success(
                request, f"Telemetry stream {stream.number} created successfully."
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)
    else:
        initial = {}
        connector_id = (request.GET.get("connector") or "").strip()
        if connector_id.isdigit():
            initial["connector"] = int(connector_id)
        form = AssetTelemetryStreamForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/integrationapihub/asset_telemetry_stream/form.html",
        {
            "form": form,
            "stream": None,
            "is_edit": False,
            "title": "New Telemetry Stream",
        },
    )


@login_required
def stream_detail(request, pk):
    """Display telemetry stream configuration, ingestion form, and recent AssetTelemetryReadings."""
    stream = assets_object(
        request,
        AssetTelemetryStream,
        pk,
        select_related=(
            "connector",
            "operational_asset",
            "fixed_asset",
            "steward",
            "last_telemetry_reading",
            "latest_maintenance_request",
        ),
    )

    readings_qs = AssetTelemetryReading.objects.filter(
        tenant=stream.tenant
    ).select_related("operational_asset", "fixed_asset", "recorded_by")
    if stream.operational_asset_id:
        readings_qs = readings_qs.filter(operational_asset_id=stream.operational_asset_id)
    elif stream.fixed_asset_id:
        readings_qs = readings_qs.filter(fixed_asset_id=stream.fixed_asset_id)
    else:
        readings_qs = readings_qs.none()

    recent_readings = readings_qs.order_by("-recorded_at", "-pk")[:10]

    return render(
        request,
        "assets/integrationapihub/asset_telemetry_stream/detail.html",
        {
            "stream": stream,
            "recent_readings": recent_readings,
        },
    )


@login_required
def stream_edit(request, pk):
    """Edit an existing Asset Telemetry Stream."""
    stream = assets_object(request, AssetTelemetryStream, pk)
    if request.method == "POST":
        form = AssetTelemetryStreamForm(
            request.POST, instance=stream, tenant=stream.tenant
        )
        if form.is_valid():
            with transaction.atomic():
                stream = form.save()
                write_audit_log(
                    request.user,
                    stream,
                    "update",
                    changes={
                        "number": stream.number,
                        "stream_status": stream.stream_status,
                    },
                    tenant=stream.tenant,
                )
            messages.success(
                request, f"Telemetry stream {stream.number} updated successfully."
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)
    else:
        form = AssetTelemetryStreamForm(instance=stream, tenant=stream.tenant)

    return render(
        request,
        "assets/integrationapihub/asset_telemetry_stream/form.html",
        {
            "form": form,
            "stream": stream,
            "is_edit": True,
            "title": f"Edit {stream.number} — {stream.stream_name}",
        },
    )


@tenant_admin_required
@require_POST
def stream_delete(request, pk):
    """Delete a tenant-scoped Asset Telemetry Stream."""
    stream = assets_object(request, AssetTelemetryStream, pk)
    label = str(stream)
    with transaction.atomic():
        write_audit_log(
            request.user,
            stream,
            "delete",
            changes={"number": stream.number, "tag_address": stream.tag_address},
            tenant=stream.tenant,
        )
        stream.delete()
    messages.success(request, f"Telemetry stream {label} deleted.")
    return redirect("assets:asset_telemetry_stream_list")


@login_required
@require_POST
def ingest_sample_reading(request, pk):
    """Normalize a simulated/sample payload into 11.7 AssetTelemetryReading and trigger 11.5 CBM if critical."""
    raw_input = (request.POST.get("raw_value") or "").strip()

    with transaction.atomic():
        stream = get_object_or_404(
            AssetTelemetryStream.objects.select_for_update(),
            pk=pk,
            tenant=request.tenant,
        )
        if stream.stream_status != "active":
            messages.error(
                request,
                f"Stream {stream.number} is {stream.get_stream_status_display()} and must be Active to ingest readings.",
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

        connector = stream.connector
        op_asset = stream.operational_asset
        fixed_asset = stream.fixed_asset
        existing_mr = stream.latest_maintenance_request

        for fk_label, rel in (
            ("Connector", connector),
            ("Operational asset", op_asset),
            ("Fixed asset", fixed_asset),
        ):
            if rel is not None and getattr(rel, "tenant_id", None) != stream.tenant_id:
                messages.error(
                    request,
                    f"Cannot ingest into {stream.number}: {fk_label} belongs to another workspace.",
                )
                return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

        if raw_input:
            if len(raw_input) > 32:
                messages.error(
                    request,
                    "Raw telemetry reading exceeds maximum input length (32 characters).",
                )
                return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)
            try:
                raw_val = Decimal(raw_input)
            except (InvalidOperation, ValueError):
                messages.error(
                    request, "Raw telemetry reading must be a valid decimal number."
                )
                return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)
            if not raw_val.is_finite():
                messages.error(request, "Raw telemetry reading must be finite.")
                return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)
        else:
            raw_val = (
                stream.warning_threshold
                if stream.warning_threshold is not None
                else (
                    stream.baseline_value
                    if stream.baseline_value is not None
                    else Decimal("25.0000")
                )
            )

        try:
            if abs(raw_val) > Decimal("999999999999"):
                raise InvalidOperation("Raw reading magnitude out of bounds.")
            normalized = (raw_val * stream.scale_factor + stream.offset_value).quantize(
                Decimal("0.0001")
            )
        except (InvalidOperation, ArithmeticError):
            messages.error(
                request,
                "Raw telemetry reading is outside the supported decimal precision/range.",
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

        if not normalized.is_finite() or abs(normalized) > Decimal("99999999.9999"):
            messages.error(
                request,
                "Normalized telemetry reading must be between -99,999,999.9999 and 99,999,999.9999.",
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

        now = timezone.now()

        if (
            stream.deadband_delta
            and stream.deadband_delta > Decimal("0")
            and stream.last_ingested_value is not None
            and abs(normalized - stream.last_ingested_value) < stream.deadband_delta
        ):
            stream.last_ingested_at = now
            stream.save(update_fields=["last_ingested_at", "updated_at"])
            messages.info(
                request,
                f"Sample reading {normalized} fell within deadband delta ({stream.deadband_delta}); no duplicate telemetry reading recorded.",
            )
            return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

        mapped_metric_type, mapped_unit, note = (
            stream.resolve_telemetry_metric_and_unit()
        )
        computed_status = stream.evaluate_reading_status(normalized)
        reading_source = (
            "scada_historian"
            if connector.connector_category == "iot_scada"
            else "iot_sensor"
        )

        open_mr_statuses = ("submitted", "triaged", "assigned", "in_progress")
        existing_open_mr = (
            existing_mr
            if (
                existing_mr is not None
                and existing_mr.tenant_id == stream.tenant_id
                and existing_mr.status in open_mr_statuses
            )
            else None
        )

        maint_req = None
        if (
            computed_status == "critical"
            and stream.auto_trigger_maintenance
            and existing_open_mr is None
        ):
            maint_req = AssetMaintenanceRequest.objects.create(
                tenant=stream.tenant,
                title=f"IoT Critical Alert: {stream.stream_name} ({stream.number})"[
                    :255
                ],
                fixed_asset=fixed_asset,
                operational_asset=op_asset,
                requester=request.user,
                request_type="breakdown_repair",
                urgency="critical",
                is_breakdown=True,
                downtime_started_at=now,
                symptom_description=(
                    f"Telemetry stream {stream.number} (tag {stream.tag_address}) "
                    f"recorded normalized value {normalized} {stream.get_metric_unit_display()}, "
                    f"breaching critical threshold {stream.critical_threshold}."
                ),
            )
            stream.latest_maintenance_request = maint_req

        reading = AssetTelemetryReading.objects.create(
            tenant=stream.tenant,
            operational_asset=op_asset,
            fixed_asset=fixed_asset,
            sensor_identifier=stream.tag_address[:100],
            recorded_by=request.user,
            recorded_at=now,
            source=reading_source,
            metric_type=mapped_metric_type,
            metric_unit=mapped_unit,
            reading_value=normalized,
            baseline_value=stream.baseline_value,
            threshold_status=computed_status,
            alert_notes=note,
            triggered_maintenance_request=maint_req,
        )
        # AssetTelemetryReading.save() recalculates % deviation against baseline; preserve stream threshold classification cleanly.
        if (
            stream.warning_threshold is not None
            or stream.critical_threshold is not None
        ) and reading.threshold_status != computed_status:
            AssetTelemetryReading.objects.filter(pk=reading.pk).update(
                threshold_status=computed_status
            )
            reading.threshold_status = computed_status

        stream.last_ingested_value = normalized
        stream.last_ingested_at = now
        stream.readings_ingested_count = (stream.readings_ingested_count or 0) + 1
        stream.last_telemetry_reading = reading
        update_fields = [
            "last_ingested_value",
            "last_ingested_at",
            "readings_ingested_count",
            "last_telemetry_reading",
            "updated_at",
        ]
        if maint_req is not None:
            update_fields.append("latest_maintenance_request")
        stream.save(update_fields=update_fields)

        write_audit_log(
            request.user,
            stream,
            "ingest",
            changes={
                "reading": reading.number,
                "normalized_value": str(normalized),
                "threshold_status": computed_status,
                "maintenance_request": maint_req.number if maint_req else None,
            },
            tenant=stream.tenant,
        )

    if maint_req is not None:
        messages.warning(
            request,
            f"Ingested {normalized} -> {reading.number} (CRITICAL). Auto-created maintenance request {maint_req.number}.",
        )
    elif computed_status == "critical" and existing_open_mr is not None:
        messages.warning(
            request,
            f"Ingested {normalized} -> {reading.number} (CRITICAL). Existing open maintenance request {existing_open_mr.number} remains active.",
        )
    else:
        messages.success(
            request,
            f"Ingested {normalized} -> {reading.number} ({computed_status.upper()}).",
        )
    return redirect("assets:asset_telemetry_stream_detail", pk=stream.pk)

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.assets.models.AssetInventoryTracking.AssetAudits import AssetAudit
from apps.assets.models.AssetInventoryTracking.AssetCustodyLogs import AssetCustodyLog
from apps.assets.models.AssetInventoryTracking.AssetIncidentReports import AssetIncidentReport
from apps.assets.models.AssetInventoryTracking.AssetMovementLogs import AssetMovementLog
from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.assets.models.AssetProcurement.AssetTags import AssetTag
from apps.assets.models.IntegrationApiHub.AssetGisMappings import AssetGisMapping
from apps.assets.models.IntegrationApiHub.AssetGlSyncBatches import AssetGlSyncBatch
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import AssetIntegrationConnector
from apps.assets.models.IntegrationApiHub.AssetTelemetryStreams import AssetTelemetryStream
from apps.assets.views._common import assets_scope


@login_required
def overview(request):
    """Command center and analytics overview for Module 11 Asset Management System."""
    req_qs = assets_scope(AssetRequisition.objects.all(), request)
    rcv_qs = assets_scope(AssetAcquisitionReceipt.objects.all(), request)
    cap_qs = assets_scope(AssetCapitalization.objects.all(), request)
    tag_qs = assets_scope(AssetTag.objects.all(), request)

    audit_qs = assets_scope(AssetAudit.objects.all(), request)
    mov_qs = assets_scope(AssetMovementLog.objects.all(), request)
    custody_qs = assets_scope(AssetCustodyLog.objects.all(), request)
    inc_qs = assets_scope(AssetIncidentReport.objects.all(), request)

    req_agg = req_qs.aggregate(
        total=Count("id"),
        pending_approval=Count("id", filter=Q(status="pending_approval")),
    )
    rcv_agg = rcv_qs.aggregate(
        total=Count("id"),
        pending_inspection=Count("id", filter=Q(status="draft")),
    )
    cap_agg = cap_qs.aggregate(
        total=Count("id"),
        total_capex=Sum("total_cost_basis", filter=Q(status="capitalized")),
    )
    tag_agg = tag_qs.aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(is_verified=True)),
    )

    audit_agg = audit_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=["scheduled", "in_progress"])),
    )
    mov_agg = mov_qs.aggregate(
        total=Count("id"),
        in_transit=Count("id", filter=Q(status__in=["dispatched", "in_transit"])),
    )
    custody_agg = custody_qs.aggregate(
        total=Count("id"),
        active_loans=Count("id", filter=Q(status="active_loan")),
        overdue=Count("id", filter=Q(status="overdue")),
    )
    inc_agg = inc_qs.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=["reported", "under_investigation", "write_off_pending"])),
    )

    conn_agg = assets_scope(AssetIntegrationConnector.objects.all(), request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )
    stream_agg = assets_scope(AssetTelemetryStream.objects.all(), request).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(stream_status="active")),
    )
    gl_batch_agg = assets_scope(AssetGlSyncBatch.objects.all(), request).aggregate(
        total=Count("id"),
        posted=Count("id", filter=Q(status__in=["posted", "reconciled"])),
    )
    gis_agg = assets_scope(AssetGisMapping.objects.all(), request).aggregate(
        total=Count("id"),
        drifted=Count("id", filter=Q(drift_status__in=["location_drift", "attribute_drift"])),
    )

    kpis = {
        "total_requisitions": req_agg["total"],
        "pending_approval_reqs": req_agg["pending_approval"],
        "total_receipts": rcv_agg["total"],
        "pending_inspection_rcvs": rcv_agg["pending_inspection"],
        "total_capitalizations": cap_agg["total"],
        "capitalized_value": cap_agg["total_capex"] or Decimal("0.00"),
        "total_tags": tag_agg["total"],
        "verified_tags": tag_agg["verified"],
        "total_audits": audit_agg["total"],
        "active_audits": audit_agg["active"],
        "total_movements": mov_agg["total"],
        "in_transit_movements": mov_agg["in_transit"],
        "total_custody_loans": custody_agg["total"],
        "active_custody_loans": custody_agg["active_loans"],
        "overdue_custody_loans": custody_agg["overdue"],
        "total_incidents": inc_agg["total"],
        "open_incidents": inc_agg["open"],
        "total_connectors": conn_agg["total"],
        "active_connectors": conn_agg["active"],
        "total_streams": stream_agg["total"],
        "active_streams": stream_agg["active"],
        "total_gl_batches": gl_batch_agg["total"],
        "posted_gl_batches": gl_batch_agg["posted"],
        "total_gis_mappings": gis_agg["total"],
        "drifted_gis_mappings": gis_agg["drifted"],
    }

    recent_requisitions = req_qs.select_related("currency", "proposed_vendor").order_by("-created_at")[:5]
    recent_receipts = rcv_qs.select_related("vendor", "receiving_location").order_by("-created_at")[:5]
    recent_capitalizations = cap_qs.select_related("fixed_asset").order_by("-created_at")[:5]
    recent_tags = tag_qs.select_related("operational_asset").order_by("-created_at")[:5]
    recent_audits = audit_qs.select_related("target_location").order_by("-created_at")[:5]
    recent_movements = mov_qs.select_related("asset", "from_location", "to_location").order_by("-created_at")[:5]

    context = {
        "kpis": kpis,
        "recent_requisitions": recent_requisitions,
        "recent_receipts": recent_receipts,
        "recent_capitalizations": recent_capitalizations,
        "recent_tags": recent_tags,
        "recent_audits": recent_audits,
        "recent_movements": recent_movements,
    }
    return render(request, "assets/overview.html", context)

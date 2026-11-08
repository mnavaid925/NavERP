from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.models.AssetProcurement.AssetCapitalizations import AssetCapitalization
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.assets.models.AssetProcurement.AssetTags import AssetTag
from apps.assets.views._common import assets_scope


@login_required
def overview(request):
    """Command center and analytics overview for Module 11 Asset Management System."""
    req_qs = assets_scope(AssetRequisition.objects.all(), request)
    rcv_qs = assets_scope(AssetAcquisitionReceipt.objects.all(), request)
    cap_qs = assets_scope(AssetCapitalization.objects.all(), request)
    tag_qs = assets_scope(AssetTag.objects.all(), request)

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

    kpis = {
        "total_requisitions": req_agg["total"],
        "pending_approval_reqs": req_agg["pending_approval"],
        "total_receipts": rcv_agg["total"],
        "pending_inspection_rcvs": rcv_agg["pending_inspection"],
        "total_capitalizations": cap_agg["total"],
        "capitalized_value": cap_agg["total_capex"] or Decimal("0.00"),
        "total_tags": tag_agg["total"],
        "verified_tags": tag_agg["verified"],
    }

    recent_requisitions = req_qs.select_related("currency", "proposed_vendor").order_by("-created_at")[:5]
    recent_receipts = rcv_qs.select_related("vendor", "receiving_location").order_by("-created_at")[:5]
    recent_capitalizations = cap_qs.select_related("fixed_asset").order_by("-created_at")[:5]
    recent_tags = tag_qs.select_related("operational_asset").order_by("-created_at")[:5]

    context = {
        "kpis": kpis,
        "recent_requisitions": recent_requisitions,
        "recent_receipts": recent_receipts,
        "recent_capitalizations": recent_capitalizations,
        "recent_tags": recent_tags,
    }
    return render(request, "assets/overview.html", context)

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
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

    total_capex = cap_qs.filter(status="capitalized").aggregate(total=Sum("total_cost_basis"))["total"] or Decimal("0.00")

    kpis = {
        "total_requisitions": req_qs.count(),
        "pending_approval_reqs": req_qs.filter(status="pending_approval").count(),
        "total_receipts": rcv_qs.count(),
        "pending_inspection_rcvs": rcv_qs.filter(status="pending_inspection").count(),
        "total_capitalizations": cap_qs.count(),
        "capitalized_value": total_capex,
        "total_tags": tag_qs.count(),
        "verified_tags": tag_qs.filter(is_verified=True).count(),
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

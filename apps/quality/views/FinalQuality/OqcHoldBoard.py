from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from apps.quality.models.FinalQuality.CertificatesOfConformance import CertificateOfConformance
from apps.quality.models.FinalQuality.FinalInspectionLots import FinalInspectionLot
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorization


@login_required
def oqc_hold_board(request):
    tenant = request.tenant

    # Active Holds
    active_holds_lots = FinalInspectionLot.objects.filter(
        tenant=tenant,
        is_on_hold=True,
    ).select_related("customer", "sales_order", "inspector").order_by("-updated_at")

    active_holds_releases = QualityReleaseAuthorization.objects.filter(
        tenant=tenant,
        is_on_hold=True,
    ).select_related("customer", "shipment", "releasing_officer").order_by("-updated_at")

    # Pending Inspections
    pending_inspection_lots = FinalInspectionLot.objects.filter(
        tenant=tenant,
        usage_decision="pending",
    ).select_related("customer", "inspector").order_by("-created_at")[:10]

    # Pending CoCs awaiting signature
    pending_cocs = CertificateOfConformance.objects.filter(
        tenant=tenant,
        status__in=["draft", "under_review"],
    ).select_related("customer").order_by("-created_at")[:10]

    # Ready Releases (cleared to ship)
    ready_releases = QualityReleaseAuthorization.objects.filter(
        tenant=tenant,
        status="authorized",
        release_disposition__in=["released_full", "conditional_release"],
        is_on_hold=False,
    ).select_related("customer", "shipment").order_by("-updated_at")[:10]

    context = {
        "active_holds_lots": active_holds_lots,
        "active_holds_releases": active_holds_releases,
        "pending_inspection_lots": pending_inspection_lots,
        "pending_cocs": pending_cocs,
        "ready_releases": ready_releases,
        "hold_lot_count": active_holds_lots.count(),
        "hold_release_count": active_holds_releases.count(),
        "pending_lot_count": pending_inspection_lots.count(),
        "pending_coc_count": pending_cocs.count(),
        "ready_release_count": ready_releases.count(),
    }
    return render(request, "quality/finalquality/oqc_hold_board.html", context)

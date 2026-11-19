from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from apps.quality.models.FinalQuality.CertificatesOfConformance import CertificateOfConformance
from apps.quality.models.FinalQuality.FinalInspectionLots import FinalInspectionLot
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorization


@login_required
def oqc_hold_board(request):
    tenant = request.tenant

    # Active Holds (pre-evaluated to avoid duplicate SQL queries)
    active_holds_lots = list(
        FinalInspectionLot.objects.filter(
            tenant=tenant,
            is_on_hold=True,
        ).select_related("customer", "sales_order", "inspector").order_by("-updated_at")
    )
    active_holds_releases = list(
        QualityReleaseAuthorization.objects.filter(
            tenant=tenant,
            is_on_hold=True,
        ).select_related("customer", "shipment", "releasing_officer").order_by("-updated_at")
    )

    # Pending Inspections count (dead queryset omitted from context)
    pending_lot_count = FinalInspectionLot.objects.filter(
        tenant=tenant,
        usage_decision="pending",
    ).count()

    # Pending CoCs awaiting signature (count computed on unsliced queryset)
    pending_cocs_qs = CertificateOfConformance.objects.filter(
        tenant=tenant,
        status__in=["draft", "under_review"],
    ).select_related("customer").order_by("-created_at")
    pending_coc_count = pending_cocs_qs.count()
    pending_cocs = pending_cocs_qs[:10]

    # Ready Releases cleared to ship (prerequisite flags aligned with is_cleared_to_ship)
    ready_releases_qs = QualityReleaseAuthorization.objects.filter(
        tenant=tenant,
        status="authorized",
        release_disposition__in=["released_full", "conditional_release"],
        is_on_hold=False,
        final_inspection_passed=True,
        no_open_ncrs_or_capas=True,
        packaging_label_approved=True,
        coc_issued_and_signed=True,
    ).select_related("customer", "shipment").order_by("-updated_at")
    ready_release_count = ready_releases_qs.count()
    ready_releases = ready_releases_qs[:10]

    context = {
        "active_holds_lots": active_holds_lots,
        "active_holds_releases": active_holds_releases,
        "pending_cocs": pending_cocs,
        "ready_releases": ready_releases,
        "hold_lot_count": len(active_holds_lots),
        "hold_release_count": len(active_holds_releases),
        "pending_lot_count": pending_lot_count,
        "pending_coc_count": pending_coc_count,
        "ready_release_count": ready_release_count,
    }
    return render(request, "quality/finalquality/oqc_hold_board.html", context)

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout
from apps.ecommerce.models.Marketplace.VendorProductListings import VendorProductListing
from apps.ecommerce.models.Marketplace.VendorSubOrders import VendorSubOrder
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def marketplace_console(request):
    vendors_qs = ecommerce_scope(MarketplaceVendor.objects.all(), request)
    listings_qs = ecommerce_scope(VendorProductListing.objects.all(), request)
    suborders_qs = ecommerce_scope(VendorSubOrder.objects.all(), request)
    payouts_qs = ecommerce_scope(VendorPayout.objects.all(), request)

    total_vendors = vendors_qs.count()
    pending_kyc_count = vendors_qs.filter(kyc_status="pending").count()
    pending_moderation_count = listings_qs.filter(moderation_status="pending_review").count()
    open_disputes_count = suborders_qs.filter(
        dispute_status__in=["disputed", "under_investigation", "escalated_to_admin"]
    ).count()

    unpaid_payouts_sum = (
        payouts_qs.filter(payout_status__in=["draft", "pending_approval", "processing"]).aggregate(
            total=Sum("net_payout_amount")
        )["total"]
        or Decimal("0.00")
    )

    metrics = {
        "total_vendors": total_vendors,
        "pending_kyc_count": pending_kyc_count,
        "pending_moderation_count": pending_moderation_count,
        "open_disputes_count": open_disputes_count,
        "unpaid_payouts_sum": unpaid_payouts_sum,
    }

    pending_kyc_vendors = vendors_qs.filter(kyc_status__in=["pending", "unsubmitted"]).order_by("-updated_at")[:5]
    pending_listings = listings_qs.filter(moderation_status="pending_review").select_related("vendor", "product")[:5]
    sla_risk_suborders = (
        suborders_qs.filter(
            sla_status__in=["near_breach", "breached"],
            fulfillment_status__in=["unfulfilled", "allocated", "picking", "packed"],
        )
        .select_related("vendor", "order")
        .order_by("promised_dispatch_date")[:5]
    )
    active_disputes = (
        suborders_qs.filter(dispute_status__in=["disputed", "under_investigation", "escalated_to_admin"])
        .select_related("vendor", "order")
        .order_by("-updated_at")[:5]
    )

    context = {
        "title": "Marketplace & Multi-Vendor Operations Console",
        "metrics": metrics,
        "pending_kyc_vendors": pending_kyc_vendors,
        "pending_listings": pending_listings,
        "sla_risk_suborders": sla_risk_suborders,
        "active_disputes": active_disputes,
    }
    return render(request, "ecommerce/marketplace/console/dashboard.html", context)

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def inventory_operations(request):
    centers = ecommerce_scope(FulfillmentCenter.objects.all(), request)
    allocations = ecommerce_scope(InventoryAllocation.objects.select_related("product", "variant", "fulfillment_center"), request)
    backorders = ecommerce_scope(BackorderPolicy.objects.select_related("variant", "variant__product"), request)
    syncs = ecommerce_scope(ChannelInventorySync.objects.select_related("variant__product", "fulfillment_center"), request)

    # Aggregates
    totals = allocations.aggregate(
        total_on_hand=Sum("quantity_on_hand"),
        total_allocated=Sum("quantity_allocated"),
        total_safety_buffer=Sum("safety_stock_buffer"),
    )

    total_on_hand = totals["total_on_hand"] or 0
    total_allocated = totals["total_allocated"] or 0
    total_safety_buffer = totals["total_safety_buffer"] or 0
    total_atp = max(0, total_on_hand - total_allocated - total_safety_buffer)

    low_stock_allocations = allocations.filter(is_low_stock_alert=True)[:15]
    low_stock_count = allocations.filter(is_low_stock_alert=True).count()
    active_backorders = backorders.filter(is_active=True).count()
    active_centers = centers.filter(is_active=True).count()

    recent_syncs = syncs.order_by("-last_synced_at", "-created_at")[:10]
    recent_backorders = backorders.order_by("-updated_at")[:10]

    kpis = {
        "total_on_hand": total_on_hand,
        "total_allocated": total_allocated,
        "total_atp": total_atp,
        "low_stock_count": low_stock_count,
        "active_backorders": active_backorders,
        "active_centers": active_centers,
    }

    context = {
        "kpis": kpis,
        "centers": centers[:10],
        "low_stock_allocations": low_stock_allocations,
        "recent_syncs": recent_syncs,
        "recent_backorders": recent_backorders,
    }
    return render(request, "ecommerce/inventorystock/overview.html", context)

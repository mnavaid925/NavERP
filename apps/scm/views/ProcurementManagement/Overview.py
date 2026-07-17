"""SCM module landing page — the procure-to-pay pipeline + supplier + inventory at a glance."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.models import (
    GoodsReceiptNote,
    Item,
    PurchaseOrder,
    PurchaseRequisition,
    ReorderRule,
    RFQ,
    StockMove,
    SupplierProfile,
)


@login_required
def overview(request):
    """Counts down the procure-to-pay chain plus supplier + inventory KPIs and the exception queues.

    Every count is a tenant-scoped aggregate — nothing here is stored.
    """
    tenant = request.tenant
    requisitions = PurchaseRequisition.objects.filter(tenant=tenant)
    rfqs = RFQ.objects.filter(tenant=tenant)
    orders = PurchaseOrder.objects.filter(tenant=tenant)
    receipts = GoodsReceiptNote.objects.filter(tenant=tenant)

    open_order_value = orders.exclude(status__in=PurchaseOrder.CLOSED_STATUSES).aggregate(
        s=Sum("total"))["s"] or Decimal("0")
    # 4.3 inventory: total stock value = Σ quantity×unit_cost over the whole ledger.
    stock_value = StockMove.objects.filter(tenant=tenant).aggregate(
        v=Sum(F("quantity") * F("unit_cost"),
              output_field=models.DecimalField(max_digits=20, decimal_places=4)))["v"] or Decimal("0")
    # Low-stock: reorder rules whose derived on-hand is at/below their point (Python, small set).
    low_stock = [r for r in ReorderRule.objects.filter(tenant=tenant, is_active=True)
                 .select_related("item", "location") if r.is_below_point()]

    return render(request, "scm/overview.html", {
        "stats": {
            "requisitions": requisitions.count(),
            "requisitions_pending": requisitions.filter(status="pending_approval").count(),
            "rfqs": rfqs.count(),
            "rfqs_open": rfqs.filter(status="sent").count(),
            "orders": orders.count(),
            "orders_pending": orders.filter(status="pending_approval").count(),
            "receipts": receipts.count(),
            "open_order_value": open_order_value,
            "suppliers": SupplierProfile.objects.filter(tenant=tenant).count(),
            "items": Item.objects.filter(tenant=tenant, is_active=True).count(),
            "stock_value": stock_value.quantize(Decimal("0.01")),
            "low_stock": len(low_stock),
        },
        # The exception queues — what a buyer actually opens this page to find.
        "awaiting_approval": (requisitions.filter(status="pending_approval")
                              .select_related("requester", "org_unit")[:8]),
        "unmatched_receipts": (receipts.filter(status="received")
                               .exclude(match_status="matched")
                               .select_related("purchase_order", "purchase_order__vendor")[:8]),
        "low_stock": low_stock[:8],
    })

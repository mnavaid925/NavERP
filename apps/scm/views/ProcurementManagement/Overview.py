"""SCM module landing page — the procure-to-pay pipeline at a glance."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.models import (
    GoodsReceiptNote,
    PurchaseOrder,
    PurchaseRequisition,
    RFQ,
)


@login_required
def overview(request):
    """Counts down the procure-to-pay chain plus whatever currently needs a human.

    Every count is a tenant-scoped aggregate — nothing here is stored.
    """
    tenant = request.tenant
    requisitions = PurchaseRequisition.objects.filter(tenant=tenant)
    rfqs = RFQ.objects.filter(tenant=tenant)
    orders = PurchaseOrder.objects.filter(tenant=tenant)
    receipts = GoodsReceiptNote.objects.filter(tenant=tenant)

    open_order_value = orders.exclude(status__in=PurchaseOrder.CLOSED_STATUSES).aggregate(
        s=Sum("total"))["s"] or Decimal("0")

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
        },
        # The exception queues — what a buyer actually opens this page to find.
        "awaiting_approval": (requisitions.filter(status="pending_approval")
                              .select_related("requester", "org_unit")[:8]),
        "unmatched_receipts": (receipts.filter(status="received")
                               .exclude(match_status="matched")
                               .select_related("purchase_order", "purchase_order__vendor")[:8]),
    })

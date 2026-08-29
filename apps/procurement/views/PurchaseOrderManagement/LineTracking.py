"""Procurement 6.10 Purchase Order Management — per-line delivery tracking board.

**PO Line Item Tracking** bullet: granular tracking of delivery status for individual line
items. A COMPUTED page — zero writes, zero new state: the same one-aggregation-per-row rule the
spine uses (received quantities are derived from goods-receipt lines, never stored), extended
across every order in the workspace at once.
"""
from decimal import Decimal

from django.db.models import F, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder, PurchaseOrderLine


@login_required
def po_line_tracking(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view line tracking.")
        return redirect("dashboard:home")
    qs = (PurchaseOrderLine.objects
          .filter(purchase_order__tenant=request.tenant)
          .select_related("purchase_order", "purchase_order__vendor", "gl_account")
          .annotate(
              # Same cancelled-receipts-excluded rule as PurchaseOrder.received_by_line(); the
              # Coalesce turns the no-receipts NULL into a zero so the template can subtract.
              received_qty=Coalesce(
                  Sum("receipt_lines__quantity_received",
                      filter=~Q(receipt_lines__goods_receipt__status="cancelled")),
                  Value(Decimal("0"))),
              outstanding_qty=F("quantity") - F("received_qty"),
          )
          .order_by("-purchase_order__order_date", "-purchase_order_id", "id"))
    return crud_list(
        request, qs, "procurement/purchaseordermanagement/linetracking.html",
        search_fields=["item_description", "sku_hint", "purchase_order__number"],
        filters=[("status", "purchase_order__status", False)],
        extra_context={"status_choices": PurchaseOrder.STATUS_CHOICES},
    )

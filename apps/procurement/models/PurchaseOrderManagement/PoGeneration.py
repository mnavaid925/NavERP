"""Procurement 6.10 Purchase Order Management — requisition -> PO generation service.

**PO Generation** bullet: automated creation of POs from approved requisitions (manual entry
already lives on the spine at ``scm:purchaseorder_create``). Before this module the ONLY
requisition->order path ran through 6.5/6.6 sourcing (RFQ -> quote award sets
``requisition.status = "converted"``); buyers who skip competitive sourcing had no direct route.

``generate_po_from_requisition()`` drafts a REAL ``scm.PurchaseOrder`` (+ its lines) inside the
caller's transaction, copying the free-text line stand-ins (L28), GL account codes and the
requisition's currency/org-unit context. The requisition is NOT flipped to ``converted``:
unlike an award (exactly one winner), an approved requisition may legitimately be split across
several vendors/orders — the generation console counts linked POs instead, so commitment
reporting via ``PurchaseRequisition.COMMITTED_STATUSES`` keeps working unchanged.
"""
from django.utils import timezone

from apps.procurement.models._base import ZERO


def convertible_requisitions(tenant):
    """Approved requisitions of this workspace, oldest backlog first — the generation queue."""
    from apps.scm.models import PurchaseRequisition

    if tenant is None:
        return PurchaseRequisition.objects.none()
    return (PurchaseRequisition.objects
            .filter(tenant=tenant, status="approved")
            .select_related("requester", "org_unit", "currency")
            .prefetch_related("lines", "purchase_orders", "purchase_orders__vendor")
            .order_by("created_at"))


def generate_po_from_requisition(requisition, vendor, expected_date=None):
    """Draft one purchase order from an approved requisition and return it.

    Caller contract (enforced in the view): runs inside ``transaction.atomic()`` with the
    requisition freshly locked and re-checked as ``approved``. The new order starts DRAFT on
    purpose — 4.1's submit/approve/send machinery owns how it reaches the vendor; generation
    merely saves the buyer the retyping.
    """
    from apps.scm.models import PurchaseOrder, PurchaseOrderLine

    earliest_needed = (requisition.lines.filter(needed_by__isnull=False)
                       .order_by("needed_by").values_list("needed_by", flat=True).first())
    order = PurchaseOrder.objects.create(
        tenant=requisition.tenant,
        vendor=vendor,
        requisition=requisition,
        currency=requisition.currency,
        ship_to=requisition.org_unit,
        order_date=timezone.now().date(),
        expected_date=expected_date or requisition.required_by or earliest_needed,
    )
    # Create through .save(), NOT bulk_create: line_total is DERIVED in the line's save()
    # (L28 spine rule) and bulk_create bypasses save() — the copy would land with zero totals.
    for line in requisition.lines.all():
        PurchaseOrderLine.objects.create(
            purchase_order=order,
            item_description=line.item_description,
            sku_hint=line.sku_hint,
            uom_hint=line.uom_hint,
            quantity=line.quantity,
            unit_price=line.estimated_unit_price or ZERO,
            gl_account=line.gl_account,
        )
    order.recalc_totals()
    return order

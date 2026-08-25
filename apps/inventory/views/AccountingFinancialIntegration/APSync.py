"""Inventory 5.18 Accounts Payable (AP) Integration — "Syncing POs and GRNs to create bills".

The queue is every RECEIVED goods receipt whose vendor bill has not been drafted yet;
the register below it shows what the sync already produced (the receipt keeps a
``scm.GoodsReceiptNote.bill`` pointer, so both sides of that question are one query
each). The verb drafts a DRAFT ``accounting.Bill`` — Module 2 owns the payable and its
posting; this hands it over exactly like 4.6's freight audit does (L29) — priced at the
PO's agreed unit prices, with each line's tax rate resolved by the TaxRule catalog
(product × vendor country) and the expense account carried over from the PO line.
Linking the bill re-runs the receipt's three-way match, so a synced receipt lands on
"matched" by construction.
"""
from decimal import Decimal

from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.accounting.models import Bill, BillLine
from apps.core.decorators import tenant_admin_required
from apps.inventory.models import TaxRule
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import GoodsReceiptNote

from . import _common

ZERO = Decimal("0")


def _scoped(tenant):
    """Every received receipt, annotated with its accepted value at PO prices."""
    return (GoodsReceiptNote.objects.filter(tenant=tenant, status="received")
            .select_related("purchase_order", "purchase_order__vendor", "bill")
            .annotate(received_total=Sum(
                F("lines__quantity_received") * F("lines__po_line__unit_price"),
                output_field=models.DecimalField()))
            # The joined annotate DROPS the model's default ordering — pin it explicitly
            # so pagination is stable.
            .order_by("-receipt_date", "-id"))


@login_required
def ap_sync(request):
    qs = _scoped(request.tenant)
    vendors = ({pk: name for pk, name in qs.values_list("purchase_order__vendor_id",
                                                        "purchase_order__vendor__name")}
               if request.tenant is not None else {})
    register = (qs.filter(bill__isnull=False)
                .select_related("bill", "purchase_order__vendor")
                .order_by("-receipt_date", "-id")[:10])
    return crud_list(
        request, qs.filter(bill__isnull=True), "inventory/finint/ap_sync.html",
        search_fields=["number", "purchase_order__number", "purchase_order__vendor__name"],
        filters=[("vendor", "purchase_order__vendor_id", True)],
        extra_context={
            "register": register,
            "vendors": sorted(vendors.items()),
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
@require_POST
def ap_sync_run(request, pk):
    grn = get_object_or_404(_scoped(request.tenant), pk=pk, bill__isnull=True)
    po = grn.purchase_order
    # PO lines are 4.1's free-text stand-in (item_description/sku_hint, NO item FK — L28),
    # so tax resolution here runs on GEOGRAPHY alone; AR's order lines carry a real
    # scm.Item FK and get the full product × country lookup.
    lines = list(grn.lines.select_related("po_line"))
    if not any((l.quantity_received or ZERO) > ZERO for l in lines):
        messages.error(request, f"{grn.number} has no accepted quantity to bill.")
        return redirect("inventory:ap_sync")

    rules = _common._active_tax_rules(request.tenant)
    country = _common._party_country(request.tenant, po.vendor)

    with transaction.atomic():
        # Re-check inside the transaction so two concurrent POSTs cannot draft two bills
        # for one receipt (the row-lock pattern scm's own receive/post verbs use).
        locked = (GoodsReceiptNote.objects.select_for_update()
                  .select_related("purchase_order").get(pk=grn.pk))
        if locked.bill_id:
            messages.info(request, f"{locked.number} was already synced — {locked.bill}.")
            return redirect("inventory:ap_sync")

        bill = Bill(tenant=request.tenant, party=po.vendor,
                    payment_terms=po.payment_terms, currency=po.currency,
                    bill_date=timezone.localdate(),
                    notes=f"Drafted from goods receipt {grn.number} · PO {po.number}")
        bill.save()  # TenantNumbered assigns BILL-#####
        # AP lines are free-text (no item FK), so the resolved rate is invariant across
        # lines — resolve ONCE, not per line.
        rate = TaxRule.rate_for(request.tenant, item=None, country=country, rules=rules)
        for line in lines:
            qty = line.quantity_received or ZERO
            if qty <= ZERO:
                continue
            BillLine.objects.create(
                bill=bill,
                description=(line.po_line.item_description or line.po_line.sku_hint
                             or f"PO line {line.po_line_id}")[:255],
                quantity=qty,
                unit_price=line.po_line.unit_price or ZERO,
                tax_rate_pct=rate,
                gl_account=line.po_line.gl_account)
        bill.recalc_totals()

        locked.bill = bill
        locked.save(update_fields=["bill", "updated_at"])
        locked.recompute_match(save=True)
        write_audit_log(request.user, locked, "update",
                        {"action": "sync_ap", "bill": bill.number})
    messages.success(request, f"{grn.number} synced — draft bill {bill.number} handed to AP.")
    return redirect("inventory:ap_sync")

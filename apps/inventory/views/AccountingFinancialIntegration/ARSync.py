"""Inventory 5.18 Accounts Receivable (AR) Integration — "Syncing shipments to create invoices".

The queue is every DELIVERED outbound shipment whose sales order has no invoice yet
(the order carries the ``scm.SalesOrder.invoice`` pointer, so the register is the same
query the other way). The verb drafts a DRAFT ``accounting.Invoice`` — Module 2 owns
the receivable and its posting; this hands it over exactly like 4.17's client billing
does (L29). Lines come from the ORDER lines (a shipment is a TMS-level document without
its own quantity detail), so the draft covers the FULL ordered quantity — partial
deliveries should wait until the order ships completely. Each line's discount is folded
into a net unit price because ``InvoiceLine.line_total`` is quantity × unit price, and
each line's tax rate resolves through the TaxRule catalog (product × customer billing
country).
"""
from datetime import timedelta
from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.accounting.models import Invoice, InvoiceLine
from apps.core.decorators import tenant_admin_required
from apps.inventory.models import TaxRule
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Shipment

from . import _common

ZERO = Decimal("0")
CENT = Decimal("0.01")


def _scoped(tenant):
    """Delivered outbound shipments joined to their order's invoicing state."""
    return (Shipment.objects.filter(tenant=tenant, direction="outbound", status="delivered",
                                    sales_order__isnull=False)
            .select_related("sales_order", "sales_order__customer",
                            "sales_order__currency", "sales_order__invoice")
            .order_by("-id"))


@login_required
def ar_sync(request):
    qs = _scoped(request.tenant)
    register = (qs.filter(sales_order__invoice__isnull=False)
                .select_related("sales_order__invoice", "sales_order__customer")
                .order_by("-actual_delivery_at", "-id")[:10])
    return crud_list(
        request, qs.filter(sales_order__invoice__isnull=True), "inventory/finint/ar_sync.html",
        search_fields=["number", "sales_order__number", "sales_order__customer__name"],
        extra_context={
            "register": register,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
@require_POST
def ar_sync_run(request, pk):
    shipment = get_object_or_404(_scoped(request.tenant), pk=pk,
                                 sales_order__invoice__isnull=True)
    so = shipment.sales_order
    lines = list(so.lines.select_related("item"))
    if not lines:
        messages.error(request, f"{so.number} has no lines to invoice.")
        return redirect("inventory:ar_sync")

    rules = _common._active_tax_rules(request.tenant)
    country = _common._party_country(request.tenant, so.customer)

    with transaction.atomic():
        # Re-check inside the transaction so two concurrent POSTs cannot draft two
        # invoices for one order.
        locked_so = type(so).objects.select_for_update().get(pk=so.pk)
        if locked_so.invoice_id:
            messages.info(request, f"{locked_so.number} was already invoiced — {locked_so.invoice}.")
            return redirect("inventory:ar_sync")

        terms_days = locked_so.payment_terms.days_due if locked_so.payment_terms_id else None
        invoice = Invoice(
            tenant=request.tenant, kind="invoice", party=locked_so.customer,
            payment_terms=locked_so.payment_terms, currency=locked_so.currency,
            issue_date=timezone.localdate(),
            due_date=(timezone.localdate() + timedelta(days=terms_days))
            if terms_days is not None else None,
            notes=f"Drafted from delivery {shipment.number} · order {locked_so.number}")
        invoice.save()  # TenantNumbered assigns INV-#####
        for line in lines:
            qty = line.quantity_ordered or ZERO
            if qty <= ZERO:
                continue
            # Fold the line discount into a NET unit price: InvoiceLine.line_total is
            # quantity × unit_price, so passing the gross would overstate the receivable.
            net_unit = ((line.unit_price or ZERO)
                        * (Decimal("1") - (line.discount_pct or ZERO) / Decimal("100"))
                        ).quantize(CENT, rounding=ROUND_HALF_UP)
            InvoiceLine.objects.create(
                invoice=invoice,
                description=(line.description
                             or (line.item.name if line.item_id else f"Order line {line.pk}"))[:255],
                quantity=qty,
                unit_price=net_unit,
                tax_rate_pct=TaxRule.rate_for(request.tenant, item=line.item,
                                              country=country, rules=rules))
        invoice.recalc_totals()

        # Linking does NOT flip the order status — that is scm's own ruling for this field.
        locked_so.invoice = invoice
        locked_so.save(update_fields=["invoice", "updated_at"])
        write_audit_log(request.user, locked_so, "update",
                        {"action": "sync_ar", "invoice": invoice.number})
    messages.success(request, f"Delivery {shipment.number} synced — draft invoice "
                              f"{invoice.number} handed to AR.")
    return redirect("inventory:ar_sync")

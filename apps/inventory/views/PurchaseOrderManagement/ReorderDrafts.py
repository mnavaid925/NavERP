"""Inventory 5.3 Purchase Order (PO) Management — reorder-point auto-drafting.

**PO Creation & Drafting bullet** ("auto-generated purchase orders based on reorder
points"). SCM 4.3's ``ReorderRule`` already knows WHAT is low and HOW MUCH to buy
(``is_below_point`` / ``suggested_quantity`` over the derived ledger); what nothing else
does is turn those suggestions into purchase orders. This page does exactly that — and
nothing more than that:

* suggestions are computed live over 4.3's append-only ledger (never stored);
* the buyer still routes each line to a vendor — ``scm.Item`` has no vendor FK, so WHO to
  buy from is a human decision taken here, once, at draft time;
* everything lands as DRAFT ``scm.PurchaseOrder``s (L36 spine) for review/submit on the
  spine's own pages — no silent auto-send, mirroring the MRP rule that a planner converts
  suggestions rather than the system committing money.
"""
import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _vendor_parties
from apps.inventory.models._base import ZERO
from apps.scm.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    ReorderRule,
)


@login_required
def reorderdraft(request):
    """Review below-point reorder rules and draft POs from the ticked ones."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before drafting orders.")
        return redirect("dashboard:home")

    tenant = request.tenant
    vendors = _vendor_parties(tenant).order_by("name")
    vendor_map = {str(v.pk): v for v in vendors}
    today = timezone.localdate()

    if request.method == "POST":
        return _draft_orders(request, vendor_map, today)

    rules = list(ReorderRule.objects.filter(tenant=tenant, is_active=True)
                 .select_related("item", "item__uom", "location"))
    on_hand_map = ReorderRule.on_hand_map(tenant, rules)

    suggestions, total_value = [], ZERO
    for rule in rules:
        on_hand = on_hand_map.get((rule.item_id, rule.location_id), ZERO)
        if not rule.is_below_point(on_hand):
            continue
        qty = rule.suggested_quantity(on_hand)
        if qty <= ZERO:
            continue  # at/below point but policy asks for nothing — nothing to draft
        unit_cost = rule.item.standard_cost or ZERO
        extended = (qty * unit_cost).quantize(Decimal("0.01"))
        total_value += extended
        suggestions.append({
            "rule": rule,
            "on_hand": on_hand,
            "qty": qty,
            "unit_cost": unit_cost,
            "extended": extended,
        })

    return render(request, "inventory/po/reorderdraft.html", {
        "suggestions": suggestions,
        "total_value": total_value,
        "vendors": vendors,
        "today": today,
    })


def _draft_orders(request, vendor_map, today):
    """Group the ticked rows by their chosen vendor into DRAFT spine orders."""
    wanted = set(request.POST.getlist("select"))
    if not wanted:
        messages.error(request, "Tick at least one suggestion to draft.")
        return redirect("inventory:reorderdraft")

    rows = []
    for raw in sorted(wanted, key=lambda v: (not v.isdecimal(), int(v) if v.isdecimal() else 0)):
        if not raw.isdecimal():
            continue  # a hand-edited non-pk value is a skipped row, never a 500 (L11)
        rule = ReorderRule.objects.filter(
            tenant=request.tenant, pk=int(raw), is_active=True).select_related(
            "item", "item__uom").first()
        if rule is None:
            continue
        vendor = vendor_map.get(request.POST.get(f"vendor_{rule.pk}", ""))
        if vendor is None:
            continue  # unrouted line: the buyer simply didn't pick a vendor yet
        on_hand = rule.current_on_hand()
        qty = rule.suggested_quantity(on_hand)
        if qty <= ZERO:
            continue
        rows.append((rule, vendor, qty))
    if not rows:
        messages.warning(request, "Nothing drafted — pick a vendor for each ticked line.")
        return redirect("inventory:reorderdraft")

    groups = {}
    for rule, vendor, qty in rows:
        groups.setdefault(vendor.pk, []).append((rule, vendor, qty))

    created = []
    with transaction.atomic():
        for group in groups.values():
            _, vendor, _ = group[0]
            leads = [r.lead_time_days for r, _, _ in group if r.lead_time_days]
            po = PurchaseOrder(
                tenant=request.tenant, vendor=vendor,
                order_date=today,
                expected_date=(today + datetime.timedelta(days=max(leads))) if leads else None,
                status="draft",
                notes="Auto-drafted from reorder points (Inventory 5.3); review before submitting.",
            )
            po.save()
            for rule, _, qty in group:
                PurchaseOrderLine.objects.create(
                    purchase_order=po,
                    item_description=rule.item.name,
                    sku_hint=rule.item.sku,
                    uom_hint=rule.item.uom.code if rule.item.uom_id else "",
                    quantity=qty,
                    unit_price=rule.item.standard_cost or ZERO,
                )
            po.recalc_totals()
            write_audit_log(request.user, po, "create",
                            {"action": "auto_draft_reorder"})
            created.append(po)

    lines = sum(len(g) for g in groups.values())
    messages.success(request, f"Drafted {len(created)} order(s) covering {lines} line(s) "
                              f"— review and submit them on the purchase order pages.")
    if len(created) == 1:
        return redirect("scm:purchaseorder_detail", pk=created[0].pk)
    return redirect("scm:purchaseorder_list")

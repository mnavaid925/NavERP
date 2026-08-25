"""Inventory 5.20 Units of Measure (UOM) — the conversion calculator.

A COMPUTED, read-only surface (the ``global_stock`` posture): pick an optional item,
two units and a quantity, and the page resolves the answer through the shared engine —
direct rule or multi-hop chain — showing every hop it used. No writes anywhere; a pair
with no route says so plainly instead of guessing a rate.
"""
from decimal import Decimal, InvalidOperation

from apps.core.crud import as_db_int
from apps.inventory.models import UomConversion, convert_quantity
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import Item, UOM


def _pick(queryset, raw):
    number = as_db_int(raw)
    if number is None:
        return None
    return queryset.filter(pk=number).first()


@login_required
def uom_calculator(request):
    items = Item.objects.filter(tenant=request.tenant).order_by("sku")
    uoms = UOM.objects.filter(tenant=request.tenant).order_by("code")

    item = _pick(items, request.GET.get("item", ""))
    from_uom = _pick(uoms, request.GET.get("from", ""))
    to_uom = _pick(uoms, request.GET.get("to", ""))

    result = None
    path = None
    qty = None
    error = ""
    asked = bool(request.GET.get("from") or request.GET.get("to") or request.GET.get("qty"))

    if from_uom is not None and to_uom is not None:
        raw_qty = request.GET.get("qty", "").strip() or "1"
        try:
            qty = Decimal(raw_qty)
        except InvalidOperation:
            error = f"'{raw_qty}' is not a quantity I can read — enter a plain number."
        else:
            if from_uom.pk == to_uom.pk:
                result, path = qty.quantize(Decimal("0.0001")), []
            else:
                result, path = convert_quantity(request.tenant, item, qty, from_uom, to_uom)
                if path is None:
                    error = ("No conversion path links these units"
                             " for this scope — add a rule below.")
    elif asked:
        error = "Pick both units to convert."

    return render(request, "inventory/uom/calculator.html", {
        "items": items,
        "uoms": uoms,
        "item": item,
        "from_uom": from_uom,
        "to_uom": to_uom,
        "qty": qty,
        "result": result,
        "path": path,
        "error": error,
        # Header stats: how well-covered this workspace's unit graph is.
        "rule_count": UomConversion.objects.filter(tenant=request.tenant).count(),
        "default_count": UomConversion.objects.filter(
            tenant=request.tenant, is_active=True, item__isnull=True).count(),
        "item_rule_count": UomConversion.objects.filter(
            tenant=request.tenant, is_active=True, item__isnull=False).count(),
    })

"""Inventory 5.8 Lot & Serial Number Tracking — Traceability & Genealogy (computed page, NO table).

**Traceability & Genealogy** bullet: "Full forward and backward tracing of a lot/serial
number for recalls." Nothing here is stored: a lot's history IS its rows in 4.3's
append-only ``StockMove`` ledger, and the genealogy falls out of the ledger too —
a work order that CONSUMED this lot alongside others PRODUCED the lots whose
production moves carry the same reference, so parent/child links are matched through
``reference`` (the WO/document number every posting writes).

Backward trace = the lot's inbound legs (where it came from). Forward trace = its
outbound legs (where it went — recall scope). Genealogy = the transformation links
across references in both directions. All tenant-scoped; a foreign ``?lot=`` is a 404
via the scoped queryset.
"""
from django.db.models import Q, Sum
from django.db.models.functions import Abs
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.models import ShelfLifePolicy, classify_lot
from apps.scm.models import LotSerial, StockMove


@login_required
def traceability(request):
    tenant = request.tenant
    lot_pk = as_db_int(request.GET.get("lot"))
    if lot_pk:
        obj = get_object_or_404(
            LotSerial.objects.select_related("item"), pk=lot_pk, tenant=tenant)
        return _render_trace(request, obj)

    # Picker mode: tracked lots that actually hold stock, most recently touched first.
    q = request.GET.get("q", "").strip()
    lots = _picker_lots(tenant, q)
    return render(request, "inventory/lottrack/trace.html", {
        "obj": None,
        "lots": lots,
        "q": q,
    })


def _picker_lots(tenant, q):
    """Tracked lots with positive ledger balance (or all matching when searching)."""
    qs = (LotSerial.objects.filter(tenant=tenant,
                                   item__tracking__in=("lot", "serial"))
          .select_related("item").order_by("-updated_at", "number"))
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(item__sku__icontains=q)
                       | Q(item__name__icontains=q))
    balances = {
        row["lot_serial_id"]: row["qty"]
        for row in (StockMove.objects.filter(tenant=tenant, lot_serial__isnull=False)
                    .values("lot_serial_id").annotate(qty=Sum("quantity")))
    }
    rows = []
    for lot in qs[:60]:
        rows.append({"lot": lot, "on_hand": balances.get(lot.pk) or 0})
    # Stocked lots first so the picker leads with what a recall would actually bite.
    rows.sort(key=lambda r: r["on_hand"] <= 0)
    return rows[:25]


def _render_trace(request, obj):
    # The explicit tenant predicate is defence-in-depth (same as the 5.6 helpers): the
    # lot is already tenant-scoped, but spelling it also lets MariaDB drive the
    # (tenant, item, location) ledger index instead of trusting the join.
    moves = list(obj.stock_moves.filter(tenant=obj.tenant_id)
                 .select_related("item", "location").order_by("moved_at", "id"))

    inbound = [m for m in moves if m.quantity > 0]
    outbound = [m for m in moves if m.quantity < 0]

    # -- genealogy across transformation references -------------------------------------
    refs_consumed = {m.reference for m in outbound
                     if m.move_type == "consumption" and m.reference}
    children = _sibling_moves(obj, move_type="production", refs=refs_consumed)
    refs_produced = {m.reference for m in inbound
                     if m.move_type == "production" and m.reference}
    parents = _sibling_moves(obj, move_type="consumption", refs=refs_produced)

    today = timezone.localdate()
    policy = ShelfLifePolicy.objects.filter(tenant=obj.tenant_id,
                                            item=obj.item).first()
    flag, css, label = classify_lot(obj, policy, today)

    return render(request, "inventory/lottrack/trace.html", {
        "obj": obj,
        "on_hand": obj.on_hand(),
        "inbound": inbound[:40],
        "outbound": outbound[:40],
        "parents": parents,
        "children": children,
        "policy": policy,
        "flag": flag,
        "css": css,
        "label": label,
        "today": today,
    })


def _sibling_moves(obj, move_type, refs):
    """Other lots' legs under the SAME transformation references.

    A WO that drew this lot also drew siblings and produced outputs under one
    document number, so matching on ``reference`` reconstructs both directions:
    consumption legs by OTHER lots below this lot's production refs are its
    ingredients; production legs by OTHER lots above this lot's consumption refs
    are what it helped make. Tenant-scoped first — the reference string is only a
    key INSIDE one workspace. Unlotted legs are excluded: a move with no lot can
    never be pinned to a specific sibling, and inventing the link would overstate
    recall scope (they still appear in the movement panels above).
    """
    if not refs:
        return StockMove.objects.none()
    return (StockMove.objects
            .filter(tenant=obj.tenant_id, move_type=move_type, reference__in=refs)
            .exclude(lot_serial_id=obj.pk)
            .exclude(lot_serial__isnull=True)
            # abs_qty: the genealogy chips report HOW MUCH moved, not the ledger's
            # sign — consumption legs post negative, production positive, and a chip
            # reading "×-3" for an input would misstate the draw.
            .annotate(abs_qty=Abs("quantity"))
            .select_related("item", "location", "lot_serial")
            .order_by("moved_at")[:20])

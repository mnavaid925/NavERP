"""Inventory 5.8 Lot & Serial Number Tracking — the FEFO board (computed page, NO table).

**Shelf-Life & Expiry Management** bullet. Everything on this page is DERIVED: on-hand
per lot is the append-only StockMove aggregate (never stored anywhere), the expiry
comes from ``scm.LotSerial.expiry_date``, and the red/amber/green verdicts come from
``ShelfLifePolicy`` through the one shared :func:`classify_lot`. The board's job is to
turn those three inputs into a pick order — earliest expiry first, FEFO — and a
do-not-ship line for lots inside their item's minimum-remaining gate.

Rows are dicts, paginated through ``apps.core.crud.paginate`` (which accepts plain
lists), exactly like the Real-Time Stock Levels page built them. Filters run BEFORE
pagination.
"""
from django.db.models import Sum
from django.utils import timezone

from apps.core.crud import as_db_int, paginate
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.models import ShelfLifePolicy, classify_lot
from apps.scm.models import Item, LotSerial, StockMove

#: Board view filters — flag codes mirror classify_lot's outputs.
FLAG_CHOICES = [
    ("expired", "Expired"),
    ("blocked", "Do not ship"),
    ("warning", "Expiring soon"),
    ("ok", "OK"),
    ("none", "No expiry"),
]


@login_required
def fefo_board(request):
    tenant = request.tenant
    today = timezone.localdate()

    # One grouped ledger query: Σ signed quantity per lot. Lots at or below zero have
    # nothing on the shelf — the board is about pickable stock, not history.
    on_hand = {
        row["lot_serial_id"]: row["qty"]
        for row in (StockMove.objects.filter(tenant=tenant, lot_serial__isnull=False)
                    .values("lot_serial_id").annotate(qty=Sum("quantity")))
        if row["qty"] and row["qty"] > 0
    }
    policies = {p.item_id: p for p in ShelfLifePolicy.objects.filter(tenant=tenant)}

    rows = []
    for lot in (LotSerial.objects.filter(tenant=tenant,
                                         item__tracking__in=("lot", "serial"))
                .select_related("item")):
        qty = on_hand.get(lot.pk)
        if not qty:
            continue
        policy = policies.get(lot.item_id)
        flag, css, label = classify_lot(lot, policy, today)
        rows.append({
            "item": lot.item,
            "lot": lot,
            "on_hand": qty,
            "policy": policy,
            "flag": flag,
            "css": css,
            "label": label,
            "remaining": ((lot.expiry_date - today).days
                          if lot.expiry_date is not None else None),
        })

    q = request.GET.get("q", "").strip()
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["item"].sku.lower()
                or needle in r["item"].name.lower()
                or needle in r["lot"].number.lower()]

    item_pk = as_db_int(request.GET.get("item"))
    if item_pk:
        rows = [r for r in rows if r["item"].pk == item_pk]

    flag = request.GET.get("flag", "").strip()
    if flag:
        rows = [r for r in rows if r["flag"] == flag]

    # THE pick order. Enforced policies drive true FEFO: earliest expiry first, and
    # never-expiring goods sort last, then by item so each SKU's lots stay together
    # for a picker walking the shelf. An ADVISORY regime (fefo_enforced=False) has
    # no pick order imposed at all — its lots group under their SKU in plain number
    # order — so the badge on the policy tells the truth about what the board does.
    def _pick_order(row):
        if row["policy"] is not None and not row["policy"].fefo_enforced:
            return (1, False, None, row["item"].sku, row["lot"].number)
        return (0, row["lot"].expiry_date is None,
                row["lot"].expiry_date or today, row["item"].sku, row["lot"].number)

    rows.sort(key=_pick_order)

    counts = {}
    for row in rows:
        counts[row["flag"]] = counts.get(row["flag"], 0) + 1

    page_obj = paginate(request, rows, per_page=15)
    return render(request, "inventory/lottrack/fefo.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "flag_choices": FLAG_CHOICES,
        "items": _board_items(tenant, on_hand),
        "counts": counts,
        "today": today,
    })


def _board_items(tenant, on_hand):
    """Tracked items that actually appear on the board — the filter dropdown.

    ``on_hand`` is keyed by LOT pk, so the item set comes from a DISTINCT walk over
    the lots that carry stock — filtering on the map's keys directly would match
    whatever items coincidentally share primary keys with lots.
    """
    if not on_hand or tenant is None:
        return Item.objects.none()
    item_ids = (LotSerial.objects.filter(tenant=tenant, pk__in=on_hand)
                .values_list("item_id", flat=True).distinct())
    return Item.objects.filter(tenant=tenant, pk__in=item_ids).order_by("sku")

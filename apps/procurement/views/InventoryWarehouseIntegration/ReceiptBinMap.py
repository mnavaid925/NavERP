"""Procurement 6.18 Inventory & Warehouse Integration — the Receipt → Bin map.

**Warehouse Location Mapping** bullet. One read-only page answering the question no existing NavERP
page answers: *the goods I received — where did they actually end up?* The GRN detail shows the
**staging** location the receipt was booked into, which is where stock lands, not where it lives.
This page follows it the rest of the way, to the bin.

**Nothing here is stored.** No model, no form, no migration, no write. Every column is a live
grouped aggregate over data owned elsewhere (L36), and a bin **IS** ``scm.Location`` with
``location_type="bin"`` — there is no Bin or Zone model and this page does not add one.

--------------------------------------------------------------------------------------------------
THE JOIN — and the wrong one it is easy to write
--------------------------------------------------------------------------------------------------

An earlier draft of this page's contract said *"the receipt→bin link IS
``StockMove.reference == grn.number``"*. **That is wrong**, and building on it would have shipped a
bins column that was silently blank or, worse, quietly showed staging and called it a bin. Verified
against ``apps/scm/views/_helpers.py``:

===================  ==========================  =====================  ==========================
move                 written by                  ``reference``          lands in
===================  ==========================  =====================  ==========================
goods receipt        ``_post_receipt`` `:330`    ``grn.number``         the **staging** location
putaway out (−)      ``_post_putaway`` `:227`    ``task.number``        out of staging
putaway in  (+)      ``_post_putaway`` `:231`    ``task.number``        the destination **bin**
===================  ==========================  =====================  ==========================

So ``reference == grn.number`` finds only the receipt INTO STAGING. It can never name the bin the
goods reached, which is the one question this page exists to answer. The correct trail is two hops,
and the second is not a stock lookup at all:

1. ``scm.PutawayTask.objects.filter(tenant=…, goods_receipt_id__in=<the page's pks>)`` — the FK
   already ties the task to its GRN. This is the link.
2. **``PutawayTask.to_location`` IS the destination bin.** No stock query is needed to know where
   the goods were sent; the task says so.
3. ``StockMove`` is used ONLY for a *quantity per bin*, joined on ``reference == task.number``
   against the positive ``reason="Putaway in"`` leg — never on ``grn.number``.
4. ``unputaway_qty`` is ``received_qty`` minus the sum of COMPLETED putaway task quantities. It is
   not a ``StockMove`` difference: a pending task has moved nothing, and a task that was never
   raised leaves stock sitting in staging with no move to subtract.

The honest consequence, stated on the page rather than buried here: **stock received but never put
away has no bin at all.** It is still in staging. That is exactly what ``is_unputaway`` reports, and
it is a finding, not a gap in the page.

--------------------------------------------------------------------------------------------------
Shape
--------------------------------------------------------------------------------------------------

* **The GRNs are filtered, capped and PAGINATED FIRST**; only then do the grouped queries run, over
  the page's pks. The query count is therefore FLAT — it does not move when the receipt count
  doubles, because nothing is aggregated inside the row loop.
* The four ``stats`` cover the whole capped population (not merely the page), which costs exactly
  two extra grouped queries and makes "how many are still in staging?" answerable without paging
  through the register. ``ROW_CAP`` bounds that population and ``truncated`` says so out loud.
* **Every url is ``reverse()``d in Python**, never in the template — the rows are plain dicts, and a
  ``{% url %}`` tag cannot express "only when this receipt has a putaway task".
* ``request.tenant is None`` renders an EMPTY map, never a 500; junk GET params narrow nothing and
  return 200.
* Directed-putaway **suggestions are not rebuilt here.** ``inventory.PutawayRule`` and
  ``scm.PutawayTask`` already do that job; this page links out to them.
"""
from datetime import date as _date

from django.db.models import Q, Sum
from django.urls import reverse

from apps.core.crud import as_db_int, paginate
from apps.inventory.models import BinCapacity
from apps.scm.models import (GoodsReceiptLine, GoodsReceiptNote, Location, PutawayTask,
                             StockMove)

from apps.procurement.models._base import ZERO
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/inventorywarehouse/receipt_bin_map.html"

#: Hard ceiling on the population the page reports over, surfaced as ``row_cap`` with ``truncated``
#: so a capped board cannot imply its stats cover the whole workspace.
ROW_CAP = 500

#: One page of receipts. Each row expands into its bins and tasks, so it is kept shorter than a
#: flat register's page.
_PER_PAGE = 20

#: The exact ``reason`` string ``_post_putaway`` stamps on the POSITIVE leg — the one that lands in
#: the destination bin. The negative leg out of staging carries "Putaway out" and must not be
#: summed here, or every bin would net to zero.
_PUTAWAY_IN_REASON = "Putaway in"

#: Putaway task lifecycle → theme.css colour-named badges (L33: ``-success``/``-warning`` do not
#: exist and render unstyled).
PUTAWAY_TASK_CSS = {
    "pending": "badge-amber",
    "in_progress": "badge-info",
    "completed": "badge-green",
    "cancelled": "badge-slate",
}

#: Whole-receipt putaway state → badge. Keyed by the three states :func:`_putaway_state` returns.
PUTAWAY_STATE_CSS = {
    "complete": "badge-green",
    "partial": "badge-amber",
    "staging": "badge-red",
}

#: Bin fullness → badge. A bin with no declared capacity is not "empty", it is UNMEASURED, and it
#: gets the muted badge rather than a reassuring green one.
_CAPACITY_CSS_BANDS = ((Ellipsis, "badge-muted"), (100, "badge-red"), (85, "badge-amber"))

#: The limitation this page must state out loud. Verbatim on the page.
REFERENCE_NOTE = (
    "The receipt-to-bin trail runs GRN → putaway task → bin, and only that way. A goods receipt "
    "posts its stock into a STAGING location under the receipt's own number; the bin is reached "
    "later, by a putaway task, whose stock moves carry the TASK's number instead. So the bins "
    "below come from each receipt's putaway tasks — the task's destination is the bin — and the "
    "per-bin quantity comes from the positive leg of that task's moves. Stock that was received "
    "but never put away has NO bin: it is still sitting in staging, which is exactly what the "
    "unputaway figure reports. A receipt with no putaway task at all is not a data error on this "
    "page; it is a receipt nobody has put away."
)


def _capacity_css(fullness_pct):
    """Badge for a bin's fullness. ``None`` (no declared capacity) is muted, never green."""
    if fullness_pct is None:
        return _CAPACITY_CSS_BANDS[0][1]
    for threshold, css in _CAPACITY_CSS_BANDS[1:]:
        if fullness_pct >= threshold:
            return css
    return "badge-green"


def _putaway_state(received_qty, unputaway_qty):
    """One of ``complete`` / ``partial`` / ``staging`` for a whole receipt.

    ``staging`` means nothing has been put away at all — the strongest signal on the page, so it
    is not folded in with "partial". A receipt of nothing (a draft with no lines) reads as
    ``complete`` rather than alarming: there is nothing to put away.
    """
    if unputaway_qty <= ZERO:
        return "complete"
    if unputaway_qty >= received_qty:
        return "staging"
    return "partial"


def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None``. Junk narrows nothing and never raises."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return _date.fromisoformat(raw)
    except ValueError:
        return None


@login_required
def receipt_bin_map(request):
    """Where each goods receipt's stock actually landed. Derived on read, stored nowhere."""
    tenant = request.tenant
    q = (request.GET.get("q") or "").strip()
    location_id = as_db_int(request.GET.get("location"))
    selected_status = (request.GET.get("status") or "").strip()
    if selected_status not in {value for value, _ in GoodsReceiptNote.STATUS_CHOICES}:
        selected_status = ""
    date_from = _as_date(request.GET.get("date_from"))
    date_to = _as_date(request.GET.get("date_to"))

    locations = Location.objects.none()
    selected_location = None
    capped_pks, truncated = [], False
    received_map, putaway_done_map = {}, {}

    if tenant is not None:
        locations = (Location.objects.filter(tenant=tenant)
                     .order_by("code"))
        if location_id is not None:
            selected_location = locations.filter(pk=location_id).first()

        qs = GoodsReceiptNote.objects.filter(tenant=tenant)
        if q:
            qs = qs.filter(Q(number__icontains=q)
                           | Q(delivery_note_ref__icontains=q)
                           | Q(purchase_order__number__icontains=q)
                           | Q(purchase_order__vendor__name__icontains=q))
        if selected_status:
            qs = qs.filter(status=selected_status)
        if selected_location is not None:
            qs = qs.filter(location_id=selected_location.pk)
        if date_from is not None:
            qs = qs.filter(receipt_date__gte=date_from)
        if date_to is not None:
            qs = qs.filter(receipt_date__lte=date_to)

        # Cap the POPULATION, then paginate the cap. Doing it in this order is what lets the four
        # stats below describe more than the current page while still costing a fixed number of
        # queries — and it guarantees every page's pks are a subset of the population the two
        # stats maps were built over, so the rows and the stats can never disagree.
        probe = list(qs.order_by("-receipt_date", "-id").values_list("pk", flat=True)[:ROW_CAP + 1])
        truncated = len(probe) > ROW_CAP
        capped_pks = probe[:ROW_CAP]

        if capped_pks:
            # ONE grouped query: quantity received per receipt, over the whole capped population.
            received_map = {
                row["goods_receipt_id"]: (row["s"] or ZERO)
                for row in (GoodsReceiptLine.objects
                            .filter(goods_receipt_id__in=capped_pks)
                            .values("goods_receipt_id")
                            .annotate(s=Sum("quantity_received")))}
            # ONE grouped query: quantity actually PUT AWAY per receipt. Completed tasks only — a
            # pending task has moved nothing, so counting it would report stock as binned while it
            # is still standing in staging.
            putaway_done_map = {
                row["goods_receipt_id"]: (row["s"] or ZERO)
                for row in (PutawayTask.objects
                            .filter(tenant=tenant, goods_receipt_id__in=capped_pks,
                                    status="completed")
                            .values("goods_receipt_id")
                            .annotate(s=Sum("quantity")))}

    # Stats cover the whole capped population, not just the rendered page.
    stats = {"receipts": len(capped_pks), "fully_putaway": 0,
             "partially_putaway": 0, "in_staging": 0}
    _STATE_STAT = {"complete": "fully_putaway", "partial": "partially_putaway",
                   "staging": "in_staging"}
    for pk in capped_pks:
        received = received_map.get(pk, ZERO)
        state = _putaway_state(received, received - putaway_done_map.get(pk, ZERO))
        stats[_STATE_STAT[state]] += 1

    page_obj = paginate(request, capped_pks, per_page=_PER_PAGE)
    page_pks = list(page_obj.object_list)
    rows = []

    if page_pks:
        # ONE query for the page's receipts. `pk__in` loses the ordering, so it is restored from
        # `capped_pks`, which already carries it.
        grn_map = {grn.pk: grn for grn in
                   GoodsReceiptNote.objects
                   .filter(pk__in=page_pks)
                   .select_related("purchase_order", "purchase_order__vendor", "location")}

        # ONE query for the page's putaway tasks — THE link between a receipt and its bin. The
        # destination bin's ancestry is select_related to a bounded depth so `Location.path()`
        # (the ONE definition of a location's readable path) costs no extra query per hop for a
        # warehouse › zone › bin hierarchy.
        tasks = list(PutawayTask.objects
                     .filter(tenant=tenant, goods_receipt_id__in=page_pks)
                     .select_related("item", "to_location",
                                     "to_location__parent__parent__parent")
                     .order_by("to_location__code", "number"))

        task_numbers = [task.number for task in tasks if task.number]
        bin_ids = {task.to_location_id for task in tasks if task.to_location_id}

        # ONE grouped query for the quantity each task actually landed in its bin — the POSITIVE
        # "Putaway in" leg only. Summing both legs would net every bin to zero, and joining on
        # grn.number instead of task.number would find the staging receipt and no bin at all.
        moved_map = {}
        if task_numbers:
            moved_map = {(row["reference"], row["location_id"]): (row["s"] or ZERO)
                         for row in (StockMove.objects
                                     .filter(tenant=tenant, reference__in=task_numbers,
                                             reason=_PUTAWAY_IN_REASON)
                                     .values("reference", "location_id")
                                     .annotate(s=Sum("quantity")))}

        # ONE grouped query for each touched bin's TOTAL on-hand, and ONE for its declared
        # capacity. Fullness is the bin's own state — how full it is overall — not this receipt's
        # share of it, which is what a receiver actually needs to know before sending more there.
        bin_on_hand, bin_capacity = {}, {}
        if bin_ids:
            bin_on_hand = {row["location_id"]: (row["s"] or ZERO)
                           for row in (StockMove.objects
                                       .filter(tenant=tenant, location_id__in=bin_ids)
                                       .values("location_id")
                                       .annotate(s=Sum("quantity")))}
            bin_capacity = {cap.location_id: cap.max_quantity
                            for cap in BinCapacity.objects.filter(tenant=tenant,
                                                                  location_id__in=bin_ids)
                            if cap.max_quantity}

        tasks_by_grn = {}
        for task in tasks:
            tasks_by_grn.setdefault(task.goods_receipt_id, []).append(task)

        for pk in page_pks:
            grn = grn_map.get(pk)
            if grn is None:            # deleted between the pk probe and the fetch
                continue
            grn_tasks = tasks_by_grn.get(pk, [])
            received = received_map.get(pk, ZERO)
            unputaway = received - putaway_done_map.get(pk, ZERO)

            # A bin can be the destination of more than one task on the same receipt, so quantities
            # are folded per bin rather than per task.
            bins, seen_bins = [], {}
            for task in grn_tasks:
                location = task.to_location
                if location is None:
                    continue
                quantity = moved_map.get((task.number, location.pk), ZERO)
                if location.pk in seen_bins:
                    seen_bins[location.pk]["quantity"] += quantity
                    continue
                capacity = bin_capacity.get(location.pk)
                fullness = None
                if capacity:
                    fullness = (bin_on_hand.get(location.pk, ZERO) / capacity) * 100
                entry = {
                    "location": location,
                    "path": location.path(),
                    "quantity": quantity,
                    "capacity": capacity,
                    "fullness_pct": fullness,
                    "capacity_css": _capacity_css(fullness),
                }
                seen_bins[location.pk] = entry
                bins.append(entry)

            state = _putaway_state(received, unputaway)
            rows.append({
                "grn": grn,
                "grn_url": reverse("scm:goodsreceipt_detail", args=[grn.pk]),
                "staging_location": grn.location,
                "received_qty": received,
                "bins": bins,
                "putaway_tasks": [{
                    "task": task,
                    "url": reverse("scm:putawaytask_detail", args=[task.pk]),
                    "status": task.status,
                    "status_css": PUTAWAY_TASK_CSS.get(task.status, "badge-muted"),
                    "to_location": task.to_location,
                } for task in grn_tasks],
                "unputaway_qty": unputaway if unputaway > ZERO else ZERO,
                "is_unputaway": unputaway > ZERO,
                "putaway_css": PUTAWAY_STATE_CSS[state],
            })

    return render(request, TEMPLATE, {
        "page_obj": page_obj,
        "object_list": rows,
        "q": q,
        "locations": locations,
        "status_choices": GoodsReceiptNote.STATUS_CHOICES,
        "selected_location": selected_location,
        "selected_status": selected_status,
        "date_from": date_from,
        "date_to": date_to,
        "stats": stats,
        "row_cap": ROW_CAP,
        "truncated": truncated,
        "reference_note": REFERENCE_NOTE,
        # Out to the pages that OWN putaway — this one reports, it does not re-implement directed
        # putaway, bin capacity or cross-docking.
        "links": [
            {"label": "Putaway tasks", "url": reverse("scm:putawaytask_list"),
             "icon": "package-check"},
            {"label": "Putaway rules", "url": reverse("inventory:putawayrule_list"),
             "icon": "route"},
            {"label": "Bin capacity", "url": reverse("inventory:bincapacity_list"),
             "icon": "gauge"},
            {"label": "Cross-dock orders", "url": reverse("inventory:crossdockorder_list"),
             "icon": "shuffle"},
        ],
    })

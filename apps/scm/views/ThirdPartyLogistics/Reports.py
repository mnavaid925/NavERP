"""SCM 4.17 Third-Party Logistics (3PL) — two COMPUTED pages. **No new table, no new column.**

Two of this sub-module's five NavERP bullets are PAGES rather than tables — the ``sparepart_list`` /
``labor_board`` / ``cold_storage_report`` precedent — and both are derived entirely from rows that
already exist:

* :func:`client_inventory_report` — **"Client Inventory Segregation"**, computed over 4.3. Whose
  stock is whose comes from ``Item.owner_client`` (4.17's one additive column on the item master) and
  the quantities come from the append-only ``StockMove`` ledger. **There is deliberately no owner
  column on ``StockMove``** and no second on-hand figure anywhere: an owner on an append-only ledger
  would be a second source of truth for the same fact, and the two would disagree the first time an
  item was re-assigned (L37).
* :func:`client_space_report` — **"Warehouse Rental Management"**. What each client COMMITTED to
  (``committed_sqft`` / ``committed_pallet_positions`` on the client record) shown BESIDE the summed
  ``Location.capacity`` of the bins actually reserved to them. **No conversion is invented between
  the two.** ``Location.capacity`` is documented on 4.3's own field as being "in the bin's own
  units", so a square-foot figure derived from it would be a number that looks authoritative and is
  fiction. The page prints both and labels the capacity column with the units caveat.

--------------------------------------------------------------------------------------------------
THREE STANDING RULES THESE PAGES ARE BUILT AROUND
--------------------------------------------------------------------------------------------------
**1. These pages WRITE NOTHING.** No ``StockMove``, no ``JournalEntry`` (L29), no ``Item`` column, no
``LogisticsClient`` column. They are GET pages with query-string options; there is not a POST route
between them.

**2. Coverage, not a confident zero** (the 4.11 lesson). ``occupied_pallet_positions`` is deliberately
NOT offered anywhere on either page: ``Item`` carries no dimensions, so pallet occupancy cannot be
derived, and a computed "occupied" figure would be an estimate presented as a measurement. What IS
offered — committed space, dedicated bin count, summed bin capacity — is stated with its units.
``unassigned_sku_count`` exists for the same reason: an item with no ``owner_client`` is the
segregation GAP, and a report that silently omitted it would show a tidy page for a warehouse nobody
has assigned.

**3. Both pages render 200 on an EMPTY tenant**, with honest zeros and ``None`` capacity totals.
Neither may 500 on a first run, and neither may 500 on a hand-edited query string: every pk param
goes through ``as_db_int`` (L11), so ``?client=abc``, ``?client=²`` and
``?client=99999999999999999999`` all SKIP the filter rather than raise.

--------------------------------------------------------------------------------------------------
QUERY HYGIENE
--------------------------------------------------------------------------------------------------
Nothing here calls a per-row method that queries. ``LogisticsClient.on_hand_quantity()``,
``on_hand_value()``, ``sku_count()`` and ``dedicated_location_count()`` are all correct and all fire
their own query — they are for ONE row on the detail page. Each is replaced here by ONE grouped
aggregate over the whole page's client ids. Every section is capped with a queryset SLICE, so the cap
bounds what is FETCHED rather than merely what is rendered (L40 §1).
"""
from apps.scm.views._common import *  # noqa: F401,F403

from apps.scm.models import (Item, ItemCategory, Location, LogisticsClient, MAX_MEASUREMENT_ROWS,
                             SPACE_MODEL_CHOICES, StockMove)
# `ZERO` and `q2` come from the models toolkit rather than being re-derived here: `q2` is the one
# quantize-AND-clamp helper every computed money figure in this app goes through, so a poisoned
# value can only ever degrade its own row (the `ColdChainManagement/Reports.py` precedent for the
# same import).
from apps.scm.models._base import ZERO, q2


#: Client rows either page will list. Applied as a queryset SLICE and reported when it bites, so the
#: page can say it is showing a window rather than pretending the window is the total.
MAX_REPORT_ROWS = 100


def _client_qs(tenant):
    """The client master for this workspace — the queryset behind every ``?client=`` dropdown here.

    Returns ``.none()`` for a tenant-less user (the superuser has ``tenant=None`` by design) rather
    than a filter on NULL, which for a nullable-FK lookup is not "nothing" — it is "everybody's".
    """
    if tenant is None:
        return LogisticsClient.objects.none()
    return LogisticsClient.objects.filter(tenant=tenant).select_related("party").order_by("code")


def _category_qs(tenant):
    """4.3's item categories, scoped — the ``?category=`` dropdown."""
    if tenant is None:
        return ItemCategory.objects.none()
    return ItemCategory.objects.filter(tenant=tenant).order_by("name")


def _location_qs(tenant):
    """4.3's locations, scoped — the ``?location=`` dropdown.

    A LOCAL copy of the shared ``views/_helpers._location_qs`` rather than an import, because this
    one adds the ordering both pages render in and the helper's caller set does not want it. (If a
    third page ever needs exactly this shape, it moves to ``_helpers`` — Backend Package Structure
    rule 5.)
    """
    if tenant is None:
        return Location.objects.none()
    return Location.objects.filter(tenant=tenant).order_by("code")


# =================================================================================================
# Report 1 — Client Inventory Segregation (computed over 4.3's item master + StockMove ledger)
# =================================================================================================
@login_required
def client_inventory_report(request):
    """Whose stock is whose, and what it is worth — derived, never stored.

    **Filter GET params**, all three L11-guarded through ``as_db_int``:

    * ``client`` — a pk. Narrows the table to one client AND populates the per-SKU breakdown.
    * ``category`` — a pk. Narrows BOTH the assigned-SKU counts and the ledger figures (a category
      is a property of the item, so it is meaningful on both sides).
    * ``location`` — a pk. Narrows **the ledger figures only**, and the page must say so. A location
      is where stock sits, not a property of an item master, so it cannot narrow "how many SKUs is
      this client assigned" without changing what that column means mid-page.

    **Context**, exhaustively:

    * ``rows`` — a LIST of dicts, keys EXACTLY ``client`` (a ``LogisticsClient``, ``party`` joined),
      ``sku_count`` (int — item masters ASSIGNED to this client; deliberately not "items currently
      holding stock", because a client with forty SKUs and an empty warehouse still has forty SKUs),
      ``on_hand_quantity`` (Decimal), ``on_hand_value`` (Decimal) and ``dedicated_locations`` (int).
    * ``totals`` — a dict with the SAME four keys, summed over the listed rows.
    * ``clients`` / ``categories`` / ``locations`` — querysets for the three dropdowns. Compare a pk
      with ``|stringformat:"d"``, **NEVER** ``|slugify``.
    * ``selected_client`` — a ``LogisticsClient`` or ``None``.
    * ``item_rows`` — a LIST of dicts, keys EXACTLY ``item`` (an ``Item``), ``quantity`` (Decimal)
      and ``value`` (Decimal). Populated ONLY when ``selected_client`` is set; an **empty list**
      otherwise, never absent.
    * ``unassigned_sku_count`` (int) — items with ``owner_client`` NULL. **This is the segregation
      gap and it is the most useful number on the page**: stock nobody has claimed. Zero is the
      healthy answer; anything else is a list of items somebody has to assign.
    * Plus, for honest rendering: ``truncated`` / ``item_rows_truncated`` / ``ledger_truncated``
      (bools), ``row_cap`` (int), ``ledger_cap`` (int), ``location_note`` and ``reads_only_note``
      (strings that MUST be rendered — they are the page's own caveats, not decoration).

    QUERIES: one for the clients, one grouped aggregate over the ledger, one grouped count of
    assigned items, one grouped count of dedicated locations, one for the unassigned count, and one
    ``in_bulk`` for the selected client's items. SIX, flat — not one of them per row.
    """
    tenant = request.tenant
    client_pk = as_db_int(request.GET.get("client"))
    category_pk = as_db_int(request.GET.get("category"))
    location_pk = as_db_int(request.GET.get("location"))

    # --- the clients on the page --------------------------------------------------------------------
    clients_qs = LogisticsClient.objects.filter(tenant=tenant).select_related("party")
    if client_pk is not None:
        clients_qs = clients_qs.filter(pk=client_pk)
    clients = list(clients_qs.order_by("code", "id")[:MAX_REPORT_ROWS + 1])
    truncated = len(clients) > MAX_REPORT_ROWS
    del clients[MAX_REPORT_ROWS:]
    client_ids = [client.pk for client in clients]

    selected_client = clients[0] if (client_pk is not None and clients) else None

    # --- the ledger, ONE grouped aggregate -----------------------------------------------------------
    # Grouped per (client, item) rather than per client, because the SAME result set serves both the
    # per-client totals and the selected client's per-SKU breakdown. The item's cached average cost
    # rides along in the same query, so valuing the position costs no second round trip per SKU.
    #
    # `.order_by()` is load-bearing: `StockMove.Meta.ordering` is `["-moved_at", "-id"]` and an
    # inherited ORDER BY column is dragged into the GROUP BY, splitting every sum per timestamp.
    #
    # `.filter(qty__gt=ZERO)` compiles to a HAVING clause and drops items whose moves net to zero or
    # below — an item that has fully shipped out is history, not a holding, and printing it as a 0
    # row would make an empty position look like a stocked one. It also matches
    # `LogisticsClient.on_hand_value()` exactly, so the figure on the detail page and the figure in
    # this row are the same fact rather than two opinions.
    ledger_rows = []
    ledger_truncated = False
    if client_ids:
        moves = StockMove.objects.filter(tenant=tenant, item__owner_client_id__in=client_ids)
        if category_pk is not None:
            moves = moves.filter(item__category_id=category_pk)
        if location_pk is not None:
            moves = moves.filter(location_id=location_pk)
        ledger_rows = list(moves
                           .order_by()
                           .values("item__owner_client_id", "item_id", "item__average_cost")
                           .annotate(qty=Sum("quantity"))
                           .filter(qty__gt=ZERO)
                           .order_by("item__owner_client_id", "item_id")[:MAX_MEASUREMENT_ROWS + 1])
        ledger_truncated = len(ledger_rows) > MAX_MEASUREMENT_ROWS
        del ledger_rows[MAX_MEASUREMENT_ROWS:]

    holdings = {}
    for row in ledger_rows:
        quantity = row["qty"] or ZERO
        value = quantity * (row["item__average_cost"] or ZERO)
        bucket = holdings.setdefault(row["item__owner_client_id"], {"qty": ZERO, "value": ZERO})
        bucket["qty"] += quantity
        bucket["value"] += value

    # --- assigned SKUs and dedicated bins, ONE grouped count each ------------------------------------
    assigned = {}
    dedicated = {}
    if client_ids:
        item_counts = Item.objects.filter(tenant=tenant, owner_client_id__in=client_ids)
        if category_pk is not None:
            item_counts = item_counts.filter(category_id=category_pk)
        assigned = {row["owner_client_id"]: row["n"] for row in
                    item_counts.order_by().values("owner_client_id").annotate(n=Count("id"))}

        location_counts = Location.objects.filter(tenant=tenant, owner_client_id__in=client_ids)
        if location_pk is not None:
            location_counts = location_counts.filter(pk=location_pk)
        dedicated = {row["owner_client_id"]: row["n"] for row in
                     location_counts.order_by().values("owner_client_id").annotate(n=Count("id"))}

    rows = [{
        "client": client,
        "sku_count": assigned.get(client.pk, 0),
        "on_hand_quantity": holdings.get(client.pk, {}).get("qty", ZERO),
        "on_hand_value": q2(holdings.get(client.pk, {}).get("value", ZERO)),
        "dedicated_locations": dedicated.get(client.pk, 0),
    } for client in clients]

    totals = {
        "sku_count": sum(row["sku_count"] for row in rows),
        "on_hand_quantity": sum((row["on_hand_quantity"] for row in rows), ZERO),
        "on_hand_value": q2(sum((row["on_hand_value"] for row in rows), ZERO)),
        "dedicated_locations": sum(row["dedicated_locations"] for row in rows),
    }

    # --- the per-SKU breakdown for ONE client --------------------------------------------------------
    item_rows = []
    item_rows_truncated = False
    if selected_client is not None:
        selected_rows = [row for row in ledger_rows
                         if row["item__owner_client_id"] == selected_client.pk]
        item_rows_truncated = len(selected_rows) > MAX_REPORT_ROWS
        del selected_rows[MAX_REPORT_ROWS:]
        # ONE in_bulk for the whole breakdown rather than a query per SKU. `select_related` on the
        # category and UoM because the table renders both.
        items = (Item.objects.filter(tenant=tenant,
                                     pk__in=[row["item_id"] for row in selected_rows])
                 .select_related("category", "uom").in_bulk())
        for row in selected_rows:
            item = items.get(row["item_id"])
            if item is None:
                continue  # the item was deleted between the aggregate and this fetch
            quantity = row["qty"] or ZERO
            item_rows.append({
                "item": item,
                "quantity": quantity,
                "value": q2(quantity * (row["item__average_cost"] or ZERO)),
            })
        item_rows.sort(key=lambda entry: entry["item"].sku)

    # --- the segregation gap ---------------------------------------------------------------------------
    unassigned = Item.objects.filter(tenant=tenant, owner_client__isnull=True)
    if category_pk is not None:
        unassigned = unassigned.filter(category_id=category_pk)

    return render(request, "scm/3pl/client_inventory_report.html", {
        "rows": rows,
        "totals": totals,
        "clients": _client_qs(tenant),
        "categories": _category_qs(tenant),
        "locations": _location_qs(tenant),
        "selected_client": selected_client,
        "item_rows": item_rows,
        "item_rows_truncated": item_rows_truncated,
        "unassigned_sku_count": unassigned.count(),
        "truncated": truncated,
        "ledger_truncated": ledger_truncated,
        "row_cap": MAX_REPORT_ROWS,
        "ledger_cap": MAX_MEASUREMENT_ROWS,
        "location_note": LOCATION_FILTER_NOTE,
        "reads_only_note": READS_ONLY_NOTE,
    })


# =================================================================================================
# Report 2 — Warehouse Rental Management (committed space beside the bins actually reserved)
# =================================================================================================
@login_required
def client_space_report(request):
    """What each client agreed to rent, beside the bins actually reserved to them.

    **Filter GET params:** ``client`` (a pk, L11-guarded through ``as_db_int``) and ``space_model``
    (one of ``SPACE_MODEL_CHOICES``; anything else is ignored rather than filtering to nothing).

    **NO CONVERSION IS INVENTED ON THIS PAGE.** ``committed_sqft`` and ``committed_pallet_positions``
    are what the contract says; ``dedicated_capacity`` is the SUM of ``Location.capacity`` over the
    bins reserved to the client, and 4.3's own field help text describes that number as being "in the
    bin's own units". Those units are not square feet, they are not pallet positions, and they are not
    necessarily the same unit from one bin to the next. The three columns therefore sit side by side
    and the page labels the capacity one with the caveat; **an ``occupied_pallet_positions`` column is
    deliberately not offered at all**, because ``Item`` carries no dimensions and any such figure
    would be an estimate rendered as a measurement.

    **Context**, exhaustively:

    * ``rows`` — a LIST of dicts, keys EXACTLY ``client`` (a ``LogisticsClient``, ``party`` joined),
      ``space_model`` (the RAW value, for a ``{% if %}`` on an exact value), ``space_model_label``,
      ``committed_sqft`` (Decimal), ``committed_pallet_positions`` (int), ``dedicated_locations``
      (int), ``dedicated_capacity`` (Decimal or **``None``** — ``None`` means no reserved bin records
      a capacity at all, which is NOT the same as zero capacity and must not render as ``0``),
      ``contract_start`` (date or ``None``), ``contract_end`` (date or ``None``) and
      ``days_to_expiry`` (int or **``None``** — negative once the contract has ended, ``None`` when
      no end date is on file; ``None`` must never render as ``0``, which would read as "expires
      today").
    * ``totals`` — a dict with keys EXACTLY ``committed_sqft``, ``committed_pallet_positions``,
      ``dedicated_locations`` and ``dedicated_capacity`` (the last is ``None`` when not one listed
      client records a bin capacity).
    * ``space_model_choices`` — the vocabulary for the ``?space_model=`` dropdown (strings: compare
      against ``request.GET.space_model`` directly).
    * ``clients`` — the queryset for the ``?client=`` dropdown (a pk: ``|stringformat:"d"``).
    * Plus ``truncated`` (bool), ``row_cap`` (int), ``today`` (date), and ``capacity_note`` /
      ``reads_only_note`` (strings that MUST be rendered — the capacity caveat is the whole
      difference between an honest column and a misleading one).

    QUERIES: one for the clients, one grouped aggregate for the reserved bins (count + capacity in
    the same pass). TWO, flat.
    """
    tenant = request.tenant
    today = timezone.localdate()
    client_pk = as_db_int(request.GET.get("client"))
    space_model = (request.GET.get("space_model") or "").strip()
    if space_model not in dict(SPACE_MODEL_CHOICES):
        space_model = ""

    clients_qs = LogisticsClient.objects.filter(tenant=tenant).select_related("party")
    if client_pk is not None:
        clients_qs = clients_qs.filter(pk=client_pk)
    if space_model:
        clients_qs = clients_qs.filter(space_model=space_model)
    clients = list(clients_qs.order_by("code", "id")[:MAX_REPORT_ROWS + 1])
    truncated = len(clients) > MAX_REPORT_ROWS
    del clients[MAX_REPORT_ROWS:]
    client_ids = [client.pk for client in clients]

    # Count and capacity in ONE pass. `Sum("capacity")` answers NULL — not 0 — when every reserved
    # bin leaves the column blank, and that NULL is carried all the way to the template on purpose:
    # "no bin records a capacity" is a different statement from "the capacity is zero", and only one
    # of them means somebody should go and fill the field in. Deliberately NOT wrapped in Coalesce.
    reserved = {}
    if client_ids:
        reserved = {row["owner_client_id"]: row for row in
                    Location.objects.filter(tenant=tenant, owner_client_id__in=client_ids)
                    .order_by()
                    .values("owner_client_id")
                    .annotate(n=Count("id"), capacity_total=Sum("capacity"))}

    labels = dict(SPACE_MODEL_CHOICES)
    rows = []
    for client in clients:
        bucket = reserved.get(client.pk)
        rows.append({
            "client": client,
            "space_model": client.space_model,
            "space_model_label": labels.get(client.space_model, client.space_model),
            "committed_sqft": client.committed_sqft or ZERO,
            "committed_pallet_positions": client.committed_pallet_positions or 0,
            "dedicated_locations": bucket["n"] if bucket else 0,
            "dedicated_capacity": bucket["capacity_total"] if bucket else None,
            "contract_start": client.contract_start,
            "contract_end": client.contract_end,
            # None, never 0, when no end date is on file: 0 would read as "expires today".
            "days_to_expiry": ((client.contract_end - today).days
                               if client.contract_end is not None else None),
        })

    capacities = [row["dedicated_capacity"] for row in rows
                  if row["dedicated_capacity"] is not None]
    totals = {
        "committed_sqft": sum((row["committed_sqft"] for row in rows), ZERO),
        "committed_pallet_positions": sum(row["committed_pallet_positions"] for row in rows),
        "dedicated_locations": sum(row["dedicated_locations"] for row in rows),
        # None rather than 0 when nothing was recorded — the same rule as the per-row column above.
        "dedicated_capacity": sum(capacities, ZERO) if capacities else None,
    }

    return render(request, "scm/3pl/client_space_report.html", {
        "rows": rows,
        "totals": totals,
        "space_model_choices": SPACE_MODEL_CHOICES,
        "clients": _client_qs(tenant),
        "truncated": truncated,
        "row_cap": MAX_REPORT_ROWS,
        "today": today,
        "capacity_note": CAPACITY_NOTE,
        "reads_only_note": READS_ONLY_NOTE,
    })


# =================================================================================================
# Prose the templates print
# =================================================================================================

#: On both pages. The single most important thing a reader has to understand about them.
READS_ONLY_NOTE = (
    "This page is computed, not stored. It writes nothing: no stock movement, no journal entry, no "
    "client or item record. Every figure is derived on read from rows another part of the system "
    "already owns, so there is no second number here to drift from the first."
)

#: On the inventory report, beside the location filter — the one place a filter changes what a
#: column MEANS rather than merely which rows are listed.
LOCATION_FILTER_NOTE = (
    "Filtering by location narrows the quantity and value figures to the stock held there. It does "
    "not narrow the assigned-SKU count, which is a property of the item master rather than of where "
    "the goods happen to be sitting."
)

#: On the space report, beside the capacity column. This is the whole difference between an honest
#: column and a misleading one.
CAPACITY_NOTE = (
    "Committed space is what the contract says. Reserved capacity is the sum of the capacity "
    "recorded on the bins assigned to this client, and that figure is in each bin's own units — it "
    "is not square feet, it is not pallet positions, and it is not necessarily the same unit from "
    "one bin to the next. The columns are shown side by side and are deliberately NOT converted "
    "into one another. Occupied pallet positions are not offered at all: items carry no dimensions "
    "in this system, so any such number would be an estimate presented as a measurement."
)

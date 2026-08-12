"""SCM 4.16 Customer Portal — the two COMPUTED staff pages (NavERP bullets 1 and 5).

``portal_order_tracking`` (Order Tracking) · ``portal_catalog_preview`` (Catalog Browsing).

**Neither page owns a table, and neither writes a row of any kind.** They are the
``coa_report`` / ``mrp_report`` / ``labor_board`` precedent applied to the portal: 4.5 owns the
order, 4.6 owns the shipment and its tracking events, 4.3 owns the item and the append-only
``StockMove`` ledger, and 4.16 owns only the ``PortalAccount`` row that decides how a given customer
sees any of it. Nothing here posts a ``StockMove``, drafts an ``Invoice`` or writes a
``JournalEntry`` (L29), and — deliberately — nothing here writes a ``PortalActivity`` either: that
log records **a read by a CUSTOMER**, and a member of staff opening a staff console is not one. A
page that logged itself would put fabricated customer reads into the very trail a document dispute
turns on.

Why each page exists, rather than being a filter on a page that already shipped:

* **``portal_order_tracking``** puts the order, what is allocated against it, the shipment's live
  status, its ETA, its exception and its POD state **in one row**. 4.5's order list knows nothing
  about shipments; 4.6's shipment list knows nothing about allocation or backorder. The whole value
  of the page is the join, and the join is the reason WISMO ("where is my order") is 25-40% of
  inbound support volume: today somebody answers it by opening two lists and a tab.
* **``portal_catalog_preview``** answers "what does customer X actually see?" — Sana's sales-agent
  view. Stock presentation, catalog scope and pricing are all per-ACCOUNT, so the only way to check
  a configuration before a customer hits it is to render that customer's projection.

  **# SECURITY: render-as, NEVER authenticate-as.** There is no session swap, no impersonation
  token, no ``login()`` call and no cookie of any kind involved. The staff user stays exactly who
  they are; the page reads one ``PortalAccount`` row and renders the projection that account
  configures. Impersonation would mean a staff session carrying a customer's identity — every write
  it then made would be attributed to the customer, and the audit trail would be fiction. This page
  needs none of that to answer the question it asks, so it does none of it.

**Aggregates are grouped and per-page, never per-row.** Every figure below that looks like it wants
a model method in a loop is instead ONE grouped query over the page's ids:

* line-level allocated/backordered — ``SalesOrderLine.quantity_allocated()`` /
  ``quantity_backordered()`` are correct on a detail page and are **two aggregates per line** on a
  console (``quantity_backordered()`` calls ``quantity_allocated()`` again, so it re-derives the
  same figure twice). :func:`_line_figures` is the same arithmetic as one ``GROUP BY line``.
* on-hand — ``Item.on_hand()`` is one aggregate per item; :func:`_stock_totals` is one
  ``GROUP BY item`` over ``StockMove`` for the whole page. Same ledger, same scope (every location,
  exactly as ``on_hand()`` sums), batched.
* the last-ordered price — one ``ROW_NUMBER() OVER (PARTITION BY item)`` pass over
  ``SalesOrderLine`` (:func:`_last_ordered_prices`), not "fetch this customer's whole order history
  and sort it in Python".

**Derived figures render as an em dash when they are ``None``, and NEVER as 0.** This is not
cosmetic. On the catalog, *no ledger rows exist for this item* and *we have none left* are different
facts, and ``stock_band()`` is built to keep them apart — ``None`` in, ``None`` out. Printing 0 for
the first tells a customer an item is unavailable when the truth is that nobody has ever counted it.
The one place a zero IS printed for an absent aggregate is ``quantity_allocated``, and it is correct
there for a reason stated at :func:`_line_figures`.

**Vocabulary comes from ``models/CustomerPortal/_choices.py``, never from here.** Availability words
and colours are ``STOCK_BAND_LABELS`` / ``STOCK_BAND_CSS`` keyed by ``stock_band()``. The two small
maps this module does declare (:data:`EXCEPTION_REASONS`, :data:`TRACKING_STATE_CSS` and friends)
are read by this file only, which is exactly the rule ``_choices.py``'s own docstring states: a
vocabulary read from one direction stays where it is used. Only the six classes that exist in
``static/css/theme.css`` appear — ``badge-green / badge-red / badge-amber / badge-info /
badge-muted / badge-slate``. ``badge-success`` / ``badge-warning`` / ``badge-danger`` do not exist
and render completely unstyled (L33).

=================================================================================================
CONTEXT-VARIABLE CONTRACT (pinned, L7). The templates are written by a separate pass, so every key
each page consumes is listed here — and **the row dicts are as much a contract as the page keys**:
a template built against a guessed key renders a grid of em dashes and still returns 200 (L41).
=================================================================================================

``scm/portal/order_tracking.html``
    Rows:        ``rows`` (list of ORDER ROW dicts) · ``row_count`` · ``page_obj`` (paginate())
                 — the computed-report precedent (``refund_queue``) uses ``rows``, NOT
                 ``object_list``; there is no model instance list to hand over, only row dicts.
    Filters:     ``q`` · ``portal_account`` / ``carrier`` / ``status`` / ``shipment_status`` /
                 ``state`` / ``portal_active`` (the raw echoed GET values — compare the two pk
                 params with ``o.pk|stringformat:"d"``, NEVER ``|slugify``) ·
                 ``date_from`` / ``date_to`` (echoed) · ``portal_accounts`` (queryset) ·
                 ``carriers`` (queryset) · ``status_choices`` · ``shipment_status_choices`` ·
                 ``state_choices`` · ``portal_active_choices``
    Totals:      ``exception_row_count`` · ``delayed_row_count`` · ``unshipped_row_count`` ·
                 ``awaiting_pod_count`` (all counted over the CURRENT PAGE — see the note where
                 they are built)
    Standing:    ``tracking_note`` · ``generated_at`` · ``no_tenant`` · ``no_tenant_note``

    ORDER ROW dict::

        obj              SalesOrder            pk / number / url        int / str / str
        customer         Party                 customer_id              int
        status           raw value             status_label             get_status_display()
        is_held          bool                  hold_reason              str  (INTERNAL — see below)
        order_date / requested_date / promised_date   date | None
        portal_account   PortalAccount | None  portal_account_number    str ("" when none)
        portal_active    bool
        line_count       int                   lines                    list of ORDER LINE dicts
        quantity_ordered / quantity_allocated / quantity_backordered    Decimal
        backordered_line_count                 int
        shipments        list of SHIPMENT dicts (LIVE only — cancelled ones are excluded)
        shipment_count   int                   cancelled_shipment_count int
        eta              datetime | None       delivered_count          int
        delayed_count    int                   exception_count          int
        exception_reason str ("" when clean — a CUSTOMER-READABLE sentence, never a raw code)
        state            key of TRACKING_STATE_LABELS      state_label / state_css   str
        pod_state        key of POD_STATE_LABELS           pod_label  / pod_css      str
        pod_received_at  datetime | None

    ORDER LINE dict::

        pk int    sku str ("" when unmapped)    description str
        quantity_ordered / quantity_allocated / quantity_backordered   Decimal
        is_backordered bool

    SHIPMENT dict::

        obj Shipment   pk / number / url        status / status_label / mode_label
        carrier        Carrier | None           tracking_number str
        current_status_text / last_known_location  str
        eta datetime | None    planned_delivery_date date | None    is_delayed bool
        pod_received bool      pod_received_at datetime | None
        exception_reason str ("" when clean)

    ``hold_reason`` is INTERNAL credit/fraud text written by 4.5's submit evaluation. It is on a
    staff page on purpose and **must never be echoed onto a customer-facing page.**

``scm/portal/catalog_preview.html``
    Picker:      ``account`` (PortalAccount | None) · ``account_id`` (raw echoed pk) ·
                 ``portal_accounts`` (queryset — the picker) · ``account_is_active`` (bool)
    Projection:  ``stock_display`` / ``stock_display_label`` · ``show_quantity`` / ``show_band`` /
                 ``band_as_text`` / ``show_locations`` (bools) · ``low_stock_threshold`` ·
                 ``price_basis`` / ``price_basis_label`` / ``show_price`` (bool) ·
                 ``catalog_scope`` / ``catalog_scope_label`` · ``scope_categories`` (queryset)
    Rows:        ``rows`` (list of CATALOG ROW dicts) · ``row_count`` · ``page_obj`` · ``item_count``
    Filters:     ``q`` · ``category`` (raw echoed pk) · ``item_categories`` (queryset — only the
                 categories actually reachable in this projection) · ``stock_display_choices`` ·
                 ``catalog_scope_choices`` · ``price_basis_choices``
    Standing:    ``render_as_note`` (the banner — render it prominently) · ``no_account_note`` ·
                 ``inactive_note`` (str, "" when the account is live) · ``preview_scope_note`` ·
                 ``generated_at`` · ``no_tenant`` · ``no_tenant_note``

    CATALOG ROW dict::

        obj Item   pk / sku / name / url        category str ("" when none)   uom str ("" when none)
        item_type_label str                     is_stocked bool
        on_hand  Decimal | None  — the raw ledger aggregate, and **None whenever the account's
                                   stock_display does not permit a number**, so a template bug
                                   cannot leak a figure the customer may not see
        band     "out"|"low"|"in"|None          band_label / band_css   str | None
        locations list of LOCATION dicts (empty unless show_locations)
        last_price Decimal | None   last_price_date date | None   last_order_number str

    LOCATION dict::

        location_id int   location str ("CODE · Name")   on_hand Decimal | None
        band / band_label / band_css   as above

    ``band_css`` is a COLOUR and colour is never the only carrier of the meaning: a template that
    renders the chip without visible text must still expose ``band_label`` as ``title`` /
    ``aria-label`` (``_choices.py`` states the rule; this is where it is handed over).
"""
from django.db.models.functions import RowNumber
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _date_window, _tms_carrier_qs
from apps.scm.models import (STOCK_BAND_CSS, STOCK_BAND_LABELS, CATALOG_SCOPE_CHOICES, Item,
                             ItemCategory, PRICE_BASIS_CHOICES, PortalAccount, SalesOrder,
                             SalesOrderLine, STOCK_DISPLAY_CHOICES, Shipment, StockMove,
                             TrackingEvent, stock_band)

ZERO = Decimal("0")

NO_TENANT_NOTE = ("This login has no tenant workspace, so there are no portal customers to report "
                  "on. Sign in as a workspace member to see this page.")


# =================================================================================================
# Shared vocabulary — read by this module only, which is why it lives here rather than in
# `models/CustomerPortal/_choices.py` (that file's own docstring states the rule: a vocabulary read
# from one direction stays where it is used; the ones it holds are read from two or more).
# =================================================================================================

#: A ``TrackingEvent.event_type`` -> the sentence a CUSTOMER can act on.
#:
#: **The raw code never reaches a page.** ``get_event_type_display()`` would give "Customs Hold",
#: which is a label for the person who wrote the integration, not an answer to "where is my order".
#: The whole reason bullet 1 and bullet 4 are one design problem is that a customer who cannot read
#: the tracking page opens a ticket instead — so the tracking page is where the plain sentence
#: belongs. Staff read this page, but they read it in order to say this sentence out loud, and a
#: sentence that lives in one place cannot be two different sentences on two channels.
#:
#: Only the three exception-shaped event types are mapped. Everything else is not an exception and
#: takes no reason at all — a blank, not a cheerful string, because a row with no problem should
#: print nothing rather than something reassuring nobody verified.
EXCEPTION_REASONS = {
    "exception": "The carrier has reported a problem with this delivery and is working on it.",
    "delayed": "This delivery is running behind the carrier's own schedule.",
    "customs_hold": "Held at customs while the import paperwork is cleared.",
}

#: The event types :data:`EXCEPTION_REASONS` covers, as a tuple for the ``__in`` lookup. Derived
#: from the map rather than retyped, so the query and the rendering can never come to disagree
#: about which events are exceptions.
EXCEPTION_EVENT_TYPES = tuple(EXCEPTION_REASONS)

#: What to say when the shipment's own STATUS is ``exception`` but no exception event explains it.
#: This is a real state — 4.6 lets a status be set from an event whose type has since been
#: superseded, and a shipment can be flagged without a narrative. Saying "there is a problem and we
#: do not yet know what" is honest; inventing a cause would not be.
UNEXPLAINED_EXCEPTION_REASON = ("This delivery is flagged as an exception and the carrier has not "
                                "yet said why.")

#: And when nothing is flagged but the planned delivery date has passed with the shipment still
#: moving (``Shipment.is_delayed``). That is a DERIVED delay, not a carrier-reported one, and the
#: wording says so rather than blaming a carrier that never reported anything.
DERIVED_DELAY_REASON = ("Past the delivery date we planned for, and still in transit. The carrier "
                        "has not reported a problem.")

#: The one chip the console sorts and filters on. Five states, and the ORDER of the branches that
#: assign them is a contract with the SQL filter — see :func:`_state_filter`.
TRACKING_STATE_LABELS = {
    "unshipped": "Not shipped yet",
    "exception": "Exception",
    "delayed": "Delayed",
    "in_transit": "On the way",
    "delivered": "Delivered",
}

#: Colour is by **what somebody has to do about it**: red is a problem a person must pick up, amber
#: is late and unattended, info is moving normally, green is done, slate is not started. A console
#: that is red by default trains its reader to ignore red (the ``INQUIRY_OUTCOME_CSS`` reasoning,
#: applied to a different vocabulary).
TRACKING_STATE_CSS = {
    "unshipped": "badge-slate",
    "exception": "badge-red",
    "delayed": "badge-amber",
    "in_transit": "badge-info",
    "delivered": "badge-green",
}

#: The filter dropdown, built FROM the label map so a state added above appears in the filter bar
#: automatically rather than being silently unfilterable.
STATE_CHOICES = [(value, label) for value, label in TRACKING_STATE_LABELS.items()]

#: Proof of delivery, as its own chip: it answers a different question from "where is it" and it is
#: the one a billing dispute turns on. ``awaiting`` is amber because it is the state somebody has to
#: chase — goods are with the customer and we cannot yet prove it.
POD_STATE_LABELS = {
    "no_shipment": "No shipment raised",
    "not_delivered": "Not delivered yet",
    "awaiting": "Delivered — proof of delivery outstanding",
    "received": "Proof of delivery received",
}
POD_STATE_CSS = {
    "no_shipment": "badge-slate",
    "not_delivered": "badge-muted",
    "awaiting": "badge-amber",
    "received": "badge-green",
}

#: A shipment that is still expected to move. Mirrors ``Shipment.is_delayed`` EXACTLY — that
#: property is the per-row verdict and this tuple is the SQL half of it, so they are written next to
#: each other and change together (§7.5: the filter SQL and the per-row verdict must agree).
OPEN_SHIPMENT_STATUSES = ("planned", "booked", "in_transit", "exception")

#: Orders this console tracks. Derived from ``SalesOrder.STATUS_CHOICES`` rather than typed out, so
#: a status added to 4.5 later is TRACKED by default instead of silently vanishing from a page whose
#: whole job is "which of my orders is somebody going to ask about".
#:
#: ``draft`` is excluded because a draft is an internal working document the customer has not been
#: told about, and ``CLOSED_STATUSES`` (cancelled / closed) because those are finished. Everything
#: between — including ``on_hold``, ``fulfilled`` and ``invoiced`` — stays: an invoiced order whose
#: POD never arrived is exactly the row this page exists to surface.
TRACKED_ORDER_STATUSES = tuple(
    value for value, _label in SalesOrder.STATUS_CHOICES
    if value != "draft" and value not in SalesOrder.CLOSED_STATUSES)

#: The two-value boolean filter, spelled out rather than left to a bare checkbox so the template can
#: render a three-state dropdown (all / on / off) and echo it back.
PORTAL_ACTIVE_CHOICES = [("True", "Portal switched on"), ("False", "Portal switched off")]

TRACKING_NOTE = (
    "Every figure on this page is derived at read time — 4.5 owns the order, 4.6 owns the shipment "
    "and its tracking events, and this page writes nothing. Allocated and backordered quantities "
    "come from the allocation ledger, never from a stored column, so they cannot drift from it. "
    "Only customers with a portal account appear here; a cancelled shipment is left out of the "
    "status roll-up because a withdrawn booking is not a movement of goods, but it is still counted "
    "so it is not hidden.")

RENDER_AS_NOTE = (
    "This is a RENDER-AS preview, not an impersonation. No session is swapped, no login is "
    "borrowed and no token is issued — you are still signed in as yourself, and the page simply "
    "renders the projection this customer's portal account configures. Nothing on this page is "
    "written, including the customer's own activity log: a member of staff looking at a preview is "
    "not a customer read.")

NO_ACCOUNT_NOTE = ("Pick a customer above to see their catalog exactly as their portal renders it — "
                   "their stock presentation, their catalog scope and their pricing.")

INACTIVE_ACCOUNT_NOTE = (
    "This portal account is switched OFF, so the customer currently sees none of this: every gated "
    "portal page refuses at the account check. The preview below is what they WOULD see if the "
    "account were switched back on.")

PREVIEW_SCOPE_NOTE = (
    "The preview renders the three things this ACCOUNT configures — which items are in scope, how "
    "much of the live stock figure it may show, and whether a price appears. Anything the customer "
    "catalog shows that is the same for every customer is deliberately not duplicated here; this "
    "page answers 'what does THIS configuration produce', not 'what does the catalog page look "
    "like'.")


# =================================================================================================
# Order Tracking (bullet 1) — helpers
# =================================================================================================

def _live_shipments(tenant):
    """The shipments that count, bound to the outer order: this tenant's, and not cancelled.

    Returned already correlated through ``OuterRef("pk")``, because every caller wraps it in an
    ``Exists``. The ``tenant`` term is redundant with the outer order's own tenant filter and is
    kept anyway: an authorisation scope that is only IMPLIED by a join is one refactor away from
    not being there at all.
    """
    return (Shipment.objects.filter(tenant=tenant, sales_order_id=OuterRef("pk"))
            .exclude(status="cancelled"))


def _state_filter(qs, state, tenant, today):
    """Narrow ``qs`` to one derived tracking state, in SQL.

    **The SQL here and the per-row verdict in :func:`_row_state` are two spellings of one rule**
    (§7.5). The row branches in the order ``unshipped -> exception -> delayed -> delivered ->
    in_transit``, so each clause below re-states the branches ABOVE it as negations — without that,
    ``?state=delayed`` would return rows the page then chips as "Exception", and a filtered console
    that disagrees with itself is worse than one with no filter.

    An unrecognised value narrows NOTHING rather than returning an empty page: a stale bookmark or a
    hand-typed ``?state=lost`` must not render "there is no work" (L11's posture — a bad filter
    value is skipped, not obeyed).
    """
    live = _live_shipments(tenant)
    has_any = Exists(live)
    has_exception = Exists(live.filter(status="exception"))
    # The SQL half of `Shipment.is_delayed`: a planned date in the past on a shipment still expected
    # to move. `planned_delivery_date__lt` already excludes NULL, exactly as the property's `bool()`
    # guard does.
    has_delayed = Exists(live.filter(planned_delivery_date__lt=today,
                                     status__in=OPEN_SHIPMENT_STATUSES))
    has_undelivered = Exists(live.exclude(status="delivered"))

    if state == "unshipped":
        return qs.filter(~has_any)
    if state == "exception":
        return qs.filter(has_exception)
    if state == "delayed":
        return qs.filter(has_delayed, ~has_exception)
    if state == "delivered":
        return qs.filter(has_any, ~has_undelivered, ~has_exception, ~has_delayed)
    if state == "in_transit":
        return qs.filter(has_any, has_undelivered, ~has_exception, ~has_delayed)
    return qs


def _row_state(shipments):
    """The per-row verdict :func:`_state_filter` encodes in SQL. Pure — takes the row's own dicts."""
    if not shipments:
        return "unshipped"
    if any(s["status"] == "exception" for s in shipments):
        return "exception"
    if any(s["is_delayed"] for s in shipments):
        return "delayed"
    if all(s["status"] == "delivered" for s in shipments):
        return "delivered"
    return "in_transit"


def _pod_state(shipments):
    """Proof-of-delivery roll-up for one order. Same shape of rule as :func:`_row_state`."""
    if not shipments:
        return "no_shipment"
    delivered = [s for s in shipments if s["status"] == "delivered"]
    if len(delivered) != len(shipments):
        return "not_delivered"
    return "received" if all(s["pod_received"] for s in delivered) else "awaiting"


def _line_figures(order_ids):
    """``{order_id: (line dicts, ordered, allocated, backordered, backordered_line_count)}``.

    **ONE grouped query for every line on the page.** The obvious version — calling
    ``line.quantity_allocated()`` and ``line.quantity_backordered()`` per row — costs two aggregates
    per line and re-derives the same figure twice, because ``quantity_backordered()`` calls
    ``quantity_allocated()`` again. ``SalesOrder.recompute_allocation_status()`` already solved
    exactly this and its comment says why; this is the same fix on the read side.

    **The fan-out trap, stated so nobody "simplifies" it away:** this groups at LINE level, not at
    order level. ``values("sales_order_id").annotate(ordered=Sum("quantity_ordered"),
    allocated=Sum("allocations__quantity"))`` looks like one query fewer and is WRONG — the join to
    the allocation table multiplies a line's row once per allocation, so ``ordered`` silently
    counts a two-allocation line twice. Grouping per line makes the join one-to-many against a
    single grouped row, and the order totals are then summed in Python from figures that are each
    correct.

    ``Sum`` answers ``None`` when a line has no allocation rows at all, and that is coalesced to
    ZERO **here and only here**. It is a genuine zero, not a missing measurement: an allocation is a
    positive reservation, so "no rows" means "nothing reserved" and ``quantity_allocated()`` itself
    returns ZERO for it. Contrast the stock aggregate on the catalog page, where ``None`` must
    survive all the way to an em dash because the ledger is the ONLY source of the quantity.
    """
    figures = {}
    rows = (SalesOrderLine.objects
            .filter(sales_order_id__in=order_ids)
            .annotate(_allocated=Sum("allocations__quantity",
                                     filter=~Q(allocations__status="cancelled")))
            # `_allocated` is named in values() on purpose: values() AFTER annotate() returns ONLY
            # the columns it lists, so leaving the annotation out drops it from the result dicts
            # while still computing it in SQL — a KeyError, or worse, a silent zero.
            .values("id", "sales_order_id", "quantity_ordered", "description", "item__sku",
                    "_allocated")
            .order_by("sales_order_id", "id"))
    for row in rows:
        ordered = row["quantity_ordered"] or ZERO
        allocated = row["_allocated"] or ZERO
        backordered = ordered - allocated
        if backordered < ZERO:
            # Over-allocation is possible (a line can be reserved beyond what was ordered) and it is
            # not a backorder. Clamping matches `quantity_backordered()`, which returns ZERO rather
            # than a negative — a negative backorder on a console would read as a credit.
            backordered = ZERO
        entry = figures.setdefault(row["sales_order_id"],
                                   {"lines": [], "ordered": ZERO, "allocated": ZERO,
                                    "backordered": ZERO, "backordered_lines": 0})
        entry["lines"].append({
            "pk": row["id"],
            "sku": row["item__sku"] or "",
            "description": row["description"] or "",
            "quantity_ordered": ordered,
            "quantity_allocated": allocated,
            "quantity_backordered": backordered,
            "is_backordered": backordered > ZERO,
        })
        entry["ordered"] += ordered
        entry["allocated"] += allocated
        entry["backordered"] += backordered
        if backordered > ZERO:
            entry["backordered_lines"] += 1
    return figures


def _exception_events(shipment_ids):
    """``{shipment_id: TrackingEvent}`` — the LATEST exception-shaped event per shipment, one query.

    ``TrackingEvent`` is append-only and ordered newest-first by its own Meta, so the first row seen
    for a shipment is the current one. Only the three exception types are fetched: the non-exception
    narrative is already projected onto ``Shipment.current_status_text`` by
    ``apply_tracking_event()``, and re-reading the whole log to recover something the summary column
    already carries would be a second source of truth for one fact.
    """
    latest = {}
    if not shipment_ids:
        return latest
    for event in (TrackingEvent.objects
                  .filter(shipment_id__in=shipment_ids, event_type__in=EXCEPTION_EVENT_TYPES)
                  .order_by("shipment_id", "-event_at", "-id")):
        latest.setdefault(event.shipment_id, event)
    return latest


def _shipment_reason(shipment, event):
    """The customer-readable reason for one shipment, or ``""`` when there is nothing wrong.

    Precedence: what the carrier actually said, then the flag with no narrative behind it, then our
    own derived lateness. Never a raw ``event_type``.
    """
    if event is not None:
        return EXCEPTION_REASONS.get(event.event_type, UNEXPLAINED_EXCEPTION_REASON)
    if shipment.status == "exception":
        return UNEXPLAINED_EXCEPTION_REASON
    if shipment.is_delayed:
        return DERIVED_DELAY_REASON
    return ""


def _shipment_rows(order_ids, tenant):
    """``{order_id: [SHIPMENT dict, …]}`` plus the cancelled counts — two queries for the page.

    Cancelled shipments are counted but not listed: a withdrawn booking is not a movement of goods,
    and letting one sit in the roll-up would make "all delivered" unreachable on any order whose
    first booking fell through. The count is still handed over so the fact is visible rather than
    quietly dropped.
    """
    rows, cancelled = {}, {}
    if not order_ids:
        return rows, cancelled
    shipments = list(Shipment.objects
                     .filter(tenant=tenant, sales_order_id__in=order_ids)
                     .select_related("carrier__party")
                     .order_by("sales_order_id", "-id"))
    live = [s for s in shipments if s.status != "cancelled"]
    events = _exception_events([s.pk for s in live])
    for shipment in shipments:
        if shipment.status == "cancelled":
            cancelled[shipment.sales_order_id] = cancelled.get(shipment.sales_order_id, 0) + 1
            continue
        rows.setdefault(shipment.sales_order_id, []).append({
            "obj": shipment,
            "pk": shipment.pk,
            "number": shipment.number,
            # reverse(), never a hand-built path: the mount point of `apps.scm` is a config decision
            # and a literal "/scm/…" here would be a link that silently 404s the day it moves.
            "url": reverse("scm:shipment_detail", args=[shipment.pk]),
            "status": shipment.status,
            "status_label": shipment.get_status_display(),
            "mode_label": shipment.get_mode_display(),
            "carrier": shipment.carrier,
            "tracking_number": shipment.carrier_tracking_number or "",
            "current_status_text": shipment.current_status_text or "",
            "last_known_location": shipment.last_known_location or "",
            "eta": shipment.eta,
            "planned_delivery_date": shipment.planned_delivery_date,
            # A model PROPERTY, not a query — `is_delayed` reads two columns already in memory.
            "is_delayed": shipment.is_delayed,
            "pod_received": shipment.pod_received,
            "pod_received_at": shipment.pod_received_at,
            "exception_reason": _shipment_reason(shipment, events.get(shipment.pk)),
        })
    return rows, cancelled


def _portal_account_qs(tenant):
    """The tenant's portal accounts, ordered by the name a human would look for them under."""
    if tenant is None:
        return PortalAccount.objects.none()
    return (PortalAccount.objects.filter(tenant=tenant)
            .select_related("customer").order_by("customer__name", "number"))


# =================================================================================================
# Order Tracking (NavERP bullet 1)
# =================================================================================================

@login_required
def portal_order_tracking(request):
    """Portal customers' open orders with shipment status, ETA, exception and POD state in one row.

    **This join is the page.** 4.5's order list has no shipment column and 4.6's shipment list has
    no allocation or backorder figure, so answering "where is my order" today means opening two
    lists and reconciling them by order number. Every column below already exists somewhere; what
    did not exist is the row.

    FILTERS, all applied BEFORE pagination so page 2 shows the right rows: ``q`` (order number,
    customer name, carrier tracking number), ``portal_account`` and ``carrier`` (both ints through
    ``as_db_int``, so ``?carrier=abc``, ``?carrier=²`` and a 20-digit value skip the filter rather
    than raising out of ``.filter()`` — L11), ``status`` (order), ``shipment_status``,
    ``portal_active``, the derived ``state`` bucket (:func:`_state_filter`) and a ``date_from`` /
    ``date_to`` window on ``order_date``.

    QUERY COUNT is flat in the number of rows: one for the page of orders, one for their lines
    (grouped), one for their shipments, one for the exception events, one for the portal accounts,
    plus the two small dropdown querysets. Nothing is per-row.
    """
    tenant = request.tenant
    today = timezone.localdate()

    # Base scope: an order belonging to a customer this workspace has given a portal account. The
    # Exists is what makes the page mean "portal customers" rather than "every order"; it also keeps
    # the page honest when the portal is enabled for two customers out of four hundred.
    has_account = Exists(PortalAccount.objects.filter(tenant=tenant,
                                                      customer_id=OuterRef("customer_id")))
    qs = (SalesOrder.objects
          .filter(tenant=tenant, status__in=TRACKED_ORDER_STATUSES)
          .filter(has_account)
          .select_related("customer")
          .order_by("-order_date", "-id"))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q)
                       | Q(customer__name__icontains=q)
                       | Q(shipments__carrier_tracking_number__icontains=q)).distinct()

    account_raw = (request.GET.get("portal_account") or "").strip()
    account_pk = as_db_int(account_raw)
    if account_pk is not None:
        # Through the ACCOUNT's own row, never through a customer pk typed straight at the order:
        # the filter has to mean "this portal account". An Exists rather than a join so a future
        # second account per customer could not duplicate an order across the page, and so the
        # tenant term travels WITH the pk — a foreign account pk then matches nothing rather than
        # silently widening the page.
        qs = qs.filter(Exists(PortalAccount.objects.filter(
            pk=account_pk, tenant=tenant, customer_id=OuterRef("customer_id"))))

    carrier_raw = (request.GET.get("carrier") or "").strip()
    carrier_pk = as_db_int(carrier_raw)
    if carrier_pk is not None:
        qs = qs.filter(Exists(_live_shipments(tenant).filter(carrier_id=carrier_pk)))

    status = (request.GET.get("status") or "").strip()
    if status in TRACKED_ORDER_STATUSES:
        # Membership-tested rather than passed through: a value outside the tracked set can only
        # ever return nothing, and an empty page is exactly the wrong answer to a stale bookmark.
        qs = qs.filter(status=status)

    shipment_status = (request.GET.get("shipment_status") or "").strip()
    if shipment_status:
        qs = qs.filter(Exists(_live_shipments(tenant).filter(status=shipment_status)))

    portal_active = (request.GET.get("portal_active") or "").strip()
    if portal_active in ("True", "False"):
        qs = qs.filter(Exists(PortalAccount.objects.filter(
            tenant=tenant, customer_id=OuterRef("customer_id"),
            is_active=(portal_active == "True"))))

    state = (request.GET.get("state") or "").strip()
    qs = _state_filter(qs, state, tenant, today)
    qs = _date_window(qs, request.GET, "order_date")

    page_obj = paginate(request, qs)
    orders = list(page_obj.object_list)
    order_ids = [order.pk for order in orders]

    figures = _line_figures(order_ids)
    shipments_by_order, cancelled_by_order = _shipment_rows(order_ids, tenant)
    # One query for the accounts on this page. `unique_together ("tenant", "customer")` makes the
    # map exact — there is never a second account to pick between.
    accounts = {a.customer_id: a for a in
                PortalAccount.objects.filter(tenant=tenant,
                                             customer_id__in=[o.customer_id for o in orders])}

    rows = []
    for order in orders:
        shipments = shipments_by_order.get(order.pk, [])
        figure = figures.get(order.pk, {"lines": [], "ordered": ZERO, "allocated": ZERO,
                                        "backordered": ZERO, "backordered_lines": 0})
        account = accounts.get(order.customer_id)
        state_key = _row_state(shipments)
        pod_key = _pod_state(shipments)
        # The order's ETA is the LATEST of its shipments' — the order is not complete until the last
        # box lands, so the earliest one would be a promise the order cannot keep. None when no
        # shipment carries an ETA at all, which renders as an em dash rather than as "today".
        etas = [s["eta"] for s in shipments if s["eta"] is not None]
        # The first reason in shipment order, so a multi-shipment order shows the problem rather
        # than the first shipment's silence.
        reasons = [s["exception_reason"] for s in shipments if s["exception_reason"]]
        pod_stamps = [s["pod_received_at"] for s in shipments if s["pod_received_at"] is not None]
        rows.append({
            "obj": order,
            "pk": order.pk,
            "number": order.number,
            "url": reverse("scm:salesorder_detail", args=[order.pk]),
            "customer": order.customer,
            "customer_id": order.customer_id,
            "status": order.status,
            "status_label": order.get_status_display(),
            "is_held": order.is_held,
            # INTERNAL credit/fraud text. It belongs on a staff console and must never be echoed
            # onto a customer-facing page — see the module docstring.
            "hold_reason": order.hold_reason or "",
            "order_date": order.order_date,
            "requested_date": order.requested_date,
            "promised_date": order.promised_date,
            "portal_account": account,
            "portal_account_number": account.number if account is not None else "",
            "portal_active": bool(account is not None and account.is_active),
            "line_count": len(figure["lines"]),
            "lines": figure["lines"],
            "quantity_ordered": figure["ordered"],
            "quantity_allocated": figure["allocated"],
            "quantity_backordered": figure["backordered"],
            "backordered_line_count": figure["backordered_lines"],
            "shipments": shipments,
            "shipment_count": len(shipments),
            "cancelled_shipment_count": cancelled_by_order.get(order.pk, 0),
            "eta": max(etas) if etas else None,
            "delivered_count": sum(1 for s in shipments if s["status"] == "delivered"),
            "delayed_count": sum(1 for s in shipments if s["is_delayed"]),
            "exception_count": sum(1 for s in shipments if s["status"] == "exception"),
            "exception_reason": reasons[0] if reasons else "",
            "state": state_key,
            "state_label": TRACKING_STATE_LABELS[state_key],
            "state_css": TRACKING_STATE_CSS[state_key],
            "pod_state": pod_key,
            "pod_label": POD_STATE_LABELS[pod_key],
            "pod_css": POD_STATE_CSS[pod_key],
            "pod_received_at": max(pod_stamps) if pod_stamps else None,
        })

    return render(request, "scm/portal/order_tracking.html", {
        "rows": rows,
        "row_count": len(rows),
        "page_obj": page_obj,
        "q": q,
        # Counted over THIS PAGE, not the whole filtered set, and labelled as such in the template:
        # a whole-set figure would need the state verdict computed for every matching order, which
        # is the per-row work this page is built to avoid. The `state` filter is how somebody asks
        # the whole-set question — it narrows in SQL and then the paginator reports the total.
        "exception_row_count": sum(1 for r in rows if r["state"] == "exception"),
        "delayed_row_count": sum(1 for r in rows if r["state"] == "delayed"),
        "unshipped_row_count": sum(1 for r in rows if r["state"] == "unshipped"),
        "awaiting_pod_count": sum(1 for r in rows if r["pod_state"] == "awaiting"),
        # --- filter context: every choice list AND every queryset behind a pk dropdown ---
        "portal_account": account_raw,
        "carrier": carrier_raw,
        "status": status,
        "shipment_status": shipment_status,
        "state": state,
        "portal_active": portal_active,
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
        "portal_accounts": _portal_account_qs(tenant),
        "carriers": _tms_carrier_qs(tenant),
        # Narrowed to what the page can actually show. Offering `draft` / `cancelled` / `closed`
        # would be offering three ways to guarantee an empty result.
        "status_choices": [(value, label) for value, label in SalesOrder.STATUS_CHOICES
                           if value in TRACKED_ORDER_STATUSES],
        # Same rule for shipments: cancelled ones are excluded from the roll-up, so a
        # `?shipment_status=cancelled` could only ever return nothing.
        "shipment_status_choices": [(value, label) for value, label in Shipment.STATUS_CHOICES
                                    if value != "cancelled"],
        "state_choices": STATE_CHOICES,
        "portal_active_choices": PORTAL_ACTIVE_CHOICES,
        "tracking_note": TRACKING_NOTE,
        "generated_at": timezone.localtime(),
        "no_tenant": tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
    })


# =================================================================================================
# Catalog Browsing (bullet 5) — helpers
# =================================================================================================

def _catalog_scope_qs(tenant, account):
    """The items in THIS account's catalog — the ``catalog_scope`` vocabulary turned into a queryset.

    ``is_active=True`` applies to all three scopes, including ``previously_ordered``: a catalog is a
    buying surface, and offering a customer something that has been withdrawn is offering a
    one-click disappointment. An item they bought last year that is now inactive is history, not
    stock.
    """
    items = Item.objects.filter(tenant=tenant, is_active=True)
    if account.catalog_scope == "previously_ordered":
        # Their OWN history, through the order they placed. `.distinct()` because an item bought on
        # five orders is one catalog row.
        return items.filter(sales_order_lines__sales_order__tenant=tenant,
                            sales_order_lines__sales_order__customer_id=account.customer_id).distinct()
    if account.catalog_scope == "categories":
        # An account configured for `categories` with no categories chosen shows NOTHING, and that
        # is the truthful projection: `PortalAccountForm.clean()` is what stops the configuration
        # being saved in the first place, so a row in this state predates the rule or was written
        # around the form. Showing every item instead would hide the misconfiguration behind a
        # catalog that looks fine.
        return items.filter(category__in=account.catalog_categories.all())
    return items


def _stock_totals(tenant, item_ids):
    """``{item_id: Decimal}`` — ONE ``GROUP BY item`` over the append-only ledger for the page.

    Identical arithmetic and identical scope to ``Item.on_hand()`` (every location summed, no move
    type excluded), batched. Calling the method per row is one aggregate per item, on a page whose
    entire content is aggregates.

    **An item with no ledger rows is ABSENT from the result, and the caller must keep it absent.**
    ``.get(item_id)`` then answers ``None``, which ``stock_band()`` maps to ``None`` and the
    template renders as an em dash. Coalescing it to zero here would be a one-character change that
    tells customers an item is out of stock when the truth is that nobody has ever counted it.
    """
    if not item_ids:
        return {}
    return {row["item_id"]: row["qty"] for row in
            StockMove.objects.filter(tenant=tenant, item_id__in=item_ids)
            .values("item_id").annotate(qty=Sum("quantity")).order_by()}


def _stock_by_location(tenant, item_ids):
    """``{item_id: [(location_id, "CODE · Name", Decimal), …]}`` — one ``GROUP BY (item, location)``.

    Only ever run when the account sets ``show_by_location``; it is off by default because a
    per-site breakdown tells a competitor where our stock sits.

    **It breaks down by STOCK LOCATION, not by warehouse.** ``StockMove`` posts against the location
    named on the move, which for a WMS-managed tenant is a bin; rolling bins up to their warehouse
    would need a recursive walk of ``Location.parent`` that 4.3's flat self-FK cannot do in one
    query. Named here rather than silently approximated — a page that printed a bin's quantity under
    a warehouse heading would be wrong in a way nobody could see.
    """
    if not item_ids:
        return {}
    grouped = {}
    rows = (StockMove.objects.filter(tenant=tenant, item_id__in=item_ids)
            .values("item_id", "location_id", "location__code", "location__name")
            .annotate(qty=Sum("quantity"))
            .order_by("item_id", "location__code"))
    for row in rows:
        label = f"{row['location__code']} · {row['location__name']}"
        grouped.setdefault(row["item_id"], []).append(
            (row["location_id"], label, row["qty"]))
    return grouped


def _last_ordered_prices(tenant, customer_id, item_ids):
    """``{item_id: (unit_price, order_date, order_number)}`` — this customer's own last price.

    ONE query. ``ROW_NUMBER() OVER (PARTITION BY item ORDER BY order_date DESC, …)`` filtered to
    rank 1 returns exactly one line per item; the alternatives are worse in both directions —
    fetching the customer's whole order history and sorting it in Python is unbounded, and
    ``Max("order_date")`` per item cannot bring the price along with it without a second query.

    Draft and cancelled orders are excluded: a price on a document the customer never agreed to is
    not a price they last paid, and quoting one back to them would be a commitment made by a page.

    The tie-break chain (order date, then order id, then line id) is total, so the answer does not
    depend on row order for two lines dated the same day. There is no customer price master on the
    SCM side — this IS the only price 4.16 can state truthfully, and a real price engine is 9.3.
    """
    if not item_ids or customer_id is None:
        return {}
    ranked = (SalesOrderLine.objects
              .filter(sales_order__tenant=tenant, sales_order__customer_id=customer_id,
                      item_id__in=item_ids)
              .exclude(sales_order__status__in=("draft", "cancelled"))
              .annotate(_rank=models.Window(
                  expression=RowNumber(),
                  partition_by=[F("item_id")],
                  order_by=[F("sales_order__order_date").desc(nulls_last=True),
                            F("sales_order_id").desc(), F("id").desc()]))
              .filter(_rank=1)
              .values("item_id", "unit_price", "sales_order__order_date", "sales_order__number"))
    return {row["item_id"]: (row["unit_price"], row["sales_order__order_date"],
                             row["sales_order__number"] or "")
            for row in ranked}


def _band(quantity, threshold):
    """``(band, label, css)`` for a derived quantity — or ``(None, None, None)``.

    The words and the colours come from ``_choices.py`` and are decided nowhere else, so the text
    display and the colour chip cannot disagree about the same quantity on the same page.
    """
    band = stock_band(quantity, threshold)
    if band is None:
        return None, None, None
    return band, STOCK_BAND_LABELS[band], STOCK_BAND_CSS[band]


# =================================================================================================
# Catalog Browsing (NavERP bullet 5)
# =================================================================================================

@login_required
def portal_catalog_preview(request):
    """The customer's catalog, rendered as their portal account configures it.

    # SECURITY: render-as, NEVER authenticate-as. No session is swapped, no impersonation token is
    # issued, no `login()` is called and no customer credential is touched. The staff user stays
    # signed in as themselves; the page reads ONE `PortalAccount` row and renders the projection
    # that row configures, and nothing more. Impersonation would attribute every subsequent write to
    # the customer and turn the audit trail into fiction — and it is not needed to answer the
    # question this page asks.

    The page also writes nothing at all, including no ``PortalActivity`` row: that log records a
    read BY A CUSTOMER, and a staff preview is not one. Logging it would put fabricated customer
    reads into the trail a document dispute turns on.

    THE PICKER accepts ``?account=<PortalAccount pk>`` and, for the "Preview catalog as this
    customer" button on the account detail page, ``?customer=<Party pk>`` — the account wins when
    both are present. Both go through ``as_db_int`` and are then resolved **against this tenant**,
    so a junk value and another workspace's pk take the same answer: no account, the picker, and the
    standing note (L11 for the first, an authorisation boundary for the second — a narrowed dropdown
    has never held against a hand-typed query string).

    FILTERS applied BEFORE pagination: ``q`` (sku / name / description) and ``category`` (int).
    **There is deliberately no "in stock only" filter.** Availability is a band computed from a
    grouped aggregate taken over the page's items AFTER pagination, so filtering on it would need a
    second aggregate over the whole catalog on every page load — and a band is a projection of the
    account's display setting, not a property of the item. Stated rather than silently missing.
    """
    tenant = request.tenant
    accounts = _portal_account_qs(tenant)

    account_raw = (request.GET.get("account") or "").strip()
    customer_raw = (request.GET.get("customer") or "").strip()
    account_pk, customer_pk = as_db_int(account_raw), as_db_int(customer_raw)
    account = None
    # Resolved out of the SAME tenant-scoped queryset the picker renders, so the dropdown and the
    # authorisation check cannot disagree. `prefetch_related` on the M2M because the scope query and
    # the template's "which categories" panel both read it — one fetch, not two.
    pickable = accounts.prefetch_related("catalog_categories")
    if account_pk is not None:
        account = pickable.filter(pk=account_pk).first()
    elif customer_pk is not None:
        account = pickable.filter(customer_id=customer_pk).first()

    q = (request.GET.get("q") or "").strip()
    category_raw = (request.GET.get("category") or "").strip()
    category_pk = as_db_int(category_raw)

    if account is None:
        # No account picked (or a pk that resolves to nothing in this workspace): the picker, the
        # note, and an EMPTY page rather than a default projection. There is no such thing as "the
        # catalog" here — every figure on this page is per-account, so guessing one would be
        # inventing a customer.
        scope = Item.objects.none()
        categories = ItemCategory.objects.none()
    else:
        scope = _catalog_scope_qs(tenant, account)
        # Exactly the categories reachable in THIS projection, so the dropdown can never offer a
        # value that returns an empty page.
        categories = (ItemCategory.objects.filter(tenant=tenant, items__in=scope)
                      .distinct().order_by("name"))
        if q:
            scope = scope.filter(Q(sku__icontains=q) | Q(name__icontains=q)
                                 | Q(description__icontains=q))
        if category_pk is not None:
            scope = scope.filter(category_id=category_pk)
    scope = scope.select_related("category", "uom").order_by("sku")

    page_obj = paginate(request, scope)
    items = list(page_obj.object_list)
    item_ids = [item.pk for item in items]

    # What the account's configuration PERMITS, resolved once for the page. The per-row values below
    # are set to None whenever the display forbids them, so a template bug cannot leak a number the
    # customer may not see — the figure is never handed over in the first place.
    stock_display = account.stock_display if account is not None else "hidden"
    show_quantity = stock_display == "exact_quantity"
    show_band = stock_display in ("availability_text", "band")
    band_as_text = stock_display == "availability_text"
    show_locations = bool(account is not None and account.show_by_location
                          and (show_quantity or show_band))
    threshold = account.low_stock_threshold if account is not None else ZERO
    show_price = bool(account is not None and account.price_basis == "last_ordered")

    totals = _stock_totals(tenant, item_ids) if (account is not None
                                                 and (show_quantity or show_band)) else {}
    by_location = _stock_by_location(tenant, item_ids) if show_locations else {}
    prices = (_last_ordered_prices(tenant, account.customer_id, item_ids)
              if show_price else {})

    rows = []
    for item in items:
        # Absent from `totals` means NO LEDGER ROWS, which is not zero — see _stock_totals. A
        # non-stocked item (a service) has no ledger at all, so it is None for a second, different
        # reason and prints the same em dash.
        quantity = totals.get(item.pk) if item.is_stocked else None
        band, band_label, band_css = _band(quantity, threshold)
        locations = []
        for location_id, label, location_qty in by_location.get(item.pk, ()):
            loc_band, loc_label, loc_css = _band(location_qty, threshold)
            locations.append({
                "location_id": location_id,
                "location": label,
                # The SAME suppression rules one level down. A breakdown row that carried a number
                # or a colour chip the account's display forbids would be the leak the row-level
                # rule exists to prevent, wearing a warehouse code — and an exact-quantity account
                # showing a band beside its own figure would be two answers to one question.
                "on_hand": location_qty if show_quantity else None,
                "band": loc_band if show_band else None,
                "band_label": loc_label if show_band else None,
                "band_css": loc_css if show_band else None,
            })
        price, price_date, price_order = prices.get(item.pk, (None, None, ""))
        rows.append({
            "obj": item,
            "pk": item.pk,
            "sku": item.sku,
            "name": item.name,
            "url": reverse("scm:item_detail", args=[item.pk]),
            "category": item.category.name if item.category_id else "",
            "uom": item.uom.code if item.uom_id else "",
            "item_type_label": item.get_item_type_display(),
            "is_stocked": item.is_stocked,
            "on_hand": quantity if show_quantity else None,
            "band": band if show_band else None,
            "band_label": band_label if show_band else None,
            "band_css": band_css if show_band else None,
            "locations": locations,
            "last_price": price,
            "last_price_date": price_date,
            "last_order_number": price_order,
        })

    return render(request, "scm/portal/catalog_preview.html", {
        "rows": rows,
        "row_count": len(rows),
        "page_obj": page_obj,
        "item_count": page_obj.paginator.count,
        "q": q,
        # --- the picker ---
        "account": account,
        "account_id": account_raw or customer_raw,
        "portal_accounts": accounts,
        "account_is_active": bool(account is not None and account.is_active),
        # --- the projection this account configures ---
        "stock_display": stock_display,
        "stock_display_label": (account.get_stock_display_display()
                                if account is not None else ""),
        "show_quantity": show_quantity,
        "show_band": show_band,
        "band_as_text": band_as_text,
        "show_locations": show_locations,
        "low_stock_threshold": threshold,
        "price_basis": account.price_basis if account is not None else "hidden",
        "price_basis_label": (account.get_price_basis_display() if account is not None else ""),
        "show_price": show_price,
        "catalog_scope": account.catalog_scope if account is not None else "",
        "catalog_scope_label": (account.get_catalog_scope_display()
                                if account is not None else ""),
        "scope_categories": (account.catalog_categories.all() if account is not None
                             else ItemCategory.objects.none()),
        # --- filter context: every choice list AND every queryset behind a pk dropdown ---
        "category": category_raw,
        "item_categories": categories,
        "stock_display_choices": STOCK_DISPLAY_CHOICES,
        "catalog_scope_choices": CATALOG_SCOPE_CHOICES,
        "price_basis_choices": PRICE_BASIS_CHOICES,
        # --- standing notes ---
        "render_as_note": RENDER_AS_NOTE,
        "no_account_note": NO_ACCOUNT_NOTE,
        "inactive_note": ("" if account is None or account.is_active else INACTIVE_ACCOUNT_NOTE),
        "preview_scope_note": PREVIEW_SCOPE_NOTE,
        "generated_at": timezone.localtime(),
        "no_tenant": tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
    })

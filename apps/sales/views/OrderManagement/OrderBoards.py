"""Sales 8.6 — the seven read-only boards and the three POST verbs that act on them.

Every board in this file is a **projection over facts that already exist**. There is no board
model, no board table, and no stored board figure anywhere in 8.6: the capture queue is SCM 4.5's
``SalesOrder``, the backorder quantities are 4.5's derived
``SalesOrderLine.quantity_backordered()``, the revenue balances are this sub-module's own
``RevenueSchedule`` ``@property`` values, and the renewal watch is a read-only lens over
Accounting 2.4's ``RecurringInvoice``. Nothing here is a second source of truth that can fall out
of date, and — the other half of that — nothing here can be edited.

**Why the boards are worth having at all**, when a filter on the underlying list would do the same
job: each one answers a question that crosses module boundaries. "Which orders are waiting on
something?" spans 4.5's status, 8.6's holds, 4.5's allocations and 4.6's shipments; "who is due to
reorder?" spans 4.5's order history and 4.5's shipment delivery facts. A board is that cross-module
read assembled once, in one place — and each page says in visible prose that its figures are
derived, because a number that looks like a column and is not needs telling.

Ownership (L36/L37) is the constraint everything else follows from. ``scm.SalesOrder`` is SCM 4.5's:

* the seven boards **read** any scm/accounting field they need and write **nothing**;
* the three verbs write only through 4.5's own code — ``salesorderallocation_release`` /
  ``salesorderallocation_cancel`` for a backorder, and 4.5's own ``recalc_totals()`` plus its own
  status defaults for a repeat. No view here writes ``SalesOrder.status``, ``promised_date``, a
  quantity or a total directly, and no view posts a ``JournalEntry`` (L29).

Three structural rules, the same three the four entity modules obey:

* **Tenant scope, always.** ``filter(tenant=request.tenant)``, never ``.objects.all()``. The
  tenantless superuser therefore sees empty boards BY DESIGN, and every verb 404s on another
  workspace's row.
* **Junk in, ignored out (L11).** ``?q=``, ``?status=``, ``?channel=``, ``?risk=`` and
  ``?fiscal_period=`` are each validated before use — a choice filter ignores anything outside its
  own ``CHOICES`` and the FK filter goes through ``as_db_int``, so ``?status=nonsense`` and
  ``?fiscal_period=abc`` narrow nothing rather than raising on a URL anybody can type.
* **No GET may mutate.** All three verbs are ``@require_POST`` + CSRF, and every board view is
  ``@login_required`` + ``@tenant_admin_required``. Audit on every mutation, with
  ``write_audit_log`` called POSITIONALLY — ``(user, obj, action, changes, tenant)``.

**The timeline creates NO timeline table.** A sixth append-only log summarising five existing ones
is a log that can disagree with all five, so ``order_timeline`` assembles its ``events`` list in the
view from the order's own status and notification stamps, the allocation timestamps, every
``TrackingEvent``, the invoice's issue date, and 8.6's own holds and amendments. Every event dict
is ``{"at", "kind", "label", "detail"}``, every ``label`` names the module that owns the record it
came from (an SCM fact must never read as a Sales fact), every ``at`` is non-``None`` — a null key
sorts last and silently breaks the ordering on MariaDB — and the list is newest first.

**The reorder board has NO basket model.** Cadence and lifetime value are derived in PYTHON over a
fetched set — never with an ``F()`` expression or a database-side division, which is the SQLite
integer-division trap SCM 4.5 names in ``recalc_totals()`` and that silently drops fractional cents
instead of raising.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.models.OrderManagement.OrderAmendments import OrderAmendment
from apps.sales.models.OrderManagement.OrderHolds import OrderHold
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule
from apps.sales.models.OrderManagement.RevenueSchedules import RevenueSchedule
from apps.sales.views._common import *  # noqa: F401,F403  (login_required, get_object_or_404, ...)


CAPTURE_TEMPLATE = "sales/ordermanagement/boards/capture.html"
FULFILLMENT_TEMPLATE = "sales/ordermanagement/boards/fulfillment.html"
HISTORY_TEMPLATE = "sales/ordermanagement/boards/history.html"
TIMELINE_TEMPLATE = "sales/ordermanagement/boards/timeline.html"
REORDER_TEMPLATE = "sales/ordermanagement/boards/reorder.html"
RENEWALS_TEMPLATE = "sales/ordermanagement/boards/renewals.html"
RECOGNITION_TEMPLATE = "sales/ordermanagement/boards/recognition.html"
VALIDATION_TEMPLATE = "sales/ordermanagement/boards/validation.html"

#: Rows per page. Matches the shared pagination partial's expectation of ``page_obj``.
PAGE_SIZE = 15

#: Summed in PYTHON, so every money accumulator needs a real Decimal zero to add into.
ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
TWO_PLACES = Decimal("0.01")

#: How far ahead a live promise still counts as "at risk" rather than "on track". Mirrors
#: procurement 6.11's ``Backorder.AT_RISK_DAYS`` so the two boards' vocabularies read the same way.
AT_RISK_DAYS = 7

#: How wide the reorder board's "worth calling now" window is.
REORDER_DUE_SOON_DAYS = 30

#: The three resolutions ``order_backorder_resolve`` accepts. Data, not a chain of ``if``s in the
#: raise path, and the same tuple the template renders its buttons from.
BACKORDER_RESOLUTIONS = [
    ("release", "Release to floor"),
    ("cancel", "Cancel shortfall"),
    ("keep", "Keep promising"),
]


def _sales_order_model():
    """``scm.SalesOrder``, imported INSIDE the function.

    8.6 declares no second order master and never imports SCM's model at module scope — the
    validation-rule set's docstring makes that a rule and the four entity views here all follow it
    with a function-local import. A module-scope import would also drag ``apps.scm`` into every
    import of this file, seeder included.
    """
    from apps.scm.models import SalesOrder

    return SalesOrder


def _capture_statuses():
    """The capture queue's statuses: 4.5's own allocatable set plus the held state.

    Read from 4.5's tuple rather than re-typed, so a change to ``ALLOCATABLE_STATUSES`` cannot
    leave this board describing a workflow 4.5 has moved on from. **Drafts are deliberately not
    here**: a draft is 4.5's own editable register, and this board is the queue of orders that
    have been submitted and are waiting on 8.6.
    """
    return tuple(_sales_order_model().ALLOCATABLE_STATUSES) + ("on_hold",)


def _order_queryset(request):
    """The tenant-scoped order register every order board projects over. One place."""
    return (
        _sales_order_model().objects.filter(tenant=request.tenant)
        .select_related("customer", "currency")
    )


def _tenant_orders(request):
    """The order dropdown for the resolve/validate forms. Read-only over SCM 4.5's table."""
    return _order_queryset(request).order_by("-order_date", "-id")


def _open_hold_counts(request, order_ids):
    """``{order_id: n}`` for orders carrying at least one OPEN 8.6 hold.

    One grouped query for the whole page rather than a per-order ``count()``. The count is a
    derived figure — it reads 8.6's hold register, which is the whole point of a board — and it
    is deliberately NOT 4.5's ``credit_hold`` boolean, which cannot say how many reasons there
    are or which rule fired.
    """
    if not order_ids:
        return {}
    return dict(
        OrderHold.objects.filter(
            tenant=request.tenant,
            sales_order_id__in=order_ids,
            status=OrderHold.OPEN_STATUS,
        )
        .values("sales_order_id")
        .annotate(n=Count("id"))
        .values_list("sales_order_id", "n")
    )


def _hold_reasons(request, order_ids):
    """``{order_id: [reason, …]}`` — why a live order is held, in 8.6's own words.

    The count alone is not actionable: a fulfilment clerk needs the sentence, not "3". Built from
    the same open holds as the count, so the two can never disagree about which orders are held.
    """
    if not order_ids:
        return {}
    reasons = {}
    rows = (
        OrderHold.objects.filter(
            tenant=request.tenant,
            sales_order_id__in=order_ids,
            status=OrderHold.OPEN_STATUS,
        )
        .order_by("raised_at", "id")
        .values_list("sales_order_id", "reason")
    )
    for order_id, reason in rows:
        reasons.setdefault(order_id, []).append(reason)
    return reasons


def _backordered_by_order(request, order_ids):
    """``{order_id: Decimal}`` — the DERIVED backordered quantity per order.

    Computed in PYTHON over ONE grouped query, the same shape 4.5's
    ``recompute_allocation_status()`` uses and for the same reason: the obvious version — looping
    ``line.quantity_backordered()`` — costs an aggregate per line AND derives the same figure
    twice, because ``quantity_backordered()`` calls ``quantity_allocated()`` itself. A board runs
    on every page view, so that cost is not hypothetical.

    The arithmetic is a subtraction and a floor, done in Python, never in the database: this is
    4.5's derived quantity and 8.6 is SHOWING it, not redefining it. 8.6 declares no backorder
    table — a second source of truth for a shortfall is exactly the failure §0.6 rules out.
    """
    from apps.scm.models import SalesOrderLine

    if not order_ids:
        return {}
    rows = (
        SalesOrderLine.objects.filter(sales_order_id__in=order_ids)
        .annotate(
            _allocated=Sum("allocations__quantity", filter=~Q(allocations__status="cancelled"))
        )
        .values_list("sales_order_id", "quantity_ordered", "_allocated")
    )
    totals = {}
    for order_id, ordered, allocated in rows:
        remaining = (ordered or ZERO) - (allocated or ZERO)
        if remaining > ZERO:
            totals[order_id] = totals.get(order_id, ZERO) + remaining
    return totals


def _risk_conditions(today, live_statuses):
    """The four fulfilment risk buckets as ORM ``Q()`` objects — ONE definition, used by the
    ``?risk=`` filter AND by the stat cards, so a card can never disagree with the list it links to.

    Written the way procurement 6.11's ``_risk_conditions()`` writes its four, over the two order
    dates 4.5 actually keeps: ``promised_date`` (stamped once, when the order first became fully
    allocated) and, before that, ``requested_date`` (what the customer actually asked for). An
    order with neither has made no commitment at all, which is its own bucket rather than a silent
    exclusion — "no commitment" is the finding, not a missing filter.
    """
    horizon = today + timedelta(days=AT_RISK_DAYS)
    live = Q(status__in=live_statuses)
    no_promise = Q(promised_date__isnull=True)
    return {
        "past_due": live & (
            Q(promised_date__lt=today) | (no_promise & Q(requested_date__lt=today))
        ),
        "at_risk": live & (
            Q(promised_date__gte=today, promised_date__lte=horizon)
            | (no_promise & Q(requested_date__gte=today, requested_date__lte=horizon))
        ),
        "no_commitment": live & no_promise & Q(requested_date__isnull=True),
        "on_track": live & (
            Q(promised_date__gt=horizon) | (no_promise & Q(requested_date__gt=horizon))
        ),
    }


def _risk_bucket_for(order, today):
    """The same four buckets evaluated in PYTHON for ONE order, for the row badge.

    A per-row badge cannot be a ``Q()`` — it is one object, not a queryset — so it mirrors
    ``_risk_conditions()`` clause for clause. That is exactly the arrangement procurement 6.11
    uses between ``Backorder.risk_bucket`` and the view's ``_risk_conditions()``: one definition
    per side, written out so they can be compared, never three hand-inlined copies.
    """
    horizon = today + timedelta(days=AT_RISK_DAYS)
    commitment = order.promised_date or order.requested_date
    if commitment is None:
        return "no_commitment"
    if commitment < today:
        return "past_due"
    if commitment <= horizon:
        return "at_risk"
    return "on_track"


def _order_filter_echo(request):
    """The two order-board filters both share, validated, as ``{"q", "status", "channel"}``.

    Every value is checked against its own vocabulary before it is used, so ``?status=nonsense``
    and ``?channel=telepathy`` narrow nothing rather than raising on a URL anybody can type into
    the address bar (L11). The validated value is echoed back so the widget can show what is
    actually applied instead of what was typed.
    """
    model = _sales_order_model()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if status not in dict(model.STATUS_CHOICES):
        status = ""
    channel = request.GET.get("channel", "").strip()
    if channel not in dict(model.SOURCE_CHANNEL_CHOICES):
        channel = ""
    return {"q": q, "status": status, "channel": channel}


def _apply_order_filters(queryset, filters):
    """``?q=`` / ``?status=`` / ``?channel=`` applied to an order queryset. Junk narrows nothing."""
    q, status, channel = filters["q"], filters["status"], filters["channel"]
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(notes__icontains=q)
        )
    if status:
        queryset = queryset.filter(status=status)
    if channel:
        queryset = queryset.filter(source_channel=channel)
    return queryset


def _page_ids(page_obj):
    """The pks on the current page, as a list — the input to every per-page map below."""
    return [order.pk for order in page_obj.object_list]


@login_required
@tenant_admin_required
def order_capture_board(request):
    """The capture queue: submitted orders waiting on validation, allocation or a hold.

    The board answers "what has come in and what is stopping it", so it mixes three reads that
    live in three tables: 4.5's ``status`` and ``source_channel``, 8.6's own open holds, and 4.5's
    line mapping. The unmapped count is the one that needs saying out loud — 4.5's
    ``salesorder_submit`` refuses to submit an order carrying an unmapped line, so an order in this
    queue with one has a known, already-priced problem.
    """
    base_queryset = _order_queryset(request).filter(status__in=_capture_statuses())
    filters = _order_filter_echo(request)
    queryset = _apply_order_filters(base_queryset, filters)
    page_obj = paginate(request, queryset, PAGE_SIZE)

    page_ids = _page_ids(page_obj)
    open_hold_counts = _open_hold_counts(request, page_ids)
    unmapped_ids = _unmapped_order_ids(page_ids)

    # Per-row derived values, attached to the row object. A template CANNOT look a dict up by a
    # variable key without a custom filter, and adding a filter to read one dictionary would be a
    # worse answer than carrying the value on the row — which is also how the stat cards and the
    # badge are guaranteed to read the SAME number rather than two derivations of it.
    for order in page_obj.object_list:
        order.open_hold_count = open_hold_counts.get(order.pk, 0)
        order.has_unmapped_line = order.pk in unmapped_ids

    # The stats describe the WHOLE capture queue, not the filtered page — a stats strip that
    # changes when you search is a stats strip nobody trusts. Every figure is walked in PYTHON:
    # ``by_channel`` is a per-value count and ``unmapped`` reads each order's own lines, so
    # neither is an aggregate this file could delegate to the database.
    today = timezone.localdate()
    all_orders = list(base_queryset)
    all_ids = [order.pk for order in all_orders]
    queue_hold_counts = _open_hold_counts(request, all_ids)
    queue_unmapped = _unmapped_order_ids(all_ids)
    by_channel = {value: 0 for value, _label in _sales_order_model().SOURCE_CHANNEL_CHOICES}
    for order in all_orders:
        if order.source_channel in by_channel:
            by_channel[order.source_channel] += 1
    stats = {
        "total": len(all_orders),
        "on_hold": sum(
            1 for order in all_orders if order.status == "on_hold" or order.pk in queue_hold_counts
        ),
        "unmapped": sum(1 for pk in queue_unmapped),
        "by_channel": by_channel,
        "as_of": today,
    }

    return render(request, CAPTURE_TEMPLATE, {
        "orders": page_obj,
        # The shared pagination partial reads ``page_obj``; an ALIAS of the very same Page,
        # never a second paginator run over the same queryset.
        "page_obj": page_obj,
        "q": filters["q"],
        "status": filters["status"],
        "channel": filters["channel"],
        "channel_choices": _sales_order_model().SOURCE_CHANNEL_CHOICES,
        "status_choices": _sales_order_model().STATUS_CHOICES,
        "open_hold_counts": open_hold_counts,
        "unmapped_ids": unmapped_ids,
        "stats": stats,
    })


def _unmapped_order_ids(order_ids):
    """``{order_id}`` — orders carrying at least one line with no mapped stock item.

    One ``values_list``, not a per-order ``any(line.is_unmapped …)`` loop: the loop is an N+1 on
    every board page view, and the derived answer is identical.
    """
    from apps.scm.models import SalesOrderLine

    if not order_ids:
        return set()
    return set(
        SalesOrderLine.objects.filter(sales_order_id__in=order_ids, item__isnull=True)
        .values_list("sales_order_id", flat=True)
        .distinct()
    )


@login_required
@tenant_admin_required
def order_fulfillment_board(request):
    """The fulfilment board: live orders, how much of each is still short, and what is holding it.

    This is the one board that has to answer a question in the customer's voice — "where is my
    order" — from four different modules' facts, so it shows all four: 4.5's derived backordered
    quantity, 4.5's own ``promised_date``, 8.6's open holds with their reasons, and 4.6's shipments
    (the POD column is a 4.6 fact read, never written here).

    The risk buckets are the four from ``_risk_conditions()``, expressed as ORM date arithmetic and
    applied BEFORE pagination so the page count and the stat cards agree. A held order is
    deliberately on this board rather than filtered off it: "nothing is happening to my order" is
    the single most expensive thing a fulfilment board can fail to show, so the blocked-by-hold
    reason is rendered in the row itself.
    """
    model = _sales_order_model()
    live_statuses = tuple(model.ALLOCATABLE_STATUSES) + ("on_hold",)
    base_queryset = _order_queryset(request).filter(status__in=live_statuses)
    filters = _order_filter_echo(request)
    today = timezone.localdate()
    conditions = _risk_conditions(today, live_statuses)

    queryset = _apply_order_filters(base_queryset, filters)
    risk = request.GET.get("risk", "").strip()
    if risk in conditions:
        queryset = queryset.filter(conditions[risk])
    else:
        risk = ""

    page_obj = paginate(request, queryset, PAGE_SIZE)
    page_ids = _page_ids(page_obj)

    hold_counts = _open_hold_counts(request, page_ids)
    hold_reasons = _hold_reasons(request, page_ids)
    backordered = _backordered_by_order(request, page_ids)
    shipments_by_order = _shipments_by_order(page_ids)

    # Every count is a plain integer over the WHOLE live board, not the filtered page, and every
    # one that has to read an order's own lines or shipments is walked in PYTHON.
    all_orders = list(base_queryset)
    all_ids = [order.pk for order in all_orders]
    queue_backordered = _backordered_by_order(request, all_ids)
    queue_hold_counts = _open_hold_counts(request, all_ids)
    queue_shipments = _shipments_by_order(all_ids)
    stats = {
        "total": len(all_orders),
        "backordered": len(queue_backordered),
        "past_due": sum(1 for order in all_orders if _risk_bucket_for(order, today) == "past_due"),
        "awaiting_pod": sum(
            1
            for order in all_orders
            if any(
                shipment.status == "delivered" and not shipment.pod_received
                for shipment in queue_shipments.get(order.pk, [])
            )
        ),
        "on_hold": sum(1 for pk in all_ids if pk in queue_hold_counts),
        "as_of": today,
    }

    # Per-row derived values, attached to the row object so the template never has to re-derive
    # them (and cannot get a different answer than the stat cards).
    for order in page_obj.object_list:
        order.risk_bucket = _risk_bucket_for(order, today)
        order.backordered_qty = backordered.get(order.pk, ZERO)
        order.open_hold_count = hold_counts.get(order.pk, 0)
        order.blocking_reasons = hold_reasons.get(order.pk, [])
        order.board_shipments = shipments_by_order.get(order.pk, [])

    return render(request, FULFILLMENT_TEMPLATE, {
        "orders": page_obj,
        "page_obj": page_obj,
        "q": filters["q"],
        "status": filters["status"],
        "channel": filters["channel"],
        "risk": risk,
        "risk_choices": [
            ("", "All"),
            ("no_commitment", "No Commitment"),
            ("at_risk", "At Risk"),
            ("past_due", "Past Due"),
            ("on_track", "On Track"),
        ],
        "resolution_choices": BACKORDER_RESOLUTIONS,
        "channel_choices": model.SOURCE_CHANNEL_CHOICES,
        "status_choices": model.STATUS_CHOICES,
        "hold_counts": hold_counts,
        "hold_reasons": hold_reasons,
        "stats": stats,
    })


def _shipments_by_order(order_ids):
    """``{order_id: [Shipment, …]}`` — 4.6's outbound shipments, read for the POD column.

    Scoped to the order's OWN shipments, never reached through a load or a consignment: a
    consolidated load legitimately carries another customer's order, and showing its tracking
    against this order would be a cross-customer leak on a read-only board.
    """
    from apps.scm.models import Shipment

    if not order_ids:
        return {}
    grouped = {}
    rows = (
        Shipment.objects.filter(sales_order_id__in=order_ids, direction="outbound")
        .order_by("id")
        .select_related("carrier")
    )
    for shipment in rows:
        grouped.setdefault(shipment.sales_order_id, []).append(shipment)
    return grouped


@login_required
@tenant_admin_required
def order_history_board(request):
    """Every order this workspace has ever taken, newest first — the "what did we order" register.

    Deliberately the widest of the boards: it filters on nothing but the tenant, because a history
    that hid cancelled orders would be a history that lied. That is also why ``stats`` splits the
    register four ways rather than two — "closed" and "cancelled" are different commercial facts
    and collapsing them into one "done" number is how a cancellation rate becomes unknowable.
    """
    model = _sales_order_model()
    base_queryset = _order_queryset(request)
    filters = _order_filter_echo(request)
    queryset = _apply_order_filters(base_queryset, filters)
    page_obj = paginate(request, queryset, PAGE_SIZE)

    open_statuses = tuple(
        value for value, _label in model.STATUS_CHOICES if value not in model.CLOSED_STATUSES
    )
    # Four plain integer counts over the whole register, one grouped query. No money is involved,
    # so this is the safe kind of aggregate — the SQLite decimal trap only bites arithmetic.
    stats = base_queryset.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=open_statuses)),
        closed=Count("id", filter=Q(status="closed")),
        cancelled=Count("id", filter=Q(status="cancelled")),
    )
    stats["as_of"] = timezone.localdate()

    page_ids = _page_ids(page_obj)
    history_shipments = _shipments_by_order(page_ids)
    history_hold_counts = _open_hold_counts(request, page_ids)
    for order in page_obj.object_list:
        order.board_shipments = history_shipments.get(order.pk, [])
        order.open_hold_count = history_hold_counts.get(order.pk, 0)

    return render(request, HISTORY_TEMPLATE, {
        "orders": page_obj,
        "page_obj": page_obj,
        "q": filters["q"],
        "status": filters["status"],
        "channel": filters["channel"],
        "status_choices": model.STATUS_CHOICES,
        "channel_choices": model.SOURCE_CHANNEL_CHOICES,
        "stats": stats,
    })


@login_required
@tenant_admin_required
def order_timeline(request, pk):
    """One order's whole story, assembled here from five sources. **No timeline table exists.**

    This is the page that decides the question, so the refusal is stated plainly: 8.6 creates NO
    ``OrderEvent`` / ``OrderTimeline`` model. A sixth append-only log summarising five existing ones
    is a log that can disagree with every one of them — and the moment somebody edits an order in
    SCM directly, the timeline table is the one copy nobody looks at. Instead the ``events`` list is
    built on every read from the records that are already the truth:

    * 4.5's own order row — its status and the three notification timestamps;
    * 4.5's allocations, by their ``allocated_at``;
    * 4.6's append-only ``TrackingEvent`` ledger;
    * Accounting 2.4's invoice, by its ``issue_date``;
    * 8.6's own holds and amendments, by their raise / decide / apply stamps.

    Every event dict is ``{"at", "kind", "label", "detail"}`` and every ``label`` NAMES THE MODULE
    the fact came from ("SCM 4.5 · …", "Sales 8.6 · …", "Accounting 2.4 · …"). That is not
    decoration: a reader who cannot tell an SCM fact from a Sales fact will read 8.6's own view of
    an order as a fact about the order, and the two disagree whenever SCM is edited directly.

    Every event carries a NON-NULL ``at``, and the list is sorted newest first. A null sort key is
    the C5 MariaDB trap — it does not raise, it sorts last, and the ordering quietly stops meaning
    anything, so any event that cannot be dated is DROPPED rather than shown undated.
    """
    model = _sales_order_model()
    order = get_object_or_404(
        model.objects.filter(tenant=request.tenant).select_related("customer", "invoice"), pk=pk
    )

    holds = list(
        OrderHold.objects.filter(tenant=request.tenant, sales_order_id=order.pk)
        .select_related("rule", "raised_by", "cleared_by")
        .order_by("-raised_at", "-id")
    )
    amendments = list(
        OrderAmendment.objects.filter(tenant=request.tenant, sales_order_id=order.pk)
        .select_related("requested_by", "decided_by", "applied_by")
        .order_by("-requested_at", "-id")
    )
    shipments = list(
        _shipments_by_order([order.pk]).get(order.pk, [])
    )
    tracking_events = _tracking_events_for(shipments)
    invoice = order.invoice

    events = []
    events += _order_status_events(order)
    events += _allocation_events(order)
    events += _tracking_events_as_events(tracking_events)
    events += _invoice_events(invoice)
    events += _hold_events(holds)
    events += _amendment_events(amendments)

    dated = [event for event in events if event.get("at") is not None]
    dated.sort(key=lambda event: event["at"], reverse=True)

    return render(request, TIMELINE_TEMPLATE, {
        "order": order,
        "events": dated,
        "holds": holds,
        "amendments": amendments,
        "shipments": shipments,
        "tracking_events": tracking_events,
        "invoice": invoice,
        "dropped_events": len(events) - len(dated),
    })


def _tracking_events_for(shipments):
    """4.6's append-only tracking ledger for these shipments, newest first. Read-only."""
    from apps.scm.models import TrackingEvent

    shipment_ids = [shipment.pk for shipment in shipments]
    if not shipment_ids:
        return []
    return list(
        TrackingEvent.objects.filter(shipment_id__in=shipment_ids)
        .select_related("shipment")
        .order_by("-event_at", "-id")
    )


#: Every event ``kind`` is one of these. They are the badge vocabulary AND the source-of-truth
#: label: a reader must never have to guess whether a line came from SCM, from Accounting or from
#: Sales, because 8.6's view of an order is a *reading* of somebody else's record, and the two
#: disagree the moment SCM is edited directly.
TIMELINE_SOURCES = {
    "order": "SCM 4.5",
    "allocation": "SCM 4.5",
    "tracking": "SCM 4.6",
    "invoice": "Accounting 2.4",
    "hold": "Sales 8.6",
    "amendment": "Sales 8.6",
}


def _event(at, kind, label, detail):
    """One timeline event. ``at`` may be ``None`` — the caller DROPS undated events."""
    source = TIMELINE_SOURCES.get(kind, "NavERP")
    return {
        "at": at,
        "kind": kind,
        "source": source,
        "label": f"{source} · {label}",
        "detail": detail,
    }


def _order_status_events(order):
    """4.5's own facts: the order's creation, its CURRENT status, and its three notification stamps.

    The status is emitted as ONE event dated at the order's creation and labelled as the *current*
    status — because 4.5 records no per-transition timestamps. Dating it "now" would put a status
    the order has carried for months at the top of a newest-first list; dating it at a transition
    would be inventing a fact 4.5 never wrote. Both are lies, so the honest form is one clearly
    labelled present-tense line that says which of the two it is.
    """
    events = [
        _event(
            order.created_at,
            "order",
            f"Order {order.number} captured",
            f"{order.get_status_display()} · via {order.get_source_channel_display()} · "
            f"channel total {order.total}",
        ),
        _event(
            order.created_at,
            "order",
            f"Order {order.number} is currently {order.get_status_display().lower()}",
            "4.5 records the order's current status only — it keeps no per-transition timestamp, so "
            "this line is dated at the order's creation and is a reading, not a transition.",
        ),
    ]
    for label, stamp in (
        ("Confirmation notification", order.confirmation_sent_at),
        ("Shipment notification", order.shipped_notification_at),
        ("Delivery notification", order.delivered_notification_at),
    ):
        if stamp is not None:
            events.append(
                _event(stamp, "order", label, "4.5 records when this notification was sent.")
            )
    return events


def _allocation_events(order):
    """4.5's soft reservations, by ``allocated_at`` — the moment stock was spoken for."""
    from apps.scm.models import SalesOrderAllocation

    allocations = (
        SalesOrderAllocation.objects.filter(sales_order_line__sales_order_id=order.pk)
        .select_related("sales_order_line", "location")
        .order_by("-allocated_at", "-id")
    )
    return [
        _event(
            allocation.allocated_at,
            "allocation",
            f"{allocation.get_status_display()} {allocation.quantity} at "
            f"{allocation.location.code if allocation.location_id else '?'}",
            f"Line {allocation.sales_order_line_id} · a soft reservation, not a stock movement.",
        )
        for allocation in allocations
    ]


def _tracking_events_as_events(tracking_events):
    """4.6's append-only tracking ledger, one event per milestone."""
    return [
        _event(
            event.event_at,
            "tracking",
            event.get_event_type_display(),
            f"{event.shipment.number if event.shipment_id else 'shipment'} · "
            f"{event.location_text or 'no location recorded'} · via {event.get_source_display()}",
        )
        for event in tracking_events
    ]


def _invoice_events(invoice):
    """Accounting 2.4's invoice, dated by its ``issue_date``.

    ``issue_date`` is a ``Date``, not a datetime, so it is lifted to midnight in the default
    timezone before it can share a sort key with the rest of the list. Comparing a ``date`` to a
    ``datetime`` raises, and the fix is a real conversion — a ``date`` has no tzinfo to keep, so
    ``make_aware`` is right and ``astimezone`` would be a lie.
    """
    if invoice is None or invoice.issue_date is None:
        return []
    issued_at = timezone.make_aware(
        datetime.combine(invoice.issue_date, time.min), timezone.get_default_timezone()
    )
    return [
        _event(
            issued_at,
            "invoice",
            f"Invoice {invoice.number or invoice.pk} issued",
            f"{invoice.get_status_display()} · total {invoice.total}",
        )
    ]


def _hold_events(holds):
    """8.6's own holds, by ``raised_at`` and — where it happened — ``cleared_at``."""
    events = []
    for hold in holds:
        events.append(
            _event(
                hold.raised_at,
                "hold",
                f"Hold {hold.number} raised ({hold.get_hold_type_display().lower()})",
                f"{hold.reason} · severity {hold.get_severity_display().lower()}"
                + (f" · by {hold.raised_by}" if hold.raised_by_id else " · by the system"),
            )
        )
        if hold.cleared_at is not None:
            events.append(
                _event(
                    hold.cleared_at,
                    "hold",
                    f"Hold {hold.number} cleared",
                    f"{hold.clear_note or 'No note recorded.'}"
                    + (f" · by {hold.cleared_by}" if hold.cleared_by_id else ""),
                )
            )
    return events


def _amendment_events(amendments):
    """8.6's own change orders, by ``requested_at``, ``decided_at`` and ``applied_at``."""
    events = []
    for amendment in amendments:
        events.append(
            _event(
                amendment.requested_at,
                "amendment",
                f"Amendment {amendment.number} proposed "
                f"({amendment.get_change_type_display().lower()})",
                amendment.reason
                + (f" · by {amendment.requested_by}" if amendment.requested_by_id else ""),
            )
        )
        if amendment.decided_at is not None:
            events.append(
                _event(
                    amendment.decided_at,
                    "amendment",
                    f"Amendment {amendment.number} "
                    f"{amendment.get_status_display().lower()}",
                    amendment.decision_note
                    + (f" · by {amendment.decided_by}" if amendment.decided_by_id else ""),
                )
            )
        if amendment.applied_at is not None:
            events.append(
                _event(
                    amendment.applied_at,
                    "amendment",
                    f"Amendment {amendment.number} applied to the order",
                    "8.6 wrote the line quantities and prices; 4.5 recomputed the totals and the "
                    "allocation status."
                    + (f" · by {amendment.applied_by}" if amendment.applied_by_id else ""),
                )
            )
    return events


#: An order counts toward a customer's buying history unless it is cancelled. A cancelled order is
#: a commercial fact about the relationship, but it is not a PURCHASE, and averaging it into a
#: cadence would tell the caller to ring a customer whose last real order was much older than the
#: maths says.
REORDER_COUNTED_STATUSES_EXCLUDED = ("cancelled",)


@login_required
@tenant_admin_required
def reorder_customers_board(request):
    """Who is due to buy again, derived from their own order history. **No basket model exists.**

    8.6 builds NO basket, NO reorder-point table and NO campaign entity — a stored "next order due"
    is a column that is stale the moment an order is cancelled in SCM, and §2.5 rules that out. So
    every figure here is derived in PYTHON on read, over the tenant's real order history:

    * ``lifetime_value``    — Σ ``SalesOrder.total`` over the customer's counted orders.
    * ``avg_days_between``  — the mean gap between consecutive ``order_date`` values.
    * ``expected_order_on`` — ``last_order_on + avg_days_between``. The cadence IS the projection.
    * ``on_time_pct``       — of the orders that reached a delivery fact, the share delivered on or
      before the date 4.5 promised.

    A customer with ONE order has no cadence and therefore no expected date. They are still on the
    board with a real lifetime value and a real order count — "we have sold to them once and never
    again" is a finding — but ``expected_order_on`` is ``None`` rather than a fabricated 30 days.
    Inventing a cadence from a single observation is the exact error a stored ``days_open`` counter
    makes, and it is why this board derives instead of remembering.

    Rows sort by how overdue the expectation is, so the caller works the top of the list first;
    undated customers sort last because there is nothing to be early for.
    """
    model = _sales_order_model()
    today = timezone.localdate()
    counted = model.objects.exclude(status__in=REORDER_COUNTED_STATUSES_EXCLUDED)

    q = request.GET.get("q", "").strip()
    if q:
        counted = counted.filter(Q(customer__name__icontains=q) | Q(number__icontains=q))

    # ONE query for the whole history, then grouped in Python. The per-customer figures are means,
    # sums and differences over Decimals and dates — none has a portable database-side spelling,
    # and all are wrong on SQLite if attempted there.
    orders = list(
        counted.filter(tenant=request.tenant)
        .select_related("customer")
        .order_by("customer_id", "order_date", "id")
    )
    deliveries = _delivery_dates_by_order(orders)
    customers = _reorder_rows(orders, deliveries, today)

    page_obj = paginate(request, customers, PAGE_SIZE)
    lifetime_total = ZERO
    for row in customers:
        lifetime_total += row["lifetime_value"]

    return render(request, REORDER_TEMPLATE, {
        "customers": page_obj,
        "page_obj": page_obj,
        "q": q,
        "lifetime_total": lifetime_total,
        "due_soon_days": REORDER_DUE_SOON_DAYS,
        "stats": {
            "customers": len(customers),
            "reorderable": sum(1 for row in customers if row["due_state"] in ("due", "lapsed")),
            "lapsed": sum(1 for row in customers if row["due_state"] == "lapsed"),
            "as_of": today,
        },
    })


def _delivery_dates_by_order(orders):
    """``{order_id: date}`` — the first actual delivery 4.6 recorded for each order.

    Read from ``Shipment.actual_delivery_at``, which 4.6 stamps from its own tracking ledger and
    never from a form. The EARLIEST delivery is the one the customer experienced, so a split
    shipment that arrived in two parts counts on the first part.
    """
    from apps.scm.models import Shipment

    order_ids = [order.pk for order in orders]
    if not order_ids:
        return {}
    delivered = {}
    rows = (
        Shipment.objects.filter(
            sales_order_id__in=order_ids, actual_delivery_at__isnull=False
        )
        .order_by("actual_delivery_at", "id")
        .values_list("sales_order_id", "actual_delivery_at")
    )
    for order_id, stamp in rows:
        delivered.setdefault(order_id, stamp.date())
    return delivered


def _average_gap_days(dates):
    """The mean gap between consecutive order dates, in whole days, or ``None`` for < 2 orders.

    A ``Decimal`` of days is meaningless to a caller ("31.5 days between orders" is not a
    commitment), so this truncates to whole days and says so on the page. ``None`` — not zero —
    when there is nothing to average: zero would read as "they order every day".
    """
    usable = sorted({day for day in dates if day is not None})
    if len(usable) < 2:
        return None
    total_days = (usable[-1] - usable[0]).days
    return total_days // (len(usable) - 1)


def _on_time_percentage(customer_orders, deliveries):
    """``Decimal`` percent delivered on time, or ``None`` when nothing has been delivered yet.

    Measured against 4.5's own ``promised_date`` where it exists and its ``requested_date``
    otherwise — the date the customer was actually given, not the date the warehouse hoped for.
    Only orders that reached a real delivery fact count; an order still in transit is not late yet
    and an order never shipped is not a delivery failure, it is a different problem.
    """
    on_time = measured = 0
    for order in customer_orders:
        delivered_on = deliveries.get(order.pk)
        if delivered_on is None:
            continue
        commitment = order.promised_date or order.requested_date
        if commitment is None:
            continue
        measured += 1
        if delivered_on <= commitment:
            on_time += 1
    if not measured:
        return None
    return (
        Decimal(on_time) * ONE_HUNDRED / Decimal(measured)
    ).quantize(TWO_PLACES, rounding="ROUND_HALF_UP")


def _top_items(customer_orders, limit=3):
    """The customer's most-bought item descriptions, as a comma-joined STRING.

    A string, not a list of dicts, because the cell that shows it is one cell — and a list in a
    cell renders as ``['a', 'b']`` unless the template loops it, which is markup this board has no
    room for. ``item_id`` is preferred over the free-text ``description`` so two spellings of the
    same SKU do not read as two different products.
    """
    from apps.scm.models import SalesOrderLine

    order_ids = [order.pk for order in customer_orders]
    if not order_ids:
        return ""
    counts = {}
    rows = (
        SalesOrderLine.objects.filter(sales_order_id__in=order_ids, item__isnull=False)
        .values_list("sales_order_line__sales_order_id", "item__sku", "quantity_ordered")
    )
    for _order_id, sku, quantity in rows:
        key = sku or "unnamed"
        counts[key] = counts.get(key, ZERO) + (quantity or ZERO)
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return ", ".join(f"{sku} &times;{quantity.normalize()}" for sku, quantity in ranked[:limit])


def _due_state(expected_on, today):
    """``"lapsed"`` / ``"due"`` / ``"soon"`` / ``"undated"`` — one derivation, three consumers.

    The row badge and both stat cards read this, so a card can never say a customer is due while
    their row says otherwise. A customer with no cadence is ``undated``: absent from both cards,
    because "we do not know when they will buy again" is not a number.
    """
    if expected_on is None:
        return "undated"
    if expected_on < today:
        return "lapsed"
    if expected_on <= today + timedelta(days=REORDER_DUE_SOON_DAYS):
        return "due"
    return "soon"


def _reorder_rows(orders, deliveries, today):
    """One dict per customer, sorted most-overdue first. Every figure is PYTHON arithmetic.

    The dicts carry exactly the keys the template reads — ``party``, ``order_count``,
    ``lifetime_value``, ``avg_days_between``, ``last_order_on``, ``expected_order_on``,
    ``on_time_pct``, ``top_items`` — plus ``due_state``, so the row badge and the two stat cards
    are all read off ONE derivation rather than three.
    """
    grouped = {}
    for order in orders:
        grouped.setdefault(order.customer_id, []).append(order)

    rows = []
    for customer_orders in grouped.values():
        first = customer_orders[0]
        dates = [order.order_date for order in customer_orders if order.order_date is not None]
        lifetime = ZERO
        for order in customer_orders:
            lifetime += order.total or ZERO

        avg_gap = _average_gap_days(dates)
        last_on = max(dates) if dates else None
        # ``avg_gap`` of 0 (two orders on the same day) is a real cadence, not a missing one, so
        # the test is ``is not None`` — a truthiness test here would drop those customers silently.
        expected_on = (
            last_on + timedelta(days=avg_gap) if (last_on is not None and avg_gap is not None) else None
        )
        rows.append({
            "party": first.customer,
            "order_count": len(customer_orders),
            "lifetime_value": lifetime,
            "avg_days_between": avg_gap,
            "last_order_on": last_on,
            "expected_order_on": expected_on,
            "on_time_pct": _on_time_percentage(customer_orders, deliveries),
            "top_items": _top_items(customer_orders),
            "due_state": _due_state(expected_on, today),
        })

    # Most overdue first, then soonest due, then never-dated last. Undated rows sort on a real
    # date rather than on ``None``, which would raise against a date in the same tuple.
    rank = {"lapsed": 0, "due": 1, "soon": 2, "undated": 3}
    dated = datetime(9999, 12, 31).date()
    rows.sort(key=lambda row: (
        rank.get(row["due_state"], 4),
        row["expected_order_on"] or dated,
        -row["lifetime_value"],
    ))
    return rows


@login_required
@tenant_admin_required
def renewals_due_board(request):
    """Recurring billing coming due — a READ-ONLY watch over Accounting 2.4's own schedules.

    **8.6 builds NO renewal model and generates NO renewal orders.** That is Module 8.15's job, and
    the page says so in visible prose rather than leaving a reader to assume the button is missing
    by accident. What lives here is a lens: ``accounting.RecurringInvoice`` already owns the
    cadence, the status and the next run date, and this board only sorts them by how soon they
    fall due.

    Every figure is derived on read — ``days_until`` is a subtraction against today, which is
    exactly the kind of number that cannot be a column (a stored integer is correct when written
    and wrong the moment the clock ticks past midnight) and exactly what §2.5 rules out. The
    "overdue" bucket deliberately counts only ``active`` schedules: a paused schedule is not late,
    it is paused, and reporting it as overdue would train people to ignore the card.
    """
    from apps.accounting.models import RecurringInvoice

    base_queryset = (
        RecurringInvoice.objects.filter(tenant=request.tenant)
        .select_related("party", "currency")
    )
    q = request.GET.get("q", "").strip()
    queryset = base_queryset
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q) | Q(description__icontains=q) | Q(party__name__icontains=q)
        )
    status = request.GET.get("status", "").strip()
    if status in dict(RecurringInvoice.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""

    page_obj = paginate(request, queryset, PAGE_SIZE)
    today = timezone.localdate()

    for schedule in page_obj.object_list:
        schedule.days_until = _days_until(schedule.next_run_date, today)
        schedule.is_overdue_run = bool(
            schedule.status == "active"
            and schedule.next_run_date is not None
            and schedule.next_run_date < today
        )

    # Counts over the WHOLE tenant register, in one grouped query. The ``due_30d`` bucket is the
    # board's own horizon, so it is spelled out here rather than as a bare magic number in the
    # template — a card whose window nobody can name is a card nobody argues with.
    horizon = today + timedelta(days=REORDER_DUE_SOON_DAYS)
    stats = base_queryset.aggregate(
        due_30d=Count(
            "id",
            filter=Q(status="active", next_run_date__gte=today, next_run_date__lte=horizon),
        ),
        overdue=Count(
            "id",
            filter=Q(status="active", next_run_date__isnull=False, next_run_date__lt=today),
        ),
        active_templates=Count("id", filter=Q(status="active")),
    )
    stats["as_of"] = today
    stats["horizon"] = horizon

    return render(request, RENEWALS_TEMPLATE, {
        "recurring_invoices": page_obj,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "status_choices": RecurringInvoice.STATUS_CHOICES,
        "cadence_choices": RecurringInvoice.CADENCE_CHOICES,
        "stats": stats,
    })


def _days_until(target, today):
    """Whole days from ``today`` to ``target``; negative when the date has passed.

    ``None`` in, ``None`` out — a schedule with no next run date is unscheduled, and reporting
    "0 days" for it would put it at the top of an overdue list it does not belong on.
    """
    if target is None:
        return None
    return (target - today).days


@login_required
@tenant_admin_required
def revenue_recognition_board(request):
    """The ASC 606 / IFRS 15 position across every schedule, in one screen.

    This is the only board whose figures are MONEY, and every one of them is a ``@property`` on
    ``RevenueSchedule`` — ``contract_amount`` is 4.5's own order total read live, and the rest are
    sums and differences over the schedule's own obligations. That makes the stats strip Python
    work by definition, and it is why this view does **not** reach for ``aggregate("Sum")``: a
    contract value that reads back 12,345 instead of 12,345.67 because of a rounding that happened
    in the driver is worse than no register at all.

    The register's own verbs (open a schedule, add an obligation, recognise) are NOT duplicated
    here. This board is the portfolio view; the register one screen away owns the document. What
    the board adds is the cross-schedule total — the one number nobody can get from a paginated
    list of individual schedules.
    """
    base_queryset = (
        RevenueSchedule.objects.filter(tenant=request.tenant)
        .select_related("sales_order", "sales_order__customer", "fiscal_period")
    )
    q = request.GET.get("q", "").strip()
    queryset = base_queryset
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q) | Q(notes__icontains=q) | Q(sales_order__number__icontains=q)
        )
    method = request.GET.get("method", "").strip()
    if method in dict(RevenueSchedule.METHOD_CHOICES):
        queryset = queryset.filter(method=method)
    else:
        method = ""
    status = request.GET.get("status", "").strip()
    if status in dict(RevenueSchedule.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""
    # An FK filter goes through ``as_db_int``: ``?fiscal_period=abc`` and a 40-digit value are
    # skipped rather than handed to the driver, and 0 is skipped because it is not a pk — filtering
    # on it returns an empty page that reads as "this workspace has no schedules", which is a lie.
    period_filter = request.GET.get("fiscal_period", "").strip()
    period_pk = as_db_int(period_filter)
    if period_pk:
        queryset = queryset.filter(fiscal_period_id=period_pk)
    else:
        period_filter = ""

    page_obj = paginate(request, queryset, PAGE_SIZE)
    stats = _recognition_stats(list(base_queryset))

    return render(request, RECOGNITION_TEMPLATE, {
        "schedules": page_obj,
        "page_obj": page_obj,
        "q": q,
        "method": method,
        "status": status,
        "fiscal_period": period_filter,
        "method_choices": RevenueSchedule.METHOD_CHOICES,
        "status_choices": RevenueSchedule.STATUS_CHOICES,
        "compliance_standard_choices": RevenueSchedule.COMPLIANCE_STANDARD_CHOICES,
        "fiscal_periods": _tenant_fiscal_periods(request),
        "stats": stats,
    })


def _tenant_fiscal_periods(request):
    """The fiscal-period dropdown, tenant-narrowed and newest first."""
    from apps.accounting.models import FiscalPeriod

    return FiscalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")


def _recognition_stats(schedules):
    """The board's money strip — EVERY figure summed in PYTHON over the fetched schedules.

    ``schedules`` is a LIST, not a queryset: each schedule's ``contract_amount``,
    ``allocated_amount``, ``recognized_amount``, ``contract_asset`` and ``contract_liability`` are
    ``@property`` values that read its own order and its own obligations, so summing them is Python
    work by definition. There is no ``aggregate("Sum")`` that could do this correctly, and the one
    that would do it WRONG is the SQLite decimal / integer-division trap SCM 4.5 names in
    ``recalc_totals()``.

    A VOID schedule is excluded from the money and counted separately, because a voided schedule's
    balances are a document that was abandoned, not a position the company holds. Leaving it in
    would let a void inflate or deflate the reported contract value, which is the whole number the
    board exists to state.
    """
    total = active = overdue = voided = 0
    contract_value = recognized = deferred = contract_asset = contract_liability = ZERO
    for schedule in schedules:
        total += 1
        if schedule.status == "active":
            active += 1
        if schedule.is_overdue:
            overdue += 1
        if schedule.status == "void":
            voided += 1
            continue
        contract_value += schedule.contract_amount
        recognized += schedule.recognized_amount
        deferred += schedule.deferred_amount
        contract_asset += schedule.contract_asset
        contract_liability += schedule.contract_liability
    return {
        "total": total,
        "active": active,
        "overdue": overdue,
        "voided": voided,
        "contract_value": contract_value,
        "recognized": recognized,
        "deferred": deferred,
        "contract_asset": contract_asset,
        "contract_liability": contract_liability,
    }


@require_POST
@login_required
@tenant_admin_required
def order_backorder_resolve(request, allocation_pk):
    """Resolve one shortfall on an allocation. The one genuinely new verb in bullet 2.

    There is no backorder table in 8.6 (§0.6): the shortfall IS 4.5's derived
    ``SalesOrderLine.quantity_backordered()``, so the thing to act on is a 4.5 ALLOCATION and the
    thing to act with is 4.5's own release/cancel pair. ``release`` and ``cancel`` are therefore
    **delegated** to ``salesorderallocation_release`` / ``salesorderallocation_cancel`` — the same
    status write, the same ``recompute_allocation_status()`` call and the same audit verb, run by
    the code that owns them. Re-implementing either here would be the second allocation path
    §0.4 rules out, and the two would diverge the first time 4.5 changed its guard.

    ``promised_date`` is NEVER written. 8.6 does not rewrite a promise already given to a customer;
    that is what the ``keep`` resolution is FOR — the shortfall stands, the date stands, and the
    decision is recorded rather than papered over by moving a column.

    POST-only: a GET that released stock would let a prefetch, a crawler or a link preview release
    a customer's reservation by touching a URL.
    """
    from apps.scm.models import SalesOrderAllocation
    from apps.scm.views.OrderManagement.SalesOrderAllocations import (
        salesorderallocation_cancel,
        salesorderallocation_release,
    )

    allocation = get_object_or_404(
        SalesOrderAllocation.objects.filter(tenant=request.tenant).select_related(
            "sales_order_line__sales_order", "location"
        ),
        pk=allocation_pk,
    )
    resolution = (request.POST.get("resolution") or "").strip()
    if resolution not in dict(BACKORDER_RESOLUTIONS):
        messages.error(request, "Choose how to resolve this shortfall before submitting.")
        return redirect("sales:order_fulfillment_board")

    order = allocation.sales_order_line.sales_order
    if allocation.status == "cancelled":
        messages.info(
            request,
            f"That reservation is already cancelled — the shortfall stands until stock is "
            f"allocated against order {order.number}.",
        )
        return redirect("sales:order_fulfillment_board")

    if resolution == "keep":
        # The one resolution that changes nothing, and that is the POINT: the promise is left
        # exactly as given and the decision to keep it is written down. Audited, because a
        # decision not to act is still a decision somebody will be asked about later.
        write_audit_log(
            request.user,
            allocation,
            "update",
            {
                "action": "keep_backorder",
                "resolution": resolution,
                "quantity": str(allocation.quantity),
                "sales_order": order.number,
                "location": allocation.location.code if allocation.location_id else "",
                "promised_date": str(order.promised_date or ""),
            },
            tenant=request.tenant,
        )
        messages.info(
            request,
            f"Kept the promise on {order.number}. Nothing was released or cancelled and the "
            "promised date is unchanged — the decision is recorded against the allocation.",
        )
        return redirect("sales:order_fulfillment_board")

    # DELEGATE. 4.5 writes the status and re-derives the order's allocation state; this view never
    # does. Its own guard still wins if it refuses — that is the whole point of delegating.
    delegate = (
        salesorderallocation_release if resolution == "release" else salesorderallocation_cancel
    )
    with transaction.atomic():
        delegate(request, allocation.pk)
    return redirect("sales:order_fulfillment_board")


@require_POST
@login_required
@tenant_admin_required
def order_repeat(request, pk):
    """Raise a fresh DRAFT copy of a past order, through 4.5's own create path.

    The copy is created by 4.5's own machinery, not by 8.6 writing an order row: the header and the
    lines are built the way ``salesorder_create_from_quote`` builds them — ``SalesOrder(...)``,
    ``order.save()``, ``bulk_create`` over the line model, then **4.5's own ``recalc_totals()``** —
    so the number on the new order is produced by the code that owns the arithmetic rather than by
    a second implementation of it. 8.6 writes NO order field on an existing order here, and it
    writes no ``status``: the new row is a ``draft`` because that is 4.5's field default, and it
    goes through 4.5's own submit verb like any other draft.

    Only the CUSTOMER-FACING facts carry over. The workflow facts deliberately do not:
    ``promised_date``, the three notification stamps, the hold flags, the linked invoice and every
    allocation are all left behind with the order they described. Carrying a promise forward would
    be 8.6 rewriting a date a customer was given; carrying an allocation would reserve the same
    stock twice.

    POST-only, because creating a customer order is a mutation and a GET must never be one.
    """
    model = _sales_order_model()
    from apps.scm.models import SalesOrderLine

    source = get_object_or_404(
        model.objects.filter(tenant=request.tenant).select_related(
            "customer", "ship_to_address", "currency", "payment_terms"
        ),
        pk=pk,
    )
    source_lines = list(
        SalesOrderLine.objects.filter(sales_order_id=source.pk).select_related("item").order_by("id")
    )
    if not source_lines:
        messages.error(
            request,
            f"Order {source.number} has no lines, so there is nothing to repeat.",
        )
        return redirect("scm:salesorder_detail", pk=source.pk)

    with transaction.atomic():
        repeat = model(
            tenant=request.tenant,
            customer=source.customer,
            ship_to_address=source.ship_to_address,
            # Preserved on purpose: a customer who reorders by web should not have the repeat
            # filed as a manual order, or the channel mix on the capture board starts lying.
            source_channel=source.source_channel,
            order_date=timezone.localdate(),
            requested_date=timezone.localdate(),
            currency=source.currency,
            payment_terms=source.payment_terms,
            notes=(
                f"Repeat of order {source.number}."
                + (f"\n{source.notes}" if source.notes else "")
            ),
        )
        repeat.save()
        line_model = SalesOrderLine
        line_model.objects.bulk_create([
            line_model(
                sales_order=repeat,
                item=line.item,
                description=line.description,
                quantity_ordered=line.quantity_ordered,
                unit_price=line.unit_price,
                discount_pct=line.discount_pct,
                tax_pct=line.tax_pct,
            )
            for line in source_lines
        ])
        # 4.5's OWN totals. Never our arithmetic over their lines.
        repeat.recalc_totals()

    write_audit_log(
        request.user,
        repeat,
        "create",
        {
            "action": "order_repeat",
            "source_order": source.number,
            "lines": len(source_lines),
            "source_channel": repeat.source_channel,
            "total": str(repeat.total),
        },
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Draft order {repeat.number} raised from {source.number} with {len(source_lines)} "
        "line(s). Review it, then submit it from SCM — the promised date, the notifications and "
        "any stock allocation were left behind with the original.",
    )
    return redirect("scm:salesorder_detail", pk=repeat.pk)


@require_POST
@login_required
@tenant_admin_required
def order_validate(request, order_pk):
    """The read-only "why is — or is not — this order held" screen.

    This runs the rule set and shows the result WITHOUT raising anything. That separation is the
    whole reason it is its own screen: ``order_hold_raise`` persists a hold, and a user who wants
    to know what the rules would say should not have to raise one to find out — a hold raised "to
    see" is a hold somebody else then has to clear.

    It is POST-only for a reason that is easy to get backwards. The evaluation itself is pure and
    writes nothing, so a GET would be harmless; but the screen is reachable from a row button and
    a GET that can be triggered by a prefetch would run every rule in the workspace against an
    order on a crawler hit. POST + CSRF keeps it a deliberate act.

    ``evaluate()`` is PURE — it reads the order and the rule and returns — so nothing here can
    write even by accident, and the page says so.
    """
    model = _sales_order_model()
    order = get_object_or_404(
        model.objects.filter(tenant=request.tenant).select_related("customer", "currency"),
        pk=order_pk,
    )
    run_at = timezone.now()

    rules = OrderValidationRule.objects.filter(tenant=request.tenant, is_active=True)
    findings = []
    evaluated = 0
    for rule in rules:
        if not rule.runs_on("submit"):
            continue
        evaluated += 1
        rule_findings, _blocks = rule.evaluate(order)
        for finding in rule_findings:
            if isinstance(finding, dict):
                findings.append(finding)

    # Worst first, so the finding that would actually stop the order is the top line rather than
    # whichever rule happened to be created last. Ties keep 4.5/8.6's own ordering (priority,
    # number) because this sort is stable.
    severity_rank = {"block": 0, "hold": 1, "warn": 2}
    findings.sort(key=lambda finding: severity_rank.get(finding.get("severity"), 3))

    raised_holds = list(
        OrderHold.objects.filter(tenant=request.tenant, sales_order_id=order.pk)
        .select_related("rule", "raised_by")
        .order_by("-raised_at", "-id")
    )
    blocking_count = sum(
        1 for finding in findings if finding.get("severity") in OrderValidationRule.BLOCKING_SEVERITIES
    )

    return render(request, VALIDATION_TEMPLATE, {
        "order": order,
        "findings": findings,
        "raised_holds": raised_holds,
        "evaluation_run_at": run_at,
        "rules_evaluated": evaluated,
        "blocking_count": blocking_count,
    })


"""SCM 4.19 Integration & API Gateway — the ``IntegrationMessage`` exchange log, plus the failure
cockpit that reads it. List, detail, a single ``reprocess`` POST, and ``integration_exceptions``.

**THE ABSENT ROUTES ARE A DECISION, NOT AN OMISSION.** This module deliberately ships no
``integrationmessage_create``, no ``integrationmessage_edit`` and no ``integrationmessage_delete``,
and there is no form module, no url and no template for any of them. It is the ``scm.StockMove`` /
``scm.MeterReading`` / ``scm.PortalActivity`` posture, verbatim
(``views/AssetManagement/MeterReadings.py:1-23``): the log is append-only, so a wrong entry is
corrected by **appending a later, correct one**, exactly the way a wrong stock movement is corrected
by a compensating move and a wrong journal entry by a reversal.

Three things make that the right call rather than a missing feature:

* an exchange log is *evidence of what crossed the boundary*, and evidence that can be revised after
  the dispute starts is not evidence. "Your 855 said 400 units" has to rest on a row nobody could
  have quietly retyped;
* somebody already acted on these rows — a receipt was booked, an order was released, a 997 was
  chased — so rewriting the record leaves the action standing on a figure that exists nowhere;
* ``acknowledges`` chains the 997 to the 850 it answers. Editing the answered row silently rewrites
  what the acknowledgement is an acknowledgement *of*.

``admin.py`` registers the model read-only for the same reason. **If a later pass is tempted to add
an edit route here, the answer is a second message row, not a mutable first one.**

WHAT THIS MODULE OWNS BESIDES THE LOG PAGES:

* ``integration_exceptions`` — the failure cockpit, at ``integration-exceptions/``. It is a REPORT
  OVER ``IntegrationMessage`` ROWS, so it lives with the entity that owns the data rather than in a
  fifth ``Reports.py`` module that would own one view and no model. Its template sits at the
  SUB-MODULE ROOT (``scm/integration/exceptions.html``), template rule 6 — it is not any one
  entity's page. Deliberate, planned deviation from the todo plan's nominal fifth module; the
  build wave parallelizes per ENTITY and there is no fifth entity to hand it to.

**NOTHING HERE MAKES AN OUTBOUND REQUEST.** 4.19 ships no transport at all — no ``requests``, no
``urllib``, no ``httpx``, no ``http.client`` anywhere under ``apps/scm``. ``reprocess`` re-queues a
row and clears its error text; it does not contact the partner. Saying so out loud matters because
the button is called *Reprocess* and a reader would otherwise reasonably assume it re-sends.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here):

* ``scm/integration/integrationmessage/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``), plus ``endpoints`` (this tenant's ``IntegrationEndpoint`` queryset for the
  dropdown — a PK filter, so compare with ``{% if request.GET.endpoint == e.pk|stringformat:"d" %}``
  and never ``|slugify``), ``direction_choices`` / ``document_type_choices`` / ``status_choices`` /
  ``source_choices`` (pairs, compared as plain strings), ``date_from`` / ``date_to`` (the raw GET
  strings echoed back into the two date inputs) and ``stats`` (``total`` / ``pending`` / ``failed``
  / ``acknowledged``, over the WHOLE tenant queryset, never the filtered page). **No Add button, no
  Edit and no Delete action** — View plus the Reprocess POST form only.
* ``scm/integration/integrationmessage/detail.html`` — ``obj``, ``ack_message`` (the row that
  acknowledges THIS one, or ``None``) and ``can_reprocess`` (bool). The page links both directions:
  ``obj.acknowledges`` is what this row answers, ``ack_message`` is what answered it.
* ``scm/integration/exceptions.html`` — ``object_list`` (set explicitly by the hand-rolled render),
  ``page_obj``, ``q``, ``error_groups`` (list of dicts with exactly ``error_code`` / ``count`` /
  ``endpoint_count``), ``endpoints``, ``document_type_choices`` and ``stats`` (``failed_total`` /
  ``endpoints_affected`` / ``codes``).

**NEVER name a context key ``messages`` on any page in this sub-module** — it collides with
``django.contrib.messages`` in the template context and silently replaces the flash-message list
that ``partials/messages.html`` renders. The rows are ``object_list``; the endpoint's own panel
calls its slice ``recent_messages``.

Badge colours come from the model's own vocabularies. theme.css ships ``badge-green`` /
``badge-red`` / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate`` ONLY —
``badge-success`` / ``badge-warning`` / ``badge-danger`` do not exist and render unstyled (L33).
"""
import datetime

from apps.scm.views._common import *  # noqa: F401,F403
# `_need_tenant` is NOT imported and NOT used, deliberately: it guards CREATE paths, and this module
# has none (the log is append-only — see the docstring above). Nothing here writes a new row.
from apps.scm.views._helpers import _date_window

# The same search implementation `crud_list` uses, imported rather than re-written: the exceptions
# cockpit hand-rolls its render (it needs the grouped roll-up alongside the page slice), and a second
# copy of `q` semantics is a second place for the two pages to disagree about what searching means.
from apps.core.crud import apply_search

from apps.scm.models import IntegrationEndpoint, IntegrationMessage
# BY NAME, never `import *` — see the note at the head of the model module.
from apps.scm.models.IntegrationApiGateway._choices import (
    DOCUMENT_TYPE_CHOICES,
    MESSAGE_DIRECTION_CHOICES,
    MESSAGE_SOURCE_CHOICES,
    MESSAGE_STATUS_CHOICES,
)

#: Said once and read by the list, the detail page and the exceptions cockpit, so the three cannot
#: explain the missing Add/Edit/Delete three different ways (or, worse, two of them not at all).
APPEND_ONLY_NOTE = (
    "The exchange log is append-only. There is no Add, Edit or Delete: it is evidence of what "
    "actually crossed the boundary, and a record that can be revised after the dispute starts is "
    "not evidence. A wrong row is corrected by appending a later, correct one — exactly like a "
    "compensating stock movement. Reprocess re-queues a row; it does not edit it, and it does not "
    "contact the partner."
)

#: 30 rather than the app-wide 15 — the ``stock_ledger`` / ``meterreading_list`` /
#: ``portalactivity_list`` precedent: this is a high-volume append-only trail people SCAN for a
#: pattern, not a register they page through one record at a time.
MESSAGES_PER_PAGE = 30

#: The statuses ``reprocess`` refuses. ``pending`` is already queued (a second press would only
#: inflate ``attempt_count`` for an attempt nobody made), and ``acknowledged`` is a CLOSED exchange
#: — the partner has already answered it, and re-queuing would invite a duplicate document to be
#: sent against an acknowledgement that is already on file. Named here so the view guard and the
#: ``can_reprocess`` flag the template renders can never drift apart.
REPROCESS_BLOCKED_STATUSES = ("pending", "acknowledged")

#: What ``?q=`` searches on both message pages. The endpoint is a dropdown here, so folding its name
#: into the free-text box would make ``q`` mean two different things at once.
MESSAGE_SEARCH_FIELDS = ["number", "control_number", "external_id", "source_reference"]


# ==================================================================================== small helpers
def _message_window(qs, data):
    """Apply an optional ``?date_from=&date_to=`` window to ``occurred_at``, inclusively.

    ``occurred_at`` is a ``DateTimeField`` while the two filter boxes post plain dates, so somebody
    has to widen one into the other. A bare ``2026-08-04`` on the UPPER bound resolves to MIDNIGHT
    and would silently drop every message that crossed the boundary during the day somebody asked
    for — on a page whose whole job is "what came in on the 4th", that is the answer being wrong.

    **An explicit aware range rather than ``occurred_at__date__gte``** — a deliberate, documented
    departure from the contract's literal ``__date__gte`` spelling, and the sixth copy of a decision
    this codebase has already shipped five times (``AssetManagement/{MeterReadings,Reports}``,
    ``ColdChainManagement/{Reports,ColdChainMonitors,TemperatureReadings}``,
    ``CustomerPortal/PortalActivities``). Two reasons, both load-bearing here:

    * ``__date`` compiles to ``CONVERT_TZ`` on MariaDB and returns **NULL** when the timezone tables
      are not loaded, which on XAMPP they are not (the 4.12 carbon-report finding). A filter that
      evaluates to NULL matches nothing, so the page would render empty rather than wrong-but-
      obvious;
    * a function of a column cannot use ``scm_msg_tnt_occat_idx``. On the fastest-growing table in
      the sub-module that is the difference between an index range scan and a walk.

    The two context keys (``date_from`` / ``date_to``) and the two GET params are unchanged — only
    the ORM spelling differs, and the visible behaviour is identical apart from the end-of-day fix.

    Junk is SKIPPED, never raised on — the same L11 posture ``as_db_int`` takes: a hand-edited
    ``?date_from=lastweek`` must narrow nothing rather than 500 on a value anybody can type into the
    address bar.
    """
    widened = {}
    for param, end_of_day in (("date_from", False), ("date_to", True)):
        raw = (data.get(param) or "").strip()
        if not raw:
            continue
        try:
            day = datetime.date.fromisoformat(raw)
        except (ValueError, TypeError):
            continue
        moment = datetime.datetime.combine(
            day, datetime.time.max if end_of_day else datetime.time.min)
        if timezone.is_naive(moment):
            moment = timezone.make_aware(moment)
        widened[param] = moment.isoformat()
    return _date_window(qs, widened, "occurred_at")


def _endpoint_qs(tenant):
    """This tenant's endpoints, for the ``?endpoint=`` dropdown on both pages.

    ``.none()`` for a tenant-less user (the superuser has ``tenant=None`` by design) rather than a
    filter on NULL, matching ``_item_qs`` / ``_location_qs`` in ``views/_helpers.py``.
    """
    if tenant is None:
        return IntegrationEndpoint.objects.none()
    return IntegrationEndpoint.objects.filter(tenant=tenant).order_by("name")


def _message_stats(tenant):
    """The list page's four counters, over the WHOLE tenant queryset, in ONE aggregate query.

    Over everything and never over the filtered page: a header that silently re-counts itself as
    somebody types into the search box cannot answer "how much traffic is failing right now", which
    is the only question it is on the page to answer.
    """
    row = IntegrationMessage.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        failed=Count("id", filter=Q(status="failed")),
        acknowledged=Count("id", filter=Q(status="acknowledged")),
    )
    return {key: value or 0 for key, value in row.items()}


# ============================================================================================ pages
@login_required
def integrationmessage_list(request):
    """The append-only exchange log: search, endpoint, direction, type, status, source, date window.

    ``select_related("endpoint")`` covers every FK a row renders or whose ``__str__`` a link prints;
    without it a page of 30 messages is 30 extra queries for the endpoint column (L18). The two typed
    order pointers are deliberately NOT joined here — the template says so itself and renders
    neither, so joining them was two LEFT OUTER JOINs and ~55 unused columns per row on every page of
    the sub-module's fastest-growing table. :func:`integrationmessage_detail` joins both, because
    that page does render them.

    ``.defer("payload_excerpt", "error_message")`` drops the two ``TextField``s no list column reads
    (the failure cell renders ``error_code`` only) — a truncated document body pulled off this table
    30 rows at a time for nothing. ``defer`` touches the SELECT list ONLY, so the search over
    ``number``/``control_number``/``external_id``/``source_reference`` and all five filters are
    unaffected.

    The date window is applied BEFORE ``crud_list`` paginates — a filter applied afterwards would
    page over the unfiltered set and quietly show the wrong rows on page 2. ``endpoint`` goes
    through ``crud_list``'s ``is_int`` spec so ``?endpoint=abc`` / ``?endpoint=²`` /
    ``?endpoint=999999999999999999999`` all SKIP the filter instead of raising (L11); the four
    string filters go through its equality leg, where an unknown value narrows to an empty page
    rather than 500-ing.
    """
    qs = (IntegrationMessage.objects.filter(tenant=request.tenant)
          .select_related("endpoint")
          .defer("payload_excerpt", "error_message"))
    qs = _message_window(qs, request.GET)

    return crud_list(
        request, qs, "scm/integration/integrationmessage/list.html",
        search_fields=MESSAGE_SEARCH_FIELDS,
        filters=[
            ("endpoint", "endpoint_id", True),
            ("direction", "direction", False),
            ("document_type", "document_type", False),
            ("status", "status", False),
            ("source", "source", False),
        ],
        extra_context={
            # Every dropdown the template renders gets its data from here. A filter <select> with no
            # context is the recurring bug this rule exists to stop.
            "endpoints": _endpoint_qs(request.tenant),
            "direction_choices": MESSAGE_DIRECTION_CHOICES,
            "document_type_choices": DOCUMENT_TYPE_CHOICES,
            "status_choices": MESSAGE_STATUS_CHOICES,
            "source_choices": MESSAGE_SOURCE_CHOICES,
            # Echoed back verbatim so the two date inputs keep what was typed, including a value
            # that was rejected — silently blanking it looks like the page ignored the request.
            "date_from": (request.GET.get("date_from") or "").strip(),
            "date_to": (request.GET.get("date_to") or "").strip(),
            "stats": _message_stats(request.tenant),
            "append_only_note": APPEND_ONLY_NOTE,
        },
        per_page=MESSAGES_PER_PAGE,
    )


@login_required
def integrationmessage_detail(request, pk):
    """One exchange, both ends of its acknowledgement chain, and whether it can be re-queued.

    The chain is rendered in BOTH directions on purpose. ``obj.acknowledges`` is what this row
    answers (the 850 a 997 confirms); ``ack_message`` is what answered THIS row. Showing only the
    forward pointer leaves the far more common question — *did the partner ever acknowledge our
    850?* — unanswerable from the page about the 850.

    ``ack_message`` is re-scoped to the request tenant rather than trusted from the reverse
    accessor. The FK guard in ``clean()`` already refuses a cross-tenant pointer, but a row written
    before that guard (or by a raw import that skipped validation) must not be able to surface
    another workspace's message through a reverse relation.

    Hand-rolled ``render`` rather than ``crud_detail`` — a small, deliberate departure from the
    contract's literal spelling, taken for one reason: ``can_reprocess`` is derived from THIS row's
    ``status``, and ``crud_detail``'s ``extra_context`` has to be built *before* it fetches the
    object, so keeping it would mean a second query for a column the page is about to load anyway.
    The tenant scoping, the 404 behaviour, the ``select_related`` set and every context key are
    identical (``obj`` still comes from a tenant-filtered ``get_object_or_404``); this is the
    ``meterreading_detail`` shape, which hand-rolls for the same reason.
    """
    obj = get_object_or_404(
        IntegrationMessage.objects.select_related(
            "endpoint", "acknowledges", "purchase_order", "sales_order"),
        pk=pk, tenant=request.tenant)

    ack_message = (IntegrationMessage.objects
                   .filter(tenant=request.tenant, acknowledges_id=obj.pk)
                   .select_related("endpoint")
                   .first())

    return render(request, "scm/integration/integrationmessage/detail.html", {
        "obj": obj,
        "ack_message": ack_message,
        # The SAME tuple the reprocess view guards on, so a hidden button and a refused POST can
        # never disagree about which rows are re-queueable.
        "can_reprocess": obj.status not in REPROCESS_BLOCKED_STATUSES,
        "append_only_note": APPEND_ONLY_NOTE,
    })


# =========================================================================================== action
@login_required
@require_POST
def integrationmessage_reprocess(request, pk):
    """Re-queue one message: back to ``pending``, error text cleared, attempt counter bumped.

    **THIS FIRES NO HTTP REQUEST.** 4.19 ships no transport of any kind — no ``requests``, no
    ``urllib``, no ``httpx``, nothing. The action records the INTENT to re-run the exchange and
    resets the row's error state so a later pass (or an operator working the exceptions cockpit) has
    a clean, unambiguous queue to work from. The button says *Reprocess* and it would be entirely
    reasonable to assume it re-sends, which is exactly why it says so here and in the flash message.

    NOT ``@tenant_admin_required``, unlike the two rotate-credential actions in this sub-module: it
    mutates a log row's queue state, not a secret. Any member who can see the exceptions page can
    work it.

    The status guard lives HERE and not only in the template — hiding a button has never stopped a
    direct POST. It is evaluated INSIDE ``transaction.atomic()`` on a row taken ``FOR UPDATE``,
    because two concurrent POSTs (a double-click on a slow page, a retry, a replay) would otherwise
    both read ``failed``, both pass the guard, and both bump the counter for one re-queue. The
    ``write_audit_log`` row is written inside the same transaction: outside it, a failure between
    the commit and that line would leave a status change with nothing recording who made it.

    ``save(update_fields=…)`` is narrow on purpose — a full ``save()`` would write back every
    in-memory column, including any a concurrent import had just changed. ``updated_at`` is
    ``auto_now``, so it only fires when it is IN the list.
    """
    with transaction.atomic():
        obj = get_object_or_404(IntegrationMessage.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status in REPROCESS_BLOCKED_STATUSES:
            messages.error(
                request,
                f"{obj.number} cannot be reprocessed — it is "
                f"{obj.get_status_display().lower()}.")
            return redirect("scm:integrationmessage_detail", pk=pk)

        obj.status = "pending"
        obj.attempt_count = (obj.attempt_count or 0) + 1
        # Cleared, not kept: the row is being re-queued, and a stale error beside a pending status
        # is the kind of contradiction somebody eventually reports as a bug in the integration
        # rather than in the page.
        obj.error_code = ""
        obj.error_message = ""
        obj.save(update_fields=["status", "attempt_count", "error_code", "error_message",
                                "updated_at"])
        # Hand-rolled save path, so this owes its own audit row — the crud_* helpers write one for
        # you and nothing else does.
        write_audit_log(request.user, obj, "update",
                        changes={"status": "pending", "attempt_count": obj.attempt_count})

    messages.success(
        request,
        f"{obj.number} re-queued (attempt {obj.attempt_count}). Nothing was sent to the partner — "
        "outbound transport is not part of this release.")
    return redirect("scm:integrationmessage_detail", pk=pk)


# ========================================================================================== cockpit
@login_required
def integration_exceptions(request):
    """Every failed exchange in the workspace, grouped by error code — the failure cockpit.

    A report over ``IntegrationMessage`` rows rather than a page about one record, which is why it
    lives in this entity's module (the entity that owns the data owns the report) and why its
    template sits at the sub-module ROOT rather than in an entity folder (template rule 6).

    Hand-rolled ``render`` rather than ``crud_list`` because the page needs the grouped roll-up
    ALONGSIDE the paginated slice, and ``crud_list`` returns a response rather than a queryset. It
    therefore sets ``object_list`` explicitly — the ``coldchainmonitor_list`` /
    ``temperatureexcursion_list`` house pattern — so the template's row loop reads exactly the same
    on this page as on every other list in the app.

    ``error_groups`` is ONE grouped query, never a count per row: ``.values("error_code")
    .annotate(...)``. The bare ``.order_by()`` before ``.values()`` is load-bearing rather than
    cosmetic — the model's ``Meta.ordering`` (``-occurred_at, -id``) would otherwise be folded into
    the GROUP BY, which silently turns "failures per error code" into "failures per error code per
    timestamp", i.e. one group per row.

    ``stats`` is over the WHOLE tenant failure set and NOT over the filtered view, matching the
    house rule the message list follows: the header answers "how bad is it right now", the table
    below answers "what did I filter to". They are two different questions and one of them must not
    move when the other is asked.
    """
    tenant = request.tenant
    qs = (IntegrationMessage.objects.filter(tenant=tenant, status="failed")
          .select_related("endpoint"))

    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, MESSAGE_SEARCH_FIELDS)

    # L11, hand-rolled because this page does not go through crud_list's filter spec: `?endpoint=abc`,
    # `?endpoint=²` and a 21-digit value must all SKIP the filter rather than raise out of .filter().
    endpoint_pk = as_db_int(request.GET.get("endpoint"))
    if endpoint_pk is not None:
        qs = qs.filter(endpoint_id=endpoint_pk)

    # A string equality filter — an unknown value narrows to an empty page, which is honest, and
    # cannot raise.
    document_type = (request.GET.get("document_type") or "").strip()
    if document_type:
        qs = qs.filter(document_type=document_type)

    error_groups = list(
        qs.order_by()  # see the docstring — clears Meta.ordering out of the GROUP BY
          .values("error_code")
          .annotate(count=Count("id"), endpoint_count=Count("endpoint", distinct=True))
          .order_by("-count", "error_code")
    )

    # One aggregate for the three header figures. `error_code` is blank-not-null, so the
    # unclassified bucket counts as one distinct code — the same bucket `error_groups` shows as its
    # empty-code row, so the two figures agree.
    totals = IntegrationMessage.objects.filter(tenant=tenant, status="failed").aggregate(
        failed_total=Count("id"),
        endpoints_affected=Count("endpoint", distinct=True),
        codes=Count("error_code", distinct=True),
    )

    page_obj = paginate(request, qs, MESSAGES_PER_PAGE)
    return render(request, "scm/integration/exceptions.html", {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "error_groups": error_groups,
        "endpoints": _endpoint_qs(tenant),
        "document_type_choices": DOCUMENT_TYPE_CHOICES,
        "stats": {key: value or 0 for key, value in totals.items()},
        "append_only_note": APPEND_ONLY_NOTE,
    })

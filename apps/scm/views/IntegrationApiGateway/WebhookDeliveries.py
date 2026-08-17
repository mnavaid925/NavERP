"""SCM 4.19 Integration & API Gateway — ``WebhookDelivery`` views: the outbound attempt log.

Three function-based views — list, detail, and one ``retry`` POST — over the append-only record of
what each :class:`~apps.scm.models.WebhookSubscription` actually did, attempt by attempt.

--------------------------------------------------------------------------------------------------
THE ABSENT CREATE, EDIT AND DELETE VIEWS ARE A DECISION, NOT AN OMISSION
--------------------------------------------------------------------------------------------------
There is no ``webhookdelivery_create``, no ``_edit`` and no ``_delete`` here; no route for any of
them in ``apps/scm/urls/IntegrationApiGateway/WebhookDeliveries.py``; no ModelForm anywhere
(``apps/scm/forms/IntegrationApiGateway/WebhookDeliveries.py`` deliberately does not exist, and the
forms package ``__init__`` carries a comment saying so instead of an import); and no template for
any of them. It is the ``scm.StockMove`` / ``scm.MeterReading`` / ``scm.PortalActivity`` posture,
verbatim — the shape ``views/AssetManagement/MeterReadings.py:1-23`` states for 4.13's log and that
``apps/scm/tests/test_security.py``'s ``TestMeterReadingHasNoEditOrDeleteRoute`` asserts.

A delivery log answers what a partner asks in a dispute — *did you ever send it, how many times, and
what came back?* — and an answer somebody can retype after the argument starts is not an answer.
``crm.WebhookDelivery`` says the same thing in the same words: *"Immutable append-only delivery
record … Accessed list+detail only — never edited."* The correction for a wrong row is a LATER row.

**If a later pass is tempted to add an edit route here, the answer is a second attempt row, not a
mutable first one.**

--------------------------------------------------------------------------------------------------
NOTHING HERE SENDS ANYTHING — and ``retry`` least of all
--------------------------------------------------------------------------------------------------
4.19 ships no transport: no ``requests``, ``urllib``, ``httpx`` or ``http.client`` anywhere under
``apps/scm``, and no scheduler or task queue. :func:`webhookdelivery_retry` **performs no HTTP
request.** It advances the row to the next slot in the published backoff schedule and stamps
``next_attempt_at``; nothing wakes up and reads that stamp. The button says *Retry*, so the view, its
flash message, the URL module and the model docstring all say out loud that it does not re-send —
this is the one thing about the page a reader would otherwise reasonably assume.

There is likewise **no "test delivery" action** anywhere in the sub-module, for the same reason there
is no reveal view for a signing secret: a test button is an outbound HTTP request from the server to
a tenant-supplied URL, i.e. exactly the SSRF surface ``WebhookSubscription.target_url``'s comment
defers until an allow-list and a private-IP block exist.

--------------------------------------------------------------------------------------------------
CONTEXT-VAR CONTRACT (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the row variable)
--------------------------------------------------------------------------------------------------
``scm/integration/webhookdelivery/list.html``
    ``object_list`` (THE ROW VAR), ``page_obj``, ``q`` — all from ``crud_list``; guard prev/next
    with ``has_previous`` / ``has_next`` (L9). Filter widgets: ``subscriptions`` (this tenant's
    ``WebhookSubscription`` queryset behind ``?subscription=`` — a PK filter, so compare with
    ``{% if request.GET.subscription == s.pk|stringformat:"d" %}`` and **never** ``|slugify``),
    ``status_choices`` (a (value, label) list — a plain STRING compare), and ``date_from`` /
    ``date_to`` (the raw GET strings echoed back into the two date inputs, possibly ``""``). Header
    chips: ``stats`` with EXACTLY ``total`` / ``pending`` / ``success`` / ``failed`` / ``exhausted``
    (ints), over the WHOLE tenant queryset and never the filtered page.
    **No Add button.** The Actions column is View plus the Retry POST form only.

``scm/integration/webhookdelivery/detail.html``
    ``obj``, ``can_retry`` (bool — gates the Retry POST form), ``next_backoff_seconds``
    (int or ``None`` — rendered as *"next attempt in N seconds"* so the human knows what pressing
    Retry will do) and ``max_attempts`` (int, 8 — so the page can render *"attempt 3 of 8"*).
    Render ``obj.signature`` as *"Not computed — outbound transport is deferred"* when it is blank:
    an explicit label, never an empty cell that reads as a bug. Link back to
    ``scm:webhooksubscription_detail`` with ``obj.subscription.pk``.

**Never name a context key ``messages`` on any page in this sub-module** — it collides with
``django.contrib.messages`` in the template context and silently replaces the flash-message list that
``partials/messages.html`` renders.

Badges are COLOUR-NAMED ``theme.css`` classes only: ``success``→``badge-green``,
``failed``/``exhausted``→``badge-red``, ``pending``→``badge-amber``, ``simulated``→``badge-info``,
each chain ending ``{% else %}{{ obj.get_status_display }}``. ``badge-success`` / ``badge-danger`` /
``badge-warning`` DO NOT EXIST and render as completely unstyled text (L33, shipped four times).
"""
import datetime

from apps.scm.views._common import *  # noqa: F401,F403
# `_need_tenant` is NOT imported and NOT used, deliberately: it guards CREATE paths, and this module
# has none (the log is append-only — see the docstring above). Nothing here creates a row.
from apps.scm.views._helpers import _date_window

from apps.scm.models import WebhookDelivery, WebhookSubscription
# BY NAME, never `import *` — see the note at the head of the model module. `_choices.py` is owned
# and created by the `IntegrationEndpoints` entity; this module only reads from it.
#
# `DELIVERY_BACKOFF_SECONDS` is deliberately NOT imported here even though this module is the one
# that schedules against it: the tuple is read through `WebhookDelivery.next_backoff_seconds` and
# `WebhookDelivery.MAX_ATTEMPTS`, so the arithmetic that turns an attempt number into a slot exists
# in exactly one place. A second copy of that indexing rule in the view is how the number the detail
# page promises and the number the retry stamps come to differ by one.
from apps.scm.models.IntegrationApiGateway._choices import DELIVERY_STATUS_CHOICES


#: Said once and read by both pages, so the list and the detail cannot explain the missing
#: Add/Edit/Delete two different ways (or, worse, one of them not at all).
APPEND_ONLY_NOTE = (
    "The delivery log is append-only. There is no Add, Edit or Delete: it is evidence of what was "
    "actually attempted, and a record that can be revised after the dispute starts is not evidence. "
    "A wrong row is corrected by appending a later, correct one. Retry re-queues a row onto the next "
    "backoff slot; it does not edit the recorded outcome, and it does not contact the target."
)

#: 30 rather than the app-wide 15 — the ``stock_ledger`` / ``meterreading_list`` /
#: ``portalactivity_list`` / ``integrationmessage_list`` precedent: this is high-volume append-only
#: telemetry people SCAN for a pattern, not a register they page through one record at a time. One
#: row per ATTEMPT means this table grows faster than any other in the sub-module.
DELIVERIES_PER_PAGE = 30

#: The statuses :func:`webhookdelivery_retry` will act on, and the same tuple the ``can_retry`` flag
#: is built from — so a hidden button and a refused POST can never disagree about which rows are
#: retryable. ``success`` is done, ``simulated`` never left the process (there is nothing to retry
#: until a transport exists), and ``exhausted`` has already run the whole published schedule.
RETRYABLE_STATUSES = ("failed", "pending")

#: What ``?q=`` searches. The subscription is a dropdown on this page, so its name is folded in
#: anyway for the case somebody pastes a rule name into the free-text box rather than picking it.
DELIVERY_SEARCH_FIELDS = ("event", "subscription__name")


# ==================================================================================== small helpers
def _delivery_window(qs, data):
    """Apply an optional ``?date_from=&date_to=`` window to ``triggered_at``, inclusively.

    ``triggered_at`` is a ``DateTimeField`` while the two filter boxes post plain dates, so somebody
    has to widen one into the other. A bare ``2026-08-04`` on the UPPER bound resolves to MIDNIGHT
    and would silently drop every attempt made during the day somebody asked for.

    **An explicit aware datetime range rather than ``triggered_at__date__gte``** — a deliberate,
    documented departure from the contract's literal ``__date__gte`` spelling, and the same call this
    codebase has already shipped six times (``AssetManagement/{MeterReadings,Reports}``,
    ``ColdChainManagement/{Reports,ColdChainMonitors,TemperatureReadings}``,
    ``CustomerPortal/PortalActivities``) plus this sub-module's own ``integrationmessage_list``,
    which was written against the identical contract wording. Two reasons, both load-bearing here:

    * ``__date`` compiles to ``CONVERT_TZ`` on MariaDB and returns **NULL** when the timezone tables
      are not loaded, which on XAMPP they are not (the 4.12 carbon-report finding). A filter that
      evaluates to NULL matches nothing, so the page would render EMPTY rather than wrong-but-
      obvious;
    * a function of a column cannot use ``scm_whd_tnt_trigat_idx``. On the fastest-growing table in
      the sub-module that is the difference between an index range scan and a full walk.

    The two context keys (``date_from`` / ``date_to``), the two GET params and the visible behaviour
    are unchanged apart from the end-of-day fix — only the ORM spelling differs.

    Junk is SKIPPED, never raised on — the same L11 posture ``as_db_int`` takes: a hand-edited
    ``?date_from=lastweek`` must narrow nothing rather than 500 on a value anybody can type into the
    address bar. ``date.fromisoformat`` also raises on a well-FORMATTED non-day (``2026-02-30``),
    which is exactly as much "not a date" and takes the same answer.
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
    return _date_window(qs, widened, "triggered_at")


def _subscription_qs(tenant):
    """This tenant's subscriptions, for the ``?subscription=`` dropdown.

    ``.none()`` for a tenant-less user (the superuser has ``tenant=None`` by design) rather than a
    filter on NULL, matching ``_item_qs`` / ``_location_qs`` in ``views/_helpers.py``.
    """
    if tenant is None:
        return WebhookSubscription.objects.none()
    return WebhookSubscription.objects.filter(tenant=tenant).order_by("name")


def _delivery_stats(tenant):
    """The list page's five counters, over the WHOLE tenant queryset, in ONE aggregate query.

    Over everything and never over the filtered page: a header that silently re-counts itself as
    somebody types into the search box cannot answer *"how many pushes are failing right now"*, which
    is the only question it is on the page to answer. **DERIVED on read, never stored** (L29) — a
    cached counter beside an append-only log is a second source of truth for a fact the log already
    answers, and the two disagree the first time a write is rolled back.

    No alias here collides with a model field name, which is the trap that turns a shared aggregate
    into a ``FieldError``.
    """
    row = WebhookDelivery.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        success=Count("id", filter=Q(status="success")),
        failed=Count("id", filter=Q(status="failed")),
        exhausted=Count("id", filter=Q(status="exhausted")),
    )
    return {key: value or 0 for key, value in row.items()}


# ============================================================================================ pages
@login_required
def webhookdelivery_list(request):
    """Every push attempt in the workspace: search, subscription, status and a date window.

    The subscription detail page deep-links here as ``?subscription=<pk>``, so that param has to work
    on first load — it goes through ``crud_list``'s ``is_int`` leg, where ``?subscription=abc``,
    ``?subscription=²`` and ``?subscription=999999999999999999999`` all SKIP the filter rather than
    raise out of ``.filter()`` (L11: the first two die in ``int()``, the third inside the database
    driver). ``?status=`` is a plain equality compare, where an unknown value narrows to an empty
    page rather than 500-ing.

    Every filter — including the hand-rolled date window — is applied BEFORE ``crud_list`` paginates.
    A filter applied afterwards would page over the unfiltered set and quietly show the wrong rows on
    page 2.

    ``select_related("subscription")`` covers the one FK a row renders and whose ``__str__`` the link
    prints; without it a page of 30 attempts is 30 extra queries for one column (L18). It is also the
    join ``?q=`` searches through (``subscription__name``), which ``select_related`` does not itself
    provide but which shares the same relation.

    ``.defer("payload_excerpt")`` drops the one ``TextField`` no list column renders, off the table
    that grows a row per attempt. ``error_message`` is emphatically NOT deferred — the failure cell
    truncates it at 64 chars, and deferring a field the template reads turns one saved column into
    one extra query PER ROW. ``defer`` touches the SELECT list only, so the search and both filters
    are unaffected.

    **No Add button on this page** and no Edit/Delete in the Actions column — see the module
    docstring. ``append_only_note`` is passed so the template can say why in one place rather than
    each page inventing its own wording.
    """
    qs = (WebhookDelivery.objects.filter(tenant=request.tenant)
          .select_related("subscription")
          .defer("payload_excerpt"))
    qs = _delivery_window(qs, request.GET)

    return crud_list(
        request, qs, "scm/integration/webhookdelivery/list.html",
        search_fields=DELIVERY_SEARCH_FIELDS,
        filters=(
            ("subscription", "subscription_id", True),
            ("status", "status", False),
        ),
        extra_context={
            # Every dropdown the template renders gets its data from here. A filter <select> with no
            # context is the recurring bug this rule exists to stop.
            "subscriptions": _subscription_qs(request.tenant),
            "status_choices": DELIVERY_STATUS_CHOICES,
            # Echoed back verbatim so the two date inputs keep what was typed, including a value
            # that was REJECTED — silently blanking it looks like the page ignored the request.
            "date_from": (request.GET.get("date_from") or "").strip(),
            "date_to": (request.GET.get("date_to") or "").strip(),
            "stats": _delivery_stats(request.tenant),
            "append_only_note": APPEND_ONLY_NOTE,
        },
        per_page=DELIVERIES_PER_PAGE,
    )


@login_required
def webhookdelivery_detail(request, pk):
    """One attempt: its payload excerpt, its outcome, and what a Retry would schedule.

    Context keys, exhaustively (the template is written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.WebhookDelivery`, from a tenant-filtered
      ``get_object_or_404`` with ``select_related("subscription")``. Render ``obj.signature`` as
      *"Not computed — outbound transport is deferred"* when it is blank.
    * ``can_retry`` — built from the SAME :data:`RETRYABLE_STATUSES` tuple and the same attempt
      ceiling the retry view guards on, so a hidden button and a refused POST cannot disagree.
    * ``next_backoff_seconds`` — seconds until the attempt Retry would queue, or ``None`` when the
      published schedule is spent. Read off the model property so the number the page promises and
      the number the view stamps are computed in one place.
    * ``max_attempts`` — 8, the length of the schedule, so the page can render *"attempt 3 of 8"*.

    Hand-rolled ``render`` rather than ``crud_detail`` — a small, deliberate departure from the
    contract's literal spelling, taken for one reason and matching this sub-module's own
    ``integrationmessage_detail``, which took it against identical wording: all three derived keys
    are functions of THIS row's ``status`` and ``attempt_no``, and ``crud_detail`` builds its
    ``extra_context`` *before* it fetches the object, so keeping it would mean a second read of a row
    the page is about to load anyway. The tenant scoping, the 404 behaviour, the ``select_related``
    set and every context key are identical — ``obj`` still comes from a tenant-filtered
    ``get_object_or_404``, so a cross-tenant pk 404s exactly as before. This is also the
    ``meterreading_detail`` shape, which hand-rolls for the same reason.
    """
    obj = get_object_or_404(
        WebhookDelivery.objects.select_related("subscription"), pk=pk, tenant=request.tenant)

    return render(request, "scm/integration/webhookdelivery/detail.html", {
        "obj": obj,
        # The SAME tuple and the SAME ceiling the retry view guards on, so a hidden button and a
        # refused POST can never disagree about which rows are retryable.
        "can_retry": (obj.status in RETRYABLE_STATUSES
                      and obj.attempt_no < WebhookDelivery.MAX_ATTEMPTS),
        "next_backoff_seconds": obj.next_backoff_seconds,
        "max_attempts": WebhookDelivery.MAX_ATTEMPTS,
        "append_only_note": APPEND_ONLY_NOTE,
    })


# =========================================================================================== action
@login_required
@require_POST
def webhookdelivery_retry(request, pk):
    """Queue this attempt onto the next backoff slot — or mark it exhausted. **Sends nothing.**

    **THIS FIRES NO HTTP REQUEST.** 4.19 ships no transport of any kind, and no scheduler reads
    ``next_attempt_at`` afterwards. The action records the INTENT to try again and stamps the slot the
    published schedule says that attempt belongs in, so the row's state stays honest and a later
    transport pass has an unambiguous queue to work from. The button is called *Retry*, which is
    exactly why the flash message says out loud that nothing was sent.

    The schedule is Svix's, adopted verbatim: 8 attempts over roughly 32 hours. Attempt N has already
    consumed slot N-1, so the next slot is index ``attempt_no`` — and when that index runs off the
    end, the row is marked ``exhausted`` with ``next_attempt_at`` CLEARED rather than being given an
    attempt the schedule does not describe. "This attempt failed" and "we have stopped trying" are
    different operational facts and only one of them needs a human.

    NOT ``@tenant_admin_required``, unlike the two rotate-credential actions in this sub-module: it
    moves a log row's queue state, not a secret. Anyone who can see the log can work it. It IS
    ``@require_POST``, so a GET is a 405 rather than a silent state change — a retry link that a
    crawler or a prefetching browser could follow would re-queue rows nobody asked about.

    **The status guard lives HERE, not only in the template** — hiding a button has never stopped a
    direct POST. It is evaluated INSIDE ``transaction.atomic()`` on a row taken ``FOR UPDATE``,
    because two concurrent POSTs (a double-click on a slow page, a retry, a replay) would otherwise
    both read ``failed``, both pass the guard, and both bump ``attempt_no`` for one re-queue —
    burning two slots of an 8-slot schedule on a single press. ``write_audit_log`` is written inside
    the same transaction: outside it, a failure between the commit and that line would leave a state
    change with nothing recording who made it.

    ``save(update_fields=…)`` is narrow on purpose — a full ``save()`` would write back every
    in-memory column, including any a concurrent import had just changed, and this table's other
    columns are the RECORDED OUTCOME, which this action must never rewrite. ``updated_at`` is
    ``auto_now``, so it only fires when it is IN the list.
    """
    with transaction.atomic():
        obj = get_object_or_404(WebhookDelivery.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)

        if obj.status not in RETRYABLE_STATUSES:
            messages.error(
                request,
                f"This attempt cannot be retried — it is {obj.get_status_display().lower()}.")
            return redirect("scm:webhookdelivery_detail", pk=pk)

        # None means the published schedule is spent. Read from the model property so the number the
        # detail page promised and the number stamped here can never be two different calculations.
        wait_seconds = obj.next_backoff_seconds
        if wait_seconds is None:
            obj.status = "exhausted"
            # CLEARED, not left behind: a stale future timestamp beside an exhausted status is the
            # kind of contradiction somebody eventually reports as a bug in the integration rather
            # than in the page.
            obj.next_attempt_at = None
        else:
            obj.status = "pending"
            obj.attempt_no += 1
            obj.next_attempt_at = timezone.now() + datetime.timedelta(seconds=wait_seconds)

        obj.save(update_fields=["status", "attempt_no", "next_attempt_at", "updated_at"])
        # Hand-rolled save path, so this owes its own audit row — the crud_* helpers write one for
        # you and nothing else does.
        write_audit_log(request.user, obj, "update",
                        changes={"status": obj.status, "attempt_no": obj.attempt_no})

    if obj.status == "exhausted":
        messages.info(
            request,
            f"All {WebhookDelivery.MAX_ATTEMPTS} attempts in the retry schedule have been used, so "
            f"this delivery is now marked exhausted. Nothing was sent — outbound transport is not "
            f"part of this release.")
    else:
        messages.info(
            request,
            f"Attempt {obj.attempt_no} of {WebhookDelivery.MAX_ATTEMPTS} queued for "
            # localtime, not the raw aware value: the column is stored in UTC and a message that
            # quotes a time somebody is meant to act on has to be in the time they read clocks in
            # (the `maintenanceworkorder_schedule` / `meterreading_*` precedent).
            f"{timezone.localtime(obj.next_attempt_at):%d %b %Y %H:%M} ({wait_seconds}s from now). "
            f"Nothing was sent — outbound transport is not part of this release.")
    return redirect("scm:webhookdelivery_detail", pk=pk)

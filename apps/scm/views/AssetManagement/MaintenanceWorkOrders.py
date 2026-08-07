"""SCM 4.13 Asset Management — ``MaintenanceWorkOrder`` views: the job ladder and the parts issue.

**One table, one form, ten verbs.** A maintenance *request*, a generated PM occurrence and a
breakdown are the same document at different points on one ladder — see the model docstring for why
there is no second "notification" table. ``status`` is ``editable=False`` and absent from
``Meta.fields``, so the ONLY way it moves is through the verbs below. A crafted ``status=completed``
in a POST body cannot land: there is no path from form data to the column at all.

**The ladder, stated once** (the module constants below are what both the guards and the ``can_*``
flags on the detail page read, so a button and the route behind it cannot disagree — the 4.10 "two
of three shapes" finding)::

    requested --approve--> approved --schedule--> scheduled --start--> in_progress
                                        \\                                |  ^
                                         \\--------- start --------------/   |
                                                                    hold |   | resume
                                                                         v   |
                                                                       on_hold
    in_progress --complete--> completed --close--> closed
    any OPEN status --cancel--> cancelled

``start`` accepts ``approved`` as well as ``scheduled`` on purpose: a breakdown is worked the moment
somebody walks to the machine, and forcing a scheduling step through a form first would either be
skipped by typing a fake date or would leave every reactive job stuck one rung down. ``complete``
does NOT accept ``on_hold`` — a held job is resumed and then completed, which costs one extra click
and keeps "was it ever actually restarted?" answerable from the ladder rather than from a guess.

**Every verb is ``@require_POST`` and locks its row.** Each one opens ``transaction.atomic()``, takes
the work order ``FOR UPDATE`` and re-reads its status INSIDE the lock, so a double-click, a retry or
a replay cannot stamp ``started_at`` twice, advance a plan's schedule twice, or post one part line's
stock twice. This is the shape 4.3's ``stocktransfer_complete`` established and 4.8/4.12 kept; do not
simplify it away. An illegal move is a ``messages.error`` + redirect, never a 500 and never a silent
no-op — and a cross-tenant pk is resolved (and 404s) BEFORE any guard can answer 302, which is the
4.12 finding priced in advance.

**``maintenanceworkorder_issue_parts`` is the ONLY thing in the whole of 4.13 that writes a ledger,
and it posts NO ``JournalEntry``** (the standing 4.9/4.10/4.11/4.12 rule, L29). It appends one
negative ``maintenance`` ``StockMove`` per un-issued part line through the SHARED
``_post_stock_move`` service — never a hand-rolled ``StockMove.objects.create`` — so on-hand stays a
pure aggregate of one append-only ledger. A shortfall is a MESSAGE, not an exception: the lines that
can be drawn are drawn and the ones that cannot are named, because refusing an eight-line issue over
one missing washer helps nobody. ``unit_cost`` is stamped from ``item.average_cost`` **at issue
time**, never read live afterwards — average cost moves with every receipt, so a live read would
quietly restate the cost of a repair closed last quarter every time a new delivery landed.

**Query hygiene.** The list page annotates the issued parts cost in ONE grouped aggregate
(:func:`_with_costs`) rather than letting the template touch ``MaintenanceWorkOrder.parts_cost`` /
``.total_cost``, both of which walk ``self.parts.all()`` and would be a query PER ROW. The detail
page prefetches ``parts`` and ``tasks`` for exactly the same reason — those two properties then read
the cache the page has already paid for, which is what their own docstrings promise.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here, not just the list variable):

* ``scm/assets/maintenanceworkorder/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``), where every row additionally carries the two annotations ``issued_parts_cost``
  (Decimal, 0 when nothing has been issued) and ``job_cost`` (Decimal — issued parts + labour +
  external). Filter context: ``status_choices`` / ``work_type_choices`` / ``priority_choices`` /
  ``problem_code_choices`` (all lists of ``(value, label)`` pairs), ``assets`` (an ``Asset``
  queryset) and ``assignees`` (a ``core.Party`` queryset). Header chips: ``stats``, a dict with keys
  ``open`` / ``in_progress`` / ``on_hold`` / ``down_now`` / ``unplanned_downtime_minutes`` (the last
  is ``None`` when no unplanned outage has ever been recorded — print an em dash, never a 0 that
  reads as a measurement). Filter params: ``q`` / ``status`` / ``work_type`` / ``priority`` /
  ``problem_code`` (strings — compare with ``request.GET.<param>`` directly) and ``asset`` /
  ``assigned_to`` (pks — compare with ``a.pk|stringformat:"d"``, NEVER ``|slugify``), plus
  ``date_from`` / ``date_to`` on ``reported_at``.
* ``scm/assets/maintenanceworkorder/form.html`` — ``form``, ``formset`` (the parts inline formset),
  ``is_edit`` and ``obj`` (``None`` on create).
* ``scm/assets/maintenanceworkorder/detail.html`` — ``obj``, ``parts`` (list), ``tasks`` (list),
  ``moves`` (the ``StockMove`` rows this job wrote), ``readings`` (the ``MeterReading`` rows filed
  against this job), ``parts_cost`` / ``labour_cost`` / ``total_cost`` (Decimals),
  ``duration_hours`` and ``is_on_time`` (both ``None`` when unanswerable — a blank, never a
  confident zero/False), ``open_task_count``, ``unissued_part_count``, ``issued_part_count``,
  ``has_issued_parts``, ``can_edit`` / ``can_delete`` and the ten action gates ``can_approve`` /
  ``can_schedule`` / ``can_start`` / ``can_hold`` / ``can_resume`` / ``can_complete`` / ``can_close``
  / ``can_cancel`` / ``can_issue_parts`` / ``can_record_reading``, plus ``parts_location_missing``
  (issue-parts is refused outright without a storeroom, so say so instead of offering a one-click
  failure) and ``asset_meter_name`` / ``asset_meter_unit`` (labels for the reading box — blank when
  the asset names no meter, in which case the capture cannot be filed).

Badge colours come from the model: ``obj.status_css`` / ``obj.priority_css`` / ``obj.work_type_css``
and ``obj.asset.criticality_css``. ``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT
EXIST in theme.css (L33).

POST payloads the verb routes read. None of them takes a ``Form``, so the template names these
inputs explicitly:

* ``<int:pk>/schedule/`` — OPTIONAL ``scheduled_start`` (``date`` or ``datetime-local``). Required
  in effect when the job has none yet: ``is_on_time`` is measured against it, so committing a job to
  "scheduled" with no date is a commitment to nothing.
* ``<int:pk>/hold/`` — OPTIONAL ``reason`` (recorded in the audit row only).
* ``<int:pk>/complete/`` — OPTIONAL ``resolution_notes``. Collected HERE because ``is_editable`` is
  the open statuses only, so the moment the job completes the edit form can no longer reach the
  field — and completion is exactly when the technician has something to write.
* ``<int:pk>/cancel/`` — OPTIONAL ``reason`` (recorded in the audit row only).
* ``<int:pk>/record-reading/`` — REQUIRED ``reading``; OPTIONAL ``meter_name`` (defaults to the
  asset's primary meter), ``unit`` (defaults to the asset's), ``read_at`` and ``notes``.
* ``maintenance-work-order-tasks/<int:pk>/toggle/`` — OPTIONAL ``actual_result``.

``maintenanceworkorder_delete``, ``_approve``, ``_cancel`` and ``_issue_parts`` are
``@tenant_admin_required``, so wrap those four buttons in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a member a button
they will 403 on is the 4.11 finding.
"""
from datetime import datetime, time

from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date, parse_datetime

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_acting_party, _date_window, _insufficient_stock,
                                     _need_tenant, _post_stock_move, _shared_items)
# Views legitimately depend on forms for the shared party querysets — the `_supplier_parties`
# precedent in views/_helpers.py. The `assigned_to` filter dropdown must offer the same set the
# form's `assigned_to` field offers, or the filter lists people the field cannot select.
from apps.scm.forms._common import _employee_parties
# The clamped quantizer every writer of a computed figure goes through: a raw `average_cost` copied
# straight onto `unit_cost` could exceed what DecimalField(14, 4) holds and fail the whole atomic
# block rather than the one offending line.
from apps.scm.models._base import q4
# The three shared vocabularies come from `_choices` via the models package's star re-export, NOT
# from `_meta.get_field(...).choices`: they are the same lists the filter dropdowns and the form
# render from, and naming them directly is what keeps "the filter offers what the column accepts" a
# fact rather than a coincidence.
from apps.scm.models import (Asset, MaintenancePlan, MaintenanceWorkOrder,
                             MaintenanceWorkOrderPart, MaintenanceWorkOrderTask, MeterReading,
                             StockMove, PRIORITY_CHOICES, PROBLEM_CODE_CHOICES, WORK_TYPE_CHOICES)
from apps.scm.forms import MaintenanceWorkOrderForm, MaintenanceWorkOrderPartFormSet, MeterReadingForm

ZERO = Decimal("0")

#: How many child rows each panel on the detail page shows. A queryset SLICE, so the DATABASE
#: applies it — it bounds what is fetched, not what is rendered (L40 §1: a guard that first builds
#: the whole thing is the payload, not a guard).
MAX_PANEL_ROWS = 50

# =================================================================================== the ladder
# Declared ONCE and read by BOTH the guard inside each verb and the `can_*` flag handed to the
# detail template, so a button and the route behind it can never disagree about whether an action is
# available (the 4.10 "two of three shapes" finding). See the module docstring for the diagram.
APPROVABLE_STATUSES = ("requested",)
#: `scheduled` is included so a committed date can be MOVED without first walking the job backwards.
SCHEDULABLE_STATUSES = ("approved", "scheduled")
#: `approved` as well as `scheduled` — a breakdown is worked the moment somebody walks to the
#: machine, and a reactive job that had to be "scheduled" first would only ever be given a fake date.
STARTABLE_STATUSES = ("approved", "scheduled")
HOLDABLE_STATUSES = ("in_progress",)
RESUMABLE_STATUSES = ("on_hold",)
#: Deliberately NOT `on_hold` — a held job is resumed and then completed. One extra click buys
#: "was it ever actually restarted?" as a fact on the ladder rather than a guess.
COMPLETABLE_STATUSES = ("in_progress",)
CLOSABLE_STATUSES = ("completed",)
#: Anything still live. The model owns the tuple (three readers outside this file depend on it).
CANCELLABLE_STATUSES = MaintenanceWorkOrder.OPEN_STATUSES
#: Parts may be drawn while the job is live and never once it is terminal — issuing against a closed
#: job would attach a stock consumption to a document nobody can change.
ISSUABLE_STATUSES = MaintenanceWorkOrder.OPEN_STATUSES
#: A meter capture is a fact about the machine, so it is accepted right up to completion; `closed`
#: and `cancelled` are history and take no new attachments.
READABLE_STATUSES = MaintenanceWorkOrder.OPEN_STATUSES + ("completed",)

#: One output shape for every money expression below, so Django never has to guess how to combine a
#: SUM of (quantity × unit_cost) with two plain DecimalField columns.
_MONEY = models.DecimalField(max_digits=20, decimal_places=4)


# =================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb in this module answers with."""
    return redirect("scm:maintenanceworkorder_detail", pk=pk)


def _with_costs(qs):
    """Annotate ``issued_parts_cost`` and ``job_cost`` in ONE grouped aggregate.

    ``MaintenanceWorkOrder.parts_cost`` walks ``self.parts.all()``, which is correct on the detail
    page (the lines are prefetched there) and is a query PER ROW on a list page. ``total_cost`` calls
    it, so a cost column rendered from the model would be 15 extra queries per screen and 15 more
    every time the value is printed a second time. One ``Sum`` with a ``filter=`` does the whole page.

    ``filter=Q(parts__is_issued=True)`` mirrors the property exactly: an unissued line has
    ``unit_cost`` 0 (it is stamped at issue time), so it contributes nothing either way — the
    explicit test keeps the INTENT visible if someone later defaults the cost. ``Coalesce`` is
    load-bearing rather than tidy: without it a job with no parts annotates ``None`` and ``job_cost``
    silently becomes ``None`` too, blanking a labour-only repair's cost on the list.

    Only ONE reverse join is added, so nothing here fans the rows out; every search field and every
    filter this page applies afterwards walks a FORWARD FK (``asset``/``plan``/``assigned_to``),
    which cannot multiply a row and therefore cannot double the SUM.
    """
    return qs.annotate(
        issued_parts_cost=Coalesce(
            Sum(F("parts__quantity") * F("parts__unit_cost"),
                filter=Q(parts__is_issued=True), output_field=_MONEY),
            models.Value(ZERO, output_field=_MONEY), output_field=_MONEY),
    ).annotate(
        job_cost=models.ExpressionWrapper(
            F("issued_parts_cost") + F("labour_hours") * F("labour_rate") + F("external_cost"),
            output_field=_MONEY),
    # The Meta ordering RESTATED, and it is not redundant. `QuerySet.ordered` returns False the
    # moment a query has a GROUP BY, even though the compiler still emits the Meta ORDER BY — so
    # without this `paginate()` raises UnorderedObjectListWarning on every page load of a list that
    # is in fact perfectly ordered (the same 4.8 finding views/_common.py:20-23 records against
    # Count()). The SQL is identical to the default; only the property stops lying.
    ).order_by("-reported_at", "-id")


def _posted_moment(raw):
    """A POSTed/queried date or datetime string as an AWARE datetime, or ``None`` when it is not one.

    The verbs take raw inputs rather than a ``Form``, and a hand-edited ``scheduled_start=lastweek``
    must be a friendly message rather than a ``ValidationError`` out of ``.filter()``/``.save()`` —
    the same posture ``_date_window`` and ``as_db_int`` take on the read side (L11). A bare date is
    accepted (a ``<input type="date">`` is the normal control) and read as that day's 00:00 in the
    project timezone; a naive datetime is localised for the same reason, because a naive value handed
    to a ``DateTimeField`` under ``USE_TZ`` is read as UTC and silently shifts the whole commitment.

    **Both parsers RAISE on a value that is well FORMATTED but not a real moment**, and that is the
    one case a "returns None on junk" reading of them misses. ``parse_date("9999-99-99")`` raises
    ``ValueError: month must be in 1..12`` (so do ``0000-01-01`` and ``2026-02-30``), and
    ``parse_datetime("2026-01-01T25:00:00")`` raises ``hour must be in 0..23`` — Django's own
    docstrings say so in as many words. Uncaught, that is a 500 on TWO surfaces: the schedule verb's
    POST body, and ``?date_from=`` on the work-order list, which is a URL anybody can type into the
    address bar. An impossible date is exactly as much "not a moment" as ``lastweek`` is, so it takes
    the same answer: ``None``, the filter is skipped or the verb says so, and nothing raises.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = parse_datetime(raw)
    except ValueError:
        value = None
    if value is None:
        try:
            day = parse_date(raw)
        except ValueError:
            day = None
        value = datetime.combine(day, time.min) if day is not None else None
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _reported_window(qs, data):
    """Apply ``?date_from=&date_to=`` to ``reported_at`` through the SHARED ``_date_window`` helper.

    The helper still does the filtering, owns the lookup names and owns the skip-junk-input rule —
    it is used, never re-implemented. All this adds is that it is handed AWARE, full-day boundaries
    instead of the bare date strings a ``<input type="date">`` posts, because ``reported_at`` is a
    ``DateTimeField`` and every other page that uses the helper filters a ``DateField``. On a
    datetime column a bare ``2026-08-04`` is two defects at once:

    * ``date_to`` becomes ``<= 2026-08-04 00:00``, so the filter EXCLUDES the whole day the user
      asked for — a window that silently loses its last day is worse than no window;
    * the value is naive under ``USE_TZ``, which is a ``RuntimeWarning`` on every filtered page load
      and, under any project timezone other than UTC, a silently shifted window.

    :func:`_posted_moment` — this module's own parser, already needed by the schedule verb — turns
    each end into an aware moment, and a bare date on the ``to`` end is extended to that day's last
    microsecond so the window is inclusive at both ends, exactly like the ``DateField`` pages.
    Unparseable input yields ``None`` and the key is simply not passed, so it skips the filter rather
    than raising — the same posture as before (L11).
    """
    window = {}
    start = _posted_moment(data.get("date_from"))
    if start is not None:
        window["date_from"] = start.isoformat()
    end = _posted_moment(data.get("date_to"))
    if end is not None:
        if end.time() == time.min:   # a bare date — take the whole of that day
            end = timezone.make_aware(datetime.combine(end.date(), time.max),
                                      timezone.get_current_timezone())
        window["date_to"] = end.isoformat()
    return _date_window(qs, window, "reported_at")


def _issued_parts_refusal(obj):
    """The one sentence that refuses a job whose parts are already on the ledger, or ``""``.

    Written once and passed as a ``precheck`` to both the cancel verb and the delete view, because
    the two refuse for the same reason and must refuse identically. Callers must evaluate it INSIDE
    the row lock — see :func:`_transition`.
    """
    if obj.parts.filter(is_issued=True).exists():
        return (f"{obj.number} has parts already issued from stock and cannot be "
                f"{'deleted' if obj.status in MaintenanceWorkOrder.OPEN_STATUSES else 'changed'} — "
                "that consumption would be left attached to a job claiming nothing happened. "
                "Complete and close it, or post a stock adjustment to return the parts first.")
    return ""


def _transition(request, pk, *, from_statuses, to_status, action, verb, stamps=None, audit=None,
                message=None, precheck=None):
    """Guard, stamp, audit, redirect — the shape every plain status verb in this file shares.

    ``action`` and ``verb`` are two different things and both are needed. ``action`` is the SLUG the
    audit row is keyed on (``approve`` / ``hold`` / …), matching 4.12's trail so the log stays
    filterable — ``"put on hold"`` as an ``action`` value is a sentence, not a key, and it would be
    the only entry in the whole application nobody could query for. ``verb`` is the past participle
    the two human messages read with ("… cannot be started", "MWO-00001 started.").

    The row is taken ``FOR UPDATE`` and its status re-read INSIDE ``transaction.atomic()``: two
    concurrent POSTs (a double-click, a retry, a replay) would otherwise both see ``in_progress`` and
    each stamp ``completed_at``, and the second stamp is the one that survives. The object is
    resolved BEFORE the status guard so a cross-tenant pk answers 404 rather than a 302 that leaks
    "there is a row there, you just cannot move it" (the 4.12 finding).

    ``save(update_fields=…)`` is narrow on purpose — a full ``save()`` here would write back every
    in-memory column, including any a concurrent edit had just changed. ``updated_at`` is
    ``auto_now``, so it only fires when it is IN the list.
    """
    with transaction.atomic():
        obj = get_object_or_404(MaintenanceWorkOrder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"{obj.number} cannot be {verb} — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        # Cross-ROW guards belong here, inside the lock — not in the caller before it.
        #
        # `select_for_update()` above protects this row's own columns, but a guard that reads a
        # CHILD table (a part line's `is_issued`) is a plain snapshot read: run before the lock, it
        # answers about the state the transaction started in, and the write then simply waits for
        # the lock and lands the moment the competing transaction commits. That is not a narrow
        # window either — `_issue_parts` holds this row locked for its whole per-line loop, so an
        # attacker firing issue-parts and cancel back to back wins it reliably. The end state was a
        # `cancelled` job carrying posted `maintenance` StockMoves: `Asset._jobs()` excludes
        # cancelled jobs, so the consumption vanished from maintenance_cost_to_date(), from the
        # repair-vs-replace ratio and from MTTR/MTBF, while the stock was genuinely gone.
        if precheck is not None:
            refusal = precheck(obj)
            if refusal:
                messages.error(request, refusal)
                return _detail(pk)

        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamps or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))

    write_audit_log(request.user, obj, "update",
                    {"action": action, "status": to_status, **(audit or {})})
    messages.success(request, message or f"{obj.number} {verb}.")
    return _detail(pk)


# ======================================================================================= the list
@login_required
def maintenanceworkorder_list(request):
    """Search + seven filters + a reported-on window over the workspace's maintenance jobs.

    ``select_related`` covers the four FKs a row renders; without it a page of 15 jobs is up to 60
    extra queries for four columns. The cost column comes from :func:`_with_costs`, never from
    ``total_cost`` — see there.

    The reported-on window goes through the SHARED ``_date_window`` helper (via
    :func:`_reported_window`, which only normalises the two ends for a datetime column — see there),
    never a second copy: junk input SKIPS the filter rather than raising. Every int-valued param goes
    through ``crud_list``'s ``is_int=True`` leg, so ``?asset=abc``, ``?asset=²`` and
    ``?asset=99999999999999999999`` all skip the filter instead of 500-ing (L11).

    The window is applied BEFORE ``crud_list`` paginates, like every other filter here — one applied
    afterwards would page over the unfiltered set and quietly show the wrong rows on page 2.
    """
    qs = (MaintenanceWorkOrder.objects.filter(tenant=request.tenant)
          .select_related("asset", "plan", "assigned_to", "parts_location"))
    qs = _reported_window(qs, request.GET)
    qs = _with_costs(qs)

    # ONE aggregate for all five header chips, over the WHOLE workspace rather than the filtered
    # page: "4 jobs on hold" is a workspace fact somebody has to act on, and recomputing it per
    # filter would make the number change as you browse. `unplanned_downtime_minutes` is a Sum and
    # is None — never 0 — when nothing has ever been recorded, because a zero in a tile reads as a
    # measurement while a blank makes someone go and look (the 4.11 lesson).
    stats = MaintenanceWorkOrder.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=MaintenanceWorkOrder.OPEN_STATUSES)),
        in_progress=Count("id", filter=Q(status="in_progress")),
        on_hold=Count("id", filter=Q(status="on_hold")),
        down_now=Count("id", filter=Q(status__in=MaintenanceWorkOrder.OPEN_STATUSES,
                                      downtime_start__isnull=False, downtime_end__isnull=True)),
        unplanned_downtime_minutes=Sum("downtime_minutes", filter=Q(is_unplanned_downtime=True)),
    )

    return crud_list(
        request, qs, "scm/assets/maintenanceworkorder/list.html",
        # `asset__code` / `asset__name` are forward-FK joins, so they narrow rows without ever
        # multiplying them — which is what keeps the parts SUM above honest under a search.
        search_fields=["number", "title", "description", "asset__code", "asset__name"],
        filters=[("status", "status", False), ("work_type", "work_type", False),
                 ("priority", "priority", False), ("problem_code", "problem_code", False),
                 ("asset", "asset_id", True), ("assigned_to", "assigned_to_id", True)],
        extra_context={
            "status_choices": MaintenanceWorkOrder.STATUS_CHOICES,
            "work_type_choices": WORK_TYPE_CHOICES,
            "priority_choices": PRIORITY_CHOICES,
            "problem_code_choices": PROBLEM_CODE_CHOICES,
            # `Asset.__str__` is "code · name" off its own columns, so this dropdown owes no
            # select_related. Not narrowed to is_active: a retired machine still has job history
            # somebody filters for.
            "assets": Asset.objects.filter(tenant=request.tenant),
            "assignees": _employee_parties(request.tenant),
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def maintenanceworkorder_create(request):
    return _maintenanceworkorder_form(request, instance=None)


@login_required
def maintenanceworkorder_edit(request, pk):
    """Editable only while the job is OPEN.

    ``is_editable`` is the open statuses: a completed, closed or cancelled job is history, and
    editing one would silently restate a cost that has already been reported on the asset's
    ``maintenance_cost_to_date()`` and on the depreciation report's repair-vs-replace ratio.
    """
    obj = get_object_or_404(MaintenanceWorkOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited — a finished job is the record of what happened.")
        return _detail(pk)
    return _maintenanceworkorder_form(request, instance=obj)


def _maintenanceworkorder_form(request, instance):
    """Header + parts formset committed in ONE ``transaction.atomic()``.

    ``formset.instance = form.instance`` goes AFTER ``form.is_valid()`` and BEFORE
    ``formset.is_valid()`` (the ``_tradedocument_form`` rule): on create the formset's own instance
    is an empty ``MaintenanceWorkOrder()``, and the inline's ``work_order`` FK has to point at the
    header the form just built or ``formset.save()`` would attach the lines to nothing.

    The parts formset MUST be constructed with ``form_kwargs={"tenant": request.tenant}``:
    ``MaintenanceWorkOrderPart`` carries no ``tenant`` column, so nothing about being an inline of a
    tenant-scoped parent narrows its ``item`` / ``lot_serial`` dropdowns — the scoping lives in
    ``MaintenanceWorkOrderPartForm.__init__`` and only fires when the tenant is handed to it.

    This path bypasses ``crud_edit`` (so header and lines commit together), which means the audit row
    it would have written has to be written by hand — with ``_changed(form)``, never a second copy of
    the redaction list.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:maintenanceworkorder_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = MaintenanceWorkOrderForm(request.POST, request.FILES, instance=instance,
                                        tenant=request.tenant)
        formset = MaintenanceWorkOrderPartFormSet(request.POST, instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance   # <- load-bearing; see the docstring
        if form_ok and formset.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                formset.instance = obj
                formset.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{obj.number} saved.")
            return _detail(obj.pk)
    else:
        form = MaintenanceWorkOrderForm(instance=instance, tenant=request.tenant)
        formset = MaintenanceWorkOrderPartFormSet(instance=instance,
                                                  form_kwargs={"tenant": request.tenant})
    return render(request, "scm/assets/maintenanceworkorder/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def maintenanceworkorder_detail(request, pk):
    """The job, its parts, its checklist, the ledger rows it wrote and the meters it captured.

    ``parts`` and ``tasks`` are PREFETCHED, which is what makes ``obj.parts_cost`` /
    ``obj.total_cost`` / ``obj.open_task_count`` free here — each of those walks ``.all()`` and reads
    the cache this page has already paid for, exactly as their docstrings promise. Passing the three
    figures through the context as well means the template never has to know that.
    """
    obj = get_object_or_404(
        MaintenanceWorkOrder.objects
        .select_related("asset", "asset__location", "asset__work_center", "plan", "reported_by",
                        "assigned_to", "service_vendor", "parts_location", "non_conformance")
        .prefetch_related(
            # `LotSerial.__str__` dereferences `item.sku`, so stopping one hop short is a query per
            # part line (L18) — and the parts table is exactly what this page is for.
            Prefetch("parts", queryset=(MaintenanceWorkOrderPart.objects
                                        .select_related("item", "lot_serial__item"))),
            "tasks"),
        pk=pk, tenant=request.tenant)

    parts = list(obj.parts.all())
    tasks = list(obj.tasks.all())
    issued_part_count = sum(1 for part in parts if part.is_issued)

    return render(request, "scm/assets/maintenanceworkorder/detail.html", {
        "obj": obj,
        "parts": parts,
        "tasks": tasks,
        # `reference` is the only link StockMove keeps back to its source document — the transfer,
        # GRN and 4.8 work-order detail pages all read the ledger the same way.
        "moves": list(StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                      .select_related("item", "location", "lot_serial")[:MAX_PANEL_ROWS]),
        # The captures filed against this job: one from the complete verb, plus any the record verb
        # took while it was open. Scoped on the tenant AND the asset, never on `reference` alone.
        "readings": list(MeterReading.objects.filter(tenant=request.tenant, asset_id=obj.asset_id,
                                                     reference=obj.number)
                         .select_related("recorded_by")[:MAX_PANEL_ROWS]),
        "parts_cost": obj.parts_cost,
        "labour_cost": obj.labour_cost,
        "total_cost": obj.total_cost,
        # Both None — never 0 / False — while unanswerable. An in-flight repair counted as zero hours
        # would flatter every MTTR figure that reads it, and a never-scheduled job counted as "late"
        # would be a miss nobody committed to.
        "duration_hours": obj.duration_hours,
        "is_on_time": obj.is_on_time,
        "open_task_count": obj.open_task_count,
        "issued_part_count": issued_part_count,
        "unissued_part_count": len(parts) - issued_part_count,
        "has_issued_parts": issued_part_count > 0,
        "can_edit": obj.is_editable,
        # Exactly the condition `maintenanceworkorder_delete` enforces — offering a one-click failure
        # is worse than not offering the button (the 4.12 rule).
        "can_delete": obj.is_editable and issued_part_count == 0,
        "can_approve": obj.status in APPROVABLE_STATUSES,
        "can_schedule": obj.status in SCHEDULABLE_STATUSES,
        "can_start": obj.status in STARTABLE_STATUSES,
        "can_hold": obj.status in HOLDABLE_STATUSES,
        "can_resume": obj.status in RESUMABLE_STATUSES,
        "can_complete": obj.status in COMPLETABLE_STATUSES,
        "can_close": obj.status in CLOSABLE_STATUSES,
        "can_cancel": obj.status in CANCELLABLE_STATUSES and issued_part_count == 0,
        "can_issue_parts": (obj.status in ISSUABLE_STATUSES
                            and obj.parts_location_id is not None
                            and issued_part_count < len(parts)),
        "can_record_reading": obj.status in READABLE_STATUSES and bool(obj.asset.meter_name),
        # Say WHY the issue button is unavailable rather than just hiding it.
        "parts_location_missing": obj.parts_location_id is None,
        "asset_meter_name": obj.asset.meter_name,
        "asset_meter_unit": obj.asset.meter_unit,
    })


@tenant_admin_required
@require_POST
def maintenanceworkorder_delete(request, pk):
    """Delete a job — refused once it is terminal, and refused once any part has been issued.

    A completed / closed / cancelled job is the record of what happened to the machine: it feeds
    MTTR, MTBF, availability and the asset's maintenance cost to date, and losing it must not be one
    click away. Cancel an open job instead — a cancelled job keeps its history and is excluded from
    the reliability figures by ``Asset._jobs()``.

    An issued part is a posted ``StockMove``. Deleting its job would leave that movement standing in
    an append-only ledger with nothing to explain it and would silently drop the cost off three
    pages, so it is refused here for the same reason ``BaseMaintenanceWorkOrderPartFormSet`` refuses
    to remove an issued line. The ledger is corrected with a stock adjustment, never by deletion.
    """
    # Hand-rolled rather than delegated to crud_delete, and the reason is the whole point of this
    # view: crud_delete re-fetches the row by pk WITHOUT a lock and re-checks neither guard, because
    # it cannot know about guards it was never told about. Both guards below were therefore
    # advisory — read from an unlocked snapshot, they answered about the state this request started
    # in, and the DELETE then waited on the lock and executed anyway.
    #
    # The loss was irreversible in a way the other TOCTOU sites are not. MaintenanceWorkOrderPart is
    # CASCADE, so deleting the job destroyed the record of WHAT was drawn and AT WHAT COST, while
    # the negative `maintenance` StockMove rows survived in the append-only ledger pointing at a
    # document that no longer existed — unreconstructable from anything, and silently gone from
    # maintenance_cost_to_date(), the depreciation report and the parts panel.
    with transaction.atomic():
        obj = get_object_or_404(MaintenanceWorkOrder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and cannot "
                                    "be deleted — a finished job is history. Cancel an open job "
                                    "instead.")
            return _detail(pk)
        # Exists-shaped, not a Count: the page only asks "are there any?" (views/_common.py:20-23).
        if obj.parts.filter(is_issued=True).exists():
            messages.error(request, f"{obj.number} has parts already issued from stock and cannot "
                                    "be deleted — the ledger movement would be left with nothing "
                                    "to explain it. Cancel the job, or post a stock adjustment to "
                                    "return the parts first.")
            return _detail(pk)
        # Inside the transaction so it rolls back with a failed delete rather than recording a
        # deletion that did not happen.
        write_audit_log(request.user, obj, "delete")
        number = obj.number
        obj.delete()
    messages.success(request, f"{number} deleted.")
    return redirect("scm:maintenanceworkorder_list")


# ============================================================ the ladder (no stock effect below)
@tenant_admin_required
@require_POST
def maintenanceworkorder_approve(request, pk):
    """requested -> approved. Admin-gated: approving is what commits somebody's time and money."""
    return _transition(request, pk, from_statuses=APPROVABLE_STATUSES, to_status="approved",
                       action="approve", verb="approved")


@login_required
@require_POST
def maintenanceworkorder_schedule(request, pk):
    """approved | scheduled -> scheduled, committing (or moving) the date the job is measured against.

    ``scheduled_start`` is what ``is_on_time`` compares ``completed_at`` to, and it is snapshotted
    onto the job at generate time for exactly that reason — so a job put into ``scheduled`` with no
    date is a commitment to nothing and every PM-compliance figure that reads it goes unanswerable.
    A posted value replaces whatever is there (rescheduling is the normal case); with nothing posted
    and nothing stored, this refuses.
    """
    raw = (request.POST.get("scheduled_start") or "").strip()
    moment = _posted_moment(raw)
    if raw and moment is None:
        messages.error(request, "That is not a date and time — enter the scheduled start as "
                                "YYYY-MM-DD or YYYY-MM-DD HH:MM.")
        return _detail(pk)

    with transaction.atomic():
        # Resolved BEFORE the "no date at all" guard, so a POST to another workspace's pk is a 404
        # rather than a 302 that confirms the row exists (the 4.12 finding).
        obj = get_object_or_404(MaintenanceWorkOrder.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in SCHEDULABLE_STATUSES:
            messages.error(request, f"{obj.number} cannot be scheduled — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        if moment is None and obj.scheduled_start is None:
            messages.error(request, "Give the scheduled start — it is the date this job's on-time "
                                    "performance is measured against.")
            return _detail(pk)

        before = obj.scheduled_start
        fields = ["status", "updated_at"]
        obj.status = "scheduled"
        if moment is not None:
            obj.scheduled_start = moment
            fields.append("scheduled_start")
        obj.save(update_fields=fields)

    write_audit_log(request.user, obj, "update", {
        "action": "schedule", "status": "scheduled",
        "scheduled_start": [str(before) if before else None, str(obj.scheduled_start)]})
    messages.success(request, f"{obj.number} scheduled for "
                              f"{timezone.localtime(obj.scheduled_start):%d %b %Y %H:%M}.")
    return _detail(pk)


@login_required
@require_POST
def maintenanceworkorder_start(request, pk):
    """approved | scheduled -> in_progress, stamping ``started_at``.

    The stamp is unconditional because this is the only route into ``in_progress`` from below —
    ``resume`` comes back from ``on_hold`` and deliberately does NOT re-stamp, so the duration a job
    actually took is measured from when work first began, not from the last coffee break.
    """
    return _transition(request, pk, from_statuses=STARTABLE_STATUSES, to_status="in_progress",
                       action="start", verb="started",
                       stamps={"started_at": timezone.now()})


@login_required
@require_POST
def maintenanceworkorder_hold(request, pk):
    """in_progress -> on_hold. Waiting on a part, a permit, a shutdown window or a contractor.

    The reason is optional and lands in the audit row rather than on the document: it is a note about
    a moment, and writing it onto ``resolution_notes`` would overwrite what the technician eventually
    says they DID.
    """
    reason = (request.POST.get("reason") or "").strip()
    return _transition(request, pk, from_statuses=HOLDABLE_STATUSES, to_status="on_hold",
                       action="hold", verb="put on hold",
                       audit={"reason": reason[:200]} if reason else None)


@login_required
@require_POST
def maintenanceworkorder_resume(request, pk):
    """on_hold -> in_progress. ``started_at`` is NOT re-stamped — see :func:`..._start`."""
    return _transition(request, pk, from_statuses=RESUMABLE_STATUSES, to_status="in_progress",
                       action="resume", verb="resumed")


@login_required
@require_POST
def maintenanceworkorder_complete(request, pk):
    """in_progress -> completed, and the one verb with side effects beyond its own row.

    Three things happen, all inside ONE locked transaction:

    1. ``completed_at`` is stamped, and an optional ``resolution_notes`` from the POST is stored.
       The field is collected here because ``is_editable`` is the open statuses only — the moment
       this verb lands, the edit form can no longer reach it, and completion is exactly when the
       technician has something to write.
    2. If the job came from a ``MaintenancePlan``, that plan's ``last_completed_on`` is stamped and
       :meth:`MaintenancePlan.advance` rolls the schedule forward by exactly ONE cycle. ``advance``
       returns the FIELD NAMES it wrote and does not save; they are folded into this caller's own
       ``update_fields`` so the stamp and the roll are one round trip. The date arithmetic
       (floating vs fixed, calendar vs meter) lives there and only there.
    3. If ``meter_reading_at_work`` was captured, it becomes a ``MeterReading`` row with
       ``source="work_order"`` and ``reference=<this number>`` — the reading log stays the single
       place a meter is ever read from, and this column stays a capture field that nothing reads.

    **Filed exactly once.** The status guard is re-read INSIDE ``select_for_update()``, and the only
    transition into ``completed`` is from ``in_progress`` with no route back, so the second POST of a
    double-submit is refused before it reaches any of the three steps. That is the guard — not a
    dedupe query that would also have to guess whether a reading the record-reading verb filed
    earlier "counts".
    """
    notes = (request.POST.get("resolution_notes") or "").strip()
    filed_reading = False
    meter_skipped = ""
    plan_rolled, plan_message = [], ""

    with transaction.atomic():
        obj = get_object_or_404(
            MaintenanceWorkOrder.objects.select_for_update().select_related("asset"),
            pk=pk, tenant=request.tenant)
        if obj.status not in COMPLETABLE_STATUSES:
            messages.error(request, f"{obj.number} cannot be completed — it is "
                                    f"{obj.get_status_display().lower()}."
                                    + (" Resume it first." if obj.status == "on_hold" else ""))
            return _detail(pk)

        stamped_at = timezone.now()
        fields = ["status", "completed_at", "updated_at"]
        obj.status = "completed"
        obj.completed_at = stamped_at
        if notes:
            obj.resolution_notes = notes
            fields.append("resolution_notes")
        obj.save(update_fields=fields)

        # --- the meter capture --------------------------------------------------------------------
        # Filed BEFORE the plan roll, and the order is load-bearing: `advance()` on a *floating*
        # meter plan takes its base from `plan.latest_reading()` (MaintenancePlans.py:445), so a
        # capture filed afterwards is invisible to the very roll it should drive. Measured on a
        # forklift last read at 1218.5h completed with a 1250h capture and a 250h interval: the roll
        # published 1468.5 instead of 1500 — the next service falling 31.5h early, every cycle,
        # compounding.
        #
        # `meter_name` is required on MeterReading and blank on an asset that declares no meter, so
        # a capture against such an asset cannot be filed. That is said out loud rather than saved
        # under an invented name — a reading nobody can identify is worse than no reading.
        if obj.meter_reading_at_work is not None:
            if obj.asset.meter_name:
                MeterReading.objects.create(
                    tenant=request.tenant, asset=obj.asset,
                    recorded_by=_acting_party(request),
                    meter_name=obj.asset.meter_name, unit=obj.asset.meter_unit,
                    # Already bounded by the form's MaxValueValidator(MAX_Q4); q4 clamps anyway so a
                    # seeded or imported job can never fail the whole atomic block on one column.
                    reading=q4(obj.meter_reading_at_work),
                    read_at=stamped_at, source="work_order", reference=obj.number,
                    notes=f"Captured on completion of {obj.number}"[:255])
                filed_reading = True
            else:
                meter_skipped = (f"{obj.asset} names no meter, so the captured reading "
                                 f"({obj.meter_reading_at_work}) was not filed. Set the asset's "
                                 "meter name and log the reading from the asset page.")

        # --- the plan roll ------------------------------------------------------------------------
        # This verb is the ONLY caller of `advance()` — the published schedule has exactly one
        # writer, the same rule `Asset.status` and `downtime_minutes` follow. `maintenanceplan_
        # generate` deliberately does not roll: it would advance a `fixed` plan twice per occurrence
        # (advance() anchors a fixed plan on its own `next_due_on`, so the calls compound), it would
        # anchor a `floating` plan on the generate date rather than the completion it is defined to
        # measure from, and it would let a cancelled job consume a cycle nobody performed.
        #
        # Locked SECOND and always second, one direction for every route in this file, so two
        # concurrent completions on one plan serialise instead of deadlocking. Re-fetched with an
        # explicit tenant filter rather than followed off `obj.plan`: a plan whose row went away (or
        # was re-pointed) must degrade to "no roll", never to a cross-tenant write.
        if obj.plan_id:
            plan = (MaintenancePlan.objects.select_for_update()
                    .filter(pk=obj.plan_id, tenant=request.tenant).first())
            if plan is not None:
                completed_on = timezone.localdate(stamped_at)
                plan.last_completed_on = completed_on
                # advance() returns the names it wrote and saves nothing by default — folded into
                # ONE save with our own stamp, which is the contract its docstring states.
                plan_rolled = plan.advance(from_date=completed_on)
                plan.save(update_fields=list(dict.fromkeys(
                    ["last_completed_on", "updated_at"] + plan_rolled)))
                # Rendered HERE, inside the lock, rather than re-fetching the plan afterwards just
                # to build a sentence: the message then describes the state this transaction
                # actually wrote, and the page costs one query fewer.
                if plan_rolled:
                    plan_message = (f"{plan.number} rolled forward — next due "
                                    f"{plan.next_due_on or plan.next_due_reading}.")

    write_audit_log(request.user, obj, "update", {
        "action": "complete", "status": "completed",
        "resolution_notes": "set" if notes else "unchanged",
        "plan_advanced": plan_rolled or None,
        "meter_reading_filed": filed_reading,
    })
    messages.success(request, f"{obj.number} completed.")
    if plan_message:
        messages.info(request, plan_message)
    if filed_reading:
        messages.info(request, f"Meter reading {obj.meter_reading_at_work} "
                               f"{obj.asset.meter_unit} filed against {obj.asset.meter_name}.")
    if meter_skipped:
        messages.warning(request, meter_skipped)
    return _detail(pk)


@login_required
@require_POST
def maintenanceworkorder_close(request, pk):
    """completed -> closed: reviewed, costed, and now history.

    ``completed`` and ``closed`` are kept apart deliberately — that is what lets a supervisor find
    "finished but not yet signed off" without a second flag.
    """
    return _transition(request, pk, from_statuses=CLOSABLE_STATUSES, to_status="closed",
                       action="close", verb="closed")


@tenant_admin_required
@require_POST
def maintenanceworkorder_cancel(request, pk):
    """Any OPEN status -> cancelled. Admin-gated, and refused once parts have been issued.

    A job with a posted ``maintenance`` ``StockMove`` against it is NOT cancellable: the parts are
    gone from stock, and cancelling would attach that consumption to a document claiming nothing
    happened — while ``Asset._jobs()`` excludes cancelled jobs from every reliability figure, so the
    outage would vanish from MTTR and MTBF too. Complete and close it instead, or post a stock
    adjustment to return the parts first. Exactly the 4.8 ``workorder_cancel`` posture, and the same
    reasoning that makes ``StockMove`` append-only.
    """
    reason = (request.POST.get("reason") or "").strip()
    # Handed to _transition as a precheck so it runs INSIDE the row lock. Read here, before the
    # lock, it was advisory: a concurrent _issue_parts committed in the gap and the cancel landed
    # anyway. See _transition's precheck block for what that produced.
    return _transition(request, pk, from_statuses=CANCELLABLE_STATUSES, to_status="cancelled",
                       action="cancel", verb="cancelled", precheck=_issued_parts_refusal,
                       audit={"reason": reason[:200]} if reason else None)


# ============================================================= the posting (this moves stock)
@tenant_admin_required
@require_POST
def maintenanceworkorder_issue_parts(request, pk):
    """Draw every un-issued part line out of the job's storeroom. **The only ledger write in 4.13.**

    One negative ``maintenance`` ``StockMove`` per line, posted through the SHARED
    ``_post_stock_move`` service so on-hand stays a pure aggregate of one append-only ledger. It
    posts **no ``JournalEntry``** — the standing L29 rule; a GL hand-off, if ever wanted, follows
    4.6's freight pattern of drafting an ``accounting.Bill``.

    **Refused outright without a ``parts_location``.** There is no sensible default: guessing a
    storeroom would draw stock out of a location that never held it, and the tenant-wide figure would
    stay balanced while the real holding bin was never debited (the ``_insufficient_stock`` security
    finding, one level up).

    **A shortfall is a MESSAGE, not an exception.** ``_insufficient_stock`` is called BEFORE the move
    for every line; a line the storeroom cannot cover is named and SKIPPED while the rest are issued,
    because refusing an eight-line issue over one missing washer helps nobody. The check reflects
    moves already posted by earlier lines in this same transaction, so two lines for one item cannot
    together overdraw the bin.

    ``_shared_items`` gives every line ONE ``Item`` instance: ``select_related("item")`` hands back a
    SEPARATE object per row, and two lines naming the same part would each read their own stale
    ``average_cost``. ``unit_cost`` is stamped from that cost AT ISSUE TIME and never re-read — the
    job's cost has to be what the stock actually cost when it was drawn.
    """
    posted, blocked, issued_value = 0, [], ZERO
    with transaction.atomic():
        obj = get_object_or_404(
            MaintenanceWorkOrder.objects.select_for_update().select_related("parts_location"),
            pk=pk, tenant=request.tenant)
        if obj.status not in ISSUABLE_STATUSES:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — parts "
                                    "can only be issued while the job is still open.")
            return _detail(pk)
        if obj.parts_location_id is None:
            messages.error(request, f"{obj.number} has no storeroom set, so there is nowhere to draw "
                                    "the parts from. Edit the job and set the parts location first.")
            return _detail(pk)

        # `is_issued` is re-read inside the lock, which is what makes a double POST idempotent: the
        # second one finds every line already flagged and posts nothing.
        lines = list(obj.parts.filter(is_issued=False).select_related("item", "lot_serial"))
        items = _shared_items(lines)
        stamp = timezone.now()
        for line in lines:
            item = items[line.item_id]
            shortfall = _insufficient_stock(item, obj.parts_location, line.quantity,
                                            line.lot_serial)
            if shortfall:
                blocked.append(shortfall)
                continue
            cost = item.average_cost or ZERO
            _post_stock_move(obj.tenant, item=item, location=obj.parts_location,
                             quantity=-line.quantity, move_type="maintenance", unit_cost=cost,
                             lot_serial=line.lot_serial, reference=obj.number,
                             reason="Maintenance issue", moved_at=stamp)
            line.unit_cost = q4(cost)
            line.is_issued = True
            line.issued_at = stamp
            # No `updated_at` in the list: MaintenanceWorkOrderPart is a plain child model and has
            # no timestamps of its own.
            line.save(update_fields=["unit_cost", "is_issued", "issued_at"])
            issued_value += line.line_cost
            posted += 1

    if not posted:
        for shortfall in blocked:
            messages.error(request, shortfall)
        if not blocked:
            messages.info(request, f"Every part line on {obj.number} has already been issued."
                          if obj.parts.exists() else
                          f"{obj.number} has no part lines to issue — add them on the edit form.")
        return _detail(pk)

    write_audit_log(request.user, obj, "update", {
        "action": "issue_parts", "lines": posted, "value": str(issued_value),
        "location": obj.parts_location.code, "skipped": len(blocked)})
    messages.success(request, f"Issued {posted} part line(s) worth {issued_value} to {obj.number} "
                              f"from {obj.parts_location.code}.")
    for shortfall in blocked:
        messages.warning(request, f"Not issued — {shortfall}")
    return _detail(pk)


# ================================================================================ meters and tasks
@login_required
@require_POST
def maintenanceworkorder_record_reading(request, pk):
    """File a meter reading against this job's asset, without waiting for completion.

    Routed through ``MeterReadingForm`` rather than a bare ``objects.create``, which is what its own
    docstring anticipates: the form carries the tenant guard on ``asset``, the bounds on ``reading``
    and the refusal of a future ``read_at``, and duplicating any of those here would be a second
    implementation that drifts.

    ``asset``, ``source`` and ``reference`` are FORCED from the work order and never taken from the
    POST — the reading is a fact about THIS job's machine, and letting a caller name the asset would
    make a tenant-scoped dropdown the only thing standing between a crafted POST and another
    workspace's meter history.

    ``recorded_by`` is stamped on the object returned by ``save(commit=False)``, AFTER validation:
    ``MeterReading.clean()`` tenant-checks that FK, and a model error keyed on a column the FORM does
    not have raises ``ValueError`` out of ``Form.add_error`` — a 500 instead of a field error.
    """
    obj = get_object_or_404(MaintenanceWorkOrder.objects.select_related("asset"),
                            pk=pk, tenant=request.tenant)
    if obj.status not in READABLE_STATUSES:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — a reading "
                                "cannot be attached to a job that is already history. Log it from "
                                "the asset page instead.")
        return _detail(pk)

    data = {
        "asset": str(obj.asset_id),
        "meter_name": (request.POST.get("meter_name") or obj.asset.meter_name or "").strip(),
        "unit": (request.POST.get("unit") or obj.asset.meter_unit or "").strip(),
        "reading": (request.POST.get("reading") or "").strip(),
        # A blank read_at would be a required-field error: the column has a default, but `blank` is
        # False so the FORM field is required. Formatted in local time because forms.DateTimeField
        # localises a naive value on the way in, and truncating the microseconds keeps it a hair
        # behind `now()` so MeterReading.clean()'s no-future-dates rule cannot trip on itself.
        "read_at": (request.POST.get("read_at")
                    or timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")),
        # `source` / `reference` are NOT here: they are provenance and are no longer form fields at
        # all (leaving them on the form let a member forge a verb-filed reading onto any job). They
        # are stamped on the instance below, after validation, exactly like `recorded_by`.
        "notes": (request.POST.get("notes") or "").strip()[:255],
    }
    form = MeterReadingForm(data, tenant=request.tenant)
    if not form.is_valid():
        for field, errors in form.errors.items():
            messages.error(request, f"{field}: {' '.join(errors)}")
        return _detail(pk)

    reading = form.save(commit=False)
    reading.tenant = request.tenant
    reading.recorded_by = _acting_party(request)   # AFTER is_valid() — see the docstring
    # Provenance, stamped by the verb that is actually filing this reading rather than accepted from
    # the request. These two are what the job's readings panel selects on, so a user able to type
    # them could attribute a hand-typed number to a work order they never touched.
    reading.source = "work_order"
    reading.reference = obj.number
    reading.save()
    write_audit_log(request.user, reading, "create",
                    {"action": "record_reading", "work_order": obj.number,
                     "meter_name": reading.meter_name, "reading": str(reading.reading)})
    messages.success(request, f"Recorded {reading.meter_name} {reading.reading} "
                              f"{reading.unit} on {obj.asset} against {obj.number}.")
    return _detail(pk)


@login_required
@require_POST
def maintenanceworkordertask_toggle(request, pk):
    """Tick or untick one checklist step, stamping (or clearing) ``completed_at``.

    ``MaintenanceWorkOrderTask`` carries **no tenant column** — it is a pure child, reached through
    ``work_order__tenant``. Resolving it on ``pk`` alone would be a cross-tenant write with no query
    anywhere that would reveal it, so the parent join IS the authorization check here.

    ``completed_at`` is stamped by this route and never typed (L22): the tick is the event, so the
    time of the tick is not something a user should be able to disagree with. Unticking clears it
    rather than leaving a completion time on a step that is no longer complete.

    Refused once the job is terminal: the checklist on a finished job is evidence of what was
    actually signed off, and the whole reason ``MaintenanceWorkOrderTask`` is a SNAPSHOT with no FK
    back to the plan is that a completed record must not be mutable after the fact.
    """
    task = get_object_or_404(
        MaintenanceWorkOrderTask.objects.select_related("work_order"),
        pk=pk, work_order__tenant=request.tenant)
    order = task.work_order
    if order.status in MaintenanceWorkOrder.CLOSED_STATUSES:
        messages.error(request, f"{order.number} is {order.get_status_display().lower()} — its "
                                "checklist is the record of what was signed off and can no longer "
                                "be changed.")
        return _detail(order.pk)

    task.is_done = not task.is_done
    task.completed_at = timezone.now() if task.is_done else None
    fields = ["is_done", "completed_at"]
    # Present-but-empty is a deliberate clear; absent leaves whatever is stored alone.
    if "actual_result" in request.POST:
        task.actual_result = (request.POST.get("actual_result") or "").strip()[:255]
        fields.append("actual_result")
    task.save(update_fields=fields)

    # Audited against the TASK (that is the row that moved) with an explicit tenant: the child has no
    # tenant attribute, so write_audit_log would otherwise fall back to the user's and file the entry
    # under the wrong workspace for a superuser.
    write_audit_log(request.user, task, "update", {
        "action": "toggle_task", "work_order": order.number, "sequence": task.sequence,
        "is_done": task.is_done}, tenant=request.tenant)
    messages.success(request, f"Step {task.sequence} "
                              f"{'ticked' if task.is_done else 'un-ticked'} on {order.number}.")
    return _detail(order.pk)

"""SCM 4.14 Labor Management — ``LaborSession`` views: the shift ladder and the self-service punch.

**One table, one form, six verbs, and a status column no form can reach.** ``status`` is
``editable=False`` and absent from ``Meta.fields``, so the ONLY thing that moves it is a verb below,
each of which validates the transition it is making. A crafted ``status=approved`` in a POST body
cannot land — not because a view screens for it, but because there is no path from form data to the
column at all. That matters more here than on most documents: ``approved`` IS the payroll export's
lock, and the export reads approved sessions and nothing else.

**The ladder, stated once** (the module constants below are what BOTH the guard inside each verb and
the ``can_*`` flag handed to the detail page read, so a button and the route behind it cannot
disagree — the 4.10 "two of three shapes" finding)::

    (nothing) --clock-in--> open --close--> closed --approve--> approved
                             |                 \\                  |
                             |                  \\---- reopen -----/
                             |                   \\--> open <-----/
                             +--clock-out--> (still open, clock_out stamped)
    open | closed --cancel--> cancelled

Three things about that shape are decisions rather than accidents:

* **``clock_out`` does NOT move the status.** Stamping the punch and freezing the record are two
  different events: the shift ends on the floor, and the supervisor is still entering the last
  activity rows for ten minutes afterwards. ``open`` is the only status
  :class:`~apps.scm.models.LaborActivity` will write into, so folding the two together would mean
  every forgotten booking needed an admin ``reopen`` to add.
* **``reopen`` accepts ``closed`` as well as ``approved``**, and it is ``@tenant_admin_required``
  for the ``approved`` case: reopening a signed-off shift un-freezes minutes that the payroll export
  has already been able to see. It refuses when the worker has ANOTHER open session, which is the
  model's own one-open-session-per-worker rule (``LaborSession.clean()`` rule (e)) restated where a
  ``save(update_fields=…)`` would otherwise slip past it.
* **``cancel`` does NOT accept ``approved``.** Withdrawing a shift that has been signed off is a
  two-step move on purpose — reopen it (audited, admin-only) and then cancel it — so "this was
  cancelled after approval" is a fact readable off the audit trail instead of a guess.

**Every verb is ``@require_POST`` and locks its row.** Each opens ``transaction.atomic()``, takes the
session ``FOR UPDATE`` and re-reads its status INSIDE the lock, so a double-click, a retry or a
replay cannot stamp ``approved_at`` twice or clock one shift out at two different times. This is the
shape 4.3's ``stocktransfer_complete`` established and 4.8/4.12/4.13 kept; do not simplify it away.
An illegal move is a ``messages.error`` + redirect, never a 500 and never a silent no-op — and a
cross-tenant pk is resolved (and 404s) BEFORE any guard can answer 302, which is the 4.12 finding
priced in advance.

**4.14 writes no ``StockMove`` and no ``JournalEntry``, and this module writes nothing outside its
own table** (the standing L29 rule). It also carries **zero ``hrm.*`` references**: ``hrm`` owns
daily attendance, timesheets and pay, and these are warehouse-shift EXECUTION records that reconcile
with it on ``(worker, work_date)`` and a human eye. The payroll hand-off is a CSV on another page.

**Provenance is stamped by whichever code path files the session, never typed** (L20/L22, the 4.13
``MeterReading`` fix applied at the point of design). Two paths file a session and they stamp
differently, which is the entire reason ``source`` exists:

* :func:`laborsession_clock_in` — the worker punching themselves in. ``worker`` comes from
  ``_acting_party(request)`` and NEVER from the POST body, ``login`` is ``request.user``, and
  ``source`` is ``"web"``. Nothing in the request can name a different worker.
* :func:`_laborsession_form` — a supervisor keying a shift in after the fact, which is the ordinary
  case for a floor associate with no ERP login at all. ``source`` is ``"supervisor"`` and ``login``
  stays null, because nobody punched anything. ``recorded_by`` names the real user on both paths.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):

* ``scm/labor/laborsession/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from ``crud_list``),
  with ``activities`` PREFETCHED on every row so ``{{ obj.booked_minutes }}`` /
  ``{{ obj.unaccounted_minutes }}`` / ``{{ obj.utilisation_pct }}`` are free to print (see
  :func:`laborsession_list`). Filter context: ``status_choices`` and ``gap_choices`` (lists of
  ``(value, label)`` pairs), ``gap`` (the RESOLVED gap-filter value, ``""`` when absent or junk —
  bind the select to this, never to ``request.GET.gap``), ``workers`` (a ``core.Party`` queryset)
  and ``locations`` (a ``Location`` queryset). Header chips: ``stats``, a dict with keys ``open`` /
  ``running`` / ``awaiting_approval`` / ``approved``, counted over the WHOLE workspace rather than
  the filtered page. Filter params: ``q`` / ``status`` / ``gap`` (strings — compare with
  ``request.GET.<param>`` directly, except ``gap``, which has the resolved variable above) and
  ``worker`` / ``location`` (pks — compare with ``o.pk|stringformat:"d"``, NEVER ``|slugify``), plus
  ``date_from`` / ``date_to`` on ``work_date``.
* ``scm/labor/laborsession/form.html`` — ``form``, ``is_edit`` and ``obj`` (``None`` on create).
* ``scm/labor/laborsession/detail.html`` — see :func:`laborsession_detail`'s docstring for the full
  key list; it is long enough to belong beside the code that builds it.

Badge colours come from the models: ``obj.status_css`` and ``activity.activity_css``.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css and render as
completely unstyled text (L33).

**Every derived figure this module hands over can be ``None``, and ``None`` is never ``0``.** A
running shift has no attended minutes, an unmeasured one has no performance, a shift of pure
indirect time has no accuracy. The template must print an em dash for each; a helpful ``0`` in a
tile is a confident, wrong measurement (the 4.11 lesson).

POST payloads the verb routes read (none of them takes a ``Form`` the template can render, so the
inputs are named here):

* ``labor-sessions/clock-in/`` — REQUIRED ``location`` (a pk); OPTIONAL ``shift_label`` and
  ``notes``. **No ``worker`` field** — see above; one would be ignored.
* ``<int:pk>/cancel/`` — OPTIONAL ``reason`` (recorded in the audit row only).
* the other four verbs take no payload at all.

``laborsession_delete``, ``_approve``, ``_reopen`` and ``_cancel`` are ``@tenant_admin_required``, so
wrap those four buttons in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` —
showing a member a button they will 403 on is the 4.11 finding.
"""
from datetime import timedelta

# Same import shape 4.13 uses — views/_common.py deliberately does not re-export the functions
# module, and the gap filter below needs Coalesce to be load-bearing rather than tidy (see there).
from django.db.models.functions import Coalesce

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_acting_party, _date_window, _location_qs, _need_tenant,
                                     _status_transition)
# Views legitimately depend on forms for the shared party querysets — the `_supplier_parties`
# precedent in views/_helpers.py. The `worker` filter dropdown must offer the same set the form's
# `worker` field offers, or the filter lists people the field cannot select.
from apps.scm.forms._common import _employee_parties

from apps.scm.forms import LaborSessionForm
# MAX_SESSION_MINUTES comes from `models/LaborManagement/_choices.py` via the models package's
# re-export, NOT from a hand-typed 2880: the clock-out verb below re-checks the same ceiling
# `LaborSession.clean()` enforces, and two copies of one bound are one edit away from a verb that
# stamps a session the form would then refuse to save.
from apps.scm.models import (LaborActivity, LaborSession, MAX_SESSION_MINUTES,
                             SESSION_STATUS_CHOICES)


# =================================================================================== the ladder
# Declared ONCE and read by BOTH the guard inside each verb and the `can_*` flag handed to the detail
# template, so a button and the route behind it can never disagree about whether an action is
# available (the 4.10 "two of three shapes" finding). See the module docstring for the diagram.

#: Clocking out is a punch on a live shift, and the verb additionally refuses one that already
#: carries a `clock_out` — correcting a mis-keyed punch is the edit form's job, not a second stamp.
CLOCK_OUT_STATUSES = ("open",)
#: Closing freezes the shift and its activities. Only from `open`, and only once the shift has
#: actually ended (the verb's precheck) — a closed session with no `clock_out` has no attended
#: minutes and never will, so every figure derived from it would answer "not yet" forever.
CLOSABLE_STATUSES = ("open",)
#: Approval is the export lock, so it acts on a shift that has already been frozen and reviewed.
#: Straight from `open` is deliberately NOT offered: `closed` is what makes "ended, not yet signed
#: off" a queue a supervisor can work through without a second flag.
APPROVABLE_STATUSES = ("closed",)
#: Reopen is the ONLY way back to writable, from either frozen state. See the module docstring.
REOPENABLE_STATUSES = ("closed", "approved")
#: Deliberately not `approved` — withdrawing a signed-off shift is reopen-then-cancel, so the audit
#: trail records that somebody un-froze a settled period before the row went away.
CANCELLABLE_STATUSES = ("open", "closed")
#: The model owns the writable set (``LaborActivity.clean()`` reads the same tuple to decide whether
#: it may write into a shift), so deletion asks IT rather than restating "open".
DELETABLE_STATUSES = LaborSession.EDITABLE_STATUSES

#: The two derived exception buckets the list page filters on. NOT a model vocabulary: neither is a
#: column, and neither could be — both are `attended` against `booked`, and `booked` is a sum over a
#: child table that changes every time an activity is filed. See :func:`_gap_filter`.
GAP_CHOICES = [
    ("has_gap", "Unaccounted time"),
    ("over_booked", "Booked beyond the shift"),
]
_GAP_VALUES = {value for value, _label in GAP_CHOICES}


# =================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb in this module answers with."""
    return redirect("scm:laborsession_detail", pk=pk)


# --------------------------------------------------------------------------------------------
# The gap filter, in SQL.
#
# `?gap=` has to narrow the QUERYSET, because a filter applied after pagination pages over the
# unfiltered set and quietly shows the wrong rows on page 2. So both halves of the arithmetic have
# to exist as expressions, and the shape below is the one that survives every backend this project
# runs on (MySQL in production, SQLite under pytest).
#
# **Why intervals and not the stored `duration_minutes`.** The obvious form — SUM(duration_minutes)
# compared with the attended minutes — needs an integer minute count turned into a duration, i.e.
# `F("booked") * Value(timedelta(minutes=1))`. Django routes a mixed Integer x Duration product
# through `DurationExpression`, which on MySQL emits `(col * INTERVAL 60000000 MICROSECOND)` — a
# syntax error, not a slow query. Subtracting two datetimes has no such problem: it compiles to
# TIMESTAMPDIFF(MICROSECOND, …) on MySQL and django_timestamp_diff(…) on SQLite, both plain
# integers, so comparing one duration against another is an ordinary `>`.
#
# The one consequence worth knowing: SQL sums the EXACT interval while
# `LaborActivity.duration_minutes` floors each row to whole minutes. Every activity filed through
# the form carries minute precision (its widget's format is `%Y-%m-%dT%H:%M`), so the two agree; a
# row imported with seconds on it could differ by under a minute per activity. The badge printed on
# the row is always the model's own figure — this expression decides membership, never the number.
_ATTENDED_SPAN = models.ExpressionWrapper(F("clock_out") - F("clock_in"),
                                          output_field=models.DurationField())
#: Coalesce is load-bearing rather than tidy: a session with NO activities aggregates to NULL, and
#: `attended > NULL` is NULL, so the shift that is 100% gap time — the single most actionable row on
#: the page — would be the one row the "unaccounted time" filter dropped.
_BOOKED_SPAN = Coalesce(
    models.Sum(models.ExpressionWrapper(F("activities__ended_at") - F("activities__started_at"),
                                        output_field=models.DurationField())),
    models.Value(timedelta(0), output_field=models.DurationField()),
    output_field=models.DurationField(),
)


def _gap_filter(queryset, value):
    """Apply ``?gap=has_gap|over_booked`` and return ``(queryset, resolved_value)``.

    Anything else — absent, empty, hand-edited junk — resolves to ``""`` and narrows nothing (L11).
    The resolved value is handed to the template so the ``<select>`` binds to what was actually
    applied rather than to whatever was typed in the address bar.

    Both buckets require a ``clock_out``: attended minutes are ``None`` while a shift is running, and
    a shift still on the floor has neither "gone missing" nor over-booked itself.

    The ordering is RESTATED at the end and that is not redundant. ``QuerySet.ordered`` returns False
    the moment a query has a GROUP BY — even though the compiler still emits the Meta ORDER BY — so
    without this ``paginate()`` raises ``UnorderedObjectListWarning`` on every filtered page load of
    a list that is in fact perfectly ordered (the 4.8 finding recorded in ``views/_common.py``). Read
    off ``_meta`` rather than retyped, so the filtered page and the unfiltered one cannot drift into
    two different orders.
    """
    if value not in _GAP_VALUES:
        return queryset, ""
    queryset = (queryset.filter(clock_out__isnull=False)
                .annotate(attended_span=_ATTENDED_SPAN, booked_span=_BOOKED_SPAN))
    if value == "has_gap":
        queryset = queryset.filter(attended_span__gt=F("booked_span"))
    else:
        queryset = queryset.filter(booked_span__gt=F("attended_span"))
    return queryset.order_by(*LaborSession._meta.ordering), value


def _delete_refusal(obj):
    """The sentence that refuses a delete, or ``""`` — one implementation, two readers.

    Called by :func:`laborsession_delete` INSIDE its row lock and by :func:`laborsession_detail` to
    decide whether the button is offered and to say WHY when it is not. Offering a one-click failure
    is worse than not offering the button (the 4.12 rule), and a button whose route refuses for a
    reason the page never mentions is the same defect wearing a hat.

    Two refusals, and the second is the interesting one. A frozen or cancelled shift is history: it
    is what the payroll export was allowed to read and what the scorecard was computed from, so it is
    cancelled rather than destroyed. A shift carrying ACTIVITIES is refused even while it is open,
    because ``LaborActivity.session`` is ``CASCADE`` — one click would take the measured minutes,
    their standard snapshots and the record of which 4.4 tasks they were booked against with it, and
    none of that is reconstructable from anything. Delete the activities first, or cancel the shift.
    """
    if obj.status not in DELETABLE_STATUSES:
        return (f"{obj.number} is {obj.get_status_display().lower()} and cannot be deleted — a "
                "signed-off shift is the record of the minutes that were paid. Cancel an open one "
                "instead.")
    # A COUNT rather than an Exists() here on purpose (the inverse of the `views/_common.py` rule):
    # the refusal NAMES the number, so the query has to produce it.
    booked = obj.activities.count()
    if booked:
        return (f"{obj.number} has {booked} booked activit{'y' if booked == 1 else 'ies'} and "
                "cannot be deleted — deleting the shift would cascade those minutes, their standard "
                "snapshots and their task links away with it. Delete the activities first, or "
                "cancel the shift to withdraw it and keep the record.")
    return ""


def _transition(request, pk, *, from_statuses, to_status, action, verb, stamps=None,
                audit=None, message=None, precheck=None):
    """Delegates to the shared :func:`_status_transition` — see it for the locking contract.

    Kept as a two-line local so every verb below still reads ``_transition(request, pk, ...)`` and
    neither the model nor ``_detail`` is repeated eleven times. The body used to live here; it was
    byte-identical to 4.13's and to 4.14's own plan module, and a concurrency guard maintained in
    three places is a concurrency guard fixed in one and missed in two.
    """
    return _status_transition(
        request, LaborSession, pk, _detail,
        from_statuses=from_statuses, to_status=to_status, action=action, verb=verb,
        stamps=stamps, audit=audit, message=message, precheck=precheck)


@login_required
def laborsession_list(request):
    """Search + three filters + a work-date window + the derived gap filter.

    ``select_related`` covers the two FKs every row renders; without it a page of 15 shifts is 30
    extra queries for two columns. ``prefetch_related("activities")`` is the deliberate second half:
    the list shows booked minutes, gap time and utilisation, and every one of those is a method on
    the model that walks ``self.activities.all()``. Prefetched, the whole page costs ONE extra query
    and the template calls the same methods the detail page does; annotated instead, the page would
    print numbers computed by a second implementation that could drift from the model's own — and
    the model's is the one the payroll export and the scorecard agree with.

    The work-date window goes through the SHARED ``_date_window`` helper, never a second copy:
    ``work_date`` is a ``DateField``, so the bare ``YYYY-MM-DD`` an ``<input type="date">`` posts is
    exactly right and junk input SKIPS the filter rather than raising (L11). Every int-valued param
    goes through ``crud_list``'s ``is_int=True`` leg, so ``?worker=abc``, ``?worker=²`` and
    ``?worker=99999999999999999999`` all skip the filter instead of 500-ing.

    Both pre-filters are applied BEFORE ``crud_list`` paginates, like every other filter here — one
    applied afterwards would page over the unfiltered set and quietly show the wrong rows on page 2.
    """
    queryset = (LaborSession.objects.filter(tenant=request.tenant)
                .select_related("worker", "location")
                .prefetch_related("activities"))
    queryset = _date_window(queryset, request.GET, "work_date")
    queryset, gap = _gap_filter(queryset, request.GET.get("gap", "").strip())

    # ONE aggregate for all four header chips, over the WHOLE workspace rather than the filtered
    # page: "6 shifts awaiting approval" is a workspace fact somebody has to act on this week, and
    # recomputing it per filter would make the number change as you browse. `running` is the subset
    # of `open` that has not been clocked out yet — the people actually on the floor right now,
    # which is a different question from "which shifts are still writable".
    stats = LaborSession.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status="open")),
        running=Count("id", filter=Q(status="open", clock_out__isnull=True)),
        awaiting_approval=Count("id", filter=Q(status="closed")),
        approved=Count("id", filter=Q(status="approved")),
    )

    return crud_list(
        request, queryset, "scm/labor/laborsession/list.html",
        # `worker__name` is a forward-FK join, so it narrows rows without ever multiplying them —
        # which is what keeps the gap filter's SUM honest when a search is applied on top of it.
        search_fields=["number", "worker__name", "shift_label"],
        filters=[("status", "status", False),
                 ("worker", "worker_id", True), ("location", "location_id", True)],
        extra_context={
            "status_choices": SESSION_STATUS_CHOICES,
            "gap_choices": GAP_CHOICES,
            # The RESOLVED value, not the raw one — bind the select to this (see `_gap_filter`).
            "gap": gap,
            # The same set the form's `worker` field offers, from the same helper: a filter that
            # lists people the field cannot select is a filter that returns nothing, twice.
            "workers": _employee_parties(request.tenant),
            # Not narrowed to is_active: a shift worked last month at a site since wound down is
            # still a shift somebody was paid for and still needs to be findable.
            "locations": _location_qs(request.tenant),
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def laborsession_create(request):
    return _laborsession_form(request, instance=None)


@login_required
def laborsession_edit(request, pk):
    """Editable only while the shift is ``open``.

    ``EDITABLE_STATUSES`` is ``("open",)``: a closed shift has been reviewed, an approved one is what
    the payroll export was allowed to read, and a cancelled one is withdrawn. Editing any of the
    three would silently restate hours that have already been reported — and on an approved shift,
    hours that may already have been paid. Reopen it first; that is an admin verb, and it is audited.
    """
    obj = get_object_or_404(LaborSession, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited — reopen the shift first if the clock times or "
                                "the worker are genuinely wrong.")
        return _detail(pk)
    return _laborsession_form(request, instance=obj)


def _laborsession_form(request, instance):
    """The supervisor-entry path: a shift keyed in by hand, before or after it happened.

    Hand-rolled rather than delegated to ``crud_create`` / ``crud_edit`` for ONE reason, and it is
    the provenance. ``source`` and ``recorded_by`` are ``editable=False`` and off the form (L20/L22),
    so something has to stamp them, and the honest value depends on which path filed the row —
    ``"supervisor"`` here (somebody typed this shift; nothing punched it) and ``"web"`` in
    :func:`laborsession_clock_in`. A ``source`` a member could choose is not a provenance at all: it
    would let a hand-keyed shift claim to have come from a badge reader that never saw the worker, on
    a record whose minutes end up in a payroll export.

    Hand-rolled also means this path owes its own ``write_audit_log`` — the ``crud_*`` helpers write
    one for you and nothing else does — with ``_changed(form)``, never a second copy of the
    redaction list.

    **Neither stamp is re-applied on edit.** ``source`` records how the record ARRIVED, and a
    supervisor correcting a typo on a shift the worker punched in themselves did not turn it into a
    supervisor entry. ``login`` is likewise never touched here: it is set by the self-service punch
    and by nothing else, and a null one simply means nobody punched.

    Every clock rule — the ordering, the two-day length cap, the ``work_date``-is-the-start-date pin,
    the one-open-session-per-worker rule, the overlap guard and the employee-role check — lives in
    ``LaborSession.clean()`` and runs from ``form.is_valid()``. None of it is repeated here.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:laborsession_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = LaborSessionForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            changes = _changed(form)
            if not is_edit:
                obj.source = "supervisor"
                obj.recorded_by = request.user
                # Recorded in the audit row even though it was never on the form: the log is where
                # "who said this came from a supervisor?" gets answered.
                changes["source"] = obj.source
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", changes)
            messages.success(request, f"{obj.number} saved.")
            return _detail(obj.pk)
    else:
        form = LaborSessionForm(instance=instance, tenant=request.tenant)
    return render(request, "scm/labor/laborsession/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def laborsession_detail(request, pk):
    """The shift, its booked activities, and the eleven derived figures built from them.

    **The whole page is ONE scan of the child table**, and that is what the ``activities=None``
    parameter on every derived method exists for (the ``CycleCountTask.variance_count(lines=None)``
    idiom). ``prefetch_related`` fetches the rows once, ``list()`` materialises them, and the same
    list object is handed to each of the eleven figures below. Left to resolve their own rows, the
    six composed figures alone would be six independent scans for one render — and
    ``performance_pct`` and ``units_per_hour`` would each walk the set twice over.

    The activity list is deliberately NOT capped the way 4.13's detail panels are. A cap there
    bounds a *display* window; here the same rows are the INPUTS to attended-vs-booked arithmetic, so
    a slice would silently understate the gap on exactly the long shift most worth looking at. A
    session's activity count is bounded by the shift itself — ``MAX_ACTIVITY_MINUTES`` per row inside
    at most ``MAX_SESSION_MINUTES`` of shift — so there is no unbounded set to protect against.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the session. ``obj.status_css`` drives its badge; ``obj.source`` /
      ``obj.get_source_display`` / ``obj.recorded_by`` / ``obj.login`` / ``obj.approved_by`` are the
      provenance card, and a blank ``login`` means the shift was keyed in rather than punched.
    * ``activities`` — the booked rows, oldest-first-by-Meta (``-started_at``), each carrying
      ``activity_css``, ``is_direct`` / ``is_indirect``, ``duration_minutes``, ``earned_minutes``
      (``None`` when the work carried no standard) and ``performance_pct``.
    * ``activity_count`` — ``len(activities)``, so the empty state does not need a second pass.
    * The minutes waterfall, all ints or ``None``: ``attended_minutes`` (``None`` while the shift is
      still running), ``booked_minutes``, ``direct_minutes``, ``indirect_minutes``,
      ``unaccounted_minutes`` (the gap — ``None`` while running), ``over_booked_minutes`` (the other
      half — ``None`` while running) and ``earned_minutes`` (``None`` when nothing on the shift
      carried a standard, which is NOT the same as earning nothing).
    * The four ratios, Decimals or ``None``: ``performance_pct``, ``utilisation_pct``,
      ``units_per_hour``, ``accuracy_pct``. **Every one of them is ``None`` rather than ``0`` when
      its denominator is zero — print an em dash** (a 0% utilisation reads as "this worker did
      nothing", which is the opposite of "this shift has not been measured yet").
    * ``can_edit`` / ``can_add_activity`` — both ``obj.is_editable``, and named separately because
      the template asks two different questions of one fact.
    * ``can_delete`` and ``delete_refusal`` — the button, and the sentence to print INSTEAD of it
      when it is absent. Say why; do not just hide it.
    * ``can_clock_out`` / ``can_close`` / ``can_approve`` / ``can_reopen`` / ``can_cancel`` — the
      five ladder gates, each computed from the same tuple its verb guards on. The last three are
      ``@tenant_admin_required`` routes, so wrap those buttons in the admin test as well.
    """
    obj = get_object_or_404(
        LaborSession.objects
        .select_related("worker", "location", "recorded_by", "login", "approved_by")
        .prefetch_related(
            # Stopping one hop short is a query per activity row (L18), and the task links are
            # exactly what the table is for: `PutawayTask.__str__` dereferences `item` and
            # `to_location`, `CycleCountTask.__str__` dereferences `location`. `PickTask.__str__`
            # reads only its own columns, so it needs no second hop.
            Prefetch("activities", queryset=(LaborActivity.objects
                                             .select_related("standard", "pick_task",
                                                             "putaway_task__item",
                                                             "putaway_task__to_location",
                                                             "cycle_count_task__location")))),
        pk=pk, tenant=request.tenant)

    # Resolved ONCE and handed to every figure below — see the docstring.
    activities = list(obj.activities.all())
    refusal = _delete_refusal(obj)

    return render(request, "scm/labor/laborsession/detail.html", {
        "obj": obj,
        "activities": activities,
        "activity_count": len(activities),
        # The waterfall: attended -> direct + indirect -> unaccounted. Every one of these can be
        # None and none of them may be rendered as 0 (see the docstring).
        "attended_minutes": obj.attended_minutes,
        "booked_minutes": obj.booked_minutes(activities),
        "direct_minutes": obj.direct_minutes(activities),
        "indirect_minutes": obj.indirect_minutes(activities),
        "unaccounted_minutes": obj.unaccounted_minutes(activities),
        "over_booked_minutes": obj.over_booked_minutes(activities),
        "earned_minutes": obj.earned_minutes(activities),
        "performance_pct": obj.performance_pct(activities),
        "utilisation_pct": obj.utilisation_pct(activities),
        "units_per_hour": obj.units_per_hour(activities),
        "accuracy_pct": obj.accuracy_pct(activities),
        "can_edit": obj.is_editable,
        # The same fact the activity module gates its create/edit/delete paths on
        # (`LaborActivity` refuses to write into a shift that is not open), read from the model's
        # own tuple so the button and that refusal cannot disagree.
        "can_add_activity": obj.is_editable,
        # Exactly the condition `laborsession_delete` enforces, plus the sentence explaining it.
        "can_delete": not refusal,
        "delete_refusal": refusal,
        "can_clock_out": obj.status in CLOCK_OUT_STATUSES and obj.clock_out is None,
        "can_close": obj.status in CLOSABLE_STATUSES and obj.clock_out is not None,
        "can_approve": obj.status in APPROVABLE_STATUSES,
        "can_reopen": obj.status in REOPENABLE_STATUSES,
        "can_cancel": obj.status in CANCELLABLE_STATUSES,
    })


@tenant_admin_required
@require_POST
def laborsession_delete(request, pk):
    """Delete a shift — refused once it is frozen, and refused once anything is booked against it.

    Hand-rolled rather than delegated to ``crud_delete``, and the reason is the whole point of this
    view: ``crud_delete`` re-fetches the row by pk WITHOUT a lock and re-checks neither guard,
    because it cannot know about guards it was never told about. Both would then be advisory — read
    from an unlocked snapshot they answer about the state this request started in, and the DELETE
    waits on the lock and executes anyway. The realistic race is not exotic: a supervisor booking the
    shift's last activity while an admin deletes what looks like an empty session, and
    ``LaborActivity.session`` is ``CASCADE``.

    See :func:`_delete_refusal` for both refusals and why each exists.
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborSession.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        refusal = _delete_refusal(obj)
        if refusal:
            messages.error(request, refusal)
            return _detail(pk)
        # Inside the transaction so it rolls back with a failed delete rather than recording a
        # deletion that did not happen.
        write_audit_log(request.user, obj, "delete")
        number = obj.number
        obj.delete()
    messages.success(request, f"{number} deleted.")
    return redirect("scm:laborsession_list")


# ============================================================== the punch (self-service, no pk)
@login_required
@require_POST
def laborsession_clock_in(request):
    """Clock the LOGGED-IN USER in, right now. Routed at ``labor-sessions/clock-in/`` — there is no
    pk, because this verb is what CREATES the shift.

    **``worker`` is ``_acting_party(request)`` and can never come from the request.** The form is
    built from a dict this function assembles, not from ``request.POST``, so a ``worker=<pk>`` in the
    body is not rejected — it is never read. That is the difference between a self-service punch and
    a hole: ``login`` and ``recorded_by`` would name the real user either way, but the SHIFT would
    belong to somebody else, and it is the shift that is paid.

    ``source="web"``, ``login=request.user`` and ``recorded_by=request.user`` are stamped on the
    object returned by ``save(commit=False)``, AFTER validation. Before it would be pointless
    (they are ``editable=False``, so the form would ignore them) and keying a model error on a column
    the form does not carry raises ``ValueError`` out of ``Form.add_error`` — a 500 instead of a
    field error.

    **Two refusals in words rather than a 500 or a useless field error.** A login with no ``party``
    link has nobody to book minutes against, and a party without the ``employee`` role is not
    somebody this workspace employs — ``LaborSession.clean()`` rule (g) says exactly that, but the
    form's ``worker`` queryset would reject the choice first with "Select a valid choice", which
    tells the person at the timeclock nothing they can act on.

    **The worker's Party row is locked for the duration.** ``clean()`` refuses a second open session
    per worker, but that check is a plain read: two POSTs of one button (a double tap on a phone at
    the clock-in kiosk is the ordinary case, not an attack) both pass it and both insert, leaving two
    open shifts for one person and no defined answer to which one "clock out" means. There is no
    parent row to take FOR UPDATE, so the subject of the rule — the worker — is what is locked. The
    running-session lookup below is then a real guard rather than a hint, and it is also what turns
    the refusal into a useful sentence with a link.
    """
    if _need_tenant(request):
        return redirect("scm:laborsession_list")

    party = _acting_party(request)
    if party is None:
        messages.error(request, "Your login is not linked to a party record, so there is nobody to "
                                "book this shift against. Ask a workspace administrator to link "
                                "your user to your party record, or have a supervisor file the "
                                "shift from the New session form.")
        return redirect("scm:laborsession_list")
    if not party.roles.filter(role="employee").exists():
        messages.error(request, f"{party} does not hold the 'employee' role, so a shift cannot be "
                                "booked against them. Add the role on the party record first — a "
                                "worker nobody hired is a person whose hours nobody owes.")
        return redirect("scm:laborsession_list")

    # `work_date` is pinned to the LOCAL date of `clock_in` by `LaborSession.clean()`, so both are
    # derived from ONE localtime() reading. Two readings could straddle midnight and produce a
    # session the model then refuses for a reason nobody at the kiosk could act on. Seconds are
    # truncated because the form's `datetime-local` control round-trips minute precision, and a
    # punch a few seconds in the past is the truth about when the button was pressed anyway.
    local_now = timezone.localtime(timezone.now())
    data = {
        "worker": str(party.pk),
        "location": (request.POST.get("location") or "").strip(),
        "work_date": local_now.strftime("%Y-%m-%d"),
        "clock_in": local_now.strftime("%Y-%m-%dT%H:%M"),
        # Explicitly blank: the shift has not ended, and every figure derived from attended minutes
        # answers "not yet" rather than zero until it has.
        "clock_out": "",
        "shift_label": (request.POST.get("shift_label") or "").strip()[:60],
        "notes": (request.POST.get("notes") or "").strip(),
    }

    with transaction.atomic():
        # The lock. Tenant-filtered like every other queryset in this package even though
        # `_acting_party` has already checked it — a lookup that skips the scope because a caller
        # promised is how the one that stops promising gets missed.
        Party.objects.select_for_update().filter(pk=party.pk, tenant=request.tenant).first()

        running = (LaborSession.objects
                   .filter(tenant=request.tenant, worker_id=party.pk, status="open")
                   .order_by("-clock_in").first())
        if running is not None:
            messages.error(request, f"You are already clocked in on {running.number} "
                                    f"({running.work_date}). Clock that shift out before starting "
                                    "another — two open shifts would have no defined clock-out "
                                    "target and would bill the same minutes twice.")
            return _detail(running.pk)

        form = LaborSessionForm(data, tenant=request.tenant)
        if not form.is_valid():
            for field, errors in form.errors.items():
                messages.error(request, f"{field}: {' '.join(errors)}")
            return redirect("scm:laborsession_list")

        obj = form.save(commit=False)
        obj.tenant = request.tenant
        # Provenance, stamped by the verb that is actually filing this shift rather than accepted
        # from the request — see the docstring. `login` is set HERE and nowhere else in the module:
        # it means "the worker punched themselves in", and the supervisor-entry path leaves it null
        # precisely because nobody did.
        obj.source = "web"
        obj.login = request.user
        obj.recorded_by = request.user
        obj.save()

    write_audit_log(request.user, obj, "create", {
        "action": "clock_in", "status": obj.status, "source": obj.source,
        "worker": party.name, "location": obj.location.code,
        "clock_in": str(obj.clock_in)})
    messages.success(request, f"Clocked in on {obj.number} at "
                              f"{timezone.localtime(obj.clock_in):%H:%M} at {obj.location.code}.")
    return _detail(obj.pk)


# =============================================================== the ladder (one row each, locked)
@login_required
@require_POST
def laborsession_clock_out(request, pk):
    """Stamp ``clock_out`` on a live shift. **The status does not move** — see the module docstring.

    The stamp is ``now()`` and is never taken from the POST: this verb records that the shift ended
    *at the moment the button was pressed*, which is the one thing it can honestly know. A punch that
    was missed and is being reconstructed afterwards is a different act with a different truth value,
    and it goes through the edit form — where it is a typed field, validated by
    ``LaborSession.clean()`` and diffed into the audit row.

    Both re-checks below exist because this path saves with ``update_fields`` and therefore never
    runs ``full_clean()``. They are the two model rules that a ``now()`` stamp can actually violate:
    a shift whose ``clock_in`` is in the future (a supervisor keyed tomorrow's date) would derive
    NEGATIVE attended minutes and invert every ratio built on them, and one left running for days
    would derive an attended figure past what the arithmetic downstream holds. Refusing here means
    the correction happens on the form, where the person can see both ends of the clock.
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborSession.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in CLOCK_OUT_STATUSES:
            messages.error(request, f"{obj.number} cannot be clocked out — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        if obj.clock_out is not None:
            messages.error(request, f"{obj.number} was already clocked out at "
                                    f"{timezone.localtime(obj.clock_out):%d %b %Y %H:%M}. Correct "
                                    "the time on the edit form rather than stamping it twice.")
            return _detail(pk)

        moment = timezone.now()
        if moment <= obj.clock_in:
            messages.error(request, f"{obj.number} is clocked in at "
                                    f"{timezone.localtime(obj.clock_in):%d %b %Y %H:%M}, which is "
                                    "not in the past — correct the clock-in on the edit form before "
                                    "clocking out.")
            return _detail(pk)
        if (moment - obj.clock_in).total_seconds() // 60 > MAX_SESSION_MINUTES:
            messages.error(request, f"{obj.number} has been running for longer than "
                                    f"{MAX_SESSION_MINUTES // (60 * 24)} days, which is past the "
                                    "limit for a single session. Set the real clock-out on the edit "
                                    "form, then close the shift.")
            return _detail(pk)

        obj.clock_out = moment
        obj.save(update_fields=["clock_out", "updated_at"])

    write_audit_log(request.user, obj, "update",
                    {"action": "clock_out", "status": obj.status, "clock_out": str(moment)})
    messages.success(request, f"{obj.number} clocked out at "
                              f"{timezone.localtime(moment):%H:%M} — {obj.attended_minutes} "
                              "minutes attended.")
    return _detail(pk)


def _needs_clock_out(obj):
    """Refuse to close a shift that never ended, or ``""``.

    Attended minutes are ``clock_out − clock_in``, so a closed session with a null ``clock_out`` has
    no attended figure and — because closing freezes the record — never will. Gap time, utilisation
    and every hour in the payroll export are derived from that figure, so this is not a tidiness
    rule: it is the difference between a shift that reports "not yet measured" for one afternoon and
    one that reports it permanently.
    """
    if obj.clock_out is None:
        return (f"{obj.number} has not been clocked out yet, so it has no attended time to close "
                "against. Clock it out first, or set the real clock-out on the edit form.")
    return ""


@login_required
@require_POST
def laborsession_close(request, pk):
    """open -> closed: the shift is over, the minutes are booked, and the record is now frozen.

    Freezing is what ``closed`` is FOR — ``LaborActivity`` refuses to write into a session that is
    not open — and keeping it apart from ``approved`` is what lets a supervisor find "ended but not
    yet signed off" without a second flag.
    """
    return _transition(request, pk, from_statuses=CLOSABLE_STATUSES, to_status="closed",
                       action="close", verb="closed", precheck=_needs_clock_out,
                       stamps={"closed_at": timezone.now()})


@tenant_admin_required
@require_POST
def laborsession_approve(request, pk):
    """closed -> approved. **This is the payroll export's lock**, which is why it is admin-gated.

    The export reads ``approved`` sessions and nothing else, and there is deliberately no
    ``exported_at`` column to disagree with that (the CSV page is a GET, and a read that performs a
    write means a refresh, a prefetch or a crawler silently changes state — see the model docstring).
    Approving therefore IS the act of releasing these hours, and it happens once, under a row lock.

    Hand-rolled instead of going through :func:`_transition` for the three warnings, and they earn
    their place: a shift is approved by somebody who is signing off hours, and "45 of these minutes
    are unaccounted for" is exactly the thing they should be told AT that moment rather than find on
    a report next week. The figures are read inside the lock only because the object is already
    there; nothing is gated on them, so they carry no TOCTOU weight — they are a sentence, not a
    guard.
    """
    stamped_at = timezone.now()
    with transaction.atomic():
        obj = get_object_or_404(LaborSession.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in APPROVABLE_STATUSES:
            messages.error(request, f"{obj.number} cannot be approved — it is "
                                    f"{obj.get_status_display().lower()}."
                                    + (" Close it first." if obj.status == "open" else ""))
            return _detail(pk)

        # One scan of the child table, shared by all three figures (the `activities=None` idiom).
        activities = list(obj.activities.all())
        gap = obj.unaccounted_minutes(activities)
        over = obj.over_booked_minutes(activities)

        obj.status = "approved"
        obj.approved_at = stamped_at
        obj.approved_by = request.user
        obj.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])

    write_audit_log(request.user, obj, "update", {
        "action": "approve", "status": "approved", "activities": len(activities),
        "attended_minutes": obj.attended_minutes, "unaccounted_minutes": gap,
        "over_booked_minutes": over})
    messages.success(request, f"{obj.number} approved — its hours are now visible to the payroll "
                              "export.")
    if not activities:
        messages.warning(request, f"{obj.number} has no booked activities, so all of its attended "
                                  "time is unaccounted for and none of it can be attributed to any "
                                  "kind of work.")
    elif gap:
        messages.warning(request, f"{gap} minutes of {obj.number} are unaccounted for — paid time "
                                  "with no work booked against it.")
    if over:
        messages.warning(request, f"{obj.number} has {over} minutes booked beyond the shift it was "
                                  "attended for — usually two people on one badge, or a stop nobody "
                                  "ended.")
    return _detail(pk)


def _reopen_refusal(obj):
    """Refuse a reopen that would leave the worker with two open shifts, or ``""``.

    ``LaborSession.clean()`` rule (e) refuses a second ``open`` session per worker, and this verb
    saves with ``update_fields`` — so it never runs ``full_clean()`` and would walk straight past it.
    Two open shifts for one person have no defined clock-out target (the verb would have to guess
    which one it is closing), and until somebody noticed, the board would show that worker on shift
    twice.

    Evaluated INSIDE the caller's row lock. It reads a SIBLING row rather than this one's columns,
    so run before the lock it would answer about the state the request started in.
    """
    clash = (LaborSession.objects
             .filter(tenant_id=obj.tenant_id, worker_id=obj.worker_id, status="open")
             .exclude(pk=obj.pk).first())
    if clash is not None:
        return (f"{obj.worker} already has an open shift ({clash.number}), and a worker may only "
                f"have one. Close that shift before reopening {obj.number}.")
    return ""


@tenant_admin_required
@require_POST
def laborsession_reopen(request, pk):
    """closed | approved -> open. **The only route back to writable**, and admin-only for that reason.

    Reopening an approved shift un-freezes minutes the payroll export has already been able to read,
    which is why the three approval stamps are CLEARED rather than left standing: an ``approved_by``
    on a shift that is open again would say somebody signed off hours they have not seen. Re-approval
    is a fresh decision and gets a fresh stamp.

    ``closed_at`` is cleared for the same reason. ``login``, ``source`` and ``recorded_by`` are NOT
    touched — they record how the shift arrived, and reopening it did not change that.
    """
    return _transition(request, pk, from_statuses=REOPENABLE_STATUSES, to_status="open",
                       action="reopen", verb="reopened", precheck=_reopen_refusal,
                       # A None here is a deliberate CLEAR, not an "unset" — see `_transition`.
                       stamps={"closed_at": None, "approved_at": None, "approved_by": None})


@tenant_admin_required
@require_POST
def laborsession_cancel(request, pk):
    """open | closed -> cancelled: a shift that should not have been filed at all.

    Cancelling is how a mis-filed shift is WITHDRAWN while keeping the record of it — the model
    excludes cancelled sessions from both sides of its overlap guard (a cancelled shift occupies no
    time), and neither the payroll export nor the scorecard reads anything but ``approved``. That is
    also why it is preferred to deletion, which would cascade the booked activities away.

    Deliberately not offered on an ``approved`` shift: reopen it first. Two audited steps make "this
    was withdrawn after it had been signed off" a fact somebody can read back, rather than one status
    hop that erases the distinction.

    The reason is optional and lands in the AUDIT row rather than on the document: it is a note about
    a moment, and writing it into ``notes`` would overwrite what the shift itself says.
    """
    reason = (request.POST.get("reason") or "").strip()
    return _transition(request, pk, from_statuses=CANCELLABLE_STATUSES, to_status="cancelled",
                       action="cancel", verb="cancelled",
                       audit={"reason": reason[:200]} if reason else None)

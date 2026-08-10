"""SCM 4.14 Labor Management — ``LaborActivity`` views: the booked interval, and where it is MEASURED.

**The parent route is the authorization boundary.** An activity is created at
``labor-sessions/<pk>/activities/add/`` and nowhere else. ``session`` is absent from
``LaborActivityForm.Meta.fields``, so there is no path from form data to the column at all — the
shift is resolved here with ``tenant=request.tenant`` and handed to the form as an already-bound
instance. That absence is a stronger statement than "a view checks for it": a pk in the POST body is
how a caller grafts minutes onto somebody else's shift, and those minutes land in that worker's
performance figures and, once the shift is approved, in the payroll export.

**The standard snapshot is resolved HERE, exactly once, on create.** :func:`_stamp_standard` calls
``select_standard()`` and copies the three determinants (fixed minutes, per-unit rate, allowance)
onto the row before it is saved; ``LaborActivity.save()`` then derives the earned figure from those
three and the row's own quantity, and NEVER goes back to the ``LaborStandard`` table. One writer,
one direction. The edit path deliberately does not re-resolve — see :func:`laboractivity_edit` for
what that costs and why it is still the right trade.

**``select_standard()`` returning ``None`` is a legitimate outcome and is never turned into a zero.**
Not every job in a warehouse has been time-studied. An unmeasured activity keeps every snapshot null,
``earned_minutes`` is ``None``, ``performance_pct()`` is ``None``, and
``LaborSession._measured()`` drops the row out of BOTH sides of the shift ratio. A ``0`` here would
print as 0% performance — an unmeasured job rendered as a failing one, against a named person, with
no way for them to argue with it.

**Nothing in 4.14 writes a ``StockMove`` or a ``JournalEntry``, and this file is no exception.**
Booking minutes against a 4.4 pick/putaway/count task sets a pointer OUT to that task and adds no
column to it. Nor does this file reach into the HRM app for the person: the worker is a
``core.Party`` on the parent session, and the payroll hand-off downstream is a CSV report rather
than a write into anybody else's tables.

**The freeze rule, enforced on every write path in this file.** ``LaborSession.EDITABLE_STATUSES``
is ``("open",)``: ``closed`` and ``approved`` freeze the shift **and its activities**, and
``approved`` is the payroll export's lock. ``LaborActivity.clean()`` already refuses to SAVE into a
non-open session, but a model error surfaces as a form error on a page the user should never have
reached — and it does not guard :func:`laboractivity_delete` at all, because a delete runs no
``clean()``. So each write path pre-checks the parent's status and answers with a message plus a
redirect. Deleting an activity out of an approved shift would silently restate hours that have
already been signed off.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here, not just the list variable):

* ``scm/labor/laboractivity/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). Filter context: ``activity_choices`` / ``direction_choices`` / ``reason_choices``
  (lists of ``(value, label)`` pairs), ``sessions`` (a ``LaborSession`` queryset) and ``workers`` (a
  ``core.Party`` queryset). Filter params: ``q`` / ``activity_type`` / ``direction`` /
  ``indirect_reason`` (strings — compare with ``request.GET.<param>`` directly) and ``session`` /
  ``worker`` (pks — compare with ``s.pk|stringformat:"d"``, NEVER ``|slugify``), plus ``date_from``
  / ``date_to`` on ``started_at``.
* ``scm/labor/laboractivity/form.html`` — ``form``, ``is_edit``, ``session`` (the parent shift; the
  form has NO ``session`` field, so the heading, the breadcrumb and the cancel link can only get it
  from here) and ``obj`` (``None`` on create).
* ``scm/labor/laboractivity/detail.html`` — ``obj``, ``session``, the five derived figures
  ``duration_hours`` / ``earned_minutes`` / ``performance_pct`` / ``units_per_hour`` /
  ``accuracy_pct`` (**every one of them ``None`` when unanswerable — render an em dash, never a 0**),
  ``has_standard``, ``standard`` (the live ``LaborStandard`` row, or ``None`` once it has been
  deleted), ``standard_gone`` (measured, but the standard it named is gone), the four live-vs-snapshot
  keys ``live_fixed_minutes`` / ``live_rate`` / ``live_allowance`` / ``live_earned_minutes`` (all
  ``None`` when the standard is gone) and ``snapshot_differs`` — which is the whole point of the
  page: when it is True the standard has been re-timed SINCE this row was filed, and the figures
  above are still the ones filed at the time. ``linked_task`` / ``linked_task_kind``
  (``"pick"`` / ``"putaway"`` / ``"cycle_count"`` / ``""``) name the 4.4 task the minutes were booked
  against, so the template can pick between ``scm:picktask_detail`` / ``scm:putawaytask_detail`` /
  ``scm:cyclecounttask_detail``. Action gates: ``can_edit`` / ``can_delete`` plus ``frozen_reason``
  (a sentence, blank when nothing is frozen — say WHY a button is missing rather than just hiding it).

Badge colours come from the model: ``obj.activity_css`` and ``obj.session.status_css``.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css (L33).

``laboractivity_delete`` is ``@tenant_admin_required``, so wrap that one button in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a member a button
they will 403 on is the 4.11 finding.
"""
from datetime import datetime, time

from django.utils.dateparse import parse_date, parse_datetime

from apps.scm.views._common import *  # noqa: F401,F403
# Builds the {field: new_value} diff (with the sensitive-field redaction list applied) that crud_edit
# records automatically. The edit path below is hand-rolled, so it owes that diff by hand — imported
# rather than reimplemented, because a second copy of the redaction list is a second copy to forget.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _date_window
# Views legitimately depend on forms for the shared party queryset — the `_supplier_parties`
# precedent in views/_helpers.py. The `worker` filter dropdown must offer the same set the SESSION
# form's `worker` field offers, or the filter lists people no shift could ever have been filed for.
from apps.scm.forms._common import _employee_parties
# The vocabularies come from `_choices` via the models package's re-export, NOT from
# `_meta.get_field(...).choices`: these are the same lists the form renders from, and naming them
# directly is what keeps "the filter offers what the column accepts" a fact rather than a
# coincidence. DIRECT_ACTIVITIES / INDIRECT_ACTIVITIES are the single source of truth for the
# direct/indirect split — the `direction` filter branches on them and never on a hand-typed tuple.
from apps.scm.models import (ACTIVITY_CHOICES, DIRECT_ACTIVITIES, INDIRECT_ACTIVITIES,
                             INDIRECT_REASON_CHOICES, LaborActivity, LaborSession, select_standard)
from apps.scm.forms import LaborActivityForm

ZERO = Decimal("0")

#: The `direction` filter's option list. It is DERIVED, not a column — there is no `direction` field
#: to read choices off, so the view has to hand the two options to the template or the dropdown
#: renders empty (Filter rule 1). The values are the two keys of :data:`_DIRECTION_SETS`.
DIRECTION_CHOICES = [
    ("direct", "Direct (productive)"),
    ("indirect", "Indirect / lost time"),
]

#: What each `direction` value means, expressed as the frozensets that already define it. The whole
#: module — the session aggregates, the scorecard, the plan generator's scope — branches on these two
#: names, so the filter cannot come to a different conclusion about what "productive" means than the
#: numbers on the same screen do.
_DIRECTION_SETS = {
    "direct": DIRECT_ACTIVITIES,
    "indirect": INDIRECT_ACTIVITIES,
}


# ===================================================================================== small helpers
def _detail(pk):
    """This row's own page — where an edit lands."""
    return redirect("scm:laboractivity_detail", pk=pk)


def _session_detail(pk):
    """The parent shift — where a create and a delete land.

    A create belongs back on the shift because the next thing a supervisor does is book the NEXT
    stretch of the same shift; a delete belongs there because the row it would otherwise return to
    no longer exists.
    """
    return redirect("scm:laborsession_detail", pk=pk)


def _frozen(request, session):
    """True (and flashes) when ``session`` is no longer ``open``.

    ``closed`` and ``approved`` freeze the shift AND its activities, and ``approved`` is what the
    payroll export reads — a booking added, corrected or removed after sign-off changes hours that
    have already been paid without the approval being revisited. ``cancelled`` is not a shift at all.

    Stated once and called from all three write paths so the create form, the edit form and the
    delete button cannot disagree about when the shift is writable.
    """
    if session.status not in LaborSession.EDITABLE_STATUSES:
        messages.error(request, f"{session.number} is {session.get_status_display().lower()} — its "
                                "activities are frozen. Reopen the shift before booking or "
                                "correcting minutes.")
        return True
    return False


def _frozen_reason(session):
    """The same refusal as a SENTENCE for the detail page, or ``""``. Say why, don't just hide."""
    if session.status in LaborSession.EDITABLE_STATUSES:
        return ""
    return (f"{session.number} is {session.get_status_display().lower()}, so this activity can no "
            "longer be changed — a signed-off shift is the record of the minutes that were paid.")


def _effective_day(activity, session):
    """The LOCAL date the standard should be resolved for: when the work was actually done.

    ``started_at``, not ``session.work_date``. The two agree for an ordinary shift, and they
    deliberately do not for an overnight one — ``work_date`` is pinned to the day the shift STARTED,
    so a 02:00 pick on a night shift belongs to the standard in force on the 2nd even though the
    session is dated the 1st. A standard's effective range is a date range, and resolving it against
    the wrong side of midnight is how a re-timed standard appears to have applied a day early.

    ``localdate()`` needs an aware value; a naive one (a seeder or a test running with ``USE_TZ``
    off) is read as-is rather than raising out of what is only a lookup key.
    """
    started = activity.started_at
    if started is None:
        return session.work_date
    return started.date() if timezone.is_naive(started) else timezone.localdate(started)


def _stamp_standard(activity, session, tenant):
    """Resolve the governing ``LaborStandard`` ONCE and copy its determinants onto the row.

    Returns the standard, or ``None``. **``None`` is a legitimate, expected answer** and the row is
    left with every snapshot null — see the module docstring for why substituting ``0`` would be a
    verdict on a person rather than a measurement.

    Only ``activity_type``, the session's LOCATION and the effective day are in scope.
    ``select_standard``'s ladder also has category rungs, and they are simply not reachable from
    here: an activity books a stretch of TIME, not an item, and deriving a category from the first
    line of a linked pick task would make the measurement depend on line ordering — a figure that
    changes when somebody re-sorts a task is not a measurement.

    **Resolution is restricted to DIRECT work**, which is the contract ``LaborStandard.activity``
    already states in its own help text ("an INDIRECT activity may carry a standard, but no
    performance figure is computed against it — break time is not earned time"), and the rule
    ``LaborSession._measured()`` enforces on the aggregate side. Without the gate, a fixed-time
    standard filed against ``break`` would give a break row a non-zero ``earned_minutes`` and
    therefore a ``performance_pct()`` printed on its own detail page — a worker credited with
    achievement for being on a break. The session ratio would still be right; the row would not.

    No quantizer on the way in, and that is checked rather than assumed: each target column is
    strictly wider than the column it copies from — ``(12,4)`` holds the sum of two ``(10,4)``
    determinants and a third one on its own, ``(6,2)`` holds a ``(6,2)`` allowance — so the copy
    cannot overflow. The one DERIVED figure, ``standard_minutes_snapshot``, is computed by
    ``LaborActivity._earned_from_snapshots()``, which already clamps through ``q4()``.
    """
    if not activity.is_direct:
        return None
    standard = select_standard(tenant, activity.activity_type,
                               location=session.location_id,
                               on_date=_effective_day(activity, session))
    if standard is None:
        return None
    # The FK is traceability only — `has_standard` asks the SNAPSHOTS, so deleting the standard later
    # clears this pointer without unmeasuring a minute of the work it governed.
    activity.standard = standard
    activity.standard_fixed_snapshot = ((standard.setup_minutes or ZERO)
                                        + (standard.travel_minutes or ZERO))
    activity.standard_rate_snapshot = standard.minutes_per_unit or ZERO
    activity.standard_allowance_snapshot = standard.allowance_pct or ZERO
    return standard


def _aware_bound(raw, *, end_of_day):
    """One end of a ``?date_from=/?date_to=`` window as an AWARE datetime, or ``None`` on junk.

    ``started_at`` is a ``DateTimeField`` while ``<input type="date">`` posts a bare day, and handing
    that string straight to ``_date_window`` is two defects at once: ``date_to`` becomes
    ``<= 00:00``, so the filter EXCLUDES the whole day the user asked for, and the value is naive
    under ``USE_TZ`` — a ``RuntimeWarning`` on every filtered page load and, under any project
    timezone other than UTC, a silently shifted window. So a bare ``to`` date is extended to that
    day's last microsecond and both ends are localised.

    **Both parsers RAISE on a value that is well FORMATTED but not a real moment** — Django's own
    docstrings say so: ``parse_date("2026-02-30")`` raises ``day is out of range``, and
    ``parse_datetime("2026-01-01T25:00")`` raises ``hour must be in 0..23``. Uncaught, that is a 500
    on a URL anybody can type into the address bar. An impossible date is exactly as much "not a
    moment" as ``lastweek`` is, so it takes the same answer: ``None``, the filter is skipped, and
    nothing raises (L11, the posture ``as_db_int`` and ``_date_window`` already take).
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
        if day is None:
            return None
        value = datetime.combine(day, time.min)
    # The whole-day extension is decided by the parsed VALUE, never by which parser answered, and
    # that distinction is not academic: on this Django ``parse_datetime`` delegates to
    # ``datetime.fromisoformat``, which happily accepts a bare ``2026-08-07`` and returns midnight —
    # so the ``parse_date`` branch above is never reached for the input a ``<input type="date">``
    # actually posts. A "did the date parser match?" test therefore looks correct and does nothing,
    # and ``date_to`` goes back to excluding the entire day the user asked for. Measured against the
    # real parser rather than assumed from its name.
    #
    # ``replace`` rather than ``datetime.combine``: combining drops any tzinfo the string carried,
    # so an explicit ``?date_to=2026-08-07T00:00:00+05:00`` would silently be re-read in the project
    # timezone. A caller who really does mean "up to exactly midnight" writes ``00:00:01``; on a
    # filter bar that posts bare days, treating midnight as "that whole day" is the only reading
    # that does not lose a day of data.
    if end_of_day and value.time() == time.min:
        value = value.replace(hour=23, minute=59, second=59, microsecond=999999)
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    return value


#: How many sessions the activity list's session filter offers. Newest first, because the shift
#: somebody is filtering by is almost always a recent one.
_SESSION_FILTER_LIMIT = 200


def _session_filter_options(tenant, selected_pk):
    """The bounded session list for the filter dropdown, with the selected one guaranteed present.

    Two queries at worst, one in the normal case. The second only fires when the pk in ``?session=``
    is older than the window — which is exactly the deep-link case that must not silently reset to
    "All sessions", and is why this cannot just be a slice.
    """
    if tenant is None:
        return []
    qs = (LaborSession.objects.filter(tenant=tenant)
          .select_related("worker")
          .order_by("-work_date", "-clock_in", "-id"))
    sessions = list(qs[:_SESSION_FILTER_LIMIT])
    if selected_pk is not None and all(s.pk != selected_pk for s in sessions):
        extra = (LaborSession.objects.filter(pk=selected_pk, tenant=tenant)
                 .select_related("worker").first())
        if extra is not None:
            sessions.insert(0, extra)
    return sessions


def _started_window(qs, data):
    """Apply ``?date_from=&date_to=`` to ``started_at`` through the SHARED ``_date_window`` helper.

    The helper still does the filtering, owns the lookup names and owns the skip-junk-input rule — it
    is used, never re-implemented. All this adds is :func:`_aware_bound` on each end, because every
    other page that reaches ``_date_window`` filters a ``DateField`` and this one filters a
    datetime column.
    """
    window = {}
    start = _aware_bound(data.get("date_from"), end_of_day=False)
    if start is not None:
        window["date_from"] = start.isoformat()
    end = _aware_bound(data.get("date_to"), end_of_day=True)
    if end is not None:
        window["date_to"] = end.isoformat()
    return _date_window(qs, window, "started_at")


# ========================================================================================= the list
@login_required
def laboractivity_list(request):
    """Every booked interval in the workspace: search, five filters and a started-on window.

    **Scoped on its own tenant AND ``session__tenant``**, which is belt and braces rather than
    redundancy: the two columns cannot legitimately disagree (``LaborActivity.clean()`` refuses a
    foreign session and ``session`` is never a form field), but this page reads MINUTES that end up
    in a payroll export, and a row whose tenant column was written wrong by a fixture, a data
    migration or a direct DB edit must not print another workspace's shift here. The join is free —
    ``session`` is select_related on the same query.

    ``select_related`` covers every FK a row can print, INCLUDING the second hop each task's
    ``__str__`` walks (``PutawayTask`` prints ``item.sku`` and ``to_location.code``,
    ``CycleCountTask`` prints ``location.code``; ``PickTask`` walks nothing and is deliberately left
    at one hop). All of them are nullable, so these are LEFT joins that cannot multiply a row. The
    alternative is up to three queries per row for one column — 45 on a full page (L18).

    Every int-valued param goes through ``crud_list``'s ``is_int=True`` leg, so ``?worker=abc``,
    ``?worker=²`` and ``?worker=99999999999999999999`` all SKIP the filter instead of 500-ing (L11).
    The window and the derived ``direction`` filter are applied BEFORE ``crud_list`` paginates — one
    applied afterwards would page over the unfiltered set and quietly show the wrong rows on page 2.
    """
    qs = (LaborActivity.objects
          .filter(tenant=request.tenant, session__tenant=request.tenant)
          .select_related("session", "session__worker", "session__location", "standard",
                          "pick_task", "putaway_task", "putaway_task__item",
                          "putaway_task__to_location", "cycle_count_task",
                          "cycle_count_task__location"))
    qs = _started_window(qs, request.GET)

    # `direction` is DERIVED from the two frozensets and is not a column, so it cannot be expressed
    # as a `crud_list` filter tuple. An unrecognised value skips the filter rather than narrowing to
    # nothing — a hand-edited `?direction=sideways` must show every row, not an empty table that
    # looks like a workspace with no activities in it.
    direction = (request.GET.get("direction") or "").strip()
    if direction in _DIRECTION_SETS:
        qs = qs.filter(activity_type__in=_DIRECTION_SETS[direction])

    return crud_list(
        request, qs, "scm/labor/laboractivity/list.html",
        # Number and free-text reference only. Whose shift and which shift have their own filters
        # below, and folding `session__worker__name` in here would make a search for "Liam" and a
        # filter on Liam two subtly different result sets.
        search_fields=["number", "reference"],
        filters=[("activity_type", "activity_type", False),
                 ("indirect_reason", "indirect_reason", False),
                 ("session", "session_id", True),
                 # Through the parent — LaborActivity records WHAT was done, LaborSession records
                 # WHO did it, and there is deliberately no second copy of the worker on this table.
                 ("worker", "session__worker_id", True)],
        extra_context={
            "activity_choices": ACTIVITY_CHOICES,
            "direction_choices": DIRECTION_CHOICES,
            "reason_choices": INDIRECT_REASON_CHOICES,
            # EVERY session, not just open ones, and not a slice. This populates the FILTER dropdown,
            # and a closed or approved shift's activities are exactly the rows this page is careful
            # to still show — narrowing it would leave them filterable by URL but unreachable from
            # the select, and would make a deep link from a signed-off shift silently reset to "All
            # sessions" (the 4.8 finding on ProductionTimeLog's work-order filter).
            # `LaborSession.__str__` walks `worker.name`, so the select_related is what stops one
            # query per <option>.
            # ...but BOUNDED, because "every session ever" is not a dropdown. LaborSession is one row
            # per worker per shift, so a 60-person warehouse writes ~15,000 a year and every one
            # would become an <option> on the filter bar of a page that renders 15 rows — megabytes
            # of HTML and DOM to filter a paginated list.
            # The two properties above are both preserved: the newest _SESSION_FILTER_LIMIT are
            # offered, and if the CURRENTLY SELECTED session is older than that it is fetched and
            # prepended, so a deep link from a signed-off shift still binds instead of silently
            # resetting to "All sessions". Worst case two queries, bounded payload.
            "sessions": _session_filter_options(request.tenant,
                                                as_db_int(request.GET.get("session"))),
            # The same set the session form offers, so the filter cannot list a person no shift could
            # ever have been filed against.
            "workers": _employee_parties(request.tenant),
        },
    )


# ======================================================================= create, under the PARENT
@login_required
def laborsession_add_activity(request, pk):
    """Book one stretch of a shift. **The session comes from the URL, never from POST.**

    The parent is resolved with ``tenant=request.tenant`` before anything else, so a crafted pk is a
    404 and a tenant-less user (the superuser has ``tenant=None``) gets the same 404 rather than a
    friendly message that would confirm the row exists — ``LaborSession.tenant`` is NOT NULL, so
    ``tenant=None`` matches nothing by construction.

    The form is handed an instance ALREADY bound to that session, and that is load-bearing rather
    than tidy: ``LaborActivity.clean()``'s three most important rules — the interval must fall inside
    the shift's clock window, the shift must still be ``open``, and the cross-tenant FK guard —
    all dereference ``self.session`` and ``self.tenant`` and simply do not run when either is unset.
    A form constructed without them would validate an activity against no shift at all and then save
    it against one.

    The standard is resolved here and only here — see :func:`_stamp_standard`.
    """
    session = get_object_or_404(
        LaborSession.objects.select_related("worker", "location"), pk=pk, tenant=request.tenant)
    if _frozen(request, session):
        return _session_detail(pk)
    return _activity_form(request, session=session, instance=None)


@login_required
def laboractivity_edit(request, pk):
    """Correct one booked interval — while its shift is still open, and WITHOUT re-measuring it.

    Resolved on its own tenant AND ``session__tenant``, the same double scope the list applies, and
    the parent's status is re-checked here so an edit form on a signed-off shift is a message rather
    than a page that fails on submit.

    **The standard is not re-resolved.** ``save()`` recomputes the earned minutes from the three
    snapshots and the CURRENT quantity, so correcting a mistyped figure corrects the measurement with
    it; re-running ``select_standard()`` would mean an edit made next month silently re-measured last
    month's work against a standard that has since been re-timed, which is the exact failure the
    snapshot exists to prevent. The cost of that is one honest edge: changing ``activity_type`` on an
    existing row leaves the standard filed for the ORIGINAL type in place. That is not silent — the
    save path below says so out loud, and the fix is to delete the row and file it again, which is
    also the truthful thing to do to a booking that turned out to be a different job.
    """
    obj = get_object_or_404(
        LaborActivity.objects.select_related("session", "session__worker", "session__location"),
        pk=pk, tenant=request.tenant, session__tenant=request.tenant)
    if _frozen(request, obj.session):
        return _detail(pk)
    return _activity_form(request, session=obj.session, instance=obj)


def _activity_form(request, session, instance):
    """The create and edit paths, which differ in exactly two places: the measurement and the exit.

    Hand-rolled rather than ``crud_create`` / ``crud_edit``, and for a concrete reason each way.
    ``crud_create`` builds its own bare instance, so the form would reach validation with no session
    and no tenant (see :func:`laborsession_add_activity`) and it has nowhere to stamp the standard.
    ``crud_edit`` redirects from inside itself, which leaves no seam for the activity-type warning
    below. Hand-rolling means the audit row each helper would have written is written here — with
    ``_changed(form)`` on the update leg, never a second copy of the redaction list.
    """
    is_edit = instance is not None

    if request.method == "POST":
        form = LaborActivityForm(
            request.POST,
            instance=instance if is_edit else LaborActivity(tenant=request.tenant, session=session),
            tenant=request.tenant)
        if form.is_valid():
            activity = form.save(commit=False)
            # Restated rather than trusted to the instance we constructed: the parent and the
            # workspace are the two facts this form must not be able to disagree with the URL about,
            # and restating them costs one assignment each.
            activity.tenant = request.tenant
            activity.session = session

            standard = None
            if not is_edit:
                standard = _stamp_standard(activity, session, request.tenant)
            activity.save()   # derives duration_minutes and the earned figure — see the model

            if is_edit:
                write_audit_log(request.user, activity, "update",
                                # The object repr names the activity, not the shift, and "which
                                # shift did this land on" is the first thing anybody asks of the log.
                                {**_changed(form), "session": session.number})
                messages.success(request, f"{activity.number} updated on {session.number}.")
                # Said out loud rather than silently re-measured — see laboractivity_edit.
                if "activity_type" in form.changed_data and activity.has_standard:
                    messages.warning(
                        request,
                        f"{activity.number} is still measured against the standard resolved when it "
                        "was first filed, for the previous activity type — the snapshot is never "
                        "rewritten after the fact. If the work really was a different job, delete "
                        "this row and book it again so it is measured against the right standard.")
                return _detail(activity.pk)

            write_audit_log(request.user, activity, "create", {
                "action": "add_activity",
                "session": session.number,
                "activity_type": activity.activity_type,
                "duration_minutes": activity.duration_minutes,
                # None, not 0 — the audit row must record "unmeasured", not "earned nothing".
                "standard": standard.number if standard is not None else None,
                "earned_minutes": (str(activity.earned_minutes)
                                   if activity.earned_minutes is not None else None),
            })
            messages.success(
                request,
                f"{activity.number} booked on {session.number} — "
                + (f"{activity.duration_minutes} minute(s) of "
                   f"{activity.get_activity_type_display().lower()}."
                   if activity.ended_at is not None else
                   f"{activity.get_activity_type_display().lower()}, still running."))
            # An unmeasured DIRECT row is worth a word: it is not an error, but it is the reason its
            # performance column will be blank, and blank with no explanation is what makes people
            # distrust the page. Indirect work is unmeasured by design and says nothing.
            if standard is None and activity.is_direct:
                messages.info(
                    request,
                    f"No active labor standard covers "
                    f"{activity.get_activity_type_display().lower()} at {session.location} on "
                    f"{_effective_day(activity, session)}, so these minutes are recorded as "
                    "UNMEASURED — earned minutes and performance stay blank rather than reading as "
                    "zero. Publish a standard and future bookings will be measured against it.")
            return _session_detail(session.pk)
        # No messages.error here: the bound form is re-rendered below with its own field errors, and
        # a banner repeating them is noise that pushes the actual fields off the screen.
    else:
        form = LaborActivityForm(
            instance=instance if is_edit else LaborActivity(tenant=request.tenant, session=session),
            tenant=request.tenant,
            # Only on create, and only as an INITIAL: the next stretch of a shift normally starts
            # where the last one ended, and every booking has to fall inside the clock window
            # anyway — so defaulting to the end of the last completed activity (or to clock-in on the
            # first) removes the module's most common validation failure without deciding anything.
            # A still-running activity has no end, so it falls through to clock-in rather than
            # seeding a blank.
            initial=None if is_edit else {"started_at": _next_start(session)})

    return render(request, "scm/labor/laboractivity/form.html", {
        "form": form,
        "is_edit": is_edit,
        # The form has NO `session` field by design, so the heading, the breadcrumb and the cancel
        # link can only get the parent from here.
        "session": session,
        "obj": instance,
    })


def _next_start(session):
    """Where the next booking most likely begins: the end of the last completed activity.

    One indexed query against ``(tenant, session)``, values-only. Falls back to ``clock_in`` when
    nothing has been booked yet or everything booked so far is still running.
    """
    return (session.activities.filter(ended_at__isnull=False)
            .order_by("-ended_at").values_list("ended_at", flat=True).first()
            or session.clock_in)


# ======================================================================================= the detail
@login_required
def laboractivity_detail(request, pk):
    """One booked interval, its measurement, and the live standard beside the snapshot.

    The live-vs-snapshot comparison IS the page. ``standard_fixed_snapshot`` /
    ``standard_rate_snapshot`` / ``standard_allowance_snapshot`` are what this row was measured
    against at file time; the ``live_*`` keys are what the same standard says TODAY. When
    ``snapshot_differs`` is True the standard has been re-timed since — and the figures on this page
    have not moved, which is the guarantee the four snapshot columns exist to provide. A supervisor
    who tightens a picking standard in March must not retroactively turn February's passing shifts
    into failing ones, and nobody could reproduce a number they were shown at the time if she could.

    ``live_earned_minutes`` is what this quantity WOULD earn under today's standard — shown as the
    contrast, never as the measurement. It is pure arithmetic on a row already fetched, so it costs
    nothing.

    ``standard_gone`` is a third state and not a variant of "unmeasured": the FK is ``SET_NULL``, so
    a deleted standard leaves ``has_standard`` True (it asks the SNAPSHOTS) with nothing to compare
    against. The page says "measured, and the standard it named has since been deleted" rather than
    silently showing an empty comparison.
    """
    obj = get_object_or_404(
        LaborActivity.objects.select_related(
            "session", "session__worker", "session__location", "standard", "standard__location",
            "standard__item_category", "pick_task", "putaway_task", "putaway_task__item",
            "putaway_task__to_location", "cycle_count_task", "cycle_count_task__location"),
        pk=pk, tenant=request.tenant, session__tenant=request.tenant)

    standard = obj.standard
    live_fixed = live_rate = live_allowance = live_earned = None
    if standard is not None:
        live_fixed = (standard.setup_minutes or ZERO) + (standard.travel_minutes or ZERO)
        live_rate = standard.minutes_per_unit
        live_allowance = standard.allowance_pct
        live_earned = standard.minutes_for(obj.quantity or ZERO)

    # Exactly ONE of the three task pointers can be set (LaborActivity.clean() enforces it), so the
    # template does not need three if-blocks and a rule about which wins — it gets the one that is
    # set and a kind to pick the url name from.
    linked_task, linked_task_kind = None, ""
    for name, kind in (("pick_task", "pick"), ("putaway_task", "putaway"),
                       ("cycle_count_task", "cycle_count")):
        if getattr(obj, f"{name}_id", None) is not None:
            linked_task, linked_task_kind = getattr(obj, name), kind
            break

    can_write = obj.session.status in LaborSession.EDITABLE_STATUSES
    return render(request, "scm/labor/laboractivity/detail.html", {
        "obj": obj,
        "session": obj.session,
        # Every one of these is None when unanswerable — a duration of zero has no rate, an
        # unmeasured row has no performance, and indirect time has no accuracy. Render an em dash.
        "duration_hours": obj.duration_hours,
        "earned_minutes": obj.earned_minutes,
        "performance_pct": obj.performance_pct(),
        "units_per_hour": obj.units_per_hour(),
        "accuracy_pct": obj.accuracy_pct(),
        # Asks the SNAPSHOTS, not the FK — see the model. A deleted standard does not unmeasure the
        # work it governed.
        "has_standard": obj.has_standard,
        "standard": standard,
        "standard_gone": obj.has_standard and obj.standard_id is None,
        "live_fixed_minutes": live_fixed,
        "live_rate": live_rate,
        "live_allowance": live_allowance,
        "live_earned_minutes": live_earned,
        "snapshot_differs": standard is not None and (
            live_fixed != obj.standard_fixed_snapshot
            or live_rate != obj.standard_rate_snapshot
            or live_allowance != obj.standard_allowance_snapshot),
        "linked_task": linked_task,
        "linked_task_kind": linked_task_kind,
        # Exactly the conditions the two write views enforce — offering a one-click failure is worse
        # than not offering the button. `can_delete` is the STATUS half only; the delete view is also
        # `@tenant_admin_required`, so the button additionally needs the admin wrapper (L/4.11).
        "can_edit": can_write,
        "can_delete": can_write,
        "frozen_reason": _frozen_reason(obj.session),
    })


# ======================================================================================= the delete
@tenant_admin_required
@require_POST
def laboractivity_delete(request, pk):
    """Remove one booked interval — only while its shift is still open.

    ``@require_POST`` so a GET is a 405 rather than a silent state change, and the row is resolved on
    both tenant columns BEFORE the status guard so a cross-tenant pk answers 404 rather than a 302
    that leaks "there is a row there, you just cannot delete it".

    **The freeze is enforced here and could not be enforced anywhere else.** A delete runs no
    ``clean()``, so ``LaborActivity.clean()``'s "the session must still be open" refusal — the one
    that guards every other write to this table — simply does not apply to this route. Without this
    guard, an approved shift's minutes could be removed one by one after the payroll export had
    already read them: the export would keep reporting hours no activity accounts for, the shift's
    booked minutes would fall while its attended minutes did not, and the difference would surface as
    invented GAP TIME against a named worker.

    Tenant-admin gated, like every other delete in the sub-module. There is no soft alternative to
    offer — an activity is a booking, not a document with a lifecycle — so the honest correction for
    a mis-booked stretch of work IS to remove it and file it again while the shift is open.

    Hand-rolled rather than delegated to ``crud_delete``: that helper re-fetches by pk with no
    knowledge of the parent-status guard it was never told about, so the guard would be advisory.
    The audit row is written inside the transaction, before the delete, while the row still exists to
    be described — and it rolls back with a delete that then fails, rather than recording a deletion
    that did not happen.
    """
    obj = get_object_or_404(
        LaborActivity.objects.select_related("session"),
        pk=pk, tenant=request.tenant, session__tenant=request.tenant)
    session = obj.session
    if _frozen(request, session):
        return _detail(pk)

    label = f"{obj.number} ({obj.duration_minutes} minute(s) of " \
            f"{obj.get_activity_type_display().lower()})"
    with transaction.atomic():
        # RE-CHECK under a row lock, not just at the top. The check above is the cheap early exit
        # that gives the user a message; this one is the guard. Between the two, a concurrent
        # `laborsession_approve` can land — and approval is the export lock, so the window is
        # exactly "minutes silently removed from a shift that has already been approved and may
        # already have been exported to payroll", which is the thing this view's docstring says the
        # guard exists to prevent. Every other destructive verb in 4.14 (`_transition`,
        # `laborsession_delete`, `laborplan_delete`) re-reads its parent inside `select_for_update`
        # for this reason; this one was the outlier.
        locked = (LaborSession.objects
                  .select_for_update()
                  .filter(pk=session.pk, tenant=request.tenant)
                  .first())
        if locked is None or _frozen(request, locked):
            return _detail(pk)
        write_audit_log(request.user, obj, "delete", {
            "action": "delete_activity",
            "session": session.number,
            "activity_type": obj.activity_type,
            "duration_minutes": obj.duration_minutes,
        })
        obj.delete()
    messages.success(request, f"{label} removed from {session.number}. The shift's booked minutes "
                              "and every figure derived from them have been recalculated.")
    return _session_detail(session.pk)

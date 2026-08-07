"""SCM 4.14 Labor Management — the three COMPUTED pages and the board's two bulk verbs.

``labor_board`` (Task Assignment) · ``labor_payroll_export`` (Payroll Integration) ·
``labor_scorecard`` (the productivity report the Performance Tracking bullet links out to), plus
``labor_board_assign`` / ``labor_board_unassign``.

**No new table and no new column anywhere in this file.** Every figure on all three pages is derived
at read time from rows that already exist — 4.4's ``PickTask`` / ``PutawayTask`` / ``CycleCountTask``
on the board, 4.14's ``LaborSession`` / ``LaborActivity`` on the other two. The ONLY write in the
module is the two bulk verbs stamping 4.4's **already-existing** ``assigned_to`` column, one row at a
time, with an audit entry each. **4.14 posts no ``StockMove`` and no ``JournalEntry``** (the standing
4.9-4.13 rule, L29) and this file creates no row of any kind.

**The payroll hand-off stops at a file.** ``hrm.AttendanceRecord`` (one row per employee per day),
``hrm.Timesheet`` and ``accounting.PayrollRun`` remain the systems of record; this page reads none of
them and writes none of them. ``apps/scm`` holds **zero ``hrm.*`` code references** and this module
adds none — the three names above appear here only as PROSE handed to the template so the page can
say out loud what it is deliberately not doing, exactly as ``LaborSessions.py`` already does. There
is no ``exported_at`` stamp either: ``approved`` IS the export lock, and a download page that wrote a
column would turn a refresh, a prefetch or a crawler into a state change.

**Grouped aggregates, never a per-worker loop.** The scorecard and the payroll export are TWO
grouped queries between them (:func:`_worker_aggregate`) — one ``GROUP BY worker`` over
``LaborSession`` and one over ``LaborActivity``. Calling ``LaborSession.performance_pct()`` per
worker would be the same arithmetic at one query per session per figure, which is the single biggest
performance trap available in this file. The board is likewise three queries (one per task table),
each with its progress figures ANNOTATED — ``PickTask.line_count()`` and ``CycleCountTask
.variance_count()`` are correct on a detail page and are a query per row on a console.

**Coverage, never a confident zero.** Every ratio here answers ``None`` on a zero denominator and
every page reports what it could NOT measure beside what it could: the payroll export names the
sessions in the window that are not yet approved, the scorecard names the workers below
``MIN_RANKED_MINUTES`` and the ones with no standard behind them, and the board names its own row
cap. All three render 200 on an empty tenant (the 4.11 ``supplier_disruption_score`` first-run
defect, priced in advance).

=================================================================================================
CONTEXT-VARIABLE CONTRACT (pinned, L7 — the templates are written by a separate pass, so every key
each page consumes is listed here, and **the row dicts are as much a contract as the page keys**).
=================================================================================================

``scm/labor/labor_board.html``
    Shared:      ``generated_at`` · ``no_tenant`` · ``no_tenant_note`` · ``board_note``
    Rows:        ``rows`` (list of BOARD ROW dicts, oldest first) · ``row_count`` · ``truncated``
                 (bool) · ``truncated_note`` · ``stale_count`` · ``oldest_age_hours``
                 (Decimal | None) · ``stale_after_hours``
    Groups:      ``by_assignee`` / ``by_zone`` (lists of GROUP dicts) · ``by_kind`` (list of
                 ``{"kind", "kind_label", "task_count"}``) · ``unassigned_rows`` ·
                 ``unassigned_count``
    Filters:     ``kind`` / ``assignee`` / ``zone`` / ``unassigned`` / ``q`` (the raw echoed GET
                 values — compare ``assignee`` and ``zone`` with ``u.pk|stringformat:"d"``, NEVER
                 ``|slugify``) · ``kind_choices`` · ``assignees`` (every login in the workspace, for
                 the FILTER) · ``assignable_users`` (ACTIVE logins only, for the assign control) ·
                 ``zones`` (Location queryset) · ``board_qs`` (the current filter re-encoded, for
                 the verb forms' hidden fields)
    Verbs:       ``max_bulk_assign`` — the id cap both verbs enforce.

    BOARD ROW dict (identical keys for all three kinds, so one table renders the lot)::

        kind          "pick" | "putaway" | "count"          kind_label   "Pick" / "Put-away" / …
        pk            int (the 4.4 row's own pk)            number       "PIK-00007"
        url           str, its 4.4 detail page              status       raw status value
        status_label  get_status_display()                  assignee_id  int | None
        assignee      str ("" when unassigned)              zone_id      int | None
        zone          str ("" when the kind has none)       created_at   datetime
        age_hours     Decimal | None                        age_days     int | None
        is_stale      bool                                  detail       str (what/where)
        progress      str ("8 lines", "3 of 12 counted")    line_count   int | None
        flag          str ("" when clean)                   flag_css     theme.css badge class | ""

    GROUP dict (``by_assignee`` and ``by_zone`` share it)::

        assignee_id / zone_id   int | None      assignee / zone   str ("Unassigned" / "No zone")
        task_count              int             oldest_age_hours  Decimal | None
        rows                    list of BOARD ROW dicts
        open_session            dict | None  (``by_assignee`` only — see _open_session_map)

``scm/labor/labor_payroll_export.html`` (and the identical ``?format=csv``)
    Window:      ``date_from`` / ``date_to`` (date) · ``date_from_raw`` / ``date_to_raw`` (echoed
                 verbatim) · ``window_invalid`` (bool) · ``period_label``
    Filters:     ``location`` / ``worker`` (raw echoed pks) · ``locations`` · ``workers`` ·
                 ``export_qs`` (the current filter re-encoded, for the CSV link)
    Rows:        ``rows`` (list of PAYROLL ROW dicts) · ``row_count`` · ``totals`` (one more PAYROLL
                 ROW dict, ``worker`` = "All workers")
    Coverage:    ``approved_session_count`` · ``pending_session_count`` · ``considered_count`` ·
                 ``coverage_pct`` (Decimal | None) · ``worker_count``
    Standing:    ``approved_only_note`` · ``no_writes_note`` · ``systems_of_record`` (list of
                 ``{"system", "owns"}``) · ``gap_note``
    Shared:      ``generated_at`` · ``no_tenant`` · ``no_tenant_note``

    PAYROLL ROW dict::

        worker_id int|None   worker str            work_days int        session_count int
        attended_hours Decimal|None                booked_hours Decimal
        direct_hours Decimal                       indirect_hours Decimal
        unaccounted_hours Decimal|None             over_booked_hours Decimal|None
        earned_hours Decimal|None                  performance_pct Decimal|None
        utilisation_pct Decimal|None

``scm/labor/labor_scorecard.html``
    Window:      ``date_from`` / ``date_to`` / ``date_from_raw`` / ``date_to_raw`` /
                 ``window_invalid`` / ``period_label``
    Filters:     ``location`` / ``worker`` (raw echoed pks) · ``locations`` · ``workers``
    Rows:        ``rows`` (list of SCORECARD ROW dicts, ranked first) · ``row_count`` · ``totals``
    Coverage:    ``ranked_count`` · ``unranked_count`` · ``measured_count`` · ``unmeasured_count`` ·
                 ``coverage_pct`` (Decimal | None) · ``session_count`` · ``open_session_count`` ·
                 ``coaching_count``
    Bands:       ``min_ranked_minutes`` · ``min_ranked_hours`` · ``coaching_threshold_pct`` ·
                 ``ranking_note`` · ``coaching_note`` · ``scope_note``
    Shared:      ``generated_at`` · ``no_tenant`` · ``no_tenant_note``

    SCORECARD ROW dict — the PAYROLL ROW keys ``worker_id`` / ``worker`` / ``work_days`` /
    ``session_count`` / ``attended_hours`` / ``booked_hours`` / ``direct_hours`` /
    ``indirect_hours`` / ``earned_hours`` / ``performance_pct`` / ``utilisation_pct`` mean exactly
    the same thing here (that is why they are spelled the same), PLUS::

        open_session_count int      measured_direct_hours Decimal   booked_minutes int
        units Decimal               errors Decimal                  units_per_hour Decimal|None
        accuracy_pct Decimal|None   is_ranked bool                  rank int|None
        needs_coaching bool         band_label str                  band_css theme.css class

**Every ``…_pct`` and every ``…_hours`` marked ``| None`` must render as an em dash, never as 0.**
A utilisation of 0% reads as "this worker did nothing"; a blank reads as "this has not been
measured", and on a page carrying named people that difference is the whole point. Badge classes
come from this module (``band_css`` / ``flag_css``) so no template invents one:
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css (L33).

POST payloads the two verbs read — neither takes a ``Form``, so the template names these explicitly:

* ``labor-board/assign/`` — REQUIRED ``task_kind`` (``pick`` | ``putaway`` | ``count``), REQUIRED
  ``assign_to`` (a User pk), REQUIRED repeated ``ids``.
* ``labor-board/unassign/`` — REQUIRED ``task_kind``, REQUIRED repeated ``ids``.
* Both ALSO accept the five filter params (``kind`` / ``assignee`` / ``zone`` / ``unassigned`` /
  ``q``) so the redirect lands back on the board the operator was looking at. The verb's own payload
  is deliberately named ``task_kind`` / ``assign_to`` rather than ``kind`` / ``assignee`` precisely
  so it cannot collide with those five — one form carries both.
* One POST assigns within ONE kind, because the three kinds are three different TABLES. The page's
  "select all" is therefore always within a kind, and each kind is capped at ``MAX_BULK_ASSIGN``
  rows, so a select-all can never exceed what the verb accepts.

Both verbs are ``@tenant_admin_required`` + ``@require_POST`` — they write another sub-module's
table — so wrap their controls in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}``; showing a member a button
they will 403 on is the 4.11 finding.
"""
import datetime
from decimal import InvalidOperation

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.http import urlencode

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _location_qs, _need_tenant
# The tenant's employee parties — the SAME set the session form's `worker` dropdown offers, so the
# two report filters cannot list people the module can never have booked a shift for. Imported from
# the forms toolkit rather than restated, exactly as MaintenanceWorkOrders.py:117 does.
from apps.scm.forms._common import _employee_parties
# The ONE CSV writer in the app: it applies `_csv_safe` to every cell (a value beginning = + - @ is
# executed as a FORMULA by Excel/LibreOffice on whoever opens the file, and Party.name is free text)
# and emits the UTF-8 BOM the prose rows need. Re-implementing either half here would be a second
# copy that drifts — the 4.12 report imports it across sub-modules for the same reason.
from apps.scm.views.SupplyChainAnalytics.Reports import _csv_response
# apply_search is the shared OR-of-icontains builder crud_list uses; the board hand-rolls its
# queryset (three models, three different open-status sets) but must not hand-roll the search.
from apps.core.crud import apply_search
# q2 lives in the MODELS toolkit — views/_common.py deliberately does not re-export it (the 4.11
# alert views and the 4.12 carbon report import it the same way).
from apps.scm.models._base import q2
from apps.scm.models import (COACHING_THRESHOLD_PCT, CycleCountTask, DIRECT_ACTIVITIES,
                             INDIRECT_ACTIVITIES, LaborActivity, LaborSession, MAX_BULK_ASSIGN,
                             MIN_RANKED_MINUTES, PickTask, PutawayTask, SESSION_STATUS_CHOICES)
# MIN_PERIOD_DATE / MAX_PERIOD_DATE bound the typed window. A date within a year of `date.min`
# makes the default-window arithmetic below raise OverflowError — a 500 on a value anybody can type
# into the address bar (the 4.12 `_parse_date` finding).
from apps.scm import analytics

User = get_user_model()

ZERO = Decimal("0")
_SIXTY = Decimal("60")
_ONE_HUNDRED = Decimal("100")
_SECONDS_PER_HOUR = Decimal("3600")
_MICROSECONDS_PER_MINUTE = Decimal("60000000")

#: The frozensets from ``_choices`` turned into ORDERED tuples once, at import. ``__in`` accepts any
#: iterable, but a frozenset iterates in an arbitrary order, so the same filter would compile to a
#: differently-ordered ``IN (…)`` on every process — different query-plan cache entries for one
#: query, and a diff nobody can read when two EXPLAINs are compared. The MEMBERSHIP is still the
#: shared frozenset's; only the ordering is pinned here.
_DIRECT = tuple(sorted(DIRECT_ACTIVITIES))
_INDIRECT = tuple(sorted(INDIRECT_ACTIVITIES))

#: Every session status except ``cancelled`` — what the SCORECARD measures. Derived from the
#: vocabulary rather than typed, so a status added to ``SESSION_STATUS_CHOICES`` later is scored
#: rather than silently dropped out of every productivity figure. A cancelled shift occupies no time
#: (``LaborSession.clean()`` excludes it from the overlap guard for the same reason) and must not
#: appear in a denominator.
_SCORED_SESSION_STATUSES = tuple(value for value, _label in SESSION_STATUS_CHOICES
                                 if value != "cancelled")

#: Rows fetched per task table on the board — a queryset SLICE, so the DATABASE applies it and it
#: bounds what is FETCHED rather than what is rendered (L40 §1: a guard that first builds the whole
#: thing is the payload, not a guard). Deliberately equal to ``MAX_BULK_ASSIGN``: the page's per-kind
#: "select all" is then always exactly what the verb will accept, so an operator can never be shown a
#: selection the POST refuses.
MAX_BOARD_ROWS = MAX_BULK_ASSIGN

#: Age at which an open task is chipped as stale. A DISPLAY BAND ONLY — nothing refuses, expires or
#: escalates on it, and a constant rather than "the mean age of the queue" for the L40 reason: a
#: threshold derived from the set it is grading moves with the data and stops being a threshold.
STALE_TASK_HOURS = Decimal("24")

#: Truthy spellings a checkbox / hand-built query string can carry. Matched case-insensitively so
#: ``?unassigned=True`` and ``?unassigned=on`` behave the same; anything else leaves the filter OFF
#: rather than raising (L11).
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

NO_TENANT_NOTE = ("This login has no tenant workspace, so there is no floor to report on. Sign in as "
                  "a workspace member to see labour figures.")

#: The standing note the payroll export carries. Written down ONCE, here, because it is the reason
#: the page has the shape it has and a paraphrase of it in a template would be the version that goes
#: stale. These are PROSE strings handed to the renderer — this module imports nothing from `hrm` and
#: queries nothing in it.
SYSTEMS_OF_RECORD = [
    {"system": "hrm.AttendanceRecord",
     "owns": "Daily attendance — one row per employee per day, with geofenced and biometric punches, "
             "regularisation and overtime approval. This page does not write it and does not read "
             "it; the two reconcile on (worker, work date) by eye, never by a foreign key."},
    {"system": "hrm.Timesheet",
     "owns": "Submitted and approved time for pay. A warehouse shift's activity breakdown is an "
             "execution record, not a timesheet line."},
    {"system": "accounting.PayrollRun",
     "owns": "The pay period accrual. It is a whole-company document with no employee lines and no "
             "hours columns, so drafting one from warehouse labour would be wrong rather than "
             "merely redundant — the hand-off is this CSV, and a human posts it."},
]

APPROVED_ONLY_NOTE = (
    "Only APPROVED sessions are aggregated here. A shift still open or closed-but-unsigned is "
    "counted under 'not yet approved' below and contributes nothing to the figures — approval IS "
    "the export lock, which is what stops a shift still being corrected on the floor from leaking "
    "into a pay period.")

NO_WRITES_NOTE = (
    "This page writes nothing at all — no export stamp, no status change, no ledger row. There is "
    "deliberately no 'exported_at' column: a download is a GET, and a GET that writes makes a "
    "refresh indistinguishable from a second export. 'Who downloaded what, when' is an audit-log "
    "question.")

GAP_NOTE = (
    "Unaccounted and over-booked hours are PERIOD nets — attended minus booked across the whole "
    "window, floored at zero in each direction. They are not the sum of each shift's own gap: a "
    "period figure is what a pay run is computed on. Per-shift exceptions live on the labour "
    "session list, which filters on them directly.")

BOARD_NOTE = (
    "This board writes exactly one column and it belongs to 4.4 Warehouse Management: the "
    "'assigned to' on a pick, put-away or cycle-count task. 4.14 declares no task table and adds no "
    "assignee column — assignment is a console over rows warehouse management already owns.")

RANKING_NOTE = (
    f"A worker is ranked only after {MIN_RANKED_MINUTES} booked minutes in the window. Their "
    "figures are still shown; they are simply left out of the ordering. Three booked minutes and "
    "one lucky pick computes at 900% of standard, and a ratio over a tiny denominator is noise "
    "wearing the costume of a result.")

COACHING_NOTE = (
    f"Sustained performance below {COACHING_THRESHOLD_PCT}% of standard is the industry's "
    "coaching prompt, and that is all this chip is — a conversation a supervisor has, not an "
    "incident a system files against a person. Nothing is raised, escalated or stored from it.")

SCOPE_NOTE = (
    "Every session except a cancelled one is scored here, including shifts still running — a "
    "supervisor needs today's numbers before anything has been signed off. That is the deliberate "
    "difference from the payroll export, which reads approved sessions and nothing else. A shift "
    "with no clock-out yet has no attended figure, so it is excluded from utilisation and counted "
    "separately instead.")


# =================================================================================================
# Small shared helpers
# =================================================================================================

def _parse_day(raw):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None`` if it is anything else.

    Returns None rather than raising, because the window comes out of the query string: a truncated
    or hand-typed ``?date_from=lastweek`` must drop the filter, never 500 (L11's rule applied to a
    date instead of an int). ``date.fromisoformat`` also raises ``ValueError`` on a value that is
    well FORMATTED but not a real day (``2026-02-30``), which is exactly as much "not a date".

    Clamped to the analytics period bounds for a second, separate reason: a date within a year of
    ``date.min`` makes the ``- timedelta(days=…)`` default-window arithmetic below raise
    ``OverflowError``, which is an uncaught 500 rather than a validation error.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    if not (analytics.MIN_PERIOD_DATE <= value <= analytics.MAX_PERIOD_DATE):
        return None
    return value


def _window(data, default_from, default_to):
    """Resolve ``?date_from=&date_to=`` against a page's own defaults.

    Reports whether a value was typed and rejected (``window_invalid``) so the page can say "showing
    the default window" rather than silently ignoring what somebody asked for, and SWAPS a reversed
    window instead of rendering nothing — a ``from`` after a ``to`` is a typo, not an empty result.
    """
    raw_from = (data.get("date_from") or "").strip()
    raw_to = (data.get("date_to") or "").strip()
    date_from, date_to = _parse_day(raw_from), _parse_day(raw_to)
    invalid = bool(raw_from and date_from is None) or bool(raw_to and date_to is None)
    if date_from is None:
        date_from = default_from
    if date_to is None:
        date_to = default_to
    if date_from > date_to:
        date_from, date_to = date_to, date_from
        invalid = True
    return {"date_from": date_from, "date_to": date_to,
            "date_from_raw": raw_from, "date_to_raw": raw_to,
            "window_invalid": invalid,
            "period_label": f"{date_from:%d %b %Y} to {date_to:%d %b %Y}"}


def _duration_minutes(value):
    """``Sum(clock_out - clock_in)`` as whole minutes, whatever the backend handed back.

    ``None`` in, ``None`` out — and that is load-bearing: a NULL sum means "no shift in this window
    had a clock-out", which is not zero attended minutes, it is an unanswerable question. Every
    figure built on attended time then answers ``None`` too, and the page prints an em dash.

    Django normalises a ``DurationField`` expression to ``timedelta`` on every backend it has to
    convert for, but this project runs MariaDB in development and SQLite under pytest, and
    ``crm/analytics.py:394`` records first-hand that a duration aggregate comes back as a float of
    MICROSECONDS on one and a ``timedelta`` on the other. A report that computes payroll hours is
    not the place to depend on which; both shapes are accepted here and neither can silently produce
    a figure 60,000,000x wrong.
    """
    if value is None:
        return None
    if isinstance(value, datetime.timedelta):
        return int(value.total_seconds() // 60)
    try:
        return int(Decimal(value) / _MICROSECONDS_PER_MINUTE)
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return None


def _hours(minutes):
    """Minutes as hours to 2dp. ``None`` in, ``None`` out — see :func:`_duration_minutes`."""
    if minutes is None:
        return None
    return q2(Decimal(minutes) / _SIXTY)


def _pct(numerator, denominator):
    """``numerator / denominator * 100``, or ``None`` when the denominator cannot carry a ratio.

    The single place a percentage is computed in this file, so no page can decide for itself that a
    zero denominator means 0%. It does not: it means unanswerable, and printing 0% against a named
    person is a claim the data does not support (the rule every derived figure on ``LaborSession``
    already follows).
    """
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return q2(Decimal(numerator) * _ONE_HUNDRED / Decimal(denominator))


def _age_hours(created_at, now):
    """Hours since ``created_at``, 2dp — the board's queue-age column."""
    if created_at is None:
        return None
    return q2(Decimal((now - created_at).total_seconds()) / _SECONDS_PER_HOUR)


def _encode(data, params):
    """Re-encode a WHITELIST of filter params as a query string.

    A whitelist rather than an echo of ``request.POST``: echoing would put ``csrfmiddlewaretoken``
    (and anything else an attacker appended to the form) into a URL that lands in the browser
    history, the referrer header and the server log. This is the same rule 4.11's ``_<page>_url``
    states, and it is what both the CSV link and the verbs' redirect are built from.
    """
    return urlencode({key: value for key, value in
                      ((key, (data.get(key) or "").strip()) for key in params) if value})


# =================================================================================================
# The per-worker aggregate — TWO grouped queries, shared by the scorecard and the payroll export
# =================================================================================================

def _worker_aggregate(tenant, *, statuses, date_from, date_to, location_id=None, worker_id=None):
    """``{worker_id: {raw minute / unit totals}}`` for one window, in exactly two queries.

    One ``GROUP BY worker`` over ``LaborSession`` (how many shifts, how many days, how many attended
    minutes) and one over ``LaborActivity`` (what those minutes went on). Both pages call this with
    the same signature and differ only in ``statuses``, which is what makes it impossible for the
    scorecard and the payroll export to disagree about what a "direct hour" is.

    **Why this is not a loop.** ``LaborSession`` already computes every one of these figures as a
    derived method, and calling them per worker would be one query per session per figure — the
    session detail page's shape applied to a whole warehouse. The methods stay the reference
    implementation and this stays their ``GROUP BY`` twin; the branch on ``DIRECT_ACTIVITIES`` /
    ``INDIRECT_ACTIVITIES`` is the same shared frozenset either way, so they cannot drift about
    which side of the line an activity falls on.

    Two details that are easy to get wrong and expensive to get wrong:

    * ``.order_by()`` before ``.values(…).annotate(…)`` is MANDATORY. Both models carry a
      ``Meta.ordering`` ending in ``-id``, and Django adds default-ordering columns to the
      ``GROUP BY`` — which would make every single row its own group and turn a per-worker report
      into a per-session one, silently and with no error anywhere.
    * ``measured_direct_minutes`` is direct minutes restricted to activities whose
      ``standard_minutes_snapshot`` is set, mirroring ``LaborSession._measured()`` exactly. Leaving
      unmeasured minutes in the denominator while they contribute nothing to the numerator is the
      same thing as scoring un-time-studied work as zero, which would drag a worker's performance
      down for doing a job nobody has written a standard for yet.
    """
    sessions = (LaborSession.objects.none() if tenant is None
                else LaborSession.objects.filter(tenant=tenant))
    sessions = sessions.filter(status__in=statuses, work_date__gte=date_from, work_date__lte=date_to)
    if location_id is not None:
        sessions = sessions.filter(location_id=location_id)
    if worker_id is not None:
        sessions = sessions.filter(worker_id=worker_id)

    # LaborActivity is scoped on its OWN tenant AND on session__tenant. The two can only ever agree
    # (LaborActivity.clean() refuses a cross-tenant session), which is exactly why both are stated:
    # a row that predates the guard — a fixture, a data migration, a direct DB edit — must drop out
    # of a payroll figure rather than be trusted because one of the two columns looked right.
    activities = (LaborActivity.objects.none() if tenant is None
                  else LaborActivity.objects.filter(tenant=tenant, session__tenant=tenant))
    activities = activities.filter(session__status__in=statuses,
                                   session__work_date__gte=date_from,
                                   session__work_date__lte=date_to)
    if location_id is not None:
        activities = activities.filter(session__location_id=location_id)
    if worker_id is not None:
        activities = activities.filter(session__worker_id=worker_id)

    attended_expr = models.ExpressionWrapper(F("clock_out") - F("clock_in"),
                                             output_field=models.DurationField())
    out = {}
    for row in (sessions.order_by()
                .values("worker_id", "worker__name")
                .annotate(
                    # DISTINCT on the DATE, not on the session: two shifts on one day is one work
                    # day, and a payroll figure that counted it twice would pay a day that was
                    # never worked.
                    work_days=Count("work_date", distinct=True),
                    session_count=Count("id"),
                    open_session_count=Count("id", filter=Q(clock_out__isnull=True)),
                    # SQL SUM skips the NULL that a still-running shift's (clock_out - clock_in)
                    # produces, so an open session contributes nothing here rather than zero.
                    attended=Sum(attended_expr))):
        out[row["worker_id"]] = {
            "worker_id": row["worker_id"],
            "worker": row["worker__name"] or "(unnamed)",
            "work_days": row["work_days"] or 0,
            "session_count": row["session_count"] or 0,
            "open_session_count": row["open_session_count"] or 0,
            "attended_minutes": _duration_minutes(row["attended"]),
            # Defaults for a worker who has sessions but has booked no activity against them at all
            # — a real and common state (a shift clocked in five minutes ago).
            "booked_minutes": 0, "booked_closed_minutes": 0,
            "direct_minutes": 0, "indirect_minutes": 0, "measured_direct_minutes": 0,
            "earned_minutes": None, "units": ZERO, "errors": ZERO,
        }

    for row in (activities.order_by()
                .values("session__worker_id")
                .annotate(
                    booked=Sum("duration_minutes"),
                    # Utilisation's numerator has to cover the same shifts its denominator does, or
                    # a worker with one shift still running reads as over-100% utilised: their
                    # booked minutes would count while their attended minutes could not.
                    booked_closed=Sum("duration_minutes",
                                      filter=Q(session__clock_out__isnull=False)),
                    direct=Sum("duration_minutes", filter=Q(activity_type__in=_DIRECT)),
                    indirect=Sum("duration_minutes", filter=Q(activity_type__in=_INDIRECT)),
                    # The denominator of performance: direct minutes on the activities that
                    # actually carried a standard. `standard_minutes_snapshot__isnull=False` is the
                    # exact SQL twin of `LaborSession._measured()`'s `row.earned_minutes is None`
                    # test — it asks the SNAPSHOT, not `standard_id`, so deleting a standard cannot
                    # retroactively unmeasure the work it once measured.
                    measured_direct=Sum("duration_minutes",
                                        filter=Q(activity_type__in=_DIRECT,
                                                 standard_minutes_snapshot__isnull=False)),
                    # NULL when nothing on the shift carried a standard — never 0. An unmeasured
                    # week has not earned zero minutes, it has not been measured, and the ratio
                    # below drops out entirely rather than printing 0%.
                    earned=Sum("standard_minutes_snapshot", filter=Q(activity_type__in=_DIRECT)),
                    units=Sum("quantity", filter=Q(activity_type__in=_DIRECT)),
                    errors=Sum("error_quantity", filter=Q(activity_type__in=_DIRECT)))):
        entry = out.get(row["session__worker_id"])
        if entry is None:
            # Unreachable while the two querysets share a window (an activity's session is always in
            # the session set), and handled anyway rather than KeyError-ing a payroll page.
            continue
        entry["booked_minutes"] = row["booked"] or 0
        entry["booked_closed_minutes"] = row["booked_closed"] or 0
        entry["direct_minutes"] = row["direct"] or 0
        entry["indirect_minutes"] = row["indirect"] or 0
        entry["measured_direct_minutes"] = row["measured_direct"] or 0
        entry["earned_minutes"] = row["earned"]
        entry["units"] = row["units"] or ZERO
        entry["errors"] = row["errors"] or ZERO
    return out


def _report_filters(request):
    """The two FK filters both report pages share, guarded and echoed.

    ``as_db_int`` rather than ``isdecimal()``: ``?worker=abc`` and ``?worker=²`` fail the latter but
    ``?worker=99999999999999999999`` passes it, converts cleanly and then raises inside the database
    driver. All three are the same thing — a value that is not a pk — and all three must SKIP the
    filter rather than 500 on a URL anybody can type into the address bar (L11).
    """
    return {
        "location_raw": (request.GET.get("location") or "").strip(),
        "worker_raw": (request.GET.get("worker") or "").strip(),
        "location_id": as_db_int(request.GET.get("location")),
        "worker_id": as_db_int(request.GET.get("worker")),
    }


# =================================================================================================
# 1. labor_payroll_export — approved sessions only, per worker, per period. NO WRITES.
# =================================================================================================

def _payroll_row(totals):
    """One worker's payroll line from their raw minute totals.

    ``unaccounted`` and ``over_booked`` are split rather than allowed to be one signed number, for
    the reason ``LaborSession.over_booked_minutes()`` exists: "48 minutes booked beyond the shift"
    is a badge scan or a forgotten stop and has a fix, while "−48 minutes of gap" is a number nobody
    can act on. Both are ``None`` while there is no attended figure to subtract from.
    """
    attended = totals["attended_minutes"]
    booked = totals["booked_minutes"]
    return {
        "worker_id": totals["worker_id"],
        "worker": totals["worker"],
        "work_days": totals["work_days"],
        "session_count": totals["session_count"],
        "attended_hours": _hours(attended),
        "booked_hours": _hours(booked),
        "direct_hours": _hours(totals["direct_minutes"]),
        "indirect_hours": _hours(totals["indirect_minutes"]),
        "unaccounted_hours": None if attended is None else _hours(max(attended - booked, 0)),
        "over_booked_hours": None if attended is None else _hours(max(booked - attended, 0)),
        "earned_hours": _hours(totals["earned_minutes"]),
        "performance_pct": _pct(totals["earned_minutes"], totals["measured_direct_minutes"]),
        "utilisation_pct": _pct(totals["booked_closed_minutes"], attended),
    }


def _sum_totals(entries, label):
    """The footer line: the raw MINUTE totals re-added, then re-derived — never the rows averaged.

    ``entries`` are :func:`_worker_aggregate` values, not finished row dicts, and that is the whole
    point: the totals line goes back through the same ``_payroll_row`` / ``_scorecard_row`` builder
    the individual rows did, over the summed minutes. Averaging the per-worker percentages instead
    would weight a three-minute worker the same as a full-time one, so the footer would disagree
    with the table above it — and ``work_days`` is deliberately a sum, i.e. person-days, which is
    what a pay run is computed on.
    """
    combined = {
        "worker_id": None, "worker": label,
        "work_days": sum(e["work_days"] for e in entries),
        "session_count": sum(e["session_count"] for e in entries),
        "open_session_count": sum(e["open_session_count"] for e in entries),
        "booked_minutes": sum(e["booked_minutes"] for e in entries),
        "booked_closed_minutes": sum(e["booked_closed_minutes"] for e in entries),
        "direct_minutes": sum(e["direct_minutes"] for e in entries),
        "indirect_minutes": sum(e["indirect_minutes"] for e in entries),
        "measured_direct_minutes": sum(e["measured_direct_minutes"] for e in entries),
        "units": sum((e["units"] for e in entries), ZERO),
        "errors": sum((e["errors"] for e in entries), ZERO),
    }
    # None unless SOMETHING was measured / attended — a workspace where nothing carried a standard
    # must show a blank, not a confident zero (the same rule as every row above it). A plain sum()
    # would have turned "nobody has been measured" into a total of 0 earned minutes, which reads as
    # a whole floor performing at 0%.
    attended = [e["attended_minutes"] for e in entries if e["attended_minutes"] is not None]
    combined["attended_minutes"] = sum(attended) if attended else None
    earned = [e["earned_minutes"] for e in entries if e["earned_minutes"] is not None]
    combined["earned_minutes"] = sum(earned, ZERO) if earned else None
    return combined


@login_required
def labor_payroll_export(request):
    """Approved sessions aggregated per worker for one pay period. **Reads only.**

    ``?format=csv`` streams the identical figures through the shared CSV writer, from the SAME
    aggregate call with the SAME window params (the 4.11 export precedent) — the file cannot show a
    different number from the page it was downloaded off.

    The window defaults to the current calendar month, which is the period somebody is normally
    looking at, and every date is guarded by :func:`_parse_day`. The coverage line beneath the table
    names the sessions in the window that are NOT yet approved: a payroll page that showed 0 hours
    for a worker whose whole week is sitting unsigned would be reporting an approval backlog as an
    attendance fact.
    """
    today = timezone.localdate()
    window = _window(request.GET, today.replace(day=1), today)
    filters = _report_filters(request)

    totals_by_worker = _worker_aggregate(
        request.tenant, statuses=("approved",),
        date_from=window["date_from"], date_to=window["date_to"],
        location_id=filters["location_id"], worker_id=filters["worker_id"])

    # Sorted by name so a period's file diffs cleanly against the previous one; a dict's insertion
    # order here is the database's row order, which nothing guarantees.
    ordered = sorted(totals_by_worker.values(), key=lambda t: (t["worker"].lower(), t["worker_id"]))
    rows = [_payroll_row(t) for t in ordered]

    # Coverage: one COUNT over the same window, split by approved / not. `Count(filter=…)` rather
    # than two queries, and it excludes cancelled sessions from BOTH halves — a withdrawn shift is
    # not an approval backlog.
    scope = (LaborSession.objects.none() if request.tenant is None
             else LaborSession.objects.filter(tenant=request.tenant))
    scope = scope.filter(status__in=_SCORED_SESSION_STATUSES,
                         work_date__gte=window["date_from"], work_date__lte=window["date_to"])
    if filters["location_id"] is not None:
        scope = scope.filter(location_id=filters["location_id"])
    if filters["worker_id"] is not None:
        scope = scope.filter(worker_id=filters["worker_id"])
    counts = scope.aggregate(approved=Count("id", filter=Q(status="approved")),
                             considered=Count("id"))
    approved_count = counts["approved"] or 0
    considered = counts["considered"] or 0

    context = {
        **window,
        "rows": rows,
        "row_count": len(rows),
        "totals": _payroll_row(_sum_totals(ordered, "All workers")) if ordered else None,
        "worker_count": len(rows),
        "approved_session_count": approved_count,
        "pending_session_count": considered - approved_count,
        "considered_count": considered,
        "coverage_pct": _pct(approved_count, considered),
        "location": filters["location_raw"],
        "worker": filters["worker_raw"],
        "locations": _location_qs(request.tenant),
        "workers": _employee_parties(request.tenant),
        "export_qs": _encode(request.GET, ("date_from", "date_to", "location", "worker")),
        "approved_only_note": APPROVED_ONLY_NOTE,
        "no_writes_note": NO_WRITES_NOTE,
        "gap_note": GAP_NOTE,
        "systems_of_record": SYSTEMS_OF_RECORD,
        "generated_at": timezone.localtime(),
        "no_tenant": request.tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
    }
    if (request.GET.get("format") or "").strip().lower() == "csv":
        return _payroll_csv(context)
    return render(request, "scm/labor/labor_payroll_export.html", context)


def _payroll_csv(context):
    """The same figures as a spreadsheet, provenance first.

    The header block is not decoration: a file that leaves the building has to carry the window it
    covers, the fact that it is approved-only, and the names of the systems that actually own pay —
    otherwise the first person to open it in a payroll office has no way to know any of that.

    ``None`` is written as ``n/a``, never as ``0``. A blank cell in a column somebody is about to
    total is the one place the "unanswerable, not zero" rule matters most.
    """
    def cell(value):
        return "n/a" if value is None else value

    def body():
        yield ["NavERP", "Labour payroll export", context["period_label"]]
        yield ["Generated", context["generated_at"].isoformat(timespec="seconds")]
        yield ["Window", context["date_from"].isoformat(), context["date_to"].isoformat()]
        yield ["Approved sessions", context["approved_session_count"]]
        yield ["Not yet approved (excluded)", context["pending_session_count"]]
        yield ["Coverage %", cell(context["coverage_pct"])]
        yield [APPROVED_ONLY_NOTE]
        yield [NO_WRITES_NOTE]
        yield [GAP_NOTE]
        for entry in SYSTEMS_OF_RECORD:
            yield ["System of record", entry["system"], entry["owns"]]
        yield []
        yield ["Worker", "Work days", "Sessions", "Attended hours", "Booked hours", "Direct hours",
               "Indirect hours", "Unaccounted hours", "Over-booked hours", "Earned hours",
               "Performance %", "Utilisation %"]
        for row in context["rows"] + ([context["totals"]] if context["totals"] else []):
            yield [row["worker"], row["work_days"], row["session_count"],
                   cell(row["attended_hours"]), cell(row["booked_hours"]),
                   cell(row["direct_hours"]), cell(row["indirect_hours"]),
                   cell(row["unaccounted_hours"]), cell(row["over_booked_hours"]),
                   cell(row["earned_hours"]), cell(row["performance_pct"]),
                   cell(row["utilisation_pct"])]

    # The filename is built from the RESOLVED window (already validated dates), never from raw GET
    # text — a request-controlled filename is a Content-Disposition header-injection problem and
    # there is no reason to have one.
    return _csv_response(
        f"labor-payroll-{context['date_from'].isoformat()}-to-{context['date_to'].isoformat()}.csv",
        body())


# =================================================================================================
# 2. labor_scorecard — per-worker productivity over a window
# =================================================================================================

def _scorecard_row(totals):
    """One worker's report card. Every ratio is ``None`` rather than 0 on a zero denominator.

    ``units_per_hour`` divides by ALL direct minutes while ``performance_pct`` divides by MEASURED
    direct minutes, and that asymmetry is deliberate and matches ``LaborSession`` exactly: units are
    a fact about every direct minute worked, whereas a performance ratio can only be stated over the
    minutes something was measured against.

    ``is_ranked`` gates only the ORDERING. A worker below ``MIN_RANKED_MINUTES`` still shows every
    figure they earned — hiding the row would make a short week look like an absence.
    """
    booked = totals["booked_minutes"]
    direct = totals["direct_minutes"]
    units = totals["units"]
    errors = totals["errors"]
    performance = _pct(totals["earned_minutes"], totals["measured_direct_minutes"])
    is_ranked = booked >= MIN_RANKED_MINUTES
    # The chip fires only on a RANKED row: calling a three-minute sample "below standard" against a
    # named person is precisely the unsupported claim MIN_RANKED_MINUTES exists to prevent.
    needs_coaching = (is_ranked and performance is not None
                      and performance < COACHING_THRESHOLD_PCT)
    if performance is None:
        band_label, band_css = "Not measured", "badge-muted"
    elif not is_ranked:
        band_label, band_css = "Below sample size", "badge-slate"
    elif needs_coaching:
        band_label, band_css = "Coaching band", "badge-amber"
    else:
        band_label, band_css = "At or above standard", "badge-green"
    return {
        "worker_id": totals["worker_id"],
        "worker": totals["worker"],
        "work_days": totals["work_days"],
        "session_count": totals["session_count"],
        "open_session_count": totals["open_session_count"],
        "attended_hours": _hours(totals["attended_minutes"]),
        "booked_minutes": booked,
        "booked_hours": _hours(booked),
        "direct_hours": _hours(direct),
        "indirect_hours": _hours(totals["indirect_minutes"]),
        "measured_direct_hours": _hours(totals["measured_direct_minutes"]),
        "earned_hours": _hours(totals["earned_minutes"]),
        "units": units,
        "errors": errors,
        "units_per_hour": (q2(units * _SIXTY / Decimal(direct)) if direct > 0 else None),
        "performance_pct": performance,
        "accuracy_pct": _pct(units - errors, units) if units > ZERO else None,
        "utilisation_pct": _pct(totals["booked_closed_minutes"], totals["attended_minutes"]),
        "is_ranked": is_ranked,
        "rank": None,          # filled in below, once the list is ordered
        "needs_coaching": needs_coaching,
        "band_label": band_label,
        "band_css": band_css,
    }


@login_required
def labor_scorecard(request):
    """Per-worker productivity over ``?date_from``/``?date_to``, ranked, with a coaching chip.

    This page exists because the **Performance Tracking** sidebar bullet points at the standards
    library, which is master data — so the productivity figures that bullet names live one click
    away behind a header chip rather than being a fourth tab nobody finds (the ``pm_forecast``
    precedent).

    Scored over every session except a cancelled one, INCLUDING shifts still running: a supervisor
    needs today's numbers before anything is signed off. That is the deliberate difference from the
    payroll export, which reads ``approved`` and nothing else — and it is why an open shift's booked
    minutes are kept out of the utilisation ratio (see ``booked_closed`` in
    :func:`_worker_aggregate`) rather than being divided by an attended figure that does not exist
    yet.

    Ordering is ranked-first, then by performance descending, then by name. Rows below
    ``MIN_RANKED_MINUTES`` keep every figure and simply carry no rank — a worker with three booked
    minutes at 900% of standard must not top a scorecard.
    """
    today = timezone.localdate()
    window = _window(request.GET, today - datetime.timedelta(days=29), today)
    filters = _report_filters(request)

    totals_by_worker = _worker_aggregate(
        request.tenant, statuses=_SCORED_SESSION_STATUSES,
        date_from=window["date_from"], date_to=window["date_to"],
        location_id=filters["location_id"], worker_id=filters["worker_id"])
    rows = [_scorecard_row(t) for t in totals_by_worker.values()]

    # Ranked rows first, then rows that HAVE a performance figure, then that figure descending, then
    # name. The tuple is compared element-wise so each position stays a single type — mixing a
    # Decimal and a None in one slot would raise, which is why "has a figure at all" is its own
    # position rather than a sentinel value substituted for None.
    rows.sort(key=lambda r: (0 if r["is_ranked"] else 1,
                             0 if r["performance_pct"] is not None else 1,
                             -(r["performance_pct"] if r["performance_pct"] is not None else ZERO),
                             r["worker"].lower()))
    rank = 0
    for row in rows:
        if row["is_ranked"] and row["performance_pct"] is not None:
            rank += 1
            row["rank"] = rank

    ranked_count = sum(1 for r in rows if r["is_ranked"])
    measured_count = sum(1 for r in rows if r["performance_pct"] is not None)
    return render(request, "scm/labor/labor_scorecard.html", {
        **window,
        "rows": rows,
        "row_count": len(rows),
        "totals": _scorecard_row(_sum_totals(list(totals_by_worker.values()), "All workers"))
                  if totals_by_worker else None,
        "ranked_count": ranked_count,
        "unranked_count": len(rows) - ranked_count,
        "measured_count": measured_count,
        "unmeasured_count": len(rows) - measured_count,
        # "How much of this floor is actually measured against a standard" — the number that tells a
        # reader whether the ranking above means anything. A page that reported only the ranking
        # would look equally confident on a workspace with one standard and on one with forty.
        "coverage_pct": _pct(measured_count, len(rows)),
        "coaching_count": sum(1 for r in rows if r["needs_coaching"]),
        "session_count": sum(r["session_count"] for r in rows),
        "open_session_count": sum(r["open_session_count"] for r in rows),
        "min_ranked_minutes": MIN_RANKED_MINUTES,
        "min_ranked_hours": _hours(MIN_RANKED_MINUTES),
        "coaching_threshold_pct": COACHING_THRESHOLD_PCT,
        "ranking_note": RANKING_NOTE,
        "coaching_note": COACHING_NOTE,
        "scope_note": SCOPE_NOTE,
        "location": filters["location_raw"],
        "worker": filters["worker_raw"],
        "locations": _location_qs(request.tenant),
        "workers": _employee_parties(request.tenant),
        "generated_at": timezone.localtime(),
        "no_tenant": request.tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
    })


# =================================================================================================
# 3. labor_board — the assignment console over 4.4's three open task queues
# =================================================================================================
#
# One spec per kind, and it is the single source of everything that differs between the three:
# which model, which statuses count as still-open, which column is the "zone", what a search
# matches, and which detail page a row links to. The board view, the two bulk verbs and the filter
# dropdown all read this table, so a kind cannot be open on the page and closed in the verb.

#: Still-open picks. Expressed as the UNION of the model's own two tuples rather than a hand-typed
#: ("pending", "released", "picking") — "still editable, or still pickable" IS the definition of an
#: open pick, and stated this way a status added to either tuple on the model appears on the board
#: automatically instead of silently vanishing from the queue.
_PICK_OPEN = tuple(dict.fromkeys(PickTask.EDITABLE_STATUSES + PickTask.PICKABLE_STATUSES))

#: A counted line disagreeing with what the ledger expected — the annotated twin of
#: ``CycleCountTaskLine.has_variance``. Written as two POSITIVE comparisons OR'd rather than as
#: ``~Q(counted=expected)``: a negated Q across a multi-valued relation compiles to a subquery, and
#: both halves already exclude an uncounted line for free because a comparison against NULL is
#: never true.
_VARIANCE_Q = (Q(lines__counted_quantity__gt=F("lines__expected_quantity"))
               | Q(lines__counted_quantity__lt=F("lines__expected_quantity")))


def _annotate_picks(qs):
    """Line count + short-pick flag, in the SAME grouped query the rows are fetched by.

    ``PickTask.line_count()`` is ``self.lines.count()`` and ``is_short()`` walks
    ``self.lines.all()`` — both correct on a detail page and both a query PER ROW on a console, i.e.
    up to 400 extra queries for one board. Two filtered ``Count``s over ONE reverse join instead.

    A filtered ``Count`` rather than the ``Exists`` this codebase normally prefers for an
    "are there any?" column (views/_common.py:20-23), and the exception is the point: that rule
    exists to avoid *introducing* a GROUP BY, and the line count has already introduced one. Adding
    an ``Exists`` here would put a correlated subquery into that GROUP BY for a figure the same
    aggregation can produce for free.

    The annotation is deliberately NOT called ``is_short``: an alias matching a model method
    shadows it on every instance the queryset returns, so the next reader calling
    ``task.is_short()`` would get a ``bool`` and a ``TypeError``.
    """
    return qs.annotate(
        line_total=Count("lines"),
        short_total=Count("lines", filter=Q(lines__quantity_picked__lt=F("lines__quantity_requested"))))


def _annotate_counts(qs):
    """Sheet size, lines counted, and lines disagreeing with the ledger — one join, three figures.

    ``CycleCountTask.variance_count(lines)`` takes a pre-fetched list precisely so a DETAIL page
    scans the sheet once; on a board that is still one scan per task. This is its ``GROUP BY`` twin
    and it reads the same rule — a counted line whose quantity differs from what was expected.
    """
    return qs.annotate(line_total=Count("lines"),
                       counted_total=Count("lines", filter=Q(lines__counted_quantity__isnull=False)),
                       variance_total=Count("lines", filter=_VARIANCE_Q))


def _pick_rows(tasks, now):
    """Board rows for open picks. ``tasks`` is already fetched and already annotated."""
    return [_row(task, "pick", now,
                 zone_id=task.zone_id,
                 zone=task.zone.code if task.zone_id else "",
                 detail=(task.get_strategy_display()
                         + (f" · wave {task.wave_ref}" if task.wave_ref else "")
                         + (f" · to {task.ship_to}" if task.ship_to else "")),
                 progress=f"{task.line_total} line(s)",
                 line_count=task.line_total,
                 flag="Short pick" if task.short_total else "",
                 flag_css="badge-red" if task.short_total else "")
            for task in tasks]


def _putaway_rows(tasks, now):
    """Board rows for open put-aways. One row is one item moving between two bins — no child table,
    so nothing to annotate and no progress figure to derive."""
    return [_row(task, "putaway", now,
                 zone_id=task.to_location_id,
                 zone=task.to_location.code if task.to_location_id else "",
                 detail=f"{task.item.sku} x {task.quantity}",
                 progress=f"{task.from_location.code} to {task.to_location.code}",
                 line_count=None, flag="", flag_css="")
            for task in tasks]


def _count_rows(tasks, now):
    """Board rows for open cycle counts. ``tasks`` is already fetched and already annotated."""
    return [_row(task, "count", now,
                 zone_id=task.location_id,
                 zone=task.location.code if task.location_id else "",
                 detail=f"{task.get_count_method_display()} · due {task.scheduled_date}",
                 progress=f"{task.counted_total} of {task.line_total} counted",
                 line_count=task.line_total,
                 flag=(f"{task.variance_total} variance(s)" if task.variance_total else ""),
                 flag_css="badge-amber" if task.variance_total else "")
            for task in tasks]


#: kind -> everything that differs between the three task tables. See the block comment above.
BOARD_KINDS = {
    "pick": {
        "kind": "pick", "label": "Pick", "model": PickTask, "statuses": _PICK_OPEN,
        "url_name": "scm:picktask_detail", "zone_lookup": "zone_id",
        "select_related": ("assigned_to", "zone"),
        "search_fields": ("number", "wave_ref", "ship_to"),
        "annotate": _annotate_picks, "rows": _pick_rows,
    },
    "putaway": {
        "kind": "putaway", "label": "Put-away", "model": PutawayTask,
        "statuses": PutawayTask.OPEN_STATUSES,
        "url_name": "scm:putawaytask_detail",
        # A put-away has no zone column; the DESTINATION bin is the place the work happens, which is
        # what a supervisor grouping "who is working where" actually means by zone.
        "zone_lookup": "to_location_id",
        "select_related": ("assigned_to", "item", "from_location", "to_location"),
        "search_fields": ("number", "item__sku", "to_location__code"),
        "annotate": None, "rows": _putaway_rows,
    },
    "count": {
        "kind": "count", "label": "Cycle count", "model": CycleCountTask,
        # The model's own EDITABLE_STATUSES is exactly ("scheduled", "in_progress") — the set that
        # is still actionable, which is what "open" means on this board.
        "statuses": CycleCountTask.EDITABLE_STATUSES,
        "url_name": "scm:cyclecounttask_detail", "zone_lookup": "location_id",
        "select_related": ("assigned_to", "location"),
        "search_fields": ("number", "location__code"),
        "annotate": _annotate_counts, "rows": _count_rows,
    },
}

#: (value, label) for the kind dropdown, built from the spec table so the filter can only ever offer
#: kinds the board actually knows how to render.
KIND_CHOICES = [(spec["kind"], spec["label"]) for spec in BOARD_KINDS.values()]

#: The board's filter params — the whitelist both the CSV-style link builder and the verbs' redirect
#: are rebuilt from. Deliberately NOT the same names as the verbs' own payload; see the module
#: docstring.
BOARD_FILTERS = ("kind", "assignee", "zone", "unassigned", "q")


def _row(task, kind, now, **extra):
    """The shared half of a board row — everything that is identical across the three kinds.

    Keeping the common keys in one place is what lets the template render pick, put-away and count
    rows through ONE loop; a per-kind row shape would mean three near-identical tables that drift.
    """
    spec = BOARD_KINDS[kind]
    age = _age_hours(task.created_at, now)
    return {
        "kind": kind,
        "kind_label": spec["label"],
        "pk": task.pk,
        "number": task.number or "",
        "url": reverse(spec["url_name"], args=[task.pk]),
        "status": task.status,
        "status_label": task.get_status_display(),
        "assignee_id": task.assigned_to_id,
        "assignee": str(task.assigned_to) if task.assigned_to_id else "",
        "created_at": task.created_at,
        "age_hours": age,
        "age_days": None if age is None else int(age / Decimal("24")),
        "is_stale": age is not None and age >= STALE_TASK_HOURS,
        **extra,
    }


def _board_queryset(spec, tenant, data):
    """One kind's open queue with the board's five filters applied, ordered oldest-first and SLICED.

    The slice is a DB ``LIMIT``, applied after every filter and before anything is built — a cap
    that first materialises the whole queue is the payload, not a cap (L40 §1). Oldest first because
    that is what the page is for: the row that has been waiting longest is the one somebody has to
    act on.

    Every int-valued param goes through ``as_db_int``, so ``?assignee=abc``, ``?assignee=²`` and
    ``?assignee=99999999999999999999`` each SKIP the filter rather than 500 (L11).
    """
    model = spec["model"]
    qs = (model.objects.none() if tenant is None
          else model.objects.filter(tenant=tenant, status__in=spec["statuses"]))
    qs = qs.select_related(*spec["select_related"])

    assignee = as_db_int(data.get("assignee"))
    if assignee is not None:
        qs = qs.filter(assigned_to_id=assignee)
    if (data.get("unassigned") or "").strip().lower() in _TRUE_VALUES:
        qs = qs.filter(assigned_to__isnull=True)
    zone = as_db_int(data.get("zone"))
    if zone is not None:
        qs = qs.filter(**{spec["zone_lookup"]: zone})
    # Every search field on all three kinds is either the row's own column or a FORWARD FK
    # (`item__sku`, `to_location__code`, `location__code`). A forward join narrows rows and can
    # never multiply one, which is what keeps the reverse-join Counts annotated below honest under
    # a search — a fanned-out row would double every line count on the board.
    qs = apply_search(qs, (data.get("q") or "").strip(), spec["search_fields"])
    if spec["annotate"] is not None:
        qs = spec["annotate"](qs)
    # +1 so the caller can tell "exactly at the cap" from "there is more behind it" without a
    # second COUNT over the same queue. Slicing LAST, so the LIMIT lands in the database and the
    # annotations are computed for the rows that survive it — not for the whole backlog (L40 §1).
    return qs.order_by("created_at", "id")[:MAX_BOARD_ROWS + 1]


def _open_session_map(tenant):
    """``(by login pk, by worker party pk)`` for the workspace's currently-open shifts.

    The board's optional "what is this assignee on right now" panel. ``LaborSession.login`` is set
    only by the self-service clock-in verb — a supervisor filing for somebody else leaves it null,
    which is the common case — so the panel falls back to the assignee's ``User.party`` matching the
    session's ``worker``, and renders perfectly well with NEITHER. It is a nicety on an assignment
    console, not a fact anything depends on: no figure, filter or verb reads it.

    One query, bounded, and both maps keep the MOST RECENT session per key (the queryset is ordered
    newest-first and ``setdefault`` keeps the first seen). A worker cannot legitimately have two
    open sessions — ``LaborSession.clean()`` refuses it — so this only decides what to show if one
    ever slipped through.
    """
    by_login, by_party = {}, {}
    if tenant is None:
        return by_login, by_party
    sessions = (LaborSession.objects.filter(tenant=tenant, status="open")
                .select_related("worker", "location")
                .order_by("-clock_in", "-id")[:MAX_BOARD_ROWS])
    for session in sessions:
        payload = {
            "id": session.pk,
            "number": session.number or "",
            "worker": session.worker.name if session.worker_id else "",
            "location": session.location.code if session.location_id else "",
            "since": session.clock_in,
        }
        if session.login_id:
            by_login.setdefault(session.login_id, payload)
        if session.worker_id:
            by_party.setdefault(session.worker_id, payload)
    return by_login, by_party


def _group(rows, key_id, key_label, empty_label):
    """Bucket board rows on one of their own keys, biggest queue first.

    Grouped on the ID, never on the LABEL: two locations that happen to share a code are two
    locations, and grouping on the printed string would silently merge them into one row (the 4.12
    carbon report's carrier-grouping finding).
    """
    buckets = {}
    for row in rows:
        bucket = buckets.setdefault(row[key_id], {
            key_id: row[key_id],
            key_label: row[key_label] or empty_label,
            "task_count": 0, "oldest_age_hours": None, "rows": [],
        })
        bucket["rows"].append(row)
        bucket["task_count"] += 1
        age = row["age_hours"]
        if age is not None and (bucket["oldest_age_hours"] is None
                                or age > bucket["oldest_age_hours"]):
            bucket["oldest_age_hours"] = age
    # Busiest first, then oldest, then name — a stable order, so the page does not reshuffle itself
    # between two loads of the same data.
    return sorted(buckets.values(),
                  key=lambda b: (-b["task_count"],
                                 -(b["oldest_age_hours"] or ZERO),
                                 str(b[key_label]).lower()))


@login_required
def labor_board(request):
    """The open pick / put-away / cycle-count queue, grouped by assignee, zone and kind.

    Three queries for the queues — ONE per task table, each carrying its own progress figures as
    annotations — plus one for the open-session panel and the small dropdown querysets. Nothing here
    is per-row: see :func:`_annotate_picks` and :func:`_annotate_counts` for the model methods this
    deliberately does not call and why.

    The page reads 4.4's rows and, through its two verbs, writes exactly one of 4.4's columns. It
    creates nothing, and 4.14 owns no task table — assignment is a console over what warehouse
    management already keeps.
    """
    now = timezone.now()
    kind = (request.GET.get("kind") or "").strip()
    # An unrecognised ?kind= shows EVERYTHING rather than nothing: a hand-typed or stale value must
    # not silently render an empty board that reads as "there is no work" (L11's posture — a bad
    # filter value is skipped, not obeyed).
    selected = [BOARD_KINDS[kind]] if kind in BOARD_KINDS else list(BOARD_KINDS.values())

    rows, truncated = [], False
    for spec in selected:
        fetched = list(_board_queryset(spec, request.tenant, request.GET))
        if len(fetched) > MAX_BOARD_ROWS:
            truncated = True
            fetched = fetched[:MAX_BOARD_ROWS]
        rows.extend(spec["rows"](fetched, now))
    # One ordering for the whole board, applied after the three kinds are merged: age is the point
    # of the page and it has to mean the same thing across them.
    rows.sort(key=lambda r: (-(r["age_hours"] or ZERO), r["kind"], r["number"]))

    by_login, by_party = _open_session_map(request.tenant)
    # Every login in the workspace, fetched once and used for THREE things: the filter dropdown, the
    # assign control (narrowed to active — see below) and the party lookup the open-session panel
    # needs. `_owner_qs`'s rule, applied here: the FILTER is deliberately wider than the assign
    # control, because "what is still assigned to somebody who has left" is exactly a question a
    # supervisor asks, while giving them new work is not.
    assignees = (User.objects.none() if request.tenant is None
                 else User.objects.filter(tenant=request.tenant).order_by("email"))
    users_by_pk = {user.pk: user for user in assignees}

    by_assignee = _group(rows, "assignee_id", "assignee", "Unassigned")
    for bucket in by_assignee:
        user = users_by_pk.get(bucket["assignee_id"])
        # `by_party` is built from THIS tenant's sessions, so a login pointing at another
        # workspace's party simply finds nothing — the fallback cannot leak a foreign shift.
        bucket["open_session"] = (
            by_login.get(user.pk) or (by_party.get(user.party_id) if user.party_id else None)
        ) if user is not None else None

    ages = [row["age_hours"] for row in rows if row["age_hours"] is not None]
    return render(request, "scm/labor/labor_board.html", {
        "rows": rows,
        "row_count": len(rows),
        "by_assignee": by_assignee,
        "by_zone": _group(rows, "zone_id", "zone", "No zone"),
        "by_kind": [{"kind": spec["kind"], "kind_label": spec["label"],
                     "task_count": sum(1 for r in rows if r["kind"] == spec["kind"])}
                    for spec in BOARD_KINDS.values()],
        "unassigned_rows": [r for r in rows if r["assignee_id"] is None],
        "unassigned_count": sum(1 for r in rows if r["assignee_id"] is None),
        "oldest_age_hours": max(ages) if ages else None,
        "stale_count": sum(1 for r in rows if r["is_stale"]),
        "stale_after_hours": STALE_TASK_HOURS,
        "truncated": truncated,
        "truncated_note": (f"Showing the {MAX_BOARD_ROWS} oldest tasks per kind. Narrow the board "
                           "with the filters above to see the rest — the cap is what keeps one "
                           "page load from fetching a whole warehouse's backlog."),
        "kind": kind,
        "assignee": (request.GET.get("assignee") or "").strip(),
        "zone": (request.GET.get("zone") or "").strip(),
        "unassigned": (request.GET.get("unassigned") or "").strip(),
        "q": (request.GET.get("q") or "").strip(),
        "kind_choices": KIND_CHOICES,
        "assignees": assignees,
        # The assign TARGET must be an active login: you cannot hand new work to an account that has
        # been switched off, and offering one is offering a one-click failure (the 4.12 rule).
        "assignable_users": (User.objects.none() if request.tenant is None
                             else User.objects.filter(tenant=request.tenant, is_active=True)
                             .order_by("email")),
        "zones": _location_qs(request.tenant),
        "board_qs": _encode(request.GET, BOARD_FILTERS),
        "max_bulk_assign": MAX_BULK_ASSIGN,
        "board_note": BOARD_NOTE,
        "generated_at": timezone.localtime(),
        "no_tenant": request.tenant is None,
        "no_tenant_note": NO_TENANT_NOTE,
    })


# ---------------------------------------------------------------------------------- the bulk verbs

def _board_redirect(request):
    """Back to the board the operator was looking at, rebuilt from a WHITELIST of the POSTed filters.

    Never an echo of ``request.POST`` — see :func:`_encode`.
    """
    query = _encode(request.POST, BOARD_FILTERS)
    return redirect(f"{reverse('scm:labor_board')}?{query}" if query
                    else reverse("scm:labor_board"))


def _bulk_assign(request, *, assign):
    """The shared body of both bulk verbs: cap, resolve, re-fetch, skip, write, audit.

    Written once because the two differ in exactly one thing — whether ``assigned_to`` ends up a
    User or NULL — and two copies of a guard ladder that writes another sub-module's table is how
    one of them quietly loses a check.

    The order of the steps is the security design, not an implementation detail:

    1. **The cap is measured on the raw POST list, before a single query.** An unbounded id list is
       an unbounded fetch-check-update-audit loop that any logged-in planner could fire from a
       hand-built form; counting after the first query has already lost. ``MAX_BULK_ASSIGN`` is a
       constant, never "the number of rows on the board" (L40). Django's own
       ``DATA_UPLOAD_MAX_NUMBER_FIELDS`` refuses a genuinely enormous payload before the view is
       even entered, but it is a global 1000 and this is the module's own bound — a limit that
       depends on a project-wide setting nobody set for this reason is not this page's limit.
    2. Every id goes through ``as_db_int`` and duplicates are dropped, so ``ids=abc``, ``ids=²``,
       an over-range value and five thousand copies of one pk all cost nothing and raise nothing.
    3. **The assignee is resolved against ``tenant=request.tenant``.** The dropdown is scoped, but a
       narrowed dropdown has never held against a crafted POST (L39 §2) — without this check a
       hand-built form could hand a warehouse's work to a login in another workspace, and no query
       anywhere would reveal it.
    4. Every id is RE-FETCHED with the tenant filter and the kind's own open statuses. A foreign pk
       and a pk that has since been picked, completed or cancelled are simply not in the result set:
       they are counted and reported, never 500'd and never written. That is also what makes this
       idempotent — replaying the POST finds the same rows already pointing at the same user and
       writes nothing.
    5. One narrow ``save(update_fields=…)`` and one audit row PER CHANGED ROW, inside one
       transaction. A row already assigned to the target is skipped, so a replay leaves no audit
       trail of a change that did not happen.
    """
    raw_ids = request.POST.getlist("ids")
    if len(raw_ids) > MAX_BULK_ASSIGN:      # step 1 — BEFORE any DB work
        messages.error(request, f"That request carried {len(raw_ids)} tasks and the limit is "
                                f"{MAX_BULK_ASSIGN} at a time. Narrow the board with the filters "
                                "and assign in batches.")
        return _board_redirect(request)
    if _need_tenant(request):
        return _board_redirect(request)

    spec = BOARD_KINDS.get((request.POST.get("task_kind") or "").strip())
    if spec is None:
        messages.error(request, "That request did not say which kind of task it was for — pick, "
                                "put-away or cycle count. Nothing was changed.")
        return _board_redirect(request)

    ids, seen = [], set()
    for raw in raw_ids:                     # step 2
        pk = as_db_int(raw)
        if pk is not None and pk not in seen:
            seen.add(pk)
            ids.append(pk)
    if not ids:
        messages.info(request, "No tasks were selected, so nothing was changed.")
        return _board_redirect(request)

    target = None
    if assign:                              # step 3
        target_pk = as_db_int(request.POST.get("assign_to"))
        if target_pk is not None:
            target = User.objects.filter(pk=target_pk, tenant=request.tenant,
                                         is_active=True).first()
        if target is None:
            messages.error(request, "Choose an active member of THIS workspace to assign the work "
                                    "to. Nothing was changed.")
            return _board_redirect(request)

    target_id = target.pk if target is not None else None
    changed, unchanged = 0, 0
    with transaction.atomic():
        # step 4 — the tenant filter and the open-status filter ARE the authorization check here.
        # `select_for_update` so two supervisors assigning the same task serialise instead of one
        # silently overwriting the other's audit row with no record that both happened.
        rows = list(spec["model"].objects
                    .filter(pk__in=ids, tenant=request.tenant, status__in=spec["statuses"])
                    .select_for_update())
        skipped = len(ids) - len(rows)
        for row in rows:                    # step 5
            if row.assigned_to_id == target_id:
                unchanged += 1
                continue
            before = row.assigned_to_id
            row.assigned_to = target
            row.save(update_fields=["assigned_to", "updated_at"])
            write_audit_log(request.user, row, "update", {
                "action": "assign" if assign else "unassign",
                "kind": spec["kind"],
                "assigned_to": [before, target_id],
            })
            changed += 1

    if changed:
        who = f"to {target}" if assign else "from their previous owner"
        messages.success(request, f"{changed} {spec['label'].lower()} task(s) reassigned {who}.")
    elif unchanged:
        messages.info(request, f"Every selected {spec['label'].lower()} task was already "
                               f"{'assigned to that person' if assign else 'unassigned'}.")
    if skipped:
        # Named rather than swallowed: "3 were skipped" is a fact somebody can go and check, while a
        # silent partial success teaches people the board lies about what it did.
        messages.warning(request, f"{skipped} selected task(s) were skipped — they have been picked, "
                                  "completed, cancelled or removed since the board was loaded, or "
                                  "they do not belong to this workspace.")
    return _board_redirect(request)


@tenant_admin_required
@require_POST
def labor_board_assign(request):
    """Hand a batch of open 4.4 tasks to one login. Admin-gated: it writes another module's table."""
    return _bulk_assign(request, assign=True)


@tenant_admin_required
@require_POST
def labor_board_unassign(request):
    """Return a batch of open 4.4 tasks to the unassigned queue. Same gate, same guards."""
    return _bulk_assign(request, assign=False)

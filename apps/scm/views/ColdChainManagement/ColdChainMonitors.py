"""SCM 4.15 Cold Chain Management — the ``ColdChainMonitor`` register, its profile and the detector.

Full CRUD (list / create / detail / edit / delete) plus three derived actions:
:func:`coldchainmonitor_profile` (bullet 4's temperature profile), :func:`coldchainmonitor_detect`
(one monitor) and :func:`coldchain_detect` (the whole-workspace sweep). Every measured figure on
every one of these pages is computed by ``apps/scm/coldchain.py`` from the reading ledger; this
module fetches rows, applies filters and renders — it does no temperature arithmetic of its own.

--------------------------------------------------------------------------------------------------
NOT ONE ``latest_reading()`` PER ROW — THE 4.13 ``asset_list`` FINDING, ONE SUB-MODULE OVER
--------------------------------------------------------------------------------------------------
``ColdChainMonitor.latest_reading()``, ``is_in_range()``, ``is_reporting()``, ``open_episode()`` and
``open_excursion_count()`` are all correct and every one of them QUERIES. Calling them from a
template over a page of monitors is five queries per row (and a Django template re-evaluates the
call every time it appears), which on a workspace with a few thousand probes is the exact shape 4.13
measured and forbade by name.

So the list page resolves all five for the WHOLE PAGE in a fixed number of queries:

* the newest reading's pk arrives as a correlated scalar subquery on the row query itself
  (:func:`_latest_reading_pk`), and the rows are then fetched with ONE ``in_bulk``;
* the resolved reading is handed BACK INTO the model's own accessors — ``range_chip(reading)`` and
  ``setpoint_gap(reading)`` both take one — so the page renders the model's answer rather than a
  second implementation of it;
* a monitor with no readings at all is handed :data:`_NO_READING` instead of ``None``. That matters:
  ``_reading_temperature(None)`` means *"go and look it up"*, so passing ``None`` would put the
  per-row query straight back for exactly the rows most likely to have no index entry to find;
* the open episode and the open-triage count are ONE query each over the page's monitor ids.

``is_reporting()`` is the single accessor with no injection point — it calls ``latest_reading()``
itself — so :func:`_reporting_chip` mirrors it here, over a reading the page already holds. It reads
the SAME ``STALE_INTERVAL_MULTIPLIER`` / ``MIN_LOGGING_INTERVAL_MINUTES`` the model reads and returns
the SAME ``(label, css)`` pairs. **If ``ColdChainMonitor.is_reporting()`` ever grows a ``reading=``
parameter, delete this helper and call the model.**

--------------------------------------------------------------------------------------------------
EVERY DERIVED FILTER IS APPLIED IN SQL, BEFORE PAGINATION
--------------------------------------------------------------------------------------------------
``range``, ``reporting`` and ``calibration`` are not columns — they are answers derived from the
newest reading, the clock and the limits. A filter applied in Python after ``paginate()`` would page
over the unfiltered set and quietly show the wrong rows on page 2, so all three are expressed as
``Q`` objects against annotations (see :func:`_range_q`, :func:`_reporting_q`, :func:`_calibration_q`)
and applied before the paginator ever runs.

``reporting`` needs ``last_reading_at + interval x 3 minutes >= now``, which is per-row datetime
arithmetic no portable ORM expression gives us. It is built instead as a UNION OF ONE ``Q`` PER
DISTINCT ``logging_interval_minutes`` in the workspace — one extra tiny query for the distinct set,
and a handful of OR'd terms in practice, because a workspace runs two or three logging intervals and
not two hundred.

--------------------------------------------------------------------------------------------------
CONTEXT-VAR CONTRACT (pinned, L7 — the templates are written by a separate agent)
--------------------------------------------------------------------------------------------------
Listed per page on each view below. **Every derived figure that can be ``None`` is named there**, so
the template renders an em dash rather than a confident zero: MKT on a frozen monitor,
``pct_in_range`` on an empty window, ``setpoint_gap`` with no setpoint, ``days_to_calibration_due``
with no certificate, and every chip's muted "Not recorded" state.

Badge colours come from the model's own ``*_CSS`` vocabularies. theme.css ships ``badge-green`` /
``badge-red`` / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate`` ONLY (L33).

**This module makes no Part 11 / Annex 11 conformance claim and no page it renders may.** Recording
who calibrated what and when is an audit TRAIL; it is not a validated system, there is no
e-signature, and over-claiming is worse than the gap.
"""
from datetime import datetime, time, timedelta

from django.db.models import ProtectedError
# `reverse` rather than a hand-built path: the detect sweep's redirect carries a `?after=` cursor, and
# a url name resolved through the URLconf cannot drift the way a literal string would.
from django.urls import reverse

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _location_qs, _need_tenant, _report_window

from apps.scm import coldchain
from apps.scm.forms import ColdChainMonitorForm
from apps.scm.models import (
    Asset,
    CALIBRATION_NOTICE_DAYS,
    ColdChainMonitor,
    DEVICE_TYPE_CHOICES,
    MAX_READING_WINDOW_DAYS,
    MIN_LOGGING_INTERVAL_MINUTES,
    MONITOR_STATUS_CHOICES,
    OPEN_EXCURSION_STATUSES,
    STALE_INTERVAL_MULTIPLIER,
    STORAGE_CONDITION_CHOICES,
    Shipment,
    TemperatureExcursion,
    TemperatureReading,
)


# =================================================================================================
# Page constants
# =================================================================================================

#: Rows in each child panel on the detail page. The cap is a queryset SLICE so the DATABASE applies
#: it — it bounds what is FETCHED, not merely what is rendered (L40 §1). One more than the cap is
#: fetched so the page can say it is showing a window without paying for a second COUNT.
MAX_PANEL_ROWS = 15

#: Points plotted on the profile chart. The reading table is the fastest-growing one in the
#: sub-module (~17.5k rows per monitor per year at the 30-minute default), so a 90-day window is
#: ~4,300 rows — a series no browser should be asked to draw and no template should be asked to
#: iterate. The page says how many it is showing out of how many exist.
MAX_CHART_POINTS = 500

#: The detail page's profile window. FIXED here on purpose: the date-range form lives on
#: ``profile.html``, and giving the 360° page a second, differently-defaulted window control is how
#: two pages come to print different percentages about the same fridge.
DETAIL_PROFILE_DAYS = 7

#: The profile page's default window when the query string names neither end. Seven days is what
#: somebody opening the page is normally asking about; the form takes it up to
#: :data:`~apps.scm.models.MAX_READING_WINDOW_DAYS`, and ``coldchain.clamp_window`` REPORTS the cap
#: rather than applying it silently.
DEFAULT_PROFILE_DAYS = 7

#: The three derived list filters. Declared here and passed to the template, because a filter
#: ``<select>`` with no context is the recurring bug the house rule exists to stop. None of the three
#: is a model vocabulary: there is no ``range``, ``reporting`` or ``calibration_status`` column, and
#: there deliberately never will be — each answer changes by the clock ticking, and a stored flag
#: would need something to run every night to stay true (the ``Asset.warranty_chip()`` ruling).
RANGE_CHOICES = [
    ("out", "Out of range now"),
    ("in", "In range now"),
    ("unknown", "Unknown (no reading, or no limits)"),
]
REPORTING_CHOICES = [
    ("live", "Reporting"),
    ("stale", "Not reporting"),
    ("never", "Never reported"),
]
CALIBRATION_CHOICES = [
    ("overdue", "Calibration overdue"),
    ("due", "Due within the notice window"),
    ("ok", "In calibration date"),
    ("not_recorded", "No certificate recorded"),
]

#: Which of the three subject FKs is set. Derived, not a column — the model resolves the same
#: question as ``subject_kind``, and this filter is the SQL half of it.
SUBJECT_CHOICES = [
    ("location", "Cold room / zone (Location)"),
    ("asset", "Reefer / chiller (Asset)"),
    ("shipment", "In-transit consignment (Shipment)"),
]

#: Printed on the calibration card and on the compliance report. Said once so the two pages cannot
#: explain the same record two different ways.
CALIBRATION_NOTE = (
    "Calibration is the one genuinely persistent artefact in this sub-module, because an "
    "uncalibrated sensor invalidates every record it produced. NavERP records the certificate date, "
    "its due date and its reference, and audits every change to them. That is an audit TRAIL — it "
    "is not 21 CFR Part 11 / EU Annex 11 conformance: there is no electronic signature, no "
    "re-authentication at signing and no validated-system evidence."
)

#: Printed beside the reading panels. ``source``, ``recorded_by`` and ``interval_minutes`` are all
#: stamped by whichever verb filed the row and are not typeable — a provenance a user can choose is
#: not a provenance, and a weight a user can retype is not a snapshot.
PROVENANCE_NOTE = (
    "How a reading reached the system, who filed it and the minutes it weighs are stamped by the "
    "verb that filed it — none of the three is a form field. The weight is snapshotted from the "
    "monitor at filing time, which is why changing this monitor's logging interval cannot restate "
    "last month's time-in-range or its mean kinetic temperature."
)


class _NoReading:
    """A stand-in for "this monitor has no readings", handed to the model's own accessors.

    ``ColdChainMonitor._reading_temperature(reading=None)`` means *"resolve the latest row"* and
    fires a query. There is no sentinel on the model for "we already looked and there is nothing",
    so the page supplies one: every accessor reads ``getattr(row, "temperature", None)``, so an
    object whose ``temperature`` is ``None`` makes ``is_in_range()`` / ``range_chip()`` /
    ``setpoint_gap()`` answer the honest "we cannot say" **without touching the database**.

    A class-level singleton (:data:`_NO_READING`) rather than an instance per row: it is immutable
    and nothing ever writes to it.
    """

    pk = None
    temperature = None
    humidity_pct = None
    reading_at = None

    def __bool__(self):
        # Falsy, so `reading or _NO_READING` in a template reads as "nothing here" — the object
        # exists only to stop a query, never to look like a measurement.
        return False


_NO_READING = _NoReading()


# =================================================================================================
# Scoping helpers for the 4.15 view modules
#
# Each returns `.none()` for a tenant-less caller rather than a filter on NULL, so a superuser
# (`tenant=None`) gets an empty dropdown instead of a filter that silently matches every workspace's
# rows — the `_item_qs` / `_location_qs` idiom from `views/_helpers.py`, verbatim.
#
# `_location_qs` is imported from `views/_helpers.py` because it is already there. `_asset_qs` and
# `_shipment_qs` are declared HERE rather than promoted to that module: 4.13 already carries a
# private `_asset_qs` of its own, and promoting either is a change to a file another session is
# appending to in this same working tree. Backend Package Structure rule 5 says a helper wanted by a
# second SUB-MODULE belongs in `_helpers.py` — that consolidation is a follow-up, and this comment is
# the note for whoever does it.
# =================================================================================================

def _asset_qs(tenant):
    """4.13's asset register, scoped — the ``?asset=`` dropdown on the monitor list."""
    if tenant is None:
        return Asset.objects.none()
    return Asset.objects.filter(tenant=tenant).order_by("code")


def _shipment_qs(tenant):
    """4.6's shipments, scoped — the ``?shipment=`` dropdown on the monitor list."""
    if tenant is None:
        return Shipment.objects.none()
    return Shipment.objects.filter(tenant=tenant).order_by("-id")


def _monitor_qs(tenant):
    """This workspace's monitors, for a ``?monitor=`` dropdown on any 4.15 page.

    ``select_related`` on the three subjects because every dropdown option renders ``__str__``, and
    ``ColdChainMonitor.__str__`` is "CCM-00001 · name" — which does NOT walk a subject, so nothing
    deeper is owed here. The joins are for the pages that render ``subject_label`` beside the option.
    """
    if tenant is None:
        return ColdChainMonitor.objects.none()
    return (ColdChainMonitor.objects.filter(tenant=tenant)
            .select_related("location", "asset", "shipment")
            .order_by("name", "id"))


# =================================================================================================
# The page's five per-row facts, resolved for the WHOLE page — see the module docstring
# =================================================================================================

def _latest_reading_pk(tenant):
    """The newest reading's pk per monitor, as a correlated scalar subquery.

    A SUBQUERY rather than ``annotate(Max("readings__reading_at"))``: the join form turns the whole
    monitor query into an aggregate query, which forces a ``GROUP BY`` that ``.count()`` cannot
    collapse and pushes every annotation-touching filter into a ``HAVING`` clause — where MariaDB
    then cannot resolve a plain column such as ``scm_ccm.min_temperature`` (the measured
    ``_spare_part_qs`` finding, ``views/AssetManagement/Reports.py:419-428``). The ``range`` filter
    compares the annotation AGAINST those columns, so the join form would raise
    ``OperationalError (1054) Unknown column ... in 'having clause'`` the first time somebody used it.

    The ordering mirrors ``ColdChainMonitor.latest_reading()`` exactly, ``-id`` tie-break included: a
    bulk import can land several rows on one timestamp and "the current value" has to be one
    deterministic row.

    ``tenant`` is passed as a LITERAL rather than ``OuterRef("tenant_id")`` — the scoping is
    identical, and a correlated tenant reference is one more outer column MySQL must resolve inside a
    dependent subquery. It is REDUNDANT and load-bearing either way: ``scm_tmp_tnt_mon_idx`` is
    ``(tenant, monitor, reading_at)`` and ``tenant_id`` is its LEADING column, so a subquery that
    states only ``monitor_id`` falls back to the plain FK index plus a filesort of that monitor's
    entire history (``TemperatureReadings.py:171-182`` — *every reader owes that line*).
    """
    return models.Subquery(
        TemperatureReading.objects
        .filter(tenant=tenant, monitor_id=OuterRef("pk"))
        .order_by("-reading_at", "-id")
        .values("pk")[:1],
        output_field=models.IntegerField())


def _latest_column(tenant, column, output_field):
    """The newest reading's ``column`` per monitor — the sibling of :func:`_latest_reading_pk`.

    Used ONLY by the derived ``range`` and ``reporting`` filters, and annotated only when one of them
    is actually requested: the common page load pays for one subquery, not three.
    """
    return models.Subquery(
        TemperatureReading.objects
        .filter(tenant=tenant, monitor_id=OuterRef("pk"))
        .order_by("-reading_at", "-id")
        .values(column)[:1],
        output_field=output_field)


def _range_q(bucket):
    """``Q`` for the ``?range=`` bucket, or ``None`` for "no filter".

    Requires ``latest_temperature`` to be annotated. The three buckets are the SQL twin of
    ``ColdChainMonitor.is_in_range()``, including its tri-state: **unknown is not out of range.** A
    monitor with no reading, or with no limit on either side, cannot be judged, and a page that
    rendered it red would cry wolf — after a week of that the red means nothing.

    The comparisons are STRICT (``<`` / ``>``), matching ``coldchain.out_of_range``: a reading
    exactly ON the limit is IN range, which is what "2 to 8 °C" means everywhere it is printed. A
    one-sided band is judged on the side it has, so each leg carries its own ``isnull=False`` term —
    which also keeps the expression from ever evaluating to SQL NULL, so ``~out`` is a clean
    complement.
    """
    has_reading = Q(latest_temperature__isnull=False)
    has_band = Q(min_temperature__isnull=False) | Q(max_temperature__isnull=False)
    out = (Q(min_temperature__isnull=False, latest_temperature__lt=F("min_temperature"))
           | Q(max_temperature__isnull=False, latest_temperature__gt=F("max_temperature")))
    if bucket == "out":
        return has_reading & has_band & out
    if bucket == "in":
        return has_reading & has_band & ~out
    if bucket == "unknown":
        return ~(has_reading & has_band)
    return None


def _reporting_q(tenant, bucket, now):
    """``Q`` for the ``?reporting=`` bucket, or ``None``. Requires ``latest_reading_at`` annotated.

    ``is_reporting()`` is ``now <= newest_reading_at + logging_interval x
    STALE_INTERVAL_MULTIPLIER`` — per-row datetime arithmetic, which no portable ORM expression
    gives us. So the live condition is assembled as **one OR'd term per DISTINCT
    ``logging_interval_minutes`` in the workspace**: the cutoff is computed in Python (where the
    multiplication is trivial) and the comparison stays a plain indexed range on the annotation.

    One extra query for the distinct set, and in practice two or three terms — a workspace runs a
    handful of logging intervals, not a hundred. The column is validated to 1..1440, so the union is
    bounded even in the pathological case.

    ``never`` is its own bucket and is NOT folded into ``stale``: "not yet commissioned" and "stopped
    reporting" are different problems with different fixes, which is exactly why the model answers
    ``None`` rather than ``False`` for the first (``ColdChainMonitors.py:469-481``).
    """
    if bucket == "never":
        return Q(latest_reading_at__isnull=True)
    if bucket not in ("live", "stale"):
        return None

    live = Q(pk__in=[])  # matches nothing — the honest identity for an OR fold
    intervals = (ColdChainMonitor.objects.filter(tenant=tenant)
                 .order_by()
                 .values_list("logging_interval_minutes", flat=True)
                 .distinct())
    for raw in intervals:
        # A 0 or NULL interval falls back to the validator's floor, exactly as the model does, but
        # the FILTER still names the raw stored value or it would match no row at all.
        effective = raw if raw else MIN_LOGGING_INTERVAL_MINUTES
        cutoff = now - timedelta(minutes=effective * STALE_INTERVAL_MULTIPLIER)
        live |= Q(logging_interval_minutes=raw, latest_reading_at__gte=cutoff)

    if bucket == "live":
        return Q(latest_reading_at__isnull=False) & live
    return Q(latest_reading_at__isnull=False) & ~live


def _calibration_q(bucket, today):
    """``Q`` for the ``?calibration=`` bucket, or ``None``. Pure column arithmetic — no annotation.

    The boundaries are derived from the SAME ``CALIBRATION_NOTICE_DAYS`` that
    ``ColdChainMonitor.calibration_chip()`` reads, so a row the filter puts in the "due" bucket
    renders the amber chip. Two statements of that window would let the page argue with itself.

    ``not_recorded`` is its own bucket and is never folded into ``ok``: no certificate on file is a
    data-completeness gap the compliance report lists separately, not a due date that has not
    arrived.
    """
    notice = today + timedelta(days=CALIBRATION_NOTICE_DAYS)
    if bucket == "overdue":
        return Q(calibration_due_on__lt=today)
    if bucket == "due":
        return Q(calibration_due_on__gte=today, calibration_due_on__lte=notice)
    if bucket == "ok":
        return Q(calibration_due_on__gt=notice)
    if bucket == "not_recorded":
        return Q(calibration_due_on__isnull=True)
    return None


def _reporting_chip(monitor, reading, now):
    """``(label, css)`` for "is this device still sending", from a reading the page ALREADY holds.

    **A deliberate mirror of ``ColdChainMonitor.reporting_chip()``, and the only one in this
    sub-module.** Every other chip on the list page is the model's own answer, because
    ``range_chip`` / ``setpoint_gap`` accept an injected reading and ``calibration_chip`` reads
    columns. ``is_reporting()`` takes only ``now`` and resolves the reading itself, so calling it per
    row is one query per row for one badge — the finding this module exists to avoid.

    It reads the same two constants the model reads and returns the same three pairs, so the only
    thing that could ever drift is the comparison itself. **Delete this the day
    ``is_reporting()`` grows a ``reading=`` parameter, and call the model instead.**

    ``None`` -> "No readings" (muted), never green: not knowing whether a probe is alive is not the
    same as knowing that it is.
    """
    moment = getattr(reading, "reading_at", None)
    if moment is None:
        return ("No readings", "badge-muted")
    interval = monitor.logging_interval_minutes or MIN_LOGGING_INTERVAL_MINUTES
    deadline = moment + timedelta(minutes=interval * STALE_INTERVAL_MULTIPLIER)
    return ("Reporting", "badge-green") if now <= deadline else ("Not reporting", "badge-red")


def _page_facts(tenant, monitors):
    """``(readings, open_episodes, open_counts)`` for one page of monitors — THREE queries, flat.

    ``readings`` is ``{reading_pk: TemperatureReading}``; ``open_episodes`` is
    ``{monitor_id: TemperatureExcursion}`` (the still-running one, ``ended_at IS NULL``);
    ``open_counts`` is ``{monitor_id: int}`` of excursions whose TRIAGE is still outstanding.

    The last two answer genuinely different questions and the model names them apart for that reason
    (``open_episode`` vs ``open_excursion_count``): an episode can be over while its investigation is
    wide open, and a page that conflated them would tell somebody an incident is still happening when
    it stopped yesterday.

    The episode dict is built from a queryset ordered ``("monitor_id", "started_at")`` so the LAST
    row per monitor — the newest — is the one that survives the comprehension, matching
    ``open_episode()``'s ``order_by("-started_at").first()``.
    """
    ids = [monitor.pk for monitor in monitors]
    if not ids:
        return {}, {}, {}

    reading_pks = {monitor.latest_reading_pk for monitor in monitors
                   if getattr(monitor, "latest_reading_pk", None)}
    readings = (TemperatureReading.objects
                .filter(tenant=tenant, pk__in=reading_pks)
                .select_related("recorded_by")
                .in_bulk()) if reading_pks else {}

    open_episodes = {
        episode.monitor_id: episode
        for episode in (TemperatureExcursion.objects
                        .filter(tenant=tenant, monitor_id__in=ids, ended_at__isnull=True)
                        .order_by("monitor_id", "started_at"))
    }

    # `.order_by()` is load-bearing: Meta.ordering is ["-started_at", "-id"], and an inherited ORDER
    # BY column would be dragged into the GROUP BY and split the count per timestamp (the
    # `pm_forecast` chip trap).
    open_counts = dict(
        TemperatureExcursion.objects
        .filter(tenant=tenant, monitor_id__in=ids, status__in=OPEN_EXCURSION_STATUSES)
        .order_by()
        .values_list("monitor_id")
        .annotate(n=Count("id")))

    return readings, open_episodes, open_counts


def _detect_message(request, summary):
    """Turn a ``coldchain.detect_excursions()`` summary into one sentence a person can act on.

    ``opened`` and ``closed`` deliberately OVERLAP — an episode that opened and closed inside one
    pass (which a back-dated logger import does constantly) counts in both — so the sentence names
    them separately rather than adding them up.

    ``skipped`` and ``more_remain`` are reported rather than swallowed: an ACTIVE monitor with no
    temperature limit can never be in or out of range, which is a configuration gap somebody has to
    be told about (the 4.11 "an alert with no threshold" finding), and a capped sweep that said
    nothing would look like a sweep that found nothing.

    **The two caps are told apart because they are continued differently**, and saying the wrong one
    is worse than saying nothing. A READING cap heals itself: each pass advances the watermark, so
    pressing again genuinely continues that monitor. A MONITOR cap does not — the sweep is ordered by
    id, so a cursor-less re-run walks the same first page again. That one is continued by the
    ``after`` cursor this view puts on the redirect and the list page posts back.
    """
    parts = [f"{summary['opened']} opened", f"{summary['extended']} updated",
             f"{summary['closed']} closed"]
    messages.success(request, "Detection pass complete — " + ", ".join(parts) + ".")
    if summary.get("skipped"):
        messages.warning(
            request,
            f"{summary['skipped']} active monitor(s) were skipped because they carry no temperature "
            "limit at all — without one, nothing can ever be in or out of range. Set at least an "
            "upper or a lower limit on each.")
    if summary.get("more_monitors"):
        messages.info(
            request,
            f"There are more monitors than one pass covers — this one stopped after monitor "
            f"#{summary.get('last_monitor_id')}. Run Detect again on the page you land on: the "
            "button carries a cursor and picks up at the next monitor rather than re-walking these.")
    elif summary.get("more_remain"):
        messages.info(
            request,
            "One monitor holds more unwalked readings than a single pass covers — run Detect again "
            "to continue from where this one stopped. Each pass moves the watermark forward, so the "
            "next one starts at the first reading this one did not reach.")


# =================================================================================================
# The register
# =================================================================================================
@login_required
def coldchainmonitor_list(request):
    """The monitoring-point register with the live chips that are the whole point of bullet 1.

    **Filter GET params** (every one applied BEFORE pagination):

    * ``q`` — free text over ``name`` / ``number`` / ``device_serial``
    * ``status`` — ``MONITOR_STATUS_CHOICES`` (string)
    * ``device_type`` — ``DEVICE_TYPE_CHOICES`` (string)
    * ``storage_condition`` — ``STORAGE_CONDITION_CHOICES`` (string)
    * ``subject`` — ``location`` / ``asset`` / ``shipment``, derived from which FK is set
    * ``location`` / ``asset`` / ``shipment`` — pks, through :func:`as_db_int` (L11: ``?asset=abc``,
      ``?asset=²`` and a 21-digit value all SKIP the filter rather than raising out of ``.filter()``)
    * ``range`` — ``in`` / ``out`` / ``unknown``, DERIVED from the newest reading vs the limits
    * ``reporting`` — ``live`` / ``stale`` / ``never``, DERIVED from the newest reading vs the clock
    * ``calibration`` — ``due`` / ``overdue`` / ``ok`` / ``not_recorded``, derived from the due date

    **Context**, exhaustively:

    * ``object_list`` — the paginated ``ColdChainMonitor`` queryset slice. Present for the house
      contract; **the table renders ``rows``**, which carries the same monitors plus their resolved
      facts.
    * ``rows`` — a LIST of dicts, one per monitor on this page:
      ``monitor`` (the model instance, three subjects joined), ``latest_reading``
      (``TemperatureReading`` or **``None``** — no reading has ever been filed), ``range_chip`` /
      ``reporting_chip`` / ``calibration_chip`` / ``status_chip`` (each a plain ``(label, css)``
      2-tuple — render ``.0`` and ``.1``), ``setpoint_gap`` (Decimal or **``None``**: no setpoint
      recorded, or no reading — a gap of 0 means "exactly on setpoint", which is a different
      statement), ``days_to_calibration_due`` (int, negative once past, or **``None``** when no
      certificate is on file), ``open_episode`` (``TemperatureExcursion`` or **``None``** — set means
      this monitor is OUT OF LIMITS RIGHT NOW) and ``open_excursion_count`` (int — outstanding
      TRIAGE, which is a different question).
    * ``page_obj`` — the paginator page (guard prev/next with ``has_previous`` / ``has_next``, L9).
    * ``q`` — the echoed search term.
    * Dropdown data: ``status_choices``, ``device_type_choices``, ``storage_condition_choices``,
      ``subject_choices``, ``range_choices``, ``reporting_choices``, ``calibration_choices`` (all
      lists of ``(value, label)`` pairs) and ``locations`` / ``assets`` / ``shipments`` (querysets).
      Compare pk params with ``|stringformat:"d"``, never ``|slugify``.
    * Workspace-wide chips (deliberately NOT recomputed per filter — "6 out of range" is a fact
      somebody must act on, and a number that changed as you browsed would be useless):
      ``total_count``, ``active_count``, ``out_of_range_count``, ``calibration_overdue_count``,
      ``calibration_missing_count``, ``open_excursion_count`` (all ints).
    * ``calibration_notice_days`` (int) and ``calibration_note`` (str).

    QUERIES: one for the page (with the newest-reading subquery folded in), one ``in_bulk`` for the
    page's readings, two for the page's episodes and triage counts, one aggregate plus two counts for
    the workspace chips, and one small ``DISTINCT`` only when ``?reporting=`` is used. Nothing scales
    with the number of rows on the page.
    """
    tenant = request.tenant
    today = timezone.localdate()
    now = timezone.now()

    qs = (ColdChainMonitor.objects.filter(tenant=tenant)
          .select_related("location", "asset", "shipment")
          .annotate(latest_reading_pk=_latest_reading_pk(tenant)))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q)
                       | Q(device_serial__icontains=q))

    for param, column in (("status", "status"), ("device_type", "device_type"),
                          ("storage_condition", "storage_condition")):
        value = (request.GET.get(param) or "").strip()
        if value:
            qs = qs.filter(**{column: value})

    subject = (request.GET.get("subject") or "").strip()
    if subject in ColdChainMonitor.SUBJECT_FIELDS:
        qs = qs.filter(**{f"{subject}__isnull": False})

    # L11 on all three: a GET value that is not a pk must SKIP the filter, never raise.
    for param, column in (("location", "location_id"), ("asset", "asset_id"),
                          ("shipment", "shipment_id")):
        pk = as_db_int(request.GET.get(param))
        if pk is not None:
            qs = qs.filter(**{column: pk})

    # --- the three DERIVED filters, in SQL, before pagination ------------------------------------
    range_bucket = (request.GET.get("range") or "").strip()
    reporting_bucket = (request.GET.get("reporting") or "").strip()
    calibration_bucket = (request.GET.get("calibration") or "").strip()

    # The two extra subqueries are annotated ONLY when a filter needs them — the common page load
    # pays for one correlated subquery, not three.
    if range_bucket:
        qs = qs.annotate(latest_temperature=_latest_column(
            tenant, "temperature", models.DecimalField(max_digits=6, decimal_places=2)))
        condition = _range_q(range_bucket)
        if condition is not None:
            qs = qs.filter(condition)
        else:
            range_bucket = ""  # junk narrowed nothing; the <select> must show "All"
    if reporting_bucket:
        qs = qs.annotate(latest_reading_at=_latest_column(
            tenant, "reading_at", models.DateTimeField()))
        condition = _reporting_q(tenant, reporting_bucket, now)
        if condition is not None:
            qs = qs.filter(condition)
        else:
            reporting_bucket = ""
    if calibration_bucket:
        condition = _calibration_q(calibration_bucket, today)
        if condition is not None:
            qs = qs.filter(condition)
        else:
            calibration_bucket = ""

    # STATED, not inherited from Meta, so page 2 is deterministic without the reader having to go and
    # check: `name` is not unique per tenant, so the `id` tie-break is load-bearing.
    page_obj = paginate(request, qs.order_by("name", "id"))
    monitors = list(page_obj.object_list)
    readings, open_episodes, open_counts = _page_facts(tenant, monitors)

    rows = []
    for monitor in monitors:
        reading = readings.get(monitor.latest_reading_pk) if monitor.latest_reading_pk else None
        # The sentinel, NOT None — see `_NoReading`. Passing None would mean "go and look it up".
        probe = reading if reading is not None else _NO_READING
        rows.append({
            "monitor": monitor,
            "latest_reading": reading,
            "range_chip": monitor.range_chip(probe),
            "reporting_chip": _reporting_chip(monitor, reading, now),
            "calibration_chip": monitor.calibration_chip(today),
            "status_chip": (monitor.get_status_display(), monitor.status_css),
            "setpoint_gap": monitor.setpoint_gap(probe),
            "days_to_calibration_due": monitor.days_to_calibration_due(today),
            "open_episode": open_episodes.get(monitor.pk),
            "open_excursion_count": open_counts.get(monitor.pk, 0),
        })

    # --- workspace-wide chips ---------------------------------------------------------------------
    chips = ColdChainMonitor.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        calibration_overdue=Count("id", filter=Q(calibration_due_on__lt=today)),
        calibration_missing=Count("id", filter=Q(calibration_due_on__isnull=True)))
    out_of_range_count = (ColdChainMonitor.objects.filter(tenant=tenant)
                          .annotate(latest_temperature=_latest_column(
                              tenant, "temperature",
                              models.DecimalField(max_digits=6, decimal_places=2)))
                          .filter(_range_q("out")).count())
    open_excursion_count = (TemperatureExcursion.objects
                            .filter(tenant=tenant, status__in=OPEN_EXCURSION_STATUSES).count())

    return render(request, "scm/coldchain/coldchainmonitor/list.html", {
        "object_list": monitors,
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        "status_choices": MONITOR_STATUS_CHOICES,
        "device_type_choices": DEVICE_TYPE_CHOICES,
        "storage_condition_choices": STORAGE_CONDITION_CHOICES,
        "subject_choices": SUBJECT_CHOICES,
        "range_choices": RANGE_CHOICES,
        "reporting_choices": REPORTING_CHOICES,
        "calibration_choices": CALIBRATION_CHOICES,
        # The RESOLVED buckets, not request.GET — a junk `?range=foo` narrowed nothing, so the
        # <select> must show "All" rather than an option that did not happen.
        "range_bucket": range_bucket,
        "reporting_bucket": reporting_bucket,
        "calibration_bucket": calibration_bucket,
        "locations": _location_qs(tenant),
        "assets": _asset_qs(tenant),
        "shipments": _shipment_qs(tenant),
        "total_count": chips["total"] or 0,
        "active_count": chips["active"] or 0,
        "out_of_range_count": out_of_range_count,
        "calibration_overdue_count": chips["calibration_overdue"] or 0,
        "calibration_missing_count": chips["calibration_missing"] or 0,
        "open_excursion_count": open_excursion_count,
        "calibration_notice_days": CALIBRATION_NOTICE_DAYS,
        "calibration_note": CALIBRATION_NOTE,
    })


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def coldchainmonitor_create(request):
    """Deploy a monitoring point. ``crud_create`` stamps the tenant, audits and refuses a
    tenant-less user.

    ``ColdChainMonitorForm.__init__`` ALSO stamps the tenant onto the unsaved instance, and that is
    not redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so without the
    form-side stamp THREE of ``ColdChainMonitor.clean()``'s nine rules — the cross-tenant FK guard,
    the subject-freeze check and the one-active-monitor-per-serial rule — would validate an instance
    whose ``tenant_id`` is ``None``, which is the exact case every one of them skips. They would be
    dead code on the create path, and the create path is the one a crafted POST takes.

    Context: ``form``, ``is_edit`` (``False``), ``storage_condition_ranges_note`` (str — the
    ``STORAGE_CONDITION_RANGES`` pre-fill is a SUGGESTION and the explicit limits are what apply),
    ``subject_rule_note`` (str — the exactly-one-subject rule, stated ABOVE the three FK fields
    rather than only in the error message).
    """
    if _need_tenant(request):
        return redirect("scm:coldchainmonitor_list")
    return crud_create(request, form_class=ColdChainMonitorForm,
                       template="scm/coldchain/coldchainmonitor/form.html",
                       success_url="scm:coldchainmonitor_list",
                       extra_context={
                           "storage_condition_ranges_note": STORAGE_PREFILL_NOTE,
                           "subject_rule_note": SUBJECT_RULE_NOTE,
                       })


@login_required
def coldchainmonitor_edit(request, pk):
    """Editable at any status, deliberately — but what it WATCHES freezes once readings exist.

    A monitor row describes a live configuration that legitimately gets renamed, re-banded and
    re-calibrated, and a retired deployment is often the row that most needs correcting. Nothing an
    edit can reach is a derived figure: in range, in the warning band, still reporting, calibration
    due, the open episode and the setpoint gap have no columns at all, so there is nothing here for a
    form to restate.

    The one thing an edit CANNOT do is re-point the subject once readings exist —
    ``ColdChainMonitor.clean()`` rule (3) refuses it, because last quarter's "Cold Room 2 was in range
    99.4% of the time" must not silently become a statement about Cold Room 5.

    Widening the limits on a monitor with a RUNNING episode is legal and its effect is deliberate:
    the detector judges an extension against the CURRENT limits while the excursion keeps the ones
    snapshotted when it fired, so the incident can end. Judging an extension against the snapshot
    would leave it open forever after a legitimate re-band.

    Context: ``form``, ``obj``, ``is_edit`` (``True``), the same two notes as the create page, plus
    ``subject_label`` (str) and ``has_readings`` (bool) — **both computed HERE, because the template
    may not ask the database** (house rule 9). The page used to render ``obj.subject_label``,
    ``obj.readings.count``, ``obj.excursions.count`` and ``obj.readings.exists`` itself: two of those
    are unbounded ``COUNT``s over the highest-volume table in the sub-module (~17,500 rows per
    monitor per year), they fired on every draw of the form for a decorative figure the detail page
    already reports, and going through the related manager states no ``tenant`` — so they could not
    open ``scm_tmp_tnt_mon_idx``, whose LEADING column it is (the rule ``latest_reading()`` states in
    as many words). The two counts are gone from the page; the one fact the FORM needs is
    ``has_readings``, asked as a tenant-scoped ``EXISTS`` that stops at the first row.

    The monitor is fetched here with its three subjects joined so ``subject_label`` costs no lazy FK
    query either. ``crud_edit`` fetches its own copy — one primary-key hit, and the price of leaving
    the shared helper alone.
    """
    monitor = get_object_or_404(
        ColdChainMonitor.objects.select_related("location", "asset", "shipment"),
        pk=pk, tenant=request.tenant)
    # `tenant=` is REDUNDANT AND LOAD-BEARING — the same line every reader of this table owes.
    has_readings = (TemperatureReading.objects
                    .filter(tenant=request.tenant, monitor_id=monitor.pk).exists())
    return crud_edit(request, model=ColdChainMonitor, pk=pk, form_class=ColdChainMonitorForm,
                     template="scm/coldchain/coldchainmonitor/form.html",
                     success_url="scm:coldchainmonitor_list",
                     extra_context={
                         "storage_condition_ranges_note": STORAGE_PREFILL_NOTE,
                         "subject_rule_note": SUBJECT_RULE_NOTE,
                         "subject_label": monitor.subject_label,
                         "has_readings": has_readings,
                     })


@tenant_admin_required
@require_POST
def coldchainmonitor_delete(request, pk):
    """Delete a monitor — refused while any excursion references it.

    ``TemperatureExcursion.monitor`` is ``PROTECT`` deliberately: an episode is EVIDENCE and carries
    its own snapshotted limits, so it stays readable forever and must outlive the device being
    retired. This pre-checks and refuses with a sentence naming the blocker, and ALSO catches
    ``ProtectedError`` — the pre-check is the good message, the catch is what stops a detection pass
    landing an episode between the check and the delete from becoming an uncaught 500 (the 4.10
    ``currency_delete`` finding, priced in advance rather than after).

    What DOES go with the monitor is said out loud, and only after the delete actually succeeded:
    ``TemperatureReading.monitor`` is ``CASCADE``, so **the entire append-only reading history is
    removed with it** and cannot be reconstructed from anything. The three subjects are ``PROTECT``
    on the other side, so no cold room, reefer or shipment is touched.

    Tenant-admin gated for exactly that reason, and because ``status="retired"`` — a plain edit — is
    the move that keeps the record. That is why the status vocabulary has ``retired`` and ``lost`` in
    it at all.
    """
    obj = get_object_or_404(ColdChainMonitor, pk=pk, tenant=request.tenant)

    episodes = obj.excursions.count()
    if episodes:
        messages.error(
            request,
            f"{obj.number} still has {episodes} temperature excursion(s) and cannot be deleted — "
            "each one is the evidence record of an incident, with the limits that were in force when "
            "it fired snapshotted onto it. Set this monitor's status to Retired instead; a retired "
            "deployment stops being detected against and keeps its whole history.")
        return redirect("scm:coldchainmonitor_detail", pk=pk)

    # Counted BEFORE the delete, while the rows still exist to be counted.
    readings = obj.readings.count()

    try:
        with transaction.atomic():
            # atomic() so the audit row `crud_delete` writes BEFORE deleting rolls back with a
            # delete that then fails.
            response = crud_delete(request, model=ColdChainMonitor, pk=pk,
                                   success_url="scm:coldchainmonitor_list")
    except ProtectedError:
        # Generic rather than an enumeration: only TemperatureExcursion PROTECTs this table today,
        # and an enumeration would go stale silently the first time something else pointed here.
        messages.error(
            request,
            f"{obj.number} is referenced by another record and cannot be deleted. Set its status to "
            "Retired instead — that stops it being detected against and keeps its history.")
        return redirect("scm:coldchainmonitor_detail", pk=pk)

    if readings:
        messages.info(request, f"{readings} temperature reading(s) were removed with it — the "
                               "reading ledger cascades off the deployment that defines its limits.")
    return response


# =================================================================================================
# The 360° page
# =================================================================================================
@login_required
def coldchainmonitor_detail(request, pk):
    """What this monitor watches, what it is reading, and what it has done lately.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.ColdChainMonitor`, all three subjects joined. Safe to
      ask for ``subject`` / ``subject_kind`` / ``subject_label`` / ``status_css`` /
      ``is_frozen_condition`` — none of them queries.
    * **Live state** — ``latest_reading`` (``TemperatureReading`` or **``None``**), ``range_chip`` /
      ``reporting_chip`` / ``calibration_chip`` (each a ``(label, css)`` 2-tuple),
      ``in_warning_band`` (``True`` / ``False`` / **``None``** — no reading, no margin or no limits),
      ``setpoint_gap`` (Decimal or **``None``**), ``days_to_calibration_due`` (int or **``None``**),
      ``limit_min`` / ``limit_max`` (Decimal or **``None``** — a ONE-SIDED band is legitimate and
      must render as "no lower limit", not as 0).
    * **Profile** — ``profile`` (the ``coldchain.profile()`` dict; **``count``, ``first_at``,
      ``last_at``, ``min``, ``max``, ``mean``, ``in_range_minutes``, ``out_minutes``,
      ``pct_in_range`` and ``mkt`` are ALL ``None`` on an empty window, never 0**, and ``mkt`` is
      additionally ``None`` for a frozen / deep-frozen / cryogenic monitor because USP <1079.2> says
      it does not apply — print an em dash plus that note, never 0.00), ``profile_days`` (int) and
      ``profile_window`` (a ``(date_from, date_to)`` 2-tuple).
    * **Readings panel** — ``readings`` (a LIST, newest first, capped at :data:`MAX_PANEL_ROWS`),
      ``readings_truncated`` (bool), ``reading_count`` (int, the monitor's whole history).
    * **Excursions panel** — ``open_episode`` (``TemperatureExcursion`` or **``None``** — set means
      it is out of limits RIGHT NOW), ``excursions`` (a LIST, newest first, capped),
      ``excursions_truncated`` (bool), ``excursion_count`` and ``open_excursion_count`` (ints — the
      second is outstanding TRIAGE, a different question from ``open_episode``).
    * **Notes** — ``calibration_note``, ``provenance_note``, ``append_only_note`` (strs).
    * ``can_delete`` (bool — ``True`` only when no excursion references the monitor; **gate the
      Delete button on it**, since that is exactly what :func:`coldchainmonitor_delete` enforces and
      offering a one-click failure is worse than not offering it). Delete, Import and both Detect
      buttons are tenant-admin only, so wrap them in
      ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a member a
      button they will 403 on is the 4.11 finding.

    QUERIES: one for the monitor, one for the readings panel, one for the reading count, one for the
    excursions panel, one aggregate for the two excursion counts, and the profile's own two. The
    latest reading is taken from the readings panel rather than re-queried — the panel is ordered
    ``("-reading_at", "-id")`` under the same tenant predicate, so its first row IS what
    ``latest_reading()`` answers with.
    """
    obj = get_object_or_404(
        ColdChainMonitor.objects.select_related("location", "asset", "shipment"),
        pk=pk, tenant=request.tenant)

    today = timezone.localdate()
    now = timezone.now()

    # The "redundant" tenant= is load-bearing: `scm_tmp_tnt_mon_idx` is (tenant, monitor,
    # reading_at) and `tenant_id` is its LEADING column, so without it MariaDB falls back to the
    # plain FK index plus a filesort over this monitor's entire history.
    readings = list(obj.readings.filter(tenant=request.tenant)
                    .select_related("recorded_by")
                    .order_by("-reading_at", "-id")[:MAX_PANEL_ROWS + 1])
    readings_truncated = len(readings) > MAX_PANEL_ROWS
    del readings[MAX_PANEL_ROWS:]
    latest_reading = readings[0] if readings else None
    probe = latest_reading if latest_reading is not None else _NO_READING
    reading_count = obj.readings.filter(tenant=request.tenant).count()

    excursions = list(obj.excursions.filter(tenant=request.tenant)
                      .select_related("non_conformance", "maintenance_work_order",
                                      "lot_serial", "lot_serial__item")
                      .order_by("-started_at", "-id")[:MAX_PANEL_ROWS + 1])
    excursions_truncated = len(excursions) > MAX_PANEL_ROWS
    del excursions[MAX_PANEL_ROWS:]
    episode_counts = obj.excursions.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        open_triage=Count("id", filter=Q(status__in=OPEN_EXCURSION_STATUSES)),
        running=Count("id", filter=Q(ended_at__isnull=True)))
    open_episode = next((e for e in excursions if e.ended_at is None), None)
    if open_episode is None and episode_counts["running"]:
        # The running episode fell outside the capped panel — rare, but a page that showed "no open
        # episode" while one was live would be the page saying the freezer is fine.
        open_episode = obj.open_episode()

    date_to = today
    date_from = date_to - timedelta(days=DETAIL_PROFILE_DAYS - 1)
    profile = coldchain.profile(obj, date_from=date_from, date_to=date_to)

    limit_min, limit_max = obj.effective_limits()

    return render(request, "scm/coldchain/coldchainmonitor/detail.html", {
        "obj": obj,
        "latest_reading": latest_reading,
        "range_chip": obj.range_chip(probe),
        "reporting_chip": _reporting_chip(obj, latest_reading, now),
        "calibration_chip": obj.calibration_chip(today),
        "in_warning_band": obj.is_in_warning_band(probe),
        "setpoint_gap": obj.setpoint_gap(probe),
        "days_to_calibration_due": obj.days_to_calibration_due(today),
        "limit_min": limit_min,
        "limit_max": limit_max,
        "profile": profile,
        "profile_days": DETAIL_PROFILE_DAYS,
        "profile_window": (date_from, date_to),
        "readings": readings,
        "readings_truncated": readings_truncated,
        "reading_count": reading_count,
        "panel_cap": MAX_PANEL_ROWS,
        "open_episode": open_episode,
        "excursions": excursions,
        "excursions_truncated": excursions_truncated,
        "excursion_count": episode_counts["total"] or 0,
        "open_excursion_count": episode_counts["open_triage"] or 0,
        "can_delete": not (episode_counts["total"] or 0),
        "calibration_note": CALIBRATION_NOTE,
        "provenance_note": PROVENANCE_NOTE,
        "append_only_note": APPEND_ONLY_NOTE,
    })


@login_required
def coldchainmonitor_profile(request, pk):
    """Bullet 4's headline artefact: the temperature profile over a window the user chooses.

    **Filter GET params:** ``date_from`` / ``date_to`` (``YYYY-MM-DD``; junk falls back to the
    default window and the page SAYS so rather than silently ignoring the request; a reversed pair is
    SWAPPED and flagged, because a ``from`` after a ``to`` is a typo and not an empty result).

    The window is then clamped a second time inside ``coldchain.profile()`` to
    ``MAX_READING_WINDOW_DAYS``, and the result REPORTS the cap (``window_capped``) rather than
    pretending the range was honoured — the reading table is the fastest-growing one in the
    sub-module, so an unbounded date range is a full scan on a page anyone can open.

    Context:

    * ``obj`` — the monitor (three subjects joined).
    * ``profile`` — the ``coldchain.profile()`` dict. **Every measured key is ``None`` on an empty
      window and MUST render as an em dash**: ``count`` (int, 0 when empty), ``first_at`` /
      ``last_at`` (datetime or ``None``), ``min`` / ``max`` / ``mean`` (Decimal or ``None``),
      ``in_range_minutes`` / ``out_minutes`` (int or ``None`` — ``None`` also when the monitor has NO
      limits at all, because readings without a band cannot be in or out of one),
      ``pct_in_range`` (Decimal or ``None`` — **0 % means "never in range", blank means "we have no
      readings"; conflating them is how a page lies**), ``mkt`` (Decimal or ``None`` — ``None`` for a
      FROZEN monitor, where USP <1079.2> says MKT does not apply, and for an unreadable window),
      ``window_capped`` (bool), ``truncated`` (bool — the row walk hit ``MAX_EPISODE_READINGS``),
      ``date_from`` / ``date_to`` (the RESOLVED window), ``limit_min`` / ``limit_max`` (Decimal or
      ``None``) and ``frozen`` (bool).
    * ``series`` — a LIST of dicts ``{"reading_at", "temperature", "humidity_pct", "out"}`` for the
      chart, OLDEST FIRST, capped at :data:`MAX_CHART_POINTS`. ``humidity_pct`` is ``None`` when the
      device does not report it; ``out`` is ``""`` / ``"high"`` / ``"low"`` from
      ``coldchain.out_of_range`` so the chart and the episode list cannot disagree about which points
      broke the band.
    * ``series_truncated`` (bool) and ``series_cap`` (int).
    * ``episodes`` — the excursions OVERLAPPING the window (a LIST, newest first, capped), so they
      can be marked on the chart. An episode that started before the window and is still running is
      included.
    * ``window`` — the ``_report_window`` dict: ``date_from`` / ``date_to`` (dates),
      ``date_from_raw`` / ``date_to_raw`` (the echoed strings), ``window_invalid`` (bool — a value
      was typed and REJECTED, so the page can say "showing the default window") and
      ``period_label`` (str).
    * ``max_window_days`` (int), ``default_days`` (int), ``frozen_mkt_note`` (str — the USP <1079.2>
      sentence to print when ``profile.mkt`` is ``None`` on a frozen monitor).
    """
    obj = get_object_or_404(
        ColdChainMonitor.objects.select_related("location", "asset", "shipment"),
        pk=pk, tenant=request.tenant)

    today = timezone.localdate()
    window = _report_window(request.GET,
                            today - timedelta(days=DEFAULT_PROFILE_DAYS - 1), today)
    profile = coldchain.profile(obj, date_from=window["date_from"], date_to=window["date_to"])

    # The RESOLVED window — `coldchain.profile()` may have clamped it, and the chart must plot the
    # window that was actually measured rather than the one that was asked for.
    start, end = _aware_bounds(profile["date_from"], profile["date_to"])
    limit_min, limit_max = obj.effective_limits()

    rows = list(obj.readings.filter(tenant=request.tenant,
                                    reading_at__gte=start, reading_at__lte=end)
                .order_by("-reading_at", "-id")
                .values("reading_at", "temperature", "humidity_pct")[:MAX_CHART_POINTS + 1])
    series_truncated = len(rows) > MAX_CHART_POINTS
    del rows[MAX_CHART_POINTS:]
    # Fetched newest-first so the CAP keeps the most recent points, then reversed so the chart reads
    # left to right.
    series = [{
        "reading_at": row["reading_at"],
        "temperature": row["temperature"],
        "humidity_pct": row["humidity_pct"],
        "out": coldchain.out_of_range(row["temperature"], limit_min, limit_max),
    } for row in reversed(rows)]

    episodes = list(obj.excursions
                    .filter(tenant=request.tenant, started_at__lte=end)
                    .filter(Q(ended_at__isnull=True) | Q(ended_at__gte=start))
                    .order_by("-started_at", "-id")[:MAX_PANEL_ROWS])

    return render(request, "scm/coldchain/coldchainmonitor/profile.html", {
        "obj": obj,
        "profile": profile,
        "series": series,
        "series_truncated": series_truncated,
        "series_cap": MAX_CHART_POINTS,
        "episodes": episodes,
        # ONE window dict rather than the dict PLUS its splat: `profile` carries its own
        # (post-clamp) `date_from` / `date_to`, and two loose context keys of the same name would
        # leave the template unable to tell the requested window from the measured one.
        "window": window,
        "max_window_days": MAX_READING_WINDOW_DAYS,
        "default_days": DEFAULT_PROFILE_DAYS,
        "frozen_mkt_note": FROZEN_MKT_NOTE,
    })


def _aware_bounds(date_from, date_to):
    """A pair of dates as the inclusive AWARE datetime range covering both days end to end.

    An explicit range rather than ``reading_at__date__gte``: ``__date`` compiles to ``CONVERT_TZ`` on
    MariaDB and returns NULL when the timezone tables are not loaded, which on XAMPP they are not
    (the 4.12 carbon-report finding). ``time.max`` on the upper bound so a reading taken at 16:00 on
    the closing day is inside the window somebody asked for — a bare date resolves to midnight and
    would drop the whole final day.
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


# =================================================================================================
# The detector — a BUTTON, never a GET, and never a cron this project does not have
# =================================================================================================
@tenant_admin_required
@require_POST
def coldchain_detect(request):
    """Sweep every ACTIVE monitor in the workspace for new, extended and closed episodes.

    A POST-only button, exactly as 4.11 runs ``detect_alerts``: there is no scheduler in this project
    and inventing half of one here would be a second thing to operate. The seeder calls the SAME
    function, so the demo excursions are produced by the real code path and that path is exercised on
    every ``seed_scm`` run.

    ``@tenant_admin_required`` because the rows it mints are what a regulator reads, and
    ``@require_POST`` so a GET is a 405 rather than a silent state change.

    All the audit rows, the row locks and the merge-not-duplicate rule live in
    ``coldchain.detect_excursions()`` — this view resolves the tenant, calls it once and renders its
    summary. **It writes nothing itself.**

    **The sweep is CURSORED.** An optional ``after`` in the POST body (a monitor id, read through
    ``as_db_int`` so junk skips the cursor rather than raising) is handed straight to the service as
    ``after=``; when the pass stops on the monitor cap, the redirect carries the last examined id
    back as ``?after=…`` and the list page's Detect button posts it on the next press. Without that
    round trip every press re-walks the same first ``MAX_MONITORS_PER_SWEEP`` monitors and the ones
    past the cap are reachable only through their own per-monitor button.
    """
    if _need_tenant(request):
        return redirect("scm:coldchainmonitor_list")
    summary = coldchain.detect_excursions(
        request.tenant, user=request.user, after=as_db_int(request.POST.get("after")))
    _detect_message(request, summary)
    target = reverse("scm:temperatureexcursion_list")
    if summary.get("more_monitors") and summary.get("last_monitor_id"):
        target = f"{target}?after={summary['last_monitor_id']}"
    return redirect(target)


@tenant_admin_required
@require_POST
def coldchainmonitor_detect(request, pk):
    """The same sweep, narrowed to ONE monitor — the button on its detail page.

    The monitor is resolved with ``get_object_or_404(..., tenant=request.tenant)`` FIRST, so a
    cross-tenant pk answers 404 rather than a 302 that leaks "there is a row there, you just cannot
    touch it" (the 4.12 finding). ``detect_excursions`` re-scopes by tenant anyway; both are stated
    because a lookup that skips the scope because a caller promised is how the one that stops
    promising gets missed.

    A monitor whose status is not ``active``, or that carries no temperature limit at all, produces a
    summary of zeros (or a ``skipped`` count) rather than an error — the message says which.
    """
    obj = get_object_or_404(ColdChainMonitor, pk=pk, tenant=request.tenant)
    summary = coldchain.detect_excursions(request.tenant, monitor=obj, user=request.user)
    if obj.status != "active":
        messages.info(request, f"{obj.number} is {obj.get_status_display().lower()}, so the "
                               "detector skipped it — only active monitors are detected against.")
    _detect_message(request, summary)
    return redirect("scm:coldchainmonitor_detail", pk=pk)


# =================================================================================================
# Prose the templates print. Declared at the foot so the code above reads first.
# =================================================================================================

#: The `storage_condition` pre-fill, in one sentence. `STORAGE_CONDITION_RANGES` is DOCUMENTATION of
#: the industry bands, not policy: it exists so nobody has to look up "what is chilled?" before
#: typing two numbers, and the numbers that decide in-range stay the explicit per-monitor columns.
STORAGE_PREFILL_NOTE = (
    "Choosing a temperature class SUGGESTS the limits on a new monitor — it never overwrites what "
    "you typed, and it never touches a saved row. The two limit boxes are what actually decide "
    "whether a reading is in range, and an excursion snapshots them as they were when it fired."
)

#: The exactly-one-subject rule, stated ABOVE the three FK fields rather than only in the error.
SUBJECT_RULE_NOTE = (
    "A monitor watches exactly one thing: a cold room or zone (Location), a reefer or chiller "
    "(Asset), or an in-transit consignment (Shipment). Fill in one and leave the other two blank. "
    "Once readings exist the choice is FIXED — retire this deployment and start a new one instead, "
    "because moving the pointer would restate every compliance figure already derived from it."
)

#: Printed wherever MKT comes back blank on a frozen point.
FROZEN_MKT_NOTE = (
    "Mean kinetic temperature is not reported for frozen, deep-frozen or cryogenic product: USP "
    "<1079.2> states it does not apply, because the Arrhenius weighting models a degradation rate "
    "frozen product is not undergoing — quoting a figure would let a warm spell be offset by the "
    "cold hours either side of it."
)

#: Said once and read by the reading list, the reading detail and the monitor page, so three
#: templates cannot explain the missing Edit/Delete three different ways.
APPEND_ONLY_NOTE = (
    "Temperature readings are append-only. There is no edit and no delete: a wrong reading is "
    "corrected by filing a later, correct one, exactly like a compensating stock movement. The "
    "current value is always the newest row, so the correction takes effect immediately — and the "
    "mistaken reading stays in the history, which is the point of a log rather than a defect in it."
)

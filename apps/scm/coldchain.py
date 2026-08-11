"""SCM 4.15 Cold Chain Management — the excursion detector, the MKT service and the profile.

**Where and why this file is FLAT at the app root.** Backend Package Structure rule 8: *"admin.py,
apps.py, analytics.py, services.py and other single-purpose modules stay flat at the app root."*
4.11's ``SupplyChainAlert`` detector lives in ``apps/scm/analytics.py`` for exactly this reason, and
this module is its 4.15 sibling.

**IMPORT DIRECTION IS ONE-WAY: ``coldchain`` -> ``models`` -> ``_choices``.** This module imports
``apps.scm.models``; **no module under ``apps/scm/models/`` may ever import
``apps.scm.coldchain``.** That is the rule ``SupplyChainAlerts.py:9-11`` already records for this app
(*"the metric vocabulary comes from ``_choices`` (pure data), NEVER from ``apps.scm.analytics`` —
that module imports the model layer, so the edge has to run one way or the package will not
import"*). Views, the seeder and the tests import this module freely; the model layer never does.

--------------------------------------------------------------------------------------------------
THIS MODULE IS THE ONLY WRITER OF EVERY ``editable=False`` COLUMN ON ``TemperatureExcursion``
--------------------------------------------------------------------------------------------------
``started_at`` / ``ended_at`` / ``duration_minutes`` / ``breach_direction`` /
``extreme_temperature`` / ``limit_min`` / ``limit_max`` / ``reading_count`` / ``mkt`` /
``last_detected_at`` are computed HERE from the reading ledger. No form in this app touches one, and
the manual back-dated create path does not type them either — it hands a window to this module and
takes back the measured numbers (see :func:`window_stats`).

**``status`` is NEVER written here.** Only the four workflow verbs on the model move it, so a re-fire
on an acknowledged excursion moves ``last_detected_at`` and leaves the triage state exactly where a
human put it. **``severity`` is written at OPEN time only**, for the same reason inverted: a
triager's downgrade has to survive the next detection pass, or the queue silently re-escalates
everything anybody has already judged. "Recompute everything on every pass" is the natural instinct
and it is wrong on both columns.

--------------------------------------------------------------------------------------------------
"ONE OPEN EPISODE PER MONITOR" IS ENFORCED HERE, BY A ROW LOCK — MariaDB HAS NO PARTIAL INDEXES
--------------------------------------------------------------------------------------------------
The shape that *looks* right is
``UniqueConstraint(fields=["tenant", "monitor"], condition=Q(ended_at__isnull=True))``, and
``SupplyChainAlerts.py:17-37`` already recorded why it is wrong twice over: Django **silently omits**
a conditional constraint on MariaDB while the SQLite test settings honour it (a guard that exists
only under test is more dangerous than no guard), and a constraint can only **refuse** a write, never
**merge** one — merging is the actual rule, because a breach that keeps breaching must extend the
open episode rather than raise a second row.

So :func:`detect_excursions` opens ``transaction.atomic()`` per monitor and takes
``select_for_update()`` **on the MONITOR row, BEFORE any reading is read**. The monitor row always
exists, so the lock is never the no-op that ``select_for_update()`` on an empty queryset would be,
and it also serialises the reading-import path against the detector. Taking the lock after the walk
would leave the classic TOCTOU window: two concurrent passes both read "no open episode", both walk,
and both INSERT.

--------------------------------------------------------------------------------------------------
NO TEMPERATURE IN THIS MODULE PASSES THROUGH ``q2()`` OR ``q4()``
--------------------------------------------------------------------------------------------------
``_base.py:48`` — ``q4()`` is ``min(max(Decimal(value or ZERO), -MAX_Q4), MAX_Q4)``. The *sign*
survives the clamp, so at a glance it looks safe for a signed column. It is not: **``value or ZERO``
turns ``None`` into ``Decimal("0")``, and 0 °C is a perfectly plausible temperature.** A missing
measurement would arrive as "the fridge was at freezing" — a wrong number that reads exactly like a
real one, which is the worst possible failure mode for a record that ends up in an audit pack.
Everything here quantizes with ``.quantize(Decimal("0.01"))`` applied to a value already proven
non-``None``, and a row with no readable temperature is **skipped**, never coerced.

**Every derived figure answers ``None``, never 0, when it cannot be computed** —
:func:`mean_kinetic_temperature` for a frozen monitor or an empty window, :func:`profile`'s whole
result set on an empty window, :func:`excess_over_limit` with no limit on the breached side.

--------------------------------------------------------------------------------------------------
WHAT THIS MODULE DOES NOT WRITE
--------------------------------------------------------------------------------------------------
No ``StockMove``. No ``accounting.JournalEntry`` (L29). No ``LotSerial.status`` — 4.9 owns quarantine
and 4.15 only ever READS that column. No ``Asset.status``, no ``MaintenancePlan``, no value added to
any 4.9 or 4.13 vocabulary. The single cross-sub-module write is :func:`raise_work_order`, which
creates one ``scm.MaintenanceWorkOrder`` with an **existing** ``SOURCE_CHOICES`` value and points the
excursion at it — a one-way link, the ``MaintenanceWorkOrder.non_conformance`` precedent.
"""
import math
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Avg, Count, Max, Min
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.scm.models import (
    ColdChainMonitor,
    KELVIN_OFFSET,
    MAX_EPISODE_READINGS,
    MAX_EXCURSION_MINUTES,
    MAX_READING_WINDOW_DAYS,
    MAX_TEMPERATURE_C,
    MIN_TEMPERATURE_C,
    MKT_EA_OVER_R,
    MaintenanceWorkOrder,
    TemperatureExcursion,
    TemperatureReading,
)


# -------------------------------------------------------------------------------------------------
# Detector policy.
#
# These live HERE and not in `models/ColdChainManagement/_choices.py` on purpose. `_choices` is pure
# vocabulary that the MODEL layer imports, and the model layer must not learn the detector's rules —
# that is the one-way import edge this module's docstring opens with. Nothing outside this file reads
# them, so "stated in one place" is satisfied by stating them beside the function that applies them.
# -------------------------------------------------------------------------------------------------

#: Monitors examined in ONE sweep. A tenant with more gets `more_remain=True` and the caller presses
#: again — the 4.7 `MAX_HORIZON_PERIODS` lesson applied to a batch action rather than to a write.
MAX_MONITORS_PER_SWEEP = 500

#: How far past its limit a breach has to go before the detector's OPENING severity is `critical` /
#: `major`. Magnitudes, so both are positive even though the temperatures they are compared against
#: are signed.
CRITICAL_EXCESS_C = Decimal("5")
MAJOR_EXCESS_C = Decimal("2")

#: An episode that outran its grace period this many times over is critical on duration alone — a
#: half-degree breach that has run for a day is not a minor event no matter how small the excess.
CRITICAL_GRACE_MULTIPLE = 4

#: The stand-in grace period used when a monitor's own is 0. A grace of zero means "every breach
#: counts", which makes `duration >= grace * 4` true for every episode and would mark all of them
#: critical; one hour is the unit that keeps the duration rule meaningful in that configuration.
UNGRACED_UNIT_MINUTES = 60

#: Excursion severity -> the priority of the repair job :func:`raise_work_order` raises. Both
#: vocabularies are 4.13's and 4.15 adds nothing to either.
SEVERITY_PRIORITY = {"critical": "urgent", "major": "high", "minor": "medium"}

#: An EXISTING `MaintenanceWorkOrder.SOURCE_CHOICES` value (`MaintenanceWorkOrders.py:90-99`), chosen
#: rather than added: 4.13 declares `condition` as *"the seam 11.7 (condition monitoring) writes
#: through"*, and a temperature excursion raising a repair is precisely a condition trigger. 4.15
#: adds no reciprocal value to that list, and no `reefer` value to `Asset.ASSET_TYPE_CHOICES` — a
#: reefer is DERIVED as "an Asset with an active ColdChainMonitor pointed at it", which cannot go
#: stale the way a hand-set type would.
WORK_ORDER_SOURCE = "condition"

#: The columns an extend/close pass writes. Narrow ON PURPOSE: a full `save()` would write back every
#: in-memory column including any a concurrent triage edit had just changed (the `_status_transition`
#: reasoning, `views/_helpers.py:425-428`). `status`, `severity`, `limit_min` and `limit_max` are
#: deliberately absent — see the module docstring.
EPISODE_UPDATE_FIELDS = ["ended_at", "duration_minutes", "extreme_temperature", "breach_direction",
                         "reading_count", "mkt", "last_detected_at", "updated_at"]


# -------------------------------------------------------------------------------------------------
# Row access — every pure function below takes either a `.values()` dict or a model instance
# -------------------------------------------------------------------------------------------------

def _value(row, name):
    """One field off a reading row, whether it is a ``.values()`` mapping or a model instance.

    The detector and the profile both read through ``.values(...)`` (never a per-row model
    instantiation), while a test or the seeder finds it far more natural to hand over real
    ``TemperatureReading`` objects. Supporting both costs one ``isinstance`` and keeps every pure
    function below callable with plain dicts, which is what makes them unit-testable without a
    database.
    """
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _decimal(value):
    """A ``Decimal`` or ``None`` — **and ``None`` stays ``None``.**

    This is the whole of Trap 1 in one function. ``Decimal(value or ZERO)`` (what ``q2``/``q4`` do)
    would turn a missing measurement into ``Decimal("0")``, and 0 °C is an ordinary reading. A value
    that cannot be read answers ``None`` and its caller skips the row.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _weight(row):
    """The row's own weight in minutes — its SNAPSHOTTED ``interval_minutes``, floored at 1.

    That column is the entire reason MKT and time-out-of-range cannot be retroactively re-weighted
    (Decision B): a single hot hour inside a cold month must weigh one hour, not "one row". A row
    with a missing or nonsensical weight **falls back to 1 rather than being dropped** — losing a
    real measurement because its metadata is thin is worse than under-weighting it.
    """
    raw = _value(row, "interval_minutes")
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        return 1
    return minutes if minutes > 0 else 1


def _quantize(value):
    """2dp on a value already proven non-``None``. Never a clamping helper — see the docstring."""
    return None if value is None else Decimal(value).quantize(Decimal("0.01"))


def _json(value):
    """A JSON-safe copy of one audit-payload value.

    ``core.AuditLog.changes`` is a ``JSONField`` and stores what it is given verbatim; a ``Decimal``
    or a ``datetime`` in there is a ``TypeError`` at write time, which would turn a successful
    detection pass into a 500 at the very last step.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


# -------------------------------------------------------------------------------------------------
# 4a. PURE FUNCTIONS — no database, unit-testable on their own
# -------------------------------------------------------------------------------------------------

def out_of_range(temperature, limit_min, limit_max):
    """``""`` / ``"high"`` / ``"low"`` — which side of the band this reading broke, if any.

    * **A ``None`` limit means NO LIMIT ON THAT SIDE.** A one-sided band is legitimate all over this
      sub-module (a freezer that only ever needs a ceiling), and treating a missing limit as "always
      in range on both sides" would be a monitor that can never fire.
    * **``temperature is None`` returns ``""`` and the caller SKIPS the row.** A missing measurement
      is neither in range nor a breach. This is the second half of Trap 1: this function must never
      be handed a ``q4()``-coerced ``0`` standing in for a blank cell.
    * A monitor with NO limits at all also answers ``""`` for every reading — ``clean()`` refuses to
      leave an *active* monitor in that state, and :func:`detect_excursions` skips and counts one
      rather than crashing on it.

    The comparisons are strict (``<`` / ``>``): a reading exactly ON the limit is IN range, which is
    what "2 to 8 °C" means everywhere it is printed.
    """
    temperature = _decimal(temperature)
    if temperature is None:
        return ""
    limit_min = _decimal(limit_min)
    limit_max = _decimal(limit_max)
    if limit_min is not None and temperature < limit_min:
        return "low"
    if limit_max is not None and temperature > limit_max:
        return "high"
    return ""


def excess_over_limit(extreme_temperature, breach_direction, limit_min, limit_max):
    """How far past the limit the extreme went, or ``None`` — the twin of
    :meth:`TemperatureExcursion.excess_c`.

    Stated here as a pure function so the detector's severity call and the model's rendered figure
    are literally the same arithmetic; two implementations of "how bad was it" would eventually
    disagree, and the one on the page is the one somebody would act on.

    ``None`` — **never ``0``** — when there is no extreme recorded or no limit on the breached side.
    An excess of zero means "it touched the limit exactly", which is a different statement from "we
    cannot compute this". For ``both`` the larger of the two excesses wins: an episode that swung
    through the band and out the other side is as bad as its worse end.
    """
    extreme = _decimal(extreme_temperature)
    if extreme is None:
        return None
    limit_min = _decimal(limit_min)
    limit_max = _decimal(limit_max)
    gaps = []
    if breach_direction in ("high", "both") and limit_max is not None:
        gaps.append(extreme - limit_max)
    if breach_direction in ("low", "both") and limit_min is not None:
        gaps.append(limit_min - extreme)
    if not gaps:
        return None
    return _quantize(max(gaps))


def episode_duration_minutes(started_at, ended_at, now=None):
    """Minutes the episode has run — ``(ended_at or now) - started_at``, floored at 0 and CLAMPED.

    The clamp is load-bearing rather than tidy. ``duration_minutes`` is ``editable=False`` so it
    never sees form validation, two ``DateTimeField`` values can legally be thousands of years apart,
    and this figure is fed to ``timedelta(minutes=…)`` on the report pages — where an out-of-range
    value is an uncaught ``OverflowError``, a 500 rather than a message (the 4.10 DoS finding, and
    the ``MaintenanceWorkOrder.MAX_DOWNTIME_MINUTES`` idiom).

    The clock is read ONCE per call so two figures derived in one pass cannot disagree.
    """
    if not started_at:
        return 0
    finish = ended_at or now or timezone.now()
    elapsed = int((finish - started_at).total_seconds() // 60)
    return max(0, min(elapsed, MAX_EXCURSION_MINUTES))


def severity_for(excess_c, duration_minutes, grace_minutes):
    """The detector's **initial** severity — ``"critical"`` / ``"major"`` / ``"minor"``.

    Pure, so the rule is testable and lives in exactly one place. Written at OPEN time and never
    re-applied: a later pass must not overwrite a triager's downgrade (see the module docstring).

    The rule, in words:

    * **critical** — the extreme went :data:`CRITICAL_EXCESS_C` past the limit, **or** the episode
      ran :data:`CRITICAL_GRACE_MULTIPLE` times its monitor's grace period. Either alone is enough:
      a big spike and a long drift are different failures and both are the worst kind.
    * **major** — the extreme went :data:`MAJOR_EXCESS_C` past the limit, **or** the episode
      outlived the grace period at all (which is what :attr:`TemperatureExcursion.is_reportable`
      means, so a reportable episode is never opened below ``major``).
    * **minor** — everything else: a blip that stayed inside the grace period and barely left the
      band.

    ``excess_c`` may be ``None`` (no extreme, or no limit on the breached side), in which case the
    judgement rests on duration alone rather than defaulting to the worst or the best case.
    """
    excess = _decimal(excess_c)
    if excess is not None:
        excess = abs(excess)
    try:
        duration = max(int(duration_minutes or 0), 0)
    except (TypeError, ValueError):
        duration = 0
    try:
        grace = max(int(grace_minutes or 0), 0)
    except (TypeError, ValueError):
        grace = 0
    unit = grace if grace > 0 else UNGRACED_UNIT_MINUTES

    if excess is not None and excess >= CRITICAL_EXCESS_C:
        return "critical"
    if duration >= unit * CRITICAL_GRACE_MULTIPLE:
        return "critical"
    if excess is not None and excess >= MAJOR_EXCESS_C:
        return "major"
    # `max(grace, 1)` so a zero-minute episode cannot be major under a zero grace period.
    if duration >= max(grace, 1):
        return "major"
    return "minor"


def mean_kinetic_temperature(rows, *, frozen=False):
    """Mean kinetic temperature over ``rows``, in °C — or **``None``**, never ``0``.

    USP <1079.2>::

        MKT = (dH/R) / -ln( SUM( w_i * exp( -(dH/R) / T_i ) ) / SUM( w_i ) )     [T in kelvin]

    ``w_i`` is the row's SNAPSHOTTED ``interval_minutes`` — that is the entire reason that column
    exists (Decision B), and a row with a missing weight falls back to 1 rather than being dropped.
    :data:`MKT_EA_OVER_R` is used directly because ``83.144 / 0.0083144 == 10000`` EXACTLY, which is
    precisely why the USP chose those two figures; dividing two ``Decimal`` s on every call would be
    slower and would add a rounding step that has no business existing.

    **Answers ``None`` — an honest figure can answer ``None``, never 0 (the 4.13 rule verbatim) —
    for:**

    * ``frozen=True``. USP <1079.2> states MKT does not apply to frozen / deep-frozen / cryogenic
      product: the Arrhenius weighting models a chemical degradation rate a frozen product is not
      undergoing, and quoting a figure anyway would let a warm spell be "offset" by the cold hours
      either side of it. An MKT of 0 °C reads as a perfectly-cold shipment, which is the precise
      opposite of "this does not apply".
    * an empty row set, or one in which no row carries a readable temperature;
    * a weight sum of zero;
    * a log-domain or overflow failure;
    * a result outside the physical bounds the column is validated against — which would be a
      ``DataError`` on save rather than a number anybody should read.

    **Computed in ``float`` via ``math.exp`` / ``math.log``, deliberately.** ``Decimal.exp()`` over
    tens of thousands of rows costs on the order of 100x for precision no thermometer in this
    sub-module has; the result is quantized back to a 2dp ``Decimal`` because that is what the column
    holds. Do not "fix" this to Decimal arithmetic.

    **Property worth asserting in a test:** MKT is always **>=** the arithmetic mean for a varying
    series, and **equal** to it for a constant one. That is a real correctness check on the formula
    rather than a smoke test.
    """
    if frozen:
        return None
    ea_over_r = float(MKT_EA_OVER_R)
    offset = float(KELVIN_OFFSET)
    weighted = 0.0
    total_weight = 0.0
    for row in rows:
        temperature = _decimal(_value(row, "temperature"))
        if temperature is None:
            continue
        kelvin = float(temperature) + offset
        if kelvin <= 0:
            # Below absolute zero is not a temperature. Unreachable through the validators
            # (MIN_TEMPERATURE_C is -200 °C) and guarded anyway, because `-ea_over_r / 0` is a
            # ZeroDivisionError rather than a number.
            continue
        weight = float(_weight(row))
        try:
            weighted += weight * math.exp(-ea_over_r / kelvin)
        except (OverflowError, ValueError, ZeroDivisionError):
            return None
        total_weight += weight
    if total_weight <= 0 or weighted <= 0:
        return None
    try:
        kelvin = ea_over_r / -math.log(weighted / total_weight)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    celsius = kelvin - offset
    if not (float(MIN_TEMPERATURE_C) <= celsius <= float(MAX_TEMPERATURE_C)):
        return None
    return _quantize(Decimal(str(celsius)))


def time_in_range(rows, limit_min, limit_max):
    """Minute-weighted time in and out of the band. **Every figure is ``None`` on nothing to say.**

    Returns ``{"count", "in_minutes", "out_minutes", "total_minutes", "pct_in_range"}``.

    **MINUTE-weighted, not row-weighted.** Each row contributes its own ``interval_minutes``, so a
    monitor whose logging interval changed mid-window still reports the truth — a row-count
    percentage would silently mis-state exactly the drift the snapshot exists to prevent.

    ``pct_in_range`` of ``0`` means "it was never in range"; ``None`` means "we have no readings" or
    "this monitor has no band to be in or out of". Conflating those is how a page lies, so a monitor
    with no limits at all gets the ``None`` shape with its ``count`` still filled in — the readings
    exist, the verdict does not.

    Shared by :func:`profile`, the compliance report and the cold-storage board so the same window
    cannot render two different percentages on two pages.
    """
    limit_min = _decimal(limit_min)
    limit_max = _decimal(limit_max)
    count = 0
    in_minutes = 0
    out_minutes = 0
    for row in rows:
        temperature = _decimal(_value(row, "temperature"))
        if temperature is None:
            continue  # a missing measurement is neither in range nor a breach — Trap 1
        count += 1
        if out_of_range(temperature, limit_min, limit_max):
            out_minutes += _weight(row)
        else:
            in_minutes += _weight(row)
    unbanded = limit_min is None and limit_max is None
    if not count or unbanded:
        return {"count": count, "in_minutes": None, "out_minutes": None,
                "total_minutes": None, "pct_in_range": None}
    total = in_minutes + out_minutes
    pct = (Decimal(in_minutes) * 100 / Decimal(total)).quantize(Decimal("0.01")) if total else None
    return {"count": count, "in_minutes": in_minutes, "out_minutes": out_minutes,
            "total_minutes": total, "pct_in_range": pct}


def walk_episodes(rows, limit_min, limit_max, *, open_started_at=None):
    """Split an ASCENDING reading series into out-of-range episodes. **Pure — this is the algorithm.**

    ``rows`` must be ordered oldest-first; the caller orders by ``("reading_at", "id")``.

    The episode rule (tier 1 + tier 2 of the market's five): **open** at the first out-of-range
    reading, **extend** while consecutive readings stay out of range, **close** at the first reading
    back inside the band, with ``ended_at`` = that reading's ``reading_at``.

    ``open_started_at`` seeds the walk as "already inside an episode" — it is the ``started_at`` of
    the row the detector found still running when it took the monitor lock. The first segment is then
    flagged ``continued`` and the caller EXTENDS that stored row instead of creating a second one.
    Note that a continued segment can legitimately come back with **no new rows and an ``ended_at``**:
    that is the case where the very first new reading was back in range, and the stored episode is
    closed without gaining a row.

    Each segment is ``{"started_at", "ended_at", "rows", "continued"}``, where ``rows`` holds only
    the **out-of-range** rows this walk saw (a continued segment therefore holds only the NEW ones —
    the caller re-reads the full window when it needs episode-wide statistics). ``ended_at is None``
    means the episode is still running at the end of the series.
    """
    segments = []
    current = None
    if open_started_at is not None:
        current = {"started_at": open_started_at, "ended_at": None, "rows": [], "continued": True}
    for row in rows:
        moment = _value(row, "reading_at")
        temperature = _decimal(_value(row, "temperature"))
        if temperature is None or moment is None:
            # Structurally unreachable from the database — `temperature` is NOT NULL and
            # `reading_at` has no default — but a caller handing over hand-built dicts must not be
            # able to turn a blank cell into a breach or into 0 °C.
            continue
        if out_of_range(temperature, limit_min, limit_max):
            if current is None:
                current = {"started_at": moment, "ended_at": None, "rows": [], "continued": False}
            current["rows"].append(row)
        elif current is not None:
            current["ended_at"] = moment
            segments.append(current)
            current = None
    if current is not None:
        segments.append(current)
    return segments


def episode_stats(rows, limit_min, limit_max, *, frozen=False):
    """The measured figures for one episode, from its rows. **Pure.**

    Returns ``{"reading_count", "breach_direction", "extreme_temperature", "excess_c", "mkt"}``.

    * ``reading_count`` — every row in the window that carries a readable temperature, in or out of
      range, which is what the column's help text promises ("how many reading rows fall inside the
      episode window").
    * ``breach_direction`` — ``"high"`` / ``"low"`` / ``"both"`` once an episode has seen breaches on
      both sides, or ``""`` when the window holds no breach at all. **``""`` rather than a default**,
      so the caller keeps whatever direction is already stored instead of a fresh row claiming
      ``high`` about an episode that never went high.
    * ``extreme_temperature`` — the max for ``high``, the min for ``low``, and for ``both`` whichever
      end went further past its own limit. ``None`` when nothing breached.
    * ``mkt`` — ``None`` for a frozen monitor and for an unreadable window; see
      :func:`mean_kinetic_temperature`.
    """
    limit_min = _decimal(limit_min)
    limit_max = _decimal(limit_max)
    reading_count = 0
    highest = None
    lowest = None
    directions = set()
    for row in rows:
        temperature = _decimal(_value(row, "temperature"))
        if temperature is None:
            continue
        reading_count += 1
        direction = out_of_range(temperature, limit_min, limit_max)
        if not direction:
            continue
        directions.add(direction)
        if direction == "high":
            highest = temperature if highest is None else max(highest, temperature)
        else:
            lowest = temperature if lowest is None else min(lowest, temperature)

    if len(directions) > 1:
        breach_direction = "both"
    elif directions:
        breach_direction = next(iter(directions))
    else:
        breach_direction = ""

    extreme = None
    if breach_direction == "high":
        extreme = highest
    elif breach_direction == "low":
        extreme = lowest
    elif breach_direction == "both":
        # Both ends broke. The record carries ONE extreme, so it is the end that went further past
        # its own limit — which is also the one `excess_over_limit` will report.
        high_gap = (highest - limit_max) if (highest is not None and limit_max is not None) else None
        low_gap = (limit_min - lowest) if (lowest is not None and limit_min is not None) else None
        if high_gap is None:
            extreme = lowest
        elif low_gap is None:
            extreme = highest
        else:
            extreme = highest if high_gap >= low_gap else lowest

    return {
        "reading_count": reading_count,
        "breach_direction": breach_direction,
        "extreme_temperature": _quantize(extreme),
        "excess_c": excess_over_limit(extreme, breach_direction, limit_min, limit_max),
        "mkt": mean_kinetic_temperature(rows, frozen=frozen),
    }


def clamp_window(date_from, date_to):
    """``(date_from, date_to, capped)`` — a reading window never wider than
    :data:`MAX_READING_WINDOW_DAYS`.

    The reading table is the fastest-growing one in the sub-module (~17.5k rows per monitor per year
    at the 30-minute default), so an unbounded date range is a full scan on a page anyone can open. A
    reversed pair is SWAPPED rather than rendered as nothing — a ``from`` after a ``to`` is a typo,
    not an empty result — and the cap is REPORTED rather than applied silently, so the page can say
    it truncated instead of pretending the range was honoured.

    The window is inclusive of both ends, so ``MAX_READING_WINDOW_DAYS`` days means a span of
    ``MAX_READING_WINDOW_DAYS - 1``.
    """
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    capped = False
    if (date_to - date_from).days > MAX_READING_WINDOW_DAYS - 1:
        date_from = date_to - timedelta(days=MAX_READING_WINDOW_DAYS - 1)
        capped = True
    return date_from, date_to, capped


def _moment_bounds(date_from, date_to):
    """A pair of dates as the aware datetime range that covers both days end to end.

    ``reading_at`` is a ``DateTimeField`` while every report window in this app is a pair of DATES
    (``_report_window``, ``views/_helpers.py:486``), so somebody has to widen one into the other. Done
    here, once, rather than in each of the three report views — a ``__date__range`` lookup would read
    more naturally but cannot use ``scm_tmp_tnt_mon_idx`` (a function of the column is not a range on
    it), and this table is the one place in 4.15 where that matters.
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        zone = timezone.get_current_timezone()
        start = timezone.make_aware(start, zone)
        end = timezone.make_aware(end, zone)
    return start, end


# -------------------------------------------------------------------------------------------------
# 4b. The derived temperature profile
# -------------------------------------------------------------------------------------------------

#: The shape :func:`profile` answers with when the window holds nothing. Every figure is ``None`` and
#: **not one of them is 0** — `pct_in_range` of 0 % means "it was never in range", a blank means "we
#: have no readings", and a page that conflates the two lies about a fridge nobody was watching.
_EMPTY_PROFILE = ("count", "first_at", "last_at", "min", "max", "mean",
                  "in_range_minutes", "out_minutes", "pct_in_range", "mkt")


def profile(monitor, *, date_from, date_to):
    """The temperature profile for one monitor over one window — bullet 4's headline artefact.

    Returns ``{"count", "first_at", "last_at", "min", "max", "mean", "in_range_minutes",
    "out_minutes", "pct_in_range", "mkt", "window_capped"}`` plus the resolved window and the limits
    it was judged against (``date_from`` / ``date_to`` / ``limit_min`` / ``limit_max`` / ``frozen`` /
    ``truncated``), so the page can state what it actually measured rather than re-deriving it.

    **Every figure is ``None`` on an empty window, never ``0``.** See :data:`_EMPTY_PROFILE`.

    **Cost: exactly two queries.** ONE ``.aggregate()`` for count / min / max / mean / first / last,
    then ONE bounded iterator over ``.values("temperature", "interval_minutes")`` for the
    minute-weighted split and the MKT. Never a per-row model instantiation, never N queries. Both
    carry the "redundant" ``tenant=``, which is not redundant at all: ``scm_tmp_tnt_mon_idx`` is
    ``(tenant, monitor, reading_at)`` and ``tenant_id`` is the LEADING column, so a query that states
    no tenant cannot open that index and falls back to the plain FK index plus a filesort
    (``MeterReadings.py:101-116``).

    The window is capped at :data:`MAX_READING_WINDOW_DAYS` and the return says so
    (``window_capped``); the row walk is capped at :data:`MAX_EPISODE_READINGS` and the return says
    that too (``truncated``).
    """
    date_from, date_to, window_capped = clamp_window(date_from, date_to)
    start, end = _moment_bounds(date_from, date_to)
    limit_min, limit_max = monitor.effective_limits()
    frozen = monitor.is_frozen_condition

    result = {name: None for name in _EMPTY_PROFILE}
    result.update({"count": 0, "window_capped": window_capped, "truncated": False,
                   "date_from": date_from, "date_to": date_to,
                   "limit_min": limit_min, "limit_max": limit_max, "frozen": frozen})

    base = TemperatureReading.objects.filter(
        tenant_id=monitor.tenant_id, monitor_id=monitor.pk,
        reading_at__gte=start, reading_at__lte=end)
    agg = base.aggregate(count=Count("id"), lowest=Min("temperature"), highest=Max("temperature"),
                         mean=Avg("temperature"),
                         first_at=Min("reading_at"), last_at=Max("reading_at"))
    if not agg["count"]:
        return result

    rows = list(base.order_by("reading_at", "id")
                .values("temperature", "interval_minutes")[:MAX_EPISODE_READINGS + 1])
    truncated = len(rows) > MAX_EPISODE_READINGS
    rows = rows[:MAX_EPISODE_READINGS]
    spread = time_in_range(rows, limit_min, limit_max)

    result.update({
        "count": agg["count"],
        "first_at": agg["first_at"],
        "last_at": agg["last_at"],
        "min": _quantize(_decimal(agg["lowest"])),
        "max": _quantize(_decimal(agg["highest"])),
        "mean": _quantize(_decimal(agg["mean"])),
        "in_range_minutes": spread["in_minutes"],
        "out_minutes": spread["out_minutes"],
        "pct_in_range": spread["pct_in_range"],
        "mkt": mean_kinetic_temperature(rows, frozen=frozen),
        "truncated": truncated,
    })
    return result


def window_stats(monitor, started_at, ended_at, *, now=None):
    """The measured block for a hand-entered episode window — what the manual create path types NOT.

    ``TemperatureExcursionWindowForm`` collects a monitor and two moments and nothing else: no
    measured number is ever typed, because every one of them is ``editable=False`` on the model and a
    measurement a user can retype is not a measurement. The create view hands the window here and
    takes back ``{"duration_minutes", "breach_direction", "extreme_temperature", "limit_min",
    "limit_max", "reading_count", "mkt", "severity", "last_detected_at"}``, which is exactly the set
    it then writes. That is how CRUD Completeness ("every model with a list page gets a create view")
    and the ``editable=False`` contract are BOTH honoured — do not "simplify" it into typed numbers.

    The limits ARE snapshotted here (this is an open, so the snapshot is being taken for the first
    time), and ``severity`` is the same :func:`severity_for` the detector opens with, so a
    hand-entered episode and a detected one are graded by one rule.

    Reads at most one bounded query. A window with no readings comes back with ``reading_count`` 0,
    ``extreme_temperature`` / ``mkt`` ``None`` and the monitor's limits — never fabricated numbers.
    """
    limit_min, limit_max = monitor.effective_limits()
    rows = _window_rows(monitor, started_at, ended_at or (now or timezone.now()))
    stats = episode_stats(rows, limit_min, limit_max, frozen=monitor.is_frozen_condition)
    duration = episode_duration_minutes(started_at, ended_at, now=now)
    return {
        "duration_minutes": duration,
        "breach_direction": stats["breach_direction"] or "high",
        "extreme_temperature": stats["extreme_temperature"],
        "limit_min": limit_min,
        "limit_max": limit_max,
        "reading_count": stats["reading_count"],
        "mkt": stats["mkt"],
        "severity": severity_for(stats["excess_c"], duration, monitor.excursion_grace_minutes),
        "last_detected_at": ended_at or started_at,
    }


def _window_rows(monitor, start, end):
    """The reading rows inside one closed window, bounded and index-friendly.

    The "redundant" ``tenant_id=`` is load-bearing — see :func:`profile`. Only the two columns the
    pure functions read are fetched: instantiating models here would be tens of thousands of objects
    nobody looks at.
    """
    return list(TemperatureReading.objects
                .filter(tenant_id=monitor.tenant_id, monitor_id=monitor.pk,
                        reading_at__gte=start, reading_at__lte=end)
                .order_by("reading_at", "id")
                .values("temperature", "interval_minutes")[:MAX_EPISODE_READINGS])


# -------------------------------------------------------------------------------------------------
# 4c. The episode detector — the ONLY writer of the measured block
# -------------------------------------------------------------------------------------------------

def detect_excursions(tenant, *, monitor=None, user=None):
    """Open, extend and close ``TemperatureExcursion`` episodes from the reading ledger.

    Returns ``{"opened", "extended", "closed", "skipped", "more_remain"}``:

    * ``opened`` — episodes CREATED by this pass.
    * ``extended`` — already-open episodes UPDATED by this pass (new readings folded in, or the
      episode closed). A pass that finds nothing new for a monitor writes nothing and counts nothing.
    * ``closed`` — episodes given an ``ended_at`` by this pass, including one that opened and closed
      inside the same pass (a back-dated logger import does that constantly). ``opened`` and
      ``closed`` therefore overlap on purpose; each answers a different question.
    * ``skipped`` — active monitors with NO temperature limit at all. Counted rather than crashed on
      and rather than silently ignored: without a limit nothing can ever be in or out of range, which
      is a configuration gap somebody has to be told about (the 4.11 "an alert with no threshold"
      finding).
    * ``more_remain`` — a cap bit (too many monitors, or too many unwalked readings on one of them)
      and the caller should press again.

    **Scope:** ``status="active"`` monitors in ``tenant``, optionally narrowed to one by ``monitor=``
    (a model instance or a pk), which is what the per-monitor button uses.

    **ONE ``transaction.atomic()`` PER MONITOR, not one for the whole sweep.** A poisoned monitor
    must not roll back the twenty that already succeeded, and a single transaction spanning every
    monitor in a workspace would hold locks for the length of the sweep.

    **Inside each transaction the MONITOR ROW is locked FIRST, before any reading is read** — that
    lock IS the "one open episode per monitor" guard (see the module docstring for why it is not a
    database constraint, and why it is the monitor row rather than the episode).

    **Cost: this is a BATCH action, not a page load.** Roughly three to five queries per monitor plus
    one per episode touched. It belongs behind a ``@tenant_admin_required`` POST — a button, exactly
    as 4.11 runs ``detect_alerts`` — and behind the seeder, so the demo data is produced by this same
    code path and the path is exercised on every ``seed_scm`` run. Never call it from a GET.

    **It writes NOTHING outside its own table** — no ``StockMove``, no ``JournalEntry``, no
    ``LotSerial.status``, no ``Asset.status``, no ``MaintenanceWorkOrder``. Worth asserting in a test.
    """
    summary = {"opened": 0, "extended": 0, "closed": 0, "skipped": 0, "more_remain": False}
    if tenant is None:
        return summary

    candidates = ColdChainMonitor.objects.filter(tenant=tenant, status="active")
    if monitor is not None:
        pk = getattr(monitor, "pk", monitor)
        try:
            candidates = candidates.filter(pk=int(pk))
        except (TypeError, ValueError):
            # A junk pk narrows to nothing rather than raising out of `.filter()` (L11).
            return summary

    # Only the three columns the skip test needs. The row is re-read in full under its own lock
    # below, so this cheap pass cannot make a stale decision that matters.
    rows = list(candidates.order_by("id")
                .values("id", "min_temperature", "max_temperature")[:MAX_MONITORS_PER_SWEEP + 1])
    if len(rows) > MAX_MONITORS_PER_SWEEP:
        summary["more_remain"] = True
        rows = rows[:MAX_MONITORS_PER_SWEEP]

    # The audit rows are written AFTER their transaction commits, the `_status_transition` shape
    # (`views/_helpers.py:451`): an audit row for a write that then rolled back is worse than no
    # audit row, and holding the monitor lock while writing to another table lengthens it for nothing.
    audit = []
    for row in rows:
        if row["min_temperature"] is None and row["max_temperature"] is None:
            summary["skipped"] += 1
            continue
        _detect_one(tenant, row["id"], user, summary, audit)
    for entry in audit:
        write_audit_log(user, entry["object"], entry["action"], entry["changes"])
    return summary


def _detect_one(tenant, monitor_id, user, summary, audit):
    """One monitor, one transaction, one lock. See :func:`detect_excursions` for the contract."""
    now = timezone.now()
    with transaction.atomic():
        # ---- THE LOCK, FIRST, ON THE MONITOR ROW -------------------------------------------------
        # Before any reading is read, and on a row that ALWAYS EXISTS — `select_for_update()` on a
        # queryset that matches nothing locks nothing, which is why the episode row is the wrong
        # thing to lock (the whole point is the case where there is no episode yet). Locking the
        # monitor also serialises the reading-import path against the detector.
        monitor = (ColdChainMonitor.objects.select_for_update()
                   .filter(pk=monitor_id, tenant=tenant).first())
        if monitor is None:
            return  # deleted between the sweep query and the lock

        limit_min, limit_max = monitor.effective_limits()
        if limit_min is None and limit_max is None:
            # Re-checked under the lock: the limits could have been cleared since the sweep query.
            summary["skipped"] += 1
            return
        if monitor.status != "active":
            return  # retired under us

        # Read INSIDE the lock, never before it. Two concurrent passes would otherwise both see "no
        # open episode", both walk and both INSERT — the classic TOCTOU the 4.13 review found twice.
        episode = (TemperatureExcursion.objects
                   .filter(tenant=tenant, monitor_id=monitor_id, ended_at__isnull=True)
                   .order_by("-started_at")
                   .first())

        rows, capped = _unwalked_readings(tenant, monitor, episode)
        if capped:
            summary["more_remain"] = True

        segments = walk_episodes(
            rows, limit_min, limit_max,
            open_started_at=episode.started_at if episode is not None else None)

        for segment in segments:
            if segment["continued"]:
                _extend_episode(tenant, monitor, episode, segment, now, summary, audit)
            else:
                _open_episode(tenant, monitor, segment, now, summary, audit)


def _watermark(tenant, monitor, episode):
    """The moment the walk starts AFTER, or ``None`` to walk this monitor's whole history.

    ``max(open episode's last_detected_at, last closed episode's ended_at, the deployment date)`` —
    so a re-run is cheap and, crucially, **cannot re-open an episode that was already closed**.

    Only one query, because an open episode already dominates: episodes on one monitor cannot
    overlap, so an open one started after the newest closed one ended and its ``last_detected_at`` is
    at or after its own ``started_at``.

    ``last_detected_at`` is written by this module as **the newest folded reading's ``reading_at``**,
    not as the wall clock. That is what makes the watermark honest for a back-dated logger download:
    a clock stamp would sit in the future relative to the data and every subsequent pass would walk
    past rows it had never seen. "When we last saw it breaching" is a statement about the series, not
    about when somebody pressed the button.
    """
    if episode is not None:
        return episode.last_detected_at

    marks = []
    closed = (TemperatureExcursion.objects
              .filter(tenant=tenant, monitor_id=monitor.pk, ended_at__isnull=False)
              .order_by("-ended_at")
              .values_list("ended_at", flat=True)
              .first())
    if closed is not None:
        marks.append(closed)
    if monitor.deployed_on:
        # A microsecond BEFORE the deployment day starts, because the watermark is exclusive and a
        # reading filed at 00:00:00 on the deployment date is legitimate.
        day_start, _ = _moment_bounds(monitor.deployed_on, monitor.deployed_on)
        marks.append(day_start - timedelta(microseconds=1))
    return max(marks) if marks else None


def _unwalked_readings(tenant, monitor, episode):
    """``(rows, capped)`` — the readings this pass has to walk, oldest first and hard-bounded.

    An unbounded walk over the fastest-growing table in the sub-module is the 4.7
    ``MAX_HORIZON_PERIODS`` lesson applied to reads instead of writes: the caller is told
    ``more_remain`` and presses again rather than watching the request time out.

    One row past the cap is fetched so "there is more" is a fact rather than a guess — a plain
    ``len(rows) == cap`` cannot tell a full page from an exactly-full table.
    """
    reading_qs = TemperatureReading.objects.filter(tenant=tenant, monitor_id=monitor.pk)
    watermark = _watermark(tenant, monitor, episode)
    if watermark is not None:
        reading_qs = reading_qs.filter(reading_at__gt=watermark)
    rows = list(reading_qs.order_by("reading_at", "id")
                .values("id", "reading_at", "temperature", "interval_minutes")
                [:MAX_EPISODE_READINGS + 1])
    if len(rows) > MAX_EPISODE_READINGS:
        return rows[:MAX_EPISODE_READINGS], True
    return rows, False


def _last_moment(rows):
    """The newest ``reading_at`` in a segment's rows, or ``None`` when it has none."""
    moments = [_value(row, "reading_at") for row in rows]
    moments = [moment for moment in moments if moment is not None]
    return max(moments) if moments else None


def _open_episode(tenant, monitor, segment, now, summary, audit):
    """Create one ``TemperatureExcursion`` from a fresh segment.

    ``limit_min`` / ``limit_max`` are SNAPSHOTTED here and never touched again — an extend that
    re-snapshotted them would make the record read differently next year, which is the one thing a
    GxP record must not do. ``severity`` is likewise written here and only here.

    ``save()`` rather than ``bulk_create``: ``TenantNumbered.save()`` is what mints ``EXC-00001``,
    and a queue of excursions with blank numbers is a queue nobody can quote in an email.
    """
    limit_min, limit_max = monitor.effective_limits()
    rows = segment["rows"]
    stats = episode_stats(rows, limit_min, limit_max, frozen=monitor.is_frozen_condition)
    started_at = segment["started_at"]
    ended_at = segment["ended_at"]
    duration = episode_duration_minutes(started_at, ended_at, now=now)

    excursion = TemperatureExcursion(
        tenant=tenant,
        monitor=monitor,
        started_at=started_at,
        ended_at=ended_at,
        duration_minutes=duration,
        # `or "high"` only fires for a segment with no readable breach, which `walk_episodes` cannot
        # produce — the column is NOT NULL with a default and this keeps the create honest either way.
        breach_direction=stats["breach_direction"] or "high",
        extreme_temperature=stats["extreme_temperature"],
        limit_min=limit_min,
        limit_max=limit_max,
        reading_count=stats["reading_count"],
        mkt=stats["mkt"],
        last_detected_at=_last_moment(rows) or started_at,
        severity=severity_for(stats["excess_c"], duration, monitor.excursion_grace_minutes),
    )
    excursion.save()

    summary["opened"] += 1
    if ended_at is not None:
        summary["closed"] += 1
    audit.append({
        "object": excursion,
        "action": "create",
        "changes": {
            "action": "detect",
            "monitor": monitor.number,
            "started_at": _json(started_at),
            "ended_at": _json(ended_at),
            "duration_minutes": duration,
            "breach_direction": excursion.breach_direction,
            "extreme_temperature": _json(stats["extreme_temperature"]),
            "excess_c": _json(stats["excess_c"]),
            "limit_min": _json(limit_min),
            "limit_max": _json(limit_max),
            "reading_count": stats["reading_count"],
            "mkt": _json(stats["mkt"]),
            "severity": excursion.severity,
        },
    })


def _extend_episode(tenant, monitor, episode, segment, now, summary, audit):
    """Re-fire the already-open episode: fold in the new readings, and close it if it ended.

    **UPDATE, never a second ``create()``** — that is the merge a database constraint could not have
    performed, and the reason the guard is a lock rather than a constraint.

    The recomputation judges against the monitor's **CURRENT** limits, while ``limit_min`` /
    ``limit_max`` on the row keep the ones snapshotted at open time. The asymmetry is deliberate: the
    snapshot is the audit fact (what band was in force when this fired), the live limits are the
    operational fact (is the freezer back inside the band it is held to *now*). Judging an extension
    against the snapshot would leave an episode open forever after somebody legitimately widened the
    band — the freezer would be fine and the incident would never end.

    ``save(update_fields=…)`` is narrow ON PURPOSE (:data:`EPISODE_UPDATE_FIELDS`): a full ``save()``
    would write back every in-memory column, including any a concurrent triage edit had just
    changed. ``status`` and ``severity`` are not in that list, so a re-fire on an acknowledged and
    downgraded excursion leaves both exactly where the human put them.
    """
    ended_at = segment["ended_at"]
    if not segment["rows"] and ended_at is None:
        # Nothing new and still running. Writing here would be pure churn: the live duration is
        # DERIVED by `TemperatureExcursion.live_duration_minutes()` on every read, so the page is
        # already current without a row update.
        return

    limit_min, limit_max = monitor.effective_limits()
    # The full window, so `reading_count`, the extreme and the MKT describe the WHOLE episode rather
    # than only the rows this pass happened to see. Bounded, and the only extra query an extend costs.
    rows = _window_rows(monitor, episode.started_at, ended_at or now)
    stats = episode_stats(rows, limit_min, limit_max, frozen=monitor.is_frozen_condition)
    duration = episode_duration_minutes(episode.started_at, ended_at, now=now)

    before = {
        "ended_at": episode.ended_at,
        "duration_minutes": episode.duration_minutes,
        "extreme_temperature": episode.extreme_temperature,
        "breach_direction": episode.breach_direction,
        "reading_count": episode.reading_count,
        "mkt": episode.mkt,
    }

    episode.ended_at = ended_at
    episode.duration_minutes = duration
    episode.extreme_temperature = stats["extreme_temperature"]
    if stats["breach_direction"]:
        # Kept when the recomputed window shows no breach at all — which happens the moment somebody
        # widens the band under a running episode. The record should not lose the direction it fired
        # in just because the policy changed afterwards.
        episode.breach_direction = stats["breach_direction"]
    episode.reading_count = stats["reading_count"]
    episode.mkt = stats["mkt"]
    episode.last_detected_at = _last_moment(segment["rows"]) or episode.last_detected_at
    episode.save(update_fields=EPISODE_UPDATE_FIELDS)

    summary["extended"] += 1
    if ended_at is not None:
        summary["closed"] += 1

    changes = {"action": "detect", "monitor": monitor.number,
               "still_running": ended_at is None,
               "new_readings": len(segment["rows"])}
    for name, was in before.items():
        now_value = getattr(episode, name)
        if was != now_value:
            changes[name] = [_json(was), _json(now_value)]
    audit.append({"object": episode, "action": "update", "changes": changes})


# -------------------------------------------------------------------------------------------------
# 4d. The one cross-sub-module verb
# -------------------------------------------------------------------------------------------------

def raise_work_order(excursion, user=None):
    """Raise one 4.13 repair job against the failing unit and point the excursion at it.

    Bullet 5's "alarm code -> work order -> repair" (ORBCOMM, Carrier, Thermo King) and bullet 2's
    "equipment fix raised from the excursion" (SmartSense).

    **Returns ``None`` when the monitor's subject is not an ``Asset``** — a cold room is a
    ``scm.Location`` and a consignment is a ``scm.Shipment``, and neither is a maintainable thing.
    The view messages that rather than 500-ing on a null asset.

    **Idempotent.** The excursion is taken ``select_for_update()`` and ``maintenance_work_order_id``
    is re-read INSIDE the lock, so a double-click cannot raise two jobs (the 4.13 TOCTOU fix); the
    second call returns the SAME job. A caller that needs to know which happened reads
    ``excursion.maintenance_work_order_id`` before calling.

    **One-way link out, no reciprocal edit.** ``source`` is an EXISTING ``SOURCE_CHOICES`` value
    (:data:`WORK_ORDER_SOURCE`) and ``Asset.ASSET_TYPE_CHOICES`` gains no ``reefer`` entry — see the
    module docstring. 4.15 creates the job and stops; 4.13 owns everything that happens to it next.
    """
    tenant_id = excursion.tenant_id
    with transaction.atomic():
        locked = (TemperatureExcursion.objects.select_for_update()
                  .filter(pk=excursion.pk, tenant_id=tenant_id)
                  .first())
        if locked is None:
            return None
        if locked.maintenance_work_order_id:
            # Already raised — re-read under the lock, which is the whole point of taking it.
            return locked.maintenance_work_order

        monitor = locked.monitor
        asset = monitor.asset if monitor.asset_id else None
        if asset is None:
            return None

        limits = _limit_label(locked.limit_min, locked.limit_max)
        extreme = locked.extreme_temperature
        work_order = MaintenanceWorkOrder(
            tenant=locked.tenant,
            asset=asset,
            work_type="corrective",
            priority=SEVERITY_PRIORITY.get(locked.severity, "medium"),
            source=WORK_ORDER_SOURCE,
            title=f"Temperature excursion {locked.number} on {asset.code}"[:255],
            description=(
                f"Raised from cold-chain excursion {locked.number} on monitor "
                f"{monitor.number} ({monitor.name}).\n"
                f"Started {locked.started_at:%Y-%m-%d %H:%M}"
                + (f", ended {locked.ended_at:%Y-%m-%d %H:%M}" if locked.ended_at
                   else ", still running")
                + f".\nDuration {locked.live_duration_minutes()} minutes, "
                  f"{locked.get_breach_direction_display().lower()}.\n"
                + (f"Worst reading {extreme} °C" if extreme is not None
                   else "No extreme temperature recorded")
                + (f" against {limits}." if limits else ".")
            ),
            reported_at=timezone.now(),
        )
        work_order.save()

        locked.maintenance_work_order = work_order
        locked.save(update_fields=["maintenance_work_order", "updated_at"])

    write_audit_log(user, excursion, "update", {
        "action": "raise_work_order",
        "maintenance_work_order": work_order.number,
        "asset": asset.code,
        "priority": work_order.priority,
    })
    return work_order


def _limit_label(limit_min, limit_max):
    """"2.00 to 8.00 °C" / "at most 8.00 °C" / "at least 2.00 °C" / "" — a one-sided band reads
    as one, because "None to 8.00" is not a sentence anybody should find in a work order."""
    if limit_min is not None and limit_max is not None:
        return f"limits {limit_min} to {limit_max} °C"
    if limit_max is not None:
        return f"an upper limit of {limit_max} °C"
    if limit_min is not None:
        return f"a lower limit of {limit_min} °C"
    return ""

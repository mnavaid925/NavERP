"""SCM 4.15 Cold Chain Management — ``apps/scm/coldchain.py``, the excursion detector and the
derived-figure service.

This module is where every measured column on a ``TemperatureExcursion`` comes from, so the tests
below are the ones that decide whether an audit record says something true. They are split into the
two halves the service itself is split into:

* the **pure functions** (``out_of_range`` / ``excess_over_limit`` / ``episode_duration_minutes`` /
  ``severity_for`` / ``mean_kinetic_temperature`` / ``time_in_range`` / ``walk_episodes`` /
  ``episode_stats`` / ``clamp_window``) — no database, no fixtures, called with plain dicts;
* the **writers** (``detect_excursions`` / ``window_stats`` / ``profile`` / ``raise_work_order``) —
  driven through real reading rows, because "the detector is the only writer of the measured block"
  is a claim about what it actually writes.

--------------------------------------------------------------------------------------------------
WHAT THIS FILE CANNOT PROVE, ON THIS ENGINE — READ BEFORE TRUSTING A GREEN RUN
--------------------------------------------------------------------------------------------------
The suite runs under ``config.settings_test``, which is **SQLite in memory**. Production is
**MariaDB**. Two of the sub-module's stated guarantees are therefore NOT exercised here, no matter
how many of these tests pass:

1. **``select_for_update()`` on the monitor row** — the "one open episode per monitor" guard
   (``coldchain.py:32-51``, ``_detect_one``). SQLite has no row-level locking and Django's SQLite
   backend accepts ``select_for_update()`` inside a transaction as a **no-op**; the whole test run is
   single-connection and serial besides. The tests in :class:`TestDetectExcursionsDeDupe` therefore
   measure the *logic* — a second pass MERGES into the open episode instead of inserting a second row
   — and prove **nothing at all** about two concurrent passes racing. A real test of that needs two
   connections against MariaDB and is out of scope for this suite.
2. **The partial-index limitation that is the REASON the guard is a lock** — MariaDB silently drops
   a ``UniqueConstraint(condition=…)``, while SQLite honours it. That asymmetry is precisely why such
   a constraint must never be added here: it would be created under these test settings, pass every
   test in this file, and be **absent in production**. So a green run here is also not evidence that
   a constraint would have been sufficient — if anything it is the trap the model docstring names.

Nothing below asserts a lock was taken. Do not read one into a passing run.

--------------------------------------------------------------------------------------------------
Every reference moment comes from ``cc_moment()`` / ``cc_day()`` in ``_coldchain.py``, which derive
from ``timezone.now()`` / ``timezone.localdate()`` — the same basis the service reads (lesson L16).
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.scm import coldchain
from apps.scm.tests._coldchain import *  # noqa: F401,F403


# =================================================================================================
# Local helpers. Prefixed ``_ccs_`` so no module-level name in this file can shadow one in another
# suite module (``test_suite_hygiene.py``).
# =================================================================================================

def _ccs_row(temperature, minutes=30, moment=None):
    """One reading row as the ``.values()`` DICT the pure functions are handed in production.

    Dicts rather than model instances on purpose: ``profile``, ``_window_rows`` and
    ``_unwalked_readings`` all read through ``.values(...)`` and never instantiate a model, so a
    unit test that only ever passed objects would be exercising the ``isinstance`` branch the
    service does not use at scale.
    """
    # The value is passed through UNCONVERTED when it is not a plain number, so a test can hand the
    # service the junk a real row can actually carry — "", "nan", "Infinity". Coercing here with
    # `Decimal(str(...))` raised `InvalidOperation` inside the HELPER on exactly those inputs, which
    # made the four junk-input tests fail while looking like product failures. A fixture that cannot
    # express the bad case is a fixture that quietly narrows the suite to the happy path.
    if temperature is None or isinstance(temperature, (str, Decimal)):
        value = temperature
    else:
        value = Decimal(str(temperature))
    row = {"temperature": value, "interval_minutes": minutes}
    if moment is not None:
        row["reading_at"] = moment
    return row


def _ccs_arithmetic_mean(rows):
    """The plain average of a row set — the figure MKT must never fall below.

    Coerces the same way the service does, and for the same reason: ``_ccs_row`` passes a value
    through UNCONVERTED when it is a string, so a test can hand the service the junk a caller can
    actually pass ("", "nan"). This helper therefore has to do the conversion itself, and skip
    anything unreadable rather than summing it — mirroring ``coldchain._decimal``, whose whole job is
    that an unreadable value is absent rather than zero.
    """
    values = []
    for row in rows:
        raw = row["temperature"]
        if raw is None:
            continue
        try:
            value = raw if isinstance(raw, Decimal) else Decimal(str(raw).strip())
        except (ArithmeticError, ValueError, TypeError):
            continue
        if value.is_finite():
            values.append(value)
    return sum(values) / Decimal(len(values))


def _ccs_run(monitor, temperatures, **kwargs):
    """File a run of readings and immediately sweep that one monitor. Returns the summary."""
    cc_series(monitor, temperatures, **kwargs)
    return coldchain.detect_excursions(monitor.tenant, monitor=monitor)


def _ccs_episodes(monitor):
    from apps.scm.models import TemperatureExcursion
    return list(TemperatureExcursion.objects.filter(tenant=monitor.tenant, monitor=monitor)
                .order_by("started_at", "id"))


# =================================================================================================
# 4.15 · the pure band arithmetic — no database
# =================================================================================================
class TestOutOfRange:
    """``""`` / ``"high"`` / ``"low"``. Strict comparisons, a ``None`` limit means NO limit on that
    side, and a missing measurement is neither in range nor a breach."""

    @pytest.mark.parametrize("temperature,expected", [
        ("5", ""), ("2", ""), ("8", ""),          # ON the limit is IN range
        ("1.99", "low"), ("8.01", "high"),
        ("-18", "low"), ("40", "high"),
    ])
    def test_the_band_is_inclusive_of_its_own_limits(self, temperature, expected):
        assert coldchain.out_of_range(temperature, Decimal("2"), Decimal("8")) == expected

    def test_a_missing_temperature_is_not_a_breach_and_not_in_range(self):
        """Trap 1: this function must never be handed a ``q4()``-coerced 0 standing in for a blank
        cell, and it must not invent a verdict for one either."""
        assert coldchain.out_of_range(None, Decimal("2"), Decimal("8")) == ""
        assert coldchain.out_of_range("", Decimal("2"), Decimal("8")) == ""
        assert coldchain.out_of_range("not a number", Decimal("2"), Decimal("8")) == ""

    def test_a_one_sided_band_is_judged_on_the_side_it_has(self):
        assert coldchain.out_of_range("-40", None, Decimal("8")) == ""
        assert coldchain.out_of_range("9", None, Decimal("8")) == "high"
        assert coldchain.out_of_range("1", Decimal("2"), None) == "low"
        assert coldchain.out_of_range("500", Decimal("2"), None) == ""

    def test_a_monitor_with_no_limits_at_all_can_never_be_out_of_range(self):
        assert coldchain.out_of_range("999", None, None) == ""

    def test_zero_celsius_is_an_ordinary_reading_and_not_a_missing_one(self):
        assert coldchain.out_of_range("0", Decimal("2"), Decimal("8")) == "low"
        assert coldchain.out_of_range(Decimal("0"), Decimal("-5"), Decimal("5")) == ""


class TestExcessOverLimit:
    def test_it_measures_past_the_limit_on_the_breached_side(self):
        assert coldchain.excess_over_limit("12.5", "high", Decimal("2"), Decimal("8")) \
            == Decimal("4.50")
        assert coldchain.excess_over_limit("-1", "low", Decimal("2"), Decimal("8")) \
            == Decimal("3.00")

    def test_both_directions_report_the_worse_end(self):
        assert coldchain.excess_over_limit("-20", "both", Decimal("2"), Decimal("8")) \
            == Decimal("22.00")

    def test_it_is_none_and_never_zero_when_it_cannot_be_computed(self):
        """An excess of 0 means "it touched the limit exactly" — a different statement from "we
        cannot compute this"."""
        assert coldchain.excess_over_limit(None, "high", Decimal("2"), Decimal("8")) is None
        assert coldchain.excess_over_limit("12", "high", Decimal("2"), None) is None
        assert coldchain.excess_over_limit("12", "", Decimal("2"), Decimal("8")) is None

    def test_touching_the_limit_exactly_is_a_real_zero(self):
        assert coldchain.excess_over_limit("8", "high", Decimal("2"), Decimal("8")) \
            == Decimal("0.00")

    def test_it_is_the_same_arithmetic_the_model_renders(self, cc_excursion_a):
        assert coldchain.excess_over_limit(
            cc_excursion_a.extreme_temperature, cc_excursion_a.breach_direction,
            cc_excursion_a.limit_min, cc_excursion_a.limit_max) == cc_excursion_a.excess_c()


class TestEpisodeDurationMinutes:
    def test_a_closed_window_is_its_own_span(self):
        started = cc_moment(180)
        assert coldchain.episode_duration_minutes(
            started, started + datetime.timedelta(minutes=90)) == 90

    def test_a_running_window_is_measured_to_the_supplied_clock(self):
        started = cc_moment(120)
        assert coldchain.episode_duration_minutes(started, None, now=started
                                                  + datetime.timedelta(minutes=45)) == 45

    def test_no_start_is_zero_rather_than_an_exception(self):
        assert coldchain.episode_duration_minutes(None, None) == 0

    def test_a_reversed_window_floors_at_zero(self):
        started = cc_moment(10)
        assert coldchain.episode_duration_minutes(
            started, started - datetime.timedelta(hours=5)) == 0

    def test_it_is_clamped_so_a_report_cannot_overflow_a_timedelta(self):
        """This figure is fed to ``timedelta(minutes=…)`` on the report pages, where an out-of-range
        value is an uncaught ``OverflowError`` — a 500, not a message (the 4.10 DoS finding)."""
        from apps.scm.models import MAX_EXCURSION_MINUTES
        started = timezone.now() - datetime.timedelta(days=4000)
        assert coldchain.episode_duration_minutes(started, None) == MAX_EXCURSION_MINUTES


class TestSeverityFor:
    """The detector's OPENING grade, written once and never re-applied."""

    def test_a_big_excess_is_critical_on_its_own(self):
        assert coldchain.severity_for(Decimal("5"), 1, 30) == "critical"
        assert coldchain.severity_for(Decimal("40"), 0, 30) == "critical"

    def test_a_long_run_is_critical_even_on_a_small_excess(self):
        """A half-degree breach that has run for a day is not a minor event."""
        assert coldchain.severity_for(Decimal("0.5"), 30 * coldchain.CRITICAL_GRACE_MULTIPLE, 30) \
            == "critical"

    def test_a_moderate_excess_is_major(self):
        assert coldchain.severity_for(Decimal("2"), 0, 30) == "major"

    def test_outliving_the_grace_period_at_all_is_major(self):
        """A reportable episode is never opened below ``major`` — that is what
        ``TemperatureExcursion.is_reportable`` means."""
        assert coldchain.severity_for(Decimal("0.1"), 30, 30) == "major"

    def test_a_blip_inside_the_grace_period_is_minor(self):
        assert coldchain.severity_for(Decimal("0.5"), 5, 30) == "minor"

    def test_a_negative_excess_is_read_as_a_magnitude(self):
        assert coldchain.severity_for(Decimal("-6"), 1, 30) == "critical"

    def test_an_unknown_excess_rests_the_judgement_on_duration_alone(self):
        """``None`` must not default to the worst or the best case."""
        assert coldchain.severity_for(None, 5, 30) == "minor"
        assert coldchain.severity_for(None, 30, 30) == "major"
        assert coldchain.severity_for(None, 200, 30) == "critical"

    def test_a_zero_grace_period_uses_the_stand_in_unit_rather_than_marking_everything_critical(self):
        """``duration >= grace * 4`` is true for every episode when the grace is 0, which would
        grade the whole queue critical and make the colour meaningless."""
        assert coldchain.severity_for(Decimal("0.1"), 30, 0) == "major"
        assert coldchain.severity_for(Decimal("0.1"), 0, 0) == "minor"
        assert coldchain.severity_for(
            Decimal("0.1"), coldchain.UNGRACED_UNIT_MINUTES * coldchain.CRITICAL_GRACE_MULTIPLE,
            0) == "critical"

    @pytest.mark.parametrize("duration,grace", [("NaN", 30), (None, None), ("abc", "abc"),
                                                (-5, -5)])
    def test_junk_duration_or_grace_degrades_rather_than_raising(self, duration, grace):
        assert coldchain.severity_for(None, duration, grace) in ("critical", "major", "minor")

    def test_a_junk_excess_string_is_read_as_unknown(self):
        assert coldchain.severity_for("Infinity", 5, 30) == "minor"


class TestClampWindow:
    def test_a_reversed_pair_is_swapped_rather_than_rendered_as_nothing(self):
        early, late = cc_day(-5), cc_day()
        assert coldchain.clamp_window(late, early) == (early, late, False)

    def test_an_ordinary_window_is_left_alone(self):
        early, late = cc_day(-5), cc_day()
        assert coldchain.clamp_window(early, late) == (early, late, False)

    def test_the_cap_is_reported_rather_than_applied_silently(self):
        from apps.scm.models import MAX_READING_WINDOW_DAYS
        date_to = cc_day()
        date_from, resolved_to, capped = coldchain.clamp_window(cc_day(-400), date_to)
        assert capped is True
        assert resolved_to == date_to
        assert (date_to - date_from).days == MAX_READING_WINDOW_DAYS - 1

    def test_the_widest_uncapped_window_is_inclusive_of_both_ends(self):
        from apps.scm.models import MAX_READING_WINDOW_DAYS
        date_to = cc_day()
        date_from = date_to - datetime.timedelta(days=MAX_READING_WINDOW_DAYS - 1)
        assert coldchain.clamp_window(date_from, date_to) == (date_from, date_to, False)


# =================================================================================================
# 4.15 · mean kinetic temperature (USP <1079.2>)
# =================================================================================================
class TestMeanKineticTemperature:
    def test_it_is_at_or_above_the_arithmetic_mean_for_a_varying_series(self):
        """The real correctness check on the formula rather than a smoke test: the Arrhenius
        weighting can never be *kinder* than the plain average."""
        rows = [_ccs_row(t) for t in ("2", "4", "6", "20", "3", "5")]
        mkt = coldchain.mean_kinetic_temperature(rows)
        assert mkt is not None
        assert mkt > _ccs_arithmetic_mean(rows)

    def test_it_equals_the_arithmetic_mean_for_a_constant_series(self):
        rows = [_ccs_row("5") for _ in range(8)]
        assert coldchain.mean_kinetic_temperature(rows) == Decimal("5.00")

    def test_a_frozen_monitor_answers_none_and_never_zero(self):
        """USP <1079.2>: MKT does not apply to frozen product. An MKT of 0 °C reads as a
        perfectly-cold shipment, which is the precise opposite of "this does not apply"."""
        rows = [_ccs_row(t) for t in ("-18", "-22", "-15")]
        assert coldchain.mean_kinetic_temperature(rows, frozen=True) is None
        assert coldchain.mean_kinetic_temperature(rows, frozen=False) is not None

    def test_a_frozen_MONITOR_carries_that_answer_all_the_way_through_the_service(
            self, cc_monitor_frozen_a):
        cc_series(cc_monitor_frozen_a, ["-30", "-32", "-28"])
        result = coldchain.profile(cc_monitor_frozen_a, date_from=cc_day(-1), date_to=cc_day())
        assert result["frozen"] is True
        assert result["mkt"] is None
        assert result["count"] > 0        # readings exist; only the MKT is unanswerable

    def test_an_empty_or_unreadable_window_answers_none(self):
        assert coldchain.mean_kinetic_temperature([]) is None
        assert coldchain.mean_kinetic_temperature([_ccs_row(None), _ccs_row("")]) is None

    def test_a_zero_weight_row_falls_back_to_one_minute_rather_than_being_dropped(self):
        """Losing a real measurement because its metadata is thin is worse than under-weighting it."""
        assert coldchain.mean_kinetic_temperature([_ccs_row("5", minutes=0)]) == Decimal("5.00")
        assert coldchain.mean_kinetic_temperature([_ccs_row("5", minutes="junk")]) == Decimal("5.00")

    def test_it_is_MINUTE_weighted_and_not_row_weighted(self):
        """A single hot hour inside a cold month must weigh one hour, not "one row" — the entire
        reason ``interval_minutes`` is snapshotted onto every reading."""
        light = [_ccs_row("2", minutes=60), _ccs_row("30", minutes=1)]
        heavy = [_ccs_row("2", minutes=60), _ccs_row("30", minutes=60)]
        assert coldchain.mean_kinetic_temperature(light) \
            < coldchain.mean_kinetic_temperature(heavy)

    def test_a_result_outside_the_physical_bounds_answers_none(self):
        """Which would be a ``DataError`` on save rather than a number anybody should read."""
        assert coldchain.mean_kinetic_temperature([_ccs_row("-250")]) is None

    def test_a_temperature_below_absolute_zero_is_skipped_rather_than_dividing_by_zero(self):
        assert coldchain.mean_kinetic_temperature([_ccs_row("-300")]) is None

    def test_it_accepts_model_instances_as_well_as_value_dicts(self, cc_monitor_a):
        rows = cc_series(cc_monitor_a, ["4", "6", "5"])
        assert coldchain.mean_kinetic_temperature(rows) is not None


# =================================================================================================
# 4.15 · time in range — minute-weighted, and None on nothing to say
# =================================================================================================
class TestTimeInRange:
    def test_it_weights_by_minutes_and_not_by_row_count(self):
        rows = [_ccs_row("5", minutes=60), _ccs_row("12", minutes=15)]
        spread = coldchain.time_in_range(rows, Decimal("2"), Decimal("8"))
        assert spread == {"count": 2, "in_minutes": 60, "out_minutes": 15,
                          "total_minutes": 75, "pct_in_range": Decimal("80.00")}

    def test_never_in_range_is_a_real_zero_percent(self):
        rows = [_ccs_row("12"), _ccs_row("14")]
        assert coldchain.time_in_range(rows, Decimal("2"), Decimal("8"))["pct_in_range"] \
            == Decimal("0.00")

    def test_no_readings_is_none_rather_than_zero_percent(self):
        """Conflating "never in range" with "we have no readings" is how a page lies."""
        spread = coldchain.time_in_range([], Decimal("2"), Decimal("8"))
        assert spread["count"] == 0
        for key in ("in_minutes", "out_minutes", "total_minutes", "pct_in_range"):
            assert spread[key] is None

    def test_an_unbanded_monitor_keeps_its_count_but_has_no_verdict(self):
        """The readings exist; the verdict does not."""
        spread = coldchain.time_in_range([_ccs_row("5"), _ccs_row("9")], None, None)
        assert spread["count"] == 2
        assert spread["pct_in_range"] is None
        assert spread["in_minutes"] is None

    def test_a_row_with_no_readable_temperature_is_neither_in_nor_out(self):
        rows = [_ccs_row("5"), _ccs_row(None), _ccs_row("")]
        spread = coldchain.time_in_range(rows, Decimal("2"), Decimal("8"))
        assert spread["count"] == 1
        assert spread["total_minutes"] == 30


# =================================================================================================
# 4.15 · the episode walk — this is THE algorithm
# =================================================================================================
class TestWalkEpisodes:
    """Open at the first out-of-range reading, extend while it stays out, close at the first reading
    back inside the band."""

    def _series(self, temperatures):
        base = cc_moment(600)
        return [_ccs_row(value, moment=base + datetime.timedelta(minutes=30 * index))
                for index, value in enumerate(temperatures)]

    def test_one_breach_run_becomes_exactly_one_closed_segment(self):
        rows = self._series(["5", "12", "13", "12", "5", "5"])
        segments = coldchain.walk_episodes(rows, Decimal("2"), Decimal("8"))
        assert len(segments) == 1
        assert segments[0]["started_at"] == rows[1]["reading_at"]
        assert segments[0]["ended_at"] == rows[4]["reading_at"]
        assert len(segments[0]["rows"]) == 3      # only the BREACHING rows
        assert segments[0]["continued"] is False

    def test_two_separated_breaches_become_two_segments(self):
        rows = self._series(["12", "5", "5", "1", "5"])
        segments = coldchain.walk_episodes(rows, Decimal("2"), Decimal("8"))
        assert len(segments) == 2
        assert segments[0]["ended_at"] == rows[1]["reading_at"]
        assert segments[1]["started_at"] == rows[3]["reading_at"]

    def test_a_series_that_ends_while_breaching_leaves_the_segment_open(self):
        rows = self._series(["5", "12", "12"])
        segments = coldchain.walk_episodes(rows, Decimal("2"), Decimal("8"))
        assert len(segments) == 1 and segments[0]["ended_at"] is None

    def test_an_all_in_range_series_produces_no_segment(self):
        assert coldchain.walk_episodes(self._series(["3", "4", "5"]),
                                       Decimal("2"), Decimal("8")) == []

    def test_open_started_at_seeds_the_walk_as_already_inside_an_episode(self):
        rows = self._series(["12", "12", "5"])
        opened = cc_moment(900)
        segments = coldchain.walk_episodes(rows, Decimal("2"), Decimal("8"),
                                           open_started_at=opened)
        assert len(segments) == 1
        assert segments[0]["continued"] is True
        assert segments[0]["started_at"] == opened
        assert segments[0]["ended_at"] == rows[2]["reading_at"]

    def test_a_continued_segment_can_close_without_gaining_a_single_row(self):
        """The case where the very first new reading was back in range — the stored episode is
        closed without gaining a row, and the caller must still write the end time."""
        rows = self._series(["5"])
        segments = coldchain.walk_episodes(rows, Decimal("2"), Decimal("8"),
                                           open_started_at=cc_moment(900))
        assert len(segments) == 1
        assert segments[0]["rows"] == []
        assert segments[0]["ended_at"] == rows[0]["reading_at"]

    def test_a_blank_cell_can_neither_open_an_episode_nor_be_read_as_zero_celsius(self):
        rows = [_ccs_row(None, moment=cc_moment(120)), _ccs_row("", moment=cc_moment(90))]
        assert coldchain.walk_episodes(rows, Decimal("2"), Decimal("8")) == []


class TestEpisodeStats:
    def _rows(self, temperatures):
        return [_ccs_row(value) for value in temperatures]

    def test_reading_count_covers_every_readable_row_in_or_out_of_range(self):
        stats = coldchain.episode_stats(self._rows(["5", "12", "13"]),
                                        Decimal("2"), Decimal("8"))
        assert stats["reading_count"] == 3

    def test_a_window_with_no_breach_reports_an_empty_direction_rather_than_a_default(self):
        """``""`` rather than ``high``, so a caller keeps whatever direction is stored instead of a
        fresh row claiming ``high`` about an episode that never went high."""
        stats = coldchain.episode_stats(self._rows(["5", "6"]), Decimal("2"), Decimal("8"))
        assert stats["breach_direction"] == ""
        assert stats["extreme_temperature"] is None
        assert stats["excess_c"] is None

    def test_a_high_episode_reports_its_maximum(self):
        stats = coldchain.episode_stats(self._rows(["9", "14", "11"]),
                                        Decimal("2"), Decimal("8"))
        assert stats["breach_direction"] == "high"
        assert stats["extreme_temperature"] == Decimal("14.00")
        assert stats["excess_c"] == Decimal("6.00")

    def test_a_low_episode_reports_its_minimum(self):
        stats = coldchain.episode_stats(self._rows(["1", "-4", "0"]),
                                        Decimal("2"), Decimal("8"))
        assert stats["breach_direction"] == "low"
        assert stats["extreme_temperature"] == Decimal("-4.00")
        assert stats["excess_c"] == Decimal("6.00")

    def test_a_both_direction_window_records_the_end_that_went_further(self):
        stats = coldchain.episode_stats(self._rows(["-10", "9", "5"]),
                                        Decimal("2"), Decimal("8"))
        assert stats["breach_direction"] == "both"
        assert stats["extreme_temperature"] == Decimal("-10.00")
        assert stats["excess_c"] == Decimal("12.00")

    def test_the_mkt_it_reports_is_none_for_a_frozen_monitor(self):
        stats = coldchain.episode_stats(self._rows(["-30", "-10"]), Decimal("-45"),
                                        Decimal("-25"), frozen=True)
        assert stats["mkt"] is None
        assert stats["breach_direction"] == "high"   # -10 is above the -25 ceiling


# =================================================================================================
# 4.15 · the detector — opening an episode
# =================================================================================================
class TestDetectExcursionsOpen:
    def test_an_out_of_range_run_opens_exactly_one_episode(self, cc_monitor_a):
        summary = _ccs_run(cc_monitor_a, ["5", "12", "13", "12", "5"])
        assert summary["opened"] == 1
        assert summary["closed"] == 1
        assert summary["extended"] == 0
        assert len(_ccs_episodes(cc_monitor_a)) == 1

    def test_the_episode_it_writes_is_the_measured_block_and_nothing_typed(self, cc_monitor_a):
        _ccs_run(cc_monitor_a, ["5", "12", "13", "12", "5"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.number == "EXC-00001"
        assert episode.breach_direction == "high"
        assert episode.extreme_temperature == Decimal("13.00")
        assert episode.duration_minutes == 90
        assert episode.limit_min == Decimal("2.00") and episode.limit_max == Decimal("8.00")
        assert episode.mkt is not None
        assert episode.status == "open"            # triage, untouched by the detector
        assert episode.assessment == "pending"

    def test_an_all_in_range_series_opens_nothing(self, cc_monitor_a):
        summary = _ccs_run(cc_monitor_a, ["3", "4", "5", "6"])
        assert summary == {"opened": 0, "extended": 0, "closed": 0, "skipped": 0,
                           "more_remain": False, "more_monitors": False,
                           "last_monitor_id": cc_monitor_a.pk}

    def test_a_still_breaching_run_leaves_the_episode_open(self, cc_monitor_a):
        _ccs_run(cc_monitor_a, ["5", "12", "12"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.ended_at is None
        assert episode.is_episode_running is True

    def test_a_LOW_breach_is_detected_as_readily_as_a_high_one(self, cc_monitor_a):
        _ccs_run(cc_monitor_a, ["5", "-2", "5"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.breach_direction == "low"
        assert episode.extreme_temperature == Decimal("-2.00")

    def test_the_severity_it_opens_with_is_severity_for(self, cc_monitor_a):
        _ccs_run(cc_monitor_a, ["5", "20", "5"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        # 20 °C against an 8 °C ceiling is a 12 °C excess — critical on excess alone.
        assert episode.severity == "critical"

    def test_an_episode_opened_and_closed_in_ONE_pass_counts_the_rows_its_own_page_lists(
            self, cc_monitor_a):
        """REGRESSION LOCK — this was a real bug. An episode is CLOSED BY the first reading back
        inside the band, and that row falls inside ``[started_at, ended_at]``, so it is one of the
        rows ``TemperatureExcursion.readings()`` lists. Counting only the breaching rows made a
        back-dated import file an episode whose badge disagreed with its own reading table."""
        _ccs_run(cc_monitor_a, ["5", "12", "13", "12", "5"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.reading_count == episode.readings().count()
        assert episode.reading_count == 4      # three breaching + the closing in-range row

    def test_the_same_identity_holds_for_an_episode_a_LATER_pass_closed(self, cc_monitor_a):
        """The two writers (`_open_episode` and `_extend_episode`) must agree, or the same weather
        would report a different row count depending on when somebody pressed the button."""
        _ccs_run(cc_monitor_a, ["5", "12", "13"], first_minutes_ago=300, step_minutes=30)
        cc_file_reading(cc_monitor_a, 210, "12.00")
        cc_file_reading(cc_monitor_a, 180, "5.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.ended_at is not None
        assert episode.reading_count == episode.readings().count()

    def test_a_breach_shorter_than_the_grace_period_is_recorded_but_NOT_reportable(
            self, cc_monitor_a):
        """The grace period is what separates "an incident" from "a door-open", and it does that by
        GRADING rather than by hiding the row: without it every door-open fills the queue inside a
        week and then nobody reads it. The episode still exists (a compliance log that silently
        dropped breaches would be worse), it is simply minor and not reportable — and moving the
        monitor's grace moves the answer, because nothing about it is stored."""
        cc_monitor_a.excursion_grace_minutes = 60
        cc_monitor_a.save(update_fields=["excursion_grace_minutes"])
        _ccs_run(cc_monitor_a, ["5", "8.5", "5"])
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.duration_minutes == 30
        assert episode.severity == "minor"
        assert episode.is_reportable is False

        cc_monitor_a.excursion_grace_minutes = 10
        cc_monitor_a.save(update_fields=["excursion_grace_minutes"])
        episode.monitor.refresh_from_db()
        assert episode.is_reportable is True

    def test_an_active_monitor_with_no_limits_is_SKIPPED_and_counted(self, cc_monitor_unlimited_a):
        """Counted rather than crashed on and rather than silently ignored — without a limit nothing
        can ever be in or out of range, which is a configuration gap somebody has to be told about
        (the 4.11 "an alert with no threshold" finding)."""
        cc_monitor_unlimited_a.status = "active"
        cc_monitor_unlimited_a.save(update_fields=["status"])
        cc_series(cc_monitor_unlimited_a, ["5", "40", "5"])
        summary = coldchain.detect_excursions(cc_monitor_unlimited_a.tenant,
                                              monitor=cc_monitor_unlimited_a)
        assert summary["skipped"] == 1
        assert summary["opened"] == 0
        assert summary["last_monitor_id"] == cc_monitor_unlimited_a.pk

    def test_an_inactive_monitor_is_not_detected_against_at_all(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["5", "12", "5"])
        cc_monitor_a.status = "retired"
        cc_monitor_a.save(update_fields=["status"])
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        assert summary["opened"] == 0 and summary["skipped"] == 0
        assert _ccs_episodes(cc_monitor_a) == []

    def test_a_reading_before_the_deployment_date_is_never_walked(self, cc_monitor_a):
        """``_watermark`` starts a first sweep at the deployment day, so an earlier consignment's
        rows cannot raise an episode against this deployment."""
        from apps.scm.models import TemperatureReading
        stale = timezone.now() - datetime.timedelta(days=40)
        TemperatureReading.objects.create(
            tenant=cc_monitor_a.tenant, monitor=cc_monitor_a, reading_at=stale,
            temperature=Decimal("30.00"), interval_minutes=30, source="manual")
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        assert summary["opened"] == 0

    def test_it_writes_NOTHING_outside_its_own_table(self, cc_monitor_asset_a, lot_a):
        """No ``StockMove``, no ``JournalEntry``, no ``LotSerial.status``, no ``Asset.status``, no
        ``MaintenanceWorkOrder``. The detector's whole surface is one table."""
        from apps.scm.models import (Asset, MaintenanceWorkOrder, StockMove)
        before = (StockMove.objects.count(), MaintenanceWorkOrder.objects.count(),
                  lot_a.status, Asset.objects.get(pk=cc_monitor_asset_a.asset_id).status,
                  cc_monitor_asset_a.status)
        cc_series(cc_monitor_asset_a, ["-20", "0", "-20"])
        coldchain.detect_excursions(cc_monitor_asset_a.tenant, monitor=cc_monitor_asset_a)
        lot_a.refresh_from_db()
        cc_monitor_asset_a.refresh_from_db()
        assert (StockMove.objects.count(), MaintenanceWorkOrder.objects.count(),
                lot_a.status, Asset.objects.get(pk=cc_monitor_asset_a.asset_id).status,
                cc_monitor_asset_a.status) == before

    def test_it_writes_one_audit_row_per_episode(self, cc_monitor_a, admin_user):
        from apps.core.models import AuditLog
        before = AuditLog.objects.count()
        _ccs_run(cc_monitor_a, ["5", "12", "5"])
        assert AuditLog.objects.count() == before + 1
        entry = AuditLog.objects.order_by("-id").first()
        assert entry.action == "create"
        assert entry.changes["action"] == "detect"
        # Decimals and datetimes are stringified — a raw Decimal in a JSONField is a TypeError that
        # would turn a successful pass into a 500 at the very last step.
        assert isinstance(entry.changes["extreme_temperature"], str)

    def test_a_tenant_less_caller_gets_an_empty_summary_rather_than_a_crash(self):
        summary = coldchain.detect_excursions(None)
        assert summary["opened"] == 0 and summary["last_monitor_id"] is None

    def test_a_junk_monitor_pk_narrows_to_nothing_rather_than_raising(self, cc_monitor_a):
        """L11 — a value that is not a pk must SKIP rather than raise out of ``.filter()``."""
        cc_series(cc_monitor_a, ["5", "12", "5"])
        assert coldchain.detect_excursions(cc_monitor_a.tenant, monitor="abc")["opened"] == 0

    def test_a_junk_cursor_sweeps_from_the_start_rather_than_doing_nothing(self, cc_monitor_a):
        """Walking the first page twice is a wasted press; walking nothing is a silent no-op."""
        cc_series(cc_monitor_a, ["5", "12", "5"])
        assert coldchain.detect_excursions(cc_monitor_a.tenant, after="not-a-cursor")["opened"] == 1

    def test_a_sweep_never_reaches_another_workspaces_monitor(self, cc_monitor_a, cc_monitor_b):
        cc_series(cc_monitor_b, ["5", "12", "5"])
        summary = coldchain.detect_excursions(cc_monitor_a.tenant)
        assert summary["opened"] == 0
        assert _ccs_episodes(cc_monitor_b) == []


# =================================================================================================
# 4.15 · the detector — de-duplication and the merge
#
# NOTE ON WHAT THESE PROVE. See the module docstring: the production guard is
# ``select_for_update()`` on the MONITOR row, and SQLite makes that a no-op. Everything below
# measures the LOGIC (a second pass merges rather than inserting), not the lock.
# =================================================================================================
class TestDetectExcursionsDeDupe:
    def test_running_the_pass_twice_does_not_open_a_second_episode(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["5", "12", "13", "12", "5"])
        first = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        second = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        assert first["opened"] == 1
        assert second["opened"] == 0 and second["extended"] == 0
        assert len(_ccs_episodes(cc_monitor_a)) == 1

    def test_a_breach_that_keeps_breaching_EXTENDS_the_open_row_rather_than_raising_a_second(
            self, cc_monitor_a):
        """The merge a database constraint could not have performed — which is why the guard is a
        lock rather than a ``UniqueConstraint``."""
        cc_file_reading(cc_monitor_a, 180, "5.00")
        cc_file_reading(cc_monitor_a, 150, "12.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        first_seen = episode.last_detected_at

        cc_file_reading(cc_monitor_a, 120, "14.00")
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode.refresh_from_db()
        assert summary["extended"] == 1 and summary["opened"] == 0
        assert len(_ccs_episodes(cc_monitor_a)) == 1
        assert episode.extreme_temperature == Decimal("14.00")
        assert episode.last_detected_at > first_seen
        assert episode.ended_at is None

    def test_a_later_pass_closes_the_open_episode_when_the_fridge_recovers(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 180, "12.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        cc_file_reading(cc_monitor_a, 150, "5.00")
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert summary["closed"] == 1 and summary["extended"] == 1
        assert episode.ended_at is not None

    def test_a_re_run_can_never_re_open_an_episode_that_was_already_closed(self, cc_monitor_a):
        """The watermark is a statement about the SERIES, not about the clock."""
        cc_series(cc_monitor_a, ["5", "12", "5"])
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        for _ in range(3):
            coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        assert len(_ccs_episodes(cc_monitor_a)) == 1

    def test_a_pass_that_finds_nothing_new_writes_nothing_at_all(self, cc_monitor_a):
        cc_file_reading(cc_monitor_a, 180, "12.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        stamp = episode.updated_at
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode.refresh_from_db()
        assert summary["extended"] == 0
        assert episode.updated_at == stamp

    def test_a_re_fire_leaves_the_triage_STATUS_exactly_where_a_human_put_it(self, cc_monitor_a,
                                                                             admin_user):
        cc_file_reading(cc_monitor_a, 180, "12.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        episode.acknowledge(admin_user)

        cc_file_reading(cc_monitor_a, 150, "14.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode.refresh_from_db()
        assert episode.status == "investigating"
        assert episode.extreme_temperature == Decimal("14.00")

    def test_a_re_fire_never_re_escalates_a_severity_a_triager_downgraded(self, cc_monitor_a):
        """"Recompute everything on every pass" is the natural instinct and it is wrong here: the
        queue would silently re-escalate everything anybody had already judged."""
        cc_file_reading(cc_monitor_a, 180, "20.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.severity == "critical"
        episode.severity = "minor"
        episode.save(update_fields=["severity"])

        cc_file_reading(cc_monitor_a, 150, "25.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode.refresh_from_db()
        assert episode.severity == "minor"

    def test_the_snapshotted_limits_are_NEVER_rewritten_when_the_band_is_edited(self, cc_monitor_a):
        """The record must read the same next year. An audit reader has to still see the band that
        was actually in force when this fired, not the one somebody set afterwards."""
        cc_file_reading(cc_monitor_a, 240, "12.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert (episode.limit_min, episode.limit_max) == (Decimal("2.00"), Decimal("8.00"))

        cc_monitor_a.min_temperature = Decimal("-30.00")
        cc_monitor_a.max_temperature = Decimal("30.00")
        cc_monitor_a.save(update_fields=["min_temperature", "max_temperature"])

        cc_file_reading(cc_monitor_a, 210, "5.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode.refresh_from_db()
        assert (episode.limit_min, episode.limit_max) == (Decimal("2.00"), Decimal("8.00"))
        # …and the EXTENSION was judged against the CURRENT band, so the incident could end.
        assert episode.ended_at is not None

    def test_widening_the_band_under_a_running_episode_lets_it_end(self, cc_monitor_a):
        """Judging an extension against the snapshot would leave an episode open forever after a
        legitimate re-band — the freezer would be fine and the incident would never close."""
        cc_file_reading(cc_monitor_a, 240, "9.00")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        cc_monitor_a.max_temperature = Decimal("12.00")
        cc_monitor_a.save(update_fields=["max_temperature"])
        cc_file_reading(cc_monitor_a, 210, "9.50")
        coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        episode = _ccs_episodes(cc_monitor_a)[0]
        assert episode.ended_at is not None
        assert episode.breach_direction == "high"   # the direction it FIRED in is kept


# =================================================================================================
# 4.15 · the sweep cursor
# =================================================================================================
class TestDetectExcursionsCursor:
    def test_the_cursor_advances_past_the_monitor_cap_and_the_next_press_continues(
            self, cc_monitor_a, cc_monitor_a2, monkeypatch):
        """``MAX_MONITORS_PER_SWEEP`` is 500 in production; it is patched to 1 here so the cap is
        reachable without seeding 501 probes. The behaviour under test is the CURSOR: the sweep is
        ordered by id, so a cursor-less re-run walks the same first page forever and the monitors
        past the cap are reachable only through their own per-monitor button."""
        monkeypatch.setattr(coldchain, "MAX_MONITORS_PER_SWEEP", 1)
        cc_series(cc_monitor_a, ["5", "12", "5"])
        cc_series(cc_monitor_a2, ["5", "12", "5"])
        first, second = sorted([cc_monitor_a, cc_monitor_a2], key=lambda m: m.pk)

        pass_one = coldchain.detect_excursions(cc_monitor_a.tenant)
        assert pass_one["more_remain"] is True and pass_one["more_monitors"] is True
        assert pass_one["last_monitor_id"] == first.pk
        assert pass_one["opened"] == 1
        assert _ccs_episodes(second) == []

        pass_two = coldchain.detect_excursions(cc_monitor_a.tenant,
                                               after=pass_one["last_monitor_id"])
        assert pass_two["opened"] == 1
        assert pass_two["more_monitors"] is False
        assert len(_ccs_episodes(second)) == 1

    def test_a_cursor_less_re_run_walks_the_same_first_page_again(self, cc_monitor_a,
                                                                  cc_monitor_a2, monkeypatch):
        """The half a plain re-press cannot fix — which is exactly why ``more_monitors`` is reported
        apart from ``more_remain``."""
        monkeypatch.setattr(coldchain, "MAX_MONITORS_PER_SWEEP", 1)
        cc_series(cc_monitor_a2, ["5", "12", "5"])
        second = max([cc_monitor_a, cc_monitor_a2], key=lambda m: m.pk)
        for _ in range(3):
            coldchain.detect_excursions(cc_monitor_a.tenant)
        assert _ccs_episodes(second) == [] if second is cc_monitor_a2 else True

    def test_a_skipped_monitor_still_advances_the_cursor_past_itself(self, cc_monitor_a,
                                                                     cc_monitor_unlimited_a):
        """A cursor that stalled on an unconfigurable monitor would be the same bug in a smaller
        box."""
        cc_monitor_unlimited_a.status = "active"
        cc_monitor_unlimited_a.save(update_fields=["status"])
        summary = coldchain.detect_excursions(cc_monitor_a.tenant)
        assert summary["skipped"] == 1
        assert summary["last_monitor_id"] == max(cc_monitor_a.pk, cc_monitor_unlimited_a.pk)

    def test_the_READING_cap_reports_more_remain_without_the_monitor_flag(self, cc_monitor_a,
                                                                          monkeypatch):
        """The reading cap is SELF-HEALING — each pass advances the watermark — so it must not be
        reported as the monitor cap, which is not."""
        monkeypatch.setattr(coldchain, "MAX_EPISODE_READINGS", 2)
        cc_series(cc_monitor_a, ["5", "12", "13", "12", "5"])
        summary = coldchain.detect_excursions(cc_monitor_a.tenant, monitor=cc_monitor_a)
        assert summary["more_remain"] is True
        assert summary["more_monitors"] is False


# =================================================================================================
# 4.15 · window_stats — the manual create path types NOT ONE measured number
# =================================================================================================
class TestWindowStats:
    def test_every_measured_figure_comes_from_the_readings_in_the_window(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["5", "12", "13", "5"], first_minutes_ago=240, step_minutes=30)
        stats = coldchain.window_stats(cc_monitor_a, cc_moment(240), cc_moment(150))
        assert stats["reading_count"] == 4
        assert stats["breach_direction"] == "high"
        assert stats["extreme_temperature"] == Decimal("13.00")
        assert stats["limit_min"] == Decimal("2.00") and stats["limit_max"] == Decimal("8.00")
        assert stats["duration_minutes"] == 90
        assert stats["severity"] in ("critical", "major", "minor")
        assert stats["mkt"] is not None

    def test_a_window_with_no_readings_comes_back_blank_and_never_fabricated(self, cc_monitor_a):
        stats = coldchain.window_stats(cc_monitor_a, cc_moment(600), cc_moment(540))
        assert stats["reading_count"] == 0
        assert stats["extreme_temperature"] is None
        assert stats["mkt"] is None
        # The LIMITS are still snapshotted — they are the monitor's, not a measurement.
        assert stats["limit_min"] == Decimal("2.00")
        # `breach_direction` falls back to `high` because the column is NOT NULL with a default.
        assert stats["breach_direction"] == "high"

    def test_a_still_running_window_is_measured_to_the_supplied_clock(self, cc_monitor_a):
        started = cc_moment(120)
        stats = coldchain.window_stats(cc_monitor_a, started, None,
                                       now=started + datetime.timedelta(minutes=45))
        assert stats["duration_minutes"] == 45
        assert stats["last_detected_at"] == started

    def test_it_is_graded_by_the_SAME_rule_the_detector_opens_with(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["20"], first_minutes_ago=200)
        stats = coldchain.window_stats(cc_monitor_a, cc_moment(240), cc_moment(150))
        assert stats["severity"] == coldchain.severity_for(
            Decimal("12.00"), stats["duration_minutes"], cc_monitor_a.excursion_grace_minutes)


# =================================================================================================
# 4.15 · profile — the derived temperature profile
# =================================================================================================
class TestProfile:
    def test_an_empty_window_answers_none_everywhere_and_never_zero(self, cc_monitor_a):
        result = coldchain.profile(cc_monitor_a, date_from=cc_day(-3), date_to=cc_day(-2))
        assert result["count"] == 0
        for key in ("first_at", "last_at", "min", "max", "mean", "in_range_minutes",
                    "out_minutes", "pct_in_range", "mkt"):
            assert result[key] is None, key

    def test_a_populated_window_reports_the_measured_spread(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["4", "12", "6", "5"])
        result = coldchain.profile(cc_monitor_a, date_from=cc_day(-1), date_to=cc_day())
        assert result["count"] == 4
        assert result["min"] == Decimal("4.00") and result["max"] == Decimal("12.00")
        assert result["mean"] == Decimal("6.75")
        assert result["in_range_minutes"] == 90 and result["out_minutes"] == 30
        assert result["pct_in_range"] == Decimal("75.00")
        assert result["frozen"] is False

    def test_a_monitor_with_no_band_keeps_its_count_and_has_no_percentage(
            self, cc_monitor_unlimited_a):
        cc_series(cc_monitor_unlimited_a, ["5", "40"])
        result = coldchain.profile(cc_monitor_unlimited_a, date_from=cc_day(-1), date_to=cc_day())
        assert result["count"] == 2
        assert result["pct_in_range"] is None
        assert result["limit_min"] is None and result["limit_max"] is None

    def test_the_window_cap_is_applied_and_REPORTED(self, cc_monitor_a):
        result = coldchain.profile(cc_monitor_a, date_from=cc_day(-400), date_to=cc_day())
        assert result["window_capped"] is True
        assert result["date_from"] > cc_day(-400)

    def test_a_reversed_window_is_swapped_rather_than_rendered_as_nothing(self, cc_monitor_a):
        cc_series(cc_monitor_a, ["5"])
        result = coldchain.profile(cc_monitor_a, date_from=cc_day(), date_to=cc_day(-1))
        assert result["date_from"] < result["date_to"]
        assert result["count"] == 1

    def test_the_row_walk_cap_is_reported_too(self, cc_monitor_a, monkeypatch):
        monkeypatch.setattr(coldchain, "MAX_EPISODE_READINGS", 2)
        cc_series(cc_monitor_a, ["5", "6", "7", "8"])
        result = coldchain.profile(cc_monitor_a, date_from=cc_day(-1), date_to=cc_day())
        assert result["truncated"] is True

    def test_it_costs_two_queries_regardless_of_how_many_rows_it_reads(
            self, cc_monitor_a, django_assert_max_num_queries):
        cc_series(cc_monitor_a, ["4", "5", "6", "7", "8", "9", "10", "11"])
        with django_assert_max_num_queries(2):
            coldchain.profile(cc_monitor_a, date_from=cc_day(-1), date_to=cc_day())

    def test_it_never_reads_another_workspaces_rows(self, cc_monitor_a, cc_monitor_b):
        cc_series(cc_monitor_b, ["40", "41"])
        assert coldchain.profile(cc_monitor_a, date_from=cc_day(-1),
                                 date_to=cc_day())["count"] == 0


# =================================================================================================
# 4.15 · raise_work_order — the ONE cross-sub-module write
# =================================================================================================
class TestRaiseWorkOrder:
    def test_it_creates_one_4_13_job_against_the_failing_unit(self, cc_monitor_asset_a, asset_a):
        from apps.scm.models import MaintenanceWorkOrder
        episode = cc_make_excursion(cc_monitor_asset_a, severity="critical")
        job = coldchain.raise_work_order(episode)
        assert isinstance(job, MaintenanceWorkOrder)
        assert job.asset_id == asset_a.pk
        assert job.tenant_id == cc_monitor_asset_a.tenant_id
        assert job.work_type == "corrective"
        assert job.number.startswith("MWO-")
        episode.refresh_from_db()
        assert episode.maintenance_work_order_id == job.pk

    def test_the_source_it_stamps_is_an_EXISTING_4_13_vocabulary_value(self, cc_monitor_asset_a):
        from apps.scm.models import MaintenanceWorkOrder
        job = coldchain.raise_work_order(cc_make_excursion(cc_monitor_asset_a))
        assert job.source == coldchain.WORK_ORDER_SOURCE
        assert job.source in dict(MaintenanceWorkOrder.SOURCE_CHOICES)

    @pytest.mark.parametrize("severity,priority", [("critical", "urgent"), ("major", "high"),
                                                   ("minor", "medium")])
    def test_the_severity_maps_onto_a_4_13_priority(self, cc_monitor_asset_a, severity, priority):
        job = coldchain.raise_work_order(cc_make_excursion(cc_monitor_asset_a, severity=severity))
        assert job.priority == priority

    def test_it_is_IDEMPOTENT_and_a_double_press_returns_the_SAME_job(self, cc_monitor_asset_a):
        from apps.scm.models import MaintenanceWorkOrder
        episode = cc_make_excursion(cc_monitor_asset_a)
        first = coldchain.raise_work_order(episode)
        second = coldchain.raise_work_order(episode)
        assert first.pk == second.pk
        assert MaintenanceWorkOrder.objects.filter(tenant=cc_monitor_asset_a.tenant).count() == 1

    def test_a_cold_room_monitor_raises_NOTHING_rather_than_500_ing_on_a_null_asset(
            self, cc_monitor_a):
        from apps.scm.models import MaintenanceWorkOrder
        episode = cc_make_excursion(cc_monitor_a)
        assert coldchain.raise_work_order(episode) is None
        assert MaintenanceWorkOrder.objects.count() == 0

    def test_a_shipment_monitor_raises_nothing_either(self, cc_monitor_frozen_a):
        assert coldchain.raise_work_order(cc_make_excursion(cc_monitor_frozen_a)) is None

    def test_the_job_description_quotes_the_episode_and_its_snapshotted_band(self,
                                                                            cc_monitor_asset_a):
        episode = cc_make_excursion(cc_monitor_asset_a)
        job = coldchain.raise_work_order(episode)
        assert episode.number in job.description
        assert cc_monitor_asset_a.number in job.description
        assert "limits" in job.description

    def test_a_one_sided_band_reads_as_one_sentence_in_the_job(self, cc_monitor_asset_a):
        episode = cc_make_excursion(cc_monitor_asset_a, limit_min=None,
                                    limit_max=Decimal("-15.00"))
        job = coldchain.raise_work_order(episode)
        assert "an upper limit of -15.00" in job.description
        assert "None" not in job.description

    def test_the_limit_label_helper_never_prints_a_null_side(self):
        assert coldchain._limit_label(None, None) == ""
        assert coldchain._limit_label(Decimal("2"), None) == "a lower limit of 2 °C"
        assert coldchain._limit_label(None, Decimal("8")) == "an upper limit of 8 °C"
        assert coldchain._limit_label(Decimal("2"), Decimal("8")) == "limits 2 to 8 °C"

    def test_it_writes_its_own_audit_row(self, cc_monitor_asset_a, admin_user):
        from apps.core.models import AuditLog
        episode = cc_make_excursion(cc_monitor_asset_a)
        before = AuditLog.objects.count()
        coldchain.raise_work_order(episode, user=admin_user)
        assert AuditLog.objects.count() > before
        entry = AuditLog.objects.order_by("-id").first()
        assert entry.changes["action"] == "raise_work_order"

    def test_it_never_touches_the_asset_or_any_4_13_vocabulary(self, cc_monitor_asset_a, asset_a):
        before = (asset_a.status, asset_a.asset_type)
        coldchain.raise_work_order(cc_make_excursion(cc_monitor_asset_a))
        asset_a.refresh_from_db()
        assert (asset_a.status, asset_a.asset_type) == before

"""Compute-layer tests for SCM 4.11 Supply Chain Analytics (``apps/scm/analytics.py``).

The five report pages, the CSV exports, every ``KpiSnapshot`` and every ``SupplyChainAlert`` are four
renderings of ONE computation — :func:`apps.scm.analytics.compute_metric`. So the arithmetic is
tested here, once, and ``test_views.py`` tests that the pages render what this module returned.

Covers:
- The window helpers (``range_bounds`` / ``period_count`` / ``period_windows`` / ``clamp_date``),
  including the date-overflow guards at the edge of ``datetime.date``.
- ``band_for`` in both directions, and its refusal to band on ``target_value`` alone.
- The ``compute_metric`` entry point: a closed registry, a backwards window, an illegal scope, a
  deleted scope subject, and the JSON-safety contract every breakdown owes ``KpiSnapshot``.
- The two writers: ``capture_snapshots`` (idempotent — a re-run UPDATES) and ``detect_alerts``
  (de-duped by ``dedupe_key``; a RESOLVED alert never blocks the next genuine breach).
- ``supplier_delivery_stats`` / ``supplier_quality_stats`` parity with 4.2's
  ``SupplierScorecard.recompute_from_signals`` — the parity test those two functions' docstrings
  explicitly say is owed, because they duplicate that arithmetic rather than refactor it.

Classes marked REGRESSION LOCK pin a defect this sub-module has already produced. Each fails against
the pre-fix behaviour — that is the whole point of writing them.
"""
import datetime
import json
from decimal import Decimal

import pytest
from django.utils import timezone

pytestmark = pytest.mark.django_db


def _target_stub(direction="higher_is_better", warning=None, critical=None):
    """A duck-typed stand-in for a KpiTarget — ``band_for`` reads four attributes and nothing else."""
    class _Stub:
        pass

    stub = _Stub()
    stub.direction = direction
    stub.warning_threshold = warning
    stub.critical_threshold = critical
    stub.target_value = None
    return stub


# ================================================================ Windows
class TestWindowHelpers:
    def test_range_bounds_last_7_is_seven_inclusive_days(self):
        from apps.scm.analytics import range_bounds, window_days
        today = datetime.date(2026, 3, 15)
        start, end = range_bounds("last_7", today=today)
        assert (start, end) == (datetime.date(2026, 3, 9), today)
        assert window_days(start, end) == 7

    def test_range_bounds_last_30_and_90_are_inclusive_too(self):
        from apps.scm.analytics import range_bounds, window_days
        today = datetime.date(2026, 3, 15)
        assert window_days(*range_bounds("last_30", today=today)) == 30
        assert window_days(*range_bounds("last_90", today=today)) == 90

    def test_range_bounds_quarter_starts_on_the_quarter(self):
        from apps.scm.analytics import range_bounds
        start, end = range_bounds("quarter", today=datetime.date(2026, 5, 20))
        assert start == datetime.date(2026, 4, 1)
        assert end == datetime.date(2026, 5, 20)

    def test_range_bounds_year_starts_in_january(self):
        from apps.scm.analytics import range_bounds
        start, _ = range_bounds("year", today=datetime.date(2026, 5, 20))
        assert start == datetime.date(2026, 1, 1)

    def test_range_bounds_all_has_no_lower_bound(self):
        from apps.scm.analytics import range_bounds, window_days
        start, end = range_bounds("all", today=datetime.date(2026, 5, 20))
        assert start is None and end == datetime.date(2026, 5, 20)
        # "No lower bound" is not a length — the resolvers ask the ledger for one instead.
        assert window_days(start, end) is None

    def test_range_bounds_defaults_to_todays_localdate(self):
        """L16: the reference date comes from the tz-aware basis every resolver reads."""
        from apps.scm.analytics import range_bounds
        _, end = range_bounds("last_30")
        assert end == timezone.localdate()

    def test_window_days_rejects_a_backwards_window(self):
        from apps.scm.analytics import window_days
        assert window_days(datetime.date(2026, 3, 10), datetime.date(2026, 3, 1)) is None

    def test_period_count_is_arithmetic_not_a_walk(self):
        from apps.scm.analytics import period_count
        assert period_count("month", datetime.date(2026, 1, 1), datetime.date(2026, 3, 31)) == 3
        assert period_count("day", datetime.date(2026, 1, 1), datetime.date(2026, 1, 7)) == 7

    def test_period_count_of_an_absurd_span_costs_nothing(self):
        """L40: counting buckets must never build them — this span is 3.6 million days."""
        from apps.scm.analytics import period_count
        assert period_count("day", datetime.date(1900, 1, 1), datetime.date(9998, 12, 31)) > 2_900_000

    def test_period_windows_are_oldest_first_and_bucket_shaped(self):
        from apps.scm.analytics import period_windows
        windows = period_windows("month", 3, end=datetime.date(2026, 3, 15))
        assert windows == [(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31)),
                           (datetime.date(2026, 2, 1), datetime.date(2026, 2, 28)),
                           (datetime.date(2026, 3, 1), datetime.date(2026, 3, 31))]

    def test_period_windows_clamps_the_count_before_building_anything(self):
        from apps.scm.analytics import MAX_TREND_PERIODS, period_windows
        assert len(period_windows("day", 10_000)) == MAX_TREND_PERIODS
        assert len(period_windows("month", 0)) == 1
        assert len(period_windows("month", "not a number")) == 1

    def test_period_windows_survives_the_end_of_the_calendar(self):
        """`next_bucket(9999-12-31, ...)` leaves the calendar — clamp_date is why this is not a 500."""
        from apps.scm.analytics import MAX_PERIOD_DATE, period_windows
        for grain in ("day", "week", "month", "quarter"):
            windows = period_windows(grain, 2, end=datetime.date(9999, 12, 31))
            assert windows[-1][1] <= datetime.date(9999, 12, 31), grain
            assert windows[-1][0] <= MAX_PERIOD_DATE, grain

    def test_period_windows_labelled_carries_the_charts_x_axis(self):
        from apps.scm.analytics import period_windows_labelled
        rows = period_windows_labelled("month", 2, end=datetime.date(2026, 3, 15))
        assert len(rows) == 2 and all(row[2] for row in rows)

    def test_clamp_date_bounds_both_ends_and_passes_none_through(self):
        from apps.scm.analytics import MAX_PERIOD_DATE, MIN_PERIOD_DATE, clamp_date
        assert clamp_date(datetime.date(1000, 1, 1)) == MIN_PERIOD_DATE
        assert clamp_date(datetime.date(9999, 12, 31)) == MAX_PERIOD_DATE
        assert clamp_date(None) is None
        assert clamp_date(datetime.date(2026, 3, 1)) == datetime.date(2026, 3, 1)


# ================================================================ Banding
class TestBandFor:
    def test_no_target_or_no_value_is_unknown(self):
        from apps.scm.analytics import band_for
        assert band_for(None, Decimal("5")) == "unknown"
        assert band_for(_target_stub(warning=Decimal("5")), None) == "unknown"

    def test_a_target_with_no_threshold_bands_nothing(self):
        """``target_value`` alone does NOT band — the same conjunction ``clean()`` refuses."""
        from apps.scm.analytics import band_for
        assert band_for(_target_stub(), Decimal("1")) == "unknown"

    def test_higher_is_better_crosses_downwards(self):
        from apps.scm.analytics import band_for
        target = _target_stub("higher_is_better", warning=Decimal("95"), critical=Decimal("90"))
        assert band_for(target, Decimal("99")) == "ok"
        assert band_for(target, Decimal("95")) == "warning"      # at the threshold has crossed it
        assert band_for(target, Decimal("92")) == "warning"
        assert band_for(target, Decimal("90")) == "critical"
        assert band_for(target, Decimal("10")) == "critical"

    def test_lower_is_better_crosses_upwards(self):
        from apps.scm.analytics import band_for
        target = _target_stub("lower_is_better", warning=Decimal("10"), critical=Decimal("20"))
        assert band_for(target, Decimal("5")) == "ok"
        assert band_for(target, Decimal("10")) == "warning"
        assert band_for(target, Decimal("25")) == "critical"

    def test_one_threshold_alone_still_bands(self):
        from apps.scm.analytics import band_for
        assert band_for(_target_stub("lower_is_better", critical=Decimal("20")),
                        Decimal("30")) == "critical"
        assert band_for(_target_stub("lower_is_better", critical=Decimal("20")),
                        Decimal("5")) == "ok"

    def test_a_junk_value_is_unknown_rather_than_an_exception(self):
        from apps.scm.analytics import band_for
        assert band_for(_target_stub("lower_is_better", warning=Decimal("10")), "abc") == "unknown"

    def test_a_stored_target_bands_through_the_same_function(self, kpi_target_a):
        from apps.scm.analytics import band_for
        # inv_turnover is higher_is_better: 6 >= 4 (warning) >= 2 (critical).
        assert band_for(kpi_target_a, Decimal("7")) == "ok"
        assert band_for(kpi_target_a, Decimal("3.5")) == "warning"
        assert band_for(kpi_target_a, Decimal("1")) == "critical"


# ================================================================ compute_metric — the entry point
class TestComputeMetric:
    def test_an_unknown_metric_raises_rather_than_rendering_an_empty_tile(self, tenant_a):
        from apps.scm.analytics import compute_metric
        with pytest.raises(ValueError):
            compute_metric(tenant_a, "not_a_metric", None, timezone.localdate())

    def test_a_backwards_window_is_unavailable_not_a_wrong_number(self, tenant_a):
        from apps.scm.analytics import compute_metric
        today = timezone.localdate()
        result = compute_metric(tenant_a, "inv_turnover", today, today - datetime.timedelta(days=5))
        assert result["value"] is None
        assert "ends before it starts" in result["breakdown"]["unavailable"]

    def test_an_illegal_scope_is_refused_not_silently_widened(self, tenant_a, carrier_a):
        """A carrier scope on a stock metric is an empty conjunction (L39) — never the network figure."""
        from apps.scm.analytics import compute_metric
        result = compute_metric(tenant_a, "inv_turnover", None, timezone.localdate(),
                                scope=("carrier", carrier_a))
        assert result["value"] is None
        assert "cannot be narrowed" in result["breakdown"]["unavailable"]

    def test_a_scope_whose_subject_was_deleted_is_refused(self, tenant_a):
        """SET_NULL leaves scope='vendor' pointing at nothing; widening would be a different number."""
        from apps.scm.analytics import compute_metric
        result = compute_metric(tenant_a, "spend_total", None, timezone.localdate(),
                                scope=("vendor", None))
        assert result["value"] is None
        assert "deleted" in result["breakdown"]["unavailable"]

    def test_the_result_is_enriched_with_the_metrics_identity(self, tenant_a, kpi_target_a):
        from apps.scm.analytics import compute_metric
        result = compute_metric(tenant_a, "inv_turnover", None, timezone.localdate(),
                                target=kpi_target_a)
        for key in ("metric", "label", "group", "unit", "kind", "direction", "scope", "scope_label",
                    "period_start", "period_end", "parameter_days", "parameter_pct", "band"):
            assert key in result, key
        assert result["metric"] == "inv_turnover"
        assert result["group"] == "inventory"

    def test_an_end_date_past_the_calendar_is_clamped_not_a_500(self, tenant_a, analytics_history_a):
        """`_moment(9999-12-31, end_of_day=True)` adds a day and overflows — every windowed metric
        would inherit that crash without the clamp at this one entry point."""
        from apps.scm.analytics import MAX_PERIOD_DATE, compute_metric
        result = compute_metric(tenant_a, "inv_turnover", datetime.date(2026, 1, 1),
                                datetime.date(9999, 12, 31))
        assert result["period_end"] == MAX_PERIOD_DATE.isoformat()

    def test_a_target_supplies_the_metrics_own_knobs(self, tenant_a):
        from apps.scm.analytics import compute_metric
        from apps.scm.models import KpiTarget
        target = KpiTarget.objects.create(
            tenant=tenant_a, metric="inv_dead_stock_value", name="Dead stock", scope="all",
            parameter_days=30, target_value=Decimal("100.00"))
        result = compute_metric(tenant_a, "inv_dead_stock_value", None, timezone.localdate(),
                                target=target)
        assert result["parameter_days"] == 30

    def test_the_module_default_applies_when_no_target_exists(self, tenant_a):
        """A page is browsable on a fresh tenant, so every N/% metric carries a documented default."""
        from apps.scm.analytics import DEAD_STOCK_DAYS, compute_metric
        result = compute_metric(tenant_a, "inv_dead_stock_value", None, timezone.localdate())
        assert result["parameter_days"] == DEAD_STOCK_DAYS

    def test_every_catalogued_metric_computes_on_a_seeded_tenant(self, tenant_a,
                                                                 analytics_history_a):
        from apps.scm.analytics import SCM_METRICS, compute_metric, range_bounds
        start, end = range_bounds("last_90")
        for key in SCM_METRICS:
            result = compute_metric(tenant_a, key, start, end)
            assert "value" in result and "display" in result, key
            # A metric that could not be computed must SAY so rather than return a bare None.
            if result["value"] is None:
                assert result["breakdown"].get("unavailable"), key

    def test_every_catalogued_metric_computes_on_an_EMPTY_tenant(self, tenant_b):
        """The first-run path: a workspace created by the onboarding wizard, clicking the sidebar."""
        from apps.scm.analytics import SCM_METRICS, compute_metric, range_bounds
        start, end = range_bounds("last_90")
        for key in SCM_METRICS:
            result = compute_metric(tenant_b, key, start, end)
            assert result["display"], key

    def test_every_breakdown_is_json_serializable(self, tenant_a, analytics_history_a):
        """``KpiSnapshot.breakdown`` is a JSONField that stores the payload VERBATIM — a stray
        Decimal or date in there is a TypeError at capture time, on one metric, months later."""
        from apps.scm.analytics import SCM_METRICS, _snapshot_payload, compute_metric, range_bounds
        start, end = range_bounds("last_90")
        for key in SCM_METRICS:
            result = compute_metric(tenant_a, key, start, end)
            json.dumps(_snapshot_payload(result))       # raises TypeError if anything is not JSON

    def test_metrics_for_group_covers_the_five_pages(self):
        from apps.scm.analytics import SCM_METRICS, metrics_for_group
        counted = 0
        for group in ("inventory", "procurement", "logistics", "margin", "risk"):
            entries = metrics_for_group(group)
            assert entries, group
            counted += len(entries)
        assert counted == len(SCM_METRICS) == 36

    def test_the_registry_and_the_catalog_cannot_drift(self):
        from apps.scm.analytics import _RESOLVERS
        from apps.scm.models import METRIC_META
        assert set(_RESOLVERS) == set(METRIC_META)


# ================================================================ REGRESSION LOCK — the impact floor
class TestImpactOfAndTheAlertFatigueFloor:
    """``_impact_of`` returns None — NOT ZERO — for a metric with no money behind it.

    Collapsing "unmeasurable" into "zero" made ``impact < min_impact_value`` true forever, so ANY
    operator who set a floor on ``otd_pct`` / ``otif_pct`` / ``inv_turnover`` /
    ``supplier_disruption_score`` / ``projected_stockout_count`` silently stopped receiving that
    target's alerts. That is the never-fires conjunction ``KpiTarget.clean()`` rejects for a missing
    threshold, arrived at from the other direction.
    """

    def test_a_money_metric_is_its_own_impact(self, tenant_a, analytics_history_a):
        from apps.scm.analytics import _impact_of, compute_metric, range_bounds
        from apps.scm.models import METRIC_META
        start, end = range_bounds("last_90")
        result = compute_metric(tenant_a, "spend_total", start, end)
        assert _impact_of(result, METRIC_META["spend_total"]) == abs(Decimal(result["value"]))

    def test_a_non_money_metric_with_money_in_its_breakdown_uses_that(self, tenant_a,
                                                                     analytics_history_a):
        from apps.scm.analytics import _impact_of, compute_metric, range_bounds
        from apps.scm.models import METRIC_META
        start, end = range_bounds("last_90")
        result = compute_metric(tenant_a, "spend_off_contract_pct", start, end)
        expected = Decimal(str(result["breakdown"]["off_contract_spend"]))
        assert expected > 0
        assert _impact_of(result, METRIC_META["spend_off_contract_pct"]) == expected

    def test_a_metric_with_no_money_behind_it_returns_none_not_zero(self, tenant_a,
                                                                    analytics_history_a):
        from apps.scm.analytics import IMPACT_KEYS, _impact_of, compute_metric, range_bounds
        from apps.scm.models import METRIC_META
        start, end = range_bounds("last_90")
        result = compute_metric(tenant_a, "otd_pct", start, end)
        assert result["value"] is not None                      # the metric itself computed
        assert not any(key in result["breakdown"] for key in IMPACT_KEYS)
        assert _impact_of(result, METRIC_META["otd_pct"]) is None

    def test_booleans_in_the_breakdown_are_never_read_as_an_amount(self):
        """``isinstance(True, int)`` is True — ``truncated``/``mixed_currency`` are not money."""
        from apps.scm.analytics import _impact_of
        result = {"value": Decimal("5"), "breakdown": {"total": True, "revenue": False}}
        assert _impact_of(result, {"unit": "pct"}) is None

    def test_a_floor_does_NOT_mute_a_breach_it_cannot_measure(self, tenant_a, alerting_target_a,
                                                              late_shipment_a):
        """THE LOCK: an alerting otd_pct target with ``min_impact_value=1`` and a breaching value
        must still raise. ``otd_pct`` emits no money figure at all, so an unmeasurable impact has to
        fail OPEN."""
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        summary = detect_alerts(tenant_a)
        assert summary["targets"] == 1
        assert summary["breaches"] == 1
        assert summary["below_impact"] == 0, "an unmeasurable impact must not be suppressed"
        alert = SupplyChainAlert.objects.get(tenant=tenant_a, alert_type="kpi_breach")
        assert alert.kpi_target_id == alerting_target_a.pk
        assert alert.metric == "otd_pct"
        # The queue's ordering key is non-null, so an unmeasurable impact sorts to the bottom.
        assert alert.impact_value == Decimal("0.00")
        assert alert.severity == "critical"                     # 0 % crossed the critical band

    def test_a_floor_DOES_suppress_a_breach_worth_less_than_it(self, tenant_a, analytics_history_a):
        """The floor still works where the money IS measurable — and the suppression is counted, so
        the POST action can say so out loud."""
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import KpiTarget, SupplyChainAlert
        KpiTarget.objects.create(
            tenant=tenant_a, metric="spend_off_contract_pct", name="Off-contract spend",
            scope="all", date_range="last_90", direction="lower_is_better",
            target_value=Decimal("5.00"), warning_threshold=Decimal("10.00"),
            critical_threshold=Decimal("20.00"), is_alerting=True,
            min_impact_value=Decimal("999999.00"))
        summary = detect_alerts(tenant_a)
        assert summary["below_impact"] == 1
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a,
                                                   alert_type="kpi_breach").exists()


# ================================================================ REGRESSION LOCK — the risk score
class TestSupplierDisruptionScoreShape:
    """``breakdown["components"]`` is ``dict[str, dict]`` in BOTH branches.

    It used to collapse to ``{key: explanation}`` on the nothing-could-be-scored early return, and
    the risk page's ``_risk_components`` calls ``entry.get("points")`` on each value — so a tenant
    with no supply-chain history at all got an AttributeError instead of the page's own empty state.
    That is the FIRST-RUN path: a fresh workspace clicking the sidebar's Predictive Analytics bullet.
    """

    COMPONENT_KEYS = ("late_delivery", "quality_rejects", "nonconformances", "open_capa",
                      "contract_cover", "concentration", "acknowledgement", "stored_risk_index")

    def _components(self, tenant, scope=None):
        from apps.scm.analytics import compute_metric, range_bounds
        start, end = range_bounds("last_90")
        result = compute_metric(tenant, "supplier_disruption_score", start, end, scope=scope)
        return result, result["breakdown"].get("components")

    def test_nothing_scorable_still_returns_dict_of_dicts(self, tenant_a):
        result, components = self._components(tenant_a)
        assert result["value"] is None
        assert result["breakdown"]["unavailable"]
        assert set(components) == set(self.COMPONENT_KEYS)
        for key, entry in components.items():
            assert isinstance(entry, dict), key
            # The exact three reads `_risk_components` makes on every entry.
            assert entry.get("points") is None
            assert entry.get("scored") is False
            assert entry["explanation"]
            assert entry["contribution"] is None
            assert "_raw" not in entry               # the private accumulator never escapes

    def test_the_scored_branch_has_the_same_shape(self, tenant_a, analytics_history_a):
        result, components = self._components(tenant_a)
        assert result["value"] is not None
        assert set(components) == set(self.COMPONENT_KEYS)
        for key, entry in components.items():
            assert isinstance(entry, dict), key
            assert "points" in entry and "weight" in entry and "scored" in entry
            assert "_raw" not in entry
        assert result["breakdown"]["components_scored"] >= 1
        assert result["breakdown"]["components_total"] == len(self.COMPONENT_KEYS)

    def test_a_vendor_scope_on_an_empty_tenant_keeps_the_shape(self, tenant_a, supplier_a):
        _result, components = self._components(tenant_a, scope=("vendor", supplier_a))
        assert all(isinstance(entry, dict) for entry in components.values())

    def test_the_composite_is_reweighted_over_the_components_that_had_a_signal(
            self, tenant_a, analytics_history_a):
        """The same rule ``SupplierScorecard.recompute_overall`` uses — a supplier with no risk
        assessment is scored on what is known, not given a phantom zero."""
        from decimal import Decimal as D
        result, components = self._components(tenant_a)
        scored = {key: entry for key, entry in components.items() if entry["scored"]}
        weight = sum(entry["weight"] for entry in scored.values())
        assert weight == result["breakdown"]["weight_applied"]
        expected = sum(D(str(entry["points"])) * entry["weight"] for entry in scored.values()) / weight
        assert abs(D(result["value"]) - expected) < D("0.01")

    def test_it_is_deterministic_run_twice(self, tenant_a, analytics_history_a):
        """The page promises 'run it twice on the same rows and it returns the same number'."""
        first, _ = self._components(tenant_a)
        second, _ = self._components(tenant_a)
        assert first["value"] == second["value"]


# ================================================================ REGRESSION LOCK — reassuring zero
class TestProjectedStockoutCount:
    """A rule with no demand rate is UNMEASURABLE, not safe.

    ``avg_daily_demand`` is ``editable=False`` and written only by 4.7's safety-stock calculation, so
    a tenant that has never run it would otherwise be shown a confident green "0 projected stockouts"
    computed from zero measurable rules.
    """

    def test_every_rule_without_a_demand_rate_returns_no_value(self, tenant_a, reorder_rule_a):
        from apps.scm.analytics import compute_metric, range_bounds
        start, end = range_bounds("last_90")
        assert reorder_rule_a.avg_daily_demand == Decimal("0")
        result = compute_metric(tenant_a, "projected_stockout_count", start, end)
        assert result["value"] is None, "a zero here reads as good news nobody computed"
        assert "demand rate" in result["breakdown"]["unavailable"]
        assert result["breakdown"]["rules_checked"] == 1
        assert result["breakdown"]["rules_without_demand_rate"] == 1

    def test_no_active_rule_at_all_is_also_unavailable(self, tenant_a):
        from apps.scm.analytics import compute_metric, range_bounds
        start, end = range_bounds("last_90")
        result = compute_metric(tenant_a, "projected_stockout_count", start, end)
        assert result["value"] is None
        assert "reorder rule" in result["breakdown"]["unavailable"]

    def test_one_measurable_rule_makes_the_count_real_again(self, tenant_a, reorder_rule_a,
                                                            analytics_history_a):
        """analytics_history_a adds a SECOND rule that DOES carry a rate — so the metric is a
        number, and the unmeasurable one is reported beside it rather than counted as safe."""
        from apps.scm.analytics import compute_metric, range_bounds
        start, end = range_bounds("last_90")
        result = compute_metric(tenant_a, "projected_stockout_count", start, end)
        assert result["value"] == Decimal("1")
        assert result["breakdown"]["rules_checked"] == 2
        assert result["breakdown"]["rules_without_demand_rate"] == 1
        assert result["rows"][0]["sku"] == "WIDGET-1"

    def test_a_rule_with_cover_longer_than_its_lead_time_is_not_at_risk(self, tenant_a, item_a,
                                                                        location_a):
        from apps.scm.analytics import compute_metric, range_bounds
        from apps.scm.models import ReorderRule
        from apps.scm.tests._helpers import seed_stock
        seed_stock(tenant_a, item_a, location_a, "500", "8.0000")
        rule = ReorderRule.objects.create(tenant=tenant_a, item=item_a, location=location_a,
                                          lead_time_days=5)
        rule.avg_daily_demand = Decimal("1.0000")
        rule.save(update_fields=["avg_daily_demand"])
        result = compute_metric(tenant_a, "projected_stockout_count", *range_bounds("last_90"))
        assert result["value"] == Decimal("0")           # a MEASURED zero, which is a fact
        assert result["breakdown"]["rules_without_demand_rate"] == 0


# ================================================================ capture_snapshots
class TestCaptureSnapshots:
    def test_it_freezes_one_point_per_active_target(self, tenant_a, kpi_target_a,
                                                    analytics_history_a, admin_user):
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        summary = capture_snapshots(tenant_a, user=admin_user)
        assert summary["targets"] == 1 and summary["created"] == 1
        snapshot = KpiSnapshot.objects.get(tenant=tenant_a)
        assert snapshot.kpi_target_id == kpi_target_a.pk
        assert snapshot.metric == "inv_turnover"
        assert snapshot.computed_by_id == admin_user.pk
        assert snapshot.dimension_key == ""              # the roll-up row is "", never NULL
        assert snapshot.target_value_at_time == kpi_target_a.target_value

    def test_the_period_is_the_targets_GRAIN_bucket_not_its_rolling_range(self, tenant_a,
                                                                         kpi_target_a,
                                                                         analytics_history_a):
        """A rolling window overlaps its neighbour, and a trend line of overlapping windows is
        meaningless — so a monthly target snapshots 1-31 January, not "the last 90 days"."""
        from apps.scm.analytics import capture_snapshots, period_windows
        from apps.scm.models import KpiSnapshot
        end = timezone.localdate()
        capture_snapshots(tenant_a, period_end=end)
        expected_start, expected_end = period_windows("month", 1, end=end)[0]
        snapshot = KpiSnapshot.objects.get(tenant=tenant_a)
        assert (snapshot.period_start, snapshot.period_end) == (expected_start, expected_end)

    def test_running_it_twice_UPDATES_rather_than_stacking_a_second_row(self, tenant_a,
                                                                       kpi_target_a,
                                                                       analytics_history_a):
        """THE LOCK: the capture button is safe to press twice."""
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        first = capture_snapshots(tenant_a)
        before = KpiSnapshot.objects.filter(tenant=tenant_a).count()
        # Back-dated with a direct UPDATE rather than read straight off the first capture. Windows'
        # system clock ticks every ~15.6 ms and two back-to-back `timezone.now()` calls inside that
        # tick return the IDENTICAL microsecond, so `second > first` compared two equal values and
        # failed — every time this test ran on its own, and intermittently inside the full suite.
        # The contract under test is "a re-run RE-STAMPS freshness", and forcing a known-old stamp
        # is what measures that instead of measuring the clock.
        stamped = timezone.now() - datetime.timedelta(hours=1)
        KpiSnapshot.objects.filter(tenant=tenant_a).update(computed_at=stamped)

        second = capture_snapshots(tenant_a)
        assert KpiSnapshot.objects.filter(tenant=tenant_a).count() == before == 1
        assert (first["created"], first["updated"]) == (1, 0)
        assert (second["created"], second["updated"]) == (0, 1)
        # computed_at is default=timezone.now, NOT auto_now_add, precisely so a re-run re-stamps
        # freshness instead of freezing the first run's time and lying about it ever after.
        assert KpiSnapshot.objects.get(tenant=tenant_a).computed_at > stamped

    def test_the_re_run_updates_the_value_it_measured(self, tenant_a, kpi_target_a,
                                                      analytics_history_a, item_a, location_a):
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        from apps.scm.views._helpers import _post_stock_move
        capture_snapshots(tenant_a)
        first = KpiSnapshot.objects.get(tenant=tenant_a).value
        _post_stock_move(tenant_a, item=item_a, location=location_a, quantity=Decimal("-20"),
                         move_type="issue", unit_cost=Decimal("8.0000"), reference="SO-00009")
        capture_snapshots(tenant_a)
        assert KpiSnapshot.objects.get(tenant=tenant_a).value != first

    def test_an_inactive_target_is_not_captured(self, tenant_a, kpi_target_a, analytics_history_a):
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        kpi_target_a.is_active = False
        kpi_target_a.save(update_fields=["is_active"])
        summary = capture_snapshots(tenant_a)
        assert summary["targets"] == 0
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()

    def test_a_metric_with_no_value_is_a_GAP_never_a_stored_zero(self, tenant_a):
        """``KpiSnapshot.value`` is non-null and a not-computable figure stored as 0 renders as good
        news — so it is skipped, counted, and the reason is reported."""
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot, KpiTarget
        KpiTarget.objects.create(tenant=tenant_a, metric="projected_stockout_count",
                                 name="Stockouts", scope="all")
        summary = capture_snapshots(tenant_a)
        assert summary["skipped"] == 1 and summary["created"] == 0
        assert not KpiSnapshot.objects.filter(tenant=tenant_a).exists()
        assert "reorder rule" in summary["details"][0]["skipped"]

    def test_it_stamps_last_evaluated_at_on_the_target(self, tenant_a, kpi_target_a,
                                                       analytics_history_a):
        from apps.scm.analytics import capture_snapshots
        assert kpi_target_a.last_evaluated_at is None
        capture_snapshots(tenant_a)
        kpi_target_a.refresh_from_db()
        assert kpi_target_a.last_evaluated_at is not None

    def test_a_caller_supplied_target_from_another_tenant_is_dropped(self, tenant_a, kpi_target_b,
                                                                     analytics_history_a):
        """L40 §3 — two records joined by an action must agree on more than being passed together."""
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        summary = capture_snapshots(tenant_a, targets=[kpi_target_b])
        assert summary["targets"] == 0 and summary["available"] == 0
        assert not KpiSnapshot.objects.filter(kpi_target=kpi_target_b).exists()

    def test_no_tenant_writes_nothing(self, tenant_a, kpi_target_a):
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        summary = capture_snapshots(None)
        assert summary["targets"] == 0
        assert not KpiSnapshot.objects.exists()

    def test_the_frozen_breakdown_carries_the_display_and_the_scope_label(self, tenant_a,
                                                                          kpi_target_a,
                                                                          analytics_history_a):
        """The payload is re-rendered months later WITHOUT recomputing, so it has to carry its own
        labels — by then the supplier may have been renamed and the parameters retuned."""
        from apps.scm.analytics import capture_snapshots
        from apps.scm.models import KpiSnapshot
        capture_snapshots(tenant_a)
        breakdown = KpiSnapshot.objects.get(tenant=tenant_a).breakdown
        for key in ("display", "label", "unit", "scope", "scope_label", "period_start",
                    "period_end", "rows"):
            assert key in breakdown, key


# ================================================================ detect_alerts
class TestDetectAlerts:
    def test_a_repeat_breach_UPDATES_the_open_row_rather_than_raising_a_second(
            self, tenant_a, alerting_target_a, late_shipment_a):
        """THE LOCK: de-dupe is this function, not a database constraint (MariaDB has no partial
        indexes, so a conditional unique would silently protect nothing in production)."""
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        first = detect_alerts(tenant_a)
        alert = SupplyChainAlert.objects.get(tenant=tenant_a, alert_type="kpi_breach")
        raised_at, last_seen = alert.raised_at, alert.last_seen_at

        second = detect_alerts(tenant_a)
        assert SupplyChainAlert.objects.filter(tenant=tenant_a,
                                               alert_type="kpi_breach").count() == 1
        assert first["created"] == 1 and second["created"] == 0
        assert second["updated"] >= 1
        alert.refresh_from_db()
        assert alert.raised_at == raised_at              # "raised" is when it FIRST fired
        assert alert.last_seen_at > last_seen            # "still breaching" moves this instead

    def test_a_RESOLVED_alert_does_not_block_the_next_genuine_breach(self, tenant_a, admin_user,
                                                                     alerting_target_a,
                                                                     late_shipment_a):
        """A resolved row is deliberately NOT matched — a problem that comes back raises a fresh row,
        which a ``unique_together`` on the dedupe columns would have made impossible forever."""
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        detect_alerts(tenant_a)
        alert = SupplyChainAlert.objects.get(tenant=tenant_a, alert_type="kpi_breach")
        alert.resolve(admin_user, note="Chased the carrier.")

        detect_alerts(tenant_a)
        rows = SupplyChainAlert.objects.filter(tenant=tenant_a, alert_type="kpi_breach")
        assert rows.count() == 2
        assert sorted(row.status for row in rows) == ["open", "resolved"]

    def test_an_acknowledged_alert_is_still_re_fired_not_duplicated(self, tenant_a, admin_user,
                                                                    alerting_target_a,
                                                                    late_shipment_a):
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        detect_alerts(tenant_a)
        alert = SupplyChainAlert.objects.get(tenant=tenant_a, alert_type="kpi_breach")
        alert.acknowledge(admin_user)
        detect_alerts(tenant_a)
        assert SupplyChainAlert.objects.filter(tenant=tenant_a,
                                               alert_type="kpi_breach").count() == 1
        alert.refresh_from_db()
        assert alert.status == "acknowledged"            # a re-fire never reopens somebody's triage

    def test_a_target_that_is_not_breaching_raises_nothing(self, tenant_a, analytics_history_a):
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import KpiTarget, SupplyChainAlert
        KpiTarget.objects.create(
            tenant=tenant_a, metric="otd_pct", name="Generous OTD", scope="all",
            date_range="last_90", target_value=Decimal("10.00"),
            warning_threshold=Decimal("5.00"), critical_threshold=Decimal("1.00"),
            is_alerting=True)
        summary = detect_alerts(tenant_a)
        assert summary["targets"] == 1 and summary["breaches"] == 0
        assert not SupplyChainAlert.objects.filter(tenant=tenant_a,
                                                   alert_type="kpi_breach").exists()

    def test_a_target_with_alerting_off_is_never_evaluated(self, tenant_a, kpi_target_a,
                                                           analytics_history_a):
        from apps.scm.analytics import detect_alerts
        assert detect_alerts(tenant_a)["targets"] == 0

    def test_the_alert_quotes_the_same_number_the_tile_shows(self, tenant_a, alerting_target_a,
                                                             analytics_history_a, late_shipment_a):
        from apps.scm.analytics import compute_metric, detect_alerts, range_bounds
        from apps.scm.models import SupplyChainAlert
        detect_alerts(tenant_a)
        alert = SupplyChainAlert.objects.get(tenant=tenant_a, alert_type="kpi_breach")
        live = compute_metric(tenant_a, "otd_pct", *range_bounds("last_90"),
                              target=alerting_target_a)
        assert alert.observed_value == pytest.approx(Decimal(live["value"]), rel=Decimal("0.0001"))
        assert alert.detail["display"] == live["display"]
        assert alert.detail["band"] == live["band"]

    def test_the_rule_based_detectors_run_on_a_thin_tenant_without_raising(self, tenant_b):
        from apps.scm.analytics import detect_alerts
        summary = detect_alerts(tenant_b)
        assert summary["created"] == 0 and summary["exceptions"] == 0

    def test_the_rule_based_detectors_raise_typed_exceptions_on_a_seeded_tenant(
            self, tenant_a, analytics_history_a):
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        summary = detect_alerts(tenant_a)
        assert summary["exceptions"] >= 1
        raised = SupplyChainAlert.objects.filter(tenant=tenant_a)
        assert raised.exists()
        for alert in raised:
            assert alert.number.startswith("ALR-")       # save(), not bulk_create — L: quotable
            assert alert.dedupe_key
            assert alert.tenant_id == tenant_a.pk

    def test_no_tenant_writes_nothing(self):
        from apps.scm.analytics import detect_alerts
        from apps.scm.models import SupplyChainAlert
        assert detect_alerts(None)["created"] == 0
        assert not SupplyChainAlert.objects.exists()

    def test_detection_never_writes_a_stock_move_or_a_journal_entry(self, tenant_a,
                                                                    analytics_history_a,
                                                                    alerting_target_a):
        """4.11 is READ-ONLY over 4.1-4.10, and apps.accounting owns the ledger (L29)."""
        from apps.accounting.models import JournalEntry
        from apps.scm.analytics import capture_snapshots, detect_alerts
        from apps.scm.models import StockMove
        moves = StockMove.objects.filter(tenant=tenant_a).count()
        entries = JournalEntry.objects.filter(tenant=tenant_a).count()
        detect_alerts(tenant_a)
        capture_snapshots(tenant_a)
        assert StockMove.objects.filter(tenant=tenant_a).count() == moves
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == entries


# ================================================================ 4.2 parity (the owed test)
class TestSupplierStatsParityWithTheScorecard:
    """``supplier_delivery_stats`` / ``supplier_quality_stats`` vs 4.2's
    ``SupplierScorecard.recompute_from_signals``.

    The two deliberately duplicate that arithmetic rather than refactor a shipped, load-bearing
    method during an unrelated build — and both docstrings say a parity test is OWED. This is it. If
    they ever diverge, 4.11's copy is the one to change, because 4.2's is the one with users.
    """

    def _scorecard(self, tenant, party, start, end):
        from apps.scm.models import SupplierScorecard
        card = SupplierScorecard.objects.create(tenant=tenant, party=party,
                                                period_start=start, period_end=end)
        card.recompute_from_signals()
        return card

    def test_delivery_pct_equals_the_scorecards_delivery_score(self, tenant_a, supplier_a,
                                                               analytics_history_a):
        from apps.scm.analytics import range_bounds, supplier_delivery_stats
        start, end = range_bounds("last_90")
        card = self._scorecard(tenant_a, supplier_a, start, end)
        stats = supplier_delivery_stats(tenant_a, supplier_a, start, end)
        assert card.delivery_score is not None
        assert stats["pct"].quantize(Decimal("0.01")) == card.delivery_score

    def test_delivery_parity_holds_for_a_LATE_supplier_too(self, tenant_a, vendor_a,
                                                           analytics_history_a):
        from apps.scm.analytics import range_bounds, supplier_delivery_stats
        start, end = range_bounds("last_90")
        card = self._scorecard(tenant_a, vendor_a, start, end)
        stats = supplier_delivery_stats(tenant_a, vendor_a, start, end)
        assert card.delivery_score == Decimal("0.00")
        assert stats["pct"].quantize(Decimal("0.01")) == card.delivery_score
        assert (stats["datable"], stats["on_time"], stats["late"]) == (1, 0, 1)

    def test_quality_pct_equals_the_scorecards_quality_score(self, tenant_a, vendor_a,
                                                             analytics_history_a):
        from apps.scm.analytics import range_bounds, supplier_quality_stats
        start, end = range_bounds("last_90")
        card = self._scorecard(tenant_a, vendor_a, start, end)
        stats = supplier_quality_stats(tenant_a, vendor_a, start, end)
        assert card.quality_score is not None
        assert stats["quality_pct"].quantize(Decimal("0.01")) == card.quality_score
        # 8 received + 2 rejected = 10 presented, so 20 % rejected and an 80 % quality score.
        assert stats["reject_pct"] == Decimal("20")

    def test_an_undated_order_is_excluded_from_BOTH(self, tenant_a, supplier_a, usd):
        """A receipt against an order with no promised date cannot be late — scoring it as on time
        is how an OTD number quietly becomes 100 %."""
        from apps.scm.analytics import range_bounds, supplier_delivery_stats
        from apps.scm.models import (GoodsReceiptLine, GoodsReceiptNote, PurchaseOrder,
                                     PurchaseOrderLine)
        today = timezone.localdate()
        order = PurchaseOrder.objects.create(tenant=tenant_a, vendor=supplier_a, currency=usd,
                                             order_date=today - datetime.timedelta(days=10),
                                             status="received")
        line = PurchaseOrderLine.objects.create(purchase_order=order, item_description="Paper",
                                                quantity=Decimal("1"), unit_price=Decimal("1.00"))
        grn = GoodsReceiptNote.objects.create(tenant=tenant_a, purchase_order=order,
                                              receipt_date=today, status="received")
        GoodsReceiptLine.objects.create(goods_receipt=grn, po_line=line,
                                        quantity_received=Decimal("1"))
        start, end = range_bounds("last_90")
        card = self._scorecard(tenant_a, supplier_a, start, end)
        stats = supplier_delivery_stats(tenant_a, supplier_a, start, end)
        assert stats["datable"] == 0 and stats["pct"] is None
        assert card.delivery_score is None               # neither invents a figure

    def test_the_network_wide_form_takes_no_party(self, tenant_a, analytics_history_a):
        from apps.scm.analytics import range_bounds, supplier_delivery_stats
        start, end = range_bounds("last_90")
        stats = supplier_delivery_stats(tenant_a, None, start, end)
        assert (stats["datable"], stats["on_time"]) == (2, 1)
        assert stats["pct"] == Decimal("50")

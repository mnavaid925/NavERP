"""Inventory 5.17 Reporting & Analytics — snapshot model + engine contracts.

The sub-module owns ONE table, ``InventoryReportSnapshot``, whose whole job is to
freeze what ``_engine.py`` computed: a per-tenant ``IRS-`` number minted in
``save()``, a foreign-workspace location refused in ``clean()``, a badge css map,
and a ``<Type> — <date>`` display fallback. The engine side is pure functions over
SCM 4.3's append-only ``StockMove`` ledger: window clamping that survives hostile
input, one-fetch indexing of STOCK items only, WAC/FIFO costing walks that exclude
transfer legs while the AGING physical view includes them, velocity verdicts that
never call a trading SKU dead, FIFO age buckets that always sum to true on-hand,
an ABC Pareto with a class-C floor for zero usage, and a freeze path whose JSON is
scalar-only by construction.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inventory.models import InventoryReportSnapshot
from apps.inventory.views.ReportingAnalytics._engine import (
    Ledger,
    abc_rows,
    aging_rows,
    build_summary,
    clamp_window,
    turnover_rows,
    valuation_rows,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ local helpers


def _post_move(tenant, item, location, *, quantity="4", unit_cost="1",
               move_type="receipt", days_ago=0):
    """One append-only StockMove leg, mirroring conftest._post_move's fields."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location,
        quantity=Decimal(quantity), unit_cost=Decimal(unit_cost),
        move_type=move_type, reference="", reason="",
        moved_at=timezone.now() - datetime.timedelta(days=days_ago))


def _costed_item(tenant, sku, *, costing_method="weighted_avg", average_cost="0"):
    """A stocked item master with an explicit cached average cost (WAC reads it)."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Report {sku}",
        standard_cost=Decimal("8.00"), costing_method=costing_method,
        average_cost=Decimal(average_cost))


def _row_for(rows, sku):
    matched = [row for row in rows if row["item"].sku == sku]
    assert matched, f"no report row for {sku}"
    return matched[0]


def _assert_scalars_only(value):
    """Recursively: every leaf is str/int/float/bool/None — never Decimal/date/model."""
    if isinstance(value, dict):
        for child in value.values():
            _assert_scalars_only(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_scalars_only(child)
    else:
        assert value is None or isinstance(value, (str, int, float, bool)), repr(value)


# ------------------------------------------------------------------ InventoryReportSnapshot


def test_snapshot_number_sequence_per_tenant(tenant_a, tenant_b):
    first = InventoryReportSnapshot.objects.create(tenant=tenant_a, report_type="valuation")
    second = InventoryReportSnapshot.objects.create(tenant=tenant_a, report_type="aging")
    foreign = InventoryReportSnapshot.objects.create(tenant=tenant_b, report_type="valuation")
    assert first.number == "IRS-00001"
    assert second.number == "IRS-00002"
    assert foreign.number == "IRS-00001"          # per-tenant sequence, not global
    assert str(first) == "IRS-00001 Inventory Valuation"


def test_snapshot_defaults_and_meta_ordering(tenant_a, admin_user):
    assert InventoryReportSnapshot._meta.ordering == ["-created_at"]
    snap = InventoryReportSnapshot.objects.create(
        tenant=tenant_a, report_type="turnover", window_days=90,
        location=None, generated_by=admin_user, notes="")
    assert snap.summary == {}                     # JSONField default=dict
    assert snap.notes == ""
    fresh = InventoryReportSnapshot(report_type="valuation")
    assert fresh.window_days is None              # nullable PositiveInteger
    assert fresh.generated_by_id is None


@pytest.mark.parametrize("code,expected", [
    ("valuation", "badge-info"),
    ("turnover", "badge-green"),
    ("aging", "badge-amber"),
    ("abc", "badge-slate"),
    ("nonsense", "badge-muted"),                  # defensive fallback off-map
])
def test_snapshot_type_css_mapping(code, expected):
    assert InventoryReportSnapshot(report_type=code).type_css == expected


def test_snapshot_display_title_fallback_and_override(tenant_a):
    blank = InventoryReportSnapshot.objects.create(tenant=tenant_a, report_type="abc")
    assert blank.display_title.startswith("ABC Analysis")
    assert "—" in blank.display_title
    captioned = InventoryReportSnapshot.objects.create(
        tenant=tenant_a, report_type="abc", title="Q3 month-end freeze")
    assert captioned.display_title == "Q3 month-end freeze"


def test_snapshot_clean_rejects_foreign_location(db, tenant_a, location_b):
    snap = InventoryReportSnapshot(tenant=tenant_a, report_type="valuation", location=location_b)
    with pytest.raises(ValidationError):
        snap.clean()


def test_snapshot_clean_allows_own_or_unset_location(tenant_a, location_a):
    scoped = InventoryReportSnapshot(tenant=tenant_a, report_type="valuation", location=location_a)
    unscoped = InventoryReportSnapshot(tenant=tenant_a, report_type="valuation")
    bare = InventoryReportSnapshot(report_type="valuation")
    scoped.clean()                                # own-workspace scope is legal
    unscoped.clean()                              # tenant without a location is legal
    bare.clean()                                  # neither *_id set — guard skipped


# ------------------------------------------------------------------ _engine: clamp_window


@pytest.mark.parametrize("raw,expected", [
    ("", 90),                                     # empty -> default
    ("   ", 90),                                  # whitespace-only -> default
    ("junk", 90),                                 # non-digit junk -> default
    ("-5", 90),                                   # sign makes it non-decimal
    ("30", 30),
    ("0", 1),                                     # clamped up into [1, 3650]
    ("99999", 3650),                              # clamped down into [1, 3650]
    ("9" * 500, 90),                              # digit bomb: default WITHOUT raising
])
def test_clamp_window(raw, expected):
    assert clamp_window(raw) == expected


# ------------------------------------------------------------------ _engine: Ledger


def test_ledger_indexes_stock_moves_only(tenant_a, item_a, location_a):
    from apps.scm.models import Item
    service = Item.objects.create(
        tenant=tenant_a, sku="SVC-1", name="Freight surcharge", item_type="service")
    _post_move(tenant_a, item_a, location_a, quantity="6", days_ago=3)
    _post_move(tenant_a, service, location_a, quantity="1", days_ago=2)
    ledger = Ledger(tenant_a)
    assert set(ledger.by_item) == {item_a.pk}     # the service leg never enters
    assert set(ledger.by_spot) == {(item_a.pk, location_a.pk)}
    assert len(ledger.moves) == 1
    assert set(ledger.items(tenant_a)) == {item_a.pk}


# ------------------------------------------------------------------ _engine: valuation math


def test_valuation_weighted_avg_uses_cached_average_cost(tenant_a, location_a):
    item = _costed_item(tenant_a, "RPT-WAC", average_cost="10.00")
    _post_move(tenant_a, item, location_a, quantity="5", unit_cost="3.00", days_ago=30)
    rows, totals = valuation_rows(tenant_a)
    row = _row_for(rows, "RPT-WAC")
    assert row["on_hand"] == Decimal("5.00")
    assert row["value"] == Decimal("50.00")       # on_hand x average_cost, NOT the 3.00 leg
    assert row["unit_value"] == Decimal("10.00")
    assert row["method"] == "Weighted Average"
    assert totals["total_value"] == Decimal("50.00") and totals["spots"] == 1


def test_valuation_fifo_partial_issue_consumes_oldest_layer(tenant_a, location_a):
    item = _costed_item(tenant_a, "RPT-FIFO", costing_method="fifo")
    _post_move(tenant_a, item, location_a, quantity="2", unit_cost="10.00", days_ago=100)
    _post_move(tenant_a, item, location_a, quantity="3", unit_cost="20.00", days_ago=50)
    _post_move(tenant_a, item, location_a, quantity="-3", unit_cost="15.00",
               move_type="issue", days_ago=10)
    rows, _totals = valuation_rows(tenant_a)
    row = _row_for(rows, "RPT-FIFO")
    assert row["on_hand"] == Decimal("2.00")
    assert row["value"] == Decimal("40.00")       # oldest layer gone; survivors price at 20


def test_transfer_legs_excluded_from_costing_but_count_in_aging(tenant_a, location_a):
    """Costing ignores transfers entirely (no fake layer); aging treats every inbound
    leg — transfers included — as a fresh arrival, so its buckets sum to true on-hand."""
    item = _costed_item(tenant_a, "RPT-TRF", costing_method="fifo")
    _post_move(tenant_a, item, location_a, quantity="2", unit_cost="10.00", days_ago=100)
    _post_move(tenant_a, item, location_a, quantity="4", unit_cost="3.00", days_ago=45)
    _post_move(tenant_a, item, location_a, quantity="5", unit_cost="99.00",
               move_type="transfer", days_ago=5)
    val_rows, _totals = valuation_rows(tenant_a)
    val_row = _row_for(val_rows, "RPT-TRF")
    assert val_row["on_hand"] == Decimal("11.00")
    assert val_row["value"] == Decimal("32.00")   # 2x10 + 4x3; the 99.00 layer must NOT exist
    age_rows, age_totals = aging_rows(tenant_a)
    age_row = _row_for(age_rows, "RPT-TRF")
    bucket_qty_sum = sum((b["qty"] for b in age_row["bucket_rows"]), Decimal("0"))
    assert bucket_qty_sum == age_row["on_hand"] == Decimal("11.00")
    assert age_totals["total_value"] == Decimal("527.00")   # physical view prices the arrival


# ------------------------------------------------------------------ _engine: turnover velocity


def test_turnover_sellthrough_with_no_endpoints_is_fast(tenant_a, location_a):
    item = _costed_item(tenant_a, "RPT-FAST")
    _post_move(tenant_a, item, location_a, quantity="5", unit_cost="10.00", days_ago=10)
    _post_move(tenant_a, item, location_a, quantity="-5", unit_cost="10.00",
               move_type="issue", days_ago=5)
    rows, totals = turnover_rows(tenant_a, 90)
    row = _row_for(rows, "RPT-FAST")
    assert row["cogs"] == Decimal("50.00")
    assert row["velocity"] == "fast"              # sold through: fastest possible mover
    assert row["turns"] is None                   # no measurable average stock to divide by
    assert totals["total_cogs"] == Decimal("50.00")


def test_turnover_zero_demand_stocked_item_is_dead(tenant_a, location_a):
    item = _costed_item(tenant_a, "RPT-DEAD", average_cost="4.00")
    _post_move(tenant_a, item, location_a, quantity="5", unit_cost="10.00", days_ago=20)
    rows, _totals = turnover_rows(tenant_a, 90)
    assert _row_for(rows, "RPT-DEAD")["velocity"] == "dead"


def test_turnover_high_turns_read_fast(tenant_a, location_a):
    item = _costed_item(tenant_a, "RPT-TURN", average_cost="1.00")
    _post_move(tenant_a, item, location_a, quantity="10", unit_cost="1.00", days_ago=200)
    _post_move(tenant_a, item, location_a, quantity="-9", unit_cost="5.00",
               move_type="issue", days_ago=30)
    rows, _totals = turnover_rows(tenant_a, 90)
    row = _row_for(rows, "RPT-TURN")
    assert row["velocity"] == "fast"
    assert row["turns"] is not None and row["turns"] >= Decimal("2")


# ------------------------------------------------------------------ _engine: aging health


def test_aging_health_flags_from_last_draw(tenant_a, location_a):
    never_drawn = _costed_item(tenant_a, "AGE-NONE")
    _post_move(tenant_a, never_drawn, location_a, quantity="4", unit_cost="5.00", days_ago=20)
    stale = _costed_item(tenant_a, "AGE-91")
    _post_move(tenant_a, stale, location_a, quantity="4", unit_cost="5.00", days_ago=120)
    _post_move(tenant_a, stale, location_a, quantity="-1", unit_cost="5.00",
               move_type="issue", days_ago=91)
    slowing = _costed_item(tenant_a, "AGE-75")
    _post_move(tenant_a, slowing, location_a, quantity="4", unit_cost="5.00", days_ago=120)
    _post_move(tenant_a, slowing, location_a, quantity="-1", unit_cost="5.00",
               move_type="issue", days_ago=75)
    moving = _costed_item(tenant_a, "AGE-10")
    _post_move(tenant_a, moving, location_a, quantity="4", unit_cost="5.00", days_ago=120)
    _post_move(tenant_a, moving, location_a, quantity="-1", unit_cost="5.00",
               move_type="issue", days_ago=10)
    rows, totals = aging_rows(tenant_a)
    assert _row_for(rows, "AGE-NONE")["health"] == "dead"     # no outbound leg EVER
    assert _row_for(rows, "AGE-91")["health"] == "dead"       # >= 91 days since last draw
    assert _row_for(rows, "AGE-75")["health"] == "slow"       # 61-90 band
    assert _row_for(rows, "AGE-10")["health"] == "healthy"
    assert totals["spots"] == 4


# ------------------------------------------------------------------ _engine: ABC Pareto


def test_abc_ranking_assigns_classes_by_issued_cost(tenant_a, location_a):
    heavy = _costed_item(tenant_a, "ABC-H")
    _post_move(tenant_a, heavy, location_a, quantity="40", unit_cost="10.00", days_ago=60)
    _post_move(tenant_a, heavy, location_a, quantity="-30", unit_cost="10.00",
               move_type="issue", days_ago=10)                       # cogs 300
    light = _costed_item(tenant_a, "ABC-L")
    _post_move(tenant_a, light, location_a, quantity="20", unit_cost="10.00", days_ago=60)
    _post_move(tenant_a, light, location_a, quantity="-10", unit_cost="10.00",
               move_type="issue", days_ago=20)                       # cogs 100
    sleeper = _costed_item(tenant_a, "ABC-Z", average_cost="3.00")
    _post_move(tenant_a, sleeper, location_a, quantity="7", unit_cost="3.00", days_ago=30)
    rows, meta = abc_rows(tenant_a, 90)
    top = _row_for(rows, "ABC-H")
    assert top["abc_class"] == "A" and top["cum_share"] <= Decimal("80")
    assert _row_for(rows, "ABC-L")["abc_class"] in ("B", "C")
    tail = _row_for(rows, "ABC-Z")
    assert tail["abc_class"] == "C" and tail["cum_share"] is None
    assert rows.index(tail) > rows.index(top)     # zero usage sorts behind every ranked SKU
    assert meta["a_items"] == 1 and meta["c_items"] == 2 and meta["b_items"] == 0


# ------------------------------------------------------------------ _engine: build_summary


def test_build_summary_freezes_scalar_only_json_for_all_report_types(tenant_a, location_a):
    wac = _costed_item(tenant_a, "SUM-WAC", average_cost="10.00")
    _post_move(tenant_a, wac, location_a, quantity="6", unit_cost="10.00", days_ago=80)
    _post_move(tenant_a, wac, location_a, quantity="-2", unit_cost="10.00",
               move_type="issue", days_ago=15)
    fifo = _costed_item(tenant_a, "SUM-FIFO", costing_method="fifo")
    _post_move(tenant_a, fifo, location_a, quantity="3", unit_cost="7.00", days_ago=70)
    _post_move(tenant_a, fifo, location_a, quantity="2", unit_cost="9.00", days_ago=40)
    _post_move(tenant_a, fifo, location_a, quantity="1", unit_cost="9.00",
               move_type="transfer", days_ago=5)
    idle = _costed_item(tenant_a, "SUM-IDLE", average_cost="2.00")
    _post_move(tenant_a, idle, location_a, quantity="5", unit_cost="2.00", days_ago=200)

    ledger = Ledger(tenant_a)
    for report_type in ("valuation", "turnover", "aging", "abc"):
        summary = build_summary(report_type, tenant_a, window_days=90, ledger=ledger)
        assert isinstance(summary, dict) and summary
        _assert_scalars_only(summary)

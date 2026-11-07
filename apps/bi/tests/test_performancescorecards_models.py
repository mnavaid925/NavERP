"""Unit tests for Sub-module 10.11 Performance Scorecards models.

Models covered:
- KpiDefinition (BKPI)
- PerformanceScorecard (BSCR)
- StrategicObjective (BOBJ)
- ScorecardKpiAssignment (BSCI)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.bi.models import (
    KpiDefinition,
    PerformanceScorecard,
    ScorecardKpiAssignment,
    StrategicObjective,
)


def _performancescorecards_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


# ==============================================================================
# 1. KpiDefinition Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_kpi_creation_autonumber_and_str(kpi_definition_a):
    """Test KpiDefinition creation, auto-numbering with BKPI prefix, and str representation."""
    assert kpi_definition_a.pk is not None
    assert kpi_definition_a.NUMBER_PREFIX == "BKPI"
    assert kpi_definition_a.number.startswith("BKPI-")
    expected_str = f"{kpi_definition_a.number} - {kpi_definition_a.name} ({kpi_definition_a.code})"
    assert str(kpi_definition_a) == expected_str
    assert kpi_definition_a.is_active is True
    assert kpi_definition_a.status == "active"


@pytest.mark.django_db
def test_performancescorecards_kpi_slug_generation_and_uniqueness(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test KpiDefinition auto-slugifies name and enforces tenant-isolated slug uniqueness."""
    kpi1 = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="CSAT_SCORE",
        name="Customer Satisfaction Index",
        category="customer_success",
        perspective="customer",
        owner=admin_user,
    )
    assert kpi1.slug == "customer-satisfaction-index"

    # Same slug in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            KpiDefinition.objects.create(
                tenant=tenant_a,
                code="CSAT_DUPE",
                name="Duplicate Slug KPI",
                slug="customer-satisfaction-index",
                owner=admin_user,
            )

    # Same slug in different tenant must succeed
    kpi_b = KpiDefinition.objects.create(
        tenant=tenant_b,
        code="CSAT_SCORE_B",
        name="Customer Satisfaction Index",
        slug="customer-satisfaction-index",
        owner=admin_user_b,
    )
    assert kpi_b.pk is not None
    assert kpi_b.slug == kpi1.slug
    assert kpi_b.tenant != kpi1.tenant


@pytest.mark.django_db
def test_performancescorecards_kpi_choice_fields():
    """Verify all defined choice sets on KpiDefinition model."""
    perspectives = _performancescorecards_choice_keys(KpiDefinition.PERSPECTIVE_CHOICES)
    assert "financial" in perspectives
    assert "customer" in perspectives
    assert "internal_process" in perspectives
    assert "learning_growth" in perspectives

    directions = _performancescorecards_choice_keys(KpiDefinition.DIRECTION_CHOICES)
    assert "maximize" in directions
    assert "minimize" in directions
    assert "in_range" in directions

    uoms = _performancescorecards_choice_keys(KpiDefinition.UOM_CHOICES)
    assert "percentage" in uoms
    assert "currency" in uoms
    assert "count" in uoms
    assert "days" in uoms
    assert "hours" in uoms
    assert "ratio" in uoms
    assert "score" in uoms

    frequencies = _performancescorecards_choice_keys(KpiDefinition.FREQUENCY_CHOICES)
    assert "daily" in frequencies
    assert "weekly" in frequencies
    assert "monthly" in frequencies
    assert "quarterly" in frequencies
    assert "annual" in frequencies

    calc_types = _performancescorecards_choice_keys(KpiDefinition.CALC_TYPE_CHOICES)
    assert "manual" in calc_types
    assert "semantic_measure" in calc_types
    assert "formula_expression" in calc_types
    assert "aggregation" in calc_types

    statuses = _performancescorecards_choice_keys(KpiDefinition.STATUS_CHOICES)
    assert "draft" in statuses
    assert "active" in statuses
    assert "under_review" in statuses
    assert "deprecated" in statuses
    assert "archived" in statuses


@pytest.mark.django_db
def test_performancescorecards_kpi_variance_and_benchmark_properties(tenant_a, admin_user):
    """Test KpiDefinition variance, variance_percentage, and benchmark_gap properties."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="OP_MARGIN",
        name="Operating Margin",
        target_direction="maximize",
        target_value=Decimal("20.0000"),
        current_value=Decimal("22.5000"),
        industry_benchmark_value=Decimal("18.0000"),
        owner=admin_user,
    )
    # variance = current - target = 22.5 - 20.0 = 2.5
    assert kpi.variance == Decimal("2.5000")
    # variance_percentage = (2.5 / 20.0) * 100 = 12.50
    assert kpi.variance_percentage == Decimal("12.50")
    # benchmark_gap = current - benchmark = 22.5 - 18.0 = 4.5
    assert kpi.benchmark_gap == Decimal("4.5000")

    # Case when benchmark is None
    kpi_no_bench = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="NO_BENCH",
        name="No Benchmark KPI",
        target_value=Decimal("10.0000"),
        current_value=Decimal("8.0000"),
        industry_benchmark_value=None,
        owner=admin_user,
    )
    assert kpi_no_bench.benchmark_gap is None
    assert kpi_no_bench.variance == Decimal("-2.0000")
    assert kpi_no_bench.variance_percentage == Decimal("-20.00")

    # Case with target 0
    kpi_zero_target = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="ZERO_TGT",
        name="Zero Target KPI",
        target_value=Decimal("0.0000"),
        current_value=Decimal("5.0000"),
        owner=admin_user,
    )
    assert kpi_zero_target.variance_percentage == Decimal("0.00")


@pytest.mark.django_db
def test_performancescorecards_kpi_calculate_rag_status_maximize(tenant_a, admin_user):
    """Test KpiDefinition.calculate_rag_status for maximize direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="SALES_REV",
        name="Sales Revenue",
        target_direction="maximize",
        target_value=Decimal("100.0000"),
        warning_threshold=Decimal("80.0000"),
        critical_threshold=Decimal("60.0000"),
        current_value=Decimal("105.0000"),
        owner=admin_user,
    )
    # cur >= tgt -> green
    assert kpi.calculate_rag_status() == "green"

    # tgt > cur >= warn -> amber
    kpi.current_value = Decimal("85.0000")
    assert kpi.calculate_rag_status() == "amber"

    # warn > cur >= crit -> amber (since warn is set)
    kpi.current_value = Decimal("70.0000")
    assert kpi.calculate_rag_status() == "amber"

    # cur < crit -> red
    kpi.current_value = Decimal("55.0000")
    assert kpi.calculate_rag_status() == "red"

    # Without thresholds: cur < tgt -> red
    kpi_no_thresh = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="MAX_NO_THRESH",
        name="Max No Threshold",
        target_direction="maximize",
        target_value=Decimal("100.0000"),
        current_value=Decimal("90.0000"),
        owner=admin_user,
    )
    assert kpi_no_thresh.calculate_rag_status() == "red"


@pytest.mark.django_db
def test_performancescorecards_kpi_calculate_rag_status_minimize(tenant_a, admin_user):
    """Test KpiDefinition.calculate_rag_status for minimize direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="DEFECT_RATE",
        name="Defect Rate",
        target_direction="minimize",
        target_value=Decimal("2.0000"),
        warning_threshold=Decimal("5.0000"),
        critical_threshold=Decimal("8.0000"),
        current_value=Decimal("1.5000"),
        owner=admin_user,
    )
    # cur <= tgt -> green
    assert kpi.calculate_rag_status() == "green"

    # tgt < cur <= warn -> amber
    kpi.current_value = Decimal("4.0000")
    assert kpi.calculate_rag_status() == "amber"

    # warn < cur <= crit -> amber (since warn is set)
    kpi.current_value = Decimal("6.0000")
    assert kpi.calculate_rag_status() == "amber"

    # cur > crit -> red
    kpi.current_value = Decimal("9.5000")
    assert kpi.calculate_rag_status() == "red"

    # Without thresholds: cur > tgt -> red
    kpi_no_thresh = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="MIN_NO_THRESH",
        name="Min No Threshold",
        target_direction="minimize",
        target_value=Decimal("2.0000"),
        current_value=Decimal("3.0000"),
        owner=admin_user,
    )
    assert kpi_no_thresh.calculate_rag_status() == "red"


@pytest.mark.django_db
def test_performancescorecards_kpi_calculate_rag_status_in_range(tenant_a, admin_user):
    """Test KpiDefinition.calculate_rag_status for in_range direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="INVENTORY_TURNS",
        name="Inventory Turns Band",
        target_direction="in_range",
        target_value=Decimal("12.0000"),
        warning_threshold=Decimal("10.0000"),  # lower bound
        critical_threshold=Decimal("15.0000"),  # upper bound
        current_value=Decimal("12.5000"),
        owner=admin_user,
    )
    # within bounds -> green
    assert kpi.calculate_rag_status() == "green"

    # below lower bound -> amber
    kpi.current_value = Decimal("9.0000")
    assert kpi.calculate_rag_status() == "amber"

    # above upper bound -> amber
    kpi.current_value = Decimal("16.0000")
    assert kpi.calculate_rag_status() == "amber"

    # Fallback bounds when warn/crit not specified (tgt * 0.9 to tgt * 1.1)
    # 10.0 * 0.9 = 9.0, 10.0 * 1.1 = 11.0
    kpi_auto = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="AUTO_RANGE",
        name="Auto Range KPI",
        target_direction="in_range",
        target_value=Decimal("10.0000"),
        current_value=Decimal("10.5000"),
        owner=admin_user,
    )
    assert kpi_auto.calculate_rag_status() == "green"
    kpi_auto.current_value = Decimal("8.5000")
    assert kpi_auto.calculate_rag_status() == "amber"


@pytest.mark.django_db
def test_performancescorecards_kpi_calculate_rag_status_inactive_or_archived(tenant_a, admin_user):
    """Test KpiDefinition.calculate_rag_status returns gray when inactive or archived/deprecated."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="INACTIVE_KPI",
        name="Inactive KPI",
        target_value=Decimal("100.0000"),
        current_value=Decimal("120.0000"),
        is_active=False,
        owner=admin_user,
    )
    assert kpi.calculate_rag_status() == "gray"

    kpi.is_active = True
    kpi.status = "archived"
    assert kpi.calculate_rag_status() == "gray"

    kpi.status = "deprecated"
    assert kpi.calculate_rag_status() == "gray"


@pytest.mark.django_db
def test_performancescorecards_kpi_calculate_rag_status_none_values(tenant_a, admin_user):
    """Test KpiDefinition.calculate_rag_status returns gray when current_value or target_value is None."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="NONE_KPI",
        name="None Value KPI",
        target_value=Decimal("100.0000"),
        current_value=Decimal("50.0000"),
        owner=admin_user,
    )
    kpi.current_value = None
    assert kpi.calculate_rag_status() == "gray"

    kpi.current_value = Decimal("50.0000")
    kpi.target_value = None
    assert kpi.calculate_rag_status() == "gray"


@pytest.mark.django_db
def test_performancescorecards_kpi_record_measurement_save(tenant_a, admin_user):
    """Test KpiDefinition.record_measurement shifts current to previous and saves updated values."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="REC_KPI",
        name="Recorded KPI",
        current_value=Decimal("50.0000"),
        previous_value=None,
        owner=admin_user,
    )
    before_time = timezone.now()
    kpi.record_measurement(Decimal("75.5000"), save=True)

    kpi.refresh_from_db()
    assert kpi.previous_value == Decimal("50.0000")
    assert kpi.current_value == Decimal("75.5000")
    assert kpi.last_calculated_at is not None
    assert kpi.last_calculated_at >= before_time


@pytest.mark.django_db
def test_performancescorecards_kpi_record_measurement_no_save(tenant_a, admin_user):
    """Test KpiDefinition.record_measurement with save=False alters in-memory instance only."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="REC_NOSAVE",
        name="No Save Measurement KPI",
        current_value=Decimal("40.0000"),
        previous_value=None,
        owner=admin_user,
    )
    kpi.record_measurement(Decimal("60.0000"), save=False)
    assert kpi.previous_value == Decimal("40.0000")
    assert kpi.current_value == Decimal("60.0000")

    # DB state remains unchanged
    kpi.refresh_from_db()
    assert kpi.previous_value is None
    assert kpi.current_value == Decimal("40.0000")


@pytest.mark.django_db
def test_performancescorecards_kpi_get_absolute_url(kpi_definition_a):
    """Test KpiDefinition.get_absolute_url returns correct reverse path."""
    assert kpi_definition_a.get_absolute_url() == f"/bi/kpis/{kpi_definition_a.pk}/"


# ==============================================================================
# 2. PerformanceScorecard Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_scorecard_creation_autonumber_and_str(performance_scorecard_a):
    """Test PerformanceScorecard creation, BSCR prefix numbering, and string formatting."""
    assert performance_scorecard_a.pk is not None
    assert performance_scorecard_a.NUMBER_PREFIX == "BSCR"
    assert performance_scorecard_a.number.startswith("BSCR-")
    expected_str = f"{performance_scorecard_a.number} - {performance_scorecard_a.name} ({performance_scorecard_a.fiscal_year})"
    assert str(performance_scorecard_a) == expected_str
    assert performance_scorecard_a.financial_weight == Decimal("25.00")
    assert performance_scorecard_a.customer_weight == Decimal("25.00")
    assert performance_scorecard_a.internal_process_weight == Decimal("25.00")
    assert performance_scorecard_a.learning_growth_weight == Decimal("25.00")


@pytest.mark.django_db
def test_performancescorecards_scorecard_slug_generation_and_uniqueness(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test PerformanceScorecard slug generation and tenant-isolated uniqueness."""
    sc1 = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Corporate Strategic Scorecard 2026",
        fiscal_year=2026,
        owner=admin_user,
    )
    assert sc1.slug == "corporate-strategic-scorecard-2026"

    # Duplicate slug in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PerformanceScorecard.objects.create(
                tenant=tenant_a,
                name="Duplicate Slug Scorecard",
                slug="corporate-strategic-scorecard-2026",
                fiscal_year=2026,
                owner=admin_user,
            )

    # Same slug in another tenant succeeds
    sc_b = PerformanceScorecard.objects.create(
        tenant=tenant_b,
        name="Corporate Strategic Scorecard 2026",
        slug="corporate-strategic-scorecard-2026",
        fiscal_year=2026,
        owner=admin_user_b,
    )
    assert sc_b.pk is not None
    assert sc_b.slug == sc1.slug
    assert sc_b.tenant != sc1.tenant


@pytest.mark.django_db
def test_performancescorecards_scorecard_choice_fields():
    """Verify all defined choice sets on PerformanceScorecard model."""
    types = _performancescorecards_choice_keys(PerformanceScorecard.SCORECARD_TYPE_CHOICES)
    assert "balanced_scorecard" in types
    assert "executive" in types
    assert "departmental" in types
    assert "operational" in types
    assert "strategic_initiative" in types

    periods = _performancescorecards_choice_keys(PerformanceScorecard.PERIOD_CHOICES)
    assert "monthly" in periods
    assert "quarterly" in periods
    assert "semi_annual" in periods
    assert "annual" in periods
    assert "rolling_12_months" in periods

    rag_statuses = _performancescorecards_choice_keys(PerformanceScorecard.RAG_STATUS_CHOICES)
    assert "green" in rag_statuses
    assert "amber" in rag_statuses
    assert "red" in rag_statuses
    assert "gray" in rag_statuses

    statuses = _performancescorecards_choice_keys(PerformanceScorecard.STATUS_CHOICES)
    assert "draft" in statuses
    assert "active" in statuses
    assert "in_review" in statuses
    assert "closed" in statuses
    assert "archived" in statuses


@pytest.mark.django_db
def test_performancescorecards_scorecard_get_absolute_url(performance_scorecard_a):
    """Test PerformanceScorecard.get_absolute_url returns correct detail path."""
    assert performance_scorecard_a.get_absolute_url() == f"/bi/scorecards/{performance_scorecard_a.pk}/"


@pytest.mark.django_db
def test_performancescorecards_scorecard_default_handling_same_tenant(tenant_a, admin_user):
    """Test that setting is_default=True unsets is_default on other scorecards for the same tenant."""
    sc1 = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Scorecard Alpha",
        is_default=True,
        owner=admin_user,
    )
    assert sc1.is_default is True

    sc2 = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Scorecard Beta",
        is_default=True,
        owner=admin_user,
    )
    sc1.refresh_from_db()
    assert sc1.is_default is False
    assert sc2.is_default is True

    # Updating sc1 back to default unsets sc2
    sc1.is_default = True
    sc1.save()
    sc2.refresh_from_db()
    assert sc1.is_default is True
    assert sc2.is_default is False


@pytest.mark.django_db
def test_performancescorecards_scorecard_default_handling_cross_tenant_isolation(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test that is_default reset respects tenant boundary and leaves other tenants intact."""
    sc_a = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Acme Default Scorecard",
        is_default=True,
        owner=admin_user,
    )
    sc_b = PerformanceScorecard.objects.create(
        tenant=tenant_b,
        name="Globex Default Scorecard",
        is_default=True,
        owner=admin_user_b,
    )
    # Both remain default because they are in separate tenants
    sc_a.refresh_from_db()
    sc_b.refresh_from_db()
    assert sc_a.is_default is True
    assert sc_b.is_default is True

    # Adding another in tenant_a does not affect tenant_b
    sc_a2 = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Acme Second Scorecard",
        is_default=True,
        owner=admin_user,
    )
    sc_a.refresh_from_db()
    sc_b.refresh_from_db()
    assert sc_a.is_default is False
    assert sc_a2.is_default is True
    assert sc_b.is_default is True


@pytest.mark.django_db
def test_performancescorecards_scorecard_recalculate_performance_empty(performance_scorecard_a):
    """Test PerformanceScorecard.recalculate_performance with zero assignments sets score 0 and gray."""
    performance_scorecard_a.kpi_assignments.all().delete()
    performance_scorecard_a.recalculate_performance()
    performance_scorecard_a.refresh_from_db()

    assert performance_scorecard_a.overall_score == Decimal("0.00")
    assert performance_scorecard_a.overall_rag_status == "gray"
    assert performance_scorecard_a.last_recalculated_at is not None


@pytest.mark.django_db
def test_performancescorecards_scorecard_recalculate_performance_weighted_multi_perspective(tenant_a, admin_user):
    """Test recalculate_performance aggregates weighted scores across the four BSC perspectives."""
    scorecard = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Balanced Strategy 2026",
        financial_weight=Decimal("40.00"),
        customer_weight=Decimal("30.00"),
        internal_process_weight=Decimal("20.00"),
        learning_growth_weight=Decimal("10.00"),
        owner=admin_user,
    )

    # 1. Financial: 2 KPIs (weight 50 and 50)
    # KPI 1: target 100, actual 100 -> score 100.00
    # KPI 2: target 100, actual 80 (with warn 80) -> score 75.00
    # Financial score = (100 * 50 + 75 * 50) / 100 = 87.50
    kpi_f1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="FIN_1", name="Fin 1", perspective="financial",
        target_value=Decimal("100.0000"), current_value=Decimal("100.0000"),
        owner=admin_user,
    )
    kpi_f2 = KpiDefinition.objects.create(
        tenant=tenant_a, code="FIN_2", name="Fin 2", perspective="financial",
        target_value=Decimal("100.0000"), warning_threshold=Decimal("80.0000"),
        current_value=Decimal("80.0000"), owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_f1, perspective="financial",
        weight=Decimal("50.00"), actual_value=Decimal("100.0000"),
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_f2, perspective="financial",
        weight=Decimal("50.00"), actual_value=Decimal("80.0000"),
    )

    # 2. Customer: 1 KPI (weight 100) -> actual 75 / 100 (warn 70) -> amber (score 75.00)
    kpi_c1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="CUST_1", name="Cust 1", perspective="customer",
        target_value=Decimal("100.0000"), warning_threshold=Decimal("70.0000"),
        current_value=Decimal("75.0000"), owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_c1, perspective="customer",
        weight=Decimal("100.00"), actual_value=Decimal("75.0000"),
    )

    # 3. Internal: 1 KPI -> actual 100 / 100 -> score 100.00
    kpi_i1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="INT_1", name="Int 1", perspective="internal_process",
        target_value=Decimal("100.0000"), current_value=Decimal("100.0000"),
        owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_i1, perspective="internal_process",
        weight=Decimal("100.00"), actual_value=Decimal("100.0000"),
    )

    # 4. Learning: 1 KPI -> actual 100 / 100 -> score 100.00
    kpi_l1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="LRN_1", name="Lrn 1", perspective="learning_growth",
        target_value=Decimal("100.0000"), current_value=Decimal("100.0000"),
        owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_l1, perspective="learning_growth",
        weight=Decimal("100.00"), actual_value=Decimal("100.0000"),
    )

    # Financial = 87.50, weight 40 -> 3500
    # Customer = 75.00, weight 30 -> 2250
    # Internal = 100.00, weight 20 -> 2000
    # Learning = 100.00, weight 10 -> 1000
    # Total = (3500 + 2250 + 2000 + 1000) / 100 = 8750 / 100 = 87.50
    scorecard.recalculate_performance()
    scorecard.refresh_from_db()

    assert scorecard.overall_score == Decimal("87.50")
    assert scorecard.overall_rag_status == "green"  # >= 85.00


@pytest.mark.django_db
def test_performancescorecards_scorecard_recalculate_rag_status_brackets(tenant_a, admin_user):
    """Test PerformanceScorecard overall_rag_status brackets: green (>=85), amber (>=70), red (>0)."""
    scorecard = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="RAG Brackets Scorecard",
        financial_weight=Decimal("100.00"),
        customer_weight=Decimal("0.00"),
        internal_process_weight=Decimal("0.00"),
        learning_growth_weight=Decimal("0.00"),
        owner=admin_user,
    )
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a, code="BRACKET_KPI", name="Bracket KPI", perspective="financial",
        target_value=Decimal("100.0000"), owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi, perspective="financial",
        weight=Decimal("100.00"), actual_value=Decimal("100.0000"),
    )

    # 1. Green bracket (>= 85.00)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("85.00"))
    scorecard.recalculate_performance()
    scorecard.refresh_from_db()
    assert scorecard.overall_rag_status == "green"

    # 2. Amber bracket (70.00 to 84.99)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("72.50"))
    scorecard.recalculate_performance()
    scorecard.refresh_from_db()
    assert scorecard.overall_rag_status == "amber"

    # 3. Red bracket (0.01 to 69.99)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("50.00"))
    scorecard.recalculate_performance()
    scorecard.refresh_from_db()
    assert scorecard.overall_rag_status == "red"

    # 4. Gray bracket (0.00)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("0.00"))
    scorecard.recalculate_performance()
    scorecard.refresh_from_db()
    assert scorecard.overall_rag_status == "gray"


@pytest.mark.django_db
def test_performancescorecards_scorecard_get_perspective_summary(tenant_a, admin_user):
    """Test PerformanceScorecard.get_perspective_summary returns aggregated metrics per perspective."""
    scorecard = PerformanceScorecard.objects.create(
        tenant=tenant_a,
        name="Perspective Summary Scorecard",
        owner=admin_user,
    )
    # Financial 1: green, score 100
    kpi_f1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="PS_F1", name="PS F1", perspective="financial",
        target_value=Decimal("100.0000"), owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_f1, perspective="financial",
        actual_value=Decimal("100.0000"),
    )
    # Financial 2: amber, score 75
    kpi_f2 = KpiDefinition.objects.create(
        tenant=tenant_a, code="PS_F2", name="PS F2", perspective="financial",
        target_value=Decimal("100.0000"), warning_threshold=Decimal("80.0000"),
        owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_f2, perspective="financial",
        actual_value=Decimal("80.0000"),
    )

    # Customer 1: green, score 100
    kpi_c1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="PS_C1", name="PS C1", perspective="customer",
        target_value=Decimal("50.0000"), owner=admin_user,
    )
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=scorecard, kpi=kpi_c1, perspective="customer",
        actual_value=Decimal("50.0000"),
    )

    summary = scorecard.get_perspective_summary()
    assert summary["financial"]["count"] == 2
    assert summary["financial"]["on_track"] == 1  # 1 green, 1 amber
    assert summary["financial"]["avg_score"] == Decimal("87.50")  # (100 + 75) / 2

    assert summary["customer"]["count"] == 1
    assert summary["customer"]["on_track"] == 1
    assert summary["customer"]["avg_score"] == Decimal("100.00")

    assert summary["internal_process"]["count"] == 0
    assert summary["internal_process"]["avg_score"] == Decimal("0.00")

    assert summary["learning_growth"]["count"] == 0
    assert summary["learning_growth"]["avg_score"] == Decimal("0.00")


# ==============================================================================
# 3. StrategicObjective Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_objective_creation_autonumber_and_str(strategic_objective_a):
    """Test StrategicObjective creation, BOBJ prefix numbering, and str representation."""
    assert strategic_objective_a.pk is not None
    assert strategic_objective_a.NUMBER_PREFIX == "BOBJ"
    assert strategic_objective_a.number.startswith("BOBJ-")
    expected_str = f"{strategic_objective_a.number} - {strategic_objective_a.name} ({strategic_objective_a.code})"
    assert str(strategic_objective_a) == expected_str
    assert strategic_objective_a.status == "active"
    assert strategic_objective_a.sort_order == 10


@pytest.mark.django_db
def test_performancescorecards_objective_slug_generation_and_uniqueness(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test StrategicObjective slug generation and tenant-isolated slug uniqueness."""
    obj1 = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="EXP_MARKET",
        name="Expand International Operations",
        perspective="financial",
        owner=admin_user,
    )
    assert obj1.slug == "expand-international-operations"

    # Same slug in same tenant must raise IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            StrategicObjective.objects.create(
                tenant=tenant_a,
                code="EXP_DUPE",
                name="Duplicate Slug Objective",
                slug="expand-international-operations",
                perspective="financial",
                owner=admin_user,
            )

    # Same slug in different tenant succeeds
    obj_b = StrategicObjective.objects.create(
        tenant=tenant_b,
        code="EXP_MARKET_B",
        name="Expand International Operations",
        slug="expand-international-operations",
        perspective="financial",
        owner=admin_user_b,
    )
    assert obj_b.pk is not None
    assert obj_b.slug == obj1.slug
    assert obj_b.tenant != obj1.tenant


@pytest.mark.django_db
def test_performancescorecards_objective_choice_fields():
    """Verify all defined choice sets on StrategicObjective model."""
    perspectives = _performancescorecards_choice_keys(StrategicObjective.PERSPECTIVE_CHOICES)
    assert "financial" in perspectives
    assert "customer" in perspectives
    assert "internal_process" in perspectives
    assert "learning_growth" in perspectives

    rag_statuses = _performancescorecards_choice_keys(StrategicObjective.RAG_STATUS_CHOICES)
    assert "green" in rag_statuses
    assert "amber" in rag_statuses
    assert "red" in rag_statuses
    assert "gray" in rag_statuses

    statuses = _performancescorecards_choice_keys(StrategicObjective.STATUS_CHOICES)
    assert "proposed" in statuses
    assert "active" in statuses
    assert "achieved" in statuses
    assert "postponed" in statuses
    assert "canceled" in statuses


@pytest.mark.django_db
def test_performancescorecards_objective_hierarchy_parent_child(tenant_a, admin_user):
    """Test StrategicObjective parent-child self-referential hierarchy."""
    parent = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="PARENT_OBJ",
        name="Parent Strategic Objective",
        perspective="financial",
        owner=admin_user,
    )
    child1 = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="CHILD_OBJ_1",
        name="Child Objective One",
        parent_objective=parent,
        perspective="internal_process",
        owner=admin_user,
    )
    child2 = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="CHILD_OBJ_2",
        name="Child Objective Two",
        parent_objective=parent,
        perspective="customer",
        owner=admin_user,
    )
    children = list(parent.child_objectives.all())
    assert len(children) == 2
    assert child1 in children
    assert child2 in children


@pytest.mark.django_db
def test_performancescorecards_objective_get_absolute_url(strategic_objective_a):
    """Test StrategicObjective.get_absolute_url returns correct detail path."""
    assert strategic_objective_a.get_absolute_url() == f"/bi/objectives/{strategic_objective_a.pk}/"


@pytest.mark.django_db
def test_performancescorecards_objective_recalculate_alignment_empty_achieved(tenant_a, admin_user):
    """Test recalculate_alignment sets 100% and green when objective is achieved without KPI assignments."""
    obj = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="ACHIEVED_OBJ",
        name="Achieved Objective",
        status="achieved",
        owner=admin_user,
    )
    obj.recalculate_alignment()
    obj.refresh_from_db()
    assert obj.alignment_score == Decimal("100.00")
    assert obj.rag_status == "green"


@pytest.mark.django_db
def test_performancescorecards_objective_recalculate_alignment_empty_canceled_postponed(tenant_a, admin_user):
    """Test recalculate_alignment sets gray when objective is canceled or postponed without KPI assignments."""
    obj_cancel = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="CANCELED_OBJ",
        name="Canceled Objective",
        status="canceled",
        owner=admin_user,
    )
    obj_cancel.recalculate_alignment()
    obj_cancel.refresh_from_db()
    assert obj_cancel.rag_status == "gray"

    obj_postpone = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="POSTPONED_OBJ",
        name="Postponed Objective",
        status="postponed",
        owner=admin_user,
    )
    obj_postpone.recalculate_alignment()
    obj_postpone.refresh_from_db()
    assert obj_postpone.rag_status == "gray"


@pytest.mark.django_db
def test_performancescorecards_objective_recalculate_alignment_with_kpis(tenant_a, admin_user, performance_scorecard_a):
    """Test recalculate_alignment averages normalized scores from linked scorecard KPIs."""
    obj = StrategicObjective.objects.create(
        tenant=tenant_a,
        code="ALIGN_OBJ",
        name="Aligned Revenue Growth",
        status="active",
        owner=admin_user,
    )
    kpi1 = KpiDefinition.objects.create(
        tenant=tenant_a, code="K1", name="K1", target_value=Decimal("100.0000"),
        current_value=Decimal("100.0000"), owner=admin_user,
    )
    kpi2 = KpiDefinition.objects.create(
        tenant=tenant_a, code="K2", name="K2", target_value=Decimal("100.0000"),
        warning_threshold=Decimal("80.0000"), current_value=Decimal("80.0000"),
        owner=admin_user,
    )
    # Assignment 1: 100/100 -> score 100.00
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=performance_scorecard_a, kpi=kpi1, objective=obj,
        actual_value=Decimal("100.0000"),
    )
    # Assignment 2: 80/100 (warn 80) -> score 75.00
    ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=performance_scorecard_a, kpi=kpi2, objective=obj,
        actual_value=Decimal("80.0000"),
    )

    # Average score = (100.00 + 75.00) / 2 = 87.50
    obj.recalculate_alignment()
    obj.refresh_from_db()
    assert obj.alignment_score == Decimal("87.50")
    assert obj.rag_status == "green"  # >= 85.00


@pytest.mark.django_db
def test_performancescorecards_objective_recalculate_rag_brackets(tenant_a, admin_user, performance_scorecard_a):
    """Test StrategicObjective.recalculate_alignment RAG health thresholds."""
    obj = StrategicObjective.objects.create(
        tenant=tenant_a, code="OBJ_BRACKETS", name="Objective Brackets", owner=admin_user,
    )
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a, code="K_BRACKET", name="K Bracket", target_value=Decimal("100.0000"), owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a, scorecard=performance_scorecard_a, kpi=kpi, objective=obj,
        actual_value=Decimal("100.0000"),
    )

    # 1. Amber (70.00 to 84.99)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("75.00"))
    obj.recalculate_alignment()
    obj.refresh_from_db()
    assert obj.rag_status == "amber"

    # 2. Red (0.01 to 69.99)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("45.00"))
    obj.recalculate_alignment()
    obj.refresh_from_db()
    assert obj.rag_status == "red"

    # 3. Gray (0.00)
    ScorecardKpiAssignment.objects.filter(pk=assign.pk).update(normalized_score=Decimal("0.00"))
    obj.recalculate_alignment()
    obj.refresh_from_db()
    assert obj.rag_status == "gray"


# ==============================================================================
# 4. ScorecardKpiAssignment Model Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_assignment_creation_autonumber_and_str(scorecard_kpi_assignment_a):
    """Test ScorecardKpiAssignment creation, BSCI prefix numbering, and string formatting."""
    assert scorecard_kpi_assignment_a.pk is not None
    assert scorecard_kpi_assignment_a.NUMBER_PREFIX == "BSCI"
    assert scorecard_kpi_assignment_a.number.startswith("BSCI-")
    expected_str = f"{scorecard_kpi_assignment_a.number} - {scorecard_kpi_assignment_a.scorecard.name} / {scorecard_kpi_assignment_a.kpi.name}"
    assert str(scorecard_kpi_assignment_a) == expected_str
    assert scorecard_kpi_assignment_a.weight == Decimal("25.00")
    assert scorecard_kpi_assignment_a.trend_direction == "steady"


@pytest.mark.django_db
def test_performancescorecards_assignment_unique_scorecard_kpi_per_tenant(scorecard_kpi_assignment_a, tenant_a, tenant_b, admin_user_b):
    """Test that a KPI cannot be assigned more than once to the same scorecard within a tenant."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ScorecardKpiAssignment.objects.create(
                tenant=tenant_a,
                scorecard=scorecard_kpi_assignment_a.scorecard,
                kpi=scorecard_kpi_assignment_a.kpi,
                actual_value=Decimal("10.0000"),
            )


@pytest.mark.django_db
def test_performancescorecards_assignment_choice_fields():
    """Verify all defined choice sets on ScorecardKpiAssignment model."""
    perspectives = _performancescorecards_choice_keys(ScorecardKpiAssignment.PERSPECTIVE_CHOICES)
    assert "financial" in perspectives
    assert "customer" in perspectives
    assert "internal_process" in perspectives
    assert "learning_growth" in perspectives

    rag_statuses = _performancescorecards_choice_keys(ScorecardKpiAssignment.RAG_STATUS_CHOICES)
    assert "green" in rag_statuses
    assert "amber" in rag_statuses
    assert "red" in rag_statuses
    assert "gray" in rag_statuses

    trends = _performancescorecards_choice_keys(ScorecardKpiAssignment.TREND_CHOICES)
    assert "improving" in trends
    assert "steady" in trends
    assert "deteriorating" in trends


@pytest.mark.django_db
def test_performancescorecards_assignment_get_absolute_url(scorecard_kpi_assignment_a):
    """Test ScorecardKpiAssignment.get_absolute_url returns correct detail path."""
    assert scorecard_kpi_assignment_a.get_absolute_url() == f"/bi/assignments/{scorecard_kpi_assignment_a.pk}/"


@pytest.mark.django_db
def test_performancescorecards_assignment_save_defaults_from_kpi(tenant_a, admin_user, performance_scorecard_a):
    """Test ScorecardKpiAssignment defaults perspective, target_value, and benchmark from KpiDefinition on save."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="AUTO_DEF_KPI",
        name="Auto Defaults KPI",
        perspective="learning_growth",
        target_value=Decimal("80.0000"),
        industry_benchmark_value=Decimal("75.0000"),
        owner=admin_user,
    )
    # Create assignment with empty perspective to test defaulting from KPI
    assign = ScorecardKpiAssignment(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        perspective="",
        actual_value=Decimal("85.0000"),
    )
    assign.save()

    assert assign.perspective == "learning_growth"
    assert assign.target_value == Decimal("80.0000")
    assert assign.benchmark_overlay_value == Decimal("75.0000")
    assert assign.variance == Decimal("5.0000")  # 85 - 80
    assert assign.benchmark_gap == Decimal("10.0000")  # 85 - 75


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_maximize(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics for maximize KPI direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="ASSIGN_MAX",
        name="Assign Max",
        target_direction="maximize",
        target_value=Decimal("100.0000"),
        warning_threshold=Decimal("80.0000"),
        critical_threshold=Decimal("60.0000"),
        owner=admin_user,
    )
    # 1. On track (actual >= target)
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("110.0000"),
    )
    assert assign.rag_status == "green"
    assert assign.normalized_score == Decimal("100.00")
    assert assign.variance == Decimal("10.0000")
    assert assign.variance_percentage == Decimal("10.00")

    # 2. Warning zone (actual >= warning)
    assign.actual_value = Decimal("85.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("75.00")
    assert assign.variance == Decimal("-15.0000")
    assert assign.variance_percentage == Decimal("-15.00")

    # 3. Critical zone (actual < critical)
    assign.actual_value = Decimal("50.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "red"
    assert assign.normalized_score == Decimal("40.00")

    # 4. Amber fallthrough (actual between crit and warn)
    assign.actual_value = Decimal("70.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("60.00")


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_minimize(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics for minimize KPI direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="ASSIGN_MIN",
        name="Assign Min",
        target_direction="minimize",
        target_value=Decimal("10.0000"),
        warning_threshold=Decimal("20.0000"),
        critical_threshold=Decimal("30.0000"),
        owner=admin_user,
    )
    # 1. On track (actual <= target)
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("8.0000"),
    )
    assert assign.rag_status == "green"
    assert assign.normalized_score == Decimal("100.00")
    assert assign.variance == Decimal("-2.0000")
    assert assign.variance_percentage == Decimal("-20.00")

    # 2. Warning zone (actual <= warning)
    assign.actual_value = Decimal("15.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("75.00")

    # 3. Critical zone (actual > critical)
    assign.actual_value = Decimal("35.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "red"
    assert assign.normalized_score == Decimal("40.00")

    # 4. Amber fallthrough (actual between warn and crit)
    assign.actual_value = Decimal("25.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("60.00")


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_in_range(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics for in_range KPI direction."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="ASSIGN_RANGE",
        name="Assign Range",
        target_direction="in_range",
        target_value=Decimal("50.0000"),
        warning_threshold=Decimal("40.0000"),
        critical_threshold=Decimal("60.0000"),
        owner=admin_user,
    )
    # 1. In range -> green, 100%
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("48.0000"),
    )
    assert assign.rag_status == "green"
    assert assign.normalized_score == Decimal("100.00")

    # 2. Out of range -> amber, 60%
    assign.actual_value = Decimal("35.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("60.00")

    assign.actual_value = Decimal("65.0000")
    assign.calculate_performance_metrics()
    assert assign.rag_status == "amber"
    assert assign.normalized_score == Decimal("60.00")


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_trend_maximize(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics trend direction for maximize KPIs."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="TREND_MAX",
        name="Trend Max",
        target_direction="maximize",
        target_value=Decimal("100.0000"),
        previous_value=Decimal("70.0000"),
        owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("80.0000"),
    )
    # actual > previous -> improving
    assert assign.trend_direction == "improving"

    # actual < previous -> deteriorating
    assign.actual_value = Decimal("60.0000")
    assign.calculate_performance_metrics()
    assert assign.trend_direction == "deteriorating"

    # actual == previous -> steady
    assign.actual_value = Decimal("70.0000")
    assign.calculate_performance_metrics()
    assert assign.trend_direction == "steady"


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_trend_minimize(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics trend direction for minimize KPIs."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="TREND_MIN",
        name="Trend Min",
        target_direction="minimize",
        target_value=Decimal("10.0000"),
        previous_value=Decimal("15.0000"),
        owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("12.0000"),
    )
    # actual < previous -> improving (for minimize)
    assert assign.trend_direction == "improving"

    # actual > previous -> deteriorating (for minimize)
    assign.actual_value = Decimal("18.0000")
    assign.calculate_performance_metrics()
    assert assign.trend_direction == "deteriorating"

    # actual == previous -> steady
    assign.actual_value = Decimal("15.0000")
    assign.calculate_performance_metrics()
    assert assign.trend_direction == "steady"


@pytest.mark.django_db
def test_performancescorecards_assignment_metrics_benchmark_gap(tenant_a, admin_user, performance_scorecard_a):
    """Test calculate_performance_metrics calculates benchmark_gap against overlay or KPI benchmark."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="GAP_KPI",
        name="Gap KPI",
        industry_benchmark_value=Decimal("80.0000"),
        owner=admin_user,
    )
    # Uses KPI benchmark as default overlay
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("95.0000"),
    )
    assert assign.benchmark_overlay_value == Decimal("80.0000")
    assert assign.benchmark_gap == Decimal("15.0000")

    # Custom overlay value overrides KPI benchmark
    assign.benchmark_overlay_value = Decimal("90.0000")
    assign.calculate_performance_metrics()
    assert assign.benchmark_gap == Decimal("5.0000")


@pytest.mark.django_db
def test_performancescorecards_assignment_record_actual_value_save(tenant_a, admin_user, performance_scorecard_a):
    """Test ScorecardKpiAssignment.record_actual_value with save=True updates DB and recalculates metrics."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="REC_ACT_KPI",
        name="Record Actual KPI",
        target_value=Decimal("100.0000"),
        owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("50.0000"),
    )
    assert assign.rag_status == "red"

    before_time = timezone.now()
    assign.record_actual_value(Decimal("100.0000"), save=True)

    assign.refresh_from_db()
    assert assign.actual_value == Decimal("100.0000")
    assert assign.rag_status == "green"
    assert assign.normalized_score == Decimal("100.00")
    assert assign.evaluated_at is not None
    assert assign.evaluated_at >= before_time


@pytest.mark.django_db
def test_performancescorecards_assignment_record_actual_value_no_save(tenant_a, admin_user, performance_scorecard_a):
    """Test ScorecardKpiAssignment.record_actual_value with save=False updates in-memory metrics only."""
    kpi = KpiDefinition.objects.create(
        tenant=tenant_a,
        code="REC_ACT_NOSAVE",
        name="Record Actual No Save",
        target_value=Decimal("100.0000"),
        owner=admin_user,
    )
    assign = ScorecardKpiAssignment.objects.create(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi,
        actual_value=Decimal("60.0000"),
    )
    assign.record_actual_value(Decimal("110.0000"), save=False)
    assert assign.actual_value == Decimal("110.0000")
    assert assign.rag_status == "green"

    # DB remains unchanged
    assign.refresh_from_db()
    assert assign.actual_value == Decimal("60.0000")
    assert assign.rag_status == "red"


# ==============================================================================
# 5. Cross-Tenant Isolation Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_cross_tenant_isolation_all_models(
    tenant_a, tenant_b, admin_user, admin_user_b,
    kpi_definition_a, kpi_definition_b,
    performance_scorecard_a, performance_scorecard_b,
    strategic_objective_a, strategic_objective_b,
    scorecard_kpi_assignment_a, scorecard_kpi_assignment_b,
):
    """Verify complete tenant isolation across all four Performance Scorecard models."""
    # Tenant A queries must never return Tenant B records
    assert KpiDefinition.objects.filter(tenant=tenant_a, pk=kpi_definition_b.pk).exists() is False
    assert PerformanceScorecard.objects.filter(tenant=tenant_a, pk=performance_scorecard_b.pk).exists() is False
    assert StrategicObjective.objects.filter(tenant=tenant_a, pk=strategic_objective_b.pk).exists() is False
    assert ScorecardKpiAssignment.objects.filter(tenant=tenant_a, pk=scorecard_kpi_assignment_b.pk).exists() is False

    # Tenant B queries must never return Tenant A records
    assert KpiDefinition.objects.filter(tenant=tenant_b, pk=kpi_definition_a.pk).exists() is False
    assert PerformanceScorecard.objects.filter(tenant=tenant_b, pk=performance_scorecard_a.pk).exists() is False
    assert StrategicObjective.objects.filter(tenant=tenant_b, pk=strategic_objective_a.pk).exists() is False
    assert ScorecardKpiAssignment.objects.filter(tenant=tenant_b, pk=scorecard_kpi_assignment_a.pk).exists() is False

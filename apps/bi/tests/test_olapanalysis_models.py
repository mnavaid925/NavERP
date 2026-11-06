"""Unit tests for Sub-module 10.12 OLAP & Multidimensional Analysis models.

Models covered:
- OlapCube (BOCB)
- PivotAnalysisView (BPIV)
- WhatIfScenario (BWIF)
- ScenarioWritebackCell (BWBC)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import Budget, FiscalPeriod, GLAccount
from apps.bi.models import (
    OlapCube,
    PivotAnalysisView,
    ScenarioWritebackCell,
    WhatIfScenario,
)
from apps.core.models import OrgUnit


def _olapanalysis_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


# ---------------------------------------------------------------------------
# 1. OlapCube Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_cube_creation_and_autonumber(olap_cube_a):
    """Test OlapCube creation, BOCB- auto-numbering, default properties, and str."""
    assert olap_cube_a.pk is not None
    assert olap_cube_a.NUMBER_PREFIX == "BOCB"
    assert olap_cube_a.number.startswith("BOCB-")
    assert str(olap_cube_a) == f"{olap_cube_a.name} ({olap_cube_a.number})"
    assert olap_cube_a.get_absolute_url() == f"/bi/olap/cubes/{olap_cube_a.pk}/"
    assert olap_cube_a.dimension_count == 2
    assert olap_cube_a.measure_count == 2


@pytest.mark.django_db
def test_olapanalysis_cube_storage_mode_choices(tenant_a, admin_user):
    """Test OlapCube storage_mode choices and configurations."""
    keys = _olapanalysis_choice_keys(OlapCube.STORAGE_MODE_CHOICES)
    assert "rolap" in keys
    assert "summary_rollup" in keys
    assert "hybrid" in keys
    assert "molap" in keys

    cube = OlapCube.objects.create(
        tenant=tenant_a,
        name="Rolap Dynamic Cube",
        slug="rolap-dynamic-cube",
        storage_mode="rolap",
        created_by=admin_user,
    )
    assert cube.storage_mode == "rolap"
    assert cube.dimensions_config == []
    assert cube.measures_config == []
    assert cube.time_intelligence_enabled is True
    assert cube.cache_ttl_minutes == 60


@pytest.mark.django_db
def test_olapanalysis_cube_status_choices(tenant_a, admin_user):
    """Test OlapCube status choices."""
    keys = _olapanalysis_choice_keys(OlapCube.STATUS_CHOICES)
    assert "draft" in keys
    assert "active" in keys
    assert "archived" in keys

    cube = OlapCube.objects.create(
        tenant=tenant_a,
        name="Archived Cube",
        slug="archived-cube",
        status="archived",
        created_by=admin_user,
    )
    assert cube.status == "archived"


@pytest.mark.django_db
def test_olapanalysis_cube_dimensions_and_measures_config(tenant_a, admin_user):
    """Test OlapCube dimensions and measures complex JSON configurations."""
    dims = [
        {"name": "Customer", "field": "cust_id", "type": "dimension"},
        {"name": "Time", "field": "order_date", "type": "time"},
        {"name": "Geography", "field": "region", "type": "dimension"},
    ]
    measures = [
        {"name": "Gross Sales", "field": "amount", "agg": "sum"},
        {"name": "Discount", "field": "discount", "agg": "sum"},
        {"name": "Net Sales", "formula": "[Gross Sales] - [Discount]", "agg": "calculated"},
    ]
    cube = OlapCube.objects.create(
        tenant=tenant_a,
        name="Sales Analytics Cube",
        slug="sales-analytics-cube",
        dimensions_config=dims,
        measures_config=measures,
        created_by=admin_user,
    )
    assert cube.dimension_count == 3
    assert cube.measure_count == 3
    assert cube.dimensions_config[0]["name"] == "Customer"
    assert cube.measures_config[2]["formula"] == "[Gross Sales] - [Discount]"


@pytest.mark.django_db
def test_olapanalysis_cube_slug_uniqueness_per_tenant(tenant_a, admin_user):
    """Test OlapCube slug uniqueness is enforced per tenant."""
    OlapCube.objects.create(
        tenant=tenant_a,
        name="Duplicate Slug Cube",
        slug="unique-cube-slug",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OlapCube.objects.create(
                tenant=tenant_a,
                name="Another Cube Same Slug",
                slug="unique-cube-slug",
                created_by=admin_user,
            )


@pytest.mark.django_db
def test_olapanalysis_cube_cross_tenant_slug_allowance(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test that identical OlapCube slugs are allowed across different tenants."""
    cube_a = OlapCube.objects.create(
        tenant=tenant_a,
        name="Corporate Cube",
        slug="corporate-shared-slug",
        created_by=admin_user,
    )
    cube_b = OlapCube.objects.create(
        tenant=tenant_b,
        name="Corporate Cube",
        slug="corporate-shared-slug",
        created_by=admin_user_b,
    )
    assert cube_a.slug == cube_b.slug
    assert cube_a.tenant != cube_b.tenant
    assert cube_a.pk != cube_b.pk


@pytest.mark.django_db
def test_olapanalysis_cube_auto_slug_generation(tenant_a, admin_user):
    """Test that blank slug is automatically populated from cube name."""
    cube = OlapCube.objects.create(
        tenant=tenant_a,
        name="Revenue & Margin Cube 2026",
        slug="",
        created_by=admin_user,
    )
    assert cube.slug == "revenue-margin-cube-2026"


@pytest.mark.django_db
def test_olapanalysis_cube_refresh_cube(olap_cube_a):
    """Test OlapCube refresh_cube() updates last_refreshed_at."""
    before_refresh = timezone.now()
    olap_cube_a.refresh_cube()
    olap_cube_a.refresh_from_db()
    assert olap_cube_a.last_refreshed_at is not None
    assert olap_cube_a.last_refreshed_at >= before_refresh


# ---------------------------------------------------------------------------
# 2. PivotAnalysisView Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_pivot_view_creation_and_autonumber(pivot_view_a):
    """Test PivotAnalysisView creation, BPIV- prefix, and str."""
    assert pivot_view_a.pk is not None
    assert pivot_view_a.NUMBER_PREFIX == "BPIV"
    assert pivot_view_a.number.startswith("BPIV-")
    assert str(pivot_view_a) == f"{pivot_view_a.name} ({pivot_view_a.number})"
    assert pivot_view_a.get_absolute_url() == f"/bi/olap/pivots/{pivot_view_a.pk}/"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_dimensions_and_measures(tenant_a, olap_cube_a, admin_user):
    """Test PivotAnalysisView row_dimensions, column_dimensions, selected_measures, drill_through."""
    pivot = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Regional Margin Matrix",
        slug="regional-margin-matrix",
        row_dimensions=["Region", "Country"],
        column_dimensions=["FiscalYear", "Quarter"],
        selected_measures=["GrossRevenue", "NetMargin"],
        filters_json=[{"field": "FiscalYear", "operator": "eq", "value": "2026"}],
        drill_through_enabled=True,
        drill_through_target="accounting:journal_entry_list",
        show_row_subtotals=True,
        show_col_subtotals=False,
        show_grand_totals=True,
        created_by=admin_user,
    )
    assert pivot.row_dimensions == ["Region", "Country"]
    assert pivot.column_dimensions == ["FiscalYear", "Quarter"]
    assert pivot.selected_measures == ["GrossRevenue", "NetMargin"]
    assert pivot.measures_selection == ["GrossRevenue", "NetMargin"]
    assert pivot.drill_through_enabled is True
    assert pivot.drill_through_target == "accounting:journal_entry_list"
    assert pivot.show_row_subtotals is True
    assert pivot.show_col_subtotals is False


@pytest.mark.django_db
def test_olapanalysis_pivot_view_status_and_totals_choices(tenant_a, olap_cube_a, admin_user):
    """Test PivotAnalysisView status choices and total_position choices."""
    status_keys = _olapanalysis_choice_keys(PivotAnalysisView.STATUS_CHOICES)
    assert "active" in status_keys
    assert "draft" in status_keys
    assert "archived" in status_keys

    pos_keys = _olapanalysis_choice_keys(PivotAnalysisView.TOTAL_POSITION_CHOICES)
    assert "bottom_right" in pos_keys
    assert "top_left" in pos_keys
    assert "none" in pos_keys

    pivot = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Draft Top-Left Pivot",
        slug="draft-top-left-pivot",
        status="draft",
        total_position="top_left",
        created_by=admin_user,
    )
    assert pivot.status == "draft"
    assert pivot.total_position == "top_left"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_slug_uniqueness_per_tenant(tenant_a, olap_cube_a, admin_user):
    """Test PivotAnalysisView slug uniqueness per tenant."""
    PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Unique Pivot",
        slug="unique-pivot-slug",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PivotAnalysisView.objects.create(
                tenant=tenant_a,
                cube=olap_cube_a,
                name="Another Unique Pivot",
                slug="unique-pivot-slug",
                created_by=admin_user,
            )


@pytest.mark.django_db
def test_olapanalysis_pivot_view_cross_tenant_slug_allowance(
    tenant_a, tenant_b, olap_cube_a, olap_cube_b, admin_user, admin_user_b
):
    """Test that identical PivotAnalysisView slugs are allowed across tenants."""
    pv_a = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Corporate Pivot",
        slug="corporate-shared-pivot",
        created_by=admin_user,
    )
    pv_b = PivotAnalysisView.objects.create(
        tenant=tenant_b,
        cube=olap_cube_b,
        name="Corporate Pivot",
        slug="corporate-shared-pivot",
        created_by=admin_user_b,
    )
    assert pv_a.slug == pv_b.slug
    assert pv_a.tenant != pv_b.tenant


@pytest.mark.django_db
def test_olapanalysis_pivot_view_auto_slug_generation(tenant_a, olap_cube_a, admin_user):
    """Test blank slug auto-population in PivotAnalysisView."""
    pivot = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Quarterly Operational Matrix",
        slug="",
        created_by=admin_user,
    )
    assert pivot.slug == "quarterly-operational-matrix"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_cascade_on_cube_delete(tenant_a, admin_user):
    """Test deleting OlapCube cascades to delete associated PivotAnalysisView."""
    cube = OlapCube.objects.create(
        tenant=tenant_a,
        name="Cascade Test Cube",
        slug="cascade-test-cube",
        created_by=admin_user,
    )
    pivot = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=cube,
        name="Dependent Pivot View",
        slug="dependent-pivot-view",
        created_by=admin_user,
    )
    pivot_id = pivot.id
    cube.delete()
    assert not PivotAnalysisView.objects.filter(id=pivot_id).exists()


# ---------------------------------------------------------------------------
# 3. WhatIfScenario Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_scenario_creation_and_autonumber(what_if_scenario_a):
    """Test WhatIfScenario creation, BWIF- prefix, and str."""
    assert what_if_scenario_a.pk is not None
    assert what_if_scenario_a.NUMBER_PREFIX == "BWIF"
    assert what_if_scenario_a.number.startswith("BWIF-")
    assert str(what_if_scenario_a) == f"{what_if_scenario_a.name} ({what_if_scenario_a.number})"
    assert what_if_scenario_a.get_absolute_url() == f"/bi/olap/scenarios/{what_if_scenario_a.pk}/"


@pytest.mark.django_db
def test_olapanalysis_scenario_variance_calculation_on_save(tenant_a, olap_cube_a, admin_user):
    """Test total_variance_amount is automatically computed on save as adjusted - baseline."""
    scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Variance Test Scenario",
        slug="variance-test-scenario",
        total_baseline_amount=Decimal("50000.00"),
        total_adjusted_amount=Decimal("65000.00"),
        created_by=admin_user,
    )
    assert scenario.total_variance_amount == Decimal("15000.00")

    scenario.total_adjusted_amount = Decimal("42000.00")
    scenario.save()
    assert scenario.total_variance_amount == Decimal("-8000.00")


@pytest.mark.django_db
def test_olapanalysis_scenario_status_choices(tenant_a, olap_cube_a, admin_user):
    """Test WhatIfScenario status choices."""
    keys = _olapanalysis_choice_keys(WhatIfScenario.STATUS_CHOICES)
    assert "draft" in keys
    assert "simulated" in keys
    assert "approved" in keys
    assert "committed" in keys
    assert "archived" in keys

    scen = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Simulated Scenario",
        slug="simulated-scenario",
        status="simulated",
        created_by=admin_user,
    )
    assert scen.status == "simulated"


@pytest.mark.django_db
def test_olapanalysis_scenario_disaggregation_choices(tenant_a, olap_cube_a, admin_user):
    """Test WhatIfScenario default_disaggregation choices."""
    keys = _olapanalysis_choice_keys(WhatIfScenario.DEFAULT_DISAGGREGATION_CHOICES)
    assert "pro_rata" in keys
    assert "equal" in keys
    assert "delta" in keys

    scen = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Delta Splash Scenario",
        slug="delta-splash-scenario",
        default_disaggregation="delta",
        created_by=admin_user,
    )
    assert scen.default_disaggregation == "delta"


@pytest.mark.django_db
def test_olapanalysis_scenario_relations_and_indexes(tenant_a, olap_cube_a, admin_user):
    """Test WhatIfScenario relations with Budget, FiscalPeriod, and driver parameters."""
    period = FiscalPeriod.objects.create(
        tenant=tenant_a,
        name="2026-Q1",
        period_type="quarter",
        start_date="2026-01-01",
        end_date="2026-03-31",
        status="open",
    )
    budget = Budget.objects.create(
        tenant=tenant_a,
        name="FY2026 Operating Budget",
        fiscal_period=period,
        version="original",
        status="draft",
    )
    scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        baseline_budget=budget,
        fiscal_period=period,
        name="Budget Linked Simulation",
        slug="budget-linked-sim",
        driver_parameters={"growth_rate": 0.08, "inflation": 0.03},
        created_by=admin_user,
    )
    assert scenario.baseline_budget == budget
    assert scenario.fiscal_period == period
    assert scenario.driver_parameters["growth_rate"] == 0.08
    assert scenario.cube == olap_cube_a


@pytest.mark.django_db
def test_olapanalysis_scenario_slug_uniqueness_per_tenant(tenant_a, olap_cube_a, admin_user):
    """Test WhatIfScenario slug uniqueness per tenant."""
    WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Unique Scenario",
        slug="unique-scenario-slug",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WhatIfScenario.objects.create(
                tenant=tenant_a,
                cube=olap_cube_a,
                name="Another Unique Scenario",
                slug="unique-scenario-slug",
                created_by=admin_user,
            )


@pytest.mark.django_db
def test_olapanalysis_scenario_cross_tenant_slug_allowance(
    tenant_a, tenant_b, olap_cube_a, olap_cube_b, admin_user, admin_user_b
):
    """Test that identical WhatIfScenario slugs are allowed across tenants."""
    sc_a = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Shared Scenario",
        slug="shared-scenario-slug",
        created_by=admin_user,
    )
    sc_b = WhatIfScenario.objects.create(
        tenant=tenant_b,
        cube=olap_cube_b,
        name="Shared Scenario",
        slug="shared-scenario-slug",
        created_by=admin_user_b,
    )
    assert sc_a.slug == sc_b.slug
    assert sc_a.tenant != sc_b.tenant


@pytest.mark.django_db
def test_olapanalysis_scenario_auto_slug_generation(tenant_a, olap_cube_a, admin_user):
    """Test blank slug auto-population in WhatIfScenario."""
    scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Expansion Scenario Plan 2026",
        slug="",
        created_by=admin_user,
    )
    assert scenario.slug == "expansion-scenario-plan-2026"


# ---------------------------------------------------------------------------
# 4. ScenarioWritebackCell Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_creation_and_autonumber(writeback_cell_a):
    """Test ScenarioWritebackCell creation, BWBC- prefix, and str representation."""
    assert writeback_cell_a.pk is not None
    assert writeback_cell_a.NUMBER_PREFIX == "BWBC"
    assert writeback_cell_a.number.startswith("BWBC-")
    assert str(writeback_cell_a) == f"{writeback_cell_a.number}"
    assert writeback_cell_a.get_absolute_url() == f"/bi/olap/writeback-cells/{writeback_cell_a.pk}/"


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_coordinate_keys_and_values(writeback_cell_a):
    """Test coordinate_keys_json and amount aliases."""
    assert writeback_cell_a.cell_coordinates == {"dept": "Sales", "period": "2026-Q1"}
    assert writeback_cell_a.coordinate_keys_json == {"dept": "Sales", "period": "2026-Q1"}
    assert writeback_cell_a.baseline_value == Decimal("10000.00")
    assert writeback_cell_a.baseline_amount == Decimal("10000.00")
    assert writeback_cell_a.adjusted_value == Decimal("12000.00")
    assert writeback_cell_a.simulated_amount == Decimal("12000.00")
    assert writeback_cell_a.variance_amount == Decimal("2000.00")
    assert writeback_cell_a.adjustment_delta == Decimal("2000.00")
    assert writeback_cell_a.spread_method in ["direct_leaf", "pro_rata", "equal", "delta", "absolute"]
    assert writeback_cell_a.adjustment_method == writeback_cell_a.spread_method


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_variance_auto_calc_on_save(tenant_a, what_if_scenario_a, admin_user):
    """Test variance_amount is auto-calculated on save as adjusted_value - baseline_value."""
    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        cell_coordinates={"period": "2026-Q2"},
        baseline_value=Decimal("8000.00"),
        adjusted_value=Decimal("9500.00"),
        created_by=admin_user,
    )
    assert cell.variance_amount == Decimal("1500.00")

    cell.adjusted_value = Decimal("7200.00")
    cell.save()
    assert cell.variance_amount == Decimal("-800.00")


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_adjustment_method_choices(tenant_a, what_if_scenario_a, admin_user):
    """Test ScenarioWritebackCell spread_method / adjustment_method choices."""
    keys = _olapanalysis_choice_keys(ScenarioWritebackCell.SPREAD_METHOD_CHOICES)
    assert "direct_leaf" in keys
    assert "pro_rata" in keys
    assert "equal" in keys
    assert "delta" in keys

    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        cell_coordinates={"dept": "Marketing"},
        baseline_value=Decimal("5000.00"),
        adjusted_value=Decimal("6000.00"),
        spread_method="equal",
        created_by=admin_user,
    )
    assert cell.spread_method == "equal"
    assert cell.adjustment_method == "equal"


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_foreign_keys_and_committed(tenant_a, what_if_scenario_a, admin_user):
    """Test ScenarioWritebackCell relations to GLAccount, OrgUnit, and is_committed flag."""
    gl_account = GLAccount.objects.create(
        tenant=tenant_a,
        code="6010",
        name="Travel & Entertainment",
        account_type="expense",
    )
    org_unit = OrgUnit.objects.create(
        tenant=tenant_a,
        name="Sales Division",
        kind="department",
    )
    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        gl_account=gl_account,
        org_unit=org_unit,
        cell_coordinates={"dept": "Sales", "account": "6010"},
        baseline_value=Decimal("25000.00"),
        adjusted_value=Decimal("30000.00"),
        is_committed=True,
        commentary="Approved by board for Q3 expansion",
        created_by=admin_user,
    )
    assert cell.gl_account == gl_account
    assert cell.org_unit == org_unit
    assert cell.is_committed is True
    assert cell.commentary == "Approved by board for Q3 expansion"


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_cascade_on_scenario_delete(tenant_a, olap_cube_a, admin_user):
    """Test deleting WhatIfScenario cascades to delete associated ScenarioWritebackCell."""
    scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Temporary Scenario",
        slug="temporary-scenario",
        created_by=admin_user,
    )
    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=scenario,
        cell_coordinates={"key": "val"},
        baseline_value=Decimal("100.00"),
        adjusted_value=Decimal("200.00"),
        created_by=admin_user,
    )
    cell_id = cell.id
    scenario.delete()
    assert not ScenarioWritebackCell.objects.filter(id=cell_id).exists()

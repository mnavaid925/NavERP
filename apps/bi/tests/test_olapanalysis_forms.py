"""Unit tests for Sub-module 10.12 OLAP & Multidimensional Analysis forms.

Forms covered:
- OlapCubeForm
- PivotAnalysisViewForm
- WhatIfScenarioForm
- ScenarioWritebackCellForm
"""
import json
from decimal import Decimal

import pytest
from django.utils.text import slugify

from apps.accounting.models import Budget, FiscalPeriod, GLAccount
from apps.bi.forms.OlapAnalysis import (
    OlapCubeForm,
    PivotAnalysisViewForm,
    ScenarioWritebackCellForm,
    WhatIfScenarioForm,
)
from apps.bi.models.OlapAnalysis import (
    OlapCube,
    PivotAnalysisView,
    ScenarioWritebackCell,
    WhatIfScenario,
)
from apps.core.models import OrgUnit


def _olapanalysis_valid_dims_json():
    """Helper returning a standard JSON-encoded dimensions configuration."""
    return json.dumps([
        {"name": "FiscalPeriod", "type": "time", "levels": ["Year", "Quarter", "Month"]},
        {"name": "Department", "type": "organization", "levels": ["Division", "Department"]},
    ])


def _olapanalysis_valid_measures_json():
    """Helper returning a standard JSON-encoded measures configuration."""
    return json.dumps([
        {"name": "ActualRevenue", "aggregation": "sum", "format": "$#,##0.00"},
        {"name": "OperatingCost", "aggregation": "sum", "format": "$#,##0.00"},
    ])


def _olapanalysis_valid_aggregations_json():
    """Helper returning a standard JSON-encoded pre-aggregations configuration."""
    return json.dumps([
        ["FiscalPeriod", "Department"],
    ])


# ---------------------------------------------------------------------------
# 1. OlapCubeForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_cube_form_valid_submission(tenant_a):
    """Test valid OlapCubeForm submission creates an OlapCube instance with JSON configs."""
    form_data = {
        "name": "Global Sales & Profitability Cube",
        "storage_mode": "rolap",
        "status": "active",
        "time_intelligence_enabled": True,
        "cache_ttl_minutes": 120,
        "dimensions_config_raw": _olapanalysis_valid_dims_json(),
        "measures_config_raw": _olapanalysis_valid_measures_json(),
        "aggregations_config_raw": _olapanalysis_valid_aggregations_json(),
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    cube = form.save(commit=False)
    cube.tenant = tenant_a
    cube.save()

    assert cube.pk is not None
    assert cube.name == "Global Sales & Profitability Cube"
    assert cube.slug == "global-sales-profitability-cube"
    assert cube.storage_mode == "rolap"
    assert cube.status == "active"
    assert len(cube.dimensions_config) == 2
    assert cube.dimensions_config[0]["name"] == "FiscalPeriod"
    assert len(cube.measures_config) == 2
    assert cube.measures_config[0]["name"] == "ActualRevenue"
    assert len(cube.aggregations_config) == 1
    assert cube.aggregations_config[0] == ["FiscalPeriod", "Department"]


@pytest.mark.django_db
def test_olapanalysis_cube_form_system_field_exclusion(tenant_a):
    """Test system and read-only fields are excluded from OlapCubeForm fields."""
    form = OlapCubeForm(tenant=tenant_a)
    excluded = ["tenant", "number", "last_refreshed_at", "created_at", "updated_at", "created_by"]
    for field in excluded:
        assert field not in form.fields, f"System field '{field}' must not be in form.fields"


@pytest.mark.django_db
def test_olapanalysis_cube_form_blank_slug_population(tenant_a):
    """Test blank slug is automatically populated from name during clean."""
    form_data = {
        "name": "Acme Regional Performance Cube",
        "slug": "",
        "storage_mode": "hybrid",
        "status": "draft",
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "acme-regional-performance-cube"

    cube = form.save(commit=False)
    assert cube.slug == "acme-regional-performance-cube"


@pytest.mark.django_db
def test_olapanalysis_cube_form_negative_invalid_json(tenant_a):
    """Test negative/malformed JSON in raw fields produces field errors without 500."""
    form_data = {
        "name": "Invalid JSON Cube",
        "storage_mode": "rolap",
        "status": "draft",
        "dimensions_config_raw": "{broken json: [",
        "measures_config_raw": "[broken measures",
        "aggregations_config_raw": "invalid: json",
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dimensions_config_raw" in form.errors
    assert "measures_config_raw" in form.errors
    assert "aggregations_config_raw" in form.errors


@pytest.mark.django_db
def test_olapanalysis_cube_form_non_list_json(tenant_a):
    """Test JSON that parses into a dict instead of a list raises validation error."""
    form_data = {
        "name": "Non-Array JSON Cube",
        "storage_mode": "rolap",
        "status": "draft",
        "dimensions_config_raw": json.dumps({"FiscalPeriod": "time"}),
        "measures_config_raw": json.dumps({"Revenue": "sum"}),
        "aggregations_config_raw": json.dumps({"FiscalPeriod": "Department"}),
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dimensions_config_raw" in form.errors
    assert "measures_config_raw" in form.errors
    assert "aggregations_config_raw" in form.errors
    assert "must be a JSON array" in str(form.errors["dimensions_config_raw"])
    assert "must be a JSON array" in str(form.errors["measures_config_raw"])
    assert "must be a JSON array" in str(form.errors["aggregations_config_raw"])


@pytest.mark.django_db
def test_olapanalysis_cube_form_missing_required_name(tenant_a):
    """Test missing required 'name' field fails validation."""
    form_data = {
        "storage_mode": "rolap",
        "status": "draft",
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_olapanalysis_cube_form_reject_foreign(
    tenant_a,
    semantic_model_b,
    warehouse_table_b,
    drill_hierarchy_b,
):
    """Test cross-tenant foreign keys are rejected via reject_foreign."""
    form_data = {
        "name": "Cross-Tenant Infiltration Cube",
        "storage_mode": "rolap",
        "semantic_model": semantic_model_b.pk,
        "warehouse_table": warehouse_table_b.pk,
        "default_hierarchy": drill_hierarchy_b.pk,
        "status": "draft",
    }
    form = OlapCubeForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "warehouse_table" in form.errors
    assert "default_hierarchy" in form.errors


@pytest.mark.django_db
def test_olapanalysis_cube_form_edit_mode_initial_json(tenant_a, olap_cube_a):
    """Test editing an existing OlapCube populates JSON fields with formatted initial data."""
    form = OlapCubeForm(instance=olap_cube_a, tenant=tenant_a)
    assert form.fields["dimensions_config_raw"].initial is not None
    dims_data = json.loads(form.fields["dimensions_config_raw"].initial)
    assert isinstance(dims_data, list)
    assert len(dims_data) == 2

    assert form.fields["measures_config_raw"].initial is not None
    measures_data = json.loads(form.fields["measures_config_raw"].initial)
    assert isinstance(measures_data, list)
    assert len(measures_data) == 2


# ---------------------------------------------------------------------------
# 2. PivotAnalysisViewForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_valid_submission(tenant_a, olap_cube_a):
    """Test valid PivotAnalysisViewForm submission creates a PivotAnalysisView instance."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Executive P&L Cross-Tab Matrix",
        "row_dimensions_raw": json.dumps(["OrgUnit", "GLAccount"]),
        "column_dimensions_raw": json.dumps(["FiscalPeriod"]),
        "selected_measures_raw": json.dumps(["Actual Amount", "Budget Amount"]),
        "filters_json_raw": json.dumps([{"field": "FiscalPeriod.Year", "operator": "eq", "value": "2026"}]),
        "show_row_subtotals": True,
        "show_col_subtotals": True,
        "show_grand_totals": True,
        "total_position": "bottom_right",
        "drill_through_enabled": True,
        "drill_through_target": "bi:olap_cube_list",
        "status": "active",
        "is_favorite": True,
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    view = form.save(commit=False)
    view.tenant = tenant_a
    view.save()

    assert view.pk is not None
    assert view.cube == olap_cube_a
    assert view.name == "Executive P&L Cross-Tab Matrix"
    assert view.slug == "executive-pl-cross-tab-matrix"
    assert view.row_dimensions == ["OrgUnit", "GLAccount"]
    assert view.column_dimensions == ["FiscalPeriod"]
    assert view.selected_measures == ["Actual Amount", "Budget Amount"]
    assert len(view.filters_json) == 1
    assert view.is_favorite is True


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_system_field_exclusion(tenant_a):
    """Test system and read-only fields are excluded from PivotAnalysisViewForm."""
    form = PivotAnalysisViewForm(tenant=tenant_a)
    excluded = ["tenant", "number", "created_at", "updated_at", "created_by"]
    for field in excluded:
        assert field not in form.fields, f"System field '{field}' must not be in form.fields"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_reject_foreign_cube(tenant_a, olap_cube_b):
    """Test tenant scoping & cross-tenant rejection for cube."""
    form_data = {
        "cube": olap_cube_b.pk,
        "name": "Cross-Tenant Pivot View",
        "status": "active",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cube" in form.errors


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_blank_slug_population(tenant_a, olap_cube_a):
    """Test blank slug auto-population in PivotAnalysisViewForm."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Monthly Expense By Cost Center",
        "slug": "",
        "status": "draft",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "monthly-expense-by-cost-center"

    view = form.save(commit=False)
    assert view.slug == "monthly-expense-by-cost-center"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_drill_through_target_valid(tenant_a, olap_cube_a):
    """Test valid reverse target passes clean_drill_through_target."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Drill-Through Valid Target View",
        "drill_through_target": "bi:pivot_view_list",
        "status": "active",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["drill_through_target"] == "bi:pivot_view_list"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_drill_through_target_invalid(tenant_a, olap_cube_a):
    """Test invalid reverse target fails clean_drill_through_target validation."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Drill-Through Invalid Target View",
        "drill_through_target": "non_existent:route_does_not_exist",
        "status": "active",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "drill_through_target" in form.errors
    assert "could not be reversed" in str(form.errors["drill_through_target"])


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_conditional_formatting_json(tenant_a, olap_cube_a):
    """Test conditional_formatting_raw accepts valid JSON dict/array and rejects invalid JSON."""
    valid_rules = [
        {"rule": "variance < 0", "color": "#ef4444", "background": "#fee2e2"},
        {"rule": "variance >= 0", "color": "#16a34a", "background": "#dcfce7"},
    ]
    form_data_valid = {
        "cube": olap_cube_a.pk,
        "name": "Conditional Formatting Pivot",
        "conditional_formatting_raw": json.dumps(valid_rules),
        "status": "active",
    }
    form_valid = PivotAnalysisViewForm(data=form_data_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors
    assert len(form_valid.cleaned_data["conditional_formatting_raw"]) == 2

    form_data_invalid = {
        "cube": olap_cube_a.pk,
        "name": "Broken Formatting Pivot",
        "conditional_formatting_raw": "invalid: json format {",
        "status": "active",
    }
    form_invalid = PivotAnalysisViewForm(data=form_data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "conditional_formatting_raw" in form_invalid.errors


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_invalid_dimensions_json(tenant_a, olap_cube_a):
    """Test invalid JSON in dimensional axis fields produces field errors."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Malformed Matrix Dimensions",
        "row_dimensions_raw": "{broken: json",
        "column_dimensions_raw": "[broken",
        "selected_measures_raw": "{not an array: true",
        "filters_json_raw": "[bad filter json",
        "status": "draft",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "row_dimensions_raw" in form.errors
    assert "column_dimensions_raw" in form.errors
    assert "selected_measures_raw" in form.errors
    assert "filters_json_raw" in form.errors


@pytest.mark.django_db
def test_olapanalysis_pivot_view_form_alias_and_direct_list_support(tenant_a, olap_cube_a):
    """Test form handles row_dimensions, column_dimensions, measures_selection passed as lists."""
    form_data = {
        "cube": olap_cube_a.pk,
        "name": "Direct Python Lists Pivot",
        "row_dimensions": ["Department", "Region"],
        "column_dimensions": ["FiscalYear"],
        "measures_selection": ["OperatingProfit"],
        "status": "active",
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["row_dimensions_raw"] == ["Department", "Region"]
    assert form.cleaned_data["column_dimensions_raw"] == ["FiscalYear"]
    assert form.cleaned_data["selected_measures_raw"] == ["OperatingProfit"]


# ---------------------------------------------------------------------------
# 3. WhatIfScenarioForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_valid(tenant_a, olap_cube_a):
    """Test valid WhatIfScenarioForm submission creates a WhatIfScenario instance."""
    form_data = {
        "name": "FY2027 Optimistic Market Expansion",
        "cube": olap_cube_a.pk,
        "default_disaggregation": "pro_rata",
        "status": "draft",
        "driver_parameters_raw": json.dumps({
            "revenue_growth_pct": 12.5,
            "cost_inflation_pct": 3.0,
            "headcount_multiplier": 1.10,
        }),
    }
    form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    scenario = form.save(commit=False)
    scenario.tenant = tenant_a
    scenario.save()

    assert scenario.pk is not None
    assert scenario.name == "FY2027 Optimistic Market Expansion"
    assert scenario.slug == "fy2027-optimistic-market-expansion"
    assert scenario.cube == olap_cube_a
    assert scenario.status == "draft"
    assert scenario.driver_parameters["revenue_growth_pct"] == 12.5
    assert scenario.default_disaggregation == "pro_rata"


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_system_field_exclusion(tenant_a):
    """Test system and computed financial ledger fields are excluded from WhatIfScenarioForm."""
    form = WhatIfScenarioForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "total_baseline_amount",
        "total_adjusted_amount",
        "total_variance_amount",
        "is_committed",
        "committed_at",
        "committed_by",
        "committed_budget_line",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"System field '{field}' must not be in form.fields"


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_lifecycle_guard_committed(tenant_a, olap_cube_a):
    """Test lifecycle guard: selecting status='committed' fails form validation."""
    # Ensure 'committed' is removed from the choices
    form = WhatIfScenarioForm(tenant=tenant_a)
    status_choice_keys = [k for k, _ in form.fields["status"].choices]
    assert "committed" not in status_choice_keys

    # Submission with status='committed' must be rejected
    form_data = {
        "name": "Directly Committed Scenario",
        "cube": olap_cube_a.pk,
        "status": "committed",
    }
    bound_form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "status" in bound_form.errors


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_reject_foreign(tenant_a, olap_cube_b):
    """Test cross-tenant cube foreign key rejection in WhatIfScenarioForm."""
    form_data = {
        "name": "Cross-Tenant Simulation Scenario",
        "cube": olap_cube_b.pk,
        "status": "draft",
    }
    form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cube" in form.errors


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_blank_slug(tenant_a, olap_cube_a):
    """Test blank slug auto-population in WhatIfScenarioForm."""
    form_data = {
        "name": "Simulated Cost Restructuring 2026",
        "slug": "",
        "cube": olap_cube_a.pk,
        "status": "draft",
    }
    form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["slug"] == "simulated-cost-restructuring-2026"

    scenario = form.save(commit=False)
    assert scenario.slug == "simulated-cost-restructuring-2026"


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_missing_required_name(tenant_a):
    """Test missing name fails validation."""
    form_data = {
        "status": "draft",
    }
    form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_olapanalysis_what_if_scenario_form_driver_parameters_json(tenant_a, olap_cube_a):
    """Test driver_parameters_raw validation for invalid JSON and non-dict JSON."""
    # Invalid JSON syntax
    form_data_invalid = {
        "name": "Invalid Driver Scenario",
        "cube": olap_cube_a.pk,
        "status": "draft",
        "driver_parameters_raw": "{broken json",
    }
    form_invalid = WhatIfScenarioForm(data=form_data_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "driver_parameters_raw" in form_invalid.errors

    # Non-dict JSON (array)
    form_data_list = {
        "name": "List Driver Scenario",
        "cube": olap_cube_a.pk,
        "status": "draft",
        "driver_parameters_raw": json.dumps([1, 2, 3]),
    }
    form_list = WhatIfScenarioForm(data=form_data_list, tenant=tenant_a)
    assert not form_list.is_valid()
    assert "driver_parameters_raw" in form_list.errors
    assert "must be a JSON object" in str(form_list.errors["driver_parameters_raw"])


# ---------------------------------------------------------------------------
# 4. ScenarioWritebackCellForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_valid(tenant_a, what_if_scenario_a):
    """Test valid ScenarioWritebackCellForm submission creates an adjustment instance."""
    form_data = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "15000.00",
        "adjusted_value": "18000.00",
        "spread_method": "direct_leaf",
        "commentary": "Q1 Revenue projection top-up",
        "cell_coordinates_raw": json.dumps({"dept": "Sales", "period": "2026-Q1"}),
    }
    form = ScenarioWritebackCellForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    cell = form.save(commit=False)
    cell.tenant = tenant_a
    cell.save()

    assert cell.pk is not None
    assert cell.scenario == what_if_scenario_a
    assert cell.baseline_value == Decimal("15000.00")
    assert cell.adjusted_value == Decimal("18000.00")
    assert cell.variance_amount == Decimal("3000.00")
    assert cell.spread_method == "direct_leaf"
    assert cell.cell_coordinates == {"dept": "Sales", "period": "2026-Q1"}


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_alias_submission(tenant_a, what_if_scenario_a):
    """Test ScenarioWritebackCellForm accepts alias field names (coordinate_keys_raw, baseline_amount, etc)."""
    form_data = {
        "scenario": what_if_scenario_a.pk,
        "baseline_amount": "20000.00",
        "simulated_amount": "25000.00",
        "adjustment_method": "pro_rata",
        "coordinate_keys_raw": json.dumps({"region": "EMEA", "segment": "Enterprise"}),
        "commentary": "Pro-rata enterprise reallocation",
    }
    form = ScenarioWritebackCellForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    cell = form.save(commit=False)
    cell.tenant = tenant_a
    cell.save()

    assert cell.pk is not None
    assert cell.baseline_value == Decimal("20000.00")
    assert cell.adjusted_value == Decimal("25000.00")
    assert cell.variance_amount == Decimal("5000.00")
    assert cell.spread_method == "pro_rata"
    assert cell.cell_coordinates == {"region": "EMEA", "segment": "Enterprise"}


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_system_field_exclusion(tenant_a):
    """Test system and computed/locked fields are excluded from ScenarioWritebackCellForm."""
    form = ScenarioWritebackCellForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "variance_amount",
        "adjustment_delta",
        "is_committed",
        "committed_at",
        "committed_budget_line",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in excluded:
        assert field not in form.fields, f"System field '{field}' must not be in form.fields"


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_reject_foreign(tenant_a, what_if_scenario_b):
    """Test tenant scoping & cross-tenant rejection for scenario."""
    form_data = {
        "scenario": what_if_scenario_b.pk,
        "baseline_value": "1000.00",
        "adjusted_value": "1500.00",
        "spread_method": "direct_leaf",
    }
    form = ScenarioWritebackCellForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "scenario" in form.errors


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_committed_scenario_exclusion(tenant_a, admin_user, olap_cube_a):
    """Test scenario queryset excludes committed scenarios."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Committed Historical Budget",
        slug="committed-historical-budget",
        status="committed",
        created_by=admin_user,
    )
    active_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Active Working Simulation",
        slug="active-working-simulation",
        status="draft",
        created_by=admin_user,
    )

    form = ScenarioWritebackCellForm(tenant=tenant_a)
    scenario_choices = list(form.fields["scenario"].queryset)
    assert committed_scenario not in scenario_choices
    assert active_scenario in scenario_choices


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_clean_scenario_committed_guard(tenant_a, admin_user, olap_cube_a):
    """Test clean_scenario validation error when a committed scenario is submitted."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Locked Budget Scenario",
        slug="locked-budget-scenario",
        status="committed",
        created_by=admin_user,
    )
    form_data = {
        "scenario": committed_scenario.pk,
        "baseline_value": "5000.00",
        "adjusted_value": "6000.00",
        "spread_method": "direct_leaf",
    }
    form = ScenarioWritebackCellForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "scenario" in form.errors


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_form_invalid_coordinates_json(tenant_a, what_if_scenario_a):
    """Test invalid or non-dict JSON in coordinate fields produces validation errors."""
    # Malformed JSON
    form_data_broken = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "5000.00",
        "adjusted_value": "6000.00",
        "spread_method": "direct_leaf",
        "cell_coordinates_raw": "{invalid json: [",
    }
    form_broken = ScenarioWritebackCellForm(data=form_data_broken, tenant=tenant_a)
    assert not form_broken.is_valid()
    assert "cell_coordinates_raw" in form_broken.errors

    # Malformed JSON via coordinate_keys_raw alias
    form_data_broken_alias = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "5000.00",
        "adjusted_value": "6000.00",
        "spread_method": "direct_leaf",
        "coordinate_keys_raw": "{broken coordinates",
    }
    form_broken_alias = ScenarioWritebackCellForm(data=form_data_broken_alias, tenant=tenant_a)
    assert not form_broken_alias.is_valid()
    assert (
        "coordinate_keys_raw" in form_broken_alias.errors
        or "cell_coordinates_raw" in form_broken_alias.errors
    )

    # Non-dict JSON (array)
    form_data_array = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "5000.00",
        "adjusted_value": "6000.00",
        "spread_method": "direct_leaf",
        "cell_coordinates_raw": json.dumps(["dept", "Sales"]),
    }
    form_array = ScenarioWritebackCellForm(data=form_data_array, tenant=tenant_a)
    assert not form_array.is_valid()
    assert "cell_coordinates_raw" in form_array.errors
    assert "must be a JSON object" in str(form_array.errors["cell_coordinates_raw"])

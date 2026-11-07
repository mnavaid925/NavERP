"""Views unit tests for Sub-module 10.12 OLAP & Multidimensional Analysis (apps/bi).

Entities covered:
1. OlapCube (list, detail, create, edit, delete, refresh)
2. PivotAnalysisView (list, detail, create, edit, delete, matrix workspace)
3. WhatIfScenario (list, detail, create, edit, delete, simulate, commit)
4. ScenarioWritebackCell (list, detail, create, edit, delete, guards)
"""
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    OlapCube,
    PivotAnalysisView,
    ScenarioWritebackCell,
    WhatIfScenario,
)


def _olapanalysis_dims_payload():
    """Helper returning JSON-encoded dimensional hierarchy configuration."""
    return json.dumps([
        {"name": "Region", "type": "geography", "levels": ["Country", "State"]},
        {"name": "Time", "type": "time", "levels": ["Year", "Quarter", "Month"]},
    ])


def _olapanalysis_measures_payload():
    """Helper returning JSON-encoded measures configuration."""
    return json.dumps([
        {"name": "Revenue", "aggregation": "sum", "format": "$#,##0.00"},
        {"name": "GrossMargin", "formula": "[Revenue] - [COGS]", "format": "$#,##0.00"},
    ])


def _olapanalysis_aggregations_payload():
    """Helper returning JSON-encoded cuboid aggregations configuration."""
    return json.dumps([["Region", "Time"]])


# ===========================================================================
# 1. OlapCube Views
# ===========================================================================

@pytest.mark.django_db
def test_olapanalysis_cube_list_view(client_a, olap_cube_a):
    """Test olap_cube_list returns 200, contains expected context variables and cube record."""
    url = reverse("bi:olap_cube_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "cubes" in resp.context
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "status_choices" in resp.context
    assert "storage_mode_choices" in resp.context
    assert resp.context["total_count"] >= 1
    assert olap_cube_a.name in resp.content.decode()


@pytest.mark.django_db
def test_olapanalysis_cube_list_filters_and_search(client_a, olap_cube_a):
    """Test olap_cube_list filters by status, storage_mode, and search keyword."""
    url = reverse("bi:olap_cube_list")

    # Filter by status and storage_mode
    resp_filter = client_a.get(url, {"status": "active", "storage_mode": "molap"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["cubes"]) >= 1

    # Search keyword match
    resp_search = client_a.get(url, {"q": olap_cube_a.name[:10]})
    assert resp_search.status_code == 200
    assert len(resp_search.context["cubes"]) >= 1

    # Search non-existent keyword
    resp_empty = client_a.get(url, {"q": "NON_EXISTENT_CUBE_QUERY_XYZ"})
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["cubes"]) == 0


@pytest.mark.django_db
def test_olapanalysis_cube_create_view_get(client_a):
    """Test GET olap_cube_create renders form template with is_edit=False."""
    url = reverse("bi:olap_cube_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False


@pytest.mark.django_db
def test_olapanalysis_cube_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test POST olap_cube_create successfully persists cube with tenant isolation and autonumbering."""
    url = reverse("bi:olap_cube_create")
    payload = {
        "name": "Global Profitability & Margin Analysis",
        "description": "Enterprise profitability analysis cube",
        "storage_mode": "rolap",
        "status": "active",
        "time_intelligence_enabled": True,
        "cache_ttl_minutes": 90,
        "dimensions_config_raw": _olapanalysis_dims_payload(),
        "measures_config_raw": _olapanalysis_measures_payload(),
        "aggregations_config_raw": _olapanalysis_aggregations_payload(),
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 302
    created = OlapCube.objects.filter(tenant=tenant_a, name="Global Profitability & Margin Analysis").first()
    assert created is not None
    assert created.number.startswith("BOCB")
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert created.storage_mode == "rolap"
    assert len(created.dimensions_config) == 2
    redirect_url = reverse("bi:olap_cube_detail", kwargs={"pk": created.pk})
    assert resp.url == redirect_url


@pytest.mark.django_db
def test_olapanalysis_cube_detail_view(client_a, olap_cube_a, pivot_view_a, what_if_scenario_a):
    """Test GET olap_cube_detail returns 200 and passes cube, pivot_views, and scenarios."""
    url = reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["cube"] == olap_cube_a
    assert "pivot_views" in resp.context
    assert "scenarios" in resp.context
    assert resp.context["pivot_views_count"] >= 1
    assert resp.context["scenarios_count"] >= 1
    assert olap_cube_a.name in resp.content.decode()


@pytest.mark.django_db
def test_olapanalysis_cube_edit_view(client_a, olap_cube_a):
    """Test GET and POST olap_cube_edit updates cube configuration and redirects to detail."""
    url = reverse("bi:olap_cube_edit", kwargs={"pk": olap_cube_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["cube"] == olap_cube_a

    # POST update
    payload = {
        "name": "Acme Financial Performance Cube Updated",
        "slug": olap_cube_a.slug,
        "description": "Updated financial cube description",
        "storage_mode": "hybrid",
        "status": "active",
        "cache_ttl_minutes": 120,
        "dimensions_config_raw": _olapanalysis_dims_payload(),
        "measures_config_raw": _olapanalysis_measures_payload(),
        "aggregations_config_raw": _olapanalysis_aggregations_payload(),
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})

    olap_cube_a.refresh_from_db()
    assert olap_cube_a.name == "Acme Financial Performance Cube Updated"
    assert olap_cube_a.storage_mode == "hybrid"
    assert olap_cube_a.cache_ttl_minutes == 120


@pytest.mark.django_db
def test_olapanalysis_cube_delete_view_post_and_guard(client_a, tenant_a, admin_user):
    """Test POST olap_cube_delete deletes cube; GET returns 405 Method Not Allowed."""
    cube_to_delete = OlapCube.objects.create(
        tenant=tenant_a,
        name="Temporary Disposable Cube",
        storage_mode="rolap",
        status="draft",
        created_by=admin_user,
    )
    url = reverse("bi:olap_cube_delete", kwargs={"pk": cube_to_delete.pk})

    # GET must fail with 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert OlapCube.objects.filter(pk=cube_to_delete.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:olap_cube_list")
    assert not OlapCube.objects.filter(pk=cube_to_delete.pk).exists()


@pytest.mark.django_db
def test_olapanalysis_cube_refresh_view_post_and_guard(client_a, olap_cube_a):
    """Test POST olap_cube_refresh stamps last_refreshed_at; GET returns 405."""
    url = reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST refreshes cube
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})

    olap_cube_a.refresh_from_db()
    assert olap_cube_a.last_refreshed_at is not None
    assert (timezone.now() - olap_cube_a.last_refreshed_at).total_seconds() < 60


# ===========================================================================
# 2. PivotAnalysisView Views
# ===========================================================================

@pytest.mark.django_db
def test_olapanalysis_pivot_view_list_view(client_a, pivot_view_a, olap_cube_a):
    """Test pivot_view_list returns 200, context keys, and supports filtering by cube and status."""
    url = reverse("bi:pivot_view_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert ("views" in resp.context) or ("pivot_views" in resp.context)
    assert "total_count" in resp.context
    assert "active_count" in resp.context
    assert "cubes" in resp.context
    assert "status_choices" in resp.context
    assert pivot_view_a.name in resp.content.decode()

    # Filter by cube and status
    resp_filtered = client_a.get(url, {"cube": olap_cube_a.pk, "status": "active"})
    assert resp_filtered.status_code == 200
    filtered_list = resp_filtered.context.get("views", resp_filtered.context.get("pivot_views"))
    assert len(filtered_list) >= 1


@pytest.mark.django_db
def test_olapanalysis_pivot_view_create_view(client_a, tenant_a, olap_cube_a):
    """Test GET and POST pivot_view_create persists a new pivot view and redirects to matrix workspace."""
    url = reverse("bi:pivot_view_create")

    # GET with pre-selected cube
    resp_get = client_a.get(url, {"cube": olap_cube_a.pk})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid pivot view
    payload = {
        "cube": olap_cube_a.pk,
        "name": "Global Operating Expenses Breakdown",
        "description": "Hierarchical pivot cross-tab",
        "row_dimensions_raw": json.dumps(["Department", "CostCenter"]),
        "column_dimensions_raw": json.dumps(["FiscalPeriod"]),
        "selected_measures_raw": json.dumps(["Actual Amount", "Budget Amount"]),
        "total_position": "bottom_right",
        "show_row_subtotals": True,
        "show_col_subtotals": True,
        "show_grand_totals": True,
        "drill_through_enabled": True,
        "status": "active",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = PivotAnalysisView.objects.filter(tenant=tenant_a, name="Global Operating Expenses Breakdown").first()
    assert created is not None
    assert created.number.startswith("BPIV")
    assert created.tenant == tenant_a
    assert created.cube == olap_cube_a
    assert resp_post.url == reverse("bi:pivot_view_matrix", kwargs={"pk": created.pk})


@pytest.mark.django_db
def test_olapanalysis_pivot_view_detail_view(client_a, pivot_view_a):
    """Test GET pivot_view_detail returns 200 and displays pivot view summary."""
    url = reverse("bi:pivot_view_detail", kwargs={"pk": pivot_view_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert ("view" in resp.context) or ("pivot_view" in resp.context)
    assert pivot_view_a.name in resp.content.decode()


@pytest.mark.django_db
def test_olapanalysis_pivot_view_edit_view(client_a, pivot_view_a):
    """Test GET and POST pivot_view_edit updates pivot configuration and redirects to detail."""
    url = reverse("bi:pivot_view_edit", kwargs={"pk": pivot_view_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = {
        "cube": pivot_view_a.cube.pk,
        "name": "Acme Department Expense Matrix Updated",
        "slug": pivot_view_a.slug,
        "description": "Updated matrix view description",
        "row_dimensions_raw": json.dumps(["Department"]),
        "column_dimensions_raw": json.dumps(["FiscalPeriod"]),
        "selected_measures_raw": json.dumps(["Actual Amount"]),
        "total_position": "top_left",
        "status": "active",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:pivot_view_detail", kwargs={"pk": pivot_view_a.pk})

    pivot_view_a.refresh_from_db()
    assert pivot_view_a.name == "Acme Department Expense Matrix Updated"
    assert pivot_view_a.total_position == "top_left"


@pytest.mark.django_db
def test_olapanalysis_pivot_view_delete_view_post_and_guard(client_a, tenant_a, olap_cube_a):
    """Test POST pivot_view_delete removes view; GET returns 405 Method Not Allowed."""
    view_to_delete = PivotAnalysisView.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Temporary Pivot To Delete",
        status="draft",
    )
    url = reverse("bi:pivot_view_delete", kwargs={"pk": view_to_delete.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert PivotAnalysisView.objects.filter(pk=view_to_delete.pk).exists()

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:pivot_view_list")
    assert not PivotAnalysisView.objects.filter(pk=view_to_delete.pk).exists()


@pytest.mark.django_db
def test_olapanalysis_pivot_view_matrix_workspace(client_a, pivot_view_a):
    """Test GET pivot_view_matrix renders multidimensional cross-tab matrix workspace with calculations."""
    url = reverse("bi:pivot_view_matrix", kwargs={"pk": pivot_view_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert ("view" in resp.context) or ("pivot_view" in resp.context)
    assert "cube" in resp.context
    assert "col_headers" in resp.context
    assert "matrix_rows" in resp.context or "row_headers" in resp.context
    assert "grand_totals" in resp.context
    assert pivot_view_a.name in resp.content.decode()


# ===========================================================================
# 3. WhatIfScenario Views
# ===========================================================================

@pytest.mark.django_db
def test_olapanalysis_scenario_list_view(client_a, what_if_scenario_a):
    """Test what_if_scenario_list returns 200 and context variables, and supports filtering."""
    url = reverse("bi:what_if_scenario_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "scenarios" in resp.context
    assert "total_count" in resp.context
    assert "status_choices" in resp.context
    assert what_if_scenario_a.name in resp.content.decode()

    # Filter by status
    resp_filter = client_a.get(url, {"status": "draft"})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["scenarios"]) >= 1

    # Search keyword
    resp_search = client_a.get(url, {"q": "Optimistic"})
    assert resp_search.status_code == 200
    assert len(resp_search.context["scenarios"]) >= 1


@pytest.mark.django_db
def test_olapanalysis_scenario_create_view(client_a, tenant_a, olap_cube_a):
    """Test GET and POST what_if_scenario_create saves scenario in draft and redirects to simulate."""
    url = reverse("bi:what_if_scenario_create")

    resp_get = client_a.get(url, {"cube": olap_cube_a.pk})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    payload = {
        "name": "Acme FY2026 High Growth Plan",
        "description": "Simulation with 15% revenue expansion",
        "cube": olap_cube_a.pk,
        "default_disaggregation": "pro_rata",
        "status": "draft",
        "driver_parameters_raw": json.dumps({"growth_rate": 15.0, "headcount_factor": 1.1}),
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = WhatIfScenario.objects.filter(tenant=tenant_a, name="Acme FY2026 High Growth Plan").first()
    assert created is not None
    assert created.number.startswith("BWIF")
    assert created.status == "draft"
    assert resp_post.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": created.pk})


@pytest.mark.django_db
def test_olapanalysis_scenario_detail_view(client_a, what_if_scenario_a, writeback_cell_a):
    """Test GET what_if_scenario_detail returns 200 with writeback cells count."""
    url = reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["scenario"] == what_if_scenario_a
    assert "writeback_cells" in resp.context
    assert resp.context["writeback_cells_count"] >= 1
    assert what_if_scenario_a.name in resp.content.decode()


@pytest.mark.django_db
def test_olapanalysis_scenario_edit_view(client_a, what_if_scenario_a):
    """Test GET and POST what_if_scenario_edit updates draft scenario."""
    url = reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = {
        "name": "Acme FY2026 Optimistic Budget Updated",
        "slug": what_if_scenario_a.slug,
        "description": "Refined optimistic simulation parameters",
        "cube": what_if_scenario_a.cube.pk if what_if_scenario_a.cube else "",
        "default_disaggregation": "equal",
        "status": "draft",
        "driver_parameters_raw": json.dumps({"growth_rate": 12.5}),
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})

    what_if_scenario_a.refresh_from_db()
    assert what_if_scenario_a.name == "Acme FY2026 Optimistic Budget Updated"
    assert what_if_scenario_a.default_disaggregation == "equal"


@pytest.mark.django_db
def test_olapanalysis_scenario_edit_guard_committed(client_a, what_if_scenario_a):
    """Guard test: editing a committed scenario must be blocked and redirect with an error message."""
    what_if_scenario_a.status = "committed"
    what_if_scenario_a.save(update_fields=["status"])

    url = reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk})

    # GET blocked
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})

    # POST blocked
    resp_post = client_a.post(url, {"name": "Should Not Update"})
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})

    what_if_scenario_a.refresh_from_db()
    assert what_if_scenario_a.name != "Should Not Update"


@pytest.mark.django_db
def test_olapanalysis_scenario_delete_view_post_and_guard(client_a, tenant_a):
    """Test POST what_if_scenario_delete deletes draft scenario; GET returns 405."""
    scenario_to_delete = WhatIfScenario.objects.create(
        tenant=tenant_a,
        name="Temporary Scenario To Delete",
        status="draft",
    )
    url = reverse("bi:what_if_scenario_delete", kwargs={"pk": scenario_to_delete.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert WhatIfScenario.objects.filter(pk=scenario_to_delete.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_list")
    assert not WhatIfScenario.objects.filter(pk=scenario_to_delete.pk).exists()


@pytest.mark.django_db
def test_olapanalysis_scenario_delete_guard_committed(client_a, what_if_scenario_a):
    """Guard test: deleting a committed scenario must be blocked and redirect with an error message."""
    what_if_scenario_a.status = "committed"
    what_if_scenario_a.save(update_fields=["status"])

    url = reverse("bi:what_if_scenario_delete", kwargs={"pk": what_if_scenario_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})
    assert WhatIfScenario.objects.filter(pk=what_if_scenario_a.pk).exists()


@pytest.mark.django_db
def test_olapanalysis_scenario_simulate_view(client_a, what_if_scenario_a, writeback_cell_a):
    """Test what_if_scenario_simulate computes aggregates and transitions draft scenario to simulated."""
    url = reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["scenario"] == what_if_scenario_a
    assert "writeback_cells" in resp.context
    assert "baseline_total" in resp.context
    assert "adjusted_total" in resp.context
    assert "variance_total" in resp.context

    # Verify scenario transition
    what_if_scenario_a.refresh_from_db()
    assert what_if_scenario_a.status == "simulated"
    assert what_if_scenario_a.total_adjusted_amount == writeback_cell_a.adjusted_value


@pytest.mark.django_db
def test_olapanalysis_scenario_commit_view_post_and_guard(client_a, what_if_scenario_a, writeback_cell_a, admin_user):
    """Test POST what_if_scenario_commit sets is_committed=True, marks scenario committed; GET returns 405."""
    url = reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST commits scenario and all writeback cells
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})

    what_if_scenario_a.refresh_from_db()
    assert what_if_scenario_a.status == "committed"
    assert what_if_scenario_a.committed_by == admin_user
    assert what_if_scenario_a.committed_at is not None

    writeback_cell_a.refresh_from_db()
    assert writeback_cell_a.is_committed is True

    # Re-committing returns warning and redirects safely
    resp_recommit = client_a.post(url)
    assert resp_recommit.status_code == 302
    assert resp_recommit.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})


# ===========================================================================
# 4. ScenarioWritebackCell Views
# ===========================================================================

@pytest.mark.django_db
def test_olapanalysis_writeback_cell_list_view(client_a, writeback_cell_a, what_if_scenario_a):
    """Test writeback_cell_list returns 200, context variables, and supports scenario filtering."""
    url = reverse("bi:writeback_cell_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "cells" in resp.context
    assert "total_count" in resp.context
    assert "committed_count" in resp.context
    assert "pending_count" in resp.context
    assert "scenarios" in resp.context
    assert "spread_method_choices" in resp.context
    assert writeback_cell_a.number in resp.content.decode()

    # Filter by scenario
    resp_filter = client_a.get(url, {"scenario": what_if_scenario_a.pk})
    assert resp_filter.status_code == 200
    assert len(resp_filter.context["cells"]) >= 1


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_create_view(client_a, tenant_a, what_if_scenario_a):
    """Test GET and POST writeback_cell_create saves writeback cell with variance auto-calculation."""
    url = reverse("bi:writeback_cell_create")

    # GET with pre-selected scenario
    resp_get = client_a.get(url, {"scenario": what_if_scenario_a.pk})
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid cell
    payload = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "15000.00",
        "adjusted_value": "18500.00",
        "spread_method": "direct_leaf",
        "cell_coordinates_raw": json.dumps({"period": "2026-Q2", "division": "EMEA"}),
        "commentary": "Projected Q2 expansion adjustment",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk})

    created = ScenarioWritebackCell.objects.filter(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        commentary="Projected Q2 expansion adjustment",
    ).first()
    assert created is not None
    assert created.number.startswith("BWBC")
    assert created.baseline_value == Decimal("15000.00")
    assert created.adjusted_value == Decimal("18500.00")
    assert created.variance_amount == Decimal("3500.00")
    assert created.is_committed is False


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_create_guard_committed_scenario(client_a, what_if_scenario_a):
    """Guard test: creating a cell against a committed scenario must be blocked."""
    what_if_scenario_a.status = "committed"
    what_if_scenario_a.save(update_fields=["status"])

    url = reverse("bi:writeback_cell_create")

    # GET with committed scenario param redirects to detail
    resp_get = client_a.get(url, {"scenario": what_if_scenario_a.pk})
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})

    # POST targeting committed scenario is rejected and cell is NOT created
    payload = {
        "scenario": what_if_scenario_a.pk,
        "baseline_value": "1000.00",
        "adjusted_value": "1200.00",
        "spread_method": "direct_leaf",
    }
    resp_post = client_a.post(url, payload)
    # Form rejects choice from excluded queryset (200) or view guard redirects (302)
    assert resp_post.status_code in (200, 302)
    assert not ScenarioWritebackCell.objects.filter(scenario=what_if_scenario_a, baseline_value=Decimal("1000.00")).exists()


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_detail_view(client_a, writeback_cell_a):
    """Test GET writeback_cell_detail returns 200 with cell in context."""
    url = reverse("bi:writeback_cell_detail", kwargs={"pk": writeback_cell_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["cell"] == writeback_cell_a
    assert writeback_cell_a.number in resp.content.decode()


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_edit_view(client_a, writeback_cell_a):
    """Test GET and POST writeback_cell_edit updates amounts and recalculated variance."""
    url = reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk})

    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    payload = {
        "scenario": writeback_cell_a.scenario.pk,
        "baseline_value": "10000.00",
        "adjusted_value": "13500.00",
        "spread_method": "direct_leaf",
        "cell_coordinates_raw": json.dumps({"period": "2026-Q1", "dept": "Sales"}),
        "commentary": "Refined adjustment to 13,500",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": writeback_cell_a.scenario.pk})

    writeback_cell_a.refresh_from_db()
    assert writeback_cell_a.adjusted_value == Decimal("13500.00")
    assert writeback_cell_a.variance_amount == Decimal("3500.00")
    assert writeback_cell_a.commentary == "Refined adjustment to 13,500"


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_edit_guard_committed(client_a, writeback_cell_a):
    """Guard test: editing a cell that is committed or belongs to a committed scenario is blocked."""
    writeback_cell_a.is_committed = True
    writeback_cell_a.save(update_fields=["is_committed"])

    url = reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk})

    # GET blocked
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": writeback_cell_a.scenario.pk})

    # POST blocked
    resp_post = client_a.post(url, {"adjusted_value": "99999.00"})
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": writeback_cell_a.scenario.pk})

    writeback_cell_a.refresh_from_db()
    assert writeback_cell_a.adjusted_value != Decimal("99999.00")


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_delete_view_post_and_guard(client_a, tenant_a, what_if_scenario_a):
    """Test POST writeback_cell_delete removes cell; GET returns 405 Method Not Allowed."""
    cell_to_delete = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=what_if_scenario_a,
        baseline_value=Decimal("1000.00"),
        adjusted_value=Decimal("1200.00"),
    )
    url = reverse("bi:writeback_cell_delete", kwargs={"pk": cell_to_delete.pk})

    # GET returns 405
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert ScenarioWritebackCell.objects.filter(pk=cell_to_delete.pk).exists()

    # POST deletes
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk})
    assert not ScenarioWritebackCell.objects.filter(pk=cell_to_delete.pk).exists()


@pytest.mark.django_db
def test_olapanalysis_writeback_cell_delete_guard_committed(client_a, writeback_cell_a):
    """Guard test: deleting a committed cell is blocked and redirects with an error message."""
    writeback_cell_a.is_committed = True
    writeback_cell_a.save(update_fields=["is_committed"])

    url = reverse("bi:writeback_cell_delete", kwargs={"pk": writeback_cell_a.pk})
    resp = client_a.post(url)

    assert resp.status_code == 302
    assert resp.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": writeback_cell_a.scenario.pk})
    assert ScenarioWritebackCell.objects.filter(pk=writeback_cell_a.pk).exists()

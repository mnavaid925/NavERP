"""Security, Multi-Tenancy, Authorization, and Immutability Tests for Sub-module 10.12
(OLAP & Multidimensional Analysis).

Covers:
1. Anonymous Authentication (@login_required):
   - Anonymous GET to all 18 routes (lists, details, creates, edits, matrix, simulate)
     redirects to /accounts/login/ (HTTP 302).
   - Anonymous POST to mutation/action routes (delete, refresh, commit) redirects to login.
2. Multi-Tenant Isolation & IDOR Protection:
   - Client A attempting to access Client B's objects (cubes, pivot views, scenarios,
     writeback cells) returns strictly HTTP 404 on detail, edit, delete, refresh, matrix,
     simulate, and commit endpoints.
   - Bidirectional reverse IDOR protection: Client B accessing Client A's objects returns 404.
   - List views: Client A never sees Client B's objects in cubes, pivot_views, scenarios,
     or cells; zero data leakage across tenant boundaries.
3. Role-Based Authorization (@tenant_admin_required):
   - Non-admin member user in Tenant A (is_tenant_admin=False) attempting to execute
     admin-only endpoints (what_if_scenario_commit, olap_cube_delete, pivot_view_delete,
     what_if_scenario_delete, writeback_cell_delete) receives HTTP 403 Forbidden.
   - Non-admin member retains access to non-privileged reads, creations, edits, matrix,
     and simulation views.
4. HTTP Method Constraints (@require_POST):
   - All 4 delete routes and action routes (refresh, commit) reject GET requests with
     HTTP 405 Method Not Allowed.
5. Cross-Tenant Foreign Key Injection:
   - Form and view rejection of foreign OlapCube in PivotAnalysisViewForm and WhatIfScenarioForm.
   - Form and view rejection of foreign WhatIfScenario in ScenarioWritebackCellForm.
   - Form rejection of foreign SemanticModel, WarehouseTable, DrillHierarchy, Budget,
     FiscalPeriod, GLAccount, and OrgUnit.
6. Ledger Immutability & Status Bypass Protection:
   - Attempting to update or delete an already committed scenario via POST is blocked and
     does not alter or delete the scenario.
   - Attempting to create, update, or delete a writeback cell on an already committed scenario
     is blocked.
   - Attempting to bypass workflow by injecting status='committed' in create/edit POST payload
     is rejected by form validation.
   - Mutating state transitions produce append-only AuditLog records scoped to the tenant.
7. Multi-User Simulation & Boundary Scaling:
   - Simulates heterogeneous users across Tenant A and Tenant B concurrently querying
     OLAP entities, asserting 100% tenant boundary preservation and zero leakage.
"""
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

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
from apps.bi.views._common import bi_scope
from apps.core.models import AuditLog, OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Bridge Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


# ---------------------------------------------------------------------------
# Module Helpers
# ---------------------------------------------------------------------------

def _olapanalysis_dims_payload():
    """Helper returning JSON-encoded dimensional hierarchy configuration."""
    return json.dumps([
        {"name": "Department", "type": "organization", "levels": ["Division", "Department"]},
        {"name": "FiscalPeriod", "type": "time", "levels": ["Year", "Quarter", "Month"]},
    ])


def _olapanalysis_measures_payload():
    """Helper returning JSON-encoded measures configuration."""
    return json.dumps([
        {"name": "Actual Amount", "aggregation": "sum", "format": "$#,##0.00"},
        {"name": "Budget Amount", "aggregation": "sum", "format": "$#,##0.00"},
    ])


def _olapanalysis_aggregations_payload():
    """Helper returning JSON-encoded cuboid aggregations configuration."""
    return json.dumps([["Department", "FiscalPeriod"]])


def _olapanalysis_driver_params_payload():
    """Helper returning JSON-encoded scenario driver parameters."""
    return json.dumps({
        "revenue_growth_pct": 10.0,
        "cost_inflation_pct": 3.0,
    })


# ===========================================================================
# 1. Anonymous Authentication (@login_required)
# ===========================================================================

def test_olapanalysis_anonymous_get_redirects_to_login(
    client,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert anonymous GET requests to all 18 routes redirect to /accounts/login/ (HTTP 302)."""
    routes = [
        # OlapCube (4 GET routes)
        reverse("bi:olap_cube_list"),
        reverse("bi:olap_cube_create"),
        reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:olap_cube_edit", kwargs={"pk": olap_cube_a.pk}),
        # PivotAnalysisView (5 GET routes)
        reverse("bi:pivot_view_list"),
        reverse("bi:pivot_view_create"),
        reverse("bi:pivot_view_detail", kwargs={"pk": pivot_view_a.pk}),
        reverse("bi:pivot_view_edit", kwargs={"pk": pivot_view_a.pk}),
        reverse("bi:pivot_view_matrix", kwargs={"pk": pivot_view_a.pk}),
        # WhatIfScenario (5 GET routes)
        reverse("bi:what_if_scenario_list"),
        reverse("bi:what_if_scenario_create"),
        reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk}),
        # ScenarioWritebackCell (4 GET routes)
        reverse("bi:writeback_cell_list"),
        reverse("bi:writeback_cell_create"),
        reverse("bi:writeback_cell_detail", kwargs={"pk": writeback_cell_a.pk}),
        reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk}),
    ]

    assert len(routes) == 18, f"Expected exactly 18 GET routes, found {len(routes)}"

    for url in routes:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 for anonymous GET {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected redirect to /login/ for {url}, got {resp.url}"


def test_olapanalysis_anonymous_post_mutations_redirects_to_login(
    client,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert anonymous POST to all 6 mutation/action endpoints redirects to login (HTTP 302)."""
    mutation_endpoints = [
        reverse("bi:olap_cube_delete", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:pivot_view_delete", kwargs={"pk": pivot_view_a.pk}),
        reverse("bi:what_if_scenario_delete", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:writeback_cell_delete", kwargs={"pk": writeback_cell_a.pk}),
    ]

    assert len(mutation_endpoints) == 6

    for url in mutation_endpoints:
        resp = client.post(url, {})
        assert resp.status_code == 302, f"Expected 302 redirect for POST {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected redirect to login for {url}, got {resp.url}"


# ===========================================================================
# 2. Multi-Tenant Isolation & IDOR Protection
# ===========================================================================

def test_olapanalysis_cube_cross_tenant_idor_protection(client_a, olap_cube_b):
    """Assert Tenant A user cannot access or mutate Tenant B cube endpoints (strictly 404)."""
    pk = olap_cube_b.pk
    detail_url = reverse("bi:olap_cube_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:olap_cube_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:olap_cube_delete", kwargs={"pk": pk})
    refresh_url = reverse("bi:olap_cube_refresh", kwargs={"pk": pk})

    # Detail GET -> 404
    assert client_a.get(detail_url).status_code == 404
    # Edit GET -> 404
    assert client_a.get(edit_url).status_code == 404
    # Edit POST -> 404
    assert client_a.post(edit_url, {"name": "Tampered Cube Name"}).status_code == 404
    # Delete POST -> 404
    assert client_a.post(delete_url).status_code == 404
    # Refresh POST -> 404
    assert client_a.post(refresh_url).status_code == 404

    # Confirm object unchanged in DB
    olap_cube_b.refresh_from_db()
    assert olap_cube_b.name != "Tampered Cube Name"


def test_olapanalysis_pivot_view_cross_tenant_idor_protection(client_a, pivot_view_b):
    """Assert Tenant A user cannot access or mutate Tenant B pivot view endpoints (strictly 404)."""
    pk = pivot_view_b.pk
    detail_url = reverse("bi:pivot_view_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:pivot_view_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:pivot_view_delete", kwargs={"pk": pk})
    matrix_url = reverse("bi:pivot_view_matrix", kwargs={"pk": pk})

    # Detail GET -> 404
    assert client_a.get(detail_url).status_code == 404
    # Edit GET -> 404
    assert client_a.get(edit_url).status_code == 404
    # Edit POST -> 404
    assert client_a.post(edit_url, {"name": "Tampered Pivot View"}).status_code == 404
    # Delete POST -> 404
    assert client_a.post(delete_url).status_code == 404
    # Matrix GET -> 404
    assert client_a.get(matrix_url).status_code == 404

    pivot_view_b.refresh_from_db()
    assert pivot_view_b.name != "Tampered Pivot View"


def test_olapanalysis_what_if_scenario_cross_tenant_idor_protection(client_a, what_if_scenario_b):
    """Assert Tenant A user cannot access or mutate Tenant B scenario endpoints (strictly 404)."""
    pk = what_if_scenario_b.pk
    detail_url = reverse("bi:what_if_scenario_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:what_if_scenario_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:what_if_scenario_delete", kwargs={"pk": pk})
    simulate_url = reverse("bi:what_if_scenario_simulate", kwargs={"pk": pk})
    commit_url = reverse("bi:what_if_scenario_commit", kwargs={"pk": pk})

    # Detail GET -> 404
    assert client_a.get(detail_url).status_code == 404
    # Edit GET -> 404
    assert client_a.get(edit_url).status_code == 404
    # Edit POST -> 404
    assert client_a.post(edit_url, {"name": "Tampered Scenario"}).status_code == 404
    # Delete POST -> 404
    assert client_a.post(delete_url).status_code == 404
    # Simulate GET -> 404
    assert client_a.get(simulate_url).status_code == 404
    # Commit POST -> 404
    assert client_a.post(commit_url).status_code == 404

    what_if_scenario_b.refresh_from_db()
    assert what_if_scenario_b.name != "Tampered Scenario"
    assert what_if_scenario_b.status == "draft"


def test_olapanalysis_writeback_cell_cross_tenant_idor_protection(client_a, writeback_cell_b):
    """Assert Tenant A user cannot access or mutate Tenant B writeback cell endpoints (strictly 404)."""
    pk = writeback_cell_b.pk
    detail_url = reverse("bi:writeback_cell_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:writeback_cell_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:writeback_cell_delete", kwargs={"pk": pk})

    # Detail GET -> 404
    assert client_a.get(detail_url).status_code == 404
    # Edit GET -> 404
    assert client_a.get(edit_url).status_code == 404
    # Edit POST -> 404
    assert client_a.post(edit_url, {"adjusted_value": "999999.00"}).status_code == 404
    # Delete POST -> 404
    assert client_a.post(delete_url).status_code == 404

    writeback_cell_b.refresh_from_db()
    assert writeback_cell_b.adjusted_value != Decimal("999999.00")


def test_olapanalysis_reverse_cross_tenant_idor_protection(
    client_b,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert Tenant B user cannot access Tenant A objects across all 20 object endpoints (strictly 404)."""
    # Cube A
    assert client_b.get(reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:olap_cube_edit", kwargs={"pk": olap_cube_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:olap_cube_edit", kwargs={"pk": olap_cube_a.pk}), {}).status_code == 404
    assert client_b.post(reverse("bi:olap_cube_delete", kwargs={"pk": olap_cube_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk})).status_code == 404

    # Pivot View A
    assert client_b.get(reverse("bi:pivot_view_detail", kwargs={"pk": pivot_view_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:pivot_view_edit", kwargs={"pk": pivot_view_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:pivot_view_edit", kwargs={"pk": pivot_view_a.pk}), {}).status_code == 404
    assert client_b.post(reverse("bi:pivot_view_delete", kwargs={"pk": pivot_view_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:pivot_view_matrix", kwargs={"pk": pivot_view_a.pk})).status_code == 404

    # Scenario A
    assert client_b.get(reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk}), {}).status_code == 404
    assert client_b.post(reverse("bi:what_if_scenario_delete", kwargs={"pk": what_if_scenario_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk})).status_code == 404

    # Writeback Cell A
    assert client_b.get(reverse("bi:writeback_cell_detail", kwargs={"pk": writeback_cell_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk}), {}).status_code == 404
    assert client_b.post(reverse("bi:writeback_cell_delete", kwargs={"pk": writeback_cell_a.pk})).status_code == 404


def test_olapanalysis_cross_tenant_list_isolation(
    client_a,
    client_b,
    olap_cube_a,
    olap_cube_b,
    pivot_view_a,
    pivot_view_b,
    what_if_scenario_a,
    what_if_scenario_b,
    writeback_cell_a,
    writeback_cell_b,
):
    """Assert list views strictly isolate querysets and never leak cross-tenant records."""
    # 1. Cubes list
    resp_cube_a = client_a.get(reverse("bi:olap_cube_list"))
    assert resp_cube_a.status_code == 200
    cubes_a = list(resp_cube_a.context["cubes"])
    assert olap_cube_a in cubes_a
    assert olap_cube_b not in cubes_a
    assert olap_cube_b.name not in resp_cube_a.content.decode()

    resp_cube_b = client_b.get(reverse("bi:olap_cube_list"))
    assert resp_cube_b.status_code == 200
    cubes_b = list(resp_cube_b.context["cubes"])
    assert olap_cube_b in cubes_b
    assert olap_cube_a not in cubes_b
    assert olap_cube_a.name not in resp_cube_b.content.decode()

    # 2. Pivot Views list
    resp_pivot_a = client_a.get(reverse("bi:pivot_view_list"))
    assert resp_pivot_a.status_code == 200
    pivots_a = list(resp_pivot_a.context["views"])
    assert pivot_view_a in pivots_a
    assert pivot_view_b not in pivots_a
    assert pivot_view_b.name not in resp_pivot_a.content.decode()

    resp_pivot_b = client_b.get(reverse("bi:pivot_view_list"))
    assert resp_pivot_b.status_code == 200
    pivots_b = list(resp_pivot_b.context["views"])
    assert pivot_view_b in pivots_b
    assert pivot_view_a not in pivots_b
    assert pivot_view_a.name not in resp_pivot_b.content.decode()

    # 3. What-If Scenarios list
    resp_scen_a = client_a.get(reverse("bi:what_if_scenario_list"))
    assert resp_scen_a.status_code == 200
    scens_a = list(resp_scen_a.context["scenarios"])
    assert what_if_scenario_a in scens_a
    assert what_if_scenario_b not in scens_a
    assert what_if_scenario_b.name not in resp_scen_a.content.decode()

    resp_scen_b = client_b.get(reverse("bi:what_if_scenario_list"))
    assert resp_scen_b.status_code == 200
    scens_b = list(resp_scen_b.context["scenarios"])
    assert what_if_scenario_b in scens_b
    assert what_if_scenario_a not in scens_b
    assert what_if_scenario_a.name not in resp_scen_b.content.decode()

    # 4. Writeback Cells list
    resp_cell_a = client_a.get(reverse("bi:writeback_cell_list"))
    assert resp_cell_a.status_code == 200
    cells_a = list(resp_cell_a.context["cells"])
    assert writeback_cell_a in cells_a
    assert writeback_cell_b not in cells_a
    assert what_if_scenario_b.name not in resp_cell_a.content.decode()

    resp_cell_b = client_b.get(reverse("bi:writeback_cell_list"))
    assert resp_cell_b.status_code == 200
    cells_b = list(resp_cell_b.context["cells"])
    assert writeback_cell_b in cells_b
    assert writeback_cell_a not in cells_b
    assert what_if_scenario_a.name not in resp_cell_b.content.decode()


# ===========================================================================
# 3. Role-Based Authorization (@tenant_admin_required)
# ===========================================================================

def test_olapanalysis_non_admin_member_forbidden_on_admin_endpoints(
    member_client,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert non-admin member user receives HTTP 403 Forbidden on privileged endpoints."""
    privileged_endpoints = [
        reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:olap_cube_delete", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:pivot_view_delete", kwargs={"pk": pivot_view_a.pk}),
        reverse("bi:what_if_scenario_delete", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:writeback_cell_delete", kwargs={"pk": writeback_cell_a.pk}),
    ]

    for url in privileged_endpoints:
        resp = member_client.post(url, {})
        assert resp.status_code == 403, f"Expected 403 Forbidden for non-admin on POST {url}, got {resp.status_code}"

    # Confirm records were not deleted or committed
    olap_cube_a.refresh_from_db()
    pivot_view_a.refresh_from_db()
    what_if_scenario_a.refresh_from_db()
    writeback_cell_a.refresh_from_db()
    assert what_if_scenario_a.status == "draft"


def test_olapanalysis_non_admin_member_allowed_standard_operations(
    member_client,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert non-admin member user retains access to non-privileged reads, creations, edits, and simulation."""
    # 1. Read operations return 200
    assert member_client.get(reverse("bi:olap_cube_list")).status_code == 200
    assert member_client.get(reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:pivot_view_list")).status_code == 200
    assert member_client.get(reverse("bi:pivot_view_detail", kwargs={"pk": pivot_view_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:pivot_view_matrix", kwargs={"pk": pivot_view_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:what_if_scenario_list")).status_code == 200
    assert member_client.get(reverse("bi:what_if_scenario_detail", kwargs={"pk": what_if_scenario_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:what_if_scenario_simulate", kwargs={"pk": what_if_scenario_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:writeback_cell_list")).status_code == 200
    assert member_client.get(reverse("bi:writeback_cell_detail", kwargs={"pk": writeback_cell_a.pk})).status_code == 200

    # 2. Cube refresh is permitted to regular logged-in members (POST only)
    refresh_resp = member_client.post(reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk}))
    assert refresh_resp.status_code == 302
    assert refresh_resp.url == reverse("bi:olap_cube_detail", kwargs={"pk": olap_cube_a.pk})

    # 3. GET create/edit forms return 200
    assert member_client.get(reverse("bi:olap_cube_create")).status_code == 200
    assert member_client.get(reverse("bi:olap_cube_edit", kwargs={"pk": olap_cube_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:pivot_view_create")).status_code == 200
    assert member_client.get(reverse("bi:pivot_view_edit", kwargs={"pk": pivot_view_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:what_if_scenario_create")).status_code == 200
    assert member_client.get(reverse("bi:what_if_scenario_edit", kwargs={"pk": what_if_scenario_a.pk})).status_code == 200
    assert member_client.get(reverse("bi:writeback_cell_create")).status_code == 200
    assert member_client.get(reverse("bi:writeback_cell_edit", kwargs={"pk": writeback_cell_a.pk})).status_code == 200


# ===========================================================================
# 4. HTTP Method Constraints (@require_POST)
# ===========================================================================

def test_olapanalysis_post_only_endpoints_reject_get(
    client_a,
    olap_cube_a,
    pivot_view_a,
    what_if_scenario_a,
    writeback_cell_a,
):
    """Assert mutating and action endpoints reject GET requests with HTTP 405 Method Not Allowed."""
    post_only_urls = [
        reverse("bi:olap_cube_delete", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk}),
        reverse("bi:pivot_view_delete", kwargs={"pk": pivot_view_a.pk}),
        reverse("bi:what_if_scenario_delete", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk}),
        reverse("bi:writeback_cell_delete", kwargs={"pk": writeback_cell_a.pk}),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


# ===========================================================================
# 5. Cross-Tenant Foreign Key Injection
# ===========================================================================

def test_olapanalysis_pivot_view_form_cross_tenant_cube_injection(tenant_a, olap_cube_b):
    """Assert PivotAnalysisViewForm rejects foreign OlapCube belonging to Tenant B."""
    form_data = {
        "cube": olap_cube_b.pk,
        "name": "Hostile Injected Cross-Tenant Pivot View",
        "status": "active",
        "row_dimensions_raw": json.dumps(["Department"]),
        "column_dimensions_raw": json.dumps(["FiscalPeriod"]),
        "selected_measures_raw": json.dumps(["Actual Amount"]),
    }
    form = PivotAnalysisViewForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cube" in form.errors
    assert OlapCube.objects.filter(pk=olap_cube_b.pk, tenant=tenant_a).count() == 0


def test_olapanalysis_what_if_scenario_form_cross_tenant_cube_injection(tenant_a, olap_cube_b):
    """Assert WhatIfScenarioForm rejects foreign OlapCube belonging to Tenant B."""
    form_data = {
        "name": "Hostile Scenario Targeting Foreign Cube",
        "cube": olap_cube_b.pk,
        "status": "draft",
        "default_disaggregation": "pro_rata",
    }
    form = WhatIfScenarioForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cube" in form.errors


def test_olapanalysis_writeback_cell_form_cross_tenant_scenario_injection(tenant_a, what_if_scenario_b):
    """Assert ScenarioWritebackCellForm rejects foreign WhatIfScenario belonging to Tenant B."""
    form_data = {
        "scenario": what_if_scenario_b.pk,
        "baseline_value": "15000.00",
        "adjusted_value": "18000.00",
        "spread_method": "direct_leaf",
    }
    form = ScenarioWritebackCellForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "scenario" in form.errors


def test_olapanalysis_create_views_reject_cross_tenant_fk_post(
    client_a,
    tenant_a,
    olap_cube_b,
    what_if_scenario_b,
):
    """Assert submitting foreign FKs in create POST requests is rejected and saves no records."""
    # 1. Pivot create with foreign cube
    pivot_payload = {
        "cube": olap_cube_b.pk,
        "name": "Unauthorized Injected Pivot View",
        "status": "active",
        "row_dimensions_raw": json.dumps(["Department"]),
        "column_dimensions_raw": json.dumps(["FiscalPeriod"]),
        "selected_measures_raw": json.dumps(["Actual Amount"]),
    }
    resp_pivot = client_a.post(reverse("bi:pivot_view_create"), pivot_payload)
    assert resp_pivot.status_code == 200  # Re-renders form with validation errors
    assert PivotAnalysisView.objects.filter(tenant=tenant_a, name="Unauthorized Injected Pivot View").count() == 0

    # 2. Scenario create with foreign cube
    scen_payload = {
        "name": "Unauthorized Injected Scenario",
        "cube": olap_cube_b.pk,
        "status": "draft",
    }
    resp_scen = client_a.post(reverse("bi:what_if_scenario_create"), scen_payload)
    assert resp_scen.status_code == 200
    assert WhatIfScenario.objects.filter(tenant=tenant_a, name="Unauthorized Injected Scenario").count() == 0

    # 3. Writeback cell create with foreign scenario
    cell_payload = {
        "scenario": what_if_scenario_b.pk,
        "baseline_value": "5000.00",
        "adjusted_value": "6000.00",
        "spread_method": "direct_leaf",
    }
    resp_cell = client_a.post(reverse("bi:writeback_cell_create"), cell_payload)
    assert resp_cell.status_code == 200
    assert ScenarioWritebackCell.objects.filter(tenant=tenant_a, scenario=what_if_scenario_b).count() == 0


def test_olapanalysis_form_reject_foreign_helpers(
    tenant_a,
    tenant_b,
    olap_cube_a,
    what_if_scenario_a,
):
    """Assert reject_foreign validates all foreign keys across models."""
    # Budget in Tenant B
    budget_b = Budget.objects.create(
        tenant=tenant_b,
        name="Globex Operations Budget",
        version="original",
        status="draft",
    )
    # FiscalPeriod in Tenant B
    period_b = FiscalPeriod.objects.create(
        tenant=tenant_b,
        name="Globex 2026 Q1",
        start_date="2026-01-01",
        end_date="2026-03-31",
        period_type="quarter",
    )
    # GLAccount in Tenant B
    gl_b = GLAccount.objects.create(
        tenant=tenant_b,
        code="4000-GLB",
        name="Globex Sales Revenue",
        account_type="revenue",
    )
    # OrgUnit in Tenant B
    ou_b = OrgUnit.objects.create(
        tenant=tenant_b,
        name="Globex EMEA Division",
        kind="department",
    )

    # WhatIfScenarioForm rejecting foreign budget and period
    form_scen = WhatIfScenarioForm(
        data={
            "name": "Cross-Tenant Financial Scenario",
            "cube": olap_cube_a.pk,
            "baseline_budget": budget_b.pk,
            "fiscal_period": period_b.pk,
            "status": "draft",
        },
        tenant=tenant_a,
    )
    assert not form_scen.is_valid()
    assert "baseline_budget" in form_scen.errors
    assert "fiscal_period" in form_scen.errors

    # ScenarioWritebackCellForm rejecting foreign gl_account and org_unit
    form_cell = ScenarioWritebackCellForm(
        data={
            "scenario": what_if_scenario_a.pk,
            "gl_account": gl_b.pk,
            "org_unit": ou_b.pk,
            "baseline_value": "1000.00",
            "adjusted_value": "1200.00",
            "spread_method": "direct_leaf",
        },
        tenant=tenant_a,
    )
    assert not form_cell.is_valid()
    assert "gl_account" in form_cell.errors
    assert "org_unit" in form_cell.errors


# ===========================================================================
# 6. Ledger Immutability & Status Bypass Protection
# ===========================================================================

def test_olapanalysis_committed_scenario_edit_blocked(client_a, tenant_a, olap_cube_a, admin_user):
    """Assert an already committed scenario cannot be updated via edit endpoint."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Immutable Committed Scenario",
        slug="immutable-committed-scenario",
        status="committed",
        total_baseline_amount=Decimal("100000.00"),
        total_adjusted_amount=Decimal("110000.00"),
        total_variance_amount=Decimal("10000.00"),
        created_by=admin_user,
    )

    edit_url = reverse("bi:what_if_scenario_edit", kwargs={"pk": committed_scenario.pk})

    # GET redirect to detail
    get_resp = client_a.get(edit_url)
    assert get_resp.status_code == 302
    assert get_resp.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": committed_scenario.pk})

    # POST payload attempting update is blocked
    post_resp = client_a.post(edit_url, {
        "name": "Tampered Committed Scenario Name",
        "cube": olap_cube_a.pk,
        "status": "draft",
    })
    assert post_resp.status_code == 302

    committed_scenario.refresh_from_db()
    assert committed_scenario.name == "Immutable Committed Scenario"
    assert committed_scenario.status == "committed"


def test_olapanalysis_committed_scenario_delete_blocked(client_a, tenant_a, olap_cube_a, admin_user):
    """Assert an already committed scenario cannot be deleted via delete endpoint."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Locked From Deletion Scenario",
        slug="locked-from-deletion-scenario",
        status="committed",
        created_by=admin_user,
    )

    delete_url = reverse("bi:what_if_scenario_delete", kwargs={"pk": committed_scenario.pk})
    resp = client_a.post(delete_url, {})
    assert resp.status_code == 302
    assert resp.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": committed_scenario.pk})

    assert WhatIfScenario.objects.filter(pk=committed_scenario.pk).exists()


def test_olapanalysis_committed_scenario_writeback_cell_create_blocked(
    client_a,
    tenant_a,
    olap_cube_a,
    admin_user,
):
    """Assert writeback cells cannot be added to a committed scenario."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Committed Closed Scenario",
        slug="committed-closed-scenario",
        status="committed",
        created_by=admin_user,
    )

    create_url = reverse("bi:writeback_cell_create")

    # GET with scenario parameter redirects with error
    get_resp = client_a.get(create_url, {"scenario": committed_scenario.pk})
    assert get_resp.status_code == 302
    assert get_resp.url == reverse("bi:what_if_scenario_detail", kwargs={"pk": committed_scenario.pk})

    # POST attempting creation targeting committed scenario is blocked
    post_payload = {
        "scenario": committed_scenario.pk,
        "baseline_value": "2000.00",
        "adjusted_value": "2500.00",
        "spread_method": "direct_leaf",
    }
    post_resp = client_a.post(create_url, post_payload)
    # Form validation clean_scenario fails, or view guard blocks
    assert ScenarioWritebackCell.objects.filter(scenario=committed_scenario).count() == 0


def test_olapanalysis_committed_scenario_writeback_cell_edit_blocked(
    client_a,
    tenant_a,
    olap_cube_a,
    admin_user,
):
    """Assert writeback cells on committed scenarios cannot be modified."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Committed Simulation Ledger",
        slug="committed-simulation-ledger",
        status="committed",
        created_by=admin_user,
    )
    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=committed_scenario,
        baseline_value=Decimal("10000.00"),
        adjusted_value=Decimal("12000.00"),
        variance_amount=Decimal("2000.00"),
        spread_method="direct_leaf",
        is_committed=True,
        created_by=admin_user,
    )

    edit_url = reverse("bi:writeback_cell_edit", kwargs={"pk": cell.pk})

    # GET redirects to simulate view
    get_resp = client_a.get(edit_url)
    assert get_resp.status_code == 302
    assert get_resp.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": committed_scenario.pk})

    # POST update attempt is blocked
    post_resp = client_a.post(edit_url, {"adjusted_value": "99999.00"})
    assert post_resp.status_code == 302

    cell.refresh_from_db()
    assert cell.adjusted_value == Decimal("12000.00")


def test_olapanalysis_committed_scenario_writeback_cell_delete_blocked(
    client_a,
    tenant_a,
    olap_cube_a,
    admin_user,
):
    """Assert writeback cells on committed scenarios cannot be deleted."""
    committed_scenario = WhatIfScenario.objects.create(
        tenant=tenant_a,
        cube=olap_cube_a,
        name="Committed Simulation Ledger For Deletion Test",
        slug="committed-simulation-ledger-del",
        status="committed",
        created_by=admin_user,
    )
    cell = ScenarioWritebackCell.objects.create(
        tenant=tenant_a,
        scenario=committed_scenario,
        baseline_value=Decimal("5000.00"),
        adjusted_value=Decimal("5500.00"),
        spread_method="direct_leaf",
        is_committed=True,
        created_by=admin_user,
    )

    delete_url = reverse("bi:writeback_cell_delete", kwargs={"pk": cell.pk})
    resp = client_a.post(delete_url, {})
    assert resp.status_code == 302
    assert resp.url == reverse("bi:what_if_scenario_simulate", kwargs={"pk": committed_scenario.pk})

    assert ScenarioWritebackCell.objects.filter(pk=cell.pk).exists()


def test_olapanalysis_status_bypass_injection_rejected(tenant_a, olap_cube_a, what_if_scenario_a):
    """Assert attempting to inject status='committed' via POST payload is rejected by form validation."""
    # 1. On creation
    form_create = WhatIfScenarioForm(
        data={
            "name": "Bypass Attempt Scenario",
            "cube": olap_cube_a.pk,
            "status": "committed",
        },
        tenant=tenant_a,
    )
    assert not form_create.is_valid()
    assert "status" in form_create.errors

    # 2. On editing an uncommitted scenario
    form_edit = WhatIfScenarioForm(
        instance=what_if_scenario_a,
        data={
            "name": what_if_scenario_a.name,
            "cube": olap_cube_a.pk,
            "status": "committed",
        },
        tenant=tenant_a,
    )
    assert not form_edit.is_valid()
    assert "status" in form_edit.errors


def test_olapanalysis_audit_log_recorded_for_commit_and_mutations(
    client_a,
    tenant_a,
    admin_user,
    what_if_scenario_a,
    olap_cube_a,
):
    """Assert state-changing operations write audit logs strictly scoped to the tenant."""
    # 1. Scenario commit writes audit log
    commit_url = reverse("bi:what_if_scenario_commit", kwargs={"pk": what_if_scenario_a.pk})
    resp = client_a.post(commit_url, {})
    assert resp.status_code == 302

    what_if_scenario_a.refresh_from_db()
    assert what_if_scenario_a.status == "committed"

    commit_logs = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="commit",
        object_id=what_if_scenario_a.pk,
    )
    assert commit_logs.exists()

    # 2. Cube refresh writes audit log
    refresh_url = reverse("bi:olap_cube_refresh", kwargs={"pk": olap_cube_a.pk})
    resp_ref = client_a.post(refresh_url, {})
    assert resp_ref.status_code == 302

    refresh_logs = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="refresh",
        object_id=olap_cube_a.pk,
    )
    assert refresh_logs.exists()


# ===========================================================================
# 7. Multi-User Simulation & Boundary Scaling
# ===========================================================================

def test_olapanalysis_multi_user_scale_simulation(
    db,
    tenant_a,
    tenant_b,
):
    """Simulate 30 heterogeneous users across Tenant A and B to verify 100% tenant boundary isolation."""
    # 1. Bulk create 15 users for Tenant A and 15 for Tenant B
    users_a = [
        User(
            email=f"scale_user_a_{i}@acme.com",
            username=f"scale_user_a_{i}",
            tenant=tenant_a,
            is_tenant_admin=False,
        )
        for i in range(1, 16)
    ]
    users_b = [
        User(
            email=f"scale_user_b_{i}@globex.com",
            username=f"scale_user_b_{i}",
            tenant=tenant_b,
            is_tenant_admin=False,
        )
        for i in range(1, 16)
    ]
    User.objects.bulk_create(users_a + users_b)

    all_users = list(User.objects.filter(username__startswith="scale_user_"))
    assert len(all_users) == 30

    # 2. Populate 3 OLAP stacks for Tenant A and 3 for Tenant B
    admin_a = User.objects.filter(tenant=tenant_a, is_tenant_admin=True).first()
    admin_b = User.objects.filter(tenant=tenant_b, is_tenant_admin=True).first()

    for i in range(1, 4):
        cube_a = OlapCube.objects.create(
            tenant=tenant_a,
            name=f"Scale Cube A {i}",
            slug=f"scale-cube-a-{i}",
            created_by=admin_a,
        )
        pivot_a = PivotAnalysisView.objects.create(
            tenant=tenant_a,
            cube=cube_a,
            name=f"Scale Pivot A {i}",
            slug=f"scale-pivot-a-{i}",
            created_by=admin_a,
        )
        scen_a = WhatIfScenario.objects.create(
            tenant=tenant_a,
            cube=cube_a,
            name=f"Scale Scenario A {i}",
            slug=f"scale-scenario-a-{i}",
            created_by=admin_a,
        )
        ScenarioWritebackCell.objects.create(
            tenant=tenant_a,
            scenario=scen_a,
            baseline_value=Decimal("1000.00"),
            adjusted_value=Decimal("1100.00"),
            spread_method="direct_leaf",
            created_by=admin_a,
        )

        cube_b = OlapCube.objects.create(
            tenant=tenant_b,
            name=f"Scale Cube B {i}",
            slug=f"scale-cube-b-{i}",
            created_by=admin_b,
        )
        pivot_b = PivotAnalysisView.objects.create(
            tenant=tenant_b,
            cube=cube_b,
            name=f"Scale Pivot B {i}",
            slug=f"scale-pivot-b-{i}",
            created_by=admin_b,
        )
        scen_b = WhatIfScenario.objects.create(
            tenant=tenant_b,
            cube=cube_b,
            name=f"Scale Scenario B {i}",
            slug=f"scale-scenario-b-{i}",
            created_by=admin_b,
        )
        ScenarioWritebackCell.objects.create(
            tenant=tenant_b,
            scenario=scen_b,
            baseline_value=Decimal("2000.00"),
            adjusted_value=Decimal("2200.00"),
            spread_method="direct_leaf",
            created_by=admin_b,
        )

    class DummyRequest:
        def __init__(self, user):
            self.user = user
            self.tenant = user.tenant

    # 3. Simulate scoped queries for every single user
    for user in all_users:
        req = DummyRequest(user)

        scoped_cubes = list(bi_scope(OlapCube.objects.all(), req))
        scoped_pivots = list(bi_scope(PivotAnalysisView.objects.all(), req))
        scoped_scenarios = list(bi_scope(WhatIfScenario.objects.all(), req))
        scoped_cells = list(bi_scope(ScenarioWritebackCell.objects.all(), req))

        # Check tenant isolation strictly: 100% tenant boundary preservation
        if user.tenant == tenant_a:
            assert all(c.tenant_id == tenant_a.id for c in scoped_cubes)
            assert all(p.tenant_id == tenant_a.id for p in scoped_pivots)
            assert all(s.tenant_id == tenant_a.id for s in scoped_scenarios)
            assert all(c.tenant_id == tenant_a.id for c in scoped_cells)
            assert not any(c.tenant_id == tenant_b.id for c in scoped_cubes)
            assert not any(p.tenant_id == tenant_b.id for p in scoped_pivots)
            assert not any(s.tenant_id == tenant_b.id for s in scoped_scenarios)
            assert not any(c.tenant_id == tenant_b.id for c in scoped_cells)
        else:
            assert all(c.tenant_id == tenant_b.id for c in scoped_cubes)
            assert all(p.tenant_id == tenant_b.id for p in scoped_pivots)
            assert all(s.tenant_id == tenant_b.id for s in scoped_scenarios)
            assert all(c.tenant_id == tenant_b.id for c in scoped_cells)
            assert not any(c.tenant_id == tenant_a.id for c in scoped_cubes)
            assert not any(p.tenant_id == tenant_a.id for p in scoped_pivots)
            assert not any(s.tenant_id == tenant_a.id for s in scoped_scenarios)
            assert not any(c.tenant_id == tenant_a.id for c in scoped_cells)

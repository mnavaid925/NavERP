"""Views test suite for Sub-module 10.11 Performance Scorecards (apps/bi).

Views covered:
1. KpiDefinitions: list, create, detail, edit, delete, refresh
2. PerformanceScorecards: list, create, detail, edit, delete, strategy_map, recalculate
3. ScorecardKpiAssignments: list, create, detail, edit, delete, record_actual
4. StrategicObjectives: list, create, detail, edit, delete
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    KpiDefinition,
    PerformanceScorecard,
    ScorecardKpiAssignment,
    StrategicObjective,
)
from apps.core.models.OrgUnit import OrgUnit


# ==============================================================================
# Module Helpers (named _performancescorecards_*)
# ==============================================================================


def _performancescorecards_create_org_unit(tenant, name="Finance Department"):
    """Helper to create a tenant-scoped OrgUnit instance."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind="department")


def _performancescorecards_create_kpi(tenant, owner, **kwargs):
    """Helper to create a tenant-scoped KpiDefinition instance."""
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "code": "TEST_KPI_CODE",
        "name": "Test Metric KPI",
        "category": "operations",
        "perspective": "internal_process",
        "target_direction": "maximize",
        "unit_of_measure": "percentage",
        "tracking_frequency": "monthly",
        "calculation_type": "manual",
        "target_value": Decimal("90.0000"),
        "warning_threshold": Decimal("75.0000"),
        "critical_threshold": Decimal("60.0000"),
        "current_value": Decimal("85.0000"),
        "status": "active",
        "is_active": True,
    }
    defaults.update(kwargs)
    return KpiDefinition.objects.create(**defaults)


def _performancescorecards_create_scorecard(tenant, owner, **kwargs):
    """Helper to create a tenant-scoped PerformanceScorecard instance."""
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "name": "Operations Balanced Scorecard",
        "scorecard_type": "departmental",
        "review_period": "quarterly",
        "fiscal_year": 2026,
        "financial_weight": Decimal("25.00"),
        "customer_weight": Decimal("25.00"),
        "internal_process_weight": Decimal("25.00"),
        "learning_growth_weight": Decimal("25.00"),
        "status": "active",
        "is_published": True,
    }
    defaults.update(kwargs)
    return PerformanceScorecard.objects.create(**defaults)


def _performancescorecards_create_objective(tenant, owner, **kwargs):
    """Helper to create a tenant-scoped StrategicObjective instance."""
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "code": "TEST_OBJ_CODE",
        "name": "Optimize Operational Workflows",
        "perspective": "internal_process",
        "statement_of_intent": "Reduce cycle time and operational waste by 20%.",
        "rag_status": "green",
        "status": "active",
        "sort_order": 1,
    }
    defaults.update(kwargs)
    return StrategicObjective.objects.create(**defaults)


def _performancescorecards_create_assignment(tenant, scorecard, kpi, objective=None, **kwargs):
    """Helper to create a tenant-scoped ScorecardKpiAssignment instance."""
    defaults = {
        "tenant": tenant,
        "scorecard": scorecard,
        "kpi": kpi,
        "objective": objective,
        "perspective": kpi.perspective or "financial",
        "weight": Decimal("25.00"),
        "target_value": kpi.target_value or Decimal("100.0000"),
        "actual_value": kpi.current_value or Decimal("90.0000"),
        "rag_status": "green",
        "trend_direction": "improving",
        "sort_order": 1,
    }
    defaults.update(kwargs)
    return ScorecardKpiAssignment.objects.create(**defaults)


# ==============================================================================
# 1. KpiDefinition View Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_kpi_list_view_200_and_context(client_a, kpi_definition_a):
    """Test kpi_definition_list returns 200, contains expected context keys, choices, and counts."""
    url = reverse("bi:kpi_definition_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "kpis" in resp.context
    assert "status_choices" in resp.context
    assert "perspective_choices" in resp.context
    assert "direction_choices" in resp.context
    assert "calc_type_choices" in resp.context
    assert "departments" in resp.context
    assert "stats" in resp.context

    stats = resp.context["stats"]
    assert stats["total"] >= 1
    assert stats["active"] >= 1
    assert "under_review" in stats
    assert "on_target" in stats

    content = resp.content.decode()
    assert kpi_definition_a.number in content
    assert kpi_definition_a.name in content


@pytest.mark.django_db
def test_performancescorecards_kpi_list_view_filtering(client_a, tenant_a, admin_user, kpi_definition_a):
    """Test kpi_definition_list filters by q, status, perspective, direction, calc_type, and department."""
    dept = _performancescorecards_create_org_unit(tenant_a, name="Customer Operations")
    kpi2 = _performancescorecards_create_kpi(
        tenant=tenant_a,
        owner=admin_user,
        code="CSAT_NPS_METRIC",
        name="Customer Net Promoter Score",
        category="customer_care",
        perspective="customer",
        target_direction="minimize",
        calculation_type="automated",
        status="under_review",
        department=dept,
    )
    url = reverse("bi:kpi_definition_list")

    # Search query matching KPI 1
    resp_q1 = client_a.get(url, {"q": kpi_definition_a.code})
    assert resp_q1.status_code == 200
    results_q1 = list(resp_q1.context["kpis"])
    assert kpi_definition_a in results_q1
    assert kpi2 not in results_q1

    # Search query matching KPI 2
    resp_q2 = client_a.get(url, {"q": "Net Promoter"})
    assert resp_q2.status_code == 200
    results_q2 = list(resp_q2.context["kpis"])
    assert kpi2 in results_q2
    assert kpi_definition_a not in results_q2

    # Filter by status
    resp_status = client_a.get(url, {"status": "under_review"})
    assert resp_status.status_code == 200
    results_status = list(resp_status.context["kpis"])
    assert kpi2 in results_status
    assert kpi_definition_a not in results_status

    # Filter by perspective
    resp_persp = client_a.get(url, {"perspective": "customer"})
    assert resp_persp.status_code == 200
    results_persp = list(resp_persp.context["kpis"])
    assert kpi2 in results_persp
    assert kpi_definition_a not in results_persp

    # Filter by target_direction
    resp_dir = client_a.get(url, {"target_direction": "minimize"})
    assert resp_dir.status_code == 200
    results_dir = list(resp_dir.context["kpis"])
    assert kpi2 in results_dir
    assert kpi_definition_a not in results_dir

    # Filter by calculation_type
    resp_calc = client_a.get(url, {"calculation_type": "automated"})
    assert resp_calc.status_code == 200
    results_calc = list(resp_calc.context["kpis"])
    assert kpi2 in results_calc
    assert kpi_definition_a not in results_calc

    # Filter by department
    resp_dept = client_a.get(url, {"department": str(dept.pk)})
    assert resp_dept.status_code == 200
    results_dept = list(resp_dept.context["kpis"])
    assert kpi2 in results_dept
    assert kpi_definition_a not in results_dept


@pytest.mark.django_db
def test_performancescorecards_kpi_list_view_resiliency_junk_params(client_a, kpi_definition_a):
    """Test kpi_definition_list handles junk parameters without 500 error."""
    url = reverse("bi:kpi_definition_list")
    resp = client_a.get(
        url,
        {
            "department": "abc_not_an_int",
            "fiscal_year": "xyz_junk",
            "status": "bogus_status_value",
            "target_direction": "invalid_dir",
            "calculation_type": "none_existing",
            "page": "invalid_page_num",
        },
    )
    assert resp.status_code == 200
    assert "kpis" in resp.context


@pytest.mark.django_db
def test_performancescorecards_kpi_list_view_empty_state(client_a):
    """Test kpi_definition_list renders empty-state message when no KPIs match."""
    url = reverse("bi:kpi_definition_list")
    resp = client_a.get(url, {"q": "NON_EXISTING_KPI_SEARCH_TOKEN_XYZ"})

    assert resp.status_code == 200
    assert len(resp.context["kpis"]) == 0
    content = resp.content.decode()
    assert "No KPI Definitions Found" in content
    assert "empty-state" in content


@pytest.mark.django_db
def test_performancescorecards_kpi_detail_view(client_a, kpi_definition_a, scorecard_kpi_assignment_a):
    """Test kpi_definition_detail returns 200 with object identifier and pinned context keys."""
    url = reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["kpi"] == kpi_definition_a
    assert "assignments" in resp.context
    assert "rag_status" in resp.context
    assert "refresh_form" in resp.context
    assert scorecard_kpi_assignment_a in resp.context["assignments"]

    content = resp.content.decode()
    assert kpi_definition_a.number in content
    assert kpi_definition_a.name in content


@pytest.mark.django_db
def test_performancescorecards_kpi_create_view_get(client_a):
    """Test GET kpi_definition_create renders form with is_edit=False and form action."""
    url = reverse("bi:kpi_definition_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["kpi"] is None


@pytest.mark.django_db
def test_performancescorecards_kpi_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test POST kpi_definition_create persists record, assigns tenant/owner, and redirects."""
    url = reverse("bi:kpi_definition_create")
    payload = {
        "code": "OP_CYCLE_TIME",
        "name": "Manufacturing Order Cycle Time",
        "description": "Average hours from order receipt to manufacturing completion.",
        "category": "operations",
        "perspective": "internal_process",
        "target_direction": "minimize",
        "unit_of_measure": "hours",
        "tracking_frequency": "weekly",
        "calculation_type": "manual",
        "target_value": "48.0000",
        "warning_threshold": "60.0000",
        "critical_threshold": "72.0000",
        "current_value": "52.5000",
        "status": "active",
        "is_active": True,
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 302
    created = KpiDefinition.objects.filter(tenant=tenant_a, code="OP_CYCLE_TIME").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.owner == admin_user
    assert created.name == "Manufacturing Order Cycle Time"
    assert created.number.startswith("BKPI-")
    assert resp.url == created.get_absolute_url()


@pytest.mark.django_db
def test_performancescorecards_kpi_create_view_post_invalid(client_a):
    """Test POST kpi_definition_create with invalid data re-renders form with errors."""
    url = reverse("bi:kpi_definition_create")
    payload = {
        "code": "",  # Required
        "name": "",  # Required
        "perspective": "financial",
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert "code" in resp.context["form"].errors
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_kpi_edit_view(client_a, kpi_definition_a):
    """Test GET and POST kpi_definition_edit updates KPI attributes and redirects."""
    url = reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["kpi"] == kpi_definition_a

    # POST valid update
    payload = {
        "code": kpi_definition_a.code,
        "name": "Acme Updated Revenue Metric",
        "category": kpi_definition_a.category,
        "perspective": kpi_definition_a.perspective,
        "target_direction": kpi_definition_a.target_direction,
        "unit_of_measure": kpi_definition_a.unit_of_measure,
        "tracking_frequency": kpi_definition_a.tracking_frequency,
        "calculation_type": kpi_definition_a.calculation_type,
        "target_value": "18.0000",
        "current_value": str(kpi_definition_a.current_value),
        "status": "active",
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == kpi_definition_a.get_absolute_url()

    kpi_definition_a.refresh_from_db()
    assert kpi_definition_a.name == "Acme Updated Revenue Metric"
    assert kpi_definition_a.target_value == Decimal("18.0000")


@pytest.mark.django_db
def test_performancescorecards_kpi_edit_view_post_invalid(client_a, kpi_definition_a):
    """Test POST kpi_definition_edit with empty required name re-renders form with errors."""
    url = reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk})
    resp = client_a.post(url, {"code": kpi_definition_a.code, "name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_kpi_delete_view_post_and_guard(client_a, tenant_a, admin_user):
    """Test POST kpi_definition_delete removes record; GET returns 405 Method Not Allowed."""
    kpi_to_delete = _performancescorecards_create_kpi(
        tenant=tenant_a,
        owner=admin_user,
        code="KPI_TO_BE_DELETED",
        name="Disposable KPI Definition",
    )
    url = reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_to_delete.pk})

    # GET must return 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert KpiDefinition.objects.filter(pk=kpi_to_delete.pk).exists()

    # POST deletes record and redirects to list
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:kpi_definition_list")
    assert not KpiDefinition.objects.filter(pk=kpi_to_delete.pk).exists()


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_action_post_and_guard(client_a, kpi_definition_a):
    """Test POST kpi_definition_refresh updates current/previous values and timestamp; GET returns 405."""
    url = reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST valid new measurement
    old_current = kpi_definition_a.current_value
    payload = {"new_value": "17.7500", "notes": "Audited fiscal measurement"}
    resp_post = client_a.post(url, payload)

    assert resp_post.status_code == 302
    assert resp_post.url == kpi_definition_a.get_absolute_url()

    kpi_definition_a.refresh_from_db()
    assert kpi_definition_a.current_value == Decimal("17.7500")
    assert kpi_definition_a.previous_value == old_current
    assert kpi_definition_a.last_calculated_at is not None


@pytest.mark.django_db
def test_performancescorecards_kpi_refresh_action_invalid_value(client_a, kpi_definition_a):
    """Test POST kpi_definition_refresh with invalid data redirects with error message."""
    url = reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk})
    resp = client_a.post(url, {"new_value": "not-a-number"})

    assert resp.status_code == 302
    assert resp.url == kpi_definition_a.get_absolute_url()


# ==============================================================================
# 2. PerformanceScorecard View Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_scorecard_list_view_200_and_context(client_a, performance_scorecard_a):
    """Test performance_scorecard_list returns 200, context choices, stats, and scorecard record."""
    url = reverse("bi:performance_scorecard_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "scorecards" in resp.context
    assert "type_choices" in resp.context
    assert "status_choices" in resp.context
    assert "rag_choices" in resp.context
    assert "period_choices" in resp.context
    assert "org_units" in resp.context
    assert "stats" in resp.context

    stats = resp.context["stats"]
    assert stats["total"] >= 1
    assert stats["active"] >= 1
    assert "on_track" in stats
    assert "needs_attention" in stats
    assert "critical" in stats

    content = resp.content.decode()
    assert performance_scorecard_a.number in content
    assert performance_scorecard_a.name in content


@pytest.mark.django_db
def test_performancescorecards_scorecard_list_view_filtering(
    client_a, tenant_a, admin_user, performance_scorecard_a
):
    """Test performance_scorecard_list filters by q, type, status, rag_status, period, fiscal_year, org_unit."""
    org_unit = _performancescorecards_create_org_unit(tenant_a, name="Supply Chain Unit")
    sc2 = _performancescorecards_create_scorecard(
        tenant=tenant_a,
        owner=admin_user,
        name="Supply Chain Operational Scorecard",
        scorecard_type="departmental",
        review_period="annual",
        fiscal_year=2025,
        status="draft",
        overall_rag_status="amber",
        org_unit=org_unit,
    )
    url = reverse("bi:performance_scorecard_list")

    # Search keyword
    resp_q = client_a.get(url, {"q": "Supply Chain"})
    assert resp_q.status_code == 200
    results_q = list(resp_q.context["scorecards"])
    assert sc2 in results_q
    assert performance_scorecard_a not in results_q

    # Filter by scorecard_type
    resp_type = client_a.get(url, {"scorecard_type": "departmental"})
    assert resp_type.status_code == 200
    results_type = list(resp_type.context["scorecards"])
    assert sc2 in results_type
    assert performance_scorecard_a not in results_type

    # Filter by status
    resp_status = client_a.get(url, {"status": "draft"})
    assert resp_status.status_code == 200
    results_status = list(resp_status.context["scorecards"])
    assert sc2 in results_status
    assert performance_scorecard_a not in results_status

    # Filter by rag_status
    resp_rag = client_a.get(url, {"rag_status": "amber"})
    assert resp_rag.status_code == 200
    results_rag = list(resp_rag.context["scorecards"])
    assert sc2 in results_rag
    assert performance_scorecard_a not in results_rag

    # Filter by review_period
    resp_period = client_a.get(url, {"review_period": "annual"})
    assert resp_period.status_code == 200
    results_period = list(resp_period.context["scorecards"])
    assert sc2 in results_period
    assert performance_scorecard_a not in results_period

    # Filter by fiscal_year
    resp_year = client_a.get(url, {"fiscal_year": "2025"})
    assert resp_year.status_code == 200
    results_year = list(resp_year.context["scorecards"])
    assert sc2 in results_year
    assert performance_scorecard_a not in results_year

    # Filter by org_unit
    resp_org = client_a.get(url, {"org_unit": str(org_unit.pk)})
    assert resp_org.status_code == 200
    results_org = list(resp_org.context["scorecards"])
    assert sc2 in results_org
    assert performance_scorecard_a not in results_org


@pytest.mark.django_db
def test_performancescorecards_scorecard_list_view_resiliency_junk_params(client_a, performance_scorecard_a):
    """Test performance_scorecard_list handles junk parameters without crashing."""
    url = reverse("bi:performance_scorecard_list")
    resp = client_a.get(
        url,
        {
            "department": "not_an_int",
            "fiscal_year": "year_bad",
            "org_unit": "invalid_org",
            "status": "bogus_status",
            "rag_status": "bogus_rag",
            "review_period": "bogus_period",
        },
    )
    assert resp.status_code == 200
    assert "scorecards" in resp.context


@pytest.mark.django_db
def test_performancescorecards_scorecard_list_view_empty_state(client_a):
    """Test performance_scorecard_list renders empty-state when no scorecards match query."""
    url = reverse("bi:performance_scorecard_list")
    resp = client_a.get(url, {"q": "NON_EXISTENT_SCORECARD_TOKEN_XYZ"})

    assert resp.status_code == 200
    assert len(resp.context["scorecards"]) == 0
    content = resp.content.decode()
    assert "No Performance Scorecards Found" in content
    assert "empty-state" in content


@pytest.mark.django_db
def test_performancescorecards_scorecard_detail_view(
    client_a, performance_scorecard_a, scorecard_kpi_assignment_a
):
    """Test performance_scorecard_detail returns 200 with all pinned perspective summaries and form."""
    url = reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["scorecard"] == performance_scorecard_a
    assert "financial_kpis" in resp.context
    assert "customer_kpis" in resp.context
    assert "process_kpis" in resp.context
    assert "learning_kpis" in resp.context
    assert "perspective_summary" in resp.context
    assert "perspective_scores" in resp.context
    assert "recalculate_form" in resp.context

    # Assert assigned KPI is in financial_kpis
    assert scorecard_kpi_assignment_a in resp.context["financial_kpis"]

    content = resp.content.decode()
    assert performance_scorecard_a.number in content
    assert performance_scorecard_a.name in content


@pytest.mark.django_db
def test_performancescorecards_scorecard_create_view_get(client_a):
    """Test GET performance_scorecard_create renders form with is_edit=False."""
    url = reverse("bi:performance_scorecard_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["scorecard"] is None


@pytest.mark.django_db
def test_performancescorecards_scorecard_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test POST performance_scorecard_create persists scorecard with 100% perspective weight sum."""
    url = reverse("bi:performance_scorecard_create")
    payload = {
        "name": "Global 2027 Strategic Scorecard",
        "description": "Multi-year corporate scorecard aligned with Vision 2030",
        "scorecard_type": "balanced_scorecard",
        "review_period": "quarterly",
        "fiscal_year": 2027,
        "financial_weight": "25.00",
        "customer_weight": "25.00",
        "internal_process_weight": "25.00",
        "learning_growth_weight": "25.00",
        "status": "active",
        "is_published": True,
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 302
    created = PerformanceScorecard.objects.filter(tenant=tenant_a, name="Global 2027 Strategic Scorecard").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.owner == admin_user
    assert created.number.startswith("BSCR-")
    assert resp.url == created.get_absolute_url()


@pytest.mark.django_db
def test_performancescorecards_scorecard_create_view_post_invalid(client_a):
    """Test POST performance_scorecard_create with invalid weights sum re-renders form with errors."""
    url = reverse("bi:performance_scorecard_create")
    payload = {
        "name": "Invalid Weight Scorecard",
        "scorecard_type": "balanced_scorecard",
        "review_period": "quarterly",
        "fiscal_year": 2026,
        "financial_weight": "20.00",
        "customer_weight": "20.00",
        "internal_process_weight": "20.00",
        "learning_growth_weight": "20.00",  # Sum = 80.00 != 100.00
        "status": "draft",
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_edit_view(client_a, performance_scorecard_a):
    """Test GET and POST performance_scorecard_edit updates scorecard and triggers recalculation."""
    url = reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["scorecard"] == performance_scorecard_a

    # POST valid update
    payload = {
        "name": "Acme Balanced Scorecard 2026 Revised",
        "scorecard_type": performance_scorecard_a.scorecard_type,
        "review_period": performance_scorecard_a.review_period,
        "fiscal_year": performance_scorecard_a.fiscal_year,
        "financial_weight": "30.00",
        "customer_weight": "30.00",
        "internal_process_weight": "20.00",
        "learning_growth_weight": "20.00",  # Sum = 100.00
        "status": "active",
        "is_published": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == performance_scorecard_a.get_absolute_url()

    performance_scorecard_a.refresh_from_db()
    assert performance_scorecard_a.name == "Acme Balanced Scorecard 2026 Revised"
    assert performance_scorecard_a.financial_weight == Decimal("30.00")


@pytest.mark.django_db
def test_performancescorecards_scorecard_edit_view_post_invalid(client_a, performance_scorecard_a):
    """Test POST performance_scorecard_edit with invalid weights re-renders form with errors."""
    url = reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk})
    payload = {
        "name": performance_scorecard_a.name,
        "financial_weight": "50.00",
        "customer_weight": "50.00",
        "internal_process_weight": "10.00",
        "learning_growth_weight": "10.00",  # Sum = 120.00 != 100.00
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_scorecard_delete_view_post_and_guard(client_a, tenant_a, admin_user):
    """Test POST performance_scorecard_delete removes scorecard; GET returns 405."""
    sc_to_delete = _performancescorecards_create_scorecard(
        tenant=tenant_a,
        owner=admin_user,
        name="Scorecard Scheduled for Deletion",
    )
    url = reverse("bi:performance_scorecard_delete", kwargs={"pk": sc_to_delete.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert PerformanceScorecard.objects.filter(pk=sc_to_delete.pk).exists()

    # POST deletes record
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:performance_scorecard_list")
    assert not PerformanceScorecard.objects.filter(pk=sc_to_delete.pk).exists()


@pytest.mark.django_db
def test_performancescorecards_scorecard_recalculate_action_post_and_guard(
    client_a, performance_scorecard_a, scorecard_kpi_assignment_a
):
    """Test POST performance_scorecard_recalculate triggers score calculation; GET returns 405."""
    url = reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST recalculates and redirects
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == performance_scorecard_a.get_absolute_url()

    performance_scorecard_a.refresh_from_db()
    assert performance_scorecard_a.overall_score is not None
    assert performance_scorecard_a.overall_rag_status in ["green", "amber", "red"]


@pytest.mark.django_db
def test_performancescorecards_scorecard_strategy_map_view(
    client_a, performance_scorecard_a, strategic_objective_a
):
    """Test performance_scorecard_strategy_map returns 200 with all 4 Kaplan-Norton perspectives."""
    url = reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["scorecard"] == performance_scorecard_a
    assert "financial_objectives" in resp.context
    assert "customer_objectives" in resp.context
    assert "process_objectives" in resp.context
    assert "learning_objectives" in resp.context
    assert "strategy_stats" in resp.context

    # strategic_objective_a is in financial perspective
    assert strategic_objective_a in resp.context["financial_objectives"]

    content = resp.content.decode()
    assert "Financial Perspective" in content
    assert "Customer Perspective" in content
    assert "Internal Process Perspective" in content
    assert "Learning & Growth Perspective" in content


# ==============================================================================
# 3. ScorecardKpiAssignment View Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_assignment_list_view_200_and_context(client_a, scorecard_kpi_assignment_a):
    """Test scorecard_kpi_assignment_list returns 200, context choices, stats, and assignment record."""
    url = reverse("bi:scorecard_kpi_assignment_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "assignments" in resp.context
    assert "scorecards" in resp.context
    assert "perspective_choices" in resp.context
    assert "rag_choices" in resp.context
    assert "trend_choices" in resp.context
    assert "stats" in resp.context

    stats = resp.context["stats"]
    assert stats["total"] >= 1
    assert "on_track" in stats
    assert "improving" in stats
    assert "critical" in stats

    content = resp.content.decode()
    assert scorecard_kpi_assignment_a.number in content
    assert scorecard_kpi_assignment_a.kpi.name in content


@pytest.mark.django_db
def test_performancescorecards_assignment_list_view_filtering(
    client_a, tenant_a, admin_user, performance_scorecard_a, scorecard_kpi_assignment_a
):
    """Test scorecard_kpi_assignment_list filters by q, scorecard, perspective, rag_status, trend_direction."""
    kpi2 = _performancescorecards_create_kpi(
        tenant=tenant_a,
        owner=admin_user,
        code="SYS_UPTIME",
        name="Production System Uptime",
        perspective="internal_process",
        target_value=Decimal("90.0000"),
        warning_threshold=Decimal("75.0000"),
        critical_threshold=Decimal("60.0000"),
        previous_value=Decimal("70.0000"),
    )
    assign2 = _performancescorecards_create_assignment(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi2,
        perspective="internal_process",
        target_value=Decimal("90.0000"),
        actual_value=Decimal("50.0000"),  # Below critical (60.0000) -> red; < prev (70.0000) -> deteriorating
    )
    url = reverse("bi:scorecard_kpi_assignment_list")

    # Search keyword
    resp_q = client_a.get(url, {"q": "System Uptime"})
    assert resp_q.status_code == 200
    results_q = list(resp_q.context["assignments"])
    assert assign2 in results_q
    assert scorecard_kpi_assignment_a not in results_q

    # Filter by scorecard
    resp_sc = client_a.get(url, {"scorecard": str(performance_scorecard_a.pk)})
    assert resp_sc.status_code == 200
    assert assign2 in list(resp_sc.context["assignments"])

    # Filter by perspective
    resp_persp = client_a.get(url, {"perspective": "internal_process"})
    assert resp_persp.status_code == 200
    results_persp = list(resp_persp.context["assignments"])
    assert assign2 in results_persp
    assert scorecard_kpi_assignment_a not in results_persp

    # Filter by rag_status
    resp_rag = client_a.get(url, {"rag_status": "red"})
    assert resp_rag.status_code == 200
    results_rag = list(resp_rag.context["assignments"])
    assert assign2 in results_rag
    assert scorecard_kpi_assignment_a not in results_rag

    # Filter by trend_direction
    resp_trend = client_a.get(url, {"trend_direction": "deteriorating"})
    assert resp_trend.status_code == 200
    results_trend = list(resp_trend.context["assignments"])
    assert assign2 in results_trend
    assert scorecard_kpi_assignment_a not in results_trend


@pytest.mark.django_db
def test_performancescorecards_assignment_list_view_resiliency_junk_params(
    client_a, scorecard_kpi_assignment_a
):
    """Test scorecard_kpi_assignment_list handles junk parameters without crashing."""
    url = reverse("bi:scorecard_kpi_assignment_list")
    resp = client_a.get(
        url,
        {
            "scorecard": "invalid_scorecard_pk",
            "perspective": "non_existent_persp",
            "rag_status": "bogus_rag",
            "trend_direction": "bogus_trend",
        },
    )
    assert resp.status_code == 200
    assert "assignments" in resp.context


@pytest.mark.django_db
def test_performancescorecards_assignment_list_view_empty_state(client_a):
    """Test scorecard_kpi_assignment_list renders empty-state when no assignments match query."""
    url = reverse("bi:scorecard_kpi_assignment_list")
    resp = client_a.get(url, {"q": "NON_EXISTING_ASSIGNMENT_TOKEN_XYZ"})

    assert resp.status_code == 200
    assert len(resp.context["assignments"]) == 0
    content = resp.content.decode()
    assert "No Target Assignments Found" in content
    assert "empty-state" in content


@pytest.mark.django_db
def test_performancescorecards_assignment_detail_view(client_a, scorecard_kpi_assignment_a):
    """Test scorecard_kpi_assignment_detail returns 200 with assignment identifier."""
    url = reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["assignment"] == scorecard_kpi_assignment_a

    content = resp.content.decode()
    assert scorecard_kpi_assignment_a.number in content
    assert scorecard_kpi_assignment_a.kpi.name in content


@pytest.mark.django_db
def test_performancescorecards_assignment_create_view_get(client_a, performance_scorecard_a):
    """Test GET scorecard_kpi_assignment_create populates initial query params."""
    url = reverse("bi:scorecard_kpi_assignment_create")
    resp = client_a.get(url, {"scorecard": str(performance_scorecard_a.pk), "perspective": "financial"})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["assignment"] is None
    form = resp.context["form"]
    assert form.initial.get("scorecard") == performance_scorecard_a.pk
    assert form.initial.get("perspective") == "financial"


@pytest.mark.django_db
def test_performancescorecards_assignment_create_view_post_valid(
    client_a, tenant_a, admin_user, performance_scorecard_a, strategic_objective_a
):
    """Test POST scorecard_kpi_assignment_create assigns KPI to scorecard and redirects."""
    kpi_new = _performancescorecards_create_kpi(
        tenant=tenant_a,
        owner=admin_user,
        code="NEW_FIN_METRIC",
        name="EBITDA Margin Percentage",
        perspective="financial",
    )
    url = reverse("bi:scorecard_kpi_assignment_create")
    payload = {
        "scorecard": performance_scorecard_a.pk,
        "kpi": kpi_new.pk,
        "objective": strategic_objective_a.pk,
        "perspective": "financial",
        "weight": "20.00",
        "target_value": "22.5000",
        "actual_value": "21.0000",
        "sort_order": 5,
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 302
    assert resp.url == performance_scorecard_a.get_absolute_url()

    created = ScorecardKpiAssignment.objects.filter(
        tenant=tenant_a, scorecard=performance_scorecard_a, kpi=kpi_new
    ).first()
    assert created is not None
    assert created.weight == Decimal("20.00")
    assert created.number.startswith("BSCI-")


@pytest.mark.django_db
def test_performancescorecards_assignment_create_view_post_invalid(client_a):
    """Test POST scorecard_kpi_assignment_create with missing required fields re-renders form."""
    url = reverse("bi:scorecard_kpi_assignment_create")
    resp = client_a.post(url, {})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_assignment_edit_view(client_a, scorecard_kpi_assignment_a):
    """Test GET and POST scorecard_kpi_assignment_edit updates assignment attributes."""
    url = reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["assignment"] == scorecard_kpi_assignment_a

    # POST valid update
    payload = {
        "scorecard": scorecard_kpi_assignment_a.scorecard.pk,
        "kpi": scorecard_kpi_assignment_a.kpi.pk,
        "perspective": scorecard_kpi_assignment_a.perspective,
        "weight": "35.00",
        "target_value": "20.0000",
        "actual_value": "19.5000",
        "sort_order": 8,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == scorecard_kpi_assignment_a.scorecard.get_absolute_url()

    scorecard_kpi_assignment_a.refresh_from_db()
    assert scorecard_kpi_assignment_a.weight == Decimal("35.00")
    assert scorecard_kpi_assignment_a.sort_order == 8


@pytest.mark.django_db
def test_performancescorecards_assignment_delete_view_post_and_guard(
    client_a, tenant_a, admin_user, performance_scorecard_a
):
    """Test POST scorecard_kpi_assignment_delete removes assignment; GET returns 405."""
    kpi_del = _performancescorecards_create_kpi(
        tenant=tenant_a,
        owner=admin_user,
        code="DISPOSABLE_KPI_FOR_ASSIGN",
        name="Disposable KPI Assignment Target",
    )
    assign_del = _performancescorecards_create_assignment(
        tenant=tenant_a,
        scorecard=performance_scorecard_a,
        kpi=kpi_del,
    )
    url = reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": assign_del.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert ScorecardKpiAssignment.objects.filter(pk=assign_del.pk).exists()

    # POST deletes record and redirects to scorecard detail
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == performance_scorecard_a.get_absolute_url()
    assert not ScorecardKpiAssignment.objects.filter(pk=assign_del.pk).exists()


@pytest.mark.django_db
def test_performancescorecards_assignment_record_actual_view(client_a, scorecard_kpi_assignment_a):
    """Test GET and POST scorecard_kpi_assignment_record_actual updates measurement value."""
    url = reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["assignment"] == scorecard_kpi_assignment_a
    assert "form" in resp_get.context

    # POST valid update
    payload = {
        "actual_value": "16.8500",
        "manager_notes": "Exceeded monthly expectation due to accelerated contracts.",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == scorecard_kpi_assignment_a.scorecard.get_absolute_url()

    scorecard_kpi_assignment_a.refresh_from_db()
    assert scorecard_kpi_assignment_a.actual_value == Decimal("16.8500")
    assert "accelerated contracts" in scorecard_kpi_assignment_a.manager_notes


@pytest.mark.django_db
def test_performancescorecards_assignment_record_actual_view_post_invalid(
    client_a, scorecard_kpi_assignment_a
):
    """Test POST scorecard_kpi_assignment_record_actual with bad input re-renders form with errors."""
    url = reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk})
    resp = client_a.post(url, {"actual_value": "not-a-number"})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert "actual_value" in resp.context["form"].errors


# ==============================================================================
# 4. StrategicObjective View Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_objective_list_view_200_and_context(client_a, strategic_objective_a):
    """Test strategic_objective_list returns 200, context choices, stats, and objective record."""
    url = reverse("bi:strategic_objective_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "objectives" in resp.context
    assert "perspective_choices" in resp.context
    assert "status_choices" in resp.context
    assert "rag_choices" in resp.context
    assert "org_units" in resp.context
    assert "stats" in resp.context

    stats = resp.context["stats"]
    assert stats["total"] >= 1
    assert stats["active"] >= 1
    assert "achieved" in stats
    assert "on_track" in stats

    content = resp.content.decode()
    assert strategic_objective_a.number in content
    assert strategic_objective_a.name in content


@pytest.mark.django_db
def test_performancescorecards_objective_list_view_filtering(
    client_a, tenant_a, admin_user, strategic_objective_a
):
    """Test strategic_objective_list filters by q, perspective, status, rag_status, org_unit."""
    org_unit = _performancescorecards_create_org_unit(tenant_a, name="Customer Success Unit")
    obj2 = _performancescorecards_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        code="RETAIN_CUSTOMERS_OBJ",
        name="Achieve 98% Net Customer Retention",
        perspective="customer",
        statement_of_intent="Strengthen post-sales customer success enablement and QBRs.",
        status="achieved",
        rag_status="green",
        org_unit=org_unit,
    )
    url = reverse("bi:strategic_objective_list")

    # Search keyword
    resp_q = client_a.get(url, {"q": "Retention"})
    assert resp_q.status_code == 200
    results_q = list(resp_q.context["objectives"])
    assert obj2 in results_q
    assert strategic_objective_a not in results_q

    # Filter by perspective
    resp_persp = client_a.get(url, {"perspective": "customer"})
    assert resp_persp.status_code == 200
    results_persp = list(resp_persp.context["objectives"])
    assert obj2 in results_persp
    assert strategic_objective_a not in results_persp

    # Filter by status
    resp_status = client_a.get(url, {"status": "achieved"})
    assert resp_status.status_code == 200
    results_status = list(resp_status.context["objectives"])
    assert obj2 in results_status
    assert strategic_objective_a not in results_status

    # Filter by org_unit
    resp_org = client_a.get(url, {"org_unit": str(org_unit.pk)})
    assert resp_org.status_code == 200
    results_org = list(resp_org.context["objectives"])
    assert obj2 in results_org
    assert strategic_objective_a not in results_org


@pytest.mark.django_db
def test_performancescorecards_objective_list_view_resiliency_junk_params(client_a, strategic_objective_a):
    """Test strategic_objective_list handles junk parameters without crashing."""
    url = reverse("bi:strategic_objective_list")
    resp = client_a.get(
        url,
        {
            "org_unit": "invalid_pk_str",
            "perspective": "non_existent_persp",
            "status": "bogus_status_code",
            "rag_status": "bogus_rag_value",
        },
    )
    assert resp.status_code == 200
    assert "objectives" in resp.context


@pytest.mark.django_db
def test_performancescorecards_objective_list_view_empty_state(client_a):
    """Test strategic_objective_list renders empty-state when no objectives match query."""
    url = reverse("bi:strategic_objective_list")
    resp = client_a.get(url, {"q": "NON_EXISTENT_OBJECTIVE_TOKEN_XYZ"})

    assert resp.status_code == 200
    assert len(resp.context["objectives"]) == 0
    content = resp.content.decode()
    assert "No Strategic Objectives Defined" in content
    assert "empty-state" in content


@pytest.mark.django_db
def test_performancescorecards_objective_detail_view(
    client_a, tenant_a, admin_user, strategic_objective_a, scorecard_kpi_assignment_a
):
    """Test strategic_objective_detail returns 200 with child objectives and assigned KPIs."""
    child_obj = _performancescorecards_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        code="SUB_OBJ_GROWTH",
        name="Enterprise Tier Sales Penetration",
        parent_objective=strategic_objective_a,
    )
    url = reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert resp.context["objective"] == strategic_objective_a
    assert "child_objectives" in resp.context
    assert "assigned_kpis" in resp.context
    assert child_obj in resp.context["child_objectives"]
    assert scorecard_kpi_assignment_a in resp.context["assigned_kpis"]

    content = resp.content.decode()
    assert strategic_objective_a.number in content
    assert strategic_objective_a.name in content


@pytest.mark.django_db
def test_performancescorecards_objective_create_view_get(client_a):
    """Test GET strategic_objective_create renders form with is_edit=False."""
    url = reverse("bi:strategic_objective_create")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["objective"] is None


@pytest.mark.django_db
def test_performancescorecards_objective_create_view_post_valid(client_a, tenant_a, admin_user):
    """Test POST strategic_objective_create persists objective, assigns tenant/owner, and redirects."""
    url = reverse("bi:strategic_objective_create")
    payload = {
        "code": "TECH_MODERNIZE",
        "name": "Cloud Native Modernization",
        "perspective": "learning_growth",
        "statement_of_intent": "Migrate all legacy monolith components to microservices architectures.",
        "target_date": "2027-12-31",
        "status": "active",
        "sort_order": 2,
    }
    resp = client_a.post(url, payload)

    assert resp.status_code == 302
    created = StrategicObjective.objects.filter(tenant=tenant_a, code="TECH_MODERNIZE").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.owner == admin_user
    assert created.name == "Cloud Native Modernization"
    assert created.number.startswith("BOBJ-")
    assert resp.url == created.get_absolute_url()


@pytest.mark.django_db
def test_performancescorecards_objective_create_view_post_invalid(client_a):
    """Test POST strategic_objective_create with missing required fields re-renders form."""
    url = reverse("bi:strategic_objective_create")
    resp = client_a.post(url, {"code": "", "name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_objective_edit_view(client_a, strategic_objective_a):
    """Test GET and POST strategic_objective_edit updates objective and recalculates alignment."""
    url = reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["objective"] == strategic_objective_a

    # POST valid update
    payload = {
        "code": strategic_objective_a.code,
        "name": "Acme Revised Sustainable Growth",
        "perspective": strategic_objective_a.perspective,
        "statement_of_intent": "Updated vision statement for enterprise leadership.",
        "status": "active",
        "sort_order": 1,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post.url == strategic_objective_a.get_absolute_url()

    strategic_objective_a.refresh_from_db()
    assert strategic_objective_a.name == "Acme Revised Sustainable Growth"
    assert "enterprise leadership" in strategic_objective_a.statement_of_intent


@pytest.mark.django_db
def test_performancescorecards_objective_edit_view_post_invalid(client_a, strategic_objective_a):
    """Test POST strategic_objective_edit with empty required name re-renders form with errors."""
    url = reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk})
    resp = client_a.post(url, {"code": strategic_objective_a.code, "name": ""})

    assert resp.status_code == 200
    assert "form" in resp.context
    assert "name" in resp.context["form"].errors


@pytest.mark.django_db
def test_performancescorecards_objective_delete_view_post_and_guard(client_a, tenant_a, admin_user):
    """Test POST strategic_objective_delete removes objective; GET returns 405."""
    obj_del = _performancescorecards_create_objective(
        tenant=tenant_a,
        owner=admin_user,
        code="OBJ_SCHEDULED_DEL",
        name="Disposable Strategic Objective",
    )
    url = reverse("bi:strategic_objective_delete", kwargs={"pk": obj_del.pk})

    # GET returns 405 Method Not Allowed
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405
    assert StrategicObjective.objects.filter(pk=obj_del.pk).exists()

    # POST deletes record and redirects to list
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:strategic_objective_list")
    assert not StrategicObjective.objects.filter(pk=obj_del.pk).exists()


# ==============================================================================
# 5. Authentication & Anonymous Access Tests
# ==============================================================================


@pytest.mark.django_db
def test_performancescorecards_anonymous_requests_redirect_to_login(
    anon_client, kpi_definition_a, performance_scorecard_a, scorecard_kpi_assignment_a, strategic_objective_a
):
    """Test all performance scorecards views redirect unauthenticated requests to login."""
    endpoints = [
        # KPI endpoints
        reverse("bi:kpi_definition_list"),
        reverse("bi:kpi_definition_create"),
        reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}),
        # Scorecard endpoints
        reverse("bi:performance_scorecard_list"),
        reverse("bi:performance_scorecard_create"),
        reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_a.pk}),
        # Assignment endpoints
        reverse("bi:scorecard_kpi_assignment_list"),
        reverse("bi:scorecard_kpi_assignment_create"),
        reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        # Objective endpoints
        reverse("bi:strategic_objective_list"),
        reverse("bi:strategic_objective_create"),
        reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_a.pk}),
        reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk}),
        reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_a.pk}),
    ]

    for url in endpoints:
        # GET request
        resp_get = anon_client.get(url)
        assert resp_get.status_code == 302, f"GET {url} did not redirect (status: {resp_get.status_code})"
        assert "/accounts/login/" in resp_get.url or "login" in resp_get.url

        # POST request
        resp_post = anon_client.post(url, {})
        assert resp_post.status_code == 302, f"POST {url} did not redirect (status: {resp_post.status_code})"
        assert "/accounts/login/" in resp_post.url or "login" in resp_post.url

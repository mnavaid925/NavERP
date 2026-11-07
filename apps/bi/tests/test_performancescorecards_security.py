"""Security, Multi-Tenancy, Authorization, and RBAC Test Suite for Sub-module 10.11
Performance Scorecards (apps/bi).

Covers:
1. Anonymous Authentication Enforcement (@login_required):
   - Anonymous GET and POST requests across all 20 views redirect to login (HTTP 302).
2. Complete Multi-Tenant Isolation & IDOR Protection:
   - Tenant A admin attempting to access Tenant B records returns strictly HTTP 404
     on detail (GET), edit (GET/POST), delete (POST), and actions:
     - kpi_definition_refresh (POST -> 404)
     - performance_scorecard_recalculate (POST -> 404)
     - performance_scorecard_strategy_map (GET -> 404)
     - scorecard_kpi_assignment_record_actual (GET/POST -> 404)
   - Bidirectional reverse IDOR protection: Tenant B admin accessing Tenant A records returns 404.
   - List views: strict tenant partition with zero leakage of Tenant B records into Tenant A views.
3. Cross-Tenant Foreign Key Assignment Injection:
   - Rejection of foreign FKs in forms and view POST handlers:
     - KpiDefinition: owner, department, semantic_measure
     - PerformanceScorecard: owner, org_unit
     - ScorecardKpiAssignment: scorecard, kpi, objective
     - StrategicObjective: owner, org_unit, parent_objective
4. Authorization & Role Gates (@tenant_admin_required):
   - Standard non-admin member in Tenant A (is_tenant_admin=False) is blocked (HTTP 403 Forbidden)
     from all 4 creates (GET/POST), all 4 edits (GET/POST), all 4 deletes (POST), and action views
     (kpi_definition_refresh, performance_scorecard_recalculate, scorecard_kpi_assignment_record_actual).
   - Standard user retains read-only access to list, detail, and strategy map views.
5. HTTP Method Restriction (@require_POST):
   - Delete endpoints and action endpoints reject GET requests with HTTP 405 Method Not Allowed.
6. Audit Logging and Security Integrity:
   - Actions generate append-only AuditLog records strictly scoped to the tenant.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.bi.forms.PerformanceScorecards import (
    KpiDefinitionForm,
    PerformanceScorecardForm,
    ScorecardKpiAssignmentForm,
    StrategicObjectiveForm,
)
from apps.bi.models import (
    KpiDefinition,
    PerformanceScorecard,
    ScorecardKpiAssignment,
    StrategicObjective,
)
from apps.core.models import AuditLog, OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# -----------------------------------------------------------------------------
# Bridge Fixture
# -----------------------------------------------------------------------------


@pytest.fixture
def admin_user_b(admin_b):
    """Bridge fixture to unify admin_b and admin_user_b without duplicate username collision."""
    return admin_b


# -----------------------------------------------------------------------------
# Module Helpers (named _performancescorecards_*)
# -----------------------------------------------------------------------------


def _performancescorecards_create_org_unit(tenant, name="Operations", kind="department"):
    """Helper to create a tenant-scoped OrgUnit instance."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind=kind)


def _performancescorecards_create_standard_user(tenant, username="standard_sec_user"):
    """Helper to create a standard (non-admin) user within a tenant."""
    return User.objects.create_user(
        email=f"{username}@{tenant.slug}.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=False,
    )


def _performancescorecards_kpi_payload(**kwargs):
    """Helper returning a valid create/edit payload for KpiDefinition."""
    payload = {
        "code": "KPI_SEC_001",
        "name": "Security Test Margin KPI",
        "slug": "security-test-margin-kpi",
        "description": "Metric used for security suite verification.",
        "category": "finance",
        "perspective": "financial",
        "target_direction": "maximize",
        "unit_of_measure": "percentage",
        "tracking_frequency": "quarterly",
        "calculation_type": "manual",
        "target_value": "15.0000",
        "warning_threshold": "10.0000",
        "critical_threshold": "5.0000",
        "current_value": "14.0000",
        "status": "active",
        "is_active": True,
    }
    payload.update(kwargs)
    return payload


def _performancescorecards_scorecard_payload(**kwargs):
    """Helper returning a valid create/edit payload for PerformanceScorecard."""
    payload = {
        "name": "Security Balanced Scorecard 2026",
        "slug": "security-balanced-scorecard-2026",
        "description": "Scorecard used for security suite verification.",
        "scorecard_type": "balanced_scorecard",
        "review_period": "quarterly",
        "fiscal_year": 2026,
        "financial_weight": "25.00",
        "customer_weight": "25.00",
        "internal_process_weight": "25.00",
        "learning_growth_weight": "25.00",
        "status": "active",
        "is_published": True,
    }
    payload.update(kwargs)
    return payload


def _performancescorecards_assignment_payload(scorecard, kpi, objective=None, **kwargs):
    """Helper returning a valid create/edit payload for ScorecardKpiAssignment."""
    payload = {
        "scorecard": scorecard.pk,
        "kpi": kpi.pk,
        "perspective": "financial",
        "weight": "25.00",
        "target_value": "15.0000",
        "actual_value": "14.5000",
        "sort_order": 1,
    }
    if objective:
        payload["objective"] = objective.pk
    payload.update(kwargs)
    return payload


def _performancescorecards_objective_payload(**kwargs):
    """Helper returning a valid create/edit payload for StrategicObjective."""
    payload = {
        "code": "OBJ_SEC_001",
        "name": "Accelerate Security Compliance",
        "slug": "accelerate-security-compliance",
        "perspective": "financial",
        "statement_of_intent": "Ensure zero vulnerabilities across all tenant boundaries.",
        "status": "active",
        "sort_order": 1,
    }
    payload.update(kwargs)
    return payload


# =============================================================================
# 1. Anonymous Authentication Enforcement (@login_required)
# =============================================================================


def test_performancescorecards_anonymous_get_redirects_to_login(
    anon_client,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Assert anonymous GET to all 15 read/render endpoints redirects to /accounts/login/ (HTTP 302)."""
    routes = [
        # KpiDefinition (4 GET routes)
        reverse("bi:kpi_definition_list"),
        reverse("bi:kpi_definition_create"),
        reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk}),
        # PerformanceScorecard (5 GET routes)
        reverse("bi:performance_scorecard_list"),
        reverse("bi:performance_scorecard_create"),
        reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_a.pk}),
        # ScorecardKpiAssignment (5 GET routes)
        reverse("bi:scorecard_kpi_assignment_list"),
        reverse("bi:scorecard_kpi_assignment_create"),
        reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        # StrategicObjective (4 GET routes)
        reverse("bi:strategic_objective_list"),
        reverse("bi:strategic_objective_create"),
        reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_a.pk}),
        reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk}),
    ]

    assert len(routes) == 18, f"Expected 18 GET routes, got {len(routes)}"

    for url in routes:
        resp = anon_client.get(url)
        assert resp.status_code == 302, f"Expected 302 for anonymous GET {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected redirect to login for {url}, got {resp.url}"


def test_performancescorecards_anonymous_post_mutation_redirects_to_login(
    anon_client,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Assert anonymous POST to all creation, mutation, action, and deletion endpoints redirects to login."""
    post_routes = [
        # Create POST
        (reverse("bi:kpi_definition_create"), _performancescorecards_kpi_payload()),
        (reverse("bi:performance_scorecard_create"), _performancescorecards_scorecard_payload()),
        (reverse("bi:scorecard_kpi_assignment_create"), _performancescorecards_assignment_payload(performance_scorecard_a, kpi_definition_a)),
        (reverse("bi:strategic_objective_create"), _performancescorecards_objective_payload()),
        # Edit POST
        (reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk}), _performancescorecards_kpi_payload()),
        (reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk}), _performancescorecards_scorecard_payload()),
        (reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk}), _performancescorecards_assignment_payload(performance_scorecard_a, kpi_definition_a)),
        (reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk}), _performancescorecards_objective_payload()),
        # Delete POST
        (reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_a.pk}), {}),
        (reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_a.pk}), {}),
        (reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_a.pk}), {}),
        (reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_a.pk}), {}),
        # Actions POST
        (reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}), {"new_value": "99.0000"}),
        (reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk}), {}),
        (reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk}), {"actual_value": "99.0000"}),
    ]

    for url, payload in post_routes:
        resp = anon_client.post(url, data=payload)
        assert resp.status_code == 302, f"Expected 302 for anonymous POST {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected redirect to login for {url}, got {resp.url}"


# =============================================================================
# 2. Complete IDOR Isolation Across All 4 Models
# =============================================================================


def test_performancescorecards_idor_tenant_a_admin_cannot_access_tenant_b_detail(
    client_a,
    kpi_definition_b,
    performance_scorecard_b,
    scorecard_kpi_assignment_b,
    strategic_objective_b,
):
    """Tenant A admin attempting GET on Tenant B records detail returns strictly HTTP 404."""
    assert client_a.get(reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_b.pk})).status_code == 404


def test_performancescorecards_idor_tenant_a_admin_cannot_edit_tenant_b_records(
    client_a,
    kpi_definition_b,
    performance_scorecard_b,
    scorecard_kpi_assignment_b,
    strategic_objective_b,
):
    """Tenant A admin attempting GET/POST on Tenant B edit endpoints returns strictly HTTP 404."""
    # KpiDefinition
    kpi_url = reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_b.pk})
    assert client_a.get(kpi_url).status_code == 404
    resp = client_a.post(kpi_url, _performancescorecards_kpi_payload(name="Hijacked KPI"))
    assert resp.status_code == 404
    kpi_definition_b.refresh_from_db()
    assert kpi_definition_b.name != "Hijacked KPI"

    # PerformanceScorecard
    sc_url = reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_b.pk})
    assert client_a.get(sc_url).status_code == 404
    resp = client_a.post(sc_url, _performancescorecards_scorecard_payload(name="Hijacked Scorecard"))
    assert resp.status_code == 404
    performance_scorecard_b.refresh_from_db()
    assert performance_scorecard_b.name != "Hijacked Scorecard"

    # ScorecardKpiAssignment
    asgn_url = reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_b.pk})
    assert client_a.get(asgn_url).status_code == 404
    resp = client_a.post(
        asgn_url,
        _performancescorecards_assignment_payload(
            performance_scorecard_b,
            kpi_definition_b,
            weight="99.99",
        ),
    )
    assert resp.status_code == 404
    scorecard_kpi_assignment_b.refresh_from_db()
    assert scorecard_kpi_assignment_b.weight != Decimal("99.99")

    # StrategicObjective
    obj_url = reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_b.pk})
    assert client_a.get(obj_url).status_code == 404
    resp = client_a.post(obj_url, _performancescorecards_objective_payload(name="Hijacked Objective"))
    assert resp.status_code == 404
    strategic_objective_b.refresh_from_db()
    assert strategic_objective_b.name != "Hijacked Objective"


def test_performancescorecards_idor_tenant_a_admin_cannot_delete_tenant_b_records(
    client_a,
    kpi_definition_b,
    performance_scorecard_b,
    scorecard_kpi_assignment_b,
    strategic_objective_b,
):
    """Tenant A admin attempting POST on Tenant B delete endpoints returns strictly HTTP 404 and does not delete records."""
    assert client_a.post(reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_b.pk})).status_code == 404
    assert ScorecardKpiAssignment.objects.filter(pk=scorecard_kpi_assignment_b.pk).exists()

    assert client_a.post(reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_b.pk})).status_code == 404
    assert KpiDefinition.objects.filter(pk=kpi_definition_b.pk).exists()

    assert client_a.post(reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_b.pk})).status_code == 404
    assert StrategicObjective.objects.filter(pk=strategic_objective_b.pk).exists()

    assert client_a.post(reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_b.pk})).status_code == 404
    assert PerformanceScorecard.objects.filter(pk=performance_scorecard_b.pk).exists()


def test_performancescorecards_idor_tenant_a_admin_cannot_trigger_tenant_b_actions(
    client_a,
    kpi_definition_b,
    performance_scorecard_b,
    scorecard_kpi_assignment_b,
):
    """Tenant A admin attempting action endpoints on Tenant B records returns strictly HTTP 404."""
    # 1. kpi_definition_refresh (POST -> 404)
    orig_kpi_val = kpi_definition_b.current_value
    resp = client_a.post(
        reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_b.pk}),
        {"new_value": "999.0000", "notes": "Unauthorized refresh"},
    )
    assert resp.status_code == 404
    kpi_definition_b.refresh_from_db()
    assert kpi_definition_b.current_value == orig_kpi_val

    # 2. performance_scorecard_recalculate (POST -> 404)
    resp = client_a.post(reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_b.pk}))
    assert resp.status_code == 404

    # 3. performance_scorecard_strategy_map (GET -> 404)
    resp = client_a.get(reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_b.pk}))
    assert resp.status_code == 404

    # 4. scorecard_kpi_assignment_record_actual (GET -> 404, POST -> 404)
    act_url = reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_b.pk})
    assert client_a.get(act_url).status_code == 404
    orig_act_val = scorecard_kpi_assignment_b.actual_value
    resp = client_a.post(act_url, {"actual_value": "999.0000", "manager_notes": "Unauthorized actual"})
    assert resp.status_code == 404
    scorecard_kpi_assignment_b.refresh_from_db()
    assert scorecard_kpi_assignment_b.actual_value == orig_act_val


def test_performancescorecards_idor_reverse_tenant_b_cannot_access_tenant_a_records(
    client_b,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Bidirectional verification: Tenant B admin attempting to access Tenant A records returns HTTP 404."""
    # Details
    assert client_b.get(reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_a.pk})).status_code == 404

    # Edits
    assert client_b.get(reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk}), _performancescorecards_kpi_payload()).status_code == 404
    assert client_b.get(reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk}), _performancescorecards_scorecard_payload()).status_code == 404
    assert client_b.get(reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk}), {}).status_code == 404
    assert client_b.get(reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk}), _performancescorecards_objective_payload()).status_code == 404

    # Deletions
    assert client_b.post(reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_a.pk})).status_code == 404

    # Actions
    assert client_b.post(reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}), {"new_value": "50.0"}).status_code == 404
    assert client_b.post(reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_a.pk})).status_code == 404
    assert client_b.get(reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk})).status_code == 404
    assert client_b.post(reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk}), {"actual_value": "50.0"}).status_code == 404


def test_performancescorecards_list_views_zero_cross_tenant_leakage(
    client_a,
    client_b,
    kpi_definition_a,
    kpi_definition_b,
    performance_scorecard_a,
    performance_scorecard_b,
    scorecard_kpi_assignment_a,
    scorecard_kpi_assignment_b,
    strategic_objective_a,
    strategic_objective_b,
):
    """Verify list views strictly isolate records: Tenant A sees only Tenant A; Tenant B sees only Tenant B."""
    # 1. KpiDefinition List
    resp_kpi_a = client_a.get(reverse("bi:kpi_definition_list"))
    assert resp_kpi_a.status_code == 200
    kpis_a = list(resp_kpi_a.context["kpis"])
    assert kpi_definition_a in kpis_a
    assert kpi_definition_b not in kpis_a
    assert kpi_definition_b.name not in resp_kpi_a.content.decode()

    resp_kpi_b = client_b.get(reverse("bi:kpi_definition_list"))
    assert resp_kpi_b.status_code == 200
    kpis_b = list(resp_kpi_b.context["kpis"])
    assert kpi_definition_b in kpis_b
    assert kpi_definition_a not in kpis_b

    # 2. PerformanceScorecard List
    resp_sc_a = client_a.get(reverse("bi:performance_scorecard_list"))
    assert resp_sc_a.status_code == 200
    scs_a = list(resp_sc_a.context["scorecards"])
    assert performance_scorecard_a in scs_a
    assert performance_scorecard_b not in scs_a
    assert performance_scorecard_b.name not in resp_sc_a.content.decode()

    resp_sc_b = client_b.get(reverse("bi:performance_scorecard_list"))
    assert resp_sc_b.status_code == 200
    scs_b = list(resp_sc_b.context["scorecards"])
    assert performance_scorecard_b in scs_b
    assert performance_scorecard_a not in scs_b

    # 3. ScorecardKpiAssignment List
    resp_asgn_a = client_a.get(reverse("bi:scorecard_kpi_assignment_list"))
    assert resp_asgn_a.status_code == 200
    asgns_a = list(resp_asgn_a.context["assignments"])
    assert scorecard_kpi_assignment_a in asgns_a
    assert scorecard_kpi_assignment_b not in asgns_a
    assert scorecard_kpi_assignment_b.number not in resp_asgn_a.content.decode()

    resp_asgn_b = client_b.get(reverse("bi:scorecard_kpi_assignment_list"))
    assert resp_asgn_b.status_code == 200
    asgns_b = list(resp_asgn_b.context["assignments"])
    assert scorecard_kpi_assignment_b in asgns_b
    assert scorecard_kpi_assignment_a not in asgns_b

    # 4. StrategicObjective List
    resp_obj_a = client_a.get(reverse("bi:strategic_objective_list"))
    assert resp_obj_a.status_code == 200
    objs_a = list(resp_obj_a.context["objectives"])
    assert strategic_objective_a in objs_a
    assert strategic_objective_b not in objs_a
    assert strategic_objective_b.name not in resp_obj_a.content.decode()

    resp_obj_b = client_b.get(reverse("bi:strategic_objective_list"))
    assert resp_obj_b.status_code == 200
    objs_b = list(resp_obj_b.context["objectives"])
    assert strategic_objective_b in objs_b
    assert strategic_objective_a not in objs_b


# =============================================================================
# 3. Cross-Tenant Foreign Key Assignment Injection
# =============================================================================


def test_performancescorecards_kpi_form_rejects_tenant_b_fks(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    calculated_measure_b,
):
    """KpiDefinitionForm rejects Tenant B owner, department, and semantic_measure."""
    dept_b = _performancescorecards_create_org_unit(tenant_b, name="Globex Ops Dept")

    # 1. Reject Tenant B owner
    form_owner = KpiDefinitionForm(
        data=_performancescorecards_kpi_payload(owner=admin_user_b.pk),
        tenant=tenant_a,
    )
    assert not form_owner.is_valid()
    assert "owner" in form_owner.errors

    # 2. Reject Tenant B department
    form_dept = KpiDefinitionForm(
        data=_performancescorecards_kpi_payload(department=dept_b.pk),
        tenant=tenant_a,
    )
    assert not form_dept.is_valid()
    assert "department" in form_dept.errors

    # 3. Reject Tenant B semantic_measure
    form_measure = KpiDefinitionForm(
        data=_performancescorecards_kpi_payload(semantic_measure=calculated_measure_b.pk),
        tenant=tenant_a,
    )
    assert not form_measure.is_valid()
    assert "semantic_measure" in form_measure.errors


def test_performancescorecards_kpi_view_injection_tenant_b_fks_blocked(
    client_a,
    tenant_b,
    admin_user_b,
    calculated_measure_b,
):
    """Submitting Tenant B FKs to kpi_definition_create view is rejected with form error and no object is created."""
    dept_b = _performancescorecards_create_org_unit(tenant_b, name="Foreign Dept")
    url = reverse("bi:kpi_definition_create")

    payload = _performancescorecards_kpi_payload(
        code="KPI_INJECT_FAIL",
        name="Injection Failed KPI",
        owner=admin_user_b.pk,
        department=dept_b.pk,
        semantic_measure=calculated_measure_b.pk,
    )
    resp = client_a.post(url, data=payload)
    # Re-rendered form with HTTP 200 and validation errors
    assert resp.status_code == 200
    assert not KpiDefinition.objects.filter(code="KPI_INJECT_FAIL").exists()


def test_performancescorecards_scorecard_form_rejects_tenant_b_fks(
    tenant_a,
    tenant_b,
    admin_user_b,
):
    """PerformanceScorecardForm rejects Tenant B owner and org_unit."""
    org_unit_b = _performancescorecards_create_org_unit(tenant_b, name="Globex Division")

    # 1. Reject Tenant B owner
    form_owner = PerformanceScorecardForm(
        data=_performancescorecards_scorecard_payload(owner=admin_user_b.pk),
        tenant=tenant_a,
    )
    assert not form_owner.is_valid()
    assert "owner" in form_owner.errors

    # 2. Reject Tenant B org_unit
    form_org = PerformanceScorecardForm(
        data=_performancescorecards_scorecard_payload(org_unit=org_unit_b.pk),
        tenant=tenant_a,
    )
    assert not form_org.is_valid()
    assert "org_unit" in form_org.errors


def test_performancescorecards_scorecard_view_injection_tenant_b_fks_blocked(
    client_a,
    tenant_b,
    admin_user_b,
):
    """Submitting Tenant B FKs to performance_scorecard_create view is rejected and no scorecard is created."""
    org_unit_b = _performancescorecards_create_org_unit(tenant_b, name="Foreign Division")
    url = reverse("bi:performance_scorecard_create")

    payload = _performancescorecards_scorecard_payload(
        name="Injection Scorecard Fail",
        owner=admin_user_b.pk,
        org_unit=org_unit_b.pk,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert not PerformanceScorecard.objects.filter(name="Injection Scorecard Fail").exists()


def test_performancescorecards_assignment_form_rejects_tenant_b_fks(
    tenant_a,
    performance_scorecard_a,
    performance_scorecard_b,
    kpi_definition_a,
    kpi_definition_b,
    strategic_objective_a,
    strategic_objective_b,
):
    """ScorecardKpiAssignmentForm rejects Tenant B scorecard, kpi, and objective."""
    # 1. Reject Tenant B scorecard
    form_sc = ScorecardKpiAssignmentForm(
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_b,
            kpi=kpi_definition_a,
            objective=strategic_objective_a,
        ),
        tenant=tenant_a,
    )
    assert not form_sc.is_valid()
    assert "scorecard" in form_sc.errors

    # 2. Reject Tenant B kpi
    form_kpi = ScorecardKpiAssignmentForm(
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_a,
            kpi=kpi_definition_b,
            objective=strategic_objective_a,
        ),
        tenant=tenant_a,
    )
    assert not form_kpi.is_valid()
    assert "kpi" in form_kpi.errors

    # 3. Reject Tenant B objective
    form_obj = ScorecardKpiAssignmentForm(
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_a,
            kpi=kpi_definition_a,
            objective=strategic_objective_b,
        ),
        tenant=tenant_a,
    )
    assert not form_obj.is_valid()
    assert "objective" in form_obj.errors


def test_performancescorecards_assignment_view_injection_tenant_b_fks_blocked(
    client_a,
    performance_scorecard_a,
    performance_scorecard_b,
    kpi_definition_a,
    kpi_definition_b,
    strategic_objective_a,
    strategic_objective_b,
):
    """Submitting Tenant B FKs to scorecard_kpi_assignment_create view is rejected and no assignment is created."""
    url = reverse("bi:scorecard_kpi_assignment_create")

    # Injected Tenant B scorecard
    resp = client_a.post(
        url,
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_b,
            kpi=kpi_definition_a,
            objective=strategic_objective_a,
        ),
    )
    assert resp.status_code == 200
    assert not ScorecardKpiAssignment.objects.filter(scorecard=performance_scorecard_b, kpi=kpi_definition_a).exists()

    # Injected Tenant B kpi
    resp = client_a.post(
        url,
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_a,
            kpi=kpi_definition_b,
            objective=strategic_objective_a,
        ),
    )
    assert resp.status_code == 200
    assert not ScorecardKpiAssignment.objects.filter(scorecard=performance_scorecard_a, kpi=kpi_definition_b).exists()

    # Injected Tenant B objective
    resp = client_a.post(
        url,
        data=_performancescorecards_assignment_payload(
            scorecard=performance_scorecard_a,
            kpi=kpi_definition_a,
            objective=strategic_objective_b,
        ),
    )
    assert resp.status_code == 200
    assert not ScorecardKpiAssignment.objects.filter(scorecard=performance_scorecard_a, objective=strategic_objective_b).exists()


def test_performancescorecards_objective_form_rejects_tenant_b_fks(
    tenant_a,
    tenant_b,
    admin_user_b,
    strategic_objective_b,
):
    """StrategicObjectiveForm rejects Tenant B owner, org_unit, and parent_objective."""
    org_unit_b = _performancescorecards_create_org_unit(tenant_b, name="Globex Branch")

    # 1. Reject Tenant B owner
    form_owner = StrategicObjectiveForm(
        data=_performancescorecards_objective_payload(owner=admin_user_b.pk),
        tenant=tenant_a,
    )
    assert not form_owner.is_valid()
    assert "owner" in form_owner.errors

    # 2. Reject Tenant B org_unit
    form_org = StrategicObjectiveForm(
        data=_performancescorecards_objective_payload(org_unit=org_unit_b.pk),
        tenant=tenant_a,
    )
    assert not form_org.is_valid()
    assert "org_unit" in form_org.errors

    # 3. Reject Tenant B parent_objective
    form_parent = StrategicObjectiveForm(
        data=_performancescorecards_objective_payload(parent_objective=strategic_objective_b.pk),
        tenant=tenant_a,
    )
    assert not form_parent.is_valid()
    assert "parent_objective" in form_parent.errors


def test_performancescorecards_objective_view_injection_tenant_b_fks_blocked(
    client_a,
    tenant_b,
    admin_user_b,
    strategic_objective_b,
):
    """Submitting Tenant B FKs to strategic_objective_create view is rejected and no objective is created."""
    org_unit_b = _performancescorecards_create_org_unit(tenant_b, name="Foreign Branch")
    url = reverse("bi:strategic_objective_create")

    payload = _performancescorecards_objective_payload(
        code="OBJ_INJECT_FAIL",
        name="Injection Objective Fail",
        owner=admin_user_b.pk,
        org_unit=org_unit_b.pk,
        parent_objective=strategic_objective_b.pk,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 200
    assert not StrategicObjective.objects.filter(code="OBJ_INJECT_FAIL").exists()


# =============================================================================
# 4. Authorization & Role Gates (@tenant_admin_required)
# =============================================================================


@pytest.fixture
def standard_client_a(tenant_a):
    """Create a standard (non-admin) user in Tenant A (is_tenant_admin=False) and client."""
    user = _performancescorecards_create_standard_user(tenant_a, username="member_alice")
    c = Client()
    c.force_login(user)
    return c


def test_performancescorecards_standard_user_blocked_from_create_views(standard_client_a):
    """Standard non-admin user is blocked (403 Forbidden) from all 4 create views (GET and POST)."""
    routes = [
        (reverse("bi:kpi_definition_create"), _performancescorecards_kpi_payload()),
        (reverse("bi:performance_scorecard_create"), _performancescorecards_scorecard_payload()),
        (reverse("bi:scorecard_kpi_assignment_create"), {}),
        (reverse("bi:strategic_objective_create"), _performancescorecards_objective_payload()),
    ]

    for url, payload in routes:
        # GET -> 403
        resp_get = standard_client_a.get(url)
        assert resp_get.status_code == 403, f"Expected 403 on GET {url}, got {resp_get.status_code}"

        # POST -> 403
        resp_post = standard_client_a.post(url, data=payload)
        assert resp_post.status_code == 403, f"Expected 403 on POST {url}, got {resp_post.status_code}"


def test_performancescorecards_standard_user_blocked_from_edit_views(
    standard_client_a,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Standard non-admin user is blocked (403 Forbidden) from all 4 edit views (GET and POST)."""
    routes = [
        (
            reverse("bi:kpi_definition_edit", kwargs={"pk": kpi_definition_a.pk}),
            _performancescorecards_kpi_payload(name="Tampered Name"),
        ),
        (
            reverse("bi:performance_scorecard_edit", kwargs={"pk": performance_scorecard_a.pk}),
            _performancescorecards_scorecard_payload(name="Tampered Name"),
        ),
        (
            reverse("bi:scorecard_kpi_assignment_edit", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
            {"weight": "99.00"},
        ),
        (
            reverse("bi:strategic_objective_edit", kwargs={"pk": strategic_objective_a.pk}),
            _performancescorecards_objective_payload(name="Tampered Name"),
        ),
    ]

    for url, payload in routes:
        # GET -> 403
        resp_get = standard_client_a.get(url)
        assert resp_get.status_code == 403, f"Expected 403 on GET {url}, got {resp_get.status_code}"

        # POST -> 403
        resp_post = standard_client_a.post(url, data=payload)
        assert resp_post.status_code == 403, f"Expected 403 on POST {url}, got {resp_post.status_code}"


def test_performancescorecards_standard_user_blocked_from_delete_views(
    standard_client_a,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Standard non-admin user is blocked (403 Forbidden) from all 4 delete views (POST)."""
    routes = [
        reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_a.pk}),
    ]

    for url in routes:
        resp = standard_client_a.post(url)
        assert resp.status_code == 403, f"Expected 403 on POST {url}, got {resp.status_code}"

    # Verify no records were deleted
    assert ScorecardKpiAssignment.objects.filter(pk=scorecard_kpi_assignment_a.pk).exists()
    assert KpiDefinition.objects.filter(pk=kpi_definition_a.pk).exists()
    assert PerformanceScorecard.objects.filter(pk=performance_scorecard_a.pk).exists()
    assert StrategicObjective.objects.filter(pk=strategic_objective_a.pk).exists()


def test_performancescorecards_standard_user_blocked_from_action_views(
    standard_client_a,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
):
    """Standard non-admin user is blocked (403 Forbidden) from all action views."""
    # 1. kpi_definition_refresh (POST -> 403)
    resp_refresh = standard_client_a.post(
        reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}),
        {"new_value": "99.0000"},
    )
    assert resp_refresh.status_code == 403

    # 2. performance_scorecard_recalculate (POST -> 403)
    resp_recalc = standard_client_a.post(
        reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk})
    )
    assert resp_recalc.status_code == 403

    # 3. scorecard_kpi_assignment_record_actual (GET -> 403, POST -> 403)
    act_url = reverse("bi:scorecard_kpi_assignment_record_actual", kwargs={"pk": scorecard_kpi_assignment_a.pk})
    assert standard_client_a.get(act_url).status_code == 403
    assert standard_client_a.post(act_url, {"actual_value": "99.0000"}).status_code == 403


def test_performancescorecards_standard_user_can_access_read_views(
    standard_client_a,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Standard non-admin user retains read-only access (HTTP 200) to list, detail, and strategy map views."""
    read_routes = [
        reverse("bi:kpi_definition_list"),
        reverse("bi:kpi_definition_detail", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:performance_scorecard_list"),
        reverse("bi:performance_scorecard_detail", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:performance_scorecard_strategy_map", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:scorecard_kpi_assignment_list"),
        reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:strategic_objective_list"),
        reverse("bi:strategic_objective_detail", kwargs={"pk": strategic_objective_a.pk}),
    ]

    for url in read_routes:
        resp = standard_client_a.get(url)
        assert resp.status_code == 200, f"Expected 200 on read GET {url}, got {resp.status_code}"


# =============================================================================
# 5. HTTP Method Restriction (@require_POST)
# =============================================================================


def test_performancescorecards_delete_views_reject_get_405(
    client_a,
    kpi_definition_a,
    performance_scorecard_a,
    scorecard_kpi_assignment_a,
    strategic_objective_a,
):
    """Delete views reject GET requests with HTTP 405 Method Not Allowed."""
    delete_routes = [
        reverse("bi:kpi_definition_delete", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:performance_scorecard_delete", kwargs={"pk": performance_scorecard_a.pk}),
        reverse("bi:scorecard_kpi_assignment_delete", kwargs={"pk": scorecard_kpi_assignment_a.pk}),
        reverse("bi:strategic_objective_delete", kwargs={"pk": strategic_objective_a.pk}),
    ]

    for url in delete_routes:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on delete view {url}, got {resp.status_code}"


def test_performancescorecards_mutation_actions_reject_get_405(
    client_a,
    kpi_definition_a,
    performance_scorecard_a,
):
    """Action endpoints decorated with @require_POST reject GET requests with HTTP 405."""
    action_routes = [
        reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}),
        reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk}),
    ]

    for url in action_routes:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET on action view {url}, got {resp.status_code}"


# =============================================================================
# 6. Audit Logging and Security Integrity
# =============================================================================


def test_performancescorecards_mutations_create_tenant_scoped_audit_logs(
    client_a,
    tenant_a,
    admin_user,
    kpi_definition_a,
    performance_scorecard_a,
):
    """Verifies mutations create append-only AuditLog records strictly scoped to Tenant A."""
    initial_log_count = AuditLog.objects.filter(tenant=tenant_a).count()

    # 1. Refresh KPI
    resp_refresh = client_a.post(
        reverse("bi:kpi_definition_refresh", kwargs={"pk": kpi_definition_a.pk}),
        {"new_value": "18.5000", "notes": "Audited value update"},
    )
    assert resp_refresh.status_code == 302

    # 2. Recalculate Scorecard
    resp_recalc = client_a.post(
        reverse("bi:performance_scorecard_recalculate", kwargs={"pk": performance_scorecard_a.pk})
    )
    assert resp_recalc.status_code == 302

    new_logs = AuditLog.objects.filter(tenant=tenant_a).order_by("-at")
    assert new_logs.count() >= initial_log_count + 2

    # Assert actor and tenant integrity
    latest_logs = list(new_logs[:2])
    for log in latest_logs:
        assert log.user == admin_user
        assert log.tenant == tenant_a
        assert log.action == "update"

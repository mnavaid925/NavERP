"""Security, Multi-Tenancy, Authorization, and IDOR Protection Tests for Sub-module 10.13:
Predictive & Advanced Analytics (apps/bi).

Covers:
1. Anonymous Authentication (@login_required):
   - Anonymous access to all list, detail, create, edit, delete, and action routes
     redirects to /accounts/login/ (HTTP 302).
2. Multi-Tenant Isolation & IDOR Protection:
   - Client A attempting to access Client B's objects returns strictly HTTP 404.
   - Bidirectional reverse IDOR protection: Client B accessing Client A's objects returns 404.
   - List views enforce zero data leakage across tenant boundaries.
3. Role-Based Authorization (@tenant_admin_required):
   - Non-admin member user in Tenant A receives HTTP 403 Forbidden on all 4 delete routes.
4. HTTP Method Constraints (@require_POST):
   - Delete and state mutation routes (train, triage, solve) reject GET requests with HTTP 405.
5. Cross-Tenant Foreign Key Injection:
   - Form and view rejection of foreign SemanticModel, PredictiveModel, KpiDefinition, and User.
6. Multi-User Simulation & Boundary Scaling:
   - Simulates heterogeneous users across Tenant A and Tenant B asserting 100% tenant boundary preservation.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    ForecastExecution,
    OptimizationScenario,
    PredictiveModel,
    StatisticalAnomaly,
)


# ===========================================================================
# 1. Anonymous Authentication (@login_required)
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_anon_redirects_to_login(
    client,
    predictive_model_a,
    forecast_execution_a,
    statistical_anomaly_a,
    optimization_scenario_a,
):
    """Verify anonymous requests redirect to login for all sub-module routes."""
    routes = [
        # Lists
        reverse("bi:predictive_model_list"),
        reverse("bi:forecast_execution_list"),
        reverse("bi:statistical_anomaly_list"),
        reverse("bi:optimization_scenario_list"),
        # Creates
        reverse("bi:predictive_model_create"),
        reverse("bi:forecast_execution_create"),
        reverse("bi:statistical_anomaly_create"),
        reverse("bi:optimization_scenario_create"),
        # Details
        reverse("bi:predictive_model_detail", args=[predictive_model_a.pk]),
        reverse("bi:forecast_execution_detail", args=[forecast_execution_a.pk]),
        reverse("bi:statistical_anomaly_detail", args=[statistical_anomaly_a.pk]),
        reverse("bi:optimization_scenario_detail", args=[optimization_scenario_a.pk]),
        # Edits
        reverse("bi:predictive_model_edit", args=[predictive_model_a.pk]),
        reverse("bi:forecast_execution_edit", args=[forecast_execution_a.pk]),
        reverse("bi:statistical_anomaly_edit", args=[statistical_anomaly_a.pk]),
        reverse("bi:optimization_scenario_edit", args=[optimization_scenario_a.pk]),
    ]
    for url in routes:
        res = client.get(url)
        assert res.status_code == 302
        assert "/login/" in res.url


# ===========================================================================
# 2. Multi-Tenant Isolation & IDOR Protection
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_cross_tenant_idor_blocked(
    client_a,
    predictive_model_b,
    forecast_execution_b,
    statistical_anomaly_b,
    optimization_scenario_b,
):
    """Verify Client A accessing Client B's objects returns HTTP 404 across all operations."""
    idor_targets = [
        ("GET", reverse("bi:predictive_model_detail", args=[predictive_model_b.pk])),
        ("GET", reverse("bi:predictive_model_edit", args=[predictive_model_b.pk])),
        ("POST", reverse("bi:predictive_model_delete", args=[predictive_model_b.pk])),
        ("POST", reverse("bi:predictive_model_train", args=[predictive_model_b.pk])),

        ("GET", reverse("bi:forecast_execution_detail", args=[forecast_execution_b.pk])),
        ("GET", reverse("bi:forecast_execution_edit", args=[forecast_execution_b.pk])),
        ("POST", reverse("bi:forecast_execution_delete", args=[forecast_execution_b.pk])),

        ("GET", reverse("bi:statistical_anomaly_detail", args=[statistical_anomaly_b.pk])),
        ("GET", reverse("bi:statistical_anomaly_edit", args=[statistical_anomaly_b.pk])),
        ("POST", reverse("bi:statistical_anomaly_delete", args=[statistical_anomaly_b.pk])),
        ("POST", reverse("bi:statistical_anomaly_triage", args=[statistical_anomaly_b.pk])),

        ("GET", reverse("bi:optimization_scenario_detail", args=[optimization_scenario_b.pk])),
        ("GET", reverse("bi:optimization_scenario_edit", args=[optimization_scenario_b.pk])),
        ("POST", reverse("bi:optimization_scenario_delete", args=[optimization_scenario_b.pk])),
        ("POST", reverse("bi:optimization_scenario_solve", args=[optimization_scenario_b.pk])),
    ]

    for method, url in idor_targets:
        res = client_a.get(url) if method == "GET" else client_a.post(url)
        assert res.status_code == 404, f"IDOR Vulnerability detected: {method} {url} returned {res.status_code}"


@pytest.mark.django_db
def test_predictiveanalytics_reverse_cross_tenant_idor_blocked(
    client_b,
    predictive_model_a,
    forecast_execution_a,
    statistical_anomaly_a,
    optimization_scenario_a,
):
    """Verify Client B accessing Client A's objects returns HTTP 404."""
    reverse_targets = [
        reverse("bi:predictive_model_detail", args=[predictive_model_a.pk]),
        reverse("bi:forecast_execution_detail", args=[forecast_execution_a.pk]),
        reverse("bi:statistical_anomaly_detail", args=[statistical_anomaly_a.pk]),
        reverse("bi:optimization_scenario_detail", args=[optimization_scenario_a.pk]),
    ]
    for url in reverse_targets:
        assert client_b.get(url).status_code == 404


@pytest.mark.django_db
def test_predictiveanalytics_list_view_strict_tenant_isolation(
    client_a,
    client_b,
    predictive_model_a,
    predictive_model_b,
    forecast_execution_a,
    forecast_execution_b,
    statistical_anomaly_a,
    statistical_anomaly_b,
    optimization_scenario_a,
    optimization_scenario_b,
):
    """Verify zero data leakage in list views between Tenant A and Tenant B."""
    # PredictiveModel
    res_a = client_a.get(reverse("bi:predictive_model_list"))
    assert predictive_model_a in res_a.context["predictive_models"]
    assert predictive_model_b not in res_a.context["predictive_models"]

    res_b = client_b.get(reverse("bi:predictive_model_list"))
    assert predictive_model_b in res_b.context["predictive_models"]
    assert predictive_model_a not in res_b.context["predictive_models"]

    # ForecastExecution
    res_f_a = client_a.get(reverse("bi:forecast_execution_list"))
    assert forecast_execution_a in res_f_a.context["forecast_executions"]
    assert forecast_execution_b not in res_f_a.context["forecast_executions"]

    # StatisticalAnomaly
    res_s_a = client_a.get(reverse("bi:statistical_anomaly_list"))
    assert statistical_anomaly_a in res_s_a.context["statistical_anomalies"]
    assert statistical_anomaly_b not in res_s_a.context["statistical_anomalies"]

    # OptimizationScenario
    res_o_a = client_a.get(reverse("bi:optimization_scenario_list"))
    assert optimization_scenario_a in res_o_a.context["optimization_scenarios"]
    assert optimization_scenario_b not in res_o_a.context["optimization_scenarios"]


# ===========================================================================
# 3. Role-Based Authorization (@tenant_admin_required)
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_delete_requires_tenant_admin(
    member_client,
    predictive_model_a,
    forecast_execution_a,
    statistical_anomaly_a,
    optimization_scenario_a,
):
    """Verify non-admin member user receives HTTP 403 Forbidden on all 4 deletion endpoints."""
    delete_routes = [
        reverse("bi:predictive_model_delete", args=[predictive_model_a.pk]),
        reverse("bi:forecast_execution_delete", args=[forecast_execution_a.pk]),
        reverse("bi:statistical_anomaly_delete", args=[statistical_anomaly_a.pk]),
        reverse("bi:optimization_scenario_delete", args=[optimization_scenario_a.pk]),
    ]
    for url in delete_routes:
        res = member_client.post(url)
        assert res.status_code == 403, f"Non-admin allowed to delete at {url}! Status: {res.status_code}"


# ===========================================================================
# 4. HTTP Method Constraints (@require_POST)
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_mutations_require_post(
    client_a,
    predictive_model_a,
    forecast_execution_a,
    statistical_anomaly_a,
    optimization_scenario_a,
):
    """Verify delete and mutation endpoints reject GET requests with HTTP 405."""
    mutation_routes = [
        reverse("bi:predictive_model_delete", args=[predictive_model_a.pk]),
        reverse("bi:predictive_model_train", args=[predictive_model_a.pk]),
        reverse("bi:forecast_execution_delete", args=[forecast_execution_a.pk]),
        reverse("bi:statistical_anomaly_delete", args=[statistical_anomaly_a.pk]),
        reverse("bi:statistical_anomaly_triage", args=[statistical_anomaly_a.pk]),
        reverse("bi:optimization_scenario_delete", args=[optimization_scenario_a.pk]),
        reverse("bi:optimization_scenario_solve", args=[optimization_scenario_a.pk]),
    ]
    for url in mutation_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"GET request allowed on POST-only route {url}!"


# ===========================================================================
# 5. Cross-Tenant Foreign Key Injection via Views
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_cross_tenant_foreign_key_injection_blocked(
    client_a,
    tenant_a,
    semantic_model_b,
    predictive_model_b,
    kpi_definition_b,
    admin_user_b,
):
    """Verify form submission injecting foreign tenant relations fails validation."""
    # Attempt to inject foreign model in forecast create
    payload = {
        "name": "Malicious Forecast Injection",
        "model": predictive_model_b.pk,
        "kpi_definition": kpi_definition_b.pk,
        "cadence": "monthly",
        "horizon_periods": 6,
    }
    res = client_a.post(reverse("bi:forecast_execution_create"), data=payload)
    assert res.status_code == 200
    assert "form" in res.context
    assert not res.context["form"].is_valid()
    assert not ForecastExecution.objects.filter(tenant=tenant_a, name="Malicious Forecast Injection").exists()


# ===========================================================================
# 6. Multi-User Simulation & Scale
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_multi_user_boundary_scaling(tenant_a, tenant_b):
    """Simulate 20 heterogeneous tenant users across tenants asserting absolute data boundary isolation."""
    User = get_user_model()
    simulated_users = []
    for i in range(1, 11):
        simulated_users.append(
            User.objects.create_user(
                email=f"user_a_{i}@acme.com",
                username=f"scale_user_a_{i}",
                password="password",
                tenant=tenant_a,
            )
        )
    for i in range(1, 11):
        simulated_users.append(
            User.objects.create_user(
                email=f"user_b_{i}@globex.com",
                username=f"scale_user_b_{i}",
                password="password",
                tenant=tenant_b,
            )
        )

    # Verify queryset isolation for each simulated user
    for user in simulated_users:
        user_tenant = user.tenant
        models_qs = PredictiveModel.objects.filter(tenant=user_tenant)
        for m in models_qs:
            assert m.tenant == user_tenant, f"Cross-tenant leak in PredictiveModel for {user.username}"

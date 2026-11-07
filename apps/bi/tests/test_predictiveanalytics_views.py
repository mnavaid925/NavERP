"""Views unit tests for Sub-module 10.13: Predictive & Advanced Analytics (apps/bi).

Entities covered:
1. PredictiveModel (list, detail, create, edit, delete, train)
2. ForecastExecution (list, detail, create, edit, delete)
3. StatisticalAnomaly (list, detail, create, edit, delete, triage)
4. OptimizationScenario (list, detail, create, edit, delete, solve)
"""
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bi.models import (
    ForecastExecution,
    OptimizationScenario,
    PredictiveModel,
    StatisticalAnomaly,
)
from apps.core.models import AuditLog


# ===========================================================================
# 1. PredictiveModel Views
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_model_list_view(client_a, predictive_model_a):
    """Test model list view returns 200, context variables, and filters."""
    url = reverse("bi:predictive_model_list")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "predictive_models" in res.context
    assert predictive_model_a in res.context["predictive_models"]
    assert res.context["total_count"] >= 1
    assert "problem_type_choices" in res.context
    assert "status_choices" in res.context

    # Filter by q search
    res_search = client_a.get(f"{url}?q=Demand")
    assert res_search.status_code == 200
    assert predictive_model_a in res_search.context["predictive_models"]

    # Filter by problem_type
    res_type = client_a.get(f"{url}?problem_type=time_series_forecast")
    assert res_type.status_code == 200
    assert predictive_model_a in res_type.context["predictive_models"]


@pytest.mark.django_db
def test_predictiveanalytics_model_detail_view(client_a, predictive_model_a):
    """Test model detail view returns 200 and passes model_obj and related collections."""
    url = reverse("bi:predictive_model_detail", args=[predictive_model_a.pk])
    res = client_a.get(url)
    assert res.status_code == 200
    assert res.context["model_obj"] == predictive_model_a
    assert "executions" in res.context
    assert "anomalies" in res.context
    assert predictive_model_a.number in res.content.decode()


@pytest.mark.django_db
def test_predictiveanalytics_model_create_view(client_a, tenant_a, semantic_model_a):
    """Test model create GET form and POST creation with redirect."""
    url = reverse("bi:predictive_model_create")
    get_res = client_a.get(url)
    assert get_res.status_code == 200

    payload = {
        "name": "View Test Predictive Model",
        "slug": "view-test-predictive-model",
        "problem_type": "regression",
        "algorithm": "gradient_boosting",
        "target_metric": "net_revenue",
        "model_version": "1.0.0",
        "status": "draft",
        "drift_threshold": "12.50",
        "features_list_raw": '["orders_count", "average_basket"]',
        "hyperparameters_raw": '{"n_estimators": 50}',
        "semantic_model": semantic_model_a.pk,
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302

    created = PredictiveModel.objects.filter(tenant=tenant_a, slug="view-test-predictive-model").first()
    assert created is not None
    assert created.name == "View Test Predictive Model"
    assert created.features_list == ["orders_count", "average_basket"]
    assert post_res.url == created.get_absolute_url()


@pytest.mark.django_db
def test_predictiveanalytics_model_edit_view(client_a, predictive_model_a):
    """Test model edit GET form and POST update."""
    url = reverse("bi:predictive_model_edit", args=[predictive_model_a.pk])
    get_res = client_a.get(url)
    assert get_res.status_code == 200

    payload = {
        "name": "Updated Acme Demand Model",
        "slug": predictive_model_a.slug,
        "problem_type": predictive_model_a.problem_type,
        "algorithm": predictive_model_a.algorithm,
        "target_metric": predictive_model_a.target_metric,
        "model_version": "1.1.0",
        "status": "active",
        "drift_threshold": "10.00",
        "features_list_raw": json.dumps(predictive_model_a.features_list),
        "hyperparameters_raw": json.dumps(predictive_model_a.hyperparameters),
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302
    predictive_model_a.refresh_from_db()
    assert predictive_model_a.name == "Updated Acme Demand Model"
    assert predictive_model_a.model_version == "1.1.0"


@pytest.mark.django_db
def test_predictiveanalytics_model_train_action(client_a, tenant_a, predictive_model_a):
    """Test train action triggers AutoML fitting, updates metrics, and writes AuditLog."""
    url = reverse("bi:predictive_model_train", args=[predictive_model_a.pk])
    post_res = client_a.post(url)
    assert post_res.status_code == 302
    assert post_res.url == predictive_model_a.get_absolute_url()

    predictive_model_a.refresh_from_db()
    assert predictive_model_a.accuracy_metric_value is not None

    log = AuditLog.objects.filter(tenant=tenant_a, action="train").first()
    assert log is not None


# ===========================================================================
# 2. ForecastExecution Views
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_forecast_list_view(client_a, forecast_execution_a):
    """Test forecast list view returns 200, context variables, and filters."""
    url = reverse("bi:forecast_execution_list")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "forecast_executions" in res.context
    assert forecast_execution_a in res.context["forecast_executions"]
    assert res.context["total_count"] >= 1
    assert "cadence_choices" in res.context


@pytest.mark.django_db
def test_predictiveanalytics_forecast_detail_view(client_a, forecast_execution_a):
    """Test forecast detail view returns 200 and passes forecast_obj."""
    url = reverse("bi:forecast_execution_detail", args=[forecast_execution_a.pk])
    res = client_a.get(url)
    assert res.status_code == 200
    assert res.context["forecast_obj"] == forecast_execution_a
    assert len(forecast_execution_a.forecast_output_data) == 2
    assert forecast_execution_a.number in res.content.decode()


@pytest.mark.django_db
def test_predictiveanalytics_forecast_create_view(client_a, tenant_a, predictive_model_a, kpi_definition_a):
    """Test forecast create generates points in single database write and redirects."""
    url = reverse("bi:forecast_execution_create")
    get_res = client_a.get(url)
    assert get_res.status_code == 200

    payload = {
        "name": "View Test Annual Forecast",
        "model": predictive_model_a.pk,
        "kpi_definition": kpi_definition_a.pk,
        "cadence": "monthly",
        "horizon_periods": 6,
        "confidence_level": "95",
        "historical_window_periods": 36,
        "trend_direction": "upward",
        "notes": "Generated by view test",
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302

    created = ForecastExecution.objects.filter(tenant=tenant_a, name="View Test Annual Forecast").first()
    assert created is not None
    assert len(created.forecast_output_data) == 6
    assert created.status == "completed"
    assert post_res.url == created.get_absolute_url()


# ===========================================================================
# 3. StatisticalAnomaly Views
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_list_view(client_a, statistical_anomaly_a):
    """Test anomaly list view returns 200, context variables, and stat counts."""
    url = reverse("bi:statistical_anomaly_list")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "statistical_anomalies" in res.context
    assert statistical_anomaly_a in res.context["statistical_anomalies"]
    assert res.context["total_count"] >= 1
    assert "severity_choices" in res.context
    assert "triage_choices" in res.context


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_detail_view(client_a, statistical_anomaly_a):
    """Test anomaly detail view returns 200 and passes anomaly_obj."""
    url = reverse("bi:statistical_anomaly_detail", args=[statistical_anomaly_a.pk])
    res = client_a.get(url)
    assert res.status_code == 200
    assert res.context["anomaly_obj"] == statistical_anomaly_a
    assert statistical_anomaly_a.number in res.content.decode()


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_create_view(client_a, tenant_a, admin_user):
    """Test anomaly create view GET and POST with JSON root causes."""
    url = reverse("bi:statistical_anomaly_create")
    assert client_a.get(url).status_code == 200

    payload = {
        "title": "Payment Gateway Timeout Outlier",
        "metric_name": "gateway_timeout_rate",
        "anomaly_type": "spike",
        "detection_method": "z_score",
        "severity": "critical",
        "observed_value": "45.0000",
        "expected_value": "1.2000",
        "deviation_percentage": "3650.00",
        "anomaly_timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "triage_status": "open",
        "assigned_to": admin_user.pk,
        "root_cause_factors_raw": '[{"factor": "upstream_psp_outage", "pct": 95.0}]',
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302

    created = StatisticalAnomaly.objects.filter(tenant=tenant_a, title="Payment Gateway Timeout Outlier").first()
    assert created is not None
    assert created.severity == "critical"
    assert created.root_cause_factors[0]["factor"] == "upstream_psp_outage"


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_triage_action(client_a, tenant_a, statistical_anomaly_a, admin_user):
    """Test triage action updates status, notes, assigned user, and writes AuditLog."""
    url = reverse("bi:statistical_anomaly_triage", args=[statistical_anomaly_a.pk])
    payload = {
        "triage_status": "investigating",
        "resolution_notes": "Operations triage team assigned ticket to infrastructure team.",
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302
    assert post_res.url == statistical_anomaly_a.get_absolute_url()

    statistical_anomaly_a.refresh_from_db()
    assert statistical_anomaly_a.triage_status == "investigating"
    assert "Operations triage team" in statistical_anomaly_a.resolution_notes

    log = AuditLog.objects.filter(tenant=tenant_a, action="triage").first()
    assert log is not None


# ===========================================================================
# 4. OptimizationScenario Views
# ===========================================================================


@pytest.mark.django_db
def test_predictiveanalytics_scenario_list_view(client_a, optimization_scenario_a):
    """Test scenario list view returns 200, context variables, and filters."""
    url = reverse("bi:optimization_scenario_list")
    res = client_a.get(url)
    assert res.status_code == 200
    assert "optimization_scenarios" in res.context
    assert optimization_scenario_a in res.context["optimization_scenarios"]
    assert res.context["total_count"] >= 1
    assert "solver_status_choices" in res.context


@pytest.mark.django_db
def test_predictiveanalytics_scenario_detail_view(client_a, optimization_scenario_a):
    """Test scenario detail view returns 200 and passes scenario_obj."""
    url = reverse("bi:optimization_scenario_detail", args=[optimization_scenario_a.pk])
    res = client_a.get(url)
    assert res.status_code == 200
    assert res.context["scenario_obj"] == optimization_scenario_a
    assert len(optimization_scenario_a.decision_variables) == 1
    assert optimization_scenario_a.number in res.content.decode()


@pytest.mark.django_db
def test_predictiveanalytics_scenario_create_view(client_a, tenant_a, kpi_definition_a):
    """Test scenario create view GET and POST."""
    url = reverse("bi:optimization_scenario_create")
    assert client_a.get(url).status_code == 200

    payload = {
        "name": "Fleet Route Fuel Minimization",
        "slug": "fleet-route-fuel-minimization",
        "objective_type": "minimize",
        "target_metric_name": "gallons_consumed",
        "kpi_definition": kpi_definition_a.pk,
        "baseline_value": "12000.00",
        "target_value": "9500.00",
        "solver_algorithm": "linear_programming",
        "status": "active",
        "decision_variables_raw": '[{"name": "route_count", "min": 5, "max": 20}]',
        "constraint_rules_raw": '[{"rule": "delivery_sla <= 48"}]',
    }
    post_res = client_a.post(url, data=payload)
    assert post_res.status_code == 302

    created = OptimizationScenario.objects.filter(tenant=tenant_a, slug="fleet-route-fuel-minimization").first()
    assert created is not None
    assert created.objective_type == "minimize"
    assert post_res.url == created.get_absolute_url()


@pytest.mark.django_db
def test_predictiveanalytics_scenario_solve_action(client_a, tenant_a, optimization_scenario_a):
    """Test solve action executes prescriptive optimization heuristic and writes AuditLog."""
    url = reverse("bi:optimization_scenario_solve", args=[optimization_scenario_a.pk])
    post_res = client_a.post(url)
    assert post_res.status_code == 302
    assert post_res.url == optimization_scenario_a.get_absolute_url()

    optimization_scenario_a.refresh_from_db()
    assert optimization_scenario_a.solver_status == "optimal"
    assert len(optimization_scenario_a.recommended_actions) > 0

    log = AuditLog.objects.filter(tenant=tenant_a, action="solve").first()
    assert log is not None

"""Unit tests for Sub-module 10.13 Predictive & Advanced Analytics models.

Models covered:
- PredictiveModel (BPML)
- ForecastExecution (BFOR)
- StatisticalAnomaly (BANM)
- OptimizationScenario (BOPT)
"""
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    ForecastExecution,
    OptimizationScenario,
    PredictiveModel,
    StatisticalAnomaly,
)


def _predictiveanalytics_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


# ---------------------------------------------------------------------------
# 1. PredictiveModel Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_model_creation_and_autonumber(predictive_model_a):
    """Test PredictiveModel creation, BPML- auto-numbering, str and get_absolute_url."""
    assert predictive_model_a.pk is not None
    assert predictive_model_a.NUMBER_PREFIX == "BPML"
    assert predictive_model_a.number.startswith("BPML-")
    assert str(predictive_model_a) == f"{predictive_model_a.name} v{predictive_model_a.model_version} ({predictive_model_a.number})"
    assert predictive_model_a.get_absolute_url() == f"/bi/predictive-models/{predictive_model_a.pk}/"
    assert predictive_model_a.status == "active"
    assert predictive_model_a.problem_type == "time_series_forecast"
    assert predictive_model_a.algorithm == "arima"


@pytest.mark.django_db
def test_predictiveanalytics_model_choice_enumerations():
    """Verify choice keys match domain specifications."""
    problem_keys = _predictiveanalytics_choice_keys(PredictiveModel.PROBLEM_TYPE_CHOICES)
    assert "time_series_forecast" in problem_keys
    assert "binary_classification" in problem_keys
    assert "regression" in problem_keys
    assert "anomaly_detection" in problem_keys

    algorithm_keys = _predictiveanalytics_choice_keys(PredictiveModel.ALGORITHM_CHOICES)
    assert "arima" in algorithm_keys
    assert "random_forest" in algorithm_keys
    assert "gradient_boosting" in algorithm_keys

    status_keys = _predictiveanalytics_choice_keys(PredictiveModel.STATUS_CHOICES)
    assert "active" in status_keys
    assert "draft" in status_keys
    assert "training" in status_keys
    assert "retired" in status_keys


@pytest.mark.django_db
def test_predictiveanalytics_model_trigger_training(predictive_model_a):
    """Verify trigger_training executes simulation and updates model metrics."""
    assert predictive_model_a.accuracy_metric_value is None
    predictive_model_a.trigger_training()
    predictive_model_a.refresh_from_db()

    assert predictive_model_a.status == "active"
    assert predictive_model_a.accuracy_metric_name == "MAPE"
    assert predictive_model_a.accuracy_metric_value is not None
    assert Decimal("4.0") <= predictive_model_a.accuracy_metric_value <= Decimal("10.0")
    assert "historical_mean" in predictive_model_a.feature_importance


@pytest.mark.django_db
def test_predictiveanalytics_model_slug_uniqueness_per_tenant(tenant_a, admin_user):
    """Assert unique constraint on (tenant, slug)."""
    PredictiveModel.objects.create(
        tenant=tenant_a,
        name="Model One",
        slug="unique-slug-123",
        problem_type="regression",
        created_by=admin_user,
    )
    with pytest.raises(IntegrityError):
        PredictiveModel.objects.create(
            tenant=tenant_a,
            name="Model Duplicate Slug",
            slug="unique-slug-123",
            problem_type="regression",
            created_by=admin_user,
        )


# ---------------------------------------------------------------------------
# 2. ForecastExecution Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_forecast_creation_and_autonumber(forecast_execution_a):
    """Test ForecastExecution creation, BFOR- prefix, and string representation."""
    assert forecast_execution_a.pk is not None
    assert forecast_execution_a.NUMBER_PREFIX == "BFOR"
    assert forecast_execution_a.number.startswith("BFOR-")
    assert str(forecast_execution_a) == f"{forecast_execution_a.name} ({forecast_execution_a.number})"
    assert forecast_execution_a.get_absolute_url() == f"/bi/forecast-executions/{forecast_execution_a.pk}/"
    assert forecast_execution_a.horizon_periods == 6
    assert forecast_execution_a.confidence_level == "95"
    assert len(forecast_execution_a.forecast_output_data) == 2


@pytest.mark.django_db
def test_predictiveanalytics_forecast_generate_points_in_memory(tenant_a, admin_user, predictive_model_a):
    """Verify in-memory forecast points generation with save=False."""
    exec_obj = ForecastExecution(
        tenant=tenant_a,
        name="Test In-Memory Run",
        model=predictive_model_a,
        horizon_periods=4,
        confidence_level="95",
        executed_by=admin_user,
    )
    exec_obj.generate_forecast_points(base_value=50000.0, save=False)
    assert len(exec_obj.forecast_output_data) == 4
    assert exec_obj.mape_score is not None
    assert exec_obj.status == "completed"
    assert exec_obj.forecast_output_data[0]["predicted"] > 0
    # Record has not been saved to database yet
    assert exec_obj.pk is None


@pytest.mark.django_db
def test_predictiveanalytics_forecast_generate_points_with_save(forecast_execution_a):
    """Verify database update when generate_forecast_points is called with save=True."""
    forecast_execution_a.horizon_periods = 5
    forecast_execution_a.generate_forecast_points(save=True)
    forecast_execution_a.refresh_from_db()
    assert len(forecast_execution_a.forecast_output_data) == 5
    assert forecast_execution_a.status == "completed"


# ---------------------------------------------------------------------------
# 3. StatisticalAnomaly Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_creation_and_autonumber(statistical_anomaly_a):
    """Test StatisticalAnomaly creation, BANM- prefix, and string representation."""
    assert statistical_anomaly_a.pk is not None
    assert statistical_anomaly_a.NUMBER_PREFIX == "BANM"
    assert statistical_anomaly_a.number.startswith("BANM-")
    assert str(statistical_anomaly_a) == f"{statistical_anomaly_a.title} ({statistical_anomaly_a.number})"
    assert statistical_anomaly_a.get_absolute_url() == f"/bi/statistical-anomalies/{statistical_anomaly_a.pk}/"
    assert statistical_anomaly_a.severity == "critical"
    assert statistical_anomaly_a.triage_status == "open"
    assert statistical_anomaly_a.deviation_percentage == Decimal("608.75")


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_mark_triage(statistical_anomaly_a, admin_user):
    """Verify mark_triage updates triage status, resolution notes, and assigned user."""
    assert statistical_anomaly_a.triage_status == "open"
    statistical_anomaly_a.mark_triage(
        status="resolved",
        notes="Identified as automated stress test spike; marked resolved.",
        user=admin_user,
    )
    statistical_anomaly_a.refresh_from_db()
    assert statistical_anomaly_a.triage_status == "resolved"
    assert "automated stress test" in statistical_anomaly_a.resolution_notes
    assert statistical_anomaly_a.assigned_to == admin_user


# ---------------------------------------------------------------------------
# 4. OptimizationScenario Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_scenario_creation_and_autonumber(optimization_scenario_a):
    """Test OptimizationScenario creation, BOPT- prefix, and string representation."""
    assert optimization_scenario_a.pk is not None
    assert optimization_scenario_a.NUMBER_PREFIX == "BOPT"
    assert optimization_scenario_a.number.startswith("BOPT-")
    assert str(optimization_scenario_a) == f"{optimization_scenario_a.name} ({optimization_scenario_a.number})"
    assert optimization_scenario_a.get_absolute_url() == f"/bi/optimization-scenarios/{optimization_scenario_a.pk}/"
    assert optimization_scenario_a.objective_type == "maximize"
    assert optimization_scenario_a.solver_status == "optimal"


@pytest.mark.django_db
def test_predictiveanalytics_scenario_solve_execution(tenant_a, admin_user):
    """Verify solve_scenario runs prescriptive heuristic and updates optimal results."""
    scenario = OptimizationScenario.objects.create(
        tenant=tenant_a,
        name="Pending Optimization",
        slug="pending-optimization",
        objective_type="maximize",
        target_metric_name="operating_profit",
        baseline_value=Decimal("100000.00"),
        solver_algorithm="linear_programming",
        solver_status="draft",
        owner=admin_user,
        decision_variables=[{"name": "production_capacity", "min_val": 10, "max_val": 100}],
    )
    assert scenario.optimal_value is None

    scenario.solve_scenario()
    scenario.refresh_from_db()

    assert scenario.solver_status == "optimal"
    assert scenario.optimal_value is not None
    assert scenario.optimal_value > scenario.baseline_value
    assert scenario.projected_lift_percentage > Decimal("0")
    assert len(scenario.recommended_actions) > 0

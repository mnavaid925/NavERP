"""Unit tests for Sub-module 10.13 Predictive & Advanced Analytics forms.

Forms covered:
- PredictiveModelForm
- ForecastExecutionForm
- StatisticalAnomalyForm
- OptimizationScenarioForm
"""
import pytest
from django.utils import timezone

from apps.bi.forms import (
    ForecastExecutionForm,
    OptimizationScenarioForm,
    PredictiveModelForm,
    StatisticalAnomalyForm,
)
from apps.bi.models import (
    ForecastExecution,
    OptimizationScenario,
    PredictiveModel,
    StatisticalAnomaly,
)


# ---------------------------------------------------------------------------
# 1. PredictiveModelForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_model_form_system_field_exclusions():
    """Verify system fields (tenant, number, timestamps, metrics) are excluded."""
    form = PredictiveModelForm()
    for field in ["tenant", "number", "created_at", "updated_at", "accuracy_metric_value", "feature_importance"]:
        assert field not in form.fields, f"Security violation: {field} exposed in PredictiveModelForm"


@pytest.mark.django_db
def test_predictiveanalytics_model_form_valid_submission(tenant_a, semantic_model_a):
    """Test valid form payload parses JSON features and cleans properly."""
    data = {
        "name": "Customer Lifetime Value Model",
        "slug": "clv-model-2027",
        "problem_type": "regression",
        "algorithm": "gradient_boosting",
        "target_metric": "net_revenue_12m",
        "model_version": "1.0.0",
        "status": "draft",
        "drift_threshold": "10.00",
        "features_list_raw": '["recency", "frequency", "monetary_value"]',
        "hyperparameters_raw": '{"learning_rate": 0.05, "max_depth": 5}',
        "semantic_model": semantic_model_a.pk,
    }
    form = PredictiveModelForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"
    cleaned = form.cleaned_data
    assert cleaned["features_list_raw"] == ["recency", "frequency", "monetary_value"]
    assert cleaned["hyperparameters_raw"]["learning_rate"] == 0.05
    instance = form.save(commit=False)
    assert instance.features_list == ["recency", "frequency", "monetary_value"]
    assert instance.hyperparameters["learning_rate"] == 0.05


@pytest.mark.django_db
def test_predictiveanalytics_model_form_invalid_json_handling(tenant_a):
    """Verify malformed JSON inputs raise clean validation errors."""
    data = {
        "name": "Invalid JSON Model",
        "slug": "invalid-json-model",
        "problem_type": "regression",
        "algorithm": "gradient_boosting",
        "target_metric": "target",
        "features_list_raw": 'not-a-valid-json-string',
        "hyperparameters_raw": '{"incomplete_json":',
    }
    form = PredictiveModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "features_list_raw" in form.errors
    assert "hyperparameters_raw" in form.errors


@pytest.mark.django_db
def test_predictiveanalytics_model_form_reject_cross_tenant_fk(tenant_a, semantic_model_b):
    """Verify reject_foreign stops cross-tenant semantic model assignment."""
    data = {
        "name": "Cross Tenant Exploit Model",
        "slug": "cross-tenant-exploit",
        "problem_type": "regression",
        "algorithm": "gradient_boosting",
        "target_metric": "sales",
        "semantic_model": semantic_model_b.pk,
    }
    form = PredictiveModelForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors


# ---------------------------------------------------------------------------
# 2. ForecastExecutionForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_forecast_form_exclusions():
    """Verify forecast output and internal fields are excluded."""
    form = ForecastExecutionForm()
    for field in ["tenant", "number", "created_at", "updated_at", "executed_at", "forecast_output_data", "mape_score"]:
        assert field not in form.fields, f"Security violation: {field} exposed in ForecastExecutionForm"


@pytest.mark.django_db
def test_predictiveanalytics_forecast_form_tenant_scoping(tenant_a, predictive_model_a, predictive_model_b):
    """Verify ForeignKey dropdowns in ForecastExecutionForm are strictly scoped to tenant."""
    form = ForecastExecutionForm(tenant=tenant_a)
    model_qs = form.fields["model"].queryset
    assert predictive_model_a in model_qs
    assert predictive_model_b not in model_qs


@pytest.mark.django_db
def test_predictiveanalytics_forecast_form_valid_submission(tenant_a, predictive_model_a, kpi_definition_a):
    """Verify valid forecast execution submission."""
    data = {
        "name": "Q3 2027 Revenue Projection",
        "model": predictive_model_a.pk,
        "kpi_definition": kpi_definition_a.pk,
        "cadence": "quarterly",
        "horizon_periods": 4,
        "confidence_level": "95",
        "historical_window_periods": 24,
        "trend_direction": "upward",
        "notes": "Forecast for quarterly planning",
    }
    form = ForecastExecutionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"


@pytest.mark.django_db
def test_predictiveanalytics_forecast_form_reject_foreign(tenant_a, predictive_model_b):
    """Verify cross-tenant model assignment fails validation."""
    data = {
        "name": "Unauthorized Foreign Model Forecast",
        "model": predictive_model_b.pk,
        "cadence": "monthly",
        "horizon_periods": 6,
    }
    form = ForecastExecutionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "model" in form.errors


# ---------------------------------------------------------------------------
# 3. StatisticalAnomalyForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_form_assigned_to_tenant_scoping(tenant_a, admin_user, admin_user_b):
    """Verify assigned_to user dropdown is strictly scoped to tenant users (I1 fix)."""
    form = StatisticalAnomalyForm(tenant=tenant_a)
    assigned_qs = form.fields["assigned_to"].queryset
    assert admin_user in assigned_qs
    assert admin_user_b not in assigned_qs, "Cross-tenant user leakage detected in assigned_to dropdown!"


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_form_valid_submission(tenant_a, admin_user):
    """Verify valid statistical anomaly creation with JSON root cause factors."""
    data = {
        "title": "API Gateway Request Latency Spike",
        "metric_name": "api_p99_latency_ms",
        "anomaly_type": "spike",
        "detection_method": "z_score",
        "severity": "critical",
        "observed_value": "940.50",
        "expected_value": "110.00",
        "deviation_percentage": "755.00",
        "anomaly_timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "triage_status": "open",
        "assigned_to": admin_user.pk,
        "root_cause_factors_raw": '[{"factor": "db_connection_pool_saturation", "pct": 80.0}]',
    }
    form = StatisticalAnomalyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"
    assert form.cleaned_data["root_cause_factors_raw"][0]["factor"] == "db_connection_pool_saturation"
    instance = form.save(commit=False)
    assert instance.root_cause_factors[0]["factor"] == "db_connection_pool_saturation"


@pytest.mark.django_db
def test_predictiveanalytics_anomaly_form_reject_foreign_user(tenant_a, admin_user_b):
    """Verify cross-tenant user assignment is rejected by clean() validation."""
    data = {
        "title": "Exploit Cross-Tenant Assignment",
        "metric_name": "metric",
        "anomaly_type": "spike",
        "severity": "warning",
        "observed_value": "100.00",
        "expected_value": "50.00",
        "deviation_percentage": "100.00",
        "anomaly_timestamp": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
        "assigned_to": admin_user_b.pk,
    }
    form = StatisticalAnomalyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_to" in form.errors


# ---------------------------------------------------------------------------
# 4. OptimizationScenarioForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_predictiveanalytics_scenario_form_exclusions():
    """Verify optimal_value and system fields are excluded from OptimizationScenarioForm."""
    form = OptimizationScenarioForm()
    for field in ["tenant", "number", "created_at", "updated_at", "optimal_value", "projected_lift_percentage"]:
        assert field not in form.fields, f"Security violation: {field} exposed in OptimizationScenarioForm"


@pytest.mark.django_db
def test_predictiveanalytics_scenario_form_valid_submission(tenant_a, kpi_definition_a):
    """Verify valid optimization scenario with structured decision levers."""
    data = {
        "name": "Dynamic Pricing Margin Optimization",
        "slug": "dynamic-pricing-margin-opt",
        "objective_type": "maximize",
        "target_metric_name": "gross_margin",
        "kpi_definition": kpi_definition_a.pk,
        "baseline_value": "150000.00",
        "target_value": "180000.00",
        "solver_algorithm": "linear_programming",
        "status": "active",
        "decision_variables_raw": '[{"name": "discount_rate", "min": 0.05, "max": 0.25}]',
        "constraint_rules_raw": '[{"rule": "margin >= 0.35"}]',
    }
    form = OptimizationScenarioForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Validation errors: {form.errors}"
    assert form.cleaned_data["decision_variables_raw"][0]["name"] == "discount_rate"
    assert form.cleaned_data["constraint_rules_raw"][0]["rule"] == "margin >= 0.35"
    instance = form.save(commit=False)
    assert instance.decision_variables[0]["name"] == "discount_rate"
    assert instance.constraint_rules[0]["rule"] == "margin >= 0.35"


@pytest.mark.django_db
def test_predictiveanalytics_scenario_form_reject_foreign_kpi(tenant_a, kpi_definition_b):
    """Verify reject_foreign rejects foreign tenant KPI definition."""
    data = {
        "name": "Cross Tenant KPI Exploit",
        "slug": "cross-tenant-kpi-exploit",
        "objective_type": "maximize",
        "target_metric_name": "revenue",
        "kpi_definition": kpi_definition_b.pk,
        "solver_algorithm": "linear_programming",
        "status": "draft",
    }
    form = OptimizationScenarioForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi_definition" in form.errors

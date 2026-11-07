# Contract — Sub-module 10.13: Predictive & Advanced Analytics (Module 10: Business Intelligence, `bi`)

- **Sub-module:** 10.13 Predictive & Advanced Analytics • **Module:** 10 Business Intelligence • **App:** `apps/bi`
- **Date:** 2026-11-07 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Existing app `apps/bi/` (scaffolded in 10.1; extended across 10.2 through 10.12). Incremental migration: `0030_...`
- **Package Layout:** `PredictiveAnalytics/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/bi/predictive_analytics/`.

---

## 1. Models & CHOICES Contract

All 4 top-level models inherit from `apps.bi.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `PredictiveModel` (`apps/bi/models/PredictiveAnalytics/PredictiveModels.py`)
- **Table:** `bi_predictive_model`
- **Number Prefix:** `BPML` (`BPML-00001`)
- **CHOICES:**
  - `PROBLEM_TYPE_CHOICES = [('time_series_forecast', 'Time-Series Forecasting'), ('binary_classification', 'Binary Classification (Propensity/Churn)'), ('multiclass_classification', 'Multiclass Classification'), ('regression', 'Value Regression (Numeric Prediction)'), ('anomaly_detection', 'Statistical Anomaly Detection')]`
  - `ALGORITHM_CHOICES = [('linear_regression', 'Linear / Ridge Regression'), ('logistic_regression', 'Logistic Regression'), ('random_forest', 'Random Forest Ensemble'), ('gradient_boosting', 'Gradient Boosted Trees (GBM)'), ('exponential_smoothing', 'Holt-Winters / Exponential Smoothing'), ('arima', 'Auto-ARIMA'), ('isolation_forest', 'Isolation Forest'), ('z_score', 'Moving Z-Score / Statistical Baseline')]`
  - `STATUS_CHOICES = [('draft', 'Draft Configuration'), ('training', 'Training / Fitting'), ('active', 'Active / Deployed'), ('under_review', 'Under Review'), ('retired', 'Retired')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `problem_type`: `CharField(max_length=35, choices=PROBLEM_TYPE_CHOICES, default='time_series_forecast')`
  - `algorithm`: `CharField(max_length=40, choices=ALGORITHM_CHOICES, default='exponential_smoothing')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='predictive_models')`
  - `warehouse_table`: `ForeignKey('bi.WarehouseTable', null=True, blank=True, on_delete=models.SET_NULL, related_name='predictive_models')`
  - `target_metric`: `CharField(max_length=120, help_text="Target column or metric being predicted")`
  - `features_list`: `JSONField(default=list, help_text="List of feature column names used for training")`
  - `hyperparameters`: `JSONField(default=dict, help_text="Model tuning hyperparameters")`
  - `model_version`: `CharField(max_length=20, default='1.0.0')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `accuracy_metric_name`: `CharField(max_length=30, default='R2', help_text="Evaluation metric name (e.g., R2, RMSE, AUC, F1, MAPE)")`
  - `accuracy_metric_value`: `DecimalField(max_digits=8, decimal_places=4, null=True, blank=True, help_text="Validated performance score")`
  - `feature_importance`: `JSONField(default=dict, help_text="Relative feature weightings / contributions")`
  - `drift_threshold`: `DecimalField(max_digits=5, decimal_places=2, default=15.00, help_text="Percentage drift trigger for re-training")`
  - `is_active`: `BooleanField(default=True)`
  - `created_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_predictive_models')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bpml_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bpml_tenant_num_uniq')`
  - `Index(fields=['tenant', 'problem_type'], name='idx_bpml_ten_prob')`
  - `Index(fields=['tenant', 'status'], name='idx_bpml_ten_stat')`
  - `Index(fields=['tenant', 'created_by'], name='idx_bpml_ten_user')`

---

### 1.2 `ForecastExecution` (`apps/bi/models/PredictiveAnalytics/ForecastExecutions.py`)
- **Table:** `bi_forecast_execution`
- **Number Prefix:** `BFOR` (`BFOR-00001`)
- **CHOICES:**
  - `CADENCE_CHOICES = [('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('annual', 'Annual')]`
  - `CONFIDENCE_CHOICES = [('80', '80% Confidence Interval'), ('90', '90% Confidence Interval'), ('95', '95% Confidence Interval'), ('99', '99% Confidence Interval')]`
  - `TREND_CHOICES = [('upward', 'Upward Trend'), ('downward', 'Downward Trend'), ('stable', 'Stable / Horizontal'), ('volatile', 'Volatile / Irregular')]`
  - `STATUS_CHOICES = [('pending', 'Pending Execution'), ('running', 'Running Prediction'), ('completed', 'Completed'), ('failed', 'Failed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `model`: `ForeignKey('bi.PredictiveModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='forecast_executions')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='forecast_executions')`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='forecast_executions')`
  - `cadence`: `CharField(max_length=20, choices=CADENCE_CHOICES, default='monthly')`
  - `horizon_periods`: `PositiveIntegerField(default=12, help_text="Number of forward-looking periods to predict")`
  - `confidence_level`: `CharField(max_length=10, choices=CONFIDENCE_CHOICES, default='95')`
  - `historical_window_periods`: `PositiveIntegerField(default=36, help_text="Lookback periods used for training")`
  - `seasonality_detected`: `BooleanField(default=False)`
  - `seasonal_cycle_length`: `PositiveIntegerField(default=12, help_text="Lag periods for detected seasonality")`
  - `trend_direction`: `CharField(max_length=20, choices=TREND_CHOICES, default='upward')`
  - `mape_score`: `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Mean Absolute Percentage Error (%)")`
  - `forecast_output_data`: `JSONField(default=list, help_text="Array of point predictions with upper/lower bounds: [{period, point, lower, upper}]")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='completed')`
  - `execution_duration_ms`: `PositiveIntegerField(default=0)`
  - `notes`: `TextField(blank=True)`
  - `executed_by`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='executed_bi_forecasts')`
  - `executed_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bfor_tenant_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_bfor_ten_stat')`
  - `Index(fields=['tenant', 'cadence'], name='idx_bfor_ten_cad')`
  - `Index(fields=['tenant', 'executed_by'], name='idx_bfor_ten_user')`

---

### 1.3 `StatisticalAnomaly` (`apps/bi/models/PredictiveAnalytics/StatisticalAnomalies.py`)
- **Table:** `bi_statistical_anomaly`
- **Number Prefix:** `BANM` (`BANM-00001`)
- **CHOICES:**
  - `ANOMALY_TYPE_CHOICES = [('spike', 'Positive Spike'), ('dip', 'Negative Dip'), ('trend_break', 'Structural Trend Break'), ('variance_outlier', 'Variance Outlier')]`
  - `METHOD_CHOICES = [('z_score', 'Z-Score (Sigma Deviation)'), ('iqr', 'Interquartile Range (IQR)'), ('isolation_forest', 'Isolation Forest'), ('moving_average', 'Moving Average Envelope')]`
  - `SEVERITY_CHOICES = [('info', 'Informational Notice'), ('warning', 'Moderate Warning'), ('critical', 'Critical Anomaly')]`
  - `TRIAGE_CHOICES = [('open', 'Open / Unreviewed'), ('acknowledged', 'Acknowledged'), ('investigating', 'Under Investigation'), ('false_positive', 'False Positive'), ('resolved', 'Resolved')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `model`: `ForeignKey('bi.PredictiveModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='detected_anomalies')`
  - `semantic_model`: `ForeignKey('bi.SemanticModel', null=True, blank=True, on_delete=models.SET_NULL, related_name='statistical_anomalies')`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='statistical_anomalies')`
  - `metric_name`: `CharField(max_length=120)`
  - `anomaly_type`: `CharField(max_length=20, choices=ANOMALY_TYPE_CHOICES, default='spike')`
  - `detection_method`: `CharField(max_length=30, choices=METHOD_CHOICES, default='z_score')`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')`
  - `observed_value`: `DecimalField(max_digits=16, decimal_places=4)`
  - `expected_value`: `DecimalField(max_digits=16, decimal_places=4)`
  - `deviation_percentage`: `DecimalField(max_digits=8, decimal_places=2)`
  - `anomaly_timestamp`: `DateTimeField()`
  - `root_cause_factors`: `JSONField(default=list, help_text="Contributing drivers and dimension segments")`
  - `triage_status`: `CharField(max_length=20, choices=TRIAGE_CHOICES, default='open')`
  - `resolution_notes`: `TextField(blank=True)`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_anomalies')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_banm_tenant_num_uniq')`
  - `Index(fields=['tenant', 'triage_status'], name='idx_banm_ten_triage')`
  - `Index(fields=['tenant', 'severity'], name='idx_banm_ten_sev')`
  - `Index(fields=['tenant', 'assigned_to'], name='idx_banm_ten_user')`

---

### 1.4 `OptimizationScenario` (`apps/bi/models/PredictiveAnalytics/OptimizationScenarios.py`)
- **Table:** `bi_optimization_scenario`
- **Number Prefix:** `BOPT` (`BOPT-00001`)
- **CHOICES:**
  - `OBJECTIVE_CHOICES = [('maximize', 'Maximize Objective'), ('minimize', 'Minimize Cost / Risk'), ('target_value', 'Reach Specific Target Value')]`
  - `ALGORITHM_CHOICES = [('linear_programming', 'Linear Programming (Simplex)'), ('goal_programming', 'Goal Programming / Multi-Objective'), ('heuristic', 'Greedy Heuristic / Hill Climbing')]`
  - `SOLVER_STATUS_CHOICES = [('draft', 'Draft Setup'), ('optimal', 'Optimal Solution Found'), ('feasible', 'Feasible (Sub-Optimal)'), ('infeasible', 'Infeasible (Constraints Conflict)'), ('unbounded', 'Unbounded')]`
  - `STATUS_CHOICES = [('active', 'Active Scenario'), ('draft', 'Draft Exploration'), ('applied', 'Applied / Implemented'), ('archived', 'Archived')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='+')`
  - `number`: `CharField(max_length=20, editable=False)`
  - `name`: `CharField(max_length=200)`
  - `slug`: `SlugField(max_length=120)`
  - `description`: `TextField(blank=True)`
  - `objective_type`: `CharField(max_length=20, choices=OBJECTIVE_CHOICES, default='maximize')`
  - `target_metric_name`: `CharField(max_length=120, help_text="Metric/KPI being optimized")`
  - `kpi_definition`: `ForeignKey('bi.KpiDefinition', null=True, blank=True, on_delete=models.SET_NULL, related_name='optimization_scenarios')`
  - `baseline_value`: `DecimalField(max_digits=16, decimal_places=4, default=0.00)`
  - `target_value`: `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)`
  - `optimal_value`: `DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)`
  - `projected_lift_percentage`: `DecimalField(max_digits=8, decimal_places=2, default=0.00)`
  - `solver_algorithm`: `CharField(max_length=30, choices=ALGORITHM_CHOICES, default='linear_programming')`
  - `solver_status`: `CharField(max_length=20, choices=SOLVER_STATUS_CHOICES, default='draft')`
  - `decision_variables`: `JSONField(default=list, help_text="List of controllable levers, min/max bounds, step size")`
  - `constraint_rules`: `JSONField(default=list, help_text="Operational boundary equations")`
  - `recommended_actions`: `JSONField(default=list, help_text="Prescriptive next-best-actions with expected delta")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='owned_optimization_scenarios')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'slug'], name='bi_bopt_tenant_slug_uniq')`
  - `UniqueConstraint(fields=['tenant', 'number'], name='bi_bopt_tenant_num_uniq')`
  - `Index(fields=['tenant', 'solver_status'], name='idx_bopt_ten_solv')`
  - `Index(fields=['tenant', 'status'], name='idx_bopt_ten_stat')`
  - `Index(fields=['tenant', 'owner'], name='idx_bopt_ten_user')`

---

## 2. Forms Contract (`apps/bi/forms/PredictiveAnalytics/`)

### 2.1 `PredictiveModelForm` (`apps/bi/forms/PredictiveAnalytics/PredictiveModels.py`)
- **Fields:** `['name', 'slug', 'description', 'problem_type', 'algorithm', 'semantic_model', 'warehouse_table', 'target_metric', 'drift_threshold', 'is_active', 'status']`
- **Exclusions:** `['tenant', 'number', 'created_by', 'created_at', 'updated_at', 'features_list', 'hyperparameters', 'model_version', 'accuracy_metric_name', 'accuracy_metric_value', 'feature_importance']`
- **Tenant scoping in `__init__`:** Filter `semantic_model` and `warehouse_table` by `tenant`.

### 2.2 `ForecastExecutionForm` (`apps/bi/forms/PredictiveAnalytics/ForecastExecutions.py`)
- **Fields:** `['name', 'model', 'semantic_model', 'kpi_definition', 'cadence', 'horizon_periods', 'confidence_level', 'historical_window_periods', 'notes']`
- **Exclusions:** `['tenant', 'number', 'executed_by', 'executed_at', 'updated_at', 'seasonality_detected', 'seasonal_cycle_length', 'trend_direction', 'mape_score', 'forecast_output_data', 'status', 'execution_duration_ms']`
- **Tenant scoping in `__init__`:** Filter `model`, `semantic_model`, and `kpi_definition` by `tenant`.

### 2.3 `StatisticalAnomalyForm` (`apps/bi/forms/PredictiveAnalytics/StatisticalAnomalies.py`)
- **Fields:** `['title', 'model', 'semantic_model', 'kpi_definition', 'metric_name', 'anomaly_type', 'detection_method', 'severity', 'observed_value', 'expected_value', 'deviation_percentage', 'anomaly_timestamp', 'triage_status', 'resolution_notes', 'assigned_to']`
- **Exclusions:** `['tenant', 'number', 'created_at', 'updated_at', 'root_cause_factors']`
- **Tenant scoping in `__init__`:** Filter FK querysets by `tenant`.

### 2.4 `OptimizationScenarioForm` (`apps/bi/forms/PredictiveAnalytics/OptimizationScenarios.py`)
- **Fields:** `['name', 'slug', 'description', 'objective_type', 'target_metric_name', 'kpi_definition', 'baseline_value', 'target_value', 'solver_algorithm', 'status']`
- **Exclusions:** `['tenant', 'number', 'owner', 'created_at', 'updated_at', 'optimal_value', 'projected_lift_percentage', 'solver_status', 'decision_variables', 'constraint_rules', 'recommended_actions']`
- **Tenant scoping in `__init__`:** Filter `kpi_definition` by `tenant`.

---

## 3. URLs & View Context Contract (`apps/bi/urls/PredictiveAnalytics/` & `views/`)

### 3.1 `PredictiveModel` URLs (`bi:predictive_model_*`)
- `bi:predictive_model_list` (`predictive-models/`) -> context: `{'predictive_models': page_obj, 'status_choices': ..., 'problem_type_choices': ...}`
- `bi:predictive_model_detail` (`predictive-models/<int:pk>/`) -> context: `{'model_obj': model, 'executions': ..., 'anomalies': ...}`
- `bi:predictive_model_create` (`predictive-models/create/`) -> context: `{'form': form}`
- `bi:predictive_model_edit` (`predictive-models/<int:pk>/edit/`) -> context: `{'form': form, 'model_obj': model}`
- `bi:predictive_model_delete` (`predictive-models/<int:pk>/delete/`) -> POST-only
- `bi:predictive_model_train` (`predictive-models/<int:pk>/train/`) -> POST-only

### 3.2 `ForecastExecution` URLs (`bi:forecast_execution_*`)
- `bi:forecast_execution_list` (`forecast-executions/`) -> context: `{'forecast_executions': page_obj, 'status_choices': ..., 'cadence_choices': ...}`
- `bi:forecast_execution_detail` (`forecast-executions/<int:pk>/`) -> context: `{'forecast_obj': execution}`
- `bi:forecast_execution_create` (`forecast-executions/create/`) -> context: `{'form': form}`
- `bi:forecast_execution_edit` (`forecast-executions/<int:pk>/edit/`) -> context: `{'form': form, 'forecast_obj': execution}`
- `bi:forecast_execution_delete` (`forecast-executions/<int:pk>/delete/`) -> POST-only

### 3.3 `StatisticalAnomaly` URLs (`bi:statistical_anomaly_*`)
- `bi:statistical_anomaly_list` (`statistical-anomalies/`) -> context: `{'statistical_anomalies': page_obj, 'severity_choices': ..., 'triage_choices': ...}`
- `bi:statistical_anomaly_detail` (`statistical-anomalies/<int:pk>/`) -> context: `{'anomaly_obj': anomaly}`
- `bi:statistical_anomaly_create` (`statistical-anomalies/create/`) -> context: `{'form': form}`
- `bi:statistical_anomaly_edit` (`statistical-anomalies/<int:pk>/edit/`) -> context: `{'form': form, 'anomaly_obj': anomaly}`
- `bi:statistical_anomaly_delete` (`statistical-anomalies/<int:pk>/delete/`) -> POST-only
- `bi:statistical_anomaly_triage` (`statistical-anomalies/<int:pk>/triage/`) -> POST-only

### 3.4 `OptimizationScenario` URLs (`bi:optimization_scenario_*`)
- `bi:optimization_scenario_list` (`optimization-scenarios/`) -> context: `{'optimization_scenarios': page_obj, 'status_choices': ..., 'solver_status_choices': ...}`
- `bi:optimization_scenario_detail` (`optimization-scenarios/<int:pk>/`) -> context: `{'scenario_obj': scenario}`
- `bi:optimization_scenario_create` (`optimization-scenarios/create/`) -> context: `{'form': form}`
- `bi:optimization_scenario_edit` (`optimization-scenarios/<int:pk>/edit/`) -> context: `{'form': form, 'scenario_obj': scenario}`
- `bi:optimization_scenario_delete` (`optimization-scenarios/<int:pk>/delete/`) -> POST-only
- `bi:optimization_scenario_solve` (`optimization-scenarios/<int:pk>/solve/`) -> POST-only

---

## 4. Navigation LIVE_LINKS Mapping

`apps/core/navigation.py`:
```python
    "10.13": {
        "Forecasting & Trend Analysis": "bi:forecast_execution_list",
        "Predictive & Propensity Models": "bi:predictive_model_list",
        "Prescriptive & Optimization": "bi:optimization_scenario_list",
        "Anomaly & Outlier Detection": "bi:statistical_anomaly_list",
        "AutoML & Model Lifecycle": "bi:predictive_model_list",
    },
```

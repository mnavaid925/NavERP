# Review Findings — Module 10.13: Predictive & Advanced Analytics

**Base Commit:** `831d4a2fa67f1876bab24a5541f0e35ea4ec45e9`

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Verdict
Commit after fixing Critical+Important findings.

### Critical
1. `apps/bi/forms/PredictiveAnalytics/PredictiveModels.py:111-115` — `clean_semantic_model` and `clean_warehouse_table` invoke `reject_foreign(self.tenant, ...)` with only 2 positional arguments, raising `TypeError: reject_foreign() missing 1 required positional argument: 'names'` on form submission. Fix: Replace both per-field methods with a canonical `clean(self)` method calling `reject_foreign(self, cleaned_data, ["semantic_model", "warehouse_table"])` and returning `cleaned_data`.
2. `apps/bi/forms/PredictiveAnalytics/ForecastExecutions.py:44-51` — `clean_model`, `clean_semantic_model`, and `clean_kpi_definition` invoke `reject_foreign(self.tenant, ...)` with 2 positional arguments, causing `TypeError` on all create/edit POST requests. Fix: Replace with `clean(self)` calling `reject_foreign(self, cleaned_data, ["model", "semantic_model", "kpi_definition"])` and returning `cleaned_data`.
3. `apps/bi/forms/PredictiveAnalytics/StatisticalAnomalies.py:98-105` — `clean_model`, `clean_semantic_model`, and `clean_kpi_definition` invoke `reject_foreign(self.tenant, ...)` with 2 positional arguments, causing `TypeError` on all create/edit POST requests. Fix: Replace with `clean(self)` calling `reject_foreign(self, cleaned_data, ["model", "semantic_model", "kpi_definition", "assigned_to"])` and returning `cleaned_data`.
4. `apps/bi/forms/PredictiveAnalytics/OptimizationScenarios.py:111-113` — `clean_kpi_definition` invokes `reject_foreign(self.tenant, ...)` with 2 positional arguments, causing `TypeError` on all scenario save attempts. Fix: Replace with `clean(self)` calling `reject_foreign(self, cleaned_data, ["kpi_definition"])` and returning `cleaned_data`.

### Important
1. `apps/bi/management/commands/seed_bi.py:84-136` — The `--flush` command deletes other BI tables but completely omits the four 10.13 tables (`OptimizationScenario`, `StatisticalAnomaly`, `ForecastExecution`, `PredictiveModel`), leaving orphaned records when parent models are deleted. Fix: Add 10.13 model `.delete()` calls to the flush list before their foreign targets are deleted.
2. `templates/bi/predictive_analytics/forecast_execution/detail.html:163` — Raw Python representation of output points `const rawData = {{ forecast_obj.forecast_output_data|safe }};` renders single quotes and Python literals (`None`, `True`), risking JavaScript `SyntaxError` or `ReferenceError` when parsed in browser. Fix: Use Django's built-in `{{ forecast_obj.forecast_output_data|json_script:"forecast-output-data" }}` and load it with `JSON.parse(document.getElementById("forecast-output-data").textContent)`.
3. `templates/bi/predictive_analytics/statistical_anomaly/form.html:36-71` — `StatisticalAnomalyForm.Meta.fields` declares `semantic_model`, but the field is omitted from `form.html`, preventing users from setting or updating the semantic model relation. Fix: Render `form.semantic_model` in the incident classification section of `form.html`.
4. `apps/bi/forms/PredictiveAnalytics/ForecastExecutions.py:40-42` — `model` and `kpi_definition` querysets in `__init__` filter strictly by `is_active=True`, which prevents saving edits to existing forecast executions whose linked model or KPI has since become inactive. Fix: Preserve existing instance selections using `Q(is_active=True) | Q(pk=self.instance.model_id)` and `Q(is_active=True) | Q(pk=self.instance.kpi_definition_id)`.

### Minor
1. `templates/bi/predictive_analytics/forecast_execution/detail.html:145` — Uncertainty spread is rendered using `&plusmn;{{ pt.upper_bound|add:pt.lower_bound }}`, which adds the upper and lower bounds together (displaying 2x point prediction) rather than displaying the margin. Fix: Include `"margin": margin` in the dictionary generated in `ForecastExecution.generate_forecast_points()` and render `&plusmn;{{ pt.margin }}`.
2. `templates/bi/predictive_analytics/optimization_scenario/detail.html:59-100` — `scenario_obj.description`, `scenario_obj.kpi_definition`, and `scenario_obj.owner` are fetched with `select_related` in the view but omitted from the detail template. Fix: Add an information section to `detail.html` displaying the scenario description, linked KPI link, and owner.
3. `templates/bi/predictive_analytics/forecast_execution/detail.html:160` — Duplicate script import `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>` in detail template. Fix: Remove redundant `<script>` tag since `templates/base.html` already loads Chart.js globally.

### Done Well
- Excellent architecture: all 4 models inherit from `TenantNumbered` with reliable sequence generation, complete database indices, tenant uniqueness constraints, and explicit reverse URLs.
- Robust security & permissions: all list views apply `bi_scope(..., owner_field=...)`, all mutations/deletions use `bi_object(..., pk=...)` with POST requirements and tenant admin gates, and actions write comprehensive audit logs.
- Design system compliance: full adherence to `theme.css` colour-named badges and stat-card icons (`green`, `amber`, `red`, `info`, `slate`), responsive tables, and zero inline CSS regressions.

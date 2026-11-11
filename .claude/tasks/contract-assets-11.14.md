# Pre-Build Contract: Sub-module 11.14 — Asset Analytics & Business Intelligence (`apps/assets`)

**Status:** Frozen Specification (Phase 3.1)  
**App Slug / Namespace:** `assets` (`apps/assets`)  
**Package Folder:** `apps/assets/{models,forms,views,urls}/AssetAnalytics/`  
**Template Folder:** `templates/assets/assetanalytics/<entity>/`  
**Core Spine Reuse:** `accounting.FixedAsset`, `accounting.Budget`, `accounting.Currency` (GLOBAL — never filter by `tenant`), `scm.Asset`, `scm.Location`, `core.OrgUnit`, `settings.AUTH_USER_MODEL`, `assets.AssetCategory`, `assets.AssetModel`, `assets.AssetConditionAssessment`, `assets.AssetRequisition`.  
**Cross-App / Sibling Guardrails:**
- All 4 persistent models inherit `TenantNumbered` (`apps/assets/models/_base.py`, which already defines `tenant`, `number`, `created_at`, `updated_at` — do NOT redeclare `tenant` on subclasses).
- Every `CharField(choices=...)` enforces `max_length >= longest choice key` (`L65`).
- Every `Meta.constraints` / `Meta.indexes` name is `<= 30` chars (`L65`).
- Every badge CSS dictionary uses ONLY valid `static/css/theme.css` classes: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
- `write_audit_log` `action` string is strictly `<= 10` chars (`AuditLog.action` max_length=10, `L66`).
- Zero foreign keys to `apps/bi` (`Report`, `Dataset`, etc.).
- CSV exports sanitize every cell with `csv_safe()` against formula injection (`=`, `+`, `-`, `@`, `\t`, `\r`, `\n`) and emit `X-Content-Type-Options: nosniff`.

---

## 1. Models Contract

### 1.1 `AssetLifecycleCostAnalysis` (`apps/assets/models/AssetAnalytics/AssetLifecycleCostAnalyses.py`)
- **Table:** `assets_assetlifecyclecostanalysis`
- **Number Prefix:** `ALCC` (`ALCC-YYYYMM-XXXX`)
- **CHOICES:**
  - `LIFECYCLE_STAGE_CHOICES = [("acquisition", "Acquisition & Commissioning"), ("in_service", "Active In-Service"), ("mid_life", "Mid-Life Operations"), ("late_life", "Late-Life / High Maintenance"), ("end_of_life", "End-of-Life Candidate"), ("disposed", "Disposed / Retired")]` (`max_length=20`)
  - `STATUS_CHOICES = [("draft", "Draft"), ("calculated", "Calculated"), ("reviewed", "Reviewed"), ("approved", "Approved"), ("archived", "Archived")]` (`max_length=20`)
  - `RECOMMENDATION_CHOICES = [("retain_operate", "Retain & Operate"), ("overhaul_refurbish", "Overhaul / Refurbish"), ("schedule_replacement", "Schedule Replacement"), ("dispose_retire", "Dispose / Retire")]` (`max_length=30`)
  - `STATUS_CSS = {"draft": "badge-slate", "calculated": "badge-info", "reviewed": "badge-amber", "approved": "badge-green", "archived": "badge-muted"}`
  - `LIFECYCLE_STAGE_CSS = {"acquisition": "badge-info", "in_service": "badge-green", "mid_life": "badge-slate", "late_life": "badge-amber", "end_of_life": "badge-red", "disposed": "badge-muted"}`
  - `RECOMMENDATION_CSS = {"retain_operate": "badge-green", "overhaul_refurbish": "badge-info", "schedule_replacement": "badge-amber", "dispose_retire": "badge-red"}`
- **Fields:**
  - Inherited from `TenantNumbered`: `tenant`, `number`, `created_at`, `updated_at`
  - `title`: `CharField(max_length=255)`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=SET_NULL, null=True, blank=True, related_name="lifecycle_cost_analyses")`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=SET_NULL, null=True, blank=True, related_name="lifecycle_cost_analyses")`
  - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="lifecycle_cost_analyses")`
  - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=SET_NULL, null=True, blank=True, related_name="lifecycle_cost_analyses")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="asset_lifecycle_analyses")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="asset_lifecycle_analyses")` *(GLOBAL — no tenant filter)*
  - `analyzed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="asset_lifecycle_analyses")`
  - `analysis_date`: `DateField(default=timezone.localdate)`
  - `analysis_horizon_years`: `PositiveSmallIntegerField(default=5)`
  - `discount_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("8.00"))`
  - `lifecycle_stage`: `CharField(max_length=20, choices=LIFECYCLE_STAGE_CHOICES, default="in_service")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - Spend & Recovery Buckets (`DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`):
    - `acquisition_capital_cost`
    - `installation_commissioning_cost`
    - `preventive_maintenance_cost`
    - `corrective_maintenance_cost`
    - `service_contract_cost`
    - `energy_utility_cost`
    - `downtime_opportunity_cost`
    - `insurance_compliance_cost`
    - `accumulated_depreciation_cost`
    - `expected_salvage_value`
    - `warranty_insurance_recoveries`
    - `current_replacement_value`
  - Computed Outputs:
    - `total_lifecycle_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `equivalent_annual_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
    - `maintenance_to_rav_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `opex_to_capex_ratio`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `economic_eol_year`: `PositiveIntegerField(null=True, blank=True)`
    - `recommendation`: `CharField(max_length=30, choices=RECOMMENDATION_CHOICES, default="retain_operate")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_alcc_ten_num_uniq")` (24)
  - `Index(fields=["tenant", "status"], name="idx_alcc_ten_stat")` (17)
  - `Index(fields=["tenant", "lifecycle_stage"], name="idx_alcc_ten_stg")` (16)
  - `Index(fields=["tenant", "recommendation"], name="idx_alcc_ten_rec")` (16)
  - `Index(fields=["tenant", "analysis_date"], name="idx_alcc_ten_date")` (17)
- **Methods & Badge Properties:**
  - `status_badge_class`, `lifecycle_stage_badge_class`, `recommendation_badge_class`
  - `recalculate_metrics()`:
    - `total_capex = acquisition_capital_cost + installation_commissioning_cost`
    - `total_maint = preventive_maintenance_cost + corrective_maintenance_cost + service_contract_cost`
    - `total_opex = total_maint + energy_utility_cost + downtime_opportunity_cost + insurance_compliance_cost`
    - `total_recoveries = expected_salvage_value + warranty_insurance_recoveries`
    - `total_lifecycle_cost = max(Decimal("0.00"), total_capex + total_opex - total_recoveries).quantize(Decimal("0.01"))`
    - `equivalent_annual_cost`: CRF formula `r*(1+r)^n / ((1+r)^n - 1)` when `discount_rate_pct > 0`, else `total_lifecycle_cost / horizon`.
    - `maintenance_to_rav_pct`: `(total_maint / current_replacement_value * 100)` if `current_replacement_value > 0` else `0.00` (capped at `Decimal("99999.99")`).
    - `opex_to_capex_ratio`: `(total_opex / total_capex)` if `total_capex > 0` else `0.00` (capped at `Decimal("99999.99")`).
    - `recommendation`: `dispose_retire` (`lifecycle_stage in ("end_of_life", "disposed")` and `maintenance_to_rav_pct >= 60`); `schedule_replacement` (`maintenance_to_rav_pct >= 50` or `opex_to_capex_ratio >= 1.50` or `lifecycle_stage == "end_of_life"`); `overhaul_refurbish` (`maintenance_to_rav_pct >= 25` or `lifecycle_stage == "late_life"`); else `retain_operate`.
    - `economic_eol_year`: `analysis_date.year + max(1, analysis_horizon_years)` (reduced proportionally if `recommendation in ("schedule_replacement", "dispose_retire")`).
  - `populate_from_asset_records()`: aggregates real tenant-scoped sums from `AssetCapitalization`, `AssetDepreciationSchedule`, `AssetMaintenanceLog`, `AssetServiceContract`, `AssetDowntimeLog`, `AssetEnergyReading`, `AssetInsurancePolicy`, `AssetWarrantyClaim`, `AssetInsuranceClaim`, `AssetComplianceIncident`, `AssetResaleListing`, `AssetScrapSalvage`, `FixedAsset`, and `scm.Asset`, calls `recalculate_metrics()`, sets `status = "calculated"` when `"draft"`, and saves.

---

### 1.2 `AssetReplacementPlan` (`apps/assets/models/AssetAnalytics/AssetReplacementPlans.py`)
- **Table:** `assets_assetreplacementplan`
- **Number Prefix:** `ARPL` (`ARPL-YYYYMM-XXXX`)
- **CHOICES:**
  - `QUARTER_CHOICES = [("q1", "Q1 (Jan-Mar)"), ("q2", "Q2 (Apr-Jun)"), ("q3", "Q3 (Jul-Sep)"), ("q4", "Q4 (Oct-Dec)")]` (`max_length=5`)
  - `STRATEGY_CHOICES = [("like_for_like", "Like-for-Like Replacement"), ("technology_upgrade", "Technology / Efficiency Upgrade"), ("capacity_expansion", "Capacity Expansion"), ("consolidate_retire", "Consolidate & Retire"), ("refurbish_extend", "Major Overhaul / Life Extension")]` (`max_length=25`)
  - `FUNDING_STATUS_CHOICES = [("unfunded", "Unfunded Backlog"), ("requested", "CapEx Requested"), ("budget_allocated", "Budget Allocated"), ("deferred", "Deferred")]` (`max_length=24`)
  - `STATUS_CHOICES = [("forecasted", "Forecasted"), ("proposed", "Proposed for CIP"), ("approved", "Approved"), ("scheduled", "Scheduled"), ("executed", "Executed"), ("deferred", "Deferred"), ("cancelled", "Cancelled")]` (`max_length=20`)
  - `PRIORITY_BAND_CHOICES = [("critical", "Critical Priority"), ("high", "High Priority"), ("medium", "Medium Priority"), ("low", "Low Priority")]` (`max_length=15`)
  - `STATUS_CSS = {"forecasted": "badge-slate", "proposed": "badge-info", "approved": "badge-green", "scheduled": "badge-info", "executed": "badge-green", "deferred": "badge-amber", "cancelled": "badge-muted"}`
  - `FUNDING_STATUS_CSS = {"unfunded": "badge-red", "requested": "badge-amber", "budget_allocated": "badge-green", "deferred": "badge-slate"}`
  - `PRIORITY_BAND_CSS = {"critical": "badge-red", "high": "badge-amber", "medium": "badge-info", "low": "badge-green"}`
- **Fields:**
  - Inherited from `TenantNumbered`: `tenant`, `number`, `created_at`, `updated_at`
  - `title`: `CharField(max_length=255)`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="asset_replacement_plans")`
  - `location`: `ForeignKey("scm.Location", on_delete=SET_NULL, null=True, blank=True, related_name="asset_replacement_plans")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="asset_replacement_plans")` *(GLOBAL)*
  - `condition_assessment`: `ForeignKey("assets.AssetConditionAssessment", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `lifecycle_analysis`: `ForeignKey("assets.AssetLifecycleCostAnalysis", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `capital_budget`: `ForeignKey("accounting.Budget", on_delete=SET_NULL, null=True, blank=True, related_name="asset_replacement_plans")`
  - `linked_requisition`: `ForeignKey("assets.AssetRequisition", on_delete=SET_NULL, null=True, blank=True, related_name="replacement_plans")`
  - `planner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="planned_asset_replacements")`
  - `predicted_eol_date`: `DateField(null=True, blank=True)`
  - `remaining_useful_life_months`: `PositiveIntegerField(default=12)`
  - `planned_replacement_year`: `PositiveIntegerField(default=2027)`
  - `planned_quarter`: `CharField(max_length=5, choices=QUARTER_CHOICES, default="q1")`
  - `replacement_strategy`: `CharField(max_length=25, choices=STRATEGY_CHOICES, default="like_for_like")`
  - `funding_status`: `CharField(max_length=24, choices=FUNDING_STATUS_CHOICES, default="unfunded")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="forecasted")`
  - `condition_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("50.00"))`
  - `criticality_weight`: `PositiveSmallIntegerField(default=5)` *(1..10)*
  - `failure_risk_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("50.00"))` *(0..100)*
  - `priority_score`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - `priority_band`: `CharField(max_length=15, choices=PRIORITY_BAND_CHOICES, default="medium")`
  - `current_replacement_value`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `deferred_maintenance_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `fci_ratio_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
  - `estimated_replacement_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `inflation_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("4.00"))`
  - `inflation_adjusted_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `estimated_salvage_recovery`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `deferral_penalty_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_arpl_ten_num_uniq")` (24)
  - `Index(fields=["tenant", "status"], name="idx_arpl_ten_stat")` (17)
  - `Index(fields=["tenant", "funding_status"], name="idx_arpl_ten_fund")` (17)
  - `Index(fields=["tenant", "priority_band"], name="idx_arpl_ten_prio")` (17)
  - `Index(fields=["tenant", "planned_replacement_year"], name="idx_arpl_ten_year")` (17)

---

### 1.3 `AssetPortfolioScenario` (`apps/assets/models/AssetAnalytics/AssetPortfolioScenarios.py`)
- **Table:** `assets_assetportfolioscenario`
- **Number Prefix:** `AWIF` (`AWIF-YYYYMM-XXXX`)
- **CHOICES:**
  - `SCENARIO_TYPE_CHOICES = [("baseline_bau", "Baseline (Business-As-Usual)"), ("fleet_expansion", "Fleet / Capacity Expansion"), ("site_consolidation", "Site / Fleet Consolidation"), ("accelerated_replacement", "Accelerated Replacement Program"), ("budget_constrained", "CapEx Budget Cap Constraint"), ("deferred_maintenance_impact", "Deferred Maintenance Impact"), ("sustainability_retrofit", "Efficiency & Electrification Retrofit")]` (`max_length=35`)
  - `STATUS_CHOICES = [("draft", "Draft"), ("simulated", "Simulated"), ("under_review", "Under Review"), ("recommended", "Recommended"), ("adopted", "Adopted"), ("archived", "Archived")]` (`max_length=20`)
  - `STATUS_CSS = {"draft": "badge-slate", "simulated": "badge-info", "under_review": "badge-amber", "recommended": "badge-green", "adopted": "badge-green", "archived": "badge-muted"}`
  - `SCENARIO_TYPE_CSS = {"baseline_bau": "badge-slate", "fleet_expansion": "badge-info", "site_consolidation": "badge-amber", "accelerated_replacement": "badge-green", "budget_constrained": "badge-red", "deferred_maintenance_impact": "badge-red", "sustainability_retrofit": "badge-green"}`
- **Fields:**
  - Inherited from `TenantNumbered`: `tenant`, `number`, `created_at`, `updated_at`
  - `name`: `CharField(max_length=255)`
  - `scenario_type`: `CharField(max_length=35, choices=SCENARIO_TYPE_CHOICES, default="baseline_bau")`
  - `is_baseline`: `BooleanField(default=False)`
  - `base_fiscal_year`: `PositiveIntegerField(default=2026)`
  - `horizon_years`: `PositiveSmallIntegerField(default=5)`
  - `scope_org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="asset_portfolio_scenarios")`
  - `scope_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="asset_portfolio_scenarios")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="asset_portfolio_scenarios")` *(GLOBAL)*
  - `baseline_scenario`: `ForeignKey("self", on_delete=SET_NULL, null=True, blank=True, related_name="derived_scenarios")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="owned_asset_scenarios")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - Scenario Levers:
    - `annual_capex_budget_limit`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
    - `discount_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("8.00"))`
    - `inflation_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("4.00"))`
    - `acceleration_months`: `IntegerField(default=0)`
    - `fleet_growth_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `consolidation_reduction_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `maintenance_efficiency_gain_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - Simulated Output Metrics (all server-computed by `run_simulation()`):
    - `baseline_capex_total`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_capex_total`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `capex_variance_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `baseline_opex_maintenance`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_opex_maintenance`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `opex_savings_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `baseline_deferred_backlog`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_deferred_backlog`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `baseline_avg_health_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_avg_health_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`
    - `baseline_fci_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_fci_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `baseline_risk_exposure`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `simulated_risk_exposure`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `net_present_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `payback_period_years`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `benefit_cost_ratio`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - `assumptions_summary`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_awif_ten_num_uniq")` (24)
  - `Index(fields=["tenant", "status"], name="idx_awif_ten_stat")` (17)
  - `Index(fields=["tenant", "scenario_type"], name="idx_awif_ten_type")` (17)
  - `Index(fields=["tenant", "base_fiscal_year"], name="idx_awif_ten_yr")` (15)

---

### 1.4 `AssetExecutiveScorecard` (`apps/assets/models/AssetAnalytics/AssetExecutiveScorecards.py`)
- **Table:** `assets_assetexecutivescorecard`
- **Number Prefix:** `AKPI` (`AKPI-YYYYMM-XXXX`)
- **CHOICES:**
  - `PERIOD_TYPE_CHOICES = [("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual"), ("ytd", "Year-to-Date"), ("adhoc", "Ad-Hoc Executive Brief")]` (`max_length=15`)
  - `RAG_STATUS_CHOICES = [("green", "On Target (Green)"), ("amber", "Watch / Variance (Amber)"), ("red", "Action Required (Red)")]` (`max_length=10`)
  - `STATUS_CHOICES = [("draft", "Draft"), ("published", "Published"), ("board_approved", "Board Approved"), ("archived", "Archived")]` (`max_length=20`)
  - `STATUS_CSS = {"draft": "badge-slate", "published": "badge-info", "board_approved": "badge-green", "archived": "badge-muted"}`
  - `RAG_STATUS_CSS = {"green": "badge-green", "amber": "badge-amber", "red": "badge-red"}`
- **Fields:**
  - Inherited from `TenantNumbered`: `tenant`, `number`, `created_at`, `updated_at`
  - `title`: `CharField(max_length=255)`
  - `period_type`: `CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="quarterly")`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="asset_executive_scorecards")`
  - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="asset_executive_scorecards")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="asset_executive_scorecards")` *(GLOBAL)*
  - `prepared_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="prepared_asset_scorecards")`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="approved_asset_scorecards")`
  - `rag_status`: `CharField(max_length=10, choices=RAG_STATUS_CHOICES, default="green")`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`
  - Valuation / ROI KPIs:
    - `total_asset_count`: `PositiveIntegerField(default=0)`
    - `gross_replacement_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `total_net_book_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `total_maintenance_spend`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
    - `annual_asset_return_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
    - `asset_roi_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `target_asset_roi_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("12.00"))`
  - Cost / Reliability KPIs:
    - `maintenance_cost_to_rav_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `target_mcr_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("3.50"))`
    - `planned_maintenance_ratio_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `portfolio_fci_pct`: `DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))`
    - `capex_budget_utilization_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `fleet_availability_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `portfolio_oee_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
  - Compliance / Risk KPIs:
    - `compliance_audit_pass_rate_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))`
    - `target_compliance_rate_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("95.00"))`
    - `open_compliance_incidents`: `PositiveIntegerField(default=0)`
    - `total_risk_exposure_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
    - `unfunded_replacement_backlog`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `executive_summary`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars):**
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_akpi_ten_num_uniq")` (24)
  - `Index(fields=["tenant", "status"], name="idx_akpi_ten_stat")` (17)
  - `Index(fields=["tenant", "period_type"], name="idx_akpi_ten_per")` (16)
  - `Index(fields=["tenant", "rag_status"], name="idx_akpi_ten_rag")` (16)
  - `Index(fields=["tenant", "period_end"], name="idx_akpi_ten_end")` (16)
- **Draft Lock Property/Method:**
  - `is_locked`: `self.status in ("published", "board_approved", "archived")`
  - `compute_from_live_portfolio()`: raises `ValidationError` if `self.is_locked`.

---

## 2. Forms Contract (`apps/assets/forms/AssetAnalytics/*.py`)

All forms inherit `(TenantUniqueMixin, TenantModelForm)`.  
**NEVER** filter `accounting.Currency` by `tenant` (use `Currency.objects.filter(is_active=True)`), and **NEVER** include `"currency"` in `reject_foreign(...)`.

1. **`AssetLifecycleCostAnalysisForm` (`AssetLifecycleCostAnalyses.py`)**:
   - `Meta.fields`: `["title", "fixed_asset", "operational_asset", "asset_category", "asset_model", "org_unit", "currency", "analyzed_by", "analysis_date", "analysis_horizon_years", "discount_rate_pct", "lifecycle_stage", "acquisition_capital_cost", "installation_commissioning_cost", "preventive_maintenance_cost", "corrective_maintenance_cost", "service_contract_cost", "energy_utility_cost", "downtime_opportunity_cost", "insurance_compliance_cost", "accumulated_depreciation_cost", "expected_salvage_value", "warranty_insurance_recoveries", "current_replacement_value", "notes"]`
   - Excludes: `tenant`, `number`, `status`, `created_at`, `updated_at`, `total_lifecycle_cost`, `equivalent_annual_cost`, `maintenance_to_rav_pct`, `opex_to_capex_ratio`, `economic_eol_year`, `recommendation`
   - Tenant FK filtering + `reject_foreign`: `fixed_asset`, `operational_asset`, `asset_category`, `asset_model`, `org_unit`, `analyzed_by`
   - `clean()` validations: `1 <= analysis_horizon_years <= 50`, `0 <= discount_rate_pct <= 100`, all monetary buckets `>= 0`.

2. **`AssetReplacementPlanForm` (`AssetReplacementPlans.py`)**:
   - `Meta.fields`: `["title", "fixed_asset", "operational_asset", "asset_category", "asset_model", "org_unit", "location", "currency", "condition_assessment", "lifecycle_analysis", "capital_budget", "linked_requisition", "planner", "predicted_eol_date", "remaining_useful_life_months", "planned_replacement_year", "planned_quarter", "replacement_strategy", "funding_status", "condition_score", "criticality_weight", "failure_risk_score", "current_replacement_value", "deferred_maintenance_cost", "estimated_replacement_cost", "inflation_rate_pct", "estimated_salvage_recovery", "deferral_penalty_cost", "notes"]`
   - Excludes: `tenant`, `number`, `status`, `created_at`, `updated_at`, `priority_score`, `priority_band`, `fci_ratio_pct`, `inflation_adjusted_cost`
   - Tenant FK filtering + `reject_foreign`: `fixed_asset`, `operational_asset`, `asset_category`, `asset_model`, `org_unit`, `location`, `condition_assessment`, `lifecycle_analysis`, `capital_budget`, `linked_requisition`, `planner`
   - `clean()` validations: `1 <= criticality_weight <= 10`, `0 <= condition_score <= 100`, `0 <= failure_risk_score <= 100`, `0 <= inflation_rate_pct <= 50`, `2000 <= planned_replacement_year <= 2100`, monetary amounts `>= 0`.

3. **`AssetPortfolioScenarioForm` (`AssetPortfolioScenarios.py`)**:
   - `Meta.fields`: `["name", "scenario_type", "is_baseline", "base_fiscal_year", "horizon_years", "scope_org_unit", "scope_category", "currency", "baseline_scenario", "owner", "annual_capex_budget_limit", "discount_rate_pct", "inflation_rate_pct", "acceleration_months", "fleet_growth_pct", "consolidation_reduction_pct", "maintenance_efficiency_gain_pct", "assumptions_summary"]`
   - Excludes: `tenant`, `number`, `status`, `created_at`, `updated_at`, and ALL 17 computed baseline/simulated metrics (`baseline_*`, `simulated_*`, `capex_variance_amount`, `opex_savings_amount`, `net_present_value`, `payback_period_years`, `benefit_cost_ratio`)
   - Tenant FK filtering + `reject_foreign`: `scope_org_unit`, `scope_category`, `baseline_scenario`, `owner`
   - `clean()` validations: `baseline_scenario != instance`, `1 <= horizon_years <= 30`, `2000 <= base_fiscal_year <= 2100`, `annual_capex_budget_limit >= 0`, `0 <= discount_rate_pct <= 100`, `0 <= inflation_rate_pct <= 50`, `-60 <= acceleration_months <= 120`, `-95 <= fleet_growth_pct <= 500`, `0 <= consolidation_reduction_pct <= 100`, `0 <= maintenance_efficiency_gain_pct <= 100`.

4. **`AssetExecutiveScorecardForm` (`AssetExecutiveScorecards.py`)**:
   - `Meta.fields`: `["title", "period_type", "period_start", "period_end", "org_unit", "asset_category", "currency", "prepared_by", "target_asset_roi_pct", "target_mcr_pct", "target_compliance_rate_pct", "annual_asset_return_amount", "executive_summary"]`
   - Excludes: `tenant`, `number`, `created_at`, `updated_at`, `status`, `approved_by`, `rag_status`, and all live-computed KPI snapshots (`total_asset_count`, `gross_replacement_value`, `total_net_book_value`, `total_maintenance_spend`, `asset_roi_pct`, `maintenance_cost_to_rav_pct`, `planned_maintenance_ratio_pct`, `portfolio_fci_pct`, `capex_budget_utilization_pct`, `fleet_availability_pct`, `portfolio_oee_pct`, `compliance_audit_pass_rate_pct`, `open_compliance_incidents`, `total_risk_exposure_amount`, `unfunded_replacement_backlog`)
   - Tenant FK filtering + `reject_foreign`: `org_unit`, `asset_category`, `prepared_by`
   - `clean()` validations: `period_end >= period_start`, `0 <= target_compliance_rate_pct <= 100`, `0 <= target_mcr_pct <= 100`.

---

## 3. Views, Context Keys & URLconf Contract

- **Shared List & Export Policy:** All 4 `11.14` list views paginate at `PAGE_SIZE = 15` (`_helpers.PAGE_SIZE`), and all CSV exports stream up to 10,000 rows via `qs[:10000].iterator(chunk_size=500)` with `csv_safe` formula-injection neutralization.

### 3.1 `AssetLifecycleCostAnalysis` Views & Routes (`AssetLifecycleCostAnalyses.py`)
- `asset_lifecycle_cost_analysis_list` (`analytics/lifecycle-cost/`):
  - Filters (`GET`): `q`, `status`, `lifecycle_stage`, `recommendation`, `asset_category`, `org_unit`
  - Context keys: `analyses`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `stage_choices`, `recommendation_choices`, `categories`, `org_units`, `total_analyses`, `avg_tco`, `replace_candidates_count`, `total_tco_value`
- `asset_lifecycle_cost_analysis_create` (`analytics/lifecycle-cost/new/`): context `form`, `analysis=None`, `is_edit=False`
- `asset_lifecycle_cost_analysis_detail` (`analytics/lifecycle-cost/<int:pk>/`): context `analysis`, `total_capex`, `total_maint`, `total_opex`, `total_recoveries`
- `asset_lifecycle_cost_analysis_edit` (`analytics/lifecycle-cost/<int:pk>/edit/`): enforces lock (`approved`/`archived` -> error flash + redirect to detail); context `form`, `analysis`, `is_edit=True`
- `asset_lifecycle_cost_analysis_delete` (`analytics/lifecycle-cost/<int:pk>/delete/`): POST-only; enforces lock (`approved`/`archived` -> error flash + redirect to detail)
- `asset_lifecycle_cost_analysis_populate` (`analytics/lifecycle-cost/<int:pk>/populate/`): POST-only; enforces lock (`approved`/`archived`), calls `populate_from_asset_records()`, audit action `"populate"`
- `asset_lifecycle_cost_analysis_transition` (`analytics/lifecycle-cost/<int:pk>/status/`): POST-only; enforces `ALLOWED_TRANSITIONS` (`draft -> calculated/reviewed/archived`, `calculated -> reviewed/approved/archived`, `reviewed -> approved/archived`, `approved -> archived`, `archived -> {}`), audit action `"update"`
- `asset_lifecycle_cost_analysis_export_csv` (`analytics/lifecycle-cost/export-csv/`): CSV attachment (`alcc-analyses.csv`)

### 3.2 `AssetReplacementPlan` Views & Routes (`AssetReplacementPlans.py`)
- `asset_replacement_plan_list` (`analytics/replacement-plans/`):
  - Filters (`GET`): `q`, `status`, `funding_status`, `priority_band`, `replacement_strategy`, `planned_replacement_year`, `org_unit`, `asset_category`, `location`
  - Context keys: `plans`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `funding_choices`, `priority_choices`, `strategy_choices`, `years`, `org_units`, `categories`, `locations`, `total_plans`, `critical_plans_count`, `unfunded_plans_value`, `total_capex_forecast`
- `asset_replacement_plan_create` (`analytics/replacement-plans/new/`): context `form`, `plan=None`, `is_edit=False`
- `asset_replacement_plan_detail` (`analytics/replacement-plans/<int:pk>/`): context `plan`
- `asset_replacement_plan_edit` (`analytics/replacement-plans/<int:pk>/edit/`): enforces lock (`approved`/`scheduled`/`executed`/`cancelled` -> error flash + redirect to detail); context `form`, `plan`, `is_edit=True`
- `asset_replacement_plan_delete` (`analytics/replacement-plans/<int:pk>/delete/`): POST-only; enforces lock (`approved`/`scheduled`/`executed`/`cancelled` -> error flash + redirect to detail)
- `asset_replacement_plan_recalculate` (`analytics/replacement-plans/<int:pk>/recalculate/`): POST-only; enforces lock, audit action `"compute"`
- `asset_replacement_plan_transition` (`analytics/replacement-plans/<int:pk>/status/`): POST-only; enforces `ALLOWED_TRANSITIONS` (`forecasted -> proposed/approved/deferred/cancelled`, `proposed -> approved/deferred/cancelled`, `approved -> scheduled/deferred/cancelled`, `scheduled -> executed/deferred/cancelled`, `deferred -> proposed/cancelled`, terminal `executed`/`cancelled`), audit action `"update"`
- `asset_replacement_plan_export_csv` (`analytics/replacement-plans/export-csv/`): CSV attachment (`arpl-replacement-plans.csv`)

### 3.3 `AssetPortfolioScenario` Views & Routes (`AssetPortfolioScenarios.py`)
- `asset_portfolio_scenario_list` (`analytics/scenarios/`):
  - Filters (`GET`): `q`, `status`, `scenario_type`, `base_fiscal_year`, `scope_org_unit`, `scope_category`
  - Context keys: `scenarios`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `type_choices`, `years`, `org_units`, `categories`, `total_scenarios`, `simulated_count`, `adopted_count`, `best_npv`
- `asset_portfolio_scenario_create` (`analytics/scenarios/new/`): context `form`, `scenario=None`, `is_edit=False`
- `asset_portfolio_scenario_detail` (`analytics/scenarios/<int:pk>/`): context `scenario`
- `asset_portfolio_scenario_edit` (`analytics/scenarios/<int:pk>/edit/`): enforces lock (`adopted`/`archived` -> error flash + redirect to detail); context `form`, `scenario`, `is_edit=True`
- `asset_portfolio_scenario_delete` (`analytics/scenarios/<int:pk>/delete/`): POST-only; enforces lock (`adopted`/`archived` -> error flash + redirect to detail)
- `asset_portfolio_scenario_simulate` (`analytics/scenarios/<int:pk>/simulate/`): POST-only; enforces lock (`adopted`/`archived`), calls `run_simulation()`, audit action `"simulate"`
- `asset_portfolio_scenario_transition` (`analytics/scenarios/<int:pk>/status/`): POST-only; enforces `ALLOWED_TRANSITIONS` (`draft -> simulated/under_review/archived`, `simulated -> under_review/recommended/archived`, `under_review -> recommended/archived`, `recommended -> adopted/archived`, `adopted -> archived`, `archived -> {}`), audit action `"update"`
- `asset_portfolio_scenario_export_csv` (`analytics/scenarios/export-csv/`): CSV attachment (`awif-scenarios.csv`)

### 3.4 `AssetExecutiveScorecard` Views & Routes (`AssetExecutiveScorecards.py`)
- `asset_executive_scorecard_list` (`analytics/scorecards/`):
  - Filters (`GET`): `q`, `status`, `period_type`, `rag_status`, `org_unit`, `asset_category`
  - Context keys: `scorecards`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `period_choices`, `rag_choices`, `org_units`, `categories`, `total_scorecards`, `green_count`, `board_approved_count`, `avg_roi_pct`
- `asset_executive_scorecard_create` (`analytics/scorecards/new/`): context `form`, `scorecard=None`, `is_edit=False`
- `asset_executive_scorecard_detail` (`analytics/scorecards/<int:pk>/`): context `scorecard`
- `asset_executive_scorecard_edit` (`analytics/scorecards/<int:pk>/edit/`): enforces draft-lock (`if scorecard.is_locked`: error flash + redirect to detail); context `form`, `scorecard`, `is_edit=True`
- `asset_executive_scorecard_delete` (`analytics/scorecards/<int:pk>/delete/`): POST-only; enforces draft-lock (`if scorecard.is_locked`: error flash + redirect to detail)
- `asset_executive_scorecard_compute` (`analytics/scorecards/<int:pk>/compute/`): POST-only, enforces draft-lock (`if scorecard.is_locked`: error flash + redirect), calls `compute_from_live_portfolio()`, audit action `"compute"`
- `asset_executive_scorecard_publish` (`analytics/scorecards/<int:pk>/publish/`): POST-only (`draft -> published`), audit action `"publish"`
- `asset_executive_scorecard_approve` (`analytics/scorecards/<int:pk>/approve/`): POST-only `@tenant_admin_required` (`published -> board_approved`, blocks `prepared_by_id == request.user.pk` for SoD, sets `approved_by=request.user`), audit action `"approve"`
- `asset_executive_scorecard_archive` (`analytics/scorecards/<int:pk>/archive/`): POST-only, audit action `"archive"`
- `asset_executive_scorecard_export_csv` (`analytics/scorecards/export-csv/`): CSV attachment (`akpi-scorecards.csv`)

### 3.5 Computed `PortfolioDashboards` Views & Routes (`PortfolioDashboards.py` — NO extra model)
- `portfolio_dashboard` (`analytics/dashboard/`):
  - Filters (`GET`): `org_unit`, `asset_category`, `location`, `fiscal_year`
  - Context keys: `org_units`, `categories`, `locations`, `fiscal_years`, `selected_fiscal_year`, `kpis`, `health_matrix`, `bad_actors`, `capex_forecast_years`, `risk_posture_rows`, `compliance_summary`, `recent_scorecards`
- `portfolio_dashboard_export_csv` (`analytics/dashboard/export-csv/`): CSV attachment (`portfolio-analytics.csv`)
- `scenario_compare` (`analytics/scenarios/compare/`):
  - Multi-select filter (`GET` list `scenarios`): returns selected tenant scenarios (if non-empty valid ints submitted and 0 tenant matches -> `Http404`), else top 4 latest tenant scenarios.
  - Context keys: `all_scenarios`, `compared_scenarios`, `selected_ids`, `baseline_scenario`

---

## 4. Templates Contract

All templates extend `"base.html"`, use valid `theme.css` classes, `|stringformat:"d"` for FK `<option selected>`, color-named badges (`badge-*` only from `theme.css`), pagination preserving query params, and CSRF tokens on all POST forms:
1. `templates/assets/assetanalytics/asset_lifecycle_cost_analysis/{list,detail,form}.html`
2. `templates/assets/assetanalytics/asset_replacement_plan/{list,detail,form}.html`
3. `templates/assets/assetanalytics/asset_portfolio_scenario/{list,detail,form}.html`
4. `templates/assets/assetanalytics/asset_executive_scorecard/{list,detail,form}.html`
5. `templates/assets/assetanalytics/portfolio_dashboard/{dashboard,scenario_compare}.html`

---

## 5. Navigation Wiring Contract (`LIVE_LINKS["11.14"]`)

In `apps/core/navigation.py`:
```python
    "11.14": {
        "Asset Lifecycle Cost Analysis (LCC)": "assets:asset_lifecycle_cost_analysis_list",
        "Replacement Planning & Forecasting": "assets:asset_replacement_plan_list",
        "Portfolio Performance Dashboards": "assets:portfolio_dashboard",
        "What-if Scenario Modeling": "assets:asset_portfolio_scenario_list",
        "Executive Reporting & KPIs": "assets:asset_executive_scorecard_list",
        # Convenience aliases
        "Lifecycle Cost Analysis": "assets:asset_lifecycle_cost_analysis_list",
        "LCC Analysis": "assets:asset_lifecycle_cost_analysis_list",
        "Replacement Plans": "assets:asset_replacement_plan_list",
        "Portfolio Dashboard": "assets:portfolio_dashboard",
        "Scenario Modeling": "assets:asset_portfolio_scenario_list",
        "Scenario Comparison": "assets:scenario_compare",
        "Executive Scorecards": "assets:asset_executive_scorecard_list",
        "Asset Analytics & BI": "assets:portfolio_dashboard",
    },
```

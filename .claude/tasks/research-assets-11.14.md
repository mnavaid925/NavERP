# Research — 11.14 Asset Analytics & Business Intelligence

**Module**: 11 — Asset Management System (`apps/assets`)  
**Sub-module**: `11.14 Asset Analytics & Business Intelligence`  
**`NavERP.md` reference**: Lines 1820–1825  
**Scope**: Competitive domain research + deduplicated feature catalog + recommended 4-model + computed dashboard build scope (build-plan hand-off for Phase 2 `todo`).

---

## 1. Repo State Checked First

### Existing `apps/assets` Footprint (`11.1`–`11.13`, 52 models)
Inspected `apps/assets/models/__init__.py`, `apps/assets/views/overview.py`, `apps/core/navigation.py` (`LIVE_LINKS["11.1"]`–`"11.13"`), and `.claude/skills/assets/SKILL.md`:

| Sub-module | Package | Existing Models (`NUMBER_PREFIX`) |
|---|---|---|
| `11.1` Acquisition & Onboarding | `AssetProcurement` | `AssetRequisition` (`AREQ`), `AssetReceipt` (`ARCV`), `AssetCapitalization` (`ACAP`), `AssetTag` (`ATAG`) |
| `11.2` Tracking & Inventory | `AssetTracking` | `AssetAudit` (`AAUD`), `AssetMovement` (`AMOV`), `AssetCheckOut` (`ACHK`), `AssetIncidentReport` (`AINC`) |
| `11.3` Classification & Taxonomy | `AssetClassification` | `AssetCategory` (`ACAT`), `AssetModel` (`AMOD`), `AssetCriticalityAssessment` (`ACRT`), `AssetSpecification` (`ASPC`) |
| `11.4` Depreciation & Valuation | `AssetDepreciation` | `AssetDepreciationSchedule` (`ADEP`), `AssetRevaluation` (`AREV`), `AssetTransfer` (`AXFR`), `CapitalizationThreshold` (`ACTH`) |
| `11.5` Maintenance Management | `AssetMaintenance` | `AssetMaintenanceRequest` (`AMRQ`), `AssetMaintenanceSchedule` (`AMSC`), `AssetServiceContract` (`ASVC`), `AssetMaintenanceLog` (`AMLG`) |
| `11.6` Performance & Utilization | `AssetPerformance` | `AssetDowntimeLog` (`ADWN`), `AssetOeeRecord` (`AOEE`), `AssetEnergyReading` (`AENG`), `AssetPerformanceScorecard` (`APSC`) |
| `11.7` Condition & Reliability | `AssetReliability` | `AssetConditionAssessment` (`ACAS`), `AssetTelemetryLog` (`ATEL`), `AssetFmeaAnalysis` (`AFMA`), `AssetCalibrationLog` (`ACAL`) |
| `11.8` Warranty & Insurance | `AssetWarrantyInsurance` | `AssetWarranty` (`AWAR`), `AssetWarrantyClaim` (`AWCL`), `AssetInsurancePolicy` (`AINS`), `AssetInsuranceClaim` (`AICL`) |
| `11.9` Disposal & Retirement | `AssetDisposal` | `AssetDisposalRequest` (`ADSP`), `AssetResale` (`ARSL`), `AssetTradeIn` (`ATRD`), `AssetScrap` (`ASCR`) |
| `11.10` Lease & Rental | `AssetLeaseRental` | `AssetLeaseContract` (`ALC`), `AssetLeasePayment` (`ALSP`), `AssetLeaseModification` (`ALMD`), `AssetLeaseBuyAnalysis` (`ALBA`) |
| `11.11` Compliance & Regulatory | `AssetCompliance` | `AssetComplianceFramework` (`ACF`), `AssetComplianceAudit` (`ACA`), `AssetCompliancePolicy` (`APL`), `AssetComplianceIncident` (`ACI`) |
| `11.12` Risk Management | `AssetRisk` | `AssetRiskRegister` (`ARK`), `AssetBusinessContinuityPlan` (`ABC`), `AssetCybersecurityBaseline` (`ACS`), `AssetRiskMitigationAction` (`ARMA`) |
| `11.13` Mobile & Field | `AssetMobileField` | `MobileInspection` (`MINS`), `MobileFieldWorkOrder` (`MFWO`), `AssetScanLog` (`ASCN`), `AssetGeofenceZone` (`AGEO`) |

- `LIVE_LINKS` has `"11.1"` through `"11.13"` wired; `"11.14"` is not yet registered.
- Existing `/assets/` hub (`apps/assets/views/overview.py`) only aggregates `11.1` & `11.2` counts; there is no portfolio-wide lifecycle cost, replacement forecast, what-if simulator, or executive KPI cockpit.
- Zero FKs currently exist between `apps/assets` and `apps/bi`.

### Base Class & Sibling Analytics Conventions Verified
- `apps/assets/models/_base.py`: `TenantOwned` defines `tenant` (`core.Tenant`, `related_name="+"`, `db_index=True`), `created_at`, `updated_at`. `TenantNumbered(TenantOwned)` adds `number = CharField(max_length=32, editable=False)` and atomic `next_number(...)` minting using `NUMBER_PREFIX`. Subclasses inheriting `TenantNumbered` do **not** need to redeclare `tenant`.
- Sibling module analytics patterns verified:
  - `apps/scm/models/SupplyChainAnalytics/KpiSnapshots.py`: Persisted KPI period snapshots avoid historical recalculation drift when thresholds or formulas change.
  - `apps/procurement/models/SpendAnalyticsReporting/SpendDashboards.py` & `apps/projects/models/ReportingBusinessIntelligence/ProjectDashboards.py`: Computed read-only dashboard views aggregate live operational/financial tables without inventing redundant persistent dashboard models.
- `apps/bi/` boundary checked (`BiDashboards.py` `BDSH`, `WhatIfScenarios.py` `BWIF`, `PerformanceScorecards.py`, `KpiDefinitions.py`, `ForecastExecutions.py`, `OptimizationScenarios.py`): `apps/bi` is generic enterprise BI (semantic cubes, cross-ERP dashboards). Keeping `11.14` self-contained in `apps/assets` using EAM-native formulas (TCO/LCC, EAC, FCI, MCR % RAV, repair-vs-replace crossover) avoids cross-app coupling while permitting optional BI connector export later (`11.15`).

### Verified Spine & Cross-Module Entities Available for Reuse
| Spine / Sibling Class | Verified Location / Key Fields Observed | How `11.14` Reuses It |
|---|---|---|
| `accounting.FixedAsset` | `apps/accounting/models/FixedAssets/FixedAssetsRegister.py` (`acquisition_cost`, `salvage_value`, `useful_life_months`, `method`, `in_service_date`, `accumulated_depreciation`, `status`, `location`, `custodian`) | Financial basis, NBV, remaining depreciable life |
| `accounting.Budget` | `apps/accounting/models/Budgeting/Budgets.py` (`name`, `fiscal_period`, `version`, `status`, `total()`) | Optional CapEx budget linkage on replacement plans |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py` | Multi-currency normalization on LCC, plans, KPIs |
| `scm.Asset` | `apps/scm/models/AssetManagement/Assets.py` (`code`, `name`, `asset_type`, `status`, `criticality`, `category`, `location`, `org_unit`, `purchase_date`, `commissioned_on`, `purchase_cost`, `fixed_asset`) | Operational asset scope, criticality, commissioning age |
| `scm.Location` | `apps/scm/models/InventoryManagement/Locations.py` | Site/facility rollup for FCI & heat maps |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py` | Department / business unit portfolio segmentation |
| `assets.AssetCategory`, `assets.AssetModel` | `11.3` (`estimated_replacement_cost`, `expected_useful_life_months`) | Benchmark replacement cost & expected service life |
| `assets.AssetConditionAssessment` | `11.7` (`ACAS`, condition grade / health score) | Condition input to EOL prediction & health heat map |
| `assets.AssetPerformanceScorecard` | `11.6` (`APSC`, `availability_rate`, `average_oee_percentage`, `total_downtime_cost`, `total_energy_consumption_kwh`, `total_carbon_emissions_kg`, `performance_index_score`) | Per-asset telemetry rolled up into executive scorecards & LCC |
| `assets.AssetRiskRegister` | `11.12` (`ARK`, `inherent_risk_score/level`, `residual_risk_score/level`, `financial_exposure_amount`) | Risk exposure views & what-if risk delta |
| `assets.AssetCapitalization`, `AssetDepreciationSchedule`, `AssetMaintenanceLog`, `AssetServiceContract`, `AssetDowntimeLog`, `AssetEnergyReading`, `AssetInsurancePolicy`, `AssetWarrantyClaim`, `AssetInsuranceClaim`, `AssetDisposalRequest`, `AssetResale`, `AssetScrap` | `11.1`, `11.4`, `11.5`, `11.6`, `11.8`, `11.9` | Live source records aggregated into `11.14` LCC spend breakdowns |
| `assets.AssetRequisition` | `11.1` (`AREQ`, `estimated_cost`, `target_org_unit`) | Optional downstream requisition link when an approved replacement plan triggers acquisition |
| `assets.AssetComplianceAudit`, `AssetComplianceIncident` | `11.11` (`ACA`, `ACI`) | Compliance pass rate & penalty/incident feed into executive scorecards |

### Repo-Wide `NUMBER_PREFIX` Collision Check
All 52 existing `apps/assets` prefixes (`AREQ`, `ARCV`, `ACAP`, `ATAG`, `AAUD`, `AMOV`, `ACHK`, `AINC`, `ACAT`, `AMOD`, `ACRT`, `ASPC`, `ADEP`, `AREV`, `AXFR`, `ACTH`, `AMRQ`, `AMSC`, `ASVC`, `AMLG`, `ADWN`, `AOEE`, `AENG`, `APSC`, `ACAS`, `ATEL`, `AFMA`, `ACAL`, `AWAR`, `AWCL`, `AINS`, `AICL`, `ADSP`, `ARSL`, `ATRD`, `ASCR`, `ALC`, `ALSP`, `ALMD`, `ALBA`, `ACF`, `ACA`, `APL`, `ACI`, `ARK`, `ABC`, `ACS`, `ARMA`, `MINS`, `MFWO`, `ASCN`, `AGEO`) and repo-wide prefixes in `apps/` were searched via `Select-String`.  
Note: `ASCN` is already taken by `11.13 AssetScanLog`.  
Candidate prefixes **`ALCC`**, **`ARPL`**, **`AWIF`**, and **`AKPI`** returned **0 matches** across all files in `apps/`.

---

## 2. Leaders Surveyed (2025/2026 Commercial Platforms)

1. **IBM Maximo Application Suite (MAS Health, Predict, Asset Investment Planning)** — [ibm.com/products/maximo](https://www.ibm.com/products/maximo)  
   Unified asset health scoring (combining condition, age, maintenance cost, and work history), end-of-life probability curves, Repair-vs-Replace scoring, and multi-year capital investment optimization under budget and risk constraints.
2. **SAP Asset Performance Management (APM) + SAP Analytics Cloud (SAC)** — [sap.com](https://www.sap.com)  
   Closed-loop operational-to-financial planning: APM computes dynamic asset health and criticality scores, while SAC provides CapEx/OpEx alignment, TCO tracking, and multi-year Compass/What-If replacement backlog simulations.
3. **Brightly Predictor / AssetPlanner (Siemens)** — [brightlysoftware.com](https://www.brightlysoftware.com) / [siemens.com](https://www.siemens.com)  
   Purpose-built strategic capital planning for infrastructure and facility portfolios: degradation curve modeling, Facility Condition Index (FCI) forecasting, deferred maintenance backlog tracking, and funding-scenario comparison ("what happens under 3 budget levels?").
4. **Copperleaf (an IFS company — Asset Investment Planning & Management / AIPM)** — [copperleaf.com](https://www.copperleaf.com)  
   Industry benchmark for Value-Based Asset Investment Planning: multi-criteria value frameworks converting reliability, safety, compliance, and ESG risk into comparable monetary value, optimizing capital portfolios across multi-year horizons and scenario trade-offs.
5. **HxGN EAM (Hexagon Asset Lifecycle Intelligence + EcoSys)** — [hexagon.com/products/enterprise-asset-management](https://www.hexagon.com/products/enterprise-asset-management)  
   Asset Performance Management (APM) health & criticality matrices, cradle-to-grave lifecycle spend tracking, capital project/replacement planning integration, and executive KPI scorecards across multi-site fleets.
6. **Gordian VFA Capital Planning & Facility Condition Assessment** — [gordian.com/products/vfa-facility-condition-assessments-capital-planning-software](https://www.gordian.com/products/vfa-facility-condition-assessments-capital-planning-software)  
   Capital planning driven by condition assessments, Current Replacement Value (CRV), FCI benchmarks, renewal schedules, inflation-escalated replacement cost forecasts, and funding-gap scenarios.
7. **PowerPlan (Asset Investment Optimization & Lifecycle Management)** — [powerplan.com](https://powerplan.com)  
   Financial-grade asset analytics combining tax/book depreciation, O&M maintenance actuals, TCO/NPV/Equivalent Annual Cost (EAC), retirement forecasting, and CapEx vs. OpEx impact modeling for asset-intensive enterprises.
8. **ServiceNow Enterprise Asset Management (EAM Workspace)** — [servicenow.com/products/enterprise-asset-management.html](https://www.servicenow.com/products/enterprise-asset-management.html)  
   End-to-end hardware & enterprise asset lifecycle TCO dashboarding, model end-of-life/end-of-support tracking, planned refresh/disposal scheduling, and executive asset ROI / utilization / compliance visibility.
9. **IFS Ultimo EAM (Power BI EAM Analytics)** — [ultimo.com](https://www.ultimo.com)  
   Turnkey executive EAM KPI packs featuring Maintenance Cost as % of Replacement Asset Value (MCR/CRV), Planned vs. Reactive Maintenance ratio, Asset Availability & OEE rollups, Bad-Actor cost rankings, and budget variance dashboards.

---

## 3. Deduplicated, Prioritized Feature Catalog

Organized by the 5 `NavERP.md` bullets for `11.14`, plus **Beyond the bullets**.

### 3.1 Asset Lifecycle Cost Analysis (LCC)
*`NavERP.md`: Total cost of ownership, acquisition-to-disposal spend tracking.*

| Feature | Priority | Spine / Existing Model Mapping | Horizon |
|---|---|---|---|
| **Cradle-to-Grave TCO Cost Breakdown** (acquisition/capitalization, installation/freight, preventive & corrective maintenance, service contracts, energy/utility, downtime cost, insurance/compliance, depreciation, minus salvage/warranty/insurance recoveries) | `table-stakes` | `reuses` `AssetCapitalization`, `AssetDepreciationSchedule`, `AssetMaintenanceLog`, `AssetServiceContract`, `AssetDowntimeLog`, `AssetEnergyReading`, `AssetInsurancePolicy`, `AssetWarrantyClaim`, `AssetInsuranceClaim`, `AssetDisposalRequest`, `AssetResale`, `AssetScrap` + **new table (`AssetLifecycleCostAnalysis`)** | `buildable-now` |
| **Auto-Aggregation from Live Ledger/Asset Sub-modules** (one-click roll-up of recorded spend for the selected asset/category/org unit into LCC buckets while allowing overrides/projections) | `common` | `reuses` `accounting.FixedAsset`, `scm.Asset`, `11.1`–`11.9` tables + **`AssetLifecycleCostAnalysis`** | `buildable-now` |
| **Maintenance Cost % of Replacement Asset Value (MCR / CRV Ratio)** & **Cumulative OpEx vs. CapEx Ratio** | `table-stakes` | `reuses` `AssetModel.estimated_replacement_cost` + **`AssetLifecycleCostAnalysis`** | `buildable-now` |
| **Equivalent Annual Cost (EAC) & Discounted NPV Lifecycle Cost** (normalizes assets of unequal lifespans using discount rate & horizon years) | `common` | `new table` (`AssetLifecycleCostAnalysis`) | `buildable-now` |
| **Economic End-of-Life & Repair-vs-Replace Tipping Point Recommendation** (`retain_operate` / `overhaul_refurbish` / `schedule_replacement` / `dispose_retire`) | `differentiator` | `new table` (`AssetLifecycleCostAnalysis`) | `buildable-now` |
| **Category / Fleet Cohort LCC Benchmarking** (analyze a single asset or an entire category/model/org-unit cohort) | `common` | `reuses` `assets.AssetCategory`, `assets.AssetModel`, `core.OrgUnit` + **`AssetLifecycleCostAnalysis`** | `buildable-now` |

### 3.2 Replacement Planning & Forecasting
*`NavERP.md`: End-of-life prediction, capital budget forecasting, and replacement scheduling.*

| Feature | Priority | Spine / Existing Model Mapping | Horizon |
|---|---|---|---|
| **End-of-Life (EOL) Prediction & Remaining Useful Life Tracking** (combines `FixedAsset` / `AssetModel` useful life, age since commissioning, and latest `AssetConditionAssessment` health score) | `table-stakes` | `reuses` `accounting.FixedAsset`, `scm.Asset`, `assets.AssetModel`, `assets.AssetConditionAssessment` + **new table (`AssetReplacementPlan`)** | `buildable-now` |
| **Facility / Asset Condition Index (FCI = Deferred Maintenance Backlog / Current Replacement Value)** & Backlog Tracking | `table-stakes` | `new table` (`AssetReplacementPlan`) | `buildable-now` |
| **Risk- & Criticality-Weighted Replacement Priority Scoring (0–100 + Priority Band)** | `common` | `reuses` `scm.Asset.criticality`, `assets.AssetRiskRegister` + **`AssetReplacementPlan`** | `buildable-now` |
| **Multi-Year Capital Budget Forecasting with Inflation Escalation** (projects current replacement cost forward to target fiscal year & quarter) | `table-stakes` | `reuses` `accounting.Budget` (optional FK) + **`AssetReplacementPlan`** | `buildable-now` |
| **Replacement Strategy & Lifecycle Backing Link** (`like_for_like`, `technology_upgrade`, `capacity_expansion`, `consolidate_retire`, `refurbish_extend`, linked to `AssetLifecycleCostAnalysis`) | `common` | `new table` (`AssetReplacementPlan` -> `AssetLifecycleCostAnalysis`) | `buildable-now` |
| **Optional Handoff Link to Procurement Requisition** (connects approved replacement plan to `11.1 AssetRequisition` without duplicating requisition workflows) | `common` | `reuses` `assets.AssetRequisition` (`AREQ`) | `buildable-now` |
| **ML-Based Failure Curve / IoT Sensor Anomaly EOL Forecasting** | `differentiator` | Deferred to **`11.17 AI & Predictive Maintenance`** (`AssetTelemetryLog` streaming pipelines) | `integration/later` |

### 3.3 Portfolio Performance Dashboards
*`NavERP.md`: Asset health heat maps, investment return, and risk exposure views.*

| Feature | Priority | Spine / Existing Model Mapping | Horizon |
|---|---|---|---|
| **Computed Portfolio Performance Dashboard (Executive Cockpit)** — live cross-module views aggregating `11.1`–`11.13` + `accounting.FixedAsset` + `11.14` plans/scenarios (no duplicate persistent dashboard model) | `table-stakes` | `reuses` `accounting.FixedAsset`, `scm.Asset`, `11.6`, `11.7`, `11.11`, `11.12` + computed views | `buildable-now` |
| **Asset Health Heat Map Matrix** (Condition/Health tier vs. Criticality tier matrix + site/category health distribution) | `table-stakes` | `reuses` `assets.AssetConditionAssessment`, `assets.AssetPerformanceScorecard`, `scm.Asset`, `core.OrgUnit`, `scm.Location` (computed view) | `buildable-now` |
| **Portfolio Investment Return & TCO Distribution Views** (Gross Cost vs. Net Book Value, Bad-Actor Top-10 Costly Assets, Maintenance % RAV by category/org unit) | `table-stakes` | `reuses` `accounting.FixedAsset` + `AssetLifecycleCostAnalysis` + `AssetExecutiveScorecard` (computed view) | `buildable-now` |
| **Portfolio Risk Exposure & Compliance Posture Views** (financial risk exposure by risk level from `AssetRiskRegister`, open compliance incidents/audit score from `11.11`, unfunded replacement backlog exposure) | `common` | `reuses` `assets.AssetRiskRegister`, `assets.AssetComplianceAudit`, `assets.AssetComplianceIncident` + `AssetReplacementPlan` (computed view) | `buildable-now` |
| **5-Year Capital Replacement Forecast Bar/Schedule Matrix** (funded vs. unfunded CapEx demand across upcoming fiscal years) | `common` | `reuses` `AssetReplacementPlan` (computed view) | `buildable-now` |
| **Cross-ERP Generic BI Semantic Cube / Widget Push (`apps/bi`)** | `differentiator` | Deferred integration with `apps/bi` (`BiDashboard`, `KpiDefinition`) | `integration/later` |

### 3.4 What-if Scenario Modeling
*`NavERP.md`: Budget impact of expansion, consolidation, or accelerated replacement.*

| Feature | Priority | Spine / Existing Model Mapping | Horizon |
|---|---|---|---|
| **Multi-Scenario Capital & Portfolio Simulation** (`baseline_bau`, `fleet_expansion`, `site_consolidation`, `accelerated_replacement`, `budget_constrained`, `deferred_maintenance_impact`, `sustainability_retrofit`) | `table-stakes` | `new table` (`AssetPortfolioScenario`) | `buildable-now` |
| **Expansion / Consolidation / Acceleration / CapEx Limit Drivers** (fleet growth %, consolidation reduction %, acceleration/deferral months, annual CapEx cap, discount & inflation rates) | `table-stakes` | `new table` (`AssetPortfolioScenario`) | `buildable-now` |
| **Deterministic Live Portfolio Simulation Engine** (runs against tenant `AssetReplacementPlan`, `AssetLifecycleCostAnalysis`, `AssetConditionAssessment`, and `AssetRiskRegister` rows to calculate Baseline vs. Simulated CapEx, OpEx maintenance savings, deferred backlog delta, projected avg health score, projected FCI %, risk exposure delta, NPV, payback years, and Benefit-Cost Ratio) | `differentiator` | `reuses` `AssetReplacementPlan`, `AssetLifecycleCostAnalysis`, `AssetRiskRegister` + **`AssetPortfolioScenario`** | `buildable-now` |
| **Side-by-Side Scenario Comparison View** (compares Baseline vs. 2+ active scenarios cleanly on CapEx, OpEx, Health/FCI, Risk, and NPV) | `common` | `reuses` `AssetPortfolioScenario` (computed comparison view) | `buildable-now` |

### 3.5 Executive Reporting & KPIs
*`NavERP.md`: Asset ROI, maintenance cost ratios, and compliance scorecards.*

| Feature | Priority | Spine / Existing Model Mapping | Horizon |
|---|---|---|---|
| **Immutable Period Executive KPI Scorecards** (distinct from per-asset operational `11.6 AssetPerformanceScorecard`: snapshots portfolio/org-unit/category financial & governance KPIs per period) | `table-stakes` | `new table` (`AssetExecutiveScorecard`) | `buildable-now` |
| **Core EAM Executive Financial & Reliability Ratios**: Asset ROI / ROA %, Maintenance Cost % of RAV, Planned vs. Unplanned Maintenance Ratio %, Portfolio FCI %, CapEx Budget Adherence %, Fleet Availability / Avg OEE %, Lifecycle Cost per Asset | `table-stakes` | `reuses` `11.1`–`11.12`, `accounting.FixedAsset` + **`AssetExecutiveScorecard`** | `buildable-now` |
| **Compliance & Risk Governance Scorecard Metrics** (Compliance Audit Pass Rate %, Open Compliance Incidents count, Total Residual Risk Exposure, Unfunded Replacement Backlog) | `table-stakes` | `reuses` `assets.AssetComplianceAudit`, `assets.AssetComplianceIncident`, `assets.AssetRiskRegister` + **`AssetExecutiveScorecard`** | `buildable-now` |
| **Target vs. Actual RAG Threshold Evaluation & One-Click Live Refresh** (`green` / `amber` / `red` grading + snapshot recomputation from live tenant asset data while keeping published/board-approved records locked) | `common` | `new table` (`AssetExecutiveScorecard`) | `buildable-now` |

### 3.6 Beyond the Bullets (High-Value Domain Additions)
| Feature | Priority | Notes | Horizon |
|---|---|---|---|
| **Deferral Cost Penalty Quantification** (explicitly tracks estimated extra maintenance/risk cost incurred when a replacement plan is deferred instead of funded) | `differentiator` | Included on `AssetReplacementPlan` (`deferral_penalty_cost`, `deferred_maintenance_cost`) | `buildable-now` |
| **Executive CSV Export & Printable Scorecard / CIP Views** | `common` | Clean CSV export views + print-friendly summary tables | `buildable-now` |
| **External BI / ERP Warehouse Sync & Automated Scheduled Snapshots** | `differentiator` | Integration hub (`11.15`) + generic `apps/bi` bridge | `integration/later` |

---

## 4. Recommended Build Scope (`11.14`)

Recommend **4 clean, tenant-scoped models** (`ALCC`, `ARPL`, `AWIF`, `AKPI`) under `apps/assets/models/AssetAnalytics/`, paired with a **computed Portfolio Performance Dashboard & Scenario Comparison view suite** (no duplicate persistent dashboard model).

All 4 models inherit `TenantNumbered` (from `apps/assets/models/_base.py`, which already includes `tenant`, `created_at`, `updated_at`, and unique `number`). All `CharField` choice lengths comply with L65 (`max_length >= longest key`).

### Model 1 — `AssetLifecycleCostAnalysis` (`NUMBER_PREFIX = "ALCC"`)
- **Purpose**: Cradle-to-grave Total Cost of Ownership (TCO), Equivalent Annual Cost (EAC), Maintenance-to-RAV ratio, and Repair-vs-Replace economic end-of-life recommendation for an asset or category/org-unit cohort.
- **Verified FKs**:
  - `fixed_asset` -> `"accounting.FixedAsset"` (`SET_NULL`, null/blank)
  - `operational_asset` -> `"scm.Asset"` (`SET_NULL`, null/blank)
  - `asset_category` -> `"assets.AssetCategory"` (`SET_NULL`, null/blank)
  - `asset_model` -> `"assets.AssetModel"` (`SET_NULL`, null/blank)
  - `org_unit` -> `"core.OrgUnit"` (`SET_NULL`, null/blank)
  - `currency` -> `"accounting.Currency"` (`SET_NULL`, null/blank)
  - `analyzed_by` -> `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank)
- **Key Fields**:
  - `title` (`CharField(200)`), `analysis_date` (`DateField`), `analysis_horizon_years` (`PositiveIntegerField(default=10)`), `discount_rate_pct` (`DecimalField(5,2)`), `lifecycle_stage` (`CharField(20)`), `status` (`CharField(20)`).
  - Spend & recovery buckets (`DecimalField(15,2)`): `acquisition_capital_cost`, `installation_commissioning_cost`, `preventive_maintenance_cost`, `corrective_maintenance_cost`, `service_contract_cost`, `energy_utility_cost`, `downtime_opportunity_cost`, `insurance_compliance_cost`, `accumulated_depreciation_cost`, `expected_salvage_value`, `warranty_insurance_recoveries`, `current_replacement_value`.
  - Computed outputs: `total_lifecycle_cost` (net TCO), `equivalent_annual_cost` (EAC), `maintenance_to_rav_pct`, `opex_to_capex_ratio`, `economic_eol_year` (`PositiveIntegerField(null=True, blank=True)`), `recommendation` (`CharField(25)`), `notes` (`TextField(blank=True)`).
  - Action helper: **`populate_from_asset_records()`** / recalculate view pulling live totals from `11.1`, `11.4`, `11.5`, `11.6`, `11.8`, `11.9` when `fixed_asset` / `operational_asset` is linked.
- **Choices**:
  - `LIFECYCLE_STAGE_CHOICES`: `acquisition`, `in_service`, `mid_life`, `late_life`, `end_of_life`, `disposed` (`max_length=20`)
  - `RECOMMENDATION_CHOICES`: `retain_operate`, `overhaul_refurbish`, `schedule_replacement`, `dispose_retire` (`max_length=25`)
  - `STATUS_CHOICES`: `draft`, `calculated`, `reviewed`, `approved`, `archived` (`max_length=20`)

### Model 2 — `AssetReplacementPlan` (`NUMBER_PREFIX = "ARPL"`)
- **Purpose**: End-of-life prediction, FCI & backlog quantification, risk-weighted priority scoring, inflation-adjusted capital budget forecasting, and replacement scheduling.
- **Verified FKs**:
  - `fixed_asset` -> `"accounting.FixedAsset"` (`SET_NULL`, null/blank)
  - `operational_asset` -> `"scm.Asset"` (`SET_NULL`, null/blank)
  - `asset_category` -> `"assets.AssetCategory"` (`SET_NULL`, null/blank)
  - `asset_model` -> `"assets.AssetModel"` (`SET_NULL`, null/blank)
  - `org_unit` -> `"core.OrgUnit"` (`SET_NULL`, null/blank)
  - `location` -> `"scm.Location"` (`SET_NULL`, null/blank)
  - `currency` -> `"accounting.Currency"` (`SET_NULL`, null/blank)
  - `condition_assessment` -> `"assets.AssetConditionAssessment"` (`SET_NULL`, null/blank)
  - `lifecycle_analysis` -> `"assets.AssetLifecycleCostAnalysis"` (`SET_NULL`, null/blank)
  - `capital_budget` -> `"accounting.Budget"` (`SET_NULL`, null/blank)
  - `linked_requisition` -> `"assets.AssetRequisition"` (`SET_NULL`, null/blank)
  - `planner` -> `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank)
- **Key Fields**:
  - `title` (`CharField(200)`), `predicted_eol_date` (`DateField`), `remaining_useful_life_months` (`IntegerField(default=0)`), `planned_replacement_year` (`PositiveIntegerField`), `planned_quarter` (`CharField(5)`), `replacement_strategy` (`CharField(25)`), `funding_status` (`CharField(20)`), `status` (`CharField(20)`).
  - Assessment & scoring: `condition_score` (`DecimalField(5,2)`), `criticality_weight` (`PositiveSmallIntegerField(default=3)`), `failure_risk_score` (`DecimalField(5,2)`), `priority_score` (`DecimalField(5,2)`), `priority_band` (`CharField(15)`).
  - Financials (`DecimalField(15,2)`): `current_replacement_value`, `deferred_maintenance_cost`, `fci_ratio_pct` (`DecimalField(7,2)`), `estimated_replacement_cost`, `inflation_rate_pct` (`DecimalField(5,2)`), `inflation_adjusted_cost`, `estimated_salvage_recovery`, `deferral_penalty_cost`, `notes` (`TextField(blank=True)`).
- **Choices**:
  - `PRIORITY_BAND_CHOICES`: `critical`, `high`, `medium`, `low` (`max_length=15`)
  - `QUARTER_CHOICES`: `q1`, `q2`, `q3`, `q4` (`max_length=5`)
  - `STRATEGY_CHOICES`: `like_for_like`, `technology_upgrade`, `capacity_expansion`, `consolidate_retire`, `refurbish_extend` (`max_length=25`)
  - `FUNDING_STATUS_CHOICES`: `unfunded`, `requested`, `budget_allocated`, `deferred` (`max_length=20`)
  - `STATUS_CHOICES`: `forecasted`, `proposed`, `approved`, `scheduled`, `executed`, `deferred`, `cancelled` (`max_length=20`)

### Model 3 — `AssetPortfolioScenario` (`NUMBER_PREFIX = "AWIF"`)
- **Purpose**: What-if capital & portfolio simulation modeling the CapEx, OpEx, FCI/health, backlog, and risk impact of expansion, consolidation, accelerated replacement, or constrained budgets.
- **Verified FKs**:
  - `scope_org_unit` -> `"core.OrgUnit"` (`SET_NULL`, null/blank)
  - `scope_category` -> `"assets.AssetCategory"` (`SET_NULL`, null/blank)
  - `currency` -> `"accounting.Currency"` (`SET_NULL`, null/blank)
  - `baseline_scenario` -> `"self"` (`SET_NULL`, null/blank)
  - `owner` -> `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank)
- **Key Fields**:
  - `name` (`CharField(200)`), `scenario_type` (`CharField(35)`), `is_baseline` (`BooleanField(default=False)`), `base_fiscal_year` (`PositiveIntegerField`), `horizon_years` (`PositiveIntegerField(default=5)`), `status` (`CharField(20)`).
  - Simulation levers: `annual_capex_budget_limit` (`DecimalField(15,2)`), `discount_rate_pct` (`DecimalField(5,2)`), `inflation_rate_pct` (`DecimalField(5,2)`), `acceleration_months` (`IntegerField(default=0)`), `fleet_growth_pct` (`DecimalField(6,2)`), `consolidation_reduction_pct` (`DecimalField(6,2)`), `maintenance_efficiency_gain_pct` (`DecimalField(6,2)`).
  - Baseline vs. Simulated results (`DecimalField(15,2)` / `DecimalField(6,2)`): `baseline_capex_total`, `simulated_capex_total`, `capex_variance_amount`, `baseline_opex_maintenance`, `simulated_opex_maintenance`, `opex_savings_amount`, `baseline_deferred_backlog`, `simulated_deferred_backlog`, `baseline_avg_health_score`, `simulated_avg_health_score`, `baseline_fci_pct`, `simulated_fci_pct`, `baseline_risk_exposure`, `simulated_risk_exposure`, `net_present_value`, `payback_period_years`, `benefit_cost_ratio`.
  - `assumptions_summary` (`TextField(blank=True)`).
  - Action helper: **`run_simulation()`** action querying tenant `AssetReplacementPlan`, `AssetLifecycleCostAnalysis`, `AssetConditionAssessment`, and `AssetRiskRegister` to compute deterministic Baseline vs. Simulated deltas.
- **Choices**:
  - `SCENARIO_TYPE_CHOICES`: `baseline_bau`, `fleet_expansion`, `site_consolidation`, `accelerated_replacement`, `budget_constrained`, `deferred_maintenance_impact`, `sustainability_retrofit` (`max_length=35`)
  - `STATUS_CHOICES`: `draft`, `simulated`, `under_review`, `recommended`, `adopted`, `archived` (`max_length=20`)

### Model 4 — `AssetExecutiveScorecard` (`NUMBER_PREFIX = "AKPI"`)
- **Purpose**: Executive KPI reporting & compliance scorecards tracking Asset ROI, Maintenance Cost % RAV, Planned vs. Unplanned Maintenance %, Portfolio FCI, Fleet OEE/Availability, Risk Exposure, and Regulatory Compliance Rate with RAG status and frozen period snapshots.
- **Verified FKs**:
  - `org_unit` -> `"core.OrgUnit"` (`SET_NULL`, null/blank)
  - `asset_category` -> `"assets.AssetCategory"` (`SET_NULL`, null/blank)
  - `currency` -> `"accounting.Currency"` (`SET_NULL`, null/blank)
  - `prepared_by` -> `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank)
  - `approved_by` -> `settings.AUTH_USER_MODEL` (`SET_NULL`, null/blank)
- **Key Fields**:
  - `title` (`CharField(200)`), `period_type` (`CharField(15)`), `period_start` (`DateField`), `period_end` (`DateField`), `rag_status` (`CharField(10)`), `status` (`CharField(20)`).
  - Portfolio valuation & returns: `total_asset_count` (`PositiveIntegerField(default=0)`), `gross_replacement_value` (`DecimalField(16,2)`), `total_net_book_value` (`DecimalField(16,2)`), `total_maintenance_spend` (`DecimalField(15,2)`), `annual_asset_return_amount` (`DecimalField(15,2)`), `asset_roi_pct` (`DecimalField(7,2)`), `target_asset_roi_pct` (`DecimalField(7,2)`).
  - Cost & reliability KPIs: `maintenance_cost_to_rav_pct` (`DecimalField(6,2)`), `target_mcr_pct` (`DecimalField(6,2)`), `planned_maintenance_ratio_pct` (`DecimalField(6,2)`), `portfolio_fci_pct` (`DecimalField(6,2)`), `capex_budget_utilization_pct` (`DecimalField(6,2)`), `fleet_availability_pct` (`DecimalField(6,2)`), `portfolio_oee_pct` (`DecimalField(6,2)`).
  - Compliance & risk KPIs: `compliance_audit_pass_rate_pct` (`DecimalField(6,2)`), `target_compliance_rate_pct` (`DecimalField(6,2)`), `open_compliance_incidents` (`PositiveIntegerField(default=0)`), `total_risk_exposure_amount` (`DecimalField(15,2)`), `unfunded_replacement_backlog` (`DecimalField(15,2)`).
  - `executive_summary` (`TextField(blank=True)`).
  - Action helper: **`compute_from_live_portfolio()`** action (allowed while `draft`) populating metrics directly from tenant `11.1`–`11.14` + `accounting.FixedAsset` records and evaluating RAG status.
- **Choices**:
  - `PERIOD_TYPE_CHOICES`: `monthly`, `quarterly`, `annual`, `ytd`, `adhoc` (`max_length=15`)
  - `RAG_STATUS_CHOICES`: `green`, `amber`, `red` (`max_length=10`)
  - `STATUS_CHOICES`: `draft`, `published`, `board_approved`, `archived` (`max_length=20`)

### Computed Views (No Extra Model)
1. **Portfolio Performance Dashboard (`portfolio_dashboard`)**:
   - Filterable by `org_unit`, `asset_category`, `location`, `fiscal_year`.
   - Renders:
     - **Asset Health Heat Map** (`Condition Tier × Criticality Tier` grid from `AssetConditionAssessment` + `scm.Asset.criticality` + `AssetPerformanceScorecard`)
     - **Investment Return & TCO Summary** (Gross Replacement Value, Net Book Value, Asset ROI %, MCR % RAV, Top-5 Costliest Lifecycle Assets from `ALCC` & `accounting.FixedAsset`)
     - **Risk Exposure & Compliance Posture** (Residual Risk Exposure by severity from `AssetRiskRegister`, Compliance Pass Rate & Open Incidents from `11.11`, Unfunded Backlog & FCI from `ARPL`)
     - **Multi-Year Capital Replacement Forecast** (year-by-year funded vs. unfunded demand from `ARPL`)
2. **What-If Scenario Comparison View (`scenario_compare`)**:
   - Side-by-side matrix comparing tenant `AssetPortfolioScenario` records on CapEx delta, OpEx savings, Health/FCI trajectory, Risk delta, and NPV/Payback.

---

## 5. Belongs to Sibling Sub-modules (Explicit Exclusions)

- **`11.4 Asset Depreciation & Valuation`**: Depreciation schedules, GL postings, revaluations, and capitalization thresholds remain in `11.4` (`ADEP`, `AREV`); `11.14` consumes book values/depreciation totals read-only.
- **`11.6 Asset Performance & Utilization`**: Per-asset operational downtime, OEE, kWh/carbon logs, and per-asset operational scorecards (`APSC`) remain in `11.6`; `11.14` rolls them up into **portfolio/executive** scorecards (`AKPI`) and dashboards.
- **`11.10 Asset Lease & Rental Management`**: Acquisition Lease-vs-Buy NPV (`ALBA`) and IFRS 16 lease schedules remain in `11.10`; `11.14` owns post-acquisition cradle-to-grave LCC and repair-vs-replace portfolio planning.
- **`11.12 Asset Risk Management`**: Individual asset risk register entries (`ARK`) and continuity plans remain in `11.12`; `11.14` aggregates risk exposure in portfolio views and scenario modeling.
- **`Module 10 apps/bi`**: Generic cross-ERP OLAP/BI dashboards (`BiDashboard`), semantic KPI definitions, and generic `WhatIfScenario` models stay in `apps/bi` with zero hard FK from `11.14`.

---

## 6. Deferred / Integration Later

- **Live IoT Telemetry & ML Predictive Failure Curves**: Belongs to `11.15` (Integration/API Hub) and `11.17` (AI & Predictive Maintenance).
- **Deep Scope 1/2/3 Carbon & ESG Analytics**: Belongs to `11.16` (Asset Sustainability & ESG Tracking).
- **Automated Push of `AKPI` / `AWIF` into `apps/bi` Enterprise Data Warehouse**: Optional connector task once `11.15` API Hub lands.

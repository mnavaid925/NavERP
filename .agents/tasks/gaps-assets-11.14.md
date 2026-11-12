# Gap Register — Module 11.14 Asset Analytics & Business Intelligence

**Sub-module**: `11.14 Asset Analytics & Business Intelligence` (`apps/assets`, package `AssetAnalytics`)
**Review Register**: `.claude/tasks/review-assets-11.14.md` (34 findings: 6 Critical, 15 Important, 13 Minor — all `[x] fixed`)
**In-Scope Gaps**: None (all contract features, 291 dedicated tests, and sibling cleanup `GAP-assets-11.16-04` resolved).

---

## Deferred / Cross-Module Future Enhancements

### GAP-assets-11.14-01 — ML-Based Failure Curve & Live IoT Telemetry EOL Forecasting
- **Owner**: `assets` (`11.17 AI & Predictive Maintenance`)
- **Waiting For / Blocked On**: Sub-module `11.17 AI & Predictive Maintenance` (`AssetTelemetryLog` streaming & failure-curve inference pipelines) building on `11.15` telemetry ingestion.
- **Status**: `- [~]` Deferred — `AssetReplacementPlan` (`ARPL-`) currently computes deterministic replacement score, remaining useful life percentage, FCI, and renewal capex from `FixedAsset` + maintenance totals; ML Weibull/telemetry RUL forecasting is scoped to `11.17`.
- **Done When**: `11.17` predictive telemetry model outputs feed `AssetReplacementPlan` RUL/failure-probability fields via a loosely coupled service call and have passing tests in `apps/assets/tests/`.

### GAP-assets-11.14-02 — Deep Scope 1/2/3 Carbon & ESG Portfolio Analytics
- **Owner**: `assets` (`11.16 Asset Sustainability & ESG Tracking`)
- **Waiting For / Blocked On**: Cross-sub-module portfolio rollups integrating `11.16` `AssetEnergyUsage` / `AssetCarbonEmission` / `AssetSustainabilityGoal` tables into executive scorecard / BI dashboards without breaking clean service boundaries.
- **Status**: `- [~]` Deferred — `AssetExecutiveScorecard` (`AKPI-`) and `portfolio_dashboard` track TCO, ROI, uptime/utilization, FCI, capex backlog, and depreciation accuracy; deep Scope 1/2/3 emissions rollups belong to `11.16` / future executive ESG BI extensions.
- **Done When**: ESG Scope 1/2/3 intensity and sustainability target attainment KPIs are exposed on `portfolio_dashboard` / `AssetExecutiveScorecard` from `11.16` aggregates with full tenant isolation tests.

### GAP-assets-11.14-03 — Automated Scheduled Push of `AKPI` / `AWIF` Snapshots into `apps/bi` Enterprise Data Warehouse
- **Owner**: `assets` / `bi` (cross-module reporting integration)
- **Waiting For / Blocked On**: `apps/bi` scheduled warehouse ingestion contract so `apps/assets` preserves zero hard cross-app foreign keys to `apps/bi`.
- **Status**: `- [~]` Deferred — `AssetExecutiveScorecard` and `AssetPortfolioScenario` currently serve self-contained CSV exports and computed dashboard/compare views within `apps/assets`.
- **Done When**: A documented read/export connector pushes published `AssetExecutiveScorecard` (`AKPI-`) and approved `AssetPortfolioScenario` (`AWIF-`) snapshots into `apps/bi` without adding hard cross-app FKs and with integration tests passing.

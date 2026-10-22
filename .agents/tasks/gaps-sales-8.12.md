# Gap Register: Sub-module 8.12 Sales Analytics & Intelligence

**Module**: Module 8 — Sales Management System (`apps/sales/`)  
**Sub-module**: 8.12 Sales Analytics & Intelligence  
**Status**: Core Scope Complete — Every NavERP.md bullet ships a live, tenant-scoped, CRUD-complete page and derived console. The gaps below represent **external integrations, AI/ML dependencies, or future automation hooks**, not unfinished work inside the built surface.  
**Updated**: 2026-10-22  
**Contract**: `.claude/tasks/contract-sales-8.12.md` · **Research**: `.claude/tasks/research-sales-8.12.md` · **Review**: `.claude/tasks/review-sales-8.12.md` · **Plan**: `.claude/tasks/todo.md`  

---

## 1. As-Built Core Surface Status

- **Core Models**:
  - `WinLossDebrief` (`WLA-`): Tenant-isolated win/loss intelligence interview records with JSON decision driver arrays, feedback team classification, and buyer quotes.
  - `StageVelocityAnalysis` (`VCA-`): Tenant-isolated pipeline stage duration, bottleneck ranking, cycle days, and median/P90 latency tracking.
  - `FunnelConversionRecord` (`FNL-`): Tenant-isolated funnel stage-to-stage transition metrics, dropoff counters, and conversion efficiency percentages.
  - `RepPerformanceScorecard` (`RPS-`): Tenant-isolated sales rep holistic scorecards tracking activity volume, conversion efficiency, pipeline velocity, and quota attainment.
- **CRUD Surface**: 4 complete entity CRUD sets (4 lists with search/filters/pagination, 4 detail views, 4 create forms with `@tenant_admin_required`, 4 edit forms, 4 POST-only delete actions).
- **Derived Consoles**: 6 comprehensive operational boards in `AnalyticsConsoles.py`:
  1. `analytics_console` (`/sales/sales-analytics/`): Executive birds-eye view linking debriefs, velocity analyses, funnel stats, and rep performance metrics.
  2. `win_loss_console` (`/sales/sales-analytics/win-loss/`): Win/loss ratios, competitor head-to-head outcomes, and decision driver aggregations.
  3. `velocity_console` (`/sales/sales-analytics/velocity/`): Stage aging, pipeline bottlenecks, and cycle time acceleration opportunities.
  4. `funnel_console` (`/sales/sales-analytics/funnel/`): Stage-to-stage conversion rates, leakage points, and drop-off analysis.
  5. `rep_scorecard_console` (`/sales/sales-analytics/rep-scorecards/`): Leaderboards, quota attainment rankings, and rep coaching gaps.
  6. `benchmark_console` (`/sales/sales-analytics/benchmarks/`): Industry vs. internal performance benchmarks across sales velocity and conversion KPIs.
- **Sidebar Integration**: `LIVE_LINKS["8.12"]` registered in `apps/core/navigation.py`.
- **Migrations**: `0024_winlossdebrief_stagevelocityanalysis_and_more.py` & `0027_winlossdebrief_sales_wla_tenant_debrief_idx_and_more.py`.
- **Seeder**: `_seed_sales_analytics` in `apps/sales/management/commands/seed_sales.py` (idempotent, verified across consecutive runs).
- **Ownership**: Zero duplicate tables. Reuses core spine: `crm.Opportunity` (`OPP-`), `crm.OpportunityOutcome` (`OUT-`), `sales.PipelineStage`, `sales.OpportunityPipeline`, `sales.WinLossReason`, `sales.Competitor`, `sales.QuotaPlan`, `sales.CoachingScorecard`, `sales.ForecastPeriod`, `sales.SalesTerritory`, `accounts.User`.
- **Financial Postings**: Pure analytics & reporting surface; posts zero `JournalEntry` records.
- **Test Suite**: 69 test cases passing 100% green across models, forms, views, and security.

---

## 2. Deferred / External Integration Register

| Gap ID | Owner | Status | Waiting For / Blocked On | Done When |
|---|---|---|---|---|
| `GAP-sales-8.12-01` | External Integrations / Audio AI | `[~] Deferred` | Audio call recording / transcription provider (Gong, Chorus, Zoom AI). NavERP does not currently ingest call audio streams. | Win/loss debriefs can ingest transcribed call snippets directly and auto-extract sentiment tags into `decision_drivers`. |
| `GAP-sales-8.12-02` | Module 23 `ai` | `[~] Deferred` | Module 23 AI & Intelligent Automation build. Machine-learned stage slip and cycle stalling prediction. | The velocity console surfaces automated ML risk alerts when an active opportunity's stage age exceeds historical P90 thresholds. |
| `GAP-sales-8.12-03` | Frontend UI / Visualisation | `[~] Deferred` | Client-side Sankey diagram library integration for multi-stage conversion flow diagrams. | The funnel console renders an interactive multi-stage Sankey diagram visualizing opportunity flow and drop-off. |
| `GAP-sales-8.12-04` | Advanced Analytics | `[~] Deferred` | Statistical clustering algorithms for auto-cohorting reps based on deal complexity and territory sizing. | Rep performance scorecards automatically normalize quota attainment and velocity scores based on territory potential clustering. |
| `GAP-sales-8.12-05` | Sales Enablement (8.10) | `[~] Deferred` | Automated synchronization between 8.12 Win/Loss Debrief aggregations and 8.10 Competitor Battlecards. | Competitor Battlecard strengths and counter-strategies automatically receive frequency update flags when recurring loss drivers reference that competitor. |
| `GAP-sales-8.12-06` | QA / Test Automation | `[x] Closed` | Phase 6 verification completed. 69 tests across models, forms, views, and security suites pass with zero regressions. | `test_salesanalytics_models.py`, `test_salesanalytics_forms.py`, `test_salesanalytics_views.py`, and `test_salesanalytics_security.py` exist and pass 100% green. |

---

## 3. Explicitly Declined Scope

| Declined Feature | Rationale |
|---|---|
| Redundant Opportunity or Rep Tables | Strict adherence to spine ownership (L36/L37); references `crm.Opportunity` and `accounts.User` via FK. |
| Storing Redundant KPI Aggregates | Total pipeline value, win rate percentages, and quota attainment are derived dynamically on console views to prevent synchronization drift. |
| Non-tenant-scoped Analytics Queries | All analytics aggregation queries strictly enforce `tenant=request.tenant` isolation. |

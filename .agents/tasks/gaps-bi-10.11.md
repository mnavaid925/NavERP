# Gap Register: Sub-module 10.11 — KPI & Performance Scorecards (apps/bi)

> **Context**: Sub-module 10.11 delivers centralized KPI definition libraries (`KpiDefinition`), Kaplan & Norton Balanced Scorecards with 4 strategic perspectives (`PerformanceScorecard`), relational KPI bindings and actual measurement tracking (`ScorecardKpiAssignment`), and cause-and-effect strategic goals (`StrategicObjective`) with interactive Strategy Maps.
> All core CRUD workflows, measurement refresh, roll-up recalculation, strategy map visualization, actual measurement recording, CSRF/method security guards, 23 review findings, and 183 dedicated tests (1,613 tests across `apps/bi/`) are fully completed and verified 100% green.

---

### GAP-10.11-01: Automated External SaaS Metric Ingestion
- **Owner**: `bi` / Integration Hub Agent
- **Waiting For / Blocked On**: Sub-module 10.19 (Integration & API Ecosystem) connector endpoints and OAuth token stores for third-party SaaS platforms (HubSpot, Salesforce, Stripe, Jira).
- **Status**: `- [~]` Deferred to Sub-module 10.19 (manual measurement recording, semantic layer measure integration, and 1-click refresh workbench are fully functional).
- **Done When**: Out-of-the-box scheduled background synchronizers ingest metric values directly from external SaaS APIs into `KpiDefinition` current measurements and `ScorecardKpiAssignment` actuals without manual input.

### GAP-10.11-02: Predictive Anomaly Detection & Forecast Trend Regressions on KPIs
- **Owner**: `bi` / Advanced Analytics Agent
- **Waiting For / Blocked On**: Sub-module 10.13 (Predictive & Advanced Analytics) time-series forecasting engine and Scikit-learn/Statsmodels regressors.
- **Status**: `- [~]` Deferred to Sub-module 10.13 (deterministic plan-vs-actual variance, normalized scores, and trend arrows [↗/→/↘] based on measurement history are fully operational).
- **Done When**: Time-series forecast models generate confidence intervals, forward-looking trend projections, and automated threshold breach anomaly alerts on historical KPI series.

### GAP-10.11-03: Bi-Directional Financial Budget Writeback to General Ledger
- **Owner**: `accounting` / Financial Ledger Agent
- **Waiting For / Blocked On**: Cross-module integration with Module 2 Accounting `accounting.Budget` / `BudgetLine` approval and variance workflows.
- **Status**: `- [~]` Deferred to Module 2 integration pass (scorecard weighted roll-ups and target tracking operate autonomously without direct GL journal writes).
- **Done When**: Scorecard financial targets can synchronize directly with General Ledger budget revisions through approved, audited variance reconciliations.

---

### Summary of Completed Invariants:
- All 23 review findings (`C1`–`C5`, `I1`–`I10`, `M1`–`M8`) in `.claude/tasks/review-bi-10.11.md` are closed (`[x] fixed`).
- Zero open critical, important, or minor defects in Sub-module 10.11.
- 183 passing dedicated tests across `test_performancescorecards_models.py`, `_forms.py`, `_views.py`, and `_security.py`.
- 1,613 passing tests across full unfiltered `apps/bi` test suite.

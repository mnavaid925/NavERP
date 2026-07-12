# Research - Module 3: Human Resource Management (HRM) - sub-module 3.32 Analytics Dashboard (hrm)

## Framing
3.32 sits ON TOP of the already-shipped derived HR reporting layer:
- 3.28 HR Reports (`hr_reports_index`, `headcount_report`, `attrition_report`, `diversity_report`, `cost_report`, `hiring_report`)
- 3.29 Attendance Reports (`attendance_reports_index`, `attendance_summary_report`, `late_early_report`, `absenteeism_report`, `overtime_report`)
- 3.30 Leave Reports (`leave_reports_index`, `leave_register_report`, `leave_liability_report`, `comp_off_report`, `leave_trend_report`)
- 3.31 Payroll Reports (`payroll_reports_index`, `salary_register_report`, `tax_report`, `statutory_report`, `ctc_report`, `cost_center_report`)

All four live in `apps/hrm/views.py` and share the helpers `_report_period(request)`, `_report_department(request, tenant)`,
`_dept_choices(tenant)`, `_headcount_at(tenant, as_of)`, `_age(dob, as_of)`, `_tenure_band(days)`, `_age_band(years)`,
`_month_end(today, months_ago)`, plus constants `VOLUNTARY_SEPARATION_TYPES`, `TENURE_BANDS`, `AGE_BANDS`. 3.32 MUST
reuse these helpers rather than re-deriving headcount/attrition/leave/payroll math. `payroll_reports_index` and
`hr_reports_index` already use a "KPI tile list" pattern (`tiles = [{"label", "value", "url", "icon"}, ...]`) -
that pattern is the direct ancestor of the 3.32 Executive Dashboard.

The proven saved-dashboard mechanic already exists in this codebase at CRM 1.6
(`apps/crm/models.py` `AnalyticsDashboard` + `DashboardWidget`, `apps/crm/analytics.py` `WIDGET_METRICS` /
`compute_widget()`, `apps/crm/views.py` `dashboard_*` / `widget_*` / `widget_move` using position-swap "up/down"
reordering, NOT pixel drag-drop). 3.32 should mirror this pattern for HR metrics instead of inventing a new one.

## Leaders surveyed (with source links)
1. **Workday People Analytics / Prism Analytics** - enterprise HCM-native analytics; embedded dashboards, ML-powered
   attrition-risk surfacing, pre-built + customizable dashboards, unified role-based security model -
   https://www.workday.com/en-us/products/analytics-reporting/data-hub.html
2. **Visier (Workforce Intelligence)** - purpose-built people-analytics platform; ML attrition/flight-risk models
   with quantified impact + "what-if" retention simulation, prebuilt workforce metrics + benchmark library, AI
   assistant (Vee) for conversational insights - https://www.visier.com/ , https://www.visier.com/blog/predictive-people-analytics-machine-learning/
3. **SAP SuccessFactors People/Workforce Analytics** - customizable dashboards with 2,000+ standardized metrics,
   persona dashboards (Performance, CDP/succession-readiness), predictive risk flags (attrition, skills gaps),
   absence-metric benchmarking by department/season/tenure - https://www.sap.com/products/hcm/data-cloud.html
4. **ADP DataCloud** - prebuilt dashboards + heavy INDUSTRY benchmarking from ADP's own aggregated/anonymized
   client base (by job title/industry); named modules: Pay Equity, Turnover Cost, Top Performers, and a Turnover
   Probability predictive tool (tenure-in-role + under-pay-for-role signals) -
   https://www.adp.com/what-we-offer/products/adp-datacloud.aspx
5. **ChartHop** - org-chart-centric people analytics + workforce/headcount planning; one-click "designed"
   dashboards or a custom chart builder, DEI analytics with segmentation + historical "time travel", scenario
   modeling tied to headcount plans - https://www.charthop.com/ , https://www.charthop.com/resources/essential-features-people-analytics-software
6. **BambooHR** - custom dashboards combining headcount/turnover/diversity/hiring-velocity/engagement widgets;
   role-specific dashboards (admin/exec/manager/employee) with user-arrangeable widgets; turnover benchmarked
   against other companies - https://www.bamboohr.com/platform/hr-data-and-reporting/custom-dashboards-and-analytics
7. **Keka** - Org Dashboard aggregating headcount/attrition/hiring/performance; Analytics tab split into
   Headcount-by-Demographics / Growth & Retention / Attrition Analysis; descriptive->diagnostic->predictive->
   prescriptive framing; AI attrition forecasting - https://www.keka.com/hr-analytics-software , https://help.keka.com/admin/org-dashboard-overview
8. **Darwinbox (Atlas)** - admin + leadership "summary dashboards" answering attrition/headcount/performance/TA
   questions at a glance; an "Attrition Predictor" (customizable-per-org or global AI model) scoring flight risk
   from performance/comp-change/engagement/tenure signals; persona-curated dashboards with AI "smart nudges" -
   https://darwinbox.com/features/mis-analytics.php , https://darwinbox.com/blog/how-darwinbox-atlas-helps-unleash-the-power-of-people-analytics
9. **Oracle Fusion HCM Analytics** - prebuilt dashboards (Workforce Demographics, Compensation, Talent, Recruitment,
   Retention Analytics); ML attrition prediction refreshed as new data flows in; "Workforce Modeling" what-if
   scenario tool - https://www.oracle.com/fusion-data-intelligence/hcm-analytics/
10. **Lattice People/HR Analytics** - aggregates performance + engagement + goals + compensation into one
    dashboard/report surface; predictive retention-risk modeling mapping sentiment against performance;
    intelligent benchmark comparisons vs industry/company-size norms - https://lattice.com/platform/analytics

**Supporting UX reference (not a headline-count leader, used only for widget/tile mechanics):**
Microsoft Power BI dashboards - tiles are pinned live snapshots of a visual, drag-to-reposition, resize by
corner-drag (1x1 to 5x5), "Add tile" for standalone KPI/text tiles, per-tile edit-details menu -
https://learn.microsoft.com/en-us/power-bi/create-reports/service-dashboard-tiles

## Feature catalog by NavERP.md 3.32 bullet

### Executive Dashboard - key HR metrics at a glance
- **Curated KPI tile strip (headcount, attrition/turnover %, open reqs, avg tenure, gross payroll cost, pending
  approvals)** - one-glance leadership snapshot · seen in: Workday Prism, Keka (Org Dashboard), Darwinbox
  (leadership summary dashboard), BambooHR (exec role dashboard), ADP DataCloud · priority: Must (table-stakes)
  · spine: derived from `EmployeeProfile`/`core.Employment`/`SeparationCase`/`Payslip`/`PayrollCycle` (no new
  table) — same shape as the existing `payroll_reports_index`/`hr_reports_index` `tiles` list · buildable now.
- **Role-specific / persona dashboards (exec vs manager vs admin view)** - different tile sets per audience ·
  seen in: BambooHR, Darwinbox, SAP SuccessFactors (persona dashboards) · priority: Should (common among
  enterprise leaders) · spine: reuse `request.user` + `@tenant_admin_required` gate (already used for all 3.28-3.31
  reports) — no per-persona model needed this pass, a single admin-facing exec view is sufficient · buildable now
  (persona variants deferred).
- **Trend sparkline / mini chart per KPI tile (last-N-month direction)** - shows whether a metric is improving or
  worsening at a glance · seen in: Workday Prism, Visier, Keka · priority: Should · spine: reuse `_month_end`
  bucketing already used by `attrition_report`'s `trend_labels`/`trend_values` · buildable now.
- **Drill-down from tile to the underlying detail report** - click a KPI to jump to its full report · seen in:
  ADP DataCloud ("click from bar chart down to specific employees"), Power BI (pin->drill) · priority: Must ·
  spine: reuse existing report URL names (`hrm:attrition_report`, `hrm:salary_register_report`, etc.) as tile
  `url` targets, exactly like `payroll_reports_index`'s tiles · buildable now.
- **Alerts / exceptions surfaced on the dashboard (overdue statutory filings, pending approvals, expiring
  probations, upcoming contract ends)** - proactive callouts, not just static numbers · seen in: Workday Prism
  (smart nudges), Darwinbox (AI smart nudges), SAP SuccessFactors (risk flags) · priority: Should · spine: reuse
  existing `StatutoryReturn`, `LeaveRequest(status='pending')`, `EmployeeProfile.probation_end_date` queries
  already computed in `payroll_reports_index`/other index views — just surfaced as a combined list · buildable now.
- **Live/auto-refresh data (no stale snapshot)** - tiles reflect current DB state on every render · seen in: all
  10 (Power BI tiles explicitly "not static screenshots") · priority: Must · spine: n/a (view is computed on
  every request, same as all 3.28-3.31 reports — no caching layer) · buildable now.
- **Embedding/distribution "in the flow of work" (Slack/Teams/email digest)** - push the exec dashboard to where
  leaders already work · seen in: Workday Prism · priority: Later (differentiator) · integration/later.

### Custom Dashboards - drag-drop dashboard builder
- **Per-user saved dashboard(s) of chosen widgets, one marked default** - a user assembles/saves their own view ·
  seen in: BambooHR (arrangeable widgets per role), ChartHop (custom chart builder), Power BI, CRM 1.6
  `AnalyticsDashboard` in this codebase · priority: Must · spine: **new table** `HRDashboard` (mirrors CRM's
  `AnalyticsDashboard`: tenant, owner, name, is_default, is_shared) · buildable now.
- **Widget catalog with fixed metric choices (KPI card / trend line / bar / pie / table), each computed live from
  a metric key** - the widget doesn't store data, it stores "which live query to run" · seen in: Power BI
  (pinned live tiles), CRM 1.6 `DashboardWidget`/`WIDGET_METRICS`/`compute_widget()` in this codebase · priority:
  Must · spine: **new table** `HRDashboardWidget` (dashboard FK, title, metric choice, chart_type choice,
  date_range choice, size choice, position) — metric choices sourced from the existing 3.28-3.31 aggregation
  functions (headcount, attrition %, voluntary/involuntary split, absenteeism %, leave liability days, gross
  payroll, top department by attrition, etc.) · buildable now.
- **Add / remove / resize / reorder widgets** - the "drag-drop" mechanic · seen in: Power BI (literal pixel
  drag+resize), ChartHop (chart builder), BambooHR ("arrange widgets") · priority: Must (the mechanic) but
  **implementation simplified**: this repo's own CRM 1.6 precedent (`widget_move` in `apps/crm/views.py`) does
  NOT do pixel drag-drop — it does position-swap "move up/down" buttons + a `size` choice field (small/medium/
  large/full) instead of free-form resize. Recommend the same for HRM · spine: `HRDashboardWidget.position` +
  `.size` · buildable now (as move-up/down, not true drag-drop JS).
- **Shared/team dashboards visible to more than the owner** - seen in: BambooHR (role-based), CRM 1.6
  `is_shared` flag · priority: Should · spine: `HRDashboard.is_shared` boolean (owner-only edit, tenant-wide read
  when shared) — reuse the CRM 1.6 field name/semantics · buildable now (fine-grained sharing/permissions
  deferred).
- **One-click "designed" (pre-built) dashboard templates vs. fully custom** - seen in: ChartHop ("enable designed
  dashboards with a single click or build your own") · priority: Later · integration/later (a seed-time default
  `HRDashboard` with a starter widget set covers this cheaply — see build scope).
- **AI-generated narrative insights/notes attached to a dashboard** - seen in: ChartHop (AI insights notes),
  Darwinbox (AI smart nudges) · priority: Later (differentiator, needs LLM integration) · integration/later.
- **True pixel drag-and-drop grid layout (react-grid-layout style)** - seen in: Power BI · priority: Later ·
  integration/later (JS grid library; deferred in favor of position/size fields, per CRM 1.6 precedent).

### Predictive Analytics - attrition prediction, hiring needs
- **Attrition / flight-risk score per employee from tenure, engagement/performance, comp, and demographic
  signals** - a per-employee risk indicator (not necessarily true ML) · seen in: Visier (ML flight-risk +
  quantified impact), Darwinbox (Attrition Predictor: performance/comp-change/engagement/tenure), ADP DataCloud
  (Turnover Probability: time-in-role + under-pay-for-role), Lattice (sentiment x performance retention-risk
  profiles), Oracle HCM, SAP SuccessFactors (risk flags), Keka (AI attrition forecasting) · priority: Must
  (near-universal in modern HR analytics; but MODEL COMPLEXITY varies) · spine: **derived view**, transparent
  heuristic score computed from data already in the spine: `core.Employment.hired_on` (tenure), `LeaveRequest`
  frequency/recency, `AttendanceRecord` lateness/absence rate (reuse `AttendanceRecord.is_late()` boundary logic
  already used by 3.29's `late_early_report`), `EmployeeProfile.date_of_birth` (age band), `probation_end_date`
  proximity, no recent `PerformanceReview` rating (if available) — weighted heuristic, NOT a trained ML model ·
  buildable now (heuristic); true ML model = integration/later.
- **Segment/team-level (not just individual) attrition risk aggregation** - "which department/manager has the
  most at-risk headcount" · seen in: Visier (segment hotspots), SAP SuccessFactors · priority: Should · spine:
  group the same per-employee heuristic by `core.OrgUnit` (department), reusing `_dept_choices`/`_report_department`
  · buildable now.
- **Headcount forecast / hiring-needs projection** - project future hiring demand from current trend +
  attrition + open reqs · seen in: Visier ("what-if" workforce planning), SAP SuccessFactors ("anticipate
  workforce trends"), Oracle HCM (Workforce Modeling what-if), Darwinbox (workforce planning analytics), ChartHop
  (headcount planning module) · priority: Must · spine: **derived view** combining `Designation.budgeted_headcount`
  (existing "position-slot proxy" field, migration 0007) vs. current active `EmployeeProfile` count per
  designation, plus trailing attrition rate (reuse `attrition_report`'s turnover-rate math) projected forward, plus
  open `JobRequisition` count (3.5) — a transparent formula, not a trained forecast model · buildable now.
- **Retention-intervention simulation ("what happens if we act")** - seen in: Visier · priority: Later
  (differentiator, needs a mature ML pipeline) · integration/later.
- **Skill-gap / succession-risk prediction** - seen in: Visier, Oracle Workforce Modeling · priority: Later
  (overlaps with 3.38 Talent Management & Succession Planning, not yet built) · deferred to that module.
- **Natural-language query over predictions ("which segment is highest risk next 6 months")** - seen in: Oracle
  HCM, Visier (Vee assistant) · priority: Later · integration/later (needs LLM/NLQ layer).

### Benchmarking - industry comparison metrics
- **External industry benchmark data (aggregated across the vendor's client base, by industry/job title/region)**
  - seen in: ADP DataCloud (1M+ employers, 9,000+ job titles), Lattice (industry + company-size norms), Visier
    (benchmark library), BambooHR (turnover vs other companies) · priority: Must among leaders BUT requires a
    licensed external data feed NavERP does not have · spine: none (no external data source) · **integration/later**
    — out of scope for a single-tenant Django pass.
- **Internal benchmarking: current period vs. prior period (trend) and current vs. target/goal** - the buildable
  substitute for external industry data · seen in: SAP SuccessFactors (absence benchmarking by season/tenure),
  Keka (Growth & Retention trend section), all 10 in some form (trend charts) · priority: Must · spine: **derived
  view** comparing the current-period aggregate (reuse `_report_period`) against the immediately-prior period of
  equal length, and against an optional target value — same "target_value" concept as CRM 1.6's
  `DashboardWidget.target_value` gauge · buildable now.
- **Pay-equity / cost benchmarking (gender pay gap, cost-per-department vs. average)** - seen in: ADP DataCloud
  (Pay Equity module), SAP SuccessFactors (demographic cost analysis) · priority: Should · spine: derived view
  over `Payslip`/`PayslipLine` grouped by `EmployeeProfile.gender` and `core.OrgUnit`, reusing `cost_report`'s
  `by_department`/`by_component` aggregation shape · buildable now.
- **Scorecard view (RAG - red/amber/green status per KPI vs. target)** - seen in: SAP SuccessFactors, Keka ·
  priority: Should · spine: derived view, a thin presentation layer over the same period-comparison numbers,
  no new table (color threshold logic in the view/template) · buildable now.
- **Top-performer benchmarking (compare comp/tenure of top performers vs. peers in same role)** - seen in: ADP
  DataCloud (Top Performers module) · priority: Later (needs a performance-rating signal source wired cleanly —
  3.19 Performance Review exists but cross-linking is a bigger lift) · deferred.

## Recommended 3.32 build scope (2 new models + 3 derived views)

**Models (mirrors the proven CRM 1.6 `AnalyticsDashboard`/`DashboardWidget` pattern 1:1 for HR):**

- **`HRDashboard`** [`DASH`-numbered, `TenantNumbered`] — fields: `name` (CharField), `description` (TextField,
  blank), `owner` (FK `settings.AUTH_USER_MODEL`, SET_NULL, related_name `hr_dashboards`), `is_shared`
  (BooleanField, default False — visible tenant-wide when true), `is_default` (BooleanField, default False — the
  landing dashboard for its owner), `layout` (CharField choices one/two/three columns). Justified by: BambooHR
  "custom dashboards per role", ChartHop "designed or custom dashboards", CRM 1.6 precedent. Reuses `core.Tenant`
  (via `TenantNumbered`) — no new party/item spine touch.
- **`HRDashboardWidget`** [plain tenant-scoped child row, not numbered] — fields: `tenant` (FK, `related_name="+"`),
  `dashboard` (FK `HRDashboard`, CASCADE, related_name `widgets`), `title` (CharField), `metric` (CharField,
  choices — a fixed catalog of HR metric keys: `kpi_headcount`, `kpi_attrition_rate`, `kpi_open_reqs`,
  `kpi_avg_tenure`, `kpi_gross_payroll`, `kpi_absenteeism_rate`, `kpi_leave_liability_days`,
  `kpi_avg_attrition_risk`, `attrition_by_department`, `headcount_trend`, `hiring_funnel`, `gender_diversity`,
  `payroll_cost_by_department`, `top_attrition_risk_employees` (table) — modeled 1:1 on CRM's
  `WIDGET_METRIC_CHOICES` shape, but computed by a new `apps/hrm/analytics.py` that wraps the existing 3.28-3.31
  aggregation helpers), `chart_type` (CharField choices: kpi/gauge/bar/line/pie/doughnut/table — reuse CRM's
  `WIDGET_CHART_CHOICES` verbatim), `date_range` (CharField choices: last_30/last_90/quarter/year/all — reuse
  CRM's `ANALYTICS_RANGE_CHOICES`), `size` (CharField choices small/medium/large/full — reuse CRM's
  `WIDGET_SIZE_CHOICES`), `target_value` (DecimalField, null/blank — the benchmark-vs-target gauge value, directly
  answers the Benchmarking bullet for gauge widgets), `position` (PositiveIntegerField, default 0 — manual
  ordering, moved via up/down like CRM's `widget_move`), timestamps. Justified by: the widget-catalog + live-
  compute + reorder features found in every leader's "custom dashboard" section, kept buildable via the CRM 1.6
  precedent rather than a JS drag-drop grid.

**Derived, read-only views (no new tables — `apps/hrm/views.py`, `@tenant_admin_required`, reusing
`_report_period`/`_report_department`/`_dept_choices`):**

- **`executive_dashboard` view** — Purpose: the curated leadership KPI-tile overview (bullet 1). Source: same
  aggregation calls already used by `payroll_reports_index`/`hr_reports_index`/`attrition_report`/
  `diversity_report` — active headcount (`_headcount_at`), turnover % (reuse `attrition_report`'s formula), open
  `JobRequisition` count, avg tenure (reuse `diversity_report`'s tenure calc), latest `PayrollCycle` gross/net,
  absenteeism % (reuse 3.29's `absenteeism_report` math), pending-approval counts (`LeaveRequest(status='pending')`,
  overdue `StatutoryReturn`). Filters: `?department`, defaults to trailing-12-months like other reports. Each tile
  links to its full 3.28-3.31 report (drill-down), matching `payroll_reports_index`'s `{"label","value","url","icon"}`
  tile shape.
- **`predictive_analytics` view** — Purpose: attrition-risk heuristic scoring + hiring-needs projection (bullet 3).
  Source: per-employee heuristic score (0-100, transparent weighted sum, documented in the view docstring — NOT
  presented as ML) from tenure band (`_tenure_band`), absence/lateness rate (`AttendanceRecord`, reusing
  `is_late()`), leave-request frequency/recency (`LeaveRequest`), probation proximity
  (`EmployeeProfile.probation_end_date`); ranked table of highest-risk employees + risk-by-department rollup.
  Hiring-needs projection: `Designation.budgeted_headcount` vs. current filled count per designation, plus
  trailing attrition rate (reused from `attrition_report`) projected over the next quarter, plus open
  `JobRequisition` count (3.5) — a `gap = budgeted - filled + projected_attrition_replacements` table per
  designation/department. Filters: `?department`.
- **`benchmarking` view** — Purpose: period-over-period + vs-target comparison of core KPIs (bullet 4, internal
  substitute for unavailable external industry data). Source: current-period vs. immediately-prior-period-of-
  equal-length deltas for headcount/attrition/absenteeism/gross payroll (reusing `_report_period` twice — current
  window and the equal-length window immediately before it), plus optional target values (mirrors
  `DashboardWidget.target_value`) rendered as a RAG scorecard; a pay-equity mini-table (avg gross by
  `EmployeeProfile.gender` x `core.OrgUnit`, reusing `cost_report`'s `by_department` shape). Filters: `?department`,
  `?date_from`/`?date_to`.

**Index/landing:** `analytics_dashboard_index` (or reuse `executive_dashboard` as the 3.32 landing page) lists the
user's `HRDashboard`s (own + shared) plus links to Predictive Analytics and Benchmarking, following the same
"`<sub-module>_index` hub + individual report views" convention already established by `hr_reports_index`/
`attendance_reports_index`/`leave_reports_index`/`payroll_reports_index`.

**New file:** `apps/hrm/analytics.py` (mirrors `apps/crm/analytics.py`) holding `WIDGET_METRIC_CHOICES`,
`WIDGET_CHART_CHOICES`, `WIDGET_SIZE_CHOICES`, `ANALYTICS_RANGE_CHOICES`, and `compute_widget(widget)` /
`_r_*(tenant, start, end)` per-metric functions that each call into the existing 3.28-3.31 aggregation logic
(refactor shared math into small helpers where `views.py` and `analytics.py` both need it, e.g. a `_turnover_rate`
extracted from `attrition_report`) rather than duplicating queries inline.

## Deferred (later passes / integrations)
- **True pixel drag-and-drop grid builder (react-grid-layout style free resize/reposition)** — replaced this pass
  by `HRDashboardWidget.position` (move up/down) + `.size` (small/medium/large/full), matching the CRM 1.6
  precedent; a real JS grid library is a distinct frontend investment for a later pass.
- **Trained ML attrition/flight-risk model** — replaced this pass by a transparent, documented weighted heuristic
  over tenure/absence/leave/probation signals; a real ML pipeline (Visier/Darwinbox/ADP-style) needs a data-
  science stack and historical-outcome training data NavERP doesn't have yet.
- **External industry benchmark data feeds (ADP DataCloud-style aggregated cross-employer data, Lattice/Culture
  Amp survey-norm libraries)** — no licensed external data source; replaced this pass by internal period-over-
  period and vs-target comparisons only.
- **Dashboard sharing/permissions granularity (per-role visibility, per-widget permissions)** — this pass ships
  only owner + a single tenant-wide `is_shared` flag (mirrors CRM 1.6); role-scoped sharing is a later pass.
- **AI-generated narrative insights / natural-language query over dashboards** — needs an LLM integration layer;
  out of scope for a single Django pass.
- **Retention-intervention "what-if" simulation** — needs the ML model above as a prerequisite; deferred with it.
- **Skill-gap / succession-risk prediction** — overlaps 3.38 Talent Management & Succession Planning (not yet
  built); deferred to that module rather than duplicated here.
- **Top-performer compensation benchmarking tied to performance ratings** — needs a clean cross-link into 3.19
  Performance Review data; deferred as a follow-up enhancement once that linkage is designed.
- **Dashboard/report embedding into Slack/Teams/email digests** — external integration, deferred.
- **Pre-built "designed" dashboard template gallery** — this pass covers the equivalent cheaply via a seeded
  default `HRDashboard` with a starter widget set (seeder enhancement), not a template picker UI.

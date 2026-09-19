# Research — Sub-module 7.16: Reporting & Business Intelligence (Module 7 — Project Management, `projects`)

> **Read this first.** 7.16 is the module's **read layer**, not a fourth register. Everything it shows already
> exists as a row written by 7.1–7.15: the risk is not missing data, it is **building tables that duplicate
> queries**. Every sibling pass before this one explicitly pushed its visuals and its "save this view" need
> down to 7.16 — 7.5's contract says *"**No chart library** (7.16 owns charts)"*, 7.7 says the same, 7.4
> deferred *"burn charts, CPI trend lines and the executive cost pack"*, 7.12 ruled *"steering-committee packs
> are a computed page… 7.16 Reporting owns persisted report snapshots if a later pass wants one"*, and 7.15
> parked *"Custom Report Builder, Pivot Grids & External Data Connectors → 7.16"*. **That is the backlog this
> pass inherits**, and it is why this file spends its budget on a *metric registry*, not on models.
>
> The failure mode to resist: inventing a per-report model for each of the ~10 standard reports (a
> `StatusReport` table, a `RiskReport` table, …). Commercial leaders do not have ten report products; they have
> **one saved-report object with a type**, **one dashboard container with tiles**, and **a compute layer**. That
> is NavERP 7.16 too: 4 models, one `analytics.py`, and a family of canned report *kinds* rendered by one
> template set.

## Repo state checked first

**LIVE_LINKS built so far in module 7** (`apps/core/navigation.py`, read at run time): `7.1`–`7.15` are all
present (7.12 at line 1891, 7.13 at 1903, 7.14 at 1915, **7.15 at 1926**); **no `7.16` key exists** — this pass
adds it. NavERP.md defines 7.1–7.19, so 7.16 is the lowest unbuilt sub-module. The 7.15 block is the direct
upstream feeder (its extra live leaves are `financial_pnl`, `ar_aging`, `cash_flow_forecast`).

**Already-computed report/dashboard pages in this app — reuse and link, never rebuild** (verified by grepping
`name="…"` across `apps/projects/urls/`): `pfm_dashboard` (7.12), `utilization_dashboard` (7.11),
`velocity_report` (7.13), `financial_pnl`, `ar_aging`, `cash_flow_forecast` (7.15), `risk_analysis` (7.5),
`qrv_report` (7.6), `task_board` + the 7.8 Gantt page. 7.16's contribution over these is **configuration,
persistence, personalisation and export** — not a second health engine.

**Sibling models available to FK (all verified by `grep -rn "^class " apps/projects/models` — models are a
PACKAGE):**

| Sub-module | Verified classes | Fields 7.16 aggregates |
|---|---|---|
| 7.1 | `Project`, `ProjectRequest`, `ProjectStakeholder`, `ProjectKickoff` | `status`, `charter_status`, `methodology`, `start_date`/`end_date`, `is_overdue`, `project_manager`, `org_unit`, `client` |
| 7.2 | `ProjectTask`, `TaskDependency`, `ProjectMilestone`, `ScheduleBaseline` | `status`, `planned_start/end`, `actual_start/end`, `percent_complete`, `effort_hours`, `priority`, `moscow`, `assignee`, `node_type`; milestone `target_date` vs `actual_date`, `is_phase_gate` |
| 7.3 | `ResourceAllocation`, `ResourceTimeEntry`, `ResourceProfile` | allocation `hours_per_week`, `pct_capacity`, `total_hours`, `booking_status`, **`planned_hours(win_start, win_end)`**; time entry `hours`, `is_billable`, `activity_code`, `status`, `entry_date`, `submitted_at`, `approved_at`, **`iso_year`/`iso_week`/`week_key`** |
| 7.4 | `BudgetRevision`, `ProjectBudgetLine`, `CostControlAccount`, `ProjectExpense` | **`CostControlAccount` already exposes `bac`, `bac_with_contingency`, `ev`, `pv`, `ac`, `cv`, `sv`, `cpi`, `spi`, `eac`, `etc`, `committed`, `available`, `health` as read-only properties** — 7.16 READS them; expense `amount`, `entry_date`, `entry_type`, `source_kind`, `status`, `gl_account`, `currency` |
| 7.5 | `ProjectRisk`, `ProjectIssue`, `RiskResponseAction`, `IssueEscalation` | risk `probability`, `impact`, `cost_impact`, `schedule_impact_days`, `residual_*`, `category`, `response_strategy`, `status`, `identified_date`, `review_date`, `closed_at`; issue `severity`, `status`, `due_date`, `resolved_at`, `escalation_level` |
| 7.6 | `QualityPlan`, `QualityReview`, `DeliverableInspection`, `QualityDefect` | defect `defect_category`, `severity`, `disposition`, `status`, `identified_date`, `due_date`, `resolved_at` |
| 7.7 | `Requirement`, `ScopeItem`, `ScopeChangeRequest`, `ScopeVerification` | requirement status mix, change-request decision mix |
| 7.8 | `TaskBlock`, `TaskChecklistItem` | blocked count/duration |
| 7.9 | `Channel`, `ChannelMessage`, `Meeting`, `MeetingActionItem`, `ProjectNotification`, `DocumentShare` | activity/engagement signals, open action items |
| 7.10 | `ProjectFolder`, `ProjectDocument`, `ProjectDocumentRevision`, `DocumentTemplate`, `KnowledgeEntry` | **`DocumentTemplate.CATEGORY_CHOICES` already contains `report` and `status_update`** — 7.10's research parked *"Status-report and dashboard formats as generated reports → 7.16"*. This is the format standard an issued report files against. |
| 7.11 | `TimeActivityCode`, `OvertimeRule`, `ProjectOvertimeRecord` | overtime hours, activity mix |
| 7.12 | `Portfolio`, `Program`, `PortfolioInvestment`, `ProgramDependency` | investment `strategic_fit`/`financial_return`/`delivery_risk`/`capacity_fit` + four weights, `allocated_budget`, `status` |
| 7.13 | `Sprint`, `ProjectEpic`, `ProjectRelease`, `SprintImpediment`, `SprintRetrospective` | `committed_points`, sprint `status`, `started_at`/`completed_at` |
| 7.14 | `ClientPortalAccess`, `ClientApprovalRequest`, `StatementOfWork`, `SOWAmendment`, `VendorHandoff` | approval cycles, SOW linkage |
| 7.15 | `ProjectBillingRun`, `ProjectPaymentRecord`, `ProjectClientInvoice`, `ProjectRevenueSchedule`, `ProjectRateCard` | billing `total_time_hours`, `labor_amount`, `expense_amount`, `subtotal`, `tax_amount`, `total_amount`, `cutoff_date`, `dispatched_at`, `status`; revenue `recognized_amount`, `deferred_amount`, **`unbilled_amount`**, `completion_percent`, `method`, `fiscal_period` |

**Spine entities verified to EXIST** (`grep -rn "^class " apps/core/models/`): `Tenant`, `Party`, `PartyRole`,
`Address`, `ContactMethod`, `PartyRelationship`, `Employment`, `OrgUnit`, `Activity`, **`AuditLog`**,
**`Document`**. `accounting` owns `GLAccount`, `Currency`, `FiscalPeriod`, `JournalEntry`, `Budget`, … — read
only, never written (L29).

**Reporting precedents already in this repo (this is the strongest grounding in the file — the pattern is
as-built, not aspirational):**

| Where | What exists (verified) | Why it matters for 7.16 |
|---|---|---|
| `apps/crm/models/AnalyticsReporting/` (1.6) | `AnalyticsDashboard` [DASH-] (`owner`, `is_shared`, `is_default`, `layout`), `DashboardWidget` (child, `metric`, `chart_type`, `date_range`, `size`, `target_value`, `position`), `AnalyticsReport` [RPT-] (`report_type`, `date_range`, `group_by`, `is_favorite`, `last_run_at` system-stamped), `ReportSnapshot` (`summary` + `data` JSON, minted only by POST) | The **exact four-model shape** 7.16 needs, already shipped once. `WIDGET_METRIC_CHOICES` (21 keys) + `apps/crm/analytics.py` (471 lines, `_r_*` registry functions, `range_bounds()`, `_bucket()`) is the compute-layer convention |
| `apps/procurement/models/SpendAnalyticsReporting/SpendReports.py` (6.14) | `SpendReport` [SPR-]: `basis`, `measure`, `dimension_1`/`dimension_2`, `date_range`+`date_from/to`, four tenant-checked scope FKs (`core.Party`, `scm.ItemCategory`, `core.OrgUnit`, `accounting.GLAccount`), `min_amount`, `chart_type`, `top_n`, `is_favorite`/`is_shared`, `last_run_at`; `SpendReportSnapshot` (`summary`, `data`, `row_count`, `["-generated_at","-id"]` ordering with the tie-breaker ruling) | The **most recent and most explicit "guided builder" ruling in the repo**: *"A `SpendReport` is a SAVED SET OF CHOICES, not a stored result… each axis is picked from a dropdown whose options are the frozen `*_CHOICES` lists… that is what makes a saved report auditable."* Also *"analytics.py imports these models; this module NEVER imports analytics"* and *"RATIO MEASURES are the answer to calculated columns"* (`maverick_pct`, `classified_pct`, `avg_transaction`, `leakage`) |
| `templates/base.html:28` | `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js">` loaded globally | **Chart.js is already available** — 7.5/7.7 deferred charts to this pass and the library is in place |
| `templates/crm/analytics/dashboard/detail.html:59,77–94` | `<canvas id="wchart{{ w.pk }}">` + `{{ chart_configs\|json_script:"dash-charts" }}` + `new Chart(el, {...})` | The as-built **rendering contract** for widgets: server computes labels/data, ships them as a JSON script block, Chart.js draws. Reuse verbatim |
| `apps/*/models/SupplyChainAnalytics/{KpiTargets,KpiSnapshots}.py`, `procurement/SupplierKpis.py` | Target/threshold + snapshot rows exist in other modules | KPI *targets* are a known repo concept — but 7.16 carries `target_value` on the tile (crm precedent) instead of adding a fifth KPI table |
| CSV export | matched `text/csv` / `Content-Disposition` in `apps/accounting/views/CashManagement/BankTransactions.py`, `apps/procurement/views/DashboardPortal/SelfServiceReports.py`, `apps/crm/views/ActivityManagement/CalendarEvents.py` | CSV streaming is an established, dependency-free in-repo pattern — no new library |
| PDF | `apps/crm/views/FinanceBilling/PaymentReceipts.py:57`: *"Standalone printable receipt (browser print → PDF). Server-side PDF (weasyprint) deferred."* and `requirements.txt` has only `pdfplumber` (extraction, not generation) | **There is no server-side PDF generator in the repo.** PDF for 7.16 = a print-styled page; document it, do not silently add WeasyPrint |
| `apps/projects/` root | **no `analytics.py`, no `services.py`** (contrast: `crm`, `hrm`, `procurement`, `scm` all have `analytics.py`) | 7.16 authors the projects compute layer |
| `apps/projects/views/_helpers.py` | `org_units()`, `clients()`, `projects()`, `resource_profiles()`, `project_requests()`, `owners()`, `requirements()`, `critical_path_ids()` | Every dropdown the builder needs already exists tenant-scoped |
| Prefixes taken in this app | `DSH`=DocumentShare, `PRT`=Portfolio, `RSP`=ResourceProfile, `PDB`/`REP`/`RSN`/`RUN`/`WGT` **free** | `REP-` and `PDB-` are safe; do **not** reuse `DASH`/`RPT` shapes naively — `RPT` is not taken here but `PRT` is, and prefix drift across apps is how collisions happen |

**Prior research in this repo, not re-surveyed here:** `.claude/tasks/research-crm-analytics-reporting.md`
(Salesforce, HubSpot, Zoho Analytics, Pipedrive Insights, Dynamics 365, Zendesk Explore, monday, Insightly,
Copper, Freshsales — 11 leaders on the CRM reporting slice) already established report formats, widget types,
drill paths, historical snapshots and the scheduled-email pattern. This file does not repeat that evidence; it
cites it where a capability is domain-generic and spends its web effort on the **project/portfolio reporting**
slice. `.claude/tasks/research-projects-7.12.md` (rulings 1, 4) and `-7.15.md` (parked list) are the two
directly upstream files.

## Leaders surveyed (with source links)

Domain taken as **project/portfolio reporting, analytics, dashboards, custom report builders and BI-style
export** — not "best PM software".

1. **Smartsheet** — spreadsheet-work-management suite; its Advanced Reporting tier is the reference for "report over many sheets, then a dashboard on top" — [Advanced reports in Smartsheet](https://help.smartsheet.com/learning-track/reporting-resource-management/advanced-reports-smartsheet), [Advanced reporting learning track](https://help.smartsheet.com/learning-track/resource-management-best-practices/advanced-reporting), [AI dashboard builder](https://help.smartsheet.com/learning-track/ai-tools/ai-dashboard-builder)
2. **monday.com** — work-management platform whose dashboards are block/tile based; the "reporting block" model — [monday.com Dashboards](https://monday.com/features/dashboards), [Dashboard template guide](https://monday.com/blog/project-management/dashboard-template/), [Unlocking advanced reporting in monday.com](https://www.gb-advisors.com/blog/unlocking-advanced-reporting-in-monday-com-driving-better-decisions-with-real-time-data)
3. **Asana** — the portfolio/WorkGraph reporting model; richest published widget vocabulary — [How to use reporting dashboards in Asana](https://help.asana.com/s/article/reporting-with-dashboards), [Portfolio progress & reporting](https://help.asana.com/s/article/portfolio-progress-and-reporting), [The complete guide to Asana dashboards (BlinkMetrics)](https://blinkmetrics.com/asana-dashboard-guide/)
4. **Wrike** — enterprise PSA-style dashboards with interactive/table/gauge widgets and per-metric grouping — [Dashboards (Wrike Help Center)](https://help.wrike.com/hc/en-us/articles/22009910120471-Dashboards), [Gauge Widget in Dashboards](https://help.wrike.com/hc/en-us/articles/35459440520983-Gauge-Widget-in-Dashboards), [Reporting on User Attributes in Dashboards](https://help.wrike.com/hc/en-us/articles/24985711411863-Reporting-on-User-Attributes-in-Dashboards), [Drag-and-Drop](https://help.wrike.com/hc/en-us/articles/22009916622871-Drag-and-Drop)
5. **ClickUp** — dashboard *canvas* with advanced filtering and external-share-without-workspace-access — [ClickUp Dashboards](https://clickup.com/features/dashboards)
6. **Zoho Projects** — the clearest "50+ canned reports + drag-drop builder + scheduled email + CSV/Excel/PDF + embedded BI" bundle in one mid-market product — [Zoho Projects reporting tools](https://www.zoho.com/projects/zoho-reporting-tools.html), [Scheduled and automated report delivery from Zoho Projects](https://help.zoho.com/portal/nl/community/topic/scheduled-and-automated-report-delivery-from-zoho-projects)
7. **Teamwork.com** — **the best-documented guided builder data model in this survey** (pick entity → columns → filters → save → schedule) — [Reports Overview](https://support.teamwork.com/projects/reports/reports-overview), [Create a Custom Report](https://support.teamwork.com/projects/reports/create-a-custom-report), [View and Edit Custom Reports](https://support.teamwork.com/projects/reports/view-edit-custom-reports), [Scheduled Reports](https://support.teamwork.com/projects/reports/scheduling-reports)
8. **Planview PPM Express** — Power-BI-native portfolio reporting; the Executive/steering pack as a product, with RAG status by portfolio/program/project — [PPM Analytics & BI](https://www.ppm.express/ppm-analytics-and-bi), [PPM Express Executive Report Pack](https://ppmx.helpjuice.com/1055046-ppm-express-executives-report-pack), [PPM Express Portfolio Management Reports (Azure Marketplace)](https://marketplace.microsoft.com/en-hk/product/ppmexpresscorporation.ppm-express-potfolio-management-reports)
9. **Celoxis** — PMO suite whose differentiator is a custom report writer with formula fields — [Project Management Software with Custom KPIs & Reporting](https://www.celoxis.com/article/project-management-software-kpis-reporting)
10. **Kantata (Agiloft/Unanet-line PSA)** — scheduled dynamic dashboard emails, report exports and KPI alerts — [Schedule Dynamic Dashboard Emails, Report Exports, and KPI Alerts](https://knowledge.kantata.com/hc/en-us/articles/12008793655195-Schedule-Dynamic-Dashboard-Emails-Report-Exports-and-KPI-Alerts)
11. **Microsoft Project Online / PWA** — the "BI feed" reference: a dedicated reporting-data surface (OData) that external tools such as Power BI consume, incl. resource-demand paths — [Tune Project Online performance](https://learn.microsoft.com/en-us/projectonline/tune-project-online-performance), [OData Reporting in PWA (PPM Works)](https://ppmworks.com/odata-reporting-pwa/), [Project Online OData resource path for Resource Demand reporting](https://pwmather.wordpress.com/2016/11/22/projectonline-new-odata-resource-path-for-resource-demand-reporting-bi-o365-ppm/)
12. **Procore** — construction-PM reporting with per-report calculated columns and totals — [Create a Calculated Column in a 360 Report](https://v2.support.procore.com/product-manuals/reports-company/tutorials/create-a-calculated-column-in-a-360-report/)
13. **Leaplytics** (PPM advisory, read for *requirements*, not features) — what makes a steering-committee report trustworthy — [Your project portfolio report is open in every steering meeting and nobody trusts it](https://www.leaplytics.de/your-project-portfolio-report-is-open-in-every-steering-meeting-and-nobody-trusts-it/)
14. **In-repo prior art** — CRM 1.6's own survey (Salesforce, HubSpot, Zoho Analytics, Pipedrive, Dynamics 365, Zendesk Explore, monday, Insightly, Copper, Freshsales): [`.claude/tasks/research-crm-analytics-reporting.md`](../../.claude/tasks/research-crm-analytics-reporting.md). Plus the two shipped NavERP builders: `procurement.SpendReport` (6.14) and `crm.AnalyticsReport`/`AnalyticsDashboard` (1.6).

## Feature catalog (sub-module 7.16 only)

### Bullet 1 — Standard Project Reports ("status reports, risk registers, issue logs, and milestone summaries")

- **A canned report library, one row per saved report with a `report_type`** — Zoho ships *"50+ standard
  reports"*; Teamwork distinguishes *built-in* from *custom* reports; NavERP already does this in code
  (`crm.AnalyticsReport.report_type` with 4 canned types, `procurement.SpendReport` with a measure catalog).
  The unit is a *saved question*, not a table per report. · seen in: Zoho, Teamwork, Smartsheet, Celoxis,
  crm-1.6 (in-repo) · priority: **table-stakes** · spine: **new table `ProjectReport`** (`report_type` choices)
  · buildable now.
- **Status report = schedule + cost + risk + scope + quality on one page, auto-filled from the registers**
  — Celoxis documents the project status report as its headline output; Procore's 360/Dynamic reports assemble
  a formatted page from live project data. In NavERP every section is already a verified query: tasks
  (`percent_complete`, `planned_end` vs `actual_end`), milestones (`target_date` vs `actual_date`),
  `CostControlAccount.cpi/spi/eac/health` (read, not recomputed), `ProjectRisk.status`,
  `ProjectIssue.severity`, `QualityDefect.status`. · seen in: Celoxis, Procore, PWA/Power BI report packs,
  PPM Express · priority: **table-stakes** · spine: **no new table** — one computed page per canned type, all
  reading sibling models; the *issued* copy is `ProjectReportRun` · buildable now.
- **Risk register / issue log / milestone summary as a formatted, period-cut, printable export of a register
  that already exists** — 7.5 and 7.2 own the live registers; what 7.16 adds is the report *form* (frozen
  columns, as-of date, print stylesheet). NavERP 7.10 parked exactly this: *"Status-report and dashboard
  formats as generated reports → 7.16"*. · seen in: Celoxis, Procore, Zoho (report library), Teamwork ·
  priority: **table-stakes** · spine: **reuses 7.5 `ProjectRisk`/`ProjectIssue`, 7.2 `ProjectMilestone`**;
  print CSS, no chart dependency · buildable now.
- **Report section templates rather than one template per report** — Smartsheet's editor adjusts *"columns,
  filters, grouping and summaries"* on one report object; monday composes dashboards from blocks. Ten canned
  report types must render from **one run template + per-type section partials**, or the pass ships ten
  near-duplicate pages. · seen in: Smartsheet, monday, (in-repo) `templates/crm/analytics/report/detail.html` ·
  priority: **common** · spine: implementation convention, no table · buildable now.
- **As-of / cutoff discipline on every standard report** — Leaplytics: trustworthy packs *"read directly from
  standardized Friday cutoffs"*; Teamwork's builder caps the range at two years; Smartsheet advanced reports
  refresh *"daily or manually"*. Every 7.16 figure must state the date it was true on. · seen in: Teamwork,
  Smartsheet, Leaplytics · priority: **common** · spine: `ProjectReport.date_*` + `ProjectReportRun.as_of`
  · buildable now.
- **Variance and trend columns, not just current values** — Procore and Sage Intacct both expose per-report
  calculated columns/totals; NavERP's in-repo answer is procurement's ratio measures (`maverick_pct`,
  `classified_pct`, `avg_transaction`). For projects the equivalents are frozen measure keys: `cv_pct`,
  `sv_pct`, `variance_days`, `on_time_pct`, `overdue_count`, `aging_days`. · seen in: Procore, Celoxis (formula
  fields), Sage Intacct CRW, `procurement` (in-repo) · priority: **common** · spine: **new measure keys in
  `apps/projects/analytics.py`**, no expression engine · buildable now.

### Bullet 2 — Custom Report Builder ("drag-and-drop fields, filters, grouping, and calculated columns")

- **Guided builder over frozen axes, not a free expression engine** — Teamwork: *"Choose entity: user, project,
  task, or milestone. Add columns, filters (is, contains, etc.), date ranges up to two years."* NavERP 6.14
  ruled the same way for a reason: dropdown axes make a saved report **auditable in one glance**, and a free
  parser is a SQL-injection surface plus a support burden. · seen in: Teamwork, Zoho, Celoxis, Smartsheet,
  `procurement.SpendReport` (in-repo) · priority: **table-stakes** · spine: **new table `ProjectReport`** with
  `SUBJECT_CHOICES`, `MEASURE_CHOICES`, `DIMENSION_CHOICES` · buildable now.
- **Up to two group-by dimensions with a "none" option** — `procurement.SpendReport.dimension_1/dimension_2`
  (as-built, plus the `clean()` rule that two identical axes are a bug) and Asana's *"group by status,
  section, assignee, or custom fields"*. For projects the axes are real columns: `project`, `portfolio`,
  `client` (`core.Party`), `org_unit`, `project_manager`, `resource`, `status`, `priority`, `severity`,
  `risk_category`, `activity_code`, `billing_type`, `methodology`, `month`, `quarter`, `wbs_phase`. · seen in:
  procurement (in-repo), Asana, Smartsheet, Teamwork · priority: **table-stakes** · spine: reads sibling
  columns · buildable now.
- **Measure list with an explicit denominator caveat per measure** — procurement's `uses_department_axis`
  property (as-built) prints a caveat when a 3-hop nullable axis is used. The project analogue: `utilization`
  divides `ResourceTimeEntry.hours` by `ResourceAllocation.planned_hours(win_start, win_end)`, and an
  unallocated resource has **no denominator** — the report must say "(unassigned)" rather than divide by zero. ·
  seen in: `procurement` (in-repo), Teamwork (Utilization report) · priority: **common** · spine: **reuses
  `ResourceAllocation.planned_hours`, `ResourceTimeEntry.week_key`** · buildable now.
- **Scope narrowing by tenant-checked FKs** — `SpendReport` carries four nullable scope FKs and re-validates
  each FK's tenant in `clean()` because *"a narrowed <select> is UX, not an authorization boundary"*. 7.16
  copies this **exactly**: `project`, `portfolio`, `client` (`core.Party`), `org_unit` (`core.OrgUnit`). ·
  seen in: procurement (in-repo) · priority: **table-stakes** · spine: FKs by string · buildable now.
- **Top-N with a visible tail** — `SpendReport.top_n` (1–100, validated) is the in-repo precedent for
  "long-tail of suppliers/categories". Same for projects (Top 20 projects by cost variance). · seen in:
  procurement (in-repo), Salesforce/HubSpot (via CRM 1.6 research) · priority: **common** · buildable now.
- **Calculated columns** — Procore documents per-report calculated columns; Celoxis markets formula fields.
  **Honest NavERP mapping:** a fixed vocabulary of derived measures (ratios, per-day rates, variance %, aging
  days) computed in `analytics.py`, **not** a user-authored formula parser — the repo has no expression
  sandbox, and 7.19 (*Custom Fields & Forms*) owns dynamic schema. · seen in: Procore, Celoxis, Sage Intacct ·
  priority: **differentiator** · spine: measure registry · **partial now; true formula builder deferred
  (7.19 / later)**.
- **Save / share / favorite the built report** — Teamwork: *"Share view-only; save to Custom Reports."*
  ClickUp: *"Share dashboards without sharing your workspace"* with granular permissions. In-repo:
  `SpendReport.is_shared`/`is_favorite`, `AnalyticsReport.is_favorite`. · seen in: Teamwork, ClickUp, monday,
  in-repo ×2 · priority: **table-stakes** · spine: `ProjectReport` columns · buildable now.

### Bullet 3 — Real-Time Dashboards & Widgets ("KPI cards, trend charts, and personalized home screens")

- **Widget = one metric key + one chart type + one window, validated as a pair** — the crm `DashboardWidget`
  contract, as built: *"`metric` selects a read-only aggregation (see `analytics.WIDGET_METRICS`);
  `chart_type` chooses how to render it (the form's `clean()` enforces a chart that the metric supports)"*.
  That form-level pairing is what stops a gauge asking for a multi-series series. · seen in: crm 1.6
  (in-repo), Wrike (gauge/table widgets), monday, Asana · priority: **table-stakes** · spine: **new table
  `DashboardWidget`** · buildable now.
- **KPI card / number tile with progress-to-target** — `DashboardWidget.target_value` (in-repo), Wrike's gauge,
  monday's counter, Asana's *number* chart, Kantata's KPI alerts. · priority: **table-stakes** · buildable now.
- **Chart vocabulary the products actually ship:** bar/column (all), line & area (all), pie/doughnut (Asana
  donut, crm doughnut), **burn-up/burndown** (Asana names it explicitly; NavERP 7.13 already computes
  velocity), **workload/time-tracking tiles** (ClickUp *"charts, tables, workloads, time tracking, and
  calculations into a single canvas"*), lollipop (Asana), table (Wrike, crm), progress/battery (monday), Gantt
  view block (monday — park: 7.8 owns the Gantt page), scatter/funnel (from CRM 1.6 research). ·
  priority: **table-stakes for bar/line/pie/kpi/table, common for gauge/progress, differentiator for
  lollipop/heat-strip** · spine: `templates/base.html:28` Chart.js 4.4.1 + the `json_script` → `new Chart()`
  contract from `templates/crm/analytics/dashboard/detail.html:77–94` · buildable now.
- **Live data, computed at request time — no overnight cache** — ClickUp: *"Always current. Always synced. No
  manual refresh needed."* Smartsheet's advanced reports refresh daily or manually (a weaker guarantee);
  PPM Express sells *"real-time data"*. For a Django ERP over one DB, live ORM aggregation **is** the answer;
  a cache table would be the stale-data bug 7.12 ruled out. · seen in: ClickUp, PPM Express, Kantata,
  in-repo crm · priority: **table-stakes** · spine: `analytics.py` functions · buildable now.
- **Personalized home: an `is_default` dashboard per user + audience templates** — Dynamics 365 ships
  role-specific dashboards, crm has `is_default`/`is_shared`/`owner` as-built, Zoho and monday ship template
  galleries. For projects the audiences are real personas: PM, resource manager, PMO/executive, finance,
  delivery lead/agile team. · seen in: crm (in-repo), Dynamics, monday, Zoho, ClickUp ("pre-built templates for
  sprint tracking, client reporting, or team workload") · priority: **table-stakes** · spine: **new table
  `ProjectDashboard`** (`audience`, `is_default`, `is_shared`, `layout`) · buildable now (the tile landing
  inside `apps/dashboard`'s global home is deferred — cross-app).
- **Grid position + size persisted even though drag-drop JS is deferred** — crm stores `position` +
  `size` (`small|medium|large|full`) today; HubSpot/Pipedrive/monday offer true drag-drop. Persist the layout,
  defer the JS: that is the exact ruling 1.6 recorded ("store grid positions but defer the live JS builder"). ·
  priority: **common** · buildable now (data) / **later** (JS).
- **Drill-down from every tile to the filtered register** — Insightly "drill paths", Dynamics visual filters,
  PPM Express *"drill-down analytics"*. In NavERP this is nearly free: `analytics.py` declares
  `drill_url_name` + query params per metric and the target list pages already accept `project`/`status`/
  `q` filters (7.5, 7.8, 7.11 registers). · seen in: Insightly, Dynamics, PPM Express (also CRM 1.6 research) ·
  priority: **common** · spine: **reuses existing sibling url names** · buildable now.
- **Dashboard-level filter window (one date range for all tiles)** — ClickUp's *"advanced filtering… by owner,
  status, date, or any custom field"*; Wrike's dashboard reporting on user attributes. In-repo: crm
  `ANALYTICS_RANGE_CHOICES` shared by reports and widgets so one vocabulary serves both. · priority:
  **table-stakes** · spine: shared `_choices.py` range list · buildable now.
- **Heat map of project health across a portfolio as a tile type** — 7.12 already computes the portfolio heat
  map at `pfm_dashboard`; NavERP 7.1's research pushed bubble/matrix visuals to 7.16. Ship the tile as
  **bands over the same derivation** and deep-link to `pfm_dashboard`, rather than a second health engine. ·
  seen in: PPM Express ("Portfolios by Overall Status"), monday, 7.12 (in-repo) · priority: **differentiator** ·
  spine: **read `PortfolioInvestment` scores + `CostControlAccount.health` + `Project.status`** · buildable now.

### Bullet 4 — Executive & Steering Committee Packs ("high-level summaries, RAG status, and strategic narrative generation")

- **An executive pack is a *report run that has been issued*, not a new object** — PPM Express's Executive
  Report Pack is a set of Power BI views (portfolio → program → project) over one dataset, not a per-meeting
  table. NavERP 7.12 already ruled the pack is *"a computed page… 7.16 Reporting owns persisted report
  snapshots if a later pass wants one."* The durable artifact 7.16 needs is therefore
  **`ProjectReportRun` with a `status: draft → issued`** and a frozen payload. · seen in: PPM Express,
  in-repo 7.12 ruling · priority: **common** · buildable now.
- **RAG must carry *persistence*, not just the current letter** — Leaplytics: a report people trust shows
  *"whether a project just turned amber or has been amber for six weeks"*. That is only derivable from a
  **series of frozen runs** (weeks in amber = count of consecutive runs with the same rating), never from a
  live query. This single requirement is the strongest justification for a snapshot table in a read-light
  module, and it is why "just compute it live" is not enough for bullet 4. · seen in: Leaplytics, PPM Express,
  monday (AI proactive insights) · priority: **differentiator** · spine: `ProjectReportRun` series +
  `analytics.py` streak computation · buildable now.
- **Executive view and operational detail deliberately separated** — Leaplytics: *"Executive views separate
  from operational detail; one-pagers need no clicking."* PPM Express's pack ships portfolio-level views with
  drill-down behind them. NavERP mapping: the pack page renders summary bands + narrative only; each band
  deep-links to the sibling register. · priority: **common** · buildable now.
- **Strategic narrative attached to the frozen numbers, authored before issue** — monday markets *AI
  "executive summary reports"* and "proactive insights"; PPM Express markets *"AI narrative status reporting"*.
  **No LLM infrastructure exists in this repo** (and the 7.1 pass already recorded that as a reason to defer
  AI re-scoring). The buildable-now version is a **`narrative` text field on the run**, pre-filled from
  templates/registers (e.g. a `KnowledgeEntry` lessons-learned reference, open `IssueEscalation` rows), edited
  by a human, then locked at issue. · seen in: monday, PPM Express · priority: **differentiator** · spine:
  **text field on the run + seed-from-existing-registers helper** · **buildable now; AI generation deferred**.
- **Standardised submission so cross-project comparison is honest** — Leaplytics: *"All projects use identical
  status submission processes and definitions."* NavERP's equivalent guarantee is structural, not process:
  every figure in a pack comes from the **same frozen measure keys** in `analytics.py`, so two PMs' "amber"
  cannot mean different queries. Document it as the reason the metric registry is code. · priority:
  **common** · spine: metric registry convention (in-repo crm `WIDGET_METRICS`) · buildable now.
- **File the issued pack into the document repository** — NavERP 7.10 ships `DocumentTemplate` with
  `category = report | status_update` and 7.10's research parked the *format* question here. An issued run
  should be attachable to `core.Document` (verified) and surface on the project's 7.10 repository — this is
  the write 7.16 legitimately makes. · priority: **common** · spine: **reuses `core.Document`,
  `projects.ProjectDocument`, `DocumentTemplate`** · buildable now.
- **Recurring distribution to a steering list (email/PPT)** — Kantata: *"schedule dynamic dashboard emails,
  report exports and KPI alerts"*; Teamwork: cadence *"day, week, month, or custom interval"* + recipients +
  *"CSV, Excel, PDF"*; Zoho and monday both ship scheduled email. **Repo reality: no mail worker and no
  scheduler** (recorded at 7.1: *"No mail worker and no scheduler… the reminder/notification engine is
  7.17's"*; the same limitation is logged for procurement 6.8/6.19). NavERP's `accounting.ScheduledReport`
  is the precedent for the shape: **configuration rows whose delivery worker was explicitly deferred**. ·
  priority: **table-stakes commercially, integration/later here** · spine: park the cadence/recipient model →
  **7.17**; ship a manual "Freeze & issue" POST now (optionally a management command an admin can cron).

### Bullet 5 — Data Export & API Connectivity ("CSV, Excel, PDF exports, and OData/REST feeds to external BI tools")

- **CSV download of any saved report's live result** — Zoho: *"CSV/Excel/PDF exports"*; Teamwork: formats
  *"CSV, Excel, PDF"*; Kantata: *"report exports"*. In-repo this is already a solved, dependency-free pattern
  (`accounting` bank-transaction export, `procurement` self-service reports, `crm` calendar events all match
  `text/csv`). · priority: **table-stakes** · spine: no model — a streaming view over the computed payload ·
  buildable now.
- **Print-styled PDF (browser print), not server-side PDF** — `crm.PaymentReceipts`: *"Standalone printable
  receipt (browser print → PDF). Server-side PDF (weasyprint) deferred"*, and `requirements.txt` carries only
  `pdfplumber` (extraction). Ship a print stylesheet on the run/exec-pack page and say so in the docstring;
  adding a PDF engine is a dependency decision, not this pass's. · priority: **common** · **buildable now
  (print) / later (true PDF)**.
- **Excel (.xlsx) export** — commercially table-stakes (Zoho, Teamwork); **`openpyxl` is not in
  requirements.txt**. Deferred: CSV opens in Excel and the multi-axis payload is tabular anyway. ·
  priority: **common commercially, deferred here** · integration/later.
- **A read-only JSON endpoint per saved report — the machine-readable face of the same payload** — ClickUp's
  always-current tiles already require it; a BI tool wants the same shape. In-repo: `crm`'s dashboards already
  ship a `json_script` payload, and `apps/core/views/Search.py` uses `JsonResponse`. **No new model** —
  one authenticated endpoint returning `{summary, columns, rows, chart_*}` for a tenant-scoped report. This is
  also what makes the future external feed cheap. · priority: **common** · buildable now.
- **An OData / Power-BI-consumable external feed** — PWA is the market reference: a dedicated Project
  Reporting OData surface (incl. resource-demand paths) that Power BI consumes; PPM Express ships **Power BI
  datasets**; Zoho projects its data into **Zoho Analytics**. For NavERP this is *tokenised, cross-tenant-safe,
  versioned* API work and Module 7's own **7.18 Integration & API Hub** owns the endpoint/credential/message
  machinery (the `apps/core/navigation.py` comment block at lines ~1952–1959 describes `IntegrationMessage` /
  `WebhookDelivery` / an exceptions cockpit as that pattern). · priority: **differentiator** ·
  **parked → 7.18**; 7.16 only guarantees its payload is JSON-clean and serialisable (the procurement rule:
  *"every value `compute_report` returns must be JSON-serialisable; the analytics layer owns that contract"*).
- **Export/extract audit trail** — in an ERP, *who pulled which slice of project financials* is a governance
  question answered without a new table: tenant `AuditLog` (verified `core.AuditLog`) on every CSV/JSON run,
  the same way 7.1 recorded decisions *"land… in `core.AuditLog`"*. **Deliberate rejection of a fifth
  `ReportExportLog` model** — it would duplicate an audit table the spine already has. · priority: **common** ·
  spine: **reuses `core.AuditLog`** · buildable now.

### Beyond the bullets

- **Reports read, never write money** — the hard constraint from `apps/accounting` owning the ledger (L29):
  7.16 must not add balances, re-derive EVM, or post anything. `CostControlAccount.cpi/spi/eac/health` are
  **read**; `ProjectExpense`/`ProjectBillingRun`/`ProjectRevenueSchedule` are **aggregated**; nothing here
  writes `accounting.*`. procurement states the same rule for its own report builder ("this sub-module writes
  NOTHING to `accounting.*`… and stores no balance of its own").
- **The metric registry lives in code, not in a table** — the in-repo convention (`crm.analytics.WIDGET_METRICS`
  keyed identically to `WIDGET_METRIC_CHOICES`, `procurement.analytics.compute_report`, `hrm`/`scm`
  equivalents). A "metrics table" would look like a semantic layer but would silently break the
  form/chart-compatibility validation and the tenant-scoping guarantees. **A staff engineer rejects a
  `MetricDefinition` model here; the frozen `*_CHOICES` + registry dict IS the definition layer.**
- **One-way import edge** — `analytics.py` imports models; models never import analytics (verbatim from the
  6.14 docstring). Preserve it.
- **Ordering tie-breakers on every timestamp-ordered list** — `SpendReportSnapshot.Meta.ordering =
  ["-generated_at", "-id"]` exists because two runs in one clock tick make "latest" flip between renders.
  Copy it onto the run table.
- **Cross-app / tenant-wide analytics** (one report spanning CRM + projects + accounting) is a real category in
  the surveyed BI slice (Zoho Analytics, Power BI datasets, Metabase-style semantic layers) but is **not** the
  repo's convention: each module owns its own `analytics.py` today, and NavERP's sidebar maps bullets to
  pages, not to a warehouse. → Deferred.

## Recommended build scope (this pass — 4 models + 1 compute layer + computed pages)

**Why exactly four, and why not more.** The pass is deliberately **write-light**: bullets 1, 3 and 5 are
satisfied mostly by pages and endpoints. A model earns its migration only if it stores something the rest of
the system cannot recompute — which is true of (a) a *saved question*, (b) a *frozen answer*, (c) a *dashboard
container*, (d) a *widget tile*. Everything else is a query.

### Model 1: `ProjectReport` [REP-] — the saved question (bullets 1 + 2)
`TenantNumbered`, `NUMBER_PREFIX = "REP"` (verified free in this app; `PRT` is Portfolio, `DSH` is
DocumentShare). Shaped directly on the as-built `procurement.SpendReport`.
- `name`, `description`, `owner` (SET_NULL User), `is_favorite`, `is_shared`, `last_run_at` (system-stamped on
  run/freeze **only**, never on opening the page — both in-repo precedents stamp this way)
- `report_type` — the standard-report library: `status_report`, `milestone_summary`, `schedule_variance`,
  `risk_register`, `issue_log`, `quality_defect_summary`, `scope_change_summary`, `cost_variance`,
  `earned_value`, `resource_utilization`, `time_entry`, `billing_summary`, `agile_throughput`,
  `portfolio_health`, `steering_pack`, `custom` (every one maps to verified sibling fields above)
- `subject` (which register the builder starts from: `project`/`task`/`milestone`/`risk`/`issue`/`defect`/
  `requirement`/`scope_change`/`time_entry`/`allocation`/`expense`/`budget_line`/`billing_run`/
  `revenue_schedule`/`sprint`/`investment`) — the Teamwork "choose entity" step
- `measures` — **JSONField list, 1–3 keys** from a frozen `MEASURE_CHOICES` (counts, hours, money, and the
  *ratio/variance/aging* keys that stand in for "calculated columns": `cv`, `sv`, `cv_pct`, `sv_pct`,
  `cpi`, `spi`, `eac`, `on_time_pct`, `slip_days`, `utilization_pct`, `billable_pct`, `exposure_value`,
  `open_count`, `aging_days`, `unbilled_amount`)
- `dimension_1`, `dimension_2` (`none` allowed, identical-pair rejected in `clean()`)
- `date_range` + `date_from`/`date_to` + `as_of` (window ≤ 730 days, mirroring Teamwork's two-year cap)
- scope FKs, all SET_NULL + tenant-revalidated in `clean()`: `project` → `projects.Project`,
  `portfolio` → `projects.Portfolio`, `client` → `core.Party`, `org_unit` → `core.OrgUnit`
- `chart_type` (`kpi`/`bar`/`line`/`pie`/`doughnut`/`gauge`/`table`/`heat`), `top_n` (1–100), `sort_by`
- `clean()`: measures ⊆ registry keys and each supports the chosen chart; window required unless `all`;
  `as_of` inside window; FK-tenant check on all four scope FKs; `metric`/`chart` compatibility pair rule from crm
- **No money, no percentage, no count column on this table.** The row holds the question.

### Model 2: `ProjectReportRun` (unnumbered child) — the frozen answer (bullets 1, 4, and the trend requirement)
Plain `models.Model` with its own `tenant` FK + `generated_at` (verbatim `crm.ReportSnapshot` /
`procurement.SpendReportSnapshot` shape — *"a snapshot is written once and never edited"*).
- `report` FK → `ProjectReport` (`related_name="runs"`), `title`, `period_from`, `period_to`, `as_of`
- `summary` JSON (KPI cards), `data` JSON (`{columns, rows, chart_type, chart_labels, chart_data}`), `row_count`
- **`narrative` TextField** — the steering-pack commentary, authored pre-issue (the honest, no-LLM version of
  monday/PPM Express "AI narrative")
- `status` (`draft` → `issued` → `archived`), `issued_by`, `issued_at` (verb-written only, the 7.1 verb
  pattern); `document` FK → `core.Document` nullable (set when the issued pack is filed to 7.10's repository
  against a `DocumentTemplate` of category `report`/`status_update`)
- `generated_by`, `generated_at`; `Meta.ordering = ["-generated_at", "-id"]` (tie-breaker ruling)
- **No create/edit/delete view and no form.** Rows appear only from the `report_freeze` POST; the only later
  writes are narrative + the `issue` verb.
- **Why this table is not a duplicated query:** it is the *only* place 7.16 can compute "amber for six weeks"
  (Leaplytics), period-over-period EVM history (7.4's deferred `EACSnapshot` need — answered by the run series
  instead of a fifth model), and "what exactly did we tell the steering committee on 12 September".

### Model 3: `ProjectDashboard` [PDB-] — the container (bullet 3)
`TenantNumbered`, `NUMBER_PREFIX = "PDB"` (`DSH` is taken by `DocumentShare`).
- `name`, `description`, `owner` (null = tenant-provided), `is_default` (the personalized home),
  `is_shared`, `audience` (`pm`/`resource_manager`/`finance`/`quality`/`agile_team`/`executive`/`portfolio`),
  `layout` (`one`/`two`/`three` — reuse the crm vocabulary), `default_range`, `project`/`portfolio` nullable
  scope FKs, `position`/`sequence` not needed here
- derived `widget_count` property; indexes on `(tenant, owner)` and `(tenant, is_shared)`

### Model 4: `DashboardWidget` (unnumbered child) — the tile
`models.Model` + own `tenant`, on `ProjectDashboard` (`related_name="widgets"`), verbatim crm shape plus scope:
`title`, `metric` (frozen `WIDGET_METRIC_CHOICES` mirroring `analytics.WIDGET_METRICS` keys), `chart_type`,
`date_range`, `size` (`small`/`medium`/`large`/`full`), `position`, `target_value` (KPI/gauge goal),
`project`/`portfolio` nullable scope FKs, created/updated. `clean()` enforces that the metric supports the
chart (crm's rule) and that scope FKs belong to the tenant.

### The compute layer: `apps/projects/analytics.py` (NEW FILE, zero tables) — the real substance of 7.16
Mirrors `apps/crm/analytics.py` (471 lines, `_r_*` functions keyed to `WIDGET_METRIC_CHOICES`) and
`apps/procurement/analytics.compute_report`. Must provide: `range_bounds()`, `as_of` resolution, the widget
registry (label, allowed charts, drill url + params, compute fn), `compute_report(report) ->
{summary, columns, rows, chart_*}` returning **only JSON-serialisable values**, and the ratio/variance/aging
derived measures. **All reads.** Every EVM figure is taken from
`CostControlAccount.pv/ev/ac/cv/sv/cpi/spi/eac/health` (verified properties, `@property` at
`apps/projects/models/CostManagement/CostControlAccounts.py:104–232`); every utilization denominator from
`ResourceAllocation.planned_hours(win_start, win_end)`; every week bucket from `ResourceTimeEntry.week_key`.

### Computed pages / endpoints (no model)
- One report-run template family + per-type section partials rendering the 16 canned `report_type` values
  (never ten copies of a page).
- `projects:dash_home` (the `is_default` dashboard), `projects:dash_detail`, widget add/edit/delete under
  `ProjectDashboard`'s folder.
- `projects:report_csv` (streaming CSV, in-repo precedent) and `projects:report_json` (the read-only payload
  feed) — both tenant-scoped, both writing a `core.AuditLog` row.
- `projects:exec_pack` — the issued `steering_pack` run rendered one-pager-style with print CSS.
- Chart rendering via the existing global Chart.js 4.4.1 (`templates/base.html:28`) and the
  `{{ chart_configs|json_script }}` → `new Chart()` contract from
  `templates/crm/analytics/dashboard/detail.html:77–94`. This is the pass 7.5/7.7 were told to wait for.

**Structure for the todo/contract steps:** backend `apps/projects/{models,forms,views,urls}/ReportingBusinessIntelligence/{ProjectReports,ReportRuns,ProjectDashboards,DashboardWidgets}.py`
(PascalCase sub-module folder, four layers line up); templates `templates/projects/reporting/{report,report_run,dashboard,widget}/{list,detail,form}.html`
+ `reporting/`-root standalone pages (`exec_pack.html`, `home.html`); one `LIVE_LINKS["7.16"]` entry mapping the
five bullets; seeder extension seeding 1–2 audience dashboards + widgets + 2–3 saved reports per tenant
(idempotent, no snapshot seeding — a frozen run must be *issued* by a human).

## Belongs to sibling sub-modules (parked, not scoped here)

- **Scheduled delivery engine, digests, cadence/recipient config, KPI threshold alerts** → **7.17 Workflow &
  Automation** (no scheduler or mail worker exists; 7.1's note and `accounting.ScheduledReport`'s deferred
  worker are the evidence). 7.16 exposes `target_value` + frozen metric keys so 7.17 can consume them.
- **Client/external-facing report sharing and portal downloads** → **7.14** (`ClientPortalAccess` owns
  external visibility; ClickUp/Asana-style "share without workspace access" is a tokenised external surface,
  not this pass).
- **Tokenised external feeds, OData/REST endpoint management, Power BI/Metabase connection config, webhooks**
  → **7.18 Integration & API Hub** (endpoints, credentials, `IntegrationMessage`, delivery logs).
- **Portfolio heat maps, investment scoring, program rollups** → **7.12** (`pfm_dashboard`). 7.16 links to it
  and re-reads its derivation; it does not build a second health engine.
- **EVM maths, budget revisions, cost variance ownership** → **7.4** (`CostControlAccount` properties).
  **Billing, A/R aging, cash-flow boards** → **7.15** (`financial_pnl`, `ar_aging`, `cash_flow_forecast`).
  **Velocity/burndown** → **7.13** (`velocity_report`). **Utilization** → **7.11**
  (`utilization_dashboard`). **Risk exposure analytics** → **7.5** (`risk_analysis`). **Quality review
  variance** → **7.6** (`qrv_report`). **Gantt/timeline** → **7.8**. 7.16 surfaces and exports them.
- **A second ledger, stored balances, money writes** → **Module 2 `apps/accounting`** (L29). Never here.
- **Custom fields / dynamic entity schema that a true formula builder would need** → **7.19 Master Data &
  Configuration**; **report/document format authoring, locking and merge fields** → **7.10** + **Module 13**.
- **Chart-library procurement / a new frontend dependency** → not needed; Chart.js is already global.

## Deferred (later passes / integrations)

| Deferred | Why |
|---|---|
| **True drag-and-drop grid builder** (sortable, resize handles) | Asana/monday/HubSpot/ClickUp all have it; `position` + `size` are stored from day one so the JS is additive — the identical ruling 1.6 recorded. |
| **User-authored formula / calculated-column expressions** (Procore, Celoxis) | No expression sandbox in the repo; a parser over a multi-tenant queryset is an injection and performance surface. The frozen derived-measure registry answers the same need. Revisit with 7.19 custom fields. |
| **Server-side PDF generation** (report PDFs, packs) | `requirements.txt` has no PDF writer; the repo pattern is browser print → PDF (`crm.PaymentReceipts:57`). Add deliberately with the owning pass that needs real distribution. |
| **Native Excel (.xlsx) export** | `openpyxl` absent; CSV covers it. |
| **AI narrative / natural-language report building** (monday AI exec summary, PPM Express AI narrative status, HubSpot Breeze, Pipedrive AI, Salesforce Einstein, Zoho Ask Zia) | No LLM infrastructure in NavERP; the narrative field + template pre-fill is the honest buildable-now slice. |
| **Nightly auto-snapshot / scheduled freeze command** | Needs the 7.17 scheduler. Manual "Freeze run" POST ships now; a management command an operator can cron is a 1-line follow-up. |
| **`MetricDefinition` / semantic-layer table** | Rejected on purpose. The frozen `*_CHOICES` + `analytics.WIDGET_METRICS` registry is the in-repo definition layer and it is what keeps the metric↔chart validation and tenant scoping honest. |
| **`EACSnapshot` / period-EVM table** (7.4's explicitly deferred item) | Answered by the `ProjectReportRun` series for period-over-period trend without a dedicated table; add only if a tenant needs machine-readable period EVM curves. |
| **Pivot / cross-tab with >2 axes** | `dimension_1`/`dimension_2` mirrors procurement's shipped limit; a true N-axis pivot needs a different payload contract. |
| **Cross-module tenant-wide analytics** (one report spanning CRM + projects + SCM + accounting) | Every module owns its own `analytics.py` today; a warehouse-style layer is an architecture decision above one sub-module. |
| **Cache/materialised aggregate tables for report speed** | Premature; live ORM aggregation over indexed `(tenant, …)` FKs is the shipped convention. Revisit only if a specific board measures slow. |
| **Tiles embedded in the Module 0 global dashboard home** (`templates/dashboard/home.html`) | Cross-app wiring; 7.16 ships `projects:dash_home` first. |

## Sources

Product/feature pages and help documentation read:

- Smartsheet — [Advanced reports in Smartsheet](https://help.smartsheet.com/learning-track/reporting-resource-management/advanced-reports-smartsheet), [Advanced reporting (learning track)](https://help.smartsheet.com/learning-track/resource-management-best-practices/advanced-reporting), [Build dashboards using AI](https://help.smartsheet.com/learning-track/ai-tools/ai-dashboard-builder), [Platform features](https://www.smartsheet.com/platform/features)
- monday.com — [Dashboards](https://monday.com/features/dashboards), [Dashboard template guide](https://monday.com/blog/project-management/dashboard-template/), [KPI software platforms](https://monday.com/blog/project-management/kpi-dashboard/), [Unlocking advanced reporting in monday.com](https://www.gb-advisors.com/blog/unlocking-advanced-reporting-in-monday-com-driving-better-decisions-with-real-time-data)
- Asana — [How to use reporting dashboards in Asana](https://help.asana.com/s/article/reporting-with-dashboards), [Portfolio progress & reporting](https://help.asana.com/s/article/portfolio-progress-and-reporting), [The complete guide to Asana dashboards (2026) — BlinkMetrics](https://blinkmetrics.com/asana-dashboard-guide/), [Asana Dashboard: key features, pros and cons](https://www.projectmanager.com/blog/asana-dashboard)
- Wrike — [Dashboards](https://help.wrike.com/hc/en-us/articles/22009910120471-Dashboards), [Gauge widget in dashboards](https://help.wrike.com/hc/en-us/articles/35459440520983-Gauge-Widget-in-Dashboards), [Reporting on user attributes in dashboards](https://help.wrike.com/hc/en-us/articles/24985711411863-Reporting-on-User-Attributes-in-Dashboards), [Drag-and-drop](https://help.wrike.com/hc/en-us/articles/22009916622871-Drag-and-Drop)
- ClickUp — [Dashboards](https://clickup.com/features/dashboards)
- Zoho Projects — [Project reporting tools](https://www.zoho.com/projects/zoho-reporting-tools.html), [Scheduled and automated report delivery](https://help.zoho.com/portal/nl/community/topic/scheduled-and-automated-report-delivery-from-zoho-projects), [Zoho Analytics — emailing reports and dashboards](https://www.zoho.com/analytics/help/export/email.html)
- Teamwork.com — [Reports overview](https://support.teamwork.com/projects/reports/reports-overview), [Create a custom report](https://support.teamwork.com/projects/reports/create-a-custom-report), [View and edit custom reports](https://support.teamwork.com/projects/reports/view-edit-custom-reports), [Scheduled reports](https://support.teamwork.com/projects/reports/scheduling-reports), [Custom reports guide](https://www.teamwork.com/academy/custom-reports-guide/)
- Planview PPM Express — [PPM Analytics & BI](https://www.ppm.express/ppm-analytics-and-bi), [Executive Report Pack](https://ppmx.helpjuice.com/1055046-ppm-express-executives-report-pack), [Portfolio Management Reports (Microsoft Marketplace)](https://marketplace.microsoft.com/en-hk/product/ppmexpresscorporation.ppm-express-potfolio-management-reports)
- Celoxis — [Project management software with custom KPIs & reporting](https://www.celoxis.com/article/project-management-software-kpis-reporting)
- Kantata — [Schedule dynamic dashboard emails, report exports and KPI alerts](https://knowledge.kantata.com/hc/en-us/articles/12008793655195-Schedule-Dynamic-Dashboard-Emails-Report-Exports-and-KPI-Alerts)
- Microsoft Project Online / PWA — [Tune Project Online performance](https://learn.microsoft.com/en-us/projectonline/tune-project-online-performance), [OData reporting in PWA — PPM Works](https://ppmworks.com/odata-reporting-pwa/), [Project Online OData resource path for Resource Demand — pmMather](https://pwmather.wordpress.com/2016/11/22/projectonline-new-odata-resource-path-for-resource-demand-reporting-bi-o365-ppm/)
- Procore — [Create a calculated column in a 360 report](https://v2.support.procore.com/product-manuals/reports-company/tutorials/create-a-calculated-column-in-a-360-report/); Sage Intacct — [Add column totals (Custom Report Wizard)](https://www.intacct.com/ia/docs/en_ZA/help_action/Reporting/Custom_reports/Custom_Report_Wizard/Define_columns/5-add-column-totals.htm)
- Leaplytics — [Your project portfolio report is open in every steering meeting and nobody trusts it](https://www.leaplytics.de/your-project-portfolio-report-is-open-in-every-steering-meeting-and-nobody-trusts-it/)
- Comparison context — [Productive: top project dashboard software](https://productive.io/blog/project-dashboard-software/), [Fanruan: project reporting tools compared](https://www.fanruan.com/en/blog/best-project-reporting-software-tools), [Amoeboids: best reporting tools 2026](https://amoeboids.com/blog/best-reporting-tools-2026-comparison/), [Teamwork: best reporting tools](https://www.teamwork.com/blog/reporting-tools/)

In-repo evidence cited inline above: `apps/core/navigation.py` (LIVE_LINKS 7.1–7.15, lines 1704–1940),
`apps/crm/models/AnalyticsReporting/{Dashboards,Reports,Widgets,Snapshots,_choices}.py`,
`apps/crm/analytics.py`, `apps/procurement/models/SpendAnalyticsReporting/SpendReports.py`,
`apps/scm/models/SupplyChainAnalytics/{KpiTargets,KpiSnapshots}.py`,
`apps/accounting/models/Reporting/ScheduledReports.py`,
`apps/projects/models/CostManagement/CostControlAccounts.py`,
`apps/projects/models/ResourceManagement/{ResourceAllocations,ResourceTimeEntries}.py`,
`apps/projects/models/DocumentKnowledgeManagement/Templates.py`, `apps/projects/views/_helpers.py`,
`templates/base.html`, `templates/crm/analytics/dashboard/detail.html`, `requirements.txt`,
`.claude/tasks/research-crm-analytics-reporting.md`, `.claude/tasks/research-projects-{7.1,7.4,7.5,7.10,7.12,7.15}.md`,
`.claude/tasks/contract-projects-{7.5,7.7}.md`, `NavERP.md` §7.16 (lines 1258–1264).

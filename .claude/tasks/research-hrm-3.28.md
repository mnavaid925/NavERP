# Research — Module 3.28: HR Reports (hrm)

## Scope note (read first)
Per NavERP.md, 3.28 covers 5 report families: **Headcount, Attrition, Diversity, Cost, Hiring**. This is a
**derived-view, read-only reporting sub-module** — like accounting's `trial_balance`/`ap_aging` — built entirely
on data that already exists in `apps/hrm/models.py` and `apps/core/models.py`. **No new models are proposed.**
Source models confirmed by reading the codebase:
- `core.Employment` (`party`, `org_unit`, `manager`, `hired_on`, `status` ∈ active/on_leave/terminated)
- `hrm.EmployeeProfile` (`gender`, `date_of_birth`, `designation`, `employee_type`, `employment` FK, `work_location`)
- `hrm.Designation` (`budgeted_headcount` — confirmed field, migration 0007)
- `hrm.SeparationCase` (`employee`, `separation_type`, `exit_reason`, `actual_last_working_day`, `status`)
- `hrm.JobRequisition` (`created_at`, `posted_at`, `filled_at`, `department`, `cost_center`, `hiring_manager`,
  `recruiter`, `headcount`, `estimated_annual_cost`, `hiring_cost_budget`, `status`)
- `hrm.JobApplication` (`stage`, `source`, `applied_at`, `stage_changed_at`, `hired_on`, `requisition`, `candidate`)
- `hrm.CandidateProfile` (`source` — `CANDIDATE_SOURCE_CHOICES`, `gender`) — **source-of-hire already exists**,
  no gap here (both `CandidateProfile.source` and a per-application `JobApplication.source` are present).
- `hrm.EmployeeSalaryStructure` (`annual_ctc_amount`, `status` — current/effective-dated CTC, no payroll run needed)
- `hrm.Payslip` / `hrm.PayslipLine` (`gross_pay`, `net_pay`, `component_type`, `contribution_side` — actual
  realized payroll cost per `PayrollCycle`)
- `core.OrgUnit` (`kind` ∈ company/branch/department/team/cost_center — the department/cost-center dimension)

## Leaders surveyed (with source links)
1. **Workday People Analytics** — enterprise HCM with 70+ pre-built workforce metrics and executive dashboards —
   [Analytics & Reporting](https://www.workday.com/en-us/products/human-capital-management/analytics-reporting.html),
   [Headcount Report guide](https://www.workday.com/en-us/topics/hr/headcount-report.html)
2. **SAP SuccessFactors People Analytics** — "Stories" report builder with standard Headcount & FTE / Turnover
   templates — [Headcount and FTE story](https://help.sap.com/docs/successfactors-platform/understanding-story-reports-template-in-people-analytics/headcount-and-fte),
   [Turnover Analysis with Stories](https://community.sap.com/t5/human-capital-management-blog-posts-by-sap/creation-of-a-simple-turnover-analysis-with-stories-in-people-analytics/ba-p/13581046)
3. **BambooHR** — SMB HRIS with a built-in Reports Gallery (headcount, turnover, demographics, EEO-1) —
   [HR Reporting](https://www.bamboohr.com/hr-software/hr-reporting),
   [Most Useful HR Reports](https://www.bamboohr.com/blog/most-useful-hr-reports-new-users),
   [New Headcount Report](https://www.bamboohr.com/blog/growing-something-new-headcount-report-can-track)
4. **ADP DataCloud** — workforce analytics layered on ADP payroll data with external peer benchmarking —
   [ADP DataCloud](https://www.adp.com/what-we-offer/products/adp-datacloud.aspx)
5. **Visier People** — pure-play people-analytics platform; canonical metric definitions (headcount, attrition,
   diversity) — [Visier People](https://www.visier.com/products/visier-people/),
   [What Are People Metrics](https://www.visier.com/blog/what-are-people-metrics/)
6. **Zoho People (Advanced Analytics)** — 75+ ready-made HR reports/dashboards incl. Hiring-vs-Attrition —
   [Advanced Analytics](https://www.zoho.com/people/advanced-analytics.html)
7. **Keka HR Analytics** — Headcount-by-Demographics / Growth & Retention / Attrition-Analysis dashboard triad —
   [HR Analytics Software](https://keka.com/hr-analytics-software),
   [Tracking attrition](https://help.keka.com/admin/tracking-attrition-in-the-organization)
8. **Darwinbox People Analytics (Atlas)** — AI-driven analytics incl. an Attrition Predictor and DEI dashboards —
   [People Analytics](https://darwinbox.com/en-us/products/people-analytics)
9. **greytHR** — India-centric HRMS with a 150+ report "Reports Gallery" (payroll cost, headcount, statutory) —
   [greytHR overview](https://www.softwaresuggest.com/greythr),
   [What is HRMS](https://www.greythr.com/blog/what-is-human-resources-management-system-hrms/)
10. **Oracle Fusion HCM Analytics** — pre-built workforce-core metrics incl. FTE, tenure/age-band diversity,
    ML-flagged diversity anomalies — [Workforce Analytics product tour](https://www.oracle.com/fusion-ai-data-platform/hcm-analytics/workforce-analytics-product-tour/),
    [HCM Workforce Core Metrics reference](https://docs.oracle.com/en/cloud/saas/analytics/25r4/fahia/hcm---workforce-core-metrics.html)

**Bonus (11th, cited for a specific differentiator):** **ChartHop** — org-chart-centric people analytics with
"time travel" historical diversity snapshots and headcount-planning scenarios —
[People Analytics](https://www.charthop.com/landing-pages/people-analytics)

**Metric-formula standards referenced:**
- [SHRM: How to Determine Turnover Rate](https://www.shrm.org/topics-tools/tools/how-to-guides/how-to-determine-turnover-rate) —
  annualized turnover = separations ÷ average headcount × 100, average headcount = (period-start + period-end)/2.
- [SHRM Time-to-Hire/Time-to-Fill Calculation Spreadsheet](https://www.shrm.org/topics-tools/tools/forms/time-to-hire-time-to-fill-calculation-spreadsheet) —
  time-to-fill = requisition-open → offer-accepted; time-to-hire = candidate-enters-pipeline → offer-accepted.
- [ANSI/SHRM 06001.2012 Cost-Per-Hire standard](https://x0pa.com/calculators/cost-per-hire/) —
  CPH = (internal + external recruiting costs) ÷ total hires.

## Feature catalog by report family

### Headcount Report
- **Point-in-time headcount snapshot (as-of date)** — count of active employees on a chosen date · seen in:
  Workday, BambooHR, Zoho People, SAP SuccessFactors, Keka · priority: table-stakes · spine: `core.Employment`
  filtered `status="active"` and `hired_on <= as_of` (exclude separations before as_of via `SeparationCase`)
  · buildable now
- **New joins in period** — hires whose start date falls in the selected range · seen in: Workday, BambooHR,
  Zoho People · priority: table-stakes · spine: `core.Employment.hired_on` between range · buildable now
- **Exits in period** — departures whose last working day falls in the range · seen in: Workday, BambooHR,
  Zoho People, Keka · priority: table-stakes · spine: `hrm.SeparationCase.actual_last_working_day` (fallback
  `core.Employment.status="terminated"`) · buildable now
- **Headcount trend (month-by-month)** — line/table of headcount over a rolling N months · seen in: BambooHR,
  Workday, Zoho People, Keka · priority: common · spine: derived by iterating months and counting `Employment`
  · buildable now
- **Headcount by department / org unit** — bar breakdown by department · seen in: Workday (Headcount & FTE
  story), SAP SuccessFactors, Keka · priority: table-stakes · spine: `core.Employment.org_unit` · buildable now
- **Headcount by designation / job title** — seen in: SAP SuccessFactors, Keka · priority: common · spine:
  `hrm.EmployeeProfile.designation` · buildable now
- **Headcount by employment type (FT/PT/contract/intern)** — seen in: Workday, Keka (worker-type filter) ·
  priority: common · spine: `hrm.EmployeeProfile.employee_type` · buildable now
- **Actual vs budgeted headcount (by designation)** — variance against approved position slots · seen in:
  Workday, SAP SuccessFactors · priority: differentiator · spine: `hrm.Designation.budgeted_headcount` vs
  actual count · buildable now (field already exists — nice differentiator to include)
- **FTE (fractional full-time-equivalent) count** — distinguishes headcount from FTE for part-timers · seen in:
  Workday, SAP SuccessFactors, Oracle HCM · priority: differentiator · spine: needs an FTE-fraction field not
  present on `Employment`/`EmployeeProfile` · **data gap — out of scope this pass**
- **Vacancy rate (open approved reqs)** — seen in: Workday · priority: differentiator · spine:
  `hrm.JobRequisition.status`/`headcount` (cross-listed under Hiring) · buildable now, optional KPI tile

### Attrition Report
- **Annualized turnover rate** = separations ÷ average headcount × 100 (annualized if period < 12 months) —
  the SHRM/BLS standard formula · seen in: SAP SuccessFactors, Visier, industry-standard (SHRM) · priority:
  table-stakes · spine: `hrm.SeparationCase` count ÷ avg(`core.Employment` active count at period start/end)
  · buildable now
- **Voluntary vs involuntary turnover split** — seen in: BambooHR (reason for departure), SAP SuccessFactors,
  Keka (exit type) · priority: table-stakes · spine: `SeparationCase.separation_type` (map `resignation`/
  `retirement`/`contract_end` → voluntary; `termination`/`layoff`/`deceased` → involuntary/other — a mapping
  constant, not a new field) · buildable now
- **Attrition by department** — seen in: BambooHR, Keka, Oracle HCM · priority: table-stakes · spine:
  `SeparationCase.employee.employment.org_unit` · buildable now
- **Attrition by exit reason** — seen in: BambooHR ("reason for departure"), Keka · priority: common · spine:
  `SeparationCase.exit_reason` · buildable now
- **Attrition by tenure band at exit** (e.g. <1yr, 1–2, 3–5, 6–10, 10+) — seen in: BambooHR ("length of
  employment"), Oracle HCM, Visier · priority: common · spine: derived from `Employment.hired_on` →
  `actual_last_working_day` · buildable now
- **Attrition trend (monthly/quarterly)** — seen in: Zoho People (Attrition Trend report), SAP SuccessFactors
  (Turnover Analysis story), Keka · priority: table-stakes · spine: `SeparationCase` grouped by month of
  `actual_last_working_day` · buildable now
- **Retention rate** (complement of turnover) — seen in: Workday, Keka (Growth & Retention section) ·
  priority: common · spine: derived, no extra query · buildable now
- **Attrition risk prediction (ML)** — seen in: Workday, Darwinbox (Attrition Predictor), ADP (vulnerability
  turnover) · priority: differentiator · integration/later (needs a trained model + historical feature store)
- **Regrettable vs non-regrettable attrition (perf-linked)** — seen in: Keka (by performance rating), Oracle
  HCM · priority: differentiator · spine: would join `SeparationCase` → `hrm.PerformanceReview` rating (3.19,
  already built) · nice-to-have, **deferred** to keep this pass to pure spine fields
- **Industry turnover benchmarking** — seen in: ADP DataCloud (42M-employee peer data) · priority:
  differentiator · integration/later (external data feed)

### Diversity Report
- **Gender split (overall + by department)** — seen in: Visier, BambooHR, Zoho People, Oracle HCM, ChartHop ·
  priority: table-stakes · spine: `hrm.EmployeeProfile.gender` × `Employment.org_unit` · buildable now
- **Age-band distribution** (industry-standard bands: <25, 25–34, 35–44, 45–54, 55–64, 65+) — seen in: Oracle
  HCM, Visier, ChartHop, BambooHR (age in turnover breakdown) · priority: table-stakes · spine: derived from
  `EmployeeProfile.date_of_birth` · buildable now
- **Tenure-band distribution** (<1yr, 1–2, 3–5, 6–10, 10+) — seen in: Oracle HCM, ChartHop, SAP SuccessFactors
  (avg length of service) · priority: common · spine: derived from `Employment.hired_on` · buildable now
- **Diversity cross-tab by department** (gender/age mix per dept) — seen in: Zoho People, Oracle HCM, ChartHop
  · priority: common · spine: `EmployeeProfile.gender` × `Employment.org_unit` · buildable now
- **Average age / average tenure (company-wide + by dept)** — seen in: SAP SuccessFactors (Headcount & FTE
  story) · priority: common · spine: derived aggregate · buildable now
- **Race/ethnicity representation (EEO-1 categories)** — seen in: Oracle HCM, ChartHop, Workday (diversity
  ratios) · priority: differentiator · spine: **no field exists** on `EmployeeProfile` (only free-text
  `nationality`) · **data gap — out of scope** (adding it would also be sensitive PII requiring the encryption
  pattern already used for `national_id`)
- **Pay-equity / compensation gap by gender** — seen in: ADP DataCloud, Oracle HCM · priority: differentiator ·
  integration/later (needs a dedicated comp-equity analysis, beyond a single report view)
- **Disability / veteran-status representation** — seen in: Oracle HCM, Workday (EEO categories) · priority:
  differentiator · **data gap — out of scope** (no field)

### Cost Reports
- **Total salary cost (period)** — seen in: greytHR (payroll cost reports), SAP SuccessFactors, Keka ·
  priority: table-stakes · spine: `hrm.Payslip.gross_pay`/`net_pay` summed for a `PayrollCycle`; when no cycle
  has been run yet, fall back to `EmployeeSalaryStructure.annual_ctc_amount / 12` (current run-rate) ·
  buildable now
- **Department-wise / cost-center-wise salary cost** — seen in: greytHR (cost-center reports), SAP
  SuccessFactors, Keka · priority: table-stakes · spine: `Payslip.employee.employment.org_unit` (dept) —
  `core.OrgUnit.kind="cost_center"` gives the cost-center dimension used elsewhere (e.g. `JobRequisition.cost_center`)
  · buildable now
- **Average cost per employee** — seen in: Workday ("costs tied to individuals"), ADP DataCloud · priority:
  common · spine: total cost ÷ headcount · buildable now
- **CTC component breakdown (earning / deduction / employer contribution)** — seen in: greytHR (CTC breakdown),
  Keka · priority: common · spine: `PayslipLine.component_type` + `contribution_side` · buildable now
- **Cost trend over time (monthly payroll run-rate)** — seen in: greytHR, SAP SuccessFactors · priority:
  common · spine: `Payslip` aggregated by `PayrollCycle.period_start` · buildable now
- **Overtime / bonus / arrears cost breakdown** — seen in: greytHR, ADP · priority: nice-to-have · spine:
  `PayslipLine.component_type` ∈ (`bonus`,`arrears`) · buildable now, but overlaps NavERP.md's own 3.29/3.31 —
  keep as a minor line item here, full OT analysis belongs to 3.29/3.31
- **Budgeted vs actual cost variance (vs requisition budget)** — seen in: Workday, SAP SuccessFactors
  (compensation planning) · priority: differentiator · spine: `JobRequisition.estimated_annual_cost` vs actual
  `Payslip` cost for that hire · buildable now as an optional KPI, nice-to-have
- **Fully-loaded cost incl. employer contributions** — seen in: Workday, ANSI/SHRM external-cost methodology ·
  priority: differentiator · spine: `PayslipLine.contribution_side="employer"` rows · buildable now, nice-to-have

### Hiring Reports
- **Time-to-fill** (requisition open → offer accepted) — the SHRM-standard org-process metric · seen in: SHRM
  standard, Workday, SAP SuccessFactors, Oracle HCM · priority: table-stakes · spine:
  `JobRequisition.created_at` (or `posted_at`) → `JobRequisition.filled_at` · buildable now
- **Time-to-hire** (candidate enters pipeline → accepts offer) — the SHRM-standard candidate-experience metric
  · seen in: SHRM standard, Zoho People · priority: table-stakes · spine: `JobApplication.applied_at` →
  `JobApplication.hired_on` · buildable now
- **Source-of-hire mix** — which channel produced actual hires · seen in: Zoho People (Hiring-vs-Attrition),
  Workday, Darwinbox · priority: table-stakes · spine: `JobApplication.source` (or `CandidateProfile.source`),
  filtered to `stage="hired"` · buildable now — **no gap**, source is already tracked at both the candidate and
  per-application level
- **Recruiting funnel conversion** (applied → screening → interview → offer → hired, with drop-off %) — seen
  in: Workday, SAP SuccessFactors (talent-pipeline metrics), Zoho People · priority: table-stakes · spine:
  `JobApplication.stage` counts using `APPLICATION_STAGE_CHOICES` order · buildable now
- **Requisitions opened vs filled / open-position aging** — seen in: Workday (vacancy rate), SAP SuccessFactors
  · priority: common · spine: `JobRequisition.status` counts + `is_overdue` property · buildable now
- **Hires by department / hiring manager / recruiter** — seen in: Workday, SAP SuccessFactors · priority:
  common · spine: `JobRequisition.department`/`hiring_manager`/`recruiter` joined to hired `JobApplication`s ·
  buildable now
- **Offer acceptance rate** — seen in: Workday, SAP SuccessFactors · priority: common · spine:
  `JobApplication.stage` transitions `offer`→`hired` vs `offer`→`rejected`/`withdrawn` · buildable now
- **Cost-per-hire (ANSI/SHRM standard)** — seen in: ANSI/SHRM 06001.2012, Workday, ADP · priority:
  differentiator · spine: NavERP only has `JobRequisition.hiring_cost_budget`, a **budget estimate**, not
  actual recruiting spend (no agency-fee/job-board-spend ledger exists) · **data gap** — buildable only as a
  rough "budgeted cost ÷ planned hires" proxy; a true actuals-based CPH is out of scope until a recruiting-spend
  ledger exists
- **Diversity of hires** (gender/source mix of new hires) — seen in: Oracle HCM, ChartHop · priority:
  nice-to-have · spine: `CandidateProfile.gender` × hired `JobApplication`s · buildable now, cross-cutting with
  the Diversity family

## Recommended report views (this pass — no new models)
6 derived views + a landing page, mirroring the `accounting/reports/*` convention (`render()` with an
aggregation-only view function, no model writes). All views filter by `tenant=request.tenant` and accept
GET-param filters (date range / department / period) per the Filter Implementation Rules.

- **`hr_reports_index`** — landing/hub page. Tiles linking to the 5 reports below, each showing one headline
  KPI (current headcount, YTD annualized attrition %, gender split, MTD salary cost, avg time-to-fill). No
  filters (or a single global `as_of` date passed through to child links).
- **`headcount_report`** — KPIs: total active headcount (as-of), new joins in period, exits in period, net
  change, actual-vs-budgeted headcount. Tables: by department (`Employment.org_unit`), by designation
  (`EmployeeProfile.designation`), by employment type (`EmployeeProfile.employee_type`). Chart: trailing-12-month
  headcount trend. Filters: `as_of` date (default today), `date_from`/`date_to` (for joins/exits), `department`.
  Sources: `core.Employment`, `hrm.EmployeeProfile`, `hrm.SeparationCase`, `hrm.Designation.budgeted_headcount`.
- **`attrition_report`** — KPIs: total separations in period, annualized turnover %, voluntary %, involuntary %,
  retention %. Tables: by department, by exit reason, by tenure band. Chart: monthly attrition trend. Filters:
  `date_from`/`date_to` (default trailing 12 months), `department`, `separation_type`.
  Source: `hrm.SeparationCase` + `core.Employment` (for average headcount denominator).
- **`diversity_report`** — KPIs: gender split %, avg age, avg tenure. Tables/charts: age-band distribution,
  tenure-band distribution, dept × gender cross-tab. Filters: `department`, `as_of` date.
  Source: `hrm.EmployeeProfile` (gender, date_of_birth) + `core.Employment` (hired_on, org_unit).
- **`cost_report`** — KPIs: total salary cost (period), avg cost per employee, employer-contribution cost.
  Tables: department-wise cost, CTC component breakdown (earning/deduction/employer). Chart: monthly cost
  trend. Filters: `cycle`/period select (defaults to latest `PayrollCycle`), `department`. Sources:
  `hrm.Payslip`/`hrm.PayslipLine` (actual, when a cycle exists) with an `hrm.EmployeeSalaryStructure
  .annual_ctc_amount` fallback for a "current run-rate" figure when no payroll has been processed yet.
- **`hiring_report`** — KPIs: open requisitions, filled requisitions, avg time-to-fill (days), avg time-to-hire
  (days), offer acceptance rate. Tables: source-of-hire mix, funnel conversion by stage, hires by department.
  Filters: `date_from`/`date_to` (against `JobRequisition.created_at`/`JobApplication.applied_at`),
  `department`. Sources: `hrm.JobRequisition`, `hrm.JobApplication`, `hrm.CandidateProfile`.

**Nice-to-have, buildable in the same pass if time allows:** a CSV export button per report (mirrors no
existing pattern in `accounting/reports` yet, but is a trivial `django.http.HttpResponse` + `csv.writer` add);
a simple bar/pie via inline SVG or a lightweight chart partial (no new JS dependency needed — the codebase uses
Tailwind + HTMX, so a CSS-bar or `<canvas>`-free div-bar chart keeps this a pure-Django pass).

## Deferred (later passes / integrations)
- **FTE (fractional headcount)** — needs a new FTE-fraction field on `Employment`/`EmployeeProfile`; not
  present today. Defer until a real part-time/FTE-weighting need surfaces.
- **Race/ethnicity, disability, veteran-status representation (EEO-1 categories)** — no field exists; adding
  one is sensitive PII and should follow the encryption pattern already used for `national_id`/`passport_number`.
  Defer to a dedicated EEO-compliance pass, not this reporting pass.
- **Pay-equity / compensation-gap analysis** — deeper statistical modeling (regression-adjusted gaps) beyond a
  single aggregation view; candidate for 3.37 Compensation & Benefits or a future analytics-specific pass.
- **Attrition-risk prediction (ML)** — needs a trained model + historical feature pipeline; explicitly out of
  scope for a derived-view Django pass. (NavERP.md 3.32 Analytics Dashboard already earmarks "Predictive
  Analytics" separately.)
- **True actuals-based cost-per-hire (ANSI/SHRM)** — NavERP has no recruiting-spend ledger (job-board/agency
  fees); only `JobRequisition.hiring_cost_budget` (a budget estimate) exists. A rough budgeted-CPH proxy is
  buildable now; real CPH needs a future recruiting-expense model.
- **Industry benchmarking (ADP DataCloud-style)** — requires an external aggregated-data feed; out of scope.
- **Regrettable vs. non-regrettable attrition (perf-linked)** — a real but secondary cross-join to
  `hrm.PerformanceReview`; nice-to-have, can be added later without a schema change.
- **Custom drag-and-drop dashboard builder** — Workday/BambooHR/Keka-style report builder is a major UI/UX
  investment; NavERP.md already reserves this for 3.32 Analytics Dashboard, not 3.28.
- **Overtime cost analysis, leave liability, statutory reports** — belong to sibling sub-modules 3.29 Attendance
  Reports / 3.30 Leave Reports / 3.31 Payroll Reports, not 3.28; only a light CTC-component breakdown is
  included here under Cost Reports.

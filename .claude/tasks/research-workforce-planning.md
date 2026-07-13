# Research — Module 3: HRM Sub-module 3.40 Workforce Planning (workforce-planning)

Context confirmed before writing this catalog: `apps/hrm/models.py` currently has ~103 models built through
3.35 Travel Management (`TravelPolicy`/`TravelRequest`/`TravelBooking`). 3.36 (Helpdesk), 3.37, 3.38 (Talent
Management & Succession Planning — 9-box/talent pool/succession live there, NOT here), and 3.39 (Compliance &
Legal) are not yet built. There is **no existing structured employee-skills model** — `CandidateSkill` exists but
is scoped to `CandidateProfile` (pre-hire candidates), not `EmployeeProfile`. `HRDashboard`/`HRDashboardWidget`
(3.32) already provide a generic, metric-driven analytics/KPI framework that the "Workforce Analytics" bullet
should extend rather than duplicate. `JobRequisition` (3.5) already carries per-opening `headcount`,
`salary_min/max`, `estimated_annual_cost`, `hiring_cost_budget`, `department`/`cost_center` — it is the tactical
"authorize one opening" record; 3.40 is the strategic "plan headcount across the org over a period" layer above it.

## Leaders surveyed (with source links)
1. **Visier** — People-analytics platform with predictive workforce planning (ML-based attrition/skill-shortage
   forecasting) — https://www.visier.com/products/workforce-planning/
2. **Anaplan (Workforce Planning)** — Connected planning platform; demand/supply/gap analysis, position-level
   budget, what-if scenario simulation — https://www.anaplan.com/use-case/workforce-planning-software/
3. **Workday Adaptive Planning** — HR+Finance driver-based headcount/cost modeling, scenario comparison, skills
   gap alignment — https://www.workday.com/en-us/products/adaptive-planning/workforce-planning/overview.html
4. **ChartHop** — Org-chart-first headcount planning: drag-and-drop scenario building, real-time budget impact,
   approval routing, ATS push — https://www.charthop.com/modules/headcount-planning
5. **Orgvue** — Organizational design + strategic workforce planning: data harmonization, simulation engine for
   supply/demand gaps, skills analysis, continuous plan-vs-actual monitoring —
   https://www.orgvue.com/solutions/strategic-workforce-planning/
6. **Deel (Workforce Planning)** — Global headcount forecasting tied to real payroll/compliance cost data across
   150+ countries, scenario-based budget impact — https://www.deel.com/hr/workforce-planning/
7. **Sisense (HR/People Analytics)** — General BI embedded into HR: dashboards, predictive trend/forecast,
   natural-language query over blended HR data — https://www.sisense.com/solutions/hr/
8. **Panalyt** — People-analytics platform (APAC-strong): 400+ pre-built HR metrics incl. workforce planning,
   attrition, DEI dashboards; talent management ties into succession/skill development —
   https://www.panalyt.com/product
9. **TalentGuard** — Skills-inventory / competency platform: employee skills database, 3,000+ job/skill library,
   dynamic skill-gap analysis feeding workforce planning dashboards —
   https://www.talentguard.com/skill-inventory , https://www.talentguard.com/platform/workforce-agility
10. **SAP SuccessFactors Workforce Planning** — Operational Headcount Planning (position/job-level, per org unit:
    hires/terminations/transfers/cost) + Strategic Workforce Planning (5-year demand/supply/gap/cost scenario
    modeling) — https://help.sap.com/docs/sap-successfactors-workforce-analytics
11. *(context confirmation)* **Rippling / HiBob / Planful** appeared as top-rated in the current G2 "Workforce
    Planning" category (2026) — HiBob in particular: "build multiple headcount plans simultaneously for any
    workforce scenario" — corroborates the plan+scenario shape recommended below —
    https://www.g2.com/categories/workforce-planning

## Feature catalog by sub-module
### 3.40 Workforce Planning

- **Headcount demand plan (by period/org unit)** — Forward-looking target headcount tied to a planning
  horizon/fiscal period and a growth assumption · seen in: Anaplan, SAP SuccessFactors (Strategic WFP), Workday
  Adaptive Planning, Deel · priority: table-stakes · spine: new table `WorkforcePlan` header, scoped by
  `core.OrgUnit` · buildable now
- **Operational headcount by position/department** — Line-item breakdown of current vs. planned headcount per
  department/designation, with hire/transfer/termination classification · seen in: SAP SuccessFactors
  (Operational Headcount Planning), Anaplan, ChartHop · priority: table-stakes · spine: new table
  `WorkforcePlanLine`, FKs `core.OrgUnit` + `hrm.Designation`/`hrm.JobGrade` (reused, not duplicated) ·
  buildable now
- **Supply analysis / internal talent availability** — Current headcount and skill inventory as the "supply"
  side of the demand/supply/gap triad · seen in: Anaplan, Orgvue, SAP SuccessFactors, Visier · priority:
  table-stakes · spine: `WorkforcePlanLine.current_headcount` + new table `EmployeeSkill` (FK
  `hrm.EmployeeProfile`) · buildable now
- **Skills inventory / employee skills database** — Structured per-employee skill records (proficiency,
  experience, certification) searchable across the org, distinct from the evergreen `Designation.requirements`
  text · seen in: TalentGuard (skills inventory, skills library), Orgvue (skills analysis), Workday Adaptive
  Planning ("skills alignment") · priority: differentiator · spine: new table `EmployeeSkill`, mirrors
  `hrm.CandidateSkill`'s child-row pattern but anchored to `EmployeeProfile` instead of `CandidateProfile` ·
  buildable now
- **Gap analysis (computed)** — Planned minus current headcount (and cost) per line and rolled up per plan,
  surfaced as a live number rather than a stored ledger · seen in: Anaplan, SAP SuccessFactors, Orgvue (gap over
  time) · priority: table-stakes · spine: computed `@property` on `WorkforcePlanLine`/`WorkforcePlan` (no new
  table — mirrors `TravelRequest.net_settlement`'s computed-never-stored convention) · buildable now
- **Hiring/replacement/attrition classification** — Tagging each planned headcount delta as new growth,
  replacement backfill, attrition-driven, or reduction · seen in: SAP SuccessFactors (hires/terminations/
  transfers), Anaplan (backfill needs) · priority: common · spine: `WorkforcePlanLine.hiring_type` choice field ·
  buildable now
- **Cost modeling / hiring budget** — Average loaded cost per head, rolled up to a plan-level budget total;
  ties workforce numbers to money · seen in: Anaplan, Workday Adaptive Planning, Deel (real payroll-driven cost),
  SAP SuccessFactors · priority: table-stakes · spine: `WorkforcePlanLine.avg_annual_cost` (Decimal) +
  `WorkforcePlan.currency` reusing `accounting.Currency`; **does not** post to `accounting.JournalEntry` this
  pass (it's a forecast, not an actual) · buildable now
- **Salary forecast / compensation-band tie-in** — Using existing salary bands to project cost · seen in:
  Anaplan, Deel (global salary benchmarks) · priority: common · spine: reuse `hrm.Designation.min/mid/max_salary`
  as the default source for `WorkforcePlanLine.avg_annual_cost` (pre-fill only — no external benchmark feed) ·
  buildable now
- **Position-level budget & real-time budget tracking** — Every planned role rolls up live into a total cost
  view broken down by team/department · seen in: ChartHop (Impact tab / waterfall), Anaplan (position-level
  budget assignment) · priority: differentiator · spine: computed rollup off `WorkforcePlanLine` — no new table ·
  buildable now
- **Scenario / what-if modeling** — Named alternative plans (growth, freeze, restructuring, cost reduction)
  compared against a baseline, each with its own headcount/cost delta · seen in: Anaplan, Workday Adaptive
  Planning, ChartHop (visual scenarios), Orgvue (simulation engine), SAP SuccessFactors, HiBob ("multiple
  headcount plans simultaneously") · priority: table-stakes (this is the category's headline feature) · spine:
  new table `WorkforceScenario`, FK `WorkforcePlan` · buildable now (as an aggregate-delta record — a full
  line-by-line scenario re-forecast engine is deferred, see below)
- **Restructuring simulation** — Scenario scoped to a specific org unit, modeling a reorg's headcount/cost
  impact · seen in: Anaplan ("restructuring"), Orgvue (org design), ChartHop (drag-and-drop reorg on the org
  chart) · priority: common · spine: `WorkforceScenario.affected_org_unit` (nullable FK `core.OrgUnit`) ·
  buildable now (static delta fields — no live drag-and-drop org-chart editor this pass)
- **Baseline vs. selected/approved scenario** — Marking one scenario as the current-state baseline and one as
  the chosen path forward · seen in: ChartHop, Workday Adaptive Planning (compare scenarios) · priority: common ·
  spine: `WorkforceScenario.is_baseline` / `is_selected` booleans · buildable now
- **Approval workflow for headcount plans/scenarios** — Routing plan or scenario approval to Finance/HR/exec
  stakeholders before it becomes the committed plan · seen in: ChartHop (approval routing by cost/change type),
  Anaplan (position/requisition approvals) · priority: common · spine: reuse the existing lean single-status-field
  pattern (`WorkforcePlan.status`/`WorkforceScenario.status`) rather than a new multi-step `*Approval` child table
  this pass · buildable now (lean); a full multi-approver chain (mirroring `RequisitionApproval`) is deferred
- **Auto-generate job requisitions from an approved plan** — Pushing approved headcount lines straight into
  ATS/requisition creation · seen in: ChartHop (auto-push to Ashby/Greenhouse/Jobvite/Lever), Anaplan · priority:
  differentiator · spine: would create `hrm.JobRequisition` rows from `WorkforcePlanLine` · integration/later
  (needs a bespoke "Generate Requisition" action; reuses existing `JobRequisition`, no new table)
- **Predictive/ML forecasting (attrition-driven demand, skill-shortage prediction)** — Machine-learning models
  projecting future headcount/skill needs from historical trends · seen in: Visier, Workday Adaptive Planning (AI
  prompts), Sisense (forecast/trend), SAP SuccessFactors (predictive analytics) · priority: differentiator ·
  spine: would read `hrm.EmployeeLifecycleEvent`/`SeparationCase` history · integration/later (needs an ML/stats
  layer, out of a single Django CRUD pass)
- **Workforce analytics — productivity/utilization dashboards** — KPI tiles for utilization rate (billable/
  available hours), cost-per-head, headcount trend, plan-vs-actual variance · seen in: Visier, SAP SuccessFactors,
  Sisense, Panalyt (400+ pre-built metrics) · priority: table-stakes · spine: **reuse** `hrm.HRDashboard` +
  `HRDashboardWidget` (3.32) by adding new entries to `WIDGET_METRIC_CHOICES` (e.g. `kpi_workforce_plan_gap`,
  `kpi_avg_cost_per_head`, `kpi_utilization_rate` computed off `hrm.TimesheetEntry`) — **no new model** · buildable
  now as a metric-registry extension (small, additive change to `apps/hrm/analytics.py`, not core to this pass)
- **Multi-country / compliance-aware cost planning** — Localized labor-law and salary-benchmark inputs baked
  into the cost forecast per country · seen in: Deel (150+ countries) · priority: differentiator · spine: would
  need a country/jurisdiction cost-rule table · integration/later
- **Data harmonization from multiple HR/Finance sources** — Ingesting HRIS + payroll + finance data into one
  planning model · seen in: Orgvue, Panalyt (API/CSV ingestion) · priority: common (for standalone BI tools; N/A
  for NavERP since HR/Payroll/Finance already share one DB) · spine: n/a — NavERP's unified core spine already
  solves this · not applicable (an advantage of the unified data model, not a gap)
- **Drag-and-drop visual org-chart scenario builder** — Reorganize by dragging boxes on a live org chart, see
  cost impact instantly · seen in: ChartHop, Orgvue · priority: differentiator · spine: would layer on
  `core.OrgUnit`/`core.Employment` · integration/later (rich client-side interaction — HTMX/Tailwind static forms
  this pass; the org chart itself is already a derived view per the ERD, not a new model)
- **9-box / succession / talent pool linkage** — Connecting workforce gaps to internal successor readiness ·
  seen in: Orgvue, Panalyt · priority: differentiator · spine: belongs to **3.38 Talent Management & Succession
  Planning** (not yet built) — do not duplicate here · deferred to 3.38
- **Continuous/rolling plan monitoring (plan vs. actual)** — Ongoing comparison of the plan against real
  headcount as hires/exits happen · seen in: Orgvue, Anaplan (rolling forecasts) · priority: common · spine:
  computed comparison of `WorkforcePlanLine.current_headcount` (re-entered/refreshed) against live
  `hrm.EmployeeProfile` counts by department — a "Refresh Actuals" action, not a new table · buildable now
  (simple action), full continuous auto-sync is integration/later

## Recommended build scope (this pass — 4 models)
- **`WorkforcePlan`** [`WFP-`] (`TenantNumbered`) — the planning-cycle header. Fields: `name`, `org_unit` (FK
  `core.OrgUnit`, nullable = whole-company scope), `plan_type` (choices: `annual`/`project`/`restructuring`/
  `custom`), `period_start`/`period_end` (DateField), `growth_assumption_percent` (Decimal, nullable — the
  Demand Forecasting driver), `owner` (FK `hrm.EmployeeProfile`), `currency` (FK `accounting.Currency`),
  `status` (choices: `draft`/`active`/`approved`/`archived`), `notes`. Computed properties:
  `total_current_headcount`, `total_planned_headcount`, `total_gap`, `total_budget_impact` (sum of line
  properties). Justified by: Demand Forecasting, Budget Planning · reuses `core.OrgUnit`, `hrm.EmployeeProfile`,
  `accounting.Currency`.
- **`WorkforcePlanLine`** (`TenantOwned`, child of `WorkforcePlan`, `related_name="lines"`) — one row per
  department (+ optional designation). Fields: `plan` (FK), `org_unit` (FK `core.OrgUnit`, required —
  `limit_choices_to={"kind": "department"}` mirroring `JobRequisition.department`), `designation` (FK
  `hrm.Designation`, nullable — blank = whole-department aggregate), `current_headcount`
  (PositiveSmallIntegerField, default 0), `planned_headcount` (PositiveSmallIntegerField, default 0),
  `hiring_type` (choices: `new_growth`/`replacement`/`attrition_backfill`/`reduction`), `avg_annual_cost`
  (Decimal, nullable — pre-fillable from `designation.mid_salary`), `notes`. Computed properties:
  `headcount_gap` (`planned_headcount - current_headcount`), `budget_impact` (`headcount_gap *
  avg_annual_cost`, only when both set). Justified by: Supply Analysis, Gap Analysis, Budget Planning, Operational
  Headcount Planning (SAP SF) · reuses `core.OrgUnit`, `hrm.Designation`.
- **`WorkforceScenario`** [`WFS-`] (`TenantNumbered`, FK `WorkforcePlan`, `related_name="scenarios"`) — a
  named what-if variant. Fields: `plan` (FK), `name`, `scenario_type` (choices: `growth`/`freeze`/
  `restructuring`/`attrition`/`cost_reduction`/`custom`), `affected_org_unit` (FK `core.OrgUnit`, nullable —
  scopes a restructuring to one unit), `description`, `headcount_delta` (SmallIntegerField, signed),
  `cost_delta` (Decimal, signed), `is_baseline` (Boolean, default False), `is_selected` (Boolean, default False),
  `status` (choices: `draft`/`under_review`/`approved`/`rejected`), `notes`. Justified by: Scenario Planning,
  restructuring simulations (Anaplan, ChartHop, Orgvue, Workday Adaptive Planning) · reuses `core.OrgUnit`.
  Own top-level list page (browse/compare scenarios tenant-wide, each linking back to its parent plan) — mirrors
  the `KeyResult`/`GoalCheckIn` precedent of a `TenantNumbered` child with independent identity.
- **`EmployeeSkill`** (`TenantOwned`, FK `hrm.EmployeeProfile`, `related_name="skills"`) — structured skills
  inventory. Fields: `employee` (FK), `skill_name` (CharField), `skill_category` (choices:
  `technical`/`functional`/`leadership`/`soft_skill`/`certification`), `proficiency_level` (choices:
  `beginner`/`intermediate`/`advanced`/`expert`), `years_experience` (PositiveSmallIntegerField, nullable),
  `is_certified` (Boolean, default False), `certification_name` (CharField, blank), `last_assessed_date`
  (DateField, nullable), `is_critical_skill` (Boolean, default False — flags a skill critical to future workforce
  needs), `notes`. `unique_together = ("tenant", "employee", "skill_name")` — mirrors
  `CandidateSkill`'s `("candidate", "skill_name")` pattern exactly, just anchored to `EmployeeProfile` instead of
  `CandidateProfile`. Own tenant-wide, searchable/filterable list page (search by skill/category/department) —
  the "skills inventory" screen. Justified by: Supply Analysis (internal talent availability, skills inventory),
  Gap Analysis (critical-skill flag), TalentGuard/Orgvue's skills-database differentiator.

## Deferred (later passes / integrations)
- **Auto-generate `JobRequisition` rows from an approved `WorkforcePlanLine`** — a bespoke "Generate
  Requisition" action; reuses the existing `JobRequisition` model (ChartHop/Anaplan pattern) — deferred until
  after this pass proves the plan/line shape.
- **Multi-step approval chain for plans/scenarios** (mirroring `RequisitionApproval`/`OfferApproval`) — this pass
  uses a single `status` field; a full approver-sequence child table is deferred.
- **Predictive/ML forecasting** (attrition-driven demand, skill-shortage prediction) — Visier/Workday/SAP SF
  differentiator; needs a stats/ML layer outside a single Django CRUD pass.
- **Drag-and-drop visual org-chart scenario builder** — ChartHop/Orgvue's headline UX; NavERP ships static
  HTMX/Tailwind forms this pass, not a live-editable org-chart canvas.
- **Multi-country compliance-aware cost planning** (Deel's 150+-country labor-law/benchmark inputs) — needs a
  jurisdiction cost-rule table; out of scope for a single-tenant-model ERP pass.
- **9-box grid / succession planning / talent pools** — explicitly belongs to the future **3.38 Talent
  Management & Succession Planning** sub-module; do not build here to avoid duplicating that scope.
- **`WIDGET_METRIC_CHOICES` extension on `HRDashboard`** (utilization rate, plan-vs-actual, cost-per-head KPIs)
  — small additive change to `apps/hrm/analytics.py`, safe to fold into this pass's "wire-up" step but is not a
  new model — flagged here so the `todo` agent doesn't forget it, not because it's postponed indefinitely.
- **Continuous auto-sync of `current_headcount` from live `EmployeeProfile` counts** — this pass ships a manual
  "Refresh Actuals" action at most; a scheduled/automatic sync job is deferred.
- **Full line-by-line scenario re-forecast engine** (recompute every `WorkforcePlanLine` under a scenario) —
  this pass keeps `WorkforceScenario` as plan-level aggregate deltas (mirrors `TravelPolicy`'s "static number
  this pass, not an auto-calc engine" convention), not a per-line override engine.

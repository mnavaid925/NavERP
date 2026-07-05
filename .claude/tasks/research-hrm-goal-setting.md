# Research — Module 3: Human Resource Management — Sub-module 3.18 Goal Setting (hrm)

**Scope note:** This is a **single sub-module** research pass (3.18 Goal Setting only), the first of four
Performance Management sub-modules (3.18 Goal Setting -> 3.19 Performance Review -> 3.20 Continuous Feedback ->
3.21 Performance Improvement). Features that belong to review cycles, ratings/calibration, 360 feedback, kudos/1:1s,
or PIPs are noted here but flagged **Deferred** to their own sub-module so this pass stays scoped to OKR/goal
mechanics only.

## Grounding — existing NavERP spine & HRM models (read before recommending)

- `apps/hrm/models.py::EmployeeProfile` (`TenantNumbered`, prefix `EMP`) is the anchor for every HRM model — a thin
  1:1 extension of `core.Party` + `core.Employment`. **A goal's owner is an `EmployeeProfile` FK — never a raw
  `core.Party` or `User`.**
- `EmployeeProfile.manager` is a **derived property** (`self.employment.manager if self.employment_id else None`)
  returning a `core.Party`, not an `EmployeeProfile`. To resolve "my manager's own goals" the code must do
  `employee.manager.employee_profile` (the reverse `OneToOneField` accessor) — the reporting chain is **not** a
  stored FK on `EmployeeProfile` itself; it flows through `core.Employment.manager`.
- `EmployeeProfile.department` is likewise a derived property returning `self.employment.org_unit` (a
  `core.OrgUnit`, kind="department"). HRM's `DepartmentProfile` (`TenantOwned`) is the thin companion table adding
  `head`/`cost_center`/`code` on top of the `OrgUnit` node — HRM never duplicates the org node itself.
- No goal/OKR/KPI/performance-review model exists anywhere in `apps/hrm/models.py` today (confirmed via grep for
  `Goal|Objective|KeyResult|OKR|PerformanceReview|CheckIn` — zero matches). This is a **greenfield** pass.
- Free `NUMBER_PREFIX` values (39 already used by other HRM models: EMP, LA, LR, ENC, TS, OT, ATT, REG, ONBT, ONB,
  AST, SEP, EI, FNF, EDOC, ELC, JDTMPL, JR, CAND, APP, CETMPL, CC, INTV, IFB, OLTMPL, OFR, BGV, SST, ESS, PRC, PSL,
  SCR, ITD, TXC, POB, BRC) — none clash with the `GP-`, `OBJ-`, `KR-`, `GCI-` prefixes proposed below.
- `NavERP-ERD.md` confirms HRM's core-spine reuse: `Party` (employee role) - `Employment` - `OrgUnit` - `Asset` -
  `Document` - `JournalEntry` (payroll). Goal Setting adds no new spine entity — it is a pure HRM-domain extension
  hanging off `EmployeeProfile`, mirroring how `LeaveAllocation`/`AttendanceRecord`/`PayrollRun` already do.

## Leaders surveyed (with source links)

1. **Lattice** — HR-integrated performance suite; OKR module bundled with reviews/engagement, strong on cascading
   alignment and mid-cycle flexibility — [Goals & OKRs](https://lattice.com/insights/goals-and-okrs) ·
   [OKR Software for People and Performance](https://lattice.com/platform/goals/okrs) ·
   [Understand Progress Calculation](https://help.lattice.com/hc/en-us/articles/360059451414-Understand-Progress-Calculation-in-Lattice) ·
   [Cascading Goals](https://help.lattice.com/hc/en-us/articles/1500001356821-Cascading-Goals)
2. **15Five** — Continuous-performance platform where OKRs live inside the weekly Check-in cadence; strong
   quarterly-cycle + aspirational-vs-commitment target framing —
   [Objectives: Feature Overview](https://success.15five.com/hc/en-us/articles/17103846921243-Objectives-Feature-Overview) ·
   [OKR Methodology in 15Five](https://success.15five.com/hc/en-us/articles/360002682112-OKR-Methodology-in-15Five)
3. **Leapsome** — All-in-one people platform; "Goal Tree" visualization for cascading + AI-assisted OKR drafting —
   [OKR Software for People & Business Success](https://www.leapsome.com/product/goals-and-okrs) ·
   [Getting started with Goals & OKRs](https://help.leapsome.com/hc/en-us/articles/360008358994-Getting-started-with-Goals-OKRs)
4. **Betterworks** — Enterprise goal-setting/OKR platform; goal cloning across teams, Slack drift-nudge alerts,
   flexible check-in cadence — [Enterprise Goal Setting & OKR Software](https://www.betterworks.com/product/okr-software) ·
   [Enterprise Goal Setting & OKR Software (Goals)](https://www.betterworks.com/product/goals/)
5. **Quantive (formerly Gtmhub)** — Strategy-execution/OKR platform with deep automation; 170+ data-source
   integrations for auto-progress, two-way KR/KPI linking, Insightboards —
   [OKRs and Goal Tracking](https://quantive.com/solutions/results/okr-software) ·
   [8 Best OKR Software](https://quantive.com/resources/articles/okr-software)
6. **Perdoo** — Lightweight strategy-execution tool connecting company OKRs, team KRs, and always-on KPIs in one
   Strategy Map; explicit sub-goal weighting and Initiative-driven KR logging —
   [Perdoo — OKR & Strategy Execution Software](https://www.perdoo.com/) ·
   [Superior goal management](https://www.perdoo.com/solutions/superior-goal-management) ·
   [Add OKRs & KPIs](https://support.perdoo.com/en/articles/3960117-add-okrs-kpis) ·
   [Different types of Key Results](https://www.perdoo.com/resources/blog/different-types-of-key-results-and-when-to-use-them)
7. **WorkBoard** — Enterprise/board-ready strategy-execution platform; multi-level cascading across departments/
   BUs/geographies, OKR Heatmap, Business Review Dashboards, AI-drafted weekly briefings —
   [WorkBoardAI product](https://www.workboard.com/product/) ·
   [How to Pick the Best Enterprise OKR Software](https://www.workboard.com/resources/blog/best-okr-software-for-enterprise-strategy)
8. **Microsoft Viva Goals** — Teams-integrated OKR tool; three formal **Key Result types** (Quantity/regular,
   Quality/control, Baseline) and automated hourly check-ins via data-source integration —
   [Introduction to Microsoft Viva Goals](https://learn.microsoft.com/en-us/viva/goals/intro-to-ms-viva-goals) ·
   [Check in and update OKRs](https://learn.microsoft.com/en-us/viva/goals/viva-goals-healthy-okr-program/check-in-okrs-overview) ·
   [Define KR Types in Viva Goals](https://learn.microsoft.com/en-us/viva/goals/viva-goals-healthy-okr-program/kr-types)
9. **Profit.co** — Full-stack OKR + task + performance suite; explicit "sum of weights = 1" weighting model, cascade
   engine, 400+ built-in KPI catalog, AI check-in summaries —
   [OKR Management Software](https://www.profit.co/product/okr-management/) ·
   [KPIs and Initiatives Alignment](https://www.profit.co/answers/okrs/what-is-kpis-and-initiatives-alignment-in-profit-co) ·
   [Milestone tracked Key Result](https://www.profit.co/answers/okrs/what-does-milestone-tracked-key-result-imply/)
10. **Culture Amp (Goals)** / **BambooHR (Performance)** / **Weekdone** — rounding out the survey: Culture Amp's
    "Goals Tree" + Delivery-vs-Development goal split
    ([Goal management tool](https://www.cultureamp.com/platform/features/goal-management) ·
    [Working with the Goals Tree](https://support.cultureamp.com/en/articles/9798545-working-with-the-goals-tree));
    BambooHR's milestone-percentage goal tracking bundled into core HRIS
    ([Performance Management Systems](https://www.bamboohr.com/platform/performance-management/)); Weekdone's
    weekly-check-in-first OKR tree with auto-colored progress dashboards
    ([Weekdone product](https://weekdone.com/product)).

(Peoplebox, Workday Goal Management, Culture Amp, and BambooHR were also searched directly per the target list;
Culture Amp/BambooHR/Weekdone are grouped above as the "#10" entry since their goal-feature depth converges on the
same primitives already covered by 1–9 — no unique feature beyond what's cataloged below was found for them.)

## Feature catalog by sub-module (3.18 Goal Setting)

### 3.18.1 OKR/KPI Management — "Set objectives, key results"
- **Objective (the "O")** — a qualitative, ambitious statement of what to achieve, scoped to company/team/individual
  level · seen in: Lattice, 15Five, Quantive, Perdoo, WorkBoard, Viva Goals, Profit.co, Culture Amp · priority:
  table-stakes · spine: new table `Objective`, owner FK -> `hrm.EmployeeProfile` · buildable now.
- **Key Result (the "KR")** — a quantitative, measurable outcome under an Objective, with start/current/target
  values and a unit · seen in: all 10 · priority: table-stakes · spine: new table `KeyResult` FK -> `Objective` ·
  buildable now.
- **Key Result types (Quantity/Numeric, Percentage, Currency, Boolean/Milestone-binary, Milestone-with-steps)** —
  Viva Goals formalizes 3 types (Quantity/regular, Quality/control "guardrail", Baseline); Perdoo and Profit.co
  distinguish metric-based KRs from milestone-based (binary or step-weighted) KRs · seen in: Viva Goals, Perdoo,
  Profit.co · priority: common · spine: `KeyResult.metric_type` choices field (no new table — a `CharField` choice
  is sufficient for this pass; Viva Goals' "control/guardrail" KR nuance is a **differentiator** deferred, see
  Deferred section) · buildable now (as a choices field on `KeyResult`).
- **Always-on KPIs alongside OKRs** — Perdoo and Profit.co track long-horizon health metrics (not tied to a single
  cycle) in the same workspace as cycle-bound OKRs, with a large pre-built KPI category catalog (400+ in Profit.co)
  · seen in: Perdoo, Profit.co · priority: differentiator · spine: would need a separate `KPI`/metric-catalog table
  distinct from cycle-scoped `KeyResult` · integration/later — deferred, see Deferred section (KPI catalog is a
  bigger, cross-module concern that overlaps BI/Module 10 dashboards).
- **Objective ownership — individual vs. shared/team** — Quantive explicitly supports "assign (shared) OKR
  ownership"; WorkBoard supports multi-owner OKRs at company/team/individual levels · seen in: Quantive, WorkBoard,
  Profit.co · priority: common · spine: reuse `Objective.owner` (FK to `EmployeeProfile`) + an `Objective.scope`
  choice (`company`/`department`/`team`/`individual`) rather than a full M2M co-owner table for this pass ·
  buildable now.
- **AI-drafted OKRs / AI check-in summaries** — Leapsome, WorkBoard, Profit.co all offer generative-AI assistance
  to draft objectives/KRs or summarize check-ins · seen in: Leapsome, WorkBoard, Profit.co · priority: differentiator
  · spine: N/A · integration/later (external LLM call — out of scope for a single Django pass).

### 3.18.2 Goal Alignment — "Cascading goals, team alignment"
- **Cascading/parent-child Objective linkage** — a child Objective explicitly aligns to (rolls up into) a parent
  Objective, forming a tree from company -> department -> team -> individual · seen in: Lattice ("Cascading
  Alignment"), Betterworks, Quantive, Perdoo (Strategy Map), WorkBoard, Viva Goals, Profit.co (cascade engine),
  Culture Amp (Goals Tree), Leapsome (Goal Tree) · priority: table-stakes · spine: new table field
  `Objective.parent_objective` (self-referential FK, `on_delete=SET_NULL`, `related_name="child_objectives"`) ·
  buildable now.
- **Goal Tree / alignment-map visualization** — a visual hierarchy showing how objectives roll up, with drill-down
  by department · seen in: Lattice, Culture Amp, Leapsome, Profit.co, WorkBoard (OKR Heatmap) · priority: common ·
  spine: reuse `Objective.parent_objective` self-FK (a tree can be rendered from the existing parent link — no new
  table needed) · buildable now (as a template/view feature over the recursive FK, not a new model).
- **Horizontal alignment (cross-team, not just vertical cascade)** — Profit.co explicitly calls out connecting
  goals "both vertically and horizontally" (e.g., peer department goals supporting each other, not just parent->
  child) · seen in: Profit.co, Quantive (two-way linking) · priority: differentiator · spine: would need a M2M
  "aligned/contributing objectives" beyond the single `parent_objective` FK · integration/later (defer — start with
  vertical cascade only, the table-stakes case; add M2M horizontal alignment in a later pass if needed).
- **Scope/level tagging (Company / Department / Team / Individual)** — every product tags each Objective with the
  organizational level it lives at, driving default alignment paths and dashboard rollups · seen in: all 10 ·
  priority: table-stakes · spine: `Objective.scope` choices field + `Objective.department` FK -> `core.OrgUnit`
  (reusing the existing OrgUnit "department" kind, exactly as `Designation.department` already does) · buildable
  now.
- **Manager visibility into direct reports' goals** — a manager can see (and in some tools edit) the goals of
  employees who report to them, derived from the reporting line · seen in: Culture Amp ("Viewing and Updating
  Direct Reports' Goals"), Lattice, Betterworks · priority: table-stakes · spine: reuse the **derived**
  `EmployeeProfile.manager` property (-> `core.Employment.manager` -> `Party.employee_profile`) for the queryset
  filter — no new FK needed, this is exactly the pattern `EmployeeProfile.manager` already exists for · buildable
  now.

### 3.18.3 Weight Assignment — "Weightage for different goals"
- **Per-Key-Result weighting within an Objective** — each KR gets a weight (percentage or fractional share) so the
  parent Objective's progress is a weighted (not simple) average of its KRs; default is equal-weight, override-able
  · seen in: Lattice (equal-by-default, override to e.g. 30/70), Perdoo, Profit.co ("sum of weights = 1"),
  Betterworks · priority: table-stakes · spine: new field `KeyResult.weight` (`DecimalField`, default equal-split or
  a tenant-configurable default) · buildable now.
- **Weighted rollup to parent progress %** — the Objective's overall progress/status is computed (not hand-entered)
  from its KRs' individual progress × weight, and that in turn can roll further up a cascade · seen in: Lattice
  (documented "Progress Calculation" help article), Profit.co (KR weight-roll-up), Quantive · priority:
  table-stakes · spine: a `save()`/property method on `Objective` computing `progress_pct` from child `KeyResult`
  rows (derived-not-stored, mirroring the existing NavERP spine principle used for `LeaveAllocation`/
  `AttendanceRecord.hours_worked`) · buildable now.
- **Weighted Objective-to-cascade contribution** — beyond KR-level weight, some tools also weight how much a child
  Objective contributes to its parent's score (not just KR-to-Objective) · seen in: Perdoo ("adjust the weight of an
  Objective's sub-goals — Key Results, Initiatives, and/or aligned OKRs") · priority: differentiator · spine: would
  extend weighting onto `Objective.parent_objective` itself · integration/later — start with KR-level weighting only
  this pass (table-stakes), defer Objective-level cascade-weighting as a refinement.

### 3.18.4 Goal Timeline — "Quarterly/annual goal periods"
- **Named goal cycle/period (Quarterly, Half-yearly, Annual)** — every Objective is scoped to a defined time-boxed
  period with a start/end date, and organizations typically run 3–5 company objectives per quarter · seen in: 15Five
  ("Objectives are usually set quarterly, bi-annually, or yearly"), Lattice, BambooHR (up to 4 review cycles/year),
  Quantive, Profit.co · priority: table-stakes · spine: new table `GoalPeriod` (tenant-scoped cycle catalog: name,
  period_type choice, start_date, end_date, is_active/is_current) that every `Objective` FKs into · buildable now.
- **Mid-cycle goal editing / carry-over** — Lattice explicitly supports adjusting goals mid-cycle as priorities
  shift; 15Five supports deciding whether an incomplete Objective "continues" into the next cycle · seen in:
  Lattice, 15Five · priority: common · spine: reuse `Objective.status` + a simple "clone into next GoalPeriod"
  action (no new table — a view-level copy operation) · buildable now.
- **Aspirational vs. commitment-based target framing** — 15Five frames some Objectives as "aspirational" (50–70%
  success is a win) vs. "commitment" (100% expected) — changes how a completed-vs-partial score is interpreted ·
  seen in: 15Five · priority: differentiator · spine: `Objective.target_type` choice field (`aspirational`/
  `committed`) · buildable now (cheap field, high alignment value) — recommend including.

### 3.18.5 Goal Tracking — "Progress updates, milestones"
- **Periodic check-ins (progress-update log)** — a recurring cadence (weekly is most common) where the goal owner
  logs a new current-value/progress %, a confidence/sentiment note, and blockers; every check-in is timestamped and
  stored as history (not just an overwrite of "current value") · seen in: Betterworks ("flexible check-in
  cadences"), Viva Goals (manual or automated), Quantive, Perdoo (weekly check-ins w/ confidence), Weekdone (weekly-
  check-in-first), Profit.co (automated alerts + AI summaries) · priority: table-stakes · spine: new table
  `GoalCheckIn` FK -> `KeyResult` (or `Objective` for milestone-only goals), capturing date, updated_value/progress,
  confidence/status, comment · buildable now.
- **Milestone-type tracking (binary or step-weighted completion)** — for KRs that aren't a single metric (e.g., a
  project deliverable), track discrete milestones/steps, each optionally weighted, whose completion drives the KR's
  progress % · seen in: Perdoo, Profit.co ("Milestone tracked Key Result"), BambooHR (percentage-of-milestones-
  complete), WorkBoard ("OKR milestones") · priority: common · spine: reuse `GoalCheckIn` as the milestone-completion
  event log for this pass (a lightweight `is_milestone` flag on `KeyResult` + check-ins marking milestone completion)
  rather than a 5th model — full step-weighted milestone sub-tables are a differentiator refinement deferred to
  later hardening.
- **Status/health coloring (On track / At risk / Off track / Behind)** — auto-derived status badge from the
  progress trend, not just a raw percentage · seen in: Weekdone ("auto-colored OKR progress"), WorkBoard (Heatmap),
  Betterworks (Slack drift-nudge at 10% off track) · priority: table-stakes · spine: a computed `status`/`health`
  property on `Objective`/`KeyResult` derived from progress vs. time-elapsed-in-period — no new table · buildable
  now.
- **Drift/stagnation alerts** — automatic nudge (e.g., Slack) when a goal hasn't been updated recently or its
  progress has fallen materially behind the expected pace · seen in: Betterworks, Profit.co · priority: common ·
  spine: N/A (needs a notification/Slack integration) · integration/later.
- **Progress trend visualization / dashboards** — sparkline or history chart of a KR's progress over its check-ins,
  plus an org-wide "goals dashboard" rollup · seen in: all 10 · priority: common · spine: reuse the `GoalCheckIn`
  history table as the data source for a chart view — no new table · buildable now (as a template/view, once
  `GoalCheckIn` exists).
- **Automated progress from connected systems (Jira, Azure DevOps, Excel, 170+ integrations)** — KR progress
  updates automatically from an external system rather than manual check-in · seen in: Quantive, Viva Goals, Lattice
  (Jira/Salesforce/Slack/Teams), Leapsome · priority: common (among enterprise players) · spine: N/A · integration/
  later — clearly external-system territory, out of a single Django pass.

## Recommended build scope (this pass — 4 models)

Per the prompt's suggested OKR shape, and confirmed by the researched feature set (every single one of the 10
surveyed products separates "the time-boxed cycle," "the O," "the KR," and "the periodic update log" into distinct
concepts), the 4-model build for 3.18 is:

- **`GoalPeriod`** [`GP-`] — the quarterly/annual goal-timeline container (3.18.4 Goal Timeline). Fields: `name`
  (e.g. "Q3 2026"), `period_type` (choices: `quarterly`/`half_yearly`/`annual`/`custom`), `start_date`, `end_date`,
  `is_current` (bool, one-per-tenant-at-a-time convenience flag), `status` (choices: `upcoming`/`active`/`closed`).
  Justified by: 15Five/Lattice/BambooHR/Profit.co all scope every Objective to a named, dated cycle; `is_current`
  and `status` support the "carry-over to next cycle" pattern Lattice/15Five describe. Tenant-scoped
  (`TenantOwned`), no core-spine reuse needed (this is a pure HRM-domain catalog table, same pattern as
  `hrm.JobGrade`).

- **`Objective`** [`OBJ-`] — the "O" (3.18.1 OKR Management, 3.18.2 Goal Alignment, 3.18.3 Weight Assignment,
  3.18.4 Goal Timeline). Fields: `title`, `description`, `owner` (FK -> `hrm.EmployeeProfile`, the goal owner — the
  spine reuse point), `goal_period` (FK -> `GoalPeriod`), `scope` (choices: `company`/`department`/`team`/
  `individual`), `department` (FK -> `core.OrgUnit`, kind="department" — reused exactly as `Designation.department`
  already does, nullable for individual-scope goals), `parent_objective` (self-FK, `null=True`,
  `on_delete=SET_NULL`, `related_name="child_objectives"` — the cascade/alignment link from 3.18.2), `target_type`
  (choices: `aspirational`/`committed`, per 15Five), `status` (choices: `draft`/`active`/`completed`/`closed`/
  `cancelled`), plus a derived `progress_pct` property computed as the weighted average of child `KeyResult.weight
  × progress` (3.18.3's weighted-rollup feature, mirroring the spine's derived-not-stored principle already used
  for `LeaveAllocation`). Justified by: cascading (Lattice/Betterworks/Quantive/Perdoo/WorkBoard/Viva Goals/
  Profit.co/Culture Amp/Leapsome all have this), scope tagging (all 10), weighted rollup (Lattice/Profit.co/Perdoo/
  Quantive), and named-cycle scoping (15Five/Lattice/BambooHR/Profit.co).

- **`KeyResult`** [`KR-`] — the "KR" under an Objective (3.18.1 OKR/KPI Management, 3.18.3 Weight Assignment,
  3.18.5 Goal Tracking). Fields: `objective` (FK -> `Objective`), `title`, `metric_type` (choices:
  `numeric`/`percentage`/`currency`/`boolean`/`milestone` — per Viva Goals' formal KR-type distinction and Perdoo/
  Profit.co's metric-vs-milestone split), `start_value`, `target_value`, `current_value` (all `DecimalField`,
  nullable for boolean/milestone types), `unit` (free-text, e.g. "%", "$", "signups"), `weight` (`DecimalField`,
  default equal-split among siblings — 3.18.3's weighting feature, per Lattice/Perdoo/Profit.co/Betterworks), plus
  a derived `progress_pct` property (from start/current/target for numeric KRs, or from linked `GoalCheckIn`/
  milestone completions for milestone-type KRs) and a derived `health_status` property (on-track/at-risk/off-track,
  per Weekdone/WorkBoard/Betterworks' status-coloring feature). Justified by: every one of the 10 products
  structures a KR this way; the metric_type choice buys Viva Goals'/Perdoo's KR-type distinction cheaply as a
  CharField rather than a new table.

- **`GoalCheckIn`** [`GCI-`] — the periodic progress-update log (3.18.5 Goal Tracking). Fields: `key_result` (FK ->
  `KeyResult`), `checked_in_by` (FK -> `hrm.EmployeeProfile`, usually the KR owner but allow manager overrides),
  `check_in_date`, `updated_value` (`DecimalField`, nullable — the new current_value snapshot at check-in time),
  `progress_pct_snapshot` (`DecimalField`, the computed % at that point in time, stored as history so trend charts
  don't need to re-derive from a live current_value that has since moved on), `confidence` (choices:
  `on_track`/`at_risk`/`off_track`, per Betterworks/Weekdone/WorkBoard's health-status framing), `comment` (text —
  the "blockers/wins" note per Quantive/Perdoo/Profit.co). Justified by: Betterworks/Viva Goals/Quantive/Perdoo/
  Weekdone/Profit.co all treat check-ins as a **timestamped history log**, not a single mutable field — this is
  what powers both "progress trend visualization" (3.18.5) and the "drift alert" precondition (last-check-in-date)
  without needing a 5th model for milestones (folded into `GoalCheckIn.comment`/a lightweight `is_milestone_event`
  flag for this pass).

All 4 models are `TenantOwned`/`TenantNumbered` per the mandatory multi-tenancy rule; `Objective`/`KeyResult`/
`GoalCheckIn` FK into `hrm.EmployeeProfile` (never `core.Party` directly, per the existing HRM convention) and reuse
`core.OrgUnit` for department scoping exactly as `Designation`/`DepartmentProfile` already do. No new core-spine
entity is introduced — Goal Setting is a pure HRM-domain extension, consistent with how Leave/Attendance/Payroll
were built.

## Deferred (later passes / integrations)

- **Always-on KPI catalog (400+ built-in KPIs, health-metric tracking distinct from cycle OKRs)** — Perdoo/
  Profit.co feature; a proper KPI-catalog table overlaps Module 10 (BI/Analytics) and is bigger than one
  sub-module's scope. Defer to a later HRM Analytics pass or BI integration.
- **Horizontal (cross-team, non-hierarchical) alignment / M2M "contributing objectives"** — Quantive's two-way
  linking and Profit.co's horizontal-alignment map. Start with vertical `parent_objective` cascade only (table-
  stakes); add M2M horizontal alignment later if demand emerges.
  - **Objective-to-cascade weighting (weighting how much a child Objective contributes to its parent's score, on
  top of KR-level weighting)** — Perdoo's refinement. This pass ships KR-level weighting only (the table-stakes
  case every product has); Objective-level cascade-weight is a follow-on refinement.
- **AI-drafted OKRs / AI check-in summaries** — Leapsome/WorkBoard/Profit.co. Requires an external LLM call —
  out of a single Django pass; note for a future integrations pass.
- **Automated progress sync from external systems (Jira, Azure DevOps, Salesforce, Excel, 170+ integrations)** —
  Quantive/Viva Goals/Lattice/Leapsome. External-integration territory; `GoalCheckIn.updated_value` stays manual-
  entry-only for this pass, but the check-in table shape does not block adding an `is_automated`/`source_system`
  field later.
- **Drift/stagnation Slack/notification alerts** — Betterworks/Profit.co. Needs the notification/Slack integration
  layer; defer.
- **Viva Goals' "control/guardrail" (Quality-type) Key Result nuance** — a KR that monitors consistency rather than
  driving a target. Folded generically into `metric_type` choices for now; the guardrail *behavior* (e.g., alert if
  it drops below a floor rather than climbs to a ceiling) is a refinement for later hardening, not this pass.
- **Review Cycles, Self/Manager/360 assessment, calibration/bell-curve** — belongs to **3.19 Performance Review**,
  not 3.18. Explicitly out of scope here even though check-ins/OKR data will later feed review scoring.
- **Real-time kudos/appreciation, 1:1 meeting notes/action items, anonymous feedback channels** — belongs to
  **3.20 Continuous Feedback**, not 3.18.
- **PIP management, warning letters, coaching notes** — belongs to **3.21 Performance Improvement**, not 3.18.
- **Goal-tree visualization UI (recursive rendering of `parent_objective`) and org-wide dashboard rollups** — these
  are template/view-layer work once the 4 models exist, not additional models; called out in the catalog above as
  "buildable now" but left for the `todo` agent to scope as views/templates rather than data-model work.

---
name: projects
description: >-
  Work on the Project Management module (Module 7 — as-built: 7.1 Project Initiation & Charter:
  project requests/intake with a business case and risk-adjusted ROI, the go/no-go decision verbs,
  request→project conversion, charter authoring with a submit/approve gate, the RACI stakeholder
  register with influence/interest engagement strategy, and kickoff ceremonies with baseline
  acknowledgement; and 7.2 Project Planning & Scheduling: the WBS tree with computed WBS codes and
  deliverable rollups, the task register with duration/effort estimation, the dependency network
  with a computed critical chain, milestones and phase gates with a one-shot achieved stamp, and
  frozen schedule baselines with what-if scenarios and promote/activate verbs; and 7.3 Resource
  Management: the resource pool (internal via hrm.EmployeeProfile / external via core.Party), the
  allocation register with placeholders, soft/firm booking verbs and substitution, the capacity &
  demand board with over-allocation alerts, and project-facing time entries with an approval
  queue, weekly bulk-approve and an actuals-to-plan comparison; and 7.4 Cost & Budget Management:
  budget revisions whose approved-and-activated row IS the cost baseline, the EVM control-account
  register and detail panel (BAC/EV/PV/AC/CPI/SPI/EAC/ETC/TCPI/VAC as guarded derived properties),
  the budget register with category totals, and the expense register (commitments, actuals,
  accruals) with post/void verbs; 7.5 Risk & Issue Management: the risk register with
  probability×impact severity bands and realize/close/reopen verbs, response actions, the issue
  register with an escalation path; 7.6 Quality Management: per-deliverable acceptance-criteria
  plans with an approve/supersede lifecycle, the combined QA + continuous-improvement review
  register (methodology/compliance/gate + kaizen/retrospective/maturity), deliverable inspections
  whose record→accept/reject verbs carry the acceptance decision and customer-party sign-off, the
  defect punch list with an issue bridge, and the two computed boards (CMMI-banded maturity +
  defect trend + lessons lens; per-deliverable acceptance state + acceptance queue); 7.7 Scope &
  Requirements Management: the requirements baseline with submit/approve/implement/verify verbs,
  scope items, the CCB scope-change register, requirement-level verification, and the scope matrix;
  7.8 Task & Work Management: the in-place execution extension on ProjectTask (priority/MoSCoW/
  Eisenhower/percent/actuals), checklist items, the manual-block evidence register, and the board /
  priority / Gantt lenses; and 7.9 Collaboration & Communication: the channel register with archive,
  threaded channel messages, document shares with access levels and revoke/claim/release verbs,
  meetings with agenda + action items and start/complete/cancel/minutes verbs, per-recipient
  project notifications, and the merged activity feed; and 7.10 Document & Knowledge Management: the
  per-project folder tree with a computed path and document count, the controlled-document register
  with real link FKs to milestones/tasks, the immutable approved-revision chain with a cooperative
  check-out lock and a denormalized search copy, the tenant-wide standards library, the insight
  library (usage counter + featured shelf, no FileField), and the three computed pages (repository
  overview, retention & archiving board with its idempotent reminder Run, and knowledge search); and 7.11 Time & Attendance Tracking: time activity codes [TAC-] with overhead categories and billing defaults, overtime calculation rules [OTR-] with daily/weekly/weekend/holiday threshold multipliers, project overtime claims [POT-] with submit/approve/reject workflow and pay/billable calculations, ResourceTimeEntry [RTE-] billable toggle, activity code, and frozen re-logging loop (rte_relog), the utilization dashboard (utilization_dashboard), and the synchronized time/leave/holiday calendar (time_calendar); and 7.12 Portfolio & Program Management: multi-project portfolios [PRT-] with strategic themes and budget envelopes, sub-portfolio programs [PGM-] with target dates and budget targets, portfolio investment scoring [PIN-] with 4-criterion weighted models (strategic, financial, risk, capacity) and decision verbs (fund, reject, defer), cross-project program dependencies [PDEP-] with lead/lag days and clear/reopen verbs, and the executive portfolio dashboard (pfm_dashboard) with scatter heat maps and demand pipeline funnel; and 7.13 Agile & Scrum Management: sprints [SPT-] with start/complete/cancel lifecycle verbs, project epics [EPC-] with derived progress rollups, project releases [REL-] with version tags and publish verb, sprint impediments [IMP-] with severity bands and resolve verb, sprint retrospectives [RET-] with sentiment score and open/close verbs, in-place ProjectTask agile extensions (story_points, sprint, epic, release, is_in_backlog), and the four computed workbenches: sprint backlog grooming (sprint_backlog), active sprint execution burndown (sprint_execution), release roadmap (release_roadmap), and team velocity & health report (velocity_report); and 7.14 Client & External Collaboration: client portal access tokens [CPA-] with fine-grained visibility flags and expiration checks, formal client review cycles & approval requests [CFB-] with sign-off/rejection workflows, contract statements of work [SOW-] and approved amendment chains [SWA-] with dynamic value rollup, external vendor coordination & handoffs [VHD-] with deliverable acceptance and 1–5 scorecard ratings, and project client billing schedules [PCI-] with 1-click accounting AR invoice generation).
  Use when the user
  asks to add/change/debug anything under apps/projects or templates/projects, extend the
  seed_projects seeder, touch project sidebar wiring (LIVE_LINKS 7.1–7.14), work on
  ProjectRequest/Project/ProjectStakeholder/ProjectKickoff/ProjectTask/TaskDependency/
  ProjectMilestone/ScheduleBaseline/ResourceProfile/ResourceAllocation/ResourceTimeEntry/
  BudgetRevision/CostControlAccount/ProjectBudgetLine/ProjectExpense/
  QualityPlan/QualityReview/DeliverableInspection/QualityDefect/
  ProjectRisk/RiskResponseAction/ProjectIssue/IssueEscalation/
  Requirement/ScopeItem/ScopeChangeRequest/ScopeVerification/
  TaskChecklistItem/TaskBlock/
  Channel/ChannelMessage/DocumentShare/Meeting/MeetingAgendaItem/MeetingActionItem/
  ProjectNotification/
  ProjectFolder/ProjectDocument/ProjectDocumentRevision/DocumentTemplate/KnowledgeEntry/
  TimeActivityCode/OvertimeRule/ProjectOvertimeRecord/
  Portfolio/Program/PortfolioInvestment/ProgramDependency/
  Sprint/ProjectEpic/ProjectRelease/SprintImpediment/SprintRetrospective/
  ClientPortalAccess/ClientApprovalRequest/StatementOfWork/SOWAmendment/VendorHandoff/ProjectClientInvoice,
  or invokes /projects.
---

# Module 7 — Project Management (`apps/projects`)

**As-built: 7.1 + 7.2 + 7.3 + 7.4 + 7.5 + 7.6 + 7.7 + 7.8 + 7.9 + 7.10 + 7.11 + 7.12 + 7.13 + 7.14.** 7.15–7.19 are roadmap (a
parallel build may be landing them — always check `apps/projects/models/` first). Do not assume a
model exists because NavERP.md lists the feature — check first.

App path `apps/projects/`, templates `templates/projects/`, `app_name = "projects"`, mounted at
`/projects/`. Migrations `0001_initial`, `0002_ordering_indexes_and_nonnegative_estimates`,
`0003_projecttask_projectmilestone_schedulebaseline_and_more`,
`0004_resourceprofile_resourceallocation_resourcetimeentry_and_more` (12 named indexes),
`0005_budgetrevision_costcontrolaccount_projectbudgetline_and_more` (10 named indexes — the 7.4
tables), `0006_projectrisk_projectissue_riskresponseaction_and_more` (7.5),
`0008_projectissue_iss_tnt_type_idx_and_more` (7.5 review indexes) and
`0009_deliverableinspection_qualityplan_qualitydefect_and_more` (the 7.6 tables — the 0007 leaf
went to the parallel 7.7 build), `0010_alter_scopeitem_status` (7.7 — the `violated` status the
build had omitted from the choices entirely), `0011_taskblock_taskchecklistitem_projecttask_actual_end_and_more`
(7.8's execution columns + its two registers), `0012_channel_channelmessage_documentshare_meeting_and_more`
(7.9's seven tables), `0013_channelmessage_chm_tnt_created_idx_and_more` (7.9 review indexes) and
`0014_projectfolder_projectdocument_documenttemplate_and_more` (7.10's five tables), `0017_resourcetimeentry_activity_code_and_more` (7.11 ResourceTimeEntry fields), `0018_overtimerule_projectovertimerecord_timeactivitycode` (7.11's three tables), `0019_portfolio_program_portfolioinvestment_and_more` (7.12's four tables), `0020_projecttask_epic_projecttask_release_and_more` (7.13's five tables + ProjectTask agile extensions), and `0021_statementofwork_sowamendment_projectclientinvoice_and_more` (7.14's six tables).

## ⚠️ Three different models are called "Project"

| Model | Path | What it is |
|---|---|---|
| `projects.Project` | `apps/projects/models/ProjectInitiation/Projects.py` | **this module's** — the chartered project |
| `accounting.Project` | `apps/accounting/models/ProjectCosting/Projects.py` | pre-spine stand-in for job costing |
| `crm.CrmProject` | `apps/crm/models/ProjectDelivery/Projects.py` | pre-spine stand-in for delivery |

All three use `NUMBER_PREFIX = "PRJ"`. **This is deliberate and is not a bug to "fix".** Numbers are
unique per `(tenant, number)` *within a model*, so there is no key collision. Always import
explicitly (`from apps.projects.models import Project`) and say which "project" a page means.

## Models

All four subclass `TenantNumbered` (`apps/projects/models/_base.py`): tenant FK, `number` allocated
in `save()` via `apps.core.utils.next_number`, timestamps, `ordering = ["-created_at", "-id"]`,
`unique_together ("tenant", "number")`.

### `ProjectRequest` [PRQ-] — intake + business case
Choices: `REQUEST_TYPE_CHOICES` (new_project/enhancement/change_request/defect/idea) ·
`SOURCE_CHOICES` (portal/internal/idea/opportunity/email) · `PRIORITY_CHOICES` ·
`RISK_RATING_CHOICES` (low/medium/high/critical) · `FEASIBILITY_CHOICES` (not_assessed/feasible/
**feasible_with_constraints**/not_feasible — 25 chars, hence `max_length=32`) ·
`STATUS_CHOICES` (draft/submitted/screening/assessment/needs_information/approved/rejected/
deferred/converted) · `DECISION_CHOICES` (go/no_go/hold/deferred).

Money: `estimated_cost`, `estimated_benefit` — `DecimalField(14,2)` with `MinValueValidator(0)`.
Derived, never stored: `roi_pct`, `risk_adjusted_benefit`, `risk_adjusted_roi_pct` using
`RISK_DISCOUNT = {low: 1.00, medium: 0.85, high: 0.70, critical: 0.50}` — a **documented flat
factor, deliberately not Monte Carlo** (that is 7.5's). All arithmetic is `Decimal`; `q2()` clamps
at `9999999999.99`.

`convert_to_project()` — one `transaction.atomic()` with a **row-level compare-and-swap**
(`select_for_update` / `filter(converted_project__isnull=True)`); maps `title→name`, `description`,
`org_unit`, `requester_party→client`, `assigned_approver→executive_sponsor`,
`target_start_date→start_date`, `target_end_date→end_date`, sets both FK directions and
`created_by`. It deliberately does **not** gate on `status` — that rule belongs to the `prq_convert`
view.

### `Project` [PRJ-] — the charter
`name`, `code`, `description`, `request` (back-pointer), `methodology`, and the charter body:
`in_scope`, `out_of_scope`, `objectives`, `success_criteria`, `assumptions`, `constraints`,
`risk_summary`. People: `executive_sponsor`, `project_manager` (Users), `org_unit`, `client`
(`core.Party`). `charter_status` (draft/submitted/approved/rejected) + `charter_approved_by/_at`
(`editable=False`) + `charter_document` (`core.Document`). `status` (draft/chartered/kickoff/
active/on_hold/completed/cancelled).

### `ProjectStakeholder` [PST-] — RACI register
A stakeholder is a **`core.Party` OR a User** — at least one required (`clean()`).
`STAKEHOLDER_TYPE_CHOICES`, `RACI_ROLE_CHOICES` (r/a/c/i), `INFLUENCE_CHOICES` /
`INTEREST_CHOICES` (high/medium/low), `COMMS_PREFERENCE_CHOICES`, `COMMS_FREQUENCY_CHOICES`,
`attending_kickoff`. `unique_together ("tenant","project","party","raci_scope")`.
**`get_engagement_strategy_display()` is hand-written** — Django does *not* generate
`get_FOO_display` for a property. It derives manage_closely / keep_satisfied / keep_informed /
monitor from the influence×interest grid.

### `ProjectKickoff` [PKO-] — the ceremony
`unique_together ("tenant","project")` — one kickoff per project. `AGENDA_TEMPLATE_CHOICES`,
`STATUS_CHOICES` (planned/scheduled/held/completed), `meeting_date`, `completed_at`,
`baseline_acknowledged_by/_at`. `attendee_count` is a **property**; `is_locked` is the attested
predicate (`completed`, or either stamp set), mirroring `accounting.JournalEntry.is_locked`.

## 7.2 Project Planning & Scheduling — `ProjectPlanningScheduling/`, template slug `planning`

Contract: `.claude/tasks/contract-projects-7.2.md`. Scope: the PLAN only — no money columns (7.4's),
no execution actuals/assignments (7.8 extends `ProjectTask` in place), no risk rows (7.5's).

### `ProjectTask` [TSK-] — the WBS node AND the schedulable activity in one row
`project` FK CASCADE `related_name="tasks"` · `parent` self-FK SET_NULL `related_name="children"`
(plain self-FK, no MPTT) · `node_type` (`deliverable` = summary rollup / `work_package` = schedulable
leaf) · `status` (planned/in_progress/done/cancelled — planning only, NOT gated) ·
`planned_start`/`planned_end` (clean(): end ≥ start) · `duration_days` derived property ·
`effort_hours` + `estimation_method` (bottom_up/top_down/analogous/parametric) + `confidence` ·
`sequence` (sibling order). `clean()` also rejects a **cross-project parent**. The hierarchical
`1.2.3` WBS code and every deliverable rollup are computed in the tree view — NEVER stored.

### `TaskDependency` [DEP-] — the sequencing network
`predecessor`/`successor` FKs (`related_name="successor_links"` / `"predecessor_links"`) ·
`link_type` (finish_to_start/start_to_start/finish_to_finish/start_to_finish) · `lag_days`
SmallIntegerField — positive = lag, negative = lead. `clean()`: no self-link, both endpoints in the
same project (and tenant).

### `ProjectMilestone` [MST-] — milestones and phase gates
`is_phase_gate` + `entry_criteria`/`exit_criteria` · `status` (planned/in_review/achieved/missed/
cancelled) · `actual_date` is a stamp: `save()` writes it the first time status is `achieved` and
clears it on reopen — never a form field. Ordering `["target_date", "id"]` (timeline) — a deliberate
exception to newest-first. `status` is NOT on `MilestoneForm`: the only path to `achieved` is the
tenant-admin verb `mst_achieve`.

### `ScheduleBaseline` [BSL-] — frozen baselines and what-if scenarios
`baseline_type` (`baseline` frozen / `what_if` scenario) · snapshot columns `planned_finish`/
`task_count`/`total_effort_hours` + `frozen_on` (editable=False — freeze-time evidence written by
`freeze_snapshot()`, one aggregate; NOT live aggregates). Frozen rows refuse edit/delete (state
guard, not role gate); type is LOCKED on edit (only `bsl_promote` moves what_if→baseline);
`bsl_activate`/`bsl_promote` keep exactly one active baseline per project inside
`transaction.atomic()` — deliberately NO conditional unique constraint (MariaDB can't enforce one).

### 7.2 views and the WBS tree
`views/ProjectPlanningScheduling/ProjectTasks.py::_decorate_wbs` prefetches the whole tree in ONE
query, then decorates each node in Python: `wbs_code`, `is_critical`, `kids` (the decorated child
instances) and the `rollup_*` attrs. The template walks `node.kids` — NEVER `node.children.all`
(see gotcha 8). `views/_helpers.py::critical_path_ids` = the longest dependency chain, computed on
read (iterative Kahn pass, hop-capped, `(sequence, id)` tie-breaks; full CPM float is 7.16's).

## 7.3 Resource Management - `ResourceManagement/`, template slug `resource`

Contract: `.claude/tasks/contract-projects-7.3.md`. Scope: the PEOPLE layer - pool, bookings,
project-facing time actuals. NO money columns (7.4/7.15), no skill table (the matrix/certs are
the `hrm:employeeskill_list` lens, deep-linked from `rsp_detail` for employee-keyed rows), no
timesheet header model (flat entries + weekly verbs), no smoothing engine (alert + manual
rebalance from the allocation verbs), no leave deduction (uniform weekly hours - stated on the
board). WARNING: **two `ResourceAllocation` models exist** - `crm.ResourceAllocation` [RA-] is
the 1.8 pre-spine stand-in; this module's [RAL-] keyed on `ResourceProfile` is the Module 7
master. Same ruling as the three PRJ- models: never rename either.

### `ResourceProfile` [RSP-] - one bookable person
`employee` FK `hrm.EmployeeProfile` OR `party` FK `core.Party` - **exactly one of the two**
(clean() guards it; one pool row per employee per tenant, deliberately no conditional unique -
MariaDB can't). `weekly_capacity_hours` is the denominator of every capacity computation;
`resource_type` internal/contractor/freelancer/consultant; contractor rows carry an
`available_from/to` engagement window; `status` is a lens toggle ON the form. `name` property
walks employee->party->number - every queryset that renders it must
`select_related("employee__party", "party")`.

### `ResourceAllocation` [RAL-] - the booking
NULL `resource` = **placeholder** (a state of the booking, never a fake person row). Hangs off
`project` OR `project_request` (pipeline demand) OR both-none-refused; optional `project_task`.
One magnitude matching `allocation_unit` (hours_per_week / pct_capacity / total_hours - clean()
refuses the mismatch). `booking_status` moves ONLY through the verbs; `end_date` null = ongoing.
`planned_hours(win_start, win_end)` = the crm `overlap_hours()` proration extended to the three
units - cancelled AND released count ZERO (the successor already carries the demand), % of a
placeholder counts ZERO.

### `ResourceTimeEntry` [RTE-] - one day's project time
The thinnest projects-side time log (NOT a fourth timesheet: `hrm.TimesheetEntry.project` points
at the accounting.Project stand-in and cannot join `projects.Project`). Status moves draft ->
submitted -> approved/rejected ONLY through the verbs; the stamps (`submitted_at`, `approved_by`,
`approved_at`) are written exactly once and never rewound (forms exclude them; approved/rejected
rows refuse edit/delete at the view). `week_key` (`resource_id:YYYY-Www`) is the regroup key -
`Meta.ordering ["resource_id", "-entry_date", "-id"]` keeps person-weeks contiguous.

### 7.3 verbs - all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `ral_assign` | **tenant_admin** | placeholder in requested/soft -> names it (requested becomes soft) |
| `ral_substitute` | **tenant_admin** | named soft/firm -> releases the row inside `select_for_update`, mints the successor (status preserved, `substitute_of` set) |
| `ral_commit` | login | requested->soft, or soft->firm - **refused on a placeholder going firm** ("Assign a resource before committing a placeholder to firm.") |
| `ral_complete` / `ral_cancel` | login | soft/firm -> completed / requested|soft|firm -> cancelled |
| `rte_submit` | login | draft -> submitted (stamps `submitted_at`) |
| `rte_approve` / `rte_reject` | **tenant_admin** | submitted -> approved / rejected (reject carries the `reason` textarea -> `decision_note`) |
| `rte_approve_week` | **tenant_admin** | bulk-approves one person-week (`time-entries/week/<int:resource>/<int:year>/w<int:week>/approve/`, literal BEFORE the `<int:pk>/` routes); week clamped 1..53 + a real-ISO-week guard; ONE audit row on the resource |

**Capacity & Demand board** (`capacity_demand`, template at the sub-module root - rule 6
standalone page): per active resource-week, soft/firm `planned_hours` vs `weekly_capacity_hours`
(`?weeks=` clamped 4..13, default 8) with the over-allocation alert line; `id="demand"` section =
requested/soft demand with `is_gap` placeholders as the hiring trigger. The seeded data keeps
one booking over capacity (RAL-00001 at 48h/wk vs a 40h resource) so the red branch is alive.

## 7.4 Cost & Budget Management — `CostManagement/`, template slug `cost`

Contract: `.claude/tasks/contract-projects-7.4.md`. Scope: the MONEY layer — budget versions,
the EVM structure, cost evidence. NO rates/hours anywhere (7.3 owns people-hours and ships no
money columns; a future rate card may *generate* an `amount`, never add rate fields), NO
`CostBaseline`/`BSL` model, NO `ChangeRequest` model (7.7's), NO GL posting (2.x owns the
ledger — `gl_account` is a PROTECT lens only), NO PO/invoice engines (4.x/6.x own them —
`source_number` is a soft string, never an FK).

**The cost baseline IS the approved-and-activated `BudgetRevision`** — no `is_active` boolean,
no second table. `bvr_activate` supersedes every other approved revision of the project inside
one `transaction.atomic()` (approve deliberately does NOT activate, so two `approved` rows may
coexist; superseded rows KEEP `activated_at` as history, which is why every badge/status check
pairs `activated_at` WITH `status == "approved"`).

### `BudgetRevision` [BVR-] — the budget document and its change control
`STATUS_CHOICES` draft/pending_approval/approved/rejected/superseded. `decision_notes` is
verb-written evidence (`bvr_reject`), off every form. `unique_together ("tenant","number")` AND
`("tenant","project","revision_no")`. `amount_delta` = this revision's lines vs the active
baseline's — the approver's headline. `is_locked` = approved|superseded → edit/delete refuse.
`active_revision` orders by `-activated_at` (None-guards everywhere).

### `CostControlAccount` [CCA-] — the EVM structure
`wbs_node` anchor (same-project `clean()`), `gl_account` lens, separable `contingency`
(`bac_with_contingency`), manually-attested `percent_complete` (7.8's execution fields supersede
it). ALL 16 metrics are DERIVED properties, never columns: `bac/ev/pv/ac/committed/available/cv/
sv/cpi/spi/eac/etc/tcpi/vac/health`. **`active_revision`/`bac`/`ac`/`committed` are
`cached_property`** (review C2: cca_list was 75 queries/page before) — a mutation through the
same in-memory instance reads STALE until a re-fetch; the model tests pin this. None-guards:
`cpi` None when `ac == 0` (absence of spend is not health), `spi` None when `pv == 0`, `tcpi`
None when the denominator is 0; `eac = bac/cpi` (one documented technique, falls back to BAC).
`health` → `{"state", "badge"}` with colour-named classes only; over = `available < 0` OR
`cpi < 0.95`, watch = `cpi < 1.00` (strict — exactly 1.00 or 0.95 is NOT over). `pv` is a
PLANNING-GRADE linear fraction of the anchored window (labelled on the page; not a BCWS curve).

### `ProjectBudgetLine` [PBL-] — the row everything rolls up from
`budget_revision` (a line is only real inside a revision) + denormalised `project` +
required `category` (7 values, no default) + optional `wbs_node`/`control_account`/`gl_account`.
`clean()` pins project/`wbs_node`/`control_account` to the revision's project. **Frozen-revision
lines refuse edit/delete** (review I1 ruling): the approved baseline cannot be rewritten through
its lines — the correction path is a new revision, exactly like the revision itself.

### `ProjectExpense` [PEX-] — the cost evidence that burns the budget
`entry_type` commitment/actual/accrual · `source_kind` (max_length **16** — `supplier_invoice`)
· `source_number` soft string. `control_account` is REQUIRED non-nullable (a CA-less row would
silently drop out of every EVM figure). Only POSTED actual+accrual rows count into `ac`; posted
commitments into `committed`; drafts burn nothing; void rows stay visible and stop counting.
amounts are non-negative — reversals are paired void+adjustment rows. `entry_date` non-nullable
(the burn-trend dimension). Posted/void refuse edit/delete; `pex_void` is the correction path.

### 7.4 verbs — all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `bvr_submit` | login | draft → pending_approval (stamps `requested_at`) |
| `bvr_approve` | **tenant_admin** | pending_approval → approved — does NOT activate |
| `bvr_reject` | **tenant_admin** | pending_approval; the `decision_notes` textarea is REQUIRED (status precondition runs BEFORE the form check — review M11) |
| `bvr_activate` | **tenant_admin** | approved, not yet stamped → THE baseline; supersedes every other approved row (one `supersede` audit per row) inside the atomic block |
| `pex_post` | login | draft → posted (replay says "already posted") |
| `pex_void` | **tenant_admin** | posted → void (rows stay visible, stop counting) |

Audit: every verb captures `previous = obj.status` BEFORE mutating and logs
`{"verb", "from", "to"}` INSIDE the atomic block where one runs (review I3); actions ≤ 10 chars.

Register notes: `pbl_list` aggregates its totals strip over a queryset pre-scoped with the SAME
filter params + guards as `crud_list` re-applies (one conditional-Sum query), and the totals
card renders BELOW the filter bar. `cca_detail` pins its `budget_lines` to the EXACT active
revision (a superseded-but-stamped revision must not leak in) and caps `expenses` at 25.

## 7.5 Risk & Issue Management — `RiskManagement/`, template slug `risk`

Contract: `.claude/tasks/contract-projects-7.5.md`. Scope: the UNCERTAINTY layer — the risk
register, response actions, the issue log with its escalation trail, and the two computed boards.
Boundaries ruled at build time: the enterprise QMS (NCR/CAPA/audits/inspections) is **scm 4.9's**
(7.6 quality is deliverable-scoped); per-tenant risk appetite is **7.19's** master data (7.5 pins
the documented default `TOLERANCE_BANDS = {high, critical}`); the knowledge repository is
**7.10's** (`lessons_learned` is a FIELD on the row, not a second store); no GL posting and no
money columns beyond the risk's own exposure inputs (7.4 owns budgets — `contingency_account` is
a read-only lens and the write to `CostControlAccount.contingency` stays 7.4's, Ruling 4).

**Everything scored is DERIVED, never stored** — the 7.1 ROI / 7.4 EVM ruling again: `score`,
`severity_band`, `emv`, `residual_*`, `is_review_overdue`, `is_open`, `is_overdue`, `age_days`
are Python properties. `PROBABILITY_PCT = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}` (a MODULE-level
constant, not a class attribute) converts the 1–5 ordinal for EMV and the Monte Carlo draw;
`SEVERITY_BANDS` maps score 1–25 onto low/medium/high/critical. `residual_emv` divides the
residual ordinal by 100 DIRECTLY (entered as a percent — deliberately not routed through
`PROBABILITY_PCT`; the model tests pin this).

### `ProjectRisk` [RSK-] — the register row
`project` (CASCADE) + same-project `clean()` guards on `wbs_node` and `contingency_account`.
Lifecycle `identified → assessing → response_planned → monitoring → realized → closed` is
verb-driven (`status`/`closed_at`/`created_by` off the form). `is_locked` = realized|closed →
edit/delete refuse.

### `RiskResponseAction` [RRA-] — the committed work that executes a strategy
`risk` CASCADE; own `owner`/`due_date`/`cost` (an estimate, not a 7.4 posting); strategy
vocabulary mirrors the risk's six. `rra_complete` is the only writer of `status="completed"` +
`completed_at`; a completed action is terminal — there is **no cancel verb** (the detail page
says so; review I6).

### `ProjectIssue` [ISS-] — what already happened
`issue_type` issue/action_item/decision/other; triaged by `severity` (critical/high/medium/low —
no P×I score). The realize bridge: `rsk_realize` mints the issue INSIDE its atomic block with
`risk` FK + `severity=obj.severity_band` (the I1 invariant — the registers cannot drift about
which risk materialized). `escalation_level` is stored 0–4 because the `?escalated=1` queue lens
is a real column lookup; the evidence stamps (`root_cause`, `resolution_note`, `resolved_by/_at`,
`escalated_to/_at`) are verb-written only.

### `IssueEscalation` [ESC-] — one step of the escalation path
No status, no lifecycle — appended by `iss_escalate` or `esc_create`; `escalated_at` is
`auto_now_add`; `reason` REQUIRED. `LEVEL_CHOICES` 1–4 is the ONE level vocabulary (filter + form
+ verb all read it; the form field is a `TypedChoiceField(coerce=int)` over it).

### 7.5 verbs — all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `rsk_realize` | login | any live status; **atomic** risk-save + issue-mint (review I1); replay = info no-op |
| `rsk_close` | login | any live status; `RiskClosureForm` lesson optional; stamps `closed_at` |
| `rsk_reopen` | **tenant_admin** | closed → monitoring, clears `closed_at` |
| `rra_complete` | login | planned/in_progress → completed (terminal; replay refused) |
| `iss_escalate` | **tenant_admin** | live issue; bumps `escalation_level` + mints the ESC row atomically |
| `iss_resolve` | login | live issue; `resolution_note` REQUIRED; replay refuses to overwrite the note |
| `iss_close` | login | resolved ONLY (an open issue cannot be closed) |
| `esc_create`/`esc_edit`/`esc_delete` | **tenant_admin** (review I9) | the register that writes the escalation trail is admin-gated to match `iss_escalate`; the list/detail pages hide the controls for members |

Audit: every verb captures `previous` BEFORE mutating and logs `{"verb", "from", "to"}` inside
the atomic block where one runs; actions ≤ 10 chars.

Register notes: the derived lenses are **pre-scoped in the views from real columns** — `_band_q`
rebuilds `?band=` from the `(probability, impact)` pairs inside `SEVERITY_BANDS`' bounds (a
property cannot be filtered), `?overdue=1` ≡ `?review_due=1`, `?top=1` orders by
`(-probability, -impact, -cost_impact, -id)`. The two computed boards (no snapshot tables) cap
their working set at `_REGISTER_CAP = 2000` rows (review M13). The Monte Carlo
(`risk_analysis`, POST): `rng = random.Random(seed)`, one Bernoulli per open costed risk,
nearest-rank percentiles; a seed is reproducible byte-for-byte (CSRF aside), `iterations` clamps
to `[100, 10000]`, and a valid `?seed=` survives an out-of-range `?iterations=` and an
empty-body POST (per-field resolution — review M4); population = `cost_impact > 0`, status live,
**id-ascending** (the draw order IS the reproducibility guarantee, review M9). Monitoring's
lessons lens follows `?project=` (review I10). All seven register indexes are named
(`rsk_tnt_created_idx`, `rsk_tnt_review_idx`, `rsk_tnt_owner_idx`, `rra_tnt_created_idx`,
`rra_tnt_strategy_idx`, `iss_tnt_type_idx`, `iss_tnt_due_idx` — migration 0008 added the last
five reviews I7/M11/M12 asked for; `rsk_tnt_created_idx` came with the build in 0006).

## 7.6 Quality Management — `QualityManagement/`, template slug `quality`

Contract: `.claude/tasks/contract-projects-7.6.md`. Scope: the CONFORMANCE layer — what a
deliverable must satisfy (plans), whether it does (reviews + inspections + defects) and who
formally accepted it (the acceptance decision). Boundaries ruled at build time: the enterprise
QMS (NCR/CAPA/audits/`QualityInspection`) is **scm 4.9's** — 7.6's inspection class is
deliberately named `DeliverableInspection` because that name is taken; a defect is **not** a
second issue log (it LINKS to `ProjectIssue` via the `qdf_raise_issue` verb, the `rsk_realize`
idiom, and the quality-native fields — criterion, category, disposition — stay here); the
schedule phase gate is **7.2's** `ProjectMilestone` (7.6's gate is the deliverable acceptance
decision, optionally anchored by a nullable `milestone` FK); standards/regulatory references are
free text (**7.19's** master data); minutes/ceremony/repository are **7.9/7.13/7.10's**; and
there is **no money column and no stored score** (a quality cost is a 7.4 `ProjectExpense`;
maturity is computed on read).

**Everything derived is a property, never a column** — same ruling again: `is_review_overdue`,
`is_locked`, `is_overdue`, `age_days`, `defect_count`, `is_acceptance` are Python properties;
every pass rate, punch-list count and maturity figure is computed in a view.

### `QualityPlan` [QPL-] — what one deliverable must satisfy
`acceptance_criteria` REQUIRED (the bullet-1 core); `verification_method` inspection/testing/
demonstration/review/analysis/audit; `standard_reference`/`regulatory_requirement` free text.
Lifecycle `draft → active → superseded/closed` is verb-driven (`status`/`approved_by`/`approved_at`
off the form); `is_locked` = superseded|closed. Same-project `clean()` guards on `wbs_node` and
`source_risk` (the 7.5 quality-category risk the plan mitigates).

### `QualityReview` [QRV-] — one structured quality event (QA + continuous improvement)
`review_type` discriminates: methodology_review/compliance_check/gate_review (bullet 2) vs
kaizen_event/retrospective/maturity_assessment (bullet 4) — ONE register, the market's "one
object with a kind" ruling. Carries the improvement block (`improvement_action/owner/due_date/
status`) as FORM data (planning, not verb-written); `maturity_score` 1–5 optional.
`qrv_report` accepts **planned AND in_progress** (status is off the form and there is no start
verb — the planned-only gate would strand every review); `qrv_close` stamps `closed_at`.

### `DeliverableInspection` [QCI-] — QC execution AND the acceptance decision on one row
`inspection_type` review/testing/demonstration/walkthrough/acceptance; `result` (pass/fail/
conditional/not_applicable, max_length 14 — fields.E009, scm-width) is split from
`usage_decision` (pending/accept/accept_with_deviation/reject/rework — the scm 4.9 vocabulary,
a deliberate superset: nothing writes `rework`). **Evidence order:** `qci_record` sets result +
inspected_date and moves status to `in_progress` — NEVER a terminal status, or `is_locked`
(terminal OR decision-taken) would lock the row out of the decision it is still owed;
`qci_accept` (binds `InspectionAcceptanceForm`, party queryset + verb re-check) and `qci_reject`
move decision AND status together — that save is the moment the row freezes. External/customer
acceptance is `accepted_by_party` → `core.Party` (queryset-scoped, never `_reject_foreign`).

### `QualityDefect` [QDF-] — the punch list
`defect_category` (deliverable-quality vocabulary, distinct from scm's goods categories),
`severity` (scm 4.9's four, max_length 12 for `observation`), `disposition` (open/rework/repair/
resubmit/accept_as_is/reject/deferred). `project_issue` is verb-written only; `qdf_raise_issue`
maps severity critical→critical/major→high/minor→medium/observation→low, re-fetches under
`select_for_update` and re-tests the bridge inside the atomic block. `is_locked` =
resolved|closed|**cancelled** (M1 — a cancelled defect is frozen evidence like its siblings).

### 7.6 verbs — all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `qpl_approve` | login (D1: deliberately not admin-gated — recorded for the product owner) | draft → active, stamps `approved_by/_at` |
| `qpl_supersede` | **tenant_admin** (`@require_POST` ABOVE the admin gate, M2) | active → superseded |
| `qrv_report` | login | planned OR in_progress → reported |
| `qrv_close` | login | reported → closed, stamps `closed_at` |
| `qci_record` | login | live row; result ∈ non-pending RESULT_CHOICES; optional ISO `inspected_date` |
| `qci_accept` | login | result recorded; `InspectionAcceptanceForm`; decision+stamps+`passed` in one save |
| `qci_reject` | login | result recorded; `usage_decision=reject` + `failed` in one save |
| `qdf_resolve` | login | live row; `DefectResolutionForm` (`resolution_note` REQUIRED); stamps resolver |
| `qdf_close` | login | resolved ONLY |
| `qdf_raise_issue` | login | live, unbridged row; mints the `ProjectIssue` atomically, audits both sides |

Register notes: the derived lenses are **pre-scoped from real columns** (`?overdue=1` on
qci/qdf, `?review_due=1` on qpl, `?kind=assurance|improvement` on qrv); an unrecognised `kind`
narrows nothing (never an empty page for a stale URL). The two computed boards follow the
capped single-pass idiom (`_REGISTER_CAP`-capped Python bucketing for the trend — the 7.5
review-M13 ruling; `aggregate(Avg/Count)` for maturity; the acceptance queue renders ≤100 rows
with a DB `.count()` header): `quality_improvement` computes the maturity score (60% scored
reviews' average + 40% defect closure, CMMI-banded, `has_score` gates the card so a 0.0 score
renders "Initial" instead of the no-data state) and `quality_acceptance` derives one row per
WBS deliverable node from its LATEST inspection until it carries a decision. All 19 register
indexes are named (`qpl_/qrv_/qci_/qdf_tnt_*` — migration 0009; the peer's 7.7 took 0007 and
7.5's index migration 0008, so the leaf was conceded per L43). Audit actions ≤ 10 chars with
the verb in `changes`.

## 7.7 Scope & Requirements Management — `ScopeRequirements/`, template slug `scope`

Contract: `.claude/tasks/contract-projects-7.7.md`. Review: `.claude/tasks/review-projects-7.7.md`.
Tests pinned in `.claude/tasks/test-contract-projects-7.7.md`. Scope: the REQUIREMENTS BASELINE —
what was asked for (requirements), what was agreed to be in and out (the scope statement's
boundaries, constraints and assumptions), what changed the agreement (change requests + the CCB
decision), and whether it was actually delivered as agreed (verification + acceptance). Boundaries
ruled at build time: the WBS is **7.2's** (`wbs_node` is a traceability FK, never a second
task table); the budget the creep board costs against is **7.4's** (`cost_impact` is an *estimate
input* on the change row — 7.7 posts nothing to the GL); risks are **7.5's** (`source_change` and
`related_requirement` are read-only lenses); the deliverable acceptance of 7.6's `qci_accept` is
the QC event, while 7.7's `ScopeVerification` is the **requirement-level** acceptance that closes
the traceability loop — they are two different questions and both are needed.

**Everything computed is derived, never stored** — the 7.1 ROI / 7.4 EVM / 7.5 EMV ruling again:
`is_open`, `is_locked`, `is_overdue`, `is_high_impact`, `coverage_pct`, `bar_pct`, every creep
rollup and the whole coverage matrix are Python properties or view-side computation. There is
**no stored score column anywhere in 7.7**.

Model constants kept MODULE-level only when the view needs them too (the 7.5 `PROBABILITY_PCT`
idiom): `HIGH_COST` on the change model (`is_high_impact` compares against it, the creep board
counts `high_impact_count` off it) and `CREEP_LIMIT = 500` in the view (the board's scan cap).

### `Requirement` [REQ-] — what the stakeholder actually asked for
`requirement_type` functional/non_functional/business/technical/regulatory/interface;
`elicitation_method` the eight documented capture techniques (interview/workshop/survey/
user_story/observation/document_analysis/prototype/brainstorm, `max_length=20` — the field is
20 chars because `document_analysis` is 17, review I2 corrected the CONTRACT's 16, not the model);
`priority` is **MoSCoW** (must/should/could/wont — the only priority vocabulary in the module);
`verification_method` is IEEE 1012's four (inspection/analysis/demonstration/test). Lifecycle
`draft → submitted → approved/rejected → implemented → verified` (+`deferred`) is verb-driven
(`status` OFF the form); `STATUS_BANDS` maps each status to a theme badge. `parent` is a self-FK
(the epic/story tree); `wbs_node` is the traceability link to 7.2's work package; `source_party` →
`core.Party` (never a second stakeholder table — 7.1 owns that register); `version` is a
documentation marker only (the real trail is `ScopeChangeRequest`). `is_locked` = implemented|
verified. `clean()` guards `wbs_node` and `parent` onto the same project.

### `ScopeItem` [SCI-] — the scope statement's boundary registry
`item_type` in_scope/out_of_scope/assumption/constraint/dependency — ONE register for all five
because they are all "a claim about the boundary" and the type is a lens (the 7.6
one-object-with-a-kind ruling). `status` **open/validated/realized/retired/violated**;
`is_open` = open|validated (the state where transitions are still legal), `is_locked` =
realized|retired|**violated** — review **C1**: `violated` was missing from `STATUS_CHOICES`
entirely, so the one status that *means the boundary was breached* was unwritable; migration
`0010_alter_scopeitem_status` adds it (and `is_locked` now freezes it like its terminal
siblings — a violated boundary is evidence). `sci_retire` gates on `obj.is_open` (review **I3** —
retiring an already-`realized` item was accepted). `impact_area` is the six-way tag
(schedule/cost/quality/scope/resource/compliance) that lets the register be sliced by what the
boundary protects.

### `ScopeChangeRequest` [SCR-] — what changed the agreement, and the CCB decision
`source` internal/client/regulatory/vendor/technical; `priority` low/medium/high/critical (a
SEPARATE vocabulary from the requirement's MoSCoW — a change is triaged, a requirement is
prioritised, and conflating them was ruled out at contract time); the three impact dimensions
`cost_impact` (Decimal), `schedule_impact_days` (**PositiveIntegerField** — see the seeder gotcha
below), `quality_impact` none/low/medium/high. Lifecycle `draft → submitted → under_review →
approved/rejected → implemented` is verb-driven. `is_high_impact` compares `cost_impact` against
the module-level `HIGH_COST`; the creep board counts `high_impact_count` off it. `decided_at` is
stamped by the approval/rejection verbs and is what the creep board groups by month — an approved
row with no `decided_at` would be invisible to the trend.

### `ScopeVerification` [SVR-] — requirement-level acceptance, the loop-closer
`method` inspection/test/demonstration/analysis/review; `result` pass/conditional/fail;
**`acceptance_status` pending/accepted/rejected/waived** is the decision field and is
verb-written only (`svr_accept` / `svr_reject` / `svr_waive`) — it is deliberately NOT a second
`result`. `svr_reject` requires a written reason (a rejected deliverable without a stated cause
is not a gate, it is a shrug) and `svr_waive` requires an authority note. This model is what makes
the matrix's `verified` count meaningful: a requirement is verified when its domain is verified.

### 7.7 verbs — all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `req_submit` | login | draft/deferred → submitted |
| `req_approve` | **tenant_admin** | submitted → approved (stamps the decision) |
| `req_reject` | **tenant_admin** | submitted → rejected; `RequirementRejectionForm` reason |
| `req_implement` | login | approved → implemented |
| `req_verify` | **tenant_admin** | implemented → verified; `RequirementVerificationForm` |
| `sci_validate` | login | `is_open` → validated |
| `sci_realize` | login (I9 — recorded for the product owner, see below) | `is_open` → realized |
| `sci_retire` | login (I9) | **`obj.is_open` ONLY** (review I3 — realized was wrongly accepted) |
| `scr_submit` | login | draft → submitted |
| `scr_review` | **tenant_admin** | submitted → under_review (the CCB opens the file) |
| `scr_approve` | **tenant_admin** | under_review → approved, stamps `decided_at` |
| `scr_reject` | **tenant_admin** | under_review → rejected; `ChangeRejectionForm` reason |
| `scr_implement` | login | approved → implemented |
| `svr_accept` | login (I9) | pending → accepted; `VerificationDecisionForm` |
| `svr_reject` | **tenant_admin** | pending → rejected; mandatory written reason |
| `svr_waive` | **tenant_admin** | pending → waived; mandatory authority note |

**Decorator order is load-bearing (review C2).** `@tenant_admin_required` internally applies
`@login_required`, and decorators apply bottom-up — so on an admin-gated verb the stack must read
**`@login_required` → `@require_POST` → `@tenant_admin_required`** (top to bottom). If
`@tenant_admin_required` sits ABOVE `@require_POST`, a *member's* GET is answered **403 instead of
405** — the role check fires before the method check. The 7.7 fix moved all 8 gated verbs to the
correct order, and `test_scope_security.py` asserts **both actors** get 405 (the regression net).
This is the opposite of a bug: 405 is house policy, and only the *order* was wrong.

Audit: every verb captures `previous = obj.status` BEFORE mutating and logs
`{"verb", "from", "to"}` inside the atomic block where one runs; actions ≤ 10 chars
(`core.AuditLog.action` is `varchar(10)`).

Register notes: derived lenses are **pre-scoped in the views from real columns** (a Python
property cannot be filtered) — `?status=`, `?priority=`, `?requirement_type=`,
`?elicitation_method=` (review I5 — the filter existed but was never wired into the view's
`filters` list, so the choice list rendered a dead dropdown) on `req_list`; `?item_type=`,
`?status=` on `sci_list`; `?status=`, `?source=` on `scr_list`. The `scope_matrix` board is the
only computed page and it is **grouped aggregates, not row fan-out** (review I7/I8): the coverage
strip and the matrix rows use `.values(...).annotate(Count("id"))` (one query per relation, not
one per row), and the creep scan is a `.values(...)`-sliced query capped at
`CREEP_LIMIT = 500` rows in id-descending order; `creep_max` is the max `cost_total` over that
slice and `bar_pct` is `round(cost_total / creep_max * 100, 1)` as a `Decimal` (the 0-safe branch
returns float `0.0` — the tests pin both types). The board's context keys (`coverage`,
`matrix_rows`, `creep_rows`, `creep_max`, `creep`, `scope_summary`) are all computed in one pass
over the tenant's registers; nothing is snapshotted.

Register indexes: `req_tnt_status_idx`, `req_tnt_project_idx`, `sci_tnt_project_idx`,
`sci_tnt_type_idx`, `scr_tnt_status_idx`, `svr_tnt_status_idx`-class named indexes came with the
build in migration `0007`; `violated` was added by `0010_alter_scopeitem_status` (chained onto the
7.6 leaf `0009_...`, the L53 discipline — read the disk leaf, never assume the number).

## 7.8 Task & Work Management — `TaskWorkManagement/`, template slug `taskwork`

Contract: `.claude/tasks/contract-projects-7.8.md` (§9 carries the post-review amendments).
Review: `.claude/tasks/review-projects-7.8.md`. Tests pinned in
`.claude/tasks/test-contract-projects-7.8.md`. Scope: the EXECUTION layer — how the plan is
actually worked: who is doing it, how urgent it is, how far along, what is blocking it, and the
checklist of the work inside a task.

**The defining ruling is that 7.8 EXTENDS `ProjectTask` IN PLACE — there is no second task
table.** The six execution fields (`assignee`, `priority`, `moscow`, `is_urgent`, `is_important`,
`percent_complete`) and the two verb-written stamps (`actual_start`, `actual_end`) live on 7.2's
row; sub-tasks already work through its `parent` self-FK. A `WorkTask`/`TaskExecution` table
would be the L29/L36 bug. `owner` stays the accountable manager, `assignee` is the doer, and team
bookings remain 7.3's `ResourceAllocation`.

Boundaries ruled at build time: the WBS is **7.2's** (7.8 only adds columns to it); team capacity
is **7.3's**; money is **7.4's** (there is no cost column here); risks are **7.5's**; the sprint
cadence is **7.13's** (the board is continuous flow, not scrum); WIP-limit VALUES are **7.19**
master data (the board counts and badges ship, the limits do not); auto-rescheduling and resource
levelling are **7.16/7.17** (7.8 flags conflicts, it never moves dates).

### `TaskChecklistItem` [TCL-] — the checklist inside a task
`task` CASCADE, `label`, `sequence`, `is_done` + `done_by`/`done_at`. **The tick is the POST-only
`tcl_check` toggle and the ONLY writer** of those three — `is_done`/`done_by`/`done_at` are on no
form (the `TaskChecklistItemForm` field list is `["task", "label", "sequence"]`). One writer per
direction: the same verb ticks and un-ticks, clearing the stamps on the way back. Indexes
`tcl_tnt_task_idx`, `tcl_tnt_done_idx`.

### `TaskBlock` [TBK-] — the manual-blocker evidence row
`reason` REQUIRED and `unblock_criteria` REQUIRED (a block with no stated reason or no exit is
not evidence), plus the verb-written trail `blocked_by`/`blocked_at`/`unblocked_by`/
`unblocked_at`/`resolution_note`. **`is_active` is `unblocked_at is None`** — derived, never a
column. The row is minted ONLY by `tsk_block` and closed exactly once by `tsk_unblock`; there is
no ModelForm and the admin refuses add/delete (M4) because an evidence row with no verb behind it
is not evidence. One open blocker at a time, so `is_manually_blocked` always names THE row.
Indexes `tbk_tnt_task_idx`, `tbk_tnt_unblocked_idx`.

**"Blocked" is DERIVED from two independent halves (Ruling 3):** `is_dependency_blocked` walks
`predecessor_links` (an unfinished FS predecessor holds the finish; an un-started SS predecessor
holds the start; FF/SF never block) and `is_manually_blocked` reads the open TBK row.
`is_blocked` is their OR — **never a stored boolean** (a stored one goes stale and has no
evidence trail).

### The in-place execution extension on `ProjectTask`
`priority` low/medium/high/critical; **`moscow` is NULLABLE** (must/should/could/wont — `None` is
the board's "Unclassified" bucket and the priority page's unclassified group, so nullability is
load-bearing); `is_urgent`/`is_important` feed the derived `eisenhower_quadrant`
(do_first/schedule/delegate/eliminate); `percent_complete` is the attestation and
`actual_start`/`actual_end` are `editable=False` (verb-written only). Indexes
`tsk_tnt_assignee_idx`, `tsk_tnt_priority_idx`.

### 7.8 verbs — all `@require_POST`; GET answers 405

| Verb | Gate | Requires |
|---|---|---|
| `tsk_start` | login | `planned` → in_progress; refuses while blocked; stamps `actual_start` once |
| `tsk_complete` | login | `in_progress` → done; refuses while blocked; stamps `actual_end` + `percent_complete=100` |
| `tsk_block` | login | **refuses terminal statuses** (M8) and an already-open block; mints the TBK row |
| `tsk_unblock` | login | an OPEN block only; writes the unblock trail exactly once |
| `tsk_bulk_update` | login | status/assignee/priority over the multi-selected ids, PER-ROW gating + one audit entry per applied field |
| `tcl_check` | login | toggles the item's tick + stamps (the only writer) |
| `tsk_execute` | login | the one GET+POST route — the six execution fields via `TaskExecutionForm` |

**`tsk_block` refuses terminal work** (`done`/`cancelled`) — a finished task has nothing left to
hold — and the check is **re-tested inside the `select_for_update` block** alongside the
one-open-blocker re-test, so a concurrent complete/cancel cannot slip a block past the gate.
`tsk_bulk_update` mirrors both rules row-by-row: a transition to a terminal status is refused for
any row with an open block, so a block can never outlive the work it was holding.

**`tsk_bulk_update` is bounded and cheap (review I9).** The POST accepts at most
`_BULK_CAP = 500` ids and tells the user when it truncated; every id resolves through ONE
tenant-scoped `pk__in` fetch (a forged id simply is not in the map and is counted refused); the
old assignee `User` is loaded ONLY in the audit branch that needs its label; and the open-block
row is fetched once per row and reused for both the gate and the refusal message.

**`TaskExecutionForm` guards attested history (M9).** A `cancelled` row refuses execution-field
writes outright; a `done` row has `clean()` restore its stored `percent_complete` rather than
rejecting the form — `tsk_complete` wrote 100 as evidence and a form must not quietly lower it,
while the other five fields stay editable. This is the ONLY execution write surface: I2's ruling
keeps the six fields off `TaskForm` (whose `Meta.fields` is pinned to the exact 13 by 7.2's
tests).

Register notes: the three computed pages derive everything on read — no snapshot table anywhere.
`task_board` buckets the live rows into the four status columns with a ready queue and WIP
badges; `task_priority` groups by MoSCoW and buckets the Eisenhower quadrants, and **both bucket
live work only** (`planned`/`in_progress` — done and cancelled drop out, the I6 amendment);
`gantt_timeline` resolves its window from the union of planned dates and draws the bars with the
resolved `start`/`end` on each bar dict. **A blocked card offers no Start/Complete** — the action
block renders a disabled button instead of a guaranteed-refusal click (I10). All three pages
flash a message when a supplied `?project=`/`?assignee=` id is not in the workspace, while still
degrading to the unfiltered view with no 500 (M11).

**The panels on `tsk_detail` consume view-computed context, not the model's re-querying
properties (I7).** `tsk_detail` prefetches `checklist_items` (+`done_by`), `blocks` (+both stamp
users), and both link sets (+the counterpart task) once, computes `checklist_progress` and
`obj.active_blocks` off those caches, and passes the link lists as context; the three
`_task_*_panel.html` includes read those keys. Calling `obj.checklist_progress` (2 COUNTs) or
`obj.is_manually_blocked` (`.filter().exists()`) would bypass the prefetch cache — measured
**31 → 13 queries** on the seeded probe task. The board/priority prefetch chains the join
(`Prefetch("predecessor_links", queryset=TaskDependency.objects.select_related("predecessor"))`)
rather than using `__`-nesting, which costs two queries where one suffices (M14).

## 7.9 Collaboration & Communication — `CollaborationCommunication/`, template slug `collab`

Contract: `.claude/tasks/contract-projects-7.9.md` (§10 carries the build amendments).
Review: `.claude/tasks/review-projects-7.9.md`. Tests pinned in
`.claude/tasks/test-contract-projects-7.9.md`. Scope: the CONVERSATION layer — the five NavERP.md
bullets collapse to **five entity files carrying SEVEN tables plus one computed page**:

| Bullet | Artifact |
|---|---|
| Team Messaging & Channels | `Channel` [CHN-] + `ChannelMessage` [CHM-] |
| Document Sharing & Co-Editing | `DocumentShare` [DSH-] |
| Meeting Management | `Meeting` [MTG-] + `MeetingAgendaItem` [AGI-] + `MeetingActionItem` [MAIT-] |
| Notifications & Alerts | `ProjectNotification` [NTF-] |
| Activity Streams & Feeds | computed page `activity_feed` (**no table**) |

**The defining ruling is that 7.9 ships the SHARE, never a second file store.** `DocumentShare`
FKs the existing `core.Document` by string — the repository, folders, metadata and **version
history are 7.10's**. Real-time co-editing is deferred (there is no websocket stack in the repo),
so the honest affordance is an `access_level` plus a single-editor **claim**
(`dsh_claim`/`dsh_release`). Likewise `Meeting.recurrence` merely **DECLARES** the pattern — the
engine that would mint the next occurrence is 7.17's — and `ProjectNotification` rows are minted
by triggers only, with the trigger RULES (and reminders) belonging to 7.17.

**Prefix collisions that are deliberate.** `MSG` is taken by `scm.IntegrationMessage` and `MAI` by
`hrm.MeetingActionItem` (a 1-on-1 action item in another app, `NUMBER_PREFIX = "MAI"`, indexes
`hrm_mai_*`) — hence `CHM` and `MAIT` here. The `hrm` sibling is documented in 7.9's model
docstring and must **not** be renamed or merged.

### `Channel` [CHN-] — the conversation container
`project` CASCADE rn `channels`, `name`, `topic`, `kind` (discussion/announcement),
`is_archived` + `archived_by`/`archived_at`. `unique_together` is
`(("tenant","number"), ("tenant","project","name"))` — a project cannot carry two channels of the
same name. **`is_archived` and both stamps are verb-written by `chn_archive` only**, which is a
single Toggle covering both directions (archiving stamps all three; unarchiving clears all three).
Indexes `chn_tnt_project_idx`, `chn_tnt_archived_idx`. `message_count` is an **annotation on the
list queryset**, never a model property.

### `ChannelMessage` [CHM-] — the threaded message
`channel` CASCADE rn `messages`, `parent` self-FK rn `replies` (one nesting level), `body`,
`mentions` M2M to `AUTH_USER_MODEL` rn `channel_mentions`, `edited_by`/`edited_at`.
`clean()` carries **three** invariants, and the third is the one that is easy to miss:
1. a reply whose parent lives in another channel is refused;
2. a reply whose parent is itself a reply is refused;
3. **a ROOT may not change channel while it has replies elsewhere** — the replies would stay in the
   old channel while the root moves, and because the channel page keys replies by parent inside
   that channel's own message list, they would then render on **neither** channel. User-authored
   content silently disappearing.

`edited_by`/`edited_at` are written by `msg_edit` only. Indexes `chm_tnt_channel_idx`,
`chm_tnt_parent_idx`, `chm_tnt_created_idx`.

### `DocumentShare` [DSH-] — who may do what with an already-stored document
`project` CASCADE, `channel` SET_NULL, `document` FK to `core.Document` rn `project_shares`,
`access_level` (view/comment/edit), `shared_with` SET_NULL, `note`, plus `is_active` +
`revoked_by`/`revoked_at` and the claim pair `claimed_by`/`claimed_at`. Derived:
`is_revoked`, `is_claimed`, and `is_co_editable` = `is_active and access_level == "edit"` — **a
revoked edit share is not co-editable**. `dsh_revoke` is the only writer of `is_active` and, being
a Toggle, clears both revoke stamps on restore; **it also releases any active claim**, because a
revoked share must not stay claimed. Indexes `dsh_tnt_project_idx`, `dsh_tnt_active_idx`,
`dsh_tnt_document_idx`, `dsh_tnt_created_idx`.

### `Meeting` [MTG-] + its two children
`Meeting` carries `kind` (standup/review/steering/workshop/other), `mode`
(in_person/virtual/hybrid), `recurrence` (none/daily/weekly/biweekly/monthly), `status`
(scheduled/in_progress/completed/cancelled), `location`, `scheduled_start`/`scheduled_end`, and the
two verb-written pairs `actual_start`/`actual_end` and `minutes`/`minutes_by`/`minutes_at`.
`is_upcoming` needs BOTH `status == "scheduled"` AND a future start; `is_past` is the start
comparison alone. Indexes `mtg_tnt_project_idx`, `mtg_tnt_status_idx`, `mtg_tnt_start_idx`,
`mtg_tnt_created_idx`.

`MeetingAgendaItem` [AGI-] (`presenter`, `duration_minutes`, `sequence`, `is_covered` +
`covered_by`/`covered_at`) and `MeetingActionItem` [MAIT-] (`assignee`, `due_date`, optional `task`
link to 7.2's `ProjectTask`, `is_done` + `done_by`/`done_at`, `is_overdue`) are both edited on the
meeting detail page and neither has an independent register. `MeetingActionItem.task` is
**optional** — a minute may point at the work it produced, but 7.9 never creates a task.

### `ProjectNotification` [NTF-] — per-recipient delivery
`project` CASCADE, `recipient` CASCADE, `kind` (mention/assignment/due_date/status_change/system),
`title`, `body`, four optional source FKs (`channel`/`message`/`task`/`meeting`) that the feed and
inbox deep-link from, `triggered_by`, `is_read`/`read_at`. Indexes `ntf_tnt_recipient_idx`
(tenant, recipient, is_read), `ntf_tnt_kind_idx`, `ntf_tnt_project_idx`, `ntf_tnt_created_idx`.

**There is no `ProjectNotification` ModelForm and no create/edit route — by design.** Rows are
minted by triggers (`msg_create`/`msg_edit` mentions, the seeder, later 7.17's engine) and
read/closed by `ntf_mark_read`. Unlike 7.8's `TaskBlock`, an inbox row **is** deletable: it is
per-recipient delivery, not shared evidence. And it is **per-recipient in the authorization sense
too** — `ntf_mark_read`, `ntf_delete` and `ntf_mark_all_read` all carry `recipient=request.user`,
so a teammate's row is a **404**, not something you may clear. That was review finding I8: the two
single-row verbs originally scoped by tenant only, which contradicted both the model's docstring
and their own bulk sibling.

### 7.9 verbs — all `@require_POST`; GET answers 405

| Verb | Requires |
|---|---|
| `chn_archive` | Toggle both directions; stamps/clears `archived_by`/`archived_at` together |
| `msg_delete` | redirects to the channel REGISTER (a message has no register of its own) |
| `dsh_revoke` | Toggle; clears both revoke stamps on restore **and releases any claim** |
| `dsh_claim` | `edit` + active + unheld only; re-claiming your own is a no-op; names the holder on refusal |
| `dsh_release` | any member may release (a stale claim must not deadlock the document) |
| `mtg_start` | `scheduled` → in_progress; stamps `actual_start` |
| `mtg_complete` | `in_progress` → completed; stamps `actual_end` |
| `mtg_cancel` | refuses a terminal meeting; `scheduled`/`in_progress` → cancelled |
| `agi_cover` | Toggle; stamps/clears `covered_by`/`covered_at` |
| `mai_toggle` | Toggle; stamps/clears `done_by`/`done_at` |
| `ntf_mark_read` | Toggle; **caller's own row only** (404 otherwise) |
| `ntf_mark_all_read` | bulk over the caller's own unread rows; ONE `UPDATE` + ONE audit entry |
| `ntf_delete` | **caller's own row only** (404 otherwise) |

The three GET+POST form pages are `msg_create`, `mtg_minutes` and the two child creates
`agi_create`/`mai_create` (which take the meeting from the URL pk — `meeting` is excluded from both
child forms). **`mtg_minutes` does not change `status`** — capturing minutes is not completing the
meeting, and `mtg_complete` is.

**Every mutating verb captures `previous` BEFORE mutating and writes its verb into
`changes={"verb": …}`, never into `action`** — `AuditLog.action` is varchar(10), so a verb written
there would truncate.

### `activity_feed` — the merged computed page (no table)
Five capped sources (`ChannelMessage`, `Meeting`, `DocumentShare`, `ProjectNotification`,
`AuditLog`) filtered on `created_at__gte=since` / `at__gte=since`, each `.order_by("-created_at")`
and sliced `[:100]` **in the database** (a real `LIMIT`, so a decade of history costs the same),
merged and sorted in Python, then truncated to 100 rendered entries.

- `?project=` → `as_db_int`, resolved tenant-scoped; an unresolvable id degrades to the
  whole-workspace feed **with a `messages.warning`**.
- `?kind=` → allow-listed against `_FEED_KINDS`; junk is IGNORED.
- `?days=` → allow-listed against `{7, 30, 90}`; junk falls back to 30.
- **The five `counts` are pre-cap window figures for ALL five kinds — `?kind=` narrows the STREAM,
  not the summary.** Zeroing the other four cards when one kind is picked was review finding M3.
- **`counts["audit"]` is 0 under a project lens, and the page says so in visible copy.**
  `core.AuditLog` carries only a GFK and a free-text `target`, so attributing a row to one project
  would be a fabricated fact. That is the one pinned zeroing rule.

### Four Criticals, all caught by the Step-3 verification pass rather than by a reviewer

Worth remembering as a class, because each is invisible to a status-only test:

1. **A Django template filter inside a Python f-string** — `f"{obj.get_status_display()|lower}"`
   in `mtg_start`/`mtg_complete`/`mtg_cancel`'s refusal branches. `NameError: name 'lower' is not
   defined`, i.e. a **500 on the guard path** of all three lifecycle verbs. Use `.lower()`.
2. **`form.save_m2m()` after a committing `form.save()`** in `msg_edit`. `ModelForm.save()` at the
   default `commit=True` calls `_save_m2m()` internally and deliberately does **not** leave a
   `save_m2m` attribute — only `commit=False` does. So every message edit 500'd. The correct
   pairing (used by `msg_create`) is `save(commit=False)` → `obj.save()` → `form.save_m2m()`.
3. **Paginating an UNORDERED queryset.** `annotate()` puts a `GROUP BY` on the query, and Django's
   `QuerySet.ordered` is `False` whenever a GROUP BY is present — so `Meta.ordering` is silently
   ignored and the paginator slices an unordered set, where a row can land on two pages or none
   (`UnorderedObjectListWarning`). `chn_list`/`msg_list`/`mtg_list` all did this; the fix is to
   re-state the model's own ordering with an explicit `.order_by(...)` on the annotated queryset.
   Note this pattern was **new in 7.9** — no pre-7.9 projects list view warns.
4. **A seeder that stops short of a real page 2.** `_collab` created 13 messages where the contract
   pinned ≥16, so the message register could never paginate.

**The lesson for the smoke harness: a page-2 assertion that greps the rendered HTML for the row
prefix is a FALSE PASS.** `Paginator.get_page()` falls back to the last in-range page when
`?page=` overshoots, so the prefix appears even on a single-page register. Assert
`page_obj.paginator.num_pages > 1`, that page 2 carries row numbers page 1 does not, and that no
`UnorderedObjectListWarning` was raised. Also call `setup_test_environment()` in a standalone
script, or `response.context` is `None` and every context-key assertion silently becomes a no-op.

## 7.10 Document & Knowledge Management — `DocumentKnowledgeManagement/`, template slug `documentknowledge`

The **record layer**: the folder tree, the controlled documents with their approved-revision chains,
the tenant-wide standards library and the insight library, plus three computed pages. It reuses the
workspace's existing projects, work packages and milestones; it invents no project and no user.

### What it deliberately does NOT reuse — `core.Document` is untouched

`core.Document` is the generic per-record attachment every module hangs off a `GenericForeignKey`.
It carries **no project FK, no doc type, no status, no owner**, a flat `version` CharField instead of
a chain, and a GFK cannot be `.filter(tenant=…)`-ed, joined or faceted — which makes it an IDOR
surface the moment a register lists it. That is procurement 6.19's recorded rejection, inherited
here verbatim: 7.10 declares its own `ProjectDocument` with **real link FKs** (`projects.ProjectMilestone`,
`projects.ProjectTask`), no import of `core.Document`, no FK to it and no migration against it. 7.9's
`DocumentShare` (which *does* FK `core.Document`) keeps working untouched and is shown on the
document detail page as a **read-only lens** linking out to `?project=`.

### `TimeActivityCode` [TAC-] — standard activities and overhead classification
Choices: `CATEGORY_CHOICES` (direct_project, client_service, internal_overhead, general_admin, training, research_dev).
Carries `code` (uppercased in `clean()`), `name`, `category`, `is_billable_default`, `is_active`, `description`. Unique on `(tenant, code)`.

### `OvertimeRule` [OTR-] — project and tenant overtime policies
Optional `project` FK (null = tenant-wide policy).
Thresholds: `standard_daily_hours` (8.00), `standard_weekly_hours` (40.00).
Multipliers: `daily_overtime_multiplier` (1.50), `weekly_overtime_multiplier` (1.50), `weekend_multiplier` (1.50), `holiday_multiplier` (2.00).
`requires_pre_approval`, `is_active`, `notes`.

### `ProjectOvertimeRecord` [POT-] — overtime claims and rate splits
Linked to `resource` (`ResourceProfile`), `project` (`Project`), optional `project_task`, optional `time_entry`.
Carries `date`, `overtime_hours`, `overtime_type` (daily, weekly, weekend, holiday), `pay_multiplier`, `billable_multiplier`, `is_billable`.
Workflow: `draft` -> `submitted` -> `approved` / `rejected`. Approved/rejected records are locked against edit/delete.
Derived properties: `pay_equivalent_hours`, `billable_equivalent_hours`.

### `ProjectFolder` [PFD-] — the per-project tree

`project` FK (required, CASCADE) · `parent` self-FK (CASCADE, null = root) · `name` · `description` ·
`sequence` · `is_archived`/`archived_by`/`archived_at` (verb-written). `unique_together` on
`(tenant, project, parent, name)` **and** `(tenant, number)`; indexes `pfd_tnt_{project,parent,archived}_idx`.
`clean()` refuses a cross-project parent, a self-parent, a descendant cycle, and two same-named
**root** folders (a MySQL unique index treats NULL parents as distinct, so the constraint cannot
catch those).

**The materialized path and the per-folder document count are COMPUTED, never stored** — the 7.2
WBS `_decorate_wbs` ruling. `pfd_list` decorates the whole tree in memory (depth, `path`, `doc_count`)
from **two** queries total and orders it depth-first by `(sequence, name.lower(), -pk)`; a stored
path would go stale the instant a parent was renamed.

**A folder is organisation, not authorisation.** It grants nobody anything — access is 7.9's
`DocumentShare`, permission matrices are 13.7's, and no code may branch on folder membership to
authorize a thing. Deleting a folder that still holds documents or children is refused outright (the
Deltek PIM "you cannot delete a container that has issued documents" rule); `ProjectDocument.folder`
being PROTECT is the schema-level half of that guarantee.

### `ProjectDocument` [PDM-] — the register row

`project` (required, CASCADE) · `folder` (PROTECT, required) · `title` · `document_type` (11 values:
charter/plan/schedule/report/status_update/minutes/specification/drawing/test_result/handover/other) ·
`classification` (public/internal/confidential — the `core.Document` vocabulary reused on purpose) ·
`owner` (User, SET_NULL) · `tags` (normalized CharField via the shared `normalize_tags()`) ·
`description` · `status` (draft/**expected**/in_review/approved/superseded/archived) · the two real
link FKs `milestone`/`task` (SET_NULL, nullable) · the check-out lock `is_checked_out`/`checked_out_by`/
`checked_out_at` · the retention intent `retention_months`/`review_on` · the archive
`is_archived`/`archived_by`/`archived_at` · the legal hold `is_legal_hold`/`hold_reason`/`held_by`/
`held_at` · the pointer `current_revision_no` (PositiveSmallInteger, **0 = none**) and the search copy
`extracted_text`. `unique_together (tenant, number)`; five `pdm_tnt_*_idx` indexes.

**`expected` is the Deltek PIM document placeholder** — a named slot created *before* the file
arrives. `clean()` allows a blank title only in that state; every other state is a document somebody
has to find by title later. ⚠️ **The field is `CharField(max_length=255)` with `blank=False`, so
`full_clean()` refuses a blank title at the FIELD level before `clean()` ever runs — the relaxation
is currently unreachable and a titleless placeholder cannot be created through a form.** The seeder
therefore creates its placeholder *with* a title ("a named slot"). Recorded for the close-out: either
the field gains `blank=True` (and `0014` needs a sibling `AlterField`) or the `clean()` branch should
be deleted as dead slack — leaving it in place is what a reviewer will read as an inconsistency.

**Derived, never stored:** `is_expected`, `is_locked` (the check-out), `is_live`, `tag_list`,
`retain_until` (**`created_at + 30 * retention_months`** — 30-day months on purpose, so the figure
does not drift with the calendar), `is_retention_due`, `is_review_due`, `status_css`, and
`current_revision` — which **filters `is_approved=True`**. Do not "unify" that filter away: without
it a re-allocated number can put an unapproved file on the record and the register renders a green
*Current* badge beside *Not approved*. (6.19 reproduced that three ways; the filter is the fix.)

### `ProjectDocumentRevision` [PDV-] — the immutable chain

`document` FK (CASCADE, `related_name="revisions"`) · `revision_no` · `file`
(`projects/documents/%Y/%m/`) · `checksum` (SHA-256 of the stored bytes, streamed) · `change_note`
(**the ONLY column editable after creation**) · `is_approved`/`approved_by`/`approved_at` ·
`extracted_text` (**the text of record**) · `extraction_note` · `uploaded_by`.
`unique_together (tenant, document, revision_no)`; index `pdv_tnt_document_idx`.

**There is no `uploaded_at` column** — `TenantOwned.created_at` IS the upload moment.

**The chain is linear and only moves forward.** `revision_no` is allocated by `next_revision_no()`
(one past the highest — a deleted revision leaves a **gap**, and the gap is the honest record) inside
the transaction that takes the **parent's** `select_for_update()`. An upload NEVER moves the pointer
and never approves itself. `pdv_approve` refuses `revision_no <= current_revision_no` and
**re-checks that refusal INSIDE the lock** (the TOCTOU the unique constraint alone cannot catch),
then stamps the row, moves the pointer, copies `extracted_text` up to the parent and lifts a
still-open parent to `approved` — all in one audit-logged transaction. **An older approved revision
KEEPS `is_approved=True` for ever**: it *was* approved, and "only one version is current" is
expressed by the pointer landing on exactly one row, never by un-approving history. `pdv_restore`
rolls **FORWARD** (an older approved revision's file is re-uploaded as a NEW revision), so history is
never rewritten and never deleted.

**Immutability is STRUCTURAL, not a `save()` guard.** There is **no edit url, no edit view and no
edit template** for a revision anywhere; everything but `change_note` is `editable=False` so no
`ModelForm` can surface a column; the only form is `ProjectDocumentRevisionUploadForm` and it is
create-path only. A wrong revision is superseded by the next upload, never amended in place.

**The check-out lock belongs to the PARENT and is cooperative.** `is_checked_out` +
`checked_out_by`/`checked_out_at` are written by `pdm_checkout`/`pdm_checkin` alone. Check-in is open
to **any member on purpose** — a stale lock must not be able to deadlock a document any more than
7.9's stale claim could. Every page that shows it says it is an **in-app signal, not an OS file
lock**. 7.10 refuses an upload while the parent is checked out (the form's `clean()` and the model's
`clean()` both), so "whoever holds the check-out wins" is the whole conflict-resolution story here —
there is no merge tool (13.2 owns branching/redlining).

**Text extraction is honest about its limits and bounded in three ways.** `extract_text()` never
raises; it reads plain-text uploads from a bounded prefix and PDFs through a **lazy `pdfplumber`
import** stopped at `MAX_EXTRACT_PAGES` (60) or `EXTRACT_MAX_CHARS` (200,000), freeing each page's
cache as it goes. A scanned image simply has no text layer — `extraction_note` says so **on the row**
rather than leaving a silently empty column that looks like a bug.

### `DocumentTemplate` [DTM-] — the standards library (bullet 2)

`name` · `category` (charter/plan/schedule/report/status_update/minutes/register/checklist/other) ·
`document_type` (the **same vocabulary** as `ProjectDocument`, so "start from the standard for this
type" is expressible) · `description` · `version` (**CharField** — real template versions read
"2026.1" or "v3 (brand refresh)") · `file` · `is_active` (verb-written by `dtm_publish`, a Toggle) ·
`is_format_locked` (**an INTENT only**) · `owner` · `review_on`.
`unique_together (tenant, name, version)`; indexes `dtm_tnt_{category,active}_idx`.

**Tenant-wide with NO project FK — deliberately.** A standard belongs to the PMO, not to one project;
that asymmetry with `ProjectDocument.project` (required) is the design, and it is what stops the
standard charter format becoming forty copies of itself. **No version chain**: re-publishing edits
the row. Attaching a standard to a project copies it into the repository as a `ProjectDocument`,
where the chain and the retention then apply to the copy.

**`is_format_locked` records an intent a human reads.** Nothing in this sub-module enforces
authorship or formatting, so **no page, label or help text may claim the format is locked**. There is
also no "generate a document from this template" affordance anywhere — merge fields, locked
formatting and co-editing are 13.1's; the honest verb this pass ships is the download link.

**Content-only standards live in `KnowledgeEntry.kind="template"/"standard"`, not here** (Ruling 4).
This register exists for artifacts with a file and a publishable version, so the two registers never
both hold "how we write a charter".

### `KnowledgeEntry` [KNE-] — the insight library (bullet 4)

`title` · `kind` (lesson_learned/retrospective/playbook/checklist/best_practice/template/standard) ·
`summary` · `body` · `category` · `tags` (the same normalizer) · `source_project` (SET_NULL,
nullable) · `document` FK → `ProjectDocument` (SET_NULL) · `owner` · `status` (draft/published/
retired) · `review_on` · `usage_count` · `is_featured`. `Meta.ordering = ["-is_featured",
"-created_at", "-id"]` — **the `-id` tiebreak is load-bearing for deterministic paging**: without it
two rows created in the same second can swap places between page 1 and page 2, so a row repeats on
one page while another vanishes.

**No `FileField`, deliberately.** The attached artifact is a `ProjectDocument` chosen through the FK,
so a playbook PDF goes through the repository's extension allow-list, size cap, checksum, text read
and revision chain. A second upload path here would skip all five and leave the library holding an
unversioned copy of a file that also exists, differently, on a document row. **One artifact, one
place, one history.**

**`usage_count` is a CLICK COUNTER, never a metric and never an audit trail.** It counts presses of
"use this" and nothing else: it does not know who pressed it, it is not evidence that a lesson was
applied, and it can never be reconciled against anything. `kne_use` increments it with an atomic
`F("usage_count") + 1` — a read-modify-write silently drops one of two concurrent presses. It is
**off the form**, so no save path can reset somebody's counter to zero. **`is_featured` is a SHELF,
never a permission**: it decides what surfaces first, it gates nothing, and no code may branch on it.

**Not machinery.** Nothing stored here executes — it raises no risk, opens no issue and schedules no
review. 7.5's risk register and 7.6's defect rows each keep their OWN `lessons_learned` field on the
row where the lesson was dispositioned; this library is where a lesson becomes **findable and
reusable across projects**, which is the 7.5/7.6 ruling quoted back at itself. Wikis (13.17),
semantic search / auto-tagging (13.5/13.6) and AI summaries (Module 23) stay where they are.

### Retention — a documented INTENT plus audited verbs

`retention_months` feeds the computed `retain_until`; `review_on` feeds `is_review_due`; `pdm_archive`
is a **Toggle** over `is_archived` + both stamps; `pdm_hold`/`pdm_release` are a Toggle over
`is_legal_hold` + `hold_reason` + both stamps. **A hold outranks the archive**: it blocks archive AND
delete in the model's `clean()` *and* on the delete view (three surfaces, deliberately), and it also
refuses a new revision approval. **Nothing in 7.10 deletes anything on a schedule** and no page may
claim it does — automatic destruction, an immutable vault and proof-of-deletion artefacts are
**13.9/13.14's**.

`doc_retention` recomputes everything against `timezone.localdate()` on every load (a stored "is due"
flag goes stale at midnight — the 6.19 ruling) and its **Run is a button, not a cron**: there is no
scheduler and no mail worker in this repo, so `doc_retention_run` raises **in-app rows only** into
7.9's inbox. **Idempotency comes from the TITLE**, because `ProjectNotification` has no link column
and no open/closed state machine — it has a recipient, a kind, a title and `is_read`, so the dedupe
key is `(tenant, kind="due_date", recipient, title, is_read=False)` with the document's **number AND
its date** inside the title. The same window state therefore cannot raise twice, while a genuinely
changed date raises a fresh row; the authoritative re-check runs INSIDE the per-document row lock, so
two concurrent Runs cannot both raise for one document.

### Search — a denormalized copy with a stated caveat (Ruling 6)

`ProjectDocument.extracted_text` is the parent's search copy and has **exactly two writers**: the
`pdv_approve` verb and the `pdm_reindex` Run. Do not "fix" this into a live join — the copy is the
feature. `pdm_list` deliberately does **not** pass `extracted_text` to `crud_list`'s `search_fields`:
it applies its own `_search()` BEFORE `crud_list` (number/title/tags always, the TextField copy only
from **4 characters**) and passes `search_fields=[]`, because `apply_search` no-ops on an empty field
list. A 1–3 character `?q=` would otherwise sweep a TextField twice per matching search (the
Paginator's COUNT, then the page) for results nobody wanted. Every page says plainly that a scan has
no text layer, so an empty result is never a mystery.

### The three computed pages (no table of their own)

`doc_repository` (the sub-module landing page: ten tiles + the by-type lens + the ten most recent
rows, every figure a single aggregated COUNT computed on read) · `doc_retention` (the queue, the four
figures, the Run) · `kne_search` (title/summary/body/tags/category from ONE character — the
4-character rule governs a stored file copy, **not** prose a person typed — with a featured-first
shelf and an empty state that **names the fields it searched**).

### 7.10 verbs — all `@require_POST`; GET answers 405

`pdm_{checkout,checkin,archive,hold,release,reindex}` · `pfd_archive` · `dtm_publish` ·
`kne_{use,publish}` · `pdv_{approve,restore,delete}` · `doc_retention_run`. Five of them are
**Toggles** whose un-doing goes through the SAME verb and the same audit row (`pdm_archive`,
`pfd_archive`, `dtm_publish`, `pdm_hold`/`pdm_release`, `kne_publish`). Every verb writes an
`core.AuditLog` row with the verb in **`changes`**, never in `action` (varchar(10)).

### Three defects this pass found in its own already-committed backend

Worth reading before touching any of these three, because each was invisible until a template
exercised it:

1. **`pdm_list` applied only `?q=`.** The seven-select filter bar rendered and filtered *nothing*.
   It now hands the whole `filters` spec to `crud_list` — which is where the L11 guards live (a junk
   enum is IGNORED rather than silently emptying the register; `?folder=0` is not a pk and is
   skipped). Hand-rolling that loop means hand-rolling those guards.
2. **`kne_search` raised `NameError: name 'Q' is not defined` on every non-empty `?q=`.** `Q` was
   never imported; `views/_common.py` exports `crud_*` and `write_audit_log` but **no** `Q`/`F`, so
   any view using them must import them explicitly. A hard 500 on the sub-module's own search page.
3. **`ProjectDocumentForm` left `project` editable** on an existing instance while narrowing
   `folder`/`milestone`/`task` from `self.instance.project_id` — the OLD project. Changing the
   project therefore left every folder on the form failing "Select a valid choice", with no way to
   recover. The field is now `disabled` on edit, which is what the form's own docstring already
   claimed ("a document never moves between projects"); Django reads a disabled field's value from
   the instance, so a crafted POST cannot move it either.

**Plus one pre-existing 7.9 defect found while smoking the module overview:**
`_cc_activityfeed` was imported into `apps/projects/urls/__init__.py` but **never concatenated into
`urlpatterns`**, so `projects:activity_feed` raised `NoReverseMatch` and took `/projects/` — the
module landing page, which every 7.10 breadcrumb hangs off — down with it. Three templates reverse
that name. Measured before/after: reverting the one-line fix leaves 7.9's own
`test_collab_security.py::test_collab_anonymous_is_redirected_to_login[activity_feed-None]`
**failing on `main`**; with the fix it passes. **When adding a url module, the import and the
concatenation are two separate edits — grep for the `+ _xx_` line, not just the import.**

### As-built (2026-09-16)

5 models · 7 url modules · 40 route names (`pfd_`/`pdm_`/`pdv_`/`dtm_`/`kne_` + `doc_repository`/
`doc_retention`/`doc_retention_run`) · 22 templates · migrations `0014`–`0016` · `_docmgt` seeder
block. Verified: `temp/smoke_710.py` **169 checks / 0 failures**.

**The close-out ran and found 53 things.** Six serial reviewers produced **5 Critical, 22 Important,
26 Minor** (plus 18 explicit no-action rows) in `.claude/tasks/review-projects-7.10.md`; `code-fixer`
pass 1 closed **C1–C5 and I1–I22** (26 fixed, 1 skipped, 0 refuted) across 71 commits. The five
Criticals are worth knowing before touching this sub-module, because four of them are silent:

- **C1** — the upload verb must read `extract_text(revision.file)` **after** `save()`, never the raw
  `UploadedFile`: the raw object has no `.path`, the never-raising extractor returns
  `("", NOTE_UNREADABLE_PATH)`, and `pdv_approve` then **overwrites** the parent's search copy with
  that empty string. The seeder's order is the correct one.
- **C2** — `ProjectFolder._is_descendant_of()` is the cycle guard, and it is only correct with
  `seen = set()` and the equality test **before** the membership check; seeding `seen` with `self.pk`
  makes it structurally unable to return `True`, and a folder cycle then makes `_decorate`'s
  `walk(None, …)` drop the whole branch from the tree without an error.
- **C3** — never interpolate a user-authored string into a single-quoted JS literal inside an
  `onsubmit`: HTML escaping does not protect an inline-handler attribute, because it is
  character-reference-decoded before the browser compiles it. **`|escapejs`, always** (lesson **L42**;
  this was its third recurrence).
- **C4** — `.svg` must not be on an upload allow-list while `MEDIA_ROOT` is served unauthenticated
  with `Content-Disposition: inline`: the script runs on the site origin for anonymous visitors. The
  list is now imported from `core.forms.ALLOWED_DOC_EXTENSIONS` and extended, never forked.
- **C5** — `AuditLog.action` is `varchar(10)` with `choices` that `.create()` never validates. A
  longer action is silently truncated on a non-strict MySQL and raises `DataError` (a 500) on a
  strict-mode one. The verb goes in `changes`; the action stays `create`/`update`/`delete`.

**Still open — two carried items and one gap:**

- **Carried, cross-module (do NOT fold into a 7.10 fix):** the anonymous `/media/` handler in
  `config/urls.py` (the enabling half of C4 — one authenticated media view fixes 14 modules), and
  the repo-wide over-length `AuditLog.action` sweep (25 other sites, mostly procurement 6.19's).
- **Close-out completed (Pass 2):** `M1`–`M26` are all resolved and checked off in `.claude/tasks/review-projects-7.10.md`. The `docmgt_*` conftest block and the four `test_docmgt_{models,forms,views,security}.py` lanes are fully implemented and passing 100% green (120 tests passed, 0 failures).

## Routes (`app_name = "projects"`, 303 names)

`overview` · `prq_{list,create,detail,edit,delete}` · `prj_…` · `pst_…` · `pko_…` plus the verbs ·
7.2: `tsk_{list,create,detail,edit,delete}` + `tsk_tree` (literal route `tasks/tree/`) ·
`dep_…` · `mst_…` · `bsl_…` (path prefixes `tasks/ dependencies/ milestones/ baselines/` — first
segments disjoint from 7.1's, so the url concatenation cannot shadow).
7.3: `rsp_{list,create,detail,edit,delete}` - `ral_...` + `ral_{assign,substitute,commit,complete,cancel}` -
`rte_{list,create,detail,edit,delete,submit,approve,reject}` + `rte_approve_week` - `capacity_demand`
(path prefixes `resource-profiles/ allocations/ time-entries/ capacity-demand/` - disjoint literals).
7.4: `pbl_{list,create,detail,edit,delete}` · `bvr_…` + `bvr_{submit,approve,reject,activate}` ·
`cca_{list,create,detail,edit,delete}` · `pex_…` + `pex_{post,void}` (path prefixes
`budgetlines/ revisions/ controlaccounts/ expenses/` — disjoint literals).
7.5: `rsk_{list,create,detail,edit,delete}` + `rsk_{realize,close,reopen}` ·
`rra_…` + `rra_complete` · `iss_…` + `iss_{escalate,resolve,close}` · `esc_…` (full CRUD trio,
no verbs) · `risk_analysis` + `risk_monitoring` (path prefixes `risks/ responses/ issues/
escalations/ risk-analysis/ risk-monitoring/` — disjoint literals).
7.6: `qpl_{list,create,detail,edit,delete}` + `qpl_{approve,supersede}` ·
`qrv_…` + `qrv_{report,close}` · `qci_…` + `qci_{record,accept,reject}` · `qdf_…` +
`qdf_{resolve,close,raise-issue}` · `quality_improvement` + `quality_acceptance` (path prefixes
`quality-plans/ quality-reviews/ inspections/ defects/ quality-improvement/
quality-acceptance/` — disjoint literals).
7.7: `req_{list,create,detail,edit,delete}` + `req_{submit,approve,reject,implement,verify}` ·
`sci_…` + `sci_{validate,realize,retire}` · `scr_…` +
`scr_{submit,review,approve,reject,implement}` · `svr_…` + `svr_{accept,reject,waive}` ·
`scope_matrix` (path prefixes `requirements/ scope-items/ scope-changes/ scope-verifications/
scope-matrix/` — disjoint literals).
7.10: `pfd_{list,create,detail,edit,delete}` + `pfd_archive` ·
`pdm_{list,create,detail,edit,delete}` + `pdm_{checkout,checkin,archive,hold,release,reindex}` ·
`pdv_{list,compare,upload}` + `pdv_{approve,restore,delete}` ·
`dtm_{list,create,detail,edit,delete}` + `dtm_publish` ·
`kne_{list,search,create,detail,edit,delete}` + `kne_{use,publish}` ·
`doc_repository` · `doc_retention` + `doc_retention_run` (path prefixes `doc-folders/ documents/
document-revisions/ document-templates/ knowledge/ document-repository/ document-retention/` —
disjoint literals; within `knowledge/` the literal `search/` precedes the `<int:pk>/` ones and
within `document-revisions/` the literal `compare/` does the same). `pdv_upload` is nested under the
**document's** pk (`document-revisions/<int:document_pk>/upload/`) because an upload is always an
upload ONTO a specific document — the form carries no document chooser of its own.

**`req_amendment_create` is NOT 7.7's** — that name belongs to **procurement 4.1**
(`procurement:req_amendment_create`, prefix `requisitions/`). Both apps use a `req_` name prefix,
which is safe only because the namespaces differ; when enumerating "7.7 routes" always scope to the
`projects` namespace or you will pick up 4.1's `req_*` names.
7.8: `tsk_{execute,start,complete,block,unblock}` + `tsk_bulk_update` (**REUSES 7.2's `tasks/`
segment** with disjoint leaf literals — `execute|start|complete|block|unblock|bulk-update` cannot
collide with 7.2's `tree|add|edit|delete`, and the literal `tasks/bulk-update/` is listed FIRST) ·
`tcl_{list,create,detail,edit,delete}` + `tcl_check` · `tbk_{list,detail}` (read-only register —
no CRUD) · `task_board` + `task_priority` + `gantt_timeline` (path prefixes
`checklist-items/ blocks/ task-board/ task-priority/ gantt-timeline/`).
7.9: `chn_{list,create,detail,edit,delete}` + `chn_archive` ·
`msg_{list,create,edit,delete}` · `dsh_{list,create,detail,edit,delete}` +
`dsh_{revoke,claim,release}` · `mtg_{list,create,detail,edit,delete}` +
`mtg_{start,complete,cancel,minutes}` · `agi_{create,edit,delete,cover}` ·
`mai_{create,edit,delete,toggle}` · `ntf_{list,detail,mark_read,delete}` + `ntf_mark_all_read` ·
`activity_feed` (**eight new first segments** — `channels/ messages/ shared-documents/ meetings/
agenda-items/ action-items/ notifications/ activity-feed/` — all disjoint from the 38 pre-existing
segments and from each other, with no converter in any first component).
Within each 7.9 module the literal routes precede the `<int:pk>/` routes, and
`notifications/read-all/` is listed **before** `notifications/<int:pk>/` even though `read-all`
cannot match an int converter (belt and braces, and it keeps the module readable).

**The 15 POST-only 7.1 verbs are `@require_POST`, so a GET returns 405, not 302** — that is the house
pattern, not a bug. 7.2 adds three more, all `@require_POST` + `@tenant_admin_required`:

| Verb | Requires |
|---|---|
| `mst_achieve` | not achieved/cancelled — stamps `actual_date` exactly once |
| `bsl_activate` | type `baseline`, not already active |
| `bsl_promote` | type `what_if` — snapshots, freezes, activates |

7.2's plain CRUD is login-only, but **frozen baselines refuse `bsl_edit`/`bsl_delete` with a
redirect + message** — and `BaselineForm` locks `baseline_type` on edit, so the promote verb is the
only what_if→baseline path.

| Verb | Gate | Requires |
|---|---|---|
| `prq_submit` | login | draft / needs_information |
| `prq_approve` | **tenant_admin** | `DECISION_STATUSES` |
| `prq_reject` | **tenant_admin** | `DECISION_STATUSES` |
| `prq_return_for_information` | **tenant_admin** | not draft/converted; **voids the decision stamps** |
| `prq_convert` | **tenant_admin** | `approved`, not already converted |
| `prj_submit_charter` | login | charter draft/rejected, project not terminal |
| `prj_approve_charter` | **tenant_admin** | charter `submitted`, project not terminal |
| `prj_delete` | login | **refused while `charter_status == "approved"`**; reopens the source request |
| `pko_schedule` | login | needs a `meeting_date` |
| `pko_mark_held` | **tenant_admin** | `scheduled` |
| `pko_complete` | **tenant_admin** | `held` **and** an approved charter |
| `pko_mark_baseline_set` | **tenant_admin** | not planned/scheduled |

`prq_edit` and `prj_edit` and `pko_edit` carry **post-attestation edit locks** — once decided /
charter-approved / ceremony-attested, the row is not editable. This is the module's evidence model:
*you cannot forge the signature, so you must not be able to change what it signs.*

## Templates — `templates/projects/<submodule>/<entity>/{list,detail,form}.html`

Entity folders `initiation/{projectrequest, project, projectstakeholder, projectkickoff}/`,
`planning/{task, taskdependency, milestone, schedulebaseline}/`,
`resource/{resourceprofile, resourceallocation, resourcetimeentry}/`,
`cost/{budgetrevision, costcontrolaccount, projectbudgetline, projectexpense}/`,
`risk/{projectrisk, responseaction, issue, escalation}/` and
`quality/{qualityplan, qualityreview, deliverableinspection, qualitydefect}/`, plus
`scope/{requirement, scopeitem, scopechange, scopeverification}/` and the sub-module-root board
`scope/scope_matrix.html` (the folder names are `scopechange`/`scopeverification` — NOT
`scopechangerequest`/`scopeverification`; match the on-disk names), plus
`taskwork/{checklistitem, block}/{list,detail,form}.html` and the three computed pages
`taskwork/{task_board, task_priority, gantt_timeline}.html` — plus the three panel partials
`taskwork/_task_{blocks,checklist,dependencies}_panel.html`, which are `{% include %}`d by
`planning/task/detail.html` (they read the host view's context keys, never a manager of their
own), plus
`templates/projects/overview.html` at the app root, the recursive
`planning/task/{tree.html,_tree_node.html}` WBS pair (depth-capped, walks `node.kids`) and the
standalone boards `resource/capacity_demand.html`, `risk/risk_analysis.html`,
`risk/risk_monitoring.html`, `quality/quality_improvement.html`,
`quality/quality_acceptance.html` and `scope/scope_matrix.html` (sub-module root, rule 6), plus
`collaboration/{channel, message, documentshare, meeting}/{list,detail,form}.html` and
`collaboration/{notification/{list,detail}.html, activity_feed.html}` — where `activity_feed.html`
stands **FLAT at the `collaboration/` root** (the computed-page rule) alongside
`collaboration/meeting/minutes.html` (a secondary entity-action page, the
`cost/bank_transaction/import.html` idiom) and the two child forms under
`collaboration/meeting/{agendaitem,actionitem}/form.html`. **7.9 introduces the repo's first
THREE-LEVEL template nesting** (`collaboration/meeting/agendaitem/form.html`), which the contract
authorised explicitly; the child forms sit under their parent's folder because they have no
independent register. The channel page and the feed each carry a small **page-local** CSS block
(the `collab-` prefix, mirroring 7.8's `tw-` precedent) — self-contained, and not yet promoted into
`theme.css` because no second page needs them.
7.10 adds `documentknowledge/{projectfolder, projectdocument, projectdocumentrevision,
documenttemplate, knowledgeentry}/{list,detail,form,delete}.html` — **`delete.html` is a fourth page
file in every entity folder here**, because every one of the five models has a POST-only delete view
with a refusal the page has to explain up front. Three pages stand at the sub-module root rather than
in an entity folder: `documentknowledge/overview.html` (the sub-module landing page, which doubles as
the entity-less repository overview), `documentknowledge/retention.html` and
`documentknowledge/knowledgeentry/search.html` — the computed-page rule. `projectdocumentrevision`
carries no `detail.html` (a revision has no page of its own: the chain renders inside its parent's
detail page) and instead carries `compare.html`, a secondary entity-action page (the
`cost/bank_transaction/import.html` idiom). `knowledgeentry/search.html` is the library's second
lens over the same rows and lives inside the entity folder because it is the entity's page, not a
board.
Extend `base.html`; colour-named theme.css
badges only (`badge-green/-red/-amber/-info/-muted/-slate` — the semantic `-success/-warning/
-danger` variants **do not exist** and render unstyled; the alignment class is `text-right` —
`ta-right` is NOT defined, review I4).

## Seeder — `seed_projects`

Idempotent, per-tenant guarded, and the 7.2 block has its OWN guard (an already-seeded 7.1
workspace still gets its planning rows). Creates **9 ProjectRequests / 3 Projects /
6 ProjectStakeholders / 2 ProjectKickoffs per tenant** (Acme + Globex) plus `core.Activity` rows,
and — 7.2 — a stage-sized plan per project: the ACTIVE project gets an 11-node WBS, a 9-link
dependency network whose longest chain is the critical path, 3 milestones (one achieved gate) and a
frozen baseline + what-if; the chartered project a 5-node WBS, 2 links, an in-review gate and a
what-if; the draft 3 sketch nodes and 3 planned milestones (no commitments). 7.3 (own guard):
**5 ResourceProfiles / 10 ResourceAllocations / 16 ResourceTimeEntries per tenant** - internal
rows from the workspace's EmployeeProfiles (capacities 40/40/32/24) + a windowed contractor, all
six booking statuses, all three magnitude units, both placeholder kinds (project- and
request-linked), a released->successor chain, and entries in all four statuses across three ISO
weeks (the submitted trio is the approval queue; RAL-00001's 48h/wk keeps the over-allocation
alert alive). 7.4 (own guard): **4 BudgetRevisions / 31 ProjectBudgetLines / 3 CostControlAccounts /
12 ProjectExpenses per tenant** — an approved-and-activated revision 0 per planned project (it IS
the baseline), a draft sketch revision on the draft project, a pending-approval scope change
(`amount_delta` +50,000.00), lines across all seven categories anchored to the WBS work
packages, one CA per active-project deliverable tuned so CA-1 renders **over** (AC 160,000 vs EV
147,250), CA-2 **watch** (CPI 0.97) and CA-3 **under** (no actuals — CPI None), and expenses in
every entry type and status (PO/invoice STRINGS as soft references, one void, one draft). 7.5
(own guard): **17 ProjectRisks / 7 RiskResponseActions / 7 ProjectIssues / 2 IssueEscalations per
tenant** (12 risks on the active project, 5 on the chartered one) covering all nine categories,
both threat/opportunity values, all four severity bands and all six statuses — one realized risk
carrying the issue the realize verb would have minted, one closed with a lesson, three with a
past review date — plus response actions on the top risks (one completed, one overdue), seven
issues across all four severities and six statuses (one two-step escalation path: level 1 → 2,
one resolved with lessons), and issues seeded so the `?escalated=1` queue is alive. 7.6 (own
guard): **4 QualityPlans / 6 QualityReviews / 6 DeliverableInspections / 6 QualityDefects per
tenant** — deliverable-anchored active plans (one superseded, one draft), reviews across all six
types with one overdue improvement action and maturity scores on the assessed rows, inspections
across all five types with one signed off (party acceptor + conditions note) and one
failed-and-pending, and defects across the severities/dispositions (two resolved/closed with
stamps and lessons, one bridged to a seeded issue, the rest open so the acceptance board's
punch-list counts are non-zero); identified dates spread over ~2 months for the trend. 7.7 (own
guard): **15 Requirements / 12 ScopeItems / 9 ScopeChangeRequests / 9 ScopeVerifications per
tenant** (12 requirements on the active project, 3 on the chartered one) — covering every
`requirement_type`, every elicitation technique, all four MoSCoW priorities and all seven
statuses, with **three rows deliberately left untraced** (no `wbs_node`) so the coverage gap list
is non-empty and three approved/implemented rows so the "never verified" gap is too; scope items
across all five `item_type`s (boundaries, out-of-scope, assumptions, constraints, dependencies)
and all five statuses including a `violated` one; change requests across all six statuses with
the approved rows carrying cost + schedule + quality impacts so all three creep dimensions are
non-zero (one crosses `HIGH_COST`), `decided_at` stamped on every decided row because the creep
board groups by decision month; and verifications across all three `result`s and all four
`acceptance_status`es including a waived gate and a rejected deliverable with its mandatory
written reason. 7.8 (own guard): **20 work packages extended for execution / 20 checklist items /
2 block rows per tenant** — the extension writes the six execution fields across every priority,
all four MoSCoW values PLUS an unclassified row (the first work package of each project, so the
board's "Unclassified" bucket and the priority page's unclassified group are both non-empty), all
four Eisenhower quadrants, `percent_complete` honest to the row's status (done at 100, in_progress
mid-flight, planned at 0), the `actual_start`/`actual_end` stamps written the way the verbs would,
one overdue row and one **cancelled** work package (7.2's `ACTIVE_WBS`) so the
terminal-but-not-done lens has something to exclude; checklists land on every third work package
with mixed ticks so the rollup is non-trivial and the register runs to page 2, leaving the
un-checklisted rows as the empty state; the block trail is one ACTIVE blocker and one CLOSED with
its full evidence. Log in as `admin_acme` / `admin_globex`, password `password`. Run it twice to
prove idempotency. 7.9 (own guard, `_collab`, dispatched after `_taskwork`): **3 channels / 18
messages / 4 document shares / 4 meetings / 8 agenda items / 7 action items / 18 notifications per
tenant** — three channels (discussion / announcement / ARCHIVED, so the archive facet and both
badge states have rows); 18 messages, which is deliberately more than the register's 15-row page so
the paginator has a **genuine** page 2 (13 was short — review C-D), comprising two roots carrying
two and three replies, two bare roots, an EDITED root carrying two mentions, five announcement
roots and three on the archived channel; four shares covering all three `access_level`s plus one
revoked and one claimed; four meetings, one per status, the completed one carrying full minutes, a
covered agenda and a mixed action list; agenda and action items spread across the meetings (one
overdue, one task-linked to a real 7.2 work package, one unassigned); and 18 notifications covering
every kind, both read states, every optional source FK and three recipients, so both the
`?recipient=` and `?mine=1` lenses have rows. The block **creates at most two `core.Document`
rows and never a second file store** — the repository is 7.10's. `--flush` deletes
`ProjectNotification` FIRST (it FKs four tables), then `MeetingActionItem` / `MeetingAgendaItem` /
`DocumentShare` / `ChannelMessage` / `Meeting` / `Channel`, all before `ProjectTask` / `Project`.

**The seeder's own history is a gotcha (review C3).** The 7.7 block originally seeded
`schedule_impact_days=-10` (and a second `-30`) into a `PositiveIntegerField`. MySQL's
`CHECK constraint failed: schedule_impact_days` fired **inside `transaction.atomic()`**, so the
command committed NOTHING, printed no error a human would notice, and was silently un-rerunnable
forever after. The live rows that "proved" the seeder worked predated the bad edit. The fix
flipped both signs AND added `obj.full_clean(exclude=["number"])` to all four factories so the
next out-of-range literal fails loudly at seed time instead of poisoning the transaction. If you
touch a numeric seed literal, run the command twice and confirm the row counts.

Do **not** "optimize" it with `bulk_create` — `TenantNumbered.save()` allocates `number`, and
`bulk_create` bypasses `save()`, shipping rows with empty numbers.

7.10 (own guard, dispatched after `_collab`): **12 ProjectFolders / 22 ProjectDocuments /
23 ProjectDocumentRevisions / 16 DocumentTemplates / 17 KnowledgeEntries per tenant**. The guard is
on the FOLDER tree because that is the block's entry point — `ProjectDocument.folder` is PROTECT and
required, so every document needs a folder by construction (the `document()` factory takes the folder
and reads the project OFF it, which makes "the folder belongs to another project" unrepresentable in
the seeder). Coverage: a 10-folder tree on the active project plus 2 on the second, including an
ARCHIVED branch so the archive lens has rows; documents spanning every doc type and every status —
one `expected` placeholder, one checked-out, one under legal hold, two archived, one superseded, and
two whose retention window has already closed; 25 revisions with two superseded PAIRS (v1 and v2 both
approved, pointer on v2) and four left pending approval; 16 standards covering every category with
both publish states; 17 knowledge entries covering every kind and every status with three featured.
Both the document and the knowledge registers clear the 15-row page, so the paginator has a genuine
page 2.

**Two seeder gotchas specific to 7.10, and both are load-bearing:**

- **`backdate()` is not cosmetic.** `retain_until` is `created_at + 30 * retention_months`, so with
  `created_at` at seed time **no** document could ever be retention-due and the retention board's
  headline figure would be structurally zero. `created_at` is `auto_now_add` and cannot be passed to
  the constructor; a queryset `.update(created_at=…)` bypasses the `pre_save` hook and is the only
  honest way to give a seeded row a past. Assign the attribute back on the in-memory row too, or the
  later `approve()` calls read the wrong value.
- **The revision writers are the VIEWS' helpers, never hand-stamped literals.** `next_revision_no()`
  allocates the number, `file_sha256()` measures the checksum over the payload BEFORE the storage
  layer consumes it, and `extract_text()` reads the text AFTER the row exists — there is nothing on
  disk to read until then. The payloads are `.txt` on purpose (`PLAIN_TEXT_EXTENSIONS`), so the
  extractor genuinely reads them and the register's four-character full-text sweep is demonstrably
  working on a fresh workspace without committing a binary fixture.

**The block writes FILES under `MEDIA_ROOT`, and only for rows it just created.** Every
`ContentFile` is minted inside the guard's `else` branch, so a second run writes none — which is what
keeps the media folder clean, because Django's storage layer **renames on collision**
(`project-charter-r2_a3f9c1x.txt`) rather than overwriting. Verify with a file count either side of a
second run, not by trusting the guard's message. `--flush` deletes revisions → documents → folders in
that order (the PROTECT edge, not just FK depth) and must leave the re-seed's counts identical.

## Tests — `apps/projects/tests/` (green unfiltered — **3390 passed / 0 failed / 2 skipped**)

**7.10's four lanes are implemented and verified:** The `docmgt_*` conftest block and
`test_docmgt_{models,forms,views,security}.py` (120 tests total: models 34 / forms 11 / views 47 / security 28)
are pinned in `.claude/tasks/test-contract-projects-7.10.md` and pass 100% green with `--nomigrations`.
In addition, `temp/smoke_710.py` passes all 169 runtime checks with 0 failures.

`conftest.py` (7.1 `projectinitiation_*` + 7.2 `planning_*` + 7.3 `resource_*` + 7.4 `cost_*` +
7.5 `risk_*` + 7.6 `quality_*` + 7.7 `scope_*` + 7.8 `taskwork_*` + 7.9 `collab_*` fixture blocks —
**owned by
itself; edit it only
with a full unfiltered re-run**) plus `test_initiation_{models,forms,views,security}.py`,
`test_planning_{models,forms,views,security}.py`,
`test_resource_{models,forms,views,security}.py`, `test_cost_{models,forms,views,security}.py`
(cost: models 67 / forms 42 / views 41 / security — names pinned in
`.claude/tasks/test-contract-projects-7.4.md` with the computed EVM table the model tests
assert), `test_risk_{models,forms,views,security}.py` (risk: models 35 / forms 23 —
band-boundary arithmetic, the seeded-Monte-Carlo draw replicated in-test, I9's esc-trio gating;
names pinned in `.claude/tasks/test-contract-projects-7.5.md`) and
`test_quality_{models,forms,views,security}.py` (quality: models 53 / forms 29 / views 76 /
security 44 — numbering, choices, derived figures, same-project guards; the crafted-POST
boundary (TenantModelForm's queryset narrowing refuses a foreign pk as "Select a valid choice"
before `_reject_foreign` can fire — assert the FIELD error, never the message); the verb state
machines incl. record-keeps-row-live and the QPL/QRV/QCI/QDF frozen-row gates; both computed
boards' pinned figures recomputed from the conftest fills; names pinned in
`.claude/tasks/test-contract-projects-7.6.md`) and
`test_scope_{models,forms,views,security}.py` (scope: models 205 / forms 103 / views 162 /
security 73 = **543** — numbering prefixes, every `*_CHOICES` set pinned against the model,
`STATUS_BANDS` checked against the theme.css badge allow-list, derived-property truth tables
(`is_open`/`is_locked`/`is_high_impact`), the same-project `clean()` guards, all 37 route names,
the pinned `scope_matrix` figures (coverage total 4 / traced 2 / untraced 2 / verified 1 /
`coverage_pct` `50.0`; `bar_pct` `[66.7, 100.0, 16.7]` asserted as the STRING form because it is
a `Decimal` while the 0-safe branch is float `0.0`; `creep_max` `60000.00`; `creep`
`{count 3, cost_total 110000.00, schedule_days 12, high_impact_count 2}`; `scope_summary`
`{items 5, boundaries 2, constraints 1, assumptions 1, open_items 4, overdue_items 1}`), all 16
verbs happy-path + refusal, and — the C2 regression net — **both actors** get 405 on every
`@require_POST` verb; names pinned in `.claude/tasks/test-contract-projects-7.7.md`) and
`test_taskwork_{models,forms,views,security}.py` (taskwork: models 29 / forms 16 / views 53 /
security 39 = **137** — the two registers' numbering and `is_active`, the derived blocking truth
tables (manual / dependency / done-and-cancelled-predecessor), the `checklist_progress` figures
(0 / 75 / 100 / `None`), the four choice vocabularies, the named indexes, the execution form's
exact six-field set and the M9 guards, all 17 routes, the four computed pages' context keys, the
bulk cap + the terminal-transition refusal, pagination, and the security lane's IDOR 404s,
**both-actor 405s** (the C2 net), CSRF, mass assignment and XSS; names pinned in
`.claude/tasks/test-contract-projects-7.8.md`) and
`test_collab_{models,forms,views,security}.py` (collab: models 70 / forms 32 / views 140 /
security 140 = **382** — the seven prefixes pinned against `MSG`/`MAI` so a future tidy-up cannot
collide with `scm.IntegrationMessage`/`hrm.MeetingActionItem`; `ChannelMessage.clean()`'s three
invariants including the I1 root-repoint guard, plus the cases it must NOT catch (a reply-less root
may move, a reply's body stays editable); the `unique_together` constraint asserted BOTH through
`full_clean()` — which reports it on `__all__`, not on `name` — and through a raw
`objects.create()` that bypasses validation and reaches the DB; every derived property
(`is_co_editable` false for a revoked edit share, `is_overdue` false on the due date itself);
all 22 declared index names and that every one leads with `tenant`; the `Meta.fields` lists
verbatim as the mass-assignment boundary; the M2M mention boundary (a foreign user pk is invalid)
and that `_reject_foreign` never touches a User FK; all 41 routes; the pinned figure graph
(channel 2/1, reply 1/0, agenda 3/2, open actions 2, overdue 1, unread 3, feed
`{message 3, meeting 1, share 3, notification 4, audit 0}` / `total_count` 11); all 18 verbs
both directions with their `changes["verb"]` audit row; the ordered-pagination assertion
(no `UnorderedObjectListWarning`) and a page 2 that carries rows page 1 does not; and the security
lane's 41 anonymous redirects, 30 cross-tenant 404s for **both** actors, crafted cross-tenant POST
bodies, the I1/I8 regressions, CSRF, mass assignment and XSS through the five user-authored text
fields; names pinned in
`.claude/tasks/test-contract-projects-7.9.md`). Naming:
every test
`test_<subslug>_*`, every helper `_<subslug>_*`, so the next sub-module cannot shadow them.

```bash
venv\Scripts\python.exe -m pytest apps/projects/ --nomigrations
```

**Iterate with `--nomigrations` (~90 s). The full migration path takes ~23 minutes** of DB setup and
`--reuse-db` is inert against SQLite `:memory:`. Never use `-k` for the final run (L47).

## Gotchas that have already bitten this module

1. **A nullable FK inside a `|default:` filter argument 500s the page.** Django resolves filter
   *arguments* eagerly and `string_if_invalid` only swallows `VariableDoesNotExist` for the *main*
   variable. `{{ obj.user.get_full_name|default:obj.user.username }}` is a hard 500 the instant the
   FK is NULL. Use `{% if obj.user %}…{% else %}—{% endif %}`. This cost four 500-ing pages here.
2. **`attendee_total`, not `attendee_count`, in the registers.** `attendee_count` is a `property`
   (a data descriptor) and shadows an annotation — `annotate(attendee_count=…)` raises
   `AttributeError: can't set attribute`.
3. **An aggregate over a multi-valued relation drops `Meta.ordering`.** `pko_list` and `prj_detail`
   annotate `attendee_total`, so the explicit `.order_by("-created_at", "-id")` is **load-bearing** —
   remove it and the register silently stops being newest-first.
4. **403 vs 404 depends on the actor.** `apps/core/decorators.py:16` runs before
   `get_object_or_404`, so on an admin-gated verb with a cross-tenant pk a *member* gets 403 and an
   *admin* gets 404. Write IDOR-404 assertions with the admin client.
5. **`_reject_foreign`'s message is unreachable via a normal crafted POST** — `TenantModelForm`
   narrows the queryset first, so Django's "Select a valid choice" wins. Assert *that the field has
   an error*, never the wording.
6. **`accounting.Currency` is a deliberate GLOBAL table with no `tenant` column (L29)** — it is the
   one FK that must stay unscoped.
7. **`core.AuditLog.action` is `varchar(10)`.** The verb goes in `changes` (`{"verb":…, "from":…,
   "to":…}`), never in `action`. Capture `previous = obj.status` *before* mutating — a hard-coded
   `from` makes the trail assert a gate held precisely when it was skipped.
8. **`prefetch_related("children")` returns DIFFERENT Python objects than the parent queryset.**
   7.2's first tree build decorated one set and the template read the other — rows rendered with no
   wbs_code/critical/rollup. That is why `_decorate_wbs` hangs the DECORATED instances on
   `node.kids` and the include walks `node.kids`, never `node.children.all`.
9. **Recursion depth is a member-triggerable 500.** The tree walk and the critical-path pass are
   ITERATIVE with hard caps (template depth 5, walk depth 20, Kahn hop cap) — a ~1000-node chain
   must skip nodes, never RecursionError. Don't "simplify" them back to recursion.
10. **A verb-gated field must not also be POST-settable through the ungated edit form.** 7.2 shipped
   `status` on `MilestoneForm` and `baseline_type` on `BaselineForm` — both let a member bypass the
   tenant-admin verbs (achieve without the stamp gate; "freeze" without a snapshot). Verbs write
   state; forms must not.
11. **`cached_property` is per-INSTANCE cache (7.4's C2).** `CostControlAccount.bac/ac/committed/
   active_revision` cache on the instance — after a mutation, the SAME instance reads stale;
   re-fetch before re-reading (the model tests pin this). They exist because per-row property
   re-queries made `cca_list` 75 queries/page and `cca_detail` 119 for one object.
12. **An activated baseline is frozen through BOTH surfaces (7.4's I1).** The revision refuses
   edit/delete AND its budget lines refuse edit/delete — a baseline that could be rewritten
   through its lines would not be a baseline. The correction path is a new revision.
13. **`@require_POST` must sit ABOVE `@tenant_admin_required` in the decorator stack (7.7's C2).**
   Decorators apply bottom-up and `tenant_admin_required` wraps `login_required` internally, so
   `@login_required → @require_POST → @tenant_admin_required` is the correct top-to-bottom order.
   Swap the last two and a *member's* GET on an admin-gated verb returns **403 instead of the
   house 405** — the role check fires first. The bug hides from an admin-actor test (which gets
   the right answer either way); always assert the method guard with the MEMBER client too. This
   same ordering bug was found in 7.1–7.5 and **swept on 2026-09-13** (23 verbs across 12 files);
   the full suite now asserts 405 for both actors on every POST-only verb.
14. **A wrongly-signed numeric seed literal inside `transaction.atomic()` fails SILENTLY and
   permanently (7.7's C3).** `schedule_impact_days=-10` into a `PositiveIntegerField` raised a
   MySQL CHECK violation that rolled the WHOLE `_scope` block back — no rows, no loud error, and
   `--flush` then `seed` could never recover because the guard saw "already seeded" from the
   *previous* good run. Always add `obj.full_clean(exclude=["number"])` to new seed factories and
   prove a fresh seed by row count, not by "the command exited 0".
15. **A derived property that uses `.filter()` bypasses the prefetch cache (7.8's I7).**
   `obj.is_manually_blocked` is `self.blocks.filter(unblocked_at__isnull=True).exists()` — the
   `.filter()` builds a NEW queryset, so it re-queries even when `blocks` was prefetched, once
   per badge. `obj.checklist_progress` is the same trap (2 COUNTs). Compute the flag off the
   prefetched list in the VIEW (`obj.active_blocks = [b for b in obj.blocks.all() if b.is_active]`)
   and pass it as context. Only `.all()` reads the cache. Measured: 31 → 13 queries on
   `tsk_detail`.
16. **`Prefetch("a__b")` costs two queries where a chained `Prefetch` costs one (7.8's M14).**
   The nested spelling prefetches `a`, then issues a SECOND query for `b`. Write
   `Prefetch("a", queryset=A.objects.select_related("b"))` instead — the join rides the first
   query. Both forms populate the same cache, so `is_dependency_blocked`'s `.all()` walk is
   unaffected either way.

## Sidebar wiring — `apps/core/navigation.py`

```python
"7.1": {
    "Project Request & Intake":              "projects:prq_list",
    "Business Case & Feasibility":           "projects:prq_list?status=submitted",
    "Project Charter Authoring":             "projects:prj_list",
    "Stakeholder Identification & Analysis": "projects:pst_list",
    "Project Kickoff & Launch":              "projects:pko_list",
}
```
The business case has no register of its own — cost/benefit, ROI and the go/no-go verbs all live
**on `ProjectRequest`**, so that bullet deep-links the same register filtered to the gate where
those numbers are weighed (the 2.15 `?category=` precedent).

```python
"7.2": {
    "Work Breakdown Structure (WBS)":        "projects:tsk_tree",
    "Task Sequencing & Dependency Mapping":  "projects:dep_list",
    "Duration & Effort Estimation":          "projects:tsk_list?node_type=work_package",
    "Milestone & Phase-Gate Definition":     "projects:mst_list",
    "Schedule Baseline & Version Control":   "projects:bsl_list",
    "Task Register":                         "projects:tsk_list",  # extra live leaf
}
```
Estimation deep-links the task register filtered to work packages (the rows that carry the
estimate); "Task Register" is an extra leaf — the parser appends labels that don't match a
NavERP.md bullet.

```python
"7.3": {
    "Resource Pool & Skills Inventory":      "projects:rsp_list",
    "Resource Allocation & Leveling":        "projects:capacity_demand",
    "Team Assembly & Role Assignment":       "projects:ral_list",
    "Resource Forecasting & Demand Planning": "projects:capacity_demand#demand",
    "Time Tracking & Timesheets":            "projects:rte_list",
    "Time Approvals":                        "projects:rte_list?status=submitted",  # extra leaf
}
```
The leveling bullet maps to the computed board (not the allocation register) and forecasting to
its `#demand` fragment - the URL fragment syntax is supported by `_safe_reverse` (6.13 precedent).
The skills-matrix promise of bullet 1 is HRM 3.40's lens (`hrm:employeeskill_list?employee=<pk>`
from `rsp_detail`, employee-keyed rows only).

```python
"7.4": {
    "Budget Planning & Estimation":         "projects:pbl_list",
    "Cost Baseline & Control Accounts":     "projects:cca_list",
    "Expense Tracking & Commitments":       "projects:pex_list",
    "Forecasting & EAC":                    "projects:cca_list",  # EVM columns are CA columns
    "Change Control & Budget Revisions":    "projects:bvr_list",
    "Budget Register":                      "projects:pbl_list",  # extra live leaf
}
```
Forecasting & EAC maps to the same register as bullet 2 on purpose — the EVM columns are
control-account columns, so a bullet may be a lens on a register rather than a new page
(7.2's Task-Register precedent).

```python
"7.5": {
    "Risk Identification & Register":        "projects:rsk_list",
    "Qualitative & Quantitative Analysis":   "projects:risk_analysis",
    "Risk Response Planning":                "projects:rra_list",
    "Issue Logging & Escalation":            "projects:iss_list",
    "Risk Monitoring & Reporting":           "projects:risk_monitoring",
    "Issue Escalation Queue":                "projects:iss_list?escalated=1",  # extra live leaf
}
```
Bullets 2 and 5 map to the computed boards (the matrix+EMV+Monte Carlo and the
top-risks/burn-down/review/lessons strip — computed over the register on every load, no snapshot
tables); the escalation-queue leaf deep-links the issue log's `?escalated=1` lens.

```python
"7.6": {
    "Quality Planning & Standards":          "projects:qpl_list",
    "Quality Assurance (QA)":                "projects:qrv_list?kind=assurance",
    "Quality Control (QC) & Inspections":    "projects:qci_list",
    "Continuous Improvement":                "projects:quality_improvement",
    "Deliverable Acceptance & Sign-off":     "projects:quality_acceptance",
    "Quality Review Register":               "projects:qrv_list",  # extra live leaf
    "Defect & Punch List":                   "projects:qdf_list",  # extra live leaf
}
```
Bullet 2 deep-links the review register's assurance lens and bullet 4 is the computed
improvement board (kaizen/retro rows, computed maturity, defect trend, lessons lens — no stored
maturity table); bullet 5 is the computed acceptance board whose queue links to the inspection
detail page where the `qci_accept` action lives.

```python
"7.7": {
    "Requirements Elicitation":               "projects:req_list",
    "Requirements Documentation & Traceability": "projects:scope_matrix",
    "Scope Definition & Boundaries":          "projects:sci_list",
    "Change Request Management":              "projects:scr_list",
    "Scope Verification & Control":           "projects:svr_list",
    "Requirement Approval Queue":             "projects:req_list?status=submitted",  # extra live leaf
}
```

```python
"7.8": {
    "Task Creation & Assignment":            "projects:task_board",
    "Priority & Urgency Scoring":            "projects:task_priority",
    "Kanban & Scrum Boards":                 "projects:task_board",
    "Gantt Charts & Timeline Views":         "projects:gantt_timeline",
    "Task Dependencies & Blocking":          "projects:dependencies",
    "Task Checklist Register":               "projects:tcl_list",  # extra live leaf
}
```
Bullets 1 and 3 both map to the board (it IS the task surface: create/assign live there and the
columns are the workflow); bullet 2 is the MoSCoW + Eisenhower lens; bullet 5 is 7.2's dependency
register (7.8 derives the blocking verdict from it and adds no link table of its own — the pinned
`LIVE_LINKS` mapping is a deliberate cross-sub-module deep link, recorded as review I5). The
checklist register is the extra leaf.
Bullet 2 is the computed traceability matrix (requirement × work-package coverage plus the gaps
and the creep board — computed over the registers on every load, no snapshot table); the
approval-queue leaf deep-links the register's `?status=submitted` lens (7.2's Task-Register /
7.5's escalation-queue precedent).

```python
"7.9": {
    "Team Messaging & Channels":             "projects:chn_list",
    "Document Sharing & Co-Editing":         "projects:dsh_list",
    "Meeting Management":                    "projects:mtg_list",
    "Notifications & Alerts":                "projects:ntf_list",
    "Activity Streams & Feeds":              "projects:activity_feed",
    "Message Register":                      "projects:msg_list",  # extra live leaf
}
```
Two mappings are deliberate and recorded as justification comments in `navigation.py`: bullet 2
maps to the **SHARE** register (the document repository and its version history are 7.10's — 7.9
only ships who may do what with an already-stored `core.Document`), and bullet 4 maps to the
notification **ROWS** inbox (the trigger rules, reminders and escalation-on-timeout are 7.17's).
Bullet 1's messaging half has its own register, hence the extra leaf.

```python
"7.10": {
    "Document Repository & Folders":         "projects:pdm_list",
    "Folder Tree":                           "projects:pfd_list",   # extra live leaf
    "Document Templates & Standards":        "projects:dtm_list",
    "Version Control & Check-in/Out":        "projects:pdv_list",
    "Knowledge Base & Lessons Learned":      "projects:kne_list",
    "Document Retention & Archiving":        "projects:doc_retention",
}
```

```python
"7.11": {
    "Timesheet Entry & Submission":          "projects:rte_list",
    "Approval Workflows":                    "projects:pot_list?status=submitted",
    "Billable vs. Non-Billable Hours":       "projects:utilization_dashboard",
    "Overtime & Leave Integration":          "projects:time_calendar",
    "Time Reporting & Utilization":          "projects:utilization_dashboard",
    "Activity Codes Register":               "projects:tac_list",                  # extra live leaf
    "Overtime Rules":                        "projects:otr_list",                  # extra live leaf
    "Overtime Records Register":             "projects:pot_list",                  # extra live leaf
}
```
Bullet 1 points at the extended `ResourceTimeEntry` register; bullet 2 maps to the pending overtime approval queue (`pot_list?status=submitted`); bullet 3 and bullet 5 map to the computed `utilization_dashboard` (chargeability ratios, client billing splits, category allocations, capacity vs demand); bullet 4 maps to `time_calendar` synchronizing project hours, leaves, holidays, and overtime claims. Activity codes, overtime rules, and the full overtime claims register are registered as extra live leaves.
Bullet 1 has two halves and both are live pages: the **register** is the bullet, and the **folder
tree** takes the extra leaf — 7.9's own sidebar comment settled that ("the file store, **the
folders** and the VERSION HISTORY are 7.10's"). Bullet 2 maps to the standards library, **file-backed
only**: a written standard that is prose lives in the knowledge register as
`kind="template"/"standard"`, deliberately two lenses rather than two near-duplicate tables (Ruling
4). Bullet 3 maps to the revision **LOG** — the immutable chain itself is reached from each
document's detail page, where upload/approve/restore are its verbs — and it is explicitly NOT a diff
(redlining is 13.2's). Bullet 5 is the one computed page of the five. `kne_search` and
`doc_repository` are **lenses**, not bullets, and each has a justification comment in
`navigation.py` saying so.

```python
"7.12": {
    "Portfolio Dashboard & Heat Maps":       "projects:pfm_dashboard",
    "Program Dependency Mapping":            "projects:pdep_list",
    "Strategic Alignment & Scoring":         "projects:pin_list",
    "Capacity & Pipeline Planning":          "projects:pfm_dashboard#pipeline",
    "Portfolio Reporting & Governance":      "projects:prt_list",
    # Extra live leaves:
    "Portfolios":                            "projects:prt_list",
    "Programs":                              "projects:pgm_list",
    "Investments & Scoring":                 "projects:pin_list",
    "Program Dependencies":                  "projects:pdep_list",
}
```
Bullet 1 maps to the executive `pfm_dashboard` with bubble scatter heat maps; bullet 2 maps to cross-project `pdep_list` register; bullet 3 maps to the multi-criteria `pin_list` scoring register; bullet 4 maps to the computed pipeline funnel over 7.1 intake requests (`pfm_dashboard#pipeline`); bullet 5 maps to `prt_list` governance overview and investment funding decisions.

### 7.12 Portfolio & Program Management — Reference

Covers multi-project portfolio governance, program decomposition, 4-criterion investment scoring, cross-project dependencies, and executive portfolio reporting:

#### Models (`apps/projects/models/PortfolioProgramManagement/`)
- **`Portfolio`** [`PRT-`] (`Portfolios.py`): Top-level strategic investment container. Fields: `name`, `code`, `description`, `status` (draft/active/on_hold/closed/archived), `strategic_theme` (growth/efficiency/transformation/compliance/innovation/customer_experience), `budget_envelope`, `currency`, `start_date`, `end_date`, `owner`, `is_active`. Properties: `total_programs`, `total_investments`, `allocated_budget`, `budget_variance`.
- **`Program`** [`PGM-`] (`Programs.py`): Sub-portfolio coordinated delivery cluster. Fields: `portfolio`, `name`, `code`, `description`, `manager`, `status` (proposed/planning/active/on_hold/completed/cancelled), `target_start_date`, `target_end_date`, `objectives`, `budget_target`. Properties: `total_projects`, `allocated_budget`. Unique on `(tenant, portfolio, name)`.
- **`PortfolioInvestment`** [`PIN-`] (`PortfolioInvestments.py`): Investment scoring & governance link between `Portfolio` and `Project`. Fields: `portfolio`, `project`, `program` (optional), `status` (proposed/under_review/funded/deferred/rejected), `strategic_fit` (0-100), `financial_return` (0-100), `delivery_risk` (0-100), `capacity_fit` (0-100), criterion weights (`weight_strategic`, `weight_financial`, `weight_risk`, `weight_capacity`), `allocated_budget`, `approved_by`, `approved_at`, `decision_notes`. Property: `weighted_score` (computed 0-100). Verbs: `pin_fund`, `pin_reject`, `pin_defer`.
- **`ProgramDependency`** [`PDEP-`] (`ProgramDependencies.py`): Cross-project inter-dependency edge. Fields: `source_project`, `target_project`, `program` (optional), `dependency_type` (finish_to_start/start_to_start/shared_resource/deliverable_handover/governance_gate), `criticality` (low/medium/high/critical), `status` (open/mitigated/cleared/waived), `lead_lag_days`, `description`, `owner`, `cleared_at`. Verbs: `pdep_clear`, `pdep_reopen`.

#### Views & Routes (`apps/projects/views/PortfolioProgramManagement/`, `apps/projects/urls/PortfolioProgramManagement/`)
- **Portfolio**: `prt_list` (`portfolios/`), `prt_create` (`portfolios/add/`), `prt_detail` (`portfolios/<int:pk>/`), `prt_edit` (`portfolios/<int:pk>/edit/`), `prt_delete` (`portfolios/<int:pk>/delete/`).
- **Program**: `pgm_list` (`programs/`), `pgm_create` (`programs/add/`), `pgm_detail` (`programs/<int:pk>/`), `pgm_edit` (`programs/<int:pk>/edit/`), `pgm_delete` (`programs/<int:pk>/delete/`).
- **Investment**: `pin_list` (`investments/`), `pin_create` (`investments/add/`), `pin_detail` (`investments/<int:pk>/`), `pin_edit` (`investments/<int:pk>/edit/`), `pin_delete` (`investments/<int:pk>/delete/`), `pin_fund` (`investments/<int:pk>/fund/`), `pin_reject` (`investments/<int:pk>/reject/`), `pin_defer` (`investments/<int:pk>/defer/`).
- **Dependency**: `pdep_list` (`program-dependencies/`), `pdep_create` (`program-dependencies/add/`), `pdep_detail` (`program-dependencies/<int:pk>/`), `pdep_edit` (`program-dependencies/<int:pk>/edit/`), `pdep_delete` (`program-dependencies/<int:pk>/delete/`), `pdep_clear` (`program-dependencies/<int:pk>/clear/`), `pdep_reopen` (`program-dependencies/<int:pk>/reopen/`).
#### Dashboard: `pfm_dashboard` (`portfolio-dashboard/`): Multi-project health summary, capacity & pipeline intake funnel (from 7.1 requests), 4-quadrant strategic alignment heat map matrix, executive committee investment ranking table.

```python
"7.13": {
    "Sprint Planning & Backlog Grooming":    "projects:sprint_backlog",
    "Sprint Execution & Daily Standups":     "projects:sprint_execution",
    "Release & Version Planning":            "projects:rel_list",
    "Epic & Feature Management":             "projects:epc_list",
    "Retrospectives & Team Health":          "projects:ret_list",
    # Extra live leaves:
    "Sprint Register":                       "projects:spt_list",
    "Impediment Register":                   "projects:imp_list",
    "Velocity & Health":                     "projects:velocity_report",
    "Release Roadmap":                       "projects:release_roadmap",
}
```
Bullet 1 maps to the `sprint_backlog` grooming workbench; bullet 2 maps to the `sprint_execution` active sprint workbench with burndown chart, daily standup notes, and impediments; bullet 3 maps to `rel_list` release register; bullet 4 maps to `epc_list` epic hierarchy register; bullet 5 maps to `ret_list` sprint retrospective board. Extra live leaves provide direct access to `spt_list`, `imp_list`, `velocity_report`, and `release_roadmap`.

### 7.13 Agile & Scrum Management — Reference

Covers sprint planning & grooming, sprint execution with burndown & daily standups, release & version planning, epic hierarchy with progress rollups, sprint retrospectives, and velocity reporting:

#### Models (`apps/projects/models/AgileScrumManagement/` & in-place extensions)
- **`ProjectTask` Agile Extensions** (`ProjectTasks.py`): In-place extensions on the canonical task model. Fields: `story_points` (PositiveSmallIntegerField, 0-100), `sprint` (FK `Sprint`, null=True), `epic` (FK `ProjectEpic`, null=True), `release` (FK `ProjectRelease`, null=True). Property: `is_in_backlog` (True when `sprint_id is None`).
- **`Sprint`** [`SPT-`] (`Sprints.py`): Timeboxed sprint iteration container. Fields: `project`, `name`, `goal`, `status` (planning/active/completed/cancelled), `start_date`, `end_date`, `committed_points`, `standup_notes`. Properties: `total_points`, `completed_points`, `remaining_points`, `completion_rate`, `task_count`, `completed_task_count`, `is_overdue`. Verbs: `spt_start`, `spt_complete`, `spt_cancel`.
- **`ProjectEpic`** [`EPC-`] (`ProjectEpics.py`): High-level feature/epic hierarchy container. Fields: `project`, `name`, `summary`, `status` (planned/in_progress/completed/cancelled), `owner`, `target_start`, `target_end`, `color_code`. Properties: `total_points`, `completed_points`, `progress_percent`, `task_count`, `done_task_count`.
- **`ProjectRelease`** [`REL-`] (`ProjectReleases.py`): Release train and version deploy tracker. Fields: `project`, `name`, `version_tag`, `status` (unreleased/in_progress/released/archived), `release_date`, `release_notes`, `feature_flags`, `released_at`, `released_by`. Properties: `total_stories`, `completed_stories`, `progress_percent`, `is_overdue`. Verb: `rel_publish`.
- **`SprintImpediment`** [`IMP-`] (`SprintImpediments.py`): Team blocker and impediment tracker. Fields: `sprint`, `title`, `description`, `severity` (low/medium/high/critical), `status` (open/in_progress/resolved), `owner`, `raised_by`, `resolved_at`, `resolution_notes`. Property: `is_active`. Verb: `imp_resolve`.
- **`SprintRetrospective`** [`RET-`] (`SprintRetrospectives.py`): Post-sprint review & sentiment survey. Fields: `sprint`, `conducted_date`, `conducted_by`, `status` (draft/open/closed), `sentiment_score` (Decimal 1.0-5.0), `what_went_well`, `what_needs_improvement`, `action_items`, `closed_at`. Verbs: `ret_open`, `ret_close`.

#### Views & Routes (`apps/projects/views/AgileScrumManagement/`, `apps/projects/urls/AgileScrumManagement/`)
- **Sprint**: `spt_list` (`agile/sprints/`), `spt_create` (`agile/sprints/add/`), `spt_detail` (`agile/sprints/<int:pk>/`), `spt_edit` (`agile/sprints/<int:pk>/edit/`), `spt_delete` (`agile/sprints/<int:pk>/delete/`), `spt_start` (`agile/sprints/<int:pk>/start/`), `spt_complete` (`agile/sprints/<int:pk>/complete/`), `spt_cancel` (`agile/sprints/<int:pk>/cancel/`).
- **ProjectEpic**: `epc_list` (`agile/epics/`), `epc_create` (`agile/epics/add/`), `epc_detail` (`agile/epics/<int:pk>/`), `epc_edit` (`agile/epics/<int:pk>/edit/`), `epc_delete` (`agile/epics/<int:pk>/delete/`).
- **ProjectRelease**: `rel_list` (`agile/releases/`), `rel_create` (`agile/releases/add/`), `rel_detail` (`agile/releases/<int:pk>/`), `rel_edit` (`agile/releases/<int:pk>/edit/`), `rel_delete` (`agile/releases/<int:pk>/delete/`), `rel_publish` (`agile/releases/<int:pk>/publish/`).
- **SprintImpediment**: `imp_list` (`agile/impediments/`), `imp_create` (`agile/impediments/add/`), `imp_detail` (`agile/impediments/<int:pk>/`), `imp_edit` (`agile/impediments/<int:pk>/edit/`), `imp_delete` (`agile/impediments/<int:pk>/delete/`), `imp_resolve` (`agile/impediments/<int:pk>/resolve/`).
- **SprintRetrospective**: `ret_list` (`agile/retrospectives/`), `ret_create` (`agile/retrospectives/add/`), `ret_detail` (`agile/retrospectives/<int:pk>/`), `ret_edit` (`agile/retrospectives/<int:pk>/edit/`), `ret_delete` (`agile/retrospectives/<int:pk>/delete/`), `ret_open` (`agile/retrospectives/<int:pk>/open/`), `ret_close` (`agile/retrospectives/<int:pk>/close/`).
- **Computed Workbenches**:
  - `sprint_backlog` (`agile/backlog/`): Backlog grooming workbench with project filter, sprint allocation, story point assignment, and epic breakdown.
  - `sprint_execution` (`agile/execution/`): Active sprint dashboard featuring day-by-day burndown chart (ideal vs actual points), standup notes logger, and open blockers panel.
  - `release_roadmap` (`agile/roadmap/`): Release calendar and feature delivery timeline across unreleased, in-progress, and released version trains.
  - `velocity_report` (`agile/velocity/`): Historical sprint velocity analysis (points committed vs completed), rolling velocity average, and team sentiment trend.

```python
"7.14": {
    "Client Portal & Visibility":            "projects:cpa_list",
    "Client Feedback & Approvals":           "projects:cfb_list",
    "Contract & SOW Management":             "projects:sow_list",
    "External Vendor Coordination":          "projects:vhd_list",
    "Billing & Invoicing to Clients":        "projects:pci_list",
    # Extra live leaves:
    "Statement of Work Register":            "projects:sow_list",
    "Vendor Coordination":                   "projects:vhd_list",
    "Client Billing & Invoices":             "projects:pci_list",
}
```
Bullet 1 maps to `cpa_list` client portal access & visibility management; bullet 2 maps to `cfb_list` review cycles & approval requests; bullet 3 maps to `sow_list` statements of work and amendment tracking; bullet 4 maps to `vhd_list` external vendor coordination and scorecards; bullet 5 maps to `pci_list` client billing schedules and AR invoice generation. Extra live leaves provide direct access to `sow_list`, `vhd_list`, and `pci_list`.

### 7.14 Client & External Collaboration — Reference

Covers client portal access control, formal client review & approval workflows, statement of work (SOW) authoring with amendment rollup, external vendor coordination with scorecard ratings, and project delivery billing schedules with 1-click accounting AR invoice generation:

#### Models (`apps/projects/models/ClientExternalCollaboration/`)
- **`ClientPortalAccess`** [`CPA-`] (`ClientPortals.py`): Client external visibility and token management. Fields: `project`, `client_contact` (Party person), `portal_user`, `access_token` (UUID), `can_view_progress`, `can_view_milestones`, `can_view_deliverables`, `can_view_financials`, `can_submit_feedback`, `is_active`, `expires_at`, `notes`. Property: `is_expired`. Unique on `(tenant, project, client_contact)`.
- **`ClientApprovalRequest`** [`CFB-`] (`ClientFeedbacks.py`): Formal review cycle and deliverable sign-off. Fields: `project`, `deliverable_name`, `document`, `milestone`, `requested_by`, `assigned_contact` (Party person), `status` (draft/pending_review/approved/rejected/revision_requested), `due_date`, `review_notes`, `client_feedback`, `signed_by_name`, `signed_at`, `rejection_reason`. Verbs: `cfb_approve`, `cfb_reject`.
- **`StatementOfWork`** [`SOW-`] (`StatementOfWorks.py`): Master project delivery contract and scope terms. Fields: `project`, `client` (Party organization), `title`, `sow_code`, `billing_type` (fixed_fee/time_and_materials/milestone_based/retainer), `contract_value`, `currency`, `start_date`, `end_date`, `status` (draft/under_review/active/amended/completed/terminated), `scope_summary`, `terms_and_conditions`, `activated_at`, `activated_by`. Properties: `total_amendments` (count of approved amendments), `effective_value` (contract_value + approved amendment deltas). Verb: `sow_activate`.
- **`SOWAmendment`** [`SWA-`] (`StatementOfWorks.py`): Contract scope/value change order. Fields: `sow`, `amendment_number`, `title`, `effective_date`, `value_change`, `revised_scope`, `justification`, `status` (draft/approved/rejected), `approved_by`, `approved_at`.
- **`VendorHandoff`** [`VHD-`] (`VendorHandoffs.py`): External subcontractor task/deliverable handover. Fields: `project`, `vendor` (Party organization), `task`, `title`, `description`, `handoff_date`, `due_date`, `status` (assigned/in_progress/delivered/accepted/rejected), `deliverable_link`, `scorecard_rating` (1–5), `performance_notes`, `deficiency_notes`, `accepted_at`, `accepted_by`. Verbs: `vhd_accept`, `vhd_reject`.
- **`ProjectClientInvoice`** [`PCI-`] (`ClientInvoices.py`): Client billing schedule linking delivery directly to canonical `accounting.Invoice` ledger. Fields: `project`, `sow`, `milestone`, `billing_type` (fixed_fee/time_and_materials/milestone/retainer), `billing_date`, `due_date`, `currency`, `amount`, `tax_amount`, `total_amount`, `status` (draft/ready_to_bill/invoiced/cancelled), `accounting_invoice` (FK `accounting.Invoice`), `invoiced_at`, `notes`. Verb: `pci_generate_invoice` (atomic creation of customer invoice + invoice lines in AR ledger).

#### Views & Routes (`apps/projects/views/ClientExternalCollaboration/`, `apps/projects/urls/ClientExternalCollaboration/`)
- **ClientPortalAccess**: `cpa_list` (`client-portal-access/`), `cpa_create` (`client-portal-access/add/`), `cpa_detail` (`client-portal-access/<int:pk>/`), `cpa_edit` (`client-portal-access/<int:pk>/edit/`), `cpa_delete` (`client-portal-access/<int:pk>/delete/`).
- **ClientApprovalRequest**: `cfb_list` (`client-approvals/`), `cfb_create` (`client-approvals/add/`), `cfb_detail` (`client-approvals/<int:pk>/`), `cfb_edit` (`client-approvals/<int:pk>/edit/`), `cfb_delete` (`client-approvals/<int:pk>/delete/`), `cfb_approve` (`client-approvals/<int:pk>/approve/`), `cfb_reject` (`client-approvals/<int:pk>/reject/`).
- **StatementOfWork**: `sow_list` (`statements-of-work/`), `sow_create` (`statements-of-work/add/`), `sow_detail` (`statements-of-work/<int:pk>/`), `sow_edit` (`statements-of-work/<int:pk>/edit/`), `sow_delete` (`statements-of-work/<int:pk>/delete/`), `sow_activate` (`statements-of-work/<int:pk>/activate/`), `sow_amendment_create` (`statements-of-work/<int:pk>/amendments/add/`).
- **VendorHandoff**: `vhd_list` (`vendor-handoffs/`), `vhd_create` (`vendor-handoffs/add/`), `vhd_detail` (`vendor-handoffs/<int:pk>/`), `vhd_edit` (`vendor-handoffs/<int:pk>/edit/`), `vhd_delete` (`vendor-handoffs/<int:pk>/delete/`), `vhd_accept` (`vendor-handoffs/<int:pk>/accept/`), `vhd_reject` (`vendor-handoffs/<int:pk>/reject/`).
- **ProjectClientInvoice**: `pci_list` (`client-invoices/`), `pci_create` (`client-invoices/add/`), `pci_detail` (`client-invoices/<int:pk>/`), `pci_edit` (`client-invoices/<int:pk>/edit/`), `pci_delete` (`client-invoices/<int:pk>/delete/`), `pci_generate_invoice` (`client-invoices/<int:pk>/generate-invoice/`).

## Common tasks

- **Add a field** — edit the entity file under `models/ProjectInitiation/`, add it to the form's
  `Meta` (or its `exclude` if it is system/evidence — see the evidence model above), render it in
  the templates, `makemigrations projects`, `migrate`, extend `seed_projects`, add tests.
- **Add a model + CRUD** — new `<Entity>.py` in **all four** layers under `ProjectInitiation/`,
  **add it to every package `__init__.py` re-export block** (a missing re-export is a runtime
  `ImportError`), templates at `templates/projects/initiation/<entity>/`, then the seeder and tests.
- **Add a filter** — parse it in the view *before* pagination, pass the choices/queryset into the
  context, and in the template compare pk filters with `|stringformat:"d"` (never `|slugify`).
- **Build 7.4+** — use `/next-module`. New sub-module = a new `<SubModule>/` folder in each of
  the four layers, a new `templates/projects/<submodule>/` tree, and one new `LIVE_LINKS` entry.

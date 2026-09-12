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
  accruals) with post/void verbs; and 7.6 Quality Management: per-deliverable acceptance-criteria
  plans with an approve/supersede lifecycle, the combined QA + continuous-improvement review
  register (methodology/compliance/gate + kaizen/retrospective/maturity), deliverable inspections
  whose record→accept/reject verbs carry the acceptance decision and customer-party sign-off, the
  defect punch list with an issue bridge, and the two computed boards (CMMI-banded maturity +
  defect trend + lessons lens; per-deliverable acceptance state + acceptance queue). Use when the user
  asks to add/change/debug anything under apps/projects or templates/projects, extend the
  seed_projects seeder, touch project sidebar wiring (LIVE_LINKS 7.1–7.6), work on
  ProjectRequest/Project/ProjectStakeholder/ProjectKickoff/ProjectTask/TaskDependency/
  ProjectMilestone/ScheduleBaseline/ResourceProfile/ResourceAllocation/ResourceTimeEntry/
  BudgetRevision/CostControlAccount/ProjectBudgetLine/ProjectExpense/
  QualityPlan/QualityReview/DeliverableInspection/QualityDefect,
  or invokes /projects.
---

# Module 7 — Project Management (`apps/projects`)

**As-built: 7.1 + 7.2 + 7.3 + 7.4 + 7.5 + 7.6 + 7.7.** 7.8–7.19 are roadmap (a parallel build is
landing them — always
check `apps/projects/models/` first). Do
not assume a model exists because NavERP.md lists the feature — check first.

App path `apps/projects/`, templates `templates/projects/`, `app_name = "projects"`, mounted at
`/projects/`. Migrations `0001_initial`, `0002_ordering_indexes_and_nonnegative_estimates`,
`0003_projecttask_projectmilestone_schedulebaseline_and_more`,
`0004_resourceprofile_resourceallocation_resourcetimeentry_and_more` (12 named indexes),
`0005_budgetrevision_costcontrolaccount_projectbudgetline_and_more` (10 named indexes — the 7.4
tables), `0006_projectrisk_projectissue_riskresponseaction_and_more` (7.5),
`0008_projectissue_iss_tnt_type_idx_and_more` (7.5 review indexes) and
`0009_deliverableinspection_qualityplan_qualitydefect_and_more` (the 7.6 tables — the 0007 leaf
went to the parallel 7.7 build).

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
| `req_amendment_create` | login | mints a new version row from an approved baseline (the version-bump path) |
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

## Routes (`app_name = "projects"`, 205 names)

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
7.7: `req_{list,create,detail,edit,delete}` + `req_{submit,approve,reject,implement,verify,
amendment-create}` · `sci_…` + `sci_{validate,realize,retire}` · `scr_…` +
`scr_{submit,review,approve,reject,implement}` · `svr_…` + `svr_{accept,reject,waive}` ·
`scope_matrix` (path prefixes `requirements/ scope-items/ scope-changes/ scope-verifications/
scope-matrix/` — disjoint literals).

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
`templates/projects/overview.html` at the app root, the recursive
`planning/task/{tree.html,_tree_node.html}` WBS pair (depth-capped, walks `node.kids`) and the
standalone boards `resource/capacity_demand.html`, `risk/risk_analysis.html`,
`risk/risk_monitoring.html`, `quality/quality_improvement.html`,
`quality/quality_acceptance.html` and `scope/scope_matrix.html` (sub-module root, rule 6).
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
written reason. Log in as `admin_acme` / `admin_globex`, password `password`. Run it twice to
prove idempotency.

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

## Tests — `apps/projects/tests/` (green unfiltered)

`conftest.py` (7.1 `projectinitiation_*` + 7.2 `planning_*` + 7.3 `resource_*` + 7.4 `cost_*` +
7.5 `risk_*` + 7.6 `quality_*` + 7.7 `scope_*` fixture blocks — **owned by itself; edit it only
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
(`is_open`/`is_locked`/`is_high_impact`), the same-project `clean()` guards, all 38 route names,
the pinned `scope_matrix` figures (coverage total 4 / traced 2 / untraced 2 / verified 1 /
`coverage_pct` `50.0`; `bar_pct` `[66.7, 100.0, 16.7]` asserted as the STRING form because it is
a `Decimal` while the 0-safe branch is float `0.0`; `creep_max` `60000.00`; `creep`
`{count 3, cost_total 110000.00, schedule_days 12, high_impact_count 2}`; `scope_summary`
`{items 5, boundaries 2, constraints 1, assumptions 1, open_items 4, overdue_items 1}`), all 16
verbs happy-path + refusal, and — the C2 regression net — **both actors** get 405 on every
`@require_POST` verb; names pinned in `.claude/tasks/test-contract-projects-7.7.md`). Naming:
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
Bullet 2 is the computed traceability matrix (requirement × work-package coverage plus the gaps
and the creep board — computed over the registers on every load, no snapshot table); the
approval-queue leaf deep-links the register's `?status=submitted` lens (7.2's Task-Register /
7.5's escalation-queue precedent).

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

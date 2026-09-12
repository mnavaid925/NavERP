# Research — Sub-module 7.8: Task & Work Management (Module 7 — Project Management, `projects`)

> **Read this first.** 7.8 is the module's **execution engine**: it turns 7.2's planned WBS
> (`ProjectTask` [TSK-] + `TaskDependency` [DEP-]) into *assigned, prioritised, tracked and
> unblocked* work — **who does this card** (assignee), **how urgent** (priority / MoSCoW /
> Eisenhower), **where on the board** (workflow state), **how far along** (percent complete,
> actual dates), **what is standing in its way** (blocked status + unblock criteria).
>
> **Researched 2026-09-12** against 9 leading products: Asana, Monday.com, Jira, ClickUp, Wrike,
> Microsoft Project + Planner, Smartsheet, Airtable, Teamwork.com — plus MoSCoW/Eisenhower as the
> vocabulary source.
>
> **Recommended scope: 2 NEW models** — `TaskChecklistItem` [TCL-], `TaskBlock` [TBK-] — plus an
> **in-place execution-field extension of `ProjectTask`** and **3 computed pages**
> (`task_board`, `gantt_timeline`, `task_priority`).
>
> It is **not** a second task table (the `ProjectTask` docstring contract), **not** a second
> assignment register or time log (**7.3 `ResourceAllocation`/`ResourceTimeEntry`**), **not** a
> second dependency graph (**7.2 `TaskDependency`**), **not** sprint ceremony (**7.13**),
> **not** notifications (**7.17**), **not** charts/BI (**7.16**), **not** configuration master
> data (**7.19**).
>
> **The two failure modes for this pass:**
> 1. **Minting a parallel task model** (`WorkTask`, `TaskExecution`, …). `ProjectTask` already IS
>    the WBS node and schedulable activity; its docstring rules *"sub-module 7.8 extends it in
>    place with execution fields rather than declaring a second task table"*. See **Ruling 1**.
> 2. **Re-declaring assignments or dependencies.** 7.3 owns staffing (RAL books a
>    `ResourceProfile` — note RSP has **no User FK**, it is capacity grain, not login grain) and
>    7.2 owns the dependency network. 7.8 adds the *blocking layer* on top. See **Rulings 2–3**.

---

## Repo state checked first

**LIVE_LINKS:** `grep -n '"7\.' apps/core/navigation.py` → 7.1 (1702), 7.2 (1717), 7.3 (1732),
7.4 (1747), 7.5 (1766), 7.6 (1787), 7.7 (1808). **7.8 is the seventh Module 7 entry.** Migrations
run to `0010_alter_scopeitem_status` — **7.8's migration is `0011_…`**.

### Spine entities VERIFIED (grep/read evidence)

| Entity | Verified at | What 7.8 uses it for |
|---|---|---|
| `projects.ProjectTask` [TSK-] | `ProjectPlanningScheduling/ProjectTasks.py:22` | **THE task row, extended in place.** Has: `project` FK (`"tasks"`), `parent` self-FK (`"children"` — **sub-tasks already work**), `node_type`, `owner`→User (`"planned_project_tasks"`), `status` ∈ {planned, in_progress, done, cancelled} (help-text: *"Execution workflow (assignments, actuals) is 7.8's"*), `planned_start/end`, `effort_hours`, `sequence`, derived `duration_days`. **Missing (7.8 adds): assignee, priority, MoSCoW, urgent/important, percent_complete, actual dates.** |
| `projects.TaskDependency` [DEP-] | `TaskDependencies.py:17` | **the dependency network — NOT re-declared.** 4 link kinds, signed `lag_days`, same-project guard, unique `(tenant, predecessor, successor)`. 7.8 derives *blocking* from it. |
| `critical_path_ids(project)` | `apps/projects/views/_helpers.py:107` | **the critical chain, computed on read** (iterative Kahn). 7.8's Gantt highlights exactly this set. |
| `projects.ResourceAllocation` [RAL-] | `ResourceManagement/ResourceAllocations.py:24` | **the staffing register — NOT re-declared.** `project_task` FK (`"allocations"`), verb-driven `booking_status`, `ral_assign`/`ral_substitute`. Books a `ResourceProfile`, never a User. |
| `projects.ResourceTimeEntry` [RTE-] | `ResourceManagement/ResourceTimeEntries.py:19` | **the time log — NOT re-declared.** `project_task` FK (`"time_entries"`), `hours`, `entry_date`. Docstring: *"7.8 extends the task in place with execution fields."* |
| `projects.CostControlAccount` [CCA-] | `CostManagement/CostControlAccounts.py:29` | `percent_complete` is a **manual attestation** feeding EV — *"7.8's execution fields supersede this figure"*. See **Ruling 5**. |
| `crmproject_board` (house idiom) | `apps/crm/views/ProjectDelivery/Projects.py:92` | the existing GET-only kanban: columns bucketed per `STATUS_CHOICES` in Python, `?project=` guarded with `isdigit()`. **7.8's board copies this.** No JS framework exists in the repo. |
| `core.AuditLog` / `AUTH_USER_MODEL` | — | verbs `start/complete/block/unblock/check` fit varchar(10); assignee/stamp FKs nullable `SET_NULL`. |

### Verified NOT to exist / naming-collision check (performed, not assumed)

- `grep -rn "class (TaskChecklistItem|TaskBlock|KanbanBoard|TaskAssignment|TaskExecution)" apps/`
  → **empty**; no `priority`/`assignee`/`percent_complete` field exists on `ProjectTask`.
- **Prefixes:** `TCL`, `TBK` free repo-wide. Near-misses taken and avoided: **`TSK` (7.2), `TASK`
  (crm 1.8 Tasks — the pre-spine stand-in), `DEP`, `RAL`, `RTE`, `SCR` (7.7)**.
- **URL stems taken:** `tasks/`, `dependencies/`, `milestones/`, `baselines/` (7.2),
  `allocations/`, `time-entries/`, `capacity-demand/` (7.3), …, `scope-matrix/` (7.7). **7.8's
  literals `task-board/`, `gantt-timeline/`, `task-priority/` are disjoint** (first-segment
  converter invariant, `urls/__init__.py:1-24`).
- **Templates:** `templates/projects/planning/task/` is 7.2's CRUD. **7.8 uses
  `templates/projects/taskwork/<entity>/…`** (the `quality/`←QualityManagement, `scope/`←
  ScopeRequirements shortening pattern); computed pages flat (`taskwork/task_board.html`, …).
- `related_name="assigned_project_tasks"` verified free (`grep -rln` → 0 files).

---

## THE RULINGS — boundaries 7.8 must set before anyone else does

### Ruling 1 — 7.8 EXTENDS `ProjectTask` IN PLACE; no second task model
The `ProjectTask` docstring (`ProjectTasks.py:8-10`) makes the build-plan ruling explicit. Sub-tasks
already work (`parent` self-FK, the OrgUnit/GLAccount idiom). 7.8 adds execution FIELDS
(`assignee`, `priority`, `moscow`, `is_urgent`, `is_important`, `percent_complete`, `actual_start`,
`actual_end`) to the same row. A separate `WorkTask` table is the L29/L36 bug.

### Ruling 2 — Assignment: one `assignee` FK on the task; RAL/RTE stay the registers
The market keeps assignment ON the task (Jira single assignee; ClickUp guidance: *"avoid assigning
tasks to multiple people"* — ZenPilot); team-level staffing is what 7.3's RAL already books
(role/capacity over a window, verb-driven). **Decision: nullable `assignee` FK →
AUTH_USER_MODEL** (the doer; `owner` stays accountable — RSP has no User FK, so RAL cannot serve
as the login-grain assignee anyway). Multi-assignee M2M is **deferred (P2)**.

### Ruling 3 — "Blocked" is DERIVED from `TaskDependency`; a manual block is a `TaskBlock` evidence row
The market splits blocking in two: **auto** ("waiting on" — Asana; ClickUp refuses completion
until blockers clear; Smartsheet/Monday auto-shift dates) and **manual** ("Stuck/Blocked" —
Monday's status label; Jira's custom blocked status). 7.2 owns the edges; 7.8 owns the state:
- **Dependency-blocking is computed, never stored:** `is_dependency_blocked` = has an unfinished
  FS/SS predecessor (derived property over `predecessor_links` — the CCA derived-property idiom).
- **Real-world blockers get a `TaskBlock` [TBK-] row** (reason, unblock criteria, who/when stamped
  by POST-only `tsk_block`/`tsk_unblock`; frozen once unblocked — the 7.4/7.6 frozen-row idiom).
  A stored `blocked` boolean would go stale and have no evidence trail.

### Ruling 4 — Board columns ARE the status; no workflow engine, no column-config table
Jira's configurable status→column mapping and WIP limits are board configuration — a workflow
engine (**7.17's**) plus master data (**7.19's**). **Decision: the kanban board is a computed page
whose columns are `ProjectTask.STATUS_CHOICES`** (the CRM board idiom), counts rendered per
column; WIP-limit *values* wait for 7.19 (P2). "Drag-and-drop" ships as POST-only status verbs per
card — no JS framework in the repo.

### Ruling 5 — CCA `percent_complete` stays attested; 7.8 feeds a READ-ONLY lens, no write-back
The market auto-rolls progress (Smartsheet % complete rolls up from children; Teamwork shows a
completion % column) — but NavERP's `CCA.percent_complete` is an *attested* EV input. **Decision:
7.8 ships a computed lens** (per control account / deliverable node: effort-weighted rollup of
descendant task `percent_complete` + checklist ticks) rendered **alongside** the attested figure as
advisory. Nothing writes the CCA column (L36: extend by lens, never re-declare; derived figures
are never stored columns).

---

## Leaders surveyed (with source links)

1. **Asana** — list/board/timeline/Gantt/calendar views; multi-level subtasks + milestones;
   **dependencies drawn in Timeline**, native **"waiting on"** state notifying the assignee when
   the blocker completes; **no native "task is blocked" rule trigger** (feature request) and no
   native quadrant view — Eisenhower is built from two custom fields (Urgency, Importance);
   multi-select bulk edits.
   <br>[Views](https://asana.com/features/project-management/project-views) · [Dependencies](https://help.asana.com/s/article/task-dependencies) · [Timeline](https://help.asana.com/s/article/timeline) · [Eisenhower](https://asana.com/resources/eisenhower-matrix) · [Blocked-trigger request](https://forum.asana.com/t/add-a-trigger-for-rules-that-execute-when-task-is-blocked/126514)
2. **Monday.com** — **Dependency Column** (FS logic, **restructures dates automatically**);
   **Status column with customisable labels incl. "Stuck/Blocked"**; People column (assignee);
   Priority column (Low/Medium/High/Critical); Gantt **baselines (subitems supported)**.
   <br>[Dependencies](https://support.monday.com/hc/en-us/articles/360007402599-Dependencies-on-monday-com) · [Status column](https://support.monday.com/hc/en-us/articles/360001269685-The-Status-Column) · [Gantt baseline](https://support.monday.com/hc/en-us/articles/360020978159-The-Gantt-Baseline)
3. **Jira (Atlassian)** — issue types (Epic/Story/Task/Bug/**Sub-task**), priority/status core
   fields, **configurable workflows**; **kanban boards with per-column WIP limits** (Scrum boards
   none natively — sprints timebox); **"blocks / is blocked by" links**; "Blocked" usually a
   custom status + automation.
   <br>[Boards](https://www.atlassian.com/software/jira/guides/boards/overview) · [WIP limits](https://www.atlassian.com/agile/kanban/wip-limits) · [Statuses/priorities](https://support.atlassian.com/jira-cloud-administration/docs/what-are-issue-statuses-priorities-and-resolutions/) · [Issue links](https://confluence.atlassian.com/spaces/JIRASOFTWARESERVER/pages/939938925/Creating+issues+and+sub-tasks) · [MoSCoW in trackers](https://community.atlassian.com/forums/App-Central-articles/Understanding-the-MoSCoW-prioritization-How-to-implement-it-into/ba-p/2463999)
4. **ClickUp** — nested subtasks (same columns as parent; *"one level of nesting covers 90% of use
   cases"*) vs **checklists for simple step items**; List/Board/Gantt views; dependencies
   **"blocks"/"waiting on"** where **a blocked task cannot be marked complete until blockers are
   done** (enforceable or warning-only) and a **native "task unblocked" automation trigger**
   (auto-moving INTO Blocked is still a feature request); unblocking statuses configurable.
   <br>[Tasks & custom fields](https://clickup.com/features/tasks) · [Subtasks guidance](https://clickup.com/learn/topic/task-management/concepts/subtasks/) · [Subtasks vs checklists](https://processdriven.co/hub/subtasks-vs-checklists-vs-descriptions-beginner-clickup-tutorial-to-make-sops-and-templates) · [Dependency relationships](https://help.clickup.com/hc/en-us/articles/6309155073303-Intro-to-Dependency-Relationships) · [Blocked-status request](https://feedback.clickup.com/feature-requests/p/blockingdependency-automation)
5. **Wrike** — **Gantt with dependency chains that auto-shift** (drag a whole chain); **critical
   path highlighted**; **Board view organised by workflow statuses, priority the default sort**
   (drag to reprioritise); **mass edit up to 1,000 tasks**; recurring tasks auto-duplicate.
   <br>[Critical path](https://help.wrike.com/hc/en-us/articles/209604189-Critical-Path) · [Dependencies on Gantt](https://help.wrike.com/hc/en-us/articles/209604229-Task-Dependencies-on-the-Gantt-Chart) · [Board view](https://help.wrike.com/hc/en-us/articles/115000193205-Board-View-in-Wrike) · [Mass editing](https://help.wrike.com/hc/en-us/articles/209603889-Mass-Editing-Tasks)
6. **Microsoft Project / Planner** — classic Project is the **critical-path reference** (full CPM
   on the Gantt); **Planner premium** adds **dependencies + a "Show Critical Path" toggle on
   Timeline view** (base Planner has no true Gantt — third parties fill the gap).
   <br>[Project CPM](https://support.microsoft.com/en-us/project/show-the-critical-path-of-your-project-in-project) · [Planner critical path](https://support.microsoft.com/en-us/planner/show-the-critical-path-of-a-plan) · [Planner dependencies](https://techcommunity.microsoft.com/blog/plannerblog/advanced-project-planning-with-microsoft-planner-dependencies-and-critical-path-/4168235)
7. **Smartsheet** — enabling dependencies activates **Predecessor / Duration / % Complete
   columns**; dependent dates **auto-update** (FS default, lag/lead supported); **multiple
   predecessors → the most-delaying wins**; **% complete auto-rolls up to parent rows**;
   **critical-path highlight toggle** in Gantt.
   <br>[Enable dependencies](https://help.smartsheet.com/articles/765727-enabling-dependencies-using-predecessors) · [Gantt w/ dependencies](https://help.smartsheet.com/learning-track/level-3-solutions/gantt-chart-dependencies) · [Multi-predecessor rule](https://community.smartsheet.com/en/discussion/44381/dependencies-predecessor-dates)
8. **Airtable** — Gantt view with a **dependency field, milestones, critical path**; Kanban view;
   dates/dependencies editable on the timeline. Known limits: same-day FS conflicts, strain at
   ~300 interdependent records.
   <br>[Gantt dependencies & critical path](https://support.airtable.com/articles/9146034701-gantt-view-milestones-dependencies-and-critical-paths) · [Gantt guide](https://www.airtable.com/articles/gantt-chart)
9. **Teamwork.com** — **List/Table/Gantt/Board** views; **dependencies created by dragging an
   arrow in the Gantt**; completion % column on the Gantt; Workload Planner / Resource Schedule
   (7.3's territory).
   <br>[Gantt chart](https://support.teamwork.com/projects/planning-managing-work/viewing-your-project-in-a-gantt-chart) · [Dependencies in Gantt](https://support.teamwork.com/projects/gantt/creating-task-dependencies-in-the-gantt-chart) · [Board view](https://support.teamwork.com/projects/board-view/manage-tasks-board-view)
10. **The frameworks (vocabulary source)** — **MoSCoW** is a single four-option classification
    (Must/Should/Could/Won't); **Eisenhower** a 2×2 of urgency × importance — **no surveyed tool
    ships a native quadrant view** (Asana/ClickUp build it from two custom fields); weighted
    scoring (RICE/WSJF) needs third-party add-ons (Ducalis).
    <br>[ProductPlan MoSCoW](https://www.productplan.com/glossary/moscow-prioritization) · [MoSCoW vs Eisenhower](https://medium.com/@nowacki.lukasz/moscow-method-vs-eisenhower-matrix-prioritization-of-tasks-in-the-project-372f8553c12a) · [ClickUp matrix request](https://feedback.clickup.com/feature-requests/p/eisenhower-matrix-for-prioritization)

**Considered and not cited:** *MS Planner base tier* (checklists + assignment only, covered by 6);
*Notion/Trello* (card boards only — no schedule/deps model the ERP needs); *Ducalis* (third-party
scoring add-on, cited under frameworks).

---

## Feature catalog (deduplicated, prioritized — grouped by the NavERP.md 7.8 bullets, L1182-1188)

Priority key: **P0** = must-have (every surveyed product) · **P1** = differentiator (most) ·
**P2** = defer (enterprise nicety). Spine names grep-verified per the table above.

### Bullet 1 — Task Creation & Assignment
- **Tasks anchored to the WBS with a parent self-FK (sub-tasks)** — every product nests; ClickUp
  keeps subtask columns identical to the parent's. · priority: **P0** · spine: **already exists**
  (`ProjectTask.parent`, `node_type`) — build nothing.
- **A named doer distinct from the accountable owner** — Jira assignee; Monday People column; the
  Wrike/ClickUp norm is ONE assignee per card. · priority: **P0** · spine: **new `assignee` FK →
  AUTH_USER_MODEL on `ProjectTask`** (Ruling 2) · buildable now.
- **Team staffing referenced, not re-declared** — team tasks are role/capacity bookings. ·
  priority: **P0** · spine: **lens over `ResourceAllocation.allocations` on task detail** (RAL/RTE
  untouched) · buildable now.
- **Checklists inside a task** — simple tick items (ClickUp: checklists vs subtasks; Planner
  checklist). · priority: **P0** · spine: **new table `TaskChecklistItem`** (rows give done-stamps
  and feed the progress rollup — a TextField cannot) · buildable now.
- **Bulk operations on the register** — Wrike mass-edits up to 1,000 tasks; Asana multi-select. ·
  priority: **P1** · spine: **POST-only `tsk_bulk_update`** (status/assignee/priority over
  multi-select ids — the `rte_approve_week` bulk-verb idiom) · buildable now.
- **Copied / recurring tasks** — Wrike auto-duplicates per schedule. · priority: **P1/P2** ·
  spine: **deferred** — recurrence needs the 7.17 scheduler; a copy verb is the P1 fallback.
- **Multi-assignee (several people on one card)** · priority: **P2** · **deferred** (M2M forks
  forms/save; single-assignee is the market norm).

### Bullet 2 — Priority & Urgency Scoring
- **A coarse priority field on the task** — Jira priority; Monday Low/Medium/High/Critical; Wrike
  priority as default sort. · priority: **P0** · spine: **`priority` CharField(choices
  low/medium/high/critical) on `ProjectTask`** · buildable now.
- **MoSCoW classification** — one four-option dropdown. · priority: **P1** · spine: **`moscow`
  CharField(null+blank) on `ProjectTask`** ("unclassified" is a state, not a default); the MoSCoW
  lens is a computed grouping, never a table · buildable now.
- **Eisenhower inputs (urgent × important)** — two fields, quadrant computed on read (no native
  quadrant view exists in Asana/ClickUp either). · priority: **P1** · spine: **`is_urgent` +
  `is_important` Booleans on `ProjectTask`**; the 2×2 grid is a computed lens · buildable now.
- **Priority board lens (sort/group by priority, overdue first)** — Wrike's default sort. ·
  priority: **P1** · spine: **computed page `task_priority`** · buildable now.
- **Computed priority SCORE (weighted frameworks, RICE/WSJF)** · priority: **P2** · **deferred →
  7.19** (framework definitions are master data; a stored score goes stale — the 7.4 EVM ruling).

### Bullet 3 — Kanban & Scrum Boards
- **A board whose columns are the workflow states** — every product; Jira maps status→column;
  Wrike's board is status-organised. · priority: **P0** · spine: **computed page `task_board`**
  (columns = existing `STATUS_CHOICES`, cards bucketed in Python — the CRM board idiom) ·
  buildable now.
- **Status progression through POST-only verbs (the drag-and-drop drop)** — moves are audited
  transitions. · priority: **P0** · spine: **`tsk_start`** (stamps `actual_start`) /
  **`tsk_complete`** (stamps `actual_end`, `percent_complete=100`) · buildable now.
- **Completion guarded by blockers** — ClickUp refuses completion until blockers clear. ·
  priority: **P1** · spine: `tsk_complete` **refuses while `is_dependency_blocked`** (Ruling 3) ·
  buildable now.
- **WIP limits per column with over-limit highlighting** — Jira kanban only (Scrum none). ·
  priority: **P1/P2** · spine: counts render now; **limit values are 7.19 configuration** — the
  over-limit badge lights once they exist.
- **Sprint cadence / sprint boards that reset** — Jira Scrum boards. · priority: **P2** ·
  **deferred → 7.13** (Agile ceremonies); NavERP's board is continuous-flow.
- **Swimlanes / card cover fields** · priority: **P2** · **deferred** (cosmetic).

### Bullet 4 — Gantt Charts & Timeline Views
- **Timeline bars from planned dates** — every Gantt product. · priority: **P0** · spine:
  **computed page `gantt_timeline`** — CSS bars over the existing WBS tree (deliverable rollups +
  work packages; `duration_days` exists), **no chart library** (7.16's) · buildable now.
- **Dependency rendering on the timeline** — Teamwork drag-arrows; Asana drawn links. · priority:
  **P1** · spine: predecessor/successor **markers + a links table beside the chart** (arrows are
  JS; the DEP edges already exist) · buildable now.
- **Progress shading from task progress** — Teamwork completion % column; Smartsheet % complete. ·
  priority: **P1** · spine: bar fill from the new `percent_complete` · buildable now.
- **Critical path highlight** — Wrike/Smartsheet/Airtable toggles; MS Project/Planner premium. ·
  priority: **P1** · spine: **`critical_path_ids(project)` already computes it** — highlight that
  set · buildable now.
- **Auto-rescheduling when a predecessor moves** — Monday/Smartsheet/Wrike shift dependent dates. ·
  priority: **P2** · **deferred** (a scheduling engine is 7.17/7.16 territory; 7.2 shipped none) —
  the Gantt page flags conflicts instead.
- **Gantt baseline comparison** — Monday Gantt baseline. · priority: **P2** · **owned by 7.2's
  `ScheduleBaseline`** — render as a lens if room; build no second baseline.

### Bullet 5 — Task Dependencies & Blocking
- **Predecessor/successor links (4 kinds, lag/lead)** · priority: **P0** · spine: **already
  exists** (`TaskDependency` [DEP-]) — build nothing.
- **A computed "blocked" state from unfinished predecessors** — Asana "waiting on"; ClickUp
  blocks/waiting-on. · priority: **P0** · spine: **derived `is_dependency_blocked` property** on
  `ProjectTask` (unfinished FS/SS predecessor ⇒ blocked; never a stored column — Ruling 3) ·
  buildable now.
- **A manual blocked record with unblock criteria** — Monday "Stuck" label; Jira blocked status. ·
  priority: **P0** · spine: **new table `TaskBlock`** — reason, `unblock_criteria`, verb-stamped
  who/when, frozen once unblocked · buildable now.
- **Unblock notification when the blocker completes** — Asana notifies the waiting assignee. ·
  priority: **P1** · spine: **in-page queues** on the board ("unblocked — ready to start");
  mail/push is **7.17's** · buildable now.
- **Visible dependency chain per task (upstream blockers / downstream dependents)** · priority:
  **P1** · spine: **lens section on task detail** over `predecessor_links`/`successor_links` ·
  buildable now.
- **Auto-status flips on block/unblock (automation rules)** — ClickUp's unblocked trigger. ·
  priority: **P2** · **deferred → 7.17** (no rule engine; verbs + audit rows stand in).

---

## Recommended build scope (this pass — 2 NEW models + in-place extension + 3 computed pages)

Sub-module folder **`TaskWorkManagement/`** in `models/ forms/ views/ urls/` (same file name per
layer, sub-package `__init__.py` files stay empty, re-export block `# --- 7.8 Task & Work
Management` added to `apps/projects/models/__init__.py`), migration `0011_…`, templates
`templates/projects/taskwork/…`, seeder block `_taskwork` with its own guard, tests
`test_taskwork_*`. **No new dependency table, no new assignment register, no stored aggregate** —
every board, quadrant, rollup and blocked state is computed on read.

### In-place execution fields on `ProjectTask` (the Ruling-1 extension — same migration)
- `assignee` → `AUTH_USER_MODEL` SET_NULL null+blank `related_name="assigned_project_tasks"`
  (verified free) — the doer; `owner` stays the accountable manager. Help-text points at RAL for
  staffing ("team bookings live on ResourceAllocation").
- `priority` CharField(8, choices low/medium/high/critical, default `"medium"`);
  `moscow` CharField(12, choices must_have/should_have/could_have/wont_have, null+blank).
- `is_urgent` + `is_important` BooleanField(default=False) — the Eisenhower inputs.
- `percent_complete` DecimalField(5,2, default 0, 0–100 validators) — task-grain attestation;
  **deliverable-node rollup is computed on read** (effort-weighted over descendants), never stored.
- `actual_start` / `actual_end` DateField null+blank — stamped ONLY by `tsk_start`/`tsk_complete`
  (editable=False — the verb-written-stamp idiom of 7.4/7.6).
- Forms exclude tenant/number/stamps; new fields join the 7.2 task form (+ a slim execution edit
  form); `tsk_complete` hard-refuses while `is_dependency_blocked` (the ClickUp default).

### 1. `TaskChecklistItem` [**TCL-**] — one tick item inside a task (bullet 1's checklists + the progress feed)
`task` FK → `ProjectTask` CASCADE `related_name="checklist_items"`; `label` CharField(255);
`sequence` PositiveSmallIntegerField; `is_done` BooleanField(default=False); `done_by` FK → User
SET_NULL null+blank editable=False; `done_at` DateTimeField null+blank editable=False — written
exactly once by the POST-only **`tcl_check`** verb (un-tick goes through the same verb + audit).
Index `(tenant, task)`. Derived: per-task `checklist_progress` = done/total — a computed input to
the progress lens, never a column. Prefix **TCL** verified free; **do not shorten to `TASK`**
(crm 1.8 owns it).

### 2. `TaskBlock` [**TBK-**] — one manual block event with its unblock criteria (bullet 5's blocked status)
`task` FK → `ProjectTask` CASCADE `related_name="blocks"`; `reason` TextField;
`unblock_criteria` TextField (what must be true to unblock — the bullet's exact ask);
`blocked_by` FK → User SET_NULL editable=False; `blocked_at` DateTimeField editable=False
(stamped by POST-only **`tsk_block`**); `unblocked_by`/`unblocked_at` editable=False, written
exactly once by **`tsk_unblock`**; `resolution_note` TextField blank. Active = `unblocked_at is
null`. Derived: `task.is_manually_blocked` (any active row), `task.is_blocked` =
`is_dependency_blocked or is_manually_blocked`. Active blocks refuse edit/delete (frozen while
open; frozen entirely once unblocked). Prefix **TBK** verified free.

### Computed pages (GET-only, no model — the 7.3 `capacity_demand` / 7.5 `risk_analysis` precedent)
- **`task_board`** (`task-board/`) — the kanban board: columns = `STATUS_CHOICES` with counts +
  overdue badges, cards show priority/MoSCoW/assignee, per-card `tsk_start`/`tsk_complete`
  buttons, and an **"Unblocked & ready"** queue. WIP counts render; limit values wait for 7.19
  (Ruling 4).
- **`gantt_timeline`** (`gantt-timeline/`) — CSS bars from the WBS tree, progress shading from
  `percent_complete`, dependency markers/link table from DEP edges, **critical-path tasks
  highlighted via `critical_path_ids`**, conflict flags when a successor starts before its FS
  predecessor ends. No chart library (7.16's).
- **`task_priority`** (`task-priority/`) — MoSCoW groups, the Eisenhower 2×2 grid (bucketed on
  read), and the overdue/urgent work queue. `?project=` parsed through a
  `forms.Form`/`as_db_int` (L11/L35), never raw `request.GET`.

**Sidebar entry to add — `LIVE_LINKS["7.8"]`:** `"Task Creation & Assignment":
"projects:tsk_list"` (execution fields land on the existing task registers), `"Priority & Urgency
Scoring": "projects:task_priority"`, `"Kanban & Scrum Boards": "projects:task_board"`, `"Gantt
Charts & Timeline Views": "projects:gantt_timeline"`, `"Task Dependencies & Blocking":
"projects:dependencies"` (7.2's register) + block/checklist lenses on task detail.

**Trade-offs consciously accepted:** boards are form-POST not drag-drop (no JS framework in-repo);
single assignee (M2M is P2); WIP-limit *values* deferred to 7.19 (counts now); no auto-reschedule
(engine = 7.17); `CCA.percent_complete` gets an advisory lens, not a write-back (Ruling 5).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Timesheets, hour approval, billable splits** → **7.3 RTE / 7.11**. 7.8 links `time_entries`,
  builds no second log.
- **Staffing/capacity, workload heat maps, placeholders** → **7.3 `ResourceAllocation` /
  `capacity-demand`** (Teamwork's Workload Planner lives there).
- **Sprint ceremonies, retrospectives, team health** → **7.13**. The board is continuous flow.
- **Meeting-minuted action items** → **7.9** (the 7.6 precedent: 7.8 owns task rows only).
- **Milestones/phase gates, schedule baselines, the WBS CRUD itself** → **7.2** (unchanged).
- **Notifications/reminders on due dates, auto-scheduling, workflow rules, escalations** → **7.17**.
  7.8 writes `core.AuditLog` and renders in-page queues only.
- **Charts/report builder/exports/PDF** → **7.16** (7.8 renders CSS bars and tables).
- **Priority-framework definitions, WIP-limit values, custom field libraries, recurring-task
  schedules** → **7.19 Master Data & Configuration**.
- **Jira/Asana/Monday sync** → **7.18** (a `source_number` soft reference is the pattern).
- **Portfolio roll-ups of boards/priority** → **7.12**.

## Deferred (later passes / integrations)

| Area | Why deferred |
|---|---|
| **Multi-assignee M2M on tasks** | Forks form/save for a differentiator; single assignee is the market norm (Jira; ClickUp guidance). |
| **WIP-limit value storage + over-limit hard stop** | Board configuration is master data → **7.19**; counts and badges ship now. |
| **Sprint cadence / sprint boards / velocity** | **7.13** (Agile ceremonies); the board is continuous flow (Ruling 4). |
| **Auto-rescheduling (dependency date push) / resource levelling** | A scheduling engine → **7.17/7.16**; 7.2 shipped no scheduler. The Gantt page flags conflicts instead. |
| **Computed priority scores (RICE/WSJF/custom weighted)** | Framework definitions are master data → **7.19**; a stored score goes stale (the 7.4 EVM ruling). |
| **Recurring tasks / bulk task duplication** | Recurrence needs the scheduler → **7.17**; a copy verb is the fallback. |
| **Block/unblock notifications (mail/push)** | No mail worker → **7.17**; in-page queues stand in. |
| **Gantt baseline overlay rendering** | **7.2 `ScheduleBaseline`** owns the data; a lens is optional. |
| **Drag-and-drop board JS / timeline arrow drawing** | No JS framework in the repo; POST verbs + markers (the CRM board precedent). |
| **Write-back to `CostControlAccount.percent_complete`** | Attested EV input stays manual (Ruling 5); the computed lens is advisory only. |

## House-rule constraints discovered (lessons that apply)

- **L31** — one sub-module per run; 7.8 builds its own tables only (2 here).
- **L28/L36** — every FK above grep-verified; **extend `ProjectTask`/`TaskDependency` by field and
  lens, never re-declare**. The task-model premise was checked against the docstring contract and
  held.
- **L7/L8/L11/L9/L10/L2/L3** — pin every context key the three computed pages consume; assert
  `str(obj)` tokens on detail pages; validate integer GET filters (`isdigit()` / `as_db_int`);
  guard nullable user FKs (`assignee`, `blocked_by`, `done_by`); `{% comment %}` not `{# #}`.
- **L33** — badges use colour-named classes (`badge-green/red/amber/info/muted/slate`) — grep
  `static/css/theme.css` before writing priority/blocked/overdue badge ternaries.
- **L27** — all 7.8 verbs are `@login_required` (none are privileged/workspace-config writes);
  `tsk_bulk_update` POSTs per selected id with a per-row audit entry.
- **L16** — `actual_start`/`actual_end`/overdue comparisons use `timezone.localdate()`.
- **L29/L35** — no money columns anywhere in 7.8; no hand-parsed Decimals (percentages arrive via
  ModelForms with validators).

**Verified spine summary for the todo agent:** `projects.ProjectTask`
(`ProjectTasks.py:22` — extend in place), `projects.TaskDependency` (`TaskDependencies.py:17`),
`critical_path_ids` (`views/_helpers.py:107`), `projects.ResourceAllocation`
(`ResourceAllocations.py:24`), `projects.ResourceTimeEntry` (`ResourceTimeEntries.py:19`),
`projects.CostControlAccount` (`CostControlAccounts.py:29`), `core.AuditLog`, `AUTH_USER_MODEL`.
**No `TaskChecklistItem`/`TaskBlock` class exists**; prefixes **`TCL`/`TBK` free**
(`TSK`/`TASK`/`DEP`/`RAL`/`RTE`/`SCR` taken); migration **`0011_…`**; URL literals
`task-board/`, `gantt-timeline/`, `task-priority/` disjoint; templates
`templates/projects/taskwork/` new.

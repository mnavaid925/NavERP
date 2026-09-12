# Review — Projects 7.8 Task & Work Management

Six read-only lanes ran **serially** (code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer) over the 7.8 file set
(~48 files: `apps/projects/{models,forms,views,urls}/TaskWorkManagement/`, the in-place
`ProjectPlanningScheduling/ProjectTasks.py` execution extension, integration surfaces
(`__init__.py` re-exports, `admin.py`, seeder `_taskwork`, `navigation.py` LIVE_LINKS,
overview), `templates/projects/taskwork/`, migration 0011, and the two amended planning
test pins). Scope was pinned by file globs, NOT by commit range — parallel sessions are
live in this tree (L46/L48).

Build-phase context for the lanes:
- Smoke gate (inline, `temp/smoke_78.py`): **71/71 PASS** — pages render with content,
  verbs POST-only, one-time stamps hold, blocked-refusal works, bulk update applies,
  member-level access per contract, cross-tenant IDOR → 404, junk params never 500,
  no traceback/None leaks.
- Known contract contradiction resolved at build: contract §2.1 suggested extending 7.2's
  `TaskForm` with the execution fields; built as the separate `TaskExecutionForm` surface
  instead (7.2's tests pin `TaskForm.Meta.fields` to the exact 13; the 7.2 form surface is
  frozen). Reviewers should sanity-check that ruling.
- Smoke observation worth a lane's judgement: the priority lens buckets ALL in-scope tasks
  into Eisenhower quadrants regardless of status (done tasks appear in "Do First").

---

## Lane findings (raw, appended per lane)

### Lane 1 — code-reviewer (serial pass 1)

Scope check: 49 pinned items — all read; taskwork templates on disk are 12, not 13 (the
contract §6 table itself lists 12 — the prompt's count was wrong, not a missing file).
Static review only (no shell reach to run manage.py). Migration 0011 verified correct
(indexes match Meta, additive-only, dependencies right). Both amended planning test pins
verified true. Route table: all 17 routes match the contract exactly.

- [C1] Block/unblock verbs skip the sibling's atomic re-fetch under lock — one-open-blocker invariant is racy
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 146-165 (tsk_block), 176-194 (tsk_unblock)
  finding: `tsk_block` does check-then-mint (`active = obj.blocks.filter(unblocked_at__isnull=True).first()` then `TaskBlock.objects.create(...)`) and `tsk_unblock` does check-then-stamp with no `transaction.atomic()` + `select_for_update()`. The sibling idiom for exactly this shape locks and re-tests: `QualityDefects.py:199-210` (`qdf_raise_issue`), also `ResourceAllocations.py:171-176`, `ProjectIssues.py:157`. Two concurrent `tsk_block` POSTs both pass the active-block check and mint two open rows, breaking the documented "one open blocker at a time" invariant that `_blocker_source`/`is_manually_blocked` rely on (`block = ...first()` then names an arbitrary row); two concurrent `tsk_unblock` POSTs both stamp the row, the second overwriting the first's `resolution_note`/`unblocked_by` — violating the model docstring's "written EXACTLY ONCE". `tsk_start`/`tsk_complete`/`tcl_check` are check-then-act too but their worst case is a same-value overwrite or a toggle-back.
  fix: wrap the guard+write in `with transaction.atomic():` and re-fetch the task/block via `select_for_update()`, re-running the guard inside the lock (the `qdf_raise_issue` shape verbatim), for `tsk_block` and `tsk_unblock` at minimum.
- [I1] Overview 7.8 context keys drift from the contract; "Tasks" card duplicates the existing WBS-nodes count; blocked semantics lost
  file: `apps/projects/views/ProjectInitiation/Overview.py`  lines: 124-132 (template: `templates/projects/overview.html:44-46`)
  finding: Contract §7.5 pins new keys `in_progress_task_count`, `blocked_task_count`, `overdue_task_count`. As-built ships `task_execution_count`, `open_block_count`, `overdue_task_count`. (a) `task_execution_count` is the identical queryset/value as the pre-existing `task_count` (`Overview.py:79` vs `:127`), so `overview.html` renders the same number twice under "WBS nodes" (:23) and "Tasks" (:44) — the pinned in-progress figure is never computed; (b) `open_block_count` counts open `TaskBlock` rows, not blocked tasks — a dependency-blocked task (no manual block) never surfaces in the "Open blockers" card, though the contract's `blocked_task_count` is defined to include it.
  fix: rename to the pinned keys and compute `in_progress_task_count` as a DB count and `blocked_task_count` in Python over a materialized live-task list (the `risk_count` register shape already in this file), deleting the duplicate `task_execution_count`.
- [I2] Navigation LIVE_LINKS "7.8" maps bullet 5 to the wrong route and swaps the pinned extra leaf
  file: `apps/core/navigation.py`  lines: 1829-1839
  finding: Contract §7.4 pins `"Task Dependencies & Blocking": "projects:dependencies"` (bullet 5's links half → 7.2's dependency register, with justification comments recording BOTH deliberate register mappings) and the extra live leaf `"Task Checklist Register": "projects:tcl_list"`. As-built has `"Task Dependencies & Blocking": "projects:tbk_list"` (its comment even re-justifies the deviation) and ships an unpinned `"Active Blockers": "projects:tbk_list?active=1"` leaf instead — the checklist register has no sidebar entry at all.
  fix: restore the pinned mapping to `projects:dependencies` and the `"Task Checklist Register"` leaf (or get the contract amended and record both rulings in the justification comments, which currently document only one side's reasoning).
- [I3] ProjectTaskAdmin surgical edit was never made — no execution columns in admin
  file: `apps/projects/admin.py`  lines: 83-89
  finding: Contract §7.2 step 2 pins a surgical edit of the existing `ProjectTaskAdmin`: `list_display` += `"assignee", "priority", "percent_complete"` and `list_select_related` += `"assignee"`. As-built `list_display`/`list_select_related` are untouched; `grep assignee apps/projects/admin.py` returns nothing. Every other §7.2 admin item landed, so this one read-only integration surface silently didn't.
  fix: apply the pinned two-line edit (and keep `owner` beside `assignee` in `list_select_related`).
- [I4] 7.2 TaskForm never gained the execution fields pinned by contract §2.1 (evidence file sits one step outside the pinned globs)
  file: `apps/projects/forms/ProjectPlanningScheduling/ProjectTasks.py`  lines: 19-30
  finding: Contract §2.1 "Form implications" pins: `TaskForm.Meta.fields` gains `assignee, priority, moscow, is_urgent, is_important, percent_complete` appended after `"sequence"`, with `assignee` joining `owner` in the NOT-`_reject_foreign` set. As-built `Meta.fields` still ends at `"sequence"` and `_reject_foreign` stays `["project", "parent"]` with no assignee carve-out. Consequence: a task cannot be given an assignee/priority/MoSCoW at planning time — only afterwards via `tsk_execute`.
  fix: either apply the pinned TaskForm extension, or amend contract §2.1 to make `TaskExecutionForm` the sole execution write surface and note the TaskForm carve-out there. (Build-phase note: the build deliberately chose the separate-form surface because `test_planning_forms.py` pins `TaskForm.Meta.fields` to the exact 13 — the contract amendment is the fix that preserves the frozen test.)
- [M1] Pre-Integrate direct sub-module import shims and stale "re-exports land in the Integrate step" comments left across all four layers
  file: `apps/projects/urls/TaskWorkManagement/*.py` (all 7), `apps/projects/views/TaskWorkManagement/*.py`, `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:40-42`, `apps/projects/views/ProjectPlanningScheduling/ProjectTasks.py:13`
  finding: Integrate has happened, yet: (a) all seven 7.8 urls modules import view functions directly from `apps.projects.views.TaskWorkManagement.<Module>` while every 7.1-7.7 urls module uses `from apps.projects import views` (26 sibling modules); (b) views/forms import models/forms from their sub-modules beside package re-export imports in the same block; (c) the justifying comments ("the views package re-export lands in the Integrate step") are now false — the re-exports exist; (d) `models/ProjectPlanningScheduling/ProjectTasks.py:40-42`'s comment calls its TaskBlock/TaskChecklistItem imports "load-bearing" for registering reverse relations, but the models package re-exports both and Django resolves string FKs through the app registry — the imports are redundant belt-and-braces, not load-bearing.
  fix: switch urls modules to `from apps.projects import views`, point views/forms at the package re-exports, delete or correct the stale comments (keep the models import only if you want the safety net, with an honest comment).
- [M2] forms `__init__` 7.8 comment miscounts the block; TaskBlockForm/TaskUnblockForm file placement deviates from contract §3
  file: `apps/projects/forms/__init__.py`  lines: 95-104; `apps/projects/forms/TaskWorkManagement/TaskBlocks.py`
  finding: The block comment says "Three forms, no fourth" but re-exports FOUR classes. Separately, contract §3 pins `TaskBlockForm`/`TaskUnblockForm` under `forms/TaskWorkManagement/ProjectTasks.py`; the build put them in `TaskBlocks.py` (defensible under §1's "same file name in all four layers" rule, but the deviation from the explicit §3 pin is unrecorded).
  fix: correct the count comment; if the TaskBlocks.py placement stands, note in the contract or SKILL.md that §1's layer rule superseded §3's file pin.
- [M3] 7.8 admin registrations drift from the pinned tuples; `is_active` column renders raw True/False
  file: `apps/projects/admin.py`  lines: 378-404
  finding: Contract §7.2 pins `TaskChecklistItemAdmin.list_select_related` with `task__project` and `list_display` ordered `task` before `label`; as-built omits `task__project`, adds `created_by`, reorders. `TaskBlockAdmin` pinned with NO `list_filter` and a specific `list_display` — as-built adds unpinned `list_filter` and extra columns `reason`/`is_active`, and swaps `task__project` for `created_by`. The `is_active` property has no `boolean = True` attribute, so the column renders text "True"/"False" instead of Django's on/off icon.
  fix: align the tuples with the contract (or record the additions as rulings); add `@admin.display(boolean=True, ordering="unblocked_at")` for `is_active`.
- [M4] Seeder `_taskwork` misses four pinned coverage items and the `--flush` help text omits the new tables
  file: `apps/projects/management/commands/seed_projects.py`  lines: 42-47 (header), 212-219 (help text), 1838-1880 (_taskwork)
  finding: Contract §7.3 pins "every `moscow` value + unclassified rows" — `task.moscow = moscow[i % 4]` assigns all four to every work package, so the priority page's trailing "Unclassified" group seeds empty; "percent_complete 0/50/100" — 25.00 is also minted; "one `cancelled`" — no WBS spec creates a cancelled task; "one empty checklist" and "enough rows for page 2" — every checklist has exactly 4 items and the total is 12 rows, below `per_page=15`, so no page 2. The `--flush` help text enumerates every flushed table but omits checklist items and blocks despite the code deleting them.
  fix: leave one lead task per project `moscow=None`, seed 15+ checklist items including one empty checklist, add a `cancelled` work package to one WBS spec, and append "checklist items, task blocks" to the help text enumeration.
- [M5] Gantt "today-marker line" reduced to a header badge
  file: `templates/projects/taskwork/gantt_timeline.html`  lines: 83-87
  finding: Contract §6 pins "today line from `today`" (a marker line on the chart); the as-built renders only a conditional header badge and no line on the track. The `today` context key is otherwise unused in the chart body.
  fix: add a vertical marker in `.tw-chart` (e.g. a positioned `.tw-today` div at the today offset %, computable in the view or via a `today_offset_pct` context key).
- [M6] Gantt bar tooltip renders "None% complete" for childless deliverables
  file: `templates/projects/taskwork/gantt_timeline.html`  lines: 102-104
  finding: The `title` attribute is unconditional: `title="… · {{ bar.progress_pct }}% complete"` — when `progress_pct` is `None` (deliverable with no descendant work packages), the tooltip literally reads "None% complete". The visible progress fill is correctly guarded.
  fix: guard the tail of the title with `{% if bar.progress_pct is not None %}`.
- [M7] Bulk update can move done/cancelled tasks to planned/cancelled ungated, carrying stale stamps; dead branch in `tsk_unblock`
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 197-202, 256-294; 186
  finding: `_VERB_GATED_STATUSES` gates only targets `in_progress`/`done`; a bulk `status="planned"` on a `done` task "resurrects" it while `actual_end`/`percent_complete=100`/`actual_start` remain set (no cleanup), so a later `tsk_start` overwrites `actual_start` — the "stamped exactly once" property holds only per-direction. The docstring documents the asymmetry (recorded design note rather than an oversight), but the audit entry for such a reversal is indistinguishable from a gated one. Separately, `previous = "active" if block.unblocked_at is None else "resolved"` has a dead `"resolved"` branch — the queryset filter guarantees `unblocked_at is None`.
  fix: for reversals either gate them too or clear the matching stamps in the same `update_fields` (and say so in the audit `changes`); simplify `previous = "active"`.

### Lane 2 — explorer (serial pass 2)

- [C1] `tsk_bulk_update` resolves the bulk assignee through an unscoped User queryset — the one 7.8 write path that can mint an out-of-tenant FK
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 223-231
  finding: `assignee = get_user_model().objects.filter(pk=assignee_id).first()` — no tenant predicate. The contract's §1 invariant is "every queryset is `filter(tenant=request.tenant)`", and the cited precedent (`TaskForm.owner`, "users can be tenant-less") does not actually authorize this: on the form path `TenantModelForm` auto-scopes the `assignee` queryset and `ModelChoiceField` validation runs against the scoped queryset, so a foreign-tenant user can never be written through `tsk_execute`. The bulk verb has no such validation, so a crafted member POST (`POST /projects/tasks/bulk-update/ assignee=<other-tenant-user-pk>&task_ids=…`) attaches any user of any tenant (or the tenant-less superuser) as the doer on this workspace's tasks — rows the board/priority "my tasks" lens can then never see.
  fix: scope the existence check to the precedent's real population — `filter(Q(tenant=request.tenant) | Q(tenant__isnull=True), pk=assignee_id)` — so tenant users plus the tenant-less superuser are assignable and no foreign-tenant FK can be written.
- [I1] Sidebar `LIVE_LINKS["7.8"]` breaks the pinned bullet→register map and drops the checklist leaf (agrees with Lane 1 I2; architectural consequence recorded here)
  file: `apps/core/navigation.py`  lines: ~1829-1841
  finding: As-built maps `"Task Dependencies & Blocking": "projects:tbk_list"` and ships `"Active Blockers": "projects:tbk_list?active=1"` instead of the pinned `"Task Checklist Register": "projects:tcl_list"`. The contract's mapping encoded the L31 boundary: bullet 5's links half belongs to 7.2's `dependencies` register (7.8 owns only the blocking STATE); bullet 1's checklists are a real register. As-built, the sidebar presents the blocker register as the home of the dependency bullet and gives the checklist register no sidebar entry at all.
  fix: restore `"Task Dependencies & Blocking": "projects:dependencies"` and the `"Task Checklist Register": "projects:tcl_list"` leaf, or amend the contract and record both re-mappings in the justification comment.
- [I2] Overview 7.8 cards render the same number twice and reduce "blocked" to the manual half — the page does not tell one honest story (agrees with Lane 1 I1)
  file: `apps/projects/views/ProjectInitiation/Overview.py`  lines: 124-132 (template `templates/projects/overview.html:23,44`)
  finding: `task_execution_count` is the identical queryset/value as the pre-existing `task_count` (`Overview.py:79`), so the grid shows one number twice ("WBS nodes" and "Tasks"); the pinned `in_progress_task_count` is never computed. `open_block_count` counts open `TaskBlock` rows, so a dependency-blocked task never appears on the landing page. The contract's `blocked_task_count` was defined over `is_blocked`, and the same file already contains the correct shape one block above (`risk_count` computed in Python over one materialized register).
  fix: compute `in_progress_task_count` (DB count) and `blocked_task_count` (Python over a materialized live-task list, the `risk_count` shape) under the pinned key names, delete the duplicate `task_execution_count`, and keep `overdue_task_count`.
- [I3] `tsk_bulk_update` is a fully built, audited mutating route with no caller anywhere in the template layer
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 205-317
  finding: grep over `templates/projects/` finds no reference to `tsk_bulk_update` or `task_ids`. NavERP.md bullet 1 explicitly names "bulk operations", and the sidebar maps that bullet to `projects:tsk_list`, whose template carries no multi-select affordance. The verb's whole security surface is exercised only by direct POST — dead integration from the product's perspective, and the first 7.8 verb a maintainer would "simplify away" because nothing links to it.
  fix: wire the bulk bar into `tsk_list` (checkbox column + status/assignee/priority submits, dropdowns from `owners(tenant)` — which also incidentally contains the C1 scoping fix), or move the verb to the contract's deferred list with a ruling so the as-built matches the intent.
- [I4] Task detail renders the dependency network twice through two different query paths — the 7.8 panel ignores the host view's prepared context lists
  file: `templates/projects/taskwork/_task_dependencies_panel.html`  lines: 17-60
  finding: `tsk_detail` already ships `predecessor_links`/`successor_links` — sliced `[:50]` and `select_related(...)` — and 7.2's own dependency section iterates those context lists. The 7.8 partial instead re-walks `obj.predecessor_links.all` / `obj.successor_links.all`: a fresh unbounded query per manager with no `select_related`, so every `dep.predecessor.number/.name/.status` is a lazy FK load (N+1 on link-heavy tasks), on the same page as the sliced rendering of the same rows.
  fix: iterate the existing `predecessor_links`/`successor_links` context keys in the partial (raising the slice cap if needed), keeping one query path and one bound per page; note the superseded §6 pin in the contract.
- [I5] The priority lens is two different snapshots on one page — the grid and groups are all-status, the queue and counts are live-lens
  file: `apps/projects/views/TaskWorkManagement/TaskPriority.py`  lines: 86-102, 159-178
  finding: `_bucket_quadrants` and `_group_moscow` bucket the entire scoped materialization with no status filter, so done and cancelled tasks sit in "Do First" and "Must Have" indefinitely, while `_work_queue`, `counts.unassigned`, and the board's blocked/overdue figures are all live-status lenses. The build matches the frozen contract's context spec verbatim, so this is a contract-level ruling to amend, not a coding slip — but as shipped the page misleads ("Do First" full of completed work) and is inconsistent with the rest of 7.8's execution surfaces.
  fix: amend contract §5.4 so the MoSCoW groups and Eisenhower quadrants bucket live tasks only (done/cancelled drop out, matching the queue and counts), or keep all-status and say so on the page header; record the ruling either way.
- [M1] The two computed pages duplicate more than the pinned rank map — the whole request scaffold is a two-consumer copy
  file: `apps/projects/views/TaskWorkManagement/TaskBoard.py`  lines: 146-182 (vs `TaskPriority.py:127-160`)
  finding: The contract sanctioned re-declaring `_PRIORITY_RANK` verbatim, but the two modules also carry byte-equivalent `?project=`/`?assignee=` parse blocks, the same queryset builder, and the same 2000-row working-set cap under two names (`_BOARD_CAP` vs `_REGISTER_CAP`).
  fix: when the freeze lifts, promote the parse + queryset scaffold (and the rank map) into `_helpers.py`; until then note the promotion trigger (a third consumer) in both docstrings.
- [M2] The three computed pages introduce page-local `<style>` blocks — no sibling page in the app does this
  file: `templates/projects/taskwork/task_board.html`  lines: 4-21 (also `task_priority.html`, `gantt_timeline.html`)
  finding: grep shows the only `<style>` blocks under `templates/projects/` are the three 7.8 computed pages; the sibling computed boards render entirely through `theme.css` classes. The `tw-*` rules are cleanly prefixed, but this quietly establishes a new styling convention that no contract §6 pin or sibling precedent backs.
  fix: either move the `tw-*` layout rules into `static/css/theme.css` or record the page-local-CSS precedent in the contract/SKILL so the next computed page has a ruling to follow.

**Architectural verdict.** 7.8 sits coherently in the projects spine: extend `ProjectTask` in place, derive every board/quadrant/blocked/rollup figure on read, store nothing but two small verb-stamped tables, keep CCA advisory — executed faithfully, boundary greps clean (no money column, no second dependency graph/time log/assignment register/task table, no reach into 7.3/7.4/7.5), migration additive-only, re-exports and urls concatenation correct. What is not fully coherent lives at the integration seams: the bulk-verb tenant-scoping hole (C1), sidebar/overview drift (I1/I2), the UI-less bulk verb (I3), the doubled dependency render (I4) — all seam-level, plus the one contract-amendment call (I5) on the priority lens's scope.


### Lane 3 — frontend-reviewer (serial pass 3)

Scope note: context-var integrity verified template-by-template against every view's context
dict — no L7/L8 blanks anywhere; filter bars, CRUD completeness, badge fallbacks, empty
states, pagination GET-preservation, reversed URL names all check out.

- [I1] Bulk-update verb is unreachable — no template anywhere POSTs `task_ids`
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 207-317 (route `urls/TaskWorkManagement/ProjectTasks.py:26`)
  finding: `tsk_bulk_update` is fully built (gating, per-row audit, redirect to `tsk_list`) and pinned by the contract as bullet 1's "bulk operations", but a repo-wide grep of `templates/` finds zero occurrences of `name="task_ids"` and zero forms/clicks targeting `projects:tsk_bulk_update` — the feature has no UI entry point.
  fix: add a bulk bar to the task register list (`planning/task/list.html`): per-row checkboxes posting `task_ids`, one status/assignee/priority picker, a single POST form with `{% csrf_token %}` and a confirm — or defer the route out of this pass with a note.
- [I2] Board offers Start/Complete on blocked cards — a guaranteed-refusal click
  file: `templates/projects/taskwork/task_board.html`  lines: 140-152
  finding: the verb block fires for every `planned`/`in_progress` card, including dependency- or manually-blocked ones; `tsk_start`/`tsk_complete` hard-refuse while `is_blocked`, so the button invites an error the page already predicts via its own Blocked badge. The ready queue correctly excludes blocked tasks, making the inconsistency visible on the same page.
  fix: wrap the actions div in `{% if not t.is_dependency_blocked and not t.active_blocks %}` (or render a disabled button with a "clear the block first" title).
- [I3] Gantt deliverable tooltips render raw `None` for dates/progress
  file: `templates/projects/taskwork/gantt_timeline.html`  lines: 102-104
  finding: the bar `title` reads `bar.task.planned_start`/`bar.task.planned_end` and `bar.progress_pct`, but for a deliverable the bar window is the descendant min/max computed in the view — the deliverable's own dates are typically unset, so hovering shows "None → None · None% complete" (raw `None` twice; house law forbids it). Work-package bars are unaffected.
  fix: have `_gantt_bars` put the resolved window (`start`/`end`) on each bar dict and build the tooltip from those, guarding `progress_pct` with `{% if bar.progress_pct is not None %}…{% else %}no rollup{% endif %}`.
- [I4] Today marker is a header badge only — the pinned today line is not drawn on the chart
  file: `templates/projects/taskwork/gantt_timeline.html`  lines: 83-87, 90-116
  finding: the contract (§6) and the view docstring pin "today line from `today`"; the template renders only a conditional `badge-info` in the card header. On the chart itself there is no vertical marker, so "where are we in the window" is unreadable against the bars.
  fix: add one absolutely-positioned `.tw-today` line per track (or a single overlay across `.tw-chart`): `left: {{ today_offset_pct }}%` computed in the view when `window.start <= today <= window.end`.
- [I5] Eisenhower badges flatten Critical to amber, contradicting the suite's own scale
  file: `templates/projects/taskwork/task_priority.html`  lines: 136
  finding: `{% if t.priority == 'critical' or t.priority == 'high' %}` renders Critical and High identically, while every other badge ternary in the same 7.8 suite and the seeded scale use `critical → badge-red`. Same-value-different-colour across one feature is a consistency defect.
  fix: split the branch: critical → `badge-red`, high → `badge-amber`.
- [M1] Overview 7.8 stat cards diverge from the pinned context keys and undercount "blocked"
  file: `templates/projects/overview.html`  lines: 44-46 (view `apps/projects/views/ProjectInitiation/Overview.py:127-132`)
  finding: the contract pins `in_progress_task_count`/`blocked_task_count`/`overdue_task_count`; the page ships `task_execution_count` (all tasks), `open_block_count` (open `TaskBlock` rows) and `overdue_task_count`. Every used key exists (no blank render), but a dependency-blocked task with no manual block — counted as Blocked on the board and priority lens — is invisible in the overview stats, so the landing page and the execution pages disagree on the same word.
  fix: align the cards with the pinned keys/semantics (compute `blocked` over a materialized live list like the board does) or relabel to "Open blocks" to make the narrower meaning explicit.
- [M2] Page-local `<style>` blocks are a new pattern for screen pages (UI consequence: contained)
  file: `templates/projects/taskwork/task_board.html:4-21`, `gantt_timeline.html:4-21`, `task_priority.html:4-14`
  finding: the only prior `<style>` users in the repo are print/certificate templates; every screen page styles through `theme.css`. Judged on UI consequence: the `tw-` prefix prevents collisions, the rules reuse theme variables, and the responsive breakpoints work — a styling-system fork, not a defect.
  fix: promote the `tw-` rules into `theme.css` (same names) in a follow-up so future boards inherit them.
- [M3] Ready-queue table header says "Action", everywhere else says "Actions"
  file: `templates/projects/taskwork/task_board.html`  lines: 177
  finding: sibling tables all use `<th class="table-actions">Actions</th>`; the board's ready queue is the lone singular.
  fix: change the label to "Actions".
- [M4] Start/Complete exist only on the board; the task's own detail page cannot move lifecycle
  file: `templates/projects/planning/task/detail.html`  lines: 41-46, 95
  finding: task detail gains the blocks panel and checklist panel, but not the Start/Complete verbs — the lifecycle entry points live solely on `task_board.html`; the priority lens work queue has no action column either. Contract-conformant (§6 pins the verbs on the board only), but the verb surface is asymmetric: one computed page can start/finish work, the object's own page cannot.
  fix (next pass): add Start/Complete forms (same gating as I2) to the task detail page header or the work queue's rows.

### Lane 4 — performance-reviewer (serial pass 4)

Index coverage: none missing — every hot seeded query is served (tsk status/assignee/priority,
tbk unblocked_at/task, tcl task/is_done, dep both sides). Seeder: linear, one transaction,
no per-row re-query. Clean bands: `task_board`/`task_priority` are the strongest pages in the
file set (one capped materialization + 3 prefetch queries, free-half tests at every call
site, ~6-9 queries per render at any scale); the gantt template triggers no lazy loads.

- [C1] Checklist panel on tsk_detail: double materialization + 2 COUNTs + per-done-item `done_by` N+1
  file: `templates/projects/taskwork/_task_checklist_panel.html`  lines: 13, 14, 19, 27 (view: `apps/projects/views/ProjectPlanningScheduling/ProjectTasks.py` 168-185)
  finding: `{% if obj.checklist_items.all %}` fully materializes the manager into a discarded queryset, `{{ obj.checklist_progress }}` then runs the property's TWO `count()` queries (bypass any prefetch by construction), and `{% for item in obj.checklist_items.all %}` re-resolves `.all` → a second full fetch. Each done item's `item.done_by.get_full_name` is one more query — the fetch has no `select_related("done_by")`. At seed scale (~16 items, ~12 done): ~16 queries for one panel; cost scales linearly with per-task checklist length (unbounded).
  fix: in `tsk_detail` add `Prefetch("checklist_items", queryset=TaskChecklistItem.objects.select_related("done_by"))` on the obj fetch and pass a view-computed progress figure (one annotate, or len over the prefetched list) so the panel never calls `checklist_progress`.
- [C2] Blocks/dependencies panels re-evaluate the derived blockers 3x each and walk links with no select_related
  file: `templates/projects/taskwork/_task_blocks_panel.html`  lines: 15-19, 44; `templates/projects/taskwork/_task_dependencies_panel.html`  lines: 13-17, 22-48
  finding: every `obj.is_dependency_blocked` evaluation = 1 link fetch + 1 `link.predecessor` FK load per link; it is evaluated 3x (blocks panel 15, `obj.is_blocked` 17, deps panel 13). `obj.is_manually_blocked` = 1 `blocks.filter(...).exists()` per call, 3x (16, 17, 44) — a plain `blocks` prefetch would NOT fix it (`.filter()` chains a fresh clone). `obj.blocks.all` (19) is a raw fetch + 1-2 user-FK loads per block row. The deps panel re-fetches `predecessor_links.all`/`successor_links.all` twice each and loads `dep.predecessor`/`dep.successor` per row even though `tsk_detail` already passes select_related link lists in context that the panels ignore. Expected ~20-25 panel queries at seed scale (~30-40 for the whole page vs ~7 needed); same shape on `tsk_execute` (`task_execution.html:13` `obj.is_blocked`).
  fix: in `tsk_detail` (and `tsk_execute`'s object fetch) prefetch `blocks` (+ user FKs), `predecessor_links`/`successor_links` with select_related of the counterpart task, plus a `Prefetch("blocks", ..., to_attr="active_blocks")`; switch badge call sites to the board's free-half idiom; have the panels consume the existing context lists instead of `obj.…links.all`.
- [I1] `tsk_bulk_update`: per-row eager assignee FK load, uncapped id list, double blocker-source queries on refusals
  file: `apps/projects/views/TaskWorkManagement/ProjectTasks.py`  lines: 243-262 (250 specifically)
  finding: `previous_assignee = obj.assignee` dereferences the FK for EVERY row even when assignee is untouched and even for rows later refused — 500 task_ids → up to 500 wasted SELECTs on top of the pinned per-row cost (~3000 round trips in one POST). `task_ids` has no length cap (a forged multi-id POST loops unbounded in-request). A gated refusal re-queries the blocker source: `obj.is_blocked` then `_blocker_source` recomputes ≈ 5-6 queries/row.
  fix: compare `obj.assignee_id` (free) and load the old User only inside the assignee audit branch; cap the id list (the `_BOARD_CAP` precedent, e.g. 500) or refuse oversized batches; reuse one active-block fetch for both the gate and the message.
- [I2] Register pages materialize the whole tenant task table for a filter dropdown, uncapped
  file: `apps/projects/views/TaskWorkManagement/TaskChecklistItems.py`  lines: 34-37; `apps/projects/views/TaskWorkManagement/TaskBlocks.py`  lines: 41-44
  finding: `ProjectTask.objects.filter(tenant=…).select_related("project").order_by("number")` in `extra_context` is unbounded — at the pinned 2000-task register every tcl_list/tbk_list render joins and ships 2000 rows + 2000 `<option>` elements per request. Same shape on tcl_create/tcl_edit via the form's task dropdown.
  fix: cap the dropdown queryset (the `GAP_LIMIT`/`[:25]` precedent in ScopeMatrix.py:122) or swap the `<select>` for a search input.
- [I3] Gantt: task table and dependency table each fetched twice per request
  file: `apps/projects/views/TaskWorkManagement/GanttTimeline.py`  lines: 226, 246, 248
  finding: `nodes = list(project.tasks…)` (226), then `critical_path_ids(project)` (246) re-fetches the work packages plus the same dep set, then `_dependency_rows` (248) re-queries the identical TaskDependency filter. Bounded (per-project, 4 queries total) — waste, not breakage.
  fix: compute `conflicts` from the `dep_rows` result so deps are fetched once; once `_helpers` unfreezes, let `critical_path_ids` accept prefetched nodes/edges. Acceptable if documented as-is.
- [M1] Overview 7.8 block: `task_execution_count` repeats the identical COUNT already run for `task_count`
  file: `apps/projects/views/ProjectInitiation/Overview.py`  lines: 79, 127
  finding: both keys run `ProjectTask.objects.filter(tenant=tenant).count()` — one redundant COUNT per render of the module landing page.
  fix: reuse the `task_count` value (alias in the view).
- [M2] Board/priority link prefetch costs 2 queries where 1 suffices
  file: `apps/projects/views/TaskWorkManagement/TaskBoard.py`  lines: 171-176; `apps/projects/views/TaskWorkManagement/TaskPriority.py`  lines: 148-153
  finding: `prefetch_related("predecessor_links__predecessor")` issues one query for links plus one for predecessors; a chained `Prefetch` with `select_related("predecessor")` does it in one (verdicts unchanged either way).
  fix: swap to the chained `Prefetch` in both modules.

### Lane 5 — qa-smoke-tester (serial pass 5, report-only)

Script: `temp/qa_smoke_78.py` (gitignored; verb edges on throwaway SMOKETEST rows, Acme/Globex
read-only) — 52/52 checks green. Clean bands: state-machine refusals name their source; unblock-twice
refused, trail written exactly once, audit payloads all name verb + from/to; `tcl_edit` on a DONE item
leaves the one-time stamps untouched; `tcl_delete` keeps `checklist_progress` consistent; combined
filters exact both directions; pagination truth (16 items → 2 pages, page 2 carries row 16, links
preserve filters); gantt on undated/zero-task projects renders states, no 500; bulk mixed/foreign/empty
id handling truthful ("No tasks updated — 1 skipped", zero cross-tenant write); TSK-00012 (no
checklist/blocks/deps) renders every panel empty state with zero raw None.

- [I1] The six execution fields have no reachable write surface anywhere in the UI — `tsk_execute` is orphaned
  evidence: grep over `templates/` and `apps/core/navigation.py` finds zero references to `projects:tsk_execute` — no link, button, or nav entry anywhere; 7.2's task detail offers only Edit/Delete, and `TaskForm.Meta.fields` still ends at `"sequence"` (the §2.1 deviation already logged as Lane 1 I4). Runtime corroboration: `task_priority.html:114` empty state tells the user to "set a task's MoSCoW classification on its Execute page" — an instruction that dead-ends; the board/priority/gantt pages all render priority/MoSCoW/assignee/percent values no page can set. Contract §2.1 pinned those fields joining `TaskForm`, and §5.1 built the Execute page — the build smoke passed 71/71 only because it hits routes directly.
  fix: add an "Execute" entry point on the task-detail page header (or per board card) linking to `tsk_execute`; or take Lane 1 I4's contract-amendment route and add at least one discoverable surface for `TaskExecutionForm`.
- [M1] `tsk_block` has no status gate — blocking DONE (and CANCELLED) work is allowed
  evidence: walked a throwaway task to done, then POSTed `tsk_block` → 302, an active TBK minted on the finished task; its detail shows "Manually blocked" + the Unblock form, the board `blocked_count` includes it (red badge on a Done card). Contract §5.1 pins only the one-open-blocker refusal — as-built == contract letter, but semantically odd.
  fix: add a status gate to `tsk_block` (refuse terminal statuses with a named message) or amend the contract to bless blocking finished work.
- [M2] The execution form silently overwrites a done task's verb-attested `percent_complete=100` (and writes freely on cancelled tasks)
  evidence: on a done task (pct 100.00, `actual_end` stamped), POST `tsk_execute {percent_complete: 40.00}` → 200, pct now 40.00, status still done — the 100% attestation of `tsk_complete` is one form POST away from being contradicted, and the low pct then drags the effort-weighted deliverable rollups. On a CANCELLED task the same POST also saved priority/moscow/assignee. Contract pins no gate (only `actual_start`/`actual_end` are `editable=False`) — as-built == contract letter; directly URL-reachable.
  fix: gate `percent_complete` (freeze or clamp to 100) when `status in ("done", "cancelled")` in `TaskExecutionForm.clean()`, or document the overwrite as intended.
- [M3] Bulk terminal transitions bypass block gating — an open TaskBlock outlives cancellation
  evidence: throwaway task to in_progress, active TBK raised, then `tsk_bulk_update status=cancelled` → applied; row now `cancelled` with the block still open (`is_manually_blocked` stays True forever until someone unblocks a cancelled task). As-built matches the contract's explicit gating list (`_VERB_GATED_STATUSES = ("in_progress", "done")` only) — extends Lane 1 M7. (Bulk foreign-tenant ids cleanly skipped; empty `task_ids` a clean no-op.)
  fix: on a terminal bulk transition, either refuse rows with open blocks (naming the TBK) or auto-note the orphaned block; at minimum document the state in the contract.
- [M4] Out-of-tenant `?assignee=`/`?project=` on the three computed pages silently degrade to the UNFILTERED workspace (contract-pinned; zero leak)
  evidence: as Acme admin, `task_priority?assignee=<admin_globex.pk>` → 200, context `assignee` None, no Globex names in the body, but the full Acme workspace renders — the "my tasks" lens silently drops instead of showing empty. Contract §5.4 explicitly pins "an out-of-tenant id degrades to `None`, never a 500" — as-built == contract, no cross-tenant leak.
  fix: optional polish only — flash "not in this workspace" or render the empty state when a parsed id resolves to None while one was supplied; otherwise leave as pinned.

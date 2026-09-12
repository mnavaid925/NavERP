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


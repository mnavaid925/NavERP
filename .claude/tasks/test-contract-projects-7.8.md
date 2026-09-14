# TEST CONTRACT — NavERP 7.8 Task & Work Management (`projects`)

Pins the fixtures, the naming rule, and the computed figures the four test modules assert.
Written BEFORE the tests (Phase 6 step 1). Base: the 7.8 fix pass (`f0ec2180`).

## 1. Naming rule

Every test is `test_taskwork_*`; every helper is `_taskwork_*`; every fixture is `taskwork_*`.
No collision with `_planning_*` / `_quality_*` / `_scope_*`. The 7.8 model is `ProjectTask`,
which 7.2 owns — the `taskwork_*` prefix is what keeps the two lanes apart.

## 2. Fixtures to append to `apps/projects/tests/conftest.py` (APPEND-ONLY, L43)

The `taskwork_*` block reuses 7.2's spine (`tenant_a/tenant_b`, `admin_user`, `member_client`,
`planning_project_a/_b`, `planning_task_a/_b`, `planning_wbs_tree_a`, `planning_dependency_a`)
rather than rebuilding it.

### Factories

| Factory | Signature | Defaults |
|---|---|---|
| `_taskwork_checklist_item` | `(tenant, task, **overrides)` | `label="Checklist item NN"`, `sequence=0`, `is_done=False`, no stamps |
| `_taskwork_block` | `(tenant, task, **overrides)` | `reason=…`, `unblock_criteria=…`, `blocked_by=None`, `blocked_at=None`, `unblocked_at=None` (so it is ACTIVE unless overridden) |
| `_taskwork_today` | `()` | `timezone.localdate()` — never `date.today()` (L16) |

### Lifecycle fixtures

| Fixture | What it is |
|---|---|
| `taskwork_task_planned_a` | a `planned` work package on project A |
| `taskwork_task_in_progress_a` | `in_progress`, `actual_start` set, `percent_complete=50.00` |
| `taskwork_task_done_a` | `done`, `actual_start`/`actual_end` set, `percent_complete=100.00` |
| `taskwork_task_cancelled_a` | `cancelled`, no actuals |
| `taskwork_task_blocked_a` | `in_progress` + an OPEN `TaskBlock` (the manual-block state) |
| `taskwork_task_dep_blocked_a` | `planned` with an unfinished FS predecessor (the dependency-blocked state) |
| `taskwork_checklist_mixed_a` | 4 items on one task, 3 done / 1 open → `checklist_progress == 75` |
| `taskwork_checklist_empty_a` | a task with NO checklist → `checklist_progress is None` |
| `taskwork_block_active_a` / `taskwork_block_closed_a` | one open, one with the full unblock trail |
| `taskwork_fill_checklist` | `(task, count, done=…)` → the register's page-2 case |

### Actors

`taskwork_admin_client` (tenant A admin), `taskwork_member_client` (tenant A member),
`taskwork_anon_client`, `taskwork_tenantless_client`, `taskwork_csrf_client`.

## 3. Pinned model facts

* `ProjectTask.STATUS_CHOICES` — `planned, in_progress, done, cancelled` (4 values).
* `ProjectTask.PRIORITY_CHOICES` — `low, medium, high, critical` (4).
* `ProjectTask.MOSCOW_CHOICES` — `must_have, should_have, could_have, wont_have` (4), and the
  field is **nullable** (`moscow=None` = the Unclassified bucket).
* `_TERMINAL_STATUSES = ("done", "cancelled")` in the view module — the `tsk_block` gate.
* `TaskChecklistItem` [TCL-], `TaskBlock` [TBK-]; `TaskBlock.is_active` is
  `unblocked_at is None`.
* Indexes: `tcl_tnt_task_idx`, `tcl_tnt_done_idx`, `tbk_tnt_task_idx`, `tbk_tnt_unblocked_idx`
  (7.8's own), plus `tsk_tnt_assignee_idx` / `tsk_tnt_priority_idx` (the in-place extension).

## 4. Pinned view facts

| Fact | Value |
|---|---|
| `tsk_block` on a `done`/`cancelled` task | refused, message names the status |
| `tsk_block` with an open block already | refused, message names the TBK number |
| `tsk_unblock` with no open block | `messages.info`, no write |
| `tsk_bulk_update` batch cap | `_BULK_CAP = 500`; beyond it a truthful `messages.info` |
| `tsk_bulk_update` foreign/forged id | skipped (`refused += 1`), never written |
| `tsk_bulk_update` terminal transition with an open block | refused, names the TBK number |
| `tsk_detail` `checklist_progress` context | `int` 0–100, or `None` when the checklist is empty |
| `gantt_timeline` `today_offset_pct` | a float when today is inside the window, else `None` |
| Every 7.8 verb | `@require_POST` — a GET is **405** for BOTH actors |
| `TaskExecutionForm` on a `done` row | `percent_complete` frozen to its stored value |
| `TaskExecutionForm` on a `cancelled` row | refuses with a named error |

## 5. Post-fix gates (what the fix pass changed, and what the tests must hold)

| Gate | Assertion |
|---|---|
| C1 | two concurrent `tsk_block` POSTs mint at most ONE open block |
| C2 | a foreign-tenant `assignee` pk in the bulk POST writes nothing |
| I7 | `tsk_detail` reads the view-computed `checklist_progress`, never `obj.checklist_progress` |
| I8 | every gantt tooltip carries a date and never the string `None` |
| I9 | the bulk POST is capped and says so |
| I10 | a blocked card renders no Start/Complete form |
| M6 | the today line renders iff today is inside the window |
| M8 | terminal work cannot be blocked |
| M9 | a done row's `percent_complete` survives a `tsk_execute` POST |
| M10 | a terminal bulk transition refuses a row with an open block |
| M14 | the board/priority prefetch is a chained `Prefetch`, not `__`-nested |

## 6. Module split

| File | Covers |
|---|---|
| `test_taskwork_models.py` | numbering, choices, `is_active`, derived blocking, the in-place fields, indexes |
| `test_taskwork_forms.py` | `TaskExecutionForm` field set + the M9 guards; `TaskChecklistItemForm`; the two block forms |
| `test_taskwork_views.py` | all 17 routes, the four computed pages, every verb, the bulk bar, pagination |
| `test_taskwork_security.py` | IDOR 404s, both-actor 405s, role gates, CSRF, mass assignment, crafted FKs, XSS |

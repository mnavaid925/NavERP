# Contract — Projects 7.2 Project Planning & Scheduling

Frozen before any code. Every choice machine value, url name, template path, context key and
index name below is **the spec** — templates and tests compare against these exact strings.

## Namespaces

| thing | value |
|---|---|
| app | `apps.projects` (`app_name = "projects"`) — exists, no settings/urls wire-up |
| backend sub-module folder | `ProjectPlanningScheduling/` in each of `models/ forms/ views/ urls/` |
| template slug | `templates/projects/planning/` |
| entity files | `ProjectTasks.py`, `TaskDependencies.py`, `ProjectMilestones.py`, `ScheduleBaselines.py` (same name in all four layers) |
| template entity folders | `task/`, `taskdependency/`, `milestone/`, `schedulebaseline/` (lowercase singular) |
| url stems | `tsk_`, `dep_`, `mst_`, `bsl_` |
| path prefixes | `tasks/`, `dependencies/`, `milestones/`, `baselines/` (under the `/projects/` mount) |
| number prefixes | `TSK`, `DEP`, `MST`, `BSL` (per-tenant, `next_number`, unique only per (tenant, number) per model) |
| migration | next incremental = `0003_…` |
| test subslug | `planning` → fixtures `planning_*`, helpers `_planning_*`, tests `test_planning_*` |

**Scope guard:** 7.2 owns the *plan* (structure, sequence, estimates, gates, frozen baseline). NO
money columns (7.4), no timesheets (7.3 / `hrm.Timesheet`), no risk rows (7.5), no execution
actuals/assignments workflow (7.8 extends `ProjectTask` in place). No second attachment store.

## 🚨 Invariants carried from 7.1

- `AuditLog.action` is varchar(10): allowed actions here = `create`, `update`, `delete`,
  `achieve`, `activate`, `promote` (all ≤ 10 chars; verb detail goes in `changes`).
- A nullable FK must NEVER sit inside a `|default:` filter argument in a template (hard 500).
- Multi-line template notes use `{% comment %}` blocks, never `{# #}`.
- Badge classes colour-named only: `badge-green/-amber/-red/-info/-slate/-muted`.
- Entity modules star-import `_base` / `_common` + explicit `from … import models` etc.; all
  package imports absolute; sub-package `__init__.py` files stay EMPTY (7.1 precedent); re-export
  blocks go in the four TOP-LEVEL `__init__.py` files only.
- `TenantUniqueMixin` BEFORE `TenantModelForm` on every form whose model `clean()` compares FK
  tenant; `_reject_foreign` re-checks every tenant-scoped FK that renders as a field.
- Factory saves in seeders/tests are `obj.save()`, never `bulk_create` (numbering).

## Model 1 — ProjectTask [TSK-]

`models/ProjectPlanningScheduling/ProjectTasks.py`. The WBS node and the schedulable activity in
one row (`node_type` discriminates): ERD module-7 `ProjectTask`; 7.8 extends THIS row.

Base `TenantNumbered`, prefix `TSK`. `Meta.ordering = ["project_id", "sequence", "id"]`.
`unique_together = ("tenant", "number")`.

### CHOICES (exact machine values)

- `NODE_TYPE_CHOICES`: `deliverable` (Deliverable — summary/rollup node), `work_package`
  (Work Package — schedulable leaf). default `work_package`.
- `STATUS_CHOICES`: `planned` (Planned), `in_progress` (In Progress), `done` (Done),
  `cancelled` (Cancelled). default `planned`.
- `ESTIMATION_CHOICES`: `bottom_up` (Bottom-Up), `top_down` (Top-Down), `analogous` (Analogous),
  `parametric` (Parametric). default `bottom_up`.
- `CONFIDENCE_CHOICES`: `high` (High), `medium` (Medium), `low` (Low). default `medium`.

### Fields

| field | definition |
|---|---|
| `project` | FK `projects.Project` CASCADE, `related_name="tasks"` |
| `parent` | FK `"self"` SET_NULL, null+blank, `related_name="children"` |
| `node_type` | CharField(12), choices above, default `work_package` |
| `name` | CharField(255) |
| `description` | TextField blank |
| `owner` | FK `AUTH_USER_MODEL` SET_NULL, null+blank, `related_name="planned_project_tasks"` |
| `status` | CharField(12), choices above, default `planned` |
| `planned_start` | DateField null+blank |
| `planned_end` | DateField null+blank |
| `effort_hours` | DecimalField(8, 2), null+blank, MinValueValidator(0) |
| `estimation_method` | CharField(12), choices above, default `bottom_up` |
| `confidence` | CharField(8), choices above, default `medium` |
| `sequence` | PositiveSmallIntegerField default 0 (order among siblings) |
| `created_by` | FK `AUTH_USER_MODEL` SET_NULL, null+blank, **editable=False**, `related_name="+"` |

Indexes: `("tenant","project")` → `tsk_tnt_project_idx`; `("tenant","status")` →
`tsk_tnt_status_idx`; `("tenant","project","parent")` → `tsk_tnt_prj_parent_idx`;
`("tenant","node_type")` → `tsk_tnt_ntype_idx`.

Derived (properties, NEVER columns): `duration_days` = `(end - start).days + 1` when both dates
set else `None`. `clean()`: `planned_end >= planned_start` (scm.WorkOrder precedent). WBS codes
(`1.2.3`) are view-computed from the prefetched tree — never stored.

### Form — TaskForm

`fields` = project, parent, node_type, name, description, owner, status, planned_start,
planned_end, effort_hours, estimation_method, confidence, sequence. Excludes tenant, number,
created_by. `clean()`: parent must belong to the chosen project; walking the new parent's
ancestor chain must never reach `self` (cycle guard, bounded walk); `_reject_foreign` on
`project`, `parent`, `owner` (owner is a User — users carry `tenant`; `_reject_foreign` works).

### Routes (`tasks/`) + context keys

| url name | view | template | context |
|---|---|---|---|
| `tsk_list` | `tsk_list` | `projects/planning/task/list.html` | `object_list`, `page_obj`, `q`, `status_choices`, `node_type_choices`, `estimation_method_choices`, `projects` |
| `tsk_tree` (literal `tasks/tree/`) | `tsk_tree` | `projects/planning/task/tree.html` | `project` (selected or None), `projects`, `roots`, `tree_max_depth` (5), `critical_ids` (set of pks) |
| `tsk_create` | `tsk_create` | `projects/planning/task/form.html` | `form`, `is_edit=False` |
| `tsk_detail` | `tsk_detail` | `projects/planning/task/detail.html` | `obj`, `child_tasks`, `predecessor_links`, `successor_links` |
| `tsk_edit` | `tsk_edit` | `projects/planning/task/form.html` | `form`, `is_edit=True`, `obj` |
| `tsk_delete` | `tsk_delete` | — | POST-only, `crud_delete` |

Tree view decorates each node instance (in Python, not stored) with: `wbs_code` (str),
`is_critical` (bool), `kids` (the decorated child instances — the recursive include MUST walk
`node.kids`, never `node.children.all`: prefetch_related returns distinct Python objects, which
would render undecorated), and for deliverables `rollup_start`, `rollup_end`,
`rollup_effort_hours`, `rollup_count`. `_tree_node.html` include mirrors hrm's objective tree
(bounded recursion).

## Model 2 — TaskDependency [DEP-]

`models/ProjectPlanningScheduling/TaskDependencies.py`. Base `TenantNumbered`, prefix `DEP`.
`Meta.ordering = ["-created_at", "-id"]`.
`unique_together = ("tenant", "number")` + `("tenant", "predecessor", "successor")`.

### CHOICES

- `LINK_TYPE_CHOICES`: `finish_to_start` (Finish-to-Start), `start_to_start` (Start-to-Start),
  `finish_to_finish` (Finish-to-Finish), `start_to_finish` (Start-to-Finish).
  default `finish_to_start`.

### Fields

| field | definition |
|---|---|
| `predecessor` | FK `projects.ProjectTask` CASCADE, `related_name="successor_links"` |
| `successor` | FK `projects.ProjectTask` CASCADE, `related_name="predecessor_links"` |
| `link_type` | CharField(16), choices above, default `finish_to_start` |
| `lag_days` | SmallIntegerField default 0 (positive = lag, negative = lead) |
| `note` | TextField blank |

Index: `("tenant","successor")` → `dep_tnt_succ_idx` (the unique_together already covers the
`tenant, predecessor` prefix). `clean()`: no self-link; both tasks same project AND same tenant.

### Form — TaskDependencyForm

`fields` = predecessor, successor, link_type, lag_days, note. `_reject_foreign` on predecessor +
successor (both are tenant-stamped Task rows).

### Routes (`dependencies/`) + context keys

| url name | view | template | context |
|---|---|---|---|
| `dep_list` | `dep_list` | `projects/planning/taskdependency/list.html` | `object_list`, `page_obj`, `q`, `link_type_choices`, `projects` |
| `dep_create` | `dep_create` | `projects/planning/taskdependency/form.html` | `form`, `is_edit=False` |
| `dep_detail` | `dep_detail` | `projects/planning/taskdependency/detail.html` | `obj` |
| `dep_edit` | `dep_edit` | `projects/planning/taskdependency/form.html` | `form`, `is_edit=True`, `obj` |
| `dep_delete` | `dep_delete` | — | POST-only |

## Model 3 — ProjectMilestone [MST-]

`models/ProjectPlanningScheduling/ProjectMilestones.py`. Base `TenantNumbered`, prefix `MST`.
`Meta.ordering = ["target_date", "id"]` (date-ordered on purpose, documented in Meta docstring).
`unique_together = ("tenant", "number")`.

### CHOICES

- `STATUS_CHOICES`: `planned` (Planned), `in_review` (In Review), `achieved` (Achieved),
  `missed` (Missed), `cancelled` (Cancelled). default `planned`.

### Fields

| field | definition |
|---|---|
| `project` | FK `projects.Project` CASCADE, `related_name="milestones"` |
| `anchor_task` | FK `projects.ProjectTask` SET_NULL, null+blank, `related_name="milestones"` |
| `name` | CharField(255) |
| `description` | TextField blank |
| `target_date` | DateField |
| `is_phase_gate` | BooleanField default False |
| `entry_criteria` | TextField blank |
| `exit_criteria` | TextField blank |
| `status` | CharField(12), choices above, default `planned` |
| `actual_date` | DateField null+blank, **editable=False** — stamped by `save()` the first time
status becomes `achieved`, cleared if status leaves `achieved` (crm.CrmMilestone idiom) |

Indexes: `("tenant","project")` → `mst_tnt_project_idx`; `("tenant","status")` →
`mst_tnt_status_idx`. `clean()`: anchor_task (when set) must belong to the same project.

### Form — MilestoneForm

`fields` = project, anchor_task, name, description, target_date, is_phase_gate, entry_criteria,
exit_criteria, status. Excludes tenant, number, actual_date. `_reject_foreign` on project +
anchor_task.

### Routes (`milestones/`) + context keys

| url name | view | template | context |
|---|---|---|---|
| `mst_list` | `mst_list` | `projects/planning/milestone/list.html` | `object_list`, `page_obj`, `q`, `status_choices`, `projects` |
| `mst_create` | `mst_create` | `projects/planning/milestone/form.html` | `form`, `is_edit=False` |
| `mst_detail` | `mst_detail` | `projects/planning/milestone/detail.html` | `obj` |
| `mst_edit` | `mst_edit` | `projects/planning/milestone/form.html` | `form`, `is_edit=True`, `obj` |
| `mst_delete` | `mst_delete` | — | POST-only |
| `mst_achieve` (POST verb) | `mst_achieve` | — | audit `achieve`; refuses cancelled/already-achieved |

## Model 4 — ScheduleBaseline [BSL-]

`models/ProjectPlanningScheduling/ScheduleBaselines.py`. Base `TenantNumbered`, prefix `BSL`.
`Meta.ordering = ["-created_at", "-id"]`. `unique_together = ("tenant", "number")`.

### CHOICES

- `BASELINE_TYPE_CHOICES`: `baseline` (Frozen Baseline), `what_if` (What-If Scenario).
  default `baseline`.

### Fields

| field | definition |
|---|---|
| `project` | FK `projects.Project` CASCADE, `related_name="schedule_baselines"` |
| `name` | CharField(255) |
| `baseline_type` | CharField(8), choices above, default `baseline` |
| `is_active` | BooleanField default False (exactly one active per project enforced by the
activate/promote verbs inside `transaction.atomic()` — NO conditional unique constraint:
MySQL/MariaDB cannot enforce one) |
| `frozen_on` | DateField null+blank, **editable=False** — set when the row is frozen |
| `planned_finish` | DateField null+blank, **editable=False** — snapshot at freeze (max task `planned_end`) |
| `task_count` | PositiveIntegerField null+blank, **editable=False** — snapshot at freeze |
| `total_effort_hours` | DecimalField(12, 2) null+blank, **editable=False** — snapshot at freeze |
| `strategy_note` | TextField blank (schedule compression applied: fast-tracking/crashing) |
| `note` | TextField blank |

These snapshot columns are freeze-time evidence, NOT live aggregates — the one legitimate
stored-derived case (a frozen baseline that recomputed itself would not be frozen). Task-level
snapshots are a documented future extension; 7.2 freezes summary figures only.

Index: `("tenant","project")` → `bsl_tnt_project_idx`. Model method `freeze_snapshot()`
aggregates the project's live tasks into the snapshot columns; called by the create view (when
type = `baseline`) and by `bsl_promote` BEFORE save.

State guards: a `baseline` row is frozen — `bsl_edit`/`bsl_delete` refuse it with a message;
`what_if` rows edit/delete freely. Verbs (both `@tenant_admin_required` + POST):
- `bsl_activate` — only `baseline` rows; flips `is_active` on, all siblings off, atomically.
- `bsl_promote` — only `what_if` rows; becomes `baseline`, snapshots, freezes, activates.

### Form — BaselineForm

`fields` = project, name, baseline_type, strategy_note, note. `_reject_foreign` on project.

### Routes (`baselines/`) + context keys

| url name | view | template | context |
|---|---|---|---|
| `bsl_list` | `bsl_list` | `projects/planning/schedulebaseline/list.html` | `object_list`, `page_obj`, `q`, `baseline_type_choices`, `projects` |
| `bsl_create` | `bsl_create` | `projects/planning/schedulebaseline/form.html` | `form`, `is_edit=False` |
| `bsl_detail` | `bsl_detail` | `projects/planning/schedulebaseline/detail.html` | `obj` |
| `bsl_edit` | `bsl_edit` | `projects/planning/schedulebaseline/form.html` | `form`, `is_edit=True`, `obj` |
| `bsl_delete` | `bsl_delete` | — | POST-only, refuses frozen rows |
| `bsl_activate` (POST verb) | `bsl_activate` | — | audit `activate` |
| `bsl_promote` (POST verb) | `bsl_promote` | — | audit `promote` |

## Shared helpers

- `views/_helpers.py` gains `critical_path_ids(project)` — longest-chain pass over the
  dependency DAG (visited-set cycle guard, deterministic by (sequence, id)); returns a set of
  task pks; simplification (planning-grade longest chain, not full CPM backward pass)
  documented in its docstring. Tree decorations + WBS coding helper live in the ProjectTasks
  view module (single-consumer).

## Seeded shape (per tenant, idempotent guard `ProjectTask.objects.filter(tenant=...).exists()`)

For each of the tenant's 3 seeded projects: a 3-deliverable WBS with 2–3 work packages each
(~8–10 `TSK-` rows, varied estimation_method/confidence, chained dates), one FS chain long
enough to be the critical path + one SS link + one lagged link (`DEP-` rows), 3 `MST-` rows
(one achieved phase gate with actual_date, one in_review, one planned), 1 active frozen
`BSL-` baseline + 1 `what_if`. `--flush` deletes children-first: ScheduleBaseline,
ProjectMilestone, TaskDependency, ProjectTask.

## `LIVE_LINKS["7.2"]`

```python
"7.2": {
    "Work Breakdown Structure (WBS)":       "projects:tsk_tree",
    "Task Sequencing & Dependency Mapping": "projects:dep_list",
    "Duration & Effort Estimation":         "projects:tsk_list?node_type=work_package",
    "Milestone & Phase-Gate Definition":    "projects:mst_list",
    "Schedule Baseline & Version Control":  "projects:bsl_list",
    "Task Register":                        "projects:tsk_list",  # extra live leaf
}
```

Overview page (`projects/overview.html` + `Overview.py`): one aggregate per new table
(task_count, milestone_count, baseline_count + dependency_count) and four quick-link rows
(Task Register, Dependencies, Milestones, Baselines) in the existing table style.

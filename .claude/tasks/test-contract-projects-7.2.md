# Test contract — Projects 7.2 Project Planning & Scheduling (`apps/projects`)

**Phase 6, step 1.** Everything below is pinned from the **as-built source** (`models/ forms/ views/
urls` under `*ProjectPlanningScheduling*`, migration `0003_projecttask_projectmilestone_
schedulebaseline_and_more`), not from `.claude/tasks/contract-projects-7.2.md` (the *build*
contract). Where the two disagree, **this file wins**. Steps 2–5 write the four test files against
these names — a wrong name here becomes four wrong test files.

The four files, in build order: `test_planning_models.py` → `test_planning_forms.py` →
`test_planning_views.py` → `test_planning_security.py`. Planned test counts: **16 / 15 / 21 / 12**
(64 total). The numbered lists in §6 are the implementation spec — write exactly those functions.

---

## 0. How the suite runs

| | |
|---|---|
| Settings | `config.settings_test` (SQLite `:memory:`) via `pytest.ini`; add `--nomigrations` while iterating, never for the final run |
| Command | `venv\Scripts\python.exe -m pytest apps/projects -q` |
| App mount | `/projects/` → every route below |
| Namespace | `app_name = "projects"` → `reverse("projects:<name>")` |
| Pagination | every 7.2 register uses `crud_list`'s default `per_page=15`, exposed as **`PLANNING_PAGE_SIZE = 15`** in `apps/projects/tests/conftest.py` |

### Naming rule (mandatory — same as 7.1)

* test functions: `test_planning_*`
* module-level helpers (incl. constants): `_planning_*` / `_PLANNING_*`
* conftest fixtures: `planning_*` (root-conftest names excepted)
* 7.1's lane uses `projectinitiation_*` / `test_projectinitiation_*` — never collide with it, never
  import a 7.1 *fixture*; DO import 7.1's factory functions where they fit (see §7).

### conftest ownership

`apps/projects/tests/conftest.py` is owned by step 1 **alone**. Steps 2–5 must not edit it. Test
modules pull the factories in directly (peer pattern):

```python
from apps.projects.tests.conftest import (
    PLANNING_PAGE_SIZE,
    _planning_today, _planning_task, _planning_dependency,
    _planning_milestone, _planning_baseline, _planning_wbs_tree,
    _planning_fill_tasks,
)
```

---

## 1. Models — `apps/projects/models/ProjectPlanningScheduling/`

All four inherit `TenantNumbered` → `TenantOwned`: `tenant` (FK `core.Tenant`, related_name="+"),
`created_at`, `updated_at`, `number` minted in `save()` via `apps.core.utils.next_number`.
**Every factory/fill path must construct + `.save()` — never `bulk_create`** (numbering lives in
`save()`). Also exported from `apps.projects.models`: `q2`, `MAX_Q2`, `ZERO`.

Number prefixes are **per tenant, per model**: tenant A and tenant B both read `TSK-00001` with no
collision; a second `save()` never renumbers. `accounting.Project` / `crm.CrmProject` also mint
`PRJ-` — irrelevant here, but never assert a number is globally unique.

### 1.1 `ProjectTask` — `TSK-`, the WBS node + schedulable leaf in one row

* `Meta.ordering = ["project_id", "sequence", "id"]`; `unique_together = ("tenant", "number")`.
* Indexes (exact names): `tsk_tnt_project_idx` `(tenant, project)` · `tsk_tnt_status_idx`
  `(tenant, status)` · `tsk_tnt_prj_parent_idx` `(tenant, project, parent)` ·
  `tsk_tnt_ntype_idx` `(tenant, node_type)`.
* `__str__` → `f"{number} — {name}"` (em dash U+2014).
* FKs: `project` (CASCADE, `related_name="tasks"`), `parent` (self, SET_NULL, null+blank,
  `related_name="children"`), `owner` (AUTH_USER_MODEL, SET_NULL, null+blank,
  `related_name="planned_project_tasks"`), `created_by` (SET_NULL, null+blank, **editable=False**,
  `related_name="+"`).
* `node_type` CharField(12) default `work_package`; `status` CharField(12) default `planned`;
  `planned_start` / `planned_end` DateField null+blank; `effort_hours` DecimalField(8,2) null+blank
  MinValueValidator(0); `estimation_method` CharField(12) default `bottom_up`; `confidence`
  CharField(8) default `medium`; `sequence` PositiveSmallIntegerField default 0.
* **`duration_days` is a property** (never a column): both dates → `(end - start).days + 1`
  (inclusive); either missing → `None`.
* `clean()`: `planned_end < planned_start` → `ValidationError` **keyed `"planned_end"`**;
  `parent` set and `parent.project_id != project_id` → `ValidationError` **keyed `"parent"`**
  ("The parent task must belong to the same project as the task.") — the C1 cross-project guard.
  WBS codes (`1.2.3`) are view-computed, NEVER stored — assert no such column.
* CHOICES (assert exact values + labels):
  * `NODE_TYPE_CHOICES`: `deliverable` (Deliverable), `work_package` (Work Package)
  * `STATUS_CHOICES`: `planned` (Planned), `in_progress` (In Progress), `done` (Done),
    `cancelled` (Cancelled)
  * `ESTIMATION_CHOICES`: `bottom_up` (Bottom-Up), `top_down` (Top-Down), `analogous` (Analogous),
    `parametric` (Parametric)
  * `CONFIDENCE_CHOICES`: `high` (High), `medium` (Medium), `low` (Low)

### 1.2 `TaskDependency` — `DEP-`

* `Meta.ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number"),
  ("tenant", "predecessor", "successor")`. Index: `dep_tnt_succ_idx` `(tenant, successor)` ONLY
  (the unique covers the predecessor prefix — assert the exact one-element set).
* FKs: `predecessor` / `successor` → `projects.ProjectTask` CASCADE, related names
  `successor_links` (on predecessor) / `predecessor_links` (on successor). `link_type` CharField(16)
  default `finish_to_start`; `lag_days` SmallIntegerField default 0 (positive = lag, negative =
  lead); `note` TextField blank.
* `clean()` (errors are **non-field / `__all__`**):
  * `predecessor_id == successor_id` → `"A task cannot depend on itself."`
  * endpoints differ in `tenant_id` **or** `project_id` → `"Both endpoints of a dependency must
    belong to the same project."`
* CHOICES — `LINK_TYPE_CHOICES`: `finish_to_start` (Finish-to-Start), `start_to_start`
  (Start-to-Start), `finish_to_finish` (Finish-to-Finish), `start_to_finish` (Start-to-Finish).

### 1.3 `ProjectMilestone` — `MST-`

* `Meta.ordering = ["target_date", "id"]` — **date order, the deliberate exception** to
  newest-first (documented in Meta). `unique_together = ("tenant", "number")`.
* Indexes: `mst_tnt_project_idx` `(tenant, project)` · `mst_tnt_status_idx` `(tenant, status)`.
* FKs: `project` (CASCADE, `related_name="milestones"`), `anchor_task` (SET_NULL, null+blank,
  `related_name="milestones"`). `target_date` DateField required. `is_phase_gate` Boolean default
  False; `entry_criteria` / `exit_criteria` blank TextFields; `status` CharField(12) default
  `planned`; `actual_date` DateField null+blank **editable=False**.
* **`save()` stamps `actual_date` exactly once**: first time `status == "achieved"` and
  `actual_date` is None → `timezone.localdate()`; a re-save while still `achieved` keeps the
  ORIGINAL stamp; status leaving `achieved` CLEARS it (reopen); re-achieving re-stamps. (crm idiom.)
* `is_late` property: True iff `status in ("planned", "in_review")` and
  `target_date < timezone.localdate()`. **Test against `timezone.localdate()`** (L16) —
  `achieved`/`missed`/`cancelled` are False even with a past date.
* `clean()`: `anchor_task.project_id != project_id` → ValidationError keyed `"anchor_task"`.
* CHOICES — `STATUS_CHOICES`: `planned` (Planned), `in_review` (In Review), `achieved` (Achieved),
  `missed` (Missed), `cancelled` (Cancelled).

### 1.4 `ScheduleBaseline` — `BSL-`

* `Meta.ordering = ["-created_at", "-id"]`; `unique_together = ("tenant", "number")`.
  Index: `bsl_tnt_project_idx` `(tenant, project)`.
* FK `project` (CASCADE, `related_name="schedule_baselines"`). `baseline_type` CharField(8) default
  `baseline`; `is_active` Boolean default False (exactly-one-per-project enforced by the VERBS in
  `transaction.atomic()`, NOT by a constraint); `strategy_note` / `note` blank TextFields.
* **editable=False snapshot columns** (freeze-time evidence, never live aggregates):
  `frozen_on` (DateField), `planned_finish` (DateField), `task_count` (PositiveInteger),
  `total_effort_hours` (DecimalField(12,2)).
* `is_frozen` property → `baseline_type == "baseline"` (what_if rows are never frozen).
* `freeze_snapshot()`: ONE aggregate over `project.tasks` — `planned_finish = Max("planned_end")`
  (None when the plan is all-undated), `task_count = Count("pk")` (**undated tasks count**),
  `total_effort_hours = q2(Sum("effort_hours") or ZERO)`, `frozen_on = timezone.localdate()`.
* CHOICES — `BASELINE_TYPE_CHOICES`: `baseline` (Frozen Baseline), `what_if` (What-If Scenario).

### 1.5 `q2` (shared clamp)

`q2(v)` quantizes to 2dp AND clamps to `±MAX_Q2 = Decimal("9999999999.99")`; `q2(None) == 0.00`.
`freeze_snapshot` routes its effort sum through it — pin the clamp at the unit level, not by
building >10 000 tasks.

---

## 2. Forms — `apps/projects/forms/ProjectPlanningScheduling/`

Import through the package root: `from apps.projects.forms import TaskForm, TaskDependencyForm,
MilestoneForm, BaselineForm`. Every form is `class X(TenantUniqueMixin, TenantModelForm)` — mixin
FIRST. Constructor: `Form(data=None, *, tenant=...)`. All four are tenant-stamped-FK forms.

**Cross-tenant FK POSTs (verified shape):** `TenantModelForm` narrows the ModelChoiceField
queryset first, so a crafted foreign pk fails queryset validation — the message is Django's
`Select a valid choice. That choice is not one of the available choices.`, not
`_reject_foreign`'s wording (that is defence-in-depth for paths the scoping misses).
**Assert that the field HAS an error, never the wording.**

### 2.1 `TaskForm` — fields (exact 13)

`project parent node_type name description owner status planned_start planned_end effort_hours
estimation_method confidence sequence`. Required: `project`, `name` only.
`clean()` → `_reject_foreign(self, cleaned, ["project", "parent"])` — **`owner` is deliberately
NOT re-checked** (a User FK; users can be tenant-less, 7.1 precedent). Cycle guard: on EDIT
(`instance.pk` set), walking the candidate parent's ancestor chain over a one-query
`{pk: parent_id}` map must never reach `self` — else `add_error("parent", "A task cannot be nested
beneath its own descendant.")`.

### 2.2 `TaskDependencyForm` — fields (exact 5)

`predecessor successor link_type lag_days note`. `_reject_foreign` on BOTH endpoints.
The model `clean()` self-link/cross-project rules surface as **non-field** errors.

### 2.3 `MilestoneForm` — fields (exact 8)

`project anchor_task name description target_date is_phase_gate entry_criteria exit_criteria`.
**`status` is NOT a field — and neither is `actual_date`** (I2): status moves only through the
gated `mst_achieve`; leaving it on the form would let any member achieve a milestone through the
ungated edit view. `_reject_foreign` on `project` + `anchor_task`.

### 2.4 `BaselineForm` — fields (exact 5)

`project name baseline_type strategy_note note`. `is_active` and all four snapshot columns are
excluded (written by `freeze_snapshot()` / verbs only). `_reject_foreign` on `project`.
**Type lock (I1), edit-only:** when `self.instance.pk` and the POSTed `baseline_type` differs from
`instance.baseline_type` → `add_error("baseline_type", "A row's type is fixed — promote a what-if
scenario instead of editing it.")`. On CREATE both types are free.

---

## 3. URLs — all 24 names (`app_name = "projects"`)

`tsk_tree` is the only literal-before-pk route (`tasks/tree/` before `tasks/<int:pk>` — actually
`tasks/` `tasks/add/` then `tasks/<int:pk>/`; `tree` precedes them all).

| # | name | path | # | name | path |
|---|---|---|---|---|---|
| 1 | `tsk_list` | `/projects/tasks/` | 13 | `mst_create` | `/projects/milestones/add/` |
| 2 | `tsk_tree` | `/projects/tasks/tree/` | 14 | `mst_detail` | `/projects/milestones/<pk>/` |
| 3 | `tsk_create` | `/projects/tasks/add/` | 15 | `mst_edit` | `/projects/milestones/<pk>/edit/` |
| 4 | `tsk_detail` | `/projects/tasks/<pk>/` | 16 | `mst_delete` | `/projects/milestones/<pk>/delete/` |
| 5 | `tsk_edit` | `/projects/tasks/<pk>/edit/` | 17 | `mst_achieve` | `/projects/milestones/<pk>/achieve/` |
| 6 | `tsk_delete` | `/projects/tasks/<pk>/delete/` | 18 | `bsl_list` | `/projects/baselines/` |
| 7 | `dep_list` | `/projects/dependencies/` | 19 | `bsl_create` | `/projects/baselines/add/` |
| 8 | `dep_create` | `/projects/dependencies/add/` | 20 | `bsl_detail` | `/projects/baselines/<pk>/` |
| 9 | `dep_detail` | `/projects/dependencies/<pk>/` | 21 | `bsl_edit` | `/projects/baselines/<pk>/edit/` |
| 10 | `dep_edit` | `/projects/dependencies/<pk>/edit/` | 22 | `bsl_delete` | `/projects/baselines/<pk>/delete/` |
| 11 | `dep_delete` | `/projects/dependencies/<pk>/delete/` | 23 | `bsl_activate` | `/projects/baselines/<pk>/activate/` |
| 12 | `mst_list` | `/projects/milestones/` | 24 | `bsl_promote` | `/projects/baselines/<pk>/promote/` |

Flat list for reverse() checks (authoritative): `tsk_list, tsk_tree, tsk_create, tsk_detail,
tsk_edit, tsk_delete · dep_list, dep_create, dep_detail, dep_edit, dep_delete · mst_list,
mst_create, mst_detail, mst_edit, mst_delete, mst_achieve · bsl_list, bsl_create, bsl_detail,
bsl_edit, bsl_delete, bsl_activate, bsl_promote` — **24 names**.

---

## 4. Views — context keys, filters, tree

Base contract from `apps.core.crud`: list → `object_list` + `page_obj` + `q`; detail/edit object →
`obj`; form → `form` + `is_edit`.

| view | template | extra context keys |
|---|---|---|
| `tsk_list` | `projects/planning/task/list.html` | `status_choices` `node_type_choices` `estimation_method_choices` `projects` |
| `tsk_tree` | `projects/planning/task/tree.html` | `project` (selected or None) `projects` `roots` `tree_max_depth` (== 5) `critical_ids` (a SET of task pks) |
| `dep_list` | `projects/planning/taskdependency/list.html` | `link_type_choices` `projects` |
| `mst_list` | `projects/planning/milestone/list.html` | `status_choices` `projects` |
| `bsl_list` | `projects/planning/schedulebaseline/list.html` | `baseline_type_choices` `projects` |

Search fields: tsk `name number description` · dep `number note predecessor__name successor__name`
· mst `name number description` · bsl `name number strategy_note note`.
Int filters (`is_int=True`, junk/0/over-range skipped): tsk `project` · dep `project` (→
`predecessor__project_id`) · mst `project` · bsl `project`. Enum filters (junk value SKIPPED, never
matched — the register must not silently empty): tsk `status node_type estimation_method` · dep
`link_type` · mst `status` (+ `is_phase_gate`, a BooleanField with no choices — do not pin enum
semantics on it) · bsl `baseline_type`.

### `tsk_tree` decoration (all in Python, never stored)

`_decorate_wbs(project)` returns `(roots, critical_ids)`. Each node instance gains:
`wbs_code` (`"1"`, `"1.1"`, `"1.2.3"` — position-derived), `is_critical` (bool),
`kids` (list of DECORATED child instances — the template include walks `node.kids`, never
`node.children.all`), and on deliverables `rollup_start` / `rollup_end` / `rollup_effort_hours` /
`rollup_count` (post-order subtree rollup; own values on a work package). Tree body markers
(`_tree_node.html`): WBS code in a `badge badge-slate`, critical nodes get
`<span class="badge badge-red">Critical</span>`, deliverables render
`{{ rollup_count }} package…`. Project picker: `?project=<own pk>` honored;
`?project=<foreign/junk/absent>` falls back to the tenant's first project (ordered by name);
a tenant-less user gets `project=None`, empty `projects`, empty `roots` — 200, never a 500.

`critical_path_ids` (`apps/projects/views/_helpers.py`): ONE chain of `work_package` tasks — Kahn
topological longest-path pass over `TaskDependency` edges, duration floored at 1 day, ties by
`(sequence, id)`, cycles skipped (defensively capped). Returns a set of pks; empty for a plan with
no work packages. With a 2-link FS chain plus an isolated task, the chain's two pks are exactly the
critical set.

---

## 5. Verbs and guards

| verb | decorators | behaviour / refusal |
|---|---|---|
| `tsk_delete` `dep_delete` `mst_delete` | `login_required` + `require_POST` | straight `crud_delete` → redirect to the model's list |
| `bsl_delete` | `login_required` + `require_POST` | **refuses `is_frozen` rows**: `messages.error` + 302 to `bsl_detail`, row survives; `what_if` deletes |
| `mst_achieve` | `login_required` + **`tenant_admin_required`** + `require_POST` | `status == "achieved"` → info "already achieved" (NO re-stamp); `status == "cancelled"` → error "cannot be achieved"; else `status="achieved"` saved via `update_fields`, `save()` stamps `actual_date`, audit action **`achieve`** with `changes["from"]` = real prior status |
| `bsl_activate` | `login_required` + **`tenant_admin_required`** + `require_POST` | only `baseline` rows (what_if → error); already active → info; else atomically flips itself on and every sibling off, audit action **`activate`** |
| `bsl_promote` | `login_required` + **`tenant_admin_required`** + `require_POST` | only `what_if` rows (baseline → info "already a frozen baseline"); else becomes `baseline`, `freeze_snapshot()`, `is_active=True`, siblings off — audit action **`promote`** |
| `bsl_edit` | `login_required` | GET/POST on a frozen row → `messages.error` + 302 to `bsl_detail` BEFORE any form; `what_if` edits normally |

All four create views (`tsk_create`, `dep_create`, `mst_create`, `bsl_create`) guard
`request.tenant is None` on the FIRST line → `redirect("dashboard:home")` with an error message.
Audit `action` values used by 7.2: `create` `update` `delete` `achieve` `activate` `promote` —
every one ≤ 10 chars (`AuditLog.action` is varchar(10)).

**I4 template guard** (`templates/projects/planning/*/detail.html`): the verb buttons are wrapped
in `{% if request.user.is_superuser or request.user.is_tenant_admin %}`. Pin the exact strings:
milestone detail — `Mark Achieved` (also gated on status planned/in_review/missed); baseline
detail — `Promote to Baseline` (what_if rows) / `Activate` (inactive baseline rows). A member's
detail page must NOT contain them; the admin's must. Edit links stay for everyone.

---

## 6. The four test files — exact function lists

Every file starts `pytestmark = pytest.mark.django_db`. HTTP actor fixtures: root `client_a`
(tenant A ADMIN — there is deliberately NO `planning_client`; 7.1 defines none either),
`client_b`, `member_client` (tenant A member), plus the `planning_*` clients from §7.

### 6.1 `test_planning_models.py` — 16 tests

1. `test_planning_numbering_is_per_tenant_per_model` — one row of each model per tenant: tenant A
   reads `TSK-00001` / `DEP-00001` / `MST-00001` / `BSL-00001`, tenant B independently reads the
   SAME four numbers (no cross-tenant collision); a second `save()` never renumbers.
2. `test_planning_choice_machine_values_are_pinned` — exact (value, label) tuples of all seven
   CHOICES constants (tsk ×4, dep ×1, mst ×1, bsl ×1) AND the field defaults (`work_package`,
   `planned`, `bottom_up`, `medium`, `finish_to_start`, `lag_days=0`, `sequence=0`,
   `baseline`, `is_active=False`).
3. `test_planning_task_duration_days_is_inclusive_or_none` — both dates → `(end-start).days + 1`
   (same-day → 1); start-only / end-only / neither → `None`; `duration_days` is NOT a column.
4. `test_planning_task_clean_rejects_planned_end_before_start` — `full_clean()` raises
   ValidationError keyed `"planned_end"`; equal dates pass.
5. `test_planning_task_clean_rejects_parent_from_another_project` (C1) — same-tenant sibling
   project's task as parent → ValidationError keyed `"parent"`; same-project parent control passes.
6. `test_planning_dependency_clean_rejects_self_link` — predecessor == successor → non-field
   ValidationError "A task cannot depend on itself."
7. `test_planning_dependency_clean_rejects_mismatched_endpoints` — cross-project (same tenant) AND
   cross-tenant endpoints both raise the same-project message; same-project control passes.
8. `test_planning_dependency_pair_is_unique_per_tenant` — duplicate
   `(tenant, predecessor, successor)` → IntegrityError on save; a different pair and the reversed
   pair save fine.
9. `test_planning_milestone_actual_date_stamps_exactly_once` — planned→achieved stamps
   `localdate`; re-save while achieved keeps the ORIGINAL stamp; reopen to planned CLEARS it;
   re-achieving re-stamps fresh.
10. `test_planning_milestone_is_late_follows_status_and_date` — planned/in_review + past target →
    True; achieved/missed/cancelled with the same past date → False; future target → False
    (basis `timezone.localdate()`, L16).
11. `test_planning_milestone_clean_rejects_anchor_task_from_another_project` — ValidationError
    keyed `"anchor_task"`; same-project anchor passes.
12. `test_planning_baseline_is_frozen_and_freeze_snapshot_aggregates_the_plan` — `is_frozen` True
    for baseline / False for what_if; snapshot with 2 dated + 1 undated task → `task_count == 3`,
    `planned_finish == max(planned_end)`, `total_effort_hours == q2(sum)`, `frozen_on ==
    localdate`; all-undated plan → `planned_finish None`, effort `0.00`.
13. `test_planning_q2_clamps_to_the_column_ceiling` — `q2(None) == 0.00`, 2dp quantize, values
    beyond `±MAX_Q2` clamp to `±MAX_Q2` (the clamp `freeze_snapshot` relies on).
14. `test_planning_index_names_are_the_as_built_set` — exact index-name SETS: tsk
    `{tsk_tnt_project_idx, tsk_tnt_status_idx, tsk_tnt_prj_parent_idx, tsk_tnt_ntype_idx}` ·
    dep `{dep_tnt_succ_idx}` · mst `{mst_tnt_project_idx, mst_tnt_status_idx}` ·
    bsl `{bsl_tnt_project_idx}`.
15. `test_planning_ordering_and_unique_together_are_pinned` — Meta.ordering exact lists for all
    four (mst `["target_date", "id"]` proven behaviorally: rows saved out of date order come back
    date-ordered); `unique_together` tuples pinned.
16. `test_planning_non_editable_stamps_carry_no_form_path` — editable=False sets: tsk
    `{number, created_by}` · dep `{number}` · mst `{number, actual_date}` · bsl
    `{number, frozen_on, planned_finish, task_count, total_effort_hours}` (model-layer half of L20).

### 6.2 `test_planning_forms.py` — 15 tests

Assert a field HAS an error for cross-tenant cases — never the message wording.

1. `test_planning_task_form_valid_path_and_field_list` — Meta.fields is the exact 13-list;
   valid data → `is_valid()`, cleaned values stick; only `project` + `name` required.
2. `test_planning_task_form_owner_is_deliberately_not_rejected` — `owner` = a tenant-None
   (superuser-shape) user → form still valid: `owner` must never be tenant-compared.
3. `test_planning_task_form_rejects_cross_tenant_project` — `project` = tenant B project →
   error on `"project"`.
4. `test_planning_task_form_rejects_parent_from_another_project` — same-tenant parent from a
   sibling project → error on `"parent"` (model clean surfaces on the field).
5. `test_planning_task_form_rejects_parent_from_another_tenant` — tenant B parent pk → error on
   `"parent"` (queryset scoping fires first).
6. `test_planning_task_form_rejects_a_descendant_as_parent` — edit form (instance = existing task),
   data `parent` = its own child → `"parent"` error "cannot be nested beneath its own descendant"
   (cycle guard).
7. `test_planning_task_form_rejects_planned_end_before_start` — inverted window → error on
   `"planned_end"` at the form layer too.
8. `test_planning_dependency_form_valid_path_and_defaults` — valid; exact 5-field list;
   `link_type` defaults `finish_to_start`, `lag_days` 0.
9. `test_planning_dependency_form_rejects_cross_tenant_endpoints` — foreign successor → error on
   `"successor"`; foreign predecessor → error on `"predecessor"`.
10. `test_planning_dependency_form_rejects_self_link` — predecessor == successor → NON_FIELD_ERRORS
    (`__all__`), via the model clean.
11. `test_planning_milestone_form_excludes_status_and_actual_date` (I2 pin) — exact 8-field list;
    `"status"` and `"actual_date"` (and `number`/`tenant`) are NOT fields.
12. `test_planning_milestone_form_rejects_cross_tenant_project_and_anchor` — foreign `project` →
    error on `"project"`; `anchor_task` from a sibling project → error on `"anchor_task"`.
13. `test_planning_baseline_form_fields_and_exclusions` — exact 5-field list;
    `is_active`/`frozen_on`/`planned_finish`/`task_count`/`total_effort_hours` absent; both types
    valid on create.
14. `test_planning_baseline_form_type_lock_on_edit_only` (I1) — bound to a saved row with a
    CHANGED `baseline_type` → `"baseline_type"` error; same-type edit passes; CREATE with either
    type passes (the lock is edit-only).
15. `test_planning_baseline_form_rejects_cross_tenant_project` — foreign project → error on
    `"project"`.

### 6.3 `test_planning_views.py` — 21 tests

Every request runs as `client_a` (tenant A admin) unless stated. Assert template + context keys +
state deltas, redirect targets via `reverse("projects:…")`.

1. `test_planning_task_register_renders_context_keys_and_content` — GET `tsk_list` → 200, template
   `projects/planning/task/list.html`, context has `object_list/page_obj/q/status_choices/
   node_type_choices/estimation_method_choices/projects`, `page_obj.paginator.per_page ==
   PLANNING_PAGE_SIZE`; body contains a fixture task's number and name.
2. `test_planning_task_register_search_and_filters` — `?q=` hits name/number/description;
   `?status=done`, `?node_type=deliverable`, `?estimation_method=parametric`, `?project=<pk>` each
   narrow; a no-match q → empty register (200).
3. `test_planning_task_register_skips_junk_params` — `?status=nope&node_type=abc&
   estimation_method=zzz&project=abc` (and `project=0`, `project=999999999999999999999`) → 200
   with ALL rows still listed — filter skipped, register never silently emptied (L11).
4. `test_planning_dependency_register_renders_context_keys_and_filters` — dep_list 200 + keys
   (`link_type_choices`, `projects`); `?q=` by predecessor name; `?link_type=start_to_start`
   narrows; junk `link_type` skipped.
5. `test_planning_milestone_register_renders_context_keys_and_filters` — mst_list 200 + keys;
   `?status=` / `?project=` narrow; junk enum skipped; rows come back `target_date`-ordered
   (Meta ordering survives crud_list).
6. `test_planning_baseline_register_renders_context_keys_and_filters` — bsl_list 200 + keys
   (`baseline_type_choices`, `projects`); `?baseline_type=what_if` narrows; junk skipped.
7. `test_planning_wbs_tree_renders_codes_rollups_and_structure` — with `_planning_wbs_tree`:
   GET `tsk_tree?project=<pk>` → 200; context `tree_max_depth == 5`, `critical_ids` is a set,
   `roots == [d1, d2]`; `d1.wbs_code == "1"`, kids' codes `"1.1"` / `"1.2"`; deliverable rollups
   (start = min child start, end = max child end, effort = q2 child sum, `rollup_count == 2`);
   body contains the WBS codes; `kids` hold DECORATED instances (each kid has `wbs_code`).
8. `test_planning_wbs_tree_marks_the_critical_chain` — FS chain wp11 → wp12 (dated, 3+2 days) vs
   isolated wp21/wp22: `critical_ids == {wp11.pk, wp12.pk}`; `is_critical` True on the chain /
   False off it; body contains `badge badge-red` "Critical" ONLY on chain nodes.
9. `test_planning_wbs_tree_project_picker_honored_and_junk_ignored` — `?project=<project_a>` →
   context project is that one; `?project=<project_b pk>` → falls back to a TENANT A project
   (never B's); `?project=abc` / no param → tenant's first project by name; a project-less tenant
   → `project is None`, empty `roots`, 200.
10. `test_planning_task_crud_round_trip` — POST `tsk_create` (valid) → 302 to the new
    `tsk_detail`; GET detail 200 shows number + name (create GET context `is_edit is False`);
    POST `tsk_edit` → 302, name changed (edit GET `is_edit is True` + `obj`); POST `tsk_delete` →
    302 to `tsk_list`; GET detail → 404.
11. `test_planning_dependency_crud_round_trip` — same shape through dep_create/detail/edit/delete
    → 404 at the end.
12. `test_planning_milestone_crud_round_trip` — same shape through mst_*.
13. `test_planning_baseline_crud_round_trip_what_if` — POST `bsl_create` type `what_if` → 302 to
    detail; `frozen_on is None`, `is_active is False`, snapshot columns all None; edit (same type)
    → 302; delete → 302 to bsl_list; detail → 404.
14. `test_planning_baseline_create_as_baseline_snapshots_and_takes_over` — with an ACTIVE baseline
    already on the project: POST `bsl_create` type `baseline` → new row has `frozen_on ==
    localdate`, `task_count`/`planned_finish`/`total_effort_hours` snapshotted from the project's
    tasks, `is_active is True`; the OLD active row is flipped False (exactly one active).
15. `test_planning_task_detail_lists_children_and_links` — task with a child, a predecessor dep and
    a successor dep → detail 200; context `child_tasks` / `predecessor_links` / `successor_links`
    each contain the expected rows.
16. `test_planning_milestone_achieve_stamps_once_and_refuses_replays` — POST `mst_achieve` on a
    planned milestone → 302 to detail, `status == "achieved"`, `actual_date == localdate`; force
    `actual_date` to a past date and POST again → 302 info, status AND the old stamp unchanged.
17. `test_planning_milestone_achieve_refuses_cancelled` — POST on a cancelled milestone → 302
    error, status still `cancelled`, `actual_date` None.
18. `test_planning_baseline_activate_flips_exactly_one` — two `baseline` rows, one active: POST
    `bsl_activate` on the inactive → 302, it active, the other off; repeat POST → info no-op;
    POST `bsl_activate` on a `what_if` → refused, nothing changed.
19. `test_planning_baseline_promote_freezes_and_takes_over` — `what_if` + active baseline: POST
    `bsl_promote` → `baseline_type == "baseline"`, snapshot columns + `frozen_on` set,
    `is_active True`, old active off; POST again → info "already a frozen baseline".
20. `test_planning_frozen_baseline_refuses_edit_and_delete` — GET `bsl_edit` on a frozen row → 302
    to `bsl_detail` (never a form), row unchanged; POST `bsl_delete` → 302 to detail, row STILL
    EXISTS; the `what_if` control: GET edit → 200, POST delete → 302 to list and gone.
21. `test_planning_registers_paginate_to_a_second_page` — `PLANNING_PAGE_SIZE + 1` tasks → page 1
    has 15, `?page=2` has 1; `?page=abc` → page 1; `?page=99` → last page (L9).

### 6.4 `test_planning_security.py` — 12 tests

Fixtures from §7: `planning_*_b` rows are the cross-tenant targets; `planning_member_b` is the
tenant-B member; `planning_tenantless_client` the superuser shape.

1. `test_planning_cross_tenant_detail_edit_delete_are_404` — `client_a` GET detail + GET edit +
   POST delete on `planning_task_b`, `planning_dependency_b`, `planning_milestone_b`,
   `planning_baseline_b` → **404 each** (never 403/500), B's rows unchanged.
2. `test_planning_cross_tenant_verbs_are_404` — `client_a` POST `mst_achieve` / `bsl_activate` /
   `bsl_promote` on the tenant-B pks → 404, rows unchanged.
3. `test_planning_admin_gated_verbs_403_for_member_and_succeed_for_admin` — `member_client` POSTs
   `mst_achieve`, `bsl_activate`, `bsl_promote` on OWN-tenant rows → **403** with ZERO field
   deltas; `client_a` replays each → 302 and the state moves (the 403 was the ROLE, not the row).
4. `test_planning_verbs_are_post_only` — `client_a` GET on all seven POST-only routes (4 deletes +
   3 verbs) → **405**.
5. `test_planning_crafted_cross_tenant_post_creates_nothing` — `client_a` POSTs each create form
   carrying tenant-B FKs (tsk: `project` AND `parent`; dep: `successor`; mst: `project` +
   `anchor_task`; bsl: `project`) → 200 form redisplay, count unchanged; each paired with a
   same-tenant control POST that DOES create (so a malformed payload can't fake a pass).
6. `test_planning_member_cannot_move_milestone_status_through_edit` — `member_client` POST
   `mst_edit` (login-only, so it runs) with valid data AND a smuggled `status=achieved` → 302;
   status still `planned`, `actual_date` None (I2 at the route: status is not a form field).
7. `test_planning_tenantless_user_sees_empty_registers_and_cannot_create` —
   `planning_tenantless_client`: all five registers → 200 with EMPTY `object_list` and empty
   `projects` dropdown (tree: `project is None`, empty roots); all four creates → 302 to
   `dashboard:home`, no form rendered, nothing written.
8. `test_planning_anonymous_is_redirected_to_login` — `planning_anon_client`: five registers +
   four create GETs → 302 to the login page; verb POSTs against REAL tenant-A rows → 302 to login
   BEFORE any mutation (rows unchanged).
9. `test_planning_member_detail_pages_hide_the_admin_verbs` (I4) — `member_client` GET
   `mst_detail` (planned milestone) → 200 WITHOUT the string `Mark Achieved`; `client_a` GET same
   → contains it. `bsl_detail`: member's page contains neither `Promote to Baseline` nor
   `Activate`; admin's what_if page shows `Promote to Baseline`, admin's inactive-baseline page
   shows `Activate`.
10. `test_planning_no_template_comment_markers_leak` — as admin AND member: the five registers,
    the tree and the three detail pages render 200 with NEITHER `{#` NOR `{% comment` in the body.
11. `test_planning_cross_tenant_rows_never_enter_a_register_or_filter` — rows exist in both
    tenants: every register lists only A's rows (B's number/name absent); a VALID-but-foreign
    `?project=<B pk>` on tsk/mst/bsl lists → 200 EMPTY (int filter applies — unlike junk, a foreign
    pk is a legitimate narrowing that matches nothing); searching B's unique name → empty.
12. `test_planning_verbs_write_audit_rows_with_short_actions` — after achieve/activate/promote and
    a create + delete: `AuditLog` rows exist with actions `achieve` / `activate` / `promote` /
    `create` / `delete` (each ≤ 10 chars), and the achieve row's `changes["from"]` is the row's
    REAL prior status.

---

## 7. Fixtures — seeded-vs-factory strategy

**Tests use the FACTORIES, never the seeder.** `apps/projects/management/commands/seed_projects.py`
builds the demo workspace (11-node WBS, dependency network, frozen baseline …); no test may call
it or depend on its rows — every test builds exactly what it asserts on. Also never `bulk_create`
(numbering), never `datetime.date.today()` (L16 — `_planning_today()` = `timezone.localdate()`).

### From the ROOT conftest — reuse, never redefine

`tenant_a` · `tenant_b` · `admin_user` (tenant A admin) · `member_user` (tenant A member) ·
`admin_b` · `client_a` (tenant A ADMIN client — **the 7.2 admin client; there is no
`planning_client`**, 7.1 defines none either) · `client_b` · `member_client`.

### Reused 7.1 factories (import the FUNCTIONS, not fixtures)

`_projectinitiation_project(tenant, **overrides)` builds every `Project` a 7.2 test needs — pass
`status="active"`, `charter_status="approved"` for the planning host projects. Nothing else from
7.1 is required.

### New in `apps/projects/tests/conftest.py` (step 1 owns these)

Constant `PLANNING_PAGE_SIZE = 15`. Helpers:

| helper | signature | builds |
|---|---|---|
| `_planning_today` | `()` | `timezone.localdate()` — the only date basis in the lane |
| `_planning_task` | `(tenant, project, parent=None, **overrides)` | saved `ProjectTask`: `node_type="work_package"`, distinct `name` ("Work package NN" via per-tenant count), `planned_start=today`, `planned_end=today+4` (duration 5), `effort_hours=40.00`, defaults otherwise; `parent=None` → root |
| `_planning_dependency` | `(tenant, predecessor, successor, **overrides)` | saved `TaskDependency`: `finish_to_start`, `lag_days=0` |
| `_planning_milestone` | `(tenant, project, **overrides)` | saved `ProjectMilestone`: distinct name, `target_date=today+30`, `status="planned"` |
| `_planning_baseline` | `(tenant, project, **overrides)` | saved `ScheduleBaseline`: distinct name, **`baseline_type="what_if"`** (NOT frozen), `is_active=False` |
| `_planning_wbs_tree` | `(tenant, project)` | the 2-deliverable × 2-work-package tree: d1 (seq 1) ← wp11 (seq 1, today→today+2, 24.00h) + wp12 (seq 2, today+3→today+4, 16.00h); d2 (seq 2) ← wp21 (seq 1, today→today, 8.00h) + wp22 (seq 2, today+1→today+2, 8.00h). Returns a dict `{d1, d2, wp11, wp12, wp21, wp22}` — wp11→wp12 is the critical chain (5 days) |
| `_planning_fill_tasks` | `(tenant, project, count, **overrides)` | `count` distinct-named root work packages (pagination / search fills) |

Fixtures: `planning_project_a` / `planning_project_b` (ACTIVE projects via
`_projectinitiation_project`, status `active`, charter `approved`) · `planning_task_a` /
`planning_task_b` (default work packages — the round-trip + cross-tenant targets) ·
`planning_dependency_a` / `planning_dependency_b` (each builds its own two endpoints) ·
`planning_milestone_a` (planned) / `planning_milestone_b` · `planning_baseline_whatif_a` ·
`planning_baseline_frozen_a` (`baseline` type, `is_active=False` — the activate happy-path row) ·
`planning_baseline_active_a` (`baseline` type, `is_active=True` — frozen + edit/delete-refused) ·
`planning_baseline_b` · `planning_member_b` (non-admin tenant-B user, the admin_b-shaped member) ·
`planning_tenantless_user` / `planning_tenantless_client` · `planning_anon_client` ·
`planning_csrf_client` (`Client(enforce_csrf_checks=True)` as `admin_user`) ·
`planning_wbs_tree_a` (the tree on `planning_project_a`).

---

## 8. Reminders that have bitten this repo

* **L16** — `USE_TZ=True`: derive every date from `timezone.localdate()` / `timezone.now()`.
* **L11** — junk enum + junk/0/over-range int FK filters must 200 with the filter SKIPPED; a valid
  foreign pk filters (→ empty register), it does not skip.
* **L9** — page 2 and past-the-end with `PLANNING_PAGE_SIZE + 1` rows.
* **L35** — absent prerequisite = refusal: `bsl_activate` on a what_if, `bsl_promote` on a baseline.
* **L47/L49** — closing run is unfiltered with migrations ON.
* 403-vs-404 on the gated verbs depends on the ACTOR: the role check runs before
  `get_object_or_404`, so IDOR-404s must use `client_a` (admin) and member tests must never claim
  a 404.
* A parallel session owns `CostManagement`/`ResourceManagement` — 7.2 tests import nothing from
  them and never touch their files.

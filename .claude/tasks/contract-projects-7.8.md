# Build contract — Projects 7.8 Task & Work Management (`projects`)

> Frozen 2026-09-12 against the live tree at commit `7c0e8588` (build plan) / `536c2230` (research).
> This file is the single source of truth for the entity-by-entity build: every name below is
> resolved against the real code, not aspirational. Anything not pinned here is not authorized.
>
> Scope (frozen by the plan, Rulings 1–5): **2 new models** (`TaskChecklistItem` [TCL-],
> `TaskBlock` [TBK-]) + an **in-place execution-field extension of `ProjectTask`** + **3 computed
> pages** (`task_board`, `gantt_timeline`, `task_priority`). No third table, no stored aggregate,
> no money column, no write-back to `CostControlAccount`.

## 0. Verified ground truth (read, not assumed)

| Fact | Verified at |
|---|---|
| `ProjectTask` [TSK-] fields/Meta/`duration_days` | `apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py:22` — docstring `:8-10` IS the in-place-extension contract; `STATUS_CHOICES` = `planned/in_progress/done/cancelled`; `owner` rn `planned_project_tasks`; 4 existing indexes (`tsk_tnt_project_idx`, `tsk_tnt_status_idx`, `tsk_tnt_prj_parent_idx`, `tsk_tnt_ntype_idx`) untouched |
| `TaskDependency` [DEP-] | `apps/projects/models/ProjectPlanningScheduling/TaskDependencies.py:17` — rn `successor_links` (on predecessor) / `predecessor_links` (on successor); `LINK_TYPE_CHOICES` = `finish_to_start/start_to_start/finish_to_finish/start_to_finish`; same-project `clean()` guard |
| `TenantNumbered` | `apps/projects/models/_base.py:54` — `number CharField(20, editable=False)` minted in `save()` via `apps.core.utils.next_number` with 5-retry collision loop; `unique_together ("tenant","number")` declared per model; `TenantOwned` gives `tenant` (rn `+`, db_index) + `created_at`/`updated_at`; `ZERO`, `q2`, `MinValueValidator`/`MaxValueValidator` exported by `_base` |
| Prefixes | `TCL`/`TBK` free repo-wide; `TSK` (7.2), `TASK` (crm 1.8), `DEP`, `RAL`, `RTE`, `SCR` (7.7) taken. **Do not shorten TCL to TASK.** |
| Related names | `assigned_project_tasks`, `checked_task_checklist_items`, `task_blocks_raised`, `task_blocks_cleared`, `checklist_items` (on ProjectTask), `blocks` (on ProjectTask) — all verified free (grep over `apps/` empty) |
| `critical_path_ids(project)` | `apps/projects/views/_helpers.py:107` — iterative Kahn, returns `set[int]` of work-package pks. **Reuse; add NOTHING to `_helpers.py`** |
| `owners(tenant)` / `projects(tenant)` | `apps/projects/views/_helpers.py:79` / `:43` — dropdown builders, `.none()` for tenant-less user |
| Migration leaf | `0010_alter_scopeitem_status` is the disk leaf → **7.8's migration is `0011_…`, assigned at generation, never reserved; announce-then-generate** |
| URL first segments | 34 existing literals (incl. `""`): `project-requests/ projects/ stakeholders/ kickoffs/ tasks/ dependencies/ milestones/ baselines/ resource-profiles/ allocations/ time-entries/ capacity-demand/ budgetlines/ revisions/ controlaccounts/ expenses/ risks/ responses/ issues/ escalations/ risk-analysis/ risk-monitoring/ quality-plans/ quality-reviews/ inspections/ defects/ quality-improvement/ quality-acceptance/ requirements/ scope-items/ scope-changes/ scope-verifications/ scope-matrix/`. The five new segments below are disjoint from all of them. **Re-check `apps/projects/urls/__init__.py` at Integrate** in case the 7.7 peer added a segment |
| Badge classes | `static/css/theme.css:286-291`: `badge-green badge-red badge-amber badge-info badge-muted badge-slate` (colour-named only, L33) |
| Peer territory (DO NOT TOUCH) | `.claude/tasks/test-contract-projects-7.7.md`, `apps/projects/tests/conftest.py`, `apps/projects/tests/test_zz_scope_smoke_throwaway.py`, and any `apps/projects/tests/test_scope_*.py` — the live 7.7 test session owns them |

## 1. House invariants that bind every 7.8 artifact

- **L16** — every date comparison / stamp uses `timezone.localdate()` (never `date.today()`); datetime stamps use `timezone.now()`.
- **L27** — every 7.8 verb is `@login_required` member-level; NO `tenant_admin_required` gate anywhere this pass.
- **L11/L35** — every GET int through `as_db_int` (`apps.core.crud`); every enum allow-listed against its CHOICES; derived properties are pre-scoped in the view, never faked as DB lookups.
- **L7/L8** — every context key in §5 is pinned; a name not in the template's context renders blank at 200.
- **L10** — no nullable FK inside a `|default:` filter argument (`assignee`, `done_by`, `blocked_by`, `unblocked_by`, `owner` guard with `{% if %}…{% else %}—{% endif %}`).
- **L2** — multi-line template notes use `{% comment %} … {% endcomment %}`, never multi-line `{# #}`.
- **L29** — no money column, no `accounting.Currency`/`core.Party` FK anywhere in 7.8.
- **Audit** — `core.AuditLog.action` is varchar(10): 7.8 writes only `create` / `update` / `delete`; the verb goes in `changes={"verb": …, "from": …, "to": …}`. Every mutating verb captures `previous` BEFORE mutating.
- **Verbs are POST-only** (`@require_POST`) except `tsk_execute` (GET+POST). Every queryset is `filter(tenant=request.tenant)`, never `.all()`.
- **Imports absolute** in all four layers; FKs declared by string (`"projects.ProjectTask"`, `settings.AUTH_USER_MODEL`); no cross-app model import at module level.
- **Layer files**: `apps/projects/{models,forms,views,urls}/TaskWorkManagement/<Entity>.py` — same file name in all four layers; **sub-package `__init__.py` files stay EMPTY**; re-exports only in the four top-level `__init__.py` (Integrate step, §7).

## 2. Models

### 2.1 `ProjectTask` — in-place execution extension (Ruling 1; edit `models/ProjectPlanningScheduling/ProjectTasks.py`)

NOTHING existing is altered or reordered. Append AFTER `confidence` (before `sequence`? No — **append after the existing field block, before `class Meta`**; the file's field order becomes: existing fields …, `confidence`, then the new block below, then the existing `sequence`/`created_by`… — in practice insert the new fields immediately after `confidence` so the execution block reads together).

New CHOICES class attributes (alongside the existing four):

```python
PRIORITY_CHOICES = [
    ("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical"),
]
MOSCOW_CHOICES = [
    ("must_have", "Must Have"), ("should_have", "Should Have"),
    ("could_have", "Could Have"), ("wont_have", "Won't Have"),
]
```
Exact machine values (lowercase): `low`, `medium`, `high`, `critical` (`max_length=8`); `must_have`, `should_have`, `could_have`, `wont_have` (`max_length=12`).

New fields, exact declarations:

```python
assignee = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    related_name="assigned_project_tasks",
    help_text="The doer. The accountable manager stays owner; team bookings live on "
              "ResourceAllocation (7.3 staffing).")
priority = models.CharField(
    max_length=8, choices=PRIORITY_CHOICES, default="medium")
moscow = models.CharField(
    max_length=12, choices=MOSCOW_CHOICES, null=True, blank=True,
    help_text="MoSCoW classification. No default on purpose — unclassified is a state, "
              "not a value.")
is_urgent = models.BooleanField(default=False)
is_important = models.BooleanField(default=False)
percent_complete = models.DecimalField(
    max_digits=5, decimal_places=2, default=Decimal("0"),
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    help_text="Task-grain attestation (0–100). A deliverable's rollup is computed on read, "
              "never stored; the attested CostControlAccount.percent_complete (7.4) is "
              "superseded by this figure, not written by it.")
actual_start = models.DateField(
    null=True, blank=True, editable=False,
    help_text="VERB-WRITTEN by tsk_start only — the 7.4/7.6 verb-written-stamp idiom.")
actual_end = models.DateField(
    null=True, blank=True, editable=False,
    help_text="VERB-WRITTEN by tsk_complete only (which also stamps percent_complete=100).")
```
`Decimal("0")` (the `_base` `ZERO` idiom). `actual_start`/`actual_end` are form-unreachable via `editable=False`. **No other execution stamps exist on the task.**

`Meta.indexes` — APPEND exactly two (the existing four untouched):

```python
models.Index(fields=["tenant", "assignee"], name="tsk_tnt_assignee_idx"),
models.Index(fields=["tenant", "priority"], name="tsk_tnt_priority_idx"),
```

Derived properties (appended after `duration_days`; **never columns**; all safe on unset FKs/dates):

| Property | Exact formula / None-guard |
|---|---|
| `is_overdue` | `False` when `planned_end` unset; else `self.planned_end < timezone.localdate() and self.status in ("planned", "in_progress")` (L16 clock) |
| `is_dependency_blocked` | Over `self.predecessor_links` (rn from `TaskDependency.successor`): `True` when ANY link has `link_type == "finish_to_start"` and `predecessor.status not in ("done", "cancelled")`, OR `link_type == "start_to_start"` and `predecessor.status == "planned"`. **FF/SF links never block.** Empty links → `False`. Derived, never stored — Ruling 3 |
| `is_manually_blocked` | `self.blocks.filter(unblocked_at__isnull=True).exists()` (the `tbk_tnt_unblocked_idx` lookup) |
| `is_blocked` | `self.is_dependency_blocked or self.is_manually_blocked` |
| `checklist_progress` | `total = self.checklist_items.count()`; `None` when `total == 0`; else `int(round(self.checklist_items.filter(is_done=True).count() / total * 100))` — an int 0–100 percentage, a computed input to the progress lens, never a column |
| `eisenhower_quadrant` | `is_urgent and is_important` → `"do_first"`; `is_important` only → `"schedule"`; `is_urgent` only → `"delegate"`; neither → `"eliminate"` (exact lowercase strings) |

Form implications (surgical edit of **7.2's** `forms/ProjectPlanningScheduling/ProjectTasks.py` `TaskForm`):
`Meta.fields` gains `assignee, priority, moscow, is_urgent, is_important, percent_complete` — appended after `"sequence"`; **`status` STAYS on that form** (it is 7.2's planning write); `actual_start`/`actual_end` unreachable (`editable=False`). `assignee` joins `owner` in the NOT-`_reject_foreign` set (users can be tenant-less — the `TaskForm` docstring precedent); `_reject_foreign` list stays `["project", "parent"]`.

### 2.2 Model 1 — `TaskChecklistItem` [TCL-] (`models/TaskWorkManagement/TaskChecklistItems.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "TCL"`. Docstring must carry: realizes bullet 1's checklists; rows give one-time done-stamps; `is_done`/`done_by`/`done_at` are **VERB-WRITTEN only via `tcl_check`** (stamped exactly once per direction); `label`/`sequence` stay editable on done items (a tick item is a working row, not frozen evidence — only the STAMPS are verb-only); no money column.

| Field | Exact declaration |
|---|---|
| `task` | `models.ForeignKey("projects.ProjectTask", on_delete=models.CASCADE, related_name="checklist_items")` |
| `label` | `models.CharField(max_length=255)` |
| `sequence` | `models.PositiveSmallIntegerField(default=0)` — order within the task's checklist |
| `is_done` | `models.BooleanField(default=False)` — verb-written, NOT on the form |
| `done_by` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="checked_task_checklist_items")` |
| `done_at` | `models.DateTimeField(null=True, blank=True, editable=False)` |
| `created_by` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")` |

Meta/behaviour:
- `ordering = ["task_id", "sequence", "id"]` (a checklist reads in sequence order)
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "task"], name="tcl_tnt_task_idx"), models.Index(fields=["tenant", "is_done"], name="tcl_tnt_done_idx")]`
- `__str__` = `f"{self.number} — {self.label}"`
- No `clean()` (no cross-model guard needed; `task` is `_reject_foreign`-checked on the form)

### 2.3 Model 2 — `TaskBlock` [TBK-] (`models/TaskWorkManagement/TaskBlocks.py`)

Base `TenantNumbered`, `NUMBER_PREFIX = "TBK"`. **Evidence-row docstring ruling (verbatim constraint): rows are minted ONLY by `tsk_block` and closed ONLY by `tsk_unblock` — no `tbk_create`/`tbk_edit`/`tbk_delete` routes ship at all; no `TaskBlock` ModelForm exists.** Active blocks are frozen while open (the exit is `tsk_unblock` with a `resolution_note`); once unblocked the row is frozen evidence entirely (the 7.4/7.6 frozen-row idiom). `is_blocked` is DERIVED (Ruling 3) — nothing blocking is stored on the task.

| Field | Exact declaration |
|---|---|
| `task` | `models.ForeignKey("projects.ProjectTask", on_delete=models.CASCADE, related_name="blocks")` |
| `reason` | `models.TextField()` — required (why it is blocked) |
| `unblock_criteria` | `models.TextField()` — required (what must be true to unblock — bullet 5's exact ask) |
| `resolution_note` | `models.TextField(blank=True)` — how the criteria were met, written by `tsk_unblock` |
| `blocked_by` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="task_blocks_raised")` |
| `blocked_at` | `models.DateTimeField(null=True, blank=True, editable=False)` — stamped by `tsk_block` |
| `unblocked_by` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="task_blocks_cleared")` |
| `unblocked_at` | `models.DateTimeField(null=True, blank=True, editable=False)` — **written exactly once** by `tsk_unblock` |
| `created_by` | `models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="+")` |

Meta/behaviour:
- `ordering = ["-created_at", "-id"]`
- `unique_together = ("tenant", "number")`
- `indexes = [models.Index(fields=["tenant", "task"], name="tbk_tnt_task_idx"), models.Index(fields=["tenant", "unblocked_at"], name="tbk_tnt_unblocked_idx")]` (the second serves the active-block lookup `unblocked_at__isnull=True`)
- `@property is_active` → `self.unblocked_at is None`
- `__str__` = `f"{self.number} — {self.task}"`
- No `clean()`

### 2.4 Migration

`0010_alter_scopeitem_status` is the disk leaf → **expect `0011_…`, assigned by `makemigrations` at generation, NEVER reserved**. Announce-then-generate: `python manage.py makemigrations projects --dry-run` first; read every model it names — anything beyond `TaskChecklistItem` / `TaskBlock` / `ProjectTask` means **STOP and report**. One migration carries all three (the extension shares it, build order: ProjectTask extension → TaskChecklistItem → TaskBlock).

## 3. Forms (`forms/TaskWorkManagement/`)

File `forms/TaskWorkManagement/ProjectTasks.py`:

- **`TaskExecutionForm(TenantUniqueMixin, TenantModelForm)`** — `Meta.model = ProjectTask`; `Meta.fields = ["assignee", "priority", "moscow", "is_urgent", "is_important", "percent_complete"]` (IN ORDER; plan fields stay 7.2's — the form cannot touch them). `assignee`'s choices come from the tenant's users via `TenantModelForm` auto-scoping (the `TaskForm.owner` precedent — `User` carries `tenant`); `assignee` is **NOT** `_reject_foreign`-checked, so the form defines **no `clean()` override** (nothing to re-check). Docstring notes the exemption.
- **`TaskBlockForm(forms.Form)`** — plain form (NOT a ModelForm — the evidence-row ruling), bound by `tsk_block`: `reason = forms.CharField(required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))`; `unblock_criteria = forms.CharField(required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))` (the `DefectResolutionForm` widget idiom).
- **`TaskUnblockForm(forms.Form)`** — plain form, bound by `tsk_unblock`: `resolution_note = forms.CharField(required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}))`.

File `forms/TaskWorkManagement/TaskChecklistItems.py`:

- **`TaskChecklistItemForm(TenantUniqueMixin, TenantModelForm)`** — `Meta.model = TaskChecklistItem`; `Meta.fields = ["task", "label", "sequence"]` (in order — the exclusion list is: `tenant`, `number`, `is_done`, `done_by`, `done_at`, `created_by`; `is_done` is verb-written). `clean()` runs `_reject_foreign(self, cleaned, ["task"])` only. No `TaskBlock` form and no `GanttWindowForm` in the forms package (the Gantt window form is private to its view, §5.4).

`tenant=` scoping: every ModelForm instantiation passes `tenant=request.tenant` (both create and edit paths — the `qdf_create`/`crud_edit` shape); `TenantUniqueMixin` is mixed in FIRST on both ModelForms (house idiom).

## 4. URLs (`urls/TaskWorkManagement/` — six modules)

Full route table (paths are under the app mount `/projects/`; `app_name = "projects"`). View function name == url name everywhere (house convention).

| Path literal | URL name | View function | Methods | View module |
|---|---|---|---|---|
| `tasks/bulk-update/` | `tsk_bulk_update` | `tsk_bulk_update` | POST | `urls/TaskWorkManagement/ProjectTasks.py` |
| `tasks/<int:pk>/execute/` | `tsk_execute` | `tsk_execute` | GET, POST | same |
| `tasks/<int:pk>/start/` | `tsk_start` | `tsk_start` | POST | same |
| `tasks/<int:pk>/complete/` | `tsk_complete` | `tsk_complete` | POST | same |
| `tasks/<int:pk>/block/` | `tsk_block` | `tsk_block` | POST | same |
| `tasks/<int:pk>/unblock/` | `tsk_unblock` | `tsk_unblock` | POST | same |
| `checklist-items/` | `tcl_list` | `tcl_list` | GET | `urls/TaskWorkManagement/TaskChecklistItems.py` |
| `checklist-items/add/` | `tcl_create` | `tcl_create` | GET, POST | same |
| `checklist-items/<int:pk>/` | `tcl_detail` | `tcl_detail` | GET | same |
| `checklist-items/<int:pk>/edit/` | `tcl_edit` | `tcl_edit` | GET, POST | same |
| `checklist-items/<int:pk>/delete/` | `tcl_delete` | `tcl_delete` | POST | same |
| `checklist-items/<int:pk>/check/` | `tcl_check` | `tcl_check` | POST | same |
| `blocks/` | `tbk_list` | `tbk_list` | GET | `urls/TaskWorkManagement/TaskBlocks.py` |
| `blocks/<int:pk>/` | `tbk_detail` | `tbk_detail` | GET | same |
| `task-board/` | `task_board` | `task_board` | GET | `urls/TaskWorkManagement/TaskBoard.py` |
| `gantt-timeline/` | `gantt_timeline` | `gantt_timeline` | GET | `urls/TaskWorkManagement/GanttTimeline.py` |
| `task-priority/` | `task_priority` | `task_priority` | GET | `urls/TaskWorkManagement/TaskPriority.py` |

Ordering constraints (first-match-wins):
- Within each new module, literal routes precede `<int:pk>/` routes; in `ProjectTasks.py` `tasks/bulk-update/` is listed first.
- The six task verbs deliberately **REUSE 7.2's existing `tasks/` first segment** with disjoint leaf literals (`execute|start|complete|block|unblock|bulk-update` cannot collide with 7.2's `tree/`, `add/`, `edit/`, `delete/` literals nor with `<int:pk>/`, an int converter) — no new `tasks/` segment is declared, so nothing can shadow 7.2.
- Five NEW first segments — `checklist-items/`, `blocks/`, `task-board/`, `gantt-timeline/`, `task-priority/` — disjoint from all 34 existing first segments (§0 table) and from each other. No route uses a converter in its first component.
- Integrate appends to `urls/__init__.py`: six imports (`from .TaskWorkManagement.ProjectTasks import urlpatterns as _tw_tasks`, `…TaskChecklistItems import … as _tw_checklistitems`, `…TaskBlocks import … as _tw_blocks`, `…TaskBoard import … as _tw_board`, `…GanttTimeline import … as _tw_gantt`, `…TaskPriority import … as _tw_priority`) and the concat block appended AFTER the `+ _sr_matrix` line, with a `# 7.8 Task & Work Management — first segments (…)` disjointness comment matching the 7.2–7.7 blocks.

## 5. Views (`views/TaskWorkManagement/`) — decorators, templates, CONTEXT KEYS

Common: every view `@login_required`; every queryset `filter(tenant=request.tenant)`; absolute imports; `owners`/`projects` reused from `views/_helpers.py` (nothing added to `_helpers`); `critical_path_ids` from `views/_helpers.py`.

### 5.1 `views/TaskWorkManagement/ProjectTasks.py` — execution edit + five verbs + bulk

- **`tsk_execute(request, pk)`** — `@login_required`. Delegates to `crud_edit(request, model=ProjectTask, pk=pk, form_class=TaskExecutionForm, template="projects/taskwork/task_execution.html", success_url="projects:tsk_detail")` (tenant-scoped fetch inside `crud_edit`; POST audit `update` with `crud._changed(form)`). Context: `form` (`TaskExecutionForm`), `obj` (`ProjectTask`), `is_edit=True` — the crud form contract. The POST can never touch plan fields (the form's field list is the guard).
- **`tsk_start(request, pk)`** — `@login_required` `@require_POST` (exact order). Tenant-scoped `get_object_or_404`. Refused with `messages.error` + redirect to `projects:tsk_detail` unless `obj.status == "planned"` **and** `not obj.is_blocked`. On success: `previous = obj.status`; `obj.status = "in_progress"`; `obj.actual_start = timezone.localdate()`; `save(update_fields=["status", "actual_start", "updated_at"])`; `write_audit_log(request.user, obj, "update", changes={"verb": "start", "from": previous, "to": obj.status})`; `messages.success`; redirect `projects:tsk_detail`.
- **`tsk_complete(request, pk)`** — `@login_required` `@require_POST`. Refused unless `obj.status == "in_progress"`; **hard-refused while `obj.is_blocked`** — the refusal message names the source (the unfinished FS/SS predecessor numbers when `is_dependency_blocked`, the active `TaskBlock.number` when `is_manually_blocked` — the ClickUp default). On success: `previous = obj.status`; `obj.status = "done"`; `obj.actual_end = timezone.localdate()`; `obj.percent_complete = Decimal("100")`; `save(update_fields=["status", "actual_end", "percent_complete", "updated_at"])`; audit `update` `changes={"verb": "complete", "from": previous, "to": obj.status}`; redirect `projects:tsk_detail`.
- **`tsk_block(request, pk)`** — `@login_required` `@require_POST`. Refused while an active block already exists (`obj.blocks.filter(unblocked_at__isnull=True).exists()` — one open blocker at a time, so `is_manually_blocked` always names THE row). Binds `TaskBlockForm(request.POST)`; invalid → `messages.error` + redirect `projects:tsk_detail`. Valid → `TaskBlock.objects.create(tenant=request.tenant, task=obj, reason=…, unblock_criteria=…, blocked_by=request.user, blocked_at=timezone.now(), created_by=request.user)`; audit `create` on the TBK row with `changes={"verb": "block", "task": obj.number}`; `messages.success` naming `block.number`; redirect `projects:tsk_detail`.
- **`tsk_unblock(request, pk)`** — `@login_required` `@require_POST`. Fetches the task's active block; refused with `messages.info` when none is active (unblock-twice). Binds `TaskUnblockForm(request.POST)`; `previous` = the block's active state captured BEFORE mutating; stamps `unblocked_by=request.user`, `unblocked_at=timezone.now()`, `resolution_note=form.cleaned_data["resolution_note"]` exactly once; `save(update_fields=["unblocked_by", "unblocked_at", "resolution_note", "updated_at"])`; audit `update` `changes={"verb": "unblock", "from": "active", "to": "resolved"}`; redirect `projects:tsk_detail`.
- **`tsk_bulk_update(request)`** — `@login_required` `@require_POST` (the `rte_approve_week` bulk idiom, but **per-row audit entries**). POST params (pinned): `task_ids` = `request.POST.getlist("task_ids")` (each through `as_db_int`, junk ids skipped); optional `status` (allow-listed against `ProjectTask.STATUS_CHOICES`), `assignee` (`as_db_int`), `priority` (allow-listed against `PRIORITY_CHOICES`); at least one field must be present or the request is refused with `messages.error`. Per-id loop with the **per-row transition gating** of the single verbs (start/complete refusals honored row-by-row — a refused row is skipped with its own `messages.error`, never aborts the batch) and a per-row audit entry per applied field change; redirect `projects:tsk_list`.

### 5.2 `views/TaskWorkManagement/TaskChecklistItems.py`

- **`tcl_list(request)`** — `@login_required`. `qs = TaskChecklistItem.objects.filter(tenant=request.tenant).select_related("task", "task__project", "done_by")` → `crud_list(request, qs, "projects/taskwork/checklistitem/list.html", search_fields=["number", "label"], filters=[("task", "task_id", True), ("is_done", "is_done", False)], extra_context={…})`. Context: `object_list` (page of `TaskChecklistItem`), `page_obj`, `q` (str — the crud contract) + `tasks` = `ProjectTask.objects.filter(tenant=request.tenant).select_related("project").order_by("number")` (the task filter dropdown).
- **`tcl_create(request)`** — `@login_required`; FIRST LINE tenant-None guard → `messages.error` + `redirect("dashboard:home")` (the `tsk_create`/`qdf_create` shape). Parses `?task=<pk>` preselect through `as_db_int`. POST: `TaskChecklistItemForm(request.POST, tenant=request.tenant)`; on valid: `obj = form.save(commit=False)`; `obj.tenant = request.tenant`; `obj.created_by = request.user`; `save()` (number minted by `TenantNumbered.save`); audit `create`; `messages.success` naming `obj.number`; redirect `projects:tcl_detail`. Context: `form`, `is_edit=False`.
- **`tcl_detail(request, pk)`** — `@login_required`. `crud_detail(request, model=TaskChecklistItem, pk=pk, template="projects/taskwork/checklistitem/detail.html", select_related=("task", "task__project", "done_by", "created_by"))`. Context: `obj` (the parent-task link renders from `obj.task`).
- **`tcl_edit(request, pk)`** — `@login_required`. `crud_edit(request, model=TaskChecklistItem, pk=pk, form_class=TaskChecklistItemForm, template="projects/taskwork/checklistitem/form.html", success_url="projects:tcl_list")`. Context: `form`, `obj`, `is_edit=True`. `label`/`sequence` stay editable on done items (only the stamps are verb-only).
- **`tcl_delete(request, pk)`** — `@login_required` `@require_POST`. `crud_delete(request, model=TaskChecklistItem, pk=pk, success_url="projects:tcl_list")`.
- **`tcl_check(request, pk)`** — `@login_required` `@require_POST`. `previous = obj.is_done` captured BEFORE mutating (one writer per direction — the un-tick goes through the SAME verb + audit). Open → done: `done_by=request.user`, `done_at=timezone.now()`, `is_done=True`. Done → open: all three cleared to `None`/`False`. `save(update_fields=["is_done", "done_by", "done_at", "updated_at"])`; audit `update` `changes={"verb": "tcl_check", "from": previous, "to": obj.is_done}`; redirect `projects:tcl_detail` (documented trade-off: the task-detail panel's tick button lands on the item detail — no `?next=` plumbing this pass).

### 5.3 `views/TaskWorkManagement/TaskBlocks.py` — the evidence-row ruling: `tbk_list`/`tbk_detail` ONLY

- **`tbk_list(request)`** — `@login_required`. `qs = TaskBlock.objects.filter(tenant=request.tenant).select_related("task", "task__project", "blocked_by", "unblocked_by")`; the derived lens `?active=1` → `qs = qs.filter(Q(unblocked_at__isnull=True))` **pre-scoped before `crud_list`** (the `qdf_list ?overdue=1` idiom — `is_active` is a property, not a column); junk `?active=` values are ignored (only the exact string `"1"` activates). `crud_list(request, qs, "projects/taskwork/block/list.html", search_fields=["number", "reason", "unblock_criteria", "resolution_note"], filters=[("task", "task_id", True)], extra_context={…})`. Context: `object_list`, `page_obj`, `q` + `tasks` (same queryset shape as `tcl_list`'s). **No Actions delete column — evidence.**
- **`tbk_detail(request, pk)`** — `@login_required`. `crud_detail(request, model=TaskBlock, pk=pk, template="projects/taskwork/block/detail.html", select_related=("task", "task__project", "blocked_by", "unblocked_by", "created_by"), extra_context={"block_form": TaskBlockForm(), "unblock_form": TaskUnblockForm()})`. Context: `obj`, `block_form`, `unblock_form` — the action panels POST to the TASK routes (`projects:tsk_block` / `projects:tsk_unblock` with `obj.task_id`); the template shows the unblock panel only when `obj.is_active`.

### 5.4 Computed pages — GET-only, no model (the `capacity_demand`/`risk_analysis`/`quality_improvement` precedent)

`?project=` and `?assignee=` are parsed through `as_db_int` and resolved against the tenant-scoped querysets (`Project.objects.filter(tenant=tenant, pk=…).first()` — an out-of-tenant id degrades to `None`, never a 500). **No other query param is parsed by any of the three pages** (no `?status=`, `?priority=`, `?moscow=`, `?q=`, `?weeks=` — do not invent them).

**`task_board(request)`** — `views/TaskWorkManagement/TaskBoard.py`, template `projects/taskwork/task_board.html`. Module constants pinned:
- `WIP_LIMITS: dict = {}` — documented **EMPTY** dict keyed by status value; the 7.19 hook (Ruling 4). Counts render now; `over_limit` is computed only when an entry exists (always `False` today). NOT passed into context — it reaches the template through each column's `over_limit`.
- `_PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}` — declared locally (re-declared verbatim in `TaskPriority.py`; the `_helpers` single-consumer rule — a third consumer moves it to `_helpers`).

Context contract (exact keys):

| Key | Type / content |
|---|---|
| `projects` | tenant `Project` queryset — `projects(tenant)` |
| `project` | `Project` or `None` (from `?project=`; `None` → all-tenant board) |
| `assignees` | `owners(tenant)` — the assignee filter dropdown |
| `assignee` | `User` or `None` (from `?assignee=` — the "my tasks" lens) |
| `columns` | list of dicts, ONE per `ProjectTask.STATUS_CHOICES` value in declared order (`planned`, `in_progress`, `done`, `cancelled`): `{"value": str, "label": str, "tasks": list[ProjectTask], "count": int, "over_limit": bool}`. Within-column order: priority rank (`critical→high→medium→low`), then `planned_start` (nulls LAST), then `-id` (Wrike's priority-default sort). Tasks are materialized ONCE (one queryset + Python bucketing — the `crmproject_board` idiom); deliverable nodes render as summary cards (rollup figures, NO verb buttons) |
| `ready_queue` | list[`ProjectTask`]: `status="planned"` AND ≥1 predecessor link (`predecessor_links` non-empty) AND no unfinished predecessor AND no active `TaskBlock`; ordered `planned_start` (nulls last), then `id` |
| `total_count` | int — count over the scoped queryset |
| `blocked_count` | int — tasks with `is_blocked`, counted in Python over the materialized board list |
| `overdue_count` | int — tasks with `is_overdue`, counted in Python likewise |

**`gantt_timeline(request)`** — `views/TaskWorkManagement/GanttTimeline.py`, template `projects/taskwork/gantt_timeline.html`. Module-level private window form (NOT in the forms package):

```python
class _GanttWindowForm(forms.Form):
    start = forms.DateField(required=False)
    end = forms.DateField(required=False)
```
Window resolution (pinned, never a 500 — junk `?start=`/`?end=` fall through the form to the default): defaults = the task-date union padded 7 days each side; undated → `today..today+30`; clamps: `end <= start` → `end = start + 30d`; span > 366d → `end = start + 366d`. Module constants: `_WINDOW_PAD_DAYS = 7`, `_DEFAULT_SPAN_DAYS = 30`, `_MAX_SPAN_DAYS = 366`. `days` is INCLUSIVE (`(end - start).days + 1` — the `duration_days` idiom). Bars are CSS (left/width = offset/duration over the window); **no chart library** (7.16's).

Context contract:

| Key | Type / content |
|---|---|
| `projects` | tenant `Project` queryset |
| `project` | `Project` or `None` (from `?project=`; `None` → the picker empty state) |
| `window` | `{"start": date, "end": date, "days": int}` — or `None` when `project is None` |
| `bars` | list of dicts, one per WBS node in TREE order: `{"task": ProjectTask, "depth": int (0 = root), "left_pct": float|None, "width_pct": float|None, "progress_pct": float|None, "is_critical": bool, "is_deliverable": bool}`. `left_pct`/`width_pct` are `None` for undated nodes (template renders the label row without a bar). Work packages: `progress_pct = percent_complete`. Deliverables: bar window = min/max descendant planned dates; `progress_pct` = the effort-weighted rollup over descendant work packages — `Σ(percent_complete × effort_hours or 0) / Σ(effort_hours or 0)`, falling back to the unweighted descendant mean when `Σeffort = 0`, `None` with no descendants — computed on read, never stored (Ruling 5) |
| `critical_ids` | `set[int]` — `critical_path_ids(project)`; the template highlights via `task.pk in critical_ids` |
| `dep_rows` | list of dicts `{"dependency": TaskDependency, "predecessor": ProjectTask, "successor": ProjectTask, "link_type_label": str (dep.get_link_type_display()), "lag_days": int}` — the links table beside the chart (arrows are JS → deferred) |
| `conflicts` | list[`TaskDependency`] — FS links only, where `successor.planned_start` and `predecessor.planned_end` are both set and `successor.planned_start < predecessor.planned_end` |
| `today` | `date` — `timezone.localdate()` (the today-marker line) |

When `project is None`: `bars = []`, `dep_rows = []`, `conflicts = []`, `critical_ids = set()`, `window = None` (the `tsk_tree` empty precedent). The page carries the computed-lens caveat (planning-grade, no auto-rescheduling) as a `{% comment %}`.

**`task_priority(request)`** — `views/TaskWorkManagement/TaskPriority.py`, template `projects/taskwork/task_priority.html`. Declares its own verbatim `_PRIORITY_RANK` (see above).

Context contract:

| Key | Type / content |
|---|---|
| `projects` | tenant `Project` queryset |
| `project` | `Project` or `None` (same guards as the board) |
| `assignees` | `owners(tenant)` |
| `assignee` | `User` or `None` |
| `moscow_groups` | list of dicts in declared order (`must_have`, `should_have`, `could_have`, `wont_have`) **plus a trailing `unclassified` group** (`moscow` null — a state, not a default): `{"value": str|None (None for unclassified), "label": str ("Unclassified" for the trailing group), "tasks": list[ProjectTask], "count": int}`; tasks ordered priority-rank → `planned_start` (nulls last) |
| `quadrants` | list of dicts in fixed order `do_first`/`schedule`/`delegate`/`eliminate`, bucketed on read from `is_urgent`/`is_important`: `{"key": str, "label": str, "tasks": list[ProjectTask], "count": int, "badge": str}` — badge classes pinned: `do_first` → `"badge-red"`, `schedule` → `"badge-info"`, `delegate` → `"badge-amber"`, `eliminate` → `"badge-slate"` (colour-named, L33; verified in `theme.css:286-291`) |
| `work_queue` | list[`ProjectTask`] **capped at 25** (`_WORK_QUEUE_CAP = 25`): live tasks (`status in ("planned", "in_progress")`) that are `is_overdue` OR `is_blocked` OR `priority in ("high", "critical")`; ordered overdue-first → priority-rank → `planned_start` (nulls last) |
| `counts` | dict with EXACTLY these keys, over the scoped queryset: `{"overdue": int, "blocked": int, "unassigned": int, "in_progress": int}` (`blocked`/`overdue` counted in Python over the materialized list; `unassigned` = `assignee` null among live tasks; `in_progress` = `status == "in_progress"`) |

## 6. Templates (`templates/projects/taskwork/`)

Every page `{% extends "base.html" %}` and fills `{% block title %}` + `{% block content %}` (the house two-block shape); lists include `{% include "partials/pagination.html" %}` (L9-safe, `has_previous`/`has_next` guarded) and a filter bar reflecting `request.GET` with FK `<select>` comparisons via `|stringformat:"d"`. Colour-named badges only; every badge ternary ends `{% else %}{{ obj.get_<field>_display }}{% endif %}`. No nullable FK inside `|default:`. Empty states on every list/board region.

| Path | Rendered by | Shape |
|---|---|---|
| `taskwork/checklistitem/list.html` | `tcl_list` | filter bar (`q`, `task`, `is_done`), Actions column with delete POST + `confirm()` + `{% csrf_token %}` and a check/uncheck POST to `tcl_check` |
| `taskwork/checklistitem/detail.html` | `tcl_detail` | `obj` fields, stamp row (`done_by`/`done_at` — `—` when unset), parent-task link, check verb button |
| `taskwork/checklistitem/form.html` | `tcl_create` / `tcl_edit` | the `partials/form_field.html`-style form render, `is_edit` heading |
| `taskwork/block/list.html` | `tbk_list` | filter bar (`q`, `task`, `active`), NO delete column (evidence), active badge from `is_active` |
| `taskwork/block/detail.html` | `tbk_detail` | `obj` evidence fields, `block_form` (POST → `projects:tsk_block` on `obj.task_id`), `unblock_form` (POST → `projects:tsk_unblock`, shown only when `obj.is_active`) |
| `taskwork/task_board.html` | `task_board` | the four status columns with counts + WIP/over-limit badges + card lists (priority/MoSCoW/assignee badges, per-card `tsk_start`/`tsk_complete` POST buttons — deliverable rows as summary cards WITHOUT verbs), the ready queue, project + assignee filter bar |
| `taskwork/gantt_timeline.html` | `gantt_timeline` | CSS bars (left/width from `left_pct`/`width_pct`, progress shading from `progress_pct`), critical-path highlight (`task.pk in critical_ids` — compare pks, `|stringformat:"d"` idiom for FK selects), today line from `today`, `dep_rows` links table, `conflicts` flags, project picker; computed-lens caveat in `{% comment %}` |
| `taskwork/task_priority.html` | `task_priority` | MoSCoW groups (incl. the `unclassified` group), the Eisenhower 2×2 grid (badge from `quadrants[].badge`), the work queue (cap 25), the `counts` stat row, project + assignee filter bar |
| `taskwork/task_execution.html` | `tsk_execute` | the slim execution form (`form`), `obj` header context, `is_edit` |
| `taskwork/_task_checklist_panel.html` | include | partial (no extends): iterates `obj.checklist_items.all` + `obj.checklist_progress`; per-item POST to `tcl_check` |
| `taskwork/_task_blocks_panel.html` | include | partial: iterates `obj.blocks.all` + `obj.is_blocked`/`is_manually_blocked` badges; embeds `block_form` / `unblock_form` POSTing to the task routes |
| `taskwork/_task_dependencies_panel.html` | include | partial: iterates `obj.predecessor_links.all` / `obj.successor_links.all` with per-link blocking verdict (`is_dependency_blocked` naming) |

Entity SUB-FOLDERS exist only for the two entities (`checklistitem/`, `block/` — 7.8 has two entities, so CLAUDE.md rule 3's single-entity collapse does NOT apply); the three computed pages, the execution form and the three partials stand FLAT at the `taskwork/` root (rule 6). `templates/projects/taskwork/` is new (verified absent).

**Surgical edits of 7.2's `templates/projects/planning/task/detail.html`** (Integrate): the three partials are `{% include %}`d into the task detail page, so the lenses live on task detail. Because `_task_blocks_panel.html` embeds the two verb forms, **7.2's `views/ProjectPlanningScheduling/ProjectTasks.py::tsk_detail` gains two context keys** (a 7.8-owned surgical edit — context additions only, no behavior change): `block_form` = `TaskBlockForm()`, `unblock_form` = `TaskUnblockForm()`. The checklist/dependency panels read `obj.checklist_items.all` / `obj.blocks.all` / `obj.predecessor_links.all` / `obj.successor_links.all` directly — no further context keys.

## 7. Integration surfaces (Integrate step — single writer, surgical `Edit` with re-read anchors, path-limited commits)

1. **Four top-level `__init__.py`** — append a `# --- 7.8 Task & Work Management ---…` block AFTER the existing `# --- 7.7` block in each. A missing re-export is a runtime `ImportError`.
   - `models/__init__.py`: `from .TaskWorkManagement.TaskChecklistItems import TaskChecklistItem` + `from .TaskWorkManagement.TaskBlocks import TaskBlock` (both `# noqa: F401`).
   - `forms/__init__.py`: `from .TaskWorkManagement.ProjectTasks import TaskExecutionForm, TaskBlockForm, TaskUnblockForm` + `from .TaskWorkManagement.TaskChecklistItems import TaskChecklistItemForm` (grouped per file-of-origin, the 7.7 shape).
   - `views/__init__.py`: `from .TaskWorkManagement.ProjectTasks import (tsk_block, tsk_bulk_update, tsk_complete, tsk_execute, tsk_start, tsk_unblock)` + `from .TaskWorkManagement.TaskChecklistItems import (tcl_check, tcl_create, tcl_delete, tcl_detail, tcl_edit, tcl_list)` + `from .TaskWorkManagement.TaskBlocks import tbk_detail, tbk_list` + `from .TaskWorkManagement.TaskBoard import task_board` + `from .TaskWorkManagement.GanttTimeline import gantt_timeline` + `from .TaskWorkManagement.TaskPriority import task_priority` (alphabetized inside parens, the 7.7 shape).
   - `urls/__init__.py`: the six imports + concat block per §4.
2. **`admin.py`** — append after the 7.7 block:
   - `@admin.register(TaskChecklistItem)` `class TaskChecklistItemAdmin`: `list_display = ("number", "task", "label", "sequence", "is_done", "done_by", "done_at", "tenant")`; `list_filter = ("is_done",)`; `list_select_related = ("tenant", "task", "task__project", "done_by")`; `search_fields = ("number", "label")`; `readonly_fields = ("is_done", "done_by", "done_at", "created_by", "created_at", "updated_at")` (verb-state columns frozen).
   - `@admin.register(TaskBlock)` `class TaskBlockAdmin`: `list_display = ("number", "task", "blocked_by", "blocked_at", "unblocked_by", "unblocked_at", "tenant")`; `list_select_related = ("tenant", "task", "task__project", "blocked_by", "unblocked_by")`; `search_fields = ("number", "reason", "unblock_criteria", "resolution_note")`; the whole row is evidence → `readonly_fields = ("reason", "unblock_criteria", "resolution_note", "blocked_by", "blocked_at", "unblocked_by", "unblocked_at", "created_by", "created_at", "updated_at")`.
   - **Surgical edit of the existing `ProjectTaskAdmin`**: `list_display` += `"assignee", "priority", "percent_complete"`; `list_select_related` += `"assignee"`.
3. **`seed_projects.py`** — `_taskwork` block with its OWN guard (`TaskChecklistItem.objects.filter(tenant=tenant).exists()`), called after `self._scope(tenant, now)` in `_seed_tenant`. Creates: execution state on the existing seeded WBS work packages (assignees, every `priority`, every `moscow` value + unclassified rows, all four Eisenhower quadrants, `percent_complete` 0/50/100, `in_progress`/`done` rows carrying `actual_start`/`actual_end`, one `cancelled`); a dependency-blocked task (unfinished FS predecessor off the existing `_planning` network); a manually blocked task with an OPEN `TaskBlock` (reason + `unblock_criteria` + stamps); an unblocked `TaskBlock` trail (both stamp pairs + `resolution_note`); checklists with mixed ticks (stamped `done_by`/`done_at` + open items) on several tasks + one empty checklist — enough rows for page 2. `--flush`: add `TaskChecklistItem.objects.all().delete()` + `TaskBlock.objects.all().delete()` at the TOP of the children-first list (both FK `ProjectTask`), update the `add_arguments` help text, extend the imports with both models.
4. **`apps/core/navigation.py`** — one new `LIVE_LINKS["7.8"]` immediately after the `"7.7"` block (~`:1832`), keys VERBATIM (character-for-character against NavERP.md 7.8):
   `"Task Creation & Assignment": "projects:tsk_list"` (bullet 1 → 7.2's task register — 7.8 extends that row in place, Ruling 1); `"Priority & Urgency Scoring": "projects:task_priority"`; `"Kanban & Scrum Boards": "projects:task_board"`; `"Gantt Charts & Timeline Views": "projects:gantt_timeline"`; `"Task Dependencies & Blocking": "projects:dependencies"` (bullet 5's links half → 7.2's dependency register, Ruling 3; 7.8 owns the blocking STATE on top, reached from the task-detail panels); extra live leaf `"Task Checklist Register": "projects:tcl_list"`. Justification comments record both deliberate register mappings. `_safe_reverse` supports `?query=` (confirmed).
5. **`templates/projects/overview.html` + `views/ProjectInitiation/Overview.py`** — 7.8 quick-link rows in the "Start here" table (board, Gantt, priority lens, checklist register) + stat cards with NEW context keys `in_progress_task_count`, `blocked_task_count`, `overdue_task_count` (blocked/overdue computed in Python over a materialized live-task list; `in_progress` a DB count — the `open_defect_count` shape); extend the intro layer sentence with the 7.8 execution layer.
6. **Peer boundary** — none of the above touches `apps/projects/tests/conftest.py`, `test_zz_scope_smoke_throwaway.py`, any `test_scope_*.py`, or `.claude/tasks/test-contract-projects-7.7.md`.

## 8. Names reserved for later steps (not built this pass)

Tests land only after the 7.7 test wave: `test_taskwork_{models,forms,views,security}.py`, fixture block `taskwork_*`, helpers `_taskwork_*` (no collision with `test_initiation_*`/`test_planning_*`/`test_resource_*`/`test_cost_*`/`test_risk_*`/`test_quality_*`/`test_scope_*`). Smoke script `temp/smoke_78.py` (the `smoke_73.py` sibling). Review file `.claude/tasks/review-projects-7.8.md`. Skill section in `.claude/skills/projects/SKILL.md`; README row → **7 of 19**.

Deferred by ruling (do NOT build): multi-assignee M2M (P2), WIP-limit values + over-limit hard stop (7.19), sprints (7.13), auto-rescheduling (7.17/7.16), computed priority scores (7.19), recurring/copy verbs (7.17), block/unblock notifications (7.17), Gantt baseline overlay (7.2's `ScheduleBaseline`), drag-drop JS / arrows, CCA write-back (Ruling 5).

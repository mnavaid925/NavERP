# Build Contract — Projects 7.13 Agile & Scrum Management (`projects`)

> Frozen 2026-09-18 against the live tree at commit `045a0b02`.
> This contract is the single source of truth for the entity-by-entity build.
> Every variable name, field name, URL name, context key, and badge class is pinned here.

---

## 0. Scope & Capability Coverage

Five NavERP.md 7.13 capability bullets mapped to 5 models + 1 in-place model extension + 4 computed pages:

| Bullet | What 7.13 Owns | Artifacts |
|---|---|---|
| **Sprint Planning & Backlog Grooming** | Sprint container, story point estimation, velocity tracking, backlog ranking | `Sprint` [SPT-], `ProjectTask` extensions, `sprint_backlog` workbench |
| **Sprint Execution & Daily Standups** | Active sprint execution, burndown chart, standup notes, team impediments | `SprintExecution.py` (burndown math + standup notes) + `SprintImpediment` [IMP-] |
| **Release & Version Planning** | Release trains, version tags, feature flags, version roadmap | `ProjectRelease` [REL-], `ReleaseRoadmap.py` |
| **Epic & Feature Management** | Hierarchical story organization, cross-sprint features, progress rollups | `ProjectEpic` [EPC-] with derived progress rollups |
| **Retrospectives & Team Health** | Retrospective boards, action items, team sentiment surveys | `SprintRetrospective` [RET-], `VelocityReport.py` |

### Non-Goals & Invariants
- **No second task table (L29/Ruling 1)**: User stories and backlog items ARE `ProjectTask` [TSK-] rows.
- **No stored progress or health columns**: Rollups (`progress_percent`, `completed_points`, `remaining_points`, `velocity`) are calculated dynamically on read.
- **No hardcoded cross-project dependencies**: Inter-project dependencies belong to 7.12 (`ProgramDependency`); intra-project task dependencies belong to 7.2 (`TaskDependency`).
- **Audit action strings ≤ 10 characters**: `create`, `update`, `delete`, `start`, `complete`, `cancel`, `publish`, `resolve`, `open`, `close`.
- **Badges strictly colour-named (L33)**: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.

---

## 1. Verified Ground Truth

- `Project` [PRJ-] (`apps/projects/models/ProjectInitiation/Projects.py`), url name `projects:prj_detail`.
- `ProjectTask` [TSK-] (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py`), url name `projects:tsk_detail`.
- `TenantNumbered` (`apps/projects/models/_base.py`).
- `TenantModelForm`, `_reject_foreign` (`apps/projects/forms/_common.py`).
- `crud_list`, `crud_detail`, `crud_create`, `crud_edit`, `crud_delete` (`apps/core/crud.py`).
- `write_audit_log` (`apps/core/utils.py`).

---

## 2. Model & Form Specifications

### 2.0 In-Place Extension on `ProjectTask` (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py`)
- Fields:
  - `story_points`: `models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text="Story points estimation (Fibonacci/numeric)")`
  - `sprint`: `models.ForeignKey("projects.Sprint", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")`
  - `epic`: `models.ForeignKey("projects.ProjectEpic", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")`
  - `release`: `models.ForeignKey("projects.ProjectRelease", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")`
- Derived Property:
  - `is_in_backlog`: `self.sprint_id is None`

### 2.1 Entity 1: `Sprint` [SPT-] (`apps/projects/models/AgileScrumManagement/Sprints.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "SPT"`
- Choices:
  - `STATUS_CHOICES = [("planning", "Planning"), ("active", "Active"), ("completed", "Completed"), ("cancelled", "Cancelled")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="sprints")`
  - `name`: `CharField(max_length=255)`
  - `goal`: `TextField(blank=True)`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="planning")`
  - `start_date`: `DateField(null=True, blank=True)`
  - `end_date`: `DateField(null=True, blank=True)`
  - `committed_points`: `PositiveIntegerField(default=0, help_text="Committed story points snapshot at activation")`
  - `scrum_master`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="scrum_master_sprints")`
  - `standup_notes`: `TextField(blank=True, help_text="Daily standup notes, updates, and announcements")`
  - `started_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `completed_at`: `DateTimeField(null=True, blank=True, editable=False)`
- Derived properties:
  - `total_points`: sum of story_points of related tasks
  - `completed_points`: sum of story_points of related tasks with status "done"
  - `remaining_points`: total_points - completed_points
  - `completion_rate`: percentage (0-100)
  - `task_count`: count of tasks
  - `completed_task_count`: count of done tasks
  - `is_overdue`: `end_date < timezone.localdate() and status == "active"`
- Form (`forms/AgileScrumManagement/Sprints.py`):
  - `SprintForm(TenantModelForm)`:
    - `Meta.model = Sprint`
    - `Meta.fields = ["project", "name", "goal", "status", "start_date", "end_date", "scrum_master", "standup_notes"]`
    - `_reject_foreign` checks `project` and `scrum_master`.

### 2.2 Entity 2: `ProjectEpic` [EPC-] (`apps/projects/models/AgileScrumManagement/ProjectEpics.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "EPC"`
- Choices:
  - `STATUS_CHOICES = [("draft", "Draft"), ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="epics")`
  - `name`: `CharField(max_length=255)`
  - `summary`: `TextField(blank=True)`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="draft")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_epics")`
  - `target_start`: `DateField(null=True, blank=True)`
  - `target_end`: `DateField(null=True, blank=True)`
  - `color_code`: `CharField(max_length=7, default="#3b82f6", validators=[RegexValidator(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")])`
- Derived properties:
  - `total_points`, `completed_points`, `progress_percent`, `task_count`, `done_task_count`
- Form (`forms/AgileScrumManagement/ProjectEpics.py`):
  - `ProjectEpicForm(TenantModelForm)`:
    - `Meta.model = ProjectEpic`
    - `Meta.fields = ["project", "name", "summary", "status", "owner", "target_start", "target_end", "color_code"]`

### 2.3 Entity 3: `ProjectRelease` [REL-] (`apps/projects/models/AgileScrumManagement/ProjectReleases.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "REL"`
- Choices:
  - `STATUS_CHOICES = [("unreleased", "Unreleased"), ("in_progress", "In Progress"), ("released", "Released"), ("archived", "Archived")]`
- Fields:
  - `project`: `ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="releases")`
  - `name`: `CharField(max_length=255)`
  - `version_tag`: `CharField(max_length=50)`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="unreleased")`
  - `release_date`: `DateField(null=True, blank=True)`
  - `release_notes`: `TextField(blank=True)`
  - `feature_flags`: `TextField(blank=True, help_text="Enabled feature flags or toggle states")`
  - `released_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `released_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="published_releases")`
- Derived properties:
  - `total_stories`, `completed_stories`, `progress_percent`, `is_overdue`
- Form (`forms/AgileScrumManagement/ProjectReleases.py`):
  - `ProjectReleaseForm(TenantModelForm)`:
    - `Meta.model = ProjectRelease`
    - `Meta.fields = ["project", "name", "version_tag", "status", "release_date", "release_notes", "feature_flags"]`

### 2.4 Entity 4: `SprintImpediment` [IMP-] (`apps/projects/models/AgileScrumManagement/SprintImpediments.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "IMP"`
- Choices:
  - `SEVERITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")]`
  - `STATUS_CHOICES = [("open", "Open"), ("in_progress", "In Progress"), ("resolved", "Resolved")]`
- Fields:
  - `sprint`: `ForeignKey("projects.Sprint", on_delete=models.CASCADE, related_name="impediments")`
  - `title`: `CharField(max_length=255)`
  - `description`: `TextField()`
  - `severity`: `CharField(max_length=10, choices=SEVERITY_CHOICES, default="medium")`
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="open")`
  - `owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_impediments")`
  - `raised_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")`
  - `resolved_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `resolution_notes`: `TextField(blank=True)`
- Form (`forms/AgileScrumManagement/SprintImpediments.py`):
  - `SprintImpedimentForm(TenantModelForm)`:
    - `Meta.model = SprintImpediment`
    - `Meta.fields = ["sprint", "title", "description", "severity", "status", "owner", "resolution_notes"]`

### 2.5 Entity 5: `SprintRetrospective` [RET-] (`apps/projects/models/AgileScrumManagement/SprintRetrospectives.py`)
- Base: `TenantNumbered`, `NUMBER_PREFIX = "RET"`
- Choices:
  - `STATUS_CHOICES = [("draft", "Draft"), ("open", "Open / In Review"), ("closed", "Closed")]`
- Fields:
  - `sprint`: `ForeignKey("projects.Sprint", on_delete=models.CASCADE, related_name="retrospectives")`
  - `conducted_date`: `DateField(default=timezone.localdate)`
  - `conducted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="conducted_retrospectives")`
  - `status`: `CharField(max_length=10, choices=STATUS_CHOICES, default="draft")`
  - `sentiment_score`: `DecimalField(max_digits=3, decimal_places=1, default=Decimal("3.0"), validators=[MinValueValidator(1), MaxValueValidator(5)])`
  - `what_went_well`: `TextField(blank=True)`
  - `what_needs_improvement`: `TextField(blank=True)`
  - `action_items`: `TextField(blank=True)`
  - `closed_at`: `DateTimeField(null=True, blank=True, editable=False)`
- Form (`forms/AgileScrumManagement/SprintRetrospectives.py`):
  - `SprintRetrospectiveForm(TenantModelForm)`:
    - `Meta.model = SprintRetrospective`
    - `Meta.fields = ["sprint", "conducted_date", "conducted_by", "status", "sentiment_score", "what_went_well", "what_needs_improvement", "action_items"]`

---

## 3. URLs and View Context Key Contract (L7 / L41)

### Sprint URLs (`apps/projects/urls/AgileScrumManagement/Sprints.py`):
- `projects:spt_list` -> `/agile/sprints/` -> context: `sprints`, `status_choices`, `projects`
- `projects:spt_create` -> `/agile/sprints/create/` -> context: `form`
- `projects:spt_detail` -> `/agile/sprints/<pk>/` -> context: `sprint`, `tasks`, `impediments`, `burndown_data`
- `projects:spt_edit` -> `/agile/sprints/<pk>/edit/` -> context: `form`, `sprint`
- `projects:spt_delete` -> `/agile/sprints/<pk>/delete/`
- Verbs:
  - `projects:spt_start` -> `/agile/sprints/<pk>/start/` (POST)
  - `projects:spt_complete` -> `/agile/sprints/<pk>/complete/` (POST)
  - `projects:spt_cancel` -> `/agile/sprints/<pk>/cancel/` (POST)

### ProjectEpic URLs (`apps/projects/urls/AgileScrumManagement/ProjectEpics.py`):
- `projects:epc_list` -> `/agile/epics/` -> context: `epics`, `status_choices`, `projects`
- `projects:epc_create` -> `/agile/epics/create/` -> context: `form`
- `projects:epc_detail` -> `/agile/epics/<pk>/` -> context: `epic`, `tasks`
- `projects:epc_edit` -> `/agile/epics/<pk>/edit/` -> context: `form`, `epic`
- `projects:epc_delete` -> `/agile/epics/<pk>/delete/`

### ProjectRelease URLs (`apps/projects/urls/AgileScrumManagement/ProjectReleases.py`):
- `projects:rel_list` -> `/agile/releases/` -> context: `releases`, `status_choices`, `projects`
- `projects:rel_create` -> `/agile/releases/create/` -> context: `form`
- `projects:rel_detail` -> `/agile/releases/<pk>/` -> context: `release`, `tasks`
- `projects:rel_edit` -> `/agile/releases/<pk>/edit/` -> context: `form`, `release`
- `projects:rel_delete` -> `/agile/releases/<pk>/delete/`
- Verb:
  - `projects:rel_publish` -> `/agile/releases/<pk>/publish/` (POST)

### SprintImpediment URLs (`apps/projects/urls/AgileScrumManagement/SprintImpediments.py`):
- `projects:imp_list` -> `/agile/impediments/` -> context: `impediments`, `severity_choices`, `status_choices`, `sprints`
- `projects:imp_create` -> `/agile/impediments/create/` -> context: `form`
- `projects:imp_detail` -> `/agile/impediments/<pk>/` -> context: `impediment`
- `projects:imp_edit` -> `/agile/impediments/<pk>/edit/` -> context: `form`, `impediment`
- `projects:imp_delete` -> `/agile/impediments/<pk>/delete/`
- Verb:
  - `projects:imp_resolve` -> `/agile/impediments/<pk>/resolve/` (POST)

### SprintRetrospective URLs (`apps/projects/urls/AgileScrumManagement/SprintRetrospectives.py`):
- `projects:ret_list` -> `/agile/retrospectives/` -> context: `retrospectives`, `status_choices`, `sprints`
- `projects:ret_create` -> `/agile/retrospectives/create/` -> context: `form`
- `projects:ret_detail` -> `/agile/retrospectives/<pk>/` -> context: `retrospective`
- `projects:ret_edit` -> `/agile/retrospectives/<pk>/edit/` -> context: `form`, `retrospective`
- `projects:ret_delete` -> `/agile/retrospectives/<pk>/delete/`
- Verbs:
  - `projects:ret_open` -> `/agile/retrospectives/<pk>/open/` (POST)
  - `projects:ret_close` -> `/agile/retrospectives/<pk>/close/` (POST)

### Computed Feature Pages URLs:
1. `projects:sprint_backlog` -> `/agile/backlog/` -> context: `backlog_tasks`, `active_sprints`, `future_sprints`, `epics`, `projects`, `selected_project`
2. `projects:sprint_execution` -> `/agile/execution/` -> context: `active_sprint`, `sprints`, `todo_tasks`, `in_progress_tasks`, `done_tasks`, `impediments`, `burndown_data`, `standup_notes`
3. `projects:release_roadmap` -> `/agile/roadmap/` -> context: `releases`, `projects`, `selected_project`
4. `projects:velocity_report` -> `/agile/velocity/` -> context: `completed_sprints`, `avg_velocity`, `total_delivered_points`, `sentiment_history`

---

## 4. Templates Contract

Templates live under `templates/projects/agile/`:
- `sprint/{list,detail,form}.html`
- `epic/{list,detail,form}.html`
- `release/{list,detail,form}.html`
- `impediment/{list,detail,form}.html`
- `retro/{list,detail,form}.html`
- `backlog.html`
- `execution.html`
- `roadmap.html`
- `velocity.html`

Badges:
- `planning`, `draft`, `unreleased`: `badge-info`
- `active`, `in_progress`, `open`: `badge-amber`
- `completed`, `released`, `resolved`, `closed`: `badge-green`
- `cancelled`, `critical`: `badge-red`
- `archived`, `low`, `medium`: `badge-slate` or `badge-muted`

---

## 5. Navigation LIVE_LINKS Contract

In `apps/core/navigation.py`:
```python
"7.13": {
    "Sprint Planning & Backlog Grooming": "projects:sprint_backlog",
    "Sprint Execution & Daily Standups": "projects:sprint_execution",
    "Release & Version Planning": "projects:rel_list",
    "Epic & Feature Management": "projects:epc_list",
    "Retrospectives & Team Health": "projects:ret_list",
    # Extra live leaves:
    "Sprint Register": "projects:spt_list",
    "Impediment Register": "projects:imp_list",
    "Velocity & Health": "projects:velocity_report",
    "Release Roadmap": "projects:release_roadmap",
},
```

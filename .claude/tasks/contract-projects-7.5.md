# CONTRACT — NavERP 7.5 Risk & Issue Management (`projects`)

Frozen 2026-09-11, `BASE = 3eacff12cf7f466922b6874bd4085db647d97f59`.
Source of truth for the build: `.claude/tasks/todo.md` §7.5 + `.claude/tasks/research-projects-7.5.md`.
**An unpinned name renders blank at 200 (L7). Nothing in this file is optional.**

## 0. Identity

| Thing | Value |
|---|---|
| Module / sub-module | 7 / 7.5 Risk & Issue Management |
| Backend sub-package | `apps/projects/{models,forms,views,urls}/RiskManagement/` |
| Template root | `templates/projects/risk/` |
| Migration | `0006_…` (number taken from the disk leaf at generation, never reserved) |
| Models | `ProjectRisk` [RSK-], `RiskResponseAction` [RRA-], `ProjectIssue` [ISS-], `IssueEscalation` [ESC-] |
| Entity file names | `ProjectRisks.py`, `RiskResponseActions.py`, `ProjectIssues.py`, `IssueEscalations.py` (models/forms/views/urls, same name in all four) |
| Extra view+url modules | `RiskAnalysis.py`, `RiskMonitoring.py` (computed pages, no model) |
| Entity template folders | `projectrisk/`, `responseaction/`, `issue/`, `escalation/` |
| Computed templates | `templates/projects/risk/risk_analysis.html`, `risk_monitoring.html` (sub-module level, no entity folder) |
| Tests | `test_risk_models.py` / `_forms` / `_views` / `_security`; test names `test_risk_*`, helpers `_risk_*` |

**URL first segments (all disjoint literals — no converter in any first component):**
`risks/`, `responses/`, `issues/`, `escalations/`, `risk-analysis/`, `risk-monitoring/`.
Existing segments they must not collide with: `""`, `project-requests/`, `projects/`, `stakeholders/`,
`kickoffs/`, `tasks/`, `dependencies/`, `milestones/`, `baselines/`, `resource-profiles/`,
`allocations/`, `time-entries/`, `capacity-demand/`, `budgetlines/`, `revisions/`,
`controlaccounts/`, `expenses/`.

## 1. Shared toolkit facts (verified, do not re-derive)

* `apps/projects/models/_base.py` → `TenantOwned` (tenant FK + `created_at`/`updated_at`),
  `TenantNumbered` (`NUMBER_PREFIX`, per-tenant `number` allocated in `save()` with a collision
  retry), `q2()`, `MAX_Q2`, `ZERO`, and re-exported `models`, `settings`, `timezone`, `Decimal`,
  `MinValueValidator`, `MaxValueValidator`, `Q`, `F`, `Sum`, `Count`, `next_number`, `IntegrityError`.
* `apps/projects/forms/_common.py` → `forms`, `ValidationError`, `TenantModelForm`,
  `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`.
  **`TenantUniqueMixin` FIRST, then `TenantModelForm`** on every form whose model `clean()` compares
  a chosen FK's project.
* `apps/projects/views/_common.py` → `messages`, `login_required`, `get_object_or_404`, `redirect`,
  `render`, `require_POST`, `crud_create`, `crud_delete`, `crud_detail`, `crud_edit`, `crud_list`,
  `tenant_admin_required`, `write_audit_log`.
* `apps/core/crud.py` → `crud_list(request, qs, template, *, search_fields=(), filters=(),
  extra_context=None, per_page=15)` renders `object_list`/`page_obj`/`q`; `filters` are
  `(get_param, orm_lookup, is_int)` **field lookups only** — a Python *property* can never be a
  filter, so every derived lens (`?band=`, `?overdue=`, `?review_due=`, `?escalated=1`, `?top=1`)
  is **pre-scoped in the view** before `crud_list`. `as_db_int(value)` guards every int GET.
  `crud_edit` renders `form`/`obj`/`is_edit`; `crud_delete` is self-defending (POST-only) but the
  views still carry `@require_POST`.
* `apps/projects/views/_helpers.py` — **7.5 adds one builder here** (Integrate): `owners(tenant)`
  (shared by all four registers; returns `get_user_model().objects.filter(tenant=tenant)
  .order_by("email")`, `.none()` for a tenant-less user — the `org_units`/`projects` precedent).
* `write_audit_log(user, obj, action, changes=None, tenant=None)`; **`AuditLog.action` is
  `varchar(10)`** — allowed verbs: `create`, `update`, `delete`, `realize`, `close`, `reopen`,
  `complete`, `escalate`, `resolve`. The verb + transition live in `changes`
  (`{"verb":…, "from":…, "to":…}`). Capture `previous = obj.status` **before** mutating.
* Badge classes that exist in `static/css/theme.css`: **`badge-green`, `badge-amber`, `badge-red`,
  `badge-info`, `badge-muted`, `badge-slate`** only. Stat-icon colours: `blue`, `green`, `orange`,
  `purple`, `red`, `slate`. There is **no** `-success`/`-warning`/`-danger` (L33).
* `_safe_reverse` (`apps/core/navigation.py`) supports both `?query` and `#fragment` suffixes.
* Verified spine FKs: `projects.Project` (`.name`, `.code`, `.project_manager`, `.start_date`,
  `.end_date`, `.status`), `projects.ProjectTask` (`.project`, `.name`, `.node_type`, `.sequence`),
  `projects.CostControlAccount` (`.project`, `.contingency`), `projects.BudgetRevision` (`.project`,
  `.status`, `.activated_at`, `.currency`), `projects.ProjectBudgetLine` (`.budget_revision`,
  `.project`, `.amount`). No `Risk`/`Issue`/`LessonsLearned`/`Simulation` class exists anywhere.

## 2. Models

All four: `TenantNumbered`, `unique_together = ("tenant", "number")`, money `DecimalField(14, 2)`
with `MinValueValidator(Decimal("0"))`, all scores/bands/EMV **derived properties, never stored**.

### 2.1 `ProjectRisk` [RSK-] — `models/RiskManagement/ProjectRisks.py`

Choices:
* `CATEGORY_CHOICES` (max_length=16): `technical`/Technical, `schedule`/Schedule, `cost`/Cost,
  `resource`/Resource, `external`/External, `organizational`/Organizational, `quality`/Quality,
  `compliance`/Compliance, `other`/Other
* `RISK_TYPE_CHOICES` (max_length=12): `threat`/Threat, `opportunity`/Opportunity
* `RESPONSE_STRATEGY_CHOICES` (max_length=12): `avoid`/Avoid, `mitigate`/Mitigate,
  `transfer`/Transfer, `accept`/Accept, `exploit`/Exploit, `escalate`/Escalate
* `STATUS_CHOICES` (max_length=16): `identified`/Identified, `assessing`/Assessing,
  `response_planned`/Response Planned, `monitoring`/Monitoring, `realized`/Realized, `closed`/Closed
* `PROBABILITY_PCT = {1: 10, 2: 30, 3: 50, 4: 70, 5: 90}` (documented constant map)
* `SEVERITY_BANDS` — `{"low": (1, 3), "medium": (4, 7), "high": (8, 14), "critical": (15, 25)}`
* `TOLERANCE_BANDS = {"high", "critical"}` (documented constant, not a per-tenant table)

Fields (declared):
`project` FK `"projects.Project"` CASCADE `related_name="risks"` ·
`wbs_node` FK `"projects.ProjectTask"` SET_NULL null+blank `related_name="risks"` ·
`title` CharField(255) · `description` TextField() · `cause` TextField(blank) · `effect` TextField(blank) ·
`category` CharField(16, CATEGORY_CHOICES, default `other`) ·
`risk_type` CharField(12, RISK_TYPE_CHOICES, default `threat`) ·
`probability` PositiveSmallIntegerField(`MinValueValidator(1)`, `MaxValueValidator(5)`) ·
`impact` PositiveSmallIntegerField(`MinValueValidator(1)`, `MaxValueValidator(5)`) ·
`cost_impact` DecimalField(14,2, default `Decimal("0")`, `MinValueValidator(0)`) ·
`schedule_impact_days` PositiveIntegerField(null+blank) ·
`response_strategy` CharField(12, RESPONSE_STRATEGY_CHOICES, default `mitigate`) ·
`response_note` TextField(blank) · `trigger` TextField(blank) · `contingency_plan` TextField(blank) ·
`status` CharField(16, STATUS_CHOICES, default `identified`) — **off the form** ·
`owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="owned_risks"` ·
`identified_by` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="raised_risks"` ·
`identified_date` DateField(default `timezone.localdate`) · `review_date` DateField(null+blank) ·
`residual_probability` / `residual_impact` PositiveSmallIntegerField(null+blank,
validators 1–5) · `contingency_account` FK `"projects.CostControlAccount"` SET_NULL null+blank
`related_name="risks"` · `lessons_learned` TextField(blank) ·
`closed_at` DateTimeField(null+blank, `editable=False`) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="rsk_created"`

Derived / Meta:
* `score` = `probability * impact`
* `severity_band` → key of `SEVERITY_BANDS`; **`get_severity_band_display()`** hand-written
  (`{"low":"Low","medium":"Medium","high":"High","critical":"Critical"}`) — Django does not generate
  `get_FOO_display` for a property (the `ProjectStakeholder.get_engagement_strategy_display`
  precedent); without it the template renders blank.
* `emv` = `q2(cost_impact * PROBABILITY_PCT[probability] / 100)`; `exposure` = `emv`
* `residual_score` = `residual_probability * residual_impact` (None if either None);
  `residual_band` via `SEVERITY_BANDS` (None when `residual_score` is None)
* `residual_emv` = `q2(cost_impact * residual_probability / 100)` when `residual_probability` else
  `Decimal("0")`
* `is_review_overdue` = `review_date` set, `< timezone.localdate()`, and `status not in
  ("realized", "closed")`
* `is_locked` = `status in ("realized", "closed")`
* `clean()`: `wbs_node.project_id == project_id`; `contingency_account.project_id == project_id`
  — field-keyed `ValidationError`s
* `ordering = ["-created_at", "-id"]`; indexes `rsk_tnt_project_idx` ("tenant","project"),
  `rsk_tnt_status_idx` ("tenant","status"), `rsk_tnt_category_idx` ("tenant","category"),
  `rsk_tnt_rtype_idx` ("tenant","risk_type"), `rsk_tnt_created_idx` ("tenant","-created_at")
* `__str__` = `f"{self.number} — {self.title}"`

### 2.2 `RiskResponseAction` [RRA-] — `models/RiskManagement/RiskResponseActions.py`

* `STRATEGY_CHOICES` (12) = the same six as `ProjectRisk.RESPONSE_STRATEGY_CHOICES`
* `STATUS_CHOICES` (12): `planned`/Planned, `in_progress`/In Progress, `completed`/Completed,
  `cancelled`/Cancelled

Fields: `risk` FK `"projects.ProjectRisk"` CASCADE `related_name="response_actions"` ·
`title` CharField(255) · `description` TextField(blank) ·
`strategy` CharField(12, STRATEGY_CHOICES, default `mitigate`) ·
`owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="risk_actions"` ·
`due_date` DateField(null+blank) · `cost` DecimalField(14,2, default 0, MinValueValidator(0)) ·
`trigger` TextField(blank) · `status` CharField(12, STATUS_CHOICES, default `planned`) — off the form ·
`residual_probability`/`residual_impact` PositiveSmallIntegerField(null+blank, 1–5) ·
`completed_at` DateTimeField(null+blank, `editable=False`) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="rra_created"`

Derived: `is_overdue` = `due_date` set, `< today`, `status not in ("completed","cancelled")` ·
`residual_score` · `is_locked` = `status == "completed"`.
Meta: `ordering = ["-created_at", "-id"]`; indexes `rra_tnt_risk_idx` ("tenant","risk"),
`rra_tnt_status_idx`, `rra_tnt_owner_idx` ("tenant","owner"), `rra_tnt_due_idx` ("tenant","due_date").
`__str__` = `f"{self.number} — {self.title}"`.

### 2.3 `ProjectIssue` [ISS-] — `models/RiskManagement/ProjectIssues.py`

* `ISSUE_TYPE_CHOICES` (12): `issue`/Issue, `action_item`/Action Item, `decision`/Decision,
  `other`/Other
* `SEVERITY_CHOICES` (8): `critical`/Critical, `high`/High, `medium`/Medium, `low`/Low
* `STATUS_CHOICES` (12): `open`/Open, `in_progress`/In Progress, `blocked`/Blocked,
  `resolved`/Resolved, `closed`/Closed, `cancelled`/Cancelled

Fields: `project` FK `"projects.Project"` CASCADE `related_name="issues"` ·
`wbs_node` FK `"projects.ProjectTask"` SET_NULL null+blank `related_name="issues"` ·
`risk` FK `"projects.ProjectRisk"` SET_NULL null+blank `related_name="issues"` ·
`title` CharField(255) · `description` TextField() ·
`issue_type` CharField(12, ISSUE_TYPE_CHOICES, default `issue`) ·
`severity` CharField(8, SEVERITY_CHOICES, default `medium`) ·
`status` CharField(12, STATUS_CHOICES, default `open`) — off the form ·
`owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="owned_issues"` ·
`raised_by` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="raised_issues"` ·
`identified_date` DateField(default `timezone.localdate`) · `due_date` DateField(null+blank) ·
`escalation_level` PositiveSmallIntegerField(default 0) ·
`escalated_to` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="escalated_issues"` ·
`escalated_at` DateTimeField(null+blank, `editable=False`) ·
`root_cause` TextField(blank) · `resolution_note` TextField(blank) ·
`resolved_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="resolved_issues"` ·
`resolved_at` DateTimeField(null+blank, `editable=False`) · `lessons_learned` TextField(blank) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="iss_created"`

Derived: `is_open` = `status in ("open","in_progress","blocked")` ·
`is_overdue` = `due_date` set, `< today`, and `is_open` ·
`age_days` = `(timezone.localdate() - identified_date).days` (0 when unset) ·
`is_locked` = `status in ("resolved","closed")`.
Meta: `ordering = ["-created_at","-id"]`; indexes `iss_tnt_project_idx`, `iss_tnt_status_idx`,
`iss_tnt_severity_idx`, `iss_tnt_esc_idx` ("tenant","escalation_level"), `iss_tnt_created_idx`.
`clean()`: `wbs_node.project_id == project_id`; `risk.project_id == project_id`.
`__str__` = `f"{self.number} — {self.title}"`.

### 2.4 `IssueEscalation` [ESC-] — `models/RiskManagement/IssueEscalations.py`

Fields: `issue` FK `"projects.ProjectIssue"` CASCADE `related_name="escalations"` ·
`level` PositiveSmallIntegerField(`MinValueValidator(1)`, `MaxValueValidator(4)`) ·
`target_role` CharField(80, blank) · `target_user` FK AUTH_USER_MODEL SET_NULL null+blank
`related_name="issue_escalations"` · `reason` TextField() (required) ·
`escalated_by` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="escalations_raised"` ·
`escalated_at` DateTimeField(`auto_now_add=True`) · `resolved_at` DateTimeField(null+blank) ·
`outcome` TextField(blank) · `created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="esc_created"`

Meta: `ordering = ["issue_id", "level", "id"]`; indexes `esc_tnt_issue_idx`, `esc_tnt_level_idx`.
`LEVEL_CHOICES = [(1,"Level 1 — Team Lead"), (2,"Level 2 — Project Manager"),
(3,"Level 3 — Program Manager"), (4,"Level 4 — Executive Sponsor")]` (a class constant used by the
`esc_list` filter and the form). `__str__` = `f"{self.number} — L{self.level} {self.issue.number}"`.

## 3. Forms (6)

| Form | Module | `Meta.fields` / exclusion |
|---|---|---|
| `ProjectRiskForm` | `ProjectRisks.py` | fields: `project, wbs_node, title, description, cause, effect, category, risk_type, probability, impact, cost_impact, schedule_impact_days, response_strategy, response_note, trigger, contingency_plan, owner, identified_by, identified_date, review_date, residual_probability, residual_impact, contingency_account, lessons_learned` (excludes `tenant, number, status, closed_at, created_by`) |
| `RiskClosureForm` | `ProjectRisks.py` | plain `forms.Form`: `lessons_learned` CharField(required=False, `widget=Textarea`) |
| `RiskResponseActionForm` | `RiskResponseActions.py` | fields: `risk, title, description, strategy, owner, due_date, cost, trigger, residual_probability, residual_impact` (excludes `tenant, number, status, completed_at, created_by`) |
| `ProjectIssueForm` | `ProjectIssues.py` | fields: `project, wbs_node, risk, title, description, issue_type, severity, owner, raised_by, identified_date, due_date, lessons_learned` (excludes `tenant, number, status, root_cause, resolution_note, resolved_by, resolved_at, escalation_level, escalated_to, escalated_at, created_by`) |
| `IssueResolutionForm` | `ProjectIssues.py` | plain `forms.Form`: `root_cause` CharField(required=False, Textarea), `resolution_note` CharField(required=True, Textarea) |
| `IssueEscalationForm` | `IssueEscalations.py` | `TenantUniqueMixin, TenantModelForm` — fields: `issue, level, target_role, target_user, reason, outcome` (excludes `tenant, number, escalated_by, escalated_at, resolved_at, created_by`) |

Every ModelForm whose model `clean()` compares an FK's project mixes in **`TenantUniqueMixin`
first**. Every tenant-scoped FK on every form is re-checked with
`_reject_foreign(self, cleaned, [...])` — never `accounting.Currency` (not used this pass).

## 4. Views, routes & CONTEXT KEYS (the contract)

### 4.1 ProjectRisk — `views/RiskManagement/ProjectRisks.py`

Routes (`urls/RiskManagement/ProjectRisks.py`): `risks/` `rsk_list` · `risks/add/` `rsk_create` ·
`risks/<int:pk>/` `rsk_detail` · `risks/<int:pk>/edit/` `rsk_edit` ·
`risks/<int:pk>/delete/` `rsk_delete` · `risks/<int:pk>/realize/` `rsk_realize` ·
`risks/<int:pk>/close/` `rsk_close` · `risks/<int:pk>/reopen/` `rsk_reopen`.

`rsk_list` — qs `ProjectRisk.objects.filter(tenant=request.tenant).select_related("project",
"wbs_node", "owner", "identified_by", "contingency_account")`.
`search_fields = ["number", "title", "description", "cause", "effect"]`.
`filters = [("project","project_id",True), ("category","category",False),
("risk_type","risk_type",False), ("status","status",False), ("owner","owner_id",True)]`.
Pre-scoped derived lenses (applied to the qs before `crud_list`):
* `?band=low|medium|high|critical` → `Q` OR of `Q(probability=p, impact=i)` for every `(p, i)` whose
  product falls in `SEVERITY_BANDS[band]`; an unknown band value is **ignored** (L11).
* `?review_due=1` / `?overdue=1` → `Q(review_date__lt=timezone.localdate(),
  status__in=("identified","assessing","response_planned","monitoring"))`
* `?top=1` → `qs.order_by("-probability", "-impact", "-cost_impact")` (a stable DB ordering; the
  `score` property is not a column)
`extra_context` (exact keys): `projects`, `category_choices`, `risk_type_choices`,
`status_choices`, `strategy_choices`, `band_choices`
(`[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")]`), `owners`.

`rsk_create` — `crud_create`-style but the view stamps `created_by` and `identified_by` (default
`request.user` when the form leaves it blank): use the explicit `pex_create` pattern, not
`crud_create`. `?project=` seeds the `project` initial via `as_db_int`. Template
`projects/risk/projectrisk/form.html` with `form`, `is_edit=False`.

`rsk_detail` — `render` with `obj` plus `response_actions` (`obj.response_actions
.select_related("owner").order_by("due_date","id")`) and `linked_issues` (`obj.issues
.select_related("owner")`). Derived figures read straight off `obj` (no computed context keys).

`rsk_edit` — refuses a locked row (`messages.error` + redirect to detail); else `crud_edit`.
`rsk_delete` — `@require_POST`; refuses a locked row; else `crud_delete`.

Verbs (all `@login_required @require_POST`, `previous = obj.status` captured first, audit via
`changes={"verb","from","to"}`):
* `rsk_realize` — login. Refused when `status == "closed"` (error). Already `realized` → info, no
  write. Otherwise `status = "realized"`, then **creates the linked `ProjectIssue`**:
  `project=obj.project`, `risk=obj`, `wbs_node=obj.wbs_node`, `title=obj.title[:255]`,
  `description=obj.effect or obj.description`, `severity` mapped from `severity_band`
  (`critical→critical`, `high→high`, `medium→medium`, `low→low`), `owner=obj.owner`,
  `raised_by=request.user`, `identified_date=timezone.localdate()`, `created_by=request.user`.
  Audit `realize` on the risk (`changes` includes `"issue": issue.number`) and `create` on the issue.
  Message names both numbers.
* `rsk_close` — login. Already `closed` → info, no write. Otherwise bound `RiskClosureForm`; on valid,
  stores `lessons_learned` when supplied, `status = "closed"`, `closed_at = timezone.now()`.
  Audit `close`.
* `rsk_reopen` — **`@tenant_admin_required`**. Only from `closed` (else error). `status =
  "monitoring"`, `closed_at = None`. Audit `reopen`.

### 4.2 RiskResponseAction — `views/RiskManagement/RiskResponseActions.py`

Routes: `responses/` `rra_list` · `responses/add/` `rra_create` · `responses/<int:pk>/`
`rra_detail` · `responses/<int:pk>/edit/` `rra_edit` · `responses/<int:pk>/delete/` `rra_delete` ·
`responses/<int:pk>/complete/` `rra_complete`.

`rra_list` — qs `.select_related("risk", "risk__project", "owner")`;
`search_fields = ["number","title","description","trigger"]`;
`filters = [("risk","risk_id",True), ("strategy","strategy",False), ("status","status",False),
("owner","owner_id",True)]`; derived `?overdue=1` →
`Q(due_date__lt=today, status__in=("planned","in_progress"))`.
`extra_context`: `risks` (`ProjectRisk.objects.filter(tenant=…)`), `strategy_choices`,
`status_choices`, `owners`. Detail: `obj` (+ `obj.risk` read in the template).

`rra_create` stamps `created_by`; `?risk=` seeds the `risk` initial. `rra_edit`/`rra_delete` refuse a
locked (`completed`) row. `rra_complete` (login): already `completed` → info, no write; else
`status = "completed"`, `completed_at = timezone.now()`, audit `complete`.

### 4.3 ProjectIssue — `views/RiskManagement/ProjectIssues.py`

Routes: `issues/` `iss_list` · `issues/add/` `iss_create` · `issues/<int:pk>/` `iss_detail` ·
`issues/<int:pk>/edit/` `iss_edit` · `issues/<int:pk>/delete/` `iss_delete` ·
`issues/<int:pk>/escalate/` `iss_escalate` · `issues/<int:pk>/resolve/` `iss_resolve` ·
`issues/<int:pk>/close/` `iss_close`.

`iss_list` — qs `.select_related("project","wbs_node","risk","owner","raised_by","escalated_to")`;
`search_fields = ["number","title","description"]`;
`filters = [("project","project_id",True), ("severity","severity",False), ("status","status",False),
("issue_type","issue_type",False), ("owner","owner_id",True), ("risk","risk_id",True)]`;
derived `?escalated=1` → `Q(escalation_level__gt=0)`; `?overdue=1` →
`Q(due_date__lt=today, status__in=("open","in_progress","blocked"))`.
`extra_context`: `projects`, `severity_choices`, `status_choices`, `issue_type_choices`, `owners`,
`risks`. Detail: `obj`, `escalations` (`obj.escalations.select_related("target_user","escalated_by")
.order_by("level","id")`), `escalation_form` (an unbound `IssueEscalationForm(tenant=request.tenant,
initial={"level": min(obj.escalation_level + 1, 4)})`), `resolution_form` (unbound
`IssueResolutionForm()`).

`iss_create` stamps `created_by` and `raised_by` (default `request.user`); `?project=` seeds the
`project` initial. `iss_edit`/`iss_delete` refuse a locked row.

Verbs:
* `iss_escalate` — **`@tenant_admin_required @require_POST`**. Refused when the issue `is_locked`
  (resolved/closed) or `escalation_level >= 4` (error). Binds `IssueEscalationForm(request.POST,
  tenant=request.tenant)`; on invalid → `messages.error` with the first error and redirect back.
  On valid: `level` defaults to `min(obj.escalation_level + 1, 4)`; saves the row with
  `issue=obj`, `escalated_by=request.user`, `created_by=request.user`, `tenant`; then sets
  `escalation_level = level`, `escalated_to = row.target_user`, `escalated_at = timezone.now()`.
  Audit `escalate` on the issue.
* `iss_resolve` — login. Refused when `is_locked` (error); `resolved` → info, no write. Binds
  `IssueResolutionForm(request.POST)`; on valid sets `root_cause`, `resolution_note`,
  `resolved_by = request.user`, `resolved_at = timezone.now()`, `status = "resolved"`. Audit
  `resolve`.
* `iss_close` — login. Only from `resolved` (else error). `status = "closed"`. Audit `close`.

### 4.4 IssueEscalation — `views/RiskManagement/IssueEscalations.py`

Routes: `escalations/` `esc_list` · `escalations/add/` `esc_create` · `escalations/<int:pk>/`
`esc_detail` · `escalations/<int:pk>/edit/` `esc_edit` · `escalations/<int:pk>/delete/` `esc_delete`.

`esc_list` — qs `.select_related("issue","issue__project","target_user","escalated_by")`;
`search_fields = ["number","target_role","reason","outcome"]`;
`filters = [("issue","issue_id",True), ("level","level",True), ("target_user","target_user_id",True)]`.
`extra_context`: `issues` (`ProjectIssue.objects.filter(tenant=…)`), `level_choices`
(`IssueEscalation.LEVEL_CHOICES`), `owners`. Detail: `obj` (+ `obj.issue`).
`esc_create` stamps `created_by` and `escalated_by` (default `request.user`); `?issue=` seeds the
`issue` initial. No verbs.

### 4.5 `risk_analysis` — `views/RiskManagement/RiskAnalysis.py`, route `risk-analysis/`

Template `projects/risk/risk_analysis.html`. **GET renders the matrix + EMV tables; POST runs the
seeded Monte Carlo** and re-renders. Context (exact keys):
* `projects` — tenant `Project` queryset ordered by `name`; `project` — the selected `Project` from
  `?project=` (`as_db_int`-guarded, `filter(tenant=request.tenant)`), else `None`
* `baseline` — the project's `BudgetRevision` with `status="approved"` and `activated_at__isnull=False`
  ordered `-activated_at` first, else `None`; `baseline_total` = `q2(Σ lines.amount)` or `None`
* `matrix` — 5 rows (probability 5→1), each a list of 5 cells
  `{"probability", "impact", "count", "badge", "risks"}` where `badge` is the band's colour class
  (`low→badge-green`, `medium→badge-info`, `high→badge-amber`, `critical→badge-red`);
  `matrix_max` — max cell count (0-safe)
* `emv_rows` — per risk `{"risk", "probability_pct", "cost_impact", "emv"}` ordered `-emv`, capped 50;
  `emv_total` = `q2(Σ emv)`; `residual_emv_total` = `q2(Σ residual_emv)`
* `seed` (effective int, default constant `42`, always shown), `iterations` (effective int, default
  `1000`, clamped `100…10000`), `run` (True only on a POST that ran the simulation)
* `simulation` — `None` on a plain GET; else `{"mean", "p10", "p50", "p80", "p90", "samples",
  "baseline_total", "overrun_probability", "contingency_delta"}` where
  `overrun_probability` = percentage (1dp) of iterations whose sampled exposure exceeds
  `baseline_total` (`None` when there is no baseline) and `contingency_delta` = `q2(p80 − baseline_total)`
  (`None` when no baseline). **Displayed, never written** to the CA (Ruling 4).
* `?seed=` / `?iterations=` are parsed through a module-level `forms.Form`
  (`SimulationParamsForm`: `seed = IntegerField(required=False)`, `iterations =
  IntegerField(required=False, min_value=100, max_value=10000)`) — **never** raw `request.GET`
  parsing (L35). A junk seed falls back to the default and never 500s.

Simulation algorithm (pin it in the view docstring):
`random.Random(seed)`; population = the project's risks with `cost_impact > 0` and
`status not in ("closed", "realized")`; per iteration `total += cost_impact` when
`rng.random() < PROBABILITY_PCT[probability] / 100`; percentiles by nearest-rank on the sorted
sample list (`sorted_samples[min(n - 1, int(round(p / 100 * (n - 1))))]` for p in 10/50/80/90);
`mean` = `q2(Σ samples / n)`. Simple random sampling is the documented simplification (Latin
Hypercube / correlation are deferred). **No stored simulation table, no chart library.**

### 4.6 `risk_monitoring` — `views/RiskManagement/RiskMonitoring.py`, route `risk-monitoring/`

Template `projects/risk/risk_monitoring.html`, **GET-only**. Context (exact keys):
* `projects`, `project` (from `?project=`, `as_db_int`-guarded), `open_count`, `closed_count`,
  `realized_count`
* `top_risks` — the (project-scoped) register ordered `-probability, -impact, -cost_impact`, cap 25
* `burndown_rows` — period rows `{"period" (YYYY-MM), "label" (e.g. "Sep 2026"), "count",
  "score_total", "emv_total", "bar_pct"}` aggregated by `identified_date` month over the selected
  project (or all the tenant's risks when no project is selected), ordered by period ascending;
  `bar_pct` = `score_total` as a percentage of the max row's `score_total` (0-safe); `burndown_max`
* `review_queue` — risks with `review_date` set and `< today` and status not in
  `("realized","closed")`, ordered `review_date`; `review_due_count`
* `tolerance` — `{"threshold" (the label "High / Critical"), "band", "above"}`;
  `above_tolerance_count` = count of open risks whose `severity_band` is in `TOLERANCE_BANDS`
* `lessons` — list of `{"kind" ("Risk"/"Issue"), "obj", "lesson"}` over closed `ProjectRisk` rows and
  closed/resolved `ProjectIssue` rows with a non-empty `lessons_learned`, newest first, cap 25;
  `lessons_count`
* `by_category`, `by_band` — dicts `{label: count}` for the summary strip

Rendering: matrix grid, EMV/percentile tables, CSS bar rows (`style="width: {{ row.bar_pct }}%"`),
badges. **No chart library** (7.16 owns charts), **no stored snapshot**.

## 5. Templates

* `projectrisk/{list,detail,form}.html`, `responseaction/{list,detail,form}.html`,
  `issue/{list,detail,form}.html`, `escalation/{list,detail,form}.html`, plus
  `risk_analysis.html`, `risk_monitoring.html` at `templates/projects/risk/`.
* Every list: `.page-header` + breadcrumb, GET filter form reflecting `request.GET` (string filters
  `{% if request.GET.status == value %}selected{% endif %}`; FK filters
  `{% if request.GET.project == p.pk|stringformat:"d" %}selected{% endif %}`), `.table-wrap`/`.table`
  with an Actions column (eye → detail, pencil → edit, delete POST form + `confirm()` +
  `{% csrf_token %}`), `.pagination` guarded by `has_previous`/`has_next`, `.empty-state`.
* Badges: colour-named only; every block ends
  `{% else %}{{ obj.get_<field>_display }}{% endif %}`.
* **No nullable FK inside a `|default:` filter argument** (L10) — `owner`, `identified_by`,
  `escalated_to`, `resolved_by`, `target_user` render via `{% if fk %}…{% else %}—{% endif %}`.
* **Multi-line notes use `{% comment %} … {% endcomment %}`** — a multi-line `{# … #}` leaks as
  visible text (L2).
* Verb buttons are POST forms with `{% csrf_token %}`, gated by status/role in the template the same
  way the view gates them (defence in depth, not the boundary).

## 6. Wire-up (Integrate only — single writer, surgical edits)

* `apps/projects/{models,forms,views,urls}/RiskManagement/__init__.py` — **empty** sub-package
  `__init__.py` files (4 files).
* Top-level `__init__.py` re-export blocks `# --- 7.5 Risk & Issue Management` in all four layers:
  models (4), forms (6), views (4 CRUD sets + 7 verbs + `risk_analysis` + `risk_monitoring`),
  urls (6 `urlpatterns` imports + concat, in the order ProjectRisks, RiskResponseActions,
  ProjectIssues, IssueEscalations, RiskAnalysis, RiskMonitoring).
* `apps/projects/views/_helpers.py` — add `owners(tenant)`.
* `apps/projects/admin.py` — 4 registrations (`list_display` led by `number`,
  `list_select_related` for every rendered FK, `closed_at`/`resolved_at`/`completed_at`/`escalated_at`
  readonly).
* `apps/projects/management/commands/seed_projects.py` — a `_risk` block with its own guard
  (`ProjectRisk.objects.filter(tenant=tenant).exists()`), called per tenant; `--flush` deletes
  children-first `IssueEscalation, ProjectIssue, RiskResponseAction, ProjectRisk`.
* `apps/core/navigation.py` — one `LIVE_LINKS["7.5"]` block immediately after the `"7.4"` block:
  `Risk Identification & Register` → `projects:rsk_list`; `Qualitative & Quantitative Analysis` →
  `projects:risk_analysis`; `Risk Response Planning` → `projects:rra_list`;
  `Issue Logging & Escalation` → `projects:iss_list`; `Risk Monitoring & Reporting` →
  `projects:risk_monitoring`; extra leaf `Issue Escalation Queue` → `projects:iss_list?escalated=1`.
* `templates/projects/overview.html` — 7.5 quick links + counts.
* `config/settings.py` / `config/urls.py` — **not touched** (app already registered).
* Then: `makemigrations projects --dry-run` (read every model it names; abort if it names anything
  outside 7.5's four) → generate → `migrate` → `seed_projects` ×2 → `manage.py check`.

## 7. Sidebar keys (verbatim from NavERP.md — must match character-for-character)

1. `Risk Identification & Register`
2. `Qualitative & Quantitative Analysis`
3. `Risk Response Planning`
4. `Issue Logging & Escalation`
5. `Risk Monitoring & Reporting`

# CONTRACT — NavERP 7.7 Scope & Requirements Management (`projects`)

Frozen 2026-09-11, `BASE = 08d91a7d8f80906e19f64b35ec72b16932741824`.
Source of truth for the build: `NavERP.md` §7.7 + `.claude/skills/projects/SKILL.md` + the 7.1–7.5
as-built code. **An unpinned name renders blank at 200 (L7). Nothing in this file is optional.**

## 0. Identity

| Thing | Value |
|---|---|
| Module / sub-module | 7 / 7.7 Scope & Requirements Management |
| Backend sub-package | `apps/projects/{models,forms,views,urls}/ScopeRequirements/` |
| Template root | `templates/projects/scope/` |
| Migration | the next free number on disk at generation time (never reserved) |
| Models | `Requirement` [REQ-], `ScopeItem` [SCI-], `ScopeChangeRequest` [SCR-], `ScopeVerification` [SVR-] |
| Entity files | `Requirements.py`, `ScopeItems.py`, `ScopeChangeRequests.py`, `ScopeVerifications.py` (same name in all four layers) |
| Extra view+url module | `ScopeMatrix.py` (computed page, no model) |
| Entity template folders | `requirement/`, `scopeitem/`, `scopechange/`, `scopeverification/` |
| Computed template | `templates/projects/scope/scope_matrix.html` (sub-module level, no entity folder) |
| Tests | `test_scope_{models,forms,views,security}.py`; names `test_scope_*`, helpers `_scope_*` |

**URL first segments (all disjoint literals — no converter in any first component):**
`requirements/`, `scope-items/`, `scope-changes/`, `scope-verifications/`, `scope-matrix/`.
Existing segments they must not collide with: `""`, `project-requests/`, `projects/`,
`stakeholders/`, `kickoffs/`, `tasks/`, `dependencies/`, `milestones/`, `baselines/`,
`resource-profiles/`, `allocations/`, `time-entries/`, `capacity-demand/`, `budgetlines/`,
`revisions/`, `controlaccounts/`, `expenses/`, `risks/`, `responses/`, `issues/`, `escalations/`,
`risk-analysis/`, `risk-monitoring/`.

## 1. Shared toolkit facts (verified, do not re-derive)

* `apps/projects/models/_base.py` → `TenantOwned`, `TenantNumbered` (`NUMBER_PREFIX`, per-tenant
  `number` in `save()` with a collision retry), `q2()`, `MAX_Q2`, `ZERO`, re-exported `models`,
  `settings`, `timezone`, `Decimal`, validators, `Q`, `F`, `Sum`, `Count`, `next_number`,
  `IntegrityError`.
* `apps/projects/forms/_common.py` → `forms`, `ValidationError`, `TenantModelForm`,
  `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`.
  **`TenantUniqueMixin` FIRST, then `TenantModelForm`** on every form whose model `clean()`
  compares a chosen FK's project.
* `apps/projects/views/_common.py` → `messages`, `login_required`, `get_object_or_404`, `redirect`,
  `render`, `require_POST`, `crud_create`, `crud_delete`, `crud_detail`, `crud_edit`, `crud_list`,
  `tenant_admin_required`, `write_audit_log`, `timezone`.
* `apps/core/crud.py` → `crud_list(request, qs, template, *, search_fields=(), filters=(),
  extra_context=None, per_page=15)` renders `object_list`/`page_obj`/`q`; `filters` are
  `(get_param, orm_lookup, is_int)` **field lookups only** — a Python *property* can never be a
  filter, so every derived lens (`?untraced=1`, `?pending=1`, `?high_impact=1`, `?open=1`) is
  **pre-scoped in the view** before `crud_list`. `as_db_int(value)` guards every int GET.
  `crud_edit` renders `form`/`obj`/`is_edit`; `crud_delete` is POST-only self-defending.
* `apps/projects/views/_helpers.py` — **7.7 adds one builder** (Integrate): `requirements(tenant)`
  (shared by the change-request and verification registers' filter dropdowns; returns
  `Requirement.objects.filter(tenant=tenant).order_by("number")`, `.none()` for a tenant-less user
  — the `owners`/`projects` precedent). `projects(tenant)` and `owners(tenant)` already exist.
* `write_audit_log(user, obj, action, changes=None, tenant=None)`; **`AuditLog.action` is
  `varchar(10)`** — allowed verbs: `create`, `update`, `delete`, `submit`, `approve`, `reject`,
  `review`, `verify`, `realize`, `retire`, `accept`, `waive`, `implement`. The transition lives in
  `changes` (`{"verb":…, "from":…, "to":…}`). Capture `previous = obj.status` **before** mutating.
* Badge classes that exist in `static/css/theme.css`: **`badge-green`, `badge-amber`, `badge-red`,
  `badge-info`, `badge-muted`, `badge-slate`** only. Stat-icon colours: `blue`, `green`, `orange`,
  `purple`, `red`, `slate`. There is **no** `-success`/`-warning`/`-danger` (L33).
* `_safe_reverse` (`apps/core/navigation.py`) supports both `?query` and `#fragment` suffixes.
* Verified spine FKs: `projects.Project` (`.name`, `.code`, `.project_manager`, `.status`,
  `.in_scope`, `.out_of_scope`, `.assumptions`, `.constraints`), `projects.ProjectTask`
  (`.project`, `.name`, `.node_type`, `.sequence`, `.status`), `projects.ProjectRisk`
  (`.project`, `.title`, `.status`, `.severity_band`), `core.Party`, `core.Document`,
  `core.Activity`. No `Requirement`/`ScopeItem`/`ChangeRequest` class exists anywhere
  (`ChangeRequest` is NOT a model — only the NavERP.md bullet text).

## 2. Models

All four: `TenantNumbered`, `unique_together = ("tenant", "number")`, money
`DecimalField(14, 2)` with `MinValueValidator(Decimal("0"))`, every derived figure a **property**.

### 2.1 `Requirement` [REQ-] — `models/ScopeRequirements/Requirements.py`

Choices:
* `REQUIREMENT_TYPE_CHOICES` (max_length=16): `functional`/Functional,
  `non_functional`/Non-Functional, `business`/Business, `technical`/Technical,
  `regulatory`/Regulatory, `interface`/Interface
* `ELICITATION_METHOD_CHOICES` (max_length=20): `interview`/Interview, `workshop`/Workshop,
  `survey`/Survey, `user_story`/User Story Mapping, `observation`/Observation,
  `document_analysis`/Document Analysis, `prototype`/Prototype, `brainstorm`/Brainstorming
* `PRIORITY_CHOICES` (max_length=12, MoSCoW): `must`/Must Have, `should`/Should Have,
  `could`/Could Have, `wont`/Won't Have
* `STATUS_CHOICES` (max_length=12): `draft`/Draft, `submitted`/Submitted, `approved`/Approved,
  `rejected`/Rejected, `implemented`/Implemented, `verified`/Verified, `deferred`/Deferred
* `VERIFICATION_METHOD_CHOICES` (max_length=12): `inspection`/Inspection, `analysis`/Analysis,
  `demonstration`/Demonstration, `test`/Test
* `STATUS_BANDS = {"draft": "muted", "submitted": "amber", "approved": "info",
  "rejected": "red", "implemented": "green", "verified": "green", "deferred": "slate"}` —
  the template's badge class map (documented constant, the `PROBABILITY_PCT` idiom)

Fields (declared):
`project` FK `"projects.Project"` CASCADE `related_name="requirements"` ·
`parent` FK `"self"` SET_NULL null+blank `related_name="children"` (epic → story hierarchy) ·
`wbs_node` FK `"projects.ProjectTask"` SET_NULL null+blank `related_name="requirements"`
(the traceability link: the WBS node that delivers it) · `title` CharField(255) ·
`description` TextField() · `requirement_type` CharField(16, default `functional`) ·
`elicitation_method` CharField(20, default `interview`) · `elicitation_note` TextField(blank) ·
`source_party` FK `"core.Party"` SET_NULL null+blank `related_name="requirements"` ·
`priority` CharField(12, default `must`) · `acceptance_criteria` TextField(blank) ·
`version` CharField(16, default `"1.0"`) ·
`verification_method` CharField(12, default `test`) ·
`status` CharField(12, default `draft`) — **off the form** ·
`owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="owned_requirements"` ·
`requested_by` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="requested_requirements"` ·
`rejection_reason` TextField(blank) — off the form ·
`approved_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="approved_requirements"` · `approved_at` DateTimeField(null+blank,
`editable=False`) · `verified_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="verified_requirements"` · `verified_at` DateTimeField(null+blank, `editable=False`) ·
`verification_note` TextField(blank) — off the form ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="req_created"`

Derived / Meta:
* `is_approved` = `status in ("approved", "implemented", "verified")`
* `is_verified` = `status == "verified"`
* `is_traced` = `wbs_node_id is not None`
* `is_open` = `status in ("draft", "submitted", "approved", "implemented")`
* `is_locked` = `status == "verified"`
* `badge_class` = `STATUS_BANDS.get(status, "slate")`
* `clean()`: `wbs_node.project_id == project_id`; `parent.project_id == project_id` —
  field-keyed `ValidationError`s
* `ordering = ["-created_at", "-id"]`; indexes `req_tnt_project_idx` ("tenant","project"),
  `req_tnt_status_idx` ("tenant","status"), `req_tnt_type_idx` ("tenant","requirement_type"),
  `req_tnt_priority_idx` ("tenant","priority"), `req_tnt_created_idx` ("tenant","-created_at")
* `__str__` = `f"{self.number} — {self.title}"`

### 2.2 `ScopeItem` [SCI-] — `models/ScopeRequirements/ScopeItems.py`

* `ITEM_TYPE_CHOICES` (max_length=12): `in_scope`/In Scope, `out_of_scope`/Out of Scope,
  `assumption`/Assumption, `constraint`/Constraint, `dependency`/Dependency
* `STATUS_CHOICES` (max_length=12): `open`/Open, `validated`/Validated, `realized`/Realized,
  `retired`/Retired, `violated`/Violated
* `IMPACT_AREA_CHOICES` (max_length=12): `schedule`/Schedule, `cost`/Cost, `quality`/Quality,
  `scope`/Scope, `resource`/Resource, `compliance`/Compliance
* `BOUNDARY_TYPES = {"in_scope", "out_of_scope"}` (documented constant — the two types the
  boundaries panel renders)

Fields: `project` FK CASCADE `related_name="scope_items"` ·
`requirement` FK `"projects.Requirement"` SET_NULL null+blank `related_name="scope_items"` ·
`item_type` CharField(12, default `assumption`) · `statement` CharField(255) ·
`description` TextField(blank) · `impact_area` CharField(12, default `scope`) ·
`status` CharField(12, default `open`) — **off the form** ·
`owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="owned_scope_items"` ·
`identified_date` DateField(default `timezone.localdate`) · `review_date` DateField(null+blank) ·
`outcome` TextField(blank) — off the form (verb-written) ·
`closed_at` DateTimeField(null+blank, `editable=False`) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="sci_created"`

Derived: `is_boundary` = `item_type in BOUNDARY_TYPES`; `is_open` =
`status in ("open", "validated")`; `is_locked` = `status in ("realized", "retired", "violated")`;
`is_review_overdue` = `review_date` set, `< timezone.localdate()`, and `is_open`.
Meta: `ordering = ["-created_at", "-id"]`; indexes `sci_tnt_project_idx`, `sci_tnt_type_idx`,
`sci_tnt_status_idx`, `sci_tnt_impact_idx` ("tenant","impact_area").
`clean()`: `requirement.project_id == project_id`. `__str__` = `f"{self.number} — {self.statement}"`.

### 2.3 `ScopeChangeRequest` [SCR-] — `models/ScopeRequirements/ScopeChangeRequests.py`

* `SOURCE_CHOICES` (max_length=12): `internal`/Internal, `client`/Client, `regulatory`/Regulatory,
  `vendor`/Vendor, `technical`/Technical
* `PRIORITY_CHOICES` (max_length=12): `low`/Low, `medium`/Medium, `high`/High, `critical`/Critical
* `QUALITY_IMPACT_CHOICES` (max_length=12): `none`/None, `low`/Low, `medium`/Medium, `high`/High
* `STATUS_CHOICES` (max_length=16): `draft`/Draft, `submitted`/Submitted, `under_review`/Under
  Review, `approved`/Approved, `rejected`/Rejected, `implemented`/Implemented
* `QUALITY_WEIGHT = {"none": 0, "low": 1, "medium": 2, "high": 3}` and the documented high-impact
  thresholds `HIGH_COST = Decimal("50000")`, `HIGH_SCHEDULE_DAYS = 10` (constant map, not config)

Fields: `project` FK CASCADE `related_name="scope_changes"` ·
`requirement` FK `"projects.Requirement"` SET_NULL null+blank `related_name="change_requests"` ·
`risk` FK `"projects.ProjectRisk"` SET_NULL null+blank `related_name="scope_changes"` (the 7.5
bridge — one line, no new risk machinery) · `title` CharField(255) · `description` TextField() ·
`justification` TextField(blank) · `source` CharField(12, default `internal`) ·
`priority` CharField(12, default `medium`) · `schedule_impact_days` PositiveIntegerField(null+blank)
· `cost_impact` DecimalField(14,2, default `Decimal("0")`, `MinValueValidator(0)`) ·
`quality_impact` CharField(12, default `none`) · `quality_note` TextField(blank) ·
`status` CharField(16, default `draft`) — **off the form** ·
`decision_note` TextField(blank) — off the form · `requested_by` FK AUTH_USER_MODEL SET_NULL
null+blank `related_name="requested_scope_changes"` · `decided_by` FK AUTH_USER_MODEL SET_NULL
null+blank `editable=False` `related_name="decided_scope_changes"` ·
`decided_at` DateTimeField(null+blank, `editable=False`) ·
`implemented_at` DateTimeField(null+blank, `editable=False`) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="scr_created"`

Derived: `impact_weight` = `QUALITY_WEIGHT.get(quality_impact, 0)` ·
`is_high_impact` = `cost_impact >= HIGH_COST or (schedule_impact_days or 0) >= HIGH_SCHEDULE_DAYS
or quality_impact == "high"` · `is_pending` = `status in ("draft","submitted","under_review")` ·
`is_approved` = `status in ("approved","implemented")` · `is_locked` = `status == "implemented"`.
Meta: `ordering = ["-created_at","-id"]`; indexes `scr_tnt_project_idx`, `scr_tnt_status_idx`,
`scr_tnt_priority_idx`, `scr_tnt_source_idx`.
`clean()`: `requirement.project_id == project_id`; `risk.project_id == project_id`.
`__str__` = `f"{self.number} — {self.title}"`.

### 2.4 `ScopeVerification` [SVR-] — `models/ScopeRequirements/ScopeVerifications.py`

* `METHOD_CHOICES` (max_length=16): `inspection`/Inspection, `test`/Test,
  `demonstration`/Demonstration, `analysis`/Analysis, `review`/Peer Review
* `RESULT_CHOICES` (max_length=12): `pass`/Pass, `conditional`/Conditional Pass, `fail`/Fail
* `ACCEPTANCE_STATUS_CHOICES` (max_length=12): `pending`/Pending, `accepted`/Accepted,
  `rejected`/Rejected, `waived`/Waived

Fields: `project` FK CASCADE `related_name="scope_verifications"` ·
`wbs_node` FK `"projects.ProjectTask"` SET_NULL null+blank `related_name="scope_verifications"` ·
`requirement` FK `"projects.Requirement"` SET_NULL null+blank
`related_name="scope_verifications"` · `deliverable` CharField(255) · `method` CharField(16) ·
`result` CharField(12, default `pass`) ·
`acceptance_status` CharField(12, default `pending`) — **off the form** ·
`inspected_by` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="inspected_scope_deliverables"` ·
`inspection_date` DateField(default `timezone.localdate`) · `findings` TextField(blank) ·
`decision_note` TextField(blank) — off the form ·
`accepted_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="accepted_scope_deliverables"` · `accepted_at` DateTimeField(null+blank,
`editable=False`) · `created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="svr_created"`

Derived: `is_decided` = `acceptance_status != "pending"`; `is_accepted` =
`acceptance_status in ("accepted", "waived")`; `is_locked` = `is_decided`.
Meta: `ordering = ["-created_at","-id"]`; indexes `svr_tnt_project_idx`, `svr_tnt_status_idx`
("tenant","acceptance_status"), `svr_tnt_result_idx`.
`clean()`: `wbs_node.project_id == project_id`; `requirement.project_id == project_id`.
`__str__` = `f"{self.number} — {self.deliverable}"`.

## 3. Forms (9)

| Form | Module | Shape |
|---|---|---|
| `RequirementForm` | `Requirements.py` | ModelForm; fields `project, parent, wbs_node, title, description, requirement_type, elicitation_method, elicitation_note, source_party, priority, acceptance_criteria, version, verification_method, owner, requested_by` (excludes `tenant, number, status, rejection_reason, approved_by, approved_at, verified_by, verified_at, verification_note, created_by`) |
| `RequirementRejectionForm` | `Requirements.py` | plain: `reason` CharField(required=True, Textarea) |
| `RequirementVerificationForm` | `Requirements.py` | plain: `note` CharField(required=False, Textarea) |
| `ScopeItemForm` | `ScopeItems.py` | ModelForm; fields `project, requirement, item_type, statement, description, impact_area, owner, identified_date, review_date` (excludes `tenant, number, status, outcome, closed_at, created_by`) |
| `ScopeItemOutcomeForm` | `ScopeItems.py` | plain: `outcome` CharField(required=True, Textarea) |
| `ScopeChangeForm` | `ScopeChangeRequests.py` | ModelForm; fields `project, requirement, risk, title, description, justification, source, priority, schedule_impact_days, cost_impact, quality_impact, quality_note, requested_by` (excludes `tenant, number, status, decision_note, decided_by, decided_at, implemented_at, created_by`) |
| `ChangeRejectionForm` | `ScopeChangeRequests.py` | plain: `decision_note` CharField(required=True, Textarea) |
| `ScopeVerificationForm` | `ScopeVerifications.py` | ModelForm; fields `project, wbs_node, requirement, deliverable, method, result, inspected_by, inspection_date, findings` (excludes `tenant, number, acceptance_status, decision_note, accepted_by, accepted_at, created_by`) |
| `VerificationDecisionForm` | `ScopeVerifications.py` | plain: `note` CharField(required=False, Textarea) |

Every ModelForm whose model `clean()` compares an FK's project mixes in **`TenantUniqueMixin`
first**, and re-checks every tenant-scoped FK with `_reject_foreign(self, cleaned, [...])`.

## 4. Views, routes & CONTEXT KEYS (the contract)

### 4.1 Requirement — `views/ScopeRequirements/Requirements.py`

Routes: `requirements/` `req_list` · `requirements/add/` `req_create` ·
`requirements/<int:pk>/` `req_detail` · `requirements/<int:pk>/edit/` `req_edit` ·
`requirements/<int:pk>/delete/` `req_delete` · `requirements/<int:pk>/submit/` `req_submit` ·
`requirements/<int:pk>/approve/` `req_approve` · `requirements/<int:pk>/reject/` `req_reject` ·
`requirements/<int:pk>/implement/` `req_implement` · `requirements/<int:pk>/verify/` `req_verify`.

`req_list` — qs `Requirement.objects.filter(tenant=request.tenant).select_related("project",
"parent", "wbs_node", "source_party", "owner", "requested_by")`.
`search_fields = ["number", "title", "description", "acceptance_criteria"]`.
`filters = [("project","project_id",True), ("requirement_type","requirement_type",False),
("priority","priority",False), ("status","status",False), ("owner","owner_id",True)]`.
Pre-scoped derived lenses (applied to the qs before `crud_list`):
* `?untraced=1` → `qs.filter(wbs_node__isnull=True)`
* `?pending=1` → `qs.filter(status__in=("draft", "submitted"))`
* `?verified=1` → `qs.filter(status="verified")`
`extra_context` (exact keys): `projects`, `type_choices`, `priority_choices`, `status_choices`,
`method_choices` (`Requirement.ELICITATION_METHOD_CHOICES`), `owners`, `requirements`
(`_helpers.requirements(request.tenant)`).

`req_create` — explicit view (stamps `created_by`; `?project=` seeds the `project` initial via
`as_db_int`); template `projects/scope/requirement/form.html` with `form`, `is_edit=False`.

`req_detail` — `obj` plus `child_requirements` (`obj.children.select_related("owner")
.order_by("number")`), `change_requests` (`obj.change_requests.select_related("requested_by")
.order_by("-created_at","-id")`), `verifications` (`obj.scope_verifications
.select_related("inspected_by").order_by("-inspection_date","-id")`),
`linked_scope_items` (`obj.scope_items.select_related("owner").order_by("item_type","number")`),
`rejection_form` (unbound `RequirementRejectionForm()`), `verification_form` (unbound
`RequirementVerificationForm()`).

`req_edit` — refuses a locked (`verified`) row (`messages.error` + redirect to detail); else
`crud_edit`. `req_delete` — `@require_POST`; refuses a locked row; else `crud_delete`.

Verbs (all `@login_required @require_POST`, `previous = obj.status` captured first, audit via
`changes={"verb","from","to"}`):
* `req_submit` — login. Only from `draft`/`rejected` (else error). `status = "submitted"`,
  clears `rejection_reason`. Audit `submit`.
* `req_approve` — **`@tenant_admin_required`**. Only from `submitted` (else error).
  `status = "approved"`, `approved_by = request.user`, `approved_at = timezone.now()`. Audit
  `approve`.
* `req_reject` — **`@tenant_admin_required`**. Only from `submitted` (else error). Binds
  `RequirementRejectionForm`; invalid → error + redirect. On valid: `rejection_reason` stored,
  `status = "rejected"`, `approved_by`/`approved_at` cleared. Audit `reject`.
* `req_implement` — login. Only from `approved` (else error). `status = "implemented"`. Audit
  `implement`.
* `req_verify` — **`@tenant_admin_required`**. Only from `implemented` (else error). Binds
  `RequirementVerificationForm` (optional note → `verification_note`); `status = "verified"`,
  `verified_by = request.user`, `verified_at = timezone.now()`. Audit `verify`.

### 4.2 ScopeItem — `views/ScopeRequirements/ScopeItems.py`

Routes: `scope-items/` `sci_list` · `scope-items/add/` `sci_create` · `scope-items/<int:pk>/`
`sci_detail` · `scope-items/<int:pk>/edit/` `sci_edit` · `scope-items/<int:pk>/delete/`
`sci_delete` · `scope-items/<int:pk>/validate/` `sci_validate` · `scope-items/<int:pk>/realize/`
`sci_realize` · `scope-items/<int:pk>/retire/` `sci_retire`.

`sci_list` — qs `.select_related("project", "requirement", "owner")`;
`search_fields = ["number", "statement", "description", "outcome"]`;
`filters = [("project","project_id",True), ("item_type","item_type",False),
("status","status",False), ("impact_area","impact_area",False), ("owner","owner_id",True)]`;
derived `?boundaries=1` → `qs.filter(item_type__in=("in_scope","out_of_scope"))`;
`?open=1` → `qs.filter(status__in=("open","validated"))`.
`extra_context`: `projects`, `type_choices`, `status_choices`, `impact_choices`, `owners`.
Detail: `obj` (+ `obj.requirement`), `outcome_form` (unbound `ScopeItemOutcomeForm()`).

`sci_create` stamps `created_by`; `?project=` seeds the initial. `sci_edit`/`sci_delete` refuse a
locked row. Verbs (login, `@require_POST`): `sci_validate` (open → `validated`), `sci_realize`
(open/validated → `realized`, stamps `closed_at`), `sci_retire` (open/validated → `retired`,
stamps `closed_at`) — each binds `ScopeItemOutcomeForm` and stores `outcome`; audit
`submit`/`realize`/`retire` (the `submit` action string is reused for the validate transition
because `AuditLog.action` is 10 chars and `validated` is 9 — the verb in `changes` is `validate`).

### 4.3 ScopeChangeRequest — `views/ScopeRequirements/ScopeChangeRequests.py`

Routes: `scope-changes/` `scr_list` · `scope-changes/add/` `scr_create` ·
`scope-changes/<int:pk>/` `scr_detail` · `scope-changes/<int:pk>/edit/` `scr_edit` ·
`scope-changes/<int:pk>/delete/` `scr_delete` · `scope-changes/<int:pk>/submit/` `scr_submit` ·
`scope-changes/<int:pk>/review/` `scr_review` · `scope-changes/<int:pk>/approve/` `scr_approve` ·
`scope-changes/<int:pk>/reject/` `scr_reject` · `scope-changes/<int:pk>/implement/`
`scr_implement`.

`scr_list` — qs `.select_related("project", "requirement", "risk", "requested_by", "decided_by")`;
`search_fields = ["number", "title", "description", "justification"]`;
`filters = [("project","project_id",True), ("status","status",False), ("priority","priority",False),
("source","source",False), ("requirement","requirement_id",True)]`;
derived `?pending=1` → `qs.filter(status__in=("draft","submitted","under_review"))`;
`?high_impact=1` → `qs.filter(Q(cost_impact__gte=HIGH_COST) |
Q(schedule_impact_days__gte=HIGH_SCHEDULE_DAYS) | Q(quality_impact="high"))`.
`extra_context`: `projects`, `status_choices`, `priority_choices`, `source_choices`,
`requirements`, `owners`.
Detail: `obj`, `decision_form` (unbound `ChangeRejectionForm()`).

`scr_create` stamps `created_by` and `requested_by` (default `request.user`); `?project=` seeds
the initial. `scr_edit`/`scr_delete` refuse a locked (`implemented`) row. Verbs:
* `scr_submit` — login. From `draft` (else error). `status = "submitted"`. Audit `submit`.
* `scr_review` — **`@tenant_admin_required`**. From `submitted` (else error).
  `status = "under_review"`. Audit `review`.
* `scr_approve` — **`@tenant_admin_required`**. From `submitted`/`under_review` (else error).
  `status = "approved"`, `decided_by`/`decided_at`. Audit `approve`.
* `scr_reject` — **`@tenant_admin_required`**. From `submitted`/`under_review` (else error).
  Binds `ChangeRejectionForm`; `decision_note`, `status = "rejected"`, `decided_by`/`decided_at`.
  Audit `reject`.
* `scr_implement` — login. From `approved` (else error). `status = "implemented"`,
  `implemented_at`. Audit `implement`.

### 4.4 ScopeVerification — `views/ScopeRequirements/ScopeVerifications.py`

Routes: `scope-verifications/` `svr_list` · `scope-verifications/add/` `svr_create` ·
`scope-verifications/<int:pk>/` `svr_detail` · `scope-verifications/<int:pk>/edit/` `svr_edit` ·
`scope-verifications/<int:pk>/delete/` `svr_delete` · `scope-verifications/<int:pk>/accept/`
`svr_accept` · `scope-verifications/<int:pk>/reject/` `svr_reject` ·
`scope-verifications/<int:pk>/waive/` `svr_waive`.

`svr_list` — qs `.select_related("project", "wbs_node", "requirement", "inspected_by",
"accepted_by")`; `search_fields = ["number", "deliverable", "findings", "decision_note"]`;
`filters = [("project","project_id",True), ("acceptance_status","acceptance_status",False),
("result","result",False), ("method","method",False), ("requirement","requirement_id",True)]`;
derived `?pending=1` → `qs.filter(acceptance_status="pending")`.
`extra_context`: `projects`, `method_choices`, `result_choices`, `status_choices`,
`requirements`, `owners`.
Detail: `obj`, `decision_form` (unbound `VerificationDecisionForm()`).

`svr_create` stamps `created_by` and `inspected_by` (default `request.user`); `?project=` seeds the
initial. `svr_edit`/`svr_delete` refuse a locked row. Verbs:
* `svr_accept` — login. From `pending` (else error). Binds `VerificationDecisionForm` (optional
  note → `decision_note`); `acceptance_status = "accepted"`, `accepted_by = request.user`,
  `accepted_at = timezone.now()`. Audit `accept`.
* `svr_reject` — **`@tenant_admin_required`**. From `pending` (else error). Binds
  `VerificationDecisionForm` and requires a non-empty note (`messages.error` + redirect when
  blank); `acceptance_status = "rejected"`, `decision_note` stored, `accepted_by`/`accepted_at`
  stamped. Audit `reject`.
* `svr_waive` — **`@tenant_admin_required`**. From `pending` (else error). `acceptance_status =
  "waived"`, `accepted_by`/`accepted_at` stamped. Audit `waive`.

### 4.5 `scope_matrix` — `views/ScopeRequirements/ScopeMatrix.py`, route `scope-matrix/`

Template `projects/scope/scope_matrix.html`, **GET-only**. Context (exact keys):
* `projects` — tenant `Project` queryset ordered by `name`; `project` — the selected `Project`
  from `?project=` (`as_db_int`-guarded, `filter(tenant=request.tenant)`), else `None`
* `work_packages` — the selected project's `ProjectTask` rows with `node_type="work_package"`
  ordered by `sequence, id`, capped at 12 columns (the matrix's columns); `wp_total`
* `matrix_rows` — per requirement `{"requirement", "cells": [bool per work package], "traced",
  "verified_count", "verification_count"}` where `traced` = `requirement.wbs_node_id` is set;
  requirements scoped to the selected project (or all the tenant's when none), ordered `-created_at`
* `coverage` — `{"total", "traced", "untraced", "verified", "coverage_pct"}` (`coverage_pct` =
  1-dp percentage of requirements with a `wbs_node`; 0-safe)
* `untraced` — requirements with no `wbs_node`, cap 25
* `unverified` — requirements with `status` in `("approved", "implemented")`, cap 25
* `creep_rows` — per month over the scoped change requests whose `status` is `approved` or
  `implemented`: `{"period" (YYYY-MM), "label" (e.g. "Sep 2026"), "count", "cost_total",
  "schedule_days", "bar_pct"}` ordered by period ascending; `bar_pct` = `cost_total` as a
  percentage of the max row's `cost_total` (0-safe); `creep_max`
* `creep` — `{"count", "cost_total", "schedule_days", "high_impact_count"}` over the same rows
* `type_rows`, `priority_rows` — lists of `{"label", "count"}` for the summary strip
* `scope_summary` — `{"items", "boundaries", "constraints", "assumptions", "open_items",
  "overdue_items"}` over the tenant's `ScopeItem` rows

Rendering: a CSS-grid matrix table (`✓` / `—` cells), CSS bar rows
(`style="width: {{ row.bar_pct }}%"`), badges. **No chart library** (7.16 owns charts), **no
stored snapshot**.

## 5. Templates

* `requirement/{list,detail,form}.html`, `scopeitem/{list,detail,form}.html`,
  `scopechange/{list,detail,form}.html`, `scopeverification/{list,detail,form}.html`, plus
  `scope_matrix.html` at `templates/projects/scope/`.
* Every list: `.page-header` + breadcrumb, GET filter form reflecting `request.GET` (string filters
  `{% if request.GET.status == value %}selected{% endif %}`; FK filters
  `{% if request.GET.project == p.pk|stringformat:"d" %}selected{% endif %}`), `.table-wrap`/`.table`
  with an Actions column (eye → detail, pencil → edit, delete POST form + `confirm()` +
  `{% csrf_token %}`), `{% include "partials/pagination.html" %}`, `.empty-state`.
* Badges: colour-named only; every block ends
  `{% else %}{{ obj.get_<field>_display }}{% endif %}`.
* **No nullable FK inside a `|default:` filter argument** (L10) — `owner`, `requested_by`,
  `inspected_by`, `source_party`, `accepted_by` render via `{% if fk %}…{% else %}—{% endif %}`.
* **Multi-line notes use `{% comment %} … {% endcomment %}`** — a multi-line `{# … #}` leaks as
  visible text (L2).
* Verb buttons are POST forms with `{% csrf_token %}`, gated by status/role in the template the same
  way the view gates them.

## 6. Wire-up (Integrate only — single writer, surgical edits)

* `apps/projects/{models,forms,views,urls}/ScopeRequirements/__init__.py` — **empty** sub-package
  `__init__.py` files (4 files).
* Top-level `__init__.py` re-export blocks `# --- 7.7 Scope & Requirements Management` in all four
  layers: models (4), forms (9), views (4 CRUD sets + 16 verbs + `scope_matrix`), urls (5
  `urlpatterns` imports + concat, in the order Requirements, ScopeItems, ScopeChangeRequests,
  ScopeVerifications, ScopeMatrix).
* `apps/projects/views/_helpers.py` — add `requirements(tenant)`.
* `apps/projects/admin.py` — 4 registrations (`list_display` led by `number`,
  `list_select_related` for every rendered FK, `approved_at`/`verified_at`/`decided_at`/
  `implemented_at`/`accepted_at`/`closed_at` readonly).
* `apps/projects/management/commands/seed_projects.py` — a `_scope` block with its own guard
  (`Requirement.objects.filter(tenant=tenant).exists()`), called per tenant after `_risk`;
  `--flush` deletes children-first `ScopeVerification, ScopeChangeRequest, ScopeItem, Requirement`.
* `apps/core/navigation.py` — one `LIVE_LINKS["7.7"]` block immediately after the `"7.5"` block
  (a concurrent session owns `"7.6"`): `Requirements Elicitation` → `projects:req_list`;
  `Requirements Documentation & Traceability` → `projects:scope_matrix`;
  `Scope Definition & Boundaries` → `projects:sci_list`; `Change Request Management` →
  `projects:scr_list`; `Scope Verification & Control` → `projects:svr_list`; extra leaf
  `Requirement Approval Queue` → `projects:req_list?status=submitted`.
* `templates/projects/overview.html` — 7.7 quick links + counts;
  `apps/projects/views/ProjectInitiation/Overview.py` — the matching count context keys.
* `config/settings.py` / `config/urls.py` — **not touched** (app already registered).
* Then: `makemigrations projects --dry-run` (read every model it names; abort if it names anything
  outside 7.7's four) → generate → `migrate` → `seed_projects` ×2 → `manage.py check`.

## 7. Sidebar keys (verbatim from NavERP.md — must match character-for-character)

1. `Requirements Elicitation`
2. `Requirements Documentation & Traceability`
3. `Scope Definition & Boundaries`
4. `Change Request Management`
5. `Scope Verification & Control`

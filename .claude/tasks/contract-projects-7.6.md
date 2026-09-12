# CONTRACT — NavERP 7.6 Quality Management (`projects`)

Frozen 2026-09-11, `BASE = a6e2b0d3c0ec25ead9a878512a85dff418edf65d`.
Source of truth for the build: `.claude/tasks/todo.md` §7.6 + `.claude/tasks/research-projects-7.6.md`.
**An unpinned name renders blank at 200 (L7). Nothing in this file is optional.**

> **Concurrency note (read before editing anything).** A peer session is building **7.7
> `ScopeRequirements`** in this same checkout. Its `# --- 7.7` blocks already sit in the four
> top-level `__init__.py` files and its migration `0007_requirement_scopechangerequest_scopeitem_and_more.py`
> is on disk (untracked, **not yet applied**). Therefore: **7.6's re-export block is inserted BETWEEN
> the `# --- 7.5` and `# --- 7.7` blocks**, and **7.6's migration is generated LAST** (L43 — concede
> the lower number). Every shared-file touch is a surgical `Edit` with a re-read anchor; never `Write`.

## 0. Identity

| Thing | Value |
|---|---|
| Module / sub-module | 7 / 7.6 Quality Management |
| Backend sub-package | `apps/projects/{models,forms,views,urls}/QualityManagement/` |
| Template root | `templates/projects/quality/` |
| Migration | generated last, `0007` if still free else the next free leaf — **never reserved** |
| Models | `QualityPlan` [QPL-], `QualityReview` [QRV-], `DeliverableInspection` [QCI-], `QualityDefect` [QDF-] |
| Entity file names | `QualityPlans.py`, `QualityReviews.py`, `DeliverableInspections.py`, `QualityDefects.py` (same name in all four layers) |
| Extra view+url modules | `QualityImprovement.py`, `QualityAcceptance.py` (computed pages, no model) |
| Entity template folders | `qualityplan/`, `qualityreview/`, `deliverableinspection/`, `qualitydefect/` |
| Computed templates | `templates/projects/quality/quality_improvement.html`, `quality_acceptance.html` |
| Tests | `test_quality_{models,forms,views,security}.py`; test names `test_quality_*`, helpers `_quality_*` |

**URL first segments (all disjoint literals — no converter in any first component):**
`quality-plans/`, `quality-reviews/`, `inspections/`, `defects/`, `quality-improvement/`,
`quality-acceptance/`. Existing segments they must not collide with: `""`, `project-requests/`,
`projects/`, `stakeholders/`, `kickoffs/`, `tasks/`, `dependencies/`, `milestones/`, `baselines/`,
`resource-profiles/`, `allocations/`, `time-entries/`, `capacity-demand/`, `budgetlines/`,
`revisions/`, `controlaccounts/`, `expenses/`, `risks/`, `responses/`, `issues/`, `escalations/`,
`risk-analysis/`, `risk-monitoring/`, and the peer 7.7's `requirements/`, `scope-items/`,
`scope-changes/`, `scope-verifications/`, `scope-matrix/`.

## 1. Shared toolkit facts (verified, do not re-derive)

* `apps/projects/models/_base.py` → `TenantOwned`, `TenantNumbered` (`NUMBER_PREFIX`, per-tenant
  `number` in `save()` with a collision retry), `q2()`, `MAX_Q2`, `ZERO`, and re-exported `models`,
  `settings`, `timezone`, `Decimal`, `MinValueValidator`, `MaxValueValidator`, `Q`, `F`, `Sum`,
  `Count`, `next_number`, `IntegrityError`.
* `apps/projects/forms/_common.py` → `forms`, `ValidationError`, `TenantModelForm`,
  `TenantUniqueMixin`, `_reject_foreign(form, cleaned, names)`.
  **`TenantUniqueMixin` FIRST, then `TenantModelForm`** on every form whose model `clean()` compares
  a chosen FK's project — the CRUD helpers stamp the real tenant only AFTER `is_valid()`.
* `apps/projects/views/_common.py` → `messages`, `login_required`, `get_object_or_404`, `redirect`,
  `render`, `require_POST`, `crud_create`, `crud_delete`, `crud_detail`, `crud_edit`, `crud_list`,
  `tenant_admin_required`, `write_audit_log`.
* `apps/core/crud.py` → `crud_list(request, qs, template, *, search_fields=(), filters=(),
  extra_context=None, per_page=15)` renders `object_list`/`page_obj`/`q`; `filters` are
  `(get_param, orm_lookup, is_int)` **field lookups only** — a Python *property* can never be a
  filter, so every derived lens (`?review_due=`, `?overdue=`, `?kind=`) is **pre-scoped in the view**
  before `crud_list`. `as_db_int(value)` guards every int GET. `crud_edit` renders
  `form`/`obj`/`is_edit`; `crud_delete` is self-defending (POST-only) but views still carry
  `@require_POST`.
* `apps/projects/views/_helpers.py` — **already has `owners(tenant)` (7.5) and `clients(tenant)`**.
  7.6 **adds nothing**; reuse both.
* `write_audit_log(user, obj, action, changes=None, tenant=None)`; **`AuditLog.action` is
  `varchar(10)`** — allowed verbs: `create`, `update`, `delete`, `accept`, `reject`, `resolve`,
  `close`. The verb + transition live in `changes` (`{"verb":…, "from":…, "to":…}`). Capture
  `previous = obj.status` **before** mutating.
* Badge classes that exist in `static/css/theme.css`: **`badge-green`, `badge-amber`, `badge-red`,
  `badge-info`, `badge-muted`, `badge-slate`** only. Stat-icon colours: `blue`, `green`, `orange`,
  `purple`, `red`, `slate`. There is **no** `-success`/`-warning`/`-danger` (L33).
* `_safe_reverse` (`apps/core/navigation.py`) supports both `?query` and `#fragment` suffixes.
* Verified spine FKs: `projects.Project`, `projects.ProjectTask` (`node_type="deliverable"` is the
  inspected node), `projects.ProjectMilestone`, `projects.ProjectRisk`, `projects.ProjectIssue`,
  `core.Party`. **No `QualityPlan`/`QualityReview`/`DeliverableInspection`/`QualityDefect` class
  exists anywhere.** `scm` 4.9 owns `NonConformance`/`CapaAction`/`QualityAudit`/`QualityInspection`;
  `inventory` owns `QcChecklist`/`DefectReport`.

## 2. Models

All four: `TenantNumbered`, `unique_together = ("tenant", "number")`, **no money column (Ruling 7 —
no `DecimalField` at all)**, every pass rate / punch-list count / maturity figure a **derived
property or computed view, never stored**.

### 2.1 `QualityPlan` [QPL-] — `models/QualityManagement/QualityPlans.py`

Choices:
* `VERIFICATION_METHOD_CHOICES` (16): `inspection`/Inspection, `testing`/Testing,
  `demonstration`/Demonstration, `review`/Review, `analysis`/Analysis, `audit`/Audit
* `STATUS_CHOICES` (16): `draft`/Draft, `active`/Active, `superseded`/Superseded, `closed`/Closed

Fields: `project` FK `"projects.Project"` CASCADE `related_name="quality_plans"` ·
`wbs_node` FK `"projects.ProjectTask"` SET_NULL null+blank `related_name="quality_plans"` ·
`source_risk` FK `"projects.ProjectRisk"` SET_NULL null+blank `related_name="quality_plans"` ·
`title` CharField(255) · `description` TextField(blank) · `acceptance_criteria` TextField()
(**required**) · `verification_method` CharField(16, default `inspection`) ·
`standard_reference` CharField(120, blank) — free text, a standards master is 7.19's (Ruling 3) ·
`regulatory_requirement` TextField(blank) · `owner` FK AUTH_USER_MODEL SET_NULL null+blank
`related_name="owned_quality_plans"` · `status` CharField(16, default `draft`) — **off the form** ·
`planned_review_date` DateField(null+blank) · `approved_by` FK AUTH_USER_MODEL SET_NULL null+blank
`editable=False` `related_name="approved_quality_plans"` · `approved_at` DateTimeField(null+blank,
`editable=False`) · `created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="qpl_created"`

Derived / Meta: `is_review_overdue` = `planned_review_date` set, `< timezone.localdate()`, `status
in ("draft","active")` · `is_locked` = `status in ("superseded","closed")` · `clean()`: same-project
guards on `wbs_node` and `source_risk`, field-keyed `ValidationError`s ·
`ordering = ["-created_at","-id"]`; indexes `qpl_tnt_project_idx` ("tenant","project"),
`qpl_tnt_status_idx` ("tenant","status"), `qpl_tnt_wbs_idx` ("tenant","wbs_node"),
`qpl_tnt_created_idx` ("tenant","-created_at") · `__str__` = `f"{self.number} — {self.title}"`

Verbs: `qpl_approve` (login; `draft` → `active`, stamps `approved_by`/`approved_at`, audit
`update`); `qpl_supersede` (**`@tenant_admin_required`**; `active` → `superseded`, audit `update`).
Locked rows refuse edit/delete.

### 2.2 `QualityReview` [QRV-] — `models/QualityManagement/QualityReviews.py`

Covers bullets **2 (QA)** and **4 (Continuous Improvement)**, discriminated by `review_type`.

Choices:
* `REVIEW_TYPE_CHOICES` (24): `methodology_review`/Methodology Review, `compliance_check`/Compliance
  Check, `gate_review`/Gate Review, `kaizen_event`/Kaizen Event, `retrospective`/Retrospective,
  `maturity_assessment`/Maturity Assessment
* `STATUS_CHOICES` (12): `planned`/Planned, `in_progress`/In Progress, `reported`/Reported,
  `closed`/Closed, `cancelled`/Cancelled
* `IMPROVEMENT_STATUS_CHOICES` (12): `n_a`/N/A, `planned`/Planned, `in_progress`/In Progress,
  `done`/Done

Fields: `project` FK CASCADE `related_name="quality_reviews"` · `wbs_node` FK ProjectTask SET_NULL
null+blank `related_name="quality_reviews"` · `quality_plan` FK `"projects.QualityPlan"` SET_NULL
null+blank `related_name="reviews"` · `title` CharField(255) · `scope` TextField(blank) ·
`review_type` CharField(24, default `methodology_review`) · `checklist` TextField(blank) — a
reusable checklist library is 7.19's · `findings` TextField(blank) · `reviewer` FK AUTH_USER_MODEL
SET_NULL null+blank `related_name="conducted_quality_reviews"` · `review_date` DateField(default
`timezone.localdate`) · `status` CharField(12, default `planned`) — **off the form** ·
`maturity_score` PositiveSmallIntegerField(null+blank, validators 1–5) · `improvement_action`
TextField(blank) · `improvement_owner` FK AUTH_USER_MODEL SET_NULL null+blank
`related_name="owned_quality_reviews"` · `improvement_due_date` DateField(null+blank) ·
`improvement_status` CharField(12, default `n_a`) · `closed_at` DateTimeField(null+blank,
`editable=False`) · `created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="qrv_created"`

Derived / Meta: `is_improvement_overdue` = `improvement_due_date` set, `< today`,
`improvement_status in ("planned","in_progress")` · `is_locked` = `status in ("closed","cancelled")`
· `clean()`: same-project
guards on `wbs_node`, `quality_plan` · `ordering = ["-review_date","-id"]`; indexes
`qrv_tnt_project_idx`, `qrv_tnt_type_idx` ("tenant","review_type"), `qrv_tnt_status_idx`,
`qrv_tnt_imp_idx` ("tenant","improvement_status"), `qrv_tnt_date_idx` ("tenant","-review_date") ·
`__str__` = `f"{self.number} — {self.title}"`

Verbs: `qrv_report` (login; `in_progress` → `reported`, audit `update`); `qrv_close` (login;
`reported` → `closed`, stamps `closed_at`, audit `close`). Locked rows refuse edit/delete.

### 2.3 `DeliverableInspection` [QCI-] — `models/QualityManagement/DeliverableInspections.py`

Covers bullet **3 (QC execution + result)** and bullet **5 (acceptance decision + customer
validation + document link)**. Named `DeliverableInspection` because `QualityInspection` is scm 4.9's.

Choices:
* `INSPECTION_TYPE_CHOICES` (16): `review`/Review, `testing`/Testing, `demonstration`/Demonstration,
  `walkthrough`/Walkthrough, `acceptance`/Acceptance
* `RESULT_CHOICES` (14): `pending`/Pending, `pass`/Pass, `fail`/Fail, `conditional`/Conditional,
  `not_applicable`/Not Applicable
* `USAGE_DECISION_CHOICES` (24): `pending`/Pending, `accept`/Accept,
  `accept_with_deviation`/Accept with Deviation, `reject`/Reject, `rework`/Rework
* `STATUS_CHOICES` (12): `planned`/Planned, `in_progress`/In Progress, `passed`/Passed,
  `failed`/Failed, `on_hold`/On Hold, `cancelled`/Cancelled

Fields: `project` FK CASCADE `related_name="quality_inspections"` · `wbs_node` FK ProjectTask
SET_NULL null+blank `related_name="quality_inspections"` · `quality_plan` FK QualityPlan SET_NULL
null+blank `related_name="inspections"` · `milestone` FK `"projects.ProjectMilestone"` SET_NULL
null+blank `related_name="quality_inspections"` (7.2's gate, not re-declared — Ruling 5) · `title`
CharField(255) · `description` TextField(blank) · `inspection_type` CharField(16, default `review`) ·
`planned_date` DateField(null+blank) · `inspected_date` DateField(null+blank) · `inspector` FK
AUTH_USER_MODEL SET_NULL null+blank `related_name="conducted_inspections"` · `result` CharField(14,
default `pending`) — 14, not 12: fields.E009 needs max_length ≥ the longest choice
(`not_applicable`), matching scm 4.9's `QualityInspection.result` · `usage_decision` CharField(24,
default `pending`) · `findings` TextField(blank) ·
`accepted_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False`
`related_name="accepted_inspections"` · `accepted_by_party` FK `"core.Party"` SET_NULL null+blank
`related_name="accepted_inspections"` · `accepted_at` DateTimeField(null+blank, `editable=False`) ·
`acceptance_note` TextField(blank) · `status` CharField(12, default `planned`) — **off the form** ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="qci_created"`

Derived / Meta: `is_overdue` = `planned_date` set, `< today`, `inspected_date` is None, `status in
("planned","in_progress")` · `is_locked` = `status in ("passed","failed","cancelled")` or
`usage_decision != "pending"` · `defect_count` = `self.defects.count()` · `is_acceptance` =
`inspection_type == "acceptance"` · `clean()`: same-project guards on `wbs_node`, `quality_plan`,
`milestone` · `ordering = ["-created_at","-id"]`; indexes `qci_tnt_project_idx`,
`qci_tnt_status_idx`, `qci_tnt_result_idx` ("tenant","result"), `qci_tnt_decision_idx`
("tenant","usage_decision"), `qci_tnt_wbs_idx` · `__str__` = `f"{self.number} — {self.title}"`

Verbs: `qci_record` (login; sets `result` + `inspected_date` + `status`, audit `update`);
`qci_accept` (login; binds `InspectionAcceptanceForm`; `usage_decision` ∈ {`accept`,
`accept_with_deviation`}, `accepted_by=request.user`, `accepted_by_party`, `accepted_at=now()`,
`status="passed"`, `acceptance_note`, audit `accept`); `qci_reject` (login; `usage_decision="reject"`,
`status="failed"`, audit `reject`). Locked rows refuse edit/delete.

### 2.4 `QualityDefect` [QDF-] — `models/QualityManagement/QualityDefects.py`

Bullet **3's defect tracking** + bullet **5's punch list**. NOT a second NCR (scm 4.9) and NOT a
second issue log (7.5) — it LINKS to `ProjectIssue` by FK (Ruling 2).

Choices:
* `DEFECT_CATEGORY_CHOICES` (16): `functional`/Functional, `performance`/Performance,
  `documentation`/Documentation, `compliance`/Compliance, `dimensional`/Dimensional,
  `workmanship`/Workmanship, `usability`/Usability, `other`/Other
* `SEVERITY_CHOICES` (12): `critical`/Critical, `major`/Major, `minor`/Minor, `observation`/Observation
* `DISPOSITION_CHOICES` (16): `open`/Open, `rework`/Rework, `repair`/Repair, `resubmit`/Resubmit,
  `accept_as_is`/Accept As Is, `reject`/Reject, `deferred`/Deferred
* `STATUS_CHOICES` (12): `open`/Open, `in_progress`/In Progress, `resolved`/Resolved,
  `closed`/Closed, `cancelled`/Cancelled

Fields: `project` FK CASCADE `related_name="quality_defects"` · `wbs_node` FK ProjectTask SET_NULL
null+blank `related_name="quality_defects"` · `quality_plan` FK QualityPlan SET_NULL null+blank
`related_name="defects"` · `inspection` FK `"projects.DeliverableInspection"` SET_NULL null+blank
`related_name="defects"` · `project_issue` FK `"projects.ProjectIssue"` SET_NULL null+blank
`related_name="quality_defects"` (**the bridge**) · `title` CharField(255) · `description`
TextField() · `defect_category` CharField(16, default `other`) · `severity` CharField(12, default
`minor`) — 12, not 8: fields.E009 needs max_length ≥ the longest choice (`observation`), matching
scm 4.9's `NonConformance.severity` · `disposition` CharField(16, default `open`) · `status`
CharField(12, default `open`) —
**off the form** · `owner` FK AUTH_USER_MODEL SET_NULL null+blank `related_name="owned_quality_defects"`
· `identified_date` DateField(default `timezone.localdate`) · `due_date` DateField(null+blank) ·
`root_cause` TextField(blank) · `resolution_note` TextField(blank) · `resolved_by` FK
AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="resolved_quality_defects"` ·
`resolved_at` DateTimeField(null+blank, `editable=False`) · `lessons_learned` TextField(blank) ·
`created_by` FK AUTH_USER_MODEL SET_NULL null+blank `editable=False` `related_name="qdf_created"`

Derived / Meta: `is_overdue` = `due_date` set, `< today`, `status in ("open","in_progress")` ·
`age_days` · `is_open` = `status in ("open","in_progress")` · `is_locked` = `status in
("resolved","closed","cancelled")` (cancelled locks like the QRV/QCI siblings) · `clean()`: same-project guards on `wbs_node`, `quality_plan`, `inspection` ·
`ordering = ["-created_at","-id"]`; indexes `qdf_tnt_project_idx`, `qdf_tnt_status_idx`,
`qdf_tnt_severity_idx`, `qdf_tnt_disp_idx` ("tenant","disposition"), `qdf_tnt_created_idx` ·
`__str__` = `f"{self.number} — {self.title}"`

Verbs: `qdf_resolve` (login; binds `DefectResolutionForm`; sets `root_cause`, `resolution_note`,
`resolved_by=request.user`, `resolved_at=now()`, `status="resolved"`, audit `resolve`);
`qdf_close` (login; `resolved` → `closed`, audit `close`); `qdf_raise_issue` (login; creates a
`projects.ProjectIssue` — `project`, `wbs_node`, `title`, `description`, `severity` **mapped
`critical→critical` / `major→high` / `minor→medium` / `observation→low`**, `owner`,
`raised_by=request.user`, `identified_date=timezone.localdate()`, `created_by=request.user` — sets
`project_issue`, audits `create` on the issue and `update` on the defect; message names both
numbers). Refused when `project_issue` is already set. Locked rows refuse edit/delete.

## 3. Forms (6)

| Form | Module | `Meta.fields` / exclusion |
|---|---|---|
| `QualityPlanForm` | `QualityPlans.py` | fields: `project, wbs_node, source_risk, title, description, acceptance_criteria, verification_method, standard_reference, regulatory_requirement, owner, planned_review_date` (excludes `tenant, number, status, approved_by, approved_at, created_by`) |
| `QualityReviewForm` | `QualityReviews.py` | fields: `project, wbs_node, quality_plan, title, scope, review_type, checklist, findings, reviewer, review_date, maturity_score, improvement_action, improvement_owner, improvement_due_date, improvement_status` (excludes `tenant, number, status, closed_at, created_by`) |
| `DeliverableInspectionForm` | `DeliverableInspections.py` | fields: `project, wbs_node, quality_plan, milestone, title, description, inspection_type, planned_date, inspected_date, inspector, result, findings` (excludes `tenant, number, usage_decision, accepted_by, accepted_by_party, accepted_at, acceptance_note, status, created_by`) |
| `InspectionAcceptanceForm` | `DeliverableInspections.py` | plain `forms.Form`: `usage_decision` ChoiceField ∈ {`accept`,`accept_with_deviation`}, `accepted_by_party` ModelChoiceField(queryset=`clients(tenant)`, required=False), `acceptance_note` CharField(required=False, Textarea) |
| `QualityDefectForm` | `QualityDefects.py` | fields: `project, wbs_node, quality_plan, inspection, title, description, defect_category, severity, disposition, owner, identified_date, due_date, lessons_learned` (excludes `tenant, number, project_issue, status, root_cause, resolution_note, resolved_by, resolved_at, created_by`) |
| `DefectResolutionForm` | `QualityDefects.py` | plain `forms.Form`: `root_cause` CharField(required=False, Textarea), `resolution_note` CharField(required=True, Textarea) |

Every ModelForm whose model `clean()` compares an FK's project mixes in **`TenantUniqueMixin`
first**. Every tenant-scoped FK is re-checked with `_reject_foreign(self, cleaned, [...])` — never
`core.Party` (a `Party` has no `tenant` column; scope it in the view/form queryset instead).

## 4. Views, routes & CONTEXT KEYS (the contract)

### 4.1 QualityPlan — `views/QualityManagement/QualityPlans.py`

Routes: `quality-plans/` `qpl_list` · `quality-plans/add/` `qpl_create` ·
`quality-plans/<int:pk>/` `qpl_detail` · `quality-plans/<int:pk>/edit/` `qpl_edit` ·
`quality-plans/<int:pk>/delete/` `qpl_delete` · `quality-plans/<int:pk>/approve/` `qpl_approve` ·
`quality-plans/<int:pk>/supersede/` `qpl_supersede`.

`qpl_list` — qs `.filter(tenant=request.tenant).select_related("project","wbs_node","source_risk",
"owner","approved_by")`; `search_fields = ["number","title","description","acceptance_criteria",
"standard_reference"]`; `filters = [("project","project_id",True), ("status","status",False),
("verification_method","verification_method",False), ("owner","owner_id",True)]`; pre-scoped
`?review_due=1` / `?overdue=1` → `Q(planned_review_date__lt=timezone.localdate(),
status__in=("draft","active"))`.
`extra_context`: `projects`, `status_choices`, `verification_method_choices`, `owners`.
`qpl_detail` context: `obj`, `linked_reviews` (`obj.reviews.select_related("reviewer")`),
`linked_inspections` (`obj.inspections.select_related("inspector","milestone")`), `linked_defects`
(`obj.defects.select_related("owner")`).
`qpl_create` stamps `created_by`; `?project=` seeds the `project` initial via `as_db_int`.
`qpl_edit`/`qpl_delete` refuse a locked row.

### 4.2 QualityReview — `views/QualityManagement/QualityReviews.py`

Routes: `quality-reviews/` `qrv_list` · `quality-reviews/add/` `qrv_create` ·
`quality-reviews/<int:pk>/` `qrv_detail` · `quality-reviews/<int:pk>/edit/` `qrv_edit` ·
`quality-reviews/<int:pk>/delete/` `qrv_delete` · `quality-reviews/<int:pk>/report/` `qrv_report` ·
`quality-reviews/<int:pk>/close/` `qrv_close`.

`qrv_list` — qs `.select_related("project","wbs_node","quality_plan","reviewer",
"improvement_owner")`; `search_fields = ["number","title","scope","findings","improvement_action"]`;
`filters = [("project","project_id",True), ("review_type","review_type",False),
("status","status",False), ("improvement_status","improvement_status",False),
("reviewer","reviewer_id",True)]`; pre-scoped lenses `?kind=assurance` →
`Q(review_type__in=("methodology_review","compliance_check","gate_review"))`; `?kind=improvement` →
`Q(review_type__in=("kaizen_event","retrospective","maturity_assessment"))`; `?overdue=1` →
`Q(improvement_due_date__lt=today, improvement_status__in=("planned","in_progress"))`.
`extra_context`: `projects`, `review_type_choices`, `status_choices`,
`improvement_status_choices`, `owners`. Detail: `obj` (the improvement panel reads off `obj`).

### 4.3 DeliverableInspection — `views/QualityManagement/DeliverableInspections.py`

Routes: `inspections/` `qci_list` · `inspections/add/` `qci_create` · `inspections/<int:pk>/`
`qci_detail` · `inspections/<int:pk>/edit/` `qci_edit` · `inspections/<int:pk>/delete/`
`qci_delete` · `inspections/<int:pk>/record/` `qci_record` · `inspections/<int:pk>/accept/`
`qci_accept` · `inspections/<int:pk>/reject/` `qci_reject`.

`qci_list` — qs `.select_related("project","wbs_node","quality_plan","milestone","inspector",
"accepted_by","accepted_by_party")`; `search_fields = ["number","title","description","findings"]`;
`filters = [("project","project_id",True), ("inspection_type","inspection_type",False),
("result","result",False), ("usage_decision","usage_decision",False), ("status","status",False),
("inspector","inspector_id",True)]`; pre-scoped `?overdue=1` → `Q(planned_date__lt=today,
inspected_date__isnull=True, status__in=("planned","in_progress"))`.
`extra_context`: `projects`, `inspection_type_choices`, `result_choices`, `usage_decision_choices`,
`status_choices`, `owners` — the originally pinned `parties` key is dropped: no template reads it,
so it was one dead Party query per render.
Detail: `obj`, `defects` (`obj.defects.select_related("owner")`), `accept_form` (unbound
`InspectionAcceptanceForm(tenant=request.tenant)`).

### 4.4 QualityDefect — `views/QualityManagement/QualityDefects.py`

Routes: `defects/` `qdf_list` · `defects/add/` `qdf_create` · `defects/<int:pk>/` `qdf_detail` ·
`defects/<int:pk>/edit/` `qdf_edit` · `defects/<int:pk>/delete/` `qdf_delete` ·
`defects/<int:pk>/resolve/` `qdf_resolve` · `defects/<int:pk>/close/` `qdf_close` ·
`defects/<int:pk>/raise-issue/` `qdf_raise_issue`.

`qdf_list` — qs `.select_related("project","wbs_node","quality_plan","inspection","project_issue",
"owner","resolved_by")`; `search_fields = ["number","title","description","root_cause",
"resolution_note"]`; `filters = [("project","project_id",True), ("severity","severity",False),
("status","status",False), ("disposition","disposition",False),
("defect_category","defect_category",False), ("owner","owner_id",True),
("inspection","inspection_id",True)]`; pre-scoped `?overdue=1` → `Q(due_date__lt=today,
status__in=("open","in_progress"))`.
`extra_context`: `projects`, `severity_choices`, `status_choices`, `disposition_choices`,
`defect_category_choices`, `owners`, `inspections` (`DeliverableInspection.objects.filter(tenant=…)`).
Detail: `obj`, `resolution_form` (unbound `DefectResolutionForm()`).

### 4.5 `quality_improvement` — `views/QualityManagement/QualityImprovement.py`, route `quality-improvement/`

Template `projects/quality/quality_improvement.html`, **GET-only**. Context (exact keys):
`projects`; `project` (`?project=`, `as_db_int`-guarded, tenant-filtered, else None);
`improvement_rows` (the project's `QualityReview` with `review_type in ("kaizen_event",
"retrospective")` ordered `-review_date`, cap 25); `maturity` (dict `{"has_score","score","band",
"badge","reviews_scored","defects_total","defects_closed","closure_pct"}` — computed, **no stored
table**; `has_score` distinguishes a computed 0.0 from no data so the band renders); `defect_trend_rows` (period rows `{"period","label","opened","closed","bar_pct"}`, CSS bars, **not a
chart**); `defect_trend_max`; `lessons` (list of `{"obj","lesson"}` over closed defects with a
non-empty `lessons_learned`, newest first, cap 25); `lessons_count`; `open_defect_count`;
`improvement_open_count`.

### 4.6 `quality_acceptance` — `views/QualityManagement/QualityAcceptance.py`, route `quality-acceptance/`

Template `projects/quality/quality_acceptance.html`, **GET-only**. Context (exact keys): `projects`;
`project` (`?project=`, `as_db_int`-guarded); `deliverable_rows` (one row per WBS `deliverable` node
of the selected project: `{"wbs_node","plan","plan_status","latest_inspection","result",
"usage_decision","open_defects","acceptance_state","badge"}` where `acceptance_state` ∈
`pending`/`conditional`/`accepted`/`rejected` and `badge` is a colour-named class — **L33**);
`acceptance_queue` (inspections with `inspection_type="acceptance"` and `usage_decision="pending"`,
ordered `planned_date`, rendered rows capped at 100 with the header figure a DB count — each row
links to its detail page, where the `qci_accept` action lives); `acceptance_queue_count`;
`accepted_count`; `conditional_count`; `rejected_count`; `pending_count`.

## 5. Templates

* `qualityplan/{list,detail,form}.html`, `qualityreview/{list,detail,form}.html`,
  `deliverableinspection/{list,detail,form}.html`, `qualitydefect/{list,detail,form}.html`, plus
  `quality_improvement.html`, `quality_acceptance.html` at `templates/projects/quality/`.
* Every list: `.page-header` + breadcrumb, GET filter form reflecting `request.GET` (string filters
  `{% if request.GET.status == value %}selected{% endif %}`; FK filters
  `{% if request.GET.project == p.pk|stringformat:"d" %}selected{% endif %}`), `.table-wrap`/`.table`
  with an Actions column (eye → detail, pencil → edit, delete POST form + `confirm()` +
  `{% csrf_token %}`), `.pagination` guarded by `has_previous`/`has_next`, `.empty-state`.
* Badges: colour-named only; every block ends
  `{% else %}{{ obj.get_<field>_display }}{% endif %}`.
* **No nullable FK inside a `|default:` filter argument** (L10) — `owner`, `approved_by`,
  `reviewer`, `improvement_owner`, `inspector`, `accepted_by`, `accepted_by_party`, `resolved_by`
  render via `{% if fk %}…{% else %}—{% endif %}`.
* **Multi-line notes use `{% comment %} … {% endcomment %}`** — a multi-line `{# … #}` leaks as
  visible text (L2).
* Verb buttons are POST forms with `{% csrf_token %}`, gated in the template the same way the view
  gates them (defence in depth, not the boundary).

## 6. Wire-up (Integrate only — single writer, surgical edits)

* `apps/projects/{models,forms,views,urls}/QualityManagement/__init__.py` — **empty** (4 files).
* Top-level `__init__.py` re-export blocks `# --- 7.6 Quality Management`, **inserted between the
  existing `# --- 7.5` and `# --- 7.7` blocks**, in all four layers: models (4), forms (6), views
  (4 CRUD sets + 10 verbs + `quality_improvement` + `quality_acceptance`), urls (6 `urlpatterns`
  imports + concat, in the order QualityPlans, QualityReviews, DeliverableInspections,
  QualityDefects, QualityImprovement, QualityAcceptance).
* `apps/projects/views/_helpers.py` — **nothing added** (`owners`/`clients` already exist).
* `apps/projects/admin.py` — 4 registrations (`list_display` led by `number`,
  `list_select_related` for every rendered FK, `approved_at`/`closed_at`/`accepted_at`/`resolved_at`
  readonly).
* `apps/projects/management/commands/seed_projects.py` — a `_quality` block with its own guard
  (`QualityPlan.objects.filter(tenant=tenant).exists()`), called per tenant; `--flush` deletes
  children-first `QualityDefect, DeliverableInspection, QualityReview, QualityPlan`.
* `apps/core/navigation.py` — one `LIVE_LINKS["7.6"]` block immediately after the `"7.5"` block.
* `templates/projects/overview.html` — 7.6 quick links + counts.
* `config/settings.py` / `config/urls.py` — **not touched** (app already registered).
* Then, **LAST**: `makemigrations projects --dry-run` (read every model it names; **abort if it
  names anything outside 7.6's four**) → generate → `migrate` → `seed_projects` ×2 → `manage.py check`.

## 7. Sidebar keys (verbatim from NavERP.md — must match character-for-character)

1. `Quality Planning & Standards` → `projects:qpl_list`
2. `Quality Assurance (QA)` → `projects:qrv_list?kind=assurance`
3. `Quality Control (QC) & Inspections` → `projects:qci_list`
4. `Continuous Improvement` → `projects:quality_improvement`
5. `Deliverable Acceptance & Sign-off` → `projects:quality_acceptance`

Extra live leaves: `Quality Review Register` → `projects:qrv_list`; `Defect & Punch List` →
`projects:qdf_list`.

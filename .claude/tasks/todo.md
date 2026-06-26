---
# HRM Sub-module 3.5 — Job Requisition (hrm) — plan from research-hrm-job-requisition.md  (2026-06-26)

**Extending `apps/hrm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py`
are already in place. The only new wire-up is ONE `LIVE_LINKS["3.5"]` entry + URL patterns inside the
existing `apps/hrm/urls.py`. Three models: `JobRequisition` [JR-], `JobDescriptionTemplate` [JDTMPL-],
`RequisitionApproval` (child — no number). Sub-module template folder: `templates/hrm/recruitment/`.

---

## 0. Template folder decision

3.5 is a multi-entity sub-module (2 primary entities + 1 child inline). Per CLAUDE.md rule 2, the
folder shape is `templates/hrm/recruitment/<entity>/<page>.html`.

- [ ] Create folder structure `templates/hrm/recruitment/`:
  - `recruitment/jobrequisition/{list,detail,form}.html`   — JobRequisition CRUD
  - `recruitment/jobdescriptiontemplate/{list,detail,form}.html` — JobDescriptionTemplate CRUD
  - `recruitment/jobrequisition/clone.html`                — optional clone-confirm page (can be POST-only redirect)
  - NOTE: `RequisitionApproval` rows render **inline on the requisition detail hub** (identical to
    `ClearanceItem` rows on the separation-case hub). They get NO standalone list/form templates.
    The only approval-facing page is the detail hub; workflow actions are POST-only views.

---

## 1. Models (add to `apps/hrm/models.py`)

### 1a. `JobDescriptionTemplate` [JDTMPL-] — `TenantNumbered`, `NUMBER_PREFIX = "JDTMPL"`

Drivers: Greenhouse (template library), Workable (JD body pre-fill), SmartRecruiters (template→req
copy-on-apply); mirrors `OnboardingTemplate.designation` FK pattern already in the codebase.

- [ ] Add `JobDescriptionTemplate(TenantNumbered)` with `NUMBER_PREFIX = "JDTMPL"`:
  - `number`          — `CharField(max_length=20, editable=False)` — inherited from `TenantNumbered`
  - `name`            — `CharField(max_length=255)` — e.g. "Senior Software Engineer — Backend"
                        (drivers: Greenhouse template names, Workable)
  - `designation`     — `ForeignKey("hrm.Designation", on_delete=SET_NULL, null=True, blank=True,
                        related_name="jd_templates")` — auto-suggest when a req is raised for this
                        designation (mirrors `OnboardingTemplate.designation`); drivers: Workday
                        position-based auto-population, Greenhouse recurring role types
  - `employment_type` — `CharField(max_length=20, blank=True, choices=EMPLOYMENT_TYPE_CHOICES)` —
                        default employment type hint for this template; defined as a module-level
                        constant (see choices block below)
  - `jd_summary`      — `TextField(blank=True)` — role overview / elevator pitch
                        (drivers: Oracle Taleo, Greenhouse, SmartRecruiters)
  - `jd_responsibilities` — `TextField(blank=True)` — bullet list of duties
  - `jd_requirements`    — `TextField(blank=True)` — must-have qualifications
  - `jd_nice_to_have`    — `TextField(blank=True)` — preferred qualifications
                        (drivers: Greenhouse, Workable, Breezy HR structured JD)
  - `is_active`       — `BooleanField(default=True)`
  - `Meta.ordering = ["name"]`
  - `unique_together = ("tenant", "name")`
  - DB indexes:
    - `("tenant", "designation")` — `hrm_jdtmpl_tenant_desig_idx`
    - `("tenant", "is_active")` — `hrm_jdtmpl_tenant_active_idx`
  - `__str__`: `f"{self.number} · {self.name}"`
  - No `clean()` needed (no cross-field constraint)
  - **Reuses**: `hrm.Designation` (optional linkage). Adds `jd_*` text fields + `employment_type`.

### 1b. `JobRequisition` [JR-] — `TenantNumbered`, `NUMBER_PREFIX = "JR"`

The hub record — the "authorization to hire" into which 3.6 Candidate / 3.7 Interview / 3.8 Offer
will FK in future passes. Inherits `TenantNumbered`.

Drivers: Workday (requisition hub, position-based), Workable (status lifecycle + all P0/P1 fields),
Lever (headcount + backfill + compensation band), iCIMS (sequential approval chain hub), Oracle Taleo
(JD body on the opening), Breezy HR (cost-center code + salary range).

- [ ] Add module-level choice constants BEFORE `JobDescriptionTemplate` (reused by both models):

  ```python
  EMPLOYMENT_TYPE_CHOICES = [
      ("full_time", "Full-Time"),
      ("part_time", "Part-Time"),
      ("contract", "Contract"),
      ("intern", "Intern"),
      ("consultant", "Consultant"),
  ]

  REQ_TYPE_CHOICES = [
      ("standard", "Standard"),
      ("backfill", "Backfill"),
      ("replacement", "Replacement"),
      ("evergreen", "Evergreen / Pipeline"),
  ]

  REASON_FOR_HIRE_CHOICES = [
      ("new_headcount", "New Headcount"),
      ("backfill", "Backfill Vacancy"),
      ("replacement", "Replacement"),
      ("project", "Project / Fixed Term"),
      ("contractor_to_perm", "Contractor to Permanent"),
  ]

  POSTING_TYPE_CHOICES = [
      ("internal", "Internal Only"),
      ("external", "External Only"),
      ("both", "Internal & External"),
  ]

  PRIORITY_CHOICES = [
      ("low", "Low"),
      ("medium", "Medium"),
      ("high", "High"),
      ("urgent", "Urgent"),
  ]

  JR_STATUS_CHOICES = [
      ("draft", "Draft"),
      ("submitted", "Submitted"),
      ("pending_approval", "Pending Approval"),
      ("approved", "Approved"),
      ("posted", "Posted"),
      ("on_hold", "On Hold"),
      ("filled", "Filled"),
      ("cancelled", "Cancelled"),
      ("rejected", "Rejected"),
  ]

  APPROVAL_STEP_STATUS_CHOICES = [
      ("pending", "Pending"),
      ("approved", "Approved"),
      ("rejected", "Rejected"),
      ("returned", "Returned for Revision"),
      ("skipped", "Skipped"),
  ]

  APPROVER_ROLE_CHOICES = [
      ("hiring_manager", "Hiring Manager"),
      ("hr", "HR"),
      ("finance", "Finance"),
      ("executive", "Executive"),
      ("custom", "Custom"),
  ]
  ```

- [ ] Add `JobRequisition(TenantNumbered)` with `NUMBER_PREFIX = "JR"`:

  **Identity:**
  - `number`       — `CharField(max_length=20, editable=False)` — JR-00001; `TenantNumbered`
  - `title`        — `CharField(max_length=255)` — job title for this specific opening
                     (drivers: Workday job title, Workable, Oracle Taleo)
  - `designation`  — `ForeignKey("hrm.Designation", on_delete=SET_NULL, null=True, blank=True,
                     related_name="requisitions")` — links to the evergreen role definition +
                     salary band; auto-populates `jd_*` + salary range via `apply_template_to_requisition`
                     (drivers: Workday position-based req, SAP SuccessFactors position mgmt)
  - `job_grade`    — `ForeignKey("hrm.JobGrade", on_delete=SET_NULL, null=True, blank=True,
                     related_name="requisitions")` — denormalized from `designation.job_grade` for
                     quick filter (drivers: Lever, Workday management level)
  - `template`     — `ForeignKey("hrm.JobDescriptionTemplate", on_delete=SET_NULL, null=True,
                     blank=True, related_name="requisitions")` — which template was applied
                     (record-keeping only; copy-on-apply semantics)

  **Organization:**
  - `department`   — `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True,
                     related_name="requisitions", limit_choices_to={"kind": "department"})` —
                     inherits from `designation.department` but overridable (drivers: Workday dept,
                     Oracle Taleo, iCIMS)
  - `cost_center`  — `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True,
                     related_name="requisitions_cc", limit_choices_to={"kind": "cost_center"})` —
                     which cost center absorbs the headcount (drivers: Breezy HR, Workday, Oracle Taleo)
  - `location`     — `CharField(max_length=255, blank=True)` — office / city / "Remote"
                     (drivers: Workable, iCIMS, SAP SuccessFactors)

  **Headcount & type:**
  - `headcount`    — `PositiveSmallIntegerField(default=1)` — number of openings
                     (drivers: Workable headcount field, Lever)
  - `req_type`     — `CharField(max_length=20, choices=REQ_TYPE_CHOICES, default="standard")`
                     (drivers: Workday standard/evergreen, Oracle Taleo req type)
  - `employment_type` — `CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default="full_time")`
                     (drivers: Workable, iCIMS, Zoho Recruit — table stakes)
  - `reason_for_hire` — `CharField(max_length=30, choices=REASON_FOR_HIRE_CHOICES, default="new_headcount")`
                     (drivers: Lever backfill flag, Workable, BambooHR)
  - `is_replacement_for` — `CharField(max_length=255, blank=True)` — name of departing employee
                     (free-text stub; FK upgrade to `EmployeeProfile` deferred to 3.6)
                     (drivers: Oracle Taleo, Workable)

  **Posting scope:**
  - `posting_type` — `CharField(max_length=10, choices=POSTING_TYPE_CHOICES, default="external")`
                     (drivers: Oracle Taleo internal/external toggle, SAP SuccessFactors)

  **Hiring team:**
  - `hiring_manager` — `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True,
                      related_name="managed_requisitions")` — reports-to for the new hire;
                      per HRM convention: FK goes to `EmployeeProfile`, NEVER `core.Party` directly
                      (drivers: Workable, Oracle Taleo, iCIMS, Greenhouse — P0)
  - `recruiter`     — `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True,
                      related_name="assigned_requisitions")` — TA owner
                      (drivers: Oracle Taleo, iCIMS, Workable — P0)

  **Timeline:**
  - `target_start_date` — `DateField(null=True, blank=True)` — when the new hire should start
                      (drivers: Lever, Workable, SAP SuccessFactors — used for overdue tracking)
  - `priority`      — `CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")`
                      (drivers: Oracle Taleo DAR, Breezy HR, Lever)

  **Budget (P0/P1):**
  - `salary_min`    — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` —
                      opening-specific budget min (may differ from `Designation.min_salary`)
                      (drivers: Lever compensation band, Workable, Breezy HR, Zoho Recruit — P0)
  - `salary_max`    — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
  - `salary_currency` — `CharField(max_length=3, default="USD")` — ISO-4217 code
                      (drivers: multi-currency tenants, SAP SuccessFactors)
  - `estimated_annual_cost` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` —
                      loaded annual cost (salary + benefits estimate); manually entered by requester
                      (drivers: GoodTime/Teravexa loaded-cost estimate, Deel guide — P1)
  - `hiring_cost_budget` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` —
                      one-time recruitment cost budget (agency fees, job-board spend)
                      (drivers: Breezy HR budgetary impact summary — P2, optional field)

  **Job description (hiring-event-specific copy — distinct from `Designation.description`):**
  - `jd_summary`          — `TextField(blank=True)` (drivers: Oracle Taleo, Greenhouse)
  - `jd_responsibilities` — `TextField(blank=True)` (drivers: Greenhouse, SmartRecruiters)
  - `jd_requirements`     — `TextField(blank=True)` (drivers: Greenhouse, Workable)
  - `jd_nice_to_have`     — `TextField(blank=True)` (drivers: Greenhouse, Breezy HR)

  **Workflow-owned (editable=False — never on the form; set only by POST actions):**
  - `status`        — `CharField(max_length=20, choices=JR_STATUS_CHOICES, default="draft",
                      editable=False)` (drivers: Workable draft→approved→open→filled lifecycle)
  - `submitted_at`  — `DateTimeField(null=True, blank=True, editable=False)`
  - `approved_at`   — `DateTimeField(null=True, blank=True, editable=False)`
  - `posted_at`     — `DateTimeField(null=True, blank=True, editable=False)`
  - `filled_at`     — `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`         — `TextField(blank=True)` — internal HR notes (editable — stays on the form)

  **Meta:**
  - `Meta.ordering = ["-created_at"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "status")` — `hrm_jr_tenant_status_idx`
    - `("tenant", "designation")` — `hrm_jr_tenant_desig_idx`
    - `("tenant", "department")` — `hrm_jr_tenant_dept_idx`
    - `("tenant", "hiring_manager")` — `hrm_jr_tenant_hm_idx`
    - `("tenant", "priority", "status")` — `hrm_jr_tenant_prio_status_idx`

  **`__str__`**: `f"{self.number} · {self.title}"`

  **`clean()` validations:**
  - If `salary_min` and `salary_max` are both set: raise `ValidationError` if `salary_min > salary_max`
    ("Salary minimum cannot exceed maximum.")
  - If `headcount` is set: raise `ValidationError` if `headcount < 1` ("Headcount must be at least 1.")

  **Derived properties (never stored):**
  - `is_overdue` — `@property`: `target_start_date is not None and target_start_date < date.today()
    and self.status not in ("filled", "cancelled")` — flags overdue reqs for red badge
  - `approval_progress` — `@property`: returns `(approved_count, total_count)` tuple from
    `self.approvals.all()` counts; used in the detail hub progress bar
  - `current_approval_step` — `@property`: returns the first `RequisitionApproval` with
    `status="pending"` ordered by `step_order`; returns `None` if none pending

  **Reuses**: `hrm.Designation`, `hrm.JobGrade`, `hrm.EmployeeProfile` (hiring_manager + recruiter),
  `core.OrgUnit` (department + cost_center), `hrm.JobDescriptionTemplate`. Does NOT FK to
  Candidate/Interview/Offer — those arrive in 3.6/3.7/3.8.

### 1c. `RequisitionApproval` — `TenantOwned` (child row, no number prefix)

One row per approval step per requisition. The collection is both the sequential approval chain and
the immutable audit trail. Mirrors the `ClearanceItem` pattern from 3.4 Offboarding.

Drivers: Oracle Taleo DAR (step order + decided_at audit), SmartRecruiters (approve/reject/return
actions), Workable (sequential chain, mandatory), iCIMS (minimum 2 approvers, P0).

- [ ] Add `RequisitionApproval(TenantOwned)`:
  - `tenant`       — FK → `"core.Tenant"` (inherited via `TenantOwned`)
  - `requisition`  — `ForeignKey("hrm.JobRequisition", on_delete=CASCADE,
                     related_name="approvals")` — the parent req
  - `step_order`   — `PositiveSmallIntegerField()` — 1, 2, 3 ... defines sequential order; the view
                     only exposes the action buttons for the approver whose step_order equals the
                     minimum pending step (drivers: Oracle Taleo DAR, iCIMS)
  - `approver`     — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True,
                     related_name="hrm_requisition_approvals")` — designated approver
                     (drivers: SmartRecruiters per-step approver, Workable)
  - `approver_role` — `CharField(max_length=20, choices=APPROVER_ROLE_CHOICES, default="hr")` —
                      label only; does not enforce auth (drivers: Oracle Taleo role labels)
  - `status`       — `CharField(max_length=20, choices=APPROVAL_STEP_STATUS_CHOICES,
                     default="pending", editable=False)` — workflow-owned; set only by
                     approve/reject/return POST actions (never editable via form)
  - `decided_at`   — `DateTimeField(null=True, blank=True, editable=False)` — stamped by the action
                     (drivers: Oracle Taleo History tab, SmartRecruiters audit)
  - `decided_by`   — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True,
                     blank=True, related_name="hrm_approval_decisions", editable=False)` —
                     may differ from `approver` when an admin overrides; stamped by the action
  - `comments`     — `TextField(blank=True)` — rejection/return reason; editable on the action form
                     (drivers: Oracle Taleo, SmartRecruiters comments, Workable)

  **Meta:**
  - `Meta.ordering = ["step_order"]`
  - `unique_together = ("requisition", "step_order")` — one step per order position per req;
    `clean()` validates `step_order >= 1`
  - DB indexes:
    - `("requisition", "status")` — `hrm_ra_req_status_idx`
    - `("approver", "status")` — `hrm_ra_approver_status_idx` (used in "my pending approvals" query)

  **`__str__`**: `f"Step {self.step_order} — {self.get_approver_role_display()} — {self.get_status_display()}"`

  **`clean()` validations:**
  - Raise `ValidationError` if `step_order < 1` ("Step order must be at least 1.")
  - Cross-tenant guard: validate `self.requisition.tenant_id == self.tenant_id`

  **NOT deleted** — rows are immutable once created (they form the audit trail); the approve/reject/
  return actions UPDATE `status`/`decided_at`/`decided_by` via `update_fields`.

  **Reuses**: `hrm.JobRequisition` (parent), `settings.AUTH_USER_MODEL` (approver + decided_by).
  No `TenantNumbered` — child rows are identified by `requisition + step_order`.

---

## 2. Services (`apps/hrm/services.py`)

Two request-free helpers importable by views, the seeder, and tests.

- [ ] **`generate_approval_chain(requisition)`** — idempotent; mirrors `generate_clearance_checklist`.
  - Signature: `def generate_approval_chain(requisition) -> list[RequisitionApproval]`
  - Logic: if `requisition.approvals.exists()`: return list of existing rows (idempotent — never
    duplicates). Otherwise create the default 2-step chain:
    - Step 1: `step_order=1, approver=None, approver_role="hr", status="pending"` (HR approval)
    - Step 2: `step_order=2, approver=None, approver_role="executive", status="pending"` (Exec approval)
    Use `bulk_create([...])` to create both at once. Return the two rows.
  - Guards: must only be called when `requisition.status == "draft"` (else raise `ValueError`).
  - Import guard: import `RequisitionApproval` inside the function (or at module top) — avoid
    circular import since `services.py` already imports from `.models`.

- [ ] **`apply_template_to_requisition(requisition, template)`** — copy-on-apply helper.
  - Signature: `def apply_template_to_requisition(requisition, template) -> None`
  - Copies `template.jd_summary`, `template.jd_responsibilities`, `template.jd_requirements`,
    `template.jd_nice_to_have` onto `requisition.jd_*` fields and sets `requisition.template = template`.
  - Does NOT copy `employment_type` (the req has its own field; avoid silently overriding).
  - Saves via `requisition.save(update_fields=["jd_summary","jd_responsibilities","jd_requirements",
    "jd_nice_to_have","template","updated_at"])`.
  - Request-free: no `request` parameter; the calling view passes the already-fetched objects.

- [ ] Add `JobRequisition`, `JobDescriptionTemplate`, `RequisitionApproval` to the
  `from .models import (...)` block in `services.py`.

---

## 3. Forms (`apps/hrm/forms.py`)

All forms use `TenantModelForm` (auto-scopes FK querysets; applies widget classes; sets tenant).

- [ ] **`JobDescriptionTemplateForm(TenantModelForm)`**:
  - `model = JobDescriptionTemplate`
  - `fields = ["name", "designation", "employment_type", "jd_summary", "jd_responsibilities",
    "jd_requirements", "jd_nice_to_have", "is_active"]`
  - Excluded: `tenant`, `number` (auto-generated by `TenantNumbered.save()`)
  - `__init__`: scope `designation` queryset →
    `Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name")`

- [ ] **`JobRequisitionForm(TenantModelForm)`**:
  - `model = JobRequisition`
  - `fields = ["title", "designation", "job_grade", "template", "department", "cost_center",
    "location", "headcount", "req_type", "employment_type", "reason_for_hire",
    "is_replacement_for", "posting_type", "hiring_manager", "recruiter", "target_start_date",
    "priority", "salary_min", "salary_max", "salary_currency", "estimated_annual_cost",
    "hiring_cost_budget", "jd_summary", "jd_responsibilities", "jd_requirements",
    "jd_nice_to_have", "notes"]`
  - **Excluded** (workflow-owned): `tenant`, `number`, `status`, `submitted_at`, `approved_at`,
    `posted_at`, `filled_at` — mirror `SeparationCaseForm` exclusion pattern
  - `__init__`: scope FK querysets:
    - `designation` → `Designation.objects.filter(tenant=self.tenant, is_active=True).order_by("name")`
    - `job_grade` → `JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order","name")`
    - `template` → `JobDescriptionTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("name")`
    - `department` → `OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name")`
    - `cost_center` → `OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center").order_by("name")`
    - `hiring_manager` → `EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name")`
    - `recruiter` → same as `hiring_manager`
  - `clean()`: validate `salary_min <= salary_max` if both set; validate `headcount >= 1`

- [ ] **`RequisitionApprovalForm(TenantModelForm)`** — used ONLY for the inline "add step" form on
  the requisition detail hub (similar to how `ClearanceItemForm` is used):
  - `model = RequisitionApproval`
  - `fields = ["step_order", "approver", "approver_role", "comments"]`
  - Excluded: `tenant`, `requisition` (set by view), `status`, `decided_at`, `decided_by`
    (workflow-owned — set only by approve/reject/return actions)
  - `__init__`: scope `approver` queryset → `User.objects.filter(is_active=True).order_by("username")`
    (approvers are `User` rows, not `EmployeeProfile`, per design)

- [ ] Add `JobDescriptionTemplate`, `JobRequisition`, `RequisitionApproval` to the
  `from .models import (...)` block in `forms.py`; add `EMPLOYMENT_TYPE_CHOICES`, `JR_STATUS_CHOICES`,
  `APPROVAL_STEP_STATUS_CHOICES`, `APPROVER_ROLE_CHOICES`, `REQ_TYPE_CHOICES`, `PRIORITY_CHOICES` where
  needed for `extra_context` in views.

---

## 4. Views (`apps/hrm/views.py`)

All views: `@login_required`, tenant-scoped (`tenant=request.tenant`). Workflow write actions:
`@tenant_admin_required` + `@require_POST`. Audit via `write_audit_log`.

### 4a. `JobDescriptionTemplate` CRUD

- [ ] **`jobdescriptiontemplate_list(request)`** — `crud_list(...)`:
  - QS: `JobDescriptionTemplate.objects.filter(tenant=request.tenant).select_related("designation").order_by("name")`
  - `template="hrm/recruitment/jobdescriptiontemplate/list.html"`
  - `search_fields=["number", "name", "jd_summary", "designation__name"]`
  - `filters=[("is_active","is_active",False), ("designation","designation_id",True)]`
  - `extra_context={"designations": Designation.objects.filter(tenant=request.tenant, is_active=True).order_by("name")}`

- [ ] **`jobdescriptiontemplate_create(request)`** — `crud_create(...)`:
  - `form_class=JobDescriptionTemplateForm`, `template="hrm/recruitment/jobdescriptiontemplate/form.html"`
  - `success_url="hrm:jobdescriptiontemplate_list"`

- [ ] **`jobdescriptiontemplate_detail(request, pk)`** — `get_object_or_404(JobDescriptionTemplate,
  pk=pk, tenant=request.tenant)` with `select_related("designation")`;
  render `"hrm/recruitment/jobdescriptiontemplate/detail.html"` with context:
  `{"obj": obj, "linked_reqs": JobRequisition.objects.filter(tenant=request.tenant, template=obj)
  .order_by("-created_at")[:10]}`

- [ ] **`jobdescriptiontemplate_edit(request, pk)`** — `crud_edit(...)`:
  - `model=JobDescriptionTemplate`, `form_class=JobDescriptionTemplateForm`
  - `template="hrm/recruitment/jobdescriptiontemplate/form.html"`, `success_url="hrm:jobdescriptiontemplate_list"`

- [ ] **`jobdescriptiontemplate_delete(request, pk)`** — `@require_POST`; guard: if
  `JobRequisition.objects.filter(tenant=request.tenant, template=obj).exists()` →
  `messages.error(request, "Cannot delete a template used by requisitions. Deactivate it instead.")`
  + redirect to detail. Else: `write_audit_log` + `obj.delete()` + `messages.success` +
  redirect to list.

### 4b. `JobRequisition` CRUD

- [ ] **`jobrequisition_list(request)`** — `crud_list(...)`:
  - QS: `JobRequisition.objects.filter(tenant=request.tenant).select_related(
    "designation", "department", "hiring_manager__party", "recruiter__party").order_by("-created_at")`
  - `template="hrm/recruitment/jobrequisition/list.html"`
  - `search_fields=["number", "title", "location", "designation__name"]`
  - `filters=[
      ("status", "status", False),
      ("priority", "priority", False),
      ("department", "department_id", True),
      ("hiring_manager", "hiring_manager_id", True),
      ("req_type", "req_type", False),
      ("employment_type", "employment_type", False),
    ]`
  - `extra_context={
      "status_choices": JR_STATUS_CHOICES,
      "priority_choices": PRIORITY_CHOICES,
      "req_type_choices": REQ_TYPE_CHOICES,
      "employment_type_choices": EMPLOYMENT_TYPE_CHOICES,
      "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
      "hiring_managers": EmployeeProfile.objects.filter(tenant=request.tenant)
        .select_related("party").order_by("party__name"),
    }`

- [ ] **`jobrequisition_create(request)`** — `crud_create(...)`:
  - `form_class=JobRequisitionForm`, `template="hrm/recruitment/jobrequisition/form.html"`
  - `success_url="hrm:jobrequisition_list"`
  - After save, if `request.POST.get("apply_template")` is set: call
    `apply_template_to_requisition(obj, obj.template)` if `obj.template_id`

- [ ] **`jobrequisition_detail(request, pk)`** — the **hub view** (mirrors `separationcase_detail`):
  - Fetch: `get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)` with
    `select_related("designation__job_grade", "department", "cost_center",
    "hiring_manager__party", "recruiter__party", "template")`
  - Approval rows: `approvals = obj.approvals.select_related("approver", "decided_by").order_by("step_order")`
  - Computed: `current_step = obj.current_approval_step` (property)
  - `approval_form = RequisitionApprovalForm(tenant=request.tenant)` (for the "add step" form)
  - render `"hrm/recruitment/jobrequisition/detail.html"` with context:
    `{"obj": obj, "approvals": approvals, "current_step": current_step,
    "approval_form": approval_form, "can_submit": obj.status == "draft",
    "can_approve": obj.status == "pending_approval",
    "can_post": obj.status == "approved",
    "can_hold": obj.status in ("approved", "posted"),
    "can_fill": obj.status == "posted",
    "can_cancel": obj.status not in ("filled","cancelled"),}`

- [ ] **`jobrequisition_edit(request, pk)`** — `crud_edit(...)`:
  - Guard: if `obj.status not in ("draft", "rejected")` →
    `messages.error(request, "Only draft or rejected requisitions can be edited.")` + redirect to detail
  - `model=JobRequisition`, `form_class=JobRequisitionForm`
  - `template="hrm/recruitment/jobrequisition/form.html"`, `success_url="hrm:jobrequisition_list"`

- [ ] **`jobrequisition_delete(request, pk)`** — `@require_POST`; guard: if `obj.status != "draft"` →
  error "Only draft requisitions can be deleted." + redirect to detail. Else: `write_audit_log` +
  `obj.delete()` + `messages.success` + redirect to list.

### 4c. `RequisitionApproval` — inline create (add step from detail hub)

- [ ] **`approval_add(request, jr_pk)`** — `@tenant_admin_required`, `@require_POST`:
  - Fetch req: `get_object_or_404(JobRequisition, pk=jr_pk, tenant=request.tenant)`
  - Guard: req.status must be `"draft"` (steps only added before submission)
  - Bind `RequisitionApprovalForm(request.POST, tenant=request.tenant)`; if valid:
    `step = form.save(commit=False); step.tenant = request.tenant; step.requisition = req; step.status = "pending"; step.save()`
  - `write_audit_log(request.user, step, "create")`; `messages.success`; redirect to detail hub
  - No GET — POST-only inline form on the detail page

- [ ] **`approval_delete(request, pk)`** — `@tenant_admin_required`, `@require_POST`:
  - Fetch: `get_object_or_404(RequisitionApproval, pk=pk, tenant=request.tenant)`
  - Guard: `step.requisition.status` must be `"draft"` (can only remove steps before submission)
  - Guard: `step.status != "approved"` (can't remove a decided step)
  - `write_audit_log`; `obj.delete()`; `messages.success`; redirect to `hrm:jobrequisition_detail jr_pk=step.requisition.pk`

### 4d. Workflow POST actions on `JobRequisition`

All workflow actions: `@tenant_admin_required`, `@require_POST`, `write_audit_log`, redirect to detail.

- [ ] **`jobrequisition_submit(request, pk)`**:
  - Guard: `status == "draft"` only
  - Call `generate_approval_chain(obj)` (creates default steps if none added manually)
  - Set `obj.status = "submitted"` → `"pending_approval"` if approval chain exists, else
    `"approved"` directly (if no steps — edge case for tenants that bypass approval)
  - Set `obj.submitted_at = timezone.now()`
  - `obj.save(update_fields=["status","submitted_at","updated_at"])`
  - `write_audit_log(request.user, obj, "update", {"action":"submit","from":"draft","to":obj.status})`

- [ ] **`jobrequisition_approve_step(request, pk)`** — approve the CURRENT pending step (the
  minimum `step_order` with `status="pending"`):
  - Guard: `obj.status == "pending_approval"`
  - Fetch current step: `step = obj.approvals.filter(status="pending").order_by("step_order").first()`
  - Guard: `step is not None` and `request.user == step.approver` OR request.user is tenant admin
    (admin can override any step)
  - Set `step.status = "approved"`, `step.decided_at = timezone.now()`, `step.decided_by = request.user`
  - `step.save(update_fields=["status","decided_at","decided_by","updated_at"])`
  - Check if all steps approved: if `obj.approvals.filter(status="pending").count() == 0`:
    set `obj.status = "approved"`, `obj.approved_at = timezone.now()`
    `obj.save(update_fields=["status","approved_at","updated_at"])`
  - `write_audit_log(request.user, obj, "update", {"action":"approve_step","step":step.step_order})`

- [ ] **`jobrequisition_reject(request, pk)`** — reject the entire requisition at the current step:
  - Guard: `obj.status == "pending_approval"`
  - Fetch current step; set `step.status = "rejected"`, stamp `decided_at`/`decided_by`/`comments`
    (from `request.POST.get("comments","")`); save step.
  - Set `obj.status = "rejected"`, save req.
  - `write_audit_log(request.user, obj, "update", {"action":"reject","step":step.step_order})`

- [ ] **`jobrequisition_return(request, pk)`** — return for revision (req → `draft`, pending steps reset):
  - Guard: `obj.status == "pending_approval"`
  - Fetch current step; set `step.status = "returned"`, stamp, save.
  - Reset all other pending steps: `obj.approvals.filter(status="pending").update(status="pending")`
    (already pending — the point is the req goes back to `draft` for editing)
  - Set `obj.status = "draft"`, clear `obj.submitted_at = None`, save.
  - `write_audit_log(request.user, obj, "update", {"action":"return","step":step.step_order})`

- [ ] **`jobrequisition_post(request, pk)`** — mark as posted (approved → posted):
  - Guard: `obj.status == "approved"`
  - Set `obj.status = "posted"`, `obj.posted_at = timezone.now()`, save.
  - `write_audit_log(request.user, obj, "update", {"action":"post"})`

- [ ] **`jobrequisition_hold(request, pk)`** — place on hold (approved or posted → on_hold):
  - Guard: `obj.status in ("approved","posted")`
  - Set `obj.status = "on_hold"`, save.
  - `write_audit_log(request.user, obj, "update", {"action":"hold"})`

- [ ] **`jobrequisition_mark_filled(request, pk)`** — mark as filled (posted → filled):
  - Guard: `obj.status in ("posted","on_hold")`
  - Set `obj.status = "filled"`, `obj.filled_at = timezone.now()`, save.
  - `write_audit_log(request.user, obj, "update", {"action":"fill"})`

- [ ] **`jobrequisition_cancel(request, pk)`** — cancel (any status except filled/cancelled):
  - Guard: `obj.status not in ("filled","cancelled")`
  - Set `obj.status = "cancelled"`, save.
  - `write_audit_log(request.user, obj, "update", {"action":"cancel"})`

### 4e. Apply-template action

- [ ] **`jobrequisition_apply_template(request, pk)`** — `@tenant_admin_required`, `@require_POST`:
  - Fetch req (tenant-scoped); guard: `obj.status in ("draft","rejected")` only
  - `template_pk = request.POST.get("template_id")` — validate int; fetch `JobDescriptionTemplate`
    (tenant-scoped)
  - Call `apply_template_to_requisition(obj, tmpl)` from services
  - `messages.success(request, f"Template '{tmpl.name}' applied to {obj.number}.")`
  - `write_audit_log(request.user, obj, "update", {"action":"apply_template","template":tmpl.name})`
  - Redirect to `hrm:jobrequisition_detail pk=obj.pk`

### 4f. Clone action (P2 — include in this pass as a simple POST-only view)

- [ ] **`jobrequisition_clone(request, pk)`** — `@login_required`, `@require_POST`:
  - Fetch source req (tenant-scoped)
  - Create a new `JobRequisition` copying all non-workflow fields (title, designation, job_grade,
    template, department, cost_center, location, headcount, req_type, employment_type,
    reason_for_hire, posting_type, hiring_manager, recruiter, priority, salary_min, salary_max,
    salary_currency, estimated_annual_cost, hiring_cost_budget, jd_summary, jd_responsibilities,
    jd_requirements, jd_nice_to_have, notes); set `status="draft"`, clear all `*_at` stamps;
    set `tenant=request.tenant`.
  - New record saved via `.save()` (gets new `number` from `TenantNumbered`).
  - `write_audit_log(request.user, new_req, "create", {"cloned_from": source.number})`
  - `messages.success`; redirect to `hrm:jobrequisition_detail pk=new_req.pk`

- [ ] Add all new imports to `views.py`:
  - From `.models`: `JobDescriptionTemplate`, `JobRequisition`, `RequisitionApproval`,
    `JR_STATUS_CHOICES`, `APPROVAL_STEP_STATUS_CHOICES`, `APPROVER_ROLE_CHOICES`,
    `EMPLOYMENT_TYPE_CHOICES`, `REQ_TYPE_CHOICES`, `PRIORITY_CHOICES`, `POSTING_TYPE_CHOICES`,
    `REASON_FOR_HIRE_CHOICES`
  - From `.forms`: `JobDescriptionTemplateForm`, `JobRequisitionForm`, `RequisitionApprovalForm`
  - From `.services`: `generate_approval_chain`, `apply_template_to_requisition`

---

## 5. URLs (`apps/hrm/urls.py`)

Add the following patterns inside `app_name = "hrm"` (no changes to existing patterns):

- [ ] **JobDescriptionTemplate (5 CRUD):**
  ```python
  path("job-templates/",                      views.jobdescriptiontemplate_list,   name="jobdescriptiontemplate_list"),
  path("job-templates/add/",                  views.jobdescriptiontemplate_create, name="jobdescriptiontemplate_create"),
  path("job-templates/<int:pk>/",             views.jobdescriptiontemplate_detail, name="jobdescriptiontemplate_detail"),
  path("job-templates/<int:pk>/edit/",        views.jobdescriptiontemplate_edit,   name="jobdescriptiontemplate_edit"),
  path("job-templates/<int:pk>/delete/",      views.jobdescriptiontemplate_delete, name="jobdescriptiontemplate_delete"),
  ```

- [ ] **JobRequisition (5 CRUD + 8 workflow + 2 utility):**
  ```python
  path("requisitions/",                                views.jobrequisition_list,          name="jobrequisition_list"),
  path("requisitions/add/",                            views.jobrequisition_create,         name="jobrequisition_create"),
  path("requisitions/<int:pk>/",                       views.jobrequisition_detail,         name="jobrequisition_detail"),
  path("requisitions/<int:pk>/edit/",                  views.jobrequisition_edit,           name="jobrequisition_edit"),
  path("requisitions/<int:pk>/delete/",                views.jobrequisition_delete,         name="jobrequisition_delete"),
  path("requisitions/<int:pk>/submit/",                views.jobrequisition_submit,         name="jobrequisition_submit"),
  path("requisitions/<int:pk>/approve-step/",          views.jobrequisition_approve_step,   name="jobrequisition_approve_step"),
  path("requisitions/<int:pk>/reject/",                views.jobrequisition_reject,         name="jobrequisition_reject"),
  path("requisitions/<int:pk>/return/",                views.jobrequisition_return,         name="jobrequisition_return"),
  path("requisitions/<int:pk>/post/",                  views.jobrequisition_post,           name="jobrequisition_post"),
  path("requisitions/<int:pk>/hold/",                  views.jobrequisition_hold,           name="jobrequisition_hold"),
  path("requisitions/<int:pk>/fill/",                  views.jobrequisition_mark_filled,    name="jobrequisition_mark_filled"),
  path("requisitions/<int:pk>/cancel/",                views.jobrequisition_cancel,         name="jobrequisition_cancel"),
  path("requisitions/<int:pk>/apply-template/",        views.jobrequisition_apply_template, name="jobrequisition_apply_template"),
  path("requisitions/<int:pk>/clone/",                 views.jobrequisition_clone,          name="jobrequisition_clone"),
  ```

- [ ] **RequisitionApproval (2 inline actions — no standalone list):**
  ```python
  path("requisitions/<int:jr_pk>/approval/add/",       views.approval_add,    name="approval_add"),
  path("requisition-approvals/<int:pk>/delete/",        views.approval_delete, name="approval_delete"),
  ```

---

## 6. Admin (`apps/hrm/admin.py`)

- [ ] Register `JobDescriptionTemplate`:
  - `list_display = ["number","name","designation","employment_type","is_active","created_at"]`
  - `list_filter = ["is_active","employment_type"]`
  - `search_fields = ["number","name","designation__name"]`
  - `readonly_fields = ["number","tenant","created_at","updated_at"]`

- [ ] Register `JobRequisition`:
  - `list_display = ["number","title","designation","status","priority","hiring_manager","headcount","created_at"]`
  - `list_filter = ["status","priority","req_type","employment_type"]`
  - `search_fields = ["number","title","location","designation__name"]`
  - `readonly_fields = ["number","tenant","status","submitted_at","approved_at","posted_at","filled_at","created_at","updated_at"]`

- [ ] Register `RequisitionApproval` (inline on `JobRequisition` admin + standalone):
  - `list_display = ["requisition","step_order","approver","approver_role","status","decided_at","decided_by"]`
  - `list_filter = ["status","approver_role"]`
  - `readonly_fields = ["tenant","status","decided_at","decided_by","created_at","updated_at"]`

- [ ] Add all three models to the admin imports.

---

## 7. Migration

- [ ] Run `python manage.py makemigrations hrm` — expect ONE migration file adding:
  - Module-level choice constants (no migration needed — code only)
  - New model `JobDescriptionTemplate` (with `number`, `name`, `designation` FK, `employment_type`,
    `jd_*` fields, `is_active`, indexes)
  - New model `JobRequisition` (with all fields enumerated above, indexes)
  - New model `RequisitionApproval` (with FK to `JobRequisition` + `User` FKs, indexes)
- [ ] Run `python manage.py migrate` — applies cleanly, no data migration needed.
- [ ] Run `python manage.py check` — 0 issues.

---

## 8. Seed (`apps/hrm/management/commands/seed_hrm.py`)

Extend the existing seeder with a `_seed_job_requisition(tenant, *, flush)` function.

- [ ] Add `JobDescriptionTemplate`, `JobRequisition`, `RequisitionApproval` to the `from apps.hrm.models import (...)`
  block at the top of `seed_hrm.py`.

- [ ] Add the three models to the `--flush` delete cascade in `_seed_tenant()`, **before**
  `EmployeeProfile` (since `hiring_manager`/`recruiter` FK it) and `Designation` (since `designation`
  FK it):
  ```python
  # In the flush loop, add before (EmployeeProfile, Designation, JobGrade):
  RequisitionApproval, JobRequisition, JobDescriptionTemplate,
  ```

- [ ] Define a `_seed_job_requisition(tenant, *, flush)` method on `Command`:

  ```python
  def _seed_job_requisition(self, tenant, *, flush):
      if JobRequisition.objects.filter(tenant=tenant).exists():
          self.stdout.write(self.style.NOTICE(
              f"  [skip] Job requisition data already seeded for {tenant.slug}"))
          return

      # Reuse already-seeded designations + employees
      designations = list(Designation.objects.filter(tenant=tenant).order_by("created_at"))
      employees = list(EmployeeProfile.objects.filter(tenant=tenant).order_by("created_at"))
      dept = OrgUnit.objects.filter(tenant=tenant, kind="department").first()

      if not designations or not employees:
          self.stdout.write(self.style.WARNING(
              f"  [skip] No designations or employees — run seed_hrm first for {tenant.slug}"))
          return

      # 1. JD Templates (idempotent via get_or_create keyed on tenant+name)
      tmpl1, _ = JobDescriptionTemplate.objects.get_or_create(
          tenant=tenant, name="Software Engineer — Backend",
          defaults={
              "designation": designations[0],
              "employment_type": "full_time",
              "jd_summary": "Build and maintain scalable backend services.",
              "jd_responsibilities": "- Design REST APIs\n- Write unit tests\n- Participate in code reviews",
              "jd_requirements": "- 3+ years Python/Django\n- SQL databases",
              "jd_nice_to_have": "- Experience with Docker/Kubernetes",
              "is_active": True,
          })

      tmpl2, _ = JobDescriptionTemplate.objects.get_or_create(
          tenant=tenant, name="Engineering Manager",
          defaults={
              "designation": designations[2] if len(designations) > 2 else None,
              "employment_type": "full_time",
              "jd_summary": "Lead a team of 5–8 engineers.",
              "jd_responsibilities": "- Define engineering roadmap\n- Conduct 1:1s\n- Hire and develop talent",
              "jd_requirements": "- 5+ years engineering experience\n- 2+ years people management",
              "jd_nice_to_have": "- MBA or advanced degree",
              "is_active": True,
          })

      # 2. Job Requisitions — check by number before creating (TenantNumbered idempotency pattern)
      jr_data = [
          {
              "title": "Senior Python Developer",
              "designation": designations[1] if len(designations) > 1 else designations[0],
              "department": dept,
              "headcount": 2,
              "req_type": "standard",
              "employment_type": "full_time",
              "reason_for_hire": "new_headcount",
              "posting_type": "external",
              "priority": "high",
              "salary_min": "90000",
              "salary_max": "130000",
              "salary_currency": "USD",
              "hiring_manager": employees[0] if employees else None,
              "recruiter": employees[1] if len(employees) > 1 else None,
              "jd_summary": "Build and maintain backend services using Python/Django.",
              "template": tmpl1,
              "status": "posted",
          },
          {
              "title": "Junior Software Engineer",
              "designation": designations[0],
              "department": dept,
              "headcount": 1,
              "req_type": "backfill",
              "employment_type": "full_time",
              "reason_for_hire": "backfill",
              "posting_type": "both",
              "priority": "medium",
              "salary_min": "60000",
              "salary_max": "85000",
              "salary_currency": "USD",
              "hiring_manager": employees[0] if employees else None,
              "recruiter": employees[1] if len(employees) > 1 else None,
              "status": "draft",
          },
          {
              "title": "Engineering Manager",
              "designation": designations[2] if len(designations) > 2 else designations[0],
              "department": dept,
              "headcount": 1,
              "req_type": "standard",
              "employment_type": "full_time",
              "reason_for_hire": "new_headcount",
              "posting_type": "external",
              "priority": "urgent",
              "salary_min": "130000",
              "salary_max": "180000",
              "salary_currency": "USD",
              "hiring_manager": employees[0] if employees else None,
              "recruiter": employees[1] if len(employees) > 1 else None,
              "template": tmpl2,
              "status": "approved",
          },
      ]
      reqs = []
      for d in jr_data:
          jr = JobRequisition(tenant=tenant, **d)
          jr.save()  # TenantNumbered.save() assigns number; never bare create() for TenantNumbered
          reqs.append(jr)

      # 3. Approval steps — add to the "approved" req to demonstrate the chain
      if reqs:
          approved_req = reqs[2]  # the Engineering Manager req
          from django.contrib.auth import get_user_model
          User = get_user_model()
          admin_user = User.objects.filter(is_superuser=True).first()
          if not RequisitionApproval.objects.filter(requisition=approved_req).exists():
              RequisitionApproval.objects.bulk_create([
                  RequisitionApproval(
                      tenant=tenant, requisition=approved_req,
                      step_order=1, approver=admin_user, approver_role="hr", status="approved",
                  ),
                  RequisitionApproval(
                      tenant=tenant, requisition=approved_req,
                      step_order=2, approver=admin_user, approver_role="executive", status="approved",
                  ),
              ])
  ```

- [ ] Call `self._seed_job_requisition(tenant, flush=options["flush"])` from `handle()` after
  `self._seed_employee_records(tenant, flush=options["flush"])`.

- [ ] Idempotency: the `_seed_job_requisition` function is guarded by
  `JobRequisition.objects.filter(tenant=tenant).exists()` at the top. JD templates use `get_or_create`.
  `JobRequisition` rows cannot use `get_or_create` (no stable unique field other than `number`
  which is auto-assigned); the guard returns early before any `.save()` call — consistent with the
  established HRM seeder pattern.

---

## 9. Templates (`templates/hrm/recruitment/`)

All templates: `{% extends "base.html" %}`, Tailwind design system, Lucide icons. Actions column on
every list: View (eye), Edit (pencil), Delete (trash — POST form + `onclick="return confirm(...)"` +
`{% csrf_token %}`). Detail pages: workflow action buttons in sidebar. Filter bar reflects `request.GET`.

### 9a. `JobDescriptionTemplate` templates

- [ ] **`templates/hrm/recruitment/jobdescriptiontemplate/list.html`**:
  - Page header + "Add Template" button (→ `hrm:jobdescriptiontemplate_create`).
  - Filter bar: search `q`, `designation` select (compare `desig.pk|stringformat:"d"` vs
    `request.GET.designation`), `is_active` select (`"true"`/`"false"`, filter in view).
  - Table columns: Number, Name, Designation (if set), Employment Type, Active (badge), Actions.
  - Empty state + pagination.

- [ ] **`templates/hrm/recruitment/jobdescriptiontemplate/detail.html`**:
  - Breadcrumb: HRM › Job Templates › `{obj.number}`.
  - Sidebar actions: Edit, Delete (POST+confirm + guard if linked reqs), Back to Job Templates.
  - Cards:
    1. **Details**: Number, Name, Designation link, Employment Type, Is Active.
    2. **Job Description**: collapsible sections for Summary, Responsibilities, Requirements,
       Nice-to-Have — each rendered if non-blank.
    3. **Linked Requisitions** table (from `linked_reqs`): Number, Title, Status badge, Date.
  - "Apply to a Requisition" hint link → `hrm:jobrequisition_list`.

- [ ] **`templates/hrm/recruitment/jobdescriptiontemplate/form.html`**:
  - Fields: `name`, `designation`, `employment_type`, `jd_summary` (textarea), `jd_responsibilities`
    (textarea), `jd_requirements` (textarea), `jd_nice_to_have` (textarea), `is_active`.
  - Submit + Cancel (→ `hrm:jobdescriptiontemplate_list`).

### 9b. `JobRequisition` templates

- [ ] **`templates/hrm/recruitment/jobrequisition/list.html`**:
  - Page header + "Add Requisition" button.
  - Filter bar: search `q`, status select (from `status_choices`), priority select (from
    `priority_choices`), department select (compare `dept.pk|stringformat:"d"`), req_type select,
    employment_type select. All compared by exact string or `|stringformat:"d"` (per CLAUDE.md
    filter rules).
  - Table columns: Number (link to detail), Title, Designation, Department, Priority (badge:
    urgent=red, high=amber, medium=blue, low=slate), Status (badge: draft=slate, submitted=amber,
    pending_approval=amber, approved=green, posted=blue, on_hold=yellow, filled=green,
    cancelled=red, rejected=red), Headcount, Hiring Manager, Target Start, Actions (view/edit/delete;
    edit + delete shown only when `status in ("draft","rejected")`).
  - Overdue indicator: if `obj.is_overdue`, show a small red "Overdue" pill beside the target date.
  - Empty state + pagination.

- [ ] **`templates/hrm/recruitment/jobrequisition/detail.html`** — the hub page:
  - Breadcrumb: HRM › Requisitions › `{obj.number}`.
  - **Sidebar** (workflow actions — all POST forms with `{% csrf_token %}`):
    - "Submit for Approval" → `hrm:jobrequisition_submit` (show if `can_submit`)
    - "Post Requisition" → `hrm:jobrequisition_post` (show if `can_post`)
    - "Place on Hold" → `hrm:jobrequisition_hold` (show if `can_hold`)
    - "Mark as Filled" → `hrm:jobrequisition_mark_filled` (show if `can_fill`)
    - "Cancel" → `hrm:jobrequisition_cancel` (show if `can_cancel`) + `onclick="return confirm('Cancel this requisition?')"`
    - "Clone" → `hrm:jobrequisition_clone` (always shown — POST form)
    - Edit button → `hrm:jobrequisition_edit` (shown if `status in ("draft","rejected")`)
    - Delete → POST form (shown if `status == "draft"`)
    - Back to Requisitions link.
  - **Status bar**: current status badge + `approval_progress` "(N of M steps approved)".
  - **Cards:**
    1. **Requisition Info** (`detail-grid`): Number, Title, Status badge, Priority badge, Req Type,
       Employment Type, Reason for Hire, Headcount, Location, Posting Type.
    2. **Team**: Hiring Manager (link to employee detail), Recruiter.
    3. **Timeline & Budget**: Target Start Date (red if `is_overdue`), Salary Min–Max (currency),
       Estimated Annual Cost, Hiring Cost Budget.
    4. **Organization**: Designation (link), Job Grade, Department (link), Cost Center.
    5. **Job Description** (4 collapsible subsections: Summary / Responsibilities / Requirements /
       Nice-to-Have — each rendered only if non-blank; show Template badge if `obj.template` set).
    6. **Approval Chain** (hub section — mirrors clearance items hub on separation case):
       - Table of `approvals` rows: Step, Approver Role, Approver, Status badge (pending=amber,
         approved=green, rejected=red, returned=yellow), Decided By, Decided At, Comments.
       - For the current pending step (if `can_approve`): inline Approve / Reject / Return buttons
         (POST forms with `{% csrf_token %}`; Reject and Return show a `<textarea name="comments">`
         prompt via `onclick` or a small inline form).
       - "Add Approval Step" form (from `approval_form`, `RequisitionApprovalForm`) — shown only
         when `status == "draft"` (admin-only action; rendered for all users, server enforces the
         `@tenant_admin_required` guard).
       - Delete step button (POST to `hrm:approval_delete`) — shown per-row when `status == "draft"`.
    7. **Audit Notes**: `obj.notes` textarea display.
  - Apply-template quick action (shown when `status in ("draft","rejected")`): select `<select>`
    of active JD templates + POST to `hrm:jobrequisition_apply_template`.

- [ ] **`templates/hrm/recruitment/jobrequisition/form.html`**:
  - Breadcrumb: HRM › Requisitions › Add / Edit.
  - Two-column layout with fieldset groups:
    1. **Basics**: `title`, `designation`, `job_grade`, `template`, `department`, `cost_center`,
       `location`.
    2. **Type & Count**: `headcount`, `req_type`, `employment_type`, `reason_for_hire`,
       `is_replacement_for`, `posting_type`, `priority`.
    3. **Hiring Team**: `hiring_manager`, `recruiter`.
    4. **Timeline & Budget**: `target_start_date`, `salary_min`, `salary_max`, `salary_currency`,
       `estimated_annual_cost`, `hiring_cost_budget`.
    5. **Job Description** (collapsible fieldset): `jd_summary`, `jd_responsibilities`,
       `jd_requirements`, `jd_nice_to_have` (all `<textarea>`).
    6. **Notes**: `notes`.
  - Note below `template` field: "Selecting a template pre-fills the Job Description fields
    when you save with 'Apply Template'."
  - Two submit buttons: primary "Save" + secondary "Save & Apply Template" (`name="apply_template" value="1"`).
  - Cancel → `hrm:jobrequisition_list`.

---

## 10. Wire-up (`apps/core/navigation.py`)

- [ ] Add `"3.5"` entry to `LIVE_LINKS` mapping all 5 NavERP.md 3.5 bullets to live pages.
  Exact NavERP.md bullet text (from `NavERP.md` §3.5):
  - "Job Posting" → `"hrm:jobrequisition_list"`
  - "Approval Workflow" → `"hrm:jobrequisition_list?status=pending_approval"` (filtered view)
  - "Budget Management" → `"hrm:jobrequisition_list"`
  - "Job Templates" → `"hrm:jobdescriptiontemplate_list"`
  - "Requisition Tracking" → `"hrm:jobrequisition_list"`

  ```python
  # 3.5 Job Requisition — authorization to hire; approval chain; JD templates.
  "3.5": {
      "Job Posting": "hrm:jobrequisition_list",                         # bullet
      "Approval Workflow": "hrm:jobrequisition_list?status=pending_approval",  # bullet (filtered pending)
      "Budget Management": "hrm:jobrequisition_list",                   # bullet (salary/cost fields on req)
      "Job Templates": "hrm:jobdescriptiontemplate_list",               # bullet
      "Requisition Tracking": "hrm:jobrequisition_list",                # bullet (status tracking on list)
  },
  ```

  Note: `_safe_reverse` in navigation.py handles `?query` suffixes correctly (splits at `?`).

---

## 11. Verify

- [ ] `python manage.py makemigrations hrm` — confirm ONE new migration; no unapplied changes
  (`--check` passes after `migrate`).
- [ ] `python manage.py migrate` — applies cleanly to `nav_erp` MariaDB.
- [ ] `python manage.py seed_hrm` — first run: creates 2 JD templates + 3 requisitions + 2 approval
  rows; prints login instructions.
- [ ] `python manage.py seed_hrm` (second run) — `[skip]` message fires; no new rows, no
  `IntegrityError` (idempotency).
- [ ] `python manage.py check` — 0 issues.
- [ ] **Smoke sweep** — log in as `admin_acme` (tenant admin) and verify each new URL → 200/302:
  - [ ] `hrm:jobrequisition_list` → 200 (seeded rows visible)
  - [ ] `hrm:jobrequisition_create` → 200 (form renders; FK dropdowns scoped)
  - [ ] `hrm:jobrequisition_detail pk=<posted_req>` → 200 (hub renders all cards + approval chain)
  - [ ] `hrm:jobrequisition_edit pk=<draft_req>` → 200
  - [ ] `hrm:jobrequisition_submit pk=<draft_req>` → POST → 302 (status becomes pending_approval)
  - [ ] `hrm:jobrequisition_approve_step pk=<pending_req>` → POST → 302 (step approved)
  - [ ] `hrm:jobrequisition_post pk=<approved_req>` → POST → 302 (status → posted)
  - [ ] `hrm:jobrequisition_hold pk=<approved_or_posted_req>` → POST → 302
  - [ ] `hrm:jobrequisition_mark_filled pk=<posted_req>` → POST → 302
  - [ ] `hrm:jobrequisition_cancel pk=<any_non_final_req>` → POST → 302
  - [ ] `hrm:jobrequisition_clone pk=<any_req>` → POST → 302 (new draft created)
  - [ ] `hrm:jobrequisition_delete pk=<draft_req>` → POST → 302
  - [ ] `hrm:jobdescriptiontemplate_list` → 200 (seeded templates visible)
  - [ ] `hrm:jobdescriptiontemplate_create` → 200
  - [ ] `hrm:jobdescriptiontemplate_detail pk=<seeded>` → 200
  - [ ] `hrm:jobdescriptiontemplate_edit pk=<seeded>` → 200
  - [ ] `hrm:approval_add jr_pk=<draft_req>` → POST → 302 (step added)
  - [ ] `hrm:approval_delete pk=<draft_step>` → POST → 302
  - [ ] `hrm:jobrequisition_apply_template pk=<draft_req>` → POST → 302 (JD fields filled)
- [ ] **Cross-tenant IDOR → 404**: GET `hrm:jobrequisition_detail pk=<globex_req>` logged in as
  `admin_acme` → 404.
- [ ] **Cross-tenant IDOR → 404**: same for `hrm:jobdescriptiontemplate_detail`.
- [ ] **Workflow gate**: POST `hrm:jobrequisition_submit` as a regular member (not tenant admin) → 403
  (enforced by `@tenant_admin_required`).
- [ ] **No template comment leaks**: grep all new `.html` files for `{#` or `{% comment`.
- [ ] **Sidebar**: log in as `admin_acme`; open HRM → sub-module 3.5 Job Requisition → confirm
  "Job Posting", "Approval Workflow", "Budget Management", "Job Templates", "Requisition Tracking"
  all show as **Live** (not "On the roadmap").
- [ ] **Filter verify**: on `jobrequisition_list`, apply `?status=pending_approval` →
  only pending_approval rows shown; `?priority=urgent` → only urgent rows.
- [ ] **Approval Workflow filter**: the "Approval Workflow" sidebar link with `?status=pending_approval`
  resolves correctly via `_safe_reverse` (navigation.py split at `?`).

---

## 12. Close-out

- [ ] Run **code-reviewer** agent — apply findings, one commit per file.
- [ ] Run **explorer** agent — apply findings, one commit per file.
- [ ] Run **frontend-reviewer** agent — focus: approval-chain hub card, status/priority badge color
  consistency with existing HRM badges, filter bar compare patterns, "Apply Template" UX,
  collapsible JD fieldsets; one commit per file.
- [ ] Run **performance-reviewer** agent — focus: `jobrequisition_list` select_related coverage;
  `jobrequisition_detail` approval rows N+1 (`select_related("approver","decided_by")`);
  `is_overdue` / `approval_progress` / `current_approval_step` properties called per-row in list
  (consider annotating or computing in Python loop instead of per-object `.count()`).
- [ ] Run **qa-smoke-tester** agent — apply findings, one commit per file.
- [ ] Run **security-reviewer** agent — focus: `@tenant_admin_required` on all workflow write views;
  `status`/`submitted_at`/`approved_at` cannot be set via crafted POST (excluded from form);
  cross-tenant guard on `RequisitionApproval.clean()`; `approval_add` verifies `jr_pk` is
  tenant-scoped before creating step; clone copies no workflow-owned fields.
- [ ] Run **test-writer** agent — apply output, one commit per file. Tests should cover:
  - `JobRequisition` model: auto-number JR-prefix, `__str__`, `clean()` salary validation,
    `clean()` headcount validation, `is_overdue` property, `approval_progress` property,
    `current_approval_step` property.
  - `JobDescriptionTemplate` model: auto-number JDTMPL-prefix, `__str__`, unique_together.
  - `RequisitionApproval` model: `unique_together` (requisition+step_order), `clean()` step_order
    validation, `__str__`.
  - `generate_approval_chain` service: idempotent (second call returns existing rows),
    creates 2 default steps, raises `ValueError` if req not `"draft"`.
  - `apply_template_to_requisition` service: copies jd_* fields; does not overwrite employment_type.
  - Form exclusions: POST with `status`, `submitted_at`, `approved_at` → fields ignored.
  - CRUD views 200/302 for both entities.
  - Workflow state-machine views: submit → pending_approval, approve_step advances, final step → approved,
    reject → rejected, return → draft, post → posted, hold → on_hold, fill → filled, cancel.
  - Delete guards: non-draft JR → 403/redirect; template with linked reqs → blocked delete.
  - Edit guard: non-draft/non-rejected JR → blocked edit.
  - Cross-tenant IDOR → 404 for both entities + approval rows.
  - `@tenant_admin_required` on submit/approve_step/reject/return/post/hold/fill/cancel/approval_add/approval_delete → 403 for non-admin.
  - Seeder idempotency.
- [ ] Update **`.claude/skills/hrm/SKILL.md`** — add `JobDescriptionTemplate`, `JobRequisition`,
  `RequisitionApproval` to the Models section; add the 17 new url names to the URLs section; add
  `recruitment/jobrequisition/` and `recruitment/jobdescriptiontemplate/` to the Templates section;
  add `_seed_job_requisition` to the Seeder section; update `LIVE_LINKS["3.5"]` in sidebar wiring.
- [ ] Mark 3.5 as delivered in **`README.md`** roadmap.

---

## Later passes / deferred

- **Candidate linkage (3.6)** — `Candidate.requisition` FK arrives in 3.6; `JobRequisition` needs
  no changes when it lands. The `headcount` field is in place for the fill-counter logic.
- **Auto-close when headcount filled** — when 3.6 increments a `hires_made` counter, compare to
  `headcount` and auto-set `status = "filled"`. Deferred to 3.6.
- **Interview linkage (3.7) / Offer linkage (3.8)** — separate later sub-modules; no FK additions
  to `JobRequisition` needed now.
- **Condition-based approval routing** — different chains triggered by headcount > N, salary >
  threshold, or department. Needs a workflow-engine configuration model (module 0.11 pass). Deferred.
- **Approval delegation** — `delegated_to` FK on `RequisitionApproval`. Low MVP value; deferred.
- **Re-approval on salary change** — if salary range is edited post-approval, restart workflow.
  Deferred to a hardening pass.
- **External job board posting** — LinkedIn/Indeed API integration. Deferred.
- **AI JD generation / bias detection** — Greenhouse / BambooHR AI feature. External API; deferred.
- **Internal career portal** — candidate-facing public view of posted requisitions. Deferred to 3.6
  Candidate Management.
- **Requisition analytics / time-to-fill metrics** — deferred to 3.32 Analytics Dashboard.
- **GL / budget integration** — informational only at this stage; salary cost posts in payroll
  (accounting module / HRM 3.13+).
- **Evergreen requisition auto-reopen** — `req_type=evergreen` choice is present; auto-reopen logic
  (when `status=filled`, re-open to `posted`) deferred to a business-rule hardening pass.
- **`is_replacement_for` FK upgrade** — currently a `CharField`; upgrade to
  `FK("hrm.EmployeeProfile", null=True, blank=True)` when 3.6 is built and a clear departing-
  employee concept is established.

---

## Review notes

(filled in at the end)

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

**Delivered (2026-06-26).** HRM 3.5 Job Requisition built end-to-end, extending `apps/hrm`:
- **Models (migration `0010`):** `JobDescriptionTemplate` (`JDTMPL-`), `JobRequisition` (`JR-`) hub with the
  9-state lifecycle + `clean()` (salary_min≤max, headcount≥1) + 3 derived props (`is_overdue`,
  `approval_progress`, `current_approval_step`), and `RequisitionApproval` child (immutable audit trail,
  `unique_together(requisition, step_order)`). All workflow fields `editable=False`.
- **Services:** `generate_approval_chain` (idempotent default HR→Executive chain) + `apply_template_to_requisition`
  (copy-on-apply JD, leaves `employment_type`).
- **Forms:** workflow fields excluded (mirrors `SeparationCaseForm`); FK querysets tenant-scoped; `approver`
  scoped to tenant users.
- **Views/URLs:** full CRUD for both entities + 8 workflow POSTs (submit/approve-step/reject/return/post/hold/
  fill/cancel) + apply-template + clone + inline approval add/delete. All writes `@tenant_admin_required`+`@require_POST`,
  audited. 17 new url names.
- **Templates:** `templates/hrm/recruitment/{jobrequisition,jobdescriptiontemplate}/{list,detail,form}.html` —
  approval chain renders inline on the requisition hub.
- **Wire-up:** `LIVE_LINKS["3.5"]` (all 5 NavERP bullets live; Approval Workflow deep-links `?status=pending_approval`).
- **Seeder:** `_seed_job_requisition` (2 templates + 3 reqs across the lifecycle + a 2-step approved chain),
  idempotent + `--flush`.
- **Verify:** `makemigrations`/`migrate`/`check` clean; seed idempotent; smoke sweep — every page 200, full
  state-machine POSTs 302, cross-tenant IDOR → 404, non-admin write → 403, no template-comment leaks. **ALL PASS.**

**Deferred:** Candidate/Interview/Offer linkage (3.6–3.8), condition-based approval routing, delegation,
re-approval on salary change, external job-board posting, AI JD generation, internal career portal,
`is_replacement_for` FK upgrade, evergreen auto-reopen. (See "Later passes / deferred" above.)

**Pending close-out:** review-agent sequence (code-reviewer → explorer → frontend-reviewer → performance-reviewer →
qa-smoke-tester → security-reviewer → test-writer) + HRM skill update.

---
# CRM Sub-module 1.3 — Marketing Automation (crm) — plan from research-crm-marketing.md  (2026-06-26)

**Extending `apps/crm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py`
are already in place. The existing `Campaign` (CAM-) model is enhanced in-place; five new models are
added to `apps/crm/models.py`. The next migration is `0006`. Template sub-module folder: `templates/crm/marketing/`.

**Approved build scope — exactly 6 entities (fixed):**

1. **`Campaign`** (CAM-, existing, ENHANCE) — add `objective`, `parent_campaign`, `utm_source`, `utm_medium`, `utm_campaign`
2. **`CampaignMember`** (plain, NOT TenantNumbered) — per-recipient membership + status tracking
3. **`EmailTemplate`** (EMT-, TenantNumbered) — reusable HTML email template
4. **`EmailCampaign`** (BLAST-, TenantNumbered) — email blast/drip/A-B send record + aggregate metrics
5. **`LandingPage`** (LP-, TenantNumbered) — campaign landing page with public token + embedded form config
6. **`FormSubmission`** (plain, READ-MOSTLY) — captured lead data; list + detail + delete + convert only

---

## 0. Template folder decision

1.3 is a multi-entity sub-module with 5 primary entities. Per CLAUDE.md rule 2, the folder shape is
`templates/crm/marketing/<entity>/<page>.html`. The existing campaign templates at
`templates/crm/marketing/campaign/{list,detail,form}.html` must be **recreated** (they need the new
fields: `objective`, `parent_campaign`, `utm_*` in the form; member/email stats in the detail).

- [ ] Template paths to create (or recreate):
  - `marketing/campaign/{list,detail,form}.html` — recreate with new fields
  - `marketing/campaignmember/{list,detail,form}.html` — CampaignMember CRUD (form = add member)
  - `marketing/emailtemplate/{list,detail,form}.html` — EmailTemplate CRUD
  - `marketing/emailcampaign/{list,detail,form}.html` — EmailCampaign CRUD + send action
  - `marketing/landingpage/{list,detail,form}.html` — LandingPage CRUD
  - `marketing/formsubmission/{list,detail}.html` — FormSubmission (no create/edit form)
  - `marketing/landing_public.html` — standalone public page (extends `base_public.html` or minimal base; no auth required)

---

## 1. Models (enhance/add in `apps/crm/models.py` after existing `Campaign`)

### 1a. Enhance `Campaign` (existing CAM- model at line ~103, migration `0006`)

Drivers from research: 1.3.A goal/objective (HubSpot/Pardot/Marketo), campaign hierarchy (HubSpot
campaign grouping), UTM attribution from email blast and landing pages.

- [ ] Add to `Campaign` model:
  - `OBJECTIVE_CHOICES` module-level constant (or inner class):
    ```
    ("awareness", "Brand Awareness"),
    ("lead_gen", "Lead Generation"),
    ("nurture", "Nurture"),
    ("conversion", "Conversion"),
    ("event", "Event Promotion"),
    ("retention", "Retention"),
    ```
  - `objective` — `CharField(max_length=20, choices=OBJECTIVE_CHOICES, blank=True)`
    (driver: 1.3.A campaign goal field — HubSpot, Pardot, Marketo)
  - `parent_campaign` — `ForeignKey("crm.Campaign", on_delete=SET_NULL, null=True, blank=True,
    related_name="child_campaigns")` (driver: 1.3.A multi-channel asset grouping — HubSpot hierarchy)
  - `utm_source` — `CharField(max_length=120, blank=True)` (driver: 1.3.C UTM attribution)
  - `utm_medium` — `CharField(max_length=120, blank=True)`
  - `utm_campaign` — `CharField(max_length=120, blank=True)`
  - Keep all existing fields (`name`, `type`, `status`, `start_date`, `end_date`, `budget_planned`,
    `budget_actual`, `expected_revenue`, `actual_revenue`, `target_size`, `owner`, `description`)
    and `@property roi` unchanged.
  - Add DB index: `("tenant", "objective")` — `crm_cam_tnt_obj_idx`
  - Member/response stats (influenced_count, converted_count, member_count) are computed in the
    detail VIEW via `.aggregate()` over `CampaignMember` — NOT stored on Campaign.

### 1b. `CampaignMember` (plain, tenant-scoped, NOT TenantNumbered)

Drivers: 1.3.A target list + per-member status (HubSpot "Campaign Contacts", Marketo "Program Members",
Pardot "List Members"); 1.3.B per-recipient email tracking (status lifecycle).

- [ ] Add `CampaignMember(models.Model)`:
  - `tenant` FK → `core.Tenant` (CASCADE, `related_name="+"`, `db_index=True`)
  - `campaign` FK → `"crm.Campaign"` (CASCADE, `related_name="members"`)
  - `party` FK → `"core.Party"` (SET_NULL, null=True, blank=True, `related_name="campaign_memberships"`)
    (driver: converted contacts are `core.Party`)
  - `lead` FK → `"crm.Lead"` (SET_NULL, null=True, blank=True, `related_name="campaign_memberships"`)
    (driver: pre-conversion prospects are `crm.Lead`)
  - `member_name` — `CharField(max_length=255)` (denormalized at add-time; survives lead rename)
  - `member_email` — `EmailField(max_length=255)` (denormalized at add-time for tracking)
  - `STATUS_CHOICES`:
    ```
    ("targeted", "Targeted"),
    ("sent", "Sent"),
    ("opened", "Opened"),
    ("clicked", "Clicked"),
    ("responded", "Responded"),
    ("converted", "Converted"),
    ("bounced", "Bounced"),
    ("unsubscribed", "Unsubscribed"),
    ```
  - `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="targeted")`
  - `responded_at` — `DateTimeField(null=True, blank=True)` — system-stamped in `save()` when
    `status in ("responded", "converted")` and `responded_at is None`; EXCLUDED from forms
    (driver: 1.3.B per-recipient tracking — Marketo, HubSpot, Klaviyo)
  - `notes` — `TextField(blank=True)`
  - `created_at` — `DateTimeField(auto_now_add=True)`
  - `updated_at` — `DateTimeField(auto_now=True)`
  - `save()` override: stamp `responded_at` when status enters responded/converted
  - `Meta.ordering = ["-created_at"]`
  - `unique_together = ("tenant", "campaign", "party")` — one party membership per campaign
    (Note: party can be null; constraint applies to non-null rows — add a DB-level partial
    unique constraint OR accept that null rows are excluded from the unique_together check,
    which is Django's default behavior. Document this.)
  - DB indexes:
    - `("tenant", "campaign", "status")` — `crm_cm_tnt_cam_status_idx`
    - `("tenant", "status")` — `crm_cm_tnt_status_idx`
    - `("tenant", "campaign", "lead")` — `crm_cm_tnt_cam_lead_idx`
  - `__str__`: `f"{self.member_name} ({self.get_status_display()}) — {self.campaign}"`
  - **Reuses**: `core.Party` (contacts), `crm.Lead` (prospects), `crm.Campaign` (parent).
    Does NOT reuse `TenantNumbered` (no auto-number needed; rows identified by campaign+party/lead).

### 1c. `EmailTemplate` (EMT-, TenantNumbered)

Drivers: 1.3.B HTML email template builder — all 10 leaders; raw HTML now, visual editor = later.

- [ ] Add `EmailTemplate(TenantNumbered)`:
  - `NUMBER_PREFIX = "EMT"`
  - `CATEGORY_CHOICES`:
    ```
    ("newsletter", "Newsletter"),
    ("promotional", "Promotional"),
    ("transactional", "Transactional"),
    ("drip", "Drip"),
    ("announcement", "Announcement"),
    ```
  - `name` — `CharField(max_length=255)`
  - `category` — `CharField(max_length=20, choices=CATEGORY_CHOICES, default="newsletter")`
    (driver: Mailchimp/HubSpot template categorization)
  - `subject` — `CharField(max_length=255)` — default subject line (merge-tag-aware)
    (driver: all leaders; rename from research's `subject_default` for clarity)
  - `preheader` — `CharField(max_length=255, blank=True)` — inbox preview snippet
    (driver: Mailchimp, Klaviyo, Brevo — inbox preview text)
  - `body` — `TextField(blank=True)` — raw HTML; list view defers rendering (no body on list QS)
    (driver: 1.3.B HTML template body; merge vars like `{{ contact.first_name }}`)
  - `from_name` — `CharField(max_length=120, blank=True)` (driver: per-template sender identity)
  - `from_email` — `EmailField(blank=True)` (driver: all leaders)
  - `is_active` — `BooleanField(default=True)`
  - `owner` FK → `settings.AUTH_USER_MODEL` (SET_NULL, null=True, blank=True,
    `related_name="crm_email_templates"`)
  - `Meta.ordering = ["-created_at"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "category")` — `crm_emt_tnt_category_idx`
    - `("tenant", "is_active")` — `crm_emt_tnt_active_idx`
  - `__str__`: `f"{self.number} · {self.name}"`
  - **Reuses**: `TenantNumbered` (from existing `crm` abstract base). Adds HTML body + category.

### 1d. `EmailCampaign` (BLAST-, TenantNumbered)

Drivers: 1.3.B email blast (Mailchimp, HubSpot, Pardot), drip/A-B via `send_type` + `variant_template`
(folded from research's separate DripStep/ABVariant tables per approved build scope).

- [ ] Add `EmailCampaign(TenantNumbered)`:
  - `NUMBER_PREFIX = "BLAST"`
  - `SEND_TYPE_CHOICES`:
    ```
    ("one_time", "One-Time Blast"),
    ("drip", "Drip Sequence"),
    ("ab_test", "A/B Test"),
    ```
  - `STATUS_CHOICES`:
    ```
    ("draft", "Draft"),
    ("scheduled", "Scheduled"),
    ("sending", "Sending"),
    ("sent", "Sent"),
    ("paused", "Paused"),
    ("cancelled", "Cancelled"),
    ```
  - `name` — `CharField(max_length=255)`
  - `campaign` FK → `"crm.Campaign"` (CASCADE, `related_name="email_campaigns"`)
    (driver: 1.3.A multi-asset grouping under one Campaign — HubSpot)
  - `template` FK → `"crm.EmailTemplate"` (SET_NULL, null=True, blank=True,
    `related_name="email_campaigns"`) (driver: reusable template; can be null if A/B)
  - `variant_template` FK → `"crm.EmailTemplate"` (SET_NULL, null=True, blank=True,
    `related_name="+"`) (driver: A/B test variant template — Mailchimp, HubSpot, Klaviyo)
  - `is_ab_test` — `BooleanField(default=False)` (driver: A/B test flag, folded per scope)
  - `send_type` — `CharField(max_length=10, choices=SEND_TYPE_CHOICES, default="one_time")`
  - `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")`
  - `scheduled_at` — `DateTimeField(null=True, blank=True)` (driver: scheduled blast — all leaders)
  - `sent_at` — `DateTimeField(null=True, blank=True)` — SYSTEM-MANAGED; EXCLUDED from forms;
    stamped in `emailcampaign_send` view action (driver: 1.3.B send record — Mailchimp, HubSpot)
  - **Metric counter fields — ALL system-managed, ALL EXCLUDED from forms:**
    - `recipients_count` — `PositiveIntegerField(default=0)`
    - `sent_count` — `PositiveIntegerField(default=0)`
    - `opened_count` — `PositiveIntegerField(default=0)`
    - `clicked_count` — `PositiveIntegerField(default=0)`
    - `bounced_count` — `PositiveIntegerField(default=0)`
    - `unsubscribed_count` — `PositiveIntegerField(default=0)`
    (driver: 1.3.B aggregate metrics — Mailchimp, HubSpot, Pardot, Klaviyo, Brevo)
  - `owner` FK → `settings.AUTH_USER_MODEL` (SET_NULL, null=True, blank=True,
    `related_name="crm_email_campaigns"`)
  - `@property delivered_count` — `recipients_count - bounced_count` (Decimal-safe int diff)
  - `@property open_rate` — `Decimal(opened_count) / Decimal(delivered_count) * 100` if delivered > 0 else `None`
  - `@property click_rate` — `Decimal(clicked_count) / Decimal(delivered_count) * 100` if delivered > 0 else `None`
  - `@property bounce_rate` — `Decimal(bounced_count) / Decimal(recipients_count) * 100` if recipients > 0 else `None`
  - `Meta.ordering = ["-created_at"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "status")` — `crm_blast_tnt_status_idx`
    - `("tenant", "campaign")` — `crm_blast_tnt_campaign_idx`
    - `("tenant", "send_type")` — `crm_blast_tnt_sendtype_idx`
  - `__str__`: `f"{self.number} · {self.name}"`
  - **Reuses**: `crm.Campaign` (parent FK), `crm.EmailTemplate` (template + variant_template),
    `settings.AUTH_USER_MODEL`. Does NOT separately model DripStep/ABVariant (folded).

### 1e. `LandingPage` (LP-, TenantNumbered)

Drivers: 1.3.C landing page record (HubSpot, Unbounce, ActiveCampaign, Brevo, GetResponse); public
token access; lead routing; form field configuration; submission counter.

- [ ] Add `LandingPage(TenantNumbered)`:
  - `NUMBER_PREFIX = "LP"`
  - `STATUS_CHOICES`:
    ```
    ("draft", "Draft"),
    ("published", "Published"),
    ("archived", "Archived"),
    ```
  - `name` — `CharField(max_length=255)`
  - `campaign` FK → `"crm.Campaign"` (SET_NULL, null=True, blank=True,
    `related_name="landing_pages"`) (driver: 1.3.A multi-asset attribution — HubSpot, Marketo)
  - `slug` — `SlugField(max_length=100, blank=True)` — URL-safe; unique per tenant; used in admin
    context only (public access uses `public_token`)
  - `public_token` — `CharField(max_length=32, unique=True, editable=False)` — auto-assigned via
    `secrets.token_urlsafe(16)` in `save()` when blank; the token used in the public URL
    `p/<str:token>/`; EXCLUDED from forms (driver: Unbounce/HubSpot unique page URL)
  - `headline` — `CharField(max_length=255)` (driver: landing page headline — Unbounce, HubSpot)
  - `subheadline` — `CharField(max_length=255, blank=True)`
  - `body` — `TextField(blank=True)` — page body; rendered publicly via `|linebreaks` NEVER `|safe`
    (SECURITY: XSS prevention — never render as raw HTML on the public page)
    (driver: 1.3.C page content — Unbounce, HubSpot, Brevo)
  - `capture_phone` — `BooleanField(default=False)` (driver: 1.3.C configurable form fields)
  - `capture_company` — `BooleanField(default=False)`
  - `capture_message` — `BooleanField(default=False)`
  - `cta_label` — `CharField(max_length=60, default="Submit")` (driver: 1.3.C CTA button label)
  - `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="draft")`
    (driver: only `published` pages render publicly)
  - `routing_owner` FK → `settings.AUTH_USER_MODEL` (SET_NULL, null=True, blank=True,
    `related_name="crm_landing_page_routing"`) (driver: 1.3.C lead routing to a default owner —
    Zoho, HubSpot, Pardot)
  - `lead_source` — `CharField(max_length=20, choices=Lead.SOURCE_CHOICES, blank=True)`
    (driver: tag submissions with a lead source for the CRM Lead created on convert)
  - `submission_count` — `PositiveIntegerField(default=0)` — SYSTEM-MANAGED; EXCLUDED from forms;
    bumped via `F()` expression in the public POST view (driver: 1.3.C form submissions counter)
  - `owner` FK → `settings.AUTH_USER_MODEL` (SET_NULL, null=True, blank=True,
    `related_name="crm_landing_pages"`)
  - `save()` override: generate `public_token = secrets.token_urlsafe(16)` if blank
  - `Meta.ordering = ["-created_at"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "status")` — `crm_lp_tnt_status_idx`
    - `("tenant", "campaign")` — `crm_lp_tnt_campaign_idx`
    - `public_token` covered by `unique=True`
  - `__str__`: `f"{self.number} · {self.name}"`
  - **Reuses**: `crm.Campaign` (FK), `crm.Lead.SOURCE_CHOICES` (lead_source), `settings.AUTH_USER_MODEL`.
    Adds: public_token (secrets), capture_* bools, submission_count (F()-bumped).

### 1f. `FormSubmission` (plain, tenant-scoped, READ-MOSTLY)

Drivers: 1.3.C form submission capture (HubSpot, Pardot, Zoho, Marketo, ActiveCampaign); UTM attribution;
web-to-lead conversion.

- [ ] Add `FormSubmission(models.Model)`:
  - `tenant` FK → `core.Tenant` (CASCADE, `related_name="+"`, `db_index=True`)
  - `landing_page` FK → `"crm.LandingPage"` (CASCADE, `related_name="submissions"`)
  - `name` — `CharField(max_length=255)`
  - `email` — `EmailField(max_length=255)`
  - `phone` — `CharField(max_length=40, blank=True)`
  - `company` — `CharField(max_length=255, blank=True)`
  - `message` — `TextField(blank=True)`
  - `STATUS_CHOICES`:
    ```
    ("new", "New"),
    ("routed", "Routed"),
    ("converted", "Converted"),
    ("spam", "Spam"),
    ```
  - `status` — `CharField(max_length=12, choices=STATUS_CHOICES, default="new")`
  - `routed_to` FK → `settings.AUTH_USER_MODEL` (SET_NULL, null=True, blank=True,
    `related_name="crm_routed_submissions"`) (driver: 1.3.C lead routing — Zoho, HubSpot, Pardot)
  - `converted_lead` FK → `"crm.Lead"` (SET_NULL, null=True, blank=True,
    `related_name="form_submissions"`) (driver: 1.3.C auto-lead creation — HubSpot, Pardot, Zoho)
  - `ip_address` — `GenericIPAddressField(null=True, blank=True)` (driver: 1.3.C spam/bot detection)
  - `created_at` — `DateTimeField(auto_now_add=True)`
  - `Meta.ordering = ["-created_at"]`
  - DB indexes:
    - `("tenant", "landing_page", "status")` — `crm_fs_tnt_lp_status_idx`
    - `("tenant", "status")` — `crm_fs_tnt_status_idx`
    - `("tenant", "created_at")` — `crm_fs_tnt_created_idx`
  - `__str__`: `f"{self.name} <{self.email}> ({self.get_status_display()})"`
  - **NO create/edit form** — submissions arrive ONLY via the public endpoint `landing_public(token)`.
    The internal views are: list + detail + delete + `formsubmission_convert` action.
  - **Reuses**: `crm.LandingPage` (parent FK), `crm.Lead` (converted_lead), `settings.AUTH_USER_MODEL`.

---

## 2. Forms (`apps/crm/forms.py`)

All internal forms exclude system-managed/auto fields. The public form is a plain `forms.Form` (no model form;
submission saved manually in the view).

- [ ] **`CampaignForm`** (enhance existing):
  - Add `objective`, `parent_campaign`, `utm_source`, `utm_medium`, `utm_campaign` to `fields`
  - `__init__`: scope `parent_campaign` queryset →
    `Campaign.objects.filter(tenant=self.tenant).order_by("-created_at")` (exclude self on edit by
    excluding `instance.pk` if `self.instance.pk`)
  - Excluded (unchanged): `tenant`, `number`

- [ ] **`CampaignMemberForm`** (new):
  - `model = CampaignMember`
  - `fields = ["campaign", "party", "lead", "member_name", "member_email", "status", "notes"]`
  - Excluded: `tenant`, `responded_at` (system-stamped in `save()`)
  - `__init__`: scope `campaign` queryset → tenant-scoped; `party` → tenant-scoped `core.Party`;
    `lead` → tenant-scoped `crm.Lead`

- [ ] **`EmailTemplateForm`** (new):
  - `model = EmailTemplate`
  - `fields = ["name", "category", "subject", "preheader", "body", "from_name", "from_email", "is_active", "owner"]`
  - Excluded: `tenant`, `number`

- [ ] **`EmailCampaignForm`** (new):
  - `model = EmailCampaign`
  - `fields = ["name", "campaign", "template", "variant_template", "is_ab_test", "send_type",
    "status", "scheduled_at", "owner"]`
  - **Excluded** (system-managed): `tenant`, `number`, `sent_at`, `recipients_count`, `sent_count`,
    `opened_count`, `clicked_count`, `bounced_count`, `unsubscribed_count`
  - `__init__`: scope `campaign` → tenant; `template` → `EmailTemplate.objects.filter(tenant=..., is_active=True)`;
    `variant_template` → same queryset

- [ ] **`LandingPageForm`** (new):
  - `model = LandingPage`
  - `fields = ["name", "campaign", "slug", "headline", "subheadline", "body", "capture_phone",
    "capture_company", "capture_message", "cta_label", "status", "routing_owner", "lead_source", "owner"]`
  - **Excluded** (system-managed): `tenant`, `number`, `public_token`, `submission_count`
  - `__init__`: scope `campaign` → tenant; `routing_owner` → `User.objects.filter(is_active=True).order_by("username")`

- [ ] **`PublicLeadForm`** (plain `forms.Form`, NOT a ModelForm — no model binding):
  - Fields: `name` (CharField, max_length=255, required=True), `email` (EmailField, required=True),
    `phone` (CharField, max_length=40, required=False), `company` (CharField, max_length=255, required=False),
    `message` (CharField/Textarea, required=False)
  - The view conditionally renders `phone`/`company`/`message` fields based on `landing_page.capture_*` bools
  - Input length caps enforced via `max_length` (security: prevents oversized payloads)
  - NOTE: `phone`, `company`, `message` fields are ALWAYS present in the form definition;
    the template hides them with `{% if landing_page.capture_phone %}` conditionals

- [ ] Add `Campaign`, `CampaignMember`, `EmailTemplate`, `EmailCampaign`, `LandingPage` to the
  `from .models import (...)` block in `forms.py`

---

## 3. Views (`apps/crm/views.py`)

All internal views: `@login_required`, tenant-scoped (`tenant=request.tenant`). Custom action views:
`@require_POST`. Public view: NO `@login_required`.

### 3a. Campaign CRUD (enhance existing 5 views)

- [ ] **`campaign_list`** — add `objective` filter; pass `objective_choices=Campaign.OBJECTIVE_CHOICES`,
  `status_choices=Campaign.STATUS_CHOICES`, `type_choices=Campaign.TYPE_CHOICES` to context
- [ ] **`campaign_create`** — use enhanced `CampaignForm` (no view logic changes; form additions propagate)
- [ ] **`campaign_detail`** — add `members` aggregate stats: compute via
  `.aggregate(total=Count("members"), converted=Count("members", filter=Q(members__status="converted")),
  responded=Count("members", filter=Q(members__status__in=["responded","converted"])))`
  then pass `member_stats` dict to context; also pass `email_campaigns` (prefetched) and `landing_pages`
- [ ] **`campaign_edit`** — use enhanced `CampaignForm`
- [ ] **`campaign_delete`** — no change (POST-only, existing pattern)

### 3b. CampaignMember CRUD (5 new views)

- [ ] **`campaignmember_list(request)`**:
  - QS: `CampaignMember.objects.filter(tenant=request.tenant).select_related("campaign","party","lead")`
  - Filters: `q` (search member_name, member_email), `status`, `campaign` (pk)
  - `template="crm/marketing/campaignmember/list.html"`
  - `extra_context`: `status_choices=CampaignMember.STATUS_CHOICES`, `campaigns=Campaign.objects.filter(tenant=request.tenant)`

- [ ] **`campaignmember_create(request)`**:
  - Form: `CampaignMemberForm`; tenant auto-set; redirect to `crm:campaignmember_list`
  - `template="crm/marketing/campaignmember/form.html"`

- [ ] **`campaignmember_detail(request, pk)`**:
  - `get_object_or_404(CampaignMember, pk=pk, tenant=request.tenant)`
  - `template="crm/marketing/campaignmember/detail.html"`

- [ ] **`campaignmember_edit(request, pk)`**:
  - `get_object_or_404(...)`, form pre-filled
  - `template="crm/marketing/campaignmember/form.html"`

- [ ] **`campaignmember_delete(request, pk)`**:
  - POST-only; `get_object_or_404(CampaignMember, pk=pk, tenant=request.tenant)`; redirect to list

### 3c. EmailTemplate CRUD (5 new views)

- [ ] **`emailtemplate_list(request)`**:
  - QS: `EmailTemplate.objects.filter(tenant=request.tenant).defer("body").select_related("owner")`
    (defer body on list — large HTML field)
  - Filters: `q` (number, name, subject), `category`, `is_active` (`"true"`/`"false"`)
  - `template="crm/marketing/emailtemplate/list.html"`
  - `extra_context`: `category_choices=EmailTemplate.CATEGORY_CHOICES`

- [ ] **`emailtemplate_create(request)`**: form `EmailTemplateForm`, redirect to list
- [ ] **`emailtemplate_detail(request, pk)`**: renders full body; `template="crm/marketing/emailtemplate/detail.html"`
- [ ] **`emailtemplate_edit(request, pk)`**: form pre-filled
- [ ] **`emailtemplate_delete(request, pk)`**: POST-only guard; redirect to list

### 3d. EmailCampaign CRUD + send action (6 new views)

- [ ] **`emailcampaign_list(request)`**:
  - QS: `.filter(tenant=request.tenant).select_related("campaign","template","owner")`
  - Filters: `q` (number, name), `status`, `send_type`, `campaign` (pk)
  - `template="crm/marketing/emailcampaign/list.html"`
  - `extra_context`: `status_choices`, `send_type_choices`, `campaigns`

- [ ] **`emailcampaign_create(request)`**: form `EmailCampaignForm`, redirect to detail
- [ ] **`emailcampaign_detail(request, pk)`**: renders metric counters + computed rates; `template="crm/marketing/emailcampaign/detail.html"`
- [ ] **`emailcampaign_edit(request, pk)`**: guard: only draft/paused editable; form pre-filled
- [ ] **`emailcampaign_delete(request, pk)`**: guard: only draft/cancelled deletable
- [ ] **`emailcampaign_send(request, pk)`** — `@require_POST`:
  - `get_object_or_404(EmailCampaign, pk=pk, tenant=request.tenant)`
  - Guard: only `status == "draft"` or `"scheduled"` → transition to `"sent"`
  - Set `sent_at = timezone.now()`, `status = "sent"` via `update_fields`
  - `messages.success(...)` → redirect to detail
  - SECURITY: system fields (`sent_at`, metric counts) are never set from POST data

### 3e. LandingPage CRUD (5 new views)

- [ ] **`landingpage_list(request)`**:
  - QS: `.filter(tenant=request.tenant).select_related("campaign","owner")`
  - Filters: `q` (number, name, slug), `status`, `campaign` (pk)
  - `template="crm/marketing/landingpage/list.html"`
  - `extra_context`: `status_choices=LandingPage.STATUS_CHOICES`, `campaigns`

- [ ] **`landingpage_create(request)`**: form `LandingPageForm`, `public_token` auto-set in model `save()`; redirect to detail
- [ ] **`landingpage_detail(request, pk)`**: shows `public_token` URL, submission count, submission list (latest 10); `template="crm/marketing/landingpage/detail.html"`
- [ ] **`landingpage_edit(request, pk)`**: form pre-filled; `public_token`/`submission_count` excluded from form
- [ ] **`landingpage_delete(request, pk)`**: POST-only; guard against deleting published pages (warn/block)

### 3f. FormSubmission list + detail + delete + convert (4 new views)

- [ ] **`formsubmission_list(request)`**:
  - QS: `.filter(tenant=request.tenant).select_related("landing_page","routed_to","converted_lead")`
  - Filters: `q` (name, email), `status`, `landing_page` (pk)
  - `template="crm/marketing/formsubmission/list.html"`
  - `extra_context`: `status_choices=FormSubmission.STATUS_CHOICES`, `landing_pages`
  - NO create/edit — submissions arrive via public endpoint only

- [ ] **`formsubmission_detail(request, pk)`**: show all fields + link to converted_lead if set; `template="crm/marketing/formsubmission/detail.html"`

- [ ] **`formsubmission_delete(request, pk)`**: POST-only; redirect to list

- [ ] **`formsubmission_convert(request, pk)`** — `@require_POST`:
  - `get_object_or_404(FormSubmission, pk=pk, tenant=request.tenant)`
  - Guard: `status not in ("new","routed")` → redirect with warning
  - Create `Lead(tenant, name, email, company, phone, source=landing_page.lead_source or "web")`
    via `Lead.objects.get_or_create(tenant=tenant, email=submission.email, defaults={...})`
  - Set `submission.converted_lead = lead`, `submission.status = "converted"`; save via `update_fields`
  - Set `submission.routed_to = landing_page.routing_owner` if set and not already routed
  - Bump `landing_page.submission_count` via `F()` expression? — NO; submission_count already bumped on
    public POST. The convert action just links the Lead.
  - `messages.success(...)` → redirect to `crm:lead_detail pk=lead.pk`

### 3g. Public landing page (1 new view — NO `@login_required`)

- [ ] **`landing_public(request, token)`** — unauthenticated:
  - `get_object_or_404(LandingPage, public_token=token)` — NO tenant scope on the GET (public)
  - SECURITY: if `landing_page.status != "published"` → return `Http404` (draft/archived = 404,
    not even a redirect — prevents enumeration of unpublished pages)
  - GET: render `"crm/marketing/landing_public.html"` with `landing_page` + blank `PublicLeadForm()`
  - POST:
    - Bind `form = PublicLeadForm(request.POST)` and validate
    - SECURITY: input length enforced by `max_length` on each field; `email` validated by EmailField
    - On valid: create `FormSubmission(tenant=landing_page.tenant, landing_page=landing_page,
      name=form.cleaned_data["name"], email=form.cleaned_data["email"],
      phone=form.cleaned_data.get("phone",""), company=form.cleaned_data.get("company",""),
      message=form.cleaned_data.get("message",""), ip_address=request.META.get("REMOTE_ADDR"),
      status="new")`
    - Bump `landing_page.submission_count` via
      `LandingPage.objects.filter(pk=landing_page.pk).update(submission_count=F("submission_count")+1)`
    - Redirect to same page with `?submitted=1` (PRG pattern — prevents double-submission on refresh)
    - On invalid: re-render form with errors
  - CSRF: `@csrf_protect` (default Django; template includes `{% csrf_token %}`)
  - NOTE: `landing_public.html` extends a minimal `base_public.html` (no auth sidebar);
    body rendered via `{{ landing_page.body|linebreaks }}` (NEVER `|safe`) — XSS prevention
  - NOTE: no tenant-scoping on GET — any browser can access; submissions auto-inherit
    `landing_page.tenant` (no user session needed)

---

## 4. URLs (`apps/crm/urls.py`)

- [ ] Add the following URL patterns (no existing URL to remove; append after the existing `campaign_delete`):

  **Campaign (new routes only — existing 5 CRUD remain):** no new campaign URLs; the detail page now
  shows member stats inline (computed in view, no separate URL).

  **CampaignMember (5 CRUD):**
  ```python
  path("campaign-members/",                     views.campaignmember_list,   name="campaignmember_list"),
  path("campaign-members/add/",                 views.campaignmember_create, name="campaignmember_create"),
  path("campaign-members/<int:pk>/",            views.campaignmember_detail, name="campaignmember_detail"),
  path("campaign-members/<int:pk>/edit/",       views.campaignmember_edit,   name="campaignmember_edit"),
  path("campaign-members/<int:pk>/delete/",     views.campaignmember_delete, name="campaignmember_delete"),
  ```

  **EmailTemplate (5 CRUD):**
  ```python
  path("email-templates/",                      views.emailtemplate_list,    name="emailtemplate_list"),
  path("email-templates/add/",                  views.emailtemplate_create,  name="emailtemplate_create"),
  path("email-templates/<int:pk>/",             views.emailtemplate_detail,  name="emailtemplate_detail"),
  path("email-templates/<int:pk>/edit/",        views.emailtemplate_edit,    name="emailtemplate_edit"),
  path("email-templates/<int:pk>/delete/",      views.emailtemplate_delete,  name="emailtemplate_delete"),
  ```

  **EmailCampaign (5 CRUD + 1 action):**
  ```python
  path("email-campaigns/",                      views.emailcampaign_list,    name="emailcampaign_list"),
  path("email-campaigns/add/",                  views.emailcampaign_create,  name="emailcampaign_create"),
  path("email-campaigns/<int:pk>/",             views.emailcampaign_detail,  name="emailcampaign_detail"),
  path("email-campaigns/<int:pk>/edit/",        views.emailcampaign_edit,    name="emailcampaign_edit"),
  path("email-campaigns/<int:pk>/delete/",      views.emailcampaign_delete,  name="emailcampaign_delete"),
  path("email-campaigns/<int:pk>/send/",        views.emailcampaign_send,    name="emailcampaign_send"),
  ```

  **LandingPage (5 CRUD):**
  ```python
  path("landing-pages/",                        views.landingpage_list,      name="landingpage_list"),
  path("landing-pages/add/",                    views.landingpage_create,    name="landingpage_create"),
  path("landing-pages/<int:pk>/",               views.landingpage_detail,    name="landingpage_detail"),
  path("landing-pages/<int:pk>/edit/",          views.landingpage_edit,      name="landingpage_edit"),
  path("landing-pages/<int:pk>/delete/",        views.landingpage_delete,    name="landingpage_delete"),
  ```

  **FormSubmission (list + detail + delete + convert — NO create/edit):**
  ```python
  path("form-submissions/",                     views.formsubmission_list,   name="formsubmission_list"),
  path("form-submissions/<int:pk>/",            views.formsubmission_detail, name="formsubmission_detail"),
  path("form-submissions/<int:pk>/delete/",     views.formsubmission_delete, name="formsubmission_delete"),
  path("form-submissions/<int:pk>/convert/",    views.formsubmission_convert,name="formsubmission_convert"),
  ```

  **Public landing page (unauthenticated — include BEFORE `@login_required` middleware scope):**
  ```python
  path("p/<str:token>/",                        views.landing_public,        name="landing_public"),
  ```
  NOTE: the `p/<str:token>/` path must be registered in `config/urls.py` under the `crm/` include so
  that it participates in the `crm:` namespace. The public view itself does NOT use `@login_required`.
  The URL is: `/crm/p/<token>/` — confirm this is accessible without auth in the smoke sweep.

---

## 5. Admin (`apps/crm/admin.py`)

- [ ] Register `CampaignMember`:
  - `list_display = ["id","campaign","member_name","member_email","status","responded_at","created_at"]`
  - `list_filter = ["status","campaign__status"]`
  - `search_fields = ["member_name","member_email","campaign__name"]`
  - `readonly_fields = ["tenant","responded_at","created_at","updated_at"]`

- [ ] Register `EmailTemplate`:
  - `list_display = ["number","name","category","from_email","is_active","owner","created_at"]`
  - `list_filter = ["category","is_active"]`
  - `search_fields = ["number","name","subject"]`
  - `readonly_fields = ["number","tenant","created_at","updated_at"]`

- [ ] Register `EmailCampaign`:
  - `list_display = ["number","name","send_type","status","campaign","sent_at","recipients_count","opened_count","created_at"]`
  - `list_filter = ["status","send_type","is_ab_test"]`
  - `search_fields = ["number","name","campaign__name"]`
  - `readonly_fields = ["number","tenant","sent_at","recipients_count","sent_count","opened_count",
    "clicked_count","bounced_count","unsubscribed_count","created_at","updated_at"]`

- [ ] Register `LandingPage`:
  - `list_display = ["number","name","status","campaign","submission_count","public_token","owner","created_at"]`
  - `list_filter = ["status"]`
  - `search_fields = ["number","name","slug","public_token"]`
  - `readonly_fields = ["number","tenant","public_token","submission_count","created_at","updated_at"]`

- [ ] Register `FormSubmission`:
  - `list_display = ["id","name","email","status","landing_page","routed_to","converted_lead","created_at"]`
  - `list_filter = ["status"]`
  - `search_fields = ["name","email","company"]`
  - `readonly_fields = ["tenant","ip_address","created_at"]`

- [ ] Add all 5 new models to the `from .models import (...)` block in `admin.py`.

---

## 6. Migration

- [ ] Run `python manage.py makemigrations crm` — expect ONE migration file `0006_...` adding:
  - `Campaign`: add fields `objective`, `parent_campaign`, `utm_source`, `utm_medium`, `utm_campaign`
    + index `crm_cam_tnt_obj_idx`
  - New model `CampaignMember` (with all fields, unique_together, 3 indexes)
  - New model `EmailTemplate` (with all fields, unique_together, 2 indexes)
  - New model `EmailCampaign` (with all fields, unique_together, 3 indexes)
  - New model `LandingPage` (with all fields, unique_together, 2 indexes)
  - New model `FormSubmission` (with all fields, 3 indexes)
- [ ] Run `python manage.py migrate` — applies cleanly, no data migration needed.
- [ ] Run `python manage.py check` — 0 issues.

---

## 7. Seeder (`apps/crm/management/commands/seed_crm.py`)

The CRM seeder already exists. Add a `_seed_marketing(tenant)` helper function called **unconditionally**
from `handle()` like the existing `_backfill_*` functions — guarded internally by
`EmailTemplate.objects.filter(tenant=tenant).exists()`.

- [ ] Add `Campaign`, `CampaignMember`, `EmailTemplate`, `EmailCampaign`, `LandingPage`, `FormSubmission`
  to the `from apps.crm.models import (...)` block in `seed_crm.py`.

- [ ] Define `_seed_marketing(tenant)` function (module-level or as a helper):

  ```python
  def _seed_marketing(tenant):
      if EmailTemplate.objects.filter(tenant=tenant).exists():
          return  # idempotent guard — already seeded

      # Reuse first existing Campaign (seeded in base CRM seed)
      campaign = Campaign.objects.filter(tenant=tenant).first()
      if not campaign:
          return  # base seed hasn't run; skip gracefully

      # Reuse existing Party + Lead rows for CampaignMember demo data
      from apps.core.models import Party
      parties = list(Party.objects.filter(tenant=tenant)[:3])
      leads = list(Lead.objects.filter(tenant=tenant)[:3])

      from django.contrib.auth import get_user_model
      User = get_user_model()
      owner = User.objects.filter(is_active=True).order_by("id").first()

      # 1. EmailTemplates (get_or_create — unique_together tenant+number not applicable; use name)
      # Use .save() pattern (TenantNumbered assigns number)
      tmpl1 = EmailTemplate(tenant=tenant, name="Welcome Newsletter",
          category="newsletter", subject="Welcome to {{company_name}}!",
          preheader="Thanks for joining us.", from_name="NavERP Team",
          from_email="hello@example.com", is_active=True, owner=owner)
      tmpl1.save()

      tmpl2 = EmailTemplate(tenant=tenant, name="Product Launch Announcement",
          category="promotional", subject="Introducing our latest feature",
          preheader="Big news from the team.", from_name="NavERP Team",
          from_email="hello@example.com", is_active=True, owner=owner)
      tmpl2.save()

      # 2. EmailCampaign (BLAST-)
      blast = EmailCampaign(tenant=tenant, name="Q3 Newsletter Blast",
          campaign=campaign, template=tmpl1, send_type="one_time",
          status="sent", owner=owner)
      blast.save()
      # Simulate sent metrics (direct field update — seeder-only pattern)
      EmailCampaign.objects.filter(pk=blast.pk).update(
          recipients_count=500, sent_count=498, opened_count=210,
          clicked_count=85, bounced_count=2, unsubscribed_count=5)

      blast2 = EmailCampaign(tenant=tenant, name="Product Launch Drip",
          campaign=campaign, template=tmpl2, send_type="drip",
          status="draft", owner=owner)
      blast2.save()

      # 3. CampaignMembers
      for i, party in enumerate(parties):
          statuses = ["opened", "clicked", "unsubscribed"]
          cm = CampaignMember(tenant=tenant, campaign=campaign, party=party,
              member_name=party.name, member_email=f"contact{i+1}@example.com",
              status=statuses[i % len(statuses)])
          cm.save()
      for i, lead in enumerate(leads):
          cm = CampaignMember(tenant=tenant, campaign=campaign, lead=lead,
              member_name=lead.name, member_email=lead.email or f"lead{i+1}@example.com",
              status="targeted")
          cm.save()

      # 4. LandingPage (LP-)
      lp = LandingPage(tenant=tenant, name="Q3 Webinar Registration",
          campaign=campaign, slug="q3-webinar", headline="Join Our Q3 Product Webinar",
          subheadline="Live demo + Q&A — register now.",
          body="Reserve your spot for our quarterly product webinar.",
          capture_phone=True, capture_company=True, capture_message=False,
          cta_label="Register Now", status="published",
          routing_owner=owner, lead_source="event", owner=owner)
      lp.save()

      lp2 = LandingPage(tenant=tenant, name="Contact Us Draft",
          campaign=campaign, slug="contact-us", headline="Get in Touch",
          subheadline="", body="Fill in the form and we will get back to you.",
          capture_phone=True, capture_company=True, capture_message=True,
          cta_label="Send Message", status="draft", owner=owner)
      lp2.save()

      # 5. FormSubmissions (on the published LandingPage)
      sub_data = [
          {"name": "Alice Prospect", "email": "alice@prospect.com", "phone": "555-0101", "company": "Acme", "status": "converted"},
          {"name": "Bob Viewer", "email": "bob@viewer.com", "status": "new"},
          {"name": "Carol Spam", "email": "carol@spam.com", "status": "spam"},
      ]
      for d in sub_data:
          fs = FormSubmission(tenant=tenant, landing_page=lp,
              name=d["name"], email=d["email"],
              phone=d.get("phone",""), company=d.get("company",""),
              status=d["status"])
          fs.save()
  ```

- [ ] Call `_seed_marketing(tenant)` from the seeder's `handle()` method, after the existing
  Campaign seed block. (If the seeder has a per-tenant loop, add inside it.)

- [ ] Verify idempotency: second run hits the `if EmailTemplate.objects.filter(tenant=tenant).exists(): return` guard.

---

## 8. Wire-up

- [ ] **`apps/core/navigation.py` — rewrite `LIVE_LINKS["1.3"]`** (currently only has
  `"Campaign Management": "crm:campaign_list"`):

  ```python
  "1.3": {
      # NavERP.md bullet text (verbatim) → route name
      "Campaign Management":    "crm:campaign_list",       # bullet
      "Email Marketing":        "crm:emailcampaign_list",  # bullet
      "Landing Pages & Forms":  "crm:landingpage_list",    # bullet
      # Extra built pages (not NavERP.md bullets; appended as live leaves)
      "Campaign Members":       "crm:campaignmember_list", # extra
      "Email Templates":        "crm:emailtemplate_list",  # extra
      "Form Submissions":       "crm:formsubmission_list", # extra
  },
  ```

  IMPORTANT: The three bullet texts `"Campaign Management"`, `"Email Marketing"`,
  `"Landing Pages & Forms"` must match EXACTLY what `NavERP.md` section 1.3 prints — the
  navigation parser uses them to light up the bullet. Verify against `NavERP.md §1.3` before committing.

---

## 9. Templates (`templates/crm/marketing/`)

All templates: `{% extends "base.html" %}`, Tailwind design system, Lucide icons. Every list has a
filter bar, Actions column (view/edit/delete or view/delete where edit is excluded), pagination, and
empty state. Every detail has an Actions sidebar. System-managed fields display as read-only info, never
in form `<input>`s.

### 9a. Campaign templates (RECREATE — new fields)

- [ ] **`templates/crm/marketing/campaign/list.html`**:
  - Filter bar: `q`, `status`, `type`, `objective` (new) selects; compare strings
  - Table: Number, Name, Type, Objective (new badge), Status badge, Owner, Budget Planned, ROI, Actions
  - Empty state; pagination

- [ ] **`templates/crm/marketing/campaign/detail.html`**:
  - Breadcrumb, sidebar (Edit / Delete / Back to Campaigns)
  - Cards:
    1. Campaign Details (Number, Name, Type, Status, Objective, Dates, Owner, UTM fields)
    2. Budget & ROI (budget_planned, budget_actual, expected/actual revenue, `campaign.roi`)
    3. Member Stats (new — show `member_stats.total`, `member_stats.responded`, `member_stats.converted`)
    4. Child Campaigns (loop `campaign.child_campaigns.all` if any)
    5. Email Campaigns table (loop `email_campaigns`)
    6. Landing Pages table (loop `landing_pages`)

- [ ] **`templates/crm/marketing/campaign/form.html`**:
  - Fields: `name`, `type`, `status`, `start_date`, `end_date`, `objective` (new), `parent_campaign` (new),
    `budget_planned`, `budget_actual`, `expected_revenue`, `actual_revenue`, `target_size`,
    `utm_source`, `utm_medium`, `utm_campaign` (new UTM section), `owner`, `description`

### 9b. CampaignMember templates

- [ ] **`templates/crm/marketing/campaignmember/list.html`**:
  - Filter bar: `q` (name/email), `status`, `campaign` (FK pk; use `|stringformat:"d"` for comparison)
  - Table: Campaign, Member Name, Email, Status badge, Responded At (if set), Notes, Created At, Actions
  - Empty state; pagination

- [ ] **`templates/crm/marketing/campaignmember/detail.html`**:
  - Cards: Membership Info (campaign, party/lead links, email, status, responded_at), Notes, Timestamps
  - Sidebar: Edit / Delete / Back to Members

- [ ] **`templates/crm/marketing/campaignmember/form.html`**:
  - Fields: `campaign`, `party`, `lead`, `member_name`, `member_email`, `status`, `notes`
  - Note: `responded_at` is NEVER shown in this form (system-stamped)

### 9c. EmailTemplate templates

- [ ] **`templates/crm/marketing/emailtemplate/list.html`**:
  - Filter bar: `q`, `category`, `is_active` (`"true"`/`"false"`)
  - Table: Number, Name, Category badge, Subject, From Email, Active (badge), Owner, Actions

- [ ] **`templates/crm/marketing/emailtemplate/detail.html`**:
  - Cards: Template Details, Preview (preheader, from_name/email, subject), HTML Body (rendered in
    a `<pre>` or `<div class="font-mono text-xs">` block — NOT `|safe`; display as escaped code)
  - Sidebar: Edit / Delete / Back to Templates

- [ ] **`templates/crm/marketing/emailtemplate/form.html`**:
  - Fields: `name`, `category`, `subject`, `preheader`, `body` (textarea large), `from_name`,
    `from_email`, `is_active`, `owner`

### 9d. EmailCampaign templates

- [ ] **`templates/crm/marketing/emailcampaign/list.html`**:
  - Filter bar: `q`, `status`, `send_type`, `campaign` (FK pk)
  - Table: Number, Name, Send Type, Status badge, Campaign, Scheduled At, Open Rate (if sent), Actions

- [ ] **`templates/crm/marketing/emailcampaign/detail.html`**:
  - Cards:
    1. Campaign Details (name, campaign FK link, template links, send_type, status, scheduled_at, sent_at, owner)
    2. A/B Test info (if `is_ab_test`: show `variant_template` link)
    3. Delivery Metrics (recipients, sent, delivered, opened, clicked, bounced, unsubscribed — computed props)
    4. Rates (open_rate, click_rate, bounce_rate — show as badges; null = "N/A")
  - Sidebar: Edit (if draft/paused) / Send Action (POST form → `crm:emailcampaign_send` if draft/scheduled) /
    Delete (if draft/cancelled) / Back to Email Campaigns

- [ ] **`templates/crm/marketing/emailcampaign/form.html`**:
  - Fields: `name`, `campaign`, `template`, `variant_template` (show if `is_ab_test` checked),
    `is_ab_test`, `send_type`, `status`, `scheduled_at`, `owner`
  - NOTE: metric count fields (`recipients_count`, `sent_count`, etc.) and `sent_at` are NEVER in this form

### 9e. LandingPage templates

- [ ] **`templates/crm/marketing/landingpage/list.html`**:
  - Filter bar: `q`, `status`, `campaign` (FK pk)
  - Table: Number, Name, Status badge, Campaign, Slug, Submission Count, Public URL (link to `crm:landing_public token=lp.public_token`), Actions

- [ ] **`templates/crm/marketing/landingpage/detail.html`**:
  - Cards:
    1. Page Info (name, campaign, slug, status, headline, subheadline, cta_label, capture_* bools)
    2. Public Access (show full public URL with copyable link: `/crm/p/<public_token>/`)
    3. Lead Routing (routing_owner, lead_source)
    4. Stats (submission_count)
    5. Recent Submissions table (latest 10 from `landing_page.submissions.all()[:10]`)
  - Sidebar: Edit / Delete / Back to Landing Pages / "View Public Page" link → `crm:landing_public`

- [ ] **`templates/crm/marketing/landingpage/form.html`**:
  - Fields: `name`, `campaign`, `slug`, `headline`, `subheadline`, `body`, `capture_phone`,
    `capture_company`, `capture_message`, `cta_label`, `status`, `routing_owner`, `lead_source`, `owner`
  - NOTE: `public_token` and `submission_count` NEVER shown (system fields)

### 9f. FormSubmission templates

- [ ] **`templates/crm/marketing/formsubmission/list.html`**:
  - Filter bar: `q` (name/email), `status`, `landing_page` (FK pk)
  - Table: ID, Name, Email, Company, Landing Page, Status badge, Routed To, Converted Lead (link), Created At, Actions
  - Actions column: View (eye), Delete (trash — POST+confirm), Convert button (if status in new/routed → `crm:formsubmission_convert`)
  - NO Edit button (read-only data)

- [ ] **`templates/crm/marketing/formsubmission/detail.html`**:
  - Cards:
    1. Submission Data (name, email, phone, company, message)
    2. Meta (landing_page link, ip_address, created_at, status)
    3. Routing & Conversion (routed_to, converted_lead link if set)
  - Sidebar: Convert to Lead (POST → `crm:formsubmission_convert`, only if status in new/routed) /
    Delete (POST + confirm) / Back to Submissions
  - NO Edit button

### 9g. Public landing page (standalone)

- [ ] **`templates/crm/marketing/landing_public.html`**:
  - Extends `base_public.html` (no auth sidebar; minimal NavERP branding; or extends `base.html`
    with sidebar hidden via template block — confirm which public base exists in the project)
  - Shows: `{{ landing_page.headline }}`, `{{ landing_page.subheadline }}`,
    `{{ landing_page.body|linebreaks }}` (NEVER `|safe`)
  - Form section: `{% csrf_token %}` + `name` (required), `email` (required),
    `{% if landing_page.capture_phone %}phone{% endif %}`,
    `{% if landing_page.capture_company %}company{% endif %}`,
    `{% if landing_page.capture_message %}message{% endif %}`,
    submit button with `{{ landing_page.cta_label }}`
  - If `request.GET.submitted`: show success message instead of form (PRG pattern)
  - On form error: re-render form with error messages
  - SECURITY: no `|safe` anywhere; all user-supplied content escaped; CSRF token present

---

## 10. Verify

- [ ] `python manage.py makemigrations crm` — produces `0006_...`; no unexpected alterations to other models
- [ ] `python manage.py migrate` — applies cleanly
- [ ] `python manage.py check` — 0 issues
- [ ] `python manage.py seed_crm` (first run) — seeds 2 email templates, 2 email campaigns, 3–6
  campaign members, 2 landing pages, 3 form submissions; prints tenant-admin login hint
- [ ] `python manage.py seed_crm` (second run) — `[skip]` message fires; no new rows; no `IntegrityError`
- [ ] **Smoke sweep** — log in as a tenant admin (e.g., `admin_acme`) and verify:
  - [ ] `crm:campaign_list` → 200 (existing + new `objective` filter visible)
  - [ ] `crm:campaign_detail pk=<seeded>` → 200 (member_stats + email_campaigns + landing_pages cards)
  - [ ] `crm:campaign_create` → 200 (new fields: objective, parent_campaign, utm_*)
  - [ ] `crm:campaign_edit pk=<seeded>` → 200
  - [ ] `crm:campaignmember_list` → 200
  - [ ] `crm:campaignmember_create` → 200
  - [ ] `crm:campaignmember_detail pk=<seeded>` → 200
  - [ ] `crm:campaignmember_edit pk=<seeded>` → 200
  - [ ] `crm:campaignmember_delete pk=<seeded>` → POST → 302
  - [ ] `crm:emailtemplate_list` → 200 (body deferred on QS — no large HTML blobs in list)
  - [ ] `crm:emailtemplate_create` → 200
  - [ ] `crm:emailtemplate_detail pk=<seeded>` → 200 (body displayed as escaped code, not rendered HTML)
  - [ ] `crm:emailtemplate_edit pk=<seeded>` → 200
  - [ ] `crm:emailtemplate_delete pk=<seeded>` → POST → 302
  - [ ] `crm:emailcampaign_list` → 200 (open_rate badge on sent rows)
  - [ ] `crm:emailcampaign_create` → 200
  - [ ] `crm:emailcampaign_detail pk=<seeded_sent>` → 200 (metrics, rates shown; `sent_at` read-only)
  - [ ] `crm:emailcampaign_edit pk=<draft>` → 200 (metric counts NOT in form)
  - [ ] `crm:emailcampaign_send pk=<draft>` → POST → 302 (status → sent, sent_at stamped)
  - [ ] `crm:emailcampaign_delete pk=<draft>` → POST → 302
  - [ ] `crm:landingpage_list` → 200 (public URL links visible)
  - [ ] `crm:landingpage_create` → 200 (`public_token`/`submission_count` NOT in form)
  - [ ] `crm:landingpage_detail pk=<published>` → 200 (public token URL shown; recent submissions)
  - [ ] `crm:landingpage_edit pk=<seeded>` → 200
  - [ ] `crm:landingpage_delete pk=<draft>` → POST → 302
  - [ ] `crm:formsubmission_list` → 200 (no Add button visible)
  - [ ] `crm:formsubmission_detail pk=<seeded>` → 200 (no Edit button; Convert button if status=new)
  - [ ] `crm:formsubmission_convert pk=<new_submission>` → POST → 302 → lead_detail (Lead created)
  - [ ] `crm:formsubmission_delete pk=<spam>` → POST → 302
- [ ] **Public endpoint:**
  - [ ] `/crm/p/<published_token>/` (GET, no auth) → 200 (headline, body, form rendered)
  - [ ] `/crm/p/<published_token>/` (POST, valid form, no auth) → 302 → `?submitted=1` (FormSubmission created; submission_count bumped)
  - [ ] `/crm/p/<draft_token>/` (GET, no auth) → 404 (draft page is not publicly accessible)
  - [ ] `/crm/p/<archived_token>/` (GET, no auth) → 404
  - [ ] `/crm/p/invalid-token-xyz/` → 404
- [ ] **Cross-tenant IDOR → 404**: GET `crm:emailcampaign_detail pk=<other_tenant_blast>` logged in
  as `admin_acme` → 404
- [ ] **Cross-tenant IDOR → 404**: GET `crm:landingpage_detail pk=<other_tenant_lp>` → 404
- [ ] **Cross-tenant IDOR → 404**: GET `crm:formsubmission_detail pk=<other_tenant_sub>` → 404
- [ ] **No template comment leaks**: grep all new `.html` files for `{#` or `{% comment`
- [ ] **XSS prevention**: verify `landing_public.html` uses `|linebreaks` not `|safe` on `body`
- [ ] **System field exclusion**: POST to `crm:emailcampaign_edit` with `sent_at=2020-01-01` in body →
  field ignored; `sent_at` unchanged in DB
- [ ] **Sidebar**: log in as tenant admin; open CRM → Marketing Automation (1.3) → confirm
  "Campaign Management", "Email Marketing", "Landing Pages & Forms" all show as **Live**;
  "Campaign Members", "Email Templates", "Form Submissions" show as extra live leaves

---

## 11. Close-out

- [ ] Run **code-reviewer** agent — apply findings, one commit per file.
- [ ] Run **explorer** agent — apply findings, one commit per file.
- [ ] Run **frontend-reviewer** agent — focus: metric rate badges on EmailCampaign detail;
  conditional form field visibility (`variant_template` shown only when `is_ab_test=True`);
  public landing page mobile responsiveness; campaign detail cards layout; filter bar FK comparisons
  using `|stringformat:"d"`.
- [ ] Run **performance-reviewer** agent — focus: `emailtemplate_list` defers `body` (large TextField);
  `campaignmember_list` select_related coverage; `campaign_detail` aggregate query count;
  `formsubmission_list` select_related `converted_lead`; public endpoint F()-bump vs. extra DB hit.
- [ ] Run **qa-smoke-tester** agent — apply findings, one commit per file.
- [ ] Run **security-reviewer** agent — focus: `landing_public` CSRF protection; `|linebreaks` not
  `|safe` on body; draft/archived → 404 guard; `submission_count` bumped via `F()` not from POST;
  `sent_at`/metric counts excluded from form; cross-tenant IDOR on all 5 new models; `public_token`
  excluded from `LandingPageForm`; `formsubmission_convert` only sets lead from cleaned data not POST.
- [ ] Run **test-writer** agent — apply output, one commit per file. Tests should cover:
  - `Campaign` model: new fields saved; `parent_campaign` self-FK; `roi` property unchanged.
  - `CampaignMember` model: `responded_at` stamped on status→responded/converted; unique_together
    on (tenant, campaign, party); `__str__`.
  - `EmailTemplate` model: EMT- auto-number; `unique_together`; `is_active` default True.
  - `EmailCampaign` model: BLAST- auto-number; `open_rate`/`click_rate`/`bounce_rate` properties
    (None when denominator=0; correct Decimal); `delivered_count`; system fields excluded from form POST.
  - `LandingPage` model: LP- auto-number; `public_token` auto-generated in `save()`; unique; `public_token`
    excluded from `LandingPageForm`.
  - `FormSubmission` model: no auto-number; `__str__`; read-only (no create/edit view URLs).
  - CRUD views: 200/302 for all internal URLs; tenant-scoped.
  - `emailcampaign_send`: POST transitions draft→sent; stamps `sent_at`; non-draft → redirect with warning.
  - `formsubmission_convert`: creates Lead; sets `converted_lead`; status→converted; idempotent
    (second convert → warning, no duplicate Lead if same email).
  - `landing_public` (GET): published → 200; draft → 404; archived → 404; invalid token → 404.
  - `landing_public` (POST, valid): creates `FormSubmission`; bumps `submission_count` via F();
    redirects to `?submitted=1`.
  - `landing_public` (POST, invalid email): re-renders form with errors; no FormSubmission created.
  - Cross-tenant IDOR → 404 for CampaignMember, EmailTemplate, EmailCampaign, LandingPage, FormSubmission.
  - Seeder idempotency (second `_seed_marketing` call skips).
- [ ] Update **`.claude/skills/crm/SKILL.md`** — add all 6 new/enhanced models to the Models section;
  add new url names (5+5+6+5+4+1 = 26 new url names) to the URLs section; add marketing template paths
  to the Templates section; add `_seed_marketing` to the Seeder section; update `LIVE_LINKS["1.3"]` in
  sidebar wiring.
- [ ] Mark 1.3 Marketing Automation as delivered in **`README.md`** roadmap.

---

## Later passes / deferred

- **Real ESP integration (actual email delivery)** — sending via SendGrid, Mailgun, AWS SES, Postmark;
  requires Celery + API keys. `EmailCampaign.status`, `sent_at`, and metric counters are model-ready.
- **Drag-and-drop HTML visual builder** — GrapeJS/Unlayer embed for `EmailTemplate.body`. The raw
  HTML textarea is the MVP; visual editor is an integration/later frontend feature.
- **DripStep / ABVariant normalized tables** — if A/B testing grows beyond a single `variant_template`
  FK, add normalized child tables. The `send_type` and `is_ab_test` flags make the upgrade non-breaking.
- **Send-time optimization / predictive send** — algorithm requires historical open-time data per contact.
  The `scheduled_at` field is model-ready; ML routing deferred.
- **Smart Traffic / AI page routing** — `LandingPage.status` + `public_token` architecture is ready;
  ML-based split routing deferred.
- **Progressive profiling on forms** — Marketo feature; requires cookie/session tracking. Deferred.
- **Behavioral web-tracking (site events)** — JS snippet + event-ingestion endpoint; deferred.
- **SMS / WhatsApp channel** — out of scope for this Django-only pass.
- **Multi-touch revenue attribution reports** — `CampaignMember.status` data is ready; report
  deferred to Module 10 BI.
- **Separate `FormField` model** — `LandingPage.capture_*` bools cover the MVP; dynamic form-field
  builder (`FormField` child model + field type choices) deferred to a later pass.
- **Transactional email** — belongs to Module 2 Accounting / Module 9 eCommerce, not CRM marketing.
- **Geography-based lead routing** — `routing_owner` field is model-ready; IP-to-geo lookup + territory
  table algorithm deferred.
- **CAPTCHA enforcement** — a stub bool on `LandingPage` (not modeled this pass; can add as a field in
  a follow-up); wiring to Google reCAPTCHA v3 or hCaptcha requires an API key and front-end JS.
- **`ContactProfile.is_email_opted_out`** — global unsubscribe suppression flag deferred to a
  hardening pass; the `CampaignMember.status = "unsubscribed"` field is the per-campaign record.
- **`FormSubmission` UTM fields** — utm_source/medium/campaign/term/content on `FormSubmission`
  (research 1.3.C UTM attribution) deferred for simplicity; the `LandingPage.utm_*` fields on the
  parent Campaign cover basic attribution.
- **Engagement scoring** — bumping `Lead.score` on CampaignMember email opens/clicks; service function
  deferred until ESP integration is live (no real open events without actual sends).
- **Round-robin lead routing** — `routing_owner` is manual assignment this pass; round-robin algorithm
  (`User.objects.filter(is_active=True).order_by("crm_routed_submissions")`) deferred.

---

## Review notes — CRM §1.3 Marketing Automation (recreated in detail) ✅

**Delivered (migrations 0006 + 0007):** enhanced `Campaign` (objective/parent_campaign/utm_*) + 5 new entities —
`CampaignMember` (target-list segmentation, per-recipient funnel status, `responded_at` stamping), `EmailTemplate`
(`EMT-`), `EmailCampaign` (`BLAST-`, A/B variant + drip + open/click/bounce metrics & rates), `LandingPage`
(`LP-`, 256-bit `public_token`, capture toggles, owner routing), `FormSubmission` (read-mostly web-to-lead). Full
CRUD + custom actions (`campaignmember_add/_remove`, admin-gated `emailcampaign_send`, admin-gated
`landingpage_publish`, `formsubmission_convert`) + **public** `landing_public(token)` (no login, published-only,
CSRF, escaped body, PRG). `LIVE_LINKS["1.3"]` lights up all 3 NavERP bullets + 3 extras. 14 templates under
`templates/crm/marketing/`. `_seed_marketing` seeder (unconditional, EmailTemplate-guarded). One file per commit
to `main` (not pushed).

**Verification:** `manage.py check` clean; migrations apply; `seed_crm` idempotent (×2); `temp/smoke_marketing.py`
all green; **745 CRM pytest tests pass** (193 new in `test_marketing.py` + 3 pre-existing Campaign tests fixed for
the now-required `objective` field).

**Review agents (CLAUDE.md sequence), findings applied:**
- **code-reviewer** — race-safe `emailcampaign_send` (conditional UPDATE), validate inline member email, PRG on the
  public form, "View all members" link. (False positive: `is_active` string filter — verified Django coerces it.)
- **explorer** — confirmed full URL/context/field consistency; no code changes.
- **frontend-reviewer** — theme CSS vars on the public page (`--text-muted`/`--ok`), `<div>|linebreaksbr` for the
  landing body (no nested `<p>`), removed a redundant inline style, documented the read-only column.
- **performance-reviewer** — `.defer("body")`/`.defer("message")` on landing list/detail, `(tenant, created_at)`
  index on CampaignMember (0007), `bulk_create` in the seeder.
- **qa-smoke-tester** — 64/64 checks pass, no changes.
- **security-reviewer** (3 Medium applied) — excluded `status` from EmailCampaignForm + LandingPageForm
  (mass-assignment), gated `emailcampaign_send` + new `landingpage_publish` behind `@tenant_admin_required`,
  256-bit token, audit-log the convert, WARNING comments (IP proxy caveat, public rate-limiting).
- **test-writer** — 193 tests.

**Note:** the final scope folded the research's separate DripStep/ABVariant tables into
`EmailCampaign.send_type`/`variant_template`, and FormSubmission stores typed columns (not a `data` JSONField) —
matching the approved 6-entity plan. Deferred: real ESP delivery, visual builder, CAPTCHA/rate-limit enforcement,
multi-touch attribution (→ BI Module 10).

---
# Module 1.2 — CRM Sales Force Automation (crm-sfa) — plan from research-crm-sfa.md  (2026-06-26)

**Extending `apps/crm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py` are already
in place. The only new wire-up is rewriting `LIVE_LINKS["1.2"]` in `apps/core/navigation.py` + new URL patterns
inside the existing `apps/crm/urls.py`. Migration base: **0007** (next migration will be **0008**).

Sub-module template folder: `templates/crm/sales/` with one entity-folder per model (CLAUDE.md rule 2).
Standalone pages: `templates/crm/sales/pipeline.html` (Kanban), `templates/crm/sales/forecast.html` (dashboard),
`templates/crm/sales/quote/print.html` (print view — lives inside the quote entity folder as a secondary action).

---

## 0. Template folder structure

- [ ] Create `templates/crm/sales/` sub-module root with the following entity folders:
  - `sales/territory/{list,detail,form}.html`          — Territory CRUD
  - `sales/product/{list,detail,form}.html`            — Product CRUD
  - `sales/pricebook/{list,detail,form}.html`          — PriceBook CRUD
  - `sales/opportunity/{list,detail,form}.html`        — Opportunity CRUD (replaces/extends existing
    `templates/crm/` flat opportunity pages if any; existing views will be re-pointed)
  - `sales/quote/{list,detail,form,print}.html`        — Quote CRUD + print action
  - `sales/salesquota/{list,detail,form}.html`         — SalesQuota CRUD
  - `sales/pipeline.html`                              — standalone Kanban board (sub-module root)
  - `sales/forecast.html`                              — standalone forecast dashboard (sub-module root)
  - NOTE: `OpportunitySplit` and `QuoteLine` are **inline only** — rendered inside their parent
    detail pages. No standalone list/form templates.

---

## 1. Models (add to / enhance in `apps/crm/models.py`)

### 1a. `Territory` [TER-] — `TenantNumbered`, `NUMBER_PREFIX = "TER"`

Drivers: territory-assignment on opportunities (Salesforce, Zoho, Dynamics 365, SugarCRM); sub-territory
hierarchy for forecast rollups (Salesforce, Zoho); territory quota in SalesQuota.

- [ ] Add `Territory(TenantNumbered)` with `NUMBER_PREFIX = "TER"`:
  - `number`       — `CharField(max_length=20, editable=False)` — inherited
  - `name`         — `CharField(max_length=120)` — e.g. "North America – Enterprise"
  - `region`       — `CharField(max_length=120, blank=True)` — geographic region label (Salesforce territory
                      regions; Zoho territory hierarchy filter)
  - `segment`      — `CharField(max_length=120, blank=True)` — market segment e.g. "Mid-Market"
                      (Dynamics 365 sales territories by segment; Zoho territory-based forecasting)
  - `parent`       — `ForeignKey("self", on_delete=SET_NULL, null=True, blank=True,
                      related_name="child_territories")` — sub-territory parent for hierarchy
                      rollups (Salesforce, Zoho, SugarCRM)
  - `manager`      — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                      related_name="managed_territories")` — territory manager / quota owner
                      (Salesforce territory manager role; Zoho territory owner)
  - `is_active`    — `BooleanField(default=True)`
  - `description`  — `TextField(blank=True)`
  - Meta indexes: `(tenant, is_active)` named `crm_ter_tnt_active_idx`; `(tenant, created_at)` named
    `crm_ter_tnt_created_idx`; unique_together `(tenant, number)` (inherited from TenantNumbered)

### 1b. `Product` [PRD-] — `TenantNumbered`, `NUMBER_PREFIX = "PRD"`

Drivers: all 10 leaders have a product catalog; CRM-owned sales catalog distinct from `crm.ProductStock`
(inventory-tracking); `product_type` drives quoting logic (Dynamics 365 product types, SugarCRM product
catalog); `margin_pct` property for forecast-by-product-line reporting (Clari, Salesforce CPQ).

- [ ] Add `Product(TenantNumbered)` with `NUMBER_PREFIX = "PRD"`:
  - `number`        — `CharField(max_length=20, editable=False)` — inherited
  - `name`          — `CharField(max_length=255)`
  - `sku`           — `CharField(max_length=64, blank=True)` — stock-keeping unit
                       (Dynamics 365, Salesforce, SugarCRM product SKU)
  - `product_type`  — `CharField(max_length=20, choices=PRODUCT_TYPE_CHOICES, default="good")` —
                       `good` / `service` / `subscription`
                       (Dynamics 365 product types: product/service/bundle; SugarCRM types)
  - `unit_price`    — `DecimalField(max_digits=12, decimal_places=2, default=0)` — default list price
                       (Salesforce standard price; Dynamics 365 list price)
  - `cost`          — `DecimalField(max_digits=12, decimal_places=2, default=0)` — internal cost for
                       margin calc (SugarCRM, DealHub margin guardrails)
  - `tax_pct`       — `DecimalField(max_digits=5, decimal_places=2, default=0)` — default tax rate
                       applied when product is added to a QuoteLine (Zoho tax on product)
  - `is_active`     — `BooleanField(default=True)`
  - `description`   — `TextField(blank=True)`
  - `PRODUCT_TYPE_CHOICES` module-level constant: `[("good","Good"),("service","Service"),
    ("subscription","Subscription")]`
  - `@property margin_pct` — `Decimal`-safe: `(unit_price - cost) / unit_price * 100` when
    `unit_price > 0` else `Decimal(0)` (DealHub/PandaDoc margin display)
  - Meta indexes: `(tenant, product_type)` named `crm_prd_tnt_type_idx`; `(tenant, is_active)` named
    `crm_prd_tnt_active_idx`; unique_together `(tenant, number)`

### 1c. `PriceBook` [PB-] — `TenantNumbered`, `NUMBER_PREFIX = "PB"`

Drivers: regional/tier pricing (Salesforce Standard + Custom Price Books; Dynamics 365 PriceLevel;
SugarCRM, Zoho, DealHub price books); `price_adjustment_pct` folds PriceBookEntry into the header
(±% off product base — PriceBookEntry is a future enhancement); `is_default` for auto-selection
(Salesforce default price book pattern).

- [ ] Add `PriceBook(TenantNumbered)` with `NUMBER_PREFIX = "PB"`:
  - `number`                — `CharField(max_length=20, editable=False)` — inherited
  - `name`                  — `CharField(max_length=255)`
  - `currency_code`         — `CharField(max_length=3, default="USD")` — ISO-4217 code; CharField
                               because core Currency table is not yet built (Zoho, SugarCRM, Dynamics
                               multi-currency quotes)
  - `region`                — `CharField(max_length=120, blank=True)` — e.g. "APAC", "US West"
                               (Salesforce territory→price-book; Dynamics 365 regional PriceLevel)
  - `tier`                  — `CharField(max_length=80, blank=True)` — e.g. "Enterprise", "SMB"
                               (DealHub tiered pricing; SugarCRM pricing tiers)
  - `price_adjustment_pct`  — `DecimalField(max_digits=6, decimal_places=2, default=0)` — ±% off
                               product `unit_price`; positive = markup, negative = discount
                               (Salesforce custom price book % adjustment; Zoho pricebook discount)
  - `is_default`            — `BooleanField(default=False)` — exactly one default per tenant
                               (Salesforce Standard Price Book concept)
  - `is_active`             — `BooleanField(default=True)`
  - `description`           — `TextField(blank=True)`
  - Meta indexes: `(tenant, is_active)` named `crm_pb_tnt_active_idx`; `(tenant, is_default)` named
    `crm_pb_tnt_default_idx`; unique_together `(tenant, number)`

### 1d. Enhance existing `Opportunity` (apps/crm/models.py line 453)

Drivers: competitor capture (Salesforce, Dynamics 365, Zoho, SugarCRM deal detail fields); forecast
category independent of stage (Salesforce Forecast Categories; Zoho 5-bucket forecasting; Clari);
loss_reason on Closed Lost (Salesforce, Zoho, SugarCRM); `lost_at` system-stamp like `Case.resolved_at`;
territory assignment for forecast rollups (Salesforce, Zoho); `stage_changed_at` for stalled-deal
detection (Salesforce Pipeline Inspection, Clari).

- [ ] ADD fields to `Opportunity` model (no new migration file yet — combined into 0008):
  - `competitor`          — `CharField(max_length=100, blank=True)` — primary competing product/vendor
  - `forecast_category`   — `CharField(max_length=20, choices=FORECAST_CATEGORY_CHOICES,
                             default="pipeline")` — `omitted`/`pipeline`/`best_case`/`commit`/`closed`
                             (Salesforce Forecast Categories; Zoho pipeline/best-case/committed/closed/
                             omitted; HubSpot stage→category mapping; Clari Commit/Best Case/Pipeline)
  - `loss_reason`         — `CharField(max_length=20, choices=LOSS_REASON_CHOICES, blank=True)` —
                             `price`/`competition`/`timeline`/`no_decision`/`other`
                             (Salesforce, Zoho loss reason on Closed Lost; SugarCRM loss reason field)
  - `lost_at`             — `DateTimeField(null=True, blank=True)` — system-stamped in `save()` when
                             `stage` transitions to `closed_lost`; cleared when stage changes away
                             (mirrors `Case.resolved_at` pattern already in codebase)
  - `territory`           — `ForeignKey("crm.Territory", on_delete=SET_NULL, null=True, blank=True,
                             related_name="opportunities")` — territory for forecast rollup
  - `stage_changed_at`    — `DateTimeField(null=True, blank=True)` — system-stamped in `save()` when
                             `stage` changes; used for stage-age / stalled-deal detection
  - `FORECAST_CATEGORY_CHOICES` module-level constant (add near `STAGE_CHOICES`)
  - `LOSS_REASON_CHOICES` module-level constant
  - Update `save()` to: (a) stamp `lost_at = timezone.now()` when `stage == "closed_lost"` and
    `lost_at` is None; clear it when stage changes away from `closed_lost`; (b) stamp
    `stage_changed_at` when `stage` differs from the DB value (`__class__.objects.filter(pk=self.pk)
    .values_list("stage",flat=True).first()` before saving)
  - Add Meta index `(tenant, forecast_category)` named `crm_opp_tnt_fcat_idx`

### 1e. `OpportunitySplit` — plain tenant-scoped (no TenantNumbered)

Drivers: Salesforce revenue + overlay splits (team selling, SE/SDR credit); HubSpot Sales Hub Enterprise
deal credit splits; commission-credit distribution where revenue splits must total ≤ 100%.

- [ ] Add `OpportunitySplit(models.Model)` (NOT TenantNumbered — no auto-number):
  - `tenant`        — `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="crm_opp_splits")`
  - `opportunity`   — `ForeignKey("crm.Opportunity", on_delete=CASCADE, related_name="splits")`
  - `user`          — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE,
                       related_name="crm_splits")`
  - `split_type`    — `CharField(max_length=10, choices=[("revenue","Revenue"),("overlay","Overlay")])`
                       (Salesforce revenue split = must total 100%; overlay = SE/channel credit, may
                       exceed 100%; HubSpot deal-credit split types)
  - `percentage`    — `DecimalField(max_digits=5, decimal_places=2)` — share 0.00–100.00
  - `created_at`    — `DateTimeField(auto_now_add=True)`
  - `updated_at`    — `DateTimeField(auto_now=True)`
  - `clean()`: query sibling revenue splits, assert sum (excluding self) + self.percentage ≤ 100
    for `split_type == "revenue"`; overlay has no cap
  - Meta: ordering `["split_type", "-percentage"]`; no unique_together beyond natural FKs

### 1f. `Quote` [QUO-] — `TenantNumbered`, `NUMBER_PREFIX = "QUO"`

Drivers: formal quote document (all 10 leaders); quote lifecycle Draft→Sent→Accepted→Declined→Expired
(Salesforce, Dynamics, SugarCRM 8-stage, Zoho, Freshsales); `price_book` auto-sets line `unit_price`
(Salesforce Price Book on quote; Dynamics 365 PriceLevel); `recalc_totals()` mirrors existing
`PurchaseOrder.recalc_total()`; system fields excluded from form (status, subtotal, tax_total, total,
sent_at, accepted_at).

- [ ] Add `Quote(TenantNumbered)` with `NUMBER_PREFIX = "QUO"`:
  - `number`        — `CharField(max_length=20, editable=False)` — inherited
  - `opportunity`   — `ForeignKey("crm.Opportunity", on_delete=SET_NULL, null=True, blank=True,
                       related_name="quotes")` — linked deal
  - `account`       — `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True,
                       related_name="crm_quotes")` — billing party (denormalized for standalone quotes;
                       Salesforce quote billing account; Dynamics 365 quote customer)
  - `price_book`    — `ForeignKey("crm.PriceBook", on_delete=SET_NULL, null=True, blank=True,
                       related_name="quotes")` — drives line unit_price adjustment
  - `STATUS_CHOICES` — `[("draft","Draft"),("sent","Sent"),("accepted","Accepted"),
                        ("declined","Declined"),("expired","Expired")]` module-level constant
  - `status`        — `CharField(max_length=10, choices=STATUS_CHOICES, default="draft")` —
                       SYSTEM field; excluded from form; set only by `quote_send`/`quote_accept`/
                       `quote_decline` views
  - `valid_until`   — `DateField(null=True, blank=True)` — quote expiry (Zoho, Freshsales, SugarCRM
                       valid-through date)
  - `currency_code` — `CharField(max_length=3, default="USD")` — ISO-4217; CharField because core
                       Currency is not yet built (SugarCRM currency on quote; Dynamics 365 currency)
  - `discount_pct`  — `DecimalField(max_digits=5, decimal_places=2, default=0)` — quote-level % off
                       subtotal (SugarCRM Grand Total Discount %; DealHub quote discount)
  - `subtotal`      — `DecimalField(max_digits=14, decimal_places=2, default=0)` — SYSTEM; set by
                       `recalc_totals()`; excluded from form
  - `tax_total`     — `DecimalField(max_digits=12, decimal_places=2, default=0)` — SYSTEM; set by
                       `recalc_totals()`; excluded from form
  - `total`         — `DecimalField(max_digits=14, decimal_places=2, default=0)` — SYSTEM; grand
                       total; set by `recalc_totals()`; excluded from form
  - `sent_at`       — `DateTimeField(null=True, blank=True)` — SYSTEM; stamped by `quote_send`
  - `accepted_at`   — `DateTimeField(null=True, blank=True)` — SYSTEM; stamped by `quote_accept`
  - `terms`         — `TextField(blank=True)` — payment/delivery terms; rendered escaped in template
                       (never |safe — XSS guard)
  - `owner`         — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                       related_name="crm_quotes")`
  - `recalc_totals()` method: aggregates `lines` DB-side via `Aggregate(Sum(...))`:
    - line_sum = `lines.aggregate(s=Sum(line_total_expr))["s"] or 0`  (use DB expression)
    - tax_sum  = `lines.aggregate(t=Sum(line_tax_expr))["t"] or 0`
    - subtotal = line_sum
    - tax_total = tax_sum
    - total = subtotal * (1 - discount_pct/100) + tax_total
    - saves with `update_fields=["subtotal","tax_total","total"]`
  - Meta indexes: `(tenant, status)` named `crm_quo_tnt_status_idx`; `(tenant, created_at)` named
    `crm_quo_tnt_created_idx`; unique_together `(tenant, number)`

### 1g. `QuoteLine` — plain tenant-scoped (inline on quote detail)

Drivers: line items on quotes (all 10 leaders); nullable `product` FK for write-in lines (Dynamics 365,
SugarCRM, Salesforce); `order` for sort control; `unit_price` defaulting from `product.unit_price`
adjusted by `quote.price_book.price_adjustment_pct` (Salesforce price book item; Dynamics 365
PriceLevel); per-line discount + tax (SugarCRM %; DealHub per-line discount).

- [ ] Add `QuoteLine(models.Model)` (NOT TenantNumbered — child of Quote):
  - `tenant`        — `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="crm_quote_lines")`
  - `quote`         — `ForeignKey("crm.Quote", on_delete=CASCADE, related_name="lines")`
  - `product`       — `ForeignKey("crm.Product", on_delete=SET_NULL, null=True, blank=True,
                       related_name="quote_lines")` — nullable for write-in lines
  - `description`   — `CharField(max_length=500, blank=True)` — snapshot or write-in label
  - `quantity`      — `DecimalField(max_digits=10, decimal_places=2, default=1)`
  - `unit_price`    — `DecimalField(max_digits=12, decimal_places=2, default=0)` — from product or
                       overridden; if product FK set and quote has price_book, default =
                       `product.unit_price * (1 + price_book.price_adjustment_pct / 100)`
  - `discount_pct`  — `DecimalField(max_digits=5, decimal_places=2, default=0)` — per-line % discount
  - `tax_pct`       — `DecimalField(max_digits=5, decimal_places=2, default=0)` — per-line tax %;
                       defaults from `product.tax_pct` when product FK set
  - `order`         — `PositiveSmallIntegerField(default=0)` — display sort order
  - `@property line_subtotal` — `Decimal(quantity) * Decimal(unit_price) * (1 - discount_pct/100)`,
                                 Decimal-safe, 2dp
  - `@property line_tax`      — `line_subtotal * Decimal(tax_pct) / 100`, Decimal-safe
  - `@property line_total`    — `line_subtotal + line_tax`, Decimal-safe
  - `line_total` is NEVER stored; computed only — excluded from form
  - Meta: ordering `["quote", "order", "id"]`

### 1h. `SalesQuota` [QTA-] — `TenantNumbered`, `NUMBER_PREFIX = "QTA"`

Drivers: per-rep + per-territory quota definitions (Salesforce, Zoho, Clari, SugarCRM, HubSpot Sales
Hub Enterprise); `period_type` month/quarter/year (Zoho, Salesforce, Clari period buckets);
`period_year` + `period_number` integer pair (simpler than a DateField — avoids quarter-start date
ambiguity); unique_together prevents double-booking (Salesforce enforces one quota per rep/period).

- [ ] Add `SalesQuota(TenantNumbered)` with `NUMBER_PREFIX = "QTA"`:
  - `number`         — `CharField(max_length=20, editable=False)` — inherited
  - `owner`          — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                        related_name="crm_quotas")` — null = territory-only quota
  - `territory`      — `ForeignKey("crm.Territory", on_delete=SET_NULL, null=True, blank=True,
                        related_name="quotas")` — territory quota; both owner+territory can be set
  - `PERIOD_TYPE_CHOICES` — `[("month","Month"),("quarter","Quarter"),("year","Year")]`
  - `period_type`    — `CharField(max_length=8, choices=PERIOD_TYPE_CHOICES, default="quarter")`
  - `period_year`    — `PositiveSmallIntegerField()` — e.g. 2026
  - `period_number`  — `PositiveSmallIntegerField()` — month 1–12 or quarter 1–4 or 1 for year
  - `target_amount`  — `DecimalField(max_digits=14, decimal_places=2, default=0)` — revenue quota
  - Meta: unique_together `[("tenant","number"), ("tenant","owner","period_type","period_year",
    "period_number")]` — prevents duplicate quota rows per rep/period; index `(tenant, period_year)`
    named `crm_qta_tnt_year_idx`

---

## 2. Backend (`apps/crm/`)

### 2a. `models.py`

- [ ] Add module-level `PRODUCT_TYPE_CHOICES`, `FORECAST_CATEGORY_CHOICES`, `LOSS_REASON_CHOICES`,
  `PERIOD_TYPE_CHOICES` constants near top of file (before or after `TenantNumbered`)
- [ ] Implement `Territory(TenantNumbered)` with all fields, Meta indexes, `__str__`
- [ ] Implement `Product(TenantNumbered)` with all fields, `margin_pct` property, Meta indexes, `__str__`
- [ ] Implement `PriceBook(TenantNumbered)` with all fields, Meta indexes, `__str__`
- [ ] Enhance `Opportunity` — add 6 fields + update `save()` to stamp `lost_at` and `stage_changed_at`
  + add Meta index for `forecast_category`; keep all existing fields/props/Meta untouched
- [ ] Implement `OpportunitySplit(models.Model)` with all fields, `clean()` revenue-sum guard, Meta
- [ ] Implement `Quote(TenantNumbered)` with all fields + `recalc_totals()` method, Meta indexes, `__str__`
- [ ] Implement `QuoteLine(models.Model)` with all fields + `line_subtotal`/`line_tax`/`line_total`
  Decimal-safe properties, Meta ordering, `__str__`
- [ ] Implement `SalesQuota(TenantNumbered)` with all fields, dual unique_together, Meta index, `__str__`

### 2b. `forms.py`

- [ ] `TerritoryForm(ModelForm)` — fields: `name`, `region`, `segment`, `parent`, `manager`,
  `is_active`, `description`; exclude `tenant`, `number`; `parent` queryset scoped to
  `Territory.objects.filter(tenant=request.tenant)` (pass via `__init__` kwarg)
- [ ] `ProductForm(ModelForm)` — fields: `name`, `sku`, `product_type`, `unit_price`, `cost`,
  `tax_pct`, `is_active`, `description`; exclude `tenant`, `number`
- [ ] `PriceBookForm(ModelForm)` — fields: `name`, `currency_code`, `region`, `tier`,
  `price_adjustment_pct`, `is_default`, `is_active`, `description`; exclude `tenant`, `number`
- [ ] `OpportunityForm(ModelForm)` — EXTEND existing form to include new fields: `competitor`,
  `forecast_category`, `loss_reason`, `territory`; exclude system fields `lost_at`,
  `stage_changed_at`; `territory` queryset scoped to tenant
- [ ] `OpportunitySplitForm(ModelForm)` — fields: `user`, `split_type`, `percentage`; exclude
  `tenant`, `opportunity` (set in view); `user` queryset scoped to `request.tenant.users`
- [ ] `QuoteForm(ModelForm)` — fields: `opportunity`, `account`, `price_book`, `valid_until`,
  `currency_code`, `discount_pct`, `terms`, `owner`; **EXCLUDE** `status`, `subtotal`, `tax_total`,
  `total`, `sent_at`, `accepted_at`, `number`, `tenant` (all system-managed); FK querysets
  tenant-scoped in `__init__`
- [ ] `QuoteLineForm(ModelForm)` — fields: `product`, `description`, `quantity`, `unit_price`,
  `discount_pct`, `tax_pct`, `order`; **EXCLUDE** `tenant`, `quote`, computed line totals;
  `product` queryset scoped to tenant active products
- [ ] `SalesQuotaForm(ModelForm)` — fields: `owner`, `territory`, `period_type`, `period_year`,
  `period_number`, `target_amount`; exclude `tenant`, `number`; FK querysets tenant-scoped

### 2c. `views.py` — add to existing file

All views: `@login_required`, `tenant=request.tenant` scoping, `get_object_or_404(..., tenant=request.tenant)` on
every write, deletes POST-only, board + forecast aggregate DB-side.

- [ ] `territory_list` — search (name/region/segment `Q`), filter `is_active` (`'active'/'inactive'`),
  filter `parent` by pk; context: `territories`, `is_active_filter`, `status_choices=[("active","Active"),
  ("inactive","Inactive")]`; pagination 20
- [ ] `territory_create` — `TerritoryForm`; set `tenant` before save; redirect to `crm:territory_detail`
- [ ] `territory_detail` — child territories listed inline; back to list, edit/delete sidebar actions
- [ ] `territory_edit` — `TerritoryForm`; guard parent cannot be self or own descendant
- [ ] `territory_delete` — POST-only; redirect `crm:territory_list`
- [ ] `product_list` — search (name/sku Q), filter `product_type`, filter `is_active`; context:
  `products`, `product_type_choices`, `status_choices`; pagination 25
- [ ] `product_create` — `ProductForm`; set `tenant`; redirect `crm:product_detail`
- [ ] `product_detail` — margin_pct displayed; back/edit/delete sidebar
- [ ] `product_edit` — `ProductForm`
- [ ] `product_delete` — POST-only; redirect `crm:product_list`
- [ ] `pricebook_list` — search (name/region/tier Q), filter `is_active`, filter `is_default`;
  context: `pricebooks`, `status_choices`; pagination 20
- [ ] `pricebook_create` — `PriceBookForm`; set `tenant`; redirect `crm:pricebook_detail`
- [ ] `pricebook_detail` — shows adjustment_pct, quotes using this book listed inline (count);
  edit/delete sidebar
- [ ] `pricebook_edit` — `PriceBookForm`
- [ ] `pricebook_delete` — POST-only; redirect `crm:pricebook_list`
- [ ] `opportunity_list` — KEEP existing view but ensure new filter params work: add `forecast_category`
  filter (GET param `forecast_category`), `territory` filter (GET param `territory` pk); pass
  `forecast_category_choices` and `territories` to context; pagination unchanged
- [ ] `opportunity_create` / `opportunity_detail` / `opportunity_edit` / `opportunity_delete` — KEEP
  existing views but update forms to include new fields; `opportunity_detail` renders `splits` inline
  section with `OpportunitySplitForm`
- [ ] `opportunity_board` — GET; aggregates existing `Opportunity` queryset grouped by `stage` for
  Kanban columns; filters: `owner` (pk), `territory` (pk), `forecast_category`; context:
  `board_columns` (list of `{stage, label, opportunities, total_amount}`); renders
  `crm/sales/pipeline.html`
- [ ] `opportunity_advance` — POST; `pk` + `stage` (next stage in STAGE_CHOICES); tenant-scoped;
  updates `stage` and returns redirect to `crm:opportunity_detail` (or 302 to board)
- [ ] `opportunitysplit_add` — POST on opportunity detail; `OpportunitySplitForm`; runs `full_clean()`
  to invoke `clean()` revenue-sum guard; sets `tenant` + `opportunity`; redirect
  `crm:opportunity_detail`
- [ ] `opportunitysplit_remove` — POST; `pk` + implicit `opportunity_pk`; tenant-scoped on opportunity;
  redirect `crm:opportunity_detail`
- [ ] `quote_list` — search (number/account name Q), filter `status`, filter `opportunity` pk;
  context: `quotes`, `status_choices`, `opportunities`; pagination 20
- [ ] `quote_create` — `QuoteForm`; set `tenant`, `status="draft"`; call `recalc_totals()`; redirect
  `crm:quote_detail`
- [ ] `quote_detail` — renders `lines` inline with `QuoteLineForm` + add/remove actions; sidebar:
  Edit (draft only), Send, Accept, Decline, Delete (draft only), Print link; totals displayed
- [ ] `quote_edit` — `QuoteForm`; draft-only guard; after save call `recalc_totals()`
- [ ] `quote_delete` — POST-only; draft-only guard; redirect `crm:quote_list`
- [ ] `quoteline_add` — POST; `QuoteLineForm`; atomic with `recalc_totals()`; sets `tenant` + `quote`;
  default `unit_price` computed from product + price_book adjustment if both set; redirect
  `crm:quote_detail`
- [ ] `quoteline_remove` — POST; tenant-scoped via quote FK; atomic with `recalc_totals()`; redirect
  `crm:quote_detail`
- [ ] `quote_send` — POST; draft→sent transition; stamp `sent_at = timezone.now()`; idempotent guard
  (already sent → redirect with warning); redirect `crm:quote_detail`
- [ ] `quote_accept` — POST; sent→accepted; stamp `accepted_at`; update linked
  `opportunity.amount = quote.total` and advance stage toward "negotiation" if currently earlier;
  idempotent guard; redirect `crm:quote_detail`
- [ ] `quote_decline` — POST; sent→declined; idempotent guard; redirect `crm:quote_detail`
- [ ] `quote_print` — `@login_required` (NOT public); GET; renders `crm/sales/quote/print.html`;
  terms rendered with `|linebreaksbr` (never `|safe`)
- [ ] `forecast_view` — GET; reads `period_year` + `period_type` from GET (defaults: current year +
  "quarter"); aggregates `Opportunity` DB-side by `forecast_category`; joins `SalesQuota`; context:
  `by_category` (dict), `quotas_qs`, `period_year`, `period_type`, `pipeline_coverage` (pipeline /
  quota target or None), `closed_won_total`; renders `crm/sales/forecast.html`
- [ ] `salesquota_list` — filter `period_type`, `period_year`, `owner`; context: `quotas`,
  `period_type_choices`, `users`; pagination 20
- [ ] `salesquota_create` — `SalesQuotaForm`; set `tenant`; redirect `crm:salesquota_detail`
- [ ] `salesquota_detail` — shows target vs. closed-won actual for the period; edit/delete sidebar
- [ ] `salesquota_edit` — `SalesQuotaForm`
- [ ] `salesquota_delete` — POST-only; redirect `crm:salesquota_list`

### 2d. `urls.py` — add to existing `app_name = "crm"` urlconf

- [ ] Territory: `territory_list`, `territory_create`, `territory_detail/<int:pk>/`, `territory_edit/<int:pk>/`,
  `territory_delete/<int:pk>/`
- [ ] Product: `product_list`, `product_create`, `product_detail/<int:pk>/`, `product_edit/<int:pk>/`,
  `product_delete/<int:pk>/`
- [ ] PriceBook: `pricebook_list`, `pricebook_create`, `pricebook_detail/<int:pk>/`,
  `pricebook_edit/<int:pk>/`, `pricebook_delete/<int:pk>/`
- [ ] Opportunity extras: `opportunity_board` (GET), `opportunity_advance/<int:pk>/` (POST),
  `opportunitysplit_add/<int:opportunity_pk>/` (POST),
  `opportunitysplit_remove/<int:pk>/opportunity/<int:opportunity_pk>/` (POST)
- [ ] Quote: `quote_list`, `quote_create`, `quote_detail/<int:pk>/`, `quote_edit/<int:pk>/`,
  `quote_delete/<int:pk>/`, `quote_send/<int:pk>/`, `quote_accept/<int:pk>/`,
  `quote_decline/<int:pk>/`, `quote_print/<int:pk>/`
- [ ] QuoteLine: `quoteline_add/<int:quote_pk>/` (POST), `quoteline_remove/<int:pk>/quote/<int:quote_pk>/` (POST)
- [ ] SalesQuota: `salesquota_list`, `salesquota_create`, `salesquota_detail/<int:pk>/`,
  `salesquota_edit/<int:pk>/`, `salesquota_delete/<int:pk>/`
- [ ] Forecast: `forecast/` → `forecast_view`, name `forecast`

### 2e. `admin.py`

- [ ] Register `Territory` with `list_display=(number, name, region, manager, parent, is_active)`,
  `list_filter=(tenant, is_active)`, `search_fields=(name, region)`
- [ ] Register `Product` with `list_display=(number, name, sku, product_type, unit_price, is_active)`,
  `list_filter=(tenant, product_type, is_active)`, `search_fields=(name, sku)`
- [ ] Register `PriceBook` with `list_display=(number, name, currency_code, is_default, is_active)`,
  `list_filter=(tenant, is_default, is_active)`
- [ ] Register `OpportunitySplit` with `list_display=(opportunity, user, split_type, percentage)`,
  `list_filter=(tenant, split_type)`
- [ ] Register `Quote` with `list_display=(number, account, status, total, valid_until, owner)`,
  `list_filter=(tenant, status)`, `search_fields=(number,)`
- [ ] Register `QuoteLine` with `list_display=(quote, product, description, quantity, unit_price)`,
  `list_filter=(tenant,)`
- [ ] Register `SalesQuota` with `list_display=(number, owner, territory, period_type, period_year,
  period_number, target_amount)`, `list_filter=(tenant, period_type, period_year)`
- [ ] Enhance `Opportunity` admin to show new fields `competitor`, `forecast_category`, `territory`

### 2f. Migration

- [ ] `python manage.py makemigrations crm` — produces `apps/crm/migrations/0008_*.py`; verify it
  contains Territory, Product, PriceBook, OpportunitySplit, Quote, QuoteLine, SalesQuota models +
  ALTER TABLE on `crm_opportunity` for 6 new fields; no data loss to existing Opportunity rows

### 2g. Seeder (`apps/crm/management/commands/seed_crm.py`)

- [ ] Add `_seed_sfa(tenant)` function (called unconditionally in `handle()` like `_seed_marketing`):
  - Guard: `if Product.objects.filter(tenant=tenant).exists(): print("SFA already seeded."); return`
  - Create 3 `Territory` rows (e.g. North America, EMEA, APAC) with TER- numbers; EMEA.parent = None,
    APAC could be child of APAC-Pacific parent
  - Create 4 `Product` rows: 1 good (Hardware Widget), 1 service (Implementation), 1 subscription
    (SaaS Platform Annual), 1 service (Premium Support); each gets PRD- number via `save()`
  - Create 2 `PriceBook` rows: "Standard" (`is_default=True`, `price_adjustment_pct=0`) +
    "Enterprise" (`price_adjustment_pct=-10`); PB- numbers
  - Reuse first `Opportunity` (`Opportunity.objects.filter(tenant=tenant).first()`) — if none exists,
    create one minimal OPP- row — then attach 1 `Quote` (QUO-) with 2 `QuoteLine` rows; call
    `quote.recalc_totals()` after lines are created
  - Add 1 `OpportunitySplit` (revenue 60%) + 1 (overlay 100%) on that opportunity
  - Create 2 `SalesQuota` rows (QTA-): one for `period_type=quarter, period_year=2026, period_number=2`
    on a user; one for the North America Territory
  - All rows use `get_or_create` / existence check to stay idempotent; print summary counts

---

## 3. Wire-up

- [ ] `apps/core/navigation.py` — REWRITE `LIVE_LINKS["1.2"]` to replace the current 2-entry stub with
  the 8-entry full map (3 NavERP.md bullets verbatim + 5 extras):
  ```python
  "1.2": {
      # NavERP.md bullets (verbatim text)
      "Opportunity Management (Deals)": "crm:opportunity_list",   # bullet
      "Product Catalog (Quoting)":      "crm:product_list",       # bullet
      "Forecasting":                    "crm:forecast",            # bullet
      # Extra live links
      "Pipeline Board":   "crm:opportunity_board",   # extra (Kanban)
      "Quotes":           "crm:quote_list",           # extra
      "Price Books":      "crm:pricebook_list",       # extra
      "Sales Quotas":     "crm:salesquota_list",      # extra
      "Territories":      "crm:territory_list",       # extra
  },
  ```
  Note: existing `"crm:overview"` entry for Forecasting is replaced by `"crm:forecast"` (the new
  dedicated forecast view).

- [ ] `config/settings.py` — NO CHANGE (crm already in INSTALLED_APPS)
- [ ] `config/urls.py` — NO CHANGE (crm already included at `crm/`)

---

## 4. Templates (`templates/crm/sales/`)

All templates: `{% extends "base.html" %}`, Tailwind + HTMX patterns, filter-bar reflects `request.GET`,
Actions column = view/edit/delete (CRUD rules), pagination with empty-state. Never `|safe` on user text.

### Territory
- [ ] `sales/territory/list.html` — table (number, name, region, segment, parent→link, manager, is_active);
  filter bar: search `q`, `is_active` select; Actions column: view/edit/delete-POST+confirm+csrf;
  "New Territory" button; empty-state; pagination
- [ ] `sales/territory/detail.html` — all fields displayed; child territories inline list; sidebar:
  Edit / Delete (POST+confirm) / Back to List
- [ ] `sales/territory/form.html` — create + edit (pre-filled); `parent` select (excludes self on edit);
  `manager` select; cancel → list

### Product
- [ ] `sales/product/list.html` — table (number, name, sku, product_type badge, unit_price, margin_pct%,
  is_active badge); filter bar: search `q`, `product_type` select (pass `product_type_choices`),
  `is_active` select; Actions; "New Product"; pagination
- [ ] `sales/product/detail.html` — all fields; margin_pct computed; sidebar Edit/Delete/Back
- [ ] `sales/product/form.html` — create + edit; product_type select; numeric fields; cancel → list

### PriceBook
- [ ] `sales/pricebook/list.html` — table (number, name, currency_code, region, tier, price_adjustment_pct,
  is_default badge, is_active badge); filter bar: search `q`, `is_active` select; Actions; "New Price Book"
- [ ] `sales/pricebook/detail.html` — all fields; count of quotes using this book; sidebar Edit/Delete/Back
- [ ] `sales/pricebook/form.html` — create + edit; currency_code text input (with placeholder "USD");
  numeric adjustment_pct; is_default checkbox; cancel → list

### Opportunity (extend existing — MOVE to sales/ submodule folder)
- [ ] `sales/opportunity/list.html` — extend existing list template under `sales/opportunity/`; add
  `forecast_category` badge column, `territory` column; filter bar gains `forecast_category` select +
  `territory` select (pass `forecast_category_choices`, `territories`); existing search/stage/owner
  filters retained
- [ ] `sales/opportunity/detail.html` — extend existing; add new field display block (competitor,
  forecast_category, loss_reason, lost_at, territory, stage_changed_at); add **Splits inline section**:
  table of splits (user, split_type, percentage, delete POST); `OpportunitySplitForm` to add new split;
  "Advance Stage" button (POST `opportunity_advance`); keep existing fields above
- [ ] `sales/opportunity/form.html` — extend existing form; add new fields in a "SFA Details" fieldset:
  `competitor`, `forecast_category`, `loss_reason`, `territory`; `loss_reason` shown only when stage =
  closed_lost (JS/HTMX show/hide); existing fields unchanged

### Quote
- [ ] `sales/quote/list.html` — table (number, account name, opportunity number→link, status badge,
  total, valid_until, owner); filter bar: search `q`, `status` select (pass `status_choices`),
  `opportunity` select (pass `opportunities`); Actions: view/edit(draft-only)/delete(draft-only)/print;
  "New Quote"; pagination
- [ ] `sales/quote/detail.html` — header section: all Quote fields; **Line Items section**: table of
  QuoteLines (description, qty, unit_price, discount_pct%, tax_pct%, line_subtotal, line_tax,
  line_total; Remove POST button per line); `QuoteLineForm` at bottom to add line (product select
  auto-fills unit_price + tax_pct via JS/HTMX); totals footer (subtotal, tax, quote-discount, TOTAL);
  **sidebar**: Edit (draft only), Send (draft only — POST `quote_send`), Accept (sent only — POST
  `quote_accept`), Decline (sent only — POST `quote_decline`), Print (`quote_print` GET link),
  Delete (draft only — POST+confirm), Back to List; sent_at / accepted_at displayed when set
- [ ] `sales/quote/form.html` — create + edit; opportunity select; account select; price_book select;
  currency_code text; discount_pct; valid_until date; terms textarea; owner select; cancel → list;
  note: status/totals/timestamps NOT in form (excluded)
- [ ] `sales/quote/print.html` — print-optimized; `@media print` CSS; company name/logo placeholder;
  quote header (number, date, valid_until, client); line items table (description, qty, unit_price,
  line_total); subtotal/tax/discount/TOTAL rows; `terms` rendered `|linebreaksbr` (never `|safe`);
  no base navbar (standalone layout with minimal chrome); login-gated (no public access)

### Pipeline Board (standalone)
- [ ] `sales/pipeline.html` — Kanban columns from `board_columns` context; each column: stage label,
  count + total amount; cards: deal name→detail link, account, amount, close_date, probability badge,
  forecast_category badge; filter bar: `owner` select, `territory` select, `forecast_category` select;
  "Advance" button on each card (POST `opportunity_advance` to next stage); responsive horizontal scroll

### Forecast Dashboard (standalone)
- [ ] `sales/forecast.html` — period selector (year + period_type GET form); KPI cards: Closed Won,
  Weighted Pipeline, Best Case, Commit, Quota Target, Pipeline Coverage Ratio; table: forecast_category
  rows (label, count, total_amount, weighted_amount); Quota vs. Actual per rep/territory table from
  `quotas_qs`; all data from context (no inline JS fetches); aggregate DB-side

### SalesQuota
- [ ] `sales/salesquota/list.html` — table (number, owner, territory, period_type, period label,
  target_amount); filter bar: `period_type` select, `period_year` text, `owner` select; Actions;
  "New Quota"; pagination
- [ ] `sales/salesquota/detail.html` — all fields; computed closed_won actual for the period; gap to
  quota; sidebar Edit/Delete/Back
- [ ] `sales/salesquota/form.html` — owner select, territory select, period_type select, period_year
  number input, period_number number input, target_amount; cancel → list

---

## 5. Verify

- [ ] `python manage.py makemigrations crm` — confirms only migration 0008 produced (no spurious
  changes to prior models)
- [ ] `python manage.py migrate` — applies 0008 cleanly; no errors
- [ ] `python manage.py seed_crm` — first run: seeds SFA data + prints counts; no errors
- [ ] `python manage.py seed_crm` again (×2 idempotency) — prints "SFA already seeded." for SFA
  section; no duplicate rows created; no IntegrityError
- [ ] `python manage.py check` — 0 issues
- [ ] `temp/smoke_sfa.py` — sweep all `crm:*` SFA urls returning 200 or 302 (authenticated as
  tenant admin):
  - All list pages: territory_list, product_list, pricebook_list, opportunity_list, quote_list,
    salesquota_list → 200
  - opportunity_board → 200 (pipeline.html rendered)
  - forecast → 200 (forecast.html rendered with period defaults)
  - Territory/Product/PriceBook/Quote/SalesQuota create (GET) → 200
  - Territory/Product/PriceBook/Quote/SalesQuota detail (seeded pk) → 200
  - Territory/Product/PriceBook/Quote/SalesQuota edit (GET) → 200
  - quote_print (seeded pk) → 200 (login-gated; no public access)
  - quote_send (POST) → 302; second POST on same quote → 302 with warning (idempotent)
  - quote_accept (POST after send) → 302; opportunity.amount updated to quote.total
  - quote_decline on a sent quote → 302; status = declined
  - QuoteLine add (POST) → 302; quote.subtotal / tax_total / total updated by recalc_totals()
  - QuoteLine remove (POST) → 302; totals recalculated
  - OpportunitySplit add revenue 60% + revenue 50% = 110% → 400/form error (sum > 100% rejected)
  - opportunity_advance (POST) → 302; stage advances
  - Cross-tenant IDOR: GET/POST on Territory/Product/PriceBook/Quote/SalesQuota/Opportunity pk
    belonging to a different tenant → 404
  - No `{#` or `{% comment` leaks in rendered HTML (search rendered output)
  - Superuser (no tenant) hitting any list → 0 results (empty-state shown, not crash)

---

## 6. Close-out

- [ ] **code-reviewer** agent — apply findings; commit
- [ ] **explorer** agent — apply findings; commit
- [ ] **frontend-reviewer** agent — apply findings; commit
- [ ] **performance-reviewer** agent — apply findings; commit
- [ ] **qa-smoke-tester** agent — apply findings; commit
- [ ] **security-reviewer** agent — apply findings; commit
- [ ] **test-writer** agent — write pytest suite for SFA; commit
- [ ] Update `.claude/skills/crm/SKILL.md` — add 1.2 SFA section (Territory/Product/PriceBook/
  Opportunity enhancements/OpportunitySplit/Quote/QuoteLine/SalesQuota models, new url names,
  new templates under `sales/`, `_seed_sfa` seeder, LIVE_LINKS["1.2"] rewrite); commit
- [ ] Update module README if one exists; commit

---

## 7. Later passes / deferred

- **PriceBookEntry join table** — per-product price override per price book (unit_price + min_qty);
  skipped this pass; `price_adjustment_pct` on PriceBook covers the common ±% case. Future enhancement.
- **Multiple sales pipelines** — distinct pipeline definitions per product line / sales motion;
  one default pipeline covers SMB. Deferred: new `Pipeline` + `PipelineStage` tables.
- **Product bundling / kits** — self-FK on Product or separate bundle_line table; adds quoting
  complexity. Deferred.
- **Volume / tiered discount schedules** — `DiscountSchedule` + `DiscountTier` tables for quantity-
  break pricing. Manual per-line discount covers initial need. Deferred.
- **PDF library rendering** — WeasyPrint/wkhtmltopdf for true PDF; browser "Print to PDF" covers
  the immediate requirement. Integration/later.
- **E-signature delivery on quotes** — DocuSign/HelloSign integration; existing `ContractDocument`/
  `SignerRecord` models the tracking, but delivery requires an e-sign provider. Integration/later.
- **Quote → Sales Order sync** — push accepted quote into Module 8 `SalesOrder`; blocked until
  Module 8 (Sales) is built.
- **Quote → Invoice sync** — push accepted quote into Module 2 AR; blocked until Module 2 is built.
- **AI predictive deal scoring** — win probability from activity signals (Salesforce Einstein, Clari,
  Freshsales Freddy). Requires external ML inference. Integration/later.
- **AI forecast accuracy / range** — HubSpot/Clari best/worst/likely AI forecast. Integration/later.
- **Commission payout calculation** — dollar amounts from `OpportunitySplit` percentages; payroll
  integration required. Deferred to Module 3 HRM/Payroll or dedicated commission module.
- **OpportunityContact junction** — stakeholder roles (Decision Maker, Champion, Economic Buyer);
  useful but not blocking core quoting. Follow-up sub-module pass.
- **Real-time FX conversion** — multi-currency with live exchange rates; `currency_code` CharField
  is sufficient now. Deferred to Module 2 Accounting.
- **Inline pipeline editing (HTMX)** — edit amount/stage/close_date inline on board without full
  reload; secondary pass after board is stable.
- **Deal velocity / stage-age reporting** — average days per stage from `stage_changed_at` history;
  secondary analytics pass.
- **Approval workflow for over-discount quotes** — connect existing `WorkflowRule`/`ApprovalRequest`
  to quotes exceeding discount threshold; no new model needed but wiring work. Secondary pass.

---

## 8. Review notes — CRM §1.2 Sales Force Automation (recreated in detail) ✅

**Delivered (migrations 0008–0011):** enhanced `Opportunity` (forecast_category/competitor/loss_reason +
system lost_at & stage_changed_at via from_db/save, territory) + 7 new entities — `Territory` (TER-, self-FK
hierarchy), `Product` (PRD-, sales catalog, margin), `PriceBook` (PB-, ±% regional/tier), `OpportunitySplit`
(revenue ≤100% + bounded percentage), `Quote` (QUO-, system status/totals, `recalc_totals`), `QuoteLine`
(Decimal-safe line props), `SalesQuota` (QTA-, per-rep/territory period). Plus a **Kanban pipeline board**, a
**quote builder** with printable output, and a **forecast dashboard** (weighted pipeline by category + quota
attainment). `LIVE_LINKS["1.2"]` lights up all 3 NavERP bullets + 5 extras. 21 templates under
`templates/crm/sales/`. `_seed_sfa` seeder (unconditional, Product-guarded). One file per commit to `main`.

**Verification:** `manage.py check` clean; migrations apply; `seed_crm` idempotent (×2); `temp/smoke_sfa.py`
all green; **980 CRM pytest tests pass** (235 new in `test_sfa.py` + 3 pre-existing Opportunity tests fixed for
the now-required `forecast_category`).

**Review agents (CLAUDE.md sequence), findings applied:**
- **code-reviewer** — OpportunitySplit.clean tenant guard, Opportunity.save None sentinel, SalesQuota
  unique_together + territory + SalesQuotaForm dup guard, territory-aware forecast attainment, quote-print
  linebreaksbr. (False positive: `is_active` string filter — verified Django coerces it.)
- **explorer** — confirmed full URL/context/field consistency; no code changes (backslash-path note was a false
  positive — all paths use forward slashes).
- **frontend-reviewer** — valid `kanban` icon, pipeline board theme vars (--page-bg/--radius) + `.btn-sm`,
  forecast progress-bar pct clamp, dropped unused `{% load static %}`.
- **performance-reviewer** — board 12→7 queries (one grouped aggregate), territory_detail children
  select_related, defer(description) on 3 lists, OpportunitySplit.clean DB-side Sum, SalesQuota (tenant,territory)
  index.
- **qa-smoke-tester** — 74/74 checks pass, no changes.
- **security-reviewer** (Medium) — bounded all percentage/discount/tax fields (no negative/over-100 that distort
  totals); documented the deliberate `@login_required` (rep workflow) choice on quote send/accept + advance.
- **test-writer** — 235 tests + surfaced a **real cross-DB bug**: `recalc_totals` used `F()/100` which
  integer-divided on SQLite (dropped line discounts) → fixed to a portable Python sum over line properties.

**Spine-gap note:** Product/PriceBook/Quote are CRM-owned (core.Item/PriceList/Currency/SalesOrder unbuilt);
`currency_code` is a CharField; quote→sales-order sync deferred. Other deferrals: PriceBookEntry per-product
pricing, real PDF/e-sign, CPQ rules/approval workflows, AI forecasting, commission payout, multi-currency FX.

---

# Module 1 CRM §1.4 — Customer Service & Support / Help Desk (crm) — plan from research-crm-helpdesk.md  (2026-06-26)

**Extending `apps/crm`** — NOT a new app. Next migration is **0012**. The plan enhances two existing
models (`Case` at line 865, `KnowledgeArticle` at line 936) and adds four new ones, all in
`apps/crm/models.py`. Sub-module template folder: `templates/crm/service/`. Public + portal pages
extend `base_auth.html` / `base.html` respectively (no login required for token pages; portal login-gated
via `CustomerPortalAccess` check helper).

---

## 0. Template folder layout (decide before any code)

All 1.4 entities live under `templates/crm/service/` (per CLAUDE.md two-level rule: sub-module=`service`,
entity folder per model).

- [ ] Confirm folder shape:
  - `service/slapolicy/{list,detail,form}.html`            — SlaPolicy CRUD
  - `service/case/{list,detail,form}.html`                 — Case CRUD (recreate existing flat templates)
  - `service/kbcategory/{list,detail,form}.html`           — KbCategory CRUD
  - `service/knowledgearticle/{list,detail,form}.html`     — KnowledgeArticle CRUD (recreate existing)
  - `service/customerportalaccess/{list,detail,form}.html` — CustomerPortalAccess CRUD
  - `service/case_public.html`                             — standalone public token page (no login)
  - `service/kb_public.html`                               — standalone public KB article page (no login)
  - `service/portal_case_list.html`                        — portal: customer's case list
  - `service/portal_case_detail.html`                      — portal: customer's case detail (public comments only)
  - `service/portal_case_form.html`                        — portal: submit new case
  - NOTE: `CaseComment` rows render **inline on case detail** — no standalone list/form templates.

---

## 1. Models (all changes in `apps/crm/models.py`, migration 0012)

### 1a. `SlaPolicy` [SLA-] — `TenantNumbered`, `NUMBER_PREFIX = "SLA"`

Drivers: Freshdesk/Zendesk/HubSpot priority-tiered FRT + resolution targets in hours; one policy covers
all four priorities in a single row (avoids multi-row fan-out, avoids unique_together on priority).

- [ ] Add `SlaPolicy(TenantNumbered)` with `NUMBER_PREFIX = "SLA"`:
  - `name`               — `CharField(max_length=255)` — e.g. "Standard", "VIP", "Urgent"
  - `description`        — `TextField(blank=True)`
  - `is_active`          — `BooleanField(default=True)`
  - `is_default`         — `BooleanField(default=False)` — at most one default per tenant (enforced in save/admin)
  - `response_low`       — `PositiveSmallIntegerField(default=48)` — first-response target in hours for Low priority
  - `response_medium`    — `PositiveSmallIntegerField(default=24)` — first-response target in hours for Medium
  - `response_high`      — `PositiveSmallIntegerField(default=8)`  — first-response target in hours for High
  - `response_critical`  — `PositiveSmallIntegerField(default=1)`  — first-response target in hours for Critical
  - `resolution_low`     — `PositiveSmallIntegerField(default=120)` — resolution target in hours for Low
  - `resolution_medium`  — `PositiveSmallIntegerField(default=72)`  — resolution target in hours for Medium
  - `resolution_high`    — `PositiveSmallIntegerField(default=24)`  — resolution target in hours for High
  - `resolution_critical`— `PositiveSmallIntegerField(default=8)`   — resolution target in hours for Critical
  - `Meta.indexes`: `(tenant, is_active)` named `crm_sla_tnt_active_idx`; `(tenant, is_default)` named
    `crm_sla_tnt_default_idx`
  - Method `targets_for(priority)` → `(response_hours, resolution_hours)` integer tuple; maps
    `"low"/"medium"/"high"/"critical"` → the matching pair of fields; raises `ValueError` for unknown priority
  - `__str__`: `f"{self.number} · {self.name}"`

### 1b. Enhance `Case` (existing at `apps/crm/models.py:865`) — ADD fields only

Drivers: Freshdesk/Zendesk dual SLA timers (FRT + resolution), CSAT on close, public token URL,
first-response stamping, closed_at system stamp.

- [ ] Add the following fields to `Case` (after existing `resolved_at`):
  - `sla_policy`             — `ForeignKey("crm.SlaPolicy", on_delete=SET_NULL, null=True, blank=True,
                               related_name="cases")` — policy applied at case creation
  - `first_response_due`     — `DateTimeField(null=True, blank=True)` — system-computed; not on forms
  - `first_responded_at`     — `DateTimeField(null=True, blank=True)` — system-stamped on first public
                               agent reply via `case_comment_add`; not on forms
  - `resolution_due`         — `DateTimeField(null=True, blank=True)` — system-computed; not on forms
  - `closed_at`              — `DateTimeField(null=True, blank=True)` — system-stamped when status=closed;
                               cleared if re-opened; not on forms
  - `satisfaction_rating`    — `PositiveSmallIntegerField(null=True, blank=True)` — 1–5 CSAT score; set
                               via public token page or portal; not on agent forms
  - `satisfaction_comment`   — `TextField(blank=True)` — optional free-text CSAT feedback
  - `satisfaction_at`        — `DateTimeField(null=True, blank=True)` — system-set on submission
  - `public_token`           — `CharField(max_length=64, unique=True, blank=True)` — unguessable token;
                               auto-generated in `save()` via `secrets.token_urlsafe(32)`
- [ ] Extend `Case.save()`:
  - Keep existing `resolved_at` logic
  - Stamp `closed_at = timezone.now()` when `status == "closed"` and `closed_at is None`; clear
    `closed_at` if status moves back to an open status (re-open scenario)
  - When `sla_policy` is set and `first_response_due is None`, call
    `sla_policy.targets_for(priority)` anchored at `(self.created_at or timezone.now())` to compute
    `first_response_due = anchor + timedelta(hours=response_hours)` and
    `resolution_due = anchor + timedelta(hours=resolution_hours)`
  - Generate `public_token = secrets.token_urlsafe(32)` if `public_token` is blank
- [ ] Add `Case` properties:
  - `is_response_overdue` — `True` when `first_response_due` is set AND `first_responded_at is None`
    AND `is_open` AND `first_response_due < timezone.now()`
  - `is_resolution_overdue` — `True` when `resolution_due` is set AND `is_open` AND
    `resolution_due < timezone.now()`
  - Keep existing `is_open` and `is_overdue` unchanged
- [ ] Add `Meta.indexes` entry: `(tenant, priority)` named `crm_case_tnt_priority_idx`

### 1c. `CaseComment` (plain model — NOT TenantNumbered)

Drivers: Universal across all 10 surveyed products — Zendesk yellow-bg internal notes, Freshdesk
private/public toggle, Help Scout notes/replies, JSM internal/public comments.

- [ ] Add `CaseComment(models.Model)` (no number prefix, no TenantNumbered):
  - `tenant`       — `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="crm_case_comments")`
  - `case`         — `ForeignKey("crm.Case", on_delete=CASCADE, related_name="comments")`
  - `author`       — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                     related_name="crm_case_comments")` — snapshot of who posted; null for system
  - `author_name`  — `CharField(max_length=255, blank=True)` — snapshot of author display name at post time
  - `body`         — `TextField()` — comment content
  - `is_public`    — `BooleanField(default=False)` — False = internal/agent-only note; True = customer-visible reply
  - `created_at`   — `DateTimeField(auto_now_add=True)`
  - `Meta.ordering = ["created_at"]` (chronological thread)
  - `Meta.indexes`: `(tenant, case)` named `crm_ccomment_tnt_case_idx`
  - `__str__`: `f"Comment on {self.case_id} by {self.author_name}"`

### 1d. `KbCategory` [KBC-] — `TenantNumbered`, `NUMBER_PREFIX = "KBC"`

Drivers: Zoho Desk (Category > Sections), JSM categories, Freshdesk (categories + folders), Zendesk
(categories + sections) — 2-level hierarchy; replaces the flat `KnowledgeArticle.category CharField`.

- [ ] Add `KbCategory(TenantNumbered)` with `NUMBER_PREFIX = "KBC"`:
  - `name`         — `CharField(max_length=255)`
  - `description`  — `TextField(blank=True)`
  - `slug`         — `CharField(max_length=160, blank=True)` — URL-safe slug for portal browsing (blank ok)
  - `parent`       — `ForeignKey("self", on_delete=SET_NULL, null=True, blank=True,
                     related_name="child_categories")` — enables parent → child hierarchy (2 levels)
  - `order`        — `PositiveSmallIntegerField(default=0)` — display ordering within parent
  - `is_active`    — `BooleanField(default=True)`
  - `Meta.ordering = ["order", "name"]`
  - `Meta.indexes`: `(tenant, is_active)` named `crm_kbcat_tnt_active_idx`
  - `__str__`: `f"{self.number} · {self.name}"`

### 1e. Enhance `KnowledgeArticle` (existing at `apps/crm/models.py:936`) — ADD fields only

Drivers: Zoho Desk (helpful/not-helpful votes), JSM (voted-as-helpful deflection metric), Zendesk article
votes; `category FK KbCategory` replaces legacy `category CharField` without removing the old field yet
(keep it as `category_legacy` or deprecate — migration copies string to KbCategory name if needed).

- [ ] Add the following fields to `KnowledgeArticle`:
  - `kb_category`        — `ForeignKey("crm.KbCategory", on_delete=SET_NULL, null=True, blank=True,
                           related_name="articles")` — structured category replacing flat CharField
  - `helpful_count`      — `PositiveIntegerField(default=0)` — F()-incremented; excluded from forms
  - `not_helpful_count`  — `PositiveIntegerField(default=0)` — F()-incremented; excluded from forms
  - `public_token`       — `CharField(max_length=64, unique=True, blank=True)` — auto-generated in
                           `save()` for external-visibility articles; enables no-login public URL
  - `slug`               — `CharField(max_length=200, blank=True)` — optional URL slug for portal
- [ ] Extend `KnowledgeArticle.save()`:
  - Generate `public_token = secrets.token_urlsafe(32)` if `public_token` is blank
- [ ] Add `Meta.indexes` entry: `(tenant, kb_category)` named `crm_kb_tnt_cat_idx`
- [ ] NOTE: keep legacy `category = CharField(max_length=120, blank=True)` in place (do NOT drop it in
  migration 0012 — rename it to `category_legacy` or leave as-is; deferred cleanup)

### 1f. `CustomerPortalAccess` [CSP-] — `TenantNumbered`, `NUMBER_PREFIX = "CSP"`

Drivers: HubSpot (login-required customer portal), Freshdesk (customer accounts + ticket access),
Zoho Desk (client portal), JSM (customer request portal) — mirrors existing `PartnerPortalAccess`
pattern (§1.12) for customer-side helpdesk access.

- [ ] Add `CustomerPortalAccess(TenantNumbered)` with `NUMBER_PREFIX = "CSP"`:
  - `customer_party`  — `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True,
                        related_name="crm_portal_accesses")` — the customer org/contact this grant covers
  - `portal_user`     — `OneToOneField(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
                        related_name="crm_customer_portal_access")` — Django User login for the customer
  - `can_submit_cases`— `BooleanField(default=True)` — allow/deny ticket submission from portal
  - `accepted_at`     — `DateTimeField(null=True, blank=True)` — system-set on first portal login/activate
  - `is_active`       — `BooleanField(default=True)`
  - `Meta.indexes`: `(tenant, is_active)` named `crm_cpa_tnt_active_idx`; `(tenant, customer_party)`
    named `crm_cpa_tnt_party_idx`
  - `__str__`: `f"{self.number} · {self.customer_party}"`

---

## 2. Backend — `apps/crm/`

### 2a. `models.py` (migration 0012)

- [ ] Insert `SlaPolicy` class before `Case` class in `models.py`
- [ ] Add all new fields to `Case` (§1b above); extend `save()`; add properties; add priority index
- [ ] Add `CaseComment` class after `Case` in `models.py`
- [ ] Add `KbCategory` class before `KnowledgeArticle` in `models.py`
- [ ] Add all new fields to `KnowledgeArticle` (§1e above); extend `save()`; add kb_category index
- [ ] Add `CustomerPortalAccess` class after `KnowledgeArticle` in `models.py`
- [ ] Run `python manage.py makemigrations crm --name helpdesk` — produces `0012_helpdesk.py`

### 2b. `forms.py`

- [ ] `SlaPolicyForm(forms.ModelForm)` — fields: `name, description, is_active, is_default,
  response_low, response_medium, response_high, response_critical,
  resolution_low, resolution_medium, resolution_high, resolution_critical`; exclude `tenant`, `number`
- [ ] Extend `CaseForm` — add `sla_policy` to included fields; exclude system fields:
  `first_response_due, first_responded_at, resolution_due, closed_at, resolved_at,
  public_token, satisfaction_rating, satisfaction_comment, satisfaction_at`
- [ ] `KbCategoryForm(forms.ModelForm)` — fields: `name, description, slug, parent, order, is_active`;
  exclude `tenant`, `number`; `parent` queryset filtered to tenant in `__init__` (no self-reference on
  create: exclude self.instance.pk when editing)
- [ ] Extend `KnowledgeArticleForm` — add `kb_category` to included fields; exclude system fields:
  `helpful_count, not_helpful_count, public_token, views_count`; `kb_category` queryset filtered to
  tenant in `__init__`
- [ ] `CustomerPortalAccessForm(forms.ModelForm)` — fields: `customer_party, portal_user,
  can_submit_cases, accepted_at, is_active`; exclude `tenant`, `number`; `customer_party` queryset
  filtered to tenant in `__init__`
- [ ] `CaseCommentForm(forms.ModelForm)` — fields: `body, is_public`; exclude `tenant, case, author,
  author_name, created_at`; used inline on case detail (agent toggles is_public)
- [ ] `PublicSatisfactionForm(forms.Form)` — fields: `rating (IntegerField, min=1 max=5)`,
  `comment (CharField, max_length=2000, required=False)`; for public token CSAT submission
- [ ] `PublicCommentForm(forms.Form)` — fields: `body (CharField, max_length=5000)`; for portal
  customer reply (portal view forces `is_public=True` before saving as `CaseComment`)

### 2c. `views.py` — all function-based, `@login_required` for agent/portal views

#### SlaPolicy CRUD (agent, standard)
- [ ] `slapolicy_list` — tenant-scoped qs; search by name (`q`); filter by `is_active`; pass
  `status_choices=[("active","Active"),("inactive","Inactive")]`; paginate 20
- [ ] `slapolicy_create` via `crud_create` helper — `SlaPolicyForm`; template
  `crm/service/slapolicy/form.html`
- [ ] `slapolicy_detail` — detail page showing all response/resolution targets; template
  `crm/service/slapolicy/detail.html`
- [ ] `slapolicy_edit` via `crud_edit` helper — pre-filled form; template
  `crm/service/slapolicy/form.html`
- [ ] `slapolicy_delete` — POST-only, tenant-scoped `get_object_or_404`, redirect to
  `crm:slapolicy_list`

#### Case CRUD (agent, recreated with SLA + comments)
- [ ] `case_list` — tenant-scoped; search by `subject/number`; filter by `status, priority, origin,
  sla_policy`; pass `status_choices, priority_choices, origin_choices, sla_policies`; annotate SLA
  breach flags from properties; paginate 25
- [ ] `case_create` via `crud_create` helper — `CaseForm`; template
  `crm/service/case/form.html`
- [ ] `case_detail` — tenant-scoped detail; load `case.comments.order_by("created_at")` (all for
  agent); show SLA breach badges (`is_response_overdue`, `is_resolution_overdue`); inline
  `CaseCommentForm`; show satisfaction rating if set; template `crm/service/case/detail.html`
- [ ] `case_edit` via `crud_edit` helper — `CaseForm`; template `crm/service/case/form.html`
- [ ] `case_delete` — POST-only, tenant-scoped, redirect to `crm:case_list`

#### CaseComment custom action
- [ ] `case_comment_add(request, pk)` — `@login_required`; POST-only; get_object_or_404 Case by
  `pk + tenant`; validate `CaseCommentForm`; snapshot `author_name = request.user.get_full_name()
  or request.user.username`; create `CaseComment(tenant, case, author, author_name, body,
  is_public)`; if `is_public=True` AND `case.first_responded_at is None`, stamp
  `case.first_responded_at = timezone.now()` and save Case; redirect to `crm:case_detail pk`
  (driver: Freshdesk/Zendesk FRT stamping on first public agent reply)

#### KbCategory CRUD (agent, standard)
- [ ] `kbcategory_list` — tenant-scoped; search by name; filter by `is_active, parent`; pass
  `status_choices, parent_categories` (root categories only); paginate 20
- [ ] `kbcategory_create` via `crud_create` helper — `KbCategoryForm`; template
  `crm/service/kbcategory/form.html`
- [ ] `kbcategory_detail` — show parent, child_categories, linked articles count; template
  `crm/service/kbcategory/detail.html`
- [ ] `kbcategory_edit` via `crud_edit` helper; template `crm/service/kbcategory/form.html`
- [ ] `kbcategory_delete` — POST-only, tenant-scoped, redirect to `crm:kbcategory_list`

#### KnowledgeArticle CRUD (agent, recreated with kb_category + vote counts)
- [ ] `knowledgearticle_list` — tenant-scoped; search by title; filter by `status, visibility,
  kb_category`; pass `status_choices, visibility_choices, kb_categories`; paginate 20
- [ ] `knowledgearticle_create` via `crud_create` helper — `KnowledgeArticleForm`; template
  `crm/service/knowledgearticle/form.html`
- [ ] `knowledgearticle_detail` — increment `views_count` via `F()` on GET; show `helpful_count /
  not_helpful_count`; show public link if `public_token` set; template
  `crm/service/knowledgearticle/detail.html`
- [ ] `knowledgearticle_edit` via `crud_edit` helper; template
  `crm/service/knowledgearticle/form.html`
- [ ] `knowledgearticle_delete` — POST-only, tenant-scoped, redirect to
  `crm:knowledgearticle_list`

#### CustomerPortalAccess CRUD (agent, standard)
- [ ] `customerportalaccess_list` — tenant-scoped; search by party name; filter by `is_active,
  can_submit_cases`; pass `status_choices`; paginate 20
- [ ] `customerportalaccess_create` via `crud_create` helper; template
  `crm/service/customerportalaccess/form.html`
- [ ] `customerportalaccess_detail`; template
  `crm/service/customerportalaccess/detail.html`
- [ ] `customerportalaccess_edit` via `crud_edit` helper; template
  `crm/service/customerportalaccess/form.html`
- [ ] `customerportalaccess_delete` — POST-only, tenant-scoped, redirect to
  `crm:customerportalaccess_list`

#### Public no-login views (no `@login_required`)
- [ ] `case_public(request, token)` — GET: `get_object_or_404(Case, public_token=token)`; expose
  only `subject, status, priority, created_at` and last `is_public=True` CaseComment; render
  `crm/service/case_public.html`; POST (CSAT): validate `PublicSatisfactionForm`; if Case is
  resolved/closed and `satisfaction_rating is None`, set `satisfaction_rating, satisfaction_comment,
  satisfaction_at`; redirect back with success message; security: no tenant data exposed beyond the
  token-scoped case, body/comment escaped (never `|safe`), CSRF required on POST
- [ ] `kb_public(request, token)` — `get_object_or_404(KnowledgeArticle, public_token=token,
  visibility="external", status="published")`; increment `views_count` via `F()`;
  render `crm/service/kb_public.html`; draft/internal → 404 by queryset filter
- [ ] `kb_helpful(request, token)` — POST-only; no login; `get_object_or_404(KnowledgeArticle,
  public_token=token, status="published")`; read `vote` from POST (`helpful`/`not_helpful`);
  `F()` increment `helpful_count` or `not_helpful_count`; redirect back to `kb_public` with
  `?voted=1`; CSRF required

#### Portal login-gated views (helper + 3 views)
- [ ] `_customer_portal_access(request)` helper — returns `CustomerPortalAccess` for
  `portal_user=request.user, tenant=request.tenant, is_active=True`; raises `Http404` if not found
  (gates all portal views)
- [ ] `portal_case_list(request)` — `@login_required`; call `_customer_portal_access`; filter
  `Case.objects.filter(tenant=request.tenant, account=access.customer_party)`; filter by status
  (GET param); show only public CaseComment count; render `crm/service/portal_case_list.html`
- [ ] `portal_case_detail(request, pk)` — `@login_required`; call `_customer_portal_access`; get
  Case by `pk + tenant + account=access.customer_party` (IDOR = 404); show only `is_public=True`
  comments; `PublicCommentForm` for new reply; on POST: create `CaseComment(is_public=True,
  author=request.user, author_name=...)`; if `case.status == "waiting"`, set `status = "open"` and
  save; render `crm/service/portal_case_detail.html`
- [ ] `portal_case_create(request)` — `@login_required`; call `_customer_portal_access`; check
  `access.can_submit_cases`; on POST: validate form (subject/description/priority); force
  `origin="portal"`, `account=access.customer_party`, `tenant=request.tenant`; create Case; redirect
  to `portal_case_detail`; render `crm/service/portal_case_form.html`

### 2d. `urls.py`

- [ ] Add URL patterns (all under existing `app_name = "crm"`):
  - `service/sla/` → `slapolicy_list` name=`slapolicy_list`
  - `service/sla/new/` → `slapolicy_create` name=`slapolicy_create`
  - `service/sla/<int:pk>/` → `slapolicy_detail` name=`slapolicy_detail`
  - `service/sla/<int:pk>/edit/` → `slapolicy_edit` name=`slapolicy_edit`
  - `service/sla/<int:pk>/delete/` → `slapolicy_delete` name=`slapolicy_delete`
  - `service/cases/` → `case_list` name=`case_list` (replaces existing `cases/` if any)
  - `service/cases/new/` → `case_create` name=`case_create`
  - `service/cases/<int:pk>/` → `case_detail` name=`case_detail`
  - `service/cases/<int:pk>/edit/` → `case_edit` name=`case_edit`
  - `service/cases/<int:pk>/delete/` → `case_delete` name=`case_delete`
  - `service/cases/<int:pk>/comment/` → `case_comment_add` name=`case_comment_add`
  - `service/kb-categories/` → `kbcategory_list` name=`kbcategory_list`
  - `service/kb-categories/new/` → `kbcategory_create` name=`kbcategory_create`
  - `service/kb-categories/<int:pk>/` → `kbcategory_detail` name=`kbcategory_detail`
  - `service/kb-categories/<int:pk>/edit/` → `kbcategory_edit` name=`kbcategory_edit`
  - `service/kb-categories/<int:pk>/delete/` → `kbcategory_delete` name=`kbcategory_delete`
  - `service/articles/` → `knowledgearticle_list` name=`knowledgearticle_list`
  - `service/articles/new/` → `knowledgearticle_create` name=`knowledgearticle_create`
  - `service/articles/<int:pk>/` → `knowledgearticle_detail` name=`knowledgearticle_detail`
  - `service/articles/<int:pk>/edit/` → `knowledgearticle_edit` name=`knowledgearticle_edit`
  - `service/articles/<int:pk>/delete/` → `knowledgearticle_delete` name=`knowledgearticle_delete`
  - `service/portal-access/` → `customerportalaccess_list` name=`customerportalaccess_list`
  - `service/portal-access/new/` → `customerportalaccess_create` name=`customerportalaccess_create`
  - `service/portal-access/<int:pk>/` → `customerportalaccess_detail` name=`customerportalaccess_detail`
  - `service/portal-access/<int:pk>/edit/` → `customerportalaccess_edit` name=`customerportalaccess_edit`
  - `service/portal-access/<int:pk>/delete/` → `customerportalaccess_delete` name=`customerportalaccess_delete`
  - `cases/track/<str:token>/` → `case_public` name=`case_public`
  - `kb/public/<str:token>/` → `kb_public` name=`kb_public`
  - `kb/public/<str:token>/vote/` → `kb_helpful` name=`kb_helpful`
  - `portal/cases/` → `portal_case_list` name=`portal_case_list`
  - `portal/cases/<int:pk>/` → `portal_case_detail` name=`portal_case_detail`
  - `portal/cases/new/` → `portal_case_create` name=`portal_case_create`
  - NOTE: check for and remove/replace any existing `cases/` and `articles/` patterns from the
    original §1.4 stub to avoid URL name conflicts

### 2e. `admin.py`

- [ ] Register `SlaPolicy` with `list_display=[number, name, is_default, is_active]`
- [ ] Register `CaseComment` with `list_display=[case, author_name, is_public, created_at]`,
  `list_filter=[is_public, tenant]`, `raw_id_fields=[case, author]`
- [ ] Register `KbCategory` with `list_display=[number, name, parent, order, is_active]`
- [ ] Update existing `Case` admin — add `sla_policy, first_response_due, first_responded_at,
  resolution_due, closed_at, satisfaction_rating, public_token` to `list_display` or `readonly_fields`
- [ ] Update existing `KnowledgeArticle` admin — add `kb_category, helpful_count,
  not_helpful_count, public_token` to `list_display` or `readonly_fields`
- [ ] Register `CustomerPortalAccess` with `list_display=[number, customer_party, portal_user,
  can_submit_cases, is_active]`

### 2f. Migration

- [ ] `python manage.py makemigrations crm --name helpdesk` → confirms 0012 is next
- [ ] Verify migration covers: new SlaPolicy table, new CaseComment table, new KbCategory table,
  new CustomerPortalAccess table, new fields on Case, new fields on KnowledgeArticle
- [ ] `python manage.py migrate` — applies 0012 cleanly

### 2g. Seeder — `_seed_service(tenant)` in `seed_crm` management command

- [ ] Add `_seed_service(tenant)` function to `apps/crm/management/commands/seed_crm.py`:
  - Guard: `if SlaPolicy.objects.filter(tenant=tenant).exists(): print("service data exists"); return`
  - Create 2 SlaPolicy records: `"Standard SLA"` (response 48/24/8/1, resolution 120/72/24/8,
    `is_default=True`) and `"VIP SLA"` (response 24/8/4/1, resolution 72/48/16/4)
  - Create 2 KbCategory records: `"Getting Started"` (order=1) and `"Troubleshooting"` (order=2,
    parent = Getting Started to demo hierarchy)
  - Reuse the first existing Case from the tenant (created by `_seed_directory`); add 2 CaseComments
    — one internal note (`is_public=False`), one public reply (`is_public=True`) — and update
    `case.first_responded_at` on the first public comment
  - Set `sla_policy` on that Case; compute `first_response_due` / `resolution_due` via `save()`
  - Reuse the first existing KnowledgeArticle from the tenant (created by earlier stub); set
    `kb_category` to "Getting Started"
  - Create 1 KbCategory child: `"Account Setup"` (parent = Getting Started, order=1)
  - NOTE: `CustomerPortalAccess` is intentionally skipped in seeder (requires a real portal_user User
    account; document this in seeder comments)
  - Print summary: counts of created objects; reminder: log in as tenant admin to see data
- [ ] Call `_seed_service(tenant)` unconditionally from `handle()` (same pattern as `_seed_sfa`)

---

## 3. Wire-up

- [ ] `apps/core/navigation.py` — rewrite `LIVE_LINKS["1.4"]` to:
  ```python
  "1.4": {
      "Case / Ticket Management":        "crm:case_list",                 # bullet (verbatim)
      "Solutions & Knowledge Base":      "crm:knowledgearticle_list",     # bullet (verbatim)
      "Customer Self-Service Portal":    "crm:customerportalaccess_list", # bullet (verbatim)
      "SLA Policies":                    "crm:slapolicy_list",            # extra
      "KB Categories":                   "crm:kbcategory_list",           # extra
      "Portal Access":                   "crm:customerportalaccess_list", # extra (duplicate ok — distinct label)
  },
  ```
  NOTE: existing `"Case \ Ticket Management"` key uses a backslash — replace with the correct
  forward-slash form `"Case / Ticket Management"` to match NavERP.md verbatim bullet text.
- [ ] `config/settings.py` — `apps.crm` is already in `INSTALLED_APPS`; no change needed
- [ ] `config/urls.py` — `crm/` include already in place; no change needed; confirm existing stub
  case/article URL patterns are replaced by the new ones in §2d

---

## 4. Templates — `templates/crm/service/`

All templates extend `base.html`. Public pages (`case_public.html`, `kb_public.html`) extend
`base_auth.html` (unauthenticated shell). Portal pages (`portal_case_*.html`) extend `base.html`
(user is logged in as portal_user).

### SlaPolicy
- [ ] `crm/service/slapolicy/list.html` — filter bar: search input + is_active dropdown; table cols:
  Number, Name, Default badge, Response (Low/Med/High/Crit in hours), Resolution (Low/Med/High/Crit),
  Active badge, Actions (view/edit/delete); empty state
- [ ] `crm/service/slapolicy/detail.html` — full policy card with 4-column target matrix (priority ×
  response/resolution); created_at; Actions sidebar (Edit / Delete / Back)
- [ ] `crm/service/slapolicy/form.html` — form for name/description/is_active/is_default + 8 integer
  fields in a 2-column grid (Response Targets / Resolution Targets); labels show "(hours)"

### Case (recreate under service/)
- [ ] `crm/service/case/list.html` — filter bar: search + status + priority + origin + sla_policy
  dropdowns; table cols: Number, Subject, Account, Priority badge, Status badge, SLA (breach icon if
  `is_resolution_overdue`), Owner, Created; Actions (view/edit/delete); pagination; empty state
- [ ] `crm/service/case/detail.html` — full case info card; SLA panel (first_response_due +
  first_responded_at with green/red indicator; resolution_due with green/orange/red badge);
  satisfaction panel (show rating stars + comment if `satisfaction_rating` set); **comment thread
  panel** (chronological; internal notes have yellow/grey background, public replies have white/blue;
  agent sees all; inline `CaseCommentForm` at bottom with is_public toggle); Actions sidebar
  (Edit / Delete / Back / Public Link copy button if `public_token`)
- [ ] `crm/service/case/form.html` — `CaseForm`; include sla_policy dropdown; exclude all system fields;
  note "SLA due dates are computed automatically"

### KbCategory
- [ ] `crm/service/kbcategory/list.html` — filter bar: search + is_active + parent dropdown; table
  cols: Number, Name, Parent, Order, Article count, Active badge, Actions; empty state
- [ ] `crm/service/kbcategory/detail.html` — category info + parent breadcrumb + child_categories
  list + linked articles count; Actions sidebar
- [ ] `crm/service/kbcategory/form.html` — fields: name, description, slug, parent (exclude self on
  edit), order, is_active; help text "Leave slug blank to auto-generate"

### KnowledgeArticle (recreate under service/)
- [ ] `crm/service/knowledgearticle/list.html` — filter bar: search + status + visibility +
  kb_category dropdowns; table cols: Number, Title, KB Category, Visibility badge, Status badge,
  Views, Helpful (count), Actions; empty state
- [ ] `crm/service/knowledgearticle/detail.html` — article body; KB Category breadcrumb;
  helpful_count / not_helpful_count display; public link if `public_token` set; Actions sidebar
  (Edit / Delete / Back / Public Link)
- [ ] `crm/service/knowledgearticle/form.html` — `KnowledgeArticleForm`; kb_category dropdown;
  exclude helpful counts, public_token, views_count; note "Public token generated automatically"

### CustomerPortalAccess
- [ ] `crm/service/customerportalaccess/list.html` — filter bar: search + is_active + can_submit
  dropdowns; table cols: Number, Customer Party, Portal User, Can Submit, Active, Accepted At,
  Actions; empty state
- [ ] `crm/service/customerportalaccess/detail.html` — full grant info; portal_user display;
  can_submit_cases badge; accepted_at; linked cases count for customer_party; Actions sidebar
- [ ] `crm/service/customerportalaccess/form.html` — `CustomerPortalAccessForm`; customer_party +
  portal_user + can_submit_cases + accepted_at + is_active

### Standalone public pages
- [ ] `crm/service/case_public.html` — extends `base_auth.html`; shows case subject, status badge,
  priority badge, created_at, last public agent reply body; CSAT form if case resolved/closed and
  `satisfaction_rating is None`; all user-generated text escaped (no `|safe`); max input lengths enforced
- [ ] `crm/service/kb_public.html` — extends `base_auth.html`; shows article title, body (escaped),
  KB Category if set; helpful/not-helpful vote form (POST to `kb_helpful`); shows voted state
  (`?voted=1`); returns 404 for non-published or non-external articles

### Portal pages
- [ ] `crm/service/portal_case_list.html` — extends `base.html`; customer's own cases filtered by
  their party; status filter dropdown; table: Subject, Priority, Status, Last Updated, Actions (view);
  "Submit New Case" CTA if `access.can_submit_cases`; empty state
- [ ] `crm/service/portal_case_detail.html` — extends `base.html`; case info (subject/status/priority);
  only `is_public=True` comments shown (no internal notes); `PublicCommentForm` at bottom for reply;
  CSAT form if resolved/closed and not yet rated; all content escaped
- [ ] `crm/service/portal_case_form.html` — extends `base.html`; subject + description + priority
  fields only; `origin` and `account` are forced server-side (not in form); submit button

---

## 5. Verify

- [ ] `python manage.py makemigrations --check` — no unapplied model changes
- [ ] `python manage.py migrate` — applies 0012 cleanly with no errors
- [ ] `python manage.py seed_crm` ×2 — both runs succeed; second run prints "service data exists,
  skipping" (idempotent guard); `manage.py check` clean after both runs
- [ ] `python manage.py check` — no system check errors
- [ ] `temp/smoke_helpdesk.py` sweep — verify:
  - All `crm:slapolicy_*` URLs return 200 (list/create/detail/edit) or 302 (delete POST)
  - All `crm:case_*` URLs return 200/302; `case_comment_add` POST-only returns 302
  - All `crm:kbcategory_*` URLs return 200/302
  - All `crm:knowledgearticle_*` URLs return 200/302
  - All `crm:customerportalaccess_*` URLs return 200/302
  - `case_public` GET with valid token → 200; with invalid token → 404
  - `case_public` POST (CSAT) on resolved case → 302 + satisfaction_rating set
  - `kb_public` with valid token + published + external → 200; draft → 404; internal → 404
  - `kb_helpful` POST → 302 + helpful_count incremented (verify via DB query)
  - `portal_case_list` with no CustomerPortalAccess → 404; with active access → 200
  - `portal_case_create` POST with `can_submit_cases=False` → 404 or redirect
  - `portal_case_detail` with case belonging to different party → 404 (IDOR check)
  - Cross-tenant IDOR: Case.pk from tenant A accessed by tenant B session → 404
  - No `{#` or `{% comment` template-comment leaks in rendered output
  - Sidebar shows "Case / Ticket Management", "Solutions & Knowledge Base", "Customer Self-Service
    Portal" as Live (green) links

---

## 6. Close-out

- [ ] Run `code-reviewer` agent → apply findings → commit `apps/crm/` changes
- [ ] Run `explorer` agent → apply findings → commit
- [ ] Run `frontend-reviewer` agent → apply findings → commit templates
- [ ] Run `performance-reviewer` agent → apply findings (check N+1 on comment thread, views_count F()
  query, portal case list) → commit
- [ ] Run `qa-smoke-tester` agent → apply findings → commit
- [ ] Run `security-reviewer` agent → verify public endpoint token security, CSRF on all POSTs,
  portal IDOR guards, no |safe on user content, input length caps → apply findings → commit
- [ ] Run `test-writer` agent → add `tests/test_helpdesk.py` → commit
- [ ] Update `.claude/skills/crm/SKILL.md` — add §1.4 models (SlaPolicy, CaseComment, KbCategory,
  CustomerPortalAccess + Case/KnowledgeArticle enhancements), new URL names, new templates under
  `service/`, `_seed_service` seeder, LIVE_LINKS["1.4"] rewrite → commit
- [ ] Update module README if one exists → commit

---

## 7. Later passes / deferred

- **Email-to-ticket ingestion (IMAP/SMTP)** — `Case.origin=email` choice already in place; live
  mailbox polling via Celery beat + IMAP is an external integration; defer to integration pass
- **Business hours / holiday calendar for SLA** — `SlaPolicy` ships with calendar-hours only;
  `hours_mode` field + `BusinessHours`/`HolidaySchedule` table deferred to extension pass
- **SLA escalation notifications** — breach properties (`is_response_overdue`, `is_resolution_overdue`)
  ship now; email/in-app dispatch via existing `WorkflowRule` (1.10) wiring deferred to
  notification/workflow pass
- **CSAT survey email delivery** — CSAT fields + public token submission ship now; auto-send
  post-close email requires SMTP notification integration; deferred to notification pass
- **Merge duplicate cases** — self-FK `merged_into` on Case; deferred; low priority
- **Macros / canned responses** — new `CannedResponse` table; wire into portal reply form; deferred
- **Round-robin / skill-based auto-assignment** — assignment-engine table; deferred to workflow pass
- **Article version history / rollback** — `KbArticleVersion` table; deferred
- **Multi-language KB** — localization is a Module 0 cross-cutting concern; deferred
- **Community forums** — separate sub-product; deferred
- **Article-to-case keyword suggestion** — text-match service to surface KB on case creation; deferred
  to search/AI pass
- **AI answer-bot / ticket deflection** — requires LLM integration; deferred
- **Omnichannel (social / SMS / WhatsApp / telephony)** — external channel integrations; deferred
- **Live chat / chatbot on portal** — requires WebSocket; deferred
- **`category_legacy` CharField cleanup** — the old `KnowledgeArticle.category CharField` field is
  kept in migration 0012 for safety; drop it in a later migration once all data is migrated to
  `kb_category` FK

---

## 8. Review notes — CRM §1.4 Customer Service & Support (recreated in detail) ✅

**Delivered (migration 0012):** new `SlaPolicy` (per-priority hour targets) + enhanced `Case` (SLA dues/breach
props + CSAT + public_token, SLA-driven save) + `CaseComment` conversation thread + `KbCategory` + enhanced
`KnowledgeArticle` (category FK + helpful votes + public_token) + `CustomerPortalAccess`. Plus a public
case-status tracking page + public KB article page (+ helpful vote), and a **login-gated customer self-service
portal** (own-cases-only list/detail/create). `LIVE_LINKS["1.4"]` lights up all 3 NavERP bullets + 3 extras. 20
templates under `templates/crm/service/`. `_seed_service` seeder (unconditional, SlaPolicy-guarded). One file per
commit to `main`.

**Verification:** `manage.py check` clean; migration applies (public_token null=True+unique so existing rows stay
distinct); `seed_crm` idempotent (×2); `temp/smoke_service.py` all green; **1178 CRM pytest tests pass** (198 new
in `test_helpdesk.py` + a de-flaked SFA timestamp test).

**Review agents (CLAUDE.md sequence), findings applied:**
- **code-reviewer** — (Critical) reject portal access with customer_party=None (no Q(account=None) leak);
  (Critical) atomic case_comment_add first-response claim (no TOCTOU); SLA two-guard due computation; CSAT
  submitted-once; case_public select_related; portal reply success message.
- **explorer** — confirmed full URL/context/field consistency; no code changes (public pages on base_auth match the
  sign/survey/landing precedent).
- **frontend-reviewer** — public case page: plain bordered divs (no card-in-auth-card); `<label for>` on the
  comment/CSAT/reply forms; `--radius-sm` var.
- **performance-reviewer** — Case.save skips the sla_policy lazy-load when dues are set; select_related(author) on
  portal/public comments + select_related(kb_category) on KB detail; defer(description/…) on case/sla/kbcategory
  lists; .only(...) on kbcategory children.
- **qa-smoke-tester** — 62/62 checks pass, no changes.
- **security-reviewer** (Medium×3) — atomic CSAT guard; `@tenant_admin_required` on SlaPolicy +
  CustomerPortalAccess create/edit/delete (tenant-wide config / portal-login IAM); explicit portal-reply reject +
  public-endpoint rate-limit WARNING comments.
- **test-writer** — 198 tests; surfaced + I de-flaked the pre-existing `stage_changed_at` timestamp test.

**Deferred (noted):** real email-to-ticket/telephony/omnichannel, AI answer-bot, macros/canned responses,
round-robin assignment, business-hours SLA calendar, SLA-breach email escalation, CSAT email delivery, KB article
versioning/multi-language, public-endpoint rate-limiting (WARNING-commented, needs django-ratelimit/WAF).

---
# CRM Sub-module 1.5 — Activity & Communication Management (crm) — plan from research-crm-1.5.md  (2026-06-27)

**Extending `apps/crm`** — NOT a new app. No `apps.py`/`settings.py`/`config/urls.py` churn.
Scope: enhance `CrmTask` (3 new fields + spawn-next-on-complete logic) + add 3 new models
(`CalendarEvent`, `EventAttendee`, `CommunicationLog`). One incremental migration (next after 0012).
Extend `seed_crm`. Rewrite `LIVE_LINKS["1.5"]` from 1 bullet to 3. All templates under
`templates/crm/activities/` (existing task templates stay, new entity folders added alongside).

Authoritative scope from `bubbly-squishing-adleman.md` — do NOT expand beyond these 4 models this pass.

---

## 0. Template folder structure

Sub-module folder is `templates/crm/activities/` (already exists for `task/`). Add new entity folders:

- [ ] `templates/crm/activities/calendarevent/{list,detail,form}.html` — CalendarEvent CRUD
- [ ] `templates/crm/activities/eventattendee/` — no standalone pages; attendees render inline on event detail
- [ ] `templates/crm/activities/communicationlog/{list,detail,form}.html` — CommunicationLog CRUD
- [ ] `templates/crm/activities/event_invite.html` — public RSVP page (standalone sub-module root, not an entity CRUD page; per CLAUDE.md rule 6)
- [ ] NOTE: existing `templates/crm/activities/task/{list,detail,form}.html` gain new recurrence fields — no folder rename needed

---

## 1. Models (add to / enhance `apps/crm/models.py`)

### 1a. `CrmTask` [ENHANCE — existing `TASK-` numbered model, line ~1144]

Drivers: Salesforce recurring-task-on-complete, Zoho daily/weekly/monthly patterns, SuiteCRM series model.

- [ ] Add 3 fields to `CrmTask` after the existing `completed_at` field:
  - `recurrence` — `CharField(max_length=10, choices=[("none","None"),("daily","Daily"),("weekly","Weekly"),("monthly","Monthly")], default="none")` — recurrence frequency (Zoho/Salesforce daily/weekly/monthly)
  - `recurrence_interval` — `PositiveSmallIntegerField(default=1)` — "every N days/weeks/months" (Zoho custom intervals); must be ≥ 1
  - `recurrence_until` — `DateField(null=True, blank=True)` — optional end date for the series; no occurrences beyond this date (Zoho end-on-date)
  - `recurrence_parent` — `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="recurrence_children")` — system-set; links a spawned occurrence to the origin task (Salesforce series model); never shown in forms
- [ ] Update `CrmTask.save()` to add spawn-next-on-complete logic **after** the existing `completed_at` stamp block:
  - Condition: `self.status == "done"` AND `self.recurrence != "none"` AND `self.due_date is not None` AND `self.pk is not None` (already saved, not a new object) AND the current object has just transitioned to done (guard: check that `completed_at` was None before, i.e. was not already done — use `_state.adding=False` + a pre-save old-status check via `type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()`)
  - Guard against double-spawn: only spawn if `recurrence_parent_id is None` OR `self` is the series origin (avoids spawned children spawning further on re-save)
  - Compute `next_due`: `due_date + timedelta(days=interval)` for daily, `due_date + timedelta(weeks=interval)` for weekly, `due_date + relativedelta(months=interval)` for monthly (use `dateutil.relativedelta` — already available in the Django environment)
  - Skip spawn if `recurrence_until is not None` and `next_due > recurrence_until`
  - Spawn: `CrmTask.objects.create(tenant=self.tenant, subject=self.subject, type=self.type, priority=self.priority, status="open", due_date=next_due, owner=self.owner, party=self.party, related_opportunity=self.related_opportunity, related_case=self.related_case, recurrence=self.recurrence, recurrence_interval=self.recurrence_interval, recurrence_until=self.recurrence_until, recurrence_parent=self.recurrence_parent or self)` — note: calls `TenantNumbered.save()` via `create()`, number is assigned there; no recursion risk because the spawned task starts `status="open"`
  - IMPORTANT: the spawn must happen **after** `super().save()` returns (not before), to avoid a partially-saved parent
  - Add `related_case` FK (see below) to the copy fields in the spawn
- [ ] Add `related_case` FK to `CrmTask` (also needed for spawn copy above):
  - `related_case` — `ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")` — task linkable to a support case (Salesforce/HubSpot pattern)
- [ ] Update `CrmTask.Meta` indexes: the existing `crm_task_tenant_status_idx` and `crm_task_tnt_due_created_idx` are unchanged; no new index needed for recurrence (queried by parent_id only in spawn, small cardinality)
- [ ] `CrmTask.__str__` unchanged
- [ ] Reuses: existing spine (`core.Party`, `crm.Opportunity`); adds `crm.Case` FK + recurrence fields. No new table.

### 1b. `CalendarEvent` [NEW — `TenantNumbered`, `NUMBER_PREFIX = "EVT"`]

Drivers: Salesforce Event object, HubSpot Meetings, Zoho CRM Events, Pipedrive Activity (meeting type), Dynamics 365 Appointment + Calendly ICS/invite-link pattern.

- [ ] Add `CalendarEvent(TenantNumbered)` after `CrmTask` in `models.py` with `NUMBER_PREFIX = "EVT"`:
  - `number` — inherited from `TenantNumbered`; `unique_together(tenant, number)` in Meta
  - `title` — `CharField(max_length=255)`
  - `event_type` — `CharField(max_length=20, choices=[("meeting","Meeting"),("call","Call"),("demo","Demo"),("deadline","Deadline"),("reminder","Reminder"),("other","Other")], default="meeting")` — event categorization (research: Salesforce event types, Pipedrive activity types, HubSpot meeting types)
  - `start` — `DateTimeField()` — event start; required
  - `end` — `DateTimeField(null=True, blank=True)` — event end (null = open-ended / all-day-like)
  - `all_day` — `BooleanField(default=False)` — when True, `start`/`end` are date-only semantics (HubSpot all-day meeting)
  - `location` — `CharField(max_length=255, blank=True)` — physical location (Dynamics 365, HubSpot)
  - `video_url` — `URLField(blank=True)` — Zoom/Teams/Meet link (HubSpot Meetings/Pipedrive Zoom/Calendly; store now, auto-generate later)
  - `status` — `CharField(max_length=20, choices=[("scheduled","Scheduled"),("confirmed","Confirmed"),("cancelled","Cancelled"),("completed","Completed")], default="scheduled")` — lifecycle (HubSpot completion/cancellation, Dynamics 365 Completed/Cancelled)
  - `sync_source` — `CharField(max_length=10, choices=[("manual","Manual"),("google","Google Calendar"),("outlook","Outlook"),("ical","iCal")], default="manual")` — provenance tag (Salesforce Einstein Activity Capture, Zoho/Pipedrive two-way sync; OAuth push is deferred)
  - `reminder_minutes` — `PositiveSmallIntegerField(default=15, null=True, blank=True)` — lead-time reminder in minutes (Zoho/HubSpot/Salesforce; email send is integration/later)
  - `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")` — organizer/rep
  - `party` — `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")` — primary contact/account (spine reuse)
  - `related_opportunity` — `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")` — linked deal
  - `related_case` — `ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")` — linked support case
  - `description` — `TextField(blank=True)`
  - `public_token` — `CharField(max_length=64, unique=True, blank=True)` — unguessable bearer token for the public invite/RSVP/ICS link; mirrors `Case.public_token` / `LandingPage.public_token` pattern; auto-assigned in `save()` via `secrets.token_urlsafe(32)` when blank; **excluded from all forms** (L20/L22)
  - `Meta.ordering = ["-start"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "status")` — `crm_calevent_tenant_status_idx`
    - `("tenant", "start")` — `crm_calevent_tenant_start_idx`
  - Properties:
    - `is_past` — `@property` returning `bool(self.start < timezone.now())` when start is set
    - `duration_display` — `@property` returning `"HH:MM"` string when both `start` and `end` are set, else `""`; formula: `(end - start)` total seconds → `"%d:%02d" % divmod(total_seconds // 60, 60)` (hours:minutes)
  - `save()`: assign `public_token` if blank (`self.public_token = secrets.token_urlsafe(32)`) before calling `super().save()` — same pattern as `Case.save()` and `LandingPage.save()`
  - `__str__`: `f"{self.number} · {self.title}"`
  - Reuses: `core.Party`, `crm.Opportunity`, `crm.Case`, `settings.AUTH_USER_MODEL`. Adds event lifecycle + ICS/invite token.

### 1c. `EventAttendee` [NEW — plain model, child of `CalendarEvent`]

Drivers: Dynamics 365 appointment attendee sync, Google Calendar accepted/declined/tentative/needsAction, Calendly invitee RSVP, iCalendar RFC-5545 PARTSTAT values.

- [ ] Add `EventAttendee(models.Model)` immediately after `CalendarEvent` in `models.py` — NOT `TenantNumbered` (child rows, no auto-number needed; mirrors `CaseComment` pattern):
  - `tenant` — `ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)` — required for tenant-scoped queries; set in view/seeder to `event.tenant`
  - `event` — `ForeignKey(CalendarEvent, on_delete=models.CASCADE, related_name="attendees")`
  - `party` — `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="event_attendees")` — CRM contact/account (spine reuse); nullable so external guests (no Party record) can still be tracked
  - `name` — `CharField(max_length=255)` — display-name snapshot; survives party deletion (Calendly invitee name)
  - `email` — `EmailField(blank=True)` — used for ICS delivery and dedup; blank allowed for party-only attendees
  - `rsvp_status` — `CharField(max_length=20, choices=[("no_response","No Response"),("accepted","Accepted"),("declined","Declined"),("tentative","Tentative")], default="no_response")` — iCalendar RFC-5545 PARTSTAT states (Google Calendar needsAction/accepted/declined/tentative, Dynamics 365, Calendly)
  - `is_organizer` — `BooleanField(default=False)` — marks the meeting organizer among attendees; typically one per event
  - `responded_at` — `DateTimeField(null=True, blank=True)` — system-set when `rsvp_status` changes from `no_response`; **excluded from all forms** (L20/L22)
  - `created_at` — `DateTimeField(auto_now_add=True)`
  - `Meta.ordering = ["-is_organizer", "name"]`
  - `unique_together = ("event", "email")` — dedup: one row per (event, email); blank email is NOT unique-constrained (multiple party-only attendees without emails OK — Django unique_together with blank allows multiple blank rows)
  - NO standalone list page or URL; managed inline on CalendarEvent detail only
  - `__str__`: `f"{self.name} ({self.get_rsvp_status_display()})"`
  - Reuses: `core.Party`, `crm.CalendarEvent`. Plain child model — no numbered prefix.

### 1d. `CommunicationLog` [NEW — `TenantNumbered`, `NUMBER_PREFIX = "COM"`]

Drivers: HubSpot unified activity timeline (call/email/SMS/note/meeting), Freshsales real-time feed, Salesloft multi-channel cadence, Outreach disposition logging, Pipedrive Smart BCC email dropbox.

- [ ] Add `CommunicationLog(TenantNumbered)` after `EventAttendee` in `models.py` with `NUMBER_PREFIX = "COM"`:
  - `number` — inherited from `TenantNumbered`; `unique_together(tenant, number)` in Meta
  - `channel` — `CharField(max_length=10, choices=[("call","Call"),("email","Email"),("sms","SMS"),("note","Note"),("meeting","Meeting")], default="call")` — interaction channel (HubSpot unified timeline: calls/emails/meetings/notes/SMS)
  - `direction` — `CharField(max_length=10, choices=[("inbound","Inbound"),("outbound","Outbound")], blank=True)` — who initiated (HubSpot inbound/outgoing, Salesloft direction property); blank for notes/meetings
  - `subject` — `CharField(max_length=255, blank=True)` — email subject or call topic
  - `body` — `TextField(blank=True)` — email body preview or note text; field name `body` (not `body_snippet`) per the approved plan
  - `party` — `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")` — contact/account (spine reuse; HubSpot auto-associates to contact + company)
  - `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")` — rep who made/received the interaction
  - `related_opportunity` — `ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")` — linked deal (HubSpot: 5 most recent open deals, Pipedrive Smart BCC auto-link)
  - `related_case` — `ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="communication_logs")` — linked support case (Salesforce/HubSpot service call-back log)
  - `occurred_at` — `DateTimeField(default=timezone.now)` — the actual interaction time (may differ from `created_at` for retrospective logging); the canonical sort key
  - `duration_seconds` — `PositiveIntegerField(null=True, blank=True)` — call duration in seconds (HubSpot/Salesloft/Freshsales VoIP field; null for non-call channels)
  - `outcome` — `CharField(max_length=20, choices=[("connected","Connected"),("voicemail","Voicemail"),("no_answer","No Answer"),("busy","Busy"),("wrong_number","Wrong Number")], blank=True)` — call-only disposition (Salesloft disposition, Outreach "No Answer" default, HubSpot customizable call outcome); blank for email/note/SMS/meeting
  - `logged_via` — `CharField(max_length=20, choices=[("manual","Manual"),("bcc_dropbox","BCC Dropbox"),("voip","VoIP Auto-log"),("sync","Calendar Sync")], default="manual")` — provenance (Pipedrive Smart BCC, HubSpot BCC vs connected-inbox, Freshsales auto-log; full mail/VoIP engine is integration/later)
  - `email_message_id` — `CharField(max_length=255, blank=True)` — email `Message-ID` header for dedup when same email arrives via BCC and sync; `db_index=True` (L11 guard: filter only when non-empty)
  - `Meta.ordering = ["-occurred_at"]`
  - `unique_together = ("tenant", "number")`
  - DB indexes:
    - `("tenant", "channel")` — `crm_commlog_tenant_channel_idx`
    - `("tenant", "occurred_at")` — `crm_commlog_tenant_occurred_idx`
  - Properties:
    - `duration_display` — `@property` returning `"%d:%02d" % divmod(self.duration_seconds // 60, 60)` when `duration_seconds` is not None, else `""`; format is `"mm:ss"` for sub-hour calls (standard VoIP display)
    - `is_call` — `@property` returning `self.channel == "call"`
  - `save()`: no extra logic needed beyond `TenantNumbered.save()` number assignment
  - `__str__`: `f"{self.number} · {self.get_channel_display()} ({self.occurred_at:%Y-%m-%d})"`
  - Reuses: `core.Party`, `crm.Opportunity`, `crm.Case`, `settings.AUTH_USER_MODEL`. Adds unified comms log.

---

## 2. Forms (add to / update `apps/crm/forms.py`)

Rule: exclude `tenant`, auto `number`, `public_token`, `completed_at`, `responded_at`, `recurrence_parent` — all system-set (L20/L22). Never expose `public_token` or `email_message_id` in editable forms.

- [ ] Update import list in `forms.py` to add `CalendarEvent`, `EventAttendee`, `CommunicationLog`
- [ ] Update `CrmTaskForm` — add `recurrence`, `recurrence_interval`, `recurrence_until`, `related_case` to `fields` list; keep `recurrence_parent` and `completed_at` **excluded** (system-set):
  ```python
  fields = ["subject", "type", "priority", "status", "due_date", "owner", "party",
            "related_opportunity", "related_case", "description",
            "recurrence", "recurrence_interval", "recurrence_until"]
  ```
- [ ] Add `CalendarEventForm(TenantModelForm)`:
  - `fields = ["title", "event_type", "start", "end", "all_day", "location", "video_url", "status", "sync_source", "reminder_minutes", "owner", "party", "related_opportunity", "related_case", "description"]`
  - `public_token` excluded (L20/L22 — system-set in `save()`)
  - `number` excluded (inherited, system-set)
- [ ] Add `EventAttendeeForm(TenantModelForm)`:
  - `fields = ["party", "name", "email", "rsvp_status", "is_organizer"]`
  - `responded_at` excluded (system-set when rsvp_status changes from no_response)
  - `event` and `tenant` excluded (set by view)
- [ ] Add `CommunicationLogForm(TenantModelForm)`:
  - `fields = ["channel", "direction", "subject", "body", "party", "owner", "related_opportunity", "related_case", "occurred_at", "duration_seconds", "outcome", "logged_via"]`
  - `email_message_id` excluded from staff form (populated by sync engine in later pass; staff enters manually only via future import)
  - `number` excluded (system-set)
- [ ] Add `PublicRsvpForm(forms.Form)` — plain Form (NOT TenantModelForm; no tenant binding needed, data written directly in view):
  - `name = forms.CharField(max_length=255)`
  - `email = forms.EmailField()`
  - `rsvp_status = forms.ChoiceField(choices=[("accepted","Accept"),("declined","Decline"),("tentative","Maybe")])`
  - NOTE: `rsvp_status` choices deliberately exclude `no_response` (the default); the form is an affirmative RSVP action

---

## 3. Views (add to `apps/crm/views.py`)

All staff views: `@login_required`. Public views: no decorator, token bearer. Tenant-scoped: all `filter(tenant=request.tenant)` — no exceptions.

### 3a. CalendarEvent CRUD (staff, `@login_required`)

- [ ] `calendarevent_list` — `crud_list(request, CalendarEvent.objects.filter(tenant=request.tenant).select_related("owner","party"), "crm/activities/calendarevent/list.html", search_fields=["title","number"], filters=[("status","status",False),("event_type","event_type",False)], extra_context={"status_choices":CalendarEvent.STATUS_CHOICES,"type_choices":CalendarEvent.TYPE_CHOICES})` — (L7: pin all filter-dropdown choices)
- [ ] `calendarevent_create` — `crud_create(request, form_class=CalendarEventForm, template="crm/activities/calendarevent/form.html", success_url="crm:calendarevent_list")`
- [ ] `calendarevent_detail(request, pk)` — `get_object_or_404(CalendarEvent..., pk=pk, tenant=request.tenant)`; render with `attendees = event.attendees.select_related("party").all()` and `attendee_form = EventAttendeeForm(tenant=request.tenant)` in context (L7 — always pass the add-attendee form)
- [ ] `calendarevent_edit(request, pk)` — `crud_edit(request, model=CalendarEvent, pk=pk, form_class=CalendarEventForm, template="crm/activities/calendarevent/form.html", success_url="crm:calendarevent_list")`
- [ ] `calendarevent_delete(request, pk)` — `@require_POST`; `crud_delete(request, model=CalendarEvent, pk=pk, success_url="crm:calendarevent_list")`

### 3b. EventAttendee inline actions (staff, `@login_required`)

- [ ] `event_attendee_add(request, event_pk)` — `@login_required @require_POST`; get_or_404 `CalendarEvent(pk=event_pk, tenant=request.tenant)`, bind `EventAttendeeForm(request.POST, tenant=request.tenant)`, if valid: `obj = form.save(commit=False); obj.tenant = event.tenant; obj.event = event; obj.save()`; set `responded_at` if `rsvp_status != "no_response"` on save in view; `redirect("crm:calendarevent_detail", pk=event_pk)` — PRG
- [ ] `event_attendee_delete(request, pk)` — `@login_required @require_POST`; `get_object_or_404(EventAttendee, pk=pk, tenant=request.tenant)`; `.delete()`; `redirect("crm:calendarevent_detail", pk=attendee.event_id)` — PRG
- [ ] IMPORTANT: `event_attendee_add` must use `update_or_create(event=event, email=email, defaults={...})` when the form has a non-blank email (handles the public RSVP upsert case and avoids `unique_together(event,email)` IntegrityError on re-RSVP from staff side)

### 3c. Public token views (no `@login_required`)

- [ ] `event_invite(request, token)` — no `@login_required`; `get_object_or_404(CalendarEvent, public_token=token)`; render `PublicRsvpForm()` for GET; on POST bind `PublicRsvpForm(request.POST)`, if valid: `update_or_create(EventAttendee, event=event, email=cd["email"], defaults={"name":cd["name"],"rsvp_status":cd["rsvp_status"],"tenant":event.tenant,"responded_at":timezone.now()})` (upsert-by-email, no IntegrityError); `redirect("crm:event_invite", token=token)` with success message; context: `{"event": event, "attendees": event.attendees.all(), "form": rsvp_form}` — (L7: pin event + attendees + form). **`# WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or WAF throttle in production`**
- [ ] `event_ics(request, token)` — no `@login_required`; `get_object_or_404(CalendarEvent, public_token=token)`; build a minimal iCalendar (RFC 5545) text/calendar response inline (no external ical library needed for a basic VCALENDAR with one VEVENT): `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//NavERP//EN\r\nBEGIN:VEVENT\r\nUID:{event.number}@naverp\r\nDTSTART:{start_ical}\r\nDTEND:{end_ical}\r\nSUMMARY:{event.title}\r\nLOCATION:{event.location}\r\nDESCRIPTION:{event.description}\r\nEND:VEVENT\r\nEND:VCALENDAR`; return `HttpResponse(ics_text, content_type="text/calendar; charset=utf-8")` with `Content-Disposition: attachment; filename="{event.number}.ics"`
- [ ] L32 reminder: `event_invite` and `event_ics` are token-gated public pages — they must NOT appear in `LIVE_LINKS["1.5"]` and must NOT be sidebar targets

### 3d. CommunicationLog CRUD (staff, `@login_required`)

- [ ] `communicationlog_list` — `crud_list(request, CommunicationLog.objects.filter(tenant=request.tenant).select_related("party","owner"), "crm/activities/communicationlog/list.html", search_fields=["subject","number","body"], filters=[("channel","channel",False),("direction","direction",False),("logged_via","logged_via",False)], extra_context={"channel_choices":CommunicationLog.CHANNEL_CHOICES,"direction_choices":CommunicationLog.DIRECTION_CHOICES,"logged_via_choices":CommunicationLog.LOGGED_VIA_CHOICES})` — (L7: pin all 3 filter-dropdown choice lists; define as class-level constants in model)
- [ ] `communicationlog_create` — `crud_create(request, form_class=CommunicationLogForm, template="crm/activities/communicationlog/form.html", success_url="crm:communicationlog_list")`
- [ ] `communicationlog_detail(request, pk)` — `get_object_or_404(CommunicationLog.objects.select_related("party","owner","related_opportunity","related_case"), pk=pk, tenant=request.tenant)`; render `"crm/activities/communicationlog/detail.html"`
- [ ] `communicationlog_edit(request, pk)` — `crud_edit(request, model=CommunicationLog, pk=pk, form_class=CommunicationLogForm, template="crm/activities/communicationlog/form.html", success_url="crm:communicationlog_list")`
- [ ] `communicationlog_delete(request, pk)` — `@require_POST`; `crud_delete(request, model=CommunicationLog, pk=pk, success_url="crm:communicationlog_list")`

### 3e. Task views — no new views needed
- [ ] Confirm existing `task_list`/`task_create`/`task_detail`/`task_edit`/`task_delete` views still work after model field additions — the `crud_*` helpers are data-driven and the form field list controls what the user edits; verify `CrmTaskForm` new fields render correctly in `task_edit` smoke test

---

## 4. URLs (append to `apps/crm/urls.py`)

- [ ] CalendarEvent CRUD routes (5):
  ```python
  path("calendar/", views.calendarevent_list, name="calendarevent_list"),
  path("calendar/add/", views.calendarevent_create, name="calendarevent_create"),
  path("calendar/<int:pk>/", views.calendarevent_detail, name="calendarevent_detail"),
  path("calendar/<int:pk>/edit/", views.calendarevent_edit, name="calendarevent_edit"),
  path("calendar/<int:pk>/delete/", views.calendarevent_delete, name="calendarevent_delete"),
  ```
- [ ] EventAttendee inline action routes (2):
  ```python
  path("calendar/<int:event_pk>/add-attendee/", views.event_attendee_add, name="event_attendee_add"),
  path("calendar/attendees/<int:pk>/delete/", views.event_attendee_delete, name="event_attendee_delete"),
  ```
- [ ] Public token routes (2, outside any `@login_required` group — place at the very end of urlpatterns):
  ```python
  path("event-invite/<str:token>/", views.event_invite, name="event_invite"),
  path("event-ics/<str:token>/", views.event_ics, name="event_ics"),
  ```
- [ ] CommunicationLog CRUD routes (5):
  ```python
  path("comms/", views.communicationlog_list, name="communicationlog_list"),
  path("comms/add/", views.communicationlog_create, name="communicationlog_create"),
  path("comms/<int:pk>/", views.communicationlog_detail, name="communicationlog_detail"),
  path("comms/<int:pk>/edit/", views.communicationlog_edit, name="communicationlog_edit"),
  path("comms/<int:pk>/delete/", views.communicationlog_delete, name="communicationlog_delete"),
  ```
- [ ] Verify `app_name = "crm"` is set (already is; no change)
- [ ] Full URL name inventory for 1.5: `crm:calendarevent_list`, `crm:calendarevent_create`, `crm:calendarevent_detail`, `crm:calendarevent_edit`, `crm:calendarevent_delete`, `crm:event_attendee_add`, `crm:event_attendee_delete`, `crm:event_invite`, `crm:event_ics`, `crm:communicationlog_list`, `crm:communicationlog_create`, `crm:communicationlog_detail`, `crm:communicationlog_edit`, `crm:communicationlog_delete`

---

## 5. Admin (`apps/crm/admin.py`)

- [ ] Register `CalendarEvent` with `list_display = ["number","title","event_type","status","start","owner"]` and `list_filter = ["status","event_type","sync_source"]`
- [ ] Register `EventAttendee` with `list_display = ["name","email","event","rsvp_status","is_organizer"]` and `list_filter = ["rsvp_status"]`
- [ ] Register `CommunicationLog` with `list_display = ["number","channel","direction","subject","party","occurred_at"]` and `list_filter = ["channel","direction","logged_via"]`
- [ ] `CrmTask` admin already registered; no structural change needed — new fields auto-appear in the default admin form unless `fields` is pinned

---

## 6. Templates (`templates/crm/activities/`)

Conventions from existing task templates: `{% extends "base.html" %}`, filter bar uses `request.GET.*` comparisons (string fields — no `|slugify`; L11/Filter-Implementation-Rules), Actions column has eye/pencil/bin buttons, pagination uses `page_obj.window`, empty-state has an "Add" CTA, badge CSS classes match existing `.badge-*` pattern.

### 6a. CalendarEvent templates

- [ ] `templates/crm/activities/calendarevent/list.html`:
  - Filter bar: status dropdown (iterate `status_choices`, `{% if request.GET.status == value %}selected{% endif %}`), event_type dropdown (iterate `type_choices`), text search input bound to `?q=`
  - Table columns: Number, Title, Event Type, Start, Status, Owner, Actions
  - Actions column: eye (detail), pencil (edit), bin (delete POST + `onclick="return confirm(...)"`+ `{% csrf_token %}`)
  - Badges: status values `scheduled/confirmed/cancelled/completed` — use `obj.get_status_display` with `{% else %}` fallback
  - Pagination: `page_obj.window` + prev/next links (L9 guard: `page_obj.has_previous`/`has_next`)
  - Empty state: "No events yet. Schedule your first meeting." with link to `crm:calendarevent_create`
- [ ] `templates/crm/activities/calendarevent/form.html`:
  - `is_edit` context var (L7) drives `<h1>` label ("Add Calendar Event" vs "Edit Calendar Event") and back-button URL
  - Fields: title, event_type, start, end, all_day, location, video_url, status, sync_source, reminder_minutes, owner, party, related_opportunity, related_case, description
  - `public_token` not rendered (system-set, L20/L22)
  - For datetime fields: use `<input type="datetime-local">` with Django widget
- [ ] `templates/crm/activities/calendarevent/detail.html`:
  - Event info: title, type, status, start/end, `event.duration_display`, all_day, location, video_url, sync_source, reminder_minutes, owner, party, opportunity, case, description
  - `event.is_past` drives a "Past Event" badge
  - Invite link: `{% url "crm:event_invite" token=event.public_token %}` — show as a copyable input (not a sidebar link; L32)
  - ICS download: `{% url "crm:event_ics" token=event.public_token %}` — "Add to Calendar" button
  - Attendees section (inline list): iterate `attendees`, show name/email/rsvp_status badge; "Add Attendee" form (`attendee_form` from context — L7) as a collapsed/inline form posting to `crm:event_attendee_add`; each attendee row has a delete POST button
  - Actions sidebar: Edit (→ `crm:calendarevent_edit`), Delete POST (→ `crm:calendarevent_delete`), Back to List

### 6b. CommunicationLog templates

- [ ] `templates/crm/activities/communicationlog/list.html`:
  - Filter bar: channel dropdown (`channel_choices`), direction dropdown (`direction_choices`), logged_via dropdown (`logged_via_choices`), text search `?q=`
  - Table columns: Number, Channel, Direction, Subject, Party, Owner, Occurred At, Duration, Actions
  - Badges: channel values `call/email/sms/note/meeting`; direction values `inbound/outbound`
  - Duration column: show `obj.duration_display` for calls, blank for others
  - Actions: eye/pencil/bin
  - Pagination + empty state
- [ ] `templates/crm/activities/communicationlog/form.html`:
  - Fields: channel, direction, subject, body, party, owner, related_opportunity, related_case, occurred_at, duration_seconds, outcome, logged_via
  - `email_message_id` not in form (L20/L22 — sync-only; system-populated in later pass)
  - Outcome and duration_seconds: note in help text "for calls only"
  - `is_edit` label + back-button
- [ ] `templates/crm/activities/communicationlog/detail.html`:
  - All fields displayed; `obj.duration_display` for calls; `obj.is_call` drives "Call Details" section visibility
  - Actions sidebar: Edit, Delete POST, Back to List

### 6c. Public invite page

- [ ] `templates/crm/activities/event_invite.html`:
  - Standalone: extends `base_auth.html` (same as `crm/service/case_public.html` — public page, no sidebar) OR `base.html` minimal (check what `case_public.html` extends and mirror it exactly)
  - Show event title, type, start/end, location, video_url, organizer name
  - Show current attendee list with RSVP badges
  - RSVP form: `PublicRsvpForm` fields (name, email, rsvp_status) with `{% csrf_token %}`, POST to same URL
  - "Add to Calendar" ICS link: `{% url "crm:event_ics" token=event.public_token %}`
  - Success message after RSVP (Django messages or inline flag in context)
  - NOTE: this page is NOT a sidebar entry (L32); it is linked from the CalendarEvent detail page

### 6d. CrmTask templates — update existing

- [ ] `templates/crm/activities/task/form.html` — add `recurrence`, `recurrence_interval`, `recurrence_until` fields; group as "Recurrence" fieldset (show/hide when recurrence != "none"); `related_case` FK dropdown
- [ ] `templates/crm/activities/task/list.html` — verify no changes needed to filter bar (status/priority/type already there); recurrence badge is optional in the list (only if space allows)
- [ ] `templates/crm/activities/task/detail.html` — add recurrence display fields (`recurrence`, `recurrence_interval`, `recurrence_until`); if `recurrence_parent` set, show "This is a recurring occurrence of [parent number]" link; if `recurrence_children.count() > 0`, show "Spawned occurrences" mini-list

---

## 7. Migration

- [ ] Run `python manage.py makemigrations crm` — should produce one migration (next after `0012_…`) adding:
  - `CrmTask`: 4 new fields (`recurrence`, `recurrence_interval`, `recurrence_until`, `recurrence_parent`, `related_case`) — note `recurrence_parent` is a self-FK on `CrmTask`
  - New table `crm_calendarevent` (CalendarEvent)
  - New table `crm_eventattendee` (EventAttendee)
  - New table `crm_communicationlog` (CommunicationLog)
- [ ] Run `python manage.py migrate` — migration must apply cleanly with no data loss (existing `CrmTask` rows get `recurrence="none"`, `recurrence_interval=1`, null dates, null FKs — all safe defaults)
- [ ] Verify `python manage.py check` reports no issues

---

## 8. Seed (`apps/crm/management/commands/seed_crm.py`)

Add a `_seed_activities(tenant, users, parties, opportunities)` helper function in `seed_crm.py`, called from `handle()` after `_seed_service` — **idempotent** (skip block if any `CalendarEvent.objects.filter(tenant=tenant).exists()`; separate skip guard for `CommunicationLog`; the CrmTask recurrence update is guarded by checking for an existing recurring task).

- [ ] Add idempotency guard: `if CalendarEvent.objects.filter(tenant=tenant).exists(): print("Activities already seeded."); return` at top of `_seed_activities`
- [ ] Create 1 recurring CrmTask from existing seeded tasks data:
  - Find any existing `CrmTask` for the tenant with `status="open"` (from prior seed); update it to set `recurrence="weekly", recurrence_interval=1, recurrence_until=(date.today() + timedelta(days=90))`
  - OR create a new one: `CrmTask.objects.get_or_create(tenant=tenant, subject="Weekly Check-In Call", defaults={...recurrence fields...})`
  - Do NOT call `.save()` on the task in a way that triggers spawn logic during seeding (set `status="open"` so the done→spawn path is not triggered)
- [ ] Create 1 spawned occurrence manually (simulate the spawn for demo data):
  - Use `CrmTask.objects.filter(tenant=tenant, subject="Weekly Check-In Call").first()` as parent
  - Create child: `CrmTask.objects.get_or_create(tenant=tenant, subject="Weekly Check-In Call", due_date=<next_week>, defaults={"recurrence":"weekly","recurrence_interval":1,"recurrence_parent":parent_task,...})`
- [ ] Create ~4 CalendarEvents with `get_or_create` keyed on `(tenant, title)` — check by number pattern is NOT needed here because CalendarEvent has no `unique_together(tenant, title)`, so use title as the uniqueness key for seeding:
  ```
  EVT-1: "Kickoff Meeting with Acme" — type=meeting, status=confirmed, start=now()+2days, owner=users[0], party=parties[0]
  EVT-2: "Product Demo for GlobalEx" — type=demo, status=scheduled, start=now()+7days, owner=users[0], party=parties[1]
  EVT-3: "Quarterly Business Review" — type=meeting, status=completed, start=now()-14days, owner=users[0]
  EVT-4: "Follow-Up Call — Acme" — type=call, status=scheduled, start=now()+3days, owner=users[0], party=parties[0]
  ```
  IMPORTANT: use `get_or_create(tenant=tenant, title=<title>, defaults={...})` — do NOT use bare `.create()` (idempotency rule)
- [ ] Create 2–3 EventAttendees per event using `update_or_create(event=evt, email=<email>, defaults={...})` (dedup on event+email per `unique_together`):
  - Attendee 1 per event: `is_organizer=True, name=owner.get_full_name(), email=owner.email, rsvp_status="accepted"`
  - Attendee 2 per event: `name=party.name, email="contact@example.com", rsvp_status="no_response"` (external guest)
  - Attendee 3 on EVT-1 only: a second contact from parties[1], `rsvp_status="tentative"`
- [ ] Create ~6 CommunicationLogs with `get_or_create` keyed on `(tenant, subject, occurred_at)` — use approximate timestamps to avoid collision:
  ```
  COM-1: channel=call, direction=outbound, subject="Cold Call — Acme Corp", outcome=connected, duration_seconds=243, party=parties[0], owner=users[0], occurred_at=now()-5days
  COM-2: channel=call, direction=outbound, subject="Follow-Up Call — GlobalEx", outcome=voicemail, duration_seconds=0, party=parties[1], owner=users[0], occurred_at=now()-3days
  COM-3: channel=email, direction=outbound, subject="Proposal Sent — Acme Corp", body="Please find attached...", party=parties[0], owner=users[0], logged_via=bcc_dropbox, occurred_at=now()-4days
  COM-4: channel=email, direction=inbound, subject="Re: Proposal — Acme Corp", body="Thanks, looks good...", party=parties[0], owner=users[0], logged_via=bcc_dropbox, occurred_at=now()-3days
  COM-5: channel=note, subject="Meeting Notes — Kickoff", body="Discussed Q3 roadmap...", party=parties[0], owner=users[0], occurred_at=now()-14days
  COM-6: channel=sms, direction=outbound, subject="Reminder: Demo Tomorrow", party=parties[1], owner=users[0], occurred_at=now()-6days
  ```
- [ ] Print summary: `"Activities seeded: {len(events)} events, {len(logs)} comms logs"`

---

## 9. Wire-up

- [ ] `apps/core/navigation.py` — rewrite `LIVE_LINKS["1.5"]` from the current 1-bullet mapping to 3-bullet mapping:
  ```python
  "1.5": {
      "Task Management": "crm:task_list",                      # bullet — to-dos w/ due dates & priorities, automated recurring tasks
      "Calendar Integration": "crm:calendarevent_list",        # bullet — meeting scheduling, invite links, two-way sync
      "Email & Call Integration": "crm:communicationlog_list", # bullet — email sync via BCC dropbox, automatic call logging
  },
  ```
  - Bullet labels must match **exact** NavERP.md `**Feature**` text (the parser matches on these)
  - L32 reminder: `event_invite`/`event_ics` are public token-gated pages — they are NOT sidebar targets; staff links to them from the CalendarEvent detail page only
- [ ] Verify no `config/settings.py` or `config/urls.py` changes needed (existing `apps.crm` + `crm/` include already wired)

---

## 10. Verify

- [ ] `python manage.py makemigrations crm` — no drift, one migration file generated
- [ ] `python manage.py migrate` — applies cleanly
- [ ] `python manage.py seed_crm` — runs without error; prints activities seed summary
- [ ] `python manage.py seed_crm` a **second time** — idempotent: prints "Activities already seeded." and exits without duplicate rows or IntegrityError
- [ ] `python manage.py check` — zero issues
- [ ] Smoke script `temp/smoke_activities.py` — write a throwaway script (`force_login(admin_acme)`):
  - GET `crm:calendarevent_list` → 200, contains a seeded event title
  - GET `crm:calendarevent_create` → 200, form renders
  - GET `crm:calendarevent_detail` (sampled pk) → 200, attendees section present
  - GET `crm:calendarevent_edit` (same pk) → 200, form pre-filled
  - POST `crm:calendarevent_delete` (same pk) → 302
  - GET `crm:communicationlog_list` → 200, contains a seeded COM number
  - GET `crm:communicationlog_create` → 200
  - GET `crm:communicationlog_detail` (sampled pk) → 200
  - GET `crm:communicationlog_edit` (sampled pk) → 200
  - GET `crm:event_invite` (a seeded event's public_token) → 200 (no login required)
  - GET `crm:event_ics` (same token) → 200, content-type `text/calendar`
  - No `{#` or `{% comment` leaks in any response body
  - Cross-tenant IDOR: `admin_globex` GET `crm:calendarevent_detail` with Acme pk → 404
  - Cross-tenant IDOR: `admin_globex` GET `crm:communicationlog_detail` with Acme pk → 404
- [ ] Human sidebar pass (L30/L32):
  - Log in as `admin_acme` (tenant admin, not the global `admin` superuser)
  - Sidebar sub-module "1.5 Activity & Communication Management" shows 3 bullets, all Live (not "Soon")
  - "Task Management" → `crm:task_list` → 200
  - "Calendar Integration" → `crm:calendarevent_list` → 200
  - "Email & Call Integration" → `crm:communicationlog_list` → 200
  - None of the 3 bullets points at the public invite page (L32: sidebar bullets → staff-reachable pages only)
- [ ] `pytest` — existing 1178 CRM tests pass; new tests from test-writer step will add to this count

---

## 11. Close-out

- [ ] `code-reviewer` agent — apply findings, one file per commit
- [ ] `explorer` agent — apply findings, one file per commit
- [ ] `frontend-reviewer` agent — apply findings, one file per commit
- [ ] `performance-reviewer` agent — apply findings (likely: `.select_related` on list querysets, `.defer("body"/"description")` on list pages, `(tenant, occurred_at)` index review); one file per commit
- [ ] `qa-smoke-tester` agent — apply findings, one file per commit
- [ ] `security-reviewer` agent — apply findings; expected areas: public RSVP POST (unauthenticated write — add `# WARNING` rate-limit note), `event_ics` response headers, `email_message_id` dedup guard; one file per commit
- [ ] `test-writer` agent — apply output; expected: `tests/test_activities.py` covering CalendarEvent/EventAttendee/CommunicationLog CRUD + recurrence spawn logic + public token views; one file per commit
- [ ] Update `.claude/skills/crm/SKILL.md` — add §1.5 models (CrmTask recurrence fields, CalendarEvent, EventAttendee, CommunicationLog), URL names, templates, seeder additions, LIVE_LINKS["1.5"] rewrite → commit

---

## 12. Later passes / deferred

- **OAuth calendar push (Google/Outlook two-way sync)** — `CalendarEvent.sync_source` and `external_uid` (not in this pass — add `external_uid CharField` in a later migration) store provenance; actual event push/pull via Google Calendar API or MS Graph API is an external OAuth integration deferred to a later pass
- **Live email send/receive engine (BCC dropbox)** — `logged_via=bcc_dropbox` and `email_message_id` fields are ready; the mail-receive webhook and SMTP handler are integration/later
- **Email open/click tracking pixels** — `opened_at`/`clicked_at` fields from the research are not in this pass's scope; add in a later migration when the email send engine ships
- **VoIP dialer integration (Twilio/Aircall)** — `duration_seconds`, `outcome`, `logged_via=voip` fields are modeled; real-time call webhook handler is deferred
- **Call recording URL** — `recording_url URLField` from the research is deferred (add to CommunicationLog in a later migration with the VoIP integration)
- **AI call transcription / sentiment** — `sentiment CharField` and `notes TextField` from the research are deferred to the VoIP/AI pass
- **Round-robin meeting scheduling** — CalendarEvent.booking_token foundation exists (as `public_token`); availability-slot picking and round-robin distribution is a later feature
- **Email sequence / cadence engine** — `CrmTask.recurrence` + `CommunicationLog` provide the data foundation; multi-step automated outreach sequences are a separate sub-module (1.10 already has WorkflowRule)
- **Business-hours calendar for SLA / recurring task due calculation** — Zoho business-day adjustment on recurring tasks is deferred alongside the SLA policy business-hours calendar already deferred in 1.4
- **Bulk recurring task creation across multiple records** — Zoho cross-record recurrence; single-record ships first in this pass
- **SMS gateway send** — `channel=sms` is modeled for logging; the send gateway (Twilio SMS) is integration/later

---

## 13. Review notes

**Delivered (2026-06-27).** 4 models — `CrmTask` (enhanced: recurrence none/daily/weekly/monthly + interval +
until + self-FK parent + spawn-next-on-complete, `related_case`), `CalendarEvent` [EVT] (+ public invite/RSVP
+ `.ics` export), `EventAttendee` (RSVP child), `CommunicationLog` [COM] (unified call/email log). Migrations
`0013` + `0014`. `LIVE_LINKS["1.5"]` now wires all 3 NavERP.md bullets live. Seeder `_seed_activities`
(idempotent). Verification: `manage.py check` clean, seed idempotent ×2, a `temp/` smoke script passes 21/21
(routes 200/302, public invite/ICS, IDOR 404, recurrence spawn + no double-spawn, delete), `apps/crm` suite
**1,315 pass** (1178 prior + 137 new in `apps/crm/tests/test_activities.py`).

**Review-agent sequence (all 7 run, one at a time, fixes committed one file per commit):**
- **code-reviewer** — wrapped `CrmTask.save()` parent-write + recurrence spawn in `transaction.atomic`; dropped
  a redundant self-`exclude` in the idempotency guard; ICS line-folding per RFC 5545 §3.1; seeder voicemail
  `duration_seconds=None` (not 0). Deferred (needs a new field+migration): monthly last-day drift → a
  `recurrence_anchor_day` (see §12).
- **explorer** — verified all `{% url %}`/context-var/filter/LIVE_LINKS wiring; **0 issues**.
- **frontend-reviewer** — invite-link label `for`/`id` (a11y); explicit `note` channel + `cancelled` status
  badge branches. Skipped (L28, faithful copies of app-wide patterns): `th-actions` (all 46 CRM `<th>` use
  `table-actions`), and restyling `event_invite.html` beyond its `case_public.html` sibling.
- **performance-reviewer** — `task_detail` `select_related(related_case, recurrence_parent)`; dropped unused
  `owner`/`party` joins from the comm-log/calendar list querysets. Kept `body` in comm-log search (app-wide
  TextField-search pattern — Expense/Timesheet/Survey/PO all do it, L28).
- **qa-smoke-tester** — independent sweep, **36/36 pass**, 0 leaks, 0 fixes.
- **security-reviewer** — public RSVP **first-response-wins** (no overwrite of a recorded answer via the shared
  token); `CalendarEvent.public_token` `editable=False`; `_esc` strips bare CR. XSS/CSRF/IDOR/tenant-isolation
  verified clean.
- **test-writer** — 137 tests (`test_activities.py`).

## 14. Deferred — add to §12
- **`recurrence_anchor_day`** on `CrmTask` — current monthly recurrence advances from the (clamped) child due
  date, so Jan 31 → Feb 28 → **Mar 28** (last-day drift). A stored anchor day (clamp from the original day each
  month) fixes it. Test `TestCrmTaskMonthlyClamp::test_monthly_drift_on_subsequent_spawn` locks in current
  behavior so the fix is a conscious change. Needs a field + migration.

---
# CRM Sub-module 1.6 — Analytics & Reporting (crm) — plan from research-crm-analytics-reporting.md  (2026-06-27)

**Extending `apps/crm`** — NOT a new app. `apps.py`, `__init__.py`, `settings.py`, `config/urls.py` are already
in place. Four new models are appended to `apps/crm/models.py`; a new pure-Python helper `apps/crm/analytics.py`
provides all aggregation logic (no new DB tables beyond the 4 models). The next migration is `0015_analytics`.
Template sub-module folder: `templates/crm/analytics/`.

**Existing CRM models that supply raw data (do NOT re-model — only query in analytics.py):**
`Lead` (status/source/rating/score), `Opportunity` (stage/amount/probability/forecast_category/close_date/
weighted_amount/stage_changed_at/lost_at/loss_reason/competitor), `SalesQuota` (target_amount/owner/territory),
`Case` (status/priority/type/origin/resolved_at/first_responded_at/closed_at/satisfaction_rating),
`CrmTask` (status/task_type/owner/completed_at), `Campaign` (budget/actual_cost/expected_revenue),
`CommunicationLog` (direction/channel/duration_seconds/owner), `CalendarEvent` (owner/start_at).

---

## 0. Context — what is being built

Sub-module 1.6 currently has `LIVE_LINKS["1.6"]` pointing both "Dashboards" and "Standard Reports" at
`crm:overview` (a stub). This pass delivers:
- Saved per-user/shared **dashboards** with individually configurable **widgets** that compute live
- Saved **standard reports** (4 types) with **point-in-time snapshots** for trending
- `apps/crm/analytics.py` — the single compute engine (17 metric resolvers + 4 report computers)
- Full CRUD on all 4 models; 1.6 sidebar bullets light up as Live

---

## 1. Models (append to `apps/crm/models.py`)

### 1a. `AnalyticsDashboard` [DASH-] — `TenantNumbered`, `NUMBER_PREFIX = "DASH"`

Drivers: Per-User Dashboard Container (Salesforce/HubSpot/Pipedrive/monday — table-stakes); Dashboard Sharing
(HubSpot/Insightly/Copper — common); Date Range / Period Filter on Dashboard (all leaders — table-stakes);
Role-Based / Audience Dashboards (Dynamics 365/Freshsales personas — common).

- [ ] Add module-level choice constants BEFORE `AnalyticsDashboard`:

  ```python
  DASHBOARD_LAYOUT_CHOICES = [
      ("one_col",   "Single Column"),
      ("two_col",   "Two Columns"),
      ("three_col", "Three Columns"),
  ]

  PERIOD_CHOICES = [
      ("last_7",   "Last 7 Days"),
      ("last_30",  "Last 30 Days"),
      ("last_90",  "Last 90 Days"),
      ("quarter",  "This Quarter"),
      ("year",     "This Year"),
      ("all",      "All Time"),
  ]
  ```

- [ ] Add `AnalyticsDashboard(TenantNumbered)` with `NUMBER_PREFIX = "DASH"`:
  - `name` — `CharField(max_length=120)` — human name, e.g. "Sales Command Center"
  - `description` — `TextField(blank=True)`
  - `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
    related_name="crm_dashboards")` — null = system/shared dashboard (driver: personal vs. team dashboards)
  - `is_shared` — `BooleanField(default=False)` — visible to all tenant users when True
    (driver: Dashboard Sharing — HubSpot/Insightly/Copper)
  - `is_default` — `BooleanField(default=False)` — one default per owner; loaded on first visit
    (driver: Per-User Dashboard Container — Salesforce/Pipedrive set-as-default)
  - `layout` — `CharField(max_length=12, choices=DASHBOARD_LAYOUT_CHOICES, default="two_col")`
    (driver: Drag-and-Drop Layout Builder — store grid column count; JS builder deferred)
  - `default_period` — `CharField(max_length=12, choices=PERIOD_CHOICES, default="last_30")`
    (driver: Date Range / Period Filter on Dashboard — all leaders)
  - `Meta.ordering = ["-is_default", "name"]`
  - `unique_together = ("tenant", "owner", "name")`
  - DB indexes: `("tenant", "owner", "is_default")` → `crm_adash_tenant_owner_default_idx`
  - `__str__`: `f"{self.number} · {self.name}"`
  - **Reuses**: `core.Tenant` (via TenantNumbered), `accounts.User`. Adds dashboard-domain fields only.

### 1b. `DashboardWidget` — tenant-scoped child (no number prefix)

Drivers: KPI Summary Card (table-stakes, all leaders); Bar/Column Chart (table-stakes, all 10); Line/Area Chart
(table-stakes, 6 leaders); Funnel Chart (table-stakes, Dynamics 365 ships it on every dashboard); Gauge (common,
Salesforce/Zoho/Insightly); Leaderboard/Table (common, Zoho/Dynamics/Freshsales); Pie/Donut (common,
Zoho/Pipedrive/monday); Widget Configuration metric+dimension+filter (table-stakes, Pipedrive/HubSpot/Zoho).

- [ ] Add widget metric choices constant:

  ```python
  WIDGET_METRIC_CHOICES = [
      # Scalar KPI metrics (kind=scalar)
      ("kpi_open_pipeline",      "Open Pipeline Value"),
      ("kpi_weighted_forecast",  "Weighted Forecast"),
      ("kpi_win_rate",           "Win Rate (%)"),
      ("kpi_open_cases",         "Open Cases"),
      ("kpi_avg_csat",           "Average CSAT"),
      ("kpi_open_tasks",         "Open Tasks"),
      # Series / categorical metrics (kind=series)
      ("pipeline_by_stage",      "Pipeline by Stage (Count)"),
      ("pipeline_value_by_stage","Pipeline by Stage (Value)"),
      ("leads_by_rating",        "Leads by Rating"),
      ("leads_by_status",        "Leads by Status"),
      ("win_loss",               "Win / Loss Comparison"),
      ("cases_by_status",        "Cases by Status"),
      ("cases_by_priority",      "Cases by Priority"),
      ("revenue_won_by_month",   "Revenue Won by Month"),
      ("top_performers",         "Top Performers (Revenue Won)"),
      ("tasks_by_type",          "Tasks by Type"),
      ("campaign_roi",           "Campaign ROI"),
  ]

  CHART_TYPE_CHOICES = [
      ("kpi",       "KPI Card"),
      ("bar",       "Bar Chart"),
      ("line",      "Line Chart"),
      ("pie",       "Pie Chart"),
      ("doughnut",  "Doughnut Chart"),
      ("gauge",     "Gauge"),
      ("table",     "Data Table"),
  ]

  WIDGET_SIZE_CHOICES = [
      ("small",  "Small (1 col)"),
      ("medium", "Medium (2 col)"),
      ("large",  "Large (3 col)"),
      ("full",   "Full Width"),
  ]
  ```

- [ ] Add `DashboardWidget(models.Model)`:
  - `tenant` — `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="crm_widgets", db_index=True)`
  - `dashboard` — `ForeignKey(AnalyticsDashboard, on_delete=CASCADE, related_name="widgets")`
    (driver: each widget belongs to one dashboard; CASCADE removes widget when dashboard deleted)
  - `title` — `CharField(max_length=120)` — display label on the tile
  - `metric` — `CharField(max_length=40, choices=WIDGET_METRIC_CHOICES)`
    (driver: Widget Configuration — fixed catalog of metric_key choices, Pipedrive/HubSpot/Zoho)
  - `chart_type` — `CharField(max_length=12, choices=CHART_TYPE_CHOICES, default="bar")`
    (driver: Bar/Line/Pie/Doughnut/KPI/Gauge/Table — all leaders)
  - `date_range` — `CharField(max_length=12, choices=PERIOD_CHOICES, blank=True)`
    — blank = inherit `dashboard.default_period` (driver: per-widget date override)
  - `size` — `CharField(max_length=8, choices=WIDGET_SIZE_CHOICES, default="medium")`
    (driver: Drag-and-drop layout — store column span; live resize deferred)
  - `position` — `PositiveSmallIntegerField(default=0)`
    (driver: manual ordering; drag-and-drop reorder deferred to JS polish sprint)
  - `target_value` — `DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)`
    (driver: Gauge dial target / KPI goal threshold — Salesforce/Zoho/Insightly)
  - `created_at` / `updated_at` — `DateTimeField(auto_now_add/auto_now)`
  - `Meta.ordering = ["position", "id"]`
  - DB indexes: `("tenant", "dashboard")` → `crm_widget_tenant_dash_idx`
  - `__str__`: `f"{self.title} ({self.get_chart_type_display()})"`
  - **Reuses**: `core.Tenant`. No spine duplication. Aggregates existing CRM models via `analytics.py`.

### 1c. `AnalyticsReport` [RPT-] — `TenantNumbered`, `NUMBER_PREFIX = "RPT"`

Drivers: Sales Activity Report (table-stakes, Salesforce/HubSpot/Pipedrive/Dynamics 365); Sales Performance /
Top Performers (table-stakes, all 10 leaders); Pipeline / Funnel Analysis (table-stakes, all 10 — core CRM report);
Service Resolution Time (table-stakes, Zendesk/Salesforce Service Cloud); CSAT/Satisfaction (table-stakes,
Zendesk/Salesforce Service/HubSpot); Report Saved Filters/Parameters (table-stakes, Salesforce/HubSpot);
Scheduling fields stored now, wired to task queue in a later sprint.

- [ ] Add report type and group-by choices constants:

  ```python
  REPORT_TYPE_CHOICES = [
      ("sales_activity",    "Sales Activity"),
      ("sales_performance", "Sales Performance"),
      ("funnel",            "Pipeline / Funnel"),
      ("service",           "Service (Resolution & CSAT)"),
  ]

  GROUP_BY_CHOICES = [
      ("month",    "By Month"),
      ("week",     "By Week"),
      ("owner",    "By Owner"),
      ("priority", "By Priority"),
      ("stage",    "By Stage"),
  ]

  SCHEDULE_FREQ_CHOICES = [
      ("none",    "None"),
      ("daily",   "Daily"),
      ("weekly",  "Weekly"),
      ("monthly", "Monthly"),
  ]
  ```

- [ ] Add `AnalyticsReport(TenantNumbered)` with `NUMBER_PREFIX = "RPT"`:
  - `name` — `CharField(max_length=200)`
  - `description` — `TextField(blank=True)`
  - `report_type` — `CharField(max_length=24, choices=REPORT_TYPE_CHOICES)`
    (driver: the 4 table-stakes report types per approved build scope — approved plan §scope)
  - `date_range` — `CharField(max_length=12, choices=PERIOD_CHOICES, default="last_30")`
    (driver: Report Saved Filters/Parameters — Salesforce/HubSpot/Pipedrive/Zoho)
  - `group_by` — `CharField(max_length=12, choices=GROUP_BY_CHOICES, default="month")`
    (driver: dimension breakdowns — Pipedrive measure-by / HubSpot segment-by)
  - `is_favorite` — `BooleanField(default=False)` — pinned to report library header
    (driver: Insightly shared folders / Copper pre-built one-click templates)
  - `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
    related_name="crm_reports")` — null = system/shared report
  - `last_run_at` — `DateTimeField(null=True, blank=True, editable=False)` — system-set on snapshot
    creation; never exposed in form (driver: Copper/Insightly report freshness indicator)
  - `schedule_frequency` — `CharField(max_length=8, choices=SCHEDULE_FREQ_CHOICES, default="none")`
    (driver: Scheduled Report Email Delivery — store now; task-queue wiring deferred)
  - `schedule_recipients` — `JSONField(default=list, blank=True)` — list of email addresses
  - `next_run_at` — `DateTimeField(null=True, blank=True)` — task queue sets this; null when none
  - `Meta.ordering = ["-is_favorite", "name"]`
  - `unique_together = ("tenant", "name")`
  - DB indexes: `("tenant", "report_type")` → `crm_rpt_tenant_type_idx`;
    `("tenant", "is_favorite")` → `crm_rpt_tenant_fav_idx`
  - `__str__`: `f"{self.number} · {self.name}"`
  - **Reuses**: `core.Tenant` (via TenantNumbered), `accounts.User`. All compute logic in `analytics.py`
    — this model stores saved parameters only, no aggregated data.

### 1d. `ReportSnapshot` — tenant-scoped child (no number prefix)

Drivers: Historical Snapshot / Trend Data (common, Salesforce Reporting Snapshots/Zoho historical trend/
HubSpot deal change history); Period-over-Period Comparison (common, Salesforce/HubSpot/Zoho/Pipedrive).

- [ ] Add `ReportSnapshot(models.Model)`:
  - `tenant` — `ForeignKey("core.Tenant", on_delete=CASCADE, related_name="crm_snapshots", db_index=True)`
  - `report` — `ForeignKey(AnalyticsReport, on_delete=CASCADE, related_name="snapshots")`
  - `title` — `CharField(max_length=200)` — e.g. "Sales Activity · Last 30 Days · 2026-06-27"
    (auto-set by `report_snapshot` view action; editable if user wants to rename)
  - `generated_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True,
    related_name="crm_snapshots_generated")`
  - `generated_at` — `DateTimeField(auto_now_add=True)`
  - `summary` — `JSONField(default=list)` — list of KPI dicts, e.g.
    `[{"label": "Tasks Completed", "value": 143}, {"label": "Calls Logged", "value": 89}]`
  - `data` — `JSONField(default=dict)` — full result: `{"columns": [...], "rows": [...],
    "chart_type": "bar", "chart_labels": [...], "chart_data": [...], "totals": {...}}`
  - `Meta.ordering = ["-generated_at"]`
  - DB indexes: `("tenant", "report")` → `crm_snap_tenant_report_idx`;
    `("tenant", "generated_at")` → `crm_snap_tenant_gen_idx`
  - `__str__`: `f"{self.title} @ {self.generated_at:%Y-%m-%d %H:%M}"`
  - No create form — made exclusively via the `report_snapshot` POST action.
  - **Reuses**: `core.Tenant`, `accounts.User`. Pure analytics artifact; no spine FK.

---

## 2. `apps/crm/analytics.py` — compute helper (no new DB tables)

All functions are tenant-scoped, read-only against existing CRM models, and return plain Python dicts.

- [ ] Create `apps/crm/analytics.py` with the following structure:

  **Date range utilities:**
  - [ ] `RANGE_CHOICES` — mirrors `PERIOD_CHOICES` (same keys: `last_7`, `last_30`, `last_90`,
    `quarter`, `year`, `all`)
  - [ ] `range_bounds(key)` → `(start_date, end_date)` using `timezone.now()` — handles `quarter`
    (first day of current quarter), `year` (Jan 1), `all` (returns `None, None`). Used by every
    compute function to turn a period key into `created_at__gte` / `created_at__lt` filter kwargs.

  **Widget metrics registry:**
  - [ ] `WIDGET_METRICS` dict — `metric_key → {"label": str, "kind": "scalar"|"series"|"table",
    "compatible_charts": [...]}`. Maps the 17 `WIDGET_METRIC_CHOICES` keys. Used by
    `DashboardWidgetForm.clean()` to validate chart_type vs metric kind.

  **Widget compute function:**
  - [ ] `compute_widget(widget)` → `dict` with keys `kind`, `value`, `labels`, `data`, `columns`,
    `rows`, `max`, `target`. Branches on `widget.metric`:
    - `kpi_open_pipeline` — `Opportunity.objects.filter(tenant, stage__in=OPEN_STAGES).aggregate(Sum("amount"))`
    - `kpi_weighted_forecast` — `Sum(amount * probability / 100)` via `ExpressionWrapper`
    - `kpi_win_rate` — closed-won count / total closed count × 100
    - `kpi_open_cases` — `Case.objects.filter(tenant, status__in=["open","in_progress"]).count()`
    - `kpi_avg_csat` — `Case.objects.filter(tenant, satisfaction_rating__isnull=False).aggregate(Avg("satisfaction_rating"))`
    - `kpi_open_tasks` — `CrmTask.objects.filter(tenant, status__in=["todo","in_progress"]).count()`
    - `pipeline_by_stage` — `Opportunity.objects.filter(tenant).values("stage").annotate(Count("id"))`
    - `pipeline_value_by_stage` — same with `Sum("amount")`
    - `leads_by_rating` — `Lead.objects.filter(tenant).values("rating").annotate(Count("id"))`
    - `leads_by_status` — `Lead.objects.filter(tenant).values("status").annotate(Count("id"))`
    - `win_loss` — `{"Won": closed_won_count, "Lost": closed_lost_count}`
    - `cases_by_status` — `Case.objects.filter(tenant).values("status").annotate(Count("id"))`
    - `cases_by_priority` — same with `priority`
    - `revenue_won_by_month` — `Opportunity.objects.filter(tenant, stage="closed_won").annotate(
      month=TruncMonth("close_date")).values("month").annotate(revenue=Sum("amount")).order_by("month")`
    - `top_performers` — `Opportunity.objects.filter(tenant, stage="closed_won")
      .values("owner__username").annotate(revenue=Sum("amount"), deals=Count("id")).order_by("-revenue")[:10]`
    - `tasks_by_type` — `CrmTask.objects.filter(tenant).values("task_type").annotate(Count("id"))`
    - `campaign_roi` — `Campaign.objects.filter(tenant).values("name","budget","actual_cost","expected_revenue")`
    - All filtered by `range_bounds(widget.date_range or widget.dashboard.default_period)` on the
      appropriate date field (`created_at` / `close_date` / `start_date`).

  **Report compute functions:**
  - [ ] `compute_report(report)` → `dict` — dispatcher that calls one of the 4 below:

  - [ ] `_compute_sales_activity(tenant, start, end, group_by)`:
    - Aggregates `CrmTask` (completed, by type), `CommunicationLog` (by channel), `CalendarEvent`
      (by owner) over the period. Groups by `month`/`week`/`owner` per `group_by`.
    - Returns `{"summary": [{label, value},...], "columns": [...], "rows": [...],
      "chart_type": "line", "chart_labels": [...], "chart_data": [...]}`
    - Fields used: `CrmTask.completed_at`, `CrmTask.task_type`, `CrmTask.owner`;
      `CommunicationLog.occurred_at`, `CommunicationLog.channel`;
      `CalendarEvent.start_at`, `CalendarEvent.owner`

  - [ ] `_compute_sales_performance(tenant, start, end, group_by)`:
    - Per-owner: deals won, revenue won (`Sum("amount")` where `stage="closed_won"`), win rate
      (won / total closed), quota attainment (won / `SalesQuota.target_amount` × 100).
    - Groups by `owner`. Returns ranked rows + bar chart data.
    - Fields used: `Opportunity.stage`, `Opportunity.amount`, `Opportunity.owner`,
      `Opportunity.close_date`; `SalesQuota.target_amount`, `SalesQuota.owner`

  - [ ] `_compute_funnel(tenant, start, end, group_by)`:
    - Stage-by-stage count and value from `Opportunity.stage` + lead-to-opp conversion from
      `Lead.status`. Calculates drop-off % between consecutive stages.
    - Returns funnel rows ordered by stage progression. Chart type "bar" (horizontal).
    - Fields used: `Opportunity.stage`, `Opportunity.amount`, `Opportunity.created_at`;
      `Lead.status`, `Lead.created_at`

  - [ ] `_compute_service(tenant, start, end, group_by)`:
    - Resolved count, avg resolution hrs (`Avg(resolved_at - created_at)`),
      avg first-response hrs (`Avg(first_responded_at - created_at)`),
      SLA breach rate (`% where resolved_at > resolution_due`), avg CSAT, rated case count.
    - Groups by `month`/`week`/`owner`/`priority` per `group_by`.
    - Returns summary KPIs + detail rows + bar chart.
    - Fields used: `Case.created_at`, `Case.resolved_at`, `Case.first_responded_at`,
      `Case.resolution_due`, `Case.satisfaction_rating`, `Case.owner`, `Case.priority`

  **Note:** `OPEN_STAGES` constant (used by `kpi_open_pipeline`) — import from `crm.models` or
  define locally in `analytics.py` as the set of stages that are neither closed_won nor closed_lost.

---

## 3. Backend — `apps/crm/forms.py`

- [ ] Add `AnalyticsDashboardForm(TenantModelForm)`:
  - `model = AnalyticsDashboard`
  - `exclude = ("tenant", "number", "created_at", "updated_at")`
  - No special `clean()` needed; `owner` dropdown scoped to `tenant` users in `__init__`

- [ ] Add `DashboardWidgetForm(TenantModelForm)`:
  - `model = DashboardWidget`
  - `exclude = ("tenant", "dashboard", "created_at", "updated_at")`
  - `__init__`: no extra FK scoping (metric/chart_type are choice fields, not FKs)
  - `clean()`: validate `chart_type` is compatible with `metric` kind using `WIDGET_METRICS` registry:
    - scalar metrics (`kpi_*`) must use `chart_type in ("kpi", "gauge")` — raise
      `ValidationError("This metric is a single value — use KPI Card or Gauge chart type.")`
    - series/table metrics must NOT use `chart_type="kpi"` — raise
      `ValidationError("KPI Card only works with scalar (single-value) metrics.")`

- [ ] Add `AnalyticsReportForm(TenantModelForm)`:
  - `model = AnalyticsReport`
  - `exclude = ("tenant", "number", "last_run_at", "created_at", "updated_at")`
  - `owner` dropdown scoped to `tenant` users in `__init__`
  - NOTE: `schedule_recipients` is a `JSONField` — render as `Textarea` with a help_text
    "Comma-separated email addresses (stored as JSON list). Leave blank if no schedule."
  - `clean_schedule_recipients()`: if non-blank, parse comma-separated emails into a Python list;
    store as `["a@b.com", "c@d.com"]`

- [ ] (No `ReportSnapshotForm` — snapshots are created by a view action, never a user form.)

---

## 4. Backend — `apps/crm/views.py`

Add a clearly-delimited `# ── 1.6 Analytics & Reporting ──` section at the end of `views.py`.

### 4a. `AnalyticsDashboard` CRUD

- [ ] **`dashboard_list(request)`** — `@login_required`:
  - QS: `AnalyticsDashboard.objects.filter(tenant=request.tenant).filter(
    Q(owner=request.user) | Q(is_shared=True)).select_related("owner").order_by("-is_default","name")`
  - Search: `q` on `name`, `description`
  - Filters: `?shared=1` → `is_shared=True`; `?period=<key>` → `default_period=<key>`
  - Context: `{"dashboards": page, "period_choices": PERIOD_CHOICES, "q": q, "shared": shared}`
  - Template: `"crm/analytics/dashboard/list.html"`

- [ ] **`dashboard_create(request)`** — `@login_required`, GET+POST:
  - On POST save: set `obj.tenant = request.tenant`; if `obj.is_default`, clear other
    `is_default=True` dashboards for this owner before saving
  - `write_audit_log(request.user, obj, "create")`
  - Redirect to `crm:dashboard_detail pk=obj.pk`
  - Template: `"crm/analytics/dashboard/form.html"`

- [ ] **`dashboard_detail(request, pk)`** — `@login_required`:
  - Fetch: `get_object_or_404(AnalyticsDashboard, pk=pk, tenant=request.tenant)` — also allow if
    `obj.is_shared` (but still enforce `obj.tenant == request.tenant` for IDOR safety)
  - Widgets: `widgets = obj.widgets.order_by("position", "id")`
  - Compute each widget: `computed = [compute_widget(w) for w in widgets]`
  - Context: `{"dashboard": obj, "widgets": widgets, "computed": computed,
    "widget_zip": zip(widgets, computed), "layout_cols": {"one_col":1,"two_col":2,"three_col":3}[obj.layout]}`
  - Template: `"crm/analytics/dashboard/detail.html"` — renders Chart.js via `json_script`

- [ ] **`dashboard_edit(request, pk)`** — `@login_required`, GET+POST:
  - Fetch with `tenant=request.tenant`; if `obj.is_default` toggled on, clear other defaults for owner
  - `write_audit_log(request.user, obj, "update")`
  - Template: `"crm/analytics/dashboard/form.html"`

- [ ] **`dashboard_delete(request, pk)`** — `@login_required`, POST-only:
  - `get_object_or_404(AnalyticsDashboard, pk=pk, tenant=request.tenant)`
  - Delete cascades to widgets (Django CASCADE)
  - `write_audit_log`; `messages.success`; redirect to `crm:dashboard_list`

### 4b. `DashboardWidget` CRUD

- [ ] **`widget_create(request, dashboard_pk)`** — `@login_required`, GET+POST:
  - Fetch dashboard: `get_object_or_404(AnalyticsDashboard, pk=dashboard_pk, tenant=request.tenant)`
  - On POST save: `obj.tenant = request.tenant; obj.dashboard = dashboard`
  - Set `obj.position = dashboard.widgets.count()` (append to end)
  - `write_audit_log`; redirect to `crm:dashboard_detail pk=dashboard.pk`
  - Template: `"crm/analytics/widget/form.html"` with context `{"dashboard": dashboard}`

- [ ] **`widget_edit(request, pk)`** — `@login_required`, GET+POST:
  - Fetch: `get_object_or_404(DashboardWidget, pk=pk, tenant=request.tenant)`
  - On save: `write_audit_log`; redirect to `crm:dashboard_detail pk=obj.dashboard.pk`
  - Template: `"crm/analytics/widget/form.html"`

- [ ] **`widget_delete(request, pk)`** — `@login_required`, POST-only:
  - Fetch; store `dashboard_pk = obj.dashboard.pk`; `write_audit_log`; `obj.delete()`
  - Redirect to `crm:dashboard_detail pk=dashboard_pk`

- [ ] **`widget_move(request, pk)`** — `@login_required`, POST-only:
  - Accepts `direction` POST param (`"up"` or `"down"`)
  - Swaps `position` with the adjacent widget in the same dashboard
  - Redirect to `crm:dashboard_detail pk=obj.dashboard.pk`

### 4c. `AnalyticsReport` CRUD + actions

- [ ] **`report_list(request)`** — `@login_required`:
  - QS: `AnalyticsReport.objects.filter(tenant=request.tenant).select_related("owner")
    .order_by("-is_favorite","name")`
  - Search: `q` on `name`, `description`
  - Filters: `?report_type=<key>`, `?is_favorite=1`
  - Context: `{"reports": page, "report_type_choices": REPORT_TYPE_CHOICES,
    "q": q, "report_type": rt, "is_favorite": fav}`
  - Template: `"crm/analytics/report/list.html"`

- [ ] **`report_create(request)`** — `@login_required`, GET+POST:
  - On POST save: `obj.tenant = request.tenant`; `write_audit_log`
  - Redirect to `crm:report_detail pk=obj.pk`
  - Template: `"crm/analytics/report/form.html"`

- [ ] **`report_detail(request, pk)`** — `@login_required`:
  - Fetch: `get_object_or_404(AnalyticsReport, pk=pk, tenant=request.tenant)`
  - Compute live: `result = compute_report(report)` — catches any exception, renders error message
    gracefully
  - Snapshots: `snapshots = report.snapshots.order_by("-generated_at")[:10]`
  - Context: `{"report": report, "result": result, "snapshots": snapshots}`
  - Template: `"crm/analytics/report/detail.html"`

- [ ] **`report_edit(request, pk)`** — `@login_required`, GET+POST:
  - `write_audit_log`; redirect to `crm:report_detail pk=obj.pk`
  - Template: `"crm/analytics/report/form.html"`

- [ ] **`report_delete(request, pk)`** — `@login_required`, POST-only:
  - Cascades to snapshots; `write_audit_log`; redirect to `crm:report_list`

- [ ] **`report_favorite(request, pk)`** — `@login_required`, POST-only:
  - Toggle `is_favorite`; `obj.save(update_fields=["is_favorite", "updated_at"])`; redirect to
    `crm:report_list`

- [ ] **`report_snapshot(request, pk)`** — `@login_required`, POST-only:
  - Fetch report; call `compute_report(report)`
  - Create `ReportSnapshot(tenant=request.tenant, report=report, generated_by=request.user,
    title=f"{report.name} · {report.get_date_range_display()} · {today}", summary=result["summary"],
    data=result)`
  - Stamp `report.last_run_at = timezone.now(); report.save(update_fields=["last_run_at","updated_at"])`
  - `write_audit_log`; `messages.success`; redirect to `crm:report_detail pk=pk`

### 4d. `ReportSnapshot` views

- [ ] **`snapshot_detail(request, pk)`** — `@login_required`:
  - Fetch: `get_object_or_404(ReportSnapshot, pk=pk, tenant=request.tenant)` with
    `select_related("report", "generated_by")`
  - Context: `{"snap": snap, "summary": snap.summary, "data": snap.data}`
  - Template: `"crm/analytics/snapshot/detail.html"`

- [ ] **`snapshot_delete(request, pk)`** — `@login_required`, POST-only:
  - Fetch; store `report_pk = snap.report_id`; `write_audit_log`; `snap.delete()`
  - Redirect to `crm:report_detail pk=report_pk`

---

## 5. Backend — `apps/crm/urls.py`

Append a `# ── 1.6 Analytics & Reporting ──` comment block with:

- [ ] Dashboard URLs:
  - `path("analytics/dashboards/", views.dashboard_list, name="dashboard_list")`
  - `path("analytics/dashboards/add/", views.dashboard_create, name="dashboard_create")`
  - `path("analytics/dashboards/<int:pk>/", views.dashboard_detail, name="dashboard_detail")`
  - `path("analytics/dashboards/<int:pk>/edit/", views.dashboard_edit, name="dashboard_edit")`
  - `path("analytics/dashboards/<int:pk>/delete/", views.dashboard_delete, name="dashboard_delete")`

- [ ] Widget URLs:
  - `path("analytics/dashboards/<int:dashboard_pk>/widgets/add/", views.widget_create, name="widget_create")`
  - `path("analytics/widgets/<int:pk>/edit/", views.widget_edit, name="widget_edit")`
  - `path("analytics/widgets/<int:pk>/delete/", views.widget_delete, name="widget_delete")`
  - `path("analytics/widgets/<int:pk>/move/", views.widget_move, name="widget_move")`

- [ ] Report URLs:
  - `path("analytics/reports/", views.report_list, name="report_list")`
  - `path("analytics/reports/add/", views.report_create, name="report_create")`
  - `path("analytics/reports/<int:pk>/", views.report_detail, name="report_detail")`
  - `path("analytics/reports/<int:pk>/edit/", views.report_edit, name="report_edit")`
  - `path("analytics/reports/<int:pk>/delete/", views.report_delete, name="report_delete")`
  - `path("analytics/reports/<int:pk>/favorite/", views.report_favorite, name="report_favorite")`
  - `path("analytics/reports/<int:pk>/snapshot/", views.report_snapshot, name="report_snapshot")`

- [ ] Snapshot URLs:
  - `path("analytics/snapshots/<int:pk>/", views.snapshot_detail, name="snapshot_detail")`
  - `path("analytics/snapshots/<int:pk>/delete/", views.snapshot_delete, name="snapshot_delete")`

---

## 6. Backend — `apps/crm/admin.py`

- [ ] Register `AnalyticsDashboard` — `list_display = ("number","name","owner","is_shared","is_default","layout","default_period")`;
  `list_filter = ("is_shared","is_default","layout","default_period")`;
  `search_fields = ("number","name")`; `raw_id_fields = ("owner",)`
- [ ] Register `DashboardWidget` — `list_display = ("title","metric","chart_type","size","position","dashboard")`;
  `list_filter = ("metric","chart_type","size")`;
  `raw_id_fields = ("dashboard",)` (inline on `AnalyticsDashboard` is optional nice-to-have)
- [ ] Register `AnalyticsReport` — `list_display = ("number","name","report_type","date_range","group_by","is_favorite","last_run_at","owner")`;
  `list_filter = ("report_type","date_range","group_by","is_favorite")`;
  `search_fields = ("number","name")`;
  `readonly_fields = ("last_run_at",)`
- [ ] Register `ReportSnapshot` — `list_display = ("title","report","generated_by","generated_at")`;
  `list_filter = ("report__report_type",)`;
  `readonly_fields = ("generated_at","summary","data")`

---

## 7. Seeder — `apps/crm/management/commands/seed_crm.py`

Add `_seed_analytics(tenant)` called from the existing `handle()`. No new management files needed
(the `management/` and `management/commands/` `__init__.py` files already exist).

- [ ] Add `_seed_analytics(tenant)` function:

  **Idempotency guard:**
  ```python
  if AnalyticsDashboard.objects.filter(tenant=tenant).exists():
      self.stdout.write("  [skip] Analytics data already seeded.")
      return
  ```

  **Seed data:**
  - [ ] Resolve `owner` = first tenant admin user (`User.objects.filter(tenantmembership__tenant=tenant, tenantmembership__role="admin").first()`)
  - [ ] Create **Dashboard 1**: `name="Sales Command Center"`, `layout="two_col"`, `is_default=True`,
    `is_shared=True`, `default_period="last_30"` — use `AnalyticsDashboard(tenant=tenant, owner=owner, ...)` + `.save()` (TenantNumbered)
  - [ ] Add 5 widgets to Dashboard 1 (one per metric kind):
    1. `title="Open Pipeline"`, `metric="kpi_open_pipeline"`, `chart_type="kpi"`, `size="small"`, `position=0`
    2. `title="Pipeline by Stage"`, `metric="pipeline_by_stage"`, `chart_type="bar"`, `size="medium"`, `position=1`
    3. `title="Revenue Won by Month"`, `metric="revenue_won_by_month"`, `chart_type="line"`, `size="large"`, `position=2`
    4. `title="Win / Loss"`, `metric="win_loss"`, `chart_type="doughnut"`, `size="small"`, `position=3`
    5. `title="Top Performers"`, `metric="top_performers"`, `chart_type="table"`, `size="medium"`, `position=4`
    — Use `DashboardWidget.objects.bulk_create([...])`
  - [ ] Create **Dashboard 2**: `name="Service Desk"`, `layout="two_col"`, `is_default=False`,
    `is_shared=True`, `default_period="last_30"`
  - [ ] Add 3 widgets to Dashboard 2:
    1. `title="Open Cases"`, `metric="kpi_open_cases"`, `chart_type="kpi"`, `size="small"`, `position=0`
    2. `title="Cases by Priority"`, `metric="cases_by_priority"`, `chart_type="bar"`, `size="medium"`, `position=1`
    3. `title="Average CSAT"`, `metric="kpi_avg_csat"`, `chart_type="gauge"`, `size="small"`, `position=2`, `target_value=Decimal("4.0")`
  - [ ] Create **4 Reports** (one per `report_type`), using `AnalyticsReport(tenant=tenant, ...).save()`:
    1. `name="Monthly Sales Activity"`, `report_type="sales_activity"`, `date_range="last_30"`, `group_by="month"`, `is_favorite=True`, `owner=owner`
    2. `name="Sales Performance — Top Reps"`, `report_type="sales_performance"`, `date_range="quarter"`, `group_by="owner"`, `is_favorite=True`, `owner=owner`
    3. `name="Pipeline Funnel Overview"`, `report_type="funnel"`, `date_range="last_90"`, `group_by="stage"`, `is_favorite=False`, `owner=owner`
    4. `name="Service Resolution & CSAT"`, `report_type="service"`, `date_range="last_30"`, `group_by="month"`, `is_favorite=False`, `owner=owner`
  - [ ] Create **2 Snapshots** for the first report (demonstrate trending):
    - Snapshot 1: `title="Monthly Sales Activity · Snapshot 1"`, compute `_compute_sales_activity(tenant, ...)`
      for `last_30`; store result in `summary`/`data`; `generated_by=owner`
    - Snapshot 2: same report, `title="Monthly Sales Activity · Snapshot 2"` (re-run to show the
      snapshots list on report_detail)
    - Use `ReportSnapshot.objects.create(...)` (not `TenantNumbered` — no `save()` override needed)
  - [ ] Print on success:
    ```
    self.stdout.write("  [analytics] 2 dashboards (8 widgets) + 4 reports + 2 snapshots seeded.")
    self.stdout.write("  Login as admin_acme / password123 to see analytics data.")
    ```

---

## 8. Wire-up — `apps/core/navigation.py`

- [ ] Update `LIVE_LINKS["1.6"]` — replace the two stub entries with real routes + add overview:

  ```python
  # 1.6 Analytics & Reporting — dashboards (per-user widgets), standard reports (4 types), snapshots
  "1.6": {
      "Dashboards":       "crm:dashboard_list",   # bullet (per-user/shared dashboard containers)
      "Standard Reports": "crm:report_list",       # bullet (sales activity / performance / funnel / service)
      "Analytics Overview": "crm:overview",        # extra (module landing)
  },
  ```

  NOTE: "Analytics Overview" does not match a NavERP.md bullet — it will be appended as an extra
  live leaf (navigation.py handles non-matching labels as extras, same as "Subscription Invoices" in 0.1).

---

## 9. Templates — `templates/crm/analytics/<entity>/<page>.html`

Sub-module folder: `templates/crm/analytics/`. Per CLAUDE.md template rules:
- sub-module = `analytics`, each entity gets its own subfolder
- Pages are bare filenames: `list.html`, `detail.html`, `form.html`

### 9a. `templates/crm/analytics/dashboard/list.html`

- [ ] Extend `base.html`. Page header: "Dashboards" + "New Dashboard" button → `crm:dashboard_create`.
- [ ] Filter bar:
  - Search input `name="q"` (persists `{{ q }}`)
  - "Shared Only" checkbox or toggle → `?shared=1` (compare `{% if request.GET.shared == "1" %}checked{% endif %}`)
  - Period select `name="period"` — iterate `period_choices`; compare `{% if request.GET.period == value %}selected{% endif %}`
  - "Reset" link → `crm:dashboard_list`
- [ ] Dashboard cards grid (not a table — dashboards are card-view entities):
  - Card per dashboard: name (link to `crm:dashboard_detail`), number badge, description,
    default badge (green "Default" if `is_default`), shared badge (blue "Shared" if `is_shared`),
    layout chip, period chip, owner name, widget count (`dashboard.widgets.count`),
    Edit / Delete actions (POST delete with `onclick="return confirm(...)"` + `{% csrf_token %}`)
- [ ] Empty state + pagination.

### 9b. `templates/crm/analytics/dashboard/form.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Dashboards › Add / Edit.
- [ ] Fields: `name`, `description` (textarea), `owner`, `is_shared`, `is_default`, `layout`, `default_period`.
- [ ] Help text below `is_default`: "Only one dashboard per user can be the default. Enabling this will
  unset other defaults for the same owner."
- [ ] Submit + Cancel (→ `crm:dashboard_list`).

### 9c. `templates/crm/analytics/dashboard/detail.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Dashboards › `{{ dashboard.number }}`.
- [ ] Page header: dashboard name + description + chips (layout, period, Shared badge, Default badge).
- [ ] Sidebar actions:
  - "Edit Dashboard" → `crm:dashboard_edit`
  - "Add Widget" → `crm:widget_create dashboard_pk=dashboard.pk`
  - Delete (POST to `crm:dashboard_delete` + confirm)
  - Back to Dashboards
- [ ] Widget grid — render `{% for widget, computed in widget_zip %}` in a CSS grid with
  `layout_cols` columns:
  - Each tile: title, metric label, size badge.
  - KPI tile (`chart_type=="kpi"`): large centered value `{{ computed.value }}` with optional
    target comparison (% of target if `widget.target_value`).
  - Bar/Line/Pie/Doughnut tile: `<canvas id="chart-{{ widget.pk }}">` — emit one
    `{% json_script computed.chart_data widget.pk|stringformat:"s" %}` block; JS loop in
    `{% block extra_js %}` iterates `document.querySelectorAll("canvas[id^='chart-']")` and builds
    Chart.js instances with `labels` and `data` from the JSON script tags.
  - Gauge tile: HTML progress bar from 0 to `computed.max` (or `widget.target_value`) showing
    `computed.value` — no Chart.js for gauge (pure CSS).
  - Table tile: `<table>` of `computed.columns` / `computed.rows`.
  - Per-tile actions: Edit (→ `crm:widget_edit`), Move Up / Move Down (POST → `crm:widget_move`
    with `direction=up/down`), Delete (POST → `crm:widget_delete` + confirm).
- [ ] Empty state when no widgets: "No widgets yet. Add your first widget."
- [ ] `{% block extra_js %}` — Chart.js CDN `<script>` + initialization loop.

### 9d. `templates/crm/analytics/widget/form.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Dashboards › `{{ dashboard.number }}` › Add Widget / Edit Widget.
- [ ] Fields: `title`, `metric` (select from `WIDGET_METRIC_CHOICES`), `chart_type`, `date_range`
  (blank = inherit dashboard default), `size`, `position`, `target_value`.
- [ ] Help text below `chart_type`: "KPI Card and Gauge only work with scalar metrics (kpi_* prefix).
  Bar, Line, Pie, Doughnut, and Table work with category/series metrics."
- [ ] Submit + Cancel (→ `crm:dashboard_detail pk=dashboard.pk`).

### 9e. `templates/crm/analytics/report/list.html`

- [ ] Extend `base.html`. Page header: "Standard Reports" + "New Report" button → `crm:report_create`.
- [ ] Filter bar:
  - Search `name="q"` (persists `{{ q }}`)
  - Report type select `name="report_type"` — iterate `report_type_choices`;
    compare `{% if request.GET.report_type == value %}selected{% endif %}`
  - "Favorites only" checkbox → `?is_favorite=1`
  - "Reset" link → `crm:report_list`
- [ ] Table columns: Number (link to `crm:report_detail`), Name, Type (badge: sales_activity=blue /
  sales_performance=green / funnel=purple / service=amber), Date Range, Group By, Owner, Last Run
  (`last_run_at|timesince` or "Never"), Favorite (star icon — POST to `crm:report_favorite`),
  Actions (view/edit/delete).
- [ ] Favorite star: filled gold if `is_favorite`, hollow otherwise. POST form with `{% csrf_token %}`.
- [ ] Empty state + pagination.

### 9f. `templates/crm/analytics/report/form.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Standard Reports › Add / Edit.
- [ ] Fields: `name`, `description`, `report_type`, `date_range`, `group_by`, `is_favorite`, `owner`,
  `schedule_frequency`, `schedule_recipients` (textarea with help text), `next_run_at`.
- [ ] Section divider between main fields and scheduling fields with note: "Scheduling fields are stored
  now; email delivery requires the task-queue integration (future sprint)."
- [ ] Submit + Cancel (→ `crm:report_list`).

### 9g. `templates/crm/analytics/report/detail.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Standard Reports › `{{ report.number }}`.
- [ ] Sidebar actions:
  - "Run Snapshot" → POST to `crm:report_snapshot pk=report.pk` + `{% csrf_token %}`
  - Favorite toggle → POST to `crm:report_favorite` (star icon)
  - "Edit Report" → `crm:report_edit`
  - Delete (POST + confirm)
  - Back to Reports
- [ ] Report header card: name, type badge, date range, group by, owner, last run timestamp.
- [ ] **Summary KPIs row**: `{% for kpi in result.summary %}` — render each as a small KPI card
  (`label` + `value`).
- [ ] **Chart area**: `<canvas id="report-chart">` — emit `{% json_script result.chart_labels "rpt-labels" %}`
  and `{% json_script result.chart_data "rpt-data" %}`; JS renders a Chart.js chart of type
  `{{ result.chart_type }}` with those labels/data in `{% block extra_js %}`.
- [ ] **Detail table**: `<table>` of `result.columns` headers + `result.rows` rows (generic — works for
  all 4 report types since they all return the same dict shape).
- [ ] **Snapshots list**: `{% for snap in snapshots %}` — card per snapshot: title, generated_by,
  generated_at (relative), link to `crm:snapshot_detail`, Delete POST → `crm:snapshot_delete`.
  Empty state: "No snapshots yet. Click 'Run Snapshot' to save the current results."
- [ ] `{% block extra_js %}` — Chart.js + initialization.

### 9h. `templates/crm/analytics/snapshot/detail.html`

- [ ] Extend `base.html`. Breadcrumb: CRM › Standard Reports › `{{ snap.report.name }}` › Snapshot.
- [ ] Sidebar: "Back to Report" → `crm:report_detail pk=snap.report.pk`; Delete snapshot (POST + confirm).
- [ ] Header card: title, report link, generated by, generated at.
- [ ] **Summary KPIs row**: `{% for kpi in summary %}` — same pattern as report_detail.
- [ ] **Chart + Table**: from `data` JSON (stored result) — same rendering as report_detail but reading
  from the snapshot's stored data instead of recomputing.
- [ ] NOTE: This page shows a frozen historical result; add a note "Snapshot captured on `{{ snap.generated_at|date }}`."

---

## 10. Verify

- [ ] `venv\Scripts\python.exe manage.py makemigrations crm` — confirm a single new migration file
  `0015_analyticsdashboard_dashboardwidget_analyticsreport_reportsnapshot.py` (or similar name);
  no unapplied changes after `--check`.
- [ ] `venv\Scripts\python.exe manage.py migrate` — applies cleanly to `nav_erp` MariaDB.
- [ ] `venv\Scripts\python.exe manage.py seed_crm` — first run: prints "2 dashboards (8 widgets) + 4
  reports + 2 snapshots seeded" + login instructions.
- [ ] `venv\Scripts\python.exe manage.py seed_crm` (second run) — `[skip] Analytics data already seeded.`
  message fires; no new rows, no `IntegrityError` (idempotency verified).
- [ ] `venv\Scripts\python.exe manage.py check` — 0 issues.
- [ ] **Smoke sweep** (throwaway `temp/test_analytics_smoke.py`) — `force_login(admin_acme)`, assert:
  - [ ] `crm:dashboard_list` → 200 (seeded dashboards visible)
  - [ ] `crm:dashboard_create` → 200 (form renders)
  - [ ] `crm:dashboard_detail pk=<sales_command_center>` → 200 (widget grid rendered; no unrendered
    `{#`/`{% comment` tags)
  - [ ] `crm:dashboard_edit pk=<dash>` → 200
  - [ ] `crm:dashboard_delete pk=<dash>` → POST → 302
  - [ ] `crm:widget_create dashboard_pk=<dash>` → 200
  - [ ] `crm:widget_edit pk=<widget>` → 200
  - [ ] `crm:widget_move pk=<widget>` POST `direction=down` → 302
  - [ ] `crm:widget_delete pk=<widget>` POST → 302
  - [ ] `crm:report_list` → 200 (seeded reports visible)
  - [ ] `crm:report_create` → 200
  - [ ] `crm:report_detail pk=<sales_activity_report>` → 200 (KPI cards + chart + table rendered)
  - [ ] `crm:report_edit pk=<report>` → 200
  - [ ] `crm:report_favorite pk=<report>` POST → 302 (favorite toggled)
  - [ ] `crm:report_snapshot pk=<report>` POST → 302 (new snapshot created; `last_run_at` stamped)
  - [ ] `crm:report_delete pk=<report>` POST → 302
  - [ ] `crm:snapshot_detail pk=<snap>` → 200 (stored data rendered without recompute)
  - [ ] `crm:snapshot_delete pk=<snap>` POST → 302
  - [ ] **Cross-tenant IDOR → 404**: `admin_acme` GET `crm:dashboard_detail pk=<globex_dashboard>` → 404
  - [ ] **Cross-tenant IDOR → 404**: `admin_acme` GET `crm:report_detail pk=<globex_report>` → 404
  - [ ] **No template comment leaks**: grep all new `.html` files for `{#` or `{% comment` — 0 matches
- [ ] **Sidebar Live**: log in as `admin_acme`; CRM → sub-module 1.6 → "Dashboards" and
  "Standard Reports" both show as **Live** (not "On the roadmap"). "Analytics Overview" also Live.
- [ ] **Filter verify**: `crm:report_list?report_type=funnel` → only funnel reports; `?is_favorite=1` →
  only favorited reports. `crm:dashboard_list?shared=1` → only shared dashboards.
- [ ] **Widget form validation**: POST `crm:widget_create` with `metric=kpi_open_pipeline` and
  `chart_type=bar` → form re-renders with `DashboardWidgetForm.clean()` error message.
- [ ] **Snapshot freshness**: after `report_snapshot` POST, `crm:report_detail` shows `last_run_at` as
  non-null and the new snapshot card appears in the snapshots list.

---

## 11. Close-out

- [ ] Run **code-reviewer** agent — focus: `compute_widget` branching completeness, `range_bounds`
  edge cases (empty DB), `DashboardWidgetForm.clean()` chart/metric compatibility, `dashboard_detail`
  context size (large computed list), atomic `is_default` toggle. Apply findings, one file per commit.
- [ ] Run **explorer** agent — verify all `{% url %}` names match `urls.py`, context-var names match
  templates, `WIDGET_METRIC_CHOICES` keys match `analytics.py` branch names, `LIVE_LINKS["1.6"]`
  resolves cleanly. Apply findings, one file per commit.
- [ ] Run **frontend-reviewer** agent — focus: Chart.js `json_script` pattern correctness, gauge
  CSS-only implementation, widget grid CSS classes match `layout_cols`, filter bar `|stringformat:"d"`
  for FK selects (none here — all choice fields), empty-state rendering. Apply findings, one file per commit.
- [ ] Run **performance-reviewer** agent — focus: `dashboard_detail` calling `compute_widget` N times
  in a loop (consider annotating or caching), `report_list` `select_related("owner")`, snapshot list
  `[:10]` slice, `DashboardWidget.objects.count()` per card on dashboard_list (use `Prefetch`).
  Apply findings, one file per commit.
- [ ] Run **qa-smoke-tester** agent — apply findings, one file per commit.
- [ ] Run **security-reviewer** agent — focus: `report_snapshot` POST stamps `last_run_at` server-side
  (not from user input); snapshot `data` JSON stored verbatim (no XSS risk since rendered via template
  tags); `compute_report` exception handling doesn't leak stack traces to the template;
  cross-tenant `is_shared` dashboards still enforce `tenant=request.tenant` IDOR guard.
  Apply findings, one file per commit.
- [ ] Run **test-writer** agent — apply output, one file per commit. Expected: `tests/test_analytics.py`
  covering:
  - `AnalyticsDashboard` model: `DASH-` prefix, `__str__`, `unique_together`, `is_default` toggle.
  - `DashboardWidget` model: ordering by position, `__str__`.
  - `AnalyticsReport` model: `RPT-` prefix, `__str__`, `unique_together`.
  - `ReportSnapshot` model: `__str__`, ordering.
  - `DashboardWidgetForm.clean()`: kpi_* metric + bar chart_type → ValidationError; kpi_* + kpi chart_type → valid.
  - `AnalyticsReportForm.clean_schedule_recipients()`: comma-separated → list; blank → empty list.
  - `analytics.range_bounds()`: `last_7`, `last_30`, `quarter`, `year`, `all` return correct tuple types.
  - `compute_widget()`: each of the 17 metric keys returns a dict with the expected keys.
  - `compute_report()`: each of the 4 report types returns a dict with `summary`, `columns`, `rows`,
    `chart_type`, `chart_labels`, `chart_data`.
  - CRUD views: dashboard list/create/detail/edit/delete → 200/302; all tenant-scoped.
  - Widget views: create under dashboard, edit, delete, move (position swap).
  - Report views: list/create/detail/edit/delete, favorite toggle, snapshot POST stamps `last_run_at`.
  - Snapshot views: detail renders stored data, delete redirects to report.
  - Cross-tenant IDOR → 404 for all 4 models.
  - Seeder idempotency.
- [ ] Update **`.claude/skills/crm/SKILL.md`** — add §1.6 to the Models section (4 new models);
  add 19 new url names to the URLs section; add `analytics/<entity>/` template paths;
  add `analytics.py` compute helpers; update `LIVE_LINKS["1.6"]`; add `_seed_analytics` to Seeder section.
- [ ] Mark 1.6 as delivered in **`README.md`** roadmap.

---

## 12. Later passes / deferred

- **Drag-and-drop JS layout builder** — `DashboardWidget.position` + `size` fields are stored now;
  interactive live rearrangement (Sortable.js / GridStack.js / HTMX drag) deferred to a UI-polish sprint.
  The `widget_move` (up/down) action ships now as the minimum usable ordering UX.
- **Scheduled email delivery** — `AnalyticsReport.schedule_frequency` / `schedule_recipients` /
  `next_run_at` fields are in the model and form now; actual task execution (Celery Beat / Django Q) is
  deferred; no migration change needed when it ships.
- **PDF export** — CSV download (simple `HttpResponse` streaming of report rows) is buildable without
  a library; PDF layout (WeasyPrint / reportlab) deferred.
- **Additional report types** — Win/Loss Analysis, Revenue Forecast, Lead Source / Campaign Attribution,
  Case Volume / Agent Performance, Deal Velocity, NPS/Survey Analytics — all have researched fields
  in the existing models; they can be added by extending `REPORT_TYPE_CHOICES` + adding compute branches
  in `analytics.py` (no migration needed for new report types).
- **AI natural-language report builder** — requires LLM API (OpenAI / Anthropic) integration; deferred.
- **Cross-object custom report builder** — Salesforce-style drag-fields-from-any-object canvas;
  deferred to Module 10 BI.
- **External BI embed** (Power BI / Tableau / Looker iframes) — integration/later.
- **Automatic nightly snapshot command** — `snapshot_crm_reports` management command (calls
  `compute_report` for all `schedule_frequency != "none"` reports) is deferred; the model fields
  are ready.
- **Real-time push (WebSockets / SSE)** — widgets compute on page load (HTMX GET); true push without
  page reload deferred.
- **Mobile-responsive widget grid** — CSS responsive breakpoints for the dashboard grid are best-effort
  this pass; full mobile-optimized widget resizing deferred.
- **`recurrence_anchor_day` on CrmTask** — deferred from 1.5 (see §14 of 1.5 notes above).

---

## 13. Review notes

(To be filled in after the build and review-agent sequence completes.)

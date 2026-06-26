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

## Review notes

(filled in at the end)

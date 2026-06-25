---
# HRM Sub-module 3.2 — Organizational Structure (rebuild)  — plan from research-hrm-org-structure.md  (2026-06-26)

**Building HRM 3.2 Organizational Structure (rebuild).** Model set: NEW `hrm.JobGrade` [JG-],
NEW `hrm.DepartmentProfile` [DP-], NEW `hrm.CostCenterProfile` [CC-], ENHANCE existing
`hrm.Designation` (add `job_grade` FK + `description` + `requirements` + `mid_salary` +
`budgeted_headcount`), DERIVED org_chart view (no model), DERIVED company_setup view (no model).

---

## 0. Template folder decision

3.2 is now a **multi-entity** sub-module (5 NavERP.md bullets, 4 entity types). Per CLAUDE.md
Template Folder Structure rule 2/3 the old single-entity folder `templates/hrm/designation/`
must move to a two-level sub-module folder `templates/hrm/organization/` with per-entity
sub-folders.

- [ ] Create new folder structure `templates/hrm/organization/`:
  - `organization/designation/{list,detail,form}.html`  — MOVED from `hrm/designation/`
  - `organization/jobgrade/{list,detail,form}.html`     — NEW
  - `organization/department/{list,detail,form}.html`   — NEW
  - `organization/costcenter/{list,detail,form}.html`   — NEW
  - `organization/org_chart.html`                        — NEW (standalone, no entity folder — rule 6)
  - `organization/company_setup.html`                    — NEW (standalone — rule 6)
- [ ] MOVE the 3 existing designation templates from `templates/hrm/designation/` to
  `templates/hrm/organization/designation/` (new path under the `organization` sub-module folder).
- [ ] UPDATE all render() / crud_* template= arguments in `apps/hrm/views.py` for the designation
  views from `"hrm/designation/list.html"` → `"hrm/organization/designation/list.html"` etc.
- [ ] DELETE the old `templates/hrm/designation/` folder once the three files have been moved
  (the folder `designation` would otherwise collide with the CLAUDE.md banned flat shape).
- [ ] Note for close-out: the HRM SKILL.md must be updated to rename 3.2's template folder
  `designation` → `organization` and to document the new entities.

---

## 1. Models

### 1a. NEW `hrm.JobGrade` — orderable grade catalog [prefix: JG- optional, TenantOwned]

Driver features: Personio (grade integer + level label), Keka (pay grade), Darwinbox (bands +
grades), ADP (job grade), Workday (management level).

- [ ] Add `JobGrade(TenantOwned)` to `apps/hrm/models.py`:
  - `tenant`       — FK → `"core.Tenant"` (inherited via `TenantOwned`)
  - `name`         — `CharField(max_length=50)` — e.g. "G1", "L3", "IC5", "Senior"
  - `level_order`  — `PositiveSmallIntegerField()` — integer rank for hierarchy display,
                     sequencing, and org-chart level-coloring (Personio level within track;
                     Workday management level)
  - `description`  — `TextField(blank=True)` — narrative definition of what this grade means
  - `is_active`    — `BooleanField(default=True)`
  - `Meta.ordering = ["level_order", "name"]`
  - `unique_together = ("tenant", "name")`
  - DB index: `("tenant", "is_active")` name `"hrm_jg_tenant_active_idx"`
  - DB index: `("tenant", "level_order")` name `"hrm_jg_tenant_order_idx"`
  - `__str__`: `f"{self.name} (L{self.level_order})"` if level_order else `self.name`
  - No `clean()` needed (no cross-field constraint)
  - **Reuses**: `core.Tenant` only. Does NOT subclass `TenantNumbered` — grades are small
    catalogs identified by name, not by auto-number.

### 1b. ENHANCE `hrm.Designation` — add fields via migration (no destructive change)

Driver features: Personio (min/mid/max salary band), Keka (pay grade FK), Darwinbox (job
description + headcount), Workday (job profile description), ADP (position description + FTE).

- [ ] Add the following nullable/blank fields to the **existing** `Designation` model:
  - `job_grade`          — `ForeignKey("hrm.JobGrade", on_delete=SET_NULL, null=True, blank=True,
                           related_name="designations")` — replaces free-text `grade` as the
                           primary grade reference; old `grade` CharField is **kept** for
                           backwards-compat and as a free-text fallback
  - `description`        — `TextField(blank=True)` — job duties / purpose statement (Workday job
                           profile, Darwinbox, ADP position description)
  - `requirements`       — `TextField(blank=True)` — qualifications / competencies (Darwinbox,
                           Personio career frameworks)
  - `mid_salary`         — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`
                           — band midpoint alongside existing `min_salary`/`max_salary` (Personio
                           min/mid/max salary band)
  - `budgeted_headcount` — `PositiveSmallIntegerField(null=True, blank=True)` — approved position
                           slots (Darwinbox "total roles to be recruited", ADP position management,
                           Oracle HCM FTE budget)
- [ ] Update `Designation.clean()` to also validate: if `mid_salary` is set and `min_salary` is
  set, `mid_salary >= min_salary`; if `mid_salary` is set and `max_salary` is set,
  `mid_salary <= max_salary`.
- [ ] Update `Designation.__str__` to prefer `job_grade.name` over free-text `grade` when
  `job_grade_id` is set: `f"{self.name} ({self.job_grade.name})"` else fall back to the existing
  `f"{self.name} ({self.grade})"` / `self.name` logic.
- [ ] Add DB index `("tenant", "job_grade")` name `"hrm_desig_tenant_jg_idx"` to `Designation.Meta`.

### 1c. NEW `hrm.DepartmentProfile` — HRM companion to `core.OrgUnit(kind="department")` [TenantOwned]

Driver features: Keka (explicit dept-head assignment used in approval chains), SAP SuccessFactors
(dept code, is_active), Darwinbox (dept code), Oracle HCM (cost_center mapping), BambooHR (dept head).

- [ ] Add `DepartmentProfile(TenantOwned)` to `apps/hrm/models.py`:
  - `tenant`       — FK → `"core.Tenant"` (inherited via `TenantOwned`)
  - `org_unit`     — `OneToOneField("core.OrgUnit", on_delete=CASCADE,
                     related_name="department_profile")` — the canonical department node; name,
                     parent, and hierarchy all live on OrgUnit — no duplication here
  - `code`         — `CharField(max_length=20, blank=True)` — short mnemonic e.g. "ENG", "FIN";
                     used in payroll splits and reports (ADP, SAP SuccessFactors dept codes)
  - `description`  — `TextField(blank=True)`
  - `head`         — `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True,
                     related_name="headed_departments")` — the department head; drives future
                     approval chains in leave/expense (Keka's core differentiator)
  - `cost_center`  — `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True,
                     related_name="department_cost_mappings",
                     limit_choices_to={"kind": "cost_center"})` — maps payroll spend to a cost
                     center (SAP SuccessFactors, Oracle HCM, ADP)
  - `is_active`    — `BooleanField(default=True)` — soft-deactivate without deleting OrgUnit
                     (Keka, Darwinbox dept active/inactive toggle)
  - `Meta.ordering = ["org_unit__name"]`
  - `unique_together = ("tenant", "org_unit")`
  - DB index: `("tenant", "is_active")` name `"hrm_dp_tenant_active_idx"`
  - DB index: `("tenant", "head")` name `"hrm_dp_tenant_head_idx"`
  - `__str__`: `f"{self.org_unit.name} ({self.code})"` if code else `self.org_unit.name`
  - `clean()`: validate `self.org_unit.kind == "department"` (raise ValidationError if a non-
    department OrgUnit is linked); validate `self.org_unit.tenant_id == self.tenant_id` (cross-
    tenant IDOR guard).
  - **Reuses**: `core.OrgUnit` (the department node AND the cost_center node),
    `hrm.EmployeeProfile` (the head). Never stores `name` or `parent` — reads them from OrgUnit.

### 1d. NEW `hrm.CostCenterProfile` — HRM companion to `core.OrgUnit(kind="cost_center")` [TenantOwned]

Driver features: SAP SuccessFactors (cost center code + budget), Oracle HCM (owner), Keka (budget
annual), Fynth HRMS (owner + budget), ADP (cost center codes as validation tables).

- [ ] Add `CostCenterProfile(TenantOwned)` to `apps/hrm/models.py`:
  - `tenant`         — FK → `"core.Tenant"` (inherited via `TenantOwned`)
  - `org_unit`       — `OneToOneField("core.OrgUnit", on_delete=CASCADE,
                       related_name="cost_center_profile")` — the canonical cost_center node;
                       name, parent, and hierarchy all live on OrgUnit
  - `code`           — `CharField(max_length=20, blank=True)` — alphanumeric code used in payroll
                       allocation and GL reporting (ADP dept codes, SAP SuccessFactors CC codes)
  - `description`    — `TextField(blank=True)`
  - `owner`          — `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True,
                       blank=True, related_name="owned_cost_centers")` — budget owner / cost
                       center manager (Oracle HCM, SAP SuccessFactors, Keka)
  - `budget_annual`  — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` —
                       approved annual personnel budget (Keka, Personio cost planning, SAP)
  - `budget_year`    — `PositiveSmallIntegerField(null=True, blank=True)` — fiscal year the budget
                       applies to
  - `is_active`      — `BooleanField(default=True)`
  - `Meta.ordering = ["org_unit__name"]`
  - `unique_together = ("tenant", "org_unit")`
  - DB index: `("tenant", "is_active")` name `"hrm_cc_tenant_active_idx"`
  - DB index: `("tenant", "owner")` name `"hrm_cc_tenant_owner_idx"`
  - `__str__`: `f"{self.org_unit.name} ({self.code})"` if code else `self.org_unit.name`
  - `clean()`: validate `self.org_unit.kind == "cost_center"` (raise ValidationError if non-CC
    OrgUnit is linked); validate `self.org_unit.tenant_id == self.tenant_id` (cross-tenant guard).
  - **Reuses**: `core.OrgUnit` (the CC node and its parent self-FK for roll-up hierarchy),
    `hrm.EmployeeProfile` (the owner). Does NOT store name or parent.

---

## 2. Migration

- [ ] Run `python manage.py makemigrations hrm` — expect ONE migration file covering:
  - New model `JobGrade`
  - New fields on `Designation` (`job_grade`, `description`, `requirements`, `mid_salary`,
    `budgeted_headcount`) — all nullable/blank so zero data loss
  - New model `DepartmentProfile`
  - New model `CostCenterProfile`
  - New indexes on `Designation` (`hrm_desig_tenant_jg_idx`)
- [ ] Run `python manage.py migrate` — verify it applies cleanly.
- [ ] NO data migration needed: old `Designation.grade` CharField is kept; `job_grade` FK starts
  null and is linked by the seeder / manually by HR.

---

## 3. Backend — `apps/hrm/`

### 3a. forms.py — new and updated ModelForms
(All forms receive `tenant` kwarg via `__init__` and filter FK querysets to that tenant.)

- [ ] `JobGradeForm(ModelForm)` — fields: `name`, `level_order`, `description`, `is_active`.
  Exclude: `tenant` (set by view).

- [ ] Update `DesignationForm(ModelForm)` — add fields: `job_grade`, `description`, `requirements`,
  `mid_salary`, `budgeted_headcount`. Filter `job_grade` queryset to
  `JobGrade.objects.filter(tenant=tenant, is_active=True).order_by("level_order", "name")`.
  Existing fields unchanged.

- [ ] `DepartmentProfileForm(ModelForm)` — fields: `org_unit`, `code`, `description`, `head`,
  `cost_center`, `is_active`.
  - Filter `org_unit` queryset: `OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("name")`.
  - Filter `head` queryset: `EmployeeProfile.objects.filter(tenant=tenant).select_related("party").order_by("party__name")`.
  - Filter `cost_center` queryset: `OrgUnit.objects.filter(tenant=tenant, kind="cost_center").order_by("name")`.
  - Exclude: `tenant` (set by view).

- [ ] `CostCenterProfileForm(ModelForm)` — fields: `org_unit`, `code`, `description`, `owner`,
  `budget_annual`, `budget_year`, `is_active`.
  - Filter `org_unit` queryset: `OrgUnit.objects.filter(tenant=tenant, kind="cost_center").order_by("name")`.
  - Filter `owner` queryset: `EmployeeProfile.objects.filter(tenant=tenant).select_related("party").order_by("party__name")`.
  - Exclude: `tenant` (set by view).

### 3b. views.py — new views + updated designation views

All views: `@login_required`, tenant-scoped (`tenant=request.tenant`), use `crud_list` /
`crud_create` / `crud_edit` / `crud_delete` helpers where applicable.

**Update existing designation views (template path change + new filter context):**

- [ ] `designation_list`: update template path to `"hrm/organization/designation/list.html"`;
  add `job_grades` to `extra_context` for filter dropdown:
  `"job_grades": JobGrade.objects.filter(tenant=request.tenant, is_active=True).order_by("level_order")`;
  add filter tuple `("job_grade", "job_grade_id", True)` to `filters=`.
  Search fields: keep `["name", "grade", "department__name"]`, add `"job_grade__name"`.
  Select-related: add `"job_grade"`.

- [ ] `designation_create`: update template to `"hrm/organization/designation/form.html"`.

- [ ] `designation_detail`: update template to `"hrm/organization/designation/detail.html"`;
  add `job_grade` display, `description`, `requirements`, `mid_salary`, `budgeted_headcount`,
  `filled_headcount` (annotated count of active employees on this designation) to context.

- [ ] `designation_edit`: update template to `"hrm/organization/designation/form.html"`.

- [ ] `designation_delete`: no path change (POST-only, no template); keep existing guard logic.

**New JobGrade views:**

- [ ] `jobgrade_list(request)` — `crud_list(...)`:
  - QS: `JobGrade.objects.filter(tenant=request.tenant).order_by("level_order", "name")`
    `.annotate(designation_count=Count("designations"))`
  - Template: `"hrm/organization/jobgrade/list.html"`
  - `search_fields=["name", "description"]`
  - `filters=[("is_active", "is_active", False)]`
  - `extra_context={}` (no FK filter needed for this simple catalog)

- [ ] `jobgrade_create(request)` — `crud_create(...)` with `JobGradeForm`,
  template `"hrm/organization/jobgrade/form.html"`, `success_url="hrm:jobgrade_list"`.

- [ ] `jobgrade_detail(request, pk)` — `get_object_or_404` + render
  `"hrm/organization/jobgrade/detail.html"`:
  - context: `obj`, `designations` (Designation.objects.filter(tenant, job_grade=obj)
    .select_related("department")[:50]).

- [ ] `jobgrade_edit(request, pk)` — `crud_edit(...)` with `JobGradeForm`,
  template `"hrm/organization/jobgrade/form.html"`, `success_url="hrm:jobgrade_list"`.

- [ ] `jobgrade_delete(request, pk)` — `@require_POST`; guard: if
  `Designation.objects.filter(tenant=request.tenant, job_grade=obj).exists()` → error redirect
  to detail with message "Cannot delete a grade assigned to designations. Deactivate it instead.";
  else `write_audit_log` + delete + redirect to list.

**New DepartmentProfile views (URL entity name: "department"):**

- [ ] `department_list(request)` — `crud_list(...)`:
  - QS: `DepartmentProfile.objects.filter(tenant=request.tenant)`
    `.select_related("org_unit", "head__party", "cost_center")`
    `.annotate(employee_count=Count("org_unit__employments"))` — NOTE: count is from
    `core.Employment.org_unit` FK (Employment.related_name="employments").
  - Template: `"hrm/organization/department/list.html"`
  - `search_fields=["org_unit__name", "code", "description"]`
  - `filters=[("is_active", "is_active", False)]`
  - `extra_context={}` (no additional FK filter dropdowns required at this level)

- [ ] `department_create(request)` — `crud_create(...)` with `DepartmentProfileForm`,
  template `"hrm/organization/department/form.html"`, `success_url="hrm:department_list"`.

- [ ] `department_detail(request, pk)` — render `"hrm/organization/department/detail.html"`:
  - context: `obj` (select_related org_unit + head__party + cost_center),
    `designations` (Designation.objects.filter(tenant, department=obj.org_unit)[:50]),
    `employees` (EmployeeProfile.objects.filter(tenant, employment__org_unit=obj.org_unit)
    .select_related("party")[:50]).

- [ ] `department_edit(request, pk)` — `crud_edit(...)` with `DepartmentProfileForm`,
  template `"hrm/organization/department/form.html"`, `success_url="hrm:department_list"`.

- [ ] `department_delete(request, pk)` — `@require_POST`; guard: if active employees in
  `org_unit` → error message "Cannot delete a department with active employees."; else
  `write_audit_log` + delete (DepartmentProfile only; OrgUnit is unaffected) + redirect to list.

**New CostCenterProfile views (URL entity name: "costcenter"):**

- [ ] `costcenter_list(request)` — `crud_list(...)`:
  - QS: `CostCenterProfile.objects.filter(tenant=request.tenant)`
    `.select_related("org_unit", "owner__party")`
  - Template: `"hrm/organization/costcenter/list.html"`
  - `search_fields=["org_unit__name", "code", "description"]`
  - `filters=[("is_active", "is_active", False)]`
  - `extra_context={}` (no FK filter dropdown needed)

- [ ] `costcenter_create(request)` — `crud_create(...)` with `CostCenterProfileForm`,
  template `"hrm/organization/costcenter/form.html"`, `success_url="hrm:costcenter_list"`.

- [ ] `costcenter_detail(request, pk)` — render `"hrm/organization/costcenter/detail.html"`:
  - context: `obj` (select_related org_unit + owner__party), `mapped_departments`
    (DepartmentProfile.objects.filter(tenant, cost_center=obj.org_unit).select_related("org_unit")[:50]).

- [ ] `costcenter_edit(request, pk)` — `crud_edit(...)` with `CostCenterProfileForm`,
  template `"hrm/organization/costcenter/form.html"`, `success_url="hrm:costcenter_list"`.

- [ ] `costcenter_delete(request, pk)` — `@require_POST`; guard: if any
  `DepartmentProfile.objects.filter(tenant, cost_center=obj.org_unit).exists()` → error; else
  `write_audit_log` + delete + redirect to list.

**New derived views (no model):**

- [ ] `org_chart(request)` — `@login_required`:
  - Query `EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party",
    "employment__org_unit", "employment__manager", "designation__job_grade")`
  - Build Python dict tree keyed by `employment.manager_id` (root = manager_id is None).
  - Render `"hrm/organization/org_chart.html"` with context:
    `{"employees": employees_qs, "org_units": OrgUnit.objects.filter(tenant=request.tenant),
    "view_mode": request.GET.get("view", "reporting")}` — `view_mode` toggles
    reporting-line vs. department-grouped display.

- [ ] `company_setup(request)` — `@login_required`:
  - Read `core.OrgUnit.objects.filter(tenant=request.tenant, kind="company").first()` for
    company name/parent info.
  - Read `tenants.BrandingSetting` for logo/colors — import from `apps.tenants.models`.
  - Render `"hrm/organization/company_setup.html"` with context:
    `{"company_unit": company_unit, "branding": branding_obj}`.
  - This is a **read-only** page in this pass (branding edits stay in the Tenants module at
    `tenants:brandingsetting_list`; a link to that page is shown).

### 3c. urls.py — new URL patterns

- [ ] Add to `apps/hrm/urls.py` inside `app_name = "hrm"`:

  ```python
  # Job Grades (3.2)
  path("job-grades/",                  views.jobgrade_list,   name="jobgrade_list"),
  path("job-grades/add/",              views.jobgrade_create, name="jobgrade_create"),
  path("job-grades/<int:pk>/",         views.jobgrade_detail, name="jobgrade_detail"),
  path("job-grades/<int:pk>/edit/",    views.jobgrade_edit,   name="jobgrade_edit"),
  path("job-grades/<int:pk>/delete/",  views.jobgrade_delete, name="jobgrade_delete"),

  # Department Profiles (3.2)
  path("departments/",                  views.department_list,   name="department_list"),
  path("departments/add/",              views.department_create, name="department_create"),
  path("departments/<int:pk>/",         views.department_detail, name="department_detail"),
  path("departments/<int:pk>/edit/",    views.department_edit,   name="department_edit"),
  path("departments/<int:pk>/delete/",  views.department_delete, name="department_delete"),

  # Cost Center Profiles (3.2)
  path("cost-centers/",                  views.costcenter_list,   name="costcenter_list"),
  path("cost-centers/add/",              views.costcenter_create, name="costcenter_create"),
  path("cost-centers/<int:pk>/",         views.costcenter_detail, name="costcenter_detail"),
  path("cost-centers/<int:pk>/edit/",    views.costcenter_edit,   name="costcenter_edit"),
  path("cost-centers/<int:pk>/delete/",  views.costcenter_delete, name="costcenter_delete"),

  # Org Chart & Company Setup (3.2 — derived, no model)
  path("org-chart/",      views.org_chart,      name="org_chart"),
  path("company-setup/",  views.company_setup,  name="company_setup"),
  ```

### 3d. admin.py

- [ ] Register `JobGrade`, `DepartmentProfile`, `CostCenterProfile` in `apps/hrm/admin.py`.
  List-display for each: `tenant`, `name/org_unit`, `is_active`.
  Add `job_grade` to `Designation` admin inline if an `EmployeeProfileInline` exists.

### 3e. Seeder — extend `apps/hrm/management/commands/seed_hrm.py`

The seeder already creates `Designation`, `OrgUnit` (dept), and `EmployeeProfile` rows.
Extend it to seed the new models **idempotently** after those rows are created.

- [ ] Add `JobGrade` and `DepartmentProfile` and `CostCenterProfile` to the imports.

- [ ] Define a `JOB_GRADES` constant at module level:
  ```python
  JOB_GRADES = [
      # (name, level_order, description)
      ("G1 — Junior",    1, "Entry-level individual contributor"),
      ("G2 — Mid",       2, "Developing individual contributor"),
      ("G3 — Senior",    3, "Senior individual contributor"),
      ("M1 — Manager",   4, "First-level people manager"),
      ("M2 — Director",  5, "Department or function director"),
  ]
  ```

- [ ] In `_seed_tenant()`, after Designations are created, call a new helper
  `_seed_org_structure(tenant, designations)`:
  - **JobGrades** (idempotent via `get_or_create(tenant=tenant, name=name, defaults=...)`):
    Create the 5 grade rows. Collect them into a list `grades`.
  - **Link Designations to JobGrades**: update each Designation's `job_grade` if it is currently
    null: `Software Engineer` → G2, `Senior Engineer` → G3, `Engineering Manager` → M1. Use
    `Designation.objects.filter(tenant=tenant, name=name, job_grade=None).update(job_grade=grade)`.
    Also set `mid_salary` and `budgeted_headcount` via the same conditional update:
    `Software Engineer`: mid=75000, headcount=3; `Senior Engineer`: mid=110000, headcount=2;
    `Engineering Manager`: mid=155000, headcount=1.
  - **DepartmentProfiles** — iterate `OrgUnit.objects.filter(tenant=tenant, kind="department")`;
    for each, `get_or_create(tenant=tenant, org_unit=unit, defaults={"code": unit.name[:3].upper(),
    "is_active": True, "head": employees[0] if employees else None})`.
    Skip if `DepartmentProfile.objects.filter(tenant=tenant).exists()` (already seeded).
  - **CostCenterProfiles** — iterate `OrgUnit.objects.filter(tenant=tenant, kind="cost_center")`;
    for each, `get_or_create(tenant=tenant, org_unit=unit, defaults={"code": unit.name[:4].upper(),
    "is_active": True, "budget_annual": Decimal("500000"), "budget_year": today.year,
    "owner": employees[1] if len(employees) > 1 else employees[0] if employees else None})`.
    Skip if `CostCenterProfile.objects.filter(tenant=tenant).exists()`.

- [ ] Add `JobGrade`, `DepartmentProfile`, `CostCenterProfile` to the `--flush` deletion cascade
  (before `Designation`, since grades are referenced by designations):
  `CostCenterProfile, DepartmentProfile` before `EmployeeProfile`; `JobGrade` before `Designation`.

- [ ] Idempotency guard: wrap each new model's seed block with an `if not
  ModelClass.objects.filter(tenant=tenant).exists():` check (or use `get_or_create` throughout —
  consistent with the existing pattern).

---

## 4. Templates (`templates/hrm/organization/`)

All templates: `{% extends "base.html" %}`, use Tailwind design system, Lucide icons.
Actions column on every list: View (eye), Edit (pencil), Delete (trash — POST form +
`onclick="return confirm(...)"` + `{% csrf_token %}`). Detail pages: Edit button + Delete form
in sidebar + Back to List link. Filter bar reflects `request.GET` state.

### Moved templates (designation — path change only, content polished):

- [ ] `templates/hrm/organization/designation/list.html` — MOVED + updated:
  - New filter: Job Grade dropdown (`{% for g in job_grades %}`, compare with
    `request.GET.job_grade == g.pk|stringformat:"d"`).
  - Show `job_grade.name` column (if set) else `grade` fallback.
  - Show `budgeted_headcount` column.

- [ ] `templates/hrm/organization/designation/detail.html` — MOVED + updated:
  - Show `job_grade` (linked to grade detail if set, else free-text `grade`).
  - Show `description`, `requirements` (collapsible or full-width sections).
  - Show salary band: min / mid / max in a 3-column row.
  - Show `budgeted_headcount` vs. `employee_count` (filled slots indicator).

- [ ] `templates/hrm/organization/designation/form.html` — MOVED + updated:
  - Add fields: `job_grade` (select), `description` (textarea), `requirements` (textarea),
    `mid_salary` (number), `budgeted_headcount` (number).
  - Keep existing fields in logical order: name → job_grade → department → salary band
    (min/mid/max) → is_active → description → requirements → budgeted_headcount.

### New templates (Job Grades):

- [ ] `templates/hrm/organization/jobgrade/list.html`:
  - Columns: Level Order, Name, Description (truncated), Active, # Designations, Actions.
  - Filter: is_active (Active / Inactive / All). Search by name/description.
  - Empty state with "Add Job Grade" CTA.

- [ ] `templates/hrm/organization/jobgrade/detail.html`:
  - Header: grade name + level badge. Sections: Details card (level_order, description,
    is_active), Linked Designations table.
  - Sidebar actions: Edit, Delete (guarded if designations exist — show disabled state),
    Back to Job Grades.

- [ ] `templates/hrm/organization/jobgrade/form.html`:
  - Fields: `name`, `level_order`, `description`, `is_active`.
  - Help text under `level_order`: "Lower numbers appear higher in seniority (1 = most junior)."

### New templates (Departments):

- [ ] `templates/hrm/organization/department/list.html`:
  - Columns: Name (from `obj.org_unit.name`), Code, Parent (from `obj.org_unit.parent.name`),
    Head, Cost Center, Active, # Employees, Actions.
  - Filter: is_active. Search: name, code.
  - Empty state: explain that departments are OrgUnit nodes — link to core OrgUnit list to create
    departments first, then return here to enrich them.

- [ ] `templates/hrm/organization/department/detail.html`:
  - Header: department name + code badge. Sections: OrgUnit info card (name, parent, kind — from
    `obj.org_unit`), Department Profile card (code, head, cost_center, is_active, description),
    Designations in this department, Employees in this department.
  - Sidebar: Edit, Delete, Back to Departments.

- [ ] `templates/hrm/organization/department/form.html`:
  - Fields: `org_unit` (select — filtered to kind=department), `code`, `description`, `head`
    (select — filtered employees), `cost_center` (select — filtered OrgUnit kind=cost_center),
    `is_active`.
  - Help text under `org_unit`: "Select a Department from the Organization Units list. To create
    a new department, add it in Organization Units first."

### New templates (Cost Centers):

- [ ] `templates/hrm/organization/costcenter/list.html`:
  - Columns: Name (from `obj.org_unit.name`), Code, Parent, Owner, Budget Year, Annual Budget,
    Active, Actions.
  - Filter: is_active. Search: name, code.
  - Empty state: link to core OrgUnit list to create cost_center nodes first.

- [ ] `templates/hrm/organization/costcenter/detail.html`:
  - Header: CC name + code badge. Sections: OrgUnit info card, Cost Center Profile card (code,
    owner, budget_annual, budget_year, is_active, description), Mapped Departments table.
  - Sidebar: Edit, Delete, Back to Cost Centers.

- [ ] `templates/hrm/organization/costcenter/form.html`:
  - Fields: `org_unit` (select — kind=cost_center), `code`, `description`, `owner` (employee
    select), `budget_annual` (number), `budget_year` (number), `is_active`.

### New standalone templates:

- [ ] `templates/hrm/organization/org_chart.html`:
  - Toggle bar: "Reporting Lines" | "By Department" (sets `?view=reporting` or `?view=department`
    in GET, handled in view).
  - Reporting-lines mode: recursive Tailwind card tree built from the Python dict tree passed in
    context (`employees` keyed by manager_id). Each employee card: photo placeholder / initials
    avatar, name, designation, department. Direct reports indented with a connecting line.
  - Department mode: group cards by `employment.org_unit.name`. Each group is a collapsible
    section. Employee cards within show name + designation.
  - Empty state: "No employees found — add employees in Employee Management."
  - No JS framework required; pure Tailwind + HTMX if collapse/expand is desired (progressive
    enhancement only).

- [ ] `templates/hrm/organization/company_setup.html`:
  - Read-only page. Sections: Company Info (from `core.OrgUnit` kind=company — name, parent
    hierarchy displayed as breadcrumb), Branding (logo preview, primary_color, accent_color from
    `tenants.BrandingSetting`), Links (button → `tenants:brandingsetting_list` to edit branding,
    button → `core:orgunit_list` to manage org units).
  - If no company OrgUnit exists: info banner "No company unit found — create one in
    Organization Units."

---

## 5. Wire-up

### 5a. `apps/core/navigation.py` — replace `LIVE_LINKS["3.2"]`

- [ ] Replace the existing `"3.2"` entry with all five NavERP.md bullets plus the extra Job
  Grades leaf:

  ```python
  # 3.2 Organizational Structure — rebuilt with full entity set.
  "3.2": {
      "Company Setup": "hrm:company_setup",          # bullet
      "Department Management": "hrm:department_list", # bullet
      "Designation/Job Titles": "hrm:designation_list", # bullet
      "Organization Chart": "hrm:org_chart",          # bullet
      "Cost Centers": "hrm:costcenter_list",          # bullet
      "Job Grades": "hrm:jobgrade_list",              # extra (grade catalog)
  },
  ```

  Exact bullet text must match `NavERP.md` section 3.2 feature bullets character-for-character
  for the sidebar Live/Roadmap logic to activate them.

### 5b. No `config/settings.py` or `config/urls.py` changes needed

`apps.hrm` is already in `INSTALLED_APPS` and `hrm/` is already included in `config/urls.py`.

---

## 6. Verify

- [ ] `python manage.py makemigrations --check` — confirms no unapplied model changes.
- [ ] `python manage.py migrate` — applies cleanly with zero errors.
- [ ] `python manage.py seed_hrm` — first run creates all rows, prints login instructions.
- [ ] `python manage.py seed_hrm` (second run) — prints "already exists" notices; no duplicate
  rows, no IntegrityError (idempotency check).
- [ ] `python manage.py check` — zero issues.
- [ ] Smoke-test all new `hrm:*` 3.2 routes as a tenant admin (log in as `admin_acme` or
  `admin_globex`):
  - [ ] `hrm:company_setup` → 200
  - [ ] `hrm:department_list` → 200, shows seeded DepartmentProfiles
  - [ ] `hrm:department_create` → 200
  - [ ] `hrm:department_detail` + edit + delete → 200/302
  - [ ] `hrm:designation_list` → 200 (now at new template path; shows `job_grade` column)
  - [ ] `hrm:designation_create` + edit + detail → 200 (new fields visible)
  - [ ] `hrm:org_chart` → 200 (shows employee tree)
  - [ ] `hrm:costcenter_list` → 200
  - [ ] `hrm:costcenter_create` + edit + detail + delete → 200/302
  - [ ] `hrm:jobgrade_list` → 200, shows 5 seeded grades
  - [ ] `hrm:jobgrade_create` + edit + detail + delete → 200/302
- [ ] Cross-tenant IDOR: GET `hrm:department_detail pk=<other_tenant_row>` → 404.
- [ ] Cross-tenant IDOR: GET `hrm:costcenter_detail pk=<other_tenant_row>` → 404.
- [ ] Cross-tenant IDOR: GET `hrm:jobgrade_detail pk=<other_tenant_row>` → 404.
- [ ] No template-comment leaks: grep for `{#` or `{% comment` in rendered output
  (temp/ smoke sweep).
- [ ] Sidebar: log in as `admin_acme`; verify sub-module 3.2 shows "Company Setup", "Department
  Management", "Designation/Job Titles", "Organization Chart", "Cost Centers", "Job Grades" all
  as **Live** (green dot / linked).
- [ ] Old template paths (`hrm/designation/list.html` etc.) no longer exist — no 500 from stale
  references. Confirm `templates/hrm/designation/` folder is deleted.

---

## 7. Close-out

- [ ] Run `code-reviewer` agent — apply findings, one file per commit.
- [ ] Run `explorer` agent — apply findings, one file per commit.
- [ ] Run `frontend-reviewer` agent — apply findings, one file per commit.
- [ ] Run `performance-reviewer` agent — apply findings, one file per commit.
- [ ] Run `qa-smoke-tester` agent — apply findings, one file per commit.
- [ ] Run `security-reviewer` agent — apply findings, one file per commit.
- [ ] Run `test-writer` agent — apply output, one file per commit.
- [ ] Update HRM SKILL.md (`.claude/skills/hrm/SKILL.md`):
  - Rename 3.2 template folder reference from `designation/` to `organization/`.
  - Add `JobGrade`, `DepartmentProfile`, `CostCenterProfile` to the Models section.
  - Add new URL names to the URLs section.
  - Update LIVE_LINKS sidebar wiring section.
  - Update "Common tasks" section: add "add a new org-structure entity".

---

## Later passes / deferred

- **Job families / tracks** — Personio-style `hrm.JobFamily` + `hrm.JobTrack` tables for career
  laddering. `hrm.JobGrade` + `hrm.Designation.description` lay the groundwork. Revisit at 3.38
  Talent Management.
- **Position management (position slots)** — Workday/ADP "open position" concept (a `hrm.Position`
  table, distinct from the person who fills it, with headcount-control logic). `budgeted_headcount`
  on Designation is the lightweight proxy for now.
- **Effective-dated org changes** — Workday org studio / ChartHop scenario planning (historical
  OrgUnit membership with from/to dates). Far beyond a single Django pass; deferred to a dedicated
  workforce-planning sub-module.
- **Location / work-site registry** — `hrm.WorkLocation` companion to `core.OrgUnit(kind="branch")`
  with address + timezone + is_remote. Useful but not required for the 5 3.2 NavERP.md bullets;
  deferred to 3.1 Employee Management or a future location sub-module.
- **Budget tracking vs. actuals** — comparing `CostCenterProfile.budget_annual` against actual
  payroll spend requires the Accounting module (Module 2 → PayrollRun → GL). Deferred until
  Accounting is fully built.
- **Org-chart export (PDF/PNG)** — standard in ChartHop, BambooHR, OrgVue. Deferred; browser
  print covers the immediate need.
- **Matrix / cross-functional reporting** — Workday matrix orgs, Zoho cross-entity reporting.
  `core.Employment.manager` is single-parent; a matrix structure needs an M2M join table.
  Deferred to a future org-design sub-module.
- **CompanyProfile** — if registered name, tax ID, and industry need to be stored separately from
  `tenants.BrandingSetting` (which covers logo/colors), a `hrm.CompanyProfile` OneToOne companion
  to `core.OrgUnit(kind="company")` can be added in a later pass. Not in scope now because
  `BrandingSetting` already satisfies the Company Setup bullet's branding requirement.

---

## Review notes (build complete — 2026-06-26)

**Delivered (rebuild of HRM 3.2 Organizational Structure):** `JobGrade` + `DepartmentProfile` + `CostCenterProfile`
models, enhanced `Designation` (job_grade FK, description/requirements, mid_salary, budgeted_headcount, band
validation), derived `org_chart` (reporting-line/by-department) + read-only `company_setup` views, full CRUD with
delete guards, templates moved/added under `templates/hrm/organization/`, `LIVE_LINKS["3.2"]` lighting all 5
NavERP.md bullets + a Job Grades leaf, idempotent `_seed_org_structure` seeder, migrations 0007/0008. Verified:
`manage.py check` clean, seeder idempotent, smoke sweep of every 3.2 route 200/302, cross-tenant IDOR → 404, no
template-comment leaks. New test module `apps/hrm/tests/test_org_structure.py` (119 tests; HRM suite 728, project
1,790 — all green).

**Review agents run (Module Creation Sequence):** code-reviewer → explorer → frontend-reviewer →
performance-reviewer → qa-smoke-tester → security-reviewer → test-writer, each applied + committed.
- *code-reviewer:* iterative DFS in org_chart (no RecursionError), exclude terminated employees, active-only
  department headcount, cost_center tenant guard, clarified clean() docstrings, simplified `__str__`.
- *frontend-reviewer:* `.stat-grid` (not invented `.stat-cards`), branding color swatches (not dotted badges),
  org-chart `--border`/`--text-muted` vars + overflow-x, `overflow-wrap` on descriptions, guarded job-grade delete.
- *performance-reviewer:* killed costcenter_detail `head__party` N+1, collapsed detail count+slice into one
  annotate, capped org_chart at 500, added `(tenant, cost_center)` index (migration 0008).
- *explorer / qa-smoke-tester:* no changes needed — all route/template/context chains consistent, 44/44 smoke PASS.

**Flagged app-wide (NOT changed — L18):** the security review suggested gating 3.2 *write* views with
`@tenant_admin_required`. Left at `@login_required` to stay consistent with the rest of HRM's master-data CRUD
(leave types, shifts, holidays, designation are all `@login_required`; only lifecycle/approval *actions* are
tenant-admin-gated). Whether HR master-data config (incl. department-head/cost-center-budget) should be
tenant-admin-gated is an **app-wide policy decision** worth a dedicated pass, not a one-sub-module fork.

**Deferred (see plan above):** job families/tracks, position slots, effective-dated reorg, work-site registry,
budget-vs-actuals (needs Accounting), org-chart export, matrix reporting, a `CompanyProfile` companion.

---

# Module 3 Completion — HRM Sub-module 3.1: Employee Management (hrm) — plan from research-hrm-employee.md  (2026-06-26)

> **Context:** Completion pass on sub-module 3.1 in the existing `apps/hrm` app (NOT a new app). The
> Employee Directory / Profile / Employment Details views are already built and passing (see Module 3
> HRM build outcome in the prior todo history). This plan closes two **priority gaps** — Document
> Management and Employee Lifecycle — and enriches `EmployeeProfile` with 15 missing personal/contact/
> compliance fields. Two new models are added to `apps/hrm/models.py`. The app is already wired into
> `config/settings.py`, `config/urls.py`, and `navigation.py`; only `LIVE_LINKS["3.1"]` needs two
> new bullet entries. No new app; no new `apps.py`. All models follow the exact same
> `TenantOwned`/`TenantNumbered` abstract bases already in `apps/hrm/models.py`.

---

## 1. `EmployeeProfile` field additions (edit existing model — NO new model)

These 15 fields are missing from `EmployeeProfile` per the competitive research. All are nullable/
blank/defaulted so the incremental migration is non-destructive (existing rows unaffected).

- [ ] **`marital_status`** — `CharField(max_length=20, blank=True)` with class-level constant
  `MARITAL_STATUS_CHOICES`:
  `("single","Single"), ("married","Married"), ("divorced","Divorced"), ("widowed","Widowed"),
  ("other","Other")`. Add alongside existing `EMPLOYEE_TYPE_CHOICES`/`GENDER_CHOICES`/
  `BLOOD_GROUP_CHOICES` on `EmployeeProfile`. Drivers: Workday, SAP SuccessFactors, greytHR, HiBob,
  Zoho People — statutory benefits/tax compliance.

- [ ] **`work_email`** — `EmailField(blank=True)`. Professional email distinct from `personal_email`
  (which is already on the model). Drivers: Workday, HiBob, Rippling, BambooHR — required for
  active-directory provisioning and HR communications.

- [ ] **`work_location`** — `CharField(max_length=255, blank=True)`. Office/site/remote assignment
  (free-text in v1; upgrade to FK→`core.OrgUnit(kind=branch)` deferred). Drivers: HiBob, greytHR,
  Keka, Rippling — mandatory field in all modern HRIS for location-based payroll and headcount.

- [ ] **`notice_period_days`** — `PositiveSmallIntegerField(null=True, blank=True)`. Contract-default
  notice period in days. Note: `SeparationCase` already carries its own `notice_period_days` (the
  case-specific override); this field is the **profile-level default** that the SeparationCase form
  should pre-fill from. Drivers: greytHR, HiBob, Personio.

- [ ] **`national_id`** — `CharField(max_length=100, blank=True)`. The national identifier value
  (Aadhaar no., SSN, NRIC, NID, PAN, etc.). Stored directly on the profile for quick search/filter
  without joining the document vault. Drivers: Workday Government IDs, greytHR Aadhaar/PAN, HiBob
  Identification.

- [ ] **`national_id_type`** — `CharField(max_length=50, blank=True)`. The label for `national_id`
  (e.g. `"Aadhaar"`, `"SSN"`, `"NRIC"`, `"PAN"`). Paired with `national_id`.

- [ ] **`passport_number`** — `CharField(max_length=50, blank=True)`. Passport number for quick access
  (full passport document lives in `EmployeeDocument`). Drivers: greytHR passport page, Workday
  immigration, Keka document types.

- [ ] **`passport_expiry`** — `DateField(null=True, blank=True)`. Quick expiry reference on the profile.
  Drivers: greytHR "Valid Till", Workday expiration date.

- [ ] **`father_name`** — `CharField(max_length=255, blank=True)`. Statutory field for PF, ESI, and
  gratuity nomination in South Asia and GCC. Drivers: greytHR, Darwinbox, Keka.

- [ ] **`spouse_name`** — `CharField(max_length=255, blank=True)`. Family details for dependents/
  nominations. Drivers: greytHR family details section.

- [ ] **`current_address`** — `TextField(blank=True)`. Present/current residential address (freeform
  in v1; upgrade to a normalized `EmployeeAddress` table deferred). Drivers: greytHR "Present
  Address", HiBob address table, Gusto home address.

- [ ] **`permanent_address`** — `TextField(blank=True)`. Permanent/hometown address (distinct from
  current address — required for PF/ESI correspondence). Drivers: greytHR "Permanent Address",
  Workday mailing address.

- [ ] **`emergency_contact_2_name`** — `CharField(max_length=255, blank=True)`. Second emergency
  contact name. Drivers: almost all 10 surveyed products support ≥2 emergency contacts.

- [ ] **`emergency_contact_2_phone`** — `CharField(max_length=30, blank=True)`.

- [ ] **`emergency_contact_2_relation`** — `CharField(max_length=100, blank=True)`.

- [ ] Add all 15 new fields to `EmployeeProfileForm.fields` in `apps/hrm/forms.py`. None are
  computed/workflow fields so all belong in the form.

- [ ] `makemigrations hrm` for the profile field additions (one migration, non-destructive).

---

## 2. `EmployeeDocument` model [EDOC-] (new — add to `apps/hrm/models.py`)

Personnel-file document vault. One row per document per employee. Distinct from `OnboardingDocument`
(program e-sign) and `core.Document` (generic attachment). Inherits `TenantNumbered`; `NUMBER_PREFIX = "EDOC"`.

- [ ] **Fields:**
  - `employee` — `FK("hrm.EmployeeProfile", CASCADE, related_name="documents")`. NOT `core.Party` —
    all HRM FKs go to `EmployeeProfile`.
  - `document_type` — `CharField(max_length=30)` with `DOCUMENT_TYPE_CHOICES` (19 choices):
    `("national_id","National ID / Aadhaar / NRIC")`,
    `("passport","Passport")`,
    `("driving_license","Driving License")`,
    `("address_proof","Address Proof")`,
    `("visa","Visa")`,
    `("work_permit","Work Permit")`,
    `("degree_certificate","Degree / Diploma Certificate")`,
    `("professional_cert","Professional Certification")`,
    `("appointment_letter","Appointment Letter")`,
    `("employment_contract","Employment Contract")`,
    `("nda","Non-Disclosure Agreement")`,
    `("non_compete","Non-Compete Agreement")`,
    `("tax_form","Tax Form (W-4 / Form 16 / TDS)")`,
    `("bank_proof","Bank Account Proof")`,
    `("pf_nomination","PF / Pension Nomination")`,
    `("medical_cert","Medical / Fitness Certificate")`,
    `("background_check","Background Check Report")`,
    `("experience_certificate","Previous Employment / Experience Letter")`,
    `("other","Other")`.
    Drivers: Workday doc categories, BambooHR, greytHR, Keka, Personio, Darwinbox.
  - `title` — `CharField(max_length=255)`.
  - `document_number` — `CharField(max_length=100, blank=True)`. The alphanumeric ID on the document
    itself (passport no., PAN, license no., visa no.). Drivers: greytHR passport/visa no., Darwinbox.
  - `issuing_authority` — `CharField(max_length=255, blank=True)`. Drivers: greytHR Issue Place,
    Workday immigration.
  - `issuing_country` — `CharField(max_length=100, blank=True)`. Drivers: greytHR Country, Workday.
  - `issued_on` — `DateField(null=True, blank=True)`. Drivers: greytHR issue date, Zoho People.
  - `expires_on` — `DateField(null=True, blank=True)`. null = no expiry. Drivers: greytHR "Valid Till",
    Workday Expiration Date, Keka alerts, Zoho People.
  - `verification_status` — `CharField(max_length=20, editable=False)` with
    `VERIFICATION_STATUS_CHOICES`:
    `("pending","Pending")`, `("verified","Verified")`, `("rejected","Rejected")`.
    Default `"pending"`. **editable=False** — workflow-owned; set only by `mark_verified`/`reject`
    POST actions, never via the form. Drivers: Keka 3-bucket verification, BambooHR, Darwinbox.
  - `verified_by` — `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
    related_name="hrm_verified_documents", editable=False)`. Set by `mark_verified` action only.
  - `verified_at` — `DateTimeField(null=True, blank=True, editable=False)`. Stamped by `mark_verified`.
  - `is_confidential` — `BooleanField(default=False)`. HR-only visibility flag. Drivers: Workday
    restricted doc categories, BambooHR padlock icon, Keka confidential access control.
  - `file` — `FileField(upload_to="hrm/employee_docs/%Y/%m/", null=True, blank=True)`.
  - `notes` — `TextField(blank=True)`.
  **Derived properties (never stored):**
  - `is_expired` — `@property`: `expires_on is not None and expires_on < date.today()`.
  - `is_expiring_soon` — `@property`: `expires_on is not None` and `0 < (expires_on − date.today()).days ≤ 30`.
    Drivers: Keka 60/30/7-day GCC visa alert, Workday auto-alerts.
  **Meta:** `unique_together = ("tenant", "number")`; `ordering = ["-created_at"]`.
  **Indexes:**
  - `(tenant, employee)` — `hrm_edoc_tenant_emp_idx`
  - `(tenant, document_type)` — `hrm_edoc_tenant_type_idx`
  - `(tenant, verification_status)` — `hrm_edoc_tenant_vstatus_idx`
  - `(tenant, expires_on)` — `hrm_edoc_tenant_expiry_idx`
  **`__str__`:** `f"{self.number} · {self.title}"`.

---

## 3. `EmployeeLifecycleEvent` model [ELC-] (new — add to `apps/hrm/models.py`)

Append-only, auditable log of every dated job-change event. One row per event per employee.
Inherits `TenantNumbered`; `NUMBER_PREFIX = "ELC"`. Driven by: Workday Change Job process, SAP
SuccessFactors jobInfo event types + reason codes, BambooHR jobInfo/compensation historical tables,
greytHR position history, HiBob Work/Employment/Lifecycle/Salary tables, Personio Employee History.

- [ ] **Add module-level constant** `LIFECYCLE_EVENT_TYPE_CHOICES` (alongside existing
  `TASK_CATEGORY_CHOICES`/`PHASE_CHOICES`):
  `("hire","Hire")`,
  `("confirmation","Confirmation (Probation End)")`,
  `("transfer","Transfer")`,
  `("promotion","Promotion")`,
  `("demotion","Demotion")`,
  `("salary_revision","Salary Revision")`,
  `("re_designation","Re-designation")`,
  `("location_change","Location Change")`,
  `("reporting_change","Reporting Manager Change")`,
  `("suspension","Suspension")`,
  `("reinstatement","Reinstatement")`,
  `("contract_renewal","Contract Renewal")`,
  `("separation","Separation")`,
  `("other","Other")`.

- [ ] **Fields:**
  - `employee` — `FK("hrm.EmployeeProfile", CASCADE, related_name="lifecycle_events")`.
  - `event_type` — `CharField(max_length=30, choices=LIFECYCLE_EVENT_TYPE_CHOICES)`.
  - `effective_date` — `DateField()`. When the change takes effect. Table-stakes across all 10
    surveyed products.
  - `reason` — `TextField(blank=True)`. Free-text change reason. Drivers: Workday reason codes, SAP SF
    event reasons, BambooHR compensation `reason`, Personio reason columns.
  - **From/To capture** (all null/blank; populate only the fields relevant to the event type):
    - `from_designation` — `FK("hrm.Designation", SET_NULL, null=True, blank=True, related_name="+")`.
    - `to_designation` — `FK("hrm.Designation", SET_NULL, null=True, blank=True, related_name="+")`.
    - `from_department` — `FK("core.OrgUnit", SET_NULL, null=True, blank=True, related_name="+")`.
    - `to_department` — `FK("core.OrgUnit", SET_NULL, null=True, blank=True, related_name="+")`.
    - `from_location` — `CharField(max_length=255, blank=True)`.
    - `to_location` — `CharField(max_length=255, blank=True)`.
    - `from_job_title` — `CharField(max_length=255, blank=True)`.
    - `to_job_title` — `CharField(max_length=255, blank=True)`.
    - `from_salary` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`.
      Drivers: BambooHR compensation table, HiBob Salary table.
    - `to_salary` — `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)`.
    - `from_manager` — `FK("hrm.EmployeeProfile", SET_NULL, null=True, blank=True, related_name="+")`.
    - `to_manager` — `FK("hrm.EmployeeProfile", SET_NULL, null=True, blank=True, related_name="+")`.
    - `from_employee_type` — `CharField(max_length=20, blank=True)`.
    - `to_employee_type` — `CharField(max_length=20, blank=True)`.
    Drivers: Workday new org/position, SAP SF new vs. old jobInfo row, Personio old/new value columns,
    HiBob effective rows vs. prior rows.
  - `notes` — `TextField(blank=True)`.
  - `initiated_by` — `FK(settings.AUTH_USER_MODEL, SET_NULL, null=True, blank=True,
    related_name="hrm_initiated_lifecycle_events", editable=False)`. Set in the create view
    (`form.instance.initiated_by = request.user`), NOT a form field. Drivers: Personio editor
    column, Workday initiating user.
  **v1 design note:** This model records events for the timeline only. It does NOT auto-mutate
  `core.Employment` or `EmployeeProfile` on save. That bidirectional auto-sync is a deferred
  enhancement (see Later Passes section).
  **Meta:** `unique_together = ("tenant", "number")`; `ordering = ["-effective_date", "-created_at"]`.
  **Indexes:**
  - `(tenant, employee, effective_date)` — `hrm_elc_tenant_emp_date_idx`
  - `(tenant, event_type)` — `hrm_elc_tenant_type_idx`
  - `(tenant, employee, event_type)` — `hrm_elc_tenant_emp_type_idx`
  - `(tenant, effective_date)` — `hrm_elc_tenant_effdate_idx`
  **`__str__`:** `f"{self.number} · {self.employee.name} — {self.get_event_type_display()} ({self.effective_date})"`.

---

## 4. Forms (`apps/hrm/forms.py`)

- [ ] **`EmployeeProfileForm`** — extend `fields` list with 15 new fields, grouped logically:
  personal→`marital_status`; work→`work_email`, `work_location`, `notice_period_days`; IDs→
  `national_id`, `national_id_type`, `passport_number`, `passport_expiry`; family→`father_name`,
  `spouse_name`; addresses→`current_address`, `permanent_address`; emergency2→
  `emergency_contact_2_name`, `emergency_contact_2_phone`, `emergency_contact_2_relation`.

- [ ] **`EmployeeDocumentForm(TenantModelForm)`** — new form.
  - `model = EmployeeDocument`.
  - `fields = ["employee", "document_type", "title", "document_number", "issuing_authority",
    "issuing_country", "issued_on", "expires_on", "is_confidential", "file", "notes"]`.
  - **Excluded**: `tenant`, `number`, `verification_status`, `verified_by`, `verified_at`
    (workflow-owned / system fields — never settable via form POST).
  - `__init__`: scope `employee` queryset →
    `EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party").order_by("party__name")`.
  - `clean_file` — **mirror `OnboardingDocumentForm.clean_file` exactly**:
    allowlist `{".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"}`, size cap 10 MB, fresh-upload
    check, WARNING comment re: extension-only allowlist.

- [ ] **`EmployeeLifecycleEventForm(TenantModelForm)`** — new form.
  - `model = EmployeeLifecycleEvent`.
  - `fields = ["employee", "event_type", "effective_date", "reason", "from_designation",
    "to_designation", "from_department", "to_department", "from_location", "to_location",
    "from_job_title", "to_job_title", "from_salary", "to_salary", "from_manager", "to_manager",
    "from_employee_type", "to_employee_type", "notes"]`.
  - **Excluded**: `tenant`, `number`, `initiated_by` (set to `request.user` in the create view).
  - `__init__`: scope `employee` → tenant-filtered `EmployeeProfile`; `from_designation`/
    `to_designation` → `Designation.objects.filter(tenant=self.tenant, is_active=True)`; `from_department`/
    `to_department` → `OrgUnit.objects.filter(tenant=self.tenant)`; `from_manager`/`to_manager` →
    tenant-filtered `EmployeeProfile.select_related("party")`.

- [ ] Add `EmployeeDocument` and `EmployeeLifecycleEvent` to the `from .models import (...)` block.

---

## 5. Views (`apps/hrm/views.py`)

### 5.1 `EmployeeDocument` CRUD + workflow

- [ ] **`employee_document_list`** — `crud_list(...)`:
  - Queryset: `EmployeeDocument.objects.filter(tenant=request.tenant).select_related("employee__party")`.
  - `template="hrm/employee/document/list.html"`.
  - `search_fields=["number", "title", "document_number", "employee__party__name"]`.
  - `filters=[("document_type","document_type",False), ("verification_status","verification_status",False)]`.
  - `extra_context={"document_type_choices": EmployeeDocument.DOCUMENT_TYPE_CHOICES,
    "verification_status_choices": EmployeeDocument.VERIFICATION_STATUS_CHOICES}`.

- [ ] **`employee_document_create`** — `crud_create(...)`:
  - `form_class=EmployeeDocumentForm`, `template="hrm/employee/document/form.html"`.
  - Honor `?employee=<pk>` pre-fill: extract `request.GET.get("employee")` and pass as `initial`.
  - After save, redirect to `hrm:employee_detail pk=obj.employee.pk` (returns user to the hub).

- [ ] **`employee_document_detail`** — `get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)`;
  `render(request, "hrm/employee/document/detail.html", {"obj": obj})`.

- [ ] **`employee_document_edit`** — `crud_edit(...)`:
  - `model=EmployeeDocument`, `form_class=EmployeeDocumentForm`,
    `template="hrm/employee/document/form.html"`, `success_url="hrm:employee_document_list"`.
  - Guard: if `obj.verification_status == "verified"`, `messages.warning(request,
    "Verified documents cannot be edited. Reject first.")` → redirect to detail.

- [ ] **`employee_document_delete`** — `@require_POST`; tenant-scoped fetch. Guard: block deletion
  of `"verified"` documents (`messages.error` + redirect to detail). On POST: `write_audit_log`,
  `obj.delete()`, `messages.success`, redirect to `hrm:employee_document_list`.

- [ ] **`employee_document_mark_verified`** — `@tenant_admin_required`, `@require_POST`.
  - Guard: `verification_status` must be `"pending"` (error + redirect if not).
  - Set `obj.verification_status = "verified"`, `obj.verified_by = request.user`,
    `obj.verified_at = timezone.now()`.
  - `obj.save(update_fields=["verification_status","verified_by","verified_at","updated_at"])`.
  - `write_audit_log(request.user, obj, "update", {"action": "mark_verified"})`.
  - `messages.success`. Redirect to `hrm:employee_document_detail pk=obj.pk`.

- [ ] **`employee_document_reject`** — `@tenant_admin_required`, `@require_POST`.
  - Guard: `verification_status` must be `"pending"` or `"verified"` (error if already `"rejected"`).
  - Set `obj.verification_status = "rejected"`.
  - `obj.save(update_fields=["verification_status","updated_at"])`.
  - `write_audit_log(request.user, obj, "update", {"action": "reject"})`.
  - `messages.success`. Redirect to `hrm:employee_document_detail pk=obj.pk`.

### 5.2 `EmployeeLifecycleEvent` CRUD

- [ ] **`employee_lifecycle_list`** — `crud_list(...)`:
  - Queryset: `EmployeeLifecycleEvent.objects.filter(tenant=request.tenant).select_related(
    "employee__party","from_designation","to_designation")`.
  - `template="hrm/employee/lifecycle/list.html"`.
  - `search_fields=["number","employee__party__name","reason","notes"]`.
  - `filters=[("event_type","event_type",False), ("employee","employee_id",True)]`.
  - `extra_context={"event_type_choices": LIFECYCLE_EVENT_TYPE_CHOICES,
    "employees": EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party")
    .order_by("party__name")}`.

- [ ] **`employee_lifecycle_create`** — `crud_create(...)`:
  - `form_class=EmployeeLifecycleEventForm`, `template="hrm/employee/lifecycle/form.html"`.
  - Honor `?employee=<pk>` pre-fill (same `initial` pattern as `employee_document_create`).
  - Stamp `initiated_by = request.user` on `form.instance` before `form.save()`. If `crud_create`
    does not support a pre-save hook, write the view manually (mirror `crud_create` logic with the
    extra stamp step).
  - After save, redirect to `hrm:employee_detail pk=obj.employee.pk`.

- [ ] **`employee_lifecycle_detail`** — `get_object_or_404(EmployeeLifecycleEvent, pk=pk,
  tenant=request.tenant)` with full `select_related` on designation/department/manager FKs;
  `render(request, "hrm/employee/lifecycle/detail.html", {"obj": obj})`.

- [ ] **`employee_lifecycle_edit`** — `crud_edit(...)`:
  - `model=EmployeeLifecycleEvent`, `form_class=EmployeeLifecycleEventForm`,
    `template="hrm/employee/lifecycle/form.html"`, `success_url="hrm:employee_lifecycle_list"`.

- [ ] **`employee_lifecycle_delete`** — `@require_POST`; tenant-scoped fetch; `write_audit_log`;
  `obj.delete()`; `messages.success`; redirect to `hrm:employee_lifecycle_list`.

### 5.3 Extend `employee_detail` view

- [ ] Add to the context passed by `employee_detail(request, pk)`:
  - `"documents"`: `EmployeeDocument.objects.filter(tenant=request.tenant, employee=obj)
    .order_by("-created_at")[:10]`.
  - `"lifecycle_events"`: `EmployeeLifecycleEvent.objects.filter(tenant=request.tenant, employee=obj)
    .select_related("from_designation","to_designation","from_department","to_department")
    .order_by("-effective_date")[:10]`.
- [ ] Add `EmployeeDocument`, `EmployeeLifecycleEvent` to the `from .models import (...)` block.
- [ ] Add `EmployeeDocumentForm`, `EmployeeLifecycleEventForm` to the `from .forms import (...)` block.

---

## 6. URLs (`apps/hrm/urls.py`)

Add the following path() entries (all existing patterns untouched):

- [ ] **`EmployeeDocument` (5 CRUD + 2 workflow):**
  ```
  "employee-documents/"                    → employee_document_list        (name="employee_document_list")
  "employee-documents/add/"               → employee_document_create       (name="employee_document_create")
  "employee-documents/<int:pk>/"          → employee_document_detail       (name="employee_document_detail")
  "employee-documents/<int:pk>/edit/"     → employee_document_edit         (name="employee_document_edit")
  "employee-documents/<int:pk>/delete/"   → employee_document_delete       (name="employee_document_delete")
  "employee-documents/<int:pk>/verify/"   → employee_document_mark_verified (name="employee_document_mark_verified")
  "employee-documents/<int:pk>/reject/"   → employee_document_reject       (name="employee_document_reject")
  ```

- [ ] **`EmployeeLifecycleEvent` (5 CRUD):**
  ```
  "lifecycle-events/"                     → employee_lifecycle_list        (name="employee_lifecycle_list")
  "lifecycle-events/add/"                 → employee_lifecycle_create      (name="employee_lifecycle_create")
  "lifecycle-events/<int:pk>/"            → employee_lifecycle_detail      (name="employee_lifecycle_detail")
  "lifecycle-events/<int:pk>/edit/"       → employee_lifecycle_edit        (name="employee_lifecycle_edit")
  "lifecycle-events/<int:pk>/delete/"     → employee_lifecycle_delete      (name="employee_lifecycle_delete")
  ```

---

## 7. Admin (`apps/hrm/admin.py`)

- [ ] Register `EmployeeDocument`:
  - `list_display = ["number","employee","document_type","title","verification_status","expires_on",
    "is_confidential","created_at"]`.
  - `list_filter = ["document_type","verification_status","is_confidential"]`.
  - `search_fields = ["number","title","document_number","employee__party__name"]`.
  - `readonly_fields = ["number","tenant","verification_status","verified_by","verified_at",
    "created_at","updated_at"]`.

- [ ] Register `EmployeeLifecycleEvent`:
  - `list_display = ["number","employee","event_type","effective_date","from_designation",
    "to_designation","initiated_by","created_at"]`.
  - `list_filter = ["event_type"]`.
  - `search_fields = ["number","employee__party__name","reason","notes"]`.
  - `readonly_fields = ["number","tenant","initiated_by","created_at","updated_at"]`.

- [ ] Add both models to the admin imports.

---

## 8. Templates (`templates/hrm/employee/`)

Template folder rule: sub-module folder `employee/` doubles as the `EmployeeProfile` entity folder
(single-entity rule from SKILL.md / CLAUDE.md). The two new child entities get their own sub-folders:
`templates/hrm/employee/document/` and `templates/hrm/employee/lifecycle/`. Existing
`employee/list.html`, `employee/detail.html`, `employee/form.html` STAY in place (no move needed).

### 8.1 `EmployeeDocument` templates

- [ ] **`templates/hrm/employee/document/list.html`** — extends `base.html`.
  - Page header + "Add Document" button (→ `hrm:employee_document_create`).
  - Filter bar: search `q`, `document_type` `<select>` (pre-filled from `request.GET.document_type`,
    exact string compare), `verification_status` `<select>` (pre-filled from `request.GET.
    verification_status`, exact string compare). Pass both choice lists via `extra_context`.
  - Table columns: Number, Employee, Type (badge), Title, Doc Number, Issued, Expires
    (+ `badge-red` if `obj.is_expired`, `badge-amber` if `obj.is_expiring_soon`), Verification
    (badge: `badge-amber` pending, `badge-green` verified, `badge-red` rejected), Confidential
    (lock icon if `is_confidential`), Actions (view/edit/delete-POST+confirm+csrf).
  - Empty-state + `{% include "partials/pagination.html" %}`.

- [ ] **`templates/hrm/employee/document/detail.html`** — extends `base.html`.
  - Breadcrumb: HRM › Employees › `{obj.employee.name}` › Documents › `{obj.number}`.
  - Page actions: Edit (if `verification_status != "verified"`), Delete (POST+confirm, blocked if
    verified), Back to Employee (`hrm:employee_detail obj.employee.pk`).
  - Cards:
    1. **Document Info** (`detail-grid`): Number, Type, Title, Document Number, Issuing Authority,
       Issuing Country, Issued On, Expires On (+ expiry badge), Confidential flag.
    2. **Verification** card: Status badge, Verified By, Verified At, Notes.
    3. **File** card: download link `<a href="{{ obj.file.url }}" target="_blank" rel="noopener">
       Download</a>` (if `obj.file`), else "No file uploaded".
  - Workflow buttons (POST forms; show only if current user is tenant admin — server enforces):
    "Mark Verified" → `hrm:employee_document_mark_verified` (show if `status == "pending"`).
    "Reject" → `hrm:employee_document_reject` (show if `status == "pending"` or `"verified"`).
    Each wrapped in `<form method="post" ...>{% csrf_token %}<button ...></form>`.

- [ ] **`templates/hrm/employee/document/form.html`** — extends `base.html`.
  - `<form enctype="multipart/form-data" ...>` (required for file upload).
  - Breadcrumb: HRM › Employees › Documents › Add / Edit.
  - All `EmployeeDocumentForm` fields. Date inputs for `issued_on`/`expires_on` (`type="date"`).
  - Hint text below file input: "Allowed: PDF, DOC, DOCX, JPG, PNG. Max 10 MB."
  - Submit + Cancel (→ `hrm:employee_document_list`) buttons.

### 8.2 `EmployeeLifecycleEvent` templates

- [ ] **`templates/hrm/employee/lifecycle/list.html`** — extends `base.html`.
  - Page header + "Add Event" button (→ `hrm:employee_lifecycle_create`).
  - Filter bar: search `q`, `event_type` `<select>` (exact string compare), `employee` `<select>`
    (FK filter — compare `emp.pk|stringformat:"d"` vs `request.GET.employee`).
  - Table columns: Number, Employee, Event Type (badge — hire=green, promotion=info, demotion=red,
    separation=slate, salary_revision=amber, others=muted), Effective Date, From→To summary
    (compact: show first populated from/to pair — designation, location, or salary), Reason
    (truncated 60 chars), Actions (view/edit/delete-POST+confirm+csrf).
  - Empty-state + pagination.

- [ ] **`templates/hrm/employee/lifecycle/detail.html`** — extends `base.html`.
  - Breadcrumb: HRM › Employees › `{obj.employee.name}` › Lifecycle › `{obj.number}`.
  - Page actions: Edit, Delete (POST+confirm), Back to Employee.
  - Cards:
    1. **Event** card: Number, Event Type badge, Effective Date, Reason, Notes, Initiated By,
       Created At.
    2. **Change Details** card (`detail-grid`): render each from/to pair only when at least one
       side is populated:
       Designation (from → to), Department (from → to), Location (from → to), Job Title (from → to),
       Salary (from → to, `.text-right`), Manager (from → to), Employee Type (from → to).
       Guard each row: `{% if obj.from_designation or obj.to_designation %}`.

- [ ] **`templates/hrm/employee/lifecycle/form.html`** — extends `base.html`.
  - Breadcrumb: HRM › Employees › Lifecycle Events › Add / Edit.
  - Two `<fieldset>` groups:
    1. **Core**: `event_type`, `employee`, `effective_date`, `reason`, `notes`.
    2. **Change Details**: all `from_*`/`to_*` fields with hint:
       "Fill only the fields relevant to this event type."
  - Submit + Cancel (→ `hrm:employee_lifecycle_list`).

### 8.3 Extend `templates/hrm/employee/detail.html` (existing file — edit in place)

- [ ] **"Personal Information" card** — add after `mobile`:
  - Marital Status: `{{ obj.get_marital_status_display|default:"—" }}`.
  - Work Email: `{{ obj.work_email|default:"—" }}`.
  - Work Location: `{{ obj.work_location|default:"—" }}`.
  - After the emergency contact row: second emergency contact (render name/phone/relation in the same
    compact style — only if any of the three `emergency_contact_2_*` fields is non-empty).
  - Father's Name: `{{ obj.father_name|default:"—" }}`.
  - Spouse Name: `{{ obj.spouse_name|default:"—" }}`.

- [ ] **"Employment" card** — add after `confirmed_on`:
  - Notice Period: `{{ obj.notice_period_days|default:"—" }} days`.
  - After `bank_routing`: National ID: `{{ obj.national_id|default:"—" }}`, ID Type:
    `{{ obj.national_id_type|default:"—" }}`, Passport No.: `{{ obj.passport_number|default:"—" }}`,
    Passport Expiry: `{{ obj.passport_expiry|default:"—" }}`.

- [ ] **Add "Addresses" card** (new `<div class="card">` after the Employment card):
  - Current Address: `{{ obj.current_address|linebreaksbr|default:"—" }}`.
  - Permanent Address: `{{ obj.permanent_address|linebreaksbr|default:"—" }}`.
  - Wrap the entire card in `{% if obj.current_address or obj.permanent_address %}...{% endif %}`.

- [ ] **Add "Employee Documents" card** (after the Addresses card):
  - Header: "Employee Documents" + "Add Document" button → `hrm:employee_document_create` with
    `?employee={{ obj.pk }}`.
  - Table from `documents` context: Type badge, Title, Doc Number, Issued/Expiry (+ expiry badges),
    Verification badge, File download link, Actions (View + workflow verify/reject if admin).
  - "View All" link → `hrm:employee_document_list`.
  - Empty-state: "No documents on file. Add the first document."

- [ ] **Add "Employment Lifecycle" card** (after the Documents card):
  - Header: "Employment Lifecycle" + "Add Event" button → `hrm:employee_lifecycle_create` with
    `?employee={{ obj.pk }}`.
  - Timeline table from `lifecycle_events` context (ordered `-effective_date`): Effective Date,
    Event Type badge, compact From→To summary, Reason (truncated), View detail link.
  - "View Full Timeline" link → `hrm:employee_lifecycle_list`.
  - Empty-state: "No lifecycle events recorded yet."

### 8.4 Extend `templates/hrm/employee/form.html` (existing file — edit in place)

- [ ] Add the 15 new `EmployeeProfile` form fields, grouped:
  - Personal: `marital_status` (`<select>`), `work_email` (`type="email"`), `work_location`
    (`type="text"`), `notice_period_days` (`type="number"`).
  - Family: `father_name`, `spouse_name`.
  - Identity: `national_id`, `national_id_type`, `passport_number`, `passport_expiry`
    (`type="date"`).
  - Addresses: `current_address` (`<textarea>`), `permanent_address` (`<textarea>`).
  - Second Emergency Contact: `emergency_contact_2_name`, `emergency_contact_2_phone`,
    `emergency_contact_2_relation`.

---

## 9. Wire-up (`apps/core/navigation.py`)

- [ ] In `LIVE_LINKS["3.1"]`, **add two new entries** (keep the existing three unchanged):
  ```python
  "Document Management": "hrm:employee_document_list",   # bullet — closes gap 3.1.D
  "Employee Lifecycle":  "hrm:employee_lifecycle_list",  # bullet — closes gap 3.1.E
  ```
  After this change, all 5 NavERP.md 3.1 bullets are Live. Do NOT touch any other `LIVE_LINKS` entry.

---

## 10. Migration

- [ ] `python manage.py makemigrations hrm` — one incremental migration adding the 15 `EmployeeProfile`
  fields and creating the two new tables. Verify all 15 new fields are nullable/blank/have defaults
  (non-destructive to existing rows).
- [ ] `python manage.py migrate` — apply to `nav_erp` database.
- [ ] `python manage.py check` — 0 issues.

---

## 11. Seed (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] Add a `_seed_employee_records(tenant)` function. Call it from `handle()` after the existing
  `_seed_offboarding(tenant)` block.

- [ ] **Idempotent guard at top of `_seed_employee_records`:**
  ```python
  if EmployeeDocument.objects.filter(tenant=tenant).exists():
      self.stdout.write(f"  [skip] Employee records already seeded for {tenant.slug}")
      return
  ```

- [ ] **For each of the first 3 seeded employees** (`EmployeeProfile.objects.filter(tenant=tenant)
  .order_by("created_at")[:3]`), create:
  - **`EmployeeDocument` rows (2–3 per employee):**
    1. `document_type="national_id"`, `title="National ID"` — create, then set
       `obj.verification_status = "verified"; obj.save(update_fields=["verification_status",
       "updated_at"])` (direct model update bypasses the editable=False restriction, permitted in
       management commands).
    2. `document_type="passport"`, `title="Passport"`, `issued_on = date.today() - timedelta(3650)`,
       `expires_on = date.today() + timedelta(180)` (shows as expiring-soon), `verification_status`
       stays `"pending"` (default, no extra save needed).
    3. `document_type="employment_contract"`, `title="Appointment Letter"` — create, then set
       `obj.verification_status = "verified"` (direct model update as above).
  - **`EmployeeLifecycleEvent` rows (1–2 per employee):**
    1. `event_type="hire"`, `effective_date = emp.employment.hired_on if emp.employment_id else
       date.today() - timedelta(365)`, `reason="Initial hire"`, `initiated_by=None`.
    2. If `emp.confirmed_on` is set: `event_type="confirmation"`, `effective_date=emp.confirmed_on`,
       `reason="Probation successfully completed"`, `initiated_by=None`.

- [ ] Add `EmployeeDocument`, `EmployeeLifecycleEvent` to the seeder's `--flush` delete list.

- [ ] Add imports to the seeder: `from .models import EmployeeDocument, EmployeeLifecycleEvent`
  (alongside the existing model imports).

- [ ] Run seeder twice to verify idempotency (second run must print skip message, no extra rows).

---

## 12. Verify

- [ ] `manage.py check` — 0 issues.
- [ ] `manage.py migrate` — clean on `nav_erp` MariaDB.
- [ ] **Seed twice** — second run skips `_seed_employee_records` (idempotent guard fires).
- [ ] **Smoke sweep (`temp/` script)** — all new named URLs 200/302:
  - `hrm:employee_document_list` → 200.
  - `hrm:employee_document_create` → 200.
  - `hrm:employee_document_detail pk=<seeded>` → 200.
  - `hrm:employee_document_edit pk=<seeded>` → 200.
  - `hrm:employee_document_mark_verified pk=<seeded>` → POST → 302.
  - `hrm:employee_document_reject pk=<seeded>` → POST → 302.
  - `hrm:employee_lifecycle_list` → 200.
  - `hrm:employee_lifecycle_create` → 200.
  - `hrm:employee_lifecycle_detail pk=<seeded>` → 200.
  - `hrm:employee_lifecycle_edit pk=<seeded>` → 200.
  - `hrm:employee_detail pk=<seeded>` → 200 (two new hub cards render without TemplateDoesNotExist).
- [ ] **No template comment leaks** — scan all new `.html` files for `{#` or `{% comment`.
- [ ] **Cross-tenant IDOR → 404** — `employee_document_detail` and `employee_lifecycle_detail` with
  pk from tenant B, logged in as tenant A → 404 (enforced by `tenant=request.tenant` in
  `get_object_or_404`).
- [ ] **Workflow gate** — `employee_document_mark_verified` as a regular member → 403 (enforced by
  `@tenant_admin_required`).
- [ ] **Sidebar** — log in as `admin_acme`; open HRM → Employee Management (3.1) → confirm
  "Document Management" and "Employee Lifecycle" both show as **Live** (not "On the roadmap").
- [ ] **Employee detail hub** — open any employee record → confirm "Employee Documents" card and
  "Employment Lifecycle" card render with seeded data.
- [ ] **Expiry badge** — the seeded passport doc (`expires_on = today + 180 days`) shows
  `is_expiring_soon=True` (amber badge) on list and detail — NOT `is_expired` (red badge).

---

## 13. Close-out

- [ ] **code-reviewer** agent — apply findings, one commit per file.
- [ ] **explorer** agent — apply findings, one commit per file.
- [ ] **frontend-reviewer** agent — apply findings, one commit per file.
- [ ] **performance-reviewer** agent — focus: `employee_detail` two new querysets use `select_related`;
  `is_expired`/`is_expiring_soon` not called per-row in the list view (compute in Python loop or
  annotate via `ExpressionWrapper`); document list `select_related("employee__party")` sufficient.
- [ ] **qa-smoke-tester** agent — apply findings, one commit per file.
- [ ] **security-reviewer** agent — focus: `mark_verified`/`reject` gate (`@tenant_admin_required`);
  file-upload allowlist (`clean_file`); cross-tenant IDOR; `verification_status`/`initiated_by` not
  settable via crafted POST.
- [ ] **test-writer** agent — tests for: `EmployeeDocument` model props (`is_expired`,
  `is_expiring_soon`, `__str__`, auto-number); `EmployeeLifecycleEvent` (`__str__`, auto-number,
  ordering); form exclusions (POST with `verification_status` or `initiated_by` → field ignored);
  CRUD views 200/302; `mark_verified` + `reject` workflow (guard + state transitions); member-403
  on admin-gated actions; IDOR 404 for both new models; seeder idempotency.
- [ ] **Update `.claude/skills/hrm/SKILL.md`** — add `EmployeeDocument` and `EmployeeLifecycleEvent`
  to the Models table; add the 12 new url names to the URLs section; add the two new entity folders
  (`employee/document/`, `employee/lifecycle/`) to the Templates section; update the Seeder section
  with `_seed_employee_records`; update the Sidebar wiring section for the two new `LIVE_LINKS["3.1"]`
  entries; update the EmployeeProfile field list.
- [ ] **`README.md`** — update HRM feature list + seeding instructions to mention Document Management
  and Employee Lifecycle.

---

## Later passes / deferred

- **Expiry email/push notifications** — Celery/management-command background task emailing HR when
  `EmployeeDocument.expires_on < today + N days`. The `expires_on` data is in place; delivery
  mechanism (SMTP/Celery) is an integration pass. Add `expiry_alert_sent_at DateTimeField` to prevent
  duplicate sends. Drivers: Keka 60/30/7-day GCC Iqama alerts, Workday auto-alerts (research 3.1.D).

- **Auto-sync lifecycle event → `EmployeeProfile`/`core.Employment`** — when a `promotion` or
  `transfer` event is saved, auto-update `EmployeeProfile.designation` and `core.Employment.org_unit`
  to the `to_*` values. v1 records the event only. Auto-sync deferred to avoid complexity + data-
  integrity risk. Requires careful `update_fields` + audit.

- **Multi-field `EmployeeAddress` table** — normalized table with `address_type`
  (current/permanent/contact/emergency), `line1`/`line2`/`city`/`state`/`postal`/`country`. v1 uses
  `current_address`/`permanent_address` TextFields. Deferred. Drivers: greytHR, Workday (research 3.1.B).

- **Second emergency contact as a normalized table** — `EmployeeEmergencyContact` table when >2
  contacts per employee are needed. v1 uses flat `_2_*` fields.

- **Document OCR / AI extraction** — Darwinbox-style AI OCR to auto-populate `document_number`,
  `issued_on`, `expires_on` from scanned images. Requires Tesseract/AWS Textract/Google Vision.

- **E-signature on personnel documents** — Zoho Sign/DocuSign/Adobe Sign integration. `OnboardingDocument`
  already handles e-sign for onboarding. Extending to the personnel vault is a later integration pass.

- **Document retention policy / GDPR auto-purge** — scheduled deletion past retention window. Add
  `retention_until DateField` to `EmployeeDocument` when this ships (research 3.1.D).

- **Dedicated Passport/Visa sub-model** — greytHR-style `EmployeePassport`/`EmployeeVisa` tables with
  family-member tracking and immigration-system integration. v1 covers via `document_type` on
  `EmployeeDocument`.

- **Background check workflow integration** — vendor API calls, status webhooks. v1: `document_type=
  "background_check"` + `is_confidential=True` is the data stub.

- **`work_location` FK upgrade** — upgrade from `CharField` to FK→`core.OrgUnit(kind=branch)` when
  a branch/location master is populated.

- **Languages / skills inventory** — `EmployeeSkill`/`EmployeeLanguage` table. Deferred to Talent
  Management (3.38).

- **Org chart view** — visual reporting-structure tree. Deferred to the 3.2 Organizational Structure
  pass.

- **Custom document types / fields** — admin-defined document types and per-type metadata fields.
  Requires the Module 0.10 Custom Fields engine.

---

## Review notes

**Delivered (3.1 completion).** Added the two missing NavERP.md 3.1 bullets on top of the existing `EmployeeProfile`
anchor (kept intact — 16+ HRM models FK it): **`EmployeeDocument`** (`EDOC-` personnel-file vault, verify/reject
workflow, expiry props, enforced `is_confidential`) + **`EmployeeLifecycleEvent`** (`ELC-` dated job-history
timeline) + 15 personnel-file fields on `EmployeeProfile` (incl. masked national_id/passport/bank_routing). Wired
`LIVE_LINKS["3.1"]` so all 5 bullets are Live; migration `0009`; `_seed_employee_records`; Documents + Lifecycle
hub cards on the employee detail. `manage.py check` clean; **844 HRM / 1,906 project-wide tests pass**.

> Coordination note: this ran in parallel with a separate agent rebuilding **3.2 Organizational Structure**. To
> avoid clobbering shared `apps/hrm/*` files + a clashing `0007` migration, 3.1 **waited** for 3.2 to land, then
> built cleanly on top (3.1 is migration `0009`, appended after 3.2's `0007`/`0008`).

Ran the full review-agent sequence (committed between each): **code-reviewer** (masked national_id/passport;
confirmed_on→form; seeder doc-type; cancel back-link), **explorer** (consistent), **frontend-reviewer** (expanded
14-type lifecycle badge map; folded confidential column; validated `?employee` cancel pk; page-actions on hub),
**performance-reviewer** (no N+1s — clean), **qa-smoke-tester** (49/49), **security-reviewer** (enforced
`is_confidential` admin-only; gated lifecycle writes to admin; masked bank_routing), **test-writer** (116 tests).
**Deferred (documented in SKILL.md):** lifecycle→Employment auto-sync, address normalization, expiry reminders,
and two project-wide security items (raw PII in the employee *edit form* — same as the pre-existing bank_account
treatment; unauthenticated `/media/` doc serving — same as onboarding docs/photos, mitigated by MEDIA_ROOT placement).

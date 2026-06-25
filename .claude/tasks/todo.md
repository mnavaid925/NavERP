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

## Review notes

(filled in at the end of the build pass)

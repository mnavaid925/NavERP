---
# HRM 3.13 Salary Structure (salary) — plan from research-salary.md (2026-07-04)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the compensation
**definition/master-data** layer only: a unified pay-component catalog, grade-wise CTC structure
templates + breakdown lines, and effective-dated per-employee structure assignments. Reuses
`hrm.JobGrade`, `hrm.Designation` (pay-band already present), `hrm.EmployeeProfile` as the only
cross-references — **no new spine masters**, **no GL posting** (that's `accounting.PayrollRun`, per
lesson L29), `currency` stays a plain `CharField` this pass. 4 new models, all in `apps/hrm/models.py`.

NavERP.md 3.13 bullets (exact text, all 5 go Live this pass):
- Pay Components — Basic, HRA, allowances, deductions.
- Salary Structure Templates — Grade-wise structures, CTC breakdown.
- Variable Pay — Bonus, incentives, commissions.
- Tax Components — TDS, professional tax, PF, ESI.
- Reimbursements — LTA, medical, fuel, mobile reimbursements.

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `PayComponent(TenantOwned)` — no number prefix (small catalog like `JobGrade`), the unified
      component master covering 4 of the 5 bullets in one table:
  - [ ] `name` — CharField(max_length=150)
  - [ ] `code` — CharField(max_length=20, blank=True) — optional short code (e.g. "HRA", "PF-EE")
  - [ ] `component_type` — CharField(max_length=20, choices=`COMPONENT_TYPE_CHOICES`) —
        `[("earning","Earning"),("statutory_deduction","Statutory Deduction"),
        ("voluntary_deduction","Voluntary Deduction"),("reimbursement","Reimbursement"),
        ("variable","Variable")]` — driver: Zoho Payroll's 4-way Earnings/Benefits/Deductions/
        Corrections taxonomy + greytHR's Gross/Deduction/PF grouping (research L28-31, L153-155)
  - [ ] `variable_subtype` — CharField(max_length=30, blank=True) — free label (e.g. "bonus",
        "incentive", "commission"); only meaningful when `component_type="variable"` — driver:
        RazorpayX Bonus Management types, Darwinbox named variable components, Workday Bonus Plan
        family (research L84-88, L99-102)
  - [ ] `calculation_type` — CharField(max_length=20, choices=`CALCULATION_TYPE_CHOICES`) —
        `[("fixed_amount","Fixed Amount"),("pct_of_basic","% of Basic"),("pct_of_ctc","% of CTC"),
        ("pct_of_gross","% of Gross")]` — driver: Keka/Zoho/Darwinbox formula-driven components,
        Zoho's explicit Basic+DA/Gross statutory basis (research L32-37, L122-127, L156-159)
  - [ ] `default_amount` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) —
        org-wide default when `calculation_type="fixed_amount"`; a `SalaryStructureLine` can override
  - [ ] `default_percentage` — DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) —
        org-wide default when `calculation_type` is a `pct_*` type
  - [ ] `frequency` — CharField(max_length=20, choices=`FREQUENCY_CHOICES`) —
        `[("monthly","Monthly"),("annual","Annual"),("one_time","One-Time")]` — driver: Zoho's
        recurring-earning vs. one-time-deduction distinction, RazorpayX per-run variable additions
        (research L41-43, L89-94)
  - [ ] `is_taxable` — BooleanField(default=True) — driver: Zoho's taxable-fixed-earning rule,
        factoHR's tax-exempt fuel reimbursement (research L38-40, L143-147)
  - [ ] `include_in_ctc` — BooleanField(default=True) — driver: Zoho's Benefits-vs-CTC split,
        Darwinbox's Direct/Indirect Benefits/Savings split (research L47-50, L163-166)
  - [ ] `contribution_side` — CharField(max_length=10, choices=`CONTRIBUTION_SIDE_CHOICES`,
        default="employee") — `[("employee","Employee"),("employer","Employer"),("both","Both")]` —
        driver: Zoho Payroll's PF/ESI employee-vs-employer contribution split (research L112-116,
        L165-166); mainly meaningful for statutory components
  - [ ] `annual_cap_amount` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) —
        driver: factoHR's LTA/medical claim caps (research L135-138, L167)
  - [ ] `requires_bill` — BooleanField(default=False) — driver: greytHR's mandatory-attachment
        reimbursement setting (research L139-142, L168)
  - [ ] `is_active` — BooleanField(default=True)
  - [ ] `display_order` — PositiveSmallIntegerField(default=0) — driver: Keka/Zoho component
        management UX, payslip/breakdown print ordering (research L44-46, L162)
  - [ ] `description` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["display_order", "name"]`; `unique_together = ("tenant", "name")`;
        index `models.Index(fields=["tenant", "component_type"], name="hrm_paycomp_tenant_type_idx")`
  - [ ] `clean()` — soft consistency validation (allow blank defaults since a
        `SalaryStructureLine` can override, but validate when a default IS provided):
        if `calculation_type == "fixed_amount"` and `default_percentage` is not None →
        `ValidationError({"default_percentage": "Fixed-amount components should not set a default
        percentage."})`; if `calculation_type` startswith `"pct_"` and `default_amount` is not None →
        `ValidationError({"default_amount": "Percentage-based components should not set a default
        amount."})`
  - [ ] `__str__` → `self.name`

- [ ] `SalaryStructureTemplate(TenantNumbered, NUMBER_PREFIX="SST")` — the grade-wise CTC container:
  - [ ] `name` — CharField(max_length=150) — e.g. "L3 Engineer — Standard CTC"
  - [ ] `job_grade` — FK `hrm.JobGrade`, `on_delete=models.SET_NULL`, `null=True, blank=True`,
        `related_name="salary_structure_templates"` — reuse, do not duplicate the grade catalog
        (research L53-57, L174-178)
  - [ ] `annual_ctc_amount` — DecimalField(max_digits=14, decimal_places=2, null=True, blank=True) —
        target CTC used to derive `pct_of_ctc` line amounts; blank if amount-driven line-by-line
  - [ ] `currency` — CharField(max_length=10, default="USD") — plain field per the brief, no FK to
        `accounting.Currency` this pass (research L182, Deferred)
  - [ ] `is_active` — BooleanField(default=True)
  - [ ] `description` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-created_at"]`; `unique_together = ("tenant", "number")`; index
        `models.Index(fields=["tenant", "job_grade"], name="hrm_sst_tenant_grade_idx")`
  - [ ] `computed_ctc_total` — **derived property** (NOT a stored field) — sums `resolved_amount()`
        across `self.lines.select_related("pay_component").all()`; mirrors the
        `PayrollRun.net_pay`-style derived-field convention (research L69-72, L184-185)
  - [ ] `__str__` → `f"{self.number} · {self.name}"`

- [ ] `SalaryStructureLine(TenantOwned)` — the CTC breakdown row, child of the template:
  - [ ] `template` — FK `SalaryStructureTemplate`, `on_delete=models.CASCADE`,
        `related_name="lines"`
  - [ ] `pay_component` — FK `PayComponent`, `on_delete=models.PROTECT` — PROTECT (not SET_NULL) so
        an in-use component can't vanish out from under a template's breakdown
  - [ ] `calculation_type` — CharField(max_length=20, choices=`PayComponent.CALCULATION_TYPE_CHOICES`,
        blank=True) — optional per-template override; blank = defer to `pay_component.calculation_type`
  - [ ] `amount` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — overrides
        `pay_component.default_amount` on this template when set
  - [ ] `percentage` — DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) —
        overrides `pay_component.default_percentage` on this template when set
  - [ ] `sequence` — PositiveSmallIntegerField(default=0) — print/breakdown ordering (research L196)
  - [ ] `class Meta`: `ordering = ["sequence", "id"]`; `unique_together = ("tenant", "template",
        "pay_component")` — one line per component per template; index `models.Index(fields=["tenant",
        "template"], name="hrm_ssl_tenant_template_idx")`
  - [ ] `resolved_amount()` method — the CTC-total resolver used by `computed_ctc_total`:
        effective_calc = `self.calculation_type or self.pay_component.calculation_type`; if
        `effective_calc == "fixed_amount"`: return `self.amount if self.amount is not None else
        (self.pay_component.default_amount or Decimal("0"))`; else (a `pct_*` type): resolve `pct =
        self.percentage if self.percentage is not None else (self.pay_component.default_percentage or
        Decimal("0"))`, then `base = self.template.annual_ctc_amount or Decimal("0")` for
        `pct_of_ctc`, else fall back to `base = self.template.annual_ctc_amount or Decimal("0")` for
        `pct_of_basic`/`pct_of_gross` too (v1 simplification — no separate stored "basic" or "gross"
        subtotal exists yet, so all percentage types resolve against `annual_ctc_amount`; note this
        simplification explicitly in the model docstring and carry a true multi-base resolver to a
        later pass); return `(base * pct / Decimal("100")).quantize(Decimal("0.01"))`
  - [ ] `__str__` → `f"{self.template} · {self.pay_component}"`

- [ ] `EmployeeSalaryStructure(TenantNumbered, NUMBER_PREFIX="ESS")` — effective-dated assignment:
  - [ ] `employee` — FK `hrm.EmployeeProfile`, `on_delete=models.CASCADE`,
        `related_name="salary_structures"`
  - [ ] `template` — FK `SalaryStructureTemplate`, `on_delete=models.SET_NULL`, `null=True,
        blank=True`, `related_name="employee_assignments"`
  - [ ] `annual_ctc_amount` — DecimalField(max_digits=14, decimal_places=2) — the employee's actual
        CTC, may differ from `template.annual_ctc_amount` (RazorpayX per-employee override, research
        L206-207)
  - [ ] `effective_from` — DateField()
  - [ ] `effective_to` — DateField(null=True, blank=True) — open-ended until superseded
  - [ ] `status` — CharField(max_length=20, choices=`STATUS_CHOICES`, default="active") —
        `[("active","Active"),("superseded","Superseded")]` — simple two-state, no multi-level
        approval workflow this pass (research L210-211, Deferred); **decision:** no dedicated
        "supersede" action view — superseding is done by editing the old row's `status` to
        `"superseded"` (and setting `effective_to`) then creating a new active row via the normal
        create form; note this explicitly so the main agent doesn't over-build a wizard
  - [ ] `notes` — TextField(blank=True) — e.g. reason for revision
  - [ ] `class Meta`: `ordering = ["-effective_from"]`; `unique_together = ("tenant", "number")`;
        indexes: `models.Index(fields=["tenant", "employee", "effective_from"],
        name="hrm_ess_tenant_emp_efrom_idx")`, `models.Index(fields=["tenant", "status"],
        name="hrm_ess_tenant_status_idx")`
  - [ ] `clean()`:
    - [ ] if `self.effective_to` and `self.effective_from` and `self.effective_to <
          self.effective_from` → `ValidationError({"effective_to": "Effective-to date cannot be
          before effective-from date."})`
    - [ ] at-most-one-active-per-employee: if `self.status == "active"` and `self.employee_id`,
          query `EmployeeSalaryStructure.objects.filter(tenant_id=self.employee.tenant_id,
          employee_id=self.employee_id, status="active").exclude(pk=self.pk)`; if it `.exists()` →
          `ValidationError({"status": "This employee already has an active salary structure — mark
          the existing one superseded first."})` (mirror the tenant-derived-from-employee idiom used
          in `FloatingHolidayElection.clean()` per lesson from 3.12 since `self.tenant_id` may be
          unset during ModelForm create-validation)
  - [ ] `__str__` → `f"{self.number} · {self.employee}"`

- [ ] one incremental migration `apps/hrm/migrations/0024_paycomponent_salarystructuretemplate_and_more.py`
      (NOT `0001_initial`) — `makemigrations hrm`, review the generated file, adjust index/constraint
      names to match the ones specified above if Django's auto-names differ.

## B. Forms (`apps/hrm/forms.py`)

- [ ] `PayComponentForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["name", "code", "component_type", "variable_subtype", "calculation_type",
        "default_amount", "default_percentage", "frequency", "is_taxable", "include_in_ctc",
        "contribution_side", "annual_cap_amount", "requires_bill", "is_active", "display_order",
        "description"]`
- [ ] `SalaryStructureTemplateForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["name", "job_grade", "annual_ctc_amount", "currency", "is_active",
        "description"]` (exclude `number` — auto; exclude `computed_ctc_total` — derived property,
        never a form field)
  - [ ] `__init__`: narrow `job_grade` queryset to `JobGrade.objects.filter(tenant=self.tenant,
        is_active=True)` (guard `if "job_grade" in self.fields`), mirror `LeaveEncashmentForm.__init__`
- [ ] `SalaryStructureLineForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["pay_component", "calculation_type", "amount", "percentage", "sequence"]`
        (exclude `template` — set by the view from the URL `pk`, never form-editable)
  - [ ] `__init__`: narrow `pay_component` queryset to `PayComponent.objects.filter(tenant=self.tenant,
        is_active=True)`; make `calculation_type` not required (`self.fields["calculation_type"
        ].required = False`) since blank defers to the component's own type
- [ ] `EmployeeSalaryStructureForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["employee", "template", "annual_ctc_amount", "effective_from",
        "effective_to", "status", "notes"]`
  - [ ] `__init__`: narrow `employee` queryset to `EmployeeProfile.objects.filter(tenant=self.tenant,
        is_active=True)` if that flag exists on `EmployeeProfile` (else leave unfiltered — verify
        against the real field); narrow `template` queryset to
        `SalaryStructureTemplate.objects.filter(tenant=self.tenant, is_active=True)`

## C. Views (`apps/hrm/views.py`)

- [ ] `paycomponent_list` (`@login_required`) — `crud_list(request,
      PayComponent.objects.filter(tenant=request.tenant), "hrm/salary/paycomponent/list.html",
      search_fields=["name", "code", "description"], filters=[("component_type", "component_type",
      False), ("calculation_type", "calculation_type", False), ("frequency", "frequency", False),
      ("is_active", "is_active", False)], extra_context={"component_type_choices":
      PayComponent.COMPONENT_TYPE_CHOICES, "calculation_type_choices":
      PayComponent.CALCULATION_TYPE_CHOICES, "frequency_choices": PayComponent.FREQUENCY_CHOICES})`
- [ ] `paycomponent_create` / `_edit` / `_delete` — standard `crud_create`/`crud_edit`/`crud_delete`
      wrappers, template paths under `hrm/salary/paycomponent/`
- [ ] `paycomponent_detail` (`@login_required`) — `crud_detail(request, model=PayComponent, pk=pk,
      template="hrm/salary/paycomponent/detail.html")`; template shows a reverse peek of
      `obj.salarystructureline_set.select_related("template")[:10]` (templates using this component)
- [ ] `salarystructuretemplate_list` (`@login_required`) — `crud_list(request,
      SalaryStructureTemplate.objects.filter(tenant=request.tenant).select_related("job_grade"),
      "hrm/salary/salarystructuretemplate/list.html", search_fields=["name", "number"],
      filters=[("job_grade", "job_grade_id", True), ("is_active", "is_active", False)],
      extra_context={"job_grades": JobGrade.objects.filter(tenant=request.tenant)})`
- [ ] `salarystructuretemplate_create` / `_edit` / `_delete` — standard wrappers, template paths
      under `hrm/salary/salarystructuretemplate/`
- [ ] `salarystructuretemplate_detail` (`@login_required`) — `crud_detail(request,
      model=SalaryStructureTemplate, pk=pk, template="hrm/salary/salarystructuretemplate/detail.html",
      select_related=("job_grade",))`; extra_context adds `"lines":
      obj.lines.select_related("pay_component").order_by("sequence", "id")` and
      `"line_form": SalaryStructureLineForm(tenant=request.tenant)` for the inline add form; template
      renders `computed_ctc_total` and the line breakdown table with inline edit/delete actions
- [ ] inline line actions (mirror the 3.11 `TimesheetEntry` inline pattern — managed on the template
      detail page, NOT standalone CRUD):
  - [ ] `salarystructureline_add` (`@login_required`, `@require_POST`) —
        `get_object_or_404(SalaryStructureTemplate, pk=template_pk, tenant=request.tenant)`;
        `SalaryStructureLineForm(request.POST, tenant=request.tenant)`; on valid, `save(commit=False)`,
        set `.tenant = request.tenant`, `.template = template`, `.save()`; `write_audit_log(...,
        "create")`; redirect to `salarystructuretemplate_detail`; on invalid, re-render the detail
        template with the bound form + existing lines (form errors surfaced inline)
  - [ ] `salarystructureline_edit` (`@login_required`) — GET renders an edit form (reuse the same
        detail template or a small standalone form template — pick standalone
        `hrm/salary/salarystructuretemplate/line_form.html` for a clean back-link to the template
        detail); POST updates via `SalaryStructureLineForm(request.POST, instance=line,
        tenant=request.tenant)`; redirect to `salarystructuretemplate_detail`
  - [ ] `salarystructureline_delete` (`@login_required`, `@require_POST`) —
        `get_object_or_404(SalaryStructureLine, pk=pk, tenant=request.tenant)`; delete;
        `write_audit_log(..., "delete")`; redirect to `salarystructuretemplate_detail` of
        `line.template_id`
- [ ] `employeesalarystructure_list` (`@login_required`) — `crud_list(request,
      EmployeeSalaryStructure.objects.filter(tenant=request.tenant).select_related("employee",
      "template"), "hrm/salary/employeesalarystructure/list.html", search_fields=[
      "employee__party__name" (verify exact lookup path used by `leaverequest_list`/
      `floatingholidayelection_list` — mirror exactly), "number"], filters=[("status", "status",
      False), ("employee", "employee_id", True), ("template", "template_id", True)],
      extra_context={"status_choices": EmployeeSalaryStructure.STATUS_CHOICES, "employees":
      EmployeeProfile.objects.filter(tenant=request.tenant), "templates":
      SalaryStructureTemplate.objects.filter(tenant=request.tenant)})`
- [ ] `employeesalarystructure_create` / `_edit` / `_delete` — standard wrappers, template paths
      under `hrm/salary/employeesalarystructure/`
- [ ] `employeesalarystructure_detail` (`@login_required`) — `crud_detail(request,
      model=EmployeeSalaryStructure, pk=pk, template="hrm/salary/employeesalarystructure/detail.html",
      select_related=("employee", "template"))`
- [ ] all new views import `PayComponent`, `SalaryStructureTemplate`, `SalaryStructureLine`,
      `EmployeeSalaryStructure`, `PayComponentForm`, `SalaryStructureTemplateForm`,
      `SalaryStructureLineForm`, `EmployeeSalaryStructureForm` at the top of `views.py` alongside the
      existing HRM imports

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("pay-components/", views.paycomponent_list, name="paycomponent_list")`
- [ ] `path("pay-components/add/", views.paycomponent_create, name="paycomponent_create")`
- [ ] `path("pay-components/<int:pk>/", views.paycomponent_detail, name="paycomponent_detail")`
- [ ] `path("pay-components/<int:pk>/edit/", views.paycomponent_edit, name="paycomponent_edit")`
- [ ] `path("pay-components/<int:pk>/delete/", views.paycomponent_delete, name="paycomponent_delete")`
- [ ] `path("salary-structures/", views.salarystructuretemplate_list, name="salarystructuretemplate_list")`
- [ ] `path("salary-structures/add/", views.salarystructuretemplate_create, name="salarystructuretemplate_create")`
- [ ] `path("salary-structures/<int:pk>/", views.salarystructuretemplate_detail, name="salarystructuretemplate_detail")`
- [ ] `path("salary-structures/<int:pk>/edit/", views.salarystructuretemplate_edit, name="salarystructuretemplate_edit")`
- [ ] `path("salary-structures/<int:pk>/delete/", views.salarystructuretemplate_delete, name="salarystructuretemplate_delete")`
- [ ] `path("salary-structures/<int:template_pk>/lines/add/", views.salarystructureline_add, name="salarystructureline_add")`
- [ ] `path("salary-structure-lines/<int:pk>/edit/", views.salarystructureline_edit, name="salarystructureline_edit")`
- [ ] `path("salary-structure-lines/<int:pk>/delete/", views.salarystructureline_delete, name="salarystructureline_delete")`
- [ ] `path("employee-salary-structures/", views.employeesalarystructure_list, name="employeesalarystructure_list")`
- [ ] `path("employee-salary-structures/add/", views.employeesalarystructure_create, name="employeesalarystructure_create")`
- [ ] `path("employee-salary-structures/<int:pk>/", views.employeesalarystructure_detail, name="employeesalarystructure_detail")`
- [ ] `path("employee-salary-structures/<int:pk>/edit/", views.employeesalarystructure_edit, name="employeesalarystructure_edit")`
- [ ] `path("employee-salary-structures/<int:pk>/delete/", views.employeesalarystructure_delete, name="employeesalarystructure_delete")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `PayComponent` — `list_display = ("name", "code", "component_type",
      "calculation_type", "frequency", "is_taxable", "include_in_ctc", "is_active")`, `list_filter =
      ("tenant", "component_type", "calculation_type", "frequency", "is_active")`, `search_fields =
      ("name", "code")`
- [ ] register `SalaryStructureTemplate` — `list_display = ("number", "name", "job_grade",
      "annual_ctc_amount", "currency", "is_active")`, `list_filter = ("tenant", "job_grade",
      "is_active")`, `search_fields = ("number", "name")`
- [ ] register `SalaryStructureLine` as a `TabularInline` on `SalaryStructureTemplateAdmin` (`model =
      SalaryStructureLine`, `extra = 0`, `fields = ("pay_component", "calculation_type", "amount",
      "percentage", "sequence")`) — mirrors the inline-on-template UI pattern; also register a thin
      standalone `SalaryStructureLineAdmin` for direct lookup if useful (optional)
- [ ] register `EmployeeSalaryStructure` — `list_display = ("number", "employee", "template",
      "annual_ctc_amount", "effective_from", "effective_to", "status")`, `list_filter = ("tenant",
      "status")`, `search_fields = ("number", "employee__party__name")` (match the real lookup path
      confirmed in Section C)

## F. Templates (`templates/hrm/salary/<entity>/<page>.html`)

- [ ] `salary/paycomponent/list.html` — filter bar: search `q`, `component_type` select (from
      `component_type_choices`), `calculation_type` select (from `calculation_type_choices`),
      `frequency` select (from `frequency_choices`), `is_active` select; columns: name, code,
      component_type badge, calculation_type, frequency, is_taxable/include_in_ctc icons, is_active
      badge, Actions (view/edit/delete POST+confirm+csrf); `{% include "partials/pagination.html" %}`;
      `.empty-state`. Badge classes per L33: `earning`→`badge-green`, `statutory_deduction`→
      `badge-red`, `voluntary_deduction`→`badge-amber`, `reimbursement`→`badge-info`,
      `variable`→`badge-slate`; always `{% else %}{{ obj.get_component_type_display }}`
- [ ] `salary/paycomponent/detail.html` — show all fields incl. defaults, cap, requires_bill;
      Actions sidebar (Edit/Delete + Back to List); "used in templates" reverse-peek list
- [ ] `salary/paycomponent/form.html` — standard form; JS/conditional note (not required, just a
      hint) that `variable_subtype` only applies when `component_type=variable`
- [ ] `salary/salarystructuretemplate/list.html` — filter bar: search `q`, `job_grade` select (from
      `job_grades`, `|stringformat:"d"` pk-compare), `is_active` select; columns: number, name,
      job_grade, annual_ctc_amount, currency, computed_ctc_total, is_active badge, Actions
      (view/edit/delete); pagination include; empty-state
- [ ] `salary/salarystructuretemplate/detail.html` — header fields incl. `computed_ctc_total` vs.
      `annual_ctc_amount` (flag a variance if they differ materially); **inline line breakdown
      table** (component, calc type, amount/percentage, resolved amount, sequence, Actions
      edit/delete per line via POST forms + csrf) + an inline "Add line" form
      (`SalaryStructureLineForm`) posting to `salarystructureline_add`; Actions sidebar (Edit/Delete
      template + Back to List)
- [ ] `salary/salarystructuretemplate/form.html` — standard form (name, job_grade, annual_ctc_amount,
      currency, is_active, description)
- [ ] `salary/salarystructuretemplate/line_form.html` — small standalone edit form for a single line
      (pay_component, calculation_type, amount, percentage, sequence) with a back-link to the parent
      template's detail page
- [ ] `salary/employeesalarystructure/list.html` — filter bar: search `q`, `status` select (from
      `status_choices`), `employee` select (from `employees`, pk-compare), `template` select (from
      `templates`, pk-compare); columns: number, employee, template, annual_ctc_amount,
      effective_from, effective_to, status badge (`active`→`badge-green`, `superseded`→
      `badge-muted`), Actions (view/edit/delete); pagination include; empty-state
- [ ] `salary/employeesalarystructure/detail.html` — show employee/template/annual_ctc_amount/
      effective dates/status badge/notes; Actions sidebar (Edit/Delete + Back to List); note near
      status: superseding = edit this row to `status=superseded` + set `effective_to`, then create a
      new active assignment
- [ ] `salary/employeesalarystructure/form.html` — standard form

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add a new idempotent block (after the existing Holiday/Timesheet blocks) creating, per tenant,
      via `get_or_create(tenant=tenant, name=...)`:
  - [ ] ~6-8 `PayComponent` rows:
    - [ ] "Basic" — `component_type="earning"`, `calculation_type="fixed_amount"`,
          `frequency="monthly"`, `is_taxable=True`, `include_in_ctc=True`
    - [ ] "HRA" — `component_type="earning"`, `calculation_type="pct_of_basic"`,
          `default_percentage=40`, `frequency="monthly"`, `is_taxable=True`
    - [ ] "Provident Fund — Employee" — `component_type="statutory_deduction"`,
          `calculation_type="pct_of_basic"`, `default_percentage=12`, `contribution_side="employee"`,
          `frequency="monthly"`, `is_taxable=False`
    - [ ] "Provident Fund — Employer" — `component_type="statutory_deduction"`,
          `calculation_type="pct_of_basic"`, `default_percentage=12`, `contribution_side="employer"`,
          `frequency="monthly"`, `is_taxable=False`, `include_in_ctc=True`
    - [ ] "Professional Tax" — `component_type="statutory_deduction"`,
          `calculation_type="fixed_amount"`, `default_amount=200`, `contribution_side="employee"`,
          `frequency="monthly"`
    - [ ] "Leave Travel Allowance (LTA)" — `component_type="reimbursement"`,
          `calculation_type="fixed_amount"`, `annual_cap_amount=50000`, `requires_bill=True`,
          `frequency="annual"`, `is_taxable=False`
    - [ ] "Performance Bonus" — `component_type="variable"`, `variable_subtype="bonus"`,
          `calculation_type="fixed_amount"`, `frequency="one_time"`, `is_taxable=True`
    - [ ] (optional 8th) "Special Allowance" — `component_type="earning"`,
          `calculation_type="fixed_amount"`, `frequency="monthly"` — a balancing/plug component
  - [ ] 1-2 `SalaryStructureTemplate` rows, each tied to an existing seeded `JobGrade` (reuse, don't
        create new grades): `name="<grade> — Standard CTC"`, `annual_ctc_amount=` a realistic figure
        (e.g. 600000/1200000), `currency="USD"` (or the tenant's convention if one already exists in
        the seeder — check), `is_active=True`
  - [ ] for each template, `get_or_create` `SalaryStructureLine` rows wiring Basic/HRA/PF-EE/PF-ER/
        Professional Tax (+ optionally LTA) with `sequence` 10/20/30/40/50 — use
        `get_or_create(tenant=tenant, template=template, pay_component=component, defaults={...})`
        per the unique_together
  - [ ] 1-2 `EmployeeSalaryStructure` rows against existing seeded `EmployeeProfile` rows:
        `get_or_create(tenant=tenant, employee=emp, status="active", defaults={"template": template,
        "annual_ctc_amount": template.annual_ctc_amount, "effective_from": <a past date, e.g. start of
        current fiscal year>, "status": "active"})` — guard so a second seeder run doesn't try to
        create a second "active" row for the same employee (the `clean()` active-uniqueness check
        only fires via `full_clean()`/forms, not bare `.create()`, so the seeder itself must
        explicitly check `.filter(tenant=tenant, employee=emp, status="active").exists()` first)
- [ ] add the 4 models to the `--flush` wipe order in dependency sequence (children first):
      `EmployeeSalaryStructure` → `SalaryStructureLine` → `SalaryStructureTemplate` → `PayComponent`
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — each new block is itself idempotent, no new top-level guard needed

## H. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.13"]`:
      ```python
      "3.13": {
          "Pay Components": "hrm:paycomponent_list",                                        # bullet
          "Salary Structure Templates": "hrm:salarystructuretemplate_list",                  # bullet
          "Variable Pay": "hrm:paycomponent_list?component_type=variable",                   # bullet
          "Tax Components": "hrm:paycomponent_list?component_type=statutory_deduction",      # bullet
          "Reimbursements": "hrm:paycomponent_list?component_type=reimbursement",             # bullet
          "Employee Salary Assignments": "hrm:employeesalarystructure_list",                 # extra
      },
      ```
      — all 5 NavERP.md 3.13 bullets go Live; confirm the deep-link `?component_type=` query params
      match the nav's most-specific-match highlighting convention (same pattern as 3.11's
      `?status=pending`)

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0024_...py` (field/index/unique_together names
      match the plan)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:paycomponent_*`, `hrm:salarystructuretemplate_*`,
      `hrm:salarystructureline_*`, `hrm:employeesalarystructure_*` URL returns 200/302 when logged in
      as a tenant admin; no `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR check —
      any of the 4 models' pk belonging to tenant A returns 404 when fetched as tenant B; the
      `SalaryStructureLine` `unique_together` violation (same component added twice to one template)
      surfaces a form error, not a 500; `EmployeeSalaryStructure.clean()`'s at-most-one-active guard
      blocks a second active row for the same employee via the form (re-renders with the error); the
      `?component_type=variable/statutory_deduction/reimbursement` deep-links each render the
      filtered subset correctly
- [ ] sidebar: confirm 3.13 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.13 bullets: Pay Components / Salary
      Structure Templates / Variable Pay / Tax Components / Reimbursements all live; bump the HRM +
      project-wide test-count lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.13 section: document `PayComponent`/
      `SalaryStructureTemplate`/`SalaryStructureLine`/`EmployeeSalaryStructure` models, the
      `computed_ctc_total`/`resolved_amount()` derived-value convention, the inline-line-on-template
      UI pattern, the new LIVE_LINKS entries (incl. the `?component_type=` deep-links), the extended
      seeder block, and mark all 5 bullets of 3.13 as built (bump the module's sub-module-count table
      if present)

## Later passes / deferred (carried over from research-salary.md — do not build this pass)

- Payroll run / calculation engine (pro-ration, attendance/leave integration, arrears) — 3.14 Payroll
  Processing, consuming `EmployeeSalaryStructure` + `PayComponent` as inputs. **3.13 must not post to
  the GL or create a payroll run** — `accounting.PayrollRun` already owns that (lesson L29).
- Payslip generation / YTD statements / total-rewards statements — presentation layer for 3.14.
- Statutory filing / challan generation (PF ECR, ESI return, TDS Form 16/24Q) — out of scope; NavERP
  is not a statutory filing system.
- Full arbitrary formula engine referencing any other component (Keka/Darwinbox-style) — the 4-model
  scope covers fixed/%-of-basic/%-of-CTC/%-of-gross; a generic expression evaluator is deferred.
- Compensation review cycles / multi-level approval workflow (Workday budget pools + manager
  proposals, BambooHR compensation planning) — `EmployeeSalaryStructure.status` stays a simple
  active/superseded state.
- Claims / expense-tracking for reimbursements (submitting a bill against a component, tracking
  consumption against `annual_cap_amount`) — `requires_bill` is a flag only; the claim
  submission/approval workflow is a future Reimbursement Claims feature (or Module 13 Documents for
  attachment storage).
- Statutory eligibility-threshold enforcement (e.g. ESI wage-ceiling check against actual gross) —
  `contribution_side`/`annual_cap_amount` capture the definition; per-run enforcement is 3.14's job.
- Multi-currency compensation — `currency` stays a plain CharField; migrating to FK
  `accounting.Currency` is a note for a future pass if multi-currency payroll becomes a requirement.
- Pay-group / multi-entity structure scoping (different templates per legal entity/location) —
  `SalaryStructureTemplate` could later gain an optional `core.OrgUnit`/location scope; not needed for
  a single-pay-group v1.
- Benefits administration (health/dental/401k enrollment carrier integrations) — out of scope for a
  Django-only pass; the resulting payroll deduction only needs a `PayComponent` row, already supported.
- True multi-base percentage resolution (`pct_of_basic` vs. `pct_of_gross` resolving against distinct
  stored subtotals rather than both falling back to `annual_ctc_amount`) — noted as a v1
  simplification in `SalaryStructureLine.resolved_amount()`; revisit once 3.14 introduces real
  gross-pay computation to resolve against.

## Review

(filled in at the end)

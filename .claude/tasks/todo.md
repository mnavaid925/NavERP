---
# HRM 3.14 Payroll Processing (payroll) — plan from research-payroll.md (2026-07-04)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the **operational** payroll
run layer on top of 3.13's compensation *definition* layer: computes per-employee payslips from each
employee's active `EmployeeSalaryStructure`, routes the run through an approval workflow, supports
salary holds + arrears + bonus, and hands the rolled-up totals off to `accounting.PayrollRun` for GL
posting (lesson **L29** — HRM never builds a `JournalEntry`). 3 new models, all in `apps/hrm/models.py`.
Scope decision from research: **no `PayrollAdjustment` model** — flat `arrears_amount`/`bonus_amount`
fields on `Payslip` (+ mirrored `PayslipLine` snapshot rows) are sufficient for v1.

NavERP.md 3.14 bullets (exact text, all 5 go Live this pass):
- Payroll Run — Monthly processing, calculation engine.
- Payroll Approval — Multi-level approval before disbursement.
- Salary Holds — Hold salary for specific employees.
- Arrears Calculation — Retroactive calculations.
- Bonus Processing — Performance bonus, ex-gratia.

Reuses (no duplication): `hrm.EmployeeProfile`, `hrm.EmployeeSalaryStructure` (+ its
`template.lines`/`resolved_amount()`), `hrm.PayComponent.COMPONENT_TYPE_CHOICES`,
`accounting.PayrollRun` (existing, `apps/accounting/models_advanced.py:162`), `settings.AUTH_USER_MODEL`.

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `PayrollCycle(TenantNumbered, NUMBER_PREFIX="PRC")` — the HRM operational run header (named
      distinctly from `accounting.PayrollRun` per the research coordination rule):
  - [ ] `period_start` — DateField()
  - [ ] `period_end` — DateField()
  - [ ] `pay_date` — DateField()
  - [ ] `cycle_type` — CharField(max_length=20, choices=`CYCLE_TYPE_CHOICES`, default="regular") —
        `[("regular","Regular"),("off_cycle","Off-Cycle"),("bonus","Bonus")]` — driver: Rippling
        unlimited off-cycle runs / Gusto "Extra Pay" bonus payroll / Zoho off-cycle vs regular
        distinction; gates whether approval is enforced (Gusto: off-cycle/bonus MAY skip approval)
  - [ ] `status` — CharField(max_length=20, choices=`STATUS_CHOICES`, default="draft") —
        `[("draft","Draft"),("pending_approval","Pending Approval"),("approved","Approved"),
        ("rejected","Rejected"),("locked","Locked")]` — driver: Workday calculate→commit two-phase
        lifecycle + greytHR "lock payroll" + Darwinbox RIVeR stages, collapsed to a buildable state
        machine
  - [ ] `submitted_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=models.SET_NULL`, `null=True,
        blank=True`, `related_name="hrm_payroll_cycle_submissions"`, `editable=False`
  - [ ] `submitted_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `approved_by` — FK `settings.AUTH_USER_MODEL`, `on_delete=models.SET_NULL`, `null=True,
        blank=True`, `related_name="hrm_payroll_cycle_approvals"`, `editable=False`
  - [ ] `approved_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] `rejection_reason` — TextField(blank=True)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `accounting_payroll_run` — FK `"accounting.PayrollRun"`, `on_delete=models.SET_NULL,
        null=True, blank=True, editable=False, related_name="hrm_cycles"` — set on lock; carries the
        rolled-up totals into accounting's existing GL-posting flow (`payroll_run_post`)
  - [ ] `class Meta`: `ordering = ["-pay_date"]`; `unique_together = ("tenant", "number")`; index
        `models.Index(fields=["tenant", "status"], name="hrm_prc_tenant_status_idx")`
  - [ ] derived **properties** (NOT stored fields, aggregate over `self.payslips.all()`):
    - [ ] `headcount` → `self.payslips.count()`
    - [ ] `total_gross` → `sum(p.gross_pay for p in self.payslips.all()) or Decimal("0")` (use
          `.aggregate(Sum(...))` for efficiency — see performance note below)
    - [ ] `total_deductions` → same pattern, sums `total_deductions`
    - [ ] `total_net` → same pattern, sums `net_pay`
    - [ ] `is_locked` → `self.status == "locked"`
  - [ ] **Performance note (bake in from day 1, don't wait for performance-reviewer):** implement the
        three `total_*` properties with a single `self.payslips.aggregate(g=Sum("gross_pay"),
        d=Sum("total_deductions"), n=Sum("net_pay"))` call (one query, not three separate `.aggregate()`
        calls) — cache the dict on first access per-request if convenient, but at minimum don't issue 3
        separate queries when the detail page renders all three
  - [ ] `__str__` → `f"{self.number} · {self.get_cycle_type_display()} · {self.period_start}–{self.period_end}"`

- [ ] `Payslip(TenantNumbered, NUMBER_PREFIX="PSL")` — one per employee per cycle:
  - [ ] `cycle` — FK `"hrm.PayrollCycle"`, `on_delete=models.CASCADE`, `related_name="payslips"`
  - [ ] `employee` — FK `"hrm.EmployeeProfile"`, `on_delete=models.PROTECT` — PROTECT (not CASCADE/
        SET_NULL) so a payslip's employee can't vanish out from under paid-history
  - [ ] `salary_structure` — FK `"hrm.EmployeeSalaryStructure"`, `on_delete=models.SET_NULL,
        null=True, blank=True`, `related_name="payslips"` — the structure this payslip was computed
        from (calc-engine input/audit trail)
  - [ ] `days_in_period` — PositiveSmallIntegerField()
  - [ ] `days_worked` — PositiveSmallIntegerField() — defaults to `days_in_period` at generation time
        unless overridden (mid-period joiner/leaver pro-ration)
  - [ ] `lop_days` — DecimalField(max_digits=5, decimal_places=2, default=0)
  - [ ] `lop_amount` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False) —
        derived at generation/`recompute()`
  - [ ] `gross_pay` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `total_deductions` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `net_pay` — DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
  - [ ] `arrears_amount` — DecimalField(max_digits=14, decimal_places=2, default=0) — retroactive pay
        from a back-dated structure revision or new-joinee arrears (Keka/greytHR/Zoho); form-editable
        while cycle is draft
  - [ ] `bonus_amount` — DecimalField(max_digits=14, decimal_places=2, default=0) — performance bonus/
        ex-gratia, taxed as a normal earning (Gusto/Keka/factoHR); form-editable while cycle is draft
  - [ ] `on_hold` — BooleanField(default=False) — Salary Holds bullet (Keka "Salary on Hold", greytHR
        "Hold Salary Payout") — payslip still computed for statutory-compliance totals, excluded from
        disbursement (disbursement/bank-file itself is out of scope)
  - [ ] `hold_reason` — TextField(blank=True)
  - [ ] `released_at` — DateTimeField(null=True, blank=True, editable=False)
  - [ ] NO independent status field — "locked" is derived from `self.cycle.is_locked` (avoid a second
        state machine per the research's explicit recommendation)
  - [ ] `class Meta`: `ordering = ["cycle", "employee__party__name"]`; `unique_together = ("tenant",
        "cycle", "employee")` — one payslip per employee per cycle; indexes
        `models.Index(fields=["tenant", "cycle"], name="hrm_psl_tenant_cycle_idx")`,
        `models.Index(fields=["tenant", "employee"], name="hrm_psl_tenant_emp_idx")`
  - [ ] `is_locked` **property** → `self.cycle.is_locked`
  - [ ] `recompute()` **method** — the calculation engine (see spec below); (re)derives
        `gross_pay`/`total_deductions`/`net_pay`/`lop_amount`, rebuilds this payslip's `PayslipLine`
        rows (delete existing lines for this payslip, recreate from resolved structure lines +
        arrears/bonus/LOP), then `self.save(update_fields=[...])`. Callable standalone (used by both
        `payrollcycle_generate` for the initial build and `payslip_edit` after an arrears/bonus/
        days_worked/lop_days change) — **must raise/guard against being called when
        `self.cycle.is_locked`** (a locked cycle's payslips are immutable)
  - [ ] `__str__` → `f"{self.number} · {self.employee} · {self.cycle.number}"`

- [ ] `PayslipLine(TenantOwned)` — per-component snapshot, no own number:
  - [ ] `payslip` — FK `"hrm.Payslip"`, `on_delete=models.CASCADE`, `related_name="lines"`
  - [ ] `component_name` — CharField(max_length=150) — copied string label, NOT a live FK to
        `PayComponent` (so a later component rename/edit never rewrites historical payslips —
        Workday's immutable payroll-results-worklet convention)
  - [ ] `component_type` — CharField(max_length=20, choices=`COMPONENT_TYPE_CHOICES`) — union of
        `PayComponent.COMPONENT_TYPE_CHOICES` (`earning`/`statutory_deduction`/`voluntary_deduction`/
        `reimbursement`/`variable`) **plus** `("arrears","Arrears")`, `("bonus","Bonus")`,
        `("lop","Loss of Pay")` — build this list explicitly in `PayslipLine` (e.g.
        `PayComponent.COMPONENT_TYPE_CHOICES + [("arrears","Arrears"),("bonus","Bonus"),
        ("lop","Loss of Pay")]`) rather than re-typing the base 5, so a future `PayComponent` type
        addition doesn't silently drift out of sync
  - [ ] `amount` — DecimalField(max_digits=14, decimal_places=2) — resolved, pro-rated value for this
        line on this payslip (may be negative for the `lop` line — see calc engine)
  - [ ] `contribution_side` — CharField(max_length=10, choices=`PayComponent.CONTRIBUTION_SIDE_CHOICES`,
        blank=True, default="") — snapshotted from the source `PayComponent.contribution_side` (blank
        for arrears/bonus/lop synthetic lines) so `payrollcycle_lock`'s employee-tax-vs-employer-tax
        roll-up doesn't need to re-join back to `PayComponent`/`SalaryStructureLine` after the fact
  - [ ] `sequence` — PositiveSmallIntegerField(default=0)
  - [ ] `class Meta`: `ordering = ["sequence", "id"]`; index `models.Index(fields=["tenant",
        "payslip"], name="hrm_psll_tenant_payslip_idx")`
  - [ ] `__str__` → `f"{self.payslip} · {self.component_name}"`

- [ ] one incremental migration `apps/hrm/migrations/0025_payrollcycle_payslip_payslipline_and_more.py`
      (NOT `0001_initial`; last is `0024_paycomponent_salarystructuretemplate_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ

## Calculation engine — spec `Payslip.recompute()` exactly this way

- [ ] guard: if `self.cycle.is_locked` → raise (e.g. `ValidationError`/a plain `RuntimeError` — pick
      one and use it consistently across `recompute()` and the generate/edit views) — a locked cycle's
      payslips are immutable; corrections need a new `off_cycle` `PayrollCycle`
- [ ] resolve the employee's active structure lines: `structure = self.salary_structure`; if
      `structure` and `structure.template_id`: `lines = structure.template.lines.select_related(
      "pay_component").order_by("sequence", "id")`; else `lines = []` (no structure → zero earnings,
      payslip still exists so headcount/hold state is trackable)
- [ ] convert each line's annual `resolved_amount()` to a **monthly** amount:
      `monthly = (line.resolved_amount() / Decimal("12")).quantize(Decimal("0.01"))`
- [ ] split lines into EARNINGS (`pay_component.component_type in
      {"earning","reimbursement","variable"}`) vs DEDUCTIONS (`component_type in
      {"statutory_deduction","voluntary_deduction"}`)
- [ ] pro-rate EARNINGS only by `ratio = Decimal(self.days_worked) / Decimal(self.days_in_period)` if
      `self.days_in_period` else `Decimal("1")` (default `days_worked = days_in_period` at generation
      unless explicitly overridden — mid-period joiner/leaver case); DEDUCTIONS are NOT pro-rated by
      days_worked (statutory deductions are computed on the pro-rated gross downstream, not
      double-pro-rated — keep this simple: deductions resolve off the component's own
      `resolved_amount()`/12 unmodified for v1, note this as a v1 simplification matching the
      "generic statutory line" scope, not a full attendance-linked deduction proration engine)
- [ ] `period_gross = sum(pro-rated earning amounts)` (before LOP/arrears/bonus)
- [ ] `lop_amount = ((period_gross / Decimal(self.days_in_period)) * self.lop_days).quantize(
      Decimal("0.01"))` if `self.days_in_period` else `Decimal("0")`
- [ ] `gross_pay = (period_gross - lop_amount + self.arrears_amount + self.bonus_amount).quantize(
      Decimal("0.01"))`
- [ ] `total_deductions = sum(deduction line monthly amounts).quantize(Decimal("0.01"))`
- [ ] `net_pay = (gross_pay - total_deductions).quantize(Decimal("0.01"))`
- [ ] rebuild `PayslipLine`s: `self.lines.all().delete()`, then bulk-create:
  - [ ] one line per pro-rated EARNING (`component_type=pay_component.component_type`,
        `component_name=pay_component.name`, `amount=` the pro-rated value,
        `contribution_side=pay_component.contribution_side`, `sequence=pay_component.display_order`)
  - [ ] one line per DEDUCTION (same shape, `amount=` the resolved monthly deduction, negative sign
        convention documented — pick **positive magnitude with `component_type` distinguishing sign
        semantics** (i.e. store deductions as positive numbers, the type tells you it's a deduction) to
        match the existing `SalaryStructureLine`/`PayComponent` convention of no signed amounts; note
        this explicitly in the model docstring
  - [ ] an `arrears` line (`component_type="arrears"`, `component_name="Arrears"`,
        `amount=self.arrears_amount`) only if `self.arrears_amount != 0`
  - [ ] a `bonus` line (`component_type="bonus"`, `component_name="Bonus"`,
        `amount=self.bonus_amount`) only if `self.bonus_amount != 0`
  - [ ] a `lop` line (`component_type="lop"`, `component_name="Loss of Pay"`,
        `amount=self.lop_amount`) only if `self.lop_amount != 0`
  - [ ] use consistent `sequence` numbering so the payslip renders earnings, then arrears/bonus, then
        LOP, then deductions in a sensible print order (e.g. earnings 1-89, arrears/bonus 90-94, lop
        95, deductions 100+)
- [ ] `self.gross_pay`, `self.total_deductions`, `self.net_pay`, `self.lop_amount` set on the instance;
      `self.save(update_fields=["gross_pay","total_deductions","net_pay","lop_amount","updated_at"])`
- [ ] use `Decimal` throughout (never float); `.quantize(Decimal("0.01"))` at every derived-amount step
      per the research's explicit convention

## `payrollcycle_generate` — the batch driver around `recompute()`

- [ ] `@login_required`, `@require_POST` view, only runs while `cycle.status == "draft"` (else
      `messages.error` + redirect to detail — regeneration is draft-only, matches Keka's rollback
      convention: correction after lock needs a new off-cycle cycle)
- [ ] inside `transaction.atomic()`:
  - [ ] delete existing `cycle.payslips.all()` (cascades their `PayslipLine`s) — safe re-run/rollback
        while draft
  - [ ] for each `hrm.EmployeeProfile` in `tenant` that has an `EmployeeSalaryStructure` with
        `status="active"` as of `cycle.period_end` (i.e. `effective_from <= cycle.period_end` and
        (`effective_to` is null or `effective_to >= cycle.period_start`) — pick the simpler
        `status="active"` filter as the v1 baseline per the research's "Include/exclude headcount by
        pay group" table-stakes note; document the date-window refinement as a fast-follow if the
        simpler filter is used):
    - [ ] `Payslip.objects.create(tenant=tenant, cycle=cycle, employee=employee,
          salary_structure=structure, days_in_period=<days in cycle.period_start..period_end
          inclusive>, days_worked=days_in_period)`
    - [ ] call `payslip.recompute()` immediately after create
  - [ ] `write_audit_log(request.user, cycle, "update", {"action": "generate", "headcount": N})`
- [ ] redirect to `payrollcycle_detail`; `messages.success` with the generated headcount

## Approval workflow + hand-off (POST actions, mirror the 3.12 `FloatingHolidayElection` pattern)

- [ ] `payrollcycle_submit` (`@login_required`, `@require_POST`) — only from `status="draft"`;
      set `status="pending_approval"`, `submitted_by=request.user`, `submitted_at=timezone.now()`;
      **decision (documented per the brief):** an `off_cycle`/`bonus` `cycle_type` MAY skip approval —
      allow this same view to detect `cycle.cycle_type != "regular"` and go straight to submit-and-lock
      in one action if a `request.POST.get("skip_approval")` flag (or simply: for non-regular cycles,
      submit transitions directly to `"approved"` instead of `"pending_approval"`, then a separate lock
      action still required) — **pick the simpler rule: non-regular cycles submit straight to
      `"approved"`** (still requires an explicit `payrollcycle_lock` call to actually hand off to
      accounting — lock is never implicit); write this decision into the view's docstring so it's not
      re-litigated later
- [ ] `payrollcycle_approve` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending_approval"`; set `status="approved"`, `approved_by=request.user`,
      `approved_at=timezone.now()`; `write_audit_log(..., "update", {"action": "approve"})`
- [ ] `payrollcycle_reject` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending_approval"`; set `status="rejected"`, `approved_by=request.user`,
      `rejection_reason=request.POST.get("rejection_reason", "").strip()[:2000]`;
      `write_audit_log(..., "update", {"action": "reject"})` — mirror
      `floatingholidayelection_reject`'s truncation/no-op-if-not-pending pattern exactly
- [ ] `payrollcycle_lock` (`@tenant_admin_required`, `@require_POST`) — only from `status="approved"`;
      inside `transaction.atomic()`:
  - [ ] roll up across `cycle.payslips.select_related(None).prefetch_related("lines")`:
    - [ ] `headcount = cycle.payslips.count()`
    - [ ] `gross_wages = cycle.payslips.aggregate(Sum("gross_pay"))["gross_pay__sum"] or Decimal("0")`
    - [ ] `employee_tax = ` sum of `PayslipLine.amount` where
          `component_type="statutory_deduction"` and `contribution_side="employee"` across all of the
          cycle's payslips (`PayslipLine.objects.filter(payslip__cycle=cycle,
          component_type="statutory_deduction", contribution_side="employee").aggregate(
          Sum("amount"))`)
    - [ ] `employer_tax = ` same filter with `contribution_side="employer"`
    - [ ] `deductions = ` sum of `PayslipLine.amount` where `component_type="voluntary_deduction"`
          (regardless of side) across the cycle's payslips
    - [ ] `benefits = Decimal("0")` for v1 (no benefits-specific component_type modeled yet — note this
          as a placeholder the accounting form already defaults; `PayrollRun.benefits` stays 0 unless a
          later pass adds a benefits component_type)
    - [ ] holds still count toward these totals (Keka/greytHR: held salaries still hit statutory
          totals) — do NOT exclude `on_hold` payslips from the roll-up
  - [ ] `from apps.accounting.models_advanced import PayrollRun as AccountingPayrollRun` (import at
        top of `apps/hrm/models.py` or inside the view — **prefer a lazy import inside the view/method**
        to avoid a hard cross-app import at module load time; verify no circular-import issue exists
        first, else use `django.apps.apps.get_model("accounting", "PayrollRun")`)
  - [ ] `accounting_run = AccountingPayrollRun.objects.create(tenant=request.tenant,
        period_start=cycle.period_start, period_end=cycle.period_end, pay_date=cycle.pay_date,
        headcount=headcount, gross_wages=gross_wages, employee_tax=employee_tax,
        employer_tax=employer_tax, benefits=Decimal("0"), deductions=deductions)` — `net_pay` is
        derived by `AccountingPayrollRun.save()` automatically; `status` stays its model default
        (`"draft"`) — **HRM never sets `status="posted"` or builds a `JournalEntry`**
  - [ ] `cycle.accounting_payroll_run = accounting_run`; `cycle.status = "locked"`; save both with
        explicit `update_fields`
  - [ ] `write_audit_log(request.user, cycle, "update", {"action": "lock", "accounting_payroll_run":
        accounting_run.number})`
  - [ ] `messages.success` linking to the created accounting PayrollRun (e.g. "Locked — created
        accounting PayrollRun {number}, post it from Accounting → Payroll to generate the GL entry.")

## Salary holds

- [ ] `payslip_hold` (`@tenant_admin_required`, `@require_POST`) — gate: allowed while
      `payslip.cycle.status in {"draft", "pending_approval", "approved"}` (i.e. anytime BEFORE
      `locked` — a hold is a pre-disbursement decision; once the cycle is locked and handed to
      accounting, a hold no longer has meaning for that payslip — document this gate choice in the
      view's docstring since the brief flags it as "your call"); set `on_hold=True`,
      `hold_reason=request.POST.get("hold_reason","").strip()[:2000]`; `write_audit_log(...,
      {"action": "hold"})`
- [ ] `payslip_release` (`@tenant_admin_required`, `@require_POST`) — same gate (not locked); set
      `on_hold=False`, `released_at=timezone.now()`; keep `hold_reason` as history (don't clear it);
      `write_audit_log(..., {"action": "release"})`
- [ ] both redirect to `payslip_detail`

## Payslip edit (arrears/bonus/hold-adjacent fields, draft-cycle only)

- [ ] `payslip_edit` (`@login_required`) — only while `payslip.cycle.status == "draft"` (else
      `messages.error` "A locked/submitted cycle's payslips cannot be edited." + redirect to detail);
      `PayslipForm` covers `days_worked`, `lop_days`, `arrears_amount`, `bonus_amount` (NOT `on_hold`/
      `hold_reason` — those go through the dedicated hold/release actions, not a generic edit form);
      on valid POST save, call `obj.recompute()` immediately after `form.save()` so gross/deductions/
      net + lines reflect the new inputs before redirecting to `payslip_detail`

## B. Forms (`apps/hrm/forms.py`)

- [ ] `PayrollCycleForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["period_start", "period_end", "pay_date", "cycle_type", "notes"]` (exclude
        `number`/`status`/`submitted_by`/`submitted_at`/`approved_by`/`approved_at`/
        `rejection_reason`/`accounting_payroll_run` — all workflow/derived, never form fields)
  - [ ] no custom `__init__` needed (no FK dropdowns to narrow)
- [ ] `PayslipForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["days_worked", "lop_days", "arrears_amount", "bonus_amount"]` (exclude
        `cycle`/`employee`/`salary_structure`/`days_in_period`/`lop_amount`/`gross_pay`/
        `total_deductions`/`net_pay`/`on_hold`/`hold_reason`/`released_at` — set by the view/generate
        flow or the dedicated hold/release actions, never generic-form-editable)
  - [ ] no create view for `Payslip` (payslips are only created via `payrollcycle_generate`) — this
        form is edit-only

## C. Views (`apps/hrm/views.py`)

- [ ] `payrollcycle_list` (`@login_required`) — `crud_list(request,
      PayrollCycle.objects.filter(tenant=request.tenant), "hrm/payroll/payrollcycle/list.html",
      search_fields=["number", "notes"], filters=[("status", "status", False), ("cycle_type",
      "cycle_type", False)], extra_context={"status_choices": PayrollCycle.STATUS_CHOICES,
      "cycle_type_choices": PayrollCycle.CYCLE_TYPE_CHOICES})`
- [ ] `payrollcycle_create` — standard `crud_create` wrapper (`PayrollCycleForm`, template
      `hrm/payroll/payrollcycle/form.html`, success_url `hrm:payrollcycle_detail` of the new obj —
      note `crud_create` redirects to a fixed `success_url` string; if a post-create redirect to the
      new detail page (not the list) is wanted, mirror however 3.13's `salarystructuretemplate_create`
      does it — verify and match that exact pattern rather than inventing a new one)
- [ ] `payrollcycle_edit` — standard `crud_edit` wrapper, only while `status == "draft"` (else
      `messages.error` + redirect to detail, mirror the `floatingholidayelection_edit` pending-only
      guard pattern exactly)
- [ ] `payrollcycle_delete` (`@login_required`, `@require_POST`) — only while `status == "draft"` AND
      it has no payslips yet (or cascades its payslips — CASCADE FK means deleting the cycle deletes
      its payslips; guard: only allow delete while `draft`, mirror the
      `floatingholidayelection_delete` decided-lock pattern) — else `messages.error` + redirect
- [ ] `payrollcycle_detail` (`@login_required`) — `crud_detail(request, model=PayrollCycle, pk=pk,
      template="hrm/payroll/payrollcycle/detail.html")`; extra_context adds `"payslips":
      cycle.payslips.select_related("employee__party").order_by("employee__party__name")` (the
      cycle-detail hub lists all payslips with links to their detail pages) + the derived
      `total_gross`/`total_deductions`/`total_net`/`headcount` rendered from the model properties
- [ ] `payrollcycle_generate` (`@login_required`, `@require_POST`) — per the Calculation Engine spec
      above
- [ ] `payrollcycle_submit` / `_approve` / `_reject` / `_lock` — per the Approval Workflow spec above
- [ ] `payslip_list` (`@login_required`) — global cross-cycle list for the Salary Holds / Arrears
      Calculation / Bonus Processing nav deep-links: `crud_list(request,
      Payslip.objects.filter(tenant=request.tenant).select_related("cycle", "employee__party"),
      "hrm/payroll/payslip/list.html", search_fields=["number", "employee__party__name"],
      filters=[("cycle", "cycle_id", True), ("employee", "employee_id", True), ("on_hold", "on_hold",
      False)], extra_context={"cycles": PayrollCycle.objects.filter(tenant=request.tenant),
      "employees": EmployeeProfile.objects.filter(tenant=request.tenant)})`
- [ ] `payslip_detail` (`@login_required`) — `crud_detail(request, model=Payslip, pk=pk,
      template="hrm/payroll/payslip/detail.html", select_related=("cycle", "employee__party",
      "salary_structure"))`; extra_context adds `"lines": obj.lines.order_by("sequence", "id")`
- [ ] `payslip_edit` — per the Payslip Edit spec above (draft-cycle-only gate + `recompute()` call
      after save)
- [ ] `payslip_hold` / `payslip_release` — per the Salary Holds spec above
- [ ] NO `payslip_create`/`payslip_delete` standalone views — payslips are lifecycle-managed via
      `payrollcycle_generate` (create) and cascade-delete with their cycle; a delete-one-payslip action
      is out of scope (regenerate the whole cycle instead, matches the draft-only regenerate rule)
- [ ] all new views import `PayrollCycle`, `Payslip`, `PayslipLine`, `PayrollCycleForm`, `PayslipForm`
      at the top of `views.py` alongside the existing HRM imports; import `transaction` from
      `django.db`, `Sum` from `django.db.models` if not already imported

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("payroll-cycles/", views.payrollcycle_list, name="payrollcycle_list")`
- [ ] `path("payroll-cycles/add/", views.payrollcycle_create, name="payrollcycle_create")`
- [ ] `path("payroll-cycles/<int:pk>/", views.payrollcycle_detail, name="payrollcycle_detail")`
- [ ] `path("payroll-cycles/<int:pk>/edit/", views.payrollcycle_edit, name="payrollcycle_edit")`
- [ ] `path("payroll-cycles/<int:pk>/delete/", views.payrollcycle_delete, name="payrollcycle_delete")`
- [ ] `path("payroll-cycles/<int:pk>/generate/", views.payrollcycle_generate, name="payrollcycle_generate")`
- [ ] `path("payroll-cycles/<int:pk>/submit/", views.payrollcycle_submit, name="payrollcycle_submit")`
- [ ] `path("payroll-cycles/<int:pk>/approve/", views.payrollcycle_approve, name="payrollcycle_approve")`
- [ ] `path("payroll-cycles/<int:pk>/reject/", views.payrollcycle_reject, name="payrollcycle_reject")`
- [ ] `path("payroll-cycles/<int:pk>/lock/", views.payrollcycle_lock, name="payrollcycle_lock")`
- [ ] `path("payslips/", views.payslip_list, name="payslip_list")`
- [ ] `path("payslips/<int:pk>/", views.payslip_detail, name="payslip_detail")`
- [ ] `path("payslips/<int:pk>/edit/", views.payslip_edit, name="payslip_edit")`
- [ ] `path("payslips/<int:pk>/hold/", views.payslip_hold, name="payslip_hold")`
- [ ] `path("payslips/<int:pk>/release/", views.payslip_release, name="payslip_release")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `PayrollCycle` — `list_display = ("number", "cycle_type", "period_start",
      "period_end", "pay_date", "status", "accounting_payroll_run")`, `list_filter = ("tenant",
      "cycle_type", "status")`, `search_fields = ("number", "notes")`
- [ ] register `Payslip` — `list_display = ("number", "cycle", "employee", "gross_pay",
      "total_deductions", "net_pay", "on_hold")`, `list_filter = ("tenant", "on_hold")`,
      `search_fields = ("number", "employee__party__name")` (verify exact lookup path matches
      `employeesalarystructure` admin's confirmed path from 3.13)
- [ ] register `PayslipLine` as a `TabularInline` on `PayslipAdmin` (`model = PayslipLine`,
      `extra = 0`, `fields = ("component_name", "component_type", "amount", "contribution_side",
      "sequence")`, `readonly_fields` matching since these are snapshot rows) — also register a thin
      standalone `PayslipLineAdmin` for direct lookup if useful (optional)

## F. Templates (`templates/hrm/payroll/<entity>/<page>.html`)

- [ ] `payroll/payrollcycle/list.html` — filter bar: search `q`, `status` select (from
      `status_choices`), `cycle_type` select (from `cycle_type_choices`); columns: number, cycle_type
      badge, period_start–period_end, pay_date, status badge, headcount, total_net, Actions
      (view/edit-if-draft/delete-if-draft); pagination include; empty-state. Badge classes (**L33,
      colour-named**): `draft`→`badge-muted`, `pending_approval`→`badge-amber`, `approved`→
      `badge-info`, `rejected`→`badge-red`, `locked`→`badge-green`; `cycle_type`:
      `regular`→`badge-info`, `off_cycle`→`badge-amber`, `bonus`→`badge-slate`; always
      `{% else %}{{ obj.get_status_display }}` / `{{ obj.get_cycle_type_display }}` fallback
- [ ] `payroll/payrollcycle/detail.html` — the **cycle-detail hub**: header fields (period, pay_date,
      cycle_type badge, status badge), derived-totals panel (headcount/total_gross/
      total_deductions/total_net), workflow action buttons gated by status (`Generate Payslips` —
      draft only; `Submit for Approval` — draft only, POST+confirm+csrf; `Approve`/`Reject` —
      pending_approval only, tenant-admin, POST+confirm+csrf, reject includes a `rejection_reason`
      textarea; `Lock & Hand Off to Accounting` — approved only, tenant-admin, POST+confirm+csrf,
      confirm text warns this is irreversible); if `accounting_payroll_run` is set, show a link to it
      (`accounting:payrollrun_detail` or whatever its real url name is — verify); **payslip list
      table**: number, employee, gross_pay, total_deductions, net_pay, on_hold badge, link to
      `payslip_detail`; Actions sidebar (Edit-if-draft/Delete-if-draft + Back to List)
- [ ] `payroll/payrollcycle/form.html` — standard form (period_start, period_end, pay_date,
      cycle_type, notes)
- [ ] `payroll/payslip/list.html` — filter bar: search `q`, `cycle` select (from `cycles`,
      `|stringformat:"d"` pk-compare), `employee` select (from `employees`, pk-compare), `on_hold`
      select (True/False); columns: number, cycle, employee, gross_pay, total_deductions, net_pay,
      on_hold badge (`True`→`badge-red "On Hold"`, `False`→`badge-green "Released/Active"`), Actions
      (view/edit-if-draft-cycle); pagination include; empty-state
- [ ] `payroll/payslip/detail.html` — header (cycle link, employee, salary_structure link,
      days_in_period/days_worked, lop_days/lop_amount, arrears_amount, bonus_amount, on_hold badge +
      hold_reason + released_at), derived totals (gross_pay/total_deductions/net_pay), **line
      breakdown table** (component_name, component_type badge, amount, contribution_side, sequence —
      read-only, snapshot data); Actions sidebar: Edit (only if `not obj.is_locked`), Hold/Release POST
      buttons (only if `not obj.is_locked`, toggle based on current `on_hold`), Back to List. Badge
      classes for `component_type`: `earning`→`badge-green`, `statutory_deduction`→`badge-red`,
      `voluntary_deduction`→`badge-amber`, `reimbursement`→`badge-info`, `variable`→`badge-slate`,
      `arrears`→`badge-amber`, `bonus`→`badge-green`, `lop`→`badge-red`; always
      `{% else %}{{ line.get_component_type_display }}` fallback
- [ ] `payroll/payslip/form.html` — standard form (days_worked, lop_days, arrears_amount,
      bonus_amount) with a note that saving triggers an automatic recompute of gross/deductions/net

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_payroll(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_salary(tenant, flush=options["flush"])` (payroll generation needs 3.13's
      `EmployeeSalaryStructure` rows to exist first)
- [ ] `if flush:` child-first wipe: `PayslipLine.objects.filter(tenant=tenant).delete()` →
      `Payslip.objects.filter(tenant=tenant).delete()` → `PayrollCycle.objects.filter(
      tenant=tenant).delete()`
- [ ] `if PayrollCycle.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Payroll data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] create 1 `regular` `PayrollCycle` for the current month:
      `period_start=timezone.localdate().replace(day=1)`, `period_end=` the last day of that month
      (use `calendar.monthrange` or the existing date-util pattern already used elsewhere in
      `seed_hrm.py` — check for an existing helper before hand-rolling), `pay_date=period_end`,
      `cycle_type="regular"`, `status="draft"` (or `"pending_approval"` — pick `"draft"` so the demo
      data still allows exercising `generate`/`submit` manually; document the choice)
- [ ] for each `EmployeeProfile` in `tenant` with an `active` `EmployeeSalaryStructure` (reuse the
      3.13-seeded assignment): create a `Payslip` (`days_in_period`/`days_worked` = the days in the
      seeded period) and call `.recompute()` — mirror the `payrollcycle_generate` view's own logic
      (consider factoring a small shared helper if convenient, but a direct call to the same
      `recompute()` method is sufficient and avoids duplicating the calc engine)
- [ ] optionally set one seeded payslip `on_hold=True` with a demo `hold_reason` (e.g. "Pending
      clearance verification.") to exercise the Salary Holds bullet in seeded data
- [ ] print a summary line: `f"Payroll seeded for '{tenant.name}': 1 cycle ({cycle.number}),
      {Payslip.objects.filter(tenant=tenant).count()} payslip(s)."`
- [ ] add the 3 models to the `--flush` wipe order in dependency sequence (children first):
      `PayslipLine` → `Payslip` → `PayrollCycle` (already specified above — restate here for the
      flush-order checklist)
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## H. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.14"]` (verify the exact query-string highlighting convention against 3.11/
      3.13's existing entries before finalizing):
      ```python
      # 3.14 Payroll Processing — one PayrollCycle/Payslip surface serves all 5 bullets via
      # deep-linked query params (mirrors 3.13's ?component_type= pattern).
      "3.14": {
          "Payroll Run": "hrm:payrollcycle_list",                                   # bullet
          "Payroll Approval": "hrm:payrollcycle_list?status=pending_approval",      # bullet
          "Salary Holds": "hrm:payslip_list?on_hold=True",                         # bullet
          "Arrears Calculation": "hrm:payslip_list",                               # bullet (arrears entered on the payslip)
          "Bonus Processing": "hrm:payrollcycle_list?cycle_type=bonus",             # bullet
      },
      ```
      — all 5 NavERP.md 3.14 bullets go Live; adjust the literal query strings if the real filter
      param names implemented in Section C differ (e.g. confirm `on_hold` filter accepts the string
      `"True"` per `crud_list`'s boolean-string mapping)

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0025_...py` (field/index/unique_together names
      match the plan; confirm the `accounting.PayrollRun` FK doesn't trigger a spurious
      cross-app migration dependency issue — it shouldn't since it's a plain FK-by-string)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm 3.13's `_seed_salary` still runs
      first and the new `_seed_payroll` block generates payslips against it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:payrollcycle_*` and `hrm:payslip_*` URL returns 200/302 when
      logged in as a tenant admin; no `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR
      check — a `PayrollCycle`/`Payslip` pk belonging to tenant A returns 404 when fetched as tenant B;
      `payrollcycle_generate` run twice while draft produces the same headcount (regeneration replaces,
      doesn't duplicate); `payrollcycle_lock` creates exactly one `accounting.PayrollRun` row with the
      correct rolled-up totals (spot-check `gross_wages`/`employee_tax`/`employer_tax`/`deductions`
      arithmetic against the seeded payslip(s) by hand); a second `lock` attempt on an already-locked
      cycle is a no-op (guarded by the `status="approved"` precondition); `payslip_edit`/`payslip_hold`/
      `payslip_release` are blocked (error message, no mutation) once the parent cycle is `locked`;
      `payrollcycle_edit`/`_delete` are blocked once not `draft`; non-admin user gets 403 on
      approve/reject/lock/hold/release (`@tenant_admin_required`); the `?status=pending_approval`,
      `?on_hold=True`, `?cycle_type=bonus` deep-links each render the filtered subset correctly
- [ ] sidebar: confirm 3.14 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.14 bullets: Payroll Run / Payroll Approval /
      Salary Holds / Arrears Calculation / Bonus Processing all live; bump the HRM + project-wide
      test-count lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.14 section: document `PayrollCycle`/`Payslip`/
      `PayslipLine` models, the `recompute()` calculation-engine contract, the approve/reject/lock
      workflow + the `accounting.PayrollRun` hand-off (and that HRM never builds a `JournalEntry` —
      L29), the salary-hold gate rule, the new `LIVE_LINKS["3.14"]` entries (incl. the deep-links), the
      extended seeder block, and mark all 5 bullets of 3.14 as built

## Later passes / deferred (carried over from research-payroll.md — do not build this pass)

- **Full statutory engine** (PF/ESI/PT/TDS slabs, challans, returns, Form 16) — NavERP.md **3.15
  Statutory Compliance**, a separate sub-module; this pass only stores generic
  `statutory_deduction`/`employer`-contribution amounts already modeled by `PayComponent`.
- **Bank file / NEFT / direct-deposit disbursement generation** — external banking integration (ADP,
  Rippling, Gusto, greytHR); out of a single Django pass.
- **Tax-slab TDS/withholding computation engine** — needs annual tax-regime rules (NavERP.md 3.16 Tax
  & Investment); this pass stores the deduction amount but does not compute it from a slab table.
- **Payslip PDF rendering + email delivery + employee self-service download portal** — templating/PDF
  generation and email dispatch; defer to an integration pass.
- **Configurable N-level approval criteria engine** (Zoho's WHEN/AND/OR custom approval builder) — v1
  ships a fixed submit→approve/reject two-step (with the off_cycle/bonus straight-to-approved shortcut
  documented above); a rules-based configurable chain is differentiator/deferred.
- **Automatic arrears computation by diffing salary-structure history** — v1 takes `arrears_amount` as
  a manually-entered value on the payslip (edited via `PayslipForm` while draft); an automated "detect
  every back-dated structure change since the last processed cycle and compute the exact delta" engine
  is a fast-follow, not blocking.
- **Rollback/re-run UX for a subset of employees within a locked cycle** (Keka) — v1 only allows
  regenerate-while-draft (the whole cycle, not per-employee); once `locked`, a correction requires a
  new `off_cycle` `PayrollCycle` (matches Workday's "corrections require off-cycle processing"
  convention) rather than in-place edits.
- **Multi-currency payroll** — `SalaryStructureTemplate.currency` stays a plain CharField (per 3.13);
  `PayrollCycle`/`Payslip` assume single-currency per tenant, consistent with that.
- **YTD tax projection / cumulative annual payslip aggregation view** — useful (Deel, Workday) but a
  reporting concern layered on top of per-cycle `Payslip` rows already being retained; can be added as
  a query/report later without new models.
- **Formula/criteria-driven incentive calculation** (factoHR's target-based bonus %) — store the
  resulting `bonus_amount`, don't build the rules/target-tracking engine.
- **LOP wired automatically to actual unpaid-leave records from 3.10** (Leave module) — v1 takes
  `lop_days` as a manually-entered field on the payslip; auto-pulling confirmed unpaid-leave days from
  `hrm.LeaveRequest`/attendance is a fast-follow integration, not blocking.
- **`accounting.PayrollRun` extension** (a cleaner "post directly from HRM" helper instead of leaving
  posting in accounting's existing UI) — a small accounting-side follow-up, not part of this HRM pass;
  HRM only creates the `draft` row and links it, accounting's own `payroll_run_post` view still does
  the actual GL posting.
- **Two distinct hold outcomes ("pay later" vs. "void/never pay")** (Keka) — v1 ships a single
  `on_hold`/`hold_reason`/`released_at` flag set; a `hold_resolution` choice
  (`pending`/`release_next_cycle`/`void`) is deferred unless a later pass needs the distinction.

## Review

**Delivered (2026-07-04):** HRM 3.14 Payroll Processing — the operational payroll run. All 5 NavERP.md bullets Live.
3 new models; the L29 boundary respected (HRM computes; `accounting.PayrollRun` posts the GL).
- **`PayrollCycle`** (`PRC-`) — run header + `draft→pending_approval→approved/rejected→locked` workflow;
  cycle_type regular/off_cycle/bonus (non-regular skip approval); derived totals (single aggregate); on lock creates
  a draft `accounting.PayrollRun` with rolled-up totals + links it.
- **`Payslip`** (`PSL-`) — per (cycle,employee); `recompute()` calc engine (monthly-from-CTC, day pro-ration, LOP,
  arrears/bonus; employer-side statutory excluded from net; pct lines scaled by the employee's assigned CTC); holds.
- **`PayslipLine`** — immutable component snapshot (name/type/amount/contribution_side) so a later structure edit
  never rewrites history.
- Migration `0025`; `_seed_payroll` (1 regular cycle, 3 generated payslips, 1 on hold; central flush wipes payslips
  before EmployeeProfile for the PROTECT FK); `LIVE_LINKS["3.14"]` → all 5 bullets.

**Verification:** own smoke test 0 failures — full lifecycle generate→submit→approve→lock created accounting run
PRUN-#### with penny-perfect totals (gross/employer_tax/net reconcile), immutable-after-lock, holds, arrears
recompute, IDOR→404, filters, sidebar Live.

**Module Creation Sequence — all 7 review agents, one at a time, findings applied + committed:**
- **code-reviewer** — 0 Critical. Fixed 6 Important: lock roll-up buckets employee_tax/deductions as "not
  employer-side" (so accounting net reconciles with Σ payslip net, incl. `both`); `resolved_amount(ctc=)` scales pct
  lines by the employee's CTC (different-CTC employees now differ); `Payslip.clean()` (days/negative guards);
  generate adds an effective-date window + preserves manual arrears/bonus/hold across a re-generate; + Minor badge.
  (Also fixed a seeder --flush ProtectedError the on_stop hook caught — payslips wiped before EmployeeProfile.)
- **explorer** — all 7 wiring seams clean; zero `JournalEntry` construction in HRM (L29 confirmed). No fixes.
- **frontend-reviewer** — 1 Critical: privileged buttons (approve/reject/lock/hold/release) rendered for everyone →
  gated behind `is_superuser or is_tenant_admin` with an awaiting-admin notice (matches the app-wide convention incl.
  accounting's own payroll template; the 2 stragglers spun off as a task).
- **performance-reviewer** — the generate loop is O(N), no hidden multiplier (FK cache warm). Fixed 1 Minor:
  `payslip_edit` select_related's the structure+template so the post-save recompute() doesn't re-fetch.
- **qa-smoke-tester** — **79/79** green; verified the accounting reconciliation (net == Σ payslip net, run stays
  draft, no JE) and the admin-gating (template + 403). No code changes.
- **security-reviewer** — no vulnerabilities (IDOR, authz, CSRF, mass-assignment, XSS, injection, hand-off integrity
  all correct). One app-wide authz-policy observation (already covered by a spawned task).
- **test-writer** — **+109 tests** (35 model/calc + 54 view + 20 security): recompute arithmetic + employer-exclusion
  + CTC-scaling, the lock penny-reconciliation, workflow guards, non-admin 403, immutability, IDOR. Full HRM suite
  **2,221 passed / 0 failed** (was 2,112); project-wide **4,868**.

**Follow-up tasks spawned (app-wide, not forked into 3.14):** gate the 2 straggler approve/reject templates
(leaverequest, floatingholidayelection); tenant-admin gate on sensitive HRM writes (carried from 3.13).

**Next:** 3.15 Statutory Compliance (PF/ESI/PT/TDS challans & returns over the payroll runs).

---
# Module 3 — HRM — Sub-module 3.15 Statutory Compliance (statutory-compliance) — plan from research-statutory-compliance.md (2026-07-04)

**Context.** Extends the existing `apps/hrm` app — NOT a new app. Builds the **compliance/reporting/
configuration** layer on top of 3.13 (`PayComponent`/`SalaryStructureTemplate`) and 3.14
(`PayrollCycle`/`Payslip`/`PayslipLine`). This is explicitly NOT a second payroll engine — it does not
recompute or re-store per-employee statutory amounts (those already live on `PayslipLine`); it adds
tenant-wide registration/config, state-wise PT+LWF slab rules, per-employee government identifiers
(UAN/PF/ESI numbers), and a shared per-scheme/per-period return/challan-tracking record that
**aggregates already-computed `PayslipLine` totals** — mirroring `PayrollCycle._totals()`'s
aggregate-and-cache convention and `payrollcycle_lock`'s employee-tax/employer-tax roll-up query. 4 new
models, all in `apps/hrm/models.py`. Money still posts only through `accounting.PayrollRun`/
`JournalEntry` (L29) — this sub-module never touches either.

NavERP.md 3.15 bullets (exact text, all 5 go Live this pass):
- PF Management — PF calculation, challan, returns.
- ESI Management — ESI calculation, contributions.
- PT Management — Professional tax, state-wise rules.
- TDS Management — Tax calculation, Form 16, quarterly returns.
- LWF Management — Labour welfare fund.

Reuses (no duplication): `hrm.EmployeeProfile` (incl. `national_id`/`national_id_type` for PAN,
`employee_type`), `hrm.PayrollCycle`, `hrm.Payslip`/`PayslipLine` (`component_type`,
`contribution_side`, `amount`), `hrm.PayComponent`, `settings.AUTH_USER_MODEL` (audit only via
`write_audit_log`). Never touches `accounting.PayrollRun`/`JournalEntry` — this sub-module builds no
GL-posting path (L29).

## A. Models + migration (`apps/hrm/models.py`)

- [ ] `StatutoryConfig(TenantOwned)` — tenant-wide settings singleton, no numeric prefix (drivers: Zoho
      Payroll's single Statutory Components screen; RazorpayX registration management; greytHR/ClearTax
      Form 16 TAN config):
  - [ ] `pf_establishment_code` — CharField(max_length=50, blank=True) — PF Management (Zoho: PF
        establishment code)
  - [ ] `pf_wage_ceiling` — DecimalField(max_digits=12, decimal_places=2, default=Decimal("15000.00"))
        — PF Management (Zoho: ₹15,000 Basic+DA ceiling)
  - [ ] `pf_employee_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) —
        PF Management
  - [ ] `pf_employer_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00")) —
        PF Management
  - [ ] `esi_employer_code` — CharField(max_length=50, blank=True) — ESI Management (Zoho: ESI number)
  - [ ] `esi_wage_ceiling` — DecimalField(max_digits=12, decimal_places=2, default=Decimal("21000.00"))
        — ESI Management (Zoho: ₹21,000 gross ceiling)
  - [ ] `esi_employee_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.75")) —
        ESI Management
  - [ ] `esi_employer_rate` — DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.25")) —
        ESI Management
  - [ ] `pt_default_state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`, blank=True) — PT
        Management fallback when an employee's own `pt_state` can't be resolved
  - [ ] `tan_number` — CharField(max_length=20, blank=True) — TDS Management (employer TAN, mandatory
        on Form 24Q/16, distinct from PAN)
  - [ ] `tds_circle_address` — TextField(blank=True) — TDS Management (greytHR Form 16 config: TDS
        circle address)
  - [ ] `pan_of_deductor` — CharField(max_length=10, blank=True) — TDS Management (the employer's own
        PAN, distinct from `EmployeeProfile.national_id` which is the *employee's* PAN)
  - [ ] `is_lwf_applicable` — BooleanField(default=False) — LWF Management, org-wide master switch
        (per-state detail lives on `StatutoryStateRule`)
  - [ ] `tenant` — override the inherited FK to add `unique=True` (one row per tenant, settings-object
        pattern — `tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE,
        related_name="hrm_statutory_config")` instead of `TenantOwned`'s plain FK; keep
        `created_at`/`updated_at` via the same mixin)
  - [ ] `class Meta`: no numeric prefix, no `unique_together` beyond the OneToOne
  - [ ] `__str__` → `f"Statutory Config · {self.tenant.name}"`
  - [ ] get-or-create helper: a small `StatutoryConfig.for_tenant(tenant)` classmethod wrapping
        `StatutoryConfig.objects.get_or_create(tenant=tenant)` so every view/seeder call-site is
        consistent (avoid repeating the get_or_create kwargs inline everywhere)

- [ ] `StatutoryStateRule(TenantOwned)` — state-wise PT + LWF slab/rate table, one shared table for
      both state-scoped schemes (drivers: greytHR's editable state-wise PT slab grid; Zimyo/ClearTax/
      saral PayPack LWF state-applicability + periodicity + amount pattern):
  - [ ] `state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`) — a plain choices list of
        India's states/UTs (define `INDIAN_STATE_CHOICES` once near the top of the statutory model
        block, reused by `StatutoryConfig.pt_default_state` and `EmployeeStatutoryIdentifier.pt_state`)
  - [ ] `scheme` — CharField(max_length=10, choices=`[("pt","Professional Tax"),("lwf","Labour Welfare
        Fund")]`)
  - [ ] `income_from` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — PT-only
        (blank/null when `scheme="lwf"`); part of the `unique_together`
  - [ ] `income_to` — DecimalField(max_digits=12, decimal_places=2, null=True, blank=True) — PT-only
  - [ ] `pt_monthly_amount` — DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) —
        PT-only, the tax amount for this income bracket
  - [ ] `pt_deduction_month` — CharField(max_length=20, blank=True) — PT-only, optional (some states
        deduct only in specific months, e.g. an annual lump sum in February)
  - [ ] `lwf_employee_contribution` — DecimalField(max_digits=10, decimal_places=2, null=True,
        blank=True) — LWF-only
  - [ ] `lwf_employer_contribution` — DecimalField(max_digits=10, decimal_places=2, null=True,
        blank=True) — LWF-only
  - [ ] `lwf_periodicity` — CharField(max_length=20, choices=`[("monthly","Monthly"),
        ("half_yearly","Half-Yearly"),("annual","Annual")]`, blank=True) — LWF-only
  - [ ] `lwf_due_month_1` — CharField(max_length=20, blank=True) — LWF-only (e.g. "July")
  - [ ] `lwf_due_month_2` — CharField(max_length=20, blank=True) — LWF-only, nullable-equivalent via
        blank (e.g. "January", for half-yearly states)
  - [ ] `registration_number` — CharField(max_length=50, blank=True) — the state-specific PT/LWF
        employer registration number, where applicable
  - [ ] `is_active` — BooleanField(default=True) — supports the greytHR "Odisha PT discontinued from
        April 2026" pattern: deactivate/supersede, never delete, so prior-period reports stay correct
  - [ ] `effective_from` — DateField(default=timezone.localdate... actually use
        `django.utils.timezone.now().date` via a callable default, or simply
        `models.DateField()` non-null required at creation — pick required, no silent default) —
        supports rate-change history as a new row, not an edit
  - [ ] `class Meta`: `ordering = ["state", "scheme", "income_from"]`; `unique_together = ("tenant",
        "state", "scheme", "income_from")` — for LWF, `income_from` stays `None` so uniqueness is
        effectively `(tenant, state, scheme)` (one active LWF row per state per tenant; supersede via
        `is_active=False` + a new row if a rate changes, don't edit in place; note this constraint
        nuance in the model docstring since `None` participates in `unique_together` per-Django's
        NULL-is-distinct semantics — confirm this is the desired behavior, i.e. **you technically CAN
        have two `income_from=None` LWF rows** for the same `(tenant, state, scheme)` since Postgres
        treats NULLs as distinct in unique constraints; document that `clean()` should additionally
        enforce "at most one `is_active=True` LWF row per `(tenant, state, scheme)`" as an application
        -level guard on top of the DB constraint)
  - [ ] `clean()` — validate PT fields present when `scheme="pt"` (income_from/income_to/
        pt_monthly_amount required), LWF fields present when `scheme="lwf"`
        (lwf_employee_contribution/lwf_employer_contribution/lwf_periodicity required); raise
        `ValidationError` otherwise
  - [ ] `__str__` → `f"{self.get_state_display()} · {self.get_scheme_display()}"` (+ bracket suffix for
        PT: `f" ({self.income_from}-{self.income_to})"` if `scheme == "pt"`)

- [ ] `EmployeeStatutoryIdentifier(TenantOwned)` — 1:1 per-employee government-issued identifiers,
      created lazily (drivers: UAN/ESI-number-per-employee called out across every India payroll
      product surveyed):
  - [ ] `employee` — `models.OneToOneField("hrm.EmployeeProfile", on_delete=models.CASCADE,
        related_name="statutory_identifiers")`
  - [ ] `uan_number` — CharField(max_length=20, blank=True) — PF Universal Account Number (lifelong,
        distinct from the establishment-specific PF number)
  - [ ] `pf_number` — CharField(max_length=30, blank=True) — the establishment-specific PF account/
        member ID
  - [ ] `esi_number` — CharField(max_length=20, blank=True) — ESI Insurance Number, blank if the
        employee's gross exceeds the ESI ceiling and they're exempt
  - [ ] `pt_state` — CharField(max_length=50, choices=`INDIAN_STATE_CHOICES`, blank=True) — resolves
        which `StatutoryStateRule` applies to this employee; falls back to
        `StatutoryConfig.pt_default_state` if blank (kept explicit here rather than overloading
        `EmployeeProfile.work_location`, which is free text)
  - [ ] `is_pf_applicable` — BooleanField(default=True)
  - [ ] `is_esi_applicable` — BooleanField(default=True) — an employee above the ESI wage ceiling, or
        exempted/international worker, can be flagged out without deleting the identifier record
  - [ ] WARNING: `uan_number`/`pf_number`/`esi_number` are government ID numbers — add these three
        field names to `apps.core.crud._SENSITIVE_AUDIT_FIELDS` (redacted in `AuditLog.changes`),
        mirroring the existing `national_id`/`passport_number` entries
  - [ ] `class Meta`: `ordering = ["employee__party__name"]`; index `models.Index(fields=["tenant",
        "employee"], name="hrm_esi_tenant_emp_idx")` (verify auto-index name doesn't collide with the
        model short-name abbreviation already used elsewhere)
  - [ ] `__str__` → `f"Statutory IDs · {self.employee}"`
  - [ ] get-or-create pattern: view-layer helper
        `EmployeeStatutoryIdentifier.objects.get_or_create(tenant=tenant, employee=employee)` called
        lazily from the detail/edit view (not every employee needs every identifier filled immediately)

- [ ] `StatutoryReturn(TenantNumbered, NUMBER_PREFIX="SCR")` — shared per-scheme, per-period compliance
      register/challan/return-tracking record (drivers: Keka's monthly PF ECR report, saral PayPack's
      PF/ESI return generation + compliance-calendar, ClearTax's quarterly Form 24Q + annual Form 16,
      Zimyo's LWF Report, RazorpayX's due-date/payment-status tracking):
  - [ ] `scheme` — CharField(max_length=15, choices=`[("pf","Provident Fund"),("esi","ESI"),
        ("pt","Professional Tax"),("tds_24q","TDS — Form 24Q"),("tds_form16","TDS — Form 16"),
        ("lwf","Labour Welfare Fund")]`)
  - [ ] `period_type` — CharField(max_length=15, choices=`[("monthly","Monthly"),
        ("quarterly","Quarterly"),("half_yearly","Half-Yearly"),("annual","Annual")]`)
  - [ ] `period_start` — DateField()
  - [ ] `period_end` — DateField()
  - [ ] `cycle` — `models.ForeignKey("hrm.PayrollCycle", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="statutory_returns")` — set for the common one-cycle-to-one-return
        case (monthly PF/ESI/LWF); left null for multi-cycle rollups (quarterly Form 24Q spans 3
        cycles, aggregates from `Payslip`/`PayslipLine` by date range instead)
  - [ ] `employee` — `models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
        blank=True, related_name="statutory_returns")` — set only for `scheme="tds_form16"`; null for
        org-level returns (pf/esi/pt/lwf/tds_24q)
  - [ ] `employee_contribution_total` — DecimalField(max_digits=14, decimal_places=2, default=0,
        editable=False) — **derived/cached, never hand-typed**, rolled up from `PayslipLine.amount`
        where `contribution_side="employee"` matching the scheme, across the period (mirrors
        `PayrollCycle._totals()`'s aggregate-and-cache convention)
  - [ ] `employer_contribution_total` — DecimalField(max_digits=14, decimal_places=2, default=0,
        editable=False) — same pattern, `contribution_side="employer"` (+ `"both"` split rule — decide
        and document: include `contribution_side="both"` lines in BOTH totals, matching 3.14's
        `payrollcycle_lock` roll-up convention for `component_type="statutory_deduction"` with `both`)
  - [ ] `headcount` — PositiveIntegerField(default=0, editable=False) — distinct employee count
        contributing to this return's period for this scheme
  - [ ] `due_date` — DateField(null=True, blank=True) — drives the Compliance Calendar cross-cutting
        feature (PF/ESI by 15th, TDS by 7th via Challan 281, PT by 15th/20th depending on state, LWF
        half-yearly by 15 July/15 January)
  - [ ] `status` — CharField(max_length=15, choices=`[("pending","Pending"),("filed","Filed"),
        ("paid","Paid"),("late","Late")]`, default="pending")
  - [ ] `filed_on` — DateField(null=True, blank=True, editable=False)
  - [ ] `paid_on` — DateField(null=True, blank=True, editable=False)
  - [ ] `payment_reference` — CharField(max_length=100, blank=True)
  - [ ] `registration_number_used` — CharField(max_length=50, blank=True) — snapshot copy of the
        relevant `StatutoryConfig`/`StatutoryStateRule` registration number at generation time (mirrors
        `PayslipLine`'s immutable-snapshot convention from 3.14 — a later registration-number edit must
        never rewrite a historical return)
  - [ ] `notes` — TextField(blank=True)
  - [ ] `class Meta`: `ordering = ["-period_start", "scheme"]`; `unique_together = ("tenant", "scheme",
        "period_start", "employee")` — one return per scheme per period (per employee for
        `tds_form16`, org-wide otherwise — `employee=None` participates in the constraint the same way
        as any other FK value); index `models.Index(fields=["tenant", "status"],
        name="hrm_scr_tenant_status_idx")`, index `models.Index(fields=["tenant", "due_date"],
        name="hrm_scr_tenant_duedate_idx")` (powers the compliance calendar query)
  - [ ] `is_overdue` **property** → `self.status == "pending" and self.due_date and
        self.due_date < timezone.localdate()` (drives a "late" visual flag before the status is
        manually flipped to `"late"`)
  - [ ] `__str__` → `f"{self.number} · {self.get_scheme_display()} · {self.period_start}–{self.period_end}"`

- [ ] one incremental migration `apps/hrm/migrations/0026_statutoryconfig_statutorystaterule_and_more.py`
      (NOT `0001_initial`; last is `0025_payrollcycle_payslip_payslipline_and_more.py`) —
      `makemigrations hrm`, review the generated file, adjust index/constraint names to match the ones
      specified above if Django's auto-names differ; confirm `StatutoryConfig.tenant`
      `OneToOneField` doesn't collide with `TenantOwned`'s abstract FK (override cleanly, don't
      multiple-inherit both)

## `statutoryreturn_generate` — the aggregation engine (the key domain action)

- [ ] `@login_required`, `@require_POST` (or a `@tenant_admin_required` gate — pick tenant-admin to
      match 3.14's workflow-action convention) view, form/inputs: `scheme`, `period_type`,
      `period_start`, `period_end`, optional `cycle` (for the monthly single-cycle case), optional
      `employee` (for `tds_form16`)
- [ ] guard: `get_or_create`-style idempotent behavior — if a `StatutoryReturn` already exists for
      `(tenant, scheme, period_start, employee)`, either re-aggregate in place (if `status="pending"`)
      or block with `messages.error` if already `filed`/`paid` (mirror 3.14's draft-only-regenerate
      rule: only `pending` returns can be re-aggregated)
- [ ] inside `transaction.atomic()`:
  - [ ] resolve the `PayslipLine` queryset for this scheme+period: `PayslipLine.objects.filter(
        payslip__tenant=tenant, payslip__cycle__pay_date__gte=period_start,
        payslip__cycle__pay_date__lte=period_end, component_type="statutory_deduction")` — **note:**
        `PayslipLine` has no direct "scheme" tag (pf vs esi vs pt vs lwf are all
        `component_type="statutory_deduction"` today); document the v1 simplification explicitly: this
        pass aggregates ALL `statutory_deduction` lines for the period as a single pool per scheme
        selection (cannot yet distinguish a PF line from an ESI line within `PayslipLine` without a
        `PayComponent`-name-based heuristic) — **decide and document one of:** (a) filter additionally
        by `component_name__icontains=<scheme keyword>` (e.g. "PF"/"Provident", "ESI", "Professional
        Tax", "Labour Welfare") as a pragmatic v1 match against the seeded `PayComponent.name` strings,
        or (b) aggregate the full `statutory_deduction` pool once and let the user pick `scheme` purely
        as a label — **pick (a)**, the name-substring match, and note it as a v1 heuristic (a proper
        per-line scheme tag is a fast-follow noted under Later passes)
  - [ ] `employee_total = qs.filter(contribution_side__in=["employee", "both"]).aggregate(
        Sum("amount"))["amount__sum"] or Decimal("0")`
  - [ ] `employer_total = qs.filter(contribution_side__in=["employer", "both"]).aggregate(
        Sum("amount"))["amount__sum"] or Decimal("0")`
  - [ ] `headcount = qs.values("payslip__employee_id").distinct().count()`
  - [ ] snapshot `registration_number_used` from the relevant `StatutoryConfig`/`StatutoryStateRule`
        field for the chosen scheme (e.g. `pf_establishment_code` for `scheme="pf"`,
        `esi_employer_code` for `"esi"`, `tan_number` for `"tds_24q"`/`"tds_form16"`, the matching
        `StatutoryStateRule.registration_number` for `"pt"`/`"lwf"`)
  - [ ] `StatutoryReturn.objects.update_or_create(tenant=tenant, scheme=scheme,
        period_start=period_start, employee=employee, defaults={...period_end, cycle,
        employee_contribution_total: employee_total, employer_contribution_total: employer_total,
        headcount, registration_number_used, ...})`
  - [ ] `write_audit_log(request.user, obj, "update", {"action": "generate", "headcount": headcount})`
- [ ] redirect to `statutoryreturn_detail`; `messages.success` with the aggregated totals

## Filing/payment status-workflow actions

- [ ] `statutoryreturn_mark_filed` (`@tenant_admin_required`, `@require_POST`) — only from
      `status="pending"`; set `status="filed"`, `filed_on=timezone.localdate()`; `write_audit_log(...,
      {"action": "mark_filed"})`
- [ ] `statutoryreturn_mark_paid` (`@tenant_admin_required`, `@require_POST`) — only from
      `status in {"pending", "filed"}`; set `status="paid"`, `paid_on=timezone.localdate()`,
      `payment_reference=request.POST.get("payment_reference", "").strip()[:100]`; if `paid_on >
      due_date` (when `due_date` set) also flip `status="late"` instead of `"paid"` — document this
      override rule explicitly (mirrors RazorpayX/saral PayPack's paid-vs-late comparison); write_audit_log
- [ ] both redirect to `statutoryreturn_detail`

## B. Forms (`apps/hrm/forms.py`)

- [ ] `StatutoryConfigForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["pf_establishment_code", "pf_wage_ceiling", "pf_employee_rate",
        "pf_employer_rate", "esi_employer_code", "esi_wage_ceiling", "esi_employee_rate",
        "esi_employer_rate", "pt_default_state", "tan_number", "tds_circle_address",
        "pan_of_deductor", "is_lwf_applicable"]` (exclude `tenant` — set via `get_or_create`, never a
        form field since there's exactly one row per tenant)
  - [ ] no custom `__init__` needed (no FK dropdowns)
- [ ] `StatutoryStateRuleForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["state", "scheme", "income_from", "income_to", "pt_monthly_amount",
        "pt_deduction_month", "lwf_employee_contribution", "lwf_employer_contribution",
        "lwf_periodicity", "lwf_due_month_1", "lwf_due_month_2", "registration_number", "is_active",
        "effective_from"]` (exclude `tenant`/auto-number — no number field on this model, all fields
        form-editable except `tenant`)
  - [ ] template-side JS/UX note (not blocking backend): consider toggling PT-only vs LWF-only field
        visibility based on the `scheme` select, but not required for v1 — plain form with all fields
        shown is acceptable
- [ ] `EmployeeStatutoryIdentifierForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["employee", "uan_number", "pf_number", "esi_number", "pt_state",
        "is_pf_applicable", "is_esi_applicable"]` (exclude `tenant`)
  - [ ] custom `__init__` narrows `employee` queryset to `EmployeeProfile.objects.filter(tenant=tenant)`
        (standard tenant-scoped FK-narrowing pattern used across every prior HRM form)
- [ ] `StatutoryReturnForm(TenantModelForm)`:
  - [ ] `Meta.fields = ["scheme", "period_type", "period_start", "period_end", "cycle", "employee",
        "due_date", "notes"]` (exclude `tenant`/auto-number `number`/derived
        `employee_contribution_total`/`employer_contribution_total`/`headcount`/`status`/`filed_on`/
        `paid_on`/`payment_reference`/`registration_number_used` — all workflow/derived, never
        generic-form-editable; totals are only ever set via `statutoryreturn_generate`)
  - [ ] custom `__init__` narrows `cycle` to `PayrollCycle.objects.filter(tenant=tenant)` and
        `employee` to `EmployeeProfile.objects.filter(tenant=tenant)`
  - [ ] this form covers manual create (a return with due_date/notes but zero aggregates, to be
        generated later) and metadata edit; the aggregate totals are never form-editable

## C. Views (`apps/hrm/views.py`)

- [ ] `statutoryconfig_detail` (`@login_required`) — the settings-singleton page: `config, _ =
      StatutoryConfig.objects.get_or_create(tenant=request.tenant)`; render
      `hrm/statutory/statutoryconfig/detail.html` with `{"obj": config}` — no `_list`/`_create`/
      `_delete` views (singleton, nothing to list or delete)
- [ ] `statutoryconfig_edit` (`@login_required`) — `get_or_create` then standard `crud_edit`-style
      handling (or a thin custom view since `crud_edit` expects a `pk` — either add a `pk`-taking
      wrapper that resolves `pk=config.pk` via redirect, or write a small dedicated
      get-or-create-then-edit view; **pick the dedicated view**, document why `crud_edit` isn't reused
      directly for this one singleton model)
- [ ] `statutorystaterule_list` (`@login_required`) — `crud_list(request,
      StatutoryStateRule.objects.filter(tenant=request.tenant), "hrm/statutory/statutorystaterule/list.html",
      search_fields=["state", "registration_number"], filters=[("scheme", "scheme", False),
      ("state", "state", False), ("is_active", "is_active", False)], extra_context={"scheme_choices":
      StatutoryStateRule._meta.get_field("scheme").choices, "state_choices": INDIAN_STATE_CHOICES})`
- [ ] `statutorystaterule_create` / `_edit` / `_detail` / `_delete` — standard `crud_create`/
      `crud_edit`/`crud_detail`/`crud_delete` wrappers, template base
      `hrm/statutory/statutorystaterule/{form,detail}.html`
- [ ] `employeestatutoryidentifier_list` (`@login_required`) — `crud_list(request,
      EmployeeStatutoryIdentifier.objects.filter(tenant=request.tenant).select_related(
      "employee__party"), "hrm/statutory/employeestatutoryidentifier/list.html",
      search_fields=["employee__party__name", "uan_number", "pf_number", "esi_number"],
      filters=[("pt_state", "pt_state", False), ("is_pf_applicable", "is_pf_applicable", False),
      ("is_esi_applicable", "is_esi_applicable", False)], extra_context={"state_choices":
      INDIAN_STATE_CHOICES})`
- [ ] `employeestatutoryidentifier_create` / `_edit` / `_detail` / `_delete` — standard wrappers;
      `_create`'s form narrows the `employee` dropdown to employees who don't already have an
      identifier row (`EmployeeProfile.objects.filter(tenant=tenant).exclude(
      statutory_identifiers__isnull=False)`) so the OneToOne can't collide — document this narrowing in
      the form's `__init__`
- [ ] `statutoryreturn_list` (`@login_required`) — `crud_list(request,
      StatutoryReturn.objects.filter(tenant=request.tenant).select_related("cycle",
      "employee__party"), "hrm/statutory/statutoryreturn/list.html", search_fields=["number",
      "registration_number_used", "notes"], filters=[("scheme", "scheme", False), ("status", "status",
      False), ("period_type", "period_type", False)], extra_context={"scheme_choices":
      StatutoryReturn._meta.get_field("scheme").choices, "status_choices":
      StatutoryReturn._meta.get_field("status").choices, "period_type_choices":
      StatutoryReturn._meta.get_field("period_type").choices})`
- [ ] `statutoryreturn_create` — standard `crud_create` wrapper (manual metadata-only create; totals
      stay 0 until `generate` is run)
- [ ] `statutoryreturn_edit` — standard `crud_edit` wrapper, only while `status == "pending"` (else
      `messages.error` + redirect to detail, mirror the `floatingholidayelection_edit`/
      `payrollcycle_edit` pending-only guard pattern)
- [ ] `statutoryreturn_delete` (`@login_required`, `@require_POST`) — only while `status == "pending"`
      (mirror `payrollcycle_delete`'s draft-only guard) — else `messages.error` + redirect
- [ ] `statutoryreturn_detail` (`@login_required`) — `crud_detail(request, model=StatutoryReturn,
      pk=pk, template="hrm/statutory/statutoryreturn/detail.html", select_related=("cycle",
      "employee__party"))`
- [ ] `statutoryreturn_generate` — per the Aggregation Engine spec above
- [ ] `statutoryreturn_mark_filed` / `_mark_paid` — per the Filing/Payment Status Workflow spec above
- [ ] `statutory_compliance_calendar` (`@login_required`) — the cross-cutting **compliance calendar**
      read-only view, no new model: `returns = StatutoryReturn.objects.filter(
      tenant=request.tenant).select_related("cycle", "employee__party").order_by("due_date",
      "scheme")`; group into buckets by `status` (overdue via `is_overdue` property / pending / filed /
      paid) for the template to render as calendar/list columns; support the same `scheme`/`status`
      GET-param filters as `statutoryreturn_list` (reuse `apply_search`/manual filtering, not
      necessarily full `crud_list` since this is a grouped, not paginated-flat, view — document that
      choice); render `hrm/statutory/compliance_calendar.html`
- [ ] all new views import `StatutoryConfig`, `StatutoryStateRule`, `EmployeeStatutoryIdentifier`,
      `StatutoryReturn`, `StatutoryConfigForm`, `StatutoryStateRuleForm`,
      `EmployeeStatutoryIdentifierForm`, `StatutoryReturnForm` at the top of `views.py`; `Sum` from
      `django.db.models` and `transaction` from `django.db` (already imported for 3.14 — confirm, don't
      re-import)

## D. URLs (`apps/hrm/urls.py`, `app_name = "hrm"` already set)

- [ ] `path("statutory-config/", views.statutoryconfig_detail, name="statutoryconfig_detail")`
- [ ] `path("statutory-config/edit/", views.statutoryconfig_edit, name="statutoryconfig_edit")`
- [ ] `path("statutory-state-rules/", views.statutorystaterule_list, name="statutorystaterule_list")`
- [ ] `path("statutory-state-rules/add/", views.statutorystaterule_create, name="statutorystaterule_create")`
- [ ] `path("statutory-state-rules/<int:pk>/", views.statutorystaterule_detail, name="statutorystaterule_detail")`
- [ ] `path("statutory-state-rules/<int:pk>/edit/", views.statutorystaterule_edit, name="statutorystaterule_edit")`
- [ ] `path("statutory-state-rules/<int:pk>/delete/", views.statutorystaterule_delete, name="statutorystaterule_delete")`
- [ ] `path("statutory-identifiers/", views.employeestatutoryidentifier_list, name="employeestatutoryidentifier_list")`
- [ ] `path("statutory-identifiers/add/", views.employeestatutoryidentifier_create, name="employeestatutoryidentifier_create")`
- [ ] `path("statutory-identifiers/<int:pk>/", views.employeestatutoryidentifier_detail, name="employeestatutoryidentifier_detail")`
- [ ] `path("statutory-identifiers/<int:pk>/edit/", views.employeestatutoryidentifier_edit, name="employeestatutoryidentifier_edit")`
- [ ] `path("statutory-identifiers/<int:pk>/delete/", views.employeestatutoryidentifier_delete, name="employeestatutoryidentifier_delete")`
- [ ] `path("statutory-returns/", views.statutoryreturn_list, name="statutoryreturn_list")`
- [ ] `path("statutory-returns/add/", views.statutoryreturn_create, name="statutoryreturn_create")`
- [ ] `path("statutory-returns/<int:pk>/", views.statutoryreturn_detail, name="statutoryreturn_detail")`
- [ ] `path("statutory-returns/<int:pk>/edit/", views.statutoryreturn_edit, name="statutoryreturn_edit")`
- [ ] `path("statutory-returns/<int:pk>/delete/", views.statutoryreturn_delete, name="statutoryreturn_delete")`
- [ ] `path("statutory-returns/<int:pk>/generate/", views.statutoryreturn_generate, name="statutoryreturn_generate")`
- [ ] `path("statutory-returns/<int:pk>/mark-filed/", views.statutoryreturn_mark_filed, name="statutoryreturn_mark_filed")`
- [ ] `path("statutory-returns/<int:pk>/mark-paid/", views.statutoryreturn_mark_paid, name="statutoryreturn_mark_paid")`
- [ ] `path("statutory-compliance-calendar/", views.statutory_compliance_calendar, name="statutory_compliance_calendar")`

## E. Admin (`apps/hrm/admin.py`)

- [ ] register `StatutoryConfig` — `list_display = ("tenant", "pf_establishment_code",
      "esi_employer_code", "tan_number", "is_lwf_applicable")`, `list_filter = ("is_lwf_applicable",)`,
      `search_fields = ("tenant__name", "pf_establishment_code", "esi_employer_code", "tan_number")`
- [ ] register `StatutoryStateRule` — `list_display = ("state", "scheme", "income_from", "income_to",
      "is_active", "effective_from")`, `list_filter = ("tenant", "scheme", "state", "is_active")`,
      `search_fields = ("state", "registration_number")`
- [ ] register `EmployeeStatutoryIdentifier` — `list_display = ("employee", "uan_number", "pf_number",
      "esi_number", "is_pf_applicable", "is_esi_applicable")`, `list_filter = ("tenant",
      "is_pf_applicable", "is_esi_applicable")`, `search_fields = ("employee__party__name",
      "uan_number", "pf_number", "esi_number")`
- [ ] register `StatutoryReturn` — `list_display = ("number", "scheme", "period_start", "period_end",
      "status", "employee_contribution_total", "employer_contribution_total", "due_date")`,
      `list_filter = ("tenant", "scheme", "status", "period_type")`, `search_fields = ("number",
      "registration_number_used", "notes")`

## F. Templates (`templates/hrm/statutory/<entity>/<page>.html`)

- [ ] `statutory/statutoryconfig/detail.html` — single-entity sub-module-doubles-as-entity-folder
      pattern (per Template Folder Structure rule 3): header sections PF (establishment_code,
      wage_ceiling, employee/employer rates), ESI (employer_code, wage_ceiling, employee/employer
      rates), PT (pt_default_state), TDS (tan_number, tds_circle_address, pan_of_deductor), LWF
      (is_lwf_applicable badge); single Edit action (links to `statutoryconfig_edit`, no delete —
      singleton); no list page for this model
- [ ] `statutory/statutoryconfig/form.html` — standard form, all `StatutoryConfigForm` fields grouped
      into the same PF/ESI/PT/TDS/LWF sections as the detail page
- [ ] `statutory/statutorystaterule/list.html` — filter bar: search `q`, `scheme` select (from
      `scheme_choices`), `state` select (from `state_choices`), `is_active` select (True/False);
      columns: state, scheme badge (`pt`→`badge-info`, `lwf`→`badge-amber`), income bracket (PT) or
      periodicity (LWF), amount, registration_number, is_active badge, effective_from, Actions
      (view/edit/delete); pagination include; empty-state
- [ ] `statutory/statutorystaterule/detail.html` — header (state, scheme badge, is_active badge,
      effective_from), PT section (income_from–income_to, pt_monthly_amount, pt_deduction_month) shown
      only if `scheme == "pt"`, LWF section (lwf_employee_contribution, lwf_employer_contribution,
      lwf_periodicity, lwf_due_month_1, lwf_due_month_2) shown only if `scheme == "lwf"`,
      registration_number; Actions sidebar (Edit/Delete/Back to List)
- [ ] `statutory/statutorystaterule/form.html` — standard form (all fields; PT/LWF fields shown
      together, no JS toggle required for v1 per Forms section note)
- [ ] `statutory/employeestatutoryidentifier/list.html` — filter bar: search `q`, `pt_state` select
      (from `state_choices`), `is_pf_applicable`/`is_esi_applicable` selects (True/False); columns:
      employee, uan_number, pf_number, esi_number, pt_state, is_pf_applicable badge, is_esi_applicable
      badge, Actions (view/edit/delete); pagination include; empty-state
- [ ] `statutory/employeestatutoryidentifier/detail.html` — header (employee link), PF section
      (uan_number, pf_number, is_pf_applicable badge), ESI section (esi_number, is_esi_applicable
      badge), PT section (pt_state); Actions sidebar (Edit/Delete/Back to List)
- [ ] `statutory/employeestatutoryidentifier/form.html` — standard form (employee dropdown +
      uan_number/pf_number/esi_number/pt_state/is_pf_applicable/is_esi_applicable)
- [ ] `statutory/statutoryreturn/list.html` — filter bar: search `q`, `scheme` select (from
      `scheme_choices`), `status` select (from `status_choices`), `period_type` select (from
      `period_type_choices`); columns: number, scheme badge, period_start–period_end, status badge
      (`pending`→`badge-muted`, `filed`→`badge-info`, `paid`→`badge-green`, `late`→`badge-red`),
      employee_contribution_total, employer_contribution_total, headcount, due_date (highlight red if
      `obj.is_overdue`), Actions (view/edit-if-pending/delete-if-pending/generate); pagination include;
      empty-state; always `{% else %}{{ obj.get_scheme_display }}`/`{{ obj.get_status_display }}`
      fallback per Badge Values rule
- [ ] `statutory/statutoryreturn/detail.html` — header fields (scheme badge, period_type,
      period_start–period_end, cycle link if set, employee link if `tds_form16`), derived-totals panel
      (employee_contribution_total/employer_contribution_total/headcount), status badge + due_date
      (with overdue flag), filed_on/paid_on/payment_reference, registration_number_used, notes; action
      buttons gated by status (`Generate/Re-aggregate` — pending only, POST+confirm+csrf; `Mark Filed`
      — pending only, tenant-admin, POST+confirm+csrf; `Mark Paid` — pending/filed only, tenant-admin,
      POST+confirm+csrf with a `payment_reference` input); Actions sidebar (Edit-if-pending/
      Delete-if-pending, Back to List)
- [ ] `statutory/statutoryreturn/form.html` — standard form (scheme, period_type, period_start,
      period_end, cycle, employee, due_date, notes)
- [ ] `statutory/compliance_calendar.html` — the cross-cutting calendar page: grouped sections
      (Overdue / Pending / Filed / Paid, or grouped by upcoming `due_date`), each row links to
      `statutoryreturn_detail`; filter bar mirrors `statutoryreturn_list`'s scheme/status selects;
      empty-state; this is a **standalone page** at the sub-module root (`statutory/`), not inside an
      entity folder, per Template Folder Structure rule 6
- [ ] a landing link: add a `statutory/overview.html`-style link OR simply ensure
      `statutoryreturn_list`/`statutory_compliance_calendar` are reachable from the sidebar — confirm
      against the existing HRM sub-module landing convention (3.13/3.14 didn't add a dedicated overview
      page; match whichever pattern those actually used) before adding a new one unnecessarily

## G. Seeder (`apps/hrm/management/commands/seed_hrm.py`)

- [ ] add `_seed_statutory(self, tenant, *, flush)` method, called from `handle()` **AFTER**
      `self._seed_payroll(tenant, flush=options["flush"])` (return generation needs 3.14's
      `PayrollCycle`/`Payslip`/`PayslipLine` rows to exist first)
- [ ] `if flush:` child-first wipe: `StatutoryReturn.objects.filter(tenant=tenant).delete()` →
      `EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).delete()` →
      `StatutoryStateRule.objects.filter(tenant=tenant).delete()` →
      `StatutoryConfig.objects.filter(tenant=tenant).delete()`
- [ ] `if StatutoryConfig.objects.filter(tenant=tenant).exists(): self.stdout.write(self.style.NOTICE(
      f"Statutory compliance data already exists for '{tenant.name}'. Use --flush to re-seed.")); return`
- [ ] create 1 `StatutoryConfig` row: `pf_establishment_code="MH/BAN/1234567/000"`,
      `esi_employer_code="11-22-334455-000-1111"`, `pt_default_state="Maharashtra"`,
      `tan_number="MUMB12345C"`, `tds_circle_address="ITO (TDS), Room 101, Mumbai"`,
      `pan_of_deductor="AABCN1234A"`, `is_lwf_applicable=True` (defaults cover pf/esi rates/ceilings —
      don't override unless demonstrating a non-default rate)
- [ ] create 2 `StatutoryStateRule` rows:
  - [ ] a Maharashtra PT slab: `state="Maharashtra"`, `scheme="pt"`, `income_from=Decimal("0.00")`,
        `income_to=Decimal("7500.00")`, `pt_monthly_amount=Decimal("0.00")`, `is_active=True`,
        `effective_from=` a fixed past date (e.g. `2024-04-01`) — plus a second bracket row (e.g.
        `income_from=7501, income_to=10000, pt_monthly_amount=175`) to demonstrate the slab-table shape
        (2 PT rows minimum, satisfying "a couple of StatutoryStateRule rows")
  - [ ] a Maharashtra half-yearly LWF row: `state="Maharashtra"`, `scheme="lwf"`,
        `lwf_employee_contribution=Decimal("6.00")`, `lwf_employer_contribution=Decimal("18.00")`,
        `lwf_periodicity="half_yearly"`, `lwf_due_month_1="July"`, `lwf_due_month_2="January"`,
        `registration_number="LWF/MH/998877"`, `is_active=True`, `effective_from=` same fixed past date
- [ ] for each seeded `EmployeeProfile` in `tenant` (reuse the 3.13/3.14-seeded employees): `get_or_create`
      an `EmployeeStatutoryIdentifier` with deterministic demo values (`uan_number=f"UAN{employee.pk:010d}"`,
      `pf_number=f"MH/BAN/1234567/000/{employee.pk:04d}"`, `esi_number=f"3411{employee.pk:06d}"`,
      `pt_state="Maharashtra"`, `is_pf_applicable=True`, `is_esi_applicable=True`)
- [ ] generate 1 `StatutoryReturn` (scheme=`"pf"`) for the existing seeded `PayrollCycle` from
      `_seed_payroll`: reuse or directly call the same aggregation logic as `statutoryreturn_generate`
      (a shared helper is preferable — if the view logic is short enough, factor a
      `build_statutory_return(tenant, scheme, period_start, period_end, cycle=None, employee=None)`
      module-level function in `models.py` or a `services.py` that both the view and the seeder call,
      avoiding duplicating the aggregation query) — `period_type="monthly"`,
      `period_start=cycle.period_start`, `period_end=cycle.period_end`, `cycle=cycle`,
      `due_date=cycle.period_end.replace(day=15)` (approximate 15th-of-month PF due date, clamped if
      the month has fewer days — use a safe date-arithmetic helper), `registration_number_used=
      config.pf_establishment_code`
- [ ] print a summary line: `f"Statutory compliance seeded for '{tenant.name}': 1 config, 2 state
      rules, {EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).count()} employee
      identifier(s), 1 statutory return ({return_obj.number})."`
- [ ] add the 4 models to the `--flush` wipe order in dependency sequence (children first):
      `StatutoryReturn` → `EmployeeStatutoryIdentifier` → `StatutoryStateRule` → `StatutoryConfig`
      (already specified above — restate here for the flush-order checklist); confirm this sits BEFORE
      `EmployeeProfile`'s own wipe in the central flush order (since `EmployeeStatutoryIdentifier` FKs
      to it) — mirror the 3.14 lesson about wiping children before the PROTECT-adjacent parent
- [ ] verify the seeder still prints the tenant-admin login reminder + "Data already exists" warning
      path unchanged — the new block is itself idempotent, no new top-level guard needed

## H. Navigation (`apps/core/navigation.py`)

- [ ] add `LIVE_LINKS["3.15"]` (verify the exact query-string highlighting convention against 3.13/
      3.14's existing entries before finalizing):
      ```python
      # 3.15 Statutory Compliance — StatutoryReturn (scheme-filtered) serves PF/ESI/PT/TDS/LWF;
      # StatutoryStateRule serves PT's state-wise rules; mirrors 3.14's deep-linked query-param pattern.
      "3.15": {
          "PF Management": "hrm:statutoryreturn_list?scheme=pf",                    # bullet
          "ESI Management": "hrm:statutoryreturn_list?scheme=esi",                  # bullet
          "PT Management": "hrm:statutorystaterule_list?scheme=pt",                 # bullet
          "TDS Management": "hrm:statutoryreturn_list?scheme=tds_24q",              # bullet
          "LWF Management": "hrm:statutorystaterule_list?scheme=lwf",               # bullet
      },
      ```
      — all 5 NavERP.md 3.15 bullets go Live; adjust the literal query strings if the real filter
      param names implemented in Section C differ; PT/LWF deliberately point at
      `statutorystaterule_list` (the state-wise rule table) rather than `statutoryreturn_list` since
      the rule table IS the PT/LWF-specific configuration surface the bullet describes, while PF/ESI/
      TDS point at the shared `statutoryreturn_list` (challan/return tracking) — document this split
      rationale in the navigation.py comment

## I. Migrate / seed / verify (run from the venv)

- [ ] `python manage.py makemigrations hrm` → review `0026_...py` (field/index/unique_together names
      match the plan; confirm `StatutoryConfig`'s `OneToOneField` override of the abstract `tenant` FK
      generates cleanly with no spurious `TenantOwned.tenant` leftover column)
- [ ] `python manage.py migrate`
- [ ] `python manage.py seed_hrm` (1st run — creates data; confirm 3.14's `_seed_payroll` still runs
      first and the new `_seed_statutory` block generates its config/rules/identifiers/return against
      it)
- [ ] `python manage.py seed_hrm` (2nd run — must be idempotent, no duplicates, no errors)
- [ ] `python manage.py check`
- [ ] `temp/` smoke sweep: every new `hrm:statutoryconfig_*`, `hrm:statutorystaterule_*`,
      `hrm:employeestatutoryidentifier_*`, `hrm:statutoryreturn_*`, and
      `hrm:statutory_compliance_calendar` URL returns 200/302 when logged in as a tenant admin; no
      `{#`/`{% comment` leaks in the new templates; cross-tenant IDOR check — a `StatutoryStateRule`/
      `EmployeeStatutoryIdentifier`/`StatutoryReturn` pk belonging to tenant A returns 404 when fetched
      as tenant B; `statutoryreturn_generate` run twice on a `pending` return produces the same
      totals (re-aggregation replaces, doesn't duplicate/double-count); spot-check
      `employee_contribution_total`/`employer_contribution_total`/`headcount` arithmetic against the
      seeded `PayslipLine` rows by hand; `statutoryreturn_mark_paid` after `due_date` correctly flips
      to `"late"` not `"paid"`; `statutoryreturn_edit`/`_delete` blocked once not `pending`; non-admin
      user gets 403 on mark_filed/mark_paid; the `?scheme=pf`/`?scheme=pt` deep-links each render the
      filtered subset correctly; the compliance calendar groups returns by status/due_date correctly
- [ ] sidebar: confirm 3.15 shows all five bullets as **Live** (not "Coming soon") for a tenant with
      data

## J. Close-out

- [ ] update `README.md` module-status / HRM section (3.15 bullets: PF Management / ESI Management /
      PT Management / TDS Management / LWF Management all live; bump the HRM + project-wide test-count
      lines once test-writer runs)
- [ ] run the review-agent sequence in order, each ending in its own commit(s): `code-reviewer` →
      `explorer` → `frontend-reviewer` → `performance-reviewer` → `qa-smoke-tester` →
      `security-reviewer` → `test-writer`
- [ ] update `.claude/skills/hrm/SKILL.md` — 3.15 section: document `StatutoryConfig`/
      `StatutoryStateRule`/`EmployeeStatutoryIdentifier`/`StatutoryReturn` models, the
      `statutoryreturn_generate` aggregation-engine contract (incl. the v1 `component_name`-substring
      scheme-matching heuristic against `PayslipLine`), the mark_filed/mark_paid workflow + the
      due-date/late-status rule, the compliance calendar view, the new `LIVE_LINKS["3.15"]` entries
      (incl. the PT/LWF-vs-PF/ESI/TDS routing split), the extended seeder block, and mark all 5 bullets
      of 3.15 as built

## Later passes / deferred (carried over from research-statutory-compliance.md — do not build this pass)

- **ECR file / ESIC challan / EPFO-portal file-format generation** — the exact pipe/CSV government file
  layouts and direct portal upload; this pass stores the aggregated numbers
  (`StatutoryReturn.employee_contribution_total` etc.) needed to generate them later.
- **TRACES integration / unconsumed-challan matching** — external government-portal API integration.
- **AI/rules-based error detection before filing** (late-deduction/PAN-validation flagging) — a
  validation-rules engine layered on top of `StatutoryReturn`; fast-follow, not blocking v1.
- **Form 16 / Form 24Q PDF/XML rendering and email delivery** — presentation/document-generation
  layer, consistent with the payslip-PDF deferral noted in 3.14; this pass tracks the
  `StatutoryReturn` row's status/aggregates, not the rendered document.
- **Automatic rate-change alerting** (e.g. the Odisha PT discontinuation pattern) — structurally
  supported via `StatutoryStateRule.is_active`/`effective_from` (supersede, don't edit), but no
  notification/alert engine built this pass.
- **Compliance-calendar dashboard UI as a distinct product surface beyond the read-only grouped list**
  — `statutory_compliance_calendar` ships as a straightforward grouped list this pass; a richer
  calendar-grid UI is a later frontend polish pass, not a data-model change.
- **Multi-country / non-India statutory schemes** — `StatutoryReturn.scheme` choices stay India-only
  this pass; extending for other jurisdictions is a future-pass consideration.
- **Gratuity and Bonus Act statutory compliance** — out of the five NavERP.md 3.15 bullets (PF/ESI/PT/
  TDS/LWF only); would be a separate future bullet if NavERP.md is extended.
- **PT/LWF per-employee-type differentiation beyond `EmployeeProfile.employee_type` reuse** — supported
  at the query/filter level using the existing field; no new per-type override table added.
- **Per-`PayslipLine` scheme tagging** (a proper `scheme` FK/choice on `PayslipLine` distinguishing PF
  vs ESI vs PT vs LWF lines cleanly, replacing the v1 `component_name`-substring heuristic used by
  `statutoryreturn_generate`) — noted above as the pragmatic v1 aggregation approach; a real per-line
  scheme tag would require a 3.14 model change and is deferred to avoid touching an already-shipped,
  reviewed, tested model this pass.

## Review
(filled in at the end)

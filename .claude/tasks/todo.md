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

(filled in at the end)

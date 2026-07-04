# Research — Module 3: HRM Sub-module 3.14 Payroll Processing (payroll)

## Scope note — the L29 coordination boundary
This research covers the **operational** payroll run: computing each employee's pay for a period from
their salary structure, routing it through approval, applying holds/arrears/bonus, and handing the
totals off to the general ledger. It builds strictly ON TOP of two things that already exist and must
NOT be re-modeled:

- **3.13 Salary Structure** (`apps/hrm/models.py`) — `PayComponent` (the component catalog), `SalaryStructureTemplate`
  + `SalaryStructureLine` (grade-wise CTC breakdown, `resolved_amount()`), and **`EmployeeSalaryStructure`**
  (`ESS-#####`, the effective-dated per-employee CTC assignment, `status=active/superseded`,
  `annual_ctc_amount`). The payroll run's calculation engine reads FROM the employee's active
  `EmployeeSalaryStructure` → its `template.lines` → each line's `resolved_amount()`. No new pay-component
  modeling in this pass.
- **`accounting.PayrollRun`** (`apps/accounting/models_advanced.py:162`, ALREADY BUILT) — a pay-period
  FINANCIAL aggregate (`PRUN-#####`) with `period_start/end`, `pay_date`, `headcount`, `gross_wages`,
  `employee_tax`, `employer_tax`, `benefits`, `deductions`, derived `net_pay`, `status=draft/posted`, and a
  `journal_entry` FK. Its `payroll_run_post` view (`apps/accounting/views_advanced.py:376`) builds the
  balanced Dr Wages/Tax/Benefits Expense / Cr Cash + Taxes Payable + Deductions Payable journal entry. **It
  has no per-employee breakdown, no salary-structure link, no approval/holds/arrears** — it is a
  headcount-and-totals shell that accounting posts from.

**Coordination rule:** HRM 3.14 owns the operational/per-employee layer (this research). On
finalize/approval it must create-or-link an `accounting.PayrollRun` row (FK by string
`models.ForeignKey('accounting.PayrollRun', ...)`) populated with the HRM cycle's rolled-up totals
(headcount, gross_wages, employee_tax, employer_tax, benefits, deductions) so the **existing**
`payroll_run_post` view in accounting does the GL posting. **Do not build a second GL-posting path or
duplicate `JournalEntry` construction in HRM.** Naming must not collide with `accounting.PayrollRun` —
this catalog recommends `PayrollCycle` (HRM operational header) to keep the two distinct.

**Coordination flag for accounting (small extension likely needed):** `accounting.PayrollRun` currently has
no field/FK back to an HRM source object and no "populate totals from a payload" helper — just a manually
filled form (`PayrollRunForm`) plus a manual `payroll_run_post`. To wire HRM → accounting cleanly, accounting
should gain (in a later/parallel small change, not re-litigated here): (a) an optional
`source_cycle` reverse link or simply let HRM set the six total fields directly when it creates the
`accounting.PayrollRun` row, and (b) confirmation that `payroll_run_post` can be called
programmatically (it already is a plain function view — HRM's "finalize" action can call
`PayrollRun.objects.create(...)` with the computed totals, in `draft`, and either leave posting to the
accounting UI or invoke the same account-resolution + JE-build logic accounting uses). No new JE code in
HRM either way.

## Leaders surveyed (with source links)
1. **Keka** — India-centric HRIS/payroll leader; explicit "Salary on Hold & Arrears" step inside the payroll
   run wizard — [Running payroll on Keka](https://help.keka.com/hc/en-us/articles/39946563404561-Running-payroll-on-Keka), [How are arrears calculated?](https://help.keka.com/hc/en-us/articles/39946569378065-How-are-arrears-calculated), [Salary Revision, Arrear Processing & Bonus Payments](https://www.keka.com/employee-salary-revision-arrear-processing-bonus-payments), [Payroll rollback](https://help.keka.com/admin/knowledge/how-to-roll-back-the-payroll-of-some-employees-or-of-an-entire-pay-group)
2. **greytHR** — India HRMS/payroll; salary-revision approval chain feeding automatic arrears —
   [Process employees' payroll](https://admin-help.greythr.com/admin/answers/94174307/), [Calculate and process employee's arrears](https://admin-help.greythr.com/admin/answers/122441429/), [Lock payroll and release payslips for selected employees](https://admin-help.greythr.com/admin/answers/122119665/), [Approve/Reject salary revisions](https://admin-help.greythr.com/admin/answers/121650468/)
3. **Darwinbox** — enterprise HCM; payroll built on the "RIVeR" (Review, Initiate, Verify & e-approve,
   Release & Report) framework — [Payroll automation process](https://darwinbox.com/blog/payroll-automation-process-from-attendance-to-payslips), [Darwinbox Payroll product page](https://darwinbox.com/en-us/products/payroll)
4. **Zoho Payroll** — SMB payroll; configurable simple/custom multi-level pay-run approval, new-joinee
   arrears, off-cycle runs — [Pay Runs](https://www.zoho.com/in/payroll/help/employer/pay-runs/), [Configure Approval Workflows](https://www.zoho.com/in/payroll/help/employer/settings/configure-approvals.html), [Types of Pay Runs](https://www.zoho.com/en-in/erp/help/payroll/pay-runs/pay-run-types.html)
5. **factoHR** — India payroll; monthly-input model (stop-payment / arrears / increment / ad hoc / loans)
   feeding one payroll run — [factoHR payroll software](https://factohr.com/payroll-software/), [Payroll – factoHR Help](https://help.factohr.com/knowledgebase/payroll/), [Complete payroll guide](https://factohr.com/complete-payroll-guide/)
6. **Rippling** — US payroll/HRIS; unlimited off-cycle/bonus runs, preview-before-approve pattern —
   [Off-cycle pay run recipe](https://www.rippling.com/recipes/off-cycle-pay-run-alert), [Payroll review](https://www.rippling.com/blog/rippling-payroll-review)
7. **Gusto** — SMB payroll; "extra pay" (bonus) payroll type is explicitly separate from regular payroll and
   does NOT support the approval step — [Run an off-cycle payroll](https://support.gusto.com/article/999908231000000/run-an-off-cycle-payroll-for-admins), [Extra pay payroll (bonus)](https://support.gusto.com/article/999946501000000/Extra-pay-payroll-for-admins-aka-bonus-payroll), [Set up approvals for payroll](https://support.gusto.com/article/240829150046240/Set-up-approvals-for-payroll)
8. **ADP Workforce Now** — enterprise payroll; General Ledger Interface (GLI) exports/creates journal
   entries from the payroll run against a mapped chart of accounts —
   [ADP Workforce Now Payroll](https://apps.adp.com/en-US/apps/188481/adp-workforce-now-payroll), [GL Mapping guide](https://support.adp.com/adp_payroll/content/hybrid/GL/Online-Infographic-GL-Mapping.pdf)
9. **Deel** — global payroll/EOR; single-system salary approval workflow, YTD payslip breakdown (gross,
   net, tax withholding, deductions all tracked year-to-date) — [How to read a paycheck stub](https://www.deel.com/blog/how-to-read-a-paycheck/), [Deel vs Paychex](https://www.deel.com/blog/deel-vs-paychex-payroll-hr-comparison/)
10. **Workday** — enterprise HCM/payroll; two-phase **calculate → commit** lifecycle (re-runnable
    calculation, then a locking commit), line-level payslip breakdown by earning code/deduction/tax
    jurisdiction — [Workday Payroll for the U.S.](https://www.workday.com/content/dam/web/en-us/documents/datasheets/datasheet-workday-payroll.pdf), [Workday Payroll overview](https://www.workday.com/en-us/products/payroll/overview.html)

(Paychex and SAP SuccessFactors were referenced for the YTD-payslip and maker/checker comparison points
but did not surface distinct new features beyond the above set.)

## Feature catalog — grouped by the five NavERP.md 3.14 bullets

### Payroll Run — Monthly processing, calculation engine
- **Period-based run header** — one run object per pay period (month) that aggregates all employees'
  payslips · seen in: Keka, greytHR, Zoho Payroll, Workday · priority: table-stakes · spine: new table
  `PayrollCycle` (tenant-scoped, one per period) · buildable now
- **Calculate → review → commit/lock two-phase lifecycle** — calculation can be re-run freely while in
  draft; a distinct "commit"/"finalize" step locks it against further edits · seen in: Workday, Darwinbox
  (RIVeR), greytHR (lock payroll) · priority: differentiator · spine: `PayrollCycle.status` state machine ·
  buildable now (state machine only — no re-run engine needed beyond "recompute while draft")
- **Pull each employee's active salary structure into the run** — the run reads each employee's current
  `EmployeeSalaryStructure`/template lines rather than storing salary data itself · seen in: all reviewed
  products (conceptually) · priority: table-stakes · spine: reuse `hrm.EmployeeSalaryStructure` +
  `SalaryStructureLine` + `PayComponent` · buildable now
- **Per-employee payslip generation with earnings/deductions/employer-contribution/net breakdown** · seen
  in: Workday (line-level by earning code), Deel, Keka, greytHR · priority: table-stakes · spine: new table
  `Payslip` (header) + `PayslipLine` (component snapshot) · buildable now
- **Component-line snapshotting** — a payslip's lines are a point-in-time COPY of the resolved structure
  lines, so a later salary-structure edit never rewrites historical payslips · seen in: Workday (payroll
  results worklet is immutable per run), implied by every product's "reprint payslip" feature · priority:
  common · spine: new table `PayslipLine` storing `name`/`component_type`/`amount` as plain values (no live FK
  dependency for the amount) · buildable now
- **Include/exclude headcount by pay group / employment status** — only active employees with a resolved
  salary structure are pulled into a run · seen in: Zoho Payroll (pay groups), Workday (pay group) ·
  priority: common · spine: filter on `EmployeeSalaryStructure.status=active` at generation time ·
  buildable now
- **Rollback / re-run for selected employees or the whole run** — undo a draft run's payslips and
  regenerate · seen in: Keka ("roll back payroll for some employees or entire pay group") · priority:
  differentiator · spine: delete+regenerate `Payslip` rows while `PayrollCycle.status=draft` · buildable now
- **Two-pass calculation with variance/error surfacing** (missing tax elections, workers in error status)
  before final commit · seen in: Workday · priority: differentiator · integration/later (needs a fuller
  validation/error-reporting layer; defer, but the draft/lock states support a manual "recalculate" pass)
- **Payslip PDF generation, email delivery, employee self-service portal for payslip download** · seen in:
  Darwinbox, Deel, Gusto, ADP · priority: table-stakes (in the market) but **integration/later** for NavERP
  (PDF rendering + email are out of a single Django pass)
- **Bank-file / NEFT / direct-deposit disbursement generation** · seen in: ADP, Rippling, Gusto, greytHR ·
  priority: table-stakes (in the market) · integration/later (external banking file formats)

### Payroll Approval — Multi-level approval before disbursement
- **Configurable simple vs. multi-level (custom) approval chains** for a pay run · seen in: Zoho Payroll
  (Settings → Approvals, simple or custom with WHEN/AND/OR criteria and multiple levels), Darwinbox (RIVeR
  "Verify & e-approve" step), greytHR (salary-revision approval chain) · priority: differentiator (full
  configurable-criteria engine) but a fixed 1–2-level chain is table-stakes · spine: new status field +
  simple sequential approval on `PayrollCycle` · buildable now (fixed HR-review → Finance-approve two-step;
  a fully configurable N-level criteria engine deferred)
- **Maker/checker separation** — the person who runs/calculates payroll is not the same person who gives
  final sign-off · seen in: Workday (two-phase calculate/commit performed by different roles in practice),
  Darwinbox · priority: common · spine: `PayrollCycle.submitted_by` / `approved_by` fields (distinct users) ·
  buildable now
- **Preview-before-approve summary** — total payroll cost, per-employee take-home, comparison to the
  previous cycle, shown before the approve action is available · seen in: Rippling ("Preview Payroll"),
  Gusto ("Review summary") · priority: common · spine: computed properties on `PayrollCycle`
  (`total_gross`, `total_net`, `headcount`) surfaced on the review/detail page · buildable now
- **Approval is required only for regular/monthly runs, not every off-cycle/bonus run** — some products
  (Gusto) explicitly skip the approval step for off-cycle/bonus payrolls · seen in: Gusto · priority:
  common · spine: `PayrollCycle.cycle_type` (regular vs. off_cycle/bonus) gates whether approval is
  enforced · buildable now
- **Audit trail of who submitted/approved/rejected and when, with rejection reason** · seen in: greytHR
  (Approve/Reject salary revisions), Zoho Payroll · priority: common · spine: `PayrollCycle` status +
  timestamp + actor fields (mirrors the `FloatingHolidayElection` approve/reject pattern already used in
  3.12) · buildable now
- **Post-approval hand-off to finance/accounting for disbursement & GL posting** · seen in: ADP (GLI),
  Workday, all enterprise products · priority: table-stakes · spine: `PayrollCycle.accounting_payroll_run`
  FK to `accounting.PayrollRun` (string FK) — populated on finalize, GL posting stays in accounting ·
  buildable now (the hand-off; not the JE logic itself)

### Salary Holds — Hold salary for specific employees
- **Per-employee "hold payout" flag within a run** — the employee's payslip is still computed (statutory
  contributions/deductions still calculated for compliance) but the net-pay disbursement is withheld; the
  employee is excluded from the bank/payment file · seen in: Keka ("Salary on Hold & Arrears" tile — "the
  payout will be held, no payment will be made yet, release later"), greytHR ("Hold Salary Payout" /
  "Stop Salary Processing", used for notice-period/absconding/maternity cases), factoHR ("stop payment"
  monthly input) · priority: table-stakes · spine: new field `Payslip.on_hold` (boolean) + `hold_reason`
  (text) + `released_at`/`released_by` — reuse the same `Payslip` row, don't fork a table · buildable now
- **Reason/category for the hold** (absconding, uninformed leave, notice period, dispute, pending
  clearance) · seen in: Keka, greytHR · priority: common · spine: `Payslip.hold_reason` free-text (or a
  small choices list); no new master needed · buildable now
- **Release a held salary later** — a subsequent action (or the next cycle) pays out the previously held
  net amount, distinct from a fresh arrears calculation · seen in: Keka ("release the payout later
  whenever required") · priority: common · spine: `Payslip.on_hold` toggled off + a `released` audit
  timestamp; actual re-disbursement handled as a follow-up off-cycle/adjustment payslip · buildable now
  (flag + audit fields); the disbursement mechanics are integration/later
- **Two distinct hold outcomes — "pay later" vs. "void/never pay"** · seen in: Keka (admin can mark held
  salary as "arrears", or "void/Never Pay") · priority: differentiator · spine: could be a
  `hold_resolution` choice (`pending`/`release_next_cycle`/`void`) on `Payslip` · buildable now as an
  optional field, else defer to a status choice only

### Arrears Calculation — Retroactive calculations
- **Arrears from a mid-period/back-dated salary revision** — when a new `EmployeeSalaryStructure` is
  created with an `effective_from` in the past relative to when it's approved, the difference between old
  and new pay for the already-processed months is computed and paid in the next run · seen in: Keka,
  greytHR (arrears explicitly tied to the salary-revision workflow), factoHR ("back-dated increments") ·
  priority: table-stakes · spine: `Payslip.arrears_amount` (a single rolled-up decimal on the payslip,
  computed as `(new_component_amount - old_component_amount) × affected_months`), optionally itemized via
  a dedicated `PayslipLine` row of `component_type='arrears'` so it appears in the earnings breakdown ·
  buildable now (simple formula version); a full retroactive-recalculation engine that re-derives every
  historical period's difference automatically is differentiator/deferred
- **New-joinee arrears** — pay due for days already worked when an employee joins after a run has already
  been processed for that period · seen in: Zoho Payroll (explicit "New Joinee Arrear" concept, CSV bulk
  upload of arrears) · priority: common · spine: same `Payslip.arrears_amount` field, source-agnostic (the
  UI/entry can label the reason); CSV bulk-import is integration/later · buildable now (manual entry)
  / integration/later (bulk CSV import)
  automatically flowing into the next payroll cycle · seen in: Zoho Payroll ("Once the salary revision is
  approved, arrears are automatically calculated and processed in the payout month") · priority:
  differentiator · spine: could be automated by a helper that diffs the employee's current vs. prior
  `EmployeeSalaryStructure.annual_ctc_amount` when generating the next `PayrollCycle`'s payslips — flagged
  as a nice-to-have automation, not required for v1 (manual arrears-amount entry per payslip is the
  buildable baseline)
- **Arrears also cover attendance/overtime corrections from a prior period**, not just salary revisions ·
  seen in: factoHR ("previous months' attendance correction, or overtime") · priority: common · spine: same
  `arrears_amount` field — reason is descriptive, not structurally different · buildable now

### Bonus Processing — Performance bonus, ex-gratia
- **Off-cycle / "extra pay" bonus run distinct from the regular monthly run** — bonuses, corrections, and
  one-time payments processed outside the standard cycle, often with fewer controls (e.g., no approval
  step) · seen in: Rippling (unlimited off-cycle runs), Gusto ("Extra Pay" payroll, explicitly skips
  approval), Zoho Payroll (off-cycle pay run supports withholding salary, new-joinee arrears, LOP reversal
  too) · priority: table-stakes · spine: `PayrollCycle.cycle_type` choice (`regular`/`off_cycle`) rather
  than a separate model — an off-cycle cycle is still a `PayrollCycle` with its own period/payslips ·
  buildable now
- **Bonus/ex-gratia amount recorded per employee, taxed as supplemental earning, shown as its own payslip
  line** · seen in: Gusto ("appears as a separate line item on the pay stub"), Keka, factoHR (performance
  incentive formulas) · priority: table-stakes · spine: `Payslip.bonus_amount` rolled-up decimal, mirrored
  as a `PayslipLine` with `component_type='bonus'`/`ex_gratia` for the itemized breakdown · buildable now
- **Formula/criteria-driven incentive calculation** (e.g., % of sales achieved against a target) · seen in:
  factoHR · priority: differentiator · integration/later (needs a rules/target-tracking engine tied to
  sales or KPI data — out of scope for this pass; store the resulting number, don't build the formula
  engine)
- **Bonus is still subject to statutory contributions** (tax, PF, etc.) even though it's a one-time
  component · seen in: Gusto ("bonuses add supplemental wages taxed at the regular rate") · priority:
  common · spine: bonus contributes to `Payslip.gross_pay` before deductions are computed, same as any
  other earning · buildable now

### Cross-cutting — Pro-ration / LOP (feeds the calculation engine, not a named 3.14 bullet but required
by "Monthly processing, calculation engine")
- **LOP (loss-of-pay) deduction for unpaid leave days** — `LOP = (monthly salary / days-in-period) ×
  LOP days`, reducing each earning component proportionally (reimbursements typically excluded) · seen in:
  Zoho Payroll (dedicated LOP explainer), factoHR, general market convention · priority: table-stakes ·
  spine: `Payslip.lop_days` + `lop_amount` (computed), sourced from `hrm` attendance/leave data (leave
  module already exists in 3.10) · buildable now as a manual/derived field; wiring it automatically to
  actual unpaid-leave records from 3.10 is a light integration — flag as a fast-follow, not blocking
- **Pro-ration for mid-period joiners/leavers** — `(monthly gross / working days in period) × days
  worked` · seen in: general market convention (Zoho, factoHR, Keka all support it) · priority:
  table-stakes · spine: `Payslip.days_worked` / `days_in_period` used to derive `gross_pay` when an
  employee's `EmployeeProfile` join/exit date falls inside the cycle period · buildable now (simple
  ratio); calendar-day vs. working-day method configurability is a policy choice — default to calendar-day
  for v1, note as a config point

## Recommended build scope (this pass — 4 models)

- **`PayrollCycle`** [`PRC-`, `TenantNumbered`] — the HRM operational run header (named distinctly from
  `accounting.PayrollRun` per the coordination rule).
  - `period_start`, `period_end`, `pay_date` (dates) — from Payroll Run / monthly processing (Keka,
    greytHR, Zoho, Workday).
  - `cycle_type` choices `regular` / `off_cycle` / `bonus` — from Rippling/Gusto/Zoho off-cycle-vs-regular
    distinction; gates whether approval is enforced (Gusto: off-cycle skips approval).
  - `status` choices `draft` / `pending_approval` / `approved` / `rejected` / `locked` — from Workday's
    calculate→commit two-phase lifecycle + greytHR "lock payroll" + Darwinbox RIVeR review/verify/approve/
    release stages, collapsed to a buildable state machine.
  - `submitted_by`, `submitted_at`, `approved_by`, `approved_at`, `rejection_reason` — maker/checker +
    audit trail (greytHR Approve/Reject, Zoho approval workflow), mirrors the `FloatingHolidayElection`
    approve/reject pattern from 3.12.
  - Derived properties: `headcount`, `total_gross`, `total_deductions`, `total_net` (sum across
    `Payslip`s) — preview-before-approve summary (Rippling "Preview Payroll", Gusto "Review summary").
  - `accounting_payroll_run` — `models.ForeignKey('accounting.PayrollRun', on_delete=models.SET_NULL,
    null=True, blank=True, editable=False)` — set when the cycle is finalized/locked, carrying the rolled-up
    totals into the existing accounting GL-posting flow (ADP GLI / Workday commit pattern, mapped to the
    existing `accounting.PayrollRun.status=draft` → `payroll_run_post` flow). **No JE logic duplicated here.**

- **`Payslip`** [`PSL-`, `TenantNumbered`] — one per employee per cycle.
  - `cycle` FK → `PayrollCycle`; `employee` FK → `hrm.EmployeeProfile` (reuse, no new master);
    `salary_structure` FK → `hrm.EmployeeSalaryStructure` (the structure this payslip was computed from —
    calculation-engine input, Keka/greytHR/Zoho all pull from the current structure).
  - `days_in_period`, `days_worked` (for pro-ration on mid-period joiners/leavers — general market
    convention) and `lop_days` / `lop_amount` (loss-of-pay deduction — Zoho Payroll LOP, factoHR).
  - `gross_pay`, `total_deductions`, `net_pay` (derived, `editable=False`, computed at generation time from
    the resolved `SalaryStructureLine`s pro-rated by `days_worked/days_in_period`, minus LOP) — the core
    calculation engine (all products).
  - `arrears_amount` (decimal, default 0) — retroactive pay from a back-dated structure revision or
    new-joinee arrears (Keka, greytHR, Zoho "New Joinee Arrear", factoHR back-dated increments);
    contributes to `gross_pay`.
  - `bonus_amount` (decimal, default 0) — performance bonus / ex-gratia, taxed as a normal earning (Gusto,
    Keka, factoHR); contributes to `gross_pay`.
  - `on_hold` (boolean, default False), `hold_reason` (text, blank), `released_at` (nullable datetime) —
    Salary Holds (Keka "Salary on Hold & Arrears", greytHR "Hold Salary Payout" — computed but not
    disbursed, excluded from the pay/bank file).
  - `status` choices mirroring the cycle (`draft`/`finalized`) or simply inherit lock state from
    `cycle.status` — avoid duplicating a second state machine; **recommendation: no independent Payslip
    status field, derive "locked" from `cycle.is_locked`.**

- **`PayslipLine`** [`TenantOwned`, no own number] — per-component breakdown, snapshotted at generation
  time so later `PayComponent`/structure edits never rewrite history (Workday's immutable payroll-results
  worklet; general "reprint payslip" expectation across every product).
  - `payslip` FK → `Payslip`; `component_name` (copied string, not a live FK to `PayComponent` for the
    label), `component_type` choices mirroring `PayComponent.COMPONENT_TYPE_CHOICES` plus `arrears` and
    `bonus` as additional line types for the itemized breakdown (Gusto "bonus as separate pay-stub line
    item", Keka/greytHR arrears line).
  - `amount` (decimal) — the resolved, pro-rated value for this line on this payslip.
  - `sequence` (small int, for consistent payslip ordering — mirrors `SalaryStructureLine.sequence`).

- **(Optional 4th if scope allows) `PayrollAdjustment`** — a small adhoc-item table only if arrears/bonus
  need a richer audit trail than a flat `Payslip.arrears_amount`/`bonus_amount` field (e.g. multiple
  arrears entries per payslip with distinct reasons/periods). **Recommendation: start WITHOUT this model** —
  the flat `arrears_amount`/`bonus_amount` fields on `Payslip` plus their mirrored `PayslipLine` rows are
  sufficient for v1 per the researched feature set (Keka/greytHR/Zoho all show arrears/bonus as a rolled-up
  number on the payslip, not a multi-entry ledger). Revisit only if a later pass needs per-arrears-item
  history (e.g. "3 separate arrears entries from 3 different revisions").

## Calculation engine (buildable core)

```
For each employee with an active EmployeeSalaryStructure as of cycle.period_end:
  1. Resolve annual_ctc_amount and each SalaryStructureLine.resolved_amount() (existing 3.13 methods).
  2. Convert annual → period amount (monthly = annual/12; matches PayComponent.frequency semantics
     already on the component: monthly components divide by 12, one_time/annual components pass through
     as-is on the periods they apply).
  3. Pro-rate each earning line by (days_worked / days_in_period) if the employee joined/left mid-period.
  4. Subtract lop_amount = (period_gross / days_in_period) * lop_days from the pro-rated gross.
  5. Add arrears_amount and bonus_amount to gross_pay (both are supplemental earnings).
  6. Sum all deduction-type lines (statutory_deduction + voluntary_deduction component_types) →
     total_deductions.
  7. net_pay = gross_pay - total_deductions  (derived, matches the existing accounting.PayrollRun
     net_pay-is-derived convention).
  8. Snapshot every resolved line (+ arrears/bonus/LOP as their own lines) into PayslipLine rows.
  9. If on_hold: net_pay is still computed and included in cycle deduction/tax totals, but excluded from
     any disbursement/bank-file total (out of scope) and flagged for the accounting hand-off note.
```

## Posting hand-off to `accounting.PayrollRun`
On `PayrollCycle` finalize/approve (status → `locked`):
1. Sum `headcount`, `gross_pay`→`gross_wages`, employee-side statutory deduction lines→`employee_tax`,
   employer-side contribution lines→`employer_tax`, remaining voluntary deductions→`deductions` across all
   non-void payslips in the cycle (holds still count — per Keka/greytHR, held salaries still hit statutory
   totals).
2. Create (or update, if re-run) one `accounting.PayrollRun` row via `PayrollRun.objects.create(tenant=...,
   period_start=cycle.period_start, period_end=cycle.period_end, pay_date=cycle.pay_date,
   headcount=..., gross_wages=..., employee_tax=..., employer_tax=..., benefits=..., deductions=...)` —
   `net_pay` is derived automatically by the existing `PayrollRun.save()`.
3. Link it back via `PayrollCycle.accounting_payroll_run`.
4. Leave `status='draft'` on the `accounting.PayrollRun` — actual GL posting continues to happen through
   accounting's own `payroll_run_post` view/action, unchanged. **HRM never constructs a `JournalEntry`.**

## Deferred (later passes / integrations)
- **Full statutory engine** (PF/ESI/PT/TDS slabs, challans, returns, Form 16) — that is NavERP.md **3.15
  Statutory Compliance**, a separate sub-module; this pass only needs generic
  `statutory_deduction`/`employer` contribution lines already modeled by `PayComponent`.
- **Bank file / NEFT / direct-deposit disbursement generation** — external banking integration (ADP,
  Rippling, Gusto, greytHR all have this); out of a single Django pass.
- **Tax-slab TDS/withholding computation engine** — needs annual tax-regime rules (NavERP.md 3.16 Tax &
  Investment); this pass stores the deduction amount but does not compute it from a slab table.
- **Payslip PDF rendering + email delivery + employee self-service download portal** — templating/PDF
  generation and email dispatch; defer to an integration pass.
- **Off-cycle multi-country / multi-currency payroll** (Deel's core differentiator) — out of scope; NavERP
  payroll assumes single-currency per tenant for now, consistent with `SalaryStructureTemplate.currency`.
- **YTD tax projection / cumulative annual payslip aggregation view** — useful (Deel, Workday) but a
  reporting concern layered on top of per-cycle `Payslip` rows already being retained; can be added as a
  query/report later without new models.
- **Configurable N-level approval criteria engine** (Zoho's WHEN/AND/OR custom approval builder) — v1 ships
  a fixed submitted→approved/rejected two-step; a rules-based configurable chain is differentiator/deferred.
- **Automatic arrears computation by diffing salary-structure history** — v1 takes `arrears_amount` as a
  manually-entered/derived-once value on the payslip; an automated "detect every back-dated structure
  change since the last processed cycle and compute the exact delta" engine is a fast-follow, not blocking.
- **Rollback/re-run UX for a subset of employees within a locked cycle** (Keka) — v1 only allows
  regenerate-while-draft; once `locked`, a correction requires a new off-cycle `PayrollCycle` (matches
  Workday's "corrections require off-cycle processing" convention) rather than in-place edits.
- **Formula/criteria-driven incentive calculation** (factoHR's target-based bonus %) — store the resulting
  `bonus_amount`, don't build the rules/target-tracking engine.
- **`accounting.PayrollRun` extension** (noted above) — if a cleaner "post directly from HRM" helper is
  wanted instead of leaving it in accounting's existing UI, that is a small accounting-side follow-up, not
  part of this HRM pass.

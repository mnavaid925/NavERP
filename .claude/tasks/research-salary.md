# Research — Module 3: HRM — Sub-module 3.13 Salary Structure (salary)

Scope note: this research covers ONLY the compensation **definition/master-data** layer (pay components,
grade-wise structure templates/CTC breakdown, variable-pay definitions, tax/statutory components,
reimbursement definitions). It explicitly excludes the payroll **run**/calculation engine, payslip generation,
disbursement, and GL posting — those belong to 3.14 Payroll Processing and `accounting.PayrollRun`
(already implemented; see Deferred section and the coordination boundary note).

## Leaders surveyed (with source links)

1. **Keka** — India-centric HRIS/payroll leader; formula-driven salary-structure builder with per-component
   fixed/percentage formulas — [Create/edit a custom salary structure](https://help.keka.com/admin/knowledge/how-to-create/edit-a-new/custom-salary-structure), [Salary structure in India](https://www.keka.com/salary-structure-in-india), [CTC glossary](https://www.keka.com/glossary/ctc), [Salary breakup glossary](https://www.keka.com/glossary/salary-breakup)
2. **greytHR** — India payroll/HRMS; CTC structure template + IT (income-tax) component editor + payslip categorized by Gross/Deduction/PF groups — [Add/Revise salary](https://admin-help.greythr.com/admin/answers/88238753/), [CTC structure template](https://www.greythr.com/downloadable-resource/ctc-structure/), [IT components](https://admin-help.greythr.com/admin/answers/122162792/), [Payroll preferences / reimbursement attachments](https://admin-help.greythr.com/admin/answers/123828110/)
3. **Darwinbox** — Enterprise HRMS (APAC/India); configurable salary structure with formula builder, fixed vs. variable component split, total-rewards statement — [Compensation Management Suite](https://darwinbox.com/en-us/solutions/use-cases/compensation-management-suite), [Understanding key compensation components](https://darwinbox.com/blog/understanding-the-key-compensation-components-for-effective-management), [CTC glossary](https://darwinbox.com/hr-glossary/cost-to-company)
4. **Zoho Payroll** — SMB/India payroll; explicit four-way component taxonomy (Earnings/Benefits/Deductions/Corrections) + statutory component toggles — [Salary Components settings](https://www.zoho.com/in/payroll/help/employer/settings/set-salary-components.html), [Statutory Components settings](https://www.zoho.com/in/payroll/help/employer/settings/set-statutory-components.html), [Payroll compliance](https://www.zoho.com/in/payroll/payroll-compliance/)
5. **factoHR** — India payroll; Salary Master with revision dates, 200+ CTC templates, dedicated reimbursable-component guidance — [CTC calculator](https://factohr.com/calculate-ctc-structure/), [Salary structure in India](https://factohr.com/salary-structure-india/), [Payroll components guide](https://factohr.com/payroll-components/), [Reimbursable components of salary](https://factohr.com/reimbursable-components-of-salary/)
6. **RazorpayX Payroll** — India payroll; per-employee custom salary structure override + explicit Bonus Management (types, clawback) + ad hoc variable "Additions" during a run — [Salary settings](https://razorpay.com/docs/payroll/salary/), [Bonus Management](https://razorpay.com/docs/payroll/bonus/), [What is variable pay](https://razorpay.com/payroll/learn/what-is-variable-pay/)
7. **Rippling** — US HR/IT/Finance platform; payroll tied to unified employee record, automated deductions synced from benefits enrollment — [Rippling vs Gusto comparison](https://www.rippling.com/rippling-vs-gusto)
8. **Gusto** — US payroll/benefits for SMBs; guided pay-schedule + benefits (medical/dental/401k) deduction setup feeding payroll — [Gusto vs Rippling](https://gusto.com/product/compare/gusto-vs-rippling)
9. **Workday** — Enterprise HCM; explicit 3-tier architecture — Compensation Element (pay-item building block) → Compensation Plan (Salary/Bonus/Allowance/Equity Plan) → Compensation Grade + Grade Profile (band by location/job family), bundled into Compensation Packages — [Workday Compensation Architecture 101](https://workdaynavigator.com/blog/workday-compensation-architecture/), [Workday Compensation datasheet](https://www.workday.com/content/dam/web/en-us/documents/datasheets/datasheet-workday-compensation.pdf)
10. **SAP SuccessFactors Employee Central** — Enterprise HCM; Pay Grade + Pay Range (min/mid/max) + Pay Component + Pay Matrix (grade x location/job-level) — [Pay Grade/Pay Range](https://help.sap.com/docs/successfactors-employee-central/implementing-employee-compensation-data/pay-grade-pay-range), [Configuring the Compensation Structure Object](https://help.sap.com/docs/SAP_SUCCESSFACTORS_EMPLOYEE_CENTRAL/0514f99ba10b466aa4d89b3eb3d8ff10/6cb0b3671d454f9ca63d17624e74a7a2.html)
11. *(supporting reference)* **BambooHR** — Levels & Bands (job levels → pay bands) + compensation review cycles — [Levels and Bands](https://www.bamboohr.com/product-updates/levels-and-bands)
12. *(supporting reference)* **Personio** — localized payroll fields, multi-currency compensation for international teams (referenced for the "currency stays simple for now" note)

## Feature catalog by sub-module (3.13 bullets)

### Pay Components (Basic, HRA, allowances, deductions)
- **Component master with type taxonomy** — a reusable catalog of named pay items, each tagged earning /
  benefit(pre-tax) / deduction(post-tax) / statutory — seen in: Zoho Payroll (explicit Earnings/Benefits/
  Deductions/Corrections categories), Keka, greytHR (Gross/Deduction/PF groups), Darwinbox · priority:
  table-stakes · spine: new table `PayComponent` (tenant-scoped catalog, not per-employee) · buildable now.
- **Calculation type per component** — fixed amount vs. percentage-of-basic vs. percentage-of-CTC/gross vs.
  formula referencing other components — seen in: Keka ("formula" per component), Zoho Payroll (fixed/
  percentage/custom formula), Darwinbox (formula builder) · priority: table-stakes (fixed/percentage);
  differentiator (full formula engine) · spine: field on `PayComponent`/`SalaryStructureLine` ·
  buildable now (fixed + %-of-basic + %-of-CTC); formula engine referencing arbitrary components is
  differentiator/deferred.
- **Taxable flag** — whether a component counts toward taxable income vs. is tax-exempt/pre-tax — seen in:
  Zoho Payroll ("fixed earnings... considered as taxable"), factoHR (fuel reimbursement "completely exempt
  from tax") · priority: common · spine: boolean field on `PayComponent` · buildable now.
- **Frequency** — monthly (recurring) vs. annual/one-time (bonus, LTA once/year) vs. per-run variable entry —
  seen in: Zoho Payroll ("Deductions are one-time... won't recur"), RazorpayX (ad hoc "Additions" per run) ·
  priority: table-stakes · spine: choice field on `PayComponent` · buildable now.
- **Active/inactive + display order** — enable/disable a component org-wide without deleting historical data,
  and control the order components print on payslip/breakdown — seen in: Keka, Zoho Payroll · priority:
  common · spine: `is_active` + `display_order` fields · buildable now.
- **Include-in-CTC vs. off-CTC flag** — some components (e.g. certain reimbursements/benefits) sit outside
  the CTC total or are shown separately — seen in: Zoho Payroll ("Benefits... reduce net taxable income"),
  Darwinbox (Direct/Indirect Benefits/Savings split) · priority: common · spine: boolean field on
  `PayComponent` · buildable now.

### Salary Structure Templates (Grade-wise structures, CTC breakdown)
- **Template tied to a job grade/band** — a reusable structure definition scoped to a grade (or grade +
  location) rather than built per employee from scratch — seen in: Workday (Compensation Grade + Grade
  Profile), SAP SuccessFactors (Pay Grade/Pay Matrix by grade x location/job-level), greytHR (pay-group
  structures) · priority: table-stakes · spine: new table `SalaryStructureTemplate` FK `hrm.JobGrade` ·
  buildable now.
- **Component line list (the CTC breakup)** — a template is a set of component rows each with an amount or
  percentage, whose sum computes the CTC — seen in: Keka, greytHR (CTC structure template), factoHR
  ("configure multiple CTC components for precise salary breakdowns"), Darwinbox (example: Basic, HRA, LTA,
  Special Allowance, Employer PF, Mobile/Internet, Professional Development) · priority: table-stakes ·
  spine: new child table `SalaryStructureLine` (template FK + component FK + amount/percentage) ·
  buildable now.
- **Min/mid/max pay range per grade** — a band the structure/CTC must fall within, used for compa-ratio /
  range-penetration checks — seen in: SAP SuccessFactors (Pay Range min/median/max), Workday (Grade Profile
  bands); NavERP already has this on `hrm.Designation.min_salary/mid_salary/max_salary` — priority:
  table-stakes (already satisfied) · spine: **reuse `hrm.Designation`/`hrm.JobGrade`** — do not duplicate ·
  buildable now (no new field needed).
- **Derived/computed CTC total** — the template's total annual/monthly CTC is derived from its line sum, not
  manually re-entered — seen in: Keka, factoHR, Darwinbox · priority: table-stakes · spine: property/method on
  `SalaryStructureTemplate`, not a stored duplicate field (mirrors NavERP's derived-field convention, e.g.
  `PayrollRun.net_pay`) · buildable now.
- **Effective-dated revisions / versioning** — a structure or an employee's assigned structure has a revision
  date so history is preserved when salary changes — seen in: factoHR (Salary Master "revision dates"),
  Workday (Compensation Review Cycles with effective dates) · priority: common · spine: `effective_from`/
  `effective_to` fields on the employee-assignment table · buildable now (simple date pair; full
  approval-cycle workflow is differentiator/deferred).
- **Pay-group / multiple structures per org** — different templates for different legal entities, pay
  groups, or locations — seen in: greytHR ("salary structures for a pay group"), SAP SuccessFactors (Pay
  Matrix by location) · priority: common · spine: could reuse tenant + optional `core.OrgUnit` scoping on the
  template later · integration/later (not needed for a single-pay-group v1).

### Variable Pay (Bonus, incentives, commissions)
- **Bonus/incentive component type with sub-type** — bonuses classed as e.g. performance, joining/signing,
  retention, festive, profit-sharing — seen in: RazorpayX (Bonus Management: types + clawback), Darwinbox
  (Joining Bonus / Performance Bonus as named variable components), Workday (Bonus Plan as a distinct
  Compensation Plan type) · priority: common · spine: `component_type="variable"` + a `variable_subtype`
  choice on `PayComponent` (or free-text label) · buildable now.
- **One-time vs. recurring variable entry** — most variable pay is entered per pay-run rather than as a fixed
  recurring line, but the *component definition* (that "Performance Bonus" exists as a payable item, its
  default calc type, taxability) still lives in the setup layer — seen in: RazorpayX ("add incentives...
  during Run Payroll"), Zoho Payroll (Variable Pay = "entered during payroll processing") · priority:
  table-stakes · spine: `frequency="one_time"` choice on `PayComponent`; the actual per-period amount entry
  is 3.14's job · buildable now (definition only).
- **Clawback / recovery flag** — some bonus types can be recovered if the employee leaves before a vesting
  period — seen in: RazorpayX (Bonus Management "clawbacks") · priority: differentiator · spine: boolean/
  note field on `PayComponent` · buildable now as a simple flag; the recovery calculation itself is
  integration/later.
- **Commission (sales-linked variable pay)** — a named variable component representing sales commission —
  seen in: Workday (Bonus Plan family covers incentive/commission plans generically) · priority: common ·
  spine: modeled as another `PayComponent` row with `variable_subtype="commission"` — no new table needed ·
  buildable now (definition only; commission calculation against CRM/Sales figures is integration/later).

### Tax Components (TDS, professional tax, PF, ESI)
- **Statutory component catalog with jurisdiction rules** — PF (Provident Fund), ESI (Employee State
  Insurance), Professional Tax, TDS (income tax withholding), and (for US-style orgs) 401(k)/FICA equivalents,
  each with its own contribution basis and rate — seen in: Zoho Payroll (dedicated Statutory Components
  settings: EPF/ESI/PT/LWF/TDS with establishment codes), greytHR (IT/income-tax component editor), factoHR,
  Gusto (401k/benefits deductions feeding payroll) · priority: table-stakes · spine: modeled as
  `PayComponent` rows with `component_type="statutory"` (not a separate table) — e.g. "Employee PF", "Employer
  PF", "ESI", "Professional Tax", "TDS" · buildable now.
- **Employee vs. employer contribution split** — PF and ESI both have an employee-paid and an employer-paid
  leg with different rates on the same basis — seen in: Zoho Payroll (EPF 12%/12% of Basic+DA split
  employee/employer; ESI 0.75%/3.25% of Gross split) · priority: table-stakes · spine: a `contribution_side`
  choice (employee/employer/both) on `PayComponent`, or two paired component rows ("PF – Employee", "PF –
  Employer") · buildable now.
- **Eligibility thresholds** — statutory components often apply only below a salary ceiling (ESI ≤ ₹21,000/mo
  gross; LWF/PF have their own thresholds) — seen in: Zoho Payroll (ESI/LWF wage ceilings called out
  explicitly) · priority: common · spine: optional `threshold_amount` field on `PayComponent`, used
  descriptively; actual eligibility enforcement during a run is 3.14's job · buildable now (store the
  threshold; don't enforce it here).
- **Calculation basis reference** — PF/ESI compute off "Basic + DA" or "Gross", not off CTC — i.e. the
  statutory component's percentage must reference a specific *other* component or component group, not just
  "basic" — seen in: Zoho Payroll (explicit Basic+DA / Gross basis per statutory item) · priority: common ·
  spine: `calculation_type="pct_of_basic"` covers the common case; a `pct_of_gross`/reference-to-specific-
  component case is a differentiator · buildable now for the basic/CTC cases; full arbitrary-basis reference
  is deferred.

### Reimbursements (LTA, medical, fuel, mobile)
- **Reimbursement component catalog** — named reimbursable items (LTA, medical, fuel/conveyance, mobile/
  internet, uniform, children's education, meal coupons) each with its own tax-exemption rule and annual/
  monthly cap — seen in: factoHR (dedicated reimbursable-components guide listing LTA/medical/fuel/mobile/
  uniform/education/meal), greytHR (Reimbursement section in Payroll Preferences) · priority: table-stakes ·
  spine: `component_type="reimbursement"` on `PayComponent` · buildable now.
- **Claim cap / annual limit** — reimbursements are typically capped per year (e.g. LTA twice in a 4-year
  block, fixed annual medical limit) — seen in: factoHR (LTA/medical component descriptions with limits) ·
  priority: common · spine: `annual_cap_amount` field on `PayComponent` · buildable now (store the cap; the
  actual claim-tracking/consumption ledger is a later/integration feature).
- **Bill/attachment requirement flag** — some reimbursement items require a submitted bill/receipt before
  payout is processed — seen in: greytHR ("select reimbursement items for which attachments must be
  mandatory") · priority: common · spine: boolean `requires_bill` field on `PayComponent` · buildable now
  (flag only; actual document upload/claim workflow is deferred to a claims/expense feature).
- **Tax-exempt-up-to-limit vs. fully taxable** — most reimbursements are tax-exempt up to a limit and taxable
  above it (or fully exempt, e.g. fuel against bills) — seen in: factoHR (fuel "completely exempt from tax"),
  Darwinbox (LTA/Mobile listed among "fixed salary components" that are largely non-taxable perks) ·
  priority: common · spine: reuses the `taxable` boolean + `annual_cap_amount` from the Pay Components
  section (exempt-up-to-cap is a documented convention, not a separate field) · buildable now.

## Recommended build scope (this pass — 4 models)

- **`PayComponent`** [no numeric prefix — small catalog like `JobGrade`, identified by name] — the unified
  component master covering Pay Components + Variable Pay + Tax Components + Reimbursements in one table:
  - `component_type`: choices `earning | statutory_deduction | voluntary_deduction | reimbursement |
    variable` — collapses Zoho's Earnings/Benefits/Deductions taxonomy and factoHR/Zoho's statutory list
    into one enum, justified by: Zoho Payroll's 4-way taxonomy, greytHR's Gross/Deduction/PF grouping.
  - `calculation_type`: choices `fixed_amount | pct_of_basic | pct_of_ctc | pct_of_gross` — justified by:
    Keka/Zoho/Darwinbox formula-driven components (full arbitrary formula deferred, see below).
  - `frequency`: choices `monthly | annual | one_time` — justified by: Zoho Payroll's recurring-earning vs.
    one-time-deduction distinction, RazorpayX's per-run variable additions.
  - `is_taxable` (boolean) — justified by: Zoho Payroll's fixed-earning-is-taxable rule, factoHR's
    tax-exempt fuel reimbursement.
  - `is_active`, `display_order` — justified by: Keka/Zoho component management UX.
  - `include_in_ctc` (boolean) — justified by: Zoho's Benefits-vs-CTC split, Darwinbox's Direct/Indirect
    Benefits/Savings split.
  - `contribution_side`: choices `employee | employer | both` — justified by: Zoho Payroll's PF/ESI
    employee-vs-employer contribution split.
  - `annual_cap_amount` (nullable decimal) — justified by: factoHR's LTA/medical claim caps.
  - `requires_bill` (boolean) — justified by: greytHR's mandatory-attachment reimbursement setting.
  - `default_percentage` (nullable decimal, used when `calculation_type` is a percentage type) and
    `default_amount` (nullable decimal, used when `calculation_type="fixed_amount"`) — the org-wide default
    that a `SalaryStructureLine` can override per template.
  - Tenant-scoped catalog table (like `JobGrade`), unique on `(tenant, name)`.

- **`SalaryStructureTemplate`** [SST-numbered via `TenantNumbered`, e.g. `SST-00001`] — the grade-wise CTC
  container, justified by: Workday's Compensation Grade + Grade Profile, SAP SuccessFactors' Pay Grade/Pay
  Matrix, greytHR's "salary structures for a pay group", Keka's named custom salary structure:
  - `name` (e.g. "L3 Engineer — Standard CTC").
  - `job_grade` FK → **`hrm.JobGrade`** (reuse, do not duplicate the grade catalog).
  - `annual_ctc_amount` — the template's declared target CTC (used to derive `pct_of_ctc` line amounts);
    optionally left blank if the template is amount-driven line-by-line instead.
  - `currency` — plain `CharField` (e.g. `"USD"`/`"INR"`, default from tenant settings) — kept
    self-contained per the brief; do not FK `accounting.Currency` in this pass.
  - `is_active`.
  - `computed_ctc_total` as a derived **property** (sum of resolved line amounts), not a stored field —
    mirrors the `PayrollRun.net_pay`-style derived-field convention already used in `accounting`.

- **`SalaryStructureLine`** [child of `SalaryStructureTemplate`, plain `TenantOwned`, no separate number] —
  the CTC breakdown row, justified by: Keka's per-component formula rows, greytHR's CTC structure template,
  factoHR's "configure multiple CTC components for precise salary breakdowns":
  - `template` FK → `SalaryStructureTemplate` (`related_name="lines"`).
  - `pay_component` FK → `PayComponent`.
  - `calculation_type` override (optional; defaults to the component's own `calculation_type` if blank) and
    `amount`/`percentage` value actually used on this template (overrides the component's
    `default_amount`/`default_percentage`) — justified by: Keka's "add/change the formula of a component in
    the salary structure" (per-template override of the component default).
  - `sequence`/`display_order` for print/breakdown ordering.
  - `unique_together (tenant, template, pay_component)` — one line per component per template.

- **`EmployeeSalaryStructure`** [ESS-numbered via `TenantNumbered`, e.g. `ESS-00001`] — the effective-dated
  assignment of a structure/CTC to a specific employee, justified by: factoHR's Salary Master with revision
  dates, Workday's Compensation Review Cycle effective dates, RazorpayX's per-employee custom-structure
  override:
  - `employee` FK → **`hrm.EmployeeProfile`** (reuse, never `core.Party` directly, per the established
    convention).
  - `template` FK → `SalaryStructureTemplate` (the base structure this employee is on).
  - `annual_ctc_amount` — the employee's actual assigned CTC (may differ from the template's default,
    supporting RazorpayX-style per-employee custom overrides).
  - `effective_from` / `effective_to` (nullable — open-ended until superseded) — justified by: factoHR's
    revision-dated Salary Master, Workday's compensation-cycle effective dating.
  - `status`: choices `active | superseded` (simple two-state; no multi-level approval workflow in this
    pass — see Deferred).
  - `notes` (optional free text, e.g. reason for revision).
  - Index on `(tenant, employee, effective_from)`; at most one `status="active"` row per employee enforced in
    `clean()`.

This 4-model set reuses `hrm.JobGrade`, `hrm.Designation` (band already present — not duplicated), and
`hrm.EmployeeProfile` as the only cross-references, adds no new spine masters, and stays fully within
Django/this-repo buildable territory (no external integrations required to ship it).

## Deferred (later passes / integrations)

- **Payroll run / calculation engine** — actually computing a period's pay from the assigned structure
  (pro-ration, attendance/leave integration, arrears) is 3.14 Payroll Processing, which will consume
  `EmployeeSalaryStructure` + `PayComponent` as inputs. **3.13 must not post to the GL or create a payroll
  run** — `accounting.PayrollRun` already owns that (lesson L29: payroll posting is Accounting's job).
- **Payslip generation / YTD statements / total-rewards statements** — greytHR's CTC payslip, Darwinbox's
  total-rewards statement — presentation layer for 3.14, not 3.13.
- **Statutory filing / challan generation** — PF ECR, ESI return, TDS Form 16/24Q generation seen in
  Zoho Payroll's compliance suite — out of scope; NavERP is not a statutory filing system.
- **Full arbitrary formula engine** — Keka/Darwinbox's component formulas that reference *any* other
  component (not just basic/CTC/gross) — the 4-model scope covers the 90% case (fixed, %-of-basic,
  %-of-CTC, %-of-gross); a generic expression evaluator is a differentiator feature for a later pass if
  needed.
- **Compensation review cycles / multi-level approval workflow** — Workday's Compensation Review Cycle
  (budget pools, manager proposals, HR approval) and BambooHR's compensation planning cycles — the
  `EmployeeSalaryStructure.status` field keeps a simple active/superseded state; a full proposal→approval
  workflow is deferred.
- **Claims / expense-tracking for reimbursements** — actually submitting a bill against a reimbursement
  component and tracking consumption against `annual_cap_amount` — greytHR's mandatory-attachment setting is
  captured as a flag only; the claim submission/approval workflow belongs to a future Reimbursement Claims
  feature (or Module 13 Documents for attachment storage).
  process — the `contribution_side` field and `annual_cap_amount` capture the *definition*; per-run
  eligibility enforcement (e.g. ESI ceiling check against actual gross) is 3.14's job.
- **Multi-currency compensation** — Personio's multi-currency payroll for international teams — 3.13 keeps
  `currency` as a plain CharField per the brief; migrating to FK `accounting.Currency` is a note for a future
  pass if multi-currency payroll becomes a requirement.
- **Pay-group / multi-entity structure scoping** — greytHR's per-pay-group structures, SAP SuccessFactors'
  Pay Matrix by location — `SalaryStructureTemplate` could later gain an optional `core.OrgUnit`/location
  scope; not needed for a single-pay-group v1.
- **Benefits administration (health/dental/401k enrollment)** — Rippling's Ben Admin, Gusto's insurance
  marketplace — these are third-party benefits-carrier integrations, entirely out of scope for a Django-only
  pass; NavERP would only need a `PayComponent` row for the resulting payroll deduction, which the 4-model
  scope already supports.

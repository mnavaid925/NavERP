# Research — Module 3: HRM — Sub-module 3.15 Statutory Compliance (statutory-compliance)

## Scope note — the compliance/reporting/configuration layer, NOT a second payroll engine
This research covers the Indian statutory-payroll-compliance layer that sits **on top of** already-built
payroll (3.13 Salary Structure, 3.14 Payroll Processing). It explicitly does **not** re-model anything that
already exists:

- **`hrm.PayComponent`** (`component_type="statutory_deduction"`, `contribution_side=employee|employer|both`,
  `calculation_type`, `default_amount`/`default_percentage`) already defines PF/ESI/PT/TDS/LWF as pay-component
  *definitions* usable on a `SalaryStructureLine`.
- **`hrm.Payslip` / `hrm.PayslipLine`** already COMPUTE and SNAPSHOT the actual per-employee statutory amounts
  every cycle via `Payslip.recompute()` — each `PayslipLine` carries `component_type`, `contribution_side`, and
  `amount` for every statutory deduction/contribution, already split employee vs. employer.
- **`hrm.EmployeeProfile`** already has `national_id`/`national_id_type` (e.g. PAN) for a generic ID
  quick-reference, `bank_name`/`bank_account` for disbursement.
- **`accounting.PayrollRun`** already receives the rolled-up `employee_tax`/`employer_tax` totals per cycle
  from `hrm.PayrollCycle` and is the only place a `JournalEntry` gets built (lesson L29 — HRM/statutory never
  posts to the GL).

3.15 must therefore be a **registration/configuration + aggregation/reporting + filing-tracking** layer:
1. **Statutory registration/config per tenant** — PF/ESI/PT/TDS/LWF employer registration numbers, rates,
   wage ceilings, and (for PT/LWF) state-wise slab tables — configured once, referenced by the calculation
   engine and by the compliance registers.
2. **Per-cycle statutory register/challan** — an aggregate object, one per `PayrollCycle` per scheme (PF/ESI/
   PT/LWF) or per return period (TDS quarterly), that rolls up the already-computed `PayslipLine` amounts into
   the numbers a challan/return needs (total employee contribution, total employer contribution, headcount),
   plus a payment/filing-status workflow.
3. **Compliance calendar / due-date tracking** — a due-date register per scheme/period so nothing is missed,
   independent of any one cycle (works even for schemes without a payroll trigger, e.g. an annual PT
   registration renewal).

Money still posts through `accounting.PayrollRun`/`JournalEntry`; employees are still `hrm.EmployeeProfile`;
this pass adds no new employee master and no new ledger table — only compliance metadata, aggregation, and
filing/deadline tracking around what payroll already produced.

## Leaders surveyed (with source links)
1. **Keka** — India HRIS/payroll leader; auto-generates ECR files, Form 24Q/26Q, and state-specific challans
   the moment payroll closes, and keeps PF/ESI/TDS/PT/LWF rules current with automatic rule-change alerts —
   [Payroll Compliance Simplified](https://www.keka.com/payroll-compliance), [Managing IT, PF, LWF, PT, ESI
   filing details for the pay group](https://help.keka.com/admin/managing-it-pf-lwf-professional-tax-and-esi-filing-details-for-the-pay-group), [How to generate monthly PF ECR report](https://help.keka.com/hc/en-us/articles/39946688739345-How-to-generate-monthly-PF-ECR-report)
2. **greytHR** — India HRMS/payroll; per-branch/pay-group "Filing Location" master for PF/PT/ESI/LWF, an
   editable state-wise Professional Tax slab grid (salary-from/salary-till/tax-amount/deduction-month), and
   configurable Form 16 Part A/Part B generation (TDS circle address, signing/generated date, suppress-zero-tax,
   show-with-previous-employment) — [Add/Edit PF, PT, ESI, LWF Filing Location](https://admin-help.greythr.com/admin/answers/143353629/), [View/Update professional tax slabs](https://admin-help.greythr.com/admin/answers/143779998/), [Configure Form 16](https://admin-help.greythr.com/admin/answers/143409207/), [Payroll-related Statutory Compliances](https://www.greythr.com/hr-garden/payroll-related-statutory-compliances/)
3. **Zoho Payroll** — SMB/India payroll; a single Statutory Components settings screen to enable EPF/ESI/PT/LWF
   and enter the PF establishment code, ESI number, and PT registration number per organization; explicit wage
   ceilings (PF ₹15,000 Basic+DA, capping monthly employer/employee contribution at ₹1,800 each; ESI ₹21,000
   gross ceiling, 0.75%/3.25% employee/employer split); state-driven LWF cycle setup — [Statutory Components](https://www.zoho.com/in/payroll/help/employer/settings/set-statutory-components.html), [Statutory compliance in Zoho Payroll](https://www.zoho.com/in/payroll/academy/taxes-and-compliance/compliance-in-zoho-payroll.html), [LWF in Zoho Payroll](https://www.zoho.com/in/payroll/academy/taxes-and-compliance/lwf-in-zoho-payroll.html)
4. **RazorpayX Payroll** — India payroll; automates PF/ESI/PT/LWF/TDS "periodic return filings," manages PF/ESI
   registrations, professional-tax registration+payment+filing by state, and explicitly tracks payment due dates
   (before the 15th for PF/ESI, 15th or 20th for PT depending on state) plus maintains statutory reports —
   [Statutory Compliance](https://razorpay.com/payroll/payroll-compliance/), [Manage Statutory Compliance in
   RazorpayX Payroll](https://razorpay.com/docs/payroll/statutory-compliance/?preferred-country=IN), [Check
   Professional Tax Management](https://razorpay.com/docs/payroll/professional-tax/)
5. **saral PayPack** (Relyon Softech) — India payroll/statutory specialist; "Saral ePFESI" dedicated PF+ESI
   module that automates calculation, generates PF returns (ECR) and ESI returns with direct upload to
   department portals; a full compliance calendar tracking TDS (7th, Challan 281), PF+ECR (15th), ESI (15th),
   and state-specific PT due dates with penalty tracking — [Payment and Filing due dates for PF, ESI, PT, TDS](https://saralpaypack.com/blogs/pf-esi-tds-due-dates/), [Saral ePFESI](https://saralpaypack.com/saral-epfesi/), [Compliance Calendar for FY 2025–26](https://saral.pro/blogs/compliance-calendar/)
6. **Darwinbox** — enterprise HCM/payroll (APAC/India); a compliance engine that validates payroll results
   against country-specific legal requirements and files statutory reports (TDS, ESIC, PF ECR, arrears) on
   monthly/quarterly/half-yearly/annual cadences per scheme — [Ultimate Guide to Statutory Compliance in
   Payroll](https://darwinbox.com/blog/statutory-compliance-in-payroll), [10 Best Payroll Software for India](https://darwinbox.com/blog/10-best-payroll-software-india)
7. **ClearTax (ClearTDS)** — dedicated TDS return-filing platform; quarterly Form 24Q (salary TDS) / Form 26Q
   (non-salary) / Form 27Q (NRI) / Form 27EQ (TCS) filing, single-click Form 16 Part A + Part B + Form 16A
   generation, PAN validation and late-deduction error detection, unconsumed-challan matching, direct TRACES
   integration — [Form 24Q — TDS Return on Salary Payment](https://cleartax.in/s/tds-return-salary-payment), [TDS Return Filing Online](https://cleartax.in/tds), [Generate Form 16 and File TDS Return with ClearTDS](https://taxcloudindia.com/tds/features)
8. **Zimyo** — India HRMS; state-aware LWF auto-incorporation across all applicable states, a dedicated
   filterable "LWF Report," and unified PF/ESI/PT/TDS compliance automation reducing manual filing effort —
   [Statutory Compliances — Payroll](https://www.zimyo.com/payroll-software/statutory-compliance/), [What is LWF Report?](https://help.zimyo.com/docs/what-is-lwf-report/)
9. **HROne** — India payroll/compliance platform; scored specifically on "statutory compliance depth" with
   multi-state PT and LWF slabs auto-applied across 22 states/36 PT jurisdictions, and filing automation
   spanning Form 24Q, Form 16, ECR, ESIC challan, Form 12BB — [10 Best Payroll Software for India 2026](https://hrone.cloud/blog/best-payroll-software-india/), [How Payroll Software Simplifies PF, ESI, TDS & Compliances](https://hrone.cloud/blog/payroll-software-pf-esi-tds-statutory-compliance/)
10. **Kredily** — free-tier India payroll/HR; PF/ESI/PT/TDS compliance targeted specifically at small teams
    with minimal dedicated HR/finance resources, showing the "baseline" feature set even budget products
    consider must-have — [10 Best Payroll Software for India 2026](https://hrone.cloud/blog/best-payroll-software-india/)

(ADP India, Deel, and Rippling were referenced as global-equivalent payroll/compliance leaders per the brief,
but their public feature pages describe US/global tax-filing patterns rather than India-specific PF/ESI/PT/
LWF mechanics, so they did not surface additional India-specific features beyond the ten above; their
general "automated filing + compliance calendar" pattern corroborates points already sourced from Darwinbox/
Keka/RazorpayX.)

## Feature catalog by sub-module

### 3.15.a PF Management (PF calculation, challan, returns)
- **Employer PF establishment code / registration number** stored once per tenant, referenced on every
  challan/return · seen in: Zoho Payroll (Settings → Statutory Components → PF establishment code), greytHR
  (Filing Location master) · priority: table-stakes · spine: new field on a tenant-scoped statutory-config
  model (new table `StatutoryConfig` or similar) · buildable now
- **PF wage ceiling** (Basic + DA ≤ ₹15,000/month, capping the 12%/12% employee/employer contribution at
  ₹1,800 each unless the employer opts to contribute above-ceiling) · seen in: Zoho Payroll (explicit ₹15,000
  ceiling + ₹1,800 cap rule) · priority: table-stakes · spine: `wage_ceiling_amount` + `contribution_rate`
  fields on the config; **actual per-payslip enforcement stays in `Payslip.recompute()`/`PayComponent`
  defaults — this model stores/documents the ceiling, doesn't re-derive contributions** · buildable now
  (config) / already computed (payslip)
- **Monthly PF register/summary** — aggregated employee+employer contribution totals across all employees for
  a period, the source data for the ECR file · seen in: Keka ("generate monthly PF ECR report"), saral
  PayPack (Saral ePFESI automates ECR generation) · priority: table-stakes · spine: new table
  `StatutoryReturn` (scheme=`pf`, one row per `PayrollCycle`), aggregated from existing `PayslipLine` rows
  filtered by `component_type='statutory_deduction'` + a PF tag — **reuse `hrm.PayrollCycle`/`Payslip`
  totals, do not re-store per-employee PF amounts** · buildable now
- **ECR (Electronic Challan-cum-Return) file generation** — the specific EPFO government file format (member
  UAN, wages, contributions per employee, in a pipe/CSV layout) uploaded to the EPFO portal · seen in: Keka,
  saral PayPack (Saral ePFESI), HROne (ECR filing automation) · priority: differentiator · integration/later
  (the exact EPFO file format/portal upload is external; this pass stores the aggregate + per-employee detail
  needed to LATER export it, not the file-format generator itself)
- **PF challan payment tracking** (amount, payment reference, bank, paid date vs. due date) · seen in:
  RazorpayX (due-by-15th tracking), saral PayPack (compliance calendar with penalty tracking) · priority:
  common · spine: `payment_reference`, `paid_on`, `due_date` fields on `StatutoryReturn` · buildable now
- **UAN (Universal Account Number) per employee** — the lifelong PF identifier, distinct from the employer's
  establishment code · seen in: every India payroll product (UAN is EPFO-mandated) · priority: table-stakes ·
  spine: new field on a per-employee statutory-identifiers extension (see 3.15.e note) — **not** duplicating
  `EmployeeProfile`, but a small 1:1 companion table or added fields, since `EmployeeProfile.national_id` is
  generic (PAN) and doesn't fit UAN/PF/ESI-number semantics cleanly · buildable now

### 3.15.b ESI Management (ESI calculation, contributions)
- **Employer ESI code/registration number** · seen in: Zoho Payroll (ESI number field in Statutory
  Components) · priority: table-stakes · spine: field on `StatutoryConfig` · buildable now
- **ESI wage/gross ceiling** (≤ ₹21,000/month gross → ESI-eligible; above it, employee exits the scheme) ·
  seen in: Zoho Payroll (explicit ₹21,000 ceiling rule) · priority: table-stakes · spine: `wage_ceiling_amount`
  field on config, scheme-specific row · buildable now (config; enforcement already happens via
  `PayComponent`/payslip logic, this documents the threshold for the register/report)
- **Employee vs. employer contribution rate split** (0.75% employee / 3.25% employer of gross, per current
  Indian rates) · seen in: Zoho Payroll · priority: table-stakes · spine: `employee_rate`/`employer_rate`
  fields on config, used descriptively — **actual computation already happens via
  `PayComponent.contribution_side` + `Payslip.recompute()`**, this stores the documented rate for audit/
  reference and to drive the register aggregation · buildable now
- **Monthly ESI contribution register/return**, aggregated per cycle, feeding the ESIC portal upload · seen
  in: HROne ("ESIC challan" filing automation), saral PayPack (ESI returns "direct upload to department
  portals") · priority: table-stakes · spine: `StatutoryReturn` (scheme=`esi`) — same shared table as PF,
  differing only by `scheme` choice and config reference · buildable now
- **ESI number per employee** (the Insurance Number issued once an employee is ESI-eligible) · seen in: every
  India payroll product · priority: table-stakes · spine: same per-employee statutory-identifiers companion
  as UAN · buildable now
- **Direct portal upload / ESIC challan file generation** · seen in: saral PayPack, HROne · priority:
  differentiator · integration/later (external ESIC portal API/file format — store the aggregate now, wire
  the actual upload later)

### 3.15.c PT Management (Professional Tax, state-wise slab rules)
- **State-wise PT slab table** (income bracket → monthly tax amount, one table per state; deduction-month
  callouts for states that deduct in specific months rather than every month) · seen in: greytHR (editable
  state-wise slab grid: salary-from / salary-till / tax-amount / deduction-month, selectable by state) ·
  priority: table-stakes · spine: new table `ProfessionalTaxSlab` (tenant-scoped, `state`, `income_from`,
  `income_to`, `tax_amount`, `deduction_month` optional) — **this is genuinely new data NavERP doesn't have
  anywhere (not on `PayComponent`, which only supports flat/%-based calc, not bracket lookups)** · buildable
  now
- **PT registration/employer number per state** (an employer can have multiple state PT registrations if it
  has employees across states) · seen in: RazorpayX ("PT registrations, payments and return filings based on
  the location of your organization"), Zoho Payroll (PT registration number field) · priority: table-stakes ·
  spine: per-state registration numbers on `StatutoryConfig` (or a small per-state config row if the tenant
  operates in >1 state) · buildable now
- **Employee's applicable state** drives which slab applies · seen in: greytHR (map PT filing location per
  branch/employee) · priority: table-stakes · spine: reuse the employee's `work_location`
  (`EmployeeProfile.work_location`, already a free-text field) or `Employment.org_unit` location to resolve
  the applicable `ProfessionalTaxSlab.state` — **no duplicate employee-state field needed if `work_location`
  is normalized enough; otherwise a light `state` field addition on the config-matching logic** · buildable
  now
- **PT due-date variance by state** (15th or 20th depending on state, half-yearly in a few states) · seen in:
  RazorpayX (15th/20th PT split), greytHR (Odisha PT discontinued from April 2026 — slabs need an
  effective-date/discontinued flag) · priority: common · spine: `due_day`/`is_active` fields on the slab or
  config row so discontinued states can be deactivated without deleting history · buildable now
- **Annual PT registration renewal reminder** (for the states requiring it) · seen in: RazorpayX (state
  registration lifecycle) · priority: differentiator · integration/later — folds into the Compliance Calendar
  concept described under 3.15.e below rather than a dedicated PT-only feature

### 3.15.d TDS Management (Income tax deduction at source, Form 16, quarterly returns)
- **PAN validation and per-employee PAN tracking** · seen in: ClearTax (PAN validation flagged as an
  intelligent error check) · priority: table-stakes · spine: **reuse `EmployeeProfile.national_id` where
  `national_id_type='PAN'`** — do not add a duplicate PAN field · buildable now
- **Quarterly TDS return — Form 24Q** (salary TDS, one filing per quarter: Q1 Apr–Jun, Q2 Jul–Sep, Q3 Oct–Dec,
  Q4 Jan–Mar) aggregating TDS deducted across all payslips issued in the quarter · seen in: ClearTax (Form
  24Q "TDS Return on Salary Payment," filed every quarter), Darwinbox (quarterly TDS filing cadence), HROne
  (Form 24Q filing automation) · priority: table-stakes · spine: new table `StatutoryReturn` (scheme=`tds`,
  `period_type='quarterly'`) aggregating the `component_type='statutory_deduction'` TDS `PayslipLine` rows
  across every `PayrollCycle` whose `pay_date` falls in the quarter · buildable now
- **Form 16 (annual TDS certificate) — Part A (TDS deposited/deducted summary) + Part B (detailed salary/
  exemption/deduction breakup)** generated per employee per financial year · seen in: greytHR (dedicated
  Form 16 configuration: TDS circle address, signing date, generated date, "suppress zero tax," "show with
  previous employment," "show with Form 12BA"), ClearTax ("draft, merge, and mail Form 16 Part A, Part B, and
  Form 16A in a single click") · priority: table-stakes · spine: `StatutoryReturn` (scheme=`tds`,
  `period_type='annual'`, `employee` FK set) OR a lightweight generation flag/status on a per-employee annual
  aggregate — **recommendation: model Form 16 as a per-employee annual `StatutoryReturn` row so its filing
  workflow (draft → generated → issued) is tracked the same way as the quarterly org-level ones** · buildable
  now (the aggregation + status tracking; the actual PDF template/rendering is integration/later per the
  general payslip-PDF deferral already noted in 3.14's research)
- **Late-deduction / clerical-error detection before filing** (flags a TDS amount that looks wrong before it
  becomes a filing error) · seen in: ClearTax ("AI... helps identify and flag errors even before they become
  errors") · priority: differentiator · integration/later (a validation-rules engine, not core CRUD)
- **Unconsumed-challan matching / TRACES integration** (importing prior TDS challans/returns to avoid
  double-payment) · seen in: ClearTax · priority: differentiator · integration/later (external
  government-portal integration)
- **Employer TAN (Tax Deduction Account Number)** — the TDS-specific registration distinct from PAN · seen
  in: every TDS filing product (TAN is mandatory on Form 24Q/16) · priority: table-stakes · spine: field on
  `StatutoryConfig` · buildable now

### 3.15.e LWF Management (Labour Welfare Fund)
- **State applicability flag** — LWF only applies in ~16 of India's states/UTs (e.g. Maharashtra, Karnataka,
  Gujarat, Tamil Nadu, Delhi, West Bengal); a tenant operating only in non-LWF states needs it switched off
  entirely · seen in: Zimyo ("LWF... incorporated automatically for every state"), Zoho Payroll (LWF setup
  driven by company address/state) · priority: table-stakes · spine: `is_active` per-state flag, part of the
  same state-scoped config used for PT (a state can require PT, LWF, both, or neither) · buildable now
- **State-wise contribution amount + periodicity (monthly / half-yearly / annual)** — LWF amounts are small
  flat sums (₹6–₹480 range across states) and the cadence differs: some states deduct monthly, several
  (Gujarat, Madhya Pradesh, Maharashtra) deduct half-yearly in June & December with due dates around 15
  July/15 January · seen in: ClearTax LWF guide, Zoho Payroll (LWF cycle setup), saral PayPack (compliance
  calendar penalty tracking) · priority: table-stakes · spine: `employee_contribution`, `employer_contribution`,
  `periodicity` choices (`monthly`/`half_yearly`/`annual`) fields on a state-scoped LWF config row · buildable
  now
- **LWF register/report per period** — a filterable report listing per-employee LWF deductions for a given
  half-year/year, used for the actual fund payment · seen in: Zimyo (dedicated filterable "LWF Report") ·
  priority: common · spine: `StatutoryReturn` (scheme=`lwf`, `period_type='half_yearly'` or `'annual'` per
  state) — same shared aggregation table as PF/ESI/TDS · buildable now
- **LWF employer registration number** (where required by the state) · seen in: RazorpayX (state-driven LWF
  registrations) · priority: common · spine: field on the state-scoped config · buildable now

### Cross-cutting — Statutory report registers, compliance calendar/due-date tracking (spans all five bullets)
- **Compliance calendar with per-scheme due dates and penalty awareness** — a single calendar showing every
  upcoming statutory deadline (TDS deposit by the 7th via Challan 281, PF+ECR by the 15th, ESI by the 15th, PT
  by the 15th/20th depending on state, LWF half-yearly by 15 July/15 January in applicable states) · seen in:
  saral PayPack (dedicated compliance-calendar blog/tooling with due-date + penalty tracking), RazorpayX
  ("all compliance payments are made before the 15th... 15th or 20th in case of PT"), Darwinbox (monthly/
  quarterly/half-yearly/annual filing cadences tracked together) · priority: differentiator (as a unified
  calendar UI) but table-stakes as underlying due-date data · spine: `due_date` + `status` fields already
  proposed on `StatutoryReturn` are the buildable core; a true calendar/dashboard VIEW aggregating across
  schemes is a thin read-only report over that same table — **buildable now** (the due-date field + a
  calendar-style list view), no new model needed beyond `StatutoryReturn`
- **Filing/payment status workflow** (`pending` → `filed`/`paid` → optionally `late`) with the actual
  paid-date vs. due-date comparison surfaced · seen in: RazorpayX, saral PayPack, Keka (audit-ready status per
  cycle) · priority: common · spine: `status` choices + `filed_on`/`paid_on` timestamps on `StatutoryReturn` ·
  buildable now
- **Rule/rate update alerts when statutory rates change** (e.g. Odisha discontinuing PT from April 2026) ·
  seen in: greytHR (auto rate handling), Keka ("automatic alerts... every rule change instantly applied") ·
  priority: differentiator · integration/later (this pass supports it structurally via `effective_from`/
  `is_active` on slab/config rows so a rate change is a new row, not an edit — no alerting/notification engine
  built now)
- **Multi-employee-type handling** (full-time/part-time/contract/intern each may have different statutory
  applicability) · seen in: Keka ("supports full-time, part-time, contractual, and freelance employees,
  applying the right compliance rules") · priority: common · spine: **reuse
  `hrm.EmployeeProfile.employee_type`** already present; the aggregation query can filter/segment by it, no
  new field · buildable now

## Recommended build scope (this pass — 4 models)

- **`StatutoryConfig`** [`TenantOwned`, singleton-per-tenant like a settings row — no numeric prefix] —
  the tenant-wide employer registration + default-rate master, justified by: Zoho Payroll's single Statutory
  Components settings screen (PF establishment code / ESI number / PT registration number), RazorpayX's
  registration-management flows, and the TDS-side TAN requirement (ClearTax/greytHR Form 16 config).
  - `pf_establishment_code`, `pf_wage_ceiling` (default 15000.00), `pf_employee_rate` / `pf_employer_rate`
    (default 12.00/12.00) — PF Management.
  - `esi_employer_code`, `esi_wage_ceiling` (default 21000.00), `esi_employee_rate` / `esi_employer_rate`
    (default 0.75/3.25) — ESI Management.
  - `pt_default_state` (used when an employee's own state can't be resolved) — PT Management.
  - `tan_number` (TDS employer TAN), `tds_circle_address`, `pan_of_deductor` — TDS Management (mirrors
    greytHR's Form 16 config fields).
  - `is_lwf_applicable` (org-wide master switch; per-state detail lives on `StatutoryStateRule`) — LWF
    Management.
  - One row per tenant (`OneToOneField`-style enforced via `unique=True` on `tenant`, or simply
    `get_or_create` in views) — a small settings object, not a numbered/listed entity.

- **`StatutoryStateRule`** [`TenantOwned`] — the state-wise PT + LWF slab/rate table, justified by: greytHR's
  editable state-wise PT slab grid (salary-from/salary-till/tax-amount/deduction-month) and the LWF
  state-applicability + periodicity + amount pattern (Zimyo, ClearTax LWF guide, saral PayPack).
  - `state` (CharField, e.g. `"Maharashtra"`, `"Karnataka"` — plain choices list of Indian states/UTs).
  - `scheme` choices `pt` / `lwf` — one shared table for both state-scoped schemes rather than two near
    -identical tables.
  - PT-specific (blank when `scheme='lwf'`): `income_from`, `income_to`, `pt_monthly_amount`,
    `pt_deduction_month` (optional — some states deduct only in specific months, e.g. an annual lump sum in
    February).
  - LWF-specific (blank when `scheme='pt'`): `lwf_employee_contribution`, `lwf_employer_contribution`,
    `lwf_periodicity` choices `monthly`/`half_yearly`/`annual`, `lwf_due_month_1` (e.g. July),
    `lwf_due_month_2` (nullable, e.g. January, for half-yearly states).
  - `registration_number` (the state-specific PT/LWF employer registration, where applicable).
  - `is_active`, `effective_from` — supports the greytHR "Odisha PT discontinued from April 2026" pattern:
    deactivate/supersede rather than delete, preserving history for prior-period reports.
  - `unique_together (tenant, state, scheme, income_from)` guards against duplicate/overlapping slabs for PT;
    for LWF, `income_from` stays null and uniqueness is effectively `(tenant, state, scheme)`.

- **`EmployeeStatutoryIdentifier`** [`TenantOwned`, 1:1 with `hrm.EmployeeProfile`] — the per-employee
  government-issued identifiers that don't fit `EmployeeProfile.national_id`'s generic PAN/Aadhaar semantics,
  justified by: UAN/ESI-number-per-employee being called out across virtually every India payroll product as
  a required master field.
  - `employee` — `OneToOneField("hrm.EmployeeProfile", related_name="statutory_identifiers")`.
  - `uan_number` (PF Universal Account Number).
  - `pf_number` (the establishment-specific PF account/member ID, distinct from the lifelong UAN).
  - `esi_number` (ESI Insurance Number, blank if the employee's gross exceeds the ESI ceiling and they're
    exempt).
  - `pt_state` (the state used to resolve which `StatutoryStateRule` applies to this employee — falls back to
    `StatutoryConfig.pt_default_state` if blank; kept explicit here rather than overloading
    `EmployeeProfile.work_location`, since the latter is free text and PT needs a clean state match).
  - `is_pf_applicable`, `is_esi_applicable` (booleans — an employee above the wage ceiling, or an
    exempted/international worker, can be flagged out without deleting the identifier record) — mirrors the
    "employee exits ESI scheme above ₹21,000 gross" convention (Zoho Payroll).
  - Created lazily (get-or-create) alongside `EmployeeProfile` — not every employee needs every identifier
    filled immediately.

- **`StatutoryReturn`** [`TenantNumbered`, `SCR-#####`] — the shared per-scheme, per-period compliance
  register/challan/return-tracking record, justified by: Keka's monthly PF ECR report, saral PayPack's PF/ESI
  return generation + compliance-calendar due-date/penalty tracking, ClearTax's quarterly Form 24Q + annual
  Form 16, Zimyo's LWF Report, RazorpayX's "statutory reports maintained... accessed at any time."
  - `NUMBER_PREFIX = "SCR"`.
  - `scheme` choices `pf` / `esi` / `pt` / `tds_24q` / `tds_form16` / `lwf` — one table covers every bullet
    (3.15.a–e) instead of five near-duplicate tables.
  - `period_type` choices `monthly` / `quarterly` / `half_yearly` / `annual` — matches Darwinbox's observed
    monthly/quarterly/half-yearly/annual filing cadence split per scheme.
  - `period_start`, `period_end` (the return's covered period — e.g. a calendar month for PF/ESI, a financial
    quarter for Form 24Q, a financial year for Form 16 or an annual-cadence LWF state).
  - `cycle` — `models.ForeignKey("hrm.PayrollCycle", null=True, blank=True, related_name="statutory_returns")`
    for the common case (one PF/ESI/LWF return ties to one monthly `PayrollCycle`); left null for
    multi-cycle rollups (a quarterly Form 24Q spans 3 `PayrollCycle`s, so it aggregates from
    `Payslip`/`PayslipLine` by date range instead of a single FK).
  - `employee` — `models.ForeignKey("hrm.EmployeeProfile", null=True, blank=True, related_name=
    "statutory_returns")` — set only for the per-employee `tds_form16` scheme; null for org-level returns
    (PF/ESI/PT/LWF/24Q are org-level aggregates).
  - `employee_contribution_total`, `employer_contribution_total`, `headcount` — derived/cached aggregates
    rolled up from `PayslipLine` amounts matching the scheme, across the return's period (mirrors
    `PayrollCycle._totals()`'s aggregate-and-cache convention already in the codebase).
  - `due_date` — drives the Compliance Calendar cross-cutting feature (RazorpayX's 15th/20th tracking, saral
    PayPack's 7th/15th tracking).
  - `status` choices `pending` / `filed` / `paid` / `late` — RazorpayX/saral PayPack's filing/payment
    workflow.
  - `filed_on`, `paid_on` (nullable dates), `payment_reference` (CharField, blank) — challan/payment audit
    trail.
  - `registration_number_used` (CharField, blank — a snapshot copy of the relevant `StatutoryConfig`/
    `StatutoryStateRule` registration number at filing time, so a later registration-number change doesn't
    rewrite historical returns — mirrors the `PayslipLine` snapshotting convention already established in
    3.14).
  - `notes` (TextField, blank).
  - `unique_together (tenant, scheme, period_start, employee)` — one return per scheme per period (per
    employee for `tds_form16`, org-wide otherwise).

This 4-model set reuses `hrm.EmployeeProfile`, `hrm.PayrollCycle`, `hrm.Payslip`/`PayslipLine`, and
`hrm.PayComponent` for every actual money computation; it adds no new employee master, no new ledger, and no
duplicate GL-posting path — `accounting.PayrollRun`/`JournalEntry` remain untouched and unreferenced by this
sub-module.

## Deferred (later passes / integrations)
- **ECR file / ESIC challan / EPFO-portal file-format generation** — the exact pipe/CSV government file
  layouts and direct portal upload (Keka, saral PayPack "Saral ePFESI," HROne) — this pass stores the
  aggregated numbers (`StatutoryReturn.employee_contribution_total` etc.) needed to generate them later; the
  file-format writer and portal API integration are out of a single Django pass.
- **TRACES integration / unconsumed-challan matching** (ClearTax) — external government-portal API
  integration, not buildable in this pass.
- **AI/rules-based error detection before filing** (ClearTax's late-deduction/PAN-validation flagging) — a
  validation-rules engine layered on top of `StatutoryReturn`; deferred as a fast-follow, not blocking v1.
- **Form 16 / Form 24Q PDF/XML rendering and email delivery** — presentation/document-generation layer,
  consistent with the payslip-PDF deferral already noted in the 3.14 research; this pass tracks the
  `StatutoryReturn` row's status/aggregates, not the rendered document.
- **Automatic rate-change alerting** (Keka/greytHR's "rule changes applied instantly," e.g. the Odisha PT
  discontinuation) — structurally supported via `StatutoryStateRule.is_active`/`effective_from` (supersede,
  don't edit), but no notification/alert engine is built in this pass.
- **Compliance-calendar dashboard UI** as a distinct product surface — the underlying `due_date`/`status`
  fields on `StatutoryReturn` are buildable now; a cross-scheme calendar/dashboard view is a report built on
  top of the existing table, not a new model, and can be added without further data-model work.
- **Multi-country / non-India statutory schemes** — RazorpayX/Deel/Rippling's global-equivalent tax filing
  (US FICA/state tax, EOR compliance in other countries) — this catalog is India-specific per the brief;
  extending `StatutoryReturn.scheme` choices for other jurisdictions is a future-pass consideration, not
  blocking.
- **Gratuity and Bonus Act statutory compliance** — mentioned in passing by RazorpayX/Zimyo alongside PF/ESI/
  PT/LWF, but out of the five NavERP.md 3.15 bullets (PF/ESI/PT/TDS/LWF only) — not modeled here; would be a
  separate future bullet if NavERP.md is extended.
- **PT/LWF per-employee-type differentiation beyond `employee_type` reuse** — Keka's full-time/part-time/
  contract/intern/freelance-specific statutory rule variations are supported at the query/filter level using
  the existing `EmployeeProfile.employee_type` field; no new per-type override table is added in this pass.

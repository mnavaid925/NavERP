# Research - Module 3: HRM -> Sub-module 3.31 Payroll Reports (hrm)

## Scope note (read this first)

3.31 is a DERIVED reporting layer, same pattern as 3.28 HR Reports / 3.29 Attendance Reports / 3.30 Leave
Reports (`apps/hrm/views.py` lines ~11920-12714, urls at `apps/hrm/urls.py` lines ~947-966). Those three
sub-modules added **zero new models** - every report is a `@tenant_admin_required` view that aggregates
existing tables and renders a `hrm/reports/<name>.html` template, reusing shared helpers
(`_report_period`, `_report_department`, `_dept_choices`, `_report_year`). 3.31 must follow the same
convention: the payroll engine (3.13 Pay Components/Salary Structure, 3.14 Payroll Processing, 3.15
Statutory Compliance, 3.16 Tax & Investment, 3.17 Payout & Reports) already stores every number this
sub-module needs to report on.

Confirmed in `apps/hrm/models.py`:
- `PayComponent` (line 3269) - earning/statutory_deduction/voluntary_deduction/reimbursement/variable
  catalog, `contribution_side` (employee/employer/both).
- `EmployeeSalaryStructure` (3415) - effective-dated CTC assignment (`annual_ctc_amount`), one active row
  per employee.
- `SalaryStructureTemplate` / `SalaryStructureLine` (3342/3374) - the CTC breakdown a structure is built
  from; `resolved_amount(ctc)` derives each component's annual amount.
- `PayrollCycle` (3472) - pay-period run header, `total_gross`/`total_deductions`/`total_net`/`headcount`
  derived from its payslips.
- `Payslip` (3554) - per-employee per-cycle gross/net/deductions/lop/arrears/bonus, POSITIVE magnitudes.
- `PayslipLine` (3676) - snapshotted component rows (earning/deduction/arrears/bonus/lop +
  `contribution_side`) - the line-level detail a Salary Register grid pivots into columns.
- `EmployeeStatutoryIdentifier` (3876) - UAN/PF/ESI numbers, PT state; has `masked_uan_number()` /
  `masked_pf_number()` / `masked_esi_number()` - MUST be used by any statutory report (these are
  redacted from AuditLog too - never render raw numbers in a report).
- `StatutoryReturn` (3925) - one shared table for PF/ESI/PT/TDS-24Q/TDS-Form16/LWF
  (`scheme` choice field), period, `employee_contribution_total`/`employer_contribution_total`/
  `headcount`, `status` (pending/filed/paid/late), `is_overdue`.
- `TaxRegimeConfig` / `TaxSlabBand` (4120/4156) - old/new regime rate master.
- `InvestmentDeclaration` / `InvestmentDeclarationLine` / `InvestmentProof` (4182/4227/4284) - per-FY
  80C-style declarations, draft/submitted/locked, verified vs declared amounts.
- `TaxComputation` (4325) - per-employee-per-FY `tax_payable`/`tax_paid_ytd`/`monthly_tds_amount`, links
  to a `StatutoryReturn(scheme="tds_form16")` row via `link_form16()`.
- `CostCenterProfile` (219) - HRM companion to `core.OrgUnit(kind="cost_center")`: `budget_annual`,
  `budget_year`, `owner`. Distinct from `kind="department"` (the dimension 3.28's `cost_report` already
  uses).
- `core.OrgUnit` (`apps/core/models.py:42`) - has a self-referential `parent`, so department and
  cost-center nodes can nest; `Employment.org_unit` is usually a department, not necessarily the
  cost-center directly.

**Already built - do not re-propose:**
- `payslip_list` / `payslip_detail` (3.14, `apps/hrm/views.py:6196`) - a raw CRUD list/detail of
  `Payslip`, NOT a pivoted earnings/deductions grid across employees for a period. A true Salary Register
  is still missing.
- `cost_report` (3.28, `apps/hrm/views.py:12207`, url `reports/hr/cost/`) - already covers "Salary cost,
  department-wise cost": per-cycle `total_cost`/`avg_cost`/`employer_cost`, `by_department` (via
  `OrgUnit(kind="department")`), `by_component`, and a 12-cycle trend. **3.31's Cost Analysis must not
  duplicate this** - it must add what `cost_report` does NOT do: (a) the *structural* annualized CTC
  breakdown per employee (from `EmployeeSalaryStructure`/`SalaryStructureTemplate`, not actual payslip
  runs), and (b) true **cost-center** (not department) rollup with `CostCenterProfile.budget_annual`
  budget-vs-actual variance.
- `payment_register(pk)` / `payout_exceptions` (3.17, `apps/hrm/views.py:7415`/`7436`) - a per-batch bank
  disbursement/advice register (masked accounts, UTR, status/method breakdown) and a failed-payment
  exception queue. Different data (disbursement, not earnings/deductions) - not a 3.31 duplicate but worth
  cross-linking.
- `form16_partb(pk)` (3.16, `apps/hrm/views.py:7003`) - the single-employee Form 16 Part A+B
  certificate/detail view; its own docstring says **"PDF rendering deferred"**. 3.31's Tax Reports should
  add an *aggregate, across-employees* Form 16 filing-status register that links out to this existing
  detail view - it must not rebuild the certificate itself, and PDF export stays deferred.
- `taxcomputation_link_form16(pk)` (3.16, `apps/hrm/views.py:6993`) - links a `TaxComputation` to its
  `StatutoryReturn(scheme="tds_form16")` row - the join 3.31's Form 16 register reads, not writes.

## Leaders surveyed (with source links)

1. **ADP Workforce Now** - enterprise US payroll/HCM; the "Payroll Register Report" is the reference
   point for a granular per-employee earnings/deductions grid - [Payroll Report | ADP](https://www.adp.com/resources/articles-and-insights/articles/p/payroll-report.aspx), [ADP Workforce Now Payroll](https://www.adp.com/what-we-offer/products/adp-workforce-now/payroll.aspx)
2. **Gusto** - SMB US payroll; Payroll Journal report (earnings/taxes/deductions/net pay, groupable by
   department/project) doubles as the GL/cost-allocation source - [Payroll Journal - Gusto Help Center](https://support.gusto.com/article/101334493100000/view-download-and-customize-reports-in-gusto-for-admins), [Payroll features](https://gusto.com/product/payroll/features)
3. **Zoho Payroll (India)** - direct India-statutory analog to this codebase: Payroll Summary, Monthly
   Salary Register, Employee Salary Statement, Payroll Liability Summary, Leave Encashment Summary, LOP
   Summary, EPF/ESI/PT/LWF statutory registers, Form 16 Part A+B - [Payroll compliance | Zoho Payroll](https://www.zoho.com/in/payroll/payroll-compliance/), [Form 16 in Zoho Payroll](https://www.zoho.com/in/payroll/help/employer/taxes-and-forms/form-16.html)
4. **greytHR** - India payroll/compliance leader: PF (with ECR generation), ESI, PT (state-slab aware),
   LWF, TDS/Form 24Q one-click generation, digitally signed Form 16 - [greytHR Payroll Software](https://www.greythr.com/payroll-software/), [greytHR statutory filing help](https://admin-help.greythr.com/admin/answers/143353629/)
5. **Keka HR** - India payroll: Pay/Payroll Register filterable by Business Unit / **Cost Center** /
   Location / Department / Worker Type / Status; a dedicated "Current CTC Report"; monthly and annual cost
   breakdowns - [Using Payroll Reports on Keka](https://help.keka.com/admin/using-payroll-reports-on-keka), [Pay register help](https://help.keka.com/admin/admin-help/how-to-check-the-pay-register), [CTC report](https://help.keka.com/hc/en-us/articles/39946570565649-How-to-pull-out-a-report-of-employees-annual-CTCs)
6. **RazorpayX Payroll** - India payroll: a "Salary Register" report with a **PT-location filter** to
   list who owes PT and by how much; downloadable PF/ESI/PT compliance/challan documents from the same
   Reports screen - [Statutory compliance | RazorpayX Payroll](https://razorpay.com/payroll/payroll-compliance/), [Payroll processing](https://razorpay.com/payroll/payroll-processing/)
7. **Rippling** - US payroll/HR platform: hundreds of prebuilt reports, planned-vs-actual headcount/labor
   cost reports, automated GL journal sync with department/location codes carried through for cost
   allocation - [HR metrics & reporting](https://www.rippling.com/hr-metrics-reporting), [Total payroll cost per employee report](https://www.rippling.com/recipes/total-payroll-costs-per-employee-report-template)
8. **Paycom** - US payroll: "GL Concierge" maps payroll to GL codes automatically; "Labor Allocation"
   reports cost by role/GL/cost-center code for budgeting and planning - [GL Concierge](https://www.paycom.com/software/gl-concierge/), [Labor Allocation](https://www.paycom.com/software/labor-allocation/)
9. **UKG Pro (UltiPro)** - enterprise HCM: "Summary Payroll Register" (totals for selected pay
   period(s): earnings, employee/employer deductions, taxes) and a Payroll Edit Detail Listing for
   period-over-period change verification - [UKG Pro reports](https://www.ukg.com/working-smarter-cafe/introducing-ukg-pro-report-rundown), [UKG Pro payroll](https://www.ukg.com/products/features/payroll)
10. **Workday Payroll** - enterprise: prebuilt Pay Balance Summary / Payroll Register / pay-calculation
    reports, real-time drill-down analytics, and dedicated payroll-reconciliation tooling comparing
    internal vs. vendor/bank data - [Payroll Reporting and Analytics](https://www.workday.com/en-us/products/payroll/reporting-and-analytics.html)
11. **Deel** (global/EOR payroll, extra reference) - a consolidated "G2N" (gross-to-net) report across
    countries/entities, headcount starters/leavers, year-end variance and year-to-date reports - [Global payroll reporting](https://www.deel.com/blog/global-payroll-reporting-for-enterprise/)

## Feature catalog by sub-module

### 3.31.a Salary Register
- **Payroll/Pay Register (per-period earnings/deductions/net grid)** - one row per employee for a chosen
  pay period, columns pivoted from earning/deduction components, gross/net/deduction totals + a totals
  footer row - seen in: ADP (Payroll Register Report), UKG Pro (Summary Payroll Register), Keka (Pay
  Register), Zoho Payroll (Monthly Salary Register), RazorpayX (Salary Register), Workday (Payroll
  Register) - priority: **table-stakes** - spine: reuse `hrm.PayrollCycle` + `hrm.Payslip` +
  `hrm.PayslipLine` (no new table) - buildable now.
- **Filter by Business Unit / Cost Center / Location / Department / Worker Type** - narrows the register
  before export - seen in: Keka, RazorpayX (PT-location filter) - priority: common - spine: reuse
  `core.OrgUnit` via `EmployeeProfile -> Employment.org_unit` (mirrors `_report_department` from 3.28-3.30)
  - buildable now.
- **Employee Salary Statement / Pay Summary (single-employee, multi-period)** - one employee's payslip
  history side-by-side - seen in: Zoho Payroll (Employee Salary Statement / Pay Summary) - priority:
  common - spine: reuse `hrm.Payslip` filtered by employee across cycles - buildable now (fold into the
  register as an employee filter rather than a separate page).
- **Arrears report** - arrears paid this period/FY, employee + amount - seen in: Keka (arrears reports)
  - priority: common - spine: reuse `hrm.Payslip.arrears_amount` / `PayslipLine(component_type="arrears")`
  - buildable now (fold into the register: a non-zero-arrears filter/column, not a separate page).
- **Bonus register** - bonus paid this period, by employee - seen in: Keka (earned bonus report), ADP
  (earnings breakdown) - priority: common - spine: reuse `hrm.Payslip.bonus_amount` /
  `PayslipLine(component_type="bonus")` - buildable now (same as arrears: a column/filter, not a
  separate page).
- **Loss-of-Pay (LOP) / unpaid-leave summary** - days and amount deducted for LOP - seen in: Zoho Payroll
  (LOP Summary) - priority: common - spine: reuse `hrm.Payslip.lop_days`/`lop_amount` - buildable now
  (column on the register).
- **Payroll journal / GL-mapped export** - the register grouped/mapped to GL accounts for import into
  accounting - seen in: Gusto (Payroll Journal), Paycom (GL Concierge), Rippling (automated GL journal
  sync) - priority: differentiator - spine: **out of HRM** - `accounting.PayrollRun`/`JournalEntry` is
  the GL system of record (per the existing "HRM never builds a JournalEntry" convention baked into
  `PayrollCycle.accounting_payroll_run`) - integration/later (belongs to the Accounting module, not this
  pass).
- **Bank disbursement / payment advice register** - separate from the earnings register; already exists
  as `payment_register` (3.17) - not re-proposed here.

### 3.31.b Tax Reports
- **TDS/income-tax summary across employees** (payable, paid-to-date, monthly TDS, regime split) - seen
  in: greytHR (TDS/IT calculations), RazorpayX (TDS by regime), Zoho Payroll (TDS auto-computed per
  Section 192) - priority: **table-stakes** - spine: reuse `hrm.TaxComputation`
  (`tax_payable`/`tax_paid_ytd`/`monthly_tds_amount`) joined to `hrm.InvestmentDeclaration.regime_elected`
  - buildable now.
- **Investment declaration status / compliance-gap tracking** (draft vs submitted vs locked; employees
  with NO declaration filed) - seen in: greytHR, Zoho Payroll, RazorpayX (all track IT-declaration
  submission state as a compliance checklist) - priority: common - spine: reuse
  `hrm.InvestmentDeclaration.status` + a `EmployeeProfile` outer count for "missing" - buildable now.
- **Section-wise (80C/HRA/24b/etc.) declared vs verified totals** - aggregate proof-verification progress
  - seen in: greytHR, Zoho Payroll (proof collection windows) - priority: common - spine: reuse
  `hrm.InvestmentDeclarationLine.declared_amount`/`verified_amount`/`effective_amount` - buildable now
  (optional secondary table on the same page).
- **Form 16 / year-end tax certificate register** (filing status per employee per FY: pending/filed/paid,
  link to the certificate) - seen in: greytHR (digitally signed Form 16), Zoho Payroll (Form 16 Part A+B
  generation and email), Deel (year-end tax documents) - priority: **table-stakes** - spine: reuse
  `hrm.StatutoryReturn(scheme="tds_form16")` (status/headcount/due_date already on the model) linked to
  `hrm.TaxComputation` via the existing `link_form16()`/`form16_partb` view - buildable now as an
  aggregate list; the certificate/PDF itself is already flagged deferred in the existing code
  (`form16_partb` docstring: "PDF rendering deferred").
- **TDS quarterly return (Form 24Q) generation/validation** - seen in: greytHR ("one-click Form 24Q
  generation with automatic FVU validation") - priority: differentiator - spine: reuse
  `hrm.StatutoryReturn(scheme="tds_24q")` for the register row; the actual e-filing/FVU/XML generation is
  integration/later (statutory e-filing format, not a Django CRUD concern).
- **Auto-filed/auto-paid TDS with government portals** - seen in: RazorpayX, Zoho Payroll (direct
  challan/return filing) - priority: differentiator - integration/later (government e-filing API).

### 3.31.c Statutory Reports
- **PF (Provident Fund) contribution register / ECR-style report** (employee + employer contribution
  totals, UAN, headcount, period) - seen in: greytHR (PF with ECR generation), Zoho Payroll (EPF
  Summary), RazorpayX (PF compliance documents), Keka - priority: **table-stakes** - spine: reuse
  `hrm.StatutoryReturn(scheme="pf")` + masked `hrm.EmployeeStatutoryIdentifier.masked_uan_number()`/
  `masked_pf_number()` - buildable now.
- **ESI contribution register** - seen in: greytHR (ESI computations and challans), Zoho Payroll (ESI
  register) - priority: **table-stakes** - spine: reuse `hrm.StatutoryReturn(scheme="esi")` + masked
  `EmployeeStatutoryIdentifier.masked_esi_number()` - buildable now.
- **Professional Tax (PT) register, filterable by state/location** - seen in: greytHR (state-specific PT
  slabs), RazorpayX (Salary Register PT-location filter), Zoho Payroll (Professional Tax report) -
  priority: **table-stakes** - spine: reuse `hrm.StatutoryReturn(scheme="pt")` +
  `EmployeeStatutoryIdentifier.pt_state` - buildable now.
- **Labour Welfare Fund (LWF) register** - seen in: greytHR, Zoho Payroll (LWF register) - priority:
  common - spine: reuse `hrm.StatutoryReturn(scheme="lwf")` - buildable now (same view, `scheme` filter).
- **Filing/due-date tracker with overdue flag** - which returns are pending past due date - seen in:
  greytHR, RazorpayX (compliance dashboards/due reminders) - priority: common - spine: reuse
  `hrm.StatutoryReturn.due_date`/`is_overdue`/`status` (already derived properties on the model) -
  buildable now.
- **ECR/challan file generation (government upload format)** - seen in: greytHR (ECR generation), Zoho
  Payroll/RazorpayX (challan documents, direct payment) - priority: differentiator - integration/later
  (statutory file-format generation + government portal upload, not this pass).
- **State-wise PT slab configuration UI** - already exists as `StatutoryStateRule` (3.15) - not
  re-proposed; the report just reads `StatutoryReturn.registration_number_used` which is already
  snapshotted from it.

### 3.31.d Cost Analysis
- **CTC breakdown (per employee / per grade)** - annualized structural composition of an employee's cost
  (basic, HRA, allowances, employer PF/ESI, gratuity, bonus, etc.) - seen in: Keka ("Current CTC Report",
  Salary Structure Report), Zoho Payroll (Employee Salary Statement), CTC as a concept is India-market
  standard across all India players surveyed - priority: **table-stakes** (for India-model payroll) -
  spine: reuse `hrm.EmployeeSalaryStructure.annual_ctc_amount` +
  `hrm.SalaryStructureTemplate`/`SalaryStructureLine.resolved_amount()` + `hrm.PayComponent` for
  component grouping - buildable now.
- **Department/cost-center-wise payroll cost** - actual spend grouped by org dimension - seen in: Keka
  (pay register filter by Cost Center/Business Unit/Location), Rippling (labor cost by
  department/location via GL sync), Paycom (Labor Allocation by GL/cost-center code) - priority: **table
  -stakes** - spine: **department-wise already exists** (3.28 `cost_report`); **cost-center-wise is new**
  - reuse `hrm.CostCenterProfile` + `core.OrgUnit(kind="cost_center")` + `hrm.Payslip`/`PayslipLine` -
  buildable now.
- **Budget vs. actual variance by cost center** - seen in: Rippling ("planned vs. actual headcount, labor
  costs and progress towards business goals") - priority: common - spine: reuse
  `hrm.CostCenterProfile.budget_annual`/`budget_year` vs. aggregated actual `Payslip.gross_pay` +
  employer-side `PayslipLine` for the matching cycles in that budget year - buildable now.
- **Period-over-period payroll cost trend** - seen in: UKG Pro (payroll comparison reports), ADP
  (ongoing payroll totals) - priority: common - spine: **already exists** on 3.28 `cost_report`
  (`trend_labels`/`trend_values` over the last 12 cycles) - not re-proposed; the new cost-center report
  can reuse the same trend pattern if useful, scoped to a cost center.
- **Headcount cost / average cost-per-employee** - seen in: Rippling (headcount + labor cost together),
  Keka (annual cost breakdown) - priority: common - spine: **already exists** on 3.28 `cost_report`
  (`headcount`/`avg_cost`) - the new cost-center report should compute the cost-center-scoped equivalent,
  not duplicate the department one.
- **Full G2N (gross-to-net) consolidated report across entities/countries** - seen in: Deel (multi-entity
  consolidated G2N) - priority: differentiator - out of scope: NavERP is single-currency-per-tenant in
  this pass; deferred (multi-entity/multi-currency payroll consolidation is a later, bigger feature).
- **Job/project costing (labor cost by project)** - seen in: Rippling (job profitability reporting via
  GL sync) - priority: differentiator - integration/later (needs `accounting`/project-costing tie-in, not
  this pass).

## Recommended 3.31 build scope (this pass - 6 views, ZERO new models)

All views: `@tenant_admin_required`, `request.tenant`-scoped, in `apps/hrm/views.py` near the existing
3.28-3.30 report block; templates at `templates/hrm/reports/<name>.html`; reuse the existing helpers
`_report_department`/`_dept_choices`/`_report_period`/`_report_year` where applicable. URLs under
`hrm:reports/payroll/...` mirroring `reports/hr/`, `reports/attendance/`, `reports/leave/`.

1. **`payroll_reports_index`** - tiles/landing page (mirrors `hr_reports_index`/`attendance_reports_index`
   /`leave_reports_index`). Tiles: latest cycle headcount/gross/net, pending Form 16 count, overdue
   statutory returns count, links into the 5 reports below.
   - Source models: `PayrollCycle` (latest), `StatutoryReturn` (overdue count).

2. **`salary_register_report`** - Salary Register bullet. Per-cycle earnings/deductions/net grid, one row
   per employee, columns pivoted from `PayslipLine` (grouped by `component_type`, or top-N named
   components), arrears/bonus/LOP columns, totals footer.
   - Source models: `PayrollCycle` (cycle selector, mirrors `cost_report`'s cycle dropdown), `Payslip`
     (gross/deductions/net/days/lop/arrears/bonus), `PayslipLine` (component pivot), `EmployeeProfile`.
   - Filters: cycle (required, defaults to latest), department (`_report_department`), on_hold toggle.

3. **`tax_report`** - Tax Reports bullet, one page with three aggregate sections: (a) TDS summary
   (payable/paid-YTD/monthly TDS per employee, old-vs-new regime split), (b) investment declaration
   status funnel (draft/submitted/locked + "not filed" count), (c) Form 16 filing-status register
   (pending/filed/paid per employee, each row links to the existing `form16_partb` detail).
   - Source models: `TaxComputation`, `InvestmentDeclaration`, `InvestmentDeclarationLine` (optional
     section-wise total), `StatutoryReturn(scheme="tds_form16")`, `EmployeeProfile`.
   - Filters: financial_year (text/select of years seen on `InvestmentDeclaration`), department, regime.

4. **`statutory_report`** - Statutory Reports bullet. One scheme-filtered register (dropdown mirrors
   `PayrollCycle`'s cycle-dropdown pattern) covering PF/ESI/PT/LWF: contribution totals (employee vs
   employer), headcount, due date + overdue flag, status, and a masked-identifier drill-down per employee.
   - Source models: `StatutoryReturn` (`scheme` as the primary filter, `is_overdue`/`status`/
     `employee_contribution_total`/`employer_contribution_total`), `EmployeeStatutoryIdentifier` (MUST use
     `masked_uan_number()`/`masked_pf_number()`/`masked_esi_number()` - never render raw values).
   - Filters: scheme (pf/esi/pt/lwf), period/financial-year, status.

5. **`ctc_report`** - Cost Analysis bullet, part 1 (CTC breakdown). Per-employee (optionally per job
   grade) annualized CTC composition: total annual CTC, monthly equivalent, and a component breakdown
   (earning/statutory/reimbursement/variable %) resolved from the employee's active salary structure -
   the STRUCTURAL number, distinct from 3.28's actual-payslip `cost_report`.
   - Source models: `EmployeeSalaryStructure` (active, `annual_ctc_amount`), `SalaryStructureTemplate` +
     `SalaryStructureLine.resolved_amount(ctc)`, `PayComponent` (component_type grouping), `EmployeeProfile`.
   - Filters: department, job_grade (via `SalaryStructureTemplate.job_grade`).

6. **`cost_center_report`** - Cost Analysis bullet, part 2 (cost center reports). Payroll cost rolled up
   by `core.OrgUnit(kind="cost_center")` via `CostCenterProfile`, with budget-vs-actual variance
   (`CostCenterProfile.budget_annual`/`budget_year` vs. aggregated actual cost for cycles in that year) -
   the dimension 3.28's `cost_report` never covers (department only).
   - Source models: `CostCenterProfile` (budget_annual, budget_year, owner), `core.OrgUnit` (kind=
     "cost_center"), `Payslip` (gross_pay by `employee__employment__org_unit`), `PayslipLine`
     (contribution_side="employer" for full employer cost).
   - Filters: cost_center, budget_year/cycle.
   - Known v1 simplification (state explicitly in code comments): matches employees whose
     `Employment.org_unit` IS the cost-center node directly; multi-level roll-up of department children
     under a parent cost center is a deferred fast-follow (mirrors the `StatutoryReturn` v1
     keyword-matching simplification already accepted in 3.15).

## Deferred (later passes / integrations)

- **Payroll journal / GL-mapped export** (Gusto Payroll Journal, Paycom GL Concierge, Rippling GL sync) -
  belongs to `accounting.PayrollRun`/`JournalEntry` per the existing "HRM never posts a JournalEntry"
  convention (`PayrollCycle.accounting_payroll_run`) - not an HRM report.
- **Form 16 PDF/certificate generation** - already flagged deferred in the existing `form16_partb`
  docstring ("PDF rendering deferred"); 3.31 only adds the aggregate filing-status register, not the PDF.
- **TDS Form 24Q e-filing / FVU validation, PF ECR file generation, ESI/PT challan file generation** -
  statutory e-filing/government-portal integrations (greytHR, RazorpayX, Zoho Payroll all do this via
  direct portal/bank integration) - out of a single Django pass; the models already store enough
  (`StatutoryReturn.registration_number_used`, `payment_reference`) to add the export later.
- **Auto-pay/auto-file to government portals** (RazorpayX, Zoho Payroll) - external
  integration/compliance-vendor API - later.
- **Multi-entity/multi-country consolidated G2N report** (Deel) - NavERP payroll is single-tenant/
  single-currency in this pass - deferred.
- **Job/project-based labor costing** (Rippling job profitability via GL) - needs project-costing tie-in
  from a later Accounting/Projects pass - deferred.
- **Custom/drag-drop report builder, prebuilt-report library at scale** (Workday 5,000+ reports, UKG
  Report Builder, Rippling custom report builder) - this is NavERP's 3.32 Analytics Dashboard territory
  (Custom Dashboards bullet), not 3.31 - explicitly out of this pass.
- **Payroll reconciliation vs. bank/vendor data** (Workday Global Payroll Reconciliation) - NavERP has no
  external payroll vendor/bank feed to reconcile against yet (3.17's `PayoutPayment`/bank statement side
  is the closest primitive) - deferred until a bank-feed integration exists.
- **Multi-level cost-center roll-up** (department children rolling up to a parent cost center via
  `OrgUnit.parent`) - v1 `cost_center_report` matches direct cost-center assignment only; documented as a
  known simplification above, not silently dropped.

# Research — Module 3: HRM — Sub-module 3.16 Tax & Investment (tax-investment)

## Scope note — the India income-tax declaration + computation layer on top of payroll, reusing 3.13/3.14/3.15
This research covers NavERP.md **3.16 Tax & Investment**: Tax Regime (old vs new comparison), Investment
Declaration (80C/80D/HRA/24b/NPS/other Chapter VI-A), Investment Proof (upload + verification), Tax
Computation (annual projection + monthly TDS spread), and Form 16 Generation. It builds strictly ON TOP of
what already exists and must NOT be re-modeled:

- **`hrm.EmployeeProfile`** — `national_id`/`national_id_type` already holds PAN; employees stay here, no new
  employee master.
- **`hrm.EmployeeSalaryStructure`** (3.13) — `annual_ctc_amount`, resolved `SalaryStructureLine`s — the CTC/
  gross basis `TaxComputation` projects taxable income FROM, not a value it re-derives independently.
- **`hrm.PayrollCycle`/`Payslip`/`PayslipLine`** (3.14) — the ACTUAL TDS already deducted each cycle lives on
  `PayslipLine` (`component_type='statutory_deduction'`); "tax paid to date" is a query over these, not a new
  ledger.
- **`hrm.StatutoryConfig`** (3.15) — already has `tan_number`, `pan_of_deductor`, `tds_circle_address` — the
  Form 16 employer-config fields already exist here; 3.16 does not duplicate them.
- **`hrm.StatutoryReturn`** (3.15) — already has `scheme="tds_form16"` (per-employee, annual) and
  `scheme="tds_24q"` (org-level, quarterly) as the TDS return/Form-16 filing register, with
  `employee_contribution_total`, `due_date`, `status` (`pending`/`filed`/`paid`/`late`), `filed_on`,
  `registration_number_used`. **Form 16 Generation in 3.16 builds ON this row — it does not create a new
  Form-16 table.** 3.16 adds the annual per-employee TAX-COMPUTATION DETAIL (regime elected, declared/
  verified investment breakup, taxable-income workings) that a Form 16 Part B template renders from, linked
  to the existing `StatutoryReturn(scheme="tds_form16")` row for that employee/FY.
- **`core.Document`** — a generic `GenericForeignKey` file-attachment table (`file`, `name`, `classification`,
  `version`) already exists; **Investment Proof reuses it** rather than adding a duplicate generic-attachment
  model (mirrors the `EmployeeDocument` upload-validation pattern for the type-specific metadata, but the
  attachment mechanism itself is `core.Document`).
- Money still posts only through `accounting.PayrollRun`/`JournalEntry` (lesson L29) — **3.16 posts nothing to
  the GL**; it only computes/declares/verifies/reports numbers that 3.14's `Payslip.recompute()` already used
  or that a future TDS-line-item change could consume.

**Regulatory note (verify at build time — this space changes yearly):** searches surfaced the **Income Tax
Act, 2025** taking effect from **1 April 2026**, which renumbers familiar sections (e.g. the new-regime
concessional-rate section, historically "115BAC," and salary-TDS "Section 192," are being renumbered — sources
disagree on the exact new numbers, e.g. "Section 123" vs a different renumbering scheme for what was 80C, and
a new unified declaration form referenced as both "Form 122" and "Form 124" replacing Form 12BB). **Do not
hard-code a single new section-number scheme as gospel** — model section codes as a descriptive
`CharField`/choice list keyed to the FAMILIAR names (80C, 80D, 24b, 80CCD(1B), HRA, standard deduction) with a
`tax_law_reference` free-text note field, so the UI labels can be corrected once the renumbering settles
without a schema change.

## Leaders surveyed (with source links)
1. **Keka** — India HRIS/payroll leader; a dedicated "Managing Income Tax Regime Choices" flow with an
   explicit employee-initiated regime-change action, a "Declaring investments for tax saving" screen
   (Settings → Payroll → My Finance Settings sets the declaration-window last-submission-date; per-section
   declared amount + proof upload), and a manual monthly-vs-annual TDS override for salary/bonus/declaration
   changes mid-year — [Managing Income Tax Regime Choices](https://help.keka.com/hc/en-us/articles/39946625948305-Managing-Income-Tax-Regime-Choices), [How can an employee change the tax regime?](https://help.keka.com/hc/en-us/articles/39946668931729-How-can-an-employee-change-the-tax-regime), [Declaring investments for tax saving](https://help.keka.com/hc/en-us/articles/39946743856657-Declaring-investments-for-tax-saving), [How to override TDS monthly or annually?](https://help.keka.com/hc/en-us/articles/39946625235857-How-to-override-TDS-monthly-or-annually), [Understanding Income Tax](https://www.keka.com/understanding-income-tax), [Form 12BB Guide](https://www.keka.com/compliance/forms/form-12bb)
2. **greytHR** — India HRMS/payroll; an ESS "IT Declaration" page with sections 80C / Other Chapter VI-A /
   HRA / Sec 80D (Medical) / Income-from-house-property / Other income / Previous employment income, a
   dedicated year-end **Proof of Investment (POI)** verification workflow with Pending/Verified/Rejected/On
   Hold statuses and employer-employee messaging on each proof's outcome, and an IT Statement showing Annual
   Tax / Tax Paid Till Date / Balance Payable (the monthly-spread source numbers) — [IT Declaration](https://support.greythr.com/hc/en-us/articles/360041852292-IT-Declaration), [Declare income tax (ESS)](https://ess-help.greythr.com/employee-portal/answers/40960112/), [Investment Proof Verification Guide](https://www.greythr.com/blog/investment-proof-verification-process-employers/), [A Complete Guide to Investment Proof Submission & Verification](https://www.greythr.com/guides/investment-proof-submission/), [Upload, declare and submit POI](https://ess-help.greythr.com/employee-portal/answers/40457150/), [View and download income tax (IT) statement](https://ess-help.greythr.com/employee-portal/answers/40958669/), [View Income Tax slabs](https://admin-help.greythr.com/admin/answers/143810135/), [Which exemptions are unavailable under the new regime?](https://support.greythr.com/hc/en-us/articles/360042214591-Which-are-the-unavailable-exemptions-under-the-new-regime-)
3. **Zoho Payroll** — SMB/India payroll; the clearest "declare → Save and Compare → Tax Comparison page → pick
   old/new regime" UX, an explicit regime-lock rule ("switch before the first payroll run of the FY, else only
   at ITR filing"), a Proof-of-Investment attach-icon flow from the Overall Tax Summary page, and Form 16 Part
   B auto-generated while Part A must be downloaded from TRACES and merged — [Employee Portal - IT Declaration](https://www.zoho.com/in/payroll/help/it-declaration.html), [Proof of Investment](https://www.zoho.com/in/payroll/help/employer/poi.html), [Employer's IT Declaration guide (PDF)](https://www.zoho.com/in/payroll/help/pdf/investment-declaration/employer_investment_declarations_guide.pdf), [Zoho Payroll supports New Tax Regime](https://www.zoho.com/in/payroll/kb/employer/proof-of-investments/payroll-support-new-tax-regime.html), [Free Income Tax Calculator](https://www.zoho.com/in/payroll/income-tax-calculator/)
4. **RazorpayX Payroll** — India payroll; employees "compare and choose their preferred tax regime during tax
   declaration" with a projected-annual-tax preview, an explicit **regime lock after the choice is made**
   (HR-mediated mid-year change only), a January proof-submission window for HRA/80C/home-loan-interest/LTA,
   and Form 16 available only after FY-end + Q4 24Q filing completion (starting June) — [Employees Declare Investments](https://razorpay.com/docs/payroll/employees/declarations/), [Set up an Income Tax declaration window](https://razorpay.com/docs/payroll/tax-deductions-setup/), [Tax Declaration: A Walkthrough](https://razorpay.com/learn/how-to-make-tax-declaration-form12bb/), [Form 16 | Meaning, Eligibility, Benefits](https://razorpay.com/payroll/learn/form-16/), [View payslips and download Form 16](https://razorpay.com/docs/payroll/employees/payslips-form16/)
5. **ClearTax (ClearTDS)** — dedicated TDS/Form-16 specialist; single-click merge of Form 16 Part A + Part B +
   Form 16A into one combined PDF per employee, a bulk Excel-template import path for salary/declaration data,
   bulk PAN validation, and an early-warning system flagging data likely to trigger a TRACES notice before
   filing — [Form-16 Generation by ClearTDS](https://taxcloudindia.com/tds/guides/how-to-generate-form-16-using-cleartds), [Form 16 Download / Meaning / Issuance Guide](https://cleartax.in/s/what-is-form-16), [Income Tax Slabs FY 2025-26](https://cleartax.in/s/income-tax-slabs), [Old vs New Tax Regime FY 2025-26](https://cleartax.in/s/old-tax-regime-vs-new-tax-regime)
6. **Quicko** — India tax-filing specialist (referenced per the brief for the declaration/regime-comparison
   UX); documents the Form 16 Part B change under the new regime (an explicit "opting for Section 115BAC?
   Yes/No" field baked into the certificate) and offers standalone income-tax/TDS calculators as the
   comparison-engine reference point — [Form 16: TDS Certificate](https://learn.quicko.com/form-16-tds-certificate), [Changes in Form 16 as per the New Tax Regime](https://support.quicko.com/hc/en-us/articles/360061055191-Changes-in-Form-16-as-per-the-New-Tax-Regime), [Income Tax/GST/TDS Calculators](https://tools.quicko.com/)
7. **saral PayPack** (Relyon Softech) — India payroll/statutory specialist; the declaration form itself shows
   a live **taxable-income comparison** across regimes at data-entry time, plus a separate detailed "TDS
   Computation in both regimes" worksheet and a dedicated **Tax Regime Summary report** to bulk-compare/select
   per employee, and Form 16 generation keyed off importing the TRACES-downloaded Part A zip — [New Tax Regime in Saral PayPack](https://saralpaypack.com/tutorials/new-tax-regime-in-saral-paypack/), [Form 16 Generation in Saral PayPack](https://saralpaypack.com/tutorials/form-16-generation-in-saral-paypack/), [Importing Employee Declaration](https://saralpaypack.com/tutorials/importing-employee-declaration/)
8. **Darwinbox** — enterprise HCM/payroll (APAC/India); employees fill regime choice + 80C + HRA + home loan
   + other deductions in one consolidated declaration screen (referred to in current sources by the emerging
   "Form 122" unified-declaration terminology replacing Form 12BB) with scanned proof upload, native Form 16/
   Form 24Q generation, and AI-assisted anomaly detection / self-service query on tax declarations and pay
   history ("Darwinbox Sense") — [10 Best Payroll Software for India 2026](https://darwinbox.com/blog/10-best-payroll-software-india), [Form 122: Unified Salary TDS Declaration Guide](https://www.incorpx.io/blog/form-122-unified-tds-declaration-salary-2025)
9. **Zimyo** — India HRMS; an admin-configurable **tax-declaration window** (explicit start/end dates) with
   automatic admin notification when an employee submits a declaration, a toggle to exclude/include projected
   reimbursements from exemption calculations, and payroll-integrated Form 16/24Q generation alongside PF/ESI/
   PT/LWF — [Configuration | Payroll | Zimyo HRMS](https://help.zimyo.com/payroll/configurations/), [Best Payroll Software | Zimyo](https://www.zimyo.com/payroll-software/)
10. **HROne** — India payroll/compliance platform; ties Form 16 download directly to the employee dashboard,
    documents the same old-regime deduction stack (80C/HRA/24b home-loan-interest/80D/80E education-loan) and
    references the emerging "Form 124" successor to Form 12BB (sources differ from Darwinbox's "Form 122" —
    the exact new numbering was still unsettled across products at research time, corroborating the caveat
    above), and partners with ClearTax for downstream ITR filing — [Form 16 — HR Glossary](https://hrone.cloud/hr-glossary/form-16/), [IT Declaration — Importance and Meaning](https://hrone.cloud/hr-glossary/it-declaration/), [Income Tax — File Returns Under 7 Minutes](https://hrone.cloud/blog/file-tax-returns-under-7-minutes-with-hrone/), [Cleartax integration](https://hrone.cloud/integration/cleartax/)

## Feature catalog by sub-module

### 3.16.a Tax Regime — Old vs New regime comparison
- **Per-employee, per-financial-year regime election** (`old` vs `new`), captured as part of the same flow as
  the investment declaration · seen in: every product surveyed · priority: table-stakes · spine: new field
  `regime_elected` on a header model (`TaxComputation` or `InvestmentDeclaration`) · buildable now
- **Side-by-side tax-liability comparison before the employee commits** — declared/projected investments run
  through BOTH regimes' slabs simultaneously so the employee (or HR, doing it on their behalf) can see which
  is cheaper · seen in: Zoho Payroll ("Save and Compare" → Tax Comparison page), saral PayPack (declaration-
  form live comparison + dedicated worksheet + Tax Regime Summary report), RazorpayX ("compare and choose...
  see their projected taxes for the year") · priority: table-stakes · spine: computed properties on
  `TaxComputation` (`tax_under_old_regime`, `tax_under_new_regime`) derived from the same declared-investment
  data run through two slab tables — reuses `TaxSlab`/`TaxRegimeConfig` · buildable now
- **Regime-change lock rules** — regime is freely changeable while the declaration window is open / before
  the FY's first payroll run, then requires HR intervention (or is fixed until ITR filing) · seen in: RazorpayX
  ("cannot change it by yourself in the middle of the year... contact HR"), Zoho Payroll ("switch before your
  employer runs the first payroll... otherwise at ITR filing") · priority: common · spine:
  `InvestmentDeclaration.status` (draft/open) gates whether `regime_elected` is editable — no separate lock
  table · buildable now
- **New regime is the statutory default** (since FY 2023-24 in India, an employee must proactively elect old)
  · seen in: ClearTax slab guide ("new tax regime is the default... as per section 115BAC") · priority:
  table-stakes · spine: `regime_elected` default = `"new"` on the declaration/computation header · buildable
  now
- **Configurable slab tables per regime + financial year** (rates change yearly; FY 2025-26 new-regime slabs:
  nil to ₹4L, 5% ₹4-8L, 10% ₹8-12L, 15% ₹12-16L, 20% ₹16-20L, 25% ₹20-24L, 30% above ₹24L; old-regime slabs
  are the long-standing 3-slab structure) plus regime-specific standard deduction (new ₹75,000 vs old
  ₹50,000) and cess (4% health & education cess on tax, both regimes) · seen in: ClearTax/multiple tax-guide
  sources cross-referenced for current FY 2025-26 rates, greytHR ("View Income Tax slabs" admin screen) ·
  priority: table-stakes · spine: new table `TaxSlab` (tenant-scoped, keyed by financial year + regime),
  `TaxRegimeConfig` (or fields on the same table) for standard deduction + cess rate + rebate threshold ·
  buildable now
- **Section 87A rebate** (effectively zero tax up to ₹12L taxable income under the new regime for FY 2025-26)
  · seen in: ClearTax slab guide · priority: common · spine: `rebate_threshold`/`rebate_amount` fields on the
  regime config, applied in the tax-computation formula · buildable now

### 3.16.b Investment Declaration — 80C, 80D, HRA, home-loan interest (24b), NPS (80CCD), other Chapter VI-A
- **Per-financial-year declaration header** with a declaration WINDOW (open/close dates set by HR) that gates
  whether employees can edit · seen in: Zimyo (admin-configurable start/end dates + notification-on-submit),
  greytHR (window governs new-joinee/mid-year edit eligibility), Keka ("last date for submission" setting) ·
  priority: table-stakes · spine: new table `InvestmentDeclaration` (header, one per employee per FY) ·
  buildable now
- **Section-wise declared amount, one row per deduction type** — 80C (≤₹1.5L: EPF/PPF/life insurance/ELSS/
  tuition fees), 80D (medical insurance self+family, separate slab for senior-citizen parents), HRA exemption
  (rent paid, landlord PAN if annual rent >₹1L, metro/non-metro flag), home-loan interest 24b (≤₹2L self-
  occupied), NPS employee contribution 80CCD(1B) (≤₹50,000 additional), LTA, education-loan interest 80E,
  other Chapter VI-A · seen in: Zoho Payroll (full section breakdown incl. HRA metro/landlord-PAN and home-
  loan lender details), greytHR (80C / Other Ch-VI-A / HRA / 80D / house-property / other income / previous
  employment), the Form 122/124 unified-declaration part-by-part structure (Parts C-H: HRA / LTA / 80C /
  80D / home-loan interest / NPS) · priority: table-stakes · spine: new table `InvestmentDeclarationLine`
  (child of `InvestmentDeclaration`, `section_code` choice + `declared_amount`) · buildable now
- **Statutory per-section caps enforced/surfaced at declaration time** (80C ₹1.5L, 80CCD(1B) NPS ₹50k, 24b
  home-loan ₹2L, standard deduction 50k/75k old/new) · seen in: every product cross-referenced against
  current tax-guide sources (ClearTax, HDFC Life, Bajaj Finserv slab pages) · priority: table-stakes · spine:
  `TaxSlab`/`TaxRegimeConfig`-driven cap constants referenced in `clean()`/computed properties on
  `InvestmentDeclarationLine`/`TaxComputation` (warn/cap, don't silently truncate the user's input) ·
  buildable now
- **HRA-specific sub-fields** (monthly rent, city metro/non-metro classification which changes the exemption
  formula, landlord PAN mandatory above ₹1L annual rent) · seen in: Zoho Payroll (explicit rental period/
  monthly amount/address/metro flag/landlord PAN) · priority: common · spine: extra fields on the HRA
  `InvestmentDeclarationLine` row (or a small metadata JSON/extra-fields set) — kept simple as declared-amount
  + a few descriptive fields, not a full sub-model · buildable now
- **Previous-employer income & TDS already withheld this FY** (for a mid-year joiner) feeds into the annual
  projection so tax isn't double-computed · seen in: greytHR (community thread specifically on "TDS
  Calculation for Previous Employment Case"), Zoho Payroll ("Income from previous employment") · priority:
  common · spine: `previous_employer_income`/`previous_employer_tds` fields on `InvestmentDeclaration` or
  `TaxComputation` · buildable now
- **Deductions unavailable under the new regime are grayed out / not applied** when `regime_elected='new'`
  (80C/80D/HRA/24b/most Chapter VI-A don't reduce new-regime tax; only employer NPS contribution and standard
  deduction survive) · seen in: greytHR ("Which exemptions are unavailable under the new regime?"), ClearTax
  slab guide · priority: table-stakes · spine: the `TaxComputation` calculation engine filters
  `InvestmentDeclarationLine`s by section applicability-per-regime (a static mapping, not a DB flag) when
  computing `tax_under_new_regime` · buildable now
- **Bulk import of employee declarations** (Excel template upload by HR on an employee's behalf) · seen in:
  saral PayPack ("Importing Employee Declaration"), Zoho Payroll ("submit IT Declarations on behalf of your
  employees") · priority: common · integration/later (CSV/Excel import tooling; v1 supports manual entry per
  employee, including HR entering on the employee's behalf via the same form)
- **Unified unbundled declaration form replacing the old Form 12BB** (India's Income Tax Act 2025, effective
  1 Apr 2026 — referred to inconsistently across sources as "Form 122" or "Form 124") · seen in: Darwinbox-
  adjacent guide (Form 122), HROne-adjacent guide (Form 124) · priority: differentiator (regulatory, not yet
  settled) · spine: `InvestmentDeclaration`/`InvestmentDeclarationLine` model the DATA (sections + amounts),
  independent of which physical form number eventually standardizes — no schema change needed once it
  settles, only a label update · buildable now (data model) / integration-later (the exact form PDF/e-filing
  format)

### 3.16.c Investment Proof — Document upload, HR/finance verification
- **Proof-of-Investment (POI) window** — a distinct, usually shorter, later-in-year window (Dec-Feb per
  multiple sources) than the initial declaration window, during which employees upload supporting documents
  for what they declared · seen in: greytHR (dedicated POI guide, "usually around December or January"),
  RazorpayX ("submit income tax/investment proofs in January every year"), Keka ("proof submission timelines
  usually January-March... miss them, and your earlier declarations will be ignored") · priority:
  table-stakes · spine: `proof_window_open`/`proof_window_close` dates on `InvestmentDeclaration` (reuse the
  header, don't duplicate a second window concept) · buildable now
- **Per-line document upload** — one or more proof files attached to a specific declared line (e.g. the
  80C line gets a PPF passbook scan + an insurance premium receipt) · seen in: Zoho Payroll ("attach the
  proofs by clicking the Attach icon" from the tax-summary page, per investment), greytHR ("Upload, declare
   and submit POI") · priority: table-stakes · spine: new table `InvestmentProof` (child of
  `InvestmentDeclarationLine`) wrapping a `core.Document` FK (or a `FileField` directly, mirroring
  `EmployeeDocument`'s pattern) so multiple proofs per line are possible · buildable now
- **Verification status workflow** — Pending → Verified/Accepted → Rejected, with an "On Hold" state for
  incomplete/ambiguous submissions, each with an actor + timestamp + optional message back to the employee ·
  seen in: greytHR (explicit Pending/Verified·Accepted/Rejected/On Hold states + "send messages... if accepted,
  rejected or put on hold") · priority: table-stakes · spine: `verification_status` choices +
  `verified_by`/`verified_at`/`rejection_reason` fields on `InvestmentProof` — mirrors `EmployeeDocument`'s
  `verification_status`/`verified_by`/`verified_at` convention exactly · buildable now
- **Declared-vs-verified amount split** — the amount actually used in the FINAL tax computation is the
  verified amount, not the originally declared amount, once the proof window closes · seen in: Keka
  ("uses DECLARED investment amounts... even if not yet approved" provisionally, but final computation uses
  verified), greytHR ("employer is bound to disallow any claims not backed by proper proofs") · priority:
  table-stakes · spine: `declared_amount` (on `InvestmentDeclarationLine`) vs `verified_amount` (derived/
  rolled-up from that line's approved `InvestmentProof` amounts, or a manual HR-entered verified figure if no
  amount-per-proof granularity is needed) — `TaxComputation` uses `verified_amount` for the FINAL projection,
  `declared_amount` for the PROVISIONAL one · buildable now
- **Disallowed/unverified claims increase tax liability, adjusted across remaining pay periods** · seen in:
  greytHR ("potentially increasing tax liability and requiring adjustment across remaining payroll months") ·
  priority: common · spine: this is exactly what `TaxComputation.monthly_tds_remaining` recomputation captures
  when it re-runs after the proof window closes — no separate model, a re-triggered computation · buildable
  now

### 3.16.d Tax Computation — Annual tax projection
- **Provisional vs final computation** — a provisional projection uses DECLARED amounts (available from day
  one of the FY for monthly TDS deduction), a final/re-run computation after the proof window closes uses
  VERIFIED amounts · seen in: Keka (declared-vs-approved distinction explicit in their guide) · priority:
  table-stakes · spine: `TaxComputation.computation_type` choice (`provisional`/`final`) or simply re-running
  the same row's derived fields after proofs settle, timestamped via `updated_at` — **recommendation: one
  `TaxComputation` row per employee per FY that is recomputed in place (mirrors `Payslip.recompute()`'s
  re-derive-in-place convention)**, with the declared/verified split living on the `InvestmentDeclarationLine`
  rows it aggregates from, not duplicated onto the computation header · buildable now
- **Taxable income build-up**: gross annual salary (from `EmployeeSalaryStructure.annual_ctc_amount` /
  YTD-actual from `Payslip`s) minus HRA exemption, minus standard deduction, minus Chapter VI-A deductions
  (capped per section, and only the sections valid for the elected regime) = taxable income → slab tax → less
  87A rebate → plus 4% health & education cess = annual tax payable · seen in: cross-referenced from ClearTax/
  HDFC Life/Bajaj Finserv slab-rate pages + Form 16 Part B's documented breakdown (gross salary → deductions
  under Chapter VI-A → taxable income → tax → TDS) · priority: table-stakes · spine: computed
  properties/methods on `TaxComputation` (`taxable_income`, `tax_old_regime`, `tax_new_regime`,
  `annual_tax_payable`) — a pure calculation over `InvestmentDeclaration`/`EmployeeSalaryStructure`/`TaxSlab`
  data, no new source-of-truth ledger · buildable now
- **Projected annual TDS spread across the remaining pay periods** — `(annual_tax_payable − tax_already_
  deducted_ytd) / remaining_pay_periods_in_fy` gives the monthly TDS to apply going forward; recomputed
  whenever salary, declaration, or verification changes · seen in: greytHR (IT Statement shows Annual Tax /
  Tax Paid Till Date / Balance Payable — precisely this formula's three inputs), Keka ("override TDS monthly
  or annually" when salary/bonus/declaration changes mid-year necessitate a recompute) · priority:
  table-stakes · spine: `TaxComputation.tax_paid_ytd` (aggregated from `PayslipLine` rows tagged as the TDS
  statutory-deduction component for this employee's cycles so far this FY — reuses 3.14/3.15's existing
  aggregation pattern, does not re-store payslip data), `monthly_tds_remaining` (derived property) ·
  buildable now
- **Manual TDS override** (monthly or annual) for edge cases the formula doesn't cleanly cover · seen in:
  Keka (dedicated "override TDS monthly or annually" guide) · priority: differentiator · spine: an optional
  `manual_override_amount` + `override_reason` field on `TaxComputation`, used instead of the derived monthly
  figure when set — buildable now as a simple override field, not a full exception-approval workflow
- **Regime-recommendation nudge** (which regime saves more, surfaced proactively) · seen in: RazorpayX ("see
  their projected taxes for the year... to make an informed decision"), Zoho Payroll (Tax Comparison page) ·
  priority: common · spine: a read-only comparison of `tax_old_regime` vs `tax_new_regime` computed properties
  already on `TaxComputation` — no extra field, just a template/view-level "you'd save ₹X under regime Y"
  · buildable now

### 3.16.e Form 16 Generation — Auto-generate Form 16 (Part A + Part B) and Form 16A
- **Form 16 built on the existing per-employee annual `StatutoryReturn(scheme="tds_form16")` register row**
  — Part A content (TAN, employer name/address, employee PAN, FY, employment period, quarterly TDS-deposited
  summary) is exactly what `StatutoryReturn` + `StatutoryConfig` already store (`tan_number`,
  `pan_of_deductor`, `tds_circle_address`, `employee_contribution_total`, `period_start`/`period_end`) · seen
  in: official Form 16 structure (incometaxindia.gov.in via secondary sources), greytHR/RazorpayX/ClearTax ·
  priority: table-stakes · spine: **reuse `StatutoryReturn`, do not add a new Form-16 header table** —
  `TaxComputation` (3.16) is the missing Part-B DETAIL that `StatutoryReturn(scheme="tds_form16")` links to
  via a new `tax_computation` FK, or simply looked up by `(tenant, employee, financial_year)` · buildable now
- **Part B content = the detailed salary/exemption/deduction breakup** (gross salary, allowances, Chapter
  VI-A deductions claimed with section-wise amounts, taxable income, tax computed, rebate, cess, net tax
  payable, TDS deducted) — this is precisely `TaxComputation`'s derived fields + its
  `InvestmentDeclarationLine` children rendered as a report · seen in: official Form 16 structure, ClearTax
  ("Part B... deductions claimed under sections 80C, 80D etc.") · priority: table-stakes · spine:
  `TaxComputation` + `InvestmentDeclarationLine` supply every Part-B line item — a template/report layer over
  existing data, no new storage · buildable now (data); PDF rendering integration/later
- **"Opting for concessional new-regime tax? Yes/No" flag printed on the certificate** (a specific
  regime-disclosure field the current Form 16 template requires) · seen in: Quicko (documents this exact
  addition to Form 16 Part B under the new regime) · priority: common · spine: reads directly from
  `TaxComputation.regime_elected` — no new field · buildable now
- **Combined single-PDF merge of Part A + Part B + Form 16A** in one action · seen in: ClearTax ("draft,
  merge, and mail Form 16 Part A, Part B, and Form 16A in a single click") · priority: differentiator ·
  integration/later (PDF-merge/rendering, consistent with the payslip-PDF deferral already noted in 3.14/3.15
  research)
- **Part A requires TRACES (government portal) import/download**, since Part A is technically issued by the
  Income Tax Department based on filed TDS returns, not generated wholesale by the payroll product · seen in:
  Zoho Payroll ("Zoho Payroll generates Form 16 Part B, while Part A requires download from TRACES and
  merge"), saral PayPack (Form 16 generation "traces the Part A zip file downloaded from TRACES") · priority:
  table-stakes (as a workflow constraint) · spine: `StatutoryReturn` already has a `status`/`filed_on` workflow
  that can represent "Part A obtained from TRACES, ready to merge" as a status transition — no new field ·
  integration/later (the actual TRACES API/file import)
- **Form 16A (TDS certificate for non-salary payments — vendor/contractor withholding)** distinguished from
  Form 16 (salary) · seen in: ClearTax ("Difference between Form 16 and Form 16A") · priority: common ·
  spine: **out of 3.16's employee-tax scope** — Form 16A is a vendor/non-salary TDS certificate that belongs
  conceptually to Accounts Payable/vendor withholding, not HRM; noted here only because the brief lists it,
  but no model added for it in this pass (see Deferred)
- **Availability gated on FY-end + Q4 return filing completion** (Form 16 can only be issued once the annual
  cycle + the last quarterly `StatutoryReturn(scheme="tds_24q")` are filed, typically starting June) · seen
  in: RazorpayX ("available after the financial year ends and the TDS Q4 filing is completed... starting
  June") · priority: common · spine: a view-level guard checking the related `tds_24q` `StatutoryReturn`
  rows' `status='filed'` before allowing the `tds_form16` row to be marked `filed`/issued — no new field ·
  buildable now

## Recommended build scope (this pass — 4 models)

- **`TaxRegimeConfig`** [`TenantOwned`, small per-tenant-per-FY settings rows — no numeric prefix] — the
  slab + standard-deduction + cess + rebate master per regime per financial year, justified by: every
  product's regime-comparison feature (Zoho "Tax Comparison page", saral PayPack "Tax Regime Summary",
  RazorpayX "projected taxes for the year") needing a rate table to compute against, and greytHR's admin
  "View Income Tax slabs" screen.
  - `financial_year` (CharField, e.g. `"2025-26"` — matches the Indian FY convention already implicit in
    `StatutoryReturn`'s annual period fields).
  - `regime` choices `old` / `new`.
  - `standard_deduction` (default `75000.00` for new / `50000.00` for old, per current FY 2025-26 rates —
    ClearTax/HDFC Life/Bajaj Finserv slab pages).
  - `cess_rate` (default `4.00`, the Health & Education Cess applied on computed tax, both regimes).
  - `rebate_income_threshold` / `rebate_max_tax` (Section 87A — effectively nil tax up to ₹12L taxable income
    under the new regime for FY 2025-26; old-regime rebate threshold differs and is lower).
  - `is_default_regime` (boolean — statutory default is `new` since FY 2023-24; drives
    `InvestmentDeclaration.regime_elected`'s default).
  - `tax_law_reference` (CharField, blank — free-text note for the unsettled Income Tax Act 2025 section
    renumbering, so the UI can display a caveat without a schema change).
  - `unique_together (tenant, financial_year, regime)`.
  - Child table **`TaxSlabBand`** (or inline via a small JSON/ArrayField-free repeating structure — recommend
    a genuine child table for clean querying): `config` FK, `income_from`, `income_to` (nullable = no upper
    bound), `rate_percent`, `sequence` — the actual bracket table (nil-4L/5%-4-8L/... for new regime FY
    2025-26; the 3-slab old-regime structure) that the tax-computation engine walks. *(If the "4-8 models"
    budget is tight, this can be folded as JSON on `TaxRegimeConfig` instead of a 5th table — noted as an
    option, not a hard requirement; the 4-model recommendation below assumes it stays a lightweight child
    table under this same model's "slot," not counted separately since it's a pure detail-line of
    `TaxRegimeConfig`, mirroring how `PayslipLine` is a detail of `Payslip` without inflating the model
    count.)*

- **`InvestmentDeclaration`** [`TenantNumbered`, `ITD-#####`] — the per-employee-per-FY declaration header +
  regime election + both declaration and proof windows, justified by: Zimyo's admin-configurable declaration
  window, Keka's "last date for submission" setting + regime-change flow, RazorpayX's regime-lock-after-
  election rule.
  - `NUMBER_PREFIX = "ITD"`.
  - `employee` FK → `hrm.EmployeeProfile` (reuse — no new employee master).
  - `financial_year` (CharField, matches `TaxRegimeConfig.financial_year`).
  - `regime_elected` choices `old` / `new`, default from `TaxRegimeConfig.is_default_regime` — Tax Regime.
  - `status` choices `draft` / `submitted` / `locked` — governs whether `regime_elected` and declared-amount
    lines are still editable (Zoho/RazorpayX's "lock after first payroll run" pattern collapsed to a simple
    status field rather than a date-driven auto-lock, consistent with `PayrollCycle`'s own
    draft→...→locked state-machine convention already established in 3.14).
  - `declaration_window_open` / `declaration_window_close` (dates, tenant-set) — Investment Declaration.
  - `proof_window_open` / `proof_window_close` (dates, typically later/shorter than the declaration window —
    greytHR/RazorpayX/Keka's Dec-Jan/Jan-Mar POI window) — Investment Proof.
  - `previous_employer_income`, `previous_employer_tds` (decimals, default 0) — mid-year joiner projection
    input (greytHR, Zoho Payroll).
  - `submitted_at`, `notes`.
  - `unique_together (tenant, employee, financial_year)` — one declaration per employee per FY.

- **`InvestmentDeclarationLine`** [`TenantOwned`, child of `InvestmentDeclaration`] — the per-section declared
  vs. verified breakdown, justified by: Zoho Payroll's/greytHR's/the Form 122-124 unified-form's section-by-
  section structure (80C, 80D, HRA, 24b, 80CCD(1B) NPS, LTA, 80E, other), and Keka's declared-amount-used-
  provisionally-until-approved convention.
  - `declaration` FK → `InvestmentDeclaration`.
  - `section_code` choices `80C` / `80D` / `80D_parents` / `hra` / `24b_home_loan_interest` / `80ccd_1b_nps` /
    `lta` / `80e_education_loan` / `other_chapter_via` — Investment Declaration (the section taxonomy
    cross-referenced from Zoho Payroll + greytHR + the Form 122/124 part structure).
  - `declared_amount` (decimal) — the employee's initial claim.
  - `verified_amount` (decimal, nullable, editable=False — set only via the proof-verification action) — the
    FINAL amount used once proofs are checked (Keka/greytHR's declared-vs-approved distinction).
  - HRA-specific optional fields (blank unless `section_code='hra'`): `monthly_rent_amount`, `is_metro_city`
    (boolean), `landlord_pan` (CharField, blank — mandatory in the UI layer when annualized rent > ₹1,00,000,
    per Zoho Payroll) — Investment Declaration / HRA sub-fields.
  - `24b`-specific optional field (blank unless `section_code='24b_home_loan_interest'`): `lender_name`.
  - `notes` (blank).
  - `unique_together (tenant, declaration, section_code)` — one row per section per declaration (multiple
    80C instruments are summed into the one 80C line's `declared_amount`, matching every surveyed product's
    "one number per section" convention rather than a full instrument-level sub-ledger).

- **`InvestmentProof`** [`TenantOwned`, child of `InvestmentDeclarationLine`] — the uploaded evidence +
  verification workflow, justified by: greytHR's Pending/Verified/Rejected/On-Hold POI states with
  employer-employee messaging, Zoho Payroll's per-line "Attach" proof-upload flow.
  - `declaration_line` FK → `InvestmentDeclarationLine`, `related_name="proofs"` (a section can have >1
    proof document, e.g. 80C's PPF passbook + LIC receipt).
  - `file` — `models.FileField(upload_to="hrm/investment_proofs/%Y/%m/")` (mirrors `EmployeeDocument.file`'s
    direct-FileField pattern rather than routing through `core.Document`'s GenericForeignKey, since the
    verification workflow needs the same dedicated status/actor/timestamp fields `EmployeeDocument` already
    established — reuse the PATTERN, not the generic table, for workflow-field consistency).
  - `title` (CharField — e.g. "LIC Premium Receipt", "Rent Agreement").
  - `amount` (decimal, nullable — the specific amount this proof substantiates, so multiple proofs on one
    line can each carry their own amount and the line's `verified_amount` derives as their sum once each is
    individually verified).
  - `verification_status` choices `pending` / `verified` / `rejected` / `on_hold`, default `pending`,
    `editable=False` — Investment Proof (greytHR's 4-state POI workflow, one state richer than
    `EmployeeDocument`'s 3-state pending/verified/rejected, hence a distinct choices list rather than reusing
    `EmployeeDocument.VERIFICATION_STATUS_CHOICES` directly).
  - `verified_by` FK → `settings.AUTH_USER_MODEL`, `verified_at`, `rejection_reason` (blank) — mirrors
    `EmployeeDocument`'s exact verified_by/verified_at/editable=False convention.
  - `notes` (blank).

- **`TaxComputation`** [`TenantNumbered`, `TXC-#####`] — the per-employee-per-FY annual projection + regime
  comparison + monthly-TDS-spread engine, justified by: greytHR's IT Statement (Annual Tax / Tax Paid Till
  Date / Balance Payable), Keka's provisional-vs-approved + manual-override pattern, Zoho/RazorpayX/saral
  PayPack's side-by-side regime comparison, and the Form 16 Part-B data it must supply.
  - `NUMBER_PREFIX = "TXC"`.
  - `employee` FK → `hrm.EmployeeProfile`; `declaration` FK → `InvestmentDeclaration` (one-to-one per FY, the
    source of every deduction line); `financial_year` (denormalized copy for easy filtering/reporting).
  - `computation_type` choices `provisional` / `final` — Tax Computation (Keka's declared-vs-approved
    distinction: `provisional` runs on `declared_amount`s from day one of the FY, `final` re-runs on
    `verified_amount`s once the proof window closes).
  - Derived/computed properties (methods, not stored columns, mirroring `SalaryStructureTemplate.
    computed_ctc_total`'s "never a stored field" convention): `gross_annual_income` (from the employee's
    active `EmployeeSalaryStructure.annual_ctc_amount` plus `declaration.previous_employer_income`),
    `hra_exemption`, `total_chapter_via_deductions` (sum of applicable `InvestmentDeclarationLine` amounts,
    filtered by section-applicability-per-regime), `taxable_income_old_regime`, `taxable_income_new_regime`,
    `tax_old_regime`, `tax_new_regime` (each walking `TaxRegimeConfig`/`TaxSlabBand` for the matching FY +
    regime, applying the 87A rebate and cess) — Tax Regime comparison.
  - `tax_payable` (decimal, `editable=False`, cached/derived — the tax under whichever regime is
    `declaration.regime_elected`) — Tax Computation.
  - `tax_paid_ytd` (decimal, `editable=False`, aggregated from the employee's TDS-tagged `PayslipLine` rows
    across this FY's `PayrollCycle`s — reuses the exact aggregation approach `StatutoryReturn._scheme_lines()`
    already established in 3.15, filtered to this employee + FY instead of org-wide).
  - `remaining_pay_periods` (PositiveSmallIntegerField — months left in the FY from the computation date) and
    `monthly_tds_amount` (decimal, `editable=False`, derived as `(tax_payable − tax_paid_ytd) /
    remaining_pay_periods`) — the projected-annual-tax-spread-across-remaining-periods feature (greytHR's IT
    Statement formula).
  - `manual_override_amount` (decimal, nullable), `override_reason` (blank) — Keka's monthly/annual TDS
    override for edge cases.
  - `statutory_return` — `models.ForeignKey("hrm.StatutoryReturn", on_delete=models.SET_NULL, null=True,
    blank=True, related_name="tax_computations", editable=False)` — links this Part-B detail to the existing
    `StatutoryReturn(scheme="tds_form16")` row for the same employee/FY, set when that row is created/
    generated (Form 16 Generation: `StatutoryReturn` supplies Part A's TAN/deposited-TDS summary, this model
    supplies Part B's salary/exemption/deduction breakup — **no new Form 16 header table**).
  - `computed_at` (datetime, auto-set on recompute), `notes`.
  - `unique_together (tenant, employee, financial_year)` — one computation per employee per FY, recomputed
    in place (mirrors `Payslip.recompute()`), never a growing history table.

This 4-model set (`TaxRegimeConfig` [+its slab-band detail], `InvestmentDeclaration`, `InvestmentDeclarationLine`
[+its `InvestmentProof` child], `TaxComputation`) reuses `hrm.EmployeeProfile`, `hrm.EmployeeSalaryStructure`,
`hrm.PayslipLine` (for TDS-paid-to-date), `hrm.StatutoryConfig` (TAN/PAN-of-deductor/circle-address already
there), and `hrm.StatutoryReturn` (the `tds_form16`/`tds_24q` filing register) for every piece of Form-16 and
compliance-register plumbing. It adds no new employee master, no new ledger, and no GL-posting path —
`accounting.PayrollRun`/`JournalEntry` remain untouched and unreferenced by this sub-module.

## Deferred (later passes / integrations)
- **Form 16/16A/Part-A+B PDF rendering, merge, and email delivery** — presentation/document-generation layer,
  consistent with the payslip-PDF and Form-16-PDF deferrals already noted in the 3.14/3.15 research; this
  pass stores every data point Part A/B need (`StatutoryReturn` + `TaxComputation` +
  `InvestmentDeclarationLine`) but does not render the certificate itself.
- **TRACES portal integration** (downloading the government-issued Part A file/zip and importing it) — Zoho
  Payroll and saral PayPack both explicitly route through TRACES for Part A; this is an external
  government-portal API/file integration, not buildable in a single Django pass.
- **Form 16A (non-salary/vendor TDS certificate)** — belongs conceptually to Accounts Payable/vendor
  withholding, not the employee-tax scope of 3.16; not modeled here.
- **Bulk Excel import of employee declarations** (saral PayPack, Zoho Payroll "submit on behalf of") — v1
  supports manual per-employee entry (including HR entering on an employee's behalf via the same form); a
  bulk import/export pipeline is a fast-follow.
- **AI-assisted anomaly detection on tax declarations** (Darwinbox Sense) and **TRACES-notice early-warning
  system** (ClearTax) — both are rules/ML layers on top of the core computation, deferred as fast-follows,
  not blocking v1.
- **Automatic regime-change lock enforcement tied to "first payroll run of the FY"** — v1 gates editability
  via `InvestmentDeclaration.status` (draft/submitted/locked) rather than an automatic date/event-driven lock
  keyed to `PayrollCycle` creation; a tighter automatic trigger is a fast-follow.
- **Full instrument-level 80C sub-ledger** (e.g. tracking each individual PPF/ELSS/insurance policy
  separately rather than one summed `declared_amount` per section) — every surveyed product collapses to one
  number per section for computation purposes; a richer instrument-level breakdown is deferred unless a
  future audit requirement demands it.
- **Non-India / multi-country tax-regime support** — this catalog is India-specific per the brief and per
  3.15's existing India-only statutory scope; extending regime/slab modeling to other jurisdictions is a
  future-pass consideration.
- **Exact Income Tax Act 2025 section-renumbering adoption** (the "Form 122" vs "Form 124" naming
  inconsistency and renumbered section codes seen across sources) — modeled defensively via descriptive
  `section_code` choices + a free-text `tax_law_reference` note rather than committing to one unsettled
  numbering scheme; revisit once the renumbering is finalized in official guidance.
- **Separate `TaxSlabBand` model formalization** — recommended as a genuine child table of
  `TaxRegimeConfig` for clean bracket-walking logic, but could be simplified to a JSON field on
  `TaxRegimeConfig` if the `todo` agent prefers to stay at a strict 4-model count; flagged as an
  implementation-detail choice, not a scope gap.

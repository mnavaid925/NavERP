# Research — Sub-module 7.15: Financial & Billing Management (Module 7 — Project Management, `projects`)

> **Executive Scope Summary:** Sub-module 7.15 serves as the commercial financial engine and client billing bridge for NavERP's Project Management module. While 7.4 (`Cost & Budget Management`) tracks internal costs, baselines, commitments, and EVM against control accounts, and 7.11 (`Time & Attendance Tracking`) captures work hours, 7.15 governs **revenue recognition (ASC 606 / IFRS 15)**, **rate cards & billing rules**, **automated billing runs from approved time and expenses**, **client invoice generation and delivery**, **A/R aging and collections management**, **project cash flow forecasting**, **real-time budget vs. actual P&L variance**, and **multi-currency / tax jurisdiction handling**. Per core architectural rulings (L29, L36), 7.15 does **not** create a second financial ledger; all billing generation drafts canonical `accounting.Invoice` rows, cash collections reconcile through `accounting.PaymentAllocation`, and foreign exchange/tax rules leverage `accounting.Currency`, `accounting.ExchangeRate`, and `accounting.TaxCode`.

---

## 1. Repo State Checked First

### 1.1 LIVE_LINKS Built So Far in Module 7 (`apps/core/navigation.py`)
Grep check on `apps/core/navigation.py` confirms that sub-modules **7.1 through 7.14 are fully built** and active in the navigation tree:
- `"7.1"`: Project Initiation & Charter (`ProjectRequest` [PRQ-], `Project` [PRJ-], `ProjectStakeholder` [PST-], `ProjectKickoff` [PKO-])
- `"7.2"`: Project Planning & Scheduling (`ProjectTask` [TSK-], `TaskDependency` [DEP-], `ProjectMilestone` [MST-], `ScheduleBaseline` [BSL-])
- `"7.3"`: Resource Management (`ResourceProfile` [RSP-], `ResourceAllocation` [RAL-], `ResourceTimeEntry` [RTE-])
- `"7.4"`: Cost & Budget Management (`CostControlAccount` [CCA-], `ProjectBudgetLine` [PBL-], `BudgetRevision` [BVR-], `ProjectExpense` [PEX-])
- `"7.5"`: Risk & Issue Management (`ProjectRisk` [RSK-], `RiskResponseAction` [RRA-], `ProjectIssue` [ISS-], `IssueEscalation` [ESC-])
- `"7.6"`: Quality Management (`QualityPlan` [QPL-], `QualityReview` [QRV-], `DeliverableInspection` [QCI-], `QualityDefect` [QDF-])
- `"7.7"`: Scope & Requirements Management (`Requirement` [REQ-], `ScopeItem` [SCI-], `ScopeChangeRequest` [SCR-], `ScopeVerification` [SVR-])
- `"7.8"`: Task & Work Management (`TaskBlock` [TBK-], `TaskChecklistItem` [TCL-])
- `"7.9"`: Collaboration & Communication (`Channel` [CHN-], `ChannelMessage` [MSG-], `DocumentShare` [DSH-], `Meeting` [MTG-], `ProjectNotification` [NTF-])
- `"7.10"`: Document & Knowledge Management (`ProjectDocument` [PDM-], `ProjectFolder` [PFD-], `DocumentTemplate` [DTM-], `ProjectDocumentRevision` [PDV-], `KnowledgeEntry` [KNE-])
- `"7.11"`: Time & Attendance Tracking (`TimeActivityCode` [TAC-], `ProjectOvertimeRecord` [POT-], `OvertimeRule` [OTR-], uses `ResourceTimeEntry`)
- `"7.12"`: Portfolio & Program Management (`Portfolio` [PRT-], `Program` [PGM-], `PortfolioInvestment` [PIN-], `ProgramDependency` [PDEP-])
- `"7.13"`: Agile & Scrum Management (`Sprint` [SPT-], `ProjectEpic` [EPC-], `ProjectRelease` [REL-], `SprintImpediment` [IMP-], `SprintRetrospective` [RET-])
- `"7.14"`: Client & External Collaboration (`ClientPortalAccess` [CPA-], `ClientApprovalRequest` [CFB-], `StatementOfWork` [SOW-], `SOWAmendment` [SWA-], `VendorHandoff` [VHD-], `ProjectClientInvoice` [PCI-])

Sub-module **7.15 is the next unbuilt sub-module**.

### 1.2 Existing Sibling Models Available to FK or Lens
- `projects.Project` [PRJ-] (`apps/projects/models/ProjectInitiation/Projects.py`) — The root container for all project operations; has `client` (`core.Party`), `org_unit` (`core.OrgUnit`), `project_manager` (`User`).
- `projects.ProjectMilestone` [MST-] (`apps/projects/models/ProjectPlanningScheduling/ProjectMilestones.py`) — Deliverable milestone records for milestone-based billing and revenue recognition triggers.
- `projects.ProjectTask` [TSK-] (`apps/projects/models/ProjectPlanningScheduling/ProjectTasks.py`) — Work breakdown structure nodes for task-level billing and effort tracking.
- `projects.ResourceTimeEntry` [RTE-] (`apps/projects/models/ResourceManagement/ResourceTimeEntries.py`) — Daily logged hours with `is_billable` flag, `status` (`draft`, `submitted`, `approved`, `rejected`), `entry_date`, `hours`, `task_description`, and `activity_code`. Primary labor actuals source for automated billing runs.
- `projects.TimeActivityCode` [TAC-] (`apps/projects/models/TimeAttendanceTracking/ActivityCodes.py`) — Categorizes time entries (`direct_project`, `client_service`, `internal_overhead`, etc.) with `is_billable_default`.
- `projects.CostControlAccount` [CCA-] (`apps/projects/models/CostManagement/CostControlAccounts.py`) — EVM management point carrying derived properties (`bac`, `ev`, `pv`, `ac`, `committed`, `available`, `cv`, `sv`, `cpi`, `spi`, `eac`, `etc`, `tcpi`, `vac`, `health`).
- `projects.ProjectExpense` [PEX-] (`apps/projects/models/CostManagement/ProjectExpenses.py`) — Direct costs and commitments (`entry_type`: commitment, actual, accrual; `source_kind`: purchase_order, supplier_invoice, contract, timesheet, manual). Primary direct expense source for billable expense markup.
- `projects.ProjectBudgetLine` [PBL-] (`apps/projects/models/CostManagement/ProjectBudgetLines.py`) — Category budget amounts (`labor`, `material`, `equipment`, `subcontract`, `overhead`, `contingency`, `other`).
- `projects.StatementOfWork` [SOW-] (`apps/projects/models/ClientExternalCollaboration/StatementOfWorks.py`) — Contract value, currency, and billing terms (`fixed_fee`, `time_and_materials`, `milestone_based`, `retainer`).
- `projects.ProjectClientInvoice` [PCI-] (`apps/projects/models/ClientExternalCollaboration/ClientInvoices.py`) — Client delivery billing schedule record linking milestones/SOWs to `accounting.Invoice`.

### 1.3 Spine Entities Verified to Exist (Grep Verified)
- `core.Tenant` (`apps/core/models/Tenant.py`) — Multi-tenant isolation anchor.
- `core.Party` (`apps/core/models/Party.py`) — Unified party model representing clients/customers (`PartyRole` `customer`) and vendors.
- `core.OrgUnit` (`apps/core/models/OrgUnit.py`) — Organizational units including cost centers (`kind="cost_center"`).
- `core.AuditLog` (`apps/core/models/AuditLog.py`) — Immutable audit logging (action code ≤ 10 chars).
- `accounting.Invoice` & `accounting.InvoiceLine` (`apps/accounting/models/AccountsReceivable/Invoices.py`) — Canonical customer AR ledger with `recalc_totals()`, `amount_paid()`, `balance_due()`, and status flow (`draft`, `sent`, `partial`, `paid`, `void`).
- `accounting.Payment` (`apps/accounting/models/AccountsPayable/Payments.py`) — Unified inbound/outbound payment record (`confirmed`, `void`).
- `accounting.PaymentAllocation` (`apps/accounting/models/AccountsReceivable/PaymentAllocations.py`) — Cash application join linking `Payment` to `Invoice`.
- `accounting.Currency` (`apps/accounting/models/GeneralLedger/Currencies.py`) — Global currency table (ISO 4217, no tenant column).
- `accounting.ExchangeRate` (`apps/accounting/models/GeneralLedger/ExchangeRates.py`) — Tenant-scoped daily spot rates (`rate`, `rate_date`, `source`).
- `accounting.TaxCode` (`apps/accounting/models/Tax/TaxCodes.py`) — Master tax rates (`sales`, `vat`, `gst`, `use`) with jurisdiction and `payable_account`.
- `accounting.FiscalPeriod` (`apps/accounting/models/GeneralLedger/FiscalPeriods.py`) — Accounting periods with closed/locked states.
- `accounting.GLAccount` (`apps/accounting/models/GeneralLedger/GLAccounts.py`) — Chart of accounts for revenue and receivables posting.
- `accounting.CostAllocation` (`apps/accounting/models/CostManagement/CostAllocations.py`) — Cost center distribution model.

### 1.4 Entities Verified NOT to Exist
- No dedicated rate card master (`RateCard` / `ProjectBillingRule`) exists in `apps/projects/models/` or across the repository. (Note: `PRC` prefix is used by `hrm.Payrollcycle`, so `RTC-` is recommended for Rate Cards).
- No automated batch billing run model (`ProjectBillingRun`) exists.
- No revenue recognition schedule model (`ProjectRevenueSchedule`) exists.
- No project-level payment / collections tracking model (`ProjectPaymentRecord`) exists.

---

## 2. Leaders Surveyed (with Source Links)

1. **NetSuite OpenAir** — The enterprise standard in PSA and project accounting. Differentiates configurable **Billing Rules** (T&M, fixed fee on % complete, milestone, purchase items) from **Revenue Recognition Rules** (ASC 606 / IFRS 15: % complete cost-to-cost, as-billed, straight-line, incurred vs forecast). Features automated charge generation runs, WIP management, and multi-currency revaluation.  
   *Source:* https://www.netsuite.com/portal/products/openair.shtml & https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2071068.html

2. **Certinia PSA (formerly FinancialForce)** — Salesforce-native PSA market leader. Employs **Billing Event Generation** batches that aggregate approved timecards, expense reports, milestones, and adjustments into billing batches. Deeply integrates project delivery with revenue forecasting and automated revenue schedules linked to performance obligations without creating duplicate ledgers.  
   *Source:* https://certinia.com/products/professional-services-automation/ & https://certinia.com/products/revenue-management/

3. **Kantata OX (formerly Mavenlink)** — Mid-market professional services platform known for sophisticated financial management. Provides account and project-specific **Rate Cards** (by role and client), cost % complete revenue recognition, EAC/ETC financial forecasting, and margin tracking.  
   *Source:* https://www.kantata.com/product/financial-management

4. **Deltek Vantagepoint** — Leading project accounting platform for architecture, engineering, and government contractors. Features **Interactive Billing** sessions (review, hold, write-off, transfer labor/expense transactions, retainage handling) and automated periodic **Revenue Generation** (calculating job-to-date earned revenue and GL adjustments for unbilled services).  
   *Source:* https://www.deltek.com/en/products/vantagepoint/project-accounting

5. **BigTime** — Premier PSA software for consultancies and accounting firms. Delivers automated billing runs pulling unbilled time and expenses directly onto invoices, custom rate cards and expense markups, integrated **A/R Aging dashboards** (0-30, 31-60, 61-90, 90+ days), collections workflows, and multi-currency exchange feeds.  
   *Source:* https://www.bigtime.net/features/invoicing-billing/

6. **Scoro** — Work management and PSA platform featuring real-time financial tracking. Strictly isolates invoicing from revenue recognition; features a **WIP (Work in Progress) Report** tracking recognizable income vs unbilled hours, multi-currency base/transaction normalization, and automated payment tracking.  
   *Source:* https://www.scoro.com/features/work-in-progress/

7. **Forecast.app** — AI-native PSA platform featuring dedicated **Project Financials**. Offers percentage-of-completion automated revenue recognition, period locking to preserve audit integrity, and real-time budget vs actual cost/margin variance.  
   *Source:* https://www.forecast.app/platform/financials

8. **Avaza** — Cloud PSA and billing solution. Specializes in multi-currency client billing, automated timesheet-to-invoice generation wizards (grouped by task, person, or date), expense markup rules, and multi-jurisdiction tax rate calculations.  
   *Source:* https://www.avaza.com/project-invoicing-software/

---

## 3. Feature Catalog (This Sub-module Only)

### 3.1 Project Accounting & Cost Centers
*NavERP.md: "Revenue recognition, cost allocation, and profit/loss by project."*

- **ASC 606 / IFRS 15 Revenue Recognition Schedules** — Formal revenue recognition schedules that decouple revenue realization from invoice issuance. Supports four standard recognition methods:
  1. *Percentage of Completion* (Cost-to-cost or hours-expended ratio against total planned baseline).
  2. *Milestone-Based* (recognizes revenue upon formal client sign-off of deliverables).
  3. *As-Billed* (aligns revenue directly with approved customer invoices).
  4. *Straight-Line / Amortized* (distributes fixed contract values evenly across project duration).  
  *Seen in:* NetSuite OpenAir, Deltek Vantagepoint, Certinia, Scoro, Forecast.app.  
  *Priority:* Table-stakes.  
  *Spine mapping:* New model `ProjectRevenueSchedule` [`PRS-`] with FK to `projects.Project`, optional `ProjectMilestone`, `accounting.FiscalPeriod`, and `accounting.GLAccount`.  
  *Buildable now:* Yes (Django/NavERP).

- **Deferred & Unbilled Revenue Balance Tracking** — Tracks the delta between recognized earned revenue and invoiced amounts (Recognized > Invoiced = Unbilled Revenue / WIP; Invoiced > Recognized = Deferred / Unearned Revenue).  
  *Seen in:* NetSuite OpenAir, Deltek Vantagepoint, Certinia.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Derived calculations on `ProjectRevenueSchedule` and the financial P&L view.  
  *Buildable now:* Yes (computed property / view aggregation).

- **Cost Center & Org Unit Allocation** — Maps project revenue and direct expenses to specific organizational units and cost centers (`core.OrgUnit`, kind=`cost_center`) for divisional profit/loss reporting.  
  *Seen in:* Deltek Vantagepoint, NetSuite OpenAir, Certinia.  
  *Priority:* Common.  
  *Spine mapping:* Reuses `core.OrgUnit` on `ProjectRevenueSchedule` and links with `accounting.CostAllocation`.  
  *Buildable now:* Yes.

- **Project Profit & Loss (P&L) Ledger View** — Real-time project P&L dashboard summarizing Total Contract Value, Recognized Revenue, Direct Labor Costs (approved hours × cost rate), Direct Expenses (actual posted `ProjectExpense` rows), Allocated Overhead, Gross Margin ($), and Margin (%).  
  *Seen in:* Kantata OX, Scoro, Deltek Vantagepoint, BigTime.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Computed view (`projects:financial_pnl`) aggregating `ProjectRevenueSchedule`, `ResourceTimeEntry`, `ProjectExpense`, and `accounting.CostAllocation`. No duplicate snapshot table.  
  *Buildable now:* Yes.

- **Financial Period Locking** — Administrative lock on closed fiscal periods to freeze historical revenue schedules and prevent retroactive tampering with audit-sensitive numbers.  
  *Seen in:* Forecast.app, Deltek Vantagepoint, NetSuite OpenAir.  
  *Priority:* Common.  
  *Spine mapping:* Status flag on `ProjectRevenueSchedule` (`status="locked"`) enforced in model `clean()` and view verbs.  
  *Buildable now:* Yes.

---

### 3.2 Invoice Generation & Delivery
*NavERP.md: "Automated billing from timesheets and expenses, PDF generation, and email dispatch."*

- **Role & Project Billing Rate Cards** — Master rate cards defining standard hourly billing rates by role/title, activity code, or named resource, with markup percentages on pass-through project expenses. Supports tiered hierarchy: Global Standard → Client Custom → Project Override.  
  *Seen in:* Kantata OX, BigTime, NetSuite OpenAir, Deltek Vantagepoint.  
  *Priority:* Table-stakes.  
  *Spine mapping:* New model `ProjectRateCard` [`RTC-`] (FK `projects.Project` nullable, FK `core.Party` client nullable, role name, hourly rate, expense markup pct, currency).  
  *Buildable now:* Yes.

- **Automated Billing Runs (Batch Billing Sessions)** — Wizard/batch process that queries unbilled approved time entries (`ResourceTimeEntry`) and unbilled posted expenses (`ProjectExpense`) up to a selected cutoff date, applies applicable rate cards and expense markups, calculates subtotal and taxes, and creates a consolidated billing run.  
  *Seen in:* Certinia (Billing Event Batches), NetSuite OpenAir (Billing Runs), BigTime (Invoicing Runs), Deltek Vantagepoint (Interactive Billing).  
  *Priority:* Table-stakes.  
  *Spine mapping:* New model `ProjectBillingRun` [`PBR-`] with run parameters, labor/expense/fee totals, and links to source items.  
  *Buildable now:* Yes.

- **Multi-Contract Billing Modes** — Supports Time & Materials (T&M), Fixed Fee, Deliverable Milestone, Progress Percentage, and Retainer billing within the same billing run framework.  
  *Seen in:* All 8 leaders.  
  *Priority:* Table-stakes.  
  *Spine mapping:* `billing_type` choices on `ProjectBillingRun`.  
  *Buildable now:* Yes.

- **Canonical Invoice Generation (`accounting.Invoice` Bridge)** — Once a billing run is reviewed and approved, atomic transaction creates standard `accounting.Invoice` and `accounting.InvoiceLine` rows with revenue GL accounts, customer party, payment terms, and calculated tax totals. Stamped with `ProjectBillingRun` reference to eliminate double-billing.  
  *Seen in:* Certinia, NetSuite OpenAir, Deltek Vantagepoint.  
  *Priority:* Table-stakes (Core Architectural Rule L29 / L36).  
  *Spine mapping:* Direct FK to `accounting.Invoice` (`on_delete=models.SET_NULL`).  
  *Buildable now:* Yes.

- **PDF Generation & Client Preview** — Generates branded PDF invoice previews featuring itemized time/expense breakdowns, milestone descriptions, tax registration numbers, payment remittance instructions, and PO/SOW references.  
  *Seen in:* BigTime, Scoro, Avaza, Deltek Vantagepoint.  
  *Priority:* Table-stakes.  
  *Spine mapping:* View action `pbr_preview_pdf` / `pbr_download_pdf` utilizing standard Django template-to-PDF / printable HTML preview.  
  *Buildable now:* Yes.

- **Email Dispatch & Delivery Tracking** — One-click email dispatch sending invoice PDF and delivery notification to the client's billing contact, logging delivery timestamp, recipient email, and dispatch status.  
  *Seen in:* BigTime, Scoro, Avaza, NetSuite OpenAir.  
  *Priority:* Common.  
  *Spine mapping:* Fields on `ProjectBillingRun` (`delivery_channel`, `dispatched_at`, `dispatched_by`, `recipient_email`), logging to `core.AuditLog` and creating `core.Activity` record.  
  *Buildable now:* Yes.

---

### 3.3 Payment Tracking & Reconciliation
*NavERP.md: "A/R aging, collections workflow, and cash flow forecasting."*

- **Project A/R Aging Dashboard** — Real-time aging analysis classifying outstanding project invoices into standard aging buckets: Current, 1–30 Days, 31–60 Days, 61–90 Days, and 90+ Days Past Due. Filterable by client, project manager, and business unit.  
  *Seen in:* BigTime, Deltek Vantagepoint, NetSuite OpenAir, Scoro.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Computed view (`projects:ar_aging`) querying `accounting.Invoice` where `status` in `('sent', 'partial')` for project-linked invoices, calculating `(today - due_date)`. No duplicate table.  
  *Buildable now:* Yes.

- **Collections Workflow & Dunning Management** — Dedicated collection record tracking dunning stages (`friendly_reminder`, `first_notice`, `second_notice`, `final_demand`, `legal`), follow-up action logs, contact history, and dispute status for overdue project invoices.  
  *Seen in:* Deltek Vantagepoint, BigTime, NetSuite OpenAir.  
  *Priority:* Common.  
  *Spine mapping:* New model `ProjectPaymentRecord` [`PPR-`] (or `ProjectCollectionRecord`) linking `projects.Project`, `accounting.Invoice`, dunning level, next follow-up date, and assigned collector.  
  *Buildable now:* Yes.

- **Promise-to-Pay Commitments** — Records formal customer payment commitments (promised payment date, promised amount, notes) to feed into short-term cash flow projections and suspend automatic dunning escalation while active.  
  *Seen in:* Deltek Vantagepoint, BigTime.  
  *Priority:* Differentiator.  
  *Spine mapping:* Fields on `ProjectPaymentRecord` (`promised_payment_date`, `promised_amount`, `stage="promise_to_pay"`).  
  *Buildable now:* Yes.

- **Cash Application & Payment Reconciliation** — Real-time visibility into customer payment receipts applied to project invoices via `accounting.PaymentAllocation`, displaying unallocated balances, payment references, and payment method details.  
  *Seen in:* Scoro, BigTime, Deltek Vantagepoint.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Reads canonical `accounting.PaymentAllocation` and `accounting.Payment`. No second payment table.  
  *Buildable now:* Yes.

- **Project Cash Flow Forecasting** — Forward-looking cash flow forecast board projecting 30/60/90-day cash inflows (scheduled milestone billings, open AR balances, promised payment dates) against expected cash outflows (committed purchase orders, vendor expenses `ProjectExpense`, planned labor costs).  
  *Seen in:* Kantata OX, Deltek Vantagepoint, Scoro.  
  *Priority:* Common.  
  *Spine mapping:* Computed dashboard (`projects:cash_flow_forecast`) aggregating `ProjectRevenueSchedule`, `accounting.Invoice`, `ProjectPaymentRecord`, and `ProjectExpense`.  
  *Buildable now:* Yes.

---

### 3.4 Budget vs. Actual Analysis
*NavERP.md: "Real-time cost variance, earned value metrics, and forecast updates."*

- **Triple-Constraint Financial Variance Board** — Real-time comparison across the three core financial pillars of a project:
  1. *Revenue Variance:* Planned SOW Contract Value vs Recognized Revenue vs Invoiced Amount vs Cash Collected.
  2. *Cost Variance (CV):* Baselined Cost (BAC) vs Committed Costs (`ProjectExpense` commitments) vs Actual Incurred Costs (AC).
  3. *Margin Variance:* Target Gross Margin % vs Actual Incurred Margin % vs Forecasted Margin at Completion.  
  *Seen in:* Kantata OX, Deltek Vantagepoint, Scoro, Forecast.app.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Computed analytics board (`projects:financial_variance`) joining 7.4 EVM data with 7.15 revenue/billing data. No stored snapshot table (L31 / 7.4 ruling).  
  *Buildable now:* Yes.

- **Earned Value Management (EVM) Integration** — Integrates 7.4's control account EVM metrics (`CPI`, `SPI`, `EAC`, `ETC`, `TCPI`, `VAC`) with commercial client financial metrics, allowing project controllers to see how schedule and cost performance impact contract profitability.  
  *Seen in:* Deltek Vantagepoint, NetSuite OpenAir.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Directly consumes derived properties on `projects.CostControlAccount` from 7.4.  
  *Buildable now:* Yes.

- **Work in Progress (WIP) Valuation Report** — Evaluates unbilled professional services: approved labor hours logged but not yet billed, direct out-of-pocket expenses pending client reimbursement, and unearned customer advances.  
  *Seen in:* Scoro (WIP Report), Deltek Vantagepoint, BigTime.  
  *Priority:* Table-stakes.  
  *Spine mapping:* View aggregation over unbilled `ResourceTimeEntry` and `ProjectExpense` rows.  
  *Buildable now:* Yes.

- **Dynamic Estimate at Completion (EAC) Forecast Updates** — Live recalculation of projected final project costs and revenues based on current Cost Performance Index (`CPI = EV / AC`) and remaining unbilled scope.  
  *Seen in:* Kantata OX, Forecast.app, Deltek Vantagepoint.  
  *Priority:* Common.  
  *Spine mapping:* Derived calculations on the financial variance view.  
  *Buildable now:* Yes.

---

### 3.5 Multi-Currency & Tax Handling
*NavERP.md: "Exchange rate management, tax jurisdiction rules, and international billing."*

- **Multi-Currency Project Hierarchy** — Supports three distinct currency layers per project:
  1. *Contract Currency* (currency agreed in SOW / client contract, e.g. EUR).
  2. *Billing / Invoicing Currency* (currency in which client invoices are generated, e.g. USD).
  3. *Functional Base Currency* (the tenant's corporate accounting base currency, e.g. GBP).  
  *Seen in:* NetSuite OpenAir, Scoro, BigTime, Deltek Vantagepoint.  
  *Priority:* Table-stakes.  
  *Spine mapping:* FK to `accounting.Currency` on `ProjectBillingRun` and `ProjectRevenueSchedule`, with exchange rate capture.  
  *Buildable now:* Yes.

- **Exchange Rate Snapshots & Manual Overrides** — Automatically captures daily spot exchange rates from `accounting.ExchangeRate` at the time of billing run creation or revenue recognition, while permitting authorized project managers to input a contractually agreed fixed exchange rate override.  
  *Seen in:* BigTime, Scoro, Avaza, NetSuite OpenAir.  
  *Priority:* Table-stakes.  
  *Spine mapping:* Field `exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)` on `ProjectBillingRun` and `ProjectRevenueSchedule`.  
  *Buildable now:* Yes.

- **Tax Jurisdiction Rules & Auto-Calculation** — Automatically links appropriate tax rules (`accounting.TaxCode`) based on project location, client tax residency, or service type (e.g., standard VAT, GST, state sales tax, or exempt services), calculating line-level and invoice-level tax amounts.  
  *Seen in:* Avaza, Deltek Vantagepoint, NetSuite OpenAir.  
  *Priority:* Table-stakes.  
  *Spine mapping:* FK `tax_code` to `accounting.TaxCode` on `ProjectBillingRun`, storing `tax_rate_pct` and `tax_amount`.  
  *Buildable now:* Yes.

- **International Billing & Reverse Charge Handling** — Flags cross-border B2B invoices eligible for VAT Reverse Charge, export tax exemptions, or withholding tax deductions, displaying required statutory tax disclaimer notes on generated invoices.  
  *Seen in:* Scoro, Avaza, NetSuite OpenAir.  
  *Priority:* Common.  
  *Spine mapping:* Flag `is_tax_exempt` / `tax_exempt_reason` on `ProjectBillingRun`.  
  *Buildable now:* Yes.

---

## 4. Recommended Build Scope (4 Models)

To deliver complete coverage of Sub-module 7.15 while strictly adhering to core architectural boundaries (L28, L29, L31, L36) and keeping the unit of work cohesive, we recommend **4 tenant-scoped models**:

```
apps/projects/models/FinancialBillingManagement/
├── RateCards.py               → ProjectRateCard [RTC-]
├── BillingRuns.py             → ProjectBillingRun [PBR-]
├── RevenueSchedules.py        → ProjectRevenueSchedule [PRS-]
└── PaymentRecords.py          → ProjectPaymentRecord [PPR-]
```

### Model 1: `ProjectRateCard` [`RTC-`]
- **Purpose:** Governs billing rate cards by role, activity, or project, providing the pricing logic that turns time logs and out-of-pocket expenses into client billable charges. Fulfills Ruling 1 from 7.4 ("7.4 stores amounts, never rates... a future rate card may generate an amount").
- **Prefix:** `RTC` (Unique; `PRC` is reserved by `hrm.Payrollcycle`).
- **Fields:**
  - `tenant` (TenantNumbered)
  - `name`: CharField(120) — e.g. "Standard Consulting 2026", "Enterprise Tier".
  - `project`: FK(`projects.Project`, null=True, blank=True, on_delete=SET_NULL, related_name="rate_cards") — Null = tenant-wide default rate card; populated = project-specific override.
  - `client`: FK(`core.Party`, null=True, blank=True, on_delete=SET_NULL, related_name="rate_cards") — Client-specific negotiated rate card.
  - `role_name`: CharField(100) — Role title (e.g. "Lead Architect", "Senior Consultant", "Developer").
  - `activity_code`: CharField(40, blank=True) — Optional match against `TimeActivityCode.code`.
  - `hourly_rate`: DecimalField(10, 2, validators=[MinValueValidator(0)]) — Billing rate per hour.
  - `expense_markup_pct`: DecimalField(5, 2, default=0.00, validators=[MinValueValidator(0)]) — Markup on direct pass-through expenses (e.g. 10.00%).
  - `currency`: FK(`accounting.Currency`, on_delete=PROTECT, related_name="+") — Currency of the rate.
  - `effective_from`: DateField(null=True, blank=True)
  - `effective_to`: DateField(null=True, blank=True)
  - `is_active`: BooleanField(default=True)
  - `notes`: TextField(blank=True)
- **Unique constraint:** `("tenant", "number")`, with index on `("tenant", "project", "is_active")`.

### Model 2: `ProjectBillingRun` [`PBR-`]
- **Purpose:** The automated billing batch session that aggregates approved unbilled timesheets (`ResourceTimeEntry`) and expenses (`ProjectExpense`), computes billing totals with markups and taxes, generates canonical `accounting.Invoice` records, and manages PDF dispatch. Realizes Bullet 2 (Invoice Generation & Delivery) and Bullet 5 (Multi-Currency & Tax).
- **Prefix:** `PBR` (Unique).
- **Fields:**
  - `tenant` (TenantNumbered)
  - `project`: FK(`projects.Project`, on_delete=CASCADE, related_name="billing_runs")
  - `client`: FK(`core.Party`, on_delete=PROTECT, related_name="project_billing_runs")
  - `sow`: FK(`projects.StatementOfWork`, null=True, blank=True, on_delete=SET_NULL, related_name="billing_runs")
  - `milestone`: FK(`projects.ProjectMilestone`, null=True, blank=True, on_delete=SET_NULL, related_name="billing_runs")
  - `billing_type`: CharField(24, choices=[("time_and_materials", "Time & Materials"), ("fixed_fee", "Fixed Fee"), ("milestone", "Milestone-Based"), ("progress_percent", "Progress Percentage"), ("retainer", "Retainer")])
  - `run_date`: DateField(default=timezone.localdate)
  - `cutoff_date`: DateField(help_text="Unbilled hours and expenses up to this date are captured.")
  - `total_time_hours`: DecimalField(8, 2, default=0)
  - `labor_amount`: DecimalField(14, 2, default=0)
  - `expense_amount`: DecimalField(14, 2, default=0)
  - `fee_amount`: DecimalField(14, 2, default=0)
  - `subtotal`: DecimalField(14, 2, default=0)
  - `tax_code`: FK(`accounting.TaxCode`, null=True, blank=True, on_delete=SET_NULL, related_name="+")
  - `tax_rate_pct`: DecimalField(6, 3, default=0)
  - `tax_amount`: DecimalField(14, 2, default=0)
  - `total_amount`: DecimalField(14, 2, default=0)
  - `currency`: FK(`accounting.Currency`, on_delete=PROTECT, related_name="+")
  - `exchange_rate`: DecimalField(18, 8, default=Decimal("1.00000000"), help_text="Spot exchange rate to base currency.")
  - `status`: CharField(15, choices=[("draft", "Draft"), ("approved", "Approved"), ("invoiced", "Invoiced"), ("cancelled", "Cancelled")], default="draft")
  - `accounting_invoice`: FK(`accounting.Invoice`, null=True, blank=True, on_delete=SET_NULL, related_name="project_billing_runs", help_text="Canonical invoice in GL ledger.")
  - `delivery_channel`: CharField(12, choices=[("email", "Email Dispatch"), ("portal", "Client Portal"), ("download", "Manual Download")], default="email")
  - `recipient_email`: CharField(255, blank=True)
  - `dispatched_at`: DateTimeField(null=True, blank=True, editable=False)
  - `dispatched_by`: FK(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, editable=False, related_name="+")
  - `notes`: TextField(blank=True)
- **Verbs:** `pbr_approve`, `pbr_generate_invoice` (atomic creation of `accounting.Invoice` + `InvoiceLine` items), `pbr_dispatch` (records timestamp, triggers email notification, writes `core.AuditLog`).

### Model 3: `ProjectRevenueSchedule` [`PRS-`]
- **Purpose:** Governs formal ASC 606 / IFRS 15 revenue recognition plans, cost center allocations, and unbilled vs deferred revenue balances. Realizes Bullet 1 (Project Accounting & Cost Centers).
- **Prefix:** `PRS` (Unique).
- **Fields:**
  - `tenant` (TenantNumbered)
  - `project`: FK(`projects.Project`, on_delete=CASCADE, related_name="revenue_schedules")
  - `milestone`: FK(`projects.ProjectMilestone`, null=True, blank=True, on_delete=SET_NULL, related_name="revenue_schedules")
  - `recognition_date`: DateField(default=timezone.localdate)
  - `fiscal_period`: FK(`accounting.FiscalPeriod`, null=True, blank=True, on_delete=SET_NULL, related_name="project_revenue_schedules")
  - `method`: CharField(24, choices=[("percent_complete", "Percentage of Completion"), ("milestone", "Milestone-Based"), ("as_billed", "As Billed / Invoiced"), ("straight_line", "Straight-Line Amortization"), ("manual", "Manual Entry")])
  - `contract_amount`: DecimalField(14, 2, default=0, help_text="Total contractual value under recognition.")
  - `completion_percent`: DecimalField(5, 2, default=0, help_text="Progress % driving recognition.")
  - `recognized_amount`: DecimalField(14, 2, default=0, help_text="Revenue earned and recognized in this period.")
  - `deferred_amount`: DecimalField(14, 2, default=0, help_text="Invoiced revenue not yet earned.")
  - `unbilled_amount`: DecimalField(14, 2, default=0, help_text="Earned revenue not yet invoiced.")
  - `cost_center`: FK(`core.OrgUnit`, null=True, blank=True, on_delete=SET_NULL, related_name="project_revenue_schedules", help_text="Target cost center (kind='cost_center').")
  - `gl_account`: FK(`accounting.GLAccount`, null=True, blank=True, on_delete=PROTECT, related_name="project_revenue_schedules", help_text="Revenue GL Account.")
  - `journal_entry`: FK(`accounting.JournalEntry`, null=True, blank=True, on_delete=SET_NULL, editable=False, related_name="project_revenue_schedules")
  - `status`: CharField(12, choices=[("draft", "Draft"), ("approved", "Approved"), ("recognized", "Recognized"), ("locked", "Locked"), ("void", "Void")], default="draft")
  - `recognized_by`: FK(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, editable=False, related_name="+")
  - `recognized_at`: DateTimeField(null=True, blank=True, editable=False)
  - `notes`: TextField(blank=True)
- **Verbs:** `prs_approve`, `prs_recognize` (locks schedule, creates optional `accounting.JournalEntry` for revenue recognition, logs to `core.AuditLog`).

### Model 4: `ProjectPaymentRecord` [`PPR-`]
- **Purpose:** Manages project-level accounts receivable collections workflow, dunning stages, promise-to-pay commitments, and dispute tracking. Realizes Bullet 3 (Payment Tracking & Reconciliation).
- **Prefix:** `PPR` (Unique).
- **Fields:**
  - `tenant` (TenantNumbered)
  - `project`: FK(`projects.Project`, on_delete=CASCADE, related_name="payment_records")
  - `client`: FK(`core.Party`, on_delete=PROTECT, related_name="project_payment_records")
  - `billing_run`: FK(`projects.ProjectBillingRun`, null=True, blank=True, on_delete=SET_NULL, related_name="payment_records")
  - `accounting_invoice`: FK(`accounting.Invoice`, on_delete=CASCADE, related_name="project_collections")
  - `stage`: CharField(20, choices=[("current", "Current"), ("reminder_sent", "Reminder Sent"), ("overdue", "Overdue"), ("promise_to_pay", "Promise to Pay"), ("in_dispute", "In Dispute"), ("settled", "Settled"), ("written_off", "Written Off")], default="current")
  - `dunning_level`: CharField(20, choices=[("friendly_reminder", "Friendly Reminder"), ("first_notice", "First Notice"), ("second_notice", "Second Notice"), ("final_demand", "Final Demand"), ("legal", "Legal Referral")], default="friendly_reminder")
  - `last_contact_date`: DateField(null=True, blank=True)
  - `next_follow_up_date`: DateField(null=True, blank=True)
  - `promised_payment_date`: DateField(null=True, blank=True)
  - `promised_amount`: DecimalField(14, 2, null=True, blank=True)
  - `dispute_reason`: TextField(blank=True)
  - `assigned_collector`: FK(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL, related_name="assigned_project_collections")
  - `status`: CharField(12, choices=[("open", "Open"), ("escalated", "Escalated"), ("resolved", "Resolved"), ("closed", "Closed")], default="open")
  - `notes`: TextField(blank=True)
- **Verbs:** `ppr_log_contact`, `ppr_record_promise`, `ppr_resolve`, `ppr_escalate`.

---

## 5. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

- **Cost Baselines, Budget Revisions, & Contingency Reserves** → **7.4 Cost & Budget Management**. Already built as `BudgetRevision` [BVR-], `CostControlAccount` [CCA-], and `ProjectExpense` [PEX-]. 7.15 reads from them; it does not rewrite or redefine them.
- **Detailed Timesheet Entry, Timers, & Submission Approvals** → **7.11 Time & Attendance Tracking** (and 7.3 Resource Management). 7.15 acts strictly as the billing consumer of approved `ResourceTimeEntry` records.
- **Statement of Work (SOW) Authoring, SOW Amendments, & Client Sign-off** → **7.14 Client & External Collaboration**. `StatementOfWork` [SOW-] and `ClientApprovalRequest` [CFB-] remain in 7.14.
- **Client Portal Self-Service Invoice Downloads** → **7.14 Client & External Collaboration**. Customer-facing views live in 7.14's portal space (`ClientPortalAccess`); 7.15 owns the internal billing operations console.
- **Cross-Project Multi-Portfolio Financial Rollups & Bubble Charts** → **7.12 Portfolio & Program Management**. Portfolio aggregation belongs in 7.12.
- **Custom Report Builder, Pivot Grids, & External Data Connectors** → **7.16 Reporting & Business Intelligence**. 7.15 ships operational dashboards (P&L, A/R Aging, Variance, Cash Flow Forecast); ad-hoc slicing is 7.16's.
- **Automated Workflow Escalation Rules & Email Reminders Engine** → **7.17 Workflow & Automation**. Automated background cron triggers belong in 7.17.
- **Chart of Accounts, Bank Accounts, Journal Entries, & Fiscal Period Closing** → **Module 2 Accounting**. 7.15 integrates via foreign keys; it never creates parallel ledgers.

---

## 6. Deferred (Later Passes / Integrations)

- **Automated Live FX Feed Sync (xe.com / Fixer API)** — Deferred to 7.18 (`Integration & API Hub`). In 7.15, exchange rates are sourced directly from `accounting.ExchangeRate` or entered as manual contract spot rates.
- **Payment Gateway Webhooks (Stripe / PayPal / Adyen)** — Deferred to 7.18. In 7.15, cash reconciliation occurs natively through `accounting.PaymentAllocation` and `accounting.Payment`.
- **Automated Email Transmission via SMTP / SendGrid** — In 7.15, the `pbr_dispatch` verb stamps the dispatch record, logs an immutable `core.AuditLog` entry, and creates a `core.Activity` note; background mail daemon queueing is an environment-level integration.
- **Complex Proportional SSP (Standalone Selling Price) Allocation for Multi-Element Contracts** — Deferred to advanced enterprise accounting enhancements; standard contract-to-milestone/percentage recognition is fully supported in 7.15.
- **Automated AI Credit Scoring & Delinquency Prediction** — Deferred to Module 10 / Module 23 AI modules. Standard dunning and aging rules are used in 7.15.

---

## 7. Rulings & Architectural Boundaries (Summary for Todo Agent)

1. **Accounting Owns the Financial Ledger (L29, L36):**  
   `ProjectBillingRun` is an operational billing session that drafts canonical `accounting.Invoice` and `accounting.InvoiceLine` rows via `transaction.atomic()`. Payment tracking reads `accounting.PaymentAllocation`. Revenue recognition links to `accounting.GLAccount` and optional `accounting.JournalEntry`. There is NO duplicate ledger.
2. **Computed Views Over Stored Derivations:**  
   Project P&L (`financial_pnl`), A/R Aging (`ar_aging`), Budget vs. Actual Variance (`financial_variance`), and Cash Flow Forecasting (`cash_flow_forecast`) are COMPUTED views rendered on read over verified models (`ProjectRevenueSchedule`, `ProjectBillingRun`, `accounting.Invoice`, `accounting.PaymentAllocation`, `ResourceTimeEntry`, `ProjectExpense`). They hold no snapshot tables that can go stale.
3. **Rate Card Hierarchy:**  
   `ProjectRateCard` [`RTC-`] provides the missing link between hours logged in 7.3/7.11 and billing amounts in 7.15, supporting global standard rates, client-negotiated rates, and project-level overrides with markup on pass-through expenses.
4. **Verbs Drive State Transitions:**  
   State transitions (`pbr_approve`, `pbr_generate_invoice`, `pbr_dispatch`, `prs_approve`, `prs_recognize`, `ppr_log_contact`, `ppr_record_promise`, `ppr_resolve`) are POST-only actions recording audit evidence in `core.AuditLog` (action string <= 10 chars).
5. **Theme.css Badges (L33):**  
   Status badges must strictly use NavERP palette classes: `.badge-green` (approved, invoiced, recognized, settled), `.badge-amber` (in_review, overdue, reminder_sent), `.badge-red` (cancelled, void, in_dispute, written_off), `.badge-info` (draft, open, promise_to_pay), and `.badge-slate` (locked, closed).

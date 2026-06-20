# Research — Module 2 (Advanced): Accounting & Finance — Sub-modules 2.6–2.15
## Scope

This research covers the **second pass** of Module 2. The first pass (2.1–2.5) is already built and owned
by `apps/accounting`. The as-built spine consists of:

- `GLAccount` / `JournalEntry` / `JournalLine` — double-entry ledger (append-only, posted = immutable)
- `FiscalPeriod` — open/closed period gate
- `Currency` / `ExchangeRate` — multi-currency
- `Invoice` / `InvoiceLine` / `Bill` / `BillLine` / `PaymentTerm` — AR and AP documents
- `Payment` / `PaymentAllocation` — cash application
- `BankAccount` / `BankTransaction` / `ReconciliationMatch` — bank reconciliation
- Reused from `core`: `Party`/`PartyRole`, `OrgUnit`, `Document`, `AuditLog`

Everything in this document MUST either reuse the spine above or add a new `accounting`-owned table.
Later modules (Inventory = 5, HRM = 3, Projects = 7, Assets = 11) will FK into `accounting.*`.

---

## Leaders surveyed

1. **NetSuite (Oracle)** — full ERP with fixed assets, multi-book depreciation, OneWorld multi-entity,
   project accounting, ARM revenue recognition, advanced tax, budgeting
   — https://www.netsuite.com/portal/products/erp/financial-management.shtml

2. **Sage Intacct** — finance-first cloud ERP; strongest for multi-entity, project costing,
   dimensional reporting, and automated consolidations for mid-market
   — https://www.sage.com/en-us/sage-business-cloud/intacct/

3. **Microsoft Dynamics 365 Finance** — enterprise finance module with budget control, encumbrance
   accounting, intercompany, CTA, and Copilot-assisted planning
   — https://learn.microsoft.com/en-us/dynamics365/finance/

4. **SAP S/4HANA Finance** — multinational, real-time ledger, parallel valuation, FIFO/standard
   cost, withholding tax, transfer pricing, advanced tax
   — https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE

5. **Oracle Fusion Cloud Financials** — enterprise-grade tax provision, multi-GAAP, real-time
   consolidation, advanced revenue management, income tax deferred calculations
   — https://www.oracle.com/performance-management/tax-reporting/

6. **QuickBooks Enterprise** — SMB-to-midmarket; fixed assets (MACRS), 200+ reports, scheduled
   reporting, multi-company rollup, payroll GL sync
   — https://quickbooks.intuit.com/desktop/enterprise/advanced-reporting/

7. **Xero** — SMB cloud accounting; fixed assets (straight-line/declining balance), bank feeds,
   multi-currency (premium), limited consolidation requiring add-ons
   — https://www.xero.com/us/accounting-software/manage-fixed-assets/

8. **Workday Financial Management + Adaptive Planning** — HCM-native payroll-to-GL integration,
   driver-based planning, rolling forecasts, what-if scenarios, workforce cost planning
   — https://www.workday.com/en-us/products/adaptive-planning/financial-planning/budgeting-forecasting.html

9. **Avalara / Vertex** — dedicated tax engines: nexus tracking across 12,000+ jurisdictions,
   VAT/GST global filing, exemption certificate mgmt, income tax provision (Vertex)
   — https://www.avalara.com/us/en/products/sales-and-use-tax.html
   — https://www.vertexinc.com/solutions/income-tax-solutions

10. **FloQast / AuditBoard** — close management and SOX compliance; control documentation, SoD
    enforcement, reconciliation sign-off, exception/anomaly detection, audit evidence repository
    — https://floqast.com/blog/how-to-prepare-for-a-sox-audit/

11. **Vena / Planful (Workday Adaptive)** — FP&A and budgeting platforms; top-down/bottom-up
    budgets, version/scenario control, rolling forecasts, driver-based models, variance drill-down
    — https://www.selecthub.com/fp-and-a-software/vena-vs-planful/

---

## Feature catalog by sub-module

### 2.6 Fixed Assets

- **Asset Register (master record)** — tracks acquisition cost, capitalization date, location,
  custodian, serial/tag number, asset class, useful life, salvage value; links to a capitalization
  GL posting at acquisition.
  Seen in: NetSuite, Sage Intacct, Xero, QuickBooks Enterprise, Dynamics 365.
  Priority: table-stakes.
  Spine: new table `FixedAsset` — FKs into `GLAccount` (asset account), `JournalEntry`
  (capitalization entry), `core.OrgUnit` (location/dept), `core.Party` (custodian/vendor).
  Buildable now.

- **Depreciation Engine (scheduled run)** — calculates period depreciation and posts balanced JEs
  (Dr Depreciation Expense / Cr Accumulated Depreciation). Methods: straight-line, declining
  balance (150%/200%), sum-of-years-digits, units of production.
  Seen in: NetSuite, Sage Intacct, Xero, QuickBooks Enterprise, Dynamics 365, SAP S/4HANA.
  Priority: table-stakes.
  Spine: new child table `DepreciationSchedule` (one row per period per asset); posts to
  `JournalEntry`/`JournalLine`. Reuses `FiscalPeriod` for period gate.
  Buildable now.

- **Parallel Tax Books** — maintains a second depreciation schedule (e.g., MACRS for US tax)
  on the same asset simultaneously, posting to separate GL accounts per book type.
  Seen in: NetSuite (Multi-Book Accounting), Sage Intacct, Dynamics 365, SAP S/4HANA.
  Priority: common.
  Spine: `book_type` choice field on `DepreciationSchedule` (book / tax / ifrs / internal);
  separate GL account per book.
  Buildable now.

- **Construction-in-Progress (CIP)** — capitalizes cost accumulation in a CIP account before
  an asset is placed in service; transfer event creates the asset record and posts capitalization.
  Seen in: NetSuite, Dynamics 365, SAP S/4HANA.
  Priority: common.
  Spine: `status` choice on `FixedAsset` (cip / active / disposed / retired); CIP has no
  depreciation schedule until placed-in-service.
  Buildable now.

- **Asset Disposal / Retirement** — calculates gain/loss (sale proceeds minus net book value),
  posts Dr Cash / Dr Accum Depr / Cr Asset Cost / Dr or Cr Gain-Loss.
  Seen in: NetSuite, Sage Intacct, Xero, Dynamics 365, SAP S/4HANA.
  Priority: table-stakes.
  Spine: `disposal_date`, `disposal_proceeds`, `disposal_type` on `FixedAsset`; disposal
  action posts a balanced `JournalEntry`.
  Buildable now.

- **Asset Transfer (inter-department/location)** — moves an asset to a new `OrgUnit` or
  location, updating the asset record; may auto-generate intercompany JEs for multi-entity.
  Seen in: NetSuite, Sage Intacct, Dynamics 365.
  Priority: common.
  Spine: `AssetTransfer` event table logging from/to `OrgUnit`; no separate JE in single-entity.
  Buildable now.

- **Impairment Write-down** — reduces an asset's carrying value below net book value; posts
  Dr Impairment Loss / Cr Accumulated Impairment (IFRS: separate from Accum Depr).
  Seen in: NetSuite (revaluation), SAP S/4HANA, Dynamics 365.
  Priority: differentiator.
  Spine: `ImpairmentRecord` child table on `FixedAsset`; posts balanced `JournalEntry`.
  Buildable now.

- **Physical Inventory / Barcode Reconciliation** — periodic audit: scan/confirm vs. register,
  flag missing or found assets. (Module 11 Assets will own full operational tracking.)
  Seen in: NetSuite, Dynamics 365, SAP S/4HANA.
  Priority: differentiator.
  Spine: `AssetAudit` header + `AssetAuditLine` child. No GL impact until write-off.
  Buildable now (simple scan reconciliation); full RFID/barcode reader = integration/later.

---

### 2.7 Inventory & Cost Management (Accounting-owned financial layer only)

**Context:** `core.Item` and `StockMove` (Module 5 Inventory) are NOT yet built. This sub-module
owns the **financial valuation** and **COGS posting** layer only. When Module 5 ships, these
models gain a FK to its Item master and Stock movements.

- **Inventory Cost Layer (accounting-owned stub)** — a minimal item-like record for valuation
  purposes: `sku`, `description`, `valuation_method` (fifo/lifo/weighted_avg/standard),
  `standard_cost`, `current_avg_cost`. Does NOT duplicate Module 5's full item master — it is a
  thin financial-valuation extension, analogous to how `VendorProfile` extends `core.Party`.
  Seen in: SAP S/4HANA (material valuation), NetSuite (inventory item), Dynamics 365.
  Priority: table-stakes (for COGS functionality).
  Spine: new table `InventoryCostItem`; will gain a FK to `inventory.Item` when Module 5 ships.
  Buildable now (stub).

- **COGS Posting** — when goods are sold or consumed, posts balanced JE:
  Dr COGS (`GLAccount`) / Cr Inventory (`GLAccount`). Amount derived from valuation method layer.
  Seen in: NetSuite, SAP S/4HANA, Dynamics 365, Sage Intacct.
  Priority: table-stakes.
  Spine: `CostTransaction` table (unit_cost, quantity, direction: in/out, valuation_method,
  linked `JournalEntry`); reuses `GLAccount`.
  Buildable now.

- **Weighted-Average Cost Update** — on each inbound `CostTransaction`, recomputes
  `current_avg_cost = (old_qty * old_cost + new_qty * new_cost) / total_qty`.
  Seen in: NetSuite, SAP S/4HANA, Sage Intacct, Dynamics 365.
  Priority: table-stakes (if weighted avg chosen).
  Spine: computed in service layer on `InventoryCostItem`; no extra table.
  Buildable now.

- **Standard Cost Variance** — when actual receipt cost differs from standard cost, posts
  Dr/Cr Purchase Price Variance (`GLAccount`).
  Seen in: SAP S/4HANA, NetSuite, Dynamics 365.
  Priority: common.
  Spine: `variance_gl_account` on `InventoryCostItem`; variance amount on `CostTransaction`.
  Buildable now.

- **Landed Cost Allocation** — additional charges (freight, duty, insurance) allocated across
  receipt lines; increases unit cost and posts Dr Inventory / Cr Accrued Landed Cost.
  Seen in: NetSuite, SAP S/4HANA, Dynamics 365, Sage Intacct.
  Priority: common.
  Spine: new table `LandedCostAllocation` (linked to Bill lines as source, allocation method
  value/weight/qty, target `CostTransaction` rows); posts `JournalEntry`.
  Buildable now.

- **Inventory Valuation Report** — snapshot of on-hand quantities × current cost by item.
  (Report view over `CostTransaction` and `InventoryCostItem` — no new table.)
  Seen in: All major platforms.
  Priority: table-stakes.
  Buildable now.

---

### 2.8 Payroll Integration (Accounting-owned journal/accrual layer only)

**Context:** The full HRM payroll master (employee salary setup, run rules) belongs to Module 3.
This sub-module owns the **GL posting side** only: a payroll batch header, the summarized
distribution lines that post to GL accounts, and the accrual/clearing mechanism.

- **Payroll Journal Batch** — a dated batch of payroll expense postings (one batch per pay run).
  Header: `pay_period_start`, `pay_period_end`, `pay_date`, `status` (draft/posted), `source`
  (manual/hris_import). Posts a balanced JE:
    Dr Wages Expense (by dept via `OrgUnit`)
    Dr Payroll Tax Expense (employer share)
    Dr Benefits Expense (employer share)
    Cr Wages Payable
    Cr Payroll Tax Payable (employee + employer)
    Cr Benefits Payable
    Cr Garnishments Payable
    Cr Net Pay Clearing (bank account link)
  Seen in: Workday, ADP, QuickBooks Payroll, SAP S/4HANA, Dynamics 365.
  Priority: table-stakes.
  Spine: new table `PayrollJournalBatch` (TenantNumbered, prefix PJB); child table
  `PayrollJournalLine` (description, amount, `GLAccount`, `OrgUnit`, line_type choice:
  gross_wages/tax_withholding/employer_tax/benefits/garnishment/net_pay); batch posts one
  balanced `JournalEntry`.
  Buildable now.

- **Tax Withholding Remittance Tracking** — records that a payroll tax liability (`GLAccount`)
  was remitted via a payment to a tax authority (`core.Party`). Clears the payable balance.
  Seen in: ADP, Workday, QuickBooks Payroll, Dynamics 365.
  Priority: common.
  Spine: `TaxRemittance` table (batch FK, `Payment` FK, `GLAccount` payable cleared, amount);
  reuses existing `Payment` model for the bank debit.
  Buildable now.

- **Accrual / Reversal Pattern** — when pay date falls in a future period, posts an accrual JE
  in the current period and auto-schedules a reversal JE on the first day of the next period
  (using the existing `JournalEntry.reversal_of` mechanism).
  Seen in: NetSuite, Sage Intacct, Dynamics 365, Workday.
  Priority: common.
  Spine: `is_accrual` boolean on `PayrollJournalBatch`; reversal JE created via existing
  `_reverse_journal_entry` helper.
  Buildable now.

- **Benefits Accounting (employer contribution tracking)** — tracks employer contributions to
  health, 401k, HSA per GL account per pay run. Amounts appear as lines in
  `PayrollJournalLine` with `line_type = benefits`.
  Seen in: Workday, ADP, Dynamics 365.
  Priority: common.
  Spine: covered by `PayrollJournalLine` line_type choices; no extra table.
  Buildable now.

- **Garnishment Payable Clearing** — court-ordered deductions sit in a Garnishments Payable
  account; a separate payment clears them when remitted to the issuing authority.
  Seen in: ADP, Workday, Dynamics 365.
  Priority: common.
  Spine: covered by `PayrollJournalLine` line_type = garnishment + a `TaxRemittance`-pattern
  clearing payment.
  Buildable now.

---

### 2.9 Project / Job Costing

- **Project (Job) Master** — named project with a client (`core.Party`), type, status, billing
  method (time_and_materials / fixed_price / milestone / cost_plus), start/end dates, and a
  project manager (`core.Party` or User).
  Seen in: Sage Intacct, NetSuite, Dynamics 365.
  Priority: table-stakes.
  Spine: new table `Project` (TenantNumbered, prefix PRJ); FKs into `core.Party` (client),
  `core.OrgUnit` (department).
  Buildable now.

- **Project Budget** — budget amounts by GL account (or WBS task) per `FiscalPeriod`.
  Supports top-down total or bottom-up task-level budgeting.
  Seen in: Sage Intacct, NetSuite, Dynamics 365, Oracle Fusion.
  Priority: table-stakes.
  Spine: new table `ProjectBudgetLine` (Project FK, `GLAccount` FK, `FiscalPeriod` FK,
  budgeted_amount).
  Buildable now.

- **Cost Transaction Tagging** — any `JournalLine` can reference a `Project` to accumulate
  actual cost vs. budget. This is the zero-new-table trick: add a nullable `project` FK to
  `JournalLine`.
  Seen in: Sage Intacct (dimensions), NetSuite, Dynamics 365.
  Priority: table-stakes.
  Spine: add FK `project` to `JournalLine` (nullable, on_delete SET_NULL).
  Buildable now (migration on existing table).

- **Time & Expense Entry** — employee time (hours × rate) and expense items linked to a Project;
  when approved, posts a balanced JE (Dr Labor/Expense / Cr Accrued Labor) and marks lines as
  billable or non-billable.
  Seen in: Sage Intacct, NetSuite, Dynamics 365, Oracle Fusion.
  Priority: common.
  Spine: new table `TimeExpenseEntry` (TenantNumbered, prefix TE); lines child table; FKs into
  `Project`, `GLAccount`, `core.Party` (employee). Posts `JournalEntry`.
  Buildable now.

- **Revenue Recognition Schedule** — for fixed-price or milestone projects, defines when revenue
  is recognized (as % complete, milestone, or schedule); posts Dr Deferred Revenue / Cr Revenue
  (or Dr WIP / Cr Revenue).
  Seen in: NetSuite (ARM, ASC 606), Sage Intacct (rev rec module), Dynamics 365.
  Priority: common.
  Spine: new table `RevenueRecognitionSchedule` (Project FK, method choice:
  percentage_complete/milestone/straight_line, line rows with target dates and amounts);
  recognition run posts balanced `JournalEntry`.
  Buildable now.

- **Project Invoice (Progress Billing)** — generates an AR Invoice (reusing existing `Invoice`
  model) linked to the Project. Supports retention holdback percentage.
  Seen in: Sage Intacct, NetSuite, Dynamics 365.
  Priority: common.
  Spine: add nullable `project` FK to existing `Invoice`; add `retention_pct` field on Invoice.
  Buildable now (migration on existing table).

- **Profitability Dashboard (report view)** — budget vs. actual revenue and cost per project;
  earned value = % complete × budget. Report view over `ProjectBudgetLine` and tagged
  `JournalLine` rows — no new table.
  Seen in: Sage Intacct, NetSuite, Oracle Fusion.
  Priority: table-stakes.
  Buildable now (query/report view).

---

### 2.10 Multi-Entity & Consolidation

- **Entity (Sub-entity) Management** — each `core.OrgUnit` with `unit_type = entity` is a
  legal entity within the tenant group. A consolidation group links a parent entity to its
  subsidiaries. Currency can differ per entity.
  Seen in: NetSuite OneWorld, Sage Intacct Global Consolidations, Dynamics 365.
  Priority: table-stakes.
  Spine: new table `ConsolidationGroup` (parent `OrgUnit`, list of member `OrgUnit`s,
  reporting `Currency`). Reuses `core.OrgUnit`.
  Buildable now.

- **Intercompany Transaction Pair** — when entity A posts a receivable from entity B,
  the system creates a matching payable in entity B's GL (due-to / due-from accounts).
  Seen in: NetSuite, Sage Intacct, Dynamics 365, SAP S/4HANA.
  Priority: table-stakes.
  Spine: new table `IntercompanyTransaction` links two `JournalEntry` rows (one per entity);
  `from_org_unit`, `to_org_unit`, matching amount. Reuses `JournalEntry`.
  Buildable now.

- **Currency Translation (CTA)** — balance sheet accounts translated at closing rate, income
  statement at average rate; the difference is posted to a Cumulative Translation Adjustment
  equity account.
  Seen in: NetSuite OneWorld, Sage Intacct, Dynamics 365, SAP S/4HANA.
  Priority: common.
  Spine: `CurrencyTranslation` run table (period, entity, method: closing/average, CTA
  `GLAccount`); posts balanced `JournalEntry`. Reuses `ExchangeRate`, `FiscalPeriod`.
  Buildable now.

- **Elimination Entry** — reverse intercompany revenue/expense/payable/receivable pairs so they
  do not appear in consolidated statements. Elimination JEs are tagged `entry_type = elimination`.
  Seen in: NetSuite, Sage Intacct, Dynamics 365.
  Priority: common.
  Spine: new choice `elimination` on existing `JournalEntry.entry_type`; `ConsolidationGroup`
  FK on the JE identifies which consolidation it belongs to.
  Buildable now.

- **Consolidated Report (report view)** — aggregates posted `JournalLine` rows across member
  `OrgUnit`s in a `ConsolidationGroup`, applying elimination entries, yielding group-level
  Balance Sheet and P&L. No new table — report/query logic.
  Seen in: All major platforms.
  Priority: table-stakes.
  Buildable now.

- **Transfer Pricing Documentation** — notes field + supporting document attachment on an
  `IntercompanyTransaction`; links to `core.Document`. No complex pricing engine in this pass.
  Seen in: SAP S/4HANA, Dynamics 365, Oracle Fusion.
  Priority: differentiator.
  Spine: `notes` + `document` FK on `IntercompanyTransaction`.
  Buildable now (doc attachment only; automation/pricing engine = deferred).

---

### 2.11 Tax

- **Tax Rate Master** — defines rates per jurisdiction (country/state/county/city), tax type
  (sales/use/vat/gst/withholding), effective date range, and whether the product/party is exempt.
  Seen in: Avalara, Vertex, NetSuite, Sage Intacct, SAP S/4HANA, Dynamics 365.
  Priority: table-stakes.
  Spine: new table `TaxCode` (already referenced in NavERP ERD spine; if not yet in core, add to
  accounting). Fields: code, name, tax_type, rate_pct, jurisdiction_level, country, region,
  effective_from, effective_to, `GLAccount` for tax payable.
  Buildable now.

- **Nexus Tracking** — records which jurisdictions the tenant has economic or physical nexus in,
  with threshold monitoring (e.g., $100K sales or 200 transactions per state).
  Seen in: Avalara, Vertex, NetSuite, Dynamics 365.
  Priority: common.
  Spine: new table `TaxNexus` (jurisdiction, nexus_type choice: physical/economic,
  threshold_amount, current_ytd_sales, is_registered).
  Buildable now (manual threshold entry; Avalara API = integration/later).

- **Tax Calendar** — filing deadline per jurisdiction per period; supports recurring schedules
  (monthly/quarterly/annual); status: upcoming/filed/overdue.
  Seen in: Avalara, NetSuite, Dynamics 365, Sage Intacct.
  Priority: common.
  Spine: new table `TaxFilingObligation` (TaxNexus FK, filing_period_start/end, due_date,
  status, filed_date, filed_by User).
  Buildable now.

- **Use Tax Tracking** — self-assessed tax on purchases where vendor did not charge sales tax;
  records liability and posts Dr Use Tax Expense / Cr Use Tax Payable.
  Seen in: Avalara, NetSuite, Dynamics 365.
  Priority: common.
  Spine: `use_tax_amount` + `use_tax_gl_account` on `BillLine`; posting handled by the bill
  journal entry action.
  Buildable now (field addition on existing table).

- **Income Tax Provision (stub)** — tracks current and deferred tax amounts per fiscal year.
  Current tax = taxable income × effective rate. Deferred tax arises from timing differences
  (asset depreciation, bad debt, unearned revenue). Posts Dr Income Tax Expense / Cr Tax Payable
  or Deferred Tax Liability.
  Seen in: Oracle Tax Reporting Cloud, Vertex, NetSuite, Dynamics 365 Finance.
  Priority: differentiator (for public companies; stub sufficient for this pass).
  Spine: new table `TaxProvision` (fiscal_year, entity `OrgUnit`, pretax_income, current_tax,
  deferred_tax, effective_rate, status, linked `JournalEntry`).
  Buildable now (manual entry stub; full automated calculation = integration/later).

- **Sales Tax Return (filing record)** — records a completed tax filing per `TaxFilingObligation`:
  taxable_sales, exempt_sales, tax_collected, tax_remitted, `Payment` FK for the remittance.
  Seen in: Avalara, NetSuite, Dynamics 365, Sage Intacct.
  Priority: common.
  Spine: new table `TaxReturn` (filing obligation FK, period amounts, `Payment` FK).
  Buildable now (manual form; Avalara e-file = integration/later).

---

### 2.12 Reporting & Compliance

All reporting in this sub-module is **report/query views** over the existing `JournalLine`,
`GLAccount`, `FiscalPeriod`, `Invoice`, `Bill`, and `Payment` tables. No new database tables
are required for core financial statements.

- **Balance Sheet** — assets = liabilities + equity, as of a date. Filters `JournalLine`
  where `entry.status = posted` and `gl_account.account_type IN (asset, liability, equity)`;
  sums debit minus credit per account; groups by account hierarchy.
  Seen in: All 10+ platforms surveyed.
  Priority: table-stakes.
  Spine: report view only. Buildable now.

- **Profit & Loss (Income Statement)** — revenue minus expenses for a date range.
  Filters `account_type IN (income, expense)`. Supports comparative prior-period column.
  Seen in: All 10+ platforms.
  Priority: table-stakes.
  Spine: report view only. Buildable now.

- **Cash Flow Statement** — operating/investing/financing sections derived from JE entry_type
  and account classification. Indirect method: start from net income, adjust for non-cash items.
  Seen in: NetSuite, Sage Intacct, Dynamics 365, QuickBooks Enterprise.
  Priority: common.
  Spine: add `cash_flow_category` choice field (operating/investing/financing) to `GLAccount`
  to enable automated classification. Report view. Buildable now.

- **Trial Balance** — all accounts with debit and credit totals for a period.
  Seen in: All platforms.
  Priority: table-stakes.
  Spine: report view only. Buildable now.

- **Departmental P&L (Management Report)** — P&L filtered by `JournalLine.org_unit`
  (OrgUnit / cost centre dimension). No new table.
  Seen in: Sage Intacct, NetSuite, Dynamics 365.
  Priority: common.
  Spine: filter on existing `JournalLine.org_unit`. Buildable now.

- **Scheduled Report** — user configures report type + recipients + CRON-like schedule;
  Celery/Django Q worker exports PDF/XLSX and emails it.
  Seen in: QuickBooks Enterprise, Dynamics 365, NetSuite, Sage Intacct.
  Priority: common.
  Spine: new table `ScheduledReport` (report_type, frequency, last_run, recipients JSON,
  format choice). Buildable now (async task = Celery/later for live scheduling;
  data model buildable now).

- **XBRL / SEC Filing** — structured tagging of financials for SEC/EDGAR submission.
  Seen in: Dynamics 365, Oracle Fusion.
  Priority: differentiator (public companies only).
  Deferred — external filing integration.

---

### 2.13 Budgeting & Planning

- **Budget Version** — named container for a budget scenario (e.g., "FY 2026 Board Approved",
  "FY 2026 Stretch"). Multiple versions allowed per tenant per fiscal year. One version is
  flagged `is_active` for variance reporting.
  Seen in: Vena, Planful, Workday Adaptive Planning, Dynamics 365, NetSuite.
  Priority: table-stakes.
  Spine: new table `BudgetVersion` (name, fiscal_year, version_type choice:
  original/revised/forecast/what_if, is_active, locked_by, locked_at).
  Buildable now.

- **Budget Line** — one amount per GL account per period per budget version. Supports both
  top-down (entered at summary level) and bottom-up (entered at detail account level).
  Seen in: Vena, Planful, Workday Adaptive Planning, Dynamics 365, NetSuite.
  Priority: table-stakes.
  Spine: new table `BudgetLine` (BudgetVersion FK, `GLAccount` FK, `FiscalPeriod` FK,
  `OrgUnit` FK, amount). Composite unique: (version, account, period, org_unit).
  Buildable now.

- **Budget vs. Actual Variance Report** — compares `BudgetLine.amount` against actual
  `JournalLine` aggregated by same (account, period, org_unit) dimensions.
  Seen in: All FP&A platforms; Dynamics 365 Budget Analysis report.
  Priority: table-stakes.
  Spine: report/query view over `BudgetLine` JOIN `JournalLine`. No new table. Buildable now.

- **Rolling Forecast** — a `BudgetVersion` of type `forecast` where past periods contain
  actuals (copied in or sourced from JE aggregation) and future periods contain forward
  projections. UI allows period-by-period override.
  Seen in: Planful, Workday Adaptive, Dynamics 365.
  Priority: common.
  Spine: reuses `BudgetVersion` + `BudgetLine` with version_type = forecast;
  `is_locked_actuals` boolean on `BudgetLine` for past periods.
  Buildable now.

- **What-If Scenario Modeling** — creates a new `BudgetVersion` (type = what_if) as a copy of
  an existing version; user adjusts driver assumptions; variance vs. base version shown.
  Seen in: Vena, Workday Adaptive, Planful, Dynamics 365.
  Priority: common.
  Spine: `copied_from` FK on `BudgetVersion`; copy-lines view action. No new table. Buildable now.

- **Driver-Based Planning** — revenue or cost lines computed from a driver × rate formula
  (e.g., headcount × salary rate). A lightweight driver table stores the assumptions.
  Seen in: Workday Adaptive, Anaplan, Vena, Planful.
  Priority: differentiator.
  Spine: new table `BudgetDriver` (BudgetVersion FK, driver_name, value, linked `BudgetLine`
  formula). Buildable now (simple formula; ML forecasting = integration/later).

- **Budget Control / Encumbrance** — blocks posting of a `JournalEntry` if the remaining
  budget for the (account, period, org_unit) would be exceeded.
  Seen in: Dynamics 365 Finance (budget control module), NetSuite, SAP S/4HANA.
  Priority: differentiator.
  Spine: view-layer check compares proposed JE amount against `BudgetLine.amount` minus
  actual sum; no new table. Buildable now.

---

### 2.14 Audit & Controls

- **Control Record** — documents an internal control (name, objective, frequency, owner User,
  risk area) for SOX or similar compliance frameworks.
  Seen in: FloQast, AuditBoard, Dynamics 365 GRC, SAP GRC.
  Priority: common.
  Spine: new table `ControlRecord` (name, description, control_type choice:
  preventive/detective/corrective, frequency choice: daily/weekly/monthly/quarterly/annual,
  risk_area, owner User, is_active).
  Buildable now.

- **Control Test / Evidence** — records each execution of a control test: tester, date tested,
  result (passed/failed/exception), and attached evidence document (`core.Document`).
  Seen in: FloQast, AuditBoard.
  Priority: common.
  Spine: new child table `ControlTest` (ControlRecord FK, test_date, tester User, result,
  notes, `core.Document` FK).
  Buildable now.

- **Segregation of Duties (SoD) Rule** — defines conflicting permission pairs (e.g., "user who
  creates a vendor cannot also approve payments to that vendor"). Enforced at the view/permission
  layer; rule is documented in this table.
  Seen in: FloQast, AuditBoard, Dynamics 365, SAP GRC.
  Priority: common.
  Spine: new table `SoDRule` (action_a, action_b, risk_rating choice: low/medium/high/critical,
  description). Enforcement via Django permission checks; table is documentation + monitoring.
  Buildable now (documentation layer; automated SoD scanning = integration/later).

- **Audit Trail** — `core.AuditLog` already exists and is used by `write_audit_log`. The 2.14
  requirement is to surface a searchable audit-trail list view filtered by model, user, date,
  and action type.
  Seen in: All 10+ platforms.
  Priority: table-stakes.
  Spine: reuses `core.AuditLog`. Report/list view only. Buildable now.

- **Exception / Anomaly Flag** — a user or automated check flags a `JournalEntry`, `Invoice`,
  or `Bill` as an exception requiring review. Exceptions are tracked with status and resolution.
  Seen in: FloQast, AuditBoard, Dynamics 365.
  Priority: common.
  Spine: new table `ExceptionFlag` (content_type FK + object_id for generic FK pattern,
  flag_type, raised_by, raised_at, status choice: open/under_review/resolved, resolution_notes).
  Buildable now.

- **Period Close Checklist** — a list of required tasks per `FiscalPeriod` close (reconcile
  bank, post depreciation, accrue payroll, review exceptions, approve consolidation). Each task
  has an assignee, due date, and completion sign-off.
  Seen in: FloQast (primary product), AuditBoard, Dynamics 365, Sage Intacct.
  Priority: common.
  Spine: new table `PeriodCloseTask` (FiscalPeriod FK, task_name, assignee User, due_date,
  status choice: pending/in_progress/done, completed_by User, completed_at).
  Buildable now.

---

### 2.15 Integration & API

All items here are **config-model stubs** or **deferred live integrations**. The data model
supports the configuration; the live data flow ships later as Django management commands or
Celery tasks backed by external credentials.

- **External Integration Config** — stores credentials/settings for each third-party integration
  (Plaid, Stripe, Avalara, HRIS connectors, etc.) per tenant. Credentials stored encrypted
  (never plaintext in the DB).
  Seen in: NetSuite (integration records), Dynamics 365, Xero (connected apps).
  Priority: common.
  Spine: new table `IntegrationConfig` (tenant FK, integration_type choice:
  plaid/stripe/paypal/avalara/vertex/shopify/woocommerce/salesforce/hubspot/workday/adp/
  bamboohr/dropbox/box/sharepoint/custom, endpoint_url, api_key_encrypted, is_active,
  last_synced_at, sync_status).
  Buildable now (config model); live API calls = integration/later.

- **Bank Feed (Plaid / Open Banking)** — auto-imports `BankTransaction` rows from Plaid or
  Open Banking API; deduplicated by `external_ref`. The existing `BankTransaction` model
  already has `source = bank_feed` and `external_ref`.
  Seen in: Xero, QuickBooks, Sage Intacct, NetSuite.
  Priority: common.
  Spine: reuses `BankTransaction` (source = bank_feed). Live Plaid OAuth = integration/later.

- **Payment Gateway Webhook** — on Stripe/PayPal payment confirmation webhooks, auto-creates
  a `Payment` (direction=in) and `BankTransaction` row.
  Seen in: Xero, QuickBooks, NetSuite, Sage Intacct.
  Priority: common.
  Spine: reuses `Payment` + `BankTransaction`. Stripe/PayPal webhook endpoint = integration/later.

- **Tax Engine Connector (Avalara/Vertex)** — on invoice creation, calls Avalara AvaTax API
  to compute tax; writes result back to `InvoiceLine.tax_rate_pct` and `TaxCode` lookup.
  Seen in: NetSuite, Dynamics 365, SAP S/4HANA.
  Priority: differentiator.
  Spine: `IntegrationConfig` row (type=avalara); API call in invoice-post service = integration/later.

- **ERP/HRIS Payroll Import** — imports payroll run summaries from Workday/ADP/BambooHR as
  `PayrollJournalBatch` rows (CSV or API). Manual import is buildable now via CSV upload.
  Seen in: Workday, ADP, Dynamics 365.
  Priority: common.
  Spine: reuses `PayrollJournalBatch`; HRIS API connector = integration/later.

- **Custom REST API** — exposes NavERP accounting data (GL accounts, journal entries, invoices,
  payments) via DRF (Django REST Framework) endpoints for external consumers.
  Seen in: NetSuite (SuiteQL/REST), Sage Intacct (XML/REST API), Dynamics 365 (OData).
  Priority: differentiator.
  Spine: DRF serializers + viewsets; no new models. Buildable now (DRF) = integration pass.

---

## Recommended build scope (this pass — 14 primary models)

The following 14 accounting-owned models cover a representative live page per sub-module.
All post balanced `JournalEntry`/`JournalLine` rows on key actions. All are tenant-scoped.

### 2.6 Fixed Assets (3 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `FixedAsset` | FA- | asset_class, acquisition_cost, acquisition_date, useful_life_months, salvage_value, status(cip/active/disposed/retired), location `OrgUnit`, custodian `Party`, asset_gl_account `GLAccount`, accum_depr_gl_account, disposal_date, disposal_proceeds | `GLAccount`, `OrgUnit`, `Party`, `JournalEntry` (capitalization link) | On acquisition and disposal |
| `DepreciationSchedule` | — | `FixedAsset` FK, `FiscalPeriod` FK, book_type(book/tax/ifrs), method(sl/db/syd/uop), period_depr_amount, accum_depr_to_date, status(scheduled/posted), `JournalEntry` FK | `FiscalPeriod`, `GLAccount`, `JournalEntry` | Yes — Dr Depr Exp / Cr Accum Depr per period |
| `AssetDisposal` | — | `FixedAsset` FK, disposal_date, disposal_type(sale/scrap/transfer), proceeds, gain_loss (computed), `JournalEntry` FK | `JournalEntry`, `GLAccount` | Yes — Dr Cash/Accum Depr, Cr Asset Cost, Dr/Cr Gain-Loss |

### 2.7 Inventory Cost Management (2 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `InventoryCostItem` | — | sku, description, valuation_method(fifo/lifo/weighted_avg/standard), standard_cost, current_avg_cost, on_hand_qty, inventory_gl_account `GLAccount`, cogs_gl_account `GLAccount`, variance_gl_account | `GLAccount` | No (referenced by CostTransaction) |
| `CostTransaction` | CT- | `InventoryCostItem` FK, direction(in/out), quantity, unit_cost, total_cost, transaction_date, `JournalEntry` FK, reference_type(purchase/sale/adjustment/landed_cost) | `GLAccount`, `JournalEntry` | Yes — Dr COGS / Cr Inventory on outbound |

### 2.8 Payroll Integration (2 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `PayrollJournalBatch` | PJB- | pay_period_start, pay_period_end, pay_date, source(manual/csv_import/hris), is_accrual, `FiscalPeriod` FK, status(draft/posted), `JournalEntry` FK | `FiscalPeriod`, `JournalEntry` | Yes — multi-line balanced JE |
| `PayrollJournalLine` | — | `PayrollJournalBatch` FK, line_type(gross_wages/employer_tax/employee_tax/benefits/garnishment/net_pay), amount, `GLAccount` FK, `OrgUnit` FK, description | `GLAccount`, `OrgUnit` | Lines aggregated into batch JE |

### 2.9 Project / Job Costing (3 models + 2 FK additions)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `Project` | PRJ- | name, client `Party`, billing_method(t_and_m/fixed/milestone/cost_plus), status, start/end dates, project_manager User, `OrgUnit` FK, retention_pct | `Party`, `OrgUnit` | No (container) |
| `ProjectBudgetLine` | — | `Project` FK, `GLAccount` FK, `FiscalPeriod` FK, budgeted_amount | `GLAccount`, `FiscalPeriod` | No |
| `RevenueRecognitionSchedule` | — | `Project` FK, method(pct_complete/milestone/straight_line), recognized_to_date, deferred_revenue_gl `GLAccount`, revenue_gl `GLAccount` | `GLAccount`, `JournalEntry` | Yes — Dr Deferred Rev / Cr Revenue |
| FK addition | — | Add nullable `project` FK to `JournalLine` (migration on existing table) | — | — |
| FK addition | — | Add nullable `project` FK + `retention_pct` to `Invoice` (migration on existing table) | — | — |

### 2.10 Multi-Entity & Consolidation (2 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `ConsolidationGroup` | — | name, parent `OrgUnit`, member `OrgUnit`s (M2M), reporting `Currency`, is_active | `OrgUnit`, `Currency` | No |
| `IntercompanyTransaction` | ICT- | `ConsolidationGroup` FK, from_entity `OrgUnit`, to_entity `OrgUnit`, transaction_date, amount, `Currency`, from_journal_entry `JournalEntry`, to_journal_entry `JournalEntry`, status(draft/posted/eliminated), notes, `core.Document` | `OrgUnit`, `JournalEntry`, `Currency` | Yes — one JE per entity; elimination JE on consolidation run |

### 2.11 Tax (3 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `TaxCode` | — | code, name, tax_type(sales/use/vat/gst/withholding/income), rate_pct, jurisdiction_level(federal/state/county/city), country, region, effective_from, effective_to, payable_gl `GLAccount`, is_active | `GLAccount` | No (rate lookup) |
| `TaxNexus` | — | jurisdiction_name, country, region, nexus_type(physical/economic), threshold_amount, current_ytd_sales, registration_number, is_registered, registration_date | — | No |
| `TaxFilingObligation` | — | `TaxNexus` FK, `TaxCode` FK, filing_period_start, filing_period_end, due_date, status(upcoming/filed/overdue), taxable_amount, tax_due, `Payment` FK | `Payment` | No (tracks filings) |

### 2.12 Reporting (1 model)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `ScheduledReport` | — | report_type(balance_sheet/pl/cash_flow/trial_balance/ar_aging/ap_aging/budget_variance), frequency(daily/weekly/monthly), recipients JSON, format(pdf/xlsx), last_run_at, next_run_at, is_active | `FiscalPeriod` (optional) | No |

Also: add `cash_flow_category` choice (operating/investing/financing) to `GLAccount` (field migration).

### 2.13 Budgeting (2 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `BudgetVersion` | BV- | name, fiscal_year, version_type(original/revised/forecast/what_if), is_active, is_locked, copied_from `BudgetVersion` (self FK), approved_by User | — | No |
| `BudgetLine` | — | `BudgetVersion` FK, `GLAccount` FK, `FiscalPeriod` FK, `OrgUnit` FK, budgeted_amount, is_locked_actuals (for rolling forecast past periods) | `GLAccount`, `FiscalPeriod`, `OrgUnit` | No |

### 2.14 Audit & Controls (3 models)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `ControlRecord` | — | name, description, control_type(preventive/detective/corrective), frequency, risk_area, owner User, is_active | — | No |
| `ControlTest` | — | `ControlRecord` FK, test_date, tester User, result(pass/fail/exception), notes, `core.Document` FK | `core.Document` | No |
| `PeriodCloseTask` | — | `FiscalPeriod` FK, task_name, task_type(bank_recon/depreciation/payroll_accrual/exception_review/consolidation/custom), assignee User, due_date, status(pending/in_progress/done), completed_by User, completed_at | `FiscalPeriod` | No |

### 2.15 Integration (1 model)

| Model | Prefix | Key Fields | Reuses | Posts JE? |
|---|---|---|---|---|
| `IntegrationConfig` | — | integration_type(plaid/stripe/paypal/avalara/vertex/shopify/woocommerce/salesforce/hubspot/workday/adp/bamboohr/custom), endpoint_url, api_key_encrypted, is_active, last_synced_at, sync_status(idle/running/error/success), error_message | — | No |

**Total primary models this pass: 21 new tables + 3 FK/field migrations on existing tables.**

---

## Double-entry posting summary

Every action below MUST produce a balanced JE (Σdebit == Σcredit):

| Event | Dr | Cr |
|---|---|---|
| Asset acquisition (cash purchase) | Fixed Asset GL | Cash/AP |
| Monthly depreciation | Depreciation Expense | Accumulated Depreciation |
| Asset disposal (gain) | Accum Depr, Cash/AR | Asset Cost, Gain on Disposal |
| Asset disposal (loss) | Accum Depr, Cash/AR, Loss on Disposal | Asset Cost |
| Impairment write-down | Impairment Loss | Accum Impairment |
| COGS outbound | COGS | Inventory |
| Payroll run | Wages Exp, Employer Tax Exp, Benefits Exp | Wages Payable, Tax Payable, Benefits Payable, Garnishments Payable, Net Pay Clearing |
| Net pay disbursement | Net Pay Clearing | Cash (bank) |
| Tax remittance | Tax Payable | Cash |
| Labor/expense accrual (project) | Labor/Expense Expense | Accrued Labor |
| Revenue recognition (% complete) | Deferred Revenue (or WIP) | Revenue |
| Intercompany sale (entity A) | Intercompany Receivable | Revenue |
| Intercompany sale (entity B) | COGS/Expense | Intercompany Payable |
| Elimination | Intercompany Revenue | Intercompany COGS (reverse above) |
| Currency translation CTA | CTA Equity | Translation Gain/Loss Equity |

---

## Deferred (later passes / integrations)

- **Live Plaid bank feed OAuth** — `BankTransaction.source = bank_feed` is modeled; actual
  Plaid token exchange and polling requires external OAuth credentials. Deferred to an
  integration pass.

- **Avalara AvaTax real-time API call** — `TaxCode` rate master covers manual/imported rates.
  Avalara API call on invoice-post (12,000+ jurisdiction lookup) needs `IntegrationConfig`
  credential + HTTP call. Deferred.

- **Vertex income tax provision automation** — `TaxProvision` stub supports manual entry.
  Automated deferred tax calc from temporary differences (asset book-tax timing) requires
  sophisticated rules engine. Deferred.

- **XBRL / EDGAR filing** — structured tagging for SEC submission. Deferred (public companies
  only; requires XBRL taxonomy library).

- **Module 5 Item FK on `InventoryCostItem`** — when Inventory (Module 5) ships, add a FK
  from `InventoryCostItem` to `inventory.Item` and from `CostTransaction` to
  `inventory.StockMove`. The financial valuation layer is buildable now without it.

- **Module 3 HRM FK on `PayrollJournalBatch`** — when HRM (Module 3) ships, add a FK from
  `PayrollJournalBatch` to `hrm.PayrollRun`; the journal/accrual layer is buildable now
  without it.

- **Module 7 Project FK on `Project`** — when Projects (Module 7) ships, the
  `accounting.Project` stub can gain a FK to the full project management entity; the costing
  and billing layer is buildable now.

- **Full WBS task hierarchy** — multi-level task tree under a Project (epic/task/subtask).
  Covered in the nav ERD stub; deferred to the full Project module pass.

- **Earned Value Management (EVM)** — BCWS, BCWP, ACWP, SPI, CPI metrics. Deferred to
  Module 7 Projects where schedule data exists.

- **HRIS API payroll import (Workday/ADP)** — live API connector for `PayrollJournalBatch`
  import. Manual CSV import is buildable now; live API = integration/later.

- **Stripe/PayPal payment gateway webhooks** — endpoint handlers to auto-create `Payment` rows.
  The data model is ready; webhook endpoint + signature verification = integration/later.

- **DRF REST API layer** — Django REST Framework serializers/viewsets for accounting objects.
  No new models needed; DRF is an integration/API pass separate from the core module build.

- **CRON-based scheduled report delivery** — `ScheduledReport` model is buildable now; actual
  Celery beat task for timed report generation + email = async-worker pass.

- **Physical asset barcode/RFID scanning** — `AssetAudit` reconciliation is simple; full
  scanner integration (mobile app, barcode reader) = Module 11 Assets integration.

- **Transfer pricing documentation automation** — `IntercompanyTransaction.notes` + document
  attachment is buildable now; TP policy enforcement and pricing engine = deferred.

- **Minority interest calculation** — complex equity consolidation for partial ownership.
  Deferred; full consolidation engine is an enterprise-only feature.

- **Budget encumbrance (pre-commitment blocking)** — view-layer budget check is buildable;
  pre-encumbrance on purchase requisitions requires Module 6 Procurement to exist first.

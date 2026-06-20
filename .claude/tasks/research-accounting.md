# Research — Module 2: Accounting & Finance (accounting)

## Leaders surveyed (with source links)

1. **QuickBooks Online** — dominant SMB cloud accounting with 7M+ subscribers; strong bank feeds, reconciliation,
   and invoicing — https://quickbooks.intuit.com/accounting/
2. **Xero** — cloud-first double-entry accounting for SMB/mid-market; acclaimed bank reconciliation UX and 1000+
   integrations — https://www.xero.com/us/accounting-software/
3. **Sage Intacct** — AICPA-preferred mid-market platform; multi-dimensional GL, native period-close checklists,
   robust AR/AP automation — https://www.sage.com/en-us/sage-business-cloud/intacct/product-capabilities/core-financials/
4. **Oracle NetSuite ERP** — enterprise/upper-mid-market cloud ERP; multi-entity, real-time GL, AI-assisted
   reconciliation, close management — https://www.netsuite.com/portal/products/erp/financial-management/
5. **Zoho Books** — full-featured SMB accounting with 70+ reports, fiscal period locking, workflow automation,
   multi-currency — https://www.zoho.com/us/books/accounting-software-features/
6. **FreshBooks** — SMB-oriented invoicing-first accounting; journal entries, bank connections, expense tracking,
   recurring invoices — https://www.freshbooks.com/
7. **Wave** — free Starter tier for micro/small businesses; GL, bank reconciliation, invoicing, expense tracking;
   acquired 2025 — https://www.waveapps.com/
8. **Odoo Accounting** — open-source/SaaS module within full ERP; smart reconciliation (95%+ auto-match), fiscal
   localization packs, SEPA payments — https://www.odoo.com/app/accounting-features
9. **Microsoft Dynamics 365 Business Central** — mid/upper-mid ERP; unlimited fiscal periods, 8 GL dimensions,
   Copilot-assisted bank reconciliation, AI cash flow forecasting —
   https://www.randgroup.com/insights/microsoft/dynamics-365/business-central/business-central-accounting-software-key-features-and-benefits/
10. **SAP Business One** — SMB-to-mid ERP; automated GL posting on every transaction, internal reconciliation
    engine, bank statement import, period-end closing — https://softengine.com/blog-sap-business-one-accounting-and-financial-management/

---

## Feature catalog by sub-module

### 2.1 Dashboard & Analytics

- **KPI Summary Cards** — cash position, total AR outstanding, total AP outstanding, net income YTD on a single
  screen · seen in: QuickBooks, Xero, Zoho Books, FreshBooks, Odoo, Business Central · priority: table-stakes
  · spine: no new table (computed from JournalLine/Invoice aggregates) · buildable now (template-level aggregation)

- **Overdue Alert Center** — surfaced list of overdue invoices (AR) and past-due bills (AP) on the dashboard,
  with days-overdue counts · seen in: Sage Intacct, Zoho Books, QuickBooks, Xero · priority: table-stakes
  · spine: derives from Invoice.due_date vs today · buildable now

- **Cash Flow Widget** — bar or line chart showing cash-in vs cash-out by week/month, sourced from Payment
  records · seen in: Xero, QuickBooks, Business Central, Zoho Books · priority: common
  · spine: derives from Payment table (direction in/out + paid_on) · buildable now

- **Quick-Action Shortcuts** — one-click "New Invoice", "Record Bill", "New Journal Entry", "Reconcile Bank"
  buttons on the dashboard · seen in: QuickBooks, Xero, Zoho Books, FreshBooks · priority: table-stakes
  · spine: no new table; just navigation links · buildable now

- **Trial Balance / P&L Snapshot** — period-to-date balance per account type visible on the dashboard, drilling
  into the GL · seen in: Sage Intacct, NetSuite, Business Central · priority: common
  · spine: aggregate over JournalLine grouped by GLAccount.type · buildable now

- **AI Cash Flow Forecasting** — ML model predicts next 30/90-day cash position using historical Payment
  patterns and outstanding Invoice totals · seen in: Business Central (Copilot), QuickBooks, Xero · priority: differentiator
  · spine: reads Payment + Invoice · integration/later (ML / external service)

- **Custom Report Builder** — drag-and-drop column/row layout for ad-hoc financial reports · seen in: Sage
  Intacct, NetSuite, Zoho Books · priority: differentiator · spine: reads GL · integration/later (complex UI)

---

### 2.2 General Ledger (GL)

- **Chart of Accounts (CoA)** — hierarchical account tree with code, name, and type (asset, liability, equity,
  income, expense); parent-child nesting for sub-accounts; one per tenant · seen in: all 10 products
  · priority: table-stakes · spine: new table GLAccount (accounting-owned) · buildable now
  Double-entry invariant: every JournalLine debits or credits a GLAccount; balances are derived aggregates.

- **Account Types / Normal Balances** — enforced type labels (asset/liability/equity/income/expense) drive
  report placement and determine whether debit or credit increases the balance · seen in: all 10 products
  · priority: table-stakes · spine: GLAccount.account_type CharField · buildable now

- **Manual Journal Entries (double-entry)** — user creates a JournalEntry with N debit lines + N credit lines;
  system validates sum(debits) == sum(credits) before save; append-only (no delete/edit once posted) · seen in:
  all 10 products · priority: table-stakes · spine: new tables JournalEntry + JournalLine (accounting-owned)
  · buildable now
  Invariant: JournalEntry is immutable once status='posted'; corrections use a reversal entry only.

- **Recurring Journal Entries** — template JE that auto-posts on a schedule (monthly accruals, depreciation,
  prepaid amortization) · seen in: QuickBooks, Xero, Zoho Books, Business Central, Odoo · priority: common
  · spine: new table RecurringJournal (accounting-owned, references JournalEntry template) · buildable now

- **Reversing Journal Entries** — a posted JE spawns a mirror entry on the first day of the next period, used
  for accrual reversals · seen in: Sage Intacct, NetSuite, Business Central, Odoo · priority: common
  · spine: JournalEntry.reversal_of FK to self (nullable) · buildable now

- **Journal Approval Workflow** — multi-level approval: Draft → Pending Approval → Posted; approver roles gate
  posting · seen in: Sage Intacct, NetSuite, Business Central · priority: common
  · spine: JournalEntry.status choices + approver FK to User · buildable now

- **Fiscal Periods** — tenant-defined accounting periods (month/quarter/year) with open/closed status; posting
  is blocked when a period is closed · seen in: all 10 products · priority: table-stakes
  · spine: new table FiscalPeriod (accounting-owned): tenant, name, start_date, end_date, status (open/closed/locked)
  · buildable now

- **Period Close Procedure** — month-end checklist: lock AP, lock AR, lock payroll, run period-end journals,
  generate trial balance, then close period; a "close" stamp is applied to the FiscalPeriod row · seen in:
  Sage Intacct, NetSuite, Business Central, SAP Business One, Odoo · priority: common
  · spine: FiscalPeriod.status transitions + optional PeriodCloseChecklist table · buildable now

- **Account Reconciliation / Trial Balance** — report listing every GLAccount with debit/credit totals and
  computed balance; proves debits == credits globally · seen in: all 10 products · priority: table-stakes
  · spine: aggregate over JournalLine (no new table) · buildable now

- **Multi-currency GL** — transactions recorded in transaction currency; system converts to functional (tenant)
  currency via ExchangeRate; unrealized FX gain/loss computed at period end · seen in: Xero, Sage Intacct,
  NetSuite, Business Central, Odoo, Zoho Books · priority: common
  · spine: new tables Currency + ExchangeRate (accounting-owned); JournalLine.currency_code + amount_foreign
  · buildable now (basic); period-end FX revaluation buildable now

- **GL Dimensions / Cost Centers** — tag JournalLines with optional OrgUnit (department/cost center) for
  departmental P&L without exploding the CoA · seen in: Sage Intacct (multi-dimensional), Business Central
  (8 dimensions), NetSuite (segments) · priority: common
  · spine: JournalLine.org_unit FK → core.OrgUnit (reuse existing) · buildable now

- **Immutable Audit Trail** — every posted JE is append-only; voiding creates a reversing entry; full
  who/when/what log · seen in: all 10 products · priority: table-stakes
  · spine: reuse core.AuditLog (log JournalEntry create/status-change events) · buildable now

- **Allocation Rules** — automatic cost-distribution engine: splits an expense JournalLine across departments
  by fixed % or proportional rule · seen in: Sage Intacct, NetSuite, Business Central · priority: differentiator
  · spine: new table AllocationRule (accounting-owned) · deferred (later pass)

---

### 2.3 Accounts Payable (AP)

- **Vendor Management via Party spine** — vendor profiles (payment terms, credit terms, tax ID, preferred
  payment method) stored as Party + PartyRole('vendor'); accounting extensions hang off Party
  · seen in: all 10 products · priority: table-stakes
  · spine: reuse core.Party + core.PartyRole; new accounting-owned VendorProfile for AP-specific fields
  (payment_terms, default_expense_account, currency) · buildable now

- **Vendor Bill (AP Invoice)** — bill header (vendor Party, bill number, issue date, due date, status) + line
  items (description, amount, GL account, tax); status: draft → pending_approval → approved → paid
  · seen in: all 10 products · priority: table-stakes
  · spine: new table Bill (accounting-owned) + BillLine; posts to JournalEntry on approval · buildable now

- **Bill Approval Routing** — multi-level approval gates before a bill can be paid; approval threshold
  ($X triggers higher approver) · seen in: Sage Intacct, NetSuite, Business Central, Odoo · priority: common
  · spine: Bill.status + approver FK to User · buildable now

- **Payment Processing (outbound)** — record a payment against a bill (or partial); payment method choices
  (check, ACH, wire, bank transfer); links to BankAccount · seen in: all 10 products · priority: table-stakes
  · spine: new table Payment (direction='out', accounting-owned) + PaymentAllocation → Bill · buildable now

- **AP Aging Report** — outstanding bills bucketed by age: current / 1–30 / 31–60 / 61–90 / 90+ days; per
  vendor totals · seen in: all 10 products · priority: table-stakes
  · spine: aggregate over Bill (no new table; filter by due_date vs today) · buildable now

- **Payment Terms** — configurable: Net 15, Net 30, Net 60, 2/10 Net 30 (early-pay discount); auto-calculates
  due_date on bill entry · seen in: all 10 products · priority: table-stakes
  · spine: new table PaymentTerm (accounting-owned): name, days, discount_pct, discount_days · buildable now

- **Early Payment Discount Capture** — flag bills eligible for discount (paid within discount window); compute
  discount amount on payment · seen in: Sage Intacct, NetSuite, QuickBooks, Odoo · priority: common
  · spine: PaymentAllocation.discount_taken DecimalField · buildable now

- **Bill Capture / OCR** — extract vendor, amount, date from scanned PDF; pre-fill bill form · seen in: Zoho
  Books (Hubdoc), Sage Intacct, Xero, Business Central (Copilot) · priority: differentiator
  · spine: core.Document (existing) attaches to Bill · integration/later (external OCR / AI service)

- **Vendor Payment Scheduling** — cash-flow-optimized queue of upcoming payments; shows projected bank balance
  after each payment · seen in: NetSuite, Business Central, Sage Intacct · priority: differentiator
  · spine: reads Payment.paid_on + BankAccount balance · buildable now (simple scheduled list)

- **1099 / W-9 Tracking** — flag vendors as 1099-eligible; aggregate annual payments for tax form generation
  · seen in: QuickBooks, Zoho Books, Wave · priority: common (US-specific)
  · spine: VendorProfile.is_1099 BooleanField · buildable now (flag only; form generation deferred)

---

### 2.4 Accounts Receivable (AR)

- **Customer Management via Party spine** — customer credit limit, payment terms, AR account; Party +
  PartyRole('customer') + CustomerProfile for AR extensions · seen in: all 10 products · priority: table-stakes
  · spine: reuse core.Party + PartyRole; new CustomerProfile (accounting-owned): credit_limit, payment_terms,
  ar_account FK GLAccount · buildable now

- **Customer Invoice** — invoice header (customer Party, invoice number, issue date, due date, status) + lines
  (description, qty, unit_price, tax_code); status: draft → sent → partial → paid → void
  · seen in: all 10 products · priority: table-stakes
  · spine: new table Invoice (accounting-owned) + InvoiceLine; posts to JournalEntry on approval
  · buildable now

- **Invoice Numbering** — auto-sequential tenant-scoped numbers (INV-00001) with collision-safe retry (pattern
  from tenants module SubscriptionInvoice) · seen in: all 10 products · priority: table-stakes
  · spine: Invoice.number CharField; use next_number() utility already in core · buildable now

- **Recurring Invoicing** — template invoice that auto-generates on a schedule (weekly, monthly, quarterly);
  used for subscriptions/retainers · seen in: Xero, Zoho Books, FreshBooks, QuickBooks, Sage Intacct, Odoo
  · priority: common · spine: new table RecurringInvoice (accounting-owned) · buildable now

- **Payment Collection (inbound)** — record a customer payment against one or more invoices (full or partial
  cash application); payment method: bank transfer, check, card, online · seen in: all 10 products
  · priority: table-stakes · spine: new table Payment (direction='in') + PaymentAllocation → Invoice
  · buildable now

- **Cash Application / Matching** — auto-match incoming bank transactions to open invoices by amount/reference;
  flag exceptions · seen in: Sage Intacct, NetSuite, Odoo (95% auto-match), Business Central (Copilot)
  · priority: common · spine: BankTransaction → PaymentAllocation engine · buildable now (manual first;
  auto-match later)

- **Credit Limit Enforcement** — warn or block new invoices when a customer's outstanding AR exceeds their
  credit_limit · seen in: Sage Intacct, NetSuite, Business Central, Zoho Books · priority: common
  · spine: CustomerProfile.credit_limit vs sum of open Invoice.total · buildable now (warning gate in view)

- **AR Aging Analysis** — outstanding invoices bucketed by: current / 1–30 / 31–60 / 61–90 / 90+ days; per
  customer and tenant total · seen in: all 10 products · priority: table-stakes
  · spine: aggregate over Invoice (no new table) · buildable now

- **Dunning / Collections** — automated payment reminder sequence: send email at N days overdue (1st, 2nd,
  final notice); configurable escalation · seen in: Sage Intacct (collections module), Xero, QuickBooks, Zoho
  Books, Odoo · priority: common · spine: new table DunningRule (accounting-owned) + track via core.Activity
  (kind='email') · buildable now (rule store + manual trigger; auto-send deferred)

- **Credit Notes / Refunds** — issue a negative invoice (credit memo) to reverse a billed amount; applies
  against open receivables · seen in: all 10 products · priority: table-stakes
  · spine: Invoice.kind='credit_note' (same table, negative lines) · buildable now

- **Customer Portal** — self-service web page for customers to view outstanding invoices and make online
  payments · seen in: Xero, QuickBooks, Zoho Books, FreshBooks · priority: differentiator
  · integration/later (public-facing portal, payment gateway)

---

### 2.5 Cash Management

- **Bank Account Management** — tenant-scoped bank accounts: name, account number (masked), bank name, currency,
  GL account linkage, opening balance · seen in: all 10 products · priority: table-stakes
  · spine: new table BankAccount (accounting-owned); FK to GLAccount and Currency · buildable now

- **Bank Transaction Log** — imported or manually entered bank transactions: date, description, amount, direction
  (credit/debit), status (unmatched / matched / reconciled) · seen in: all 10 products · priority: table-stakes
  · spine: new table BankTransaction (accounting-owned): bank_account FK, date, amount, direction, description,
  status · buildable now

- **Bank Statement Import** — manual CSV/OFX/QIF file import into BankTransaction; foundation for bank feeds
  · seen in: Sage Intacct, Odoo, Zoho Books, Wave, Xero · priority: table-stakes
  · spine: BankTransaction (same table); CSV import view · buildable now

- **Bank Feeds (Automated Import)** — real-time/daily transaction sync via Plaid/Yodlee/Open Banking APIs
  · seen in: QuickBooks, Xero, Xero (Hubdoc), Zoho Books, Wave, FreshBooks · priority: common
  · integration/later (Plaid/Open Banking external API; model is same BankTransaction)

- **Reconciliation Engine** — match BankTransaction rows to JournalLines (or Payment records); mark matched
  pairs reconciled; flag unmatched for manual review; show reconciliation difference · seen in: all 10 products
  · priority: table-stakes · spine: new table ReconciliationMatch (accounting-owned):
  bank_transaction FK + journal_line FK (or payment FK) + status · buildable now

- **Auto-Match Rules** — user-defined rules (match by amount + description keyword, or payee name) that run
  automatically during import to suggest matches · seen in: Xero, QuickBooks, Odoo (95%+ auto-match), Business
  Central (Copilot), Zoho Books · priority: common
  · spine: new table BankMatchRule (accounting-owned): keyword, amount_range, target_account FK, direction
  · buildable now

- **Bank Reconciliation Statement** — period-end report comparing GL cash account balance vs bank statement
  balance, listing outstanding deposits/checks · seen in: all 10 products · priority: table-stakes
  · spine: aggregate over BankTransaction + ReconciliationMatch (no new table) · buildable now

- **Cash Position Dashboard** — real-time view of all bank account balances (GL balance + unreconciled
  transactions) summed across accounts · seen in: Sage Intacct, NetSuite, Business Central, Zoho Books
  · priority: common · spine: aggregate over BankAccount + BankTransaction · buildable now

- **Inter-company / Inter-account Transfers** — record a fund movement between two tenant BankAccounts;
  posts offsetting JournalLines to both accounts · seen in: Sage Intacct, NetSuite, Business Central
  · priority: common · spine: a two-line JournalEntry + two BankTransaction rows · buildable now

- **Bank Fee Analysis** — categorize service charges and interest credited from BankTransaction; auto-post to
  configured GL accounts · seen in: Sage Intacct, NetSuite · priority: differentiator
  · spine: BankMatchRule can post to a fee GLAccount; no new table · buildable now (simple rule)

- **Treasury / Cash Forecasting** — 30/90-day projected cash balance using open invoices, scheduled bills,
  and recurring transactions · seen in: Business Central (Copilot), NetSuite, Sage Intacct · priority: differentiator
  · spine: reads Invoice, Bill, Payment, BankTransaction · buildable now (simple sum projection); AI version later

---

## Recommended build scope (this pass — 12 models)

This pass covers sub-modules 2.1–2.5 (dashboard is computed, not a new model). The 12 accounting-owned models
below constitute the GL spine + AP + AR + Cash Management; they are the foundation every later NavERP module
(Inventory, Procurement, Sales, Assets) will FK into.

### Double-entry invariants to enforce at the database / save() layer

1. Every JournalEntry must have sum(JournalLine.debit) == sum(JournalLine.credit) before it can be posted.
2. JournalEntry and JournalLine rows are append-only once status == 'posted'; corrections are made only by
   creating a reversal entry (reversal_of FK self).
3. Account balances and AR/AP totals are NEVER stored as mutable fields — they are always derived by
   aggregating over JournalLine (or Invoice/Payment) rows.
4. Posting to a closed FiscalPeriod is blocked at the view/save() layer (check period.status before
   JournalEntry.save()).

---

### Model 1: Currency (accounting-owned global master)

**Sub-module:** 2.2 GL (foundation for multi-currency)
**Purpose:** ISO 4217 currency codes shared across all tenant financial data.
**Key fields:** code (ISO, unique, e.g. "USD"), name, symbol, is_active.
**Reuses spine:** none (global, not tenant-scoped — same as intended ERD). Currency rows are shared.
**Justifies features:** Multi-currency GL, multi-currency invoicing, bank account currencies.

---

### Model 2: ExchangeRate (accounting-owned)

**Sub-module:** 2.2 GL
**Purpose:** Daily spot rates for each currency against the tenant's functional currency.
**Key fields:** tenant FK, currency FK (to Currency), rate_date, rate (DecimalField), source ('manual'/'feed').
**Reuses spine:** core.Tenant (via tenant FK).
**Justifies features:** Multi-currency GL (FX gain/loss), multi-currency invoicing, cash management.

---

### Model 3: GLAccount (accounting-owned)

**Sub-module:** 2.2 GL — the core of the CoA
**Purpose:** Chart of Accounts — one row per account in the tenant's hierarchical account tree.
**Key fields:** tenant FK, code (unique per tenant), name, account_type
('asset'/'liability'/'equity'/'income'/'expense'), parent FK (self-referential, nullable), is_active,
description, normal_balance ('debit'/'credit' derived from type).
**Reuses spine:** core.Tenant.
**Justifies features:** Chart of Accounts, GL Dimensions via OrgUnit, tax account linkage, asset capitalization.
**Note:** Balances derived by aggregating JournalLine; never stored on GLAccount.

---

### Model 4: FiscalPeriod (accounting-owned)

**Sub-module:** 2.2 GL — period control
**Purpose:** Tenant-defined accounting periods; controls whether posting is allowed.
**Key fields:** tenant FK, name (e.g. "Jan 2025"), period_type ('month'/'quarter'/'year'), start_date,
end_date, status ('open'/'closed'/'locked'), closed_by FK (User, nullable), closed_at (DateTimeField, nullable).
**Reuses spine:** core.Tenant.
**Justifies features:** Period Close, posting block, month-end checklist (status transitions), year-end close.

---

### Model 5: JournalEntry (accounting-owned ledger header)

**Sub-module:** 2.2 GL — the primary financial ledger
**Purpose:** One header per double-entry posting event (manual JE, invoice posting, payment, bank fees).
**Key fields:** tenant FK, entry_number (auto, unique per tenant, e.g. "JE-00001"), entry_type
('manual'/'invoice'/'payment'/'bank'/'recurring'/'reversal'), status ('draft'/'pending_approval'/'posted'/'void'),
fiscal_period FK (FiscalPeriod), entry_date, description, reference (external doc ref), reversal_of FK (self,
nullable), created_by FK (User), approved_by FK (User, nullable), posted_at (DateTimeField, nullable).
**Reuses spine:** core.Tenant, core.AuditLog (log status transitions), core.OrgUnit (dimension on lines).
**Invariants:** status transitions are one-way (draft→pending→posted or →void); once posted, no field
edits — only reversal entry allowed.
**Justifies features:** Manual JEs, journal approval workflow, recurring JEs (template), reversal entries,
audit trail.

---

### Model 6: JournalLine (accounting-owned ledger line)

**Sub-module:** 2.2 GL — the double-entry lines
**Purpose:** Each debit or credit arm of a JournalEntry.
**Key fields:** entry FK (JournalEntry), gl_account FK (GLAccount), debit (DecimalField, default 0),
credit (DecimalField, default 0), description, party FK (core.Party, nullable — subledger link),
org_unit FK (core.OrgUnit, nullable — cost-center dimension), currency FK (Currency, nullable),
amount_foreign (DecimalField, nullable — amount in transaction currency), exchange_rate (DecimalField, nullable).
**Reuses spine:** core.Party (subledger link to customer/vendor), core.OrgUnit (dimension).
**Invariants:** debit XOR credit must be non-zero (not both); sum over entry must balance.
**Justifies features:** Double-entry GL, multi-currency, GL dimensions/cost centers, subledger drill-down.

---

### Model 7: PaymentTerm (accounting-owned master)

**Sub-module:** 2.3 AP + 2.4 AR
**Purpose:** Reusable payment term configurations; applied to bills and invoices.
**Key fields:** tenant FK, name (e.g. "Net 30", "2/10 Net 30"), days_due, discount_pct (DecimalField, default 0),
discount_days (int, default 0), is_active.
**Reuses spine:** core.Tenant.
**Justifies features:** Payment terms on vendor bills and customer invoices, early-payment discount capture.

---

### Model 8: VendorProfile / CustomerProfile — two thin extension tables

**Sub-module:** 2.3 AP (VendorProfile) + 2.4 AR (CustomerProfile)
**Purpose:** Accounting-specific extensions on core.Party for vendor/customer financial settings.
**VendorProfile key fields:** party FK (core.Party, OneToOne), tenant FK, payment_terms FK (PaymentTerm),
default_expense_account FK (GLAccount, nullable), currency FK (Currency, nullable), is_1099 BooleanField,
notes.
**CustomerProfile key fields:** party FK (core.Party, OneToOne), tenant FK, payment_terms FK, credit_limit
(DecimalField), ar_account FK (GLAccount, nullable), currency FK (Currency, nullable), credit_on_hold
BooleanField.
**Reuses spine:** core.Party (PartyRole 'vendor' / 'customer' already exists — these tables extend, not replace).
**Justifies features:** Vendor management (payment terms, 1099 flag), customer credit limits, credit hold.

---

### Model 9: Invoice (AR invoice — accounting-owned)

**Sub-module:** 2.4 AR
**Purpose:** Customer-facing invoice (AR); also used as credit_note (kind field).
**Key fields:** tenant FK, kind ('invoice'/'credit_note'), number (auto, e.g. "INV-00001"),
party FK (core.Party — the customer), payment_terms FK (PaymentTerm, nullable), issue_date, due_date,
status ('draft'/'sent'/'partial'/'paid'/'void'), currency FK, journal_entry FK (JournalEntry, nullable —
set when posted), subtotal, tax_total, total (computed; also stored for display performance).
**Reuses spine:** core.Party (customer), core.AuditLog.
**Justifies features:** Customer invoice, invoice numbering, credit notes, AR aging input.

---

### Model 10: InvoiceLine (AR)

**Sub-module:** 2.4 AR
**Purpose:** Line items on a customer invoice.
**Key fields:** invoice FK, description, quantity (DecimalField), unit_price, tax_rate_pct (DecimalField,
default 0), line_total (computed), gl_account FK (GLAccount, nullable — income account).
**Reuses spine:** none new.
**Justifies features:** Per-line revenue GL coding, tax per line, credit note line reversals.

---

### Model 11: Bill (AP bill — accounting-owned)

**Sub-module:** 2.3 AP
**Purpose:** Vendor bill (AP); mirrors Invoice on the payables side.
**Key fields:** tenant FK, number (auto, e.g. "BILL-00001"), party FK (core.Party — the vendor),
payment_terms FK (PaymentTerm, nullable), bill_date, due_date, status
('draft'/'pending_approval'/'approved'/'partial'/'paid'/'void'), currency FK, journal_entry FK (JournalEntry,
nullable), subtotal, tax_total, total, approved_by FK (User, nullable), document FK (core.Document, nullable
— scanned bill attachment).
**Reuses spine:** core.Party (vendor), core.Document (attachment), core.AuditLog.
**Justifies features:** Vendor bill, bill approval routing, 3-way match stub (document attachment).

---

### Model 12: BillLine (AP)

**Sub-module:** 2.3 AP
**Purpose:** Line items on a vendor bill.
**Key fields:** bill FK, description, quantity, unit_price, tax_rate_pct, line_total, gl_account FK
(GLAccount — expense account).
**Reuses spine:** none new.
**Justifies features:** Per-line expense GL coding, early-payment discount line.

---

### Model 13: Payment (unified inbound + outbound — accounting-owned)

**Sub-module:** 2.3 AP + 2.4 AR
**Purpose:** A single payment record for both cash receipts (AR) and disbursements (AP).
**Key fields:** tenant FK, payment_number (auto, e.g. "PAY-00001"), direction ('in'/'out'),
party FK (core.Party — customer or vendor), bank_account FK (BankAccount), payment_method
('bank_transfer'/'check'/'cash'/'card'/'ach'/'wire'), payment_date, amount, currency FK,
status ('draft'/'confirmed'/'void'), journal_entry FK (JournalEntry, nullable), notes.
**Reuses spine:** core.Party, core.AuditLog.
**Justifies features:** AP payment processing, AR payment collection, bank balance impact.

---

### Model 14: PaymentAllocation (cash application — accounting-owned)

**Sub-module:** 2.3 AP + 2.4 AR
**Purpose:** Links a Payment to one or more Invoice/Bill rows; supports partial allocation and early-pay discounts.
**Key fields:** payment FK, invoice FK (nullable), bill FK (nullable), allocated_amount,
discount_taken (DecimalField, default 0).
**Reuses spine:** none new.
**Justifies features:** Cash application (AR), payment-to-bill matching (AP), early-payment discount capture,
multi-invoice payment splits.

---

### Model 15: BankAccount (accounting-owned)

**Sub-module:** 2.5 Cash Management
**Purpose:** Tenant bank accounts linked to a GL cash account.
**Key fields:** tenant FK, name, account_number_last4, bank_name, currency FK, gl_account FK (GLAccount),
opening_balance (DecimalField), opening_balance_date, is_active.
**Reuses spine:** core.Tenant.
**Justifies features:** Bank account management, cash position dashboard, reconciliation engine anchor.

---

### Model 16: BankTransaction (accounting-owned)

**Sub-module:** 2.5 Cash Management
**Purpose:** Individual bank statement line — either imported from CSV/OFX or from a bank feed.
**Key fields:** tenant FK, bank_account FK, transaction_date, description, amount, direction
('credit'/'debit'), source ('manual'/'csv_import'/'bank_feed'), status
('unmatched'/'matched'/'reconciled'/'excluded'), external_ref (bank's own transaction id).
**Reuses spine:** core.Tenant.
**Justifies features:** Bank statement import, bank feeds (same model), reconciliation engine input.

---

### Model 17: ReconciliationMatch (accounting-owned)

**Sub-module:** 2.5 Cash Management
**Purpose:** Pair of (BankTransaction, JournalLine or Payment) that have been matched during reconciliation.
**Key fields:** tenant FK, bank_transaction FK (BankTransaction), payment FK (Payment, nullable),
journal_line FK (JournalLine, nullable), matched_by FK (User), matched_at, is_confirmed BooleanField.
**Reuses spine:** core.Tenant.
**Justifies features:** Reconciliation engine, auto-match rules output, bank reconciliation statement.

---

## Deferred (later passes / integrations)

- **Bank Feeds via Plaid / Yodlee / Open Banking** — external API integration; the BankTransaction model is
  already designed to receive feed data (source='bank_feed'), but the API connector and webhook are a separate
  integration pass.

- **OCR / AI Bill Capture** — scanning vendor invoices to pre-fill Bill form; requires an external OCR service
  (Veryfi, AWS Textract, etc.); the core.Document attachment already supports file upload.

- **AI Cash Flow Forecasting** — ML projection of 30/90-day liquidity; reads Invoice + Bill + BankTransaction
  patterns; deferred to an analytics/BI pass.

- **Customer Portal (self-service invoice view/pay)** — a public-facing portal with a payment gateway link;
  requires payment processor integration (Stripe, PayPal) and a separate auth/token flow.

- **Allocation Rules Engine (departmental cost splits)** — automatic percentage or proportional splits of
  expense JournalLines across OrgUnits; useful for shared-cost allocation; deferred (complex rule engine).

- **1099 / W-9 Form Generation** — storing the is_1099 flag and payment totals is done now; generating
  compliant PDF 1099-MISC / 1099-NEC forms requires a US-localization pass.

- **Fixed Assets (sub-module 2.6)** — Asset Register, depreciation engine, disposals; scoped to a future
  NavERP Module 11 (Assets) build; GLAccount already provides the capitalization account linkage.

- **Revenue Recognition (ASC 606 / IFRS 15)** — deferred revenue schedules, performance obligation tracking;
  belongs to a later Accounting extension pass for SaaS/subscription businesses.

- **Custom Report Builder** — drag-and-drop financial report designer; deferred to BI/reporting module (10).

- **Recurring Journal Entry auto-posting scheduler** — storing RecurringJournal templates is done now;
  the Celery/cron job that actually posts them on schedule is deferred to a task-queue integration pass.

- **Dunning auto-send** — DunningRule storage is in scope; automatically emailing customers requires an email
  integration (SMTP / SendGrid) — deferred to the notifications pass.

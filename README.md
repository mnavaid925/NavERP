<div align="center">

# NavERP

**A multi-tenant Enterprise Resource Planning (ERP) platform**

Django 5.1 Â· Tailwind CSS Â· HTMX Â· Chart.js Â· Lucide Â· MySQL/MariaDB (XAMPP)

Clean, fully responsive, blue-and-white dashboard with light/dark modes and configurable layouts.

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [Why NavERP is one ERP, not fourteen apps](#why-naverp-is-one-erp-not-fourteen-apps)
3. [What's implemented today](#whats-implemented-today)
4. [Technology stack](#technology-stack)
5. [Architecture](#architecture)
6. [Prerequisites](#prerequisites)
7. [Installation & setup](#installation--setup)
8. [Environment variables](#environment-variables)
9. [Seed data & demo logins](#seed-data--demo-logins)
10. [Running the app](#running-the-app)
11. [URL / route map](#url--route-map)
12. [Stripe billing (test mode)](#stripe-billing-test-mode)
13. [Testing](#testing)
14. [Project structure](#project-structure)
15. [Design system & layout variants](#design-system--layout-variants)
16. [Data model](#data-model)
17. [Security posture](#security-posture)
18. [Production hardening checklist](#production-hardening-checklist)
19. [Module roadmap (0â€“13)](#module-roadmap-0-13)
20. [Development conventions](#development-conventions)
21. [Troubleshooting](#troubleshooting)
22. [License](#license)

---

## Overview

NavERP is a SaaS-style ERP where many independent organizations ("tenants") share one Django deployment and
one database, with strict per-tenant data isolation. It is built **module by module** on a single shared data
model so that customers, vendors, employees, items, money, and stock are never duplicated across modules.

This repository currently delivers the **Module 0 foundation** (System Admin & Security â€”
`core`/`accounts`/`tenants`/`dashboard`) plus three domain modules built on it: **Module 1 â€” CRM** (1.1â€“1.12),
**Module 2 â€” Accounting & Finance** (2.1â€“2.15), **Module 3 â€” HRM** (employees, org structure, onboarding,
offboarding, recruiting, attendance, leave, time tracking, holidays, payroll, statutory/tax, and performance
management â€” goals, reviews, continuous feedback, and performance improvement â€” 38 of 41 sub-modules), and
**Module 4 â€” Supply Chain Management** at 18 of 19 sub-modules (4.1 Procurement: requisition â†’ RFQ â†’ purchase order â†’ goods receipt with
three-way match; 4.2 Supplier Relationship Management: onboarding, signal-derived scorecards, contracts, catalogs,
risk; 4.3 Inventory Management: the append-only stock-move ledger with derived on-hand, transfers, adjustments,
reorder automation and FIFO/LIFO/WAC valuation; 4.4 Warehouse Management: putaway, wave/batch/zone picking,
cycle counting and yard; 4.5 Order Management: order capture, credit/fraud validation, soft allocation
and backorders; 4.6 Transportation Management: carrier master + rate cards + derived on-time scorecard, loads with
route stops and cube utilization, shipments with an append-only tracking-event log and POD, and freight audit handing
off a draft accounting bill; 4.7 Demand Planning &amp; Forecasting: statistical forecasting over derived sales history,
seasonal/promotional index curves, demand sensing, consensus planning and a service-level safety-stock calculator;
4.8 Manufacturing / Production: versioned bills of materials with multi-level explosion, work centres with derived
capacity and OEE, the work-order lifecycle posting component consumption and finished-goods production through the
same append-only stock ledger, an MRP netting report and an infinite-capacity schedule board;
4.9 Quality Management: reusable inspection plans, inspections at the receipt/in-process/shipment trigger points with
snapshotted results, non-conformance reports with MRB dispositions, CAPA with effectiveness verification, audits whose
findings are NCRs, and generated certificates of analysis;
4.10 Returns Management: RMAs with an eligibility verdict snapshotted at approval, a receiving bench where the
disposition decision is the only thing that touches stock, credit notes drafted into Accounting, warranty claims
against suppliers, and a customer return portal;
4.11 Supply Chain Analytics: a closed KPI registry with targets, captured snapshots and a derived alert inbox over
5 computed report pages;
4.12 Contract & Compliance Management: a standing-obligation register whose CLM obligations point back at 4.2's
contracts rather than duplicating them, import/export licences that decrement as documents are issued under them,
trade paperwork hung off 4.6's shipments with HS codes snapshotted at issue, supplier ESG scorecards, and a
GLEC/ISO-14083 freight-emissions estimate that reports its own coverage gaps instead of a confident zero;
4.13 Asset Management: the operational asset spine â€” `scm.Asset` is the `Asset` anchor the ERD had always
described and nothing had ever built, so Module 11 extends it rather than duplicating it. Preventive-maintenance
plans carry Oracle's four trigger methods (calendar, meter, combined, condition) and roll their schedule on
completion rather than on generation, so a cancelled job never consumes a cycle and a floating plan measures from
the work that actually happened. One `MaintenanceWorkOrder` table covers requests, PM jobs and breakdowns â€”
splitting them would fork every MTTR and downtime query â€” with Maximo's problem/cause/remedy failure codes kept
as a closed vocabulary so "which cause costs us the most downtime" is answerable with a GROUP BY and no sensor
stack. MTBF, MTTR and availability return **None, never 0**, on a zero denominator, because an MTBF of 0h reads as
"fails constantly", the exact opposite of an asset that has never failed. Spare Parts Inventory is a computed view
of 4.3's one item master â€” there is no second parts catalogue â€” and issuing parts is the sub-module's only
ledger write, posting a new `maintenance` `StockMove` type deliberately kept out of COGS (a spare fitted to a
machine is upkeep, not the cost of a good sold) and equally out of `issue` (which 4.7 reads as customer demand).
Asset Depreciation READS `accounting.FixedAsset`; SCM stores no depreciation figure and posts no journal entry;
4.14 Labor Management: engineered multi-determinant labour standards resolved most-specific-wins and answering
**None, never a zero standard** â€” an unmeasured job that reads as a failing one is worse than no measurement â€”
warehouse shift sessions whose productivity figures are every one derived, and booked activity intervals that
**snapshot** their standard at file time so re-timing it cannot rewrite last month; it declares no attendance table
(HRM owns attendance), no task table (4.4 owns tasks), and writes no stock move and no journal entry at all;
4.15 Cold Chain Management: monitors watching exactly one of a location, an asset or a shipment through typed FKs
rather than a generic relation, an append-only temperature log with no edit and no delete, and excursions whose
every measured column is written solely by the detector under a lock on the monitor row, with the breached limits
snapshotted onto the episode; mean kinetic temperature returns **None** rather than 0 on frozen ranges per
USP &lt;1079.2&gt;, and no temperature is ever coerced through a zero default â€” âˆ’18 Â°C is the normal operating point,
so a blank cell must not become a plausible 0 Â°C;
4.16 Customer Portal: a per-customer entitlement record that is deliberately **not a login** (users bind through
CRM's existing access model, since a second binding could disagree about *which party a user is* and whichever page
read it would decide whose orders that user saw), expiring/revocable/download-audited document shares whose
ownership is re-checked **in the download view** rather than only at the form, and order tracking that earns its
place by joining 4.5 to 4.6 in one row neither module's own list shows;
4.17 Third-Party Logistics (3PL): warehouse-as-a-service billing â€” client configuration on `core.Party` rather than
a second company table, versioned rate cards over a 14-value charge basis, and a reviewable billing worksheet whose
quantities are **derived** from receipts, picks, shipments and the ledger before being approved into a **draft**
invoice; charge bases that are priceable but not measurable today write `needs_manual_quantity` and name the missing
measurement instead of guessing a conversion factor;
4.18 Finance & Accounting Integration: three of its five bullets are **read-only computed registers rather than
tables**, because what we owe and what we are owed already exist as pointers into `apps/accounting` from six shipped
models â€” an AP, AR or budget table here would be a second copy of the same money that drifts the first time
Accounting voids something. The one genuinely new capability is **landed cost**: a voucher over a goods receipt
whose typed charges (freight, duty, brokerage, insurance, drayage, port feesâ€¦) are spread across the receipt's
inbound stock moves by value, quantity, weight, volume or equal share as an **additive layer over the append-only
ledger** â€” it never edits a move, it rolls `Item.average_cost`, and re-allocating reverses its own prior roll first
so the button is safe to press twice. Alongside it sits an effective-dated customs-duty master keyed by HS code Ã—
country of origin, **snapshotted onto the charge** so a re-rate next quarter cannot rewrite what a shipment cleared
customs at. `draft_bill()` drafts an `accounting.Bill` and stops â€” SCM posts no journal entry).
4.19 Integration & API Gateway: the last of Module 4, and the sub-module whose discipline is knowing what it must *not* build. Its five bullets compress into four models because ERP, e-commerce, IoT and EDI are one object under four labels â€” a configured connection to somebody else's system â€” so they share one `IntegrationEndpoint` discriminated by category, each still reachable through its own category-pinned route so the EDI person lands on the trading-partner register rather than a mixed list of RFID readers and Shopify stores. **Nothing here makes a network call**: there is no HTTP client anywhere in the sub-module, and a test asserts that absence, so the endpoints, credentials, retry backoff and delivery attempts are configuration and state a human reads and acts on. Credentials are stored as prefix + SHA-256 hash â€” correct *here* precisely because no transport exists to need the plaintext back, and documented as such, since hashing is emphatically not how one stores a key that must later sign or authenticate; a rotated secret is revealed exactly once from a pop-once session key rather than flashed through the messages framework into the session store. The partner's EDI interchange identity stays on 4.17's client master and is read through the link, and a value typed where it does not belong is **refused rather than silently dropped**, because a field the system quietly ignores is worse than an error â€” the user leaves believing it applied.
The remaining functional modules (5â€“13) are planned and scaffolded against the same core. The suite stands at **17,809 passing tests**.

- [`NavERP.md`](NavERP.md) â€” the master catalog of all modules (0â€“13) and their sub-modules.
- [`NavERP-ERD.md`](NavERP-ERD.md) â€” the unified core data model (the `Party` + two-ledger spine every module reuses).

---

## Why NavERP is one ERP, not fourteen apps

Three design ideas hold the whole platform together:

1. **The Party model.** `Party` + `PartyRole` mean there is **one record per real-world person or organization**.
   *Customer, vendor, supplier, employee, lead, contact, partner* are **roles** on a party, not separate tables.
   This collapses the customer/vendor/employee duplication that otherwise spreads across CRM, Accounting, HR,
   Procurement, and Sales.

2. **Two universal ledgers.** Every financial effect posts to `JournalEntry`/`JournalLine` (append-only) â€” **built
   and owned by the Accounting module (Module 2)** â€” and every inventory effect will post to `StockMove` (arrives
   with the Inventory module). Account balances and on-hand quantities are **derived** by aggregation, never stored
   as editable fields â€” that consistency is what makes it an ERP.

3. **Shared cross-module anchors.** A small set of backbone entities (`OrgUnit`, `Employment`, `Activity`,
   `Document`, `AuditLog`, and later `Project`, `Asset`, `WorkOrder`, `Contract`) are read/written by more than
   one module. Each module adds only its **own** domain tables on top of this spine and FKs into it **by string**
   (e.g. `models.ForeignKey('core.Party', â€¦)`).

---

## What's implemented today

### `core` â€” platform & shared spine
- **Tenant** workspace model; **shared-DB multi-tenancy** via `TenantMiddleware` (sets `request.tenant` from the
  logged-in user) and a per-request **idle session timeout**.
- **Party model**: `Party`, `PartyRole`, `Address`, `ContactMethod`, `PartyRelationship`.
- **Org & people**: `OrgUnit` (company/branch/department/team/cost-center hierarchy), `Employment`.
- **Cross-cutting anchors**: `Activity` (generic task/call/email/meeting/note), `Document` (generic file
  attachment), `AuditLog` (append-only who/what/when/beforeâ†’after).
- Reusable, tenant-safe **CRUD helpers** (search, filter guards, windowed pagination, audit), a
  `tenant_admin_required` decorator, an audit-log writer, a per-tenant numbering helper, and the
  **`MODULE_CATALOG`** that drives the sidebar (modules 0â€“13 with live vs. "roadmap" links).

### `accounts` â€” identity, authentication & RBAC
- **Custom `User`** (login by **email or username**), nullable `tenant` (the superuser has none by design),
  `is_tenant_admin`, lifecycle `status` (active/suspended/archived), and a link to the person's `Party`.
- **RBAC**: `Role` (per-tenant) bundling a global `Permission` catalog.
- **`UserInvite`**: tokenized, 7-day-expiry invitations with accept/revoke.
- **Auth flows**: login, **self-service tenant registration** (creates the workspace + first admin),
  forgot/reset password (console email backend in dev), logout (POST-only).
- **Management UI**: users, roles, invites, and a self-service profile page. Admin actions are gated by
  `@tenant_admin_required`.

### `tenants` â€” Module 0.1: Tenant & Subscription Management
- **`Subscription`** (plan, status, billing cycle, seats, renewal) and **`SubscriptionInvoice`**
  (auto-numbered `SINV-#####`, race-safe).
- **Stripe (test mode)**: hosted Checkout + a **signature-verified, idempotent webhook**; degrades gracefully to
  a manual "mark as paid" flow when no keys are configured.
- **`BrandingSetting`**: per-tenant white-label logo + colors (hex-validated).
- **`EncryptionKey`**: secrets shown **exactly once** on create/rotate; only a prefix + SHA-256 hash are stored.
- **`HealthMetric`**: per-tenant resource/usage tracking.
- A first-run **onboarding wizard**.

### `dashboard`
- Tenant-scoped KPI overview: stat cards (users, parties, open invoices), party-role doughnut, activity-by-status
  bar chart, subscription status, tenant-health, and recent audit activity.

### `crm` â€” Module 1: Customer Relationship Management (1.1â€“1.12)
- **Leads** (`LEAD-#####`) with rating (hot/warm/cold), qualification status, scoring, and one-click
  **conversion** to a `core.Party` account + contact + an Opportunity (atomic).
- **1.2 Sales Force Automation** (recreated in detail â€” all three NavERP bullets live):
  - **Opportunities** (`OPP-#####`) â€” pipeline stages, amount/probability/weighted forecast, **forecast category**,
    **competitor**, **loss reason**, **territory**, system **stage-change** + **lost** timestamps; a **Kanban
    pipeline board** (per-stage totals + one-click stage advance) and **commission/credit splits** (revenue â‰¤100%).
  - **Product Catalog & Quoting** â€” a sales **Product** catalog (`PRD-#####`, margin), regional/tier **Price
    Books** (`PB-#####`), and a **Quote** builder (`QUO-#####`) with line items/discounts/tax, server-computed
    totals, a draftâ†’sentâ†’accepted lifecycle, and a printable (PDF-style) quote page.
  - **Forecasting** â€” **Sales Quotas** (`QTA-#####`) per rep/territory/period and a **forecast dashboard**
    (weighted pipeline by forecast category + quota-attainment progress).
- **1.3 Marketing Automation** (recreated in detail â€” all three NavERP bullets live):
  - **Campaigns** (`CAM-#####`) â€” type, **objective**, status, **parent-campaign** hierarchy, planned/actual budget,
    expected/actual revenue, ROI, **UTM** tags, and a member-funnel/response-rate roll-up on the detail page.
  - **Campaign Members** â€” target-list segmentation linking a campaign to a `core.Party`/`Lead` with per-recipient
    status tracking (targetedâ†’sentâ†’openedâ†’clickedâ†’responded/converted, or bounced/unsubscribed).
  - **Email Marketing** â€” **Email Templates** (`EMT-#####`, reusable HTML + merge vars) and **Email Campaigns**
    (`BLAST-#####`) with A/B variants, drip send-type, and open/click/bounce tracking; an **admin-gated Send**
    snapshots recipients and advances members.
  - **Landing Pages & Forms** (`LP-#####`) â€” an **admin-gated Publish** exposes a public, unguessable-token
    **web-to-lead** page (`/crm/p/<token>/`, no login, CSRF-protected, escaped body) whose **Form Submissions**
    route to an owner and convert one-click into a `Lead`.
- **1.4 Customer Service & Support** (recreated in detail â€” all three NavERP bullets live):
  - **Cases / Tickets** (`CASE-#####`) â€” priority + status workflow, an **SLA policy** (`SLA-#####`, per-priority
    first-response + resolution hour targets) that computes due dates with **breach badges**, a **conversation
    thread** (`CaseComment`: internal note vs customer-visible reply), **CSAT** rating, and an unguessable
    public **case-status tracking** page (`/crm/cases/track/<token>/`).
  - **Knowledge Base** (`KB-#####`) â€” hierarchical **categories** (`KBC-#####`), internal/external visibility,
    view counter, **helpful/not-helpful** voting, and a public article page (`/crm/kb/<token>/`).
  - **Customer Self-Service Portal** â€” **CustomerPortalAccess** (`CSP-#####`) grants a customer a login to view
    only their own cases, submit tickets, and reply (`/crm/portal/cases/`); admin-gated access grants.
- **1.5 Activity & Communication** (recreated in detail) â€” **Tasks** (`TASK-#####`, to-dos/calls/follow-ups with
  priority, due date, and **automated recurring tasks** that spawn the next occurrence on completion); **Calendar
  Events** (`EVT-#####`) with attendee **RSVPs**, a public **meeting-invite/RSVP link** + an **`.ics` calendar
  export** (`/crm/invite/<token>/`); and a unified **Communication Log** (`COM-#####`) for call logging
  (duration/outcome) and email/BCC sync across call/email/SMS/note/meeting channels.
- **Accounts & Contacts** are the shared **`core.Party`** identity (one record, many roles) enriched with CRM-owned
  one-to-one **`AccountProfile`** (industry, website, revenue, employees, parent company, address) and
  **`ContactProfile`** (job title, department, phone/mobile, employer account, address) extensions â€” **full CRUD**
  in CRM, no duplicate customer/contact tables. Deleting an account/contact removes the shared Party and is
  **tenant-admin-only** (cross-module impact).
- A CRM **overview** (analytics) page: stat cards (open leads, pipeline, weighted forecast, win rate, open
  cases/tasks, active campaigns) + pipeline-by-stage and leads-by-rating charts.

**Sub-module 1.6 â€” Analytics & Reporting** (recreated in detail, migration `0015`, 4 CRM-owned tables; all
metrics are read-only aggregations over existing CRM data, computed in `apps/crm/analytics.py`):
- **Dashboards** â€” saved, per-user **`AnalyticsDashboard`** (`DASH-#####`) holding **`DashboardWidget`** tiles
  that are **computed live on render**: KPI cards, gauges (with optional target), bar/line/pie/doughnut charts
  (Chart.js), and tables (top performers, campaign ROI) â€” 20 metrics over Opportunity/Case/Lead/Campaign/Task.
  Per-widget date-range + size, drag-free up/down reordering, and admin-gated `is_shared`/`is_default` flags.
- **Standard Reports** â€” saved **`AnalyticsReport`** (`RPT-#####`) in 4 canned types (sales activity, sales
  performance/top-performers, funnel drop-off, service resolution-time + CSAT) computed live with a chart +
  table + KPI summary, plus point-in-time **`ReportSnapshot`** runs frozen as JSON for period-over-period trends.

**Sub-modules 1.7â€“1.12** (extension pass, 27 CRM-owned tables, migrations `0005` + `0016`â€“`0024` for the 1.7/1.8/1.9/1.10/1.11 recreations):
- **1.7 Finance & Billing** *(recreated in detail â€” all three NavERP.md bullets now live, reusing the
  **Accounting ledger** per L29; draft hand-off)* â€” **Deal Invoices** (`DINV-#####`): one-click
  **quoteâ†’invoice conversion** that generates a draft `accounting.Invoice` (line items, per-line + quote-level
  discount, and tax carried so `invoice.total == quote.total`) and links it to the deal, with a deal-margin
  card; **Payment Receipts** (`RCPT-#####`): printable receipts over `accounting.Payment` allocations with
  payment-gateway metadata (Stripe/PayPal/Razorpay); **Expenses** (`EXP-#####`, + **`is_billable`** for true
  margin): deal/project cost logging with allowlisted receipt upload + owner **submit** / tenant-admin
  **approve/reject**.
- **1.8 Project & Delivery** *(recreated in detail â€” all three NavERP.md bullets now live)* â€” **Projects**
  (`PRJ-#####`, one-click **convert** from a won opportunity, derived **progress %** + overdue flag, a **Kanban
  board** with status-move), **Milestones** (`MS-#####`, sub-tasks); **Time Tracking** **Timesheets**
  (`TS-#####`, billable/non-billable, owner **submit** + tenant-admin **approve/reject** â€” `status` off the form
  to close a self-approve gap); and **Resource Allocation** â€” **`ResourceAllocation`** (`RA-#####`) capacity
  bookings feeding a **workload board** that flags overbooked vs. free capacity (planned vs. logged vs. capacity
  per person).
- **1.9 Document & Contract** *(recreated in detail â€” all three NavERP.md bullets now live)* â€” **E-Signatures**:
  **Contracts** (`CTR-#####`) with per-signer tracking + a **public token-based signing page**; **Document
  Generation**: **Doc Templates** (`TPL-#####`, merge-variable HTML) rendered into a contract via a one-click
  **Generate** action through an **isolated, escaping-only template engine** (no `include`/`extends`/`load`/`safe`
  â€” server-side template-injection-safe); **File Repository**: **`DocumentVersion`** (immutable contract revisions
  with body snapshot + allowlisted file uploads) and a **repository organized by account/deal** with version
  counts. Template authoring is tenant-admin-gated.
- **1.10 Automation & Workflow** *(recreated in detail â€” all three NavERP.md bullets now live)* â€” **Trigger-Based
  Actions**: **Workflow Rules** (`WFR-#####`, declarative trigger/condition/action JSON) now back a real, bounded
  **rule-execution engine** â€” an admin **Run** evaluates the conditions against the latest tenant records of the
  trigger entity (â‰¤50) through a field-name **allowlist** (only concrete non-relation columns â€” no method/property/
  FK/relation access, so a condition can't reach a token field or trigger a lazy query) and fires the actions
  (webhook delivery / approval creation / logged note), recording each fire to the append-only **Workflow Log**;
  **Approval Processes**: **Approval Requests** (`APR-#####`, admin approve/reject); **Webhooks** *(was a stub â†’
  workflow-rules)*: a real endpoint registry â€” **Webhooks** (`WH-#####`) with a **write-only HMAC signing secret**
  (PasswordInput, masked, never round-tripped) + validated custom headers, and an immutable **Webhook Delivery** log
  (HMAC-SHA256-signed JSON payloads; admin **Test**). Outbound HTTP is **recorded-and-signed only** (the real POST
  is deferred behind a documented SSRF guard â€” https-only, pin-resolved-IP, port 443, no redirects). Webhook config
  + rule authoring/run are tenant-admin-gated.
- **1.11 Customer Success** *(recreated in detail â€” all three NavERP.md bullets deepened)* â€” **Onboarding
  Pipelines**: **Onboarding Plans** (`CS-#####`, step checklists + progress + step edit) **plus reusable Onboarding
  Templates** (`OTPL-#####`, ordered steps with day-offsets, **applied in one click** to clone a fresh plan for a
  client; admin-authored); **Health Scoring**: **Health Scores** (`HS-#####`, 0â€“100 from tickets/NPS/tasks/engagement
  with configurable, validated weights) now keep an append-only **Health Score History** trend and **auto-raise a
  guarded churn-risk task** when an account turns Red, with an admin **Recompute all**; **Surveys & Feedback**:
  **Surveys** (`NPS-#####`, NPS/CSAT/CES) with **type-aware** classification + a type-aware public respond page
  (NPS 0â€“10 / CSAT 1â€“5 / CES 1â€“7), an admin **Send** action, and an **NPS analytics** page (NPS = %promoters âˆ’
  %detractors, promoter/passive/detractor split, CSAT/CES averages).
- **1.12 Inventory & Vendor** â€” CRM-owned **Product Stock** (`STK-#####`, low-stock alerts), **Purchase Orders**
  (`PO-#####`) with line items + receive-to-stock, and **Partner Portal Access** (`PRT-#####`) with a
  partner-facing read-only portal (orders + stock).
  > 1.12 uses CRM-owned PurchaseOrder/ProductStock because the Inventory/Procurement spine masters
  > (`core.Item`/`StockMove`/`PurchaseOrder`) and the Accounting ledger aren't built yet; they migrate onto
  > the spine when those modules land.

Full CRUD, tenant isolation, working filters, an idempotent `seed_crm`, and a **2,114-test** suite.

### Module 2 â€” Accounting & Finance (`accounting`) â€” 2.1â€“2.15

The first domain module to **own the GL ledger spine** (no core ledger existed â€” see lesson L28). Double-entry
throughout: journal entries post only when debits equal credits, posted entries are immutable (corrected via a
reversal), account balances are always *derived* from posted lines, and posting into a closed period is blocked.

- **2.1 Dashboard** â€” cash-position / AR / AP KPI cards, overdue alert centre, 6-week net-cash Chart.js trend, quick actions.
- **2.2 General Ledger** â€” hierarchical **Chart of Accounts**, **Journal Entries** (`JE-#####`) with an inline
  debit/credit line formset + post/void(reversal) workflow, **Fiscal Periods** with admin close, **Currencies**
  (global) + per-tenant **Exchange Rates**, plus **Trial Balance** and per-account **Ledger** reports.
- **2.3 Accounts Payable** â€” **Vendor Profiles** (on `core.Party`), **Bills** (`BILL-#####`) with line items +
  approval routing + document attachment, **AP Aging**, **Payment Terms**.
- **2.4 Accounts Receivable** â€” **Customer Profiles** (credit limit/hold), **Invoices** (`INV-#####`) + credit notes
  with a line formset and credit-limit warning, **Cash Application** (paymentâ†’invoice allocation), **AR Aging**.
- **Payments** â€” unified inbound/outbound **Payments** (`PAY-#####`) whose confirm/void post (and reverse) balanced
  GL entries; invoice/bill status derives from confirmed allocations.
- **2.5 Cash Management** â€” **Bank Accounts** (last-4 only) with a live balance, **Bank Transactions** (manual +
  CSV import, deduped on external ref), **Reconciliation** matching.

Full CRUD, tenant isolation, working filters, an idempotent `seed_accounting`, and a **212-test** accounting suite.

**Advanced sub-modules 2.6â€“2.15** (extension pass, 14 accounting-owned models, migrations `0002`/`0003`) â€” every
workflow action posts a balanced `JournalEntry`:
- **2.6 Fixed Assets** (`FA-`) with a depreciation-run action (straight-line / declining-balance, capped at the
  depreciable base) and **Disposals** (`DISP-`) booking the gain/loss; **2.7 Cost Allocation** (`CALLOC-`);
  **2.8 Payroll** runs (`PRUN-`, multi-leg wage/tax/benefit JE, derived net pay); **2.9 Project/Job Costing**
  (`PRJ-`/`JCE-`) with budget-vs-actual; **2.10 Intercompany** (`ICT-`) due-to/due-from with an elimination flag.
- **2.11 Tax** codes + returns; **2.12 Reporting** â€” **Balance Sheet**, **Profit & Loss**, and Scheduled-report
  config; **2.13 Budgeting** (`BUD-`) with a budget-variance report; **2.14 Internal Controls** (SOX); **2.15
  Integrations** (Plaid/Stripe/Avalara/â€¦ config with a write-once, reveal-once hashed API key).
All posting/approval actions are `@tenant_admin_required`; the GL stays balanced (Î£debits == Î£credits).

Sidebar completion pass (2.x): **Recurring Invoicing** (`RINV-`, generates draft invoices on a weekly/monthly/
quarterly/annual cadence anchored to the start date) and a discount-aware **Payment Schedule** report were added, and
~13 previously-roadmap feature bullets were wired to the pages that already deliver them (incl. *Employee Master â†’
HRM*, and the 2.15 connector categories as filtered integration views). The bullets still marked "Soon" are
deliberately deferred â€” they belong to unbuilt modules (all of 2.7 â†’ Inventory/Procurement) or need external
integrations (OCR capture, Plaid feeds, XBRL filing, customer/vendor portals).

### Module 3 â€” Human Resource Management (`hrm`) â€” 3.1/3.2/3.3/3.4/3.5/3.6/3.7/3.8/3.9/3.10/3.11/3.12/3.13/3.14/3.15/3.16/3.17/3.18/3.19/3.20/3.21/3.22/3.23/3.24/3.25/3.26/3.27/3.28/3.29/3.30/3.31/3.32/3.33/3.34/3.35/3.36/3.37/3.38/3.39/3.40/3.41

HRM passes so far â€” **employee directory + onboarding + offboarding + leave + attendance + time tracking + holidays**, reusing the
core spine: an employee is a `core.Party` (person) + `core.Employment` + a 1:1 `hrm.EmployeeProfile` (`EMP-#####`)
anchor; departments reuse `core.OrgUnit`. Payroll GL posting stays with `accounting.PayrollRun` (not duplicated
here). Request-free domain logic (task generation, clearance-checklist generation, leave-encashment computation)
lives in `apps/hrm/services.py` so the seeder and tests can call it without the view layer.

- **3.1 Employee Management** â€” `EmployeeProfile` directory with a full personnel file (personal / employment /
  marital status / national-ID + passport / addresses / two emergency contacts / bank â€” sensitive IDs & bank fields
  **masked** in the UI and redacted from the audit log), plus two child records: an **`EmployeeDocument`** (`EDOC-`)
  vault (ID proofs, certificates, contracts, NDAs with issue/expiry dates, an expiring-soon/expired badge, an HR
  verify/reject workflow, and an enforced **confidential** flag that hides the doc from non-admins) and an
  **`EmployeeLifecycleEvent`** (`ELC-`) job-history timeline (hire / confirmation / transfer / promotion /
  salary-revision / separation as dated fromâ†’to events, admin-managed). The employee detail page is the hub â€”
  leave balances, recent attendance, recent leave, a Documents card and an Employment-Lifecycle card â€” plus an HRM
  overview (headcount / today's attendance / pending leave / upcoming holidays).
- **3.2 Organizational Structure** â€” a `JobGrade` catalog (orderable seniority levels) bands the enriched
  `Designation` (job grade + min/mid/max salary + description/requirements + budgeted headcount, linked to
  `core.OrgUnit`); `DepartmentProfile` and `CostCenterProfile` are HRM 1:1 **companions** on `core.OrgUnit`
  (kind department/cost-center) adding the head/owner/budget/code that core can't hold; plus a derived **org chart**
  (reporting-line tree / by-department grouping from `core.Employment.manager`, no model) and a read-only
  **Company Setup** view over the company OrgUnit + `tenants.BrandingSetting`.
- **3.3 Employee Onboarding** â€” a reusable `OnboardingTemplate` (`ONBT-`) of typed `OnboardingTemplateTask` lines
  (category / assignee-role / phase / due-offset) applied to one new hire as an `OnboardingProgram` (`ONB-`,
  draftâ†’activeâ†’completed/cancelled) whose `OnboardingTask`s are auto-generated with `due_date = start_date + offset`
  and a **derived** progress %; plus `OnboardingDocument` collection with an e-sign status lifecycle (allowlisted
  uploads), `AssetAllocation` (`AST-`, laptop/ID/access-card issueâ†’return), and `OrientationSession` scheduling
  with attendance. Welcome Kit (welcome message/video/first-day notes + buddy) lives on the program.
- **3.4 Employee Offboarding** â€” a `SeparationCase` (`SEP-`) hub driving resignationâ†’approvalâ†’clearanceâ†’F&Fâ†’
  completion (status `draftâ†’pending_approvalâ†’in_clearanceâ†’clearedâ†’settledâ†’completed`, with **derived**
  `expected_last_working_day` and an `all_mandatory_cleared` gate); on approval a `generate_clearance_checklist`
  service auto-builds the per-department `ClearanceItem` lines (clearing an IT line **returns the linked issued
  `AssetAllocation`** in the same txn); an `ExitInterview` (`EI-`) with 8 Likert ratings + coded reason; a
  `FinalSettlement` (`FNF-`) with earnings/deductions and a **derived** `net_payable`, `Compute` auto-fills leave
  encashment + gratuity, then HRâ†’Finance approveâ†’paid; and auto-generated relieving/experience letters
  (print views). GL posting deferred (`gl_posted` stub â†’ `accounting.PayrollRun`).
- **3.5 Job Requisition** â€” the "authorization to hire". A `JobRequisition` (`JR-`) hub carries the opening's
  title/designation/grade, department + cost-center (`core.OrgUnit`), headcount, req-type, budget (salary range +
  estimated annual cost + hiring-cost budget) and a job-description body, with hiring_manager/recruiter as
  `EmployeeProfile`s. It runs a sequential **approval chain** of `RequisitionApproval` steps (the immutable audit
  trail) through a `draftâ†’pending_approvalâ†’approvedâ†’postedâ†’on_holdâ†’filled` lifecycle (+ rejected/cancelled, all
  status fields workflow-owned, never on the form); on submit a `generate_approval_chain` service auto-builds the
  default HRâ†’Executive chain. A reusable `JobDescriptionTemplate` (`JDTMPL-`) library pre-fills the JD via a
  copy-on-apply `apply_template_to_requisition` service; plus per-step approve/reject/return, clone, and an
  overdue indicator. Offers are built in 3.8 (an `Offer` FKs the `JobApplication`).
- **3.6 Candidate Management** â€” the ATS. A `CandidateProfile` (`CAND-`) is a `core.Party`(person) +
  `PartyRole(candidate)` lens (mirrors `EmployeeProfile`) with resume/skills/source/GDPR consent + talent-pool
  `CandidateTag`s and structured `CandidateSkill`s. `JobApplication` (`APP-`) is the pipeline record against a
  3.5 `JobRequisition` (10-stage machine appliedâ†’â€¦â†’interviewâ†’offerâ†’hired, no double-apply). Recruiting
  `CandidateEmailTemplate`s (auto-send on stage transitions) log to an append-only `CandidateCommunication` trail
  (honors `do_not_contact`); plus a **public, unauthenticated career portal** (`careers_list`/`careers_apply` via an
  unguessable `public_token`) that mints the Party+application on submit.
- **3.7 Interview Process** â€” scheduling + panel + structured scorecards over the 3.6 application. An `Interview`
  (`INTV-`) is a scheduled round on a `JobApplication` (mode in-person/phone/video; status machine scheduledâ†’
  confirmedâ†’in_progressâ†’completed +cancelled/no_show/rescheduled, with reschedule reopening a closed round); an
  `InterviewPanelist` assigns interviewers (role + RSVP); an `InterviewFeedback` (`IFB-`) scorecard (one per panelist,
  5-level hire recommendation, action-only submit) holds per-competency `FeedbackCriterion` ratings (1â€“5). Candidate
  invites/reminders reuse the 3.6 email pipeline (`interview_invite`/`interview_reminder` templates â†’
  `CandidateCommunication`); a panel feedback-request nudge emails the interviewers. Calendar/Zoom-Teams-Meet/SMS
  auto-dispatch + AI scoring deferred.
- **3.8 Offer Management** â€” offer-letter generation + multi-step approval + tracking + background verification +
  pre-boarding over the 3.6 application. An `Offer` (`OFR-`) hangs off a `JobApplication` with a compensation
  breakdown (base/bonus/signing/equity/relocation/benefits) and a workflow-owned status machine
  (draftâ†’pending_approvalâ†’approvedâ†’extendedâ†’accepted/declined/rescinded/expired, never form-set); on submit a
  `generate_offer_approval_chain` service builds the default Hiring-Managerâ†’HR chain (+ an Executive step for
  high-value offers), and the approval gate blocks extension until every `OfferApproval` step is approved. Accepting
  an offer drives the application to `hired` (+ `hired_on`) and raises a `generate_preboarding_checklist`.
  A `BackgroundVerification` (`BGV-`) tracks the Checkr/Sterling-style status+result lifecycle (consent-before-initiate
  gate, report attachment); `PreboardingItem`s collect pre-start documents (submit/verify/reject + candidate invite);
  a reusable `OfferLetterTemplate` (`OLTMPL-`) merge-renders a printable offer letter. Offer emails reuse the 3.6
  candidate pipeline (`offer` template type â†’ `CandidateCommunication`). Live e-signature / background-check vendor
  APIs, adverse-action dispute flow, parallel/rule-engine approval routing + acceptance-rate analytics deferred.
- **3.9 Attendance Management** â€” `AttendanceRecord` (`ATT-`, auto `hours_worked` incl. overnight, late-arrival
  badge, source/status, + GPS `latitude`/`longitude`/`geofence` capture with a derived `geo_status()`), `Shift`
  (grace window) + `ShiftAssignment`, `GeoFence` (GPS zones with real haversine proximity), and
  `AttendanceRegularization` (`REG-`, draftâ†’pendingâ†’approved/rejected/cancelled punch-correction workflow â€”
  admin approval rewrites the linked punch to `regularized`, materialising a punch when none is linked).
- **3.10 Leave Management** â€” `LeaveType` (accrual/carry-forward/encashment policy), `LeaveAllocation` (`LA-`,
  **derived** balance = allocated âˆ’ used âˆ’ encashed, with `carried_forward`/`encashed_days` bookkeeping),
  `LeaveRequest` (`LR-`) with a draftâ†’pendingâ†’approved/rejected/cancelled workflow (days auto-computed minus
  non-optional holidays); a **Leave Policy engine** (idempotent admin accrual + year-end carry-forward runs over
  allocations); and `LeaveEncashment` (`ENC-`) to encash unused leave into a payout (draftâ†’pendingâ†’approvedâ†’paid,
  approval consumes balance via `encashed_days` so a later accrual re-run can't restore cashed-out days).
- **3.11 Time Tracking** â€” `Timesheet` (`TS-`, weekly header with **derived** `total_hours`/`billable_hours`
  recomputed from entries, draftâ†’pendingâ†’approved workflow, entries locked on approval), `TimesheetEntry` (inline
  time lines against an optional `accounting.Project` + billable flag/rate), and `OvertimeRequest` (`OT-`,
  hours Ã— multiplier, pay-or-comp-leave); plus billable/utilization + project-time-vs-budget report pages.
- **3.12 Holiday Management** â€” `PublicHoliday` calendar (national/regional/company/observance **category** +
  optional/floating flag), `HolidayPolicy` (location/department/employee-type/designation **eligibility** +
  floating-holiday **quota** + a `for_employee` most-specific-match resolver), and `FloatingHolidayElection`
  (employees elect optional holidays, quota-enforced in `clean()`, with a tenant-admin approve/reject workflow).
- **3.13 Salary Structure** â€” `PayComponent` (unified catalog: earnings / statutory / voluntary deductions /
  reimbursements / variable pay, with calc-type / frequency / taxable / contribution-side / cap flags â€” covers 4 of
  the 5 bullets), `SalaryStructureTemplate` (`SST-`, grade-wise CTC container with a **derived** `computed_ctc_total`)
  + inline `SalaryStructureLine` breakdown (PROTECT to its component), and `EmployeeSalaryStructure` (`ESS-`,
  effective-dated per-employee CTC assignment, one-active-per-employee, superseded records read-only). The
  compensation **definition** layer â€” the payroll run/posting stays in `accounting.PayrollRun` (3.14).
- **3.14 Payroll Processing** â€” the operational payroll run: `PayrollCycle` (`PRC-`, regular/off-cycle/bonus, a
  draftâ†’pendingâ†’approved/rejectedâ†’locked approval workflow) computes a `Payslip` (`PSL-`) per employee from their
  active 3.13 salary structure (a `recompute()` calc engine: monthly-from-CTC, day pro-ration, LOP, arrears/bonus,
  with employer-side statutory excluded from net), an immutable `PayslipLine` breakdown snapshot, plus salary holds.
  On **lock** it rolls the totals up into `accounting.PayrollRun` for the GL journal â€” HRM builds no `JournalEntry`
  (L29); accounting posts it.
- **3.15 Statutory Compliance** â€” the Indian statutory-payroll compliance layer over 3.13/3.14 (PF/ESI/PT/TDS/LWF):
  a `StatutoryConfig` tenant settings singleton (employer PF/ESI codes, wage ceilings, rates, TAN/PAN), state-wise
  `StatutoryStateRule` PT slabs + LWF periodicity/amounts (supersede-not-edit via `is_active`/`effective_from`),
  per-employee `EmployeeStatutoryIdentifier` (UAN/PF/ESI, masked in the UI), and a `StatutoryReturn` (`SCR-`)
  per-scheme/period register whose contribution totals are **aggregated from `PayslipLine`** (a `recompute()`
  mirroring the 3.14 lock roll-up, never hand-typed) with a pendingâ†’filedâ†’paid/late filing workflow (paying after
  the due date auto-flags **Late**) and a cross-scheme compliance calendar. Reuses the payroll spine; touches no GL.
- **3.16 Tax & Investment** â€” the Indian income-tax declaration + computation layer over 3.13/3.14/3.15: per-FY/regime
  `TaxRegimeConfig` (+ `TaxSlabBand` slab table, standard deduction, 4% cess, Section 87A rebate), a per-employee
  `InvestmentDeclaration` (`ITD-`, draftâ†’submittedâ†’locked, 80C/80D/HRA/24b/NPS section lines with declared-vs-verified
  amounts) with `InvestmentProof` uploads (4-state verification), and a `TaxComputation` (`TXC-`) **engine** â€”
  `recompute()` walks the slabs (progressive tax â†’ 87A rebate â†’ cess), does the HRA 3-way exemption, regime-filters
  Chapter VI-A deductions (new regime keeps only NPS + standard deduction), caps per section, aggregates TDS-paid-YTD
  from `PayslipLine`, and spreads the balance across remaining pay periods â€” plus an old-vs-new regime comparison and a
  **Form 16 Part B** report that reuses the existing `StatutoryReturn(tds_form16)` (no new Form 16 table). Posts no GL.
- **3.17 Payout & Reports** â€” the salary-disbursement + reconciliation layer over 3.14: a `PayoutBatch` (`POB-`,
  generated from a **locked** `PayrollCycle`, draftâ†’approvedâ†’disbursed/partially_disbursedâ†’reconciled) with one
  `PayoutPayment` per payslip â€” snapshotting `net_pay` + the employee's **masked** bank details (never the raw
  account), a pendingâ†’processingâ†’paid/failed/returned lifecycle, a bank UTR, and a `retry_of` re-initiation chain
  (a retry supersedes the failed original so totals never double-count); a `PayslipDistribution` (1:1) tracking the
  payslip sendâ†’viewedâ†’downloaded signal; a `BankReconciliation` (`BRC-`) matching payments to the statement by UTR
  (`reconciled`/`discrepancy`); plus a **payment register** (bank-advice) and **exceptions** report. The bank-file
  writer, payslip-PDF render and live bank API are deferred; posts no GL.
- **3.18 Goal Setting** â€” the first Performance-Management sub-module (OKR mechanics): a `GoalPeriod` quarterly/annual
  cycle catalog (activate/close), an `Objective` (`OBJ-`) owned by an `EmployeeProfile` with a `parent_objective`
  self-FK cascade (Goal Alignment), a `core.OrgUnit` department scope, a weight, and **derived** weighted `progress_pct`
  + pace-based `health_status` (on_track/at_risk/off_track); a `KeyResult` (`KR-`) with 5 metric types
  (numeric/percentage/currency/boolean/milestone) + per-KR weight; and an **append-only** `GoalCheckIn` (`GCI-`) history
  log whose save advances the KR's current value. Includes a recursive **alignment tree** (companyâ†’departmentâ†’
  individual) and a **?mine** own-and-direct-reports view. Reuses `EmployeeProfile` + `core.OrgUnit` (no new core-spine
  entity, posts no GL); ratings/reviews/360/kudos/PIP are deferred to 3.19â€“3.21.
- **3.19 Performance Review** â€” the second Performance-Management sub-module (formal appraisal cycles): a `ReviewCycle`
  with a 6-phase machine (draftâ†’self-assessmentâ†’manager-reviewâ†’calibrationâ†’releasedâ†’closed, admin-advanced) + an optional
  link to a 3.18 `GoalPeriod`; a `ReviewTemplate` (`RVT-`) per review type (self/manager/peer/upward/skip-level); a
  `PerformanceReview` (`RVW-`) with **derived** weighted `overall_rating`, a stored `calibrated_rating` that overrides it
  (`effective_rating`), a `potential_rating`, and manager-only `private_notes`; and `ReviewRating` (`RVR-`) weighted
  competency lines. Covers self/manager/peer/upward reviews with a submitâ†’shareâ†’acknowledge workflow, a
  **calibration board** (manager reviews ranked by effective rating), and a goal-review section reading the subject's
  Objectives. **Performance data is confidential** â€” visible only to the subject, reviewer, or a tenant admin, and
  content is edit-locked once submitted. Reuses `EmployeeProfile` + the 3.18 goal models (no new spine, posts no GL);
  continuous feedback/PIP are deferred to 3.20â€“3.21.
- **3.20 Continuous Feedback** â€” the third Performance-Management sub-module (the ongoing/informal layer): a `Feedback`
  (`FBK-`) row for real-time kudos/appreciation/constructive feedback with `visibility` (private/team/public), an
  `is_anonymous` flag that **masks the giver on read** for non-admin/non-giver viewers (cloning the 3.19 reviewer
  masking), optional `badge`/`related_objective`/`related_review` links, and a `requested_from` self-FK that folds the
  **request-feedback pull workflow** (requestedâ†’givenâ†’acknowledged) into one table; a `KudosBadge` recognition catalog
  (values-tag chips); an `OneOnOneMeeting` (`O2O-`) with a shared agenda/notes and **manager-only
  `manager_private_notes`** (never rendered employee-side; the edit form is manager/admin-gated), scheduledâ†’completed/
  cancelled workflow, and `MeetingActionItem` (`MAI-`) children (owner + due date + open/done toggle); plus a computed
  **Feedback Dashboard** (given/received/requested + per-type mix + 30-day velocity â€” a view, not a model). Confidential
  by design (`_can_view_feedback`/`_visible_feedback_q`/`_can_edit_feedback`). Reuses `EmployeeProfile` + the 3.18/3.19
  models (no new spine, posts no GL); PIP/warning-letters/coaching are deferred to 3.21.
- **3.21 Performance Improvement** â€” the fourth & FINAL Performance-Management sub-module (the corrective-action /
  disciplinary layer, the most confidential HRM records): a `PerformanceImprovementPlan` (`PIP-`) with an HR-approval
  workflow (draft â†’ pending â†’ active â†’ closed), structured issue/standards/goals/support/measurement sections, an
  optional link to the triggering 3.19 `PerformanceReview`, a close-with-outcome step (successful/extended/failed/
  terminated) and an extend path, plus `PIPCheckIn` (`PCI-`) scheduled progress checkpoints; a `WarningLetter`
  (`WRN-`) for progressive discipline (verbal â†’ written â†’ final â†’ suspension across attendance/conduct/performance/
  policy) with an issue â†’ acknowledge workflow, an employee-response field, a derived `prior_warnings` escalation
  view, and a printable letter; and a `CoachingNote` (`CN-`) manager journal â€” **the strictest gate in the system:
  visible only to the coach and admin, NEVER to the coached employee**. Confidential throughout
  (`_can_view_pip`/`_can_view_warning`/`_can_view_coaching`). Reuses `EmployeeProfile` + the 3.19 review (no new
  spine, posts no GL). **Performance Management (3.18â€“3.21) is now complete.**
- **3.22 Training Management** â€” the Instructor-Led-Training scheduling/catalog layer (a NEW HRM domain, ordinary
  tenant-scoped CRUD â€” no confidentiality gate): a `TrainingCourse` (`TRC-`) catalog (category/delivery-mode/provider
  split, duration, certification name + validity, a self-FK prerequisite chain, default capacity) and a
  `TrainingSession` (`TRS-`) scheduled occurrence unifying **Classroom / Virtual / External** delivery via
  `delivery_mode` â€” venue + capacity/waitlist, meeting platform/link/id, an internal `EmployeeProfile` instructor or a
  named external trainer, an external vendor (`core.Party` vendor role â€” no new vendor table), and estimated/actual
  cost in an `accounting.Currency` â€” with a `clean()` that enforces the mode-specific required fields plus an
  **instructor/venue double-booking overlap guard**, derived `can_join`/`is_upcoming` props, and a **Training Calendar**
  date-grouped upcoming view. Reuses `EmployeeProfile` + `core.Party` + `accounting.Currency` (no new spine, posts no
  GL); 3.23 LMS (content/paths/assessments) and 3.24 Training Administration (nomination/attendance/certificates/
  budget) are deferred sibling sub-modules.
- **3.23 Learning Management (LMS)** â€” the self-paced digital-learning layer on top of the 3.22 `TrainingCourse`
  catalog (ordinary tenant-scoped CRUD, no confidentiality gate): a `LearningContentItem` (a CASCADE child of a
  course â€” ordered video/document/SCORM/external-link/text lessons + a lightweight `assessment` variant with
  pass-threshold/max-attempts/time-limit, `clean()` enforcing the type-matching content field; SCORM stored as an
  opaque file with a zip-slip WARNING for future extraction), a `LearningPath` (`LNP-`) role-based journey targeting
  `Designation`/`core.OrgUnit` department + its ordered `LearningPathItem` course steps (with a `clean()`
  prerequisite-gating guard reusing `TrainingCourse.prerequisite_course`), and a `LearningProgress` (unique per
  employeeÃ—course) tracking status/percent/time-spent/score/passed/attempts/`points_earned` with a derived
  `certification_expires_on`. Gamification ships as a **computed points leaderboard** (Bronze/Silver/Gold/Platinum
  tiers) + a manager **team-progress** rollup â€” no stored leaderboard/badge tables. Reuses `TrainingCourse` +
  `EmployeeProfile` + `Designation`/`OrgUnit` (no new course/learner/role tables, posts no GL); a question-bank
  assessment engine, SCORM runtime/xAPI, an achievement-badge catalog, and 3.24 Training Administration
  (nomination/attendance/feedback/certificates/budget) are deferred.
- **3.24 Training Administration** â€” the operational/admin layer over 3.22 sessions + 3.23 LMS (ordinary
  tenant-scoped CRUD): a `TrainingNomination` (`NOM-`) â€” an employee nominated for a `TrainingSession` with a
  single-approver workflow (self/manager/HR nomination â†’ pending â†’ approve[/waitlist if the session is full] /
  reject / cancel / withdraw, manager-or-admin gated via the reporting line, mirroring the LeaveRequest shape); a
  `TrainingAttendance` (per-session-per-employee â€” registered/present/absent/partial/walk-in + completion +
  check-in/out, linking back to its nomination); a `TrainingFeedback` (Kirkpatrick-L1 overall/content/trainer 1â€“5
  ratings + would-recommend + anonymous masking cloned from 3.20 Feedback); and a `TrainingCertificate` (`CERT-`) â€”
  an issuance record from a completed `TrainingAttendance` (ILT) **or** `LearningProgress` (LMS), with a
  `secrets`-based verification code, `expires_on` computed once from the course validity (via a shared
  `_advance_months` helper refactored out of 3.23), a revoke workflow, and a printable certificate. **Training
  Budget** is a **computed view** (the year's training spend â€” estimated vs actual, by course â€” vs the allocated
  `CostCenterProfile.budget_annual`), no stored model. Reuses `TrainingSession`/`TrainingCourse` (3.22) +
  `LearningProgress` (3.23) + `EmployeeProfile`/`CostCenterProfile` (no new session/learner tables, posts no GL); the
  N-step approval engine, QR check-in, multi-level Kirkpatrick, a branded certificate-PDF renderer, and a public
  verify-by-code page are deferred. **Training (3.22 ILT + 3.23 LMS + 3.24 Administration) is now complete.**
- **3.25 Personal Information (Self-Service)** â€” the Employee Self-Service (ESS) layer over the existing
  `EmployeeProfile` (which already carries flat bank/emergency/address/personal-file columns), so this pass adds the
  *self-service surface* + the child tables the flat columns can't model + an HR maker-checker approval workflow, not
  a re-model of the profile. A `my_info` hub (read-only employment context + the employee's direct-edit contact fields
  + masked sensitive fields, each with a "Request a Change" link) and its `my_info_edit` form (address / personal
  email / mobile / photo only); `EmergencyContact` â€” an unlimited roster (vs the 2 flat profile slots) with an
  auto-demote `is_primary`, **direct self-edit** (no approval gate); `EmployeeBankAccount` â€” multiple accounts with an
  auto-demote `is_salary_account`, Gusto-style `split_percentage`, a pendingâ†’verified/rejected verify workflow, and a
  `masked_account_number()` shown everywhere (the raw number is never rendered, and it's redacted from the AuditLog);
  `FamilyMember` â€” dependents/nominees with a guardian-required-when-minor rule; and `EmployeeInfoChangeRequest`
  (`ICR-`) â€” the maker-checker workflow (a `GenericForeignKey` gating sensitive `EmployeeProfile` fields [legal name â†’
  `core.Party.name`, DOB, national ID, passport], bank writes, and family writes) with an `apply()` that writes the
  approved change atomically, a lost-update guard, and maker-checker separation (the requester/subject can't self-
  approve). Bank/family writes are tenant-admin-only (an employee proposes them via a change request); emergency
  contacts + the my_info contact fields are direct self-edit. A per-tenant configurable field-permission matrix,
  effective-dated history, per-scheme statutory nomination, and live bank verification are deferred.
- **3.26 Request Management (Self-Service)** â€” the employee request portal. Leave Requests and Attendance
  Regularization **reuse** the existing 3.10 `LeaveRequest` / 3.9 `AttendanceRegularization` models (no new table â€”
  they just gain a second sidebar entry), and this pass adds three new request models plus a unified **My Requests**
  hub. `DocumentRequest` (`DOCREQ-`) â€” official-letter requests (experience letter / salary certificate / employment
  verification / NOC / address proof) with purpose, addressed-to, copies and delivery method, whose `document_fulfill`
  action can attach an HR-uploaded signed letter (validated through the shared `_validate_upload` helper);
  `IdCardRequest` (`IDREQ-`) â€” new/replacement/correction/renewal cards with a lost/damaged/expired/name-change reason
  taxonomy, issued via `idcardrequest_issue` (stamping a card number); `AssetRequest` (`ASSETREQ-`) â€” equipment
  requests reusing `AssetAllocation.ASSET_CATEGORY_CHOICES`, whose `assetrequest_fulfill` **creates and links an
  `AssetAllocation`** (`program=None`, `status=issued`) inside one atomic transaction. All three run the
  `draft â†’ pending â†’ approved/rejected/cancelled` (+ fulfillment tail) lifecycle, reuse the ESS self-service helpers
  (`_ss_child_*`, `_ss_scope`, `_can_manage_own_child`) so an employee sees only their own rows, and enforce a
  3.25-style **self-approval guard** (an admin who is the requesting employee can't approve/reject their own request;
  reject requires a note). Configurable multi-level approval chains, SLA auto-escalation, template-driven letter
  generation, e-signature, notifications, and software/license access requests are deferred.
- **3.27 Communication Hub** â€” the internal employee-communications surface. Four new models + a derived
  celebrations view. `Announcement` (`ANN-`) â€” admin-authored company news with category, audience targeting
  (all / a department [`core.OrgUnit` kind=department] / a designation [`hrm.Designation`], reusing the
  `LearningPath` 3.23 precedent), pinning, and a draftâ†’publishedâ†’archived lifecycle (`publish` stamps
  `published_at`; the employee feed shows only published, un-expired, for-them posts via an audience `Q`-filter,
  enforced on the detail page too); `Survey` (`SUR-`) + `SurveyResponse` â€” an engagement survey whose questions are
  structured JSON (rating / text / single-choice; a 0â€“10 rating covers eNPS), draftâ†’openâ†’closed, employees respond
  **once** (`unique_together(survey, employee)`), and `is_anonymous` suppresses respondent identity in the aggregated
  results; `Suggestion` (`SUG-`) â€” an employee idea box that **clones the 3.26 request lifecycle field-for-field**
  (owner `employee` FK + `approver`/`approved_at`) so the shared `_hr_request_*` helpers apply verbatim
  (draftâ†’pendingâ†’approved[Accepted]/rejected/cancelled + an `implemented` tail), with the same self-approval guard;
  and **Celebrations** â€” a derived view (no model, mirrors `org_chart`) of upcoming birthdays
  (`EmployeeProfile.date_of_birth`) + work anniversaries (`core.Employment.hired_on`) within a `?window=`. The 5th
  bullet, **Help Desk**, now resolves to the dedicated **3.36 Helpdesk** sub-module (its sidebar entry points at
  the live ticket list). Read receipts, reactions, delivery fan-out, survey k-anonymity, and voting are deferred.
- **3.28 HR Reports** â€” the core HR analytics surface, built as **6 derived, read-only, `@tenant_admin_required`
  report views** (NO new models â€” pure tenant-scoped aggregates over the existing spine, mirroring accounting's
  `trial_balance`/`ap_aging`): an `hr_reports_index` landing hub + `headcount_report` (active/joins/exits by
  department/designation[+budgeted]/type, 12-month trend), `attrition_report` (SHRM annualized turnover with
  voluntary/involuntary split, by department/exit-reason/tenure-band, monthly trend), `diversity_report`
  (gender/age-band/tenure-band distributions + a department Ã— gender cross-tab), `cost_report` (per-`PayrollCycle`
  gross + employer-contribution cost, department-wise + CTC-component breakdown, cross-cycle trend, with an
  `EmployeeSalaryStructure` CTC/12 run-rate fallback flagged as *Estimated* when no payroll run exists), and
  `hiring_report` (time-to-fill/time-to-hire, source-of-hire mix, application funnel, offer-acceptance approximation,
  hires by department). Every rate guards div-by-zero, `?department` is resolved tenant-scoped (IDOR-safe), and
  `EmployeeProfile` aggregation goes through `employment__org_unit` (department/manager are `@property`, not columns).
  Trends render via the Chart.js already loaded in `base.html`. FTE/EEO PII fields, true cost-per-hire, attrition-risk
  ML, and the drag-drop dashboard builder (3.32) are deferred.
- **3.29 Attendance Reports** â€” **5 derived, read-only, `@tenant_admin_required` report views** (NO new models,
  reusing the 3.28 report helpers): `attendance_reports_index` + `attendance_summary_report` (status breakdown +
  attendance % = present-equivalent [present + regularized + Â½Â·half-day] Ã· tracked-days [excludes holiday/on-leave],
  by department, monthly trend), `late_early_report` (late-arrival [mirroring `AttendanceRecord.is_late()`'s
  boundary math inline, to also get minute counts] + early-departure counts + avg minutes, top-offenders,
  day-of-week pattern â€” one `select_related` pass),
  `absenteeism_report` (absence rate + frequent-absentee list + monthly trend), and `overtime_report` (total +
  pay-equivalent hours [`hours_claimed Ã— multiplier`], by employee/department, status mix, trend â€” **hours only, no
  currency**, no pay-rate source). The **Utilization Report** bullet reuses the existing 3.11
  `timesheet_utilization_report`. Monthly trends use a single `TruncMonth`-grouped query; every rate guards
  div-by-zero. Currency OT cost, scheduled-vs-worked hours, Bradford-Factor discipline, and muster-roll grids are
  deferred.
- **3.30 Leave Reports** â€” **5 derived, read-only, `@tenant_admin_required` report views** (NO new models, reusing
  the 3.28 helpers + the 3.10 leave models): `leave_reports_index` + `leave_register_report` (per-employeeÃ—type
  allocated/carried/availed/encashed/balance for a `?year`), `leave_liability_report` (encashable-only, balance>0;
  days Ã— per-day rate â†’ value; rate = latest approved/paid encashment, else annual-CTCÃ·365 estimate, else none),
  `comp_off_report` (OT-comp-leave earned vs comp-off-leave availed), `leave_trend_report` (approved-leave days,
  by-type, top-takers, monthly trend). Availed-days are annotated via a correlated subquery (`used_db`, no per-row
  N+1); per-employee dicts key on `employee_id`, not the non-unique display name.
- **3.31 Payroll Reports** â€” **6 derived, read-only, `@tenant_admin_required` report views** (NO new models,
  aggregating the 3.13-3.16 payroll engine): `payroll_reports_index` + `salary_register_report` (per-`Payslip`
  earnings/deductions/net grid for a `?cycle` + component-type breakdown), `tax_report` (TDS summary from
  `TaxComputation`, investment-declaration funnel, section-wise declared/verified, regime split, Form 16
  linked/pending register â†’ `form16_partb`), `statutory_report` (PF/ESI/PT/LWF register from `StatutoryReturn` +
  **masked** UAN/PF/ESI employee-coverage), `ctc_report` (structural annualized CTC from active
  `EmployeeSalaryStructure` + component-type mix chart), and `cost_center_report` (budget-vs-actual per
  `CostCenterProfile`, attributing each employee's department to its mapped cost centre via
  `DepartmentProfile.cost_center`, unmapped spend surfaced in an **Unassigned** callout). GL posting, Form 16 PDF,
  statutory e-filing (ECR/24Q), and multi-level cost-centre roll-up are deferred.
- **3.32 Analytics Dashboard** â€” the dashboard layer over the 3.28-3.31 reports, mirroring CRM 1.6's saved-dashboard
  mechanic: **2 new models** (`HRDashboard` + `HRDashboardWidget`) with a live-compute layer (`apps/hrm/analytics.py`,
  a 16-metric catalog computed on each render) so a user can assemble/save a **custom dashboard** of KPI/gauge/chart/
  table widgets (owner-or-admin gated, shareable tenant-wide), **plus 3 derived `@tenant_admin_required` views**:
  `executive_dashboard` (leadership KPI strip + sparklines + alerts), `predictive_analytics` (a transparent
  attrition-risk heuristic â€” tenure/attendance/leave/probation/review-gap, *not* ML â€” plus a hiring-needs
  projection), and `benchmarking` (period-over-period RAG scorecard with optional vs-target override + a
  pay-equity table). A true drag-drop grid, trained ML models, and external industry-benchmark feeds are deferred.
- **3.33 Asset Management** â€” the HR-facing asset register the 3.3 `AssetAllocation` issuance rows now point at:
  **2 new models** â€” `Asset` (`ASSET-`; tag/serial/category/status lifecycle [in_stock/assigned/in_repair/retired/
  disposed] + **computed straight-line/declining-balance depreciation** book value, floored at salvage) and
  `AssetMaintenance` (`ASSETMNT-`; preventive/repair/AMC/warranty-claim/inspection with contract windows) â€” plus a
  nullable `AssetAllocation.asset` FK. Assetâ†”allocation status/holder stay in step via two atomic `save()`-override
  syncs (no-op for pre-3.33 rows), and a "repair" record moves its asset in/out of service. Full CRUD + lifecycle
  actions (assign/return/retire/dispose, `select_for_update`-guarded) + maintenance CRUD. Barcode/QR, software-license
  management, CMMS work orders, depreciation GL posting, and the Module 11 enterprise `assets.Asset` migration are deferred.
- **3.34 Expense Management** â€” employee T&E expense claims (distinct from CRM's sales expense and payroll's
  reimbursement payout): **3 new models** â€” `ExpenseCategory` (per-claim / monthly / receipt-threshold policy limits
  + a GL-account coding hint), `ExpenseClaim` (`ECL-`; a **2-stage managerâ†’finance approval** machine
  draftâ†’submittedâ†’manager_approvedâ†’approvedâ†’reimbursed, with payment tracking and computed total/violations), and
  `ExpenseClaimLine` (category / amount / merchant / **receipt upload** + a computed policy-compliance soft-flag).
  Full own-vs-admin CRUD + the six workflow actions (submit / manager-approve / approve / reject / cancel /
  reimburse â€” each self-approval-blocked for an admin acting on their own claim), inline draft-only line editing, and
  receipt validation (extension allowlist + size cap). OCR, corporate-card reconciliation, mileage/per-diem, cash
  advances, multi-currency FX, N-level routing, the payroll-payout integration, and GL posting are deferred.
- **3.35 Travel Management** â€” trip authorization with a travel advance and post-trip settlement: **3 new models** â€”
  `TravelPolicy` (per-job-grade class-of-travel + daily/hotel/advance-percent caps, scoped domestic/international/both),
  `TravelRequest` (`TRV-`; a single-approver machine draftâ†’pendingâ†’approved/rejected/cancelled then approvedâ†’completed
  â€” reusing the shared request-workflow helpers verbatim â€” plus advance request/approve/pay and a computed
  net-settlement), and `TravelBooking` (flight/hotel/cab lines with a **document upload** and a computed **out-of-policy**
  flag driven by the policy's class-rank + hotel-per-night caps). Full own-vs-admin CRUD, the advance actions
  (approve capped at the policy percent + maker-checker self-block; idempotent mark-paid), and **Generate Settlement**
  that spins up a linked 3.34 `ExpenseClaim` (atomic + idempotent). Corporate-booking-tool (GDS) integration,
  multi-leg itineraries, real-time fare shopping, and per-diem auto-calc are deferred.
- **3.36 Helpdesk** â€” the employee HR/IT/Admin/Facilities service desk. **4 new models** (`apps/hrm/models.py`,
  migrations `0051`+`0052`): `HelpdeskSLAPolicy` (`HSLA-`; per-priority response/resolution hour targets +
  `targets_for(priority)`, a mirror of `crm.SlaPolicy`), `HelpdeskCategory` (HR/IT/Admin/Facilities routing +
  KB taxonomy, carrying the default assignee + default SLA policy a new ticket inherits), `HelpdeskTicket`
  (`TKT-`; requester `employee` FK reuses `_ss_scope`/`_can_manage_own_child`; an **agent-worked** lifecycle
  newâ†’openâ†’in_progressâ†’waitingâ†’resolvedâ†’closed [+cancelled] via bespoke assign/start/waiting/resolve/close/
  reopen/cancel/feedback actions â€” NOT the single-approver `_hr_request_*` machine; SLA due timestamps stamped
  once in `save()` [mirrors `crm.Case`] with **computed** breach / `sla_state`; inline **CSAT**
  [`satisfaction_rating`/comment, no separate survey model]), and `KnowledgeArticle` (`KBA-`; internal-only
  FAQ/self-help, draftâ†’publishedâ†’archived, view/helpful counters). `LIVE_LINKS["3.36"]` maps all 5 bullets
  (Ticket Managementâ†’`ticket_list`, Ticket Categoriesâ†’`helpdeskcategory_list`, SLA Managementâ†’`helpdesksla_list`,
  Knowledge Baseâ†’`knowledgearticle_list`, Satisfaction Surveyâ†’`ticket_list?rated=1`) + an SLA-breach deep-link
  (`ticket_list?sla=breached`); the 3.27 "Help Desk" bullet is re-pointed here. A comment thread, auto-routing/
  escalation, business-hours SLA clocks, KB voting/public portal, and a CSAT analytics dashboard are deferred.

- **3.37 Compensation & Benefits** â€” market benchmarking, benefits enrollment, and equity. **4 new models**
  (`apps/hrm/models.py`, migrations `0053`+`0054`): `SalaryBenchmark` (external P25/P50/P75/P90 market data keyed
  to a `JobGrade`/`Designation` + a `compa_ratio(pay)` method â€” builds ON the 3.2 salary bands + 3.13
  `EmployeeSalaryStructure`, never duplicating them), `BenefitPlan` (the medical/dental/life/retirement catalog with
  an employer/employee monthly cost split, flex-credit eligibility, CSV coverage tiers and an enrollment window),
  `EmployeeBenefitEnrollment` (`BEN-`; the opt-in/opt-out/waived election â€” `employee` FK reuses
  `_ss_scope`/`_can_manage_own_child`, effective-dated, with **server-derived contributions** [the plan's costs are
  never user-settable â€” employer money] and an admin `enroll`/`waive`/`terminate` lifecycle), and `EquityGrant`
  (`ESOP-`; ISO/NSO/RSU/ESPP/phantom grants with a cliff + graded vesting schedule whose `vested_shares` /
  `vested_percent` / `unvested_shares` / `exercisable_shares` are **computed, never stored** â€” only
  `exercised_shares` is persisted, via a guarded `record_exercise` action). `LIVE_LINKS["3.37"]` lights **4 of the 6**
  bullets (Salary Benchmarking, Benefits Administration, Flexible Benefits, Stock/ESOP Management); Compensation
  Planning (merit/promotion cycles) and a formal monetary Rewards & Recognition are deferred â€” peer kudos already
  ship in 3.20. Carrier EDI, AI job-pricing, 409A/ASC-718 GL posting, and cap-table modeling are deferred.

- **3.38 Talent Management & Succession Planning** â€” the HiPo/9-box + succession-bench layer, built **on** the
  3.19 `PerformanceReview` ratings rather than duplicating them. **4 new models** (migration `0055`):
  `TalentPool` (hipo / successor / critical-skill / leadership segments), `TalentPoolMembership` (the 9-box row â€”
  its `review` FK supplies the two axes [`effective_rating` = performance, `potential_rating` = potential] with
  optional per-member overrides, plus `flight_risk` + a `retention_action_plan`; `nine_box_quadrant` is
  **computed, never stored** â€” a 3Ã—3 label lookup from the banded ratings: Star / Emerging Star / Core Player /
  Enigma / Underperformer â€¦), `SuccessionPlan` (`SPL-`; a critical role's bench with `vacancy_risk` and a
  **computed** `bench_strength` from successor readiness), and `SuccessionCandidate` (the ranked inline bench).
  A derived **9-box grid** view buckets active members (rows = potential, columns = performance) with an
  "unplaced" list for the unrated. **CONFIDENTIAL:** every 3.38 view is `@tenant_admin_required` â€” an employee
  must never learn they're in a HiPo pool, on a bench, or flagged a flight risk (the 3.21 precedent).
  `LIVE_LINKS["3.38"]` lights **5 of 6** bullets, and notably **two need no new table**: *Talent Reviews* reuses
  the 3.19 calibration board and *Internal Mobility* reuses `JobRequisition(posting_type="internal")` + the 3.6
  application pipeline. *Career Pathing* is deferred (needs a CareerPath + EmployeeSkill taxonomy).
- **3.39 Compliance & Legal** â€” the employment-lifecycle compliance layer. **5 new models** (migrations `0053`â€“`0057`):
  `EmploymentContract` (`ECON-`; permanent/fixed-term/probation/consultant, with a **computed** `is_expiring_soon`
  60-day window), `HRPolicy` (versioned, draftâ†’publishedâ†’archived; **publishing goes only through the dedicated
  action**, which stamps `published_at` and raises the acknowledgment rows â€” the create/edit form offers
  draft/archived only, so it can't silently skip acknowledgments), `PolicyAcknowledgment` (per-employee, employee
  self-service), `Grievance` (`GRV-`; severity + **anonymous complainants masked from everyone but HR**, investigateâ†’
  resolveâ†’close), and `ComplianceRegister` (`CREG-`; statutory filings with a **computed** `is_overdue`).
  `LIVE_LINKS["3.39"]` lights **all 6** bullets â€” *Disciplinary Actions* reuses the 3.21 `WarningLetter` (no new
  table).
- **3.40 Workforce Planning** â€” demand/supply/gap/scenario planning. **4 new models** (migrations `0058`/`0059`):
  `WorkforcePlan` (`WFP-`; a planning cycle whose four headcount/budget totals are **computed and annotation-aware** â€”
  the list annotates them so rendering N plans never fires 4N aggregates), `WorkforcePlanLine` (per-department current
  vs planned headcount with a **computed** gap and budget impact â€” `None`, not 0, when unpriced), `WorkforceScenario`
  (`WFS-`; **signed** what-if deltas for hiring-freeze/restructuring, with an enforced one-baseline-per-plan), and
  `EmployeeSkill` (the skills inventory behind Supply Analysis, **own-vs-admin self-service**). Two derived reports â€”
  a **gap analysis** (current vs planned per department, grouped by org-unit id so same-named departments don't merge)
  and **workforce analytics** (headcount + skill-coverage + hiring-mix). **CONFIDENTIAL:** every plan/scenario/report
  view is `@tenant_admin_required` (restructuring/reduction headcount); only the skills inventory is employee-facing.
  `LIVE_LINKS["3.40"]` lights **all 6** bullets.
- **3.41 Employee Engagement & Wellbeing** â€” an **extension** pass that reuses 3.27's `Survey`/`SurveyResponse`
  (pulse/eNPS delivery) and `Announcement` (values content) rather than rebuilding them. **4 new models** (migration
  `0060`): `SurveyActionPlan` (`ACTP-`; the "close the loop" gap â€” turns a closed survey's low scores into an owned,
  dated initiative, editable by the owner-or-admin), `WellbeingProgram` (`WBP-`; **one** `program_type`-discriminated
  catalog spanning wellness challenges, EAP/counseling, culture assessments, team events, interest groups and
  volunteering), `WellbeingParticipation` (the RSVP/attendance child â€” a non-admin can register or withdraw only, never
  self-award points), and `FlexibleWorkArrangement` (`FWA-`; a remote/hybrid/compressed-week request, a `TravelRequest`
  clone reusing the shared approval workflow). **CONFIDENTIAL:** EAP programs are **forced** confidential at the model
  layer, and a confidential program's roster is **aggregate-only for everyone â€” admins included** (even the audit trail
  is scrubbed of participant identity). `LIVE_LINKS["3.41"]` lights **all 6** bullets â€” the four wellbeing bullets are
  `program_type`-filtered slices of the one catalog.

Full CRUD, tenant isolation, working filters, an idempotent `seed_hrm`, and a **6,489-test** HRM suite
(**9,137 project-wide**). Leave/approver, offboarding, and document-verification/lifecycle workflow & approval
fields are workflow-set (never form-set); sensitive bank/national-ID/passport fields are masked in the UI and
redacted from the audit trail.

---

## Technology stack

| Layer | Choice | Version |
|-------|--------|---------|
| Language | Python | 3.10+ |
| Framework | Django | 5.1.x |
| DB driver | PyMySQL (as MySQLdb) | 1.2.x |
| Database | MySQL / MariaDB (XAMPP) | MariaDB 10.4+ |
| CSS | Tailwind (Play CDN) + `theme.css` design system | â€” |
| Interactivity | HTMX | 1.9.x |
| Charts | Chart.js | 4.4.x |
| Icons | Lucide | latest |
| Payments | Stripe Python SDK | 15.x |
| Images | Pillow | 12.x |
| Config | python-dotenv | 1.x |
| Tests | pytest + pytest-django | 9.x / 4.x |

---

## Architecture

### Multi-tenancy (shared database)
Every business model carries `tenant = ForeignKey('core.Tenant', db_index=True)`. On each request,
`apps.core.middleware.TenantMiddleware` sets `request.tenant` from `request.user.tenant`. Every view filters
`Model.objects.filter(tenant=request.tenant)` and every object lookup uses
`get_object_or_404(Model, pk=pk, tenant=request.tenant)`, so a foreign tenant's id returns **404** (no IDOR).
The Django superuser `admin` has `tenant=None` by design and therefore sees no module data â€” administer tenants
via the Django admin or a tenant-admin account.

### Request â†’ response flow
```
request
  â†’ SecurityMiddleware â†’ SessionMiddleware â†’ CommonMiddleware â†’ CsrfViewMiddleware
  â†’ AuthenticationMiddleware
  â†’ TenantMiddleware            (sets request.tenant)
  â†’ SessionTimeoutMiddleware    (idle logout)
  â†’ MessageMiddleware â†’ XFrameOptionsMiddleware
  â†’ view (@login_required / @tenant_admin_required)
      â†’ tenant-scoped queryset â†’ template (sidebar from MODULE_CATALOG, branding from context processor)
```

### Backend organization â€” models / forms / views / urls are packages
The domain modules keep their backend in **Python packages, not flat `.py` files**, organized **one folder per
sub-module, then one file per entity** â€” the exact mirror of the template folder rule. `apps/crm` and
`apps/accounting` are fully converted:

```
apps/<app>/
  models/  forms/  views/  urls/          each a package
    __init__.py                           re-exports every symbol it owns (so `from apps.<app>.models import X`,
    _base.py / _common.py                 shared imports + the abstract Tenant* base / TenantModelForm
    <SubModule>/<Entity>.py               e.g. models/GeneralLedger/JournalEntries.py  (= JournalEntry + JournalLine)
```

The four layers line up one-to-one, so a single entity's model, form, view and URL module share a path
(`<SubModule>/<Entity>.py`). Because each `__init__.py` re-exports everything, `urls.py`, the seeders, the admin,
cross-app imports and every test keep importing `apps.<app>.models` / `.forms` / `.views` unchanged â€” and since a
model's `app_label` still derives from the app config, **the split needs no migration**. Imports *inside* a package
are absolute; cross-sub-module view helpers live in `views/_helpers.py`; there are no `*_advanced.py` sidecars. See
the "Backend Package Structure" rule in `.claude/CLAUDE.md` and the reference apps. All three domain
modules (`crm`, `accounting`, `hrm`) are converted. The Module 0 foundation apps `core` and `tenants` use
the same packages **without** the sub-module level â€” Module 0 has no NavERP sub-modules, so their entity
files sit flat at the package root (`core/models/Party.py`), mirroring their flat templates. Their
`urls.py` stays a flat module on purpose: `core/urls.py` is a `crud()` factory that generates the 5
standard routes per model, and expanding it would only duplicate `path()` lines. `accounts` and
`dashboard` remain flat.

### Reusable CRUD layer
`apps/core/crud.py` centralizes list/create/detail/edit/delete so every module behaves consistently and the
recurring pitfalls are fixed once:
- **Search** across declared fields; **filters** with an integer-FK guard (never pass non-numeric to an int filter).
- **Windowed pagination** (`1 â€¦ n-1 [n] n+1 â€¦ last`) â€” guards prev/next and preserves active filters.
- **Tenant scoping** on every read/write; orphan-row protection for tenant-less users.
- **Audit logging** on create/update/delete.

### Numbering & audit
Human-readable per-tenant document numbers (e.g. `SINV-#####`) are generated in `save()` with an existence guard
and a retry on the rare concurrent collision (`unique_together(tenant, number)`). `AuditLog` is append-only and
read-only in the UI.

### MariaDB 10.4 compatibility
Django 5.1 targets MariaDB â‰¥ 10.5, but XAMPP ships 10.4. [`config/__init__.py`](config/__init__.py) installs
PyMySQL as the driver and applies a compatibility shim: it lowers the version floor **and** disables
`INSERT â€¦ RETURNING` (which 10.4 cannot parse). Without this, the very first migration fails with a SQL syntax
(1064) error.

---

## Prerequisites

- **Python 3.10+** on PATH.
- **XAMPP** with **MySQL/MariaDB running** (Control Panel â†’ Start MySQL). Developed against MariaDB 10.4.x.
- A database named **`nav_erp`** (created in setup step 3). The default XAMPP MySQL user is `root` with an empty
  password on `127.0.0.1:3306`.

> This XAMPP instance may host other databases â€” NavERP only ever touches **`nav_erp`**.

---

## Installation & setup

All commands are **Windows PowerShell** (the project's shell). Run from the repository root.

```powershell
# 1. Create a virtual environment and install dependencies
python -m venv venv
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 2. Create your local environment file, then edit it
Copy-Item .env.example .env
#    Open .env and set SECRET_KEY (any long random string for dev) and DB_* if yours differ.

# 3. Create the database (utf8mb4)
& "C:\xampp\mysql\bin\mysql.exe" -u root -h 127.0.0.1 -P 3306 `
  -e "CREATE DATABASE IF NOT EXISTS nav_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Apply migrations
python manage.py migrate

# 5. Seed demo data (idempotent â€” safe to re-run). Order matters:
python manage.py seed_core
python manage.py seed_accounts
python manage.py seed_tenants
python manage.py seed_crm
python manage.py seed_accounting
python manage.py seed_hrm
python manage.py seed_scm
python manage.py seed_inventory
python manage.py seed_procurement

# 6. Start the development server
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** and sign in with one of the [demo logins](#seed-data--demo-logins).

> The seed commands are **idempotent**: they skip records that already exist, so you can re-run them at any time.

---

## Environment variables

Defined in `.env` (copied from `.env.example`). `.env` is git-ignored â€” never commit real secrets.

| Variable | Purpose | Dev default |
|----------|---------|-------------|
| `SECRET_KEY` | Django cryptographic key. **Required**; app refuses to start in production without a real one. | a long random string |
| `DEBUG` | Debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | `127.0.0.1,localhost` |
| `DB_NAME` | Database name | `nav_erp` |
| `DB_USER` / `DB_PASSWORD` | DB credentials | `root` / *(empty)* |
| `DB_HOST` / `DB_PORT` | DB connection | `127.0.0.1` / `3306` |
| `EMAIL_BACKEND` | Email backend | console (prints to terminal) |
| `DEFAULT_FROM_EMAIL` | From address | `NavERP <no-reply@naverp.local>` |
| `STRIPE_SECRET_KEY` | Stripe test secret (`sk_test_â€¦`) | *(blank â†’ Stripe disabled)* |
| `STRIPE_PUBLISHABLE_KEY` | Stripe test publishable (`pk_test_â€¦`) | *(blank)* |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_â€¦`) | *(blank)* |
| `STRIPE_PRICE_STARTER` / `_PRO` / `_ENTERPRISE` | Recurring Price IDs (`price_â€¦`) | *(blank)* |

When `STRIPE_SECRET_KEY` **and** `STRIPE_PUBLISHABLE_KEY` are set, `STRIPE_ENABLED` becomes true and online
checkout appears; otherwise the UI shows a "configure Stripe" state and a manual **Mark as paid** action.

---

## Seed data & demo logins

Seeding creates two demo tenants (**Acme Inc** `acme`, **Globex Corporation** `globex`) with parties, org units,
employments, activities, subscriptions, invoices, branding, encryption keys, and health metrics â€” plus the domain
demo data: **CRM** (leads/opportunities/cases/â€¦), **Accounting** (GL accounts, invoices/bills/payments, bank
transactions, a recurring-invoice schedule), and **HRM** (employees, designations, leave allocations/requests,
attendance, holidays, shifts; **onboarding** templates â†’ programs with generated tasks/documents/assets/orientation;
**offboarding** separation cases with generated clearance checklists, an exit interview, and a paid final
settlement).

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| **Tenant admin** | `admin_acme` | `password` | Full Module-0 access for **Acme** |
| **Tenant admin** | `admin_globex` | `password` | Full Module-0 access for **Globex** |
| Member | `sales_acme`, `ops_acme` (and `*_globex`) | `password` | Standard, non-admin (read + profile) |
| **Superuser** | `admin` | `admin` | Django admin (`/admin/`). **`tenant=None` â†’ module pages show no data by design.** |

> **Tip:** to explore the app, log in as **`admin_acme` / `password`**. The superuser is for the Django admin only.

---

## Running the app

```powershell
python manage.py runserver          # http://127.0.0.1:8000/
python manage.py runserver 0.0.0.0:8000   # accessible on your LAN
```

Useful management commands:

```powershell
python manage.py check              # system checks
python manage.py createsuperuser    # another Django superuser
python manage.py makemigrations
python manage.py migrate
```

Forgot/reset password and invite emails are printed to the **runserver console** in development (console email
backend) â€” copy the link from there.

---

## URL / route map

| Area | Path prefix | Examples |
|------|-------------|----------|
| Dashboard | `/` | `/` |
| Auth | `/` | `/login/`, `/register/`, `/forgot-password/`, `/reset/<uidb64>/<token>/`, `/logout/` (POST) |
| Users & RBAC | `/` | `/users/`, `/roles/`, `/invites/`, `/invite/<token>/`, `/profile/` |
| Core spine | `/core/` | `/core/parties/`, `/core/org-units/`, `/core/party-roles/`, `/core/addresses/`, `/core/contact-methods/`, `/core/relationships/`, `/core/employments/`, `/core/activities/`, `/core/documents/`, `/core/audit-logs/` |
| Module 0.1 | `/tenants/` | `/tenants/subscriptions/`, `/tenants/subscription-invoices/`, `/tenants/branding/`, `/tenants/encryption-keys/`, `/tenants/health/`, `/tenants/onboarding/`, `/tenants/stripe/webhook/` |
| Module 1 (CRM) | `/crm/` | `/crm/` (overview), `/crm/leads/`, `/crm/opportunities/`, `/crm/opportunities/board/`, `/crm/territories/`, `/crm/products/`, `/crm/price-books/`, `/crm/quotes/`, `/crm/sales-quotas/`, `/crm/forecast/`, `/crm/campaigns/`, `/crm/campaign-members/`, `/crm/email-templates/`, `/crm/email-campaigns/`, `/crm/landing-pages/`, `/crm/form-submissions/`, `/crm/cases/`, `/crm/sla-policies/`, `/crm/knowledge/`, `/crm/kb-categories/`, `/crm/portal-access/`, `/crm/portal/cases/`, `/crm/tasks/`, `/crm/accounts/`, `/crm/contacts/`, `/crm/expenses/`, `/crm/projects/`, `/crm/milestones/`, `/crm/timesheets/`, `/crm/doc-templates/`, `/crm/contracts/`, `/crm/workflows/`, `/crm/workflow-logs/`, `/crm/approvals/`, `/crm/webhooks/`, `/crm/webhook-deliveries/`, `/crm/onboarding/`, `/crm/onboarding-templates/`, `/crm/health-scores/`, `/crm/surveys/`, `/crm/surveys/results/`, `/crm/stock/`, `/crm/purchase-orders/`, `/crm/partner-portal/`, `/crm/portal/` (partner-facing); public `/crm/p/<token>/` (web-to-lead), `/crm/cases/track/<token>/` (case status), `/crm/kb/<token>/` (KB article), `/crm/sign/<token>/`, `/crm/surveys/<token>/respond/` |
| Module 2 (Accounting) | `/accounting/` | `/accounting/` (dashboard), `/accounting/glaccounts/`, `/accounting/journal-entries/`, `/accounting/fiscal-periods/`, `/accounting/currencies/`, `/accounting/exchange-rates/`, `/accounting/vendor-profiles/`, `/accounting/bills/`, `/accounting/customer-profiles/`, `/accounting/invoices/`, `/accounting/recurring-invoices/`, `/accounting/payments/`, `/accounting/allocations/`, `/accounting/bank-accounts/`, `/accounting/bank-transactions/`, `/accounting/reconciliation/`, `/accounting/fixed-assets/`, `/accounting/asset-disposals/`, `/accounting/cost-allocations/`, `/accounting/payroll-runs/`, `/accounting/projects/`, `/accounting/intercompany/`, `/accounting/tax-codes/`, `/accounting/tax-returns/`, `/accounting/budgets/`, `/accounting/controls/`, `/accounting/integrations/`; reports `/accounting/reports/{trial-balance,cash-forecast,payment-schedule,ar-aging,ap-aging,balance-sheet,profit-and-loss,budget-variance}/` |
| Module 3 (HRM) | `/hrm/` | `/hrm/` (overview), `/hrm/employees/`, `/hrm/employee-documents/`, `/hrm/lifecycle-events/`; **org** `/hrm/designations/`, `/hrm/job-grades/`, `/hrm/departments/`, `/hrm/cost-centers/`, `/hrm/org-chart/`, `/hrm/company-setup/`; **onboarding** `/hrm/onboarding-templates/`, `/hrm/onboarding-template-tasks/`, `/hrm/onboarding/`, `/hrm/onboarding-tasks/`, `/hrm/onboarding-documents/`, `/hrm/assets/`, `/hrm/orientation/`; **offboarding** `/hrm/separations/`, `/hrm/exit-interviews/`, `/hrm/clearance/`, `/hrm/settlements/`, `/hrm/letters/` (+ POST `â€¦/{relieving,experience}-letter/`); **recruiting** `/hrm/requisitions/`, `/hrm/job-templates/`, `/hrm/candidates/`, `/hrm/candidate-tags/`, `/hrm/candidate-email-templates/`, `/hrm/candidate-communications/`, `/hrm/applications/`, `/hrm/interviews/`, `/hrm/interview-feedback/`, `/hrm/offers/`, `/hrm/background-checks/`, `/hrm/offer-letter-templates/` (+ public `/hrm/careers/`); **attendance** `/hrm/attendance/`, `/hrm/shifts/`, `/hrm/shift-assignments/`, `/hrm/geofences/`, `/hrm/regularizations/`; **leave** `/hrm/leave-types/`, `/hrm/leave-allocations/`, `/hrm/leave-requests/`, `/hrm/leave-encashments/`, `/hrm/leave-policy/`; **time tracking** `/hrm/timesheets/`, `/hrm/overtime-requests/`, `/hrm/reports/utilization/`, `/hrm/reports/project-time/`; **holidays** `/hrm/holidays/` |
| Module 4 (SCM) | `/scm/` | `/scm/` (overview); **procurement (4.1)** `/scm/requisitions/`, `/scm/rfqs/` (+ `â€¦/<pk>/compare/`), `/scm/quotes/`, `/scm/orders/`, `/scm/receipts/` â€” each with the CRUD triple plus lifecycle actions (requisition submit/approve/reject; RFQ send/close + quote award; PO submit/approve/send/acknowledge/amend/cancel/close; receipt receive/cancel/rematch); **SRM (4.2)** `/scm/suppliers/`, `/scm/scorecards/`, `/scm/contracts/`, `/scm/catalogs/`, `/scm/risk-assessments/` â€” CRUD + lifecycle actions (supplier submit/approve/reject/reopen/suspend; scorecard recompute/publish; contract activate/renew/terminate; catalog activate; risk submit/review); **inventory (4.3)** `/scm/items/`, `/scm/categories/`, `/scm/uoms/`, `/scm/locations/`, `/scm/lot-serials/`, `/scm/transfers/` (+ `â€¦/complete/`), `/scm/adjustments/` (+ `â€¦/post/`), `/scm/reorder-rules/`; reports `/scm/valuation/`, `/scm/reorder-alerts/`, `/scm/stock-ledger/`, `/scm/on-hand/`; **warehouse (4.4)** `/scm/putaway/` (+ `â€¦/complete/`), `/scm/picks/` (+ `â€¦/confirm/`, `â€¦/pack/`), `/scm/cycle-counts/` (+ `â€¦/start/`, `â€¦/reconcile/`), `/scm/yard/` (+ `â€¦/arrive/`, `â€¦/dock/`, `â€¦/depart/`); **orders (4.5)** `/scm/sales-orders/` (+ `â€¦/submit/`, `â€¦/release-hold/`, `â€¦/fulfill/`, `â€¦/mark-invoiced/`, `â€¦/cancel/`, `â€¦/close/`, `â€¦/from-quote/<pk>/`), `/scm/allocations/` (+ `â€¦/release/`, `â€¦/cancel/`); **transportation (4.6)** `/scm/carriers/` (+ `â€¦/recompute-scorecard/`), `/scm/loads/` (+ `â€¦/tender/`, `â€¦/book/`, `â€¦/dispatch/`, `â€¦/deliver/`, `â€¦/cancel/`), `/scm/shipments/` (+ `â€¦/book/`, `â€¦/add-event/`, `â€¦/cancel/`), `/scm/freight-invoices/` (+ `â€¦/run-audit/`, `â€¦/dispute/`, `â€¦/approve/`, `â€¦/reject/`, `â€¦/handoff/`); **demand planning (4.7)** `/scm/forecasts/` (+ `â€¦/generate/`, `â€¦/submit-review/`, `â€¦/approve/`, `â€¦/archive/`, `â€¦/revise/`), `/scm/seasonality/` (+ `â€¦/derive/`), `/scm/demand-signals/` (+ `/detect/`, `â€¦/review/`, `â€¦/apply/`, `â€¦/dismiss/`), `/scm/forecast-adjustments/` (+ `â€¦/accept/`, `â€¦/reject/`); reports `/scm/safety-stock/` (+ `/recalculate/`, `â€¦/apply/`), `/scm/forecast-accuracy/`; **manufacturing (4.8)** `/scm/work-centers/`, `/scm/boms/`, `/scm/work-orders/` (+ `â€¦/plan/`, `â€¦/release/`, `â€¦/schedule/`, `â€¦/issue/`, `â€¦/report/`, `â€¦/close/`, `â€¦/cancel/`), `/scm/time-logs/`; reports `/scm/mrp/`, `/scm/production-schedule/`; **quality (4.9)** `/scm/inspection-plans/`, `/scm/inspections/` (+ `â€¦/generate-results/`, `â€¦/start/`, `â€¦/complete/`, `â€¦/decide/`, `â€¦/quarantine/`, `â€¦/raise-ncr/`), `/scm/nonconformances/` (+ `â€¦/disposition/`, `â€¦/raise-capa/`), `/scm/capa/` (+ `â€¦/implement/`, `â€¦/verify/`), `/scm/quality-audits/` (+ `â€¦/add-finding/`, `â€¦/close/`, `â€¦/print/`); reports `/scm/coa/` (+ `â€¦/<pk>/issue/`, `â€¦/<pk>/print/`); **returns (4.10)** `/scm/returns/` (+ `â€¦/approve/`, `â€¦/reject/`, `â€¦/cancel/`, `â€¦/receive-all/`, `â€¦/draft-credit-note/`, `â€¦/draft-replacement/`, `â€¦/raise-warranty-claim/`), `/scm/return-reasons/`, `/scm/return-policies/`, `/scm/return-dispositions/` (+ `â€¦/decide/`, `â€¦/post/`, `â€¦/split/`, `â€¦/mark-refurbished/`), `/scm/warranty-claims/` (+ `â€¦/submit/`, `â€¦/record-response/`, `â€¦/record-credit/`); reports `/scm/refund-queue/`, `/scm/returns-bench/`, `/scm/return-portal/`; **analytics (4.11)** `/scm/kpi-targets/`, `/scm/kpi-snapshots/` (+ `/capture/`), `/scm/supply-alerts/` (+ `/detect/`, `â€¦/acknowledge/`, `â€¦/assign/`, `â€¦/snooze/`, `â€¦/resolve/`, `â€¦/dismiss/`); reports `/scm/inventory-analytics/`, `/scm/spend-analytics/`, `/scm/logistics-kpis/`, `/scm/margin-analytics/`, `/scm/disruption-risk/` (each + `â€¦/export/`); **contract & compliance (4.12)** `/scm/compliance-requirements/` (+ `â€¦/checks/add/`), `/scm/compliance-checks/<pk>/edit|delete/`, `/scm/trade-licenses/` (+ `â€¦/submit/`, `â€¦/approve/`, `â€¦/revoke/`, `â€¦/recompute/`), `/scm/trade-documents/` (+ `â€¦/issue/`, `â€¦/submit/`, `â€¦/accept/`, `â€¦/void/`, `â€¦/print/`), `/scm/sustainability-assessments/`; report `/scm/carbon-footprint/` (+ `â€¦/export/`); **labor management (4.14)** `/scm/labor-standards/` (+ `â€¦/activate/`, `â€¦/archive/`), `/scm/labor-sessions/` (+ `/clock-in/`, `â€¦/clock-out/`, `â€¦/close/`, `â€¦/approve/`, `â€¦/reopen/`, `â€¦/cancel/`, `â€¦/activities/add/`), `/scm/labor-activities/`, `/scm/labor-plans/` (+ `â€¦/generate/`, `â€¦/approve/`, `â€¦/archive/`), `/scm/labor-plan-lines/<pk>/edit/`; reports `/scm/labor-board/` (+ `/assign/`, `/unassign/`), `/scm/labor-payroll-export/` (+ `?format=csv`), `/scm/labor-scorecard/`; **cold chain (4.15)** `/scm/cold-chain-monitors/` (+ `/detect/`, `â€¦/detect/`, `â€¦/profile/`, `â€¦/readings/add/`, `â€¦/readings/import/`), `/scm/temperature-readings/` (list + detail only â€” **no edit, no delete: the log is append-only**), `/scm/temperature-excursions/` (+ `â€¦/acknowledge/`, `â€¦/assess/`, `â€¦/close/`, `â€¦/dismiss/`, `â€¦/raise-work-order/`); reports `/scm/cold-storage-report/`, `/scm/cold-chain-compliance/` (+ `?format=csv`), `/scm/reefer-board/`; **public** `/scm/return-tracking/<token>/` (+ `â€¦/label/`) |
| Django admin | `/admin/` | `/admin/` |

Each CRUD resource follows the pattern: list (`/`), create (`/add/`), detail (`/<pk>/`), edit (`/<pk>/edit/`),
delete (`/<pk>/delete/`, POST).

---

## Stripe billing (test mode)

Billing is fully functional **without** Stripe â€” use the manual **Mark as paid** action on a subscription. To
enable hosted online checkout:

1. In your Stripe **test** dashboard, create recurring Prices for the paid plans and copy their `price_â€¦` IDs.
2. Put the keys and Price IDs in `.env` (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
   `STRIPE_PRICE_STARTER/PRO/ENTERPRISE`).
3. Configure a webhook endpoint pointing at `â€¦/tenants/stripe/webhook/` and put its signing secret in
   `STRIPE_WEBHOOK_SECRET`. For local testing use the Stripe CLI:
   ```powershell
   stripe listen --forward-to 127.0.0.1:8000/tenants/stripe/webhook/
   ```
4. Restart the server.

Handled events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
`customer.subscription.updated`, `customer.subscription.deleted`. The webhook **verifies the Stripe signature**
on every request, is **idempotent** (safe under Stripe retries), matches events to records only via Stripe-issued
ids, and returns **400** for any unsigned/forged payload. It is the only CSRF-exempt endpoint. No card data ever
touches the application (Stripe-hosted checkout; only opaque `stripe_*_id`s are stored).

---

## Testing

```powershell
python -m pytest                 # full suite
python -m pytest apps/tenants    # one app
python -m pytest -k webhook -v   # by keyword
```

- **8,895 tests** run under **`config.settings_test`** (SQLite in-memory) via `pytest.ini` â€” they **never** touch
  the MySQL dev database. Per-module suites: **core 118**, **accounts 95**, **tenants 108**, **CRM 2,114**,
  **Accounting 212**, **HRM 3,838**.
- Coverage spans: model invariants & `__str__`, form validation, full CRUD via the test client, **multi-tenant
  IDOR (cross-tenant â†’ 404)**, auth flows (email-or-username, bad creds, POST-only logout), permission gating
  (member â†’ 403), forgot-password non-enumeration, invite token/expiry, encryption-key secrecy, branding hex
  validation, the Stripe webhook signature rejection, **double-entry GL invariants + posting/void workflows**
  (Accounting), the **leave-request approval state machine + derived balances** (HRM), the recurring-invoice
  cadence/generation + cash-forecast projection, and the **offboarding lifecycle** (separationâ†’clearanceâ†’F&Fâ†’letters
  state machine, derived `net_payable`/`all_mandatory_cleared`, the idempotent clearance-checklist + bounded-query
  leave-encashment services, and `@tenant_admin_required` gating on every workflow action).

---

## Project structure

```
NavERP/
â”œâ”€ config/                  Django project
â”‚  â”œâ”€ __init__.py           PyMySQL driver + MariaDB 10.4 shim
â”‚  â”œâ”€ settings.py           apps, middleware, custom user, DB, sessions, Stripe, email
â”‚  â”œâ”€ settings_test.py      SQLite in-memory (pytest)
â”‚  â”œâ”€ urls.py               root URLconf
â”‚  â””â”€ wsgi.py / asgi.py
â”œâ”€ apps/
â”‚  â”œâ”€ core/                 Tenant spine, middleware, navigation, crud helpers, audit
â”‚  â”‚  â”œâ”€ models/ forms/ views/         PACKAGES â€” FLAT entity files (Module 0 has no sub-modules)
â”‚  â”‚  â”‚  â””â”€ Party.py Tenant.py â€¦       models/forms/views line up 1:1; _base.py/_common.py hold the
â”‚  â”‚  â”‚                                shared plumbing (TenantModelForm lives in forms/_common.py)
â”‚  â”‚  â”œâ”€ urls.py            kept flat â€” a crud(slug, name) factory generates the 5 routes per model
â”‚  â”‚  â”œâ”€ crud.py  middleware.py  decorators.py  navigation.py  search.py
â”‚  â”‚  â”œâ”€ context_processors.py  utils.py  admin.py
â”‚  â”‚  â”œâ”€ management/commands/seed_core.py
â”‚  â”‚  â””â”€ tests/
â”‚  â”œâ”€ accounts/             User/Role/Permission/UserInvite, auth, RBAC
â”‚  â”‚  â”œâ”€ models.py  managers.py  backends.py  forms.py  views.py  urls.py  admin.py
â”‚  â”‚  â”œâ”€ management/commands/seed_accounts.py
â”‚  â”‚  â””â”€ tests/
â”‚  â”œâ”€ tenants/              Module 0.1 â€” subscriptions/billing/branding/keys/health + Stripe
â”‚  â”‚  â”œâ”€ models/ forms/ views/         PACKAGES â€” FLAT entity files (Subscription.py, EncryptionKey.py â€¦)
â”‚  â”‚  â”œâ”€ urls.py  stripe_utils.py  admin.py     (urls kept flat â€” small + explicit)
â”‚  â”‚  â”œâ”€ management/commands/seed_tenants.py
â”‚  â”‚  â””â”€ tests/
â”‚  â”œâ”€ dashboard/            KPI aggregation (no models)
â”‚  â”œâ”€ crm/                  Module 1 â€” CRM (leads/opportunities/cases/â€¦ + 1.7â€“1.12)
â”‚  â”‚  â”œâ”€ models/ forms/ views/ urls/   PACKAGES â€” one folder per sub-module (1.1â€“1.12), one file per entity
â”‚  â”‚  â”‚  â””â”€ <SubModule>/<Entity>.py    e.g. SalesForceAutomation/Quotes.py  (each __init__ re-exports all)
â”‚  â”‚  â”œâ”€ analytics.py  admin.py        (single-purpose modules stay flat)
â”‚  â”‚  â”œâ”€ management/commands/seed_crm.py
â”‚  â”‚  â””â”€ tests/
â”‚  â”œâ”€ accounting/           Module 2 â€” GL ledger, AP/AR, cash, recurring invoicing + advanced 2.6â€“2.15
â”‚  â”‚  â”œâ”€ models/ forms/ views/ urls/   PACKAGES â€” one folder per sub-module (2.1â€“2.15), one file per entity
â”‚  â”‚  â”‚  â””â”€ <SubModule>/<Entity>.py    e.g. AccountsReceivable/Invoices.py  (the old *_advanced.py files folded in)
â”‚  â”‚  â”œâ”€ admin.py
â”‚  â”‚  â”œâ”€ management/commands/seed_accounting.py
â”‚  â”‚  â””â”€ tests/
â”‚  â””â”€ hrm/                  Module 3 â€” employees, onboarding, offboarding, leave, attendance, holidays
â”‚     â”œâ”€ models/ forms/ views/ urls/   PACKAGES â€” one folder per sub-module (3.1â€“3.41), one file per entity
â”‚     â”‚  â””â”€ <SubModule>/<Entity>.py    e.g. LeaveManagement/Request.py; each <SubModule>/_helpers.py holds
â”‚     â”‚                                that sub-module's private helpers (entity â†’ _helpers â†’ _base)
â”‚     â”œâ”€ services.py        request-free domain logic (task/clearance generation, leave encashment)
â”‚     â”œâ”€ analytics.py  admin.py        (single-purpose modules stay flat)
â”‚     â”œâ”€ management/commands/seed_hrm.py
â”‚     â””â”€ tests/
â”‚  â””â”€ scm/                  Module 4 â€” supply chain (4.1 procurement: PR â†’ RFQ â†’ PO â†’ GRN + 3-way match)
â”‚     â”œâ”€ models/ forms/ views/ urls/   PACKAGES â€” ProcurementManagement/<Entity>.py (one file per entity)
â”‚     â”œâ”€ admin.py           (single-purpose modules stay flat)
â”‚     â”œâ”€ management/commands/seed_scm.py
â”‚     â””â”€ tests/             668-test suite (models/forms/views/security)
â”œâ”€ templates/
â”‚  â”œâ”€ base.html  base_auth.html
â”‚  â”œâ”€ partials/             sidebar, topbar, footer, messages, pagination, customizer
â”‚  â”œâ”€ registration/         login, register, forgot/reset password, invite accept
â”‚  â”œâ”€ core/ accounts/ tenants/ dashboard/   foundation CRUD pages (entity-folder layout, flat at app root)
â”‚  â””â”€ crm/ accounting/ hrm/                  domain CRUD pages, one folder per sub-module â†’ per entity:
â”‚                                            <app>/<submodule>/<entity>/<page>.html (page = list/detail/form)
â”œâ”€ static/
â”‚  â”œâ”€ css/theme.css         design system (component classes, dark mode, layout variants)
â”‚  â”œâ”€ js/layout.js          layout customizer (persists to localStorage)
â”‚  â”œâ”€ js/app.js             icons, nav, âŒ˜K search, toasts
â”‚  â””â”€ img/logo.svg
â”œâ”€ conftest.py              shared pytest fixtures
â”œâ”€ requirements.txt  pytest.ini  manage.py
â”œâ”€ .env.example  .gitignore
â”œâ”€ NavERP.md  NavERP-ERD.md   planning docs
â””â”€ README.md
```

---

## Design system & layout variants

The look mirrors a clean, airy "Tailwick"-style admin theme, re-branded to NavERP. `static/css/theme.css` defines
the component classes every template uses: `.page-header/.page-title/.breadcrumb`, `.card/.card-header/.card-body`,
`.stat-card`, `.btn` (+ `-primary/-outline/-danger/-icon`), `.badge` (+ green/red/amber/info/muted/slate),
`.table/.table-wrap/.table-actions`, `.form-*`, `.empty-state`, `.pagination`, `.avatar-initial`,
`.progress/.progress-bar`, and `.detail-grid`.

The topbar gear opens a **customizer** (state persisted to `localStorage`, applied before first paint to avoid
flashes) supporting:

- **Layout:** vertical Â· horizontal Â· detached
- **Mode:** light Â· dark
- **Width:** fluid Â· boxed
- **Sidebar size:** default Â· compact Â· small-icon Â· icon-hovered
- **Sidebar color:** light Â· colored
- **Topbar:** light Â· dark
- **Topbar position:** fixed Â· scrollable
- **Direction:** LTR Â· RTL
- **Preloader:** on Â· off

The sidebar is generated from `apps/core/navigation.py` (`MODULE_CATALOG`): built sub-modules link to live pages;
the rest render as "On the roadmap" placeholders.

---

## Data model

Foundation entities (the Module-0 subset of the full ERD in [`NavERP-ERD.md`](NavERP-ERD.md)). Every business
table also carries `tenant`.

| App | Model | Purpose |
|-----|-------|---------|
| core | `Tenant` | A customer workspace (name, slug, plan, active) |
| core | `Party` | One person/organization; roles attached separately |
| core | `PartyRole` | customer/vendor/supplier/employee/lead/contact/partner |
| core | `Address`, `ContactMethod` | Party addresses & contact points |
| core | `PartyRelationship` | employee_of / contact_of / subsidiary_of / reports_to |
| core | `OrgUnit` | company/branch/department/team/cost-center tree |
| core | `Employment` | the HR view of an employee party (job, dept, manager) |
| core | `Activity` | generic task/call/email/meeting/note (GenericFK) |
| core | `Document` | generic file attachment (GenericFK, classification, version) |
| core | `AuditLog` | append-only change history (GenericFK, JSON diff) |
| accounts | `User` | custom user; email-or-username login; nullable tenant |
| accounts | `Role`, `Permission` | per-tenant roles bundling a global permission catalog |
| accounts | `UserInvite` | tokenized, expiring workspace invitations |
| tenants | `Subscription` | plan/status/seats/renewal + Stripe ids |
| tenants | `SubscriptionInvoice` | SaaS billing line (`SINV-#####`) |
| tenants | `BrandingSetting` | per-tenant logo + hex colors |
| tenants | `EncryptionKey` | prefix + SHA-256 only; reveal-once secret |
| tenants | `HealthMetric` | per-tenant usage/health series |

> Note: the platformâ†’tenant billing models (`Subscription`/`SubscriptionInvoice`) are deliberately distinct from
> the tenant's own AR/AP `Invoice`, which arrives with the Accounting module.

---

## Security posture

Implemented in the foundation:

- **Tenant isolation** on every query; cross-tenant access returns 404 (verified by tests).
- **AuthZ**: `@tenant_admin_required` on all Module-0 admin writes; `@login_required` elsewhere; POST-only,
  CSRF-protected deletes; tenant-less users blocked from creating orphan records.
- **CSRF** on every state-changing form; the **only** exemption is the signature-verified Stripe webhook.
- **No XSS / SQL-injection vectors**: Django auto-escaping throughout (no `|safe`/`mark_safe`), chart data via
  `json_script`, ORM-only queries (no raw SQL); branding colors are hex-validated at the form **and** model layer.
- **Secrets**: passwords hashed (PBKDF2) and excluded/write-only in forms; the encryption-key plaintext is shown
  once and never stored (prefix + SHA-256 only); invite tokens are 256-bit `secrets.token_urlsafe`; `.env` is
  git-ignored.
- **Account safety**: email-or-username backend with timing-attack mitigation; forgot-password does not reveal
  whether an email exists; safe-`next` login redirect (no open redirect).
- **Uploads**: `Document` uploads are extension-allowlisted and size-capped (20 MB).
- **Sessions/headers**: HttpOnly + SameSite cookies, idle timeout (30 min) + absolute lifetime (12 h),
  `X-Frame-Options: DENY`; HSTS + secure cookies + SSL redirect auto-enabled when `DEBUG=False`.

---

## Production hardening checklist

Before deploying:

- [ ] Set a strong, unique **`SECRET_KEY`** and **`DEBUG=False`** (the app refuses to start in production
      without a real key).
- [ ] Set **`ALLOWED_HOSTS`** to your real domain(s) and serve over **HTTPS** (HSTS/secure cookies activate
      automatically when `DEBUG=False`).
- [ ] Move **`MEDIA_ROOT` outside the web root** (out of `htdocs`) so uploaded files can't be executed by Apache;
      serve media/static via a proper web server / `collectstatic`.
- [ ] Add **login rate-limiting / lockout** (e.g. `django-axes`) â€” intentionally not bundled in the foundation.
- [ ] Use a managed **MariaDB â‰¥ 10.5 / MySQL 8** in production (the 10.4 shim is for local XAMPP).
- [ ] Configure a real **SMTP** email backend.
- [ ] **Roadmap (Module 0.4):** MFA (TOTP/WebAuthn passkeys), SSO/SAML/OIDC, adaptive/risk-based auth, and
      subdomain-per-tenant routing.

---

## Module roadmap (0â€“13)

| # | Module | App slug | Status |
|---|--------|----------|--------|
| 0 | System Admin & Security | `core` + `accounts` + `tenants` + `dashboard` | ✅ Foundation built (0.1 complete) |
| 1 | Customer Relationship Management (CRM) | `crm` | ✅ 1.1–1.12 built (leads, **1.2 SFA recreated in detail: opportunities + splits + Kanban board, product catalog + price books + quote builder, territories + sales quotas + forecast dashboard**, **1.3 marketing automation recreated in detail: campaigns + members + email templates/campaigns + landing pages + public web-to-lead form submissions**, **1.4 customer service recreated in detail: cases (SLA policies/breach + conversation thread + CSAT) + knowledge base (categories/feedback) + customer self-service portal + public case-status/KB pages**, tasks, accounts/contacts; expenses, projects/milestones/timesheets, doc templates/contracts+e-sign, workflow rules/approvals, onboarding/health/surveys, stock/POs/partner portal) |
| 2 | Accounting & Finance | `accounting` | ✅ 2.1–2.15 built (dashboard + cash-forecast; GL: chart of accounts, journal entries, fiscal periods, currencies/FX; AP/AR: vendor/customer profiles, bills, invoices, recurring invoicing, payments + cash application, aging, payment schedule; Cash: bank accounts, CSV import, reconciliation; **advanced** — Fixed Assets + depreciation/disposal, Cost Allocation, Payroll journal, Project/Job Costing, Intercompany, Tax codes/returns, Balance Sheet/P&L/Scheduled reports, Budgeting + variance, Internal Controls, Integrations) |
| 3 | Human Resource Management (HRM) | `hrm` | 🟨 3.1–3.21 built — 21 of 41 sub-modules (**employee management** — full personnel-file profiles on `core.Party`/`core.Employment` with a document vault [verify/reject + expiry + confidential] and a dated lifecycle/job-history timeline; **organizational structure** — job grades + designations (salary bands/JD), department & cost-center companion profiles (head/owner/budget) on `core.OrgUnit`, a derived org chart + company-setup view; **employee onboarding** — reusable templates → per-hire programs with auto-generated tasks, document/e-sign tracking, asset issue/return, orientation scheduling; **employee offboarding** — separation cases driving resignation→approval→clearance→F&F→completion with auto-generated department clearance (asset-return on clear), exit interviews, full-&-final settlement with derived net payable, and relieving/experience letter print views; **job requisition** — a `JobRequisition` authorization-to-hire hub with budget/headcount/JD, a sequential `RequisitionApproval` chain (draft→pending→approved→posted→filled), reusable `JobDescriptionTemplate` copy-on-apply, and clone; **candidate management** — an ATS `CandidateProfile` (on `core.Party`) + talent-pool tags/skills, a `JobApplication` pipeline against requisitions with auto-firing recruiting email templates + an append-only communication log, and a public unauthenticated career portal; **interview process** — `Interview` scheduling (mode/status machine + reschedule) with an `InterviewPanelist` panel (role + RSVP) and structured `InterviewFeedback` scorecards (per-competency 1–5 ratings + hire recommendation), candidate invites/reminders reusing the recruiting email pipeline; **offer management** — an `Offer` (`OFR-`) over the `JobApplication` with a compensation breakdown + workflow status machine (draft→pending_approval→approved→extended→accepted/declined/rescinded/expired), an `OfferApproval` chain gating extension (auto-built Hiring-Manager→HR + Executive for high-value offers), offer acceptance driving the application to `hired` + raising a pre-boarding checklist, a `BackgroundVerification` (`BGV-`) status/result lifecycle with consent gate, `PreboardingItem` document collection, and a reusable `OfferLetterTemplate` (`OLTMPL-`) merge-rendering a printable letter; **attendance** with shifts + late detection, **geofencing** GPS zones + **regularization** approval workflow; **leave** types/allocations/requests with derived balances + approval, a **Leave Policy engine** (accrual/carry-forward runs) + **encashment** payout workflow; **time tracking** — weekly timesheets with inline entries + derived hours against `accounting.Project`, billable/utilization + project-time reports, overtime requests; public-holiday calendar; **salary structure** (pay-component catalog + grade CTC templates + effective-dated assignments), **payroll processing** (payslip computation + draft→approved→locked handing totals to `accounting.PayrollRun`), **statutory compliance** (PF/ESI/PT/TDS/LWF config + per-scheme returns register), **tax & investment** (old/new regime slabs + investment declarations/proofs + a Form-16 computation engine), **payout & reports** (disbursement batches from a locked cycle + masked-bank payments + UTR reconciliation + payslip distribution), **goal setting** (OKR periods/objectives/key-results/check-ins with cascade alignment + weighted progress/health), **performance review** (appraisal cycles with a 6-phase machine, self/manager/peer/upward reviews, derived + calibrated ratings, a calibration board, and subject/reviewer/admin-only confidentiality), **continuous feedback** (real-time kudos/appreciation/constructive feedback + a request-pull workflow + anonymous-giver masking, 1:1 meetings with shared/manager-private notes + action items, and a computed feedback dashboard), and **performance improvement** (Performance Improvement Plans with an HR-approval workflow + scheduled check-ins, progressive warning letters with an issue/acknowledge workflow + a printable letter, and manager-only coaching notes — the strictest confidentiality in the system: the coached employee never sees notes about themselves) [3.13–3.21]; idempotent `seed_hrm`). Next: 3.22 |
| 4 | Supply Chain Management (SCM) | `scm` | ✅ **COMPLETE — 4.1–4.19, all 19 sub-modules.** **4.19 integration & API gateway** closes the module: five NavERP bullets over four models, because ERP / e-commerce / IoT / EDI are one object under four labels — a configured connection to another system — sharing one `IntegrationEndpoint` (`CNX-`) discriminated by `category`, with four category-pinned route names resolving to a single view through Django's extra-options dict. Beside it sit an append-only `IntegrationMessage` (`MSG-`) exchange log carrying the X12 document vocabulary and a self-FK linking a 997 to what it acknowledges, and a `WebhookSubscription` (`WHK-`) / `WebhookDelivery` pair whose SCM trigger vocabulary is exactly what `crm.Webhook` cannot express. **The sub-module ships no transport** — no `requests`/`urllib`/`httpx` import exists anywhere in it and a test asserts that — which is what makes prefix + SHA-256 credential storage correct *here*: the plaintext is never needed, so the column is a configuration marker rather than a credential store, and the docs record that a future transport pass must move to encryption at rest rather than revert to plaintext. 4.17's `LogisticsClient` keeps the partner's EDI interchange identity and 4.19 reads it through the FK, refusing a duplicate typed value rather than dropping it silently. **4.18 finance & accounting integration** — the money layer, and its central ruling is one of *subtraction*: three of its five NavERP bullets — Accounts Payable, Accounts Receivable, Budgeting — are **READ-ONLY COMPUTED registers with no table**, because what we owe and what we are owed already exist as pointers into `apps/accounting` from six shipped models (4.1 `GoodsReceiptNote.bill`, 4.6 `FreightInvoice.bill`, 4.18 `LandedCostVoucher.bill`; 4.5 `SalesOrder.invoice`, 4.17 `ClientBillingRun.invoice`, 4.10 `ReturnAuthorization.credit_note` [`RMA-`]), so an AP/AR/Budget table here would be a second copy of the same money that drifts the first time Accounting voids something (L29). The one genuinely new capability is **Landed Cost**: a `LandedCostVoucher` (`LC-`) over a 4.1 goods receipt, carrying typed `LandedCostCharge` cost lines (freight, customs duty, brokerage, insurance, drayage, port fees…), which `allocate()` spreads across the receipt's inbound `StockMove`s by value / quantity / weight / volume / equal as an **ADDITIVE layer over the append-only ledger** — it never edits a move, it rolls `Item.average_cost` via `apply_landed_cost()` and records each share as an `editable=False` `LandedCostAllocation` row that the 4.3 valuation and 4.18 variance reports read directly. `allocate()` is **idempotent** (it reverses its prior average-cost roll before re-spreading), the verb ladder runs draft → allocated → accrued → reconciled (+ cancel while unbilled), and `draft_bill()` drafts an `accounting.Bill` for the payee and **stops** — SCM posts no journal entry (L29). A `DutyTariff` (`DTY-`) is the effective-dated **customs-duty master** keyed by HS code × country-of-origin × start date, resolved most-specific-wins by `rate_for()` (a named origin beats the blank any-origin fallback, newest first, returns `None` rather than raising) and **snapshotted onto the charge** so a re-rate next quarter never rewrites what a shipment cleared customs at — it exists because `accounting.TaxCode` structurally cannot be a customs master (no customs `tax_type`, no `hs_code`, no origin pair), while sales/VAT/GST stays `accounting.TaxCode`, FK'd from the charge line. Migration 0031; idempotent `_seed_finance_tenant`. **4.17 third-party logistics (3PL)** — the warehouse-as-a-service layer, and the sharpest example yet of deriving rather than storing: two of its five NavERP bullets are COMPUTED PAGES with no table, because client inventory segregation and warehouse rental are *questions about existing stock*, not new stock. A `LogisticsClient` (`3PL-`) is commercial configuration hanging off `core.Party` — never a second company table — carrying the billing cycle, the monthly minimum, the shared/dedicated `space_model` and the five-way `storage_billing_method` (calendar / anniversary / split-month / average-daily / snapshot) that separates a real 3PL system from a generic WMS. Segregation is delivered by two nullable `owner_client` columns on `Item` and `Location` (indexed `(tenant, owner_client)` in 0030) and a report that reads the **existing** append-only `StockMove` ledger; no owner column was added to `StockMove` itself, because an owner on an append-only ledger is a second source of truth. A `ClientRateCard` (`TAR-`) is the versioned tariff over a 14-value `charge_basis` vocabulary, and a `ClientBillingRun` (`CBR-`) is an Infoplus-style reviewable worksheet whose quantities are **derived** from receipts, picks, shipments and the ledger, then approved into a **draft** `accounting.Invoice` — SCM posts no journal entry (L29). The hand-off writes a pre-computed `amount` with quantity × rate in the description rather than the natural `quantity`/`unit_price` pair, because `InvoiceLine.unit_price` is `Decimal(14,2)` against a `Decimal(14,4)` rate and a `0.0450`/pallet-day storage rate would silently round to `0.05` — an ~11% over-bill on every storage line. Charge bases that are priceable but **not measurable today** (per-kg, per-sqft, per-cbm) write their lines with `needs_manual_quantity=True` and a description naming the missing measurement instead of guessing a conversion, and `per_pallet_position` bills stock units 1:1 while *saying so* on the line — a stated approximation, never a hidden one. A `ClientSLA` (`SLA-`) measures per-client targets from operational rows and distinguishes `no_data` from *meeting*, so an unmeasurable window never reads as success; its service credits are graduated, capped, and **suggested only** — nothing is auto-credited. **Client Integration** ships as non-secret partner identifiers only (`integration_mode`, `edi_partner_id`, `edi_qualifier`); no API key, token or endpoint credential is stored anywhere, with real credential handling and EDI transport deferred to 4.19. **4.16 customer portal** — the self-service layer, and like 4.14 mostly an exercise in *not* re-declaring what already exists: two of its five NavERP bullets are COMPUTED PAGES with no table at all. 4.16 owns no order (4.5), no shipment or POD (4.6), no item or catalog (4.3), no invoice (`accounting`) and no helpdesk (CRM) — `portal_order_tracking` earns its place purely by JOINING 4.5 to 4.6 in one row, which neither module's own list shows. A `PortalAccount` (`PAC-`) is the per-customer entitlement record and **deliberately not a login**: users bind through the already-shipped `crm.CustomerPortalAccess`, because a second SCM-side binding could disagree with CRM's about *which party a user is*, and whichever page read it would decide whose orders and invoices that user saw — an authorisation bug by construction rather than a data-quality issue. It carries Sana-style stock presentation (hidden / availability text / colour band / exact), a customer-scoped catalogue, and a `price_basis` that resolves the customer's own last-ordered price **at render time** because no customer price master exists yet and a stored copy would quietly become a quote nobody agreed to. `visibility_scope` was designed and **deliberately not built**: honouring "buyers see only their own orders" needs a portal originator on `SalesOrder` that 4.5 does not record, and shipping a switch that silently does nothing is worse than omitting it — an administrator who sets it believes their buyers are separated when they are not. A `PortalOrderInquiry` (`PIQ-`) **wraps `crm.Case`** rather than forking the helpdesk, inheriting the thread, SLA clocks, CSAT and ownership and adding only the supply-chain context and outcome; `open_for()` is the single writer of that case, so the staff path, the portal path and the seeder cannot drift. A `PortalDocumentShare` (`PDS-`) is the sub-module's one genuinely new idea: an **expiring, revocable, download-audited** pointer at an invoice, a POD, a trade document, a contract or a CoA — the explicit fix for the residual risk 4.10 documented on its own never-expiring token. Its authorisation rule is that the target must belong to this tenant **and** to this account's customer, checked in `clean()` **and re-checked in the download view**, because validation that only runs on a form is not an access control; where nothing on the target names an owner it **refuses**, since "cannot be proved to be theirs" is not "is theirs". The token download takes its tenant **off the object** (`request.tenant` is `None` for an anonymous visitor), re-checks tenant and account active state, enforces revoke+expiry **inside the lookup** so a dead token is indistinguishable from a wrong one, and **streams via `FileResponse`** — `config/urls.py` serves `MEDIA_URL` directly under `DEBUG`, so redirecting to `.url` would make the token decorative. `expires_at` and `revoked_at` are treated as **halves of one control** and gated identically (`portaldocumentshare_edit` is tenant-admin, matching `revoke`), because blanking an expiry means *never expires* on a share only an admin may revoke — the same privilege-escalation shape a sibling review found on a decision field elsewhere. `PortalActivity` is an append-only log of customer **reads**, which `core.AuditLog` structurally cannot express (its actions are create/update/delete only), so it ships list+detail only with a fully read-only admin — the `StockMove`/`MeterReading` posture. It records `REMOTE_ADDR` only, never `X-Forwarded-For`, which is caller-controlled with no trusted-proxy list configured. 4.16 posts **no `StockMove` and no `JournalEntry`**, and dispatches **no notifications** — the channel preferences store intent for the day a mailer exists. **4.15 cold chain management** — three of its five NavERP bullets are COMPUTED PAGES rather than tables, which is the headline fact about it. `ColdChainMonitor` (`CCM-`) is one device watching exactly one thing — a `Location`, an `Asset` or a `Shipment`, three typed PROTECT FKs and never a `GenericForeignKey` — against limits that may legitimately be one-sided; there is no device master, no cold-room table and no reefer table, because 4.3 already owns the location hierarchy and 4.13 already owns the asset. `TemperatureReading` is an APPEND-ONLY interval log with no edit view, no delete view and a read-only admin (the `StockMove`/`MeterReading` posture): a wrong reading is corrected by filing a later, correct one. Every column on a `TemperatureExcursion` that states a measurement is `editable=False` and has exactly ONE writer — `coldchain.detect_excursions()`, which takes `select_for_update()` on the MONITOR row before reading anything, so the "one open episode per monitor" rule is a lock rather than a constraint MariaDB would silently omit. **No temperature ever passes through `q2()`/`q4()` and no temperature column carries `MinValueValidator(ZERO)`**: `value or ZERO` turns a blank cell into a perfectly plausible 0 °C, and −18 °C is the normal operating point of half the sub-module — the importer SKIPS and COUNTS an unreadable row instead of substituting a number. Mean kinetic temperature is weighted by each row's own snapshotted logging interval (a hot hour weighs an hour, not "one row") and returns **None, never 0**, on every frozen/deep-frozen/cryogenic monitor, because USP <1079.2> says MKT does not apply to frozen product. Cold Storage Inventory is 4.3 filtered — on-hand from the ledger, mismatch from the two `storage_condition` columns, expiry and quarantine from `LotSerial`, whose status **4.9 writes and 4.15 only reads**. Maintenance of Reefers is a board over 4.13 in which a reefer is DERIVED as *an asset with an active monitor*, so `Asset.ASSET_TYPE_CHOICES` gains no `reefer` value that could go stale. The compliance report carries an explicit NON-CLAIM: it is an audit trail, not a validated 21 CFR Part 11 / EU Annex 11 system. **4.14 labor management** — the warehouse labour layer, and mostly an exercise in *not* declaring things other modules already own. HRM owns daily attendance (`hrm.AttendanceRecord` is unique per tenant+employee+date, with punches, geofence and biometric source), so 4.14 ships no second attendance table: a `LaborSession` (`LSN-`) is the layer *beneath* it — a shift at a warehouse whose minutes are split into booked activity intervals, which is what an LMS measures and what a one-row-per-day record structurally cannot hold. `work_date` deliberately shares `AttendanceRecord.date`'s grain so the two reconcile in a report **without a FK**; `apps/scm` still contains **zero** `hrm.*` references. 4.4 already owns the tasks, so Task Assignment is a **computed console** (`scm:labor_board`) over the `assigned_to` column `PickTask`/`PutawayTask`/`CycleCountTask` already carry — 4.14 declares no task table and adds no second assignee column, and migration `0024` containing no `AddField` at all is the evidence. A `LaborStandard` (`LST-`) is the keystone the other ten LMS products all lead with: multi-determinant (fixed setup + travel + per-unit rate + PF&D allowance), scoped by location/item-category and dated, resolved most-specific-wins by `select_standard()` — which returns **`None`, never a zero standard**, because an unmeasured job that reads as a failing one is worse than no measurement. Every `LaborActivity` (`LAB-`) **snapshots** its standard's determinants at file time, so editing a standard next month cannot silently rewrite last month's measured performance; resolution happens once, in the create path, and `save()` never re-resolves. Direct vs indirect is paired validation in both directions (an indirect row *requires* a coded reason, SAP EWM's rule), because an uncoded hour is an hour nobody can act on. Every productivity figure — units per hour, performance, utilisation, accuracy, gap time — is a **derived aggregate answering `None` on a zero denominator**, and gap time's opposite (booked exceeding attended) gets its own figure so the page names the exception instead of printing a negative gap. A `LaborPlan` (`LPL-`) follows 4.7's generate-then-review shape, deriving volume from the `StockMove` ledger, picked lines, received lines or a linked 4.7 forecast **at generate time, never from a stored history table** — and excluding `consumption`/`production`/`maintenance` moves, because manufacturing and MRO draws are not warehouse in/out work and staffing a building for them would staff it for work that never arrives at its doors. Its horizon guard measures the span by **integer arithmetic on the two dates** rather than by building the range and taking its `len()` (a bound that computes the thing it is bounding is not a bound), and the line-count guard is one `COUNT(*)` taken *before* anything is allocated. Payroll Integration is a **read-only CSV hand-off** over approved sessions only, writing nothing to `hrm.*` or `accounting.*`: `accounting.PayrollRun` is a whole-company period accrual with no employee lines and no hours columns, so "drafting" one from warehouse labour would be wrong rather than merely redundant — the contrast with 4.6's freight audit, which *does* draft an `accounting.Bill`, is that a Bill has lines and a payee. 4.14 posts **no `StockMove` and no `JournalEntry` at all**. **4.13 asset management** — SCM builds the `Asset` anchor `NavERP-ERD.md` had described from the beginning and nothing had ever created, exactly as 4.3 built `Item`/`Location`/`StockMove`; Module 11 extends `scm.Asset` by FK rather than declaring a second one. A `MaintenancePlan` (`PM-`) carries Oracle's four forecast methods verbatim (calendar / meter / combined / condition) plus SAP's cycle-and-shift-factor machinery reduced to the one bit that changes behaviour, `schedule_basis` floating-vs-fixed. Its schedule has exactly **one writer**, the completion verb: generating a job deliberately does *not* roll it, because rolling in both places advanced a fixed plan by two cycles per occurrence (Jan 1 → Apr 1 at generate → Jun 30 at completion, the April inspection silently never coming due), because `floating` is *defined* as measured from the last completion rather than from when the paperwork was raised, and because a generated job later cancelled must not consume a cycle nobody performed. A `MaintenanceWorkOrder` (`MWO-`) is **not** 4.8's `WorkOrder` (`WO-`) — a production run carries item/BOM/quantities/component+output locations, none of which a repair has, and overloading it would corrupt MRP netting, the load board and OEE — but it **is** one table for requests, PM jobs and breakdowns, because `status="requested"` plus `reported_by` IS the intake and a split would fork every MTTR and downtime query. Its `status` is `editable=False` and verb-driven, so a crafted `status=completed` is impossible by construction rather than by filtering. Failure analysis uses **Maximo's problem → cause → remedy hierarchy as a CLOSED vocabulary**, which is exactly what makes "which cause costs us the most downtime" answerable with a `GROUP BY` and no sensor stack at all. Every reliability figure is derived and an honest one answers **`None`, never `0`**: an MTBF of 0h reads as "fails constantly", the precise opposite of a machine that has never failed — and MTTR counts only repairs whose downtime window was actually closed, since counting untimed ones would make the fleet look *faster* to fix the worse the record-keeping got. `MeterReading` is append-only on the `StockMove` precedent (no edit, no delete — a wrong reading is corrected by a later one), because meter-based due dates, usage trends and condition triggers need the history rather than a mutable last value with two writers; its `source`/`reference` are stamped by whichever verb files it rather than typed, so a member cannot forge a system-filed reading onto somebody else's job. Spare Parts Inventory adds **no `SparePart` table** — it is a computed view of 4.3's one `Item` master plus one additive boolean — and issuing parts is the sub-module's only ledger write: a new `maintenance` `StockMove` type kept out of `COGS_MOVE_TYPES` (a spare fitted to your own machine is upkeep, not the cost of a good you sold) and equally out of `issue` (which 4.7 reads as customer demand, so booking MRO draws there would inflate every forecast), while still counting as movement for dead-stock recency — a distinction that had to be split into a second constant after the shared one classified every actively-consumed spare as dead and filed persisted alert rows saying so. Asset Depreciation READS `accounting.FixedAsset` and reports unlinked assets as an explicit coverage count rather than a confident zero; SCM stores no depreciation figure and posts no `JournalEntry` (L29). **4.12 contract & compliance management** — built by *subtraction* as much as addition: 4.2's `SupplierContract` already WAS the contract repository (parties, NDAs/SLAs/master agreements, renewal windows, a `core.Document` FK), 4.9 already owned audit/finding/CAPA, and Module 13 owns folders and versioning — so the "Contract Repository" bullet points at the existing `scm:contract_list` (the same call 4.4 made pointing its bin bullet at 4.3's location list) and 4.12 builds only what had no home. `SupplierContract` gains just three things it was missing: `parent_contract` (amendment hierarchy — SET_NULL, because an amendment is a separately-signed instrument and deleting the master must orphan it, not destroy it), `owner`, and a `logistics` type; `clean()` refuses a self-parent, a cross-tenant parent and a **cycle**, since the detail page walks that chain upward and a cycle there is a hung worker rather than a caught error. A `ComplianceRequirement` (`CR-`) is the standing-obligation register (Intelex's shape: source, framework, jurisdiction, applicability, owner, recurrence, next due, workflow status) where a **CLM contract obligation is `source="contract"` with an FK to 4.2's contract, not a second obligation table** — exactly the call 4.9 made when an audit finding became a `NonConformance`. Its scope is five **typed nullable FKs**, never one untyped int, because a bare id carries neither a tenant nor a type and happily points at a deleted or cross-tenant row; `compliance_rate` returns **`None`, not 0**, when nothing has been checked, so an unproven requirement never renders a confident red zero. Its child `ComplianceCheck` is tenant-less and reached only via `requirement__tenant`, has no list or detail page of its own (it is a timeline on the parent), and stamps `performed_by` from `request.user` — who proved a control is an audit fact, not an input. A `TradeLicense` (`LIC-`) brings the feature the GTM category is actually bought for, **real-time decrementing**: issuing a trade document under a licence charges its value/quantity ceiling and voiding refunds it, with `status` `editable=False` so a licence cannot be typed straight to active without the approval that authorises it. A `TradeDocument` (`TD-`) FKs 4.6's `Shipment` rather than re-declaring a consignment, and its lines **snapshot `hs_code`/`country_of_origin` at issue** — a filed customs declaration must record what was declared, not follow a mutable master, which is also precisely why the researched `Item` trade-classification columns were **deliberately not built** (they would create a second source of truth, and the first helpful default copying master onto line would silently rewrite a filed declaration). `TradeDocument.license` is `PROTECT` — the record of what moved under a licence is the audit trail the category exists for — so the licence delete view catches `ProtectedError` and names the blocker instead of 500ing. A `SustainabilityAssessment` (`ESG-`) is the EcoVadis four-theme scorecard on `core.Party` with a **derived** overall score and medal (`editable=False`, so the headline can never disagree with its components) plus Assent-style declaration flags and supplier-declared Scope 1/2/3. Carbon Footprint is a **computed page, no table**: GLEC v3.2 / ISO 14083 tonne-km over 4.6's `Load.distance_km` × `Shipment.weight_kg` (stored expressly for this), priced from a small published factor table the page **renders on screen with its own arithmetic**. A shipment missing a load, a distance or a weight is **counted as excluded and reported**, never folded in as zero — a green zero meaning "we had no data" is the 4.11 `projected_stockout_count` defect and it is worse here, because the number looks like an environmental result. The page states plainly that it is an operational estimate, unaudited, ignoring empty running, and that statutory CSRD disclosure is Accounting's (L29); it never says "AI". **4.11 supply chain analytics** — a closed KPI registry (`KPI-`) with targets, captured snapshots and a derived alert inbox (`ALR-`) over five computed report pages; read-only across 4.1–4.10, writing no `StockMove` and no `JournalEntry`. **4.10 returns management (reverse logistics)** — SCM ships the RMA tables first, so the unbuilt 5.10 and 9.5 extend them by FK rather than build a second RMA (L36, declared in the model docstrings). A `ReturnReason` is **policy, not a label**: its `fault_party` decides who pays return freight and its `blocks_restock` decides whether the unit may re-enter sellable stock — enforced in the form *and* re-checked inside the posting transaction. A `ReturnPolicy` publishes the window, the refund basis and the restocking fee, and carries the two things nothing else can hold: the **grade→cost write-down percentages** that make `condition_grade` financially real, and a printable return-to address (`Location` has no address field). A `ReturnAuthorization` (`RMA-`) is deliberately a **non-posting** document — it authorises and owns neither stock nor money; a portal submission is this record at `requested`, since a status is not a document. Its eligibility verdict is **snapshotted at approval**, so editing a policy next month cannot rewrite last month's decision, and its lines hold `unit_price` (what the customer paid) separately from `unit_cost` (what it cost us) so nobody restocks at the sale price — plus a `tax_pct` snapshot, without which every refund silently under-credits the VAT. A `ReturnDisposition` is the **only ledger writer in the sub-module**, one row per *(line, decision, quantity)* so three units back can be two restocked and one scrapped. Receiving posts **nothing**: keeping the bench off-ledger is the deliberate blocked-stock stand-in, because `Location` has no blocked type and `on_hand()` sums every location, so an intake row would inflate valuation and 4.7's reorder inputs tenant-wide — the honest cost is surfaced by a bench report, not papered over with a fake row. A restock posts a **positive `receipt` at the written-down cost**, never a transfer pair: `_post_transfer` passes `average_cost` precisely so a transfer is value-neutral and `_item_valuation` excludes transfers from the FIFO walk, so a transfer could never carry the write-down. Refund Processing drafts an `accounting.Invoice(kind="credit_note", status="draft")` and **stops** — SCM posts no journal entry (L29) — refusing outright when fees would meet or exceed the credit, because `invoice_post` requires a positive total and would otherwise leave a permanently unpostable document. A `WarrantyClaim` (`WTY-`) is **not** an extension of 4.9's `NonConformance`: an NCR is an internal register with one counterparty-less cost figure and a state machine *we* advance, while a claim is a two-party negotiation with claimed/approved/credited amounts and a deadline *they* control — with typed cost children, because the normal real outcome is a partial approval that accepts the part and refuses the labour. The Return Portal ships as **three honest surfaces**: a staff console for the sidebar (L32), a logged-in customer request page reusing CRM's existing `CustomerPortalAccess`, and a token-gated public status page and return slip — SCM's first unauthenticated views, resolving their tenant off the object because `request.tenant` is None for an anonymous visitor. Anonymous *order lookup* is deliberately not built: nothing lets a stranger prove they own a sales order and `core.Address` has no postal-code field. **4.9 quality management (QMS)** — SCM ships the QMS transaction tables first, so Module 12 will EXTEND them by FK rather than re-declare them (L36). An `InspectionPlan` is a reusable spec keyed to a trigger (incoming receipt / in-process / outgoing shipment / periodic stock / audit checklist) with 100%, percentage, fixed-count or AQL sampling; its characteristics carry target plus upper/lower limits, UOM, test method, a critical flag and `include_on_coa` — the one boolean that makes a certificate generatable. A `QualityInspection` (`QC-`) hangs off whichever of 4.1's `GoodsReceiptNote`, 4.8's `WorkOrder` or 4.6's `Shipment` triggered it, and **snapshots** the plan's characteristics onto its result rows, so editing a plan next month cannot rewrite a certificate already issued. Its usage decision is deliberately separate from its pass/fail status — an out-of-spec lot can still be accepted with deviation, which is the decision auditors care about. A `NonConformance` (`NCR-`) is the single register for findings from every source with the full MRB disposition set; only a **scrap** disposition moves stock, and it posts one ordinary `adjustment` move referencing the NCR number — **no new move type**, because 4.8's justification for `consumption`/`production` (4.7 reads `issue` as customer demand) does not transfer here. Quarantine flips the existing `LotSerial.status` and posts **nothing**: a hold is not a movement. GRN-rejected units never entered stock, so their NCR posts nothing either — expressed as an executable `posts_stock` property rather than a docstring. A `CapaAction` (`CAPA-`) treats corrective and preventive as one attribute per ISO 9001 §10.2, and a `not_effective` verification returns it to *investigating* rather than closing it. A `QualityAudit` (`QA-`) reuses an inspection plan as its checklist and raises its findings **as `NonConformance` rows** — no second findings table — refusing to close while any remains open. The CoA register issues per-lot certificates only when a usage decision accepted the lot, surfacing the first blocking reason on every row it refuses. **4.8 manufacturing / production** — the make side, built so that nothing it computes is also stored. A `BillOfMaterials` (`BOM-`) is a versioned, effectivity-dated recipe whose `explode()` recurses into any component that has its own active BOM, guarded by a visited-set plus depth cap and emitting a would-be-cyclic component as a leaf rather than dropping a real requirement. Make-vs-buy is **derived, never flagged**: an item is manufactured iff an active effective BOM exists for it, which `manufactured_item_ids()` answers for a whole tenant in one query — so there is no `Item.is_manufactured` column to drift or migrate when sourcing changes. A `WorkCenter` (`WC-`) carries capacity, efficiency and split machine/labour rates, with load, utilization and an OEE chip all aggregated from work orders and time logs at read time. A `WorkOrder` (`WO-`) **snapshots** its exploded components onto its own lines, so editing the recipe next month cannot rewrite what a run consumed last month; its two postings go through 4.3's existing `_post_stock_move` service under `select_for_update()` with the status re-read inside the transaction, and they use **new `consumption`/`production` move types rather than reusing `issue`/`receipt`** — 4.7's `demand_series` reads `issue` as *customer* demand, so booking a raw-material draw as one would have silently inflated every forecast built on the stock-issues source. Cost is read back off the ledger, not off the snapshot: material from the consumption moves, labour and machine from the time logs (downtime excluded as a loss metric, not an absorbed cost), and the produced unit cost divides by the **good** quantity so scrap is absorbed by the units that survived. `wip_value` is computed on the page — there is deliberately no WIP location (a new `location_type` would migrate a model 4.3/4.4/4.5 share, and `is_pickable=True` would leak WIP into 4.5's available-to-promise), no WIP column and **no journal entry** (L29). A `ProductionTimeLog` (`PRD-`) records setup/labour/machine/downtime in one table, and its `quantity_completed` is explicitly *advisory* — it does not roll into `quantity_produced`, which keeps the single-writer rule that the 4.7 double-writer bug taught. MRP nets demand against ledger on-hand and emits **suggestions** a planner converts, never a silent auto-PO, and openly excludes open POs because 4.1's `PurchaseOrderLine` has no `item` FK. **4.7 demand planning & forecasting** — the demand side of the plan, built on the rule that history is *derived, never stored*: `demand_series()` aggregates 4.5's `SalesOrderLine` (excluding draft/cancelled) or 4.3's `StockMove` issue ledger on demand, so no fourth copy of sales history exists to drift. A `DemandForecast` (`DF-`) fits one item (× optional location × optional customer) over a bucketed horizon using a pure-`Decimal` method library — naive, seasonal naive, moving/weighted-moving average, exponential smoothing, Holt linear, Holt-Winters, like-item copy, and a `best_fit` that competes them on an out-of-sample hold-out (no numpy/pandas dependency, so every planner-visible number is reproducible). Its `DemandForecastPeriod` grid keeps the decomposition in **separate columns** — historical → baseline → × seasonal index → + event uplift → + signal adjustment → + consensus → final — which is what makes the plan explainable rather than a single number that moved; locked periods survive a regenerate, and MAPE/WMAPE/bias/tracking-signal/**forecast-value-added** are computed over elapsed periods only. A `SeasonalityProfile` (`SEA-`) carries both halves of the seasonality bullet in one table (a recurring index curve, a dated promotion/event window with uplift + cannibalization, or a period-from-launch lifecycle ramp) and can derive its factors from the same history. A `DemandSignal` (`DS-`) is the short-horizon sensing log with a review → apply → dismiss triage; most types await an external feed, but `detect_order_surge()` **works today with zero integration**, extrapolating live sales-order run rate against the approved forecast. A `ForecastAdjustment` (`FA-`) is structured consensus input by business function with a mandatory reason code + rationale, where absolute/delta/percent all reduce to one signed delta and only *accepted* proposals roll into `consensus_quantity`. Safety Stock Calculation extends 4.3's `ReorderRule` **in place** (no duplicate policy table) with service-level Z × √ (L·σ_d² + d̄²·σ_L²), periodic-review, average-max and forecast-error methods plus ABC/XYZ ranking — and `calculate()` writes only `computed_*`: promoting a recommendation into the live `safety_stock`/`reorder_point` that 4.1 purchasing reorders against is a separate, tenant-admin-gated **apply**, never a silent overwrite. **4.6 transportation management (TMS)** — the carrier/freight layer 4.4/4.5 deferred to it (where `YardVisit.carrier_name`/`PickTask` free-text placeholders finally get a real master): a `Carrier` (`CAR-`) modeled as a spine-backed profile on `core.Party` (a required party FK, like 4.2's `SupplierProfile` — never a duplicate company table) with SCAC/MC/DOT identifiers, per-lane `CarrierRateCard`s, and an on-time-delivery scorecard *derived* from delivered-shipment history; a `Load` (`LD-`) consolidating shipments over a sequence of `LoadStop`s with a *derived* cube-utilization headline (assigned weight/volume ÷ equipment capacity, never stored); a `Shipment` (`SHP-`) linking the sales/purchase order it moves, whose status/ETA/POD are *projected* from an **append-only `TrackingEvent` log** (mirrors the StockMove ledger — a pickup event moves it in-transit, a delivered event closes it, a terminal shipment is never walked back); and a `FreightInvoice` (`FRT-`) that audits billed-vs-contract amounts per charge line into a match verdict (matched/price-variance/duplicate/disputed, mirroring the GRN three-way match) and, once approved, **drafts an `accounting.Bill` for the carrier's party and hands off** — TMS records the audit and never posts a journal entry itself (L29). **4.5 order management** — SCM ships the sales order first so it owns it (Modules 8/9 will extend it by FK): `SalesOrder` (`SO-`) captures manually or by converting an accepted CRM quote, validates on submit against the customer's real `accounting.CustomerProfile` credit limit plus a new-customer high-value rule, and `SalesOrderAllocation` reserves stock per fulfillment location. That allocation is deliberately a **soft** reservation that posts no `StockMove` — on-hand doesn't drop when stock is spoken for; availability-to-promise does, and stock physically leaves only via 4.4's pick. Ordering more than a location holds reserves what's there and backorders the rest. **4.4 warehouse management** — WMS layered on the 4.3 spine rather than beside it: bins ARE `Location`s (extended with capacity/pick-sequence/ABC class), `PutawayTask` (`PUT-`) directs received stock from receiving into its bin, `PickTask` (`PIK-`) does wave/batch/zone picking with honest short-pick handling and packing label data (carrier rendering waits for 4.6 TMS), `CycleCountTask` (`CC-`) snapshots expected quantities server-side and reconciles into exactly one existing `StockAdjustment`, and `YardVisit` (`YRD-`) tracks trucks through dock doors with derived dwell time. This pass also closed a real gap in shipped code: **booking a goods receipt now posts stock** (and cancelling reverses it with compensating moves), which previously left procure-to-pay disconnected from inventory. **4.3 inventory management** — SCM ships the **inventory spine** (`ItemCategory`/`UOM`/`Item`/`Location`/`LotSerial`/`StockMove`) that Module 5 will extend by FK: stock is an **append-only `StockMove` ledger** with signed quantities, so on-hand and valuation are always *derived* aggregates and never a stored field that can drift. On top of it, `StockTransfer` (`TRF-`) posts a paired out/in movement with a live insufficient-stock guard, `StockAdjustment` (`ADJ-`) posts reason-coded corrections (write-off/damage/cycle-count/found/revaluation), and `ReorderRule` drives low-stock alerts with a one-click hand-off into a 4.1 requisition. Reports compute FIFO/LIFO/weighted-average valuation over the ledger's cost layers, plus a stock ledger and on-hand-by-location. **4.2 supplier relationship management** — SRM on the `core.Party` supplier spine: a `SupplierProfile` (onboarding lifecycle + qualification questionnaire + a five-point due-diligence checklist gating approval); a `SupplierScorecard` (`SCR-`) whose delivery/quality/price/responsiveness scores are DERIVED from real 4.1 signals (on-time `GoodsReceiptNote`s, reject rate, `RFQQuote` price competitiveness and turnaround) with a weighted overall grade; a `SupplierContract` (`SC-`) with date-driven renewal alerts (expiring/expired) and renew/terminate; a `SupplierCatalog` (`CAT-`) of free-text priced items (pending `core.Item`); and a `SupplierRiskAssessment` (`SRA-`) scoring four risk factors into a derived level (a single critical factor floors it at High). Idempotent `seed_scm` extension; tests in the shared `apps/scm` suite. **4.1 procurement management** — the full procure-to-pay chain: a `PurchaseRequisition` (`PR-`) with multi-tier approval routing by amount and a view-time budget check against `accounting.Budget`; a multi-vendor `RFQ` (`RFQ-`) with a supplier invite list, competing `RFQQuote`s (`QT-`), and a side-by-side comparison matrix marking the cheapest supplier per line; the canonical `PurchaseOrder` (`PO-`) with a nine-state lifecycle, a version+reason amendment trail, staff-recorded vendor acknowledgement, and cancellation controls; and a `GoodsReceiptNote` (`GRN-`) that three-way-matches order↔receipt↔`accounting.Bill` on net-of-tax value with a 2% tolerance and over-receipt precedence. Reuses the `core.Party`/`PartyRole` supplier spine and `accounting.*` money masters; line items stay free-text pending `core.Item` (Module 5). Owns the procurement transaction tables that Module 6 will later extend by FK. Idempotent `seed_scm`; a 1,343-test `apps/scm` suite). Next: 4.19 |
| 5 | Inventory Management System (IMS) | `inventory` | 🟦 5.1–5.20 built — 20 of 20 sub-modules, MODULE COMPLETE. **5.1 product & catalog management** is the catalog layer AROUND the SCM 4.3 item spine, not a second master: SKU Management and Product Categorization stay `scm.Item` / hierarchical `scm.ItemCategory` (the sidebar bullets point at the owning module's live pages, L36), and the app adds three tenant-scoped children on that spine — `ItemAttribute` (name/value/unit spec-sheet rows with a per-SKU unique name and display order), `ItemPrice` (sell-side rows: retail/wholesale/promotional/clearance × price-break `min_quantity` × dated window, with margin/markup computed against the item's current `standard_cost` at render time — no stored cost column, so repricing cost never rewrites price history) and `ProductFile` (photo/safety-sheet/manual/datasheet/certificate as file-upload OR external link, extension allowlist, one auto-demoted cover image per product). An `/inventory/` overview computes catalog completeness (priced %, photographed %) as progress bars; `seed_inventory` reuses the SCM items and seeds links (RFC 2606 placeholders), never uploads. **5.2 vendor / supplier management** extends the same extend-dont-redeclare rule to the buy side: Supplier Directory, Performance Tracking and Contract & Terms stay the 4.2 SRM pages (`scm.SupplierProfile` / signal-derived `SupplierScorecard` / `SupplierContract`, whose per-line lead times and MOQs live on `SupplierCatalogItem`) - the one genuine gap was the conversation itself, so the sub-module's only new table is `VendorCommunication` (`VC-#####`: channel email/call/meeting/site visit/note, direction, subject+body, occurred-at, optional `follow_up_on` driving due/overdue list filters, PROTECT FK to the vendor `core.Party` so deleting a party cannot destroy interaction history, cross-tenant party guard in `clean()`); logged-by is deliberately not a column because every write already lands in `core.AuditLog`. The detail page cross-links the three SRM pages; `seed_inventory` seeds six scripted interactions per tenant over existing supplier-role parties.**5.3 purchase order (PO) management** adds the management layer AROUND 4.1's `scm.PurchaseOrder` spine (L36 - the PO document itself is never re-declared; manual drafting and status tracking point at the SCM pages): a multi-tier **approval workflow** - `PurchaseOrderApprovalRule` value bands (half-open, most-specific-wins: an org-unit-scoped rule beats an all-departments one, then the narrowest band) decide how many sequential sign-offs a pending order needs, the approvals queue resolves each order's rule live and replays its decision chain (`PurchaseOrderApproval` [PA-], rejection resets progress while keeping both runs' history), and clearing the final tier performs the spine's own approve transition under a `select_for_update` lock with every decision audited; an email/EDI **dispatch log** - `PurchaseOrderDispatch` [PD-] records what left, when, to which recipient, under which message/interchange reference, and the FIRST dispatch of an approved order flips it to Sent in the same transaction (append-only: no edit route by design); and **reorder-point auto-drafting** turns below-point `scm.ReorderRule`s into DRAFT spine orders grouped per buyer-chosen vendor (quantities recomputed from the ledger at POST time, nothing auto-sent). Seeder block is idempotent per tenant over existing SCM items/parties/orders.  **5.4 receiving & putaway** completes the inbound story by pointing three of its four NavERP bullets at pages SCM already owns (L29/L36): Goods Receipt Note is 4.1's `scm:goodsreceipt_list`, Three-Way Matching lives on the same GRN (`match_status` machine vs `accounting.Bill`), and Quality Inspection (Receiving) is 4.9's receipt-triggered QMS. The one genuine gap was **Putaway Logic** — scm.PutawayTask carries a "directed" strategy label but no engine — so inventory adds ONE configuration table plus ONE computed page: `PutawayRule` (nullable item/category/source_location FKs onto the spine, required destination, priority + is_active, overlapping rules legal because the resolver order decides) and `/inventory/putaway-suggestions/`, a zero-write queue over OPEN `scm.PutawayTask`s whose deterministic resolver ranks bins most-specific-wins (item rule > category rule > catch-all, then consolidation on bins already holding the SKU, then storage-condition match against own-or-inherited zone condition, then walk-order fallback), every answer carrying a reason string citing codes/SKUs only and every refusal starting "No Suggestion Found" rather than guessing a bin. Disqualifiers guard all tiers: inactive locations, declared-capacity-full bins (blank capacity = unlimited), 4.17 client-dedicated aisles, the staging location itself. Batch-preloaded context keeps the page flat ~7 app queries regardless of backlog; overrides happen on the task itself in SCM (`scm:putawaytask_edit`). Migration 0008; `_seed_putaway_rules` seeds four tier-demo rules + one open task per tenant over seed_scm's location tree. **5.5 warehousing & bin management** layers bin operations ON the SCM location spine (L36): Warehouse Structure stays `scm.Location`'s self-referential tree, and the app adds `BinCapacity` (one envelope per location — max weight/volume/quantity limits where the generic `Location.capacity` number cannot say "full by weight before full by count"; quantity utilisation is DERIVED from the append-only StockMove ledger and answers None when no limit was declared rather than a flattering 0%) plus `CrossDockOrder` (`XD-#####`: dock-to-dock bypass whose draft→received→shipped lifecycle posts REAL receipt/issue legs into the same ledger through FOR UPDATE-locked action methods — cancel-from-received posts a guarded compensating move instead of deleting, JournalEntry-reversal style; received/shipped documents refuse deletion so provenance survives); the **Warehouse Mapping** bullet ships as a computed page over the location tree — two queries total (all locations + one group-by for per-bin on-hand AND value), cycle-guarded walk, orphan roots surfaced rather than hidden — declaring no table of its own. `seed_inventory` extends seed_scm's tree with a zone/two bins/second dock, four capacity profiles (one deliberately over-limit via the real flow) and walks four cross-dock orders through the REAL receive/ship/cancel actions. **5.6 inventory tracking & control** adds the control layer around the same ledger: the **Real-Time Stock Levels** bullet is a computed page (no table) whose four grouped queries merge into per item×location rows — on-hand from `scm.StockMove`, allocated from active `scm.SalesOrderAllocation`s plus reservations, non-sellable from classifications, on-order from open `scm.PurchaseOrderLine`s matched EXACTLY by `sku_hint` (the L28 free-text stand-in) — with availability deliberately NOT clamped so over-promising shows red; **Stock Status Management** is `StockStatus`, a soft claim (L37: posts no move) classifying a slice of stock at one spot as active/damaged/expired/on-hold, ceiling-checked against the ledger in the FORM per the SalesOrderAllocation split; **Inventory Valuation** points at SCM's existing FIFO/LIFO/WAC walk (`scm:valuation_report`); **Inventory Reservations** are `InventoryReservation` [RSV-], general soft locks against any SO/job/project reference with a reserved→released→consumed/cancelled lifecycle walked through FOR UPDATE-locked verbs — consumed stops counting because the issuing document already moved the goods. **5.7 stock movement & transfers** adds the governance layer around 4.3's `scm.StockTransfer` spine (L36: drafting and execution stay on the SCM pages, whose complete action still posts the paired `transfer` StockMove legs; the spine grew two governed states — `pending_approval`/`approved` — plus a nullable `route` FK for exactly this): the **Inter-/Intra-Warehouse Transfers** bullets are one board (`inventory:transfer_board`) that classifies every movement LIVE by walking each location to its warehouse root — no scope column to drift — with scope/status/search filters and per-row submit (optionally choosing a route); the **Transfer Approval Workflow** is tiered policy + decision chain: `TransferApprovalRule` routes by scope and half-open unit band (most-specific-wins, one default tier when nothing matches — never zero), `TransferApproval` [TA-] records every sequential sign-off with rejection-replay semantics (progress resets, history survives), decisions are written under a `select_for_update` lock on the spine row, clearing the final tier performs the spine's own transition to `approved`, and execution remains tenant-admin gated on SCM; **Transfer Routing** is `TransferRoute`, the routing catalog (direct/shuttle/milk-run/freight, optional lane endpoints, expected transit days) whose deletion SET_NULLs movements rather than rewriting history; a per-movement governance panel shows lines with source coverage, the decision chain and the ledger legs posted so far. `seed_inventory` seeds three routes, two rules and four governed movements per tenant walked through the REAL transitions — including one completed via scm's own posting service so its legs are genuine StockMoves. **5.8 lot & serial tracking** adds the management layer around 4.3's scm.LotSerial master (L36: the rows themselves are never re-declared — the Serial Number Tracking bullet points straight at the SCM lot/serial list): **Lot/Batch Generation** is LotNumberRule, a pattern rule (prefix + optional YYMMDD + zero-padded sequence, per-item or tenant default, most-specific-wins resolution mirroring 5.4's putaway resolver) whose one-click mint creates the next spine LotSerial under a collision-retried sequence, refusing untracked SKUs and kind mismatches, and stamping an already past-dated expiry straight to status expired so the master can never contradict the board; **Shelf-Life & Expiry Management** is a per-SKU ShelfLifePolicy (amber warning window + red do-not-ship minimum-remaining gate, with clean() refusing an amber window narrower than its own red line) applied by the FEFO board — a COMPUTED page over the append-only ledger (one grouped on-hand query per lot, zero tables) whose pick order honours the policy: enforced regimes sort true FEFO (earliest expiry first, no-expiry last), advisory regimes keep plain item/number order so the badge tells the truth; and **Traceability & Genealogy** is a computed recall trace reading the ledger backward (inbound legs) and forward (outbound legs = recall scope), with parent/child lot links reconstructed by matching consumption↔production moves through the shared transformation reference. seed_inventory seeds the rules/policies per tenant and mints four expiry-dated demo lots through the REAL generate path with genuine opening receipts. **5.9 order management &amp; fulfillment** adds the one thing nothing else records — Wave Planning — as a management layer over pages SCM already owns (L36): Sales Order Processing points at 4.5's `scm:salesorder_list`, Pick/Pack/Ship at 4.4's `scm:picktask_list`, Shipping Integration at 4.6's `scm:carrier_list`. `FulfillmentWave` [WAV-#####] groups existing sales orders via PROTECT membership rows (unique per wave+order, triple-locked against cross-tenant pairs and frozen once the wave leaves planned); the planned&#8594;released&#8594;closed|cancelled ladder is verb-driven under `select_for_update` with in-transaction audit rows, and progress is honest by construction: fulfilled counts only the pinned fulfilled-or-later status rung (cancelled is never progress) and pick percentage rides the documented text convention `PickTask.wave_ref == wave.number`, answering None rather than a flattering zero when SCM has not typed a reference yet. The Wave Planning bullet ships as a computed board (`inventory:wave_board`) — paginate then three grouped queries flat, stats trio including an unassigned-orders NOT-IN count — while list/detail/form CRUD stays admin-gated like every config surface in this app. Migration 0014; `_seed_fulfillment_waves` builds one planned + one really-released wave per tenant from seed data's own open orders. **5.10 returns management (RMA)** adds the warehouse floor operations layer around SCM 4.10's core RMA spine (L36: primary ReturnAuthorization documents and financial refund queue belong to SCM 4.10, so Return Merchandise Authorization and Credit/Refund Processing bullets point to SCM pages): **Return Inspection** is `ReturnInspection` (`RMI-#####`) and `ReturnInspectionChecklist` capturing packaging condition, parts completeness, functional testing, cosmetic condition, serial verification, and restocking fee recommendations; **Disposition Routing** is `DispositionRoutingRule` with deterministic resolution (`resolve_disposition_routing`: Item > Category > Catch-all) directing returned goods to restock, refurbish, scrap, or quarantine locations; and **Warehouse Returns Workbench** (`/inventory/returns-workbench/`) provides real-time triage over open RMAs and receiving bench goods with guided disposition recommendations. `seed_inventory` seeds rules, inspections and checkpoints across existing demo RMAs. **5.11 stocktaking & cycle counting** adds the scheduling/freeze layer around 4.4's blind count spine (L36 — the Blind Counts bullet points at `scm:cyclecounttask_list`): a CountProgram (`CTP-`) is the recurring CALENDAR — daily/weekly/monthly cadence over a zone or ABC class whose Run action mints today's marked CycleCountTask into SCM (same-day reuse, last_run stamp); PhysicalInventory (`PHY-`) is the warehouse-wide FREEZE event — start() spawns one full-count sheet per bin/zone under the warehouse and lifts only via reconcile(), which REFUSES while any spawned sheet is still open so a freeze can never quietly skip a bin (cancel() unfreezes honestly); and Variance Analysis is a COMPUTED page over counted sheets — lines that disagreed, net variance, and the posted adjustment per sheet. Nothing here re-declares counting or posts stock: corrections stay the spine's own reason-coded adjustments. Seeder walks one event through real start/cancel and leaves one live frozen with sheets awaiting counters. Tests: test_stocktake_{models,forms,views,security}.py (96). **5.12 multi-location management** adds the org tier ABOVE the location spine: `LocationNetwork` [LNW-#####] is a company&#8594;region&#8594;dc&#8594;store self-FK tree whose nodes attach existing `scm.Location` warehouses (PROTECT, one site per node, at any tier — a stocking DC is its warehouse), with cycle- and depth-guarded clean() mirroring Location.path(). The Global Stock Visibility bullet ships as a computed page rolling the append-only ledger UP that tree in exactly four flat queries (nodes, warehouses, one grouped StockMove quantity+value sum, one grouped in-transit transfer sum synthesized from open transfer documents and never subtracted from on-hand); unattached sites surface under an honest "Unassigned sites" group, move-less sites render real zeros, and per-location rules point at where they already live (`scm:reorderrule_list` for safety stock, 5.7 TransferRoute for lanes). Migration rides the shared 0018 node; `_seed_location_network` builds HOLD-CO&#8594;REG-NORTH&#8594;DC-MAIN/DIV-RETAIL&#8594;ST-DT over seed data's real warehouses. **5.14 barcode & RFID integration** adds the DEVICE layer around the spine's own identifiers (L36 - scanners emit scm.Item.sku / scm.Location.code / scm.LotSerial.number, so one shared `resolve_code` resolver maps raw scans against those masters tenant-scoped instead of minting parallel identities): `BarcodeLabel` [LBL-] is the label register whose blank payload derives from its target (sku/bin code/lot number/free ref) and renders REAL Code39/Code128/EAN-13/QR as inline SVG via pillow-free python-barcode + qrcode (void labels render 404; print runs stamp printed_at/by through the verb); `ScanSession` [SSN-] + append-only `ScanEvent` record handheld/wedge captures single or pasted-batch (300 cap) on the Scan Console - unknowns are recorded ok=False, never dropped; `RfidTag` [TAG-] is the EPC registry (hex-normalised unique per tenant, passive/active) with assign/retire/lost verbs and a bulk-read endpoint stamping last-seen snapshots (500 cap). Zero stock writes (L37). pallet_ref free-text is the documented L28 stand-in pending a pallet/HU master. Migration 0018 (+0019 index); LIVE_LINKS 5.14 wired. **5.15 quality control (QC) & inspection** adds the warehouse-FLOOR gate around SCM 4.9's engineering spine (L36 - plans/inspections/NCRs stay `scm:*`; the floor gets its own operational layer): **QC Checklists** are `QcChecklist` + `QcChecklistItem` — mandatory pre-acceptance tick-lists pinned to a product, a vendor party, or workspace-wide, checkpoints edited inline on the checklist form (the 5.10 formset pattern) with kind (visual/functional/documentation/quantity/instruction), mandatory flag and sequence; **Inspection Routing** is `QcRoutingRule` + `resolve_qc_routing` — a deterministic most-specific-wins gate (item tier > category tier > catch-all; vendor-pinned rules add specificity and never fire blind on unknown suppliers) deciding whether an inbound receipt detours through the rule's QC zone or bypasses straight to storage, with a live resolution preview on each rule's detail page; **Quarantine Management** is `QuarantineOrder` [QRD-] whose draft→quarantined→released|scrapped|cancelled lifecycle posts REAL ledger legs (a transfer pair at average cost into the restricted zone; scrap posts the negative-adjustment shape SCM's own NCR ruling prescribes; cancel-from-held reverses) under FOR UPDATE row+item locks with shortfall guards both ends; **Defect & Scrap Reporting** is `DefectReport` [DEF-], the floor capture of defective units found during receiving→counting with photo evidence (image-allowlisted upload or link), an optional escalation pointer to `scm.NonConformance`, and writeoff()/close() verbs where only a written-off report touches stock (`posts_stock` executable rule — dock-refused units close as paper). Migration 0023; `_seed_quality_control` seeds three checklists, three routing rules over seed_scm's tree (+QC-HOLD zone), walks two quarantine orders through the REAL actions and writes one defect off for real; LIVE_LINKS 5.15 wired. **5.16 alerts & notifications** is ONE engine-raised inbox wearing four bullet lenses (`?type=` deep-links, the 5.7 board-lens pattern): `AlertRule` [ARL-] is the watch catalog — type (low_stock/out_of_stock/overstock/expiry/po_approval_pending/shipment_delayed), severity stamped onto every alert, optional item/location scope, per-type knobs (expiry window days, overstock % of declared bin max), in-app/email/SMS/push channels + comma-separated recipients (email requires at least one), and a cooldown window; `InventoryAlert` [ALT-] snapshots each raised condition (type/severity/message/observed metric frozen at raise time, open&#8594;acknowledged&#8594;resolved triage with who/when stamps) and `run_detection()` is deterministic and explainable — never AI — reading ONLY spine state: `scm.ReorderRule`s against one grouped StockMove aggregate for low/out-of-stock, 5.5 `BinCapacity` utilisation for overstock (bins with no declared limit honestly raise nothing), `scm.LotSerial.expiry_date` windows, `pending_approval` POs and past-due undelivered Shipments as workflow triggers; suppression is one-open-alert-per-dedup-key (engine guard — MariaDB cannot express the partial unique constraint) plus the rule's cooldown; `NotificationDelivery` [NDL-] is the append-only dispatch log (no edit/delete routes) whose rows stay honestly `queued` because no SMTP/SMS/push gateway exists yet — the in-app inbox IS the live surface. Rule CRUD is tenant-admin gated; acknowledge/resolve stay plain staff actions like procurement's alert center. Migration 0020 (rides an incidental rfidtag.epc help_text sync); `_seed_alerts` seeds five rules then runs a REAL detection pass so every demo alert cites live spine data; LIVE_LINKS 5.16 wired. **5.18 accounting &amp; financial integration** is the SYNC ENGINE between the warehouse and Module 2's ledger — the ledger stays accounting's (L29) and the PO/GRN/SO/shipment documents stay 4.x's (L36); what was genuinely missing is that 4.18's AP/AR pages are READ-ONLY registers, so nothing actually DRAFTED the money documents from stock events. **AP Integration** (`inventory:ap_sync`) queues received GRNs whose vendor bill has not been drafted and syncs them into a DRAFT `accounting.Bill` at PO unit prices with per-line tax resolved through TaxRule, linking `grn.bill` and re-running the three-way match in the same atomic block (a re-run re-checks under row lock, so one receipt can never draft two bills); **AR Integration** (`inventory:ar_sync`) queues delivered outbound shipments whose order is uninvoiced and drafts a DRAFT `accounting.Invoice` from the ORDER lines (discounts folded into net unit prices since `InvoiceLine.line_total` is quantity × price; order lines carry a real `scm.Item`, so product × country tax resolution applies fully), then links `so.invoice` without flipping SCM's status; **Journal Entry Automation** (`inventory:je_automation`) turns posted stock events into balanced POSTED `accounting.JournalEntry`s under a GLPostRule account map (one active mapping per event type): each pending posted `scm.StockAdjustment` posts value-up as DR inventory / CR offset (found-stock gain) or value-down reversed (write-off), and the COGS runner expenses ALL customer-issue moves in a date window as ONE entry valued at each move's stamped issue-time unit cost — historical fact, not a re-valuation — with overlapping windows refused so no move is expensed twice; **Tax Management** is `TaxRule` [TRT-], product scope (SKU > category > catch-all, PutawayRule resolver semantics) × optional billing country → `accounting.TaxCode`. Every posting lands in `JournalSyncLog` [JSY-] with its source and JE pointer. Migration 0024; `_seed_finint` seeds two tax rules + two GL rules over accounting's chart of accounts, walks a real received-but-unbilled GRN (via scm's own `_post_grn_receipt`) into the AP queue, delivers seed_scm's outbound shipment via a REAL TrackingEvent into the AR queue, and posts the seeded cycle-count adjustment through the REAL `post_adjustment_to_gl` path; LIVE_LINKS 5.18 wired. **5.19 third-party integrations & API** is the commerce-stock layer AROUND scm 4.19's generic gateway (which owns webhooks/EDI — none re-declared here) and inventory 5.18's internal GL automation: `IntegrationChannel` [INT-] is the connection register for external platforms discriminated by kind (e-commerce / ERP / accounting software — Shopify, Amazon SP-API, WooCommerce, SAP, Oracle, NetSuite, QuickBooks, Xero, Sage…), carrying auth INTENT, environment, a human-maintained health marker, rate-limit prose, an SSRF-warned inert base_url and the accounting.IntegrationConfig credential mechanics verbatim (prefix(6) + SHA-256 hash only, plaintext shown exactly once via rotate-key); `ChannelListingMap` is the SKU↔channel identity table (external product/variant ids per scm.Item × optional location; NULL variant ids coexist under MariaDB's null-coalescing unique so local-only rows are legal); `StockSyncRun` [SYN-] is the APPEND-ONLY run register (batch counts, truncated payload excerpt, error fields) created ONLY through `record()`, whose sync verb honestly records status `simulated` — nothing dials anything yet, no transport stack exists in source (SSRF-guarded for the future pass), stock is never mutated and `last_sync_at` is never faked; `ApiClient` [API-] is bullet 4's INBOUND half — keys WE issue to third-party consumers (scopes/allowed-ips recorded intent, revoke-only lifecycle, refused on revoked clients). The **API Management** bullet lands on the ApiClient register; the three integration bullets land on channel-list lenses (`?kind=`). Migration 0026 (+0027 variant-null + runs index); `_seed_integrations` seeds one channel per family over real spine items, four listing maps (incl. local-only + paused + channel-wide), one simulated run through the REAL creator and an active + a revoked client; LIVE_LINKS 5.19 wired. **5.20 units of measure (UOM)** builds the piece `scm.UOM`'s own docstring deferred — the full **N:N conversion matrix** over the 4.3 unit master (the master itself is never re-declared; its list stays linked from the page headers): `UomConversion` (TenantOwned, no numbering — the PutawayRule config posture) holds directed rules "1 FROM-unit holds FACTOR TO-units" (`factor` 14,4, min 0.0001), scoped two-tier like every most-specific-wins catalog in this app — an item-pinned row is that SKU's own truth and a blank-item row is the tenant-wide default, both legal for one pair because specificity ranks them; `(tenant, item, from_uom, to_uom)` is unique with an explicit `clean()` re-probe for the MariaDB NULL-item gap the composite index cannot see. The shared engine is module-level: `find_conversion_path()` BFS-walks active edges (item rows overriding defaults PER edge, so a chain may mix tiers across hops; MAX_PATH_DEPTH 5 refuses pathological graphs) and `convert_quantity()` multiplies factors quantizing once at the end — identity pairs convert trivially, unreachable pairs return None and callers SAY so instead of guessing a rate. The read-only **Conversion Calculator** (`inventory:uom_calculator`) resolves any quantity through that graph live, naming each hop and which tier won it; rule writes are tenant-admin gated, list/detail member-readable. Zero stock writes — converting units on paper moves no StockMove. Migration 0028; `_seed_uom_conversions` get_or_creates CASE/PLT beside seed_scm's EA/BOX and seeds the NavERP.md ladder verbatim (Case = 12 Units, Pallet = 40 Cases) plus a double-case item override per tenant; LIVE_LINKS 5.20 wired — Module 5 complete. |
| 6 | Procurement Management System | `procurement` | 🟨 6.1–6.2 built — 2 of 19 sub-modules. **6.1 user dashboard & portal** is the people/workflow layer AROUND the SCM 4.1 procurement spine (L36: it declares no requisition/PO table of its own): a `ProcurementAlert` Task & Alert Center (kind/severity + an open→acknowledged→resolved lifecycle with who/when stamps, internal-path-only links) and a `WidgetPreference` per-user overview layout (absence of a row = visible). The **Personalized Overview** (`/procurement/`) is a computed page over `scm.PurchaseRequisition` / `scm.PurchaseOrder` aggregates (pending approvals, committed spend this vs last month, open PO value, approaching deadlines) whose sections honour the stored widget choices; **Quick Requisition Entry** drafts a single-line requisition INTO `scm.PurchaseRequisition` in one transaction (requester = signed-in user, derived total, hand-off to scm's submit/approve); the **Recent Activity Feed** is `core.AuditLog` filtered to procurement content types (always windowed, my-actions by default, per-entry field-level diff view, no create/edit/delete — it is a record, not an opinion); **Self-Service Reporting** computes personal usage/spend plus a six-month committed-spend trend and exports the user's OWN requisitions as CSV with formula-injection neutralization. **6.2 requisition management** adds the management lens over the same spine: **Requisition Tracking** (`procurement:req_list` register + a detail page whose timeline IS the immutable `core.AuditLog` trail from draft through approval to PO conversion, with linked RFQs/POs); the **Duplicate Requisition Check** is an explainable heuristic (same title or any line item, case/space-insensitive, within 30 days, live statuses only) surfaced as a badge column on the register, an advisory panel with match reasons on each detail page, a warning after template apply, and a `?dupes=1` deep-link filter — never auto-blocking; **Requisition Templates** [RQT-] (+lines) are recurring-order blueprints whose Apply drafts a fresh spine requisition under the signed-in user (individual line creates so derived totals compute; duplicate warning after); **Cancellation/Amendment** [RAM-] is the gated workflow scm lacks for pending/approved requisitions: requester files cancel-or-amend (header fields + proposed add/update/remove line rows, one open amendment per requisition), tenant admin approves (atomic apply → PR cancelled or changes written + totals recalculated) or rejects with reason. Creation itself stays 4.1's full form (the sidebar bullet links there — extend, never re-declare). Idempotent `seed_procurement` seeds alerts, three templates and a pending amendment against an existing seeded PR. |
| 7 | Project Management | `projects` | Roadmap |
| 8 | Sales Management System | `sales` | Roadmap |
| 9 | eCommerce Management System | `ecommerce` | Roadmap |
| 10 | Business Intelligence (BI) | `bi` | Roadmap |
| 11 | Asset Management System | `assets` | Roadmap |
| 12 | Quality Management System (QMS) | `quality` | Roadmap |
| 13 | Document Management System (DMS) | `documents` | Roadmap |

Each new module is a Django app under `apps/<slug>` that **reuses** the unified core (Party, Item, ledgers,
anchors) and **adds** only its own domain tables â€” see the coverage map in [`NavERP-ERD.md`](NavERP-ERD.md).

---

## Development conventions

- **Multi-tenancy is mandatory**: every model has a `tenant` FK; every view filters by `request.tenant`.
- **CRUD completeness**: every list page ships with create, detail, edit, and POST-only delete.
- **Filters**: pass choices/querysets from the view; guard integer-FK filters; preserve filters across pagination.
- **Templates**: use the `theme.css` component classes; multi-line notes use `{% comment %}â€¦{% endcomment %}`
  (a multi-line `{# #}` would render as visible text).
- **Template folder layout**: one folder per sub-module, then one folder per entity, with a bare
  `list/detail/form.html` page filename â€” `templates/<app>/<submodule>/<entity>/<page>.html` (foundation apps are
  flat, so the entity folder sits at the app root). Standalone pages (reports, letters, wizards, landing/overview)
  stay at the sub-module/app level. See the project `CLAUDE.md` "Template Folder Structure" rule.
- **Seeders** are idempotent and print the demo logins.
- **Migrations** are committed alongside model changes.
- **Commits**: one file per commit with a descriptive message; work lands on `main` and is pushed manually.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Unknown database 'nav_erp'` | Run setup step 3 (create the database). Ensure XAMPP MySQL is started. |
| `(1064) â€¦ RETURNING â€¦` during migrate | The MariaDB 10.4 shim in `config/__init__.py` must be present (it is) and the venv must have PyMySQL installed. |
| `manage.py` can't import Django | Use the venv interpreter: `python â€¦`. |
| Module pages are empty | You're logged in as the superuser `admin` (no tenant). Log in as `admin_acme` / `password`. |
| Login says "session timed out" repeatedly | Idle timeout is 30 min / absolute 12 h â€” just sign in again. |
| Changes don't appear in the browser | The dev server may be running with `--noreload`; restart it and hard-refresh (Ctrl+Shift+R). |
| `SECRET_KEY is not set` on startup | Set `SECRET_KEY` in `.env` (required when `DEBUG=False`). |

---

## License

See [LICENSE](LICENSE).

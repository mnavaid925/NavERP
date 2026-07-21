<div align="center">

# NavERP

**A multi-tenant Enterprise Resource Planning (ERP) platform**

Django 5.1 · Tailwind CSS · HTMX · Chart.js · Lucide · MySQL/MariaDB (XAMPP)

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
19. [Module roadmap (0–13)](#module-roadmap-0-13)
20. [Development conventions](#development-conventions)
21. [Troubleshooting](#troubleshooting)
22. [License](#license)

---

## Overview

NavERP is a SaaS-style ERP where many independent organizations ("tenants") share one Django deployment and
one database, with strict per-tenant data isolation. It is built **module by module** on a single shared data
model so that customers, vendors, employees, items, money, and stock are never duplicated across modules.

This repository currently delivers the **Module 0 foundation** (System Admin & Security —
`core`/`accounts`/`tenants`/`dashboard`) plus three domain modules built on it: **Module 1 — CRM** (1.1–1.12),
**Module 2 — Accounting & Finance** (2.1–2.15), **Module 3 — HRM** (employees, org structure, onboarding,
offboarding, recruiting, attendance, leave, time tracking, holidays, payroll, statutory/tax, and performance
management — goals, reviews, continuous feedback, and performance improvement — 38 of 41 sub-modules), and the start
of **Module 4 — Supply Chain Management** (4.1 Procurement: requisition → RFQ → purchase order → goods receipt with
three-way match; 4.2 Supplier Relationship Management: onboarding, signal-derived scorecards, contracts, catalogs,
risk; 4.3 Inventory Management: the append-only stock-move ledger with derived on-hand, transfers, adjustments,
reorder automation and FIFO/LIFO/WAC valuation; 4.4 Warehouse Management: putaway, wave/batch/zone picking,
cycle counting and yard; 4.5 Order Management: order capture, credit/fraud validation, soft allocation
and backorders; 4.6 Transportation Management: carrier master + rate cards + derived on-time scorecard, loads with
route stops and cube utilization, shipments with an append-only tracking-event log and POD, and freight audit handing
off a draft accounting bill). The remaining functional modules (5–13) and SCM 4.7–4.19 are planned and scaffolded against the same core. The suite stands at **9,000+ passing tests**.

- [`NavERP.md`](NavERP.md) — the master catalog of all modules (0–13) and their sub-modules.
- [`NavERP-ERD.md`](NavERP-ERD.md) — the unified core data model (the `Party` + two-ledger spine every module reuses).

---

## Why NavERP is one ERP, not fourteen apps

Three design ideas hold the whole platform together:

1. **The Party model.** `Party` + `PartyRole` mean there is **one record per real-world person or organization**.
   *Customer, vendor, supplier, employee, lead, contact, partner* are **roles** on a party, not separate tables.
   This collapses the customer/vendor/employee duplication that otherwise spreads across CRM, Accounting, HR,
   Procurement, and Sales.

2. **Two universal ledgers.** Every financial effect posts to `JournalEntry`/`JournalLine` (append-only) — **built
   and owned by the Accounting module (Module 2)** — and every inventory effect will post to `StockMove` (arrives
   with the Inventory module). Account balances and on-hand quantities are **derived** by aggregation, never stored
   as editable fields — that consistency is what makes it an ERP.

3. **Shared cross-module anchors.** A small set of backbone entities (`OrgUnit`, `Employment`, `Activity`,
   `Document`, `AuditLog`, and later `Project`, `Asset`, `WorkOrder`, `Contract`) are read/written by more than
   one module. Each module adds only its **own** domain tables on top of this spine and FKs into it **by string**
   (e.g. `models.ForeignKey('core.Party', …)`).

---

## What's implemented today

### `core` — platform & shared spine
- **Tenant** workspace model; **shared-DB multi-tenancy** via `TenantMiddleware` (sets `request.tenant` from the
  logged-in user) and a per-request **idle session timeout**.
- **Party model**: `Party`, `PartyRole`, `Address`, `ContactMethod`, `PartyRelationship`.
- **Org & people**: `OrgUnit` (company/branch/department/team/cost-center hierarchy), `Employment`.
- **Cross-cutting anchors**: `Activity` (generic task/call/email/meeting/note), `Document` (generic file
  attachment), `AuditLog` (append-only who/what/when/before→after).
- Reusable, tenant-safe **CRUD helpers** (search, filter guards, windowed pagination, audit), a
  `tenant_admin_required` decorator, an audit-log writer, a per-tenant numbering helper, and the
  **`MODULE_CATALOG`** that drives the sidebar (modules 0–13 with live vs. "roadmap" links).

### `accounts` — identity, authentication & RBAC
- **Custom `User`** (login by **email or username**), nullable `tenant` (the superuser has none by design),
  `is_tenant_admin`, lifecycle `status` (active/suspended/archived), and a link to the person's `Party`.
- **RBAC**: `Role` (per-tenant) bundling a global `Permission` catalog.
- **`UserInvite`**: tokenized, 7-day-expiry invitations with accept/revoke.
- **Auth flows**: login, **self-service tenant registration** (creates the workspace + first admin),
  forgot/reset password (console email backend in dev), logout (POST-only).
- **Management UI**: users, roles, invites, and a self-service profile page. Admin actions are gated by
  `@tenant_admin_required`.

### `tenants` — Module 0.1: Tenant & Subscription Management
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

### `crm` — Module 1: Customer Relationship Management (1.1–1.12)
- **Leads** (`LEAD-#####`) with rating (hot/warm/cold), qualification status, scoring, and one-click
  **conversion** to a `core.Party` account + contact + an Opportunity (atomic).
- **1.2 Sales Force Automation** (recreated in detail — all three NavERP bullets live):
  - **Opportunities** (`OPP-#####`) — pipeline stages, amount/probability/weighted forecast, **forecast category**,
    **competitor**, **loss reason**, **territory**, system **stage-change** + **lost** timestamps; a **Kanban
    pipeline board** (per-stage totals + one-click stage advance) and **commission/credit splits** (revenue ≤100%).
  - **Product Catalog & Quoting** — a sales **Product** catalog (`PRD-#####`, margin), regional/tier **Price
    Books** (`PB-#####`), and a **Quote** builder (`QUO-#####`) with line items/discounts/tax, server-computed
    totals, a draft→sent→accepted lifecycle, and a printable (PDF-style) quote page.
  - **Forecasting** — **Sales Quotas** (`QTA-#####`) per rep/territory/period and a **forecast dashboard**
    (weighted pipeline by forecast category + quota-attainment progress).
- **1.3 Marketing Automation** (recreated in detail — all three NavERP bullets live):
  - **Campaigns** (`CAM-#####`) — type, **objective**, status, **parent-campaign** hierarchy, planned/actual budget,
    expected/actual revenue, ROI, **UTM** tags, and a member-funnel/response-rate roll-up on the detail page.
  - **Campaign Members** — target-list segmentation linking a campaign to a `core.Party`/`Lead` with per-recipient
    status tracking (targeted→sent→opened→clicked→responded/converted, or bounced/unsubscribed).
  - **Email Marketing** — **Email Templates** (`EMT-#####`, reusable HTML + merge vars) and **Email Campaigns**
    (`BLAST-#####`) with A/B variants, drip send-type, and open/click/bounce tracking; an **admin-gated Send**
    snapshots recipients and advances members.
  - **Landing Pages & Forms** (`LP-#####`) — an **admin-gated Publish** exposes a public, unguessable-token
    **web-to-lead** page (`/crm/p/<token>/`, no login, CSRF-protected, escaped body) whose **Form Submissions**
    route to an owner and convert one-click into a `Lead`.
- **1.4 Customer Service & Support** (recreated in detail — all three NavERP bullets live):
  - **Cases / Tickets** (`CASE-#####`) — priority + status workflow, an **SLA policy** (`SLA-#####`, per-priority
    first-response + resolution hour targets) that computes due dates with **breach badges**, a **conversation
    thread** (`CaseComment`: internal note vs customer-visible reply), **CSAT** rating, and an unguessable
    public **case-status tracking** page (`/crm/cases/track/<token>/`).
  - **Knowledge Base** (`KB-#####`) — hierarchical **categories** (`KBC-#####`), internal/external visibility,
    view counter, **helpful/not-helpful** voting, and a public article page (`/crm/kb/<token>/`).
  - **Customer Self-Service Portal** — **CustomerPortalAccess** (`CSP-#####`) grants a customer a login to view
    only their own cases, submit tickets, and reply (`/crm/portal/cases/`); admin-gated access grants.
- **1.5 Activity & Communication** (recreated in detail) — **Tasks** (`TASK-#####`, to-dos/calls/follow-ups with
  priority, due date, and **automated recurring tasks** that spawn the next occurrence on completion); **Calendar
  Events** (`EVT-#####`) with attendee **RSVPs**, a public **meeting-invite/RSVP link** + an **`.ics` calendar
  export** (`/crm/invite/<token>/`); and a unified **Communication Log** (`COM-#####`) for call logging
  (duration/outcome) and email/BCC sync across call/email/SMS/note/meeting channels.
- **Accounts & Contacts** are the shared **`core.Party`** identity (one record, many roles) enriched with CRM-owned
  one-to-one **`AccountProfile`** (industry, website, revenue, employees, parent company, address) and
  **`ContactProfile`** (job title, department, phone/mobile, employer account, address) extensions — **full CRUD**
  in CRM, no duplicate customer/contact tables. Deleting an account/contact removes the shared Party and is
  **tenant-admin-only** (cross-module impact).
- A CRM **overview** (analytics) page: stat cards (open leads, pipeline, weighted forecast, win rate, open
  cases/tasks, active campaigns) + pipeline-by-stage and leads-by-rating charts.

**Sub-module 1.6 — Analytics & Reporting** (recreated in detail, migration `0015`, 4 CRM-owned tables; all
metrics are read-only aggregations over existing CRM data, computed in `apps/crm/analytics.py`):
- **Dashboards** — saved, per-user **`AnalyticsDashboard`** (`DASH-#####`) holding **`DashboardWidget`** tiles
  that are **computed live on render**: KPI cards, gauges (with optional target), bar/line/pie/doughnut charts
  (Chart.js), and tables (top performers, campaign ROI) — 20 metrics over Opportunity/Case/Lead/Campaign/Task.
  Per-widget date-range + size, drag-free up/down reordering, and admin-gated `is_shared`/`is_default` flags.
- **Standard Reports** — saved **`AnalyticsReport`** (`RPT-#####`) in 4 canned types (sales activity, sales
  performance/top-performers, funnel drop-off, service resolution-time + CSAT) computed live with a chart +
  table + KPI summary, plus point-in-time **`ReportSnapshot`** runs frozen as JSON for period-over-period trends.

**Sub-modules 1.7–1.12** (extension pass, 27 CRM-owned tables, migrations `0005` + `0016`–`0024` for the 1.7/1.8/1.9/1.10/1.11 recreations):
- **1.7 Finance & Billing** *(recreated in detail — all three NavERP.md bullets now live, reusing the
  **Accounting ledger** per L29; draft hand-off)* — **Deal Invoices** (`DINV-#####`): one-click
  **quote→invoice conversion** that generates a draft `accounting.Invoice` (line items, per-line + quote-level
  discount, and tax carried so `invoice.total == quote.total`) and links it to the deal, with a deal-margin
  card; **Payment Receipts** (`RCPT-#####`): printable receipts over `accounting.Payment` allocations with
  payment-gateway metadata (Stripe/PayPal/Razorpay); **Expenses** (`EXP-#####`, + **`is_billable`** for true
  margin): deal/project cost logging with allowlisted receipt upload + owner **submit** / tenant-admin
  **approve/reject**.
- **1.8 Project & Delivery** *(recreated in detail — all three NavERP.md bullets now live)* — **Projects**
  (`PRJ-#####`, one-click **convert** from a won opportunity, derived **progress %** + overdue flag, a **Kanban
  board** with status-move), **Milestones** (`MS-#####`, sub-tasks); **Time Tracking** **Timesheets**
  (`TS-#####`, billable/non-billable, owner **submit** + tenant-admin **approve/reject** — `status` off the form
  to close a self-approve gap); and **Resource Allocation** — **`ResourceAllocation`** (`RA-#####`) capacity
  bookings feeding a **workload board** that flags overbooked vs. free capacity (planned vs. logged vs. capacity
  per person).
- **1.9 Document & Contract** *(recreated in detail — all three NavERP.md bullets now live)* — **E-Signatures**:
  **Contracts** (`CTR-#####`) with per-signer tracking + a **public token-based signing page**; **Document
  Generation**: **Doc Templates** (`TPL-#####`, merge-variable HTML) rendered into a contract via a one-click
  **Generate** action through an **isolated, escaping-only template engine** (no `include`/`extends`/`load`/`safe`
  — server-side template-injection-safe); **File Repository**: **`DocumentVersion`** (immutable contract revisions
  with body snapshot + allowlisted file uploads) and a **repository organized by account/deal** with version
  counts. Template authoring is tenant-admin-gated.
- **1.10 Automation & Workflow** *(recreated in detail — all three NavERP.md bullets now live)* — **Trigger-Based
  Actions**: **Workflow Rules** (`WFR-#####`, declarative trigger/condition/action JSON) now back a real, bounded
  **rule-execution engine** — an admin **Run** evaluates the conditions against the latest tenant records of the
  trigger entity (≤50) through a field-name **allowlist** (only concrete non-relation columns — no method/property/
  FK/relation access, so a condition can't reach a token field or trigger a lazy query) and fires the actions
  (webhook delivery / approval creation / logged note), recording each fire to the append-only **Workflow Log**;
  **Approval Processes**: **Approval Requests** (`APR-#####`, admin approve/reject); **Webhooks** *(was a stub →
  workflow-rules)*: a real endpoint registry — **Webhooks** (`WH-#####`) with a **write-only HMAC signing secret**
  (PasswordInput, masked, never round-tripped) + validated custom headers, and an immutable **Webhook Delivery** log
  (HMAC-SHA256-signed JSON payloads; admin **Test**). Outbound HTTP is **recorded-and-signed only** (the real POST
  is deferred behind a documented SSRF guard — https-only, pin-resolved-IP, port 443, no redirects). Webhook config
  + rule authoring/run are tenant-admin-gated.
- **1.11 Customer Success** *(recreated in detail — all three NavERP.md bullets deepened)* — **Onboarding
  Pipelines**: **Onboarding Plans** (`CS-#####`, step checklists + progress + step edit) **plus reusable Onboarding
  Templates** (`OTPL-#####`, ordered steps with day-offsets, **applied in one click** to clone a fresh plan for a
  client; admin-authored); **Health Scoring**: **Health Scores** (`HS-#####`, 0–100 from tickets/NPS/tasks/engagement
  with configurable, validated weights) now keep an append-only **Health Score History** trend and **auto-raise a
  guarded churn-risk task** when an account turns Red, with an admin **Recompute all**; **Surveys & Feedback**:
  **Surveys** (`NPS-#####`, NPS/CSAT/CES) with **type-aware** classification + a type-aware public respond page
  (NPS 0–10 / CSAT 1–5 / CES 1–7), an admin **Send** action, and an **NPS analytics** page (NPS = %promoters −
  %detractors, promoter/passive/detractor split, CSAT/CES averages).
- **1.12 Inventory & Vendor** — CRM-owned **Product Stock** (`STK-#####`, low-stock alerts), **Purchase Orders**
  (`PO-#####`) with line items + receive-to-stock, and **Partner Portal Access** (`PRT-#####`) with a
  partner-facing read-only portal (orders + stock).
  > 1.12 uses CRM-owned PurchaseOrder/ProductStock because the Inventory/Procurement spine masters
  > (`core.Item`/`StockMove`/`PurchaseOrder`) and the Accounting ledger aren't built yet; they migrate onto
  > the spine when those modules land.

Full CRUD, tenant isolation, working filters, an idempotent `seed_crm`, and a **2,114-test** suite.

### Module 2 — Accounting & Finance (`accounting`) — 2.1–2.15

The first domain module to **own the GL ledger spine** (no core ledger existed — see lesson L28). Double-entry
throughout: journal entries post only when debits equal credits, posted entries are immutable (corrected via a
reversal), account balances are always *derived* from posted lines, and posting into a closed period is blocked.

- **2.1 Dashboard** — cash-position / AR / AP KPI cards, overdue alert centre, 6-week net-cash Chart.js trend, quick actions.
- **2.2 General Ledger** — hierarchical **Chart of Accounts**, **Journal Entries** (`JE-#####`) with an inline
  debit/credit line formset + post/void(reversal) workflow, **Fiscal Periods** with admin close, **Currencies**
  (global) + per-tenant **Exchange Rates**, plus **Trial Balance** and per-account **Ledger** reports.
- **2.3 Accounts Payable** — **Vendor Profiles** (on `core.Party`), **Bills** (`BILL-#####`) with line items +
  approval routing + document attachment, **AP Aging**, **Payment Terms**.
- **2.4 Accounts Receivable** — **Customer Profiles** (credit limit/hold), **Invoices** (`INV-#####`) + credit notes
  with a line formset and credit-limit warning, **Cash Application** (payment→invoice allocation), **AR Aging**.
- **Payments** — unified inbound/outbound **Payments** (`PAY-#####`) whose confirm/void post (and reverse) balanced
  GL entries; invoice/bill status derives from confirmed allocations.
- **2.5 Cash Management** — **Bank Accounts** (last-4 only) with a live balance, **Bank Transactions** (manual +
  CSV import, deduped on external ref), **Reconciliation** matching.

Full CRUD, tenant isolation, working filters, an idempotent `seed_accounting`, and a **212-test** accounting suite.

**Advanced sub-modules 2.6–2.15** (extension pass, 14 accounting-owned models, migrations `0002`/`0003`) — every
workflow action posts a balanced `JournalEntry`:
- **2.6 Fixed Assets** (`FA-`) with a depreciation-run action (straight-line / declining-balance, capped at the
  depreciable base) and **Disposals** (`DISP-`) booking the gain/loss; **2.7 Cost Allocation** (`CALLOC-`);
  **2.8 Payroll** runs (`PRUN-`, multi-leg wage/tax/benefit JE, derived net pay); **2.9 Project/Job Costing**
  (`PRJ-`/`JCE-`) with budget-vs-actual; **2.10 Intercompany** (`ICT-`) due-to/due-from with an elimination flag.
- **2.11 Tax** codes + returns; **2.12 Reporting** — **Balance Sheet**, **Profit & Loss**, and Scheduled-report
  config; **2.13 Budgeting** (`BUD-`) with a budget-variance report; **2.14 Internal Controls** (SOX); **2.15
  Integrations** (Plaid/Stripe/Avalara/… config with a write-once, reveal-once hashed API key).
All posting/approval actions are `@tenant_admin_required`; the GL stays balanced (Σdebits == Σcredits).

Sidebar completion pass (2.x): **Recurring Invoicing** (`RINV-`, generates draft invoices on a weekly/monthly/
quarterly/annual cadence anchored to the start date) and a discount-aware **Payment Schedule** report were added, and
~13 previously-roadmap feature bullets were wired to the pages that already deliver them (incl. *Employee Master →
HRM*, and the 2.15 connector categories as filtered integration views). The bullets still marked "Soon" are
deliberately deferred — they belong to unbuilt modules (all of 2.7 → Inventory/Procurement) or need external
integrations (OCR capture, Plaid feeds, XBRL filing, customer/vendor portals).

### Module 3 — Human Resource Management (`hrm`) — 3.1/3.2/3.3/3.4/3.5/3.6/3.7/3.8/3.9/3.10/3.11/3.12/3.13/3.14/3.15/3.16/3.17/3.18/3.19/3.20/3.21/3.22/3.23/3.24/3.25/3.26/3.27/3.28/3.29/3.30/3.31/3.32/3.33/3.34/3.35/3.36/3.37/3.38/3.39/3.40/3.41

HRM passes so far — **employee directory + onboarding + offboarding + leave + attendance + time tracking + holidays**, reusing the
core spine: an employee is a `core.Party` (person) + `core.Employment` + a 1:1 `hrm.EmployeeProfile` (`EMP-#####`)
anchor; departments reuse `core.OrgUnit`. Payroll GL posting stays with `accounting.PayrollRun` (not duplicated
here). Request-free domain logic (task generation, clearance-checklist generation, leave-encashment computation)
lives in `apps/hrm/services.py` so the seeder and tests can call it without the view layer.

- **3.1 Employee Management** — `EmployeeProfile` directory with a full personnel file (personal / employment /
  marital status / national-ID + passport / addresses / two emergency contacts / bank — sensitive IDs & bank fields
  **masked** in the UI and redacted from the audit log), plus two child records: an **`EmployeeDocument`** (`EDOC-`)
  vault (ID proofs, certificates, contracts, NDAs with issue/expiry dates, an expiring-soon/expired badge, an HR
  verify/reject workflow, and an enforced **confidential** flag that hides the doc from non-admins) and an
  **`EmployeeLifecycleEvent`** (`ELC-`) job-history timeline (hire / confirmation / transfer / promotion /
  salary-revision / separation as dated from→to events, admin-managed). The employee detail page is the hub —
  leave balances, recent attendance, recent leave, a Documents card and an Employment-Lifecycle card — plus an HRM
  overview (headcount / today's attendance / pending leave / upcoming holidays).
- **3.2 Organizational Structure** — a `JobGrade` catalog (orderable seniority levels) bands the enriched
  `Designation` (job grade + min/mid/max salary + description/requirements + budgeted headcount, linked to
  `core.OrgUnit`); `DepartmentProfile` and `CostCenterProfile` are HRM 1:1 **companions** on `core.OrgUnit`
  (kind department/cost-center) adding the head/owner/budget/code that core can't hold; plus a derived **org chart**
  (reporting-line tree / by-department grouping from `core.Employment.manager`, no model) and a read-only
  **Company Setup** view over the company OrgUnit + `tenants.BrandingSetting`.
- **3.3 Employee Onboarding** — a reusable `OnboardingTemplate` (`ONBT-`) of typed `OnboardingTemplateTask` lines
  (category / assignee-role / phase / due-offset) applied to one new hire as an `OnboardingProgram` (`ONB-`,
  draft→active→completed/cancelled) whose `OnboardingTask`s are auto-generated with `due_date = start_date + offset`
  and a **derived** progress %; plus `OnboardingDocument` collection with an e-sign status lifecycle (allowlisted
  uploads), `AssetAllocation` (`AST-`, laptop/ID/access-card issue→return), and `OrientationSession` scheduling
  with attendance. Welcome Kit (welcome message/video/first-day notes + buddy) lives on the program.
- **3.4 Employee Offboarding** — a `SeparationCase` (`SEP-`) hub driving resignation→approval→clearance→F&F→
  completion (status `draft→pending_approval→in_clearance→cleared→settled→completed`, with **derived**
  `expected_last_working_day` and an `all_mandatory_cleared` gate); on approval a `generate_clearance_checklist`
  service auto-builds the per-department `ClearanceItem` lines (clearing an IT line **returns the linked issued
  `AssetAllocation`** in the same txn); an `ExitInterview` (`EI-`) with 8 Likert ratings + coded reason; a
  `FinalSettlement` (`FNF-`) with earnings/deductions and a **derived** `net_payable`, `Compute` auto-fills leave
  encashment + gratuity, then HR→Finance approve→paid; and auto-generated relieving/experience letters
  (print views). GL posting deferred (`gl_posted` stub → `accounting.PayrollRun`).
- **3.5 Job Requisition** — the "authorization to hire". A `JobRequisition` (`JR-`) hub carries the opening's
  title/designation/grade, department + cost-center (`core.OrgUnit`), headcount, req-type, budget (salary range +
  estimated annual cost + hiring-cost budget) and a job-description body, with hiring_manager/recruiter as
  `EmployeeProfile`s. It runs a sequential **approval chain** of `RequisitionApproval` steps (the immutable audit
  trail) through a `draft→pending_approval→approved→posted→on_hold→filled` lifecycle (+ rejected/cancelled, all
  status fields workflow-owned, never on the form); on submit a `generate_approval_chain` service auto-builds the
  default HR→Executive chain. A reusable `JobDescriptionTemplate` (`JDTMPL-`) library pre-fills the JD via a
  copy-on-apply `apply_template_to_requisition` service; plus per-step approve/reject/return, clone, and an
  overdue indicator. Offers are built in 3.8 (an `Offer` FKs the `JobApplication`).
- **3.6 Candidate Management** — the ATS. A `CandidateProfile` (`CAND-`) is a `core.Party`(person) +
  `PartyRole(candidate)` lens (mirrors `EmployeeProfile`) with resume/skills/source/GDPR consent + talent-pool
  `CandidateTag`s and structured `CandidateSkill`s. `JobApplication` (`APP-`) is the pipeline record against a
  3.5 `JobRequisition` (10-stage machine applied→…→interview→offer→hired, no double-apply). Recruiting
  `CandidateEmailTemplate`s (auto-send on stage transitions) log to an append-only `CandidateCommunication` trail
  (honors `do_not_contact`); plus a **public, unauthenticated career portal** (`careers_list`/`careers_apply` via an
  unguessable `public_token`) that mints the Party+application on submit.
- **3.7 Interview Process** — scheduling + panel + structured scorecards over the 3.6 application. An `Interview`
  (`INTV-`) is a scheduled round on a `JobApplication` (mode in-person/phone/video; status machine scheduled→
  confirmed→in_progress→completed +cancelled/no_show/rescheduled, with reschedule reopening a closed round); an
  `InterviewPanelist` assigns interviewers (role + RSVP); an `InterviewFeedback` (`IFB-`) scorecard (one per panelist,
  5-level hire recommendation, action-only submit) holds per-competency `FeedbackCriterion` ratings (1–5). Candidate
  invites/reminders reuse the 3.6 email pipeline (`interview_invite`/`interview_reminder` templates →
  `CandidateCommunication`); a panel feedback-request nudge emails the interviewers. Calendar/Zoom-Teams-Meet/SMS
  auto-dispatch + AI scoring deferred.
- **3.8 Offer Management** — offer-letter generation + multi-step approval + tracking + background verification +
  pre-boarding over the 3.6 application. An `Offer` (`OFR-`) hangs off a `JobApplication` with a compensation
  breakdown (base/bonus/signing/equity/relocation/benefits) and a workflow-owned status machine
  (draft→pending_approval→approved→extended→accepted/declined/rescinded/expired, never form-set); on submit a
  `generate_offer_approval_chain` service builds the default Hiring-Manager→HR chain (+ an Executive step for
  high-value offers), and the approval gate blocks extension until every `OfferApproval` step is approved. Accepting
  an offer drives the application to `hired` (+ `hired_on`) and raises a `generate_preboarding_checklist`.
  A `BackgroundVerification` (`BGV-`) tracks the Checkr/Sterling-style status+result lifecycle (consent-before-initiate
  gate, report attachment); `PreboardingItem`s collect pre-start documents (submit/verify/reject + candidate invite);
  a reusable `OfferLetterTemplate` (`OLTMPL-`) merge-renders a printable offer letter. Offer emails reuse the 3.6
  candidate pipeline (`offer` template type → `CandidateCommunication`). Live e-signature / background-check vendor
  APIs, adverse-action dispute flow, parallel/rule-engine approval routing + acceptance-rate analytics deferred.
- **3.9 Attendance Management** — `AttendanceRecord` (`ATT-`, auto `hours_worked` incl. overnight, late-arrival
  badge, source/status, + GPS `latitude`/`longitude`/`geofence` capture with a derived `geo_status()`), `Shift`
  (grace window) + `ShiftAssignment`, `GeoFence` (GPS zones with real haversine proximity), and
  `AttendanceRegularization` (`REG-`, draft→pending→approved/rejected/cancelled punch-correction workflow —
  admin approval rewrites the linked punch to `regularized`, materialising a punch when none is linked).
- **3.10 Leave Management** — `LeaveType` (accrual/carry-forward/encashment policy), `LeaveAllocation` (`LA-`,
  **derived** balance = allocated − used − encashed, with `carried_forward`/`encashed_days` bookkeeping),
  `LeaveRequest` (`LR-`) with a draft→pending→approved/rejected/cancelled workflow (days auto-computed minus
  non-optional holidays); a **Leave Policy engine** (idempotent admin accrual + year-end carry-forward runs over
  allocations); and `LeaveEncashment` (`ENC-`) to encash unused leave into a payout (draft→pending→approved→paid,
  approval consumes balance via `encashed_days` so a later accrual re-run can't restore cashed-out days).
- **3.11 Time Tracking** — `Timesheet` (`TS-`, weekly header with **derived** `total_hours`/`billable_hours`
  recomputed from entries, draft→pending→approved workflow, entries locked on approval), `TimesheetEntry` (inline
  time lines against an optional `accounting.Project` + billable flag/rate), and `OvertimeRequest` (`OT-`,
  hours × multiplier, pay-or-comp-leave); plus billable/utilization + project-time-vs-budget report pages.
- **3.12 Holiday Management** — `PublicHoliday` calendar (national/regional/company/observance **category** +
  optional/floating flag), `HolidayPolicy` (location/department/employee-type/designation **eligibility** +
  floating-holiday **quota** + a `for_employee` most-specific-match resolver), and `FloatingHolidayElection`
  (employees elect optional holidays, quota-enforced in `clean()`, with a tenant-admin approve/reject workflow).
- **3.13 Salary Structure** — `PayComponent` (unified catalog: earnings / statutory / voluntary deductions /
  reimbursements / variable pay, with calc-type / frequency / taxable / contribution-side / cap flags — covers 4 of
  the 5 bullets), `SalaryStructureTemplate` (`SST-`, grade-wise CTC container with a **derived** `computed_ctc_total`)
  + inline `SalaryStructureLine` breakdown (PROTECT to its component), and `EmployeeSalaryStructure` (`ESS-`,
  effective-dated per-employee CTC assignment, one-active-per-employee, superseded records read-only). The
  compensation **definition** layer — the payroll run/posting stays in `accounting.PayrollRun` (3.14).
- **3.14 Payroll Processing** — the operational payroll run: `PayrollCycle` (`PRC-`, regular/off-cycle/bonus, a
  draft→pending→approved/rejected→locked approval workflow) computes a `Payslip` (`PSL-`) per employee from their
  active 3.13 salary structure (a `recompute()` calc engine: monthly-from-CTC, day pro-ration, LOP, arrears/bonus,
  with employer-side statutory excluded from net), an immutable `PayslipLine` breakdown snapshot, plus salary holds.
  On **lock** it rolls the totals up into `accounting.PayrollRun` for the GL journal — HRM builds no `JournalEntry`
  (L29); accounting posts it.
- **3.15 Statutory Compliance** — the Indian statutory-payroll compliance layer over 3.13/3.14 (PF/ESI/PT/TDS/LWF):
  a `StatutoryConfig` tenant settings singleton (employer PF/ESI codes, wage ceilings, rates, TAN/PAN), state-wise
  `StatutoryStateRule` PT slabs + LWF periodicity/amounts (supersede-not-edit via `is_active`/`effective_from`),
  per-employee `EmployeeStatutoryIdentifier` (UAN/PF/ESI, masked in the UI), and a `StatutoryReturn` (`SCR-`)
  per-scheme/period register whose contribution totals are **aggregated from `PayslipLine`** (a `recompute()`
  mirroring the 3.14 lock roll-up, never hand-typed) with a pending→filed→paid/late filing workflow (paying after
  the due date auto-flags **Late**) and a cross-scheme compliance calendar. Reuses the payroll spine; touches no GL.
- **3.16 Tax & Investment** — the Indian income-tax declaration + computation layer over 3.13/3.14/3.15: per-FY/regime
  `TaxRegimeConfig` (+ `TaxSlabBand` slab table, standard deduction, 4% cess, Section 87A rebate), a per-employee
  `InvestmentDeclaration` (`ITD-`, draft→submitted→locked, 80C/80D/HRA/24b/NPS section lines with declared-vs-verified
  amounts) with `InvestmentProof` uploads (4-state verification), and a `TaxComputation` (`TXC-`) **engine** —
  `recompute()` walks the slabs (progressive tax → 87A rebate → cess), does the HRA 3-way exemption, regime-filters
  Chapter VI-A deductions (new regime keeps only NPS + standard deduction), caps per section, aggregates TDS-paid-YTD
  from `PayslipLine`, and spreads the balance across remaining pay periods — plus an old-vs-new regime comparison and a
  **Form 16 Part B** report that reuses the existing `StatutoryReturn(tds_form16)` (no new Form 16 table). Posts no GL.
- **3.17 Payout & Reports** — the salary-disbursement + reconciliation layer over 3.14: a `PayoutBatch` (`POB-`,
  generated from a **locked** `PayrollCycle`, draft→approved→disbursed/partially_disbursed→reconciled) with one
  `PayoutPayment` per payslip — snapshotting `net_pay` + the employee's **masked** bank details (never the raw
  account), a pending→processing→paid/failed/returned lifecycle, a bank UTR, and a `retry_of` re-initiation chain
  (a retry supersedes the failed original so totals never double-count); a `PayslipDistribution` (1:1) tracking the
  payslip send→viewed→downloaded signal; a `BankReconciliation` (`BRC-`) matching payments to the statement by UTR
  (`reconciled`/`discrepancy`); plus a **payment register** (bank-advice) and **exceptions** report. The bank-file
  writer, payslip-PDF render and live bank API are deferred; posts no GL.
- **3.18 Goal Setting** — the first Performance-Management sub-module (OKR mechanics): a `GoalPeriod` quarterly/annual
  cycle catalog (activate/close), an `Objective` (`OBJ-`) owned by an `EmployeeProfile` with a `parent_objective`
  self-FK cascade (Goal Alignment), a `core.OrgUnit` department scope, a weight, and **derived** weighted `progress_pct`
  + pace-based `health_status` (on_track/at_risk/off_track); a `KeyResult` (`KR-`) with 5 metric types
  (numeric/percentage/currency/boolean/milestone) + per-KR weight; and an **append-only** `GoalCheckIn` (`GCI-`) history
  log whose save advances the KR's current value. Includes a recursive **alignment tree** (company→department→
  individual) and a **?mine** own-and-direct-reports view. Reuses `EmployeeProfile` + `core.OrgUnit` (no new core-spine
  entity, posts no GL); ratings/reviews/360/kudos/PIP are deferred to 3.19–3.21.
- **3.19 Performance Review** — the second Performance-Management sub-module (formal appraisal cycles): a `ReviewCycle`
  with a 6-phase machine (draft→self-assessment→manager-review→calibration→released→closed, admin-advanced) + an optional
  link to a 3.18 `GoalPeriod`; a `ReviewTemplate` (`RVT-`) per review type (self/manager/peer/upward/skip-level); a
  `PerformanceReview` (`RVW-`) with **derived** weighted `overall_rating`, a stored `calibrated_rating` that overrides it
  (`effective_rating`), a `potential_rating`, and manager-only `private_notes`; and `ReviewRating` (`RVR-`) weighted
  competency lines. Covers self/manager/peer/upward reviews with a submit→share→acknowledge workflow, a
  **calibration board** (manager reviews ranked by effective rating), and a goal-review section reading the subject's
  Objectives. **Performance data is confidential** — visible only to the subject, reviewer, or a tenant admin, and
  content is edit-locked once submitted. Reuses `EmployeeProfile` + the 3.18 goal models (no new spine, posts no GL);
  continuous feedback/PIP are deferred to 3.20–3.21.
- **3.20 Continuous Feedback** — the third Performance-Management sub-module (the ongoing/informal layer): a `Feedback`
  (`FBK-`) row for real-time kudos/appreciation/constructive feedback with `visibility` (private/team/public), an
  `is_anonymous` flag that **masks the giver on read** for non-admin/non-giver viewers (cloning the 3.19 reviewer
  masking), optional `badge`/`related_objective`/`related_review` links, and a `requested_from` self-FK that folds the
  **request-feedback pull workflow** (requested→given→acknowledged) into one table; a `KudosBadge` recognition catalog
  (values-tag chips); an `OneOnOneMeeting` (`O2O-`) with a shared agenda/notes and **manager-only
  `manager_private_notes`** (never rendered employee-side; the edit form is manager/admin-gated), scheduled→completed/
  cancelled workflow, and `MeetingActionItem` (`MAI-`) children (owner + due date + open/done toggle); plus a computed
  **Feedback Dashboard** (given/received/requested + per-type mix + 30-day velocity — a view, not a model). Confidential
  by design (`_can_view_feedback`/`_visible_feedback_q`/`_can_edit_feedback`). Reuses `EmployeeProfile` + the 3.18/3.19
  models (no new spine, posts no GL); PIP/warning-letters/coaching are deferred to 3.21.
- **3.21 Performance Improvement** — the fourth & FINAL Performance-Management sub-module (the corrective-action /
  disciplinary layer, the most confidential HRM records): a `PerformanceImprovementPlan` (`PIP-`) with an HR-approval
  workflow (draft → pending → active → closed), structured issue/standards/goals/support/measurement sections, an
  optional link to the triggering 3.19 `PerformanceReview`, a close-with-outcome step (successful/extended/failed/
  terminated) and an extend path, plus `PIPCheckIn` (`PCI-`) scheduled progress checkpoints; a `WarningLetter`
  (`WRN-`) for progressive discipline (verbal → written → final → suspension across attendance/conduct/performance/
  policy) with an issue → acknowledge workflow, an employee-response field, a derived `prior_warnings` escalation
  view, and a printable letter; and a `CoachingNote` (`CN-`) manager journal — **the strictest gate in the system:
  visible only to the coach and admin, NEVER to the coached employee**. Confidential throughout
  (`_can_view_pip`/`_can_view_warning`/`_can_view_coaching`). Reuses `EmployeeProfile` + the 3.19 review (no new
  spine, posts no GL). **Performance Management (3.18–3.21) is now complete.**
- **3.22 Training Management** — the Instructor-Led-Training scheduling/catalog layer (a NEW HRM domain, ordinary
  tenant-scoped CRUD — no confidentiality gate): a `TrainingCourse` (`TRC-`) catalog (category/delivery-mode/provider
  split, duration, certification name + validity, a self-FK prerequisite chain, default capacity) and a
  `TrainingSession` (`TRS-`) scheduled occurrence unifying **Classroom / Virtual / External** delivery via
  `delivery_mode` — venue + capacity/waitlist, meeting platform/link/id, an internal `EmployeeProfile` instructor or a
  named external trainer, an external vendor (`core.Party` vendor role — no new vendor table), and estimated/actual
  cost in an `accounting.Currency` — with a `clean()` that enforces the mode-specific required fields plus an
  **instructor/venue double-booking overlap guard**, derived `can_join`/`is_upcoming` props, and a **Training Calendar**
  date-grouped upcoming view. Reuses `EmployeeProfile` + `core.Party` + `accounting.Currency` (no new spine, posts no
  GL); 3.23 LMS (content/paths/assessments) and 3.24 Training Administration (nomination/attendance/certificates/
  budget) are deferred sibling sub-modules.
- **3.23 Learning Management (LMS)** — the self-paced digital-learning layer on top of the 3.22 `TrainingCourse`
  catalog (ordinary tenant-scoped CRUD, no confidentiality gate): a `LearningContentItem` (a CASCADE child of a
  course — ordered video/document/SCORM/external-link/text lessons + a lightweight `assessment` variant with
  pass-threshold/max-attempts/time-limit, `clean()` enforcing the type-matching content field; SCORM stored as an
  opaque file with a zip-slip WARNING for future extraction), a `LearningPath` (`LNP-`) role-based journey targeting
  `Designation`/`core.OrgUnit` department + its ordered `LearningPathItem` course steps (with a `clean()`
  prerequisite-gating guard reusing `TrainingCourse.prerequisite_course`), and a `LearningProgress` (unique per
  employee×course) tracking status/percent/time-spent/score/passed/attempts/`points_earned` with a derived
  `certification_expires_on`. Gamification ships as a **computed points leaderboard** (Bronze/Silver/Gold/Platinum
  tiers) + a manager **team-progress** rollup — no stored leaderboard/badge tables. Reuses `TrainingCourse` +
  `EmployeeProfile` + `Designation`/`OrgUnit` (no new course/learner/role tables, posts no GL); a question-bank
  assessment engine, SCORM runtime/xAPI, an achievement-badge catalog, and 3.24 Training Administration
  (nomination/attendance/feedback/certificates/budget) are deferred.
- **3.24 Training Administration** — the operational/admin layer over 3.22 sessions + 3.23 LMS (ordinary
  tenant-scoped CRUD): a `TrainingNomination` (`NOM-`) — an employee nominated for a `TrainingSession` with a
  single-approver workflow (self/manager/HR nomination → pending → approve[/waitlist if the session is full] /
  reject / cancel / withdraw, manager-or-admin gated via the reporting line, mirroring the LeaveRequest shape); a
  `TrainingAttendance` (per-session-per-employee — registered/present/absent/partial/walk-in + completion +
  check-in/out, linking back to its nomination); a `TrainingFeedback` (Kirkpatrick-L1 overall/content/trainer 1–5
  ratings + would-recommend + anonymous masking cloned from 3.20 Feedback); and a `TrainingCertificate` (`CERT-`) —
  an issuance record from a completed `TrainingAttendance` (ILT) **or** `LearningProgress` (LMS), with a
  `secrets`-based verification code, `expires_on` computed once from the course validity (via a shared
  `_advance_months` helper refactored out of 3.23), a revoke workflow, and a printable certificate. **Training
  Budget** is a **computed view** (the year's training spend — estimated vs actual, by course — vs the allocated
  `CostCenterProfile.budget_annual`), no stored model. Reuses `TrainingSession`/`TrainingCourse` (3.22) +
  `LearningProgress` (3.23) + `EmployeeProfile`/`CostCenterProfile` (no new session/learner tables, posts no GL); the
  N-step approval engine, QR check-in, multi-level Kirkpatrick, a branded certificate-PDF renderer, and a public
  verify-by-code page are deferred. **Training (3.22 ILT + 3.23 LMS + 3.24 Administration) is now complete.**
- **3.25 Personal Information (Self-Service)** — the Employee Self-Service (ESS) layer over the existing
  `EmployeeProfile` (which already carries flat bank/emergency/address/personal-file columns), so this pass adds the
  *self-service surface* + the child tables the flat columns can't model + an HR maker-checker approval workflow, not
  a re-model of the profile. A `my_info` hub (read-only employment context + the employee's direct-edit contact fields
  + masked sensitive fields, each with a "Request a Change" link) and its `my_info_edit` form (address / personal
  email / mobile / photo only); `EmergencyContact` — an unlimited roster (vs the 2 flat profile slots) with an
  auto-demote `is_primary`, **direct self-edit** (no approval gate); `EmployeeBankAccount` — multiple accounts with an
  auto-demote `is_salary_account`, Gusto-style `split_percentage`, a pending→verified/rejected verify workflow, and a
  `masked_account_number()` shown everywhere (the raw number is never rendered, and it's redacted from the AuditLog);
  `FamilyMember` — dependents/nominees with a guardian-required-when-minor rule; and `EmployeeInfoChangeRequest`
  (`ICR-`) — the maker-checker workflow (a `GenericForeignKey` gating sensitive `EmployeeProfile` fields [legal name →
  `core.Party.name`, DOB, national ID, passport], bank writes, and family writes) with an `apply()` that writes the
  approved change atomically, a lost-update guard, and maker-checker separation (the requester/subject can't self-
  approve). Bank/family writes are tenant-admin-only (an employee proposes them via a change request); emergency
  contacts + the my_info contact fields are direct self-edit. A per-tenant configurable field-permission matrix,
  effective-dated history, per-scheme statutory nomination, and live bank verification are deferred.
- **3.26 Request Management (Self-Service)** — the employee request portal. Leave Requests and Attendance
  Regularization **reuse** the existing 3.10 `LeaveRequest` / 3.9 `AttendanceRegularization` models (no new table —
  they just gain a second sidebar entry), and this pass adds three new request models plus a unified **My Requests**
  hub. `DocumentRequest` (`DOCREQ-`) — official-letter requests (experience letter / salary certificate / employment
  verification / NOC / address proof) with purpose, addressed-to, copies and delivery method, whose `document_fulfill`
  action can attach an HR-uploaded signed letter (validated through the shared `_validate_upload` helper);
  `IdCardRequest` (`IDREQ-`) — new/replacement/correction/renewal cards with a lost/damaged/expired/name-change reason
  taxonomy, issued via `idcardrequest_issue` (stamping a card number); `AssetRequest` (`ASSETREQ-`) — equipment
  requests reusing `AssetAllocation.ASSET_CATEGORY_CHOICES`, whose `assetrequest_fulfill` **creates and links an
  `AssetAllocation`** (`program=None`, `status=issued`) inside one atomic transaction. All three run the
  `draft → pending → approved/rejected/cancelled` (+ fulfillment tail) lifecycle, reuse the ESS self-service helpers
  (`_ss_child_*`, `_ss_scope`, `_can_manage_own_child`) so an employee sees only their own rows, and enforce a
  3.25-style **self-approval guard** (an admin who is the requesting employee can't approve/reject their own request;
  reject requires a note). Configurable multi-level approval chains, SLA auto-escalation, template-driven letter
  generation, e-signature, notifications, and software/license access requests are deferred.
- **3.27 Communication Hub** — the internal employee-communications surface. Four new models + a derived
  celebrations view. `Announcement` (`ANN-`) — admin-authored company news with category, audience targeting
  (all / a department [`core.OrgUnit` kind=department] / a designation [`hrm.Designation`], reusing the
  `LearningPath` 3.23 precedent), pinning, and a draft→published→archived lifecycle (`publish` stamps
  `published_at`; the employee feed shows only published, un-expired, for-them posts via an audience `Q`-filter,
  enforced on the detail page too); `Survey` (`SUR-`) + `SurveyResponse` — an engagement survey whose questions are
  structured JSON (rating / text / single-choice; a 0–10 rating covers eNPS), draft→open→closed, employees respond
  **once** (`unique_together(survey, employee)`), and `is_anonymous` suppresses respondent identity in the aggregated
  results; `Suggestion` (`SUG-`) — an employee idea box that **clones the 3.26 request lifecycle field-for-field**
  (owner `employee` FK + `approver`/`approved_at`) so the shared `_hr_request_*` helpers apply verbatim
  (draft→pending→approved[Accepted]/rejected/cancelled + an `implemented` tail), with the same self-approval guard;
  and **Celebrations** — a derived view (no model, mirrors `org_chart`) of upcoming birthdays
  (`EmployeeProfile.date_of_birth`) + work anniversaries (`core.Employment.hired_on`) within a `?window=`. The 5th
  bullet, **Help Desk**, now resolves to the dedicated **3.36 Helpdesk** sub-module (its sidebar entry points at
  the live ticket list). Read receipts, reactions, delivery fan-out, survey k-anonymity, and voting are deferred.
- **3.28 HR Reports** — the core HR analytics surface, built as **6 derived, read-only, `@tenant_admin_required`
  report views** (NO new models — pure tenant-scoped aggregates over the existing spine, mirroring accounting's
  `trial_balance`/`ap_aging`): an `hr_reports_index` landing hub + `headcount_report` (active/joins/exits by
  department/designation[+budgeted]/type, 12-month trend), `attrition_report` (SHRM annualized turnover with
  voluntary/involuntary split, by department/exit-reason/tenure-band, monthly trend), `diversity_report`
  (gender/age-band/tenure-band distributions + a department × gender cross-tab), `cost_report` (per-`PayrollCycle`
  gross + employer-contribution cost, department-wise + CTC-component breakdown, cross-cycle trend, with an
  `EmployeeSalaryStructure` CTC/12 run-rate fallback flagged as *Estimated* when no payroll run exists), and
  `hiring_report` (time-to-fill/time-to-hire, source-of-hire mix, application funnel, offer-acceptance approximation,
  hires by department). Every rate guards div-by-zero, `?department` is resolved tenant-scoped (IDOR-safe), and
  `EmployeeProfile` aggregation goes through `employment__org_unit` (department/manager are `@property`, not columns).
  Trends render via the Chart.js already loaded in `base.html`. FTE/EEO PII fields, true cost-per-hire, attrition-risk
  ML, and the drag-drop dashboard builder (3.32) are deferred.
- **3.29 Attendance Reports** — **5 derived, read-only, `@tenant_admin_required` report views** (NO new models,
  reusing the 3.28 report helpers): `attendance_reports_index` + `attendance_summary_report` (status breakdown +
  attendance % = present-equivalent [present + regularized + ½·half-day] ÷ tracked-days [excludes holiday/on-leave],
  by department, monthly trend), `late_early_report` (late-arrival [mirroring `AttendanceRecord.is_late()`'s
  boundary math inline, to also get minute counts] + early-departure counts + avg minutes, top-offenders,
  day-of-week pattern — one `select_related` pass),
  `absenteeism_report` (absence rate + frequent-absentee list + monthly trend), and `overtime_report` (total +
  pay-equivalent hours [`hours_claimed × multiplier`], by employee/department, status mix, trend — **hours only, no
  currency**, no pay-rate source). The **Utilization Report** bullet reuses the existing 3.11
  `timesheet_utilization_report`. Monthly trends use a single `TruncMonth`-grouped query; every rate guards
  div-by-zero. Currency OT cost, scheduled-vs-worked hours, Bradford-Factor discipline, and muster-roll grids are
  deferred.
- **3.30 Leave Reports** — **5 derived, read-only, `@tenant_admin_required` report views** (NO new models, reusing
  the 3.28 helpers + the 3.10 leave models): `leave_reports_index` + `leave_register_report` (per-employee×type
  allocated/carried/availed/encashed/balance for a `?year`), `leave_liability_report` (encashable-only, balance>0;
  days × per-day rate → value; rate = latest approved/paid encashment, else annual-CTC÷365 estimate, else none),
  `comp_off_report` (OT-comp-leave earned vs comp-off-leave availed), `leave_trend_report` (approved-leave days,
  by-type, top-takers, monthly trend). Availed-days are annotated via a correlated subquery (`used_db`, no per-row
  N+1); per-employee dicts key on `employee_id`, not the non-unique display name.
- **3.31 Payroll Reports** — **6 derived, read-only, `@tenant_admin_required` report views** (NO new models,
  aggregating the 3.13-3.16 payroll engine): `payroll_reports_index` + `salary_register_report` (per-`Payslip`
  earnings/deductions/net grid for a `?cycle` + component-type breakdown), `tax_report` (TDS summary from
  `TaxComputation`, investment-declaration funnel, section-wise declared/verified, regime split, Form 16
  linked/pending register → `form16_partb`), `statutory_report` (PF/ESI/PT/LWF register from `StatutoryReturn` +
  **masked** UAN/PF/ESI employee-coverage), `ctc_report` (structural annualized CTC from active
  `EmployeeSalaryStructure` + component-type mix chart), and `cost_center_report` (budget-vs-actual per
  `CostCenterProfile`, attributing each employee's department to its mapped cost centre via
  `DepartmentProfile.cost_center`, unmapped spend surfaced in an **Unassigned** callout). GL posting, Form 16 PDF,
  statutory e-filing (ECR/24Q), and multi-level cost-centre roll-up are deferred.
- **3.32 Analytics Dashboard** — the dashboard layer over the 3.28-3.31 reports, mirroring CRM 1.6's saved-dashboard
  mechanic: **2 new models** (`HRDashboard` + `HRDashboardWidget`) with a live-compute layer (`apps/hrm/analytics.py`,
  a 16-metric catalog computed on each render) so a user can assemble/save a **custom dashboard** of KPI/gauge/chart/
  table widgets (owner-or-admin gated, shareable tenant-wide), **plus 3 derived `@tenant_admin_required` views**:
  `executive_dashboard` (leadership KPI strip + sparklines + alerts), `predictive_analytics` (a transparent
  attrition-risk heuristic — tenure/attendance/leave/probation/review-gap, *not* ML — plus a hiring-needs
  projection), and `benchmarking` (period-over-period RAG scorecard with optional vs-target override + a
  pay-equity table). A true drag-drop grid, trained ML models, and external industry-benchmark feeds are deferred.
- **3.33 Asset Management** — the HR-facing asset register the 3.3 `AssetAllocation` issuance rows now point at:
  **2 new models** — `Asset` (`ASSET-`; tag/serial/category/status lifecycle [in_stock/assigned/in_repair/retired/
  disposed] + **computed straight-line/declining-balance depreciation** book value, floored at salvage) and
  `AssetMaintenance` (`ASSETMNT-`; preventive/repair/AMC/warranty-claim/inspection with contract windows) — plus a
  nullable `AssetAllocation.asset` FK. Asset↔allocation status/holder stay in step via two atomic `save()`-override
  syncs (no-op for pre-3.33 rows), and a "repair" record moves its asset in/out of service. Full CRUD + lifecycle
  actions (assign/return/retire/dispose, `select_for_update`-guarded) + maintenance CRUD. Barcode/QR, software-license
  management, CMMS work orders, depreciation GL posting, and the Module 11 enterprise `assets.Asset` migration are deferred.
- **3.34 Expense Management** — employee T&E expense claims (distinct from CRM's sales expense and payroll's
  reimbursement payout): **3 new models** — `ExpenseCategory` (per-claim / monthly / receipt-threshold policy limits
  + a GL-account coding hint), `ExpenseClaim` (`ECL-`; a **2-stage manager→finance approval** machine
  draft→submitted→manager_approved→approved→reimbursed, with payment tracking and computed total/violations), and
  `ExpenseClaimLine` (category / amount / merchant / **receipt upload** + a computed policy-compliance soft-flag).
  Full own-vs-admin CRUD + the six workflow actions (submit / manager-approve / approve / reject / cancel /
  reimburse — each self-approval-blocked for an admin acting on their own claim), inline draft-only line editing, and
  receipt validation (extension allowlist + size cap). OCR, corporate-card reconciliation, mileage/per-diem, cash
  advances, multi-currency FX, N-level routing, the payroll-payout integration, and GL posting are deferred.
- **3.35 Travel Management** — trip authorization with a travel advance and post-trip settlement: **3 new models** —
  `TravelPolicy` (per-job-grade class-of-travel + daily/hotel/advance-percent caps, scoped domestic/international/both),
  `TravelRequest` (`TRV-`; a single-approver machine draft→pending→approved/rejected/cancelled then approved→completed
  — reusing the shared request-workflow helpers verbatim — plus advance request/approve/pay and a computed
  net-settlement), and `TravelBooking` (flight/hotel/cab lines with a **document upload** and a computed **out-of-policy**
  flag driven by the policy's class-rank + hotel-per-night caps). Full own-vs-admin CRUD, the advance actions
  (approve capped at the policy percent + maker-checker self-block; idempotent mark-paid), and **Generate Settlement**
  that spins up a linked 3.34 `ExpenseClaim` (atomic + idempotent). Corporate-booking-tool (GDS) integration,
  multi-leg itineraries, real-time fare shopping, and per-diem auto-calc are deferred.
- **3.36 Helpdesk** — the employee HR/IT/Admin/Facilities service desk. **4 new models** (`apps/hrm/models.py`,
  migrations `0051`+`0052`): `HelpdeskSLAPolicy` (`HSLA-`; per-priority response/resolution hour targets +
  `targets_for(priority)`, a mirror of `crm.SlaPolicy`), `HelpdeskCategory` (HR/IT/Admin/Facilities routing +
  KB taxonomy, carrying the default assignee + default SLA policy a new ticket inherits), `HelpdeskTicket`
  (`TKT-`; requester `employee` FK reuses `_ss_scope`/`_can_manage_own_child`; an **agent-worked** lifecycle
  new→open→in_progress→waiting→resolved→closed [+cancelled] via bespoke assign/start/waiting/resolve/close/
  reopen/cancel/feedback actions — NOT the single-approver `_hr_request_*` machine; SLA due timestamps stamped
  once in `save()` [mirrors `crm.Case`] with **computed** breach / `sla_state`; inline **CSAT**
  [`satisfaction_rating`/comment, no separate survey model]), and `KnowledgeArticle` (`KBA-`; internal-only
  FAQ/self-help, draft→published→archived, view/helpful counters). `LIVE_LINKS["3.36"]` maps all 5 bullets
  (Ticket Management→`ticket_list`, Ticket Categories→`helpdeskcategory_list`, SLA Management→`helpdesksla_list`,
  Knowledge Base→`knowledgearticle_list`, Satisfaction Survey→`ticket_list?rated=1`) + an SLA-breach deep-link
  (`ticket_list?sla=breached`); the 3.27 "Help Desk" bullet is re-pointed here. A comment thread, auto-routing/
  escalation, business-hours SLA clocks, KB voting/public portal, and a CSAT analytics dashboard are deferred.

- **3.37 Compensation & Benefits** — market benchmarking, benefits enrollment, and equity. **4 new models**
  (`apps/hrm/models.py`, migrations `0053`+`0054`): `SalaryBenchmark` (external P25/P50/P75/P90 market data keyed
  to a `JobGrade`/`Designation` + a `compa_ratio(pay)` method — builds ON the 3.2 salary bands + 3.13
  `EmployeeSalaryStructure`, never duplicating them), `BenefitPlan` (the medical/dental/life/retirement catalog with
  an employer/employee monthly cost split, flex-credit eligibility, CSV coverage tiers and an enrollment window),
  `EmployeeBenefitEnrollment` (`BEN-`; the opt-in/opt-out/waived election — `employee` FK reuses
  `_ss_scope`/`_can_manage_own_child`, effective-dated, with **server-derived contributions** [the plan's costs are
  never user-settable — employer money] and an admin `enroll`/`waive`/`terminate` lifecycle), and `EquityGrant`
  (`ESOP-`; ISO/NSO/RSU/ESPP/phantom grants with a cliff + graded vesting schedule whose `vested_shares` /
  `vested_percent` / `unvested_shares` / `exercisable_shares` are **computed, never stored** — only
  `exercised_shares` is persisted, via a guarded `record_exercise` action). `LIVE_LINKS["3.37"]` lights **4 of the 6**
  bullets (Salary Benchmarking, Benefits Administration, Flexible Benefits, Stock/ESOP Management); Compensation
  Planning (merit/promotion cycles) and a formal monetary Rewards & Recognition are deferred — peer kudos already
  ship in 3.20. Carrier EDI, AI job-pricing, 409A/ASC-718 GL posting, and cap-table modeling are deferred.

- **3.38 Talent Management & Succession Planning** — the HiPo/9-box + succession-bench layer, built **on** the
  3.19 `PerformanceReview` ratings rather than duplicating them. **4 new models** (migration `0055`):
  `TalentPool` (hipo / successor / critical-skill / leadership segments), `TalentPoolMembership` (the 9-box row —
  its `review` FK supplies the two axes [`effective_rating` = performance, `potential_rating` = potential] with
  optional per-member overrides, plus `flight_risk` + a `retention_action_plan`; `nine_box_quadrant` is
  **computed, never stored** — a 3×3 label lookup from the banded ratings: Star / Emerging Star / Core Player /
  Enigma / Underperformer …), `SuccessionPlan` (`SPL-`; a critical role's bench with `vacancy_risk` and a
  **computed** `bench_strength` from successor readiness), and `SuccessionCandidate` (the ranked inline bench).
  A derived **9-box grid** view buckets active members (rows = potential, columns = performance) with an
  "unplaced" list for the unrated. **CONFIDENTIAL:** every 3.38 view is `@tenant_admin_required` — an employee
  must never learn they're in a HiPo pool, on a bench, or flagged a flight risk (the 3.21 precedent).
  `LIVE_LINKS["3.38"]` lights **5 of 6** bullets, and notably **two need no new table**: *Talent Reviews* reuses
  the 3.19 calibration board and *Internal Mobility* reuses `JobRequisition(posting_type="internal")` + the 3.6
  application pipeline. *Career Pathing* is deferred (needs a CareerPath + EmployeeSkill taxonomy).
- **3.39 Compliance & Legal** — the employment-lifecycle compliance layer. **5 new models** (migrations `0053`–`0057`):
  `EmploymentContract` (`ECON-`; permanent/fixed-term/probation/consultant, with a **computed** `is_expiring_soon`
  60-day window), `HRPolicy` (versioned, draft→published→archived; **publishing goes only through the dedicated
  action**, which stamps `published_at` and raises the acknowledgment rows — the create/edit form offers
  draft/archived only, so it can't silently skip acknowledgments), `PolicyAcknowledgment` (per-employee, employee
  self-service), `Grievance` (`GRV-`; severity + **anonymous complainants masked from everyone but HR**, investigate→
  resolve→close), and `ComplianceRegister` (`CREG-`; statutory filings with a **computed** `is_overdue`).
  `LIVE_LINKS["3.39"]` lights **all 6** bullets — *Disciplinary Actions* reuses the 3.21 `WarningLetter` (no new
  table).
- **3.40 Workforce Planning** — demand/supply/gap/scenario planning. **4 new models** (migrations `0058`/`0059`):
  `WorkforcePlan` (`WFP-`; a planning cycle whose four headcount/budget totals are **computed and annotation-aware** —
  the list annotates them so rendering N plans never fires 4N aggregates), `WorkforcePlanLine` (per-department current
  vs planned headcount with a **computed** gap and budget impact — `None`, not 0, when unpriced), `WorkforceScenario`
  (`WFS-`; **signed** what-if deltas for hiring-freeze/restructuring, with an enforced one-baseline-per-plan), and
  `EmployeeSkill` (the skills inventory behind Supply Analysis, **own-vs-admin self-service**). Two derived reports —
  a **gap analysis** (current vs planned per department, grouped by org-unit id so same-named departments don't merge)
  and **workforce analytics** (headcount + skill-coverage + hiring-mix). **CONFIDENTIAL:** every plan/scenario/report
  view is `@tenant_admin_required` (restructuring/reduction headcount); only the skills inventory is employee-facing.
  `LIVE_LINKS["3.40"]` lights **all 6** bullets.
- **3.41 Employee Engagement & Wellbeing** — an **extension** pass that reuses 3.27's `Survey`/`SurveyResponse`
  (pulse/eNPS delivery) and `Announcement` (values content) rather than rebuilding them. **4 new models** (migration
  `0060`): `SurveyActionPlan` (`ACTP-`; the "close the loop" gap — turns a closed survey's low scores into an owned,
  dated initiative, editable by the owner-or-admin), `WellbeingProgram` (`WBP-`; **one** `program_type`-discriminated
  catalog spanning wellness challenges, EAP/counseling, culture assessments, team events, interest groups and
  volunteering), `WellbeingParticipation` (the RSVP/attendance child — a non-admin can register or withdraw only, never
  self-award points), and `FlexibleWorkArrangement` (`FWA-`; a remote/hybrid/compressed-week request, a `TravelRequest`
  clone reusing the shared approval workflow). **CONFIDENTIAL:** EAP programs are **forced** confidential at the model
  layer, and a confidential program's roster is **aggregate-only for everyone — admins included** (even the audit trail
  is scrubbed of participant identity). `LIVE_LINKS["3.41"]` lights **all 6** bullets — the four wellbeing bullets are
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
| CSS | Tailwind (Play CDN) + `theme.css` design system | — |
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
The Django superuser `admin` has `tenant=None` by design and therefore sees no module data — administer tenants
via the Django admin or a tenant-admin account.

### Request → response flow
```
request
  → SecurityMiddleware → SessionMiddleware → CommonMiddleware → CsrfViewMiddleware
  → AuthenticationMiddleware
  → TenantMiddleware            (sets request.tenant)
  → SessionTimeoutMiddleware    (idle logout)
  → MessageMiddleware → XFrameOptionsMiddleware
  → view (@login_required / @tenant_admin_required)
      → tenant-scoped queryset → template (sidebar from MODULE_CATALOG, branding from context processor)
```

### Backend organization — models / forms / views / urls are packages
The domain modules keep their backend in **Python packages, not flat `.py` files**, organized **one folder per
sub-module, then one file per entity** — the exact mirror of the template folder rule. `apps/crm` and
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
cross-app imports and every test keep importing `apps.<app>.models` / `.forms` / `.views` unchanged — and since a
model's `app_label` still derives from the app config, **the split needs no migration**. Imports *inside* a package
are absolute; cross-sub-module view helpers live in `views/_helpers.py`; there are no `*_advanced.py` sidecars. See
the "Backend Package Structure" rule in `.claude/CLAUDE.md` and the reference apps. All three domain
modules (`crm`, `accounting`, `hrm`) are converted. The Module 0 foundation apps `core` and `tenants` use
the same packages **without** the sub-module level — Module 0 has no NavERP sub-modules, so their entity
files sit flat at the package root (`core/models/Party.py`), mirroring their flat templates. Their
`urls.py` stays a flat module on purpose: `core/urls.py` is a `crud()` factory that generates the 5
standard routes per model, and expanding it would only duplicate `path()` lines. `accounts` and
`dashboard` remain flat.

### Reusable CRUD layer
`apps/core/crud.py` centralizes list/create/detail/edit/delete so every module behaves consistently and the
recurring pitfalls are fixed once:
- **Search** across declared fields; **filters** with an integer-FK guard (never pass non-numeric to an int filter).
- **Windowed pagination** (`1 … n-1 [n] n+1 … last`) — guards prev/next and preserves active filters.
- **Tenant scoping** on every read/write; orphan-row protection for tenant-less users.
- **Audit logging** on create/update/delete.

### Numbering & audit
Human-readable per-tenant document numbers (e.g. `SINV-#####`) are generated in `save()` with an existence guard
and a retry on the rare concurrent collision (`unique_together(tenant, number)`). `AuditLog` is append-only and
read-only in the UI.

### MariaDB 10.4 compatibility
Django 5.1 targets MariaDB ≥ 10.5, but XAMPP ships 10.4. [`config/__init__.py`](config/__init__.py) installs
PyMySQL as the driver and applies a compatibility shim: it lowers the version floor **and** disables
`INSERT … RETURNING` (which 10.4 cannot parse). Without this, the very first migration fails with a SQL syntax
(1064) error.

---

## Prerequisites

- **Python 3.10+** on PATH.
- **XAMPP** with **MySQL/MariaDB running** (Control Panel → Start MySQL). Developed against MariaDB 10.4.x.
- A database named **`nav_erp`** (created in setup step 3). The default XAMPP MySQL user is `root` with an empty
  password on `127.0.0.1:3306`.

> This XAMPP instance may host other databases — NavERP only ever touches **`nav_erp`**.

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

# 5. Seed demo data (idempotent — safe to re-run). Order matters:
python manage.py seed_core
python manage.py seed_accounts
python manage.py seed_tenants
python manage.py seed_crm
python manage.py seed_accounting
python manage.py seed_hrm
python manage.py seed_scm

# 6. Start the development server
python manage.py runserver
```

Then open **http://127.0.0.1:8000/** and sign in with one of the [demo logins](#seed-data--demo-logins).

> The seed commands are **idempotent**: they skip records that already exist, so you can re-run them at any time.

---

## Environment variables

Defined in `.env` (copied from `.env.example`). `.env` is git-ignored — never commit real secrets.

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
| `STRIPE_SECRET_KEY` | Stripe test secret (`sk_test_…`) | *(blank → Stripe disabled)* |
| `STRIPE_PUBLISHABLE_KEY` | Stripe test publishable (`pk_test_…`) | *(blank)* |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_…`) | *(blank)* |
| `STRIPE_PRICE_STARTER` / `_PRO` / `_ENTERPRISE` | Recurring Price IDs (`price_…`) | *(blank)* |

When `STRIPE_SECRET_KEY` **and** `STRIPE_PUBLISHABLE_KEY` are set, `STRIPE_ENABLED` becomes true and online
checkout appears; otherwise the UI shows a "configure Stripe" state and a manual **Mark as paid** action.

---

## Seed data & demo logins

Seeding creates two demo tenants (**Acme Inc** `acme`, **Globex Corporation** `globex`) with parties, org units,
employments, activities, subscriptions, invoices, branding, encryption keys, and health metrics — plus the domain
demo data: **CRM** (leads/opportunities/cases/…), **Accounting** (GL accounts, invoices/bills/payments, bank
transactions, a recurring-invoice schedule), and **HRM** (employees, designations, leave allocations/requests,
attendance, holidays, shifts; **onboarding** templates → programs with generated tasks/documents/assets/orientation;
**offboarding** separation cases with generated clearance checklists, an exit interview, and a paid final
settlement).

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| **Tenant admin** | `admin_acme` | `password` | Full Module-0 access for **Acme** |
| **Tenant admin** | `admin_globex` | `password` | Full Module-0 access for **Globex** |
| Member | `sales_acme`, `ops_acme` (and `*_globex`) | `password` | Standard, non-admin (read + profile) |
| **Superuser** | `admin` | `admin` | Django admin (`/admin/`). **`tenant=None` → module pages show no data by design.** |

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
backend) — copy the link from there.

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
| Module 3 (HRM) | `/hrm/` | `/hrm/` (overview), `/hrm/employees/`, `/hrm/employee-documents/`, `/hrm/lifecycle-events/`; **org** `/hrm/designations/`, `/hrm/job-grades/`, `/hrm/departments/`, `/hrm/cost-centers/`, `/hrm/org-chart/`, `/hrm/company-setup/`; **onboarding** `/hrm/onboarding-templates/`, `/hrm/onboarding-template-tasks/`, `/hrm/onboarding/`, `/hrm/onboarding-tasks/`, `/hrm/onboarding-documents/`, `/hrm/assets/`, `/hrm/orientation/`; **offboarding** `/hrm/separations/`, `/hrm/exit-interviews/`, `/hrm/clearance/`, `/hrm/settlements/`, `/hrm/letters/` (+ POST `…/{relieving,experience}-letter/`); **recruiting** `/hrm/requisitions/`, `/hrm/job-templates/`, `/hrm/candidates/`, `/hrm/candidate-tags/`, `/hrm/candidate-email-templates/`, `/hrm/candidate-communications/`, `/hrm/applications/`, `/hrm/interviews/`, `/hrm/interview-feedback/`, `/hrm/offers/`, `/hrm/background-checks/`, `/hrm/offer-letter-templates/` (+ public `/hrm/careers/`); **attendance** `/hrm/attendance/`, `/hrm/shifts/`, `/hrm/shift-assignments/`, `/hrm/geofences/`, `/hrm/regularizations/`; **leave** `/hrm/leave-types/`, `/hrm/leave-allocations/`, `/hrm/leave-requests/`, `/hrm/leave-encashments/`, `/hrm/leave-policy/`; **time tracking** `/hrm/timesheets/`, `/hrm/overtime-requests/`, `/hrm/reports/utilization/`, `/hrm/reports/project-time/`; **holidays** `/hrm/holidays/` |
| Module 4 (SCM) | `/scm/` | `/scm/` (overview); **procurement (4.1)** `/scm/requisitions/`, `/scm/rfqs/` (+ `…/<pk>/compare/`), `/scm/quotes/`, `/scm/orders/`, `/scm/receipts/` — each with the CRUD triple plus lifecycle actions (requisition submit/approve/reject; RFQ send/close + quote award; PO submit/approve/send/acknowledge/amend/cancel/close; receipt receive/cancel/rematch); **SRM (4.2)** `/scm/suppliers/`, `/scm/scorecards/`, `/scm/contracts/`, `/scm/catalogs/`, `/scm/risk-assessments/` — CRUD + lifecycle actions (supplier submit/approve/reject/reopen/suspend; scorecard recompute/publish; contract activate/renew/terminate; catalog activate; risk submit/review); **inventory (4.3)** `/scm/items/`, `/scm/categories/`, `/scm/uoms/`, `/scm/locations/`, `/scm/lot-serials/`, `/scm/transfers/` (+ `…/complete/`), `/scm/adjustments/` (+ `…/post/`), `/scm/reorder-rules/`; reports `/scm/valuation/`, `/scm/reorder-alerts/`, `/scm/stock-ledger/`, `/scm/on-hand/`; **warehouse (4.4)** `/scm/putaway/` (+ `…/complete/`), `/scm/picks/` (+ `…/confirm/`, `…/pack/`), `/scm/cycle-counts/` (+ `…/start/`, `…/reconcile/`), `/scm/yard/` (+ `…/arrive/`, `…/dock/`, `…/depart/`); **orders (4.5)** `/scm/sales-orders/` (+ `…/submit/`, `…/release-hold/`, `…/fulfill/`, `…/mark-invoiced/`, `…/cancel/`, `…/close/`, `…/from-quote/<pk>/`), `/scm/allocations/` (+ `…/release/`, `…/cancel/`); **transportation (4.6)** `/scm/carriers/` (+ `…/recompute-scorecard/`), `/scm/loads/` (+ `…/tender/`, `…/book/`, `…/dispatch/`, `…/deliver/`, `…/cancel/`), `/scm/shipments/` (+ `…/book/`, `…/add-event/`, `…/cancel/`), `/scm/freight-invoices/` (+ `…/run-audit/`, `…/dispute/`, `…/approve/`, `…/reject/`, `…/handoff/`) |
| Django admin | `/admin/` | `/admin/` |

Each CRUD resource follows the pattern: list (`/`), create (`/add/`), detail (`/<pk>/`), edit (`/<pk>/edit/`),
delete (`/<pk>/delete/`, POST).

---

## Stripe billing (test mode)

Billing is fully functional **without** Stripe — use the manual **Mark as paid** action on a subscription. To
enable hosted online checkout:

1. In your Stripe **test** dashboard, create recurring Prices for the paid plans and copy their `price_…` IDs.
2. Put the keys and Price IDs in `.env` (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
   `STRIPE_PRICE_STARTER/PRO/ENTERPRISE`).
3. Configure a webhook endpoint pointing at `…/tenants/stripe/webhook/` and put its signing secret in
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

- **8,895 tests** run under **`config.settings_test`** (SQLite in-memory) via `pytest.ini` — they **never** touch
  the MySQL dev database. Per-module suites: **core 118**, **accounts 95**, **tenants 108**, **CRM 2,114**,
  **Accounting 212**, **HRM 3,838**.
- Coverage spans: model invariants & `__str__`, form validation, full CRUD via the test client, **multi-tenant
  IDOR (cross-tenant → 404)**, auth flows (email-or-username, bad creds, POST-only logout), permission gating
  (member → 403), forgot-password non-enumeration, invite token/expiry, encryption-key secrecy, branding hex
  validation, the Stripe webhook signature rejection, **double-entry GL invariants + posting/void workflows**
  (Accounting), the **leave-request approval state machine + derived balances** (HRM), the recurring-invoice
  cadence/generation + cash-forecast projection, and the **offboarding lifecycle** (separation→clearance→F&F→letters
  state machine, derived `net_payable`/`all_mandatory_cleared`, the idempotent clearance-checklist + bounded-query
  leave-encashment services, and `@tenant_admin_required` gating on every workflow action).

---

## Project structure

```
NavERP/
├─ config/                  Django project
│  ├─ __init__.py           PyMySQL driver + MariaDB 10.4 shim
│  ├─ settings.py           apps, middleware, custom user, DB, sessions, Stripe, email
│  ├─ settings_test.py      SQLite in-memory (pytest)
│  ├─ urls.py               root URLconf
│  └─ wsgi.py / asgi.py
├─ apps/
│  ├─ core/                 Tenant spine, middleware, navigation, crud helpers, audit
│  │  ├─ models/ forms/ views/         PACKAGES — FLAT entity files (Module 0 has no sub-modules)
│  │  │  └─ Party.py Tenant.py …       models/forms/views line up 1:1; _base.py/_common.py hold the
│  │  │                                shared plumbing (TenantModelForm lives in forms/_common.py)
│  │  ├─ urls.py            kept flat — a crud(slug, name) factory generates the 5 routes per model
│  │  ├─ crud.py  middleware.py  decorators.py  navigation.py  search.py
│  │  ├─ context_processors.py  utils.py  admin.py
│  │  ├─ management/commands/seed_core.py
│  │  └─ tests/
│  ├─ accounts/             User/Role/Permission/UserInvite, auth, RBAC
│  │  ├─ models.py  managers.py  backends.py  forms.py  views.py  urls.py  admin.py
│  │  ├─ management/commands/seed_accounts.py
│  │  └─ tests/
│  ├─ tenants/              Module 0.1 — subscriptions/billing/branding/keys/health + Stripe
│  │  ├─ models/ forms/ views/         PACKAGES — FLAT entity files (Subscription.py, EncryptionKey.py …)
│  │  ├─ urls.py  stripe_utils.py  admin.py     (urls kept flat — small + explicit)
│  │  ├─ management/commands/seed_tenants.py
│  │  └─ tests/
│  ├─ dashboard/            KPI aggregation (no models)
│  ├─ crm/                  Module 1 — CRM (leads/opportunities/cases/… + 1.7–1.12)
│  │  ├─ models/ forms/ views/ urls/   PACKAGES — one folder per sub-module (1.1–1.12), one file per entity
│  │  │  └─ <SubModule>/<Entity>.py    e.g. SalesForceAutomation/Quotes.py  (each __init__ re-exports all)
│  │  ├─ analytics.py  admin.py        (single-purpose modules stay flat)
│  │  ├─ management/commands/seed_crm.py
│  │  └─ tests/
│  ├─ accounting/           Module 2 — GL ledger, AP/AR, cash, recurring invoicing + advanced 2.6–2.15
│  │  ├─ models/ forms/ views/ urls/   PACKAGES — one folder per sub-module (2.1–2.15), one file per entity
│  │  │  └─ <SubModule>/<Entity>.py    e.g. AccountsReceivable/Invoices.py  (the old *_advanced.py files folded in)
│  │  ├─ admin.py
│  │  ├─ management/commands/seed_accounting.py
│  │  └─ tests/
│  └─ hrm/                  Module 3 — employees, onboarding, offboarding, leave, attendance, holidays
│     ├─ models/ forms/ views/ urls/   PACKAGES — one folder per sub-module (3.1–3.41), one file per entity
│     │  └─ <SubModule>/<Entity>.py    e.g. LeaveManagement/Request.py; each <SubModule>/_helpers.py holds
│     │                                that sub-module's private helpers (entity → _helpers → _base)
│     ├─ services.py        request-free domain logic (task/clearance generation, leave encashment)
│     ├─ analytics.py  admin.py        (single-purpose modules stay flat)
│     ├─ management/commands/seed_hrm.py
│     └─ tests/
│  └─ scm/                  Module 4 — supply chain (4.1 procurement: PR → RFQ → PO → GRN + 3-way match)
│     ├─ models/ forms/ views/ urls/   PACKAGES — ProcurementManagement/<Entity>.py (one file per entity)
│     ├─ admin.py           (single-purpose modules stay flat)
│     ├─ management/commands/seed_scm.py
│     └─ tests/             668-test suite (models/forms/views/security)
├─ templates/
│  ├─ base.html  base_auth.html
│  ├─ partials/             sidebar, topbar, footer, messages, pagination, customizer
│  ├─ registration/         login, register, forgot/reset password, invite accept
│  ├─ core/ accounts/ tenants/ dashboard/   foundation CRUD pages (entity-folder layout, flat at app root)
│  └─ crm/ accounting/ hrm/                  domain CRUD pages, one folder per sub-module → per entity:
│                                            <app>/<submodule>/<entity>/<page>.html (page = list/detail/form)
├─ static/
│  ├─ css/theme.css         design system (component classes, dark mode, layout variants)
│  ├─ js/layout.js          layout customizer (persists to localStorage)
│  ├─ js/app.js             icons, nav, ⌘K search, toasts
│  └─ img/logo.svg
├─ conftest.py              shared pytest fixtures
├─ requirements.txt  pytest.ini  manage.py
├─ .env.example  .gitignore
├─ NavERP.md  NavERP-ERD.md   planning docs
└─ README.md
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

- **Layout:** vertical · horizontal · detached
- **Mode:** light · dark
- **Width:** fluid · boxed
- **Sidebar size:** default · compact · small-icon · icon-hovered
- **Sidebar color:** light · colored
- **Topbar:** light · dark
- **Topbar position:** fixed · scrollable
- **Direction:** LTR · RTL
- **Preloader:** on · off

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

> Note: the platform→tenant billing models (`Subscription`/`SubscriptionInvoice`) are deliberately distinct from
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
- [ ] Add **login rate-limiting / lockout** (e.g. `django-axes`) — intentionally not bundled in the foundation.
- [ ] Use a managed **MariaDB ≥ 10.5 / MySQL 8** in production (the 10.4 shim is for local XAMPP).
- [ ] Configure a real **SMTP** email backend.
- [ ] **Roadmap (Module 0.4):** MFA (TOTP/WebAuthn passkeys), SSO/SAML/OIDC, adaptive/risk-based auth, and
      subdomain-per-tenant routing.

---

## Module roadmap (0–13)

| # | Module | App slug | Status |
|---|--------|----------|--------|
| 0 | System Admin & Security | `core` + `accounts` + `tenants` + `dashboard` | ✅ Foundation built (0.1 complete) |
| 1 | Customer Relationship Management (CRM) | `crm` | ✅ 1.1–1.12 built (leads, **1.2 SFA recreated in detail: opportunities + splits + Kanban board, product catalog + price books + quote builder, territories + sales quotas + forecast dashboard**, **1.3 marketing automation recreated in detail: campaigns + members + email templates/campaigns + landing pages + public web-to-lead form submissions**, **1.4 customer service recreated in detail: cases (SLA policies/breach + conversation thread + CSAT) + knowledge base (categories/feedback) + customer self-service portal + public case-status/KB pages**, tasks, accounts/contacts; expenses, projects/milestones/timesheets, doc templates/contracts+e-sign, workflow rules/approvals, onboarding/health/surveys, stock/POs/partner portal) |
| 2 | Accounting & Finance | `accounting` | ✅ 2.1–2.15 built (dashboard + cash-forecast; GL: chart of accounts, journal entries, fiscal periods, currencies/FX; AP/AR: vendor/customer profiles, bills, invoices, recurring invoicing, payments + cash application, aging, payment schedule; Cash: bank accounts, CSV import, reconciliation; **advanced** — Fixed Assets + depreciation/disposal, Cost Allocation, Payroll journal, Project/Job Costing, Intercompany, Tax codes/returns, Balance Sheet/P&L/Scheduled reports, Budgeting + variance, Internal Controls, Integrations) |
| 3 | Human Resource Management (HRM) | `hrm` | 🟦 3.1–3.21 built — 21 of 41 sub-modules (**employee management** — full personnel-file profiles on `core.Party`/`core.Employment` with a document vault [verify/reject + expiry + confidential] and a dated lifecycle/job-history timeline; **organizational structure** — job grades + designations (salary bands/JD), department & cost-center companion profiles (head/owner/budget) on `core.OrgUnit`, a derived org chart + company-setup view; **employee onboarding** — reusable templates → per-hire programs with auto-generated tasks, document/e-sign tracking, asset issue/return, orientation scheduling; **employee offboarding** — separation cases driving resignation→approval→clearance→F&F→completion with auto-generated department clearance (asset-return on clear), exit interviews, full-&-final settlement with derived net payable, and relieving/experience letter print views; **job requisition** — a `JobRequisition` authorization-to-hire hub with budget/headcount/JD, a sequential `RequisitionApproval` chain (draft→pending→approved→posted→filled), reusable `JobDescriptionTemplate` copy-on-apply, and clone; **candidate management** — an ATS `CandidateProfile` (on `core.Party`) + talent-pool tags/skills, a `JobApplication` pipeline against requisitions with auto-firing recruiting email templates + an append-only communication log, and a public unauthenticated career portal; **interview process** — `Interview` scheduling (mode/status machine + reschedule) with an `InterviewPanelist` panel (role + RSVP) and structured `InterviewFeedback` scorecards (per-competency 1–5 ratings + hire recommendation), candidate invites/reminders reusing the recruiting email pipeline; **offer management** — an `Offer` (`OFR-`) over the `JobApplication` with a compensation breakdown + workflow status machine (draft→pending_approval→approved→extended→accepted/declined/rescinded/expired), an `OfferApproval` chain gating extension (auto-built Hiring-Manager→HR + Executive for high-value offers), offer acceptance driving the application to `hired` + raising a pre-boarding checklist, a `BackgroundVerification` (`BGV-`) status/result lifecycle with consent gate, `PreboardingItem` document collection, and a reusable `OfferLetterTemplate` (`OLTMPL-`) merge-rendering a printable letter; **attendance** with shifts + late detection, **geofencing** GPS zones + **regularization** approval workflow; **leave** types/allocations/requests with derived balances + approval, a **Leave Policy engine** (accrual/carry-forward runs) + **encashment** payout workflow; **time tracking** — weekly timesheets with inline entries + derived hours against `accounting.Project`, billable/utilization + project-time reports, overtime requests; public-holiday calendar; **salary structure** (pay-component catalog + grade CTC templates + effective-dated assignments), **payroll processing** (payslip computation + draft→approved→locked handing totals to `accounting.PayrollRun`), **statutory compliance** (PF/ESI/PT/TDS/LWF config + per-scheme returns register), **tax & investment** (old/new regime slabs + investment declarations/proofs + a Form-16 computation engine), **payout & reports** (disbursement batches from a locked cycle + masked-bank payments + UTR reconciliation + payslip distribution), **goal setting** (OKR periods/objectives/key-results/check-ins with cascade alignment + weighted progress/health), **performance review** (appraisal cycles with a 6-phase machine, self/manager/peer/upward reviews, derived + calibrated ratings, a calibration board, and subject/reviewer/admin-only confidentiality), **continuous feedback** (real-time kudos/appreciation/constructive feedback + a request-pull workflow + anonymous-giver masking, 1:1 meetings with shared/manager-private notes + action items, and a computed feedback dashboard), and **performance improvement** (Performance Improvement Plans with an HR-approval workflow + scheduled check-ins, progressive warning letters with an issue/acknowledge workflow + a printable letter, and manager-only coaching notes — the strictest confidentiality in the system: the coached employee never sees notes about themselves) [3.13–3.21]; idempotent `seed_hrm`). Next: 3.22 |
| 4 | Supply Chain Management (SCM) | `scm` | 🟦 4.1–4.6 built — 6 of 19 sub-modules. **4.6 transportation management (TMS)** — the carrier/freight layer 4.4/4.5 deferred to it (where `YardVisit.carrier_name`/`PickTask` free-text placeholders finally get a real master): a `Carrier` (`CAR-`) modeled as a spine-backed profile on `core.Party` (a required party FK, like 4.2's `SupplierProfile` — never a duplicate company table) with SCAC/MC/DOT identifiers, per-lane `CarrierRateCard`s, and an on-time-delivery scorecard *derived* from delivered-shipment history; a `Load` (`LD-`) consolidating shipments over a sequence of `LoadStop`s with a *derived* cube-utilization headline (assigned weight/volume ÷ equipment capacity, never stored); a `Shipment` (`SHP-`) linking the sales/purchase order it moves, whose status/ETA/POD are *projected* from an **append-only `TrackingEvent` log** (mirrors the StockMove ledger — a pickup event moves it in-transit, a delivered event closes it, a terminal shipment is never walked back); and a `FreightInvoice` (`FRT-`) that audits billed-vs-contract amounts per charge line into a match verdict (matched/price-variance/duplicate/disputed, mirroring the GRN three-way match) and, once approved, **drafts an `accounting.Bill` for the carrier's party and hands off** — TMS records the audit and never posts a journal entry itself (L29). **4.5 order management** — SCM ships the sales order first so it owns it (Modules 8/9 will extend it by FK): `SalesOrder` (`SO-`) captures manually or by converting an accepted CRM quote, validates on submit against the customer's real `accounting.CustomerProfile` credit limit plus a new-customer high-value rule, and `SalesOrderAllocation` reserves stock per fulfillment location. That allocation is deliberately a **soft** reservation that posts no `StockMove` — on-hand doesn't drop when stock is spoken for; availability-to-promise does, and stock physically leaves only via 4.4's pick. Ordering more than a location holds reserves what's there and backorders the rest. **4.4 warehouse management** — WMS layered on the 4.3 spine rather than beside it: bins ARE `Location`s (extended with capacity/pick-sequence/ABC class), `PutawayTask` (`PUT-`) directs received stock from receiving into its bin, `PickTask` (`PIK-`) does wave/batch/zone picking with honest short-pick handling and packing label data (carrier rendering waits for 4.6 TMS), `CycleCountTask` (`CC-`) snapshots expected quantities server-side and reconciles into exactly one existing `StockAdjustment`, and `YardVisit` (`YRD-`) tracks trucks through dock doors with derived dwell time. This pass also closed a real gap in shipped code: **booking a goods receipt now posts stock** (and cancelling reverses it with compensating moves), which previously left procure-to-pay disconnected from inventory. **4.3 inventory management** — SCM ships the **inventory spine** (`ItemCategory`/`UOM`/`Item`/`Location`/`LotSerial`/`StockMove`) that Module 5 will extend by FK: stock is an **append-only `StockMove` ledger** with signed quantities, so on-hand and valuation are always *derived* aggregates and never a stored field that can drift. On top of it, `StockTransfer` (`TRF-`) posts a paired out/in movement with a live insufficient-stock guard, `StockAdjustment` (`ADJ-`) posts reason-coded corrections (write-off/damage/cycle-count/found/revaluation), and `ReorderRule` drives low-stock alerts with a one-click hand-off into a 4.1 requisition. Reports compute FIFO/LIFO/weighted-average valuation over the ledger's cost layers, plus a stock ledger and on-hand-by-location. **4.2 supplier relationship management** — SRM on the `core.Party` supplier spine: a `SupplierProfile` (onboarding lifecycle + qualification questionnaire + a five-point due-diligence checklist gating approval); a `SupplierScorecard` (`SCR-`) whose delivery/quality/price/responsiveness scores are DERIVED from real 4.1 signals (on-time `GoodsReceiptNote`s, reject rate, `RFQQuote` price competitiveness and turnaround) with a weighted overall grade; a `SupplierContract` (`SC-`) with date-driven renewal alerts (expiring/expired) and renew/terminate; a `SupplierCatalog` (`CAT-`) of free-text priced items (pending `core.Item`); and a `SupplierRiskAssessment` (`SRA-`) scoring four risk factors into a derived level (a single critical factor floors it at High). Idempotent `seed_scm` extension; tests in the shared `apps/scm` suite. **4.1 procurement management** — the full procure-to-pay chain: a `PurchaseRequisition` (`PR-`) with multi-tier approval routing by amount and a view-time budget check against `accounting.Budget`; a multi-vendor `RFQ` (`RFQ-`) with a supplier invite list, competing `RFQQuote`s (`QT-`), and a side-by-side comparison matrix marking the cheapest supplier per line; the canonical `PurchaseOrder` (`PO-`) with a nine-state lifecycle, a version+reason amendment trail, staff-recorded vendor acknowledgement, and cancellation controls; and a `GoodsReceiptNote` (`GRN-`) that three-way-matches order↔receipt↔`accounting.Bill` on net-of-tax value with a 2% tolerance and over-receipt precedence. Reuses the `core.Party`/`PartyRole` supplier spine and `accounting.*` money masters; line items stay free-text pending `core.Item` (Module 5). Owns the procurement transaction tables that Module 6 will later extend by FK. Idempotent `seed_scm`; a 1,343-test `apps/scm` suite). Next: 4.7 |
| 5 | Inventory Management System (IMS) | `inventory` | Roadmap |
| 6 | Procurement Management System | `procurement` | Roadmap |
| 7 | Project Management | `projects` | Roadmap |
| 8 | Sales Management System | `sales` | Roadmap |
| 9 | eCommerce Management System | `ecommerce` | Roadmap |
| 10 | Business Intelligence (BI) | `bi` | Roadmap |
| 11 | Asset Management System | `assets` | Roadmap |
| 12 | Quality Management System (QMS) | `quality` | Roadmap |
| 13 | Document Management System (DMS) | `documents` | Roadmap |

Each new module is a Django app under `apps/<slug>` that **reuses** the unified core (Party, Item, ledgers,
anchors) and **adds** only its own domain tables — see the coverage map in [`NavERP-ERD.md`](NavERP-ERD.md).

---

## Development conventions

- **Multi-tenancy is mandatory**: every model has a `tenant` FK; every view filters by `request.tenant`.
- **CRUD completeness**: every list page ships with create, detail, edit, and POST-only delete.
- **Filters**: pass choices/querysets from the view; guard integer-FK filters; preserve filters across pagination.
- **Templates**: use the `theme.css` component classes; multi-line notes use `{% comment %}…{% endcomment %}`
  (a multi-line `{# #}` would render as visible text).
- **Template folder layout**: one folder per sub-module, then one folder per entity, with a bare
  `list/detail/form.html` page filename — `templates/<app>/<submodule>/<entity>/<page>.html` (foundation apps are
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
| `(1064) … RETURNING …` during migrate | The MariaDB 10.4 shim in `config/__init__.py` must be present (it is) and the venv must have PyMySQL installed. |
| `manage.py` can't import Django | Use the venv interpreter: `python …`. |
| Module pages are empty | You're logged in as the superuser `admin` (no tenant). Log in as `admin_acme` / `password`. |
| Login says "session timed out" repeatedly | Idle timeout is 30 min / absolute 12 h — just sign in again. |
| Changes don't appear in the browser | The dev server may be running with `--noreload`; restart it and hard-refresh (Ctrl+Shift+R). |
| `SECRET_KEY is not set` on startup | Set `SECRET_KEY` in `.env` (required when `DEBUG=False`). |

---

## License

See [LICENSE](LICENSE).

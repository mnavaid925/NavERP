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
**Module 2 — Accounting & Finance** (2.1–2.15), and **Module 3 — HRM** (employees, onboarding, offboarding, leave,
attendance, holidays — 7 of 41 sub-modules). The remaining functional modules (4–13) are planned and scaffolded
against the same core. The suite stands at **1,665 passing tests**.

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

**Sub-modules 1.7–1.12** (extension pass, 18 CRM-owned tables, migration `0005`):
- **1.7 Finance & Billing** — **Expenses** (`EXP-#####`): deal/project cost logging with receipt upload
  (extension-allowlisted), an owner **submit** + tenant-admin **approve/reject** workflow.
- **1.8 Project & Delivery** — **Projects** (`PRJ-#####`, one-click **convert** from a won opportunity),
  **Milestones** (`MS-#####`, Gantt/Kanban, sub-tasks), **Timesheets** (`TS-#####`, billable/non-billable).
- **1.9 Document & Contract** — **Doc Templates** (`TPL-#####`, merge-variable HTML) and **Contracts**
  (`CTR-#####`) with per-signer e-signature tracking and a **public token-based signing page**.
- **1.10 Automation & Workflow** — **Workflow Rules** (`WFR-#####`, declarative trigger/condition/action JSON),
  an append-only **Workflow Log**, and **Approval Requests** (`APR-#####`, admin approve/reject).
- **1.11 Customer Success** — **Onboarding Plans** (`CS-#####`, step checklists + progress), **Health Scores**
  (`HS-#####`, 0–100 derived from tickets/NPS/tasks/engagement with configurable weights), **Surveys**
  (`NPS-#####`, NPS/CSAT/CES with auto-classification + a public respond page).
- **1.12 Inventory & Vendor** — CRM-owned **Product Stock** (`STK-#####`, low-stock alerts), **Purchase Orders**
  (`PO-#####`) with line items + receive-to-stock, and **Partner Portal Access** (`PRT-#####`) with a
  partner-facing read-only portal (orders + stock).
  > 1.12 uses CRM-owned PurchaseOrder/ProductStock because the Inventory/Procurement spine masters
  > (`core.Item`/`StockMove`/`PurchaseOrder`) and the Accounting ledger aren't built yet; they migrate onto
  > the spine when those modules land.

Full CRUD, tenant isolation, working filters, an idempotent `seed_crm`, and a **1,488-test** suite.

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

### Module 3 — Human Resource Management (`hrm`) — 3.1/3.2/3.3/3.4/3.5/3.9/3.10/3.12

HRM passes so far — **employee directory + onboarding + offboarding + leave + attendance + holidays**, reusing the
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
  overdue indicator. Candidate/interview/offer linkage deferred to 3.6–3.8.
- **3.9 Attendance Management** — `AttendanceRecord` (`ATT-`, auto `hours_worked` incl. overnight, late-arrival
  badge, source/status), `Shift` (grace window) + `ShiftAssignment`.
- **3.10 Leave Management** — `LeaveType` (accrual/carry-forward/encashment policy), `LeaveAllocation` (`LA-`,
  **derived** used/balance from approved requests), `LeaveRequest` (`LR-`) with a draft→pending→approved/rejected/
  cancelled workflow (approve/reject are admin-only; days auto-computed minus non-optional holidays).
- **3.12 Holiday Management** — `PublicHoliday` calendar (optional/floating flag).

Full CRUD, tenant isolation, working filters, an idempotent `seed_hrm`, and an **844-test** HRM suite
(**1,906 project-wide**). Leave/approver, offboarding, and document-verification/lifecycle workflow & approval
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
| Module 1 (CRM) | `/crm/` | `/crm/` (overview), `/crm/leads/`, `/crm/opportunities/`, `/crm/opportunities/board/`, `/crm/territories/`, `/crm/products/`, `/crm/price-books/`, `/crm/quotes/`, `/crm/sales-quotas/`, `/crm/forecast/`, `/crm/campaigns/`, `/crm/campaign-members/`, `/crm/email-templates/`, `/crm/email-campaigns/`, `/crm/landing-pages/`, `/crm/form-submissions/`, `/crm/cases/`, `/crm/sla-policies/`, `/crm/knowledge/`, `/crm/kb-categories/`, `/crm/portal-access/`, `/crm/portal/cases/`, `/crm/tasks/`, `/crm/accounts/`, `/crm/contacts/`, `/crm/expenses/`, `/crm/projects/`, `/crm/milestones/`, `/crm/timesheets/`, `/crm/doc-templates/`, `/crm/contracts/`, `/crm/workflows/`, `/crm/approvals/`, `/crm/onboarding/`, `/crm/health-scores/`, `/crm/surveys/`, `/crm/stock/`, `/crm/purchase-orders/`, `/crm/partner-portal/`, `/crm/portal/` (partner-facing); public `/crm/p/<token>/` (web-to-lead), `/crm/cases/track/<token>/` (case status), `/crm/kb/<token>/` (KB article), `/crm/sign/<token>/`, `/crm/surveys/<token>/respond/` |
| Module 2 (Accounting) | `/accounting/` | `/accounting/` (dashboard), `/accounting/glaccounts/`, `/accounting/journal-entries/`, `/accounting/fiscal-periods/`, `/accounting/currencies/`, `/accounting/exchange-rates/`, `/accounting/vendor-profiles/`, `/accounting/bills/`, `/accounting/customer-profiles/`, `/accounting/invoices/`, `/accounting/recurring-invoices/`, `/accounting/payments/`, `/accounting/allocations/`, `/accounting/bank-accounts/`, `/accounting/bank-transactions/`, `/accounting/reconciliation/`, `/accounting/fixed-assets/`, `/accounting/asset-disposals/`, `/accounting/cost-allocations/`, `/accounting/payroll-runs/`, `/accounting/projects/`, `/accounting/intercompany/`, `/accounting/tax-codes/`, `/accounting/tax-returns/`, `/accounting/budgets/`, `/accounting/controls/`, `/accounting/integrations/`; reports `/accounting/reports/{trial-balance,cash-forecast,payment-schedule,ar-aging,ap-aging,balance-sheet,profit-and-loss,budget-variance}/` |
| Module 3 (HRM) | `/hrm/` | `/hrm/` (overview), `/hrm/employees/`, `/hrm/employee-documents/`, `/hrm/lifecycle-events/`, `/hrm/designations/`; **onboarding** `/hrm/onboarding-templates/`, `/hrm/onboarding-template-tasks/`, `/hrm/onboarding/`, `/hrm/onboarding-tasks/`, `/hrm/onboarding-documents/`, `/hrm/assets/`, `/hrm/orientation/`; **offboarding** `/hrm/separations/`, `/hrm/exit-interviews/`, `/hrm/clearance/`, `/hrm/settlements/`, `/hrm/letters/` (letters landing; + POST `…/separations/<pk>/{relieving,experience}-letter/`); **time** `/hrm/leave-types/`, `/hrm/leave-allocations/`, `/hrm/leave-requests/`, `/hrm/holidays/`, `/hrm/shifts/`, `/hrm/shift-assignments/`, `/hrm/attendance/` |
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

- **1,665 tests** run under **`config.settings_test`** (SQLite in-memory) via `pytest.ini` — they **never** touch
  the MySQL dev database. Per-module suites: **core 95**, **accounts 95**, **tenants 108**, **CRM 552**,
  **Accounting 212**, **HRM 603**.
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
│  │  ├─ models.py  crud.py  middleware.py  decorators.py  navigation.py
│  │  ├─ context_processors.py  utils.py  forms.py  views.py  urls.py  admin.py
│  │  ├─ management/commands/seed_core.py
│  │  └─ tests/
│  ├─ accounts/             User/Role/Permission/UserInvite, auth, RBAC
│  │  ├─ models.py  managers.py  backends.py  forms.py  views.py  urls.py  admin.py
│  │  ├─ management/commands/seed_accounts.py
│  │  └─ tests/
│  ├─ tenants/              Module 0.1 — subscriptions/billing/branding/keys/health + Stripe
│  │  ├─ models.py  stripe_utils.py  forms.py  views.py  urls.py  admin.py
│  │  ├─ management/commands/seed_tenants.py
│  │  └─ tests/
│  ├─ dashboard/            KPI aggregation (no models)
│  ├─ crm/                  Module 1 — CRM (leads/opportunities/cases/… + 1.7–1.12)
│  ├─ accounting/           Module 2 — GL ledger, AP/AR, cash, recurring invoicing + advanced 2.6–2.15
│  │  ├─ models.py  models_advanced.py  views.py  views_advanced.py  forms.py  urls.py  admin.py
│  │  ├─ management/commands/seed_accounting.py
│  │  └─ tests/
│  └─ hrm/                  Module 3 — employees, onboarding, offboarding, leave, attendance, holidays
│     ├─ models.py  forms.py  views.py  urls.py  admin.py
│     ├─ services.py        request-free domain logic (task/clearance generation, leave encashment)
│     ├─ management/commands/seed_hrm.py
│     └─ tests/
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
| 3 | Human Resource Management (HRM) | `hrm` | ✅ 3.1/3.2/3.3/3.4/3.5/3.9/3.10/3.12 built — 8 of 41 sub-modules (**employee management** — full personnel-file profiles on `core.Party`/`core.Employment` with a document vault [verify/reject + expiry + confidential] and a dated lifecycle/job-history timeline; **organizational structure** — job grades + designations (salary bands/JD), department & cost-center companion profiles (head/owner/budget) on `core.OrgUnit`, a derived org chart + company-setup view; **employee onboarding** — reusable templates → per-hire programs with auto-generated tasks, document/e-sign tracking, asset issue/return, orientation scheduling; **employee offboarding** — separation cases driving resignation→approval→clearance→F&F→completion with auto-generated department clearance (asset-return on clear), exit interviews, full-&-final settlement with derived net payable, and relieving/experience letter print views; **job requisition** — a `JobRequisition` authorization-to-hire hub with budget/headcount/JD, a sequential `RequisitionApproval` chain (draft→pending→approved→posted→filled), reusable `JobDescriptionTemplate` copy-on-apply, and clone; attendance with shifts + late detection; leave types/allocations/requests with derived balances + approval workflow; public-holiday calendar; idempotent `seed_hrm`). Next: 3.6 Candidate Management |
| 4 | Supply Chain Management (SCM) | `scm` | Roadmap |
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

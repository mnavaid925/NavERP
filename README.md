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

This repository currently delivers **Module 0 — System Admin & Security** (the cross-cutting foundation that
every other module depends on) and its first sub-module **0.1 Tenant & Subscription Management**. The remaining
functional modules (1–13) are planned and scaffolded against the same core.

- [`NavERP.md`](NavERP.md) — the master catalog of all modules (0–13) and their sub-modules.
- [`NavERP-ERD.md`](NavERP-ERD.md) — the unified core data model (the `Party` + two-ledger spine every module reuses).

---

## Why NavERP is one ERP, not fourteen apps

Three design ideas hold the whole platform together:

1. **The Party model.** `Party` + `PartyRole` mean there is **one record per real-world person or organization**.
   *Customer, vendor, supplier, employee, lead, contact, partner* are **roles** on a party, not separate tables.
   This collapses the customer/vendor/employee duplication that otherwise spreads across CRM, Accounting, HR,
   Procurement, and Sales.

2. **Two universal ledgers (roadmap).** Every inventory effect will post to `StockMove` and every financial
   effect to `JournalEntry`/`JournalLine` (append-only). On-hand quantities and account balances are **derived**
   by aggregation, never stored as editable fields — that consistency is what makes it an ERP. (These ledgers
   arrive with the inventory/accounting modules; the foundation establishes the pattern.)

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

### `crm` — Module 1: Customer Relationship Management (1.1–1.6)
- **Leads** (`LEAD-#####`) with rating (hot/warm/cold), qualification status, scoring, and one-click
  **conversion** to a `core.Party` account + contact + an Opportunity (atomic).
- **Opportunities** (`OPP-#####`) — pipeline stages, amount/probability, weighted-forecast value, FK to the
  account/contact `Party`, source lead, and campaign.
- **Campaigns** (`CAM-#####`) — type, status, planned/actual budget, expected/actual revenue, and ROI.
- **Cases** (`CASE-#####`) — support tickets with priority, status workflow, SLA `due_at` + overdue flagging,
  and system-set `resolved_at`. **Knowledge Base** (`KB-#####`) articles with internal/external visibility and a
  view counter.
- **Tasks** (`TASK-#####`) — to-dos/calls/follow-ups with priority, due date, and system-set `completed_at`.
- **Accounts & Contacts** are the shared **`core.Party`** identity (one record, many roles) enriched with CRM-owned
  one-to-one **`AccountProfile`** (industry, website, revenue, employees, parent company, address) and
  **`ContactProfile`** (job title, department, phone/mobile, employer account, address) extensions — **full CRUD**
  in CRM, no duplicate customer/contact tables. Deleting an account/contact removes the shared Party and is
  **tenant-admin-only** (cross-module impact).
- A CRM **overview** (analytics) page: stat cards (open leads, pipeline, weighted forecast, win rate, open
  cases/tasks, active campaigns) + pipeline-by-stage and leads-by-rating charts. Full CRUD, tenant isolation,
  filters, an idempotent `seed_crm`, and a 242-test suite.

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
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Create your local environment file, then edit it
Copy-Item .env.example .env
#    Open .env and set SECRET_KEY (any long random string for dev) and DB_* if yours differ.

# 3. Create the database (utf8mb4)
& "C:\xampp\mysql\bin\mysql.exe" -u root -h 127.0.0.1 -P 3306 `
  -e "CREATE DATABASE IF NOT EXISTS nav_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Apply migrations
venv\Scripts\python.exe manage.py migrate

# 5. Seed demo data (idempotent — safe to re-run). Order matters:
venv\Scripts\python.exe manage.py seed_core
venv\Scripts\python.exe manage.py seed_accounts
venv\Scripts\python.exe manage.py seed_tenants
venv\Scripts\python.exe manage.py seed_crm

# 6. Start the development server
venv\Scripts\python.exe manage.py runserver
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
employments, activities, subscriptions, invoices, branding, encryption keys, and health metrics.

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
venv\Scripts\python.exe manage.py runserver          # http://127.0.0.1:8000/
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000   # accessible on your LAN
```

Useful management commands:

```powershell
venv\Scripts\python.exe manage.py check              # system checks
venv\Scripts\python.exe manage.py createsuperuser    # another Django superuser
venv\Scripts\python.exe manage.py makemigrations
venv\Scripts\python.exe manage.py migrate
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
| Module 1 (CRM) | `/crm/` | `/crm/` (overview), `/crm/leads/`, `/crm/opportunities/`, `/crm/campaigns/`, `/crm/cases/`, `/crm/knowledge/`, `/crm/tasks/`, `/crm/accounts/`, `/crm/contacts/` |
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
venv\Scripts\python.exe -m pytest                 # full suite
venv\Scripts\python.exe -m pytest apps/tenants    # one app
venv\Scripts\python.exe -m pytest -k webhook -v   # by keyword
```

- ~300 tests run under **`config.settings_test`** (SQLite in-memory) via `pytest.ini` — they **never** touch the
  MySQL dev database.
- Coverage spans: model invariants & `__str__`, form validation, full CRUD via the test client, **multi-tenant
  IDOR (cross-tenant → 404)**, auth flows (email-or-username, bad creds, POST-only logout), permission gating
  (member → 403), forgot-password non-enumeration, invite token/expiry, encryption-key secrecy, branding hex
  validation, and the Stripe webhook signature rejection.

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
│  └─ dashboard/            KPI aggregation (no models)
├─ templates/
│  ├─ base.html  base_auth.html
│  ├─ partials/             sidebar, topbar, footer, messages, pagination, customizer
│  ├─ registration/         login, register, forgot/reset password, invite accept
│  ├─ core/ accounts/ tenants/ dashboard/   per-model CRUD pages
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
| 1 | Customer Relationship Management (CRM) | `crm` | ✅ 1.1–1.6 built (leads, opportunities, campaigns, cases, KB, tasks) |
| 2 | Accounting & Finance | `accounting` | Roadmap |
| 3 | Human Resource Management (HRM) | `hrm` | Roadmap |
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
- **Seeders** are idempotent and print the demo logins.
- **Migrations** are committed alongside model changes.
- **Commits**: one file per commit with a descriptive message; work lands on `main` and is pushed manually.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Unknown database 'nav_erp'` | Run setup step 3 (create the database). Ensure XAMPP MySQL is started. |
| `(1064) … RETURNING …` during migrate | The MariaDB 10.4 shim in `config/__init__.py` must be present (it is) and the venv must have PyMySQL installed. |
| `manage.py` can't import Django | Use the venv interpreter: `venv\Scripts\python.exe …`. |
| Module pages are empty | You're logged in as the superuser `admin` (no tenant). Log in as `admin_acme` / `password`. |
| Login says "session timed out" repeatedly | Idle timeout is 30 min / absolute 12 h — just sign in again. |
| Changes don't appear in the browser | The dev server may be running with `--noreload`; restart it and hard-refresh (Ctrl+Shift+R). |
| `SECRET_KEY is not set` on startup | Set `SECRET_KEY` in `.env` (required when `DEBUG=False`). |

---

## License

See [LICENSE](LICENSE).

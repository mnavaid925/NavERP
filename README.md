# NavERP

A multi-tenant **Enterprise Resource Planning (ERP)** platform — Django 5.1 + Tailwind (Play CDN) +
HTMX + Chart.js + Lucide, on MySQL/MariaDB (XAMPP). Clean, responsive, blue-and-white dashboard with
light/dark modes and multiple layout variants.

This repository currently implements **Module 0 — System Admin & Security** (the cross-cutting
foundation every later module builds on) and its first sub-module **0.1 Tenant & Subscription
Management**. Modules 1–13 (CRM, Accounting, HRM, SCM, Inventory, Procurement, Projects, Sales,
eCommerce, BI, Assets, Quality, DMS) are on the roadmap — see [`NavERP.md`](NavERP.md) for the full
catalog and [`NavERP-ERD.md`](NavERP-ERD.md) for the unified core data model.

## What's built

- **Multi-tenant foundation** — every record is scoped to a `Tenant`; `request.tenant` is resolved from
  the logged-in user. Shared-DB isolation enforced on every query (cross-tenant access → 404).
- **`core`** — the shared spine: `Tenant`, `Party`/`PartyRole` (one record, many roles), `OrgUnit`,
  `Address`, `ContactMethod`, `PartyRelationship`, `Employment`, `Activity`, `AuditLog`, `Document`,
  plus `TenantMiddleware`, the `MODULE_CATALOG` sidebar, reusable tenant-safe CRUD helpers, and audit logging.
- **`accounts`** — custom `User` (email-or-username login), RBAC `Role`/`Permission`, `UserInvite`;
  login, self-service tenant registration, forgot/reset password (console email in dev), user management,
  invites, and profile. Module-0 admin actions are gated by `@tenant_admin_required`.
- **`tenants` (Module 0.1)** — `Subscription`, `SubscriptionInvoice` (auto-numbered `SINV-#####`),
  `BrandingSetting` (white-label colors/logo), `EncryptionKey` (reveal-once secret; only prefix + SHA-256
  stored), `HealthMetric`, an onboarding wizard, and **Stripe** test-mode billing (Checkout + a
  signature-verified webhook) with a manual "mark as paid" fallback when Stripe isn't configured.
- **`dashboard`** — tenant-scoped KPI overview (stat cards, Chart.js, subscription/health/audit widgets).
- **Design system** — `static/css/theme.css` component classes + layout customizer (vertical/horizontal/
  detached, light/dark, fluid/boxed, sidebar sizes, light/colored sidebar, light/dark topbar,
  fixed/scrollable, LTR/RTL, preloader), persisted to `localStorage`.

## Requirements

- Python 3.10+
- XAMPP with MySQL/MariaDB running (developed against **MariaDB 10.4**)
- A database named **`nav_erp`**

> **MariaDB 10.4 note:** Django 5.1 targets MariaDB ≥ 10.5. `config/__init__.py` contains a compatibility
> shim (PyMySQL driver + lowered version floor + disabled `INSERT … RETURNING`) so migrations run on 10.4.

## Setup

```powershell
# 1. Create & activate a virtualenv, install deps
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
#   then edit .env — set SECRET_KEY and your DB credentials (DB_NAME=nav_erp)

# 3. Create the database (XAMPP MySQL)
& "C:\xampp\mysql\bin\mysql.exe" -u root -e "CREATE DATABASE IF NOT EXISTS nav_erp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Migrate + seed demo data
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py seed_core
venv\Scripts\python.exe manage.py seed_accounts
venv\Scripts\python.exe manage.py seed_tenants

# 5. Run
venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in.

### Demo logins (after seeding)

| Role | Username | Password | Notes |
|------|----------|----------|-------|
| Tenant admin | `admin_acme` | `password` | Full Module-0 access for tenant **Acme** |
| Tenant admin | `admin_globex` | `password` | Tenant **Globex** |
| Member | `sales_acme` / `ops_acme` | `password` | Non-admin (read + profile) |
| Superuser | `admin` | `admin` | Django admin only — **`tenant=None`, so module pages show no data by design** |

> Always log in as a **tenant admin** to see module data. The superuser has no tenant.

## Stripe (optional, test mode)

Billing works without Stripe (manual "mark as paid"). To enable online checkout, set the test-mode keys
and recurring Price IDs in `.env` (`STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_STARTER/PRO/ENTERPRISE`). Point a Stripe webhook at `/tenants/stripe/webhook/`
(events: `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`,
`customer.subscription.updated|deleted`). The endpoint rejects any unsigned/invalid payload (400).

## Testing

```powershell
venv\Scripts\python.exe -m pytest
```

The suite (≈300 tests) runs under `config.settings_test` (SQLite in-memory) — it never touches the dev
database. Coverage spans model invariants, form validation, CRUD integration, multi-tenant IDOR,
auth/permission gating, and the Stripe webhook.

## Project structure

```
config/            Django project (settings, urls, MariaDB shim in __init__.py)
apps/core/         Tenant spine, middleware, navigation, CRUD helpers, audit
apps/accounts/     User/Role/Permission/UserInvite, auth, RBAC
apps/tenants/      Module 0.1 — subscription/billing/branding/keys/health + Stripe
apps/dashboard/    KPI aggregation
templates/         base + partials + per-app CRUD pages
static/            theme.css, layout.js, app.js
```

## Security & production hardening

Implemented: tenant isolation on every query, `@tenant_admin_required` on admin writes, CSRF on all POSTs
(only the signature-verified Stripe webhook is exempt), password hashing + validators, secrets excluded
from forms (encryption-key secret revealed once; only prefix+SHA-256 stored), hex-validated branding colors,
safe-`next` login redirect, POST-only logout, upload extension/size limits, session idle (30 min) + absolute
(12 h) timeouts, and secure-cookie/HSTS/X-Frame-Options when `DEBUG=False`.

**Before production:**
- Set a strong `SECRET_KEY` and `DEBUG=False` (the app refuses to start in production without a real key).
- Move `MEDIA_ROOT` outside the web root (`htdocs`) so uploaded files can't be executed by Apache.
- Add login rate-limiting / lockout (e.g. **django-axes**) — intentionally not bundled in the foundation.
- **Roadmap (Module 0.4):** MFA (TOTP/WebAuthn), SSO/SAML/OIDC, and subdomain-per-tenant routing.

## License

See [LICENSE](LICENSE).

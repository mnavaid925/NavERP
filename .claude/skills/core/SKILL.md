---
name: core
description: Work on Module 0 (System Admin & Security) — the foundation, realized across FOUR apps (`core`, `accounts`, `tenants`, `dashboard`). Covers the unified spine (Party/PartyRole/Address/ContactMethod/PartyRelationship/Employment/OrgUnit/Activity/Document/AuditLog) and the platform layer built by 0.1–0.15: tenant & subscription, IAM, RBAC, SSO/MFA, user & organization, module access scope, data security & encryption, privacy & data protection, audit trail, system configuration & settings, workflow & approval administration, notification & communication, integration & API management, master data, and localization & regional settings. Use when the user asks to add/change/debug anything under apps/core, apps/accounts, apps/tenants or apps/dashboard, extend seed_core/seed_accounts/seed_tenants, touch Module 0 sidebar wiring (LIVE_LINKS 0.1–0.21), or invokes /core.
---

# Module 0 — System Admin & Security (the foundation)

Module 0 is **not one app**. It is realized across four foundation apps, and this skill covers all four:

| app | path | templates | what it owns |
|---|---|---|---|
| `core` | `apps/core/` | `templates/core/` | Tenant, the unified spine, AuditLog, navigation, crud/decorators/utils, and the platform layer 0.6/0.8/0.10–0.15 |
| `accounts` | `apps/accounts/` | `templates/accounts/` | `User`, `Role`, `Permission`, `UserInvite`, auth, MFA/sessions/password policy (0.2, 0.4) |
| `tenants` | `apps/tenants/` | `templates/tenants/` | Subscription, billing, invoices, branding, encryption keys, health metrics (0.1, 0.7) |
| `dashboard` | `apps/dashboard/` | `templates/dashboard/` | the root landing page — a tenant-scoped KPI aggregation with **no models of its own** |

`core` is the **canonical reference implementation** for a tenant-scoped CRUD module; `apps/tenants` is the
reference for a foundation app with flat entity files. Read them before inventing a shape.

## As-built

**15 of 21 sub-modules are live** (`LIVE_LINKS` in `apps/core/navigation.py` is the source of truth):

`0.1` Tenant & Subscription · `0.2` Identity & Access Management · `0.3` RBAC & Permissions ·
`0.4` Authentication & SSO · `0.5` User & Organization · `0.6` Module Administration & Access Scope ·
`0.7` Data Security & Encryption · `0.8` Privacy & Data Protection · `0.9` Audit Trail & Activity Logging ·
`0.10` System Configuration & Settings · `0.11` Workflow & Approval Administration ·
`0.12` Notification & Communication · `0.13` Integration & API Management · `0.14` Master Data &
Reference Configuration · `0.15` Localization & Regional Settings.

**Unbuilt: `0.16`–`0.21`** (Backup/Recovery, Monitoring/Observability, Threat Protection, License
Administration, Admin Console, Compliance & Governance). They render as roadmap pills.

Migrations: `core.0005`–`core.0012`, `accounts.0003`–`accounts.0004`, `tenants.0004`.

## App layout — FOUNDATION apps keep entity files FLAT

This is the one structural rule that differs from the domain modules. `crm`/`accounting`/`hrm`/`scm` use
`models/<SubModule>/<Entity>.py`; **`core` and `tenants` do not**:

```
apps/core/
  models/  __init__.py (re-exports EVERY model)  _base.py  Party.py  PartyRole.py  Setting.py  Localization.py …
  forms/   __init__.py  _common.py (TenantModelForm)  Party.py  Settings.py  Localization.py …
  views/   __init__.py  _common.py  Party.py  Settings.py  Localization.py …
  urls.py  <- a FLAT file, not a package
  navigation.py  <- parse_catalog() + MODULE_ICONS + LIVE_LINKS
  crud.py  utils.py  decorators.py  scoping.py  privacy.py  settings_engine.py
  workflow.py  notify.py  integration.py
```

**One file per SUB-MODULE, not per entity** — `Localization.py` holds all five 0.15 models;
`Privacy.py` holds all five 0.8 models. `tenants/` and `accounts/` follow the same flat rule
(`accounts/models.py` is a single file).

`dashboard` is deliberately minimal: `apps.py`, `urls.py`, `views.py`, `migrations/__init__.py` — **no
models**. It is the root landing page and aggregates six tables owned by `core` and `tenants`.

**Rules when working here:**
- Add the symbol to the entity file, **then add it to that package's `__init__.py` re-export block.** A
  missing re-export is an `ImportError` at URLconf import time.
- Imports inside the packages are **absolute** (`from apps.core.models import X`).
- Never create a `<SubModule>/` folder under a foundation app's `models/`.
- Never add `models_advanced.py` or any sidecar.

## The unified spine (`core`)

Customers, vendors, suppliers, employees, leads and contacts are **`PartyRole`s on `Party`** — never a
standalone customer/vendor/employee table. Also `Address`, `ContactMethod`, `PartyRelationship`,
`Employment`, `OrgUnit`, `Activity`, `Document` (a `GenericForeignKey` attachment), `AuditLog`.

**`apps/accounting` owns the financial ledger** (`Currency`, `GLAccount`, `TaxCode`, `ExchangeRate`,
`FiscalPeriod`, `JournalEntry`/`JournalLine`, `Invoice`, `Bill`, `Payment`). Other apps FK into it **by
string**. Balances are **derived**, never stored editable. **Module 0 does not re-declare any of it** —
0.15 points at `Currency`/`ExchangeRate`/`TaxCode` rather than growing a second copy (L36).

## The Module 0 recurring shape

Every platform sub-module resolves to the same three-part shape, and it is almost never a second engine:

1. **A registry** for what the platform can express (a definition table).
2. **A per-tenant profile/override** pointing at it (often a `OneToOneField` singleton).
3. **A COMPUTED board** that reads the *real* tables of other apps and stores nothing.

Examples: 0.13's `ConnectorDefinition` + `SyncSchedule` + `integration_health()`; 0.15's `Language`/
`TimeZone` registries + `LocaleProfile` + `localization_board`. When you are tempted to build an engine,
first check whether 71 approval models, per-module webhooks or `core.SettingDefinition` already exist.

## Multi-tenancy (mandatory)

Every model carries `tenant = models.ForeignKey('core.Tenant', …)` and every view filters
`Model.objects.filter(tenant=request.tenant)` — never `.all()`. `request.tenant` is set by
`apps.core.middleware.TenantMiddleware` from the logged-in user.

**Two deliberate exceptions, both documented in their model docstrings:**
- **Global masters with no `tenant` FK** — `accounting.Currency` (ISO 4217), `core.Language`,
  `core.TimeZone`. A currency, a language and an IANA zone are facts about the world, not a workspace.
  Their views are `@login_required` read-only lists with **no CRUD routes** (a write would need a
  platform-admin gate this repo does not have).
- The superuser `admin` has `tenant=None` **by design** and correctly sees no module data.

`crud_list`-based views deliberately **do not** guard `tenant is None` — an empty register *is* the correct
rendering for the superuser, and all 487 call sites behave this way. Only views that would otherwise
compute nonsense (the boards, the singletons) take the `messages.info` + redirect branch.

## Conventions & gotchas that have actually bitten here

- **Decorator order decides 405 vs 403.** Decorators apply bottom-up, so the OUTERMOST runs first. Put
  `@require_POST` **above** `@tenant_admin_required` so a wrong method is 405 regardless of role (7.7's
  ruling). `@login_required` above `require_POST` is fine.
- **`apps/core/views/_common.py` star-exports only** `get_user_model, login_required, JsonResponse,
  get_object_or_404, render, require_POST, crud_*, run_search, tenant_admin_required, Party, User`.
  It does **not** export `messages`, `redirect`, `timezone`, `Q`, `F`, `Count` or `Max` — import them
  explicitly or you get a `NameError` on a path a smoke test may not hit.
- **A `unique_together` that includes `tenant` is NOT validated by a `ModelForm`,** because `tenant` is
  never a `Meta.fields` member: `Model._get_unique_checks()` drops any `unique_together` containing an
  excluded field. The form validates, `crud_create` saves, and MySQL returns an `IntegrityError` **500**.
  Guard it in the form (`clean_<field>`, scoped to `self.tenant`, excluding `self.instance.pk`) — the shape
  is in `apps/crm/forms/CustomerSuccess/HealthScores.py` and `apps/core/forms/Localization.py`.
- **Give each entity its OWN seeder guard.** A tenant-wide guard silently strands every entity added
  later — that is exactly what happened to 0.6's module scopes.
- **`.alert` / `.alert-info` / `.alert-danger` do NOT exist in `static/css/theme.css`.** The inline-notice
  pattern is `<p class="text-muted">` (variants `.text-warn`, `.text-ok`, `.text-danger`, `.text-brand`).
  Badge palettes are colour-named only: `badge-green/red/amber/info/muted/slate`.
- **`AuditLog.action` is `varchar(10)`** and `.create()` never validates `choices` — a longer action
  truncates silently (or raises `DataError` under `STRICT_TRANS_TABLES`). Put the verb in `changes`.
- **A derived property calling `.filter()` bypasses the prefetch cache** (only `.all()` reads it). Compute
  in the view off the prefetched list and pass it as context.
- **Probe the EMPTY state and the tenant-less superuser.** A context key derived from a tenant-scoped
  variable 500s with no tenant. Always test no-param and junk-param requests.
- **Never interpolate user text into a single-quoted JS literal in `onsubmit`** — use `|escapejs` (L42).
- **No delete path erases bytes.** Django never unlinks a `FileField` on row delete, so "delete" is a UI
  claim unless something explicitly unlinks.

## Sidebar wiring

`apps/core/navigation.py` holds `parse_catalog()` (builds the 0–23 catalog from `NavERP.md`),
`MODULE_ICONS`, and **`LIVE_LINKS`** — the authoritative "is `N.M` built" map. A sub-module is Live iff it
has a `LIVE_LINKS["N.M"]` entry. Keys must be the **exact** `NavERP.md` bullet strings: `resolve_nav`
silently drops an unmatched key and silently appends an unknown one, so a typo produces a missing link
with no error.

## Common tasks

- **Add a sub-module:** build the entity file(s) → re-export in each package `__init__.py` → urls in the
  flat `apps/core/urls.py` (literals before `<int:pk>`) → templates at `templates/core/<entity>/<page>.html`
  → admin → extend `seed_core.py` → one `LIVE_LINKS["N.M"]` entry → `makemigrations core` → `migrate` →
  `seed_core` ×2 → `manage.py check`.
- **Verify a sub-module:** `venv\Scripts\python.exe temp\audit_integrity.py` — six checks, all must pass.
  It catches the four failure modes `manage.py check` cannot see (unapplied migration, unreversible route,
  missing template, broken sidebar target).
- **Run the tests:** `venv\Scripts\python.exe -m pytest apps/core/tests --nomigrations` (~84–186× faster
  than applying migrations). `--nomigrations` cannot catch an unapplied-migration defect — keep one run
  **without** it as the phase gate.
- **Module 0 is not covered by `/next-module`.** That skill's own SKILL.md says to edit the foundation
  directly; a bare run auto-detects module 7. Build Module 0 sub-modules explicitly.

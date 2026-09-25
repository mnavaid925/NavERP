---
name: core
description: Work on Module 0 (System Admin & Security) — the foundation, realized across FOUR apps (`core`, `accounts`, `tenants`, `dashboard`). Covers the unified spine (Party/PartyRole/Address/ContactMethod/PartyRelationship/Employment/OrgUnit/Activity/Document/AuditLog) and the platform layer built by 0.1–0.16: tenant & subscription, IAM, RBAC, SSO/MFA, user & organization, module access scope, data security & encryption, privacy & data protection, audit trail, system configuration & settings, workflow & approval administration, notification & communication, integration & API management, master data, localization & regional settings, and backup, recovery & data lifecycle. Use when the user asks to add/change/debug anything under apps/core, apps/accounts, apps/tenants or apps/dashboard, extend seed_core/seed_accounts/seed_tenants, touch Module 0 sidebar wiring (LIVE_LINKS 0.1–0.21), or invokes /core.
---

# Module 0 — System Admin & Security (the foundation)

Module 0 is **not one app**. It is realized across four foundation apps, and this skill covers all four:

| app | path | templates | what it owns |
|---|---|---|---|
| `core` | `apps/core/` | `templates/core/` | Tenant, the unified spine, AuditLog, navigation, crud/decorators/utils, and the platform layer 0.6/0.8/0.10–0.16 |
| `accounts` | `apps/accounts/` | `templates/accounts/` | `User`, `Role`, `Permission`, `UserInvite`, auth, MFA/sessions/password policy (0.2, 0.4) |
| `tenants` | `apps/tenants/` | `templates/tenants/` | Subscription, billing, invoices, branding, encryption keys, health metrics (0.1, 0.7) |
| `dashboard` | `apps/dashboard/` | `templates/dashboard/` | the root landing page — a tenant-scoped KPI aggregation with **no models of its own** |

`core` is the **canonical reference implementation** for a tenant-scoped CRUD module; `apps/tenants` is the
reference for a foundation app with flat entity files. Read them before inventing a shape.

## As-built

**16 of 21 sub-modules are live** (`LIVE_LINKS` in `apps/core/navigation.py` is the source of truth):

`0.1` Tenant & Subscription · `0.2` Identity & Access Management · `0.3` RBAC & Permissions ·
`0.4` Authentication & SSO · `0.5` User & Organization · `0.6` Module Administration & Access Scope ·
`0.7` Data Security & Encryption · `0.8` Privacy & Data Protection · `0.9` Audit Trail & Activity Logging ·
`0.10` System Configuration & Settings · `0.11` Workflow & Approval Administration ·
`0.12` Notification & Communication · `0.13` Integration & API Management · `0.14` Master Data &
Reference Configuration · `0.15` Localization & Regional Settings ·
`0.16` Backup, Recovery & Data Lifecycle.

**Unbuilt: `0.17`–`0.21`** (Monitoring/Observability, Threat Protection, License Administration,
Admin Console, Compliance & Governance). They render as roadmap pills.

Migrations: `core.0005`–`core.0014`, `accounts.0003`–`accounts.0004`, `tenants.0004`.

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
`Privacy.py` holds all five 0.8 models; `Backup.py` holds six of 0.16's seven (the seventh,
`LegalHold.py`, is separate because a hold is a peer of a retention policy, not a backup record). `tenants/` and `accounts/` follow the same flat rule
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
`TimeZone` registries + `LocaleProfile` + `localization_board`; 0.16's `RecoveryPosture` singleton +
the `backup_overview` / `backup_board` pair, which **store no figure at all**. When you are tempted to
build an engine, first check whether 71 approval models, per-module webhooks or
`core.SettingDefinition` already exist.

## 0.16 — Backup, Recovery & Data Lifecycle

The sub-module is a **register, not an engine**. NavERP has no scheduler, no object-storage client and
no ability to dump or restore its own database, so nothing here performs the act it describes: every row
records an act performed **out of band**, and the success messages say "recorded", never "completed".
State that plainly on any page you touch, because a backup register that reads like a backup tool is the
dishonesty this sub-module exists to avoid.

**Routes** — 34, all `core:`-namespaced (`0.16` accounts for 34 of the module's 240 route names):
`backup_overview` · `backup_board` · `recovery_posture_edit`, plus a five-route `crud()` set for each of
`backup_job`, `restore_record`, `data_archive`, `legal_hold`, `environment_instance`, `recovery_drill`.
`backup_job_verify` is an extra **POST-only** verb. Seven verbs are POST-only and all carry
`@require_POST` **above** `@tenant_admin_required`, so a wrong method is **405 regardless of role**.

**Templates** — `templates/core/` at the flat root: `backupoverview.html`, `backupboard.html`,
`retentionboard.html` (0.8's, which 0.16 taught about holds), `recoveryposture/form.html`, and
`<entity>/{list,detail,form}.html` for the six CRUD entities.

**Models** — `models/Backup.py` holds six (`BackupJob`, `DataArchive`, `RestoreRecord`,
`EnvironmentInstance`, `RecoveryPosture`, `RecoveryDrill`); `models/LegalHold.py` holds the seventh. All
seven inherit **`TenantConsistentMixin`**, which refuses a tenant-scoped FK pointing into another
workspace — the rule that makes the contract's "the seeder *and the admin* get it too" true, since the
admin uses a plain `ModelForm` with no queryset narrowing at all.

**Seeder** — `seed_core._seed_backup(tenant)`. Every entity has its **own** guard (never a tenant-wide
one), and the rows are chosen to exercise the states a naive seed omits: a `warning`/partial job, an
unverified `success` job, a `failed` job, a **`queued` job with `started_at=None`** (M11 — its absence is
exactly why the C5 ordering defect survived a green sweep), and an unrestorable archive
(`location=""`, `status="lost"`). Fresh-seed figures: 4 jobs / 2 archives / 1 hold / 2 environments /
2 drills / 1 posture / 1 restore.

**Tests** — `apps/core/tests/test_backup_{models,forms,views,security}.py` (**266 tests**), fixtures
appended to `apps/core/tests/conftest.py` under `bkp_*`, contract at
`.claude/tasks/test-contract-core-0.16.md`. **The test DB is SQLite** (`config.settings_test`), not
MariaDB — see contract §0 before asserting anything engine-specific.

**Sidebar** — one `LIVE_LINKS["0.16"]` entry whose bullet 4 points at the **archive catalogue**; the
landing page is `backup_overview`.

**As-built, and the two things a reader will otherwise re-litigate:**

- **C7 is ESCALATED, not fixed.** `TenantModelForm` deliberately leaves a queryset unnarrowed when
  `tenant=None`, so that `_reject_foreign` can return its precise "belongs to another workspace"
  message. Emptying it was tried and **reverted** — it broke 15 committed tests across `inventory`,
  `procurement` and `projects`. Measured latent exposure: 859 tenant-scoped fields across 618 forms.
  **Do not re-try it without the owner's decision.** A form reachable *without* a tenant must narrow
  explicitly.
- **`L5-M1` (verify idempotency) was never carried into the consolidated Minor list** and is therefore
  unfixed: a second POST to `backup_job_verify` re-dates the stamp. No test enforces either behaviour.

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

---
name: next-module
description: Build the next NavERP SUB-module end-to-end — ONE sub-module ("N.M") per run, NOT a whole module. Extend the module's Django app under apps/<slug> with that sub-module's tenant-scoped models, full CRUD views/forms/urls/admin, Tailwind+HTMX templates, an idempotent seeder, navigation wiring (a LIVE_LINKS "N.M" entry), and migrations — reusing the unified core data model (NavERP-ERD.md) and the foundation-app conventions. Use when the user says "new", "next", "next sub-module", "build/create the next sub-module", "continue the modules", or invokes /next-module. Optional argument: a specific sub-module "N.M" (e.g. "/next-module 3.4"), a sub-module name (e.g. "payroll", "offboarding"), or a whole module number/name (build its next unbuilt sub-module). With no argument, auto-detect and build the next unbuilt sub-module of the module currently in progress.
---

# next-module — NavERP module builder

When this skill is invoked, you build **one NavERP sub-module** (`N.M`) end-to-end — the **next unbuilt
sub-module of the module currently in progress**, NOT the whole module in one pass. Modules are large (HRM has 41
sub-modules, Accounting 15); each "next"/`​/next-module` run delivers exactly **one** sub-module's slice, then
stops. If the module's app already exists under `apps/<slug>`, you **extend** it (add that sub-module's models +
pages + a `LIVE_LINKS["N.M"]` entry) — you do NOT re-scaffold the app. You match the conventions
established in the codebase and the unified core data model. Module 0 (**System Admin & Security**) is realized by
the foundation apps `core` / `accounts` / `tenants` / `dashboard` — these are the **canonical reference
implementation** for a tenant-scoped CRUD module. Read them (especially `apps/tenants`) whenever you are unsure how
something should look. The shared data spine is defined in **`NavERP.md`** (catalog) and **`NavERP-ERD.md`**
(entities) — new modules POINT AT the spine instead of duplicating it.

## Triggers
- User says: **"new"**, **"next"**, "next sub-module", "build/create the next sub-module", "continue the modules". **"new"/"next" mean the next *sub-module*, one per run — never the whole module.**
- User invokes **`/next-module`** (optionally with a sub-module `N.M` like `3.4`, a sub-module name like `payroll`/`offboarding`, or a whole module number `1`–`13` / module name — in which case you build that module's *next unbuilt* sub-module).

## When NOT to use
- User wants tests for a module → `/manual-test` or `/sqa-review`.
- User wants a code dump → `/dump-module`.
- User wants to fix a specific bug → just fix it.
- User wants to change the foundation (Module 0 / dashboard / auth) → edit those directly; this skill is for **new** domain modules 1–13.

---

## Project conventions (NavERP, as-built + planned)

- **Stack:** Django 5.1, **function-based views** with `@login_required`, **Tailwind CSS (Play CDN) + HTMX +
  Chart.js + Lucide**, MySQL/MariaDB (XAMPP) via PyMySQL. DB is **`nav_erp`** (XAMPP MariaDB 10.4 version shim
  lives in `config/__init__.py`). Run Python through the venv: `venv\Scripts\python.exe manage.py ...`
  (PowerShell) — Django is not on system Python. Tests run under `config.settings_test` (SQLite in-memory) with
  pytest + pytest-django.
- **Unified core (mandatory — `NavERP-ERD.md`):** customers/vendors/suppliers/employees/leads/contacts are
  **`PartyRole`s on `Party`** — never a new standalone customer/vendor/employee table. Items/UOM/price
  lists/locations/currencies/GL accounts/tax codes are **shared masters**. Inventory effects post to **`StockMove`**
  and financial effects to **`JournalEntry`/`JournalLine`** (append-only) inside `transaction.atomic()` — on-hand
  quantities and balances are **derived** (aggregate), never stored editable. FK into core entities **by string**
  (e.g. `models.ForeignKey('core.Party', ...)`). Your module owns only its domain-specific tables.
- **App layout:** `apps/<slug>/`, AppConfig `name = 'apps.<slug>'`. Register in `config/settings.py`
  `INSTALLED_APPS` and add `path('<slug>/', include('apps.<slug>.urls'))` to `config/urls.py`.
- **Backend packages (MANDATORY):** `models/`, `forms/`, `views/`, `urls/` are **packages**, never flat `.py`
  files — **one folder per sub-module, then one file per entity**
  (`apps/<slug>/models/<SubModule>/<Entity>.py`), exactly mirroring the template rule. Each package's
  `__init__.py` re-exports everything it owns; imports inside them are **absolute**. See §2a and the two
  converted reference apps `apps/crm` + `apps/accounting`.
- **Templates:** project-level `templates/<slug>/<submodule>/<entity>/<page>.html` (**one folder per sub-module,
  then one folder per entity, with a bare `list/detail/form.html` page filename — MANDATORY**, see
  CLAUDE.md "Template Folder Structure"; landing page stays at `templates/<slug>/` root), **extend
  `templates/base.html`**, use the design-system
  classes from `static/css/theme.css`: `.page-header .page-title .breadcrumb .page-actions`, `.card .card-header
  .card-body`, `.btn .btn-primary .btn-outline .btn-danger .btn-icon`, `.badge .badge-success/.warning/.danger/
  .info/.muted` (+ color variants), `.table-wrap .table .table-actions`, `.form-group .form-label .form-input
  .form-select .form-textarea .form-error`, `.stat-card`, `.empty-state`, `.pagination`, `.avatar-initial`,
  `.progress .progress-bar`. Icons: `<i data-lucide="NAME"></i>`.
- **Multi-tenancy (mandatory):** every model has `tenant = models.ForeignKey('core.Tenant',
  on_delete=models.CASCADE, related_name='<unique>')`. Every view filters `Model.objects.filter(tenant=request.tenant)`
  — never `.all()`. `request.tenant` is set by `apps.core.middleware.TenantMiddleware`.
- **CRUD completeness (mandatory):** every model with a list page gets **list (search + filters + pagination),
  detail, create, edit, delete (POST-only + confirm + csrf)**. List templates have an Actions column
  (view/edit/delete). See CLAUDE.md "CRUD Completeness Rules" + "Filter Implementation Rules".
- **Filters:** parse `request.GET` and apply BEFORE pagination. Pass `status_choices` + any FK querysets the
  template's filter dropdowns need. pk filters compare with `|stringformat:"d"`.
- **Seeders:** idempotent (guard `if Model.objects.filter(tenant=tenant).exists()`), `get_or_create`,
  existence-check auto-numbers. Create both `management/__init__.py` and `management/commands/__init__.py`.
- **Auto-numbers:** human-readable per-tenant numbers like `INV-00001` / `PO-00001` / `NCR-00001` where it fits
  (mirror `Invoice.save()` in `apps/tenants/models.py`, which generates `INV-00001` per tenant).
- **Git:** at the end, output a **PowerShell-safe one-file-per-commit** snippet (`git add 'f'; git commit -m '...'`).
  Commit per CLAUDE.md / project memory (one file per commit, to `main`); do NOT `git push` — the user pushes.
- **Security:** flag vulnerabilities with a `# WARNING:` comment + secure alternative.

Reference files to read before building: `NavERP-ERD.md`, `apps/core/navigation.py`, `apps/core/models.py` (the
core spine), and — for the **mandatory backend package layout** — `apps/crm/` and `apps/accounting/` (both fully
converted: `models/`, `forms/`, `views/`, `urls/` packages, one folder per sub-module, one file per entity).
For single-file CRUD/auth patterns: `apps/tenants/models.py`, `apps/tenants/views.py`, `apps/tenants/forms.py`,
`templates/tenants/*.html`, `static/css/theme.css`, `apps/core/management/commands/seed_demo.py`. Patterns worth
copying from `apps/tenants`: `Invoice.save()` per-tenant auto-numbering (`INV-00001`),
`EncryptionKey.generate_secret()` / `.masked`, `OnboardingStep.seed_defaults()`, `RegisterForm.save()` (atomic)
for form `clean()` password validation, and `HEX_COLOR_VALIDATOR` on `BrandingSetting` colors.

> ⚠️ **NavERP modules are large — build ONE sub-module per run.** Each module in `NavERP.md` has many sub-modules
> (e.g. HRM has 41, Accounting 15). **Each `/next-module` run (and each "next"/"new") builds exactly ONE sub-module
> (`N.M`)** — its 1–4 own tenant-scoped models, get them fully CRUD + tenant-scoped + wired (`LIVE_LINKS["N.M"]`) +
> seeded + verified, then STOP. Do NOT build the rest of the module's sub-modules in the same run. The module's app
> is built up **sub-module by sub-module across many runs**. Reuse the unified core so you build domain logic, not
> plumbing. (The first run for a brand-new module also scaffolds the app skeleton — see Step 1 + Step 2.)

---

## Step 0 — Is the foundation built? (greenfield check)

NavERP starts as a documentation repo. Before any domain module exists, the **foundation (Module 0)** must be
built: `core` (Tenant + TenantMiddleware + `navigation.py` MODULE_CATALOG 0–13 + AuditLog + decorators +
the unified-core master tables Party/PartyRole/Item/UOM/Location/Currency/GLAccount/TaxCode + the two ledgers),
`accounts` (User/Role/Permission/UserInvite + auth/IAM/RBAC), `tenants` (subscription/billing/branding/keys/health),
`dashboard` (KPI aggregation), plus `config/`, `templates/base.html`, `static/css/theme.css`, and the seeder.
If `apps/core` / `config/settings.py` do not exist yet, build the foundation first (enter plan mode, follow
`PROMPT.md` + `NavERP-ERD.md`) — it is the reference every domain module clones.

## Step 1 — Decide which SUB-MODULE to build

> **You always resolve to exactly ONE sub-module `N.M`** (e.g. `3.4 Employee Offboarding`). The "build unit" is a
> sub-module, never a whole module. **How "built" is tracked:** a sub-module is BUILT iff it has a
> `LIVE_LINKS["N.M"]` entry in `apps/core/navigation.py` (the sidebar lights it up). Read that dict + the
> `### N.M …` sub-module headings in `NavERP.md` (or call `parse_catalog()`) to know the order and what's done.

1. **If the user passed an argument, resolve it to exactly one sub-module** (case-insensitive, punctuation/`&`/`and`
   ignored):
   - **Sub-module number `N.M`** — e.g. `3.4`, `2.13`, `module 3.4`, `#3.4` → exactly that sub-module. Build it
     (extend module N's app). This is the most direct form.
   - **Sub-module name** — e.g. `payroll`, `offboarding`, `exit interview`, `General Ledger`, `CAPA` → match it
     against the `### N.M <name>` headings in `NavERP.md` and resolve to that one `N.M`. (Match on the sub-module
     title and its feature bullets.)
   - **Whole module number `1`–`13`, app slug, or module name** — e.g. `3`, `hrm`, `"Human Resource Management"`,
     `inventory` → resolve to that module, then pick its **next unbuilt sub-module** = the lowest-numbered `N.M`
     (NavERP.md order) with **no** `LIVE_LINKS["N.M"]` entry. (Building "module 3" means building 3's next
     sub-module, NOT all of module 3.)
   - If the text matches **more than one** sub-module/module → ask the user to pick via `AskUserQuestion`. If it
     matches **none** → tell the user and show the relevant `### N.M` list.

   Examples: `/next-module 3.4` → HRM Employee Offboarding. `/next-module payroll` → HRM 3.14. `/next-module 5`
   → Inventory's next unbuilt sub-module. `/next-module hrm` → HRM's next unbuilt sub-module.

2. **If no argument**, **auto-detect the next unbuilt sub-module** of the module currently in progress:
   1. **Active module** = the **highest-numbered** module `N` (1–13) whose app slug (table below) already exists
      under `apps/` — that's the module under construction. (If NO domain app exists yet, the active module is the
      lowest unbuilt one, normally **Module 1 = `crm`**, and this run scaffolds its app + builds `1.1`.)
   2. **Next sub-module** within the active module = the **lowest-numbered `N.M`** (NavERP.md document order) that
      has **no** `LIVE_LINKS["N.M"]` entry. That is what you build. **Always read the *real* current `LIVE_LINKS`
      keys at run time** — the built set changes every run (and other sessions may build in parallel), so never
      assume it from memory or from this doc. *(Illustration of the rule only, NOT live state: if a module has
      `LIVE_LINKS` entries for `X.1, X.2, X.3, X.9, X.10, X.12`, the lowest `N.M` with no entry is **X.4**, so
      "next" → X.4, then X.5 … Out-of-order earlier builds (X.9/X.10/X.12) don't matter — you always take the
      lowest-numbered unbuilt one.)*
   3. **Module rollover:** if the active module has a `LIVE_LINKS` entry for **every** `### N.M` in NavERP.md (fully
      wired), advance to the **next module** = the lowest `1..13` whose app does NOT exist, scaffold its app, and
      build its **first** sub-module (`N.1`). Only then does a new app get created.

3. **State the one sub-module you resolved** (`N.M <name>`) and which models it adds, then proceed: enter plan mode
   per CLAUDE.md, present the short model/page spec for **that sub-module only**, then build it and STOP. If the
   user wanted a different sub-module they can pass an explicit `N.M`. Lean toward building, don't over-deliberate.

### Module → app-slug + suggested core models (module-level reference — pick the slice your sub-module needs)

This table is the **module-level** map (app slug + the kinds of models a module owns). For a single-sub-module run,
build only the **1–4 models that sub-module needs** — not every model listed for the module. Reuse the unified core
where noted; the models below are each module's **own** domain tables.

| # | Module | app slug | Suggested tenant-scoped models (own tables; reuse core for Party/Item/ledgers) |
|---|--------|----------|--------------------------------------------------------------------------------|
| 1 | Customer Relationship Management | `crm` | Lead[LEAD-], Opportunity[OPP-], Campaign[CAM-], Case[CASE-], Activity — (Account/Contact are `Party` roles; coordinate Opportunity/Quote with Sales) |
| 2 | Accounting & Finance | `accounting` | FiscalPeriod, Bill[BILL-], BankAccount, BankTransaction, Reconciliation, Budget, TaxReturn — (GLAccount/JournalEntry/Invoice/Payment are the **core** ledger) |
| 3 | Human Resource Management | `hrm` | EmployeeProfile, Department, Designation, LeaveRequest[LV-], AttendanceRecord, PayrollRun[PAY-], PerformanceReview — (Employee is a `Party` role) |
| 4 | Supply Chain Management | `scm` | Shipment[SHP-], Carrier, RoutePlan, DemandForecast, ReturnAuthorization[RMA-], SupplierScorecard |
| 5 | Inventory Management System | `inventory` | GoodsReceipt[GRN-], StockAdjustment[ADJ-], StockTransfer[TRF-], CycleCount, ReorderRule — (Item/Location/StockMove/LotSerial/UOM are **core**) |
| 6 | Procurement Management System | `procurement` | PurchaseRequisition[PR-], RFQ[RFQ-], VendorQuote, Contract[CTR-], VendorScorecard — (PurchaseOrder/GRN post to **core**) |
| 7 | Project Management | `projects` | Project[PRJ-], ProjectTask, Milestone, Timesheet[TS-], RiskItem, ChangeRequest[CR-] |
| 8 | Sales Management System | `sales` | Opportunity[OPP-], Quote[QUO-], Forecast, Territory, CommissionPlan — (SalesOrder is **core**; coordinate Lead/Opportunity with CRM) |
| 9 | eCommerce Management System | `ecommerce` | Storefront, ProductListing, Cart, Promotion[PROMO-], ProductReview — (catalog Item & orders flow to **core**) |
| 10 | Business Intelligence | `bi` | DataSource, Dashboard, Report[RPT-], KpiDefinition, ScheduledReport — (reads aggregates over the spine; minimal writes) |
| 11 | Asset Management System | `assets` | Asset[AST-], AssetCategory, MaintenanceWorkOrder[WO-], DepreciationSchedule, AssetDisposal |
| 12 | Quality Management System | `quality` | NonConformance[NCR-], CapaAction[CAPA-], Inspection[QC-], QualityAudit[QA-], Calibration |
| 13 | Document Management System | `documents` | Folder, ControlledDocument[DOC-], DocumentVersion, ApprovalRequest, RetentionPolicy — (core `Document` is the generic attachment; DMS is the full repository) |

Aim for **1–4 models** per sub-module pass (the one `N.M` you resolved) so that sub-module's features each map to a
real list page. Some sub-modules are already covered by the foundation (`accounts:role_list`, `accounts:user_list`,
`core:audit_log`, all `tenants:*`) or by an earlier sub-module — keep those mappings and only build the missing
pieces. Before coding, **verify the spine/sibling models you plan to reuse actually exist** (`grep -rn "^class <Name>"
apps/<slug>/models apps/core/models.py apps/accounting/models`  — note `models` is a **package** in crm/accounting,
so the grep must be recursive); if a planned parent (e.g. an onboarding
`AssetAllocation`, a `core.Item`) was researched but never built, make this sub-module self-contained and note the
future migration (lessons L28/L29).

---

## Step 2 — Build the sub-module (prefer a parallel agent Workflow for speed)

**Existing module vs. new module.** First check whether `apps/<slug>/` already exists:
- **App exists (the common case — you're adding a sub-module):** you **extend** it by **adding a new
  `<SubModule>/` folder to each of the four packages** (`models/`, `forms/`, `views/`, `urls/`) with one
  `<Entity>.py` per model — then **add that sub-module's re-export block to each package's `__init__.py`**
  (and wire the new url module into `urls/__init__.py`). Register the models in `admin.py` and extend the existing
  `seed_<slug>.py`. **Skip** the `apps.py`/`__init__.py` scaffolding and the `config/settings.py` `INSTALLED_APPS` +
  `config/urls.py` `include(...)` wire-up — those are already done. The only navigation change is **one new
  `LIVE_LINKS["N.M"]` entry**. `makemigrations <slug>` produces a new incremental migration (e.g. `0002_…`).
  - If you are extending an **entity that already exists** (a new field, an extra child model), edit that entity's
    existing `<Entity>.py` in each layer rather than creating a parallel file.
  - **Legacy apps not yet converted:** `apps/crm` and `apps/accounting` are packaged. If you hit an app that is
    still flat (`models.py` etc.), convert it to the package layout as part of the run — do **not** append to the
    monolith and do **not** add a `*_advanced.py` sidecar.
- **App does NOT exist (first run for a brand-new module):** scaffold the full app skeleton below (`apps.py`,
  `__init__.py`, `migrations/__init__.py`, the four **packages** with their `__init__.py` + `_base.py`/`_common.py`,
  the `management/commands` tree) AND do the `config/settings.py` + `config/urls.py` wire-up — then build that
  module's first sub-module (`N.1`).

The user prefers fanning work out across agents. For one sub-module a small **2–3 agent Workflow** works well:
keep **backend + migrations + seed** as one solo agent (single DB writer), then **templates** as 1–2 agents.
You may also build it inline if it's quick. Produce ALL of the following **for the one sub-module** (for an existing
app, "create" means "append to the existing file"):

### 2a. Backend (`apps/<slug>/`) — **models / forms / views / urls are PACKAGES, never flat .py files**

**MANDATORY — Backend Package Structure.** Exactly like the template rule, the four backend layers are organized
**one folder per sub-module, then one file per entity**. This mirrors `apps/crm` and `apps/accounting` (both fully
converted — read them as the reference).

```
apps/<slug>/
  models/   __init__.py (re-exports EVERY model)   _base.py  (shared imports + abstract Tenant* base)
  forms/    __init__.py (re-exports EVERY form)    _common.py (shared imports)
  views/    __init__.py (re-exports EVERY view)    _common.py (shared imports) [+ _helpers.py]
  urls/     __init__.py (app_name + concatenates each entity module's urlpatterns)
     +-- <SubModule>/          # PascalCase NavERP sub-module title, e.g. CoreData, GeneralLedger
           __init__.py
           <Entity>.py         # PascalCase entity, e.g. Leads.py, Invoices.py
```

The four layers **line up one-to-one**: `models/GeneralLedger/JournalEntries.py` ↔
`forms/GeneralLedger/JournalEntries.py` ↔ `views/GeneralLedger/JournalEntries.py` ↔
`urls/GeneralLedger/JournalEntries.py`. Folder = the NavERP.md sub-module title in PascalCase
(`### 2.2 General Ledger (GL)` → `GeneralLedger/`). An entity file holds the primary model **plus its children**
(`Invoices.py` = `Invoice` + `InvoiceLine`).

**Non-negotiable rules:**
1. **Every package `__init__.py` re-exports everything** it owns (`from .<SubModule>.<Entity> import (A, B)`).
   This is what keeps `from apps.<slug>.models import X`, `views.<name>` in the URLconf, and
   `include('apps.<slug>.urls')` working. **If you add a model/form/view and forget the re-export block, it breaks.**
2. **Imports inside these packages MUST be ABSOLUTE** — `from apps.<slug>.models import X`. A relative
   `from .models import X` resolves to the wrong package one level deeper and will `ImportError`/silently misbehave.
   Entity modules pull the shared toolkit via `from apps.<slug>.models._base import *` (resp. `forms._common`,
   `views._common`).
3. **`urls/__init__.py`** sets `app_name = '<slug>'` and concatenates each entity module's `urlpatterns`. Django is
   **first-match-wins**, so order is behaviour: keep literal routes before `<int:pk>` ones, and check any new greedy
   `<str:token>` route against the whole list.
4. **Shared private helpers** used by MORE THAN ONE sub-module go in `views/_helpers.py` (see
   `apps/accounting/views/_helpers.py`). Helpers used by one entity stay in that entity's module.
5. **NEVER create `models_advanced.py` / `views_advanced.py` / a second flat file for "advanced" features** — a later
   sub-module's models just get their own `<SubModule>/<Entity>.py`. (Accounting's `*_advanced.py` files were folded
   away for exactly this reason.)

**What each layer contains** (unchanged rules, new locations):
- `models/<SubModule>/<Entity>.py` — this sub-module's 1–4 models. Each: `tenant` FK, timestamps, `STATUS_CHOICES`
  class attrs where relevant, `__str__`, `class Meta: ordering`. FK into the unified core **by string**
  (`models.ForeignKey('core.Party', ...)`). Auto-number in `save()` with an existence guard. Inventory/financial
  effects go through `StockMove` / `JournalEntry` service helpers in `transaction.atomic()`. Models sit deeper than
  the app root, but Django still derives `app_label` from the app config — **migrations are unaffected**.
- `forms/<SubModule>/<Entity>.py` — ModelForms; **exclude** `tenant`, auto-`number`, and any derived/posted field.
- `views/<SubModule>/<Entity>.py` — function-based, `@login_required` (privileged writes `@tenant_admin_required`),
  tenant-scoped, full CRUD + search + filters + pagination. Write an `AuditLog` row via `apps.core.utils.log_action`.
- `urls/<SubModule>/<Entity>.py` — `urlpatterns = [...]` with names
  `<entity>_list/_detail/_create/_edit/_delete`; imports views absolutely (`from apps.<slug> import views`).
- `admin.py` — stays a flat file; register the new model(s) (`from .models import ...` still works via the re-export).
- `apps.py` / `__init__.py` — **new-app run only** (skip if the app exists).
- `migrations/` — `makemigrations <slug>` yields `0001_initial.py` for a new app, or the next incremental migration (`000N_…`) for an existing one. (`migrations/__init__.py` exists already on an existing app.)
- `management/commands/seed_<slug>.py` — for a new app create the `management/__init__.py` + `management/commands/__init__.py` tree + the command; for an existing app **extend the existing `seed_<slug>.py`** with this sub-module's demo rows (idempotent per-tenant guard; reuse existing Party/EmployeeProfile/Item rows rather than inventing duplicates).

### 2b. Wire-up
- `config/settings.py` — add `'apps.<slug>'` to `INSTALLED_APPS` **only for a brand-new app** (skip if already present).
- `config/urls.py` — add `path('<slug>/', include('apps.<slug>.urls'))` **only for a brand-new app** (skip if already present).
- `apps/core/navigation.py` — add **one `LIVE_LINKS["N.M"]` entry** for the sub-module you built, mapping its exact
  NavERP.md feature-bullet names → `'<slug>:<entity>_list'` (or the most relevant live page). After this the sidebar
  shows that sub-module as **Live** instead of the roadmap placeholder. Do NOT change `MODULE_CATALOG` (names from
  NavERP.md are already correct) and do NOT touch other sub-modules' `LIVE_LINKS` entries.

### 2c. Frontend (`templates/<slug>/<submodule>/<entity>/<page>.html`)
- **One folder per sub-module, then one folder per entity, with a bare `list/detail/form.html` page filename
  (MANDATORY — see CLAUDE.md "Template Folder Structure").** Templates live at
  `templates/<slug>/<submodule>/<entity>/<page>.html`, grouped by the NavERP.md sub-module that owns each model —
  never a flat `templates/<slug>/<submodule>/<entity>_<page>.html` file. The view's `render()`/`crud_*`
  `template=` uses that full path (e.g. `"hrm/offboarding/clearanceitem/detail.html"`). The module
  landing/overview page stays at the app root (`templates/<slug>/<slug>_overview.html` or `overview.html`/
  `dashboard.html`); standalone reports/letters/wizards stay at the sub-module level (no entity folder).
- For each new model, an entity folder under the sub-module with `list.html`, `detail.html`, `form.html`
  (shared create/edit). For a single-entity sub-module the sub-module folder doubles as the entity folder — keep
  `designation/list.html`, NOT `designation/designation/list.html`. A secondary entity-action page goes inside the
  entity folder (`cash/bank_transaction/import.html`).
- Extend `base.html`; use the design-system classes; list pages get a GET filter form (search `q` + status/FK
  selects reflecting `request.GET`), an Actions column (view/edit/delete POST+confirm+csrf), pagination, and an
  `.empty-state`. Badges use the model's exact choice values + `{{ obj.get_<field>_display }}` fallback. If the
  module already has a landing/overview page, link the new pages from it; only add a new overview page on a
  brand-new-app run.

### 2d. Migrate + seed + verify (venv python)
```
venv\Scripts\python.exe manage.py makemigrations <slug>
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py seed_<slug>
venv\Scripts\python.exe manage.py seed_<slug>   # 2nd run must be idempotent
venv\Scripts\python.exe manage.py check
```

---

## Step 3 — Verify (don't mark done until proven)

Render every new page as a tenant admin against seeded data and assert no errors / no leaks. Use a throwaway
script in `temp/` (gitignored) like the foundation smoke test:

- Log in via Django test client `force_login(User.objects.get(username='admin_acme'))` (set
  `settings.ALLOWED_HOSTS=['testserver',...]`), then GET every `<slug>:*` url (use `reverse`, sample a pk per
  model) and assert status in `(200, 302)`.
- Fetch one list page's HTML and assert **no** `'{#'` / `'{% comment'` leak markers (Django `{# #}` comments are
  single-line only — use `{% comment %}` for multi-line notes), and that the page title + a seeded record appear.
- Cross-tenant IDOR: as `admin_acme`, request an `admin_globex` record's pk → expect **404**.
- Fix anything that isn't 200/302 (usual culprit: a wrong reverse-accessor name or a context-variable
  mismatch — read the view to confirm the exact name).

Credentials: tenant admins `admin_acme` / `admin_globex`, password `password` (per
`apps/accounts/management/commands/seed_accounts.py` — NOT `password123`). The superuser `admin` has
`tenant=None` and sees no module data (by design).

---

## Step 4 — Document + commit snippet
1. Update `README.md` (mark **this sub-module** complete in the roadmap; ensure `seed_<slug>` is in the seeding section).
2. Update `.claude/tasks/todo.md` with a short review of the sub-module just built.
3. Output the **one-file-per-commit** PowerShell snippet for every created/changed file — with the package layout
   this is one commit per entity module per layer, e.g.
   `git add 'apps/<slug>/models/<SubModule>/<Entity>.py'; git commit -m 'feat(<slug>): N.M <Entity> models (...)'`
   then the same for `forms/`, `views/`, `urls/`, **and the touched `__init__.py` re-export blocks** — plus the edits to
   `apps/core/navigation.py` (the new `LIVE_LINKS["N.M"]` entry) and `README.md` — and, **on a brand-new-app run
   only**, `config/settings.py` + `config/urls.py`. One `git add` + one `git commit` per file — never bundle.
   Commit to `main`; do NOT `git push`.

---

## Step 5 — Close with the specialist review agents (CLAUDE.md "Module Creation Sequence")
After the build verifies, run the review agents **one at a time, in order** — `code-reviewer`, `explorer`,
`frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`, `test-writer` — scoped to the
sub-module's new files, applying each one's findings and committing between steps (per CLAUDE.md). This is the
quality bar, not optional (lesson L18). Then **update the module's existing skill** (`.claude/skills/<slug>/SKILL.md`)
to document the new sub-module's models/routes/templates/seeder rows — for an existing module you *update* the skill,
you do NOT create a new one (a new skill is only authored on a brand-new-app run). Commit the skill on its own.

---

## Continue / repeat
If the user says "next" again after a sub-module is done, repeat Step 1 — auto-detect now returns **the next
unbuilt sub-module** (the lowest `N.M` without a `LIVE_LINKS["N.M"]` entry in the active module), and you build that
ONE. Keep going **sub-module by sub-module** within a module; only roll over to the next module (building its `N.1`)
once every sub-module of the current one is wired (Step 1 rollover rule).

## Quality bar
A delivered sub-module must: live in the **backend package layout** (§2a — a `<SubModule>/` folder with one
`<Entity>.py` per model in each of `models/ forms/ views/ urls/`, **plus the re-export block added to every
touched `__init__.py`**, absolute imports throughout, and **no flat `models.py`/`*_advanced.py`**);
migrate cleanly to `nav_erp` (incremental migration on an existing app); seed
idempotently; pass `manage.py check`; have every new list page rendering 200 with working search/filters/pagination
+ Actions; appear as **Live** in the sidebar via its new `LIVE_LINKS["N.M"]` entry; reuse the unified core and
existing sibling models instead of duplicating Party/EmployeeProfile/Item/ledgers; match the blue/white Tailwind
design system; and isolate data per tenant. The run builds **exactly one sub-module** — if you find yourself adding
a second sub-module's models, stop. Would a staff engineer approve it? If a piece feels hacky, redo it the elegant
way before presenting.

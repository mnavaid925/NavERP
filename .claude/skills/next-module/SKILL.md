---
name: next-module
description: Scaffold and build the next NavERP module end-to-end (Modules 1–13 from NavERP.md) — a Django app under apps/<slug> with tenant-scoped models, full CRUD views/forms/urls/admin, Tailwind+HTMX templates, an idempotent seeder, navigation wiring, and migrations — reusing the unified core data model (NavERP-ERD.md) and the foundation-app conventions. Use when the user says "new", "next", "new module", "next module", "build the next module", "create the next module", "continue the modules", "scaffold the next module", or invokes /next-module. Optional argument: a specific module number 1–13 (e.g. "/next-module 5") or a module name; with no argument, auto-detect the lowest-numbered module not yet built.
---

# next-module — NavERP module builder

When this skill is invoked, you build **one complete NavERP module** end-to-end, matching the conventions
established in the codebase and the unified core data model. Module 0 (**System Admin & Security**) is realized by
the foundation apps `core` / `accounts` / `tenants` / `dashboard` — these are the **canonical reference
implementation** for a tenant-scoped CRUD module. Read them (especially `apps/tenants`) whenever you are unsure how
something should look. The shared data spine is defined in **`NavERP.md`** (catalog) and **`NavERP-ERD.md`**
(entities) — new modules POINT AT the spine instead of duplicating it.

## Triggers
- User says: **"new"**, **"next"**, "new module", "next module", "build/create the next module", "continue the modules", "scaffold module N".
- User invokes **`/next-module`** (optionally with a module number `1`–`13` or a module name).

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
- **Templates:** project-level `templates/<slug>/...`, **extend `templates/base.html`**, use the design-system
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

Reference files to read before building: `NavERP-ERD.md`, `apps/tenants/models.py`, `apps/tenants/views.py`,
`apps/tenants/urls.py`, `apps/tenants/forms.py`, `apps/core/navigation.py`, `apps/core/models.py` (the core spine),
`templates/tenants/*.html`, `static/css/theme.css`, `apps/core/management/commands/seed_demo.py`. Patterns worth
copying from `apps/tenants`: `Invoice.save()` per-tenant auto-numbering (`INV-00001`),
`EncryptionKey.generate_secret()` / `.masked`, `OnboardingStep.seed_defaults()`, `RegisterForm.save()` (atomic)
for form `clean()` password validation, and `HEX_COLOR_VALIDATOR` on `BrandingSetting` colors.

> ⚠️ **NavERP modules are large.** Each module in `NavERP.md` has many sub-modules (e.g. HRM has 41, Accounting 15).
> Do NOT try to build an entire module's every sub-module in one pass. Build the module's **core entities first**
> (the representative models below), get them fully CRUD + tenant-scoped + wired + seeded + verified, then layer
> additional sub-modules in follow-up runs. Reuse the unified core so you build domain logic, not plumbing.

---

## Step 0 — Is the foundation built? (greenfield check)

NavERP starts as a documentation repo. Before any domain module exists, the **foundation (Module 0)** must be
built: `core` (Tenant + TenantMiddleware + `navigation.py` MODULE_CATALOG 0–13 + AuditLog + decorators +
the unified-core master tables Party/PartyRole/Item/UOM/Location/Currency/GLAccount/TaxCode + the two ledgers),
`accounts` (User/Role/Permission/UserInvite + auth/IAM/RBAC), `tenants` (subscription/billing/branding/keys/health),
`dashboard` (KPI aggregation), plus `config/`, `templates/base.html`, `static/css/theme.css`, and the seeder.
If `apps/core` / `config/settings.py` do not exist yet, build the foundation first (enter plan mode, follow
`PROMPT.md` + `NavERP-ERD.md`) — it is the reference every domain module clones.

## Step 1 — Decide which module to build

1. **If the user passed an argument, resolve it to exactly one module** (number, name, keyword, or app slug — all
   accepted, case-insensitive, punctuation/`&`/`and` ignored):
   - **Number** — `1`–`13` (also `01`, `#3`, `module 5`) → that module.
   - **App slug** — a value from the table below (e.g. `crm`, `accounting`, `inventory`) → that module.
   - **Full or partial module name** — match against the `MODULE_CATALOG` names in `apps/core/navigation.py`
     (e.g. `Accounting`, `HRM`, `Inventory`, `Procurement`, `Quality`). Case-insensitive substring/keyword match on
     the module name **and** its app slug.
   - **Sub-module name** — if the text matches a sub-module (e.g. `General Ledger`, `Payroll`, `CAPA`, `Bin
     Management`), build (or extend) that sub-module's parent module.
   - If the text matches **more than one** module → ask the user to pick via `AskUserQuestion`. If it matches
     **none** → tell the user and show the module table.
   - If the resolved module's app already exists under `apps/`, say so and ask whether to extend it (add more
     sub-modules) or pick another.

   Examples: `/next-module 5`, `/next-module inventory`, `/next-module "Accounting & Finance"`,
   `/next-module payroll`, `"build the Procurement module"`, `"create Quality Management"` all resolve to one module.

2. **If no argument**, **auto-detect the next module**: the lowest `N` in `1..13` whose app slug (table below)
   does NOT yet exist under `apps/`. (Once the foundation is built, the first domain run targets **Module 1 =
   `crm`**.) Confirm by checking the directory and `apps/core/navigation.py` `LIVE_LINKS`.
3. State which module you're building and proceed (enter plan mode per CLAUDE.md, present the short model/page
   spec for the module's core entities, then build — lean toward building, don't over-deliberate).

### Module → app-slug + suggested core models (representative — adapt and extend per NavERP.md)

Reuse the unified core where noted; the models below are each module's **own** domain tables.

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

Aim for **4–8 models** per module pass so the most important sub-modules each map to a real list page. Some
sub-modules are already covered by the foundation (`accounts:role_list`, `accounts:user_list`, `core:audit_log`,
all `tenants:*`) — keep those mappings and only build the missing pieces.

---

## Step 2 — Build the module (prefer a parallel agent Workflow for speed)

The user prefers fanning work out across agents. For a single module a small **2–3 agent Workflow** works well:
keep **backend + migrations + seed** as one solo agent (single DB writer), then **templates** as 1–2 agents.
You may also build it inline if it's quick. Either way produce ALL of the following:

### 2a. Backend (`apps/<slug>/`)
- `apps.py` (`name='apps.<slug>'`, `verbose_name`), `__init__.py`.
- `models.py` — the core models above. Each: `tenant` FK, timestamps (mirror `apps/tenants` base or add
  `created_at/updated_at`), `STATUS_CHOICES` class attrs where relevant, `__str__`, `class Meta: ordering`.
  FK into the unified core **by string** (`models.ForeignKey('core.Party', ...)`, `('core.Item', ...)`). Where a
  domain model belongs to a parent in another module, FK it by string **once that module exists**. Auto-number in
  `save()` or the view with an existence guard. Inventory/financial effects go through `StockMove` /
  `JournalEntry` service helpers in `transaction.atomic()`.
- `forms.py` — ModelForms; **exclude** `tenant`, auto-`number`, and any derived/posted field (set them in the view).
- `views.py` — function-based, `@login_required` (privileged writes `@tenant_admin_required`), tenant-scoped, full
  CRUD + search + filters + pagination (copy the shape from `apps/tenants/views.py`). Write an `AuditLog` row on
  meaningful changes via `apps.core.utils.log_action`.
- `urls.py` — `app_name='<slug>'`, names `<entity>_list/_detail/_create/_edit/_delete` per model.
- `admin.py` — register every model.
- `migrations/__init__.py` (+ generated `0001_initial.py`).
- `management/__init__.py`, `management/commands/__init__.py`, `management/commands/seed_<slug>.py`
  (idempotent Faker seeder for both demo tenants; mirror `seed_demo`'s per-tenant guard + summary print; reuse
  existing Party/Item rows rather than inventing duplicates).

### 2b. Wire-up
- `config/settings.py`: add `'apps.<slug>'` to `INSTALLED_APPS`.
- `config/urls.py`: add `path('<slug>/', include('apps.<slug>.urls'))`.
- `apps/core/navigation.py`: add entries to `LIVE_LINKS` mapping each built sub-module
  `(<module_number>, '<exact sub-module name from MODULE_CATALOG>')` → `'<slug>:<entity>_list'` (or the most
  relevant live page). After this, the sidebar shows those sub-modules as **Live** instead of the roadmap
  placeholder. Do not change `MODULE_CATALOG` (names/descriptions are already correct from NavERP.md).

### 2c. Frontend (`templates/<slug>/`)
- For each model: `<entity>_list.html`, `<entity>_detail.html`, `<entity>_form.html` (shared create/edit).
- Extend `base.html`; use the design-system classes; list pages get a GET filter form (search `q` + status/FK
  selects reflecting `request.GET`), an Actions column (view/edit/delete POST+confirm+csrf), pagination, and an
  `.empty-state`. Badges use the model's exact choice values + `{{ obj.get_<field>_display }}` fallback. Add a
  module landing/overview page (stat cards summarizing the module) if helpful.

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

Credentials: tenant admins `admin_acme` / `admin_globex`, password `password123`. The superuser `admin` has
`tenant=None` and sees no module data (by design).

---

## Step 4 — Document + commit snippet
1. Update `README.md` (mark the sub-modules complete in the roadmap; add `seed_<slug>` to the seeding section).
2. Update `.claude/tasks/todo.md` with a short review.
3. Output the **one-file-per-commit** PowerShell snippet for every created/changed file
   (`git add 'apps/<slug>/models.py'; git commit -m 'feat(<slug>): models (...)'` etc.), plus the edits to
   `config/settings.py`, `config/urls.py`, `apps/core/navigation.py`, `README.md`. One `git add` + one
   `git commit` per file — never bundle. Commit to `main`; do NOT `git push`.

---

## Step 5 — Close with the specialist review agents (CLAUDE.md "Module Creation Sequence")
After the build verifies, run the review agents **one at a time, in order** — `code-reviewer`, `explorer`,
`frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`, `test-writer` — applying each
one's findings and committing between steps (per CLAUDE.md). This is the quality bar, not optional (lesson L18).

---

## Continue / repeat
If the user says "next" again after a module is done, repeat Step 1 (auto-detect now returns the next-lowest
unbuilt module) and build that one. Keep going module by module — or sub-module by sub-module within a large
module — on request.

## Quality bar
A delivered module must: migrate cleanly to `nav_erp`; seed idempotently; pass `manage.py check`; have every
list page rendering 200 with working search/filters/pagination + Actions; appear as **Live** in the sidebar for
its built sub-modules; reuse the unified core instead of duplicating Party/Item/ledgers; match the blue/white
Tailwind design system; and isolate data per tenant. Would a staff engineer approve it? If a piece feels hacky,
redo it the elegant way before presenting.

---
name: dump-module
description: Regenerate the consolidated <NN>_<slug>.txt code dump for one (or all) NavERP modules into the temp/ folder. The .txt file contains every backend file from apps/<name>/ followed by every frontend template from templates/<name>/, with per-file separators. Use when the user says "dump module X", "regenerate the temp file for X", "extract code for module X", "give me a code dump of X", or invokes /dump-module. The user can pass a module number (0-13), an app folder name (tenants/accounts/core/dashboard plus the domain slugs like crm/accounting/inventory), a friendly name (e.g. "subscription", "ledger", "purchase order", "asset"), or "all" to regenerate every module.
---

# dump-module — NavERP module code-dump generator

This skill regenerates one (or all) of the consolidated `temp\<NN>_<slug>.txt` files that contain a single module's complete backend + frontend source code, for use in code review, hand-off, AI prompts, or archival.

NavERP is a multi-tenant **Enterprise Resource Planning (ERP)** platform (Django 5.1 + Tailwind/HTMX/Chart.js/Lucide, MySQL/MariaDB via PyMySQL, DB `nav_erp`). **Module 0 (System Admin & Security)** is realized by the foundation apps **`core` / `accounts` / `tenants` / `dashboard`** (tenancy, IAM/RBAC, auth, audit, settings, subscription/billing, KPI aggregation). Modules **1–13** from `NavERP.md` are domain modules (one Django app each) built on demand by the **`/next-module`** skill — until each is built, dumping it produces only a header and a "(no backend folder found ...)" note, which is expected.

## When to use

- User says: "dump module X", "regenerate temp file for X", "extract module X code", "give me the .txt for X", "refresh the tenants module dump", "dump the crm app", "rebuild all module dumps"
- User invokes `/dump-module` (with or without an argument)
- User explicitly references the `temp/` folder code dumps

## When NOT to use

- User wants documentation written for a module → use the README maintenance rule and edit `README.md`
- User wants automated tests / SQA review for a module → use `/sqa-review`
- User wants a manual click-through test → use `/manual-test`
- User wants to scaffold a brand-new module 1–13 → use `/next-module`
- User wants a code review → use `/review` or `/sqa-review`

## Inputs

The skill takes ONE positional argument — the module identifier. Accepted forms:

| Form                | Examples                                     |
|---------------------|----------------------------------------------|
| Module number       | `0`, `5`, `13`, `00`, `05`                   |
| App folder name     | `tenants`, `accounts`, `core`, `dashboard` (foundation); `crm`, `accounting`, `hrm`, `scm`, `inventory`, `procurement`, `projects`, `sales`, `ecommerce`, `bi`, `assets`, `quality`, `documents` (domain modules 1–13) |
| Friendly keyword    | `subscription`, `users`, `ledger`, `payroll`, `purchase order`, `pipeline`, `asset`, `capa`, `document` |
| Bulk                | `all` (or `*`) — regenerates every registry entry |

If the user does NOT specify a module, ask them which one (single-select) before running the script — do not guess. Default to **tenants** (the Module 0 / System Admin & Security CRUD slice) if they say "the module" with no name; the `tenants` app is the richest as-built CRUD surface (OnboardingStep/Subscription/Invoice/EncryptionKey/BrandingSetting/HealthMetric).

## How to run

The skill ships a single PowerShell script: `.claude\skills\dump-module\dump_module.ps1`. Invoke it via the **PowerShell** tool (the user is on Windows PowerShell 5.x):

```
& '.claude\skills\dump-module\dump_module.ps1' -Module <identifier>
```

Examples:

```
& '.claude\skills\dump-module\dump_module.ps1' -Module tenants
& '.claude\skills\dump-module\dump_module.ps1' -Module 0
& '.claude\skills\dump-module\dump_module.ps1' -Module crm
& '.claude\skills\dump-module\dump_module.ps1' -Module all
```

Notes:
- The script's `$RepoRoot` defaults to `C:\xampp\htdocs\NavERP`.
- The script auto-creates `temp/` if missing.
- The script overwrites the matching `<NN>_<slug>.txt` file (idempotent — safe to re-run).
- `temp/` should be gitignored — no commit snippet needed for the generated `.txt`.
- The script prints one line per generated file: `OK  <slug>  <bytes>  ->  temp\<slug>.txt`.
- It walks `apps\<name>\` **recursively**, so the `models/ forms/ views/ urls/` **packages** (one folder per
  sub-module, one file per entity) are captured with no script change. A packaged module therefore produces many
  small file blocks rather than four large ones — that is expected, not a bug.

## Backend layout the dump walks (models/forms/views/urls are PACKAGES)

Built modules keep their backend in **packages, not flat `.py` files** — `models/`, `forms/`, `views/`, `urls/` each
hold **one folder per NavERP sub-module, then one file per entity** (see CLAUDE.md / `/next-module` §2a). `apps/crm`
and `apps/accounting` are the converted reference apps.

The generator walks `apps\<name>\` **recursively** (`Get-ChildItem -Recurse`, `__pycache__` excluded), so these
nested package files are picked up automatically — **no script change is needed when a module is packaged**. The
practical effect is that a packaged module dumps *many* small file blocks instead of four huge ones (e.g. the
accounting dump is ~228 backend blocks / ~900 KB), sorted by full path so each package's folders read together.

## Output structure (per .txt file)

```
####################################################################################################
# MODULE <number>. <Title>
# Backend:  apps\<name>\
# Frontend: templates\<name>\
# Generated: <YYYY-MM-DD HH:MM:SS>
####################################################################################################

====================================================================================================
BACKEND  (apps\<name>\)
====================================================================================================

----------------------------------------------------------------------------------------------------
FILE: apps\<name>\admin.py
----------------------------------------------------------------------------------------------------
<file contents>

----------------------------------------------------------------------------------------------------
FILE: apps\<name>\models\__init__.py            <- package __init__ (re-exports every model)
----------------------------------------------------------------------------------------------------
FILE: apps\<name>\models\_base.py               <- shared imports + abstract Tenant* base
FILE: apps\<name>\models\<SubModule>\<Entity>.py
FILE: apps\<name>\forms\<SubModule>\<Entity>.py
FILE: apps\<name>\views\_common.py  /  _helpers.py
FILE: apps\<name>\views\<SubModule>\<Entity>.py
FILE: apps\<name>\urls\__init__.py              <- app_name + concatenated urlpatterns
FILE: apps\<name>\urls\<SubModule>\<Entity>.py
...

... (one block per .py / .json / .yml / .md / .ini file, sorted by full path, __pycache__ excluded)

====================================================================================================
FRONTEND  (templates\<name>\)
====================================================================================================

----------------------------------------------------------------------------------------------------
FILE: templates\<name>\<submodule>\<entity>\list.html
----------------------------------------------------------------------------------------------------
<file contents>

... (one block per .html / .htm / .js / .css / .txt file, sorted by full path)
```

If a module's `apps\<name>\` or `templates\<name>\` folder does not exist yet (any unbuilt module 1–13), that section is replaced by `(no backend folder found at apps\<name>\)` / `(no frontend folder found at templates\<name>\)`.

## Module registry (kept in `dump_module.ps1`)

Module numbers follow `NavERP.md` (modules 0–13). **Module 0** (System Admin & Security) is realized by the foundation apps `core` / `accounts` / `tenants` / `dashboard`. **Modules 1–13** are forward-compatible registry rows that map to the `/next-module` domain app slugs; their folders are created only when `/next-module` builds them.

| # | Slug             | apps\         | templates\    | Status |
|---|------------------|---------------|---------------|--------|
| 0 | `00_tenants`     | `tenants`     | `tenants`     | Foundation (Module 0 — Tenant & Subscription slice) |
| — | `accounts`       | `accounts`    | `accounts`    | Foundation (Module 0 — users/roles/IAM/RBAC/auth) |
| — | `core`           | `core`        | `core`        | Foundation (Module 0 — tenant/audit/navigation/party) |
| — | `dashboard`      | `dashboard`   | `dashboard`   | Foundation (KPI aggregation) |
| 1 | `01_crm`         | `crm`         | `crm`         | Roadmap |
| 2 | `02_accounting`  | `accounting`  | `accounting`  | Roadmap |
| 3 | `03_hrm`         | `hrm`         | `hrm`         | Roadmap |
| 4 | `04_scm`         | `scm`         | `scm`         | Roadmap |
| 5 | `05_inventory`   | `inventory`   | `inventory`   | Roadmap |
| 6 | `06_procurement` | `procurement` | `procurement` | Roadmap |
| 7 | `07_projects`    | `projects`    | `projects`    | Roadmap |
| 8 | `08_sales`       | `sales`       | `sales`       | Roadmap |
| 9 | `09_ecommerce`   | `ecommerce`   | `ecommerce`   | Roadmap |
| 10 | `10_bi`         | `bi`          | `bi`          | Roadmap |
| 11 | `11_assets`     | `assets`      | `assets`      | Roadmap |
| 12 | `12_quality`    | `quality`     | `quality`     | Roadmap |
| 13 | `13_documents`  | `documents`   | `documents`   | Roadmap |

When `/next-module` builds one of the roadmap modules, the registry already covers it — no edit needed. If a NEW app/slug is added that is not in this table, append a row to the `$registry` and `$aliases` blocks in `dump_module.ps1`. The domain slugs above must stay in sync with the `Module → app-slug` table in `.claude/skills/next-module/SKILL.md`.

## After running

1. Show the user the printed `OK ... bytes` line(s).
2. Confirm the path: `temp\<slug>.txt`.
3. Do NOT propose a git commit for the .txt file — `temp/` is gitignored.
4. If the script reports "no backend folder found" or "no frontend folder found" for a module, surface that warning to the user. For a roadmap module (1–13) this simply means it hasn't been built yet — suggest `/next-module` to scaffold it. For a built module it would mean the folder name in the registry is stale.

## Workflow checklist

1. Resolve the module identifier from the user's request. If ambiguous, ask via `AskUserQuestion` (default to `tenants` if they said "the module" with no name).
2. Invoke the PowerShell script via the PowerShell tool with the resolved identifier.
3. Relay the script's `OK ... bytes` output to the user verbatim.
4. End the turn — no commits, no follow-up unless the user asks for more.

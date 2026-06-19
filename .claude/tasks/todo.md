# NavERP — Task Plan & Build Roadmap

NavERP is a multi-tenant **Enterprise Resource Planning (ERP)** platform. Stack: Django 5.1 (function-based views,
`@login_required`) + Tailwind (Play CDN) + HTMX + Chart.js + Lucide; MySQL/MariaDB via PyMySQL, DB **`nav_erp`**
(XAMPP MariaDB 10.4 shim in `config/__init__.py`); venv Python; tests under `config.settings_test` (SQLite).
Master catalog: **`NavERP.md`** (modules 0–13). Unified data model: **`NavERP-ERD.md`** (Party + two ledgers).

---

## Current task — Re-target `.claude` tooling + ERD from the Sales project to NavERP

- [x] Review `NavERP.md` (14 modules, 0–13) and the existing `NavERP-ERD.md`.
- [x] Review every file under `.claude/` (agents, skills, hooks, configs, tasks).
- [x] Re-theme the 7 review agents (Sales → ERP, modules 0–13, DB `nav_erp`, unified-core awareness).
- [x] Re-theme `launch.json` (config name `NavERP`) and `hooks/on_stop.py` (project name).
- [x] Preserve & adapt `tasks/lessons.md` (token swaps + carry-over note; technical lessons kept).
- [x] Reset `tasks/todo.md` to this NavERP plan.
- [x] Re-theme the 4 skills (`dump-module`, `next-module`, `sqa-review`, `manual-test`) + `dump_module.ps1`.
- [x] Rewrite `PROMPT.md` as the NavERP build prompt.
- [x] Redesign `NavERP-ERD.md` (enhance the unified-core spine; no duplication; module-coverage map; legend).
- [x] Verify: grep all `.claude` + ERD for stale tokens; 3-agent adversarial review (ERD coverage, Mermaid
      syntax, `.claude` consistency) — all findings applied.
- [x] One-file-per-commit (PowerShell-safe) to `main`; do NOT push (user pushes).

## Review (outcome)

**Status: `.claude` tooling + ERD fully re-targeted from the Sales project to NavERP. ✅**

- 7 review agents, 4 skills + `dump_module.ps1`, `PROMPT.md`, `launch.json`, `on_stop.py`, `lessons.md`, `todo.md`
  re-themed to ERP / modules 0–13 / DB `nav_erp` / domain slugs. `on_edit.py` + `settings.json` already generic
  (no change). `CLAUDE.md` commit example aligned to NavERP `templates/crm/` naming.
- `NavERP-ERD.md` enhanced: notation legend, cross-module anchors (OrgUnit/Employment/Activity/Project/Asset/
  WorkOrder/Contract/QualityRecord), DMS-enriched `Document`, and a Module 0–13 coverage map (reuse vs add). 42
  entities; Mermaid validated by an independent reviewer.
- Adversarial review (3 agents): Mermaid clean; `.claude` consistent (catalog/slugs agree across next-module,
  dump-module, `dump_module.ps1`; no duplicate `$aliases` keys; DB `nav_erp` everywhere). 3 confirmed fixes
  applied — lessons.md rename artifact, ERD USER↔ROLE cardinality vs single `role_id` FK, ERD `Invoice` name
  collision (→ `SubscriptionInvoice`).

---

## NavERP module roadmap (0–13)

Module 0 (**System Admin & Security**) is the cross-cutting platform — realized by the foundation apps. Modules
1–13 are functional domains, one Django app each. They are large (many sub-modules); build them incrementally,
sub-module by sub-module, reusing the unified core (`Party`/`Item`/`StockMove`/`JournalEntry`) instead of
duplicating customers/vendors/items.

| # | Module | App slug | Status |
|---|--------|----------|--------|
| 0 | System Admin & Security | `core` + `accounts` + `tenants` (+ `dashboard`) | Foundation — build first |
| 1 | Customer Relationship Management (CRM) | `crm` | Roadmap |
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

### Suggested build order
1. **Foundation (Module 0):** `core` (Tenant, middleware, navigation MODULE_CATALOG 0–13, audit, decorators),
   `accounts` (User/Role/Permission/auth/IAM/RBAC), `tenants` (subscription/billing/branding/keys/health),
   `dashboard` (KPI aggregation), plus the unified-core master tables from `NavERP-ERD.md`.
2. **Order-to-cash / procure-to-pay spine:** modules that exercise the two ledgers — `inventory` (5),
   `procurement` (6), `accounting` (2), `sales` (8).
3. **Remaining domains:** `crm` (1), `hrm` (3), `scm` (4), `projects` (7), `ecommerce` (9), `assets` (11),
   `quality` (12), `documents` (13), `bi` (10, read-only over the spine).

---

## Baked-in lessons (see `.claude/tasks/lessons.md`)

L1 verify DB is ours/empty before migrate · L2 `{% comment %}` for multi-line notes (not `{# #}`) ·
L3/L8 pair status-sweep with content assertions · L4/L23 MariaDB-10.4 shim (lower floor **and** force RETURNING
off) · L7 pin EVERY context var handed to parallel agents · L9 guard pagination prev/next · L10 guard FK display ·
L11 `.isdigit()` before int FK filter · L12/L24 wire-up after files exist · L18 close every build with the
specialist review agents · L19 tests run under `config.settings_test` (SQLite), never the dev DB · L20 EXCLUDE
secret/derived fields from ModelForms · L22 no system `*_at` on edit forms · L25 reveal a generated secret once
via a pop-once session key · L26 validate any value rendered into inline `style=` · L27 gate Module-0 writes
behind `@tenant_admin_required` · L28 a confirmed defect in one clone → sweep all siblings.

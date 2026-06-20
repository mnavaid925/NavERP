# NavERP — Foundation Build (Module 0 + Sub-module 0.1)

Greenfield Django 5.1 + Tailwind(Play CDN)/HTMX + Chart.js + Lucide; MySQL `nav_erp` on XAMPP MariaDB 10.4
(PyMySQL + L4/L23 shim). Plan: `C:\Users\user\.claude\plans\gleaming-gliding-ullman.md`.

Scope decisions: **Module-0 core spine only** · **real Stripe sandbox** (with no-key manual fallback) · **standard auth**
(MFA/SSO = roadmap).

## Phase checklist

- [x] **Phase 0 — Env**: venv + deps; verified `nav_erp` empty (L1).
- [x] **Phase 1 — Bootstrap**: requirements, .env(.example), pytest.ini, manage.py, `config/__init__.py` (MariaDB 10.4 shim), wsgi/asgi/settings_test.
- [x] **Phase 2 — Design system**: theme.css, layout.js, app.js, logo; base.html, base_auth.html, partials (sidebar/topbar/footer/messages/pagination/customizer), registration pages.
- [x] **Phase 3 — Backends**: core (spine + middleware/decorators/nav/crud/utils/context_processors), accounts (User/Role/Permission/UserInvite + auth + RBAC), tenants (0.1 + Stripe), dashboard. Seeders for all three.
- [x] **Phase 4 — Config wiring**: config/urls.py, then config/settings.py LAST → `manage.py check` clean (L24).
- [x] **Phase 5 — DB**: created `nav_erp`; makemigrations + migrate clean on MariaDB 10.4 (L23 shim proven); seed_core/seed_accounts/seed_tenants all ran (idempotent).
- [x] **Templates**: shell + canonical party_* hand-written; remaining 52 CRUD templates generated via Workflow (8 agents). 69 templates total.
- [x] **Phase 6 — Verify**: test-client sweep over 72 URLs (all 200/302, no comment leak), IDOR→404, admin→403; browser screenshots of login + dashboard; no console errors.
- [x] **Phase 7 — Review agents** (all 7, in order, fixes applied + committed per file): code-reviewer (open-redirect, logout POST, atomic mark-paid, orphan-create guard) · explorer (clean; stale-snapshot false alarm) · frontend-reviewer (windowed pagination, theme utilities, a11y labels, alt, toast) · performance-reviewer (N+1, indexes, branding accessor, health subquery, numbering retry) · qa-smoke-tester (49 checks, 0 fail) · security-reviewer (upload limits, SECRET_KEY fail-hard, invite guards, branding CSS-injection defense) · test-writer (**298 tests passing, 89% cover**).
- [x] **README** rewritten (setup/.env/run/seed logins/Stripe/testing + MFA-SSO-axes-media roadmap notes).

## Review (outcome)

**Status: Module 0 foundation + sub-module 0.1 — COMPLETE and verified. ✅**

- 4 apps (core/accounts/tenants/dashboard) + config; ~130 files; one-file-per-commit to `main` (not pushed).
- `manage.py check` clean; `migrate` clean on MariaDB 10.4 (L23 shim proven); 3 idempotent seeders; 298 pytest green under SQLite test settings.
- Stripe test-mode billing with signature-verified webhook + manual fallback. Multi-tenant isolation, RBAC, audit, reveal-once keys, white-label branding all working and tested.
- Next: build modules 1–13 with the `/next-module` skill, reusing the unified core.

## Demo logins (after seed)
- Superuser: `admin` / `admin` (tenant=None → no module data, by design).
- Tenant admins: `admin_acme` / `password`, `admin_globex` / `password`.
- Members: `sales_acme`, `ops_acme`, etc. / `password`.

## Notes / decisions
- One file per commit, PowerShell-safe, to `main`; never push (user pushes).
- ERD-silent choices committed: Activity.subject; UserInvite 7-day token; HealthMetric time-series; EncryptionKey prefix+sha256 reveal-once (L25); sessions idle 30m / absolute 12h; tenant from `user.tenant` (subdomain routing = roadmap).
- Stripe: webhook is the only CSRF-exempt endpoint (signature-verified, idempotent); blank keys → manual mark-paid.

---

# Module 1 — CRM (sub-modules 1.1 → 1.6)

Plan: `C:\Users\user\.claude\plans\groovy-splashing-hopper.md`. Reuses the unified core spine
(Accounts/Contacts = `core.Party`); CRM adds 6 own tables. One file per commit to `main`, no push.

## Backend (`apps/crm/`)
- [ ] `__init__.py`, `apps.py` (AppConfig `apps.crm`)
- [ ] `models.py` — abstract `TenantNumbered` + Lead/Opportunity/Campaign/Case/KnowledgeArticle/CrmTask
- [ ] `forms.py` — 6 `TenantModelForm`s
- [ ] `views.py` — CRUD (crud.py helpers) + account/contact lenses + lead_convert + overview
- [ ] `urls.py` (`app_name='crm'`), `admin.py`
- [ ] `migrations/0001_initial.py` (generated)
- [ ] `seed_crm.py` (idempotent)

## Wire-up
- [ ] `config/settings.py` → `apps.crm`; `config/urls.py` → `crm/` include
- [ ] `apps/core/navigation.py` → LIVE_LINKS 1.1–1.6

## Templates (`templates/crm/`)
- [ ] 6 models × (list, detail, form) + account/contact (list, detail) + overview

## Verify
- [ ] makemigrations+migrate; seed_crm ×2 (idempotent); `manage.py check`
- [ ] temp/ smoke: crm:* urls 200/302, no comment leaks, cross-tenant IDOR → 404; sidebar Live

## Close-out
- [ ] Review agents (code→explorer→frontend→perf→qa→security→test-writer) + `.claude/skills/crm/SKILL.md` + README

## Review notes
(to fill in at the end)

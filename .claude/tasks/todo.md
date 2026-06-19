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
- [~] **Templates**: shell + canonical party_* written; remaining ~52 CRUD templates generating via Workflow (core/accounts/tenants).
- [ ] **Phase 6 — Verify**: runserver smoke + test-client sweep (all url names 200/302, no comment leak, IDOR→404, admin-gating), browser screenshots.
- [ ] **Phase 7 — Review agents** (mandatory, in order): code-reviewer → explorer → frontend-reviewer → performance-reviewer → qa-smoke-tester → security-reviewer → test-writer. Commit per file.
- [ ] **README** update (setup/.env/run/seed logins; MFA/SSO + django-axes roadmap notes).

## Demo logins (after seed)
- Superuser: `admin` / `admin` (tenant=None → no module data, by design).
- Tenant admins: `admin_acme` / `password`, `admin_globex` / `password`.
- Members: `sales_acme`, `ops_acme`, etc. / `password`.

## Notes / decisions
- One file per commit, PowerShell-safe, to `main`; never push (user pushes).
- ERD-silent choices committed: Activity.subject; UserInvite 7-day token; HealthMetric time-series; EncryptionKey prefix+sha256 reveal-once (L25); sessions idle 30m / absolute 12h; tenant from `user.tenant` (subdomain routing = roadmap).
- Stripe: webhook is the only CSRF-exempt endpoint (signature-verified, idempotent); blank keys → manual mark-paid.

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

## Review notes — CRM COMPLETE ✅

- **Built:** `apps/crm/` (6 models via abstract `TenantNumbered` + lenses over `core.Party`), 23 templates,
  idempotent `seed_crm`, wired into settings/urls/navigation (1.1–1.6 Live). Migrations 0001 (models) + 0002
  (created_at indexes).
- **Module Creation Sequence (all 7 agents, in order, fixes committed between):**
  - code-reviewer → fixed converted_party→detail link by Party kind, tenant-scoped Party-lens querysets,
    DB-side overview aggregation.
  - explorer → all 5 categories clean, no changes.
  - frontend-reviewer → valid stat-icon variant, dashboard-style layout-2col, case `new` badge, dark/RTL SLA banner.
  - performance-reviewer → dropped unused list joins + deferred KB body, single-pass win/closed aggregate,
    (tenant, created_at) indexes.
  - qa-smoke-tester → 53/53 checks pass (0 leaks, 0 IDOR, require_POST enforced, idempotent seed).
  - security-reviewer → explicit tenant scope on detail reverse-FK sub-queries (defense-in-depth).
  - test-writer → 242 tests; surfaced + fixed Decimal-cast bug in `weighted_amount`/`roi`.
- **Verification:** `manage.py check` clean; migrate clean on nav_erp; `seed_crm` idempotent; full suite
  **540 passed** (298 foundation + 242 CRM); throwaway `temp/crm_smoke.py` green (all crm:* 200/302, no comment
  leaks, cross-tenant IDOR→404, lead_convert works).
- **Skill:** `.claude/skills/crm/SKILL.md` authored. README roadmap/seeding/route-map/feature sections updated.
- One file per commit to `main`; **not pushed** (user pushes).

### Follow-up — rich Accounts & Contacts (CRUD + fields) ✅
- User asked Contacts to have address/phone/etc. and Accounts more fields. Added CRM-owned
  `AccountProfile`/`ContactProfile` (OneToOne `core.Party`); upgraded Accounts/Contacts from read-only
  lenses to **full CRUD** (Party + profile managed atomically) with industry/website/revenue/employees/
  parent (accounts) and job title/phone/mobile/employer (contacts) + address/source/owner. Idempotent
  profile backfill in seeder. Migrations 0003 (models) + 0004 (filter indexes).
- Review agents (all 7) on the enhancement, fixes committed between:
  code-reviewer (atomic profile create in edit; URLField assume_scheme) · explorer (clean) ·
  frontend-reviewer (address-blank guard; industry/source list filters) · performance-reviewer
  (2nd-hop select_related N+1; profile indexes; admin list_select_related) · qa-smoke-tester (75/75) ·
  security-reviewer (**delete = `@tenant_admin_required`**, buttons hidden from members) · test-writer
  (116 new tests incl. member-403, IDOR, javascript:-URL rejection).
- Verify: check clean; `seed_crm` idempotent; smoke green (account/contact create→edit→detail→delete +
  IDOR + member-403); full suite **656 passed**.
- **Open recommendation (foundation):** `core:party_delete` is still `@login_required` — for platform-wide
  consistency the user may want it `@tenant_admin_required` too (left unchanged; out of CRM scope).

---

# Module 1 Extension — CRM Sub-modules 1.7 → 1.12 (slug: crm)  — plan from research-crm-1.7-1.12.md  (2026-06-20)

> **Context:** Extension pass on the existing `apps/crm` app. Sub-modules 1.1–1.6 are complete (656
> tests passing). This plan adds 10 new CRM-owned models (+ 3 companion child/config tables) covering
> Finance & Billing (1.7), Project & Delivery (1.8), Document & Contract (1.9), Automation & Workflow
> (1.10), Customer Success & Retention (1.11), and Inventory & Vendor Management (1.12).
> All new models extend `TenantNumbered` (the existing abstract base in `apps/crm/models.py`) and
> follow the exact same patterns: `NUMBER_PREFIX`, `unique_together = ("tenant", "number")`, per-tenant
> auto-number in `save()` with 5-retry collision guard, `@login_required` function-based views, full
> CRUD via `crud_list`/`crud_create`/`crud_edit`/`crud_delete` helpers, `TenantModelForm`, and
> one-file-per-commit to `main`. Models without a meaningful auto-number (HealthScore, HealthScoreConfig,
> SignerRecord, WorkflowLog) inherit plain `models.Model` with `tenant` FK directly.

---

## Phase 1 — Models (add to `apps/crm/models.py`)

### 1.7 Finance & Billing Management

- [ ] **`Expense` [EXP-]** — extends `TenantNumbered`; covers deal-related cost logging (Vtiger/Zoho Expense/Dynamics 365).
  Fields:
  - `opportunity` FK→`"crm.Opportunity"` `SET_NULL` nullable (link to deal; null = general expense)
  - `project` FK→`"crm.CrmProject"` `SET_NULL` nullable (link when post-sale project exists)
  - `category` CharField choices `[("travel","Travel"),("meals","Meals"),("software","Software"),("accommodation","Accommodation"),("other","Other")]`
  - `amount` DecimalField max_digits=12 decimal_places=2
  - `currency` FK→`"core.Currency"` `SET_NULL` nullable (spine reuse)
  - `expense_date` DateField
  - `description` TextField blank
  - `receipt` FileField upload_to=`"crm/receipts/%Y/%m/"` blank/null (receipt scan)
  - `status` CharField choices `STATUS_CHOICES=[("draft","Draft"),("submitted","Submitted"),("approved","Approved"),("rejected","Rejected")]` default `"draft"`
  - `submitted_by` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_submitted_expenses"`
  - `approved_by` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_approved_expenses"`
  - Indexes: `(tenant, status)`, `(tenant, expense_date)`, `(tenant, opportunity)`
  - Property `profit_margin` on `Opportunity` (not a field): annotated in the opportunity detail view as `opp.amount − SUM(Expense WHERE status='approved')` — no new table.

### 1.8 Project & Delivery Management (Post-Sale)

- [ ] **`CrmProject` [PRJ-]** — extends `TenantNumbered`; CRM-owned project linked to a won Opportunity (Insightly/Vtiger/Dynamics 365 deal-to-project).
  Fields:
  - `name` CharField max_length=255
  - `account` FK→`"core.Party"` `SET_NULL` nullable related_name `"crm_projects"` (client company)
  - `source_opportunity` FK→`"crm.Opportunity"` `SET_NULL` nullable related_name `"crm_projects"` (set on auto-conversion)
  - `status` CharField choices `STATUS_CHOICES=[("planning","Planning"),("active","Active"),("on_hold","On Hold"),("completed","Completed"),("cancelled","Cancelled")]` default `"planning"`
  - `start_date` DateField null/blank
  - `end_date` DateField null/blank
  - `budget` DecimalField max_digits=14 decimal_places=2 default=0
  - `owner` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_projects"`
  - `description` TextField blank
  - Indexes: `(tenant, status)`, `(tenant, created_at)`
  - Custom action `opportunity_to_project` view (POST, `@require_POST`): triggered from Opportunity detail when stage == `closed_won`; creates `CrmProject` pre-filled from opportunity data.

- [ ] **`CrmMilestone` [MS-]** — extends `TenantNumbered`; tasks/milestones within a project (Gantt/Kanban — Vtiger/Insightly/Bitrix24).
  Fields:
  - `project` FK→`"crm.CrmProject"` `CASCADE` related_name `"milestones"`
  - `title` CharField max_length=255
  - `kind` CharField choices `KIND_CHOICES=[("milestone","Milestone"),("task","Task")]` default `"task"`
  - `status` CharField choices `STATUS_CHOICES=[("not_started","Not Started"),("in_progress","In Progress"),("completed","Completed"),("blocked","Blocked")]` default `"not_started"`
  - `assignee` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_milestones"`
  - `start_date` DateField null/blank
  - `due_date` DateField null/blank
  - `completed_at` DateTimeField null/blank (system-set in `save()` when status→`completed`)
  - `order` PositiveSmallIntegerField default=0 (Kanban column sort order)
  - `parent` FK→`"crm.CrmMilestone"` `SET_NULL` nullable related_name `"subtasks"` (sub-task hierarchy)
  - `description` TextField blank
  - Indexes: `(tenant, project, status)`, `(tenant, due_date)`
  - `save()` override: stamp `completed_at` when status moves to `completed`; clear when re-opened (mirrors `CrmTask.save()`).

- [ ] **`Timesheet` [TS-]** — extends `TenantNumbered`; billable/non-billable time entries per project (Vtiger Timelogs/Dynamics 365/Bitrix24).
  Fields:
  - `project` FK→`"crm.CrmProject"` `CASCADE` related_name `"timesheets"`
  - `milestone` FK→`"crm.CrmMilestone"` `SET_NULL` nullable related_name `"timesheets"`
  - `employee` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_timesheets"` (who logged time)
  - `client` FK→`"core.Party"` `SET_NULL` nullable related_name `"crm_timesheets"` (billing party, denorm from project)
  - `date` DateField
  - `hours` DecimalField max_digits=5 decimal_places=2 (e.g., 7.50)
  - `description` TextField blank
  - `is_billable` BooleanField default=True (billable vs non-billable split — Vtiger/Dynamics 365)
  - `status` CharField choices `STATUS_CHOICES=[("draft","Draft"),("submitted","Submitted"),("approved","Approved"),("rejected","Rejected")]` default `"draft"`
  - `approved_by` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_approved_timesheets"`
  - Indexes: `(tenant, project, date)`, `(tenant, employee, date)`, `(tenant, status)`

### 1.9 Document & Contract Management

- [ ] **`DocTemplate` [TPL-]** — extends `TenantNumbered`; HTML-body templates with Django merge variables (PandaDoc/Zoho Sign/HubSpot CPQ).
  Fields:
  - `name` CharField max_length=255
  - `template_type` CharField choices `TYPE_CHOICES=[("nda","NDA"),("proposal","Proposal"),("contract","Contract"),("quote","Quote"),("receipt","Receipt")]` default `"contract"`
  - `body` TextField (HTML with Django template syntax; e.g. `{{ opportunity.name }}`, `{{ account.name }}`, `{{ today }}`)
  - `is_active` BooleanField default=True
  - `owner` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_doc_templates"`
  - Indexes: `(tenant, template_type)`, `(tenant, is_active)`

- [ ] **`ContractDocument` [CTR-]** — extends `TenantNumbered`; a rendered document instance with e-signature tracking (PandaDoc/Zoho Sign/HubSpot CPQ 2025).
  Fields:
  - `name` CharField max_length=255
  - `template` FK→`"crm.DocTemplate"` `SET_NULL` nullable related_name `"contracts"` (source template)
  - `opportunity` FK→`"crm.Opportunity"` `SET_NULL` nullable related_name `"contracts"`
  - `account` FK→`"core.Party"` `SET_NULL` nullable related_name `"crm_contracts"`
  - `current_version` PositiveSmallIntegerField default=1 (PandaDoc version control)
  - `status` CharField choices `STATUS_CHOICES=[("draft","Draft"),("sent","Sent"),("viewed","Viewed"),("signed","Signed"),("declined","Declined"),("expired","Expired"),("archived","Archived")]` default `"draft"`
  - `body_snapshot` TextField blank (rendered body at time of send, snapshot of merge-resolved HTML)
  - `signed_at` DateTimeField null/blank (system-set when all signers sign)
  - `expires_at` DateTimeField null/blank
  - `owner` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_contracts"`
  - Indexes: `(tenant, status)`, `(tenant, opportunity)`, `(tenant, created_at)`

- [ ] **`SignerRecord` (child, no prefix)** — plain `models.Model`; one row per signer per contract (PandaDoc per-signer signature event tracking).
  Fields:
  - `tenant` FK→`"core.Tenant"` `CASCADE` related_name `"+"` db_index=True
  - `contract` FK→`"crm.ContractDocument"` `CASCADE` related_name `"signers"`
  - `signer_party` FK→`"core.Party"` `SET_NULL` nullable related_name `"crm_signer_records"` (if known Party)
  - `signer_name` CharField max_length=255 (display name)
  - `signer_email` EmailField
  - `token` CharField max_length=64 unique (URL-safe random token for the signing link)
  - `order` PositiveSmallIntegerField default=1 (signing order)
  - `viewed_at` DateTimeField null/blank
  - `signed_at` DateTimeField null/blank
  - `declined_at` DateTimeField null/blank
  - `ip_address` GenericIPAddressField null/blank (recorded on sign action)
  - `created_at` DateTimeField auto_now_add=True
  - Note: No `TenantNumbered` — no meaningful prefix; accessed only through its parent `ContractDocument`.

### 1.10 Automation & Workflow Engine

- [ ] **`WorkflowRule` [WFR-]** — extends `TenantNumbered`; declarative trigger-condition-action rule (Zoho CRM 10-condition rules/HubSpot Workflows/Keap when-then/Creatio BPM).
  Fields:
  - `name` CharField max_length=255
  - `is_active` BooleanField default=True
  - `trigger_entity` CharField choices `ENTITY_CHOICES=[("lead","Lead"),("opportunity","Opportunity"),("case","Case"),("expense","Expense"),("contract","Contract"),("health_score","Health Score")]`
  - `trigger_event` CharField choices `EVENT_CHOICES=[("created","Created"),("updated","Updated"),("status_changed","Status Changed"),("field_value","Field Value Matches"),("date_reached","Date Reached")]`
  - `trigger_field` CharField max_length=100 blank (specific field to watch, e.g. `"stage"`)
  - `trigger_value` CharField max_length=255 blank (value to match, e.g. `"closed_won"`)
  - `conditions` JSONField default=list (list of `{field, operator, value}` dicts; AND logic between items)
  - `actions` JSONField default=list (list of `{type, params}` dicts; `type` in `create_task/send_email/update_field/webhook/start_approval`)
  - `delay_value` PositiveSmallIntegerField null/blank (scheduled/time-delayed action — Zoho CRM/HubSpot)
  - `delay_unit` CharField choices `DELAY_CHOICES=[("minutes","Minutes"),("hours","Hours"),("days","Days")]` blank null
  - `owner` FK→`settings.AUTH_USER_MODEL` `SET_NULL` nullable related_name `"crm_workflow_rules"`
  - Indexes: `(tenant, is_active)`, `(tenant, trigger_entity)`

- [ ] **`WorkflowLog` (companion, no prefix)** — plain `models.Model`; immutable fire-record per rule execution (Zoho CRM/HubSpot/Salesforce Flow action log).
  Fields:
  - `tenant` FK→`"core.Tenant"` `CASCADE` related_name `"+"` db_index=True
  - `rule` FK→`"crm.WorkflowRule"` `SET_NULL` null related_name `"logs"`
  - `record_label` CharField max_length=255 (human label of the triggering record, e.g. `"OPP-00003"`)
  - `fired_at` DateTimeField auto_now_add=True
  - `status` CharField choices `[("success","Success"),("failed","Failed"),("skipped","Skipped")]` default `"success"`
  - `error_msg` TextField blank
  - Note: immutable append-only; no edit/delete view; list + detail only.

- [ ] **`ApprovalRequest` [APR-]** — extends `TenantNumbered`; generic approval gate (Salesforce CPQ/HubSpot CPQ/Zoho discount-approval lock).
  Fields:
  - `rule` FK→`"crm.WorkflowRule"` `SET_NULL` null related_name `"approvals"` (originating rule, or null for manual)
  - `subject` CharField max_length=255 (e.g. `"Approve 25% discount on OPP-00003"`)
  - `record_label` CharField max_length=255 (human label of the locked record)
  - `approver` FK→`settings.AUTH_USER_MODEL` `SET_NULL` null related_name `"crm_approvals_to_action"`
  - `requested_by` FK→`settings.AUTH_USER_MODEL` `SET_NULL` null related_name `"crm_approvals_requested"`
  - `threshold_field` CharField max_length=100 blank (field that triggered the threshold, e.g. `"discount_pct"`)
  - `threshold_value` DecimalField max_digits=10 decimal_places=2 null/blank
  - `status` CharField choices `STATUS_CHOICES=[("pending","Pending"),("approved","Approved"),("rejected","Rejected"),("expired","Expired")]` default `"pending"`
  - `approved_at` DateTimeField null/blank (system-set)
  - `rejected_at` DateTimeField null/blank (system-set)
  - `reason` TextField blank (approver's note)
  - Custom actions: `approve_view` (POST) and `reject_view` (POST) — set status + timestamp, write audit log.
  - Indexes: `(tenant, status)`, `(tenant, approver)`, `(tenant, created_at)`

### 1.11 Customer Success & Retention

- [ ] **`OnboardingPlan` [CS-]** — extends `TenantNumbered`; per-client step checklist (Gainsight Playbooks/ChurnZero SuccessPlays/HubSpot Customer Portal).
  Fields:
  - `account` FK→`"core.Party"` `SET_NULL` null related_name `"crm_onboarding_plans"` (client)
  - `name` CharField max_length=255 (e.g. `"Acme Corp — 90-Day Onboarding"`)
  - `status` CharField choices `STATUS_CHOICES=[("active","Active"),("completed","Completed"),("on_hold","On Hold"),("cancelled","Cancelled")]` default `"active"`
  - `target_date` DateField null/blank
  - `completed_at` DateTimeField null/blank (system-set when all steps completed)
  - `owner` FK→`settings.AUTH_USER_MODEL` `SET_NULL` null related_name `"crm_onboarding_plans"`
  - `description` TextField blank
  - Property `progress_pct`: `(completed steps / total steps) * 100` — computed in view/template, not stored.
  - Indexes: `(tenant, account)`, `(tenant, status)`

- [ ] **`OnboardingStep` (child, no prefix)** — plain `models.Model`; ordered checklist item within an OnboardingPlan (Gainsight/Totango 30/60/90-day steps).
  Fields:
  - `tenant` FK→`"core.Tenant"` `CASCADE` related_name `"+"` db_index=True
  - `plan` FK→`"crm.OnboardingPlan"` `CASCADE` related_name `"steps"`
  - `order` PositiveSmallIntegerField default=0
  - `title` CharField max_length=255
  - `description` TextField blank
  - `assignee` FK→`settings.AUTH_USER_MODEL` `SET_NULL` null related_name `"crm_onboarding_steps"`
  - `due_date` DateField null/blank
  - `completed_at` DateTimeField null/blank (system-set on step completion action)
  - `created_at` DateTimeField auto_now_add=True
  - Note: CRUD surfaced inline on the `OnboardingPlan` detail page (add/complete/delete step actions); no separate list page.

- [ ] **`HealthScore` [HS-]** — plain `models.Model` with `tenant` FK; one score per account per tenant (Gainsight Scorecards/ChurnZero ChurnScore/Totango composite health).
  Fields:
  - `tenant` FK→`"core.Tenant"` `CASCADE` related_name `"+"` db_index=True
  - `account` FK→`"core.Party"` `CASCADE` related_name `"crm_health_scores"`
  - `score` PositiveSmallIntegerField (0–100, `MaxValueValidator(100)`)
  - `tier` CharField choices `[("green","Green — Healthy"),("yellow","Yellow — At Risk"),("red","Red — Critical")]`
  - `breakdown` JSONField default=dict (per-signal sub-scores: `{payments: 80, tickets: 60, nps: 90, tasks: 70}`)
  - `computed_at` DateTimeField (system-set by `compute_health_score(party, tenant)` service function)
  - `updated_at` DateTimeField auto_now=True
  - `unique_together = ("tenant", "account")` — one row per account; recomputed in-place.
  - Service function `compute_health_score(party, tenant)`: reads `HealthScoreConfig` weights, queries `core.Invoice`+`Payment`, `crm.Case`, `crm.Survey`, updates/creates the `HealthScore` row. Called from `HealthScore` detail view "Recompute" action and signal hooks.
  - Indexes: `(tenant, tier)`, `(tenant, computed_at)`

- [ ] **`HealthScoreConfig` (companion, no prefix)** — plain `models.Model`; one row per tenant with configurable signal weights (Gainsight Scorecard measure weights).
  Fields:
  - `tenant` OneToOneField→`"core.Tenant"` `CASCADE` related_name `"crm_health_config"`
  - `weight_payments` DecimalField max_digits=5 decimal_places=2 default=25.0 (payment punctuality weight %)
  - `weight_tickets` DecimalField max_digits=5 decimal_places=2 default=25.0 (open/overdue tickets weight %)
  - `weight_nps` DecimalField max_digits=5 decimal_places=2 default=25.0 (NPS survey score weight %)
  - `weight_tasks` DecimalField max_digits=5 decimal_places=2 default=25.0 (task completion weight %)
  - `red_threshold` PositiveSmallIntegerField default=40 (score below = Red tier)
  - `yellow_threshold` PositiveSmallIntegerField default=70 (score below = Yellow tier)
  - `updated_at` DateTimeField auto_now=True
  - Note: singleton per tenant; create-or-update in seeder and via `crm:health_config_edit` view.

- [ ] **`Survey` [NPS-]** — extends `TenantNumbered`; NPS/CSAT/CES response record (Gainsight NPS/CSAT engine/ChurnZero/HubSpot Service Hub).
  Fields:
  - `account` FK→`"core.Party"` `SET_NULL` null related_name `"crm_surveys"` (surveyed company)
  - `contact` FK→`"core.Party"` `SET_NULL` null related_name `"crm_survey_contacts"` (respondent contact)
  - `survey_type` CharField choices `TYPE_CHOICES=[("nps","NPS"),("csat","CSAT"),("ces","CES")]` default `"nps"`
  - `trigger` CharField choices `TRIGGER_CHOICES=[("manual","Manual"),("post_close","Post Close Won"),("post_ticket","Post Ticket Close"),("scheduled","Scheduled")]` default `"manual"`
  - `related_case` FK→`"crm.Case"` `SET_NULL` null related_name `"crm_surveys"` (for `post_ticket` trigger)
  - `score` PositiveSmallIntegerField null/blank (0–10 NPS; 1–5 CSAT/CES; `MaxValueValidator(10)`)
  - `feedback_text` TextField blank
  - `classification` CharField choices `[("promoter","Promoter"),("passive","Passive"),("detractor","Detractor")]` blank (auto-set by `save()` for NPS: 9–10=promoter, 7–8=passive, 0–6=detractor)
  - `sent_at` DateTimeField (when the survey was dispatched)
  - `responded_at` DateTimeField null/blank (when the response was recorded)
  - `save()` override: auto-compute `classification` from `score` + `survey_type` on save.
  - Indexes: `(tenant, survey_type)`, `(tenant, account)`, `(tenant, sent_at)`

### 1.12 Inventory & Vendor Management

- [ ] **`PartnerPortalAccess` [PRT-]** — extends `TenantNumbered`; external partner login mapping (Zoho Inventory Vendor Portal/Bitrix24 extranet/Vtiger customer portal).
  Fields:
  - `partner_party` FK→`"core.Party"` `SET_NULL` null related_name `"crm_portal_accesses"` (role=partner)
  - `portal_user` OneToOneField→`settings.AUTH_USER_MODEL` `SET_NULL` null related_name `"crm_portal_access"` (restricted portal login account)
  - `access_level` CharField choices `ACCESS_CHOICES=[("read_only","Read Only"),("lead_register","Lead Registration"),("full","Full Access")]` default `"read_only"`
  - `can_view_stock` BooleanField default=False
  - `can_register_leads` BooleanField default=False
  - `invited_at` DateTimeField auto_now_add=True
  - `accepted_at` DateTimeField null/blank (system-set when partner activates)
  - `is_active` BooleanField default=True
  - Note: the `/portal/` URL prefix with partner-scoped views (PO list, stock widget) lives in `apps/crm/views.py` under a `portal_` prefix; no separate app needed.
  - Indexes: `(tenant, is_active)`, `(tenant, partner_party)`

- [ ] **1.12 Service views — no new models needed** (reuses spine):
  - `crm_po_list` / `crm_po_detail` / `crm_po_create` — CRM-scoped views over `core.PurchaseOrder` + `core.PurchaseOrderLine` (vendor role Party + Item); these create POs in the spine without a new table.
  - `portal_dashboard` / `portal_po_list` / `portal_stock` — Partner portal read-only views (filtered by `partner_party`, stock derived from `core.StockMove` aggregation).
  - Stock deduction service: `post_stock_deduction(invoice, tenant)` — creates `core.StockMove` rows for each line item when invoice kind=receivable and status moves to `paid`; called from a future Invoice payment view.

---

## Phase 2 — Migration

- [ ] Run `python manage.py makemigrations crm` → generates `apps/crm/migrations/0005_expense_crmproject_crmmilestone_timesheet_doctemplate_contractdocument_signerrecord_workflowrule_workflowlog_approvalrequest_onboardingplan_onboardingstep_healthscore_healthscoreconfig_survey_partnerportalaccess.py` (one migration file, auto-named)
- [ ] Verify migration SQL with `python manage.py sqlmigrate crm 0005` — confirm all FK references, indexes, and `unique_together` constraints render correctly
- [ ] Run `python manage.py migrate` — apply to `nav_erp` database; confirm zero errors

---

## Phase 3 — Forms (`apps/crm/forms.py`)

Add one `TenantModelForm` per new primary model. Exclude `tenant`, `number` (auto), and all system-set fields:

- [ ] **`ExpenseForm`** — fields: `opportunity`, `project`, `category`, `amount`, `currency`, `expense_date`, `description`, `receipt`, `status`, `submitted_by`, `approved_by`
- [ ] **`CrmProjectForm`** — fields: `name`, `account`, `source_opportunity`, `status`, `start_date`, `end_date`, `budget`, `owner`, `description`
- [ ] **`CrmMilestoneForm`** — fields: `project`, `title`, `kind`, `status`, `assignee`, `start_date`, `due_date`, `order`, `parent`, `description`; `__init__` scopes `project` and `parent` querysets to `tenant`
- [ ] **`TimesheetForm`** — fields: `project`, `milestone`, `employee`, `client`, `date`, `hours`, `description`, `is_billable`, `status`, `approved_by`; `__init__` scopes `project`, `milestone`, `client` to `tenant`
- [ ] **`DocTemplateForm`** — fields: `name`, `template_type`, `body`, `is_active`, `owner`
- [ ] **`ContractDocumentForm`** — fields: `name`, `template`, `opportunity`, `account`, `current_version`, `status`, `body_snapshot`, `expires_at`, `owner`; `__init__` scopes `template`, `opportunity`, `account` to `tenant`
- [ ] **`SignerRecordForm`** — fields: `signer_party`, `signer_name`, `signer_email`, `order`; used inline on ContractDocument detail
- [ ] **`WorkflowRuleForm`** — fields: `name`, `is_active`, `trigger_entity`, `trigger_event`, `trigger_field`, `trigger_value`, `conditions`, `actions`, `delay_value`, `delay_unit`, `owner`; use `forms.JSONField` (Textarea widget) for `conditions`/`actions`
- [ ] **`ApprovalRequestForm`** — fields: `rule`, `subject`, `record_label`, `approver`, `requested_by`, `threshold_field`, `threshold_value`; `__init__` scopes `rule`, `approver`, `requested_by` to `tenant`
- [ ] **`OnboardingPlanForm`** — fields: `account`, `name`, `status`, `target_date`, `owner`, `description`; `__init__` scopes `account` to `tenant`
- [ ] **`OnboardingStepForm`** — fields: `plan`, `order`, `title`, `description`, `assignee`, `due_date`; `__init__` scopes `plan` to `tenant`
- [ ] **`HealthScoreConfigForm`** — fields: `weight_payments`, `weight_tickets`, `weight_nps`, `weight_tasks`, `red_threshold`, `yellow_threshold`; no TenantModelForm needed (singleton); plain `ModelForm`
- [ ] **`SurveyForm`** — fields: `account`, `contact`, `survey_type`, `trigger`, `related_case`, `score`, `feedback_text`, `sent_at`; `__init__` scopes `account`, `contact`, `related_case` to `tenant`; exclude `classification` (system-set) and `responded_at`
- [ ] **`PartnerPortalAccessForm`** — fields: `partner_party`, `portal_user`, `access_level`, `can_view_stock`, `can_register_leads`, `is_active`; `__init__` scopes `partner_party` to `tenant`

---

## Phase 4 — Views (`apps/crm/views.py`)

All views: `@login_required`, `tenant=request.tenant` filter everywhere, full CRUD via `crud_list`/`crud_create`/`crud_edit`/`crud_delete` helpers + `write_audit_log`. Pattern mirrors existing `lead_list`/`lead_detail`/etc.

### 1.7 — Expense views
- [ ] `expense_list` — `crud_list(Expense.objects.filter(tenant=...).select_related("opportunity","project","submitted_by","approved_by","currency"))` with search `["number","description","opportunity__name"]`; filters `[("status","status",False),("category","category",False)]`; extra_context `status_choices`, `category_choices`
- [ ] `expense_create` — `crud_create(ExpenseForm, "crm/expense_form.html", "crm:expense_list")`
- [ ] `expense_detail` — `get_object_or_404(Expense, pk=pk, tenant=...)` + context with linked opportunity profit margin annotation
- [ ] `expense_edit` — `crud_edit(Expense, pk, ExpenseForm, "crm/expense_form.html", "crm:expense_list")`
- [ ] `expense_delete` — `@require_POST`, `crud_delete(Expense, pk, "crm:expense_list")`
- [ ] `expense_approve` (custom POST action, `@require_POST`, `@login_required`) — sets `status="approved"`, `approved_by=request.user`; write_audit_log; redirect to `crm:expense_detail`
- [ ] `expense_reject` (custom POST action, `@require_POST`, `@login_required`) — sets `status="rejected"`; write_audit_log; redirect to `crm:expense_detail`

### 1.8 — CrmProject views
- [ ] `crmproject_list` — filter `(tenant, status)`; search `["number","name","account__name"]`; extra_context `status_choices`; select_related `account`, `owner`, `source_opportunity`
- [ ] `crmproject_create` — `crud_create(CrmProjectForm, ...)`
- [ ] `crmproject_detail` — includes milestone list (`milestones.filter(tenant=..., project=obj).order_by("order","due_date")`), timesheet billable total, expense total; profit-margin display
- [ ] `crmproject_edit` — `crud_edit(...)`
- [ ] `crmproject_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `opportunity_to_project` (custom POST) — `@require_POST`, `@login_required`; called from Opportunity detail when `stage=="closed_won"`; creates `CrmProject` from opportunity data (idempotent guard: skip if `CrmProject.objects.filter(source_opportunity=opp, tenant=tenant).exists()`); write_audit_log; redirect to `crm:crmproject_detail`

### 1.8 — CrmMilestone views
- [ ] `crmmilestone_list` — filter `(project [int FK], status)`; search `["number","title"]`; extra_context `status_choices`, `projects` queryset (for filter dropdown); select_related `project`, `assignee`
- [ ] `crmmilestone_create` — `crud_create(CrmMilestoneForm, ...)`
- [ ] `crmmilestone_detail` — sub-task list (`CrmMilestone.objects.filter(parent=obj, tenant=...)`)
- [ ] `crmmilestone_edit` — `crud_edit(...)`
- [ ] `crmmilestone_delete` — `@require_POST`, `crud_delete(...)`

### 1.8 — Timesheet views
- [ ] `timesheet_list` — filter `(project [int FK], status, employee [int FK])`; search `["number","description","employee__username"]`; extra_context `status_choices`, `projects`, `employees`; select_related `project`, `employee`, `milestone`
- [ ] `timesheet_create` — `crud_create(TimesheetForm, ...)`
- [ ] `timesheet_detail` — show project + billable flag + approval chain
- [ ] `timesheet_edit` — `crud_edit(...)`
- [ ] `timesheet_delete` — `@require_POST`, `crud_delete(...)`

### 1.9 — DocTemplate views
- [ ] `doctemplate_list` — filter `(template_type, is_active)`; search `["number","name"]`; extra_context `type_choices`
- [ ] `doctemplate_create` — `crud_create(DocTemplateForm, ...)`
- [ ] `doctemplate_detail` — show body HTML (escaped), related contracts count
- [ ] `doctemplate_edit` — `crud_edit(...)`
- [ ] `doctemplate_delete` — `@require_POST`, `crud_delete(...)`

### 1.9 — ContractDocument views
- [ ] `contractdocument_list` — filter `(status, opportunity [int FK])`; search `["number","name","account__name"]`; extra_context `status_choices`; select_related `template`, `opportunity`, `account`, `owner`
- [ ] `contractdocument_create` — `crud_create(ContractDocumentForm, ...)`
- [ ] `contractdocument_detail` — includes `signers` list (`SignerRecord.objects.filter(contract=obj).order_by("order")`)
- [ ] `contractdocument_edit` — `crud_edit(...)`
- [ ] `contractdocument_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `contractdocument_add_signer` (custom POST) — `@require_POST`, `@login_required`; creates `SignerRecord` with random `token` (use `secrets.token_urlsafe(32)`); redirect to detail
- [ ] `contractdocument_remove_signer` (custom POST) — `@require_POST`, `@login_required`; deletes `SignerRecord` by pk (tenant-scoped via contract FK); redirect to detail
- [ ] `sign_document` (public GET+POST, NO `@login_required`) — looks up `SignerRecord` by `token`; GET renders the signing page with body_snapshot; POST records `signed_at` + `ip_address`; if all signers signed, sets parent `ContractDocument.status="signed"` + `signed_at`. Security note: token lookup must use `get_object_or_404` and constant-time comparison (`hmac.compare_digest`) is not required here since tokens are sufficiently random.

### 1.10 — WorkflowRule views
- [ ] `workflowrule_list` — filter `(is_active, trigger_entity)`; search `["number","name"]`; extra_context `entity_choices`, `event_choices`; select_related `owner`
- [ ] `workflowrule_create` — `crud_create(WorkflowRuleForm, ...)`
- [ ] `workflowrule_detail` — show conditions/actions JSON rendered as formatted table; related `WorkflowLog` latest 20
- [ ] `workflowrule_edit` — `crud_edit(...)`
- [ ] `workflowrule_delete` — `@require_POST`, `crud_delete(...)`

### 1.10 — WorkflowLog views (read-only)
- [ ] `workflowlog_list` — `WorkflowLog.objects.filter(tenant=...)` filter `(status, rule [int FK])`; search `["record_label","error_msg"]`; no create/edit/delete (append-only); extra_context `status_choices`, `rules`

### 1.10 — ApprovalRequest views
- [ ] `approvalrequest_list` — filter `(status, approver [int FK])`; search `["number","subject","record_label"]`; extra_context `status_choices`, `approvers`; select_related `approver`, `requested_by`
- [ ] `approvalrequest_create` — `crud_create(ApprovalRequestForm, ...)`
- [ ] `approvalrequest_detail` — show full approval metadata + approve/reject buttons (conditional on `status=="pending"`)
- [ ] `approvalrequest_edit` — `crud_edit(...)` (editable only when `pending`)
- [ ] `approvalrequest_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `approvalrequest_approve` (custom POST) — `@require_POST`, `@login_required`; sets `status="approved"`, `approved_at=now()`; write_audit_log; redirect to detail
- [ ] `approvalrequest_reject` (custom POST) — `@require_POST`, `@login_required`; sets `status="rejected"`, `rejected_at=now()`; write_audit_log; redirect to detail

### 1.11 — OnboardingPlan views
- [ ] `onboardingplan_list` — filter `(status, account [int FK])`; search `["number","name","account__name"]`; extra_context `status_choices`, `accounts`; select_related `account`, `owner`
- [ ] `onboardingplan_create` — `crud_create(OnboardingPlanForm, ...)`
- [ ] `onboardingplan_detail` — includes ordered steps `plan.steps.order_by("order")`; progress_pct annotation; inline add/complete/delete step actions
- [ ] `onboardingplan_edit` — `crud_edit(...)`
- [ ] `onboardingplan_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `onboardingstep_add` (custom POST) — `@require_POST`; creates `OnboardingStep`; redirect to plan detail
- [ ] `onboardingstep_complete` (custom POST) — `@require_POST`; sets `completed_at=now()`; if all steps complete, sets plan `completed_at`; redirect to plan detail
- [ ] `onboardingstep_delete` (custom POST) — `@require_POST`; deletes step (tenant-scoped via `plan__tenant`); redirect to plan detail

### 1.11 — HealthScore views
- [ ] `healthscore_list` — filter `(tier)`; search `["account__name"]`; extra_context `tier_choices`; select_related `account`; order_by `score` ascending (lowest = most at-risk first)
- [ ] `healthscore_detail` — breakdown JSONField display; Recompute button (POST → `recompute_health_score`)
- [ ] `healthscore_create` — `crud_create(...)` (manual score entry)
- [ ] `healthscore_edit` — `crud_edit(...)` (manual override)
- [ ] `healthscore_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `recompute_health_score` (custom POST) — `@require_POST`; calls `compute_health_score(party, tenant)` service function; redirect to `crm:healthscore_detail`
- [ ] `health_config_edit` (GET+POST) — GET: render HealthScoreConfig form for `tenant`; POST: update weights; `get_or_create` for the config singleton; redirect to `crm:healthscore_list`

### 1.11 — Survey views
- [ ] `survey_list` — filter `(survey_type, classification, account [int FK])`; search `["number","feedback_text","account__name"]`; extra_context `type_choices`, `classification_choices`, `accounts`; select_related `account`, `contact`
- [ ] `survey_create` — `crud_create(SurveyForm, ...)`
- [ ] `survey_detail` — show score, classification badge, feedback, related case link
- [ ] `survey_edit` — `crud_edit(...)`
- [ ] `survey_delete` — `@require_POST`, `crud_delete(...)`
- [ ] `survey_respond` (custom GET+POST, NO `@login_required`) — public survey response endpoint; GET renders the score form; POST records `score`, `feedback_text`, `responded_at`; triggers `classification` auto-set via `save()`.

### 1.12 — PartnerPortalAccess views (internal admin)
- [ ] `partnerportalaccess_list` — filter `(is_active, access_level)`; search `["number","partner_party__name","portal_user__username"]`; extra_context `access_choices`; select_related `partner_party`, `portal_user`
- [ ] `partnerportalaccess_create` — `crud_create(PartnerPortalAccessForm, ...)`
- [ ] `partnerportalaccess_detail` — show access level, flags, portal user link
- [ ] `partnerportalaccess_edit` — `crud_edit(...)`
- [ ] `partnerportalaccess_delete` — `@require_POST`, `crud_delete(...)`

### 1.12 — CRM Purchase Order views (CRM-scoped UI over spine `core.PurchaseOrder`)
- [ ] `crm_po_list` — `core.PurchaseOrder.objects.filter(tenant=request.tenant).select_related("vendor")` with search + `(status, vendor [int FK])` filters; extra_context `status_choices`, `vendors`
- [ ] `crm_po_create` — direct `core.PurchaseOrderForm` (or inline form); creates `core.PurchaseOrder`+`core.PurchaseOrderLine` rows; tenant-scoped; write_audit_log
- [ ] `crm_po_detail` — PO detail with line items; "Generate Bill" action button (POST)
- [ ] `crm_po_generate_bill` (custom POST) — creates `core.Invoice(kind="payable")` from PO lines; redirect to po detail
- [ ] `crm_po_delete` — `@require_POST`, deletes `core.PurchaseOrder`

### 1.12 — Partner Portal views (public-ish, permission check via `PartnerPortalAccess.is_active`)
- [ ] `portal_dashboard` — `@login_required`; checks `PartnerPortalAccess.objects.get(portal_user=request.user, tenant=..., is_active=True)`; renders a simplified dashboard
- [ ] `portal_po_list` — partner sees only POs where `vendor__crm_portal_accesses__portal_user=request.user`
- [ ] `portal_stock` — requires `can_view_stock=True`; renders `core.StockMove` aggregated on-hand per Item; no edit

---

## Phase 5 — URLs (`apps/crm/urls.py`)

Append to the existing `urlpatterns` (keep `app_name = "crm"`):

- [ ] **Expenses (1.7):** `expenses/`, `expenses/add/`, `expenses/<int:pk>/`, `expenses/<int:pk>/edit/`, `expenses/<int:pk>/delete/`, `expenses/<int:pk>/approve/`, `expenses/<int:pk>/reject/` → names: `expense_list`, `expense_create`, `expense_detail`, `expense_edit`, `expense_delete`, `expense_approve`, `expense_reject`
- [ ] **CrmProjects (1.8):** `projects/`, `projects/add/`, `projects/<int:pk>/`, `projects/<int:pk>/edit/`, `projects/<int:pk>/delete/` → names: `crmproject_list`, `crmproject_create`, `crmproject_detail`, `crmproject_edit`, `crmproject_delete`; plus `opportunities/<int:pk>/to-project/` → `opportunity_to_project`
- [ ] **CrmMilestones (1.8):** `milestones/`, `milestones/add/`, `milestones/<int:pk>/`, `milestones/<int:pk>/edit/`, `milestones/<int:pk>/delete/` → names: `crmmilestone_list`, `crmmilestone_create`, `crmmilestone_detail`, `crmmilestone_edit`, `crmmilestone_delete`
- [ ] **Timesheets (1.8):** `timesheets/`, `timesheets/add/`, `timesheets/<int:pk>/`, `timesheets/<int:pk>/edit/`, `timesheets/<int:pk>/delete/` → names: `timesheet_list`, `timesheet_create`, `timesheet_detail`, `timesheet_edit`, `timesheet_delete`
- [ ] **DocTemplates (1.9):** `doc-templates/`, `doc-templates/add/`, `doc-templates/<int:pk>/`, `doc-templates/<int:pk>/edit/`, `doc-templates/<int:pk>/delete/` → names: `doctemplate_list`, `doctemplate_create`, `doctemplate_detail`, `doctemplate_edit`, `doctemplate_delete`
- [ ] **ContractDocuments (1.9):** `contracts/`, `contracts/add/`, `contracts/<int:pk>/`, `contracts/<int:pk>/edit/`, `contracts/<int:pk>/delete/`, `contracts/<int:pk>/add-signer/`, `contracts/<int:pk>/remove-signer/<int:signer_pk>/`, `sign/<str:token>/` → names: `contractdocument_list`, `contractdocument_create`, `contractdocument_detail`, `contractdocument_edit`, `contractdocument_delete`, `contractdocument_add_signer`, `contractdocument_remove_signer`, `sign_document`
- [ ] **WorkflowRules (1.10):** `workflows/`, `workflows/add/`, `workflows/<int:pk>/`, `workflows/<int:pk>/edit/`, `workflows/<int:pk>/delete/` → names: `workflowrule_list`, `workflowrule_create`, `workflowrule_detail`, `workflowrule_edit`, `workflowrule_delete`
- [ ] **WorkflowLogs (1.10):** `workflow-logs/`, `workflow-logs/<int:pk>/` → names: `workflowlog_list`, `workflowlog_detail` (read-only; no create/edit/delete URL)
- [ ] **ApprovalRequests (1.10):** `approvals/`, `approvals/add/`, `approvals/<int:pk>/`, `approvals/<int:pk>/edit/`, `approvals/<int:pk>/delete/`, `approvals/<int:pk>/approve/`, `approvals/<int:pk>/reject/` → names: `approvalrequest_list`, `approvalrequest_create`, `approvalrequest_detail`, `approvalrequest_edit`, `approvalrequest_delete`, `approvalrequest_approve`, `approvalrequest_reject`
- [ ] **OnboardingPlans (1.11):** `onboarding/`, `onboarding/add/`, `onboarding/<int:pk>/`, `onboarding/<int:pk>/edit/`, `onboarding/<int:pk>/delete/`, `onboarding/<int:pk>/add-step/`, `onboarding/steps/<int:step_pk>/complete/`, `onboarding/steps/<int:step_pk>/delete/` → names: `onboardingplan_list`, `onboardingplan_create`, `onboardingplan_detail`, `onboardingplan_edit`, `onboardingplan_delete`, `onboardingstep_add`, `onboardingstep_complete`, `onboardingstep_delete`
- [ ] **HealthScores (1.11):** `health-scores/`, `health-scores/add/`, `health-scores/<int:pk>/`, `health-scores/<int:pk>/edit/`, `health-scores/<int:pk>/delete/`, `health-scores/<int:pk>/recompute/`, `health-config/` → names: `healthscore_list`, `healthscore_create`, `healthscore_detail`, `healthscore_edit`, `healthscore_delete`, `recompute_health_score`, `health_config_edit`
- [ ] **Surveys (1.11):** `surveys/`, `surveys/add/`, `surveys/<int:pk>/`, `surveys/<int:pk>/edit/`, `surveys/<int:pk>/delete/`, `surveys/<str:token>/respond/` → names: `survey_list`, `survey_create`, `survey_detail`, `survey_edit`, `survey_delete`, `survey_respond` (Note: `survey_respond` uses a unique token, not a pk, for public access)
- [ ] **PartnerPortalAccess (1.12):** `partner-portal/`, `partner-portal/add/`, `partner-portal/<int:pk>/`, `partner-portal/<int:pk>/edit/`, `partner-portal/<int:pk>/delete/` → names: `partnerportalaccess_list`, `partnerportalaccess_create`, `partnerportalaccess_detail`, `partnerportalaccess_edit`, `partnerportalaccess_delete`
- [ ] **CRM PO views (1.12):** `purchase-orders/`, `purchase-orders/add/`, `purchase-orders/<int:pk>/`, `purchase-orders/<int:pk>/delete/`, `purchase-orders/<int:pk>/generate-bill/` → names: `crm_po_list`, `crm_po_create`, `crm_po_detail`, `crm_po_delete`, `crm_po_generate_bill`
- [ ] **Partner Portal views (1.12):** `portal/`, `portal/orders/`, `portal/stock/` → names: `portal_dashboard`, `portal_po_list`, `portal_stock`

---

## Phase 6 — Admin (`apps/crm/admin.py`)

Add `@admin.register` classes for each new primary model (mirror existing pattern — `list_display`, `list_filter`, `search_fields`, `readonly_fields`, `list_select_related`):

- [ ] `ExpenseAdmin` — list_display: `number, category, amount, status, submitted_by, opportunity, tenant`; readonly: `number, created_at, updated_at`
- [ ] `CrmProjectAdmin` — list_display: `number, name, account, status, start_date, end_date, owner, tenant`; readonly: `number, created_at, updated_at`
- [ ] `CrmMilestoneAdmin` — list_display: `number, title, project, kind, status, due_date, assignee, tenant`; readonly: `number, completed_at, created_at, updated_at`
- [ ] `TimesheetAdmin` — list_display: `number, project, employee, date, hours, is_billable, status, tenant`; readonly: `number, created_at, updated_at`
- [ ] `DocTemplateAdmin` — list_display: `number, name, template_type, is_active, owner, tenant`; readonly: `number, created_at, updated_at`
- [ ] `ContractDocumentAdmin` — list_display: `number, name, template, status, current_version, owner, tenant`; readonly: `number, signed_at, created_at, updated_at`
- [ ] `SignerRecordAdmin` — list_display: `contract, signer_name, signer_email, order, signed_at, tenant`; readonly: `token, viewed_at, signed_at, declined_at, ip_address, created_at`
- [ ] `WorkflowRuleAdmin` — list_display: `number, name, trigger_entity, trigger_event, is_active, owner, tenant`; readonly: `number, created_at, updated_at`
- [ ] `WorkflowLogAdmin` — list_display: `rule, record_label, status, fired_at, tenant`; readonly: all fields (append-only)
- [ ] `ApprovalRequestAdmin` — list_display: `number, subject, approver, status, created_at, tenant`; readonly: `number, approved_at, rejected_at, created_at`
- [ ] `OnboardingPlanAdmin` — list_display: `number, name, account, status, target_date, owner, tenant`; readonly: `number, completed_at, created_at, updated_at`
- [ ] `OnboardingStepAdmin` — list_display: `plan, order, title, assignee, due_date, completed_at, tenant`; readonly: `completed_at, created_at`; raw_id_fields: `plan`
- [ ] `HealthScoreAdmin` — list_display: `account, score, tier, computed_at, tenant`; readonly: `computed_at, updated_at`
- [ ] `HealthScoreConfigAdmin` — list_display: `tenant, weight_payments, weight_tickets, weight_nps, weight_tasks, red_threshold, yellow_threshold`; readonly: `updated_at`
- [ ] `SurveyAdmin` — list_display: `number, account, survey_type, score, classification, sent_at, responded_at, tenant`; readonly: `number, classification, responded_at, created_at`
- [ ] `PartnerPortalAccessAdmin` — list_display: `number, partner_party, portal_user, access_level, is_active, invited_at, tenant`; readonly: `number, invited_at, accepted_at, created_at, updated_at`

---

## Phase 7 — Seeder (extend `apps/crm/management/commands/seed_crm.py`)

- [ ] Add idempotency guard at the top of each new model block: `if Expense.objects.filter(tenant=tenant).exists(): continue` (per model)
- [ ] **Expense seed data** — 3 expenses per tenant (one travel/meals/software), linked to existing Opportunities; one `approved`, one `submitted`, one `draft`; use `get_or_create` pattern with `number` check
- [ ] **CrmProject seed data** — 2 projects per tenant: one `active` linked to the `closed_won` Opportunity (`source_opportunity`), one `planning` linked to an account; include milestones (see below)
- [ ] **CrmMilestone seed data** — 3 milestones per project (kickoff/development/delivery) with varying `status` values; one `completed` (with `completed_at` set), one `in_progress`, one `not_started`
- [ ] **Timesheet seed data** — 4 timesheet entries per project across 2 employees; mix of `billable=True` and `billable=False`; statuses: `approved`, `submitted`, `draft`
- [ ] **DocTemplate seed data** — 2 templates per tenant: one `contract` type, one `proposal` type; include sample merge-variable body (`{{ account.name }}`, `{{ opportunity.amount }}`, `{{ today }}`)
- [ ] **ContractDocument seed data** — 2 contracts per tenant; one `signed`, one `draft`; linked to existing Opportunities; include 2 `SignerRecord` rows per contract (one signed, one pending)
- [ ] **WorkflowRule seed data** — 2 rules per tenant: one `is_active=True` for `opportunity` / `status_changed` / `closed_won` → `create_task`; one `is_active=False` for `case` / `created` → `send_email`; include sample `conditions` and `actions` JSONField values
- [ ] **ApprovalRequest seed data** — 2 approval requests per tenant: one `pending`, one `approved`; linked to the active WorkflowRule
- [ ] **OnboardingPlan seed data** — 1 plan per tenant with 3 ordered steps (kickoff/training/go-live); one step `completed`, others pending
- [ ] **HealthScoreConfig seed data** — `get_or_create` one config per tenant (default weights 25/25/25/25)
- [ ] **HealthScore seed data** — 1 HealthScore per existing Account Party (max 3); random scores in different tiers; `breakdown` JSONField with per-signal data
- [ ] **Survey seed data** — 3 surveys per tenant: one NPS (promoter), one CSAT (post-ticket, linked to existing Case), one NPS (detractor); `responded_at` set on completed ones
- [ ] **PartnerPortalAccess seed data** — 1 entry per tenant (read-only, `is_active=True`, linked to a `partner`-role Party or the first organization Party)
- [ ] After seeding, print: `"New 1.7–1.12 entities seeded. Login as admin_acme / password to verify."` and re-print the standard superuser-has-no-tenant warning

---

## Phase 8 — Wire-up

### `apps/core/navigation.py` — LIVE_LINKS additions

Add the following entries to the `LIVE_LINKS` dict (exact NavERP.md bullet text as keys):

- [ ] **Sub-module 1.7** — Finance & Billing Management:
  ```python
  "1.7": {
      "Invoicing": "crm:expense_list",          # surfaces expense tracking; core invoice views are in core/accounting
      "Payment Tracking": "crm:approvalrequest_list",  # approval-gating ties to payment/discount approval
      "Expense Tracking": "crm:expense_list",   # bullet — deal-related expense log
  },
  ```
  Note: "Invoicing" and "Payment Tracking" bullets point to the most relevant CRM-owned routes. Full invoice/payment CRUD lives in `core` (spine) and will be wired from the Accounting module; these are CRM-scope entry points.

- [ ] **Sub-module 1.8** — Project & Delivery Management (Post-Sale):
  ```python
  "1.8": {
      "Projects": "crm:crmproject_list",         # bullet — auto deal-to-project conversion list
      "Time Tracking": "crm:timesheet_list",     # bullet — billable/non-billable timesheets
      "Resource Allocation": "crm:timesheet_list",  # bullet — workload view (filtered by employee from timesheet list)
  },
  ```

- [ ] **Sub-module 1.9** — Document & Contract Management:
  ```python
  "1.9": {
      "E-Signatures": "crm:contractdocument_list",   # bullet — contract + signer tracking
      "Document Generation": "crm:doctemplate_list", # bullet — merge-variable templates
      "File Repository": "crm:contractdocument_list",  # bullet — contract documents + versions
  },
  ```

- [ ] **Sub-module 1.10** — Automation & Workflow Engine:
  ```python
  "1.10": {
      "Trigger-Based Actions (If This, Then That)": "crm:workflowrule_list",  # bullet
      "Approval Processes": "crm:approvalrequest_list",  # bullet
      "Webhooks": "crm:workflowrule_list",        # bullet — webhook is an action type in WorkflowRule
  },
  ```

- [ ] **Sub-module 1.11** — Customer Success & Retention:
  ```python
  "1.11": {
      "Onboarding Pipelines": "crm:onboardingplan_list",   # bullet
      "Health Scoring": "crm:healthscore_list",             # bullet
      "Surveys & Feedback (NPS)": "crm:survey_list",        # bullet
  },
  ```

- [ ] **Sub-module 1.12** — Inventory & Vendor Management:
  ```python
  "1.12": {
      "Purchase Orders (POs)": "crm:crm_po_list",           # bullet
      "Stock Tracking": "crm:portal_stock",                  # bullet — stock deduction + alerts view
      "Vendor/Partner Portal": "crm:partnerportalaccess_list",  # bullet — portal access management
  },
  ```

Also add extra (non-bullet) live links for the new sub-modules to keep navigation coherent:
- [ ] Add `"Milestones": "crm:crmmilestone_list"` under 1.8 (extra; project milestone board)
- [ ] Add `"Workflow Logs": "crm:workflowlog_list"` under 1.10 (extra; audit of rule executions)
- [ ] Add `"Onboarding Steps": "crm:onboardingplan_list"` under 1.11 (extra; reuse plan list as entry point)
- [ ] Add `"Partner Portal": "crm:portal_dashboard"` under 1.12 (extra; portal entry for partners)

---

## Phase 9 — Templates (`templates/crm/`)

One file per template. Mirror the existing `lead_list.html` / `lead_detail.html` / `lead_form.html` structure (filter-bar with `request.GET` pre-fill, Actions column with view/edit/delete, pagination, empty-state, breadcrumb). Use `|stringformat:"d"` for FK pk comparison in filter dropdowns.

### 1.7 Expense templates
- [ ] `expense_list.html` — table: number, category badge, amount, opportunity link, status badge, date; filter bar: status + category dropdowns; Actions: view/edit/delete + approve/reject buttons (show approve/reject only when `status=="submitted"`)
- [ ] `expense_detail.html` — all fields; receipt file link if present; approve/reject action buttons in sidebar (conditional on status); profit margin note if linked opportunity
- [ ] `expense_form.html` — create/edit form; is_edit toggle for title; receipt FileField rendered with current-file display on edit

### 1.8 Project & Delivery templates
- [ ] `crmproject_list.html` — table: number, name, account, status badge, start/end dates, budget, owner; filter: status dropdown; Actions: view/edit/delete; "Convert Opportunity" button on Opportunity detail (not here)
- [ ] `crmproject_detail.html` — project header; milestone list table (title, kind, status, assignee, due_date) with link to milestone detail; timesheet totals (total hours / billable hours); expense total; "Convert to Project" triggered from Opportunity, shown here as read; sidebar: edit/delete
- [ ] `crmproject_form.html` — create/edit form
- [ ] `crmmilestone_list.html` — table: number, project link, title, kind badge, status badge, assignee, due_date; filter: project + status dropdowns; Actions: view/edit/delete
- [ ] `crmmilestone_detail.html` — all fields; sub-task list (parent=self); sidebar: edit/delete/complete
- [ ] `crmmilestone_form.html` — create/edit form; parent field (self-referential FK, scoped to same project)
- [ ] `timesheet_list.html` — table: number, project, employee, date, hours, is_billable badge, status badge; filter: project + status + employee dropdowns; Actions: view/edit/delete
- [ ] `timesheet_detail.html` — all fields; approve/reject sidebar buttons (conditional on `status=="submitted"`); sidebar: edit/delete
- [ ] `timesheet_form.html` — create/edit form; milestone field dynamically filtered by selected project (HTMX optional; static list acceptable for MVP)

### 1.9 Document & Contract templates
- [ ] `doctemplate_list.html` — table: number, name, type badge, is_active, owner, created_at; filter: type + is_active dropdowns; Actions: view/edit/delete
- [ ] `doctemplate_detail.html` — name, type, is_active; body rendered in `<pre>` (escaped HTML); related contracts count; sidebar: edit/delete
- [ ] `doctemplate_form.html` — create/edit form; `body` field rendered as `<textarea rows="20">` for HTML template editing
- [ ] `contractdocument_list.html` — table: number, name, account, status badge, current_version, opportunity, owner; filter: status + opportunity dropdowns; Actions: view/edit/delete
- [ ] `contractdocument_detail.html` — document metadata; signers table (name, email, order, viewed_at, signed_at, declined_at); "Add Signer" inline form; "Remove Signer" delete button per row; body_snapshot in `<pre>`; sidebar: edit/delete
- [ ] `contractdocument_form.html` — create/edit form
- [ ] `sign_document.html` — public (no navbar/auth); displays `body_snapshot` HTML; "I have read and agree — Sign" submit button; if already signed: shows confirmation message; no delete/edit

### 1.10 Workflow & Approval templates
- [ ] `workflowrule_list.html` — table: number, name, trigger_entity + trigger_event badges, is_active badge, owner; filter: is_active + trigger_entity dropdowns; Actions: view/edit/delete
- [ ] `workflowrule_detail.html` — all fields; conditions/actions JSON rendered as formatted HTML table (key-value pairs); recent WorkflowLog entries (latest 10); sidebar: edit/delete
- [ ] `workflowrule_form.html` — create/edit form; `conditions` and `actions` fields rendered as `<textarea>` (JSONField raw input with helper comment showing example structure)
- [ ] `workflowlog_list.html` — table: rule, record_label, status badge, fired_at, error_msg truncated; filter: status + rule dropdowns; No Actions column (read-only); pagination
- [ ] `workflowlog_detail.html` — full log entry: rule link, record_label, status badge, fired_at, full error_msg; No edit/delete buttons
- [ ] `approvalrequest_list.html` — table: number, subject, approver, status badge, created_at; filter: status + approver dropdowns; Actions: view/edit/delete
- [ ] `approvalrequest_detail.html` — all fields; threshold_field/value; approve/reject buttons in sidebar (conditional on `status=="pending"` and `approver==request.user`); sidebar: edit/delete (conditional on pending)
- [ ] `approvalrequest_form.html` — create/edit form

### 1.11 Customer Success templates
- [ ] `onboardingplan_list.html` — table: number, name, account, status badge, target_date, progress_pct (annotated), owner; filter: status + account dropdowns; Actions: view/edit/delete
- [ ] `onboardingplan_detail.html` — plan header with progress bar (`progress_pct`); ordered steps table (order, title, assignee, due_date, completed_at, "Complete" + "Delete" action buttons per row); "Add Step" inline form at bottom; sidebar: edit/delete
- [ ] `onboardingplan_form.html` — create/edit form
- [ ] `healthscore_list.html` — table: account, score (with tier colour chip), tier badge, computed_at; filter: tier dropdown; Actions: view/edit/delete; "Configure Weights" link to `health_config_edit`
- [ ] `healthscore_detail.html` — score gauge (numeric, large); tier badge; breakdown table (per-signal name, weight, sub-score); "Recompute" POST button in sidebar; computed_at; sidebar: edit/delete
- [ ] `healthscore_form.html` — create/edit form (manual override)
- [ ] `health_config_form.html` — standalone page for `health_config_edit` view; four weight fields + threshold fields; no number/prefix
- [ ] `survey_list.html` — table: number, account, survey_type badge, score, classification badge, sent_at, responded_at; filter: survey_type + classification + account dropdowns; Actions: view/edit/delete
- [ ] `survey_detail.html` — score display; classification badge; feedback_text; related case link; respond link (public `survey_respond` URL); sidebar: edit/delete
- [ ] `survey_form.html` — create/edit form; responded_at excluded (system-set); classification excluded (system-set)
- [ ] `survey_respond.html` — public (no auth navbar); simple score picker (0–10 radio or dropdown) + feedback textarea + submit; if already responded: shows "Thank you" message

### 1.12 Vendor & Partner templates
- [ ] `partnerportalaccess_list.html` — table: number, partner_party, portal_user, access_level badge, is_active, invited_at, accepted_at; filter: is_active + access_level dropdowns; Actions: view/edit/delete
- [ ] `partnerportalaccess_detail.html` — all fields; portal_user link; sidebar: edit/delete
- [ ] `partnerportalaccess_form.html` — create/edit form
- [ ] `crm_po_list.html` — table: PO number, vendor name, status, total amount, created_at; filter: status + vendor dropdowns; Actions: view/delete + "Generate Bill" button on detail
- [ ] `crm_po_detail.html` — PO header; line items table (item, qty, unit_price, total); "Generate Bill" POST button; sidebar: delete
- [ ] `crm_po_form.html` — create form with inline PO lines (one row per item; dynamic add-row via simple JS or HTMX)
- [ ] `portal_dashboard.html` — simplified partner portal layout (no main sidebar); partner name; PO count; stock link if `can_view_stock`
- [ ] `portal_po_list.html` — partner sees own POs only; read-only table; no Actions column
- [ ] `portal_stock.html` — on-hand stock table (Item name, on-hand qty from StockMove aggregation); read-only

---

## Phase 10 — Verify

Run all commands with the venv Python (`C:\xampp\htdocs\NavERP\venv\Scripts\python.exe`):

- [ ] `venv\Scripts\python.exe manage.py makemigrations crm` — confirm single migration `0005_*` created
- [ ] `venv\Scripts\python.exe manage.py sqlmigrate crm 0005` — review SQL; confirm FK + index + unique_together
- [ ] `venv\Scripts\python.exe manage.py migrate` — zero errors on `nav_erp`
- [ ] `venv\Scripts\python.exe manage.py seed_crm` — first run: seeds all new entities; prints login instructions
- [ ] `venv\Scripts\python.exe manage.py seed_crm` (second run) — must print "already exists — skipping" for every model; zero duplicate rows created (idempotency check)
- [ ] `venv\Scripts\python.exe manage.py check` — zero errors, zero warnings
- [ ] Write `temp/crm_smoke_ext.py` — test-client sweep over all new `crm:*` URLs for 200/302 (authenticated as `admin_acme`); check no `{#` / `{% comment` template leaks; cross-tenant IDOR → 404 for pk from tenant B when logged in as tenant A; `sign_document` and `survey_respond` public endpoints return 200 with a valid token; `portal_dashboard` returns 200 for a portal user and 403/redirect for a non-portal user
- [ ] Run `temp/crm_smoke_ext.py` — all checks green
- [ ] Sidebar check: 1.7, 1.8, 1.9, 1.10, 1.11, 1.12 sub-modules all show as **Live** (non-grey) in the sidebar

---

## Phase 11 — Close-out (review agents + skill)

- [ ] Run **`code-reviewer` agent** — apply findings; commit each changed file one at a time (PowerShell-safe)
- [ ] Run **`explorer` agent** — apply findings; commit
- [ ] Run **`frontend-reviewer` agent** — apply findings; commit
- [ ] Run **`performance-reviewer` agent** — apply findings (check N+1 on milestone/timesheet lists, JSONField reads, HealthScore recompute query count); commit
- [ ] Run **`qa-smoke-tester` agent** — apply findings; commit
- [ ] Run **`security-reviewer` agent** — apply findings (flag: `sign_document` public endpoint token enumeration risk; `survey_respond` public endpoint; portal access bypass; `approved_by`/`approver` must be scoped to tenant on form); commit
- [ ] Run **`test-writer` agent** — add tests for all new views/models (IDOR, approve/reject state machine, HealthScore recompute, survey classification auto-set, WorkflowRule JSONField round-trip, `sign_document` public flow); commit
- [ ] Update **`.claude/skills/crm/SKILL.md`** — add 1.7–1.12 models, routes, seeder additions, and new LIVE_LINKS entries; commit
- [ ] Update **`README.md`** — add new sub-modules to the feature table and seeder section; commit

### Per-file commit list (PowerShell-safe, one file per commit)

```
git add 'apps\crm\models.py'; git commit -m 'feat(crm): add 1.7-1.12 models — Expense, CrmProject, CrmMilestone, Timesheet, DocTemplate, ContractDocument, SignerRecord, WorkflowRule, WorkflowLog, ApprovalRequest, OnboardingPlan, OnboardingStep, HealthScore, HealthScoreConfig, Survey, PartnerPortalAccess'
git add 'apps\crm\migrations\0005_expense_crmproject_crmmilestone_timesheet_doctemplate_contractdocument_signerrecord_workflowrule_workflowlog_approvalrequest_onboardingplan_onboardingstep_healthscore_healthscoreconfig_survey_partnerportalaccess.py'; git commit -m 'feat(crm): migration 0005 — 1.7-1.12 models'
git add 'apps\crm\forms.py'; git commit -m 'feat(crm): forms for 1.7-1.12 models (Expense/CrmProject/Milestone/Timesheet/DocTemplate/ContractDocument/SignerRecord/WorkflowRule/ApprovalRequest/OnboardingPlan/OnboardingStep/HealthScoreConfig/Survey/PartnerPortalAccess)'
git add 'apps\crm\views.py'; git commit -m 'feat(crm): views for 1.7-1.12 — expense/project/milestone/timesheet/doctemplate/contract/workflowrule/workflowlog/approval/onboarding/healthscore/survey/portal CRUD + custom actions'
git add 'apps\crm\urls.py'; git commit -m 'feat(crm): URL patterns for 1.7-1.12 — expense/project/milestone/timesheet/doctemplate/contract/workflow/approval/onboarding/health/survey/portal routes'
git add 'apps\crm\admin.py'; git commit -m 'feat(crm): admin registration for 1.7-1.12 models'
git add 'apps\crm\management\commands\seed_crm.py'; git commit -m 'feat(crm): extend seed_crm with 1.7-1.12 demo data — expenses/projects/milestones/timesheets/templates/contracts/workflows/approvals/onboarding/health/surveys/portal'
git add 'apps\core\navigation.py'; git commit -m 'feat(core/nav): wire LIVE_LINKS 1.7-1.12 — expense/project/timesheet/doctemplate/contract/workflowrule/approval/onboarding/healthscore/survey/portal routes'
git add 'templates\crm\expense_list.html'; git commit -m 'feat(crm): expense list template with status/category filters and approve/reject actions'
git add 'templates\crm\expense_detail.html'; git commit -m 'feat(crm): expense detail template with receipt link and approve/reject sidebar'
git add 'templates\crm\expense_form.html'; git commit -m 'feat(crm): expense create/edit form template'
git add 'templates\crm\crmproject_list.html'; git commit -m 'feat(crm): CRM project list template with status filter'
git add 'templates\crm\crmproject_detail.html'; git commit -m 'feat(crm): CRM project detail with milestone list, timesheet totals, expense total'
git add 'templates\crm\crmproject_form.html'; git commit -m 'feat(crm): CRM project create/edit form template'
git add 'templates\crm\crmmilestone_list.html'; git commit -m 'feat(crm): CRM milestone list template with project/status filters'
git add 'templates\crm\crmmilestone_detail.html'; git commit -m 'feat(crm): CRM milestone detail with sub-task list'
git add 'templates\crm\crmmilestone_form.html'; git commit -m 'feat(crm): CRM milestone create/edit form template'
git add 'templates\crm\timesheet_list.html'; git commit -m 'feat(crm): timesheet list template with project/status/employee filters'
git add 'templates\crm\timesheet_detail.html'; git commit -m 'feat(crm): timesheet detail with approve/reject sidebar'
git add 'templates\crm\timesheet_form.html'; git commit -m 'feat(crm): timesheet create/edit form template'
git add 'templates\crm\doctemplate_list.html'; git commit -m 'feat(crm): doc template list with type/active filters'
git add 'templates\crm\doctemplate_detail.html'; git commit -m 'feat(crm): doc template detail with body preview'
git add 'templates\crm\doctemplate_form.html'; git commit -m 'feat(crm): doc template create/edit form with large textarea for body'
git add 'templates\crm\contractdocument_list.html'; git commit -m 'feat(crm): contract document list with status/opportunity filters'
git add 'templates\crm\contractdocument_detail.html'; git commit -m 'feat(crm): contract document detail with signer table and add/remove signer actions'
git add 'templates\crm\contractdocument_form.html'; git commit -m 'feat(crm): contract document create/edit form template'
git add 'templates\crm\sign_document.html'; git commit -m 'feat(crm): public document signing page (no auth, token-based)'
git add 'templates\crm\workflowrule_list.html'; git commit -m 'feat(crm): workflow rule list with entity/active filters'
git add 'templates\crm\workflowrule_detail.html'; git commit -m 'feat(crm): workflow rule detail with conditions/actions table and recent logs'
git add 'templates\crm\workflowrule_form.html'; git commit -m 'feat(crm): workflow rule create/edit form with JSON textarea fields'
git add 'templates\crm\workflowlog_list.html'; git commit -m 'feat(crm): workflow log list (read-only) with status/rule filters'
git add 'templates\crm\workflowlog_detail.html'; git commit -m 'feat(crm): workflow log detail (read-only, no edit/delete)'
git add 'templates\crm\approvalrequest_list.html'; git commit -m 'feat(crm): approval request list with status/approver filters'
git add 'templates\crm\approvalrequest_detail.html'; git commit -m 'feat(crm): approval request detail with approve/reject sidebar actions'
git add 'templates\crm\approvalrequest_form.html'; git commit -m 'feat(crm): approval request create/edit form template'
git add 'templates\crm\onboardingplan_list.html'; git commit -m 'feat(crm): onboarding plan list with status/account filters and progress_pct'
git add 'templates\crm\onboardingplan_detail.html'; git commit -m 'feat(crm): onboarding plan detail with step list, progress bar, and add/complete/delete step actions'
git add 'templates\crm\onboardingplan_form.html'; git commit -m 'feat(crm): onboarding plan create/edit form template'
git add 'templates\crm\healthscore_list.html'; git commit -m 'feat(crm): health score list with tier filter and configure-weights link'
git add 'templates\crm\healthscore_detail.html'; git commit -m 'feat(crm): health score detail with breakdown table and recompute action'
git add 'templates\crm\healthscore_form.html'; git commit -m 'feat(crm): health score create/edit form (manual override)'
git add 'templates\crm\health_config_form.html'; git commit -m 'feat(crm): health score config form for weight/threshold configuration'
git add 'templates\crm\survey_list.html'; git commit -m 'feat(crm): survey list with type/classification/account filters'
git add 'templates\crm\survey_detail.html'; git commit -m 'feat(crm): survey detail with score, classification badge, and public respond link'
git add 'templates\crm\survey_form.html'; git commit -m 'feat(crm): survey create/edit form template'
git add 'templates\crm\survey_respond.html'; git commit -m 'feat(crm): public survey response page (no auth)'
git add 'templates\crm\partnerportalaccess_list.html'; git commit -m 'feat(crm): partner portal access list with active/level filters'
git add 'templates\crm\partnerportalaccess_detail.html'; git commit -m 'feat(crm): partner portal access detail'
git add 'templates\crm\partnerportalaccess_form.html'; git commit -m 'feat(crm): partner portal access create/edit form'
git add 'templates\crm\crm_po_list.html'; git commit -m 'feat(crm): CRM purchase order list with status/vendor filters'
git add 'templates\crm\crm_po_detail.html'; git commit -m 'feat(crm): CRM purchase order detail with line items and generate-bill action'
git add 'templates\crm\crm_po_form.html'; git commit -m 'feat(crm): CRM purchase order create form with inline lines'
git add 'templates\crm\portal_dashboard.html'; git commit -m 'feat(crm): partner portal dashboard (restricted layout, no main sidebar)'
git add 'templates\crm\portal_po_list.html'; git commit -m 'feat(crm): partner portal PO list (read-only, partner-scoped)'
git add 'templates\crm\portal_stock.html'; git commit -m 'feat(crm): partner portal stock view (on-hand from StockMove aggregation)'
git add 'temp\crm_smoke_ext.py'; git commit -m 'test(crm): smoke test for 1.7-1.12 new routes — 200/302, no leaks, IDOR 404, public endpoints'
git add '.claude\skills\crm\SKILL.md'; git commit -m 'docs(skill/crm): update SKILL.md with 1.7-1.12 models, routes, seeder, LIVE_LINKS'
git add 'README.md'; git commit -m 'docs(readme): add CRM 1.7-1.12 sub-modules to feature table and seeder section'
```

---

## Later passes / deferred

- **Payment gateway webhooks (Stripe / PayPal / Razorpay)** — `core.Payment` data model is ready; HTTP listener + signature verification + idempotency key = integration/later pass.
- **External e-signature API (DocuSign / Zoho Sign / Adobe Sign)** — in-house token flow built here; delegating to a 3rd-party API is an integration/later concern once the `ContractDocument` + `SignerRecord` model is stable.
- **Multi-level approval chains (ApprovalStep child table)** — single-approver flow is the MVP; sequential multi-approver chains (A → B → C, short-circuit on reject) are v2.
- **Kanban drag-and-drop persistence for CrmMilestone.order** — HTMX drag-reorder with POST to update `order` is a UX enhancement; ship status-dropdown column view first.
- **Gantt drag-to-reschedule** — frappe-gantt JS library can render a static Gantt from `CrmMilestone.start_date/due_date`; persisting date changes via drag events is a deferred UX pass.
- **Skills-based resource search (ResourceSkill M2M)** — workload view (timesheet aggregated by employee) is MVP; `core.Employment` skill-tag M2M is a follow-on.
- **S3 / cloud file storage** — `Expense.receipt` and `core.Document.file` use Django's default `FileSystemStorage`; swap to `django-storages` + S3 in a later infrastructure pass.
- **AI-assisted document generation** — Zoho Sign 2025 AI / HubSpot Breeze LLM drafting; Django merge-variable template rendering is the MVP; LLM integration is deferred.
- **Survey email delivery (SMTP / SendGrid)** — in-app survey link (token URL) is MVP; SMTP or SendGrid automated dispatch is integration/later.
- **Partner portal self-service PO acceptance and lead form** — portal login + stock view is MVP; partner submitting a lead or accepting a PO is a follow-on feature.
- **Webhook delivery retry / dead-letter queue** — `WorkflowRule` webhook action fires an HTTP POST; production-grade exponential back-off retry via Celery is deferred.
- **Celery beat scheduled workflow actions** — `WorkflowRule.delay_value/delay_unit` model fields are in place; the Celery beat scan task for scheduled rule execution is deferred to a Celery infrastructure pass.
- **Revenue recognition / milestone billing (Chargebee-style)** — prorated subscription billing, contract term enforcement, dunning — deferred to the Accounting module (2.4 AR / 2.3 AP).
- **Clause/Section Library (`crm.ClauseLibrary`)** — reusable pre-approved contract blocks; deferred after core `DocTemplate` is live.
- **Recurring invoice schedule (`crm.RecurringInvoice`)** — frequency/next_run_date scheduling; deferred to the Accounting module or a dedicated billing pass once `core.Invoice` is fully wired.
- **Profit margin annotation on Opportunity list** — the detail page shows `amount − SUM(approved expenses)`; displaying this as a column on the list page requires an annotation subquery and is a performance pass.

## Review notes
(filled in after close-out)

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

## Spine-gap adaptation (build-time re-plan — 2026-06-20)

> The research/todo plan assumed unified-core master tables (`core.Item`, `core.Currency`,
> `core.Invoice`/`Payment` AR-AP ledger, `core.PurchaseOrder`/`PurchaseOrderLine`,
> `core.StockMove`) already exist. They do **not** — the foundation (Module 0) built only
> `Party/PartyRole/Address/ContactMethod/PartyRelationship/Employment/Activity/AuditLog/Document`
> in `core`, plus `Subscription/SubscriptionInvoice/BrandingSetting/EncryptionKey/HealthMetric`
> in `tenants`. The AR/AP ledger + Item/Currency/StockMove/PurchaseOrder masters belong to the
> still-unbuilt Accounting (2), Inventory (5) and Procurement (6) modules. Adaptation, keeping
> every model self-contained or reusing only what exists (`core.Party`, `settings.AUTH_USER_MODEL`,
> `crm.Opportunity/Case`):
>
> - **1.7 Expense** — drop `currency` FK→`core.Currency`; use `currency_code` CharField (default `"USD"`).
> - **1.11 HealthScoreConfig** — weight signals are `tickets / nps / tasks / engagement` (drop
>   `payments`, which needs the Accounting ledger). `compute_health_score()` derives from
>   `crm.Case` (open/overdue), `crm.Survey` (latest NPS), `crm.CrmTask` (completion), and
>   `crm.Opportunity` (open-deal engagement) — all existing CRM data.
> - **1.12 Purchase Orders / Stock** — build CRM-owned `PurchaseOrder` [PO-] + `PurchaseOrderLine`
>   (child) and `ProductStock` [STK-] instead of writing to non-existent `core.PurchaseOrder` /
>   `core.StockMove`. Vendor = `core.Party` (organization). `crm_po_generate_bill` becomes
>   `crm_po_receive` (marks the PO received + bumps `ProductStock.on_hand_qty`). The partner
>   portal stock view reads `ProductStock`. When the Procurement/Inventory modules land, these
>   can migrate onto the spine.
> - Net model count: **18** definitions (adds `PurchaseOrder`, `PurchaseOrderLine`, `ProductStock`;
>   the rest of the plan stands — all their FKs target `crm.*`, `core.Party`, or the user model,
>   which all exist).

## Review notes — CRM 1.7–1.12 COMPLETE ✅ (2026-06-20)

- **Built:** 18 CRM-owned models (migration `0005`) across all six sub-modules + `compute_health_score`
  service; full CRUD via `apps/core/crud` helpers + custom actions; 52 templates; idempotent
  `seed_crm._seed_extension`; LIVE_LINKS 1.7–1.12; admin for all models. Reused `core.Party` +
  `crm.Opportunity/Case` + the user model only — **spine-gap adaptation** applied (CRM-owned
  PurchaseOrder/PurchaseOrderLine/ProductStock, `Expense.currency_code` CharField, health from CRM signals).
- **Module Creation Sequence (research → todo → code → 7 review agents → skill, one file per commit, no push):**
  - research → `research-crm-1.7-1.12.md` (12 products: Vtiger/Bitrix24/Zoho/Salesforce/HubSpot/PandaDoc/Gainsight/…).
  - todo → this plan; build-time re-plan committed for the missing spine.
  - **code-reviewer** → 8 fixes (sign_document `select_for_update` double-sign race, public survey score clamp,
    expense/approval approve+reject `@tenant_admin_required`, portal `_portal_access` pinned to tenant, PO
    add/remove-line atomic + receive guard, onboarding step-complete tenant filter, `compute_health_score` atomic);
    1 false-positive (boolean filter) verified working on MariaDB.
  - **explorer** → restored the unreachable `opportunity_to_project` UI action; portal views use `request.tenant`.
  - **frontend-reviewer** → public-page `|safe` XSS removed; `obj.created`→`created_at`; 28 list/form consistency
    fixes (aria-label, filter form-groups, table-wrap restructure, `non_field_errors`) + 6 detail polish fixes.
  - **performance-reviewer** → onboardingplan_list `prefetch_related(steps)` (N+1), defer body/body_snapshot/error_msg
    on lists, `.only()` filter dropdowns, precomputed onboarding progress, paginated portal lists.
    (Skipped the suggested child-table composite indexes — Django already auto-indexes the FK columns those reverse
    lookups filter on.)
  - **qa-smoke-tester** → 51/51 PASS; surfaced the required inline `order` field → dropped from the 3 inline forms,
    auto-assigned in the views.
  - **security-reviewer** → "not safe to ship" → fixed: mass-assignment on Expense/Contract/ProductStock/Timesheet
    forms (system fields excluded), `Expense.receipt` extension+size allowlist, `health_config_edit`/`crm_po_receive`
    `@tenant_admin_required`, contract expiry check on signing, survey feedback length cap, new `expense_submit`
    (owner draft→submitted). All proven via direct exploit-attempt checks.
  - **test-writer** → 194 new tests (`test_ext_models/views/security.py`); **apps/crm 552 passed, full project 850
    passed, 0 failed** (exit 0 confirmed). No product bugs surfaced — security regressions locked in.
- **Skill:** `.claude/skills/crm/SKILL.md` extended with the 1.7–1.12 model table, custom actions, security
  conventions, seeder/LIVE_LINKS/perf notes. **README** roadmap/feature/route sections updated.
- `manage.py check` clean; migrate clean on `nav_erp`; `seed_crm` idempotent; throwaway `temp/crm_smoke_ext.py`
  green (all `crm:*` 200/302, public endpoints 200, IDOR→404, no comment leaks). One file per commit to `main`;
  **not pushed** (user pushes).
- **Deferred** (documented): Stripe/DocuSign/S3/SMTP integrations, Celery scheduled workflow actions, multi-level
  approval chains, Gantt drag-reschedule, AI doc generation, partner self-service lead/PO, and migrating 1.12 onto
  the real Inventory/Procurement spine once Modules 5/6 land.

---

# Module 2 — Accounting & Finance (accounting) — plan from research-accounting.md  (2026-06-20)

## Section 0 — Architecture decision: accounting OWNS the GL spine (L28 applied)

> **Critical decision recorded here before any code is written.**
>
> `apps/core/models.py` (verified 2026-06-20) contains ONLY:
> `Tenant`, `OrgUnit`, `Party`, `PartyRole`, `Address`, `ContactMethod`, `PartyRelationship`,
> `Employment`, `Activity`, `AuditLog`, `Document`.
>
> There is NO `GLAccount`, NO `JournalEntry`, NO `Currency`, NO `Invoice`, NO `Payment`,
> NO `BankAccount` in the core spine — those exist only in `NavERP-ERD.md` as *intended* future
> entities, not as built code (L28). `CRM 1.7–1.12` already documented this gap and adapted.
>
> **Decision:** The `accounting` app BUILDS the financial spine from scratch. All later modules
> (Inventory, Procurement, Sales, Assets) will FK into `accounting.*` models by string, exactly
> as every module FKs into `core.*` by string.
>
> **What `accounting` builds (net-new tables, not wrappers):**
> - `Currency` — ISO 4217 code master (shared, not tenant-scoped)
> - `ExchangeRate` — daily spot rates per tenant (tenant-scoped)
> - `GLAccount` — Chart of Accounts, hierarchical, tenant-scoped
> - `FiscalPeriod` — tenant accounting periods, open/closed lock
> - `JournalEntry` — double-entry header [JE-], tenant-scoped, append-only once posted
> - `JournalLine` — debit/credit arms, FK to GLAccount + optionally Party/OrgUnit
> - `PaymentTerm` — reusable Net-N / discount term configs, tenant-scoped
> - `VendorProfile` — thin AP extension on `core.Party` (OneToOne)
> - `CustomerProfile` — thin AR extension on `core.Party` (OneToOne)
> - `Invoice` — AR invoice/credit note [INV-], tenant-scoped
> - `InvoiceLine` — AR line items
> - `Bill` — AP vendor bill [BILL-], tenant-scoped
> - `BillLine` — AP line items
> - `Payment` — unified inbound/outbound payment [PAY-], tenant-scoped
> - `PaymentAllocation` — cash application join (Payment → Invoice/Bill)
> - `BankAccount` — tenant bank accounts, FK to GLAccount
> - `BankTransaction` — imported/manual bank statement lines
> - `ReconciliationMatch` — matched pairs (BankTransaction + Payment/JournalLine)
>
> **What `accounting` REUSES from core (confirmed-existing):**
> - `core.Party` / `core.PartyRole` — vendors and customers (no new vendor/customer tables;
>   VendorProfile/CustomerProfile are accounting-owned OneToOne extensions only)
> - `core.OrgUnit` — GL dimension / cost center (FK on JournalLine)
> - `core.AuditLog` / `core.utils.write_audit_log` — immutable status-change log
> - `core.utils.next_number` — per-tenant auto-numbering (JE-/INV-/BILL-/PAY- prefixes)
> - `apps/core/decorators.py :: tenant_admin_required` — gates period-close, posting, void
>
> **Double-entry invariants (enforced at model.save() and view layer):**
> 1. A `JournalEntry` may NOT be posted unless `sum(JournalLine.debit) == sum(JournalLine.credit)`.
>    Validated in the post view before changing `status` to `posted`.
> 2. Once `JournalEntry.status == 'posted'`, the entry and all its lines are IMMUTABLE — no edit
>    or delete. Corrections are made by creating a reversal entry (`reversal_of` FK self).
> 3. `GLAccount` balance is NEVER a stored field — always derived by aggregating posted
>    `JournalLine` rows. No `balance` field on `GLAccount`.
> 4. Posting into a `FiscalPeriod` with `status != 'open'` is blocked at the view layer
>    (check before calling `entry.save()` with `status='posted'`).
> 5. `Invoice.total` / `Bill.total` are stored for display performance but always recomputed
>    from line aggregates on save — never hand-edited via the ModelForm.
>
> **TenantNumbered pattern:** accounting models with human numbers inherit the SAME abstract
> base used in CRM — `TenantNumbered` from `apps/crm/models.py` — OR replicate its pattern
> identically inside `apps/accounting/models.py` as a local abstract base (preferred: local
> copy avoids cross-app import, since `crm` and `accounting` are peers). The local abstract
> base has the same `tenant FK`, `number CharField(editable=False)`, `created_at`, `updated_at`,
> and the same 5-retry `save()` via `apps.core.utils.next_number`.

---

## Section 1 — Models (18 accounting-owned tables)

> Each item lists: Number Prefix | key fields + CHOICES | which core entities it reuses vs. adds
> | the researched P0/P1 features that drove each non-obvious field.

### Sub-module 2.2 — General Ledger

- [ ] **`Currency`** (no NUMBER_PREFIX, global not tenant-scoped) — net-new table.
  Fields: `code` CharField(max_length=3, unique=True) — ISO 4217 e.g. "USD"; `name`
  CharField(max_length=60); `symbol` CharField(max_length=8); `is_active` BooleanField(default=True).
  NO tenant FK — shared across all tenants (same as intended ERD). Seed with USD, EUR, GBP, CAD.
  Drivers: Multi-currency GL (all 10 products), multi-currency invoicing, bank account currencies.

- [ ] **`ExchangeRate`** — net-new, tenant-scoped. Fields: `tenant` FK→`"core.Tenant"`;
  `currency` FK→`"accounting.Currency"` CASCADE; `rate_date` DateField; `rate` DecimalField
  (max_digits=18, decimal_places=8); `source` CharField choices
  `[("manual","Manual"),("feed","Feed")]` default `"manual"`. `unique_together = ("tenant",
  "currency", "rate_date")`. No tenant auto-number (lookup table, not a transactional record).
  Drivers: Multi-currency GL FX conversion, FX gain/loss at period-end, multi-currency invoicing.

- [ ] **`GLAccount`** [no NUMBER_PREFIX — CoA uses `code` field, not an auto-number] — net-new,
  tenant-scoped. Fields: `tenant` FK→`"core.Tenant"` CASCADE db_index=True;
  `code` CharField(max_length=20); `name` CharField(max_length=255);
  `account_type` CharField choices
  `[("asset","Asset"),("liability","Liability"),("equity","Equity"),("income","Income"),("expense","Expense")]`;
  `normal_balance` CharField choices `[("debit","Debit"),("credit","Credit")]`
  (auto-set in save() based on account_type: asset/expense=debit, liability/equity/income=credit —
  never on the ModelForm); `parent` FK→`"self"` SET_NULL null blank related_name=`"children"`
  (hierarchical CoA — sub-accounts nest under parent); `is_active` BooleanField(default=True);
  `description` TextField(blank=True). `unique_together = ("tenant", "code")`.
  NOTE: NO `balance` field — balances are always derived via JournalLine aggregation.
  Drivers: Chart of Accounts (all 10 products), Account Types, hierarchical sub-accounts,
  GL dimensions/OrgUnit cost-center tagging, immutable audit trail.

- [ ] **`FiscalPeriod`** — net-new, tenant-scoped. Fields: `tenant` FK→`"core.Tenant"` CASCADE
  db_index=True; `name` CharField(max_length=60, e.g. "Jan 2025"); `period_type` CharField choices
  `[("month","Month"),("quarter","Quarter"),("year","Year")]` default `"month"`; `start_date`
  DateField; `end_date` DateField; `status` CharField choices
  `[("open","Open"),("closed","Closed"),("locked","Locked")]` default `"open"`;
  `closed_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null blank related_name=`"accounting_periods_closed"`;
  `closed_at` DateTimeField null blank (system-set — EXCLUDE from ModelForm per L22).
  Drivers: Fiscal Periods (all 10 products), Period Close Procedure, posting block into closed period,
  year-end close.

- [ ] **`JournalEntry`** [PREFIX `"JE"`] — net-new, tenant-scoped. Extends the local `TenantNumbered`
  abstract base. Fields: `entry_type` CharField choices
  `[("manual","Manual"),("invoice","Invoice Posting"),("payment","Payment"),("bank","Bank"),
  ("recurring","Recurring"),("reversal","Reversal")]` default `"manual"`;
  `status` CharField choices
  `[("draft","Draft"),("pending_approval","Pending Approval"),("posted","Posted"),("void","Void")]`
  default `"draft"`; `fiscal_period` FK→`"accounting.FiscalPeriod"` SET_NULL null blank
  related_name=`"journal_entries"` (nullable because draft entries may predate period assignment);
  `entry_date` DateField; `description` TextField(blank=True); `reference` CharField(max_length=100,
  blank=True, help_text="External document reference e.g. PO number");
  `reversal_of` FK→`"self"` SET_NULL null blank related_name=`"reversals"` (populated when this entry
  is a reversal of another posted entry); `created_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null
  related_name=`"accounting_je_created"` (system-set in view — EXCLUDE from ModelForm);
  `approved_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null blank related_name=`"accounting_je_approved"`
  (system-set when status moves to posted — EXCLUDE from ModelForm);
  `posted_at` DateTimeField null blank (system-set — EXCLUDE from ModelForm).
  IMMUTABILITY RULE: `save()` override blocks edits if `self.pk` already exists and the
  ORIGINAL status was `"posted"` or `"void"` — raise `ValidationError`.
  Drivers: Manual Journal Entries (all 10 products), Journal Approval Workflow, Recurring JEs,
  Reversing JEs, immutable audit trail.

- [ ] **`JournalLine`** — net-new, no auto-number (child of JournalEntry). Fields:
  `entry` FK→`"accounting.JournalEntry"` CASCADE related_name=`"lines"`;
  `gl_account` FK→`"accounting.GLAccount"` PROTECT related_name=`"journal_lines"`;
  `debit` DecimalField(max_digits=18, decimal_places=2, default=0);
  `credit` DecimalField(max_digits=18, decimal_places=2, default=0);
  `description` CharField(max_length=255, blank=True);
  `party` FK→`"core.Party"` SET_NULL null blank related_name=`"accounting_je_lines"`
  (subledger drill-down to customer/vendor AR/AP);
  `org_unit` FK→`"core.OrgUnit"` SET_NULL null blank related_name=`"accounting_je_lines"`
  (cost-center dimension — reuses confirmed-existing core.OrgUnit);
  `currency` FK→`"accounting.Currency"` SET_NULL null blank related_name=`"je_lines"`
  (transaction currency if different from functional currency);
  `amount_foreign` DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
  (amount in transaction currency; null when same as functional);
  `exchange_rate` DecimalField(max_digits=18, decimal_places=8, null=True, blank=True).
  VALIDATION: `clean()` must enforce debit XOR credit (not both non-zero); view must
  enforce sum balance before posting.
  Drivers: Double-entry GL, Multi-currency GL, GL dimensions/cost centers (Sage Intacct, BC,
  NetSuite), subledger drill-down, immutable audit trail.

### Sub-module 2.3 — Accounts Payable + Sub-module 2.4 — Accounts Receivable (shared masters)

- [ ] **`PaymentTerm`** — net-new, tenant-scoped. Fields: `tenant` FK→`"core.Tenant"` CASCADE
  db_index=True; `name` CharField(max_length=80, e.g. "Net 30", "2/10 Net 30");
  `days_due` PositiveSmallIntegerField; `discount_pct` DecimalField(max_digits=5, decimal_places=2,
  default=0); `discount_days` PositiveSmallIntegerField(default=0); `is_active` BooleanField(default=True).
  Drivers: Payment Terms (all 10 products), Early Payment Discount Capture,
  auto-calculate due_date on bill/invoice entry.

- [ ] **`VendorProfile`** — net-new, thin AP extension on confirmed-existing `core.Party`. Fields:
  `party` OneToOneField→`"core.Party"` CASCADE related_name=`"vendor_profile"`;
  `tenant` FK→`"core.Tenant"` CASCADE db_index=True (denorm for tenant-scoped querysets);
  `payment_terms` FK→`"accounting.PaymentTerm"` SET_NULL null blank;
  `default_expense_account` FK→`"accounting.GLAccount"` SET_NULL null blank
  related_name=`"vendor_default_expense"`;
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `is_1099` BooleanField(default=False); `notes` TextField(blank=True).
  Drivers: Vendor Management via Party spine, Payment Terms, 1099/W-9 tracking flag.

- [ ] **`CustomerProfile`** — net-new, thin AR extension on `core.Party`. Fields:
  `party` OneToOneField→`"core.Party"` CASCADE related_name=`"customer_profile"`;
  `tenant` FK→`"core.Tenant"` CASCADE db_index=True;
  `payment_terms` FK→`"accounting.PaymentTerm"` SET_NULL null blank;
  `credit_limit` DecimalField(max_digits=14, decimal_places=2, default=0);
  `ar_account` FK→`"accounting.GLAccount"` SET_NULL null blank related_name=`"customer_ar_accounts"`;
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `credit_on_hold` BooleanField(default=False).
  Drivers: Customer Management via Party spine, Credit Limit Enforcement, credit hold automation.

### Sub-module 2.4 — Accounts Receivable

- [ ] **`Invoice`** [PREFIX `"INV"`] — net-new, tenant-scoped. Extends local `TenantNumbered`.
  Fields: `kind` CharField choices `[("invoice","Invoice"),("credit_note","Credit Note")]`
  default `"invoice"` (credit note = negative-amount invoice on same table, same CRUD);
  `party` FK→`"core.Party"` PROTECT related_name=`"accounting_invoices"` (the customer);
  `payment_terms` FK→`"accounting.PaymentTerm"` SET_NULL null blank;
  `issue_date` DateField; `due_date` DateField null blank;
  `status` CharField choices
  `[("draft","Draft"),("sent","Sent"),("partial","Partial"),("paid","Paid"),("void","Void")]`
  default `"draft"`;
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `journal_entry` FK→`"accounting.JournalEntry"` SET_NULL null blank related_name=`"invoices"`
  (populated when invoice is posted/confirmed — system-set, EXCLUDE from ModelForm);
  `subtotal` DecimalField(max_digits=18, decimal_places=2, default=0)
  (recomputed on line save — NOT on ModelForm; stored for display);
  `tax_total` DecimalField(max_digits=18, decimal_places=2, default=0) (same);
  `total` DecimalField(max_digits=18, decimal_places=2, default=0) (same);
  `notes` TextField(blank=True).
  IMMUTABILITY: once `status` is `paid` or `void`, block edit (validation gate in view — offer
  credit note instead). A `void` status is set by posting a reversing JournalEntry.
  Drivers: Customer Invoice (all 10 products), Invoice Numbering, Credit Notes/Refunds,
  AR Aging Analysis, Recurring Invoicing anchor.

- [ ] **`InvoiceLine`** — net-new, child of Invoice. Fields:
  `invoice` FK→`"accounting.Invoice"` CASCADE related_name=`"lines"`;
  `description` CharField(max_length=255);
  `quantity` DecimalField(max_digits=14, decimal_places=4, default=1);
  `unit_price` DecimalField(max_digits=14, decimal_places=2);
  `tax_rate_pct` DecimalField(max_digits=5, decimal_places=2, default=0);
  `line_total` DecimalField(max_digits=18, decimal_places=2, default=0)
  (computed = quantity × unit_price, stored; NOT on form — recomputed in save());
  `gl_account` FK→`"accounting.GLAccount"` SET_NULL null blank related_name=`"invoice_lines"`
  (income/revenue account for this line).
  Drivers: Per-line revenue GL coding, tax per line, credit note line reversals.

### Sub-module 2.3 — Accounts Payable

- [ ] **`Bill`** [PREFIX `"BILL"`] — net-new, tenant-scoped. Extends local `TenantNumbered`.
  Fields: `party` FK→`"core.Party"` PROTECT related_name=`"accounting_bills"` (the vendor);
  `payment_terms` FK→`"accounting.PaymentTerm"` SET_NULL null blank;
  `bill_date` DateField; `due_date` DateField null blank;
  `status` CharField choices
  `[("draft","Draft"),("pending_approval","Pending Approval"),("approved","Approved"),
  ("partial","Partial"),("paid","Paid"),("void","Void")]` default `"draft"`;
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `journal_entry` FK→`"accounting.JournalEntry"` SET_NULL null blank related_name=`"bills"`
  (system-set on approval — EXCLUDE from ModelForm);
  `subtotal` DecimalField(max_digits=18, decimal_places=2, default=0) (recomputed — NOT on form);
  `tax_total` DecimalField(max_digits=18, decimal_places=2, default=0) (same);
  `total` DecimalField(max_digits=18, decimal_places=2, default=0) (same);
  `approved_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null blank
  related_name=`"accounting_bills_approved"` (system-set — EXCLUDE from ModelForm);
  `document` FK→`"core.Document"` SET_NULL null blank related_name=`"accounting_bills"`
  (scanned bill attachment — reuses confirmed-existing core.Document);
  `notes` TextField(blank=True).
  Drivers: Vendor Bill (all 10 products), Bill Approval Routing, AP Aging Report,
  3-way match stub via Document attachment.

- [ ] **`BillLine`** — net-new, child of Bill. Fields:
  `bill` FK→`"accounting.Bill"` CASCADE related_name=`"lines"`;
  `description` CharField(max_length=255);
  `quantity` DecimalField(max_digits=14, decimal_places=4, default=1);
  `unit_price` DecimalField(max_digits=14, decimal_places=2);
  `tax_rate_pct` DecimalField(max_digits=5, decimal_places=2, default=0);
  `line_total` DecimalField(max_digits=18, decimal_places=2, default=0)
  (computed = quantity × unit_price — NOT on form);
  `gl_account` FK→`"accounting.GLAccount"` SET_NULL null blank related_name=`"bill_lines"`
  (expense account for this line).
  Drivers: Per-line expense GL coding, early-payment discount line.

- [ ] **`Payment`** [PREFIX `"PAY"`] — net-new, unified AP+AR, tenant-scoped. Extends local
  `TenantNumbered`. Fields:
  `direction` CharField choices `[("in","Inbound — Customer Receipt"),("out","Outbound — Vendor Payment")]`;
  `party` FK→`"core.Party"` PROTECT related_name=`"accounting_payments"` (customer or vendor);
  `bank_account` FK→`"accounting.BankAccount"` PROTECT related_name=`"payments"`;
  `payment_method` CharField choices
  `[("bank_transfer","Bank Transfer"),("check","Check"),("cash","Cash"),("card","Card"),
  ("ach","ACH"),("wire","Wire Transfer")]` default `"bank_transfer"`;
  `payment_date` DateField;
  `amount` DecimalField(max_digits=18, decimal_places=2);
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `status` CharField choices
  `[("draft","Draft"),("confirmed","Confirmed"),("void","Void")]` default `"draft"`;
  `journal_entry` FK→`"accounting.JournalEntry"` SET_NULL null blank related_name=`"payments"`
  (system-set on confirmation — EXCLUDE from ModelForm);
  `notes` TextField(blank=True).
  NOTE: `BankAccount` FK forces the ordering — `BankAccount` model must be defined before
  `Payment` in models.py.
  Drivers: AP Payment Processing (all 10 products), AR Payment Collection, payment method choices,
  bank balance impact, cash position dashboard.

- [ ] **`PaymentAllocation`** — net-new, no auto-number, pure join table. Fields:
  `payment` FK→`"accounting.Payment"` CASCADE related_name=`"allocations"`;
  `invoice` FK→`"accounting.Invoice"` SET_NULL null blank related_name=`"allocations"`
  (AR side; either invoice or bill must be set, not both);
  `bill` FK→`"accounting.Bill"` SET_NULL null blank related_name=`"allocations"` (AP side);
  `allocated_amount` DecimalField(max_digits=18, decimal_places=2);
  `discount_taken` DecimalField(max_digits=14, decimal_places=2, default=0).
  NOTE: no `tenant` FK — tenant is inherited from `payment.tenant`. Child join table.
  Drivers: Cash Application / Matching (AR), Payment-to-Bill Matching (AP), Early Payment Discount
  Capture, multi-invoice payment splits, partial allocation.

### Sub-module 2.5 — Cash Management

- [ ] **`BankAccount`** — net-new, tenant-scoped. Fields:
  `tenant` FK→`"core.Tenant"` CASCADE db_index=True;
  `name` CharField(max_length=255);
  `account_number_last4` CharField(max_length=4, blank=True, help_text="Last 4 digits only");
  `bank_name` CharField(max_length=255, blank=True);
  `currency` FK→`"accounting.Currency"` SET_NULL null blank;
  `gl_account` FK→`"accounting.GLAccount"` SET_NULL null blank related_name=`"bank_accounts"`
  (the GL cash account this bank maps to);
  `opening_balance` DecimalField(max_digits=18, decimal_places=2, default=0);
  `opening_balance_date` DateField null blank;
  `is_active` BooleanField(default=True).
  NOTE: must be defined BEFORE `Payment` in models.py (Payment has FK→BankAccount).
  Drivers: Bank Account Management (all 10 products), Cash Position Dashboard,
  Reconciliation Engine anchor, Inter-account Transfers.

- [ ] **`BankTransaction`** — net-new, tenant-scoped. Fields:
  `tenant` FK→`"core.Tenant"` CASCADE db_index=True;
  `bank_account` FK→`"accounting.BankAccount"` CASCADE related_name=`"transactions"`;
  `transaction_date` DateField;
  `description` CharField(max_length=512);
  `amount` DecimalField(max_digits=18, decimal_places=2);
  `direction` CharField choices `[("credit","Credit — Money In"),("debit","Debit — Money Out")]`;
  `source` CharField choices
  `[("manual","Manual Entry"),("csv_import","CSV Import"),("bank_feed","Bank Feed")]`
  default `"manual"`;
  `status` CharField choices
  `[("unmatched","Unmatched"),("matched","Matched"),("reconciled","Reconciled"),
  ("excluded","Excluded")]` default `"unmatched"`;
  `external_ref` CharField(max_length=255, blank=True,
  help_text="Bank's own transaction ID for deduplication").
  Drivers: Bank Transaction Log (all 10 products), Bank Statement Import CSV,
  Bank Feeds (same model, source='bank_feed'), Reconciliation Engine input,
  Cash Position Dashboard.

- [ ] **`ReconciliationMatch`** — net-new, tenant-scoped. Fields:
  `tenant` FK→`"core.Tenant"` CASCADE db_index=True;
  `bank_transaction` FK→`"accounting.BankTransaction"` CASCADE related_name=`"matches"`;
  `payment` FK→`"accounting.Payment"` SET_NULL null blank related_name=`"reconciliation_matches"`
  (primary match target; either payment or journal_line must be set);
  `journal_line` FK→`"accounting.JournalLine"` SET_NULL null blank related_name=`"reconciliation_matches"`
  (alternative match target for entries without a Payment record);
  `matched_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null blank
  related_name=`"accounting_reconciliation_matches"`;
  `matched_at` DateTimeField(auto_now_add=True);
  `is_confirmed` BooleanField(default=False).
  Drivers: Reconciliation Engine (all 10 products), Auto-Match Rules output storage,
  Bank Reconciliation Statement, Cash Application.

---

## Section 2 — Backend (`apps/accounting/`)

### 2a — App skeleton

- [ ] `apps/accounting/__init__.py` — empty file
- [ ] `apps/accounting/apps.py` — `AppConfig` with `name = "apps.accounting"`,
  `verbose_name = "Accounting & Finance"`
- [ ] `apps/accounting/models.py` — all 18 models in dependency order:
  `Currency` → `ExchangeRate` → `GLAccount` → `FiscalPeriod` → `JournalEntry` →
  `JournalLine` → `PaymentTerm` → `VendorProfile` → `CustomerProfile` → `BankAccount` →
  `Invoice` → `InvoiceLine` → `Bill` → `BillLine` → `Payment` → `PaymentAllocation` →
  `BankTransaction` → `ReconciliationMatch`.
  Include local `TenantNumbered` abstract base (copy the pattern from `apps/crm/models.py`;
  do NOT import from `crm` — peer-app imports are fragile).
  Include `Meta` indexes: `(tenant, status)` on Invoice/Bill/Payment/FiscalPeriod,
  `(tenant, entry_date)` on JournalEntry, `(tenant, transaction_date)` on BankTransaction,
  `(tenant, gl_account)` on JournalLine, `(tenant, is_active)` on GLAccount.
  Encoding for later modules: add `__str__` that includes the human number where present.

- [ ] `apps/accounting/forms.py` — one `ModelForm` per primary model.
  MANDATORY EXCLUSIONS from every form's `Meta.fields` (per L22 + CLAUDE.md):
  - Always exclude: `tenant`, `number` (auto), any `*_at` DateTimeField that is system-set
    (`closed_at`, `posted_at`, `matched_at`), any `*_by` FK set in the view (`created_by`,
    `approved_by`, `matched_by`), computed aggregates (`subtotal`, `tax_total`, `total`,
    `line_total`, `normal_balance`), and `journal_entry` (set when posting, not on the form).
  - `GLAccountForm`: fields `code, name, account_type, parent, is_active, description`;
    `__init__` scopes `parent` queryset to `tenant` GLAccounts.
  - `FiscalPeriodForm`: fields `name, period_type, start_date, end_date, status`;
    exclude `closed_by`, `closed_at` (system-set by the close_period action view).
  - `JournalEntryForm`: fields `entry_type, entry_date, description, reference, fiscal_period`;
    exclude `status` (controlled via action views only), `reversal_of` (system-set),
    `created_by`, `approved_by`, `posted_at`.
  - `JournalLineForm` / inline formset: fields `gl_account, debit, credit, description,
    party, org_unit, currency, amount_foreign, exchange_rate`.
  - `PaymentTermForm`: all non-system fields.
  - `VendorProfileForm`: fields `payment_terms, default_expense_account, currency, is_1099, notes`.
  - `CustomerProfileForm`: fields `payment_terms, credit_limit, ar_account, currency, credit_on_hold`.
  - `InvoiceForm`: fields `kind, party, payment_terms, issue_date, due_date, status, currency, notes`;
    exclude `journal_entry`, `subtotal`, `tax_total`, `total`.
  - `InvoiceLineForm`: fields `description, quantity, unit_price, tax_rate_pct, gl_account`;
    exclude `line_total`.
  - `BillForm`: fields `party, payment_terms, bill_date, due_date, status, currency, document, notes`;
    exclude `journal_entry`, `subtotal`, `tax_total`, `total`, `approved_by`.
  - `BillLineForm`: fields `description, quantity, unit_price, tax_rate_pct, gl_account`;
    exclude `line_total`.
  - `PaymentForm`: fields `direction, party, bank_account, payment_method, payment_date, amount,
    currency, notes`; exclude `status` (set via confirm action), `journal_entry`.
  - `PaymentAllocationForm`: fields `invoice, bill, allocated_amount, discount_taken`.
  - `BankAccountForm`: all non-system fields.
  - `BankTransactionForm`: fields `bank_account, transaction_date, description, amount, direction,
    source, external_ref`; exclude `status` (set by reconciliation engine).
  - `ReconciliationMatchForm`: fields `bank_transaction, payment, journal_line, is_confirmed`.
  - `ExchangeRateForm`: all non-system fields.
  - ALL FK dropdowns in `__init__` must be scoped to `tenant` via the pattern:
    `self.fields['field'].queryset = Model.objects.filter(tenant=self.tenant)`.
  - `Currency` FK dropdowns: filter `is_active=True` (no tenant scope — it's global).

- [ ] `apps/accounting/views.py` — function-based views, `@login_required` on all.
  `@tenant_admin_required` (from `apps.core.decorators`) on: `fiscal_period_close`,
  `journal_entry_post`, `journal_entry_void`, `bill_approve`, `payment_confirm`,
  `payment_void`, `reconciliation_confirm`. Regular `@login_required` on all CRUD and list views.
  Tenant scope: every queryset uses `filter(tenant=request.tenant)`. No `Model.objects.all()`.
  Full CRUD views for every primary model: `*_list` (search + filters + pagination),
  `*_create`, `*_detail`, `*_edit`, `*_delete` (POST-only redirect).
  Custom action views (POST-only, `@require_POST`):
    - `journal_entry_post` — validate debit==credit sum; check fiscal_period open; set
      status=`posted`, posted_at=now(), created_by=request.user; call write_audit_log.
    - `journal_entry_void` — create reversal JournalEntry (reversal_of=original);
      set original status=`void`; call write_audit_log.
    - `bill_approve` — set Bill.status=`approved`, approved_by=request.user;
      write_audit_log; redirect to bill_detail.
    - `invoice_post` — mark Invoice.status=`sent`; auto-create posting JournalEntry
      (debit AR account / credit income account) if GL accounts are configured; write_audit_log.
    - `payment_confirm` — set Payment.status=`confirmed`; auto-create JournalEntry
      (debit/credit bank + AR/AP accounts); write_audit_log.
    - `payment_void` — set Payment.status=`void`; write_audit_log.
    - `fiscal_period_close` — check no open draft JournalEntries in period; set
      FiscalPeriod.status=`closed`, closed_by=request.user, closed_at=now(); write_audit_log.
    - `bank_transaction_import_csv` — POST with uploaded CSV file; parse rows; create
      BankTransaction rows (skip duplicates by external_ref); redirect to bank_transaction_list.
    - `reconciliation_confirm` — toggle ReconciliationMatch.is_confirmed; update linked
      BankTransaction.status to `reconciled`; write_audit_log.
  Report views (GET, no model changes):
    - `trial_balance` — aggregate posted JournalLine by GLAccount, compute debit_total /
      credit_total / balance; render as table.
    - `ar_aging` — aggregate open Invoice rows by due_date buckets vs today (current /
      1-30 / 31-60 / 61-90 / 90+); group by party.
    - `ap_aging` — same for Bill.
    - `gl_account_ledger` — posted JournalLines for one GLAccount, date-filtered.
  Dashboard view (`accounting_dashboard`) — compute and pass KPI context:
    `cash_position` (sum BankAccount opening_balance + net BankTransaction credits-debits),
    `ar_outstanding` (sum open Invoice.total),
    `ap_outstanding` (sum open Bill.total),
    `overdue_invoices` (Invoice where due_date < today and status not in paid/void),
    `overdue_bills` (Bill where due_date < today and status not in paid/void),
    `recent_je` (last 5 posted JournalEntries).
  Filter rules (CLAUDE.md mandatory):
    - All FK filters validated with `.isdigit()` guard before `filter(field_id=value)` (L11).
    - All status filter dropdowns pass `status_choices` in context.
    - All list views apply filters BEFORE pagination.

- [ ] `apps/accounting/urls.py` — `app_name = "accounting"`. URL names for EVERY model:
  **GLAccount:** `glaccounts/` → `glaccount_list`; `glaccounts/add/` → `glaccount_create`;
  `glaccounts/<int:pk>/` → `glaccount_detail`; `glaccounts/<int:pk>/edit/` → `glaccount_edit`;
  `glaccounts/<int:pk>/delete/` → `glaccount_delete`.
  **FiscalPeriod:** `fiscal-periods/` → `fiscal_period_list`; `.../add/` → `fiscal_period_create`;
  `.../<int:pk>/` → `fiscal_period_detail`; `.../edit/` → `fiscal_period_edit`;
  `.../delete/` → `fiscal_period_delete`; `.../close/` → `fiscal_period_close` (POST).
  **JournalEntry:** `journal-entries/` → `journal_entry_list`; `.../add/` → `journal_entry_create`;
  `.../<int:pk>/` → `journal_entry_detail`; `.../edit/` → `journal_entry_edit`;
  `.../delete/` → `journal_entry_delete`; `.../post/` → `journal_entry_post` (POST);
  `.../void/` → `journal_entry_void` (POST).
  **PaymentTerm:** `payment-terms/` → `payment_term_list`; `.../add/` → `payment_term_create`;
  `.../<int:pk>/` → `payment_term_detail`; `.../edit/` → `payment_term_edit`;
  `.../delete/` → `payment_term_delete`.
  **VendorProfile:** `vendor-profiles/` → `vendor_profile_list`; `.../add/` → `vendor_profile_create`;
  `.../<int:pk>/` → `vendor_profile_detail`; `.../edit/` → `vendor_profile_edit`;
  `.../delete/` → `vendor_profile_delete`.
  **CustomerProfile:** `customer-profiles/` → `customer_profile_list`; same 5 CRUD names
  `customer_profile_*`.
  **Invoice:** `invoices/` → `invoice_list`; `.../add/` → `invoice_create`;
  `.../<int:pk>/` → `invoice_detail`; `.../edit/` → `invoice_edit`;
  `.../delete/` → `invoice_delete`; `.../post/` → `invoice_post` (POST).
  **Bill:** `bills/` → `bill_list`; `.../add/` → `bill_create`;
  `.../<int:pk>/` → `bill_detail`; `.../edit/` → `bill_edit`;
  `.../delete/` → `bill_delete`; `.../approve/` → `bill_approve` (POST).
  **Payment:** `payments/` → `payment_list`; `.../add/` → `payment_create`;
  `.../<int:pk>/` → `payment_detail`; `.../edit/` → `payment_edit`;
  `.../delete/` → `payment_delete`; `.../confirm/` → `payment_confirm` (POST);
  `.../void/` → `payment_void` (POST).
  **PaymentAllocation:** `allocations/` → `allocation_list`; `.../add/` → `allocation_create`;
  `.../<int:pk>/` → `allocation_detail`; `.../edit/` → `allocation_edit`;
  `.../delete/` → `allocation_delete`.
  **BankAccount:** `bank-accounts/` → `bank_account_list`; `.../add/` → `bank_account_create`;
  `.../<int:pk>/` → `bank_account_detail`; `.../edit/` → `bank_account_edit`;
  `.../delete/` → `bank_account_delete`.
  **BankTransaction:** `bank-transactions/` → `bank_transaction_list`;
  `.../add/` → `bank_transaction_create`; `.../<int:pk>/` → `bank_transaction_detail`;
  `.../edit/` → `bank_transaction_edit`; `.../delete/` → `bank_transaction_delete`;
  `bank-transactions/import-csv/` → `bank_transaction_import_csv` (POST).
  **ReconciliationMatch:** `reconciliation/` → `reconciliation_list`;
  `.../add/` → `reconciliation_create`; `.../<int:pk>/` → `reconciliation_detail`;
  `.../edit/` → `reconciliation_edit`; `.../delete/` → `reconciliation_delete`;
  `.../confirm/` → `reconciliation_confirm` (POST).
  **ExchangeRate:** `exchange-rates/` → `exchange_rate_list`; `.../add/` → `exchange_rate_create`;
  `.../<int:pk>/` → `exchange_rate_detail`; `.../edit/` → `exchange_rate_edit`;
  `.../delete/` → `exchange_rate_delete`.
  **Currency:** `currencies/` → `currency_list`; `.../add/` → `currency_create`;
  `.../<int:pk>/` → `currency_detail`; `.../edit/` → `currency_edit`;
  `.../delete/` → `currency_delete`.
  **Reports and dashboard:**
  `dashboard/` → `accounting_dashboard`; `reports/trial-balance/` → `trial_balance`;
  `reports/ar-aging/` → `ar_aging`; `reports/ap-aging/` → `ap_aging`;
  `reports/ledger/<int:account_pk>/` → `gl_account_ledger`.

- [ ] `apps/accounting/admin.py` — `@admin.register` for every model.
  Common pattern: `list_display` includes `tenant`, human `number` where present,
  status, key FKs; `list_filter` on status + tenant; `search_fields`; `readonly_fields`
  for all system-set fields (numbers, `*_at`, `*_by`, `normal_balance`, totals).
  `JournalEntryAdmin`: `readonly_fields = ("number", "status", "created_by",
  "approved_by", "posted_at", "created_at", "updated_at")` — prevent admin users from
  manually posting/voiding outside the view workflow.
  `JournalLineAdmin`: inline under `JournalEntryAdmin` (`TabularInline`).
  `InvoiceLineAdmin`: inline under `InvoiceAdmin`.
  `BillLineAdmin`: inline under `BillAdmin`.
  `PaymentAllocationAdmin`: inline under `PaymentAdmin`.

- [ ] `apps/accounting/migrations/0001_initial.py` — generated via `makemigrations`.
  NOTE: run `makemigrations` AFTER all 18 model classes are complete; do NOT run it
  incrementally during model development. One migration file covering all 18 tables.

- [ ] `apps/accounting/management/__init__.py` — empty (required)
- [ ] `apps/accounting/management/commands/__init__.py` — empty (required)
- [ ] `apps/accounting/management/commands/seed_accounting.py` — idempotent seeder.
  Idempotency guard: at the top of each model block, `if Model.objects.filter(tenant=tenant).exists(): continue`.
  For Currency (global): `Currency.objects.get_or_create(code="USD", defaults={...})`.
  Seed data per tenant (2 tenants: acme, globex):
  - 4 Currencies: USD, EUR, GBP, CAD (get_or_create, global).
  - 1 ExchangeRate per non-USD currency per tenant for today's date.
  - ~15 GLAccounts per tenant (a minimal Chart of Accounts: 1000-Cash, 1100-AR,
    1200-Prepaid Expenses, 2000-AP, 2100-Accrued Liabilities, 3000-Owner Equity,
    4000-Revenue, 4100-Service Revenue, 5000-COGS, 6000-Operating Expenses,
    6100-Salaries, 6200-Rent, 6300-Utilities, 7000-Interest Expense, 8000-Tax Expense).
  - 2 FiscalPeriods per tenant (current month open, previous month closed).
  - 2 PaymentTerms: "Net 30" (days_due=30), "2/10 Net 30" (days_due=30,
    discount_pct=2, discount_days=10).
  - 1 BankAccount per tenant (linked to the 1000-Cash GLAccount).
  - Reuse existing `core.Party` vendor-role rows for VendorProfile creation
    (get Party where PartyRole.role='vendor', get_or_create VendorProfile).
  - Reuse existing `core.Party` customer-role rows for CustomerProfile creation.
  - 2 Invoices per tenant: one `sent` (with 2 lines), one `draft` (with 1 line);
    check by number before creating (`existing = Invoice.objects.filter(tenant=t, number=n).first()`).
  - 2 Bills per tenant: one `approved` (with 2 lines), one `draft`.
  - 1 Payment (direction='in') linked to the sent Invoice + 1 PaymentAllocation.
  - 3 BankTransactions per tenant: 2 matched, 1 unmatched.
  - 1 ReconciliationMatch per tenant.
  - 1 manual JournalEntry per tenant (status=`posted`, 2 lines: debit 1000-Cash / credit 4000-Revenue).
  - After seeding, print: `"Accounting module seeded. Login as admin_acme / password to verify."`
    and `"Superuser 'admin' has no tenant — data won't appear when logged in as admin."`

---

## Section 3 — Wire-up

- [ ] **`config/settings.py`** — add `"apps.accounting"` to `INSTALLED_APPS` (after `"apps.crm"`).
  NOTE: add ONLY after all model/views/urls files exist (L12/L24 — settings wire-up is last).

- [ ] **`config/urls.py`** — add `path("accounting/", include("apps.accounting.urls"))` to
  `urlpatterns` (after the `crm/` include). Use the string form to match project convention.

- [ ] **`apps/core/navigation.py`** — add `LIVE_LINKS` entries for sub-modules 2.1–2.5.
  Use the **exact NavERP.md bullet text** as keys (verified from NavERP.md §2):
  ```python
  "2.1": {
      "Executive Summary": "accounting:accounting_dashboard",
      "Cash Flow Widget": "accounting:accounting_dashboard",
      "Alert Center": "accounting:accounting_dashboard",
      "Quick Actions": "accounting:accounting_dashboard",
      "Custom Reports": "accounting:trial_balance",
      "Forecasting": "accounting:accounting_dashboard",
  },
  "2.2": {
      "Chart of Accounts": "accounting:glaccount_list",
      "Journal Entries": "accounting:journal_entry_list",
      "Journal Approval": "accounting:journal_entry_list",
      "Period Close": "accounting:fiscal_period_list",
      "Account Reconciliation": "accounting:trial_balance",
      "Allocation Rules": "accounting:glaccount_list",
      "Audit Trail": "accounting:journal_entry_list",
      "Multi-currency Support": "accounting:exchange_rate_list",
  },
  "2.3": {
      "Vendor Management": "accounting:vendor_profile_list",
      "Bill Capture": "accounting:bill_list",
      "Bill Processing": "accounting:bill_list",
      "Payment Processing": "accounting:payment_list",
      "Payment Scheduling": "accounting:payment_list",
      "Aging Reports": "accounting:ap_aging",
      "Vendor Portal": "accounting:vendor_profile_list",
      "Early Payment Discounts": "accounting:payment_term_list",
  },
  "2.4": {
      "Customer Management": "accounting:customer_profile_list",
      "Invoice Generation": "accounting:invoice_list",
      "Recurring Invoicing": "accounting:invoice_list",
      "Payment Collection": "accounting:payment_list",
      "Cash Application": "accounting:allocation_list",
      "Collections Management": "accounting:ar_aging",
      "Credit Management": "accounting:customer_profile_list",
      "Aging Analysis": "accounting:ar_aging",
      "Customer Portal": "accounting:invoice_list",
  },
  "2.5": {
      "Bank Account Management": "accounting:bank_account_list",
      "Bank Feeds": "accounting:bank_transaction_list",
      "Reconciliation Engine": "accounting:reconciliation_list",
      "Cash Positioning": "accounting:accounting_dashboard",
      "Treasury Forecasting": "accounting:accounting_dashboard",
      "Inter-company Transfers": "accounting:bank_transaction_list",
      "Bank Fee Analysis": "accounting:bank_transaction_list",
  },
  ```

---

## Section 4 — Templates (`templates/accounting/`)

One file per template; each mirrors the CRM template conventions (filter-bar with `request.GET`
pre-fill, Actions column: view/edit/delete for list, sidebar buttons for detail, pagination with
`has_previous`/`has_next` guards per L9, empty-state, breadcrumb). FK pk comparisons use
`|stringformat:"d"` (CLAUDE.md Filter Rule). Every `{% if fk %}…{% endif %}` guard on nullable
user FKs (L10). Edit/Delete buttons on immutable records (posted JEs, paid invoices) are hidden.

### Sub-module 2.1 — Dashboard

- [ ] `templates/accounting/dashboard.html` — the 2.1 overview page. Contains:
  KPI stat-cards row: cash position (sum), AR outstanding (sum), AP outstanding (sum);
  Overdue alert center: two tables (overdue invoices / overdue bills) with party name,
  amount, days overdue (`(today - due_date).days`), link to detail;
  Cash flow widget: Chart.js bar chart with 6 weeks of net cash (credits - debits from
  BankTransaction, passed as JSON from view context);
  Quick-action buttons: "New Invoice" → `accounting:invoice_create`; "Record Bill" →
  `accounting:bill_create`; "New Journal Entry" → `accounting:journal_entry_create`;
  "Reconcile Bank" → `accounting:reconciliation_list`;
  Recent journal entries table (last 5 posted).

### Sub-module 2.2 — GL templates

- [ ] `templates/accounting/glaccount_list.html` — table: code, name, account_type badge,
  parent link, is_active badge; filter: account_type + is_active dropdowns; Actions: view/edit/delete.
- [ ] `templates/accounting/glaccount_detail.html` — all fields; child accounts list;
  "View Ledger" link → `gl_account_ledger`; sidebar: edit/delete (block delete if has JournalLines).
- [ ] `templates/accounting/glaccount_form.html` — create/edit; parent field scoped to tenant GLAccounts.
- [ ] `templates/accounting/fiscal_period_list.html` — table: name, period_type badge, start/end date,
  status badge; Actions: view/edit/delete + "Close Period" button (POST, shown when status=open).
- [ ] `templates/accounting/fiscal_period_detail.html` — all fields; closed_by/closed_at if closed;
  "Close Period" action button in sidebar (conditional on status=open, @tenant_admin_required).
- [ ] `templates/accounting/fiscal_period_form.html` — create/edit; exclude closed_at/closed_by.
- [ ] `templates/accounting/journal_entry_list.html` — table: number, entry_date, entry_type badge,
  status badge, description, fiscal_period; filter: status + entry_type dropdowns + date range;
  Actions: view (always) / edit (only if draft) / delete (only if draft).
- [ ] `templates/accounting/journal_entry_detail.html` — header metadata; JournalLine table
  (account code+name, debit, credit, party, org_unit); debit/credit column totals;
  sidebar action buttons: "Post" (if draft, @tenant_admin_required), "Void" (if posted),
  "Create Reversal" (if posted); edit/delete (only if draft).
- [ ] `templates/accounting/journal_entry_form.html` — create/edit; inline JournalLine formset
  (dynamic add-row via minimal JS); exclude status/posted_at/created_by.
- [ ] `templates/accounting/trial_balance.html` — report page (no model form); table of all
  active GLAccounts with debit_total / credit_total / balance; grand totals row;
  date-range filter (start_date, end_date GET params).
- [ ] `templates/accounting/gl_account_ledger.html` — ledger for a single GLAccount; table of
  posted JournalLines with date, JE number, description, debit, credit, running balance;
  date-range filter; back link.
- [ ] `templates/accounting/exchange_rate_list.html` — table: currency code+name, rate_date, rate,
  source badge; filter: currency FK dropdown; Actions: view/edit/delete.
- [ ] `templates/accounting/exchange_rate_detail.html` — all fields; sidebar: edit/delete.
- [ ] `templates/accounting/exchange_rate_form.html` — create/edit form.
- [ ] `templates/accounting/currency_list.html` — table: code, name, symbol, is_active; Actions.
- [ ] `templates/accounting/currency_detail.html` — all fields; sidebar: edit/delete.
- [ ] `templates/accounting/currency_form.html` — create/edit form.

### Sub-module 2.3 — AP templates

- [ ] `templates/accounting/vendor_profile_list.html` — table: party name (link to core:party_detail),
  payment_terms, currency, is_1099 badge, is_active via Party; filter: payment_terms + is_1099 dropdowns;
  Actions: view/edit/delete.
- [ ] `templates/accounting/vendor_profile_detail.html` — VendorProfile fields + linked Party name;
  related Bills list (last 5); AP aging for this vendor; sidebar: edit/delete.
- [ ] `templates/accounting/vendor_profile_form.html` — create/edit form (party field scoped to
  tenant Parties with role=vendor; `payment_terms` and `default_expense_account` scoped to tenant).
- [ ] `templates/accounting/bill_list.html` — table: number, party name, bill_date, due_date,
  status badge, total; filter: status + party dropdowns; Actions: view/edit/delete + "Approve"
  button (shown when status=pending_approval).
- [ ] `templates/accounting/bill_detail.html` — header fields; BillLine table (description, qty,
  unit_price, tax_rate_pct, line_total, gl_account); subtotal/tax/total footer; linked document
  attachment; approved_by display; sidebar: "Approve" (if pending_approval, @tenant_admin_required),
  edit (if draft/pending only), delete (if draft only).
- [ ] `templates/accounting/bill_form.html` — create/edit; inline BillLine formset; exclude
  approved_by, journal_entry, subtotal, tax_total, total.
- [ ] `templates/accounting/ap_aging.html` — AP aging report: table grouped by party (vendor),
  columns: party name, current, 1-30, 31-60, 61-90, 90+ days, total; grand-total row;
  date-as-of filter (GET param).
- [ ] `templates/accounting/payment_term_list.html` — table: name, days_due, discount_pct,
  discount_days, is_active; Actions: view/edit/delete.
- [ ] `templates/accounting/payment_term_detail.html` — all fields; sidebar: edit/delete.
- [ ] `templates/accounting/payment_term_form.html` — create/edit.

### Sub-module 2.4 — AR templates

- [ ] `templates/accounting/customer_profile_list.html` — table: party name, payment_terms,
  credit_limit, credit_on_hold badge; filter: payment_terms + credit_on_hold dropdowns; Actions.
- [ ] `templates/accounting/customer_profile_detail.html` — CustomerProfile fields + Party name;
  related Invoices list (last 5); AR aging for this customer; sidebar: edit/delete.
- [ ] `templates/accounting/customer_profile_form.html` — create/edit; party scoped to
  tenant Parties with role=customer.
- [ ] `templates/accounting/invoice_list.html` — table: number, kind badge, party name, issue_date,
  due_date, status badge, total; filter: status + kind + party dropdowns; Actions: view/edit/delete
  + "Post/Send" button (shown when draft).
- [ ] `templates/accounting/invoice_detail.html` — header fields; InvoiceLine table; totals;
  linked journal_entry link; linked PaymentAllocations (amount paid, remaining balance);
  credit limit warning if CustomerProfile.credit_on_hold; sidebar: "Post" (if draft),
  edit (if draft/sent only), delete (if draft only).
- [ ] `templates/accounting/invoice_form.html` — create/edit; inline InvoiceLine formset;
  credit limit check: render warning banner if party's CustomerProfile.credit_limit is exceeded
  by outstanding Invoices (computed in view context); exclude journal_entry, subtotal, tax_total, total.
- [ ] `templates/accounting/ar_aging.html` — AR aging report: same structure as AP aging but for
  Invoices and customers.
- [ ] `templates/accounting/allocation_list.html` — table: payment number, invoice number / bill
  number, allocated_amount, discount_taken; filter: payment FK dropdown; Actions: view/edit/delete.
- [ ] `templates/accounting/allocation_detail.html` — all fields; links to payment + invoice/bill.
- [ ] `templates/accounting/allocation_form.html` — create/edit; payment, invoice, bill scoped to
  tenant.

### Sub-module 2.4+2.3 — Shared Payment templates

- [ ] `templates/accounting/payment_list.html` — table: number, direction badge (in=green/out=red),
  party name, bank_account, payment_method badge, payment_date, amount, status badge; filter:
  direction + status + payment_method dropdowns; Actions: view/edit/delete + "Confirm" (if draft)
  + "Void" (if confirmed).
- [ ] `templates/accounting/payment_detail.html` — all fields; linked PaymentAllocations table
  (invoice/bill + amount + discount); sidebar: "Confirm" (if draft), "Void" (if confirmed),
  edit (if draft only), delete (if draft only).
- [ ] `templates/accounting/payment_form.html` — create/edit; exclude status, journal_entry;
  party scoped to tenant; bank_account scoped to tenant.

### Sub-module 2.5 — Cash Management templates

- [ ] `templates/accounting/bank_account_list.html` — table: name, bank_name, currency, gl_account,
  opening_balance, is_active badge; filter: currency + is_active dropdowns; Actions: view/edit/delete.
- [ ] `templates/accounting/bank_account_detail.html` — all fields (account_number_last4 masked);
  recent BankTransactions list (last 10); current balance (opening_balance + net transactions);
  sidebar: edit/delete.
- [ ] `templates/accounting/bank_account_form.html` — create/edit.
- [ ] `templates/accounting/bank_transaction_list.html` — table: bank_account, transaction_date,
  description, amount, direction badge, source badge, status badge; filter: bank_account +
  direction + status dropdowns; "Import CSV" button → `bank_transaction_import_csv`;
  Actions: view/edit/delete.
- [ ] `templates/accounting/bank_transaction_detail.html` — all fields; linked
  ReconciliationMatch if any; sidebar: edit (if unmatched only) / delete (if unmatched only).
- [ ] `templates/accounting/bank_transaction_form.html` — create/edit (manual entry);
  exclude status.
- [ ] `templates/accounting/bank_transaction_import.html` — CSV import form: file upload field
  (`<input type="file" accept=".csv">`), bank_account selector, submit button; instructions block
  (expected columns: date, description, amount, direction).
- [ ] `templates/accounting/reconciliation_list.html` — table: bank_transaction (date + desc),
  payment / journal_line link, matched_by, matched_at, is_confirmed badge; filter: bank_account
  + is_confirmed dropdowns; Actions: view/edit/delete + "Confirm" toggle button.
- [ ] `templates/accounting/reconciliation_detail.html` — all fields; bank_transaction detail;
  payment/journal_line detail; sidebar: "Confirm/Unconfirm" action, edit, delete.
- [ ] `templates/accounting/reconciliation_form.html` — create/edit; bank_transaction, payment,
  journal_line scoped to tenant.

---

## Section 5 — Verify

Run all commands with the venv Python (`C:\xampp\htdocs\NavERP\venv\Scripts\python.exe`):

- [ ] `venv\Scripts\python.exe manage.py makemigrations accounting` — confirm single migration
  `0001_initial.py` generated covering all 18 models.
- [ ] `venv\Scripts\python.exe manage.py sqlmigrate accounting 0001` — review SQL; confirm all FK
  references resolve, `unique_together` constraints present, `db_index` on tenant FKs, no
  reference to non-existent tables.
- [ ] `venv\Scripts\python.exe manage.py migrate` — zero errors on `nav_erp`.
- [ ] `venv\Scripts\python.exe manage.py seed_accounting` — first run: seeds all demo data;
  prints login instructions and superuser-no-tenant warning.
- [ ] `venv\Scripts\python.exe manage.py seed_accounting` (second run) — must print "already
  exists — skipping" for every model block; zero duplicate rows; idempotent confirmed.
- [ ] `venv\Scripts\python.exe manage.py check` — zero errors, zero warnings.
- [ ] Write `temp/accounting_smoke.py` — test-client sweep (Django test Client, logged in as
  `admin_acme` / `password`):
  - All `accounting:*` URL names (list, detail, create, edit) → 200 or 302 (never 500).
  - POST action URLs (journal_entry_post, bill_approve, payment_confirm) → 302 redirect (never 500).
  - No `{#` or `{% comment` template leaks in rendered HTML for any URL.
  - Cross-tenant IDOR: for each pk-based URL, try the pk from globex while logged in as acme →
    must return 404 (not 200 or 500).
  - Double-entry invariant: attempt to POST a `journal_entry_post` action when
    sum(debit) != sum(credit) → view must reject (stay on page with error, not redirect).
  - Posting into a closed FiscalPeriod → view must reject.
  - A confirmed/posted JournalEntry pk → edit URL → form save must fail / redirect to detail
    (immutability gate).
  - CSV import URL → GET returns 200; POST with a valid 3-row CSV creates 3 BankTransaction
    rows (idempotent: second import with same external_ref skips duplicates).
  - Trial balance URL → 200 with no missing template variables.
  - AR aging / AP aging URLs → 200.
- [ ] Run `temp/accounting_smoke.py` — all checks green.
- [ ] Sidebar check: sub-modules 2.1, 2.2, 2.3, 2.4, 2.5 all show as **Live** (not "On the roadmap")
  in the sidebar navigation.

---

## Section 6 — Close-out

### Review agents (run in this exact order, one at a time, commit fixes between)

- [ ] Run **`code-reviewer` agent** — check: double-entry invariant enforcement in
  `journal_entry_post` view; immutability guards on posted JE / paid Invoice / paid Bill;
  fiscal period close check before posting; L11 integer FK filter guard (.isdigit()) on all
  list views; L22 DateTimeField exclusions from all forms; L10 nullable FK display guards in
  templates; `@tenant_admin_required` on all privileged action views; `tenant_id` filter on
  ALL querysets; `approved_by` / `created_by` / `posted_at` never on ModelForm fields.
  Apply findings; commit each changed file separately (PowerShell-safe).

- [ ] Run **`explorer` agent** — explore the built module for gaps: any URL name in
  `navigation.py` that 404s; any view reachable from a template link that doesn't exist in
  `urls.py`; any context variable used in a template that the view doesn't pass; any inline
  formset that the form/template doesn't render. Apply findings; commit.

- [ ] Run **`frontend-reviewer` agent** — check: filter-bar `selected` comparisons use
  `|stringformat:"d"` for FK pks; all form `<label for=id_field>` present; pagination guards
  use `has_previous`/`has_next` (L9); no `text-danger` / unknown CSS utility class (L13);
  dashboard Chart.js data correctly JSON-serialized; debit/credit columns visually distinct;
  badge colors consistent (status → color map). Apply findings; commit.

- [ ] Run **`performance-reviewer` agent** — check: N+1 on JournalLine lists
  (`select_related("gl_account", "entry", "party", "org_unit")`); N+1 on Invoice/Bill lists
  (`select_related("party", "currency", "payment_terms")`); trial_balance aggregate query
  (should be a single GROUP BY, not Python loops); AR/AP aging report queries (subquery vs.
  Python bucketing); dashboard KPI queries (check query count); BankTransaction list pagination
  correct for large import sets. Apply findings; commit.

- [ ] Run **`qa-smoke-tester` agent** — run the module's full smoke coverage with its own
  structured test script; verify all action views require POST; verify all delete views are
  POST-only; verify CSV import handles malformed rows gracefully (no 500); verify
  PaymentAllocation total does not exceed Payment.amount (data integrity); verify
  credit-limit warning renders on invoice create form. Apply findings; commit.

- [ ] Run **`security-reviewer` agent** — check: all `@tenant_admin_required` gates correct
  (journal_entry_post, bill_approve, payment_confirm, fiscal_period_close); cross-tenant IDOR
  on all pk-based views; CSV import file extension + size validation (allowlist `.csv` only,
  reject `.exe`/`.php`/etc., max 5 MB); `account_number_last4` field never stores full account
  number; `normal_balance` is read-only (not on any form); mass-assignment check (no system
  fields on any ModelForm); `reversal_of` FK only set by the void/reversal action view, never
  by the user form; posted JE immutability cannot be bypassed via direct form POST. Apply
  findings; commit.

- [ ] Run **`test-writer` agent** — write tests for:
  double-entry balance validation (sum mismatch → reject post),
  fiscal period blocking (closed period → reject post),
  JE immutability (posted JE → edit blocked),
  invoice credit limit warning (CustomerProfile.credit_limit exceeded → context flag),
  AR/AP aging bucket placement (due_date = today-45 → 31-60 bucket),
  bill_approve requires @tenant_admin_required,
  payment_confirm requires @tenant_admin_required,
  CSV import idempotency (duplicate external_ref skipped),
  cross-tenant IDOR 404 for all pk-based views,
  seeder idempotency (seed twice → row count unchanged),
  PaymentAllocation allocated_amount <= Payment.amount validation.
  Apply output; commit each test file.

### Documentation close-out

- [ ] Create **`.claude/skills/accounting/SKILL.md`** — as-built module skill (all 18 models,
  url names, seeder description, LIVE_LINKS entries 2.1–2.5, double-entry invariant conventions,
  gotchas: Currency is global/not tenant-scoped; GLAccount balance is always derived; posted JE
  is immutable; BankAccount must be defined before Payment in models.py). Commit.
- [ ] Update **`README.md`** — add accounting module to feature table; add seeder section
  (`seed_accounting`); add route map for accounting:*; update module status table (Module 2 built).
  Commit.

### Per-file commit list (PowerShell-safe, one file per commit — reference for the build step)

```
git add 'apps\accounting\__init__.py'; git commit -m 'feat(accounting): app package init'
git add 'apps\accounting\apps.py'; git commit -m 'feat(accounting): AppConfig — apps.accounting'
git add 'apps\accounting\models.py'; git commit -m 'feat(accounting): 18 models — Currency/ExchangeRate/GLAccount/FiscalPeriod/JournalEntry/JournalLine/PaymentTerm/VendorProfile/CustomerProfile/BankAccount/Invoice/InvoiceLine/Bill/BillLine/Payment/PaymentAllocation/BankTransaction/ReconciliationMatch'
git add 'apps\accounting\migrations\0001_initial.py'; git commit -m 'feat(accounting): initial migration — 18 accounting models'
git add 'apps\accounting\forms.py'; git commit -m 'feat(accounting): forms for all 18 models (system fields excluded per L22)'
git add 'apps\accounting\views.py'; git commit -m 'feat(accounting): function-based views — full CRUD + post/void/approve/confirm/close/import-csv/trial-balance/aging/ledger/dashboard'
git add 'apps\accounting\urls.py'; git commit -m 'feat(accounting): URL patterns (app_name=accounting) — all 18 models + reports + dashboard'
git add 'apps\accounting\admin.py'; git commit -m 'feat(accounting): admin registration for all 18 models with inline formsets'
git add 'apps\accounting\management\__init__.py'; git commit -m 'feat(accounting): management package init'
git add 'apps\accounting\management\commands\__init__.py'; git commit -m 'feat(accounting): management/commands package init'
git add 'apps\accounting\management\commands\seed_accounting.py'; git commit -m 'feat(accounting): idempotent seed_accounting — CoA/periods/terms/bank/invoices/bills/payments/JEs/reconciliation for 2 tenants'
git add 'config\settings.py'; git commit -m 'feat(config): add apps.accounting to INSTALLED_APPS'
git add 'config\urls.py'; git commit -m 'feat(config): include accounting/ URLs'
git add 'apps\core\navigation.py'; git commit -m 'feat(core/nav): LIVE_LINKS 2.1-2.5 — dashboard/GL/AP/AR/cash management routes'
git add 'templates\accounting\dashboard.html'; git commit -m 'feat(accounting): 2.1 dashboard — KPI cards, overdue alert center, cash flow chart, quick actions'
git add 'templates\accounting\glaccount_list.html'; git commit -m 'feat(accounting): GL account list with account_type/is_active filters'
git add 'templates\accounting\glaccount_detail.html'; git commit -m 'feat(accounting): GL account detail with child accounts and ledger link'
git add 'templates\accounting\glaccount_form.html'; git commit -m 'feat(accounting): GL account create/edit form'
git add 'templates\accounting\fiscal_period_list.html'; git commit -m 'feat(accounting): fiscal period list with close-period action'
git add 'templates\accounting\fiscal_period_detail.html'; git commit -m 'feat(accounting): fiscal period detail with close action (tenant_admin_required)'
git add 'templates\accounting\fiscal_period_form.html'; git commit -m 'feat(accounting): fiscal period create/edit form'
git add 'templates\accounting\journal_entry_list.html'; git commit -m 'feat(accounting): journal entry list with status/type filters, edit/delete gated on draft status'
git add 'templates\accounting\journal_entry_detail.html'; git commit -m 'feat(accounting): journal entry detail with JE lines table, post/void/reversal actions'
git add 'templates\accounting\journal_entry_form.html'; git commit -m 'feat(accounting): journal entry create/edit form with inline JournalLine formset'
git add 'templates\accounting\trial_balance.html'; git commit -m 'feat(accounting): trial balance report — GLAccount debit/credit totals, date-range filter'
git add 'templates\accounting\gl_account_ledger.html'; git commit -m 'feat(accounting): GL account ledger — posted JE lines, running balance, date filter'
git add 'templates\accounting\exchange_rate_list.html'; git commit -m 'feat(accounting): exchange rate list'
git add 'templates\accounting\exchange_rate_detail.html'; git commit -m 'feat(accounting): exchange rate detail'
git add 'templates\accounting\exchange_rate_form.html'; git commit -m 'feat(accounting): exchange rate create/edit form'
git add 'templates\accounting\currency_list.html'; git commit -m 'feat(accounting): currency list'
git add 'templates\accounting\currency_detail.html'; git commit -m 'feat(accounting): currency detail'
git add 'templates\accounting\currency_form.html'; git commit -m 'feat(accounting): currency create/edit form'
git add 'templates\accounting\vendor_profile_list.html'; git commit -m 'feat(accounting): vendor profile list with payment_terms/1099 filters'
git add 'templates\accounting\vendor_profile_detail.html'; git commit -m 'feat(accounting): vendor profile detail with related bills and AP aging'
git add 'templates\accounting\vendor_profile_form.html'; git commit -m 'feat(accounting): vendor profile create/edit form'
git add 'templates\accounting\bill_list.html'; git commit -m 'feat(accounting): bill list with status/party filters and approve action'
git add 'templates\accounting\bill_detail.html'; git commit -m 'feat(accounting): bill detail with line items, document attachment, approve action'
git add 'templates\accounting\bill_form.html'; git commit -m 'feat(accounting): bill create/edit form with inline BillLine formset'
git add 'templates\accounting\ap_aging.html'; git commit -m 'feat(accounting): AP aging report — buckets by vendor'
git add 'templates\accounting\payment_term_list.html'; git commit -m 'feat(accounting): payment term list'
git add 'templates\accounting\payment_term_detail.html'; git commit -m 'feat(accounting): payment term detail'
git add 'templates\accounting\payment_term_form.html'; git commit -m 'feat(accounting): payment term create/edit form'
git add 'templates\accounting\customer_profile_list.html'; git commit -m 'feat(accounting): customer profile list with credit_on_hold filter'
git add 'templates\accounting\customer_profile_detail.html'; git commit -m 'feat(accounting): customer profile detail with related invoices and AR aging'
git add 'templates\accounting\customer_profile_form.html'; git commit -m 'feat(accounting): customer profile create/edit form'
git add 'templates\accounting\invoice_list.html'; git commit -m 'feat(accounting): invoice list with kind/status/party filters and post action'
git add 'templates\accounting\invoice_detail.html'; git commit -m 'feat(accounting): invoice detail with line items, payment allocations, credit limit warning'
git add 'templates\accounting\invoice_form.html'; git commit -m 'feat(accounting): invoice create/edit form with inline InvoiceLine formset and credit limit check'
git add 'templates\accounting\ar_aging.html'; git commit -m 'feat(accounting): AR aging report — buckets by customer'
git add 'templates\accounting\allocation_list.html'; git commit -m 'feat(accounting): payment allocation list'
git add 'templates\accounting\allocation_detail.html'; git commit -m 'feat(accounting): payment allocation detail'
git add 'templates\accounting\allocation_form.html'; git commit -m 'feat(accounting): payment allocation create/edit form'
git add 'templates\accounting\payment_list.html'; git commit -m 'feat(accounting): payment list with direction/status/method filters, confirm/void actions'
git add 'templates\accounting\payment_detail.html'; git commit -m 'feat(accounting): payment detail with allocations table, confirm/void sidebar actions'
git add 'templates\accounting\payment_form.html'; git commit -m 'feat(accounting): payment create/edit form'
git add 'templates\accounting\bank_account_list.html'; git commit -m 'feat(accounting): bank account list with currency/active filters'
git add 'templates\accounting\bank_account_detail.html'; git commit -m 'feat(accounting): bank account detail with recent transactions and current balance'
git add 'templates\accounting\bank_account_form.html'; git commit -m 'feat(accounting): bank account create/edit form'
git add 'templates\accounting\bank_transaction_list.html'; git commit -m 'feat(accounting): bank transaction list with bank_account/direction/status filters, CSV import link'
git add 'templates\accounting\bank_transaction_detail.html'; git commit -m 'feat(accounting): bank transaction detail with reconciliation match link'
git add 'templates\accounting\bank_transaction_form.html'; git commit -m 'feat(accounting): bank transaction manual entry form'
git add 'templates\accounting\bank_transaction_import.html'; git commit -m 'feat(accounting): bank transaction CSV import page with column format instructions'
git add 'templates\accounting\reconciliation_list.html'; git commit -m 'feat(accounting): reconciliation match list with bank_account/confirmed filters'
git add 'templates\accounting\reconciliation_detail.html'; git commit -m 'feat(accounting): reconciliation match detail with confirm/unconfirm toggle'
git add 'templates\accounting\reconciliation_form.html'; git commit -m 'feat(accounting): reconciliation match create/edit form'
git add 'temp\accounting_smoke.py'; git commit -m 'test(accounting): smoke test — all accounting:* routes 200/302, double-entry invariant, IDOR 404, CSV import, immutability gate'
git add '.claude\skills\accounting\SKILL.md'; git commit -m 'docs(skill/accounting): SKILL.md — 18 models, routes, seeder, invariants, LIVE_LINKS 2.1-2.5'
git add 'README.md'; git commit -m 'docs(readme): accounting module — feature table, seeder logins, route map, module status'
```

---

## Section 7 — Later passes / deferred

- **Bank Feeds via Plaid / Yodlee / Open Banking** — `BankTransaction.source='bank_feed'` is modeled;
  the external API connector and daily sync webhook are a separate integration pass. Model is ready.
- **OCR / AI Bill Capture** — `core.Document` attachment is on `Bill`; the OCR-to-form-prefill
  (Veryfi / AWS Textract) is an integration/later pass. UI file upload already works.
- **AI Cash Flow Forecasting** — ML 30/90-day liquidity projection reads Invoice + Bill +
  BankTransaction; deferred to a BI/analytics pass (Module 10). Dashboard shows static sum today.
- **Customer Portal (self-service invoice view/pay)** — public-facing portal + payment gateway
  (Stripe, PayPal) integration. Model is ready; the portal + OAuth token flow is a separate pass.
- **Allocation Rules Engine (departmental cost splits)** — automatic percentage/proportional
  JournalLine splits across OrgUnits. New `AllocationRule` table; deferred (complex rule engine).
- **1099 / W-9 Form Generation** — `VendorProfile.is_1099` flag is built; generating compliant
  PDF 1099-MISC / 1099-NEC forms requires a US-localization pass (deferred).
- **Fixed Assets (sub-module 2.6)** — Asset Register, depreciation engine, disposals. Scoped to
  a future NavERP Module 11 (Assets). `GLAccount` capitalization account linkage already exists.
- **Revenue Recognition (ASC 606 / IFRS 15)** — deferred revenue schedules, performance obligation
  tracking; a later Accounting extension pass for SaaS/subscription businesses.
- **Custom Report Builder** — drag-and-drop financial report designer; deferred to BI module (10).
- **Recurring Journal Entry auto-posting scheduler** — `RecurringJournal` template storage + Celery
  beat job are deferred to a task-queue integration pass. Manual "post now" action is MVP.
- **Dunning auto-send** — `DunningRule` storage and AR aging are in scope; auto-emailing customers
  requires SMTP/SendGrid integration (deferred to notifications pass).
- **Sub-modules 2.6 Fixed Assets, 2.7 Inventory & Cost, 2.8 Payroll, 2.9 Project/Job Costing,
  2.10 Multi-Entity Consolidation** — all deferred to later passes or their respective modules
  (Inventory = Module 5, Payroll within HRM = Module 3, Project Costing within Projects = Module 7).
- **FX Gain/Loss revaluation journal** — period-end unrealized gain/loss from ExchangeRate
  movements on open Invoices/Bills denominated in foreign currency. The data model supports it;
  deferred to a multi-currency hardening pass.
- **Inter-account Transfers UI** — the two-JournalLine / two-BankTransaction pattern for inter-bank
  transfers is documented; a dedicated "Transfer" action view is a convenience UX deferred item.

## Review notes — Module 2 build outcome (2026-06-21)

**Built:** 18 models (the GL spine, owned by `accounting` per L28), full CRUD + 9 workflow actions
(post/void/approve/confirm/close/import-csv/reconcile) + 4 reports + dashboard, 51 templates, idempotent
`seed_accounting`, LIVE_LINKS 2.1–2.5. Migrated clean to `nav_erp`; seeder idempotent; `manage.py check` clean;
per-tenant posted ledger balances (Σdebit==Σcredit). Backend built solo (financial correctness); 51 templates via a
6-agent parallel Workflow against a pinned context-var spec (zero L7 drift — smoke passed first try).

**Verification:** custom GET smoke (81 routes 200/302, no comment leaks, cross-tenant IDOR 404); qa-smoke-tester
50/50 (workflow paths, immutability, period-close, void-reversal, CSV idempotency, CSRF, POST-only); query-count
checks (aging/trial-balance 8q, dashboard fixed-cost); test-writer **74 pytest tests** (suite 850 → **924**, no regressions).

**Review agents (all 7 run, in order):**
- **code-reviewer** → fixed: `payment_void` now posts a balanced GL reversal; `status` removed from `FiscalPeriodForm`
  (privilege bypass); auth decorators outermost on all POST actions; `reconciliation_confirm` refreshes `updated_at`;
  `invoice_post` warns on skipped GL; seeded payment carries a real JE. (False positives rejected: PaymentAllocation
  FK scoping, posted-only delete guard, alloc.payment null guard, trial-balance sign — all verified non-issues.)
- **explorer** → zero wiring gaps (routes, url tags, context vars, formsets, filter context all clean); 2 N+1 notes
  routed to performance-reviewer.
- **frontend-reviewer** → gated 10 admin-only action buttons behind `is_tenant_admin`; added nullable-FK guards;
  removed hard-coded `$`/inline `text-align` in bill templates; hid Delete on non-open periods.
- **performance-reviewer** → killed N+1s: dashboard cash-position (1 grouped aggregate, was N), AR/AP aging
  (`paid_agg` annotation, was per-doc), added `journal_line__entry`/`matched_by` select_related, dropped unused JE
  join, CSV import dedupes in one query + `bulk_create` inside `atomic()`.
- **qa-smoke-tester** → 50/50 PASS, no code changes.
- **security-reviewer** → fixed: `journal_line` cross-tenant scoping in `ReconciliationMatchForm` (H3); `status`
  off Invoice/Bill forms + `source` off BankTransaction form (mass-assignment); `invoice_post` + Currency CRUD
  now `@tenant_admin_required` (H2/L1); CSV bank-account ownership re-check (M2). Added `recompute_payment_status`
  so partial/paid derive from *confirmed* allocations (lifecycle completion).
- **test-writer** → 74 tests across double-entry / lifecycle / security / csv / seeder.

**Deferred (documented in Section 7):** invoice/bill **void** actions + per-tenant configurable AR/AP control
accounts (today the auto-post heuristic picks the first 1100/2000 account), gl_account_ledger pagination,
6-week trend single-query (TruncWeek), bank feeds/OCR/forecasting/portal/dunning, sub-modules 2.6–2.15.

---

# Module 2 Advanced — Accounting 2.6–2.15 (accounting)  — plan from research-accounting-advanced.md  (2026-06-21)

## Section 0 — Architecture constraints (read before touching any file)

> **KEY RULES — violating any of these is a build-stopper.**
>
> 1. **No inline formsets.** Every child table (PayrollJournalLine, ProjectBudgetLine, BudgetLine,
>    ControlTest, etc.) is its own standalone list/create/edit/delete CRUD — no formset on any parent
>    page. This eliminates the most expensive part of the original 21-model research proposal.
>
> 2. **~14 accounting-OWNED models this pass** (trimmed from research's 21). Child tables that have
>    no user-facing list of their own (DepreciationSchedule) are owned exclusively through their
>    parent's action views and admin. See Section 1 for the exact scope.
>
> 3. **File layout — extend, don't overwrite:**
>    - New models → `apps/accounting/models_advanced.py`; bottom of `apps/accounting/models.py`
>      gains one line: `from .models_advanced import *  # noqa`
>    - New forms → `apps/accounting/forms_advanced.py`; imported at the top of
>      `apps/accounting/views_advanced.py`
>    - New views → `apps/accounting/views_advanced.py`
>    - New URL patterns → appended to the existing `urlpatterns` list in
>      `apps/accounting/urls.py` (same file, no new urls file)
>    - New admin entries → appended to `apps/accounting/admin.py` (same file)
>    - Migration → `apps/accounting/migrations/0002_advanced.py` (generated via makemigrations)
>    - Seeder → extend the existing `seed_accounting` command to call a new
>      `_seed_advanced(tenant)` helper function; idempotency guard at the top of each model block
>
> 4. **Every workflow action posts a BALANCED JournalEntry** (Σdebit == Σcredit, enforced inside
>    `transaction.atomic()`) using the existing helpers from `views.py`:
>    `_first_account(tenant, account_type, code_prefix)`, `_open_period(tenant)`,
>    `_reverse_journal_entry(tenant, user, original)`. Posting actions are `@tenant_admin_required`
>    POST-only views.
>
> 5. **Reuse, never rebuild:**
>    - Spine: `accounting.GLAccount`, `accounting.JournalEntry`/`JournalLine`,
>      `accounting.FiscalPeriod`, `accounting.Currency`, `accounting.Payment` (for tax remittances).
>    - Core: `core.Party` (clients/employees/custodians), `core.OrgUnit` (cost centre / department /
>      legal entity / consolidation entity — do NOT create a new Entity table), `core.Document`
>      (evidence attachment), `core.AuditLog` / `write_audit_log`.
>    - Local abstract bases: import `TenantOwned` and `TenantNumbered` from `.models` (not from crm).
>    - Do NOT depend on unbuilt masters: no `inventory.Item`, no `StockMove`, no `hrm.PayrollRun`,
>      no `projects.Project` (L28). The advanced models are self-contained or FK into confirmed-built
>      `accounting.*` and `core.*` tables only.
>
> 6. **Security (L20/L25):** `IntegrationConfig.api_key_encrypted` stores ONLY a
>    `prefix + ":" + sha256_hex` string — never the raw secret. The field is EXCLUDED from the
>    ModelForm. A separate write-only "rotate key" POST action is the only entry point for
>    updating the credential.
>
> 7. **L22 rule:** all system-set `*_at` DateTimeFields (`posted_at`, `disposed_at`,
>    `last_synced_at`, `completed_at`, etc.) are EXCLUDED from every ModelForm. Only genuine
>    user-set `DateField`s get a widget.

---

## Section 1 — Models (14 accounting-owned tables + 3 field migrations on existing tables)

All new models live in `apps/accounting/models_advanced.py`. Import `TenantOwned` and
`TenantNumbered` from `.models`. All have `tenant` FK → `"core.Tenant"` (except
`DepreciationSchedule`/`PayrollJournalLine`/`BudgetLine`/`ControlTest`/`PeriodCloseTask` which
are child tables that inherit tenant from their parent FK and therefore omit a direct tenant FK,
mirroring the `JournalLine` / `PaymentAllocation` pattern).

### 2.6 Fixed Assets — 2 primary models + 1 child

- [ ] **`FixedAsset`** [PREFIX `FA`] — extends `TenantNumbered`; the asset register.
  Fields:
  - `asset_class` CharField max_length=100 (e.g. "Machinery", "Furniture", "Vehicles")
  - `description` TextField blank
  - `serial_number` CharField max_length=100 blank
  - `acquisition_cost` DecimalField max_digits=18 decimal_places=2
  - `acquisition_date` DateField
  - `in_service_date` DateField null blank (set when status moves from cip → active)
  - `salvage_value` DecimalField max_digits=14 decimal_places=2 default=0
  - `useful_life_months` PositiveSmallIntegerField default=60
  - `depreciation_method` CharField choices
    `[("straight_line","Straight-Line"),("declining_balance","Declining Balance"),
    ("units_of_production","Units of Production")]` default `"straight_line"`
  - `status` CharField choices
    `[("cip","Construction in Progress"),("active","Active"),
    ("disposed","Disposed"),("retired","Retired")]` default `"active"`
  - `accumulated_depreciation` DecimalField max_digits=18 decimal_places=2 default=0
    (updated by the `depreciation_run` action — EXCLUDE from ModelForm; displayed on detail page)
  - `asset_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"fixed_asset_accounts"` (the fixed asset balance account, e.g. 1500-Equipment)
  - `accum_depr_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"fixed_asset_accum_depr"` (accumulated depreciation contra account)
  - `depr_expense_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"fixed_asset_depr_expense"` (depreciation expense account)
  - `custodian` FK → `"core.Party"` SET_NULL null blank related_name `"custodied_assets"`
    (employee or department custodian; driver: Asset Register — custodian tracking)
  - `location` FK → `"core.OrgUnit"` SET_NULL null blank related_name `"located_assets"`
    (department/location; driver: Asset Transfers — inter-department moves)
  - `capitalization_je` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"capitalized_assets"` editable=False
    (JE posted at acquisition — system-set by `asset_capitalize` action)
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, status)`, `(tenant, acquisition_date)`
  - Drivers: Asset Register (NetSuite/Sage/Xero/QB), CIP status (NetSuite/D365/SAP),
    custodian/location tracking (NetSuite/Sage/D365)

- [ ] **`DepreciationSchedule`** — child of `FixedAsset`, no auto-number, no direct tenant FK
  (tenant inherited via asset FK; mirrors JournalLine pattern).
  Fields:
  - `asset` FK → `"accounting.FixedAsset"` CASCADE related_name `"depreciation_schedules"`
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` SET_NULL null blank
    related_name `"depreciation_schedules"`
  - `book_type` CharField choices
    `[("book","Book / GAAP"),("tax","Tax / MACRS"),("ifrs","IFRS")]` default `"book"`
  - `period_depr_amount` DecimalField max_digits=18 decimal_places=2
  - `accum_depr_to_date` DecimalField max_digits=18 decimal_places=2
  - `status` CharField choices `[("scheduled","Scheduled"),("posted","Posted")]` default `"scheduled"`
  - `journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"depreciation_schedules"` editable=False (system-set on post)
  - Indexes: `(asset, fiscal_period, book_type)` unique_together
  - No standalone CRUD list page; accessed via FixedAsset detail + admin.
  - Drivers: Depreciation Engine (all 6 platforms), Parallel Tax Books (NetSuite/Sage/D365/SAP)

- [ ] **`AssetDisposal`** [PREFIX `DISP`] — extends `TenantNumbered`; records a disposal event.
  Fields:
  - `asset` FK → `"accounting.FixedAsset"` CASCADE related_name `"disposals"`
  - `disposal_date` DateField
  - `disposal_type` CharField choices
    `[("sale","Sale"),("scrap","Scrap"),("donation","Donation"),("transfer","Transfer")]`
    default `"sale"`
  - `proceeds` DecimalField max_digits=18 decimal_places=2 default=0
  - `gain_loss` DecimalField max_digits=18 decimal_places=2 default=0 editable=False
    (computed = proceeds − (acquisition_cost − accumulated_depreciation); system-set by
    `asset_dispose` action — EXCLUDE from ModelForm)
  - `cash_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"disposal_cash_accounts"`
  - `gain_loss_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"disposal_gain_loss_accounts"`
  - `journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"asset_disposals"` editable=False
  - `notes` TextField blank
  - `unique_together = ("tenant", "number")`
  - Drivers: Asset Disposal/Retirement (NetSuite/Sage/Xero/D365/SAP)
  - JE legs on `asset_dispose` action:
    Dr `accum_depr_gl_account` (accumulated depreciation cleared)
    Dr `cash_gl_account` (proceeds received)
    Dr `gain_loss_gl_account` OR Cr `gain_loss_gl_account` (gain or loss)
    Cr `asset_gl_account` (asset cost removed)

### 2.7 Inventory & Cost (accounting-owned financial stub — NO item master)

- [ ] **`InventoryCostItem`** — extends `TenantOwned`; thin financial-valuation stub.
  No auto-number (looked up by sku). Fields:
  - `sku` CharField max_length=100
  - `description` CharField max_length=255
  - `valuation_method` CharField choices
    `[("fifo","FIFO"),("lifo","LIFO"),("weighted_avg","Weighted Average"),
    ("standard","Standard Cost")]` default `"weighted_avg"`
  - `standard_cost` DecimalField max_digits=14 decimal_places=4 default=0
  - `current_avg_cost` DecimalField max_digits=14 decimal_places=4 default=0
  - `on_hand_qty` DecimalField max_digits=14 decimal_places=4 default=0
  - `inventory_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"inventory_cost_items"`
  - `cogs_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"inventory_cogs_items"`
  - `variance_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"inventory_variance_items"`
  - `unique_together = ("tenant", "sku")`
  - Indexes: `(tenant, sku)`, `(tenant, valuation_method)`
  - When Module 5 Inventory ships: add FK → `inventory.Item` here (migration); stub is buildable now.
  - Drivers: Inventory Valuation (SAP/NetSuite/D365/Sage), COGS posting, Standard Cost Variance

- [ ] **`CostTransaction`** [PREFIX `CT`] — extends `TenantNumbered`; one row per inbound/outbound movement.
  Fields:
  - `cost_item` FK → `"accounting.InventoryCostItem"` CASCADE related_name `"cost_transactions"`
  - `transaction_date` DateField
  - `direction` CharField choices `[("in","Inbound"),("out","Outbound")]`
  - `reference_type` CharField choices
    `[("purchase","Purchase"),("sale","Sale"),("adjustment","Adjustment"),
    ("landed_cost","Landed Cost")]` default `"purchase"`
  - `quantity` DecimalField max_digits=14 decimal_places=4
  - `unit_cost` DecimalField max_digits=14 decimal_places=4
  - `total_cost` DecimalField max_digits=18 decimal_places=2 editable=False
    (computed = quantity × unit_cost; system-set in view — EXCLUDE from ModelForm)
  - `journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"cost_transactions"` editable=False
  - `description` CharField max_length=255 blank
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, transaction_date)`, `(tenant, direction)`
  - On outbound `post_cost_transaction` action:
    Dr `cogs_gl_account` (COGS)
    Cr `inventory_gl_account` (Inventory)
  - Weighted-avg update logic: after each inbound, recompute
    `current_avg_cost = (old_qty * old_cost + qty * unit_cost) / new_qty` on `InventoryCostItem`.
  - Drivers: COGS Posting (NetSuite/SAP/D365/Sage), Weighted-Average Cost (NetSuite/SAP/Sage/D365)

### 2.8 Payroll Integration (GL/accrual layer only — no employee master)

- [ ] **`PayrollJournalBatch`** [PREFIX `PJB`] — extends `TenantNumbered`; one batch per pay run.
  Fields:
  - `pay_period_start` DateField
  - `pay_period_end` DateField
  - `pay_date` DateField
  - `source` CharField choices
    `[("manual","Manual"),("csv_import","CSV Import"),("hris_import","HRIS Import")]`
    default `"manual"`
  - `is_accrual` BooleanField default=False
    (if True: JE posts to the CURRENT period; a reversal JE is created on pay_date's period
    first day via the existing `_reverse_journal_entry` helper)
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` SET_NULL null blank
    related_name `"payroll_journal_batches"`
  - `status` CharField choices `[("draft","Draft"),("posted","Posted")]` default `"draft"`
  - `journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"payroll_journal_batches"` editable=False (system-set on post)
  - `notes` TextField blank
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, status)`, `(tenant, pay_date)`
  - Drivers: Payroll Journal Batch (Workday/ADP/QB Payroll/SAP/D365),
    Accrual/Reversal Pattern (NetSuite/Sage/D365/Workday)

- [ ] **`PayrollJournalLine`** — child of `PayrollJournalBatch`, no auto-number, no direct tenant FK.
  Fields:
  - `batch` FK → `"accounting.PayrollJournalBatch"` CASCADE related_name `"lines"`
  - `line_type` CharField choices
    `[("gross_wages","Gross Wages"),("employer_tax","Employer Payroll Tax"),
    ("employee_tax","Employee Tax Withholding"),("benefits","Benefits"),
    ("garnishment","Garnishment"),("net_pay","Net Pay Clearing")]`
  - `amount` DecimalField max_digits=18 decimal_places=2
  - `gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"payroll_journal_lines"`
  - `org_unit` FK → `"core.OrgUnit"` SET_NULL null blank
    related_name `"payroll_journal_lines"` (department cost split)
  - `description` CharField max_length=255 blank
  - No standalone CRUD list page; accessed via PayrollJournalBatch detail + admin.
  - On `payroll_batch_post` action the view aggregates all lines to build one balanced JE:
    Dr lines where line_type in (gross_wages, employer_tax, benefits) → Expense GLAccounts
    Cr lines where line_type in (employee_tax, net_pay, garnishment, benefits) → Liability GLAccounts
  - Drivers: Payroll GL Posting (all platforms), Benefits Accounting, Garnishment Payable Clearing

### 2.9 Project / Job Costing

- [ ] **`Project`** [PREFIX `PRJ`] — extends `TenantNumbered`; the project container.
  Fields:
  - `name` CharField max_length=255
  - `client` FK → `"core.Party"` SET_NULL null blank related_name `"accounting_projects"`
  - `org_unit` FK → `"core.OrgUnit"` SET_NULL null blank related_name `"accounting_projects"`
  - `project_manager` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"managed_accounting_projects"`
  - `billing_method` CharField choices
    `[("t_and_m","Time & Materials"),("fixed","Fixed Price"),
    ("milestone","Milestone"),("cost_plus","Cost Plus")]` default `"t_and_m"`
  - `status` CharField choices
    `[("active","Active"),("on_hold","On Hold"),("completed","Completed"),("cancelled","Cancelled")]`
    default `"active"`
  - `start_date` DateField null blank
  - `end_date` DateField null blank
  - `budget_amount` DecimalField max_digits=18 decimal_places=2 default=0
  - `retention_pct` DecimalField max_digits=5 decimal_places=2 default=0
    (for progress billing; driver: Project Invoice / Progress Billing — Sage/NetSuite/D365)
  - `notes` TextField blank
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, status)`, `(tenant, client)`
  - Drivers: Project Master (Sage/NetSuite/D365), Budget vs. Actual Profitability

- [ ] **`ProjectBudgetLine`** — standalone CRUD child, no auto-number, no direct tenant FK.
  Fields:
  - `project` FK → `"accounting.Project"` CASCADE related_name `"budget_lines"`
  - `gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"project_budget_lines"`
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` SET_NULL null blank
    related_name `"project_budget_lines"`
  - `budgeted_amount` DecimalField max_digits=18 decimal_places=2
  - `description` CharField max_length=255 blank
  - `unique_together = ("project", "gl_account", "fiscal_period")`
  - Has its own list/create/edit/delete under the `accounting:` namespace — NOT an inline formset.
  - Drivers: Project Budget (Sage/NetSuite/D365/Oracle Fusion)

> FK ADDITIONS on existing tables (migration 0002 adds columns to 0001 tables):
> - [ ] Add `project` nullable FK → `"accounting.Project"` SET_NULL on `accounting.JournalLine`
>   (cost transaction tagging; driver: Cost Transaction Tagging — Sage Intacct dimensions)
> - [ ] Add `project` nullable FK → `"accounting.Project"` SET_NULL on `accounting.Invoice`
>   (progress billing link; driver: Project Invoice / Progress Billing — Sage/NetSuite/D365)

### 2.10 Multi-Entity & Consolidation

- [ ] **`ConsolidationGroup`** — extends `TenantOwned`; no auto-number (looked up by name).
  Fields:
  - `name` CharField max_length=255
  - `parent_entity` FK → `"core.OrgUnit"` SET_NULL null blank
    related_name `"consolidation_groups_as_parent"`
    (OrgUnit with unit_type=entity is the legal-entity dimension — do NOT create a new table)
  - `members` ManyToManyField → `"core.OrgUnit"` related_name `"consolidation_groups"`
    blank (member subsidiaries)
  - `reporting_currency` FK → `"accounting.Currency"` SET_NULL null blank
    related_name `"consolidation_groups"`
  - `is_active` BooleanField default=True
  - `unique_together = ("tenant", "name")`
  - Drivers: Entity Management (NetSuite OneWorld/Sage Intacct/D365)

- [ ] **`IntercompanyTransaction`** [PREFIX `ICT`] — extends `TenantNumbered`.
  Fields:
  - `consolidation_group` FK → `"accounting.ConsolidationGroup"` CASCADE
    related_name `"intercompany_transactions"`
  - `from_entity` FK → `"core.OrgUnit"` SET_NULL null blank
    related_name `"ict_from_transactions"`
  - `to_entity` FK → `"core.OrgUnit"` SET_NULL null blank
    related_name `"ict_to_transactions"`
  - `transaction_date` DateField
  - `amount` DecimalField max_digits=18 decimal_places=2
  - `currency` FK → `"accounting.Currency"` SET_NULL null blank
    related_name `"intercompany_transactions"`
  - `from_journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"ict_from_entries"` editable=False
  - `to_journal_entry` FK → `"accounting.JournalEntry"` SET_NULL null blank
    related_name `"ict_to_entries"` editable=False
  - `status` CharField choices
    `[("draft","Draft"),("posted","Posted"),("eliminated","Eliminated")]` default `"draft"`
  - `notes` TextField blank
  - `document` FK → `"core.Document"` SET_NULL null blank related_name `"intercompany_docs"`
    (transfer pricing documentation attachment; driver: Transfer Pricing Documentation)
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, status)`, `(tenant, transaction_date)`
  - On `ict_post` action (two paired JEs inside atomic()):
    Entity A JE: Dr `due_from_gl_account` / Cr Revenue (or Pass-through GLAccount)
    Entity B JE: Dr Expense / Cr `due_to_gl_account`
    (GL accounts resolved via `_first_account` on each entity's OrgUnit; or user-supplied on form)
  - On `ict_eliminate` action: posts elimination JE tagged `entry_type="elimination"` with
    `consolidation_group` FK on JournalEntry (migration 0002 adds this field)
  - Drivers: Intercompany Transaction Pair (NetSuite/Sage/D365/SAP), Elimination Entry,
    Transfer Pricing Documentation

> FIELD ADDITION on `JournalEntry` (migration 0002):
> - [ ] Add `consolidation_group` nullable FK → `"accounting.ConsolidationGroup"` SET_NULL
>   on `accounting.JournalEntry` (tags elimination entries to a group)
> - [ ] Add `entry_type` choice `"elimination"` to `JournalEntry.ENTRY_TYPE_CHOICES`

### 2.11 Tax

- [ ] **`TaxCode`** — extends `TenantOwned`; rate master (lookup table, no auto-number).
  Fields:
  - `code` CharField max_length=20
  - `name` CharField max_length=255
  - `tax_type` CharField choices
    `[("sales","Sales Tax"),("use","Use Tax"),("vat","VAT"),("gst","GST"),
    ("withholding","Withholding"),("income","Income Tax")]` default `"sales"`
  - `rate_pct` DecimalField max_digits=7 decimal_places=4
  - `jurisdiction_level` CharField choices
    `[("federal","Federal"),("state","State"),("county","County"),("city","City")]`
    default `"state"`
  - `country` CharField max_length=2 default `"US"` (ISO 3166-1 alpha-2)
  - `region` CharField max_length=100 blank (state/province code)
  - `effective_from` DateField null blank
  - `effective_to` DateField null blank
  - `payable_gl_account` FK → `"accounting.GLAccount"` SET_NULL null blank
    related_name `"tax_code_payables"` (tax payable control account)
  - `is_active` BooleanField default=True
  - `unique_together = ("tenant", "code")`
  - Indexes: `(tenant, tax_type)`, `(tenant, is_active)`
  - Drivers: Tax Rate Master (Avalara/Vertex/NetSuite/Sage/SAP/D365)

- [ ] **`TaxNexus`** — extends `TenantOwned`; economic/physical nexus tracking.
  Fields:
  - `jurisdiction_name` CharField max_length=255
  - `country` CharField max_length=2 default `"US"`
  - `region` CharField max_length=100 blank
  - `nexus_type` CharField choices `[("physical","Physical"),("economic","Economic")]`
    default `"economic"`
  - `threshold_amount` DecimalField max_digits=14 decimal_places=2 default=100000
  - `current_ytd_sales` DecimalField max_digits=18 decimal_places=2 default=0
  - `registration_number` CharField max_length=100 blank
  - `is_registered` BooleanField default=False
  - `registration_date` DateField null blank
  - Indexes: `(tenant, is_registered)`, `(tenant, nexus_type)`
  - Drivers: Nexus Tracking (Avalara/Vertex/NetSuite/D365)

- [ ] **`TaxFilingObligation`** — extends `TenantOwned`; one filing record per jurisdiction per period.
  Fields:
  - `tax_nexus` FK → `"accounting.TaxNexus"` CASCADE related_name `"filing_obligations"`
  - `tax_code` FK → `"accounting.TaxCode"` SET_NULL null blank
    related_name `"filing_obligations"`
  - `filing_period_start` DateField
  - `filing_period_end` DateField
  - `due_date` DateField
  - `status` CharField choices
    `[("upcoming","Upcoming"),("filed","Filed"),("overdue","Overdue")]` default `"upcoming"`
  - `taxable_amount` DecimalField max_digits=18 decimal_places=2 default=0
  - `tax_due` DecimalField max_digits=18 decimal_places=2 default=0
  - `filed_date` DateField null blank
  - `filed_by` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"tax_filings_filed"` (system-set — EXCLUDE from ModelForm per L22)
  - `payment` FK → `"accounting.Payment"` SET_NULL null blank
    related_name `"tax_filing_payments"` (links to the remittance Payment)
  - Indexes: `(tenant, status)`, `(tenant, due_date)`
  - Drivers: Tax Calendar (Avalara/NetSuite/D365/Sage), Sales Tax Return (Avalara/NetSuite/D365)

> FIELD ADDITION on existing table (migration 0002):
> - [ ] Add `cash_flow_category` nullable CharField choices
>   `[("operating","Operating"),("investing","Investing"),("financing","Financing")]`
>   on `accounting.GLAccount` (enables Cash Flow Statement classification;
>   driver: Cash Flow Statement — NetSuite/Sage/D365/QB Enterprise)

### 2.12 Reporting & Compliance (1 model + 4 report views — no formsets)

- [ ] **`ScheduledReport`** — extends `TenantOwned`; configuration row for automated report delivery.
  Fields:
  - `report_type` CharField choices
    `[("balance_sheet","Balance Sheet"),("profit_loss","Profit & Loss"),
    ("cash_flow","Cash Flow"),("trial_balance","Trial Balance"),
    ("ar_aging","AR Aging"),("ap_aging","AP Aging"),
    ("budget_variance","Budget vs. Actual")]` default `"balance_sheet"`
  - `frequency` CharField choices
    `[("daily","Daily"),("weekly","Weekly"),("monthly","Monthly")]` default `"monthly"`
  - `recipients` JSONField default=list (list of email address strings)
  - `format` CharField choices `[("pdf","PDF"),("xlsx","XLSX")]` default `"pdf"`
  - `last_run_at` DateTimeField null blank editable=False (system-set — EXCLUDE from ModelForm per L22)
  - `next_run_at` DateField null blank (user-set target date)
  - `is_active` BooleanField default=True
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` SET_NULL null blank
    related_name `"scheduled_reports"` (optional scoping)
  - Indexes: `(tenant, is_active)`, `(tenant, frequency)`
  - Drivers: Scheduled Reports (QB Enterprise/D365/NetSuite/Sage)
  - NOTE: actual Celery/email delivery = deferred. This pass builds the config model + CRUD
    + the 4 live report views below.

> The 4 report views (no new models — pure query/aggregation over existing tables):
> - `balance_sheet` — assets/liabilities/equity as of a date; GLAccount balance() aggregated
>   by account_type; posted JournalLine rows only.
> - `profit_and_loss` — revenue minus expenses for a date range; income and expense accounts.
> - `cash_flow_statement` — operating/investing/financing sections using `GLAccount.cash_flow_category`
>   (added in the 0002 migration above); indirect method stub.
> - `budget_variance_report` — BudgetLine amounts vs. posted JournalLine actuals grouped by
>   (gl_account, fiscal_period, org_unit); renders once BudgetVersion / BudgetLine are built.

### 2.13 Budgeting & Planning

- [ ] **`BudgetVersion`** [PREFIX `BV`] — extends `TenantNumbered`; named budget scenario container.
  Fields:
  - `name` CharField max_length=255
  - `fiscal_year` PositiveSmallIntegerField (e.g. 2026)
  - `version_type` CharField choices
    `[("original","Original"),("revised","Revised"),("forecast","Rolling Forecast"),
    ("what_if","What-If Scenario")]` default `"original"`
  - `is_active` BooleanField default=False (only one per tenant should be True at a time)
  - `is_locked` BooleanField default=False (lock prevents BudgetLine edits)
  - `copied_from` FK → `"self"` SET_NULL null blank related_name `"derived_versions"`
    (What-If: copied from a base version; driver: What-If Scenario Modeling — Vena/Workday Adaptive/D365)
  - `approved_by` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"approved_budget_versions"` editable=False (system-set — EXCLUDE from ModelForm)
  - `unique_together = ("tenant", "number")`
  - Indexes: `(tenant, fiscal_year)`, `(tenant, is_active)`
  - Custom action `budget_copy` (POST): duplicates a BudgetVersion + all its BudgetLines
    into a new BudgetVersion with version_type=`"what_if"`.
  - Drivers: Budget Version / Scenario (Vena/Planful/Workday Adaptive/D365/NetSuite),
    Rolling Forecast (Planful/Workday Adaptive/D365)

- [ ] **`BudgetLine`** — standalone CRUD (no formset), no auto-number, no direct tenant FK.
  Fields:
  - `budget_version` FK → `"accounting.BudgetVersion"` CASCADE related_name `"lines"`
  - `gl_account` FK → `"accounting.GLAccount"` PROTECT related_name `"budget_lines"`
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` SET_NULL null blank
    related_name `"budget_lines"`
  - `org_unit` FK → `"core.OrgUnit"` SET_NULL null blank related_name `"budget_lines"`
  - `budgeted_amount` DecimalField max_digits=18 decimal_places=2
  - `is_locked_actuals` BooleanField default=False
    (for rolling forecast: True = this past period's amount came from actuals, not a projection)
  - `unique_together = ("budget_version", "gl_account", "fiscal_period", "org_unit")`
  - Has its own list/create/edit/delete — NOT an inline formset.
  - Drivers: Budget Line (Vena/Planful/Workday Adaptive/D365/NetSuite),
    Rolling Forecast past-period actuals lock (Planful/Workday Adaptive/D365)

### 2.14 Audit & Controls

- [ ] **`ControlRecord`** — extends `TenantOwned`; SOX control documentation.
  Fields:
  - `name` CharField max_length=255
  - `description` TextField blank
  - `control_type` CharField choices
    `[("preventive","Preventive"),("detective","Detective"),("corrective","Corrective")]`
    default `"preventive"`
  - `frequency` CharField choices
    `[("daily","Daily"),("weekly","Weekly"),("monthly","Monthly"),
    ("quarterly","Quarterly"),("annual","Annual")]` default `"quarterly"`
  - `risk_area` CharField max_length=255 blank
  - `owner` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"owned_controls"`
  - `is_active` BooleanField default=True
  - Indexes: `(tenant, control_type)`, `(tenant, is_active)`
  - Drivers: SOX Controls (FloQast/AuditBoard/D365 GRC/SAP GRC)

- [ ] **`ControlTest`** — standalone CRUD child, no auto-number, no direct tenant FK.
  Fields:
  - `control_record` FK → `"accounting.ControlRecord"` CASCADE related_name `"tests"`
  - `test_date` DateField
  - `tester` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank related_name `"control_tests"`
  - `result` CharField choices
    `[("pass","Pass"),("fail","Fail"),("exception","Exception / Partial")]` default `"pass"`
  - `notes` TextField blank
  - `evidence_document` FK → `"core.Document"` SET_NULL null blank
    related_name `"control_test_evidence"` (attached audit evidence; reuses confirmed-existing `core.Document`)
  - `created_at` DateTimeField auto_now_add=True
  - Has its own list/create/edit/delete under `accounting:` namespace.
  - Drivers: Control Test / Evidence (FloQast/AuditBoard)

- [ ] **`PeriodCloseTask`** — standalone CRUD child, no auto-number, no direct tenant FK.
  Fields:
  - `fiscal_period` FK → `"accounting.FiscalPeriod"` CASCADE related_name `"close_tasks"`
  - `task_name` CharField max_length=255
  - `task_type` CharField choices
    `[("bank_recon","Bank Reconciliation"),("depreciation","Post Depreciation"),
    ("payroll_accrual","Payroll Accrual"),("exception_review","Review Exceptions"),
    ("consolidation","Consolidation Run"),("custom","Custom")]` default `"custom"`
  - `assignee` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"period_close_tasks"`
  - `due_date` DateField null blank
  - `status` CharField choices
    `[("pending","Pending"),("in_progress","In Progress"),("done","Done")]` default `"pending"`
  - `completed_by` FK → `settings.AUTH_USER_MODEL` SET_NULL null blank
    related_name `"completed_close_tasks"` editable=False (system-set — EXCLUDE from ModelForm)
  - `completed_at` DateTimeField null blank editable=False (system-set — EXCLUDE from ModelForm per L22)
  - Has its own list/create/edit/delete. Custom `task_complete` POST action sets status=`"done"`,
    `completed_by=request.user`, `completed_at=now()`.
  - Drivers: Period Close Checklist (FloQast/AuditBoard/D365/Sage)

### 2.15 Integration & API

- [ ] **`IntegrationConfig`** — extends `TenantOwned`; one row per external integration per tenant.
  Fields:
  - `integration_type` CharField choices
    `[("plaid","Plaid — Banking"),("stripe","Stripe — Payments"),
    ("paypal","PayPal — Payments"),("avalara","Avalara — Tax"),
    ("vertex","Vertex — Tax"),("shopify","Shopify — E-commerce"),
    ("woocommerce","WooCommerce — E-commerce"),("salesforce","Salesforce — CRM"),
    ("hubspot","HubSpot — CRM"),("workday","Workday — HRIS"),
    ("adp","ADP — Payroll"),("bamboohr","BambooHR — HRIS"),("custom","Custom")]`
  - `endpoint_url` URLField blank
  - `api_key_encrypted` CharField max_length=255 blank
    (stores ONLY `prefix:sha256_hex` — NEVER the raw secret; EXCLUDE from the ModelForm entirely;
    only settable via the write-only `integration_rotate_key` POST action)
  - `is_active` BooleanField default=False
  - `last_synced_at` DateTimeField null blank editable=False (system-set — EXCLUDE from ModelForm per L22)
  - `sync_status` CharField choices
    `[("idle","Idle"),("running","Running"),("error","Error"),("success","Last Sync OK")]`
    default `"idle"` editable=False (system-set — EXCLUDE from ModelForm)
  - `error_message` TextField blank editable=False (system-set — EXCLUDE from ModelForm)
  - `notes` TextField blank (human notes; safe to display)
  - Indexes: `(tenant, integration_type)`, `(tenant, is_active)`
  - `unique_together = ("tenant", "integration_type")` — one config per type per tenant
  - Drivers: External Integration Config (NetSuite/D365/Xero), Banking APIs (2.15),
    Payment Gateways (2.15), Tax Software (2.15), HRIS (2.15)
  - Security: `api_key_encrypted` EXCLUDED from `IntegrationConfigForm.Meta.fields` (L20);
    `integration_rotate_key` POST action writes the new `prefix:sha256_hex` value;
    the raw secret is returned once via `request.session["_key_reveal"]` pop-once pattern (L25).

---

## Section 2 — Backend (`apps/accounting/` extensions)

### 2a — New files

- [ ] `apps/accounting/models_advanced.py` — all 14 new model classes (plus `DepreciationSchedule`,
  `PayrollJournalLine`, `BudgetLine`, `ControlTest`, `PeriodCloseTask` child classes)
  in dependency order:
  `FixedAsset` → `DepreciationSchedule` → `AssetDisposal` → `InventoryCostItem` → `CostTransaction` →
  `PayrollJournalBatch` → `PayrollJournalLine` → `Project` → `ProjectBudgetLine` →
  `ConsolidationGroup` → `IntercompanyTransaction` → `TaxCode` → `TaxNexus` → `TaxFilingObligation` →
  `ScheduledReport` → `BudgetVersion` → `BudgetLine` → `ControlRecord` → `ControlTest` →
  `PeriodCloseTask` → `IntegrationConfig`.
  Import `TenantOwned`, `TenantNumbered`, `ZERO` from `.models`.

- [ ] `apps/accounting/forms_advanced.py` — one `TenantModelForm` per primary model.
  MANDATORY EXCLUSIONS from every form (L22 + L20 + CLAUDE.md):
  - Always: `tenant`, `number` (auto), all `*_at` system DateTimeFields,
    `*_by` system FKs set in view, `journal_entry` FK, `gain_loss` (computed),
    `total_cost` (computed), `accumulated_depreciation` (system-updated),
    `capitalization_je`, `from_journal_entry`, `to_journal_entry`.
  - `IntegrationConfigForm`: EXCLUDE `api_key_encrypted`, `sync_status`,
    `error_message`, `last_synced_at` (L20 + L22).
  - `ScheduledReportForm`: EXCLUDE `last_run_at`.
  - `PeriodCloseTaskForm`: EXCLUDE `completed_by`, `completed_at`.
  - `TaxFilingObligationForm`: EXCLUDE `filed_by`.
  - `BudgetVersionForm`: EXCLUDE `approved_by`.
  - All FK dropdowns scoped to `tenant` in `__init__`; `Currency` scoped to `is_active=True`.

- [ ] `apps/accounting/views_advanced.py` — function-based views, all `@login_required`.
  Privileged action views are `@tenant_admin_required`:
  `asset_capitalize`, `depreciation_run`, `asset_dispose`,
  `post_cost_transaction`, `payroll_batch_post`,
  `ict_post`, `ict_eliminate`, `budget_copy`, `task_complete`, `integration_rotate_key`.
  Full list/create/detail/edit/delete for all 14 primary models
  plus child-model standalone CRUD for: `DepreciationSchedule` (list under asset + admin only),
  `PayrollJournalLine` (list under batch detail + admin only),
  `ProjectBudgetLine`, `BudgetLine`, `ControlTest`, `PeriodCloseTask`.
  Report views (GET only, no DB writes):
  `balance_sheet`, `profit_and_loss`, `cash_flow_statement`, `budget_variance_report`,
  `consolidation_report` (aggregates across ConsolidationGroup members).
  Import: `_first_account`, `_open_period`, `_reverse_journal_entry` from `.views`.
  Every queryset: `filter(tenant=request.tenant)`. No `Model.objects.all()`.
  All FK filter dropdowns: `.isdigit()` guard (L11).
  All list views apply filters BEFORE pagination.
  Status/type dropdowns pass `*_choices` in context (CLAUDE.md Filter Rule).

### 2b — Existing files to modify

- [ ] `apps/accounting/models.py` — add at bottom:
  `from .models_advanced import *  # noqa`
  Also add the three new field migrations listed in Section 1 as Python fields on the existing
  model classes (Django discovers them):
  - `JournalLine.project` nullable FK → `"accounting.Project"` SET_NULL
  - `Invoice.project` nullable FK → `"accounting.Project"` SET_NULL
  - `JournalEntry.consolidation_group` nullable FK → `"accounting.ConsolidationGroup"` SET_NULL
  - `JournalEntry.ENTRY_TYPE_CHOICES` extended with `("elimination","Elimination")`
  - `GLAccount.cash_flow_category` nullable CharField choices
    `[("operating","Operating"),("investing","Investing"),("financing","Financing")]`

- [ ] `apps/accounting/urls.py` — APPEND to existing `urlpatterns` (keep `app_name = "accounting"`):
  **FixedAsset (2.6):** `fixed-assets/` → `fixedasset_list`; `.../add/` → `fixedasset_create`;
  `.../<int:pk>/` → `fixedasset_detail`; `.../edit/` → `fixedasset_edit`;
  `.../delete/` → `fixedasset_delete`; `.../capitalize/` → `asset_capitalize` (POST);
  `.../depreciate/` → `depreciation_run` (POST); `.../dispose/` → `asset_dispose` (POST);
  `depreciation-schedules/<int:asset_pk>/` → `depreciation_schedule_list` (list under asset).
  **AssetDisposal (2.6):** `asset-disposals/` → `assetdisposal_list`; `.../add/` → `assetdisposal_create`;
  `.../<int:pk>/` → `assetdisposal_detail`; `.../edit/` → `assetdisposal_edit`;
  `.../delete/` → `assetdisposal_delete`.
  **InventoryCostItem (2.7):** `inventory-cost/` → `inventorycostitem_list`;
  `.../add/` → `inventorycostitem_create`; `.../<int:pk>/` → `inventorycostitem_detail`;
  `.../edit/` → `inventorycostitem_edit`; `.../delete/` → `inventorycostitem_delete`.
  **CostTransaction (2.7):** `cost-transactions/` → `costtransaction_list`;
  `.../add/` → `costtransaction_create`; `.../<int:pk>/` → `costtransaction_detail`;
  `.../edit/` → `costtransaction_edit`; `.../delete/` → `costtransaction_delete`;
  `.../post/` → `post_cost_transaction` (POST).
  **PayrollJournalBatch (2.8):** `payroll-batches/` → `payrolljournalbatch_list`;
  `.../add/` → `payrolljournalbatch_create`; `.../<int:pk>/` → `payrolljournalbatch_detail`;
  `.../edit/` → `payrolljournalbatch_edit`; `.../delete/` → `payrolljournalbatch_delete`;
  `.../post/` → `payroll_batch_post` (POST);
  `payroll-batches/<int:batch_pk>/lines/` → `payrolljournalline_list`;
  `payroll-batches/<int:batch_pk>/lines/add/` → `payrolljournalline_create`;
  `payroll-lines/<int:pk>/edit/` → `payrolljournalline_edit`;
  `payroll-lines/<int:pk>/delete/` → `payrolljournalline_delete`.
  **Project (2.9):** `projects/` → `project_list`; `.../add/` → `project_create`;
  `.../<int:pk>/` → `project_detail`; `.../edit/` → `project_edit`;
  `.../delete/` → `project_delete`.
  **ProjectBudgetLine (2.9):** `project-budget-lines/` → `projectbudgetline_list`;
  `.../add/` → `projectbudgetline_create`; `.../<int:pk>/` → `projectbudgetline_detail`;
  `.../edit/` → `projectbudgetline_edit`; `.../delete/` → `projectbudgetline_delete`.
  **ConsolidationGroup (2.10):** `consolidation-groups/` → `consolidationgroup_list`;
  `.../add/` → `consolidationgroup_create`; `.../<int:pk>/` → `consolidationgroup_detail`;
  `.../edit/` → `consolidationgroup_edit`; `.../delete/` → `consolidationgroup_delete`.
  **IntercompanyTransaction (2.10):** `intercompany/` → `intercompanytransaction_list`;
  `.../add/` → `intercompanytransaction_create`; `.../<int:pk>/` → `intercompanytransaction_detail`;
  `.../edit/` → `intercompanytransaction_edit`; `.../delete/` → `intercompanytransaction_delete`;
  `.../post/` → `ict_post` (POST); `.../eliminate/` → `ict_eliminate` (POST).
  **TaxCode (2.11):** `tax-codes/` → `taxcode_list`; `.../add/` → `taxcode_create`;
  `.../<int:pk>/` → `taxcode_detail`; `.../edit/` → `taxcode_edit`; `.../delete/` → `taxcode_delete`.
  **TaxNexus (2.11):** `tax-nexus/` → `taxnexus_list`; `.../add/` → `taxnexus_create`;
  `.../<int:pk>/` → `taxnexus_detail`; `.../edit/` → `taxnexus_edit`;
  `.../delete/` → `taxnexus_delete`.
  **TaxFilingObligation (2.11):** `tax-filings/` → `taxfilingobligation_list`;
  `.../add/` → `taxfilingobligation_create`; `.../<int:pk>/` → `taxfilingobligation_detail`;
  `.../edit/` → `taxfilingobligation_edit`; `.../delete/` → `taxfilingobligation_delete`.
  **ScheduledReport (2.12):** `scheduled-reports/` → `scheduledreport_list`;
  `.../add/` → `scheduledreport_create`; `.../<int:pk>/` → `scheduledreport_detail`;
  `.../edit/` → `scheduledreport_edit`; `.../delete/` → `scheduledreport_delete`.
  **Report views (2.12):** `reports/balance-sheet/` → `balance_sheet`;
  `reports/profit-loss/` → `profit_and_loss`; `reports/cash-flow/` → `cash_flow_statement`;
  `reports/budget-variance/` → `budget_variance_report`;
  `reports/consolidation/` → `consolidation_report`.
  **BudgetVersion (2.13):** `budget-versions/` → `budgetversion_list`;
  `.../add/` → `budgetversion_create`; `.../<int:pk>/` → `budgetversion_detail`;
  `.../edit/` → `budgetversion_edit`; `.../delete/` → `budgetversion_delete`;
  `.../copy/` → `budget_copy` (POST).
  **BudgetLine (2.13):** `budget-lines/` → `budgetline_list`; `.../add/` → `budgetline_create`;
  `.../<int:pk>/` → `budgetline_detail`; `.../edit/` → `budgetline_edit`;
  `.../delete/` → `budgetline_delete`.
  **ControlRecord (2.14):** `controls/` → `controlrecord_list`; `.../add/` → `controlrecord_create`;
  `.../<int:pk>/` → `controlrecord_detail`; `.../edit/` → `controlrecord_edit`;
  `.../delete/` → `controlrecord_delete`.
  **ControlTest (2.14):** `control-tests/` → `controltest_list`; `.../add/` → `controltest_create`;
  `.../<int:pk>/` → `controltest_detail`; `.../edit/` → `controltest_edit`;
  `.../delete/` → `controltest_delete`.
  **PeriodCloseTask (2.14):** `period-close-tasks/` → `periodclosetask_list`;
  `.../add/` → `periodclosetask_create`; `.../<int:pk>/` → `periodclosetask_detail`;
  `.../edit/` → `periodclosetask_edit`; `.../delete/` → `periodclosetask_delete`;
  `.../complete/` → `task_complete` (POST).
  **IntegrationConfig (2.15):** `integrations/` → `integrationconfig_list`;
  `.../add/` → `integrationconfig_create`; `.../<int:pk>/` → `integrationconfig_detail`;
  `.../edit/` → `integrationconfig_edit`; `.../delete/` → `integrationconfig_delete`;
  `.../rotate-key/` → `integration_rotate_key` (POST, @tenant_admin_required).
  **Audit trail view (2.14):** `audit-trail/` → `audit_trail_list`
  (read-only view over `core.AuditLog`, filtered by `tenant`, searchable by model/user/date/action).

- [ ] `apps/accounting/admin.py` — APPEND `@admin.register` classes for all 14 new primary models
  + child models (`DepreciationSchedule`, `PayrollJournalLine`, `BudgetLine`, `ControlTest`,
  `PeriodCloseTask`) as TabularInline entries under their parents.
  `IntegrationConfigAdmin`: `readonly_fields` includes `api_key_encrypted` (display masked),
  `sync_status`, `error_message`, `last_synced_at`.

### 2c — Migration

- [ ] Run `python manage.py makemigrations accounting` → generates
  `apps/accounting/migrations/0002_advanced.py` (one file covering all new tables +
  3 FK additions on existing tables + 2 field additions on existing models).
- [ ] Run `python manage.py sqlmigrate accounting 0002` — confirm SQL: no missing FKs,
  unique_together constraints present, `db_index` on all tenant and FK columns.

### 2d — Seeder extension

- [ ] Extend `apps/accounting/management/commands/seed_accounting.py` with a
  `_seed_advanced(tenant, admin_user)` function called from `handle()` after the existing seed:
  Idempotency guard per model: `if Model.objects.filter(tenant=tenant).exists(): skip`.
  Seed data per tenant (reuse existing GLAccounts seeded in 0001 via code_prefix lookups):
  - **2.6 Fixed Assets:** 2 `FixedAsset` rows (one `active`, one `cip`); 2 `DepreciationSchedule`
    rows (one `posted`, one `scheduled`); 1 `AssetDisposal` (status=`disposed` on the disposed asset).
  - **2.7 Inventory Cost:** 2 `InventoryCostItem` rows; 3 `CostTransaction` rows
    (2 inbound, 1 outbound with posted JE); weighted-avg recomputed.
  - **2.8 Payroll:** 1 `PayrollJournalBatch` (status=`posted`) with 4 `PayrollJournalLine` rows
    (gross_wages, employer_tax, employee_tax, net_pay); linked JE balanced.
  - **2.9 Projects:** 2 `Project` rows (one `active`, one `completed`); 2 `ProjectBudgetLine` rows.
  - **2.10 Consolidation:** 1 `ConsolidationGroup` using 2 existing `core.OrgUnit` rows as members;
    1 `IntercompanyTransaction` (status=`posted`); both JEs posted and balanced.
  - **2.11 Tax:** 2 `TaxCode` rows (sales, use); 1 `TaxNexus`; 1 `TaxFilingObligation` (upcoming).
  - **2.12 Reporting:** 1 `ScheduledReport` (monthly balance_sheet, is_active=True).
  - **2.13 Budgeting:** 1 `BudgetVersion` (original, is_active=True); 3 `BudgetLine` rows
    covering revenue and expense accounts.
  - **2.14 Audit & Controls:** 1 `ControlRecord` (monthly, preventive); 1 `ControlTest` (pass);
    2 `PeriodCloseTask` rows (one done, one pending).
  - **2.15 Integrations:** 1 `IntegrationConfig` (integration_type=`"plaid"`, is_active=False,
    api_key_encrypted=`"plaid_test:abc123...sha256"` placeholder, notes set).
  - After seeding: print `"Advanced accounting (2.6-2.15) seeded. Login as admin_acme / password."`
    and `"Superuser 'admin' has no tenant — data won't appear when logged in as admin."`

---

## Section 3 — Wire-up

### `apps/core/navigation.py` — LIVE_LINKS for 2.6–2.15

Add the following entries using the **exact NavERP.md bullet text** as keys:

- [ ] **Sub-module 2.6 — Fixed Assets:**
  ```python
  "2.6": {
      "Asset Register": "accounting:fixedasset_list",
      "Acquisition": "accounting:fixedasset_create",
      "Depreciation Engine": "accounting:fixedasset_list",
      "Asset Transfers": "accounting:fixedasset_list",
      "Disposals & Retirements": "accounting:assetdisposal_list",
      "Impairment Testing": "accounting:fixedasset_list",
      "Physical Inventory": "accounting:fixedasset_list",
      "Tax Depreciation": "accounting:depreciation_schedule_list",  # resolves to asset-scoped; see note
  },
  ```
  Note: `depreciation_schedule_list` requires an `asset_pk` — map to `fixedasset_list` as fallback
  if LIVE_LINKS cannot accept a parameterized URL; the build step resolves this.

- [ ] **Sub-module 2.7 — Inventory & Cost Management:**
  ```python
  "2.7": {
      "Item Master": "accounting:inventorycostitem_list",
      "Inventory Valuation": "accounting:inventorycostitem_list",
      "Purchase Orders": "accounting:costtransaction_list",
      "Inventory Transactions": "accounting:costtransaction_list",
      "Cost of Goods Sold": "accounting:costtransaction_list",
      "Reorder Point Planning": "accounting:inventorycostitem_list",
      "Cycle Counting": "accounting:inventorycostitem_list",
      "Landed Cost": "accounting:costtransaction_list",
  },
  ```

- [ ] **Sub-module 2.8 — Payroll Integration:**
  ```python
  "2.8": {
      "Employee Master": "accounting:payrolljournalbatch_list",
      "Payroll Journal": "accounting:payrolljournalbatch_list",
      "Tax Management": "accounting:taxcode_list",
      "Benefits Accounting": "accounting:payrolljournalbatch_list",
      "Garnishments": "accounting:payrolljournalbatch_list",
      "Workers Comp": "accounting:payrolljournalbatch_list",
      "Payroll Reconciliation": "accounting:payrolljournalbatch_list",
  },
  ```

- [ ] **Sub-module 2.9 — Project/Job Costing:**
  ```python
  "2.9": {
      "Project Setup": "accounting:project_list",
      "Time & Expense": "accounting:project_list",
      "Revenue Recognition": "accounting:project_list",
      "Project Billing": "accounting:project_list",
      "Profitability Analysis": "accounting:budget_variance_report",
      "Resource Planning": "accounting:project_list",
  },
  ```

- [ ] **Sub-module 2.10 — Multi-Entity & Consolidation:**
  ```python
  "2.10": {
      "Entity Management": "accounting:consolidationgroup_list",
      "Inter-company Transactions": "accounting:intercompanytransaction_list",
      "Currency Translation": "accounting:consolidationgroup_list",
      "Consolidation Engine": "accounting:consolidation_report",
      "Transfer Pricing": "accounting:intercompanytransaction_list",
      "Regulatory Reporting": "accounting:consolidation_report",
  },
  ```

- [ ] **Sub-module 2.11 — Tax:**
  ```python
  "2.11": {
      "Sales Tax Engine": "accounting:taxcode_list",
      "Tax Returns": "accounting:taxfilingobligation_list",
      "Use Tax Tracking": "accounting:taxcode_list",
      "Income Tax Provision": "accounting:taxfilingobligation_list",
      "Tax Calendar": "accounting:taxfilingobligation_list",
      "Audit Support": "accounting:controltest_list",
      "Nexus Tracking": "accounting:taxnexus_list",
  },
  ```

- [ ] **Sub-module 2.12 — Reporting & Compliance:**
  ```python
  "2.12": {
      "Financial Statements": "accounting:balance_sheet",
      "Management Reports": "accounting:profit_and_loss",
      "Custom Report Builder": "accounting:trial_balance",
      "Scheduled Reports": "accounting:scheduledreport_list",
      "XBRL/EDGAR Filing": "accounting:scheduledreport_list",
      "Statutory Reporting": "accounting:balance_sheet",
      "Consolidation Reports": "accounting:consolidation_report",
      "Dashboards": "accounting:accounting_dashboard",
  },
  ```

- [ ] **Sub-module 2.13 — Budgeting & Planning:**
  ```python
  "2.13": {
      "Budget Creation": "accounting:budgetversion_list",
      "Version Control": "accounting:budgetversion_list",
      "Driver-based Planning": "accounting:budgetversion_list",
      "Rolling Forecasts": "accounting:budgetversion_list",
      "Variance Analysis": "accounting:budget_variance_report",
      "What-if Analysis": "accounting:budgetversion_list",
      "Workforce Planning": "accounting:budgetversion_list",
  },
  ```

- [ ] **Sub-module 2.14 — Audit & Controls:**
  ```python
  "2.14": {
      "SOX Controls": "accounting:controlrecord_list",
      "Segregation of Duties": "accounting:controlrecord_list",
      "Access Controls": "accounting:audit_trail_list",
      "Change Management": "accounting:periodclosetask_list",
      "Audit Trail": "accounting:audit_trail_list",
      "Exception Reporting": "accounting:audit_trail_list",
      "Document Management": "accounting:controltest_list",
  },
  ```

- [ ] **Sub-module 2.15 — Integration & API:**
  ```python
  "2.15": {
      "Banking APIs": "accounting:integrationconfig_list",
      "Payment Gateways": "accounting:integrationconfig_list",
      "E-commerce": "accounting:integrationconfig_list",
      "CRM": "accounting:integrationconfig_list",
      "ERP": "accounting:integrationconfig_list",
      "HRIS": "accounting:integrationconfig_list",
      "Tax Software": "accounting:integrationconfig_list",
      "Document Storage": "accounting:integrationconfig_list",
      "Custom API": "accounting:integrationconfig_list",
  },
  ```

---

## Section 4 — Templates (`templates/accounting/` — new files only)

One file per template. Mirror existing `templates/accounting/` conventions: filter-bar with
`request.GET` pre-fill, Actions column (view/edit/delete) using `|stringformat:"d"` for FK pk
comparison (CLAUDE.md Filter Rule), `has_previous`/`has_next` pagination guards (L9),
nullable FK guards (L10), empty-state, breadcrumb. **NO inline formsets on any page.**
Child-table pages (PayrollJournalLine, BudgetLine, ControlTest, PeriodCloseTask) are standalone
list/create/edit/delete pages linked from their parent's detail page.

### 2.6 Fixed Asset templates (5 files)

- [ ] `templates/accounting/fixedasset_list.html` — table: number, asset_class, description, status
  badge, acquisition_cost, accumulated_depreciation, location, custodian; filter: status dropdown;
  Actions: view/edit/delete + "Capitalize" button (shown when status=cip)
- [ ] `templates/accounting/fixedasset_detail.html` — all fields; DepreciationSchedule list (latest
  5: period, amount, book_type, status, JE link); sidebar: "Run Depreciation" POST button
  (@tenant_admin_required, shown when active), "Dispose" link, edit/delete (gated on non-disposed)
- [ ] `templates/accounting/fixedasset_form.html` — create/edit; exclude accumulated_depreciation,
  capitalization_je, system fields
- [ ] `templates/accounting/assetdisposal_list.html` — table: number, asset link, disposal_date,
  disposal_type badge, proceeds, gain_loss, journal_entry link; filter: disposal_type dropdown;
  Actions: view/edit/delete
- [ ] `templates/accounting/assetdisposal_detail.html` — all fields; JE link; sidebar: edit/delete

> `assetdisposal_form.html` — reuse the pattern; exclude gain_loss, journal_entry.
- [ ] `templates/accounting/assetdisposal_form.html` — create/edit form

### 2.7 Inventory Cost templates (4 files)

- [ ] `templates/accounting/inventorycostitem_list.html` — table: sku, description,
  valuation_method badge, standard_cost, current_avg_cost, on_hand_qty; filter: valuation_method
  dropdown; Actions: view/edit/delete
- [ ] `templates/accounting/inventorycostitem_detail.html` — all fields; related CostTransactions
  list (latest 5); sidebar: edit/delete
- [ ] `templates/accounting/inventorycostitem_form.html` — create/edit form
- [ ] `templates/accounting/costtransaction_list.html` — table: number, cost_item sku, direction
  badge, quantity, unit_cost, total_cost, transaction_date, reference_type badge, JE link; filter:
  direction + reference_type dropdowns; Actions: view/edit/delete + "Post" button (shown when no JE)
- [ ] `templates/accounting/costtransaction_detail.html` — all fields; JE link; sidebar: "Post" POST
  button (@tenant_admin_required, shown when journal_entry is null), edit/delete
- [ ] `templates/accounting/costtransaction_form.html` — create/edit; exclude total_cost, journal_entry

### 2.8 Payroll templates (4 files)

- [ ] `templates/accounting/payrolljournalbatch_list.html` — table: number, pay_period_start,
  pay_period_end, pay_date, source badge, is_accrual badge, status badge; filter: status +
  source dropdowns; Actions: view/edit/delete + "Post" button (shown when draft)
- [ ] `templates/accounting/payrolljournalbatch_detail.html` — batch header; PayrollJournalLine
  table (line_type badge, gl_account, org_unit, amount) with link to add/edit lines; JE link;
  sidebar: "Post Batch" POST button (@tenant_admin_required, shown when draft), edit/delete
- [ ] `templates/accounting/payrolljournalbatch_form.html` — create/edit; exclude journal_entry
- [ ] `templates/accounting/payrolljournalline_list.html` — scoped to a batch; table: line_type
  badge, gl_account, org_unit, amount, description; filter: line_type dropdown; Actions: edit/delete
- [ ] `templates/accounting/payrolljournalline_form.html` — create/edit (used for both
  add and edit; batch is pre-filled from URL arg)

### 2.9 Project templates (4 files + 2 for child)

- [ ] `templates/accounting/project_list.html` — table: number, name, client, billing_method badge,
  status badge, budget_amount, start_date, end_date; filter: status + billing_method dropdowns;
  Actions: view/edit/delete
- [ ] `templates/accounting/project_detail.html` — all fields; ProjectBudgetLine list (account,
  period, amount) with add/edit/delete links; budget-vs-actual summary (total budgeted vs. sum of
  tagged JournalLines); sidebar: edit/delete
- [ ] `templates/accounting/project_form.html` — create/edit form
- [ ] `templates/accounting/projectbudgetline_list.html` — table: project, gl_account, fiscal_period,
  budgeted_amount; filter: project + fiscal_period dropdowns; Actions: view/edit/delete
- [ ] `templates/accounting/projectbudgetline_detail.html` — all fields; sidebar: edit/delete
- [ ] `templates/accounting/projectbudgetline_form.html` — create/edit form

### 2.10 Multi-Entity & Consolidation templates (4 files)

- [ ] `templates/accounting/consolidationgroup_list.html` — table: name, parent_entity, member
  count, reporting_currency, is_active badge; filter: is_active dropdown; Actions: view/edit/delete
- [ ] `templates/accounting/consolidationgroup_detail.html` — all fields; member OrgUnit list;
  "Run Consolidation Report" link → `consolidation_report`; sidebar: edit/delete
- [ ] `templates/accounting/consolidationgroup_form.html` — create/edit (members ManyToManyField
  as a multi-select widget)
- [ ] `templates/accounting/intercompanytransaction_list.html` — table: number, from_entity,
  to_entity, transaction_date, amount, currency, status badge; filter: status + consolidation_group
  dropdowns; Actions: view/edit/delete + "Post" (shown when draft) + "Eliminate" (shown when posted)
- [ ] `templates/accounting/intercompanytransaction_detail.html` — all fields; from_journal_entry
  and to_journal_entry links; document attachment link; sidebar: "Post" and "Eliminate" POST
  buttons (@tenant_admin_required), edit/delete (gated on draft)
- [ ] `templates/accounting/intercompanytransaction_form.html` — create/edit; exclude
  from_journal_entry, to_journal_entry
- [ ] `templates/accounting/consolidation_report.html` — report page (no model form); consolidation
  group selector; table of aggregated revenue/expense/asset/liability by member entity; elimination
  column; consolidated totals; date-range filter

### 2.11 Tax templates (6 files)

- [ ] `templates/accounting/taxcode_list.html` — table: code, name, tax_type badge, rate_pct,
  jurisdiction_level, country/region, is_active badge; filter: tax_type + is_active dropdowns;
  Actions: view/edit/delete
- [ ] `templates/accounting/taxcode_detail.html` — all fields; effective_from/effective_to;
  payable_gl_account link; sidebar: edit/delete
- [ ] `templates/accounting/taxcode_form.html` — create/edit form
- [ ] `templates/accounting/taxnexus_list.html` — table: jurisdiction_name, country, nexus_type
  badge, threshold_amount, current_ytd_sales, is_registered badge; filter: nexus_type +
  is_registered dropdowns; Actions: view/edit/delete
- [ ] `templates/accounting/taxnexus_detail.html` — all fields; related filing obligations list;
  sidebar: edit/delete
- [ ] `templates/accounting/taxnexus_form.html` — create/edit form
- [ ] `templates/accounting/taxfilingobligation_list.html` — table: tax_nexus, filing period,
  due_date, status badge (overdue highlighted), tax_due; filter: status + tax_nexus dropdowns;
  Actions: view/edit/delete
- [ ] `templates/accounting/taxfilingobligation_detail.html` — all fields; payment link if remitted;
  sidebar: edit/delete
- [ ] `templates/accounting/taxfilingobligation_form.html` — create/edit; exclude filed_by

### 2.12 Reporting & Compliance templates (5 files)

- [ ] `templates/accounting/scheduledreport_list.html` — table: report_type badge, frequency badge,
  format, next_run_at, is_active badge; filter: report_type + frequency + is_active dropdowns;
  Actions: view/edit/delete
- [ ] `templates/accounting/scheduledreport_detail.html` — all fields; recipients list; sidebar:
  edit/delete
- [ ] `templates/accounting/scheduledreport_form.html` — create/edit; exclude last_run_at
- [ ] `templates/accounting/balance_sheet.html` — report: as-of date filter (GET param); two-column
  layout (Assets left, Liabilities+Equity right); account groups with subtotals; totals row;
  "must balance" check note
- [ ] `templates/accounting/profit_and_loss.html` — report: date-range filter; Revenue section +
  Expense section + Net Income row; prior-period column if selected
- [ ] `templates/accounting/cash_flow_statement.html` — report: date-range filter; operating /
  investing / financing sections (from GLAccount.cash_flow_category); net change in cash
- [ ] `templates/accounting/budget_variance_report.html` — report: BudgetVersion selector +
  FiscalPeriod filter; table: gl_account | org_unit | budgeted_amount | actual | variance | variance%
  (highlighted red when over budget)

### 2.13 Budgeting & Planning templates (4 files)

- [ ] `templates/accounting/budgetversion_list.html` — table: number, name, fiscal_year,
  version_type badge, is_active badge, is_locked badge, copied_from link; filter: version_type +
  fiscal_year + is_active dropdowns; Actions: view/edit/delete + "Copy" POST button
- [ ] `templates/accounting/budgetversion_detail.html` — all fields; BudgetLine count + total;
  link to `budgetline_list` filtered by this version; "Copy to What-If" POST button in sidebar;
  sidebar: edit/delete
- [ ] `templates/accounting/budgetversion_form.html` — create/edit; exclude approved_by
- [ ] `templates/accounting/budgetline_list.html` — table: budget_version link, gl_account code+name,
  fiscal_period, org_unit, budgeted_amount, is_locked_actuals badge; filter: budget_version +
  gl_account (dropdown) + fiscal_period + org_unit dropdowns; Actions: view/edit/delete
- [ ] `templates/accounting/budgetline_detail.html` — all fields; sidebar: edit/delete
- [ ] `templates/accounting/budgetline_form.html` — create/edit form (budget_version, gl_account,
  fiscal_period, org_unit, budgeted_amount, is_locked_actuals)

### 2.14 Audit & Controls templates (7 files)

- [ ] `templates/accounting/controlrecord_list.html` — table: name, control_type badge,
  frequency badge, risk_area, owner, is_active badge; filter: control_type + frequency + is_active
  dropdowns; Actions: view/edit/delete
- [ ] `templates/accounting/controlrecord_detail.html` — all fields; ControlTest list (test_date,
  tester, result badge, evidence_document link) with link to add new test; sidebar: edit/delete
- [ ] `templates/accounting/controlrecord_form.html` — create/edit form
- [ ] `templates/accounting/controltest_list.html` — table: control_record link, test_date, tester,
  result badge, notes truncated, evidence_document link; filter: result dropdown; Actions:
  view/edit/delete
- [ ] `templates/accounting/controltest_detail.html` — all fields; sidebar: edit/delete
- [ ] `templates/accounting/controltest_form.html` — create/edit (control_record, test_date, tester,
  result, notes, evidence_document)
- [ ] `templates/accounting/periodclosetask_list.html` — table: fiscal_period, task_name,
  task_type badge, assignee, due_date, status badge; filter: fiscal_period + task_type + status
  dropdowns; Actions: view/edit/delete + "Mark Done" POST button (shown when status!=done)
- [ ] `templates/accounting/periodclosetask_detail.html` — all fields; completed_by/completed_at
  if done; sidebar: "Mark Done" POST button (@login_required, not admin-only), edit/delete
- [ ] `templates/accounting/periodclosetask_form.html` — create/edit; exclude completed_by,
  completed_at
- [ ] `templates/accounting/audit_trail_list.html` — read-only list over `core.AuditLog` filtered
  to `tenant`; table: timestamp, user, model_name, object_id, action, changes summary; filter:
  model_name (select of distinct values) + user (select) + action (select) + date range (start/end);
  no create/edit/delete; pagination

### 2.15 Integration & API templates (3 files)

- [ ] `templates/accounting/integrationconfig_list.html` — table: integration_type badge,
  endpoint_url (truncated), is_active badge, sync_status badge, last_synced_at; filter:
  integration_type + is_active dropdowns; Actions: view/edit/delete; masked api_key_encrypted
  display (show `prefix:****` — never the hash)
- [ ] `templates/accounting/integrationconfig_detail.html` — all fields; api_key_encrypted shown as
  `prefix:****` (never raw); "Rotate Key" POST button in sidebar (@tenant_admin_required); if
  `request.session["_key_reveal"]` is set, show one-time reveal box with copy button and pop it
  (L25 pattern); sidebar: edit/delete
- [ ] `templates/accounting/integrationconfig_form.html` — create/edit; DO NOT render
  api_key_encrypted field (L20); shows note "Use 'Rotate Key' to set the API credential"

---

## Section 5 — Verify

Run all commands with `C:\xampp\htdocs\NavERP\venv\Scripts\python.exe`:

- [ ] `python manage.py makemigrations accounting` — confirm single `0002_advanced.py` covering
  all new tables + field additions on existing models; no `0002a/0002b` splits.
- [ ] `python manage.py sqlmigrate accounting 0002` — review SQL: FK references to
  `accounting_fixedasset`, `accounting_project`, `accounting_consolidationgroup`, etc. all resolve;
  unique_together constraints present; `db_index` on all tenant FKs; no reference to unbuilt
  tables (no `inventory_*`, `hrm_*`).
- [ ] `python manage.py migrate` — zero errors on `nav_erp`.
- [ ] `python manage.py seed_accounting` — first run: `_seed_advanced` creates all demo data;
  prints new login instructions and superuser-no-tenant warning.
- [ ] `python manage.py seed_accounting` (second run) — must skip all advanced model blocks
  with "already exists — skipping"; zero duplicate rows created.
- [ ] `python manage.py check` — zero errors, zero warnings.
- [ ] Write `temp/accounting_advanced_smoke.py` — test-client sweep:
  - All new `accounting:*` URL names (list, detail, create, edit, report views) → 200 or 302.
  - POST action URLs (asset_capitalize, depreciation_run, asset_dispose, post_cost_transaction,
    payroll_batch_post, ict_post, ict_eliminate, budget_copy, task_complete,
    integration_rotate_key) → 302 redirect (not 500); wrong-tenant object → 404.
  - No `{#` / `{% comment` template leaks in any rendered page.
  - Cross-tenant IDOR: pk from tenant B while logged in as tenant A → 404 on all detail views.
  - JE balance assertion for each posting action: after action, verify the posted `JournalEntry`
    has Σdebit == Σcredit and > 0.
  - `depreciation_run` on an `active` FixedAsset → creates a `DepreciationSchedule` row,
    posts a balanced JE, updates `accumulated_depreciation` on the asset.
  - `asset_dispose` → sets `FixedAsset.status = "disposed"`, posts balanced disposal JE
    (Dr accum_depr + cash, Cr asset_cost, Dr/Cr gain_loss account).
  - `payroll_batch_post` → sets batch status=`"posted"`, creates balanced multi-leg JE.
  - `ict_post` → creates two balanced JEs (one per entity), links them to the ICT.
  - `integration_rotate_key` → api_key_encrypted updated to `prefix:sha256_hex` format;
    session contains `_key_reveal`; second GET to detail pops it (absent on refresh).
  - Report pages (balance_sheet, profit_and_loss, cash_flow_statement, budget_variance_report,
    consolidation_report) → 200 with no missing template variables or `None` rendered inline.
  - Sidebar: 2.6–2.15 all show as **Live** in the navigation.
- [ ] Run `temp/accounting_advanced_smoke.py` — all checks green.
- [ ] Sidebar check: sub-modules 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 2.15 all
  show as **Live** (not "On the roadmap") in the sidebar navigation.

---

## Section 6 — Close-out

### Review agents (run in order, one at a time, commit fixes between)

- [ ] Run **`code-reviewer` agent** — check: every posting action verifies Σdebit==Σcredit before
  `JournalEntry.status='posted'`; `accumulated_depreciation` updated atomically in `depreciation_run`;
  `IntegrationConfig.api_key_encrypted` never set on the ModelForm (L20); all `*_at` system fields
  excluded from forms (L22); `@tenant_admin_required` on all privileged action views;
  `filed_by`/`completed_by`/`approved_by` set in view not form; `total_cost` and `gain_loss`
  computed in view before save; L11 `.isdigit()` guard on all FK list filters.

- [ ] Run **`explorer` agent** — verify: every URL name in the new LIVE_LINKS resolves (no 404);
  every new template's context variables are passed by the corresponding view; child-table list
  pages (PayrollJournalLine, BudgetLine, etc.) are reachable from their parent's detail page;
  `from .models_advanced import *` is present at bottom of `models.py`.

- [ ] Run **`frontend-reviewer` agent** — check: filter `selected` comparisons use
  `|stringformat:"d"` for all FK pk dropdowns; all `<label for=id_*>` present; pagination guards
  use `has_previous`/`has_next` (L9); no unknown CSS utility classes (L13); report pages render
  cleanly with no inline `None` or blank columns; "Rotate Key" reveal box shows only once (L25);
  `api_key_encrypted` never rendered in plaintext anywhere.

- [ ] Run **`performance-reviewer` agent** — check: `fixedasset_list` select_related for
  `custodian`, `location`; `costtransaction_list` select_related for `cost_item`; budget_variance
  query is a single annotated JOIN (not Python loops); consolidation_report aggregates in one query
  per entity; no N+1 on `ControlRecord` detail (prefetch `tests`); `audit_trail_list` paginates
  (do not load all AuditLog rows).

- [ ] Run **`qa-smoke-tester` agent** — verify: all POST action views require POST method (405 on
  GET); all delete views are POST-only; `depreciation_run` on a `cip` asset → rejected (not active);
  `asset_dispose` on an already-disposed asset → rejected; `payroll_batch_post` when no lines →
  rejected (or warns); `ict_eliminate` on a draft ICT → rejected; `budget_copy` creates new
  BudgetVersion + copies all BudgetLines; seed runs twice → row count unchanged.

- [ ] Run **`security-reviewer` agent** — verify: `api_key_encrypted` absent from every form
  widget (L20); `IntegrationConfigForm.Meta.fields` does not include `api_key_encrypted`;
  `integration_rotate_key` stores `prefix:sha256_hex` not raw secret; session `_key_reveal`
  is popped (not readable on refresh, L25); cross-tenant IDOR 404 on ALL new pk-based views;
  child-table FKs verified against tenant (e.g. `PayrollJournalLine` accessed via batch that
  belongs to request.tenant); `PeriodCloseTask.fiscal_period` FK scoped to tenant in form
  `__init__`; `consolidation_group` members only from tenant's OrgUnits; all privileged
  action views gated with `@tenant_admin_required`.

- [ ] Run **`test-writer` agent** — write tests covering:
  depreciation_run balanced JE and accumulated_depreciation update,
  asset_dispose gain/loss JE correctness (both gain and loss paths),
  payroll_batch_post multi-leg balanced JE,
  ict_post two paired JEs balanced individually,
  post_cost_transaction weighted-avg update on InventoryCostItem,
  budget_copy duplicates BudgetLines correctly,
  integration_rotate_key stores prefix:hash not raw secret + session pop,
  balance_sheet and profit_and_loss render with non-empty data,
  cross-tenant IDOR 404 on all new model detail views,
  seeder idempotency (run twice → row count unchanged for all 14 models).

### Documentation close-out

- [ ] Update **`.claude/skills/accounting/SKILL.md`** — extend existing skill with 2.6–2.15
  models (all 14 new tables + child tables), new URL names, new LIVE_LINKS entries, new seeder
  section (`_seed_advanced`), posting action JE legs, `IntegrationConfig` security conventions
  (L20/L25), `models_advanced.py` / `views_advanced.py` / `forms_advanced.py` file locations.
  Do NOT rewrite the 2.1–2.5 section; append only.

- [ ] Update **`README.md`** — add sub-modules 2.6–2.15 to the feature table; add
  `seed_accounting` already seeds the advanced data via `_seed_advanced`; add route map
  entries for new `accounting:*` URLs.

### Per-file commit list (PowerShell-safe, one file per commit)

```
git add 'apps\accounting\models_advanced.py'; git commit -m 'feat(accounting): models_advanced.py — 14 new models for 2.6-2.15 (FixedAsset/DepreciationSchedule/AssetDisposal/InventoryCostItem/CostTransaction/PayrollJournalBatch/PayrollJournalLine/Project/ProjectBudgetLine/ConsolidationGroup/IntercompanyTransaction/TaxCode/TaxNexus/TaxFilingObligation/ScheduledReport/BudgetVersion/BudgetLine/ControlRecord/ControlTest/PeriodCloseTask/IntegrationConfig)'
git add 'apps\accounting\models.py'; git commit -m 'feat(accounting): models.py — add models_advanced import + 5 field additions on existing models (JournalLine.project, Invoice.project, JournalEntry.consolidation_group, JournalEntry.ENTRY_TYPE elimination, GLAccount.cash_flow_category)'
git add 'apps\accounting\migrations\0002_advanced.py'; git commit -m 'feat(accounting): migration 0002 — 14 new advanced models + 5 field additions on existing tables'
git add 'apps\accounting\forms_advanced.py'; git commit -m 'feat(accounting): forms_advanced.py — ModelForms for all 14 new models; system fields/api_key_encrypted excluded per L20/L22'
git add 'apps\accounting\views_advanced.py'; git commit -m 'feat(accounting): views_advanced.py — function-based CRUD + 10 posting/action views (asset_capitalize, depreciation_run, asset_dispose, post_cost_transaction, payroll_batch_post, ict_post, ict_eliminate, budget_copy, task_complete, integration_rotate_key) + 5 report views'
git add 'apps\accounting\urls.py'; git commit -m 'feat(accounting): urls.py — append 2.6-2.15 URL patterns for all 14 new models + 5 report views + audit_trail_list'
git add 'apps\accounting\admin.py'; git commit -m 'feat(accounting): admin.py — append admin registration for 14 new models with child TabularInlines'
git add 'apps\accounting\management\commands\seed_accounting.py'; git commit -m 'feat(accounting): extend seed_accounting with _seed_advanced — idempotent demo data for 2.6-2.15 models'
git add 'apps\core\navigation.py'; git commit -m 'feat(core/nav): LIVE_LINKS 2.6-2.15 — fixed-assets/cost/payroll/projects/consolidation/tax/reporting/budgeting/controls/integration routes'
git add 'templates\accounting\fixedasset_list.html'; git commit -m 'feat(accounting): fixed asset list with status filter and capitalize action'
git add 'templates\accounting\fixedasset_detail.html'; git commit -m 'feat(accounting): fixed asset detail with depreciation schedule list and run-depreciation action'
git add 'templates\accounting\fixedasset_form.html'; git commit -m 'feat(accounting): fixed asset create/edit form'
git add 'templates\accounting\assetdisposal_list.html'; git commit -m 'feat(accounting): asset disposal list with disposal_type filter'
git add 'templates\accounting\assetdisposal_detail.html'; git commit -m 'feat(accounting): asset disposal detail'
git add 'templates\accounting\assetdisposal_form.html'; git commit -m 'feat(accounting): asset disposal create/edit form'
git add 'templates\accounting\inventorycostitem_list.html'; git commit -m 'feat(accounting): inventory cost item list with valuation_method filter'
git add 'templates\accounting\inventorycostitem_detail.html'; git commit -m 'feat(accounting): inventory cost item detail with related cost transactions'
git add 'templates\accounting\inventorycostitem_form.html'; git commit -m 'feat(accounting): inventory cost item create/edit form'
git add 'templates\accounting\costtransaction_list.html'; git commit -m 'feat(accounting): cost transaction list with direction/reference_type filters and post action'
git add 'templates\accounting\costtransaction_detail.html'; git commit -m 'feat(accounting): cost transaction detail with post action'
git add 'templates\accounting\costtransaction_form.html'; git commit -m 'feat(accounting): cost transaction create/edit form'
git add 'templates\accounting\payrolljournalbatch_list.html'; git commit -m 'feat(accounting): payroll journal batch list with status/source filters and post action'
git add 'templates\accounting\payrolljournalbatch_detail.html'; git commit -m 'feat(accounting): payroll journal batch detail with journal lines table and post action'
git add 'templates\accounting\payrolljournalbatch_form.html'; git commit -m 'feat(accounting): payroll journal batch create/edit form'
git add 'templates\accounting\payrolljournalline_list.html'; git commit -m 'feat(accounting): payroll journal line list scoped to batch with line_type filter'
git add 'templates\accounting\payrolljournalline_form.html'; git commit -m 'feat(accounting): payroll journal line create/edit form'
git add 'templates\accounting\project_list.html'; git commit -m 'feat(accounting): project list with status/billing_method filters'
git add 'templates\accounting\project_detail.html'; git commit -m 'feat(accounting): project detail with budget lines and budget-vs-actual summary'
git add 'templates\accounting\project_form.html'; git commit -m 'feat(accounting): project create/edit form'
git add 'templates\accounting\projectbudgetline_list.html'; git commit -m 'feat(accounting): project budget line list with project/period filters'
git add 'templates\accounting\projectbudgetline_detail.html'; git commit -m 'feat(accounting): project budget line detail'
git add 'templates\accounting\projectbudgetline_form.html'; git commit -m 'feat(accounting): project budget line create/edit form'
git add 'templates\accounting\consolidationgroup_list.html'; git commit -m 'feat(accounting): consolidation group list with is_active filter'
git add 'templates\accounting\consolidationgroup_detail.html'; git commit -m 'feat(accounting): consolidation group detail with member list and consolidation report link'
git add 'templates\accounting\consolidationgroup_form.html'; git commit -m 'feat(accounting): consolidation group create/edit form with multi-select members'
git add 'templates\accounting\intercompanytransaction_list.html'; git commit -m 'feat(accounting): intercompany transaction list with status/group filters and post/eliminate actions'
git add 'templates\accounting\intercompanytransaction_detail.html'; git commit -m 'feat(accounting): intercompany transaction detail with JE links and post/eliminate actions'
git add 'templates\accounting\intercompanytransaction_form.html'; git commit -m 'feat(accounting): intercompany transaction create/edit form'
git add 'templates\accounting\consolidation_report.html'; git commit -m 'feat(accounting): consolidation report — group aggregation with elimination column'
git add 'templates\accounting\taxcode_list.html'; git commit -m 'feat(accounting): tax code list with tax_type/is_active filters'
git add 'templates\accounting\taxcode_detail.html'; git commit -m 'feat(accounting): tax code detail'
git add 'templates\accounting\taxcode_form.html'; git commit -m 'feat(accounting): tax code create/edit form'
git add 'templates\accounting\taxnexus_list.html'; git commit -m 'feat(accounting): tax nexus list with nexus_type/is_registered filters'
git add 'templates\accounting\taxnexus_detail.html'; git commit -m 'feat(accounting): tax nexus detail with filing obligations list'
git add 'templates\accounting\taxnexus_form.html'; git commit -m 'feat(accounting): tax nexus create/edit form'
git add 'templates\accounting\taxfilingobligation_list.html'; git commit -m 'feat(accounting): tax filing obligation list with status/nexus filters'
git add 'templates\accounting\taxfilingobligation_detail.html'; git commit -m 'feat(accounting): tax filing obligation detail with payment link'
git add 'templates\accounting\taxfilingobligation_form.html'; git commit -m 'feat(accounting): tax filing obligation create/edit form'
git add 'templates\accounting\scheduledreport_list.html'; git commit -m 'feat(accounting): scheduled report list with report_type/frequency/is_active filters'
git add 'templates\accounting\scheduledreport_detail.html'; git commit -m 'feat(accounting): scheduled report detail with recipients list'
git add 'templates\accounting\scheduledreport_form.html'; git commit -m 'feat(accounting): scheduled report create/edit form'
git add 'templates\accounting\balance_sheet.html'; git commit -m 'feat(accounting): balance sheet report — assets/liabilities/equity as of date'
git add 'templates\accounting\profit_and_loss.html'; git commit -m 'feat(accounting): profit and loss report — revenue minus expenses for date range'
git add 'templates\accounting\cash_flow_statement.html'; git commit -m 'feat(accounting): cash flow statement — operating/investing/financing sections'
git add 'templates\accounting\budget_variance_report.html'; git commit -m 'feat(accounting): budget vs actual variance report with BudgetVersion selector'
git add 'templates\accounting\budgetversion_list.html'; git commit -m 'feat(accounting): budget version list with version_type/fiscal_year/is_active filters and copy action'
git add 'templates\accounting\budgetversion_detail.html'; git commit -m 'feat(accounting): budget version detail with budget lines summary and copy action'
git add 'templates\accounting\budgetversion_form.html'; git commit -m 'feat(accounting): budget version create/edit form'
git add 'templates\accounting\budgetline_list.html'; git commit -m 'feat(accounting): budget line list with version/account/period/org_unit filters'
git add 'templates\accounting\budgetline_detail.html'; git commit -m 'feat(accounting): budget line detail'
git add 'templates\accounting\budgetline_form.html'; git commit -m 'feat(accounting): budget line create/edit form'
git add 'templates\accounting\controlrecord_list.html'; git commit -m 'feat(accounting): control record list with control_type/frequency/is_active filters'
git add 'templates\accounting\controlrecord_detail.html'; git commit -m 'feat(accounting): control record detail with control tests list'
git add 'templates\accounting\controlrecord_form.html'; git commit -m 'feat(accounting): control record create/edit form'
git add 'templates\accounting\controltest_list.html'; git commit -m 'feat(accounting): control test list with result filter'
git add 'templates\accounting\controltest_detail.html'; git commit -m 'feat(accounting): control test detail'
git add 'templates\accounting\controltest_form.html'; git commit -m 'feat(accounting): control test create/edit form'
git add 'templates\accounting\periodclosetask_list.html'; git commit -m 'feat(accounting): period close task list with period/task_type/status filters and mark-done action'
git add 'templates\accounting\periodclosetask_detail.html'; git commit -m 'feat(accounting): period close task detail with mark-done action'
git add 'templates\accounting\periodclosetask_form.html'; git commit -m 'feat(accounting): period close task create/edit form'
git add 'templates\accounting\audit_trail_list.html'; git commit -m 'feat(accounting): audit trail list — read-only view over core.AuditLog with model/user/action filters'
git add 'templates\accounting\integrationconfig_list.html'; git commit -m 'feat(accounting): integration config list with type/is_active filters; api_key shown masked'
git add 'templates\accounting\integrationconfig_detail.html'; git commit -m 'feat(accounting): integration config detail with rotate-key action and one-time reveal (L25)'
git add 'templates\accounting\integrationconfig_form.html'; git commit -m 'feat(accounting): integration config create/edit form — api_key_encrypted excluded (L20)'
git add 'temp\accounting_advanced_smoke.py'; git commit -m 'test(accounting): advanced smoke test — 2.6-2.15 routes 200/302, posting JE balance, IDOR 404, rotate-key L25 session pop, report pages render'
git add '.claude\skills\accounting\SKILL.md'; git commit -m 'docs(skill/accounting): extend SKILL.md with 2.6-2.15 models, URLs, seeder _seed_advanced, IntegrationConfig security'
git add 'README.md'; git commit -m 'docs(readme): accounting 2.6-2.15 — feature table, route map, seed_accounting covers advanced models'
```

---

## Section 7 — Later passes / deferred

- **Live Plaid bank feed OAuth** — `IntegrationConfig` (type=plaid) is buildable now as a config
  stub; the actual Plaid token exchange, account-link flow, and daily transaction polling requires
  Plaid SDK + OAuth redirect endpoint. Deferred to an integration pass.
- **Avalara AvaTax real-time API** — `TaxCode` rate master covers manual/imported rates;
  the Avalara AvaTax API call on invoice-post (12,000+ jurisdiction lookup) needs
  `IntegrationConfig` credential + HTTP call. Deferred.
- **Vertex income tax provision automation** — `TaxFilingObligation` stub supports manual entry
  of current/deferred tax amounts; automated deferred-tax calculation from temporary differences
  (asset book-tax timing differences) requires a rules engine. Deferred.
- **XBRL / EDGAR filing** — structured tagging of financials for SEC/EDGAR submission. Deferred
  (public companies only; requires XBRL taxonomy library).
- **Module 5 Item FK on `InventoryCostItem`** — when Inventory (Module 5) ships, add a FK from
  `InventoryCostItem` to `inventory.Item` and from `CostTransaction` to `inventory.StockMove`.
  The financial valuation layer is buildable now without it.
- **Module 3 HRM FK on `PayrollJournalBatch`** — when HRM (Module 3) ships, add a FK from
  `PayrollJournalBatch` to `hrm.PayrollRun`; the accounting-GL layer is buildable now without it.
- **Full WBS task hierarchy on `Project`** — multi-level task tree (epic/task/subtask). Covered
  in the NavERP ERD stub; deferred to the full Project Management module (Module 7).
- **Earned Value Management (EVM)** — BCWS, BCWP, ACWP, SPI, CPI metrics. Deferred to Module 7
  Projects where schedule data exists.
- **HRIS API payroll import (Workday/ADP)** — `PayrollJournalBatch.source='hris_import'` is
  modeled; live API connector for auto-creating batches = integration/later.
- **Stripe/PayPal payment gateway webhooks** — `IntegrationConfig` type=stripe/paypal is modeled;
  webhook endpoint + signature verification = integration/later.
- **DRF REST API layer** — Django REST Framework serializers/viewsets for new accounting objects.
  No new models needed; DRF is an integration/API pass separate from the core module build.
- **CRON-based scheduled report delivery** — `ScheduledReport` model buildable now;
  Celery beat task for timed generation + email = async-worker pass.
- **SoDRule (Segregation of Duties documentation table)** — trimmed from this pass; the audit
  trail list view surfaces the behavioral trail; a formal `SoDRule` table with automated scanning
  is an audit-controls enhancement pass.
- **`ImpairmentRecord` / `AssetAudit`** — research identified these as differentiators;
  trimmed from 14-model scope; can be added in a Fixed Assets enhancement pass.
- **`CurrencyTranslation` run table** — CTA calculation and translation JEs; deferred from 2.10;
  the data model (ExchangeRate + OrgUnit-as-entity + ConsolidationGroup) is ready.
- **Minority interest calculation** — complex equity consolidation for partial ownership.
  Deferred; full consolidation engine is an enterprise-only feature.
- **Budget encumbrance blocking** — view-layer budget check against BudgetLine is buildable;
  pre-encumbrance on purchase requisitions requires Module 6 Procurement to ship first.
- **`LandedCostAllocation` table** — allocation of freight/duty/insurance across CostTransactions.
  Research rated this "common"; trimmed to keep model count at 14; add in a cost-management pass.
- **Invoice/Bill void actions** — carried forward from 2.1–2.5 deferred list; still pending.

## Review notes — Module 2 Advanced (2.6–2.15) outcome (2026-06-21)

**Built:** 14 accounting-owned models (trimmed from the 21-model research proposal — one primary live page per
sub-module, NO inline formsets, migration `0002` purely additive + `0003` indexes) in `models_advanced.py`/
`forms_advanced.py`/`views_advanced.py`, 43 templates, idempotent `_seed_advanced`, LIVE_LINKS 2.6–2.15. Reuses the
2.1–2.5 GL spine + `core.OrgUnit` (entity/cost-centre dimension — no new Entity table). Six balanced-JE posting
actions (depreciate/dispose/allocate/payroll/job-cost/intercompany) via `_post_journal_entry` + Balance Sheet/P&L/
budget-variance reports + a write-once/reveal-once hashed integration key. Backend solo; 43 templates via a 6-agent
Workflow. Migrated clean; seeder idempotent; `manage.py check` clean; ledger balanced after every post.

**Verification:** advanced GET smoke (69 routes 200/302, no leaks, IDOR 404); functional posting check (all 6 actions
post balanced JEs, disposal gain/loss, masked key); qa-smoke-tester **118/118** (POST-only, immutability, depreciation
cap, admin gating, CSRF, reports balance); test-writer **100 new pytest tests** → accounting suite 74→**174**, full
project **924→1024**, no regressions.

**Review agents (all 7, in order):**
- **code-reviewer** → fixed: intercompany org-unit attribution (lender=due-from); distinct disposal account fallbacks
  (1600/1690); je-None guards on 4 posts; budget_variance tenant-None guard; atomic key rotation; budget-line views
  redirect to parent; budget badge real choices; seed last_depreciation_date. (Verified non-issues: ZERO is Decimal,
  payroll balances, TaxReturn posts no JE.)
- **explorer** → 1 silent-blank (budget_detail `obj.description`→`obj.notes`); else clean.
- **frontend-reviewer** → net-loss styled red on balance sheet; budget-line Cancel returns to parent; gl_account guard.
  (Icon `title` vs aria-label flagged app-wide, not forked.)
- **performance-reviewer** → project_detail 5 aggregates → 1 grouped query; budget_detail/variance evaluate once;
  dropped 2 unused select_related; added (tenant,status) indexes on 4 advanced models (migration 0003).
- **qa-smoke-tester** → 118/118, no code changes.
- **security-reviewer** → integration_edit/delete + tax_return_edit/delete now `@tenant_admin_required`; `eliminated`
  off the intercompany form + admin toggle action; (unsalted-sha256 flagged app-wide vs the foundation EncryptionKey).
- **test-writer** → 100 tests across posting / security / reports.

**Deferred (Section 7 + SKILL.md):** live integration sync (Plaid/Avalara/Stripe APIs), DRF REST API, Celery
scheduled-report delivery, parallel tax-depreciation books, full WBS/earned-value, CTA currency translation,
XBRL/EDGAR, per-tenant configurable control accounts, invoice/bill void, and FK migration onto Inventory/HRM/Projects
masters when those modules land.

---

# Module 3 — Human Resource Management (hrm) — plan from research-hrm.md  (2026-06-21)

> **Context:** New `apps/hrm` app. Sub-modules 3.1–3.12 covered in this pass (8 models: employee
> foundation + leave management + attendance/shift). Payroll/performance/recruiting are deferred
> to pass 2. Every HRM table FKs to `EmployeeProfile`, never directly to `core.Party`.
> `accounting.PayrollRun` (PRUN-#####) already owns GL posting — HRM must NOT touch it this pass.
> Departments reuse `core.OrgUnit` (kind=department) — no new Department table.

---

## Models (from research)

- [ ] **`Designation`** — job title catalog with grade + salary band, linked to `core.OrgUnit`
  - `tenant` FK→`"core.Tenant"` CASCADE related_name=`"hrm_designations"` db_index=True
  - `name` CharField max_length=255 (e.g. "Senior Software Engineer")
  - `grade` CharField max_length=50 blank (e.g. "L3", "M1", "Executive")
  - `department` FK→`"core.OrgUnit"` SET_NULL null blank related_name=`"designations"` (reuses OrgUnit kind=department)
  - `min_salary` DecimalField max_digits=14 decimal_places=2 null blank (salary band floor)
  - `max_salary` DecimalField max_digits=14 decimal_places=2 null blank (salary band ceiling)
  - `is_active` BooleanField default=True
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - Meta: ordering=["name"]; unique_together=("tenant","name")
  - Indexes: (tenant, is_active); (tenant, department)
  - __str__: `f"{self.name} ({self.grade})"` if grade else name
  - Drivers: "Designation/Job Title Hierarchy with salary bands" (Workday, SAP SuccessFactors, ADP, Zoho People, Paycom, Frappe HRMS — table-stakes)
  - Reuses: `core.OrgUnit` for department reference; adds HRM-owned job-grade table

- [ ] **`EmployeeProfile`** [EMP-] — HRM anchor; 1:1 extension of `core.Party` + `core.Employment`
  - Inherits `TenantNumbered` abstract base (local copy in `apps/hrm/models.py`): `tenant`, `number`, `created_at`, `updated_at`; `NUMBER_PREFIX = "EMP"`; `unique_together = ("tenant", "number")`; save() 5-retry guard via `core.utils.next_number`
  - `party` OneToOneField→`"core.Party"` CASCADE related_name=`"employee_profile"` (the underlying person record)
  - `employment` OneToOneField→`"core.Employment"` SET_NULL null blank related_name=`"employee_profile"` (job title, org_unit, manager, hired_on, status from core)
  - `designation` FK→`"hrm.Designation"` SET_NULL null blank related_name=`"employees"` (HRM-specific job grade)
  - `EMPLOYEE_TYPE_CHOICES = [("full_time","Full Time"),("part_time","Part Time"),("contract","Contract"),("intern","Intern"),("consultant","Consultant")]`
  - `employee_type` CharField max_length=20 choices=EMPLOYEE_TYPE_CHOICES default="full_time"
  - `GENDER_CHOICES = [("male","Male"),("female","Female"),("other","Other"),("prefer_not_to_say","Prefer Not to Say")]`
  - `gender` CharField max_length=20 choices=GENDER_CHOICES blank
  - `date_of_birth` DateField null blank
  - `BLOOD_GROUP_CHOICES = [("A+","A+"),("A-","A-"),("B+","B+"),("B-","B-"),("AB+","AB+"),("AB-","AB-"),("O+","O+"),("O-","O-")]`
  - `blood_group` CharField max_length=5 choices=BLOOD_GROUP_CHOICES blank
  - `nationality` CharField max_length=100 blank
  - `personal_email` EmailField blank (separate from corporate email in core.ContactMethod)
  - `mobile` CharField max_length=30 blank
  - `bank_name` CharField max_length=255 blank (driver: self-service bank update — BambooHR, Gusto, Zoho People)
  - `bank_account` CharField max_length=64 blank (account number; stored as plain text, not encrypted — flag for security reviewer)
  - `bank_routing` CharField max_length=20 blank (routing/IFSC/SWIFT code)
  - `probation_end_date` DateField null blank (driver: lifecycle management — SAP SuccessFactors, Zoho People)
  - `confirmed_on` DateField null blank (date probation formally ended and employee confirmed permanent)
  - `emergency_contact_name` CharField max_length=255 blank
  - `emergency_contact_phone` CharField max_length=30 blank
  - `emergency_contact_relation` CharField max_length=100 blank
  - `photo` ImageField upload_to=`"hrm/photos/%Y/%m/"` null blank (passport-size photo)
  - `notes` TextField blank (HR-internal notes)
  - Meta: ordering=["party__name"]; unique_together already from TenantNumbered; indexes: (tenant, employee_type), (tenant, designation)
  - __str__: `f"{self.number} · {self.party.name}"`
  - Drivers: "Centralized Employee Database" seen in all 10 products; EMP- number matches Workday/BambooHR/Frappe HRMS employee ID pattern; emergency contact = Rippling/BambooHR table-stakes
  - Reuses: `core.Party` (person record), `core.Employment` (job/org/manager), `core.OrgUnit` (via employment.org_unit)
  - IMPORTANT: all other HRM models FK to `EmployeeProfile`, not to `core.Party` directly

- [ ] **`LeaveType`** — configurable leave catalog (no auto-number; few dozen rows per tenant)
  - `tenant` FK→`"core.Tenant"` CASCADE related_name=`"hrm_leave_types"` db_index=True
  - `name` CharField max_length=100 (e.g. "Annual Leave", "Sick Leave")
  - `code` CharField max_length=20 (e.g. "AL", "SL", "CL", "CO", "UNPAID")
  - `is_paid` BooleanField default=True (driver: unpaid leave tracking — all products)
  - `ACCRUAL_CHOICES = [("none","No Accrual"),("monthly","Monthly Accrual"),("annual","Annual Grant")]`
  - `accrual_rule` CharField max_length=20 choices=ACCRUAL_CHOICES default="annual"
  - `accrual_days` DecimalField max_digits=5 decimal_places=2 default=0 (days accrued per cycle; driver: BambooHR/Zoho/Frappe HRMS configurable accrual)
  - `max_balance` DecimalField max_digits=5 decimal_places=2 default=0 (0=unlimited; driver: capping leave accumulation)
  - `max_carry_forward` DecimalField max_digits=5 decimal_places=2 default=0 (days carriable to next year; 0=none; driver: Zoho People/Frappe HRMS)
  - `encashable` BooleanField default=False (driver: encashment flag — Zoho People, SAP SuccessFactors, Frappe HRMS)
  - `is_active` BooleanField default=True
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - Meta: ordering=["name"]; unique_together=("tenant","code")
  - Indexes: (tenant, is_active)
  - __str__: `f"{self.name} ({self.code})"`
  - Drivers: every product configures leave types; BambooHR/Zoho People/Gusto/ADP/Frappe HRMS all expose accrual/carry-forward/encashment flags

- [ ] **`LeaveAllocation`** [LA-] — per-employee per-year entitlement; balance DERIVED not stored
  - Inherits `TenantNumbered`; `NUMBER_PREFIX = "LA"`
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"leave_allocations"`
  - `leave_type` FK→`"hrm.LeaveType"` CASCADE related_name=`"allocations"`
  - `year` PositiveSmallIntegerField (e.g. 2026; driver: annual leave cycle)
  - `allocated_days` DecimalField max_digits=5 decimal_places=2
  - `note` TextField blank
  - `STATUS_CHOICES = [("draft","Draft"),("active","Active"),("expired","Expired")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="active"
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - Meta: ordering=["-year","employee__party__name"]; unique_together=("tenant","number"); also unique_together=("tenant","employee","leave_type","year") to prevent duplicates
  - Indexes: (tenant, employee, year), (tenant, leave_type, year), (tenant, status)
  - Property `used_days`: `LeaveRequest.objects.filter(employee=self.employee, leave_type=self.leave_type, start_date__year=self.year, status="approved").aggregate(Sum("days"))["days__sum"] or 0` — NEVER stored, always derived
  - Property `balance`: `self.allocated_days - self.used_days`
  - __str__: `f"{self.number} · {self.employee} · {self.leave_type} · {self.year}"`
  - Drivers: BambooHR, Zoho People, Gusto track per-employee balance per year; "real-time balance" = derived calculation pattern from spine design principle

- [ ] **`LeaveRequest`** [LR-] — apply/approve/reject workflow
  - Inherits `TenantNumbered`; `NUMBER_PREFIX = "LR"`
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"leave_requests"`
  - `leave_type` FK→`"hrm.LeaveType"` CASCADE related_name=`"leave_requests"`
  - `start_date` DateField
  - `end_date` DateField
  - `days` DecimalField max_digits=5 decimal_places=2 default=0 (computed in save() as (end_date - start_date).days + 1, excluding PublicHolidays; driver: automatic day calculation — all 10 products)
  - `reason` TextField blank
  - `STATUS_CHOICES = [("draft","Draft"),("pending","Pending"),("approved","Approved"),("rejected","Rejected"),("cancelled","Cancelled")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="draft"
  - `approver` FK→settings.AUTH_USER_MODEL SET_NULL null blank related_name=`"hrm_approvals"` (manager who approves)
  - `approved_at` DateTimeField null blank (system-set on approval)
  - `rejected_reason` TextField blank (manager's rejection note)
  - `cancelled_reason` TextField blank
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - save() override: auto-compute `days` from start_date/end_date when both set and days==0; cross-check that end_date >= start_date (raise ValidationError otherwise)
  - Meta: ordering=["-start_date"]; unique_together=("tenant","number")
  - Indexes: (tenant, employee, status), (tenant, status), (tenant, leave_type, start_date)
  - __str__: `f"{self.number} · {self.employee} · {self.leave_type} · {self.start_date}"`
  - Drivers: table-stakes in all 10 products; draft→pending→approved/rejected workflow matches BambooHR/Zoho People/ADP patterns; cancelled_reason matches Rippling/Workday

- [ ] **`PublicHoliday`** — tenant-scoped holiday calendar (no auto-number; reference data)
  - `tenant` FK→`"core.Tenant"` CASCADE related_name=`"hrm_public_holidays"` db_index=True
  - `date` DateField
  - `name` CharField max_length=255
  - `is_optional` BooleanField default=False (driver: floating/optional holidays — Zoho People, Frappe HRMS, SAP SuccessFactors)
  - `created_at` DateTimeField auto_now_add=True
  - Meta: ordering=["date"]; unique_together=("tenant","date","name")
  - Indexes: (tenant, date)
  - __str__: `f"{self.date} — {self.name}"`
  - Drivers: every product integrates holiday calendar into leave calculations; holiday list used by LeaveRequest.save() to exclude holidays from `days` count

- [ ] **`Shift`** — shift definition (no auto-number; few dozen rows per tenant)
  - `tenant` FK→`"core.Tenant"` CASCADE related_name=`"hrm_shifts"` db_index=True
  - `name` CharField max_length=100 (e.g. "Morning Shift", "Night Shift")
  - `start_time` TimeField (e.g. 09:00)
  - `end_time` TimeField (e.g. 18:00)
  - `grace_minutes` PositiveSmallIntegerField default=15 (late-arrival grace period; driver: Zoho People/Frappe HRMS grace tolerance setting)
  - `is_default` BooleanField default=False (driver: default shift for new employees — UKG Pro, ADP)
  - `is_active` BooleanField default=True
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - Meta: ordering=["name"]; unique_together=("tenant","name")
  - Indexes: (tenant, is_active)
  - __str__: `f"{self.name} ({self.start_time}–{self.end_time})"`
  - Drivers: Zoho People/ADP/UKG Pro/Frappe HRMS/SAP SuccessFactors — shift management is table-stakes for attendance accuracy

- [ ] **`ShiftAssignment`** — assigns a Shift to an EmployeeProfile with effective dates
  - `tenant` FK→`"core.Tenant"` CASCADE related_name=`"hrm_shift_assignments"` db_index=True
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"shift_assignments"`
  - `shift` FK→`"hrm.Shift"` CASCADE related_name=`"assignments"`
  - `effective_from` DateField
  - `effective_to` DateField null blank (null = currently active)
  - `created_at` DateTimeField auto_now_add=True
  - Meta: ordering=["-effective_from"]; unique_together=("tenant","employee","effective_from")
  - Indexes: (tenant, employee, effective_from), (tenant, shift)
  - __str__: `f"{self.employee} → {self.shift} from {self.effective_from}"`
  - Drivers: shift rotation tracking seen in Zoho People, Frappe HRMS, UKG Pro

- [ ] **`AttendanceRecord`** [ATT-] — daily attendance entry per employee
  - Inherits `TenantNumbered`; `NUMBER_PREFIX = "ATT"`
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"attendance_records"`
  - `date` DateField
  - `check_in` TimeField null blank (driver: web/mobile/biometric punch-in — all 10 products)
  - `check_out` TimeField null blank
  - `hours_worked` DecimalField max_digits=5 decimal_places=2 default=0 (computed in save() from check_in/check_out; NEVER stored from form — always recalculated; driver: automatic hours derivation — ADP/UKG Pro/Zoho People)
  - `shift` FK→`"hrm.Shift"` SET_NULL null blank related_name=`"attendance_records"` (the expected shift for that day)
  - `STATUS_CHOICES = [("present","Present"),("absent","Absent"),("half_day","Half Day"),("on_leave","On Leave"),("holiday","Holiday"),("regularized","Regularized")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="present"
  - `SOURCE_CHOICES = [("web","Web"),("mobile","Mobile App"),("biometric","Biometric"),("manual","Manual Entry")]`
  - `source` CharField max_length=20 choices=SOURCE_CHOICES default="web"
  - `notes` TextField blank (used for regularization notes)
  - `created_at` DateTimeField auto_now_add=True; `updated_at` DateTimeField auto_now=True
  - save() override: when check_in and check_out both set, compute hours_worked = (datetime.combine(date.today(), check_out) - datetime.combine(date.today(), check_in)).seconds / 3600; handle overnight shifts (check_out < check_in → add 24h); round to 2 decimal places
  - Meta: ordering=["-date"]; unique_together=("tenant","number"); also unique_together=("tenant","employee","date") to prevent duplicate records per day
  - Indexes: (tenant, employee, date), (tenant, date, status), (tenant, status)
  - __str__: `f"{self.number} · {self.employee} · {self.date} · {self.get_status_display()}"`
  - Drivers: table-stakes in all 10 products; source tracking = ADP/UKG Pro/Zoho People/Rippling/Paycom; status enum = Frappe HRMS pattern

---

## Backend (`apps/hrm/`)

### App bootstrap
- [ ] `apps/hrm/__init__.py` — empty
- [ ] `apps/hrm/apps.py` — `AppConfig`, name=`"apps.hrm"`, verbose_name=`"Human Resource Management"`

### Models (`apps/hrm/models.py`)
- [ ] Define local `TenantOwned` + `TenantNumbered` abstract bases (mirror accounting pattern — peer apps do not import each other; local copy keeps hrm self-contained)
- [ ] `Designation` — fields as specified above; validators: min_salary <= max_salary in clean()
- [ ] `EmployeeProfile` [EMP-] — fields as specified; `save()` sets `number` via retry guard; property `department` returns `self.employment.org_unit` if employment exists (convenience accessor); property `manager` returns `self.employment.manager` if set
- [ ] `LeaveType` — fields as specified; clean(): accrual_days > 0 required when accrual_rule != "none"
- [ ] `LeaveAllocation` [LA-] — fields + properties `used_days` and `balance`; unique_together enforced via model-level constraint (not just form)
- [ ] `LeaveRequest` [LR-] — fields + save() auto-computes `days`; clean() validates end_date >= start_date
- [ ] `PublicHoliday` — fields as specified
- [ ] `Shift` — fields; clean(): end_time may be less than start_time (overnight shift is valid)
- [ ] `ShiftAssignment` — fields; clean(): effective_to must be >= effective_from if set
- [ ] `AttendanceRecord` [ATT-] — fields + save() computes `hours_worked`; unique_together on (tenant, employee, date) enforced

### Forms (`apps/hrm/forms.py`)
Exclude from all forms: `tenant`, `number` (auto), system-computed fields (`hours_worked`, `days`, `approved_at`, `confirmed_on` system-set fields). Use `__init__` to scope FK querysets to `request.tenant`.

- [ ] `DesignationForm` — fields: `name`, `grade`, `department`, `min_salary`, `max_salary`, `is_active`; `__init__` scopes `department` queryset to tenant OrgUnits with kind="department" OR all OrgUnits (to handle mixed kind data)
- [ ] `EmployeeProfileForm` — fields: `party`, `employment`, `designation`, `employee_type`, `gender`, `date_of_birth`, `blood_group`, `nationality`, `personal_email`, `mobile`, `bank_name`, `bank_account`, `bank_routing`, `probation_end_date`, `emergency_contact_name`, `emergency_contact_phone`, `emergency_contact_relation`, `photo`, `notes`; `__init__` scopes `party` to tenant Parties with kind="person", `employment` to tenant Employments, `designation` to tenant Designations
- [ ] `LeaveTypeForm` — fields: `name`, `code`, `is_paid`, `accrual_rule`, `accrual_days`, `max_balance`, `max_carry_forward`, `encashable`, `is_active`
- [ ] `LeaveAllocationForm` — fields: `employee`, `leave_type`, `year`, `allocated_days`, `note`, `status`; `__init__` scopes `employee` and `leave_type` to tenant
- [ ] `LeaveRequestForm` — fields: `employee`, `leave_type`, `start_date`, `end_date`, `reason`, `status`, `approver`; exclude: `days` (computed), `approved_at`, `rejected_reason`, `cancelled_reason`; `__init__` scopes `employee`, `leave_type`, `approver` to tenant
- [ ] `LeaveApprovalForm` — minimal form for approve/reject: fields `rejected_reason` (for reject action), `cancelled_reason` (for cancel action); used in custom approve/reject views
- [ ] `PublicHolidayForm` — fields: `date`, `name`, `is_optional`
- [ ] `ShiftForm` — fields: `name`, `start_time`, `end_time`, `grace_minutes`, `is_default`, `is_active`
- [ ] `ShiftAssignmentForm` — fields: `employee`, `shift`, `effective_from`, `effective_to`; `__init__` scopes `employee` and `shift` to tenant
- [ ] `AttendanceRecordForm` — fields: `employee`, `date`, `check_in`, `check_out`, `shift`, `status`, `source`, `notes`; exclude: `hours_worked` (computed); `__init__` scopes `employee` and `shift` to tenant

### Views (`apps/hrm/views.py`)
All views: `@login_required`, `tenant=request.tenant` filter everywhere, full CRUD via `crud_list`/`crud_create`/`crud_edit`/`crud_delete` helpers + `write_audit_log`. Mirror the `crm` view shape exactly.

**Designations (3.2):**
- [ ] `designation_list` — `crud_list(Designation.objects.filter(tenant=request.tenant).select_related("department"), "hrm/designation_list.html", search_fields=["name","grade","department__name"], filters=[("is_active","is_active",False)], extra_context={"departments": OrgUnit.objects.filter(tenant=request.tenant)})` — filter `is_active` maps `"true"/"false"` to bool
- [ ] `designation_create` — `crud_create(DesignationForm, "hrm/designation_form.html", "hrm:designation_list")`
- [ ] `designation_detail` — `get_object_or_404(Designation, pk=pk, tenant=request.tenant)` + context with `employees` count
- [ ] `designation_edit` — `crud_edit(Designation, pk, DesignationForm, "hrm/designation_form.html", "hrm:designation_list")`
- [ ] `designation_delete` — POST-only, `crud_delete(Designation, pk, "hrm:designation_list")`

**Employee Profiles (3.1):**
- [ ] `employee_list` — filters: employee_type, designation (int FK), status from employment (via employment__status); search: party__name, number, personal_email, mobile; select_related: party, employment, designation; extra_context: employee_type_choices, designations queryset, status_choices from Employment
- [ ] `employee_create` — `crud_create(EmployeeProfileForm, "hrm/employee_form.html", "hrm:employee_list")`; write_audit_log on success
- [ ] `employee_detail` — full profile; related leave_allocations (current year), recent attendance (last 10 records), shift assignment (current active), leave balance summary across all LeaveTypes
- [ ] `employee_edit` — `crud_edit(EmployeeProfile, pk, EmployeeProfileForm, "hrm/employee_form.html", "hrm:employee_list")`
- [ ] `employee_delete` — POST-only; guard: cannot delete if Employment.status == "active" (raise messages.error and redirect); write_audit_log

**Leave Types (3.10):**
- [ ] `leavetype_list` — filters: is_active, is_paid; search: name, code; extra_context: accrual_choices
- [ ] `leavetype_create` — `crud_create(LeaveTypeForm, "hrm/leavetype_form.html", "hrm:leavetype_list")`
- [ ] `leavetype_detail` — show all fields; allocations count for current year
- [ ] `leavetype_edit` — `crud_edit(LeaveType, pk, LeaveTypeForm, "hrm/leavetype_form.html", "hrm:leavetype_list")`
- [ ] `leavetype_delete` — POST-only; guard: cannot delete if active allocations or requests exist

**Leave Allocations (3.10):**
- [ ] `leaveallocation_list` — filters: status, year (integer input), employee (int FK), leave_type (int FK); search: number, employee__party__name, leave_type__name; select_related: employee__party, leave_type; extra_context: status_choices, employees, leave_types, current year default; annotate with `used_days` subquery
- [ ] `leaveallocation_create` — `crud_create(LeaveAllocationForm, ...)`; guard: check unique_together before create (show error if duplicate employee+leave_type+year)
- [ ] `leaveallocation_detail` — show allocation fields + derived balance + used_days computed from approved LeaveRequests
- [ ] `leaveallocation_edit` — `crud_edit(...)`
- [ ] `leaveallocation_delete` — POST-only

**Leave Requests (3.10):**
- [ ] `leaverequest_list` — filters: status, employee (int FK), leave_type (int FK); search: number, employee__party__name, reason; select_related: employee__party, leave_type, approver; extra_context: status_choices, employees, leave_types
- [ ] `leaverequest_create` — `crud_create(LeaveRequestForm, ...)`; on success write_audit_log; days computed in model.save()
- [ ] `leaverequest_detail` — show all fields; balance remaining for that leave_type+year on this employee; approve/reject/cancel buttons (conditional on status)
- [ ] `leaverequest_edit` — only editable when status in ["draft","pending"]; `crud_edit(...)`
- [ ] `leaverequest_delete` — POST-only; guard: cannot delete if status in ["approved","rejected"]
- [ ] `leaverequest_submit` (custom POST, `@require_POST`, `@login_required`) — sets status="pending", write_audit_log, redirect to detail
- [ ] `leaverequest_approve` (custom POST, `@require_POST`, `@login_required`) — sets status="approved", approved_at=now(), write_audit_log; update AttendanceRecord status="on_leave" for the date range; redirect to detail
- [ ] `leaverequest_reject` (custom POST, `@require_POST`, `@login_required`) — sets status="rejected" + rejected_reason from POST; write_audit_log; redirect to detail
- [ ] `leaverequest_cancel` (custom POST, `@require_POST`, `@login_required`) — sets status="cancelled" + cancelled_reason from POST; write_audit_log; redirect to detail

**Public Holidays (3.10 / 3.12):**
- [ ] `publicholiday_list` — filters: is_optional, year (derived from date__year); search: name; ordering: date; extra_context: year_choices (distinct years from existing holidays + current + next year)
- [ ] `publicholiday_create` — `crud_create(PublicHolidayForm, ...)`
- [ ] `publicholiday_detail` — show date, name, is_optional
- [ ] `publicholiday_edit` — `crud_edit(...)`
- [ ] `publicholiday_delete` — POST-only

**Shifts (3.9):**
- [ ] `shift_list` — filters: is_active; search: name; extra_context: none needed beyond list
- [ ] `shift_create` — `crud_create(ShiftForm, ...)`
- [ ] `shift_detail` — show shift fields; active assignments count; employees currently on this shift
- [ ] `shift_edit` — `crud_edit(...)`
- [ ] `shift_delete` — POST-only; guard: cannot delete if active ShiftAssignments reference this shift

**Shift Assignments (3.9):**
- [ ] `shiftassignment_list` — filters: shift (int FK), employee (int FK); search: employee__party__name, shift__name; select_related: employee__party, shift; extra_context: shifts, employees
- [ ] `shiftassignment_create` — `crud_create(ShiftAssignmentForm, ...)`
- [ ] `shiftassignment_detail` — show employee, shift, effective dates
- [ ] `shiftassignment_edit` — `crud_edit(...)`
- [ ] `shiftassignment_delete` — POST-only

**Attendance Records (3.9):**
- [ ] `attendancerecord_list` — filters: status, source, employee (int FK), date range (date_from/date_to GET params); search: number, employee__party__name, notes; select_related: employee__party, shift; extra_context: status_choices, source_choices, employees; pagination 30 per page (attendance has many rows)
- [ ] `attendancerecord_create` — `crud_create(AttendanceRecordForm, ...)`; guard: check unique (employee, date) before create
- [ ] `attendancerecord_detail` — show full record; hours_worked derived display; shift link; late-arrival detection (check_in > shift.start_time + grace_minutes → show "Late" badge)
- [ ] `attendancerecord_edit` — `crud_edit(...)`; hours_worked re-derived in model.save()
- [ ] `attendancerecord_delete` — POST-only

**HRM Overview / Dashboard (3.1):**
- [ ] `hrm_overview` — aggregate stats: total employees, new this month, on leave today (approved LeaveRequest covering today), present today (AttendanceRecord.date=today, status=present), absent today; recent leave requests (pending); upcoming holidays (next 5 from PublicHoliday); render `hrm/hrm_overview.html`

### URLs (`apps/hrm/urls.py`)
- [ ] `app_name = "hrm"` — must be set
- [ ] Overview: `""` → `hrm_overview` name=`"hrm_overview"`
- [ ] Designations: `designations/` → `designation_list`; `designations/add/` → `designation_create`; `designations/<int:pk>/` → `designation_detail`; `designations/<int:pk>/edit/` → `designation_edit`; `designations/<int:pk>/delete/` → `designation_delete`
- [ ] Employees: `employees/` → `employee_list`; `employees/add/` → `employee_create`; `employees/<int:pk>/` → `employee_detail`; `employees/<int:pk>/edit/` → `employee_edit`; `employees/<int:pk>/delete/` → `employee_delete`
- [ ] Leave Types: `leave-types/` → `leavetype_list`; `leave-types/add/` → `leavetype_create`; `leave-types/<int:pk>/` → `leavetype_detail`; `leave-types/<int:pk>/edit/` → `leavetype_edit`; `leave-types/<int:pk>/delete/` → `leavetype_delete`
- [ ] Leave Allocations: `leave-allocations/` → `leaveallocation_list`; `leave-allocations/add/` → `leaveallocation_create`; `leave-allocations/<int:pk>/` → `leaveallocation_detail`; `leave-allocations/<int:pk>/edit/` → `leaveallocation_edit`; `leave-allocations/<int:pk>/delete/` → `leaveallocation_delete`
- [ ] Leave Requests: `leave-requests/` → `leaverequest_list`; `leave-requests/add/` → `leaverequest_create`; `leave-requests/<int:pk>/` → `leaverequest_detail`; `leave-requests/<int:pk>/edit/` → `leaverequest_edit`; `leave-requests/<int:pk>/delete/` → `leaverequest_delete`; `leave-requests/<int:pk>/submit/` → `leaverequest_submit`; `leave-requests/<int:pk>/approve/` → `leaverequest_approve`; `leave-requests/<int:pk>/reject/` → `leaverequest_reject`; `leave-requests/<int:pk>/cancel/` → `leaverequest_cancel`
- [ ] Public Holidays: `holidays/` → `publicholiday_list`; `holidays/add/` → `publicholiday_create`; `holidays/<int:pk>/` → `publicholiday_detail`; `holidays/<int:pk>/edit/` → `publicholiday_edit`; `holidays/<int:pk>/delete/` → `publicholiday_delete`
- [ ] Shifts: `shifts/` → `shift_list`; `shifts/add/` → `shift_create`; `shifts/<int:pk>/` → `shift_detail`; `shifts/<int:pk>/edit/` → `shift_edit`; `shifts/<int:pk>/delete/` → `shift_delete`
- [ ] Shift Assignments: `shift-assignments/` → `shiftassignment_list`; `shift-assignments/add/` → `shiftassignment_create`; `shift-assignments/<int:pk>/` → `shiftassignment_detail`; `shift-assignments/<int:pk>/edit/` → `shiftassignment_edit`; `shift-assignments/<int:pk>/delete/` → `shiftassignment_delete`
- [ ] Attendance: `attendance/` → `attendancerecord_list`; `attendance/add/` → `attendancerecord_create`; `attendance/<int:pk>/` → `attendancerecord_detail`; `attendance/<int:pk>/edit/` → `attendancerecord_edit`; `attendance/<int:pk>/delete/` → `attendancerecord_delete`

### Admin (`apps/hrm/admin.py`)
- [ ] `DesignationAdmin` — list_display: `name, grade, department, min_salary, max_salary, is_active, tenant`; list_filter: `is_active, tenant`; search_fields: `name, grade`; readonly_fields: `created_at, updated_at`
- [ ] `EmployeeProfileAdmin` — list_display: `number, party, employee_type, designation, gender, created_at, tenant`; list_filter: `employee_type, tenant`; search_fields: `number, party__name, personal_email, mobile`; readonly_fields: `number, created_at, updated_at`; raw_id_fields: `party, employment, designation`
- [ ] `LeaveTypeAdmin` — list_display: `name, code, is_paid, accrual_rule, accrual_days, encashable, is_active, tenant`; list_filter: `is_active, is_paid, accrual_rule, tenant`; search_fields: `name, code`; readonly_fields: `created_at, updated_at`
- [ ] `LeaveAllocationAdmin` — list_display: `number, employee, leave_type, year, allocated_days, status, tenant`; list_filter: `status, year, tenant`; search_fields: `number, employee__party__name`; readonly_fields: `number, created_at, updated_at`; raw_id_fields: `employee, leave_type`
- [ ] `LeaveRequestAdmin` — list_display: `number, employee, leave_type, start_date, end_date, days, status, approver, tenant`; list_filter: `status, tenant`; search_fields: `number, employee__party__name, reason`; readonly_fields: `number, days, approved_at, created_at, updated_at`; raw_id_fields: `employee, leave_type, approver`
- [ ] `PublicHolidayAdmin` — list_display: `date, name, is_optional, tenant`; list_filter: `is_optional, tenant`; search_fields: `name`; ordering: `date`; readonly_fields: `created_at`
- [ ] `ShiftAdmin` — list_display: `name, start_time, end_time, grace_minutes, is_default, is_active, tenant`; list_filter: `is_active, is_default, tenant`; search_fields: `name`; readonly_fields: `created_at, updated_at`
- [ ] `ShiftAssignmentAdmin` — list_display: `employee, shift, effective_from, effective_to, tenant`; list_filter: `tenant`; search_fields: `employee__party__name, shift__name`; readonly_fields: `created_at`; raw_id_fields: `employee, shift`
- [ ] `AttendanceRecordAdmin` — list_display: `number, employee, date, check_in, check_out, hours_worked, status, source, tenant`; list_filter: `status, source, tenant`; search_fields: `number, employee__party__name`; readonly_fields: `number, hours_worked, created_at, updated_at`; raw_id_fields: `employee, shift`

### Migrations
- [ ] `apps/hrm/migrations/__init__.py` — empty
- [ ] Run `python manage.py makemigrations hrm` → `apps/hrm/migrations/0001_initial.py`
- [ ] Verify with `python manage.py sqlmigrate hrm 0001` — confirm FK references, unique_together, indexes all render correctly
- [ ] Run `python manage.py migrate` — zero errors

### Seeder (`apps/hrm/management/commands/seed_hrm.py`)
- [ ] `apps/hrm/management/__init__.py` — empty
- [ ] `apps/hrm/management/commands/__init__.py` — empty
- [ ] `apps/hrm/management/commands/seed_hrm.py` — implement `Command` class with `handle()`

Seeder logic (idempotent — check `EmployeeProfile.objects.filter(tenant=tenant).exists()` at the top; print skip warning if data exists; support `--flush` flag to delete and re-seed):

1. **Loop over both demo tenants** (acme + globex): use `Tenant.objects.filter(slug__in=["acme","globex"])`
2. **Reuse existing core.Party rows** (kind="person") for employee profiles — do NOT create new Party rows; query `Party.objects.filter(tenant=tenant, kind="person")[:5]`; if fewer than 3 person Parties exist, print warning and skip that tenant
3. **Designations** — seed 3 per tenant: `("Software Engineer","L2")`, `("Senior Engineer","L3")`, `("Engineering Manager","M1")` — link to first OrgUnit with kind="department" (or any OrgUnit if none with kind=department); use `get_or_create(tenant=tenant, name=name)`
4. **EmployeeProfiles** — seed up to 3 per tenant; for each Party, `get_or_create` an Employment if not exists, then `get_or_create` an EmployeeProfile (check by party); assign designations round-robin; mix employee_types (full_time, part_time, contract)
5. **LeaveTypes** — seed 4 per tenant: Annual Leave (AL, is_paid=True, accrual_rule=annual, accrual_days=21, max_carry_forward=5, encashable=True), Sick Leave (SL, is_paid=True, accrual_rule=monthly, accrual_days=1.5, max_balance=18), Casual Leave (CL, is_paid=True, accrual_rule=annual, accrual_days=12), Unpaid Leave (UPL, is_paid=False, accrual_rule=none); use `get_or_create(tenant=tenant, code=code)`
6. **LeaveAllocations** — seed one allocation per employee per leave type for current year; use `get_or_create(tenant=tenant, employee=emp, leave_type=lt, year=current_year)`; status="active"
7. **LeaveRequests** — seed 2 per tenant: one "approved" (past dates, status=approved, approved_at set), one "pending" (upcoming dates); use number-check idempotency: `if LeaveRequest.objects.filter(tenant=tenant).exists(): skip_msg; continue`
8. **PublicHolidays** — seed 5 standard holidays for current year: New Year (Jan 1), Labor Day (May 1), Independence Day (Aug 14 or Jul 4), Christmas Eve (Dec 24), Christmas (Dec 25); `get_or_create(tenant=tenant, date=date, name=name)`; is_optional=False except 1 floating holiday
9. **Shifts** — seed 2 per tenant: "Morning Shift" (09:00-18:00, grace=15) and "Night Shift" (21:00-06:00, grace=30); use `get_or_create(tenant=tenant, name=name)`; Morning is_default=True
10. **ShiftAssignments** — assign Morning Shift to all employees with effective_from=date(current_year,1,1); use `get_or_create(tenant=tenant, employee=emp, effective_from=date)`
11. **AttendanceRecords** — seed 5 records per employee (last 5 working days from today); mix of statuses (present x3, absent x1, on_leave x1); use number-check idempotency on (employee, date) unique; source="manual" for seeder
12. After seeding, print:
    ```
    HRM seeded for tenant '{tenant.name}':
      Employees: {count}
      Leave Allocations: {count}
      Attendance Records: {count}
    Login as admin_acme / password (or admin_globex / password) to verify.
    WARNING: Superuser 'admin' has no tenant — data won't appear when logged in as admin.
    ```

---

## Wire-up

- [ ] `config/settings.py` — add `"apps.hrm"` to `INSTALLED_APPS` (after `apps.accounting`)
- [ ] `config/urls.py` — add `path("hrm/", include("apps.hrm.urls", namespace="hrm"))`

### `apps/core/navigation.py` — LIVE_LINKS additions
Add the following HRM entries to the `LIVE_LINKS` dict. Use the **exact** NavERP.md `**Feature**` bullet text as keys so the sidebar lights up the built bullets:

```python
# ========================= Module 3 — Human Resource Management (HRM)
# 3.1 Employee Management
"3.1": {
    "Employee Directory": "hrm:employee_list",       # bullet
    "Employee Profile": "hrm:employee_list",         # bullet (detail view linked from list)
    "Employment Details": "hrm:employee_list",       # bullet (employment FKed from profile)
},
# 3.2 Organizational Structure
"3.2": {
    "Designation/Job Titles": "hrm:designation_list",  # bullet
    "Department Management": "core:orgunit_list",       # bullet (OrgUnit reuse)
},
# 3.9 Attendance Management
"3.9": {
    "Check-in/Check-out": "hrm:attendancerecord_list",  # bullet
    "Attendance Calendar": "hrm:attendancerecord_list",  # bullet
    "Shift Management": "hrm:shift_list",               # bullet
    "Shift Assignments": "hrm:shiftassignment_list",    # extra
},
# 3.10 Leave Management
"3.10": {
    "Leave Types": "hrm:leavetype_list",             # bullet
    "Leave Balance": "hrm:leaveallocation_list",     # bullet
    "Leave Application": "hrm:leaverequest_list",    # bullet
    "Leave Calendar": "hrm:leaverequest_list",       # bullet (calendar view from list)
},
# 3.12 Holiday Management
"3.12": {
    "Holiday Calendar": "hrm:publicholiday_list",    # bullet
},
```

- [ ] Also add `"HRM Overview": "hrm:hrm_overview"` as extra entry under `"3.1"` (non-bullet; the module landing page)

---

## Templates (`templates/hrm/`)

All templates mirror `crm/lead_list.html` pattern: filter-bar with `request.GET` pre-fill, Actions column (eye/pencil/bin icons), `|stringformat:"d"` for FK pk filter comparison, pagination, empty-state, breadcrumb. Use the existing design system (Tailwind + Lucide icons, `base.html` extends).

### HRM Overview
- [ ] `hrm/hrm_overview.html` — module landing page; stat cards (total employees, new this month, on leave today, present today, absent today); table of pending leave requests (LR number, employee, leave type, dates, days); upcoming holidays (next 5); quick-action buttons to employee_create, leaverequest_create, attendancerecord_create

### Designations (3.2)
- [ ] `hrm/designation_list.html` — table: name, grade, department, salary band (min–max), is_active badge, employee count; filter bar: is_active dropdown; search box; Actions column: view/edit/delete; pagination; empty-state
- [ ] `hrm/designation_detail.html` — all fields; salary band display; employee count (link to employee_list filtered by this designation); sidebar: Edit / Delete / Back to List
- [ ] `hrm/designation_form.html` — create/edit form; is_edit context toggle for page title; department field with OrgUnit dropdown

### Employee Profiles (3.1)
- [ ] `hrm/employee_list.html` — table: EMP number, name (party__name), employee_type badge, designation, department (via employment.org_unit), status (via employment.status), joined date (via employment.hired_on); filter bar: employee_type dropdown, designation dropdown (int FK comparison with `|stringformat:"d"`), employment status dropdown; search box; Actions column: view/edit/delete; pagination; empty-state
- [ ] `hrm/employee_detail.html` — two-column layout; left: personal info (gender, DOB, blood group, nationality, personal email, mobile, emergency contact); right: employment info (EMP number, employee_type, designation, department, manager, hired_on, probation_end_date, confirmed_on); bank details section (bank_name, account masked); photo display if set; leave balance table (all LeaveTypes for current year: type, allocated, used, balance); recent attendance (last 10 records in a table); current shift assignment; sidebar: Edit / Delete / Back to List
- [ ] `hrm/employee_form.html` — create/edit form; group fields into fieldsets: "Personal Information" (party, gender, DOB, blood group, nationality, personal_email, mobile), "Employment Details" (employment, designation, employee_type, probation_end_date), "Bank Details" (bank_name, bank_account, bank_routing), "Emergency Contact" (name, phone, relation), "Other" (photo, notes); photo field shows current image on edit

### Leave Types (3.10)
- [ ] `hrm/leavetype_list.html` — table: name, code, is_paid badge, accrual_rule badge, accrual_days, max_carry_forward, encashable badge, is_active badge; filter bar: is_active + is_paid dropdowns; search box; Actions column: view/edit/delete; empty-state
- [ ] `hrm/leavetype_detail.html` — all fields with descriptive labels; active allocations count (link to leaveallocation_list filtered by this type); sidebar: Edit / Delete / Back
- [ ] `hrm/leavetype_form.html` — create/edit form; accrual_days field shown/hidden based on accrual_rule via simple JS; max_balance note: "0 = unlimited"

### Leave Allocations (3.10)
- [ ] `hrm/leaveallocation_list.html` — table: LA number, employee name, leave type, year, allocated_days, used_days (derived annotation), balance, status badge; filter bar: status dropdown, year integer filter (GET `year`), employee dropdown (int FK), leave_type dropdown (int FK); search box; Actions column: view/edit/delete; empty-state
- [ ] `hrm/leaveallocation_detail.html` — all fields; used_days derived (count of approved requests for employee+leave_type+year); balance = allocated - used; link to related leave requests; sidebar: Edit / Delete / Back
- [ ] `hrm/leaveallocation_form.html` — create/edit form; year field defaults to current year

### Leave Requests (3.10)
- [ ] `hrm/leaverequest_list.html` — table: LR number, employee, leave type, start_date, end_date, days, status badge with colour coding (pending=yellow, approved=green, rejected=red, cancelled=grey), approver; filter bar: status, employee (int FK), leave_type (int FK) dropdowns; search box; Actions column: view/edit/delete + Submit button (when status=draft); empty-state
- [ ] `hrm/leaverequest_detail.html` — all fields; balance remaining for this leave_type+year; status workflow history note; conditional action buttons in sidebar: "Submit" (when draft), "Approve" (when pending), "Reject" (when pending, with textarea for rejected_reason), "Cancel" (when draft/pending, with textarea for cancelled_reason); sidebar: Edit (when draft/pending) / Delete (when draft) / Back; all action buttons POST with `{% csrf_token %}`
- [ ] `hrm/leaverequest_form.html` — create/edit form; end_date must be >= start_date (HTML5 min attribute); days shown as read-only computed value (JS: update on date change); reason textarea

### Public Holidays (3.10 / 3.12)
- [ ] `hrm/publicholiday_list.html` — table: date, name, is_optional badge, day-of-week; filter bar: is_optional dropdown, year filter (GET `year`, default current year); search box; Actions column: view/edit/delete; holiday count for selected year in page header; empty-state
- [ ] `hrm/publicholiday_detail.html` — date, name, is_optional, day-of-week; sidebar: Edit / Delete / Back
- [ ] `hrm/publicholiday_form.html` — create/edit form; date picker; is_optional checkbox with help text "Optional holidays can be chosen by employee"

### Shifts (3.9)
- [ ] `hrm/shift_list.html` — table: name, start_time, end_time, grace_minutes, is_default badge, is_active badge, active_assignments count; filter bar: is_active dropdown; search box; Actions column: view/edit/delete; empty-state
- [ ] `hrm/shift_detail.html` — all fields; active ShiftAssignment count and list (employee names, effective_from); sidebar: Edit / Delete / Back
- [ ] `hrm/shift_form.html` — create/edit form; time pickers for start_time/end_time; is_default checkbox with note "Only one default shift is enforced at the view layer"

### Shift Assignments (3.9)
- [ ] `hrm/shiftassignment_list.html` — table: employee name, shift name, effective_from, effective_to (or "Ongoing" if null); filter bar: shift dropdown (int FK), employee dropdown (int FK); search box; Actions column: view/edit/delete; empty-state
- [ ] `hrm/shiftassignment_detail.html` — employee, shift, dates; sidebar: Edit / Delete / Back
- [ ] `hrm/shiftassignment_form.html` — create/edit form; effective_to nullable (blank = ongoing); employee + shift dropdowns scoped to tenant

### Attendance Records (3.9)
- [ ] `hrm/attendancerecord_list.html` — table: ATT number, employee, date, check_in, check_out, hours_worked, status badge (colour-coded: present=green, absent=red, half_day=yellow, on_leave=blue, holiday=grey, regularized=purple), source badge; filter bar: status, source, employee (int FK) dropdowns + date_from/date_to date inputs; search box; pagination 30 per page; Actions column: view/edit/delete; empty-state
- [ ] `hrm/attendancerecord_detail.html` — all fields; late-arrival indicator (check_in vs shift.start_time + grace_minutes); hours_worked display; shift link; sidebar: Edit / Delete / Back
- [ ] `hrm/attendancerecord_form.html` — create/edit form; employee + shift dropdowns scoped to tenant; check_in/check_out time pickers; hours_worked shown as read-only (auto-computed on save); date picker

---

## Verify

All commands run with `C:\xampp\htdocs\NavERP\venv\Scripts\python.exe`:

- [ ] `venv\Scripts\python.exe manage.py makemigrations hrm` — confirm single `0001_initial.py` created with all 9 models (Designation, EmployeeProfile, LeaveType, LeaveAllocation, LeaveRequest, PublicHoliday, Shift, ShiftAssignment, AttendanceRecord)
- [ ] `venv\Scripts\python.exe manage.py sqlmigrate hrm 0001` — review SQL; confirm FK references to core.Tenant, core.Party, core.Employment, core.OrgUnit, auth.User are correct; unique_together constraints render; indexes for all indexed fields
- [ ] `venv\Scripts\python.exe manage.py migrate` — zero errors on `nav_erp`
- [ ] `venv\Scripts\python.exe manage.py seed_hrm` — first run: seeds designations, employees, leave types, allocations, requests, holidays, shifts, assignments, attendance; prints login + warning
- [ ] `venv\Scripts\python.exe manage.py seed_hrm` (second run) — must print "Data already exists — skipping" for every model block; zero duplicate rows (idempotency proof)
- [ ] `venv\Scripts\python.exe manage.py check` — zero errors, zero warnings
- [ ] Write `temp/hrm_smoke.py` — Django test-client sweep:
  - Authenticate as `admin_acme` (tenant admin)
  - Hit all `hrm:*` list/detail/create/edit/delete URLs → all return 200 or 302
  - Check no `{#` or `{% comment` template leaks in any response body
  - Cross-tenant IDOR: log in as `admin_globex`, request detail URL for an acme EmployeeProfile pk → must return 404
  - Cross-tenant IDOR for LeaveRequest, AttendanceRecord → 404
  - POST `leaverequest_submit` → status transitions to "pending"
  - POST `leaverequest_approve` → status transitions to "approved"
  - POST `leaverequest_reject` with rejected_reason → status transitions to "rejected"
  - POST `attendancerecord_delete` → record gone, redirect 302
  - `seed_hrm` ×2 idempotency confirmed (record count same after second run)
- [ ] Run `temp/hrm_smoke.py` — all checks green
- [ ] Sidebar check: sub-modules 3.1, 3.2, 3.9, 3.10, 3.12 all show as **Live** (non-grey) with correct href in the rendered sidebar navigation

---

## Close-out

- [ ] Run **`code-reviewer` agent** — apply findings; commit each changed file one at a time (PowerShell-safe)
- [ ] Run **`explorer` agent** — apply findings (check for N+1 on employee_detail balance/leave queries, attendance record date-range filter, used_days subquery); commit
- [ ] Run **`frontend-reviewer` agent** — apply findings (filter-bar `|stringformat:"d"` FK comparisons, badge choice values match model CHOICES, photo display on detail, leave balance table, late-arrival badge logic); commit
- [ ] Run **`performance-reviewer` agent** — apply findings (employee_detail: batch the leave balance table into one query with annotate+values; attendance list: add composite index on (tenant, employee, date); used_days derived via subquery annotation on leaveallocation_list); commit
- [ ] Run **`qa-smoke-tester` agent** — apply findings (test every status transition for LeaveRequest, test employee_delete guard when active, test AttendanceRecord duplicate-date guard, test EmployeeProfile unique_together on (tenant, number)); commit
- [ ] Run **`security-reviewer` agent** — apply findings (flag: `bank_account` stored as plaintext — WARNING comment + recommendation to encrypt or mask on display; employee_delete guard bypass; leaverequest approve/reject must check `request.user` has manager role; photo upload MIME validation); commit
- [ ] Run **`test-writer` agent** — write pytest tests for: all 9 models CRUD, status-machine transitions (LeaveRequest submit/approve/reject/cancel), AttendanceRecord.save() hours_worked computation, LeaveAllocation.used_days/balance properties, EmployeeProfile.department/manager property accessors, seeder idempotency, IDOR 404 on all detail/edit/delete views, employee_delete active-employment guard; commit
- [ ] Create **`.claude/skills/hrm/SKILL.md`** — document as-built module: 9 models, all URL names (app_name="hrm"), templates, seeder, LIVE_LINKS entries, conventions (EmployeeProfile as anchor, derived fields, accounting.PayrollRun coordination deferred), common tasks (add a leave type, add an employee, extend attendance); commit
- [ ] Update **`README.md`** — add Module 3 HRM to module status table (sub-modules 3.1/3.2/3.9/3.10/3.12 Live), update seeder section with `seed_hrm` instructions; commit

### Per-file commit list (PowerShell-safe, one file per commit)
```
git add 'apps\hrm\__init__.py'; git commit -m 'feat(hrm): new app bootstrap __init__.py'
git add 'apps\hrm\apps.py'; git commit -m 'feat(hrm): AppConfig for hrm module'
git add 'apps\hrm\models.py'; git commit -m 'feat(hrm): 9 models — Designation, EmployeeProfile, LeaveType, LeaveAllocation, LeaveRequest, PublicHoliday, Shift, ShiftAssignment, AttendanceRecord with TenantNumbered abstract base'
git add 'apps\hrm\migrations\__init__.py'; git commit -m 'feat(hrm): migrations package __init__'
git add 'apps\hrm\migrations\0001_initial.py'; git commit -m 'feat(hrm): initial migration — all 9 HRM models with FKs, unique_together, indexes'
git add 'apps\hrm\forms.py'; git commit -m 'feat(hrm): forms for all 9 models — tenant-scoped FK querysets, exclude computed fields'
git add 'apps\hrm\views.py'; git commit -m 'feat(hrm): views — full CRUD + search/filters + hrm_overview + leave workflow actions (submit/approve/reject/cancel) + attendance'
git add 'apps\hrm\urls.py'; git commit -m 'feat(hrm): URL patterns — app_name=hrm, all CRUD routes + custom workflow action URLs'
git add 'apps\hrm\admin.py'; git commit -m 'feat(hrm): admin registration for all 9 HRM models with list_display, list_filter, search_fields, readonly_fields'
git add 'apps\hrm\management\__init__.py'; git commit -m 'feat(hrm): management package __init__'
git add 'apps\hrm\management\commands\__init__.py'; git commit -m 'feat(hrm): management/commands package __init__'
git add 'apps\hrm\management\commands\seed_hrm.py'; git commit -m 'feat(hrm): idempotent seed_hrm command — designations, employees (reuse core.Party), leave types, allocations, requests, holidays, shifts, assignments, attendance'
git add 'config\settings.py'; git commit -m 'feat(hrm): add apps.hrm to INSTALLED_APPS'
git add 'config\urls.py'; git commit -m 'feat(hrm): include hrm/ URL prefix in config/urls.py'
git add 'apps\core\navigation.py'; git commit -m 'feat(core/nav): wire LIVE_LINKS 3.1/3.2/3.9/3.10/3.12 for HRM module — employee/designation/leave/attendance/holiday/shift routes'
git add 'templates\hrm\hrm_overview.html'; git commit -m 'feat(hrm): HRM overview/landing page — employee stats, pending leave requests, upcoming holidays'
git add 'templates\hrm\designation_list.html'; git commit -m 'feat(hrm): designation list template with is_active filter and employee count'
git add 'templates\hrm\designation_detail.html'; git commit -m 'feat(hrm): designation detail template with salary band and employee count'
git add 'templates\hrm\designation_form.html'; git commit -m 'feat(hrm): designation create/edit form template'
git add 'templates\hrm\employee_list.html'; git commit -m 'feat(hrm): employee list with type/designation/status filters and EMP number'
git add 'templates\hrm\employee_detail.html'; git commit -m 'feat(hrm): employee detail — personal info, employment, leave balance table, recent attendance, shift'
git add 'templates\hrm\employee_form.html'; git commit -m 'feat(hrm): employee create/edit form with fieldsets for personal/employment/bank/emergency/photo'
git add 'templates\hrm\leavetype_list.html'; git commit -m 'feat(hrm): leave type list with accrual/paid filters'
git add 'templates\hrm\leavetype_detail.html'; git commit -m 'feat(hrm): leave type detail with allocations count'
git add 'templates\hrm\leavetype_form.html'; git commit -m 'feat(hrm): leave type create/edit form'
git add 'templates\hrm\leaveallocation_list.html'; git commit -m 'feat(hrm): leave allocation list with status/year/employee/type filters and balance column'
git add 'templates\hrm\leaveallocation_detail.html'; git commit -m 'feat(hrm): leave allocation detail with derived used_days and balance'
git add 'templates\hrm\leaveallocation_form.html'; git commit -m 'feat(hrm): leave allocation create/edit form'
git add 'templates\hrm\leaverequest_list.html'; git commit -m 'feat(hrm): leave request list with status/employee/type filters and Submit button for drafts'
git add 'templates\hrm\leaverequest_detail.html'; git commit -m 'feat(hrm): leave request detail with workflow action buttons (submit/approve/reject/cancel)'
git add 'templates\hrm\leaverequest_form.html'; git commit -m 'feat(hrm): leave request create/edit form with date validation'
git add 'templates\hrm\publicholiday_list.html'; git commit -m 'feat(hrm): public holiday list with year/optional filters'
git add 'templates\hrm\publicholiday_detail.html'; git commit -m 'feat(hrm): public holiday detail template'
git add 'templates\hrm\publicholiday_form.html'; git commit -m 'feat(hrm): public holiday create/edit form'
git add 'templates\hrm\shift_list.html'; git commit -m 'feat(hrm): shift list with is_active filter and assignment count'
git add 'templates\hrm\shift_detail.html'; git commit -m 'feat(hrm): shift detail with active assignment list'
git add 'templates\hrm\shift_form.html'; git commit -m 'feat(hrm): shift create/edit form with time pickers'
git add 'templates\hrm\shiftassignment_list.html'; git commit -m 'feat(hrm): shift assignment list with shift/employee filters'
git add 'templates\hrm\shiftassignment_detail.html'; git commit -m 'feat(hrm): shift assignment detail template'
git add 'templates\hrm\shiftassignment_form.html'; git commit -m 'feat(hrm): shift assignment create/edit form'
git add 'templates\hrm\attendancerecord_list.html'; git commit -m 'feat(hrm): attendance record list with status/source/employee/date-range filters'
git add 'templates\hrm\attendancerecord_detail.html'; git commit -m 'feat(hrm): attendance record detail with late-arrival indicator'
git add 'templates\hrm\attendancerecord_form.html'; git commit -m 'feat(hrm): attendance record create/edit form with time pickers'
git add 'temp\hrm_smoke.py'; git commit -m 'test(hrm): smoke test — all hrm:* routes 200/302, no leaks, IDOR 404, leave workflow transitions, attendance delete'
git add '.claude\skills\hrm\SKILL.md'; git commit -m 'docs(skill/hrm): SKILL.md — 9 models, URL names, seeder, LIVE_LINKS, conventions, common tasks'
git add 'README.md'; git commit -m 'docs(readme): Module 3 HRM — sub-modules 3.1/3.2/3.9/3.10/3.12 Live, seed_hrm instructions'
```

---

## Later passes / deferred

- **SalaryComponent + SalaryStructure + EmployeeSalary** — pay component engine (Basic/HRA/PF/ESI/TDS); required before per-employee payslips can be computed; deferred to HRM pass 2. Do NOT duplicate `accounting.PayrollRun` when building these — the HRM `PayrollEntry` (per-employee payslip line) will FK into `accounting.PayrollRun` (period-level GL journal)
- **PayrollEntry (per-employee payslip)** — coordinates with `accounting.PayrollRun` (PRUN-#####); HRM owns the component-level breakdown; accounting owns the GL journal; deferred until SalaryStructure is built
- **JobRequisition + Candidate + InterviewRound + InterviewFeedback + OfferLetter** — full ATS/recruiting flow (sub-modules 3.5/3.6/3.7/3.8); separate pass once employee foundation is stable; can reuse `core.Party` for candidate + `hrm.Designation` for requisition job grade
- **OnboardingTask / OnboardingChecklist** — sub-module 3.3; checklist per new hire; pass 2; reuses `core.Document` (GenericFK) for attachment; `is_preboarding` flag on task
- **SeparationRequest + ExitInterview** — sub-modules 3.4; resignation/offboarding flow; pass 2; coordinates with leave encashment in PayrollEntry
- **PerformanceReview + Goal** — sub-modules 3.18/3.19; OKR/KPI goal setting + review cycle; depends on employee foundation; deferred to pass 2
- **Timesheet + TimesheetEntry** — sub-module 3.11; weekly timesheet against projects; coordinates with `accounting.Project` (PRJ-) for job costing; deferred to pass 2
- **Leave carry-forward year-end batch** — `LeaveType.max_carry_forward` is modeled; the year-end management command that rolls over balances to new LeaveAllocation rows is deferred (batch job / Celery task)
- **Leave encashment calculation** — `LeaveType.encashable` flag is modeled; the encashment computation (leave × daily_rate from salary structure) is deferred until SalaryStructure is built
- **AttendanceRegularizationRequest** — employee requests correction for missing/incorrect punches; pass 2; new table FKing to AttendanceRecord
- **Geofenced / IP-restricted check-in** — `check_in_location` JSON field on AttendanceRecord; requires mobile/GPS integration; deferred
- **Floating/Optional holiday selection** — `OptionalHolidaySelection(employee, holiday)` through-model; `PublicHoliday.is_optional` flag is already modeled; employee selection UI is deferred
- **SalaryBenchmarking** — external market salary data comparison; requires external data feed; deferred
- **BenefitPlan + EmployeeBenefit** — health/retirement benefits enrollment; US-market feature; later pass
- **TaxDeclaration + Form16** — jurisdiction-specific investment declarations + annual tax certificate; later pass
- **TrainingSession + LMS + TrainingAttendance** — training calendar + LMS content (sub-modules 3.22/3.23/3.24); full LMS is a separate pass
- **EngagementSurvey + SurveyResponse** — sub-modules 3.27/3.32; employee engagement surveys; deferred
- **Announcement model** — company-wide HR broadcasts (sub-module 3.27); deferred
- **ExpenseClaim** — employee expense submission with manager approval; sub-module 3.34; coordinates with `accounting.JournalEntry` on approval; deferred (after accounting expense GL flow confirmed)
- **HRAssetAllocation** — sub-module 3.33; links to Module 11 Asset (not yet built); deferred
- **SuccessionPlan / TalentRating (9-Box Grid)** — sub-modules 3.38/3.40; talent management; deferred
- **Predictive attrition analytics** — requires BI module + ML pipeline; deferred
- **NACHA / bank file export** — payroll bank disbursement file generation; deferred to payroll pass
- **Self-Service employee portal** — sub-module 3.25; filtered views scoped to `request.user.party`; deferred (can be added as a separate URL prefix once employee foundation is stable)
- **DRF REST API for HRM** — biometric device integration and mobile check-in rely on REST endpoints; deferred to API infrastructure pass

## Review notes — Module 3 HRM build outcome (2026-06-21)

**Built & verified.** 9 models (Designation, EmployeeProfile, LeaveType, LeaveAllocation, LeaveRequest,
PublicHoliday, Shift, ShiftAssignment, AttendanceRecord) across `apps/hrm` + 28 templates. Migrates clean to
`nav_erp`, `manage.py check` clean, `seed_hrm` idempotent (5 employees / 20 allocations / 25 attendance per tenant,
reuses core Parties). Sub-modules 3.1/3.2/3.9/3.10/3.12 Live in the sidebar.

**Module Creation Sequence — all agents run, findings applied (one commit per file, never pushed):**
- **research → todo** — competitive catalog (10 HCM products) → 9-model plan.
- **code-reviewer** — fixed C1 (LeaveRequestForm exposed `status`/`approver` → self-approval; removed both),
  C3 (cancel now reverts on_leave attendance, atomic), H3 (`probation_end` → `probation_end_date` template typo),
  M3 (designation delete guard), M5 (seed unique party names), L4 (cancel confirm). H2 (boolean filter) verified a
  **false positive** — Django coerces `"False"`→False.
- **explorer** — wired the unused `current_year` into the leave-allocation year filter default. All routes/url
  names/context vars/NavERP.md bullets verified consistent.
- **frontend-reviewer** — added a11y (img alt, label `for`/`id` on reason textareas, date-input aria-labels),
  rendered the previously-unused `recent_leaves` card, photo card header. (Inline-style→CSS refactors skipped —
  they match the existing CRM convention.)
- **performance-reviewer** — killed the `used_days`/`balance` per-row N+1 with a correlated `Subquery` annotation
  (`used_days_db`/`balance_db`) in leaveallocation_list + employee_detail (list ~40+ queries → 11); year_choices
  via `distinct date__year`; cached `used_days` on the instance; added `core.Employment (tenant, status)` index.
- **qa-smoke-tester** — 98/98 checks pass (routes 200/302, no leaks, IDOR 404, workflow transitions, privilege,
  delete guards, sidebar). No fixes needed.
- **security-reviewer** — redacted bank fields from `AuditLog.changes` (shared `core.crud`), validated attendance
  date filters (no 500 on bad input), `clean_photo` allowlist+size cap, audit-logged the attendance batch on
  approve/cancel, broadened bank WARNING. F5 (per-employee ownership on submit/cancel) deferred to the RBAC pass —
  matches the app's tenant-trust baseline.
- **test-writer** — 239 pytest tests, 99% HRM coverage, **1263 project-wide**, zero regressions.
- **skill** — `.claude/skills/hrm/SKILL.md` documents the as-built module.

**Deferred** (next HRM passes): payroll/payslip (FK into `accounting.PayrollRun`), recruiting/ATS, onboarding/
offboarding, performance/goals, timesheets, statutory/tax, attendance regularization & geofencing, leave carry-
forward/encashment batch, self-service portal + employee↔user linkage. See the "Later passes / deferred" list above.

---

# Module 3 Extension — HRM Sub-module 3.3: Employee Onboarding (hrm)  — plan from research-hrm-onboarding.md  (2026-06-25)

> **Context:** Extension pass on the EXISTING `apps/hrm` app (3.1/3.2/3.9/3.10/3.12 complete,
> 850+ tests green). No new Django app — every item below is added to the existing `apps/hrm/*`
> files. Models use the same local abstract bases `TenantOwned` / `TenantNumbered` already in
> `apps/hrm/models.py`. Every model FKs to `hrm.EmployeeProfile` (the anchor), never to
> `core.Party` directly. Welcome Kit fields live on `OnboardingProgram` — no separate table.

---

## Models (add to `apps/hrm/models.py`)

### Model 1 — `OnboardingTemplate` [ONBT-]
- [ ] **`OnboardingTemplate`** — inherits `TenantNumbered`; reusable per-role onboarding checklist
  - `NUMBER_PREFIX = "ONBT"`
  - `name` CharField max_length=255 (e.g. "Engineering New Hire", "Sales Onboarding")
  - `description` TextField blank=True
  - `designation` FK→`"hrm.Designation"` SET_NULL null=True blank=True related_name=`"onboarding_templates"` (auto-suggest this template when onboarding that job title — driver: Personio/Rippling role-based template selection)
  - `is_active` BooleanField default=True
  - Meta: ordering=["name"]; unique_together=("tenant","number"); also unique_together=("tenant","name") to prevent duplicate template names
  - Indexes: (tenant, is_active); (tenant, designation)
  - `__str__`: `f"{self.number} · {self.name}"`
  - Drivers: All 10 surveyed products (BambooHR, Workday, Rippling, HiBob, Personio, Gusto, Click Boarding, Enboarder, SAP SuccessFactors, Sapling) offer named reusable templates; the `designation` link implements role-based auto-suggestion seen in Rippling and Personio
  - Reuses: `hrm.Designation` (FK for role-based suggestion); adds HRM-owned onboarding template table

### Model 2 — `OnboardingTemplateTask` (child of template, no auto-number)
- [ ] **`OnboardingTemplateTask`** — inherits `TenantOwned`; one task definition line in a template
  - `template` FK→`"hrm.OnboardingTemplate"` CASCADE related_name=`"template_tasks"`
  - `title` CharField max_length=255 (e.g. "Set up corporate email", "Complete I-9 form")
  - `description` TextField blank=True
  - `TASK_CATEGORY_CHOICES = [("hr_admin","HR Admin"),("it_setup","IT Setup"),("manager_action","Manager Action"),("buddy_action","Buddy Action"),("new_hire_action","New Hire Action"),("document_sign","Document Sign"),("equipment_request","Equipment Request"),("training","Training"),("meet_greet","Meet & Greet"),("custom","Custom")]`
  - `task_category` CharField max_length=30 choices=TASK_CATEGORY_CHOICES default="custom" (driver: SAP SuccessFactors typed task categories; BambooHR/Gusto/Workable/HiBob custom task categories)
  - `ASSIGNEE_ROLE_CHOICES = [("hr","HR"),("it","IT"),("manager","Manager"),("buddy","Buddy"),("new_hire","New Hire")]`
  - `assignee_role` CharField max_length=20 choices=ASSIGNEE_ROLE_CHOICES default="hr" (driver: HiBob/SAP SuccessFactors/Personio/Click Boarding multi-stakeholder assignment — role rather than specific user)
  - `due_offset_days` IntegerField default=0 (negative = before start date e.g. -3 = 3 days preboarding; 0 = start date; positive = after. Driver: Gusto "Before Day 1/Day 1/After Day 1"; Workable "days before start date")
  - `PHASE_CHOICES = [("preboarding","Preboarding"),("week_1","Week 1"),("month_1","Month 1"),("month_2","Month 2"),("month_3","Month 3"),("ongoing","Ongoing")]`
  - `phase` CharField max_length=20 choices=PHASE_CHOICES default="week_1" (driver: Enboarder 30-60-90 day plans; Rippling phased checklists; SAP SuccessFactors phased onboarding)
  - `order` PositiveIntegerField default=0 (display sort order within the template/phase)
  - `is_mandatory` BooleanField default=True (driver: Workday/HiBob distinguish required vs optional tasks)
  - Meta: ordering=["template","phase","order","title"]; unique_together=("tenant","template","title") so a template cannot have duplicate task titles
  - Indexes: (tenant, template); (tenant, template, phase)
  - `__str__`: `f"{self.template} → {self.title}"`
  - Drivers: Gusto segmentation, SAP SuccessFactors task types, HiBob multi-stakeholder assignment, Enboarder 30-60-90 phasing — all these fields derive from these product features
  - Reuses: `hrm.OnboardingTemplate` (parent)

### Model 3 — `OnboardingProgram` [ONB-]
- [ ] **`OnboardingProgram`** — inherits `TenantNumbered`; one program instance per new hire
  - `NUMBER_PREFIX = "ONB"`
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"onboarding_programs"` (the person being onboarded — the HRM anchor)
  - `template` FK→`"hrm.OnboardingTemplate"` SET_NULL null=True blank=True related_name=`"programs"` (kept as a reference after tasks are generated; nullable so standalone programs without a template are allowed)
  - `start_date` DateField (the hire's actual first day — drives all due_date calculations via `due_offset_days`)
  - `STATUS_CHOICES = [("draft","Draft"),("active","Active"),("completed","Completed"),("cancelled","Cancelled")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="draft"
  - `buddy` FK→`"hrm.EmployeeProfile"` SET_NULL null=True blank=True related_name=`"buddy_for"` (peer mentor assignment — driver: HiBob/SAP SuccessFactors/Personio/Enboarder buddy assignment feature)
  - `welcome_message` TextField blank=True (personalized welcome note — driver: Workable configurable welcome message; Personio welcome email; Enboarder/Appical digital welcome experience)
  - `welcome_video_url` URLField blank=True (CEO/manager video embed URL — driver: Workable YouTube/Vimeo embed; Enboarder/Appical video welcome best practice)
  - `first_day_notes` TextField blank=True (what to bring, parking, dress code, first-day schedule — driver: SAP SuccessFactors "Prepare for Day One"; Workable welcome message; Personio welcome email; BambooHR new hire packet)
  - `completed_at` DateTimeField null=True blank=True editable=False (system-set when status moves to "completed"; never on the form)
  - `notes` TextField blank=True (HR internal notes)
  - Meta: ordering=["-start_date"]; unique_together=("tenant","number"); also unique_together=("tenant","employee") — one onboarding program per employee per tenant (enforced via clean() with a descriptive error if violated)
  - Indexes: (tenant, employee); (tenant, status); (tenant, start_date)
  - `clean()`: validate `end_date > start_date` does not apply (no end_date); validate unique employee-per-tenant via `clean()`; validate `status != "draft"` before allowing `generate_tasks` action
  - `@property progress`: derived aggregate — `tasks = OnboardingTask.objects.filter(program=self)`; `total = tasks.count()`; return `int((tasks.filter(status="completed").count() / total) * 100) if total else 0` — NEVER stored (spine principle: derived-not-stored)
  - `__str__`: `f"{self.number} · {self.employee}"`
  - Drivers: Every surveyed product has a "program instance" anchored to employee + start date; welcome fields implement the Welcome Kit (NavERP 3.3.E) feature; buddy implements HiBob/SAP SuccessFactors/Personio/Enboarder buddy assignment; `progress` property implements BambooHR progress bar / Workday/HiBob/Personio completion dashboard
  - Reuses: `hrm.EmployeeProfile` (anchor — twice: employee + buddy); `hrm.OnboardingTemplate` (source template)
  - NOTE: Welcome Kit = `welcome_message` + `welcome_video_url` + `first_day_notes` on this model — no separate table needed. Policy documents reuse `OnboardingDocument(document_type="policy_acknowledgment")`.

### Model 4 — `OnboardingTask` (concrete per-program task, no auto-number)
- [ ] **`OnboardingTask`** — inherits `TenantOwned`; concrete task instance on one program
  - `program` FK→`"hrm.OnboardingProgram"` CASCADE related_name=`"tasks"`
  - `title` CharField max_length=255
  - `description` TextField blank=True
  - `task_category` CharField max_length=30 choices=TASK_CATEGORY_CHOICES default="custom" (same choices as `OnboardingTemplateTask.TASK_CATEGORY_CHOICES` — define as a module-level constant `TASK_CATEGORY_CHOICES` to avoid duplication)
  - `assignee_role` CharField max_length=20 choices=ASSIGNEE_ROLE_CHOICES default="hr" (same module-level `ASSIGNEE_ROLE_CHOICES`)
  - `assignee` FK→`settings.AUTH_USER_MODEL` SET_NULL null=True blank=True related_name=`"assigned_onboarding_tasks"` (the specific user resolved at instance creation; nullable — role alone is sufficient to show "IT should own this")
  - `due_date` DateField null=True blank=True (calculated at generation time: `program.start_date + timedelta(days=template_task.due_offset_days)`; editable by HR after creation)
  - `phase` CharField max_length=20 choices=PHASE_CHOICES default="week_1" (same module-level `PHASE_CHOICES`)
  - `STATUS_CHOICES = [("pending","Pending"),("in_progress","In Progress"),("completed","Completed"),("skipped","Skipped")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="pending"
  - `is_mandatory` BooleanField default=True
  - `completed_at` DateTimeField null=True blank=True editable=False (system-set on complete action — never on the form)
  - `completed_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null=True blank=True related_name=`"completed_onboarding_tasks"` (system-set — who clicked Complete; audit trail driver: BambooHR/Workday task completion tracking)
  - `order` PositiveIntegerField default=0
  - `notes` TextField blank=True
  - Meta: ordering=["program","phase","order","due_date"]; indexes: (tenant, program); (tenant, program, status); (tenant, program, phase)
  - `__str__`: `f"{self.program} → {self.title}"`
  - Drivers: BambooHR progress bar, Workday to-do lists, HiBob completion tracking, Workable task status (pending→in_progress→completed/skipped); `completed_by` satisfies audit requirement (who ticked it off); `assignee_role` kept alongside `assignee` so HR sees "IT should own this" even without a specific user

### Model 5 — `OnboardingDocument` (per-program, no auto-number)
- [ ] **`OnboardingDocument`** — inherits `TenantOwned`; document to collect or e-sign per program
  - `program` FK→`"hrm.OnboardingProgram"` CASCADE related_name=`"documents"`
  - `DOCUMENT_TYPE_CHOICES = [("employment_contract","Employment Contract"),("nda","NDA"),("offer_letter","Offer Letter"),("id_proof","ID Proof"),("tax_form","Tax Form"),("bank_details","Bank Details"),("policy_acknowledgment","Policy Acknowledgment"),("background_check","Background Check"),("custom","Custom")]`
  - `document_type` CharField max_length=30 choices=DOCUMENT_TYPE_CHOICES default="custom" (driver: SAP SuccessFactors/BambooHR/TriNet/Zenefits document type taxonomy; policy docs reuse `policy_acknowledgment` — no separate table)
  - `title` CharField max_length=255 (friendly display name, e.g. "Signed NDA", "W-4 Form")
  - `description` TextField blank=True (instructions to the new hire)
  - `file` FileField upload_to=`"hrm/onboarding/docs/%Y/%m/"` null=True blank=True (HR-uploaded template or collected file; SECURITY: validate in form — see `OnboardingDocumentForm.clean_file()`)
  - `ESIGN_STATUS_CHOICES = [("not_required","Not Required"),("pending","Pending"),("sent","Sent"),("viewed","Viewed"),("signed","Signed"),("declined","Declined")]`
  - `esign_required` BooleanField default=False (driver: BambooHR/Click Boarding/Rippling e-sign toggle)
  - `esign_status` CharField max_length=20 choices=ESIGN_STATUS_CHOICES default="not_required" (driver: BambooHR/HiBob/SAP SuccessFactors/Click Boarding e-sign status lifecycle — tracks signing without requiring live DocuSign integration)
  - `due_date` DateField null=True blank=True (driver: HiBob/SAP SuccessFactors/Click Boarding document collection deadline)
  - `signed_at` DateTimeField null=True blank=True editable=False (system-set when e-sign status moves to "signed")
  - `external_ref` CharField max_length=255 blank=True (DocuSign envelope ID stub for future integration — driver: BambooHR Mitratech/SAP DocuSign/Click Boarding API-first; keeps the integration hook without requiring it now)
  - Meta: ordering=["program","document_type","title"]; indexes: (tenant, program); (tenant, program, esign_status)
  - `__str__`: `f"{self.program} → {self.title}"`
  - SECURITY NOTE: `OnboardingDocumentForm.clean_file()` must enforce an extension allowlist (`{".pdf",".doc",".docx",".jpg",".jpeg",".png"}`) and a size cap (10 MB) — mirror `EmployeeProfileForm.clean_photo()`; document in the form class
  - Drivers: BambooHR e-sign (I-9/W-4/custom docs), Gusto document collection, SAP SuccessFactors document workflows, Click Boarding eSignature, TriNet/Zenefits paperless onboarding, Deel compliance document upload; `esign_status` tracks signing lifecycle without live integration now

### Model 6 — `AssetAllocation` [AST-]
- [ ] **`AssetAllocation`** — inherits `TenantNumbered`; physical asset issued to a new hire (or standalone)
  - `NUMBER_PREFIX = "AST"`
  - `program` FK→`"hrm.OnboardingProgram"` SET_NULL null=True blank=True related_name=`"assets"` (nullable so assets can exist without a program — e.g., ad-hoc issuance or offboarding return tracking)
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"asset_allocations"` (the recipient — required even when program is null)
  - `asset_name` CharField max_length=255 (e.g. "MacBook Pro 14", "ID Card", "Locker Key")
  - `ASSET_CATEGORY_CHOICES = [("laptop","Laptop"),("desktop","Desktop"),("phone","Phone"),("id_card","ID Card"),("access_card","Access Card"),("uniform","Uniform"),("vehicle","Vehicle"),("sim","SIM Card"),("other","Other")]`
  - `asset_category` CharField max_length=30 choices=ASSET_CATEGORY_CHOICES default="other" (driver: SAP SuccessFactors "Request Equipment" task, Rippling device inventory, HiBob equipment task, BambooHR IT checklist)
  - `serial_number` CharField max_length=100 blank=True (driver: Rippling tracks device serial; SAP SuccessFactors serial/tag)
  - `asset_tag` CharField max_length=100 blank=True
  - `STATUS_CHOICES = [("pending","Pending"),("issued","Issued"),("returned","Returned"),("lost","Lost"),("damaged","Damaged")]`
  - `status` CharField max_length=20 choices=STATUS_CHOICES default="pending"
  - `issued_at` DateTimeField null=True blank=True (driver: BambooHR/SAP SuccessFactors track issuance date for audit)
  - `issued_by` FK→`settings.AUTH_USER_MODEL` SET_NULL null=True blank=True related_name=`"hrm_assets_issued"` (driver: audit trail — who issued it)
  - `returned_at` DateTimeField null=True blank=True editable=False (system-set when status moves to "returned" via the return action; relevant for offboarding 3.4)
  - `return_due_date` DateField null=True blank=True (for contract/offboarding use — driver: Rippling/TriNet)
  - `notes` TextField blank=True
  - `# asset_id_stub: nullable IntegerField (commented out) — placeholder for future FK to 'assets.Asset' (Module 11 Asset Management). Once Module 11 is built, add migration: asset_id = models.IntegerField(null=True, blank=True, db_index=True, help_text="FK stub for future assets.Asset link")`
  - Meta: ordering=["-created_at"]; unique_together=("tenant","number"); indexes: (tenant, employee); (tenant, status); (tenant, program)
  - `__str__`: `f"{self.number} · {self.asset_name} → {self.employee}"`
  - Drivers: SAP SuccessFactors "Equipment List" + "Request Equipment" task types; Rippling device provisioning + inventory; HiBob equipment task; BambooHR IT checklist; TriNet app-provisioning; the `AST-` prefix was specified in research
  - Reuses: `hrm.EmployeeProfile` (recipient anchor); `hrm.OnboardingProgram` (nullable link)

### Model 7 — `OrientationSession` (per-program, no auto-number)
- [ ] **`OrientationSession`** — inherits `TenantOwned`; a scheduled orientation meeting or training event
  - `program` FK→`"hrm.OnboardingProgram"` SET_NULL null=True blank=True related_name=`"orientation_sessions"` (nullable — ad-hoc sessions outside a formal program are allowed)
  - `employee` FK→`"hrm.EmployeeProfile"` CASCADE related_name=`"orientation_sessions"` (required: the new hire attending)
  - `title` CharField max_length=255 (e.g. "HR Orientation", "IT Setup Walk-through", "Meet the Team Lunch")
  - `SESSION_TYPE_CHOICES = [("orientation","Orientation"),("training","Training"),("meet_greet","Meet & Greet"),("policy_review","Policy Review"),("system_demo","System Demo"),("department_intro","Department Intro"),("social","Social / Team Lunch"),("custom","Custom")]`
  - `session_type` CharField max_length=30 choices=SESSION_TYPE_CHOICES default="orientation" (driver: SAP SuccessFactors "Schedule Meeting" task; HiBob "meet & greet schedules"; Click Boarding orientation activity types)
  - `facilitator` FK→`settings.AUTH_USER_MODEL` SET_NULL null=True blank=True related_name=`"facilitated_orientation_sessions"` (driver: SAP SuccessFactors/HiBob assign responsible user per session)
  - `facilitator_name` CharField max_length=255 blank=True (free-text fallback for external trainers/speakers when no User record exists)
  - `scheduled_at` DateTimeField null=True blank=True
  - `duration_minutes` PositiveIntegerField null=True blank=True
  - `location` CharField max_length=255 blank=True (room name, "Zoom Link Below", "Building A Room 3")
  - `meeting_url` URLField blank=True (Zoom/Teams link — driver: Workable/Workday/Click Boarding virtual meeting link embedding)
  - `ATTENDANCE_STATUS_CHOICES = [("scheduled","Scheduled"),("attended","Attended"),("missed","Missed"),("rescheduled","Rescheduled"),("cancelled","Cancelled")]`
  - `attendance_status` CharField max_length=20 choices=ATTENDANCE_STATUS_CHOICES default="scheduled" (driver: Click Boarding engagement tracking; Enboarder completion analytics)
  - `notes` TextField blank=True
  - Meta: ordering=["scheduled_at"]; indexes: (tenant, employee); (tenant, program); (tenant, scheduled_at)
  - `clean()`: if `scheduled_at` is provided and `program` is not null, warn (non-blocking) that `scheduled_at` should be on or after `program.start_date` — raise ValidationError if `scheduled_at.date() < program.start_date`
  - `__str__`: `f"{self.title} @ {self.scheduled_at}" if self.scheduled_at else self.title`
  - Drivers: SAP SuccessFactors "Schedule Meeting" task; HiBob meet-and-greet schedules; Click Boarding orientation activities; Workable virtual meeting portal; Sapling People page introductions; `meeting_url` supports virtual meeting pattern; `attendance_status` tracks completion without full calendar integration

---

## Backend — add to existing `apps/hrm/` files

### `apps/hrm/models.py`
- [ ] Add module-level constants above the new models: `TASK_CATEGORY_CHOICES`, `ASSIGNEE_ROLE_CHOICES`, `PHASE_CHOICES` (shared by both `OnboardingTemplateTask` and `OnboardingTask`)
- [ ] Add all 7 model classes in order: `OnboardingTemplate`, `OnboardingTemplateTask`, `OnboardingProgram`, `OnboardingTask`, `OnboardingDocument`, `AssetAllocation`, `OrientationSession`
- [ ] Ensure `ALLOWED_DOC_EXTENSIONS` and `MAX_DOC_BYTES` constants are defined here or in forms.py for file upload validation

### `apps/hrm/forms.py`
- [ ] **`OnboardingTemplateForm`** (`TenantModelForm`) — fields: `name`, `description`, `designation`, `is_active`; `__init__` scopes `designation` queryset to `tenant` ordered by name
- [ ] **`OnboardingTemplateTaskForm`** (`TenantModelForm`) — fields: `template`, `title`, `description`, `task_category`, `assignee_role`, `due_offset_days`, `phase`, `order`, `is_mandatory`; `__init__` scopes `template` queryset to `tenant`; exclude `tenant`
- [ ] **`OnboardingProgramForm`** (`TenantModelForm`) — fields: `employee`, `template`, `start_date`, `buddy`, `welcome_message`, `welcome_video_url`, `first_day_notes`, `notes`; SECURITY: exclude `status` (set only by workflow actions), `completed_at` (system-set); `__init__` scopes `employee` queryset to `EmployeeProfile.objects.filter(tenant=tenant)`, `template` to `OnboardingTemplate.objects.filter(tenant=tenant, is_active=True)`, `buddy` to `EmployeeProfile.objects.filter(tenant=tenant)` (exclude the employee being onboarded via runtime filtering in the view)
- [ ] **`OnboardingTaskForm`** (`TenantModelForm`) — fields: `program`, `title`, `description`, `task_category`, `assignee_role`, `assignee`, `due_date`, `phase`, `is_mandatory`, `order`, `notes`; SECURITY: exclude `status` (set by workflow actions), `completed_at`, `completed_by` (system-set on complete action); `__init__` scopes `program` to tenant, `assignee` to `settings.AUTH_USER_MODEL` filtered by `profile__tenant=tenant` (or `User.objects.filter(tenant=tenant)` per the accounts app pattern)
- [ ] **`OnboardingDocumentForm`** (`TenantModelForm`) — fields: `program`, `document_type`, `title`, `description`, `file`, `esign_required`, `esign_status`, `due_date`, `external_ref`; SECURITY: exclude `signed_at` (system-set); `__init__` scopes `program` to tenant; implement `clean_file()`: check extension against `{".pdf",".doc",".docx",".jpg",".jpeg",".png"}` + size cap of 10 MB (mirror `EmployeeProfileForm.clean_photo()`)
- [ ] **`AssetAllocationForm`** (`TenantModelForm`) — fields: `program`, `employee`, `asset_name`, `asset_category`, `serial_number`, `asset_tag`, `status`, `issued_at`, `issued_by`, `return_due_date`, `notes`; SECURITY: exclude `returned_at` (system-set on return action), `number` (auto); `__init__` scopes `program` to tenant, `employee` to tenant, `issued_by` to tenant users
- [ ] **`OrientationSessionForm`** (`TenantModelForm`) — fields: `program`, `employee`, `title`, `session_type`, `facilitator`, `facilitator_name`, `scheduled_at`, `duration_minutes`, `location`, `meeting_url`, `attendance_status`, `notes`; `__init__` scopes `program` to tenant, `employee` to tenant, `facilitator` to tenant users

### `apps/hrm/views.py`
All views: `@login_required`, `tenant=request.tenant` filter, full CRUD via `crud_list`/`crud_create`/`crud_edit`/`crud_delete` helpers + `write_audit_log`. Mirror existing leave/attendance patterns exactly.

#### OnboardingTemplate CRUD
- [ ] `onboardingtemplate_list` — `crud_list(OnboardingTemplate.objects.filter(tenant=...).select_related("designation"), "hrm/onboardingtemplate_list.html", search_fields=["number","name","designation__name"], filters=[("is_active","is_active",False),("designation","designation_id",True)], extra_context={"designations": Designation.objects.filter(tenant=...).order_by("name")})`
- [ ] `onboardingtemplate_create` — `crud_create(OnboardingTemplateForm, "hrm/onboardingtemplate_form.html", "hrm:onboardingtemplate_list")`
- [ ] `onboardingtemplate_detail` — GET `OnboardingTemplate` with related `template_tasks.order_by("phase","order")`; pass task list grouped by phase for display
- [ ] `onboardingtemplate_edit` — `crud_edit(OnboardingTemplate, pk, OnboardingTemplateForm, "hrm/onboardingtemplate_form.html", "hrm:onboardingtemplate_list")`
- [ ] `onboardingtemplate_delete` — `crud_delete(OnboardingTemplate, pk, "hrm:onboardingtemplate_list")` with guard: block if `programs` exist using this template (warn and redirect rather than 500)

#### OnboardingTemplateTask CRUD
- [ ] `onboardingtemplatetask_list` — filter by template (int FK) + phase + task_category; search `["title","description"]`; extra_context: `templates`, `phase_choices=PHASE_CHOICES`, `category_choices=TASK_CATEGORY_CHOICES`
- [ ] `onboardingtemplatetask_create` — `crud_create(OnboardingTemplateTaskForm, "hrm/onboardingtemplatetask_form.html", "hrm:onboardingtemplatetask_list")`
- [ ] `onboardingtemplatetask_detail` — read-only view of task definition
- [ ] `onboardingtemplatetask_edit` — `crud_edit(...)`
- [ ] `onboardingtemplatetask_delete` — `crud_delete(...)`

#### OnboardingProgram CRUD + Workflow
- [ ] `onboardingprogram_list` — filter by status + employee (int FK); search `["number","employee__party__name"]`; extra_context: `status_choices=OnboardingProgram.STATUS_CHOICES`, `employees=EmployeeProfile.objects.filter(tenant=...)`; annotate queryset with `tasks_total=Count("tasks")` and `tasks_done=Count("tasks", filter=Q(tasks__status="completed"))` for progress display on the list
- [ ] `onboardingprogram_create` — `crud_create(OnboardingProgramForm, "hrm/onboardingprogram_form.html", "hrm:onboardingprogram_list")`
- [ ] `onboardingprogram_detail` — rich detail page: program header (employee, start_date, status, buddy, welcome fields), progress bar (`obj.progress`), tasks grouped by phase (with complete/reopen POST buttons per task), documents list, assets list, orientation sessions list; sidebar: edit/delete/activate/complete/cancel action buttons
- [ ] `onboardingprogram_edit` — `crud_edit(...)` (block if status == "completed" or "cancelled" — redirect with message)
- [ ] `onboardingprogram_delete` — `crud_delete(...)` (block delete if status == "active" — warn and redirect; allow delete only when draft or cancelled)

**Program workflow POST actions (mirror leave submit/approve/reject/cancel pattern):**
- [ ] `onboardingprogram_activate` — `@require_POST`, `@login_required`; transitions draft→active; calls `_generate_tasks_from_template(program)` if template is set and no tasks exist yet; sets `status="active"`; writes audit log; redirects to detail
- [ ] `onboardingprogram_generate_tasks` — `@require_POST`, `@login_required`; regenerates tasks from template (only if status == "draft" or "active" and tasks count == 0); calls `_generate_tasks_from_template(program)`; writes audit log; redirects to detail
- [ ] `onboardingprogram_complete` — `@require_POST`, `@tenant_admin_required`; transitions active→completed; sets `completed_at=timezone.now()`; writes audit log; redirects to detail
- [ ] `onboardingprogram_cancel` — `@require_POST`, `@tenant_admin_required`; transitions draft/active→cancelled; writes audit log; redirects to detail

**Task workflow POST actions:**
- [ ] `onboardingtask_complete` — `@require_POST`, `@login_required`; `OnboardingTask` GET: `get_object_or_404(OnboardingTask, pk=pk, program__tenant=request.tenant)`; sets `status="completed"`, `completed_at=timezone.now()`, `completed_by=request.user`; writes audit log; redirects to `hrm:onboardingprogram_detail` of the parent program
- [ ] `onboardingtask_reopen` — `@require_POST`, `@login_required`; clears `status` back to `"pending"`, clears `completed_at`/`completed_by`; writes audit log; redirects to program detail
- [ ] `onboardingtask_skip` — `@require_POST`, `@login_required`; sets `status="skipped"`; writes audit log; redirects to program detail

**Task generation helper (not a view — private function in views.py):**
- [ ] `_generate_tasks_from_template(program)` — private function; iterates `program.template.template_tasks.order_by("order")`; for each `OnboardingTemplateTask` creates an `OnboardingTask` with: `tenant=program.tenant`, `program=program`, `title=tt.title`, `description=tt.description`, `task_category=tt.task_category`, `assignee_role=tt.assignee_role`, `due_date=program.start_date + timedelta(days=tt.due_offset_days)`, `phase=tt.phase`, `is_mandatory=tt.is_mandatory`, `order=tt.order`; uses `get_or_create(tenant=..., program=..., title=..., defaults={...})` to be idempotent (calling it twice does not duplicate tasks)

#### OnboardingTask CRUD (standalone, also embedded on program detail)
- [ ] `onboardingtask_list` — filter by program (int FK) + status + phase + task_category; search `["title","description","assignee__username"]`; extra_context: `status_choices`, `phase_choices`, `category_choices`, `programs`; select_related `program`, `assignee`, `completed_by`
- [ ] `onboardingtask_create` — `crud_create(OnboardingTaskForm, "hrm/onboardingtask_form.html", "hrm:onboardingtask_list")`
- [ ] `onboardingtask_detail` — show all fields + completed_by/completed_at if done; sidebar: complete/reopen/skip/edit/delete
- [ ] `onboardingtask_edit` — `crud_edit(...)` (block if status == "completed" via guard message)
- [ ] `onboardingtask_delete` — `crud_delete(...)`

#### OnboardingDocument CRUD
- [ ] `onboardingdocument_list` — filter by program (int FK) + document_type + esign_status; search `["title","description","external_ref"]`; extra_context: `type_choices`, `esign_choices`, `programs`
- [ ] `onboardingdocument_create` — `crud_create(OnboardingDocumentForm, "hrm/onboardingdocument_form.html", "hrm:onboardingdocument_list")`; template must use `enctype="multipart/form-data"`
- [ ] `onboardingdocument_detail` — show file link, esign_status badge, due_date, external_ref stub note; sidebar: edit/delete + "Mark Signed" action button
- [ ] `onboardingdocument_edit` — `crud_edit(...)` with `enctype="multipart/form-data"` on template
- [ ] `onboardingdocument_delete` — `crud_delete(...)`
- [ ] `onboardingdocument_mark_signed` — `@require_POST`, `@login_required`; sets `esign_status="signed"`, `signed_at=timezone.now()`; writes audit log; redirects to detail

#### AssetAllocation CRUD
- [ ] `assetallocation_list` — filter by employee (int FK) + status + asset_category; search `["number","asset_name","serial_number","asset_tag"]`; extra_context: `status_choices`, `category_choices`, `employees`; select_related `employee`, `program`, `issued_by`
- [ ] `assetallocation_create` — `crud_create(AssetAllocationForm, "hrm/assetallocation_form.html", "hrm:assetallocation_list")`
- [ ] `assetallocation_detail` — full asset record; sidebar: issue/return/edit/delete action buttons
- [ ] `assetallocation_edit` — `crud_edit(...)`
- [ ] `assetallocation_delete` — `crud_delete(...)` (block if status == "issued" — warn that asset must be returned first)
- [ ] `assetallocation_issue` — `@require_POST`, `@login_required`; sets `status="issued"`, `issued_at=timezone.now()`, `issued_by=request.user`; writes audit log; redirects to detail
- [ ] `assetallocation_return` — `@require_POST`, `@login_required`; sets `status="returned"`, `returned_at=timezone.now()`; writes audit log; redirects to detail

#### OrientationSession CRUD
- [ ] `orientationsession_list` — filter by employee (int FK) + session_type + attendance_status; search `["title","location","facilitator__username","facilitator_name"]`; extra_context: `type_choices`, `attendance_choices`, `employees`; select_related `employee`, `program`, `facilitator`
- [ ] `orientationsession_create` — `crud_create(OrientationSessionForm, "hrm/orientationsession_form.html", "hrm:orientationsession_list")`
- [ ] `orientationsession_detail` — meeting details, meeting_url link, attendance_status badge; sidebar: mark-attended/mark-missed/edit/delete
- [ ] `orientationsession_edit` — `crud_edit(...)`
- [ ] `orientationsession_delete` — `crud_delete(...)`
- [ ] `orientationsession_mark_attended` — `@require_POST`, `@login_required`; sets `attendance_status="attended"`; writes audit log; redirects to detail
- [ ] `orientationsession_mark_missed` — `@require_POST`, `@login_required`; sets `attendance_status="missed"`; writes audit log; redirects to detail

### `apps/hrm/urls.py`
Append to existing `urlpatterns` (keep `app_name = "hrm"`):

- [ ] **OnboardingTemplate (3.3 — template admin):**
  - `onboarding-templates/` → `onboardingtemplate_list`
  - `onboarding-templates/add/` → `onboardingtemplate_create`
  - `onboarding-templates/<int:pk>/` → `onboardingtemplate_detail`
  - `onboarding-templates/<int:pk>/edit/` → `onboardingtemplate_edit`
  - `onboarding-templates/<int:pk>/delete/` → `onboardingtemplate_delete`

- [ ] **OnboardingTemplateTask (3.3 — template tasks):**
  - `onboarding-template-tasks/` → `onboardingtemplatetask_list`
  - `onboarding-template-tasks/add/` → `onboardingtemplatetask_create`
  - `onboarding-template-tasks/<int:pk>/` → `onboardingtemplatetask_detail`
  - `onboarding-template-tasks/<int:pk>/edit/` → `onboardingtemplatetask_edit`
  - `onboarding-template-tasks/<int:pk>/delete/` → `onboardingtemplatetask_delete`

- [ ] **OnboardingProgram (3.3 — program instances + workflow):**
  - `onboarding/` → `onboardingprogram_list`
  - `onboarding/add/` → `onboardingprogram_create`
  - `onboarding/<int:pk>/` → `onboardingprogram_detail`
  - `onboarding/<int:pk>/edit/` → `onboardingprogram_edit`
  - `onboarding/<int:pk>/delete/` → `onboardingprogram_delete`
  - `onboarding/<int:pk>/activate/` → `onboardingprogram_activate`
  - `onboarding/<int:pk>/generate-tasks/` → `onboardingprogram_generate_tasks`
  - `onboarding/<int:pk>/complete/` → `onboardingprogram_complete`
  - `onboarding/<int:pk>/cancel/` → `onboardingprogram_cancel`

- [ ] **OnboardingTask (3.3 — task instances + workflow):**
  - `onboarding-tasks/` → `onboardingtask_list`
  - `onboarding-tasks/add/` → `onboardingtask_create`
  - `onboarding-tasks/<int:pk>/` → `onboardingtask_detail`
  - `onboarding-tasks/<int:pk>/edit/` → `onboardingtask_edit`
  - `onboarding-tasks/<int:pk>/delete/` → `onboardingtask_delete`
  - `onboarding-tasks/<int:pk>/complete/` → `onboardingtask_complete`
  - `onboarding-tasks/<int:pk>/reopen/` → `onboardingtask_reopen`
  - `onboarding-tasks/<int:pk>/skip/` → `onboardingtask_skip`

- [ ] **OnboardingDocument (3.3 — document collection):**
  - `onboarding-documents/` → `onboardingdocument_list`
  - `onboarding-documents/add/` → `onboardingdocument_create`
  - `onboarding-documents/<int:pk>/` → `onboardingdocument_detail`
  - `onboarding-documents/<int:pk>/edit/` → `onboardingdocument_edit`
  - `onboarding-documents/<int:pk>/delete/` → `onboardingdocument_delete`
  - `onboarding-documents/<int:pk>/mark-signed/` → `onboardingdocument_mark_signed`

- [ ] **AssetAllocation (3.3 — asset issuance):**
  - `assets/` → `assetallocation_list`
  - `assets/add/` → `assetallocation_create`
  - `assets/<int:pk>/` → `assetallocation_detail`
  - `assets/<int:pk>/edit/` → `assetallocation_edit`
  - `assets/<int:pk>/delete/` → `assetallocation_delete`
  - `assets/<int:pk>/issue/` → `assetallocation_issue`
  - `assets/<int:pk>/return/` → `assetallocation_return`

- [ ] **OrientationSession (3.3 — orientation schedule):**
  - `orientation/` → `orientationsession_list`
  - `orientation/add/` → `orientationsession_create`
  - `orientation/<int:pk>/` → `orientationsession_detail`
  - `orientation/<int:pk>/edit/` → `orientationsession_edit`
  - `orientation/<int:pk>/delete/` → `orientationsession_delete`
  - `orientation/<int:pk>/mark-attended/` → `orientationsession_mark_attended`
  - `orientation/<int:pk>/mark-missed/` → `orientationsession_mark_missed`

### `apps/hrm/admin.py`
- [ ] Register `OnboardingTemplate` — list_display: `number, name, designation, is_active, tenant`; list_filter: `is_active, designation`; readonly: `number, created_at, updated_at`
- [ ] Register `OnboardingTemplateTask` — list_display: `template, title, task_category, assignee_role, phase, due_offset_days, is_mandatory`; list_filter: `task_category, assignee_role, phase`; raw_id_fields: `template`
- [ ] Register `OnboardingProgram` — list_display: `number, employee, start_date, status, buddy, tenant`; list_filter: `status`; readonly: `number, completed_at, created_at, updated_at`
- [ ] Register `OnboardingTask` — list_display: `program, title, task_category, phase, status, assignee, due_date`; list_filter: `status, phase, task_category`; readonly: `completed_at, completed_by`; raw_id_fields: `program`
- [ ] Register `OnboardingDocument` — list_display: `program, title, document_type, esign_status, due_date`; list_filter: `document_type, esign_status`; readonly: `signed_at, created_at, updated_at`
- [ ] Register `AssetAllocation` — list_display: `number, asset_name, asset_category, employee, status, issued_at, tenant`; list_filter: `status, asset_category`; readonly: `number, returned_at, created_at, updated_at`
- [ ] Register `OrientationSession` — list_display: `title, session_type, employee, scheduled_at, attendance_status, facilitator`; list_filter: `session_type, attendance_status`

---

## Migration
- [ ] `venv\Scripts\python.exe manage.py makemigrations hrm` — generates a single new migration (e.g. `apps/hrm/migrations/0002_onboardingtemplate_onboardingtemplatetask_onboardingprogram_onboardingtask_onboardingdocument_assetallocation_orientationsession.py`)
- [ ] `venv\Scripts\python.exe manage.py sqlmigrate hrm 0002` — review SQL; confirm all FK references, unique_together constraints, and indexes render correctly on MariaDB 10.4
- [ ] `venv\Scripts\python.exe manage.py migrate` — apply to `nav_erp`; confirm zero errors

---

## Seeder — extend `apps/hrm/management/commands/seed_hrm.py`
- [ ] Add import for new models at top: `OnboardingTemplate, OnboardingTemplateTask, OnboardingProgram, OnboardingTask, OnboardingDocument, AssetAllocation, OrientationSession`
- [ ] Add idempotency guard for each new model block: `if OnboardingTemplate.objects.filter(tenant=tenant).exists(): continue` (guard runs per-tenant before each model's seed block — print `"Onboarding data already exists for {tenant.slug} — skipping"` and continue to next tenant)
- [ ] **Seed 2 `OnboardingTemplate` rows per tenant:** e.g. "Engineering New Hire" (linked to the Engineering/Software Engineer designation) and "General Staff Onboarding" (no designation); each with 5–7 `OnboardingTemplateTask` rows covering all phases (preboarding/week_1/month_1) and all task categories (hr_admin/it_setup/manager_action/document_sign/equipment_request); use `get_or_create(tenant=tenant, name=name)` on the template and `get_or_create(tenant=tenant, template=tmpl, title=title, defaults={...})` on each task
- [ ] **Seed 2 `OnboardingProgram` rows per tenant:** one `active` (linked to employee #1 as the new hire, template = "Engineering New Hire", start_date = today + 7 days, buddy = employee #2) and one `completed` (employee #2, template = "General Staff Onboarding", start_date = today - 30 days, `completed_at` set); number guard: `existing = OnboardingProgram.objects.filter(tenant=tenant, employee=emp).first()`; skip if exists
- [ ] **Seed `OnboardingTask` rows** by calling `_generate_tasks_from_template(program)` (or equivalent inline logic) for the two programs; mark 3 tasks on the `completed` program as `status="completed"` with `completed_at` and `completed_by` set; leave remaining tasks as `pending` or `in_progress`
- [ ] **Seed 2–3 `OnboardingDocument` rows per program:** one `employment_contract` (esign_status="signed", signed_at set), one `id_proof` (esign_status="pending"), one `policy_acknowledgment` (esign_required=False, esign_status="not_required"); use `get_or_create(tenant=tenant, program=program, title=title, defaults={...})`
- [ ] **Seed 2–3 `AssetAllocation` rows per program's employee:** e.g. laptop (status="issued", issued_at set, issued_by=tenant admin user), id_card (status="issued"), access_card (status="pending"); use `get_or_create(tenant=tenant, number=number, defaults={...})` pattern (check for existing number first, generate one if not exists)
- [ ] **Seed 2 `OrientationSession` rows per active program:** one "HR Orientation" (session_type="orientation", scheduled_at=program.start_date + day 1, attendance_status="attended") and one "IT Setup Walk-through" (session_type="system_demo", scheduled_at=program.start_date + day 2, attendance_status="scheduled"); use `get_or_create(tenant=tenant, program=program, title=title, defaults={...})`
- [ ] After seeding, print: `"Onboarding seeded for {tenant.slug}: 2 templates, {N} template tasks, 2 programs, {N} tasks, {N} docs, {N} assets, {N} sessions."` and re-print: `"Superuser 'admin' has no tenant — log in as admin_acme / password to see onboarding data."`

---

## Wire-up

### `apps/core/navigation.py` — add `"3.3"` entry to `LIVE_LINKS`
- [ ] Add the following block to `LIVE_LINKS` (after the `"3.2"` block, before `"3.9"`):
  ```python
  # 3.3 Employee Onboarding — uses exact NavERP.md bullet text as keys
  "3.3": {
      "Onboarding Tasks": "hrm:onboardingprogram_list",      # bullet — program list is the primary entry; tasks are accessed via program detail
      "Document Collection": "hrm:onboardingdocument_list",   # bullet
      "Asset Allocation": "hrm:assetallocation_list",         # bullet
      "Orientation Schedule": "hrm:orientationsession_list",  # bullet
      "Welcome Kit": "hrm:onboardingprogram_list",            # bullet — welcome fields live on program (no separate table)
      "Onboarding Templates": "hrm:onboardingtemplate_list",  # extra — template management
      "Onboarding Programs": "hrm:onboardingprogram_list",    # extra (explicit duplicate for clarity in nav)
  },
  ```
- [ ] Verify the 5 NavERP.md 3.3 bullet labels ("Onboarding Tasks", "Document Collection", "Asset Allocation", "Orientation Schedule", "Welcome Kit") match exactly — check against `NavERP.md` grep results

---

## Templates (`templates/hrm/`)
One file per template. Mirror `hrm/leaverequest_list.html` / `hrm/leaverequest_detail.html` / `hrm/leaverequest_form.html` conventions: extend `base.html`, use design-system classes (`page-header`, `card`, `table`, `badge`, `form-*`, `empty-state`), `partials/pagination.html`, search `q` + filter selects pre-filled from `request.GET`, FK filters compare `obj.pk|stringformat:"d"`, boolean filters use `"True"/"False"`, badges use exact model choice values with `{{ obj.get_<field>_display }}` fallback, every list has an Actions column (view/edit/delete POST+csrf+confirm).

### OnboardingTemplate templates
- [ ] `hrm/onboardingtemplate_list.html` — table: number, name, designation link (nullable), is_active badge, task count (annotated); filter bar: is_active dropdown + designation FK dropdown; Actions: view/edit/delete
- [ ] `hrm/onboardingtemplate_detail.html` — template header (name, description, designation, is_active); tasks table grouped by phase (phase heading, then rows: order, title, category badge, assignee_role badge, due_offset_days, is_mandatory badge); "Apply Template to Employee" CTA link to `onboardingprogram_create?template=<pk>`; sidebar: edit/delete
- [ ] `hrm/onboardingtemplate_form.html` — create/edit form; is_edit toggle for page title

### OnboardingTemplateTask templates
- [ ] `hrm/onboardingtemplatetask_list.html` — table: template link, title, category badge, assignee_role badge, phase badge, due_offset_days, is_mandatory badge; filter bar: template FK + phase + task_category dropdowns; Actions: view/edit/delete
- [ ] `hrm/onboardingtemplatetask_detail.html` — all fields with badge display; sidebar: edit/delete
- [ ] `hrm/onboardingtemplatetask_form.html` — create/edit form; `due_offset_days` with helper text "Negative = before start date (e.g. -3), 0 = start date, positive = after"

### OnboardingProgram templates
- [ ] `hrm/onboardingprogram_list.html` — table: number, employee link, start_date, status badge, buddy link (nullable), progress bar (annotated tasks_done/tasks_total), template link; filter bar: status dropdown + employee FK dropdown; Actions: view/edit/delete
- [ ] `hrm/onboardingprogram_detail.html` — **rich detail page:**
  - Program header card: number, employee, start_date, status badge, buddy, template, progress bar (`obj.progress`% with colour by threshold: <25=red, 25-74=yellow, 75+=green)
  - Welcome Kit section: welcome_message (if set), welcome_video_url as embed/link (if set), first_day_notes
  - Tasks section: tasks grouped by phase (preboarding/week_1/month_1/month_2/month_3); per task row: category badge, title, assignee_role badge, assignee username (nullable), due_date (coloured red if overdue), status badge; Actions column: "Complete" POST form (show if not completed), "Reopen" POST form (show if completed), "Skip" POST form (show if pending)
  - Documents section: table of `OnboardingDocument` rows: type badge, title, esign_required, esign_status badge, due_date, file link (if uploaded), "Mark Signed" POST button (show if esign_status != "signed"); link to "Add Document"
  - Assets section: table of `AssetAllocation` rows: AST- number, asset_name, category badge, serial_number, status badge, issued_at, "Issue" POST button (if pending), "Return" POST button (if issued); link to "Add Asset"
  - Orientation Sessions section: table of sessions ordered by scheduled_at: title, session_type badge, facilitator (or facilitator_name), scheduled_at, meeting_url link (if set), attendance_status badge, "Mark Attended"/"Mark Missed" POST buttons; link to "Add Session"
  - Sidebar: Edit (if not completed/cancelled), Delete (if draft/cancelled), Activate (if draft, `@login_required`), Generate Tasks (if active/draft and no tasks yet, `@login_required`), Complete (if active, `@tenant_admin_required`), Cancel (if draft/active, `@tenant_admin_required`)
- [ ] `hrm/onboardingprogram_form.html` — create/edit form; note below buddy field: "Leave blank to assign later"; notes field below welcome section

### OnboardingTask templates
- [ ] `hrm/onboardingtask_list.html` — table: program link, title, category badge, phase badge, assignee_role badge, assignee (nullable), due_date (red if overdue), status badge; filter bar: program FK + status + phase + task_category dropdowns; Actions: view/edit/delete + quick Complete/Skip inline POST buttons in Actions column
- [ ] `hrm/onboardingtask_detail.html` — all task fields, completed_by/completed_at display if done; sidebar: Complete/Reopen/Skip POST buttons + edit/delete
- [ ] `hrm/onboardingtask_form.html` — create/edit form; exclude status/completed_at/completed_by (set by workflow)

### OnboardingDocument templates
- [ ] `hrm/onboardingdocument_list.html` — table: program link, type badge, title, esign_required bool, esign_status badge, due_date, file download link (if file set); filter bar: program FK + document_type + esign_status dropdowns; Actions: view/edit/delete + "Mark Signed" inline POST
- [ ] `hrm/onboardingdocument_detail.html` — all fields; file download link (if file); external_ref stub label with note "DocuSign/eSign integration reference (future)"; sidebar: Mark Signed POST button (if esign_status != "signed") + edit/delete
- [ ] `hrm/onboardingdocument_form.html` — create/edit form with `enctype="multipart/form-data"`; show currently-uploaded file name on edit; `clean_file()` enforces allowlist + size cap

### AssetAllocation templates
- [ ] `hrm/assetallocation_list.html` — table: number, asset_name, category badge, employee link, serial_number, status badge, issued_at; filter bar: employee FK + status + asset_category dropdowns; Actions: view/edit/delete + Issue/Return inline POST buttons (conditional on status)
- [ ] `hrm/assetallocation_detail.html` — full asset record: number, asset_name, category, employee, program link (nullable), serial_number, asset_tag, status badge, issued_at, issued_by, return_due_date, returned_at (if returned), notes; stub note: "asset_id field reserved for future Module 11 Asset Management link"; sidebar: Issue POST (if pending), Return POST (if issued), edit/delete (guarded when issued)
- [ ] `hrm/assetallocation_form.html` — create/edit form; exclude returned_at (system-set); note on return_due_date: "Optionally set a return deadline (e.g. contract end date)"

### OrientationSession templates
- [ ] `hrm/orientationsession_list.html` — table: title, session_type badge, employee link, scheduled_at (coloured if overdue), facilitator/facilitator_name, attendance_status badge; filter bar: employee FK + session_type + attendance_status dropdowns; Actions: view/edit/delete + Mark Attended/Missed POST inline
- [ ] `hrm/orientationsession_detail.html` — all session fields; meeting_url rendered as clickable link with "Join Meeting" label if set; duration_minutes displayed as "X min"; sidebar: Mark Attended/Missed POST buttons (conditional on attendance_status) + edit/delete
- [ ] `hrm/orientationsession_form.html` — create/edit form; `scheduled_at` uses `<input type="datetime-local">` widget; `meeting_url` with helper text "Paste Zoom/Teams/Meet link"

---

## Verify
- [ ] `venv\Scripts\python.exe manage.py makemigrations hrm` — confirms a single new migration file
- [ ] `venv\Scripts\python.exe manage.py migrate` — zero errors on `nav_erp`
- [ ] `venv\Scripts\python.exe manage.py seed_hrm` (first run) — seeds all 7 onboarding model types; prints counts and login reminder
- [ ] `venv\Scripts\python.exe manage.py seed_hrm` (second run) — prints "already exists — skipping" for every onboarding model block; zero duplicate rows created (idempotency proof)
- [ ] `venv\Scripts\python.exe manage.py check` — zero errors, zero warnings
- [ ] Write `temp/hrm_onboarding_smoke.py` — Django test-client sweep:
  - Authenticate as `admin_acme` (tenant admin)
  - Hit all new `hrm:*` onboarding URL names (all list/detail/create/edit/delete routes) → expect 200 or 302
  - Check the onboardingprogram_list page HTML for absence of `{#` and `{% comment` (template-comment leak check)
  - IDOR check: GET `hrm:onboardingprogram_detail` with a `pk` belonging to `admin_globex`'s tenant while authenticated as `admin_acme` → expect 404
  - IDOR check: POST `hrm:assetallocation_issue` with a `pk` belonging to a different tenant → expect 404
  - POST `hrm:onboardingprogram_activate` → confirm `status` changes to "active" and tasks are created
  - POST `hrm:onboardingtask_complete` → confirm `completed_at` is set and `completed_by == request.user`
  - POST `hrm:onboardingprogram_complete` as non-admin → expect 403 (tenant_admin_required gate)
  - POST `hrm:assetallocation_delete` when status=="issued" → confirm redirect with warning (no delete)
- [ ] Run `temp/hrm_onboarding_smoke.py` — all checks green
- [ ] Sidebar check: sub-module 3.3 appears as **Live** with all 5 NavERP.md 3.3 bullets showing clickable hrefs (Onboarding Tasks, Document Collection, Asset Allocation, Orientation Schedule, Welcome Kit)

---

## Close-out
- [ ] Run **`code-reviewer` agent** — apply findings; commit each changed file one at a time (PowerShell-safe, one file per commit)
- [ ] Run **`explorer` agent** — apply findings; commit
- [ ] Run **`frontend-reviewer` agent** — apply findings; commit
- [ ] Run **`performance-reviewer` agent** — pay special attention to: N+1 on `onboardingprogram_detail` (tasks+documents+assets+sessions all loaded), `progress` property called per row on list vs. annotated aggregate, `_generate_tasks_from_template` bulk_create opportunity; commit
- [ ] Run **`qa-smoke-tester` agent** — apply findings; commit
- [ ] Run **`security-reviewer` agent** — flag: file upload extension/size allowlist in `OnboardingDocumentForm.clean_file()`; `@tenant_admin_required` on program complete/cancel; cross-tenant IDOR on all task/doc/asset/session workflow POST routes (scope via `program__tenant` / `employee__tenant`); commit
- [ ] Run **`test-writer` agent** — add tests: model `clean()` validations, `_generate_tasks_from_template` idempotency, task complete/reopen state machine, `OnboardingDocument.clean_file()` allowlist enforcement, IDOR (404 on cross-tenant pk access), `@tenant_admin_required` gate on program complete/cancel (non-admin → 403), `progress` property accuracy; commit
- [ ] Update **`.claude/skills/hrm/SKILL.md`** — add 3.3 models, URL names, workflow actions, LIVE_LINKS 3.3 entry, seeder additions, and the `_generate_tasks_from_template` helper; update description line to include "3.3 onboarding"; commit
- [ ] Update **`README.md`** — mark sub-module 3.3 Employee Onboarding as Live in the module status table; add `seed_hrm` now includes onboarding data note; commit

### Per-file commit list (PowerShell-safe, one file per commit)
```
git add 'apps\hrm\models.py'; git commit -m 'feat(hrm): add 3.3 onboarding models — OnboardingTemplate[ONBT-], OnboardingTemplateTask, OnboardingProgram[ONB-], OnboardingTask, OnboardingDocument, AssetAllocation[AST-], OrientationSession'
git add 'apps\hrm\migrations\0002_onboardingtemplate_onboardingtemplatetask_onboardingprogram_onboardingtask_onboardingdocument_assetallocation_orientationsession.py'; git commit -m 'feat(hrm): migration 0002 — 3.3 onboarding tables'
git add 'apps\hrm\forms.py'; git commit -m 'feat(hrm): forms for 3.3 onboarding models — OnboardingTemplateForm, OnboardingTemplateTaskForm, OnboardingProgramForm, OnboardingTaskForm, OnboardingDocumentForm (file allowlist+size), AssetAllocationForm, OrientationSessionForm'
git add 'apps\hrm\views.py'; git commit -m 'feat(hrm): views for 3.3 onboarding — full CRUD + workflow actions (activate, generate_tasks, complete, cancel, task complete/reopen/skip, asset issue/return, doc mark-signed, session mark-attended/missed) + _generate_tasks_from_template helper'
git add 'apps\hrm\urls.py'; git commit -m 'feat(hrm): URL patterns for 3.3 onboarding — template/task/program/task-instance/document/asset/session CRUD + workflow POST routes'
git add 'apps\hrm\admin.py'; git commit -m 'feat(hrm): admin registration for 7 onboarding models'
git add 'apps\hrm\management\commands\seed_hrm.py'; git commit -m 'feat(hrm): extend seed_hrm with 3.3 onboarding demo data — templates, template tasks, programs, tasks, documents, assets, orientation sessions (idempotent)'
git add 'apps\core\navigation.py'; git commit -m 'feat(core/nav): wire LIVE_LINKS 3.3 Employee Onboarding — 5 bullets + 2 extras → hrm:onboarding*/asset*/orientation* routes'
git add 'templates\hrm\onboardingtemplate_list.html'; git commit -m 'feat(hrm): onboarding template list with is_active/designation filters'
git add 'templates\hrm\onboardingtemplate_detail.html'; git commit -m 'feat(hrm): onboarding template detail with phase-grouped task table and apply CTA'
git add 'templates\hrm\onboardingtemplate_form.html'; git commit -m 'feat(hrm): onboarding template create/edit form'
git add 'templates\hrm\onboardingtemplatetask_list.html'; git commit -m 'feat(hrm): onboarding template task list with template/phase/category filters'
git add 'templates\hrm\onboardingtemplatetask_detail.html'; git commit -m 'feat(hrm): onboarding template task detail'
git add 'templates\hrm\onboardingtemplatetask_form.html'; git commit -m 'feat(hrm): onboarding template task form with due_offset_days helper text'
git add 'templates\hrm\onboardingprogram_list.html'; git commit -m 'feat(hrm): onboarding program list with status/employee filters and progress bar column'
git add 'templates\hrm\onboardingprogram_detail.html'; git commit -m 'feat(hrm): onboarding program detail — rich page with tasks-by-phase, documents, assets, orientation sessions, and workflow sidebar actions'
git add 'templates\hrm\onboardingprogram_form.html'; git commit -m 'feat(hrm): onboarding program create/edit form with welcome kit fields'
git add 'templates\hrm\onboardingtask_list.html'; git commit -m 'feat(hrm): onboarding task list with program/status/phase/category filters and quick complete/skip actions'
git add 'templates\hrm\onboardingtask_detail.html'; git commit -m 'feat(hrm): onboarding task detail with complete/reopen/skip sidebar'
git add 'templates\hrm\onboardingtask_form.html'; git commit -m 'feat(hrm): onboarding task create/edit form'
git add 'templates\hrm\onboardingdocument_list.html'; git commit -m 'feat(hrm): onboarding document list with program/type/esign_status filters'
git add 'templates\hrm\onboardingdocument_detail.html'; git commit -m 'feat(hrm): onboarding document detail with esign stub and mark-signed action'
git add 'templates\hrm\onboardingdocument_form.html'; git commit -m 'feat(hrm): onboarding document form with multipart file upload and clean_file enforcement'
git add 'templates\hrm\assetallocation_list.html'; git commit -m 'feat(hrm): asset allocation list with employee/status/category filters and issue/return quick actions'
git add 'templates\hrm\assetallocation_detail.html'; git commit -m 'feat(hrm): asset allocation detail with issue/return workflow and Module 11 stub note'
git add 'templates\hrm\assetallocation_form.html'; git commit -m 'feat(hrm): asset allocation create/edit form'
git add 'templates\hrm\orientationsession_list.html'; git commit -m 'feat(hrm): orientation session list with employee/type/attendance filters'
git add 'templates\hrm\orientationsession_detail.html'; git commit -m 'feat(hrm): orientation session detail with meeting link, attended/missed actions'
git add 'templates\hrm\orientationsession_form.html'; git commit -m 'feat(hrm): orientation session create/edit form with datetime-local widget'
git add 'temp\hrm_onboarding_smoke.py'; git commit -m 'test(hrm): smoke test for 3.3 onboarding routes — 200/302, no leaks, IDOR 404, workflow transitions, admin-gate 403'
git add '.claude\skills\hrm\SKILL.md'; git commit -m 'docs(skill/hrm): extend SKILL.md with 3.3 onboarding — 7 models, URL names, workflow actions, LIVE_LINKS 3.3, seeder additions'
git add 'README.md'; git commit -m 'docs(readme): mark HRM 3.3 Employee Onboarding as Live in module status table'
```

---

## Later passes / deferred

- **Real e-signature API integration** (DocuSign, HelloSign, Adobe Sign) — `OnboardingDocument.esign_status` + `external_ref` stub are in place. The webhook/callback handler + API send-for-signature call is a later integration pass. Seen in: BambooHR (Mitratech), SAP SuccessFactors (DocuSign), Rippling (native eSign), Click Boarding (API-first).
- **Preboarding before EmployeeProfile exists** — `OnboardingProgram` requires a pre-existing `EmployeeProfile` (created at offer acceptance in 3.8 Offer Management). True candidate-stage preboarding (offer accepted, no employee record yet) requires ATS/Recruiting modules 3.5–3.8 to be built first; deferred to the ATS pass.
- **Employee Offboarding (3.4)** — `AssetAllocation.status="returned"` + `returned_at` stub the offboarding data model. Full offboarding workflows (resignation, clearance, F&F settlement) belong to sub-module 3.4 (deferred).
- **Automated task reminder / nudge emails** — `OnboardingTask.due_date` data is present. The email dispatch (Celery `send_mail` scheduled job or Django signals) requires background task infrastructure. Deferred to a notifications pass. Seen in: Enboarder "manager nudges", HiBob/Rippling/Workday automated reminders.
- **Calendar invite integration** (Google Calendar / Outlook / MS Teams) — `OrientationSession.meeting_url` stores the link. Actual iCal/CalDAV API calls + OAuth are an integration-later item. Seen in: HiBob, Enboarder, Workable, Click Boarding.
- **IT system provisioning automation** — Rippling's hallmark: auto-provisioning Slack, email, Salesforce by role. `OnboardingTask(task_category="it_setup")` records the intent; the actual API calls to 500+ apps require each integration. Deferred.
- **AI-generated 30-60-90 day plans** — Enboarder's differentiator: AI reads job description + resume to generate a personalized plan. The `phase` field on `OnboardingTask` supports phases. AI generation requires an LLM integration pass.
- **New hire self-service portal** — A dedicated new-hire-facing view (separate from HR admin view) showing only the hire's own program, tasks, and documents to complete. The data model fully supports this. Deferred to an employee self-service (ESS) pass (NavERP 3.25 Personal Information). It is a template + view change only — no model change needed.
- **Bulk / role-triggered auto-onboarding** — Auto-triggering an `OnboardingProgram` when a `core.Employment` is created with a specific `Designation`. Can be a Django signal or management command; deferred to a workflow automation pass.
- **Custom digital form builder** — Structured forms for the new hire to fill in arbitrary data fields beyond `EmployeeProfile`. Gusto/BambooHR have this. Requires a form-builder model (dynamic fields). Deferred — out of scope for this pass.
- **Background verification integration** — Deel, SAP SuccessFactors, Workable (3.8) mention BGV vendor integration. Belongs to the Offer Management (3.8) pass.
- **Link `AssetAllocation` to Module 11 `assets.Asset`** — `asset_id_stub` comment in the model documents where the FK goes. Once Module 11 (Asset Management) is built, add migration: `asset_id = models.ForeignKey("assets.Asset", SET_NULL, null=True, blank=True)`.
- **Policy acknowledgment workflow** — A richer version of tracking policy acknowledgment (timestamp, digital signature, version tracking, per-policy acknowledgment list). Currently modeled as `OnboardingDocument(document_type="policy_acknowledgment", esign_status="signed")`. A dedicated compliance pass is deferred.

## Review notes
(filled in at the end)

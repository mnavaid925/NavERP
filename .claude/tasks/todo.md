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


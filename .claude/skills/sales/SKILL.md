---
name: sales
description: Work on the Sales Management System module (Module 8), including 8.1 Lead Management scoring, BANT/MEDDIC qualification, deterministic owner routing, CRM drip nurture enrollment, and 8.3 Contact & Account Management. Use when the user asks to add/change/debug anything under apps/sales or templates/sales, extend seed_sales, touch Sales sidebar wiring (LIVE_LINKS 8.x), or invokes /sales.
---

# Sales Management System (Module 8)

App path: `apps/sales/`; templates: `templates/sales/`; URL namespace: `sales`; mounted at `/sales/`.

## Ownership boundary

8.1 is a thin operational layer over the canonical CRM and core spine. It does not create a second lead, opportunity, campaign, territory, task, party, contact, or conversion writer.

- Canonical lead: `crm.Lead` (`LEAD-`).
- Canonical opportunity and conversion: `crm.Opportunity` and `apps/crm/services.py:convert_lead`.
- Web capture/ingestion: `crm.LandingPage`, `crm.FormSubmission`, `crm.Campaign`, `crm.CampaignMember`.
- CRM drip campaign: `crm.EmailCampaign(send_type="drip")`.
- Territory master: `crm.Territory`.
- Follow-up task: `crm.CrmTask`.
- Identity/consent references: `core.Party`, `core.ContactMethod`, `core.ConsentPurpose`.
- Users/owners: `accounts.User`; global budget currency: `accounting.Currency`.

Capture and conversion links reuse CRM. CSV/API/ad/chat ingestion, predictive AI, real ESP delivery, and funnel analytics are deferred to later Sales/CRM work.

## 8.1 models

Backend is package-based: `models/`, `forms/`, `views/`, and `urls/` each contain `LeadManagement/` and matching entity files. Every package `__init__.py` re-exports its 8.1 entities.

### `LeadScoreEvent`

`apps/sales/models/LeadManagement/LeadScoreEvents.py`

Append-only, tenant-scoped behavioral/firmographic score facts. Fields: `lead`, `signal_category`, `event_type`, signed `score_delta` (-100..100), `source_kind`, opaque `source_ref`, `reason`, `effective_until`, idempotency key, self-FK `corrects_event`, `occurred_at`, `recorded_by`, immutable `created_at`.

Normal event deltas are deterministic: form 5, email open 2, click 8, web visit 1, content 6, event 4, meeting 10, demo 15, call 8, reply 12, fit match 20, fit mismatch -15, unsubscribe -25, decay -5. Manual/correction deltas are explicit and reasoned. Corrections are inverse append-only facts; one correction per original. Score projection clamps to 0..100 with cold 0..39, warm 40..69, hot 70..100. CRM `Lead.score`/`rating` are cached projections; they are not ordinary CRM form fields.

### `LeadQualification`

`apps/sales/models/LeadManagement/LeadQualifications.py`

One current OneToOne assessment per CRM lead. Frameworks: BANT, MEDDIC, both. Statuses: unassessed, partially qualified, qualified, disqualified, archived. Stores geography/firmographics and qualification evidence without duplicating Party/Address/Account/Contact. Qualified status requires framework evidence; disqualified requires a reason; terminal decisions require an assessor. Qualification decisions compensate score facts, project CRM lead status, exit nurture, and invoke the deterministic router.

### `LeadRoutingRule`

`apps/sales/models/LeadManagement/LeadRoutingRules.py`

Tenant-wide configuration for fixed owner, CRM territory manager, or bounded round-robin assignment. Conditions are a strict JSON list (maximum 20 conditions, 16 KiB, closed field/operator allowlist, finite scalar values). Unknown JSON fails closed; no `eval`, dynamic import, relation traversal, or network call. The resolver orders active rules by priority/id, rejects converted leads and archived assessments, locks selected rows, and writes CRM lead owner plus one reusable CRM task and audit evidence.

### `LeadNurtureEnrollment`

`apps/sales/models/LeadManagement/LeadNurtureEnrollments.py`

Numbered `LNE-#####` lifecycle state for one lead and one CRM drip campaign. Unique by `(tenant, lead, email_campaign)` and `(tenant, number)`. Activation requires an active same-tenant consent purpose and evidence for optional purposes; it snapshots score and records a next-touch target. The module sends no email and has no ESP/worker. Pending rows may be edited; activated identity/consent fields are locked. Lifecycle verbs are activate, pause, resume, complete, cancel, reply, and verified convert-exit.

## 8.1 routes and views

`app_name="sales"`; `sales_root` is `/sales/`, `lead_overview` is `/sales/overview/`.

- Score: `lead_score_event_list`, `_detail`, `_adjust`, `_correct`, `_recompute`.
- Qualification: `lead_qualification_list`, `_create`, `_detail`, `_edit`, `_delete`, `_partial`, `_qualify`, `_disqualify`, `_archive`, `_recalculate`, `_route_preview`.
- Routing: `lead_routing_rule_list`, `_create`, `_detail`, `_edit`, `_delete`, `_toggle`, `_preview`, `_run`.
- Nurture: `lead_nurture_enrollment_list`, `_create`, `_detail`, `_edit`, `_delete`, `_activate`, `_pause`, `_resume`, `_complete`, `_cancel`, `_reply`, `_convert_exit`.
- Handoff: `lead_handoff` (`leads/<pk>/handoff/`) is POST-only and tenant-admin/qualified-assessment gated; it calls the CRM conversion service and never duplicates its writes.

All pages use `@login_required` for reads. Configuration/manual score/activation/resume/archive actions are tenant-admin gated. All mutating actions are POST-only and CSRF-protected. Lists use `crud_list` with search, pre-pagination filters, pagination, Actions, and empty states. Lists pass every FK queryset and choice list consumed by their filter bars.

## 8.3 Contact & Account Management

8.3 is an account-workspace and buying-center layer over the canonical CRM/core spine. It adds only four Sales-owned records and four model-free boards. It does not add an account/contact master, health score, opportunity, order, invoice, product, or provider connector.

- Canonical account/contact identity: `core.Party` with `crm.AccountProfile` and `crm.ContactProfile`.
- Hierarchy pointer: `crm.AccountProfile.parent_account`; the CRM model, form, view, and admin paths enforce same-tenant organization/profile, non-self, bounded, transitive-cycle-safe writes.
- Health: `crm.HealthScore` and `crm.HealthScoreHistory` are read-only sources.
- Commercial context: `crm.Opportunity`, `scm.SalesOrder`, and `accounting.Invoice` are read-only; currency buckets remain separate and Opportunity currency is explicitly unspecified.
- Relationships: `crm.ContactProfile.account` remains the primary affiliation; `core.PartyRelationship(kind='reports_to')` remains the reporting graph; Sales stakeholder rows are account-specific context only.
- Enrichment: local proposal/review evidence only. No outbound HTTP, LinkedIn/provider sync, verification worker, scheduler, merge, or email send ships here.

### 8.3 models

- `PartyEnrichmentEvent` — `apps/sales/models/ContactAccountManagement/PartyEnrichment.py`; append-only `TenantEventOwned` evidence for `core.Party` enrichment proposals. Choices are `firmographic`, `contact`, `email_validation`, `phone_validation`, `social`, `employment_change`, `duplicate_check`; sources are `manual`, `provider`, `email_signature`, `linkedin`, `import`, `api`; statuses are `proposed`, `applied`, `rejected`, `no_match`, `failed`. `changes` is a bounded allowlisted object for `job_title`, `department`, `linkedin`, `work_email`, `phone`, `mobile`, `website`, `industry`, `employee_count`, and `annual_revenue`. External sources require a same-tenant active consent purpose. Request/apply/reject are service actions, with no ordinary edit/delete.
- `AccountStakeholder` — `apps/sales/models/ContactAccountManagement/AccountStakeholders.py`; account-specific buying-center row linking a same-tenant organization Party to a different same-tenant person Party. Choices: roles `decision_maker`, `economic_buyer`, `champion`, `influencer`, `blocker`, `technical_evaluator`, `procurement`, `end_user`, `advisor`, `other`; influence `high`/`medium`/`low`/`unknown`; attitude `positive`/`neutral`/`negative`/`unknown`; strength `strong`/`moderate`/`weak`/`unknown`; status `active`/`former`. It stores validity dates and notes, not a primary account or org chart.
- `AccountClassification` — `apps/sales/models/ContactAccountManagement/AccountClassifications.py`; one current human-governed row per account with `strategic`, `key`, `growth`, `nurture` tiers; `prospect`, `active_customer`, `expansion_candidate`, `dormant`, `former_customer` lifecycle; `high`/`medium`/`low` priority; `very_high`/`high`/`medium`/`low`/`unknown` potential; and `none`/`small`/`medium`/`large`/`full_wallet` wallet categories. Rationale is required; strategic/key rows require a review date. It stores no revenue, health, or rollup facts.
- `AccountPlan` — `apps/sales/models/ContactAccountManagement/AccountPlans.py`; numbered `ACPL-` plan with `draft`, `active`, `review_due`, `completed`, `archived` lifecycle. It stores narrative strategy/white-space assessment and links existing `crm.Opportunity` rows through `related_opportunities`; period order, active same-tenant owner, and same-account opportunity invariants are enforced on form, service, and M2M writes. Delete is draft-only; non-draft plans archive.

The 8.3 migration is `apps/sales/migrations/0004_accountclassification_accountplan_accountstakeholder_and_more.py`; it creates the four tables and implicit M2M join only. Do not edit an 8.2 or CRM migration while this checkout has concurrent schema drift.

### 8.3 routes and views

`apps/sales/urls/ContactAccountManagement/` is appended after the 8.1 route modules. Literal routes precede every `<int:pk>` route.

- Enrichment: `party_enrichment_list`, `party_enrichment_detail`, `party_enrichment_request`, `party_enrichment_apply`, `party_enrichment_reject`, `party_enrichment_export` under `enrichment-events/`.
- Stakeholders: `account_stakeholder_list`, `account_stakeholder_create`, `account_stakeholder_detail`, `account_stakeholder_edit`, `account_stakeholder_delete`, `account_stakeholder_export` under `account-stakeholders/`.
- Classifications: `account_classification_list`, `account_classification_create`, `account_classification_detail`, `account_classification_edit`, `account_classification_delete`, `account_classification_export` under `account-classifications/`.
- Plans: `account_plan_list`, `account_plan_create`, `account_plan_detail`, `account_plan_edit`, `account_plan_delete`, `account_plan_activate`, `account_plan_review_due`, `account_plan_complete`, `account_plan_archive`, `account_plan_export` under `account-plans/`.
- Boards: `account_hierarchy`, `account_workspace`, `account_coverage`, `account_white_space`, and `account_workspace_export` under `accounts/`.

List contexts expose the pinned object list, pagination, filter values, choice lists, bounded FK querysets, aggregate stats, and export URLs. Detail contexts expose canonical account/contact, health/activity/document evidence, rollups, and `can_edit` where applicable. Board contexts expose the contract's `account_rows`, `coverage_rows`, `white_space_rows`, `currency_rollups`, `caveats`, and selected-account evidence. Every read is login-required; state-changing actions are POST/CSRF protected. Classification create/edit/delete and enrichment apply require tenant-admin access; plan edit/lifecycle follows owner-or-tenant-admin policy.

### 8.3 templates

Templates live under `templates/sales/contactaccountmanagement/`:

- `partyenrichmentevent/{list,detail}.html`
- `accountstakeholder/{list,detail,form}.html`
- `accountclassification/{list,detail,form}.html`
- `accountplan/{list,detail,form}.html`
- `account_hierarchy.html`, `account_workspace.html`, `account_coverage.html`, `account_white_space.html`

Use `base.html`, `partials/pagination.html`, the existing theme cards/tables/forms, and only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, and `badge-slate`. Lists have search, filters, pagination, and Actions; mutable details have edit/POST-delete/back controls. Enrichment has no edit/delete. Nullable health, currency, activity, document, and rollup values render as unavailable rather than fabricated zero. White-space pages state that exact product mapping is not governed yet.

### Seeder, exports, and tests

`venv\Scripts\python.exe manage.py seed_sales` is the single idempotent Sales seeder. It reuses tenant users, canonical Parties, CRM profiles, consent purposes, and existing opportunities; creates a root/child/grandchild plus separate account demo, stakeholder roles, classifications, plan lifecycle rows, and local enrichment proposal/apply/reject examples. It skips missing prerequisites with a message and prints the tenant admin login, tenantless-superuser warning, and the no-provider/no-worker boundary. Run it twice without `--flush` in a shared database.

All 8.3 CSV exports use the active list filters, a 5,000-row cap, `csv_safe` formula neutralization, and sanitized audit metadata. Do not export raw enrichment payloads, credentials, or mixed-currency totals. Run the full Sales suite plus focused CRM/core regressions; the 8.3 test namespace is `contactaccountmanagement`.

### Conventions and common tasks

- Filter every tenant-owned FK/M2M to `request.tenant`; validate model, form, admin, service, and M2M paths against crafted foreign IDs.
- Use the CRM account/profile pages for identity edits; do not introduce a Sales account/contact writer.
- Keep enrichment fields allowlisted and person/organization applicability explicit; redact credential-like values and sanitize errors/source references.
- Keep plan owner/admin authorization and status transitions centralized; use `save(commit=False)` plus `save_m2m()` inside the service transaction.
- Use `account_rollups` and board helpers for currency-separated, bounded, cycle-safe reads; never sum annual revenue, opportunity amount, order total, and invoice total together.
- To add a field, update the model/form/serializer equivalent, template context, export columns, seed coverage, and focused tests together.
- To add a filter, pass the exact choice/queryset key, validate GET values before filtering, and keep export parity.
- To add a board, use the existing computed-board context conventions and avoid a snapshot/analytics model.
- To extend the seeder, use `get_or_create` or existing-number checks and prove a second run creates no duplicates.
- `request.tenant=None` (superuser `admin`) intentionally yields empty tenant-scoped Sales data; use `admin_acme` / `password` for demo data.

## 8.3 sidebar wiring

`apps/core/navigation.py` contains `LIVE_LINKS["8.3"]` with these staff destinations:

- Account Hierarchy & Parent-Child → `sales:account_hierarchy`
- Contact Profiles & Enrichment → `sales:account_workspace#enrichment`
- Relationship Mapping → `sales:account_coverage`
- Account Segmentation & Tiering → `sales:account_classification_list`
- Account Plans & Growth Strategies → `sales:account_plan_list`
- Extras: Account Workspace, Enrichment Review Queue, Stakeholder Register, Account Classification, Coverage Matrix, Account Plans, White-Space Board

## Templates

- `templates/sales/overview.html` — Sales qualification/readiness board with CRM links and `#handoff`.
- `templates/sales/leadmanagement/leadscoreevent/{list,detail}.html` — append-only history/projection; no create/edit/delete.
- `templates/sales/leadmanagement/leadqualification/{list,detail,form}.html`.
- `templates/sales/leadmanagement/leadroutingrule/{list,detail,form}.html`.
- `templates/sales/leadmanagement/leadnurtureenrollment/{list,detail,form}.html`.

Use `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`; `detail-grid`/`detail-item`; `table-wrap`/`table-actions`; and `partials/pagination.html`. Nullable user/FKs are guarded. Nurture pages state that no message is sent and that `next_touch_at` is only a recorded target.

## Seeder and migrations

Run `venv\Scripts\python.exe manage.py migrate sales` then `venv\Scripts\python.exe manage.py seed_sales` twice. The command is idempotent per tenant/model, backfills score facts for CRM leads, reuses CRM users/leads/territories/campaigns, creates/reuses a drip campaign and consent purpose, and prints `admin_acme / password`, the tenantless-superuser warning, and the no-ESP/no-worker boundary. Do not use `--flush` in a shared database.

8.1 migrations are `0001_initial`, `0002_alter_leadroutingrule_max_open_leads_and_more`, and `0003_leadnurtureenrollment_tenant_number_uniq`; check the current migration graph because later Sales sub-modules may add migrations.

## Tests and conventions

Run `DJANGO_SETTINGS_MODULE=config.settings_test venv\Scripts\python.exe -m pytest -q apps/sales/tests` (use `--nomigrations` only for fast iteration). The 8.1 suite is `test_leadmanagement_models.py`, `test_leadmanagement_forms.py`, `test_leadmanagement_views.py`, and `test_leadmanagement_security.py`; shared contracts/factories are in `apps/sales/tests/conftest.py`.

- Filter FK IDs in templates with `|stringformat:"d"` and validate crafted integer/date input before querying.
- Never use `Model.objects.all()` in a tenant view.
- Never expose tenant, auto-number, score snapshot, system timestamps/counters, or status fields that an action owns on ordinary forms.
- Keep CRM conversion identity writes in `apps/crm/services.py`; Sales handoff is orchestration around that service.
- Use `write_audit_log` for cross-app projections; free-text qualification/consent evidence is redacted from generic audit changes.
- `request.tenant=None` (superuser `admin`) intentionally sees empty Sales data.

## Common tasks

- Add a score event type: update the model choices and explicit delta map, add form/service tests, and preserve append-only correction semantics.
- Add a qualification field: update the model/form/detail/list context and test framework validation; do not add a duplicate identity table.
- Add a routing condition: extend the closed allowlist only, add finite/type/size validation, and test invalid JSON plus positive matching rows.
- Add a nurture transition: update the status/reason map, lock order, view decorator, template control, and lifecycle/security tests.
- Add a list filter: pass choices/queryset in `extra_context`, apply it before pagination, and render an accessible control reflecting `request.GET`.

## Sidebar wiring

`apps/core/navigation.py` contains `LIVE_LINKS["8.1"]`:

- Lead Capture & Ingestion → `crm:formsubmission_list`
- Lead Scoring & Grading → `sales:lead_score_event_list`
- Lead Qualification & Routing → `sales:lead_qualification_list`
- Lead Nurturing & Drip Campaigns → `sales:lead_nurture_enrollment_list`
- Lead Conversion & Handoff → `sales:lead_overview#handoff`
- Extras: Lead Operations Board, Score Events, Qualification Assessments, Routing Rules, Nurture Enrollments

---
name: sales
description: Work on the Sales Management System module (Module 8), including 8.1 Lead Management, 8.2 Opportunity & Pipeline Management, and 8.3 Contact & Account Management. Use when the user asks to add/change/debug anything under apps/sales or templates/sales, extend seed_sales, touch Sales sidebar wiring (LIVE_LINKS 8.x), or invokes /sales.
---

# Sales Management System (Module 8)

App path: `apps/sales/`; templates: `templates/sales/`; URL namespace: `sales`; mounted at `/sales/`.

## Ownership boundary

8.1, 8.2, and 8.3 are operational layers over the canonical CRM and core spine. They do not duplicate `crm.Lead`, `crm.Opportunity`, `core.Party`, `core.OrgUnit`, or `accounts.User`.

- Canonical lead: `crm.Lead` (`LEAD-`).
- Canonical opportunity and conversion: `crm.Opportunity` (`OPP-`) and `apps/crm/services.py:convert_lead`.
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

## 8.2 Opportunity & Pipeline Management

8.2 delivers multi-pipeline deal stage tracking, progression criteria, deal health scoring, velocity and stale deal detection, deal team collaboration, competitive intelligence battle cards, and structured win/loss outcome tracking over `crm.Opportunity`.

### 8.2 models

- `Pipeline` — `apps/sales/models/OpportunityPipeline/Pipelines.py`; `TenantNumbered` (`PIPE-`) model representing a structured sales process. Fields: `name`, `description`, `is_default`, `is_active`.
- `PipelineStage` — `apps/sales/models/OpportunityPipeline/Pipelines.py`; ordered stage within a pipeline. Fields: `pipeline`, `name`, `code` (slug), `sequence`, `stage_kind` (`open`, `won`, `lost`), `crm_stage_key`, `probability` (0-100), `forecast_category` (`omitted`, `pipeline`, `best_case`, `commit`, `closed`), `entry_guidance`, `exit_guidance`, `entry_criteria` (JSON), `exit_criteria` (JSON), `target_days`, `is_active`. Enforces active shape invariants: exactly one won stage, exactly one lost stage, and at least one open stage.
- `OpportunityPipelinePlacement` — `apps/sales/models/OpportunityPipeline/Pipelines.py`; placement of a `crm.Opportunity` on a pipeline stage. Fields: `opportunity` (OneToOne), `pipeline`, `current_stage`, `stage_entered_at`, `probability_override`, `notes`.
- `OpportunityTeamMember` — `apps/sales/models/OpportunityTeams/OpportunityTeams.py`; cross-functional deal team. Fields: `opportunity`, `user`, `org_unit`, `role` (`co_owner`, `collaborator`, `sales_support`, `solution_consultant`, `executive_sponsor`, `approver`, `observer`), `responsibility`, `is_active`.
- `CompetitorProfile` — `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py`; `TenantNumbered` (`CMP-`) competitive intelligence. Fields: `party` (OneToOne `core.Party`, `kind='organization'`), `aliases`, `website_url`, `description`, `market_positioning`, `strengths`, `weaknesses`, `differentiators`, `objection_handling`, `is_active`.
- `OpportunityCompetitor` — `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py`; deal-specific competitor tracking. Fields: `opportunity`, `competitor_profile`, `relationship` (`identified`, `evaluating`, `shortlisted`, `preferred`, `incumbent`, `eliminated`, `lost_to`, `beaten`, `withdrew`), `is_primary`, `pricing_notes`, `deal_notes`, `positioning_notes`.
- `WinLossReason` — `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py`; `TenantNumbered` (`WLR-`) standardized decision drivers. Fields: `code` (slug), `name`, `description`, `sequence`, `result` (`won`, `lost`, `both`), `category` (`price`, `product_fit`, `timing`, `competition`, `relationship`, `authority`, `budget`, `no_decision`, `other`), `is_active`.
- `OpportunityOutcome` — `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py`; terminal deal closure decision. Fields: `opportunity` (OneToOne), `result` (`won`, `lost`), `reason` (FK `WinLossReason`), `competitor_link` (FK `OpportunityCompetitor`), `notes`, `closed_at`, `recorded_by`.

### 8.2 routes and views

- Pipelines & Stages: `opportunity_pipeline_list`, `_create`, `_detail`, `_edit`, `_delete`, `_set_default`, `_stages`, `_stage_create`, `_stage_edit`, `_stage_delete`, `_stage_reorder`.
- Pipeline Boards & Analytics: `opportunity_pipeline_board` (Kanban deal stages with currency metrics and health filters), `opportunity_pipeline_visibility` (stale deals, age distribution, velocity projections).
- Deal Workspace & Outcomes: `opportunity_workspace_list` (operational deal cockpit), `opportunity_workspace_detail` (comprehensive deal 360: placement, team, competitors, timeline, contracts, documents, audit logs), `opportunity_place`, `opportunity_unplace`, `opportunity_transition` (gated won/lost closures).
- Deal Teams: `opportunity_team_member_add`, `_edit`, `_remove`.
- Competitive Intelligence: `opportunity_competitor_profile_list`, `_create`, `_detail`, `_edit`, `_delete`, `opportunity_competitor_link_add`, `_edit`, `_remove`.
- Win/Loss Governance: `opportunity_win_loss_reason_list`, `_create`, `_detail`, `_edit`, `_delete`.

### 8.2 templates

Located in `templates/sales/opportunity/`:
- `workspace.html` — Deal 360 cockpit with active placement, team roster, competitor links, timeline, documents, contracts, and audit trails.
- `placement.html` — Pipeline stage placement and stage transition modal/form.
- `pipeline/list.html`, `detail.html`, `form.html`, `stages.html`, `board.html`, `visibility.html`.
- `competitor/list.html`, `detail.html`, `form.html`, `link_form.html`.
- `team_member/form.html`.
- `winlossreason/list.html`, `detail.html`, `form.html`.

### 8.2 navigation wiring

`apps/core/navigation.py` contains `LIVE_LINKS["8.2"]`:
- Visual Pipeline & Deal Stages → `sales:opportunity_pipeline_board`
- Multiple Pipelines → `sales:opportunity_pipeline_list`
- Deal Velocity & Stale Deals → `sales:opportunity_pipeline_visibility`
- Competitive Tracking → `sales:opportunity_competitor_profile_list`
- Win/Loss Analysis → `sales:opportunity_win_loss_reason_list`
- Deal Team Collaboration → `sales:opportunity_workspace_list`

## 8.4 Sales Forecasting

8.4 adds the forecasting cycle — periods, per-rep calls, manager overrides, what-if scenarios and four derived reports — over the 8.2 opportunity spine. It owns **no** customer, quota master, order or ledger: `crm.Opportunity` is the roll-up master, `crm.SalesQuota` is read/snapshotted only (quota *design* belongs to 8.7), and `accounting.Currency` remains the single currency spine.

### 8.4 models

All four live in `apps/sales/models/SalesForecasting/`.

- `ForecastPeriod` — `ForecastPeriods.py`; `TenantNumbered` (`FCP-`) forecasting cycle. Fields: `name`, `period_type` (`month`/`quarter`/`year`), `period_year`, `period_number`, `start_date`/`end_date` (**both `editable=False`** — derived, never typed), `rollup_dimension` (`user`/`org_unit`/`territory`), `reporting_currency` (FK `accounting.Currency`), `fx_rate_source_date`, `is_active`, `is_locked`. Properties `label`, `is_current`, `period_elapsed_pct`.
- `ForecastSubmission` — `ForecastSubmissions.py`; `TenantNumbered` (`FCS-`) one rep's call for a period. Fields: `period`, `owner`, `org_unit`, `territory`, `pipeline`, `quota_ref` (FK `crm.SalesQuota`), `submitted_by`, `reviewed_by`, `status` (`draft`/`submitted`/`approved`/`rejected`/`reverted`), the five category amounts `omitted_amount`/`pipeline_amount`/`best_case_amount`/`commit_amount`/`closed_amount`, the **service snapshot** `weighted_amount`, the `quota_amount` snapshot, `actual_amount`, `submitted_at`, `reviewed_at`, `review_note`, the explainable AI block (`ai_predicted_pipeline`/`_best_case`/`_commit`, `ai_confidence_pct`, `ai_model_name`, `ai_model_version`, `ai_generated_at`, `ai_explanation` JSON), `notes`. Properties `total_forecast_amount`, `variance_amount`, `attainment_pct`, `pace_pct`, `is_frozen`.
- `ForecastAdjustment` — `ForecastAdjustments.py`; `TenantNumbered` (`FAD-`) the manager override audit trail. Fields: `submission`, `opportunity`, `placement`, `created_by`, `adjustment_kind` (direct/indirect/revert), `target_field`, `original_value`, `adjusted_value`, `original_category`, `adjusted_category`, **`reason_code` (mandatory — it *is* the sandbagging signal)**, `note`, `is_reverted`, `reverted_at`, `revert_reason`. **No `status` field** (deliberate). Property `net_delta`. The system value is never stored, which is what makes Reset always possible.
- `ForecastScenario` — `ForecastScenarios.py`; `TenantNumbered` (`FSC-`) what-if modelling. Fields: `period`, `owner`, `name`, `scenario_type`, `probability_pct`, `is_baseline`, `is_selected` (workflow-owned), the deltas `pipeline_delta_pct`/`best_case_delta_pct`/`commit_delta_pct`, the snapshots `projected_commit_amount`/`projected_total_amount`, `assumption_notes`. A `CheckConstraint` keeps only the baseline selectable. **A scenario must never mutate a real submission.**

### 8.4 routes and views

- Periods: `forecast_period_list`, `_create`, `_detail`, `_edit`, `_delete`, `_export`, `_lock`, `_unlock`.
- Submissions: `forecast_submission_list`, `_create`, `_detail`, `_edit`, `_delete`, `_export`, `_submit`, `_approve`, `_reject`.
- Adjustments: `forecast_adjustment_list`, `_create`, `_detail`, `_edit`, `_delete`, `_export`, `_revert`.
- Scenarios: `forecast_scenario_list`, `_create`, `_detail`, `_edit`, `_delete`, `_select`, `_apply`.
- Derived reports (no model, read-only): `forecast_board` (rep→manager→director rollup), `forecast_attainment` (quota vs pace), `forecast_accuracy` (actual vs predicted, bias, sandbagging), `forecast_call` (per-rep call + override audit trail).

### 8.4 templates

`templates/sales/salesforecasting/` — lowercase folder, matching 8.1/8.3 (do **not** "fix" it to `forecasting/`):
- `forecastperiod/{list,detail,form}.html`, `forecastsubmission/{list,detail,form}.html`, `forecastadjustment/{list,detail,form}.html`, `forecastscenario/{list,detail,form}.html`.
- `forecastboard/{board,attainment,accuracy,call}.html` — the four report pages.

### 8.4 services

`apps/sales/forecast_services.py` (flat module at the app root, like `opportunity_services.py`): `forecast_org_unit_chain` (bounded, cycle-safe `core.OrgUnit.parent` walk — there is **no `User.manager`**), `forecast_submission_snapshot`, `forecast_ai_gate`.

### 8.4 seeder, migration and conventions

- Migration is **`apps/sales/migrations/0007_forecastperiod_forecastscenario_forecastsubmission_and_more.py`**. A correct model split needs no further migration — `makemigrations sales --check` must say *No changes detected*.
- `seed_sales` is idempotent and seeds 2 `FCP-` periods (current + prior), 2 `FCS-` calls across two owners, 3 `FAD-` adjustments (one reverted) and 2 `FSC-` scenarios (baseline selected).
- **Derived values are never columns.** `total_forecast_amount`, `variance_amount`, `attainment_pct`, `pace_pct`, `net_delta` are properties; `weighted_amount` is a service snapshot excluded from the form. Every percentage has a zero guard returning `None` — never `Infinity`/`NaN` (`Decimal` division by zero raises).
- **The AI gate is 40 won AND 40 lost `OpportunityOutcome` rows.** With fewer, every prediction value must render as nothing and the gate message must show. A leaked prediction with the gate shut is a Critical defect.
- **A period declares ONE `reporting_currency`**, so its submissions are commensurable by construction; a period with none gets a caveat rather than an unqualified grand total.
- **Enum values are `PipelineStage.STAGE_KIND_*` / `FORECAST_CATEGORY_*` class attributes** — grep them before hardcoding a literal.
- Tests live in `apps/sales/tests/test_salesforecasting_*.py`; every test is `test_salesforecasting_*` and every helper `_salesforecasting_*` so the next sub-module appending nearby cannot shadow them.

### 8.4 navigation wiring

`apps/core/navigation.py` `LIVE_LINKS["8.4"]`:
- Forecast Categories & Commitments → `sales:forecast_submission_list`
- AI-Powered Predictive Forecasting → `sales:forecast_board`
- Quota Management & Attainment → `sales:forecast_attainment`
- Forecast Rollups & Adjustments → `sales:forecast_adjustment_list`
- Forecast Accuracy & Variance Analysis → `sales:forecast_accuracy`
- Extra live leaves: Forecast Periods → `sales:forecast_period_list`, Scenarios & What-If → `sales:forecast_scenario_list`, Forecast Call → `sales:forecast_call`

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

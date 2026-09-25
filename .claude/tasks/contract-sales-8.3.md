# Contract — NavERP 8.3 Contact & Account Management

- App: `apps/sales` (existing app; do not scaffold or change `INSTALLED_APPS`/root URL include)
- Sub-module: `8.3 Contact & Account Management`
- Base SHA captured immediately before the build: `736c77ae2d52a274e02a479c4d58503f7112eefb`
- Research: `.claude/tasks/research-sales-8.3.md`
- Plan: `.claude/tasks/todo.md` (8.3 block)
- Test namespace: `contactaccountmanagement`

## Ownership boundaries

1. `core.Party` is the sole account/contact identity. `crm.AccountProfile` and `crm.ContactProfile` remain the canonical profile owners; Sales pages link to CRM identity/profile pages and never duplicate account/contact CRUD.
2. `crm.AccountProfile.parent_account` is the sole hierarchy pointer. Harden its existing model/form/write paths for same-tenant organization/profile, non-self, and transitive-cycle validation. Sales adds no parent field or hierarchy table.
3. `crm.HealthScore` and `crm.HealthScoreHistory` remain the only account-health truth. `crm.Opportunity`, `scm.SalesOrder`, and `accounting.Invoice` are read-only rollup sources. No Sales copies of these or of products/accounts/contacts are created.
4. `crm.ContactProfile.account` remains the primary affiliation. `core.PartyRelationship(kind='reports_to')` remains the reporting graph. `AccountStakeholder` adds account-specific buying-center facts only.
5. Enrichment is local proposal/review evidence only. No outbound HTTP, provider connector, LinkedIn sync, scheduled/bulk worker, email/phone verification claim, merge, or silent employment move ships in 8.3.
6. Every model is tenant-scoped; every list/detail/action query filters `tenant=request.tenant`; all FK/M2M selections are same-tenant and Party-kind validated. Hierarchy visibility never grants access.
7. The physical 8.2 source classes are not runtime dependencies; use only live `crm.Opportunity`.

## New package layout

- `apps/sales/models/ContactAccountManagement/{__init__.py,PartyEnrichment.py,AccountStakeholders.py,AccountClassifications.py,AccountPlans.py}`
- `apps/sales/forms/ContactAccountManagement/{__init__.py,PartyEnrichment.py,AccountStakeholders.py,AccountClassifications.py,AccountPlans.py}`
- `apps/sales/views/ContactAccountManagement/{__init__.py,PartyEnrichment.py,AccountStakeholders.py,AccountClassifications.py,AccountPlans.py,AccountBoards.py}`
- `apps/sales/urls/ContactAccountManagement/{__init__.py,PartyEnrichment.py,AccountStakeholders.py,AccountClassifications.py,AccountPlans.py,AccountBoards.py}`
- `templates/sales/contactaccountmanagement/partyenrichmentevent/{list,detail}.html`
- `templates/sales/contactaccountmanagement/accountstakeholder/{list,detail,form}.html`
- `templates/sales/contactaccountmanagement/accountclassification/{list,detail,form}.html`
- `templates/sales/contactaccountmanagement/accountplan/{list,detail,form}.html`
- `templates/sales/contactaccountmanagement/{account_hierarchy,account_workspace,account_coverage,account_white_space}.html`

Top-level package re-exports, URL concatenation, admin, seeder, and navigation are changed only at integration, after all files exist.

## Model contract

### `PartyEnrichmentEvent`

File: `models/ContactAccountManagement/PartyEnrichment.py`; inherit `TenantEventOwned`.

Fields: `tenant`; `party -> core.Party`; `kind`; `source_kind`; `source_name`; `source_reference`; `status`; nullable `match_confidence` (`DecimalField(max_digits=5, decimal_places=4)` validated 0..1); `changes` JSON; nullable `legal_basis_purpose -> core.ConsentPurpose`; nullable `requested_by`, `reviewed_by -> AUTH_USER_MODEL`; `occurred_at`; nullable `applied_at`; nullable `idempotency_key`; `error_code`; sanitized `error_summary`; inherited immutable `created_at`.

Choices:

- `KIND_CHOICES = firmographic, contact, email_validation, phone_validation, social, employment_change, duplicate_check`
- `SOURCE_KIND_CHOICES = manual, provider, email_signature, linkedin, import, api`
- `STATUS_CHOICES = proposed, applied, rejected, no_match, failed`

Constraints/indexes: tenant-scoped unique `(tenant, idempotency_key)`; indexes `(tenant, party, -occurred_at)`, `(tenant, status, -occurred_at)`, `(tenant, kind, -occurred_at)`. `changes` is a bounded allowlisted object: only `job_title`, `department`, `linkedin`, `work_email`, `phone`, `mobile`, `website`, `industry`, `employee_count`, `annual_revenue`; each value is a bounded scalar and optional confidence, never nested instructions, model paths, credentials, raw provider payloads, or fetch URLs. External source kinds require a same-tenant active `ConsentPurpose`; source reference is opaque text, not a URL. Events are append-only: no ordinary edit/delete or admin write. The request service creates `proposed`; apply/reject services update the row and canonical contact projections atomically and audit only sanitized changes.

### `AccountStakeholder`

File: `models/ContactAccountManagement/AccountStakeholders.py`; inherit `TenantOwned`.

Fields: `tenant`; `account -> core.Party`; `contact -> core.Party`; `role`; `influence`; `attitude`; `relationship_strength`; `status`; nullable `valid_from`, `valid_to`; `notes`; timestamps.

Choices:

- `ROLE_CHOICES = decision_maker, economic_buyer, champion, influencer, blocker, technical_evaluator, procurement, end_user, advisor, other`
- `INFLUENCE_CHOICES = high, medium, low, unknown`
- `ATTITUDE_CHOICES = positive, neutral, negative, unknown`
- `RELATIONSHIP_STRENGTH_CHOICES = strong, moderate, weak, unknown`
- `STATUS_CHOICES = active, former`

Account is a different same-tenant organization Party; contact is a same-tenant person Party; dates are ordered. Unique `(tenant, account, contact, role)` and indexes `(tenant, account, status)`, `(tenant, contact, status)`, `(tenant, role, attitude)`. This is not a primary-account or org-chart replacement.

### `AccountClassification`

File: `models/ContactAccountManagement/AccountClassifications.py`; inherit `TenantOwned`.

Fields: `tenant`; OneToOne `account -> core.Party`; `tier`; `lifecycle_stage`; `strategic_priority`; `revenue_potential`; `wallet_category`; `rationale`; `effective_on`; nullable `review_due_on`; nullable `classified_by -> AUTH_USER_MODEL`; timestamps.

Choices:

- `TIER_CHOICES = strategic, key, growth, nurture`
- `LIFECYCLE_STAGE_CHOICES = prospect, active_customer, expansion_candidate, dormant, former_customer`
- `STRATEGIC_PRIORITY_CHOICES = high, medium, low`
- `REVENUE_POTENTIAL_CHOICES = very_high, high, medium, low, unknown`
- `WALLET_CATEGORY_CHOICES = none, small, medium, large, full_wallet`

Account is a same-tenant organization. Rationale is required on every classification write; strategic/key rows require `review_due_on`; effective date defaults to `timezone.localdate()`. One current row per account, no historical classification or stored revenue/health/rollup. Duplicate create redirects to edit/upsert rather than 500. Classification is human intent; health remains CRM-owned.

### `AccountPlan`

File: `models/ContactAccountManagement/AccountPlans.py`; inherit `TenantNumbered`, `NUMBER_PREFIX='ACPL'`.

Fields: inherited `tenant`, `number`, timestamps; `account -> core.Party`; `title`; `period_start`, `period_end`; `status`; `owner -> AUTH_USER_MODEL`; `business_drivers`, `objectives`, `strategy`, `strengths`, `weaknesses`, `opportunities`, `threats`, `white_space_assessment`, `growth_initiatives`, `risk_summary`; nullable `next_review_on`; M2M `related_opportunities -> crm.Opportunity`.

`STATUS_CHOICES = draft, active, review_due, completed, archived`. New plans are draft; ordinary forms never edit status/number. Transitions are POST-only: draft→active; active→review_due; active/review_due→completed; draft/active/review_due/completed→archived. Period is ordered; owner is active and same-tenant; selected opportunities are same-tenant and same-account. Unique `(tenant, number)` and indexes `(tenant, account, status)`, `(tenant, owner, next_review_on)`, `(tenant, status, next_review_on)`. Delete is draft-only; non-draft plans archive. No revenue, health, product, task, QBR, onboarding, renewal, or coverage fields are copied.

## Forms

All tenant-owned forms accept `tenant=...`, narrow every FK/M2M queryset, and reject crafted foreign IDs in `clean()`.

- `PartyEnrichmentProposalForm`: `party`, `kind`, `source_kind`, `source_name`, `source_reference`, `changes`, `legal_basis_purpose`; no tenant/status/requester/confidence/timestamps.
- `PartyEnrichmentApplyForm`: bounded `selected_fields`, `review_note`; tenant-admin only at the view/service layer.
- `PartyEnrichmentRejectForm`: required `review_note`.
- `AccountStakeholderForm.Meta.fields` exactly `account`, `contact`, `role`, `influence`, `attitude`, `relationship_strength`, `status`, `valid_from`, `valid_to`, `notes`; exclude tenant/timestamps.
- `AccountClassificationForm.Meta.fields` exactly `account`, `tier`, `lifecycle_stage`, `strategic_priority`, `revenue_potential`, `wallet_category`, `rationale`, `effective_on`, `review_due_on`; exclude tenant/actor/timestamps.
- `AccountPlanForm.Meta.fields` exactly `account`, `title`, `period_start`, `period_end`, `owner`, `business_drivers`, `objectives`, `strategy`, `strengths`, `weaknesses`, `opportunities`, `threats`, `white_space_assessment`, `growth_initiatives`, `risk_summary`, `next_review_on`, `related_opportunities`; exclude tenant/number/status/timestamps. Validate M2M after form cleaning again in the save service.

## URL names and order

Literal routes precede every `<int:pk>` route.

- Enrichment: `party_enrichment_list`, `party_enrichment_detail`, `party_enrichment_request`, `party_enrichment_apply`, `party_enrichment_reject`, `party_enrichment_export`; paths `enrichment-events/`, `enrichment-events/request/`, `enrichment-events/export/`, `enrichment-events/<int:pk>/`, `/apply/`, `/reject/`.
- Stakeholders: `account_stakeholder_list`, `_create`, `_detail`, `_edit`, `_delete`, `_export`; paths `account-stakeholders/`, `add/`, `<int:pk>/`, `edit/`, `delete/`, `export/`.
- Classifications: `account_classification_list`, `_create`, `_detail`, `_edit`, `_delete`, `_export`; same literal-first shape under `account-classifications/`.
- Plans: `account_plan_list`, `_create`, `_detail`, `_edit`, `_delete`, `_activate`, `_review_due`, `_complete`, `_archive`, `_export`; same literal-first shape under `account-plans/`.
- Boards: `account_hierarchy`, `account_workspace`, `account_coverage`, `account_white_space`, `account_workspace_export`; paths `accounts/hierarchy/`, `accounts/workspace/`, `accounts/coverage/`, `accounts/white-space/`, `accounts/workspace/export/`.

## Context and filter contract

- Enrichment list: `object_list`, `page_obj`, `q`, `parties`, `kind_choices`, `source_kind_choices`, `status_choices`, `party_id`, `kind`, `source_kind`, `status`, `date_from`, `date_to`, `stats`, `proposal_form`, `export_url`; filters q/party/kind/source/status/date before pagination.
- Enrichment detail: `obj`, `party`, `proposal_rows`, `canonical_values`, `can_apply`, `can_reject`, `apply_form`, `reject_form`, `audit_events`, `export_url`.
- Stakeholder list: `object_list`, `page_obj`, `q`, `accounts`, `contacts`, all five choice lists, `account_id`, `contact_id`, all current filter strings, `stats`, `export_url`; detail: `obj`, `account`, `contact`, `is_primary_affiliation`, `reports_to`, `related_opportunities`, `interaction_recency`, `coverage_roles`, `can_edit`; form: `form`, `is_edit`, `obj` on edit, `accounts`, `contacts`.
- Classification list: `object_list`, `page_obj`, `q`, `accounts`, all five choice lists, `account_id`, current filter strings, `stats`, `export_url`; detail: `obj`, `account`, `health`, `health_history`, `hierarchy_position`, `opportunity_rollups`, `invoice_rollups`, `order_rollups`, `can_edit`; form: `form`, `is_edit`, `obj` on edit, `accounts`.
- Plan list: `object_list`, `page_obj`, `q`, `accounts`, `owners`, `status_choices`, `account_id`, `owner_id`, `status`, `next_review`, `period_from`, `period_to`, `stats`, `export_url`; detail: `obj`, `account`, `owner`, `related_opportunities`, `opportunity_rollups`, `health`, `health_history`, `tasks`, `recent_activity`, `documents`, `currency_rollups`, `coverage`, `white_space_note`, `allowed_actions`, `can_edit`; form: `form`, `is_edit`, `obj` on edit, `accounts`, `owners`, `opportunities`.
- Boards: hierarchy `accounts`, `account_rows`, `roots`, `selected_account`, `view_mode`, `view_mode_choices`, `q`, `root_id`, `parent_id`, `rollup_rows`, `stats`, `currency_rollups`, `caveats`; workspace `account`, `profile`, `classification`, `stakeholders`, `primary_contacts`, `plans`, `opportunities`, `orders`, `invoices`, `health`, `health_history`, `activities`, `tasks`, `documents`, `coverage`, `interaction_recency`, `currency_rollups`, `opportunity_rollups`, `realized_rollups`, `enrichment_events`, `white_space_note`, `caveats`; coverage `coverage_rows`, `accounts`, `role_choices`, `status_choices`, `q`, `account_id`, `role`, `status`, `stats`, `caveats`; white-space `white_space_rows`, `accounts`, `tier_choices`, `lifecycle_stage_choices`, `q`, `account_id`, `tier`, `lifecycle_stage`, `review_due`, `product_mapping_note`, `stats`, `caveats`.
- All list filters validate enum/date/FK input before ORM filtering; integer params use `as_db_int`; pagination guards prev/next; choices are exact model values.

## Boards and services

- Add a bounded, iterative, cycle-safe hierarchy reader over `AccountProfile.parent_account`; support root/parent/child/leaf/descendant modes and a safe unavailable state.
- Group opportunity/order/invoice values by verified currency; do not sum unlike currencies or `AccountProfile.annual_revenue`; Opportunity has no currency, so show an explicit unavailable/unspecified bucket.
- Workspace and coverage are read-only over canonical Parties/profiles, stakeholders, classifications, plans, opportunities, orders, invoices, health/history, tasks/activity/documents; do not create snapshot tables.
- Enrichment apply validates the allowlist and legal basis, updates `core.ContactMethod` plus the matching CRM profile projection and `core.AuditLog` in `transaction.atomic()`, and never calls a provider. Preserve manual/protected values; no raw payload or token is audited.
- Plan lifecycle verbs are state-guarded, POST-only, audited, and do not write ledger, health, inventory, or task counters.

## Templates/design system

Use `base.html` and verified classes only. Badges use `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`; stat icons use `blue`, `green`, `orange`, `purple`, `slate`. Every list has search/filter/pagination/Actions; mutable details have Actions sidebar with edit, POST+CSRF confirmed delete, and back; nullable values are guarded; FK comparisons use `|stringformat:"d"`; no multi-line `{# ... #}`. Enrichment has no form/edit/delete affordance. Product white-space pages explicitly state the missing CRM Product↔SCM Item mapping.

## Integration/verification

- Extend `models/forms/views/urls` exports, `admin.py`, `seed_sales.py`, and `LIVE_LINKS['8.3']`; do not touch catalog machinery or other live keys.
- Add exact 8.3 bullet mappings: hierarchy→`sales:account_hierarchy`; enrichment→`sales:account_workspace#enrichment`; relationship→`sales:account_coverage`; segmentation→`sales:account_classification_list`; plans→`sales:account_plan_list`; add reversing extras.
- Generate the next free Sales migration only after all files exist; it must create only the four 8.3 tables (the M2M join is implicit).
- Run `makemigrations sales`, `migrate`, `seed_sales` twice, `check`, `makemigrations --check`; then smoke every route as `admin_acme` with content assertions, junk filters, pagination, CSRF/GET action checks, and cross-tenant 404s.
- Run the full unfiltered Sales suite and relevant CRM/accounting/SCM regressions. Review/fixer/test phases remain serial and are not performed by parallel agents.

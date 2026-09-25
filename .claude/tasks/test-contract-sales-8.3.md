# Test Contract — NavERP 8.3 Contact & Account Management

- Phase: 6.1, test contract and shared factories
- App: `apps/sales`
- Namespace: `contactaccountmanagement`
- Build contract: `.claude/tasks/contract-sales-8.3.md`
- Current checkout snapshot: `749362993281f619e2c1f170e64193452cd0ac0a`
- Test settings: `config.settings_test` with SQLite `:memory:`
- No test source files are created by this step.

## 1. Scope and ownership

8.3 adds exactly four Sales models: `PartyEnrichmentEvent`, `AccountStakeholder`, `AccountClassification`, and `AccountPlan`. Account and contact identity remain `core.Party` plus `crm.AccountProfile` and `crm.ContactProfile`. Health remains `crm.HealthScore` and `crm.HealthScoreHistory`; opportunities, orders, and invoices are read-only sources. No fixture in this contract creates health, order, invoice, product-mapping, or provider-response data.

The existing 8.1 portion of `apps/sales/tests/conftest.py` is append-only. Existing 8.1 helpers, constants, and contract tests are unchanged. Every new module helper starts with `_contactaccountmanagement_`; every new fixture starts with `contactaccountmanagement`.

## 2. Shared helper contract

The following helpers are appended to `apps/sales/tests/conftest.py`:

| Helper | Required behavior |
|---|---|
| `_contactaccountmanagement_tenant_id` | Returns a tenant primary key or passes an integer through. |
| `_contactaccountmanagement_assert_same_tenant` | Asserts every supplied related row has the requested tenant. |
| `_contactaccountmanagement_user` | Creates a deterministic active user with a tenant-derived unique email and username. |
| `_contactaccountmanagement_party` | Creates a validated `core.Party` with a forced tenant and Party kind. |
| `_contactaccountmanagement_organization_party` | Creates a canonical organization Party. |
| `_contactaccountmanagement_person_party` | Creates a canonical person Party. |
| `_contactaccountmanagement_account_profile` | Creates a validated CRM `AccountProfile`; validates same-tenant organization and optional parent profile. |
| `_contactaccountmanagement_contact_profile` | Creates a validated CRM `ContactProfile`; validates same-tenant person and optional organization account. |
| `_contactaccountmanagement_consent_purpose` | Creates an active consent-basis purpose with a deterministic default code. |
| `_contactaccountmanagement_reports_to` | Creates a validated same-tenant person-to-person `core.PartyRelationship` with `kind='reports_to'`. |
| `_contactaccountmanagement_stakeholder` | Creates a valid active `AccountStakeholder` with deterministic role, influence, attitude, strength, and dates. |
| `_contactaccountmanagement_classification` | Creates a valid strategic current `AccountClassification` with rationale, effective date, and review date. |
| `_contactaccountmanagement_plan` | Creates a valid draft `AccountPlan` with an active same-tenant owner and an optional opportunity iterable. |
| `_contactaccountmanagement_enrichment_event` | Creates a valid proposed manual `PartyEnrichmentEvent`; it does not call a provider. |

There is deliberately no `_contactaccountmanagement_opportunity` helper or Opportunity fixture in this checkout. The live `crm.Opportunity` model declares `currency` and `next_step_due_date`, while the migration state at CRM `0025_alter_webhook_secret` does not contain those fields or their indexes. Creating the live model through the ORM would therefore fail on the normal migration-backed SQLite database while concurrent CRM drift is unresolved. The plan factory defaults `opportunities=()` and never fabricates an order, invoice, or currency row. Add an Opportunity factory only after the CRM migration graph is aligned, using the same namespace.

## 3. Fixture contract

The names below are the only new fixture names in the shared Sales conftest. Root fixtures `tenant_a`, `tenant_b`, `admin_user`, `admin_b`, `member_user`, `client_a`, `client_b`, and `member_client` are reused without replacement.

| Fixture | Deterministic state |
|---|---|
| `contactaccountmanagement_tenant_a` | Root Acme tenant. |
| `contactaccountmanagement_tenant_b` | Root Globex tenant. |
| `contactaccountmanagement_admin_a` | Acme tenant administrator. |
| `contactaccountmanagement_admin_b` | Globex tenant administrator. |
| `contactaccountmanagement_member_a` | Acme non-administrator. |
| `contactaccountmanagement_member_b` | Newly created Globex non-administrator. |
| `contactaccountmanagement_admin_client_a` | Logged-in Acme administrator client. |
| `contactaccountmanagement_admin_client_b` | Logged-in Globex administrator client. |
| `contactaccountmanagement_member_client_a` | Logged-in Acme member client. |
| `contactaccountmanagement_member_client_b` | Logged-in Globex member client. |
| `contactaccountmanagement_account_a` | Acme canonical organization Party. |
| `contactaccountmanagement_account_b` | Globex canonical organization Party. |
| `contactaccountmanagement_account_child_a` | Acme child organization Party for hierarchy tests. |
| `contactaccountmanagement_account_child_b` | Globex child organization Party for hierarchy tests. |
| `contactaccountmanagement_contact_a` | Acme canonical person Party. |
| `contactaccountmanagement_contact_b` | Globex canonical person Party. |
| `contactaccountmanagement_manager_a` | Acme second person for a valid reporting line. |
| `contactaccountmanagement_manager_b` | Globex second person for a valid reporting line. |
| `contactaccountmanagement_account_profile_a` | Acme `crm.AccountProfile` owned by the Acme administrator. |
| `contactaccountmanagement_account_profile_b` | Globex `crm.AccountProfile` owned by the Globex administrator. |
| `contactaccountmanagement_account_child_profile_a` | Acme child profile whose parent is the Acme canonical account. |
| `contactaccountmanagement_account_child_profile_b` | Globex child profile whose parent is the Globex canonical account. |
| `contactaccountmanagement_contact_profile_a` | Acme `crm.ContactProfile` with the Acme account as primary affiliation. |
| `contactaccountmanagement_contact_profile_b` | Globex `crm.ContactProfile` with the Globex account as primary affiliation. |
| `contactaccountmanagement_consent_purpose_a` | Active Acme consent-basis enrichment purpose. |
| `contactaccountmanagement_consent_purpose_b` | Active Globex consent-basis enrichment purpose. |
| `contactaccountmanagement_stakeholder_a` | Acme active `decision_maker` stakeholder. |
| `contactaccountmanagement_stakeholder_b` | Globex active `champion` stakeholder. |
| `contactaccountmanagement_classification_a` | Acme strategic prospect classification with review date. |
| `contactaccountmanagement_classification_b` | Globex strategic prospect classification with review date. |
| `contactaccountmanagement_plan_a` | Acme valid draft `ACPL-` plan with no opportunities. |
| `contactaccountmanagement_plan_b` | Globex valid draft `ACPL-` plan with no opportunities. |
| `contactaccountmanagement_enrichment_event_a` | Acme proposed manual organization enrichment event. |
| `contactaccountmanagement_enrichment_event_b` | Globex proposed manual organization enrichment event. |
| `contactaccountmanagement_reports_to_a` | Acme contact-to-manager reporting relationship. |
| `contactaccountmanagement_reports_to_b` | Globex contact-to-manager reporting relationship. |

All date fixtures derive from `django.utils.timezone.localdate()`. No helper uses `datetime.date.today()`.

## 4. Model contract

### 4.1 `PartyEnrichmentEvent`

Source: `apps/sales/models/ContactAccountManagement/PartyEnrichment.py`; base: `TenantEventOwned`.

Concrete field order, excluding the primary key:

`tenant, created_at, party, kind, source_kind, source_name, source_reference, status, match_confidence, changes, legal_basis_purpose, requested_by, reviewed_by, occurred_at, applied_at, idempotency_key, error_code, error_summary`

Relations:

| Field | Target | Delete | Related name | Nullable | Editable |
|---|---|---|---|---|---|
| `party` | `core.Party` | `PROTECT` | `sales_enrichment_events` | no | yes |
| `legal_basis_purpose` | `core.ConsentPurpose` | `PROTECT` | `sales_enrichment_events` | yes | yes |
| `requested_by` | `accounts.User` | `SET_NULL` | `sales_requested_enrichment_events` | yes | no |
| `reviewed_by` | `accounts.User` | `SET_NULL` | `sales_reviewed_enrichment_events` | yes | no |

Exact choices:

- `KIND_CHOICES`: `firmographic`, `contact`, `email_validation`, `phone_validation`, `social`, `employment_change`, `duplicate_check`
- `SOURCE_KIND_CHOICES`: `manual`, `provider`, `email_signature`, `linkedin`, `import`, `api`
- `STATUS_CHOICES`: `proposed`, `applied`, `rejected`, `no_match`, `failed`

Metadata and invariants:

- `match_confidence` is nullable `DecimalField(max_digits=5, decimal_places=4)` with inclusive 0..1 validators and database check constraint `sales_pee_confidence_valid`.
- `changes` is a bounded JSON object. The complete allowlist is `job_title`, `department`, `linkedin`, `work_email`, `phone`, `mobile`, `website`, `industry`, `employee_count`, and `annual_revenue`.
- Person proposals may use only `job_title`, `department`, `linkedin`, `work_email`, `phone`, and `mobile`; organization proposals may use only `website`, `industry`, `employee_count`, and `annual_revenue`.
- Every proposal value is a bounded scalar with only `value` and optional `confidence`; nested objects, arrays, booleans, non-finite confidence, credential-like text, invalid URLs/emails/phones, unsupported industries, and overlong values fail validation.
- External source kinds are every source kind except `manual`; they require an active same-tenant `ConsentPurpose`.
- The unique constraint is `(tenant, idempotency_key)` named `sales_pee_tenant_key_uniq`.
- Indexes are `sales_pee_tnt_party_idx(tenant, party, -occurred_at)`, `sales_pee_tnt_status_idx(tenant, status, -occurred_at)`, and `sales_pee_tnt_kind_idx(tenant, kind, -occurred_at)`.
- New rows start `proposed`. Direct terminal saves and evidence edits are refused. The only service transitions are proposed to applied or rejected; an applied event has `reviewed_by` and `applied_at`.
- Apply and reject services are the only decision writers. Apply validates the allowlist, Party kind, active lawful basis, protected canonical values, tenant actors, and writes canonical contact/account projections plus a sanitized audit record atomically.

### 4.2 `AccountStakeholder`

Source: `apps/sales/models/ContactAccountManagement/AccountStakeholders.py`; base: `TenantOwned`.

Concrete field order:

`tenant, created_at, updated_at, account, contact, role, influence, attitude, relationship_strength, status, valid_from, valid_to, notes`

Relations: `account -> core.Party` with `PROTECT`, related name `sales_account_stakeholders`; `contact -> core.Party` with `PROTECT`, related name `sales_stakeholder_contacts`.

Exact choices and defaults:

- `ROLE_CHOICES`: `decision_maker`, `economic_buyer`, `champion`, `influencer`, `blocker`, `technical_evaluator`, `procurement`, `end_user`, `advisor`, `other`; no default.
- `INFLUENCE_CHOICES`: `high`, `medium`, `low`, `unknown`; default `unknown`.
- `ATTITUDE_CHOICES`: `positive`, `neutral`, `negative`, `unknown`; default `unknown`.
- `RELATIONSHIP_STRENGTH_CHOICES`: `strong`, `moderate`, `weak`, `unknown`; default `unknown`.
- `STATUS_CHOICES`: `active`, `former`; default `active`.

Validation and metadata:

- Account is a different same-tenant organization; contact is a same-tenant person.
- `valid_to` cannot precede `valid_from`; either date may be null.
- Unique constraint `(tenant, account, contact, role)` is `sales_ast_tenant_account_contact_role_uniq`.
- Indexes are `sales_ast_acct_status_idx(tenant, account, status)`, `sales_ast_contact_status_idx(tenant, contact, status)`, and `sales_ast_role_attitude_idx(tenant, role, attitude)`.
- A contact may have multiple roles and multiple accounts. This model never changes `ContactProfile.account` and never writes a reporting line.

### 4.3 `AccountClassification`

Source: `apps/sales/models/ContactAccountManagement/AccountClassifications.py`; base: `TenantOwned`.

Concrete field order:

`tenant, created_at, updated_at, account, tier, lifecycle_stage, strategic_priority, revenue_potential, wallet_category, rationale, effective_on, review_due_on, classified_by`

`account` is a required OneToOne `core.Party` relation with `PROTECT` and related name `sales_account_classification`. `classified_by` is nullable `accounts.User`, `SET_NULL`, related name `sales_account_classifications`, and not editable.

Exact choices and defaults:

- `TIER_CHOICES`: `strategic`, `key`, `growth`, `nurture`; default `growth`.
- `LIFECYCLE_STAGE_CHOICES`: `prospect`, `active_customer`, `expansion_candidate`, `dormant`, `former_customer`; default `prospect`.
- `STRATEGIC_PRIORITY_CHOICES`: `high`, `medium`, `low`; default `medium`.
- `REVENUE_POTENTIAL_CHOICES`: `very_high`, `high`, `medium`, `low`, `unknown`; default `unknown`.
- `WALLET_CATEGORY_CHOICES`: `none`, `small`, `medium`, `large`, `full_wallet`; default `none`.

Validation and metadata:

- Account is a same-tenant organization and rationale is required on every write.
- `effective_on` defaults to `timezone.localdate`; `review_due_on` is nullable but required for `strategic` and `key`, and cannot precede the effective date.
- One current row is allowed per account. The explicit unique constraint is `sales_aclass_tenant_account_uniq(tenant, account)`; duplicate create redirects to edit/upsert.
- Indexes are `sales_aclass_tnt_tier_life_idx(tenant, tier, lifecycle_stage)` and `sales_aclass_prio_idx(tenant, strategic_priority, review_due_on)`.
- Classification stores human intent only. It stores no health, annual revenue, pipeline, invoice, order, or rollup value.

### 4.4 `AccountPlan`

Source: `apps/sales/models/ContactAccountManagement/AccountPlans.py`; base: `TenantNumbered`; `NUMBER_PREFIX = 'ACPL'`.

Concrete field order:

`tenant, created_at, updated_at, number, account, title, period_start, period_end, status, owner, business_drivers, objectives, strategy, strengths, weaknesses, opportunities, threats, white_space_assessment, growth_initiatives, risk_summary, next_review_on`

`related_opportunities` is a blank-allowed `ManyToManyField` to `crm.Opportunity` with related name `sales_account_plans`.

Relations: `account -> core.Party` with `PROTECT`, related name `sales_account_plans`; `owner -> accounts.User` with `PROTECT`, related name `sales_owned_account_plans`.

Exact choices and defaults:

- `STATUS_CHOICES`: `draft`, `active`, `review_due`, `completed`, `archived`; default `draft`.
- `number` is `CharField(max_length=20, editable=False)` and is generated by the Sales numbering service.
- `period_start` and `period_end` are required ordered `DateField`s.
- `next_review_on` is nullable; all narrative strategy/SWOT/growth/risk fields are optional text.

Validation and metadata:

- Account is a same-tenant organization; owner is an active same-tenant user.
- The only owner/admin service transitions are draft to active, active to review due, active or review due to completed, and draft/active/review due/completed to archived.
- Only draft plans can be deleted; non-draft plans archive.
- Unique constraint `(tenant, number)` is `sales_acpl_tenant_number_uniq`.
- Indexes are `sales_acpl_acct_status_idx(tenant, account, status)`, `sales_acpl_owner_rev_idx(tenant, owner, next_review_on)`, and `sales_acpl_stat_rev_idx(tenant, status, next_review_on)`.
- Every selected opportunity must be a same-tenant opportunity for the same account. The form, save service, and M2M signal all enforce this invariant. Because the current CRM Opportunity migration is drifted, the shared plan fixture uses no opportunity rows.

## 5. Form contract

All form constructors accept `tenant=...`; tenant-owned querysets are empty when tenant is `None`; crafted foreign IDs are rejected even if a test widens a field queryset.

| Form | Exact `base_fields` / `Meta.fields` order | Required behavior |
|---|---|---|
| `PartyEnrichmentProposalForm` | `party`, `kind`, `source_kind`, `source_name`, `source_reference`, `changes`, `legal_basis_purpose` | Same-tenant Party and active same-tenant purpose querysets; validate the exact enrichment change schema and external-purpose gate. |
| `PartyEnrichmentApplyForm` | `selected_fields`, `review_note` | Choices are limited to fields present on the event; tenant-admin gate is in the view/service. |
| `PartyEnrichmentRejectForm` | `review_note` | Required rejection reason, maximum 1000 characters. |
| `AccountStakeholderForm` | `account`, `contact`, `role`, `influence`, `attitude`, `relationship_strength`, `status`, `valid_from`, `valid_to`, `notes` | Account queryset is same-tenant organizations; contact queryset is same-tenant persons; identities disable on edit; date order and distinctness are checked. |
| `AccountClassificationForm` | `account`, `tier`, `lifecycle_stage`, `strategic_priority`, `revenue_potential`, `wallet_category`, `rationale`, `effective_on`, `review_due_on` | Same-tenant organization account; rationale and strategic/key review rules; account disables on edit; duplicate instance is handled without a 500. |
| `AccountPlanForm` | `account`, `title`, `period_start`, `period_end`, `owner`, `business_drivers`, `objectives`, `strategy`, `strengths`, `weaknesses`, `opportunities`, `threats`, `white_space_assessment`, `growth_initiatives`, `risk_summary`, `next_review_on`, `related_opportunities` | Same-tenant account and active owner; non-admin owner is forced to the actor and disabled; opportunity choices are account-dependent; M2M is revalidated after cleaning and before atomic save. |

The following system fields are never form fields: `tenant`, `id`, `created_at`, `updated_at`, `number`, `status`, `classified_by`, `requested_by`, `reviewed_by`, `occurred_at`, `applied_at`, `match_confidence`, `error_code`, and `error_summary`. `PartyEnrichmentEvent` has no ordinary edit or delete form.

## 6. URL and callback contract

The namespace is `sales`, mounted at `/sales/`. Literal `add/`, `request/`, and `export/` routes precede `<int:pk>` routes. Reverse names, paths, and callback names are exact.

| URL name | Relative path | Callback |
|---|---|---|
| `party_enrichment_list` | `enrichment-events/` | `party_enrichment_list` |
| `party_enrichment_request` | `enrichment-events/request/` | `party_enrichment_request` |
| `party_enrichment_export` | `enrichment-events/export/` | `party_enrichment_export` |
| `party_enrichment_detail` | `enrichment-events/<int:pk>/` | `party_enrichment_detail` |
| `party_enrichment_apply` | `enrichment-events/<int:pk>/apply/` | `party_enrichment_apply` |
| `party_enrichment_reject` | `enrichment-events/<int:pk>/reject/` | `party_enrichment_reject` |
| `account_stakeholder_list` | `account-stakeholders/` | `account_stakeholder_list` |
| `account_stakeholder_create` | `account-stakeholders/add/` | `account_stakeholder_create` |
| `account_stakeholder_export` | `account-stakeholders/export/` | `account_stakeholder_export` |
| `account_stakeholder_detail` | `account-stakeholders/<int:pk>/` | `account_stakeholder_detail` |
| `account_stakeholder_edit` | `account-stakeholders/<int:pk>/edit/` | `account_stakeholder_edit` |
| `account_stakeholder_delete` | `account-stakeholders/<int:pk>/delete/` | `account_stakeholder_delete` |
| `account_classification_list` | `account-classifications/` | `account_classification_list` |
| `account_classification_create` | `account-classifications/add/` | `account_classification_create` |
| `account_classification_export` | `account-classifications/export/` | `account_classification_export` |
| `account_classification_detail` | `account-classifications/<int:pk>/` | `account_classification_detail` |
| `account_classification_edit` | `account-classifications/<int:pk>/edit/` | `account_classification_edit` |
| `account_classification_delete` | `account-classifications/<int:pk>/delete/` | `account_classification_delete` |
| `account_plan_list` | `account-plans/` | `account_plan_list` |
| `account_plan_create` | `account-plans/add/` | `account_plan_create` |
| `account_plan_export` | `account-plans/export/` | `account_plan_export` |
| `account_plan_detail` | `account-plans/<int:pk>/` | `account_plan_detail` |
| `account_plan_edit` | `account-plans/<int:pk>/edit/` | `account_plan_edit` |
| `account_plan_delete` | `account-plans/<int:pk>/delete/` | `account_plan_delete` |
| `account_plan_activate` | `account-plans/<int:pk>/activate/` | `account_plan_activate` |
| `account_plan_review_due` | `account-plans/<int:pk>/review-due/` | `account_plan_review_due` |
| `account_plan_complete` | `account-plans/<int:pk>/complete/` | `account_plan_complete` |
| `account_plan_archive` | `account-plans/<int:pk>/archive/` | `account_plan_archive` |
| `account_hierarchy` | `accounts/hierarchy/` | `account_hierarchy` |
| `account_workspace_export` | `accounts/workspace/export/` | `account_workspace_export` |
| `account_workspace` | `accounts/workspace/` | `account_workspace` |
| `account_coverage` | `accounts/coverage/` | `account_coverage` |
| `account_white_space` | `accounts/white-space/` | `account_white_space` |

## 7. View context and filter contract

Every list uses page size 20. Search, valid filters, and date/FK validation happen before pagination. Invalid enum, date, and integer values are ignored or produce the view's controlled response; they must never raise a database conversion error.

### Enrichment

- `party_enrichment_list`: `object_list`, `page_obj`, `q`, `parties`, `kind_choices`, `source_kind_choices`, `status_choices`, `party_id`, `kind`, `source_kind`, `status`, `date_from`, `date_to`, `stats`, `proposal_form`, `export_url`.
- `party_enrichment_detail`: `obj`, `party`, `proposal_rows`, `canonical_values`, `can_apply`, `can_reject`, `apply_form`, `reject_form`, `audit_events`, `export_url`.
- `party_enrichment_request`, `party_enrichment_apply`, `party_enrichment_reject`, and `party_enrichment_export` render no HTML context; they redirect or return CSV.
- Enrichment list filters are `q`, `party`, `kind`, `source_kind`, `status`, `date_from`, and `date_to`; stats keys are `total`, `proposed`, `applied`, `rejected`, `no_match`, and `failed`.

### Stakeholders

- `account_stakeholder_list`: `object_list`, `page_obj`, `q`, `accounts`, `contacts`, `role_choices`, `influence_choices`, `attitude_choices`, `relationship_strength_choices`, `status_choices`, `account_id`, `contact_id`, `role`, `influence`, `attitude`, `relationship_strength`, `status`, `valid_from`, `valid_to`, `stats`, `export_url`.
- `account_stakeholder_detail`: `obj`, `account`, `contact`, `is_primary_affiliation`, `reports_to`, `related_opportunities`, `interaction_recency`, `coverage_roles`, `can_edit`.
- `account_stakeholder_create`: `form`, `is_edit`, `accounts`, `contacts`.
- `account_stakeholder_edit`: `form`, `obj`, `is_edit`, `accounts`, `contacts`.
- Stakeholder list filters are `q`, `account`, `contact`, `role`, `influence`, `attitude`, `relationship_strength`, `status`, `valid_from`, and `valid_to`; stats keys are `total`, `active`, and `former`.

### Classifications

- `account_classification_list`: `object_list`, `page_obj`, `q`, `accounts`, `tier_choices`, `lifecycle_stage_choices`, `strategic_priority_choices`, `revenue_potential_choices`, `wallet_category_choices`, `account_id`, `tier`, `lifecycle_stage`, `strategic_priority`, `revenue_potential`, `wallet_category`, `review_due`, `stats`, `export_url`, `can_edit`.
- `account_classification_detail`: `obj`, `account`, `health`, `health_history`, `hierarchy_position`, `opportunity_rollups`, `invoice_rollups`, `order_rollups`, `currency_rollups`, `can_edit`.
- `account_classification_create`: `form`, `is_edit`, `accounts`.
- `account_classification_edit`: `form`, `obj`, `is_edit`, `accounts`.
- Classification list filters are `q`, `account`, `tier`, `lifecycle_stage`, `strategic_priority`, `revenue_potential`, `wallet_category`, and `review_due`; stats keys are `total`, `strategic`, `key`, and `review_overdue`.

### Plans

- `account_plan_list`: `object_list`, `page_obj`, `q`, `accounts`, `owners`, `status_choices`, `account_id`, `owner_id`, `status`, `next_review`, `period_from`, `period_to`, `stats`, `export_url`, `can_edit_all`.
- `account_plan_detail`: `obj`, `account`, `owner`, `related_opportunities`, `opportunity_rollups`, `health`, `health_history`, `tasks`, `recent_activity`, `documents`, `currency_rollups`, `coverage`, `white_space_note`, `allowed_actions`, `can_edit`.
- `account_plan_create`: `form`, `is_edit`, `accounts`, `owners`, `opportunities`.
- `account_plan_edit`: `form`, `obj`, `is_edit`, `accounts`, `owners`, `opportunities`.
- Plan list filters are `q`, `account`, `owner`, `status`, `next_review`, `period_from`, and `period_to`; stats keys are `total`, `draft`, `active`, `review_due`, and `review_overdue`.
- Detail rollups may be empty. They must not be populated with synthetic health, order, or invoice rows.

### Boards

- `account_hierarchy`: `accounts`, `account_rows`, `roots`, `selected_account`, `view_mode`, `view_mode_choices`, `q`, `root_id`, `parent_id`, `rollup_rows`, `stats`, `currency_rollups`, `caveats`; view modes are `tree`, `roots`, `leaves`, `parent`, and `descendants`.
- `account_workspace`: `account`, `profile`, `classification`, `stakeholders`, `primary_contacts`, `plans`, `opportunities`, `orders`, `invoices`, `health`, `health_history`, `activities`, `tasks`, `documents`, `coverage`, `interaction_recency`, `currency_rollups`, `opportunity_rollups`, `realized_rollups`, `enrichment_events`, `white_space_note`, `caveats`.
- `account_coverage`: `coverage_rows`, `accounts`, `role_choices`, `status_choices`, `q`, `account_id`, `role`, `status`, `stats`, `caveats`; coverage filters are `q`, `account`, `role`, and `status`.
- `account_white_space`: `white_space_rows`, `accounts`, `tier_choices`, `lifecycle_stage_choices`, `q`, `account_id`, `tier`, `lifecycle_stage`, `review_due`, `product_mapping_note`, `stats`, `caveats`; filters are `q`, `account`, `tier`, `lifecycle_stage`, and `review_due`.
- `account_workspace_export` has no HTML context and returns CSV. A missing account is a controlled 404/empty response; a foreign or malformed account ID is not allowed to select the first account.

## 8. Authorization and security matrix

- Anonymous GETs to ordinary login-protected pages and form routes redirect to login. For action routes whose outer decorator is `@require_POST`, anonymous GET is 405 and anonymous POST redirects to login; the same method-order rule applies to members and admins.
- Tenant-less authenticated users may read empty tenant-scoped lists/boards where the view permits it, cannot see tenant rows, and cannot write into a tenant. A tenant-less tenant-admin flag does not bypass `tenant=request.tenant` scoping.
- Login-only reads include all enrichment pages, stakeholder pages, classification list/detail/export, plan list/detail/export, and all boards.
- `party_enrichment_apply`, classification create/edit/delete, and plan delete are tenant-admin gated. Member GET is 403 for classification create/edit and 405 for the outer-`@require_POST` action routes; member POST is 403 on all of these. Administrator GET on an action route is 405.
- Enrichment request and reject, stakeholder create/edit/delete, plan create, and plan lifecycle verbs are login-required; the service layer still applies tenant, Party-kind, and ownership checks.
- A member may read the workspace but may create a plan only for themselves; a member cannot edit, activate, review, complete, archive, or delete another member's plan. A tenant administrator may manage the workspace plan.
- Stakeholder create/edit/delete are not tenant-admin-only in the current 8.3 implementation; their tenant, Party-kind, distinctness, and CSRF rules still apply.
- Action verbs are POST-only and CSRF-protected. CRUD create/edit form routes accept GET for the form and POST for the write; no GET request changes state.
- Cross-tenant detail, edit, delete, apply, reject, and lifecycle IDs return 404 and leave the target row unchanged. Crafted foreign Party, user, purpose, account, contact, opportunity, and M2M IDs never create or mutate a row.
- Hierarchy visibility never widens access. Parent/child rollups remain tenant-scoped and cycle-safe.
- Reporting lines are same-tenant person-to-person, non-self relationships; a foreign manager cannot appear in `reports_to`.
- Enrichment accepts only bounded allowlisted data, never executes a provider or network call, never stores raw payloads/tokens/credentials, sanitizes references/errors, and does not replay a decided event.
- CSV cells beginning with spreadsheet formula characters are neutralized, exports are capped at 5,000 rows, and export audit metadata contains no raw enrichment payload or sensitive free text.

## 9. Expected four test lanes

Every test function is named `test_contactaccountmanagement_*`. Every module-level helper is named `_contactaccountmanagement_*`.

### `test_contactaccountmanagement_models.py`

1. `test_contactaccountmanagement_model_fields_choices_constraints_and_indexes` — exact field order, choices, relation metadata, constraints, indexes, `ACPL` prefix, and SQLite model loading.
2. `test_contactaccountmanagement_enrichment_allowlist_and_party_kind_validation` — person and organization allowlists, scalar bounds, confidence bounds, URL/email/phone/industry validation, and hostile nested JSON rejection.
3. `test_contactaccountmanagement_enrichment_source_purpose_and_confidence_validation` — external source requires an active same-tenant purpose; inactive, foreign, and malformed confidence values fail.
4. `test_contactaccountmanagement_enrichment_is_append_only_and_review_lifecycle` — proposed creation, immutable evidence, proposed-to-applied/rejected service transitions, terminal replay refusal, applied timestamp, and sanitized review state.
5. `test_contactaccountmanagement_stakeholder_identity_kind_tenant_and_date_validation` — organization/person kind, distinct Party IDs, same tenant, and ordered validity dates.
6. `test_contactaccountmanagement_stakeholder_unique_account_contact_role` — duplicate identity is rejected while the same role can exist for another account or tenant.
7. `test_contactaccountmanagement_classification_current_row_and_review_rules` — OneToOne current row, rationale, strategic/key review date, effective/review order, and duplicate upsert behavior.
8. `test_contactaccountmanagement_plan_number_owner_period_and_tenant_rules` — generated number, ordered period, active same-tenant owner, draft default, and non-draft archive/delete rules.
9. `test_contactaccountmanagement_plan_opportunity_link_contract` — pin the `related_opportunities` target, blank M2M behavior, and same-account/same-tenant validation; run an actual Opportunity integration case only after CRM migration drift is resolved.
10. `test_contactaccountmanagement_hierarchy_reader_is_cycle_safe_and_bounded` — root/leaf/parent/descendant metadata, depth bound, cycle unavailable state, and no authorization widening.
11. `test_contactaccountmanagement_rollups_keep_unspecified_opportunity_currency_separate` — no unlike-currency sum, no `AccountProfile.annual_revenue` sum, and explicit empty/unavailable buckets when no order/invoice data exists.

### `test_contactaccountmanagement_forms.py`

1. `test_contactaccountmanagement_forms_expose_exact_fields_and_exclusions` — exact `base_fields`/`Meta.fields` order and absence of tenant/system fields.
2. `test_contactaccountmanagement_forms_use_exact_closed_choices` — every choice list matches its model constant, including selected enrichment fields.
3. `test_contactaccountmanagement_forms_scope_party_user_and_purpose_querysets` — same-tenant organization/person, active users, active purposes, and empty querysets for `tenant=None`.
4. `test_contactaccountmanagement_enrichment_form_rejects_hostile_changes_and_missing_external_basis` — arbitrary JSON, nested instructions, invalid values, and missing external purpose.
5. `test_contactaccountmanagement_stakeholder_form_rejects_foreign_kind_same_and_reversed_dates` — narrowed and deliberately widened foreign querysets, same Party rejection, and date order.
6. `test_contactaccountmanagement_classification_form_requires_rationale_and_review_date` — all tier/lifecycle choices, rationale, strategic/key review, and duplicate edit behavior.
7. `test_contactaccountmanagement_plan_form_enforces_owner_period_and_account_dependent_choices` — member owner narrowing, same-tenant account, ordered period, and account-dependent opportunity queryset.
8. `test_contactaccountmanagement_plan_form_rejects_foreign_m2m_and_crafted_ids` — foreign and cross-account links are rejected without a partial save; use a migration-safe opportunity only when available.
9. `test_contactaccountmanagement_edit_forms_disable_identity_fields` — stakeholder/classification account identity and plan account identity remain locked on edit.
10. `test_contactaccountmanagement_forms_do_not_expose_sensitive_or_derived_fields` — no enrichment actors/status/timestamps, no classified actor, no plan number/status, and no raw provider payload field.

### `test_contactaccountmanagement_views.py`

1. `test_contactaccountmanagement_routes_render_templates_with_authenticated_content` — all 33 routes reverse, use the expected template or response type, and contain the canonical account/contact/plan token where applicable.
2. `test_contactaccountmanagement_view_context_keys_match_contract` — assert every exact list/detail/form/board key set in this contract; a 200 response with a missing key is a failure.
3. `test_contactaccountmanagement_enrichment_list_filters_search_pagination_and_export` — party/kind/source/status/date filters, valid and junk parameters, page 1/page 2, and export URL/filter preservation.
4. `test_contactaccountmanagement_enrichment_detail_supports_proposal_apply_and_reject` — proposal form is visible, canonical current values render, admin apply and member reject are state-guarded, and decided events do not replay.
5. `test_contactaccountmanagement_stakeholder_crud_and_detail_context` — list/create/detail/edit/delete, primary-affiliation distinction, reporting line, opportunity/interaction/capability context, and no cross-tenant rows.
6. `test_contactaccountmanagement_classification_crud_duplicate_upsert_and_detail_rollups` — admin create/edit/delete, duplicate create redirect, detail health/rollup context remains honest when empty.
7. `test_contactaccountmanagement_plan_crud_owner_policy_and_lifecycle` — create/edit/delete rules, owner/admin controls, activate/review-due/complete/archive transitions, archived read-only behavior, and atomic M2M handling.
8. `test_contactaccountmanagement_plan_list_filters_and_detail_evidence` — account/owner/status/review/period/search filters, pagination, related opportunity context, and empty health/task/document panels without fabricated rows.
9. `test_contactaccountmanagement_hierarchy_workspace_coverage_and_white_space_boards` — root/descendant views, selected account 404s, coverage derived from stakeholders plus primary affiliation, qualitative white-space note, and currency-separated rollups.
10. `test_contactaccountmanagement_exports_are_filtered_capped_and_csv_safe` — exact headers, filter parity, 5,000-row cap, formula neutralization, and safe audit metadata.
11. `test_contactaccountmanagement_views_never_fabricate_health_order_or_invoice_evidence` — missing canonical sources render empty/None/unavailable states and never insert rows.

### `test_contactaccountmanagement_security.py`

1. `test_contactaccountmanagement_anonymous_requests_redirect_to_login` — every route is protected and no state changes.
2. `test_contactaccountmanagement_tenantless_user_cannot_see_or_write_tenant_rows` — empty reads, dashboard redirect behavior where applicable, and no cross-tenant writes.
3. `test_contactaccountmanagement_admin_only_routes_reject_members` — enrichment apply and classification/plan privileged writes return 403 for members.
4. `test_contactaccountmanagement_plan_owner_and_admin_policy` — members cannot mutate another owner’s plan; admins can; archived plans remain read-only.
5. `test_contactaccountmanagement_cross_tenant_detail_edit_action_and_board_ids_are_404` — no IDOR through any list/detail/action/workspace/board parameter.
6. `test_contactaccountmanagement_crafted_foreign_fk_payloads_are_rejected_without_mutation` — Party, account, contact, user, purpose, owner, and relationship IDs remain tenant-scoped.
7. `test_contactaccountmanagement_post_only_routes_require_post_and_csrf` — administrator GET is 405; enforced-CSRF POST is 403; PUT/DELETE are refused.
8. `test_contactaccountmanagement_enrichment_hostile_input_cannot_execute_or_leak` — injection-like text, model paths, credentials, oversized JSON, non-finite confidence, provider absence, and no outbound call.
9. `test_contactaccountmanagement_enrichment_apply_is_atomic_and_protects_canonical_values` — contact method/profile/audit behavior, protected values, legal-basis recheck, and rollback on a failed selected field.
10. `test_contactaccountmanagement_hierarchy_and_reporting_lines_do_not_cross_tenants` — parent cycles, foreign parents, foreign managers, self relationships, and hierarchy visibility are rejected or unavailable.
11. `test_contactaccountmanagement_plan_m2m_cannot_cross_tenant_or_account` — use only a migration-safe opportunity when one exists; otherwise assert the structural/save-service contract and skip only the unavailable integration case.
12. `test_contactaccountmanagement_mass_assignment_cannot_set_tenant_status_number_or_actors` — posted tenant, status, number, classified_by, requested_by, reviewed_by, and timestamps do not change server-owned state.
13. `test_contactaccountmanagement_csv_and_audit_outputs_are_safe` — formula prefixes are neutralized; raw provider payloads, credentials, and sensitive free text are absent from export/audit evidence.
14. `test_contactaccountmanagement_duplicate_and_race_guarded_writes_are_idempotent` — enrichment replay, classification upsert, stakeholder uniqueness, plan number allocation, and lifecycle retries do not duplicate rows.

## 10. Test execution gate

Run a collection/import check before writing the four lane files:

```text
$env:DJANGO_SETTINGS_MODULE='config.settings_test'; & 'venv\Scripts\python.exe' -m pytest --collect-only -q apps/sales/tests --nomigrations -p no:cacheprovider
```

After all four lanes exist, run the full unfiltered `apps/sales/tests` suite with the isolated settings. Do not use a `-k` filter for the final gate. If the CRM Opportunity migration drift is resolved, add the namespaced opportunity factory and replace the conditional M2M integration case with a real row; do not reuse an 8.1 helper because later sub-modules must not share namespaces.

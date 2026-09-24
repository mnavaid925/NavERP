# Contract — Sales 8.2 Opportunity & Pipeline Management

Date: 2026-09-24
BASE: `b18d08fbca4a38eabf9e444b025fb9c4eba4bd34`
Research: `.claude/tasks/research-sales-8.2.md` (`2903072e`)

## Scope and ownership

Build only Module 8 sub-module 8.2 by extending the `apps.sales` app that a concurrent 8.1 session is building.

- The 8.2 entity modules are created unexported from the top-level Sales packages until 8.1 has generated and committed its `0001_initial` migration. This prevents 8.1's `makemigrations sales` from capturing 8.2 models.
- Do not edit 8.1-owned shared files during the build: `models/__init__.py`, `forms/__init__.py`, `views/__init__.py`, `urls/__init__.py`, `admin.py`, `services.py`, `seed_sales.py`, settings, root URL wiring, navigation, README, todo, or the 8.1 skill/review files.
- 8.2 owns new flat domain modules `opportunity_services.py` and `opportunity_analytics.py`; it does not rewrite 8.1's `services.py`.
- `crm.Opportunity` remains the canonical deal aggregate and CRM remains its create/edit/delete surface.
- `crm.OpportunitySplit` remains the only revenue/overlay credit mechanism.
- Reuse CRM activity, quote, contract, territory and quota models as read-only context.
- Reuse `core.Party`, `core.OrgUnit`, `core.Document`, `core.AuditLog`, `accounts.User` and global `accounting.Currency`.
- Do not create a second opportunity, party, activity, task, document, currency, product, quote, order, ledger, approval engine, health score, or deal ACL.
- Build four entity groups only: pipeline configuration/placement, team membership, competitive intelligence, and win/loss outcomes.
- No 8.1 or later-Sales models, routes or overview page.
- `templates/sales/overview.html` is reserved for 8.1 and must not be created or changed by 8.2.

## Build order

1. Freeze this contract.
2. Build only disjoint 8.2 package directories and files while 8.1 is uncommitted; do not export them yet.
3. Wait until 8.1 commits `sales/migrations/0001_initial.py`, then claim 8.2's next Sales migration number.
4. Build `OpportunityPipeline` completely.
5. Build `OpportunityTeams` completely.
6. Build `CompetitiveIntelligence` completely.
7. Build `OpportunityOutcomes` completely.
8. Build shared workspace, board, visibility and health views.
9. Add read-only analytics and transition services.
10. Add the two CRM Opportunity fields and compatibility guards.
11. Integrate exports, admin, seeder, navigation and URLs after re-reading each shared 8.1 file.
12. Generate the next Sales migration, migrate, seed twice and run checks.
13. Smoke, review, fix, test and document.

## Existing app compatibility

The concurrent 8.1 build already owns the app scaffold and these shared files. Reuse them after they are committed; do not recreate or rewrite them from this contract.

Before 8.1's migration is committed, 8.2 may create only its own entity-package files, entity-package `__init__.py` files, `opportunity_services.py`, `opportunity_analytics.py`, and templates. Those modules must not be imported by the top-level Sales packages yet, so Django does not register 8.2 models in 8.1's `0001_initial`.

After 8.1 is committed:

- reuse `apps/sales/models/_base.py` rather than changing it;
- surgically extend 8.1's form/view common imports only if 8.2 genuinely needs a missing toolkit symbol;
- append 8.2 re-exports and URL concatenation to the existing package initializers;
- append 8.2 seeder rows to the existing `seed_sales.py` rather than creating another seed command;
- claim the next Sales migration number only after 8.1's `0001_initial` is on disk.

`SalesConfig.name = "apps.sales"`.

`models/_base.py` remains 8.1-owned. Its `TenantOwned` and `TenantNumbered` bases are the 8.2 bases; `TenantNumbered` already uses per-tenant `next_number` and a five-attempt retry.

`forms/_common.py` and `views/_common.py` remain 8.1-owned. 8.2 entity forms/views may import their existing helpers and must use 8.2-prefixed helper names.

Package `__init__.py` files re-export every public model, form and view only at 8.2 integration. `urls/__init__.py` retains `app_name = "sales"` and appends every 8.2 URL module without rewriting 8.1 routes.

## Pipeline group

### `Pipeline`

File: `apps/sales/models/OpportunityPipeline/Pipelines.py`

Base: `TenantNumbered`, `NUMBER_PREFIX = "PIPE"`.

| Field | Contract |
|---|---|
| `name` | `CharField(max_length=255)` |
| `description` | `TextField(blank=True)` |
| `is_default` | `BooleanField(default=False)` |
| `is_active` | `BooleanField(default=True)` |

Inherited: `tenant`, `number`, `created_at`, `updated_at`.

Meta:

- ordering: `["-is_default", "name", "-created_at"]`
- unique: `("tenant", "number")`
- indexes: `(tenant, is_active)`, `(tenant, is_default)`

Rules:

- `__str__` returns `number · name`.
- At most one active default per tenant.
- Every active pipeline has at least one active open stage, exactly one active won stage and exactly one active lost stage.
- A pipeline with any placement cannot be deleted.
- A pipeline with open placements cannot be deactivated.
- Creating or activating a pipeline provisions valid baseline stages atomically.
- Selecting a default clears the previous default atomically.

### `PipelineStage`

Base: `TenantOwned`.

| Field | Contract |
|---|---|
| `pipeline` | FK `sales.Pipeline`, `CASCADE`, `related_name="stages"` |
| `name` | `CharField(max_length=120)` |
| `code` | `SlugField(max_length=40)` |
| `sequence` | `PositiveIntegerField(default=1)`, min 1 |
| `stage_kind` | choices `open`, `won`, `lost`; default `open` |
| `crm_stage_key` | CRM Opportunity stage choice |
| `probability` | `PositiveSmallIntegerField(default=10)`, 0–100 |
| `forecast_category` | CRM Opportunity forecast-category choice; default `pipeline` |
| `entry_guidance` | `TextField(blank=True)` |
| `exit_guidance` | `TextField(blank=True)` |
| `entry_criteria` | `JSONField(default=list, blank=True)` |
| `exit_criteria` | `JSONField(default=list, blank=True)` |
| `target_days` | nullable `PositiveSmallIntegerField`, 1–3650 |
| `is_active` | `BooleanField(default=True)` |

Choices:

```python
STAGE_KIND_CHOICES = [("open", "Open"), ("won", "Won"), ("lost", "Lost")]
CRM_STAGE_KEY_CHOICES = [
    ("prospecting", "Prospecting"),
    ("qualification", "Qualification"),
    ("proposal", "Proposal"),
    ("negotiation", "Negotiation"),
    ("closed_won", "Closed Won"),
    ("closed_lost", "Closed Lost"),
]
FORECAST_CATEGORY_CHOICES = [
    ("omitted", "Omitted"),
    ("pipeline", "Pipeline"),
    ("best_case", "Best Case"),
    ("commit", "Commit"),
    ("closed", "Closed"),
]
```

Integrity:

- open stage: open CRM key and probability 1–99;
- won stage: `closed_won`, probability 100, category `closed`;
- lost stage: `closed_lost`, probability 0, category `closed`;
- code lowercased;
- criteria lists contain at most 20 unique-key objects with exactly `key` and `label`;
- criterion allowlist: `account`, `primary_contact`, `amount`, `close_date`, `next_step`, `next_step_due_date`, `owner`, `active_team_member`;
- label is 1–120 characters;
- no arbitrary expression evaluation;
- a referenced stage cannot be deleted, deactivated, or have `stage_kind`, `crm_stage_key`, `probability` or `forecast_category` changed.

Meta:

- ordering: `["pipeline", "sequence", "id"]`
- unique: `("tenant", "pipeline", "code")`
- indexes: `(tenant, pipeline, sequence)`, `(tenant, stage_kind, is_active)`

### `OpportunityPipelinePlacement`

Base: `TenantOwned`.

| Field | Contract |
|---|---|
| `opportunity` | `OneToOneField("crm.Opportunity", CASCADE, related_name="sales_pipeline_placement")` |
| `pipeline` | FK `sales.Pipeline`, `PROTECT`, `related_name="placements"` |
| `current_stage` | FK `sales.PipelineStage`, `PROTECT`, `related_name="current_placements"` |
| `probability_override` | nullable 0–100 integer |
| `stage_entered_at` | `DateTimeField(default=timezone.now, editable=False)` |

The row stores current placement only. It never copies name, account, amount, close date, owner, status, or weighted value.

Validation:

- opportunity, pipeline and stage have the same tenant;
- current stage belongs to the selected pipeline and is active;
- won override must be 100 and lost override must be 0;
- `effective_probability` returns override when set, otherwise stage probability.

Meta:

- ordering: `["-updated_at", "-id"]`
- indexes: `(tenant, opportunity)`, `(tenant, pipeline)`

### Baseline stages

| Code | Name | Sequence | Kind | CRM key | Probability | Category | Target days |
|---|---|---:|---|---|---:|---|---:|
| `prospecting` | Prospecting | 10 | open | prospecting | 10 | pipeline | 14 |
| `qualification` | Discovery / Qualification | 20 | open | qualification | 30 | pipeline | 21 |
| `proposal` | Proposal | 30 | open | proposal | 60 | best_case | 21 |
| `negotiation` | Negotiation | 40 | open | negotiation | 80 | commit | 14 |
| `closed_won` | Closed Won | 50 | won | closed_won | 100 | closed | null |
| `closed_lost` | Closed Lost | 60 | lost | closed_lost | 0 | closed | null |

Baseline exit criteria:

- prospecting: account, primary contact;
- qualification: amount, close date;
- proposal: next step, next-step due date.

### Pipeline forms

`PipelineForm.Meta.fields = ["name", "description", "is_default", "is_active"]`.

`PipelineStageForm.Meta.fields = ["pipeline", "name", "code", "sequence", "stage_kind", "crm_stage_key", "probability", "forecast_category", "entry_guidance", "exit_guidance", "entry_criteria", "exit_criteria", "target_days", "is_active"]`.

`PipelineStageForm` renders criteria as fixed checkbox choices and converts selected keys to the canonical `{key, label}` JSON shape. It scopes `pipeline` to the tenant and locks that field on edit.

`PipelineStageOrderForm` has one field, `ordered_stage_ids`; submitted IDs must exactly match the current pipeline stage set.

`OpportunityPipelinePlacementForm.Meta.fields = ["opportunity", "pipeline", "current_stage", "probability_override"]`; all tenant-owned FKs are scoped and cross-tenant submissions fail validation.

Forms exclude tenant, numbers, system timestamps and derived values.

## Team group

### `OpportunityTeamMember`

File: `apps/sales/models/OpportunityTeams/OpportunityTeams.py`

Base: `TenantNumbered`, `NUMBER_PREFIX = "OTM"`.

| Field | Contract |
|---|---|
| `opportunity` | FK `crm.Opportunity`, `CASCADE`, `related_name="sales_team_members"` |
| `user` | FK `AUTH_USER_MODEL`, `CASCADE` |
| `org_unit` | nullable FK `core.OrgUnit`, `SET_NULL` |
| `role` | team role choice |
| `responsibility` | `TextField(blank=True)` |
| `is_active` | `BooleanField(default=True)` |

Roles:

```python
[("co_owner", "Co-Owner"), ("collaborator", "Collaborator"),
 ("sales_support", "Sales Support"), ("solution_consultant", "Solution Consultant"),
 ("executive_sponsor", "Executive Sponsor"), ("approver", "Approver"),
 ("observer", "Observer")]
```

Meta:

- ordering: `["is_active", "role", "id"]`
- unique: `("tenant", "opportunity", "user", "role")`
- indexes: `(tenant, opportunity, is_active)`, `(tenant, user)`

Opportunity, user and OrgUnit tenant equality is required. A new membership requires an active user. `co_owner` is operational only and creates no split or authorization grant.

`OpportunityTeamMemberForm.Meta.fields = ["user", "org_unit", "role", "responsibility", "is_active"]`. The view supplies opportunity and tenant. User and OrgUnit querysets are same-tenant; user choices are active.

Team actions are inline workspace routes, not a second list register.

## Competitive intelligence group

### `CompetitorProfile`

File: `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py`

Base: `TenantNumbered`, `NUMBER_PREFIX = "CMP"`.

| Field | Contract |
|---|---|
| `party` | `OneToOneField("core.Party", CASCADE, related_name="sales_competitor_profile")` |
| `aliases` | `TextField(blank=True)` |
| `website_url` | `URLField(max_length=500, blank=True)` |
| `description` | `TextField(blank=True)` |
| `market_positioning` | `TextField(blank=True)` |
| `strengths` | `TextField(blank=True)` |
| `weaknesses` | `TextField(blank=True)` |
| `differentiators` | `TextField(blank=True)` |
| `objection_handling` | `TextField(blank=True)` |
| `last_reviewed_on` | nullable `DateField` |
| `is_active` | `BooleanField(default=True)` |

Meta: tenant number unique; index `(tenant, is_active)`; ordering by Party name.

The Party must be a same-tenant organization. All profile text is plain escaped text. A referenced profile cannot be deleted.

### `OpportunityCompetitor`

Base: `TenantOwned`.

| Field | Contract |
|---|---|
| `opportunity` | FK `crm.Opportunity`, `CASCADE`, `related_name="sales_competitors"` |
| `competitor_profile` | FK `sales.CompetitorProfile`, `PROTECT` |
| `relationship` | relationship choice |
| `is_primary` | `BooleanField(default=False)` |
| `pricing_notes` | `TextField(blank=True)` |
| `deal_notes` | `TextField(blank=True)` |
| `positioning_notes` | `TextField(blank=True)` |

Relationships: `identified`, `evaluating`, `shortlisted`, `preferred`, `incumbent`, `eliminated`, `lost_to`, `beaten`, `withdrew`.

Meta: unique `(tenant, opportunity, competitor_profile)`; indexes `(tenant, opportunity, relationship)` and `(tenant, opportunity, is_primary)`.

Opportunity and profile tenants must match. Setting one primary link clears the previous primary under a transaction and lock.

### Competitive forms

`CompetitorProfileForm.Meta.fields` includes all profile fields above. Party choices are same-tenant organizations.

`OpportunityCompetitorForm.Meta.fields = ["competitor_profile", "relationship", "is_primary", "pricing_notes", "deal_notes", "positioning_notes"]`. The view supplies opportunity and tenant; profile choices are active and same-tenant.

## Outcomes group

### `WinLossReason`

File: `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py`

Base: `TenantNumbered`, `NUMBER_PREFIX = "WLR"`.

| Field | Contract |
|---|---|
| `code` | `SlugField(max_length=40)` |
| `name` | `CharField(max_length=120)` |
| `description` | `TextField(blank=True)` |
| `sequence` | `PositiveIntegerField(default=1)` |
| `result` | `won`, `lost`, `both` |
| `category` | price, product_fit, timing, competition, relationship, authority, budget, no_decision, other |
| `is_active` | `BooleanField(default=True)` |

Meta: unique `(tenant, number)` and `(tenant, code)`; indexes `(tenant, result, is_active)` and `(tenant, category, is_active)`.

`WinLossReasonForm.Meta.fields = ["code", "name", "description", "sequence", "result", "category", "is_active"]`. Configuration writes are tenant-admin-only. A referenced reason cannot be deleted.

### `OpportunityOutcome`

Base: `TenantNumbered`, `NUMBER_PREFIX = "OUT"`. Append-only.

| Field | Contract |
|---|---|
| `opportunity` | FK `crm.Opportunity`, `CASCADE`, `related_name="sales_outcomes"` |
| `result` | `won` or `lost` |
| `reason` | FK `sales.WinLossReason`, `PROTECT` |
| `competitor_link` | nullable FK `sales.OpportunityCompetitor`, `SET_NULL` |
| `notes` | `TextField(blank=True)` |
| `closed_at` | `DateTimeField(default=timezone.now, editable=False)` |
| `recorded_by` | nullable FK `AUTH_USER_MODEL`, `SET_NULL`, `editable=False` |

Meta: tenant number unique; indexes `(tenant, result, closed_at)`, `(tenant, opportunity, closed_at)`, `(tenant, reason)`.

Validation:

- opportunity, reason and optional competitor link are same-tenant;
- reason result is `both` or equals outcome result;
- competitor relationships `lost_to` and `beaten` require a lost outcome;
- a won outcome cannot carry a lost competitor relationship;
- outcomes have no create/edit/delete form or route;
- only the transition service writes outcomes; reopening preserves history.

`OpportunityTransitionForm` is a plain form with `target_stage`, `reason`, `competitor_link`, and `notes`. A close target requires a compatible active reason. Open transitions make reason optional. Notes are at most 4000 characters.

## Views and routes

All read views are `@login_required`; configuration writes are `@tenant_admin_required`; all mutations are POST-only, CSRF-protected and audited. State verbs use `AuditLog.action = update` and put the operation name in `changes["operation"]`.

### Pipeline routes

| Path | Name | Permission |
|---|---|---|
| `opportunity/pipelines/` | `sales:opportunity_pipeline_list` | login |
| `opportunity/pipelines/add/` | `sales:opportunity_pipeline_create` | tenant admin |
| `opportunity/pipelines/<int:pk>/` | `sales:opportunity_pipeline_detail` | login |
| `opportunity/pipelines/<int:pk>/edit/` | `sales:opportunity_pipeline_edit` | tenant admin |
| `opportunity/pipelines/<int:pk>/delete/` | `sales:opportunity_pipeline_delete` | tenant admin, POST |
| `opportunity/pipelines/<int:pk>/stages/` | `sales:opportunity_pipeline_stages` | login; POST reorders |
| `opportunity/pipelines/<int:pk>/stages/add/` | `sales:opportunity_pipeline_stage_create` | tenant admin |
| `opportunity/pipelines/<int:pk>/stages/reorder/` | `sales:opportunity_pipeline_stage_reorder` | tenant admin, POST |
| `opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/edit/` | `sales:opportunity_pipeline_stage_edit` | tenant admin |
| `opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/delete/` | `sales:opportunity_pipeline_stage_delete` | tenant admin, POST |
| `opportunity/pipelines/<int:pk>/set-default/` | `sales:opportunity_pipeline_set_default` | tenant admin, POST |
| `opportunity/board/` | `sales:opportunity_pipeline_board` | login |
| `opportunity/visibility/` | `sales:opportunity_pipeline_visibility` | login |

List filters: `q`, `active`. Integer filters use `as_db_int` or an equivalent guarded parser before pagination.

Contexts:

- list: `object_list`, `page_obj`, `q`, `active`, `active_choices`, `stats`;
- detail: `obj`, `stages`, `placement_count`, `open_placement_count`, `can_edit`;
- create/edit: `form`, `is_edit`, and `obj` on edit;
- stage editor: `pipeline`, `stages`, `stage_form`, `reorder_form`, `stage_kind_choices`, `crm_stage_choices`, `forecast_choices`;
- stage form: `pipeline`, `form`, `is_edit`, `stage` on edit, and the three choice lists;
- board: `pipelines`, `selected_pipeline`, `columns`, `unplaced_opportunities`, `summary_rows`, `currency_totals`, `health_counts`, `owner_users`, `territories`, `health_choices`, `pipeline_id`, `owner_id`, `territory_id`, `health`, `currency`;
- visibility: board contexts plus `stage_age_rows`, `win_loss_rows`, `competitor_rows`, `date_from`, `date_to`.

Each board column row has `stage`, `stage_id`, `label`, `value`, `sequence`, `count`, `amount`, `weighted_amount`, `stale_count`, `opportunities`.

### Workspace routes

| Path | Name | Permission |
|---|---|---|
| `opportunity/` | `sales:opportunity_workspace_list` | login |
| `opportunity/workspace/<int:opportunity_pk>/` | `sales:opportunity_workspace_detail` | login |
| `opportunity/workspace/<int:opportunity_pk>/place/` | `sales:opportunity_place` | login |
| `opportunity/workspace/<int:opportunity_pk>/unplace/` | `sales:opportunity_unplace` | login, POST |
| `opportunity/workspace/<int:opportunity_pk>/transition/` | `sales:opportunity_transition` | login, POST |

Workspace list filters: `q`, `health`, `owner`, `territory`, `pipeline`. Context: `opportunities`, `page_obj`, `q`, `health`, `owner_id`, `territory_id`, `pipeline_id`, `pipelines`, `owners`, `territories`, `health_choices`, `health_counts`, `stats`.

Workspace detail context: `opportunity`, `placement`, `placement_form`, `pipelines`, `stages`, `health`, `health_status`, `health_factors`, `health_stage_age_days`, `health_target_days`, `last_activity_at`, `team_members`, `team_member_form`, `competitor_links`, `competitor_form`, `competitor_profiles`, `closure_form`, `outcomes`, `win_loss_reasons`, `tasks`, `communications`, `events`, `contracts`, `documents`, `audit_entries`, `activity_timeline`, `crm_edit_url`, `can_edit_crm`.

Each timeline row has `kind`, `at`, `title`, `detail`, `url`.

Placement context: `opportunity`, `placement`, `form`, `pipelines`, `stages`, `is_edit`.

### Team routes

| Path | Name |
|---|---|
| `opportunity/workspace/<int:opportunity_pk>/team/add/` | `sales:opportunity_team_member_add` |
| `opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/edit/` | `sales:opportunity_team_member_edit` |
| `opportunity/workspace/<int:opportunity_pk>/team/<int:member_pk>/remove/` | `sales:opportunity_team_member_remove` |

Add/edit context: `opportunity`, `form`, `is_edit`, `users`, `org_units`, and `obj` on edit. Remove is POST-only and redirects to the workspace.

### Competitor routes

| Path | Name | Permission |
|---|---|---|
| `opportunity/competitors/` | `sales:opportunity_competitor_profile_list` | login |
| `opportunity/competitors/add/` | `sales:opportunity_competitor_profile_create` | tenant admin |
| `opportunity/competitors/<int:pk>/` | `sales:opportunity_competitor_profile_detail` | login |
| `opportunity/competitors/<int:pk>/edit/` | `sales:opportunity_competitor_profile_edit` | tenant admin |
| `opportunity/competitors/<int:pk>/delete/` | `sales:opportunity_competitor_profile_delete` | tenant admin, POST |
| `opportunity/workspace/<int:opportunity_pk>/competitors/add/` | `sales:opportunity_competitor_link_add` | login |
| `opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/edit/` | `sales:opportunity_competitor_link_edit` | login |
| `opportunity/workspace/<int:opportunity_pk>/competitors/<int:competitor_pk>/remove/` | `sales:opportunity_competitor_link_remove` | login, POST |

Profile list filters: `q`, `active`; context `object_list`, `page_obj`, `q`, `active`, `active_choices`, `stats`. Detail adds `opportunity_links`. Form context adds `parties` or `competitor_profiles` as applicable.

### Win/loss reason routes

| Path | Name | Permission |
|---|---|---|
| `opportunity/win-loss-reasons/` | `sales:opportunity_win_loss_reason_list` | login |
| `opportunity/win-loss-reasons/add/` | `sales:opportunity_win_loss_reason_create` | tenant admin |
| `opportunity/win-loss-reasons/<int:pk>/` | `sales:opportunity_win_loss_reason_detail` | login |
| `opportunity/win-loss-reasons/<int:pk>/edit/` | `sales:opportunity_win_loss_reason_edit` | tenant admin |
| `opportunity/win-loss-reasons/<int:pk>/delete/` | `sales:opportunity_win_loss_reason_delete` | tenant admin, POST |

List filters: `q`, `result`, `category`, `active`. Context adds `result_choices`, `category_choices`, `active_choices`, and `stats`. Detail adds `outcomes`. Forms add `obj` on edit and both choice lists.

## Services and analytics

### `apps/sales/opportunity_services.py`

#### `sales_place_opportunity`

Inside `transaction.atomic()`, lock the opportunity, pipeline and target stage; validate tenant, active state, stage membership and entry criteria; lock/create the one-to-one placement; update stage timestamp only on a real stage change; project effective probability, `crm_stage_key` and forecast category to the CRM Opportunity; save both; audit `operation = place`. An identical placement is a no-op without a second audit row.

### `sales_transition_opportunity`

Inside `transaction.atomic()`, lock opportunity, current placement, current stage and target stage. Require a placement. Validate current exit criteria, target entry criteria, closed probability rules, reason compatibility and competitor compatibility. Create one outcome only when a state actually changes. Update CRM stage/probability/category/stage timestamp and placement stage/override/timestamp together. Reopen preserves outcomes and relies on the existing CRM `save()` behavior to clear `lost_at`. Audit `operation = transition`.

Unplaced opportunities continue through the existing `crm:opportunity_advance` legacy behavior. For a placed opportunity, that route calls the Sales service and never directly writes a stage.

### `sales_unplace_opportunity`

Delete only the current placement under lock, leave the last CRM projection intact, preserve outcomes, and audit `operation = unplace`.

### `sales_compute_health`

Return:

```python
{
    "status": "on_track|watch|at_risk",
    "factors": [{"key": str, "label": str, "severity": "at_risk|watch|info", "detail": str, "date": str|None}],
    "stage_age_days": int,
    "target_days": int|None,
    "last_activity_at": str|None,
    "as_of": str,
}
```

Constants:

```python
HEALTH_ACTIVITY_WINDOW_DAYS = 14
HEALTH_NEXT_STEP_SOON_DAYS = 3
HEALTH_CLOSE_SOON_DAYS = 3
HEALTH_STAGE_WATCH_RATIO = 0.75
HEALTH_ACTIVITY_MIN_STAGE_DAYS = 7
```

Closed opportunities return `on_track` with an informational closed-won/lost factor. Open opportunities evaluate overdue/soon/missing close date, overdue/soon/missing next step, overdue/aging stage, no recent activity, and missing account/contact/owner/amount. `at_risk` outranks `watch`. No opaque score is stored or displayed.

`last_activity_at` is the latest of same-tenant CRM task update, communication occurrence, calendar start and opportunity audit timestamp. Future events do not count.

### `apps/sales/opportunity_analytics.py`

`sales_pipeline_rollups`, `sales_pipeline_currency_totals`, `sales_stage_age_rows`, `sales_win_loss_rows`, `sales_competitor_rows`, and `sales_health_counts` are read-only and request-free.

Currency totals group by actual currency id/code. Null currency is the `Unspecified` bucket. Never default to USD and never sum unlike currencies. Weighted value is amount × effective probability / 100, using placement override, stage default, or legacy CRM probability for unplaced deals.

## CRM compatibility

Add to `crm.Opportunity`:

- `next_step_due_date = DateField(null=True, blank=True)`;
- nullable `currency = ForeignKey("accounting.Currency", SET_NULL, blank=True, related_name="crm_opportunities")`;
- indexes `(tenant, next_step_due_date)` and `(tenant, currency)`.

Retain the current editable stage, probability and forecast fields globally. In the CRM form, disable those three only for a placed opportunity and compare submitted values to the instance so crafted POSTs cannot mutate projections. Disable legacy `competitor` only after structured competitor links exist and `loss_reason` only after outcomes exist; otherwise retain editable legacy behavior with a warning.

Keep the CRM Opportunity form's existing fields and add `next_step_due_date` and active global `currency`. Keep CRM admin access. Keep `crm:opportunity_advance`; it delegates placed opportunities to the Sales service and preserves legacy behavior for unplaced opportunities.

Update existing CRM board/forecast displays to group totals by currency and show a mixed-currency indicator. Do not add FX conversion.

The next CRM migration number must be rechecked immediately before generation. At spec time the leaf is `0025_alter_webhook_secret`; the expected next migration adds the two fields, indexes and a safe currency-only `RunPython` backfill from an unambiguous `accounting.CustomerProfile.currency`, with a no-op reverse.

## Templates

```text
templates/sales/opportunity/
  workspace.html
  pipeline/{list,detail,form,stages,board,visibility}.html
  competitor/{list,detail,form}.html
  winlossreason/{list,detail,form}.html
```

Every template extends `base.html`. Lists have search, filters before pagination, Actions where CRUD exists, POST/CSRF delete or remove, guarded pagination and an empty state. Details have Edit/Delete/Back actions for mutable primary records.

Use only verified theme classes. Badge classes are colour-named: green, red, amber, info, muted, slate. Stat-icon colours are blue, green, orange, purple and slate only.

Health: on-track green, watch amber, at-risk red. Outcomes: won green, lost red. Never render free text with `|safe`; URLs are validated by URLField and external links use the existing safe-link convention.

The workspace is an aggregate lens, not duplicate opportunity CRUD. It shows canonical deal data, health factors, team, competitors, outcomes, activities, contracts/documents, audit timeline and a CRM edit link.

## Admin

After 8.1 commits `admin.py`, append registrations for all eight 8.2 model classes with targeted edits. Add tenant filters, search fields, `select_related` metadata, and readonly number/system fields. `OpportunityOutcome` has no add/change/delete permission. Placement, child links and outcomes cannot be changed through admin in ways that bypass the Sales service.

## Seeder

After 8.1 commits `apps/sales/management/commands/seed_sales.py`, extend that existing command; do not create a second Sales seeder. Keep it idempotent and never flush. It reuses existing opportunities, users, org units, parties and currencies; creates default pipelines/stages, reasons, representative team members and competitor links only where suitable CRM rows exist. A second normal run is a no-op.

`--backfill` is explicit and idempotent. It places existing CRM opportunities in a default pipeline using their current static stage, preserves differing probability as an override, uses `stage_changed_at` or `created_at` for `stage_entered_at`, and never defaults currency to USD. Legacy competitor/loss conversion is attempted only when unambiguous; ambiguous data is left untouched.

Print `admin_acme / password` and warn that superuser `admin` has no tenant and sees no Sales data.

## Integration

Only after 8.1 has committed its migration and shared integrations:

1. Re-read and surgically extend every shared 8.1 file; do not rewrite it.
2. Append 8.2 model/form/view re-exports and URL concatenation.
3. Append eight 8.2 admin registrations.
4. Append 8.2 seeder behavior to the existing `seed_sales.py`.
5. Add exactly one `LIVE_LINKS["8.2"]` entry in `apps/core/navigation.py`.
6. Recheck and claim the next CRM and Sales migration numbers immediately before generation; never reserve a number.
7. Generate CRM and Sales migrations; inspect every operation and report any peer models swept in.
8. Run migrate, showmigrations, seed twice, explicit backfill twice, manage.py check and makemigrations --check.
9. Reverse every Sales route and verify every render path exists.

`LIVE_LINKS["8.2"]` exact mapping:

- `Opportunity Creation & Staging` → `sales:opportunity_pipeline_list`
- `Pipeline Visibility & Forecasting` → `sales:opportunity_pipeline_visibility`
- `Opportunity Tracking & Updates` → `sales:opportunity_workspace_list`
- `Competitive Intelligence` → `sales:opportunity_competitor_profile_list`
- `Deal Collaboration & Team Selling` → `sales:opportunity_workspace_list`
- extra `Pipeline Board` → `sales:opportunity_pipeline_board`
- extra `Win / Loss Reasons` → `sales:opportunity_win_loss_reason_list`

## Verification gate

- Every Sales page renders for `admin_acme` and includes the expected object or aggregate, not only HTTP 200.
- No `{#` or template-comment leak markers.
- Every valid filter works; junk integer/enum/date params do not 500; page 2 and pagination boundaries render.
- Cross-tenant IDs return 404 and crafted cross-tenant FK POSTs fail form/service validation.
- Tenant-less users see empty tenant lists and cannot write.
- Configuration writes reject ordinary tenant members; every mutation rejects GET.
- CSRF is required for all POST writes.
- Exactly one active default, one active won and one active lost stage per active pipeline.
- Failed criteria/reason/competitor validation leaves placement, projections and outcomes unchanged.
- Closed probability/category integrity and CRM `lost_at` behavior pass.
- Outcomes are append-only; one primary competitor per opportunity.
- Health returns exact deterministic factor keys and no numeric score.
- Currency totals remain separated, including the Unspecified bucket.
- Board/workspace/visibility have no per-row query growth.
- `seed_sales` and `seed_sales --backfill` are each idempotent on a second run.
- CRM opportunity, lead conversion, project conversion, board and forecast regressions pass.
- Final Sales and CRM tests run unfiltered with migrations enabled; the full project suite is the final gate.

## Review, fixes and tests

Review `BASE...HEAD` serially: code reviewer, explorer, frontend reviewer, performance reviewer, QA smoke tester, security reviewer. Append every finding to `.claude/tasks/review-sales-8.2.md`; do not carry findings only in the transcript.

Run one code-fixer agent after the six passes. It fixes Critical, Important and Minor findings in order, verifies each, marks each finding fixed or explicitly skipped, and commits one file per commit.

Test subslug: `opportunity_pipeline`.

1. Contract agent creates `apps/sales/tests/__init__.py` and `conftest.py`.
2. Write and commit `test_opportunity_pipeline_models.py`.
3. Write and commit `test_opportunity_pipeline_forms.py`.
4. Write and commit `test_opportunity_pipeline_views.py`.
5. Write and commit `test_opportunity_pipeline_security.py`.
6. Run the full unfiltered Sales suite, CRM regressions and full project suite.

Every test and module helper uses the `opportunity_pipeline` prefix.

## Documentation

- After 8.1 closes, update its existing `.claude/skills/sales/SKILL.md` with the 8.2 models, routes, templates, seeder rows, spine reuse, context contracts, services and CRM compatibility. Do not overwrite 8.1 content.
- Update README only after the code is green, re-reading concurrent changes first.
- Reconcile NavERP-ERD ownership in both CRM and Sales rows: CRM owns Opportunity; Sales adds only the eight 8.2 classes and reuses CRM/SCM/accounting/core.

## Deferred

- Lead capture, scoring, routing and nurturing (8.1).
- Account hierarchy, enrichment, influence and account plans (8.3).
- Formal forecasting, manager overrides, scenarios, quota attainment, FX conversion and predictive scoring (8.4).
- CPQ, quote generation/versioning, orders, revenue recognition (8.5/8.6).
- Territory/quota administration (8.7), universal activity engines (8.8), enablement libraries (8.9), compensation (8.10).
- Generic stage skip/back expressions, arbitrary approvals, automated activity ingestion, notification delivery, Slack/Teams, external deal portals, row-level opportunity ACLs, competitor web monitoring, full stage-history warehouses and opaque AI health scores.

## Commit discipline

Every new or changed file receives its own PowerShell-safe commit. Never stage unrelated dirty-tree files, never amend, and never push.

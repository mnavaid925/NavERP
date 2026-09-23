# Research — Sub-module 8.2: Opportunity & Pipeline Management (Module 8 — Sales Management System, `sales`)

Research date: 2026-09-24
Base reviewed: `b18d08fbca4a38eabf9e444b025fb9c4eba4bd34`

## Scope lock

This catalog covers only the five bolded bullets in `NavERP.md:1313-1318`:

1. Opportunity Creation & Staging
2. Pipeline Visibility & Forecasting
3. Opportunity Tracking & Updates
4. Competitive Intelligence
5. Deal Collaboration & Team Selling

8.1 Lead Management is parked, even though a future 8.1 may hand an existing or new deal into 8.2. All 8.3+ sales features are parked, including accounts, formal forecasting, CPQ, orders, territory/quota administration, general activity management, enablement content, and compensation.

## Repo state checked first

- The checkout is intentionally dirty with unrelated concurrent work. None of those paths belong to this research run.
- `apps/sales/` does not exist and there are no `LIVE_LINKS["8.*"]` entries in `apps/core/navigation.py`; this explicit run should scaffold the new app later but build only 8.2.
- No earlier `research-sales*.md` sibling catalog exists.
- The as-built CRM 1.2 surface is already substantial. Do not recreate it under `apps.sales`.

### Verified existing opportunity spine

| Existing class | Verified implementation | 8.2 decision |
|---|---|---|
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5-94` | **Canonical deal. Sales 8.2 must extend it.** It already owns name, `core.Party` account/contact, static stage, forecast category, amount, probability, close date, territory, one accountable owner, source lead/campaign, next-step text, competitor/loss text, `stage_changed_at`, weighted amount, and open/won state. |
| `crm.OpportunitySplit` | `apps/crm/models/SalesForceAutomation/Opportunities.py:97-151` | Reuse unchanged for revenue/overlay credit. Its percentage allocates value; it does **not** represent a functional collaboration role or responsibility. |
| `crm.Territory`, `crm.SalesQuota` | `Territories.py:10-33`; `SalesQuotas.py:5-39` | Use only as existing filter/roll-up dimensions. Territory and quota redesign belongs to 8.7. |
| `crm.CrmTask` | `apps/crm/models/ActivityManagement/Tasks.py:5-125` | Existing opportunity-linked follow-up/task source. Do not add another task model. |
| `crm.CommunicationLog` | `apps/crm/models/ActivityManagement/CommunicationLogs.py:5-68` | Existing call/email/SMS/note/meeting timeline. Reuse for the 8.2 activity/notes surface. |
| `crm.CalendarEvent` | `apps/crm/models/ActivityManagement/CalendarEvents.py:5-79` | Existing meeting/deadline/reminder timeline. Reuse; calendar synchronization remains deferred. |
| `crm.Quote`, `crm.QuoteLine`, `crm.Product` | `SalesForceAutomation/Quotes.py:5-120`; `Products.py:5-45` | Reuse as linked context only. CPQ, catalog, versioning, and proposal work belong to 8.5. |
| `crm.ContractDocument` | `apps/crm/models/DocumentContract/Contracts.py:5-44` | Reuse in the internal deal workspace because it already FKs to an opportunity. |
| `crm.HealthScore`, `crm.HealthScoreHistory` | `apps/crm/models/CustomerSuccess/HealthScores.py:31-77` | **Account/customer-success health only, not deal health.** Do not reuse for 8.2 pipeline risk. |
| CRM opportunity board/forecast | `views/SalesForceAutomation/Opportunities.py:22-142`; `views/SalesForceAutomation/Forecast.py:10-55` | Existing static Kanban, weighted roll-up, and forecast categories. Sales 8.2 should add configurable pipeline views and an explainable health projection without duplicating the deal list or ledger. |

The related forms (`forms/SalesForceAutomation/Opportunities.py:9-22`), views (`views/SalesForceAutomation/Opportunities.py:22-142`), URLs (`urls/SalesForceAutomation/Opportunities.py:7-18`), and `LIVE_LINKS["1.2"]` (`apps/core/navigation.py:248-258`) all confirm this contract.

### Other verified reusable entities

- `core.Party` exists at `apps/core/models/Party.py:5-21`; a competitor company must remain a `core.Party`, not a second organization table.
- `core.Activity` (`Activity.py:5-43`) is a generic activity record, but the current CRM opportunity pages already use the explicit, indexed `CrmTask`/`CommunicationLog`/`CalendarEvent` relations. Aggregate those for 8.2; do not create a fourth activity store.
- `core.Document` (`Document.py:5-28`) and `crm.ContractDocument` can form the document portion of an internal deal workspace.
- `core.OrgUnit` (`OrgUnit.py:5-26`) and `accounts.User` (`apps/accounts/models.py:52-106`) can identify internal collaborators and sponsors.
- `core.AuditLog` (`AuditLog.py:5-27`) is the existing append-only change trail.
- `accounting.Currency` (`GeneralLedger/Currencies.py:6-20`), `ExchangeRate` (`ExchangeRates.py:5-21`), and `CustomerProfile` (`AccountsReceivable/CustomerProfiles.py:5-23`) exist. Do not create a second currency or customer master.
- `scm.SalesOrder` is already canonical at `apps/scm/models/OrderManagement/SalesOrders.py:20-182`, with `source_quote -> crm.Quote`; 8.2 must not add another order.
- `scm.Item`/`scm.UOM` exist at `apps/scm/models/InventoryManagement/Items.py:51-108`; 8.2 needs no product/catalog model and must not link inventory to pipeline stages.

### Ownership decision — extend CRM, do not fork Sales

**Decision: Sales 8.2 EXTENDS the existing `crm.Opportunity`; it does not create a second parallel deal table.** The code disproves duplication as unavoidable: the deal, value, probability, forecast, close date, owner, account/contact, activity links, quotes, documents, and commercial splits already exist. A `sales.Opportunity` would split the same aggregate, break CRM quote/project/expense links, and violate the ships-first extension rule in lessons L28/L29/L36.

The recommended Sales models hold only genuine missing state:

- pipeline definitions, custom stages, and a one-to-one placement of an existing opportunity in its active pipeline;
- functional collaborators and executive-sponsor roles, separate from revenue splits;
- a sales competitive profile on `core.Party` plus opportunity-level competitor links;
- structured win/loss reasons and closure evidence.

`OpportunityPipelinePlacement` is an association, not another deal: it must contain no name, account, amount, close date, owner, or competing copy of those values.

## Leaders surveyed (official 2026 sources)

1. **Salesforce Sales Cloud** — enterprise stage/path guidance, probability-driven forecasts, pipeline inspection, opportunity teams, and dedicated battle-card practices. Sources: [Opportunity fields](https://help.salesforce.com/s/articleView?id=sales.opp_fields.htm&language=en_US&type=5), [Pipeline Inspection metrics](https://help.salesforce.com/s/articleView?id=sales.pipeline_inspection_metrics_and_fields.htm&language=en_US&type=5), [Opportunity Teams](https://help.salesforce.com/s/articleView?id=sales.salesteam_add.htm&language=en_US&type=5), [Battle Cards](https://www.salesforce.com/sales/battle-cards?bc=DB), [pipeline stages](https://www.salesforce.com/sales/pipeline/stages/).
2. **HubSpot Sales Hub** — multiple object pipelines, custom deal stages with probabilities, conditional required properties, transition rules, and explainable deal-score signals. Sources: [pipelines](https://knowledge.hubspot.com/object-settings/set-up-and-customize-pipelines), [pipeline rules](https://knowledge.hubspot.com/object-settings/set-up-pipeline-rules), [deal scores](https://knowledge.hubspot.com/records/use-deal-scores).
3. **Microsoft Dynamics 365 Sales** — opportunity business-process flows with required stage-gating, competitor identification, and a named sales team before proposal. Sources: [opportunity stages](https://learn.microsoft.com/en-us/dynamics365/sales/move-opportunity-stages), [business process flows](https://learn.microsoft.com/en-us/dynamics365/sales/customize-business-process-flows), [2026 wave overview](https://learn.microsoft.com/en-us/dynamics365/release-plan/2026wave1/sales/dynamics365-sales).
4. **Zoho CRM** — multiple pipelines, stage/probability/category mapping, Blueprint stage gates and checklists, forecast rollups, shared groups, notes, and attachments. Sources: [deal creation and stage mapping](https://help.zoho.com/portal/en/kb/crm/sales-force-automation/deal-management/articles/create-deals), [Blueprint](https://help.zoho.com/portal/en/kb/crm/process-management/blueprint/articles/design-a-blueprint), [forecasts](https://help.zoho.com/portal/en/kb/crm/sales-force-automation/forecasts/articles/creating-and-working-with-forecasts), [team collaboration](https://www.zoho.com/crm/team-collaboration.html).
5. **Pipedrive** — multiple process-specific pipelines, stage and deal probability overrides, weighted values, linked activities, overdue notifications, structured lost reasons, and followers for collaboration. Sources: [multiple pipelines](https://support.pipedrive.com/en/article/how-can-i-have-multiple-pipelines), [probability](https://support.pipedrive.com/en/article/probability-in-pipedrive), [activities](https://support.pipedrive.com/en/article/activities), [followers](https://support.pipedrive.com/en/article/followers), [lost reasons](https://support.pipedrive.com/en/article/lost-reasons).
6. **Freshsales** — custom and multiple deal pipelines, per-stage probability, manual probability override, rotting, weighted value, stale-deal and activity insights. Sources: [custom deal stages](https://crmsupport.freshworks.com/support/solutions/articles/50000002392-how-to-customize-deal-stages-), [weighted pipelines](https://crmsupport.freshworks.com/support/solutions/articles/50000002959-how-to-set-up-and-use-weighted-pipelines-), [sales funnel software](https://www.freshworks.com/sales/funnel/software/).
7. **Insightly** — process-oriented opportunity pipelines, editable probability, open/suspended/closed state reasons, predefined stage criteria, and automatic activity sets on stage entry. Source: [lead and opportunity management](https://www.insightly.com/crm/lead-oppty-management).
8. **monday CRM** — customizable pipelines, owner/value/probability fields, Kanban and forecast views, activity logging, conditional automations, and deterministic visibility into stalled/at-risk deals. Sources: [pipeline management](https://support.monday.com/hc/en-us/articles/360013348719-Sales-pipeline-management-with-monday-CRM), [sales pipeline use case](https://monday.com/crm/use-cases/sales-pipeline), [product features](https://monday.com/crm/product-features).
9. **Odoo 19 Sales/CRM** — team-owned pipelines, stage probability and expected revenue, predictive scoring, activity plans, sales teams, and configurable lost reasons. Sources: [CRM](https://www.odoo.com/documentation/19.0/applications/sales/crm.html), [predictive lead scoring](https://www.odoo.com/documentation/19.0/applications/sales/crm/track_leads/lead_scoring.html), [sales documentation](https://www.odoo.com/documentation/19.0/applications/sales.html).

### Product support matrix

A dash means the reviewed source did not establish that capability, not that the product definitely lacks it.

| Product | Multiple/custom pipelines | Stage probability / weighted roll-up | Stage gates / required data | Next-step/activity health | Competitor / win-loss structure | Team collaboration |
|---|---:|---:|---:|---:|---:|---:|
| Salesforce | Paths/processes | Yes | Sales Paths and validations | Pipeline Inspection, next step, days in stage, score | Battle cards and competitive analysis | Opportunity Teams with roles |
| HubSpot | Yes | Yes | Conditional required properties; skip/back rules | Deal score uses tasks, meetings, next step, stage age | Closed-lost reason reporting | Team-based pipeline access; collaboration support |
| Dynamics 365 | Business process flows | Native opportunity forecast | Required field stage-gating | Opportunity research/insights | Opportunity competitors | Named opportunity sales team |
| Zoho | Yes | Yes | Blueprint conditions/checklists/attachments | Tasks, notes, chat, reminders | Deal lifecycle fields; no stronger source claim used | Shared groups and record notes/files |
| Pipedrive | Yes | Yes; deal override wins | No general gate claimed by reviewed pages | Activities, overdue scheduler, followers | Predefined/free-form lost reasons | Followers, because one accountable owner remains |
| Freshsales | Yes | Yes; override allowed | No general gate claimed | Rotting/stale deals and activities | Not established in reviewed source | Deal-team orientation; not a second owner |
| Insightly | Yes | Yes | Predefined criteria plus stage-triggered activity sets | Auto-created tasks/events and stalled stages | Configurable state/loss reasons | Integrated CRM/project context |
| monday | Yes | Yes | Conditional automations | Email/activity timeline and stall health | Deal insights; no dedicated master claimed | Owner, subscribers, team views |
| Odoo | Per sales team | Yes, including learned probability | Activity plans/team assignment | Next activities and predictive scoring | Configurable lost reasons | Sales-team membership and assignment |

## Feature catalog (8.2 only)

### Opportunity Creation & Staging

- **Multiple named pipelines** — different product/service motions can have genuinely different stages without forcing location, owner, or industry segmentation into separate pipelines. Seen in HubSpot, Zoho, Pipedrive, Freshsales, monday, and Odoo. **Priority: common.** **Spine:** new `sales.Pipeline`; deals remain `crm.Opportunity`. **Build now.**
- **Tenant-custom stage definitions** — ordered, reusable stage names rather than a hard-coded global picklist. Seen in HubSpot, Zoho, Pipedrive, Freshsales, Insightly, monday, and Odoo. **Priority: table-stakes.** **Spine:** `PipelineStage`. **Build now.**
- **Stage probability and forecast-category defaults** — default probability is assigned from the stage, while a deal may override it. Seen in Salesforce, HubSpot, Zoho, Pipedrive, Freshsales, Insightly, monday, and Odoo. **Priority: table-stakes.** **Spine:** `PipelineStage` plus `OpportunityPipelinePlacement.probability_override`; effective probability projects to existing `crm.Opportunity.probability`. **Build now.**
- **Entry/exit criteria** — a transition should enforce a small, auditable checklist rather than accept free-form guidance. HubSpot conditional required properties, Zoho Blueprint, Dynamics business-process steps, and Insightly activity sets establish the pattern. **Priority: common.** **Spine:** structured `entry_criteria`/`exit_criteria` JSON on `PipelineStage` with a fixed allowlist. **Build now; no arbitrary expressions.**
- **Closed-stage integrity** — each active pipeline has one won and one lost stage; won is 100%, lost is 0%. HubSpot, Freshsales, monday, and Odoo all make closed states explicit. **Priority: table-stakes.** **Spine:** stage validation. **Build now.**
- **Skip/backward-transition controls and approvals** — seen most clearly in HubSpot pipeline rules. **Priority: differentiator.** **Build later**; this pass validates entry/exit criteria and normal forward/reopen transitions but does not add a generic rule engine.
- **Stage history** — show prior stage, entry/exit timestamps, actor, and duration. Salesforce Pipeline Inspection and Odoo/Monday stage-duration views support it. **Priority: common.** **Spine:** `core.AuditLog` for the initial immutable trail; a dedicated history table is unnecessary because placement timestamps and audit records answer the need. **Build now as a timeline view.**

### Pipeline Visibility & Forecasting

- **Filterable multi-pipeline board/list** — views switch by pipeline while all cards remain the same CRM opportunities. Seen in HubSpot, Zoho, Pipedrive, Freshsales, and monday. **Priority: table-stakes.** **Spine:** `OpportunityPipelinePlacement`. **Build now.**
- **Weighted pipeline value** — stage/deal probability multiplied by amount. Existing `Opportunity.weighted_amount` and forecast view already do this. **Priority: table-stakes.** **Spine:** reuse `crm.Opportunity.amount` and effective probability. **Build now as a pipeline-scoped roll-up.**
- **Manual probability override** — Pipedrive, Freshsales, Salesforce, and monday support or explicitly model deal-level probability. **Priority: common.** **Spine:** nullable override on placement; blank means stage default. **Build now.**
- **Time-in-stage and rotting** — show overdue stage age against a tenant-defined target. Freshsales, monday, Odoo, Salesforce, Pipedrive, and Zoho use this signal. **Priority: common.** **Spine:** `PipelineStage.target_days`; no stored rotting flag. **Build now.**
- **Pipeline inspection** — compare amount, close date, stage, category, owner, and stage-age changes over a period. Salesforce is the clearest leader. **Priority: differentiator.** **Spine:** `core.AuditLog`; a simple first-pass change view can be built, but a snapshot warehouse is deferred.
- **Currency-safe totals** — do not add unlike currencies. Salesforce supports opportunity currency; NavERP already has `accounting.Currency`/`ExchangeRate`. **Priority: differentiator for multi-currency tenants.** **Spine:** add nullable `currency` FK to existing `crm.Opportunity`; group totals by currency when no explicit reporting currency exists. **Build now for correctness; conversion roll-ups belong to 8.4.**

### Opportunity Tracking & Updates

- **Unified opportunity activity timeline** — calls, emails, meetings, notes, tasks, and system audit changes. Seen across the surveyed products; existing CRM tables already store these. **Priority: table-stakes.** **Spine:** `CrmTask`, `CommunicationLog`, `CalendarEvent`, `core.AuditLog`. **Build now; no new activity model.**
- **Next-step text plus due date** — an action without a date cannot drive reminders. Existing `Opportunity.next_step` lacks a date. **Priority: table-stakes.** **Spine:** additive `next_step_due_date` on `crm.Opportunity`; optional linked `CrmTask` remains the task source. **Build now.**
- **Explainable deal-health indicator** — on-track/watch/at-risk with visible reasons. Salesforce, HubSpot, monday, Freshsales, and Odoo all emphasize inactivity, overdue work, stage age, or next-step signals. **Priority: common.** **Spine:** deterministic query/service over existing opportunities, placements, tasks, communications, and calendar events. **Build now.**
- **Stored health score/history or AI prediction** — HubSpot, monday, Salesforce, and Odoo offer learned/predictive signals. **Priority: differentiator.** **Defer** until enough local history exists; 8.4 owns predictive forecast methodology. Do not present an opaque score as fact.
- **Email/calendar/chat ingestion and notifications** — valuable operationally but external integration rather than an 8.2 schema requirement. **Priority: integration/later.** Reuse existing `logged_via`, `sync_source`, and activity models when integrations are built.

### Competitive Intelligence

- **Structured competitor per opportunity** — a deal can face several vendors; one free-text field is insufficient. Dynamics explicitly makes competitor identification a stage step. **Priority: common.** **Spine:** competitor company remains `core.Party`; `OpportunityCompetitor` is the deal link. **Build now.**
- **Configurable win/loss reason taxonomy** — Pipedrive and Odoo use predefined reasons for comparable reporting; HubSpot reports closed-lost reasons. **Priority: common.** **Spine:** `WinLossReason` plus `OpportunityOutcome`. **Build now.**
- **Reusable battle-card summary** — competitor strengths, weaknesses, differentiation, and objection handling should not be retyped on every deal. Salesforce battle cards demonstrate the value. **Priority: differentiator.** **Spine:** `CompetitorProfile` on `core.Party`; lightweight text fields only. **Build now; the full content/enablement library belongs to 8.9.**
- **Deal-level competitive notes** — pricing, positioning, incumbent status, and why this competitor advanced or failed. **Priority: common.** **Spine:** `OpportunityCompetitor`. **Build now.**
- **Automated competitor monitoring and win/loss AI** — market-web monitoring, call mining, and competitive intelligence platforms are external integrations. **Priority: differentiator/integration.** **Defer.**

### Deal Collaboration & Team Selling

- **Functional opportunity team with roles** — Salesforce Opportunity Teams and Dynamics' sales-team step support named internal roles. **Priority: differentiator.** **Spine:** `OpportunityTeamMember -> accounts.User`; `crm.Opportunity.owner` remains the one accountable owner. **Build now.**
- **Co-owner/collaborator/sponsor distinction** — sales support, solution consultant, executive sponsor, approver, and observer have different responsibilities. **Priority: common in enterprise team-selling, differentiator for NavERP.** **Spine:** role choice on `OpportunityTeamMember`. **Build now.**
- **Follower/coordinator concept** — Pipedrive keeps one owner and adds followers. **Priority: common.** **Spine:** active team members with observer/collaborator roles; do not create a second owner field. **Build now.**
- **Internal deal room/workspace** — one tenant-authenticated view of opportunity data, team, competitors, activity, outcomes, contracts, and generic documents. Salesforce collaboration, Zoho notes/files, and Pipedrive linked project context support this pattern. **Priority: common.** **Spine:** `crm.Opportunity` + existing activity/document/contract tables. **Build now as a page; no `DealRoom` model.**
- **Record-level authorization from team membership** — membership is collaboration metadata, not automatically a security boundary. **Priority: security-sensitive differentiator.** **Defer a full opportunity-sharing ACL; every view/query remains tenant-scoped regardless of team membership.**

## Recommended build scope (four Sales 8.2 entity files)

Recommended count: **four tenant-scoped primary model groups**. Child/link classes stay in the same entity file under the project rule and do not add build units. No new deal model is included.

### 1. `OpportunityPipeline/Pipelines.py` — Pipeline [PIPE-]

Primary class plus two supporting children:

#### `Pipeline` [PIPE-]

- Base: new Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "PIPE"`.
- Fields:
  - `name` — required;
  - `description` — blank text;
  - `is_default` — boolean, default false;
  - `is_active` — boolean, default true;
  - inherited `tenant`, `number`, `created_at`, `updated_at`.
- Constraints/indexes: unique `(tenant, number)`; index `(tenant, is_active)`; a form/service must guarantee only one active default per tenant because MariaDB 10.4 cannot safely express the desired partial unique constraint.
- No target/quota: forecast targets and quota management belong to 8.4/8.7.

#### `PipelineStage` (child)

- `tenant` FK -> `core.Tenant`; `pipeline` FK -> `Pipeline`, `CASCADE`.
- `name`; `code` (stable slug); `sequence` (positive integer).
- `stage_kind` choices: `open`, `won`, `lost`.
- `crm_stage_key` choices exactly aligned to `crm.Opportunity.STAGE_CHOICES`: `prospecting`, `qualification`, `proposal`, `negotiation`, `closed_won`, `closed_lost`.
- `probability` 0-100.
- `forecast_category` choices aligned to `crm.Opportunity.FORECAST_CATEGORY_CHOICES`: `omitted`, `pipeline`, `best_case`, `commit`, `closed`.
- `entry_guidance`, `exit_guidance` — explanatory text.
- `entry_criteria`, `exit_criteria` — JSON lists. Each item is `{"key": "<allowlisted key>", "label": "<display text>"}`. Initial allowlist: `account`, `primary_contact`, `amount`, `close_date`, `next_step`, `next_step_due_date`, `owner`, `active_team_member`. Validate shape, allowed keys, labels, and uniqueness server-side; never evaluate arbitrary expressions.
- `target_days` — nullable positive small integer used for time-in-stage health.
- `is_active`; `created_at`; `updated_at`.
- Unique `(tenant, pipeline, code)` and index `(tenant, pipeline, sequence)`.
- `clean()` enforces probability `100` for won, `0` for lost, `1-99` for open; pipeline configuration must have exactly one active won and one active lost stage.

#### `OpportunityPipelinePlacement` (one-to-one link; no number)

- `tenant` FK -> `core.Tenant`.
- `opportunity` **OneToOne** FK -> `crm.Opportunity`, `CASCADE`, related name such as `sales_pipeline_placement`.
- `pipeline` FK -> `Pipeline`; `current_stage` FK -> `PipelineStage`.
- `probability_override` — nullable 0-100; blank means stage default.
- `stage_entered_at`, `created_at`, `updated_at`.
- Validate `current_stage.pipeline_id == pipeline_id`, tenant equality, and one placement per opportunity.

**Canonical-state invariant:** `OpportunityPipelinePlacement.current_stage` is authoritative for the custom pipeline stage. Existing `crm.Opportunity.stage`, `probability`, `forecast_category`, and `stage_changed_at` remain compatibility projections for the many already-built CRM consumers. A single transaction must update placement and projection together. After backfill, ordinary CRM forms may display those fields read-only; all stage moves go through the Sales transition service. Never allow the static stage and custom stage to drift.

**Transition service:** moving into a stage checks that stage's `entry_criteria`; moving out checks the current stage's `exit_criteria`. A move then sets effective probability, CRM compatibility fields, and placement timestamps atomically. Moving to lost/won requires a structured outcome reason. Reopening clears the current lost timestamp as the existing CRM model already does but retains historical `OpportunityOutcome` rows.

**Pages:** pipeline list/detail/form, stage-order editor, `?pipeline=<pk>` board, pipeline visibility roll-up. Put page templates under `templates/sales/opportunity/pipeline/`; do not add another flat opportunity list.

### 2. `OpportunityTeams.py` — OpportunityTeamMember [OTM-]

- Base: Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "OTM"`.
- `tenant`; `opportunity` FK -> `crm.Opportunity`, `CASCADE`.
- `user` FK -> `settings.AUTH_USER_MODEL`, `CASCADE`; form queryset only same-tenant active users and the service validates tenant equality.
- `org_unit` nullable FK -> `core.OrgUnit`, `SET_NULL`.
- `role` choices:
  - `co_owner`
  - `collaborator`
  - `sales_support`
  - `solution_consultant`
  - `executive_sponsor`
  - `approver`
  - `observer`
- `responsibility` — blank text; `is_active`; inherited timestamps.
- Unique `(tenant, opportunity, user, role)`; index `(tenant, opportunity, is_active)`.
- `crm.Opportunity.owner` remains the single accountable primary owner. `co_owner` denotes operational co-ownership and never creates revenue credit. `crm.OpportunitySplit` remains the only percentage/split mechanism.
- Membership supports team display, follow-up context, and sponsor tracking. It is **not** row-level authorization; tenant scoping remains mandatory.
- Surface: inline add/remove/role editor on the Sales opportunity workspace and a compact team panel. `core.OrgUnit` and existing documents provide organizational context.

### 3. `CompetitiveIntelligence.py` — CompetitorProfile [CMP-]

Primary class plus one opportunity link:

#### `CompetitorProfile` [CMP-]

- Base: Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "CMP"`.
- `party` **OneToOne** FK -> `core.Party`, `CASCADE`; the real company name/kind remains the unified Party spine.
- `aliases`; `website_url`; `description`.
- `market_positioning`, `strengths`, `weaknesses`, `differentiators`, `objection_handling` — plain text; never render as trusted HTML.
- `last_reviewed_on` nullable date; `is_active`; inherited timestamps.
- Unique `(tenant, number)`; unique `party`; index `(tenant, is_active)`.
- This is a Sales profile, not a parallel organization. If the party also has an accounting `VendorProfile`, that profile remains valid; both extend the same Party.

#### `OpportunityCompetitor` (child; no number)

- `tenant`; `opportunity` FK -> `crm.Opportunity`, `CASCADE`; `competitor_profile` FK -> `CompetitorProfile`, `PROTECT`.
- `relationship` choices: `identified`, `evaluating`, `shortlisted`, `preferred`, `incumbent`, `eliminated`, `lost_to`, `beaten`, `withdrew`.
- `is_primary` boolean; `pricing_notes`, `deal_notes`, `positioning_notes`; timestamps.
- Unique `(tenant, opportunity, competitor_profile)`; index `(tenant, opportunity, relationship)`.
- Legacy `crm.Opportunity.competitor` should be backfilled into a tenant `core.Party` organization + `CompetitorProfile` + link where safely possible, then removed from ordinary forms and treated as legacy/read-only. Do not keep two writable competitor sources.
- Surface: Competitor CRUD plus an inline opportunity-competitor panel. Full battle-card publishing, training, and content search belong to 8.9.

### 4. `OpportunityOutcomes.py` — OpportunityOutcome [OUT-] + WinLossReason [WLR-]

One primary closure record plus its supporting tenant-scoped reason catalog:

#### `WinLossReason` [WLR-]

- Base: Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "WLR"`.
- `code`; `name`; `description`; `sequence`; `is_active`; inherited tenant/number/timestamps.
- `result` choices: `won`, `lost`, `both`.
- `category` choices: `price`, `product_fit`, `timing`, `competition`, `relationship`, `authority`, `budget`, `no_decision`, `other`.
- Unique `(tenant, code)` and `(tenant, number)`; index `(tenant, result, is_active)`.

#### `OpportunityOutcome` [OUT-] (append-only closure evidence)

- Base: Sales `TenantNumbered` equivalent, `NUMBER_PREFIX = "OUT"`.
- `opportunity` FK -> `crm.Opportunity`, `CASCADE` (not one-to-one: a reopened deal may have more than one closure event).
- `result` choices: `won`, `lost`.
- `reason` FK -> `WinLossReason`, `PROTECT`.
- `competitor_link` nullable FK -> `OpportunityCompetitor`, `SET_NULL`; only for a loss tied to a competitor.
- `notes`; `closed_at` system-set; `recorded_by` FK -> user, `SET_NULL`; inherited number/timestamps.
- Indexes: `(tenant, result, closed_at)`, `(tenant, opportunity, closed_at)`.
- Outcome rows are immutable closure evidence written only by the close/reopen transition service. Reopening does not delete earlier outcomes. The current lifecycle state remains `crm.Opportunity.stage`; outcomes do not replace it.
- Closure requires a reason. `reason.result` must be `both` or match the outcome result; a `lost_to` competitor link requires a lost outcome. Seed an explicit `not_recorded` reason and use it only for honest backfill of historical rows.
- Backfill nonblank legacy `Opportunity.loss_reason` where possible, create outcomes for historical closed-lost rows, then make the legacy field read-only/non-authoritative.
- Surface: reason-catalog CRUD plus a read-only closure timeline on the opportunity workspace.

### Additive extensions to the existing CRM Opportunity (not new model count)

1. Add `next_step_due_date = DateField(null=True, blank=True)` to `crm.Opportunity`; keep existing `next_step` as the description.
2. Add nullable `currency = ForeignKey("accounting.Currency", SET_NULL, null=True, blank=True)` to `crm.Opportunity`. Backfill from `account.customer_profile.currency` when unambiguous; otherwise leave null. Never silently default to USD and never sum unlike currencies. Group pipeline totals by currency in 8.2; formal reporting-currency conversion belongs to 8.4.
3. After placement backfill, make direct static `stage`/`probability`/`forecast_category` editing unavailable through the ordinary CRM form. Preserve them as synchronized projections so `is_open`, `is_won`, `weighted_amount`, CRM health, quotes, projects, and existing tests keep working.
4. Legacy `competitor` and `loss_reason` stay in the database for rollback during migration but stop being writable once structured links/outcomes are backfilled.

### Non-model implementation surfaces

- **Opportunity workspace** — a Sales 8.2 read/extend page over the existing `crm.Opportunity`, showing health/factors, team, competitors, activity timeline, documents/contracts, pipeline placement, and outcome history. Link to `crm:opportunity_edit`; do not duplicate deal CRUD.
- **Internal deal room** — tenant-authenticated aggregate of `core.Document` and `crm.ContractDocument` plus activity/notes. No `DealRoom` table and no external sharing in 8.2.
- **Deal-health service** — deterministic, explainable status only:
  - `on_track` when no configured risk condition is true;
  - `watch` when the next step is due soon, activity is aging, or stage age approaches `target_days`;
  - `at_risk` for overdue close date, overdue next step, stage older than `target_days`, no recent opportunity activity, or missing critical qualification data.
  Return factor labels and dates; do not store a fake numeric score. A later `OpportunityHealthSnapshot` is justified only when trend/ML is actually built.
- **Analytics** — pipeline/owner/territory totals, weighted totals, stage-age distribution, stale-stage counts, win/loss by reason, and competitor outcomes. Quota/manager roll-up logic remains read-only reuse of CRM `SalesQuota`; new forecasting belongs to 8.4.

## NavERP 8.2 bullet coverage

| NavERP bullet | Concrete 8.2 implementation | Honest limit |
|---|---|---|
| Opportunity Creation & Staging | Existing `crm.Opportunity`; new Pipeline/PipelineStage/Placement; configurable order, probabilities, entry/exit checklist, closed-stage validation; pipeline board | Generic skip/back/approval rule engine deferred |
| Pipeline Visibility & Forecasting | Pipeline-filtered board/visibility page; weighted totals; probability override; stage aging; currency-safe grouping; CRM audit-based simple inspection | Commit/manager override/scenario/AI forecast belongs to 8.4 |
| Opportunity Tracking & Updates | Existing task/communication/calendar/audit timeline; additive next-step due date; deterministic health factors and reminders view | Email/calendar sync, AI score, notification delivery deferred |
| Competitive Intelligence | `core.Party` + CompetitorProfile; OpportunityCompetitor; structured WinLossReason/OpportunityOutcome; win/loss and competitor roll-ups | Web monitoring, conversation mining, full battle-card library deferred to 8.9/integrations |
| Deal Collaboration & Team Selling | OTM roles including co-owner and executive sponsor; opportunity workspace; existing contracts/documents/activity as internal deal room | Row-level deal ACL, Slack/Teams, external portal deferred |

## Belongs to sibling sub-modules (parked, not scoped)

- **8.1 Lead Management** — ingestion, behavioral scoring, BANT/MEDDIC, territory/round-robin routing, nurture campaigns, and lead-to-opportunity conversion. 8.2 only receives the resulting `crm.Opportunity`.
- **8.3 Contact & Account Management** — account hierarchies, contact enrichment, influence/champion maps, tiering, white-space analysis, and account plans. Continue using `core.Party`; do not add account hierarchy here.
- **8.4 Sales Forecasting** — commit/pipeline categories, manager overrides, quota attainment ownership, roll-up/adjustment/scenario, accuracy history, and AI prediction. 8.2 supplies stage probabilities and basic weighted visibility only.
- **8.5 Quote & Proposal Management** — CPQ, product bundling, pricing approvals, proposal templates, quote versions, and quote-to-order. Existing `crm.Quote`/`Product` are linked context only.
- **8.6 Order Management** — order capture/amendment/cancellation/revenue recognition. Extend canonical `scm.SalesOrder`; do not add an order here.
- **8.7 Territory & Quota Management** — territory design/rebalancing and quota planning. Existing CRM `Territory`/`SalesQuota` are verified roll-up dimensions only.
- **8.8 Sales Activity & Task Management** — universal activity/task/calendar/email engines and daily planning. Reuse verified CRM activity classes in 8.2.
- **8.9 Sales Enablement** — governed battle-card/content library, playbooks, training, recordings, and coaching. 8.2 stores only lightweight competitive profile text.
- **8.10 Incentive Compensation** — plans, accelerators, SPIF, earnings, clawbacks, and payout. Existing `OpportunitySplit` remains credit context; no commission engine here.
- **8.11 Customer Success** — account health, renewal/expansion pipeline, onboarding, and advocacy. Existing CRM HealthScore is account health and must not be reused as deal health.

## Deferred / later integrations

- Predictive deal scoring, machine-learning probability, and historical health-score storage — insufficient local history and belongs with 8.4 methodology.
- Automatic email/calendar/chat/VoIP capture, Slack/Teams notifications, and real reminder delivery — integration work; data hooks can be recorded later.
- Full pipeline inspection snapshots and side-by-side historical comparison — start with `core.AuditLog`; add snapshots only when reporting needs justify them.
- Record-level opportunity sharing/ACL driven by team membership — security design beyond this pass; do not imply membership changes authorization.
- External customer deal portals, external comments, and guest access — not an internal team-selling requirement.
- Automated competitor web monitoring, conversation intelligence, and imported market intelligence — external integration, not core CRUD.
- Cross-pipeline conversion rates, territory/quota analytics ownership, and reporting-currency roll-ups — 8.4/8.7.
- CPQ products, quote lines, pricing, stock reservation, orders, invoices, and revenue recognition — 8.5/8.6; do not duplicate `crm.Product`, `scm.Item`, or `scm.SalesOrder`.

## Build handoff guardrails

- New app but only 8.2: no 8.1, 8.3, or later-sales scaffolding beyond the minimum package directories required by the new app.
- Package paths should be `apps/sales/{models,forms,views,urls}/OpportunityPipeline/…` for the four entity groups above; re-export every public class.
- Suggested sales template roots: `templates/sales/opportunity/pipeline/`, `templates/sales/opportunity/team_member/`, `templates/sales/opportunity/competitor/`, and `templates/sales/opportunity/outcome/`; secondary workspace/board pages stay beside the relevant entity.
- All list queries and FK querysets must filter the request tenant. Numeric FK GET filters must reject non-digits. Cross-tenant `crm.Opportunity`, placement, team, competitor, and outcome IDs must return 404.
- Use existing color-named badge classes only; verify from `static/css/theme.css` during implementation.
- No opportunity duplication, no second activity/task/document/party/currency/item/order/ledger table, and no writes to accounting or inventory from 8.2.

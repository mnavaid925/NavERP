# Research — Sub-module 8.7: Territory & Quota Management (Module 8 — Sales, `apps/sales`)

> Phase 1 output. Target pre-resolved: **8.7 Territory & Quota Management**. NavERP.md 8.7 = the five
> feature bullets reproduced verbatim in §2. All five are addressed.

**Products researched (7, primary-doc where possible):** Salesforce Sales Cloud (Sales Territories / former
Enterprise Territory Management, Territory Planning, Collaborative Forecasts), Microsoft Dynamics 365 Sales
(Sales Territories, Work Assignment segments+rules, Goal Management), **SAP Territory and Quota** (a
standalone product — by far the richest source here), Oracle Fusion Sales (Territories & Assignment, Define
Sales Quotas, Territory Proposals), Zoho CRM (Territory Management, Forecasts by Territory Hierarchy),
HubSpot Sales Hub (goals; and, usefully, what it *doesn't* have), SugarCRM Sell (Forecasts, Forecast
Tracker). Territory-design tooling class: Salesforce Territory Planning/Maps, Badger Maps, eSpatial,
Routeware — read as the "what a dedicated tool does that a CRM does not" boundary.

**Access note.** Salesforce Help, SAP Help Portal, Oracle Help and Zoho Help are JS SPAs whose doc pages
return a loader shell to any fetcher. Content was obtained from the sources those portals actually serve:
Trailhead (`trailhead.salesforce.com/content/learn/modules/…`), Microsoft Learn (`learn.microsoft.com`),
the **SAP Help Portal search API** (`help.sap.com/http.svc/search`, which returns real body snippets),
`help.zoho.com/portal/en/kb/...` (server-rendered), and `docs.oracle.com` implementation guides.

---

## 1. Ownership ruling — 8.7 EXTENDS `crm.Territory` and `crm.SalesQuota`; it declares neither a second Territory nor a second SalesQuota

**The ruling.** Sub-module 8.7 adds four model classes, and *not one of them is a territory master or a
quota master.* It creates no `Territory`, no `SalesTerritory`, no `TerritoryMember`-on-a-private-territory,
no `Quota`, no `SalesQuota2`, no `QuotaPlan`-that-owns-amounts. The two shared entities are read, FK'd and
extended:

| Shared entity | Owner | Where it lives | How 8.7 uses it |
|---|---|---|---|
| Territory | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Territories.py` — `crm.Territory` (`TER-`) | `ForeignKey('crm.Territory', …)` from all four 8.7 models. `name`, `region`, `segment`, `parent` (self-FK roll-up), `manager`, `is_active`, `description` are read, never re-declared. |
| SalesQuota | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/SalesQuotas.py` — `crm.SalesQuota` (`QTA-`) | `ForeignKey('crm.SalesQuota', …)` from `QuotaPlan`. `target_amount`, `owner`, `territory`, `period_type/year/number` are read, never re-declared. |
| ForecastPeriod | **Sales 8.4** | `apps/sales/models/SalesForecasting/ForecastPeriods.py` | `QuotaPlan.forecast_period` FKs it — 8.7 does **not** re-spell year/quarter/month. |
| Party | **core 0** | `apps/core/models/Party.py` | `AccountTerritoryAssignment.account` FKs `core.Party` (`kind="organization"`). No new customer table (L29). |
| AccountProfile | **CRM 1.x** | `apps/crm/models/CoreData/Accounts.py` | Read by the rule evaluator for `industry`, `annual_revenue`, `employee_count`, `address_*`. |
| AccountClassification | **Sales 8.3** | `apps/sales/models/ContactAccountManagement/AccountClassifications.py` | Read by the rule evaluator for `tier` / `lifecycle_stage` — the reusable account-size axis. |
| Opportunity | **CRM 1.2** | `crm.Opportunity.territory` already exists | The precedent for territory-on-a-deal; read by the assignment + attainment boards. |
| SalesOrder / SalesOrderLine | **SCM 4.5** | `apps/scm/models/OrderManagement/SalesOrders.py` | Realized-revenue source (`subtotal`, `tax_total`, `total`) for attainment. Read-only. |
| SalesQuota (again) | CRM 1.2 | | `ForecastSubmission.quota_ref` already FKs it and **snapshots `quota_amount` by value** so editing a quota never rewrites history. 8.7 must honour that posture. |

**Why this is the ruling and not a preference (L29 / L36 / L37).**

- **L29** established the pattern with the sharpest edge: `accounting` builds and owns the GL ledger; every
  later module FKs `'accounting.JournalEntry'` and posts through *that* ledger. The rule it leaves behind is
  that the entity's owner is decided by **who shipped it first and made it real**, not by which module's
  marketing name sounds like it "should" own it.
- **L36** turned that into a procedure: when a module ships a spine entity the ERD assigned to a *later*
  module, the later module **extends by FK and never re-declares** — and the reconciliation of both plan rows
  is a required close-out step, not an optional note.
- **L37** is the direct precedent for this exact sub-module: Module 5 (Inventory IMS) is literally *named*
  for the inventory domain, and it still had to extend the `scm` spine by FK rather than declare its own
  `Item`/`StockMove`. "The module with the territory in its title does not get to re-declare the territory" is
  L37 applied twice over.

**The alternative, argued and rejected: Sales re-declares its own territory/quota.** Suppose 8.7 ships
`sales.Territory` (`TRS-`) with its own `name/region/parent/manager` and its own
`sales.SalesQuota` with its own `period_type/year/target_amount`. It would look locally tidier — 8.7 could add
`territory_type`, `overlay_depth` and `stretch_amount` as first-class columns without touching CRM. It is
wrong for five concrete reasons, in ascending order of cost:

1. **`crm.Territory` is already load-bearing, and 8.7 is not its only consumer.** As built today,
   `crm.Territory` already carries `sales_routing_rules` (`LeadRoutingRule.territory`),
   `sales_forecast_submissions` (`ForecastSubmission.territory`) and `opportunities`
   (`Opportunity.territory`). A second territory table means **an account's routing rule, its forecast
   submission and its opportunity can each point at a different "territory" object** — and nothing in the
   schema can detect it. That is not a tidiness problem; it is three modules silently disagreeing about what
   a territory is.
2. **Every read becomes a `COALESCE`-shaped union or a data migration.** Revenue-by-territory has to answer
   "which territory owns this opportunity?" — with two tables the honest answer is a query with a branch, and
   a branch is where stale duplicates breed. One territory, one question, one answer.
3. **The migration cost is paid forever, not once.** Two numbered series (`TER-` and `TRS-`) with two
   `(tenant, number)` constraints, two seeder paths, two `next_number` sequences, two admin registrations.
   Every future sub-module that wants a territory has to be told which one to use.
4. **It is the specific failure the lessons exist to prevent.** CRM 1.12's stand-in `PurchaseOrder` is the
   recorded precedent for this shape; SCM 4.1/4.3 shipped later and the parallel schema had to be unwound.
   The whole reason L36/L37 were written is that this was *known* to be wrong and had to be re-decided twice.
5. **8.7 does not actually need the extra columns.** Everything 8.7 wants to say about a territory beyond
   CRM's seven fields — what kind of model it is, how its accounts get assigned, who covers it, what quota
   method it runs — is a property of the *rules, members and plan attached to* the territory, not of the
   territory itself. That is precisely why the four new models are enough. See §3's note on where the
   "territory model type" lives so that `crm.Territory` needs no migration at all.

**The corollary, stated so it cannot be quietly violated:** every 8.7 model FKs `crm.Territory` /
`crm.SalesQuota` **by string** (`'crm.Territory'`), never by importing the class at module scope where a
cycle is possible, and **reads** them — `QuotaPlan` records `method`/`growth_target_pct`/etc. but never
writes `crm.SalesQuota.target_amount`; a quota amount is edited on the CRM quota, in CRM's own form, by CRM's
own permission set. 8.7 announces *how* a quota was derived, not *what* it is.

---

## 2. Deduplicated feature catalog

Grouped, not repeated: a feature that several vendors ship under three names is **one row**. "Difficulty" is
graded against **this** as-built stack (Django 5.1 + SQLite + function-based views + `apps.core.crud`), not in
the abstract.

### Bullet 1 — Territory Design & Mapping (geographic / industry / account-size / named-account models)

| # | Feature (deduplicated) | Products | Difficulty here |
|---|---|---|---|
| 1.1 | **Territory hierarchy with roll-up parent** — root/roll-up node + child territories; forecasts and quotas roll up the tree | SAP (Roll Up / Rep Level / Overlay types), Salesforce (master territory → East/West → CA/TX/NY), Dynamics (`ParentTerritoryId`), Oracle (territory hierarchy drives forecast roll-up), Zoho (territories + sub-territories) | **Free.** `crm.Territory.parent` (self-FK, `related_name="child_territories"`) already is this. Read it; add a derived tree board that walks it. |
| 1.2 | **Typed territory *model type*** — geographic vs industry vs product-line vs account-tier vs named-account vs mixed | Salesforce (Territory Planning: design a model, compare scenarios), Zoho ("territories can be based on geography, industry, product line, expected revenue, verticals"), Oracle (address / account-type / customer-size / industry / business-unit / product / sales-channel dimensions), SAP (Account / Product / Geography alignments) | **Free if inferred, cheap if declared.** Inferred: a territory is "geographic" because the active rules attached to it are geographic. Declared: needs a typed column on `crm.Territory`, i.e. a CRM edit. **Open question §5.1 — recommend inferred.** |
| 1.3 | **Account-size / tier axis** — segment accounts by revenue band or headcount or strategic tier | Salesforce (balance on "size of companies (employees or annual revenue)"), Oracle (customer-size dimension, "account type specifies if an account is named or not"), SAP (Account Classifier Hierarchy + `AccountClassificationRule`), Dynamics (custom goal metrics) | **Free.** The data is as-built: `crm.AccountProfile.annual_revenue` / `.employee_count`, and `sales.AccountClassification.tier` (`strategic\|key\|growth\|nurture`). Reuse the tier vocabulary verbatim; do **not** invent a second banding enum. |
| 1.4 | **Named-account territory** — a hand-picked account list carried inside a territory, overriding any rule | Oracle ("account type: named or not"), Salesforce (named-account treatment in territory models), SAP ("Aligning an Account to a Territory (Manually)") | **Easy.** This is `AccountTerritoryAssignment` with `assignment_source="named_account"` and no `rule` FK. No table of its own — a named-account list is just the set of assignments in that state, and materialising it would be a second source of truth. |
| 1.5 | **Territory-level planning before activation** — design and score models *without touching live data*, then publish | Salesforce (Territory Planning is explicitly a sandbox: "play with different territory models, and see their effects without touching your real data"), SAP (proposed territories / territory programs), Oracle (territory proposals) | **Medium, and deliberately deferred.** The value is the *dry-run*, which §3 delivers as a derived read-only rebalance-preview board over the same rule engine. A separate design-time store is a **non-goal** (§4). |
| 1.6 | **Map / geospatial territory design, drive-time balancing** | Salesforce Maps + AgentExchange (distance- and driving-time-based assignment), Badger Maps, eSpatial, Routeware | **Non-goal.** Needs a routing engine and shapefiles; out of scope for an ERP sub-module and correctly delegated to a specialist tool class (§4). |
| 1.7 | **Territory-level default price list / attributes** | Dynamics (default price list per territory), SAP (Custom Attributes on Territory/Geography/Position), Dataverse `Territory` (`transactioncurrencyid`, `timezoneruleversionnumber`) | **Not 8.7.** Pricing is 8.5's `CPQQuote`; `accounting.Currency` is L29's global master and must not be duplicated. Noted so it is not silently re-invented. |

### Bullet 2 — Territory Assignment & Rebalancing (automated assignment, coverage-gap analysis, annual rebalancing)

| # | Feature | Products | Difficulty here |
|---|---|---|---|
| 2.1 | **Typed rule set that auto-assigns records, with priority ordering and a catch-all** | Dynamics (segments + assignment rules, priority-ordered, "assigns leads, opportunities and insights", catch-all fallback), Salesforce (assignment rules run from the territory hierarchy; same rule set across the hierarchy), SAP (Territory Rules: account / product / geography alignment rules per territory), Oracle (assignment rules; territories themselves drive assignment) | **Easy and precedented — this is the repo's own pattern.** `apps/sales/models/LeadManagement/LeadRoutingRules.py` is exactly this: `priority`, `match_mode`, `conditions` JSON, `is_catch_all`, `cursor`/`last_assigned_at` `editable=False` provenance, a 16 KiB / 20-condition validator, and `validate_routing_conditions()` reused verbatim in shape. 8.7 mirrors it. **Do not write a second rule engine.** |
| 2.2 | **Explicit account→territory ledger** with alignment type (primary / secondary / overlay) and effective dates | SAP (Territory Account alignments; "alignment properties to indicate the alignment type as primary, secondary"; `Aligning a Geography as a Scenario` with start/end dates), Oracle (territory association on the record, re-run assignment after a realignment), Zoho ("An account or contact can be assigned to a maximum of ten territories. Whereas a deal can be assigned to only one territory") | **Easy.** One FK-bearing table. The alignment-type axis is the minimum needed to support overlay coverage without a second "overlay territory" concept. |
| 2.3 | **Effective-dated versioning so a rebalance does not rewrite history** | SAP (every object versioned: "Effective dates indicate when a record becomes available… and the period of time for which the version is effective"; Accounts, Territories, Positions all versioned), Oracle (territory proposal duration / activation date), Salesforce (minimise disruption, "be cautious about moving accounts with late-stage opportunities") | **Medium.** 8.7 puts `effective_from`/`effective_to` on the **assignment** and the **rule** — the two things that actually change at a rebalance. `crm.Territory` itself is unversioned and stays that way; the accepted limitation is called out in §5.8. |
| 2.4 | **Coverage-gap analysis** — who/what is unassigned, doubly-assigned, or manager-less | SAP Key Metrics dashboard (an explicit trio: **Uncovered Account List / Unassigned Account List / Over Assigned Account List**), Salesforce ("reports that show the accounts in each territory, which accounts have no territory assigned"), Zoho (a record is only tested against sub-territories if it met the parent's criteria) | **Free as a derived board.** Every one of those three lists is a filter over `AccountTerritoryAssignment` + `crm.Territory.manager IS NULL`. Storing them would be a second source of truth that goes stale the moment a rule runs. |
| 2.5 | **Annual rebalancing run with review-then-activate** | Salesforce (publish → run assignment rules → **review assignments** → activate; "Once the territories are cut, they don't change for 12 months"; minimize disruption), SAP (program effective start/end dates; territory creation/save/version workflows), Oracle (territory proposals + eligibility-for-quota, plan publish-by date) | **Medium.** Same shape as §3's rebalance-preview board + a commit action writing `AccountTerritoryAssignment` rows, with a `last_run_at` stamp on the rule. No run table (§4). |
| 2.6 | **Load balancing / round robin within a territory** | Dynamics (round robin by last-assignment time vs load balancing by seller capacity and availability, with a configurable time limit after which a record is left unassigned) | **Deliberately out of 8.7's scope.** `LeadRoutingRule.assignment_mode` already carries `fixed_owner` / `territory_manager` / `round_robin` and 8.1 owns the engine. 8.7 resolves *which territory*; 8.1 resolves *which rep*. Do not re-implement. |
| 2.7 | **Bulk alignment run / job scheduling / scenario transfer with exclusions** | SAP ("Run Account Allocation", "Overlay Account Allocation", scenario transfer with "Override Uniqueness Enforcement" and "Create Exclusion in source territory", scheduled segmentation jobs) | **Non-goal for the table; the action is in scope.** A "Run Allocation" POST action on the rule set is achievable; the scheduler belongs to `core.JobScheduler` under 8.17/8.18 (§4). |

### Bullet 3 — Quota Planning & Allocation (top-down / bottom-up, stretch goals, team quotas)

| # | Feature | Products | Difficulty here |
|---|---|---|---|
| 3.1 | **Explicit top-down vs bottom-up methodology** as a first-class choice | SAP (**Quota Planning Methodologies**: a program is Top-Down *or* Bottom-Up; "Quota Planning is not available for bottom-up territory programs"), Zoho ("In the top-down model, the target is set for the business as a whole… then dis-aggregated across roles/territories/managers/users"; bottom-up focuses on teams/roles/individuals), Oracle ("Effective top-down planning with bottom-up assessments"), HubSpot (top-down hierarchical view; bottom-up by team/role/individual) | **Easy.** One `method` enum on `QuotaPlan`, enforced in `clean()` so a bottom-up plan cannot carry top-down-only fields. |
| 3.2 | **Baseline → growth → attrition-relief → quota formula** | SAP (**Bottom-Up Quotas**: `Baseline Quota * (100% + Growth Target% − Attrition Relief)`; "if a territory's account Alignment Start Date <= Cut Off Day, the entire month is considered" — a configurable cut-off), Oracle ("Territory quota formulas… execute an MDX query on the Oracle Essbase hypercube"; predefined formulas incl. prior-year and %-of-total) | **Medium, and this is 8.7's single most differentiating row.** Three `Decimal` percentage columns on `QuotaPlan` plus a `baseline_source` enum, evaluated **in Python** over a fetched set (§5.4). No Essbase, no MDX. |
| 3.3 | **Stretch goal / uplift as a distinct figure from target** | Dynamics (**Goal Metric → `Track Stretch Target`**, which then surfaces a `Stretched Target (Money/Decimal/Integer)` field alongside `Target`), Salesforce (forecast custom columns explicitly for "**Stretch Quota**" and "Internal Booking Target", alongside the quota itself), SAP ("Top-Down: Uplift Allowed"; "Calculated Quota… This can differ from the Assigned Target when an uplift is applied") | **Easy.** `stretch_target_pct` (a percentage uplift) + `uplift_allowed` on `QuotaPlan`. Deliberately a *percentage of the CRM quota*, not a second money column — a second money column is a second source of truth for the target. |
| 3.4 | **Team-based quota allocated down the hierarchy** | Every vendor. Salesforce ("each sales team's quota is specific… each sales rep's portion is based on the products and services"), Dynamics (Goal → `Parent Goal` → `Child Goals`; "The parent goal will roll up the actuals from the child goals"), Zoho (targets at territory / manager / user level), Oracle (spread formulas distribute a parent variance among child territories) | **Free.** `crm.SalesQuota` is already per-owner *and* per-territory with `(tenant, owner, territory, period_type, period_year, period_number)` unique. Team quotas are the same rows with a manager as `owner` over a roll-up territory. **Nothing new to build for the storage.** |
| 3.5 | **Quota metric type — amount vs count, and money vs decimal vs integer** | Dynamics (Goal Metric `Metric Type` ∈ {Amount, Count}; `Amount Data Type` ∈ {money, decimal, integer}, both **locked after first save**) | **Easy, with a ruling.** `crm.SalesQuota` is money-only (`target_amount` Decimal). 8.7 records `target_type` ∈ `revenue\|units\|bookings` on the **plan** as the *label for what the CRM number means* — it does **not** add a unit-count column to the quota. Locking-after-save is the right instinct; see §5.5. |
| 3.6 | **Allocation basis / how the split is computed** | SAP (**Top-Down Bulk Quota Calculation**: allocate by `Historical Values` or by CRM `Pipeline`; "up to 3 dimensions — Products, Accounts, Period"), Oracle (seasonality factor groups distribute an annual quota across quarters; spread formulas distribute a parent variance) | **Medium.** `allocation_basis` enum + the Python calculator. The *dimension* cube (quota × product × account × period) is **out of scope** — it is a planning grid, and it is the single biggest reason SAP Territory & Quota is a separate product. Non-goal (§4). |
| 3.7 | **Phasing / seasonality of an annual quota into periods** | Oracle (Retail seasonality factor group: 10% Q1, 25% Q2, 25% Q3, 40% Q4), SAP ("if period phasing hasn't been set, the target value is the yearly quota distributed equally across 12 months"; "flexible phasing of Quota") | **Easy if kept dumb.** `phasing` ∈ `equal\|seasonal` with the weights living in `parameters` JSON on the plan is enough for 8.7; a per-period phasing table is a non-goal (§4). |

### Bullet 4 — Coverage Model Optimization (hunter/farmer splits, SDR/AE pairing, overlay specialists)

| # | Feature | Products | Difficulty here |
|---|---|---|---|
| 4.1 | **Many users per territory with a coverage role and a split percentage** | SAP (**Territory Team**: "The application uses 0% as the Split % for open positions… you can modify this percentage in the Team workspace for a specific territory"; `Assignment Type`; managers may assign *multiple positions with split percentages as a team*), Dynamics (territory **Members** tab; a manager may hold several territories, and a *new parent territory* is how you give one user a wider area), Salesforce ("Promote team selling… assign collaborative roles in a territory") | **Easy.** `TerritoryMember.coverage_split_pct` (Decimal 5,2, 0–100) + `member_role`. This is one table and it is genuinely missing from the stack: `crm.Territory.manager` is a *single* manager, which cannot express a team. |
| 4.2 | **Hunter / farmer split** | SAP (Rep Level = individual contributors, Roll Up = leaders; the split lives on the team), Salesforce (balance a team *and* overlay roles distinctly — "different, e.g., overlay roles?") | **Easy** — `member_role` ∈ `hunter\|farmer`. Note the honest modelling: a hunter/farmer split is *two members with split percentages on one territory*, not two territory types. |
| 4.3 | **SDR/AE pairing** | No major CRM ships this as a first-class object; it is invariably a workflow or a custom pair. SAP's nearest analogue is the Team with multiple positions and splits; HubSpot pairs SDR→AE with workflow-based ownership | **Easy as a nullable self-FK** (`paired_user` on the member row: the AE an SDR supports). A nullable FK is the whole feature. Making it a full pairing *graph* would be a non-goal. |
| 4.4 | **Overlay specialist territories layered over base territories** | SAP (**Overlay Territories**: "A base territory… can have any number of subordinate overlay territories as children, however, an overlay territory can only have other overlay territories as children"; "**Overlay quotas don't roll up with base territory quotas. Overlay quota distribution is always top-down, even if the base territory quota distribution is bottom-up**"; "Allocate Accounts to Overlay Territory"), Salesforce ("assign collaborative roles in a territory"; credit amounts to sales overlays by revenue / contract value), Oracle (sales channel dimension: Direct / Indirect / Partner) | **Medium, and the cleanest modelling in this report.** 8.7 does **not** create overlay *territories* — it expresses an overlay as `AccountTerritoryAssignment.alignment_type="overlay"` plus a `TerritoryMember` with `member_role="overlay_specialist"`. A second territory subtree would be a second hierarchy; a row that says "this account is also worked by this specialist under this base territory" is the fact. |
| 4.5 | **Open headcount planning** — model the coverage a *hypothetical* hire would carry | SAP (Sales Coverage tab: create/delete **open positions** on a territory; `Additional Attainment = Quota Value × Additional Attainment Target %`; `Proposed Positions = Floor(AdditionalAttainment / CostPerPosition)`), Dynamics (quota set by capacity) | **Deliberately skipped.** It needs a headcount/recruiting master and a cost-per-position figure that 8.7 has no as-built source for. Non-goal (§4), not deferred-to-a-later-pass. |
| 4.6 | **Deal-credit splitting across overlays / co-sell credit** | Salesforce ("credit the right amounts to sales overlays — by revenue, contract value"), Oracle ("Assigning Sales Teams and Allocating Sales Credits") | **Not 8.7.** Deal credit feeds compensation → **8.10 Incentive Compensation**. Note the boundary so 8.10 doesn't re-invent it (§4). |

### Bullet 5 — Territory Performance Analytics (revenue by territory, attainment heat maps, white space)

**Every row in this bullet is a derived read-only board, not a table.** Justification in §3.2.

| # | Feature | Products | Difficulty here |
|---|---|---|---|
| 5.1 | **Revenue by territory** | Every vendor. Oracle ("Forecasts roll up according to the territory hierarchy"), SAP (Territory Quota Attainment story, Top-10/Bottom-10 territories by quota) | **Free.** `AccountTerritoryAssignment` ⋈ `crm.Opportunity.territory` ⋈ `scm.SalesOrder`. Sum in Python over a fetched set. |
| 5.2 | **Quota attainment by territory × period** | SAP (attainment of quota value by Territory **and Target Type**; "Top-N / Bottom-N Territories" toggle), Dynamics (Goal actuals vs target vs stretch target, rolled up the goal tree), SugarCRM (Forecast Tracker: forecast, commitment and sales-won against quota over the period) | **Free.** `QuotaPlan.quota_ref.target_amount` vs closed-won, grouped by territory and `ForecastPeriod`. `ForecastPeriod.period_elapsed_pct` (8.4, already as-built) is the pacing denominator — reuse it, don't re-derive it. |
| 5.3 | **Uncovered / unassigned / over-assigned account lists** | SAP (the explicit dashboard trio, §2 row 2.4) | **Free.** Three filters over one table. |
| 5.4 | **White-space identification** | Salesforce (Tableau CRM "Product Whitespace Analysis" dashboard; territory-planning guidance starts from "TAM, current customer footprint, and the whitespace in between"), HubSpot's practitioner advice ("assign every account a score, then roll it up across territories to see which are overloaded or underloaded"), dedicated tools (eSpatial for "visual white space coverage") | **Medium, and partly already built.** ⚠️ **`sales:account_white_space` and `sales:account_coverage` already exist** (`apps/sales/views/ContactAccountManagement/AccountBoards.py`, 8.3) — they are *account-centric* (stakeholder/relationship coverage and classification gaps), **not** territory-centric. 8.7 must add a *territory-scoped* board under distinct url names and must **not** restate the 8.3 one. See §5.10. |
| 5.5 | **Territory balance / workload-equalisation scorecard** | Salesforce (the entire "Balance Your Territories" unit: never equalise on one factor — a zip code alone gives one rep a sparse region and another a dense city; equal account *count* can hand one rep 45 dead leads and another 50 live ones; factors to combine: number of companies, geography, size of companies, propensity to buy, industry), HubSpot (score, roll up, spot overloaded/underloaded), Badger Maps (weighted multi-objective auto-build) | **Easy.** A per-territory count-and-value profile read off `AccountTerritoryAssignment` + `AccountProfile`. The Salesforce narrative is the acceptance spec: report *every* axis, never pretend a single balance metric exists. |
| 5.6 | **Rebalance diff / what the rules would change** | Salesforce (publish model → run rules → **review assignments** → activate) | **Free as a dry run.** The same evaluator the rule set exposes, run in "propose" mode against current assignments, rendering a diff. This is the highest-value/lowest-cost row in the catalog and it is why §4 rejects a design-time territory store. |

---

## 3. Recommended build scope — **4 model classes**, plus 4 derived read-only boards

### 3.1 The four models

Placed at `apps/sales/models/TerritoryQuotaManagement/`, entity files `TerritoryRules.py`,
`AccountTerritoryAssignments.py`, `TerritoryMembers.py`, `QuotaPlans.py`; templates at
`templates/sales/territoryquotamanagement/<entity>/{list,detail,form}.html`. All four are `TenantOwned` /
`TenantNumbered` from `apps.sales.models._base`; all four are tenant-scoped; all four tenant-check every FK
(tenant-scoped models only — **never** tenant-check `accounting.Currency`, L29).

**Prefix availability verified against the whole repo** (`NUMBER_PREFIX` sweep across `apps/**`): `TRG`,
`TAS`, `TMB`, `QPA` are all **free**; `TER` and `QTA` remain CRM 1.2's.

---

#### (1) `TerritoryRule` — prefix `TRG` — `apps/sales/models/TerritoryQuotaManagement/TerritoryRules.py`

**Serves:** bullet 1 (territory model type + the industry / account-size / named-account axes) and bullet 2
(the typed assignment rule set). Mirrors `apps/sales/models/LeadManagement/LeadRoutingRules.py` field for
field in shape.

```python
SEGMENT_TYPE_CHOICES = [
    ("geographic",    "Geographic"),
    ("industry",      "Industry"),
    ("account_size",  "Account Size"),
    ("product_line",  "Product Line"),
    ("named_account", "Named Account"),
    ("mixed",         "Mixed"),
]
ALIGNMENT_TYPE_CHOICES = [
    ("primary",   "Primary"),
    ("secondary", "Secondary"),
    ("overlay",   "Overlay"),
]
ASSIGNMENT_SCOPE_CHOICES = [
    ("exact",   "This Territory Only"),
    ("subtree", "This Territory And Children"),
]
```

Reuse verbatim from `LeadRoutingRules.py`, do not re-invent: `MATCH_MODE_CHOICES = [("all",…),("any",…)]`,
`is_active`, `priority` (`PositiveIntegerField`, `MinValueValidator(1)`), `conditions = JSONField(default=list)`,
`is_catch_all`, and the `ROUTING_FIELDS` / `ROUTING_OPERATORS` / `MAX_ROUTING_CONDITIONS = 20` /
`MAX_ROUTING_JSON_BYTES = 16 * 1024` validator — **`TERRITORY_FIELDS` is a new allow-list** over
`Party`/`AccountProfile`/`AccountClassification`, e.g. `{"industry", "annual_revenue", "employee_count",
"tier", "lifecycle_stage", "country", "city", "postal_code", "is_named_account", "has_open_opportunity",
"revenue_tier"}` — mirroring how `ROUTING_FIELDS` is a closed allow-list rather than arbitrary JSON.

Key fields: `name`, `description`, `segment_type`, `match_mode`, `conditions`, `is_catch_all`,
`alignment_type`, `assignment_scope`, `target_territory = FK('crm.Territory', SET_NULL, null, blank,
related_name="sales_territory_rules")`, `effective_from = DateField(default=timezone.localdate)`,
`effective_to = DateField(null, blank)`,
**frozen evidence, `editable=False`, off every form:** `last_run_at = DateTimeField(null, blank, editable=False)`,
`last_run_matched_count = PositiveIntegerField(null, blank, editable=False)`.
`Meta`: `unique_together = ("tenant", "name")`; `ordering = ["priority", "id"]`;
indexes `(tenant, is_active, priority)`, `(tenant, segment_type)`.

`clean()` enforces, all in Python: `target_territory` required (a rule assigns *to* a territory; "no
territory" is a coverage **gap**, not a rule outcome); `target_territory` same-tenant; every condition key in
`TERRITORY_FIELDS`; `effective_to >= effective_from`; `segment_type="named_account"` may not carry
`conditions` (named accounts are hand-picked, §2 row 1.4).

*Why this and not a `TerritoryDesign` table:* `segment_type` on the rule set **is** the territory-model-type
declaration (row 1.2). A territory with only `geographic` rules is a geographic territory model. This is what
lets 8.7 satisfy bullet 1's "geographic, industry, account-size, and named-account territory models" with
**zero** change to `crm.Territory`.

#### (2) `AccountTerritoryAssignment` — prefix `TAS` — `…/AccountTerritoryAssignments.py`

**Serves:** bullet 1 (named-account territory), bullet 2 (the explicit ledger, coverage gaps, rebalance
commit), bullet 5 (the input to every derived board).

```python
ASSIGNMENT_SOURCE_CHOICES = [
    ("manual",       "Manual"),
    ("rule",         "Assignment Rule"),
    ("named_account","Named Account"),
    ("inherited",    "Inherited From Parent"),
]
# alignment_type: reuse TerritoryRule.ALIGNMENT_TYPE_CHOICES verbatim, never re-spelled
```

```python
account           = FK("core.Party", on_delete=models.PROTECT, related_name="sales_territory_assignments")
territory         = FK("crm.Territory", on_delete=models.SET_NULL, null=True, blank=True,
                       related_name="sales_account_assignments")
rule              = FK("sales.TerritoryRule", on_delete=models.SET_NULL, null=True, blank=True,
                       related_name="generated_assignments")
owner             = FK(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                       related_name="sales_territory_assignments")
alignment_type    = CharField(8, choices=ALIGNMENT_TYPE_CHOICES, default="primary")
assignment_source = CharField(16, choices=ASSIGNMENT_SOURCE_CHOICES, default="manual")
effective_from    = DateField(default=timezone.localdate)
effective_to      = DateField(null=True, blank=True)
notes             = TextField(blank=True)
assigned_by       = FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, editable=False,
                       related_name="sales_territory_assignments_made")   # frozen evidence (L22)
```
`Meta`: `unique_together = ("tenant", "account", "territory")`; indexes `(tenant, account)`,
`(tenant, territory, alignment_type)`, `(tenant, effective_to)`.

`clean()` enforces, in Python: `account` is a same-tenant `core.Party` with `kind="organization"`;
`territory`, `rule`, `owner`, `assigned_by` are same-tenant (an explicit
`_relation_belongs_to_tenant` helper, copied from `OpportunityTeamMember`); `effective_to >= effective_from`;
**at most one active `primary` row per account** across the tenant; `assignment_source="rule"` requires a
`rule`, and the other three forbid one.

*Design note.* `territory` is `SET_NULL`, matching `crm.Opportunity.territory` and `crm.SalesQuota.territory`
exactly, so deleting a territory orphans assignments rather than cascading away a book's worth of coverage
history — and the coverage-gap board (§3.2) surfaces orphans explicitly instead of hiding them.

---

#### (3) `TerritoryMember` — prefix `TMB` — `…/TerritoryMembers.py`

**Serves:** bullet 4 in full (hunter/farmer, SDR/AE pairing, overlay specialists, split percentages), plus the
team roll-up read side of bullet 3 row 3.4.

```python
MEMBER_ROLE_CHOICES = [
    ("hunter",           "Hunter / New Business"),
    ("farmer",           "Farmer / Existing Business"),
    ("sdr",              "SDR / Business Development"),
    ("ae",               "Account Executive"),
    ("overlay_specialist","Overlay Specialist"),
    ("sales_engineer",   "Sales Engineer"),
]
ASSIGNMENT_TYPE_CHOICES = [
    ("direct",  "Direct Coverage"),
    ("shared",  "Shared / Split Coverage"),
    ("overlay", "Overlay Coverage"),
]
```

**`manager` is deliberately NOT in `member_role`.** `crm.Territory.manager` is CRM's single accountable
manager; a second management field here would be a second source of truth for the same fact. Coverage
membership only.

```python
territory          = FK("crm.Territory", on_delete=models.CASCADE, related_name="sales_members")
user               = FK(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                        related_name="sales_territory_memberships")
member_role        = CharField(20, choices=MEMBER_ROLE_CHOICES)
assignment_type    = CharField(12, choices=ASSIGNMENT_TYPE_CHOICES, default="direct")
coverage_split_pct = DecimalField(max_digits=5, decimal_places=2, default=Decimal("100.00"),
                                  validators=[MinValueValidator(Decimal("0")),
                                              MaxValueValidator(Decimal("100"))])
paired_user        = FK(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                        related_name="sales_paired_territory_members")   # SDR -> AE pairing
is_primary         = BooleanField(default=True)
effective_from     = DateField(default=timezone.localdate)
effective_to       = DateField(null=True, blank=True)
notes              = CharField(max_length=255, blank=True)
```
`Meta`: `unique_together = ("tenant", "territory", "user", "member_role")`; indexes `(tenant, user)`,
`(tenant, territory, is_primary)`.

`clean()`: `user` is an **active** same-tenant user (mirrors `LeadRoutingRule.clean`'s
`default_owner`/`fallback_owner` check); `paired_user` same-tenant, not equal to `user`, and its
`member_role` must be `ae` (a pairing is SDR→AE, and saying so in the validator is cheaper than saying it in
prose); `effective_to >= effective_from`; **the `coverage_split_pct` of the `direct` members on one
territory sums to exactly 100** when any member is `shared` — enforced by summing the fetched sibling rows in
Python (`Decimal`, never `Sum()` in SQL), so the SQLite integer-division trap cannot bite.

*Why not "overlay territories" as a hierarchy:* see §2 row 4.4. An overlay is
`AccountTerritoryAssignment.alignment_type="overlay"` plus a `TerritoryMember(member_role="overlay_specialist")`
against the **base** territory. SAP's own finding — "overlay quotas don't roll up with base territory quotas" —
is reproduced by the data shape rather than by a second subtree.

#### (4) `QuotaPlan` — prefix `QPA` — `…/QuotaPlans.py`

**Serves:** bullet 3 in full (top-down/bottom-up, stretch goals, team quotas). **Extends `crm.SalesQuota` and
`sales.ForecastPeriod` by FK — owns neither.**

```python
METHOD_CHOICES = [
    ("top_down",  "Top-Down"),
    ("bottom_up", "Bottom-Up"),
]
ALLOCATION_BASIS_CHOICES = [
    ("historical_revenue", "Historical Revenue"),
    ("pipeline",          "Open Pipeline"),
    ("account_count",     "Account Count"),
    ("territory_potential","Territory Potential"),
    ("manual",            "Manual"),
]
BASELINE_SOURCE_CHOICES = [
    ("previous_period", "Previous Period"),
    ("previous_year",   "Previous Year"),
    ("custom",          "Custom"),
]
STATUS_CHOICES = [                        # reused from ForecastSubmission.STATUS_CHOICES, verbatim
    ("draft", "Draft"), ("submitted", "Submitted"), ("approved", "Approved"),
    ("rejected", "Rejected"), ("locked", "Locked"),
]
TARGET_TYPE_CHOICES = [("revenue","Revenue"), ("units","Units"), ("bookings","Bookings")]
PHASING_CHOICES = [("equal","Equal"), ("seasonal","Seasonal")]
```

```python
quota_ref       = FK("crm.SalesQuota", on_delete=models.PROTECT, related_name="sales_quota_plans")
forecast_period = FK("sales.ForecastPeriod", on_delete=models.PROTECT, related_name="quota_plans")
owner           = FK(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                     related_name="sales_quota_plans")            # the team/rep this plan is for
territory       = FK("crm.Territory", on_delete=models.SET_NULL, null=True, blank=True,
                     related_name="sales_quota_plans")             # mirrors the quota's own territory
method           = CharField(10, choices=METHOD_CHOICES)
allocation_basis = CharField(20, choices=ALLOCATION_BASIS_CHOICES, default="historical_revenue")
baseline_source  = CharField(16, choices=BASELINE_SOURCE_CHOICES, default="previous_year")
growth_target_pct   = DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
attrition_relief_pct= DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
stretch_target_pct  = DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
uplift_allowed      = BooleanField(default=False)
target_type     = CharField(10, choices=TARGET_TYPE_CHOICES, default="revenue")
phasing         = CharField(8, choices=PHASING_CHOICES, default="equal")
parameters      = JSONField(default=dict, blank=True)   # seasonal weights, cut-off day, custom baseline …
status          = CharField(10, choices=STATUS_CHOICES, default="draft")
is_active       = BooleanField(default=True)
notes           = TextField(blank=True)
# frozen evidence, editable=False, off every form (L22)
submitted_by / approved_by = FK(settings.AUTH_USER_MODEL, SET_NULL, null, blank, editable=False, …)
submitted_at / approved_at = DateTimeField(null=True, blank=True, editable=False)
calculated_at              = DateTimeField(null=True, blank=True, editable=False)
```
`Meta`: `unique_together = ("tenant", "quota_ref")`; ordering `["-forecast_period__period_year", "owner"]`;
indexes `(tenant, method)`, `(tenant, territory)`, `(tenant, status)`.

`clean()` enforces, in Python:
- `quota_ref`, `forecast_period`, `owner`, `territory` same-tenant; `territory` (if set) equals
  `quota_ref.territory_id` (a plan may not point at a different territory than the quota it annotates);
- **the binding cross-check (§5.3):** `quota_ref.period_type == forecast_period.period_type`,
  `quota_ref.period_year == forecast_period.period_year`, and
  `quota_ref.period_number == forecast_period.period_number`; mismatch → `ValidationError` naming both sides;
- `method == "bottom_up"` forbids `uplift_allowed` (SAP: uplift is a top-down-only setting);
- `stretch_target_pct` requires `uplift_allowed`;
- `status in ("approved","locked")` freezes editing (mirroring `ForecastSubmission.FROZEN_STATES`);
- `parameters` validated with the same discipline as `OrderValidationRule.parameters` — closed dict per
  `method`, unknown keys **ignored rather than rejected**, so a row written by a newer build survives a rollback.

`unique_together = ("tenant", "quota_ref")` is deliberate and stricter than CRM's six-column key: one quota gets
one plan, which makes "how was this target derived?" answerable and makes a second competing derivation for
the same number impossible.

### 3.2 Bullets served by DERIVED read-only boards instead of tables — and the justification

Four boards, in `apps/sales/views/TerritoryQuotaManagement/TerritoryBoards.py`, each a pure function over
as-built tables. None of them has a table, a seeder row, or an admin registration.

| Board | url name | Serves | Reads |
|---|---|---|---|
| **Rebalance preview** (proposed-vs-current assignment diff) | `territory_rebalance_preview` | bullet 2 (annual rebalancing, §2 rows 2.3–2.5, 5.6) | `TerritoryRule.conditions` evaluated over `core.Party` + `AccountProfile` + `AccountClassification`, diffed against live `AccountTerritoryAssignment` |
| **Coverage gap** (uncovered / unassigned / over-assigned + manager-less) | `territory_coverage_gap` | bullet 2 (coverage gap analysis, §2 row 2.4) | `AccountTerritoryAssignment` ⋈ `crm.Territory.manager IS NULL` |
| **Performance & attainment** (revenue by territory × period, pacing, balance profile) | `territory_performance` | bullet 5 (rows 5.1, 5.2, 5.5) | `AccountTerritoryAssignment` ⋈ `crm.Opportunity` ⋈ `scm.SalesOrder` ⋈ `QuotaPlan` ⋈ `crm.SalesQuota` ⋈ `ForecastPeriod` |
| **Territory white space** (accounts in a target segment that no territory covers) | `territory_white_space` | bullet 5 (row 5.4) | `core.Party` + `AccountProfile` + `AccountClassification` LEFT JOIN `AccountTerritoryAssignment` |

**Why a board and never a table — the stated justification.** A board is a *pure function of tables that
already have owners*. Its result is correct by construction on every read. A materialised board table is a
**copy**, and a copy is either (a) recomputed on a schedule and therefore **stale** between runs, or (b)
recomputed on write and therefore a **second source of truth that can fall out of date the moment any input
is edited outside it** — a rule re-run, a quota amended, an order booked. Either way the ERP ends up with two
numbers for one fact and no way to tell which one the board means. Concretely, in *this* stack:

- **Coverage gaps are already the definition of a query.** "Unassigned account" = no row in
  `AccountTerritoryAssignment` with `effective_to IS NULL`. Storing `is_unassigned = True` on the account is a
  column that is wrong the instant a rule runs, and nothing in the schema can tell you it is wrong.
- **Attainment is derived from three tables that each have their own lifecycle.** `crm.SalesQuota` is edited in
  CRM's own form; `sales.ForecastPeriod` can be locked by 8.4; `scm.SalesOrder` moves status on its own
  schedule. A stored attainment figure has no natural invalidation trigger. Note the precedent in reverse:
  8.4's `ForecastSubmission` **snapshots `quota_amount` by value** precisely so that editing a quota cannot
  rewrite a historical forecast — that is the escape hatch for a *frozen* record, and these boards are not
  frozen records.
- **8.4 already proves the pattern.** `ForecastBoards.py` ships `forecast_board`, `forecast_attainment`,
  `forecast_accuracy` and `forecast_call` as four derived read-only views with **zero** backing tables, and
  8.3 ships `account_coverage` / `account_white_space` the same way. 8.7 is the third module in a row to make
  this call, and it should make it the same way.
- **The one thing genuinely worth persisting — what a rebalance *did*** — is already persisted, twice over:
  `TerritoryRule.last_run_at` / `last_run_matched_count` (frozen evidence) and the effective-dated
  `AccountTerritoryAssignment` rows the run wrote. The audit trail exists without a run table.

Each board follows the board conventions already in the repo: every view filters by `request.tenant` and
returns empty for the tenantless superuser; a junk `?period=` / `?territory=` id is validated and `404`s on
cross-tenant (the `as_db_int` + existence-check pattern in `AccountBoards.py`); and **all money and
percentage arithmetic is `Decimal` in Python over a fetched set** — attainment %, pacing %, balance spread and
the baseline×(1+growth−relief) formula are never an `F()` expression and never a DB-side division
(§5.4).

---

### 3.3 Bullets → build artefacts, at a glance

| NavERP 8.7 bullet | Tables | Boards |
|---|---|---|
| 1 Territory Design & Mapping | `TerritoryRule.segment_type` + `conditions`; `AccountTerritoryAssignment` (`named_account`, `account_size` tier rules) | `territory_rebalance_preview` (design before commit) |
| 2 Territory Assignment & Rebalancing | `TerritoryRule`, `AccountTerritoryAssignment` | `territory_rebalance_preview`, `territory_coverage_gap` |
| 3 Quota Planning & Allocation | `QuotaPlan` (+ existing `crm.SalesQuota` for the numbers) | `territory_performance` (attainment/pacing) |
| 4 Coverage Model Optimization | `TerritoryMember` | — (a member list is not a board) |
| 5 Territory Performance Analytics | — | `territory_performance`, `territory_white_space` |

---

## 4. Explicit non-goals — what a later sub-module should own instead

Each of these was found in the research and is **deliberately declined**, with the owner that should take it.

1. **Geospatial territory design: map rendering, drive-time / distance balancing, route optimisation, shapefile import.** Salesforce (Salesforce Maps, AgentExchange — "distance- or driving-time–based assignment"), Badger Maps, eSpatial, Routeware. This is a specialist product class with a routing engine behind it; a Django/ERP sub-module has no as-built source for it. **Not 8.7, and not a later NavERP sub-module** — this stays a third-party tool that writes its conclusions into `AccountTerritoryAssignment` as `assignment_source="manual"`.
2. **A design-time territory *store* separate from the live one** (proposed territories, modelled scenarios, parallel hierarchies — Salesforce Territory Planning as a sandbox, SAP territory proposals, Oracle territory proposals). Declined because §3's `territory_rebalance_preview` board delivers the same "see the effect before committing" value against the *same* rule engine and the *same* territory rows, so a parallel hierarchy would be a second source of truth for the same concept. If a proposal must persist across sessions, it persists as **`AccountTerritoryAssignment` rows with `effective_from` in the future** — the same table, a future date, no new concept.
3. **Quota distribution as a multidimensional cube** — quota × product × account × period (SAP's up-to-3-dimensions Quota Planning; Oracle's MDX formulas over an Essbase hypercube). This is a planning grid, not an ERP entity, and it is the single biggest reason SAP Territory & Quota is a separate product. **8.7 ships `allocation_basis` + `parameters`; the grid is not built.**
4. **Quota phasing / seasonality factor groups as first-class tables** (Oracle's `Retail` group: 10/25/25/40 across quarters). The weights live in `QuotaPlan.parameters` in 8.7. A cross-plan, reusable factor library is a **master-data** concern → **8.19 Master Data & Configuration**.
5. **Open headcount / position planning and cost-per-position modelling** (SAP's open positions, `Additional Attainment`, `Proposed Positions = Floor(AdditionalAttainment / CostPerPosition)`). Needs a recruiting and cost master 8.7 does not have → **8.19** at the earliest, and realistically out of NavERP's scope.
6. **Incentive compensation, commission plans, payout calculation, deal-credit attribution to overlays.** Salesforce credits overlay contribution by revenue and contract value; Oracle assigns sales teams and allocates sales credits. **8.10 Incentive Compensation Management** owns all of it, and 8.7 must not pre-empt it by storing a "credit" figure.
7. **Scheduled / background territory & quota jobs** (SAP's "Run Account Allocation", scheduled segmentation jobs with chaining and parallelism). 8.7 ships the *action* as a POST view; the scheduler and job registry are `core.JobScheduler` → **8.17 Workflow & Process Automation** / **8.18 Integration & API Hub**.
8. **Load balancing / round-robin assignment of records within a territory.** `LeadRoutingRule.assignment_mode` (`fixed_owner` / `territory_manager` / `round_robin`) and the routing engine in `apps/sales/services.py` already own it — **8.1 Lead Management**. 8.7 resolves *which territory*; 8.1 resolves *which rep*. Re-implementing the cursor is the one place where 8.7 could most easily fork 8.1's engine, so it is named explicitly.
9. **Account hierarchy, stakeholder maps, account plans, account-level white space, health scores.** **8.3 Contact & Account Management** already owns these — including the existing `sales:account_coverage` and `sales:account_white_space` boards (§5.10).
10. **Forecast submissions, forecast categories (Pipeline/Best Case/Commit/Closed), adjustments, what-if scenarios, forecast accuracy.** **8.4 Sales Forecasting** owns all of it. `ForecastPeriod` and `Opportunity.FORECAST_CATEGORY_CHOICES` are read, never re-spelled.
11. **Territory-aware pricing / territory price lists** (Dynamics' default price list per territory). **8.5 Quote & Proposal Management (CPQ)** and `accounting.Currency` (L29 global master).
12. **Customer master, account master, opportunity master, sales order.** `core.Party`, `crm.Opportunity`, `scm.SalesOrder` respectively — the L29/L36/L37 ruling in §1.
13. **Territory-scoped row-level security / data visibility enforcement.** Zoho's territory-driven record permissions are powerful but are a *security* feature; NavERP's per-tenant isolation is Module 0's `core` concern. 8.7 stores the assignment; it does not implement visibility policy.

---

## 5. Risks and open questions to settle at contract time

Ordered by how expensive the mistake is if it is discovered late.

**5.1 — Is the territory *model type* inferred from the rule set, or declared on `crm.Territory`?** *Open.*
Inferring it (a territory is geographic because its only active rules are geographic) keeps 8.7 free of any
CRM migration and makes the declaration data, not code. Declaring it is more honest for reporting and allows a
territory to be tagged with no rules at all, but it means a column on `crm.Territory`, i.e. editing CRM's model
from a Sales sub-module, plus an ERD/ownership conversation. **Recommendation: infer; revisit as an 8.19
master-data item.** Must be pinned in the contract either way — the `TerritoryRule.segment_type` CHOICES and
the board's grouping key depend on the answer.

**5.2 — `crm.SalesQuota`'s `unique_together` contains a nullable `territory`, and SQLite treats NULLs as
distinct.** The CRM code comments this: *"a null-territory 'overall' quota is also enforced friendly-side in
the form."* So two null-territory quotas for the same `(tenant, owner, period_type, period_year,
period_number)` **can both be written at the DB level** and only the CRM form prevents it. 8.7's
`QuotaPlan` must therefore not assume `(tenant, owner, period)` is unique, and must tenant-check `quota_ref` in
`clean()`. This is an existing CRM wart, not one 8.7 introduces — but 8.7 is the first module that reads
those quotas in bulk and will surface duplicates as doubled attainment. **Settle at contract time whether
8.7 reports or refuses on a duplicate.**

**5.3 — `QuotaPlan` FKs *both* `crm.SalesQuota` and `sales.ForecastPeriod`, and each carries its own
`period_type / period_year / period_number`.** These are two parallel spellings of the same window and they
**can** disagree — nothing in either table's schema prevents it. The ruling must be: the plan refuses to save
unless all three fields match (§3.1 model 4). **This is the single most important line in the 8.7 contract**,
because a mismatch does not fail loudly — it produces an attainment board that quietly compares a Q2 quota
against a Q1 forecast, and it will read as a *data* problem rather than a schema one. Pin it in the
`contract-sales-8.7.md`, with the exact `ValidationError` key.

**5.4 — Money and percentage arithmetic.** Attainment %, pacing %, balance spread, `growth_target_pct −
attrition_relief_pct`, the `coverage_split_pct` sibling sum and the baseline→quota formula must all be
`Decimal` in **Python over a fetched set**. Never `F()`, never `Sum(...)/Sum(...)`, never
`Cast(Value(...))` division — the SQLite integer-division trap silently drops fractional cents instead of
raising (documented in `scm.SalesOrder.recalc_totals()` and honoured by
`apps/sales/models/OrderManagement/OrderValidationRules.py`). **Risk:** the board queries are exactly where
the temptation appears, because an aggregate queryset is one line and a Python loop is ten. State it in the
contract per-board, not once in a preamble.

**5.5 — Does `QuotaPlan.status` freeze, and when?** `ForecastSubmission.FROZEN_STATES = {"approved","locked"}`
is the precedent: the form disables the fields *and* the views re-check server-side, so hiding the Edit button
is never the only guard. 8.7's plan is a *methodology record*, not a submitted forecast — freezing it is
less obviously right. **Open:** freeze at `approved`, or allow post-approval recalculation with
`calculated_at` refreshed? Recommendation: freeze at `approved`, keep `parameters` editable only while
`draft`.

**5.6 — `crm.Territory` deletion.** `AccountTerritoryAssignment.territory` is `SET_NULL` (matching
`Opportunity.territory` and `SalesQuota.territory`), so deleting a territory orphans its assignment rows rather
than refusing. **Open:** is a silent orphan acceptable, given the coverage-gap board will report
`territory is null` rows as "unassigned"? Alternative is `PROTECT` and a clean refusal. Recommendation: keep
`SET_NULL` + board visibility (consistent with the rest of the spine) and pin the board's treatment of
null-territory rows explicitly.

**5.7 — `ForecastPeriod.delete()` will not know about `QuotaPlan`.** It guards `ForecastSubmission` and
`ForecastScenario` by name (see `_optional_sales_model` in `ForecastPeriods.py`). `QuotaPlan.period` being
`PROTECT` means deleting a period with a plan raises a raw `IntegrityError` from the DB rather than the
friendly `ValidationError` 8.4 produces. **Open:** (a) accept the raw error, (b) extend 8.4's guard — a
**surgical edit to another sub-module's file**, which needs explicit agreement under L43, or (c) use `CASCADE`
and accept losing plans. Recommendation: (a) for this pass, and raise (b) as a separate, deliberately-scoped
follow-up.

**5.8 — `crm.Territory` is unversioned, so historical territory shape is not reconstructible.** SAP versions
every object; 8.7 puts effective dates on assignments and rules only. So "what did Territory West contain in
March?" is answerable from `AccountTerritoryAssignment` history but *not* from the territory itself — if a
territory was renamed or re-parented, the past is not recoverable. **Open question, not a defect:** accept and
document, or raise a CRM change for `Territory` versioning. Recommendation: accept for 8.7, record the
limitation in the module docstring, revisit with 8.19.

**5.9 — `TerritoryMember` split-sum enforcement and the `SET_NULL` `paired_user`.** Two sharp edges. (a) The
"direct members sum to 100" check requires fetching siblings on every `clean()` — decide whether it is a hard
`ValidationError` (correct, but awkward for bulk edits) or a board warning. Recommendation: hard, but only
enforced when `assignment_type == "shared"` is present on the territory, so the common single-rep case costs
nothing. (b) `paired_user` is `SET_NULL`, so deactivating or deleting the AE silently orphans the pairing.
Pin whether an orphaned SDR is allowed (recommend: yes, and the board should show it).

**5.10 — ⚠️ URL and concept collision with 8.3, already in the tree.** `apps/sales/urls/ContactAccountManagement/*.py`
already registers `name="account_coverage"` and `name="account_white_space"` (`AccountBoards.py`, 8.3). Those
boards are *account-centric* (stakeholder coverage; classification-driven gaps) — **not** territory-centric —
so they are **not** duplicated and **must not** be modified. But 8.7's boards need their own, clearly distinct
names (`territory_coverage_gap`, `territory_white_space` are the proposals), and the 8.7 templates must link
*across* to the 8.3 boards rather than re-implement them. **Confirm at contract time** so a reviewer reading
8.7 does not read it as a duplicate — this is the exact "same feature under three names" trap the dedup rule
exists to catch, in the one direction that would otherwise land as a regression against 8.3.

**5.11 — Reverse-accessor collisions on `crm.Territory` / `crm.SalesQuota`.** Both already carry related names
from three other sub-modules (`sales_quotas`, `sales_routing_rules`, `sales_forecast_submissions`,
`opportunities` on the territory). 8.7 adds `sales_territory_rules`, `sales_account_assignments`,
`sales_members`, `sales_quota_plans`. All four are free **today**, but a parallel session (L43) building a
different sub-module could add one of them first. **Verify each `related_name` with
`python manage.py check` at the Integrate step, not at the spec step.**

**5.12 — Tenant isolation is not automatic through a FK.** `core.Party` and `crm.Territory` are tenant-scoped,
so an FK *looks* safe, but a hand-built `Party(pk=<other tenant>)` passed to `save()` (a seeder, a service, a
shell) bypasses it. Every one of the four models' `clean()` must tenant-check **every** FK — `account`,
`territory`, `rule`, `owner`, `paired_user`, `assigned_by`, `submitted_by`, `approved_by`, `quota_ref`,
`forecast_period` — using the explicit `_relation_belongs_to_tenant` helper already copied twice in this repo
(`LeadRoutingRules.py`, `OpportunityTeamMember`). And **never** tenant-check `accounting.Currency` (L29) —
though `QuotaPlan` correctly does not carry one, inheriting the reporting currency from `ForecastPeriod`
instead.

---

*Prepared by the `research` agent. Research-only run: no file outside this report was created, edited or
deleted, and no git operation was performed.*

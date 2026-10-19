# Research — Sub-module 8.12: Sales Analytics & Intelligence (Module 8 — Sales Management System, apps/sales)

## Repo state checked first

**LIVE_LINKS built so far in Module 8** (read from `apps/core/navigation.py`): `8.1` Lead Management · `8.2` Opportunity & Pipeline Management · `8.3` Contact & Account Management · `8.4` Sales Forecasting · `8.5` Quote & Proposal Management (CPQ) · `8.6` Order Management · `8.7` Territory & Quota Management · `8.8` Sales Activity & Task Management · `8.9` Sales Enablement · `8.10` Incentive Compensation Management · `8.11` Customer Success & Account Management. **`8.12` is the next unbuilt sub-module.** (`8.13` Marketing Alignment & Attribution is also unbuilt and is out of scope here.)

**`apps/sales` already exists** — this is an EXTEND run. No app scaffolding, no `config/settings.py` INSTALLED_APPS change, no `config/urls.py` change. The only navigation change is ONE `LIVE_LINKS["8.12"]` entry in `apps/core/navigation.py`.

**Next migration number: `0023`** (`apps/sales/migrations/` currently ends at `0021_customersuccess.py`, `0022_customersuccess_indexes.py`).

### Spine entities VERIFIED to EXIST (grep evidence)

| Entity | File | Grep hit |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py` | `class Party(models.Model):` |
| `core.PartyRole` | `apps/core/models/PartyRole.py` | `class PartyRole(models.Model):` |
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py` | `class Opportunity(TenantNumbered):` — fields confirmed: `account`→core.Party, `stage` (STAGE_CHOICES prospecting/qualification/proposal/negotiation/closed_won/closed_lost), `forecast_category`, `amount` (12,2), `currency`→accounting.Currency, `probability`, `close_date`, `competitor`, `loss_reason`, `lost_at`, `stage_changed_at`, `territory`→crm.Territory, `owner`→AUTH_USER_MODEL, `source_lead`→crm.Lead, `campaign`, `next_step`, `next_step_due_date`; properties `weighted_amount`, `is_open`, `is_won` |
| `crm.Lead` | `apps/crm/models/CoreData/Leads.py` | `class Lead(TenantNumbered):` — has `source`, `status`, `rating` (RATING_CHOICES) |
| `crm.Territory` | `apps/crm/models/SalesForceAutomation/Territories.py` | `class Territory(TenantNumbered):` — `name`, `region`, `segment`, `parent`, `manager`, `is_active` |
| `crm.CommunicationLog` | `apps/crm/models/ActivityManagement/CommunicationLogs.py` | `class CommunicationLog(TenantNumbered):` — `CHANNEL_CHOICES` = call/email/sms/note/meeting, `OUTCOME_CHOICES`, `DIRECTION_CHOICES` |
| `crm.AnalyticsReport` / `AnalyticsDashboard` / `DashboardWidget` / `ReportSnapshot` | `apps/crm/models/AnalyticsReporting/{Reports,Dashboards,Widgets,Snapshots}.py` | all four exist — a **saved-report / dashboard / snapshot engine already ships** |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py` | `class Currency(models.Model):` |
| `scm.SalesOrder` | `apps/scm/models/OrderManagement/SalesOrders.py` | `class SalesOrder(TenantNumbered):` — `customer`→core.Party, `currency`, `total`, `status` |
| `sales.Pipeline` / `PipelineStage` / `OpportunityPipelinePlacement` | `apps/sales/models/OpportunityPipeline/Pipelines.py` | `PipelineStage`: `sequence`, `stage_kind` (open/won/lost), `crm_stage_key`, `probability`, `forecast_category`, **`target_days`**, `entry_criteria`, `exit_criteria`. `OpportunityPipelinePlacement`: OneToOne→crm.Opportunity, `current_stage`, `probability_override`, **`stage_entered_at`** |
| `sales.WinLossReason` / `sales.OpportunityOutcome` | `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py` | `WinLossReason` (prefix `WLR`): `code`, `name`, `sequence`, `result` (won/lost/both), **`category` (price/product_fit/timing/competition/relationship/authority/budget/no_decision/other)**, `is_active`. `OpportunityOutcome` (prefix `OUT`): `opportunity`→crm.Opportunity, `result`, `reason`→sales.WinLossReason (PROTECT), `competitor_link`→sales.OpportunityCompetitor, `notes`, `closed_at`, `recorded_by`; **append-only** |
| `sales.OpportunityCompetitor` / `CompetitorProfile` | `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py` | both exist |
| `sales.ActivityLog` / `sales.ActivityType` | `apps/sales/models/SalesActivityTaskManagement/{ActivityLogs,ActivityTypes}.py` | `ActivityLog`: `communication_log`→crm.CommunicationLog, `activity_type`→sales.ActivityType, `owner`→user, `opportunity`, `account`, `territory`, `capture_source`, `is_auto_captured`, `occurred_on`, `planned_minutes`. `ActivityType.kind` reuses `CommunicationLog.CHANNEL_CHOICES` |
| `sales.QuotaPlan` / `sales.TerritoryMember` | `apps/sales/models/TerritoryQuotaManagement/` | `QuotaPlan.quota_ref`→`crm.SalesQuota`, `forecast_period`→sales.ForecastPeriod, `owner`, `territory`, `target_type` (revenue), `phasing`, `status` |
| `sales.ForecastPeriod` | `apps/sales/models/SalesForecasting/ForecastPeriods.py` | exists |
| `sales.CoachingScorecard` | `apps/sales/models/SalesEnablement/CoachingScorecards.py` | prefix `CSC` — **call-level** rubric scorecard (Discovery/Value-Prop/Objection/Next-Steps on one CommunicationLog) |
| `sales.CommissionEarning` / `sales.AccountPlan` / `sales.CustomerHealthScore` | 8.10 / 8.3 / 8.11 | exist |
| `accounts.User` | `apps/accounts/models.py` | `class User(AbstractBaseUser, PermissionsMixin):` = `settings.AUTH_USER_MODEL` |

### Spine entities NOT in `core` — correction to the brief

The brief listed `core.Item`/`UOM`/`StockMove`/`LotSerial` as "NOT built". That is **wrong for `scm`** and **right for `core`**:

- `apps/core/models/` → `class (Item|UOM|StockMove|LotSerial)` → **no match**. There is no `core.Item`.
- `apps/scm/models/InventoryManagement/Items.py` → `class UOM(TenantOwned):`, `class Item(TenantOwned):`
- `apps/scm/models/InventoryManagement/StockMoves.py` → `class StockMove(TenantOwned):`
- `apps/scm/models/InventoryManagement/LotSerials.py` → `class LotSerial(TenantOwned):`

Module 5 Inventory is built **under `apps/scm`**, not `apps/core`. `scm.SalesOrderLine.item` FKs `scm.Item` (PROTECT), and `scm.SalesOrderLine.description` is the free-text stand-in when no item is mapped. **8.12 does not need product-level data** (no bullet mentions product mix), so this only matters if the todo agent later adds a product/segment slice — then it should FK `scm.Item`, not invent a catalogue.

### CRITICAL: an analytics engine already exists — reuse, do not rebuild

- **`apps/sales/opportunity_analytics.py`** already ships sales-scoped aggregation helpers, all tenant-scoped:
  `sales_pipeline_rollups(tenant, *, pipeline_id, owner_id, territory_id, currency, date_from, date_to, …)`, `sales_pipeline_currency_totals(...)`, `sales_stage_age_rows(tenant, *, pipeline_id, owner_id, territory_id, currency, date_from, date_to, health, as_of, placements)` (stage-age / time-in-stage rows), `opportunity_pipeline_health(opportunity, …)`, `opportunity_pipeline_health_projection(...)`, `sales_health_counts(...)`, **`sales_win_loss_rows(tenant, *, pipeline_id, owner_id, territory_id, currency, date_from, date_to)`** (grouped by result + reason), `sales_competitor_rows(tenant, …)`.
- **`apps/crm/analytics.py`** ships a saved-report/widget engine: `WIDGET_METRICS`, `compute_widget(widget)`, `compute_report(report)`, `REPORT_COMPUTERS` with `_compute_funnel(report, tenant, start, end)`, `_compute_sales_performance(...)`, `_compute_sales_activity(...)`; `crm.AnalyticsReport` has `report_type` (REPORT_TYPE_CHOICES incl. `sales_activity`), `date_range` (ANALYTICS_RANGE_CHOICES), `group_by` (REPORT_GROUP_CHOICES).

**Consequence for 8.12:** the console/dashboard pages must be *thin renderers over these helpers*, and 8.12 must **not** build a second report builder, a second widget engine, or a second win/loss aggregation. This is the L36 ownership rule applied to the analytics layer.

### CRITICAL: no stage-transition history table exists

Grep for `stage_changed_at|StageHistory|stage_history|OpportunityStageChange` across `apps/` returns **no history model** — only:
- `crm.Opportunity.stage_changed_at` (single timestamp, system-stamped on the *last* stage transition, `apps/crm/models/SalesForceAutomation/Opportunities.py:40`)
- `sales.OpportunityPipelinePlacement.stage_entered_at` (single timestamp for the **current** stage only, `apps/sales/models/OpportunityPipeline/Pipelines.py:313`)

There is **no table recording every stage a deal passed through, or when it left each stage.** Therefore historical time-in-stage and historical stage-to-stage conversion **cannot be derived from the current data** — only the *current* stage's age can. This is why the VCA- model below is a **persisted snapshot row** (a manager records the measured stage age for a period) rather than a live query, and why the FNL- model stores `entered_count`/`converted_count` as recorded evidence.

### Free number prefixes (verified free repo-wide)

Grep for `NUMBER_PREFIX = "…"` across all of `apps/` (350+ model classes) plus a repo-wide literal search for `"WLA"`, `"VCA"`, `"FNL"`, `"RPS"`, `"BMK"` → **no matches anywhere in `C:\xampp\htdocs\NavERP`**. All five are **FREE**.

Already taken and NOT reusable: `WLR` + `OUT` (8.2 `OpportunityOutcomes`), `CSC` (8.9 `CoachingScorecard`), `SCR` (taken **four times**: `procurement/…/Screenings.py`, `scm/…/SupplierScorecards.py`, `projects/…/ScopeChangeRequests.py`, `hrm/…/Statutoryreturn.py` — a prefix collision already exists repo-wide, so avoid `SCR`).

**Recommended new prefixes: `WLA` (win/loss debrief), `VCA` (stage velocity analysis), `FNL` (funnel conversion record), `RPS` (rep performance scorecard).**

---

## Leaders surveyed (with source links)

1. **Salesforce Sales Cloud + CRM Analytics (Tableau CRM Analytics)** — CRM-native pipeline inspection, funnel and opportunity analytics; the category's incumbent — https://www.salesforce.com/sales/analytics/ · https://help.salesforce.com/s/articleView?id=sf.analytics_insights.htm · https://developer.salesforce.com/blogs/2024/03/accelerate-sales-performance-with-salesforce-crm-analytics-pipeline-inspection
2. **HubSpot Sales Hub — Sales Analytics suite** — the most explicit report catalogue of any CRM surveyed; reports grouped as Coach Reps and Teams / Forecasts & Pipelines / Sales Outcomes — https://knowledge.hubspot.com/reports/create-sales-reports-in-the-sales-analytics-suite · https://blog.hubspot.com/sales/sales-analytics-platform · https://blog.hubspot.com/sales/sales-dashboard
3. **Gong — Revenue Intelligence** — conversation-capture-led rep coaching and revenue intelligence — https://www.gong.io/ · https://www.gong.io/resources/
4. **Clari — Revenue Intelligence & Forecasting** — pipeline inspection, forecast accuracy, revenue-workforce management — https://clari.com/ · https://clari.com/blog/
5. **Zoho Analytics — Sales Analytics** — BI-layer sales analytics with win/loss-rate and rep-performance modules, Zia natural-language querying and AI forecasting — https://www.zoho.com/analytics/sales-analytics.html
6. **Microsoft Dynamics 365 Sales Insights** — AI-driven seller intelligence: predictive lead/opportunity scoring, premium forecasting, relationship analytics, conversation intelligence — https://marketplace.microsoft.com/en-us/product/dynamics-365/mscrm.70b76f06-f739-4808-bd58-b5674a0a42d4 · https://learn.microsoft.com/en-us/dynamics365/sales/intro-admin-guide-sales-insights
7. **Pipedrive — Insights & Reports** — lightweight CRM analytics: deal-conversion (funnel vs win/loss) reports, dashboards, goals, funnel charts — https://www.pipedrive.com/en/features/insights-and-reports · https://www.pipedrive.com/en/crm/features/crm-charts · https://www.pipedrive.com/en/blog/crm-metrics
8. **Klue — competitive enablement + win/loss** — structured buyer interviews, automatic tagging of competitors/objections/friction/value drivers, themes, win/loss stories, benchmarking narrative — https://klue.com/blog/win-loss-analysis-guide
9. **Clozd — Win/Loss Analysis platform** — the dedicated win/loss specialist: decision-driver taxonomy, interviews/surveys, share-and-operationalize loop to product & marketing — https://www.clozd.com/solutions/win-loss-analysis-software · https://www.clozd.com/guides/win-loss-analysis · https://www.clozd.com/blog/product-marketing-win-loss-playbook
10. **DealHub — Sales Performance Management** — pipeline-health metric taxonomy, win rate, time-per-stage, coverage ratio, benchmarking of SPM practice — https://dealhub.io/glossary/sales-performance-management/ · https://dealhub.io/glossary/sales-metrics/

**Benchmark data sources consulted for the numbers (data, not products):** Pavilion/Ebsta B2B Sales Benchmark Report (via https://pulserevops.com/knowledge/q258 and https://prospeo.io/s/sales-analytics), RAIN Group & RepVue figures (via https://prospeo.io/s/sales-analytics), The Bridge Group / OpenView (via https://pulserevops.com/knowledge/q258), Outreach industry conversion bands (https://www.outreach.ai/resources/blog/pipeline-conversion-rate-benchmarks), and a modeling-standards reference (https://www.metabase.com/integrations/pipedrive).

---

## Feature catalog (this sub-module only)

### 1. Win/Loss Analysis — Structured debriefs, pattern detection, and actionable feedback loops to product and marketing

- **Per-deal structured debrief record (why we won/lost, in narrative form)** — a durable record per closed opportunity that a manager can read and audit, separate from the bare reason code. · seen in: Klue, Clozd · priority: **table-stakes** · spine: **new table `sales.WinLossDebrief` (WLA-)** extending `sales.OpportunityOutcome` (8.2) + `sales.WinLossReason` (8.2) + `crm.Opportunity` (CRM 1.2) by FK; reuses `core.Party` for the account · **buildable now**
- **Decision-driver tagging (positive / negative drivers, weighted, each with a buyer quote attached)** — Clozd tags each driver as helping the win or causing the loss; Klue auto-tags competitors, objections, friction and value drivers and links each theme back to the source quote. · seen in: Clozd, Klue · priority: **table-stakes** · spine: JSONField tag list on the debrief (**not** a new reason master — `sales.WinLossReason.category` already carries the 8.2 taxonomy) · **buildable now**
- **Counterfactual "what would have changed the outcome"** — a named field in both specialists' interview scripts, used to turn a loss into a product or positioning change. · seen in: Klue, Clozd · priority: **common** · spine: TextField on the debrief · **buildable now**
- **Competitor attribution on the loss** — the losing competitor is already linked from the outcome record. · seen in: Klue, Gong, Pipedrive, Salesforce · priority: **common** · spine: **reuse `sales.OpportunityCompetitor` via `OpportunityOutcome.competitor_link`** — do NOT redeclare a competitor field · **buildable now**
- **Buyer feedback capture with a direct quote and a named channel (interview / survey / email / internal review)** — the *channel* and the *quote* are recorded; the outreach, scheduling and incentive automation are not. · seen in: Clozd, Klue · priority: **common** · spine: TextField + choice field on the debrief; optional FK `crm.CommunicationLog` for a recorded conversation · **buildable now** (the automated outreach/scheduling/recording engine is **integration/later**)
- **Actionable feedback loop to product and marketing (route the insight to a team, name an owner, record the action, close the loop)** — Clozd's "share and operationalize" step and Klue's "turn insights into positioning claims, objection counters, talk tracks, roadmap epics" are the loop's terminal state, and NavERP's bullet names this explicitly. · seen in: Clozd, Klue · priority: **table-stakes** · spine: new fields on the debrief — `feedback_team`, `action_owner`, `action_items`, `actioned_on`, `status` · **buildable now**
- **Pattern detection across debriefs (win rate by reason, by competitor, by segment; which driver recurs)** — aggregated rollups over many debriefs, not a single deal. · seen in: Zoho ("Analyze win-loss rate"), Klue Insights, Gong · priority: **table-stakes** · spine: **derived read-only console** over `sales.WinLossDebrief` + `sales.OpportunityOutcome`, reusing the existing helper `sales_win_loss_rows(tenant, …)` in `apps/sales/opportunity_analytics.py` and `sales_competitor_rows(tenant, …)` · **buildable now**
- **AI theme extraction / auto-summary / auto-tagging from interview transcripts** — Klue 360° Win-Loss and Clozd's generative-AI highlight-and-tag pipeline. · seen in: Klue, Clozd · priority: **differentiator** · spine: n/a — the *fields* above are the AI's landing zone; the model is **integration/later**
- **Program-level governance (sponsorship, review cadence, participation rate)** — Clozd's "executive sponsorship, clear ownership, automated collection, regular measurement" and its published saturation guidance (≈25–30 interviews per segment; 15–30% interview participation vs 3–5% survey). · seen in: Clozd · priority: **common** · spine: `status` + `debriefed_on` on the debrief give a participation/coverage count; the program-governance record is **deferred**

### 2. Sales Velocity & Cycle Time — Time-in-stage analysis, bottleneck identification, and acceleration recommendations

- **Time-in-stage measured per pipeline stage** — the single most-cited velocity report across the category. · seen in: HubSpot ("Time spent in deal stage"), Metabase reference ("Time-in-stage by stage"), DealHub ("how much time they spend at each stage") · priority: **table-stakes** · spine: source data is `sales.OpportunityPipelinePlacement.stage_entered_at` + `sales.PipelineStage.target_days`; **new table `sales.StageVelocityAnalysis` (VCA-)** · **buildable now**
- **Median and p90 cycle time, never a plain average** — the reference modelling guidance states sales cycle length and deal size must be reported as medians (p50) and p90 because both distributions are right-skewed. · seen in: Metabase modelling reference · priority: **common** · spine: **deliberately no `avg_days_in_stage` field** on VCA-; store `median_days_in_stage` + `p90_days_in_stage` (+ `max_days_in_stage` for aging) · **buildable now**
- **Bottleneck identification (which stage deals dwell in longest versus its target)** — HubSpot's funnel report shows where deals are stalling; Pipedrive can trigger a workflow when a deal sits in a stage beyond a day threshold. · seen in: HubSpot, Pipedrive, DealHub · priority: **table-stakes** · spine: `is_bottleneck` + `bottleneck_rank` on VCA-, ranked against `PipelineStage.target_days`; the **console** surfaces the ranking · **buildable now**
- **Acceleration recommendation recorded against the bottleneck stage** — NavERP's bullet asks for recommendations, and every leader publishes prescriptive guidance. · seen in: DealHub, Gong, Clari · priority: **table-stakes** · spine: `recommendation` TextField on VCA- · **buildable now**
- **Pipeline velocity as a single number** — (deals × average deal value × win rate) ÷ sales cycle length. · seen in: Pipedrive, DealHub, Prospeo · priority: **common** · spine: `velocity_value` on VCA-, computed from `crm.Opportunity.amount` / `probability` / `crm.OpportunityOutcome` · **buildable now**
- **Aging of open deals (stale opportunities by current-stage age)** — a standard pipeline-hygiene table. · seen in: Metabase reference, Pipedrive, Salesforce pipeline inspection · priority: **common** · spine: **derived console** reusing `sales_stage_age_rows(tenant, …)` in `apps/sales/opportunity_analytics.py` · **buildable now**
- **Pipeline coverage ratio (open pipeline ÷ quota, with the 3–4× healthy band)** — a standard goal-gap input. · seen in: DealHub, Prospeo, Dynamics 365 (a dedicated "pipeline coverage" column) · priority: **common** · spine: derived console over `crm.Opportunity` + `sales.QuotaPlan`; coverage band is a constant, not a table · **buildable now**
- **Historical trend of cycle time over periods** — HubSpot's "Historical snapshots" and Dynamics 365's frozen snapshot concept let managers compare a pipeline between two points in time. · seen in: HubSpot, Dynamics 365 · priority: **common** · spine: `period_start`/`period_end` on VCA-; the snapshot rows *are* the history; `crm.ReportSnapshot` (CRM 1.6) is the existing freezing mechanism and is **reused, not rebuilt** · **buildable now**
- **Conversation-to-cycle correlation (talk time, call count vs cycle length)** — Gong's core promise. · seen in: Gong, Clari, Dynamics 365 conversation intelligence · priority: **differentiator** · spine: n/a — needs call/meeting telemetry NavERP does not yet capture · **integration/later**
- **AI-predicted close date / cycle length / probability** — Dynamics 365 predictive forecasting and Zoho's AI forecasting both predict the expected close date and amount for open opportunities. · seen in: Dynamics 365, Zoho Analytics · priority: **differentiator** · spine: n/a — `crm.Opportunity.probability` and `forecast_category` remain user-set · **integration/later**

### 3. Conversion Funnel Analytics — Lead-to-opportunity, opportunity-to-close, and stage-to-stage conversion rates

- **Lead-to-opportunity conversion rate** — the top-of-funnel number every surveyed product reports, with a lead journey view. · seen in: HubSpot ("Lead funnel" + "Lead journey" tab), Pipedrive ("lead conversion report", "Conversion rate by channel"), Zoho (lead source trends) · priority: **table-stakes** · spine: source `crm.Lead` + `crm.Opportunity.source_lead`; **new table `sales.FunnelConversionRecord` (FNL-)** · **buildable now**
- **Opportunity-to-close (close) rate** — · seen in: Pipedrive, Zoho, DealHub, Salesforce · priority: **table-stakes** · spine: `crm.Opportunity` + `sales.OpportunityOutcome`; recorded as `entered_count`/`converted_count` on FNL- · **buildable now**
- **Stage-to-stage conversion rate plus a skip count** — HubSpot's deal-funnel report explicitly counts "the number of skips when a deal doesn't follow the typical deal stage chronology" alongside conversion rates. · seen in: HubSpot, Pipedrive, Metabase reference · priority: **table-stakes** · spine: `sales.PipelineStage.sequence` (the normal chronology) + `from_stage`/`to_stage` FKs on FNL- + a `skipped_count` field · **buildable now**
- **Drop-off count per stage (how many entered but did not convert)** — the complement of the rate; it is what makes a rate actionable. · seen in: Pipedrive, HubSpot, Outreach (stage with the largest gap versus peers is where attention goes) · priority: **table-stakes** · spine: `dropoff_count` on FNL-, computed from entered − converted · **buildable now**
- **Elapsed time per funnel segment** — HubSpot's lead funnel tracks "the time it takes from initial contact to deal conversion". · seen in: HubSpot, Outreach (rolling 90/180-day measurement window) · priority: **common** · spine: `avg_cycle_days` on FNL- + `period_start`/`period_end` · **buildable now**
- **Funnel waterfall (stage-by-stage counts and values)** — HubSpot's "Deal pipeline waterfall" and Pipedrive's funnel chart both visualise the drop between stages. · seen in: HubSpot, Pipedrive, Salesforce · priority: **common** · spine: **derived console**; `crm/analytics.py` already has `_compute_funnel(report, tenant, start, end)` — **reuse it** · **buildable now**
- **Conversion broken down by source / channel / territory / rep** — Pipedrive's "Conversion rate by channel" and Zoho's "trends on lead sources, campaigns, lead owners, territories". · seen in: Pipedrive, Zoho, HubSpot · priority: **common** · spine: `source_channel` CharField + `territory` FK `crm.Territory` + `owner` FK user on FNL-; the console slices by them · **buildable now**
- **Fixed denominator + fixed cohort (win rate must state won/closed vs won/created, and hold the cohort constant)** — an explicit methodological rule in the reference modelling guidance, without which a win rate is not comparable. · seen in: Metabase reference · priority: **common** · spine: `funnel_scope` choice + `entered_count`/`converted_count` recorded as the *stated* denominator on FNL- · **buildable now**
- **Rolling measurement window (90 or 180 days) rather than a single quarter** — single-quarter snapshots are too volatile to benchmark. · seen in: Outreach · priority: **common** · spine: `period_start`/`period_end` on FNL- · **buildable now**
- **Historical funnel snapshots for period-over-period comparison** — · seen in: HubSpot, Dynamics 365 · priority: **common** · spine: FNL- rows are the snapshots; `crm.ReportSnapshot` already freezes a computed result — **reuse, don't rebuild** · **buildable now**
- **Industry conversion bands to compare against** — Outreach publishes per-industry MQL→SQL and opportunity→close bands (MQL→SQL typically 25–45%, opportunity→close 25–50%; enterprise SaaS materially lower at every stage). · seen in: Outreach, Prospeo · priority: **common** · spine: editable `benchmark_pct` + `benchmark_source` + `benchmark_as_of` on FNL- · **buildable now**

### 4. Rep Performance Scorecards — Activity metrics, pipeline contribution, win rates, and revenue per rep

- **Activity metrics per rep (activities logged, calls, emails, meetings, meetings booked, tasks completed, response time, team activity timeline)** — HubSpot's "Coach Reps and Teams" report group is the most complete enumeration in the category. · seen in: HubSpot, Pipedrive, Zoho · priority: **table-stakes** · spine: source `sales.ActivityLog` (8.8) + `sales.ActivityType` (kind reuses `CommunicationLog.CHANNEL_CHOICES`); **new table `sales.RepPerformanceScorecard` (RPS-)** · **buildable now**
- **Pipeline contribution per rep (deals created, pipeline value, weighted pipeline forecast)** — · seen in: HubSpot ("Deals created", "Weighted pipeline forecast"), Zoho, Salesforce · priority: **table-stakes** · spine: `crm.Opportunity.owner` / `.territory` / `.amount` / `.probability` + `sales.OpportunityPipelinePlacement.probability_override`; `crm.Opportunity.weighted_amount` already exists as a property · **buildable now**
- **Win rate per rep** — · seen in: DealHub, Zoho, Pipedrive, HubSpot · priority: **table-stakes** · spine: `crm.Opportunity` + `sales.OpportunityOutcome`; computed `win_rate_pct` on RPS- · **buildable now**
- **Revenue per rep and average deal size** — Zoho lists "sales per representative" as a core metric; HubSpot tracks closed revenue against goal. · seen in: Zoho, HubSpot, Dynamics 365 · priority: **table-stakes** · spine: `crm.Opportunity.amount` for closed-won, `scm.SalesOrder.total` for booked orders, `accounting.Currency` for the currency FK — **no second revenue ledger** (L29) · **buildable now**
- **Quota attainment and goal gap** — HubSpot's "Quota attainment" report and Dynamics 365's dedicated "gap to quota" and "pipeline coverage" columns. · seen in: HubSpot, Dynamics 365, DealHub · priority: **table-stakes** · spine: `sales.QuotaPlan` (8.7, which itself FKs `crm.SalesQuota`) + `sales.ForecastPeriod` (8.4); computed `quota_attainment_pct` + `goal_gap_value` on RPS- · **buildable now**
- **Leading vs lagging indicator split** — HubSpot's activity tracker separates leading indicators (calls, demos booked, coverage ratio) from lagging ones (quota attainment, win rate, average deal size, revenue closed), because the two are acted on at different times. · seen in: HubSpot, Gong · priority: **common** · spine: field *grouping* on RPS- (activity block = leading, outcome block = lagging), documented in the model docstring · **buildable now**
- **Ramp time for new reps** — a named metric in HubSpot's sales-analytics platform summary. · seen in: HubSpot · priority: **common** · spine: derived from the rep's first activity date in `sales.ActivityLog`; **buildable now** as a console column
- **Side-by-side peer comparison of reps and teams** — HubSpot's dashboard template compares rep performance side by side; Pipedrive's bar chart compares deal value by rep. · seen in: HubSpot, Pipedrive, Gong · priority: **table-stakes** · spine: **derived console** over RPS- rows · **buildable now**
- **Call-level coaching rubric (Discovery / Value Proposition / Objection Handling / Next Steps, talk-listen ratio, sentiment)** — **already built as `sales.CoachingScorecard` (CSC-) in 8.9 Sales Enablement.** 8.12's scorecard is a *period-level aggregate* at a different grain; it must link to the call-level rubric, not duplicate it. · seen in: Gong, Clari · priority: **common** · spine: **reuse `sales.CoachingScorecard` by FK** (optional, one per representative call) · **buildable now** (the AI sentiment/summary engine is **integration/later**)
- **Auto-captured activity from email, calendar and VoIP** — the source of every activity metric in the leaders' products. NavERP 8.8 already records the *fact* of auto-capture (`sales.ActivityLog.capture_source`, `is_auto_captured`) but ships no connector. · seen in: Gong, Clari, Dynamics 365 · priority: **differentiator** · spine: 8.8's fields are the landing zone · **integration/later**
- **AI lead/opportunity scoring and predictive rep ranking** — Dynamics 365's predictive lead and opportunity scoring, and Zoho's Zia trend/outlier detection. · seen in: Dynamics 365, Zoho, Gong · priority: **differentiator** · spine: n/a · **integration/later**

### 5. Benchmarking & Peer Comparison — Internal team comparisons, industry benchmarks, and goal-gap analysis

- **Internal team comparison (reps and teams side by side; distribution, not just a mean)** — · seen in: HubSpot, Pipedrive, Gong · priority: **table-stakes** · spine: derived console over RPS- · **buildable now**
- **Percentile benchmarking (25th / 50th / 75th percentile of 5–7 core metrics, plus a top decile)** — the standard practice for comparing to a distribution rather than a single average. · seen in: Pulserevops benchmarking guide, knowledgelib benchmark tables · priority: **common** · spine: derived console percentile computation over RPS- and FNL- · **buildable now**
- **Industry benchmark values held next to our own measured value, and the gap between them** — · seen in: Pulserevops, Prospeo, RAIN Group, RepVue · priority: **table-stakes** · spine: editable benchmark fields on the analysis records — `benchmark_pct` (FNL-), `benchmark_days` (VCA-), `benchmark_win_rate_pct` / `benchmark_cycle_days` / `benchmark_quota_attainment_pct` (RPS-) — each with `benchmark_source` + `benchmark_as_of` · **buildable now**
- **Goal-gap analysis (attainment against quota, coverage against the required multiple, our metric against the benchmark)** — Dynamics 365's gap-to-quota and coverage columns; DealHub's coverage ratio. · seen in: Dynamics 365, DealHub, HubSpot · priority: **table-stakes** · spine: computed `goal_gap_value` / `quota_attainment_pct` on RPS- + `sales.QuotaPlan` · **buildable now**
- **Peer-segment definition so comparisons are like-for-like** — the benchmarking guidance is explicit that a 30% attainment in enterprise is closer to normal than 30% in SMB, and that cross-segment comparison is misleading; segments are sliced by revenue range and vertical. · seen in: Pulserevops, knowledgelib · priority: **common** · spine: a `segment` CharField on RPS- and FNL- (and `crm.Territory.segment` exists for a geographic slice) · **buildable now**
- **Benchmark cadence and data-vintage labelling (internal monthly vs external quarterly; vendor benchmark data lags 30–60 days)** — external benchmark feeds are too lagged to be compared monthly, so the as-of date must be carried on the record. · seen in: Pulserevops · priority: **common** · spine: `benchmark_as_of` DateField on the analysis records · **buildable now**
- **Revenue concentration (a small share of reps drives the majority of revenue)** — the Pavilion/Ebsta benchmark reports that a small minority of reps produce the large majority of revenue, and that the top-vs-peer velocity gap is widening. · seen in: Pavilion/Ebsta via Prospeo and Pulserevops · priority: **differentiator** · spine: derived console (concentration curve over RPS- `revenue_closed`) · **buildable now**
- **External benchmark data ingestion (Pavilion/Ebsta cohort snapshots, Bridge Group trends, OpenView compression reports)** — · seen in: Pulserevops · priority: **differentiator** · spine: the *values* are entered manually into the benchmark fields above; the **automated feed is integration/later**

### Beyond the bullets

- **Data-quality and pipeline-hygiene alerts (coverage below threshold, deals with no next step, stale opportunities, unworked leads)** — Zoho's "set data alerts", Pipedrive's stage-dwell workflow trigger, and Salesforce pipeline inspection's "deal health" signals. · seen in: Zoho, Pipedrive, Salesforce, Gong · priority: **common** · spine: `apps/sales/opportunity_analytics.py` already computes `opportunity_pipeline_health_projection(...)` and `sales_health_counts(...)` with a `SALES_HEALTH_CHOICES` band — **reuse it** for a derived alerts panel on the console · **buildable now** (the email/slack dispatch is **integration/later**)
- **Outlier and anomaly detection across reps and periods** — Zoho identifies trends and outliers automatically; Dynamics 365's relationship analytics surfaces "relationship health and risks". · seen in: Zoho, Dynamics 365 · priority: **common** · spine: derived console (IQR / z-score over RPS- values) · **buildable now**
- **Natural-language querying of sales data** — Zoho's Zia turns a typed question into a report and KPI widget; Pipedrive generates reports from a text prompt; Dynamics 365 exposes the same via Copilot prompts. · seen in: Zoho, Pipedrive, Dynamics 365 · priority: **differentiator** · spine: n/a — NavERP's `crm.AnalyticsReport` is the saved-report engine a natural-language layer would target · **integration/later**
- **Scheduled report delivery by email, plus mobile access** — Zoho schedules dashboards to be emailed automatically; HubSpot offers scheduled reports and mobile access. · seen in: Zoho, HubSpot · priority: **common** · spine: n/a · **integration/later**
- **BI / warehouse export (Tableau, Power BI, Snowflake, DOMO)** — Clozd ships native connections to Tableau, Power BI and DOMO; Zoho ships 75+ pre-built dashboards with connectors. · seen in: Clozd, Zoho · priority: **differentiator** · spine: n/a — NavERP's `crm.AnalyticsReport` JSON result payload is the natural export surface · **integration/later**
- **What-if scenario modelling and forecast compression analysis** — Anaplan's "what if" multi-dimensional modelling and OpenView's compression reports. · seen in: Anaplan (via the Microsoft Marketplace listing), OpenView (via Pulserevops) · priority: **differentiator** · spine: n/a · **deferred**
- **Custom dashboard builder / embeddable white-labelled dashboards** — Zoho's white-label embedded analytics; Pipedrive's shareable public dashboard links. · seen in: Zoho, Pipedrive · priority: **common** · spine: `crm.AnalyticsDashboard` + `crm.DashboardWidget` (CRM 1.6) already own this · **parked to 1.6 / deferred**

---

## Recommended build scope (this pass — 1–4 models)

Four new tenant-scoped models, one per analytic grain, all built on `apps/sales/models/_base.py` `TenantNumbered`, all in a new package `apps/sales/models/SalesAnalytics/`, all registered in the `apps/sales/models/__init__.py` re-export block (L-rule: a model without a re-export is an `ImportError`).

### 1. `WinLossDebrief` [WLA-] — `apps/sales/models/SalesAnalytics/WinLossDebriefs.py`

**Bullet 1.** Fields justified by: per-deal structured debrief (table-stakes) · decision-driver tagging (table-stakes) · counterfactual "what would have changed the outcome" (common) · buyer quote + interview channel (common) · actionable feedback loop to product/marketing (table-stakes).

- `opportunity` → `crm.Opportunity` (PROTECT) — the deal under debrief
- `outcome` → `sales.OpportunityOutcome` (PROTECT, null=True) — **extends 8.2's outcome record; never a second outcome table**
- `primary_reason` → `sales.WinLossReason` (PROTECT, null=True) — **8.2's catalogue; never a second reason table**
- `account` → `core.Party` (SET_NULL, null=True) — customer role
- `interviewer` → `AUTH_USER_MODEL` (SET_NULL, null=True)
- `debriefed_on` (Date), `interview_channel` (choice: interview / survey / email_review / internal_debrief / analysis)
- `decision_drivers` (JSONField, default=list) — `[{"driver": str, "sentiment": "positive|negative", "weight": int, "quote": str}]`
- `buyer_quote` (Text), `counterfactual` (Text) — "what would have changed the outcome"
- `feedback_team` (choice: product / marketing / sales / finance / operations / other) — the feedback-loop target
- `action_owner` → `AUTH_USER_MODEL` (SET_NULL, null=True), `action_items` (Text), `actioned_on` (Date, null)
- `status` (choice: draft / submitted / shared / actioned / closed), `notes` (Text)

### 2. `StageVelocityAnalysis` [VCA-] — `apps/sales/models/SalesAnalytics/StageVelocityAnalyses.py`

**Bullet 2.** Fields justified by: time-in-stage (table-stakes) · median+p90-not-average (common) · bottleneck identification (table-stakes) · acceleration recommendation (table-stakes) · pipeline velocity formula (common) · benchmark value + vintage for bullet 5 (table-stakes).

- `pipeline` → `sales.Pipeline` (PROTECT), `pipeline_stage` → `sales.PipelineStage` (PROTECT) — the unit of time-in-stage
- `period_start`, `period_end` (Date) — the measured window
- `opportunity_count` (PositiveInteger)
- `median_days_in_stage` (Decimal 8,2), `p90_days_in_stage` (Decimal 8,2), `max_days_in_stage` (PositiveInteger) — **no plain-average field, by design**
- `sales_cycle_days` (Decimal 8,2) — median full cycle for the deals that passed through
- `velocity_value` (Decimal 16,2) — (deals × avg deal value × win rate) ÷ cycle days
- `is_bottleneck` (Boolean), `bottleneck_rank` (PositiveSmallInteger, null) — ranked against `PipelineStage.target_days`
- `recommendation` (Text) — the acceleration recommendation
- `benchmark_days` (Decimal 8,2, null), `benchmark_source` (Char, blank), `benchmark_as_of` (Date, null), `segment` (Char, blank) — bullet 5 linkage
- `status` (choice: draft / reviewed / approved), `notes` (Text)

### 3. `FunnelConversionRecord` [FNL-] — `apps/sales/models/SalesAnalytics/FunnelConversionRecords.py`

**Bullet 3.** Fields justified by: lead-to-opportunity / opportunity-to-close / stage-to-stage rates (table-stakes) · skip count (table-stakes) · drop-off count (table-stakes) · elapsed time per segment (common) · fixed denominator (common) · rolling window (common) · breakdown dimensions (common) · industry benchmark band (common).

- `label` (Char 160) — the human name of the measured segment
- `funnel_scope` (choice: lead_to_opportunity / opportunity_to_close / stage_to_stage / overall)
- `from_stage` / `to_stage` → `sales.PipelineStage` (SET_NULL, null) — the normal chronology is `PipelineStage.sequence`
- `territory` → `crm.Territory` (SET_NULL, null), `owner` → `AUTH_USER_MODEL` (SET_NULL, null), `source_channel` (Char, blank) — the breakdown dimensions
- `period_start`, `period_end` (Date) — the rolling measurement window
- `entered_count`, `converted_count` (PositiveInteger) — the *stated* denominator
- `conversion_rate_pct` (Decimal 5,2) — computed in `save()` from entered/converted
- `dropoff_count` (PositiveInteger) — computed (entered − converted)
- `skipped_count` (PositiveInteger) — deals that did not follow the stage chronology
- `avg_cycle_days` (Decimal 8,2) — elapsed time for this segment
- `benchmark_pct` (Decimal 5,2, null), `benchmark_source` (Char, blank), `benchmark_as_of` (Date, null), `segment` (Char, blank)
- `notes` (Text)

### 4. `RepPerformanceScorecard` [RPS-] — `apps/sales/models/SalesAnalytics/RepPerformanceScorecards.py`

**Bullet 4**, and the *measurement* half of Bullet 5 (goal-gap + peer comparison data). Fields justified by: activity metrics (table-stakes) · pipeline contribution (table-stakes) · win rate (table-stakes) · revenue per rep (table-stakes) · quota attainment & goal gap (table-stakes) · leading-vs-lagging split (common) · ramp time (common) · benchmark values (table-stakes).

- `rep` → `AUTH_USER_MODEL` (PROTECT), `territory` → `crm.Territory` (SET_NULL, null), `manager` → `AUTH_USER_MODEL` (SET_NULL, null)
- `period_start`, `period_end` (Date), `forecast_period` → `sales.ForecastPeriod` (SET_NULL, null), `quota_plan` → `sales.QuotaPlan` (SET_NULL, null)
- *Leading indicators (activity):* `activities_logged`, `calls_logged`, `emails_logged`, `meetings_logged`, `meetings_booked`, `follow_ups_completed` (PositiveInteger), `activity_minutes` (PositiveInteger), `response_time_hours` (Decimal 6,2, null)
- *Pipeline contribution:* `opportunities_created`, `opportunities_won`, `opportunities_lost` (PositiveInteger), `pipeline_value`, `weighted_pipeline_value` (Decimal 16,2)
- *Lagging indicators (outcomes):* `win_rate_pct` (Decimal 5,2, computed), `revenue_closed` (Decimal 16,2), `currency` → `accounting.Currency` (SET_NULL, null), `average_deal_size` (Decimal 14,2), `sales_cycle_days` (Decimal 8,2)
- *Goal gap:* `quota_target` (Decimal 16,2), `quota_attainment_pct` (Decimal 6,2, computed), `goal_gap_value` (Decimal 16,2, computed)
- `overall_score` (Decimal 5,2), `rating` (choice: outstanding / strong / on_track / needs_improvement / underperforming)
- `strengths` (Text), `areas_for_improvement` (Text), `coaching_actions` (Text)
- *Benchmark:* `benchmark_win_rate_pct`, `benchmark_cycle_days`, `benchmark_quota_attainment_pct` (Decimal, null), `benchmark_source` (Char, blank), `benchmark_as_of` (Date, null), `segment` (Char, blank)
- `status` (choice: draft / shared / acknowledged / approved), `notes` (Text)
- Optional FK `coaching_scorecard` → `sales.CoachingScorecard` (8.9, SET_NULL, null) — links the period aggregate to the call-level rubric **without duplicating it**

### Derived read-only console pages (no new models)

Following the 8.11 `health_console` / 8.9 `boards/` precedent, and **reusing `apps/sales/opportunity_analytics.py` + `apps/crm/analytics.py` rather than writing new aggregation**:

| Page | Bullet | Content | Reuses |
|---|---|---|---|
| `sales:analytics_console` | landing | KPI tiles + links to the five bullet views | `sales_health_counts`, `crm/analytics.py` widget engine |
| `sales:win_loss_console` | 1 | Win rate by reason / competitor / segment; recurring decision drivers; open feedback actions | `sales_win_loss_rows`, `sales_competitor_rows` |
| `sales:velocity_console` | 2 | Bottleneck ranking (median & p90 days vs `PipelineStage.target_days`), aging table, velocity trend | `sales_stage_age_rows`, `sales_pipeline_rollups` |
| `sales:funnel_console` | 3 | Stage-by-stage waterfall, drop-off and skip counts, our rate vs benchmark | `crm/analytics.py::_compute_funnel` |
| `sales:rep_scorecard_console` | 4 | Rep leaderboard (activity, pipeline, win rate, revenue), team rollup | RPS- rows + `sales.ActivityLog` |
| `sales:benchmark_console` | 5 | Internal team comparison, percentile bands, our metric vs industry benchmark, goal-gap | RPS-/FNL-/VCA- benchmark fields + `sales.QuotaPlan` |

### Recommended `LIVE_LINKS["8.12"]` (one entry in `apps/core/navigation.py`)

```python
"8.12": {
    # OWNERSHIP RULING (L36/L37)
    # EXTENDS (never redeclares) Sales 8.2 WinLossReason (WLR-) + OpportunityOutcome (OUT-);
    # EXTENDS Sales 8.9 CoachingScorecard (CSC-) by FK. Reuses crm.Opportunity (OPP-),
    # crm.Lead (LEAD-), crm.Territory, crm.CommunicationLog (COM-), crm.AnalyticsReport /
    # AnalyticsDashboard / DashboardWidget / ReportSnapshot (CRM 1.6 report engine),
    # sales.Pipeline (PIP-) / PipelineStage (target_days) / OpportunityPipelinePlacement
    # (stage_entered_at), sales.ActivityLog (SAL-) / ActivityType, sales.QuotaPlan (QPA-),
    # sales.ForecastPeriod, and accounting.Currency. Reuses the sales analytics helpers in
    # apps/sales/opportunity_analytics.py. Zero duplicate reason, outcome, report, widget,
    # quota, currency, activity or competitor models declared.
    "Win/Loss Analysis": "sales:win_loss_console",
    "Sales Velocity & Cycle Time": "sales:velocity_console",
    "Conversion Funnel Analytics": "sales:funnel_console",
    "Rep Performance Scorecards": "sales:rep_scorecard_console",
    "Benchmarking & Peer Comparison": "sales:benchmark_console",
    # Extra live leaves
    "Sales Analytics Console": "sales:analytics_console",
    "Win/Loss Debriefs": "sales:win_loss_debrief_list",
    "Stage Velocity Analyses": "sales:stage_velocity_analysis_list",
    "Funnel Conversion Records": "sales:funnel_conversion_record_list",
    "Rep Performance Scorecards": "sales:rep_performance_scorecard_list",
},
```

The five NavERP bullet names map 1:1 onto five **distinct** console destinations, satisfying the human-sidebar-pass rule (L30). The four model list pages are "extra live leaves", as in 8.9/8.10/8.11.

### Template paths (per the one-folder-per-sub-module → one-folder-per-entity rule)

- `templates/sales/salesanalytics/winlossdebrief/{list,detail,form}.html`
- `templates/sales/salesanalytics/stagevelocityanalysis/{list,detail,form}.html`
- `templates/sales/salesanalytics/funnelconversionrecord/{list,detail,form}.html`
- `templates/sales/salesanalytics/repperformancescorecard/{list,detail,form}.html`
- `templates/sales/salesanalytics/boards/{analytics_console,win_loss_console,velocity_console,funnel_console,rep_scorecard_console,benchmark_console}.html`

### Backend package layout (absolute imports, re-exported)

- `apps/sales/models/SalesAnalytics/{WinLossDebriefs,StageVelocityAnalyses,FunnelConversionRecords,RepPerformanceScorecards}.py` + `__init__.py`
- `apps/sales/forms/SalesAnalytics/…`, `apps/sales/views/SalesAnalytics/…`, `apps/sales/urls/SalesAnalytics/…`
- Add the four names to the `apps/sales/models/__init__.py` import block **and** `__all__`.
- Migration: `0023_salesanalytics.py` (next free number).

### House rules that bind this build

- Every list page: search (`q`) + filters + pagination (15/page) + an Actions column (view / edit / delete, delete POST-only with `confirm()` and `{% csrf_token %}`). FK filters compare integer pks with `|stringformat:"d"`, never `|slugify`.
- Every filter dropdown needs its choices/queryset **passed explicitly** by the view (`status_choices`, `*_choices`, FK querysets, `stats` dict) — never assumed in the template.
- Badges use colour-named classes only: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`. `badge-success/danger/warning` **do not exist** in `static/css/theme.css` (L33).
- Views filter every queryset by `tenant=request.tenant`; FK targets validated to the same tenant in `clean()` (the 8.2 `OpportunityOutcome.clean()` pattern).
- `status`/`decided` style fields are the only editable ones; computed values (`conversion_rate_pct`, `win_rate_pct`, `quota_attainment_pct`, `goal_gap_value`, `dropoff_count`) are `editable=False` and set in `save()`.
- One file per commit, PowerShell-safe (`git add 'file'; git commit -m 'msg'`), never `git push`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Call-level coaching rubric, talk-listen ratio, call sentiment, transcript summary** → **8.9 Sales Enablement** — already built as `sales.CoachingScorecard` (CSC-). 8.12 links to it by FK and must not redeclare it.
- **Competitive battlecards, competitor profiles, SWOT, deal tips** → **8.9 Sales Enablement** (`sales.CompetitorProfile`, `sales.OpportunityCompetitor`) and 8.2's competitive intelligence. 8.12 only *reads* competitor attribution.
- **Win/loss reason catalogue and the per-opportunity outcome record** → **8.2 Opportunity & Pipeline Management** (`sales.WinLossReason`, `sales.OpportunityOutcome`). 8.12 extends both by FK.
- **Forecast submissions, scenarios, adjustments, forecast categories** → **8.4 Sales Forecasting** (`sales.ForecastSubmission`, `ForecastPeriod`, `ForecastScenario`, `ForecastAdjustment`). 8.12's benchmark and quota-gap views read the quota/period; they do not re-forecast.
- **Quota plans, quota allocation, territory membership, territory rules** → **8.7 Territory & Quota Management** (`sales.QuotaPlan`, `sales.TerritoryMember`, `sales.TerritoryRule`) and `crm.SalesQuota` / `crm.Territory` (CRM 1.2).
- **Commission plans, earnings, statements, clawbacks** → **8.10 Incentive Compensation Management** (`sales.CommissionPlan`, `CommissionEarning`, `CommissionStatement`). 8.12's revenue-per-rep figure is a *read* of opportunity/order revenue, not a payout calculation.
- **Customer health scores, renewals, onboardings, QBRs, advocacy** → **8.11 Customer Success & Account Management**. 8.12's win/loss debrief may reference the account but never re-scores health.
- **Campaign influence, MQL-to-SQL handoff, attribution touchpoints, content performance, events** → **8.13 Marketing Alignment & Attribution**. 8.12's *feedback loop to marketing* is the hand-off point; the attribution engine itself is 8.13's.
- **Sales activity capture, tasks, templates, plan cycles, activity goals** → **8.8 Sales Activity & Task Management** (`sales.ActivityLog`, `ActivityType`, `SalesPlanCycle`, `ActivityGoal`). 8.12 *aggregates* activities into a scorecard; it never owns the activity master.
- **Quotes, proposals, CPQ, product catalogue, bundles, approval rules** → **8.5 Quote & Proposal Management (CPQ)**. Note `crm.QuoteLine.product` is a CRM Product, a different table from `scm.Item`, with no mapping between them (see the `scm.SalesOrderLine.item` docstring).
- **Order master, order lines, order holds, amendments, revenue schedules** → **8.6 Order Management** (which itself extends `scm.SalesOrder`). 8.12 reads `scm.SalesOrder.total` for booked revenue only.
- **Saved-report / dashboard / widget / snapshot engine** → **CRM 1.6 Analytics & Reporting** (`crm.AnalyticsReport`, `AnalyticsDashboard`, `DashboardWidget`, `ReportSnapshot`; `apps/crm/analytics.py`). 8.12 renders over it; it does not build a second one.
- **Financial ledger, invoices, payments, currency, budget** → **Accounting Module 2** (`apps/accounting/…`). 8.12 FKs `accounting.Currency` by string and never builds a second ledger (L29).
- **Enablement content, certifications, playbooks** → **8.9**; **items, stock moves, lots/serials** → **Module 5 under `apps/scm`** (`scm.Item`, `scm.UOM`, `scm.StockMove`, `scm.LotSerial`).

---

## Deferred (later passes / integrations)

- **AI win/loss theme extraction, auto-summarisation, auto-tagging of interview transcripts** — Klue 360° Win-Loss, Clozd's generative-AI pipeline. Deferred: needs a model and a transcript corpus. The debrief's `decision_drivers` / `buyer_quote` fields are the landing zone.
- **Conversation intelligence (call recording, transcription, talk-listen ratio, sentiment, AI call scoring)** — Gong, Clari, Dynamics 365 conversation intelligence. Deferred: needs a call-recording store and an ASR/NLP pipeline. 8.9's `CoachingScorecard.recording_url` and `transcript_summary` are the placeholder.
- **Email / calendar / VoIP activity auto-capture** — Gong, Clari, Dynamics 365. Deferred: needs external OAuth connectors. 8.8's `ActivityLog.capture_source` / `is_auto_captured` already record the *fact* of a capture so the connector can land there.
- **AI predictive lead / opportunity scoring, predicted close date, predicted cycle length, Zia-style natural-language querying, AI rep ranking** — Dynamics 365 predictive scoring, Zoho Zia, Pipedrive AI reporting. Deferred: model-dependent. `crm.Opportunity.probability` / `forecast_category` stay user-set.
- **Automated win/loss interview outreach, scheduling, incentives, recording and distribution** — Clozd's managed program. Deferred: needs an email/scheduler/incentive stack. 8.12 records the *channel* and the *quote* only.
- **External benchmark data ingestion (Pavilion/Ebsta cohort snapshots, Bridge Group trends, OpenView compression reports, RAIN Group / RepVue feeds)** — Deferred: no public API, 30–60 day lag, licensing. The benchmark values are entered manually into `benchmark_*` + `benchmark_source` + `benchmark_as_of` this pass.
- **Scheduled report/dashboard email delivery and mobile access** — Zoho, HubSpot. Deferred: needs a mailer task and a responsive layout.
- **BI / warehouse export (Tableau, Power BI, Snowflake, DOMO) and white-label embedded dashboards** — Clozd, Zoho. Deferred: `crm.AnalyticsReport`'s JSON result payload is the natural export surface; the dashboard builder is CRM 1.6's.
- **Custom dashboard builder and shareable public dashboard links** — Zoho white-label, Pipedrive public links. Parked to CRM 1.6.
- **What-if scenario modelling and forecast compression analysis** — Anaplan, OpenView. Deferred: a modelling layer over the ledger, well beyond a sub-module.
- **Historical stage-transition history** — **not a deferral, a known spine gap**: no table records every stage a deal passed through. VCA- rows are the persisted snapshot that fills it going forward. If a later pass wants true historical time-in-stage, a stage-transition history model must be added to `crm.Opportunity` (out of 8.12's ownership). Record this in the gaps file.
- **Multi-currency revenue aggregation across reps and periods** — `crm.Opportunity.currency` is per-opportunity, so a scorecard must be single-currency; a cross-currency leaderboard needs FX rates NavERP does not yet hold. Deferred; `accounting.Currency` is the only FK.
- **Ramp-time tracking as a stored metric** — derived today from the rep's first `sales.ActivityLog`; if it needs to be snapshotted per period it becomes a field on RPS-.

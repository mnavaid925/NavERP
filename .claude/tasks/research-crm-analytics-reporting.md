# Research — Module 1.6: Analytics & Reporting (crm-analytics-reporting)

## Context: this is an extension, not greenfield

The CRM app (`apps/crm`) is already built through sub-module 1.5. The following models exist and supply all raw
data for 1.6 analytics — they must NOT be re-modeled, only queried:

| Existing model | Key analytics fields |
|---|---|
| `Lead` | `status`, `source`, `rating`, `score`, `owner`, `created_at`, `converted_party` |
| `Opportunity` | `stage`, `amount`, `probability`, `forecast_category`, `close_date`, `owner`, `territory`, `campaign`, `source_lead`, `stage_changed_at`, `lost_at`, `loss_reason`, `competitor`, `weighted_amount` |
| `SalesQuota` | `owner`, `territory`, `period_type`, `period_year`, `period_number`, `target_amount` |
| `Case` | `status`, `priority`, `type`, `origin`, `owner`, `resolved_at`, `first_responded_at`, `first_response_due`, `resolution_due`, `closed_at`, `satisfaction_rating`, `sla_policy` |
| `CrmTask` | `status`, `task_type`, `priority`, `owner`, `due_at`, `completed_at`, `recurrence` |
| `Campaign` | `status`, `type`, `budget`, `actual_cost`, `expected_revenue`, `start_date`, `end_date` |
| `CampaignMember` | `status`, `responded`, `campaign`, `party` |
| `Survey` / `HealthScore` | satisfaction/NPS signals |
| `CommunicationLog` | `direction`, `channel`, `duration_seconds`, `owner`, `party` |
| `CalendarEvent` | meeting counts per owner |

The planned build scope is exactly **4 tenant-scoped models** plus a compute helper:
1. `AnalyticsDashboard` — per-user/shared dashboard container
2. `DashboardWidget` — individual widget pinned to a dashboard
3. `AnalyticsReport` — saved report definition (type + filters + date range)
4. `ReportSnapshot` — point-in-time materialized result of a report (for trending)
5. `apps/crm/analytics.py` — pure-Python query functions that produce numbers (no new tables)

---

## Leaders surveyed (with source links)

1. **Salesforce CRM / Reports & Dashboards / CRM Analytics** — market leader; four report formats, five dashboard component types, dynamic dashboards, historical snapshots, AI-generated formulas — [Salesforce Reporting Guide](https://metricasoftware.com/salesforce-reporting-guide-reports-dashboards-crm-analytics-and-enterprise-bi/)
2. **HubSpot Sales Hub (Reports & Dashboards)** — multi-hub attribution, sales analytics suite (deals/activities/forecast/leads), AI natural-language report builder, scheduled Slack/email digests, drag-and-drop dashboard editor — [HubSpot Reporting & Dashboards](https://www.hubspot.com/products/reporting-dashboards)
3. **Zoho CRM Analytics + Zoho Analytics** — 50+ chart types, funnel analysis, leaderboard, Ask Zia (AI), 40+ standard reports, KPI cards, heat maps — [Zoho CRM Analytics Capabilities](https://www.zoho.com/crm/analytics-capabilities.html)
4. **Pipedrive Insights** — 7 report categories (activities, campaigns, contacts, leads, deals, revenue forecast, projects), drag-and-drop dashboard grid, goals/targets, public shareable links, AI report generation — [Pipedrive Insights: Report Types](https://support.pipedrive.com/en/article/insights-report-types)
5. **Microsoft Dynamics 365 Sales** — pre-built Sales Activity, Sales Performance, Sales Manager Summary dashboards; funnel chart on every dashboard; Power BI embedded; interactive visual filters; leaderboard widget — [Dynamics 365 Sales Dashboards](https://learn.microsoft.com/en-us/dynamics365/sales/dashboards)
6. **Zendesk Explore** — pre-built support analytics: ticket volume, SLA compliance, CSAT scores, agent performance, first resolution / full resolution time, one-touch ticket rate; custom metric builder; real-time updates — [Zendesk: Analyzing ticket activity & agent performance](https://support.zendesk.com/hc/en-us/articles/4408835846810-Analyzing-your-Support-ticket-activity-and-agent-performance)
7. **Salesforce Service Cloud Analytics** — CSAT, NPS, CES, FCR, average handle time, case volume, SLA adherence rate, SLA breach rate, escalation rate, backlog — [Service Cloud metrics guide](https://thiagoterzi.gitbook.io/measure-success-in-salesforce-service-cloud)
8. **Freshsales (Sales Analytics)** — Sales Essentials Dashboard (out-of-the-box), activity widgets (tasks by type/outcome/owner, meetings by outcome), deal performance, revenue forecasts, lead funnel — [Freshsales sales analytics](https://www.freshworks.com/crm/features/sales-analytics/)
9. **monday CRM (Dashboards)** — 30+ widgets (pipeline, leaderboard, conditional labels, funnel, bar, line, pie, scatter), real-time live data from boards, role-based access, seven dashboard archetypes (pipeline/revenue/team/lead/journey/activity/executive) — [monday.com Dashboards & Reporting](https://monday.com/features/dashboards)
10. **Insightly CRM** — ~50 card types including maps, gauges, bar/line charts, drill paths (click-through drill-down), scheduled auto-email of reports, shared/private folders, mobile access — [Insightly Dashboards & Reporting](https://www.insightly.com/crm/dashboards-and-reporting/)
11. **Copper CRM** — pipeline report with five views, pre-built one-click templates, KPI cards, automated alerts/scheduling, direct Google Sheets/Data Studio export, four-times-daily data refresh — [Copper Sales Reporting](https://www.copper.com/sales-reporting)

---

## Feature catalog by sub-module

### 1.6.A Dashboards

- **KPI Summary Card (metric widget)** — single numeric value with optional trend arrow (e.g., "42 Deals Won this quarter, +12% vs. last"). Seen in: Salesforce, HubSpot, Zoho CRM, Pipedrive, monday, Insightly, Copper, Dynamics 365. Priority: **table-stakes**. Spine: `DashboardWidget` (widget_type='kpi_card', metric_key, optional period_type). Buildable now.

- **Bar/Column Chart Widget** — compare a metric across categories (reps, stages, sources, territories). Seen in: all 10 leaders. Priority: **table-stakes**. Spine: `DashboardWidget` (widget_type='bar_chart'). Buildable now — rendered as Chart.js in template via HTMX JSON endpoint.

- **Line/Area Chart Widget** — show metric over time (weekly pipeline value, monthly revenue). Seen in: Salesforce, HubSpot, Zoho, Pipedrive, monday, Dynamics 365. Priority: **table-stakes**. Spine: `DashboardWidget` (widget_type='line_chart'). Buildable now.

- **Funnel Chart Widget** — stage-by-stage count and value showing drop-off rates (Lead → Opportunity → Proposal → Closed Won). Seen in: Salesforce, HubSpot, Zoho, Pipedrive, Dynamics 365 (every sales dashboard includes a funnel chart), monday, Freshsales. Priority: **table-stakes**. Spine: `DashboardWidget` (widget_type='funnel'). Buildable now — aggregated from `Lead.status` + `Opportunity.stage` in analytics.py.

- **Gauge Widget** — dial or progress bar showing a single value against a target or threshold (quota attainment %). Seen in: Salesforce, Zoho, Insightly (listed as a card type), Dynamics 365. Priority: **common**. Spine: `DashboardWidget` (widget_type='gauge', target_value). Buildable now.

- **Leaderboard / Data Table Widget** — ranked list of users by a metric (top reps by revenue, most calls made). Seen in: Zoho CRM, Dynamics 365 (Sales Professional Summary), HubSpot, monday, Pipedrive, Freshsales. Priority: **common**. Spine: `DashboardWidget` (widget_type='leaderboard'). Buildable now.

- **Pie / Donut Chart Widget** — proportional breakdown (leads by source, cases by type). Seen in: Zoho, Pipedrive, monday, Dynamics 365, HubSpot. Priority: **common**. Spine: `DashboardWidget` (widget_type='pie_chart'). Buildable now.

- **Per-User Dashboard Container** — each user gets their own default dashboard; multiple named dashboards per tenant/user. Seen in: Salesforce (personal dashboards), HubSpot, Pipedrive, monday, Dynamics 365 (set-as-default). Priority: **table-stakes**. Spine: `AnalyticsDashboard` (owner FK to User, is_default bool, is_shared bool). Buildable now.

- **Dashboard Sharing** — mark a dashboard as shared (visible to all tenant users, or specific roles). Seen in: HubSpot (public/private), Pipedrive (public view-only link), Insightly (shared folders), Copper, monday. Priority: **common**. Spine: `AnalyticsDashboard` (visibility choices: private/team/tenant). Buildable now.

- **Drag-and-Drop Layout Builder** — free-form grid drag to reorder/resize widgets on the dashboard. Seen in: HubSpot, Pipedrive (move/resize icons), monday, Salesforce (Flex dashboards). Priority: **differentiator**. Spine: `DashboardWidget` (position_x, position_y, width, height — store layout). Integration/later: requires sortable.js or similar JS library; store grid positions but defer the live JS builder to a future sprint.

- **Date Range / Period Filter on Dashboard** — global time-range selector per dashboard (This Week / This Month / This Quarter / This Year / Custom). Seen in: all leaders. Priority: **table-stakes**. Spine: `AnalyticsDashboard` (default_period field) or per-widget override. Buildable now — passed as query param to analytics.py functions.

- **Role-Based / Audience Dashboards** — separate dashboard personas: Sales Rep, Sales Manager, Executive, Service Agent. Seen in: Dynamics 365 (Sales Activity vs. Sales Manager Summary vs. Sales Professional), HubSpot, Freshsales (Sales Essentials), Zoho, monday. Priority: **common**. Spine: `AnalyticsDashboard` (audience tag choices: rep/manager/executive/service). Buildable now — pre-seeded dashboards for each role.

- **Real-Time Live Data** — widgets query current DB on page load (no overnight refresh). Seen in: monday, HubSpot, Zendesk Explore, Freshsales, Insightly. Priority: **table-stakes**. Spine: analytics.py functions called by HTMX endpoints at request time. Buildable now — Django ORM aggregates; no separate data store needed.

- **Widget Configuration (metric + dimension + filter)** — each widget stores what it measures (metric_key), how it's grouped (dimension_key), and any extra filter (e.g., status=closed_won). Seen in: Pipedrive (measure-by / view-by / segment-by), HubSpot, Zoho, Salesforce. Priority: **table-stakes**. Spine: `DashboardWidget` (metric_key, dimension_key, filter_json). Buildable now with a fixed catalog of metric_key choices.

### 1.6.B Standard Reports

- **Sales Activity Report** — count of calls, emails, meetings, tasks per rep per period; activity completion rates. Seen in: Salesforce, HubSpot (Activities & Leads suite), Pipedrive (Activities Performance), Zoho, Dynamics 365, Freshsales, Copper. Priority: **table-stakes**. Spine: `AnalyticsReport` (report_type='sales_activity'); aggregates `CrmTask`, `CommunicationLog`, `CalendarEvent` by owner and date range. Buildable now.

- **Sales Performance / Top Performers Report** — revenue won, win rate, deal count, average deal size, quota attainment per rep; ranked/leaderboard output. Seen in: Salesforce, HubSpot (Deals: Quota Attainment), Zoho (leaderboard), Dynamics 365 (Sales Performance Dashboard), Pipedrive (Deal Performance), Freshsales, Copper, Insightly. Priority: **table-stakes**. Spine: `AnalyticsReport` (report_type='sales_performance'); aggregates `Opportunity` (stage=closed_won, amount, owner) vs. `SalesQuota`. Buildable now.

- **Pipeline / Funnel Analysis Report** — count and value of opportunities at each stage; conversion rate stage-to-stage; drop-off rates; pipeline coverage ratio. Seen in: all 10 leaders (this is the core CRM report). Priority: **table-stakes**. Spine: `AnalyticsReport` (report_type='pipeline_funnel'); aggregates `Lead.status` distribution + `Opportunity.stage` distribution in analytics.py. Buildable now.

- **Win / Loss Analysis Report** — reasons deals closed lost, competitors associated with losses, loss rate by stage/owner/territory. Seen in: HubSpot (Deal Loss Reasons), Pipedrive (Deal Conversion), Salesforce, Zoho, Copper, Dynamics 365. Priority: **common**. Spine: `AnalyticsReport` (report_type='win_loss'); aggregates `Opportunity` (stage=closed_won/closed_lost, loss_reason, competitor, owner, territory). Buildable now.

- **Revenue Forecast Report** — weighted pipeline total (amount × probability) vs. quota target; breakdown by forecast_category (Pipeline / Best Case / Commit / Closed); expected close this month/quarter. Seen in: Salesforce, HubSpot (Forecast & Revenue suite), Pipedrive (Deal Revenue Forecast), Zoho, Dynamics 365, Freshsales, Copper. Priority: **common**. Spine: `AnalyticsReport` (report_type='revenue_forecast'); uses `Opportunity.weighted_amount` property + `SalesQuota.target_amount`. Buildable now.

- **Lead Source / Campaign Attribution Report** — leads and opportunities by source (web, referral, cold call, email campaign), campaign ROI (budget vs. actual_cost vs. expected_revenue vs. closed-won amount). Seen in: HubSpot (attribution / Campaign attribution), Salesforce, Zoho, Pipedrive (Campaign Performance), Dynamics 365 (Leads by Source widget). Priority: **common**. Spine: `AnalyticsReport` (report_type='lead_source'); aggregates `Lead.source`, `Opportunity.campaign` → `Campaign.actual_cost` vs. won amount. Buildable now.

- **Service Resolution Time Report** — average time from `Case.created_at` to `resolved_at`; distribution of resolution times; SLA compliance rate (% resolved before `resolution_due`); first response time vs. `first_response_due`. Seen in: Zendesk Explore (first resolution / full resolution time medians), Salesforce Service Cloud, Freshsales, HubSpot Service Hub. Priority: **table-stakes**. Spine: `AnalyticsReport` (report_type='service_resolution'); aggregates `Case` timestamps in analytics.py. Buildable now.

- **CSAT / Satisfaction Report** — average satisfaction rating, distribution (1–5 stars), CSAT by agent (Case.owner), CSAT by case type/priority/origin; % rated cases. Seen in: Zendesk Explore (Satisfaction tab), Salesforce Service Cloud, HubSpot Service, Freshdesk. Priority: **table-stakes**. Spine: `AnalyticsReport` (report_type='csat'); aggregates `Case.satisfaction_rating` (1–5) by owner, type, period. Buildable now.

- **Case Volume / Agent Performance Report** — cases opened vs. closed per period per agent; backlog; escalation rate; cases by type/priority/origin. Seen in: Zendesk Explore, Salesforce Service Cloud, HubSpot, Freshsales. Priority: **common**. Spine: `AnalyticsReport` (report_type='case_volume'); aggregates `Case` by owner, status, created_at. Buildable now.

- **Deal Velocity Report** — average days from opportunity creation to close, by stage dwell time (`stage_changed_at` deltas), by owner or territory. Seen in: HubSpot (Deal Velocity report), Pipedrive (Deal Duration), Salesforce, Zoho. Priority: **common**. Spine: `AnalyticsReport` (report_type='deal_velocity'); uses `Opportunity.stage_changed_at` and `closed_at`/`lost_at`. Buildable now.

- **Report Saved Filters / Parameters** — a saved report stores date range type (this_week / this_month / this_quarter / this_year / custom), dimension breakdowns, and any additional filter (owner, territory, pipeline, case status). Seen in: Salesforce, HubSpot, Pipedrive, Zoho, Insightly, Copper. Priority: **table-stakes**. Spine: `AnalyticsReport` (filter_json JSONField). Buildable now.

- **Historical Snapshot / Trend Data** — periodic capture of a report's aggregate result (pipeline total, CSAT avg, activity count) to track how metrics change over time; enables period-over-period comparison. Seen in: Salesforce (Reporting Snapshots to custom objects), Pipeliner CRM, Zoho (historical trend), HubSpot (deal change history). Priority: **common**. Spine: `ReportSnapshot` (report FK, period_label, captured_at, result_json). Buildable now — a management command or cron captures a snapshot nightly/weekly.

- **Period-over-Period Comparison** — comparing current period vs. prior period on any report (this month vs. last month, this quarter vs. last quarter). Seen in: Salesforce, HubSpot, Zoho, Pipedrive, Dynamics 365. Priority: **common**. Spine: analytics.py returns both current and prior-period aggregates; `ReportSnapshot` stores the series. Buildable now.

- **Scheduled Report Email Delivery** — auto-send a report's results via email on a daily/weekly/monthly cadence. Seen in: Salesforce (subscriptions), HubSpot (recurring digests), Pipedrive, Zoho, Insightly, Copper (scheduling & alerts). Priority: **differentiator**. Spine: `AnalyticsReport` (schedule_frequency, schedule_recipients JSONField, next_run_at). Integration/later — requires Celery/Beat or Django Q task queue. Defer to a future sprint.

- **CSV / PDF Export** — download a report as CSV (tabular data) or PDF (formatted). Seen in: Salesforce, HubSpot, Pipedrive, Zoho, Copper, Insightly. Priority: **common**. Spine: no new model needed — view streams queryset result as CSV. Integration/later — CSV is buildable now as a simple Django HttpResponse; PDF (WeasyPrint/reportlab) deferred.

- **Drill-Down from Chart to Records** — click a bar/segment to see the underlying records list. Seen in: Insightly (drill paths), Salesforce, Zoho, Dynamics 365 (visual filter click-through), HubSpot. Priority: **common**. Spine: `DashboardWidget` stores a drilldown_url template that analytics.py pre-filters the relevant list view. Buildable now with Django URL routing.

- **NPS / Survey Analytics** — aggregate NPS scores from `Survey` responses; NPS distribution (Promoters / Passives / Detractors); trend over time. Seen in: Salesforce Service Cloud, HubSpot, Zendesk. Priority: **differentiator**. Spine: `AnalyticsReport` (report_type='nps'); aggregates `Survey` + `HealthScore` models. Buildable now if report_type added to catalog.

- **AI Natural-Language Report Builder** — type "show me deals won by rep this quarter" and the system generates the query. Seen in: HubSpot (Breeze Assistant), Pipedrive (AI report generation), Salesforce (Einstein Copilot), Zoho (Ask Zia), Dynamics 365 (Copilot / Research Agents). Priority: **differentiator**. Integration/later — requires LLM API integration. Defer entirely.

---

## Recommended build scope (this pass — 4 models + analytics.py)

### Model 1: `AnalyticsDashboard`
Fields justified by: Per-User Dashboard Container, Dashboard Sharing, Date Range / Period Filter, Role-Based Dashboards.
```
tenant (FK core.Tenant)
owner (FK User, nullable — null = system/shared)
name (CharField 120)
slug (SlugField, unique within tenant+owner)
description (TextField blank)
visibility (choices: private / team / tenant)
audience (choices: rep / manager / executive / service / custom)
default_period (choices: this_week / this_month / this_quarter / this_year / last_30_days)
is_default (BooleanField — one default per owner)
layout_json (JSONField — stores grid column count, theme, column widths)
created_at / updated_at (auto)
```
Reuses: `core.Tenant`, `accounts.User`. No spine duplication.

### Model 2: `DashboardWidget`
Fields justified by: KPI Card, Bar/Column Chart, Line Chart, Funnel, Gauge, Leaderboard, Pie, Drag-and-Drop Layout, Widget Configuration, Drill-Down.
```
tenant (FK core.Tenant)
dashboard (FK AnalyticsDashboard on_delete=CASCADE)
title (CharField 120)
widget_type (choices: kpi_card / bar_chart / line_chart / pie_chart / funnel / gauge / leaderboard / table)
metric_key (choices: leads_by_status / opps_by_stage / revenue_won / activity_count / case_volume / csat_avg / resolution_time_avg / quota_attainment / deal_velocity / lead_conversion_rate / … ~20 choices)
dimension_key (choices: owner / stage / source / territory / type / priority / origin / period — nullable)
filter_json (JSONField blank — additional where-clause params e.g. {"stage": "closed_won"})
date_period_override (choices matching AnalyticsDashboard.default_period, nullable — inherits dashboard default if null)
position_x (PositiveSmallIntegerField default 0)
position_y (PositiveSmallIntegerField default 0)
width (PositiveSmallIntegerField default 2, 1–4 columns)
height (PositiveSmallIntegerField default 1)
target_value (DecimalField null blank — used by gauge and kpi_card for threshold/goal)
drilldown_url (CharField blank — relative URL with filter placeholders)
sort_order (PositiveSmallIntegerField — manual ordering fallback)
```
Reuses: `core.Tenant`. Aggregates existing CRM models via analytics.py.

### Model 3: `AnalyticsReport`
Fields justified by: Sales Activity Report, Sales Performance Report, Pipeline/Funnel Report, Win/Loss Analysis, Revenue Forecast, Lead Source/Campaign, Service Resolution Time, CSAT Report, Case Volume, Deal Velocity, NPS, Saved Filters/Parameters, (Scheduled Email — fields added now, wired later).
```
tenant (FK core.Tenant)
owner (FK User, nullable — null = system report)
name (CharField 200)
report_type (choices: sales_activity / sales_performance / pipeline_funnel / win_loss / revenue_forecast / lead_source / service_resolution / csat / case_volume / deal_velocity / nps — ~11 choices)
date_period (choices: this_week / this_month / this_quarter / this_year / last_30_days / last_90_days / custom)
date_from (DateField null blank — used when date_period='custom')
date_to (DateField null blank)
filter_json (JSONField blank — {"owner_id": 5, "territory_id": 3, "stage": "closed_won"})
dimension (CharField blank — e.g. "owner", "stage", "source" — how to group results)
is_pinned (BooleanField — appears in report library header)
# Scheduling fields (stored now, wired to task queue in a later sprint)
schedule_frequency (choices: none / daily / weekly / monthly, default none)
schedule_recipients (JSONField blank — list of email addresses)
next_run_at (DateTimeField null blank)
last_run_at (DateTimeField null blank)
created_at / updated_at (auto)
```
Reuses: `core.Tenant`, `accounts.User`. All compute logic in analytics.py — no new data stored in this model.

### Model 4: `ReportSnapshot`
Fields justified by: Historical Snapshot / Trend Data, Period-over-Period Comparison, Reporting Snapshots (Salesforce pattern).
```
tenant (FK core.Tenant)
report (FK AnalyticsReport on_delete=CASCADE)
period_label (CharField 40 — "2026-Q2", "2026-06", "2026-W26")
captured_at (DateTimeField auto_now_add)
result_json (JSONField — serialized aggregate result: {"total": 42, "rows": [{"label": "Alice", "value": 120000}, …]})
```
No spine reuse needed — pure analytics artifact.

### analytics.py (compute helper, no new tables)
Functions justified by all report types and widget metric_key choices:
- `leads_summary(tenant, period_start, period_end, dimension=None)` — Lead counts by status/source/owner
- `opportunity_funnel(tenant, period_start, period_end)` — count + amount at each stage
- `revenue_won(tenant, period_start, period_end, dimension=None)` — closed-won amount by owner/territory/period
- `quota_attainment(tenant, period)` — won vs. SalesQuota.target_amount per owner/territory
- `deal_velocity(tenant, period_start, period_end, dimension=None)` — avg days to close by owner/stage
- `win_loss_analysis(tenant, period_start, period_end)` — won vs. lost counts, loss_reason distribution
- `activity_summary(tenant, period_start, period_end, dimension=None)` — CrmTask + CommunicationLog + CalendarEvent counts by owner/type
- `case_volume(tenant, period_start, period_end, dimension=None)` — Case counts by status/type/priority/origin/owner
- `service_resolution_time(tenant, period_start, period_end)` — avg (resolved_at - created_at), FCR proxy (one-comment cases), SLA breach rate
- `csat_summary(tenant, period_start, period_end, dimension=None)` — avg satisfaction_rating, distribution 1–5, % rated by owner/type
- `nps_summary(tenant, period_start, period_end)` — aggregate Survey NPS scores if available
- `campaign_roi(tenant, period_start, period_end)` — Campaign budget vs. actual_cost vs. linked won Opportunity amounts
- `snapshot_report(report_instance)` — driver: calls the right function, returns result_json dict, called by a management command or Celery task

---

## Deferred (later passes / integrations)

- **Drag-and-drop JS dashboard builder** — the `position_x/y/width/height` fields are stored in `DashboardWidget` now, but the interactive live rearrangement UI (Sortable.js, GridStack.js, or HTMX drag) is deferred to a UI-polish sprint; this pass ships a fixed-grid layout with a simple ordering.
- **Scheduled email delivery of reports** — `AnalyticsReport.schedule_frequency/recipients/next_run_at` fields are added to the model now, but the actual task execution (Celery Beat / Django Q) is deferred; the fields are ready so no migration change is needed later.
- **PDF export** — CSV download is in-scope (simple Django HttpResponse streaming); PDF layout (WeasyPrint/reportlab) is deferred.
- **AI natural-language report builder** — requires LLM API (OpenAI / Anthropic) integration; deferred entirely; no model changes needed.
- **Cross-object custom report builder** — Salesforce-style drag-fields-from-any-object report canvas; deferred to Module 10 BI.
- **External BI embed** (Power BI / Tableau / Looker iframes) — integration/later; no model changes needed.
- **Pipeline snapshot cadence automation** — automatic nightly snapshot via Celery is deferred; management command `snapshot_crm_reports` is in scope for this pass (manually run / cron).
- **Real-time push (WebSockets / SSE)** — widgets query on page load via HTMX; true push/live-update without page reload is deferred.
- **Mobile-responsive widget grid** — CSS responsive breakpoints for the dashboard grid are best-effort this pass; full mobile-optimized widget resizing is deferred.

# Research — Sub-module 8.4: Sales Forecasting (Module 8 — Sales Management System, `sales`)

> Phase 1 output. Target pre-resolved: **8.4 Sales Forecasting**. Do not re-detect.
> BASE `6edc6178` · branch `main`. NavERP.md 8.4 = lines 1327–1332 (five feature bullets).

## Repo state checked first

### LIVE_LINKS actually present in `apps/core/navigation.py`
`"8.1"` (line 2167), `"8.2"` (line 2179), `"8.3"` (line 2188). **No `8.4` entry** — 8.4 is the next unbuilt sub-module of module 8. Confirmed by grep, not assumed.

### Spine entities VERIFIED to exist (recursive grep over every `apps/*/models/` package)
| Class | File | Verdict |
|---|---|---|
| `crm.Opportunity` | `apps/crm/models/SalesForceAutomation/Opportunities.py:5` | **EXISTS** — the opportunity master lives in CRM, not sales. `OPP-`, `amount`, `currency`→`accounting.Currency`, `probability`, `close_date`, `stage`, `owner`→User, `territory`→`crm.Territory`, `stage_changed_at`, `forecast_category` |
| `crm.Opportunity.FORECAST_CATEGORY_CHOICES` | same file, L20-26 | **EXISTS** — `omitted / pipeline / best_case / commit / closed` |
| `crm.SalesQuota` | `apps/crm/models/SalesForceAutomation/SalesQuotas.py:5` | **EXISTS** — `owner`→User, `territory`→`crm.Territory`, `period_type` (month/quarter/year), `period_year`, `period_number`, `target_amount`. `QTA-` |
| `crm.Territory` | `apps/crm/models/SalesForceAutomation/Territories.py:10` | **EXISTS** — self-parenting `parent`, `manager`→User |
| `sales.Pipeline` | `apps/sales/models/OpportunityPipeline/Pipelines.py:46` | **EXISTS** — `PIPE-`, `is_default`, `is_active` |
| `sales.PipelineStage` | same file, L103 | **EXISTS** — `stage_kind` (open/won/lost), `probability`, `forecast_category` (same 5 values), `sequence`, `target_days` |
| `sales.OpportunityPipelinePlacement` | same file, L292 | **EXISTS** — OneToOne `crm.Opportunity`, FK `Pipeline` + `PipelineStage`, `probability_override`, `stage_entered_at`, property `effective_probability` |
| `sales.OpportunityOutcome` | `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py:66` | **EXISTS** — `OUT-`, **append-only**, `result` (won/lost), `reason`→`WinLossReason`, `closed_at`, `recorded_by` |
| `sales.WinLossReason` | same file, L11 | **EXISTS** — `WLR-`, `result`, `category` (price/product_fit/timing/competition/…) |
| `sales.OpportunityTeamMember` | `apps/sales/models/OpportunityTeams/OpportunityTeams.py:8` | **EXISTS** — `OTM-`, FK `crm.Opportunity`, `user`, `org_unit`→`core.OrgUnit`, roles incl. `co_owner`, `approver`, `executive_sponsor` |
| `sales.CompetitorProfile` / `OpportunityCompetitor` | `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py` | **EXISTS** |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | **EXISTS** — self-parenting `parent`, `kind` ∈ company/branch/department/team/cost_center |
| `core.Tenant`, `core.Party`, `core.PartyRole`, `core.Activity`, `core.AuditLog` | `apps/core/models/*.py` | **EXIST** |
| `accounting.Currency` | `apps/accounting/models/GeneralLedger/Currencies.py:6` | **EXISTS** — `code`, `name`, `is_active` (global, no tenant FK) |
| `accounting.ExchangeRate` | `apps/accounting/models/GeneralLedger/ExchangeRates.py:5` | **EXISTS** — `(tenant, currency, rate_date)` unique, `rate` — **the FX source 8.2 deferred to 8.4** |
| `accounting.FiscalPeriod` | `apps/accounting/models/GeneralLedger/FiscalPeriods.py:5` | **EXISTS** |
| `scm.SalesOrder` | `apps/scm/models/OrderManagement/SalesOrders.py:20` | **EXISTS** (`SO-`) — but SCM 4.5's own docstring states **SCM owns the sales order** and that 8.6 "will FK INTO this order rather than declare a second one". 8.4 must not build or own an order. |
| `scm.Item` / `scm.UOM` | `apps/scm/models/InventoryManagement/Items.py:73` / `:51` | **EXIST** (Module 5 items are built) — not needed by 8.4; no product mix in a sales forecast. |

**NOT built / not to be FK'd:** no sales-owned `SalesOrder` (8.6 does not exist yet), no `sales.Quota` (8.7 not built), no `sales.Territory` (8.7 not built — use read-only `crm.Territory` as a rollup dimension, exactly as 8.2 did).

### `apps/sales` conventions to match
- `apps/sales/models/_base.py` → `TenantOwned` (tenant FK + `created_at`/`updated_at`) and `TenantNumbered` (`NUMBER_PREFIX` + `number` via `core.utils.next_number`, width 5, e.g. `PIPE-00001`).
- Sub-module folder PascalCase: `models/SalesForecasting/<Entity>.py`; templates `templates/sales/forecasting/<entity>/{list,detail,form}.html`.
- Re-export every model from `apps/sales/models/__init__.py` (`__all__`) or `from apps.sales.models import X` breaks.
- **Free number prefixes** (checked against every prefix in `apps/sales/models` + `apps/crm/models`): `FCP`, `FCS`, `FAD`, `FSC` — none collide.

### What the earlier research files already settled — do NOT re-survey
- `research-sales-8.2.md` L290 parked to 8.4: "commit/pipeline categories, manager overrides, quota attainment ownership, roll-up/adjustment/scenario, accuracy history, and AI prediction. 8.2 supplies stage probabilities and basic weighted visibility only."
- `research-sales-8.2.md` L261: *"formal reporting-currency conversion belongs to 8.4"*; L307: *"territory/quota analytics ownership, and reporting-currency roll-ups — 8.4/8.7."*
- `research-sales-8.2.md` L112: currency-safe totals — "never silently default to USD and never sum unlike currencies."
- `research-sales-8.3.md` L249: "8.4 — commit/best-case scenarios, manager overrides, quota attainment, forecast accuracy, and AI prediction. 8.3 only supplies read-only account rollups."
- 8.2 already built `PipelineStage.forecast_category` + `OpportunityPipelinePlacement.effective_probability`. 8.4 **consumes** these; it must not re-declare a stage probability or a category vocabulary.

---

## Leaders surveyed (with source links)

Domain: **CRM sales forecasting / revenue intelligence / quota management** — not generic sales software.

1. **Salesforce Sales Cloud (Sales Analytics / Revenue Cloud)** — the category originator; forecast categories + Einstein. — https://www.salesforce.com/sales/analytics/
2. **Microsoft Dynamics 365 Sales** — the most explicitly documented forecasting *mechanics* (adjustments, column types, hierarchy templates, predictive scoring). — https://learn.microsoft.com/en-us/dynamics365/sales/
3. **SAP Sales Cloud** — suite slice: pipeline & forecast intelligence with embedded AI. — https://www.sap.com/products/crm/sales-cloud.html
4. **Gong Forecast** — signal-based AI forecasting with an explicit forecast *submission/roll-up* tier. — https://www.gong.io/forecast
5. **Clari Forecast / Salesloft Forecast (+ Inspect)** — human-vs-AI projection review model. — https://www.clari.com/product/forecast
6. **Ebsta (Revenue Intelligence)** — the "forecast call" / "why did my forecast change" framing. — https://www.ebsta.com/
7. **Revenue.io** — Salesforce-native, "forecast off real activity, not rep self-reporting". — https://www.revenue.io/
8. **Pipedrive (Sales Forecasting)** — SMB end of the market: live-pipeline forecast + forecast-vs-actual reports. — https://www.pipedrive.com/en/features/sales-forecasting
9. **Zoho CRM** — suite slice: pipeline metrics (avg deal size, cycle length, win rate, velocity) feeding revenue targets. — https://www.zoho.com/crm/sales-pipeline.html

Primary sources read in depth (Dynamics 365 — five pages, the richest mechanics in the category):
- Forecast category on an opportunity — https://learn.microsoft.com/en-us/dynamics365/sales/capture-forecast-category-opportunity
- Forecast adjustments (manager override) — https://learn.microsoft.com/en-us/dynamics365/sales/adjust-values-in-forecast
- Forecast grid column types — https://learn.microsoft.com/en-us/dynamics365/sales/choose-layout-and-columns-forecast
- Forecast templates (rollup hierarchy) — https://learn.microsoft.com/en-us/dynamics365/sales/select-template-forecast
- Predictive opportunity scoring — https://learn.microsoft.com/en-us/dynamics365/sales/configure-predictive-opportunity-scoring

*Not surveyed in depth:* HubSpot — its public forecasting pages returned no product-feature content. Noted so the todo agent does not treat it as a gap.
## Feature catalog (this sub-module only)

### Bullet 1 — Forecast Categories & Commitments (best case, commit, pipeline, closed + manager override)
- **Five-value forecast-category vocabulary** — each opportunity carries a confidence bucket; the bucket decides which forecast column it rolls into. Microsoft documents: `Pipeline` (default, early/stalled), `Best Case` (progressing, no commitment), `Committed` (verbal/contractual commitment), `Omitted` (on hold / out of period), `Won`/`Lost` (set automatically by the close dialog, never picked by hand). Salesforce adds `Most Likely` to its equivalent set. · seen in: Dynamics 365, Salesforce, SAP · priority: **table-stakes**
  · spine: **reuse the existing `omitted|pipeline|best_case|commit|closed` values already on `crm.Opportunity.forecast_category` and `sales.PipelineStage.forecast_category`** — do NOT create a `ForecastCategory` table; a new table cannot drive either CharField and would be a second, disconnected vocabulary · buildable now (as submission amount columns, not as a new master)
- **Category rollup to a period total** — a computed "Total forecast = Committed + Best Case + Pipeline" column alongside the individual category columns. · seen in: Dynamics 365 (Calculated column type), Salesforce ("single forecasts" vs "cumulative forecasts") · priority: **table-stakes**
  · spine: new table `ForecastSubmission` stores the per-category amounts; the total is a **property, never a stored column that can drift** · buildable now
- **Manager override / adjustment** — a manager (or the seller) replaces a calculated cell with a value, and the change rolls up the reporting hierarchy. Microsoft documents three distinct adjustment kinds: **direct** (I changed this cell), **indirect** (someone above me changed their total and it propagated to me), and **calculated** (the system value when neither applies). · seen in: Dynamics 365, Salesforce (first-line manager assessment), SAP · priority: **table-stakes**
  · spine: new table `ForecastAdjustment`; the rollup is a read of the parent `ForecastSubmission`, not a second stored total · buildable now
- **Adjustments are opt-in per column and revertible with a reason** — Microsoft shows a pencil only on columns an admin marked editable, keeps an **adjustment History tab**, and supports **Reset** back to the system-calculated value *with a mandatory reason*, which also rolls back the indirect adjustments it created. · seen in: Dynamics 365 · priority: **common**
  · spine: `ForecastAdjustment.is_reverted` + `revert_reason`; both are why this is a table and not a field on the submission · buildable now
- **Adjustment is not a substitute for good data** — Microsoft is explicit: if the opportunity is stale, fix the opportunity; if a deal died, close it lost — do not adjust it to zero. So the override must carry a mandatory reason code and be visible in review. · seen in: Dynamics 365 · priority: **common**
  · spine: `ForecastAdjustment.reason_code` (required) + `note` · buildable now
- **Closed/actual is automatic, never hand-picked** — winning or losing flips the category automatically; setting it by hand makes a deal vanish from the forecast or corrupts the rollup. · seen in: Dynamics 365, Salesforce · priority: **table-stakes**
  · spine: reuse `sales.OpportunityOutcome` (verified, **append-only**) as the actuals source; do not add a second close-date field · buildable now

### Bullet 2 — AI-Powered Predictive Forecasting (historical win rates, deal velocity, engagement signals)
- **A prediction column beside the human forecast column** — Dynamics adds a `Prediction` rollup column that only appears once predictive forecasting is enabled, sitting next to the rep-entered numbers. Salesloft renders it as "AI forecast summary → Human Review: human vs AI projection". · seen in: Dynamics 365, Clari/Salesloft · priority: **differentiator**
  · spine: new **nullable** prediction fields on `ForecastSubmission` (`ai_predicted_*`, `ai_confidence_pct`, `ai_generated_at`) — the ML writes into them later with no migration · buildable now (schema), **the model is integration/later**
- **Top influencing factors / explainability** — Dynamics lets a manager see *why* a score is low ("review the top influencing factors to analyze why Opportunity B's score is low") and offers a **per-stage model** showing which attributes matter at which pipeline stage. · seen in: Dynamics 365 · priority: **differentiator**
  · spine: `ForecastSubmission.ai_explanation` (JSONField) holding named factors + weights; the goal is that a number is never presented without its reason · buildable now (schema)
- **A minimum-data gate before you may claim a prediction** — Dynamics refuses to train until the org has **≥40 won and ≥40 lost** opportunities in the training window, and the data-lake sync takes hours. Gong claims precision "20% more than algorithms based on CRM data" from **300+ signals**. · seen in: Dynamics 365, Gong · priority: **common**
  · spine: a documented eligibility check (count `sales.OpportunityOutcome` rows) rendered on the forecasting page; **do not** show a prediction when the gate fails — an unexplained opaque score is worse than none (8.2 already parked this) · buildable now (the count), integration later (the model)
- **Deal-level predictive scoring** — per-opportunity win probability ranked so reps prioritise. · seen in: Dynamics 365, Salesforce Einstein, Gong (AI Deal Predictor), Zoho (AI-driven predictions) · priority: **differentiator**
  · spine: **parked** — a per-deal score is 8.2 opportunity health / 8.12 analytics territory; if it lands, a `ForecastSignal` table is its home, not a column on the submission · deferred
- **Training-window provenance** — which period the model was trained on, and which model version produced the number. · seen in: Dynamics 365 (train window 3 months–2 years, per-stage on/off), Gong (model tiering) · priority: **common**

### Bullet 3 — Quota Management & Attainment
- **Attainment against the quota already on file** — Gong ships a "Metrics + Target Management" module; Ebsta markets quota-attainment improvement as its headline outcome. · seen in: Gong, Ebsta, Salesforce ("progress toward quota (for individual reps) and sales targets (for sales teams)") · priority: **table-stakes**
  · spine: **read-only reuse of the verified `crm.SalesQuota`** (`target_amount`, `owner`, `period_type`, `period_year`, `period_number`) · buildable now
- **Snapshot the quota onto the forecast so history does not silently change** — if a manager later edits `crm.SalesQuota.target_amount`, every past attainment number would move. The submission must carry its own copy. · seen in: implied by every accuracy/history feature below · priority: **common**
  · spine: `ForecastSubmission.quota_amount` (snapshot) + nullable `quota_ref`→`crm.SalesQuota` (`SET_NULL`, so deleting a quota never cascades into history) · buildable now
- **Pace vs. attainment (the ramp read)** — attainment is only meaningful against time elapsed: a rep 40% attained at 80% elapsed is behind, not fine. SAP pairs "pipeline and forecast intelligence" with quota attainment; Dynamics pairs forecasting with "Define and track your sales goals". · seen in: SAP, Dynamics 365, Gong · priority: **common**
  · spine: an attainment view comparing closed-won actual vs `quota_amount` vs linear period-elapsed expectation, derived in the view layer — **no stored ramp weights** · buildable now
- **Quota as a forecast column, uploadable from outside the CRM** — Dynamics' "Simple" column type exists specifically so a quota/target budget can be uploaded via Excel rather than typed per deal. · seen in: Dynamics 365 · priority: **common**
  · spine: an import action page on `ForecastPeriod` seeding `crm.SalesQuota`; the upload itself is a later pass · deferred
- **Setting, allocating, approving and stretching quotas; new-hire ramp weights; coverage model** — these are quota *design*, and NavERP 8.7 "Quota Planning & Allocation" owns them. · priority: n/a
  · spine: **parked to 8.7** — 8.2's research already ruled "Territory and quota redesign belongs to 8.7". 8.4 only *reads* `crm.SalesQuota` and snapshots it.

### Bullet 4 — Forecast Rollups & Adjustments (rep → manager → director, sandbagging, scenarios)
- **The rollup axis is a chosen hierarchy** — Dynamics offers exactly three templates: **org chart** (rolls up the User entity's Manager field), **product** (product hierarchy), **territory** (sales territory hierarchy). Salesforce's equivalent "Adaptable Forecasts" roll up by team, product family, territory, **opportunity split**, or custom measure. · seen in: Dynamics 365, Salesforce · priority: **table-stakes**
  · spine: **verified** `core.OrgUnit` (self-parenting, kind company/branch/department/team/cost_center) is NavERP's manager spine; `sales.OpportunityTeamMember.org_unit` and `crm.Territory` are the other two available dimensions; `crm.OpportunitySplit` (verified, percentage ≤ 100% guarded) is the split measure. Rollup is a **read** of child `ForecastSubmission` rows, never a stored parent total · buildable now
- **A formal submit-and-review cycle** — Gong puts **Forecast submission** in the paid tier specifically so teams "roll up your forecast, with advanced AI to help you triangulate and validate your team's forecast"; Ebsta organises the whole feature around the **forecast call**. Salesforce and Dynamics both gate on a forecast **owner** with review rights. · seen in: Gong, Ebsta, Salesforce, Dynamics 365 · priority: **table-stakes**
  · spine: `ForecastSubmission.status` (draft → submitted → approved/rejected → locked) + `submitted_by/at`, `reviewed_by/at`, `review_note`; the approver right is a **role check, never a record ACL** (8.2 already ruled team membership is not a security boundary) · buildable now
- **You cannot adjust a level above you in the hierarchy** — Microsoft: "You can't adjust values for users or territories above your level in the hierarchy, even if you've been given access through your security role." · seen in: Dynamics 365 · priority: **common** (security-sensitive)
  · spine: the adjustment action compares the acting user against the submission's rollup position and refuses downward-only violations; every queryset stays tenant-scoped · buildable now
- **Scenario / what-if modelling** — pipeline metrics are run as scenarios across win rates, sales cycles and customer interactions, and a forecast is stress-tested against an objective model rather than a gut number. · seen in: Pipedrive, SAP, Gong · priority: **differentiator**
  · spine: new table `ForecastScenario` sitting on a `ForecastPeriod`, holding a type (upside/base/downside/custom), a probability weight, and per-category deltas — it must **never mutate** a `ForecastSubmission` · buildable now
- **Why the forecast changed** — Ebsta's flagship playbook is literally "Understand why your forecast changed"; Salesforce surfaces "which forecasts have shifted with visual cues and alerts". · seen in: Ebsta, Salesforce · priority: **differentiator**
  · spine: the adjustment history (with reason codes) *is* the change log; the period page shows its adjustments inline · buildable now
- **Consumption / renewal forecasting combined with new business** — Salesforce ships a distinct consumption-forecasting mode for recurring/renewal revenue. · seen in: Salesforce · priority: **differentiator**
  · spine: parked to 8.15 contract/subscription — no forecast table is needed for it
- **Forecast-call notes and the pack** — the weekly call artefact. · seen in: Ebsta, Gong · priority: n/a
  · spine: parked to 8.8 (activity/task) and 8.12 (analytics), plus a document/attachment pass

### Bullet 5 — Forecast Accuracy & Variance Analysis (actual vs predicted, bias, trend)
- **Actual vs. forecast, per rep / team / period, on demand** — Pipedrive's core reporting claim is "compare predicted revenue to results across reps, teams and time periods"; Salesforce's Actionable Forecast View tracks "changes in the current period and assess performance against past periods — without manual calculations". · seen in: Pipedrive, Salesforce, Gong · priority: **table-stakes**
  · spine: **derived at query time** from `ForecastSubmission` snapshots vs closed-won actuals (`crm.Opportunity.stage="closed_won"` / `sales.OpportunityOutcome`) — no stored accuracy table, so it can never disagree with its inputs · buildable now
- **Bias detection / sandbagging** — a rep who under-commits early and inflates late is the classic failure mode; Gong's Signals layer, Revenue.io's "forecasts built on real activity data, **not rep self-reporting**", and Ebsta's "spot risks" all attack it by comparing stated numbers against observed signals. · seen in: Gong, Revenue.io, Ebsta · priority: **differentiator**
  · spine: a **derived** comparison — early-in-period `ForecastSubmission`/adjustment set vs the final one vs actuals, plus the rep's stated category mix vs their historical win rate from `sales.WinLossReason`. No model needed · buildable now
- **Human numbers vs. model numbers, side by side** — Clari/Salesloft's "Human Review — human vs AI projection" makes the divergence between what a rep claims and what the model believes the explicit artefact of the forecast call. · seen in: Clari/Salesloft, Dynamics 365 (Prediction column) · priority: **differentiator**
  · spine: `ai_predicted_*` next to the entered amounts on the same row and the same report · buildable now (schema)
- **Accuracy as a coaching input, not a scorecard** — Gong, Ebsta and Revenue.io all route accuracy back into manager 1:1s rather than ranking sheets. · seen in: Gong, Ebsta, Revenue.io · priority: **common**
  · spine: the accuracy report is read-only and links to the owner's period; the coaching workflow itself is 8.8/8.12 · buildable now (the report), parked (the workflow)
- **Trend reporting over time** — Salesforce tracks the current period against past periods; Ebsta publishes benchmark trend data across billions of opportunities. · seen in: Salesforce, Ebsta, Zoho (avg deal size, cycle length, win rate, velocity) · priority: **common**
  · spine: a per-period trend view over the `ForecastSubmission` history; the pipeline *velocity* metrics themselves are 8.12 · buildable now
- **Rep-to-manager-to-director reporting line** — Dynamics' org-chart template uses the **Manager field on the User entity**; NavERP has no `User.manager` field. · seen in: Dynamics 365 · priority: **common**
  · spine: **verified gap** — NavERP's reporting hierarchy is `core.OrgUnit.parent`, and `sales.OpportunityTeamMember.org_unit` already attaches a user to one. Use that; do **not** invent a `User.manager` field in 8.4 · buildable now

---

## Recommended build scope (this pass — 4 models)

All four live in **`apps/sales/models/SalesForecasting/`**, using `TenantOwned` / `TenantNumbered` from `apps/sales/models/_base.py`. Re-export every one of them in `apps/sales/models/__init__.py` (both the import block and `__all__`). Templates under `templates/sales/forecasting/<entity>/`.

### 1. `ForecastPeriod` **`[FCP-]`** — the forecasting cycle + rollup axis + reporting currency
`models/SalesForecasting/ForecastPeriods.py`

- Justified by: forecast category rollups (a period is what amounts roll *into*), the three Dynamics rollup templates, and 8.2's explicit deferral of reporting-currency roll-ups.
- `name`, `period_type` ∈ month/quarter/year (**reuse `crm.SalesQuota.PERIOD_CHOICES` values verbatim**), `period_year`, `period_number`, `start_date`, `end_date` — the dates are computed from the type, never typed.
- `rollup_dimension` ∈ `user` / `org_unit` / `territory` — NavERP's rendering of Dynamics' org-chart / product / territory templates (a product hierarchy is out of scope for 8.4).
- `reporting_currency` FK → `accounting.Currency` (SET_NULL, nullable) and `fx_rate_source_date` — the reference for the rate actually applied; the rate itself is read from the verified `accounting.ExchangeRate` `(tenant, currency, rate_date)` rows.
- `is_active`, `is_locked` (a locked period makes its submissions read-only).
- Unique `(tenant, period_type, period_year, period_number)`.
- **FKs (all verified):** `core.Tenant`, `accounting.Currency`.


### 2. `ForecastSubmission` **`[FCS-]`** — one seller's (or rollup node's) call for a period
`models/SalesForecasting/ForecastSubmissions.py`

- Justified by: submit-and-review cycles (Gong / Ebsta / Salesforce / Dynamics), single vs. cumulative rollups (Salesforce), the adjustment target, the accuracy baseline, and the AI prediction column.
- FKs: `period`→`ForecastPeriod` (PROTECT), `owner`→`settings.AUTH_USER_MODEL` (SET_NULL, nullable), `org_unit`→`core.OrgUnit` (SET_NULL), `territory`→`crm.Territory` (SET_NULL — a read-only dimension; 8.7 owns territory), `pipeline`→`sales.Pipeline` (SET_NULL).
- Workflow: `status` ∈ draft/submitted/approved/rejected/locked; `submitted_at`, `submitted_by`, `reviewed_at`, `reviewed_by`, `review_note`.
- Amounts, all `Decimal(max_digits=14, decimal_places=2)`, **one per existing forecast category** — `omitted_amount`, `pipeline_amount`, `best_case_amount`, `commit_amount`, `closed_amount`, plus `weighted_amount` rolled up from the verified `sales.OpportunityPipelinePlacement.effective_probability`. `total_forecast_amount`, `variance_amount` and `attainment_pct` are **properties, never stored columns** — a stored total is a drift bug waiting to happen.
- Quota snapshot: `quota_amount` + `quota_ref` FK→`crm.SalesQuota` (SET_NULL) so editing a quota never rewrites history.
- Actuals: `actual_amount` — closed-won for the period, sourced from `sales.OpportunityOutcome` / `crm.Opportunity.stage="closed_won"`.
- **Explainable AI block (schema now, model later):** `ai_predicted_pipeline`, `ai_predicted_best_case`, `ai_predicted_commit`, `ai_confidence_pct`, `ai_model_name`, `ai_model_version`, `ai_generated_at`, `ai_explanation` (JSONField of named factors + weights).
- Uniqueness: a `(tenant, period, owner, pipeline)` DB unique is unsafe with NULLs — enforce `(tenant, period, owner)` in `clean()` and index `["tenant","period","status"]`, `["tenant","owner"]`, `["tenant","period","org_unit"]`.
- **FKs (all verified):** `sales.ForecastPeriod`, User, `core.OrgUnit`, `crm.Territory`, `sales.Pipeline`, `crm.SalesQuota`.


### 3. `ForecastAdjustment` **`[FAD-]`** — the manager override, with its audit history
`models/SalesForecasting/ForecastAdjustments.py`

- Justified by: Dynamics' documented direct/indirect/calculated adjustment model, the History tab, the mandatory-reason Reset, and Salesforce's first-line manager assessment.
- FKs: `submission`→`ForecastSubmission` (**PROTECT** — an audit row is never cascaded away), `opportunity`→`crm.Opportunity` (SET_NULL, nullable), `placement`→`sales.OpportunityPipelinePlacement` (SET_NULL, nullable).
- `adjustment_kind` ∈ **direct / indirect / revert** — straight from Microsoft's taxonomy; `indirect` rows are system-written when a manager's own total propagates down.
- `target_field` ∈ category / amount; `original_value` / `adjusted_value` (Decimal), `original_category` / `adjusted_category` (the same 5-value vocabulary).
- `reason_code` (**required** — a manager override with no reason is exactly the sandbagging signal bullet 5 hunts), `note`, `is_reverted`, `reverted_at`, `revert_reason`, `created_by`→User.
- The **calculated/system value is never stored here** — it is recomputed from the opportunity, so reverting is always possible. That is Microsoft's "Reset", and it needs no extra field.
- **FKs (all verified):** `sales.ForecastSubmission`, `crm.Opportunity`, `sales.OpportunityPipelinePlacement`, User.

### 4. `ForecastScenario` **`[FSC-]`** — what-if modelling that never touches the real forecast
`models/SalesForecasting/ForecastScenarios.py`

- Justified by: scenario modelling (bullet 4), Pipedrive's ML scenario planning, SAP's stress-testing, Gong's "pressure-test pipeline against an objective AI".
- FKs: `period`→`ForecastPeriod` (PROTECT), `owner`→User (SET_NULL, nullable — a scenario is often the manager's own what-if).
- `name`, `scenario_type` ∈ upside/base/downside/custom, `probability_pct` (0–100, checked), `is_baseline`, `is_selected`.
- Deltas rather than absolutes, so a scenario stays honest as the pipeline moves: `pipeline_delta_pct`, `best_case_delta_pct`, `commit_delta_pct`; `projected_commit_amount` and `projected_total_amount` are **stored snapshots of what the scenario computed**, labelled as such, with `assumption_notes`.
- Index `["tenant","period"]`, `["tenant","is_selected"]`.





### Reports / views shipped **on top of** these four (no new model)
- **Forecast board** — period × category, with the weighted total and the AI prediction beside the entered numbers (Salesforce "single vs cumulative", Dynamics "Rollup / Calculated / Prediction" columns).
- **Attainment board** — owner/territory × period: quota (`crm.SalesQuota`) vs. actual vs. attainment % vs. period-elapsed pace.
- **Accuracy & bias report** — period-over-period: submitted vs. actual variance, and the sandbagging signal from comparing early submissions/adjustments against the final call. Derived only.
- **Forecast call view** — the period's adjustments with their reasons, the way Ebsta's "why did my forecast change" is answered.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Quota **creation, top-down/bottom-up allocation, stretch goals, non-linear ramp weights for new hires, approval workflow** → **8.7** (8.2's research already ruled quota redesign is 8.7's). 8.4 only *reads* `crm.SalesQuota` and snapshots it.
- Territory design, assignment rules, rebalancing, coverage-gap/heatmap analytics, hunter/farmer splits, overlay specialists → **8.7**.
- Pipeline board, stage probabilities, entry/exit checklists, basic pipeline inspection, per-deal health indicators → **8.2** (already built).
- Account hierarchy rollups, whitespace analysis, cross-sell/upsell opportunity mapping → **8.3** (already built).
- CPQ, pricing/discount approval, proposal generation, quote versioning, quote-to-order conversion → **8.5**.
- Order capture/amendment/cancellation, fulfillment tracking, ASC 606 revenue recognition, reorder/renewal → **8.6** (which will FK **into** the verified `scm.SalesOrder`, not declare its own).
- Rep activity logging, tasks, calendar, the forecast-call meeting itself, coaching playbooks → **8.8**.
- Sales enablement content, the battle-card library → **8.9**.
- Compensation / quota-linked incentive payouts driven by attainment → **8.10**.
- Consumption / renewal / subscription-recurring forecasting → **8.15**.
- Dashboards, cross-pipeline conversion rates, pipeline velocity metrics, per-deal predictive scoring, benchmark trend data → **8.12**.
- Marketing-sourced pipeline contribution and campaign ROI inside the forecast → **8.13**.


## Deferred (later passes / integrations)

- **Actual ML training and inference** — Dynamics premium forecasting, Gong AI Revenue Predictor, Salesforce Einstein, Zoho AI predictions. The **storage + explanation schema ships now**; the model is an integration (data-lake sync, Azure ML / an external service, a retraining cadence). Nothing may display a prediction below the **40-won / 40-lost** eligibility gate learned from Dynamics.
- **Per-deal predictive scoring table** — a `ForecastSignal` / `OpportunityPrediction` table is its eventual home; parked to 8.2 / 8.12.
- **Excel quota upload** (Dynamics' "Simple" column type) — an import action page on `ForecastPeriod` seeding `crm.SalesQuota`; a later pass.
- **Email / Teams / Slack forecast-call notifications and approval reminders** — external integrations.
- **Live FX rate fetching** — `accounting.ExchangeRate` is verified and is the source; auto-fetching spot rates is an accounting/integration concern, not 8.4's.
- **Product-hierarchy rollup** (Dynamics' third template) — needs `scm.Item`'s category tree to be treated as a reporting axis; 8.4 ships `user` / `org_unit` / `territory` only.
- **Opportunity-split rollup weighting** — `crm.OpportunitySplit` is verified and usable, but surfacing splits inside the forecast is an 8.12 analytics concern.
- **True snapshot warehouse / as-of-time rebuild** — 8.2 deliberately kept pipeline inspection on `core.AuditLog` rather than a snapshot store; the same trade-off applies here.
- **Multi-period rolling forecasts and consolidation across business units** — a later pass, once `ForecastPeriod` has history.

  · spine: `ai_model_name` / `ai_model_version` / `ai_generated_at` on the submission · buildable now (schema)



# Research — Sub-module 4.7: Demand Planning & Forecasting (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **LIVE_LINKS built so far in module 4** (`apps/core/navigation.py`, read at run time): `4.1` Procurement,
  `4.2` SRM, `4.3` Inventory, `4.4` WMS, `4.5` OMS, `4.6` TMS. There is **no `"4.7"` key** — confirmed this
  sub-module is the target of this pass and is a clean build.
- **Sibling models verified available to FK (grep evidence — `grep -rn "^class " apps/scm/models/`):**
  - `apps/scm/models/InventoryManagement/Items.py:56 class Item(TenantOwned)` — exists. Also `ItemCategory`
    (line 17) and `UOM` (line 34). `Item.on_hand(location=None)` is a **derived** aggregate over `StockMove`;
    there is deliberately no stored quantity anywhere. `Item.reorder_point` exists as an item-wide default.
  - `apps/scm/models/InventoryManagement/Locations.py:10 class Location(TenantOwned)` — exists, with
    `location_type` (default `warehouse`), `parent` self-FK, and the 4.4-added `capacity`/`pick_sequence`/
    `abc_class`/`is_pickable` bin attributes. **Precedent to note:** 4.4 WMS extended 4.3's `Location` with
    additive fields rather than declaring a parallel bin table — the same move this pass recommends for
    `ReorderRule`.
  - `apps/scm/models/InventoryManagement/StockMoves.py:13 class StockMove(TenantOwned)` — exists, append-only,
    signed `quantity`, `move_type` ∈ receipt/issue/transfer/adjustment, `moved_at`. **This is the second demand
    source**: outbound demand for a period = `-SUM(quantity)` over `move_type="issue"`.
  - `apps/scm/models/OrderManagement/SalesOrders.py:20 class SalesOrder(TenantNumbered)` (line 185
    `class SalesOrderLine`) — both exist. `SalesOrder.order_date` (DateField), `status` with
    `draft/submitted/.../cancelled/closed`, `customer → core.Party`, `currency → accounting.Currency`;
    `SalesOrderLine.item → scm.Item` (nullable — quote-converted lines can arrive unmapped),
    `quantity_ordered`. **This is the primary demand-history source** — history is aggregated over
    `SalesOrderLine` joined through `sales_order__order_date`, excluding `draft`/`cancelled`. There is
    deliberately **no new sales-history table** in this pass's scope.
  - `apps/scm/models/InventoryManagement/ReorderRules.py:11 class ReorderRule(TenantOwned)` — **exists**, and
    is the safety-stock landing point. As-built fields are only: `item`, `location`, `reorder_point`,
    `safety_stock`, `reorder_quantity`, `is_active`, plus the derived helpers `on_hand_map()`,
    `current_on_hand()`, `is_below_point()`, `suggested_quantity()`. `unique_together = (tenant, item,
    location)`. It already backs the live `scm:reorder_alerts` page.
  - **L28 correction — the docs are wrong here.** `.claude/tasks/research-scm-4.3.md` (lines ~221, ~229)
    states `ReorderRule.lead_time_days` and `ReorderRule.preferred_vendor` were "captured this pass". They
    were **not built**: `grep -rn "lead_time|preferred_vendor" apps/scm` returns hits only on
    `SupplierCatalogItem.lead_time_days` (`SupplierCatalogs.py:55`), `RFQQuote.lead_time_days`
    (`Rfqs.py:121`) and `RFQQuoteLine.lead_time_days` (`Rfqs.py:157`). **Every safety-stock formula below
    needs lead time, and it is not on the rule today** — this pass must add it (defaultable from
    `SupplierCatalogItem.lead_time_days`, which is verified to exist).
  - `apps/scm/models/SupplierRelationshipManagement/SupplierCatalogs.py:11 class SupplierCatalog` /
    `:46 class SupplierCatalogItem` — exist; `lead_time_days`, `min_order_qty`, `unit_price` are the verified
    supply-side inputs a safety-stock calculation can seed from.
  - `apps/core/models/Party.py:5 class Party`, `apps/core/models/PartyRole.py:5 class PartyRole`,
    `apps/core/models/OrgUnit.py:5 class OrgUnit`, `apps/core/models/Address.py:5 class Address`,
    `apps/core/models/Activity.py:5 class Activity`, `apps/core/models/Document.py:5 class Document` — all
    exist. `core.OrgUnit` is the verified anchor for "which function submitted this consensus input"
    (HRM 3.40 `WorkforcePlan.org_unit` uses exactly this FK).
  - `apps/accounting/models/GeneralLedger/Currencies.py:6 class Currency` and
    `apps/accounting/models/Budgeting/Budgets.py:6 class Budget` (+ `BudgetLines.py:5 class BudgetLine`) —
    exist. Accounting owns money (L29): a revenue-valued forecast may FK `accounting.Currency`, but this pass
    posts no journal entry and declares no second budget.
- **Spine entities verified NOT to exist** (`grep -rni "forecast|demand|seasonal|consensus" apps/`): nothing
  named `DemandForecast`/`DemandPlan`/`SeasonalityProfile`/`DemandSignal`/`SafetyStockPolicy` anywhere under
  `apps/`. The only "forecast" hits are unrelated: `crm:forecast` (1.2 — a weighted *sales-pipeline* dashboard
  over `Opportunity.forecast_category`, not SKU demand), `accounting:cash_forecast` (2.5 — cash-flow
  projection over open AR/AP), and `hrm:workforceplan_list` (3.40 — headcount demand). **None of these
  forecast item demand**; there is nothing to extend or collide with.
- **Precedent patterns verified in-repo and reused below:** `TenantOwned`/`TenantNumbered` in
  `apps/scm/models/_base.py` (numbering via `apps.core.utils.next_number`, retry-on-collision); the
  derived-never-stored rule (`Item.on_hand`, `SalesOrderLine.quantity_allocated`); the report-page-as-bullet
  precedent (`LIVE_LINKS["4.3"]` points "Reorder Point Automation" at `scm:reorder_alerts` and "Inventory
  Valuation" at `scm:valuation_report` — both computed report views, not CRUD lists); and
  `SupplierScorecard.recompute_from_signals` as the "derive a score from real documents" shape.
- **SCM auto-number prefixes already taken** (grep `NUMBER_PREFIX`): `PR RFQ QT PO GRN CAT SC SCR SRA TRF ADJ
  PUT PIK CC YRD SO CAR LD SHP FRT`. Free for this pass: **`DF` `SEA` `DS` `FA`**.
- **Sibling research files — this pass's starting backlog.** Three earlier files explicitly deferred work
  *to 4.7*: `research-scm-4.3.md` ("statistical/ML-driven reorder-point calculation from demand history and
  seasonality → 4.7"; "`lead_time_days` captured as a static input, the *calculation* belongs to 4.7"),
  `research-scm-4.5.md` ("demand-based statistical safety-stock / forecast-driven pre-emptive allocation →
  4.7"), `research-scm-4.6.md` ("reorder-point generation from a transportation delay → 4.3/4.7"). The
  module-wide `research-scm.md` §4.7 sketched a single `DemandForecast` table and judged statistical/ML
  forecasting "integration/later, but a simple moving-average forecast table is buildable-now" — this pass
  refines that into the four-model scope below.

## Leaders surveyed (with source links)

The domain splits into two genuine product categories, so the survey covers both: **enterprise supply-chain
planning / S&OP suites** (1–9) and **mid-market demand-forecasting & inventory-optimization tools** (10–12).

1. **Blue Yonder Demand Planning (Luminate)** — enterprise AI/ML demand planning; multi-horizon forecasting
   from short-term sensing to long-range plans, "glass box" demand-driver analysis —
   [blueyonder.com/solutions/supply-chain-planning/demand-planning](https://blueyonder.com/solutions/supply-chain-planning/demand-planning)
2. **Kinaxis (Maestro / RapidResponse)** — concurrent planning; consensus demand plan gathered from all
   stakeholders, external-signal demand sensing, scenario simulation —
   [kinaxis.com/en/solutions/demand-planning](https://www.kinaxis.com/en/solutions/demand-planning)
3. **o9 Solutions** — digital-twin planning platform; forecastability-based segmentation, explicit tracked
   assumptions at any hierarchy level, automated consensus workflow —
   [o9solutions.com/solutions/demand-planning](https://o9solutions.com/solutions/demand-planning) ·
   [collaborative demand planning](https://o9solutions.com/solutions/demand-planning/collaborative-demand-planning)
4. **SAP IBP for Demand** — forecast profiles with algorithm libraries, automated outlier detection/correction
   and best-fit selection, plus a separate short-horizon Demand Sensing engine (daily forecasts, ~4–8 week
   window) — [SAP Help: Demand Sensing](https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/feae3cea3cc549aaa9d9de7d363a83e6/c4143c55a5ef9a2de10000000a174cb4.html)
   · [SAP Learning: Using Forecast Profiles](https://learning.sap.com/courses/mastering-sap-ibp-for-demand/using-forecast-profiles)
5. **Oracle Fusion Cloud Demand Management** — Bayesian ensemble forecast engine; decomposes a forecast into
   baseline / trend / seasonality / causal components per segment —
   [oracle.com/scm/supply-chain-planning/demand-management](https://www.oracle.com/scm/supply-chain-planning/demand-management/)
   · [datasheet PDF](https://www.oracle.com/a/ocom/docs/applications/supply-chain-management/oracle-demand-management-cloud-ds.pdf)
6. **RELEX Solutions** — retail/CPG forecasting at SKU/location/day; promotion uplift with cannibalization and
   halo modelling, weather signals, attribute-based new-product forecasting —
   [relexsolutions.com/solutions/demand-planning-software](https://www.relexsolutions.com/solutions/demand-planning-software/)
   · [demand sensing](https://www.relexsolutions.com/solutions/demand-sensing-software/) ·
   [demand planning guide](https://www.relexsolutions.com/resources/demand-planning/)
7. **Logility DemandAI+** — ensemble + driver-based forecasting, automatic anomaly detection that lets a
   planner tag irregular history as an exceptional event, consensus forecasting, forecast-accuracy review that
   pinpoints which products/channels drove the miss —
   [logility.com/solutions/demand/demandai](https://www.logility.com/solutions/demand/demandai/)
8. **John Galt Atlas Planning Platform** — automatic best-method selection and ensemble forecasting with
   explainability, deep hierarchy support (item/channel/location/region), attribute-based forecasting for
   items with no history — [johngalt.com/atlas/demand-software](https://johngalt.com/atlas/demand-software)
9. **Anaplan Demand Planning** — consensus-building rules by input accuracy and horizon, input collection from
   sales/marketing/finance (web/Excel), 26 statistical time-series methods with best-fit selection, curve-fit
   new-product modelling, what-if scenarios —
   [anaplan.com/applications/demand-planning-app](https://www.anaplan.com/applications/demand-planning-app/)
   · [statistical forecasting app](https://www.anaplan.com/applications/statistical-forecasting-app/)
10. **Netstock** — mid-market SCP on top of an ERP; Pivot Forecasting, automatic SKU classification, and
    safety stock / reorder point continuously recalculated from demand pattern, seasonality, supplier
    performance and forecast accuracy — [netstock.com/product](https://www.netstock.com/product/) ·
    [safety stock formulas](https://www.netstock.com/blog/safety-stock-meaning-formula-how-to-calculate/) ·
    [reorder point formula](https://www.netstock.com/blog/reorder-point-formula/)
11. **Slimstock Slim4** — demand-profile-driven model selection, ABC/XYZ classification, dynamic safety stock
    driven by a **target service level** differentiated by product group/location/demand behaviour —
    [slimstock.com/solutions/demand-forecasting-software](https://www.slimstock.com/solutions/demand-forecasting-software/)
    · [demand management](https://www.slimstock.com/solutions/demand-management-software/) ·
    [2026 comparison](https://www.slimstock.com/insights/best-demand-planning-software-comparison/)
12. **Inventory Planner by Sage** — e-commerce/wholesale forecasting; per-product forecast-model choice,
    seasonality and marketing-event handling, spike/dip exclusion, safety stock from demand variability plus
    supply lead time, replenishment recommendations —
    [inventory-planner.com/features/forecasting](https://www.inventory-planner.com/features/forecasting/)

Supporting reference for the accuracy-metric definitions used below (MAPE / WMAPE / bias / tracking signal /
forecast value added): [demandplanning.net — MAPE, WMAPE and forecast bias](https://demandplanning.net/mape-wmape-and-forecast-bias/).

## Feature catalog (this sub-module only)

### Sales Forecasting — statistical forecasting from historical sales data and trends

- **Time-bucketed forecast over a horizon (SKU × location × period)** — the forecast is a grid of periods, not
  a single number; leaders run day/week/month buckets over horizons from weeks to 24 months · seen in: all 12 ·
  priority: table-stakes · spine: new tables `DemandForecast` + child `DemandForecastPeriod`; scoped by
  **verified-existing** `scm.Item` and nullable `scm.Location` · buildable now
- **Demand history derived from real transactions, never re-keyed** — every product reads history out of the
  transactional system rather than storing a parallel sales table · seen in: SAP IBP, Oracle, Netstock,
  Inventory Planner, Slim4 · priority: table-stakes · spine: **no new table** — aggregate
  `scm.SalesOrderLine.quantity_ordered` through `sales_order__order_date` (exclude `draft`/`cancelled`), with
  `scm.StockMove` (`move_type="issue"`, negated) as the alternate source for consumption-driven demand ·
  buildable now (this is the single most important guardrail of this pass)
- **A library of statistical methods with per-item selection** — moving average, exponential smoothing,
  Holt (trend), Holt-Winters (trend+seasonality), naive/seasonal-naive, linear regression on trend · seen in:
  Anaplan (26 methods), SAP IBP forecast profiles, Oracle, John Galt, Inventory Planner (model per product) ·
  priority: table-stakes · spine: `DemandForecast.method` choice field + a pure-Python service that fills
  `DemandForecastPeriod.baseline_quantity` · buildable now (moving average / weighted moving average / simple
  + Holt exponential smoothing / seasonal-naive are ~40 lines of Decimal arithmetic — no numpy, no ML)
- **Best-fit / automatic model selection** — score several candidate models on holdout history and pick the
  lowest-error one · seen in: Anaplan, SAP IBP, John Galt Atlas, Slim4, Netstock · priority: common · spine:
  `DemandForecast.method = "best_fit"` + `selected_method` (`editable=False`, written by the service) ·
  buildable now (run the handful of buildable methods, keep the lowest MAPE) — the *ensemble/Bayesian* variant
  (Oracle, John Galt) is deferred
- **Forecast decomposition: baseline / trend / seasonality / causal uplift** — show *why*, not just *what* ·
  seen in: Oracle (explicit component decomposition), Blue Yonder (demand-driver "glass box"), Logility
  (driver-based), Kinaxis ("see what factors influenced the forecast") · priority: common · spine: separate
  columns on `DemandForecastPeriod` — `baseline_quantity`, `seasonal_index_applied`, `event_uplift_quantity`,
  `signal_adjustment_quantity`, `consensus_quantity`, `final_quantity` — so the page shows the waterfall from
  statistics to plan-of-record · buildable now
- **Forecast accuracy measurement: MAPE / WMAPE / bias / tracking signal** — the scoreboard every planner is
  judged on · seen in: Logility (accuracy review pinpointing misses), Netstock, Slim4, SAP IBP, o9 · priority:
  table-stakes · spine: derived properties on `DemandForecast` computed from each period's `final_quantity` vs.
  the **derived** actual (`actual_quantity()` re-aggregated from `SalesOrderLine`/`StockMove`), never a stored
  actuals column · buildable now
- **Forecast Value Added (FVA)** — did the human override beat the statistical baseline? · seen in: Logility,
  Netstock, and standard S&OP practice · priority: differentiator · spine: derived — compare
  `baseline_quantity` error vs. `final_quantity` error per period; surfaced on the `DemandForecast` detail and
  on `ForecastAdjustment` · buildable now (it is pure arithmetic over columns this pass already stores)
- **Forecast versioning / plan-of-record lifecycle** — a forecast is generated, collaborated on, frozen, then
  compared to actuals; superseded versions stay readable · seen in: o9 (assumptions tracked cycle over cycle),
  SAP IBP, Anaplan, Kinaxis · priority: common · spine: `DemandForecast.status`
  (draft → statistical → in_review → approved → archived) + `revision`/`supersedes` self-FK · buildable now
- **Hierarchy / aggregation levels (item ↔ category ↔ channel ↔ region) with top-down / bottom-up / middle-out
  disaggregation** — plan at an aggregate level and split down, or roll detail up · seen in: John Galt
  ("unmatched support for complex hierarchies"), o9, Anaplan, Netstock (bottom-up/top-down/middle-out),
  Logility · priority: common · spine: partially — `DemandForecast` carries `item` (required) and nullable
  `location` + `customer → core.Party` so a forecast can be narrowed to a channel/customer, and `ItemCategory`
  gives an existing rollup dimension for **reporting**. A true multi-level plan with automatic proportional
  disaggregation is **deferred** (it needs an allocation engine, not a table)
- **Intermittent / lumpy-demand handling (Croston-style) and outlier correction on history** — most SKUs in a
  long tail have sparse demand; raw history must be cleaned first · seen in: SAP IBP (AI history
  classification + outlier detection/correction), Logility (anomaly detection, tag as exceptional event),
  Oracle (intermittent demand), Inventory Planner (exclude abnormal spikes/dips) · priority: common · spine:
  `DemandForecast.exclude_outliers` + `outlier_threshold_sigma` flags on the header, applied by the service
  when it builds the history series; the **manual** counterpart is a `SeasonalityProfile` of type
  `event` marking a known abnormal window · buildable now (a σ-threshold clip is simple); ML-based history
  classification is integration/later
- **New-product / no-history forecasting from a reference ("like") item** — day-one forecasts for SKUs with no
  sales · seen in: RELEX (attribute-AI reference matching), John Galt (attribute-based), Anaplan (curve-fit
  from similar products), Blue Yonder · priority: common · spine: `DemandForecast.reference_item → scm.Item`
  (nullable, verified existing) + `reference_scale_pct` — copy the reference item's history curve, scaled ·
  buildable now (the simple like-item copy; attribute-similarity matching is deferred)
- **Revenue-valued forecast alongside the unit forecast** — planners and finance need both · seen in: Anaplan
  (quantity *and* price inputs), o9, Logility · priority: common · spine: `DemandForecastPeriod.unit_price` +
  derived value, with `DemandForecast.currency → accounting.Currency` (**verified existing**, `SET_NULL`) —
  no journal entry, no second ledger (L29) · buildable now

### Seasonality Analysis — adjustment of plans based on seasonal peaks and promotional events

- **Reusable seasonal index/profile curve applied to a baseline** — a per-period multiplier set (e.g. 12
  monthly indices averaging 1.0) attached to an item, a category, or a whole group · seen in: Netstock, Slim4
  (demand profile per product), Inventory Planner (seasonal vs. non-seasonal model per product), Oracle
  (seasonality as an explicit forecast component), SAP IBP · priority: table-stakes · spine: new tables
  `SeasonalityProfile` + child `SeasonalityIndex` (one row per period slot, `index_factor` Decimal) ·
  buildable now
- **Auto-derive the seasonal indices from history** — compute period-over-average ratios from N prior years
  instead of typing 12 numbers · seen in: Netstock, Slim4, RELEX, Oracle · priority: common · spine: a service
  on `SeasonalityProfile` that fills its `SeasonalityIndex` children from the same derived
  `SalesOrderLine`/`StockMove` series the forecast uses (`derived_from_years`, `last_derived_at`) ·
  buildable now
- **Promotional-event uplift with a date window** — a campaign/holiday window that lifts demand for specific
  items above baseline for its duration · seen in: RELEX (promotion type, price change, display placement),
  Blue Yonder, Logility (driver-based: promotions and events), Anaplan (promotion modelling), Inventory
  Planner (marketing activities) · priority: table-stakes · spine: the **same** `SeasonalityProfile` table with
  `profile_type = "promotion"/"event"` plus `event_start`/`event_end`/`uplift_pct` — a promotion is a seasonal
  curve with a finite window, so one table serves both halves of this bullet and gives it one list page ·
  buildable now
- **Cannibalization and halo effects between promoted and related products** — a promoted SKU steals demand
  from its siblings and lifts its complements · seen in: RELEX (headline capability), Blue Yonder · priority:
  differentiator · spine: `SeasonalityProfile.cannibalization_pct` + `affected_category → scm.ItemCategory`
  (verified existing) captures the *intent*, applied as a negative uplift to the category's other items;
  automatic ML detection of the effect is **deferred** · buildable now (the manually-entered effect only)
- **Product lifecycle curves (launch ramp / phase-out decay)** — demand shape driven by where a SKU is in its
  life · seen in: John Galt (lifecycle forecasting), Oracle (diverse product life cycles), Anaplan (curve-fit),
  RELEX · priority: common · spine: `SeasonalityProfile.profile_type = "lifecycle"` reusing the same index
  child rows (index by period-from-launch instead of calendar period) · buildable now
- **Weather-driven seasonal correction** — RELEX's signature short-horizon correction for weather-sensitive
  categories · seen in: RELEX, Kinaxis, Logility · priority: differentiator · spine: belongs with
  `DemandSignal` (`signal_type = "weather"`), not with the reusable curve; the live weather feed itself is
  **integration/later** · data hook buildable now
- **Differentiated profiles by location/channel** — the same SKU peaks differently per region · seen in: RELEX
  (SKU/location/day), Slim4 (service policy by product group, location and demand behaviour), John Galt ·
  priority: common · spine: `SeasonalityProfile.location → scm.Location` (nullable = applies everywhere,
  verified existing) · buildable now

### Demand Sensing — short-term forecasting using real-time market signals

- **A short-horizon signal distinct from the long-range plan** — SAP runs demand sensing as daily forecasts
  over a rolling ~4–8-week window on top of the consensus demand plan; the mechanism is explicitly separate
  from statistical planning · seen in: SAP IBP, RELEX, Blue Yonder, Kinaxis, Logility, o9 · priority:
  table-stakes (for a modern demand-planning module) · spine: new table `DemandSignal` with
  `horizon_days`/`effective_from`/`effective_to`, deliberately **not** folded into `DemandForecast` (different
  cadence, different lifecycle, different list page) · buildable now
- **Downstream/POS and channel-inventory signals** — sell-through rather than sell-in · seen in: RELEX (POS is
  the headline input), Blue Yonder, Logility (consumer sales, channel inventory), SAP IBP · priority:
  table-stakes · spine: `DemandSignal.signal_type = "pos_sell_through"/"channel_inventory"` ·
  buildable now (the row); the actual POS/retailer feed is **integration/later**
- **Real-time order-pattern deviation (order surge / drop-off)** — the one signal NavERP can compute from its
  own data today · seen in: SAP IBP (recent sales orders as an internal signal), Logility, Kinaxis · priority:
  table-stakes · spine: `DemandSignal.signal_type = "order_surge"`, generated by a service that compares
  recent `SalesOrderLine` volume against the forecast's `final_quantity` for the current period — reuses
  **verified-existing** 4.5 data, no integration required · buildable now
- **External signals: weather, competitor activity, macro indices, social sentiment, market events** · seen
  in: Kinaxis (weather, social media, consumer-behaviour shifts), Blue Yonder (hundreds of internal+external
  signals), RELEX (weather), Logility (social sentiment), o9 (macroeconomic indicators, event data) ·
  priority: common · spine: `DemandSignal.signal_type` choices + `source`/`source_reference` free text —
  the row is storable now, every live feed is **integration/later** (same posture as 4.6's `TrackingEvent`,
  which stores whatever is posted without owning a GPS integration)
- **Customer-supplied forecasts / collaborative (CPFR) commitments** — a key account tells you what it will
  order · seen in: John Galt (Planning Portal for customers), o9, Kinaxis, Anaplan (inputs from customers) ·
  priority: common · spine: `DemandSignal.signal_type = "customer_forecast"` + `customer → core.Party`
  (**verified existing** — a customer is a `PartyRole`, never a duplicated table) · buildable now
- **Review → apply → measure workflow on each signal** — a sensed signal is triaged, then either folded into
  the plan or dismissed · seen in: Blue Yonder (exception management + decision prioritization), Logility
  (anomaly surfaced for review), Slim4 (exception-based planning), Netstock (flags SKUs needing attention) ·
  priority: common · spine: `DemandSignal.status` (new/under_review/applied/dismissed/expired) +
  `applied_to_forecast → scm.DemandForecast` + `impact_pct`/`impact_quantity` writing into
  `DemandForecastPeriod.signal_adjustment_quantity` · buildable now
- **Automatic ML signal ingestion and unbiased blending of hundreds of signals** — Blue Yonder/o9's actual
  differentiator · seen in: Blue Yonder, o9, Kinaxis Planning.AI · priority: differentiator · spine: none ·
  **integration/later**

### Collaborative Planning — sales, marketing and finance input a consensus plan

- **Structured overrides from named business functions** — sales, marketing, finance and supply chain each
  submit their number against the statistical baseline · seen in: Anaplan (unites sales/marketing/finance;
  consensus-building rules), Kinaxis ("gather demand input from all key stakeholders"), o9, SAP IBP, Logility,
  Blue Yonder, Netstock (bottom-up/top-down/middle-out with stakeholder collaboration) · priority:
  table-stakes · spine: new table `ForecastAdjustment` with `contributor_function` choices +
  `submitted_by → settings.AUTH_USER_MODEL` and `org_unit → core.OrgUnit` (**verified existing**, the same FK
  HRM 3.40 `WorkforcePlan` uses) · buildable now
- **Reason codes and written rationale on every override** — an unexplained override is untraceable · seen in:
  o9 (commentary + explicit tracked assumptions, "explainable and auditable"), Oracle (documents plan
  discussions, decisions and assumptions), Logility, Anaplan · priority: table-stakes · spine:
  `ForecastAdjustment.reason_code` (promotion/new_customer/lost_customer/price_change/market_shift/
  competitor_action/product_launch/discontinuation/budget_target/known_bias/supply_constraint/other) +
  `rationale` TextField · buildable now
- **Override expressed as absolute / delta / percentage** — different functions think in different units ·
  seen in: Anaplan, o9, Netstock, Kinaxis · priority: common · spine:
  `ForecastAdjustment.adjustment_type` (absolute/delta/percent) + `proposed_quantity`/`adjustment_pct`, with
  `resolved_quantity` derived · buildable now
- **Accept / reject review gate producing the consensus number** — the demand manager reconciles competing
  inputs into one plan of record · seen in: o9 (automated consensus workflow with human judgment at the
  volatile points), SAP IBP, Anaplan (consensus rules by input accuracy and horizon), Kinaxis · priority:
  table-stakes · spine: `ForecastAdjustment.status` (proposed/accepted/rejected/superseded) +
  `reviewed_by`/`reviewed_at` (`editable=False`); accepted adjustments roll up into
  `DemandForecastPeriod.consensus_quantity` (mirrors the verified `SalesOrder.recompute_allocation_status`
  roll-up shape) · buildable now
- **Per-contributor accuracy / bias history ("whose input helps?")** — Anaplan weights consensus by input
  accuracy; FVA per contributor is the S&OP-practice version · seen in: Anaplan, Logility · priority:
  differentiator · spine: derived from `ForecastAdjustment` history vs. actuals — no new columns · buildable
  now (as a report on the adjustment list)
- **Finance/budget reconciliation of the demand plan** — is the demand plan consistent with the revenue
  budget? · seen in: Anaplan, o9, Netstock ("align financial and performance goals"), Kinaxis (financial +
  operational scenarios) · priority: common · spine: `ForecastAdjustment.contributor_function = "finance"`
  plus the revenue-valued forecast above; a hard link to **verified-existing** `accounting.Budget`/`BudgetLine`
  is **deferred** (it needs a GL-account ↔ item-category mapping that does not exist yet)
- **Threaded discussion / @-mentions / task assignment on a plan** · seen in: o9, Anaplan, Kinaxis, Oracle ·
  priority: common · spine: reuses **verified-existing** `core.Activity` (generic activity/notes anchor) and
  `core.Document` for attachments rather than a new comment table · buildable now (light) —
  a real notification/mention system is integration/later
- **Scenario / what-if planning (optimistic, pessimistic, promo-on/promo-off)** · seen in: Kinaxis (signature
  capability), o9, Anaplan, Blue Yonder, Slim4, John Galt · priority: common · spine:
  `DemandForecast.scenario` label + the `supersedes` self-FK gives cheap side-by-side versions; a full
  multi-scenario compare/merge engine is **deferred**

### Safety Stock Calculation — dynamic buffer stock based on demand variability

- **Service-level-driven statistical safety stock (Z × σ_demand × √lead time)** — the canonical formula; the
  Z-score comes from the target service level (90% → 1.28, 95% → 1.65, 97.5% → 1.96, 99% → 2.33) · seen in:
  Netstock (documented formula), Slim4 (dynamic safety stock driven by target service level), Inventory
  Planner, Blue Yonder/Kinaxis inventory optimization · priority: table-stakes · spine: **extend the
  verified-existing `scm.ReorderRule`** with `service_level_pct`, `lead_time_days`,
  `lead_time_variability_days`, `review_period_days`, `safety_stock_method` and the derived
  `avg_daily_demand`/`demand_std_dev`/`computed_safety_stock`/`computed_reorder_point`/`last_calculated_at` —
  **not** a parallel policy table that would duplicate the rule's `(tenant, item, location)` grain and its
  existing `safety_stock` column · buildable now
- **Periodic-review variant (Z × σ_d × √(T + L))** — for businesses on a fixed weekly ordering cycle · seen
  in: Netstock, Slim4 · priority: common · spine: the `review_period_days` field + a
  `safety_stock_method = "periodic_review"` branch · buildable now
- **Max-average method ((max sales × max lead time) − (avg sales × avg lead time))** — the simple method for
  short or noisy histories · seen in: Netstock, Inventory Planner · priority: common · spine:
  `safety_stock_method = "avg_max"`, computed from the same derived history series · buildable now
- **Forecast-error-based safety stock** — buffer sized from the forecast's own MAPE/σ_error rather than raw
  demand variance; the tie-in that makes 4.7 more than 4.3 with extra fields · seen in: Netstock (safety stock
  updated from forecast accuracy), Slim4, Blue Yonder, Kinaxis · priority: differentiator · spine:
  `safety_stock_method = "forecast_error"` reading the derived error series off `DemandForecastPeriod` ·
  buildable now
- **Seasonal safety stock — size the buffer from the comparable prior period, not the annual average** ·
  seen in: Netstock (explicit: use last December when planning this December), Slim4, Inventory Planner ·
  priority: common · spine: `ReorderRule.seasonality_profile → scm.SeasonalityProfile` (nullable) so the
  calculator scales σ and average demand by the current period's index · buildable now
- **Lead time and its variability sourced from real supplier performance** — σ of lead time matters as much as
  σ of demand · seen in: Netstock (supplier performance), Slim4, Inventory Planner · priority: common ·
  spine: default `lead_time_days` from **verified-existing** `SupplierCatalogItem.lead_time_days`
  (`SupplierCatalogs.py:55`) — note the 4.3 research file wrongly claimed this field already lived on
  `ReorderRule`; it does not · buildable now (seeded default + manual override); deriving actual σ from
  PO→GRN history is **deferred**
- **ABC / XYZ segmentation driving differentiated service-level policy** — high-value/low-variability items
  get different targets · seen in: Slim4 (headline), Netstock (automatic SKU classification), o9
  (forecastability-based segmentation), Kinaxis ("apply your segmentation strategy") · priority: common ·
  spine: derived `abc_class` (revenue rank over `SalesOrderLine`) + `xyz_class` (coefficient of variation of
  demand) as `editable=False` fields on the extended `ReorderRule`. Note `Location.abc_class` already exists
  but is a **bin-velocity** attribute added by 4.4 — a different axis; do not overload it · buildable now
  (trim first if the pass runs long)
- **Recalculate-and-apply action rather than a silent overwrite** — the planner reviews the computed number
  before it becomes the live reorder policy · seen in: Netstock, Slim4, Inventory Planner (recommendations
  the buyer accepts) · priority: table-stakes · spine: a POST action that copies
  `computed_safety_stock`/`computed_reorder_point` into the rule's existing `safety_stock`/`reorder_point`
  columns, so **4.3's live `scm:reorder_alerts` page keeps working unchanged** · buildable now
- **Multi-echelon inventory optimization (MEIO)** — optimize buffers across a network of stocking locations
  simultaneously · seen in: Blue Yonder, Kinaxis, o9, Logility · priority: differentiator · spine: none this
  pass (single-echelon per item/location only) · **deferred**

### Beyond the bullets (strong features the NavERP.md bullets do not name)

- **Exception-based planning: only surface the SKUs that need a human** — the dominant UX of the whole
  category · seen in: Slim4 ("exception-based planning"), Netstock (AI flags SKUs needing attention), Blue
  Yonder (decision prioritization), Logility, Kinaxis · priority: table-stakes · spine: **no new table** —
  filtered list pages plus a "forecast exceptions" report (|bias| over threshold, tracking signal beyond ±4,
  stock-out risk, unreviewed signals) over the four models this pass builds; exactly the
  `scm:reorder_alerts` precedent · buildable now
- **Explainability of the number ("why did the forecast move?")** — Oracle, Blue Yonder, John Galt and Kinaxis
  all sell transparency as a feature · priority: common · spine: satisfied structurally by keeping
  baseline / seasonal index / event uplift / signal adjustment / consensus in **separate columns** rather than
  one overwritten `quantity` — the detail page renders the waterfall · buildable now
- **Bulk import of history/forecast from spreadsheet** — every mid-market tool assumes a CSV somewhere · seen
  in: Anaplan (Excel add-in), Netstock, Inventory Planner · priority: common · spine: an `import.html`
  secondary action on the forecast entity folder (the `cash/bank_transaction/import.html` precedent) ·
  **deferred** to keep this pass at CRUD + calculator
- **Natural-language / agentic planning assistants** — Logility's DemandAI+ agents, RELEX's Product Attribute
  AI agent, o9's automation of routine consensus steps · priority: differentiator · spine: none ·
  **integration/later**

## Recommended build scope (this pass — 1–4 models)

Four new primary models (each with the CRUD list/detail/form triple), plus one additive extension of a
verified-existing sibling model and two computed report pages. Every bullet gets a real, distinct page.

1. **`DemandForecast`** [`DF-`] + child **`DemandForecastPeriod`** — serves **Sales Forecasting** (list page
   `scm:demandforecast_list`) and is the spine the other three hang off.
   `TenantNumbered`. Header fields: `name`, `item → scm.Item` (`PROTECT`, **verified existing**),
   `location → scm.Location` (`SET_NULL`, nullable = network-level, verified existing),
   `customer → core.Party` (`SET_NULL`, nullable = all channels, **verified existing** — a customer is a
   `PartyRole`, never a duplicate table), `demand_source` (sales_orders/stock_issues/manual — which verified
   ledger the history series is aggregated from), `bucket` (day/week/month/quarter),
   `horizon_start`/`horizon_end`, `history_months` (how far back the series reaches),
   `method` (naive/seasonal_naive/moving_average/weighted_moving_average/exponential_smoothing/holt_linear/
   holt_winters/like_item/manual/best_fit), `method_parameter` (window N or α, one Decimal),
   `selected_method` (`editable=False` — what best_fit chose), `seasonality_profile → scm.SeasonalityProfile`
   (`SET_NULL`, nullable), `reference_item → scm.Item` (`SET_NULL`, nullable — the like-item source for a new
   product), `reference_scale_pct`, `exclude_outliers` + `outlier_threshold_sigma`,
   `currency → accounting.Currency` (`SET_NULL`, **verified existing** — value display only, no JE, L29),
   `scenario` (baseline/optimistic/pessimistic/custom), `revision` + `supersedes` self-FK (`SET_NULL`),
   `status` (draft/statistical/in_review/approved/archived, `editable=False`, action-driven — mirrors
   `SalesOrder.status`), `generated_at`/`approved_by → settings.AUTH_USER_MODEL`/`approved_at`
   (`editable=False`), `notes`. Derived methods (never stored, mirroring `Item.on_hand`): `history_series()`,
   `actual_quantity(period)`, `mape()`, `wmape()`, `bias_pct()`, `tracking_signal()`,
   `forecast_value_added()` — with a `period_actuals_map()` batch helper in the exact shape of the verified
   `ReorderRule.on_hand_map()` so a list page does not fire N aggregates.
   Child `DemandForecastPeriod` (tenant-less child, matching the verified `SalesOrderLine`/`LoadStop`
   convention): `forecast` (`CASCADE`), `period_start`/`period_end`, `sequence`,
   `historical_quantity` (`editable=False`, the snapshot the model was fitted on), `baseline_quantity`,
   `seasonal_index_applied`, `event_uplift_quantity`, `signal_adjustment_quantity`, `consensus_quantity`
   (rolled up from accepted `ForecastAdjustment`s, `editable=False`), `final_quantity`, `unit_price`,
   `is_locked`. FKs: `scm.Item`, `scm.Location`, `core.Party`, `accounting.Currency`, `scm.SeasonalityProfile`
   (this pass) — all verified or built here.

2. **`SeasonalityProfile`** [`SEA-`] + child **`SeasonalityIndex`** — serves **Seasonality Analysis** (list
   page `scm:seasonalityprofile_list`). One table covers both halves of the bullet: a recurring seasonal curve
   *and* a windowed promotional event are the same thing at different `profile_type`s.
   `TenantNumbered`. Header: `name`, `profile_type` (seasonal/promotion/event/lifecycle),
   `bucket` (week/month/quarter/period_from_launch), `scope` (item/category/location/global),
   `item → scm.Item` (`SET_NULL`, nullable), `category → scm.ItemCategory` (`SET_NULL`, nullable, **verified
   existing**), `location → scm.Location` (`SET_NULL`, nullable), `event_start`/`event_end` (used by
   promotion/event types), `uplift_pct`, `cannibalization_pct` +
   `cannibalized_category → scm.ItemCategory` (`SET_NULL`, nullable), `promotion_mechanic`
   (price_discount/bogo/display/advert/bundle/other — RELEX's promotion attributes),
   `derived_from_years` + `last_derived_at` (`editable=False` — set when indices are auto-derived from the
   history series), `is_active`, `notes`.
   Child `SeasonalityIndex`: `profile` (`CASCADE`), `period_number` (1–12 / 1–53 / 1–4 / months-from-launch),
   `period_label`, `index_factor` (Decimal, 1.0000 = neutral), `sample_size` (`editable=False`).
   FKs: `scm.Item`, `scm.ItemCategory`, `scm.Location` — all verified existing.

3. **`DemandSignal`** [`DS-`] — serves **Demand Sensing** (list page `scm:demandsignal_list`). A short-horizon
   observation log with a triage workflow, deliberately separate from the long-range forecast (SAP IBP runs
   demand sensing as a distinct engine over a rolling 4–8-week window). Same "store whatever is posted, wire
   the feed later" posture as the verified `TrackingEvent` in 4.6.
   `TenantNumbered`. Fields: `signal_type` (order_surge/order_dropoff/pos_sell_through/channel_inventory/
   customer_forecast/weather/competitor_action/market_index/social_sentiment/promotion_live/supply_disruption/
   other), `source` (internal_orders/internal_stock/customer/retailer_pos/market_data/weather_service/manual/
   api), `source_reference`, `item → scm.Item` (`SET_NULL`, nullable = category-wide signal),
   `category → scm.ItemCategory` (`SET_NULL`, nullable), `location → scm.Location` (`SET_NULL`, nullable),
   `customer → core.Party` (`SET_NULL`, nullable — verified existing, for customer-supplied forecasts),
   `observed_at`, `effective_from`/`effective_to`, `horizon_days`, `signal_value`, `baseline_value`,
   `impact_direction` (increase/decrease/neutral), `impact_pct`, `impact_quantity`,
   `confidence` (low/medium/high), `status` (new/under_review/applied/dismissed/expired, `editable=False`
   after apply), `applied_to_forecast → scm.DemandForecast` (`SET_NULL`, nullable — the write-back target),
   `reviewed_by → settings.AUTH_USER_MODEL` (`SET_NULL`, nullable), `reviewed_at` (`editable=False`), `notes`.
   One service — `detect_order_surge(tenant)` — generates `order_surge`/`order_dropoff` rows by comparing
   recent `SalesOrderLine` volume against the active forecast's `final_quantity`, so the module ships with a
   real working signal from **verified-existing 4.5 data** and no external integration.

4. **`ForecastAdjustment`** [`FA-`] — serves **Collaborative Planning** (list page
   `scm:forecastadjustment_list`, which doubles as the consensus review queue via `?status=proposed`).
   `TenantNumbered`. Fields: `forecast → scm.DemandForecast` (`CASCADE`),
   `period → scm.DemandForecastPeriod` (`SET_NULL`, nullable = applies across the whole horizon),
   `contributor_function` (sales/marketing/finance/supply_chain/operations/executive/customer),
   `submitted_by → settings.AUTH_USER_MODEL` (`SET_NULL`, nullable — the verified pattern used by
   `PurchaseRequisition.requester`), `org_unit → core.OrgUnit` (`SET_NULL`, nullable, **verified existing**),
   `adjustment_type` (absolute/delta/percent), `proposed_quantity`, `adjustment_pct`,
   `resolved_quantity` (`editable=False`, derived from type + the period's pre-adjustment number),
   `reason_code` (promotion/new_customer/lost_customer/price_change/market_shift/competitor_action/
   product_launch/discontinuation/budget_target/known_bias/supply_constraint/other), `rationale` (TextField,
   required for anything but `other`… i.e. always encouraged), `confidence` (low/medium/high),
   `status` (proposed/accepted/rejected/superseded, `editable=False`, action-driven),
   `reviewed_by → settings.AUTH_USER_MODEL` (`SET_NULL`, nullable), `reviewed_at` (`editable=False`),
   `review_note`. Accepting an adjustment recomputes the target period's `consensus_quantity`/`final_quantity`
   — a roll-up guarded by status exactly like the verified `SalesOrder.recompute_allocation_status()`.

**Extension (not a new model) — `scm.ReorderRule` gains the safety-stock policy**, serving **Safety Stock
Calculation** via the report page `scm:safety_stock_report` (the `scm:reorder_alerts` / `scm:valuation_report`
precedent — a bullet may point at a computed report). Additive nullable/defaulted fields only, so 4.3's
existing pages and tests keep working: `safety_stock_method` (fixed/service_level/periodic_review/avg_max/
forecast_error), `service_level_pct` (default 95), `lead_time_days`, `lead_time_variability_days`,
`review_period_days`, `seasonality_profile → scm.SeasonalityProfile` (`SET_NULL`, nullable),
`demand_forecast → scm.DemandForecast` (`SET_NULL`, nullable — the source of forecast-error sizing), and the
`editable=False` derived set `avg_daily_demand`, `demand_std_dev`, `abc_class`, `xyz_class`,
`computed_safety_stock`, `computed_reorder_point`, `last_calculated_at`. The report page lists every active
rule with computed-vs-current values and a POST **apply** action that copies the computed numbers into the
rule's existing `safety_stock`/`reorder_point` columns — a reviewed hand-off, never a silent overwrite.
**Rationale for extending rather than adding a 5th model:** a new `SafetyStockPolicy` table would duplicate
`ReorderRule`'s `(tenant, item, location)` grain and its `safety_stock` column — the exact anti-pattern the
guardrails forbid; and 4.4 already set the precedent by extending 4.3's `Location` with bin attributes rather
than declaring a parallel table.

**Proposed `LIVE_LINKS["4.7"]`:** Sales Forecasting → `scm:demandforecast_list` · Seasonality Analysis →
`scm:seasonalityprofile_list` · Demand Sensing → `scm:demandsignal_list` · Collaborative Planning →
`scm:forecastadjustment_list` · Safety Stock Calculation → `scm:safety_stock_report`. A second report page,
`scm:forecast_accuracy_report` (MAPE/WMAPE/bias/tracking-signal/FVA league table across forecasts), is
recommended as the module's exception-management landing spot but is **not** a bullet.

Every FK above resolves to a **verified-existing** entity (`scm.Item`, `scm.ItemCategory`, `scm.Location`,
`scm.SalesOrder`/`SalesOrderLine`, `scm.StockMove`, `scm.ReorderRule`, `scm.SupplierCatalogItem`,
`core.Party`, `core.OrgUnit`, `accounting.Currency`, `settings.AUTH_USER_MODEL`) or to a model built in this
pass. **No stand-in for an unbuilt master is required** — unlike 4.1 and 4.6, this sub-module ships after the
item catalog and the sales order, so there is nothing to work around. **No new demand-history table is
created**: history is always an aggregate over `SalesOrderLine` (through `sales_order__order_date`, excluding
`draft`/`cancelled`) or `StockMove` (`move_type="issue"`), matching the derived-never-stored rule that governs
`Item.on_hand` and `SalesOrderLine.quantity_allocated`.

## Belongs to sibling sub-modules (parked, not scoped here)

- **Automated PO/requisition generation from a forecast shortfall** → 4.1 Procurement + 4.3's existing
  `scm:reorder_alerts` → `requisition_create` hand-off. 4.7 computes and applies the *policy numbers*; the
  buyer-facing replenishment action stays where it already works.
- **Supply-side planning: capacity checks, constrained supply plan, MRP netting, distribution requirements
  planning** → 4.8 Manufacturing / Production (MRP bullet). 4.7 is demand-side only; a constrained supply plan
  is a different engine and a different sub-module.
- **Inventory turnover, dead-stock, aging and demand-spike dashboards** → 4.11 Supply Chain Analytics
  (Inventory Dashboards + Predictive Analytics bullets). This pass ships two focused report pages
  (safety-stock calculator, forecast accuracy) and no analytics suite.
- **Sales-pipeline/quota forecasting (weighted opportunity value, quota attainment)** → already built as
  CRM 1.2 (`crm:forecast`, `crm.SalesQuota`, `Opportunity.forecast_category`). Different object (deals, not
  SKUs) — do not merge or re-point.
- **Cash-flow forecasting** → already built as Accounting 2.5 (`accounting:cash_forecast`). Financial
  projection stays in accounting (L29).
- **Allocating forecasted (not on-hand) stock to open orders** → 4.5 OMS owns `SalesOrderAllocation`; the
  forecast-driven pre-emptive allocation it deferred here needs an allocation-engine change in 4.5, not a
  4.7 table.
- **Headcount/workforce demand forecasting** → HRM 3.40 (`hrm:workforceplan_list`), already built.
- **Promotion budget/spend management and campaign execution** → CRM 1.3 Marketing Automation owns campaigns;
  4.7 only models a promotion's *demand uplift window*, not its budget or creative.

## Deferred (later passes / integrations)

- **Machine-learning / ensemble / Bayesian forecast engines** (Oracle's Bayesian weighting, John Galt's
  reinforcement learning, Blue Yonder/o9/Kinaxis AI) — this pass ships deterministic, auditable Decimal
  arithmetic (moving average, weighted MA, exponential smoothing, Holt, Holt-Winters, seasonal naive,
  like-item, best-fit-by-MAPE). No numpy/pandas/scikit dependency is introduced.
- **Live external signal feeds** (POS/retailer EDI, weather services, market indices, social sentiment) —
  `DemandSignal` stores whatever is posted and one internal detector (`order_surge`) actually runs; every
  external feed is an integration, exactly the posture 4.6 took with `TrackingEvent`.
- **Automatic cannibalization/halo *detection*** (RELEX's headline ML capability) — this pass captures a
  manually-entered `cannibalization_pct` against a category; inferring the effect from data is later.
- **True multi-level hierarchy planning with proportional top-down/middle-out disaggregation** — needs an
  allocation engine across item↔category↔channel↔region; this pass forecasts at item (× optional location ×
  optional customer) and rolls up for reporting only.
- **Multi-echelon inventory optimization (MEIO)** — single-echelon per (item, location) only.
- **Attribute-similarity new-product matching** — the simple `reference_item` + scale copy ships; automatic
  "find the most similar SKU by attributes" does not (`Item` has no attribute framework).
- **Deriving supplier lead-time variability from actual PO→GRN history** — `lead_time_days` /
  `lead_time_variability_days` are entered (defaultable from the verified `SupplierCatalogItem.lead_time_days`)
  this pass; computing σ from `PurchaseOrder`/`GoodsReceiptNote` timestamps is a natural follow-up.
- **Hard link between the revenue-valued forecast and `accounting.Budget`/`BudgetLine`** — both exist and are
  verified, but the join needs a GL-account ↔ item-category mapping that does not exist; the finance
  contributor function on `ForecastAdjustment` is the interim seam.
- **Spreadsheet import/export of history and forecast grids** (Anaplan's Excel add-in, Netstock/Inventory
  Planner CSV) — an `import.html` secondary action on the forecast entity folder, later.
- **Full multi-scenario compare/merge and simulation** (Kinaxis's signature) — `DemandForecast.scenario` +
  `supersedes` give cheap side-by-side versions; an interactive scenario workbench is out of scope for a
  Django/HTMX CRUD pass.
- **Per-contributor accuracy weighting of consensus inputs** (Anaplan's consensus-by-input-accuracy) — the
  data to compute it is stored by `ForecastAdjustment` this pass; the weighting engine is later.
- **Notification/mention/approval-routing on collaborative plans** — `core.Activity` covers lightweight notes;
  real dispatch follows the same "hook now, wire later" posture as 4.5's notification fields.
- **Scheduled/automatic forecast regeneration** (nightly re-forecast, rolling horizon roll-forward) — this
  pass regenerates on an explicit user action; a management command / scheduler is a follow-up.
- **`ABC`/`XYZ` classification** is listed in scope but is the **first thing to trim** if the pass runs long —
  it is two derived fields plus a ranking service, and nothing else depends on it.

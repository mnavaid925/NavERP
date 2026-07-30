# Research — Sub-module 4.11: Supply Chain Analytics (Module 4 — Supply Chain Management, `scm`)

**NavERP.md feature bullets (lines 803–808) this pass is scoped against:**

- **Inventory Dashboards** — Visual reporting on turnover rates, dead stock, and aging inventory.
- **Procurement Analytics** — Spend analysis, supplier performance trends, and cost-saving opportunities.
- **Logistics KPIs** — On-time delivery rates, freight cost per unit, and vehicle utilization reports.
- **Financial Reporting** — Gross margin analysis and supply chain cost breakdowns.
- **Predictive Analytics** — AI-driven predictions for potential disruptions or demand spikes.

**Headline finding:** in every product surveyed, an analytics module is *overwhelmingly computed pages over
transactional rows*. The only things the leaders actually **store** are (a) metric **targets/thresholds**,
(b) **point-in-time snapshots** of computed values, and (c) **alert/exception instances with human state**
(acknowledged / assigned / resolved). Everything else is a query. 4.11 should follow that shape exactly:
**5 computed dashboard pages + 3 stored models.**

---

## Repo state checked first

### LIVE_LINKS built so far in module 4 (`apps/core/navigation.py`)
`"4.1"` … `"4.10"` are all present; **`"4.11"` is absent → 4.11 is the next unbuilt sub-module.** Confirmed.

### As-built SCM entities available to READ (from `apps/scm/models/__init__.py` — the real re-export list)
| Sub-module | Models 4.11 aggregates over |
|---|---|
| 4.1 Procurement | `PurchaseRequisition(+Line)`, `RFQ(+Line/Vendor/Quote/QuoteLine)`, `PurchaseOrder(+Line)`, `GoodsReceiptNote(+Line)` |
| 4.2 SRM | `SupplierProfile`, `SupplierScorecard`, `SupplierContract`, `SupplierCatalog(+Item)`, `SupplierRiskAssessment` |
| 4.3 Inventory | `ItemCategory`, `UOM`, `Item`, `Location`, `LotSerial`, `StockMove`, `StockTransfer(+Line)`, `StockAdjustment(+Line)`, `ReorderRule` |
| 4.4 WMS | `PutawayTask`, `PickTask(+Line)`, `CycleCountTask(+Line)`, `YardVisit` |
| 4.5 OMS | `SalesOrder(+Line)`, `SalesOrderAllocation` |
| 4.6 TMS | `Carrier`, `CarrierRateCard`, `Load`, `LoadStop`, `Shipment`, `TrackingEvent`, `FreightInvoice(+Line)` |
| 4.7 Planning | `SeasonalityProfile(+Index)`, `DemandForecast(+Period)`, `DemandSignal`, `ForecastAdjustment` |
| 4.8 Manufacturing | `WorkCenter`, `BillOfMaterials(+BOMLine)`, `WorkOrder(+Component)`, `ProductionTimeLog` |
| 4.9 QMS | `InspectionPlan(+Characteristic)`, `QualityInspection(+InspectionResult)`, `QualityAudit`, `NonConformance`, `CapaAction(+Task)` |
| 4.10 Returns | `ReturnReason`, `ReturnPolicy`, `ReturnAuthorization(+ReturnLine)`, `ReturnDisposition`, `WarrantyClaim(+Cost)` |

### Spine entities VERIFIED to exist (grep evidence, not the ERD)
```
apps/core/models/Tenant.py:5:class Tenant           apps/core/models/Party.py:5:class Party
apps/core/models/PartyRole.py:5:class PartyRole     apps/core/models/OrgUnit.py:5:class OrgUnit
apps/core/models/Address.py:5:class Address         apps/core/models/Document.py:5:class Document
apps/accounting/models/GeneralLedger/Currencies.py:6:class Currency
apps/accounting/models/GeneralLedger/GLAccounts.py:5:class GLAccount
apps/accounting/models/GeneralLedger/FiscalPeriods.py:5:class FiscalPeriod
apps/accounting/models/GeneralLedger/JournalEntries.py:5:class JournalEntry
apps/accounting/models/AccountsReceivable/Invoices.py:6:class Invoice
apps/accounting/models/AccountsPayable/Bills.py:6:class Bill
apps/crm/models/AnalyticsReporting/Dashboards.py:6:class AnalyticsDashboard
apps/crm/models/AnalyticsReporting/Widgets.py:6:class DashboardWidget
apps/crm/models/AnalyticsReporting/Reports.py:6:class AnalyticsReport
apps/crm/models/AnalyticsReporting/Snapshots.py:5:class ReportSnapshot
apps/scm/models/_base.py:53:class TenantOwned    apps/scm/models/_base.py:66:class TenantNumbered
```

### Key field-level facts verified (these constrain what is honestly computable)
- `StockMove`: `item, location, lot_serial, quantity` (**signed**), `unit_cost`, `move_type ∈ {receipt, issue,
  transfer, adjustment, consumption, production}`, `reference`, `moved_at`. Append-only.
  **`issue` = customer demand; `consumption` = work-order draw** — deliberately distinct (4.8 comment). Any
  turnover/COGS metric must decide which to include and say so.
- `Item`: `sku, category, uom, item_type, tracking, costing_method, standard_cost, average_cost (editable=False),
  reorder_point`; helper `Item.on_hand(location=None)` exists; `ReorderRule.on_hand_map(tenant, rules)` is the
  **bulk** helper; `Location.on_hand_value` exists. Use the bulk map — never `on_hand()` in a loop.
- `ReorderRule` already carries `abc_class`, `xyz_class`, `lead_time_days`, `safety_stock`,
  `computed_safety_stock`, `avg_daily_demand`, `demand_std_dev` (4.7 extended it). **ABC/XYZ already exists —
  4.11 reads it, does not recompute a second classification.**
- `LotSerial.expiry_date` exists → expiry-risk aging is real.
- `PurchaseOrderLine` has **`item_description` / `sku_hint` free text and NO `Item` FK** (4.1 predates the 4.3
  catalog). Spend-by-*category* must therefore come from `PurchaseOrderLine.gl_account` (verified FK to
  `accounting.GLAccount`) or from a `sku_hint` → `Item.sku` join — **state the caveat on the page, don't fake a
  category dimension.**
- `PurchaseOrder`: `vendor(core.Party)`, `requisition`, `quote(RFQQuote)`, `currency`, `order_date`,
  `expected_date`, `subtotal/tax_total/total`, `acknowledged_at`, `promised_ship_date`, `ship_to(core.OrgUnit)`.
- `SalesOrderLine`: `item` FK **does** exist (nullable), `quantity_ordered`, `unit_price`, `discount_pct`,
  `tax_pct`; `quantity_allocated()` is a **method**, and there is **no `quantity_shipped` column** → "in full"
  must be derived from allocations / `issue` StockMoves, not read off a field.
- `Shipment`: `planned_delivery_date`, `actual_delivery_at`, `actual_pickup_at`, `weight_kg`, `volume_cbm`,
  `package_count`, `eta`, `pod_received`, `sales_order`, `purchase_order`, `carrier`, `load`, `origin_text`,
  `destination_text`. `Load`: `distance_km`, `equipment_capacity_weight_kg/volume_cbm`, `freight_cost_estimate`,
  `planned/actual_departure/arrival`. `FreightInvoice`: `billed_amount`, `contract_amount`, `variance_amount`,
  `variance_pct`, `match_status`. **Every logistics KPI below has a real column behind it.**
- `Carrier.on_time_delivery_pct` is already a 4.6-derived cached field → 4.11 **trends** it, does not restate it.
- `NonConformance` has `supplier(core.Party)`, `severity`, `defect_category`, `cost_of_quality`, `source`,
  `goods_receipt`, `item` → real quality signal per supplier.
- `SupplierContract` has `party`, `start_date`, `end_date`, `status`, `contract_value`, `renewal_notice_days` →
  real off-contract / expiry signal.
- `SupplierScorecard` (4.2) **already derives** delivery/quality/price/responsiveness per period from GRN + RFQ
  signals, with `signal_summary` explaining the arithmetic. 4.11 must **trend the stored scorecards**, never
  recompute a rival supplier score.
- `SupplierRiskAssessment` (4.2) **already stores** a human financial/geopolitical/compliance/operational risk
  with `risk_index` + `risk_level`. 4.11's disruption score **consumes** it as one input — it must not become a
  second supplier risk register.

### Existing "a bullet may be a computed report" precedent in this app (URL names verified)
`scm:valuation_report`, `scm:reorder_alerts`, `scm:on_hand_by_location`, `scm:safety_stock_report`,
`scm:forecast_accuracy_report`, `scm:mrp_report`, `scm:production_schedule`, `scm:coa_report`,
`scm:refund_queue` — each lives in a `views/<SubModule>/Reports.py` + `urls/<SubModule>/Reports.py` pair.
**4.11 is that pattern at full scale: `views/SupplyChainAnalytics/Reports.py`.**

### CRM 1.6 pattern — what 4.11 reuses conceptually vs. what it must NOT copy
`AnalyticsDashboard` (`DASH-`, owner/is_shared/is_default/layout) + `DashboardWidget` (metric choice + chart
type + date range + size + `target_value` + position) + `AnalyticsReport` (`RPT-`) + `ReportSnapshot`
(`summary` JSON + `data` JSON, created only by a POST action, never a user form), driven by
`apps/crm/analytics.py` (`WIDGET_METRICS` registry, `range_bounds()`, `compute_widget()`, `compute_report()`).

- **REUSE the ideas:** (1) a **closed metric registry** — a `CHOICES` list of metric keys whose compute
  functions live in an `analytics.py`, so nothing is user-authored SQL; (2) `range_bounds()`-style date-window
  selector; (3) `target_value` on the tracked KPI for progress-to-target; (4) the **snapshot-is-system-written,
  never-a-form** rule; (5) `last_run_at` stamped on render, not on the form.
- **DO NOT copy the dashboard-canvas half.** A second `AnalyticsDashboard`/`DashboardWidget` pair in `scm`
  would be a generic BI engine rebuilt per app — and **Module 10 (`bi`) explicitly owns that**: 10.8 Dashboards
  & Visualization (drag-and-drop builder, personalization), 10.10 Self-Service & Ad-Hoc, 10.11 *KPI Library &
  Definitions with formulas/targets/thresholds/owners*, 10.12 OLAP cubes, 10.16 Alerts/Subscriptions/
  Distribution. 4.11 ships **fixed, purpose-built subject-area pages** — which is precisely what Oracle Fusion
  SCM Analytics, Netstock and project44 actually ship — plus a **closed, SCM-only** target/threshold row.
  Boundary line to state in code comments: *10.11 lets you author a formula for any domain; 4.11 lets you set a
  target on one of ~35 hard-coded supply-chain metrics.*

---

## Leaders surveyed (with source links)

1. **SAP IBP for Supply Chain Control Tower** — the reference implementation of *definition → threshold →
   alert → case*. Custom alerts are a 4-step wizard (General info incl. **severity + category**, Data selection,
   **Alert rules** with threshold key + value + `Greater than`/`Less than` operators, Display options), evaluated
   at a **calculation level** (Product/Location/Customer × Month/Week), with **subscriptions** that filter scope,
   an **alerts overview added to dashboards**, and alerts that become **cases assigned to a responsible user**
   with attached **procedure playbooks** —
   [learning.sap.com — Creating Custom Alerts](https://learning.sap.com/courses/mastering-the-main-features-and-function-in-sap-supply-chain-control-tower/creating-custom-alerts),
   [Optimizing Custom Alerts](https://learning.sap.com/learning-journeys/discovering-sap-ibp-for-supply-chain-control-tower/optimizing-custom-alerts-in-sap-supply-chain-control-tower)
2. **Blue Yonder Supply Chain Command Center (Luminate Control Tower)** — KPI-breach alerting ("projected
   inventory for SKU X drops below safety stock in week 5"), automated **exception detection of anomalies with
   material impact**, **bottleneck visualization** across suppliers/factories/DCs/channels, scenario compare,
   and **Resolution Rooms** that turn an exception into a collaborative, audit-trailed decision —
   [blueyonder.com/solutions/supply-chain-command-center](https://blueyonder.com/solutions/supply-chain-command-center),
   [What is a Planning Control Tower?](https://info.blueyonder.com/supply-chain-command-center/what-is-a-planning-control-tower)
3. **Kinaxis Maestro (control tower + embedded analytics)** — customizable dashboards, **S&OP scorecards inside
   the dashboard**, user-created **flexible exceptions and alerts**, explicit **alert tuning to fight planner
   alert-fatigue**, and side-by-side **scenario scorecards** —
   [Gartner Peer Insights — Kinaxis Maestro](https://www.gartner.com/reviews/market/analytics-and-decision-intelligence-platforms-in-supply-chain/vendor/kinaxis/product/kinaxis-maestro-platform),
   [Kinaxis Control Tower overview](https://simbustech.com/kinaxis-control-tower/)
4. **o9 Solutions Digital Brain — Supply Chain Control Tower** — **proactive exception detection before an alert
   fires** (planner-override tracking, inbound material flow vs production commitments, **aging inventory risk
   flagging**), "order-at-risk" demand alerts fed by carrier ETAs, node-level KPIs with **only constrained nodes
   highlighted** plus root-cause analytics, personalized push notifications —
   [o9 Supply Chain Control Tower](https://o9solutions.com/solutions/supply-chain-planning/supply-chain-control-tower),
   [Why you need a control tower](https://o9solutions.com/articles/what-is-a-control-tower-and-why-do-you-need-one)
5. **Oracle Fusion SCM Analytics (Fusion Data Intelligence)** — a **prebuilt KPI library** plus named
   **subject areas**: Sales Order Fulfillment Analysis, Open Sales Order Analysis, Inventory Transaction
   Analysis, Procurement Spend Supplier Overview, Supplier Shipment Analysis, Purchase Agreement Analysis;
   **personalized KPI dashboards** assembled per audience (QBR, business unit, cost center, product line);
   root-cause drill for lost discounts and spend-consolidation opportunities —
   [oracle.com/business-analytics/fusion-scm-analytics](https://www.oracle.com/business-analytics/fusion-scm-analytics/),
   [Fusion Analytics KPI Library](https://www.oracle.com/business-analytics/fusion-data-intelligence-platform/capabilities/kpis/)
6. **Sievo Spend Analytics** — the spend-analytics benchmark: **spend cube**, AI classification against a
   custom taxonomy, **supplier normalization/deduplication**, **60+ best-practice dashboards**,
   **transaction-level drill-down through the whole spend landscape**, **savings-initiative tracking from idea to
   execution**, payment-terms and category price benchmarks, and explicit **weekly/monthly refresh cycles**
   (data freshness is a stated product feature) —
   [sievo.com/solutions/spend-analysis](https://sievo.com/solutions/spend-analysis),
   [Spend Analysis 101](https://sievo.com/en/resources/spend-analysis-101)
7. **Coupa (Spend Analysis + Supply Chain Design, ex-LLamasoft)** — **cost-to-serve computed automatically per
   product and per customer with all fixed and variable costs allocated**, carbon calculated alongside cost,
   digital-twin what-if scenarios, community benchmark data —
   [Coupa Supply Chain Design](https://www.coupa.com/products/supply-chain-design/),
   [What Is Cost To Serve?](https://www.coupa.com/blog/cost-serve-framework-for-profitability-and-customer-excellence/),
   [Network Optimization](https://www.coupa.com/products/supply-chain-design/network-optimization/)
8. **GEP SMART / GEP Quantum Intelligence** — spend-analysis agents that **surface anomalies and inefficiencies
   against budget**, market-intelligence price-trend analysis to find sourcing opportunities, insight creation
   that **identifies savings opportunities and emerging category patterns**, and tail-spend management —
   [gep.com — spend analysis software](https://www.gep.com/software/gep-smart/procurement-spend-analysis-software)
9. **project44 Movement (Freight Procurement Analytics)** — the logistics-KPI reference: **carrier performance
   scorecards** (reliability score, cost, on-time), **lane analytics**, lane/equipment-level **rate benchmarking**,
   **exception trend analysis**, OTIF baselines, contract-coverage gap detection, and scorecards explicitly
   produced **ahead of QBRs** —
   [project44 Freight Procurement Analytics](https://www.project44.com/platform/tms/freight-procurement-analytics/),
   [project44 Visibility](https://www.project44.com/platform/visibility/)
10. **FourKites** — OTIF tracking, carrier performance analysis, **cost by lane and service type**, inventory
    level/safety-stock monitoring, and shipment-risk identification for at-risk delivery commitments —
    [fourkites.com — supply chain analytics](https://www.fourkites.com/platform/supply-chain-analytics/)
11. **Netstock** — the SMB inventory-analytics shape: **SKU-level drill-down from high-level KPI to item detail**,
    exception alerts that surface only the SKUs/suppliers needing attention today, **KPI benchmarking of fill
    rate, stock turns and carrying cost across categories or locations**, aged-inventory lot tracking, dead-stock
    surfacing, SKU-level profitability, forecast accuracy —
    [Netstock inventory analytics](https://www.netstock.com/blog/inventory-analytics-and-data-reporting/),
    [Netstock product](https://www.netstock.com/product/)
12. **Anaplan Supply Chain** — KPI review reports that surface operational anomalies, A/B scenario comparison,
    inventory segmentation, spend analysis for sourcing optimization, product-mix profitability —
    [anaplan.com/solutions/supply-chain](https://www.anaplan.com/solutions/supply-chain/)
13. **Resilinc RiskShield / Everstream Analytics** (risk-scoring reference for the Predictive bullet) — a
    **composite, configurable supplier resiliency score** built from named components (past disruptions,
    recovery time, performance, financial health, ESG, cyber, business continuity), **six risk areas**
    (operational, cyber, environmental, financial, compliance, social-geopolitical), **sole-source supplier
    identification**, automated supplier scorecards, and event monitoring tied back to specific supply-chain
    nodes so signals can be prioritised by real operational impact —
    [Resilinc RiskShield](https://www.resilinc.com/solutions/riskshield/),
    [Resilinc supplier risk scorecard](https://resilinc.ai/supplier-risk-scorecard/),
    [Everstream vs Resilinc, Gartner Peer Insights](https://www.gartner.com/reviews/market/supplier-risk-management-solutions/compare/everstream-analytics-vs-resilinc)

---

## Feature catalog (this sub-module only)

Legend — **spine**: `→` reuses a verified existing entity; `NEW` = one of the 3 recommended models.
Every "aggregates over" list names only tables verified above.

### Bullet 1 — Inventory Dashboards (turnover, dead stock, aging)
> **Best served by a COMPUTED page with no new model.** All five metrics fall out of the append-only
> `StockMove` ledger + `Item` + `ReorderRule`.

- **Inventory turnover / stock turns** — cost of goods issued in the window ÷ average on-hand value; shown as
  turns and as days-on-hand · seen in: Netstock, Oracle SCM Analytics, Anaplan, Coupa · **table-stakes** ·
  spine: → `StockMove` (`move_type ∈ {issue, consumption}` × `unit_cost`), `Item`, `Location` ·
  **buildable now**. *Decision to record on the page: `issue` = customer demand, `consumption` = production
  draw; `transfer` is excluded (it double-counts, exactly as the existing FIFO/LIFO walk excludes it).*
- **Dead / obsolete stock** — items with positive derived on-hand and **zero** `issue`/`consumption` movement for
  N days, valued · seen in: Netstock (dead stock), o9 (aging inventory risk), Sievo-adjacent · **table-stakes** ·
  spine: → `StockMove`, `Item`, `ReorderRule.on_hand_map()` · **buildable now**. N is a stored threshold → NEW
  `KpiTarget`.
- **Aging inventory buckets** — remaining FIFO cost layers bucketed by the age of their receipt move
  (0–30 / 31–60 / 61–90 / 91–180 / 181+ days), by item and category · seen in: Netstock (aged-inventory lot
  tracking), o9, Oracle Inventory Transaction Analysis · **table-stakes** · spine: → `StockMove.moved_at`
  layer walk (the 4.3 valuation walk, re-bucketed), `ItemCategory` · **buildable now**.
- **Expiry-risk value** — on-hand tied to `LotSerial.expiry_date` inside N days, valued · seen in: Netstock,
  Blue Yonder (spoilage/chain-of-custody) · **common** · spine: → `LotSerial`, `StockMove` · **buildable now**.
- **Excess vs. policy** — on-hand above `ReorderRule.safety_stock`/`computed_safety_stock` + cover, valued ·
  seen in: Netstock, o9, Kinaxis · **common** · spine: → `ReorderRule` (4.7-extended), `StockMove` ·
  **buildable now**.
- **ABC/XYZ mix and Pareto** — value/volume concentration of the catalogue · seen in: Sievo (ABC),
  Netstock, Anaplan (segmentation) · **common** · spine: → **`ReorderRule.abc_class`/`xyz_class` already
  exist (4.7)** — read them, do not compute a rival classification · **buildable now**.
- **Fill rate / stockout count trend** — count at-or-below reorder point over time · seen in: Netstock
  (fill rate benchmarking), FourKites · **common** · spine: → `ReorderRule`, `Item.reorder_point`, `StockMove`;
  the *live* alert list is already `scm:reorder_alerts` (4.3) — 4.11 shows the count and its **trend** only ·
  **buildable now**.
- **SKU-level drill-down from KPI tile to item detail** — click a bucket, get the item rows, click an item, land
  on the existing 4.3 item detail · seen in: Netstock (explicit "high-level KPI to item detail in seconds"),
  Sievo (transaction-level traceability), Oracle · **table-stakes** · spine: → existing `scm:item_detail` ·
  **buildable now**.
- **Carrying cost** — on-hand value × an annual carrying rate · seen in: Netstock (carrying-cost benchmarking) ·
  **common** · spine: → `StockMove` + a **stored rate parameter** on NEW `KpiTarget` · **buildable now**.

### Bullet 2 — Procurement Analytics (spend, supplier trends, cost-saving opportunities)
> **Best served by a COMPUTED page with no new model** (the spend cube is a `values().annotate()`, not a table).

- **Spend cube — supplier × category × business unit × period** — slice-and-dice the same spend total ·
  seen in: Sievo, Coupa, GEP, Oracle (Procurement Spend Supplier Overview), Zycus · **table-stakes** ·
  spine: → `PurchaseOrder` (`vendor`→`core.Party`, `order_date`, `total`, `ship_to`→`core.OrgUnit`),
  `PurchaseOrderLine.gl_account`→`accounting.GLAccount` · **buildable now** *with the honest caveat that the
  category axis is GL-account/`sku_hint`-based because 4.1 PO lines carry no `Item` FK.*
- **Supplier concentration / single-source exposure** — top-N share of spend, count of vendors, share of
  `sku_hint`s with exactly one supplier · seen in: Sievo (supplier consolidation), Resilinc (sole-source
  identification), Coupa · **common** · spine: → `PurchaseOrder`, `PurchaseOrderLine`, `SupplierCatalogItem` ·
  **buildable now**. (Explicitly deferred here by `research-scm-4.2.md` line 339.)
- **Off-contract ("maverick") spend %** — PO value in the window with **no active `SupplierContract`** for that
  vendor at `order_date`, plus POs with `requisition IS NULL` as an unrequisitioned-buy proxy · seen in: Sievo
  (contract compliance rate), Coupa, GEP, Zycus · **table-stakes** · spine: → `PurchaseOrder`,
  `SupplierContract` (`party`, `start_date`, `end_date`, `status`) · **buildable now**. *Caveat: vendor-level,
  not line-item-level — NavERP has no contract↔item linkage yet.*
- **Tail-spend concentration** — the long tail of vendors making up the bottom decile(s) of value · seen in:
  Sievo, GEP (tail-spend management), JAGGAER · **common** · spine: → `PurchaseOrder` · **buildable now**.
- **Realized negotiation savings** — for POs awarded from an RFQ: awarded `RFQQuote.total` vs the median/max
  competing quote on the **same** RFQ · seen in: GEP (savings identification), Sievo, Coupa · **differentiator**
  and *genuinely evidence-backed here* · spine: → `PurchaseOrder.quote`, `RFQQuote`, `RFQ` · **buildable now**.
- **Price-variance / consolidation opportunity** — the same `sku_hint` bought at different unit prices across
  vendors or periods; opportunity value = qty × (paid − best) · seen in: Sievo (price variance), GEP (market
  intelligence price trends), Oracle (spend consolidation) · **common** · spine: → `PurchaseOrderLine`,
  `SupplierCatalogItem` · **buildable now**.
- **Supplier performance trend** — `SupplierScorecard.overall_score`/`grade` plotted by `period_end`, per
  supplier and blended · seen in: project44 (QBR scorecards), Oracle, Sievo, Resilinc · **table-stakes** ·
  spine: → **`SupplierScorecard` (4.2) — read the stored rows; do NOT re-derive a rival score** ·
  **buildable now**.
- **On-time-delivery and reject-rate leaderboard (all suppliers at once)** — `GoodsReceiptNote.receipt_date`
  vs `PurchaseOrder.expected_date`; `GoodsReceiptLine.quantity_rejected ÷ (received+rejected)` · seen in:
  project44, Sievo, Oracle Supplier Shipment Analysis · **table-stakes** · spine: → `GoodsReceiptNote(+Line)`,
  `PurchaseOrder` · **buildable now**. *Uses the identical formula as `SupplierScorecard.recompute_from_signals`
  — factor it into `analytics.py` so the two can never disagree.*
- **Procurement cycle time & lead time** — requisition→PO days and PO→GRN days, by vendor/category · seen in:
  Sievo (procurement cycle time), Oracle, GEP · **common** · spine: → `PurchaseRequisition`, `PurchaseOrder`,
  `GoodsReceiptNote` · **buildable now**.
- **Spend vs budget / anomaly against budget** — GEP's "budget alignment" · **differentiator** ·
  spine: → `accounting.Budget` exists · **defer** — SCM must not restate accounting's budget variance
  (that is Accounting 2.x + Procurement 6.15); link out instead.
- **Spend classification, supplier normalization/dedup, external category price indices, community
  benchmarks** — seen in: Sievo, Coupa, GEP · **integration/later** — needs external data or an ML classifier;
  out of scope for a Django aggregate pass.

### Bullet 3 — Logistics KPIs (on-time delivery, freight cost per unit, vehicle utilization)
> **Best served by a COMPUTED page with no new model.** 4.6 already stores every column needed.

- **On-time delivery rate (OTD)** — delivered shipments with `actual_delivery_at::date ≤
  planned_delivery_date`, by carrier / lane / month · seen in: project44, FourKites, Blue Yonder, Oracle ·
  **table-stakes** · spine: → `Shipment` · **buildable now**.
- **OTIF (on-time *in full*)** — OTD ∧ fully-shipped · seen in: project44 (explicit OTIF baseline), FourKites ·
  **common** · spine: → `Shipment` + `SalesOrder`/`SalesOrderLine` + `SalesOrderAllocation` ·
  **buildable now with a caveat** — `SalesOrderLine` has **no `quantity_shipped` column**, so "in full" must be
  derived from allocations / `issue` StockMoves; define it once in `analytics.py` and say so on the page.
- **Freight cost per unit** — audited `FreightInvoice.billed_amount` ÷ (kg | m³ | package | shipment | km),
  selectable basis · seen in: project44, FourKites (cost by lane and service type), Coupa · **table-stakes** ·
  spine: → `FreightInvoice`, `Shipment.weight_kg/volume_cbm/package_count`, `Load.distance_km` ·
  **buildable now**.
- **Vehicle / equipment utilization** — Σ shipment weight ÷ `Load.equipment_capacity_weight_kg` and the volume
  twin, aggregated across loads and by equipment type · seen in: Blue Yonder, Oracle, TMS suites generally ·
  **table-stakes** · spine: → `Load`, `Shipment` (4.6 already shows single-load cube utilization; 4.11
  aggregates it) · **buildable now**.
- **Carrier scorecard (cost + service + audit variance in one row)** — per carrier: OTD %, avg transit days vs
  `CarrierRateCard.transit_days`, cost/kg, freight variance %, exception count · seen in: project44 (the
  canonical carrier scorecard), FourKites, Blue Yonder · **table-stakes** · spine: → `Carrier`
  (`on_time_delivery_pct` already derived in 4.6 — trend it), `CarrierRateCard`, `Shipment`, `FreightInvoice` ·
  **buildable now**.
- **Lane analytics** — group by (`origin_text`, `destination_text`) or `LoadStop`: volume, cost per unit, OTD,
  carrier mix · seen in: project44 (lane analytics), FourKites · **common** · spine: → `Shipment`, `Load`,
  `LoadStop` · **buildable now**.
- **Freight audit recovery** — Σ `FreightInvoice.variance_amount` recovered / disputed, by carrier · seen in:
  project44, Trax-class freight audit · **common** · spine: → `FreightInvoice(+Line)` (4.6) · **buildable now**.
- **Dwell time** — yard/dock dwell from `YardVisit` (4.4) and gaps between `TrackingEvent` rows · seen in:
  FourKites, project44 · **common** · spine: → `YardVisit`, `TrackingEvent` · **buildable now**.
- **Rate benchmarking against external market data (SONAR-style), predictive ETA feeds** — seen in: project44,
  FourKites · **integration/later** — needs an external market-rate feed; note the hook, ship nothing.

### Bullet 4 — Financial Reporting (gross margin, supply-chain cost breakdown)
> **Best served by a COMPUTED page with no new model.** ⚠️ **L29 guardrail to print on the page itself:**
> SCM posts **no** `JournalEntry`; `apps.accounting` owns the ledger. This page is an **operational margin
> estimate over SCM rows**, explicitly *not* the statutory P&L, and must link to the accounting reports.

- **Gross margin by item / customer / category / channel** — revenue (`SalesOrderLine.quantity_ordered ×
  unit_price × (1 − discount_pct/100)`) − COGS (the `issue` `StockMove.unit_cost` for that order, else
  `Item.average_cost`) · seen in: Oracle, Anaplan (portfolio profitability), Netstock (SKU-level
  profitability), Coupa · **table-stakes** · spine: → `SalesOrder(+Line)`, `StockMove`, `Item`,
  `ItemCategory`, `core.Party`, `SalesOrder.source_channel` · **buildable now**.
- **Cost-to-serve breakdown** — allocate onto each order/customer: freight (`FreightInvoice.billed_amount` via
  `Shipment.sales_order`), returns cost (`ReturnDisposition` write-down + `WarrantyClaimCost`), cost of quality
  (`NonConformance.cost_of_quality`), warehouse handling proxy (`PickTask(+Line)` units/lines) → margin after
  cost-to-serve, plus a customer profitability ranking · seen in: **Coupa (per product and per customer with
  fixed and variable costs allocated)**, Anaplan, Oracle · **differentiator** and the single most valuable page
  in this bullet · spine: → `FreightInvoice`, `Shipment`, `ReturnDisposition`, `WarrantyClaimCost`,
  `NonConformance`, `PickTask(+Line)`, `SalesOrder` · **buildable now**.
- **Supply-chain cost stack** — one waterfall: purchase cost, inbound freight, warehousing/handling, production
  (`ProductionTimeLog` + `WorkOrder` variances), outbound freight, quality cost, returns cost · seen in: Coupa,
  Oracle, Anaplan · **common** · spine: → the tables above + `WorkOrder`, `ProductionTimeLog` ·
  **buildable now**.
- **Purchase price variance (PPV)** — `PurchaseOrderLine.unit_price` vs `Item.standard_cost` · seen in: Oracle,
  SAP, Sievo · **common** · spine: → `PurchaseOrderLine`, `Item` · **buildable now** *(matched via `sku_hint`;
  state the caveat)*.
- **Scrap / write-off value** — negative `adjustment` StockMoves × `unit_cost`, split by 4.9 NCR disposition ·
  seen in: Oracle, SAP · **common** · spine: → `StockMove`, `NonConformance` · **buildable now**.
- **Inventory carrying cost & working capital tied up** — on-hand value × carrying rate; DIO · seen in:
  Netstock, Anaplan · **common** · spine: → `StockMove` + rate parameter on NEW `KpiTarget` · **buildable now**.
- **Carbon / emissions alongside cost** — seen in: Coupa (carbon computed with cost-to-serve), Blue Yonder ·
  **differentiator** · **PARK → 4.12** (Sustainability Tracking is an explicit 4.12 bullet; `research-scm-4.6.md`
  already routed it there). 4.6 stored `Load.distance_km` + `estimated_fuel_cost` so 4.12 can compute it.

### Bullet 5 — Predictive Analytics (disruptions, demand spikes)
> **Honest framing (mandatory):** every score below is a **deterministic, fully explainable weighted composite
> over real rows**, rendered with its component arithmetic visible — the `SupplierScorecard.signal_summary`
> precedent. No ML, no model artefacts, and the UI must not say "AI". Genuine ML/AutoML is Module 10.13.

- **Supplier disruption-risk score (0–100, explainable)** — weighted components, each shown with its own points
  and evidence: late-delivery rate (`GoodsReceiptNote` vs `PurchaseOrder.expected_date`) · quality/NCR rate
  (`GoodsReceiptLine.quantity_rejected`, `NonConformance` by `severity`) · open `CapaAction` count ·
  contract expiring within N days or **no active contract** (`SupplierContract.end_date`) · single-source
  concentration (only vendor for K `sku_hint`s; share of total spend) · acknowledgement latency
  (`PurchaseOrder.acknowledged_at`) · and **4.2's stored `SupplierRiskAssessment.risk_index` as one input** ·
  seen in: Resilinc RiskShield (configurable composite: past disruptions, recovery time, financial health, ESG,
  cyber; six risk areas; sole-source identification), Everstream (automated supplier scorecards), Blue Yonder
  (network risk), o9 · **differentiator** · spine: → all verified 4.1/4.2/4.9 tables above; **no new risk
  register** — the computed score is frozen into NEW `KpiSnapshot` for trending · **buildable now**.
- **Demand-spike detection** — trailing short-window `issue` volume vs the trailing long-window mean (a plain
  ratio/σ-band, stated on screen), and `DemandForecastPeriod` actual-vs-forecast deviation beyond a threshold ·
  seen in: o9 (demand alerts), Blue Yonder, Anaplan (anomaly surfacing), Netstock (predictive overlays) ·
  **common** · spine: → `StockMove`, `DemandForecast(+Period)`, `DemandSignal`, `SeasonalityProfile` ·
  **buildable now**. *Note `research-scm-4.10.md:290`: the demand series is deliberately GROSS — return-restock
  netting was explicitly deferred to 4.11; do it here or restate the caveat.*
- **Projected stockout / days-of-cover risk** — (derived on-hand − open allocations + open PO receipts) ÷
  avg daily demand vs `ReorderRule.lead_time_days` · seen in: Blue Yonder (projected inventory below safety
  stock in week N), o9, Netstock · **table-stakes for a control tower** · spine: → `StockMove`,
  `SalesOrderAllocation`, `PurchaseOrder(+Line)`, `ReorderRule` · **buildable now**.
- **Shipment-at-risk / stale-signal detection** — in-transit shipments whose `eta` exceeds
  `planned_delivery_date`, or with **no `TrackingEvent` for > N hours** · seen in: o9 (order-at-risk),
  FourKites (shipment risk), project44 · **common** · spine: → `Shipment`, `TrackingEvent` · **buildable now**.
- **Exception-with-material-impact ranking** — rank open exceptions by value at risk (order value, on-hand
  value, spend exposed) rather than by count · seen in: Blue Yonder ("anomalies with material impact"), o9
  ("only constrained nodes highlighted"), Kinaxis (alert tuning against alert fatigue) · **differentiator** ·
  spine: → NEW `SupplyChainAlert.impact_value` · **buildable now**.
- **Multi-tier / n-tier supplier mapping, external event feeds (weather, port congestion, geopolitical),
  ML-clustered thresholds** — seen in: Resilinc, Everstream, Blue Yonder, SAP IBP (k-means/DBSCAN alerts) ·
  **integration/later** — needs external data or ML; the data model tolerates it (alerts are already typed and
  sourced), ship nothing now.

### Beyond the bullets (strong features the bullets don't name)
- **Metric definitions with targets + warning/critical thresholds + owner** — seen in: Oracle KPI library,
  SAP IBP (threshold key + operator + value + severity + category), Kinaxis, Netstock (KPI benchmarking) ·
  **table-stakes** · spine: **NEW `KpiTarget`** · **buildable now**. *Scope guard: closed metric registry, not
  a formula builder — 10.11 owns formula authoring.*
- **Point-in-time snapshots / stated data-freshness** — seen in: Sievo (weekly/monthly refresh cycles as a
  product feature), Oracle (as-of KPI trends), CRM 1.6 `ReportSnapshot` · **common** · spine:
  **NEW `KpiSnapshot`** · **buildable now**. Every computed page also shows an "as of <timestamp>" stamp.
- **Alert → assigned case → resolution, with acknowledgement state** — seen in: SAP IBP (alerts become cases
  assigned to a responsible user + procedure playbooks), Blue Yonder (Resolution Rooms with an audit trail),
  o9 (push notifications), Netstock (exception alerts) · **table-stakes** · spine: **NEW `SupplyChainAlert`** ·
  **buildable now**.
- **Alert tuning / snooze to fight alert fatigue** — seen in: Kinaxis (explicit), SAP (subscriptions scoped by
  filter) · **differentiator** · spine: `SupplyChainAlert.status='snoozed'` + `KpiTarget.is_alerting` /
  `min_impact_value` floor · **buildable now**.
- **Period-over-period comparison + trend arrow + traffic-light band** — seen in: Oracle, Netstock, Kinaxis,
  Anaplan · **table-stakes** · spine: `KpiSnapshot` (prior period) + `KpiTarget` bands · **buildable now**.
- **CSV/Excel export of any analytics table** — seen in: every product surveyed · **table-stakes** ·
  spine: none (a view + `csv` writer, the existing report-page pattern) · **buildable now**.
- **Scenario / what-if comparison, digital twin, network optimization** — seen in: Kinaxis (scenario
  scorecards), Blue Yonder, o9, Coupa, Anaplan · **differentiator** · **defer** — a real solver/simulation
  layer is far beyond one sub-module pass; 4.7 already ships forecast scenarios.
- **Scheduled report distribution / email subscriptions / Slack-Teams bursting** — seen in: Sievo, Oracle,
  SAP, project44 (QBR packs) · **integration/later** and **PARK → 10.16** (Report Subscriptions, Distribution
  & Bursting, Notification Center are literally 10.16's bullets). 4.11 ships in-app alerts only.
- **Natural-language query / conversational BI** — seen in: FourKites (NLQ), o9, Oracle · **integration/later**
  · **PARK → 10.15**.

---

## Recommended build scope (this pass — 3 models + 5 computed pages)

### Computed pages — NO new model (this is the bulk of the sub-module)

| Page (proposed url name) | Bullet | Aggregates over (verified tables) |
|---|---|---|
| `scm:inventory_analytics` | Inventory Dashboards | `StockMove`, `Item`, `ItemCategory`, `Location`, `LotSerial`, `ReorderRule` |
| `scm:spend_analytics` | Procurement Analytics | `PurchaseOrder(+Line)`, `PurchaseRequisition`, `RFQ`/`RFQQuote`, `GoodsReceiptNote(+Line)`, `SupplierContract`, `SupplierScorecard`, `SupplierCatalogItem`, `core.Party`, `core.OrgUnit`, `accounting.GLAccount` |
| `scm:logistics_kpis` | Logistics KPIs | `Shipment`, `TrackingEvent`, `Load`, `LoadStop`, `Carrier`, `CarrierRateCard`, `FreightInvoice(+Line)`, `YardVisit` |
| `scm:margin_analytics` | Financial Reporting | `SalesOrder(+Line)`, `StockMove`, `Item`, `FreightInvoice`, `PickTask(+Line)`, `NonConformance`, `ReturnDisposition`, `WarrantyClaimCost`, `WorkOrder`, `ProductionTimeLog` |
| `scm:disruption_risk` | Predictive Analytics | all of the above + `SupplierRiskAssessment`, `SupplierContract`, `CapaAction`, `DemandForecast(+Period)`, `DemandSignal`, `SalesOrderAllocation` |

All five live in `apps/scm/views/SupplyChainAnalytics/Reports.py` + `apps/scm/urls/SupplyChainAnalytics/Reports.py`,
with the metric compute functions in a single **`apps/scm/analytics.py`** (flat at app root — the
`admin.py`/`services.py` rule) holding a closed `SCM_METRICS` registry keyed by the same strings as
`KpiTarget.metric`'s `CHOICES`, mirroring `apps/crm/analytics.py:263 WIDGET_METRICS`.

### Model 1 — `KpiTarget` [`KPI-`] · `models/SupplyChainAnalytics/KpiTargets.py`
**Why STORED (not derivable):** a target, a warning band and a critical band are **human intent**. No row in
4.1–4.10 says "our turnover target is 6 turns" or "alert me when dead stock exceeds 50 000". Every leader
stores this: Oracle's KPI library targets, SAP IBP's alert definition (threshold key + operator + value +
severity + category + calculation level), Kinaxis's tunable exceptions, Netstock's KPI benchmarks.
- Fields justified by the research: `metric` (**CHOICES over the closed `SCM_METRICS` registry** — *not* a
  formula field; 10.11 owns formula authoring) · `name` · `scope` + `scope_ref` (all / item-category /
  location / carrier / vendor — SAP's "calculation level") · `period_grain` (day/week/month/quarter) ·
  `date_range` (the CRM `ANALYTICS_RANGE_CHOICES` shape) · `direction` (higher_is_better / lower_is_better) ·
  `target_value` · `warning_threshold` · `critical_threshold` · `parameter_days` and `parameter_pct`
  (the dead-stock N days, expiry N days, carrying-cost rate, spike σ — every metric that needs a knob) ·
  `is_alerting` (bool) · `min_impact_value` (alert-fatigue floor — Kinaxis) · `severity` ·
  `owner`(`settings.AUTH_USER_MODEL`) · `is_pinned` + `display_order` (control-tower tile order — the
  personalization 4.11 gets **instead of** a widget canvas) · `is_active` · `last_evaluated_at`
  (`editable=False`, system-stamped — the `AnalyticsReport.last_run_at` precedent).
- FKs (all verified): `core.Tenant` (via `TenantNumbered`), `settings.AUTH_USER_MODEL`; nullable scope FKs to
  `scm.ItemCategory` / `scm.Location` / `scm.Carrier` / `core.Party`.
- `clean()`: warning must sit between target and critical **in the direction the metric runs**; a metric
  requiring a parameter must have one.

### Model 2 — `KpiSnapshot` · `models/SupplyChainAnalytics/KpiSnapshots.py`
**Why STORED (not derivable):** three independent reasons. (1) **History drifts** — `Item.average_cost` is
recomputed and back-dated `StockMove`/GRN rows are legal, so re-deriving last quarter's turnover *silently
rewrites the past*; a trend is only trustworthy if the value is frozen as it stood. (2) **Cost** — a 12-period
trend line otherwise means 12 full ledger walks per page load. (3) Every leader ships it: Sievo sells the
weekly/monthly refresh cycle as a feature; Oracle trends KPI cards; CRM 1.6's `ReportSnapshot` is the in-repo
precedent.
- Fields: `kpi_target` (FK, CASCADE) · `metric` (denormalized so a deleted target doesn't orphan the meaning) ·
  `period_start` / `period_end` · `dimension_key` + `dimension_label` (e.g. vendor id / carrier id / `""` for
  the roll-up — SAP's calculation level) · `value` · `target_value_at_time` · `status_band`
  (ok/warning/critical) · `breakdown` (`JSONField` — the component arithmetic, i.e. the
  `SupplierScorecard.signal_summary` idea in structured form; this is what makes the risk score *explainable*) ·
  `computed_at` · `computed_by` (nullable user).
- **Append-only, system-written by a POST action / management command — never a user form** (the
  `ReportSnapshot` rule). `unique_together (tenant, kpi_target, period_start, dimension_key)` so a re-run is
  idempotent rather than duplicating.
- Not `TenantNumbered` — it is a child fact row, so it carries its own `tenant` FK, exactly like
  `DashboardWidget` / `ReportSnapshot`.

### Model 3 — `SupplyChainAlert` [`ALR-`] · `models/SupplyChainAnalytics/SupplyChainAlerts.py`
**Why STORED (not derivable):** acknowledgement, assignment, snooze and resolution notes are **human state
that no aggregate can reproduce**. A purely computed exception list forgets that someone already looked at it —
which is exactly the alert-fatigue failure Kinaxis calls out. SAP IBP turns alerts into cases assigned to a
responsible user; Blue Yonder wraps them in Resolution Rooms with an audit trail; o9 pushes them to a person.
- Fields: `kpi_target` (nullable FK — rule-based exceptions like "shipment stale > N h" need no target) ·
  `metric` · `title` · `severity` (info/warning/critical) · `observed_value` / `threshold_value` ·
  `impact_value` (**value at risk** — Blue Yonder's "material impact"; drives the default ranking) ·
  `dimension_key` / `dimension_label` · nullable subject FKs to the row that caused it — `scm.Item`,
  `core.Party`, `scm.Carrier`, `scm.Shipment`, `scm.PurchaseOrder`, `scm.Location` (each `SET_NULL`) ·
  `detail` (`JSONField`, the evidence) · `status` (open / acknowledged / snoozed / resolved / dismissed) ·
  `assigned_to` · `acknowledged_by` / `acknowledged_at` · `snoozed_until` · `resolved_by` / `resolved_at` /
  `resolution_note` · `raised_at`.
- `unique_together (tenant, kpi_target, dimension_key, status)` **is wrong** — instead add a
  `dedupe_key` + partial-open guard so the same breach re-firing hourly updates the open row rather than
  creating a thousand duplicates (the alert-fatigue lesson, stated explicitly).
- Indexes: `(tenant, status)`, `(tenant, severity)`, `(tenant, raised_at)`, `(tenant, assigned_to)`.

### Sidebar wiring proposed for `LIVE_LINKS["4.11"]`
```
"Inventory Dashboards": "scm:inventory_analytics"   # computed page (valuation_report precedent)
"Procurement Analytics": "scm:spend_analytics"      # computed spend cube + savings/opportunity tables
"Logistics KPIs":        "scm:logistics_kpis"       # computed carrier/lane/utilization scorecards
"Financial Reporting":   "scm:margin_analytics"     # computed margin + cost-to-serve (NOT the ledger)
"Predictive Analytics":  "scm:disruption_risk"      # computed explainable risk + spike detection
```
`KpiTarget` CRUD is a **master with no sidebar key**, reached from the analytics pages (the
`InspectionPlan` / `WorkCenter` / `ReorderRule` / `ReturnReason` precedent). The **alert inbox**
(`scm:supplychainalert_list`) is reached from a persistent open-count chip in every analytics page header —
it is the daily-driver page, so the todo agent may prefer it for the Predictive slot; flagging the choice
rather than deciding it.

---

## Belongs to sibling sub-modules (parked, not scoped here)
- **Carbon footprint / emissions reporting alongside cost** (Coupa, Blue Yonder) → **4.12** Contract &
  Compliance Management, "Sustainability Tracking" bullet. `research-scm-4.6.md:255` already routed it there;
  4.6 stored `Load.distance_km` + `estimated_fuel_cost` for it.
- **Asset/fleet uptime, MTBF, maintenance-cost analytics** → **4.13** Asset Management.
- **Labor productivity (units per hour, picker accuracy) dashboards** → **4.14** Labor Management
  ("Performance Tracking" bullet), even though `PickTask`/`ProductionTimeLog` rows already exist.
- **Cold-chain temperature-excursion analytics** → **4.15**.
- **3PL billing / customer-facing analytics portal** → **4.16** / **4.17**.
- **Drag-and-drop custom report builder, PowerBI/Excel BI-tool integration** → **6.14** Spend Analytics &
  Reporting bullets, and **10.10**. 4.11 ships fixed pages + plain CSV export.
- **Savings-initiative pipeline (identified → approved → in sourcing → realized → validated)** — a genuinely
  storable workflow (Sievo initiative management, Ivalua savings management, GEP insights) → **6.5 Sourcing
  Analytics ("savings achieved") / 6.14**. 4.11's bullet says *"cost-saving opportunit**ies**"* = the
  **identification** page (negotiation savings, price-variance consolidation value, off-contract spend, tail
  spend), which is computed here. The lifecycle tracker is Module 6's.
- **Supplier 360 feedback, PIPs, external industry benchmarks** → **6.16** Supplier Performance & Evaluation.
- **Restricted-party screening, fraud-pattern detection** → **6.17**.
- **Generic dashboard builder, formula-authored KPI library, OLAP cubes, ML/AutoML, NLQ, scheduled
  distribution/bursting/notification center** → **Module 10 (`bi`)**: 10.8, 10.10, 10.11, 10.12, 10.13, 10.15,
  10.16 respectively. This is the single most important boundary in this file.
- **Statutory P&L, budget-variance reporting, journal-backed COGS** → **`apps.accounting`** (L29). The margin
  page is an operational estimate and must say so and link out.

## Deferred (later passes / integrations)
- **Scenario / what-if simulation and network optimization** (Kinaxis, Blue Yonder, o9, Coupa, Anaplan) —
  needs a solver; 4.7 already covers forecast scenarios. Deferred.
- **External data**: market rate benchmarks (project44/SONAR), community spend benchmarks (Coupa/Sievo),
  category price indices (Sievo/GEP), weather/geopolitical/port-congestion event feeds (Everstream, Resilinc),
  third-party credit scores. All **integration/later** — they inform `SupplyChainAlert.detail` and
  `KpiSnapshot.breakdown` shape but ship nothing now.
- **ML-derived thresholds (SAP's k-means/DBSCAN alerting), AutoML, propensity models** — deferred to 10.13.
  4.11's thresholds are explicit numbers a human sets, and its "predictions" are stated arithmetic.
- **Spend auto-classification into a category taxonomy + supplier normalization/dedup** (Sievo, Coupa, GEP) —
  needs a classifier and a taxonomy master. **Also blocked upstream**: 4.1 PO lines carry `sku_hint` free text,
  not an `Item` FK. Note the future migration; use GL account as the category axis for now.
- **Contract-line-level compliance / leakage** — needs a `SupplierContract`↔item/price linkage that 4.2 did not
  build. Off-contract spend is vendor-level this pass.
- **Multi-currency normalization** — `PurchaseOrder`/`SalesOrder`/`FreightInvoice` each carry a nullable
  `accounting.Currency` but there is **no FX-rate table verified in this repo**; aggregate in the tenant's
  presentation currency and **display a mixed-currency warning** rather than inventing a rate. Revisit when
  accounting exposes rates.
- **Return-restock netting of the demand series** — `research-scm-4.10.md:290` deferred this to 4.11
  explicitly. Ship the netted view on `scm:disruption_risk`/`inventory_analytics` **or** restate the
  gross-series caveat on-screen; do not silently leave it ambiguous.
- **Resolution Rooms / threaded collaboration on an alert** (Blue Yonder) — `SupplyChainAlert.resolution_note`
  + `core.Activity` cover the audit trail this pass; a comment thread is a later pass.
- **Snapshot scheduling** — snapshots are POST-triggered + a management command this pass; cron/Celery
  scheduling is integration/later (and 10.16 territory).

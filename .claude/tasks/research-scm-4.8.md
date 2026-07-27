# Research — Sub-module 4.8: Manufacturing / Production (Module 4 — Supply Chain Management, `scm`)

The five NavERP.md bullets this pass is scoped against (`NavERP.md` lines 782–787, read verbatim):

- **Bill of Materials (BOM)** — Definition of raw materials, sub-assemblies, and quantities required.
- **Production Scheduling** — Planning of production runs based on capacity and material availability.
- **Work Order Management** — Issuance and tracking of work orders on the shop floor.
- **Material Resource Planning (MRP)** — Calculation of material requirements based on production plans.
- **Shop Floor Control** — Tracking of machine time, labor time, and production progress.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4

`apps/core/navigation.py` currently carries `"4.1"`, `"4.2"`, `"4.3"`, `"4.4"`, `"4.5"`, `"4.6"`, `"4.7"`.
**4.8 is the next unbuilt sub-module** (no `LIVE_LINKS["4.8"]` key). 4.9–4.19 are also unbuilt and are OUT
of scope for this pass.

### Sibling models verified to exist (grep `^class ` over `apps/scm/models/`)

| Verified class | File | What 4.8 gets from it |
|---|---|---|
| `Item`, `ItemCategory`, `UOM` | `models/InventoryManagement/Items.py` | the produced good and every component; `Item.on_hand(location=…)`, `Item.total_value()`, `Item.apply_receipt()`, `average_cost`, `standard_cost`, `costing_method`, `tracking` |
| `Location` | `models/InventoryManagement/Locations.py` | WIP / component-source / finished-goods locations; already has `location_type` incl. `staging` and `transit`, `capacity`, `is_pickable` |
| `StockMove` | `models/InventoryManagement/StockMoves.py` | **the only** stock ledger — append-only, signed `quantity`, `move_type ∈ receipt/issue/transfer/adjustment`, `reference`, `unit_cost` |
| `LotSerial` | `models/InventoryManagement/LotSerials.py` | lot/serial on component issue and finished-goods receipt |
| `ReorderRule` | `models/InventoryManagement/ReorderRules.py` | per `(item, location)` `lead_time_days`, `safety_stock`, `reorder_point`, `reorder_quantity` — **MRP reads these instead of inventing planning parameters** |
| `SalesOrder`, `SalesOrderLine` | `models/OrderManagement/SalesOrders.py` | independent demand. `SalesOrderLine.item` **is a real FK**; `SalesOrder.requested_date` exists; the exclusion precedent is `.exclude(sales_order__status__in=("draft","cancelled"))` (already used by `ReorderRule.assign_abc_classes`) |
| `DemandForecast`, `DemandForecastPeriod` | `models/DemandPlanning/DemandForecasts.py` | forecast demand. `DemandForecast.item` is a real FK; periods carry `period_start`/`period_end`/`final_quantity` (`editable=False`) |
| `PurchaseRequisition`, `PurchaseRequisitionLine` | `models/ProcurementManagement/PurchaseRequisitions.py` | the **buy** side of an MRP suggestion — the same hand-off `scm:reorder_alerts` already uses |
| `PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceiptNote`, `GoodsReceiptLine` | `models/ProcurementManagement/` | open-PO supply (**caveat below**) |
| `SupplierProfile`, `SupplierContract`, `Carrier`, … | `models/SupplierRelationshipManagement/`, `TransportationManagement/` | not needed this pass |

Core spine verified (`grep ^class apps/core/models/`): `Tenant`, `Party`, `PartyRole`, `Address`,
`ContactMethod`, `OrgUnit`, `Employment`, `Activity`, `Document`, `AuditLog` — **all present**.
`apps/scm/models/_base.py` provides `TenantOwned`, `TenantNumbered` (with `NUMBER_PREFIX` +
`next_number()` retry), and the clamped quantizers `q2()` / `q4()`.

### Constraints that shape every recommendation below

1. **`Item` has NO `is_manufactured` / raw-vs-finished flag, and this pass must NOT add one.**
   "Is this item made or bought" is **derived**: an item is *made* iff an **active** `BillOfMaterials`
   exists for it in this tenant. One `EXISTS` subquery, no second source of truth, no data migration when
   an item's sourcing changes. (Same doctrine as `Item.on_hand` being a `Sum(quantity)` aggregate and
   `average_cost` being a cache, never a typed field.)
2. **All stock movement goes through `_post_stock_move()`** (`apps/scm/views/_helpers.py:95`). Component
   issue = a negative `StockMove` with `move_type="issue"`; finished-goods receipt = a positive
   `StockMove` with `move_type="receipt"` (which rolls `Item.apply_receipt()` first); scrap = an
   `adjustment` move. `reference` carries the work-order number, exactly like `TRF-`/`ADJ-`/`GRN-` do
   today. **No new stock table, no stored WIP quantity.**
3. **Every posting action is `@tenant_admin_required @require_POST`, inside `transaction.atomic()`, with
   `select_for_update()` + a status re-read** before mutating — the `goodsreceipt_receive` /
   `stocktransfer_complete` / `stockadjustment_post` pattern. Release / issue / report-production /
   close on a work order are all posting actions and inherit that shape verbatim.
   `_insufficient_stock()` already exists for the shortfall guard on outbound lines.
4. **SCM never posts a `JournalEntry` (L29).** See the dedicated GL section below.
5. **Compute-then-convert, never auto-execute.** `scm:reorder_alerts` produces *suggestions* a human turns
   into a `PurchaseRequisition`; 4.7's `safety_stock_report` computes into `computed_*` columns that a
   separate reviewed **apply** promotes. MRP in 4.8 obeys the same contract: it renders a plan; a person
   presses a button per row to create a `WorkOrder` (make) or a `PurchaseRequisition` (buy).
6. **Open-PO supply is only SKU-string matchable.** `PurchaseOrderLine` has **no `item` FK** — it carries
   free text `item_description` + `sku_hint` (4.1 shipped before the item master). The existing bridge is
   `_resolve_grn_item(tenant, po_line)` in `apps/scm/views/_helpers.py:241`
   (`Item.objects.filter(tenant=…, sku__iexact=sku).first()`), and `_post_grn_receipt` already surfaces
   the lines it could not match. MRP must reuse that same best-effort bridge and label open-PO supply
   **advisory**, never assert it as a hard number. (This is exactly why the netting page must be a
   *report a planner reads*, not an engine that fires orders.)

### Auto-number prefixes

Taken across `apps/scm`: `PR`, `RFQ`, `QT`, `PO`, **`GRN`**, `SCR`, `SRA`, `SC`, `CAT`, `TRF`, `ADJ`,
`PUT`, `PIK`, `CC`, `YRD`, `SO`, `CAR`, `LD`, `SHP`, `FRT`, `DF`, `DS`, `FA`, `SEA`.
**Free and proposed for 4.8:** `BOM`, `WC`, `WO`, `PRD`.

### Sibling research files consulted

- `.claude/tasks/research-scm.md` §"4.8 Manufacturing / Production (deferred)" — the module-wide survey
  parked BOM/scheduling/work orders/MRP/shop-floor time here and named no models. Its line
  "reuses core `WorkOrder`" is **stale** — no `WorkOrder` class exists anywhere in the repo (verified by
  grep); 4.8 declares it.
- `.claude/tasks/research-scm-4.7.md` line 510 explicitly deferred to 4.8: *"Supply-side planning: capacity
  checks, constrained supply plan, MRP netting, distribution requirements planning… 4.7 is demand-side
  only."* **That deferral is this pass's starting backlog** and is honoured below.
- `.claude/tasks/research-scm-4.3.md` established the derived-on-hand and lot/batch doctrine 4.8 inherits.

---

## Leaders surveyed (with source links)

1. **Odoo Manufacturing (MRP)** — open-source discrete manufacturing: multi-level BoMs, manufacturing
   orders, work orders on work centers, tablet-based Shop Floor with timers and OEE —
   [Manufacturing features](https://www.odoo.com/app/manufacturing-features) ·
   [Manufacturing docs](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing.html) ·
   [Work centers](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing/advanced_configuration/using_work_centers.html)
2. **Microsoft Dynamics 365 Supply Chain Management — Production control** — the most explicitly documented
   production-order lifecycle (created → estimated → scheduled → released → started → reported as finished
   → ended), operations vs job scheduling, picking-list / route-card / job-card journals, preflush vs
   backflush —
   [Production process overview](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/production-process-overview)
3. **Oracle NetSuite Manufacturing (Work Orders + WIP & Routings)** — assembly items, manufacturing
   routings as templates over work centers, operation tasks, WIP account movement, infinite-capacity
   scheduling with a drag-and-drop Gantt —
   [Manufacturing Routing (NetSuite help)](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N2341076.html) ·
   [Routing and work orders](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2346224.html)
4. **SAP S/4HANA Production Planning (PP)** — material master + BOM + work center + routing master data,
   production versions (BOM × routing validity), MRP procurement proposals, capacity requirements planning —
   [Introduction to SAP PP](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/introduction-to-sap-pp-production-planning-in-sap-cloud-public-edition/ba-p/13573624) ·
   [PP/DS functionality overview](https://community.sap.com/t5/supply-chain-management-blog-posts-by-sap/overview-of-the-key-functionality-production-planning-and-detailed/ba-p/13409001)
5. **Acumatica Manufacturing Edition** — BOM/routing with engineering change control, production orders,
   MRP, APS with capable-to-promise, estimating, configurator, mobile data collection + shop-floor kiosk —
   [Manufacturing management](https://www.acumatica.com/cloud-erp-software/manufacturing-management/)
6. **Epicor Kinetic — Production Management** — Job Management as the costed production object, Data
   Collection/MES for plant-floor labor + machine transactions, Advanced Production (batching), lean/kanban,
   scheduling on job quantity + setup time + production time + resource capacity —
   [Kinetic Production Management](https://www.epicor.com/en-us/products/enterprise-resource-planning-erp/kinetic/production-management/) ·
   [Production Management overview (Top10ERP)](https://www.top10erp.org/products/epicor-kinetic/production-management)
7. **Infor CloudSuite Industrial (SyteLine)** — job-centric model binding material allocations, labor
   routings, operation sequences and quality holds into one auditable record; APS with finite *and*
   infinite scheduling, constraint-based sequencing, what-if —
   [SyteLine/CSI overview](https://www.erpresearch.com/en-us/infor-syteline-csi-erp-overview) ·
   [Production planning & scheduling](https://www.frontstep.bg/solutions/infor-cloudsuite-industrial-syteline-erp/production-planning-scheduling/)
8. **Katana (Cloud Inventory / MRP)** — SMB-first: BOMs with sub-assemblies, make-to-order vs make-to-stock,
   priority-based production planning, Shop Floor App, live material-consumption tracking, contract
   manufacturing — [Katana features](https://www.katanamrp.com/features/)
9. **MRPeasy** — SMB manufacturing ERP: BOM + routing + workstation + worker management, MPS, interactive
   production calendar/Gantt with drag-and-drop rescheduling, forward *and* backward scheduling,
   "My Production Plan" operator terminal, one-click PO for missing materials —
   [Production scheduling](https://www.mrpeasy.com/production-scheduling-software/) ·
   [Manufacturing ERP systems](https://www.mrpeasy.com/blog/manufacturing-erp-systems/)
10. **Fishbowl Manufacturing** — Manufacture Order → Work Orders generated from a staged BOM (a BOM stage
    that is itself a BOM becomes its own work order); Standard / Reverse / Disassemble / Repair / Custom
    work-order types; labor & job tracking —
    [Manufacture & work orders](https://www.fishbowlinventory.com/manufacturing/manufacture-and-work-orders) ·
    [Bill of Materials (help)](https://help.fishbowlinventory.com/hc/en-us/articles/360042632234-Bill_of_Materials)

*Reference (not a product) for MRP arithmetic vocabulary — explode / net / lot-size / time-phase / peg:*
[Oracle JD Edwards — Planning Material Requirements](https://docs.oracle.com/cd/E16582_01/doc.91/e15139/plng_material_reqs.htm)

---

## Feature catalog (this sub-module only)

Priority key: **table-stakes** = nearly every leader has it · **common** = most have it ·
**differentiator** = a few standouts.

### Bullet 1 — Bill of Materials (BOM)

- **Header + component lines (item, quantity per, UOM)** — the recipe: what the parent item is, in what
  output quantity, from which components at what per-unit quantity. · seen in: Odoo, D365, NetSuite, SAP,
  Acumatica, Epicor, Katana, MRPeasy, Fishbowl · priority: **table-stakes** ·
  spine: **new table `BillOfMaterials` + `BOMLine`**, both FK `scm.Item` (verified) and `scm.UOM` (verified)
  · **buildable now**
- **Output/batch quantity on the header** — the BOM yields *N* units, so component quantities scale
  (`required = line.quantity_per × order_qty / bom.output_quantity`). · seen in: Odoo, D365 (formula-type
  BOMs), SAP (base quantity), MRPeasy · priority: **table-stakes** · spine: field on the new header ·
  **buildable now**
- **Multi-level BOMs / sub-assemblies** — a component that itself has a BOM is a sub-assembly; explosion
  recurses. Fishbowl models this as "stages": a BOM containing a BOM produces a separate work order per
  stage. · seen in: Odoo ("multi-level Bills of Materials"), Fishbowl (stages), Katana, NetSuite, SAP,
  Acumatica · priority: **table-stakes** ·
  spine: **derived, no extra table** — recursion over `BOMLine.component → active BillOfMaterials`, with a
  visited-set cycle guard (the `Location.path()` precedent already guards a self-parent cycle) ·
  **buildable now**
- **Make-vs-buy classification without a flag on the item** — a component with an active BOM is planned as
  a work order; one without is planned as a purchase. · seen in: every leader (implicitly, via
  planning/sourcing rules; SAP calls it procurement type, Odoo a manufacture route) ·
  priority: **table-stakes** ·
  spine: **derived from `BillOfMaterials` existence — explicitly NOT a new `Item.is_manufactured` field** ·
  **buildable now**
- **Versioning / revision + effectivity dates + active/obsolete status** — BOMs change; the plan must name
  which revision it used and when it is valid from/to. · seen in: Odoo ("version changes"), SAP (production
  versions binding a BOM to a routing for a validity/lot-size range), Acumatica (BOM revisions), Epicor,
  NetSuite · priority: **common** ·
  spine: `version`, `status ∈ draft/active/obsolete`, `effective_from`/`effective_to` on the new header;
  a partial unique guard so one item has at most one **active default** BOM · **buildable now**
- **Component scrap / yield percentage** — plan 3 % more of a lossy component than the arithmetic says. ·
  seen in: SAP (component scrap), D365, Acumatica, Epicor, NetSuite · priority: **common** ·
  spine: `scrap_pct` on `BOMLine` · **buildable now**
- **Kit / phantom BOMs** — a "kit" is delivered as loose components rather than built; a phantom is blown
  straight through to its parent's requirement. · seen in: Odoo (Kit type), NetSuite (kit items), SAP
  (phantom assembly) · priority: **common** ·
  spine: `bom_type ∈ manufacture/kit/phantom` on the header (a choice, not a table) · **buildable now**
- **Manufacturing lead time on the BOM** — how many days a build takes; MRP offsets the planned start by
  it. · seen in: SAP (in-house production time), NetSuite, MRPeasy, Acumatica, D365 ·
  priority: **common** · spine: `lead_time_days` on the new header
  (note: `ReorderRule.lead_time_days` is the *purchasing* lead time and is verified to exist — this is its
  make-side sibling, not a duplicate) · **buildable now**
- **Estimated / rolled-up standard cost from the BOM** — sum of component `standard_cost × quantity_per`
  plus work-center rates → the expected unit cost of the parent. · seen in: NetSuite (cost templates),
  Acumatica (estimating), Epicor, MRPeasy, Odoo (cost analysis) · priority: **common** ·
  spine: **derived method** on the new header over verified `Item.standard_cost` / `Item.average_cost` —
  no stored roll-up column to go stale · **buildable now**
- **Operations tab on the BOM (routing template)** — Odoo/SAP/NetSuite put the operation sequence *on* the
  BOM so work orders are generated per operation. · seen in: Odoo, SAP (routing + production version),
  NetSuite (routing as a template), Acumatica, Epicor, MRPeasy · priority: **table-stakes in the enterprise
  tier** · spine: **DEFERRED** — see Deferred §"Routings". This pass carries a single `work_center` FK plus
  a free-text operation label on the time log (documented stand-in, the 4.1 free-text-line precedent).
- **Engineering change orders (ECO) with approval workflow** — a governed change request against a BOM. ·
  seen in: Acumatica ("engineering change control… configurable approval workflows"), Epicor, SAP, Odoo
  (PLM app) · priority: **differentiator** · spine: **DEFERRED** — `status` + `version` +
  `effective_from/to` give lite revision control this pass; a separate `EngineeringChangeOrder` entity is a
  later pass.
- **Product-variant BOMs / configurator** — one BOM serving many SKU variants, or a rules-based
  configurator. · seen in: Odoo (variant BoMs), Acumatica (product configurator), Infor CSI (product
  configuration), Epicor · priority: **differentiator** · spine: **DEFERRED** — `scm.Item` has no variant
  axis; forcing one here would be a Module 5 decision made in the wrong sub-module.

### Bullet 2 — Production Scheduling

- **Work-center / workstation master with capacity in hours per day** — the resource a run is planned
  against. · seen in: Odoo ("work centers… track costs, make schedules, plan capacity"), NetSuite (work
  centers), SAP (work center = machine or group of machines), MRPeasy (workstations & workstation groups),
  Epicor (resource groups), Infor CSI (unlimited work centres), Acumatica · priority: **table-stakes** ·
  spine: **new table `WorkCenter`**, FK `scm.Location` (verified) for where its WIP sits and
  `core.OrgUnit` (verified) for the owning department · **buildable now**
- **Machine rate and labor rate per hour on the work center** — what an hour of that resource costs; feeds
  the produced item's cost. · seen in: NetSuite (cost template: labor + machine resources), SAP (routing
  specifies machine time and labor time), Epicor, MRPeasy, Odoo · priority: **table-stakes** ·
  spine: `machine_cost_per_hour`, `labor_cost_per_hour` on `WorkCenter` · **buildable now**
- **Efficiency / OEE factor and setup time** — planned duration is inflated by efficiency and preceded by a
  setup allowance. · seen in: Odoo (MRP scheduler "based on their OEE and capacity"), SAP, Epicor
  (setup time + production time in the scheduling computation), MRPeasy · priority: **common** ·
  spine: `efficiency_pct`, `setup_minutes` on `WorkCenter` · **buildable now**
- **Planned start / planned end on the production run** — the schedule itself. · seen in: all ten ·
  priority: **table-stakes** · spine: `planned_start`, `planned_end` on `WorkOrder` · **buildable now**
- **Backward scheduling from a due date, forward scheduling from availability** — MRPeasy names both
  explicitly; D365 splits operations scheduling (rough, long-term) from job scheduling (detailed). · seen
  in: MRPeasy, D365, SAP, Infor CSI, Acumatica APS · priority: **common** ·
  spine: **derived** — compute `planned_start = due_date − (bom.lead_time_days)` (backward) or
  `planned_end = planned_start + lead_time` (forward) as a helper on the work-order form; a
  `schedule_direction` choice records which was used · **buildable now (arithmetic only)**
- **Capacity load / utilization board per work center per day** — planned hours vs available hours, so the
  planner sees the bottleneck. · seen in: Odoo (workcenter capacity), MRPeasy (Gantt "operations view
  across all workstations"), NetSuite (infinite-capacity scheduling + Gantt), SAP (capacity requirements
  planning), Infor CSI, Epicor · priority: **table-stakes** ·
  spine: **computed report page** over `WorkCenter` × `WorkOrder.planned_start/planned_end` — the
  `scm:safety_stock_report` / `scm:valuation_report` precedent (a bullet may be a report) ·
  **buildable now, infinite-capacity (load vs capacity shown, overload flagged, nothing auto-levelled)**
- **Material availability check before release** — can this run actually start? Compare each component's
  requirement against live on-hand at the source location. · seen in: D365 ("the material availability
  check helps the shop floor supervisor assess availability"), MRPeasy, Katana ("insights for real-time
  planning"), Odoo, Acumatica · priority: **table-stakes** ·
  spine: **derived** — `Item.on_hand(location=…)` (verified) per component, plus the existing
  `_insufficient_stock()` guard reused on the release action · **buildable now**
- **Priority / sequence within a work center** — which job runs first when two compete. · seen in: Katana
  (priority-based planning), MRPeasy (per-worker plans), Infor CSI (constraint-based sequencing), Epicor ·
  priority: **common** · spine: `priority` choice + an integer `sequence` on `WorkOrder` · **buildable now**
- **Drag-and-drop Gantt / interactive production calendar** — reschedule by dragging. · seen in: MRPeasy,
  NetSuite (WIP & Routings Gantt), Infor CSI, Epicor Advanced MES, Acumatica APS ·
  priority: **common** · spine: presentation over the same fields — **later** (a read-only date-bucketed
  load board ships now; drag-and-drop is a JS concern, not a data-model one)
- **Finite-capacity scheduling / constraint-based sequencing / capable-to-promise** — the scheduler refuses
  to overbook a resource and re-plans around outages. · seen in: Infor CSI APS (finite *and* infinite),
  Acumatica APS (capable-to-promise), D365 (job scheduling with finite capacity), SAP PP/DS, Epicor ·
  priority: **differentiator** · spine: **DEFERRED** — a real finite scheduler is its own engine; this pass
  ships infinite-capacity load *visibility* with overload flagged.
- **Master Production Schedule (MPS) as a first-class object** — the agreed build plan above MRP. · seen
  in: MRPeasy, SAP, D365 (master planning) · priority: **common** · spine: **DEFERRED** — 4.7's approved
  `DemandForecast` + this pass's MRP report cover the planner's need without a third planning document.

### Bullet 3 — Work Order Management

- **The work order as the costed production object** — number, item to produce, quantity, dates, status. ·
  seen in: all ten (D365 "production order", Epicor "job", Infor CSI "job", Odoo "manufacturing order",
  Fishbowl "manufacture order → work orders") · priority: **table-stakes** ·
  spine: **new table `WorkOrder`** [`WO-`], FK `scm.Item`, `scm.BillOfMaterials`, `scm.Location`,
  `scm.WorkCenter` · **buildable now**
- **An explicit status lifecycle with gated actions** — D365 documents it most precisely: *created →
  estimated → scheduled → released → started → reported as finished → ended*; Odoo uses draft → confirmed →
  in progress → to close → done. Each transition is what makes stock and cost move. ·
  seen in: D365, Odoo, NetSuite, SAP, Fishbowl, Epicor · priority: **table-stakes** ·
  spine: `status` choices on `WorkOrder` + POST-only transition views under
  `@tenant_admin_required` + `select_for_update()` + status re-read (the `goodsreceipt_receive` pattern) ·
  **buildable now**
- **Component lines snapshotted from the BOM at creation** — the work order keeps *its own* required
  quantities, so editing the BOM later cannot silently rewrite history. · seen in: D365 (production BOM
  lines), NetSuite, SAP (order BOM), Odoo (components tab), Epicor (job materials) ·
  priority: **table-stakes** · spine: **child `WorkOrderComponent`** written by exploding the BOM at
  creation; `bom` FK is `SET_NULL`/`PROTECT` but the numbers live on the lines · **buildable now**
- **Issue components to the order (the picking list)** — a negative stock movement per component, at the
  source location, referencing the WO number. · seen in: D365 (picking-list journal), NetSuite (issue
  components), Odoo, Fishbowl, Katana ("monitor material consumption as work progresses") ·
  priority: **table-stakes** · spine: `_post_stock_move(..., move_type="issue", reference=wo.number)`
  (verified helper) writing to the verified `StockMove`; `quantity_issued` on the component line is
  maintained by the posting action alone (`editable=False`) · **buildable now**
- **Backflush vs manual issue per component** — backflushed components are consumed automatically at
  completion instead of picked up front. · seen in: D365 (preflush / forward flush / back-flush,
  documented explicitly), NetSuite, SAP, Odoo, Epicor (lean) · priority: **common** ·
  spine: `issue_method ∈ manual/backflush` on `WorkOrderComponent`; backflushed lines are posted by the
  report-production action, manual lines by the issue action · **buildable now**
- **Report production / receive finished goods** — a positive stock movement of the produced item into the
  finished-goods location, at the computed production cost. · seen in: D365 ("reported as finished"),
  Odoo ("mark as done"), NetSuite (assembly completion), Fishbowl (fulfil), Katana, MRPeasy ·
  priority: **table-stakes** · spine: `_post_stock_move(..., move_type="receipt", unit_cost=<computed>)`,
  which rolls the verified `Item.apply_receipt()` weighted average forward · **buildable now**
- **Partial completion / over- and under-production with a remaining quantity** — report 60 of 100 today,
  the rest tomorrow; D365 leaves "End job" unchecked to allow more, Odoo creates a backorder. ·
  seen in: D365, Odoo (backorders), NetSuite, MRPeasy · priority: **common** ·
  spine: `quantity_produced` accumulated by the posting action (`editable=False`), status stays
  `in_progress` until closed · **buildable now**
- **Scrap / rejected quantity on the run** — produced ≠ good; the difference must be visible and must not
  quietly inflate stock. · seen in: D365, Odoo, NetSuite, Epicor (scrap tracking), MRPeasy ·
  priority: **table-stakes** · spine: `quantity_scrapped` accumulated from the shop-floor entries;
  scrapped output is simply never received into stock (no phantom `adjustment` move for goods that never
  existed), while **scrapped *components*** post an `adjustment` move · **buildable now**
- **Lot / serial on both consumption and output** — trace which lot of component went into which lot of
  finished good. · seen in: Odoo (barcode scanning for lots/serials), D365 (batch attributes), NetSuite,
  Katana, MRPeasy, Fishbowl · priority: **table-stakes for regulated makers, common overall** ·
  spine: **reuses verified `scm.LotSerial`** — `lot_serial` FK on the component line and on the output;
  `_post_stock_move()` already accepts `lot_serial` and `_insufficient_stock()` already scopes the
  shortfall check per lot *and* location · **buildable now**
- **Make-to-order link back to the sales order** — the run exists because a customer ordered it. ·
  seen in: D365 (make-to-order principle, pegged supply), Katana (MTO vs MTS), NetSuite (special-order work
  orders), MRPeasy ("convert confirmed customer orders into manufacturing orders"), Odoo ·
  priority: **common** · spine: nullable `sales_order` FK to the **verified** `scm.SalesOrder`, plus an
  `order_policy ∈ make_to_stock/make_to_order` choice · **buildable now**
- **Work-order types beyond "build"** — reverse / disassemble / repair / custom (Fishbowl), unbuild and
  repair orders (Odoo). · seen in: Fishbowl, Odoo · priority: **differentiator** ·
  spine: **DEFERRED** — a `wo_type` choice is cheap, but disassembly inverts the whole issue/receive
  posting direction and deserves its own pass.
- **Cancel with reversal of what was posted** — the mirror of `goodsreceipt_cancel`, which already reverses
  its stock. · seen in: D365, Odoo (editable MOs "even after completion"), NetSuite ·
  priority: **common** · spine: compensating `StockMove` rows, never edits/deletes of ledger rows (the
  `StockMove` docstring makes this explicit) · **buildable now**
- **Batching several parts/operations into one reporting entity** — Epicor Advanced Production. ·
  seen in: Epicor · priority: **differentiator** · spine: **DEFERRED**.

### Bullet 4 — Material Resource Planning (MRP)

- **Explode → net → lot-size → time-phase, with pegging** — the canonical MRP arithmetic: independent
  demand becomes dependent demand down the BOM; net requirement = gross − on-hand − scheduled receipts
  (+ safety stock); the planned order is offset backwards by lead time; each suggestion is pegged to what
  demanded it. · seen in: SAP (MRP procurement proposals), D365 (master planning firming planned orders),
  NetSuite (MRP), Acumatica ("time-phased purchase and production order planning"), Odoo (MRP scheduler),
  MRPeasy, Infor CSI, Fishbowl ·
  priority: **table-stakes** ·
  spine: **computed report, NO new table** — demand from the verified `SalesOrderLine` (real `item` FK) and
  `DemandForecastPeriod.final_quantity`; supply from `StockMove` aggregates + open `WorkOrder`s;
  planning parameters (`lead_time_days`, `safety_stock`) from the verified `ReorderRule`;
  make-side lead time from `BillOfMaterials.lead_time_days` · **buildable now**
- **Time-phased buckets (week / month) rather than one flat number** — the plan says *when*, not just
  *how much*. · seen in: SAP, D365, NetSuite, Acumatica, Oracle JDE (time-phasing / lead-time offset) ·
  priority: **table-stakes** · spine: derived period buckets; 4.7's `DemandForecastPeriod` already proves
  the bucketing arithmetic in this codebase (`period_start`/`period_end`) · **buildable now**
- **Planned orders split make vs buy** — a shortage of a BOM-backed item suggests a work order; a shortage
  of a bought item suggests a purchase. · seen in: SAP (planned order vs purchase requisition), D365, NetSuite,
  Acumatica, MRPeasy ("pre-filled purchase orders for missing raw materials in a single click") ·
  priority: **table-stakes** ·
  spine: the derived make/buy test (active BOM exists?) → **make** row offers `workorder_create`, **buy**
  row offers the existing `requisition_create` hand-off that `scm:reorder_alerts` already uses ·
  **buildable now**
- **Multi-level explosion so a sub-assembly shortage surfaces too** — netting the parent is not enough. ·
  seen in: SAP, D365, NetSuite, Odoo, Fishbowl (stages) · priority: **table-stakes** ·
  spine: the same recursive `BOMLine` walk with a depth cap + visited-set cycle guard · **buildable now**
- **Pegging / "why is this suggested?"** — each suggested order names the demand it covers. ·
  seen in: SAP, D365 (pegged supply), Oracle JDE (pegging), Infor CSI · priority: **common** ·
  spine: presentation — each report row lists its contributing demand documents · **buildable now**
- **Human converts the suggestion; nothing fires by itself** — D365 calls it *firming* a planned order. ·
  seen in: D365 (firming), SAP, NetSuite, Acumatica, MRPeasy (one-click, still a click) ·
  priority: **table-stakes** AND **a NavERP doctrine requirement** (the `reorder_alerts` →
  `requisition_create` and `safety_stock_report` → reviewed-apply precedents) ·
  spine: POST-only convert actions from the report · **buildable now**
- **Respect safety stock and minimum/multiple order quantity in the net figure** — don't plan below the
  buffer; round up to a sensible batch. · seen in: SAP, D365, NetSuite, Acumatica ·
  priority: **common** · spine: `ReorderRule.safety_stock` + `reorder_quantity` (**both verified**) on the
  buy side; `BillOfMaterials.output_quantity` as the make-side lot multiple · **buildable now**
- **Include open purchase orders as scheduled receipts** — supply already on its way. · seen in: SAP, D365,
  NetSuite, Acumatica, MRPeasy · priority: **table-stakes in the market**, but **advisory here** ·
  spine: `PurchaseOrderLine` has **no `item` FK** — only free-text `item_description` + `sku_hint`. Reuse
  the existing best-effort `_resolve_grn_item()` bridge, label the column *advisory*, and show the
  unmatched-line count exactly as `goodsreceipt_receive` already does. **Never** treat it as authoritative,
  and **never** add a hard FK to 4.1's line (that is 4.1's future migration, not 4.8's). ·
  **buildable now, with the caveat surfaced in the UI**
- **Exception messages ("reschedule in", "cancel", "expedite")** — MRP telling the planner what to change
  about *existing* orders, not just what to create. · seen in: SAP, D365, Oracle JDE, Infor CSI ·
  priority: **common** · spine: **DEFERRED to a later pass** — the first MRP report ships shortage +
  suggested-order rows; action-messages on existing orders are a second layer.
- **Distribution Requirements Planning (DRP) across sites** — netting per location and transferring
  between them. · seen in: SAP, D365, NetSuite · priority: **differentiator** ·
  spine: **DEFERRED** — 4.7 already documented that its demand series is item-level, not per-site
  (`ReorderRule.demand_history` docstring), and 4.8 inherits that honest limitation rather than guessing a
  fulfilment-location rule.
- **AI/ML-driven supply planning, what-if scenarios** — Infor CSI what-if, Acumatica APS, SAP PP/DS. ·
  priority: **differentiator** · spine: **DEFERRED / integration** — this pass ships deterministic,
  auditable `Decimal` arithmetic (the explicit 4.7 precedent: no numpy/pandas).

### Bullet 5 — Shop Floor Control

- **Time entries against a work order: labor time AND machine time** — the bullet names both. D365 splits
  route-card journals (operations scheduling) from job-card journals (job scheduling); NetSuite values WIP
  from "time logged against operation tasks"; SAP routings specify machine time and labor time per
  operation. · seen in: D365, NetSuite, SAP, Epicor (Data Collection captures labor and machine activity),
  Acumatica (labor, material and move transactions), MRPeasy, Odoo, Katana, Infor CSI (Factory Track) ·
  priority: **table-stakes** ·
  spine: **new table `ProductionTimeLog`** [`PRD-`] with `entry_type ∈ setup/labor/machine/downtime`,
  `started_at`/`ended_at`, derived `duration_minutes`, FK `WorkOrder` + `WorkCenter` ·
  **buildable now**
- **Start / pause / finish timers on an operation** — the operator terminal drives the clock. ·
  seen in: Odoo (shop-floor tablet timers), MRPeasy ("My Production Plan" — follow the operation, report
  usage and output), Katana (Shop Floor App), Acumatica (shop-floor kiosk), Epicor (touchscreen Data
  Collection), D365 (MES Terminal) · priority: **table-stakes** ·
  spine: the same `ProductionTimeLog` rows created/closed by POST actions (the data model is identical
  whether the clock is typed or tapped) · **buildable now (kiosk/tablet UI polish is later)**
- **Report quantity completed and quantity scrapped with each entry** — progress is quantity, not just
  hours. · seen in: D365 ("report the production progress by job or resource"), MRPeasy, Odoo, Epicor,
  NetSuite · priority: **table-stakes** ·
  spine: `quantity_completed`, `quantity_scrapped` on `ProductionTimeLog`, rolled up onto the work order by
  the posting action (`WorkOrder.quantity_produced` stays `editable=False` — the 4.7 lesson that a
  computed column must not have a second writer) · **buildable now**
- **Who did the work** — operator attribution for cost and accountability. · seen in: MRPeasy (worker
  management, per-worker production plans), Epicor, D365, Infor CSI · priority: **common** ·
  spine: **reuses the verified core spine** — `core.Party` (+ its `employee` `PartyRole`) or
  `settings.AUTH_USER_MODEL`; **never a new employee table** (L29/spine rule). Recommend the `Party` FK,
  matching how `Carrier`/`SupplierProfile` sit on `core.Party` · **buildable now**
- **Downtime capture with a reason code** — unplanned stoppage is the number the plant actually manages. ·
  seen in: Epicor Advanced MES ("real-time alerts", production inconsistencies), Odoo (OEE), MRPeasy, Infor
  CSI · priority: **common** · spine: `entry_type="downtime"` + `downtime_reason` choice on the same log —
  one log table, not two · **buildable now**
- **Actual vs planned duration and cost variance** — the whole point of collecting the time. ·
  seen in: NetSuite (Work Order Costing / WIP reports, variances), Epicor (job-level efficiency),
  MRPeasy, Odoo (cost analysis per MO), Acumatica · priority: **table-stakes** ·
  spine: **derived** — planned = `WorkCenter.setup_minutes` + rate-based run time; actual = `Sum` over
  `ProductionTimeLog`; the delta is computed, never stored · **buildable now**
- **Labor + machine cost rolling into the produced item's unit cost** — the finished-goods receipt should
  not be valued at material cost alone. · seen in: NetSuite (WIP account, routing-based costing), D365
  (actual cost methods, WIP accounting), SAP, Epicor, Odoo, MRPeasy · priority: **table-stakes** ·
  spine: the receipt's `unit_cost` = (Σ issued component value + Σ time-log hours × work-center rates)
  ÷ good quantity produced, passed into the **verified** `_post_stock_move()` → `Item.apply_receipt()`.
  **The inventory side of WIP is therefore fully expressed in `StockMove`; the GL side is not 4.8's job**
  (see below). · **buildable now**
- **OEE (availability × performance × quality)** — Odoo ships an OEE report; Epicor Advanced MES visualises
  it. · seen in: Odoo, Epicor, MRPeasy (KPIs), Infor CSI · priority: **common** ·
  spine: **derived chip on the work-center report** from the same time log (runtime vs downtime vs
  scrapped) — no extra table. Full OEE analytics → 4.11 · **partially now, deep analytics deferred**
- **Barcode / RFID scanning and mobile data collection** — Odoo barcode, Katana Shop Floor App, Acumatica
  mobile, Epicor touchscreen, MRPeasy barcoding, Fishbowl scanning. · priority: **table-stakes in the
  market** · spine: **integration/later** — the data model (a time log keyed by WO + work center + person)
  is what a scanner writes into; the scanner itself is not a Django concern this pass.
- **Machine/IoT signal capture (automatic equipment data)** — Epicor Advanced MES, Plex, Critical
  Manufacturing. · priority: **differentiator** · spine: **integration/later**.
- **Worksheets / work instructions shown at the station** — Odoo worksheets, D365 job cards. ·
  priority: **common** · spine: **reuses verified `core.Document`** for an attached instruction sheet — no
  new table · **buildable now (small), or deferred without loss**

### Beyond the bullets (strong features the five bullets don't name)

- **Subcontracting / contract manufacturing** — send components to a partner, receive the assembly back;
  D365 models it as pegged-supply BOM lines that generate a subcontract PO. · seen in: Odoo, Katana,
  D365, Acumatica, NetSuite · priority: **common** · spine: would need `WorkOrder` → `PurchaseOrder`
  linkage · **DEFERRED** (would also collide with 4.1's free-text PO lines).
- **Co-products / by-products** — a run yields more than one sellable output; D365's batch orders exist
  precisely for this. · seen in: D365 (batch orders + Formula BOMs), Odoo (by-products), SAP ·
  priority: **common in process manufacturing** · spine: a `BOMOutput` child table · **DEFERRED**.
- **In-process quality checks / control points that gate an operation** — Odoo control points, D365
  quality orders triggered by the product receipt, Epicor/Infor quality holds. ·
  priority: **table-stakes in the market** · spine: **PARKED → 4.9 QMS** (it owns Quality Inspection, NCR,
  CAPA, CoA). 4.8 should leave a clean seam (a nullable status the QMS can gate on) and nothing more.
- **Preventive maintenance on work centers / equipment** — Odoo maintenance with MTBF, Epicor equipment
  management, Acumatica equipment management. · priority: **common** ·
  spine: **PARKED → 4.13 Asset Management**.
- **Lean / kanban production without work orders** — Epicor Lean Manufacturing, D365 kanbans. ·
  priority: **differentiator** · spine: **DEFERRED** (an entirely different execution paradigm).
- **Manufacturing estimates / quoting a build** — Acumatica estimating, Epicor. · priority: **common** ·
  spine: the BOM's derived cost roll-up covers the arithmetic; a quoting document belongs to CRM 1.2 /
  4.5, not here. **PARKED**.

---

## Recommended build scope (this pass — 4 models + 2 computed report pages)

Same envelope as 4.7 (4 CRUD entities + 1 computed report module). Child line models are **not** counted as
separate entities, per the `PurchaseOrder`/`PurchaseOrderLine` and `DemandForecast`/`DemandForecastPeriod`
precedents.

Package placement (mandatory backend structure): `apps/scm/{models,forms,views,urls}/Manufacturing/` with
one file per entity — `BillsOfMaterials.py`, `WorkCenters.py`, `WorkOrders.py`, `ProductionTimeLogs.py`,
`Reports.py`. Templates: `templates/scm/manufacturing/{bom,workcenter,workorder,productiontimelog}/{list,detail,form}.html`
plus sub-module-root report pages `templates/scm/manufacturing/mrp_report.html` and
`production_schedule.html` (the `accounting/reports/…` + `scm` report precedent).

### 1. `BillOfMaterials` [`BOM-`] (+ child `BOMLine`)

Covers bullet 1 entirely and feeds bullets 2/3/4.

- **Header fields justified by research:** `item` (FK `scm.Item`, PROTECT — the produced good),
  `name`, `version`, `bom_type ∈ manufacture/kit/phantom` (Odoo kit, SAP phantom),
  `output_quantity` + `uom` (FK `scm.UOM`) (Odoo/SAP base quantity), `lead_time_days` (SAP in-house
  production time; MRP's make-side offset), `default_work_center` (FK `WorkCenter`, nullable — the
  routing stand-in), `status ∈ draft/active/obsolete` (Acumatica/Epicor revision control),
  `effective_from`/`effective_to` (SAP production-version validity), `is_default`, `notes`.
- **Line fields:** `sequence`, `component` (FK `scm.Item`, PROTECT), `quantity_per`, `uom` (FK `scm.UOM`),
  `scrap_pct` (SAP component scrap), `issue_method ∈ manual/backflush` (D365 preflush/backflush — set here,
  copied to the work order), `notes`.
- **Derived methods (no stored columns):** `explode(quantity, depth_cap, visited)` → flat requirement list
  with recursion into components that themselves have an active BOM (Fishbowl stages / Odoo multi-level);
  `is_manufactured(item)` classmethod used everywhere instead of an `Item` flag;
  `estimated_unit_cost()` rolling up `Item.standard_cost`/`average_cost`.
- **Verified FKs:** `core.Tenant` (via `TenantOwned`), `scm.Item`, `scm.UOM`, `scm.WorkCenter` (this pass).
- **Guards to specify:** at most one `is_default` **active** BOM per `(tenant, item)`;
  a component may not be the parent item (direct self-reference) and the explosion must carry a
  visited-set + depth cap (the `Location.path()` cycle-guard precedent).

### 2. `WorkCenter` [`WC-`]

Covers bullet 2's capacity half and supplies the rates bullet 5 costs with.

- **Fields justified by research:** `code`, `name`,
  `center_type ∈ machine/assembly/manual/inspection/outsourced` (SAP work-center categories),
  `location` (FK **verified** `scm.Location` — where its WIP sits; deliberately *not* a second location
  table), `org_unit` (FK **verified** `core.OrgUnit` — the owning department),
  `supervisor` (FK **verified** `core.Party` — employee `PartyRole`, never a new employee table),
  `capacity_hours_per_day`, `efficiency_pct` (Odoo OEE-based scheduling), `setup_minutes`,
  `machine_cost_per_hour`, `labor_cost_per_hour` (NetSuite cost template; SAP machine/labor time),
  `is_active`, `notes`.
- **Derived:** `scheduled_hours(start, end)` from overlapping `WorkOrder`s; `actual_hours(start, end)` from
  `ProductionTimeLog`; `utilization_pct` — the load board's numbers, none of them stored.

### 3. `WorkOrder` [`WO-`] (+ child `WorkOrderComponent`)

Covers bullet 3 entirely, bullet 2's scheduling fields, and is the object bullets 4 and 5 point at.

- **Header fields justified by research:** `item` (FK `scm.Item`), `bom` (FK `BillOfMaterials`, SET_NULL —
  the numbers live on the snapshotted lines), `quantity_planned`, `uom`,
  `order_policy ∈ make_to_stock/make_to_order` (Katana MTS/MTO; D365 manufacturing principles),
  `sales_order` (nullable FK **verified** `scm.SalesOrder` — MTO peg),
  `work_center` (FK `WorkCenter`), `priority ∈ low/normal/high/urgent` (Katana priority planning),
  `planned_start`, `planned_end`, `schedule_direction ∈ forward/backward` (MRPeasy),
  `actual_start`, `actual_end` (`editable=False`, stamped by the transitions),
  `component_location` (FK `scm.Location` — where components are drawn from),
  `output_location` (FK `scm.Location` — where finished goods land),
  `output_lot_serial` (nullable FK **verified** `scm.LotSerial`),
  `status ∈ draft/planned/released/in_progress/completed/closed/cancelled` (the D365 lifecycle, trimmed to
  what actually gates a posting in this codebase),
  `quantity_produced` / `quantity_scrapped` / `produced_unit_cost` (**all `editable=False`** — written only
  by the posting actions; the 4.7 lesson that a computed column must have exactly one writer),
  `due_date`, `notes`.
- **Component-line fields:** `sequence`, `item` (FK `scm.Item`), `quantity_required` (from `explode()`
  including `scrap_pct`), `quantity_issued` (`editable=False`), `uom`, `lot_serial` (nullable),
  `issue_method` (copied from the BOM line), `unit_cost` snapshot, `notes`.
- **Actions (each `@tenant_admin_required @require_POST`, inside `transaction.atomic()` with
  `select_for_update()` + status re-read):**
  `release` (material availability check via `Item.on_hand()` + `_insufficient_stock()`, then draft/planned
  → released), `issue_components` (negative `StockMove`s, `move_type="issue"`, `reference=wo.number`),
  `report_production` (backflush any `backflush` lines, then a positive `StockMove`,
  `move_type="receipt"`, `unit_cost` = computed production cost → rolls `Item.apply_receipt()`),
  `close`, `cancel` (compensating moves — never edit/delete a `StockMove`).
- **Verified FKs:** `scm.Item`, `scm.Location`, `scm.LotSerial`, `scm.SalesOrder`, `scm.UOM`, `WorkCenter`
  + `BillOfMaterials` (this pass), `settings.AUTH_USER_MODEL` for `released_by`.

### 4. `ProductionTimeLog` [`PRD-`]

Covers bullet 5 — the machine-time / labor-time / progress record the bullet names explicitly.

- **Fields justified by research:** `work_order` (FK, CASCADE), `work_center` (FK, PROTECT),
  `operation` (free-text label — the documented **stand-in for the deferred routing master**, the 4.1
  free-text-line precedent), `entry_type ∈ setup/labor/machine/downtime` (D365 route-card vs job-card;
  Epicor labor + machine capture), `operator` (FK **verified** `core.Party`, nullable),
  `started_at`, `ended_at`, `duration_minutes` (`editable=False`, derived from the pair but stored so a
  manual entry without a clock is still possible — document which writer owns it),
  `quantity_completed`, `quantity_scrapped` (D365/MRPeasy progress reporting),
  `downtime_reason ∈ breakdown/changeover/material_shortage/quality_hold/no_operator/other` (blank unless
  `entry_type="downtime"`), `notes`.
- **Rules to specify:** editable only while the parent work order is open (`released`/`in_progress`);
  once the WO is `closed` the entries are frozen — the audit-trail principle `StockMove` sets, softened to
  keep CRUD-completeness rules satisfied while the run is live.
- **Roll-ups it feeds (all derived):** `WorkOrder.quantity_produced` / `quantity_scrapped`, actual vs
  planned duration, labor+machine cost into the finished-goods receipt cost, and the work-center OEE chip.

### 5. Computed report pages (no models)

- **`scm:mrp_report`** — bullet 4. Time-phased netting per `(item, location)` over the chosen horizon:
  gross demand (open `SalesOrderLine` excluding `draft`/`cancelled`, approved `DemandForecastPeriod`,
  released/planned `WorkOrderComponent` requirements) − supply (live `StockMove` on-hand, open `WorkOrder`
  output, **advisory** open-PO quantities via `_resolve_grn_item()`) − `ReorderRule.safety_stock`
  → shortage rows with a lead-time-offset suggested release date, each split **make** (has an active BOM →
  POST to create a `WorkOrder`) or **buy** (POST to `requisition_create`, the existing 4.3 hand-off).
  Follows the 4.7 `safety_stock_report` shape exactly: compute, display, convert on an explicit click.
- **`scm:production_schedule`** — bullet 2. Work-center × date-bucket load board: scheduled hours vs
  `capacity_hours_per_day × efficiency_pct`, overload flagged, each `WorkOrder` shown with its material
  availability verdict. Infinite capacity (NetSuite ships infinite-capacity scheduling in WIP & Routings);
  finite levelling is deferred.

### Proposed `LIVE_LINKS["4.8"]` (bullet names verbatim from `NavERP.md`)

```python
"4.8": {
    "Bill of Materials (BOM)": "scm:bom_list",
    "Production Scheduling": "scm:production_schedule",   # report/board (safety_stock_report precedent)
    "Work Order Management": "scm:workorder_list",
    "Material Resource Planning (MRP)": "scm:mrp_report",  # computed, compute-then-convert
    "Shop Floor Control": "scm:productiontimelog_list",
},
```

If the load board proves too thin to be a sidebar destination, the fallback for **Production Scheduling**
is `scm:workcenter_list` (the capacity master) — but the board is the better answer, because the bullet
says *"planning of production runs based on capacity and material availability"*, which is a view over
work orders, not a master-data list.

### GL / accounting hand-off — explicit answer (L29)

Manufacturing is the sub-module where the market's products *do* post to the ledger: NetSuite moves value
into a WIP account from time logged and out to the assembly asset account on completion; D365 generates a
ledger journal on "reported as finished" and reverses estimates with actuals at "ended".

**NavERP 4.8 must NOT do any of that.** Concretely:

- The **inventory** effect is fully expressible in `StockMove` and stays here: components leave stock
  (`issue`), finished goods enter stock (`receipt`) at a `unit_cost` that already absorbs material + labor +
  machine cost. `Item.apply_receipt()` keeps the weighted average honest. No GL row is needed for this.
- The **WIP control account, labor absorption, overhead application, and production variance postings**
  are ledger concepts owned by `apps.accounting` (Module 2, which owns `JournalEntry`/`JournalLine`/
  `GLAccount`/`FiscalPeriod`). 4.8 **does not** create them.
- If a GL hand-off is ever wanted, it must follow the **only sanctioned pattern** — the 4.6 freight →
  **draft** `accounting.Bill` precedent: a draft document a finance user reviews and posts. Even that is
  **out of scope for this pass**; note it in the model docstring and move on.
- There must be **no second ledger, no `WorkOrderCostEntry` table shadowing `JournalLine`**, and no
  `GLAccount` FK on any 4.8 model this pass.

### Deliberately NOT added

- ~~`Item.is_manufactured`~~ / ~~`Item.item_role ∈ raw/finished`~~ — derived from BOM existence.
- ~~A `WIP` quantity field~~ — issued-minus-received is an aggregate over `StockMove`.
- ~~A `Bin`/`Resource` location table~~ — `scm.Location` already covers it (the 4.4 precedent of extending
  `Location` rather than forking it).
- ~~An employee/operator table~~ — `core.Party` + `PartyRole` (L29).
- ~~A `PurchaseOrderLine.item` FK~~ — 4.1's free-text lines are 4.1's migration to make, not 4.8's.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **In-process quality checks, control points, non-conformance on a production run, certificates of
  analysis for a produced lot** → **4.9 QMS** (its five bullets are Quality Inspection, NCR, CAPA, Audit
  Management, CoA). 4.8 leaves the seam; it does not build a quality gate.
- **Preventive/corrective maintenance of machines, equipment master, MTBF** → **4.13 Asset Management**
  (Odoo/Epicor/Acumatica bundle it with manufacturing; NavERP does not).
- **Production/OEE dashboards, throughput and cost-of-goods analytics, predictive disruption** →
  **4.11 Supply Chain Analytics**. 4.8 ships two focused operational pages, not an analytics suite.
- **Operator labour hours for payroll, shift rosters, plant labour standards** → **4.14 Labor Management**
  and **HRM 3.x** (Time Tracking / Attendance are already built). `ProductionTimeLog` is a *cost and
  progress* record against a work order, not a timesheet — do not merge the two.
- **Subcontract purchase orders to a contract manufacturer** → **4.1 Procurement** + a later 4.8 pass;
  the PO document already exists and must not be re-declared.
- **Picking components with WMS directed tasks / putting finished goods away** → **4.4 WMS**
  (`PickTask`/`PutawayTask` exist). 4.8's issue/receive posts stock directly through
  `_post_stock_move()`; wiring a work order into a WMS pick wave is a 4.4 extension, not a 4.8 table.
- **Forecast generation, seasonality, consensus demand** → **4.7** (built). 4.8 *reads* the approved
  forecast; it never recomputes one.
- **Safety-stock and reorder-point calculation** → **4.7 / 4.3** (built). MRP *reads* `ReorderRule`;
  it must not write to `safety_stock`/`reorder_point` (that is `apply_computed()`'s job, behind a review).
- **WIP/variance journal entries, standard-cost revaluation, cost accounting close** → **`apps.accounting`**
  (Module 2, and 2.7 Cost Accounting). See the GL section above.
- **Product variants / configurable products** → a **Module 5 Inventory** item-master decision.

---

## Deferred (later passes / integrations)

- **Routings / operation sequencing as a master (`Routing` + `RoutingOperation`, SAP production versions,
  NetSuite routing templates, Odoo BOM operations tab)** — the single biggest deferral. This pass carries
  one `work_center` FK on the work order plus a free-text `operation` label on the time log, which is
  enough to record machine and labor time per station (the bullet's actual ask) without a 6th and 7th
  table. A later pass promotes the label to a `WorkOrderOperation` child with a routing master; the time
  log's FK then moves from `work_center` to the operation. Documented stand-in, in the spirit of 4.1's
  free-text lines and 4.2's free-text catalog.
- **Finite-capacity / constraint-based scheduling, capable-to-promise, what-if scenarios** (Infor CSI APS,
  Acumatica APS, SAP PP/DS, Epicor) — a real solver. This pass shows load vs capacity and flags overload.
- **Drag-and-drop Gantt rescheduling** (MRPeasy, NetSuite, Infor, Epicor) — a front-end capability over
  fields this pass already ships; no data-model change needed later.
- **MRP exception/action messages on existing orders ("reschedule in/out", "cancel", "expedite")** — layer
  two of the MRP report.
- **DRP / multi-site netting and inter-site transfer suggestions** — blocked on the same
  fulfilment-location rule 4.7 documented as missing.
- **Subcontracting / contract manufacturing** (Odoo, Katana, D365 pegged supply, Acumatica) — needs
  `WorkOrder` ↔ `PurchaseOrder` linkage and collides with 4.1's free-text PO lines.
- **Co-products / by-products and formula (process) BOMs** (D365 batch orders, SAP, Odoo) — a `BOMOutput`
  child table plus a cost-apportionment rule; a pass of its own.
- **Disassembly / unbuild / repair / reverse work-order types** (Fishbowl, Odoo) — inverts the posting
  direction; do it deliberately, not as a `wo_type` choice bolted on now.
- **Engineering Change Orders with approval workflow** (Acumatica, Epicor, SAP) — `status` + `version` +
  effectivity dates cover revision control this pass; the governed change request is later.
- **Product configurator / manufacturing estimates** (Acumatica, Infor CSI, Epicor) — needs an item-variant
  axis that `scm.Item` does not have.
- **Lean / kanban production without work orders** (Epicor Lean, D365 kanbans) — a different execution
  paradigm.
- **Master Production Schedule as its own document** (MRPeasy, SAP, D365) — 4.7's approved forecast plus
  the MRP report cover the planner's need for now.
- **Barcode / RFID scanning, tablet & kiosk shop-floor UIs, MES terminals** (Odoo, Katana, Acumatica,
  Epicor, MRPeasy, Fishbowl, D365) — **integration/UI**, informs the data model (a time log keyed by work
  order + work center + operator is exactly what a scanner writes) but ships later.
- **Machine/IoT signal capture and automated OEE** (Epicor Advanced MES, Plex, Critical Manufacturing) —
  **integration/later**.
- **AI/ML supply planning** (SAP PP/DS, Infor, Acumatica) — deterministic `Decimal` arithmetic only, per
  the explicit 4.7 precedent (no numpy/pandas/scikit dependency).
- **Any WIP/variance GL posting** — see the GL section: it belongs to `apps.accounting`, and even a draft
  hand-off is out of scope for this pass.

---

## Sources

- Odoo Manufacturing — https://www.odoo.com/app/manufacturing-features ·
  https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing.html ·
  https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing/advanced_configuration/using_work_centers.html
- Microsoft Dynamics 365 Supply Chain Management, Production control —
  https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/production-process-overview
- Oracle NetSuite — https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N2341076.html ·
  https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2346224.html ·
  https://www.netsuite.com/portal/products/erp/production-management/work-order-management.shtml
- SAP S/4HANA Production Planning —
  https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/introduction-to-sap-pp-production-planning-in-sap-cloud-public-edition/ba-p/13573624 ·
  https://community.sap.com/t5/supply-chain-management-blog-posts-by-sap/overview-of-the-key-functionality-production-planning-and-detailed/ba-p/13409001
- Acumatica Manufacturing Edition — https://www.acumatica.com/cloud-erp-software/manufacturing-management/
- Epicor Kinetic Production Management —
  https://www.epicor.com/en-us/products/enterprise-resource-planning-erp/kinetic/production-management/ ·
  https://www.top10erp.org/products/epicor-kinetic/production-management
- Infor CloudSuite Industrial (SyteLine) — https://www.erpresearch.com/en-us/infor-syteline-csi-erp-overview ·
  https://www.frontstep.bg/solutions/infor-cloudsuite-industrial-syteline-erp/production-planning-scheduling/
- Katana — https://www.katanamrp.com/features/
- MRPeasy — https://www.mrpeasy.com/production-scheduling-software/ ·
  https://www.mrpeasy.com/blog/manufacturing-erp-systems/
- Fishbowl Manufacturing — https://www.fishbowlinventory.com/manufacturing/manufacture-and-work-orders ·
  https://help.fishbowlinventory.com/hc/en-us/articles/360042632234-Bill_of_Materials
- MRP arithmetic reference (explode/net/lot-size/time-phase/peg) —
  https://docs.oracle.com/cd/E16582_01/doc.91/e15139/plng_material_reqs.htm

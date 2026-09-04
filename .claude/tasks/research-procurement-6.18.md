# Research — Sub-module 6.18: Inventory & Warehouse Integration (Module 6 — Procurement Management System, `procurement`)

> **Scope discipline (L31):** this file researches ONE sub-module. 6.18 is the *procurement side of the
> inventory boundary* — what a buyer sees before raising a PR/PO, how buying is triggered from stock, how
> stock is consumed/returned internally, where received goods landed, and how counts reconcile. WMS
> mechanics, forecasting, lot/serial and valuation belong to SCM 4.3/4.4/4.7 and Module 5 and are parked.

---

## Repo state checked first

### LIVE_LINKS built so far in module 6
`apps/core/navigation.py:1413-1632` — **6.1 … 6.15 all present**; `6.16`, `6.17`, `6.18`, `6.19` absent.
(6.18 is *not* the next unbuilt key — 6.16 is — but 6.18 is the explicitly named target this run.)

### Procurement models already built (do not re-propose)
`apps/procurement/models/__init__.py:1-187` — 6.1 alerts/widgets, 6.2 requisition templates+amendments,
6.3 approval engine, 6.4 vendor portal/suspension, 6.5 RFx, 6.6 sourcing, 6.7 e-auction, 6.8 contracts,
6.9 catalog/punch-out, 6.10 PO changes + `generate_po_from_requisition`, 6.11 ASN/backorder/delivery
schedule, 6.12 `ReceiptTolerancePolicy` / `ReceiptDiscrepancy` / `ReturnToVendor(+Line)` /
`resolve_line_item`, 6.13 supplier invoices/variances/disputes, 6.14 spend rules/reports/maverick,
6.15 `BudgetMapping` / `CostForecast` + the committed/requested line-window helpers.

### Spine entities VERIFIED to exist (grep evidence — L28, the ERD is intent, the grep is truth)

**`apps/scm` owns the inventory spine.**

| Entity | file:line | Notes that matter for 6.18 |
|---|---|---|
| `scm.Item` | `apps/scm/models/InventoryManagement/Items.py:73` | `sku`, `uom`, `standard_cost`, `average_cost` (cached, `editable=False`), item-wide `reorder_point:106`. **No vendor FK** — who to buy from is not on the item. `on_hand(location=None)` at `:197` is the ONLY quantity source. |
| `scm.ItemCategory` / `scm.UOM` | `Items.py:34` / `Items.py:51` | |
| `scm.Location` | `apps/scm/models/InventoryManagement/Locations.py:14` | **THERE IS NO `Bin` OR `Zone` MODEL.** `LOCATION_TYPES` at `:17-23` = warehouse / zone / bin / staging / transit, self-parented via `parent:34`. 4.4 bin attributes live here: `capacity:41`, `pick_sequence:44`, `abc_class:46`, `is_pickable:48`. `path()` at `:95` renders `WH1 › ZONE-A › BIN-01`. |
| `scm.StockMove` | `apps/scm/models/InventoryManagement/StockMoves.py:13` | Append-only, **signed** `quantity:43`, `unit_cost:44`, `reference:47`, `moved_at:50`. `MOVE_TYPES:16-36` = receipt / issue / transfer / adjustment / consumption / production / maintenance. Docstring `:21-35` is explicit: `issue` means **CUSTOMER** demand and feeds 4.7's forecasts — an internal cost-centre draw must never be booked as `issue`. |
| `scm.LotSerial` | `apps/scm/models/InventoryManagement/LotSerials.py:5` | |
| `scm.ReorderRule` | `apps/scm/models/InventoryManagement/ReorderRules.py:26` | `reorder_point:43`, `safety_stock:46`, `reorder_quantity:48`, `lead_time_days:61`, `review_period_days:66`, `abc_class`/`xyz_class:78-81`, `computed_*:82-85`. Helpers: `on_hand_map():107`, `is_below_point():133`, `suggested_quantity():136`, `apply_computed():319`. **`is_below_point` tests on-hand ONLY — open PO supply is not counted.** |
| `scm.StockAdjustment` / `Line` | `apps/scm/models/InventoryManagement/StockAdjustments.py:11` / `:65` | `REASON_CHOICES:23` (cycle_count / write_off / damage / found / revaluation / other), `status:35`, signed `quantity_delta:72`, `value_impact():48`. |
| `scm.StockTransfer` / `Line` | `apps/scm/models/InventoryManagement/StockTransfers.py:11` / `:73` | |
| `scm.PurchaseRequisition` / `Line` | `apps/scm/models/ProcurementManagement/PurchaseRequisitions.py:14` / `:151` | `org_unit:47`, `budget:50`, `currency:53`, `required_by:55`, `status:56`, `budget_check():94`. Lines are **free text**: `item_description:155`, `sku_hint:156`, `uom_hint:158`, `gl_account:164`. |
| `scm.PurchaseOrder` / `Line` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` / `:172` | `RECEIVABLE_STATUSES:34`, `received_by_line():101`, `outstanding_quantity():213`. Lines free text (`sku_hint:177`). |
| `scm.GoodsReceiptNote` / `Line` | `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:15` / `:166` | `location:40` = "Receiving / staging location the goods land in". |
| `scm.CycleCountTask` / `Line` | `apps/scm/models/WarehouseManagement/CycleCountTasks.py:16` / `:90` | `[CC-]`, `count_method:40` (full/abc/random/zone), `status:41`, `adjustment` provenance FK `:48`, **server-side snapshot** `expected_quantity:98` (blind), `counted_quantity:100` nullable, `variance:108`, `has_variance:115`. |
| `scm.PutawayTask` / `PickTask` | `apps/scm/models/WarehouseManagement/PutawayTasks.py:16` / `PickTasks.py:16` | |
| `scm.SalesOrderAllocation` | `apps/scm/models/OrderManagement/SalesOrderAllocations.py:15` | Soft claim; `ACTIVE_STATUSES`. |
| `core.Party` / `core.OrgUnit` / `core.Tenant` | `apps/core/models/Party.py:5` / `OrgUnit.py:5` / `Tenant.py:5` | Vendor = a `PartyRole`, never a second table. |
| `accounting.GLAccount` / `Budget` | reached by string FK from `PurchaseRequisitions.py:50,164` | Accounting owns the ledger (L29). |

**`apps/inventory` (Module 5) owns warehousing/bins and counting — verified:**

| Entity | file:line | Notes |
|---|---|---|
| `inventory.BinCapacity` | `apps/inventory/models/WarehousingBinManagement/BinCapacities.py:26` | Keyed to `scm.Location` (`:29`), NOT a bin master. Its own docstring `:5-8` says the bin, its tree position and its on-hand all stay 4.3's. |
| `inventory.CrossDockOrder` | `apps/inventory/models/WarehousingBinManagement/CrossDockOrders.py:47` | `[XD-]` |
| `inventory.PutawayRule` + `resolve_putaway_suggestion()` | `apps/inventory/models/ReceivingPutaway/PutawayRules.py:48` / `:150` | Item/category/catch-all tiers → destination `scm.Location`. **ZERO writes** (`:17-18`): applying a suggestion stays SCM's job. |
| `inventory.CountProgram` | `apps/inventory/models/StocktakingCycleCounting/CountPrograms.py:18` | `[CTP-]`, `frequency:49` daily/weekly/monthly, `weekday:50`, `day_of_month:52`, `abc_class:47`, `count_method:56`. **`generate_tasks():85` MINTS spine `scm.CycleCountTask` rows** and stamps provenance in `notes` — the exact bridge pattern 6.18 should copy. |
| `inventory.PhysicalInventory` | `apps/inventory/models/StocktakingCycleCounting/PhysicalInventories.py:31` | `[PHY-]` |
| `inventory.InventoryReservation` | `apps/inventory/models/InventoryTrackingControl/InventoryReservations.py:37` | `[RSV-]`, `ACTIVE_STATUSES:56`, soft claim, posts **no** StockMove. |
| `inventory.StockStatus` | `apps/inventory/models/InventoryTrackingControl/StockStatuses.py:18` | active/damaged/expired/on_hold, `SELLABLE_STATUSES:28`. |
| `inventory.StockLevelPlan` | `apps/inventory/models/ForecastingPlanning/StockLevelPlans.py:24` | `[SLP-]`, `base_target_qty`, `min_qty`, `max_qty`, seasonality-adjusted. |

**Existing derived pages / actions that already cover part of 6.18 (link, never rebuild):**

* `inventory:stocklevels` → `apps/inventory/views/InventoryTrackingControl/StockLevels.py:80`. **Declares no table.**
  Formula at `:124`: `available = on_hand − (SO allocations + reservations) − non-sellable`. `_on_order_map():37`
  derives open-PO supply by **exact-string `sku_hint` ↔ `Item.sku`** match.
* `scm:reorder_alerts` → `apps/scm/views/InventoryManagement/Reports.py:96`. Live list of below-point rules with
  `suggested`/`shortfall`; **persists nothing**, and the requisition form is *not* pre-filled (documented gap in
  `ReorderRules.py:5-6`).
* `inventory:reorderdraft` → `apps/inventory/views/PurchaseOrderManagement/ReorderDrafts.py:33`. Ticked
  below-point rules → **draft `scm.PurchaseOrder`s** grouped by a hand-picked vendor. Persists nothing either;
  its docstring `:10-11` states the gap plainly: *`scm.Item` has no vendor FK, so who to buy from is a human
  decision taken here, once, at draft time.*
* `scm:cyclecounttask_list`, `inventory:countprogram_list`, `inventory:physicalinventory_list`,
  `inventory:bincapacity_list`, `scm:reorderrule_list`, `scm:putawaytask_list`, `scm:stockadjustment_*`.

### The ledger-writer rule (decisive for bullet 3)
`grep "StockMove.objects.create|_post_stock_move"` across `apps/` returns **production writers only inside
`apps/scm/views/`** (`_helpers.py:133,149`; transfers `:206-210`; putaway `:227-231`; picks `:256`; GRN
`:328`; GRN reversal `:364`; adjustments `:389`; plus manufacturing/returns/NCR callers). Every hit under
`apps/inventory/` is a **test fixture**. Module 5 states the rule outright (`PutawayRules.py:17-18`):
*"Module 5 never moves another app's stock."*
→ **Module 6 must not post `StockMove` either.** A 6.18 issue/return document changes stock by **minting a
draft `scm.StockAdjustment`**, exactly as `CountProgram.generate_tasks()` mints a `scm.CycleCountTask`.

### Provenance join that makes bullet 4 free
`apps/scm/views/_helpers.py:328-330` posts every receipt move with `reference=grn.number` and
`reason="Goods receipt"`, and `StockMove` is indexed on `(tenant, reference)` (`StockMoves.py:60`).
So "where did GRN-00012's goods land" is a **query, not a table**.

---

## Leaders surveyed (with source links)

1. **Odoo 18 Inventory + Purchase** — open-source ERP; the cleanest published field vocabulary for reordering
   rules and the Replenishment dashboard. — [Reordering rules](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment/reordering_rules.html) ·
   [Configure reordering rules (Purchase)](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/purchase/products/reordering.html)
2. **Oracle NetSuite (Advanced Inventory Management)** — mid-market ERP; reorder point vs. **preferred stock
   level** vs. safety stock in **days**, per-location lead time, auto-calculate flags. —
   [Advanced Inventory Management](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N2285050.html) ·
   [Lead Time and Safety Stock Per Location](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2286205.html)
3. **Oracle Fusion Inventory Management + Self-Service Procurement** — enterprise suite; **min-max planning**
   at org or subinventory level, an ASL-driven **requisition-generating batch report**. —
   [Min-Max Planning (Fusion)](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26c/famml/min-max-planning.html) ·
   [Set Up Min-Max Planning](https://docs.oracle.com/en/cloud/saas/supply-chain-management/22b/faims/set-up-min-max-planning.html)
4. **Microsoft Dynamics 365 Supply Chain Management** — enterprise ERP; **coverage codes** (Period /
   Requirement / Min-Max / Manual), coverage groups, safety-stock journal; and WMS-side **location directives**
   + **license plates** for putaway destination, plus **cycle-count plans and thresholds**. —
   [Coverage settings](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/coverage-settings) ·
   [Define coverage rules for items](https://learn.microsoft.com/en-us/dynamics365/supply-chain/master-planning/tasks/define-coverage-rules-items) ·
   [Work with location directives](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/create-location-directive) ·
   [License plate receiving](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/warehousing-mobile-device-app-license-plate-receiving) ·
   [Cycle counting scenarios](https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/cycle-counting-scenarios)
5. **SAP S/4HANA MM (with Ariba upstream)** — the reference vocabulary for stock **types** a buyer sees
   (`MMBE` stock overview: unrestricted / quality inspection / blocked / reserved / on-order), the
   **MD04 stock–requirements list** as the buyer's supply-and-demand timeline, and **goods issue movement
   types 201 (cost centre) / 261 (order)** with reservations. —
   [MMBE stock overview walk-through](https://www.guru99.com/how-to-get-overview-of-material-stock.html) ·
   [Stock/Requirements List MD04](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/stock-requirements-list/ba-p/13538557) ·
   [Movement types 201 vs 261](https://community.sap.com/t5/enterprise-resource-planning-q-a/movment-type-201-261/qaq-p/5816073) ·
   [Reservations MB21/MB1A](https://www.guru99.com/reservation-of-inventory.html)
6. **Coupa (Procure-to-Pay → Inventory Management)** — spend-management suite; min/max pull-based
   replenishment with automated suggestions, and an explicit **inventory consumption** transaction that draws
   down on-hand against a PO. — [Inventory Consumptions API](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/the-coupa-core-api/resources/transactional-resources/receipts-api/inventory-consumptions-api-(inventory_consumptions)) ·
   [Inventory Transactions (Receipts) Export](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/coupa-core-flat-files-(csv)/flat-file-(csv)-export/inventory-transactions-(receipts)-export) ·
   [Coupa Inventory Management module overview](https://www.zanovoy.com/modules/coupa-inventory-management)
7. **Precoro** — SMB procurement suite; the closest analogue to what 6.18 is: a purchasing product with a thin
   warehouse layer. **Minimum Stock Level / Reorder To / Need To Order / On Order** fields, low-stock alerts,
   an "Order low stock items" button, and an **Inventory Consumption** document that reverses into stock
   transfers when cancelled. — [Minimum Stock Level Functionality](https://help.precoro.com/minimum-stock-level-functionality) ·
   [Inventory Consumption](https://help.precoro.com/inventory-consumption) ·
   [How to Create a Warehouse](https://help.precoro.com/how-to-manage-the-warehouse) ·
   [Stock Transfers](https://help.precoro.com/how-to-create-and-manage-a-stock-transfer-1)
8. **Cin7 Core / Omni (ex-Unleashed lineage)** — inventory-first product with purchasing;
   **Smart Reorder / reorder suggestions**, per-supplier-per-location reorder parameters, and a
   "Products Low on Stock" report carrying available / on-order / reorder / minimum-before-reorder. —
   [Generate reorder suggestions](https://help.core.cin7.com/hc/en-us/articles/10553610466575-Generate-reorder-suggestions) ·
   [Smart reorder suggestions](https://help.core.cin7.com/hc/en-us/articles/10955759303055-Smart-reorder-suggestions) ·
   [Low stock reorder](https://help.core.cin7.com/hc/en-us/articles/9034475105167-Low-stock-reorder) ·
   [Configure product suppliers](https://help.core.cin7.com/hc/en-us/articles/12047242513039-Configure-product-suppliers)
9. **Fishbowl Inventory** — SMB WMS/inventory; cycle-count report by location with a blank column for the
   physical figure, blind counts, and count adjustments that *replace* the location's quantity. —
   [Cycle count best practices](https://www.fishbowlinventory.com/blog/inventory-cycle-count-key-steps-and-best-practices) ·
   [Drive Cycle Count Report](https://help.fishbowlinventory.com/drive/s/article/Drive-Cycle-Count-Report)
10. **Procurify** — purchasing/spend product with a deliberately thin inventory layer: stock levels + reorder
    thresholds that turn into requisitions, and no full WMS. Useful as the *floor* of what a procurement
    product must do here. — [Procurify vs Coupa feature comparison](https://www.procuredesk.com/procurify-vs-coupa/) ·
    [Purchase order and inventory management](https://www.procuredesk.com/purchase-order-and-inventory-management/)
11. **Warehouse-accuracy practice (cross-vendor)** — the count-variance root-cause taxonomy and the
    receiving-error share of variance, used to shape the cycle-count-to-supplier feedback loop. —
    [Cycle count variance](https://racklify.com/encyclopedia/cycle-count-variance-the-silent-indicator-of-inventory-accuracy/) ·
    [Root cause of inventory variance](https://www.stockount.com/articles/how-to-find-the-root-cause-of-inventory-variance)

---

## Feature catalog (this sub-module only)

Priority key: **MUST** = table-stakes across the leaders · **SHOULD** = most have it · **COULD** = a few
standouts / differentiator.

### Bullet 1 — Stock Level Visibility ("real-time view of on-hand quantities for stocked items")

- **On-hand by item × location** — the base figure every product opens with. · seen in: all 10 · **MUST**
  · spine: DERIVED `Sum(scm.StockMove.quantity)` — `Item.on_hand()` `Items.py:197` · buildable now
- **Available / ATP distinct from on-hand** — SAP MMBE separates unrestricted from reserved; Cin7 reports
  `available` beside `on order`; Odoo shows `On Hand` beside `Forecast`. · seen in: SAP, Cin7, Odoo, NetSuite,
  D365 · **MUST** · spine: DERIVED, and it must reuse the ONE formula already in the codebase —
  `available = on_hand − (SalesOrderAllocation + InventoryReservation active claims) − non-sellable StockStatus`
  (`StockLevels.py:124`). Do not invent a second definition. · buildable now
- **On-order (open PO quantity) shown next to on-hand** — the single most procurement-specific column: Oracle
  min-max explicitly plans on *on-hand **plus** on-order*; SAP MD04 lists open POs as supply elements; Precoro
  flips its low-stock dot from red to yellow once an order exists. · seen in: Oracle, SAP, Precoro, Cin7,
  NetSuite · **MUST** · spine: DERIVED from `scm.PurchaseOrderLine` where PO status ∈
  `RECEIVABLE_STATUSES` (`PurchaseOrders.py:34`) minus accepted `GoodsReceiptLine` — the `_on_order_map()`
  shape at `StockLevels.py:37`. Free-text `sku_hint` ↔ `Item.sku` exact match (L28 legacy). · buildable now
- **Earliest expected arrival + vendor on the on-order figure** — SAP MD04's whole point is *when* supply
  lands, not just how much. `inventory:stocklevels` has the quantity but **not** the date or the vendor. ·
  seen in: SAP MD04, Odoo (lead times on the replenishment view), NetSuite · **SHOULD** · spine: DERIVED from
  `PurchaseOrder.expected_date` + `vendor` (`core.Party`) · buildable now — **this is the column that makes a
  6.18 page different from the Module 5 one**
- **Open requisition (not yet ordered) quantity** — demand already raised but not converted; nothing in the
  repo surfaces it. · seen in: SAP MD04 (PR as an MRP element), Coupa, Precoro · **SHOULD** · spine: DERIVED
  from `scm.PurchaseRequisitionLine` where requisition status ∈ approved/pending (`REQUESTED_PR_STATUSES` /
  `COMMITTED_PR_STATUSES` already defined in 6.15 `BudgetMappings.py`) · buildable now
- **Days-of-cover / coverage days** — on-hand ÷ average daily demand, so a buyer sorts by urgency rather than
  by quantity. · seen in: NetSuite (safety stock in days), Odoo (visibility days), Cin7 · **SHOULD** ·
  spine: DERIVED from `ReorderRule.avg_daily_demand` (`ReorderRules.py:76`, already computed by 4.7) ·
  buildable now
- **Stock-type breakdown (unrestricted / QC / blocked / reserved)** — SAP's MMBE columns. · seen in: SAP,
  D365 (inventory status), Fishbowl · **SHOULD** · spine: DERIVED from `inventory.StockStatus`
  (`StockStatuses.py:21-26`) — do NOT re-declare a classification table · buildable now
- **In-transit quantity** — goods shipped but not received. · seen in: SAP, D365, Cin7 · **COULD** ·
  spine: DERIVED from `scm.Location(location_type='transit')` on-hand + 6.11 `AdvancedShipmentNotice` lines ·
  buildable now (thin)
- **Stock check inline on the requisition/PO line before ordering** — Coupa/Precoro/Procurify all show
  "you already have N" at request time to stop redundant buying. · seen in: Coupa, Precoro, Procurify,
  Oracle SSP · **COULD** · spine: DERIVED, an HTMX panel on the existing requisition form · **later pass** —
  it touches 6.2's form, which 6.18 should not edit this pass
- **Consigned / vendor-managed stock flagged separately** — Coupa tracks consigned inventory distinctly. ·
  seen in: Coupa, SAP · **COULD** · spine: `scm.Item.owner_client` exists (`Items.py:148`) but means *3PL
  client*, not *supplier-owned* — a genuine gap · **deferred** (already parked here by 6.11)

### Bullet 2 — Reorder Point Automation ("automatic generation of requisitions when inventory falls below a set threshold")

- **Per-item × per-location reorder point + reorder quantity** — universal. · seen in: all 10 · **MUST** ·
  spine: **`scm.ReorderRule` ALREADY EXISTS** (`ReorderRules.py:26`) with `reorder_point`, `safety_stock`,
  `reorder_quantity`, `lead_time_days`, ABC/XYZ, and five safety-stock methods. **Never re-declare it.**
- **Min/max (order-up-to) semantics** — Odoo `Min Quantity`/`Max Quantity`, D365 coverage code `Min/Max`,
  Oracle min-max, NetSuite reorder point + **preferred stock level**. · seen in: Odoo, D365, Oracle, NetSuite,
  Coupa, Precoro (`Reorder To`) · **MUST** · spine: `ReorderRule.suggested_quantity()` (`:136`) already tops up
  to `reorder_point + safety_stock`; a distinct **order-up-to target** (NetSuite's *preferred stock level*,
  Precoro's *Reorder To*) is the one number missing → a nullable override on the new policy table, documented
  as an override, not a copy · buildable now
- **Order multiple / rounding, minimum order quantity** — Odoo `Multiple Quantity`; Cin7 per-supplier reorder
  quantity; NetSuite item vendor minimums. · seen in: Odoo, Cin7, NetSuite, D365 · **MUST** · spine: **new**
  (nothing in `ReorderRule`) · buildable now
- **Preferred vendor on the rule so the proposal is routable** — Odoo's `Vendor` field auto-populates the RFQ;
  Oracle uses the **Approved Supplier List** to generate the requisition; Cin7 sets reorder params per
  supplier. · seen in: Odoo, Oracle, Cin7, NetSuite, Precoro · **MUST** · spine: **new** — `core.Party`
  (supplier `PartyRole`), because `scm.Item` has no vendor FK (confirmed at `ReorderDrafts.py:10-11`) ·
  buildable now — **the single highest-value field in this sub-module**
- **Procurement source / preferred route (buy vs transfer vs make)** — Odoo `Preferred Route`; Oracle min-max
  can raise a purchase requisition, a transfer order or a work order; D365 the same. · seen in: Odoo, Oracle,
  D365, Cin7 (`purchase / transfer / assemble`) · **SHOULD** · spine: **new** CHOICES column; only the `buy`
  branch generates a document this pass (transfer → link to `scm:stocktransfer_create`) · buildable now
- **Trigger mode: automatic vs review-then-release** — Odoo `Trigger` = Auto | Manual; D365 coverage code
  `Manual`; Oracle's report *suggests*, orchestration *creates*. Every product with an auto mode still keeps a
  human gate on money. · seen in: Odoo, D365, Oracle, NetSuite · **MUST** · spine: **new** CHOICES ·
  buildable now — mirrors the repo's own `ReorderRule.apply_computed()` "calculate proposes, a person accepts"
  contract (`ReorderRules.py:319-322`)
- **Count on-order as supply when testing the threshold** — Oracle min-max plans on *on-hand plus on-order*;
  Precoro's `On Order` column exists precisely so you do not double-order. **`ReorderRule.is_below_point()`
  (`:133`) tests on-hand ONLY** — a real behavioural gap that causes duplicate PRs. · seen in: Oracle, SAP,
  Precoro, Cin7, NetSuite · **MUST** · spine: **new** boolean on the policy, applied by the run · buildable now
- **A replenishment RUN that persists its proposal lines** — Oracle's Min-Max Planning *report* run, Odoo's
  Replenishment dashboard, Cin7's Smart Reorder, D365's master-planning run. The run is a reviewable artefact:
  who proposed what, on which numbers, and what happened to each line. · seen in: Oracle, Odoo, D365, Cin7,
  NetSuite · **MUST** · spine: **new** run + suggestion tables. `scm:reorder_alerts` and
  `inventory:reorderdraft` both compute-and-forget — **nothing in the repo persists a proposal** · buildable now
- **Snapshotted numbers on each suggestion line** (on-hand, available, on-order, reorder point, target,
  suggested qty, lead time, vendor, unit price) — so the record still explains itself after stock moves. ·
  seen in: Oracle (report output), D365, Odoo · **MUST** · spine: **new**, and the repo already blesses this
  exact pattern: `CycleCountTaskLine.expected_quantity` is snapshotted server-side and `editable=False`
  (`CycleCountTasks.py:97-98`) · buildable now
- **Per-line buyer decision: accept / snooze / dismiss with a reason** — Odoo has an explicit *Snooze*;
  D365 firming; Cin7 lets you drop lines before creating the PO. · seen in: Odoo, D365, Cin7 · **SHOULD** ·
  spine: **new** CHOICES + `snooze_until` date · buildable now
- **Release accepted lines into REQUISITIONS grouped by vendor** — this is the NavERP.md bullet's literal
  wording ("generation of requisitions"), and it is the procurement-correct target: a PR then flows through
  6.3 approval routing, 6.15 budget availability and 6.10 `generate_po_from_requisition`. Oracle generates
  requisitions, not POs, for exactly this reason. · seen in: Oracle, SAP (PR from MRP), Coupa, Procurify ·
  **MUST** · spine: writes `scm.PurchaseRequisition` + `PurchaseRequisitionLine` (free-text lines carrying
  `sku_hint`/`uom_hint`, `gl_account`) · buildable now — **NOTE: distinct from `inventory:reorderdraft`,
  which creates draft POs and skips approval/budget entirely**
- **Requisition defaults per policy (org unit, budget, GL account, currency)** — so the generated PR is
  budget-checkable and routable without hand-editing. · seen in: Coupa, Oracle, Precoro, Procurify ·
  **SHOULD** · spine: **new** FKs → `core.OrgUnit`, `accounting.Budget`, `accounting.GLAccount` (the exact
  three `scm.PurchaseRequisition` reads at `:47,:50,:164`) · buildable now
- **Scheduled/batch run rather than only on-demand** — Oracle schedules the min-max report, NetSuite runs AIM
  weekly, D365 schedules master planning, Precoro emails a daily low-stock reminder. · seen in: Oracle,
  NetSuite, D365, Precoro · **SHOULD** · spine: a `trigger` CHOICES column + a management command;
  actual cron is **integration/later** (same posture as `CountProgram.is_due()`)
- **Low-stock alert notification to the buyer** — Precoro's daily email + red/yellow dots. · seen in: Precoro,
  Coupa, Cin7 · **COULD** · spine: **reuse `procurement.ProcurementAlert` (6.1)** — do not add a second alert
  table · buildable now (thin) / email is integration-later
- **Consumption-driven / pull replenishment from actual usage** — Coupa's pull-based min/max, SAP consumption-
  based planning. · seen in: Coupa, SAP · **COULD** · spine: DERIVED from the 6.18 issue documents +
  `StockMove` outbound history · **deferred**
- **Statistical safety-stock and forecast-based sizing** — · seen in: NetSuite, D365, SAP · **already built**
  by SCM 4.7 on `ReorderRule` (five methods, `calculate()`/`apply_computed()`) → **park, link to
  `scm:reorderrule_list`**

### Bullet 3 — Goods Issue / Return to Stock ("internal consumption of stock or returning unused items")

- **Internal issue document that draws stock down for consumption** — SAP goods issue movement type **201**
  (to a cost centre) / **261** (to an order); Coupa's *inventory consumption*; Precoro's *Inventory
  Consumption*. · seen in: SAP, Coupa, Precoro, Fishbowl, D365 · **MUST** · spine: **new** header+line
  document; the stock effect goes through `scm.StockAdjustment` (see below) · buildable now
- **Charge the issue to a cost dimension** — SAP 201 requires a cost centre and derives the GL account via
  OBYC; Coupa consumption carries the account/segment. · seen in: SAP, Coupa, Oracle, D365 · **MUST** ·
  spine: `core.OrgUnit` + `accounting.GLAccount` (verified in use at `PurchaseRequisitions.py:47,164`);
  optionally a free-text project/work-order reference — **do not FK a work order**, `scm.WorkOrder` is 4.8's
  manufacturing object and a procurement issue is not a production draw · buildable now
- **Return unused stock back to a location (the mirror document)** — Precoro reverses a completed consumption
  by generating stock transfers back to the original warehouses; SAP has the 202/262 reversal pair. · seen in:
  Precoro, SAP, D365, Fishbowl · **MUST** · spine: same document with an `issue` / `return` type flag and a
  sign flip on the adjustment lines — one entity, not two · buildable now
- **Reservation before issue (set aside now, draw later)** — SAP MB21 reservations feed the 201/261 issue;
  D365 reservations. · seen in: SAP, D365, Oracle · **SHOULD** · spine: **`inventory.InventoryReservation`
  ALREADY EXISTS** (`InventoryReservations.py:37`, `purpose` includes job/project/other, with
  `release()/consume()/cancel()`) → **link out, never re-declare**; the issue document may carry an optional
  reference to it
- **Draft → approve/post → posted lifecycle, with cancellation by compensation** — Precoro (draft → completed,
  cancel spawns a return transfer); SAP (material document + reversal). · seen in: Precoro, SAP, Coupa,
  Fishbowl · **MUST** · spine: **new** STATUS CHOICES; the compensating-move discipline is already the repo's
  law (`StockMoves.py:5-7`) · buildable now
- **Availability guard: refuse to issue more than the location holds** — · seen in: SAP, D365, Fishbowl ·
  **MUST** · spine: reuse the shape of `_insufficient_stock()` (`apps/scm/views/_helpers.py:157`) — mirror it
  locally (the `resolve_line_item` precedent at `ReceiptTolerances.py:398-405`: peer apps do not import each
  other's internals) · buildable now
- **Issue slip / pick list print** — Fishbowl count sheets, SAP issue slips. · seen in: Fishbowl, SAP, D365 ·
  **COULD** · spine: a print template on the new document · buildable now (thin)
- **Value the issue at moving-average / FIFO cost** — · seen in: all ERP leaders · **SHOULD** ·
  spine: snapshot `scm.Item.average_cost` (`Items.py:105`) onto the line; `StockAdjustment.value_impact()`
  (`StockAdjustments.py:48`) already totals it · buildable now
- **Post the expense journal (issue → expense, return → credit)** — SAP OBYC, D365 posting profiles. ·
  seen in: SAP, D365, Oracle, NetSuite · **SHOULD** · spine: **accounting owns the ledger (L29)** and
  `scm.StockAdjustment` posts **no** `JournalEntry` today. 6.18 must NOT open a second posting path →
  **deferred**: show the value impact and the intended GL account; a real `accounting.JournalEntry` hand-off is
  a later pass co-ordinated with `inventory.GLPostRule` (`AccountingFinancialIntegration/GLPostRules.py:23`)
- **Consumption netted back against the PO that bought it** — Coupa updates the PO's consumed quantity. ·
  seen in: Coupa · **COULD** · spine: optional `scm.PurchaseOrder` FK on the issue header · **deferred**

### Bullet 4 — Warehouse Location Mapping ("tracking the exact bin, aisle, or rack of received goods")

- **Receipts land in a named receiving/staging location** — · seen in: all · **MUST** ·
  spine: **`scm.GoodsReceiptNote.location` ALREADY EXISTS** (`GoodsReceiptNotes.py:40`) → nothing to build
- **Bin / zone / warehouse hierarchy with a readable path** — · seen in: all · **MUST** ·
  spine: **`scm.Location` ALREADY IS the bin master** (`Locations.py:17-23`, `path()` at `:95`). **There is no
  `Bin` model and there must not be one** — a second bin table would fork the `StockMove` FK and the on-hand
  aggregate (the model's own docstring says so at `:38-40`)
- **Directed putaway: a suggested destination bin per arrival** — D365 location directives; Odoo putaway
  rules; Fishbowl/Manhattan slotting. · seen in: D365, Odoo, Fishbowl, Oracle · **MUST** ·
  spine: **`inventory.PutawayRule` + `resolve_putaway_suggestion()` ALREADY EXIST**
  (`PutawayRules.py:48,150`), and execution is `scm.PutawayTask` → **link out, do not rebuild**
- **"Where did MY received goods actually land?" — receipt-to-bin traceability** — the one thing a *buyer*
  needs and that no existing NavERP page answers: the GRN detail shows the staging location, not the final
  bin. · seen in: D365 (license plate → put location), SAP (storage location/bin on the material document),
  Fishbowl · **MUST** · spine: **DERIVED, no table** — `scm.StockMove` filtered on
  `reference = grn.number` (posted at `_helpers.py:328-330`, indexed at `StockMoves.py:60`), then the onward
  `scm.PutawayTask` rows for the same item/location · buildable now
- **License plate / handling unit as the receiving container** — · seen in: D365, SAP (HU), Manhattan ·
  **COULD** · spine: nothing exists; `scm.LotSerial` is the nearest concept but means something else ·
  **deferred** (a Module 5 WMS concern, not a buyer's)
- **Bin capacity / fullness at the destination** — · seen in: D365, Fishbowl, Odoo · **SHOULD** ·
  spine: **`inventory.BinCapacity` ALREADY EXISTS** (`BinCapacities.py:26`) plus `scm.Location.capacity`
  (`Locations.py:41`) → read/link only
- **Cross-dock straight from receiving to an outbound order** — · seen in: D365, Manhattan, Coupa ·
  **COULD** · spine: **`inventory.CrossDockOrder` ALREADY EXISTS** (`CrossDockOrders.py:47`) → link out
- **Item-to-bin fixed assignment / slotting by velocity** — · seen in: Fishbowl, D365, Odoo · **SHOULD** ·
  spine: `inventory.PutawayRule` (item/category tiers) + `scm.Location.abc_class`/`pick_sequence` →
  already covered, link out

### Bullet 5 — Cycle Count Integration ("scheduling and recording periodic inventory counts to reconcile system data")

- **Recurring count schedule (daily/weekly/monthly, by zone)** — Fishbowl, D365 cycle-count plans. ·
  seen in: all · **MUST** · spine: **`inventory.CountProgram` ALREADY EXISTS** (`CountPrograms.py:18`) →
  link out, never re-declare
- **ABC-class-driven count frequency** — D365 plans per ABC group; A counted most often. · seen in: D365,
  Fishbowl, NetSuite, Oracle · **MUST** · spine: **already built** — `CountProgram.abc_class` (`:47`) and
  `scm.Location.abc_class` (`Locations.py:46`) → link out
- **Count sheet with expected hidden (blind count)** — Fishbowl's report prints a blank quantity column. ·
  seen in: Fishbowl, D365, Manhattan · **MUST** · spine: **already built** —
  `CycleCountTaskLine.expected_quantity` is snapshotted server-side and `editable=False`
  (`CycleCountTasks.py:97-98`) → link out
- **Variance calculation and posting into one adjustment** — · seen in: all · **MUST** ·
  spine: **already built** — `CycleCountTask.adjustment` (`:48`) → exactly one
  `scm.StockAdjustment(reason='cycle_count')` → link out
- **Count-triggered thresholds (count when stock hits N or zero)** — D365 cycle-count thresholds. ·
  seen in: D365 · **COULD** · spine: would extend `inventory.CountProgram` → **belongs to 5.11**, park
- **Variance ROOT-CAUSE attribution, and feeding it back to the supplier** — the procurement-specific
  half: receiving is the origin of roughly a third of inventory variance, and the taxonomy the practitioners
  use is *receiving error / putaway error / picking error / supplier shortage / damage / data entry /
  shrinkage*. Nothing in NavERP records why a count differed. · seen in: cross-vendor accuracy practice, D365
  (reason codes), Manhattan · **SHOULD** · spine: **new, small** table over
  `scm.CycleCountTaskLine` + optional `scm.GoodsReceiptNote` / vendor `core.Party` · buildable now —
  the one honest reason for 6.18 to own a row in this bullet
- **Receiving-accuracy / count-compliance KPI view** — variance rate, counts completed vs scheduled, repeat
  offenders by SKU and by supplier. · seen in: D365, Manhattan, WMS practice · **SHOULD** ·
  spine: **DERIVED, no table** over `CycleCountTaskLine.variance` (`:108`) grouped by item/location and,
  where an attribution exists, by vendor · buildable now
- **Feeding the variance into a supplier scorecard** — · seen in: D365, Coupa, JAGGAER · **COULD** ·
  spine: `scm.SupplierScorecard` exists (`SupplierRelationshipManagement/SupplierScorecards.py:11`) →
  **belongs to 6.16**, park
- **Mobile/barcode counting** — Fishbowl, D365, Manhattan. · seen in: most · **COULD** ·
  spine: `inventory.ScanSession` / `BarcodeLabel` exist → integration/later, park to Module 5

### Beyond the bullets (found in the leaders, not in NavERP.md's 6.18 wording)

- **Requisition-from-stock / internal fulfilment before buying** — Coupa and Precoro let a requester pull from
  internal stock instead of raising a PR. · **SHOULD** · spine: the reverse of bullet 3's issue document — the
  same table with an `internal_request` origin · **deferred to a later pass** (needs a requester-facing flow)
- **Consignment / supplier-managed inventory** — Coupa tracks consigned stock and its ownership transfer. ·
  **COULD** · already parked here by 6.11 · **deferred**
- **Serial/lot capture at issue** — · **COULD** · `scm.LotSerial` exists; the issue line may carry the FK ·
  buildable now (optional field)
- **Multi-location transfer request raised from a shortage** — Oracle min-max can raise a transfer order. ·
  **COULD** · `scm.StockTransfer` exists → the suggestion's `transfer` source links to
  `scm:stocktransfer_create`, no new document · buildable now (link only)

---

## As-built reuse map — per bullet

| Bullet | READ / EXTEND (verified) | MUST NOT re-declare | New in 6.18 |
|---|---|---|---|
| **1. Stock Level Visibility** | `scm.StockMove` `StockMoves.py:13` · `scm.Item.on_hand()` `Items.py:197` · `scm.Location` `Locations.py:14` · `scm.PurchaseOrderLine` `PurchaseOrders.py:172` + `RECEIVABLE_STATUSES:34` · `scm.GoodsReceiptLine` `GoodsReceiptNotes.py:166` · `scm.PurchaseRequisitionLine` `PurchaseRequisitions.py:151` · `inventory.InventoryReservation` `InventoryReservations.py:37` · `inventory.StockStatus` `StockStatuses.py:18` · `scm.SalesOrderAllocation` `SalesOrderAllocations.py:15` · formula source `StockLevels.py:124` | Any on-hand/available **column**; any stock/reservation/classification table; the availability formula (reuse it, don't restate it differently) | **NOTHING — derived page only** |
| **2. Reorder Point Automation** | `scm.ReorderRule` `ReorderRules.py:26` (+ `on_hand_map:107`, `is_below_point:133`, `suggested_quantity:136`) · `scm.PurchaseRequisition(+Line)` `PurchaseRequisitions.py:14,151` · `core.Party` `Party.py:5` · `core.OrgUnit` `OrgUnit.py:5` · `accounting.Budget`/`GLAccount` · 6.15 `REQUESTED_PR_STATUSES`/`COMMITTED_PR_STATUSES` | `reorder_point`, `safety_stock`, `reorder_quantity`, `lead_time_days`, ABC/XYZ, the five safety-stock methods — **all on `ReorderRule`**; any second requisition model; `inventory:reorderdraft`'s PO-drafting path | **Policy + Run + Suggestion tables** |
| **3. Goods Issue / Return to Stock** | `scm.StockAdjustment(+Line)` `StockAdjustments.py:11,65` · `scm.Item.average_cost` `Items.py:105` · `scm.Location` · `scm.LotSerial` `LotSerials.py:5` · `core.OrgUnit` · `accounting.GLAccount` · `inventory.InventoryReservation` (optional link) · guard shape `_helpers.py:157` | **`StockMove` — never written from `apps/procurement`** (only `apps/scm/views` writes it); `StockAdjustment`; `StockTransfer`; `InventoryReservation`; any `JournalEntry` posting (L29) | **Issue/Return document + lines** |
| **4. Warehouse Location Mapping** | `scm.Location` (**is** the bin master) `Locations.py:14,17-23,38-48,95` · `scm.GoodsReceiptNote.location` `GoodsReceiptNotes.py:40` · `scm.StockMove.reference` `StockMoves.py:47` + posting at `_helpers.py:328-330` · `scm.PutawayTask` `PutawayTasks.py:16` · `inventory.PutawayRule` + `resolve_putaway_suggestion` `PutawayRules.py:48,150` · `inventory.BinCapacity` `BinCapacities.py:26` | **A `Bin`/`Zone`/`Aisle`/`Rack` model — categorically** (bins are `Location(location_type='bin')`); putaway rules; putaway tasks; bin capacity | **NOTHING — derived page only** |
| **5. Cycle Count Integration** | `scm.CycleCountTask(+Line)` `CycleCountTasks.py:16,90` (blind snapshot `:97-98`, `variance:108`, `adjustment:48`) · `inventory.CountProgram` `CountPrograms.py:18` (+ `generate_tasks():85`) · `inventory.PhysicalInventory` `PhysicalInventories.py:31` · `scm.GoodsReceiptNote` · `core.Party` | The count task, the count line, the schedule/cadence, the blind-count rule, the adjustment posting — **all already built**; `scm.SupplierScorecard` (that's 6.16) | **Optional small variance-attribution table + a derived accuracy page** |

---

## Recommended build scope (this pass)

Backend package `apps/procurement/models|forms|views|urls/InventoryWarehouseIntegration/`;
templates `templates/procurement/inventorywarehouse/<entity>/{list,detail,form}.html`.
All models inherit `apps.procurement.models._base.TenantOwned` / `TenantNumbered` (`_base.py:44,57`);
every view filters `tenant=request.tenant`.

**Three entities are the primary scope; a fourth is optional and lowest priority.**

### 1. `ReplenishmentPolicy` — *no number prefix* (plain configuration)
> The procurement-side overlay on `scm.ReorderRule`: **who** to buy from, **how much** to round to, and
> **what defaults** the generated requisition carries. Deliberately unnumbered — it is read by the run, not
> referenced by other documents (the `inventory.PutawayRule` / `procurement.ReceiptTolerancePolicy` /
> `SpendClassificationRule` precedent).

- **FKs (by string):** `core.Tenant` · `scm.Item` (PROTECT) · `scm.Location` (SET_NULL, null → "any
  location") · `core.Party` `preferred_vendor` (SET_NULL, null OK — filtered to the supplier `PartyRole`) ·
  `core.OrgUnit` `default_org_unit` (SET_NULL) · `accounting.Budget` `default_budget` (SET_NULL) ·
  `accounting.GLAccount` `default_gl_account` (SET_NULL)
- **Fields / CHOICES driven by the research:**
  - `source_method` — `buy` | `transfer` | `manufacture` (Odoo *Preferred Route*, Oracle/D365 supply type).
    Only `buy` generates a requisition this pass; the others render a link-out.
  - `trigger_mode` — `review` (default) | `auto` (Odoo *Trigger* Manual/Auto; the human gate stays default,
    matching `ReorderRule.apply_computed()`'s "calculate proposes, a person accepts")
  - `target_level` — nullable **order-up-to** override (NetSuite *Preferred Stock Level*, Precoro *Reorder
    To*, Odoo *Max Quantity*). Null ⇒ fall back to `ReorderRule.reorder_point + safety_stock`. Documented as
    an override, never a copy.
  - `order_multiple` (Odoo *Multiple Quantity*), `min_order_qty`, `max_order_qty` — nullable
  - `include_on_order` — bool, default **True** (Oracle min-max: on-hand **+ on-order** vs. the point; closes
    the duplicate-PR gap in `ReorderRule.is_below_point()`)
  - `include_open_requisitions` — bool, default True (SAP MD04 counts PRs as supply)
  - `lead_time_days_override` — nullable (Cin7 per-supplier lead time; else `ReorderRule.lead_time_days`)
  - `is_active`, `notes`
- **Meta:** `unique_together = ("tenant", "item", "location")` — same grain as `ReorderRule`
- **Serves:** bullet 2 (and supplies the vendor/expected-date columns bullet 1's page shows)
- **`clean()`:** cross-tenant rejection on every FK; `max_order_qty ≥ min_order_qty`;
  `preferred_vendor` must hold a supplier `PartyRole`

### 2. `ReplenishmentRun` `[RPL-]` + `ReplenishmentSuggestion` (child, one entity file)
> The batch proposal Oracle/Odoo/Cin7/D365 all produce: a dated run over the tenant's active reorder rules
> that **persists** its suggestion lines with their inputs snapshotted, lets a buyer accept / snooze /
> dismiss each, and releases the accepted ones into `scm.PurchaseRequisition`s grouped by vendor.
> Neither `scm:reorder_alerts` nor `inventory:reorderdraft` persists anything — this is the gap.

- **`ReplenishmentRun` FKs:** `core.Tenant` · `scm.Location` (SET_NULL, null = whole network) ·
  `AUTH_USER_MODEL` `generated_by` (SET_NULL)
- **Run fields:** `run_date` · `trigger` = `manual` | `scheduled` · `status` = `draft` | `proposed` |
  `released` | `cancelled` · `abc_class_filter` (blank/A/B/C — D365 plans per ABC group) ·
  `notes` · `generated_at`/`released_at` (`editable=False`)
- **`ReplenishmentSuggestion` FKs:** `ReplenishmentRun` (CASCADE, `related_name="lines"`) · `scm.Item`
  (PROTECT) · `scm.Location` (PROTECT) · `scm.ReorderRule` (SET_NULL, nullable) · `ReplenishmentPolicy`
  (SET_NULL, nullable) · `core.Party` `vendor` (SET_NULL, nullable — the policy's preferred vendor,
  overridable per line) · `scm.PurchaseRequisition` (SET_NULL, `editable=False`, stamped on release)
- **Suggestion fields — every snapshot `editable=False`** (the `CycleCountTaskLine.expected_quantity`
  precedent at `CycleCountTasks.py:97-98`):
  `on_hand_qty` · `allocated_qty` · `on_order_qty` · `open_requisition_qty` · `available_qty` ·
  `reorder_point_snapshot` · `target_level_snapshot` · `raw_suggested_qty` · `suggested_qty` (after
  multiple/min/max rounding) · `lead_time_days` · `unit_cost` (from `Item.standard_cost`) ·
  `line_value` (derived) · `decision` = `pending` | `accepted` | `snoozed` | `dismissed` ·
  `snooze_until` (nullable date — Odoo *Snooze*) · `decision_note`
- **Actions:** `generate()` (compute lines in **grouped queries** — reuse `ReorderRule.on_hand_map()` and the
  `_on_order_map()` shape; never a per-row aggregate) · per-line accept/snooze/dismiss ·
  `release()` → one `scm.PurchaseRequisition` per vendor, lines written free-text
  (`item_description=item.name`, `sku_hint=item.sku`, `uom_hint=item.uom.code`, `quantity`,
  `estimated_unit_price`, `gl_account`), header carrying the policy's `org_unit`/`budget`, then
  `recalc_totals()`; `select_for_update()` on the run so a double-clicked Release cannot raise two PRs
- **Serves:** bullet 2 (primary) and bullet 1 (its snapshot columns are the buyer stock position, persisted)

### 3. `MaterialIssue` `[MIS-]` + `MaterialIssueLine` (child, one entity file)
> SAP's 201/261 goods issue and Precoro/Coupa's inventory consumption, plus the return-to-stock mirror.
> **Posting mints a draft `scm.StockAdjustment` + lines and stores it on `adjustment` (`editable=False`);
> the actual `StockMove` is written by SCM's own post action.** This is the `CountProgram.generate_tasks()`
> bridge pattern (`CountPrograms.py:85-125`) and it is what keeps "one way for stock to change".

- **FKs:** `core.Tenant` · `scm.Location` (PROTECT — issue FROM / return TO) · `core.OrgUnit` (SET_NULL —
  the cost dimension, SAP 201) · `accounting.GLAccount` (SET_NULL — expense account, header default) ·
  `AUTH_USER_MODEL` `requested_by` / `issued_by` (SET_NULL) · `scm.StockAdjustment` (SET_NULL,
  `editable=False` — provenance, the `CycleCountTask.adjustment` precedent at `CycleCountTasks.py:48`) ·
  optional `inventory.InventoryReservation` (SET_NULL — the reservation being consumed, SAP MB21→MB1A)
- **Header fields:** `movement_type` = `issue` | `return` · `purpose` = `cost_centre` | `project` |
  `work_order` | `maintenance` | `sample` | `other` (SAP's 201/261 split, generalised) ·
  `reference` (free text — project/job/WO number; **no FK to `scm.WorkOrder`**, that is 4.8's production
  object) · `issue_date` · `status` = `draft` | `submitted` | `posted` | `cancelled`
  (`EDITABLE_STATUSES = ("draft",)`) · `posted_at`/`cancelled_at` (`editable=False`) · `notes`
- **Line fields:** `scm.Item` (PROTECT) · `scm.LotSerial` (SET_NULL, nullable) · `quantity`
  (`MinValueValidator(0.0001)`) · `unit_cost` (snapshot of `Item.average_cost`, `editable=False`) ·
  `gl_account` (SET_NULL — per-line override) · `notes`
- **Guards:** on post, an issue must not exceed the location's derived on-hand (mirror
  `_insufficient_stock()`'s shape locally — do not import `apps.scm.views._helpers`);
  `select_for_update()` on the header; cancellation after posting is refused (correct it with the mirror
  document, never by deleting)
- **Derived:** `total_value` = Σ qty × unit_cost, shown beside the adjustment's own `value_impact()`
- **Serves:** bullet 3

### 4. *(optional, lowest priority)* `CountVarianceReview` `[CVR-]`
> Why a counted variance happened, and whether it traces to receiving. Attaches to one
> `scm.CycleCountTaskLine` and, when the cause is receiving, to the `scm.GoodsReceiptNote` and vendor —
> the hand-off 6.16 will consume.

- **FKs:** `core.Tenant` · `scm.CycleCountTask` (PROTECT) + `scm.CycleCountTaskLine` (CASCADE) ·
  `scm.GoodsReceiptNote` (SET_NULL, nullable) · `core.Party` `vendor` (SET_NULL, nullable) ·
  `AUTH_USER_MODEL` `reviewed_by`
- **Fields:** `root_cause` = `receiving_error` | `putaway_error` | `picking_error` | `supplier_shortage` |
  `damage` | `data_entry` | `shrinkage` | `unknown` · `variance_qty` (snapshot, `editable=False`) ·
  `variance_value` (`editable=False`) · `supplier_attributable` (bool) · `corrective_action` (text) ·
  `status` = `open` | `actioned` | `closed`
- **Serves:** bullet 5 · **Drop this first if the pass gets heavy** — bullet 5 still has a derived page.

### Bullets served by DERIVED, read-only pages (no model, no migration)

| Page | Bullet | What it reads | Why no table |
|---|---|---|---|
| **Buyer Stock Position** (`procurement:stock_position`) — item-first rows: on-hand · available · reserved · **on-order (qty + earliest expected date + vendor + PO number)** · **open requisition qty** · reorder point · days of cover · a "Raise requisition" action | **1** | `scm.StockMove` (one GROUP BY) · `scm.PurchaseOrderLine`/`GoodsReceiptLine` (the `_on_order_map()` two-query shape) · `scm.PurchaseRequisitionLine` · `inventory.InventoryReservation` · `inventory.StockStatus` · `scm.SalesOrderAllocation` · `scm.ReorderRule` | Every column is an aggregate over rows other modules own (L36). Storing any of them is a second source of truth for on-hand (`StockMoves.py:5-7`). Distinct from `inventory:stocklevels` by the PO date/vendor, the open-PR column and the days-of-cover column. |
| **Received Goods Location Map** (`procurement:receipt_bin_map`) — per GRN: staging location, the bins its stock actually reached, `Location.path()`, quantity per bin, the putaway task that moved it, and an "unputaway" flag when stock is still sitting in staging | **4** | `scm.GoodsReceiptNote(.location)` · `scm.StockMove` filtered `reference=grn.number` (indexed `StockMoves.py:60`) · `scm.PutawayTask` · `scm.Location.path()` · `inventory.BinCapacity` (fullness badge) | The bin **is** `scm.Location`; the receipt→bin link **is** `StockMove.reference`. A mapping table would be a copy of the ledger. |
| **Count Accuracy & Variance** (`procurement:count_accuracy`) — variance rate, counts completed vs scheduled, top variance SKUs/locations, repeat offenders, and (when entity 4 ships) variance split by root cause and by vendor | **5** | `scm.CycleCountTask`/`Line` (`variance:108`) · `inventory.CountProgram` · `scm.StockAdjustment` · optional `CountVarianceReview` | Counting is built end-to-end in 4.4 + 5.11; the procurement value is the read-out and the supplier attribution. |

### Suggested `LIVE_LINKS["6.18"]` (one entry per NavERP.md bullet, no plumbing)
```
"Stock Level Visibility"        -> procurement:stock_position          (derived)
"Reorder Point Automation"      -> procurement:replenishmentrun_list   (RPL- runs; policy register linked from it)
"Goods Issue/Return to Stock"   -> procurement:materialissue_list      (MIS-)
"Warehouse Location Mapping"    -> procurement:receipt_bin_map         (derived)
"Cycle Count Integration"       -> procurement:count_accuracy          (derived; links out to scm:cyclecounttask_list + inventory:countprogram_list)
```
`ReplenishmentPolicy` gets **no** sidebar key — it is configuration behind an analysis page, reached from the
run list (the `ReceiptTolerancePolicy` / `SpendClassificationRule` / `ReorderRule` precedent documented at
`navigation.py:1633-1648`).

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Count variance → **supplier scorecard / KPI / benchmarking** → **6.16** (`scm.SupplierScorecard` exists)
- Rejection/discrepancy rates, receipt tolerances, inspection, return **to vendor** → **6.12**
  (`ReceiptDiscrepancy`, `ReceiptTolerancePolicy`, `ReturnToVendor` — all built).
  *Return **to stock** (this sub-module) and return **to vendor** (6.12) are different documents; say so on
  the page so nobody files one as the other.*
- Budget availability on the generated requisition, commitment accounting → **6.15** (`BudgetMapping`,
  `budget_availability`) — 6.18 only sets the `budget`/`org_unit` defaults so 6.15's check can run
- Requisition approval routing on the generated PR → **6.3** (`ApprovalRoutingRule`, `RequisitionApproval`)
- Converting the requisition to a PO → **6.10** (`generate_po_from_requisition`)
- In-transit/ASN arrival detail → **6.11** (`AdvancedShipmentNotice`, `Backorder`, `DeliverySchedule`)
- Contract/catalog price on the suggested line → **6.8 / 6.9** (`CatalogItem`, `CatalogPriceTier`)
- Bin capacity envelopes, cross-dock, putaway **rules**, count **programs**, physical inventory, stock
  statuses, reservations, barcode/RFID → **Module 5** (all built: `BinCapacity`, `CrossDockOrder`,
  `PutawayRule`, `CountProgram`, `PhysicalInventory`, `StockStatus`, `InventoryReservation`, `BarcodeLabel`)
- Safety-stock calculation, ABC/XYZ classing, seasonality, demand forecasting → **SCM 4.7**
  (`ReorderRule.calculate()`, `DemandForecast`, `SeasonalityProfile`)
- Putaway/pick/count **execution**, yard, slotting → **SCM 4.4** (`PutawayTask`, `PickTask`,
  `CycleCountTask`, `YardVisit`)
- Item/UOM/category/lot masters, stock adjustments, transfers, valuation → **SCM 4.3**
- Landed cost on received goods → **SCM 4.18** (`LandedCostVoucher`)
- Consigned / vendor-managed inventory → parked here by 6.11; still parked (needs an ownership dimension
  neither `scm.Item.owner_client` nor `StockMove` provides)

---

## Deferred (later passes / integrations)

- **Journal posting for issues/returns (issue → expense, return → credit).** Accounting owns the ledger
  (L29) and `scm.StockAdjustment` posts no `JournalEntry` today. 6.18 shows the GL account and the value
  impact; the real hand-off is a later pass co-ordinated with `inventory.GLPostRule`
  (`AccountingFinancialIntegration/GLPostRules.py:23`). Opening a second posting path here would be the
  worst possible outcome of this sub-module.
- **Scheduled replenishment runs (cron/Celery).** The `trigger` column and a management command ship; the
  scheduler does not — same posture as `CountProgram.is_due()`.
- **Low-stock email/notification digests** (Precoro's daily reminder). Reuse `procurement.ProcurementAlert`
  in-app now; email delivery is integration/later.
- **Inline stock check on the requisition/PO entry form.** High value, but it edits 6.2/6.10 forms; 6.18
  should not touch another sub-module's templates in this pass.
- **License plates / handling units** at receiving (D365, SAP HU) — no concept exists in the spine, and it is
  a Module 5 WMS concern rather than a buyer's.
- **Item→vendor catalog price on the suggestion line** — should read 6.9 `CatalogItem`/`CatalogPriceTier`
  rather than `Item.standard_cost`; deferred to keep this pass's query count flat.
- **`sku_hint` free-text matching.** Every item-level join from a PO/PR line goes through exact-string
  `sku_hint ↔ Item.sku` (`_resolve_grn_item` `_helpers.py:279`, `resolve_line_item`
  `ReceiptTolerances.py:398`, `_on_order_map` `StockLevels.py:37`). 6.18 must mirror that helper locally and
  **report unmatched lines honestly** rather than guessing. The real fix is an `item` FK on the spine line
  models — a spine migration, not a 6.18 one.
- **Consumption-driven (pull) replenishment** from the new issue history — becomes possible once
  `MaterialIssue` has run for a period; not this pass.
- **Requisition-from-stock / internal fulfilment** (Coupa, Precoro) — the requester-facing mirror of the
  issue document.
- **`CountVarianceReview`** if the pass runs long — bullet 5 is still served by the derived accuracy page
  plus link-outs to the fully built `scm.CycleCountTask` / `inventory.CountProgram`.

---

## Non-goals (explicit — these would duplicate scm/inventory)

1. **No `StockMove` writes from `apps/procurement`.** Verified: only `apps/scm/views/` writes the ledger in
   production code; Module 5 states the rule (`PutawayRules.py:17-18`). 6.18 mints a draft
   `scm.StockAdjustment` and lets SCM post it.
2. **No second on-hand/quantity column anywhere.** On-hand is `Sum(StockMove.quantity)`, always
   (`StockMoves.py:5-7`, `Items.py:9-12`).
3. **No `Bin` / `Zone` / `Aisle` / `Rack` model.** A bin is `scm.Location(location_type='bin')`
   (`Locations.py:17-23,38-40`).
4. **No second reorder-point / safety-stock / lead-time home.** Those live on `scm.ReorderRule`
   (`ReorderRules.py:43-66`); `ReplenishmentPolicy` adds only what is missing and overrides explicitly.
5. **No second requisition or purchase-order model.** Write into `scm.PurchaseRequisition` /
   `scm.PurchaseOrder` (`_base.py:11-17`).
6. **No second cycle-count task, count line, count schedule or blind-count mechanism.** `scm.CycleCountTask`
   + `inventory.CountProgram` are built; 6.18 reads them.
7. **No second reservation or stock-classification table.** `inventory.InventoryReservation` /
   `inventory.StockStatus` are built.
8. **No second putaway rule engine or bin-capacity table.** `inventory.PutawayRule` +
   `resolve_putaway_suggestion` and `inventory.BinCapacity` are built.
9. **No `JournalEntry` / ledger posting.** `apps/accounting` owns the financial ledger (L29).
10. **No vendor/customer/employee table.** They are `core.PartyRole`s on `core.Party` (`Party.py:5`).
11. **No duplicate of `inventory:stocklevels` or `inventory:reorderdraft`.** The 6.18 stock page is
    buyer-angled (PO date/vendor, open PRs, days of cover) and the 6.18 replenishment run targets
    **requisitions** through approval + budget, not draft POs.

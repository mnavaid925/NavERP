# Research — Sub-module 4.3: Inventory Management (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **LIVE_LINKS built so far in module 4:** `"4.1"` (Purchase Requisition, RFQ, PO Management, Vendor Portal,
  Invoice Reconciliation) and `"4.2"` (Supplier Onboarding, Supplier Scorecard, Contract Management, Supplier
  Catalog Management, Risk Management) — `apps/core/navigation.py` lines 770–789. `"4.3"` has no entry yet,
  confirming it is the next unbuilt sub-module in Module 4.
- **`apps/scm/` as-built structure** (verified via glob): two sub-module packages exist —
  `models/ProcurementManagement/` (`PurchaseRequisition`+`PurchaseRequisitionLine`, `RFQ`+`RFQLine`+`RFQVendor`,
  `RFQQuote`+`RFQQuoteLine`, `PurchaseOrder`+`PurchaseOrderLine`, `GoodsReceiptNote`+`GoodsReceiptLine`) and
  `models/SupplierRelationshipManagement/` (`SupplierProfile`, `SupplierScorecard`, `SupplierContract`,
  `SupplierCatalog`+`SupplierCatalogItem`, `SupplierRiskAssessment`). 4.3 adds a third package,
  `models/InventoryManagement/`.
- **Spine entities verified NOT to exist anywhere** (`grep -rn "^class (Item|UOM|Location|StockMove|LotSerial|
  ItemCategory)\b" apps/` → no matches). This confirms the task brief's premise: 4.3 is the first sub-module
  that actually needs them, and per the **L36 precedent already set by 4.1** (SCM shipped `PurchaseRequisition`/
  `RFQ`/`PurchaseOrder`/`GoodsReceiptNote` even though `NavERP-ERD.md` line 468 assigns them to Module 6 —
  "the module that ships FIRST owns the shared entity, the later module EXTENDS by FK, never re-declares"), the
  same override applies here: `NavERP-ERD.md` line 467 assigns `Item`/`ItemCategory`/`UOM`/`Location`/
  `LotSerial`/`StockMove` to Module 5 (Inventory/IMS), but SCM 4.3 ships first, so **SCM builds and owns the
  spine now**. Module 5's future research/todo must extend `scm.*` by FK, not re-declare — see "Belongs to
  sibling sub-modules" below.
- **`NavERP-ERD.md` line 467 also lists `GoodsReceipt, StockAdjustment, StockTransfer, CycleCount, ReorderRule`**
  as Module 5's own "Adds." `GoodsReceipt` is **already built** as `scm.GoodsReceiptNote` (4.1) — a second,
  pre-existing L36 conflict. `StockAdjustment`/`StockTransfer`/`ReorderRule` are exactly this pass's domain
  models — SCM 4.3 ships them now too, leaving only `CycleCount` (scheduled physical counting — arguably 4.4
  WMS territory, see Belongs-to-sibling) and `PriceList` as Module 5's genuinely new pieces once it's reached.
  **Flag for whoever writes Module 5's `research-inventory.md`:** reconcile the ERD row for both modules in the
  same pass (per lesson L36 rule 2) — Module 5's "Adds" column should shrink to `CycleCount`, `PriceList`
  (+ whatever genuinely-new Module-5-only capability it adds), not the six spine tables or the three domain
  tables this pass ships.
- **`scm.GoodsReceiptNote` (4.1) already anticipates the StockMove hook** — its docstring reads *"There is no
  `StockMove` posting here: `core.StockMove` does not exist yet (it lands with Module 5 Inventory, lesson L28).
  When it does, `mark_received` is the hook that should post the inventory effect inside
  `transaction.atomic()`."* That comment is now stale in two ways (StockMove lands in `scm`, not Module 5; and
  it now exists) — **do not retrofit 4.1 in this pass**, but flag the docstring update + the actual
  `mark_received`→`StockMove` wiring as the first concrete follow-up once 4.3 ships (see Deferred).
- **`apps/scm/models/_base.py`** confirms the reusable pattern this pass follows: `TenantOwned` (tenant FK +
  timestamps, `related_name="+"`) and `TenantNumbered` (adds an auto-assigned `number` via `NUMBER_PREFIX` +
  `next_number()`, retry-on-collision). Master-data models (no natural "document number") use `TenantOwned`
  directly — the precedent is 4.2's `SupplierProfile`. Transactional models use `TenantNumbered`.
- **Verified-existing spine to reuse:** `core.Party` (`apps/core/models/Party.py`) +`PartyRole` (roles include
  `supplier`/`vendor`), `core.Document` (generic attachment), `core.OrgUnit`; `accounting.Currency` (global, no
  tenant FK — `apps/accounting/models/GeneralLedger/Currencies.py`), `accounting.GLAccount`,
  `accounting.JournalEntry`/`JournalLine` (`apps/accounting/models/GeneralLedger/JournalEntries.py` —
  confirms the "two universal ledgers" pattern: `JournalEntry`/`JournalLine` use **signed debit/credit** amounts
  and a plain-text `reference` field for source traceability, not a generic `content_type`/`object_id` FK — this
  is the concrete precedent `StockMove` should mirror, see below). `scm.PurchaseOrder`/`PurchaseOrderLine`,
  `scm.GoodsReceiptNote`/`GoodsReceiptLine`, `scm.PurchaseRequisition`/`PurchaseRequisitionLine` (4.1 — all use
  free-text `item_description`/`sku_hint`/`uom_hint` line fields, confirmed by grep — the exact fields that a
  future migration can backfill onto a real `item→scm.Item` FK now that 4.3 finally builds `Item`).
- **Sibling research files read:** `research-scm.md` (module-wide orientation; explicitly deferred all of 4.3
  to "later," correctly predicted `core.Item`/`UOM`/`Location`/`StockMove` would land here) and
  `research-scm-4.2.md` (confirms the `_supplier_parties(tenant)` helper in `scm/forms/_common.py`, the
  `core.Document` generic-attachment reuse pattern, and the L29/L36 ships-first precedent this file continues).

## Leaders surveyed (with source links)

1. **Oracle NetSuite Inventory Management / Advanced Inventory** — enterprise ERP-native inventory; lot/serial
   traceability from receipt to shipment, bin management with sub-location precision, reorder points computed
   from sales velocity + seasonality + supplier lead time —
   [NetSuite Inventory Management guide](https://www.brokenrubik.com/blog/netsuite-inventory-management-guide),
   [Advanced Bin/Numbered Inventory Management](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2271791.html)
2. **Oracle Inventory Cloud (Fusion SCM)** — min-max planning at the *organization or subinventory* level,
   order modifiers (fixed lot multiple, minimum order quantity) feeding the reorder-quantity calculation —
   [Min-Max Planning](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26c/famml/min-max-planning.html)
3. **Odoo Inventory** — removal strategies (FIFO/LIFO/FEFO/nearest-location), warehouse "routes" built from
   rules (buy/manufacture/resupply-between-warehouses), reordering rules with min/max quantities, valuation
   methods (FIFO/Average/LIFO/Standard) for perpetual or periodic costing —
   [Odoo Inventory features](https://www.odoo.com/app/inventory-features),
   [Removal strategies](https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/routes/strategies/removal.html)
4. **Zoho Inventory** — batch tracking (manufacture/expiry dates, defect traceback to batch), serial-number
   tracking with full transaction-history trace, stock adjustments that resolve to specific serials/batches,
   transfer orders that let a user pick specific serials/batches to move —
   [Batch Tracking](https://www.zoho.com/us/inventory/help/advanced-inventory-tracking/batch-tracking.html),
   [Transfer Orders](https://www.zoho.com/us/inventory/help/warehouses/transfer-orders.html),
   [Inventory Adjustments](https://www.zoho.com/us/inventory/help/items/inventory-adjustments.html)
5. **Cin7 Core** — FIFO/FEFO costing method choice per product, low-stock reorder points settable *per total
   product* or *per location*, stock adjustments split into plain quantity corrections vs. a distinct
   "revaluation" adjustment type (writes off then re-enters at a new cost) —
   [Costing Methods](https://help.core.cin7.com/hc/en-us/articles/9034464614415-Costing-Methods),
   [Low stock reorder](https://help.core.cin7.com/hc/en-us/articles/9034475105167-Low-stock-reorder),
   [Stock adjustment and revaluation](https://help.core.cin7.com/hc/en-us/articles/9034574097039-Stock-adjustment-and-revaluation)
6. **Fishbowl Inventory** — tracking by serial, lot, batch, revision level, and expiration date in one item
   configuration; multi-warehouse transfer tracking with consolidated stock visibility; mobile-scanned
   receiving/put-away/cycle-count/adjustment workflow —
   [Fishbowl Warehouse](https://www.fishbowlinventory.com/products/fishbowl-warehouse),
   [Purchasing](https://www.fishbowlinventory.com/purchasing)
7. **Katana MRP** — reorder points per raw material/finished-product variant with immediate low-stock alerts,
   and **auto-generation of a draft purchase order** (correct supplier, quantity, price) the moment an item
   crosses its reorder point — the clearest "Reorder Point Automation" precedent surveyed; batch/lot tracking
   from supplier lot through production to the customer —
   [Automated Inventory Management](https://katanamrp.com/inventory-management-software/automated/),
   [Purchase order management](https://katanamrp.com/features/purchasing/)
8. **Unleashed Software** — perpetual **average landed cost** updated instantly on every transaction (folds in
   freight/duty/labor), warehouse transfers between unlimited locations, manual stock adjustments for
   write-offs, low/high stock alerts —
   [Inventory Management](https://www.unleashedsoftware.com/en-us/product/inventory-management-software/)
9. **inFlow Inventory** — per-location reorder settings that can auto-*transfer* stock from a central warehouse
   (not just trigger a purchase) when a satellite location drops below its point; lot tracking with a
   dedicated "movement history" tab per lot showing every order it was assigned to —
   [Transfer stock between locations](https://www.inflowinventory.com/support/cloud/how-do-i-transfer-stock-between-locations),
   [Reordering](https://ww2.inflowinventory.com/support/cloud/everything-you-need-to-know-about-improved-reordering/),
   [Lot numbers & expiry dates](https://www.inflowinventory.com/support/cloud/lot-numbers-and-expiry-dates-beta)
10. **Sortly** — SMB/mobile-first inventory tracking; barcode/QR generation and scan-based check-in/check-out,
    location-as-folder-hierarchy (warehouse → truck → job site), quantity-threshold low-stock alerts, "move
    summary" reports of location changes over a period — the low end of the market, useful as the floor for
    what "table-stakes" stock control looks like even without lot/serial —
    [Barcode Inventory Software](https://www.sortly.com/barcode-inventory-system/)

*(10 surveyed — matches the task's suggested list closely: NetSuite, Cin7, Zoho, Katana, Odoo, Fishbowl,
Unleashed, inFlow, Sortly, plus Oracle Inventory Cloud in place of SAP EWM, which is a warehouse-execution
product whose distinct capabilities — wave picking, slotting — belong to 4.4 WMS, not 4.3.)*

## Feature catalog (this sub-module only)

### Stock Control (real-time quantities, batch numbers, serial numbers)
- **Real-time on-hand quantity, derived (never a stored editable field)** — matches the mandated spine rule
  verbatim, and is exactly how NetSuite/Odoo/Zoho/Cin7 all present "current stock" (a live sum of movements, not
  an editable counter) · seen in: **all 10** · priority: **table-stakes** · spine: `Sum(StockMove.quantity)`
  grouped by `(item, location[, lot_serial])` — new table `StockMove` (append-only) · buildable now
- **Batch/lot tracking** — group a receipt as a batch, capture manufacture/expiry date, trace defects back to
  the batch · seen in: Zoho (batch tracking + defect traceback), Fishbowl (batch + revision level), Katana
  (supplier-lot → production-batch → customer), inFlow (lot movement-history tab) · priority: **table-stakes**
  for lot-tracked industries, common overall · spine: new table `LotSerial` (`tracking_type=lot`) ·
  buildable now
- **Serial number tracking** — unique per-unit identity, full transaction-history trace · seen in: Zoho, NetSuite
  (mandatory for food/pharma/electronics recall compliance), Fishbowl, inFlow · priority: **table-stakes** ·
  spine: same `LotSerial` table (`tracking_type=serial`), one row per unit · buildable now
- **Per-item costing-method flag driving how the item is tracked/valued** (stockable vs. service, FIFO vs. LIFO
  vs. weighted-average vs. standard) · seen in: Odoo, Cin7, DOSS · priority: **table-stakes** · spine: fields on
  `Item` (`item_type`, `costing_method`) · buildable now
- **Unit of measure with a base/conversion factor** (stock in "each," purchase in "box of 12") · seen in: all
  major ERPs generally (NavERP-ERD's own `UOM_CONVERSION` design intent) · priority: common · spine: new table
  `UOM` with a self-referencing `base_uom` + `conversion_factor` (a light version of the full N:N conversion
  matrix the ERD sketches — sufficient for one stocking UOM per item this pass) · buildable now
- **Item categorization / hierarchy** — group items, inherit default costing method or GL mapping · seen in:
  Odoo (product categories), Cin7, NetSuite · priority: common · spine: new table `ItemCategory`
  (self-referencing `parent`) · buildable now
- **Barcode / SKU capture and scan-based lookup** · seen in: Sortly (barcode-first), Zoho, Fishbowl (mobile
  scanning) · priority: common · spine: `barcode`/`sku` fields on `Item`; the scan-*hardware* interaction itself
  is a later mobile/PWA concern · buildable now (fields), integration/later (actual scanner UX)
- **Multi-location on-hand breakdown** (same item, quantity per warehouse) · seen in: **all 10** · priority:
  **table-stakes** · spine: `StockMove.location` FK, aggregate `group by location` — no separate "on-hand" table
  · buildable now
- **Stock status/quarantine state on a lot** (active/quarantined/expired/consumed) — a light quality gate on a
  batch, short of a full QMS · seen in: NetSuite (recall exposure), Katana (batch quality issues) · priority:
  common · spine: `status` field on `LotSerial` · buildable now

### Warehouse Transfer (stock movement between locations)
- **Transfer between two named locations with a status lifecycle** (draft → in-transit → completed/cancelled) ·
  seen in: Zoho (Transfer Orders), Fishbowl (inter-location transfers), Unleashed (warehouse transfers), inFlow
  (Transfer Stock) · priority: **table-stakes** · spine: new table `StockTransfer` (`from_location`,
  `to_location→Location`) + `StockTransferLine`; posting creates a paired `StockMove` out at `from_location` /
  in at `to_location` per line · buildable now
- **Transfer at the batch/serial level** — pick specific lots or serials to move, not just a bare quantity ·
  seen in: Zoho (select serial numbers / select batch numbers under the transfer's line quantity) · priority:
  common · spine: `StockTransferLine.lot_serial→LotSerial` (nullable — only required for lot/serial-tracked
  items) · buildable now
- **In-transit state distinct from completed** — stock is deducted from the source before it's confirmed
  received at the destination · seen in: Zoho, Fishbowl · priority: common · spine: `StockTransfer.status`
  choice (`draft/in_transit/completed/cancelled`); the *paired* `StockMove` posting happens at completion in
  this pass (a two-step "ship then receive" is a legitimate later refinement, noted in Deferred) · buildable
  now (single-step completion), deferred (two-step ship/receive split)
- **Auto-transfer suggestion between locations driven by a reorder shortfall** — a satellite location's low
  stock triggers a transfer from a central warehouse instead of a new purchase · seen in: inFlow (reorder
  settings can trigger a transfer, not just a PO) · priority: **differentiator** · spine: `ReorderRule` could in
  principle target an internal `Location` as its "source" instead of an external `Party` vendor — flagged as a
  natural v2 enhancement, not required this pass (the bullet asks for PO generation, not transfer generation) ·
  deferred
- **Removal/picking strategy at the transfer/consumption level (FIFO/LIFO/FEFO/nearest-location)** · seen in:
  Odoo (named removal strategies, including FEFO for expiring lots) · priority: differentiator · spine: the
  `Item.costing_method` already governs *valuation*; which *physical* lot gets picked first (a distinct
  operational concern) is a WMS-grade picking strategy — see Belongs to sibling below · deferred to 4.4 WMS

### Stock Adjustment (write-offs, damages, cycle-count corrections)
- **Adjustment header with a reason code and a status lifecycle** (draft → posted → cancelled) matching the
  bullet's named reasons (write-off, damage, cycle-count correction) · seen in: Cin7 (adjustment reasons: new
  stock, damaged/stolen, data-entry error), Zoho (adjustment types), Unleashed (manual adjustment for write-offs)
  · priority: **table-stakes** · spine: new table `StockAdjustment` [`ADJ-`] (`reason` choice field) +
  `StockAdjustmentLine`; posting creates one signed `StockMove` per line at the adjustment's `location` ·
  buildable now
- **System quantity vs. counted quantity, with the delta derived** — the cycle-count use case specifically ·
  seen in: Fishbowl (mobile cycle counts feeding adjustments), Cin7 · priority: **table-stakes** · spine:
  `StockAdjustmentLine.system_quantity` (snapshotted at line-creation time from the live on-hand aggregate) +
  `counted_quantity`; `quantity_delta` is a computed property, not stored · buildable now
- **Adjustment at the batch/serial level** — write off or add specific lots/serials, not just a bare quantity ·
  seen in: Zoho (add/select serials or batches depending on adjustment type) · priority: common · spine:
  `StockAdjustmentLine.lot_serial→LotSerial` (nullable) · buildable now
- **Stock revaluation as a distinct adjustment type** — corrects the *cost* of existing stock (write off then
  re-enter at a new cost) separately from correcting the *quantity* · seen in: Cin7 (dedicated "revaluation"
  adjustment) · priority: differentiator · spine: `StockAdjustment.reason` includes a `revaluation` choice, and
  `StockAdjustmentLine.unit_cost` lets the adjustment post at a cost different from the item's current
  average — enough to model it without a separate model · buildable now
- **Required reason/justification when writing off or rejecting** (mirrors the precedent already in `scm`:
  `GoodsReceiptLine.clean()` requires `rejection_reason` whenever `quantity_rejected > 0`) · seen in: general
  inventory-audit best practice, consistent across all 10 · priority: table-stakes · spine:
  `StockAdjustmentLine.clean()` validation, same pattern as the existing `GoodsReceiptLine` · buildable now
- **Value impact of an adjustment shown before posting** (quantity delta × unit cost) · seen in: Cin7
  (revaluation), Unleashed (average-cost-aware adjustments) · priority: common · spine: computed property on
  `StockAdjustmentLine`, no stored field · buildable now

### Reorder Point Automation (alerts + PO generation)
- **Per-item, per-location reorder point (minimum) and reorder quantity** · seen in: Cin7 (settable for total
  product number AND per location), Oracle Inventory Cloud (min-max planning at the organization *or*
  subinventory level), Odoo (reordering rules: min/max), inFlow (per-location reorder settings) · priority:
  **table-stakes** · spine: new table `ReorderRule` (`item→Item`, `location→Location` nullable = tenant-wide
  rule) · buildable now
- **Safety stock / buffer quantity distinct from the bare reorder point** · seen in: Katana, Oracle (order
  modifiers: minimum order quantity, fixed lot multiple) · priority: common · spine: `ReorderRule.safety_stock`
  (nullable) · buildable now
- **Low-stock alert / dashboard the moment on-hand crosses the point** · seen in: Katana (immediate alert before
  stockout), Sortly (threshold notification), Unleashed (low/high stock alerts) · priority: **table-stakes** ·
  spine: a read-only "Reorder Alerts" view comparing the live on-hand aggregate to each active `ReorderRule` — no
  new table, a report over `StockMove` + `ReorderRule` · buildable now
- **One-click / automatic purchase-requisition (or PO) generation from a triggered reorder rule** · seen in:
  Katana (auto-drafts a PO with the correct supplier/quantity/price the moment the point is crossed — the
  clearest precedent), NetSuite/Oracle (generate purchase/transfer-order *recommendations*) · priority:
  **differentiator** · spine: a service function on the Reorder Alerts view that creates a
  `scm.PurchaseRequisition` (4.1, already built) pre-filled from `ReorderRule.preferred_vendor` +
  `reorder_quantity`, with the PR line's `item_description`/`sku_hint` populated from `Item` — **coordinate
  with 4.1**: this is the first place `Item` and the free-text PR line fields meet; keep the PR line itself
  free-text this pass (no schema change to 4.1) and treat this as a convenience pre-fill, not a hard FK ·
  buildable now (as a service function generating a `PurchaseRequisition`, not a full auto-approve-and-send PO)
- **Reorder driven by demand-history/lead-time forecasting rather than a static number** · seen in: NetSuite
  (historical sales velocity + seasonality + supplier lead time), Kinaxis-class planning tools (per
  `research-scm.md`'s 4.7 Demand Planning & Forecasting) · priority: differentiator · spine: `ReorderRule.
  lead_time_days` is captured this pass as a static input; the statistical/ML-driven *calculation* of the
  reorder point itself belongs to 4.7 · deferred to 4.7
- **Reorder rule active/inactive toggle** (pause replenishment for a discontinued item without deleting history)
  · seen generally across all surveyed · priority: common · spine: `ReorderRule.is_active` · buildable now

### Inventory Valuation (FIFO, LIFO, Weighted Average)
- **Per-item costing method selectable at the item level** · seen in: Odoo (FIFO/Average/LIFO/Standard, matches
  the bullet almost verbatim), Cin7, DOSS · priority: **table-stakes** · spine: `Item.costing_method` field
  (already listed under Stock Control above — the same field drives both tracking and valuation) · buildable
  now
- **Weighted-average cost updated on every receiving transaction** · seen in: Unleashed (perpetual average
  landed cost, "updates instantly with each transaction"), Cin7 · priority: **table-stakes** · spine: a
  **derived/cached** `Item.average_cost` decimal field, recomputed by a service function whenever an inbound
  `StockMove` posts — the same "denormalized rollup updated by a service function" precedent 4.1 already set
  for `PurchaseOrderLine.received_quantity` — **not** a field a user edits directly · buildable now
- **FIFO / LIFO valuation via cost layers consumed in date order** · seen in: NetSuite, Odoo (FIFO/LIFO removal
  strategies), Cin7, Katana · priority: **table-stakes** · spine: **no separate cost-layer model needed** — every
  `StockMove` already carries its own `unit_cost` at the moment it was posted, so each inbound `StockMove` row
  *is* a cost layer. A **Stock Valuation Report** (read-only view/service function, not a stored table) walks a
  given item's inbound `StockMove` rows ordered `asc` (FIFO) or `desc` (LIFO) by `movement_date`, consuming
  quantities against those layers until the current on-hand total is allocated, and sums `quantity × unit_cost`
  per layer for the total value · buildable now (as a report), **not** a new persisted model
- **Stock revaluation posts a cost correction without changing quantity** · seen in: Cin7 (revaluation
  adjustment type) · priority: differentiator · spine: covered above under Stock Adjustment
  (`StockAdjustmentLine.unit_cost` on a `revaluation`-reason adjustment) · buildable now
- **Valuation report broken down by item, location, and lot/batch** · seen in: NetSuite, Fishbowl · priority:
  common · spine: the same Stock Valuation Report, grouped by the `StockMove.location`/`lot_serial` dimensions
  already on the ledger · buildable now
- **Posting the period-end inventory value to the general ledger** (perpetual-inventory GL integration) · seen
  in: NetSuite, Oracle, SAP S/4HANA (valuation drives financial statements directly), DOSS · priority:
  differentiator · spine: would post to **`accounting.JournalEntry`** (reused, never a second ledger) — this is
  squarely 4.18 Finance & Accounting Integration territory per `research-scm.md`, which already flags "landed
  cost… needs 4.3's valuation first" · deferred to 4.18
- **Landed cost (freight/duty/insurance rolled into unit cost)** · seen in: Unleashed ("average landed cost…
  factoring in labor, freight & duties"), Cin7 · priority: differentiator · spine: would need cost-component
  fields on the receiving transaction (GRN, 4.1) feeding into `StockMove.unit_cost` — a genuine 4.18 concern,
  already parked there in `research-scm.md` · deferred to 4.18

### Beyond the bullets
- **Bin/sub-location precision within a warehouse** (assign a specific bin at the transaction level without
  pre-linking bins to every item) · seen in: NetSuite (Advanced Bin Management) · priority: differentiator ·
  spine: `Location.parent` (self-FK) supports a light warehouse→zone→bin hierarchy if a tenant wants it, but
  the full slotting/optimization logic is 4.4 WMS's named bullet ("Bin/Location Management — mapping of
  warehouse layout and optimization of storage space") — keep `Location` here as a lean master, not a layout
  engine · parked, belongs to 4.4
- **Scheduled cycle counting of specific sections without halting operations** (a *program*, not a one-off
  adjustment) · seen in: Fishbowl (mobile-scanned scheduled counts), Cin7 · priority: differentiator · spine:
  `StockAdjustment(reason='cycle_count')` covers an ad hoc count-and-correct this pass; a scheduling/assignment
  workflow across zones is `NavERP-ERD.md`'s own `CycleCount` entity, named as Module 5's remaining genuinely-new
  piece · parked, belongs to Module 5 (or 4.4)
- **Opening-balance / initial stock load** — seeding starting quantities when an item first goes live · seen
  generally across all 10 (every ERP needs an opening-balance mechanism) · priority: table-stakes for
  go-live · spine: `StockMove.move_type = 'opening_balance'`, posted via the seeder/an admin action — no new
  table · buildable now

## Recommended build scope (this pass — 9 models: 6 spine + 3 domain)

### Spine models (own the inventory ledger; future modules FK into these, never re-declare)

1. **`ItemCategory`** — `tenant`, `name`, `parent→self` (nullable), `is_active`. `TenantOwned`. Justified by:
   item categorization (Odoo, Cin7, NetSuite). No FKs beyond self.

2. **`UOM`** — `tenant`, `code` (e.g. `EA`, `BOX`), `name`, `base_uom→self` (nullable — null means this *is* a
   base unit), `conversion_factor` (default `1`, meaning "1 of this unit = `conversion_factor` base units").
   `TenantOwned`. Justified by: unit-of-measure conversion (general ERP practice, matches `NavERP-ERD.md`'s
   `UOM`/`UOM_CONVERSION` intent, simplified to one base-unit link per UOM rather than a full N:N matrix).

3. **`Item`** — `tenant`, `sku` (unique per tenant), `name`, `description`, `category→ItemCategory` (nullable),
   `uom→UOM`, `item_type` (`stockable/non_stockable/service`), `costing_method`
   (`fifo/lifo/weighted_avg/standard`), `is_serial_tracked`, `is_lot_tracked` (booleans — drive whether
   `StockMove`/adjustment/transfer lines require a `LotSerial`), `average_cost` (derived/cached, updated by a
   service function on inbound `StockMove`, `editable=False` — mirrors the `PurchaseOrderLine.received_quantity`
   precedent), `standard_cost` (nullable, only meaningful when `costing_method='standard'`), `barcode`,
   `preferred_vendor→core.Party` (nullable, filtered to `PartyRole(role__in=['supplier','vendor'])` via the
   existing `_supplier_parties` helper — used to pre-fill reorder-triggered requisitions), `min_order_qty`,
   `is_active`. `TenantOwned`, `unique_together(tenant, sku)`. Justified by: per-item costing method (Odoo,
   Cin7), batch/serial flags (Zoho, NetSuite, Fishbowl), barcode (Sortly, Zoho). FKs: `core.Party` (verified).

4. **`Location`** — `tenant`, `code`, `name`, `parent→self` (nullable — light warehouse→zone→bin hierarchy),
   `location_type` (`warehouse/zone/bin`), `address→core.Address` (nullable, for a warehouse's physical
   address), `is_active`. `TenantOwned`, `unique_together(tenant, code)`. Justified by: multi-location stock
   (all 10 surveyed) + light bin precision (NetSuite) — kept intentionally lean; full layout/slotting is 4.4
   WMS's job. FKs: `core.Address` (verified).

5. **`LotSerial`** — `tenant`, `item→Item`, `tracking_type` (`lot/serial`), `code` (the lot number or serial
   number), `manufacture_date` (nullable), `expiry_date` (nullable), `status`
   (`active/quarantined/expired/consumed`), `notes`. `TenantOwned`, `unique_together(tenant, item, code)`.
   Justified by: batch tracking (Zoho, Fishbowl, Katana) + serial tracking (Zoho, NetSuite, Fishbowl, inFlow) +
   quarantine/status (NetSuite recall exposure). FKs: `Item` (this pass).

6. **`StockMove`** — `tenant`, `item→Item`, `location→Location`, `lot_serial→LotSerial` (nullable — required by
   `clean()` when `item.is_serial_tracked or item.is_lot_tracked`), `quantity` (signed `Decimal` — positive =
   in, negative = out; on-hand is `Sum(quantity)`, mirroring how `JournalLine` uses signed debit/credit),
   `unit_cost` (the cost layer value at the moment of this move — required on inbound moves, used by outbound
   moves for COGS/valuation), `move_type`
   (`receipt/issue/transfer_in/transfer_out/adjustment_increase/adjustment_decrease/opening_balance`),
   `movement_date`, `reference` (free text — mirrors `JournalEntry.reference`, e.g. "GRN-00001", rather than a
   generic `content_type`/`object_id` FK, matching the as-built ledger precedent, not the ERD's aspirational
   generic-source note), `stock_transfer→StockTransfer` (nullable), `stock_adjustment→StockAdjustment`
   (nullable), `created_by`. `TenantOwned` (append-only — no update/delete path in the UI; corrections are new
   moves, exactly like `JournalEntry` reversals). Justified by: real-time derived on-hand (the mandated spine
   rule, matches all 10 surveyed) + FIFO/LIFO cost-layer valuation (NetSuite, Odoo, Cin7, Katana). FKs: `Item`,
   `Location`, `LotSerial` (this pass).

### Domain models (SCM 4.3's own transactional capabilities — post `StockMove` rows)

7. **`StockTransfer`** [`TRF-`] + **`StockTransferLine`** — Header: `tenant`, `number`,
   `from_location→Location`, `to_location→Location`, `status` (`draft/in_transit/completed/cancelled`),
   `transfer_date`, `requested_by→settings.AUTH_USER_MODEL`, `notes`. `TenantNumbered`. Line:
   `transfer→StockTransfer`, `item→Item`, `quantity`, `lot_serial→LotSerial` (nullable). Completing the
   transfer posts a paired `StockMove` per line (`transfer_out` at `from_location`, `transfer_in` at
   `to_location`, both at the item's current `average_cost` — a transfer doesn't change valuation). Justified
   by: the Warehouse Transfer bullet verbatim (Zoho, Fishbowl, Unleashed, inFlow). FKs: `Location`, `Item`,
   `LotSerial` (all this pass).

8. **`StockAdjustment`** [`ADJ-`] + **`StockAdjustmentLine`** — Header: `tenant`, `number`, `location→Location`,
   `reason` (`damage/loss/theft/cycle_count/write_off/found/correction/revaluation`), `status`
   (`draft/posted/cancelled`), `adjustment_date`, `adjusted_by→settings.AUTH_USER_MODEL`, `notes`.
   `TenantNumbered`. Line: `adjustment→StockAdjustment`, `item→Item`, `lot_serial→LotSerial` (nullable),
   `system_quantity` (snapshotted from the live on-hand aggregate when the line is added), `counted_quantity`,
   `unit_cost` (defaults to the item's current `average_cost`, overridable for a `revaluation` reason),
   `notes`; `clean()` requires `notes` when `reason` is `damage/loss/theft` (mirrors `GoodsReceiptLine`'s
   existing required-reason-on-rejection pattern). Posting creates one signed `StockMove`
   (`adjustment_increase`/`adjustment_decrease`) per line at `location`. Justified by: the Stock Adjustment
   bullet verbatim (write-offs, damages, cycle-count corrections — Cin7, Zoho, Unleashed, Fishbowl). FKs:
   `Location`, `Item`, `LotSerial` (this pass).

9. **`ReorderRule`** — `tenant`, `item→Item`, `location→Location` (nullable = tenant-wide rule),
   `reorder_point`, `reorder_quantity`, `safety_stock` (nullable), `preferred_vendor→core.Party` (nullable,
   supplier/vendor role), `lead_time_days` (nullable), `is_active`. `TenantOwned` (no document number — a
   standing configuration rule, same shape as 4.2's `SupplierProfile`). No line table. A **Reorder Alerts**
   view (report, not a model) compares live on-hand (`Sum(StockMove.quantity)` per `item`/`location`) against
   active rules and offers a "Create Requisition" action that pre-fills a `scm.PurchaseRequisition` (4.1) from
   `preferred_vendor`/`reorder_quantity`/`item`. Justified by: the Reorder Point Automation bullet verbatim
   (Cin7 per-location points, Oracle min-max planning, Katana auto-PO-draft, inFlow per-location settings). FKs:
   `Item`, `Location` (this pass), `core.Party`, `scm.PurchaseRequisition` (4.1, verified existing — target of
   the alert action, not a stored FK on `ReorderRule` itself).

### List pages vs. reports
- **List pages (CRUD):** `Item`, `ItemCategory`, `UOM`, `Location`, `LotSerial`, `StockTransfer`,
  `StockAdjustment`, `ReorderRule`.
- **Read-only reports (no CRUD, computed views):** **Stock Valuation Report** (FIFO/LIFO/weighted-average value
  by item/location/lot, walking `StockMove.unit_cost` layers), **Reorder Alerts** (on-hand vs. `ReorderRule`,
  with the "Create Requisition" action), **Stock Ledger / Movement History** (raw `StockMove` audit trail per
  item/location — the append-only ledger itself is inspectable but not directly editable, same posture as
  `JournalLine`), **On-Hand by Location** (current derived quantities, the "Stock Control" bullet's headline
  screen).

*(9 top-level entities / 12 concrete tables counting the three domain child-line tables — at the top end because
4.3 is genuinely building the spine AND the domain capabilities in the same pass, matching the task's explicit
"~5-6 SPINE + ~3 DOMAIN" scope. None of it duplicates `core.Party`/`core.Address`/`core.Document`/
`accounting.Currency`/`accounting.JournalEntry`, which are reused as-is; none of it duplicates 4.1's
`PurchaseOrder`/`GoodsReceiptNote`/`PurchaseRequisition`, which are read from/pre-filled into, not re-modeled.)*

## Belongs to sibling sub-modules (parked, not scoped here)

- **Bin/location layout mapping, storage-space optimization, put-away/pick strategy** → 4.4 Warehouse
  Management System (WMS) — this pass's `Location` is a lean master (code, name, light parent hierarchy) just
  enough to post `StockMove` rows against; 4.4 owns the actual slotting/layout intelligence.
- **Inbound dock scheduling, outbound wave/batch/zone picking, packing, shipping labels, yard management** →
  4.4 WMS entirely — out of scope here.
- **Scheduled/programmatic cycle-counting across zones (the `CycleCount` entity itself, as opposed to a one-off
  count-and-correct `StockAdjustment`)** → `NavERP-ERD.md` names this as Module 5's (or 4.4's) remaining
  genuinely-new piece once the spine exists; this pass's `StockAdjustment(reason='cycle_count')` is the manual
  building block, not the scheduling program.
- **Statistical/ML-driven reorder-point calculation from demand history and seasonality** → 4.7 Demand Planning
  & Forecasting (already flagged in `research-scm.md`). `ReorderRule.reorder_point`/`lead_time_days` are static
  inputs this pass; 4.7 is where they'd become computed outputs.
- **Perpetual-inventory GL posting (journalizing stock value changes) and landed cost (freight/duty rolled into
  unit cost)** → 4.18 Finance & Accounting Integration (already flagged in `research-scm.md` as needing "4.3's
  valuation first" — now it exists). Reuses `accounting.JournalEntry`, never a second ledger.
- **`PriceList` / sales pricing by item** → Module 5's remaining genuinely-new piece per the ERD, and/or Module 8
  Sales — `Item.standard_cost`/`average_cost` here are *costing* fields, not customer-facing price lists.
- **Auto-transfer-instead-of-purchase when a satellite location is short** (inFlow's pattern) → a natural v2 on
  `ReorderRule`, not required by the bullet as written (which asks for "PO generation," i.e. purchasing, not
  inter-location transfer).

## Deferred (later passes / integrations)

- **Wire `scm.GoodsReceiptNote.mark_received` (4.1) to post an inbound `StockMove`** — the GRN docstring already
  names this exact hook ("When it does, `mark_received` is the hook that should post the inventory effect
  inside `transaction.atomic()`"). Now that `StockMove` exists (in `scm`, not Module 5 as that comment
  currently says), this is the first concrete follow-up: update the stale docstring and add the posting call.
  **Not done in this pass** per the task brief — 4.3 ships the spine + its own domain models only.
- **Backfill `item→scm.Item` (nullable FK) onto 4.1's free-text line tables** (`PurchaseRequisitionLine`,
  `RFQLine`, `PurchaseOrderLine`, `GoodsReceiptLine`) — those four models' docstrings already record this exact
  migration as a TODO for "when Module 5 Inventory ships" (per lesson L36); since `scm.Item` now exists as of
  *this* sub-module, the migration is unblocked but still a deliberate follow-up, not an automatic side effect
  of this pass.
- **Two-step "ship then receive" transfer workflow** (deduct at source on dispatch, only credit the destination
  on confirmed receipt, with an explicit in-transit valuation) — this pass posts both `StockMove` legs at
  `StockTransfer` completion in one step; Zoho/Fishbowl's fuller in-transit modeling is a legitimate later
  refinement.
- **Landed cost components on receiving** (freight/duty/insurance folded into `StockMove.unit_cost`) — needs
  4.18's Finance integration; this pass's `unit_cost` is the PO/GRN unit price only.
- **GL posting of inventory value changes** (perpetual-inventory journal entries) — 4.18, reuses
  `accounting.JournalEntry`.
- **Full N:N UOM conversion matrix** (any unit to any unit, not just "this unit's factor to its one base unit")
  — `NavERP-ERD.md`'s `UOM_CONVERSION` join table is the fuller design; this pass's single `base_uom`+
  `conversion_factor` per `UOM` covers the common case (stock in each, buy in box-of-12) without the extra
  table.
- **Demand-history-driven reorder point calculation** (statistical/ML) — 4.7 Demand Planning & Forecasting.
- **Scheduled cycle-count program** (assign zones/sections to a counting calendar, track completion) —
  `NavERP-ERD.md`'s `CycleCount` entity, likely Module 5 or 4.4's job once reached.
- **Bin/slotting optimization and pick-path strategies** — 4.4 WMS.
- **Barcode-scanner hardware/mobile-camera UX** — `Item.barcode` is captured this pass; the actual scan
  interaction is a later mobile/PWA integration.
- **Module 5 (Inventory/IMS) ERD reconciliation** — per lesson L36's required close-out step, whoever writes
  Module 5's own `research-inventory.md` must rewrite `NavERP-ERD.md` line 467's "Adds" column for Module 5 down
  to its genuinely-new pieces (`CycleCount`, `PriceList`, whatever else 5.x turns out to add) and mark
  `Item`/`ItemCategory`/`UOM`/`Location`/`LotSerial`/`StockMove`/`StockTransfer`/`StockAdjustment`/`ReorderRule`
  as as-built-in-`scm`, to be *extended* by FK, not re-declared. This file, `apps/core/navigation.py`'s future
  `"4.3"` banner comment, and the owning models' docstrings are the three durable places to encode the call
  (mirrors how 4.1 already did this for `PurchaseOrder`/`RFQ`).

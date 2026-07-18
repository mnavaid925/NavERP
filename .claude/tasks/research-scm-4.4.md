# Research — Sub-module 4.4: Warehouse Management System (WMS) (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **LIVE_LINKS built so far in module 4** (`apps/core/navigation.py` lines 763-799): `"4.1"` Procurement
  Management (Purchase Requisition, RFQ, PO Management, Vendor Portal, Invoice Reconciliation), `"4.2"` SRM
  (Supplier Onboarding, Scorecard, Contract Management, Catalog Management, Risk Management), `"4.3"` Inventory
  Management (Stock Control, Warehouse Transfer, Stock Adjustment, Reorder Point Automation, Inventory
  Valuation). `"4.4"` has **no entry** — confirmed the next unbuilt sub-module in Module 4.
- **Spine entities verified to EXIST** (`grep -rn "^class " apps/scm/models/`):
  - `scm.Location` (`InventoryManagement/Locations.py`) — self-referential (`parent→self`), `location_type` ∈
    `warehouse/zone/bin/staging/transit`, `code`/`name`/`is_active`, `.path()`, `.is_leaf`, `.on_hand_value()`.
    **No bin-specific attributes yet** (no capacity, no pick sequence, no ABC class) — exactly the gap the task
    brief flagged. 4.4 extends this model with fields, per the "Bin/Location Management" bullet, rather than
    re-declaring a location table.
  - `scm.StockMove` (`InventoryManagement/StockMoves.py`) — append-only, signed `quantity`, `unit_cost`,
    `move_type` ∈ `receipt/issue/transfer/adjustment`, `reference` (free text), `reason`, `moved_at`. No
    stored on-hand anywhere; every quantity is `Sum(StockMove.quantity)`. Confirmed the posting service
    (`apps/scm/views/_helpers.py`) is the ONLY writer: `_post_stock_move()` (the atomic primitive),
    `_post_transfer()` (posts a −/+ pair for `StockTransfer`), `_post_adjustment()` (posts one signed move per
    `StockAdjustmentLine`). 4.4 must call these, never `StockMove.objects.create()` directly.
  - `scm.StockAdjustment` [`ADJ-`] + `StockAdjustmentLine` — `reason` choices already include
    `cycle_count` (`("cycle_count", "Cycle Count Correction")`). It has NO scheduling/assignment/count-sheet
    concept — it is purely the correction document. Confirms the task brief: 4.4 adds the *program* that
    produces one of these, it does not add a second correction path.
  - `scm.StockTransfer` [`TRF-`] + `StockTransferLine` — `from_location`/`to_location→Location`, status
    `draft/in_transit/completed/cancelled`; completion posts a paired `StockMove` via `_post_transfer`. This is
    the only real "outbound demand" document that exists today (no `SalesOrder`/OMS yet) — see Recommended
    build scope for how 4.4's picking layer uses it.
  - `scm.Item`, `scm.UOM`, `scm.ItemCategory`, `scm.LotSerial` — all exist, `TenantOwned`, as documented in
    `research-scm-4.3.md`.
  - `scm.GoodsReceiptNote` [`GRN-`] (4.1, `ProcurementManagement/GoodsReceiptNotes.py`) + `GoodsReceiptLine` —
    records receipt against a `PurchaseOrder`, drives the PO/GRN/Bill three-way match. **Critically, it does
    NOT post a `StockMove`.** Its `goodsreceipt_receive` view (`apps/scm/views/ProcurementManagement/
    GoodsReceiptNotes.py` line ~117) carries a live comment: *"NOTE (L28): when `core.StockMove` lands with
    Module 5, this is where the inventory effect posts."* That comment is now stale twice over — `StockMove`
    landed in `scm` (4.3), not Module 5, and it already exists — but the wiring itself was **never done**;
    `research-scm-4.3.md`'s own Deferred section flags this exact gap and explicitly says "not done in this
    pass." **4.4 is the natural sub-module to close it** (see Recommended build scope) because putaway is
    meaningless without a posted receipt to move.
  - `GoodsReceiptLine`/`PurchaseOrderLine` are **still free-text** (`item_description`, `sku_hint`, `uom_hint` —
    grep-verified in `apps/scm/models/ProcurementManagement/PurchaseOrders.py`), **not** an FK to `scm.Item`.
    `research-scm-4.3.md` flagged backfilling a nullable `item→scm.Item` FK onto these lines as a deferred
    follow-up; it still hasn't happened. This is a real dependency gap for 4.4's putaway (see below).
  - `PurchaseOrder` (4.1, `scm.PurchaseOrder`) is the correct FK target for inbound yard/dock visits — NOT
    `crm.PurchaseOrder` (the CRM 1.12 pre-spine stand-in).
- **Spine entities verified NOT to exist:** `SalesOrder` (Module 8), any `Carrier`/`Shipment`/`RoutePlan` (4.6
  TMS, not built — `grep -rn "^class (Carrier|Shipment|RoutePlan)" apps/` → no matches). Confirms the task
  brief: shipping-label/carrier data stops at NavERP's own boundary this pass.
- **Number prefixes already in use in `scm`** (`grep -rn "NUMBER_PREFIX" apps/scm/models/`): `GRN`, `PR`, `RFQ`,
  `QT`, `ADJ`, `PO`, `TRF`, `CAT`, `SCR`, `SC`, `SRA`. New prefixes chosen for 4.4 (`PUT`, `PIK`, `CC`, `YRD`)
  do not collide (numbering is scoped per-model via `next_number()` anyway, but distinct prefixes keep
  cross-module documents visually distinguishable).
- **Sibling research read:** `research-scm.md` (module-wide orientation; 4.4 was pre-flagged as "needs 4.3's
  Location/Bin hierarchy first" and "differentiator territory — best-of-breed WMS vendors clearly outclass
  generic ERP inventory screens"), `research-scm-4.3.md` (confirms the as-built `StockMove`/`StockAdjustment`/
  `StockTransfer` shapes above, and explicitly parks "Bin/location layout mapping, storage-space optimization,
  put-away/pick strategy," "Inbound dock scheduling, outbound wave/batch/zone picking, packing, shipping
  labels, yard management," and "Scheduled/programmatic cycle-counting" to 4.4 — this file is where those
  parked items land), `research-scm-4.2.md` (confirms the `TenantOwned`/`TenantNumbered` base-class pattern and
  the ships-first L29/L36 precedent this file continues).

## Leaders surveyed (with source links)

1. **Manhattan Associates (Manhattan Active WMS)** — Tier-1 cloud-native WMS; AI-driven directed putaway/
   slotting, waveless "Order Streaming," task interleaving (putaway combined with picking on the same aisle
   pass) — [Best WMS Brands](https://www.manh.com/our-insights/comparisons/best-wms-brands),
   [Manhattan WMS overview](https://bestopschainai.com/warehouse-inventory/manhattan-associates-wms-overview-features)
2. **Blue Yonder WMS** — mature Tier-1 WMS, Gartner Magic Quadrant Leader; AI/ML **Advanced Slotting** (demand
   pattern + item dimension + pick-velocity driven bin recommendations, "chained moves" scheduling), labor
   forecasting/engineered-labor-standards — [Blue Yonder WMS](https://blueyonder.com/solutions/warehouse-management),
   [Advanced Slotting](https://blueyonder.com/solutions/warehouse-management/advanced-slotting)
3. **SAP Extended Warehouse Management (EWM)** — deep S/4HANA integration; scheduled dock appointments combined
   with yard management to minimize dock congestion, multiple cycle-count methods (annual/continuous/
   zero-crossing), physical-inventory-by-bin —
   [SAP EWM features](https://www.sap.com/mena/products/scm/extended-warehouse-management/features.html),
   [Dock & Yard Management](https://blogs.sap.com/2019/11/26/dock-yard-management/)
4. **Oracle WMS Cloud** — configurable directed putaway (incl. AI "Market Basket Analysis" putaway method),
   wave planning with multiple allocation strategies (FEFO/LEFO, FIFO/LIFO, location-sequence), pick-to-zero
   cycle counts + summary-based cycle count module —
   [Oracle WMS Cloud](https://www.erpresearch.com/erp-add-ons/wms/oracle-wms-cloud),
   [21B What's New](https://www.oracle.com/webfolder/technetwork/tutorials/tutorial/cloud/wms/releases/21B/21B-wms-wn.htm)
5. **Körber (K.Motion WMS / now Infios)** — modular WMS; ABC-analysis and zone-based cycle counting, slotting
   analysis from product characteristics/order patterns, yard management for automated and manual yards —
   [Körber WMS](https://koerber-supplychain.com/supply-chain-solutions/supply-chain-software/warehouse-management/),
   [Körber WMS review](https://claruswms.ai/korber-wms/)
6. **Infor WMS (CloudSuite WMS)** — system-directed putaway based on zone/velocity/product-attribute/
   slot-optimization rules, order/cluster/consolidation picking, voice-directed picking, real-time system-driven
   cycle counting (ABC class, aisle range, item cost, movement, exception-driven) —
   [Infor CloudSuite WMS](https://www.erpresearch.com/en-us/infor-cloudsuite-wms),
   [Creating a putaway strategy](https://docs.infor.com/wms/11.5.x/en-us/sceolh/rgj1612894308944.html)
7. **NetSuite WMS** — wave picking / wave release grouping orders by criteria (priority, ship method, zone),
   zone picking with specialized zone pickers, "Smart Count" mobile cycle counting without freezing the whole
   location —
   [NetSuite WMS](https://www.netsuite.com/portal/products/erp/warehouse-fulfillment/wms.shtml),
   [Wave Picking](https://www.netsuite.com/portal/resource/articles/inventory-management/wave-picking.shtml)
8. **Fishbowl Warehouse** — SMB/mid-market; barcode-scanned pick/pack/ship, ShipExpress/Shippo carrier
   integrations for label generation and rate comparison from within the WMS (the concrete "packing → label"
   hand-off precedent) —
   [Fishbowl Warehouse](https://www.fishbowlinventory.com/warehouse-management),
   [Shipping Integration](https://help.fishbowlinventory.com/hc/en-us/articles/360042634254-Shipping_Integration)
9. **Deposco (Bright Warehouse)** — cloud WMS/OMS for high-growth distribution/3PL; automated daily cycle
   counts for high-velocity items (replacing annual physical inventories), dynamic slotting optimization for
   seasonal inventory —
   [Deposco Warehouse Management](https://deposco.com/solutions/supply-chain-execution/warehouse-management/),
   [6 top WMS capabilities](https://deposco.com/blog/6-top-wms-system-capabilities-that-warehouse-management-teams-cant-live-without/)
10. **Softeon WMS** — wave management that balances work across zones and limits waves per DC constraints;
    batch picking, batch-zone picking, pick-and-pass; a graphical yard tool for trailer scheduling/check-in-out
    as a WMS add-on module —
    [Softeon WMS](https://www.softeon.com/solutions/warehouse-management-system-wms/),
    [Softeon Yard Management](https://www.softeon.com/solutions/warehouse-management-system-wms/yard-management/)

*(10 surveyed, matching the task's suggested list exactly. General putaway-strategy taxonomy — directed / fixed
/ random / cross-dock — synthesized from cross-vendor warehousing-operations sources, not any single product.)*

## Feature catalog (this sub-module only)

### Inbound Operations (dock scheduling, receiving, put-away strategies)
- **Dock/door appointment scheduling for inbound trucks** — a scheduled window + assigned dock door, tied to
  the PO being delivered · seen in: SAP EWM (dock appointments combined with yard mgmt to cut congestion),
  Softeon (appointment scheduling as part of yard tooling), general dock-scheduling category (Opendock,
  DataDocks) · priority: table-stakes · spine: new field group on a **Yard/Dock visit** record (see Recommended
  build scope) — reuses `scm.Location` (`location_type='staging'`) as the dock/door, `scm.PurchaseOrder` (4.1,
  verified) as the inbound reference · buildable now
- **Directed putaway** — system suggests the optimal bin per item (zone/velocity/attribute-driven) · seen in:
  Manhattan (AI slotting engine), Infor (zone/velocity/attribute rules), Oracle (Market Basket Analysis putaway
  method), Blue Yonder (Advanced Slotting feeding putaway) · priority: **table-stakes** (as a rule-based
  suggestion; ML-driven optimization is the differentiator tier) · spine: new table `PutawayTask` with a
  `suggested_location` computed from `Location.abc_class`/`pick_sequence` (a simple rule this pass, not ML) ·
  buildable now (rule-based); differentiator (ML-driven) deferred
- **Fixed-location and random-location putaway** — the two simpler alternatives to directed putaway, still
  common in mid-market WMS · seen generally across all 10 · priority: table-stakes · spine: `PutawayTask.
  strategy` choice field (`directed/fixed/random/cross_dock`) — the same record covers all four strategies, only
  the suggestion logic differs · buildable now
- **Cross-docking** — receipt is routed straight to an outbound stage without settling in a storage bin (for
  short-shelf-life or urgent items) · seen in: general warehousing-operations literature, Softeon/Manhattan-class
  WMS · priority: differentiator · spine: `PutawayTask.strategy = 'cross_dock'` with `to_location` pointed at a
  staging/outbound `Location` instead of a bin — modeled this pass as a strategy value, not a separate flow ·
  buildable now (as a strategy tag); full automated cross-dock orchestration (auto-linking to an outbound pick
  the instant a matching demand exists) is deferred
- **Receiving posts inventory the moment goods are accepted** — the concrete wire-up gap flagged by the task
  brief: `GoodsReceiptNote.mark_received` (4.1) currently does **not** call the `StockMove` posting service at
  all · seen in: **every** surveyed WMS (goods aren't "in stock" system-wide until receiving posts them) ·
  priority: **table-stakes** · spine: this pass closes the gap — `goodsreceipt_receive` posts one `receipt`-type
  `StockMove` via the existing `_post_stock_move()` into a staging `Location` at the moment of booking (see
  Recommended build scope, "wire-up") · buildable now
- **Putaway confirmation posts the second leg of the move** (staging → final bin) · seen in: all 10 (this is the
  literal definition of "putaway" in a WMS with a receiving dock) · priority: **table-stakes** · spine:
  `PutawayTask` confirm action posts a paired `StockMove` (move_type=`transfer`) via the existing
  `_post_stock_move()` helper — the SAME primitive `_post_transfer()` already uses, just called directly rather
  than through `StockTransfer` (a putaway is a same-tenant relocation, not a new transfer document) · buildable
  now
- **Quality/condition flag at receiving before putaway** (accept/reject/quarantine) · seen in: NetSuite, Oracle,
  Infor (all gate putaway behind a QC pass) · priority: common · spine: `GoodsReceiptLine.quantity_rejected` +
  `rejection_reason` **already exist** (4.1) — only the accepted quantity should ever reach `PutawayTask`; a
  full inspection workflow (criteria, NCR) is 4.9 QMS / Module 12 territory · buildable now (using existing
  fields), deferred (formal inspection workflow)

### Outbound Operations (picking strategies — wave, batch, zone — packing, shipping label generation)
- **Wave picking** — orders/tasks released together in a batch based on criteria (priority, ship method, zone)
  · seen in: NetSuite (wave release groups like orders), Oracle (wave planning with FEFO/FIFO allocation
  strategies), Softeon (wave management balancing work across zones) · priority: **table-stakes** · spine:
  `PickTask.wave_number` (a grouping value, not a separate wave-release-engine table this pass) · buildable now
- **Batch picking** — one picker collects items for multiple outbound demands in a single warehouse pass · seen
  in: Softeon (batch picking, batch-zone picking), Infor (cluster/consolidation picking), Manhattan (cluster
  picking) · priority: **table-stakes** · spine: `PickTask.strategy = 'batch'` + shared `wave_number` groups
  tasks a picker works together · buildable now
- **Zone picking** — the warehouse is divided into zones, each with a specialized picker who only picks within
  their zone · seen in: NetSuite (zone picking), Softeon, Manhattan · priority: **table-stakes** · spine:
  `PickTask.from_location` (bin) implies its `Location` zone ancestor via `.path()`/`.parent`; `strategy =
  'zone'` documents intent · buildable now
- **Pick-path optimization (sequenced by location, not random)** — pick lists ordered to minimize walking
  distance · seen in: Manhattan, Blue Yonder (both cite 15-30% travel-time reduction from sequencing) ·
  priority: differentiator · spine: `Location.pick_sequence` (new field, this pass) drives an `order_by
  ('from_location__pick_sequence')` on the pick-list view — a simple sort, not a routing algorithm · buildable
  now (as a sort key); true path/graph optimization is differentiator/deferred
- **Short-pick handling** — recording less than the requested quantity was available, without blocking the rest
  of the task · seen generally across all 10 (a WMS staple) · priority: **table-stakes** · spine:
  `PickTaskLine.quantity_requested` vs. `quantity_picked` (may differ), `status` choice includes `short` ·
  buildable now
- **Task interleaving** — combining a putaway and a pick into one aisle pass to cut "deadhead" travel · seen in:
  Manhattan (10-15% labor productivity gain cited) · priority: differentiator · spine: would need a scheduling
  engine cross-referencing open `PutawayTask`s and `PickTask`s by aisle — genuinely a later optimization layer ·
  deferred
- **Packing — carton/package capture (weight, dimensions, carton count)** · seen in: Fishbowl (carton
  configurations, packing slips), general WMS packing stations · priority: common · spine: pack-stage fields on
  `PickTask` (`carton_count`, `package_weight`, `package_dimensions`, `packed_at`, `packed_by`) rather than a
  separate `Package` table this pass — kept lean; a multi-carton-per-pick split is a natural v2 · buildable now
- **Shipping label generation / carrier hand-off** · seen in: Fishbowl (ShipExpress/Shippo — compare rates,
  print labels, all from within the WMS) · priority: common · spine: **stops at label DATA, not label
  rendering** — `PickTask.tracking_number` (free text placeholder) is the hand-off field; actual carrier-rate
  shopping, label PDF/ZPL rendering, and tracking sync are **4.6 Transportation Management System (TMS, not
  built)** territory, exactly as the task brief instructs · buildable now (data field), integration/later
  (carrier API/label rendering)
- **Removal strategy at pick time (FIFO/LIFO/FEFO, nearest-expiry-first)** · seen in: Oracle (FEFO/LEFO
  allocation strategies), Odoo (per `research-scm-4.3.md`, already flagged as belonging here) · priority:
  differentiator · spine: `PickTask` line resolution could prefer `LotSerial.expiry_date` ascending when the
  item is lot-tracked — a query-ordering rule, no new field · buildable now (as a default query order),
  differentiator (full configurable removal-strategy engine) deferred

### Bin/Location Management (mapping of warehouse layout and optimization of storage space)
- **Bin capacity (max quantity or volume)** · seen in: general WMS slotting literature (Deposco, Blue Yonder,
  Manhattan all size bins before recommending a putaway) · priority: **table-stakes** · spine: **extend
  `scm.Location`** with `capacity_qty` (nullable decimal) — captured, not yet enforced (enforcement deferred) ·
  buildable now
- **Pick sequence per bin** — the walk order used to build an efficient pick list · seen in: Manhattan, Blue
  Yonder (pick-path sequencing) · priority: **table-stakes** for any real picking UI · spine: extend
  `scm.Location` with `pick_sequence` (nullable integer) · buildable now
- **ABC classification per location/item** — velocity-based tiering that drives both slotting priority and
  cycle-count frequency · seen in: Körber (ABC-analysis cycle counting), Infor (ABC-class-driven counts),
  Blue Yonder/Deposco (slotting by velocity) · priority: **table-stakes** · spine: extend `scm.Location` with
  `abc_class` (choice `A/B/C`, nullable) — reused by `CycleCountTask` scheduling and putaway suggestion below ·
  buildable now
- **AI/ML-driven dynamic slotting** (demand pattern + item dimension + velocity → auto-recommended bin, "chained
  moves" for re-slotting) · seen in: Blue Yonder (Advanced Slotting), Manhattan (AI slotting engine), Deposco
  (dynamic slotting for seasonal inventory) · priority: **differentiator** · spine: a v2 service function reading
  `StockMove` velocity history + `Location.abc_class`; this pass's `PutawayTask.suggested_location` is a simple
  rule (same-item's-existing-bin, else emptiest bin in the item's category zone), not ML · deferred
- **Warehouse layout visualization (map/floor plan)** · seen in: Softeon (graphical yard/warehouse tool),
  general WMS UX · priority: common · spine: presentation-layer only, over the existing `Location.parent`
  hierarchy + new `abc_class`/`capacity_qty` — no schema needed beyond the two fields above · buildable now
  (a simple grid/tree view), differentiator (a true interactive floor-plan) deferred

### Cycle Counting (scheduled counting of specific inventory sections without halting operations)
- **Ad hoc/scheduled count of one section (a zone or bin) without freezing the whole warehouse** · seen in: **all
  10** (this is the literal definition of cycle counting vs. an annual physical inventory) · priority:
  **table-stakes** · spine: new table `CycleCountTask` scoped to one `scm.Location` · buildable now
- **System quantity snapshotted at count-creation time, counted quantity entered separately, variance derived**
  · seen in: NetSuite Smart Count, SAP EWM, Oracle (pick-to-zero / summary-based counts) · priority:
  **table-stakes** · spine: `CycleCountTaskLine.system_quantity` (snapshot from the live `Item.on_hand(location)`
  aggregate) + `counted_quantity`; `variance` a computed property · buildable now
- **ABC-class-driven / velocity-driven count scheduling** (A-class items counted more often than C-class) · seen
  in: Körber, Infor, Oracle · priority: **differentiator** · spine: `Location.abc_class` (new field, above)
  informs a *manual* "create counts for all A-class bins" bulk-create action this pass; a fully automatic
  recurring calendar/program is deferred · buildable now (bulk-create action), deferred (recurring scheduler)
- **Count finalization generates the correction, never a second correction path** — the task brief's explicit
  instruction · seen in: every surveyed WMS routes a variance into the same inventory-adjustment mechanism · 
  priority: **table-stakes** · spine: **`CycleCountTask.finalize()` creates one `scm.StockAdjustment`
  (reason='cycle_count') + one `StockAdjustmentLine` per non-zero-variance line, and posts it through the
  EXISTING `_post_adjustment()` helper** — no new posting path · buildable now
- **Recount / exception flag** — a line with a large variance gets flagged for a second count before it's
  accepted · seen in: Oracle (variance management), Infor (exception-condition counts) · priority: common ·
  spine: `CycleCountTaskLine.needs_recount` (boolean) — a soft gate on `finalize()`, not a hard block this pass ·
  buildable now
- **Continuous "pick-to-zero" counting** — the picker confirms zero when a location empties out during normal
  picking, which itself is a lightweight cycle count · seen in: Oracle (pick-to-zero mode) · priority:
  differentiator · spine: could hook `PickTask` completion for a bin that lands on exactly zero — natural v2
  integration between `PickTask` and `CycleCountTask` · deferred

### Yard Management (tracking of trucks and trailers within the warehouse yard)
- **Truck/trailer check-in and check-out with dwell-time tracking** · seen in: SAP EWM, Softeon (graphical yard
  tool), general YMS category (DataDocks, Opendock, YardView) · priority: **table-stakes** · spine: new table
  `YardVisit` (`checked_in_at`/`checked_out_at`; dwell time = the difference, computed) · buildable now
- **Dock door assignment** — which physical door a trailer is at/assigned to · seen in: SAP EWM (dock+yard
  combined), Softeon · priority: **table-stakes** · spine: `YardVisit.dock_door→scm.Location` (reuses the
  existing `location_type='staging'` choice — no new `LOCATION_TYPES` value needed) · buildable now
- **Scheduled appointment window vs. actual arrival** — flags early/late/no-show trucks · seen in: dock-
  scheduling category broadly (Opendock, DataDocks), SAP EWM · priority: common · spine: `YardVisit.
  scheduled_at` vs. `checked_in_at` · buildable now
- **Inbound/outbound visit type, linked to the driving document** · seen in: general YMS (a visit either drops
  off or picks up freight) · priority: **table-stakes** · spine: `YardVisit.visit_type` (`inbound/outbound`) +
  `purchase_order→scm.PurchaseOrder` (nullable, verified existing, 4.1) for inbound; outbound has no real FK
  target yet (no `Shipment`/TMS) so uses a free-text `reference` — mirrors the task brief's "stop at the TMS
  boundary" instruction · buildable now
- **Carrier/driver/vehicle identification** · seen in: all YMS surveyed · priority: **table-stakes** · spine:
  free-text `carrier_name`, `driver_name`, `vehicle_plate`, `trailer_number` — a real `Carrier` master belongs
  to 4.6 TMS (not built); this pass captures the visit-level facts without inventing a carrier catalog ·
  buildable now
- **Self-service carrier appointment portal** · seen in: Opendock, DataDocks (drivers/dispatchers self-schedule)
  · priority: differentiator · spine: would need an externally-authenticated carrier login — same L32 pattern
  4.1's Vendor Portal already deferred (a staff-facing list instead of a real external login) · integration/later
- **Live yard map / drag-and-drop trailer assignment, GPS/RFID asset tracking** · seen in: Softeon (graphical
  yard tool), general YMS · priority: differentiator · spine: presentation-layer over `YardVisit` + `dock_door`;
  RFID/GPS is hardware integration · buildable now (a simple status board), integration/later (real-time
  tracking hardware)

### Beyond the bullets
- **Labor management / productivity tracking per task** (time-per-pick, engineered labor standards) · seen in:
  Blue Yonder (4.6/5-rated labor management), Manhattan (task interleaving labor gains) · priority:
  differentiator · spine: `PickTask`/`PutawayTask` already carry `assigned_to`/timestamps, enough for a basic
  "tasks completed per user" report; a full labor-standards/incentive engine overlaps **4.14 Labor Management**
  (already flagged in `research-scm.md` as overlapping HRM, Module 3) · parked, belongs to 4.14
- **Voice-directed picking / RF scanner hardware UX** · seen in: Infor (Vocollect integration), Fishbowl (mobile
  scanning) · priority: common in mature WMS · spine: `PickTask`/`PutawayTask` data model supports it; the
  actual scan/voice hardware interaction is a later mobile/PWA concern · integration/later
- **Quality inspection gate at receiving (formal NCR/CAPA)** · seen in: Oracle, Infor (QC before putaway) ·
  priority: common · spine: `GoodsReceiptLine.quantity_rejected`/`rejection_reason` already cover the basic
  accept/reject; a full inspection-criteria/NCR workflow is **4.9 QMS / Module 12** territory (already flagged
  in `research-scm.md`) · parked, belongs to 4.9/Module 12

## Recommended build scope (this pass — 4 new models + 2 extensions to existing spine)

### New models
1. **`PutawayTask`** [`PUT-`] — serves **Inbound Operations**. Fields: `goods_receipt_line→scm.GoodsReceiptLine`
   (PROTECT — traceability back to the exact GRN line), `item→scm.Item` (PROTECT — **user-resolved** at task
   creation, pre-filled by matching `goods_receipt_line.po_line.sku_hint` to an `Item.sku` when one exists; see
   "Dependency gap" below for why this can't be a clean auto-FK yet), `lot_serial→scm.LotSerial` (nullable),
   `quantity`, `unit_cost` (carried from the PO line's `unit_price`, feeds `StockMove.unit_cost`),
   `from_location→scm.Location` (PROTECT — the staging/dock location the receipt posted into),
   `suggested_location→scm.Location` (PROTECT, nullable — simple rule-based suggestion: the item's existing bin,
   else the emptiest bin in its category's zone), `to_location→scm.Location` (PROTECT — the confirmed bin,
   defaults to `suggested_location` but is editable), `strategy` (`directed/fixed/random/cross_dock`), `status`
   (`pending/putaway/cancelled`), `putaway_by`, `putaway_at`. `TenantNumbered`. Confirming posts a paired
   `StockMove` (`move_type='transfer'`) from `from_location` to `to_location` via the existing
   `_post_stock_move()` helper. Justified by: directed/fixed/random/cross-dock putaway strategies (Manhattan,
   Infor, Oracle, Blue Yonder). FKs: `scm.GoodsReceiptLine`, `scm.Item`, `scm.LotSerial`, `scm.Location` (all
   verified existing).

2. **`PickTask`** [`PIK-`] + **`PickTaskLine`** — serves **Outbound Operations**. Header: `transfer→
   scm.StockTransfer` (**required this pass** — the only real outbound-triggering document that exists; see
   "Outbound-demand stand-in" below), `wave_number` (free text/char — the wave/batch grouping key, not a
   separate wave-release table), `strategy` (`wave/batch/zone/discrete`), `assigned_to`, `status`
   (`pending/picking/picked/short/cancelled`), `picked_at`; packing fields folded onto the header:
   `carton_count`, `package_weight`, `package_dimensions`, `tracking_number` (free-text label-data placeholder,
   the TMS hand-off point), `packed_at`, `packed_by`. `TenantNumbered`. Line: `item→scm.Item`,
   `lot_serial→scm.LotSerial` (nullable), `from_location→scm.Location`, `quantity_requested`,
   `quantity_picked`. **`PickTask` does NOT post `StockMove` itself** — it is a pure execution/workflow layer;
   marking it `picked` is the precondition that unlocks completing the linked `StockTransfer`, whose own
   `_post_transfer()` posts the real ledger move (avoids inventing a second issue-posting path). Justified by:
   wave/batch/zone picking (NetSuite, Softeon, Manhattan), short-pick handling (all 10), pick-path sequencing via
   `from_location.pick_sequence` (Manhattan, Blue Yonder), packing/label-data (Fishbowl). FKs: `scm.StockTransfer`,
   `scm.Item`, `scm.LotSerial`, `scm.Location` (all verified existing).

3. **`CycleCountTask`** [`CC-`] + **`CycleCountTaskLine`** — serves **Cycle Counting**. Header:
   `location→scm.Location` (PROTECT — the zone or bin being counted, the "specific inventory section"),
   `count_date`, `count_method` (`manual/abc_scheduled`), `status`
   (`scheduled/counting/completed/cancelled`), `assigned_to`, `notes`. `TenantNumbered`. Line: `item→scm.Item`,
   `lot_serial→scm.LotSerial` (nullable), `system_quantity` (snapshotted from `Item.on_hand(location)` at line
   creation), `counted_quantity` (nullable until counted), `needs_recount` (boolean). `variance` is a computed
   property (`counted_quantity - system_quantity`), never stored. `finalize()` creates one
   `scm.StockAdjustment(reason='cycle_count')` + one `StockAdjustmentLine` per non-zero-variance line and posts
   it through the **existing** `_post_adjustment()` helper — the count task never writes `StockMove` itself.
   Justified by: scheduled section counting without halting operations (all 10), system-vs-counted variance
   (NetSuite Smart Count, SAP EWM, Oracle), ABC-driven scheduling as a bulk-create action (Körber, Infor,
   Oracle). FKs: `scm.Location`, `scm.Item`, `scm.LotSerial`, `scm.StockAdjustment` (the object it creates, not
   an inbound FK — all verified existing).

4. **`YardVisit`** [`YRD-`] — serves **Yard Management** and the dock-scheduling half of **Inbound Operations**.
   Fields: `visit_type` (`inbound/outbound`), `purchase_order→scm.PurchaseOrder` (PROTECT, nullable — the
   inbound reference; verified existing 4.1 model, NOT `crm.PurchaseOrder`), `reference` (free text — the
   outbound placeholder, since no `Shipment`/TMS exists yet), `carrier_name`, `driver_name`, `vehicle_plate`,
   `trailer_number` (all free text — a real carrier master is 4.6 TMS territory), `dock_door→scm.Location`
   (PROTECT, nullable — reuses `location_type='staging'`, no new choice needed), `scheduled_at`,
   `checked_in_at`, `checked_out_at`, `status`
   (`scheduled/checked_in/at_dock/departed/cancelled`), `notes`. `TenantNumbered`. No `StockMove` posting — this
   is a pure visit/appointment log; the actual receipt posts when the GRN tied to the visit's PO is booked (see
   wire-up below). Justified by: dock/door appointment scheduling (SAP EWM, Softeon, Opendock-class), truck/
   trailer check-in/out with dwell time (all YMS surveyed). FKs: `scm.PurchaseOrder`, `scm.Location` (verified
   existing).

### Extensions to existing spine models (not new tables)
5. **Extend `scm.Location`** (4.3, existing) — add `capacity_qty` (nullable decimal), `pick_sequence` (nullable
   integer), `abc_class` (nullable choice `A/B/C`). Justified by: bin capacity + pick-path sequencing + ABC
   slotting/cycle-count-frequency driver (all researched leaders). This is exactly the extension the task brief
   pre-authorized, keeping `Location` the one bin/layout master.
6. **Extend `scm.GoodsReceiptNote`** (4.1, existing) — add `location→scm.Location` (PROTECT, nullable, default
   the tenant's first `location_type='staging'` row — required before `mark_received` can post). Necessary glue:
   without knowing *which* staging location the goods arrived at, `PutawayTask.from_location` has nothing to
   move out of.

### Wire-up (closes the stale 4.1 TODO, no new model)
- **`goodsreceipt_receive` (4.1 view) posts a `receipt`-type `StockMove`** into `GoodsReceiptNote.location` via
  the existing `_post_stock_move()` helper, inside the same `transaction.atomic()` block that flips
  `status → 'received'`. This finally closes the gap `research-scm-4.3.md`'s Deferred section named and the
  view's own stale L28 comment describes — 4.4 is the right pass to do it because `PutawayTask` has nothing to
  move without it. Update the stale docstring/comment in the same change.

### Dependency gap to flag explicitly (not fixed this pass)
- **`PurchaseOrderLine`/`GoodsReceiptLine` are still free-text** (`item_description`/`sku_hint`, no
  `item→scm.Item` FK) — `research-scm-4.3.md` already deferred backfilling this. `PutawayTask.item` works
  around it by having the user **resolve** the real `Item` at putaway time (pre-filled by a `sku_hint`→`Item.sku`
  match when one exists), rather than trusting a nonexistent FK. This is now needed by **two** sub-modules
  (4.3's valuation depth and 4.4's putaway) — flag it as increasingly overdue for whoever next touches 4.1, but
  it is explicitly **not** in this pass's scope (no 4.1 model changes beyond the one `GoodsReceiptNote.location`
  field above).

### Outbound-demand stand-in (not fixed this pass)
- **No `SalesOrder`/OMS exists yet** (Module 8 / 4.5, both unbuilt). `PickTask` uses the existing
  `scm.StockTransfer` as its outbound trigger this pass (a transfer's `from_location` genuinely needs picking —
  it's real outbound demand, just inter-warehouse rather than to-a-customer). **Deferred:** once
  Module 8/4.5 lands a real order, add a nullable `sales_order` FK alongside `transfer` (relax `transfer` to
  nullable too) so `PickTask` can serve either source without a schema rewrite.

## Belongs to sibling sub-modules (parked, not scoped here)

- **Carrier master, rate cards, freight audit, real GPS shipment tracking, load/cube optimization** → 4.6
  Transportation Management System (TMS, not built). This pass's `PickTask.tracking_number` and `YardVisit`'s
  free-text carrier fields are the data hand-off boundary, nothing more.
- **Order capture/validation/allocation/backorder handling/customer notifications** → 4.5 Order Management
  System (OMS, not built) and Module 8 Sales. `PickTask.transfer` is the stand-in outbound trigger until a real
  `SalesOrder` exists.
- **Labor-standards/incentive engine, warehouse workforce scheduling** → 4.14 Labor Management (overlaps HRM,
  Module 3, already built) — already flagged in `research-scm.md`. This pass's task `assigned_to`/timestamps are
  enough for a basic productivity report, not a labor-management system.
- **Formal quality inspection (criteria, NCR, CAPA) at receiving** → 4.9 Quality Management System / Module 12
  (already flagged in `research-scm.md` as needing to stay thin in SCM). `GoodsReceiptLine.quantity_rejected`/
  `rejection_reason` (4.1, existing) already cover the basic accept/reject gate this pass relies on.
  
- **3PL client billing (per-storage-volume/transaction charges, dedicated vs. shared warehouse rental)** →
  4.17 Third-Party Logistics (3PL) Management (already flagged in `research-scm.md`). Yard/dock visits captured
  here are operational, not billing.
- **Self-service carrier appointment portal (external driver/dispatcher login)** → integration/later, same L32
  pattern as 4.1's Vendor Portal — no externally-authenticated login this pass.
- **Landed cost (freight/duty/insurance rolled into unit cost) and GL posting of inventory value** → 4.18
  Finance & Accounting Integration (already flagged in `research-scm-4.3.md`). `PutawayTask.unit_cost` this pass
  is just the PO/GRN unit price, no landed-cost allocation.

## Deferred (later passes / integrations)

- **AI/ML dynamic slotting and "chained moves" re-slotting** (Manhattan, Blue Yonder, Deposco tier) — needs
  velocity/demand history over `StockMove`; this pass's `PutawayTask.suggested_location` is a simple same-item/
  emptiest-bin-in-zone rule, not ML.
- **Task interleaving** (combining a putaway and a pick in one aisle pass) — a scheduling-engine feature that
  needs both `PutawayTask` and `PickTask` to exist and mature first.
- **Full wave-release/labor-balancing engine** — this pass folds "wave" into a plain `PickTask.wave_number`
  grouping key; a real wave-planning table (release throttling, per-DC constraints, labor balancing across
  zones — Softeon/Oracle tier) is a legitimate v2.
- **Configurable removal strategy (FIFO/LIFO/FEFO) as a first-class rule** — this pass only defaults picks to
  nearest-expiry-first when an item is lot-tracked; a full per-item/per-warehouse configurable removal-strategy
  engine (Odoo tier) is deferred.
- **Bin capacity enforcement** — `Location.capacity_qty` is captured this pass but not enforced (no hard block
  when a putaway would overfill a bin).
- **ABC-driven recurring cycle-count scheduler (a calendar/program)** — this pass supports a manual "bulk-create
  counts for all A-class bins" action, not an automatic recurring schedule.
- **Pick-to-zero → automatic cycle count** — hooking a `PickTask` that empties a bin into an automatic
  `CycleCountTask` (Oracle's pattern) is a natural v2 integration, not built this pass.
- **Carrier-rate shopping, label PDF/ZPL rendering, tracking-number sync** — 4.6 TMS; this pass stops at
  `PickTask.tracking_number` as a free-text field.
- **Voice-directed picking / RF-scanner hardware UX** — the data model (`PickTask`/`PutawayTask`) supports it;
  the scan/voice hardware interaction is a later mobile/PWA integration.
- **Live yard map, drag-and-drop trailer assignment, GPS/RFID asset tracking** — presentation/hardware layer
  over `YardVisit`, not a schema concern this pass.
- **Self-service carrier appointment portal** — integration/later (external auth), same posture as 4.1's Vendor
  Portal.
- **`item→scm.Item` backfill on `PurchaseOrderLine`/`GoodsReceiptLine`** — still not done; `PutawayTask.item`
  works around it via user resolution this pass, but this is now overdue across two sub-modules.
- **`sales_order` FK on `PickTask`** — add once Module 8/4.5 OMS lands a real order to pick against.

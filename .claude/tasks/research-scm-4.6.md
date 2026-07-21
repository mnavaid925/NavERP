# Research — Sub-module 4.6: Transportation Management System (TMS) (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **LIVE_LINKS built so far in module 4:** `4.1` (Procurement: PurchaseRequisition/RFQ/RFQQuote/PurchaseOrder/
  GoodsReceiptNote), `4.2` (SRM: SupplierProfile/SupplierScorecard/SupplierContract/SupplierCatalog/
  SupplierRiskAssessment), `4.3` (Inventory: Item/UOM/Location/StockMove/LotSerial), `4.4` (WMS:
  PutawayTask/PickTask/CycleCountTask/YardVisit), `4.5` (OMS: SalesOrder/SalesOrderLine/SalesOrderAllocation).
  `4.6` has **no** `LIVE_LINKS` entry — confirmed the target of this pass.
- **Sibling models verified available to FK (grep evidence):**
  - `apps/core/models/Party.py:5 class Party` and `apps/core/models/PartyRole.py:5 class PartyRole` — exist.
    `PartyRole.ROLE_CHOICES` = customer/vendor/supplier/employee/lead/candidate/contact/partner — **no
    "carrier" role**, and none is proposed here (L29-style rule against duplicating role machinery); a 3PL
    carrier is a `Party` most naturally holding the existing `vendor` or `partner` role.
  - `apps/scm/models/OrderManagement/SalesOrders.py:20 class SalesOrder(TenantNumbered)` — exists, `NUMBER_PREFIX
    = "SO"`, has `customer`, `ship_to_address→core.Address`, `status`, notification hook fields
    (`shipped_notification_at` etc.) already anticipating a downstream shipment.
  - `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15 class PurchaseOrder(TenantNumbered)` and
    `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:15 class GoodsReceiptNote(TenantNumbered)` —
    both exist (`NUMBER_PREFIX = "PO"` / `"GRN"`); `GoodsReceiptNote.bill→accounting.Bill` is the exact
    three-way-match precedent this pass's freight-audit hand-off follows.
  - `apps/accounting/models/AccountsPayable/Bills.py:6 class Bill(TenantNumbered)`,
    `.../Payments.py:6 class Payment(TenantNumbered)`, `.../GeneralLedger/JournalEntries.py:5 class
    JournalEntry(TenantNumbered)` — all exist; accounting owns the ledger (L29). TMS records the freight
    audit/approval and FKs a draft `Bill` by string; it never posts a JE or a second Payment record itself.
  - `apps/scm/models/InventoryManagement/Locations.py:10 class Location(TenantOwned)` and
    `apps/scm/models/WarehouseManagement/YardVisits.py:14 class YardVisit(TenantNumbered)` — exist.
    `YardVisit` already carries free-text `carrier_name`, `driver_name`, `vehicle_ref`, `trailer_ref` with an
    explicit code comment: *"a real Carrier master belongs to 4.6 TMS, which isn't built. When it lands this
    gains a nullable FK rather than being rebuilt."* This pass's `Carrier` model is that landing point, though
    migrating `YardVisit`'s free-text fields to the new FK is left for a future pass (out of scope here — see
    Deferred).
  - `apps/scm/models/InventoryManagement/Items.py:56 class Item(TenantOwned)` — exists but **has no
    weight/volume/dimension fields** (grepped; only `sku`, `name`, `item_type`, `tracking`, `costing_method`,
    cached unit cost). Cube-optimization inputs (weight/volume) therefore cannot be derived from `Item` yet —
    this pass captures them as **shipment/load-level fields**, not a new `Item` dimension catalog (that
    belongs to whichever pass extends `Item` for physical attributes).
- **Spine entities verified NOT to exist (no `Carrier`/`Shipment`/`Load`/`TrackingEvent`/`FreightInvoice`
  anywhere under `apps/`):** confirms this sub-module is a clean build, nothing to extend.
- **`core.Address`** (`apps/core/models/Address.py:5`) is owned by a `Party` (`party` FK, not generic) — usable
  for `SalesOrder.ship_to_address`-style reuse, but a shipment's origin/destination is sometimes a bare
  warehouse/dock address with no `Party` owner, so this pass keeps address fields **nullable FK + free-text
  fallback**, mirroring `PurchaseOrder.delivery_address` (plain `TextField`) rather than forcing every stop
  through the Party-owned address book.
- **Sibling research files** (`research-scm-4.4.md`, `research-scm-4.5.md`) both explicitly deferred "Carrier
  master, rate cards, freight audit, real GPS shipment tracking, load/cube optimization" to 4.6 and named the
  hand-off placeholders they left behind (`YardVisit.carrier_name`, `PickTask.tracking_number`,
  `SalesOrder.shipped_notification_at`/`delivered_notification_at`). This pass is where those placeholders get
  a real home — the starting backlog for 4.6 is exactly the five NavERP.md bullets below.

## Leaders surveyed (with source links)

1. **Oracle Transportation Management (OTM)** — enterprise multi-modal TMS; planning, routing, consolidation,
   freight payment & audit, execution and visibility in one suite — [oracle.com/scm/logistics/transportation-management](https://www.oracle.com/scm/logistics/transportation-management/)
2. **SAP Transportation Management (SAP TM / S/4HANA)** — freight order/settlement engine with calculation
   sheets, freight agreements and carrier contract-driven charge calculation — [SAP Freight Settlement help](https://help.sap.com/docs/SAP_TRANSPORTATION_MANAGEMENT/54cf405c9d9e4c96bf091967ea29d6a7/7eb8bdf270d84b16ab8a755d09b11e81.html), [sap.com/products/scm/transportation-logistics](https://www.sap.com/products/scm/transportation-logistics.html)
3. **Manhattan Active Transportation Management** — cloud-native, continuously-optimizing carrier
   selection/routing/load-building, Gartner Magic Quadrant Leader — [manh.com TMS](https://www.manh.com/solutions/supply-chain-management-software/transportation-management)
4. **MercuryGate TMS** — multimodal (parcel/LTL/TL/air/ocean/rail) rate + route optimization with carrier
   tendering, dock scheduling, freight audit and settlement in one workflow — [ERP Research MercuryGate](https://www.erpresearch.com/erp-add-ons/tms/mercurygate)
5. **Descartes Transportation Management (3G TMS)** — load planning, route optimization, carrier selection,
   rate management, freight audit/settlement (self-billing, e-invoicing, match-pay) — [descartes.com TMS](https://www.descartes.com/solutions/transportation-management/tms)
6. **project44** — multimodal real-time visibility platform (truckload/LTL/ocean/rail), 1,400+ telematics
   integrations, predictive ETAs — [FreightAmigo project44 vs FourKites comparison](https://www.freightamigo.com/en/blog/logistics/fourkites-vs-project44-feature-comparison/)
7. **FourKites** — real-time GPS/ELD visibility, ML-driven predictive ETA, dock/yard visibility, carbon
   tracking — same comparison source above
8. **Trax Technologies** — freight audit & payment specialist; ingests/normalizes carrier invoices, AI-driven
   invoice validation against contracted rates, spend analytics, automated payment cycles — [traxtech.com/products/freight-audit](https://www.traxtech.com/products/freight-audit)
9. **Cube-IQ (MagicLogic)** — 3D load/cube optimization specialist: pallet/truck/container load planning,
   weight distribution, axle-load compliance, interactive drag-and-drop — [magiclogic.com/products/cube-iq](https://magiclogic.com/products/cube-iq/)
10. **EasyCargo** — cloud-based 3D load optimization (truck/container/pallet), automatic space/weight/axle
    optimization with manual override — surveyed via [gitnux.org best load optimization software 2026](https://gitnux.org/best/load-optimization-software/)
11. **Route4Me** — last-mile/multi-stop route optimization engine, 3B+ miles optimized, fuel/time-focused
    routing — [onfleet.com/route4me-vs-onfleet](https://onfleet.com/route4me-vs-onfleet)
12. **Kuebix (Trimble/FreightWise) & Uber Freight** — carrier rate-card/digital-freight-marketplace pattern:
    web-service rate integrations, side-by-side carrier comparison, contract-rate + spot-rate management — [kuebix.com/carrier-network](https://www.kuebix.com/carrier-network/), [selecthub.com Uber Freight](https://www.selecthub.com/p/tms-software/uber-freight/)

## Feature catalog (this sub-module only)

### Route Planning
- **Multi-stop route sequencing** — order pickup/delivery stops to minimize distance/time · seen in: OTM, SAP TM,
  Manhattan, Descartes, Route4Me · priority: table-stakes · spine: new table `LoadStop` (child of `Load`) ·
  buildable now
- **Distance/fuel/time estimate per route** — headline routing-cost estimate surfaced before dispatch · seen in:
  Route4Me, Onfleet, Manhattan · priority: common · spine: `Load.distance_km` / `estimated_fuel_cost` (stored
  estimate, not live map routing) · buildable now (the estimate is a manually-entered/derived number this pass;
  live map-based route optimization is integration/later)
- **Live traffic-aware route optimization (map/routing engine)** — real-time recompute against traffic/weather ·
  seen in: Route4Me, Onfleet, Manhattan Continuous Optimization · priority: differentiator · spine: none (needs
  an external routing/maps API) · integration/later
- **Carrier/vehicle assignment to a planned route** — who executes this route · seen in: all surveyed · priority:
  table-stakes · spine: `Load.carrier → scm.Carrier` (new, FKs verified `core.Party`) · buildable now

### Freight Audit & Payment
- **3-way freight match (bill vs. contract rate vs. shipment)** — verify carrier invoice line-items against the
  agreed rate card before approving · seen in: OTM, SAP TM (freight settlement), Descartes, Trax · priority:
  table-stakes · spine: new table `FreightInvoice`/`FreightInvoiceLine`, matched against new `CarrierRateCard`;
  hands off to **verified-existing** `accounting.Bill` by nullable FK (mirrors `GoodsReceiptNote.bill` — three-way
  match precedent already in this codebase) · buildable now (the match/variance math); actual payment posting
  stays in accounting (L29)
- **Charge-level variance breakdown (linehaul/fuel/accessorial/detention)** — line-item audit, not just an
  invoice total · seen in: SAP TM calculation sheets, Trax, MercuryGate · priority: common · spine:
  `FreightInvoiceLine.charge_type` + `variance_amount` · buildable now
- **Dispute / exception workflow with approval gate** — hold a variant invoice for review before it becomes
  payable · seen in: Trax, OTM, SAP TM · priority: common · spine: `FreightInvoice.match_status` +
  `approval_status` (mirrors `GoodsReceiptNote.MATCH_STATUS_CHOICES` pattern already verified in this repo) ·
  buildable now
- **Automated invoice ingestion (EDI/PDF/e-invoice) + AI validation** — Trax processes carrier invoices at scale
  with ML-trained validation · seen in: Trax, OTM · priority: differentiator · spine: none · integration/later
  (this pass supports a manually-entered `FreightInvoice`, not automated ingestion)
- **Fuel surcharge / accessorial schedule maintenance** — carrier-specific surcharge tables feeding the audit
  baseline · seen in: SAP TM, MercuryGate, Kuebix · priority: common · spine: `CarrierRateCard.fuel_surcharge_pct`
  · buildable now

### Carrier Management
- **Carrier master with compliance identifiers (SCAC, MC/DOT number)** — standard carrier identity fields · seen
  in: all enterprise TMS surveyed · priority: table-stakes · spine: new table `Carrier`, FKs **verified**
  `core.Party` by string (vendor/partner role) — not a duplicate customer/vendor table (guardrail honored) ·
  buildable now
- **Rate cards / contract rates per lane, mode, equipment** — the negotiated pricing a carrier's shipments are
  audited against · seen in: SAP TM (freight agreements + calculation sheets), MercuryGate, Kuebix, Descartes ·
  priority: table-stakes · spine: new child table `CarrierRateCard` (FK `accounting.Currency`, verified existing)
  · buildable now
- **Carrier scorecarding (on-time %, damage rate, responsiveness)** — ongoing performance evaluation, same
  pattern as 4.2's `SupplierScorecard` · seen in: Manhattan, MercuryGate, OTM · priority: common · spine: derived
  `Carrier.on_time_delivery_pct` recomputed from `Shipment` history (mirrors `SupplierScorecard.
  recompute_from_signals`, verified existing pattern in `apps/scm/models/SupplierRelationshipManagement/`) ·
  buildable now
- **Mode/service-level capability (TL/LTL/parcel/ocean/air/rail, expedited/standard)** — what a carrier is
  contracted to move · seen in: MercuryGate, OTM, SAP TM · priority: table-stakes · spine: `Carrier.primary_mode`
  choice field (a full mode-capability matrix is deferred — see Deferred) · buildable now
- **Carrier tendering / spot-rate auction / digital freight marketplace** — shop a load to multiple carriers and
  auto-award · seen in: Uber Freight, Kuebix · priority: differentiator · spine: none (needs external carrier
  network integration) · integration/later
- **Insurance / compliance document tracking (COI, authority expiry)** — risk/compliance on the carrier record,
  same shape as 4.2's `SupplierRiskAssessment` · seen in: SAP TM, OTM · priority: common · spine:
  `Carrier.insurance_certificate_expiry` field this pass; a full risk-assessment child table is deferred to stay
  in scope · buildable now (field only)

### Shipment Tracking
- **Real-time GPS/ELD in-transit tracking with predictive ETA** — the headline feature of project44/FourKites ·
  seen in: project44, FourKites, Descartes, Manhattan · priority: table-stakes (for a modern TMS) · spine: new
  table `TrackingEvent` (child of `Shipment`) capturing `latitude`/`longitude`/`event_at`/`source`; actual
  carrier-GPS/ELD feed ingestion is integration/later — this pass stores whatever events a user/API posts ·
  buildable now (the event log) / integration/later (the live GPS feed itself)
- **Status milestone timeline (picked up → departed → in transit → delivered → POD)** — the event stream a
  shipment's status derives from · seen in: all visibility platforms · priority: table-stakes · spine:
  `TrackingEvent.event_type` choices + `Shipment.status`/`current_status_text`/`eta` summary fields updated from
  the latest event · buildable now
- **Proof of delivery (POD) capture** — signed delivery confirmation · seen in: project44, FourKites, Descartes ·
  priority: common · spine: `Shipment.pod_received` / `pod_received_at` fields this pass; actual e-signature/photo
  capture is integration/later · buildable now (flag only)
- **Exception/delay alerting** — flag a shipment falling behind its ETA · seen in: project44, FourKites ·
  priority: common · spine: `TrackingEvent.event_type = 'exception'/'delayed'` this pass; automated alert dispatch
  (email/SMS) is integration/later, same posture as 4.5's notification hook fields · buildable now (data hook) /
  integration/later (dispatch)
- **Carbon/emissions tracking per shipment** — FourKites differentiator · seen in: FourKites · priority:
  differentiator · spine: none this pass · deferred

### Load Optimization
- **3D cube/weight load planning (pallet/truck/container)** — maximize space utilization, weight distribution,
  axle-load compliance · seen in: Cube-IQ, EasyCargo, MercuryGate · priority: differentiator (true 3D bin-packing
  is a specialist niche, not universal even among enterprise TMS) · spine: new table `Load` capturing aggregate
  `planned_weight_kg`/`planned_volume_cbm` vs. `equipment_capacity_weight_kg`/`equipment_capacity_volume_cbm` with
  derived `weight_utilization_pct`/`volume_utilization_pct` — a **capacity-vs-planned aggregate**, not true 3D
  bin-packing (no interactive 3D visualization this pass; see Deferred) · buildable now (aggregate math) /
  integration/later (true 3D packing engine)
- **Load consolidation (multiple orders/shipments onto one truck/route)** — the operational unit a route actually
  executes, distinct from the customer-facing shipment · seen in: OTM, SAP TM, MercuryGate, Manhattan · priority:
  common (all enterprise TMS separate "load"/"freight order" from "shipment order") · spine: `Shipment.load →
  scm.Load` nullable FK, multiple shipments consolidate onto one `Load` · buildable now
- **Equipment/vehicle capacity profiles** — dry van vs. reefer vs. flatbed vs. container capacity specs feeding
  the utilization calc · seen in: Cube-IQ, EasyCargo, MercuryGate · priority: table-stakes (for cube math to mean
  anything) · spine: `Load.equipment_type` choice + capacity fields this pass; a reusable equipment-type capacity
  lookup table is deferred (kept as plain fields to stay within the model budget) · buildable now
- **Interactive 3D drag-and-drop load diagram** — Cube-IQ/EasyCargo's visual palletizing tool · seen in: Cube-IQ,
  EasyCargo · priority: differentiator · spine: none · integration/later (a genuine 3D packing UI is out of scope
  for a Django/HTMX CRUD pass)

## Recommended build scope (this pass — 1–4 models)

1. **`Carrier`** [`CAR-`] + child **`CarrierRateCard`** — serves **Carrier Management** (+ feeds the audit
   baseline for Freight Audit & Payment). Fields: `party → core.Party` (`PROTECT`, verified existing — the
   carrier's vendor/partner `PartyRole`), `carrier_type` (asset_based/broker/3pl), `scac_code`, `mc_number`,
   `dot_number`, `primary_mode` (truckload/ltl/parcel/ocean/air/rail/intermodal/courier), `service_level`
   (standard/expedited/economy), `insurance_certificate_expiry`, `on_time_delivery_pct` (derived, `editable=False`,
   recomputed from `Shipment` history — mirrors verified `SupplierScorecard` pattern), `is_preferred`, `status`
   (active/inactive/suspended), `notes`. `TenantNumbered`. Child `CarrierRateCard`: `carrier` (`CASCADE`),
   `origin_region`/`destination_region` (free text — no geo-zone master exists), `mode`, `equipment_type`,
   `rate_basis` (per_mile/per_kg/per_cbm/flat/per_pallet), `base_rate`, `fuel_surcharge_pct`, `currency →
   accounting.Currency` (`SET_NULL`, verified existing), `min_charge`, `effective_from`/`effective_to`,
   `is_active`. FKs: `core.Party` (verified), `accounting.Currency` (verified).

2. **`Load`** [`LD-`] + child **`LoadStop`** — serves **Route Planning** and **Load Optimization**. Fields:
   `carrier → scm.Carrier` (`SET_NULL`, nullable until tendered), `mode`, `equipment_type` (dry_van/reefer/
   flatbed/container/parcel), `status` (planning/tendered/booked/in_transit/delivered/cancelled),
   `planned_departure`/`planned_arrival`, `actual_departure`/`actual_arrival` (`editable=False`),
   `origin_address`/`destination_address → core.Address` (nullable) + `origin_text`/`destination_text` fallback
   (mirrors `PurchaseOrder.delivery_address` free-text pattern since not every dock has a `Party`-owned address),
   `distance_km`, `estimated_fuel_cost`, `equipment_capacity_weight_kg`, `equipment_capacity_volume_cbm`,
   `planned_weight_kg`/`planned_volume_cbm` (derived aggregate from assigned `Shipment`s, `editable=False`),
   `weight_utilization_pct`/`volume_utilization_pct` (derived properties — the cube-utilization headline number),
   `freight_cost_estimate`, `driver_name`/`vehicle_ref` (free text — same stand-in posture as `YardVisit` until a
   fleet/vehicle master exists), `notes`. `TenantNumbered`. Child `LoadStop`: `load` (`CASCADE`), `sequence`,
   `stop_type` (pickup/delivery/cross_dock/fuel), `address → core.Address` (nullable) + `address_text`,
   `planned_arrival`/`actual_arrival`, `status`. FKs: `scm.Carrier` (this pass), `core.Address` (verified).

3. **`Shipment`** [`SHP-`] + child **`TrackingEvent`** — serves **Shipment Tracking** (+ the customer/GRN-facing
   anchor for the other four bullets). Fields: `direction` (outbound/inbound), `sales_order → scm.SalesOrder`
   (`SET_NULL`, nullable, verified existing — outbound), `purchase_order → scm.PurchaseOrder` (`SET_NULL`,
   nullable, verified existing — inbound), `carrier → scm.Carrier` (`SET_NULL`, nullable — direct assignment for
   shipments not consolidated onto a `Load`), `load → scm.Load` (`SET_NULL`, nullable — consolidation),
   `ship_from_address`/`ship_to_address → core.Address` (nullable, reuses the same pattern as
   `SalesOrder.ship_to_address`), `mode`, `status` (planned/tendered/booked/in_transit/delivered/exception/
   cancelled), `planned_pickup_date`/`planned_delivery_date`, `actual_pickup_at`/`actual_delivery_at`
   (`editable=False`), `weight_kg`/`volume_cbm`/`package_count` (captured here since `scm.Item` has no cube
   dimensions yet — a stand-in, same posture as 4.1's pre-`Item` line fields), `carrier_tracking_number`,
   `current_status_text`/`last_known_location`/`eta` (`editable=False`, updated from the latest `TrackingEvent`),
   `pod_received`/`pod_received_at`, `freight_cost_estimate`, `notes`. `TenantNumbered`. Child `TrackingEvent`:
   `shipment` (`CASCADE`), `event_type` (pickup/departed_origin/in_transit/arrived_destination/customs_hold/
   exception/delayed/out_for_delivery/delivered/pod_signed), `event_at`, `location_text`, `latitude`/`longitude`
   (nullable decimals), `source` (manual/carrier_api/edi/driver_app/gps_ping), `recorded_by → settings.AUTH_USER_MODEL`
   (nullable), `notes`. FKs: `scm.SalesOrder`, `scm.PurchaseOrder`, `scm.Carrier`, `scm.Load`, `core.Address` (all
   verified existing or built this pass).

4. **`FreightInvoice`** [`FRT-`] + child **`FreightInvoiceLine`** — serves **Freight Audit & Payment**. Fields:
   `carrier → scm.Carrier` (`PROTECT`, this pass), `load → scm.Load` (`SET_NULL`, nullable — most carrier
   invoices bill per trip/load), `shipment → scm.Shipment` (`SET_NULL`, nullable — for direct/parcel shipments
   not consolidated), `carrier_invoice_number`, `invoice_date`, `due_date`, `currency → accounting.Currency`
   (`SET_NULL`, verified existing), `billed_amount`, `contract_amount` (looked up against `CarrierRateCard`, the
   audit baseline), `variance_amount`/`variance_pct` (`editable=False`, derived), `match_status` (not_matched/
   matched/price_variance/duplicate/disputed — mirrors verified `GoodsReceiptNote.MATCH_STATUS_CHOICES`),
   `dispute_reason`, `approval_status` (pending/approved/rejected), `approved_by → settings.AUTH_USER_MODEL`
   (nullable), `approved_at` (`editable=False`), `bill → accounting.Bill` (`SET_NULL`, nullable, verified
   existing — the hand-off point; TMS never posts its own JE/Payment, L29), `notes`. `TenantNumbered`. Child
   `FreightInvoiceLine`: `freight_invoice` (`CASCADE`), `charge_type` (linehaul/fuel_surcharge/accessorial/
   detention/demurrage/tolls/other), `description`, `billed_amount`, `contract_amount`, `variance_amount`
   (`editable=False`, derived). FKs: `scm.Carrier`, `scm.Load`, `scm.Shipment`, `accounting.Currency`,
   `accounting.Bill` (all verified existing or built this pass).

All four FK only into **verified-existing** entities (`core.Party`, `core.Address`, `accounting.Currency`,
`accounting.Bill`, `scm.SalesOrder`, `scm.PurchaseOrder`) plus each other — no hard FK to an unbuilt master.
`scm.Item`'s missing weight/volume fields are the one stand-in: cube inputs live on `Shipment`/`Load` this pass,
same posture 4.1 used for line items before `Item` existed (L28).

## Belongs to sibling sub-modules (parked, not scoped here)

- **Shipping-label rendering (PDF/ZPL) and carrier-rate shopping at pack time** → already the 4.4 hand-off point
  (`PickTask.tracking_number`); this pass's `Shipment`/`Load` are what that field will eventually FK once built,
  but rendering the label itself is integration/later, not a 4.6 model.
- **Reorder-point / automated PO generation from a transportation delay** → 4.3/4.7 territory, not 4.6.
- **Return shipment / reverse-logistics pickup scheduling** → 4.10 Returns Management (Reverse Logistics) — a
  return shipment can reuse this pass's `Shipment` by direction later, but RMA/disposition workflow itself is
  4.10's job.
- **Carbon footprint / sustainability reporting across the transportation network** → 4.11 Supply Chain
  Analytics and 4.12 Contract & Compliance Management (Sustainability Tracking bullet) — this pass stores raw
  distance/fuel-estimate fields that a later analytics pass can aggregate, but no dashboard/report is built here.
- **Import/export trade documentation (Bill of Lading, Commercial Invoice, HazMat compliance)** → 4.12 Contract &
  Compliance Management (Trade Documentation bullet) — out of scope for 4.6's shipment/carrier/audit core.
- **Yard/dock-door scheduling detail** → already owned by 4.4's `YardVisit`; 4.6 does not re-model dock
  appointments, only consumes carrier/shipment identity that `YardVisit` currently free-texts.

## Deferred (later passes / integrations)

- **Live GPS/ELD/telematics feed ingestion** (project44/FourKites-style) — `TrackingEvent` stores whatever is
  posted; wiring an actual carrier-GPS or ELD API is an integration, not a data-model concern.
- **True 3D bin-packing / interactive load diagram** (Cube-IQ/EasyCargo) — this pass computes aggregate
  weight/volume utilization percentages only; a drag-and-drop 3D visualization is out of scope for Django/HTMX.
- **Map-based/traffic-aware route optimization engine** — `Load.distance_km`/`estimated_fuel_cost` are stored
  estimates this pass; live routing (Route4Me/Onfleet-style) needs an external maps/routing API.
- **Digital freight marketplace / spot-rate auction / carrier tendering** (Uber Freight, Kuebix) — needs an
  external carrier network; this pass's `Carrier`/`CarrierRateCard` support manually-entered contract rates only.
- **Automated freight-invoice ingestion (EDI/PDF/e-invoice) + AI variance validation** (Trax-style) — this pass's
  `FreightInvoice` is manually entered; automated ingestion/OCR is a later integration.
- **Full mode-capability matrix per carrier** (e.g. a `CarrierMode` join table for "TL + LTL + ocean") — this
  pass uses a single `primary_mode` choice field on `Carrier` to stay within the model budget; a proper
  many-to-many capability matrix is a natural extension, not a blocker.
- **Reusable equipment-type capacity lookup table** — `Load.equipment_capacity_weight_kg`/`_volume_cbm` are plain
  fields this pass rather than a normalized equipment-spec master; fine for MVP, revisit if equipment types
  proliferate.
- **Carrier compliance/risk-assessment child table** (COI documents, safety ratings, financial risk — mirroring
  4.2's `SupplierRiskAssessment`) — `Carrier.insurance_certificate_expiry` is a single field this pass; a full
  risk workflow is deferred to keep the build to 4 models.
- **Automated exception/delay alert dispatch (email/SMS)** — `TrackingEvent.event_type = 'exception'/'delayed'`
  is the data hook; actual notification dispatch follows the same "hook now, wire later" posture as 4.5's
  `SalesOrder.shipped_notification_at`.
- **Migrating `YardVisit`'s free-text `carrier_name`/`driver_name`/`vehicle_ref` to real `Carrier` FKs** — now
  possible since `Carrier` exists, but changing 4.4's already-shipped model is out of scope for this pass; leave
  a note for whoever revisits 4.4.

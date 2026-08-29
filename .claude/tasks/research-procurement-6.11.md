# Research — Sub-module 6.11: Order Fulfillment & Tracking (Module 6 — Procurement Management System, `procurement`)

Scope note: ONE sub-module. 6.10 PO Management (change orders / PO generation / line tracking) is being built by a
concurrent session and 6.12 Goods Receipt & Inspection is a LATER pass — features belonging to either are parked
below, not scoped here.

---

## Repo state checked first

**`LIVE_LINKS` already registered for Module 6** (`apps/core/navigation.py`, read at run time):
`6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10`. → **6.11 is the next unbuilt sub-module.** ✅

**Spine entities VERIFIED to exist** (`grep -rn "^class <Name>" apps/*/models/` — models are packages):

| Entity | Verified at | Notes for 6.11 |
|---|---|---|
| `scm.PurchaseOrder` | `apps/scm/models/ProcurementManagement/PurchaseOrders.py:15` | `[PO-]`, statuses incl. `sent/acknowledged/partially_received/received`; has `expected_date`, `promised_ship_date`, `acknowledged_at`, `ship_to`→`core.OrgUnit`. **Owns the order lifecycle — 6.11 must not re-declare or mutate it.** |
| `scm.PurchaseOrderLine` | `…/PurchaseOrders.py:172` | Free-text `item_description` + `sku_hint` + `uom_hint` (no item FK), `quantity`, `unit_price`. Has `received_quantity()` / `outstanding_quantity()` derived from GRN lines. |
| `scm.GoodsReceiptNote` / `GoodsReceiptLine` | `…/GoodsReceiptNotes.py:15,166` | `[GRN-]`, has `delivery_note_ref` (the vendor's delivery-note number — the ASN hand-off target) and the three-way match. **6.12's territory.** |
| `scm.Shipment` | `apps/scm/models/TransportationManagement/Shipments.py:22` | `[SHP-]`, **already has `direction="inbound"` and a `purchase_order` FK**, `carrier`, `carrier_tracking_number`, `planned_/actual_pickup_at`, `actual_delivery_at`, `eta`, `last_known_location`, `pod_received`. |
| `scm.TrackingEvent` | `…/Shipments.py:152` | Append-only milestone/GPS log; `SOURCE_CHOICES` already includes `carrier_api`, `edi`, `gps_ping`; `apply_tracking_event()` projects onto the shipment. |
| `scm.Carrier` | `…/Carriers.py:47` | `[CAR-]`, a TMS profile over a `core.Party`; SCAC/MC/DOT, modes, service levels. |
| `scm.Item`, `scm.UOM`, `scm.Location`, `scm.LotSerial` | `apps/scm/models/InventoryManagement/…` | Exist, but PO lines are free-text — see the item-master note below. |
| `core.Party`, `core.OrgUnit`, `core.Address`, `core.Document`, `core.AuditLog` | `apps/core/models/{Party,OrgUnit,Address,Document,AuditLog}.py` | Vendors are `Party` + `PartyRole`. Never a second vendor table. |
| `procurement.ProcurementAlert` | `apps/procurement/models/DashboardPortal/ProcurementAlerts.py:26` | 6.1's inbox; **already has `kind="delivery"`** — 6.11's late/short-shipment alerts raise INTO it, no new alert table. |
| `inventory.PurchaseOrderDispatch` | `apps/inventory/models/PurchaseOrderManagement/Dispatches.py:19` | `[PD-]` = **buyer → supplier** transmission log (email/EDI/print + message-id). The ASN is the **opposite direction**. No overlap. |
| `procurement.PurchaseOrderChange` / `…ChangeLine` | `apps/procurement/models/PurchaseOrderManagement/PurchaseOrderChanges.py:26,173` | 6.10 (concurrent build). Buyer-filed, admin-approved, mutates the spine's qty/price/date under a row lock. **6.11 never mutates PO line qty/price.** |

**Verified NOT to exist anywhere** (grep for `ASN|AdvancedShip|ShipmentNotice|Backorder` across `apps/`): no ASN
model, no inbound-shipment-notice model, no purchase-side backorder or delivery-schedule model. The only
`backorder` hits are outbound (`scm.SalesOrder`) and unrelated HRM text. **6.11 is greenfield on all five bullets.**

**Item master note (L28 caveat, corrected by grep).** `core.Item` does NOT exist — but `scm.Item` DOES
(`apps/scm/models/InventoryManagement/Items.py:73`). It is irrelevant here anyway: `scm.PurchaseOrderLine` itself
carries **free text** (`item_description`/`sku_hint`/`uom_hint`) with no item FK, so an ASN line must mirror the
PO line's free-text shape. Recommendation: ASN lines carry an FK to `scm.PurchaseOrderLine` (the real anchor) plus
copied free-text description/sku/uom — **no `scm.Item` FK**, exactly as 6.9's `CatalogItem` treated it as optional.

**The single biggest architectural finding.** SCM 4.6 TMS already owns inbound freight tracking end-to-end
(`Shipment` with `purchase_order` FK + append-only `TrackingEvent` + `Carrier` + POD stamping), registered at
`LIVE_LINKS["4.6"]["Shipment Tracking"] = "scm:shipment_list"`. **Do not build a second tracking log** (L36).
6.11's new document is the one thing 4.6 has no concept of: the **supplier-declared** notice of what is in the
box, per PO line, with packing detail — plus the buy-side commitment schedule (split delivery / backorder) that
lives on the PO line, not on a freight movement.

---

## Leaders surveyed (with source links)

1. **SAP Business Network / Ariba Supply Chain Collaboration** — the reference buyer-supplier transaction network;
   PO → order confirmation → ASN with handling-unit (packaging) detail, workbench tiles for "items to confirm" /
   "items to ship". <https://community.sap.com/t5/spend-management-blog-posts-by-members/sap-ariba-supply-chain-collaboration-scc/ba-p/13396486> ·
   <https://learning.sap.com/courses/sap-business-network-supply-chain-collaboration-purchase-order-collaboration-features-and-functions/creating-an-advance-ship-notice-on-ariba-network_fa59cc48-2d4d-4b75-ba1e-c1e96813452c>
2. **Coupa (Supplier Portal / Supply Chain Collaboration)** — header-vs-line PO confirmation with an hours-based
   deadline, buyer-generated **delivery schedules** with scheduled/promised quantity + need-by/promised date per
   row, ASN for consigned shipments.
   <https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal/set-up-the-csp/purchase-orders/purchase-order-collaboration-with-buyers> ·
   <https://compass.coupa.com/en-us/products/product-documentation/supplier-resources/for-suppliers/coupa-supplier-portal/set-up-the-csp/purchase-orders/purchase-order-collaboration-with-buyers/manage-buyer-generated-delivery-schedules-for-external-pos>
3. **Oracle (Purchasing / iSupplier Portal / Fusion Cloud SCM)** — the most explicit ASN *data model* in public
   docs: New / Cancellation / Test ASN types, Accepted / Accepted-with-warnings / Rejected validation, in-transit
   supply effects, receipts created FROM a validated ASN, LPN + lot/serial + country-of-origin at line level.
   <https://docs.oracle.com/cd/A60725_05/html/comnls/us/po/cpoasn.htm> ·
   <https://docs.oracle.com/cd/E18727_01/doc.121/e13414/T463223T463230.htm>
4. **JAGGAER Supply Chain Collaboration** — order confirmation with supplier-side **split**, digital delivery
   notes/ASN with packaging + tracking, delivery call-offs for JIT, AI late-delivery exception flags, VMI.
   <https://www.jaggaer.com/solutions/supply-chain-collaboration>
5. **SupplyOn (ASN / delivery processes)** — deepest ASN specialisation: ASN pre-filled from the order/delivery
   instruction, supplier adds packaging + volume + transport, auto-generated labels/barcodes, quality & customs
   documents attached, deviations surfaced *before* arrival, in-transit posting then goods receipt.
   <https://www.supplyon.com/en/solutions/supply-chain-collaboration/delivery-processes/asn/>
6. **Ivalua (Supplier Collaboration / P2P)** — suppliers acknowledge POs, propose changes, handle ASNs and GRNs;
   mobile/barcode receipts and real-time three-way match with instant discrepancy detection.
   <https://www.ivalua.com/solutions/business/supplier-collaboration-innovation/>
7. **e2open Purchase Order Collaboration** — discrete + blanket orders and scheduling agreements, change
   orchestration (expedite / de-expedite / cancel), ASN + receipt collaboration, order-vs-shipment quantity
   mismatch detection, supplier on-time-delivery metrics.
   <https://www.e2open.com/supply/purchase-order-collaboration/>
8. **Infor Nexus (supply chain visibility)** — POs trigger shipment creation; milestone tracking across
   production/packing/shipping; goods receipts update shipment milestones; proactive delay alerts; electronic ASNs
   to speed receiving. <https://www.infor.com/solutions/scm/infor-nexus/supply-chain-visibility>
9. **SourceDay (PO management + supplier portal)** — the mid-market specialist for exactly this slice: PO
   acknowledgement tracking, supplier delivery-commitment updates, **At-Risk / Past-Due / Exception** PO-line
   buckets filtered by risk type, supplier-generated ASNs with barcode shipping labels, OTD scorecards.
   <https://sourceday.com/supplier-portal/> · <https://sourceday.com/blog/advanced-shipping-notice-asn/> ·
   <https://sourceday.com/blog/on-time-delivery-metrics/>
10. **Oracle NetSuite — Inbound Shipment Management** — a first-class **inbound shipment record**: items from
    *multiple* POs on one shipment, expected delivery date, in-transit status, partial receipt, "Receive" vs
    "Take Ownership" split, landed cost, linked documents/ASNs.
    <https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_1490802012.html>
11. **Microsoft Dynamics 365 Supply Chain Management — delivery schedules** — the canonical split-delivery data
    model: an order line becomes a "commercial line" header whose **delivery lines** each carry their own
    quantity, delivery date, confirmed date, mode of delivery and warehouse; receipts and invoices post against
    the delivery lines; running Total/Remaining quantity as rows are added.
    <https://learn.microsoft.com/en-us/dynamics365/supply-chain/sales-marketing/delivery-schedules> ·
    <https://learn.microsoft.com/en-us/dynamicsax-2012/appuser-itpro/create-purchase-delivery-schedules>
12. **project44 / FourKites (real-time transportation visibility)** — the "Real-time Freight Tracking" bullet's
    market reference: multimodal door-to-door milestones, AI/predictive ETAs from carrier GPS/ELD feeds, dock
    appointment management driven off inbound truck ETA.
    <https://www.project44.com/platform/visibility/> · <https://www.fourkites.com/platform/appointment-management/>

Supporting reading: GEP on ASN contents/EDI 856/dock-and-labour planning
<https://www.gep.com/blog/technology/advanced-shipping-notice-asn>.

---

## Feature catalog (this sub-module only)

### Bullet 1 — Advanced Shipping Notice (ASN): supplier notification of pending shipments with packing details

- **ASN header against one purchase order** — supplier declares a pending shipment: ship date, expected arrival,
  their own ASN/delivery-note reference · seen in: SAP Ariba, Oracle iSupplier, Coupa, JAGGAER, SupplyOn, Ivalua,
  SourceDay · priority: **table-stakes** · spine: **new table** `AdvancedShipmentNotice` FK → `scm.PurchaseOrder`
  (verified) · buildable now
- **ASN line matched to the PO line** — each declared line references the exact PO line and carries a shipped
  quantity, so short/over shipment is computable against `PurchaseOrderLine.quantity` · seen in: Oracle
  ("reference exact PO lines"), e2open (order-vs-shipment quantity mismatch), SAP Ariba · priority:
  **table-stakes** · spine: **new child table** `AsnLine` FK → `scm.PurchaseOrderLine` (verified) + free-text
  description/sku/uom mirroring the PO line (no item master on PO lines) · buildable now
- **Packing / handling-unit detail** — package & pallet counts, gross weight, volume, carton/pallet (LPN) ref per
  line · seen in: SAP Ariba ("advanced HU management"), Oracle (containers, LPN), SupplyOn, GEP, SourceDay ·
  priority: **table-stakes** (it is literally the bullet's wording) · spine: header cube fields + per-line
  `package_ref`; deliberately **flattened**, not a recursive pallet→carton→item hierarchy · buildable now
- **Lot / serial / expiry / country-of-origin at line level** — declared before arrival so receiving can verify ·
  seen in: Oracle iSupplier (lot & serial + LPN), GEP, SupplyOn · priority: **common** · spine: free-text fields on
  `AsnLine`; **do not** FK `scm.LotSerial` — that record is created at receipt, which is 6.12 · buildable now
- **Freight terms / BOL / container reference** — the paperwork identifiers on the consignment · seen in: Oracle
  (freight information, returnable containers), GEP (freight terms), NetSuite (bill of lading, vessel) · priority:
  **common** · spine: header char fields · buildable now
- **ASN validation against the order before arrival** — reject/warn on: not this tenant's order, PO not in a
  receivable state, quantity exceeding the line's outstanding balance, duplicate supplier reference · seen in:
  Oracle (Accepted / Accepted-with-warnings / Rejected + Application Advice), SupplyOn ("deviations surface before
  goods arrive"), Ivalua · priority: **table-stakes** · spine: model `clean()` + a derived `discrepancy` verdict on
  the ASN detail — **derived, never stored** (the spine's rule) · buildable now
- **ASN cancellation (never deletion) once submitted** — Oracle's Cancellation-ASN semantics: an ASN may be
  cancelled only while nothing has been received against it · seen in: Oracle, SAP Ariba · priority: **common** ·
  spine: `status="cancelled"` + reason on the same table; delete stays admin-only for drafts · buildable now
- **Attach the supplier's paperwork** (packing list PDF, certificate of analysis, customs docs) · seen in:
  SupplyOn, Ivalua, NetSuite ("attachments … linked to the shipment record") · priority: **common** · spine:
  reuses **`core.Document`** (verified) via the existing upload pattern — no new document table · buildable now
- **Barcode / shipping-label generation from the ASN** · seen in: SourceDay, SupplyOn · priority: **differentiator**
  · spine: n/a · **defer** — inventory 5.x already owns `BarcodeLabel`; a duplicate generator here would be a
  second label engine
- **EDI 856 / cXML ASN intake, supplier self-service filing** · seen in: SAP Ariba (cXML), Coupa (cXML ASN
  credentials), Oracle (EDI/JSON), SourceDay · priority: **table-stakes in-market, integration/later here** ·
  spine: a `source` choice field (`portal / email / edi / manual`) captures provenance now so the later intake has
  a column to write; the ASN is **staff-recorded this pass** (L32 — no login-gated vendor page behind a staff
  sidebar bullet; same posture as `scm.PurchaseOrder.acknowledged_at`) · integration/later

### Bullet 2 — Real-time Freight Tracking: integration with shipping carriers for live tracking updates

- **Carrier + tracking number on the inbound consignment** — the minimum viable "track it" datum · seen in: every
  product surveyed · priority: **table-stakes** · spine: **reuses `scm.Carrier`** (verified, nullable FK) +
  `tracking_number` on the ASN; a free-text `carrier_name` fallback for suppliers' own couriers with no profile ·
  buildable now
- **Link the ASN to a tracked `scm.Shipment` movement** — one consignment, one tracking log · seen in: Infor Nexus
  ("purchase orders trigger shipment creation"), NetSuite (inbound shipment record), e2open · priority:
  **common** · spine: **reuses `scm.Shipment`** (verified — it already has `direction="inbound"` +
  `purchase_order` FK) via a nullable FK on the ASN; the `TrackingEvent` log, ETA, last-known-location and POD
  stamping all stay in 4.6 · buildable now
- **Inbound tracking board: in-flight consignments with latest milestone + ETA + days-late** · seen in: project44,
  FourKites, Infor Nexus (control tower), SourceDay (At-Risk / Past-Due buckets) · priority: **table-stakes** ·
  spine: **computed page**, zero new state — ASNs joined to their linked shipment's projected
  `current_status_text` / `eta` / `last_known_location`, falling back to the ASN's own carrier + expected date when
  unlinked (the 6.10 `po_line_tracking` precedent: a bullet may be a computed board) · buildable now
- **Predictive / AI ETA refinement from carrier GPS & ELD feeds** · seen in: project44, FourKites, Infor Nexus ·
  priority: **differentiator** · spine: `scm.TrackingEvent.source` already enumerates `carrier_api` / `gps_ping` ·
  **integration/later** (no live carrier polling this pass — the 6.9 punch-out precedent)
- **Proactive delay alerts to the buyer** — raise a `delivery`-kind alert when a consignment passes its expected
  date still in transit · seen in: Infor Nexus, JAGGAER (AI late-delivery flags), SourceDay · priority: **common**
  · spine: **reuses `procurement.ProcurementAlert`** (verified; `kind="delivery"` already in `KIND_CHOICES`) —
  raised idempotently by the 6.11 board/verb, exactly as 6.8's renewals board does · buildable now
- **Dock appointment scheduling off the inbound ETA** · seen in: FourKites, SourceDay, GEP · priority:
  **differentiator** · **park** — `scm.YardVisit` (4.4 WMS) already exists; scheduling belongs there, not here

### Bullet 3 — Delivery Confirmation: system capture of the exact date and time goods arrive

- **Arrival confirmation stamping an exact timestamp** — a distinct, auditable "the truck landed at T" fact,
  separate from what was accepted · seen in: Oracle (ASN → receipt hand-off), NetSuite ("Receive" vs "Take
  Ownership" as separate acts), Infor Nexus (goods receipt updates shipment milestones), Ivalua · priority:
  **table-stakes** · spine: `delivered_at` **DateTimeField** on the ASN + a POST-only `confirm-delivery` verb;
  `scm.Shipment.actual_delivery_at` stays 4.6's own projection · buildable now
- **Proof of delivery: who signed, POD reference, condition on arrival** · seen in: SAP Ariba, project44/FourKites
  (POD capture), NetSuite · priority: **common** · spine: `pod_reference` / `received_signature_name` /
  `arrival_condition` choice on the ASN (`good / damaged / partial / refused`) · buildable now
- **Arrivals queue: what is due today / overdue / awaiting confirmation** · seen in: SourceDay (PO dashboard
  buckets), GEP (dock & labour planning), FourKites · priority: **common** · spine: **computed page** filtered
  over the ASN register · buildable now
- **Goods receipt created FROM the confirmed ASN (pre-populated lines)** · seen in: Oracle (explicit "create
  receipts from a validated ASN"), SupplyOn, NetSuite, Ivalua · priority: **table-stakes in-market** · spine:
  would write `scm.GoodsReceiptNote` + `GoodsReceiptLine` · **DEFER to 6.12** — receipt, tolerance, QC, quarantine
  and inventory posting are 6.12's ten bullets. 6.11 leaves the hook: the ASN's supplier reference is exactly what
  `GoodsReceiptNote.delivery_note_ref` (verified field) will carry, and a `Receipt booked` state on the ASN is a
  one-line 6.12 addition
- **In-transit inventory / ownership accounting on ASN acceptance** · seen in: Oracle (purchasing supply →
  intransit supply), NetSuite (Take Ownership) · priority: **differentiator** · **defer** — touches stock and the
  ledger; `accounting` owns the ledger (L29) and 6.12/Module 5 own stock

### Bullet 4 — Backorder Management: items out of stock, scheduled for future delivery

- **Recorded shortfall with a REASON** — supplier can ship only part now; the rest is backordered because of
  stock-out / production delay / allocation / material shortage · seen in: SourceDay (PO exceptions by risk type),
  JAGGAER, e2open (expedite/de-expedite), NetSuite backorder reporting · priority: **table-stakes** · spine:
  **new table** `Backorder` FK → `scm.PurchaseOrderLine` (verified) · buildable now — the *reason* and the *new
  commitment* are facts that cannot be derived from quantities alone, which is what makes this a table rather than
  a filter on 6.10's computed line board
- **Revised promise date + reschedule history** — original promised date vs the current revised one, and how many
  times it has slipped · seen in: SourceDay ("delivery commitments", date-change risk type), Coupa (promised
  date), JAGGAER, backorder-management practice (expected restock date) · priority: **table-stakes** · spine:
  `original_promise_date` / `revised_promise_date` / `reschedule_count` on `Backorder` + a `reschedule` verb ·
  buildable now
- **Backorder lifecycle** open → rescheduled → fulfilled / cancelled, with an age-in-days measure · seen in:
  NetSuite/Acctivate backorder reports, SourceDay dashboards · priority: **common** · spine: `status` choices +
  `closed_at` on the same table; `days_open` **derived** · buildable now
- **Risk buckets on the register**: at-risk (revised date within N days), past-due (revised date passed, still
  open), no-commitment (no revised date given) · seen in: SourceDay (At-Risk / Past-Due / Exception filters),
  JAGGAER (AI late flags), Infor Nexus (proactive alerts) · priority: **common** · spine: **derived** filters via
  the `?query=` deep-link convention already used by `LIVE_LINKS["6.7"]`/`["6.9"]` · buildable now
- **Escalate a backorder into the alert inbox** · seen in: Infor Nexus, SourceDay · priority: **common** · spine:
  **reuses `procurement.ProcurementAlert`** (`kind="delivery"`, verified) · buildable now
- **Auto-create a backorder when an ASN ships short of the outstanding quantity** · seen in: e2open (order-vs-
  shipment mismatch), Oracle (CUM/quantity comparison), GEP ("identifies partial shipments before arrival") ·
  priority: **differentiator** · spine: a suggestion/prefill on the ASN detail page (link with the shortfall
  pre-filled), **not** a silent background write — one writer per field · buildable now (as a prefilled link)
- **Notify the internal requester / downstream customer of the slip** · seen in: backorder-management practice
  (order confirmation → restock ETA → ship notice → delivery confirmation cadence), DOSS, Magestore · priority:
  **common** · spine: the alert row is the in-app notification; outbound email is **integration/later**
- **Substitute / alternate item offered against a backorder** · seen in: Oracle ASN (substitute item numbers) ·
  priority: **differentiator** · **defer** — needs an item master on the PO line, which does not exist

### Bullet 5 — Split Delivery Management: one PO fulfilled across multiple shipments

- **Per-line delivery schedule: N instalment rows against ONE PO line** — each with its own quantity and date;
  running total vs remaining as rows are added · seen in: Dynamics 365 (delivery schedule → delivery lines with
  Total/Remaining quantity), Coupa (buyer-generated delivery schedules on external POs), JAGGAER (delivery
  call-offs), e2open (blanket releases / scheduling agreements), SAP Ariba (schedule agreements) · priority:
  **table-stakes** · spine: **new table** `DeliverySchedule` FK → `scm.PurchaseOrderLine` (verified) · buildable now
- **Buyer requested vs supplier promised, on the SAME row** — Coupa's four columns exactly: scheduled quantity /
  need-by date (buyer) and promised quantity / promised date (supplier counter-proposal) · seen in: Coupa,
  Dynamics 365 (Delivery date + Confirmed date), SourceDay · priority: **table-stakes** · spine: four fields on
  `DeliverySchedule`; slip = `promised_date − need_by_date`, **derived** · buildable now
- **Split-a-line action**: take an outstanding PO line and generate K evenly-spaced instalments · seen in:
  Dynamics 365 (1000 → 4 × 250, one month apart), Business Central (split purchase lines), JAGGAER (supplier can
  split an order) · priority: **common** · spine: a POST-only `split` verb creating N `DeliverySchedule` rows —
  **it does not touch `PurchaseOrderLine.quantity`** (6.10 owns spine mutation) · buildable now
- **Over-commitment guard**: scheduled quantities may not exceed the line's ordered quantity; a short total is a
  visible warning, not a hard block · seen in: Coupa (orange warning vs red error on promised-below-scheduled),
  Dynamics 365 (Remaining quantity) · priority: **common** · spine: `clean()` + a derived coverage figure on the
  board · buildable now
- **Per-instalment ship-to / mode of delivery** — instalments landing at different sites · seen in: Dynamics 365
  (delivery lines carry mode of delivery + site/warehouse), JAGGAER (JIT across production locations) · priority:
  **common** · spine: nullable FK → **`core.OrgUnit`** (verified — same target as `PurchaseOrder.ship_to`) +
  a `mode` char · buildable now
- **Instalment status ladder** planned → confirmed → shipped → received / cancelled, tied back to the ASN that
  fulfilled it · seen in: Dynamics 365 (receipts post against delivery lines), Coupa, e2open · priority:
  **common** · spine: `status` on `DeliverySchedule` + a nullable FK to the fulfilling `AdvancedShipmentNotice`
  (own-app) · buildable now
- **Charge allocation across delivery lines** (copy gross vs allocate) · seen in: Dynamics 365 · priority:
  **differentiator** · **defer** — freight/landed cost is `scm.LandedCostVoucher` (4.18) and `accounting` territory
- **Blanket order / scheduling-agreement release management** · seen in: e2open, SAP Ariba, JAGGAER · priority:
  **differentiator** · **defer** — the spine has no blanket-order concept; a call-off model would need one first

### Beyond the bullets (seen in the market, not named by NavERP.md)

- **Supplier on-time-delivery scorecard fed by confirmed arrivals** — seen in SourceDay, e2open, Infor Nexus ·
  → **park**: `scm.SupplierScorecard` (verified, `recompute_from_signals` already reads GRNs by date range) and
  **6.16 Supplier Performance & Evaluation** own this. 6.11 should make its data *readable* by that engine, not
  compute scores.
- **Consigned / vendor-managed inventory replenishment** — Coupa, JAGGAER (VMI) · → park to Module 5 / 6.18.
- **Multi-PO consolidated inbound shipment** — NetSuite's inbound shipment spans several POs · priority:
  **differentiator** · **defer**: one-ASN-per-PO keeps the match arithmetic per-order and matches every P2P
  product surveyed (Ariba/Coupa/Oracle ASNs are per-order); `scm.Load` (verified) is already the multi-shipment
  consolidation concept if it is ever needed.
- **Test / draft ASN mode before the real one** — Oracle's Test ASN · covered adequately by a `draft` status.

---

## Recommended build scope (this pass — 4 tables / 3 entity files)

Package layout: `apps/procurement/{models,forms,views,urls}/OrderFulfillmentTracking/{Asn,DeliverySchedules,Backorders}.py`,
templates `templates/procurement/orderfulfillment/{asn,deliveryschedule,backorder}/{list,detail,form}.html`.

### 1. `AdvancedShipmentNotice` [**ASN-**] + `AsnLine` — *one entity file* `Asn.py`
Justified by: **Bullet 1** (ASN header + line + packing detail + validation + cancellation + documents),
**Bullet 2** (carrier/tracking + shipment link + the tracking board's row source), **Bullet 3** (delivery
confirmation timestamp + POD).

- Header fields: `purchase_order` (FK **`scm.PurchaseOrder`**, `PROTECT` — matching 6.10's `PurchaseOrderChange`
  in the same app), `supplier_reference` (the supplier's own ASN/delivery-note number → 6.12's
  `GoodsReceiptNote.delivery_note_ref`), `status` (`draft / submitted / in_transit / delivered / cancelled`),
  `source` (`portal / email / edi / manual` — provenance column for the later EDI 856 intake),
  `ship_date`, `expected_delivery_date`, `delivered_at` **DateTimeField** (Bullet 3's "exact date and time"),
  `carrier` (FK **`scm.Carrier`**, null), `carrier_name` (free-text fallback), `tracking_number`,
  `shipment` (FK **`scm.Shipment`**, null — links into 4.6's live tracking log),
  `bill_of_lading_ref`, `container_ref`, `freight_terms`,
  `package_count`, `pallet_count`, `gross_weight_kg`, `volume_cbm`,
  `arrival_condition` (`good / damaged / partial / refused`), `pod_reference`, `received_signature_name`,
  `confirmed_by` (user, `editable=False`), `cancelled_at` / `cancellation_reason` (`editable=False`), `notes`.
- `AsnLine` (tenant-less child, the `PurchaseOrderChangeLine` precedent): `asn` FK, `po_line` (FK
  **`scm.PurchaseOrderLine`**), `item_description` / `sku_hint` / `uom_hint` (free text — PO lines have no item
  FK), `quantity_shipped`, `package_ref` (carton/pallet/LPN), `lot_number`, `serial_number`, `expiry_date`,
  `country_of_origin`, `notes`.
- Derived, never stored: shortfall/over-ship per line vs `po_line.quantity − received_quantity()`, the ASN's
  discrepancy verdict, days-late vs `expected_delivery_date`.
- Verbs: `submit` (validates against the order), `confirm-delivery` (POST-only; stamps `delivered_at`, POD,
  condition), `cancel` (blocked once anything is received against the order). **No spine mutation.**
- FKs verified: `scm.PurchaseOrder`, `scm.PurchaseOrderLine`, `scm.Carrier`, `scm.Shipment`, `core.Document`,
  `core.Tenant`, `AUTH_USER_MODEL`.

### 2. `DeliverySchedule` [**DSC-**] — `DeliverySchedules.py`
Justified by: **Bullet 5** (instalment rows, buyer-requested vs supplier-promised columns, split action,
over-commitment guard, per-instalment ship-to, instalment status).

- Fields: `po_line` (FK **`scm.PurchaseOrderLine`**, `PROTECT`), `sequence`, `scheduled_quantity`, `need_by_date`
  (buyer), `promised_quantity`, `promised_date` (supplier), `status`
  (`planned / confirmed / shipped / received / cancelled`), `ship_to` (FK **`core.OrgUnit`**, null),
  `delivery_mode` (char choices), `asn` (FK own-app `AdvancedShipmentNotice`, null — which shipment fulfilled it),
  `change_reason`, `notes`.
- `clean()`: instalment quantities may not exceed the line's ordered quantity; a shortfall renders as a warning
  (Coupa's orange-vs-red distinction). Derived on read: total scheduled, remaining, coverage %, slip days.
- Verb: `split` on an outstanding PO line → K evenly-spaced rows (Dynamics 365's 1000 → 4 × 250 pattern).
- **Boundary:** never writes `PurchaseOrderLine.quantity/unit_price` or `PurchaseOrder.expected_date` — those are
  6.10's `PurchaseOrderChange` (concurrent build) under a row lock.

### 3. `Backorder` [**BKO-**] — `Backorders.py`
Justified by: **Bullet 4** (recorded shortfall + reason, revised promise date, reschedule history, lifecycle, risk
buckets, alert escalation, prefilled-from-ASN creation).

- Fields: `po_line` (FK **`scm.PurchaseOrderLine`**, `PROTECT`), `delivery_schedule` (FK own-app, null — which
  instalment slipped), `asn` (FK own-app, null — the short shipment that caused it),
  `quantity_backordered`, `reason` (`out_of_stock / production_delay / allocation / material_shortage /
  supplier_capacity / logistics / other`), `reason_note`,
  `original_promise_date`, `revised_promise_date`, `reschedule_count` (`editable=False`),
  `status` (`open / rescheduled / fulfilled / cancelled`), `closed_at` + `closure_note` (`editable=False`),
  `alert` (FK **`procurement.ProcurementAlert`**, null — the raised `kind="delivery"` row), `notes`.
- Derived: `days_open`, `days_late`, risk bucket (at-risk / past-due / no-commitment) exposed as `?risk=` filters
  on the register — the `LIVE_LINKS` `?query=` deep-link convention.
- Verbs: `reschedule` (new date + reason, bumps `reschedule_count`), `fulfil`, `cancel`, `raise-alert`
  (idempotent into `ProcurementAlert`).

### 4. Computed pages (no new state)
- **`inbound_tracking`** — Bullet 2's board: ASNs in flight joined to `shipment__current_status_text` / `eta` /
  `last_known_location`, with the ASN's own carrier + expected date as fallback; late rows flagged. Mirrors 6.10's
  `po_line_tracking` (computed board, zero writes).
- **`delivery_confirmation`** — Bullet 3's arrivals queue: due-today / overdue / awaiting-confirmation ASNs with
  the one-click confirm form.

### Suggested `LIVE_LINKS["6.11"]` (one bullet → one page)
```
"Advanced Shipping Notice (ASN)": "procurement:asn_list"
"Real-time Freight Tracking":     "procurement:inbound_tracking"
"Delivery Confirmation":          "procurement:delivery_confirmation"
"Backorder Management":           "procurement:backorder_list"
"Split Delivery Management":      "procurement:deliveryschedule_list"
```

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Goods receipt creation from a confirmed ASN, receipt tolerances, QC checklists, quarantine, lot/serial capture
  at receipt, discrepancy reports with photos, RTV, barcoding/scanning, inventory posting, receipt reversal
  → **6.12 Goods Receipt & Inspection**
- PO generation, dispatch/acknowledgement logging, change orders, cancellation/close-out, per-line delivery
  tracking board → **6.10 PO Management** (concurrent build; `inventory:dispatch_list` + `procurement:poc_list`
  + `procurement:po_line_tracking` already cover these)
- Supplier on-time-delivery KPI, scorecards, benchmarking → **6.16 Supplier Performance & Evaluation**
  (and `scm.SupplierScorecard`, already built)
- Three-way match, invoice/voucher, dispute resolution → **6.13** (and `accounting.Bill` — L29, one ledger)
- Stock-level visibility, reorder-point auto-requisition, bin/warehouse location of received goods, cycle counts
  → **6.18 Inventory & Warehouse Integration**
- Vendor portal login for suppliers to file their own ASNs → **6.4** (`procurement.VendorPortalAccess` exists);
  6.11 records ASNs staff-side this pass (L32)
- Freight invoice audit, carrier rate cards, route/load planning, POD document handling on the movement itself
  → **SCM 4.6 TMS** (`scm.FreightInvoice`, `scm.CarrierRateCard`, `scm.Load` — all verified built)
- Dock/yard appointment scheduling → **SCM 4.4 WMS** (`scm.YardVisit`, verified built)
- Barcode/RFID label generation → **Inventory 5.x** (`inventory.BarcodeLabel`, verified built)

---

## Deferred (later passes / integrations)

- **EDI 856 / cXML ASN intake and supplier self-filing** — the `source` column ships now; the transport does not.
  Same posture as 6.9's punch-out endpoint (config stored, live handshake deferred behind the SSRF-guard
  precedent).
- **Live carrier-API polling / predictive ETA** — `scm.TrackingEvent.source` already has `carrier_api`/`gps_ping`;
  events are recorded manually this pass. project44/FourKites-class prediction is out of scope for a Django CRUD
  pass.
- **Auto-creating a `scm.Shipment` when an ASN is submitted** — the FK link is selected, not auto-created; a
  cross-app write into another module's numbered table wants its own decision. Infor Nexus does this; we defer it.
- **In-transit inventory / ownership accounting on ASN acceptance** (Oracle, NetSuite) — touches stock and the
  ledger; `accounting` owns the ledger (L29).
- **Multi-PO consolidated inbound shipment** (NetSuite) — one ASN per PO this pass.
- **Charge/landed-cost allocation across delivery lines** (Dynamics 365) — `scm.LandedCostVoucher` (4.18) territory.
- **Blanket-order call-offs / scheduling agreements** (e2open, SAP Ariba) — the spine has no blanket order.
- **Substitute-item offers on a backorder** (Oracle) — PO lines carry no item FK.
- **Outbound email/SMS notification of delays** — the `ProcurementAlert` row is the in-app notification; external
  delivery is an integration.

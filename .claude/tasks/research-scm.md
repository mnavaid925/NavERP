# Research — Module 4: Supply Chain Management (scm)

## Scope note (read first)

This module has **19 sub-modules** (4.1–4.19) spanning procurement, inventory, warehousing, order management,
transportation, planning, manufacturing, quality, returns, analytics, contracts, assets, labor, cold chain, two
customer/partner portals, finance integration, and system integration. Per the `/next-module` convention this
research covers the **full sub-module catalog for orientation**, but the **build scope in this pass is 4.1
Procurement Management only** — the first sub-module to be built. Sections for 4.2–4.19 are intentionally lighter
(enough to place features correctly and avoid future rework) and are explicitly deferred.

**Existing repo state checked before researching:**
- `apps/scm/` does not exist yet — this is a net-new app.
- `apps/procurement/` (Module 6, built much later) does not exist yet either.
- `core.Item`, `core.UOM`, `core.Location`, `core.StockMove`, `core.PriceList` are **not built yet anywhere** in
  the codebase (confirmed by grep) — the as-built ERD note that these "land with their owning modules" is current.
- `core.PartyRole.ROLE_CHOICES` already has **two distinct roles**: `vendor` and `supplier` (plus `customer`,
  `employee`, `lead`, `contact`, `partner`) — `apps/core/models/PartyRole.py`. The target-ERD module coverage map
  deliberately assigns SCM (Module 4) `Party (supplier)` and Procurement (Module 6) `Party (vendor)` — i.e. the
  spine already anticipates the two modules tagging the same kind of counterparty with different role strings.
- `apps/accounting` (Module 2, already built) owns the real **`accounting.Bill`** (AP bill, `BILL-#####`,
  `party→core.Party`, `journal_entry→accounting.JournalEntry`, `recalc_totals()`, approval states) and
  **`accounting.Budget`** (`apps/accounting/models/Budgeting/Budgets.py`) — both are live, usable FK targets today.
- `apps/crm` (Module 1, already built) has its **own** lightweight `PurchaseOrder`/`PurchaseOrderLine` and
  `ProductStock` under `apps/crm/models/InventoryVendor/` (CRM 1.12) — built *before* any core `Item`/`PurchaseOrder`
  spine entity existed. This is direct precedent for how NavERP has handled "the spine entity isn't built yet":
  the module that needs it first builds a minimal, tenant-scoped stand-in (free-text item fields, not a hard FK to
  a catalog) rather than blocking on a not-yet-built module. See **Coordination concerns** below — this repeats for
  SCM 4.1.

## Leaders surveyed (with source links)

1. **SAP Ariba** — enterprise source-to-pay leader, tightly integrated with SAP ERP/Ariba Network — [Purchase Requisition & PO process](https://www.sastrageek.com/post/understanding-the-purchase-requisition-and-purchase-order-process-in-sap-ariba), [SAP Ariba Supplier Risk](https://www.sap.com/products/spend-management/supplier-risk.html)
2. **Coupa** — ERP-agnostic total-spend/procure-to-pay platform, 2026 Gartner S2P Leader — [Procurement product page](https://www.coupa.com/products/procure-to-pay/procurement/), [Procure-to-Pay](https://www.coupa.com/products/procure-to-pay/)
3. **Ivalua** — highly configurable single-platform spend management for complex direct/indirect procurement — [Procurement automation buying guide](https://www.ivalua.com/blog/procurement-automation-software/)
4. **JAGGAER (ONE)** — integrated source-to-pay suite, strong direct-spend/BOM-heavy sourcing — [Strategic Sourcing](https://www.jaggaer.com/solutions/sourcing), [JAGGAER overview](https://www.jaggaer.com/)
5. **GEP SMART** — AI-powered unified S2P suite bundled with consulting, strong spend analytics/ESG — [JAGGAER vs GEP SMART](https://www.selecthub.com/procurement-software/jaggaer-one-vs-gep-smart/)
6. **Precoro** — mid-market procure-to-pay with fast PR→PO conversion and AI invoice/PO 3-way matching — [Purchase Requisition Software](https://precoro.com/to/purchase-requisition-software), [Purchase Order Software](https://precoro.com/to/purchase-order-software), [Procure-to-Pay](https://precoro.com/to/procure-to-pay-software)
7. **Procurify** — SMB/mid-market spend-control procurement with strong budget-checking and configurable approvals — [Purchase Order Software](https://www.procurify.com/procure-to-pay/procurement/purchase-order/), [Approval Software](https://www.procurify.com/procure-to-pay/procurement/approval-software/), [Purchase Requisition](https://www.procurify.com/procure-to-pay/procurement/purchase-requisition/)
8. **Oracle Fusion Cloud SCM (incl. Procurement Cloud)** — full-suite SCM: sourcing/procurement, manufacturing, order management, logistics, planning — [Oracle SCM Cloud overview via DOSS](https://www.doss.com/trends/8-best-supply-chain-management-platforms-in-2026)
9. **Oracle NetSuite** — ERP-native purchasing with built-in 2-way/3-way vendor-bill matching workflows — [3-Way Match Vendor Bill Approval Workflow](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_4096219721.html), [Purchase Order Management](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2399585.html)
10. **Kinaxis (Maestro / RapidResponse)** — concurrent supply-chain planning, demand sensing, dynamic safety stock — [Kinaxis resilient planning](https://www.kinaxis.com/en/resilient-planning)
11. **Blue Yonder** — AI-driven demand forecasting, warehouse labor optimization, transportation route optimization, network design — [Blue Yonder vs Kinaxis](https://www.horizonsolutions.ai/supply-chain-planning/blue-yonder-vs-kinaxis)
12. **Manhattan Associates** — WMS/TMS leader for large-scale retail/e-commerce fulfillment, throughput and labor automation — [8 Best Supply Chain Management Platforms in 2026](https://www.doss.com/trends/8-best-supply-chain-management-platforms-in-2026)

*(12 surveyed — the module's 19 sub-modules span procurement, WMS/TMS, and planning, which are genuinely three
different product categories in the market; the extra two products give real coverage of the WMS/TMS/planning
sub-modules rather than stretching the procurement suites to cover things they don't actually do.)*

## Feature catalog by sub-module

### 4.1 Purchase Requisition, RFQ, PO, Vendor Portal, Invoice Reconciliation — **priority sub-module, researched in depth**

- **Purchase Requisition (PR) with line items, cost-center/account coding, and required-by date** — a fast form
  to detail item description, quantity, required date, and GL/account code · seen in: SAP Ariba, NetSuite,
  Procurify, Precoro · priority: **table-stakes** · spine: `core.Party` (requester via `Party`/`User`), new table
  `PurchaseRequisition` + `PurchaseRequisitionLine` (item stays free-text for now — see Coordination concerns)
  · buildable now
- **Multi-tier approval routing (by amount/department)** — conditional routing so bigger spend needs more sign-off
  · seen in: SAP Ariba, Coupa, Procurify, Precoro · priority: table-stakes · spine: new fields on
  `PurchaseRequisition`/`PurchaseOrder` (`status`, `approved_by`, `approved_at`) — same shape already used by
  `accounting.Bill`; full configurable routing-rule engine deferred · buildable now (simple state machine); a
  rule-based routing *engine* is a later differentiator
- **Budget checking at requisition time** — validate a request against a live budget before it can proceed ·
  seen in: Procurify (real-time budget tracking), Coupa (requisitions tied to budgets), Precoro · priority:
  table-stakes · spine: `accounting.Budget` already exists — reuse it (soft check/warning), don't re-model budgets
  in SCM · buildable now as a light integration (query `accounting.Budget`, flag over-budget); full budget
  enforcement/encumbrance accounting is integration/later
- **Duplicate requisition detection** — flags likely-duplicate requests within a time window · seen in: general
  P2P suites (Coupa-class capability) · priority: common · spine: derived query on `PurchaseRequisition`, no new
  table · buildable now
- **Requisition templates for recurring orders** · seen in: SAP Ariba, Coupa · priority: common · spine: could
  reuse `PurchaseRequisition` with an `is_template` flag rather than a new model · buildable now, low priority —
  fine to defer to a later 4.1 iteration
- **RFQ creation & multi-vendor distribution** — one RFQ, many invited suppliers, deadline, response window ·
  seen in: SAP Ariba (RFI/RFP/RFQ/auctions), JAGGAER (esourcing), GEP SMART (RFQ/RFP/reverse auctions), Precoro
  (RFx from scratch or from a requisition) · priority: table-stakes · spine: `core.Party`+`PartyRole(role=
  'supplier')` for invited vendors, new tables `RFQ` + `RFQLine` + `RFQVendor` (invite) · buildable now
- **Vendor quote capture & side-by-side comparison** — collect each vendor's price/lead-time/terms per RFQ line
  and compare · seen in: SAP Ariba, JAGGAER, GEP SMART, Precoro · priority: table-stakes · spine: new table
  `RFQQuote` (+ `RFQQuoteLine`) linked to `RFQ` and the responding `Party` · buildable now
- **RFQ→PO conversion (award)** — selecting a winning quote generates the PO directly, carrying vendor/price/
  terms forward · seen in: Precoro ("turn requisitions into POs with one click"), SAP Ariba (PR→PO generation) ·
  priority: table-stakes · spine: `RFQQuote` → `PurchaseOrder` (service function, no new table) · buildable now
- **PO generation, approval, amendment, cancellation** — full PO lifecycle with a status machine and an amendment/
  version trail · seen in: **all 12** surveyed products · priority: table-stakes · spine: new tables
  `PurchaseOrder` + `PurchaseOrderLine` (precedent: `crm.PurchaseOrder` already does this shape for CRM 1.12 —
  don't copy it 1:1 into SCM, see Coordination concerns) · buildable now
- **PO dispatch to vendor (email/portal/EDI)** — send the PO out and track delivery/acknowledgement · seen in:
  SAP Ariba (Ariba Network auto-delivery), Coupa Supplier Portal · priority: common · spine: email dispatch is
  buildable now (Django email); EDI dispatch is integration/later
- **Vendor self-service portal — view POs, acknowledge/accept, update shipment status** · seen in: SAP Ariba
  (suppliers send ASNs, change delivery dates, communicate with buyers), Coupa Supplier Portal (self-register,
  view POs, submit invoices, track performance), Precoro Supplier Portal (respond to RFQs, maintain catalogs,
  submit invoices) · priority: **differentiator** (most SMB tools have a stripped-down version; enterprise suites
  have a full portal) · spine: new table `VendorAcknowledgement` (or fields directly on `PurchaseOrder`:
  `acknowledged_at`, `acknowledged_by`, `vendor_notes`, `promised_ship_date`) — for this pass, model it as
  **fields on the PO** rather than a separate portal-user auth system; a true externally-authenticated supplier
  login is integration/later
- **Goods Receipt Note (GRN) / receiving against a PO** — record what actually arrived, partial receipts,
  quantity/quality accept-reject · seen in: **all** procurement suites + NetSuite ("item receipt" stage) ·
  priority: table-stakes · spine: new table `GoodsReceiptNote` + `GoodsReceiptLine`, FK to `PurchaseOrder` (this
  is the "GRN" the module coverage map also lists for Module 5/6 — see Coordination concerns) · buildable now
- **Three-way matching (PO ↔ GRN ↔ Vendor Invoice)** — automatic variance detection on qty/price before an
  invoice is approved for payment · seen in: SAP Ariba (matched via SAP LIV, auto-approve within tolerance),
  Coupa (AI-powered invoice validation + 3-way match), NetSuite (built-in 3-Way Match Vendor Bill Approval
  Workflow highlighting variances), Precoro (AI-extracted invoice matched to PO+receipt) · priority: table-stakes
  · spine: new table `ThreeWayMatch` (or a `match_status`/`variance` set of fields on `GoodsReceiptNote`) linking
  `PurchaseOrder` + `GoodsReceiptNote` + **`accounting.Bill`** (reuse the real AP bill that already exists — do
  **not** invent a parallel "VendorInvoice" model) · buildable now
- **PO status tracking (Draft/Sent/Partial/Received/Closed/Cancelled)** · seen in: all surveyed · priority:
  table-stakes · spine: `status` choice field on `PurchaseOrder` · buildable now

### 4.2 Supplier Relationship Management (SRM) — deferred detail, high-level only
- **Supplier onboarding/qualification questionnaires** · seen in: SAP Ariba, GEP SMART, Coupa Supplier Portal ·
  priority: common · spine: `core.Party`+`PartyRole` for the record, new table `SupplierOnboarding` for the
  questionnaire/status · integration/later (external verification checks)
- **Supplier scorecard (delivery/quality/price/responsiveness)** · seen in: SAP Ariba, GEP SMART, JAGGAER ·
  priority: differentiator · spine: new table `VendorScorecard` (also named in the module coverage map under
  Module 6 — coordination flag) · buildable later, needs PO/GRN history to compute from
- **Contract repository w/ renewal alerts** · seen in: SAP Ariba, GEP SMART, JAGGAER · priority: common · spine:
  reuse core `Contract` anchor (per ERD) rather than a new SCM contract table · buildable now if `Contract`
  exists by then, else deferred
- **Supplier catalog management** · seen in: Coupa, Precoro (vendors upload/update catalogs via portal) ·
  priority: differentiator · spine: new table, ties to whatever Item/catalog entity 4.3 lands · deferred
- **Supplier risk assessment (financial/geo-political/compliance/ESG)** · seen in: SAP Ariba Supplier Risk
  (200+ risk-incident types, configurable scoring), GEP SMART (ESG/diversity/conflict-minerals) · priority:
  differentiator · spine: new table `SupplierRiskAssessment` · integration/later (external risk-data feeds)

### 4.3 Inventory Management (deferred — later 4.x sub-module, not this pass)
- Real-time stock/batch/serial tracking, warehouse transfers, stock adjustments, reorder-point automation,
  FIFO/LIFO/weighted-average valuation — seen in NetSuite, Oracle SCM Cloud, and effectively every ERP surveyed.
  This is where `core.Item`, `core.UOM`, `core.Location`, `core.StockMove` will actually get built (per the
  target-ERD module coverage map: SCM reuses `Item`/`Location`/`StockMove`, and NavERP's precedent is "the module
  that needs a spine entity first builds it"). **Not in scope this pass** — 4.1 intentionally avoids hard FKs
  into a catalog that doesn't exist yet (see Coordination concerns).

### 4.4 Warehouse Management System (WMS) (deferred)
- Inbound dock scheduling/put-away, outbound wave/batch/zone picking, bin/location mapping, cycle counting, yard
  management — seen in: Manhattan Associates (WMS/TMS leader, labor-automation algorithms), Blue Yonder
  (warehouse labor optimization), Oracle SCM Cloud (logistics module). priority: differentiator (this is where
  best-of-breed WMS vendors clearly outclass generic ERP inventory screens). Deferred — needs 4.3's Location/Bin
  hierarchy first.

### 4.5 Order Management System (OMS) (deferred)
- Order capture/validation (credit limit, inventory availability, fraud check), allocation to fulfillment
  centers, backorder handling, automated customer notifications — seen in: Oracle SCM Cloud ("order management
  and fulfillment" as a named suite pillar), Manhattan, NetSuite. spine: reuses `core.SalesOrder` (not yet
  built) + `StockMove`. Deferred — overlaps Module 1 CRM (already has `SalesOrder`-adjacent flows) and Module 8
  Sales; needs explicit ownership decision when reached.

### 4.6 Transportation Management System (TMS) (deferred)
- Route planning/optimization, freight audit & payment, 3PL/carrier rate-card management, real-time shipment
  GPS tracking, load/cube optimization — seen in: Manhattan Associates, Blue Yonder (transportation route
  optimization), Oracle SCM Cloud. priority: differentiator. spine: new tables `Carrier`, `Shipment`,
  `RoutePlan` (matches the module coverage map's "Adds" column exactly). Deferred; GPS/carrier-API tracking is
  integration/later.

### 4.7 Demand Planning & Forecasting (deferred)
- Statistical sales forecasting, seasonality analysis, short-horizon demand sensing, collaborative S&OP input,
  dynamic safety-stock calculation — seen in: Kinaxis Maestro (AI-driven, forecast-accuracy dashboards, dynamic
  safety stock), Blue Yonder (demand forecasting with external market signals), Oracle SCM Cloud ("supply chain
  planning and collaboration" pillar). priority: differentiator — this is genuinely the deepest, hardest-to-clone
  part of the market leaders' offering. spine: new table `DemandForecast` (matches coverage map). Deferred;
  statistical/ML forecasting itself is integration/later, but a simple moving-average forecast table is
  buildable-now when this sub-module is reached.

### 4.8 Manufacturing / Production (deferred)
- BOM definition, production scheduling, work-order issuance/tracking, MRP, shop-floor time tracking — seen in:
  Oracle SCM Cloud ("manufacturing and maintenance" pillar), NetSuite (manufacturing/MRP module). spine: reuses
  core `WorkOrder` anchor + new `BillOfMaterials` table (matches coverage map). Deferred.

### 4.9 Quality Management System (QMS) (deferred — Module 12 owns full QMS later)
- Inspection criteria, NCRs, CAPA, audit scheduling, Certificate of Analysis — seen generally across Oracle SCM
  Cloud and enterprise S2P suites (quality gates on receiving). spine: reuses core `QualityRecord` anchor.
  **Flag:** Module 12 (Quality) is the module that formally owns NCR/CAPA/Inspection/Audit/Calibration per the
  coverage map — 4.9 here should stay a thin "quality flag on receiving" (pass/fail/quarantine on
  `GoodsReceiptLine`), not a parallel QMS. Deferred and intentionally light.

### 4.10 Returns Management (Reverse Logistics) (deferred)
- RMA approval workflow, refund/store-credit trigger, disposition (repair/refurbish/scrap/restock), customer
  return portal, supplier warranty claims — seen in general 3PL/SCM software (client-specific disposition rules,
  refurbishment workflows). spine: reuses `core.Party` (customer/supplier), new table `ReturnAuthorization`
  (matches coverage map), ties to `accounting` for refunds. Deferred.

### 4.11 Supply Chain Analytics (deferred)
- Inventory turnover/dead-stock dashboards, spend analysis, logistics KPIs (OTIF, freight cost/unit), predictive
  disruption alerts — seen in: GEP SMART (spend analytics/visibility), SAP Ariba, Kinaxis (out-of-the-box
  forecast-accuracy dashboards). spine: read-only aggregation over `PurchaseOrder`/`StockMove`/`Shipment`, no new
  tables of consequence. Deferred; predictive analytics is integration/later (AI-driven).

### 4.12 Contract & Compliance Management (deferred)
- Contract repository, regulatory compliance tracking (FDA/HazMat/GDPR), trade documentation (Bill of Lading,
  Commercial Invoice), import/export license tracking, sustainability/ESG reporting — seen in: SAP Ariba
  (contract lifecycle + supplier risk/ESG), GEP SMART (ESG/diversity/conflict-minerals reporting). spine: reuses
  core `Contract`/`Document` anchors. Deferred; trade-document generation and ESG scoring are integration/later.

### 4.13 Asset Management (deferred — Module 11 owns full Asset Mgmt later)
- Asset registry, preventive/breakdown maintenance, spare-parts inventory, depreciation — spine: reuses core
  `Asset`/`WorkOrder`/`GLAccount` anchors. **Flag:** same pattern as 4.9/QMS — Module 11 is the true owner per
  the coverage map; 4.13 here should stay minimal (e.g., linking a `WorkOrder` to a `PurchaseRequisition` for
  spare-parts buying) rather than re-building an asset registry. Deferred.

### 4.14 Labor Management (deferred)
- Labor demand forecasting, time & attendance, task assignment (picking/packing), productivity tracking, payroll
  export — seen in: Manhattan Associates, Blue Yonder (warehouse labor optimization). spine: reuses core
  `Employment`/`OrgUnit` anchors (HRM module already owns attendance/leave). Deferred; overlaps HRM (Module 3,
  already built) — needs explicit "who owns warehouse labor" decision when reached.

### 4.15 Cold Chain Management (deferred)
- IoT temperature monitoring, excursion alerts, cold-storage-specific inventory, reefer maintenance schedules —
  a narrow vertical feature seen in specialized 3PL/cold-chain software, not a general capability of the 12
  surveyed leaders (most treat it as an IoT-integration add-on). priority: differentiator/niche. spine: new
  table `ColdChainReading` or similar, but this is squarely integration/later (needs real IoT sensor feeds).
  Deferred, low priority relative to the rest of the module.

### 4.16 Customer Portal (deferred)
- Order tracking, account/address/payment management, document retrieval (invoice/POD), support ticketing,
  catalog browsing — seen in: Coupa Supplier Portal pattern mirrored on the customer side, general e-commerce
  SCM portals. spine: reuses `core.Party` (customer), `Document`. **Flag:** overlaps CRM's case/ticketing and
  Module 9 eCommerce's storefront. Deferred; needs ownership decision when reached.

### 4.17 Third-Party Logistics (3PL) Management (deferred)
- Client billing by storage volume/transaction/weight, strict client inventory segregation, SLA monitoring,
  client-ERP API sync, dedicated-vs-shared warehouse rental billing — seen in general 3PL software (per-client
  margin reporting, multi-client billing engines). spine: reuses `core.Party` (the 3PL's own clients), new tables
  for client billing rules. Deferred, and only relevant if NavERP tenants themselves operate as 3PLs — niche.

### 4.18 Finance & Accounting Integration (deferred — Module 2 Accounting already owns this)
- AP/AR, landed cost calculation (freight+customs+insurance rolled into item cost), budgeting, tax/VAT/customs —
  seen in: NetSuite, Oracle SCM Cloud (native GL integration). spine: **should reuse `accounting.Bill` (AP),
  `accounting.Budget`, and post to `accounting.JournalEntry`** — do not re-model AP/budgeting inside `scm`. Only
  genuinely new piece is **landed cost** (add cost components to a `GoodsReceiptNote`/`PurchaseOrderLine` and
  post the allocated amount to `JournalEntry` via a service function). Deferred to when GRN/valuation exist.

### 4.19 Integration & API Gateway (deferred)
- ERP connectors (SAP/Oracle/NetSuite/Dynamics), e-commerce connectors (Shopify/Magento/WooCommerce/Amazon),
  IoT gateway (RFID/barcode/sensors), EDI, webhooks — seen in: SAP Ariba (Ariba Network), all 3PL/EDI sources
  surveyed. priority: all integration/later by definition — no new domain tables, this is an outbound/inbound
  connector layer built once several other sub-modules exist to connect. Deferred entirely.

## Recommended build scope (this pass — 4.1 Procurement Management, 6 models)

1. **`PurchaseRequisition`** [`REQ-`] — `requester→core.Party` (or `settings.AUTH_USER_MODEL`), `department→
   core.OrgUnit`, `status` (`draft/submitted/approved/rejected/converted/cancelled`), `required_date`,
   `justification`, `estimated_total` (recomputed from lines), `approved_by`, `approved_at`. Justified by: PR
   creation/approval workflow (SAP Ariba, NetSuite, Procurify, Precoro), budget checking (Procurify, Coupa) —
   `estimated_total` vs. a light `accounting.Budget` lookup, duplicate-requisition flag (derived query, no field
   needed). Reuses `core.Party`/`core.OrgUnit`; new tenant-scoped table.
2. **`PurchaseRequisitionLine`** — `requisition→PurchaseRequisition`, `item_description`, `sku_hint` (free text —
   no `core.Item` yet), `uom_hint`, `quantity`, `estimated_unit_price`, `account_code` (free text or
   `accounting.GLAccount` FK if convenient at build time). Justified by: line-level PR detail (all 12 surveyed).
3. **`RFQ`** [`RFQ-`] — `requisition→PurchaseRequisition` (nullable — RFQs can also start standalone),
   `title`, `status` (`draft/sent/closed/awarded/cancelled`), `response_deadline`, `notes`. Justified by: RFQ
   creation/distribution (SAP Ariba, JAGGAER, GEP SMART, Precoro). New table; `requisition` FK reuses #1.
4. **`RFQLine`** + **`RFQVendor`** (invited supplier, `party→core.Party` filtered `PartyRole(role='supplier')`,
   `invited_at`, `responded_at`) — justified by: multi-vendor RFQ distribution (all sourcing-suite leaders).
   *(counted as part of model 3's cluster to stay within the 4–8 budget — implement as two small child tables.)*
5. **`RFQQuote`** (+ `RFQQuoteLine`) — `rfq→RFQ`, `vendor→core.Party`, `quoted_at`, `valid_until`,
   `total_amount` (recomputed), `is_selected`. Justified by: quote capture & side-by-side comparison (SAP Ariba,
   JAGGAER, GEP SMART, Precoro) and RFQ→PO award. New table.
6. **`PurchaseOrder`** [`PO-`] — `vendor→core.Party` (role filtered `supplier`), `rfq_quote→RFQQuote` (nullable,
   set when awarded from an RFQ), `requisition→PurchaseRequisition` (nullable, set when converted directly),
   `status` (`draft/approved/sent/acknowledged/partially_received/received/closed/cancelled`), `order_date`,
   `expected_date`, `total_amount` (recomputed), `acknowledged_at`, `acknowledged_by_vendor_note`,
   `promised_ship_date` (the light "vendor portal" fields — see Coordination concerns), `approved_by`. Justified
   by: PO generation/approval/amendment/cancellation (all 12 surveyed) + vendor acknowledgement (SAP Ariba, Coupa,
   Precoro portals). New table — **do not** reuse `crm.PurchaseOrder` (that one is CRM-scoped to
   `crm.ProductStock`; SCM's PO is the procure-to-pay spine entity and needs its own identity/number sequence and
   RFQ/GRN linkage). Flag for the `todo` agent: two `PurchaseOrder` models will now exist in the codebase
   (`crm.PurchaseOrder`, `scm.PurchaseOrder`) — intentional per-module precedent, not a bug, but should be
   documented in both modules' skills so it isn't "fixed" by accident later.
7. **`PurchaseOrderLine`** — `purchase_order→PurchaseOrder`, `item_description`, `sku_hint`, `quantity`,
   `unit_price`, `line_total` (derived), `received_quantity` (denormalized rollup from GRN lines, updated by a
   service function). Justified by: PO line detail (all 12 surveyed).
8. **`GoodsReceiptNote`** [`GRN-`] (+ `GoodsReceiptLine`, + a `match_status` field or tiny `ThreeWayMatch`
   record) — `purchase_order→PurchaseOrder`, `received_date`, `received_by`, `status`
   (`pending/partial/complete/rejected`); lines carry `ordered_quantity`, `received_quantity`,
   `quality_status` (`accepted/rejected/quarantined`); match logic compares PO line, GRN line, and
   **`accounting.Bill`** line totals/quantities within a tolerance and sets `match_status`
   (`matched/variance/unmatched`). Justified by: GRN receiving (all surveyed) + three-way matching (SAP Ariba,
   Coupa, NetSuite, Precoro). Reuses `accounting.Bill` for the invoice leg — **no new "VendorInvoice" model.**

*(This is 8 concrete tables — `PurchaseRequisition`, `PurchaseRequisitionLine`, `RFQ`, `RFQLine`/`RFQVendor`,
`RFQQuote`/`RFQQuoteLine`, `PurchaseOrder`, `PurchaseOrderLine`, `GoodsReceiptNote`/`GoodsReceiptLine` — at the
top of the 4–8 range because 4.1 explicitly names five distinct capability clusters (PR, RFQ, PO, vendor
acknowledgement, 3-way match) and each needs its own child rows to be usable; none of it duplicates
`accounting.Bill`/`accounting.Budget`/`core.Party`, which are reused as-is.)*

## Coordination concerns (flagged explicitly, per the task)

1. **Module 6 (Procurement) will re-encounter PR/RFQ/PO.** The target-ERD module coverage map's "Adds" column
   for Module 6 literally lists `PurchaseRequisition, RFQ, VendorQuote, VendorScorecard, GoodsReceiptNote` — the
   *same* entity names this research recommends building **now** in `scm`. NavERP.md's own text, however, puts
   Purchase Requisition / RFQ / PO / Vendor Portal / Invoice Reconciliation inside **4.1 SCM**, and gives Module 6
   a much larger, strategic-sourcing-flavored feature set (6.1 personalized dashboard/portal, 6.3 configurable
   approval-routing *engine* with delegation-of-authority and escalation, 6.5 sourcing events/bid evaluation
   matrices/award scenarios, 6.6 RFI/RFP/RFQ with questionnaire builder and weighted scoring, 6.7 live e-auctions,
   6.8 contract authoring with e-signature, 6.9 catalog management). **These are not the same product tier** —
   4.1 is "operational P2P" (get a PO out the door, receive it, match the invoice); Module 6 is "strategic
   sourcing / spend management" (compare and score suppliers, run auctions, author contracts). Recommendation for
   whoever builds Module 6 later: **extend `scm.PurchaseRequisition`/`scm.RFQ`/`scm.PurchaseOrder` by string-FK
   rather than re-declaring parallel tables** — e.g. Module 6's `SourcingEvent`/`Award` can point at an existing
   `scm.RFQ`, and Module 6's richer `VendorQuote`/scoring layer can wrap `scm.RFQQuote` instead of duplicating
   it. If Module 6 genuinely needs its own requisition/RFQ shape (e.g., because it targets a different approval
   engine), that's a legitimate call — but it should be a **conscious decision recorded in Module 6's own
   research/todo docs**, not an accidental duplicate schema. This note should be carried into Module 6's future
   `research-procurement.md`.
2. **`core.Item` doesn't exist yet, so 4.1's lines stay free-text.** `PurchaseRequisitionLine`/
   `RFQLine`/`PurchaseOrderLine`/`GoodsReceiptLine` in this pass use `item_description`/`sku_hint` text fields,
   not an FK to a catalog — mirroring the precedent CRM 1.12 already set with `PurchaseOrderLine.item_name` +
   optional `product→crm.ProductStock`. When SCM's own 4.3 Inventory Management sub-module lands `core.Item`
   (per the module coverage map, that's SCM's job, not Module 5's — the as-built ERD note says spine entities
   "land with their owning modules"), a follow-up migration should add a nullable `item→core.Item` FK to these
   four line tables and backfill from `sku_hint` where possible. Document this explicitly as a TODO in the
   `scm` skill so it isn't forgotten.
3. **Two `PurchaseOrder` models will coexist** (`crm.PurchaseOrder` from Module 1, `scm.PurchaseOrder` from this
   pass) with the same `NUMBER_PREFIX = "PO"`. Numbering is scoped `unique_together(tenant, number)` per model/
   table, so there's no collision risk, but the UI/reports should always show the app-qualified number (or use a
   distinguishing prefix, e.g. keep `PO-` for `scm.PurchaseOrder` since it's the "real" procure-to-pay one, and
   suggest CRM's could later be renamed/deprecated in favor of it) — call this out to the `todo` agent as a
   decision point, not a silent conflict.
4. **`accounting.Bill` is the vendor invoice — reuse it, don't re-model it.** 4.1's "Invoice Reconciliation"
   feature must match against the AP `Bill` that Module 2 already built (`bill_date`, `status`, `total`,
   `journal_entry`) rather than inventing a `VendorInvoice` model. This keeps the eventual AP posting
   (bill→payment→journal) on the one ledger that already exists.
5. **`accounting.Budget` already exists — reuse for PR budget-checking**, don't build a parallel SCM budget
   table. A light read-only check (`Budget.objects.filter(...)` compared to `PurchaseRequisition.estimated_total`)
   is enough for this pass; true encumbrance accounting (reserving budget on submission, releasing on
   rejection/cancellation) is a legitimate later enhancement, not a blocker now.
6. **`PartyRole.role` has both `vendor` and `supplier`.** Recommend `scm` filters/creates `PartyRole(role=
   'supplier')` for anything under 4.1/4.2 (matches the target-ERD coverage map's "Party (supplier)" tag for
   Module 4), leaving `role='vendor'` for Module 6 later — but note in the `scm` skill that a real-world supplier
   Party may eventually carry *both* roles if a tenant uses both modules, so queries filtering by role should use
   `role__in=[...]` defensively rather than assuming exclusivity.

## Deferred (later passes / integrations within Module 4 itself)

- **4.2 Supplier Relationship Management** — onboarding workflow, scorecards, catalog management, risk/ESG
  assessment. Needs PO/GRN history (from 4.1) to compute scorecards from, so naturally follows.
- **4.3 Inventory Management** — this is where `core.Item`/`UOM`/`Location`/`StockMove` actually get built;
  4.1's line items get retrofitted with a real `item` FK once this lands.
- **4.4 WMS, 4.5 OMS, 4.6 TMS** — best-of-breed territory (Manhattan/Blue Yonder/Oracle); needs 4.3's
  Location/Bin hierarchy first. OMS also has an ownership question vs. CRM/Sales `SalesOrder`.
  Recommendation for the `todo` agent: **build the RESTful/API surface `SalesOrder` will need before OMS is
  built**, to avoid a repeat of the "PurchaseOrder appears in two apps" situation.
- **4.7 Demand Planning & Forecasting** — genuinely differentiator territory (Kinaxis/Blue Yonder's core
  business); a simple moving-average forecast is buildable-now when reached, ML forecasting is integration/later.
- **4.8 Manufacturing/Production** — BOM/MRP/work-order tracking; reuses core `WorkOrder`.
- **4.9 Quality (QMS)** and **4.13 Asset Management** — deliberately kept thin in SCM; Modules 12 and 11 are the
  real owners per the coverage map. SCM's own sub-modules here should stay as thin hooks (a quality flag on
  receiving; a spare-parts PR link), not parallel NCR/CAPA/Asset-registry systems.
- **4.10 Returns, 4.11 Analytics, 4.12 Contract & Compliance** — straightforward once 4.1–4.3 exist; analytics
  is read-only aggregation, no new domain complexity.
- **4.14 Labor Management** — overlaps HRM (Module 3, already built); needs an explicit ownership call.
- **4.15 Cold Chain Management** — niche/vertical, IoT-dependent; lowest priority of the 19 sub-modules.
- **4.16 Customer Portal** — overlaps CRM case/ticketing and Module 9 eCommerce storefront; ownership call needed.
- **4.17 3PL Management** — only relevant if a NavERP tenant operates as a 3PL itself; niche.
- **4.18 Finance & Accounting Integration** — mostly *already satisfied* by reusing `accounting.Bill`/`Budget`/
  `JournalEntry`; the only new piece is landed-cost allocation, which needs 4.3's valuation first.
- **4.19 Integration & API Gateway** — ERP/e-commerce connectors, IoT gateway, EDI, webhooks — all
  integration/later by definition, no domain modeling of its own.

# Research — Sub-module 4.5: Order Management System (OMS) (Module 4 — Supply Chain Management, scm)

## Repo state checked first

- **`LIVE_LINKS` built so far in Module 4:** `"4.1"` (Procurement), `"4.2"` (SRM), `"4.3"` (Inventory), `"4.4"`
  (Warehouse Management) — `"4.5"` has no entry yet, confirming 4.5 is the next unbuilt sub-module (`apps/core/navigation.py` lines 803-810).
- **Sibling models verified to exist (grep evidence, all in `apps/scm/models/`):**
  - `InventoryManagement/Items.py` → `ItemCategory`, `UOM`, `Item` (sku unique/tenant, `on_hand(location=None)`,
    costing method, `average_cost`).
  - `InventoryManagement/Locations.py` → `Location` (warehouse/zone/bin hierarchy, `pick_sequence`, `is_pickable`).
  - `InventoryManagement/StockMoves.py` → `StockMove` (append-only ledger, no form/edit/delete — L37).
  - `WarehouseManagement/PickTasks.py` → `PickTask`/`PickTaskLine` — **already contains the exact comment this
    research must resolve**: *"Stands alone: no `SalesOrder` FK because Module 8 isn't built."* `PickTask.transfer`
    (→ `scm.StockTransfer`) is today's stand-in outbound trigger.
  - `ProcurementManagement/PurchaseOrders.py` → the canonical `PurchaseOrder` (distinct from `crm.PurchaseOrder`,
    the 1.12 lightweight quick-order — coexistence precedent, see Ownership decision below).
- **Accounting spine verified to exist** (`apps/accounting/models/`): `GeneralLedger/Currencies.py` → `Currency`;
  `GeneralLedger/GLAccounts.py` → `GLAccount`; `AccountsPayable/PaymentTerms.py` → `PaymentTerm`;
  `AccountsReceivable/Invoices.py` → `Invoice`/`InvoiceLine`; `AccountsReceivable/CustomerProfiles.py` →
  **`CustomerProfile`** (OneToOne on `core.Party`, has `credit_limit` + `credit_on_hold` + `ar_account`/
  `currency`/`payment_terms` — this is the exact credit-control data the OMS "Order Validation" bullet needs;
  `accounting.views.AccountsReceivable.Invoices.invoice_detail` already computes `over_limit` by summing open
  `Invoice.total` for the party against `CustomerProfile.credit_limit` — the pattern to copy for order-level
  credit checks, not reinvent).
- **Core spine verified to exist:** `core.Party`/`core.PartyRole` (role `customer` is in `ROLE_CHOICES`),
  `core.Address`, `core.AuditLog` (hold/status transitions get audit-logged the same way every other `scm`
  action view already does via `write_audit_log`, no new log table needed).
- **`SalesOrder` verified NOT to exist anywhere** (`grep -rn SalesOrder apps/` hits only comments/docstrings in
  `scm/models/WarehouseManagement/PickTasks.py`, `research-scm.md`, `research-scm-4.4.md`, `lessons.md`,
  `NavERP-ERD.md` — no `class SalesOrder` in any app).
- **`crm` order-shaped models checked for collision:** `crm.Quote`/`crm.QuoteLine` (1.2 SFA — a pre-order
  proposal document; `quote_accept()` only flips `status="accepted"`, it creates **nothing** downstream — a real
  gap this sub-module can close) and `crm.Opportunity` (pipeline stage, no order). `crm.PurchaseOrder` (1.12) is
  a vendor-facing quick-order — **no sales-order-shaped model exists in `crm` today**, so there is **no
  collision** to resolve the way 4.1/`crm.PurchaseOrder` had to be resolved; see Ownership decision.

## Ownership decision — `SalesOrder` (ships-first, L28/L29/L36/L37)

**`apps/scm` (this sub-module, 4.5) OWNS `SalesOrder`/`SalesOrderLine`.** Rationale, applying the established
rule precisely:

1. **`NavERP-ERD.md` (lines 463/470/471) nominally assigns `SalesOrder` to Modules 1 (CRM), 8 (Sales), 9
   (eCommerce)** — the same shape of ERD-says-one-thing/as-built-says-another situation L36 resolved for
   `PurchaseOrder` (ERD said Module 6, SCM 4.1 shipped it). Critically, **Module 1 (CRM) is fully built (1.1–1.12)
   and deliberately did NOT build `SalesOrder`** — it built `Lead → Opportunity → Quote` (the pre-order pipeline)
   and stopped at `quote_accept()`. CRM had its chance across 12 sub-modules and chose not to take it. Modules 8
   and 9 remain unbuilt. Per the ships-first rule, the module that actually needs the entity to function, when
   it needs it, builds and owns it.
2. **An OMS is meaningless without an order document** (the task's own framing) — 4.5's five NavERP.md bullets
   (Order Capture, Order Validation, Order Allocation, Backorder Management, Customer Notifications) are ALL
   properties/actions of one header+line document. Stubbing it as free text (the 4.1-style workaround) doesn't
   work here the same way it didn't work for 4.3's inventory spine (L37) — you cannot allocate, backorder, or
   validate credit against text.
3. **No collision precedent applies the way `crm.PurchaseOrder` did.** `crm.PurchaseOrder` (1.12) and
   `scm.PurchaseOrder` (4.1, canonical) legitimately coexist because CRM built ITS OWN simple version first for a
   different audience (a CRM rep's quick reorder) before SCM built the rich procurement one. `SalesOrder` has no
   such prior art in `crm` — there is nothing to coexist with, so this is a clean single ownership case, closer
   to 4.3's `Item`/`Location`/`StockMove` precedent than to 4.1's `PurchaseOrder` precedent.
4. **What Module 8 (Sales Management System) later EXTENDS by FK, never re-declares**, once it builds
   (`NavERP.md` 8.5–8.7 bullets):
   - `8.5` **CPQ/bundling/guided-selling, quote versioning, e-signature, customer-facing quote portal** — these
     stay on `crm.Quote` (already built) or a future richer quote entity; only the FINAL conversion step gets a
     `scm.SalesOrder` row (see `source_quote` field below).
   - `8.6` **Order Amendments & Cancellations (with impact analysis), Revenue Recognition & Scheduling (ASC
     606/IFRS 15), Order History & Reorder / subscription renewal** — these are commercial/financial workflow
     LAYERED ON `scm.SalesOrder` by FK (e.g. a future `accounting.RevenueSchedule` FK'd to
     `scm.SalesOrderLine`), not a second order table. **Two NavERP.md sections are both titled "Order
     Management" (4.5 here, and 8.6) — they are NOT the same feature set:** 4.5 is the supply-chain fulfillment
     orchestration (capture→validate→allocate→backorder→notify); 8.6 is the sales-side commercial lifecycle
     (amend/cancel/recognize revenue/reorder) that will FK into 4.5's order once Module 8 is built.
   - `8.7` **Territory/quota attribution per order** — mirrors how `crm.OpportunitySplit` attributes an
     Opportunity to reps/territories; a future `SalesOrderSplit` would FK to `scm.SalesOrderLine`, not fork it.
5. **Close-out task for whoever executes the "Write the module code" step (L36 step 2):** reconcile
   `NavERP-ERD.md` lines 463/470/471 so Module 1/8/9's "Adds" column stops listing `SalesOrder` as theirs and
   instead says "extends `scm.SalesOrder` by FK" — same treatment 4.1 and 4.3 already got. Not done here (this
   agent is read-mostly); flagged for the `todo` agent to carry as a checklist item.

## Leaders surveyed (with source links)

1. **Manhattan Active Omni (Order Management)** — enterprise omnichannel OMS; precise order promising + dynamic
   fulfillment-location selection — [Order Management System & OMS Solutions](https://www.manh.com/solutions/omnichannel-software-solutions/order-management-system), [Precise Order Promising](https://www.manh.com/solutions/omnichannel-software-solutions/order-management-system/precise-order-promising), [Omnichannel Allocation](https://www.manh.com/solutions/supply-chain-planning-software/inventory-allocation/omnichannel-allocation)
2. **IBM Sterling Order Management** — deep enterprise DOM; multi-level order orchestration, ATP/CTP, allocation
   optimized by cost/distance/time — [IBM Sterling Order Management](https://www.ibm.com/products/order-management), [product overview docs](https://www.ibm.com/docs/en/order-management?topic=overview-sterling-order-management-system-product)
3. **Oracle NetSuite (Order Management + Advanced Order Management)** — ERP-native OMS; allocation rules/waves,
   supply-allocation against incoming POs, backorder rules, SuiteFlow credit-hold workflows —
   [NetSuite Order Management](https://www.netsuite.com/portal/products/erp/order-management.shtml), [Handling Backorders](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_N2263962.html), [Advanced Order Management guide](https://netsuite.folio3.com/blog/advanced-order-management-in-netsuitepart-i-configuring-aom/)
4. **Kibo OMS** — Forrester Wave Leader distributed OMS; rules-based fulfillment-node routing, reverse-logistics
   add-on, guided fulfillment-workflow state machine — [Order Management System](https://kibocommerce.com/platform/order-management/), [OMS vs WMS](https://kibocommerce.com/blog/oms-vs-wms/)
5. **Fluent Commerce (Blue Yonder)** — cloud-native distributed-OMS specialist; configurable sourcing rules
   (profitability, split-shipment thresholds, per-store order caps, custom ATP rules) —
   [Fluent Order Orchestration](https://fluentcommerce.com/product/fluent-order-orchestration/), [Order Management Overview docs](https://docs.fluentcommerce.com/by-type/order-management-overview)
6. **Salesforce Order Management** — order capture across web/POS/marketplace, Flow-based fraud checks/approval,
   credit-memo-on-return handoff to ERP — [Salesforce Order Management help docs](https://help.salesforce.com/s/articleView?id=commerce.om_order_management.htm&language=en_US&type=5), [Order Fulfillment & Payment Automation](https://trailhead.salesforce.com/content/learn/modules/om-salesforce-order-management/om-streamline-order-fulfillment-payment)
7. **Brightpearl** — retail-ops OMS/ERP; automated order splitting on stockout, auto-fulfil backorders when
   restocked, multi-location allocation — [Order Management System guide](https://www.brightpearl.com/order-management-system), [Order Management Software](https://www.brightpearl.com/order-management-software)
8. **Cin7** — multichannel order routing with rules-based warehouse/3PL assignment on ingest —
   [Multichannel Order Management](https://www.cin7.com/blog/multichannel-order-management/), [Order Management features](https://www.cin7.com/features/sales/order-management/)
9. **Linnworks** — multichannel order routing + carrier-selection rules engine (destination/weight/channel/value)
   — [Multichannel order management system guide](https://www.linnworks.com/blog/multichannel-order-management-system/), [Linnworks vs Cin7](https://www.linnworks.com/blog/linnworks-vs-cin7/)

## Feature catalog (this sub-module only)

### Order Capture
- **Multi-channel order intake (manual/web/marketplace/EDI/API)** — a `source_channel` tag on the order records
  where it came from · seen in: Sterling, Salesforce OM, Cin7, Linnworks · priority: table-stakes · spine: new
  field on new `SalesOrder` · buildable now (the tag itself); the actual EDI/marketplace/API ingestion pipelines
  are integration/later.
- **Quote-to-order conversion** — turning an accepted quote into a live order without re-keying · seen in:
  Salesforce OM (order capture from CPQ), NetSuite (quote→SO), and closes a real gap in this repo:
  `crm.Quote.quote_accept()` currently does nothing downstream · priority: common · spine: `SalesOrder.source_quote`
  → **reuses verified `crm.Quote`** (string FK, nullable, `SET_NULL`) · buildable now (the FK + a "convert" action
  that copies `QuoteLine` rows into `SalesOrderLine` rows).
- **Order validation rules engine (structural)** — required-field/duplicate/min-order checks before an order can
  proceed · seen in: NetSuite, Sterling · priority: table-stakes · spine: `clean()`/`submit()` on new `SalesOrder`
  · buildable now.

### Order Validation
- **Credit-limit check / credit hold** — compare open AR balance to the customer's credit limit before releasing
  an order · seen in: NetSuite (SuiteFlow credit-hold workflows), Sterling, D365 · priority: table-stakes ·
  spine: **reuses verified `accounting.CustomerProfile.credit_limit`/`credit_on_hold`**, copying the exact
  `over_limit` computation `accounting.views.AccountsReceivable.Invoices.invoice_detail` already does (sum open
  `Invoice.total` for the party) — do NOT duplicate a credit-limit field on `SalesOrder`, only a derived
  `credit_hold` boolean + `hold_reason` set by `submit()` · buildable now.
- **Real-time inventory availability / ATP (available-to-promise)** — check on-hand (and, in the leaders,
  incoming supply) before confirming a promise date · seen in: Manhattan (its named differentiator), Sterling,
  NetSuite AOM (allocates against incoming POs too) · priority: differentiator for the incoming-supply version,
  table-stakes for the simple on-hand version · spine: **reuses verified `scm.Item.on_hand(location)`** ·
  buildable now for on-hand-only ATP; incoming-PO-aware ATP is deferred (see below).
- **Fraud detection / manual review flag** — flag suspicious orders (new customer + high value, mismatched
  ship/bill, velocity) for review before fulfillment · seen in: Salesforce OM (3rd-party fraud integration +
  Flow-based rule checks), Sterling · priority: common · spine: new fields `fraud_flag`/`hold_reason` on
  `SalesOrder` · buildable now as a simple rule (e.g. new-customer + amount-threshold); real fraud-scoring
  service is integration/later.
- **Order promising (requested vs. promised date)** — give the customer a promise date derived from real
  inventory/capacity, not just the requested date · seen in: Manhattan ("Precise Order Promising" is a named
  product feature), Sterling · priority: differentiator · spine: new fields `requested_date`/`promised_date` on
  `SalesOrder` · buildable now (promised date computed at `allocate()` time from what was actually reserved).

### Order Allocation
- **Assignment of order lines to specific fulfillment locations** — decide WHICH warehouse/location fills each
  line, possibly splitting one line across several · seen in: Manhattan ("omnichannel allocation," inventory
  segmentation), Sterling (allocation optimized by cost/distance/time), NetSuite AOM (allocation waves, priority
  rules), Fluent (per-location order caps, split-shipment thresholds) · priority: differentiator (this is the
  single most product-differentiating capability among the 9 surveyed) · spine: **new table**
  `SalesOrderAllocation` (line → `scm.Location`, verified existing, + quantity) — modeled as a soft reservation,
  deliberately NOT a `StockMove` (posting the physical move is a `PickTask`/4.4 job, keeps L37's append-only
  ledger the single source of physical truth) · buildable now for manual/staff-selected allocation; automatic
  cost/distance/SLA-optimized sourcing RULES (the part that makes Manhattan/Fluent/Sterling genuinely hard to
  clone) is differentiator/deferred.
- **Allocation waves / priority queues** — batch-allocate a backlog of orders in priority order when inventory is
  scarce · seen in: NetSuite AOM · priority: differentiator · deferred (needs the manual allocation flow first).

### Backorder Management
- **Partial allocation + backorder the remainder** — allocate what's available now, flag the shortfall, and
  auto-fulfil it later when stock arrives · seen in: Brightpearl ("automatically fulfill the sale" once restocked
  — its named feature), NetSuite (allow-backorder vs hold-until-in-stock config), Sterling · priority:
  table-stakes · spine: derived on `SalesOrderLine` — `quantity_allocated()` (sum of its
  `SalesOrderAllocation` rows), `quantity_backordered()` = `quantity_ordered − quantity_allocated()`,
  `is_backordered` property · buildable now for the flag/derived-quantity; the "auto-fulfil when stock arrives"
  re-trigger is deferred (needs a scheduled/event-driven re-allocation job).
- **Backorder-specific customer messaging** — tell the customer which lines are backordered and give an ETA ·
  seen in: Brightpearl, NetSuite · priority: common · spine: same `is_backordered`/`promised_date` fields feed
  the notification below · buildable now (data), integration/later (send).

### Customer Notifications
- **Automated order-lifecycle notifications (confirmation/shipped/delivered)** — seen in: every leader surveyed
  (table-stakes across the whole category) · priority: table-stakes · spine: new timestamp fields on
  `SalesOrder` (`confirmation_sent_at`, etc.) as the data hook · **integration/later** — actual email/SMS
  dispatch (SendGrid/Twilio-class service) is out of scope for this pass; this pass only stamps WHEN a
  notification event would have fired, matching how 4.4's `YardVisit.carrier_name` is a hand-off placeholder for
  4.6 TMS.

### Beyond the bullets
- **AR/ERP hand-off on fulfillment** — linking the order to the invoice it generates · seen in: Fluent, Sterling
  ("ERP handoff" language) · priority: common · spine: `SalesOrder.invoice` → **reuses verified
  `accounting.Invoice`** (nullable, `SET_NULL`) · buildable now (manual link this pass; auto-generating the
  `Invoice` from a fulfilled order is a natural next-pass enhancement, not required to close 4.5).
- **Ship-to address capture** — seen in: all 9 (table-stakes) · spine: `SalesOrder.ship_to_address` → **reuses
  verified `core.Address`** · buildable now.

## Recommended build scope (this pass — 2 models)

Folder convention (matching 4.4's `WarehouseManagement` — the "System (WMS/OMS)" suffix is dropped):
`apps/scm/{models,forms,views,urls}/OrderManagement/`, templates `templates/scm/orders/<entity>/`.

1. **`SalesOrder`** [`SO-`] + **`SalesOrderLine`** — the header+line document the whole sub-module hangs off,
   justified by ALL FIVE NavERP.md bullets at once:
   - Header: `customer` → `core.Party` (via a new `_customer_parties(tenant)` helper mirroring `scm`'s existing
     `_supplier_parties`, filtering `PartyRole(role='customer')` — Order Capture); `ship_to_address` →
     `core.Address` (Order Capture); `source_channel` (`manual/web/marketplace/edi/api/phone`, Order Capture);
     `source_quote` → `crm.Quote` nullable (Order Capture / quote-to-order); `order_date`, `requested_date`,
     `promised_date` (Order Validation — promising); `currency` → `accounting.Currency`; `payment_terms` →
     `accounting.PaymentTerm`; `status` (`draft/submitted/on_hold/allocated/partially_fulfilled/fulfilled/
     invoiced/cancelled/closed` — a 9-state lifecycle matching the existing `PurchaseOrder`'s complexity);
     `credit_hold` (bool, system-set by `submit()` reading `accounting.CustomerProfile`, Order Validation);
     `fraud_flag` (bool, system-set by a simple rule at `submit()`, Order Validation); `hold_reason` (text);
     `confirmation_sent_at`/`shipped_notification_at`/`delivered_notification_at` (nullable datetimes, Customer
     Notifications data hook); `invoice` → `accounting.Invoice` nullable (AR hand-off); `subtotal`/`tax_total`/
     `total` (derived, `editable=False`); `notes`. `TenantNumbered`.
   - Line: `sales_order` FK; `item` → **`scm.Item`** (`PROTECT` — real spine reuse, NOT free text, because unlike
     4.1's procurement lines this sub-module is built AFTER 4.3, so the item catalog already exists);
     `description` (optional override); `quantity_ordered`; `unit_price`; `discount_pct`/`tax_pct` (mirrors
     `crm.QuoteLine`'s convention for consistency); `line_subtotal`/`line_tax`/`line_total` derived properties
     (never stored); `quantity_allocated()`/`quantity_backordered()`/`is_backordered` derived from the child
     allocations below (Backorder Management). FKs: `scm.Item` (verified existing).

2. **`SalesOrderAllocation`** — serves **Order Allocation** as its own first-class record (not just a field),
   matching how Manhattan/Sterling/Fluent all model allocation as a distinct decision from the order line itself:
   `tenant`; `sales_order_line` → `SalesOrderLine` (`CASCADE`); `location` → **`scm.Location`** (`PROTECT` —
   verified existing, the specific fulfillment center/bin assigned); `quantity`; `status`
   (`reserved/released/cancelled`); `allocated_at`. Deliberately a **soft reservation, not a `StockMove`** — the
   physical pick/pack that actually moves stock stays 4.4's job (`PickTask`), preserving L37's rule that
   `StockMove` is the only ledger of physical truth. `clean()` guards `Σ quantity ≤ line.quantity_ordered`.
   `TenantOwned` (no own number — it's a child record, like `RFQVendor`/`OpportunitySplit`).

Both models FK only into **verified-existing** entities (`core.Party`, `core.Address`, `core.PartyRole`,
`accounting.Currency`, `accounting.PaymentTerm`, `accounting.CustomerProfile` (read, not FK'd), `accounting.Invoice`,
`crm.Quote`, `scm.Item`, `scm.Location`) — no new stand-ins are needed this pass because, unlike 4.1 (built before
4.3), the item/location spine already exists.

## Belongs to sibling sub-modules (parked, not scoped here)

- **RMA/return authorization, refund processing, disposition (repair/refurbish/scrap/restock), return portal,
  warranty claims** → **4.10 Returns Management (Reverse Logistics)** — NavERP.md 4.10 is a dedicated, fully-built-out
  sub-module for exactly this; do not build any return-shaped model in 4.5, even though "returns/RMA" is common OMS
  vendor territory generally.
- **Order Amendments & Cancellations (with impact analysis), Revenue Recognition & Scheduling (ASC 606/IFRS 15),
  Order History & Reorder / subscription renewal automation** → **Module 8.6 Order Management** (Sales) — see
  Ownership decision above for why this is a DIFFERENT "Order Management" from this one.
- **CPQ/bundling/guided selling, pricing & discount approval workflow, proposal templating/e-signature, quote
  versioning & customer-facing quote portal** → **Module 8.5 Quote & Proposal Management** (layers on top of the
  already-built `crm.Quote`, which stays thin).
- **Territory/quota attribution per order** → **Module 8.7 Territory & Quota Management** (future
  `SalesOrderSplit`, mirroring `crm.OpportunitySplit`).
- **Carrier selection, rate shopping, shipping-label rendering, real-time GPS tracking, freight audit** →
  **4.6 Transportation Management System** — already deferred by 4.4's own research/skill (`PickTask.tracking_number`
  is the existing hand-off placeholder). This sub-module's order does not select a carrier or generate a label.
- **Demand-based statistical safety-stock / forecast-driven pre-emptive allocation** → **4.7 Demand Planning &
  Forecasting**.
- **Customer self-service order-status/tracking portal (external login)** → **4.16 Customer Portal** / Module 9
  eCommerce storefront — no externally-authenticated customer login this pass (same L32 pattern as 4.1's Vendor
  Portal).

## Deferred (later passes / integrations)

- **Real email/SMS notification dispatch** (SendGrid/Twilio-class integration) — `confirmation_sent_at`/etc. are
  system timestamps this pass; actual sending is integration/later.
- **Automatic cost/distance/SLA-optimized sourcing rules engine** — this pass's `SalesOrderAllocation` is
  staff-selected (like 4.4's `PutawayTask.to_location`, editable but defaults to a suggestion); the auto-routing
  logic that makes Manhattan/Fluent/Sterling hard to clone is a real differentiator for a later enhancement pass.
- **Allocation against incoming supply (open POs), not just current on-hand** — NetSuite AOM's "supply
  allocation" is genuinely more advanced than a first pass needs; this pass's `Item.on_hand()` check is
  on-hand-only.
- **Auto re-allocation when stock arrives** (Brightpearl's auto-fulfil-on-restock) — needs an event hook off
  `StockMove` receipts; not built this pass, `is_backordered` is a query-time flag only.
- **Third-party/ML fraud scoring** — `fraud_flag` this pass is a simple rule (new customer + amount threshold),
  not a scoring service.
- **EDI/marketplace ingestion pipelines** — `source_channel` is the data tag this pass; the actual
  Shopify/Amazon/EDI connectors are integration/later.
- **`PickTask.sales_order`/`sales_order_allocation` FK** — `research-scm.md` and `research-scm-4.4.md` already
  flagged this: once this sub-module lands, `PickTask` should gain a nullable FK to `SalesOrderAllocation` (more
  precise than a bare `SalesOrder` FK, since one line can split across allocations) alongside the existing
  `transfer` FK (relaxed to nullable), so `PickTask` can serve either an inter-warehouse transfer or a real
  customer order without a schema rewrite. This is a **4.4 model change**, so it is a recommendation for the
  `todo`/build step, not part of this pass's own 1–2 new models.
- **`NavERP-ERD.md` reconciliation** (L36 step 2) — rows 463/470/471 currently list `SalesOrder` under Modules
  1/8/9's "Adds" column; rewrite them to say "extends `scm.SalesOrder` by FK" once this sub-module ships, mirroring
  the treatment already given to `PurchaseOrder` (4.1) and `Item`/`Location`/`StockMove` (4.3). Not done by this
  read-mostly research agent — flagged for the code-writing step's close-out.
- **Auto-generating `accounting.Invoice` from a fulfilled `SalesOrder`** — this pass only carries a manual/nullable
  `invoice` link; automated invoice creation on fulfillment is a natural next-pass enhancement.

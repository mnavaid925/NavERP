# Research — Sub-module 4.17: Third-Party Logistics (3PL) Management (Module 4 — Supply Chain Management, `scm`)

Target resolved from `NavERP.md` lines 845–850. `apps/core/navigation.py` carries `LIVE_LINKS` keys `"4.1"` …
`"4.16"` and **no `"4.17"`**, so 4.17 is the next unbuilt sub-module in Module 4.

The tenant here is the **3PL operator**. Its *clients* (depositors / stock owners) are `core.Party` rows carrying
the `customer` role. Everything below is written from that seat.

---

## Repo state checked first

**`LIVE_LINKS` built so far in module 4:** `4.1 … 4.16` (verified `apps/core/navigation.py:770–1104`; the dict ends
at `"4.16"`, the last key being `Document Retrieval → scm:portaldocumentshare_list`). No `"4.17"` / `"4.18"` /
`"4.19"` entry exists.

**Spine entities VERIFIED to exist** (`grep -rn "^class " apps/core/models/ apps/accounting/models/ apps/scm/models/`):

| Entity | File | Note for 4.17 |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` | `tenant`, `kind`, `name`, `tax_id`. The 3PL **client is a Party**, not a new company table. |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` | `ROLE_CHOICES` includes `customer`; `unique_together = ("party","role")`. |
| `core.Address` / `core.ContactMethod` / `core.Document` / `core.Activity` / `core.Tenant` | `apps/core/models/*.py` | All exist. `Address` has **no postal-code field** (already documented at 4.10/4.16). |
| `accounting.Invoice` + `InvoiceLine` | `apps/accounting/models/AccountsReceivable/Invoices.py:6,81` | `Invoice(kind=invoice\|credit_note, party→core.Party PROTECT, issue_date, due_date, status=draft…, currency, payment_terms, journal_entry, subtotal/tax_total/total editable=False)`. `InvoiceLine(description, quantity, unit_price, **tax_rate_pct**, line_total editable=False, gl_account)`. **`InvoiceLine` has NO `tax_code` FK** — a client default tax must be a `tax_rate_pct` decimal, not a `TaxCode` FK. |
| `accounting.Bill` / `Payment` / `JournalEntry` / `GLAccount` / `FiscalPeriod` / `Currency` / `TaxCode` | `apps/accounting/models/**` | All exist. `accounting.PaymentTerm` is FK'd already from `scm.SalesOrder:70`, `scm.PurchaseOrder:45`, `scm.SupplierContract:77`. |
| `scm.Item` / `ItemCategory` / `UOM` | `apps/scm/models/InventoryManagement/Items.py:63,24,41` | Item has `sku`, `category`, `uom`, `costing_method`, `average_cost` (cached, `editable=False`), `on_hand()` = **aggregate over `StockMove`**. **No owner/client column.** |
| `scm.Location` | `apps/scm/models/InventoryManagement/Locations.py:14` | `code`, `location_type` (`warehouse/zone/bin/staging/transit`), self-`parent`, `capacity`, `abc_class`, `storage_condition`. **No owner/client column.** |
| `scm.StockMove` | `apps/scm/models/InventoryManagement/StockMoves.py:13` | Append-only, signed `quantity`, `unit_cost`, `move_type`, `moved_at`, `reference`. **No owner column** — on-hand is *always* the ledger aggregate (L37). |
| `scm.LotSerial` | `apps/scm/models/InventoryManagement/LotSerials.py:5` | exists. |
| `scm.GoodsReceiptNote` / `GoodsReceiptLine` | `.../ProcurementManagement/GoodsReceiptNotes.py:15,166` | `receipt_date`, `status`, `location`, `bill→accounting.Bill`; line has `po_line→PurchaseOrderLine`, `quantity_received/rejected`. |
| `scm.PutawayTask` | `.../WarehouseManagement/PutawayTasks.py:16` | `goods_receipt`, `item`, `to_location`, `quantity`, `status`, `completed_at`. |
| `scm.PickTask` / `PickTaskLine` | `.../WarehouseManagement/PickTasks.py:16,84` | Task has `strategy`, `zone`, `package_count`, `package_weight`, `picked_at`, `packed_at` and **no order FK**; line has `item`, `from_location`, `quantity_requested/picked`. Client attribution therefore runs through **the line's item**. |
| `scm.CycleCountTask` / `CycleCountTaskLine` | `.../WarehouseManagement/CycleCountTasks.py:16,90` | line has `item`, `expected_quantity` (editable=False), `counted_quantity` → the inventory-accuracy SLA source. |
| `scm.SalesOrder` / `SalesOrderLine` | `.../OrderManagement/SalesOrders.py:20,185` | `customer→core.Party PROTECT`, `order_date`, `promised_date` (editable=False), `status`, `currency`, `payment_terms`, `invoice→accounting.Invoice`. |
| `scm.Shipment` / `TrackingEvent` | `.../TransportationManagement/Shipments.py:18,148` | `direction`, `carrier`, `sales_order`, `planned_pickup_date`, `planned_delivery_date`, `actual_pickup_at`, `actual_delivery_at`, `weight_kg`, `volume_cbm`, `package_count`, `freight_cost_estimate`, `pod_received`. The on-time SLA source. |
| `scm.Carrier` / `CarrierRateCard` | `.../TransportationManagement/Carriers.py:47,151` | **The rate-card precedent to copy**: `rate_basis` choices (`flat/per_mile/per_km/per_kg/per_cbm/per_pallet`), `base_rate`, `fuel_surcharge_pct`, `min_charge`, `currency→accounting.Currency`, `effective_from/to`, `is_active`. `Carrier.recompute_scorecard()` is the **derived-metric precedent** for SLA measurement. |
| `scm.FreightInvoice` / `FreightInvoiceLine` | `.../TransportationManagement/FreightInvoices.py:16,136` | **The accounting hand-off precedent**: audits, then sets `bill→accounting.Bill` (nullable, `editable=False`) and posts **no** JournalEntry (L29). |
| `scm.SupplierContract` | `.../SupplierRelationshipManagement/SupplierContracts.py:13` | `party`, `contract_type` (incl. `sla`, `logistics`), `start_date/end_date`, `auto_renew`, `renewal_notice_days`, `document→core.Document`, `currency`, `payment_terms`. Supplier/vendor-side — see "parked". |
| `scm.KpiTarget` / `KpiSnapshot` / `SupplyChainAlert` | `.../SupplyChainAnalytics/*.py` | `KpiTarget` has a **closed metric registry** (`METRIC_META`) and scopes `all/category/location/carrier/vendor` — **there is no client scope**, so 4.11 cannot express a per-3PL-client SLA. |
| `scm.PortalAccount` / `PortalOrderInquiry` / `PortalDocumentShare` / `PortalActivity` | `.../CustomerPortal/*.py` | 4.16 already owns the customer-facing entitlement console keyed on `customer→core.Party`. A 3PL client portal is *that*, not a second one. |
| `scm.ReturnAuthorization` | `.../ReturnsManagement/ReturnAuthorizations.py:48` | Drafts `accounting.Invoice(kind="credit_note", status="draft")` via `credit_note` FK — **the exact AR-side hand-off pattern 4.17's billing run should copy** (docstring line 15: "SCM posts NO JournalEntry"). |

**Spine entities verified NOT to exist (must be created or derived):**
- No `Client` / `Depositor` / `StockOwner` / `Warehouse` model anywhere — `grep -rn "^class .*\(Client\|Depositor\|Owner\|Tariff\|RateCard\)" apps/` returns only `scm.CarrierRateCard`.
- **No owner/client column on `Item`, `Location` or `StockMove`.** This is the single structural gap between the
  as-built inventory spine and every 3PL WMS surveyed.
- No billing-activity / billable-event table anywhere in `scm`.
- No SLA model in `scm` (`grep -rn "SLA" apps/scm` hits only 4.16 reading `crm.Case`'s clocks and
  `SupplierContract.contract_type="sla"`). `crm.SlaPolicy` exists but is a **case/ticket response-time policy**,
  not a logistics service level, and lives in another app's helpdesk.

**Free auto-number prefixes** (checked against every `NUMBER_PREFIX` in `apps/scm/models/`): `3PL`, `TAR`, `CBR`,
`SLA` are all unused. (Taken in scm: PR RFQ QT PO GRN SCR SRA SC CAT TRF ADJ PUT PIK CC YRD SO SHP LD CAR FRT SEA
DF DS FA WC BOM WO PRD QC QA NCR CAPA RMA WTY ALR KPI LIC CR TD ESG AST PM MWO LAB LST LSN LPL CCM EXC PAC PIQ PDS.)

**Sibling research files** — `research-scm.md:223` parked 4.17 wholesale ("client billing by storage volume/
transaction/weight, strict segregation, SLA monitoring, client-ERP sync, dedicated-vs-shared rental"). Four later
files deferred specific work here and form the starting backlog:
- `research-scm-4.12.md:630` — **SLA monitoring against a logistics contract** → "4.12 stores the obligation; 4.17
  measures the performance."
- `research-scm-4.14.md:561` — **3PL labor billing / cost-to-serve per client**.
- `research-scm-4.11.md:518` — **3PL billing / customer-facing analytics** (split 4.16 / 4.17).
- `research-scm-4.16.md:444` — **3PL client billing by volume/weight, SLA dashboards, client-ERP sync**.
- `research-scm-4.4.md:400` — yard/dock visits captured free-text, 3PL client attribution flagged forward.

---

## Leaders surveyed (with source links)

1. **Extensiv 3PL Warehouse Manager** (ex-3PL Central) — the category-defining multi-client 3PL WMS with a native
   billing engine; QuickBooks/QBO sync. — <https://www.extensiv.com/products/3pl-warehouse-manager>,
   <https://www.extensiv.com/blog/billing-per-client-in-3pl-wms-complete-guide>,
   <https://www.extensiv.com/blog/automated-invoicing-for-3pl-streamline-billing>,
   <https://www.extensiv.com/blog/multi-client-warehouse-guide-shared-3pl-solutions>
2. **CartonCloud** — warehouse + transport 3PL platform whose pitch is that every pick, pallet move and delivery
   is linked to a rate card so invoices fall out of what actually happened. —
   <https://www.cartoncloud.com/platform/billing-invoicing>
3. **Infoplus** — 3PL WMS with the most explicitly *modelled* billing engine: activity tables → billing rules →
   customer invoice templates → invoice worksheets. —
   <https://www.infopluscommerce.com/knowledge-base/overview-of-3pl-billing-in-infoplus>,
   <https://www.infopluscommerce.com/3pl-billing-solution>
4. **Softeon (Advanced 3PL Billing System)** — enterprise multi-client WMS; flexible rate-card definition,
   national/regional/local rates, "a robust array of methods for storage charges", non-WMS data into invoicing. —
   <https://www.softeon.com/news/softeon-extends-its-leading-software-solution-set-third-party-logistics-companies/>
5. **Da Vinci Unified (DVU WMS)** — 3PL WMS whose billing module advertises 50+ inbound/outbound charge codes and
   ~24 storage-charge options, plus recurring monthly contracts with overage tracking and freight pass-through /
   markup. — <https://dvunified.com/3pl/automating-3pl-billing-with-a-wm/>, <https://dvunified.com/industries/3pl/>
6. **SphereWMS** — multi-client warehousing with per-client billing profiles, storage fees by space/weight/
   duration, VAS logging (kitting, repack, labelling), daily→custom invoicing intervals, billing audit trail. —
   <https://spherewms.com/features/3pl-billing>, <https://spherewms.com/features/multi-client-warehousing>
7. **Deposco** — native multi-client architecture with data separation and per-client workflows; month-end billing
   pulls consolidated statements per client; fast client onboarding. — <https://deposco.com/blog/3pl-billing/>,
   <https://deposco.com/industries/third-party-logistics-3pl/>
8. **Logiwa WMS** — cloud 3PL/e-commerce WMS: multi-client operations, per-client allocation and shipment rules,
   headless/API architecture for client-facing integrations. —
   <https://www.logiwa.com/3pl-warehouse-management-software>
9. **Mecalux Easy WMS — WMS for 3PL** — records condition/location/**owner** of every good; the *3PL Automated
   Billing* module quantifies activities and assigns each to the corresponding customer; a *3PL Client Portal*
   gives stock owners restricted per-user access. —
   <https://www.mecalux.com/software/3pl-warehouse-management-software>
10. **Camelot 3PL Software — Excalibur WMS** — 3PL-only WMS; automatically computes storage, labour and material
    charges and invoices on demand. — <https://www.3plsoftware.com/solutions/wms>
11. **Industry practice on storage-period methods and SLAs** (used to pin vocabularies, not a product):
    split-month vs anniversary vs calendar billing — <https://blog.shipperswarehouse.com/split-month-billing-bargain-or-bust>,
    <http://www.coreflexoffice.com/help/3pl/billing/billing_account_level_example_2.htm>;
    3PL SLA KPIs, service credits and caps — <https://redstagfulfillment.com/how-to-manage-3pl-performance/>,
    <https://www.shippingcostoptimization.com/fulfillment-3pl-context/3pl-contract-clauses-sla-examples>,
    <https://dclcorp.com/blog/fulfillment/service-level-agreement/>;
    dedicated vs shared space commercial models — <https://blog.knightswiftsc.com/shared-warehousing-vs-dedicated-warehousing>,
    <https://3plguys.com/articles/dedicated-vs-shared-warehouse>;
    client-ERP integration surface (EDI 940/943/944/945/947) — <https://www.cleo.com/blog/3PL-integration-guide>,
    <https://www.dckap.com/blog/3pl-edi-integration/>

---

## Feature catalog (4.17 only)

### Bullet 1 — Client Billing ("automated billing based on storage volume, transactions, or weight handled")

**The client account master**

- **Client account = a profile on an existing customer Party** — one row per depositor carrying the commercial
  configuration (code, status, cycle, minimums), with identity staying on `core.Party`. · seen in: every product
  surveyed (Extensiv "customer", Infoplus "customer", Mecalux "stock owner", Softeon "client") · priority:
  **table-stakes** · spine: **new table `LogisticsClient`, `party → core.Party` (PROTECT)** — exactly the
  `scm.Carrier`/`SupplierProfile` precedent, never a second company table · buildable now
- **Short client code stamped on everything** — the 3–8 char code that appears on labels, feeds and invoices. ·
  seen in: Extensiv, Infoplus, Mecalux · priority: table-stakes · spine: `LogisticsClient.code`, unique per tenant
  · buildable now
- **Parent/child client accounts** — a client with several divisions billed together or separately. · seen in:
  Extensiv ("parent-child account relationships for clients with multiple divisions") · priority: common · spine:
  self-FK `LogisticsClient.parent_client` (the `Location.parent` / `SupplierContract.parent_contract` precedent) ·
  buildable now
- **Client lifecycle status** — prospect → onboarding → active → suspended → terminated; suspension has billing
  consequences, and onboarding speed is a competitive claim (Deposco: "new clients in two hours"). · seen in:
  Deposco, Extensiv, Softeon · priority: common · spine: `LogisticsClient.status` · buildable now

**The tariff / rate card**

- **Per-client rate card with effective dates and versioning** — separate rate cards per client, each with an
  effective range, superseded rather than edited. · seen in: Extensiv ("separate rate cards for each client …
  effective date ranges"), Softeon ("highly flexible rate card definition"), CartonCloud, SphereWMS · priority:
  **table-stakes** · spine: **new `ClientRateCard` header + `ClientRateCardLine` child**; follows
  `CarrierRateCard`'s field vocabulary (`effective_from/to`, `is_active`, `currency→accounting.Currency`) ·
  buildable now
- **Charge basis vocabulary is the heart of the model** — per pallet position, per sq ft, per m³, per unit, per
  order, per order line, per receipt/carton, per shipment, per kg, per hour, flat recurring, % of value. · seen
  in: Extensiv (pallet position / sq ft / cubic; per-order + per-line + per-unit pick charges), CartonCloud
  (weight/cubic/quantity/zone), Infoplus (per order, per item, storage, pick/pack, transport), SphereWMS
  (space/weight/duration), Da Vinci (50+ charge codes) · priority: **table-stakes** · spine:
  `ClientRateCardLine.charge_basis` choices · buildable now
- **Charge categories** — storage · inbound/receiving handling · outbound handling (pick/pack/ship) · value-added
  services · accessorials · transportation pass-through · recurring · minimum. · seen in: all surveyed · priority:
  table-stakes · spine: `ClientRateCardLine.charge_category` · buildable now
- **Rate variation by warehouse and by product group** — national/regional/local rates; different rates for
  hazmat, cold, oversize. · seen in: Softeon ("national, regional and local rates"), Extensiv, CartonCloud
  ("zone-based surcharges") · priority: common · spine: nullable `applies_to_location → scm.Location` and
  `applies_to_item_category → scm.ItemCategory` on the rate line (both verified) · buildable now
- **Free allowance + per-occurrence minimum on a charge** — e.g. first 50 pallet positions free, £5 minimum per
  receipt. · seen in: Extensiv (volume discounts / minimums), OneBill, CartonCloud · priority: common · spine:
  `included_quantity` + `minimum_charge` on the rate line (`CarrierRateCard.min_charge` precedent) · buildable now
- **Tiered / volume-banded pricing** — rate falls as volume climbs. · seen in: Extensiv ("tiered pricing, volume
  discounts"), OneBill, SphereWMS ("dynamic rate structuring") · priority: common · spine: `tier_from` /
  `tier_to` band columns on the rate line so a tier ladder is several lines, **not** a separate tier table ·
  buildable now (a full ladder engine is deferred)
- **Seasonal / promotional rate adjustment** — surge rates for peak. · seen in: SphereWMS, Extensiv ("seasonal
  adjustments") · priority: differentiator · spine: expressed as a second rate card with a peak effective range —
  no new field · buildable now
- **Revenue GL account per charge type** — storage revenue vs handling revenue split in the ledger. · seen in:
  Extensiv/Infoplus accounting exports · priority: common · spine: `gl_account → accounting.GLAccount` on the rate
  line, which maps 1:1 onto the verified `InvoiceLine.gl_account` · buildable now

**Storage charging over time — the most 3PL-specific concept in the whole sub-module**

- **Storage billing method** — `calendar_month` (all stock on hand at period start) · `anniversary` (each receipt
  bills on its own monthly anniversary of receipt date) · `split_month` (full month if received 1st–15th, half
  month if 16th–end) · `average_daily` (mean daily on-hand across the period) · `snapshot` (a point-in-time
  count). · seen in: Extensiv (names snapshot / anniversary / average daily explicitly), Softeon ("robust array of
  methods for storage charges"), Da Vinci ("two dozen different options for storage charges"), COREflex
  (anniversary worked example), Shippers Group (split month) · priority: **table-stakes for a real 3PL, and the
  single strongest differentiator vs a generic WMS** · spine:
  `LogisticsClient.storage_billing_method` + the billing run's derivation over the **existing append-only
  `StockMove` ledger** — no stored storage counters anywhere (L37) · buildable now
- **Storage measured in pallet positions / sq ft / cubic volume, accrued daily, billed monthly** · seen in:
  Extensiv ("measured in pallet positions, square footage, or cubic volume — typically calculated daily and
  billed monthly"), CartonCloud (per pallet / per location / per SKU), SphereWMS · priority: table-stakes · spine:
  `charge_basis` + `period` on the rate line; quantity derived from `StockMove` · buildable now

**Cycle, run and invoice**

- **Per-client billing cycle** — weekly, biweekly, monthly, quarterly, and clients on different cycles in one
  building. · seen in: CartonCloud (daily/weekly/monthly), Extensiv ("some clients monthly, others weekly"),
  SphereWMS ("daily, weekly, monthly, or any custom period") · priority: **table-stakes** · spine:
  `LogisticsClient.billing_cycle` + `next_billing_date` · buildable now
- **A reviewable draft billing run before anything is invoiced** — Infoplus literally ships this as an *Invoice
  Worksheet* with line detail; CartonCloud has "pre-finalisation review and adjustment". · seen in: Infoplus,
  CartonCloud, Deposco, Extensiv ("compiles all captured activities into draft invoices") · priority:
  **table-stakes** · spine: **new `ClientBillingRun` + `ClientBillingRunLine`** · buildable now
- **Every charge line traceable to the operational record that caused it** — the dispute-resolution feature every
  vendor leads with. · seen in: CartonCloud ("full charge traceability linked to operational data"), SphereWMS
  (audit trail), Infoplus (Invoice Worksheet Line Detail), Extensiv ("invoices that clients can audit") ·
  priority: **table-stakes** · spine: `ClientBillingRunLine.source_reference` + `rate_card_line` FK; the underlying
  documents (`GRN-…`, `PIK-…`, `SHP-…`) already exist and are already numbered · buildable now
- **Minimum monthly charge applied as a top-up** — "$10,000 monthly minimum, transactional charges applied against
  the minimum". · seen in: Extensiv (explicit), Da Vinci (fixed monthly contracts with overage tracking), Softeon
  · priority: **common, and cheap** · spine: `LogisticsClient.minimum_monthly_charge` → a computed
  `charge_category="minimum"` run line · buildable now
- **Manual / ad-hoc charge line on the run** — the VAS or one-off accessorial an operator adds before approval. ·
  seen in: CartonCloud, SphereWMS (VAS logging), Infoplus · priority: common · spine:
  `ClientBillingRunLine.is_manual` with a null `rate_card_line` · buildable now
- **Approved run drafts a customer invoice — and stops there** · seen in: Extensiv/Infoplus/CartonCloud/SphereWMS
  all export to QuickBooks / Xero / NetSuite / Sage rather than owning AR · priority: **table-stakes** · spine:
  **reuses `accounting.Invoice` (`kind="invoice"`, `status="draft"`, `party = client.party`) + `InvoiceLine` per
  run line**, linked by a nullable `editable=False` FK — the verified `ReturnAuthorization.credit_note` and
  `FreightInvoice.bill` pattern. **No JournalEntry, no second AR ledger (L29).** · buildable now
- **Freight pass-through or marked-up freight billing** · seen in: Da Vinci (explicit), CartonCloud (fuel levy),
  Extensiv ("actual carrier charges or markup structures") · priority: common · spine: a
  `charge_category="transportation"` rate line whose quantity comes from the verified
  `Shipment.freight_cost_estimate` / `scm.FreightInvoice` · buildable now (parcel-invoice import deferred)
- **Parcel carrier invoice import (UPS/FedEx) as a billing source** · seen in: Infoplus (explicit) · priority:
  differentiator · spine: would need a parcel-invoice feed · **integration/later**
- **User-scripted billing rules** · seen in: Infoplus ("scripting will be required … Infoplus will not write,
  edit or maintain customer scripts") · priority: differentiator · spine: deliberately **not built** — a closed
  `charge_basis` registry with reviewed resolvers, same reasoning as `KpiTarget`'s closed metric registry ·
  **out of scope, permanently**

### Bullet 2 — Client Inventory Segregation ("strict separation of inventory belonging to different clients")

- **Ownership is carried on the SKU: every item belongs to exactly one client** — in a 3PL WMS the same physical
  product held for two clients is two SKUs, and every transaction is tagged with the client identifier. · seen in:
  Extensiv ("client-level inventory segregation is non-negotiable … each transaction tagged with client
  identifiers"), Mecalux ("indicates the condition, location and **owner** of each good"), Logiwa, Deposco,
  Zenventory · priority: **table-stakes** · spine: **one additive nullable column
  `Item.owner_client → scm.LogisticsClient` (SET_NULL)** — *not* a new table and *not* a column on `StockMove`.
  Precedent: 4.4 added four bin columns to `Location`, 4.13 added `is_spare_part` and 4.15 added
  `storage_condition` to `Item`; all additive, all-default, no backfill. This one column makes every existing
  ledger row attributable, because **every `StockMove`, `PickTaskLine`, `PutawayTask`, `CycleCountTaskLine` and
  `GoodsReceiptLine` already reaches an `Item`** (verified — note `PickTask` itself has no order FK, so the item
  is the *only* path to the client). · buildable now
- **Physical segregation by dedicated zone/aisle** — the layout half of segregation. · seen in: Extensiv
  ("dedicating specific zones or aisles to individual clients"), Knight-Swift, Kanban Logistics · priority: common
  · spine: **one additive nullable column `Location.owner_client → scm.LogisticsClient` (SET_NULL)**; doubles as
  the dedicated-space allocation for bullet 5 · buildable now
- **Per-client stock, movement and valuation view** — each client sees only their own on-hand, movements and
  value. · seen in: all surveyed · priority: **table-stakes** · spine: **derived — a filtered query over the
  existing `StockMove` ledger and `Item.on_hand()`; NO new stock table and no second on-hand column** (L37, the
  StockMove docstring's own rule) · buildable now
- **Client-scoped rules: allocation, FIFO vs LIFO, lot vs serial capture, picking strategy** · seen in: Extensiv
  ("one client needs lot tracking and FIFO, another serial capture and LIFO"), Logiwa (per-client allocation and
  shipment rules), Softeon ("nearly every attribute configurable at client level"), Mecalux (*Directives*) ·
  priority: common · spine: **already exists per item** — `Item.costing_method` (`weighted_avg/fifo/lifo`) and
  `Item.tracking` (`none/lot/serial`) are verified fields, and ownership is now on the item, so client-specific
  behaviour follows for free. Nothing new. · buildable now
- **Cross-client contamination guard** — a client's stock must never be allocated, picked or billed against
  another client. · seen in: implicit in every product; Extensiv states it as a hard rule · priority:
  **table-stakes (security)** · spine: `clean()` guards on the new models (the verified
  `PortalAccount.clean()` ship-to ownership guard and `KpiTarget.clean()` tenant guard are the patterns) ·
  buildable now

### Bullet 3 — SLA Management ("monitoring Service Level Agreements for each client")

- **Per-client, per-metric service level with a numeric target** · seen in: Red Stag scorecard guide, DCL,
  Shipping Cost Optimization contract-clause guide, OWD, Softeon ("contract and billing management") · priority:
  **table-stakes for this bullet** · spine: **new `ClientSLA`**, one row per (client, metric) — the grain
  `KpiTarget` uses for network metrics. **`KpiTarget` cannot be reused**: its verified `SCOPE_CHOICES` are
  `all/category/location/carrier/vendor` with no client scope, and its `METRIC_META` registry carries no
  3PL-service metrics. · buildable now
- **The standard 3PL SLA metric set** — on-time shipping/delivery, OTIF, same-day-ship %, order accuracy,
  shipping accuracy, inventory accuracy (cycle-count variance), dock-to-stock hours, order cycle time, damage /
  shrinkage rate. · seen in: Red Stag, DCL, Cahoot, Shipium, SVDirect · priority: **table-stakes** · spine:
  closed `metric` choice list on `ClientSLA` · buildable now
- **Measured from the operational record, never typed in** — each metric resolves against verified as-built rows:
  on-time ← `Shipment.planned_delivery_date` vs `actual_delivery_at`; same-day/cycle-time ←
  `SalesOrder.order_date`/`promised_date` vs `Shipment.actual_pickup_at`; dock-to-stock ←
  `GoodsReceiptNote.receipt_date` → `PutawayTask.completed_at`; inventory accuracy ←
  `CycleCountTaskLine.expected_quantity` vs `counted_quantity`; damage ← `StockAdjustment` / `StockMove`
  (`move_type="adjustment"`). · priority: **table-stakes** · spine: a `recompute()` method writing
  `editable=False` result columns — the verified `Carrier.recompute_scorecard()` "evidence, not opinion" pattern,
  including its refusal to zero a score when there is no signal · buildable now
- **Typical target values as sensible defaults** — order accuracy 99.5 %+, inventory accuracy 97–99.8 %, shrinkage
  allowance 0.5–0.65 %, dock-to-stock 24–48 h. · seen in: Red Stag, DCL, Cahoot · priority: common · spine: form
  defaults / help text, not columns · buildable now
- **Breach detection with a warning band** — at-risk before breached. · seen in: Red Stag scorecards, Shipium ·
  priority: common · spine: `warning_threshold` + derived `status` (`meeting/at_risk/breached/no_data`) — the
  `KpiTarget` band pattern and `PortalOrderInquiry.sla_state`'s explicit `no_data ≠ ok` rule · buildable now
- **Service credits on breach, graduated and capped** — 5 % of monthly fees for a minor miss up to ~25 % for
  severe, capped at 5–20 % of aggregate monthly fees. · seen in: Shipping Cost Optimization, JIT Transportation,
  SVDirect · priority: **differentiator, and the feature that ties SLA to billing** · spine:
  `service_credit_pct` + `service_credit_cap_pct` on `ClientSLA`, surfaced as a suggested credit on the billing
  run · buildable now (auto-drafting the credit note is deferred)
- **Breach history / corrective action** · seen in: JIT ("formal corrective action plans"), Red Stag · priority:
  common · spine: `breach_count` + `last_measured_*` columns in v1; a full breach-event log is deferred — 4.9's
  `CapaAction` already exists for the corrective-action workflow · buildable now (partial)
- **Client-facing SLA scorecard / QBR pack** · seen in: Extensiv ("regular performance reports and business
  reviews"), Red Stag · priority: common · spine: a report page over `ClientSLA` — no table · buildable now
  (rendering it *to the client* is 4.16's portal)

### Bullet 4 — Client Integration ("APIs to sync data with the client's own ERP systems")

- **Per-client integration profile: what we sync with, and how** — the client's own system (SAP / NetSuite /
  Dynamics / Shopify / Amazon), the mode (manual · CSV · API · EDI · marketplace), the EDI trading-partner
  identity, and when we last synced. · seen in: Cleo, DCKAP and Celigo 3PL integration guides (EDI 940 shipping
  order, 943/944 transfer advice, 945 shipping advice, 947 inventory adjustment); Extensiv Integration Manager;
  Logiwa headless/API; Infoplus parcel-invoice import · priority: **table-stakes to record, integration/later to
  execute** · spine: data-only fields on `LogisticsClient` (`integration_mode`, `client_system`,
  `edi_partner_id`, `edi_qualifier`, `last_synced_at` `editable=False`) — the verified `PortalAccount.notify_on_*`
  posture: *record the intent, dispatch nothing, and do not let a label imply otherwise* · **data now, integration
  later**
- **The actual connector layer** — real 940/945 exchange, webhooks, REST endpoints, marketplace connectors. ·
  seen in: Extensiv, Logiwa, Infoplus, Cleo · priority: table-stakes in-market · spine: **belongs to 4.19
  Integration & API Gateway**, whose bullets are literally ERP connectors / e-commerce connectors / EDI / webhooks
  · **parked → 4.19**
- **SECURITY — do not add an endpoint URL + credential column.** Storing a client's API key or EDI password in a
  plain `CharField` on a tenant table is a credential-at-rest exposure and a cross-tenant blast radius. 4.17
  records *that* an integration exists and its non-secret partner identifiers only; secret handling is 4.19's
  problem, with a proper secrets store.

### Bullet 5 — Warehouse Rental Management ("billing logic for dedicated vs. shared warehouse space")

- **Space model on the client account: shared · dedicated · hybrid** — shared = variable per-unit pricing on what
  you actually occupy; dedicated = exclusive space at a fixed monthly cost regardless of usage; hybrid = a
  committed floor plus overflow at shared rates. · seen in: Extensiv ("Dedicated Space Agreements … exclusive
  access to defined storage capacity — perhaps 5,000 square feet or 200 pallet positions — regardless of actual
  usage"), Knight-Swift, 3PLGuys, Weber, Kanban Logistics · priority: **table-stakes for this bullet** · spine:
  `LogisticsClient.space_model` + `committed_sqft` + `committed_pallet_positions` · buildable now
- **Dedicated space bills the commitment, shared space bills the measurement** — this *is* the "billing logic" the
  bullet names. · seen in: Extensiv, Knight-Swift, 3PLGuys · priority: **table-stakes** · spine: a
  `charge_basis="dedicated_space"` rate line billed at `max(committed, actual)` (hybrid) or `committed` flat
  (dedicated), versus `per_pallet_position` / `per_sqft` billed from the derived `StockMove` occupancy (shared).
  **No separate rental table** — rental is a charge category on the tariff · buildable now
- **Which physical space is dedicated to whom** · seen in: Extensiv (client zones/aisles), Kanban Logistics
  ("dedicated space within a larger 3PL building") · priority: common · spine: the same
  `Location.owner_client` column added for bullet 2 — one column serving both bullets · buildable now
- **Occupancy vs commitment reporting (are we over- or under-selling the building?)** · seen in: Extensiv,
  Knight-Swift · priority: common · spine: derived report — committed positions per client vs
  `Location.capacity` (verified field) vs on-hand from `StockMove` · buildable now
- **Contract term and renewal on the space agreement** — dedicated 3–7 years, shared 1–3 with cancellation
  clauses. · seen in: Knight-Swift, 3PLGuys, OWD · priority: common · spine: `contract_start` / `contract_end` /
  `notice_days` / `contract_document → core.Document` on `LogisticsClient` (the verified `SupplierContract`
  field set, mirrored minimally rather than a second contract table) · buildable now

### Beyond the bullets (strong features the five bullets don't name)

- **Billing audit trail — who changed a rate, adjusted a line, applied a discount, and when** · seen in:
  CartonCloud ("timestamps and user actions"), SphereWMS ("every billing activity meticulously recorded"),
  Infoplus · priority: common · spine: **reuses the verified `core.AuditLog` / `core.Activity`**, plus
  `approved_by`/`approved_at`/`calculated_at` stamps on the run (the `FreightInvoice` precedent) · buildable now
- **Unbilled-activity / revenue-leakage view** — work done in the period that no rate line prices, which is where
  3PL margin actually leaks. · seen in: implied by every "capture every billable event" claim; Da Vinci frames it
  as revenue optimisation · priority: **differentiator, and cheap here** because both sides already exist ·
  spine: derived report comparing period activity against the run's lines · buildable now
- **Client onboarding checklist / time-to-live** · seen in: Deposco (two-hour onboarding claim), Extensiv ·
  priority: differentiator · spine: `status` + `onboarded_on` on `LogisticsClient`; a full checklist is deferred
- **Cost-to-serve / margin per client** (revenue from 4.17 vs labour cost from 4.14) · priority: differentiator ·
  spine: derived — but the *analytics* home is 4.11 · **parked → 4.11**, 4.17 supplies the revenue rows

---

## Recommended build scope (this pass — 4 models + 2 additive columns)

Package: `apps/scm/{models,forms,views,urls}/ThirdPartyLogistics/`. Templates: `templates/scm/3pl/<entity>/{list,detail,form}.html`.

1. **`LogisticsClient`** [`3PL-`] — `models/ThirdPartyLogistics/LogisticsClients.py`
   - **FKs (all verified):** `party → core.Party` (PROTECT, required — the client *is* a customer Party);
     `parent_client → self` (SET_NULL); `currency → accounting.Currency` (SET_NULL);
     `payment_terms → accounting.PaymentTerm` (SET_NULL); `default_revenue_account → accounting.GLAccount`
     (SET_NULL); `contract_document → core.Document` (SET_NULL); `account_manager → settings.AUTH_USER_MODEL`
     (SET_NULL).
   - **Fields justified by research:** `code`; `status` (prospect/onboarding/active/suspended/terminated);
     `billing_cycle` (weekly/biweekly/monthly/quarterly); `billing_day`; `next_billing_date`;
     `storage_billing_method` (calendar_month/anniversary/split_month/average_daily/snapshot);
     `minimum_monthly_charge`; `default_tax_rate_pct` (**a decimal, not a `TaxCode` FK — `InvoiceLine` carries
     `tax_rate_pct`**); `space_model` (shared/dedicated/hybrid); `committed_sqft`;
     `committed_pallet_positions`; `contract_start` / `contract_end` / `notice_days`; `integration_mode`
     (none/manual/csv/api/edi/marketplace); `client_system`; `edi_partner_id`; `edi_qualifier`;
     `last_synced_at` (editable=False); `onboarded_on` (editable=False, stamped once — the verified
     `PortalAccount.activated_on` pattern); `notes`.
   - **Derived (no columns):** on-hand quantity/value for this client, SKU count, occupied vs committed space,
     open SLA breaches, last billing run.
   - **Guards:** `party` must be tenant-matched and should carry the `customer` `PartyRole`; `space_model !=
     shared` requires a non-zero commitment (an L39 "conjunction that can never be true" check).

2. **`ClientRateCard`** [`TAR-`] **+ `ClientRateCardLine`** — `models/ThirdPartyLogistics/ClientRateCards.py`
   - Header FKs: `client → scm.LogisticsClient` (PROTECT); `currency → accounting.Currency` (SET_NULL).
     Header fields: `name`, `status` (draft/active/superseded/expired), `effective_from`, `effective_to`,
     `version`, `notes`.
   - Line (tenant-less child, reached via `rate_card.client.tenant` — the verified `CarrierRateCard` /
     `FreightInvoiceLine` precedent): `charge_category` (storage/receiving/outbound/value_added/accessorial/
     transportation/recurring/minimum); `charge_basis` (per_pallet_position/per_sqft/per_cbm/per_unit/per_order/
     per_line/per_receipt/per_carton/per_shipment/per_kg/per_hour/flat_recurring/**dedicated_space**/pct_of_value);
     `rate` (14,4); `period` (day/week/month) for storage & recurring; `included_quantity`; `minimum_charge`;
     `tier_from`/`tier_to`; `applies_to_location → scm.Location` (SET_NULL); `applies_to_item_category →
     scm.ItemCategory` (SET_NULL); `gl_account → accounting.GLAccount` (SET_NULL); `description`; `is_active`.
   - Justified by: per-client rate cards with effective dates (Extensiv, Softeon), the charge-basis vocabulary
     (Extensiv/CartonCloud/Infoplus/Da Vinci), regional and category rate variation (Softeon), allowances and
     minimums (Extensiv), and **the dedicated-space charge that carries bullet 5**.
   - **Guard:** `applies_to_location` must not be a `Location` owned by a *different* client (the verified
     `PortalAccount.clean()` ownership-guard pattern).

3. **`ClientBillingRun`** [`CBR-`] **+ `ClientBillingRunLine`** — `models/ThirdPartyLogistics/ClientBillingRuns.py`
   - FKs: `client → scm.LogisticsClient` (PROTECT); `rate_card → scm.ClientRateCard` (PROTECT);
     `invoice → accounting.Invoice` (SET_NULL, null, **editable=False**) — the hand-off;
     `approved_by → settings.AUTH_USER_MODEL` (SET_NULL, editable=False).
   - Fields: `period_start`, `period_end`, `status` (draft/calculated/approved/invoiced/void),
     `subtotal`/`minimum_adjustment`/`total` (all editable=False, recomputed from lines — the verified
     `FreightInvoice.recalc_amounts` Python-sum pattern, never an `F()` division), `calculated_at`, `approved_at`,
     `notes`.
   - Line: `rate_card_line` (SET_NULL, null = manual), `charge_category`, `charge_basis`, `description`,
     `quantity` (16,4), `rate` (14,4), `amount` (editable=False), `source_reference`, `is_manual`.
   - `calculate()` derives every quantity from **already-built rows** — `StockMove` (storage, by the client's
     `storage_billing_method`), `GoodsReceiptNote`/`GoodsReceiptLine` (receipts), `PutawayTask`,
     `PickTask`/`PickTaskLine` (outbound handling), `Shipment` (shipments, weight, freight pass-through) — all
     attributed through `Item.owner_client`. `draft_invoice()` creates
     `accounting.Invoice(kind="invoice", status="draft", party=client.party)` plus one `InvoiceLine` per run line
     (`description`, `quantity`, `unit_price=rate`, `tax_rate_pct=client.default_tax_rate_pct`, `gl_account`) and
     **posts no `JournalEntry`** (L29).
   - Justified by: the Invoice Worksheet (Infoplus), pre-finalisation review (CartonCloud), month-end consolidated
     statements (Deposco), automatic invoice compilation (Extensiv), minimum top-up (Extensiv), per-line
     traceability (CartonCloud/SphereWMS), accounting hand-off (all).

4. **`ClientSLA`** [`SLA-`] — `models/ThirdPartyLogistics/ClientSlas.py`
   - FKs: `client → scm.LogisticsClient` (CASCADE); `scope_location → scm.Location` (SET_NULL, optional).
   - Fields: `metric` (closed list: on_time_shipment_pct, otif_pct, same_day_ship_pct, order_accuracy_pct,
     inventory_accuracy_pct, dock_to_stock_hours, order_cycle_time_hours, damage_rate_pct, shrinkage_pct);
     `name`; `target_value`; `unit` (pct/hours/days); `direction` (higher_is_better/lower_is_better);
     `warning_threshold`; `measurement_window` (monthly/quarterly/rolling_30/rolling_90); `service_credit_pct`;
     `service_credit_cap_pct`; `is_active`; `notes`; and the evidence columns
     `last_measured_value` / `last_measured_at` / `measurement_summary` / `breach_count` / `status`
     (meeting/at_risk/breached/no_data) — **all `editable=False`**.
   - `recompute()` reads the verified operational tables listed under bullet 3; it must **not** zero a figure when
     there is no signal (`Carrier.recompute_scorecard` precedent) and must keep `no_data` distinct from `meeting`
     (`PortalOrderInquiry.sla_state` precedent).
   - Justified by: per-client SLA targets, the standard 3PL metric set, breach + graduated capped service credits,
     and the scorecard/QBR pack (Red Stag, DCL, Cahoot, Shipium, SVDirect, OWD, Shipping Cost Optimization).

**Two additive columns on 4.3 tables (no backfill, all-default, precedent = 4.4 on `Location`, 4.13/4.15 on `Item`):**
- `Item.owner_client → scm.LogisticsClient` (null, blank, SET_NULL) — **this is what makes bullet 2 work**, and it
  is the only path from `PickTask`/`PutawayTask`/`CycleCountTaskLine`/`StockMove` to a client.
- `Location.owner_client → scm.LogisticsClient` (null, blank, SET_NULL) — dedicated zone/aisle; serves bullets 2
  and 5.

**Bullet coverage — reuse/derivation vs new table:**

| Bullet | How it is covered |
|---|---|
| 1 Client Billing | **New:** `ClientRateCard(+Line)`, `ClientBillingRun(+Line)`. **Reuse:** `accounting.Invoice`/`InvoiceLine` draft hand-off, `accounting.Currency`/`GLAccount`/`PaymentTerm`, `core.Party`. |
| 2 Client Inventory Segregation | **No new table.** Two additive nullable columns + **derived** queries over the existing append-only `StockMove` ledger. Per-client FIFO/LIFO and lot/serial rules already exist as `Item.costing_method` / `Item.tracking`. |
| 3 SLA Management | **New:** `ClientSLA`. **Derived measurement** from `Shipment`, `SalesOrder`, `GoodsReceiptNote`, `PutawayTask`, `CycleCountTaskLine`, `StockAdjustment`. |
| 4 Client Integration | **No new table, no connector.** Data-only profile fields on `LogisticsClient`; execution parked to 4.19. Partially deferred — stated as such rather than half-shipped. |
| 5 Warehouse Rental Management | **No new table.** Commitment fields on `LogisticsClient` + `charge_basis="dedicated_space"` on the rate line + `Location.owner_client`. |

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Client-facing login, portal pages, document/invoice retrieval for the client** (Mecalux 3PL Client Portal,
  Extensiv branded portals, CartonCloud client self-service) → **4.16**, where `PortalAccount` /
  `PortalDocumentShare` / `PortalOrderInquiry` already exist keyed on `customer → core.Party`. 4.17 must not build
  a second portal or a second login binding.
- **EDI 940/943/944/945/947 exchange, REST connectors, webhooks, marketplace/e-commerce connectors** → **4.19**
  (its bullets are exactly ERP connectors / e-commerce connectors / EDI / webhooks).
- **Carrier rate cards, freight audit, carrier AP, POD, tracking** → **4.6** (`Carrier`, `CarrierRateCard`,
  `FreightInvoice`, `Shipment` all built). 4.17 only *re-bills* freight to the client.
- **Labour cost per client, units-per-hour productivity, task assignment** → **4.14** (`LaborSession`,
  `LaborActivity`, `LaborStandard`, `LaborPlan` built). 4.17 bills `per_hour` VAS; it does not measure labour.
- **Cycle counting, putaway/pick strategy, yard and dock scheduling execution** → **4.4**. 4.17 only *reads*
  those rows for SLA measurement and billing quantities.
- **Cost-to-serve / margin per client, client profitability trending, control-tower tiles** → **4.11**
  (`KpiTarget` / `KpiSnapshot` / `SupplyChainAlert`). 4.17 supplies the revenue rows.
- **The client contract document repository, renewal alerts, obligation register** → **4.2 / 4.12**
  (`SupplierContract` + `ComplianceRequirement`). 4.17 keeps only the commercial dates it bills against and a
  `core.Document` pointer. *(Open item for a later pass: `SupplierContract.party` is a plain `core.Party` FK, so a
  customer-side "client agreement" could live there — but the model, its related_name `scm_supplier_contracts`
  and 4.12's repository page are all supplier-framed. Renaming/generalising it is a cross-sub-module change, not
  4.17's to make.)*
- **AR aging, cash application, dunning, revenue recognition, tax determination, journal posting** → **Module 2
  accounting**. 4.17 stops at a draft `Invoice` (L29).
- **Kitting / assembly work orders as production** → **4.8** (`WorkOrder`, `BillOfMaterials`). 4.17 bills the VAS;
  it does not schedule it.
- **Returns processing performed on behalf of a client** → **4.10** (`ReturnAuthorization`, `ReturnDisposition`).
  4.17 may price it as a VAS charge.

---

## Deferred (later passes / integrations)

- **`ClientServiceEvent` — a billable-activity log captured at the moment work happens** (Infoplus "3PL Billing
  Activity tables", CartonCloud "every pick, pallet movement and handling task linked to billing", SphereWMS VAS
  logging). v1 *derives* quantities from the already-built operational tables and allows manual run lines, which
  is honest and avoids a duplicate activity ledger — but a first-class VAS/accessorial event table is the single
  most valuable next addition to this sub-module.
- **Scheduled/automatic billing runs** (cron or `next_billing_date` sweep). v1 creates and calculates a run from a
  human action; `next_billing_date` is recorded so a scheduler has something to read later.
- **Auto-drafting an `accounting.Invoice(kind="credit_note")` for an SLA service credit.** The percentages and cap
  are captured now; the `ReturnAuthorization.credit_note` precedent makes this a small follow-up.
- **A breach-event log with corrective actions** — v1 keeps `breach_count` + last measurement. 4.9's `CapaAction`
  already exists for the corrective workflow, so the join is cheap later.
- **True tiered/volume-discount ladders and formula-based rules** (Infoplus billing scripts, OneBill rating
  engine). Deliberately replaced by a closed `charge_basis` registry plus simple `tier_from`/`tier_to` bands —
  same reasoning as `KpiTarget`'s refusal to grow an expression language (that is Module 10's 10.11).
- **Parcel carrier invoice import (UPS/FedEx) as a billing source** (Infoplus) — needs a parcel feed.
- **Accounting-package sync (QuickBooks / Xero / NetSuite / Sage)** (Extensiv, CartonCloud, Infoplus, SphereWMS) —
  accounting owns AR; nothing in `scm` should export invoices.
- **Client API credentials / endpoint storage** — deliberately excluded on security grounds; 4.19 with a proper
  secrets store.
- **Weight-handled storage/handling charges from real weights** — `Shipment.weight_kg` exists, but `Item` has no
  weight/dimensions and `Location` has no sq-ft area (only `capacity` "in the bin's own units"). `per_kg` and
  `per_sqft` bases are therefore modelled and priceable now, with quantities entered on the run line until an
  item-dimension pass lands (the same free-text/stand-in posture 4.4 used for `YardVisit.carrier_name`).
- **Client onboarding checklist / go-live tracker** (Deposco) — `status` + `onboarded_on` only in v1.
- **Client-scoped user permissions inside the 3PL's own staff org** — `core.OrgUnit` exists; not a 4.17 concern.

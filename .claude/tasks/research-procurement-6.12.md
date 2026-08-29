# Research — Sub-module 6.12: Goods Receipt & Inspection (Module 6 — Procurement Management System, `procurement`)

Scope note: ONE sub-module. 6.12 has **ten** NavERP.md bullets — far more than one build pass can own — and the
single most important finding of this research is that **six of the ten are already built elsewhere in this
codebase**. The prioritisation below is therefore mostly an ownership map: which bullet points at an existing
page, which needs a new procurement-side table, and which is honestly deferred.

---

## Repo state checked first

### LIVE_LINKS built so far in module 6
`6.1 · 6.2 · 6.3 · 6.4 · 6.5 · 6.6 · 6.7 · 6.8 · 6.9 · 6.10 · 6.11` (`apps/core/navigation.py:1413-1566`).
**6.12 is the next unbuilt sub-module.** Sibling procurement models available to FK (all verified by
`^class` grep in `apps/procurement/models/`):

| Model | Where | Prefix |
|---|---|---|
| `AdvancedShipmentNotice` + `AsnLine` | `models/OrderFulfillment/AdvancedShipmentNotice.py:38,426` | `ASN-` |
| `DeliverySchedule` | `models/OrderFulfillment/DeliverySchedule.py:33` | `DSC-` |
| `Backorder` | `models/OrderFulfillment/Backorder.py:35` | `BKO-` |
| `PurchaseOrderChange` + `…Line` | `models/PurchaseOrderManagement/PurchaseOrderChanges.py:26,173` | `PCO-` |
| `ProcurementAlert` | `models/DashboardPortal/ProcurementAlerts.py:26` | (TenantOwned) |
| `VendorPortalAccess` / `VendorSuspension` / `VendorInvoiceSubmission` | `models/VendorManagement/…` | `VPA-`/`VSU-`/`VIS-` |

Prefixes already taken in `procurement`: `PCO EBID RQA VSU CMI EAUC VPA RFX POE DSC CAM PCI VIS BKO CUB ASN RAM
RQT RXR BID SEV`. **`RDS`, `RTV`, `TOL`, `GRC`, `RCV` are free** (grep for
`NUMBER_PREFIX = "(RTV|RDS|TOL|RCP|GRC|VRT|RCV)"` across `apps/` → no matches).

### Spine entities VERIFIED TO EXIST (grep evidence)

| Entity | Evidence | What it already does |
|---|---|---|
| `scm.GoodsReceiptNote` | `apps/scm/models/ProcurementManagement/GoodsReceiptNotes.py:15` | `[GRN-]`, `purchase_order` (PROTECT), `location`→`scm.Location`, `receipt_date`, `status` **draft/received/cancelled**, `delivery_note_ref`, `received_by`, `bill`→`accounting.Bill`, `match_status` (`not_matched/matched/price_variance/quantity_variance/over_received`), `match_notes`, `PRICE_TOLERANCE_PCT = 2`, `received_value()`, `billed_value()`, `recompute_match()` |
| `scm.GoodsReceiptLine` | `…/GoodsReceiptNotes.py:166` | `goods_receipt`, `po_line` (PROTECT), `quantity_received`, **`quantity_rejected` + `rejection_reason`**, `notes`. **No item FK, no lot field, no tenant field** (scoped through the header) |
| `scm.PurchaseOrder` / `…Line` | `…/PurchaseOrders.py:15,172` | `received_by_line()` (one query, excludes cancelled receipts), `rematch_receipts()`, `recompute_receipt_status()`, `PurchaseOrderLine.received_quantity()` (memoised) / `outstanding_quantity()`; lines are FREE TEXT (`item_description`/`sku_hint`/`uom_hint`) |
| `scm.StockMove` | `apps/scm/models/InventoryManagement/StockMoves.py:13` | Append-only signed ledger; `move_type` incl. `receipt`/`adjustment`/`transfer`; `unit_cost` IS the cost layer; `reference` carries the source doc number |
| `scm.LotSerial` | `apps/scm/models/InventoryManagement/LotSerials.py:5` | `item`, `kind` (lot/serial), `number`, **`expiry_date`**, `status` incl. `quarantine`; full CRUD at `scm:lotserial_list` (`apps/scm/urls/InventoryManagement/LotSerials.py:8-12`) |
| `scm.Item` / `ItemCategory` / `UOM` / `Location` | `…/InventoryManagement/Items.py:73,34,51`; `…/Locations.py:14` | The item + bin masters exist (contrary to the older "Module 5 will build them" note) |
| `scm.QualityInspection` + `InspectionResult` | `apps/scm/models/QualityManagement/QualityInspections.py:62,330` | `[QC-]`, **`inspection_type="incoming"`, `goods_receipt` FK already present (line 106)**, `sample_size`, `quantity_accepted/rejected`, `usage_decision` (accept / accept_with_deviation / reject), `action_taken` incl. **`quarantined` and `returned_to_vendor`**, snapshotted result rows with `_evaluate()` pass/fail |
| `scm.InspectionPlan` + `InspectionCharacteristic` | `…/QualityManagement/InspectionPlans.py:22,202` | Measurement characteristics, limits, CoA flags |
| `scm.NonConformance` | `…/QualityManagement/NonConformances.py:28` | `[NCR-]`; disposition vocabulary incl. `return_to_vendor`, which the views file documents as *"the decision only — the RMA document belongs to 4.10"* (`apps/scm/views/QualityManagement/NonConformances.py:12`) |
| `scm.WarrantyClaim` | `…/ReturnsManagement/WarrantyClaims.py:34` | `[WTY-]` supplier recovery claim for a FAILED unit (post-sale), `supplier_rma_number`. Its docstring carries an explicit **"FLAG TO MODULE 2/6: adding `Bill.kind` is the change that would unlock a real vendor credit"** |
| `scm.ReturnAuthorization` | `…/ReturnsManagement/ReturnAuthorizations.py:48` | `[RMA-]` — **CUSTOMER** returns (`customer` FK, `sales_order` FK). NOT a vendor return |
| `inventory.QuarantineOrder` | `apps/inventory/models/QualityControl/QuarantineOrders.py:48` | `[QRD-]` real segregation with **live StockMove legs** (transfer pair in, adjustment out on scrap); `reference` is FREE TEXT documented as e.g. `"GRN-00012"` |
| `inventory.QcChecklist` + `QcChecklistItem` | `…/QualityControl/QcChecklists.py:24,72` | Dock checklist DEFINITIONS scoped per item / per vendor / workspace-wide, mandatory vs advisory checkpoints |
| `inventory.QcRoutingRule` + `resolve_qc_routing()` | `…/QualityControl/QcRoutingRules.py:24,89` | **Inspect-vs-bypass routing for inbound receipts** with a most-specific-wins resolver (item 3 > category 2 > catch-all 1, vendor pin adds a point, then priority, then id) |
| `inventory.DefectReport` | `…/QualityControl/DefectReports.py:29` | `[DEF-]` floor defect capture with photo + write-off; requires `item` + `location` (stock ON HAND), escalates to `scm.NonConformance` |
| `inventory.PutawayRule`, `BarcodeLabel`, `ScanSession`/`ScanEvent`, `RfidTag`, `ShelfLifePolicy`, `CrossDockOrder` | `apps/inventory/models/{ReceivingPutaway,BarcodeRfidIntegration,LotSerialTracking,WarehousingBinManagement}/…` | Putaway suggestion rules, `[LBL-]` labels, scan console, `[TAG-]` EPC registry, shelf-life policy, cross-dock |
| `core.Party` / `PartyRole` / `AuditLog` / `Document` | `apps/core/models/{Party,PartyRole,AuditLog,Document}.py:5` | Vendor is a Party role; the audit trail is `core.AuditLog` via `apps.core.utils.write_audit_log` |
| `accounting.Bill` | FK'd by `scm.GoodsReceiptNote.bill` | AP owns the vendor bill |

### Spine entities verified NOT to exist
- **`apps/quality` does not exist.** `apps/*/apps.py` glob returns exactly: `core accounts tenants dashboard crm
  accounting hrm scm inventory procurement`. NavERP.md **Module 12 is the Quality Management System** (line 1818)
  — a future app. Today the quality layer is split: **SCM 4.9** owns the engineering/metrology side
  (`InspectionPlan` → `QualityInspection` → `NonConformance` → `CapaAction`) and **Inventory 5.15** owns the
  warehouse-floor side (`QcChecklist`, `QcRoutingRule`, `QuarantineOrder`, `DefectReport`). **6.12 must not open a
  third quality register** — it owns only the *commercial* consequences of a bad receipt (discrepancy claim, RTV).
- **No vendor-return document anywhere.** `return_to_vendor` exists only as a *disposition choice* on
  `scm.NonConformance` and `scm.ReturnDisposition` / `inventory.DispositionRoutingRule`, each with a comment saying
  the document belongs elsewhere. `scm.WarrantyClaim` is a post-sale failure claim, not a dock rejection return.
  **This is a real gap and it is 6.12's.**
- **No receipt-tolerance configuration anywhere.** The only tolerance in the codebase is the hardcoded
  `GoodsReceiptNote.PRICE_TOLERANCE_PCT = Decimal("2")` (a *price* tolerance for the three-way match). There is no
  over-/under-**quantity** tolerance, no early/late-days tolerance, and no per-item/vendor policy. **Real gap.**
- **`core.Item` does not exist** (only `scm.Item`). `scm.PurchaseOrderLine` and `scm.GoodsReceiptLine` are free
  text; 6.11's `AsnLine` deliberately mirrors that. Any 6.12 line model must mirror it too.

### Already-built behaviour 6.12 must NOT re-implement (this is the headline)
- **Inventory posting on acceptance is DONE.** `apps/scm/views/ProcurementManagement/GoodsReceiptNotes.py:117`
  `goodsreceipt_receive` is `@tenant_admin_required`, takes a `select_for_update()` row lock, flips
  `draft → received`, calls `_post_grn_receipt()` (`apps/scm/views/_helpers.py:299`) which posts one
  `move_type="receipt"` StockMove **per received line at the PO line's `unit_price` as the cost layer**, then
  `rematch_receipts()` + `recompute_receipt_status()`, then `write_audit_log(... "receive" ...)`. Lines whose
  free-text SKU resolves to no `scm.Item` are reported as `unmatched`, not silently dropped.
- **Receipt reversal is DONE.** `goodsreceipt_cancel` (line 164) posts **compensating** moves via
  `_reverse_grn_receipt()` (`_helpers.py:335`) — never deletes — and **refuses** the cancel if the stock has
  already been put away (it would drive the staging location negative). Audit row written inside the transaction.
- **Three-way match is DONE.** `recompute_match()` with an over-receipt-first precedence rule, plus a manual
  `goodsreceipt_rematch` verb.
- **The audit trail already covers GRNs.** `"goodsreceiptnote"` is in `PROCUREMENT_CONTENT_MODELS`
  (`apps/procurement/views/_helpers.py:29`), so receive/cancel/rematch rows already appear in
  `procurement:activity_list`.
- **Existing sidebar entries that already answer 6.12 bullets:** `"5.4"` maps *Goods Receipt Note (GRN)*,
  *Three-Way Matching*, *Quality Inspection (Receiving)* and *Putaway Logic*
  (`navigation.py:1193-1198`); `"5.15"` maps *QC Checklists*, *Inspection Routing*, *Quarantine Management*,
  *Defect & Scrap Reporting* (`:1348-1353`); `"5.14"` maps *Label Generation*, *Scanner Integration*, *RFID*
  (`:1285-1290`); `"4.9"` maps *Quality Inspection* (`:869-875`).

### 6.11's deferral list (the scope anchor)
`.claude/tasks/research-procurement-6.11.md:361-363` hands 6.12: *"Goods receipt creation from a confirmed ASN,
receipt tolerances, QC checklists, quarantine, lot/serial capture at receipt, discrepancy reports with photos,
RTV, barcoding/scanning, inventory posting, receipt reversal."* The documented hand-off hook is
`AdvancedShipmentNotice.supplier_reference → GoodsReceiptNote.delivery_note_ref`
(`AdvancedShipmentNotice.py:24, 213-227` — the model even enforces uniqueness of `supplier_reference` across live
ASNs *specifically so that 6.12's match is unambiguous*).

---

## Leaders surveyed (with source links)

1. **SAP S/4HANA MM (Inventory Management)** — the reference implementation of receipt tolerances. — [Applying Tolerances and the Delivery Completed Indicator](https://learning.sap.com/courses/inventory-management-and-physical-inventory-in-sap-s-4hana/applying-tolerances-and-the-delivery-completed-indicator)
2. **SAP S/4HANA QM (Quality Management at goods receipt)** — inspection lot created automatically at GR; stock lands in quality-inspection stock until a usage decision. — [Inspection for a Goods Receipt (SAP Help)](https://help.sap.com/docs/SAP_ERP/250374f0514e4e0f9057066374265eba/2514c453f57eb44ce10000000a174cb4.html) · [Incoming raw-material inspection (QA32) walkthrough](https://www.guru99.com/incoming-inspection-material-sap-qm.html)
3. **SAP Ariba Buying (+ Supply Chain Collaboration)** — the P2P receiving flow: accepted vs rejected quantities, receiving tolerances, auto-receipt, negative-value corrections, supplier-side quality notification. — [Understanding the Receive Process](https://learning.sap.com/courses/sap-ariba-procurement-buying/understanding-the-receive-process) · [Quality Notification process for Ariba SCC](https://community.sap.com/t5/spend-management-blog-posts-by-members/quality-notification-process-for-ariba-supply-chain-collaboration/ba-p/13564243)
4. **Oracle Fusion Cloud Receiving** — receipt routing (standard / inspection required / direct delivery), receiving parameters and tolerances, the inspection page, and vendor returns. — [Receiving (Fusion SCM)](https://docs.oracle.com/en/cloud/saas/supply-chain-management/21d/faims/receiving.html) · [Receipt Routing explained](https://fusionscminsights.blogspot.com/2025/09/receipt-routing-understanding.html) · [Receiving Parameters setup](https://www.techleadsit.com/blog/details/oracle-fusion-procurement-training-receiving-parameters) · [Inspect Receipts (Redwood)](https://docs.oracle.com/en/cloud/saas/readiness/common/rrdem/inspect-receipts-using-a-redwood-page.html) · [Return to Vendor integration (Oracle Cloud WMS 25D)](https://docs.oracle.com/en/cloud/saas/readiness/logistics/25d/wms25d/25D-wms-wn-f40964.htm)
5. **Microsoft Dynamics 365 Supply Chain Management** — quality associations (event-triggered quality orders), item sampling, inventory blocking during inspection, the six nonconformance types incl. **Vendor**. — [Quality and nonconformance management overview](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-management-processes) · [Quality orders](https://learn.microsoft.com/en-us/dynamics365/supply-chain/inventory/quality-orders)
6. **Oracle NetSuite (Item Receipt + NetSuite Quality Management)** — inspection queues triggered by item/vendor/location association, skip-lot sampling, the Quarantine workflow, and disposition → **Vendor Return Authorization**. — [Quality Workflows](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158627382429.html) · [Enhanced Receipt Return Authorization Workflow](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_0222101726.html) · [Receiving Orders](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/chapter_N2410585.html)
7. **Odoo (Inventory + Quality)** — quality control points bound to the *Receipt* operation type, Pass-Fail vs Measure-with-tolerance checks, photo checks, quality alerts, quarantine location on failure. — [Quality control points (Odoo 18)](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/quality/quality_management/quality_control_points.html) · [Odoo Quality](https://www.odoo.com/app/quality)
8. **Coupa** — receipts and receiving transactions in a pure P2P suite; tolerance holds when the invoice deviates from the PO beyond the allowed band; inspection codes on receiving transactions. — [Receipts API](https://compass.coupa.com/en-us/products/product-documentation/integration-technical-documentation/the-coupa-core-api/resources/transactional-resources/receipts-api) · [Receiving Transactions API](https://docs.coupa.com/en/developer-documentation/the-coupa-core-api/resources/transactional-resources/receipts-api/receiving-transactions-api-receiving_transactions)
9. **Ivalua** — mobile receipts, barcode scanning, supplier ASNs, real-time 3-way match with instant discrepancy detection, and **4-way match that adds inspection results**. — [Procure-to-Pay (P2P)](https://www.ivalua.com/solutions/process/procure-to-pay/)
10. **Procurify** — the SMB P2P receiving desk: pass/fail per line, decimal partial receipts, packing-slip upload linked to lines, unreceive/edit with audit logs, unbilled-PO feed to AP. — [How to Receive, Unreceive, and Manage Packing Slips](https://success.procurify.com/en/articles/9001632-how-to-receive-unreceive-and-manage-packing-slips) · [Receiving Inventory](https://www.procurify.com/procure-to-pay/procurement/receiving-inventory/)
11. **Precoro** — three-way matching with configurable tolerance limits, partial/multiple invoices per PO. — [Precoro product](https://precoro.com/product)
12. **Fishbowl / Epicor Kinetic (WMS end of the market)** — barcode-driven receiving, directed putaway to aisle/shelf/bin, license-plate receiving, vendor return reconciliation. — [Fishbowl Receive Goods](https://www.fishbowlinventory.com/features/receive-goods) · [Epicor Kinetic Warehouse Management](https://www.erpresearch.com/erp/epicor-kinetic/warehouse-management)

---

## Feature catalog (this sub-module only)

Legend for **spine**: `EXISTS →` means the capability is already live in this repo and the bullet should be mapped
to that page rather than rebuilt.

### Bullet 1 — Goods Receipt Note (GRN) Creation (partial + multiple receipts per line)

- **Partial receipt and multiple receipts against one PO line** — accept less than ordered now, more later; the
  outstanding balance is derived, never stored · seen in: SAP, Ariba, Oracle, Coupa, Procurify, Precoro ·
  priority: **table-stakes** · spine: **EXISTS →** `scm.GoodsReceiptLine` + `PurchaseOrderLine.received_quantity()`
  / `outstanding_quantity()` / `PurchaseOrder.received_by_line()` · nothing to build
- **Create the receipt FROM a confirmed ASN with lines pre-populated** — the dock opens the notice, adjusts
  quantities, and books · seen in: Oracle ("create receipts from a validated ASN"), NetSuite, Ivalua, Ariba ·
  priority: **table-stakes** · spine: **new VIEW over existing tables** — reads `procurement.AdvancedShipmentNotice`
  + `AsnLine`, writes `scm.GoodsReceiptNote` + `GoodsReceiptLine`, copies `supplier_reference` →
  `delivery_note_ref` (the documented 6.11 hook) · buildable now
- **Packing slip / delivery-note reference recorded on the receipt** · seen in: Procurify, Ariba, all · priority:
  **table-stakes** · spine: **EXISTS →** `GoodsReceiptNote.delivery_note_ref` · nothing to build
- **Packing-slip / POD document attached to the receipt and linked to lines** · seen in: Procurify (drag-drop or
  phone camera), Oracle (attachments on inspection) · priority: **common** · spine: fold into the new
  `ReceiptDiscrepancy.evidence` file rather than a generic attachment queue (the `inventory.DefectReport` photo
  precedent) · buildable now
- **Receiver identity + exact receipt date/time** · seen in: all · priority: **table-stakes** · spine: **EXISTS →**
  `received_by`, `receipt_date`; the ASN's POD block (`confirmed_by`, `delivered_at`, `received_signature_name`)
  covers the arrival moment · nothing to build
- **An arrivals / receiving worklist (what is due at the dock today)** · seen in: Oracle, Ivalua (mobile receipt),
  Procurify · priority: **common** · spine: **new computed page**; 6.11 already ships
  `procurement:delivery_confirmation`, so 6.12's console must be the *booking* desk (ASN → GRN), not a second
  arrivals board · buildable now
- **Auto-receipt on a threshold or event** (on ordered / on due date / on invoice reconciliation) · seen in: Ariba
  (explicit thresholds by amount / line amount / quantity), Procurify (auto-receive at PO creation) · priority:
  **common** · spine: would need a scheduler · **defer**
- **Unordered / non-PO receipt** · seen in: Oracle (unordered receipts), SAP (GR without reference) · priority:
  **common** · spine: impossible without changing SCM — `GoodsReceiptNote.purchase_order` is non-null PROTECT ·
  **defer, documented**
- **Blind receiving (expected quantities hidden from the receiver)** · seen in: Oracle, WMS players · priority:
  **differentiator** · **defer**

### Bullet 2 — Receipt Tolerances (configurable over/under thresholds that auto-flag)

- **Over-delivery % and under-delivery % per item/vendor, defaulted from a master** · seen in: SAP (purchasing
  value key on the material master, or the vendor info record, or the PO item), Oracle (receiving parameters +
  item/supplier overrides), Ariba (per purchasing unit) · priority: **table-stakes** · spine: **NEW TABLE
  `ReceiptTolerancePolicy`** · buildable now
- **Tolerance expressed as percentage OR absolute quantity OR value** · seen in: Ariba (all three), Oracle ·
  priority: **common** · spine: fields on the same policy · buildable now
- **"Unlimited over-delivery" escape flag** · seen in: SAP · priority: **common** · spine: boolean on the policy ·
  buildable now
- **Action on breach: none / warning / reject** · seen in: Oracle (explicit per-tolerance action), SAP (message
  control), Ariba · priority: **table-stakes** · spine: `action` choice on the policy; the console shows the
  verdict and the exceptions board lists breaches — **advisory in this pass** (hard-blocking would require
  changing `scm`'s own receive verb, which 6.12 must not do) · buildable now
- **Early / late receipt tolerance in days** · seen in: Oracle (days early/late receipt allowed + action), SAP
  (delivery window) · priority: **common** · spine: two integer fields on the policy, compared against
  `PurchaseOrderLine`'s promised/expected date · buildable now
- **Most-specific-wins resolution across item / category / vendor / catch-all** · seen in: SAP (material master →
  info record → PO item), Oracle (org → item → supplier) · priority: **table-stakes** · spine: mirror the proven
  in-repo resolver `resolve_qc_routing()` (`inventory/models/QualityControl/QcRoutingRules.py:89`) —
  item(3) > category(2) > catch-all(1), vendor pin adds a specificity point, then priority ASC, id ASC ·
  buildable now
- **Auto-flag quantities outside the band, with the breach visible as a badge** · seen in: SAP, Oracle, Ivalua
  ("instant discrepancy detection") · priority: **table-stakes** · spine: **new computed page** (tolerance
  exceptions board over `received_by_line()` vs the resolved policy) + one-click "raise discrepancy" ·
  buildable now
- **Invoice/price tolerance holds** · seen in: Coupa (tolerance hold), Precoro (tolerance limits on the 3-way
  match) · priority: **common** · spine: `GoodsReceiptNote.PRICE_TOLERANCE_PCT` is hardcoded at 2% — the policy
  can carry an advisory `price_variance_pct` column, but **changing what `recompute_match()` reads is an SCM
  write** → park the wiring for **6.13**
- **Delivery-completed / close-short indicator** · seen in: SAP (zeroes the open quantity, releases the
  commitment, still permits later receipts inside tolerance) · priority: **common** · **belongs to 6.10**
  (PO Cancellation & Close-out)

### Bullet 3 — Quality Inspection Checklists (pass/fail forms, sampling, failures → quarantine)

- **Rule decides whether a receipt inspects or goes straight to stock** (receipt routing) · seen in: Oracle
  (standard / inspection required / direct delivery, overridable at receipt), D365 (quality association per item /
  item group / all), NetSuite (item + vendor + location association), Odoo (QCP bound to the Receipt operation
  type) · priority: **table-stakes** · spine: **EXISTS →** `inventory.QcRoutingRule` + `resolve_qc_routing()`,
  page `inventory:qcroutingrule_list` · nothing to build
- **A checklist of checkpoints the operator ticks, mandatory vs advisory** · seen in: Odoo (Pass-Fail,
  Instructions), Procurify (pass/fail per line), NetSuite · priority: **table-stakes** · spine: **EXISTS →**
  `inventory.QcChecklist` / `QcChecklistItem` (`visual / functional / documentation / quantity / instruction`,
  `is_mandatory`, `sequence`), page `inventory:qcchecklist_list` · nothing to build
- **Measured characteristics with min/max/target and an automatic verdict** · seen in: SAP (inspection
  characteristics), D365 (test types with min/max/target + AQL), Odoo (Measure with norm + tolerance) · priority:
  **table-stakes** · spine: **EXISTS →** `scm.InspectionPlan` / `InspectionCharacteristic` +
  `scm.QualityInspection._evaluate()`, page `scm:qualityinspection_list` · nothing to build
- **Usage decision: accept / accept-with-deviation / reject, with a follow-up action** · seen in: SAP (usage
  decision), D365, NetSuite (disposition → VRA / rework order / adjustment) · priority: **table-stakes** ·
  spine: **EXISTS →** `scm.QualityInspection.usage_decision` + `action_taken`
  (`quarantined` / `ncr_raised` / `returned_to_vendor`) · nothing to build — but **`returned_to_vendor` currently
  leads nowhere**, which is exactly what 6.12's RTV document fixes
- **Certificate of Analysis from the result rows** · seen in: SAP, D365 · priority: **common** · spine:
  **EXISTS →** `scm:coa_report`
- **Sampling PLAN: fixed quantity / percentage / full license plate / skip-lot** · seen in: D365 (item sampling,
  *Per updated quantity* for partial receipts), NetSuite (skip-lot), Odoo (control frequency: all / randomly %/
  periodically), SAP (sampling procedure) · priority: **common** · spine: PARTIAL — `scm.QualityInspection` has a
  typed `sample_size` but there is **no sampling-plan rule** anywhere · **defer to Module 12 QMS / SCM 4.9** (it is
  a quality-engineering master, not a procurement one)
- **Photo as a check type** · seen in: Odoo ("Take a Picture") · priority: **differentiator** · spine: the
  evidence file on `ReceiptDiscrepancy` covers the procurement need · buildable now
- **Receipt cannot be validated until mandatory checks pass** · seen in: Odoo · priority: **common** · spine:
  would require changing `scm`'s `goodsreceipt_receive` guard · **defer, documented**

### Bullet 4 — Quarantine & Inspection Hold

- **Received goods held in a non-usable state, segregated in a QC zone** · seen in: SAP (quality-inspection
  stock; the lot is stock-relevant and only a usage decision releases it), D365 (full blocking of PO quantities
  during inspection), NetSuite (Quarantine workflow doing a bin transfer / inventory status change), Odoo
  (dedicated quarantine location) · priority: **table-stakes** · spine: **EXISTS →** `inventory.QuarantineOrder`
  `[QRD-]` with real `transfer` legs into the QC zone, page `inventory:quarantineorder_list`; plus
  `scm.LotSerial.status="quarantine"` · nothing to build
- **Release from quarantine back to usable stock, or scrap it** · seen in: SAP (release to unrestricted / block /
  scrap), NetSuite, D365 · priority: **table-stakes** · spine: **EXISTS →** `QuarantineOrder.release()` /
  `.scrap()` / `.cancel()` (compensating legs, row-locked) · nothing to build
- **The QC zone is resolved by the routing rule, not typed each time** · seen in: Oracle, Odoo · priority:
  **common** · spine: **EXISTS →** `QcRoutingRule.qc_location`
- **A typed link from the rejected receipt line to the hold that resulted** · seen in: SAP (inspection lot carries
  the GR reference), NetSuite, D365 (nonconformance records the PO/lot source) · priority: **common** ·
  spine: **GAP** — `QuarantineOrder.reference` is *free text* documented as e.g. `"GRN-00012"`. 6.12's
  `ReceiptDiscrepancy` supplies the typed GRN/line anchor and can carry a nullable `quarantine_order` FK ·
  buildable now
- **Printed quarantine / nonconformance tag** · seen in: D365 (nonconformance tag showing quarantine zone and
  usage restriction) · priority: **differentiator** · spine: `inventory.BarcodeLabel` is the nearest home ·
  **defer**

### Bullet 5 — Lot, Batch & Serial Capture (with expiry, for traceability/recall)

- **Lot / batch / serial + expiry recorded so stock is traceable** · seen in: SAP (batch at GR), Oracle (lot &
  serial, LPN), Fishbowl, NetSuite · priority: **table-stakes** · spine: **EXISTS →** `scm.LotSerial`
  (`kind`, `number`, `expiry_date`, `status`) with full CRUD at `scm:lotserial_list`; `scm.StockMove.lot_serial`
  carries it into the ledger · nothing to build for the master
- **Supplier's pre-arrival lot/serial/expiry/country-of-origin declaration** · seen in: Oracle iSupplier, GEP,
  SupplyOn · priority: **common** · spine: **EXISTS →** `AsnLine.lot_number` / `serial_number` / `expiry_date` /
  `country_of_origin` (free text, by 6.11's explicit design) · nothing to build
- **Shelf-life / expiry policy enforced at receipt** · seen in: SAP, NetSuite · priority: **common** · spine:
  **EXISTS →** `inventory.ShelfLifePolicy`, `inventory.LotNumberRule` · nothing to build
- **Typed capture ON the receipt line itself** · seen in: every leader · priority: **table-stakes in market** ·
  spine: **GAP** — `scm.GoodsReceiptLine` has no lot field and no item FK, and 6.12 must not add fields to an
  SCM-owned model. Two options: (a) a 4th table `ReceiptLotCapture`; (b) a **"mint declared lots" verb** on the
  receiving console that creates `scm.LotSerial` rows from the ASN's declared text once the SKU resolves to a
  `scm.Item` (the same `_resolve_grn_item` problem `_post_grn_receipt` already solves) · **recommend (b)** —
  see Deferred for why the table is not worth a model slot this pass

### Bullet 6 — Discrepancy Reporting (over/under/damaged, with photo + document evidence)

- **Log a discrepancy against the receipt with a typed reason** (over-shipment, short shipment, damaged, wrong
  item, quality failure, documentation missing, late) · seen in: Ariba (accepted vs rejected with a reason),
  Oracle (inspection reasons/comments), Procurify (pass/fail per line), D365 (nonconformance with a problem type),
  Ivalua (instant discrepancy detection) · priority: **table-stakes** · spine: **NEW TABLE `ReceiptDiscrepancy`**
  FK'ing `scm.GoodsReceiptNote` + `scm.GoodsReceiptLine` · buildable now
- **Photo and document evidence attached to the finding** · seen in: Odoo (photo check), Oracle (attachments and
  URLs on the inspection page), Procurify (packing-slip upload from web or phone camera), D365 (document
  attachment on the nonconformance) · priority: **table-stakes** · spine: `FileField` + external-URL fallback on
  the same table — the exact `inventory.DefectReport.photo` / `photo_url` pattern with an image/PDF allowlist and
  a size cap (`procurement.forms.CatalogManagement.UploadBatches.MAX_UPLOAD_BYTES` precedent) · buildable now
- **Choose the remedy when logging: replacement vs credit** · seen in: Ariba (rejecting *requires* saying whether
  the supplier replaces or credits, and captures a goods-return tracking number), NetSuite · priority:
  **table-stakes** · spine: `remedy` choice on the discrepancy, and the RTV is raised from it · buildable now
- **Notify the vendor / raise a supplier quality notification** · seen in: SAP Ariba SCC (quality notification
  visible to the supplier on the Network), SAP QM (supplier complaint notification), Ivalua · priority: **common**
  · spine: record `vendor_notified_on` + `vendor_reference` + notes; the actual outbound message is
  **integration/later** (there is no vendor login — L32) · data model now, transmission later
- **Escalate a receipt finding to the quality-engineering register** · seen in: D365 (nonconformance of type
  **Vendor**, sourced from the PO/receipt/lot), NetSuite · priority: **common** · spine: nullable
  `nonconformance` FK → `scm.NonConformance`, exactly the `inventory.DefectReport.ncr` precedent — **the NCR is
  raised in SCM, 6.12 only points at it** · buildable now
- **Discrepancies feed the supplier's quality/OTD score** · seen in: D365 (KPIs), Ivalua, SAP · priority:
  **differentiator** · spine: `scm.SupplierScorecard.recompute_from_signals` already reads GRN signals — a future
  signal source · **park for 6.16**
- **Auto-raise the discrepancy from a tolerance breach** · seen in: SAP, Oracle, Ivalua · priority:
  **table-stakes** · spine: the tolerance exceptions board's one-click action prefilling the form · buildable now

### Bullet 7 — Return to Vendor (RTV) Processing

- **An authorised vendor-return document with lines and a status lifecycle** · seen in: NetSuite (Vendor Return
  Authorization created from a failed inspection), Oracle (RTV transaction, now with a WMS integration in 25D),
  SAP (return delivery / returns PO), Fishbowl (vendor return reconciliation) · priority: **table-stakes** ·
  spine: **NEW TABLE `ReturnToVendor` + `ReturnToVendorLine`** — nothing in the repo is a vendor return
  (`scm.ReturnAuthorization` is the CUSTOMER RMA; `scm.WarrantyClaim` is a post-sale failure claim) · buildable now
- **Supplier's RMA / return authorisation number recorded** · seen in: NetSuite, Ariba ("goods return tracking
  number"), SAP · priority: **table-stakes** · spine: `supplier_rma_number` field — mirror
  `scm.WarrantyClaim.supplier_rma_number`, including its advisory duplicate badge idea · buildable now
- **Remedy expectation: credit / replacement / repair** · seen in: Ariba, NetSuite (disposition drives which
  downstream document is created), D365 · priority: **table-stakes** · spine: `remedy` choice on the header ·
  buildable now
- **Return shipment tracking (carrier, tracking number, shipped date)** · seen in: Oracle (RTV shipping documents
  printed), Fishbowl · priority: **common** · spine: free-text carrier/tracking on the header this pass — a real
  `scm.Shipment(direction="outbound")` link is a later refinement (SCM 4.6 owns freight, L36) · buildable now
- **Expected credit value derived from the returned lines** · seen in: all · priority: **common** · spine:
  quantity × the PO line's `unit_price`, derived at read time — **never stored twice** · buildable now
- **Debit memo / vendor credit note posted to AP** · seen in: SAP, Oracle, NetSuite, Coupa · priority:
  **table-stakes in market** · spine: **DEFER, documented.** `apps/accounting` owns the ledger (L29) and
  `accounting.Bill` has no `kind` for a vendor credit — `scm.WarrantyClaim`'s docstring already raises this as a
  **flag to Modules 2/6**. This pass records a free-text `credit_note_ref` and posts nothing
- **Stock removed when the return ships** · seen in: SAP (return delivery movement), Oracle WMS (RTV posts the
  inventory adjustment), NetSuite · priority: **table-stakes in market** · spine: **DELIBERATE NON-POSTING, and
  it is defensible from verified code**: `_post_grn_receipt` posts **only `quantity_received`**, so a quantity
  *rejected at the dock* never entered the ledger and has nothing to remove; stock that failed QC *after*
  acceptance is removed by `inventory.QuarantineOrder.scrap()` or a `scm:stockadjustment`. This is the same
  posture `scm.NonConformance` and `scm.ReturnDisposition` already take for `return_to_vendor` ("posts nothing —
  our stock never re-entered"). **6.12's RTV is the authorisation + tracking document, not a second ledger
  writer.** Document the rule on the model and on the page

### Bullet 8 — Item Tagging & Barcoding (internal barcodes/QR, handheld scan to bin)

- **Generate internal labels/barcodes for received goods** · seen in: Fishbowl, Epicor Kinetic (license plates),
  Oracle (LPN) · priority: **table-stakes** · spine: **EXISTS →** `inventory.BarcodeLabel` `[LBL-]`, page
  `inventory:barcodelabel_list` · nothing to build
- **Handheld / mobile scanning console** · seen in: Fishbowl, Epicor, Ivalua (mobile receipts + barcode) ·
  priority: **table-stakes** · spine: **EXISTS →** `inventory:scan_console` + `ScanSession`/`ScanEvent`; the
  scanner resolves against `scm.Item.sku` / `Location.code` / `LotSerial.number` · nothing to build
- **Directed putaway to a suggested bin** · seen in: Epicor (velocity/size-driven suggestions), Fishbowl (aisle /
  shelf / bin), Oracle · priority: **table-stakes** · spine: **EXISTS →** `inventory.PutawayRule` +
  `inventory:putaway_suggestions` + `scm:putawaytask_list` · nothing to build
- **RFID** · priority: **differentiator** · spine: **EXISTS →** `inventory:rfidtag_list`
- **Verdict: the whole bullet is a MAP, not a build.** A native mobile/handheld app is integration/later

### Bullet 9 — Inventory Posting (stock updates on acceptance; feeds three-way match)

- **On-hand rises when the receipt is booked, at the PO's agreed price as the cost layer** · seen in: all ·
  priority: **table-stakes** · spine: **EXISTS →** `_post_grn_receipt` posting `move_type="receipt"` StockMoves,
  guarded by a row lock, with unmatched-SKU lines surfaced as warnings · nothing to build
- **Three-way match PO ↔ GRN ↔ Bill with a price tolerance** · seen in: Coupa, Precoro, Procurify, Ivalua, all
  suites · priority: **table-stakes** · spine: **EXISTS →** `recompute_match()` + `match_status` badges +
  `scm:goodsreceipt_rematch` · nothing to build
- **Four-way match adding the inspection verdict** · seen in: Ivalua (explicitly), regulated-industry suites ·
  priority: **differentiator** · spine: once `ReceiptDiscrepancy` and the QC verdict exist, the console can show
  the fourth column — but **editing `recompute_match()` is an SCM write** · park the wiring for **6.13**
- **GR/IR accrual journal at receipt** · seen in: SAP, Oracle, NetSuite, D365 · priority: **table-stakes in
  market** · spine: **DEFER, documented** — `apps/accounting` owns `JournalEntry` (L29); procurement posts no
  journals anywhere and must not start here
- **Landed cost apportioned onto the receipt** · seen in: Fishbowl, NetSuite, Oracle · priority: **common** ·
  spine: **EXISTS →** `scm.LandedCostVoucher` / `LandedCostCharge` / `LandedCostAllocation`

### Bullet 10 — Receipt Reversal & Audit Trail

- **Cancel / reverse a posted receipt without deleting history** · seen in: Ariba (enter negative values against
  an approved receipt), Procurify (unreceive / edit via Receive Logs), Coupa (correction transactions), SAP
  (reversal movement) · priority: **table-stakes** · spine: **EXISTS →** `goodsreceipt_cancel` +
  `_reverse_grn_receipt` (compensating moves; refuses if already put away) · nothing to build
- **Timestamped who/what/when trail on every receipt action** · seen in: all; Procurify markets the audit log
  explicitly · priority: **table-stakes** · spine: **EXISTS →** `core.AuditLog` written by `write_audit_log` on
  receive / cancel / rematch, and `"goodsreceiptnote"` is already whitelisted in `PROCUREMENT_CONTENT_MODELS` ·
  nothing to build for the data
- **One page that shows a receipt's full history — booking, reversal reason, discrepancies, RTVs** · seen in:
  Procurify (Receive Logs), Oracle (receipt transaction history), SAP (document flow) · priority: **common** ·
  spine: **new computed page** over `procurement_activity_qs()` narrowed to `goodsreceiptnote` + this
  sub-module's own rows · buildable now

### Beyond the bullets (strong features the bullets do not name)

- **Receipt routing override at receipt time** (Oracle: change the destination for a specific supplier/item/order
  when the user profile allows it) · priority: **common** · spine: `resolve_qc_routing()` returns the rule and a
  human-readable reason — the console can show it and let the operator override per receipt · buildable now
- **ASN-vs-actual reconciliation** ("declared 100, arrived 92") · seen in: Oracle, SupplyOn, NetSuite ·
  priority: **common** · spine: `AsnLine.variance` / `shortfall` already exist as derived properties — the
  console shows declared vs outstanding vs received in one row · buildable now
- **Cross-dock straight from receiving** · seen in: Oracle, WMS players · priority: **differentiator** · spine:
  **EXISTS →** `inventory.CrossDockOrder`
- **Supplier files the inspection result / responds to the notification** · seen in: SAP Ariba SCC · priority:
  **differentiator** · **integration/later** — there is no vendor login (L32); `VendorPortalAccess` (6.4) is the
  future home
- **OCR of the delivery note / packing slip** · seen in: goods-receipt-automation vendors, Precoro, Coupa ·
  priority: **common** · **belongs to 6.13** (Invoice Capture OCR) · park

---

## Recommended build scope (this pass — 3 models + 1 child, plus 3 computed pages)

Three tables is the right number: six of the ten bullets already have live pages, and the two genuinely missing
documents (a tolerance policy and a vendor-return authorisation) plus the missing evidence record are exactly what
the market survey says a receiving desk cannot do without.

### 1. `ReceiptTolerancePolicy` — no number prefix (rule master)
`models/GoodsReceiptInspection/ReceiptTolerances.py` · `TenantOwned`
(the `ApprovalRoutingRule` / `EscalationPolicy` / `QcRoutingRule` precedent: rule masters carry no `[XXX-]`)

- **Justified by:** SAP under/over-delivery tolerance + unlimited-overdelivery flag; Oracle receiving parameters
  (over-receipt tolerance, days early/late receipt allowed, and an **action** per tolerance); Ariba tolerances by
  quantity/percentage/value set globally or per purchasing unit; Ivalua/Precoro tolerance limits.
- **Fields:** `name`; scope `item` → **`scm.Item`** (null), `category` → **`scm.ItemCategory`** (null), `vendor` →
  **`core.Party`** (null); `over_receipt_pct`, `under_receipt_pct`, `over_receipt_qty` (absolute alternative),
  `allow_unlimited_over_receipt` (bool), `early_receipt_days`, `late_receipt_days`,
  `action` = `none | warn | block_flag` (advisory this pass — see below), `price_variance_pct` (advisory mirror of
  the hardcoded 2%), `priority`, `is_active`, `notes`.
- **Module-level resolver** `resolve_receipt_tolerance(item=None, sku_hint="", vendor=None, *, rules=None)`
  returning `(rule, verdict, reason)` — a direct structural copy of
  `apps/inventory/models/QualityControl/QcRoutingRules.py:89` (item 3 > category 2 > catch-all 1; a vendor-pinned
  rule never fires for an unknown supplier; then `priority` ASC, `id` ASC; every refusal starts
  `"No Rule Matched"`). Overlapping rules are legal — no `unique_together`.
- **Verified FKs:** `core.Tenant`, `scm.Item`, `scm.ItemCategory`, `core.Party`.
- **Ownership guard to write into the docstring:** the policy is **advisory**. It never blocks
  `scm:goodsreceipt_receive` — SCM owns that verb (L36). It colours the console, drives the exceptions board and
  pre-fills a discrepancy.

### 2. `ReceiptDiscrepancy` `[RDS-]`
`models/GoodsReceiptInspection/ReceiptDiscrepancies.py` · `TenantNumbered`

- **Justified by:** Ariba's accepted-vs-rejected with a mandatory replace-or-credit answer and a goods-return
  tracking number; Oracle's inspection reasons/comments/attachments; Procurify's per-line pass/fail with
  packing-slip upload; Odoo's photo check and quality alert; D365's **Vendor**-type nonconformance sourced from
  the PO/receipt/lot; Ivalua's instant discrepancy detection.
- **Fields:** `goods_receipt` → **`scm.GoodsReceiptNote`** (PROTECT); `goods_receipt_line` →
  **`scm.GoodsReceiptLine`** (PROTECT, nullable — a header-level discrepancy is legal);
  `kind` = `over_shipment | short_shipment | damaged | wrong_item | quality_failure | documentation | late_delivery`;
  `severity` = `minor | major | critical`; `quantity_affected`; free-text `item_description` / `sku_hint` mirror
  (the `AsnLine` rule — there is no item FK on a GRN line); `lot_number` / `serial_number` / `expiry_date`
  free text (partially serves bullet 5 without a new table); `description`;
  `evidence` `FileField(upload_to="procurement/receipt_evidence/%Y/%m/")` + `evidence_url`
  (image/PDF allowlist + size cap, the `DefectReport` + `CatalogUploadBatch` precedent);
  `remedy` = `pending | replacement | credit | rtv | accept_as_is | scrap`;
  `status` = `open | vendor_notified | resolved | cancelled` (`editable=False`, moved by verbs only);
  `vendor_notified_on`, `vendor_reference`, `resolved_at`, `resolved_by`, `resolution_notes`;
  `nonconformance` → **`scm.NonConformance`** (SET_NULL, nullable — escalation *pointer*, the NCR is still raised
  in SCM); `quarantine_order` → **`inventory.QuarantineOrder`** (SET_NULL, nullable — the typed link the free-text
  `reference` cannot give); `return_to_vendor` → the RTV below (SET_NULL, nullable).
- **Derived, never stored:** the tolerance verdict for this line (resolve the policy, compare
  `received_by_line()[po_line_id]` against `po_line.quantity`).
- **Verified FKs:** `core.Tenant`, `scm.GoodsReceiptNote`, `scm.GoodsReceiptLine`, `scm.NonConformance`,
  `inventory.QuarantineOrder`, `core.Party` (vendor is reachable via the GRN's PO, so do **not** duplicate it as a
  stored column — derive it), `settings.AUTH_USER_MODEL`.
- **Posts nothing to the ledger or to stock.**

### 3. `ReturnToVendor` `[RTV-]` + `ReturnToVendorLine`
`models/GoodsReceiptInspection/ReturnsToVendor.py` · `TenantNumbered` + a tenant-less child scoped through its
parent (the `AsnLine` / `PurchaseOrderChangeLine` precedent)

- **Justified by:** NetSuite's Vendor Return Authorization created from a failed inspection (and the Enhanced
  Receipt RA workflow that generates returns for the specific failing lots/serials); Oracle's RTV transaction with
  printed shipping documents and the 25D WMS return integration; SAP's return delivery and supplier complaint;
  Ariba's replace-or-credit decision with a goods-return tracking number; Fishbowl's vendor return reconciliation.
- **Header fields:** `vendor` → **`core.Party`** (PROTECT — the supplier role, never a second vendor master);
  `purchase_order` → **`scm.PurchaseOrder`** (SET_NULL, nullable); `goods_receipt` →
  **`scm.GoodsReceiptNote`** (SET_NULL, nullable); `discrepancy` → `ReceiptDiscrepancy` (SET_NULL, nullable — the
  usual origin); `reason` = `damaged | defective | wrong_item | over_shipment | expired | not_to_spec | other`;
  `remedy` = `credit | replacement | repair | none`; `status` =
  `draft → authorized → shipped → closed`, with `cancelled` from anything not shipped (`editable=False`, verb
  methods that re-check their own guard inside themselves — the 6.9 C1 / 6.11 lesson);
  `supplier_rma_number` (+ advisory duplicate badge, the `WarrantyClaim` pattern); `carrier_name`,
  `tracking_number`, `shipped_on`, `expected_return_date`; `credit_note_ref` (**free text, no ledger write**);
  `authorized_by` / `authorized_at`, `cancelled_at` / `cancellation_reason`, `notes`.
- **Line fields:** `return_to_vendor` (CASCADE); `goods_receipt_line` → **`scm.GoodsReceiptLine`** (PROTECT,
  nullable); `po_line` → **`scm.PurchaseOrderLine`** (PROTECT, nullable — sizes the credit via its `unit_price`);
  free-text `item_description` / `sku_hint` / `uom_hint` auto-copied from the source line on save (the `AsnLine`
  rule); `quantity_returned`; `lot_number` / `serial_number` free text; `condition_note`.
- **Derived:** `expected_credit_value` = Σ `quantity_returned × po_line.unit_price`, computed at read time.
- **Explicit non-posting rule (write it in the docstring and show it on the page):** an RTV posts **no
  StockMove and no JournalEntry**. Rejected-at-dock quantities never entered the ledger
  (`_post_grn_receipt` posts only `quantity_received` — verified), and accepted stock that later fails QC is
  removed by `inventory.QuarantineOrder.scrap()` or a `scm:stockadjustment`. Same posture as
  `scm.NonConformance`'s `return_to_vendor` disposition. The vendor credit stays with `accounting` (L29) and is
  blocked on the `Bill.kind` gap `scm.WarrantyClaim` already flagged to Modules 2/6.
- **Verified FKs:** `core.Tenant`, `core.Party`, `scm.PurchaseOrder`, `scm.PurchaseOrderLine`,
  `scm.GoodsReceiptNote`, `scm.GoodsReceiptLine`, `settings.AUTH_USER_MODEL`.

### Computed pages (no new tables) — these carry three of the ten bullets

- **`procurement:receiving_console`** — the ASN→GRN booking desk. Lists confirmed/in-transit ASNs with no receipt
  yet; opening one shows each `AsnLine` with declared vs outstanding vs already-received, the resolved tolerance
  verdict, and the resolved `QcRoutingRule` verdict + reason; the action drafts a `scm.GoodsReceiptNote` +
  `GoodsReceiptLine` rows and copies `supplier_reference → delivery_note_ref`. (Booking the receipt still happens
  on SCM's own `scm:goodsreceipt_receive` — one writer for the stock effect.) Optional second verb: **mint the
  declared lots** into `scm.LotSerial` when the SKU resolves to a `scm.Item`.
- **`procurement:tolerance_exceptions`** — every non-cancelled receipt line whose received quantity or receipt
  date breaches the resolved policy, bucketed over / short / early / late, each row with a one-click "raise
  discrepancy" that pre-fills the form. Filter the ORM before pagination (the 6.11 backorder-risk lesson).
- **`procurement:receipt_audit`** — a receipt-scoped trail over `procurement_activity_qs()` narrowed to
  `goodsreceiptnote` plus this sub-module's rows, showing booking, reversal, re-match, discrepancies and RTVs on
  one page.

### Proposed `LIVE_LINKS["6.12"]` — all ten bullets, six of them pointing at pages that already exist

```
"Goods Receipt Note (GRN) Creation": "procurement:receiving_console",
"Receipt Tolerances":                "procurement:tolerancepolicy_list",
"Quality Inspection Checklists":     "inventory:qcchecklist_list",          # 5.15 owns the checklist master
"Quarantine & Inspection Hold":      "inventory:quarantineorder_list",      # 5.15 QRD- with real stock legs
"Lot, Batch & Serial Capture":       "scm:lotserial_list",                  # 4.3 owns the traceability master
"Discrepancy Reporting":             "procurement:discrepancy_list",
"Return to Vendor (RTV) Processing": "procurement:rtv_list",
"Item Tagging & Barcoding":          "inventory:barcodelabel_list",         # 5.14 labels + scan console
"Inventory Posting":                 "scm:goodsreceipt_list?status=received",  # 4.1 receive posts the StockMove
"Receipt Reversal & Audit Trail":    "procurement:receipt_audit",
```
(Verify each SCM/inventory url name resolves at wire-up time; `scm:goodsreceipt_list`, `scm:lotserial_list`,
`inventory:qcchecklist_list`, `inventory:quarantineorder_list` and `inventory:barcodelabel_list` are all already
referenced by existing `LIVE_LINKS` entries, so they exist today. Confirm `scm:goodsreceipt_list` actually honours
a `?status=` filter before shipping that query string — otherwise point the bullet at the plain list.)

---

## Belongs to sibling sub-modules (parked, not scoped here)

- Delivery-completed / close-short indicator on the PO; closing a short-received order → **6.10** (PO
  Cancellation & Close-out; `procurement:poc_list` / `scm:purchaseorder_list`)
- Invoice price-tolerance holds, wiring `ReceiptTolerancePolicy.price_variance_pct` into `recompute_match()`, the
  four-way match column, invoice dispute workflow → **6.13** (Invoice & Voucher Management)
- Delivery-note / packing-slip OCR → **6.13** (Invoice Capture OCR)
- Discrepancy and rejection rates as supplier KPIs and scorecards → **6.16** (Supplier Performance &
  Evaluation; `scm.SupplierScorecard` already derives GRN signals)
- Supplier self-service filing of inspection results or of the ASN → **6.4** (`VendorPortalAccess`) — and it stays
  behind a login, so a staff sidebar bullet must never point at it (L32)
- On-hand visibility, bin/aisle mapping, cycle counts, goods issue/return to stock → **6.18** (Inventory &
  Warehouse Integration)
- Evidence/document repository, versioning and full-text search over receipt paperwork → **6.19**
- The sampling-plan master (fixed / percentage / skip-lot / AQL) and any new inspection execution record →
  **SCM 4.9 / future Module 12 QMS**, never a third quality register in procurement

---

## Deferred (later passes / integrations)

- **`ReceiptLotCapture` as its own table** — the bullet is partly served by `scm:lotserial_list` (master + CRUD +
  expiry), by `AsnLine`'s declared lot/serial/expiry/country-of-origin text, and by the lot fields on
  `ReceiptDiscrepancy` / `ReturnToVendorLine`. A dedicated capture table would need its own item resolution (GRN
  lines are free text) and would spend a model slot that the tolerance policy and the RTV need more. Ship the
  "mint declared lots" verb on the console instead; revisit when `scm.GoodsReceiptLine` gains an item FK.
- **Hard-blocking a receipt that breaches tolerance or has open mandatory checks** — `goodsreceipt_receive` is
  SCM's verb (L36). 6.12 flags and reports; a real block is an SCM change to negotiate later.
- **GR/IR accrual journal on receipt, and the vendor debit memo / credit note** — `apps/accounting` owns the
  ledger (L29) and `accounting.Bill` has no `kind` for a vendor credit. `scm.WarrantyClaim` already raised this as
  a flag to Modules 2/6; 6.12 records `credit_note_ref` and posts nothing.
- **Stock removal on RTV** — deliberate, see the ownership rule above. Physical removal stays with
  `inventory.QuarantineOrder.scrap()` / `scm:stockadjustment`.
- **Unordered / non-PO receipts** — `GoodsReceiptNote.purchase_order` is a non-null PROTECT FK; supporting them
  means changing an SCM model.
- **Auto-receipt on thresholds / due date / invoice reconciliation** (Ariba, Procurify) — needs a scheduler.
- **Blind receiving, quarantine/NCR tag printing, license-plate (LPN) receiving** — WMS-grade features whose
  nearest homes are `inventory.BarcodeLabel` and SCM 4.4.
- **EDI 861 receiving advice, carrier APIs, supplier quality notifications, native handheld app** —
  integration/later; the provenance columns for them already exist (`AdvancedShipmentNotice.source` includes
  `edi`).
- **Discrepancy → supplier scorecard signal, four-way match** — both are cheap once these tables exist, but each
  writes into another module's computation; sequence them with 6.13/6.16.

# Research — Sub-module 4.9: Quality Management System (QMS) (Module 4 — Supply Chain Management, `scm`)

The five `NavERP.md` bullets for `### 4.9` (verbatim — these strings are the LIVE_LINKS keys):

- **Quality Inspection** — Definition of inspection criteria for incoming and outgoing goods.
- **Non-Conformance Reports (NCR)** — Documentation of products failing quality checks.
- **Corrective and Preventive Action (CAPA)** — Management of workflows to address root causes of defects.
- **Audit Management** — Scheduling and execution of internal and external audits.
- **Certificate of Analysis (CoA)** — Generation of compliance certificates for shipped batches.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`apps/core/navigation.py` carries `"4.1" … "4.8"`. **4.9 is the next unbuilt sub-module** (no `LIVE_LINKS["4.9"]`
key). 4.10–4.19 are out of scope for this pass.

### Ownership call — 4.9 owns the QMS transaction tables; Module 12 EXTENDS them (L36/L29/L37)

**`## 12. Quality Management System (QMS)` in `NavERP.md` (lines 1818–1956) is a second, much larger QMS**
(20 sub-modules: document control, design controls, ISO 14971 risk, CAPA, NC/deviation, supplier quality, IQC,
IPQC, FQC/OQC, calibration/MSA, audit, training, complaints, management review, validation, EHS, regulatory,
traceability, LIMS, 21 CFR Part 11). **Module 12 is not built** (no `apps/quality` app exists).

Per the ships-first precedent already applied three times in this app — **L36** (SCM 4.1 took
`PurchaseRequisition`/`RFQ`/`PurchaseOrder`/`GoodsReceiptNote` that the ERD had assigned to Module 6) and
**L37** (SCM 4.3 took the whole inventory spine that the ERD had assigned to Module 5) — **SCM 4.9 OWNS the QMS
transaction tables it builds** (`InspectionPlan`, `QualityInspection`, `NonConformance`, `CapaAction`, and later
`QualityAudit`), in `apps/scm`. **Module 12 will FK into `scm.*` by string and EXTEND** (document-controlled
SOPs, ISO 14971 risk files, design controls, LIMS samples, calibration, e-signatures, training linkage) — it must
**not** re-declare a parallel `quality.NonConformance` / `quality.CapaAction` / `quality.Inspection`. The ERD rows
for BOTH modules must be reconciled in the same pass that ships 4.9 (L36 step 2 — this is a required close-out
item, not a note). Model names deliberately match Module 12's planned names (`NonConformance` [NCR-],
`CapaAction` [CAPA-], `QualityAudit` [QA-]) so the extension is obvious; the ERD's Module-12 `Inspection` **is**
`scm.QualityInspection` [QC-].

### Spine entities verified to exist (grep, not the ERD — L28)

`grep -rn "^class " apps/scm/models/ apps/core/models/`:

| Entity | File | What 4.9 uses it for |
|---|---|---|
| `Item` | `models/InventoryManagement/Items.py:56` | what is inspected; `tracking ∈ none/lot/serial`, `uom` FK, `average_cost` |
| `UOM` | `…/Items.py:34` | unit on a measured inspection characteristic |
| `ItemCategory` | `…/Items.py:17` | plan scope "all items in this category" |
| `LotSerial` | `…/LotSerials.py:5` | **`status ∈ available/quarantine/expired/consumed` already exists** — 4.9 USES `quarantine`, it does not add a hold table |
| `Location` | `…/Locations.py:10` | where the inspected stock sits; `location_type ∈ warehouse/zone/bin/staging/transit` |
| `StockMove` | `…/StockMoves.py:13` | append-only signed ledger; `MOVE_TYPES = receipt/issue/transfer/adjustment/consumption/production`, has `reference` + `reason` |
| `GoodsReceiptNote` / `GoodsReceiptLine` | `models/ProcurementManagement/GoodsReceiptNotes.py:15,166` | **incoming** inspection hook; line already has `quantity_received` / `quantity_rejected` / `rejection_reason` |
| `PurchaseOrder` / `PurchaseOrderLine` | `…/PurchaseOrders.py:15,172` | supplier + agreed price behind an incoming inspection |
| `Shipment` | `models/TransportationManagement/Shipments.py:18` | **outgoing** / CoA hook (`direction`, `sales_order`, `status`) |
| `SalesOrder` | `models/OrderManagement/SalesOrders.py:20` | customer behind an outgoing CoA |
| `WorkOrder` | `models/Manufacturing/WorkOrders.py:26` | **in-process** inspection hook; has `quantity_produced`/`quantity_scrapped`, `output_lot_serial` |
| `SupplierProfile`, `SupplierScorecard`, `SupplierRiskAssessment` | `models/SupplierRelationshipManagement/…` | 4.2 already scores supplier quality from GRN accept/reject — do NOT rebuild |
| `core.Party`, `core.PartyRole` | `apps/core/models/Party.py:5`, `PartyRole.py:5` | inspector / auditor / NCR owner = Party with `employee` role; supplier = `supplier`/`vendor` role |
| `core.Document` | `apps/core/models/Document.py:5` | **generic FK attachment** (`content_type`/`object_id`) — inspection photos, supplier CoA PDFs, audit evidence. Already FK'd from `SupplierContract.document` |
| `core.OrgUnit`, `core.Activity`, `core.AuditLog` | `apps/core/models/…` | auditee org unit; activity log |
| `_employee_parties()` / `_supplier_parties()` / `_customer_parties()` | `apps/scm/forms/_common.py:33,45,69` | the dropdown scoping helpers to reuse |
| `_post_stock_move(...)` | `apps/scm/views/_helpers.py:95` | the ONLY way to touch the ledger; takes `move_type`, `reference`, `reason` |
| `next_number(model, tenant, prefix, field="number")` | `apps/core/utils.py:33` | supports a **second** numbered field (used below for the CoA number) |

**Verified NOT to exist:** no `apps/quality` app; no `Inspection*`, `NonConformance`, `Capa*`, `Audit*` (other than
`core.AuditLog`, which is the security trail, not a quality audit), no `Certificate*` class anywhere in
`apps/scm`, `apps/core`, `apps/accounting`. Nothing to reuse — 4.9 builds this domain from zero.

### Constraints carried in from earlier passes
- **No JournalEntry from SCM (L29).** Cost-of-poor-quality is a captured/derived figure on the NCR and a report
  roll-up; it never posts to `accounting.*`. (The 4.6 precedent for a real financial hand-off is a **draft**
  `accounting.Bill`, and nothing in 4.9 needs even that.)
- **Compute-then-convert.** An inspection *evaluates* results against the plan's limits and *proposes* an NCR;
  a human presses "Raise NCR", "Quarantine lot", "Scrap". Oracle auto-creates the nonconformance — NavERP must not.
- **Parties, never new person/company tables (L29).**
- **On-hand is always `Sum(StockMove.quantity)`** — quarantine is a `LotSerial.status` flag, not a quantity move.
- Sibling research that parked work here: `research-scm-4.4.md` (quality gate at receiving → "4.9/Module 12"),
  `research-scm-4.8.md` lines 456–459 + 633–637 ("in-process quality checks, control points, NC on a production
  run, CoA for a produced lot → **4.9 QMS**; 4.8 leaves the seam"), `research-scm-4.2.md` lines 150, 305–307
  (full CAPA off a bad scorecard → 4.9; 4.2 only has a `flagged_for_review` flag).

---

## Leaders surveyed (with source links)

EQMS suites and ERP/MES-native quality modules are genuinely different product categories here, so the survey
spans both (plus the CoA/process-QC specialists, which is where bullet 5 actually lives).

**ERP / MES-native quality modules** (closest shape to NavERP 4.9)
1. **Odoo Quality** — control points that auto-generate checks on receipts, manufacturing and deliveries; alerts
   carry root cause + corrective/preventive actions —
   [app page](https://www.odoo.com/app/quality) ·
   [control points doc](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/quality/quality_management/quality_control_points.html) ·
   [quality alerts doc](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/quality/quality_management/quality_alerts.html)
2. **NetSuite Quality Management** — quality *specifications* trigger an *inspection queue* record with a pass/fail
   state machine and a quarantine / return-to-vendor action; CoA generated at fulfillment —
   [inspection queue doc](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158627331439.html) ·
   [COA doc](https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_163274330949.html)
3. **Oracle Fusion Cloud Quality Management** — inspection plans with characteristics + specification limits,
   %/fixed-count/AQL sampling, automatic accept/reject disposition, auto-created nonconformance —
   [overview](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/24c/fauqm/overview-of-quality-management.html) ·
   [Using Quality Management (PDF)](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25d/fauqm/using-quality-management.pdf)
4. **SAP QM (S/4HANA)** — inspection plan → inspection lot → results/defects recording → **usage decision**
   (accept/reject/rework) → quality certificate; lots triggered by GR from vendor, in-process, pre-shipment and
   periodic stock/batch inspection —
   [SAP QM quick guide](https://www.tutorialspoint.com/sap_qm/sap_qm_quick_guide.htm) ·
   [final inspection type 04](https://www.guru99.com/final-inspection-production-sap-qm.html)
5. **Siemens Opcenter X Quality** (ex-IBS QMS) — inspection criteria derived from design data, incoming-goods
   inspection, inspection types mapped to production stages, operator-facing SPC charts, nonconforming-product
   event records — [product page](https://www.siemens.com/en-us/products/opcenter/quality-x-cloud-qms/)

**Process-QC / CoA specialists**
6. **AlisQI** — specification sets with internal *and* external limits (asymmetric, partially filled), automated
   spec checking that flags deviations, supplier-CoA data extraction at goods-in, batch release/blocking, and
   CoA templates per product / per customer / per product+customer with a results table carrying limit, unit and
   test method —
   [incoming goods inspection](https://www.alisqi.com/en/modules/supplier-quality/incoming-goods-inspection) ·
   [CoA help](https://help.alisqi.com/certificate-of-analysis) · [specifications help](https://help.alisqi.com/specifications)

**EQMS suites** (the CAPA/NCR/audit reference implementations)
7. **MasterControl** — quality events (deviations, nonconformance, OOS), CAPA, audits, risk, change control, with
   rules-based routing and training launched from a CAPA or change —
   [quality suite](https://www.mastercontrol.com/quality/)
8. **QT9 QMS** — the most concretely documented SMB feature set: NC logging with quarantine, use-as-is / rework /
   scrap / return-to-vendor dispositions, assigned approvers, **dollar cost of poor quality**, overdue alerts; CAPA
   auto-created from inspections/audits/complaints with integrated RCA + 8D, unlimited tasks, priority by due
   date, and **verification of effectiveness after final approval** —
   [nonconforming product](https://qt9software.com/qms/nonconforming-product-software) ·
   [CAPA](https://qt9software.com/qms/capa-software) · [modules](https://qt9software.com/qms/modules)
9. **Intelex** — NCR capture with photos, product ID, defect codes and disposition; a creation → triage →
   verification → resolution workflow; severity-driven escalation into RCA / 8D / CAPA; audit scheduler with
   frequency + risk level, ISO checklists, findings with severity and evidence, corrective-action plans —
   [nonconformance reporting](https://www.intelex.com/products/applications/nonconformance-report-software/) ·
   [audit management](https://www.intelex.com/products/applications/audit-management)
10. **Veeva Vault QMS** — deviations, CAPA, complaints, audits, supplier quality, quality risk, external-partner
    collaboration on investigations and audit findings — [product page](https://www.veeva.com/products/vault-qms/)
11. **Sparta Systems TrackWise Digital (Honeywell)** — audit management that generates CAPA plans from findings,
    nonconformance, **stand-alone CAPA** as an explicit concept, supplier quality, recall management —
    [TrackWise](https://www.spartasystems.com/trackwise/) ·
    [process overview series](https://www.spartasystems.com/resources/trackwise-digital-success-series/)
12. **Qualio** — combined "CAPA & NCR" module plus audits, suppliers, training, design controls and quality
    analytics for the SMB life-sciences end — [product page](https://www.qualio.com/product)
13. **ETQ Reliance (Hexagon)** — document control, audit management, CAPA, nonconformance, supply-chain quality,
    and a dedicated **Inspection Management** app whose selling point is auto-linking inspections to quality
    events and NCRs — [product group](https://hexagon.com/products/product-groups/etq-reliance) ·
    [inspection management launch](https://seekingalpha.com/pr/19808809-etq-expands-the-capabilities-of-etq-reliance-qms-launches-inspection-management-application)
    *(both 403'd on direct fetch; features taken from the vendor/press summaries returned by search — treated as
    corroborating, not primary, evidence)*

**Supporting reference for disposition practice (not a product):** Material Review Board convention —
cross-functional board, dispositions **use-as-is (with a written concession) / rework (re-inspection required) /
scrap (destroyed and documented) / return-to-vendor** —
[eLeaP MRB glossary](https://quality.eleapsoftware.com/glossary/material-review-board-mrb-in-quality-management-systems-meaning-process-and-role-in-controlled-nonconformance-decisions/) ·
[QT9 MRB glossary](https://qt9software.com/glossary/material-review-board-mrb). CoA-at-shipment ERP practice
(one CoA per lot on the shipping document, formats per item/customer) — [E21](https://www.e21erp.com/web-erp-system/erp-inventory-management-software/coa-software/),
[Deacom](https://www.ecisolutions.com/products/deacom-erp-software/certificate-of-analysis-software/).

---

## Feature catalog (this sub-module only)

### Bullet 1 — Quality Inspection ("definition of inspection criteria for incoming and outgoing goods")

**The criteria master (the "definition" half)**

- **Reusable inspection plan / specification keyed to what triggers it** — one record says *which* items and
  *which* event (goods receipt, work-order completion, fulfillment/shipment, periodic stock check) produce an
  inspection. · seen in: SAP (inspection plan per material + inspection type 01/03/04/…), NetSuite (Quality
  Specification: transaction type = item receipt / WO completion / item fulfillment, plus item, vendor, location
  scope), Oracle (inspection plan by plan type), Odoo (control point: products/product categories × operations),
  AlisQI (control plans in the form builder), Siemens ("define inspection criteria from design data") ·
  priority: **table-stakes** · spine: **new table `InspectionPlan`**, scoped by FKs to the verified
  `scm.Item` / `scm.ItemCategory` and a supplier `core.Party` · buildable now
- **Inspection characteristics with a target and upper/lower specification limits + unit + test method** — the
  actual criteria rows. · seen in: Oracle (characteristics specify the range of acceptable values / spec limits),
  SAP (master inspection characteristics), Odoo (a *Measure* check with a tolerance min/max), AlisQI (spec limits,
  unit and test method shown per result) · priority: **table-stakes** · spine: **new child table
  `InspectionCharacteristic`**, `uom` FK to verified `scm.UOM` · buildable now
- **Mixed criterion types on one plan: measurement vs pass-fail vs visual/instruction** — not every criterion is
  numeric. · seen in: Odoo (six check types: instructions, take a picture, register production, pass-fail,
  measure, worksheet), Oracle (values list vs numeric limits), Intelex (photo capture) · priority:
  **table-stakes** · spine: `InspectionCharacteristic.characteristic_type` choice; photos via **verified
  `core.Document`** generic FK, no new attachment table · buildable now
- **Critical-to-quality flag on a characteristic** — one failed critical characteristic fails the lot regardless
  of the rest. · seen in: Siemens (CTQ parameters), SAP (critical characteristics), Oracle (spec limits per
  characteristic) · priority: **common** · spine: `InspectionCharacteristic.is_critical` boolean, used by the
  pass/fail evaluator · buildable now
- **Sampling policy: 100% / percentage / fixed count / AQL** — how much of the lot is actually checked, and the
  accept/reject arithmetic that follows. Oracle is explicit: with %/fixed-count sampling one failed sample
  rejects the whole quantity; with AQL the lot is rejected when failures ≥ the AQL rejection number. · seen in:
  Oracle, NetSuite (conformance rules: 100% inspection or skip-lot/AQL tables), SAP (sampling procedures),
  Odoo (control per operation/product/quantity; frequency all / random % / periodic) · priority: **table-stakes**
  · spine: `InspectionPlan.sampling_method` + `sample_percentage` / `sample_size` / `aql_accept_number` /
  `aql_reject_number` · buildable now (**the AQL *tables* themselves — ANSI/ASQ Z1.4 lookup by lot size and
  inspection level — are deferred**; the plan stores the accept/reject numbers a quality engineer enters)
- **Versioned / effective-dated specifications** — a spec changes and old certificates must still show the spec
  that was in force. · seen in: AlisQI (specification versions), SAP (inspection plan valid-from key date),
  MasterControl/Veeva (document-controlled specs) · priority: **common** · spine: `InspectionPlan.version` +
  `effective_from` + `is_active`, and — critically — the **executed inspection snapshots the criteria onto its
  own result rows** (the 4.8 `WorkOrderComponent` snapshot precedent), so editing a plan can never rewrite
  history · buildable now

**The execution half**

- **An inspection record per triggering document ("inspection lot" / "inspection queue")** carrying item, lot,
  location, quantity inspected, sample size, quantity accepted, quantity rejected, inspector and date. · seen in:
  SAP (inspection lot), NetSuite (Quality Inspection Queue record), Oracle (inspection with samples/serials),
  Odoo (quality check), ETQ (Inspection Management app) · priority: **table-stakes** · spine: **new table
  `QualityInspection` [QC-]** · buildable now
- **Three trigger points: incoming (goods receipt), in-process (production), outgoing (pre-shipment)** — this is
  literally the bullet's "incoming and outgoing goods", and 4.8 explicitly left the in-process seam. · seen in:
  SAP (GR from vendor / in-process / before shipment to customer / periodic stock), NetSuite (item receipt / WO
  completion / item fulfillment), Odoo (receipts / manufacturing / delivery operations), Siemens (inspections
  mapped to production stages) · priority: **table-stakes** · spine: `QualityInspection.inspection_type` +
  **nullable FKs to the verified `scm.GoodsReceiptNote`, `scm.WorkOrder`, `scm.Shipment`** · buildable now
- **Result capture per characteristic, evaluated automatically against the limits** — measured value in, pass/fail
  out; the overall lot verdict is derived from the rows. · seen in: Oracle ("if results are within the
  specification limits, the samples are automatically accepted"), NetSuite ("conformance rules … determine an
  inspection's Pass or Fail status … evaluated after all quality data has been submitted"), Odoo (measure vs
  tolerance), AlisQI (automated specification checking) · priority: **table-stakes** · spine: **new child table
  `InspectionResult`** (snapshot of the characteristic + `measured_value` + `result`); the verdict is a
  **derived** property, never a typed field · buildable now
- **An explicit inspection state machine with a hold and a cancel** — NetSuite's is pending → in-process →
  pass/fail, with hold and cancel reachable only by a quality manager. · seen in: NetSuite, SAP (lot completion
  via usage decision), Intelex (creation → triage → verification → resolution) · priority: **table-stakes** ·
  spine: `QualityInspection.status` choices + `EDITABLE_STATUSES` (the app-wide pattern) · buildable now
- **A usage decision / disposition action on the finished inspection: accept, quarantine, return to vendor** ·
  seen in: SAP (usage decision: accept / reject / rework), NetSuite (Action = Quarantine → stop the item being
  used, or Return to Vendor → start the RTV process; pre-inspection, release-if-ready and post-inspection
  quarantine variants), Oracle (reject or scrap transaction) · priority: **table-stakes** · spine: the accept
  path needs no ledger effect; **quarantine sets the verified `LotSerial.status = 'quarantine'`** (already a
  valid value — no parallel hold table, no StockMove); reject/scrap raises an NCR whose disposition does the
  stock work (below) · buildable now
- **Inspector is a person, and the inspection is signed off** · seen in: every product · priority:
  **table-stakes** · spine: **`core.Party` with the `employee` role via the existing `_employee_parties()`
  helper** — never a new inspector table (L29) · buildable now
- **Failure proposes the nonconformance rather than silently creating it** — Oracle auto-creates an NC per
  inspection failure; NavERP's compute-then-convert doctrine makes this a "Raise NCR" button that pre-fills from
  the inspection. · seen in: Oracle (auto), ETQ/QT9/Intelex (linked NCR), Odoo ("Message If Failure" → create a
  quality alert) · priority: **table-stakes (the link), differentiator (the pre-fill)** · spine: view action on
  `QualityInspection` creating a `NonConformance` · buildable now
- **Skip-lot / reduced inspection for a trusted supplier-item ("dock to stock")** · seen in: NetSuite (skip-lot
  sampling logic), SAP (dynamic modification rules), Odoo (frequency: randomly X% of operations / periodically) ·
  priority: **common** · spine: `InspectionPlan.frequency` + `frequency_value` this pass (the *rule* is stored and
  shown; automatic escalation/de-escalation based on history is **deferred**) · buildable now (static), later (dynamic)
- **Supplier's own CoA received and verified against the spec at goods-in** · seen in: AlisQI (extracts data from
  supplier CoA PDFs automatically), SAP (certificate receipt in QM in procurement), ETQ/Intelex (supplier
  documentation) · priority: **common** · spine: `QualityInspection.supplier_coa_reference` free text +
  the attached PDF as a **verified `core.Document`**; automated PDF extraction is **integration/later**

### Bullet 2 — Non-Conformance Reports (NCR)

- **One NCR register fed from every detection source** (inspection failure, goods receipt, production, supplier,
  audit finding, internal observation). · seen in: QT9 (NC connects to CAPA, audits, complaints, inspections,
  deviations), Intelex (internal and external nonconformances), MasterControl (quality events cover deviations,
  NC and OOS), ETQ, TrackWise, Qualio (combined CAPA & NCR) · priority: **table-stakes** · spine: **new table
  `NonConformance` [NCR-]** with a `source` choice plus nullable FKs to the verified `QualityInspection`,
  `scm.GoodsReceiptNote`, `scm.WorkOrder`, `scm.Shipment` · buildable now
- **What/how much is affected: item, lot/batch, location, quantity** · seen in: all surveyed · priority:
  **table-stakes** · spine: FKs to verified `scm.Item`, `scm.LotSerial`, `scm.Location`, `scm.UOM` · buildable now
- **Defect classification + severity, with severity driving how deep the response goes** — Intelex is explicit
  that severity selects the level of RCA / 8D / CAPA. · seen in: Intelex (defect codes + severity), QT9 (types and
  categories for KPI reporting), Veeva/MasterControl (event classification) · priority: **table-stakes** ·
  spine: `defect_category` + `severity` choice fields on `NonConformance` (a configurable defect-code *table* is
  **deferred**) · buildable now
- **Containment / segregation before disposition (quarantine, suspect-material tagging, stop-ship)** · seen in:
  QT9 ("quarantine affected items", "prevent nonconforming shipments"), NetSuite (Quarantine action),
  MRB practice, `NavERP.md` 12.5 · priority: **table-stakes** · spine: `containment_action` text +
  **`LotSerial.status = 'quarantine'`** toggled by an explicit action, with the release back to `available`
  recorded on disposition. Optionally the goods are physically moved to a QC-hold bin — that needs **no new
  schema**: it is an existing 4.3 `StockTransfer` to a `Location` the tenant creates · buildable now
- **Material-review disposition: use-as-is / rework / repair / scrap / return-to-vendor / regrade, with who
  decided and when** · seen in: QT9 (scrap, use-as-is, rework, RTV + assigned approvers), MRB convention,
  `NavERP.md` 12.5, SAP (usage decision), NetSuite (RTV action) · priority: **table-stakes** · spine:
  `disposition` + `disposition_by` (`core.Party` employee) + `disposition_on` + `disposition_notes`; the MRB is
  modelled as *the decision fields*, **not** as a board/meeting entity (deferred) · buildable now
- **The disposition actually moves stock** — scrap must reduce on-hand; use-as-is must not. · seen in: Oracle
  (reject/scrap transaction), NetSuite (workflows triggered by the action), SAP · priority: **table-stakes** ·
  spine: **post through the existing `_post_stock_move(...)` helper with the existing `move_type='adjustment'`** —
  see the ruling below · buildable now
- **Cost of poor quality attached to the NCR** · seen in: QT9 ("assign credit information by putting dollars and
  cents to poor quality") · priority: **differentiator** · spine: a plain `cost_of_quality` decimal the user
  enters (defaulted from `quantity_affected × Item.average_cost`, which is a **verified** field) plus a report
  roll-up. **It never posts a JournalEntry (L29)** — accounting sees only the scrap `StockMove` through the 4.3
  valuation report · buildable now
- **Workflow with owner, due date, overdue alerting and closure** · seen in: Intelex (creation → triage →
  verification → resolution, due dates + notifications), QT9 (overdue alerts, approvers) · priority:
  **table-stakes** · spine: `status`, `owner` (Party), `due_date`, an `is_overdue` property and an overdue chip on
  the list page (the 4.6/4.7 pattern); **email notification is integration/later** · buildable now
- **Trending / Pareto by defect category, item, supplier** · seen in: Intelex (real-time dashboards), QT9
  (charts + trending), MasterControl (AI deviation-trend identification), `NavERP.md` 12.5 · priority: **common**
  · spine: computed report over `NonConformance` (no new table) · buildable now (basic counts); ML trend
  detection is **later**
- **Affected-lot tracing / impact assessment ("what else came off that batch")** · seen in: Veeva, TrackWise
  (recall management), `NavERP.md` 12.5/12.18 · priority: **common in regulated industries** · spine: derivable
  today from the verified `StockMove` ledger filtered by `lot_serial` — a **read-only "where did this lot go"
  panel** on the NCR detail; recall execution is **parked (12.18 / 4.10)** · buildable now (panel), later (recall)

### Bullet 3 — Corrective and Preventive Action (CAPA)

- **A CAPA record that can be raised from an NCR *or* stand alone** — TrackWise names "stand-alone CAPA" as a
  first-class concept; QT9 auto-creates CAPA from feedback, quality events, NC, audits, management review, risk,
  safety and inspections. · seen in: QT9, TrackWise, MasterControl, Veeva, ETQ, Intelex, Qualio · priority:
  **table-stakes** · spine: **new table `CapaAction` [CAPA-]** with a `source` choice and a **nullable**
  `nonconformance` FK · buildable now
- **Corrective vs preventive is an attribute of the action, not two tables** · seen in: Odoo (separate corrective
  and preventive action tabs on one alert), ISO 9001 §10.2, every EQMS · priority: **table-stakes** · spine:
  `action_type` choice · buildable now
- **Root cause analysis with a named method** — 5 Whys, fishbone, fault tree, 8D. · seen in: QT9 ("fully
  integrated RCA" + "8D CAPA process"), Intelex (8D problem-solving scaled to severity), `NavERP.md` 12.4 ·
  priority: **table-stakes (recording the root cause), common (naming the method)** · spine:
  `root_cause_method` choice + `root_cause` text. **Structured 8D/5-Why templates (D1–D8 step records, fishbone
  category branches) are deferred** — this pass stores the method and the conclusion · buildable now
- **Action plan broken into owned, dated tasks** · seen in: QT9 ("unlimited tasks" involving multiple parties),
  Veeva (CAPA plans), Intelex (action plans) · priority: **common** · spine: small child table `CapaTask`
  (sequence, description, `owner` Party, due date, completed on, status) — a child, so it does not consume a
  model slot · buildable now
- **Containment/correction recorded separately from the corrective action** — TrackWise distinguishes
  "corrections" from CAPA. · seen in: TrackWise, MRB practice, ISO 9001 · priority: **common** · spine:
  `containment_action` text field · buildable now
- **Effectiveness verification after implementation, then formal closure** — QT9 verifies effectiveness *after*
  final approval; `NavERP.md` 12.4 calls it out as its own bullet. · seen in: QT9, MasterControl, Veeva, ETQ,
  Qualio · priority: **table-stakes** · spine: `implemented_on`, `effectiveness_due_date`,
  `effectiveness_result` (pending / effective / not_effective), `verified_by` (Party), `verified_on`,
  `verification_notes`, `closed_on`; a "not effective" verdict is what re-opens the CAPA · buildable now
- **Due-date monitoring, priority and overdue escalation** · seen in: QT9 (overdue email alerts, priority set from
  due dates), Intelex, `NavERP.md` 12.4 · priority: **table-stakes** · spine: `priority` + `due_date` +
  `is_overdue` property + an overdue chip/filter; **email escalation is integration/later** · buildable now
- **Supplier corrective action request (SCAR) as a CAPA aimed at a vendor** · seen in: MasterControl, ETQ (supply
  chain quality), Veeva (supplier quality), TrackWise · priority: **common** · spine: `supplier` FK to
  **`core.Party`** (supplier/vendor role) on `CapaAction` — 4.2's `SupplierScorecard.flagged_for_review` was
  explicitly left as "the thin hook, not a parallel CAPA system" (`research-scm-4.2.md:305–307`), so this closes
  that loop without touching 4.2's schema · buildable now
- **Rules-based routing / dynamic approval chains** · seen in: MasterControl ("rules-based routing … based on
  conditions and context"), Veeva, ETQ (configurable workflow engine) · priority: **differentiator** ·
  spine: **deferred** — NavERP has no workflow engine; this pass uses a fixed status ladder with an approver field
- **Linking a CAPA to document changes and to training assignments** · seen in: MasterControl (launch training
  from a CAPA or change control), Veeva, TrackWise · priority: **common in EQMS** · spine: **parked** — documents
  are Module 13 / 12.1 and training is HRM 3.22–3.24 / 12.12; `core.Document` attachment is the only link this pass

### Bullet 4 — Audit Management

*(See the scope ruling below — this bullet is the one recommended for the follow-up pass. The catalog is
recorded here so nothing is lost.)*

- **Audit programme / schedule with frequency and risk-based selection** · seen in: Intelex (audit scheduler with
  frequency and risk level, filterable by scope, location, manager), ETQ, MasterControl, TrackWise, Veeva,
  Qualio, QT9 · priority: **table-stakes among EQMS suites** · spine: new table `QualityAudit` [QA-] · buildable now
- **Audit type: internal, supplier, customer, certification/regulatory** · seen in: Intelex, TrackWise ("400
  audits per year"), ETQ, Veeva (external partner audit findings), `NavERP.md` 12.11 · priority: **table-stakes**
  · spine: `audit_type` choice + a single nullable `auditee_party` (`core.Party`) *or* `auditee_org_unit`
  (`core.OrgUnit`) — **verified to exist**; a full supplier-audit-vs-internal-audit split is **deferred**
- **Checklist execution against a standard (ISO 9001 / IATF 16949 / AS9100 / ISO 13485)** · seen in: Intelex
  ("create custom or ISO checklists"), ETQ, QT9, Qualio · priority: **table-stakes** · spine: **reuse
  `InspectionPlan` + `InspectionCharacteristic` as the checklist** (`plan_type='audit_checklist'`, pass-fail
  characteristics) — the strongest argument for building the plan table first
- **Findings with a grading (major / minor / observation / opportunity for improvement) plus evidence** · seen in:
  Intelex (findings sortable by severity, evidence uploaded in real time), ETQ, TrackWise, `NavERP.md` 12.11 ·
  priority: **table-stakes** · spine: **findings are `NonConformance` rows with `source='audit'`** — one finding
  register, not two; evidence via `core.Document`
- **Finding → CAPA with a response deadline and closure verification** · seen in: TrackWise (audit report
  generates CAPA plans), Intelex, ETQ, MasterControl · priority: **table-stakes** · spine: the existing
  `CapaAction.source='audit_finding'` path — no extra schema
- **Audit report generation** · seen in: TrackWise, Intelex (export), ETQ · priority: **common** · spine: a print
  template over the audit + its findings (the 4.x print-page precedent, e.g. HRM's relieving letter)

### Bullet 5 — Certificate of Analysis (CoA)

- **A CoA is generated per lot/batch at the point of shipment, from that lot's inspection results** — NetSuite is
  unambiguous: the CoA report is produced for fulfilled sales/transfer orders when the item leaves the location,
  one page per lot, only for lot-controlled items, and only from lots actually assigned on the fulfillment. ·
  seen in: NetSuite, Deacom/E21 (CoA printed with the shipping documents, one per line item), SAP (quality
  certificate), AlisQI · priority: **table-stakes** · spine: **a generate/print page over the verified
  `scm.Shipment` → `scm.LotSerial` → outgoing `QualityInspection`** — no new table required · buildable now
- **The CoA body is the results table: characteristic, result, specification limits, unit, test method** · seen
  in: AlisQI (exactly this table plus header fields and a configurable footer), Deacom/E21 ("tests performed, the
  specification, and all test results"), NetSuite (inspection results confirming the item meets its
  specification) · priority: **table-stakes** · spine: the snapshotted `InspectionResult` rows, filtered by the
  **`InspectionCharacteristic.include_on_coa`** flag — this single boolean is what makes CoA a report instead of
  a table · buildable now
- **Header identity: product, batch/lot number, expiry, quantity, customer, order/shipment reference, issue date**
  · seen in: AlisQI (product, batch, expiry header fields), NetSuite (lot details), Deacom · priority:
  **table-stakes** · spine: all present on verified `scm.Item` / `scm.LotSerial` (`number`, `expiry_date`) /
  `scm.Shipment` / `scm.SalesOrder` / `core.Party` · buildable now
- **Refuse to issue a certificate containing an out-of-spec result** · seen in: AlisQI (can be configured to
  prevent generating a CoA with off-spec values) · priority: **differentiator, and exactly the right guard** ·
  spine: the generate page blocks (with a clear message) when the lot has no passed outgoing inspection or has a
  failing result — compute-then-convert: it proposes and blocks, a human issues · buildable now
- **Templates per product / per customer / per product+customer** · seen in: AlisQI, Deacom/E21 ("multiple unique
  CoA formats based on the item, customer, or customer-item combination") · priority: **common** · spine:
  **deferred** — one clean printable template this pass; a `CoATemplate` table is a later pass
- **Record of issuance (number, date, recipient) for traceability** · seen in: AlisQI (generated PDF is archived
  against the result and emailed to selected contacts), regulatory practice · priority: **common** · spine:
  three stamp fields on the outgoing `QualityInspection` — `coa_number` (via
  `next_number(QualityInspection, tenant, "COA", field="coa_number")`, which the **verified** helper already
  supports), `coa_issued_on`, `coa_issued_to` (`core.Party`). A standalone `CertificateOfAnalysis` register is
  **deferred**, with the `COA-` prefix reserved · buildable now
- **Email the CoA to the customer contact / publish to a portal** · seen in: AlisQI, Deacom · priority: **common**
  · spine: **integration/later** (no outbound email in SCM yet; the 4.5 "Customer Notifications" precedent)

### Beyond the bullets (strong features the five bullets don't name)

- **First-pass yield / right-first-time as the headline quality KPI** — derivable from
  `QualityInspection` pass vs fail counts, and from `WorkOrder.quantity_produced` vs `quantity_scrapped`
  (**verified** fields). · seen in: MasterControl, Intelex, QT9 dashboards · priority: **common** · spine:
  computed report, no table · buildable now
- **Statistical process control charts (X-bar/R, control limits, trend alarms) and Cp/Cpk capability studies** ·
  seen in: Siemens (operator-facing SPC), AlisQI (integrated SPC), `NavERP.md` 12.7/12.15 · priority: **common in
  manufacturing QMS** · spine: **deferred** — needs a charting story; the measured values captured on
  `InspectionResult` are the data source when it lands
- **Quality teams owning products/operations** · seen in: Odoo (unlimited quality teams assigned to products or
  operations) · priority: **differentiator** · spine: **deferred** — a single `owner` Party per record covers
  this pass
- **AI event summarisation and deviation-trend detection** · seen in: MasterControl, Veeva (Quality Event
  Agents), Qualio (AI gap analysis) · priority: **differentiator** · spine: **integration/later**
- **Mobile/offline capture on the shop floor and at the dock** · seen in: Intelex (mobile NCR app with photos),
  Intelex audits (offline), Odoo Shop Floor · priority: **common** · spine: **later** — the HTMX pages are
  responsive but there is no offline story
- **Gauge/instrument integration (direct measurement capture)** · seen in: Siemens ("use direct gauges to reduce
  errors") · priority: **differentiator** · spine: **integration/later**

---

## Recommended build scope (this pass — 4 models + 1 report/print page)

Sub-package `apps/scm/models/QualityManagement/` (+ the matching `forms/`, `views/`, `urls/` packages and
`templates/scm/quality/<entity>/{list,detail,form}.html`), re-exported from every package `__init__.py`.

1. **`InspectionPlan`** — `TenantOwned` master, **no number prefix** (like `Item`/`Location`/`UOM`/`SupplierProfile`;
   `code` + `unique_together("tenant", "code")` instead — this keeps a prefix free).
   *Fields justified by:* reusable spec keyed to a trigger (SAP/NetSuite/Oracle/Odoo), scope by item or category or
   supplier (NetSuite/Oracle/Odoo), sampling policy (Oracle AQL/%/fixed, NetSuite conformance rules), skip-lot
   frequency (NetSuite/SAP/Odoo), versioned specs (AlisQI/SAP).
   `code`, `name`, `plan_type` (incoming_receipt | in_process | outgoing_shipment | periodic_stock
   *[| audit_checklist when the audit pass lands]*), `item` (nullable), `item_category` (nullable),
   `supplier` (nullable Party), `sampling_method` (all_100 | percentage | fixed_count | aql),
   `sample_percentage`, `sample_size`, `aql_accept_number`, `aql_reject_number`, `frequency`
   (every | random_percent | periodic), `frequency_value`, `version`, `effective_from`, `is_active`, `notes`.
   **FKs (all verified):** `scm.Item`, `scm.ItemCategory`, `core.Party`.
   Child **`InspectionCharacteristic`**: `sequence`, `name`, `characteristic_type` (measurement | pass_fail |
   visual | instruction), `uom` (`scm.UOM`), `target_value`, `lower_limit`, `upper_limit`, `expected_text`,
   `test_method`, `is_critical`, `is_mandatory`, **`include_on_coa`**.

2. **`QualityInspection`** [**QC-**] — `TenantNumbered`, the transaction.
   *Fields justified by:* inspection lot / inspection queue (SAP, NetSuite, Oracle, ETQ), the three trigger points
   (SAP/NetSuite/Odoo/Siemens; 4.8 left the seam), sample vs accepted vs rejected arithmetic (Oracle), the
   pending/in-process/pass/fail/hold/cancel state machine (NetSuite), usage decision + quarantine/RTV action
   (SAP/NetSuite), inspector sign-off (all), supplier CoA verification (AlisQI/SAP).
   `plan` (nullable — ad-hoc inspections are allowed), `inspection_type`, `goods_receipt` (nullable),
   `work_order` (nullable), `shipment` (nullable), `item`, `lot_serial` (nullable), `location` (nullable),
   `supplier` (nullable Party), `quantity_inspected`, `sample_size`, `quantity_accepted`, `quantity_rejected`,
   `inspector` (Party, employee role), `inspected_on`, `status` (draft | in_progress | passed | failed | on_hold |
   cancelled; `EDITABLE_STATUSES = ("draft", "in_progress")`), `usage_decision` (pending | accept | accept_with_
   deviation | reject), `action_taken` (none | quarantined | ncr_raised | returned_to_vendor),
   `supplier_coa_reference`, `notes`, **+ the CoA stamp** `coa_number` / `coa_issued_on` / `coa_issued_to`.
   **FKs (all verified):** `scm.GoodsReceiptNote`, `scm.WorkOrder`, `scm.Shipment`, `scm.Item`, `scm.LotSerial`,
   `scm.Location`, `core.Party`.
   Child **`InspectionResult`**: snapshot of `characteristic_name` / `characteristic_type` / `uom` /
   `target_value` / `lower_limit` / `upper_limit` / `test_method` / `include_on_coa` **copied at generation**
   (the 4.8 `WorkOrderComponent` precedent — a later plan edit must never rewrite a past certificate), plus
   `measured_value`, `result` (pass | fail | not_applicable), `notes`.

3. **`NonConformance`** [**NCR-**] — `TenantNumbered`, the single finding register.
   *Fields justified by:* multi-source NC register (QT9/Intelex/MasterControl/ETQ), defect codes + severity-driven
   response (Intelex), containment/quarantine (QT9/NetSuite/MRB), MRB dispositions with decider and date
   (QT9/MRB/SAP), cost of poor quality (QT9), owner/due date/overdue (Intelex/QT9), trending (Intelex/QT9).
   `source` (inspection | goods_receipt | production | supplier | audit | internal), `inspection` (nullable),
   `goods_receipt` (nullable), `work_order` (nullable), `shipment` (nullable), `item`, `lot_serial` (nullable),
   `location` (nullable), `supplier` (nullable Party), `quantity_affected`, `uom`, `defect_category`, `severity`
   (critical | major | minor | observation), `title`, `description`, `detected_by` (Party), `detected_on`,
   `containment_action`, `quarantine_applied` (bool, mirrors the `LotSerial.status` flip),
   `disposition` (pending | use_as_is | rework | repair | scrap | return_to_vendor | regrade),
   `disposition_by` (Party), `disposition_on`, `disposition_notes`, `cost_of_quality`, `owner` (Party),
   `due_date`, `status` (open | investigating | dispositioned | closed | cancelled), `closed_on`.
   **FKs (all verified):** as above + `core.Party`. Attachments via **`core.Document`** (generic FK).

4. **`CapaAction`** [**CAPA-**] — `TenantNumbered`.
   *Fields justified by:* stand-alone or linked CAPA (TrackWise/QT9), corrective vs preventive on one record
   (Odoo/ISO 9001), named RCA method (QT9 8D/RCA, Intelex), owned dated tasks (QT9 "unlimited tasks"),
   containment separate from correction (TrackWise), effectiveness verification then closure (QT9/MasterControl/
   Veeva), priority + overdue (QT9/Intelex), SCAR against a supplier (MasterControl/ETQ/Veeva, and 4.2's parked hook).
   `action_type` (corrective | preventive), `title`, `source` (nonconformance | audit_finding | inspection_trend |
   supplier | complaint | internal_improvement), `nonconformance` (**nullable**), `item` (nullable),
   `supplier` (nullable Party), `problem_statement`, `containment_action`, `root_cause_method` (five_why |
   fishbone | fault_tree | eight_d | pareto | other), `root_cause`, `action_plan`, `owner` (Party), `priority`,
   `due_date`, `status` (open | investigating | in_progress | pending_verification | closed | cancelled),
   `implemented_on`, `effectiveness_due_date`, `effectiveness_result` (pending | effective | not_effective),
   `verified_by` (Party), `verified_on`, `verification_notes`, `closed_on`.
   Child **`CapaTask`**: `sequence`, `description`, `owner` (Party), `due_date`, `completed_on`, `status`.

5. **CoA generate/print page** (report, not a model) — `scm:coa_report` listing shipped/shippable lots with their
   outgoing inspection status, plus `scm:coa_print` (`<int:inspection_pk>/coa/`) rendering the certificate:
   header (item, lot, expiry, quantity, customer, shipment ref, issue date) + the results table restricted to
   `include_on_coa` characteristics with limits/unit/test method + a conclusion and signature block. Blocks
   issuance when there is no passed outgoing inspection or any included result is out of spec (AlisQI's guard).
   Issuing stamps `coa_number` / `coa_issued_on` / `coa_issued_to` on the inspection.
   Follows the existing report precedent: `apps/scm/urls/<SubModule>/Reports.py` →
   `path("...", views.<name>, name="<name>")`, exactly like `valuation_report` / `safety_stock_report` /
   `mrp_report`.

### Two ledger/stock rulings the todo agent should not re-litigate

**(a) A quality reject reuses `move_type='adjustment'` — do NOT add a `scrap` move type.** `StockMove.MOVE_TYPES`
already documents `adjustment` as "write-off / damage / cycle count / found / revaluation", and the model carries
both `reference` and `reason`, so a scrap disposition posts a negative `adjustment` with
`reference="NCR-00007"`, `reason="NCR scrap — <defect category>"` and is fully attributable (a scrap report is
`move_type='adjustment', reference__startswith='NCR-'`). 4.8's two new types were justified by a *correctness*
failure — 4.7's `demand_series` reads `move_type='issue'` as customer demand, so consumption had to be distinct.
No equivalent contamination exists for scrap: `adjustment` is already excluded from demand and already
participates correctly in the FIFO/LIFO layer walk. Adding a type would be a migration plus an audit of the
valuation walk, the demand series and MRP for no behavioural gain.

**(b) Quarantine is a flag, not a movement.** Setting `LotSerial.status='quarantine'` posts **nothing** — on-hand
is unchanged because the goods are still physically there. Any physical segregation is an ordinary 4.3
`StockTransfer` into a tenant-created QC-hold `Location`. Never a parallel hold/blocked-stock table, and never a
stored "blocked quantity" (L37: on-hand is always `Sum(quantity)`).

**(c) Rejections at goods receipt never entered stock.** `_post_grn_receipt` posts moves only for
`quantity_received`; `GoodsReceiptLine.quantity_rejected` was refused at the dock. An incoming NCR raised against
those units must therefore post **no** stock effect — only the RTV/credit decision. An incoming inspection done
*after* the GRN was booked is inspecting on-hand stock, and there a scrap disposition does post the adjustment.

### Sidebar wiring (exact `LIVE_LINKS["4.9"]` keys)

```python
"4.9": {
    "Quality Inspection":                        "scm:qualityinspection_list",
    "Non-Conformance Reports (NCR)":             "scm:nonconformance_list",
    "Corrective and Preventive Action (CAPA)":   "scm:capaaction_list",
    "Audit Management":                          <see the ruling below>,
    "Certificate of Analysis (CoA)":             "scm:coa_report",
}
```
`InspectionPlan` gets **no** sidebar key (it is a master reached from the inspection list — the `WorkCenter` /
`ReorderRule` precedent). "Certificate of Analysis (CoA)" pointing at a report is the
`safety_stock_report` / `mrp_report` / `valuation_report` precedent — a bullet may be a computed page.

### The fifth bullet — the one honest scope decision to make

Four models cover four bullets (bullet 1 needs *two* tables: the criteria master and the execution record) and
the CoA report covers the fifth. **"Audit Management" is therefore the bullet with no home in a 4-model pass.**
Two options, with a recommendation:

- **Option A (holds the 4-model cap — recommended if scope discipline wins):** ship the four models now and add
  `QualityAudit` in an immediate 4.9-second-pass, leaving the `"Audit Management"` key out of `LIVE_LINKS["4.9"]`
  until it exists. Pointing the key at a filtered NCR list (`?source=audit`) would be dishonest — nothing can
  create such a row yet — so the key simply waits. Design for it now: `NonConformance.source` already includes
  `audit`, and `InspectionPlan.plan_type` gains `audit_checklist` when the audit pass lands.
- **Option B (5 models — take this only if all five sidebar keys must go live in one pass):** add
  **`QualityAudit`** [**QA-**]: `audit_type` (internal | supplier | customer | certification), `title`,
  `standard` (free text, e.g. ISO 9001:2015), `scope`, `auditee_party` (nullable `core.Party`),
  `auditee_org_unit` (nullable `core.OrgUnit`), `checklist_plan` (nullable `InspectionPlan`),
  `lead_auditor` (Party, employee), `planned_date`, `actual_start`, `actual_end`, `status` (planned | in_progress
  | reported | closed | cancelled), `conclusion`, `findings_major`/`findings_minor` (derived counts), `notes`.
  Findings are `NonConformance` rows with `source='audit'` + an `audit` FK — **no separate finding table** — and
  audit CAPAs are `CapaAction(source='audit_finding')`. Sidebar: `"Audit Management": "scm:qualityaudit_list"`.
  It is the cheapest of the five to add (**zero coupling to `Item`/`LotSerial`/`StockMove`/GRN/Shipment/WorkOrder**
  — nothing in it can destabilise the ledger), which is exactly why it is also the safest to postpone.

Evidence behind ranking audit last of the five: audit management is universal in the **EQMS suites**
(MasterControl, ETQ, TrackWise, Veeva, Intelex, Qualio, QT9) but **absent from every ERP/MES-native quality
module surveyed** (Odoo Quality, NetSuite Quality Management, SAP QM's inspection flow, Siemens Opcenter X
Quality) — and 4.9 is an ERP quality module. It is also the most Module-12-shaped bullet: `NavERP.md` 12.11 is a
five-bullet sub-module devoted to it (programme planning, checklists, findings grading, CAPA linkage, regulatory
and certification audits), and 4.2 already ships `SupplierScorecard` + `SupplierRiskAssessment` for the
supply-chain-relevant slice of supplier evaluation.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **RMA / return-to-vendor execution, refunds, warranty claims, disposition of *returned* goods** → **4.10 Returns
  Management**. 4.9 records the *decision* `disposition='return_to_vendor'`; 4.10 owns the RMA document.
  (`NavERP.md` 12.7 bundles "Reject & RMA" into IQC; NavERP splits it — respect the split.)
- **Quality KPI dashboards / cross-module analytics** → **4.11 Supply Chain Analytics**. 4.9 ships stat chips on
  its own list pages (the app-wide pattern) and one CoA page; a quality command centre is 4.11's.
- **Supplier qualification, approved-vendor list, supplier scorecards, supplier risk** → **4.2 SRM** (already
  built: `SupplierProfile`, `SupplierScorecard`, `SupplierRiskAssessment`). 4.9 must **not** add a supplier
  quality rating field — the future enrichment is feeding NCR counts into 4.2's existing
  `SupplierScorecard.quality_score`, which is a 4.2 change, not a 4.9 table.
- **ISO/certification tracking, regulatory compliance registers, contract compliance clauses** → **4.12 Contract &
  Compliance Management**.
- **Gauge/instrument calibration schedules, as-found/as-left records, out-of-tolerance impact** → **4.13 Asset
  Management** (and 12.10). `Calibration` in the Module 12 plan lands there or in 12.10 — not in 4.9.
- **Temperature/cold-chain excursion monitoring** → **4.15 Cold Chain Management**.
- **Customer-facing CoA download / complaint submission** → **4.16 Customer Portal**.
- **Customer complaint intake and handling** → CRM (helpdesk `Case`) and **12.13**. `NonConformance.source` has no
  `customer_complaint` value this pass on purpose.
- **In-process control points that *block* a work-order operation from closing** → the gate itself is 4.9's, but
  the operation-level routing it would hook into does not exist (4.8 shipped work centres and time logs, not
  routings/operations). Inspection stays document-level (`work_order` FK) until routings exist.
- **Preventive maintenance / MTBF on work centres** → **4.13** (already parked there by `research-scm-4.8.md`).

---

## Deferred (later passes / integrations / Module 12)

- **`QualityAudit`** — see Option A/B above. First item in the 4.9 backlog either way.
- **Standalone `CertificateOfAnalysis` register + `CoATemplate` (per product / per customer formats) + emailing
  the PDF** — this pass generates and stamps; the `COA-` prefix is reserved. AlisQI/Deacom-grade template
  management is a later pass.
- **AQL lookup tables (ANSI/ASQ Z1.4 by lot size and inspection level) and dynamic skip-lot escalation** — the
  plan stores accept/reject numbers and a static frequency; deriving them from lot size, and tightening/loosening
  based on supplier history, is later.
- **SPC control charts and Cp/Cpk capability studies** (Siemens, AlisQI, 12.7/12.15) — the measured values on
  `InspectionResult` are the data source; charting needs a front-end story NavERP hasn't chosen.
- **Structured 8D / 5-Why / fishbone templates** (D1–D8 step records, cause branches) — this pass stores the
  method name and the conclusion text.
- **Electronic signatures, 21 CFR Part 11 / EU Annex 11 audit trails, ALCOA+ data integrity** → 12.20. NavERP has
  `core.AuditLog` but no signature manifestation.
- **Training/competency linkage** (MasterControl launches training from a CAPA) → HRM 3.22–3.24 / 12.12.
- **Document-controlled SOPs, spec approval routing, obsolescence** → Module 13 DMS / 12.1. `core.Document` is the
  only attachment mechanism this pass.
- **Configurable defect-code and root-cause-code tables** — choice fields this pass; a per-tenant code master
  later (the same call 4.6 made for mode/equipment capability matrices).
- **Rules-based/conditional workflow routing and configurable approval matrices** (MasterControl/ETQ/Veeva) —
  fixed status ladders this pass; NavERP has no workflow engine.
- **Automated supplier-CoA ingestion (PDF extraction)** (AlisQI) — a reference field plus an attached
  `core.Document` this pass; extraction is an integration.
- **Email/notification escalation for overdue NCRs and CAPAs** — the overdue *state* and filters are built; the
  outbound channel is integration/later (same posture as 4.5 "Customer Notifications").
- **Recall / field-action execution and lot genealogy tracing UI** → 12.18 / 4.10. The NCR detail gets a
  read-only "where this lot went" panel derived from `StockMove`; recall workflow is not built.
- **Material Review Board as a meeting/board entity with quorum and minutes** — the MRB is modelled as the
  disposition decision fields (who, when, why); the board itself is deferred.
- **Mobile/offline capture, gauge integration, AI event summarisation and trend detection** — all
  integration/later.
- **Feeding NCR counts into 4.2's `SupplierScorecard.quality_score`** — a small, high-value follow-up that
  belongs in a 4.2 change, not in this pass.

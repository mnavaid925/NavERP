# Research — Sub-module 4.13: Asset Management (Module 4 — Supply Chain Management, `scm`)

Domain surveyed: **EAM / CMMS** (enterprise asset management + computerised maintenance management) as it sits
*inside* a supply-chain suite — plant/warehouse/fleet equipment, PM schedules, maintenance work orders, MRO spare
parts, and the link from an operational asset to its financial depreciation.

---

## Repo state checked first

**`LIVE_LINKS` built so far in module 4** (`apps/core/navigation.py`, read at run time):
`4.1 … 4.12` — every key from `4.1` through `4.12` is present; **`4.13` is absent**, so 4.13 is the next unbuilt
sub-module. 4.14–4.19 are also unbuilt, so 4.13 may FK anything from 4.1–4.12 and nothing later.

**Spine entities VERIFIED to exist** (`grep -rn "^class \w+" apps/scm/models/ apps/accounting/models/ apps/core/models/`):

| Entity | Where | What 4.13 gets from it |
|---|---|---|
| `scm.Item` (+ `ItemCategory`, `UOM`) | `apps/scm/models/InventoryManagement/Items.py:56` | The **one** item master. MRO spare parts are `Item` rows — 4.13 must not declare a second parts catalogue. |
| `scm.Location` | `.../InventoryManagement/Locations.py:10` | Warehouse › zone › bin hierarchy + `is_pickable`, `capacity`. Asset location AND parts storeroom. |
| `scm.StockMove` | `.../InventoryManagement/StockMoves.py:13` | Append-only signed ledger; on-hand is *always* `Sum(quantity)`. Parts issued to a job = a StockMove. |
| `scm.LotSerial` | `.../InventoryManagement/LotSerials.py:5` | Serial-tracked spare parts. |
| `scm.ReorderRule` | `.../InventoryManagement/ReorderRules.py:26` | Per-(item, location) reorder point + safety stock + `reorder_quantity`, already wired to 4.3's reorder-alerts report and 4.1's requisition hand-off. **This IS the min/max the CMMS market calls "parts reorder".** |
| `scm.WorkCenter` | `.../Manufacturing/WorkCenters.py:23` | Machine/cell master with derived capacity + `oee_chip()`. An `Asset` may point at the centre it serves. |
| `scm.WorkOrder` | `.../Manufacturing/WorkOrders.py:26` | **Production** run [WO-]. A maintenance job is a *different* document — see the scope note below. |
| `scm.ProductionTimeLog` | `.../Manufacturing/ProductionTimeLogs.py:21` | Shop-floor interval log; already has `entry_type="downtime"` + `downtime_reason="breakdown"`. Production-side downtime, not asset-side. |
| `scm.NonConformance` / `scm.CapaAction` | `.../QualityManagement/` | The finding + root-cause register (4.9). A repeat failure escalates *out* to CAPA — 4.13 does not grow a second RCA table. |
| `scm.WarrantyClaim` | `.../ReturnsManagement/WarrantyClaims.py:34` | Supplier recovery claim [WTY-] with typed cost lines. Asset-warranty *claims* reuse this. |
| `accounting.FixedAsset` | `apps/accounting/models/FixedAssets/FixedAssetsRegister.py:6` | **The depreciation ledger already exists.** Verified fields: `NUMBER_PREFIX="FA"`, `name`, `category` (CharField), `acquisition_cost`, `salvage_value`, `useful_life_months`, `method` ∈ {straight_line, declining_balance, units_of_production}, `in_service_date`, `accumulated_depreciation` (editable=False), `last_depreciation_date`, `status` ∈ {cip, active, disposed}, `asset_account`/`accumulated_account`/`expense_account` → `accounting.GLAccount`, `custodian` → `core.Party`, `location` → `core.OrgUnit`; methods `depreciable_base`, `book_value()`, `remaining_depreciable()`, `period_depreciation()`. |
| `accounting.Currency` / `GLAccount` / `Bill` / `Invoice` | `apps/accounting/models/` | Already FK'd by string from `scm` (e.g. `FreightInvoices.py:63` → `accounting.Bill`). |
| `core.Party` / `PartyRole` | `apps/core/models/Party.py:5`, `PartyRole.py:5` | Technicians, maintenance vendors, custodians — **never** a new person/vendor table. |
| `core.OrgUnit`, `core.Document`, `core.Activity`, `core.AuditLog` | `apps/core/models/` | Owning department; `Document` is a `GenericForeignKey` attachment (manuals/photos) — verified at `Document.py:15-18`. |

**Verified NOT to exist** (grep returns nothing): `core.Asset`, `core.Item`, `scm.Asset`, `scm.Equipment`,
`scm.MaintenancePlan`, `scm.MeterReading`, `accounting.DepreciationEntry`, `accounting.AssetCategory`.
`NavERP-ERD.md:473`/`490-491` describe a *shared* `Asset` anchor that Accounting posts depreciation against —
**that shared row was never built.** What exists is `accounting.FixedAsset`, a purely financial record.

**Two as-built facts that constrain the design (found by grep, not assumed):**

1. `apps/scm/analytics.py:177` — `COGS_MOVE_TYPES = ("issue", "consumption")`. 4.11's margin analytics treat
   *both* existing outbound types as cost of goods sold. An MRO part drawn for a repair is **maintenance
   expense, not COGS** — so 4.13 must NOT post spare-part issues as `issue` (4.7 also reads `issue` as customer
   demand, `analytics.py:1949`/`2529`) and must NOT post them as `consumption` either. It needs its **own**
   move type, and that type must stay out of `COGS_MOVE_TYPES`.
2. Auto-number prefixes already taken in `scm`: `PO PR RFQ QT GRN SC SCR SRA CAT TRF ADJ CC PUT PIK YRD SO
   DF FA SEA DS WO WC BOM PRD QC NCR CAPA QA RMA WTY SHP LD CAR FRT ALR KPI CR TD LIC ESG`.
   **Free for 4.13: `AST`, `PM`, `MWO`, `MTR`.** (Note `FA` is taken in `scm` by `ForecastAdjustment` *and* in
   `accounting` by `FixedAsset` — numbering is per-model, but do not reuse it here.)

**Sibling research files consulted** — three earlier passes explicitly parked work *here*:
- `research-scm-4.8.md:460-462` — "Preventive maintenance on work centers / equipment (Odoo MTBF, Epicor
  equipment management, Acumatica) → **PARKED → 4.13**"; repeated at `:638`.
- `research-scm-4.9.md:590` — "Preventive maintenance / MTBF on work centres → **4.13**".
- `research-scm-4.11.md:514` — "Asset/fleet uptime, MTBF, maintenance-cost analytics → **4.13**".
- `research-scm.md:198-202` — the module-wide sweep said 4.13 "should stay minimal … rather than re-building an
  asset registry" **because Module 11 owns full asset management**. That advice pre-dates 4.3 shipping the item
  spine; see the L36 ownership call below, which supersedes it.

**L36 ownership call the `todo` agent must make explicitly.** Module 11 (Asset Management System, 19
sub-modules, `NavERP.md:1681-1815`) is the eventual home of full EAM. But 11.x is unbuilt and 4.13 is being
built now, and there is no `Asset` row anywhere to reuse. This is the exact shape of **L36 / L29**: the module
that ships a spine entity first OWNS it, and the ERD is reconciled for *both* modules in the same pass —
precisely what 4.3 did for `Item`/`Location`/`StockMove` (`Items.py:3-7`, lessons L36 at `lessons.md:427`,
`:457`). Recommendation: **`scm.Asset` is the operational asset spine**; Module 11 FKs into it by string and
extends (11.2 tracking, 11.7 condition monitoring, 11.19 fleet), and `NavERP-ERD.md:473` + `:490-491` get
reconciled to say so. The alternative (a throwaway 4.13 that Module 11 later duplicates) is the second-parallel-
schema bug L29 forbids.

---

## Leaders surveyed (with source links)

1. **IBM Maximo Application Suite (Manage)** — the enterprise EAM reference; asset lifecycle from procurement to
   decommissioning, job plans, PM records, meters, condition monitoring, storerooms, failure hierarchy —
   https://www.ibm.com/products/maximo/asset-management and
   https://www.ibm.com/products/maximo/condition-based-maintenance *(ibm.com returned HTTP 403 to a direct
   fetch; capabilities taken from the indexed summaries of those pages plus
   https://maximosecrets.com/ibm-maximo-manage-overview/ and
   https://www.interlocsolutions.com/blog/streamlining-asset-management-operations-exploring-ibm-maximo-manage)*.
2. **SAP S/4HANA Asset Management (Plant Maintenance)** — the functional-location / equipment / maintenance-plan /
   task-list / notification / order model that most of the market copies —
   https://help.sap.com/docs/SAP_S4HANA_CLOUD/2dfa044a255f49e89a3050daf3c61c11/6004e50b21d34a2088dddfd9b7f484b0.html
   (functional location),
   https://help.sap.com/docs/SAP_S4HANA_CLOUD/2dfa044a255f49e89a3050daf3c61c11/1797d08b0c71456398cb6224ff257378.html
   (equipment),
   https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/e98c7c41bbe8439e90daa5c114a7573b/a25db6531de6b64ce10000000a174cb4.html
   (maintenance-plan creation & scheduling) *(the S/4 doc pages render client-side; content taken from the
   indexed summaries)*.
3. **Oracle Fusion Cloud Maintenance** — maintenance *programs* that generate a PM forecast from calendar, meter,
   combined or condition-event methods; 360° asset view with meters, hierarchy, parts list, warranty and cost —
   https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25c/faumm/overview-of-maintenance-work-execution.html
   and https://docs.oracle.com/en/cloud/saas/readiness/scm/26a/maint26a/26A-maintenance-wn-f42290.htm
   *(oracle.com/scm/maintenance returned 403)*.
4. **Infor EAM / CloudSuite Asset Management** — one platform for asset health, criticality, financial and
   operational performance; the reactive → preventive → predictive → condition-based maturity curve; MRO and
   warranty recovery — https://www.infor.com/resources/industry-4.0-and-asset-maintenance and
   https://docs.infor.com/pub/11.1.x/en-us/useradminlib/pubworkug/cmo1441041051152.html (Work Management guide).
5. **Fiix CMMS (Rockwell Automation)** — https://fiixsoftware.com/cmms/asset-management-software/ — custom asset
   fields, drag-and-drop asset tree, criticality ratings, failure codes that trigger work orders, meter readings,
   downtime measurement, per-machine maintenance cost; parts forecaster at
   https://fiixsoftware.com/cmms/cmms-software/.
6. **UpKeep** — https://upkeep.com/product/asset-management/ — the most explicit on the finance seam: asset
   specs/serial/purchase/vendor, parent-child asset+location tree, health scoring and failure-mode analysis,
   downtime by asset/location/root cause, meters and runtime, **straight-line or declining-balance depreciation
   with finance-ready reports**, TCO including labour and parts, end-of-life candidate identification.
7. **Limble CMMS** — https://limble.com/products/asset-maintenance-management (hierarchy to component level,
   unplanned downtime per asset, cost of ownership + depreciation, labour/parts/invoice cost dashboard) and
   https://limble.com/products/spare-parts-inventory (part record = location + UoM + associated assets + work
   orders + vendors; min/max low-stock alerts; parts consumed through work orders; POs to the vendor or synced to
   the ERP; historical forecasting of parts needs).
8. **MaintainX** — https://www.getmaintainx.com/use-cases/equipment-and-asset-management (multi-layered asset
   hierarchy for cost attribution, downtime logged at the moment it occurs, full per-asset maintenance log of who
   did what with which parts, QR/barcode), plus
   https://www.getmaintainx.com/use-cases/work-order-management (requests → prioritised WOs, procedures/
   checklists, time tracking, parts state from assigned to issued, approvals) and
   https://www.getmaintainx.com/use-cases/preventive-maintenance (calendar, meter and condition triggers;
   per-meter insight over time; PM compliance + MTBF dashboards).
9. **eMaint CMMS (Fluke Reliability)** — https://www.emaint.com/asset-maintenance-software — make/model/serial/
   warranty/criticality, hierarchy by location/system/department, warranty expiry alerts, **depreciation tracking
   and remaining-useful-life estimation**, TCO = acquisition + accumulated maintenance spend + downtime cost,
   MTBF / PM completion rate / uptime %, sensor-triggered work orders
   (https://www.emaint.com/cmms/predictive-maintenance-software/).
10. **Odoo Maintenance** — https://www.odoo.com/app/maintenance — the closest analogue in scale to what NavERP
    ships: equipment records, *preventive vs corrective* requests on kanban + calendar, maintenance teams,
    auto-computed **MTBF, MTTR and expected next failure date**, and maintenance requests raised **directly from
    the work-center control panel**.

Independent comparisons used to separate table-stakes from differentiators:
https://reliamag.com/guides/best-cmms-software-2026/ (baseline = work orders, PM scheduling, asset tracking &
history, parts inventory, basic dashboards; differentiators = IoT depth, AI diagnostics, mobile/offline) and
https://www.tmasystems.com/blog/best-enterprise-asset-management-software (asset tracking, PM scheduling and work
order management present in *all ten* platforms compared).

---

## Feature catalog (4.13 only)

### Bullet 1 — Asset Registry ("database of all physical assets with specifications and location")

- **Asset master record** — code/tag, name, type/class, manufacturer, model, serial number, purchase date,
  purchase cost, supplier, commissioning date. · seen in: Maximo, SAP (Equipment), Oracle, Infor, Fiix, UpKeep,
  Limble, MaintainX, eMaint, Odoo (all 10) · priority: **table-stakes** · spine: **new table `scm.Asset`** (no
  `Asset` exists anywhere — grep-verified) · buildable now.
- **Multi-level asset hierarchy (site → system → machine → component)** — parent/child so a failure and its costs
  roll up. Limble maps "to component level"; MaintainX calls it multi-layered hierarchy "to pinpoint failures and
  attribute costs"; Fiix has a drag-and-drop asset tree; SAP splits it into functional location + installed
  equipment. · seen in: all 10 · priority: **table-stakes** · spine: self-FK `parent` on `scm.Asset` (the
  `Location.parent` precedent, `Locations.py:30`) · buildable now.
  *Design note:* SAP's two-object model (functional **location** where a machine sits vs. the **equipment**
  installed there) is already covered by `scm.Location` + `Asset.location` — one Asset table with a location FK
  and a parent FK gives both axes without a second master.
- **Asset ↔ physical location** — every product ties the asset to a site/room/bin. · **table-stakes** ·
  spine: **reuses `scm.Location`** (verified) — no new site/room table. Owning department → **reuses
  `core.OrgUnit`** (verified; `accounting.FixedAsset.location` already points there).
- **Custodian / responsible person / assigned team** — · seen in: Maximo, Infor, UpKeep, eMaint, Odoo
  (maintenance teams) · **common** · spine: **reuses `core.Party`** (+ `PartyRole` employee) — never a new
  technician table (L29; the `WorkCenter.supervisor` precedent, `WorkCenters.py:45`).
- **Criticality / business-impact rating** — drives work prioritisation and PM strategy. Fiix: "assign importance
  levels to assets for work prioritisation"; Infor manages "asset health, criticality, financial and operational
  performance"; eMaint stores criticality as a standard field. · **common** · spine: choices field on `Asset`
  (`critical / high / medium / low`) · buildable now.
- **Lifecycle status** — new / in service / under maintenance / idle / standby / retired / disposed. · seen in:
  Maximo, Infor, UpKeep, eMaint; mirrors `NavERP.md:1701` (11.3) · **table-stakes** · spine: `status` choices on
  `Asset`. Note `accounting.FixedAsset.status` is only {cip, active, disposed} — the *operational* states are a
  different vocabulary and belong here, not in the financial record.
- **Warranty terms + expiry alerting** — UpKeep stores warranty terms on the asset; eMaint raises warranty
  expiration alerts and holds claim documentation. · **common** · spine: `warranty_expires_on` date +
  `warranty_vendor` → `core.Party` on `Asset`; the **claim itself reuses the existing `scm.WarrantyClaim`
  [WTY-]** (verified) rather than a new claim table. Alerting is a derived chip, not a stored flag (the 4.12
  licence-expiry precedent).
- **QR / barcode asset tag** — Limble, MaintainX, Fiix, UpKeep all lead with scan-to-open. · **common** ·
  spine: a `tag_code` CharField on `Asset` (unique per tenant) — the *value* is buildable now and printable;
  camera scanning is **integration/later**.
- **Specifications / custom attributes** — capacity, voltage, rated output, compliance tags; every product
  supports user-defined fields. · **table-stakes in the market** · spine: a `specifications` TextField on `Asset`
  · buildable now; a real user-defined-field engine is **deferred** (it is 11.3's "Custom Attributes" bullet and
  a cross-cutting platform feature, not a 4.13 table).
- **Manuals / drawings / photos attached to the asset** — eMaint lists manuals, drawings, photos and inspection
  reports; Limble/MaintainX surface manuals on the mobile asset page. · **common** · spine: **reuses
  `core.Document`** (GenericForeignKey — `Document.py:15-18`) · buildable now.
- **Asset ↔ production work centre** — Odoo raises maintenance requests straight from the work-center control
  panel; Oracle maintains assets inside a maintenance-enabled organisation aligned to production. · seen in:
  Odoo, Oracle, Infor, Fiix (PLC/FactoryTalk) · priority: **differentiator (and the SCM-specific one)** ·
  spine: nullable FK to the verified **`scm.WorkCenter`** · buildable now. This is what makes 4.13 an *SCM*
  sub-module rather than a generic CMMS: taking a machine down for maintenance is a fact 4.8's schedule needs.
- **Asset ↔ supplier / manufacturer / service provider** — · **common** · spine: **reuses `core.Party`**.

### Bullet 2 — Preventive Maintenance ("scheduling of regular maintenance tasks to prevent breakdowns")

- **Calendar / fixed-interval PM schedule** — every day/week/month/N-days. · seen in: all 10 · **table-stakes** ·
  spine: **new table `scm.MaintenancePlan`** with an interval + next-due date · buildable now.
- **Meter- / usage-based PM** — service after N runtime hours, km, cycles, PSI. Oracle names the forecast methods
  outright: *calendar, meter, combined calendar+meter, condition event*; Maximo generates PM work orders "on a
  time and/or meter-based frequency"; MaintainX triggers on time used, mileage, temperature, pressure. · seen in:
  Maximo, SAP (counter plans), Oracle, Infor, Fiix, UpKeep, MaintainX, eMaint · **table-stakes** · spine:
  `trigger_type` + `meter_interval` + `next_due_reading` on `MaintenancePlan`, read against the asset's meter ·
  buildable now.
- **Combined calendar + meter (whichever comes first)** — · seen in: Oracle (explicit), Maximo, SAP · **common** ·
  spine: a `combined` value in `trigger_type`; due = min(date due, meter due) · buildable now.
- **Condition / event-triggered PM** — sensor threshold breach raises the work order (Maximo Condition Monitoring
  on gauge/characteristic meters; eMaint + Fluke sensors; UpKeep first-party IoT; Fiix failure codes that trigger
  WOs). · seen in: Maximo, Oracle, Infor, eMaint, UpKeep, Fiix, MaintainX · **common** · spine: a `condition`
  value in `trigger_type` + a threshold on the plan; the *reading* still arrives through the manual meter log
  this pass — **automatic sensor ingestion is integration/later**.
- **Floating vs. fixed next-due** — next due measured from *last completion* (floating) or from the fixed
  calendar regardless of when the last one closed (SAP expresses this with cycle/offset/shift factors). ·
  **common** · spine: a `schedule_basis` choice on the plan · buildable now — a two-value choice that avoids
  re-deriving the whole SAP shift-factor machinery.
- **Automatic work-order generation ahead of the due date** — SAP's *call horizon*, Oracle's PM *forecast*
  window, Maximo's PM generation, MaintainX's "automatically recurring work orders". · seen in: all 10 ·
  **table-stakes** · spine: `lead_time_days` + a `last_generated_on` stamp on the plan; a **generate action**
  that creates the maintenance work order and advances the plan · buildable now. Follow the 4.3 reorder-alert
  precedent: **propose/generate on an explicit action, never a silent background auto-post.**
- **Job plan / task list / procedure checklist** — Maximo *job plans* (with safety plans and permits), SAP *task
  lists*, MaintainX *procedures/templates*, Limble PM templates. · seen in: all 10 · **table-stakes** ·
  spine: child `MaintenancePlanTask` rows (sequence, description, expected value/response) copied onto the
  generated work order · buildable now. *Snapshot, don't reference* — the 4.9 `QualityInspection` precedent
  (`QualityInspections.py`): editing a plan must not rewrite a completed job's record.
- **Estimated duration + assigned technician/team** — · **common** · spine: `estimated_hours` + `assigned_to` →
  `core.Party`.
- **Spare parts required by the plan** — Maximo job-plan materials, Oracle work-definition parts list, Limble
  parts tied to PMs. · **common** · spine: the `AssetSparePart` link (below) supplies the candidate list; the
  actual reservation happens on the work order · buildable now.
- **PM forecast / due calendar** — "what is due in the next N days", Oracle's daily PM forecast. · seen in:
  Oracle, Maximo, SAP, MaintainX (calendar), Limble · **common** · spine: a **computed report page** over
  `MaintenancePlan` (the `scm:production_schedule` / `scm:mrp_report` / `scm:safety_stock_report` precedent —
  a bullet may be a report, not a CRUD list) · buildable now.
- **PM compliance % (completed on time ÷ scheduled)** — MaintainX reports planned-maintenance percentage,
  eMaint reports PM completion rate, Limble reports PM compliance. · **common** · spine: **derived** from
  work-order history — no stored column · buildable now.
- **Nested PMs / one PM across many assets** — Fiix nested PMs and multi-asset work orders. · **differentiator** ·
  spine: would need a plan↔asset M2M · **deferred** (one plan = one asset this pass; a fleet is N plans).

### Bullet 3 — Breakdown Maintenance ("logging of unplanned repairs and downtime tracking")

- **Maintenance request / notification intake** — an operator reports a fault; a planner turns it into a job.
  SAP splits *notification* from *order*; Maximo has service requests; MaintainX/Limble have work requests that
  managers convert. · seen in: all 10 · **table-stakes** · spine: **one** `scm.MaintenanceWorkOrder` table with a
  `requested` first status + a `reported_by` FK, **not** a second request table. Rationale: 4.9 made exactly this
  call for audit findings vs. NCRs (`navigation.py:859-868` — "audit findings are NCR rows with source='audit',
  not a second table"), and a split would fork every MTTR and downtime query.
- **Corrective / breakdown work order with priority, assignment and due date** — · seen in: all 10 ·
  **table-stakes** · spine: `work_type` ∈ {preventive, corrective, breakdown, inspection, calibration,
  predictive, safety} + `priority` + `assigned_to` → `core.Party` · buildable now.
  *A maintenance work order is NOT `scm.WorkOrder` [WO-].* The production run has `item`, `bom`,
  `quantity_planned`, `quantity_produced`, `component_location`/`output_location` (`WorkOrders.py:59-100`) —
  none of which a repair has — and `WorkOrder.status` is written only by the production actions. Overloading it
  would corrupt 4.8's MRP netting, load board and OEE. Separate document, separate prefix.
- **Downtime start/stop capture and unplanned-downtime totals** — Limble monitors each asset's unplanned
  downtime; MaintainX logs downtime "at the moment it occurs"; Fiix measures uptime/downtime for KPIs. ·
  seen in: all 10 · **table-stakes** · spine: `downtime_start` / `downtime_end` on the work order,
  `downtime_minutes` **derived in `save()`** (the `ProductionTimeLog.duration_minutes` precedent,
  `ProductionTimeLogs.py:102-115`) · buildable now.
- **MTBF / MTTR / availability per asset** — Odoo computes MTBF, MTTR *and an expected next-failure date*
  automatically; eMaint and Limble report MTBF; MaintainX dashboards PM compliance + MTBF. · seen in: Odoo,
  Limble, eMaint, MaintainX, Fiix, Maximo, Infor · **common** · spine: **derived** from the work-order history
  (failures counted, downtime summed) — never stored, matching `WorkCenter.oee_chip()` and 4.3's derived on-hand ·
  buildable now.
- **Failure coding: problem → cause → remedy** — Maximo's failure hierarchy (failure class, problem code, cause
  code, remedy code) is the canonical model; Fiix has custom failure codes that can trigger work orders. ·
  seen in: Maximo, SAP (damage/cause catalogs), Infor, Fiix · priority: **common** (a genuine differentiator
  among the SMB CMMS tools) · spine: three choice fields on the work order · buildable now. This is what makes
  the failure-analysis report possible without a sensor stack.
- **Labour time and labour cost on the job** — · seen in: all 10 · **table-stakes** · spine: `labour_hours` +
  `labour_rate` on the work order header, cost derived · buildable now. *Multi-technician per-interval labour
  logs are deferred* — 4.8 already proved that shape (`ProductionTimeLog`), and one job/one assignee covers the
  4.13 pass.
- **External contractor / third-party service with vendor and cost** — Infor tracks outsourced maintenance
  billing and SLAs; eMaint attaches purchase orders to work orders. · **common** · spine: `service_vendor` →
  `core.Party` + `external_cost` on the work order; the actual AP bill is **drafted into `accounting.Bill`**
  by a later pass, the `FreightInvoice.bill` precedent (`FreightInvoices.py:62-63`) — **deferred this pass**.
- **Meter reading captured at the moment of work** — Oracle prompts for mandatory readings on the work order. ·
  **common** · spine: an optional reading on the work order that writes a `MeterReading` row · buildable now.
- **Full per-asset maintenance history** — MaintainX: "what work was performed, who did the work, and which
  parts were used"; every product has this. · **table-stakes** · spine: **derived** — the work-order list
  filtered to the asset, rendered on the asset detail page · buildable now.
- **Repeat-failure root cause / corrective action** — · **common in EAM** · spine: **reuses the existing
  `scm.NonConformance` + `scm.CapaAction` (4.9)** by reference — 4.13 adds no RCA table.

### Bullet 4 — Spare Parts Inventory ("management of inventory required for machine maintenance")

> **The whole bullet is realised on 4.3's ledger.** Every leader's "parts" module is an item master + storeroom
> + min/max + issue-to-work-order + cost roll-up, and NavERP already has the first three.

- **MRO part record: UoM, storeroom location, vendor, cost** — Limble's part record is literally "location, unit
  of measure, associated assets, work orders, and vendors". · seen in: all 10 · **table-stakes** ·
  spine: **reuses `scm.Item` (+ `UOM`, `ItemCategory`) and `scm.Location`** — verified. **Do not create a
  `SparePart` table.** The only addition is an additive `is_spare_part` flag on `Item` so the MRO storeroom has
  its own list (precedent: 4.4 added bin attributes to `Location`, `Locations.py:34-36`; 4.7 extended
  `ReorderRule` in place, `ReorderRules.py:8-19`).
- **Real-time on-hand per storeroom** — · **table-stakes** · spine: **derived from `scm.StockMove`** —
  `Item.on_hand(location)` already exists (`Items.py:107-116`) · buildable now, zero new code.
- **Min/max levels with low-stock alerts and reorder** — Limble triggers "the reorder process before you run
  out"; eMaint alerts when parts need reordering; Maximo automates reorder points; MaintainX notifies escalation
  teams. · seen in: all 10 · **table-stakes** · spine: **reuses `scm.ReorderRule`** + 4.3's existing reorder-alerts
  report and its one-click hand-off into 4.1's requisition (`ReorderRules.py:1-6`) · buildable now, zero new code.
- **Parts associated with specific assets (the asset's spare-parts list)** — Maximo asset spare-parts list, Oracle
  360° asset "parts list", Limble "associated assets", Fiix parts consumption per machine. · seen in: Maximo,
  Oracle, Infor, Fiix, Limble, UpKeep, eMaint · priority: **common** · spine: **new small join
  `AssetSparePart`** (asset × item, qty per service, `is_critical`) — a child of `Asset`, not a new master ·
  buildable now.
- **Parts reserved → issued against a work order, consumption tracked** — MaintainX shows "where every part
  stands on a work order from assigned to issued" and warns before work starts if parts are missing; Limble
  "connect parts directly to work orders and track inventory in real time as it's used". · seen in: all 10 ·
  **table-stakes** · spine: child `MaintenanceWorkOrderPart` (item, quantity, unit_cost) + an **issue action
  posting a negative `StockMove` through the existing `_post_stock_move()` service**
  (`apps/scm/views/_helpers.py:130-151`).
  **⚠ Requires a new `move_type` value, `maintenance`.** Verified constraint: `analytics.py:177` puts both
  existing outbound types in `COGS_MOVE_TYPES`, and `analytics.py:1949`/`2529` read `issue` as customer demand
  for 4.7's forecasts. Posting MRO draws as `issue` would inflate every forecast; posting them as `consumption`
  would inflate COGS in 4.11's margin analytics. The new type **must stay out of `COGS_MOVE_TYPES`** (maintenance
  is opex, not cost of goods) while still participating in the FIFO/LIFO layer walk and aging, which exclude only
  `transfer` (`StockMoves.py:1-9`, `analytics.py:1054`).
- **Parts cost rolling into the asset's maintenance cost** — Limble dashboards labour + parts + invoice cost per
  asset; UpKeep rolls parts and labour into TCO. · **table-stakes** · spine: **derived** from the part lines ×
  their posted `unit_cost` · buildable now.
- **Purchase order for parts / vendor reorder** — Limble creates POs and sends them to the vendor or syncs to the
  ERP; eMaint involves purchasing in the WO workflow. · **common** · spine: **reuses 4.1's
  `PurchaseRequisition` → `RFQ` → `PurchaseOrder` → `GoodsReceiptNote`** (verified, `ProcurementManagement/`) —
  4.13 adds **no** purchasing document. NavERP already routes reorder alerts into `requisition_create`.
- **Parts-need forecasting from the PM schedule** — Fiix's parts forecaster predicts parts for upcoming work;
  Limble forecasts inventory needs from historical data. · **differentiator** · spine: a computed "parts required
  by PMs due in N days" section on the PM forecast page · **deferred to a later pass** (it needs plan-level parts,
  which the `AssetSparePart` link only approximates).
- **Barcode scanning of parts, multi-site parts transfer** · **common** · spine: transfers **reuse
  `scm.StockTransfer`** (verified); scanning is **integration/later**.

### Bullet 5 — Asset Depreciation ("financial tracking of asset value over time")

> **`accounting.FixedAsset` already does this and owns the posting (L29).** 4.13 must not build a second
> depreciation ledger. Its job is the *link* and the *operational* cost view around it.

- **Straight-line / declining-balance / units-of-production, accumulated depreciation, book value** —
  UpKeep computes "straight-line or declining balance" with finance-ready reports; eMaint tracks depreciation and
  remaining useful life; Limble surfaces "cost of ownership, depreciation". · seen in: Maximo, SAP, Oracle,
  Infor, UpKeep, Limble, eMaint · **table-stakes** · spine: **ALREADY EXISTS —
  `accounting.FixedAsset.method`/`acquisition_cost`/`salvage_value`/`useful_life_months`/
  `accumulated_depreciation`/`book_value()`/`period_depreciation()`** (verified, `FixedAssetsRegister.py:12-69`) ·
  **nothing to build.**
- **Depreciation posted to the GL (Dr expense / Cr accumulated)** — · **table-stakes** · spine: **accounting owns
  it** — `asset_account`/`accumulated_account`/`expense_account` and the `depreciation_run` action already exist.
  **SCM posts no JournalEntry** (the standing 4.9/4.10/4.11/4.12 rule, `navigation.py:864-868`, `:901-905`,
  `:925-928`).
- **Linking the operational asset to its financial fixed asset** — Oracle Maintenance assets tie to Fusion
  Financials; SAP equipment ties to FI-AA; Maximo tracks cost from procurement to decommissioning. · seen in:
  Maximo, SAP, Oracle, Infor · priority: **table-stakes for a suite** (the SMB CMMS tools fake it with a local
  depreciation field — the *wrong* pattern here) · spine: **nullable FK `accounting.FixedAsset`** on `scm.Asset`,
  by string (the `SalesOrder.invoice` / `GoodsReceiptNote.bill` precedent) · buildable now.
- **Total cost of ownership = acquisition + accumulated maintenance spend (+ downtime cost)** — eMaint states the
  formula outright; UpKeep's TCO reflects labour and parts; Limble's dashboard splits labour/parts/invoice cost. ·
  seen in: eMaint, UpKeep, Limble, Fiix, Maximo, Infor · **common** · spine: a **computed report page** joining
  `accounting.FixedAsset` (cost, accumulated depreciation, book value) with 4.13's maintenance work-order costs ·
  buildable now. This is the honest realisation of the bullet inside SCM: SCM contributes the *maintenance* half
  of the number and reads the *financial* half.
- **Repair-vs-replace / end-of-life candidates** — UpKeep identifies end-of-life candidates; eMaint drives
  "equipment replacement and capital planning"; Limble flags "which assets are draining resources". ·
  **common** · spine: a derived flag on the same TCO report (maintenance-spend-to-book-value ratio, over a
  threshold, with the arithmetic shown — the 4.11 explainability rule, `navigation.py:902-905`) · buildable now.
- **Revaluation, impairment, tax vs. book depreciation, disposal accounting** — · **table-stakes in EAM
  finance** · spine: **park** — `accounting.AssetDisposal` exists and 11.4 / 2.6 own the rest. Not an SCM table.

### Beyond the bullets (strong features NavERP.md's five bullets don't name)

- **Meter / reading log with history** — Maximo distinguishes three meter kinds (**continuous** runtime, **gauge**
  measurement, **characteristic** observation) and drives both PM and condition monitoring from them; Oracle
  supports meter templates mass-associated to assets and updated from IoT; MaintainX gives per-meter insight over
  time; Fiix and UpKeep track runtime readings. · seen in: Maximo, Oracle, Infor, Fiix, UpKeep, MaintainX,
  eMaint · priority: **table-stakes for meter-based PM** · spine: **new append-only table `scm.MeterReading`**
  (asset, meter name/unit, value, read_at, source) — a reading *history* is what makes meter-based due dates,
  usage trends and condition triggers possible; a single `current_reading` column on `Asset` cannot produce them
  and would drift. Same append-only philosophy as `StockMove`.
- **Maintenance scheduling / dispatch board** — a calendar or kanban of upcoming and open jobs (Odoo's kanban +
  calendar views, MaintainX's calendar, Maximo's assignment manager). · **common** · spine: a computed page over
  the work-order list (the `scm:production_schedule` precedent) · buildable now — **fold into the PM forecast
  page** this pass rather than adding a sixth destination.
- **Condition monitoring / IoT sensor ingestion with threshold alerts** — Maximo Condition Monitoring, eMaint +
  Fluke sensors, UpKeep first-party sensors, Fiix + Rockwell PLCs, Tractian's bundled hardware. · seen in: most
  leaders · **differentiator** · spine: the `MeterReading.source` field leaves the seam open · **integration/
  later** (and 11.7 owns it).
- **AI/predictive failure diagnostics** — Fiix Foresight, MaintainX AI procedures, Tractian failure-mode AI. ·
  **differentiator** · **deferred** — Module 10.13 owns ML, and 4.11 set the precedent that SCM ships explainable
  arithmetic, never a page that says "AI" (`navigation.py:902-905`).
- **Mobile/offline technician execution with signatures** — the single loudest differentiator in the CMMS market
  (MaintainX, Limble, UpKeep, Fiix all lead with it). · **out of scope** — NavERP is server-rendered Django +
  HTMX; the responsive templates are the answer, a native offline app is not a 4.13 model.
- **Safety plans, permits-to-work, LOTO attached to the job** — Maximo embeds safety plans, permits and risk
  assessments in job plans. · **common in enterprise EAM** · **deferred** (11.11 / HSE); the task-list child
  table can carry safety steps as tasks in the meantime.

---

## Recommended build scope (this pass — 4 models + 2 computed report pages)

Same envelope as 4.8/4.9/4.10 (4 primary entities; child line models are **not** counted as separate entities,
per the `PurchaseOrder`/`PurchaseOrderLine` and `QualityInspection`/`InspectionResult` precedent).

1. **`Asset`** `[AST-]` — `models/AssetManagement/Assets.py` — *the registry bullet.*
   - Justified by: asset master record · hierarchy · location · custodian · criticality · lifecycle status ·
     warranty expiry · QR tag · specifications · work-centre link · financial link.
   - Fields: `code` (unique per tenant), `name`, `asset_type` choices (machine / vehicle / forklift / conveyor /
     rack / tool / facility / it_equipment / other), `category` (FK `scm.ItemCategory`? **no** — a plain
     CharField or a `parent`-driven grouping; do not overload the item taxonomy), `manufacturer`, `model_number`,
     `serial_number`, `tag_code`, `specifications` (Text), `criticality` choices, `status` choices
     (planned / in_service / under_maintenance / standby / idle / retired / disposed), `commissioned_on`,
     `purchase_cost`, `warranty_expires_on`, `meter_name` + `meter_unit` (the asset's primary meter definition),
     `is_active`, `notes`.
   - **Verified FKs:** `parent` → self · `location` → `scm.Location` · `org_unit` → `core.OrgUnit` ·
     `work_center` → `scm.WorkCenter` (nullable — the SCM differentiator) · `custodian`, `supplier`,
     `service_vendor` → `core.Party` · **`fixed_asset` → `accounting.FixedAsset` (nullable, string FK)** —
     the depreciation link, never a second depreciation ledger.
   - Child: **`AssetSparePart`** (tenant-less, reached through its asset) — `item` → `scm.Item`,
     `quantity_per_service`, `is_critical`, `notes`.
   - Derived, never stored: MTBF, MTTR, availability %, downtime hours, maintenance-cost-to-date, open-job count,
     next-PM-due, book value (read from `fixed_asset`).

2. **`MaintenancePlan`** `[PM-]` — `models/AssetManagement/MaintenancePlans.py` — *the preventive bullet.*
   - Justified by: calendar PM · meter PM · combined · condition trigger · floating vs fixed · lead-time
     generation · job plan/task list · estimated hours · assigned technician.
   - Fields: `name`, `trigger_type` choices (calendar / meter / combined / condition), `interval_days`,
     `meter_interval`, `condition_threshold` + `condition_operator`, `schedule_basis` choices (fixed / floating),
     `lead_time_days`, `next_due_on`, `next_due_reading`, `last_completed_on`, `last_generated_on`
     (editable=False), `estimated_hours`, `priority`, `instructions`, `is_active`.
   - **Verified FKs:** `asset` → `scm.Asset` · `assigned_to` → `core.Party`.
   - Child: **`MaintenancePlanTask`** — `sequence`, `description`, `expected_result`, `is_mandatory`.
   - Action: **generate work order** — creates a `MaintenanceWorkOrder`, **snapshots** the tasks onto it, advances
     `next_due_on`/`next_due_reading`, stamps `last_generated_on`. Explicit action, inside `transaction.atomic()`,
     never a silent background post.

3. **`MaintenanceWorkOrder`** `[MWO-]` — `models/AssetManagement/MaintenanceWorkOrders.py` — *the breakdown
   bullet, and the execution record for PM too.*
   - Justified by: request intake · corrective/breakdown job · priority + assignment · downtime capture ·
     failure coding · labour hours/cost · external service · meter reading at work · parts issued · full history.
   - Fields: `work_type` choices (preventive / corrective / breakdown / inspection / calibration / predictive /
     safety), `source` choices (plan / request / condition / inspection), `title`, `description`, `priority`
     choices, `status` choices (requested / approved / scheduled / in_progress / on_hold / completed / closed /
     cancelled — `editable=False`, driven by verb actions like 4.8's `WorkOrder.status`), `reported_at`,
     `scheduled_start`, `started_at`, `completed_at`, `downtime_start`, `downtime_end`, `downtime_minutes`
     (**derived in `save()`**, `editable=False`), `is_unplanned_downtime`, `problem_code` / `cause_code` /
     `remedy_code` choices (Maximo failure hierarchy), `labour_hours`, `labour_rate`, `external_cost`,
     `meter_reading_at_work`, `resolution_notes`.
   - **Verified FKs:** `asset` → `scm.Asset` · `plan` → `scm.MaintenancePlan` (nullable) · `reported_by`,
     `assigned_to`, `service_vendor` → `core.Party` · `parts_location` → `scm.Location` (the storeroom parts are
     drawn from) · optional `non_conformance` → `scm.NonConformance` (4.9 escalation, by reference).
   - Children: **`MaintenanceWorkOrderPart`** (`item` → `scm.Item`, `lot_serial` → `scm.LotSerial`, `quantity`,
     `unit_cost`, `is_issued`) and **`MaintenanceWorkOrderTask`** (the snapshotted checklist + completion state).
   - **Issue-parts action** → `_post_stock_move(..., move_type="maintenance", quantity=-qty,
     reference=<MWO number>)` via the existing service in `apps/scm/views/_helpers.py`. Guard with the existing
     `_insufficient_stock()` helper.
   - Derived: total cost = parts + labour + external; MTTR contribution; PM-on-time flag.

4. **`MeterReading`** — `models/AssetManagement/MeterReadings.py` — *append-only, no prefix* (a log row like
   `StockMove`; `TenantOwned`, not `TenantNumbered`).
   - Justified by: meter-based PM due dates · condition triggers · usage trend · Oracle's mandatory reading at
     work · MaintainX per-meter insight.
   - Fields: `meter_name`, `unit`, `reading` (Decimal), `read_at`, `source` choices (manual / work_order /
     sensor), `reference` (the MWO number when captured on a job), `notes`.
   - **Verified FKs:** `asset` → `scm.Asset` · `recorded_by` → `core.Party`.
   - Never edited/deleted (the `StockMove` rule) — a wrong reading is corrected by a later reading.

**Additive changes to existing verified models (no new tables):**
- `scm.Item` += `is_spare_part` (BooleanField, default False) — and only that. Precedent: 4.4 added bin
  attributes to `Location`; 4.7 extended `ReorderRule`. Everything else the MRO storeroom needs (UoM, category,
  costing, on-hand, average cost) already exists.
- `scm.StockMove.MOVE_TYPES` += `("maintenance", "Maintenance")` — outbound MRO draw.
  **`apps/scm/analytics.py:177` `COGS_MOVE_TYPES` must NOT be changed** — maintenance parts are opex, not COGS.
  Add a one-line comment there recording the decision so a future sweep doesn't "fix" the omission.

**Computed report pages (no models):**
- **`scm:pm_forecast`** — PM due in the next N days (overdue / due today / due soon), with the generate-work-order
  hand-off and the open-job board folded in.
- **`scm:asset_depreciation_report`** — per asset: acquisition cost, accumulated depreciation and book value read
  from the linked `accounting.FixedAsset`, plus maintenance spend to date and a shown-arithmetic
  repair-vs-replace ratio. States on the page that the statutory depreciation figures and their GL postings
  belong to `apps.accounting` (L29) — SCM only reads them.

**Suggested `LIVE_LINKS["4.13"]` — one key per NavERP.md bullet, five bullets, five keys:**
| Bullet | Target |
|---|---|
| Asset Registry | `scm:asset_list` |
| Preventive Maintenance | `scm:maintenanceplan_list` |
| Breakdown Maintenance | `scm:maintenanceworkorder_list` (the full list, unfiltered — the 4.7 "Collaborative Planning" rationale at `navigation.py:843-846`) |
| Spare Parts Inventory | `scm:sparepart_list` (computed page over `Item(is_spare_part=True)` with derived on-hand, `ReorderRule` min/max and maintenance consumption) |
| Asset Depreciation | `scm:asset_depreciation_report` |

`MeterReading` and `AssetSparePart` take **no sidebar key** — they are reached from the asset detail page (the
`WorkCenter` / `ReorderRule` / `InspectionPlan` / `ReturnReason` / `KpiTarget` precedent).

**If the pass must shrink to 3 models:** drop `MeterReading` and keep a `current_meter_reading` +
`meter_read_at` pair on `Asset`. Cost: meter-based PM still works, but the usage trend and condition history are
lost and the field becomes a mutable number with two writers — the exact drift 4.3/4.8 were built to avoid. Keep
the four if at all possible.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Warranty claim submission, supplier recovery, credit** → **4.10** — `scm.WarrantyClaim` [WTY-] already exists
  with typed cost lines. 4.13 stores the warranty *expiry* on the asset and links out; it adds no claim table.
- **Root-cause analysis, corrective/preventive action, repeat-failure investigation** → **4.9** —
  `NonConformance` + `CapaAction`. 4.13 links by reference only.
- **Purchasing spare parts (requisition → RFQ → PO → GRN, three-way match)** → **4.1**. No purchasing document
  here.
- **Vendor qualification, service-provider scorecards, maintenance-vendor risk** → **4.2** — `SupplierProfile`,
  `SupplierScorecard`, `SupplierRiskAssessment`.
- **Stock on hand, storeroom transfers, cycle counting of the parts crib, FIFO/LIFO/WAC valuation** → **4.3**
  (and 4.4 for the count tasks). 4.13 reads them.
- **Production capacity, OEE decomposition, shop-floor time booking** → **4.8** — `WorkCenter.oee_chip()` and
  `ProductionTimeLog` already exist. 4.13 supplies the *asset* view of downtime, not a second OEE engine.
- **Maintenance-service contracts and SLAs with third parties** → **4.12 / 4.2** — `SupplierContract` [SC-]
  already carries type (incl. sla), status, dates, value and the renewal window.
- **Fleet/vehicle telematics, driver assignment, fuel** → **4.6** for the transport leg, **11.19** for fleet
  asset management proper.
- **Reefer / cold-storage unit maintenance schedules** → **4.15** ("Maintenance of Reefers" is 4.15's own
  bullet, `NavERP.md:836`). 4.13's plans are generic enough that 4.15 reuses them rather than forking.
- **Labour scheduling and technician productivity measurement** → **4.14**.
- **Fleet/asset uptime and maintenance-cost dashboards across the whole supply chain** → **4.11** (which parked
  them here at `research-scm-4.11.md:514`); the 4.13 pages are per-asset operational views, and 4.11 can add a
  cross-asset KPI later without a new table.
- **Full EAM: check-in/check-out tool crib, physical verification audits, FMEA/RCM, lease & rental, ITAM,
  space & facility assets, asset disposal accounting** → **Module 11** (11.2, 11.7, 11.9, 11.10, 11.17, 11.18).
  4.13 ships the operational spine those sub-modules extend — it does not pre-build them.
- **Depreciation posting, revaluation, impairment, disposal journals, tax vs. book schedules** → **accounting
  2.6 / 11.4**. SCM posts no `JournalEntry`.

---

## Deferred (later passes / integrations)

- **IoT / sensor ingestion and automatic condition alerts** — every leader has it (Maximo Condition Monitoring,
  eMaint+Fluke, UpKeep sensors, Fiix+Rockwell). Needs an external feed; `MeterReading.source="sensor"` and the
  plan's `condition` trigger leave the seam open. **Integration/later.**
- **Predictive/AI failure diagnostics and expected-next-failure dates** — Odoo computes a next-failure estimate
  from MTBF, which is the one piece that *is* cheap; the rest (Fiix Foresight, Tractian) is Module 10.13.
  Consider the MTBF-derived estimate as a derived chip in a follow-up pass.
- **Multi-technician labour intervals per job** — the `ProductionTimeLog` shape applied to maintenance. One
  assignee + header hours covers this pass.
- **Nested / multi-asset PM plans and PM route sheets** (Fiix) — needs a plan↔asset M2M.
- **Parts-need forecasting from the PM schedule** (Fiix parts forecaster, Limble bulk-buy forecast) — needs
  plan-level parts lists; revisit once `MaintenancePlanTask` and `AssetSparePart` have real data.
- **Drafting an `accounting.Bill` for external contractor cost** — the `FreightInvoice.bill` pattern is proven
  and small, but it is a second hand-off in a pass that already has one (`accounting.FixedAsset`). Next pass.
- **Auto-creating a `PurchaseRequisition` from a maintenance parts shortage** — 4.3's reorder-alert hand-off
  already exists for the storeroom; wiring it from an individual work order is a follow-up.
- **QR/barcode scanning, mobile offline execution, digital signatures** — the loudest CMMS differentiators, all
  client-side. `tag_code` is stored now; scanning is later.
- **User-defined custom fields on assets** — every product has them; a real UDF engine is a platform feature
  (11.3), not a 4.13 table. `specifications` Text covers the need this pass.
- **Calibration certificates, as-found/as-left values, out-of-tolerance impact** — parked here by
  `research-scm-4.9.md:581`; `work_type="calibration"` reserves the slot, the certificate model lands with 11.7
  or 12.10.
- **Safety plans, permits-to-work, LOTO** — Maximo embeds them in job plans; the task checklist carries them as
  steps until 11.11 exists.
- **Asset depreciation *forecast* schedule (period-by-period table)** — belongs to accounting 2.6's backlog, not
  to SCM.

# Research - Module 3: HRM, Sub-module 3.33 Asset Management (hrm)

## Scope note - what already exists

Before proposing anything new, the existing HRM asset code was read (`apps/hrm/models.py`):

- **`AssetAllocation`** (NUMBER_PREFIX `"AST"`, built for 3.3 Onboarding) is already a full per-employee
  issuance record: `employee` FK, `asset_name` (free text), `asset_category` (choices: laptop/desktop/
  phone/id_card/access_card/uniform/vehicle/sim/other), `serial_number`, `asset_tag`, `status`
  (pending/issued/returned/lost/damaged), `issued_at`/`issued_by`, `returned_at` (system-set),
  `return_due_date`, `notes`, optional `program` FK (nullable so it also serves ad-hoc issuance and
  offboarding returns). Its own code comment already flags the gap this research closes: *"add
  `asset = models.ForeignKey('assets.Asset', ...)` in a later migration once the module exists."*
  This means the **"Asset Allocation" and "Asset Return" bullets of 3.33 are already largely built** -
  issue-to-employee, return-due-date, returned-at timestamp, lost/damaged states are all there.
- **`AssetRequest`** (NUMBER_PREFIX `"ASSETREQ"`, built for 3.26) is the employee-request -> approval ->
  fulfil-into-`AssetAllocation` workflow. Also already built, out of scope to rebuild.
- **Module 11 "Asset Management System"** (`apps/assets`, prefix `AST-` per NavERP.md's own convention) is
  the future **enterprise-wide, cross-department** fixed-asset/EAM/CMMS module (procurement, depreciation
  schedules, maintenance work orders, facilities, mobile/RFID, software licensing - see NavERP.md 11.1-11.18).
  It does **not exist yet** (`apps/assets/` is not present in the repo). HRM 3.33 is deliberately the
  **HR-facing slice**: a lightweight asset register + maintenance + depreciation scoped to equipment issued
  to employees, not a full EAM. When Module 11 is eventually built, 3.33's `Asset` register is the natural
  seed to migrate/link into the enterprise `assets.Asset` model (mirroring how `AssetAllocation` was always
  meant to gain an `assets.Asset` FK).
- **Prefix collision to avoid:** `AssetAllocation` already owns `NUMBER_PREFIX = "AST"`. NavERP.md also
  reserves `AST-` conceptually for Module 11's future `Asset` model. 3.33's new central register therefore
  needs its **own, non-colliding prefix** - recommend `ASSET` (i.e. `ASSET-00001`) for the new `Asset` model,
  and `ASSETMNT` for the new maintenance model, keeping `AST-` free for Module 11 later.

## Leaders surveyed (with source links)

1. **Snipe-IT** - open-source, lightweight IT asset tracker built around check-in/check-out to a person,
   asset models, and license/warranty alerting - https://snipeitapp.com/features
2. **Asset Panda** - configurable, workflow-driven asset platform (IT + facilities + ops) with mobile
   barcode/QR scanning and audits - https://www.assetpanda.com/product/features/ (fetch was blocked by a
   404 on the specific URL; confirmed positioning via https://www.g2.com/compare/asset-panda-vs-snipe-it
   and https://www.assetpanda.com/resource-center/compare/best-it-asset-management-software-top-itam-platforms-compared/)
3. **Freshservice (Freshworks) Asset Management** - ITSM-integrated ITAM with configurable depreciation
   (straight-line / declining-balance / sum-of-years-digits), vendor+warranty tracking, utilization/
   depreciation reporting - https://freshservice.com/it-asset-management/asset-lifecycle-management ,
   https://support.freshservice.com/support/solutions/articles/196934-adding-depreciation-to-assets-in-freshservice
4. **EZOfficeInventory (EZO AssetSonar)** - end-to-end lifecycle (procurement -> disposal), automatic
   straight-line/declining-balance depreciation, maintenance tickets with recurring service cycles,
   custodian-acknowledgement audits - https://ezo.io/ezofficeinventory/features/ ,
   https://ezo.io/ezofficeinventory/blog/asset-lifecycle-management/
5. **ManageEngine AssetExplorer** - ITAM with discovery, fixed-asset register, multi-method depreciation
   (acquisition cost + useful life -> current value), contract/warranty-expiry notifications -
   https://www.manageengine.com/products/asset-explorer/features.html ,
   https://blog.invgate.com/best-it-asset-management-software-with-depreciation-tracking
6. **GoCodes** - QR-code-first asset tracking: scan-to-check-out/in with GPS+timestamp, return-date email
   reminders, maintenance/status alerts on scan - https://gocodes.com/features/ ,
   https://gocodes.com/how-to-use-gocodes-to-check-in-and-out-assets/
7. **Zoho AssetExplorer / Zoho Creator IT Asset Tracker** - hardware+software asset discovery, license
   compliance, lease/contract management, barcode/QR scan-to-import -
   https://www.zoho.com/creator/apps/it-asset-tracker-management-software.html ,
   https://www.zoho.com/creator/decode/7-best-it-asset-management-software-today
8. **ServiceNow ITAM (Hardware Asset Management)** - enterprise lifecycle Request > Order > Receive >
   Deploy > Use > Maintain > Retire on a CMDB, automated purchase-order triggers, compliance/patch-status
   tracking - https://www.servicenow.com/products/hardware-asset-management.html ,
   https://www.itechag.com/insights/all-about-the-assets-managing-the-it-asset-lifecycle-in-servicenow/
9. **UpKeep** - mobile-first CMMS: work orders, preventive-maintenance schedules (meter/usage-triggered),
   full asset lifecycle with maintenance history + warranties + depreciation + real-time health -
   https://upkeep.com/product/cmms-software/ , https://upkeep.com/
10. **Keka HR** - HRMS-native asset module: assign assets from the asset list or the employee profile,
    a scoped "Asset Manager" role (by location/department/business unit), damage-charge-back to employee,
    acknowledgement request on assignment - https://help.keka.com/admin/assigning-assets ,
    https://help.keka.com/admin/managing-assets

(General AMC-market pattern, not tied to one vendor above, confirmed via
https://safetyculture.com/apps/annual-maintenance-contract-management-software and
https://www.makula.io/learning-center/annual-maintenance-contract-amc : AMC = a recurring service
contract per asset with a start/end date, a vendor, an automatic renewal/expiry alert, and a linked
service-visit schedule.)

## Feature catalog by 3.33 bullet

### Asset Register (laptops, phones, equipment inventory)
- **Asset tag + serial number + name/model/manufacturer** - the core identity fields of every register
  row · seen in: Snipe-IT, Asset Panda, ManageEngine AssetExplorer, Zoho AssetExplorer, EZOfficeInventory
  · priority: table-stakes · spine: mostly already on `AssetAllocation` (asset_name, serial_number,
  asset_tag) - the NEW `Asset` register needs to be the single source of truth these values live on ·
  buildable now.
- **Asset category / type taxonomy** - laptop/desktop/phone/monitor/furniture/vehicle/etc. grouping for
  reporting and filtering · seen in: all 10 · priority: table-stakes · spine: reuse
  `AssetAllocation.ASSET_CATEGORY_CHOICES` verbatim on the new `Asset` model (same precedent `AssetRequest`
  already follows) · buildable now.
- **Purchase date + purchase cost + vendor** - acquisition record, feeds depreciation and warranty math ·
  seen in: EZOfficeInventory, ManageEngine AssetExplorer, Freshservice, ServiceNow ITAM · priority:
  table-stakes · spine: new fields on `Asset`; vendor could optionally reuse `core.Party` (role=vendor) but
  a plain text/optional-FK field is enough for this pass · buildable now.
- **Warranty expiry date + alerts** - tracked per asset, drives renewal/replace decisions · seen in:
  Snipe-IT ("email alerts for expiring warranties/licenses"), Freshservice, ManageEngine AssetExplorer ·
  priority: common · spine: new field `warranty_expiry` on `Asset`; the *alert/notification* mechanism is
  integration/later (email digest), the *field + "expiring soon" filter/badge* is buildable now.
- **Lifecycle / status field** - in_stock, assigned, in_repair, retired, disposed (ServiceNow's fuller
  Request>Order>Receive>Deploy>Use>Maintain>Retire collapses to this set for an HR-facing register) · seen
  in: ServiceNow ITAM, EZOfficeInventory ("Availability Calendar: available/reserved/checked out/under
  maintenance"), Snipe-IT (deployed/pending/ready/archived) · priority: table-stakes · spine: new `status`
  choice field on `Asset`, kept in sync with `AssetAllocation.status` transitions (issue -> assigned,
  return -> in_stock, maintenance -> in_repair) · buildable now.
- **Current holder / current location** - who has it and where, denormalized onto the asset for fast
  lookup rather than always joining allocation history · seen in: Snipe-IT, Asset Panda, GoCodes (GPS/
  location on every scan) · priority: common · spine: `current_holder` = FK to `hrm.EmployeeProfile`
  (nullable), `location` = FK to `core.OrgUnit` (reuse the existing company/branch/department hierarchy
  rather than a new locations table) · buildable now.
- **Custom fields per asset type** - flexible attribute sets (Snipe-IT "Asset Models", Asset Panda
  "Smart Forms") · seen in: Snipe-IT, Asset Panda · priority: differentiator · spine: would need an
  EAV-style side table · integration/later (out of scope for this pass - a free-text `notes`/`specs`
  field covers the 80% case now).
- **Barcode/QR code generation and scan-to-check-in/out** - printable labels, scan with phone camera, no
  extra app · seen in: GoCodes (core value prop), Snipe-IT, EZOfficeInventory, Zoho AssetExplorer ·
  priority: differentiator · spine: n/a · integration/later (needs label rendering + a scan endpoint;
  park it, the `asset_tag` text field is the seed for it).
- **Network/software discovery (auto-inventory)** - agentless/agent scanning of the network to
  auto-populate hardware+software inventory · seen in: ManageEngine AssetExplorer, ServiceNow ITAM, Zoho
  AssetExplorer · priority: differentiator (enterprise-only tier of feature) · spine: n/a · integration/
  later - out of scope for an HR-facing register entirely.
- **Software license management** - license entitlement, seat usage, compliance % · seen in: Zoho
  AssetExplorer, ManageEngine AssetExplorer, Snipe-IT (dedicated license module) · priority: common (for
  IT-specific tools) but **out of scope for 3.33** per module framing (that's Module 11.18 ITAM territory)
  · integration/later.

### Asset Allocation (assign to employees) - mostly already built
- **Check-out to a named employee with acknowledgement/signature** - core workflow of every product ·
  seen in: all 10, explicitly Snipe-IT ("digital signatures on acceptance"), Keka ("Request
  Acknowledgment from the employee"), EZOfficeInventory ("custodians acknowledge ownership") · priority:
  table-stakes · spine: **already built** as `AssetAllocation.issued_at/issued_by/employee`; 3.33 adds a
  bool "acknowledged" is a nice-to-have but out of scope this pass · buildable now (just needs the `asset`
  FK wired per the code NOTE).
- **Asset-manager scoping (by location/department)** - a role that can only see/allocate assets for their
  scope · seen in: Keka ("Asset Manager... limited scope such as a location, department, business unit")
  · priority: differentiator · spine: would layer on top of existing tenant + role permissions ·
  integration/later (permissions work, not a new model).
- **Reservation / availability calendar** - block out an asset as reserved before checkout · seen in:
  EZOfficeInventory · priority: differentiator · integration/later.
- **Condition-at-assignment tracking** - record asset condition (new/good/fair/damaged) at the moment of
  checkout, used later to detect damage-in-custody · seen in: Keka ("update the Asset Condition") ·
  priority: common · spine: new small field on `Asset` (`condition`) captured at allocation time; cheap
  to add now.
- **Damage charge-back to employee** - bill the employee/payroll for damage found on return · seen in:
  Keka · priority: differentiator · spine: would hook into HRM 3.34 Expense/payroll deduction · integration/
  later (needs payroll-deduction wiring, not this pass).

### Asset Return (track returns during offboarding) - mostly already built
- **Return with due-date + overdue tracking** - already exactly what `AssetAllocation.return_due_date` +
  `returned_at` gives you · seen in: GoCodes ("return dates with email reminders for overdue items"),
  Snipe-IT · priority: table-stakes · spine: **already built**; 3.33 only needs to flip `Asset.status`
  in_repair/assigned <-> in_stock when `AssetAllocation.returned_at` is set · buildable now.
- **Offboarding clearance integration** - asset return as a checklist item inside a broader offboarding
  clearance flow · seen in: general HR-suite pattern (Keka, BambooHR-style clearance checklists), not a
  single-vendor differentiator · priority: table-stakes for an HR suite · spine: **already built** in HRM
  3.30/3.31 offboarding (`ClearanceItem` et al. per the repo's own onboarding/offboarding submodules) - 3.33
  just needs `Asset`/`AssetAllocation` to be the system of record those clearance items point at ·
  buildable now (wiring only, no new model).
- **Lost/damaged disposition at return** - already on `AssetAllocation.STATUS_CHOICES` (lost/damaged) ·
  seen in: Snipe-IT, Asset Panda · priority: table-stakes · spine: already built; 3.33 maps
  lost/damaged -> `Asset.status` in_repair or retired · buildable now.

### Maintenance (service schedules, AMC tracking)
- **Maintenance ticket/record per asset** - type (preventive/repair/inspection), scheduled date, completed
  date, technician/vendor, cost, notes · seen in: EZOfficeInventory ("create tickets... notes and service
  details such as costs, maintenance dates, and associated vendors"), UpKeep (work orders), Snipe-IT
  ("assets retain full history including... maintenance") · priority: table-stakes · spine: new tenant-
  scoped `AssetMaintenance` model, FK to `Asset` · buildable now.
- **Preventive maintenance / recurring service cycles** - repeat-on-schedule tasks so equipment gets
  serviced regularly (e.g. every 6 months) · seen in: EZOfficeInventory ("set service cycles to repeat"),
  UpKeep ("automated schedules based on actual usage") · priority: common · spine: a `next_service_date` /
  `recurrence` field on `AssetMaintenance` or a simple "type=preventive + interval_days" pattern ·
  buildable now (simple interval, not full meter-based triggers).
- **AMC (Annual Maintenance Contract) tracking** - a contract record per asset/vendor with start/end date,
  cost, and auto-renewal/expiry alerting · seen in: general AMC-software pattern (SafetyCulture, Makula
  survey), and implicitly in Freshservice/ManageEngine's "contract" + "vendor" records attached to assets ·
  priority: common · spine: model as an `AssetMaintenance` row with `maintenance_type="amc"` plus
  `contract_start`/`contract_end`/`vendor` fields, rather than a separate contract model - keeps 3.33 to
  the ~3-4-model budget · buildable now.
- **Warranty-claim tracking** - logging a repair done under warranty (no cost to company) · seen in:
  Freshservice, ManageEngine AssetExplorer (warranty linked to contract/vendor record) · priority: common
  · spine: `maintenance_type="warranty_claim"` on the same `AssetMaintenance` model · buildable now.
- **Expiry/renewal email alerts** (warranty, AMC, license) · seen in: Snipe-IT, ManageEngine AssetExplorer,
  most AMC tools · priority: common · spine: n/a (notification job) · integration/later - the *data* (dates)
  ships now, the *alerting* does not.
- **Full CMMS work-order dispatch** (assign technician, mobile push, parts/inventory consumption, meter/
  IoT-triggered PM) · seen in: UpKeep, ServiceNow ITAM · priority: differentiator · spine: n/a · integration/
  later - explicitly the Module 11 CMMS territory, not 3.33.
- **Maintenance/service history log visible on the asset** - a running timeline of everything done to an
  asset · seen in: Snipe-IT, EZOfficeInventory, UpKeep ("maintenance history... in one place") · priority:
  table-stakes · spine: this is just the `AssetMaintenance` queryset filtered by `asset` + ordered by date -
  no extra model needed · buildable now.

### Depreciation (asset value tracking over time)
- **Multiple depreciation methods** - straight-line, declining-balance, sum-of-years-digits · seen in:
  Freshservice ("Declining balance, Straight Line and Sum-of-years-digits... unlimited depreciation
  methods"), EZOfficeInventory ("straight line and declining balance"), ManageEngine AssetExplorer
  ("multiple depreciation methods") · priority: table-stakes among ITAM tools (straight-line specifically
  is universal; declining-balance is common; sum-of-years-digits is differentiator) · spine: new field
  `depreciation_method` choice on `Asset` · buildable now for straight-line; declining-balance is a small
  extra formula, also buildable now; sum-of-years-digits -> defer.
- **Useful life + salvage/residual value inputs** - the two extra numbers straight-line depreciation needs
  beyond purchase cost · seen in: all of Freshservice/EZOfficeInventory/ManageEngine · priority:
  table-stakes · spine: new fields `useful_life_months`/`salvage_value` on `Asset` · buildable now.
- **Current/book value calculation** - acquisition cost minus accumulated depreciation, computed and shown
  per asset · seen in: ManageEngine AssetExplorer ("calculating current value based on acquisition cost and
  useful life"), UpKeep, EZOfficeInventory · priority: table-stakes · spine: **derived** - a Python
  `@property`/helper on `Asset` computing book value from `purchase_cost`, `purchase_date`,
  `useful_life_months`, `salvage_value`, `depreciation_method`, evaluated as of "today" (or an as-of date
  param) · buildable now, no extra table needed.
- **Depreciation schedule / period-by-period ledger** - a stored row per period (month/year) showing
  opening value, depreciation charge, closing value, for audit/reporting · seen in: enterprise ITAM/EAM
  tools (ManageEngine, ServiceNow-adjacent fixed-asset modules) · priority: common for finance-grade
  compliance, **differentiator** for an HR-facing register · spine: would be a `DepreciationEntry` model ·
  **recommend deferring** to Module 11/Accounting integration - see decision below.
- **GL posting of depreciation expense** - journal entries hitting a depreciation-expense / accumulated-
  depreciation GL account · seen in: NetSuite/Sage-class ERPs (not the pure-play ITAM tools above, but
  the natural next step once depreciation is tracked) · priority: differentiator · spine: would reuse
  `accounting.JournalEntry`/`JournalLine` + `GLAccount` · integration/later - explicit hook point for
  Module 2 Accounting, not this pass.
- **Depreciation/utilization reporting** - a report screen listing all assets with cost, accumulated
  depreciation, current value · seen in: Freshservice, EZOfficeInventory ("run reports to lower
  overheads") · priority: common · spine: a list/report view over `Asset`, no new model · buildable now.

## Decision: depreciation approach for this pass

**Recommend: derived computation on `Asset`, not a separate `DepreciationEntry` table.** Store
`purchase_cost`, `purchase_date`, `useful_life_months`, `salvage_value`, `depreciation_method`
(`straight_line` | `declining_balance`) directly on `Asset`, and expose `current_book_value` /
`accumulated_depreciation` as computed properties (or a small manager method taking an `as_of` date). This
matches how every surveyed tool actually *shows* depreciation (a live current-value number per asset,
recomputed on view) rather than how finance-grade GL systems *post* it (a stored monthly schedule). A
stored period-by-period `DepreciationEntry`/schedule table and GL-posting are explicitly deferred to when
this integrates with Module 2 Accounting or Module 11's enterprise depreciation-schedule model - building
it now would over-scope 3.33 past its HR-register purpose and duplicate what Module 11 will own.

## Recommended 3.33 build scope (this pass)

Two new models + one relational patch to existing models - stays inside the ~3-4-new-model budget:

- **`Asset`** [`ASSET-` prefix, `TenantNumbered`] - the central register. Fields: `asset_tag` (unique-ish
  text), `name`, `category` (reuse `AssetAllocation.ASSET_CATEGORY_CHOICES`), `manufacturer`, `model_number`,
  `serial_number`, `purchase_date`, `purchase_cost`, `vendor_name` (text, or optional FK to `core.Party`),
  `warranty_expiry`, `location` (FK `core.OrgUnit`, nullable), `current_holder` (FK
  `hrm.EmployeeProfile`, nullable, denormalized convenience pointer), `status` (choices: in_stock /
  assigned / in_repair / retired / disposed), `condition` (new/good/fair/poor/damaged), `depreciation_method`
  (none/straight_line/declining_balance), `useful_life_months`, `salvage_value`, `notes`. Properties:
  `accumulated_depreciation(as_of=None)`, `current_book_value(as_of=None)`. Justified by: Asset Register
  bullet + the register-field consensus across Snipe-IT/EZOfficeInventory/ManageEngine AssetExplorer/
  Freshservice; status field from ServiceNow/EZOfficeInventory lifecycle patterns; depreciation fields from
  Freshservice/EZOfficeInventory/ManageEngine.

- **Patch `AssetAllocation`** (existing model, no new prefix) - add the nullable
  `asset = models.ForeignKey("hrm.Asset", on_delete=models.SET_NULL, null=True, blank=True,
  related_name="allocations")` exactly as its own code comment already specifies (just pointing at
  `hrm.Asset` instead of a future `assets.Asset`, since Module 11 doesn't exist yet). Wire the
  issue/return actions to flip `Asset.status` and `Asset.current_holder` in the same transaction. This
  fulfils the Asset Allocation + Asset Return bullets by *connecting* existing workflow to the new
  register, per Keka's "assign from asset list or employee profile" and Snipe-IT/GoCodes's check-in/out
  pattern, without rebuilding allocation.

- **`AssetMaintenance`** [`ASSETMNT-` prefix, `TenantNumbered`] - fields: `asset` (FK `hrm.Asset`),
  `maintenance_type` (choices: preventive / repair / amc / warranty_claim / inspection), `status` (choices:
  scheduled / in_progress / completed / cancelled), `scheduled_date`, `completed_date`, `vendor_name`,
  `cost`, `contract_start`/`contract_end` (nullable, used when `maintenance_type="amc"`), `notes`. Justified
  by: Maintenance bullet + EZOfficeInventory's maintenance-ticket fields, UpKeep's work-order/history
  pattern, and the AMC-software consensus (contract dates + vendor + recurring service). A single model
  with a type discriminator covers preventive/repair/AMC/warranty-claim rather than four separate tables -
  keeps the model count down while covering every researched maintenance sub-feature.

- **No new depreciation model** - see decision above; `Asset.purchase_cost` /
  `useful_life_months` / `salvage_value` / `depreciation_method` plus computed properties satisfy the
  Depreciation bullet for this pass.

Net: **2 new models** (`Asset`, `AssetMaintenance`) + **1 FK patch** to the existing `AssetAllocation` -
under the 3-4-model ceiling, leaving room in a future pass if a real `DepreciationEntry` ledger becomes
necessary once Accounting integration is scoped.

## Deferred (later passes / integrations)

- **Barcode/QR label generation + scan-to-check-in/out** (GoCodes, Snipe-IT, EZOfficeInventory,
  Zoho AssetExplorer) - needs label rendering and a scan endpoint/mobile flow; `asset_tag` field is the
  seed, actual scanning ships later.
- **Software license management / SaaS subscription tracking** (Zoho AssetExplorer, Snipe-IT, ManageEngine
  AssetExplorer) - belongs to Module 11.18 ITAM, not HR-facing 3.33.
- **Network/agent-based hardware+software discovery** (ManageEngine AssetExplorer, ServiceNow ITAM, Zoho
  AssetExplorer) - enterprise IT-ops feature, out of scope for an HR module entirely.
- **Full CMMS work-order dispatch with mobile push, meter/IoT-triggered PM, parts consumption** (UpKeep,
  ServiceNow ITAM) - Module 11 CMMS territory; 3.33's `AssetMaintenance` covers the record-keeping, not
  live dispatch.
- **Asset-manager scoped permissions (by location/department/business unit)** (Keka) - a permissions/role
  feature layered on existing tenant+role infrastructure, not a new model; candidate for a later
  permissions pass.
- **Damage charge-back to employee via payroll deduction** (Keka) - needs HRM 3.34 Expense/payroll wiring;
  track `condition` at allocation now, wire the charge-back later.
- **Depreciation schedule ledger + GL posting** (`DepreciationEntry`, `JournalEntry`/`GLAccount` postings) -
  explicitly deferred per the decision above; revisit when Module 2 Accounting integration or Module 11's
  enterprise depreciation model is scoped.
- **Custom/dynamic fields per asset category** (Snipe-IT "Asset Models", Asset Panda "Smart Forms") -
  EAV-style flexibility; `notes` covers the near-term need.
- **Reservation/availability calendar for assets** (EZOfficeInventory) - nice-to-have, not core to the
  register/allocation/maintenance/depreciation bullets.
- **Expiry/renewal email alerts** for warranty/AMC/license dates (Snipe-IT, ManageEngine AssetExplorer,
  general AMC tools) - the underlying date fields ship now; the notification/digest job is a later
  cross-module scheduling concern (mirrors how other HRM submodules defer alerting).
- **Migration/coordination with Module 11 Asset Management System** (`apps/assets`, not yet built) - when
  Module 11 lands, its enterprise `Asset` (prefix `AST-`) should absorb or link to HRM's `hrm.Asset`
  (`ASSET-` prefix) the same way `AssetAllocation` was designed to eventually point at it; note this in
  the eventual Module 11 research pass so the two don't duplicate the register.

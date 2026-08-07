# Research — Sub-module 4.14: Labor Management (Module 4 — Supply Chain Management, `scm`)

Target resolved from `NavERP.md` line 824 (`### 4.14 Labor Management`) and confirmed as the next
unbuilt sub-module: `apps/core/navigation.py` has `LIVE_LINKS` keys `"4.1"`…`"4.13"` and nothing for
`"4.14"`.

The domain surveyed is the **warehouse Labor Management System (LMS)** — engineered labor standards,
goal-based work measurement, direct vs indirect labor, incentive pay, gamification, volume-driven
labor forecasting. Gartner names this market *Warehouse Labor Optimization and Management (WLOM)* and
defines it as software using data-driven (often engineered) standards to track and manage warehouse
labor. That is the right lens — **not** generic HR time-and-attendance, which NavERP already owns in
Module 3 (see the ownership section below, it is the single most important finding in this file).

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`"4.1"` Procurement · `"4.2"` SRM · `"4.3"` Inventory (the spine) · `"4.4"` WMS · `"4.5"` OMS ·
`"4.6"` TMS · `"4.7"` Demand Planning · `"4.8"` Manufacturing · `"4.9"` QMS · `"4.10"` Returns ·
`"4.11"` Analytics · `"4.12"` Contract & Compliance · `"4.13"` Asset Management.
`"4.14"` is absent → this pass. 4.15–4.19 are unbuilt, so 4.14 may FK anything from 4.1–4.13 and
nothing later.

### Spine entities VERIFIED to exist (grep evidence)

`grep -rn "^class (Party|PartyRole|Employment|OrgUnit|Activity|Document|AuditLog)\b" apps/core/models/`

| Entity | File | Notes |
|---|---|---|
| `core.Party` | `apps/core/models/Party.py:5` | `tenant`, `kind`, `name`, `tax_id`, `created_at`. **No `user` FK** — there is no built-in bridge from a Django `User` to a `Party`. |
| `core.PartyRole` | `apps/core/models/PartyRole.py:5` | `ROLE_CHOICES` includes `("employee", "Employee")`. An employee is a Party + this role. |
| `core.Employment` | `apps/core/models/Employment.py:5` | exists |
| `core.OrgUnit` | `apps/core/models/OrgUnit.py:5` | exists |
| `core.Activity` / `core.Document` / `core.AuditLog` | `apps/core/models/` | exist (GenericForeignKey-based) |

`grep -rn "^class PayrollRun" apps/accounting/models/` →
`apps/accounting/models/PayrollIntegration/PayrollRuns.py:6`. **`PayrollRun` is a period-level
ACCRUAL header** — `period_start`, `period_end`, `pay_date`, `headcount`, `gross_wages`,
`employee_tax`, `employer_tax`, `benefits`, `deductions`, `net_pay` (derived, `editable=False`),
`status` draft/posted, `journal_entry` FK. **It has no per-employee lines and no hours columns.**
That matters for the Payroll Integration bullet — see below.

### The 4.4 task tables 4.14 must READ and EXTEND, never duplicate

`apps/scm/models/WarehouseManagement/` — verified by reading the files, exact names and fields:

**`PickTask` (`PickTasks.py:16`) [`PIK-`]** — the picking + packing task.
- `strategy` (`single`/`wave`/`batch`/`zone`), `status` (`pending`/`released`/`picking`/`picked`/`packed`/`cancelled`),
  `EDITABLE_STATUSES = ("pending","released")`, `PICKABLE_STATUSES = ("released","picking")`
- `zone` → `scm.Location`, `wave_ref` (CharField, groups a wave)
- **`assigned_to` → `settings.AUTH_USER_MODEL`** (`related_name="scm_pick_tasks"`, `null=True`)
- packing data: `package_count`, `package_weight`, `tracking_ref`
- timestamps: `picked_at`, `packed_at` (both `editable=False`), plus `created_at`/`updated_at` from `TenantOwned`
- helpers: `line_count()`, `is_short()`, `is_editable`
- **`PickTaskLine` (`PickTasks.py:84`)** — `pick_task`, `item`, `lot_serial`, `from_location`,
  `quantity_requested`, `quantity_picked`, `shortfall` property. Ordering honours
  `from_location__pick_sequence`. **This is the units-picked source for units-per-hour.**

**`PutawayTask` (`PutawayTasks.py:16`) [`PUT-`]** — one item, one move.
- `goods_receipt` → `scm.GoodsReceiptNote`, `item`, `lot_serial`, `from_location`, `to_location`
- **`quantity`** (single Decimal on the header — no line table)
- `strategy` (`directed`/`fixed`/`random`/`cross_dock`), `status` (`pending`/`in_progress`/`completed`/`cancelled`)
- **`assigned_to` → `settings.AUTH_USER_MODEL`**, `completed_at` (`editable=False`)

**`CycleCountTask` (`CycleCountTasks.py:16`) [`CC-`]** — counting.
- `location`, `scheduled_date`, `count_method` (`full`/`abc`/`random`/`zone`),
  `status` (`scheduled`/`in_progress`/`counted`/`reconciled`/`cancelled`)
- **`assigned_to` → `settings.AUTH_USER_MODEL`**
- timestamps `started_at`, `counted_at`, `reconciled_at` (all `editable=False`); `adjustment` → `scm.StockAdjustment`
- `variance_count(lines=None)`, `has_variance()`, `net_variance()` — all accept a pre-fetched
  `lines` list (perf idiom: one scan, not three)
- **`CycleCountTaskLine`** — `expected_quantity` (`editable=False`, server-snapshotted),
  `counted_quantity` (nullable = "not yet counted"), `variance`, `has_variance`.
  **This is the accuracy source for counting work.**

**`YardVisit` (`YardVisits.py`) [`YRD-`]** — yard/dock; not a labor task.

> **Conclusion for "Task Assignment": the task tables already exist and already carry an assignee and
> lifecycle timestamps.** 4.14 must NOT declare a parallel `WarehouseTask`. It ships an **assignment
> console** that reads/writes the three existing tables' `assigned_to`, and a **time/measurement layer**
> that points AT them.

### HRM ALREADY OWNS TIME & ATTENDANCE — read this before designing bullet 2

`grep -rn "^class " apps/hrm/models/AttendanceManagement/ apps/hrm/models/TimeTracking/`:

| HRM class | File | Key fields |
|---|---|---|
| **`AttendanceRecord`** [`ATT-`] | `AttendanceManagement/Record.py:5` | `employee`→`hrm.EmployeeProfile`, `date`, `check_in`/`check_out` (**TimeField**), `hours_worked` (derived in `save()`, `editable=False`, handles overnight), `shift`→`hrm.Shift`, `status` (present/absent/half_day/on_leave/holiday/regularized), `source` (web/mobile/**biometric**/manual), `latitude`/`longitude`/`geofence`, `is_late()`, `geo_status()`. **`unique_together ("tenant","employee","date")` — strictly ONE row per employee per day.** |
| **`Shift`** | `AttendanceManagement/Shift.py:8` | `name`, `start_time`, `end_time`, `grace_minutes`, `is_default`, `is_active` |
| **`ShiftAssignment`** | `AttendanceManagement/Shiftassignment.py:5` | `employee`, `shift`, `effective_from`, `effective_to` |
| **`AttendanceRegularization`** | `AttendanceManagement/Regularization.py:5` | the correction-request workflow |
| **`GeoFence`** | `AttendanceManagement/Geofence.py:8` | punch-location zones |
| **`Timesheet`** [`TS-`] | `TimeTracking/Timesheet.py:8` | `employee`, `period_start`/`period_end`, `total_hours`/`billable_hours` (derived by `refresh_totals()`, `editable=False`), `status` draft→pending→approved/rejected/cancelled, `approver` |
| **`TimesheetEntry`** | `TimeTracking/Timesheetentry.py:5` | `date`, `project`→`accounting.Project`, `task_description` (free text), `hours`, `is_billable`, `billable_rate`, `billable_value` derived |
| **`OvertimeRequest`** | `TimeTracking/Overtimerequest.py:5` | the OT approval workflow |
| **`EmployeeProfile`** [`EMP-`] | `EmployeeManagement/EmployeeProfiles.py:8` | `party`→`core.Party` **OneToOne**, `employment`→`core.Employment`, `designation`, bank/PII fields |
| `SalaryStructureTemplate` / `SalaryStructureLine` | `SalaryStructure/` | **HRM owns compensation** — pay rates are not SCM's |

**Therefore, loudly:** 4.14 must NOT ship a daily attendance table. `hrm.AttendanceRecord` already
is "did this employee attend today, from when to when, and were they late/geofenced". 4.14's
clock-in/out is the **warehouse-shift execution layer**: a *session at a warehouse* whose minutes are
broken into *booked activity intervals* (direct and indirect), which is what an LMS measures and what
an HR attendance row structurally cannot hold (one row per day, TimeFields, no activity breakdown, no
quantity, no location).

**And a hard constraint on how they connect:**
`grep -rn 'ForeignKey(\s*["'"'"']hrm\.' apps/` returns matches **only inside `apps/hrm` itself** —
`apps/scm` contains **zero** references to `hrm.*` (`grep -rn '"hrm\.\w+"' apps/scm` → no matches).
No app outside HRM FKs into HRM. SCM's established way of naming a person is `core.Party` + the
`employee` `PartyRole`, stated in three separate as-built comments:
- `Manufacturing/WorkCenters.py:44-45` — `supervisor → core.Party`, *"The spine's Party + its 'employee' PartyRole — never a second employee table (L29)"*
- `Manufacturing/ProductionTimeLogs.py:52-53` — `operator → core.Party`, same comment
- `AssetManagement/MaintenanceWorkOrders.py:163-169` — `reported_by` / `assigned_to` / `service_vendor` all → `core.Party`
- `AssetManagement/MeterReadings.py:70-73` — `recorded_by → core.Party`, *"the observation outlives the observer"* (SET_NULL)

So: **the worker on a 4.14 labor record is `core.Party`, and the hand-off to HRM/payroll is a REPORT
or EXPORT, never a FK and never a write into `hrm.*`.**

### The house patterns 4.14 should copy (verified, with file refs)

- **`ProductionTimeLog` (`Manufacturing/ProductionTimeLogs.py`) [`PRD-`] is the closest existing
  sibling to a labor activity log** and should be the template: `work_order`, `work_center`,
  `entry_type` (setup/labor/machine/**downtime**), `operator`→`core.Party`, `started_at`/`ended_at`,
  `duration_minutes` (`editable=False`, derived in `save()` — including the `update_fields`
  ride-along at lines 109-115 so a partial save can't strand a stale duration),
  `quantity_completed` explicitly **advisory** (docstring lines 8-13: *"two writers for one quantity
  is the bug 4.7 shipped and had to fix"*), `MAX_LOG_MINUTES = 60*24*31` bounding interval LENGTH not
  just order, and paired validation (`downtime` requires `downtime_reason`; non-downtime forbids it).
- **`DemandForecast` + `DemandForecastPeriod` (`DemandPlanning/DemandForecasts.py`) [`DF-`] is the
  compute-then-apply calculator house style**: header carries `bucket`, `method` (10 choices),
  `status` draft/statistical/in_review/approved/archived with `EDITABLE_STATUSES`,
  `MAX_HORIZON_PERIODS = 520` (*"the grid is ONE DB ROW PER BUCKET, so an unbounded span is an
  unbounded bulk_create"*), `MIN_HORIZON_YEAR = 1900`, `generated_at`/`approved_by` `editable=False`;
  **history is DERIVED, never stored** (`history_series()` reads `SalesOrderLine`/`StockMove`); and
  the period grid keeps each contribution in its **own column** (historical → baseline → seasonal →
  event → signal → consensus → final) because *"the decomposition IS the feature"*.
- **Snapshot-don't-FK for anything that must stay true later**: `MaintenanceWorkOrderTask` copies the
  plan's steps rather than FK-ing them (`MaintenanceWorkOrders.py:49-52, 499-501`);
  `CycleCountTaskLine.expected_quantity` is snapshotted server-side and `editable=False`;
  `InspectionResult` snapshots the characteristic's choice tuple.
- **Hand-off, never a second writer**: `FreightInvoice` (`TransportationManagement/FreightInvoices.py:8-11,
  62-64`) — *"Payment is NOT posted here (L29 — apps.accounting owns the ledger)"*; approval drafts an
  `accounting.Bill` and links it by nullable `editable=False` FK; the audit stops at the draft.
- **Provenance is stamped by the verb, not typed on the form**: the 4.13 `MeterReading` fix removed
  `source`/`reference` from the form because a member could otherwise forge a "captured during work"
  reading. Any 4.14 clock/booking `source` field must follow that.
- **Rate ceilings on the way in**: `MaintenanceWorkOrder.labour_rate` is
  `MaxValueValidator(MAX_LABOUR_RATE)` with the comment *"q4() CLAMPS rather than raising, and editing
  is only @login_required, so an absurd rate does not stay local"* (`MaintenanceWorkOrders.py:218-225`).
- **`TENANT_SCOPED_FKS`** tuple idiom (`MaintenancePlans.py:127`) for cross-tenant FK rejection.
- **Bullets may point at a computed REPORT, not a CRUD list** — precedents in `navigation.py`:
  `scm:safety_stock_report`, `scm:mrp_report`, `scm:refund_queue`, `scm:valuation_report`,
  `scm:production_schedule`, `scm:pm_forecast`.
- **`_choices.py` first in the sub-package** when a vocabulary is read from more than one direction
  (4.10 `ReturnReasons`, 4.11 `_choices`, 4.12 `_choices`, 4.13 `_choices`).
- Model bases: `apps/scm/models/_base.py` — `TenantOwned`, `TenantNumbered` (auto `number` with
  retry-on-collision), `ZERO`, `q2()`, `q4()` (quantize **and clamp**), `MAX_Q2`, `MAX_Q4`.
- **Free number prefixes** (checked against every `NUMBER_PREFIX` in `apps/scm/models/`): `LST`,
  `LSN`, `LAB`, `LPL` are all unused. Taken: PR RFQ QT PO GRN SC SCR SRA CAT ADJ TRF PUT PIK CC YRD
  SO CAR LD SHP FRT SEA DF DS FA WO BOM WC PRD QC QA NCR CAPA RMA WTY KPI ALR LIC CR TD ESG AST PM
  MWO MR.

### Volume sources available for labor forecasting (verified)

`StockMove` (`InventoryManagement/StockMoves.py:13`) is append-only, signed `quantity`, with
`MOVE_TYPES = receipt | issue | transfer | adjustment | consumption | production | maintenance`,
plus `moved_at`, `reference`, and indexes on `(tenant, moved_at)` and `(tenant, reference)`.
**Inbound volume** = `receipt` (+ `GoodsReceiptNote`/`GoodsReceiptLine`), **outbound volume** =
`issue` (+ `PickTaskLine.quantity_picked`). `Location.LOCATION_TYPES = warehouse|zone|bin|…` with a
self-referential `parent`, so "the warehouse" is a `Location` — **there is no separate `Warehouse`
class**. `4.7 DemandForecast` is also available as a forward-looking volume source.

---

## Leaders surveyed (with source links)

1. **Manhattan Associates — Labor Management (Manhattan Active)** — enterprise LMS built around
   engineered standards plus behaviour/gamification; the reference implementation for goals +
   incentives + coaching. <https://www.manh.com/solutions/supply-chain-management-software/labor-management-system>
   and <https://www.manh.com/our-insights/resources/articles/key-attributes-robust-gamification-program-in-labor-management>
2. **Blue Yonder — Warehouse Labor Management** — physics-based engineered labor standards, standards
   library, incentive-pay programs at employee/team/facility level, intraday workforce balancing.
   <https://blueyonder.com/solutions/workforce-and-labor-management/warehouse-labor> and
   <https://info.blueyonder.com/workforce-labor-management/what-is-blue-yonder-warehouse-labor-management>
3. **Infios (formerly Körber / HighJump) — Labor Advantage** — measures employees against engineered
   expectations; captures direct, indirect **and lost time**; mobile self-service performance;
   incentive calculation fed into payroll.
   <https://www.infios.com/en/supply-chain-solutions/labor-management/what-is-labor-management>
4. **TZA — ProTrack** (now part of Easy Metrics) — the industrial-engineering specialist: single- vs
   multi-determinant standards with XYZ travel calculations, a multi-plan incentive engine, dashboards
   over utilisation/quality/delays/indirect/travel. Product pages read via
   <https://www.easymetrics.com/protrack-labor-management-software/>; TZA's own domain was unreachable
   at time of research, so ProTrack specifics are corroborated from SupplyChainBrain / Retail IT
   Insights coverage surfaced in search.
5. **Easy Metrics (OpsFM)** — machine-learning-derived standards, **Indirect Time Insights** and
   **Missing/Gap Time Insights** as first-class products, cost-per-unit, Pay for Performance, Dynamic
   Workforce Planning. <https://www.easymetrics.com/>
6. **Lucas Systems — Jennifer / Dynamic Work Optimization** — AI-derived standards positioned as an
   alternative to ELS data collection; predicts labor requirements and completion times; real-time
   worker dashboards; task interleaving and pick-path optimisation.
   <https://www.lucasware.com/labor-management/> and <https://www.lucasware.com/warehouse-optimization-suite/>
7. **SAP EWM — Labor Management** — the clearest published *data model*: engineered labor standards
   (normal time incl. travel, personal needs, fatigue, unavoidable delay), **planned workload document**,
   **executed workload document**, **employee performance document**, **indirect labor task (ILT)**,
   processor/processor-group master, time-and-attendance recording.
   <https://learning.sap.com/courses/configuring-labor-management-in-sap-ewm-for-sap-s-4hana-cloud-private-edition/configuring-labor-management>
8. **Softeon (IFS Softeon) — embedded Labor Management** — the honest mid-market baseline: standards
   defined by the team as "reasonable expectancies", direct + indirect tracking, dashboards; explicitly
   **no** engineered standards or advanced planning without a third-party LMS.
   <https://www.softeon.com/solutions/warehouse-management-system-wms/labor-management/>
9. **Made4net — LMS** — the component checklist: standards, time & attendance, skills-based/multi-shift
   scheduling, real-time productivity, idle-time dashboards, gamification, **"forecast labor needs based
   on inbound/outbound volume"**, WMS + HR/payroll integration.
   <https://made4net.com/knowledge-center/what-is-a-labor-management-system-lms/>
10. **CognitOps** — the modern "no-recalibration" school: ML standards that self-adjust, predictive
    demand-driven staffing, intraday rebalancing recommendations, cutoff-risk alerts, API-only into an
    existing WMS. <https://cognitops.com/warehouse-labor-management-system/>

Market framing (definition + segmentation) from Gartner Peer Insights' *Warehouse Labor Optimization
and Management* market page <https://www.gartner.com/reviews/market/warehouse-labor-management-system>
and the 2026 buyer round-ups <https://www.guideflow.com/blog/warehouse-labor-software> /
<https://deposco.com/blog/best-labor-management-software-for-mid-market-warehouse-operations-2026/>
(read as search summaries).

---

## Feature catalog (this sub-module only)

### Bullet 1 — Labor Planning ("Forecasting labor requirements based on inbound/outbound volume")

- **Volume-driven labor forecast** — convert expected inbound/outbound units into required minutes,
  then into hours and headcount per day/shift · seen in: Made4net (verbatim "based on inbound/outbound
  volume"), Blue Yonder, Easy Metrics (Dynamic Workforce Planning), CognitOps, Infios · priority:
  **table-stakes** · spine: **new table `LaborPlan` + `LaborPlanLine`**; volume DERIVED from
  `scm.StockMove` (`receipt`/`issue`), `PickTaskLine.quantity_picked`, `GoodsReceiptLine`, or an
  existing `scm.DemandForecast` — never stored history (4.7 rule) · buildable now
- **Planned workload document** — the plan is a persisted artefact with a status, not an ad-hoc screen
  · seen in: SAP EWM (planned workload document), Blue Yonder · priority: **common** · spine: the
  `LaborPlan` header with `draft → planned → approved → archived` · buildable now
- **Required vs scheduled headcount gap** — show the shortfall/surplus per bucket so a supervisor can
  act · seen in: Blue Yonder (proactive balancing), CognitOps (rebalancing recommendations), Lucas
  ("eliminating overstaffing and understaffing") · priority: **table-stakes** · spine: `LaborPlanLine`
  keeps `required_headcount` (computed) beside `planned_headcount` (planner's number); the variance is
  DERIVED · buildable now
- **Per-activity breakdown of the plan** — receiving vs putaway vs picking vs packing vs counting each
  get their own required hours · seen in: SAP EWM, Blue Yonder, Infios, Made4net · priority:
  **table-stakes** · spine: one `LaborPlanLine` per (bucket × activity) · buildable now
- **Seasonal / surge forecasting weeks ahead** · seen in: Blue Yonder ("workload surges weeks in
  advance"), Easy Metrics, Made4net · priority: **common** · spine: reuse `scm.DemandForecast` +
  `scm.SeasonalityProfile` as the `volume_source`, don't re-derive seasonality · buildable now
- **Skills/certification-aware planning** (which skills are short, not just how many bodies) · seen in:
  Blue Yonder, Made4net · priority: **differentiator** · spine: HRM owns `EmployeeSkill`; SCM cannot FK
  it · **deferred**
- **Intraday dynamic rebalancing engine** (re-optimise assignments mid-shift) · seen in: CognitOps,
  Lucas, Blue Yonder · priority: **differentiator** · spine: needs a real-time optimiser ·
  **deferred / later**

### Bullet 2 — Time & Attendance ("Clock-in/out functionality and attendance tracking")

- **Clock-in / clock-out at a facility for a shift** · seen in: SAP EWM (time & attendance recording),
  Infios, Made4net, TZA/Easy Metrics · priority: **table-stakes** · spine: **new table `LaborSession`**
  — the WAREHOUSE-SHIFT layer over HRM's day-grain `hrm.AttendanceRecord`, deliberately not a second
  attendance table · buildable now
- **Direct vs indirect vs lost time** — attended minutes split into productive work, sanctioned
  non-productive work (breaks, meetings, training, cleaning, waiting), and unaccounted time · seen in:
  **all ten** (SAP's indirect labor task; Infios "direct, indirect and lost-time"; Easy Metrics
  Indirect Time + Missing/Gap Time Insights; Softeon; TZA delays/indirect) · priority:
  **table-stakes — this is the defining LMS distinction** · spine: `LaborActivity.activity_type` over a
  `_choices.py` vocabulary with `DIRECT_ACTIVITIES` / `INDIRECT_ACTIVITIES` sets; gap time is
  `session minutes − Σ activity minutes`, **derived, never stored** · buildable now
- **Indirect labor task with a required reason** · seen in: SAP EWM (ILT), Infios, TZA · priority:
  **table-stakes** · spine: `LaborActivity.indirect_reason`, paired-validated exactly like
  `ProductionTimeLog.downtime_reason` · buildable now
- **Punch provenance / source** (badge, mobile, biometric, supervisor entry) · seen in: Infios,
  Made4net, Easy Metrics · priority: **common** · spine: `LaborSession.source`, **stamped by the verb,
  never a form field** (the 4.13 MeterReading provenance fix) · buildable now (hardware = later)
- **Missing/gap-time exception queue** — sessions where attended time is not explained by booked work ·
  seen in: Easy Metrics (a named product feature), TZA (delays), Softeon (idle time) · priority:
  **differentiator** · spine: a computed report over `LaborSession` · buildable now
- **Attendance correction/regularisation workflow** · seen in: Made4net, Infios · priority: **common** ·
  spine: **HRM already owns it** (`hrm.AttendanceRegularization`) → do not rebuild; a 4.14 session is
  editable only while `open`, frozen once approved · parked/reused
- **Geofenced / biometric punches** · priority: **common** · spine: **HRM already owns it**
  (`AttendanceRecord.latitude/longitude/geofence`, `source="biometric"`) · parked
- **Overtime detection and approval** · priority: **common** · spine: **HRM owns
  `hrm.OvertimeRequest`** · parked

### Bullet 3 — Task Assignment ("Assigning specific tasks (picking, packing) to individual workers")

- **Assign / reassign / bulk-assign open tasks to workers** · seen in: Infios ("plan, assign, track and
  optimize labor tasks"), Blue Yonder, Lucas ("optimal labor allocation"), Made4net (skills-based
  assignment) · priority: **table-stakes** · spine: **REUSES the existing `PickTask.assigned_to`,
  `PutawayTask.assigned_to`, `CycleCountTask.assigned_to`** (all `settings.AUTH_USER_MODEL`) — 4.14
  ships the **console + bulk verbs**, adds no assignee column · buildable now
- **Open-work board by worker / zone / activity with age and progress** · seen in: Blue Yonder ("current
  workloads, tasks completed, employee downtime"), CognitOps (zone falling behind), Softeon ·
  priority: **table-stakes** · spine: a computed report over the three 4.4 tables + `LaborActivity` ·
  buildable now
- **Time booked against a specific task** — the link from "who was given it" to "who spent minutes on
  it and how many units they did" · seen in: SAP EWM (executed workload per warehouse task), TZA,
  Easy Metrics · priority: **table-stakes** · spine: `LaborActivity` with nullable
  `pick_task`/`putaway_task`/`cycle_count_task` FKs, exactly one set · buildable now
- **Task interleaving** (combine putaway + pick on one trip) · seen in: Lucas (Jennifer), Manhattan,
  Infios · priority: **differentiator** · spine: an optimisation over 4.4's task queues; the data model
  supports recording it (`LaborActivity` rows in sequence) but the optimiser is **not** this pass ·
  **parked → 4.4 / deferred**
- **Real-time task prioritisation / continuous order streaming** · seen in: Manhattan, Lucas ·
  priority: **differentiator** · spine: wave/release logic lives in 4.4 (`PickTask.strategy`,
  `wave_ref`) · **parked → 4.4**
- **Skills/certification-based routing** · seen in: Made4net, Blue Yonder · priority: **common** ·
  spine: HRM owns skills; no SCM worker master this pass · **deferred**

### Bullet 4 — Performance Tracking ("Measuring worker productivity (units per hour) and accuracy")

- **Engineered labor standards (expected time per unit of work)** · seen in: **all ten** — Manhattan,
  Blue Yonder ("physics-based", standards library), TZA (single- and multi-determinant), SAP EWM (ELS),
  Infios, Easy Metrics/Lucas/CognitOps (ML-derived variants), Softeon (team-defined expectancies),
  Made4net · priority: **table-stakes — without this the module is a timeclock, not an LMS** · spine:
  **new table `LaborStandard`** · buildable now
- **Multi-determinant standards: fixed setup + per-unit + travel + PF&D allowance** · seen in: TZA
  (XYZ travel), SAP EWM (travel, personal needs, fatigue, unavoidable delay), Blue Yonder (travel
  distance, equipment, item weight) · priority: **common** · spine: `LaborStandard.setup_minutes` +
  `minutes_per_unit` + `travel_minutes` + `allowance_pct`; **distance-derived** travel needs bin
  coordinates that `scm.Location` does not have (it has `pick_sequence`, not x/y/z) · buildable now
  (the 3-determinant form); distance-based = **deferred**
- **Scope + effectivity on a standard** (per warehouse/zone, per item class, dated versions) · seen in:
  Blue Yonder (configure or use a predefined library), TZA, SAP EWM · priority: **common** · spine:
  `LaborStandard.location` → `scm.Location`, `item_category` → `scm.ItemCategory`,
  `effective_from`/`effective_to`, plus a module-level **`select_standard(...)` most-specific-wins
  resolver** modelled on 4.10's `select_policy()` · buildable now
- **Performance vs goal (earned minutes ÷ actual minutes)** · seen in: Blue Yonder ("Performance vs
  Goal" per worker), Manhattan, SAP EWM (performance document), TZA, Infios · priority:
  **table-stakes** · spine: DERIVED on `LaborActivity`/`LaborSession` — `earned = standard × quantity`,
  `performance% = earned ÷ duration`. **Never a stored editable column** · buildable now
- **Units per hour** · seen in: all; Blue Yonder explicitly frames UPH as the *naive* metric that ELS
  improves on · priority: **table-stakes** (it is the NavERP bullet) · spine: DERIVED aggregate
  `Σ quantity ÷ Σ hours`; present it **beside** performance-vs-standard so difficulty is visible ·
  buildable now
- **Accuracy / quality measurement** · seen in: TZA (quality levels), Manhattan (safety, quality,
  attendance factored into pay), Lucas (picking accuracy) · priority: **table-stakes** (the bullet says
  "and accuracy") · spine: `LaborActivity.error_quantity` as the recorded input; accuracy% DERIVED.
  Corroborating signals already exist and should be surfaced read-only: `PickTask.is_short()` /
  `PickTaskLine.shortfall`, `CycleCountTaskLine.has_variance` · buildable now
- **Utilisation** (booked minutes ÷ attended minutes) · seen in: TZA dashboards, Softeon, Made4net
  (idle time), SAP EWM (performance document utilisation) · priority: **common** · spine: DERIVED on
  `LaborSession` · buildable now
- **Employee report cards / scorecards and trends over time** · seen in: Blue Yonder ("employee report
  cards", trends), Manhattan, Infios (benchmark historical ratings), Easy Metrics · priority:
  **common** · spine: a computed per-worker report over `LaborActivity` (group by `core.Party`) — no
  new table · buildable now
- **Drill-down by department / shift / individual / activity over time** · seen in: Infios (verbatim),
  TZA, Softeon · priority: **common** · spine: report filters over `LaborSession`/`LaborActivity` ·
  buildable now
- **Coaching trigger when performance falls below a threshold** · seen in: Blue Yonder (below 80% of
  standard prompts on-the-floor coaching), Manhattan, Lucas · priority: **differentiator** · spine: a
  threshold on the report (or a 4.11 `SupplyChainAlert`-style rule later); **an alert row is 4.11's
  table** · buildable now as a report band; alerting **deferred**
- **Observation / standard-validation study** (industrial engineer times a task to set the standard) ·
  seen in: TZA, Blue Yonder ("labor observation"), Easy Metrics Standard Analytics · priority:
  **differentiator** · spine: could be a `source="observed"` value on `LaborStandard` plus notes; a
  full study table is **deferred**
- **Cost per unit / cost-to-serve** · seen in: Easy Metrics (headline), TZA · priority:
  **differentiator** · spine: minutes × a **standard labour charge-out rate** on the standard or plan —
  **never a per-person wage** (`hrm.SalaryStructureTemplate` owns compensation). Cap the rate on the way
  in like `MaintenanceWorkOrder.labour_rate` · buildable now (rate on `LaborStandard`), or **defer**

### Bullet 5 — Payroll Integration ("Exporting labor data for payroll processing")

- **Export attended / direct / indirect / unaccounted hours per worker per pay period** · seen in:
  Infios ("time and attendance and payroll system integration"), Made4net, Easy Metrics (Data
  Integrations), TZA · priority: **table-stakes** · spine: a **computed export report** over approved
  `LaborSession` rows, CSV download. **It must not write `hrm.AttendanceRecord`, `hrm.Timesheet` or
  `accounting.PayrollRun`** — `PayrollRun` is a whole-company period accrual with no employee lines and
  no hours columns, so "drafting" one from warehouse labor would be wrong, not merely redundant ·
  buildable now
- **Approval/lock before export** — a period cannot be exported twice or edited after export · seen in:
  Infios, TZA, Made4net · priority: **common** · spine: `LaborSession.status` `open → closed →
  approved`, with `approved` frozen (the `Timesheet` and `FreightInvoice` approval precedents) ·
  buildable now
- **Incentive / pay-for-performance calculation** · seen in: Manhattan ("define your own variables to
  calculate pay", bonuses factoring safety/quality/attendance), Blue Yonder (employee/team/facility
  incentive programs), TZA (multi-plan incentive engine), Infios ("calculate incentive payments and
  integrate them into payroll"), Easy Metrics (Pay for Performance) · priority: **common in the
  category, but it computes money per person** · spine: would need an `IncentivePlan` model and a pay
  rate SCM does not own · **deferred** — this pass exports performance %, and payroll decides what it
  is worth
- **Push into an HR/payroll system by API** · priority: **common** · **integration/later**

### Beyond the bullets

- **Gamification: goals, points, badges, leaderboards, individual vs team, real-time feedback** · seen
  in: Manhattan (a whole article on it — difficulty-fair goals, leaderboards, peer messaging, prizes
  that need not be large), Infios, Made4net · priority: **differentiator** · spine: a **derived
  leaderboard report** over `LaborActivity` (rank by performance% within a period/activity) needs **no
  new table** and is cheap; persisted badges/points/awards need an award table · leaderboard
  **buildable now**, awards **deferred**
- **Mobile associate self-service dashboard** (see my own score and progress to goal) · seen in:
  Manhattan, Infios, Blue Yonder, Lucas · priority: **common** · spine: a per-worker page over the same
  aggregates; a real mobile app is **later**
- **ML/AI-derived dynamic standards that self-recalibrate** · seen in: Lucas (positioned as replacing
  ELS data collection), Easy Metrics, CognitOps · priority: **differentiator** · spine: record the
  provenance now (`LaborStandard.source = engineered | observed | benchmark`) so a learned standard has
  somewhere to land · **deferred**
- **Cutoff-risk / falling-behind alerts** · seen in: CognitOps, Blue Yonder · priority:
  **differentiator** · spine: 4.11 owns `SupplyChainAlert` and a **closed** metric registry
  (`SupplyChainAnalytics/_choices.py` — grep confirms it currently has **no** labor metrics) ·
  **deferred**, and adding labor metrics is 4.11's call
- **Equipment usage tracking (forklift/RF/voice by task)** · seen in: TZA (equipment usage), Blue Yonder
  (equipment type in the standard) · priority: **differentiator** · spine: 4.13 owns `Asset`; a
  nullable `equipment → scm.Asset` on `LaborActivity` would be one field, but it is not required by any
  bullet · **deferred**

---

## Recommended build scope (this pass — 4 models + 1 child + 2 reports)

New sub-package `apps/scm/models/LaborManagement/` with a `_choices.py` **first** (the 4.10/4.11/4.12/4.13
precedent), owning `ACTIVITY_CHOICES`, `DIRECT_ACTIVITIES`, `INDIRECT_ACTIVITIES`, `INDIRECT_REASON_CHOICES`,
`STANDARD_BASIS_CHOICES`, `STANDARD_SOURCE_CHOICES`, `MAX_LABOUR_RATE`-style caps and the shared
`MAX_SESSION_MINUTES` / `MAX_ACTIVITY_MINUTES` bounds. It must import no sibling model so the edge runs
one way.

Suggested `ACTIVITY_CHOICES` (direct): `receive`, `putaway`, `pick`, `pack`, `load`, `replenish`,
`cycle_count`, `vas`. (Indirect): `break`, `meeting`, `training`, `cleaning`, `equipment_wait`,
`system_down`, `waiting_for_work`, `safety`, `other_indirect`.

### 1. `LaborStandard` [`LST-`] — the engineered standard (keystone)
Justified by: engineered labor standards (all ten products), multi-determinant standards + PF&D
allowance (TZA, SAP EWM, Blue Yonder), scoped/dated standard libraries (Blue Yonder, TZA), standard
provenance (Softeon "reasonable expectancies" vs Lucas/Easy Metrics ML).
- `name`, `activity` (from `_choices`), `basis` (`per_unit`/`per_line`/`per_task`/`per_case`/`per_pallet`)
- `minutes_per_unit`, `setup_minutes`, `travel_minutes`, `allowance_pct` (PF&D)
- `source` (`engineered`/`observed`/`benchmark`), `status` (`draft`/`active`/`archived`),
  `effective_from`, `effective_to`
- optional `labour_rate` (charge-out per hour, `MaxValueValidator` capped on the way in) for cost-per-unit
- **FKs (verified):** `location` → `scm.Location` (`null=True` = whole network), `item_category` →
  `scm.ItemCategory` (`null=True` = all items)
- derived: `minutes_for(quantity)` = `(setup + travel + quantity × minutes_per_unit) × (1 + allowance_pct/100)`
- module-level **`select_standard(tenant, activity, location, item_category, on_date)`** —
  most-specific-wins, mirroring `apps/scm/models/ReturnsManagement/ReturnPolicies.py::select_policy`
- `clean()`: refuse overlapping effective ranges for the same (activity, location, item_category) scope;
  `effective_to >= effective_from`; `TENANT_SCOPED_FKS = ("location", "item_category")`

### 2. `LaborSession` [`LSN-`] — the warehouse clock-in/out shift session
Justified by: clock-in/out (SAP EWM, Infios, Made4net), attended vs booked time, utilisation and
missing/gap time (Easy Metrics, TZA, Softeon), approve-then-export locking (Infios, Made4net).
- **`worker` → `core.Party`** (employee `PartyRole`) — the SCM house rule, `on_delete=PROTECT`
  (the worker is the subject of the row, unlike `MeterReading.recorded_by`); **never `hrm.EmployeeProfile`**
- `location` → `scm.Location` (the warehouse/zone worked), PROTECT
- `work_date` (DateField — deliberately the same grain as `hrm.AttendanceRecord.date` so the two
  reconcile in a report), `clock_in` (DateTimeField), `clock_out` (nullable)
- `shift_label` (CharField — mirrors `hrm.Shift.name` **by convention, not by FK**; SCM does not FK HRM)
- `status` `open → closed → approved` (+ `cancelled`), `EDITABLE_STATUSES = ("open",)`;
  `approved` freezes the session and its activities (export integrity)
- `source` (`web`/`badge`/`mobile`/`supervisor`) and `recorded_by` → `settings.AUTH_USER_MODEL`, both
  `editable=False` and **stamped by the verb** (the 4.13 MeterReading provenance fix), `notes`
- optionally `login` → `settings.AUTH_USER_MODEL` (`null=True`, `editable=False`) stamped on
  self-service clock-in — the only cheap bridge to 4.4's `assigned_to` (see "identity" note below)
- derived, **never stored**: `attended_minutes`, `direct_minutes`, `indirect_minutes`,
  `unaccounted_minutes` (gap time), `earned_minutes`, `performance_pct`, `utilisation_pct`, `units_per_hour`
- `clean()`: `clock_out > clock_in`; bound session LENGTH (`MAX_SESSION_MINUTES`, the
  `ProductionTimeLog.MAX_LOG_MINUTES` reasoning — a derived minutes figure feeds cost and headcount
  maths); refuse a second **open** session for the same worker; refuse sessions overlapping in time for
  the same worker; `TENANT_SCOPED_FKS = ("worker", "location")`

### 3. `LaborActivity` [`LAB-`] — the booked interval (executed workload)
Justified by: executed-workload/performance documents (SAP EWM), direct vs indirect vs lost time
(Infios, Easy Metrics, TZA, Softeon), time booked against a specific task (SAP EWM, TZA), accuracy
(TZA, Lucas), performance vs goal (Blue Yonder, Manhattan). **Shape it on `ProductionTimeLog`.**
- `session` → `LaborSession` (CASCADE, `related_name="activities"`)
- `activity_type` (from `_choices`), `indirect_reason` (blank unless indirect — **paired validation
  exactly like `ProductionTimeLog.downtime_reason`**)
- `started_at`, `ended_at`, `duration_minutes` (`editable=False`, derived in `save()` **with the
  `update_fields` ride-along** copied from `ProductionTimeLogs.py:102-115`)
- `quantity` (units done, 16,4), `error_quantity` (units wrong — the accuracy input)
- **task links (verified 4.4 classes), all nullable, at most one set:** `pick_task` → `scm.PickTask`,
  `putaway_task` → `scm.PutawayTask`, `cycle_count_task` → `scm.CycleCountTask`; plus `reference`
  CharField for work with no task document
- **standard snapshot:** `standard` → `LaborStandard` (`SET_NULL`, `editable=False`, traceability) **plus**
  `standard_minutes_snapshot` and `standard_allowance_snapshot` copied at file time
  (`editable=False`) — editing a standard next month must not silently rewrite last month's measured
  performance (the `MaintenanceWorkOrderTask` / `InspectionResult` / `CycleCountTaskLine` snapshot rule)
- derived: `earned_minutes`, `performance_pct`, `units_per_hour`, `accuracy_pct`
- `clean()`: direct requires `quantity > 0` and forbids `indirect_reason`; indirect requires
  `indirect_reason` and `quantity == 0`; `error_quantity <= quantity`; the interval must fall **inside**
  the session's clock window (the `TimesheetEntry` date-in-period precedent); no writes to a
  `closed`/`approved` session; bound interval length; at most one task FK; `TENANT_SCOPED_FKS` covering
  all four FKs

### 4. `LaborPlan` [`LPL-`] + `LaborPlanLine` — planned workload
Justified by: volume-driven forecasting (Made4net verbatim, Blue Yonder, Easy Metrics, CognitOps),
planned workload document (SAP EWM), required-vs-scheduled gap (Blue Yonder, Lucas, CognitOps).
**Follow the 4.7 `DemandForecast` + `DemandForecastPeriod` generate-then-review shape.**
- Header: `name`, `location` → `scm.Location` (null = network), `period_start`, `period_end`,
  `bucket` (`day`/`week`), `volume_source` (`stock_moves`/`pick_tasks`/`goods_receipts`/
  `demand_forecast`/`manual`), `method` (`naive`/`moving_average`/`same_period_last_year`/`manual`),
  `history_days`, `hours_per_shift` (default 8), `productivity_pct` (default 100),
  `status` (`draft`/`planned`/`approved`/`archived`) with `EDITABLE_STATUSES`,
  `generated_at`/`approved_by`/`approved_at` all `editable=False`;
  optional `demand_forecast` → `scm.DemandForecast` when `volume_source="demand_forecast"`
- **`MAX_HORIZON_PERIODS`** bound copied from `DemandForecast` — the grid is one row per
  (bucket × activity), so an unbounded span is an unbounded `bulk_create` any logged-in planner can fire
- Line (one per bucket × activity): `plan`, `period_start`, `activity`, `forecast_volume`,
  `standard_minutes_snapshot` (glass-box: which standard produced this), `required_minutes`,
  `required_headcount`, `planned_headcount` (the planner's editable override), `notes`;
  variance/coverage DERIVED
- Generation reads history from `StockMove` (`receipt` = inbound, `issue` = outbound),
  `PickTaskLine.quantity_picked` and `GoodsReceiptLine` — **derived at generate time, never a stored
  history table** (4.7's rule)

### Reports (bullets satisfied by a computed page, `scm:safety_stock_report` precedent)
- **`scm:labor_board`** — the assignment console: open `PickTask`/`PutawayTask`/`CycleCountTask` grouped
  by assignee/zone/activity, with bulk assign / reassign / unassign verbs writing the **existing**
  `assigned_to` columns. Serves **Task Assignment**.
- **`scm:labor_payroll_export`** — approved sessions aggregated per worker per period into attended /
  direct / indirect / unaccounted / earned hours and performance %, with CSV download. Serves
  **Payroll Integration**, and is explicitly a hand-off: **no writes to `hrm.*` or `accounting.*`.**
- (Cheap add-ons over the same aggregates, no new tables: a **performance scorecard** page per worker
  and a **leaderboard** for the gamification feature.)

### Proposed `LIVE_LINKS["4.14"]` (5 bullets → 5 targets)
`"Labor Planning": "scm:laborplan_list"` · `"Time & Attendance": "scm:laborsession_list"` ·
`"Task Assignment": "scm:labor_board"` · `"Performance Tracking": "scm:laborstandard_list"` (with the
scorecard/leaderboard reached from its header chips, the `pm_forecast` precedent) ·
`"Payroll Integration": "scm:labor_payroll_export"`.

### Two decisions the todo agent must make explicitly

1. **Worker identity.** 4.4's three task tables use `assigned_to = settings.AUTH_USER_MODEL`; SCM's
   people elsewhere (`WorkCenter.supervisor`, `ProductionTimeLog.operator`,
   `MaintenanceWorkOrder.assigned_to`, `MeterReading.recorded_by`) are `core.Party`. `core.Party` has
   **no** `user` FK, so there is no automatic bridge. Recommendation: keep both, and treat them as
   genuinely different facts — `assigned_to` is *who was given the work* (a login), `LaborSession.worker`
   is *whose minutes these are* (a Party, because warehouse associates often have no ERP login). Do
   **not** add a second assignee column to the 4.4 tables. The optional `LaborSession.login` field is
   the only cheap join, and it degrades gracefully when absent.
2. **No warehouse worker master this pass.** An LMS normally has an associate master (home department,
   badge, skills, shift). The precedent for adding one is `SupplierProfile` (a `OneToOneField` on
   `core.Party` holding SCM-specific attributes, `SupplierProfiles.py:33`), so a future `LaborProfile`
   is legitimate — but it is a 5th model, no bullet requires it, and HRM already holds skills and
   compensation. **Deferred.**

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **Task interleaving, wave/batch release strategy, pick-path optimisation, voice/RF picking UX** →
  **4.4** (owns `PickTask.strategy`, `wave_ref`, `zone`, and `Location.pick_sequence`)
- **Slotting / bin capacity / ABC placement** → **4.4 / 4.3**
- **The demand/volume forecast itself (statistical models, seasonality)** → **4.7** — `LaborPlan`
  *consumes* `scm.DemandForecast` / `scm.SeasonalityProfile`, it must not re-derive them
- **Labor KPI tiles, alerts and thresholds on the analytics dashboards** → **4.11**, which owns
  `KpiTarget`/`KpiSnapshot`/`SupplyChainAlert` and a deliberately **closed** metric registry (currently
  containing no labor metrics — adding them is 4.11's decision, not 4.14's)
- **Forklift/equipment maintenance, downtime, meter-driven service** → **4.13** (`Asset`,
  `MaintenanceWorkOrder`, `MeterReading`)
- **Production operator time at a work centre** → **4.8** (`ProductionTimeLog` already does this for
  manufacturing; 4.14 covers warehouse activities and must not absorb it)
- **3PL labor billing / cost-to-serve per client** → **4.17**
- **Daily attendance records, geofenced/biometric punches, shift masters and rosters, attendance
  regularisation, overtime approval, timesheets against projects, employee skills, pay rates and salary
  structures** → **HRM 3.9 / 3.11 / 3.x** (`AttendanceRecord`, `Shift`, `ShiftAssignment`,
  `AttendanceRegularization`, `GeoFence`, `Timesheet`, `TimesheetEntry`, `OvertimeRequest`,
  `EmployeeSkill`, `SalaryStructureTemplate`)
- **Payroll calculation, payslips, the payroll journal entry** → **HRM 3.14 + `accounting.PayrollRun`**
  (L29 — accounting owns the ledger; 4.14 exports and stops)

## Deferred (later passes / integrations)

- **Incentive / pay-for-performance engine** (plans, tiers, payout calculation) — computes money per
  person and needs a pay rate SCM does not own. Export performance % now; decide ownership with HRM later.
- **Persisted gamification** (points, badges, awards, team competitions) — the derived leaderboard is
  free; an award table is a later pass. Real-time peer messaging is out of scope entirely.
- **ML/AI-derived self-recalibrating standards** (Lucas, Easy Metrics, CognitOps) — record
  `LaborStandard.source` now so a learned standard has somewhere to land; the training pipeline is later.
- **Distance/XYZ travel-driven standards** (TZA, Blue Yonder) — `scm.Location` has `pick_sequence` but
  no coordinates; a coordinate model is a 4.3/4.4 change, not a 4.14 one.
- **Intraday dynamic rebalancing / cutoff-risk alerting** (CognitOps, Blue Yonder) — needs an optimiser
  and 4.11's alert table.
- **Standard-setting observation studies** (industrial-engineering time studies) — a study table with
  observed readings; `source="observed"` + notes covers the provenance for now.
- **Skills/certification-based assignment** — HRM owns `EmployeeSkill`; a cross-app read is a reporting
  question, not a FK.
- **Mobile associate app, badge/biometric clocks, voice terminals** — hardware/integration; the
  `LaborSession.source` vocabulary is the seam.
- **`LaborProfile` warehouse worker master** (home warehouse, badge ID, default shift, user link) —
  legitimate later (the `SupplierProfile` OneToOne precedent), but no bullet needs it this pass.
- **Two-way sync with `hrm.AttendanceRecord`** — the reconciliation report (session hours vs HR
  attendance hours for the same person-day) is buildable later on the `work_date` grain chosen above;
  an automatic write into HRM is not on the table.

# Research — Sub-module 4.15: Cold Chain Management (Module 4 — Supply Chain Management, `scm`)

Target resolved from `NavERP.md` line 831 (`### 4.15 Cold Chain Management`) and confirmed as the next
unbuilt sub-module: `apps/core/navigation.py` has `LIVE_LINKS` keys `"4.1"`…`"4.14"` and nothing for
`"4.15"`.

The domain surveyed is **cold chain monitoring / temperature-controlled logistics** — the products that
watch a temperature-sensitive product's environment, decide whether a deviation matters, and produce the
record a regulator or an auditor asks for. That market has **three distinct product shapes** and this
sub-module's five bullets straddle all three, so all three were surveyed:

1. **In-transit / shipment monitoring platforms** (Controlant, Sensitech, Berlinger, ELPRO, Emerson
   Cargo, Tive, Roambee) — loggers + a cloud platform + excursion assessment + GxP audit trail.
2. **Facility / storage monitoring** (SmartSense by Digi, Sensitech's remote fridge monitoring, ELPRO's
   fixed sensors) — walk-ins, chillers, display cases; alarm escalation, corrective-action workflows,
   HACCP checklists.
3. **Reefer telematics** (ORBCOMM, Carrier Transicold Lynx Fleet, Thermo King TracKing/ConnectedSuite)
   — the refrigeration *unit* itself: setpoint, run hours, alarm codes, pre-trip inspection,
   performance-based service scheduling.

Plus the **cold-storage WMS bracket** (Made4net, AEB, Datex, Logimax) for the Cold Storage Inventory
bullet, which is a warehousing feature rather than a monitoring one.

---

## Repo state checked first

### LIVE_LINKS built so far in module 4
`"4.1"` Procurement · `"4.2"` SRM · `"4.3"` Inventory (the spine) · `"4.4"` WMS · `"4.5"` OMS ·
`"4.6"` TMS · `"4.7"` Demand Planning · `"4.8"` Manufacturing · `"4.9"` QMS · `"4.10"` Returns ·
`"4.11"` Analytics · `"4.12"` Contract & Compliance · `"4.13"` Asset Management · `"4.14"` Labor
Management. `"4.15"` is absent → this pass. 4.16–4.19 are unbuilt, so 4.15 may FK anything from
4.1–4.14 and nothing later.

### Spine + sibling entities VERIFIED to exist (grep evidence)

`grep -rn "^class \w+" apps/scm/models/ apps/core/models/` — every entity below was read, not assumed.

| Entity | File:line | What 4.15 needs from it |
|---|---|---|
| `scm.Location` | `InventoryManagement/Locations.py:10` | `LOCATION_TYPES = warehouse\|zone\|bin\|staging\|transit`, self-referential `parent`, `capacity`, `pick_sequence`, `abc_class`, `is_pickable`, `is_active`, `path()`, `on_hand_value()`. **There is no separate `Warehouse` or `Bin` class** — a cold room IS a `Location`. |
| `scm.Item` | `InventoryManagement/Items.py:56` | `sku`, `category`, `uom`, `tracking` (`none\|lot\|serial`), `is_spare_part`, `on_hand(location=None)`. **No storage-condition or shelf-life field yet.** |
| `scm.LotSerial` | `InventoryManagement/LotSerials.py:5` | `item`, `kind`, `number`, **`expiry_date`**, `status` (`available\|quarantine\|expired\|consumed`), `on_hand()`. **FEFO and shelf-life already have a home — do not build a second one.** |
| `scm.StockMove` | `InventoryManagement/StockMoves.py:13` | append-only signed ledger, `MOVE_TYPES` incl. `adjustment` and `maintenance`, `moved_at`, `reference`; indexes on `(tenant, location, item)` and `(tenant, moved_at)`. On-hand at a cold location is DERIVED here. |
| `scm.Asset` | `AssetManagement/Assets.py:50` [`AST-`] | `asset_type` (machine/vehicle/forklift/conveyor/rack/tool/facility/it_equipment/other), `criticality`, `status`, `location`, `work_center`, `custodian`, `service_vendor`, `meter_name`/`meter_unit` (definition only), `fixed_asset`, `latest_reading()`, MTBF/MTTR/availability. **The reefer unit is an `Asset`.** |
| `scm.MeterReading` | `AssetManagement/MeterReadings.py:60` | append-only asset observation log — `meter_name` (free text, explicitly "Bearing Temp"), `unit`, `reading`, `read_at`, `source` (`manual\|work_order\|**sensor**`), `recorded_by`→`core.Party`. **Asset-only, non-nullable FK — cannot name a location or a shipment.** |
| `scm.MaintenancePlan` | `AssetManagement/MaintenancePlans.py:70` [`PM-`] | `TRIGGER_CHOICES = calendar \| meter \| combined \| **condition**`, `condition_operator` (gte/lte), `condition_threshold`, `schedule_basis` (floating/fixed), `interval_days`, `lead_time_days`, `meter_interval`, `next_due_on`, `due_status()`, `advance()`, `MaintenancePlanTask`. |
| `scm.MaintenanceWorkOrder` | `AssetManagement/MaintenanceWorkOrders.py:81` [`MWO-`] | `work_type` (preventive/corrective/breakdown/inspection/calibration/predictive/safety), `priority`, `source`, 8-state `status`, `asset` (PROTECT), `plan`, `downtime_start/end/minutes`, problem/cause/remedy codes, `labour_hours`/`labour_rate`/`external_cost`, **`non_conformance` FK out to 4.9**, `MaintenanceWorkOrderPart`, `MaintenanceWorkOrderTask`. |
| `scm.NonConformance` | `QualityManagement/NonConformances.py:28` [`NCR-`] | the ONE finding register. `source` (incl. `internal`), `DEFECT_CATEGORY_CHOICES` (incl. `contamination`, `process_deviation`), `severity`, `DISPOSITION_CHOICES` (pending/use_as_is/rework/repair/scrap/return_to_vendor/regrade), `item`/`lot_serial`/`location`/`shipment` FKs, `quarantine_applied`, `cost_of_quality`. **Quarantine flips `LotSerial.status` and posts nothing; scrap posts an `adjustment` StockMove.** |
| `scm.Shipment` + `scm.TrackingEvent` | `TransportationManagement/Shipments.py:18, 148` [`SHP-`] | `direction`, `carrier`, `load`, `sales_order`/`purchase_order`, `mode`, derived `status`, `actual_pickup_at`/`actual_delivery_at`, `current_status_text`, `last_known_location`, `eta`. `TrackingEvent` is the **append-only** milestone log with `event_type` (incl. `exception`, `delayed`), `latitude`/`longitude`, `source` (manual/carrier_api/edi/driver_app/gps_ping). |
| `scm.SupplyChainAlert` | `SupplyChainAnalytics/SupplyChainAlerts.py:59` [`ALR-`] | the exception queue with `SUBJECT_FIELDS` (six typed nullable FKs), `dedupe_key`, `acknowledge/assign/snooze/resolve/dismiss`, and a **closed** `METRIC_CHOICES` registry. |
| `core.Party` / `core.Document` / `core.AuditLog` | `apps/core/models/Party.py:5`, `Document.py:5`, `AuditLog.py:5` | `Document` is a GenericFK attachment (`content_type`/`object_id`/`file`/`name`/`classification`/`version`). `write_audit_log(user, obj, action, changes, tenant)` verified at **`apps/core/utils.py:6`**. |

### Spine entities verified NOT to exist
- **No `Sensor`, `Device`, `TemperatureReading`, `Excursion`, `ColdRoom`, `Reefer` or `StorageCondition`
  class anywhere** — `grep -rn "^class " apps/scm/models/ apps/core/models/` returns none of them. 4.15
  is the first and only owner of anything it declares.
- **No physical-dimension or shelf-life fields on `Item`** (4.6's docstring already notes this and puts
  weight/volume on `Shipment` as a stand-in). `LotSerial.expiry_date` is the only shelf-life fact.
- **No temperature/condition field on `Location`.**

### Free number prefixes (checked against every `NUMBER_PREFIX` in `apps/scm/models/`)
Taken: `PR RFQ QT PO GRN SC SCR SRA CAT ADJ TRF PUT PIK CC YRD SO CAR LD SHP FRT SEA DF DS FA WO BOM WC
PRD QC QA NCR CAPA RMA WTY KPI ALR LIC CR TD ESG AST PM MWO LST LSN LAB LPL`.
**Free and recommended: `CCM` (monitor), `EXC` (excursion).** The reading ledger takes **no prefix** —
the `StockMove` / `MeterReading` rule: a data point in a series is identified by its subject and its
timestamp, and minting a per-tenant sequence for one is a counter nobody ever quotes.

### Three as-built traps this sub-module walks straight into

1. **`q4()` and `MinValueValidator(ZERO)` are wrong for temperature.** `_base.py:48` — `q4()` clamps to
   `[-MAX_Q4, MAX_Q4]` so the *sign* is safe, but it is `Decimal(value or ZERO)`: **a missing reading
   becomes `0`, and 0 °C is a perfectly plausible temperature.** Every other decimal in `apps/scm`
   carries `MinValueValidator(ZERO)`; a temperature column must carry
   `MinValueValidator(MIN_TEMPERATURE_C)` / `MaxValueValidator(MAX_TEMPERATURE_C)` instead, and a
   missing reading must stay `None` rather than pass through `q4()`.
2. **MariaDB has no partial indexes** (`SupplyChainAlerts.py:17-37`, verbatim finding). Any "one open
   excursion per monitor" rule must be a `clean()` + detector guard inside `transaction.atomic()`, never
   a `UniqueConstraint(condition=…)` — that constraint is created on SQLite (the test settings), passes
   every test, and is silently omitted in production.
3. **`MeterReading` looks like it already is the temperature ledger, and it is not.** It is asset-only
   (`asset` FK is non-nullable CASCADE), so it can carry a reefer's discharge-air probe but **cannot name
   a cold room or a shipment**, has no threshold, no humidity, and no interval weight. The split is
   stated below under design question 1.

---

## Leaders surveyed (with source links)

1. **Controlant** — pharma "Cold Chain as a Service": reusable validated IoT loggers + cloud platform,
   real-time monitoring, smart excursion alerts, device-health checks, **automatic release when no
   excursion occurred**, digital audit trail, validated to 21 CFR Part 11 / EU Annex 11.
   <https://www.controlant.com/platform>
2. **Sensitech (Carrier) — SmartView** — online temperature monitoring across sites; **Handling &
   Excursion Management** (automating excursion evaluation to speed the release decision), warnings as a
   layer *before* alarms, remote fridge/freezer oversight, clustering/trending, KPI management,
   audit-ready data in one system. <https://www.sensitech.com/en/products/smartview-software/> ·
   <https://www.sensitech.com/en/products/software/>
3. **Berlinger (Sensitech) — SmartView cold chain / clinical trial** — temperature graph + statistics +
   excursions + device delivery rates, a **PDF sector report** per shipment, GAMP 5 validated web app,
   real-time excursion alerting. <https://www.berlinger.com/shipment-monitoring-solutions/smartview-cold-chain-basic-module>
   · <https://www.berlinger.com/cold-chain-monitoring-solutions>
4. **ELPRO — liberoMANAGER + LIBERO loggers** — the most explicit published *rule engine*: **up to 8
   configurable alarm levels including MKT-based alarms and total-duration-outside-limits**, assessment
   at product level to avoid unnecessary quarantine, **continuous stability-budget calculation**, one
   database across single-use PDF / Bluetooth / real-time devices, GAMP 5 + 21 CFR Part 11, ILAC/NIST/ISO
   17025-traceable 3-point calibration certificates per logger.
   <https://www.elpro.com/en/libero-manager> · <https://www.elpro.com/en/learn/mean-kinetic-temperature-explained>
5. **Emerson Cargo Solutions — GO Real-Time trackers + Oversight** — cloud portal + mobile app over
   wireless/NFC loggers and real-time trackers; monitors **temperature, location, light and humidity**;
   trackers configured to notify by SMS/email the moment a condition deviates; data export/integration
   into the customer's own platform. <https://www.fleetowner.com/refrigerated-transporter/reefer-operations/article/21233366/emersons-oversight-platform-adds-single-sign-on-feature>
   · <https://www.foodlogistics.com/transportation/cold-chain/press-release/21114227/emerson-emerson-incorporates-4gcatm-technology-into-next-generation-go-realtime-tracker>
6. **Tive** — real-time trackers + platform tiered by *rule sophistication*: standard alerts →
   **smart alerts with custom thresholds** → geofence alerts → **smart route-deviation alerts**; custom
   shipment reports + CSV; lane/carrier analytics identifying risky lanes; API/webhook integration;
   **24/7 human monitoring service**; NIST-traceable calibration certificate with every tracker.
   <https://www.tive.com/platform> · <https://www.tive.com/blog/how-to-reduce-temperature-excursions-in-pharmaceutical-cold-chain-shipping>
7. **Roambee** — AI-powered real-time visibility, predictive analytics and multi-sensor condition
   monitoring for cold chain logistics. *(Roambee's own product pages now 301 to `decklar.com` and did
   not resolve to feature content at time of research; this entry is corroborated from the 2026
   comparison round-ups only, and is therefore cited at that confidence.)*
   <https://www.guideflow.com/blog/cold-chain-software>
8. **SmartSense by Digi** — the facility/food-safety school: wireless sensors on walk-ins, chillers and
   display cases; continuous monitoring; excursion alerts; **prescriptive corrective-action workflows
   with audit-ready documentation**; **paper HACCP procedures converted to digital checklists and
   tasks**; equipment insights from **compressor performance and door-open events** for proactive
   maintenance. <https://smartsense.co/solutions/food-safety/>
9. **ORBCOMM — reefer container / trailer telematics** — around-the-clock temperature monitoring with
   **two-way control of setpoint, humidity and controlled-atmosphere**, **virtual pre-trip inspection**,
   customisable alerts for temperature/humidity/CA excursions, **equipment malfunction**, route deviation
   and unauthorised door opening, plus fuel and maintenance management on the reefer asset.
   <https://www.orbcomm.com/en/solutions/transportation/reefer-monitoring> ·
   <https://www2.orbcomm.com/container-telematics>
10. **Carrier Transicold — Lynx Fleet** and **Thermo King — TracKing / ConnectedSuite** — TRU telematics:
    remote setpoint / operating-mode / IntelliSet changes, notifications for **setpoint deviation,
    geofence breach, low fuel or battery, power and mode changes**, **up to five probes for multi-zone
    reefers**, **service scheduled on actual performance instead of calendar alerts**, digitally stored
    temperature records for **FSMA** compliance, fuel + maintenance reporting, a fleet **readiness
    score**, remote alarm-clear / pre-trip-inspection / manual-defrost.
    <https://www.carrier.com/truck-trailer/en/br/products/br-truck-trailer/lynx-fleet/> ·
    <https://www.thermoking.com/na/en/connectedsuite-telematics/tracking-telematics.html>
11. **Cold-storage WMS bracket — Made4net, AEB, Datex, Logimax** (surveyed as one bracket for the Cold
    Storage Inventory bullet): user-defined **temperature zones** (chiller / deep freeze / blast / ambient
    and sub-zones), **FEFO / shelf-life-driven picking**, catch-weight, lot + best-before tracking, and
    real-time temperature monitoring sitting *beside* the inventory rather than inside it.
    <https://made4net.com/knowledge-center/cold-storage-warehouse-management-system-wms-features-benefits/>
    · <https://www.aeb.com/en/warehouse-management-software/cold-storage-warehouse-management-software.php>
    · <https://datexcorp.com/blog/wms-solutions-best-cold-storage-wms-for-3pls/>

**Regulatory grounding** (needed because three of the five bullets are compliance features): USP General
Chapter **&lt;1079.2&gt; Mean Kinetic Temperature** <https://www.usp.org/sites/default/files/usp/document/supply-chain/apec-toolkit/USP%20GC1079.2.pdf>;
**EU GDP 2013/C 343/01** (continuous monitoring, traceability, ALCOA+ contemporaneous records) and
**EU Annex 11 / 21 CFR Part 11** for the computerised-system side <https://eupry.com/gdp/>;
HACCP/FSMA on the food side (SmartSense, Carrier).

---

## The five design questions, answered

### Q1 — The reading ledger: what shape, and what stops it becoming unbounded?

**What the products actually do.** Three storage postures coexist in the market and they are not
alternatives, they are *tiers*:

- **Single-use PDF loggers** (ELPRO LIBERO Cx, Sensitech TempTale) produce **one artefact per shipment**
  — a graph, statistics, excursions — not a live row stream. The unit of record is the *trip report*.
- **Multi-use / real-time devices** (Controlant, Tive, Emerson GO Real-Time, ORBCOMM) sample every
  1–15 minutes and **buffer, then upload in bursts**. Nothing writes one row per sample synchronously.
- **Platforms display and reason over aggregates** — min/max/mean, % time in range, MKT, and an
  **excursion record**. ELPRO's alarm engine is explicitly built on *duration outside limits* and *MKT*,
  both of which are integrals over intervals, not statements about single samples.

**Recommendation for NavERP: `TemperatureReading` is an INTERVAL SUMMARY row, not a raw sample.**

- The monitor declares `logging_interval_minutes` (default 30, bounded 1–1440). Each imported row covers
  one interval and carries `temperature` (the representative value), plus optional `min_temperature`,
  `max_temperature` and `sample_count` for that window. This is exactly the shape a logger's own PDF
  summary and a gateway batch already emit, and it makes the duration/MKT arithmetic correct because
  each row carries its own weight.
- **`interval_minutes` is snapshotted onto the row**, not read from the monitor. Editing the monitor's
  interval next month must not retroactively re-weight last month's MKT — the same rule as
  `LaborActivity.standard_minutes_snapshot` and `CycleCountTaskLine.expected_quantity`.
- **Append-only: list + create + a bulk import, and NO edit view, NO delete view, no admin write.** The
  `StockMove` (`StockMoves.py:1-9`) and `MeterReading` (`MeterReadings.py:28-37`) posture verbatim — a
  wrong reading is corrected by posting a later one, and the mistaken row stays visible because that is
  the point of an append-only log. It is also the only posture that survives an ALCOA+ / Part 11 audit,
  where a silently editable measurement is the finding.
- **Nothing derived is stored on the reading.** No `is_excursion` boolean, no `mkt`. Both are a second
  copy of a fact the monitor's limits already determine, and both go stale the moment a limit is edited.

**What bounds the table (four concrete guards, all with in-repo precedent):**

| Guard | Value | Precedent |
|---|---|---|
| Interval summaries, not raw samples | 30-min default → **17.5k rows / monitor / year** instead of 105k at 5-min sampling | new, but it is what the loggers emit |
| `MAX_BATCH_READINGS` cap per import | ~5,000 rows in one `bulk_create` inside `transaction.atomic()` | `DemandForecast.MAX_HORIZON_PERIODS` — *"the grid is ONE DB ROW PER BUCKET, so an unbounded span is an unbounded bulk_create"*; `LaborPlan` copied it |
| The list page is **never** whole-workspace-unbounded | always monitor-scoped **and** date-range-scoped, paginated; the chart reads a capped `MAX_READING_WINDOW_DAYS` (90) | `MeterReading`'s two indexes exist precisely because the unscoped list could not use the per-asset one |
| Idempotent import | `unique_together = ("monitor", "reading_at")`; the importer counts and **reports** skipped duplicates rather than `ignore_conflicts=True` swallowing them | re-uploading the same logger file must not double the series |

**Indexes:** `(tenant, monitor, reading_at)` and `(tenant, reading_at)` — and repeat the `MeterReading`
lesson in the docstring: `tenant_id` is the **leading** column, so a caller reaching the table through
the related manager alone (`monitor.readings...`) states no tenant, cannot open the index and falls back
to a filesort. Every reader owes a "redundant" `tenant=` (`MeterReadings.py:101-116`).

**Retention is a named non-goal this pass, not an oversight.** GDP wants records kept for years, so a
default purge would be wrong; the seam is a future `purge_temperature_readings` management command with
a per-tenant window. Say so in the docstring rather than leaving it unspoken.

### Q2 — Sensor / monitored-entity polymorphism

**What the products do.** Every platform separates **the device** (a serial number with a calibration
certificate, reusable across trips) from **the deployment** (this device, watching this thing, from this
date, against these limits). ELPRO runs single-use, Bluetooth and real-time devices *into one database*;
Controlant's loggers are explicitly reusable and circular; Tive's trackers are reassigned shipment to
shipment. Sensitech monitors fixed fridges and moving shipments in the same product. The subject is a
property of the *deployment*, never of the reading.

**Recommendation: a `ColdChainMonitor` "monitoring point" master carrying THREE typed nullable subject
FKs — `location` / `asset` / `shipment` — with `clean()` enforcing exactly one. The reading ledger FKs
the monitor, and nothing else.**

Why this and not the alternatives:

- **Not nullable subject FKs on the reading.** That pushes a three-way branch into the highest-volume
  table in the sub-module, widens every row, and forces every aggregate to `COALESCE` across three
  columns. Resolve the polymorphism **once, on the low-volume master**; the ledger keeps a single
  non-nullable FK and a single index.
- **Not a `GenericForeignKey`.** `SupplyChainAlerts.py:109-114` already settled this for SCM: *"Six typed
  FKs rather than one generic object id: a bare int carries neither a tenant nor a type, so it can point
  at a deleted or cross-tenant row (L40 §3)."* Copy the `SUBJECT_FIELDS` tuple idiom so `clean()` walks
  the list and a template renders "what this watches" without a three-branch if-chain.
- **Not "reuse `MeterReading`".** It is asset-only and non-nullable — it structurally cannot name a cold
  room or a shipment. **The split to state in the docstring:** `MeterReading` stays the **asset-condition**
  ledger that feeds maintenance (run hours, discharge-air temp, and `MaintenancePlan(trigger_type=
  "condition")`); `TemperatureReading` is the **product-environment** ledger — what the *goods*
  experienced. That is the same split reefer telematics makes between the unit's supply/return air
  sensors and the cargo probes, and each answers a question the other's subject cannot express.

**Device vs deployment:** `device_serial` is a plain CharField and is **deliberately not unique per
tenant** — a reusable logger has many deployments, one per shipment, and each is its own monitor row with
its own limits and its own reading history. The rule that *is* enforced (in `clean()`, because MariaDB
cannot express it as a partial unique index) is: **no second `active` monitor may share a
`device_serial`.**

**Subject FKs are `PROTECT`**, unlike `SupplyChainAlert`'s SET_NULL subjects: an alert is history and
must survive its subject being retired, but a monitor is a *live configuration* and a monitor with no
subject is uninterpretable and breaks its own exactly-one rule. You retire the monitor; you do not delete
the cold room out from under it. Correspondingly, **the subject is frozen once the monitor has readings**
(a `clean()` rule) so an audit report cannot be rewritten by re-pointing a monitor.

### Q3 — Excursion detection: the industry standard, and the minimal defensible derived rule

**The market's five tiers, in ascending rigour:**

1. **Threshold breach** — a reading outside the product's range. Universal; every product surveyed.
2. **Duration / cumulative time out of range (TOR)** — the deviation only counts once it persists.
   ELPRO alarms explicitly on *total duration outside limits*; Tive/Controlant delay alerts to avoid
   firing on a door-open blip. **This is what separates an alarm engine from a `>` operator.**
3. **Multi-level bands** — a *warning* band before the *alarm* band. ELPRO: up to 8 alarm levels;
   Sensitech: *"automated warnings as an additional layer of defence to intervene before alarms occur."*
4. **Mean Kinetic Temperature (MKT)** — USP &lt;1079.2&gt;, Arrhenius-weighted, always ≥ the arithmetic
   mean; ELPRO supports **MKT-triggered alarms**. Needs interval readings + an activation energy
   (83.144 kJ/mol default) + the gas constant. **Explicitly NOT applicable to frozen product or
   freeze-thaw**, and it must not be used to offset a prior excursion.
5. **Stability budget** — cumulative allowed out-of-range time consumed across the product's whole life
   (ELPRO's continuous remaining-budget calculation). Requires a per-product budget master.

**Recommendation — the minimal defensible rule NavERP computes rather than stores:**

An excursion is an **EPISODE derived from the reading ledger**, not a typed claim:

```
out_of_range(r) = (min_limit is not None and r.temperature < min_limit)
               or (max_limit is not None and r.temperature > max_limit)

walk the monitor's readings in reading_at order
  open an episode at the first out-of-range reading
  extend it while consecutive readings stay out of range
  close it at the first in-range reading (ended_at = that reading's reading_at)
  duration_minutes = (ended_at or now) - started_at
  extreme_temperature = max/min over the episode's readings
  breach_direction    = high | low | both
  REPORTABLE only when duration_minutes >= monitor.excursion_grace_minutes   <- tier 2
```

- **Every measured column on the excursion is `editable=False` and written only by the detector**
  (`started_at`, `ended_at`, `duration_minutes`, `extreme_temperature`, `reading_count`, `mkt`, and the
  **snapshotted `limit_min` / `limit_max` in force when it fired**). Only the triage block is
  human-writable. This is the `SupplyChainAlert` contract verbatim (`SupplyChainAlerts.py:1-8`):
  *"the numbers on an alert are recomputed by the detector, but the triage columns are written only by
  the workflow methods and never by a form."*
- **Why the excursion is a stored row at all, when its numbers are derived:** acknowledgement,
  investigation, the assessment decision, the root cause and the corrective action are *human state no
  aggregate can reproduce* — the same reason 4.11 stores alerts. Derived numbers, stored judgement.
- **De-dupe in the detector, inside `transaction.atomic()`** — resolve the monitor's still-open episode
  and UPDATE it rather than creating a second row. **Not** a DB constraint (MariaDB partial-index finding
  above).
- **MKT is computed on read and may honestly answer `None`** — for a frozen/cryogenic monitor (USP says
  it does not apply) and for a window with no readings. The 4.13 rule: *"an honest figure can answer
  `None`, never 0"* — an MKT of 0 °C reads as a perfectly-cold shipment, the exact opposite of "we don't
  know."
- **Tier 3 (warning band) is one nullable column** (`warning_margin_c`) and a chip on the monitor list —
  cheap, and it is the feature two leaders name. **Tier 5 (stability budget) is deferred** — it needs a
  per-product budget master this pass does not own.

### Q4 — Reefer maintenance: does 4.13 already carry it? (Read the code: **yes, entirely.**)

Verified by reading `apps/scm/models/AssetManagement/`:

- `MaintenancePlan` (`MaintenancePlans.py:70`) has **exactly the four triggers reefer PM needs**:
  `calendar` (annual service), `meter` (every 500 run hours — Carrier's *"service scheduled based on
  actual performance instead of calendar alerts"*), `combined` ("whichever comes first"), and
  **`condition`** with `condition_operator` + `condition_threshold`. Its own module docstring
  (lines 10-13) states the intent in writing: *"the fourth is the seam 11.7 / IoT condition monitoring
  lands on: a sensor feed becomes a `MeterReading` row, and a `condition` plan already knows what to do
  with one."* That seam was built for this sub-module.
- `MaintenanceWorkOrder` (`MaintenanceWorkOrders.py:81`) carries `work_type` including `preventive`,
  `inspection`, `predictive` and `calibration`; `downtime_start/end/minutes`; the Maximo
  problem/cause/remedy hierarchy (`overheating`, `leak`, `electrical_fault`, `contamination`,
  `environmental` are all already in the closed vocabularies); parts, tasks, labour and external cost;
  and a **link out to `NonConformance`**.
- `Asset` carries `meter_name`/`meter_unit`, `criticality`, `warranty_expires_on`, `service_vendor`,
  MTBF/MTTR/availability, and `latest_reading()`.

**Recommendation: 4.15 declares ZERO maintenance entities.** The "Maintenance of Reefers" bullet is a
**computed board over 4.13** (`scm:reefer_board`) plus one verb. Precedent for a bullet that is a page
over another sub-module's tables exists **twice in this very module**: 4.13's
`"Spare Parts Inventory": "scm:sparepart_list"` computes over 4.3, and 4.14's
`"Task Assignment": "scm:labor_board"` computes over 4.4 (`navigation.py:1005-1010` — *"migration 0024
has no `AddField` at all, which is the evidence"*).

- **What identifies a reefer:** *an `Asset` that has an active `ColdChainMonitor` pointed at it.* This
  requires **no change to 4.13 at all** and cannot go stale the way a hand-set `asset_type` would.
  (Adding `("reefer", "Reefer / Refrigeration Unit")` to `Asset.ASSET_TYPE_CHOICES` is possible —
  `max_length=14` has room and the change is additive/all-default — but it is optional garnish, not the
  definition.)
- **The board shows**, per reefer asset: latest cargo temperature + in/out-of-range chip, open
  excursions, `MaintenancePlan.due_status()`, open work orders, the run-hours meter via
  `Asset.latest_reading()`, and warranty status.
- **The one verb: "raise a work order from this excursion"** creates a `MaintenanceWorkOrder(asset=
  monitor.asset, work_type="corrective")` and links it back through
  `TemperatureExcursion.maintenance_work_order` (SET_NULL). One-way link out, no reciprocal edit to
  4.13's `SOURCE_CHOICES` — the precedent 4.13 itself set for its NCR link
  (`MaintenanceWorkOrders.py:175-179`: *"A link OUT to 4.9, one way. 4.13 owns no root-cause table and
  does not add a reciprocal choice to `NonConformance.source`"*).
- The seeder should demonstrate a reefer `MaintenancePlan` with `trigger_type="meter"` on run hours and
  one with `trigger_type="condition"` on discharge-air temperature — the proof that 4.13 carries the
  bullet.

### Q5 — Compliance reporting: what is actually in an audit pack, and what of it is a table?

What the surveyed products put in front of an auditor:

| Audit artefact | Seen in | Stored or derived in NavERP? |
|---|---|---|
| **Excursion log** for a period — every deviation, its duration, its extreme, its assessment, who signed and when | Controlant, Sensitech, Berlinger, ELPRO, SmartSense | **Derived page over `TemperatureExcursion`** — the rows exist for their triage state, the report is a filtered list |
| **Per-shipment / per-unit temperature profile** — graph, min/max/mean, % time in range, TOR, **MKT** | Berlinger (PDF sector report), ELPRO, Sensitech, Tive | **Fully derived** over `TemperatureReading` — never stored |
| **Sensor calibration certificates** with traceability and expiry (ISO 17025 / NIST) | ELPRO (3-point certs per logger), Tive (cert per tracker), Controlant | **STORED — the one genuinely persistent artefact**: `calibrated_on`, `calibration_due_on`, `calibration_reference` on the monitor + the PDF as a `core.Document` (verified GenericFK shape) |
| **Audit trail of who changed what** (ALCOA+, Part 11 / Annex 11) | Controlant, ELPRO, Berlinger | **Reuses `core.AuditLog` via `write_audit_log()`** (`apps/core/utils.py:6`) — no second audit table |
| **HACCP checklists + corrective-action records** | SmartSense (food side) | Corrective action = the excursion's own `corrective_action` + the NCR/MWO links. **A checklist engine is 4.9/4.12 territory — parked** |
| **Temperature mapping / storage qualification** | ELPRO, GxP consultancies | **Deferred** — it is a study with placement diagrams, not a monitoring feature |
| **Part 11 electronic signature** on the release decision | Controlant, ELPRO, Berlinger | **Deferred and flagged**: a real e-signature needs re-authentication at signing, a stated meaning-of-signature and a tamper-evident record. That is a Module 0 capability. 4.15 records `assessed_by` + `assessed_on` and does **not** claim to be Part 11 compliant. |

**So: "Compliance Reporting" is a page over derived data, plus three stored calibration columns.** It is
not a table.

---

## Feature catalog (this sub-module only)

### Bullet 1 — Temperature Monitoring ("Integration with IoT sensors to track temperature in real-time")

- **A monitoring point that binds a device to a subject with limits** — one row per deployment; the
  device is reusable, the deployment is not · seen in: Controlant, ELPRO (one DB across single-use /
  Bluetooth / real-time), Sensitech, Tive, ORBCOMM · priority: **table-stakes** · spine: **new table
  `ColdChainMonitor`**, subject = exactly one of `scm.Location` / `scm.Asset` / `scm.Shipment` (all
  verified) · buildable now
- **Continuous temperature series per monitor** · seen in: all eleven · priority: **table-stakes** ·
  spine: **new table `TemperatureReading`** (interval summaries, append-only) · buildable now
- **Humidity alongside temperature** · seen in: Emerson (temp/location/light/humidity), Tive, ORBCOMM
  (two-way humidity control), Roambee · priority: **common** · spine: one nullable `humidity_pct` column
  on the reading + `humidity_min`/`humidity_max` on the monitor · buildable now
- **Multi-probe / multi-zone units** (up to 5 probes on a multi-zone reefer) · seen in: Carrier Lynx
  Fleet, Thermo King · priority: **common** · spine: **already solved** — one `ColdChainMonitor` per
  probe, all pointing at the same `Asset`; no schema change · buildable now
- **Device health / missing-logger detection** ("this sensor has not reported since 09:00") · seen in:
  Controlant (device-health assessments), ELPRO (missing-logger alerts), Berlinger (device delivery
  rates) · priority: **common** · spine: DERIVED — `latest_reading().reading_at` older than N ×
  `logging_interval_minutes`; a chip on the monitor list, **no stored "offline" flag** · buildable now
- **Live in-range / out-of-range chip per monitor** · seen in: all · priority: **table-stakes** · spine:
  DERIVED from the latest reading vs the monitor's limits · buildable now
- **Set-point vs actual** (the reefer is *told* −18 °C; the probe *reads* −15 °C) · seen in: ORBCOMM,
  Carrier, Thermo King · priority: **common** · spine: `setpoint_temperature` nullable column on the
  monitor; the gap is derived · buildable now
- **Bulk import of a logger file / gateway batch** · seen in: ELPRO (PDF + Bluetooth + real-time into one
  DB), Emerson (Oversight export/integration), Sensitech (TempTale Manager download) · priority:
  **table-stakes for a system with no live device link** · spine: a CSV import page on the monitor,
  bounded by `MAX_BATCH_READINGS` · buildable now
- **Live sensor/gateway API ingestion, MQTT, device provisioning** · seen in: all · priority:
  **table-stakes in the market** · spine: `READING_SOURCE_CHOICES` declares `sensor_api` as the seam that
  nothing writes this pass — the `METER_SOURCE_CHOICES["sensor"]` precedent verbatim ·
  **integration/later**
- **Light / shock / tilt / door-open sensing** · seen in: Emerson (light), Tive, ORBCOMM (unauthorised
  door opening), SmartSense (door-open events) · priority: **common** · spine: would widen the reading
  row for facts no bullet asks for; the sub-module is *temperature* · **deferred**
- **24/7 human monitoring desk** · seen in: Tive, Controlant · priority: **differentiator** · spine: a
  service, not software · **out of scope**

### Bullet 2 — Excursion Management ("Alerts and workflows when temperature deviates from safe ranges")

- **Threshold-breach detection against the monitor's limits** · seen in: all eleven · priority:
  **table-stakes** · spine: DERIVED by the detector; materialised as **new table
  `TemperatureExcursion`** · buildable now
- **Grace period / minimum duration before a deviation counts** · seen in: ELPRO (duration outside
  limits as an alarm criterion), Tive, Controlant · priority: **table-stakes — without it every
  door-open is an incident and the queue is ignored** · spine:
  `ColdChainMonitor.excursion_grace_minutes`; reportability is derived · buildable now
- **Warning band before the alarm band** · seen in: Sensitech (explicitly), ELPRO (8 alarm levels) ·
  priority: **common** · spine: one nullable `warning_margin_c` on the monitor; the band is derived ·
  buildable now
- **Excursion episode with duration + extreme + reading count** · seen in: Berlinger (graph + statistics
  + excursions), ELPRO, Sensitech, Tive · priority: **table-stakes** · spine: `TemperatureExcursion`,
  all measured columns `editable=False` and detector-written · buildable now
- **Limits snapshotted at fire time** · seen in: implied by every GxP audit trail (the record must read
  the same next year) · priority: **table-stakes for defensibility** · spine: `limit_min`/`limit_max`
  snapshot columns — the `LaborActivity.standard_minutes_snapshot` / `InspectionResult` /
  `MaintenanceWorkOrderTask` snapshot rule · buildable now
- **Mean Kinetic Temperature over the excursion window** · seen in: ELPRO (MKT-triggered alarms),
  USP &lt;1079.2&gt;, Sensitech · priority: **differentiator** · spine: computed method over
  `TemperatureReading`; returns `None` for frozen/cryogenic monitors and empty windows · buildable now
- **Triage lifecycle: acknowledge → investigate → assess → close/dismiss** · seen in: Sensitech
  (Handling & Excursion Management), SmartSense (prescriptive corrective-action workflow), Controlant ·
  priority: **table-stakes** · spine: the human-writable block on `TemperatureExcursion`, mirroring
  `SupplyChainAlert`'s five workflow methods returning a `{field: [before, after]}` diff for
  `write_audit_log` · buildable now
- **Product-level assessment: is the product still good?** · seen in: ELPRO (*"assess shipments at
  product level to reduce unnecessary quarantines"*), Sensitech (*"faster, more precise release
  decisions"*), Tive (*"quality team maintains decision authority for disposition"*) · priority:
  **table-stakes** · spine: `assessment` (pending / product_ok / product_affected) + `assessed_by` →
  `core.Party` + `assessed_on` — **and a link OUT to `scm.NonConformance` for the actual disposition**,
  because 4.9 already owns use-as-is / rework / scrap / return-to-vendor **and** owns the quarantine verb
  that flips `LotSerial.status`. **4.15 must not re-declare a disposition vocabulary.** · buildable now
- **Automatic release when no excursion occurred** · seen in: Controlant (a headline feature),
  Sensitech · priority: **differentiator** · spine: DERIVED — a shipment-monitor with zero reportable
  excursions renders a green "clear for release" chip on the shipment profile page. **No stored release
  flag** (that would be a second writer of a fact the ledger already determines) · buildable now
- **Root cause + corrective action recorded on the excursion** · seen in: SmartSense (audit-ready
  corrective action), Tive (full CAPA documentation), ORBCOMM (alarm → rapid repair) · priority:
  **table-stakes** · spine: a small local `EXCURSION_CAUSE_CHOICES` (equipment_failure, power_loss,
  door_left_open, packaging_failure, transit_delay, loading_delay, wrong_setpoint, sensor_fault,
  unknown, other) + a `corrective_action` TextField; a full CAPA is **4.9's `CapaAction`** and is linked,
  not rebuilt · buildable now
- **Equipment fix raised from the excursion** · seen in: ORBCOMM (*"alarm generation and automated
  notifications facilitate rapid response and repair"*), SmartSense, Carrier · priority: **common** ·
  spine: a verb creating a **`scm.MaintenanceWorkOrder`** + `maintenance_work_order` SET_NULL FK back ·
  buildable now
- **Email / SMS / push notification the moment it fires** · seen in: all · priority: **table-stakes in
  the market** · spine: the excursion row is the notification's payload; delivery is an outbound channel
  NavERP does not have · **integration/later**
- **Route deviation / geofence / ETA-risk alerts** · seen in: Tive (smart route-deviation), ORBCOMM,
  Emerson · priority: **common** · spine: **4.6 owns `TrackingEvent` (with lat/long) and 4.11 owns
  `SupplyChainAlert`** · **parked → 4.6 / 4.11**
- **Lane / carrier risk analytics ("which lanes break")** · seen in: Tive Reveal, Sensitech clustering,
  Roambee · priority: **differentiator** · spine: an aggregate over excursions grouped by
  `shipment.carrier` / lane — a later report; the data model already supports it · **deferred**
- **Stability budget across a product's whole life** · seen in: ELPRO (continuous remaining-budget
  calculation) · priority: **differentiator** · spine: needs a per-product budget master · **deferred**

### Bullet 3 — Cold Storage Inventory ("Specific tracking for items requiring refrigeration or freezing")

- **Temperature-classified storage zones (chiller / freezer / deep-freeze / blast / ambient)** · seen in:
  Made4net, AEB, Datex, Logimax, SmartSense · priority: **table-stakes** · spine: **one additive
  `storage_condition` CharField on the EXISTING `scm.Location`** — not a new zone table. Precedent:
  4.4 added `capacity`/`pick_sequence`/`abc_class`/`is_pickable` to `Location` rather than declaring a
  `Bin` model (*"a bin IS a location of `location_type='bin'`, and splitting them would fork the
  StockMove FK and the on-hand aggregate"*, `Locations.py:34-36`) · buildable now
- **Items flagged with the condition they require** · seen in: the whole WMS bracket, ELPRO
  (product-level assessment) · priority: **table-stakes** · spine: **one additive `storage_condition`
  CharField on the EXISTING `scm.Item`** (blank = not temperature-controlled). Precedent: 4.13 added
  exactly one boolean `Item.is_spare_part` rather than forking a parts master (`Items.py:94-102`) ·
  buildable now
- **Storage-condition mismatch report** — "which chilled item is sitting in an ambient bin?" · seen in:
  implied by every zone-enforcing WMS; SmartSense's asset-by-asset monitoring · priority: **common, and
  the single most useful derived page in this bullet** · spine: **fully DERIVED** — on-hand by location
  from `StockMove` (`Item.on_hand(location)` verified) × the two new condition fields · buildable now
- **FEFO / shelf-life-driven picking and expiry visibility** · seen in: Made4net, AEB, Datex, Logimax
  (all name FEFO explicitly) · priority: **table-stakes in cold storage** · spine: **`LotSerial.expiry_date`
  ALREADY EXISTS** — the report is `expiring within N days` / `expired but still on hand`, derived. The
  *picking strategy* itself is **4.4's `PickTask`** · report buildable now; FEFO allocation **parked → 4.4**
- **Unmonitored cold storage** — a location classified chilled/frozen with no active monitor · seen in:
  implied by GDP continuous-monitoring requirement; SmartSense (*"sensors added to all of your critical
  assets"*) · priority: **differentiator, and a genuine audit finding** · spine: DERIVED — left join
  cold `Location`s against active `ColdChainMonitor`s · buildable now
- **Quarantined / affected stock after an excursion** · seen in: ELPRO, Sensitech, Controlant ·
  priority: **table-stakes** · spine: **`LotSerial.status='quarantine'`, written by 4.9's NCR verb** —
  4.15 links to the NCR and reads the status; it does **not** flip lot status itself and does **not**
  post a `StockMove` (4.9 owns both rulings, `NonConformances.py:8-21`) · buildable now
- **Catch-weight (variable-weight) items** · seen in: Made4net, Datex, AEB · priority: **common in cold
  storage** · spine: a genuine 4.3 costing/UOM change (`Item.uom` + `StockMove.quantity` assume fixed
  units) · **parked → 4.3**
- **Blast-freeze / tempering / staging processes as work steps** · seen in: Made4net, Logimax ·
  priority: **common** · spine: a warehouse task type — **parked → 4.4**
- **Per-item numeric temperature limits (not just a class)** · priority: **common** · spine: would need
  a `StorageCondition` master with min/max per product; the class vocabulary plus the monitor's explicit
  limits covers every page this pass needs · **deferred**

### Bullet 4 — Compliance Reporting ("Automated generation of reports for health and safety audits")

- **Excursion log for a date range, exportable** · seen in: Controlant, Sensitech, Berlinger, ELPRO,
  SmartSense · priority: **table-stakes** · spine: a **derived report page + CSV** over
  `TemperatureExcursion` (the `scm:labor_payroll_export` CSV precedent) · buildable now
- **Temperature profile per shipment / per storage unit** — min, max, mean, **% time in range**,
  cumulative TOR, **MKT**, and the reading series · seen in: Berlinger (PDF sector report), ELPRO,
  Sensitech, Tive · priority: **table-stakes** · spine: **fully DERIVED** over `TemperatureReading`,
  reachable from the monitor and from the shipment · buildable now
- **Sensor calibration status and certificates** · seen in: ELPRO (ILAC/NIST/ISO 17025 3-point certs),
  Tive (NIST-traceable cert per tracker), Controlant (validated loggers) · priority: **table-stakes —
  an uncalibrated sensor invalidates every record it produced** · spine: **the only stored piece** —
  `calibrated_on` / `calibration_due_on` / `calibration_reference` on `ColdChainMonitor`, the certificate
  attached as a **`core.Document`** (verified GenericFK). The *due/overdue* chip is derived, the
  `TradeLicense` / `Asset.WARRANTY_NOTICE_DAYS` expiry-notice idiom · buildable now
- **Immutable audit trail of who did what** (ALCOA+, Part 11 / Annex 11) · seen in: Controlant, ELPRO,
  Berlinger · priority: **table-stakes in pharma** · spine: **`core.AuditLog` via
  `apps.core.utils.write_audit_log()`** (verified) — every excursion workflow method returns its
  `{field: [before, after]}` diff. **No second audit table.** · buildable now
- **Append-only measurement record** — the record an auditor trusts because nothing can quietly edit it ·
  seen in: implied by all; Tive (*"tamper-evident audit trail with timestamps"*) · priority:
  **table-stakes** · spine: the `TemperatureReading` no-edit/no-delete posture (StockMove/MeterReading) ·
  buildable now
- **HACCP digital checklists and task sign-off** · seen in: SmartSense (a headline product feature) ·
  priority: **common on the food side** · spine: **4.12 owns `ComplianceRequirement` + `ComplianceCheck`
  and 4.9 owns `QualityAudit` + `InspectionPlan`** — a third checklist engine is exactly the duplication
  L29 forbids · **parked → 4.12 / 4.9**
- **Part 11 electronic signature on the release decision** · seen in: Controlant, ELPRO, Berlinger ·
  priority: **table-stakes in pharma, but not implementable honestly here** · spine: needs
  re-authentication at signing + meaning-of-signature + a tamper-evident record — a Module 0 capability ·
  **deferred, and the docstring must NOT claim Part 11 compliance**
- **Temperature mapping / storage qualification studies** · seen in: ELPRO, GxP practice · priority:
  **differentiator** · spine: a study artefact with sensor-placement diagrams · **deferred**
- **Scheduled report delivery / automated distribution** · priority: **common** · spine: needs a
  scheduler and outbound email · **integration/later**

### Bullet 5 — Maintenance of Reefers ("Specific maintenance schedules for refrigerated containers/units")

> **The whole bullet is served by 4.13. 4.15 declares no maintenance model.** See design question 4.

- **Reefer unit as a maintainable asset with a service history** · seen in: ORBCOMM (PT 6000 maintenance
  management), Carrier, Thermo King · priority: **table-stakes** · spine: **REUSES `scm.Asset`** ·
  buildable now
- **Run-hours-based service ("service on actual performance, not the calendar")** · seen in: Carrier Lynx
  Fleet (verbatim), Thermo King, ORBCOMM · priority: **table-stakes** · spine: **REUSES
  `MaintenancePlan(trigger_type="meter")` + `MeterReading`** — already built, already tested ·
  buildable now
- **Condition-triggered service when a reading crosses a threshold** · seen in: SmartSense (compressor
  performance → proactive maintenance), Carrier, ORBCOMM · priority: **common** · spine: **REUSES
  `MaintenancePlan(trigger_type="condition")` + `condition_operator`/`condition_threshold`** — built
  explicitly for this, per its own docstring · buildable now
- **Pre-trip inspection (PTI) before a load** · seen in: ORBCOMM (virtual PTI), Carrier, Thermo King
  (initiate PTI remotely) · priority: **table-stakes in reefer telematics** · spine: **REUSES
  `MaintenancePlan` with `work_type="inspection"` and its `MaintenancePlanTask` checklist**, generating a
  `MaintenanceWorkOrder`. Remote *initiation* of a PTI on the unit is **integration/later** ·
  buildable now
- **Alarm code → work order → repair** · seen in: ORBCOMM, Carrier, Thermo King · priority:
  **table-stakes** · spine: the excursion's `maintenance_work_order` verb; the failure codes are 4.13's
  closed `PROBLEM_CODE_CHOICES` / `CAUSE_CODE_CHOICES` (`overheating`, `leak`, `electrical_fault`,
  `environmental` all already present) · buildable now
- **A reefer board: fleet status at a glance** · seen in: Thermo King (fleet performance + **readiness
  score** dashboards), Carrier, ORBCOMM · priority: **common** · spine: **computed page
  `scm:reefer_board`** over `Asset` × `ColdChainMonitor` × `MaintenancePlan.due_status()` ×
  `MaintenanceWorkOrder` — **no table** (the `sparepart_list` / `labor_board` precedent) · buildable now
- **Fuel level monitoring and fuel reporting** · seen in: ORBCOMM (PT 6000), Thermo King, Carrier ·
  priority: **common** · spine: a `MeterReading` with `meter_name="Fuel"` — **already possible, zero
  schema change** · buildable now (no work needed)
- **Two-way remote control: change setpoint, switch mode, clear alarms, start/stop, manual defrost** ·
  seen in: ORBCOMM, Carrier Lynx Fleet, Thermo King · priority: **table-stakes in reefer telematics** ·
  spine: commands a device NavERP has no link to · **integration/later** (`setpoint_temperature` on the
  monitor is the record of what it was *set to*, not a command channel)
- **Controlled-atmosphere / cold-treatment control** · seen in: ORBCOMM CT 3500 · priority:
  **differentiator** · spine: a reefer-container feature well beyond the bullet · **out of scope**

### Beyond the bullets

- **Predictive shelf-life / freshness scoring** (remaining shelf life from accumulated thermal exposure)
  · seen in: Roambee, the Zest Labs school · priority: **differentiator** · spine: MKT plus a per-product
  degradation model NavERP does not own; `LotSerial.expiry_date` is the static answer · **deferred**
- **Predictive ETA and delay risk on a monitored shipment** · seen in: Roambee, Tive, FourKites ·
  priority: **differentiator** · spine: **4.6 owns `Shipment.eta` and 4.11 owns alerting** · **parked**
- **Cost of spoilage / claim value per excursion** · seen in: ORBCOMM (spoilage and insurance claims),
  Sensitech · priority: **common** · spine: **4.9's `NonConformance.cost_of_quality` already exists** —
  link, don't duplicate; and no `JournalEntry` (L29) · **reuse**
- **Excursion KPIs on the analytics dashboard** (% shipments excursion-free, MTTR on excursions) · seen
  in: Sensitech (KPI management), Tive Reveal, Berlinger · priority: **common** · spine: **4.11 owns
  `KpiTarget`/`KpiSnapshot` and a deliberately CLOSED `METRIC_CHOICES` registry** — adding cold-chain
  metrics is 4.11's decision · **deferred / parked → 4.11**
- **Mobile app for floor staff to acknowledge an alarm** · seen in: SmartSense, Emerson Oversight
  mobile, Tive · priority: **common** · spine: the excursion pages are the same data · **later**

---

## Recommended build scope (this pass — **3 models**, 2 additive fields, 3 computed pages)

New sub-package `apps/scm/models/ColdChainManagement/` with **`_choices.py` first** (the
4.10/4.11/4.12/4.13/4.14 precedent — pure data, no model imports, explicit `__all__`, star-imported by
`models/__init__.py` *before* the entity modules so the dependency edge runs one way).

`_choices.py` owns, because each is read from two or more directions:
`STORAGE_CONDITION_CHOICES` (read by `ColdChainMonitor`, `Item` **and** `Location` — three directions) +
a companion `STORAGE_CONDITION_RANGES` dict used only to **seed** the monitor's explicit limit columns
(the columns stay the single source of truth); `DEVICE_TYPE_CHOICES`; `READING_SOURCE_CHOICES`
(`manual` / `logger_import` / `sensor_api` / `gateway` — `sensor_api` declared now as the ingestion seam,
the `METER_SOURCE_CHOICES["sensor"]` precedent); `EXCURSION_STATUS_CHOICES` + `EXCURSION_STATUS_CSS`;
`EXCURSION_SEVERITY_CHOICES` + CSS; `EXCURSION_CAUSE_CHOICES`; `MKT_ACTIVATION_ENERGY = Decimal("83.144")`
(kJ/mol, the USP default) and `GAS_CONSTANT`; and the bounds `MIN_TEMPERATURE_C = Decimal("-200")`,
`MAX_TEMPERATURE_C = Decimal("200")`, `MAX_BATCH_READINGS`, `MAX_LOGGING_INTERVAL_MINUTES = 1440`,
`MAX_EXCURSION_GRACE_MINUTES = 10080`, `MAX_READING_WINDOW_DAYS = 90`.

> **Badge classes:** only `badge-green / red / amber / info / muted / slate` exist in `theme.css`
> (L33, five recurrences across 4.10–4.14). No `badge-success`/`-warning`/`-danger`.

### 1. `ColdChainMonitor` [`CCM-`] — the monitoring point (keystone)
Justified by: device-to-subject deployment (Controlant, ELPRO, Tive, Sensitech), limits + grace
(ELPRO duration alarms, Tive), warning band (Sensitech, ELPRO), setpoint vs actual (ORBCOMM, Carrier,
Thermo King), multi-probe zones (Carrier, Thermo King), calibration certificates (ELPRO, Tive),
device-health/missing-logger (Controlant, ELPRO, Berlinger).

- identity: `name`, `device_serial` (**not unique** — a reusable logger has many deployments),
  `device_type` (`single_use_logger`/`multi_use_logger`/`realtime_tracker`/`fixed_sensor`/`gateway_probe`/`manual`)
- **subject — exactly one of three, `SUBJECT_FIELDS = ("location", "asset", "shipment")`, all PROTECT:**
  `location` → **`scm.Location`** (verified), `asset` → **`scm.Asset`** (verified),
  `shipment` → **`scm.Shipment`** (verified)
- limits: `storage_condition` (choices; seeds the rest), `min_temperature` / `max_temperature`
  (**nullable** — a one-sided limit is legitimate; `DecimalField(6, 2)` **signed**, validators
  `MIN_TEMPERATURE_C`/`MAX_TEMPERATURE_C` and **never** `MinValueValidator(ZERO)`),
  `warning_margin_c` (nullable), `humidity_min` / `humidity_max` (nullable),
  `setpoint_temperature` (nullable — what the unit was *told*)
- rules: `excursion_grace_minutes` (default 30, capped), `logging_interval_minutes` (default 30, 1–1440)
- calibration (the audit artefact): `calibrated_on`, `calibration_due_on`, `calibration_reference`;
  the certificate PDF attaches as a **`core.Document`** (GenericFK, verified)
- lifecycle: `status` (`active`/`inactive`/`in_calibration`/`retired`/`lost`), `deployed_on`,
  `retired_on`, `notes`
- derived, never stored: `latest_reading()`, `is_in_range()`, `is_reporting()` (stale-device chip),
  `is_calibration_due()`, `open_excursion()`, `subject_label()`
- `clean()`: **exactly one** subject FK set; **the subject is frozen once readings exist**;
  `max_temperature > min_temperature` when both given; at least one limit required for an `active`
  monitor (*"an alert with no threshold"*, the 4.11 finding); **no second `active` monitor with the same
  `device_serial`** (a `clean()` guard, **not** a partial unique index — MariaDB);
  `TENANT_SCOPED_FKS = ("location", "asset", "shipment")`
- **Wrongly duplicates if built otherwise:** a `Sensor`/`Device` master separate from the deployment
  (fine in a device-fleet product, pure overhead here); a `ColdRoom` table (a cold room **is** a
  `scm.Location`); a `Reefer` table (a reefer **is** a `scm.Asset`).

### 2. `TemperatureReading` (no prefix, `TenantOwned`) — the append-only environment ledger
Justified by: continuous series (all eleven), interval statistics (Berlinger, ELPRO), humidity (Emerson,
Tive, ORBCOMM), logger-file import (ELPRO, Sensitech, Emerson), tamper-evident record (Tive, Controlant).
**Shape it on `MeterReading` + `StockMove`.**

- `monitor` → `ColdChainMonitor` (**CASCADE**, `related_name="readings"`) — the ledger's only FK
- `reading_at` (DateTimeField), `temperature` (`DecimalField(6, 2)`, **signed**, physical-bounds
  validators), `humidity_pct` (nullable, 0–100)
- interval statistics: `min_temperature`, `max_temperature` (both nullable),
  `sample_count` (PositiveSmallInteger, default 1),
  **`interval_minutes` (PositiveSmallInteger, snapshotted from the monitor at import time)** — the row
  carries its own weight so MKT/TOR cannot be retroactively re-weighted
- provenance: `source` (from `_choices`) and `recorded_by` → **`core.Party`** (`SET_NULL` — *"the
  observation outlives the observer"*, `MeterReadings.py:70-74`); both **stamped by the verb, never a
  form field** (the 4.13 `MeterReading` provenance fix), `notes`
- `Meta`: `ordering = ["-reading_at", "-id"]`;
  `unique_together = ("monitor", "reading_at")` (idempotent re-import);
  indexes `(tenant, monitor, reading_at)` and `(tenant, reading_at)`
- `clean()`: **no future `reading_at`** (`MeterReadings.py:145-148`, verbatim reasoning — a future
  reading sorts to the top of an append-only log and becomes "the current value");
  `min ≤ temperature ≤ max` when supplied; cross-tenant guard
- **Documented CRUD exception: list + create + import, NO edit view, NO delete view, read-only in
  `admin.py`.** State it in the docstring as a decision, not an omission.
- **Wrongly duplicates if built otherwise:** a second ledger for asset temperatures — `MeterReading`
  keeps the *asset-condition* series that feeds `MaintenancePlan(trigger_type="condition")`; this table
  keeps the *product-environment* series. Two tables, two subjects, two questions.

### 3. `TemperatureExcursion` [`EXC-`] — the derived episode plus its human judgement
Justified by: excursion records with duration + extreme (Berlinger, ELPRO, Sensitech, Tive), grace/
duration criteria (ELPRO), MKT assessment (ELPRO, USP), triage + corrective-action workflow (Sensitech,
SmartSense, Tive), product-level release decision (ELPRO, Controlant), alarm→repair (ORBCOMM, Carrier).
**Shape the detector-vs-triage split on `SupplyChainAlert`.**

- `monitor` → `ColdChainMonitor` (**PROTECT**, `related_name="excursions"`) — the record must survive
- **detector-written, all `editable=False`:** `started_at`, `ended_at` (null = still open),
  `duration_minutes`, `breach_direction` (`high`/`low`/`both`), `extreme_temperature`,
  **`limit_min` / `limit_max` snapshots** (what was in force when it fired), `reading_count`,
  `mkt` (nullable — `None` for frozen/cryogenic and empty windows), `last_detected_at`
- **human-writable triage block (the only editable fields):** `status` (`open`/`investigating`/
  `assessed`/`closed`/`dismissed`, with `EDITABLE_STATUSES` and `OPEN_STATUSES`), `severity`,
  `acknowledged_by` (user) / `acknowledged_at`, `assessment` (`pending`/`product_ok`/`product_affected`),
  `assessed_by` → **`core.Party`**, `assessed_on`, `cause` (`EXCURSION_CAUSE_CHOICES`),
  `corrective_action` (TextField), `notes`
- **links OUT, all `SET_NULL`, no reciprocal vocabulary edits** (the `MaintenanceWorkOrder.non_conformance`
  precedent): `non_conformance` → **`scm.NonConformance`** (4.9 owns disposition, quarantine and
  cost-of-quality), `maintenance_work_order` → **`scm.MaintenanceWorkOrder`** (4.13 owns the repair),
  `lot_serial` → **`scm.LotSerial`** (the affected batch — read its status, never write it)
- workflow methods returning `{field: [before, after]}` for `write_audit_log` (the
  `SupplyChainAlert.acknowledge/assign/resolve/dismiss` contract); an **empty dict means nothing
  changed**, and every method is no-op safe
- de-dupe **in the detector inside `transaction.atomic()`**, never a DB constraint (MariaDB partial-index
  finding, `SupplyChainAlerts.py:17-37`)
- `TENANT_SCOPED_FKS = ("monitor", "non_conformance", "maintenance_work_order", "lot_serial")`
- **Wrongly duplicates if built otherwise:** a second disposition vocabulary (4.9's
  `DISPOSITION_CHOICES`), a second CAPA table (4.9's `CapaAction`), a second alert queue (4.11's
  `SupplyChainAlert` — this one is domain-specific and carries an *episode*, which an alert does not),
  a second quarantine mechanism (4.9 flips `LotSerial.status` and posts nothing), or any
  `accounting.JournalEntry` (L29).

### Two additive fields on 4.3's masters — deliberately NOT a 4th model
Both are single, all-default, blank-permitted CharFields sharing `STORAGE_CONDITION_CHOICES`, so no
existing row changes meaning and nothing needs backfilling.

- **`scm.Item.storage_condition`** — precedent: `Item.is_spare_part` (4.13 added exactly one field
  rather than forking a parts master, `Items.py:94-102`).
- **`scm.Location.storage_condition`** — precedent: the four 4.4 bin attributes added to `Location`
  rather than declaring a `Bin` model (`Locations.py:34-36`).

Together they turn Cold Storage Inventory from a table into a **query**: on-hand by cold location from
`StockMove`, mismatch between an item's required condition and its location's condition, expiry from
`LotSerial.expiry_date`, quarantine from `LotSerial.status`, and cold locations with no active monitor.
**The 4th model slot is spent here on purpose** — a `StorageCondition` master with per-item numeric
limits is the thing to add when a bullet actually needs it, and none does this pass.

### Computed pages (three of the five bullets are pages, not tables)
- **`scm:cold_storage_report`** — Cold Storage Inventory: cold on-hand, condition mismatches,
  expiring/expired lots (FEFO), quarantined lots, unmonitored cold locations. **Reads 4.3, writes
  nothing.**
- **`scm:cold_chain_compliance_report`** — Compliance Reporting: excursion log for a date range (+ CSV),
  monitor calibration status (due/overdue), % time in range and MKT per monitor/shipment, audit-trail
  link. **Derived; the only stored inputs are the three calibration columns.**
- **`scm:reefer_board`** — Maintenance of Reefers: reefer assets (= assets with an active monitor) with
  latest temperature, open excursions, PM due status, open work orders, run-hours meter. **Computed over
  4.13 + 4.15; declares no table.**
- Plus, reached from a monitor's detail page (no sidebar key — the `MeterReading` / `LaborActivity` /
  `WorkCenter` rule): the reading list, the **CSV import** page, and the temperature **profile** page
  (graph + min/max/mean/%-in-range/TOR/MKT), which is also reachable from a `Shipment`.

### Proposed `LIVE_LINKS["4.15"]` (5 bullets → 5 targets)
```
"Temperature Monitoring":  "scm:coldchainmonitor_list"        # the monitor register + live in-range chip
"Excursion Management":    "scm:temperatureexcursion_list"    # the episode queue + triage
"Cold Storage Inventory":  "scm:cold_storage_report"          # COMPUTED over 4.3 — no table
"Compliance Reporting":    "scm:cold_chain_compliance_report" # COMPUTED — excursion log + MKT + calibration
"Maintenance of Reefers":  "scm:reefer_board"                 # COMPUTED over 4.13 — no table
```
No key for `TemperatureReading` — it is the monitor's ledger panel, exactly as `MeterReading` is the
asset's and `LaborActivity` is the session's.

### Four decisions the todo agent must make explicitly

1. **Interval summaries vs raw samples.** Recommended: **interval summaries** with a snapshotted
   `interval_minutes` per row and a bounded import. If the todo agent chooses raw samples instead, it
   must also choose a retention/rollup policy in the same breath — a Django CRUD app with a
   `bulk_create` any logged-in user can fire and no rollup is a table that grows to tens of millions of
   rows in year one.
2. **The two additive fields on 4.3's `Item` and `Location`.** They are a cross-sub-module migration and
   the alternative (a 4th `StorageCondition` table) is the worse trade. Both have an explicit in-repo
   precedent; take the decision consciously rather than by accident.
3. **Humidity in or out.** Recommended **in** — one nullable column on the reading and two on the
   monitor, and four of the eleven products treat it as co-equal with temperature. Excursion detection
   stays temperature-only this pass (a humidity excursion is a second episode type and no bullet asks
   for it).
4. **What the sub-module claims about compliance.** It must record `assessed_by`/`assessed_on` and reuse
   `core.AuditLog`, and its docstrings must **not** claim 21 CFR Part 11 / Annex 11 / GAMP 5 conformance —
   there is no e-signature, no validated-system evidence and no record-immutability guarantee at the
   database level. Overclaiming here is worse than the gap.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **All reefer maintenance schedules, PM generation, work orders, downtime, failure codes, parts and
  labour cost** → **4.13** (`Asset`, `MaintenancePlan` incl. its `condition` trigger, `MaintenanceWorkOrder`,
  `MeterReading`). 4.15 links to them and declares none of them.
- **Disposition of affected product, quarantine, scrap, cost of quality, CAPA** → **4.9**
  (`NonConformance` + its `DISPOSITION_CHOICES` and quarantine ruling, `CapaAction`, `QualityInspection`)
- **GPS pings, route deviation, geofence, ETA, carrier exception milestones** → **4.6**
  (`Shipment`, `TrackingEvent` with lat/long, `Load`, `Carrier`)
- **FEFO pick allocation, blast-freeze/tempering work steps, zone-constrained putaway and slotting** →
  **4.4** (`PickTask`, `PutawayTask`, `Location.pick_sequence`/`abc_class`)
- **Catch-weight items, per-item numeric temperature limits, item physical dimensions** → **4.3**
  (`Item`, `UOM`, `StockMove`)
- **Cold-chain KPI tiles, thresholds and the alert queue on the analytics dashboards** → **4.11**
  (`KpiTarget`/`KpiSnapshot`/`SupplyChainAlert` and a deliberately **closed** `METRIC_CHOICES` registry —
  adding cold-chain metrics is 4.11's call, not 4.15's)
- **HACCP / food-safety checklists, regulatory obligation registers, licence and certificate tracking** →
  **4.12** (`ComplianceRequirement`, `ComplianceCheck`, `TradeLicense`) and **4.9** (`QualityAudit`,
  `InspectionPlan`)
- **Supplier cold-chain scorecards and risk** → **4.2** (`SupplierScorecard`, `SupplierRiskAssessment`)
- **Any financial effect of spoilage** → **`apps.accounting`** (L29). 4.15 posts no `JournalEntry`, drafts
  no `Bill`, and records cost only through 4.9's existing `cost_of_quality`.

## Deferred (later passes / integrations)

- **Live sensor/gateway ingestion (MQTT, vendor APIs, device provisioning, webhooks)** — the whole market
  is built on it; `READING_SOURCE_CHOICES["sensor_api"]` is declared now so the feed lands as a new *row
  source* rather than a schema change (the `METER_SOURCE_CHOICES["sensor"]` precedent).
- **Outbound notification (email / SMS / push) on excursion** — the excursion row is the payload; NavERP
  has no outbound channel yet.
- **Two-way reefer control** (setpoint, mode, remote PTI, alarm clear, defrost) — ORBCOMM/Carrier/Thermo
  King all do it; it needs a command channel to a device.
- **21 CFR Part 11 electronic signature** on the release decision — needs re-authentication, meaning-of-
  signature and tamper-evidence; a Module 0 capability.
- **Stability budget** (cumulative allowed excursion time across a product's life — ELPRO) — needs a
  per-product budget master.
- **Predictive shelf-life / freshness scoring from thermal exposure** (Roambee, Zest Labs school) — needs
  a degradation model; MKT is the honest halfway house shipped this pass.
- **Lane and carrier cold-chain risk analytics** (Tive Reveal, Sensitech clustering) — an aggregate over
  excursions by carrier/lane; the data model already supports it.
- **Light / shock / tilt / door-open sensing** — would widen the highest-volume table for facts no bullet
  asks for.
- **Temperature mapping / storage qualification studies** — a study artefact with placement diagrams.
- **Calibration history table** — the monitor stores the *current* calibration (which is what "is this
  sensor in date?" needs) plus the certificate as a `core.Document`; an append-only calibration log is a
  later pass, and `MeterReading`'s shape is the template if it is ever wanted.
- **Reading retention / rollup** (`purge_temperature_readings` with a per-tenant window) — GDP wants
  years of records, so a default purge would be wrong; named as a seam, not shipped.
- **A `StorageCondition` master with per-item numeric limits** — the shared vocabulary plus the monitor's
  explicit limits covers every page this pass needs.

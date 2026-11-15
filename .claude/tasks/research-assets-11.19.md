# Research — Sub-module 11.19: Fleet & Vehicle Management (Module 11 — Asset Management System, `assets`)

**Date:** 2026-11-15  
**Target `NavERP.md` section:** `### 11.19 Fleet & Vehicle Management` (Module 11 — Asset Management System, lines 1855–1861)  
**App target:** `apps/assets` (`apps/assets/models/FleetVehicleManagement/`, `templates/assets/fleetvehiclemanagement/...`, `app_name = "assets"`)

---

## Repo state checked first

- **`LIVE_LINKS` built so far in Module 11 (`apps/core/navigation.py`):** `"11.1"` through `"11.18"` are fully built and live in the sidebar (`11.1`–`11.16` + `11.17` Space & Facility Asset Management + `11.18` IT Asset Management). `"11.19"` (Fleet & Vehicle Management) is the **final sub-module of Module 11** and has no `LIVE_LINKS` entry yet.
- **Latest migration (`apps/assets/migrations/`):** `0025_alter_assetfacilityspace_floor_plan_image_and_more.py` (next available is `0026_*`).
- **Installed apps (`apps/`):** `accounting`, `accounts`, `assets`, `bi`, `core`, `crm`, `dashboard`, `ecommerce`, `hrm`, `inventory`, `procurement`, `projects`, `sales`, `scm`, `tenants`.
- **Sibling models available to FK (verified by recursive search on `apps/`):**
  - `scm`: `scm.Asset` [`AST-`] (`code`, `name`, `asset_type` including `"vehicle"`, `status`, `criticality`, `location`, `org_unit`, `custodian`, `supplier`, `service_vendor`, `fixed_asset`), `scm.Location`.
  - `accounting`: `accounting.FixedAsset` [`FA-`] (financial ledger/depreciation owner), `accounting.Currency` (GLOBAL — no tenant filter), `accounting.GLAccount`.
  - `core`: `core.Tenant`, `core.Party` (`kind` person/organization; `PartyRole`), `core.OrgUnit`, `core.Document`.
  - `accounts`: `accounts.User` (`settings.AUTH_USER_MODEL`, filtered by `tenant=self.tenant`).
  - `hrm`: `hrm.EmployeeProfile` (`driver` assignments, license records).
  - `assets` siblings (`11.1`–`11.18`):
    - `assets.AssetCategory` [`ACAT-`] (includes `category_type="vehicle_fleet"`), `assets.AssetModel` [`AMOD-`] (`11.3`).
    - `assets.AssetWarranty` [`AWAR-`] (`11.8`), `assets.AssetInsurancePolicy` [`AINS-`] (`11.8`), `assets.AssetInsuranceClaim` [`AICL-`] (`11.8`).
    - `assets.AssetMaintenanceSchedule` [`AMSC-`] (`11.5`), `assets.AssetServiceContract` [`ASVC-`] (`11.5`), `assets.AssetMaintenanceLog` [`AML-`] (`11.5`).
    - `assets.AssetDowntimeLog` [`ADWN-`] (`11.6`).
    - `assets.AssetConditionAssessment` [`ACND-`] (`11.7`), `assets.AssetTelemetryReading` [`ATEL-`] (`11.7`).
    - `assets.AssetDisposalRequest` [`ADSP-`] (`11.9`), `assets.AssetResaleListing` [`ARSL-`] (`11.9`).
    - `assets.AssetLeaseContract` [`ALC-`] (`11.10`).
    - `assets.AssetGeofenceEvent` [`AGEO-`] (`11.13`), `assets.MobileAssetInspection` [`MAIN-`] (`11.13` DVIR inspections).
- **Prefix & class collision check (verified across `apps/` and `.claude/tasks/contract-*.md`):**
  - Candidate prefixes `FLT`, `VFUL`, `VDRV`, `VSRV` have **zero** collisions across all `NUMBER_PREFIX` declarations in NavERP.
  - Candidate classes `FleetVehicle`, `VehicleFuelLog`, `VehicleDriverAssignment`, `VehicleServiceSchedule` have **zero** collisions across all `apps/`.

---

## Leaders surveyed (with source links)

1. **Fleetio** — Industry benchmark for fleet maintenance, vehicle lifecycle tracking, fuel card reconciliation, and parts inventory — [fleetio.com](https://www.fleetio.com)
2. **Samsara** — Enterprise connected operations platform uniting live high-frequency GPS, AI telematics dashcams, safety coaching scores, and environmental monitoring — [samsara.com](https://www.samsara.com)
3. **Motive (formerly KeepTruckin)** — Market leader for commercial trucking ELD (Electronic Logging Device) compliance, driver safety scorecards, and automated IFTA fuel tax logs — [gomotive.com](https://gomotive.com)
4. **Geotab** — Benchmark for deep OBD/CAN-bus engine diagnostics, DTC fault code logging, predictive vehicle maintenance, and open telematics APIs — [geotab.com](https://www.geotab.com)
5. **Verizon Connect (Reveal)** — Major commercial fleet tracking platform offering live mapping, speed and idle time alerts, route efficiency metrics, and driver safety coaching — [verizonconnect.com](https://www.verizonconnect.com)
6. **Chevin FleetWave** — Enterprise fleet asset management platform specializing in DMV vehicle compliance, title/registration renewals, global multi-currency TCO, and driver allocation — [chevincomputel.com](https://www.chevincomputel.com)
7. **Trimble Fleet Management (TMT Fleet Maintenance)** — Heavy-duty shop maintenance platform handling manufacturer preventive maintenance schedules, warranty recovery, and DOT inspection workflows — [trimble.com](https://www.trimble.com)
8. **Teletrac Navman (Director)** — Global telematics provider focusing on geofencing, driver behaviour monitoring, vehicle utilization, and fuel card integration — [teletracnavman.com](https://www.teletracnavman.com)

---

## Feature catalog (this sub-module only)

### 1. Vehicle Registration & Compliance
*(DMV records, inspection schedules, title tracking, and regulatory compliance)*

- **Comprehensive Fleet Vehicle Registry & Classification** — Dedicated vehicle profile tracking VIN (17-char), license plate, registration state/jurisdiction, make, model, model year, vehicle type (`passenger_car`, `suv_crossover`, `pickup_truck`, `cargo_van`, `box_truck`, `semi_tractor`, `flatbed_truck`, `trailer`, `forklift_yard`, `bus_shuttle`, `specialty_equipment`), ownership type (`owned`, `leased`, `rented`, `customer_managed`), fuel type (`gasoline`, `diesel`, `electric_ev`, `hybrid_electric`, `plug_in_hybrid`, `cng_lpg`), gross vehicle weight rating (GVWR), and operational status (`active_in_service`, `staged_available`, `in_shop_maintenance`, `loaner_out`, `out_of_service`, `pending_disposal`, `decommissioned`) · seen in: Fleetio, Chevin FleetWave, Trimble · priority: `table-stakes` · spine: `new table FleetVehicle [FLT-]` + reuses `scm.Asset`, `accounting.FixedAsset`, `assets.AssetCategory`, `assets.AssetModel` · `buildable now`
- **DMV Registration, Title & Regulatory Compliance Tracking** — Manages DMV title number, title owner entity, registration certificate number, registration effective date, registration expiration date, renewal reminder window, emissions inspection due date, annual DOT/safety inspection due date, compliance status (`compliant`, `renewal_due_soon`, `expired_non_compliant`, `exempt`), and compliance document references · seen in: Chevin FleetWave, Fleetio, Motive · priority: `table-stakes` · spine: `new table FleetVehicle` + reuses `core.OrgUnit`, `core.Document` · `buildable now`
- **TCO & Financial Linkage** — Links vehicle to financial asset (`accounting.FixedAsset`), purchase cost, salvage value, monthly lease cost (if leased), and general ledger cost center (`accounting.GLAccount`, `core.OrgUnit`) · seen in: Chevin FleetWave, Fleetio · priority: `table-stakes` · spine: `reuses accounting.FixedAsset, accounting.GLAccount, core.OrgUnit` · `buildable now`
- **Automated DMV State API Sync & Electronic Title Registration** — Direct statewide DMV electronic title transfer and automated registration renewal payment · seen in: Chevin FleetWave Enterprise · priority: `common` · spine: `integration/later` · `integration/later`

### 2. Fuel & Mileage Tracking
*(Fuel card integration, MPG analysis, and route efficiency)*

- **Fuel Transaction & Fill-up Log** — Detailed fuel transaction record logging fuel date/time, fuel type (`regular_gasoline`, `premium_gasoline`, `diesel_ultra_low_sulfur`, `biodiesel`, `ev_kwh_charging`, `def_exhaust_fluid`, `cng`), quantity (gallons / liters / kWh), unit price, total cost, odometer reading at pump, fuel card number/token, vendor/fuel station name, fuel station location/city, full-tank indicator (`is_full_tank`), and receipt reference · seen in: Fleetio, Motive, Trimble, Samsara · priority: `table-stakes` · spine: `new table VehicleFuelLog [VFUL-]` + reuses `accounting.Currency`, `core.Party` (fuel vendor) · `buildable now`
- **Fuel Efficiency & Consumption Analytics (MPG / L per 100km)** — Deterministic calculation of distance travelled since previous fill-up, fuel consumption rate (Miles Per Gallon `mpg` or Liters Per 100km `l_per_100km`), cost per mile (`cost_per_mile`), and variance against manufacturer expected MPG to highlight abnormal fuel burn, engine drag, or fuel theft/slippage · seen in: Fleetio, Samsara, Geotab · priority: `table-stakes` · spine: `new table VehicleFuelLog` · `buildable now`
- **Route & Energy Efficiency Assessment** — Tracks trip distance, route category (`city_local`, `highway_longhaul`, `mixed_delivery`, `job_site_idle`), route efficiency rating (`optimal`, `acceptable`, `excessive_consumption`, `anomalous`), and driver efficiency notes · seen in: Samsara, Verizon Connect · priority: `common` · spine: `new table VehicleFuelLog` · `buildable now`
- **Direct Fuel Card Provider Webhooks (WEX, Comdata, Fuelman)** — Real-time automated ingestion of POS fuel card transactions from payment networks · seen in: Fleetio, Trimble · priority: `common` · spine: `integration/later` (can feed via `11.15 AssetIntegrationConnector`) · `integration/later`

### 3. Driver Assignment & Safety
*(Driver logs, incident reporting, and safety score tracking)*

- **Vehicle Driver Assignment & Custody Log** — Tracks historical and active driver assignments linking a vehicle to an authorized driver (`hrm.EmployeeProfile` / `accounts.User`), assignment role (`primary_assigned`, `secondary_relief`, `temporary_loaner`, `pool_driver`), assignment start datetime, assignment end datetime, starting odometer, ending odometer, and assignment status (`active`, `completed`, `revoked_safety`, `transferred`) · seen in: Fleetio, Motive, Samsara · priority: `table-stakes` · spine: `new table VehicleDriverAssignment [VDRV-]` + reuses `hrm.EmployeeProfile`, `accounts.User` · `buildable now`
- **Driver License, Medical Card & Safety Certification Tracking** — Validates and records driver commercial license (CDL / standard DL) number, state of issuance, license class (`class_a_cdl`, `class_b_cdl`, `class_c_cdl`, `standard_non_cdl`), license expiration date, DOT medical examiner certificate expiration date, hazmat endorsement status, and driver qualification status (`qualified`, `expiring_soon`, `expired_disqualified`, `suspended`) · seen in: Motive, Chevin FleetWave, Samsara · priority: `table-stakes` · spine: `new table VehicleDriverAssignment` · `buildable now`
- **Driver Safety Scorecard & Behavior Telematics** — Calculates and tracks rolling driver safety score (0–100 index), speeding event count, harsh acceleration count, harsh braking count, harsh cornering count, seatbelt non-compliance count, and safety tier (`exemplary`, `good`, `needs_coaching`, `high_risk`) · seen in: Samsara, Motive, Verizon Connect · priority: `table-stakes` · spine: `new table VehicleDriverAssignment` · `buildable now`
- **HOS & Duty Status Log** — Records current Hours of Service duty status (`off_duty`, `sleeper_berth`, `driving`, `on_duty_not_driving`), shift start datetime, driving minutes in shift, on-duty minutes, and violation alert flag · seen in: Motive, Samsara, Omnitracs · priority: `common` · spine: `new table VehicleDriverAssignment` · `buildable now`
- **AI Dashcam Real-Time Coaching & In-Cab Voice Alerts** — Edge AI video processing detecting mobile phone use, drowsiness, and lane departure with automated in-cab audio coaching · seen in: Samsara, Motive, Verizon Connect · priority: `differentiator` · spine: `integration/later` · `integration/later`

### 4. Maintenance & Service Scheduling
*(Oil changes, tire rotations, and manufacturer service intervals)*

- **Preventive Service Interval & Maintenance Schedule** — Manages scheduled vehicle services categorized by service type (`engine_oil_filter`, `tire_rotation_balance`, `brake_pad_rotor_service`, `transmission_fluid_service`, `coolant_flush`, `air_cabin_filter`, `annual_dot_inspection`, `emissions_test`, `spark_plug_replacement`, `battery_electrical_check`, `wheel_alignment`, `general_preventive_pm`), interval mileage (e.g., every 5,000 miles), interval months (e.g., every 6 months), interval engine hours, baseline service date/odometer, next service due date, next service due odometer, and schedule status (`active_tracking`, `due_soon`, `overdue`, `in_service`, `paused`, `completed`) · seen in: Fleetio, Trimble TMT, Chevin FleetWave · priority: `table-stakes` · spine: `new table VehicleServiceSchedule [VSRV-]` + reuses `assets.AssetMaintenanceSchedule`, `assets.AssetServiceContract` · `buildable now`
- **Service Work Order Execution & Shop Workflow** — Tracks maintenance provider (`core.Party` internal shop or outsourced commercial dealer/mechanic), assigned technician, service priority (`emergency_safety`, `high_priority`, `normal_routine`, `scheduled_pm`), scheduled service date, completed date, completion odometer, estimated cost, actual cost, currency (`accounting.Currency`), work order invoice reference, warranty covered flag (`is_warranty_covered` linking to `assets.AssetWarranty`), and technician resolution notes · seen in: Fleetio, Trimble, Chevin FleetWave · priority: `table-stakes` · spine: `new table VehicleServiceSchedule` + reuses `core.Party`, `accounting.Currency`, `assets.AssetWarranty` · `buildable now`
- **Service Completion & Schedule Roll-Forward** — POST action `complete_service` that validates service completion, records actual costs, links to audit log, and automatically rolls forward the next due date and due odometer based on the defined interval · seen in: Fleetio, Trimble · priority: `table-stakes` · spine: `new table VehicleServiceSchedule` · `buildable now`
- **Predictive AI Diagnostic Trouble Code (DTC) Failure Prediction** — Machine learning algorithms forecasting starter/alternator/battery failure from CAN-bus voltage curves · seen in: Geotab, Fleetio · priority: `differentiator` · spine: `integration/later` · `integration/later`

### 5. Telematics & GPS Monitoring
*(Real-time location, geofencing, speed monitoring, and idle time analysis)*

- **Vehicle Telematics Profile & Live Geolocation State** — Stores current telematics tracking device ID, serial, protocol (`obd2_dongle`, `j1939_heavy_duty`, `hardwired_gps_tracker`, `mobile_app_gps`, `satellite_hybrid`), telemetry sync enabled (`is_telematics_enabled`), current latitude (`DecimalField`), current longitude (`DecimalField`), current address/location description, current heading/bearing, current speed (MPH), last telemetry ping timestamp (`last_telemetry_at`), current engine state (`engine_off`, `idling`, `moving_normal`, `speeding_alert`, `towed_unauthorized`), current odometer, and current fuel/battery state-of-charge percentage · seen in: Samsara, Geotab, Verizon Connect, Teletrac Navman · priority: `table-stakes` · spine: fields on `FleetVehicle` · `buildable now`
- **Speed Monitoring, Idle Time & Geofence Status** — Tracks excessive speed alert threshold (MPH), current trip idle time (minutes), daily total idle time (minutes), assigned geofence zone name, and geofence status (`inside_zone`, `outside_zone`, `geofence_breach_alert`) · seen in: Samsara, Verizon Connect, Geotab · priority: `table-stakes` · spine: fields on `FleetVehicle` · `buildable now`
- **Fleet Telematics & Dispatch Command Board (`fleet_telematics_board`)** — Dedicated interactive dashboard view summarizing real-time fleet operations: live active fleet map coordinates, fleet operational status counts (in service vs in shop vs available), overdue DMV registrations, overdue service alerts, high-risk driver safety scorecards, fuel efficiency KPIs, and speed/idle alerts · seen in: Samsara Fleet Dashboard, Verizon Connect Reveal Live Map, Fleetio Dashboard · priority: `differentiator` · spine: computed view & template over `FleetVehicle`, `VehicleFuelLog`, `VehicleDriverAssignment`, `VehicleServiceSchedule` · `buildable now`

---

## Recommended build scope (this pass — 4 models + 1 operational board)

### 1. `FleetVehicle` (`FLT-`)
- **Justified by:** Vehicle Registration & Compliance, DMV Records, Telematics & GPS Monitoring, TCO & Fleet Assets.
- **Auto-number prefix:** `FLT` (e.g. `FLT-00001`).
- **Verified FKs:**
  - `operational_asset`: `scm.Asset` (optional link to general physical asset)
  - `fixed_asset`: `accounting.FixedAsset` (optional link to financial fixed asset)
  - `asset_category`: `assets.AssetCategory` (optional vehicle category)
  - `asset_model`: `assets.AssetModel` (optional vehicle model)
  - `org_unit`: `core.OrgUnit` (operating department/branch)
  - `primary_driver`: `hrm.EmployeeProfile` (assigned primary driver)
  - `custodian_party`: `core.Party` (assigned party / external custodian)
- **Computed properties:** `is_registration_expired`, `is_registration_due_soon`, `is_service_overdue`, `effective_fuel_economy_mpg`, `telematics_status_display`.

### 2. `VehicleFuelLog` (`VFUL-`)
- **Justified by:** Fuel & Mileage Tracking, Fuel Card Integration, MPG & Consumption Analysis, Route Efficiency.
- **Auto-number prefix:** `VFUL` (e.g. `VFUL-00001`).
- **Verified FKs:**
  - `vehicle`: `FleetVehicle` (mandatory)
  - `driver`: `hrm.EmployeeProfile` (optional driver at fill-up)
  - `fuel_vendor`: `core.Party` (optional fuel vendor / service station)
  - `currency`: `accounting.Currency` (GLOBAL — optional currency)
- **Computed properties:** `calculated_mpg`, `cost_per_mile`, `calculated_l_per_100km`.

### 3. `VehicleDriverAssignment` (`VDRV-`)
- **Justified by:** Driver Assignment & Safety, Driver Qualification, Safety Score Tracking, HOS & Duty Status.
- **Auto-number prefix:** `VDRV` (e.g. `VDRV-00001`).
- **Verified FKs:**
  - `vehicle`: `FleetVehicle` (mandatory)
  - `driver`: `hrm.EmployeeProfile` (mandatory assigned employee)
  - `user`: `accounts.User` (optional user account link)
- **Computed properties:** `is_license_expired`, `is_license_expiring_soon`, `is_medical_expired`, `is_active_assignment`, `safety_tier_badge`.

### 4. `VehicleServiceSchedule` (`VSRV-`)
- **Justified by:** Maintenance & Service Scheduling, Preventive Maintenance, Oil Changes, Tire Rotations, DOT Inspections.
- **Auto-number prefix:** `VSRV` (e.g. `VSRV-00001`).
- **Verified FKs:**
  - `vehicle`: `FleetVehicle` (mandatory)
  - `service_vendor`: `core.Party` (optional outsourced shop / mechanic)
  - `warranty`: `assets.AssetWarranty` (optional warranty link)
  - `maintenance_schedule`: `assets.AssetMaintenanceSchedule` (optional link to general asset maintenance schedule)
  - `currency`: `accounting.Currency` (GLOBAL — optional currency)
- **Computed properties:** `is_overdue`, `is_due_soon`, `days_until_due`, `miles_until_due`.

### 5. Fleet Telematics & Dispatch Command Board (`fleet_telematics_board`)
- **Justified by:** Telematics & GPS Monitoring, Fleet Readiness, Safety & Maintenance Executive Command Center.
- **View & Template:** `views/FleetVehicleManagement/FleetTelematicsBoards.py` + `templates/assets/fleetvehiclemanagement/fleet_telematics_board.html`.
- **Wired in navigation:** Maps all 5 `11.19` NavERP bullets in `apps/core/navigation.py`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **General Fixed Asset Depreciation & Financial Book Value** → Sub-module `11.4 Depreciation & Financial Management` (`AssetDepreciationSchedule`).
- **General Equipment Maintenance Work Orders & Failure Modes** → Sub-module `11.5 Maintenance & Repair Management` & `11.7 Asset Reliability` (`AssetMaintenanceLog`, `AssetFailureMode`).
- **Fleet Insurance Policies & Claims Management** → Sub-module `11.8 Warranty & Insurance Management` (`AssetInsurancePolicy`, `AssetInsuranceClaim`).
- **Fleet Vehicle Disposal & Auction Resale** → Sub-module `11.9 Asset Disposal & Retirement` (`AssetDisposalRequest`, `AssetResaleListing`).
- **Fleet Vehicle Leasing & Long-Term Rental Contracts** → Sub-module `11.10 Lease & Rental Management` (`AssetLeaseContract`).
- **Mobile Handheld RFID / Barcode Scanners & Field Inspections** → Sub-module `11.13 Mobile Asset Management` (`MobileAssetInspection`, `AssetGeofenceEvent`).
- **Third-Party GPS / Telematics Ingestion Connectors** → Sub-module `11.15 Integration & API Hub` (`AssetIntegrationConnector`, `AssetTelemetryStream`).

---

## Deferred (later passes / integrations)

- **Direct CAN-bus Hardware Interface** — Real-time continuous J1939 streaming requires edge hardware gateways.
- **Automated WEX / Comdata Fuel Card Clearinghouse API** — Requires commercial merchant clearinghouse contracts and OAuth credentials.
- **Direct State DMV Registration Renewal Payment Gateway** — Requires state government API partnerships.
- **AI Dashcam Video Streaming & Collision Clip Vault** — High-bandwidth video storage and streaming infrastructure.

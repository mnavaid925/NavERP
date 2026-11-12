# Research — Sub-module 11.17: Space & Facility Asset Management (Module 11 — Asset Management System, `assets`)

**Date:** 2026-11-12
**Target NavERP.md section:** `### 11.17 Space & Facility Asset Management` (Module 11 — Asset Management System, lines 1841–1847)
**App target:** `apps/assets` (`apps/assets/models/SpaceFacilityAsset/`, `templates/assets/...`, `app_name = "assets"`)

---

## Repo state checked first

- **Navigation (`apps/core/navigation.py`):** `LIVE_LINKS` has Module 11 built for `11.1` through `11.16`; `11.17`–`11.19` are unbuilt (`11.17` has no `LIVE_LINKS` entry yet). Module 20 (`Facilities & Workplace Management`, `facilities`) does not exist in `INSTALLED_APPS` or `LIVE_LINKS`.
- **Installed apps (`config/settings.py`):** `core`, `accounts`, `tenants`, `dashboard`, `crm`, `accounting`, `hrm`, `scm`, `inventory`, `procurement`, `projects`, `sales`, `ecommerce`, `bi`, `assets` (`apps/facilities` does not exist).
- **Migrations (`apps/assets/migrations/`):** Latest migration is `0023_assetdocument_idx_adoc_ten_upd_and_more.py` (all `11.1`–`11.16` models migrated; next migration is `0024_*`).
- **Existing `apps/assets` packaging convention:** Sub-modules `11.1`–`11.16` each own a PascalCase sub-package under `apps/assets/models/`, `forms/`, `views/`, and `urls/`, with **4 `TenantNumbered` models** per sub-module (64 existing `Asset*` / `CapitalizationPolicy` models across `11.1`–`11.16`). Base classes in `apps/assets/models/_base.py` provide `TenantOwned` (`tenant`, `created_at`, `updated_at`) and `TenantNumbered` (`NUMBER_PREFIX`, `number`, auto-generated via `next_number` in `save()`).
- **Upload security baseline (`apps/core/forms/_common.py`):** `ALLOWED_DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip"}` (explicitly excluding `.svg` to prevent inline stored XSS under `/media/`) and `MAX_UPLOAD_BYTES = 20 * 1024 * 1024` (20 MB).
- **Verified spine & sibling models (grep-verified across `apps/*/models/` — reuse by string FK, never duplicate):**
  - `core`: `core.Tenant`, `core.Party`, `core.PartyRole`, `core.OrgUnit`, `core.Address`, `core.Document`, `core.Activity`, `core.AuditLog`.
  - `accounts`: `accounts.User` (`settings.AUTH_USER_MODEL`).
  - `accounting`: `accounting.FixedAsset` [`FA-`], `accounting.GLAccount`, `accounting.Currency`, `accounting.FiscalPeriod`, `accounting.JournalEntry` [`JE-`] + `JournalLine`, `accounting.Invoice` [`INV-`], `accounting.Budget`, `accounting.CostAllocation` [`CALLOC-`].
  - `scm`: `scm.Asset` [`AST-`] (`code`, `name`, `asset_type`, `status`, `criticality`, `location`, `org_unit`, `custodian`, `service_vendor`, `fixed_asset`), `scm.Location` (`code`, `name`, `location_type`: `warehouse`/`zone`/`bin`/`staging`/`transit`, `parent`, `capacity`), `scm.MaintenancePlan`, `scm.MaintenanceWorkOrder`.
  - `assets` (`11.1`–`11.16`): `AssetCategory` [`ACAT-`], `AssetModel` [`AMOD-`], `AssetMovementLog` [`AMOV-`], `AssetMaintenanceRequest` [`AMRQ-`], `AssetMaintenanceSchedule` [`AMSC-`], `AssetServiceContract` [`ASVC-`], `AssetEnergyReading` [`AENG-`], `AssetConditionAssessment` [`ACAS-`], `AssetLeaseContract` [`ALC-`], `AssetPermitLicense` [`APL-`], `AssetGisMapping` [`AGIS-`], `AssetDocument` [`ADOC-`], `AssetOperatingProcedure` [`ASOP-`].
- **Boundary checks (why 11.17 adds dedicated models without duplicating existing tables):**
  - `scm.Location` models inventory stock locations (`warehouse`/`zone`/`bin`) for `StockMove` on-hand stock valuation; it does not track BOMA usable/rentable/gross square footage, CAD/BIM floor plans, seat capacity, or HVAC/room-level placement.
  - `assets.AssetGisMapping` (`11.15`) models external GIS FeatureServer synchronization (latitude/longitude, SRID, GeoJSON, LRS linear corridors) for outdoor/utility assets; it does not model indoor architectural building/floor/room spaces or FF&E/MEP room placement.
  - `assets.AssetLeaseContract` (`11.10`) models ASC 842 / IFRS 16 Right-of-Use lease contracts; `11.17` links to it for leasehold improvements and tenant/department space chargebacks while posting financial effects into `accounting.JournalEntry` / `accounting.Invoice` (never a second ledger per L29).
- **Prefix & class collision check:** Scanned all 606 unique `NUMBER_PREFIX` values across `apps/**/models/**/*.py` and all 64 model classes under `apps/assets/models/`. Candidate prefixes **`AFSP`**, **`AFBS`**, **`AFFE`**, and **`AFCB`** are all unused (`FREE`), and proposed class names (`AssetFacilitySpace`, `AssetBuildingSystem`, `AssetFurnitureFixture`, `AssetSpaceChargeback`) have zero collisions.

---

## Leaders surveyed (with source links)

1. **Archibus by Eptura** — [eptura.com](https://www.eptura.com), [autodesk.com](https://www.autodesk.com), [thebuildingpeople.com](https://thebuildingpeople.com)
   - Enterprise IWMS with bi-directional AutoCAD/Revit BIM drawing sync, BOMA space classification (gross/rentable/usable area, vertical penetrations, common areas), individual and group MAC move projects, and automated departmental/tenant space & common-area chargeback allocation.
2. **IBM TRIRIGA (transitioning into Maximo Real Estate & Facilities)** — [ibm.com](https://www.ibm.com/products/tririga), [ibm.com/docs](https://www.ibm.com/docs)
   - CAD Integrator/Publisher for floor plan boundary mapping, HVAC/building system asset linking to spatial hierarchies, capital project tracking for leasehold improvements (TI allowances & amortization), and multi-basis space/utility chargebacks routed to ERP journals.
3. **Planon** — [planonsoftware.com](https://planonsoftware.com), [mrisoftware.com](https://www.mrisoftware.com)
   - Smart-building IWMS integrating CAD/BIM digital twins, IoT environmental/HVAC comfort and energy optimization, MEP preventive/condition maintenance routines, and real-estate space allocation & financial chargebacks.
4. **Nuvolo (Connected Workplace on ServiceNow)** — [nuvolo.com](https://www.nuvolo.com), [facilio.com](https://facilio.com)
   - Unifies space planning, floor-plan asset mapping, MEP/HVAC critical environment compliance (cleanrooms, data center power/cooling redundancy), and move management workflows on a shared enterprise data model.
5. **FM:Systems (Eptura) & SpaceIQ** — [fmsystems.com](https://www.fmsystems.com), [eptura.com](https://www.eptura.com), [vlogicsystems.com](https://www.vlogicsystems.com)
   - Visual CAD/Revit floor-plan space management, stacking/reconfiguration scenario planning, occupancy utilization analytics, structured employee/FF&E move queues, and departmental space cost-allocation reporting.
6. **AkitaBox** — [akitabox.com](https://www.akitabox.com), [capterra.com](https://www.capterra.com)
   - Pin-based visual floor-plan digital twin for MEP infrastructure (AHUs, boilers, electrical switchgear, plumbing valves, elevators) linked to O&M manuals, warranties, Facility Condition Assessments (FCA), and Remaining Useful Life (RUL) capital planning.
7. **MRI Software (ManhattanONE)** — [mrisoftware.com](https://www.mrisoftware.com), [capterra.com](https://www.capterra.com)
   - Enterprise real estate and IWMS platform connecting floor-plan space hierarchies, personnel/FF&E move modules, leasehold improvement accounting, CAM/utility pro-rata recovery, and native GL/AR chargeback billing.
8. **ServiceNow Workplace Service Delivery (WSD)** — [servicenow.com](https://www.servicenow.com)
   - Indoor mapping for floors/zones/rooms, neighborhood space allocation, employee-to-facilities service routing for HVAC comfort or elevator faults, and coordinated workplace move workflows.
9. **AssetWorks AiM** — [assetworks.com](https://www.assetworks.com), [facilio.com](https://facilio.com)
   - Campus and public-sector IWMS/EAM for central utility plants (chillers, boilers, HV electrical distribution), structural/vertical infrastructure registers, FCA condition grading, and deferred maintenance backlog tracking.

---

## Feature catalog (this sub-module only)

### 1. Floor Plan & Space Mapping
*(CAD/BIM integration, room-level asset placement, and space utilization)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Architectural Space Hierarchy (`site_building -> floor -> wing_zone -> room`) typed by BOMA/space category (office, conference, mechanical room, electrical closet, HVAC zone, cleanroom, lab, lobby/common, warehouse bay, server room) | Archibus, IBM TRIRIGA, ServiceNow WSD | `table-stakes` | `core.OrgUnit`, optional `scm.Location`, optional `assets.AssetGisMapping` | Buildable now |
| Area measurement & BOMA metrics (`gross_area_sqft`, `rentable_area_sqft`, `usable_area_sqft`, `common_area_sqft`) and cost-per-sqft basis (`annual_rate_per_sqft`) | Archibus, IBM TRIRIGA, FM:Systems | `table-stakes` | — | Buildable now |
| CAD/BIM & drawing reference linkage (`cad_layer_ref`, `bim_guid`, `bim_level_ref`, `drawing_revision`, `floor_plan_document` FK to `assets.AssetDocument`, safe `floor_plan_image` upload) | Archibus, IBM TRIRIGA, Planon | `table-stakes` | `assets.AssetDocument` (`ADOC-`), `apps/core/forms/_common.py` upload rules | Buildable now |
| Room-level asset placement & pin coordinates (`pin_x_pct`, `pin_y_pct` on placed assets/systems/FF&E, plus space-level placed asset rollups) | AkitaBox, Nuvolo, ServiceNow WSD | `common` | `AssetFacilitySpace`, `AssetBuildingSystem`, `AssetFurnitureFixture` | Buildable now |
| Space capacity & utilization tracking (`design_seat_capacity`, `current_headcount`, `utilization_pct` computed, `occupancy_status`: `occupied`, `underutilized`, `vacant`, `reserved_reconfig`, `offline`) | FM:Systems, SpaceIQ, Archibus | `table-stakes` | `core.OrgUnit` | Buildable now |
| Live bidirectional AutoCAD `.dwg` / Autodesk Revit `.rvt` IFC geometry parser & interactive WebGL 3D BIM viewer | Archibus, Planon, Autodesk Tandem | `differentiator` | — | Integration/later |

### 2. HVAC & Building Systems
*(Climate control assets, energy management, and comfort optimization)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Dedicated HVAC & climate-control asset register (`ahu_air_handler`, `chiller_plant`, `boiler_heating`, `rooftop_unit`, `vav_terminal`, `split_heat_pump`, `bms_controller`) linked to served `AssetFacilitySpace` zones and `scm.Asset` | Planon, IBM TRIRIGA, Nuvolo | `table-stakes` | `scm.Asset`, `accounting.FixedAsset`, `AssetFacilitySpace` | Buildable now |
| Climate & comfort optimization parameters (`served_area_sqft`, `design_capacity_btu_kw`, `setpoint_temp_c`, `measured_temp_c`, `target_humidity_pct`, `measured_humidity_pct`, `airflow_cfm`, `refrigerant_type`, `energy_efficiency_rating`) and comfort band status (`optimal`, `drift_warning`, `out_of_comfort_band`, `offline`) | Planon, Nuvolo, ServiceNow WSD | `common` | `AssetBuildingSystem` | Buildable now |
| Energy & utility consumption linkage connecting HVAC/MEP equipment to `assets.AssetEnergyReading` (`11.6`) and `assets.AssetMaintenanceSchedule` (`11.5`) | Planon, IBM TRIRIGA, NavERP `11.6` | `table-stakes` | `assets.AssetEnergyReading` (`AENG-`), `assets.AssetMaintenanceSchedule` (`AMSC-`) | Buildable now |
| Live BACnet / Modbus / BMS building automation loop executing real-time damper/chiller setpoint overrides | Planon, Nuvolo | `differentiator` | `11.15` `AssetTelemetryStream` | Integration/later |

### 3. Furniture & Fixture Tracking
*(FF&E inventory, move management, and reconfiguration planning)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Movable FF&E asset catalog & room inventory (`workstation_desk`, `ergonomic_seating`, `conference_table`, `modular_partition`, `storage_cabinet`, `av_display_fixture`, `lighting_fixture`, `lab_casework`, `reception_millwork`) with `quantity`, `unit_replacement_cost`, `manufacturer`, `model_sku`, `finish_material`, and floor-plan pin coordinates | Archibus, MRI ManhattanONE, FM:Systems | `table-stakes` | `AssetFacilitySpace`, optional `scm.Asset`, optional `accounting.FixedAsset` | Buildable now |
| Move Management (MAC — Move, Add, Change) workflow (`move_status`: `in_place`, `move_requested`, `scheduled_reconfig`, `in_transit`, `relocated`, `in_storage`, `retired`; `target_space`, `move_scheduled_date`, `move_completed_at`, `move_notes`) with atomic POST actions (`request_move`, `schedule_move`, `complete_move` updating `facility_space` to `target_space` and optionally logging `AssetMovementLog`) | Archibus, FM:Systems, MRI ManhattanONE, SpaceIQ | `table-stakes` | `assets.AssetMovementLog` (`AMOV-`), `core.Party`, `core.OrgUnit` | Buildable now |
| Reconfiguration batch & layout planning (`reconfiguration_batch_ref`, `reconfig_phase`, `estimated_move_cost`) grouping bulk FF&E relocations for floor restacks | FM:Systems, Archibus, SpaceIQ | `common` | `AssetFurnitureFixture` | Buildable now |

### 4. Infrastructure Asset Management
*(Elevators, electrical, plumbing, and structural asset registers)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| MEP, vertical transport & structural infrastructure register (`system_domain`: `hvac_climate`, `electrical_power`, `plumbing_water`, `elevator_vertical`, `fire_life_safety`, `structural_envelope`, `bms_controls`, `backup_generation`) covering switchgear, transformers, UPS/generators, booster pumps, elevators, sprinkler risers, roofs, and facades | AkitaBox, AssetWorks AiM, Planon | `table-stakes` | `scm.Asset`, `accounting.FixedAsset`, `AssetFacilitySpace`, `core.Party` (`service_vendor`) | Buildable now |
| Facility Condition Assessment (FCA) & capital planning fields (`condition_grade`: `excellent`/`good`/`fair`/`poor`/`critical`, `remaining_useful_life_years`, `replacement_cost_estimate`, `criticality_tier`) | AkitaBox, AssetWorks AiM | `common` | `assets.AssetConditionAssessment` (`ACAS-`) | Buildable now |
| Statutory code & inspection readiness (`ashrae_nfpa_code_ref`, `load_or_voltage_rating`, `last_statutory_inspection_date`, `next_inspection_due_date`, optional FK to `assets.AssetPermitLicense` and `assets.AssetDocument`) | AkitaBox, Nuvolo, AssetWorks AiM | `table-stakes` | `assets.AssetPermitLicense` (`APL-`), `assets.AssetDocument` (`ADOC-`) | Buildable now |

### 5. Tenant & Occupancy Coordination
*(Leasehold improvements, shared asset allocation, and charge-back management)*

| Feature | Seen in | Priority | Spine reuse | Status |
|---|---|---|---|---|
| Space & shared-asset cost allocation (`coordination_type`: `space_chargeback`, `shared_asset_allocation`, `cam_utility_recovery`, `leasehold_improvement`, `ti_allowance_amortization`) with multi-basis split (`usable_sqft`, `rentable_sqft`, `headcount`, `submeter_usage`, `fixed_split_pct`, `direct_ti_cost`) | Archibus, IBM TRIRIGA, MRI ManhattanONE | `table-stakes` | `AssetFacilitySpace`, `AssetBuildingSystem`, `core.OrgUnit`, `core.Party` | Buildable now |
| Leasehold improvement (TI) & allowance tracking (`ti_improvement_cost`, `ti_allowance_offset`, `amortization_end_date`, `fixed_asset` FK for capitalized leasehold improvements, `lease_contract` FK to `assets.AssetLeaseContract`) | IBM TRIRIGA, MRI ManhattanONE | `common` | `assets.AssetLeaseContract` (`ALC-`), `accounting.FixedAsset` (`FA-`) | Buildable now |
| Chargeback calculation & accounting ledger integration (`base_cost_amount`, `shared_cam_amount`, `utility_recovery_amount`, computed `net_chargeback_amount`, `currency`, `fiscal_period`, `expense_gl_account`, `recovery_gl_account`, POST `post_chargeback` generating a balanced `accounting.JournalEntry` + two `JournalLine`s, optional `accounting.Invoice` linkage) | IBM TRIRIGA, MRI ManhattanONE, NavERP L29 | `table-stakes` | `accounting.JournalEntry`, `accounting.JournalLine`, `accounting.GLAccount`, `accounting.FiscalPeriod`, `accounting.Currency`, `accounting.Invoice` | Buildable now |

### Beyond the bullets (differentiators across leaders)
- **Visual room-to-asset & comfort roll-up:** Space detail pages surface all mounted `AssetBuildingSystem` infrastructure, `AssetFurnitureFixture` inventory, pending MAC moves, comfort band drift alerts, and active `AssetSpaceChargeback` allocations for that room/floor.
- **KPI filter chips & formula-safe CSV exports:** Consistent with `apps/assets` `11.14`–`11.16` (vacant/underutilized spaces, comfort-band alerts, overdue statutory MEP inspections, pending MAC moves, unposted chargebacks).

---

## Recommended build scope (this pass — 4 models)

Place all four `TenantNumbered` models in `apps/assets/models/SpaceFacilityAsset/`, strictly scoped by `tenant`, using collision-free 4-letter `NUMBER_PREFIX` constants, enforcing `clean()` tenant-FK validation, `max_length` >= longest choice + headroom, and index/constraint names `<= 30` chars:

1. **`AssetFacilitySpace`** [`AFSP-`] (`AssetFacilitySpaces.py`)
   - **Purpose:** Architectural facility space hierarchy (Building / Floor / Wing / Room / Mechanical Zone), BOMA area metrics, CAD/BIM references, and space utilization tracking (Bullet 1).
   - **Key fields & choices:**
     - `code` (`CharField(32)`), `name` (`CharField(200)`), `space_level` (`building`, `floor`, `wing_zone`, `room`, `mechanical_bay`, `exterior_pad`), `space_category` (`office_workspace`, `conference_meeting`, `mechanical_room`, `electrical_closet`, `hvac_zone`, `cleanroom_lab`, `lobby_common`, `server_idf_room`, `warehouse_bay`, `restroom_utility`).
     - `parent` (`ForeignKey("self", SET_NULL, null=True, blank=True)` with cycle guard in `clean()`), `gross_area_sqft`, `rentable_area_sqft`, `usable_area_sqft`, `common_area_sqft` (`DecimalField(12, 2)`, >= 0), `annual_rate_per_sqft` (`DecimalField(10, 2)`, >= 0).
     - `design_seat_capacity` (`PositiveIntegerField(default=0)`), `current_headcount` (`PositiveIntegerField(default=0)`), `occupancy_status` (`occupied`, `underutilized`, `vacant`, `reserved_reconfig`, `offline`), `status` (`active`, `planned`, `under_renovation`, `decommissioned`).
     - CAD/BIM & drawing refs: `cad_layer_ref` (`CharField(100, blank=True)`), `bim_guid` (`CharField(64, blank=True)`), `bim_level_ref` (`CharField(64, blank=True)`), `drawing_revision` (`CharField(24, blank=True)`), `floor_plan_image` (`FileField`, safe extension & 20 MB cap validation), `notes` (`TextField(blank=True)`).
   - **Verified spine/sibling FKs:** `core.Tenant`, `core.OrgUnit`, `scm.Location` (optional), `assets.AssetGisMapping` (optional), `assets.AssetDocument` (`floor_plan_document`, optional), `accounts.User` (`space_steward`).
   - **Actions:** `recalculate_utilization`, `mark_under_renovation`, `activate`, `decommission`.

2. **`AssetBuildingSystem`** [`AFBS-`] (`AssetBuildingSystems.py`)
   - **Purpose:** HVAC, climate-control, elevator/vertical, electrical, plumbing, fire/life-safety, and structural infrastructure asset register with comfort band optimization and FCA lifecycle metrics (Bullets 2 & 4).
   - **Key fields & choices:**
     - `name` (`CharField(200)`), `system_domain` (`hvac_climate`, `electrical_power`, `plumbing_water`, `elevator_vertical`, `fire_life_safety`, `structural_envelope`, `bms_controls`, `backup_generation`), `subsystem_type` (`ahu_air_handler`, `chiller_plant`, `boiler_heating`, `vav_terminal`, `rooftop_unit`, `switchgear_panel`, `transformer_sub`, `ups_battery`, `generator_set`, `booster_pump`, `passenger_elevator`, `freight_elevator`, `sprinkler_riser`, `fire_alarm_panel`, `roof_structural`, `facade_envelope`).
     - Spatial placement & specs: `pin_x_pct` / `pin_y_pct` (`DecimalField(5, 2)`, 0–100 optional), `manufacturer` (`CharField(120, blank=True)`), `model_number` (`CharField(80, blank=True)`), `serial_number` (`CharField(80, blank=True)`), `load_or_voltage_rating` (`CharField(80, blank=True)`), `ashrae_nfpa_code_ref` (`CharField(80, blank=True)`).
     - HVAC/comfort & energy optimization: `served_area_sqft` (`DecimalField(12, 2)`, null/blank), `design_capacity_btu_kw` (`DecimalField(12, 2)`, null/blank), `refrigerant_type` (`CharField(40, blank=True)`), `setpoint_temp_c` / `measured_temp_c` (`DecimalField(5, 2)`, null/blank), `target_humidity_pct` / `measured_humidity_pct` (`DecimalField(5, 2)`, null/blank), `airflow_cfm` (`DecimalField(10, 2)`, null/blank), `energy_efficiency_rating` (`CharField(40, blank=True)`), `comfort_status` (`optimal`, `drift_warning`, `out_of_band`, `offline`, `not_applicable`).
     - Condition & statutory inspection: `condition_grade` (`excellent`, `good`, `fair`, `poor`, `critical`), `remaining_useful_life_years` (`PositiveSmallIntegerField(null=True, blank=True)`), `replacement_cost_estimate` (`DecimalField(16, 2)`, >= 0), `last_statutory_inspection_date`, `next_inspection_due_date`, `status` (`operational`, `degraded`, `under_maintenance`, `standby`, `decommissioned`).
   - **Verified spine/sibling FKs:** `core.Tenant`, `AssetFacilitySpace` (`facility_space`), `scm.Asset` (`operational_asset`, optional), `accounting.FixedAsset` (`fixed_asset`, optional), `assets.AssetEnergyReading` (`latest_energy_reading`, optional), `assets.AssetMaintenanceSchedule` (`maintenance_schedule`, optional), `assets.AssetPermitLicense` (`operating_permit`, optional), `assets.AssetDocument` (`schematic_document`, optional), `core.Party` (`service_vendor`, optional), `core.OrgUnit` (optional).
   - **Actions:** `evaluate_comfort_band`, `record_inspection`, `flag_maintenance`, `decommission`.

3. **`AssetFurnitureFixture`** [`AFFE-`] (`AssetFurnitureFixtures.py`)
   - **Purpose:** Movable FF&E inventory, floor-plan pin placement, MAC move management, and bulk reconfiguration planning (Bullet 3).
   - **Key fields & choices:**
     - `name` (`CharField(200)`), `ffe_category` (`workstation_desk`, `ergonomic_seating`, `conference_table`, `modular_partition`, `storage_cabinet`, `av_display_fixture`, `lighting_fixture`, `lab_casework`, `reception_millwork`), `asset_tag_code` (`CharField(64, blank=True)`), `manufacturer` (`CharField(120, blank=True)`), `model_sku` (`CharField(80, blank=True)`), `finish_material` (`CharField(80, blank=True)`).
     - Inventory & valuation: `quantity` (`PositiveIntegerField(default=1)`), `unit_replacement_cost` (`DecimalField(14, 2)`, >= 0), `pin_x_pct` / `pin_y_pct` (`DecimalField(5, 2)`, 0–100 optional), `condition_grade` (`new`, `good`, `fair`, `worn`, `damaged`).
     - Move & reconfiguration workflow: `move_status` (`in_place`, `move_requested`, `scheduled_reconfig`, `in_transit`, `relocated`, `in_storage`, `retired`), `reconfiguration_batch_ref` (`CharField(64, blank=True)`), `move_scheduled_date` (`DateField`, null/blank), `move_completed_at` (`DateTimeField`, null/blank, `editable=False`), `estimated_move_cost` (`DecimalField(12, 2)`, >= 0), `move_notes` (`TextField(blank=True)`).
   - **Verified spine/sibling FKs:** `core.Tenant`, `AssetFacilitySpace` (`facility_space`, `target_space`), `core.Party` (`custodian_party`, optional), `core.OrgUnit` (`assigned_org_unit`, optional), `scm.Asset` (`operational_asset`, optional), `accounting.FixedAsset` (`fixed_asset`, optional), `assets.AssetMovementLog` (`movement_log`, optional, `editable=False`), `accounts.User` (`move_coordinator`, optional).
   - **Actions:** `request_move`, `schedule_reconfiguration`, `complete_move` (validates `target_space`, shifts `facility_space = target_space`, clears `target_space`, stamps `move_completed_at`), `retire_ffe`.

4. **`AssetSpaceChargeback`** [`AFCB-`] (`AssetSpaceChargebacks.py`)
   - **Purpose:** Tenant & departmental occupancy coordination, leasehold improvement (TI) tracking, shared facility/system allocation, and GL/AR chargeback posting (Bullet 5).
   - **Key fields & choices:**
     - `title` (`CharField(200)`), `coordination_type` (`space_chargeback`, `shared_asset_allocation`, `cam_utility_recovery`, `leasehold_improvement`, `ti_allowance_amortization`), `allocation_basis` (`usable_sqft`, `rentable_sqft`, `headcount`, `submeter_usage`, `fixed_split_pct`, `direct_ti_cost`).
     - Occupancy & TI metrics: `period_start`, `period_end`, `amortization_end_date` (`DateField`, null/blank), `allocated_area_sqft` (`DecimalField(12, 2)`, >= 0), `allocation_share_pct` (`DecimalField(6, 2)`, 0–100).
     - Monetary components: `base_cost_amount`, `shared_cam_amount`, `utility_recovery_amount`, `ti_improvement_cost`, `ti_allowance_offset` (`DecimalField(16, 2)`, >= 0), `net_chargeback_amount` (`DecimalField(16, 2)`, `editable=False` computed in `clean()`/`save()`).
     - Lifecycle & audit: `status` (`draft`, `pending_approval`, `approved`, `posted_to_gl`, `invoiced`, `disputed`, `closed`), `approved_at` (`DateTimeField`, null/blank, `editable=False`), `notes` (`TextField(blank=True)`).
   - **Verified spine/sibling FKs:** `core.Tenant`, `AssetFacilitySpace` (`facility_space`), `AssetBuildingSystem` (`shared_building_system`, optional), `assets.AssetLeaseContract` (`lease_contract`, optional), `accounting.FixedAsset` (`fixed_asset`, optional), `core.OrgUnit` (`charged_org_unit`, optional), `core.Party` (`occupant_party`, optional), `accounting.Currency` (optional), `accounting.FiscalPeriod` (optional), `accounting.GLAccount` (`expense_gl_account`, `recovery_gl_account`, optional), `accounting.JournalEntry` (`journal_entry`, optional, `editable=False`), `accounting.Invoice` (`ar_invoice`, optional), `accounts.User` (`approved_by`, optional, `editable=False`).
   - **Actions:** `submit_approval`, `approve`, `post_chargeback` (creates balanced `accounting.JournalEntry` + two `JournalLine`s when open `FiscalPeriod` and both GL accounts are present, never creating a second ledger), `close`.

### Recommended `LIVE_LINKS["11.17"]` Navigation Mapping (byte-identical to `NavERP.md`)
- `"Floor Plan & Space Mapping"` -> `"assets:asset_facility_space_list"`
- `"HVAC & Building Systems"` -> `"assets:asset_building_system_list"`
- `"Furniture & Fixture Tracking"` -> `"assets:asset_furniture_fixture_list"`
- `"Infrastructure Asset Management"` -> `"assets:asset_infrastructure_board"` *(dedicated filtered/overview board for electrical, elevator, plumbing & structural infrastructure so every sidebar link resolves to a distinct route without duplicate highlighting)*
- `"Tenant & Occupancy Coordination"` -> `"assets:asset_space_chargeback_list"`

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **11.18 IT Asset Management (ITAM):** Servers, laptops, network switches, software licenses, cloud subscriptions, and CMDB CI dependencies (`AssetFacilitySpace` can host a `server_idf_room`, while IT hardware/software/CMDB belong to `11.18`).
- **11.19 Fleet & Vehicle Management:** DMV registration, fuel cards, driver logs, and vehicle telematics.
- **11.4 Depreciation / 11.5 Maintenance / 11.6 Energy / 11.10 Lease Accounting / 11.15 GIS / 11.16 Documents:** Depreciation schedules (`ADEP-`), work order execution (`AMRQ-`), smart-meter energy readings (`AENG-`), ASC 842 lease schedules (`ALC-`), outdoor GIS layers (`AGIS-`), and controlled document revision chains (`ADOC-`) remain in their owning sub-modules; `11.17` links to them via nullable FKs.
- **Module 20 Facilities & Workplace Management (`20.1`–`20.20`):** Employee hot-desking/meeting-room booking (`20.10`), visitor pre-registration & badge printing (`20.8`), janitorial cleaning routes (`20.6`), security access-control zones (`20.7`), and employee workplace experience portals (`20.19`) belong to future Module 20 (`facilities`).

---

## Deferred (later passes / integrations)

- **Interactive AutoCAD `.dwg` / Revit `.rvt` / IFC CAD-BIM Parser & 2D/3D Floor Plan Canvas:** Server-side CAD/IFC geometry extraction and interactive SVG/WebGL pin-drop UI; current pass stores CAD/BIM identifiers, BOMA square footages, safe floor-plan attachments, and numeric `pin_x_pct`/`pin_y_pct` coordinates cleanly.
- **Live BMS / BACnet / Modbus HVAC Telemetry Loop:** Continuous automated setpoint optimization and comfort-drift alerting via `11.15` `AssetTelemetryStream` brokers; current pass ships explicit setpoint vs. measured evaluation via `evaluate_comfort_band`.
- **Automated Recurring Monthly CAM & Chargeback Batch Scheduler:** Cron/Celery monthly billing runs generating bulk `AssetSpaceChargeback` and `accounting.Invoice` batches per tenant/department.

# Module 11.17 Pre-Build Contract — Space & Facility Asset Management (`apps/assets/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, download hardening header, `AuditLog.action` verb (`<= 10` chars),
> and `LIVE_LINKS["11.17"]` entry below is authoritative across backend, templates, smoke tests,
> reviews, and unit/security tests.

- **Parent App**: `apps.assets` (existing app; NO scaffold; NO `config/settings.py` or `config/urls.py` edit)
- **Previous Migration**: `0023_assetdocument_idx_adoc_ten_upd_and_more`
- **Next Migration**: `0024_...` (verify via `makemigrations assets --dry-run` in Phase 3.4)
- **Package Directories**:
  - `apps/assets/models/SpaceFacilityAsset/`
  - `apps/assets/forms/SpaceFacilityAsset/`
  - `apps/assets/views/SpaceFacilityAsset/`
  - `apps/assets/urls/SpaceFacilityAsset/`
  - `templates/assets/spacefacilityasset/{asset_facility_space,asset_building_system,asset_furniture_fixture,asset_space_chargeback}/{list,detail,form}.html` + `templates/assets/spacefacilityasset/infrastructure_board.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"recalc"`, `"renovate"`, `"activate"`, `"decomm"`, `"comfort"`, `"inspect"`, `"maint"`, `"restore"`, `"req_move"`, `"sched_mv"`, `"comp_move"`, `"retire"`, `"submit"`, `"approve"`, `"post_gl"`, `"dispute"`, `"close"` (every verb `<= 9` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & Downloads Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Never expose raw `{{ space.floor_plan_image.url }}`. Floor plan uploads validate against `ALLOWED_DOC_EXTENSIONS` (excludes `.svg`) and `MAX_UPLOAD_BYTES` (20 MB), and downloads route through `@login_required` tenant-scoped `asset_facility_space_floor_plan_download` returning `FileResponse(..., as_attachment=True, filename=...)` with `X-Content-Type-Options: nosniff`.
- **Global `accounting.Currency` Rule (L39)**:
  - `accounting.Currency` is global (NO `tenant` FK). Never filter `Currency` by `tenant` in form `__init__`, and NEVER pass `"currency"` to `reject_foreign(...)` or `validate_tenant_fks(...)`.

---

## 1. Models & Choices Contract (`apps/assets/models/SpaceFacilityAsset/`)

All 4 models inherit `apps.assets.models._base.TenantNumbered` (provides `tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, and collision-retrying `save()`).

### 1.1 `AssetFacilitySpace` (`AssetFacilitySpaces.py`)
- **`NUMBER_PREFIX`**: `"AFSP"`
- **`Meta.ordering`**: `["code", "name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Facility Space"` / `"Facility Spaces"`
- **Choices & Badge Maps**:
  - `SPACE_LEVEL_CHOICES` (`max_length=24`, max value len 14):
    - `("building", "Building / Structure")`
    - `("floor", "Floor / Level")`
    - `("wing_zone", "Wing / Fire Zone")`
    - `("room", "Room / Suite")`
    - `("mechanical_bay", "Mechanical / Utility Bay")`
    - `("exterior_pad", "Exterior Pad / Yard")`
  - `SPACE_CATEGORY_CHOICES` (`max_length=32`, max value len 18):
    - `("office_workspace", "Office / Workstation")`
    - `("conference_meeting", "Conference / Meeting")`
    - `("mechanical_room", "Mechanical / Plant Room")`
    - `("electrical_closet", "Electrical / Switchgear Room")`
    - `("hvac_zone", "HVAC Thermal Zone")`
    - `("cleanroom_lab", "Cleanroom / Laboratory")`
    - `("lobby_common", "Lobby / Common Area")`
    - `("server_idf_room", "Server / IDF / MDF Room")`
    - `("warehouse_bay", "Warehouse / Storage Bay")`
    - `("restroom_utility", "Restroom / Core Utility")`
  - `OCCUPANCY_STATUS_CHOICES` (`max_length=24`, max value len 17):
    - `("occupied", "Occupied")`
    - `("underutilized", "Underutilized")`
    - `("vacant", "Vacant")`
    - `("reserved_reconfig", "Reserved for Reconfig")`
    - `("offline", "Offline / Renovation")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 16):
    - `("active", "Active")`
    - `("planned", "Planned")`
    - `("under_renovation", "Under Renovation")`
    - `("decommissioned", "Decommissioned")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`, `"planned": "badge-info"`, `"under_renovation": "badge-amber"`, `"decommissioned": "badge-muted"`
  - `OCCUPANCY_CSS`:
    - `"occupied": "badge-green"`, `"underutilized": "badge-amber"`, `"vacant": "badge-info"`, `"reserved_reconfig": "badge-slate"`, `"offline": "badge-red"`
  - `SPACE_LEVEL_CSS`:
    - `"building": "badge-info"`, `"floor": "badge-slate"`, `"wing_zone": "badge-slate"`, `"room": "badge-green"`, `"mechanical_bay": "badge-amber"`, `"exterior_pad": "badge-muted"`
  - `EDITABLE_STATUSES = {"planned", "active", "under_renovation"}`
  - `LOCKED_STATUSES = {"decommissioned"}`
- **Fields**:
  - `code`: `CharField(max_length=32)`
  - `name`: `CharField(max_length=200)`
  - `space_level`: `CharField(max_length=24, choices=SPACE_LEVEL_CHOICES, default="room")`
  - `space_category`: `CharField(max_length=32, choices=SPACE_CATEGORY_CHOICES, default="office_workspace")`
  - `parent`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_spaces")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="facility_spaces")`
  - `scm_location`: `ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True, related_name="facility_spaces")`
  - `gis_mapping`: `ForeignKey("assets.AssetGisMapping", on_delete=models.SET_NULL, null=True, blank=True, related_name="facility_spaces")`
  - `floor_plan_document`: `ForeignKey("assets.AssetDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="facility_spaces")`
  - `space_steward`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="stewarded_facility_spaces")`
  - `gross_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `rentable_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `usable_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `common_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `annual_rate_per_sqft`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))`
  - `design_seat_capacity`: `PositiveIntegerField(default=0)`
  - `current_headcount`: `PositiveIntegerField(default=0)`
  - `occupancy_status`: `CharField(max_length=24, choices=OCCUPANCY_STATUS_CHOICES, default="vacant", editable=False)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active", editable=False)`
  - `cad_layer_ref`: `CharField(max_length=100, blank=True)`
  - `bim_guid`: `CharField(max_length=64, blank=True)`
  - `bim_level_ref`: `CharField(max_length=64, blank=True)`
  - `drawing_revision`: `CharField(max_length=24, blank=True)`
  - `floor_plan_image`: `FileField(upload_to="assets/space_floor_plans/%Y/%m/", blank=True, null=True)`
  - `original_floor_plan_name`: `CharField(max_length=255, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_afsp_ten_num_uniq")`
  - `UniqueConstraint(fields=["tenant", "code"], name="assets_afsp_ten_code_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_afsp_ten_stat")`
  - `Index(fields=["tenant", "space_level"], name="idx_afsp_ten_lvl")`
  - `Index(fields=["tenant", "space_category"], name="idx_afsp_ten_cat")`
  - `Index(fields=["tenant", "occupancy_status"], name="idx_afsp_ten_occ")`
  - `Index(fields=["tenant", "parent"], name="idx_afsp_ten_par")`
- **Properties & Helpers**:
  - `utilization_pct` -> `Decimal` (`0.00` when `design_seat_capacity == 0`, else `round((current_headcount / design_seat_capacity) * 100, 2)`)
  - `annual_space_cost` -> `Decimal` (`(rentable_area_sqft or usable_area_sqft or Decimal("0.00")) * (annual_rate_per_sqft or Decimal("0.00"))`)
  - `compute_occupancy_status()` -> returns `"offline"` if `status in ("under_renovation", "decommissioned")`, `"vacant"` if `(current_headcount or 0) == 0`, `"underutilized"` if `(design_seat_capacity or 0) > 0 and utilization_pct < Decimal("50.00")`, else `"occupied"`.
  - `status_badge_class`, `occupancy_badge_class`, `level_badge_class`
  - `is_locked` -> `status in LOCKED_STATUSES`
  - `clean()`: `validate_tenant_fks` on `("parent", "org_unit", "scm_location", "gis_mapping", "floor_plan_document", "space_steward")`; `validate_space_parent_cycle(self, errors)`; non-negative area/rate checks.
  - `save()`: normalizes `code = (self.code or "").strip().upper()`, updates `occupancy_status = self.compute_occupancy_status()`, captures `original_floor_plan_name` when `floor_plan_image` present.

### 1.2 `AssetBuildingSystem` (`AssetBuildingSystems.py`)
- **`NUMBER_PREFIX`**: `"AFBS"`
- **`Meta.ordering`**: `["system_domain", "name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Building System"` / `"Building Systems"`
- **Choices & Badge Maps**:
  - `SYSTEM_DOMAIN_CHOICES` (`max_length=32`, max value len 19):
    - `("hvac_climate", "HVAC & Climate Control")`
    - `("electrical_power", "Electrical & Power Distribution")`
    - `("plumbing_water", "Plumbing & Water Systems")`
    - `("elevator_vertical", "Elevators & Vertical Transport")`
    - `("fire_life_safety", "Fire & Life Safety")`
    - `("structural_envelope", "Structural & Building Envelope")`
    - `("bms_controls", "BMS & Building Controls")`
    - `("backup_generation", "Backup Power & Generation")`
  - `INFRASTRUCTURE_DOMAINS = ("electrical_power", "plumbing_water", "elevator_vertical", "fire_life_safety", "structural_envelope", "bms_controls", "backup_generation")`
  - `SUBSYSTEM_TYPE_CHOICES` (`max_length=32`, max value len 18):
    - `("ahu_air_handler", "Air Handling Unit (AHU)")`
    - `("chiller_plant", "Chiller Plant")`
    - `("boiler_heating", "Boiler / Heating Plant")`
    - `("vav_terminal", "VAV / Fan Coil Terminal")`
    - `("rooftop_unit", "Rooftop Package Unit (RTU)")`
    - `("switchgear_panel", "Main Switchgear / Panelboard")`
    - `("transformer_sub", "Substation Transformer")`
    - `("ups_battery", "UPS / Battery Bank")`
    - `("generator_set", "Standby Generator Set")`
    - `("booster_pump", "Booster / Sump Pump")`
    - `("passenger_elevator", "Passenger Elevator")`
    - `("freight_elevator", "Freight / Service Elevator")`
    - `("sprinkler_riser", "Sprinkler Riser / Suppression")`
    - `("fire_alarm_panel", "Fire Alarm Control Panel")`
    - `("roof_structural", "Roofing / Structural Framing")`
    - `("facade_envelope", "Facade / Building Envelope")`
  - `COMFORT_STATUS_CHOICES` (`max_length=24`, max value len 14):
    - `("optimal", "Optimal Comfort Band")`
    - `("drift_warning", "Drift Warning")`
    - `("out_of_band", "Out of Comfort Band")`
    - `("offline", "System Offline")`
    - `("not_applicable", "Not Applicable (Non-HVAC)")`
  - `CONDITION_GRADE_CHOICES` (`max_length=20`, max value len 9):
    - `("excellent", "A — Excellent")`
    - `("good", "B — Good")`
    - `("fair", "C — Fair")`
    - `("poor", "D — Poor")`
    - `("critical", "F — Critical")`
  - `CRITICALITY_TIER_CHOICES` (`max_length=28`, max value len 19):
    - `("tier_1_life_safety", "Tier 1 — Life Safety")`
    - `("tier_2_mission_crit", "Tier 2 — Mission Critical")`
    - `("tier_3_operational", "Tier 3 — Operational")`
    - `("tier_4_standard", "Tier 4 — Standard")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 17):
    - `("operational", "Operational")`
    - `("degraded", "Degraded")`
    - `("under_maintenance", "Under Maintenance")`
    - `("standby", "Standby")`
    - `("decommissioned", "Decommissioned")`
  - `STATUS_CSS`:
    - `"operational": "badge-green"`, `"degraded": "badge-amber"`, `"under_maintenance": "badge-info"`, `"standby": "badge-slate"`, `"decommissioned": "badge-muted"`
  - `COMFORT_CSS`:
    - `"optimal": "badge-green"`, `"drift_warning": "badge-amber"`, `"out_of_band": "badge-red"`, `"offline": "badge-muted"`, `"not_applicable": "badge-slate"`
  - `CONDITION_CSS`:
    - `"excellent": "badge-green"`, `"good": "badge-info"`, `"fair": "badge-amber"`, `"poor": "badge-red"`, `"critical": "badge-red"`
  - `CRITICALITY_CSS`:
    - `"tier_1_life_safety": "badge-red"`, `"tier_2_mission_crit": "badge-amber"`, `"tier_3_operational": "badge-info"`, `"tier_4_standard": "badge-slate"`
  - `LOCKED_STATUSES = {"decommissioned"}`
- **Fields**:
  - `name`: `CharField(max_length=200)`
  - `system_domain`: `CharField(max_length=32, choices=SYSTEM_DOMAIN_CHOICES, default="hvac_climate")`
  - `subsystem_type`: `CharField(max_length=32, choices=SUBSYSTEM_TYPE_CHOICES, default="ahu_air_handler")`
  - `facility_space`: `ForeignKey("assets.AssetFacilitySpace", on_delete=models.PROTECT, related_name="building_systems")`
  - `pin_x_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `pin_y_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `manufacturer`: `CharField(max_length=120, blank=True)`
  - `model_number`: `CharField(max_length=80, blank=True)`
  - `serial_number`: `CharField(max_length=80, blank=True)`
  - `load_or_voltage_rating`: `CharField(max_length=80, blank=True)`
  - `ashrae_nfpa_code_ref`: `CharField(max_length=80, blank=True)`
  - `served_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `design_capacity_btu_kw`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)`
  - `refrigerant_type`: `CharField(max_length=40, blank=True)`
  - `setpoint_temp_c`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `measured_temp_c`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `target_humidity_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `measured_humidity_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `airflow_cfm`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)`
  - `energy_efficiency_rating`: `CharField(max_length=40, blank=True)`
  - `comfort_status`: `CharField(max_length=24, choices=COMFORT_STATUS_CHOICES, default="not_applicable", editable=False)`
  - `condition_grade`: `CharField(max_length=20, choices=CONDITION_GRADE_CHOICES, default="good")`
  - `criticality_tier`: `CharField(max_length=28, choices=CRITICALITY_TIER_CHOICES, default="tier_3_operational")`
  - `remaining_useful_life_years`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `replacement_cost_estimate`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `last_statutory_inspection_date`: `DateField(null=True, blank=True)`
  - `next_inspection_due_date`: `DateField(null=True, blank=True)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="operational", editable=False)`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `latest_energy_reading`: `ForeignKey("assets.AssetEnergyReading", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `maintenance_schedule`: `ForeignKey("assets.AssetMaintenanceSchedule", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `operating_permit`: `ForeignKey("assets.AssetPermitLicense", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `schematic_document`: `ForeignKey("assets.AssetDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `service_vendor`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="serviced_building_systems")`
  - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="building_systems")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_afbs_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_afbs_ten_stat")`
  - `Index(fields=["tenant", "system_domain"], name="idx_afbs_ten_dom")`
  - `Index(fields=["tenant", "comfort_status"], name="idx_afbs_ten_cmf")`
  - `Index(fields=["tenant", "facility_space"], name="idx_afbs_ten_spc")`
  - `Index(fields=["tenant", "next_inspection_due_date"], name="idx_afbs_ten_insp")`
- **Properties & Helpers**:
  - `compute_comfort_status()`: if `status in ("under_maintenance", "decommissioned", "standby")` -> `"offline"`; if `system_domain not in ("hvac_climate", "bms_controls")` and `setpoint_temp_c is None and target_humidity_pct is None` -> `"not_applicable"`; if `setpoint_temp_c is not None and measured_temp_c is not None`: `temp_diff = abs(measured_temp_c - setpoint_temp_c)` (`> 2.5` -> `"out_of_band"`, `> 1.0` -> `"drift_warning"`); if `target_humidity_pct is not None and measured_humidity_pct is not None`: `hum_diff = abs(measured_humidity_pct - target_humidity_pct)` (`> 10.0` -> `"out_of_band"`, `> 5.0` -> `"drift_warning"`); if any telemetry measured -> `"optimal"`, else `"not_applicable"`.
  - `is_inspection_overdue` -> `bool(self.next_inspection_due_date and self.status != "decommissioned" and self.next_inspection_due_date < timezone.now().date())`
  - `is_locked`, `status_badge_class`, `comfort_badge_class`, `condition_badge_class`, `criticality_badge_class`

### 1.3 `AssetFurnitureFixture` (`AssetFurnitureFixtures.py`)
- **`NUMBER_PREFIX`**: `"AFFE"`
- **`Meta.ordering`**: `["facility_space", "name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Furniture & Fixture"` / `"Furniture & Fixtures"`
- **Choices & Badge Maps**:
  - `FFE_CATEGORY_CHOICES` (`max_length=32`, max value len 18):
    - `("workstation_desk", "Workstation / Desk")`
    - `("ergonomic_seating", "Ergonomic Seating")`
    - `("conference_table", "Conference / Boardroom Table")`
    - `("modular_partition", "Modular Partition / Panel")`
    - `("storage_cabinet", "Filing / Storage Cabinet")`
    - `("av_display_fixture", "AV Display / Smartboard")`
    - `("lighting_fixture", "Architectural Lighting Fixture")`
    - `("lab_casework", "Lab Bench / Casework")`
    - `("reception_millwork", "Reception / Custom Millwork")`
  - `CONDITION_GRADE_CHOICES` (`max_length=20`, max value len 7):
    - `("new", "New")`
    - `("good", "Good")`
    - `("fair", "Fair")`
    - `("worn", "Worn")`
    - `("damaged", "Damaged")`
  - `MOVE_STATUS_CHOICES` (`max_length=28`, max value len 18):
    - `("in_place", "In Place")`
    - `("move_requested", "Move Requested")`
    - `("scheduled_reconfig", "Scheduled Reconfiguration")`
    - `("in_transit", "In Transit")`
    - `("relocated", "Relocated")`
    - `("in_storage", "In Storage")`
    - `("retired", "Retired")`
  - `MOVE_STATUS_CSS`:
    - `"in_place": "badge-green"`, `"move_requested": "badge-amber"`, `"scheduled_reconfig": "badge-info"`, `"in_transit": "badge-amber"`, `"relocated": "badge-green"`, `"in_storage": "badge-slate"`, `"retired": "badge-muted"`
  - `CONDITION_CSS`:
    - `"new": "badge-green"`, `"good": "badge-info"`, `"fair": "badge-amber"`, `"worn": "badge-amber"`, `"damaged": "badge-red"`
  - `LOCKED_STATUSES = {"retired"}`
- **Fields**:
  - `name`: `CharField(max_length=200)`
  - `ffe_category`: `CharField(max_length=32, choices=FFE_CATEGORY_CHOICES, default="workstation_desk")`
  - `asset_tag_code`: `CharField(max_length=64, blank=True)`
  - `manufacturer`: `CharField(max_length=120, blank=True)`
  - `model_sku`: `CharField(max_length=80, blank=True)`
  - `finish_material`: `CharField(max_length=80, blank=True)`
  - `facility_space`: `ForeignKey("assets.AssetFacilitySpace", on_delete=models.PROTECT, related_name="furniture_fixtures")`
  - `target_space`: `ForeignKey("assets.AssetFacilitySpace", on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_furniture_fixtures")`
  - `custodian_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="custodied_furniture_fixtures")`
  - `assigned_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="furniture_fixtures")`
  - `operational_asset`: `ForeignKey("scm.Asset", on_delete=models.SET_NULL, null=True, blank=True, related_name="furniture_fixtures")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="furniture_fixtures")`
  - `movement_log`: `ForeignKey("assets.AssetMovementLog", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="furniture_fixture_moves")`
  - `move_coordinator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="coordinated_ffe_moves")`
  - `quantity`: `PositiveIntegerField(default=1)`
  - `unit_replacement_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))`
  - `pin_x_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `pin_y_pct`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `condition_grade`: `CharField(max_length=20, choices=CONDITION_GRADE_CHOICES, default="good")`
  - `move_status`: `CharField(max_length=28, choices=MOVE_STATUS_CHOICES, default="in_place", editable=False)`
  - `reconfiguration_batch_ref`: `CharField(max_length=64, blank=True)`
  - `move_scheduled_date`: `DateField(null=True, blank=True)`
  - `move_completed_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `estimated_move_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `move_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_affe_ten_num_uniq")`
  - `Index(fields=["tenant", "move_status"], name="idx_affe_ten_mstat")`
  - `Index(fields=["tenant", "ffe_category"], name="idx_affe_ten_cat")`
  - `Index(fields=["tenant", "facility_space"], name="idx_affe_ten_spc")`
  - `Index(fields=["tenant", "reconfiguration_batch_ref"], name="idx_affe_ten_batch")`
- **Properties & Helpers**:
  - `total_replacement_value` -> `(quantity or 0) * (unit_replacement_cost or Decimal("0.00"))`
  - `is_locked`, `move_status_badge_class`, `condition_badge_class`

### 1.4 `AssetSpaceChargeback` (`AssetSpaceChargebacks.py`)
- **`NUMBER_PREFIX`**: `"AFCB"`
- **`Meta.ordering`**: `["-period_start", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Space Chargeback & Occupancy Coordination"` / `"Space Chargebacks & Occupancy Coordination"`
- **Choices & Badge Maps**:
  - `COORDINATION_TYPE_CHOICES` (`max_length=36`, max value len 25):
    - `("space_chargeback", "Departmental Space Chargeback")`
    - `("shared_asset_allocation", "Shared System / Asset Allocation")`
    - `("cam_utility_recovery", "CAM & Utility Recovery")`
    - `("leasehold_improvement", "Leasehold Improvement (TI)")`
    - `("ti_allowance_amortization", "TI Allowance Amortization")`
  - `ALLOCATION_BASIS_CHOICES` (`max_length=24`, max value len 15):
    - `("usable_sqft", "Usable SqFt")`
    - `("rentable_sqft", "Rentable SqFt")`
    - `("headcount", "Headcount / Seats")`
    - `("submeter_usage", "Submeter Usage")`
    - `("fixed_split_pct", "Fixed Percentage Split")`
    - `("direct_ti_cost", "Direct TI Cost")`
  - `STATUS_CHOICES` (`max_length=24`, max value len 16):
    - `("draft", "Draft")`
    - `("pending_approval", "Pending Approval")`
    - `("approved", "Approved")`
    - `("posted_to_gl", "Posted to GL")`
    - `("invoiced", "Invoiced")`
    - `("disputed", "Disputed")`
    - `("closed", "Closed")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`, `"pending_approval": "badge-amber"`, `"approved": "badge-info"`, `"posted_to_gl": "badge-green"`, `"invoiced": "badge-green"`, `"disputed": "badge-red"`, `"closed": "badge-muted"`
  - `EDITABLE_STATUSES = {"draft", "disputed"}`
  - `LOCKED_STATUSES = {"approved", "posted_to_gl", "invoiced", "closed"}`
- **Fields**:
  - `title`: `CharField(max_length=200)`
  - `coordination_type`: `CharField(max_length=36, choices=COORDINATION_TYPE_CHOICES, default="space_chargeback")`
  - `allocation_basis`: `CharField(max_length=24, choices=ALLOCATION_BASIS_CHOICES, default="usable_sqft")`
  - `facility_space`: `ForeignKey("assets.AssetFacilitySpace", on_delete=models.PROTECT, related_name="space_chargebacks")`
  - `shared_building_system`: `ForeignKey("assets.AssetBuildingSystem", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `lease_contract`: `ForeignKey("assets.AssetLeaseContract", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `charged_org_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `occupant_party`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")` *(GLOBAL — NO tenant filter, NOT in `_TENANT_FK_FIELDS`)*
  - `fiscal_period`: `ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `expense_gl_account`: `ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="expense_space_chargebacks")`
  - `recovery_gl_account`: `ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="recovery_space_chargebacks")`
  - `journal_entry`: `ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="space_chargebacks")`
  - `ar_invoice`: `ForeignKey("accounting.Invoice", on_delete=models.SET_NULL, null=True, blank=True, related_name="space_chargebacks")`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `amortization_end_date`: `DateField(null=True, blank=True)`
  - `allocated_area_sqft`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `allocation_share_pct`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal("100.00"))`
  - `base_cost_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `shared_cam_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `utility_recovery_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `ti_improvement_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `ti_allowance_offset`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"))`
  - `net_chargeback_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal("0.00"), editable=False)`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="draft", editable=False)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="approved_space_chargebacks")`
  - `approved_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_afcb_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_afcb_ten_stat")`
  - `Index(fields=["tenant", "coordination_type"], name="idx_afcb_ten_type")`
  - `Index(fields=["tenant", "facility_space"], name="idx_afcb_ten_spc")`
  - `Index(fields=["tenant", "period_start", "period_end"], name="idx_afcb_ten_per")`
- **Computation & Properties**:
  - `compute_net_chargeback()`: `base + cam + utility + max(Decimal("0.00"), ti_cost - ti_offset)`
  - `is_locked`, `can_edit`, `status_badge_class`

---

## 2. Forms Contract (`apps/assets/forms/SpaceFacilityAsset/`)

All 4 forms inherit `(TenantUniqueMixin, TenantModelForm)` and scope every tenant-owned FK queryset in `__init__` strictly to `tenant=self.tenant` (empty queryset when `self.tenant is None`), validating all tenant-owned FKs in `clean()` via `reject_foreign(self, cleaned, ...)`.

- **`AssetFacilitySpaceForm`**:
  - `Meta.fields`: `["code", "name", "space_level", "space_category", "parent", "org_unit", "scm_location", "gis_mapping", "floor_plan_document", "space_steward", "gross_area_sqft", "rentable_area_sqft", "usable_area_sqft", "common_area_sqft", "annual_rate_per_sqft", "design_seat_capacity", "current_headcount", "cad_layer_ref", "bim_guid", "bim_level_ref", "drawing_revision", "floor_plan_image", "notes"]`
  - Excluded: `tenant`, `number`, `occupancy_status`, `status`, `original_floor_plan_name`, `created_at`, `updated_at`.
  - `parent` queryset excludes `self.instance.pk` when editing.
  - `clean_floor_plan_image()` enforces `ALLOWED_DOC_EXTENSIONS` (no `.svg`) and `MAX_UPLOAD_BYTES`.
- **`AssetBuildingSystemForm`**:
  - `Meta.fields`: `["name", "system_domain", "subsystem_type", "facility_space", "pin_x_pct", "pin_y_pct", "manufacturer", "model_number", "serial_number", "load_or_voltage_rating", "ashrae_nfpa_code_ref", "served_area_sqft", "design_capacity_btu_kw", "refrigerant_type", "setpoint_temp_c", "measured_temp_c", "target_humidity_pct", "measured_humidity_pct", "airflow_cfm", "energy_efficiency_rating", "condition_grade", "criticality_tier", "remaining_useful_life_years", "replacement_cost_estimate", "last_statutory_inspection_date", "next_inspection_due_date", "operational_asset", "fixed_asset", "latest_energy_reading", "maintenance_schedule", "operating_permit", "schematic_document", "service_vendor", "org_unit", "notes"]`
  - Excluded: `tenant`, `number`, `comfort_status`, `status`, `created_at`, `updated_at`.
- **`AssetFurnitureFixtureForm`**:
  - `Meta.fields`: `["name", "ffe_category", "asset_tag_code", "manufacturer", "model_sku", "finish_material", "facility_space", "target_space", "custodian_party", "assigned_org_unit", "operational_asset", "fixed_asset", "move_coordinator", "quantity", "unit_replacement_cost", "pin_x_pct", "pin_y_pct", "condition_grade", "reconfiguration_batch_ref", "move_scheduled_date", "estimated_move_cost", "move_notes"]`
  - Excluded: `tenant`, `number`, `move_status`, `move_completed_at`, `movement_log`, `created_at`, `updated_at`.
- **`AssetSpaceChargebackForm`**:
  - `Meta.fields`: `["title", "coordination_type", "allocation_basis", "facility_space", "shared_building_system", "lease_contract", "fixed_asset", "charged_org_unit", "occupant_party", "currency", "fiscal_period", "expense_gl_account", "recovery_gl_account", "ar_invoice", "period_start", "period_end", "amortization_end_date", "allocated_area_sqft", "allocation_share_pct", "base_cost_amount", "shared_cam_amount", "utility_recovery_amount", "ti_improvement_cost", "ti_allowance_offset", "notes"]`
  - Excluded: `tenant`, `number`, `net_chargeback_amount`, `status`, `approved_by`, `approved_at`, `journal_entry`, `created_at`, `updated_at`.
  - Global `Currency`: `self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")` (NOT filtered by tenant, NOT in `reject_foreign`).

---

## 3. URL Routes & Views Contract (`apps/assets/urls/SpaceFacilityAsset/`, `views/SpaceFacilityAsset/`)

Literal paths MUST precede `<int:pk>/` in every URL module.

### 3.1 `AssetFacilitySpaces.py`
- `spaces/` -> `asset_facility_space_list` (`assets:asset_facility_space_list`)
- `spaces/create/` -> `asset_facility_space_create` (`assets:asset_facility_space_create`)
- `spaces/export-csv/` -> `asset_facility_space_export_csv` (`assets:asset_facility_space_export_csv`)
- `spaces/<int:pk>/` -> `asset_facility_space_detail` (`assets:asset_facility_space_detail`)
- `spaces/<int:pk>/edit/` -> `asset_facility_space_edit` (`assets:asset_facility_space_edit`)
- `spaces/<int:pk>/delete/` -> `asset_facility_space_delete` (`assets:asset_facility_space_delete`, `@require_POST`)
- `spaces/<int:pk>/floor-plan/` -> `asset_facility_space_floor_plan_download` (`assets:asset_facility_space_floor_plan_download`)
- `spaces/<int:pk>/recalculate-utilization/` -> `asset_facility_space_recalculate_utilization` (`assets:asset_facility_space_recalculate_utilization`, `@require_POST`)
- `spaces/<int:pk>/mark-renovation/` -> `asset_facility_space_mark_under_renovation` (`assets:asset_facility_space_mark_under_renovation`, `@require_POST`)
- `spaces/<int:pk>/activate/` -> `asset_facility_space_activate` (`assets:asset_facility_space_activate`, `@require_POST`)
- `spaces/<int:pk>/decommission/` -> `asset_facility_space_decommission` (`assets:asset_facility_space_decommission`, `@require_POST`, `@tenant_admin_required`)
- **Context keys**:
  - List: `spaces`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `active_count`, `underutilized_count`, `vacant_count`, `total_usable_sqft`, `level_choices`, `category_choices`, `occupancy_choices`, `status_choices`, `org_units`, `parent_spaces`, `search_query`
  - Detail: `space`, `child_spaces`, `mounted_systems`, `placed_ffe`, `active_chargebacks`, `can_edit`, `can_delete`
  - Form: `form`, `space`, `is_edit`, `title`

### 3.2 `AssetBuildingSystems.py` & `InfrastructureBoard.py`
- `building-systems/` -> `asset_building_system_list` (`assets:asset_building_system_list`)
- `building-systems/create/` -> `asset_building_system_create` (`assets:asset_building_system_create`)
- `building-systems/export-csv/` -> `asset_building_system_export_csv` (`assets:asset_building_system_export_csv`)
- `building-systems/<int:pk>/` -> `asset_building_system_detail` (`assets:asset_building_system_detail`)
- `building-systems/<int:pk>/edit/` -> `asset_building_system_edit` (`assets:asset_building_system_edit`)
- `building-systems/<int:pk>/delete/` -> `asset_building_system_delete` (`assets:asset_building_system_delete`, `@require_POST`)
- `building-systems/<int:pk>/evaluate-comfort/` -> `asset_building_system_evaluate_comfort` (`assets:asset_building_system_evaluate_comfort`, `@require_POST`)
- `building-systems/<int:pk>/record-inspection/` -> `asset_building_system_record_inspection` (`assets:asset_building_system_record_inspection`, `@require_POST`)
- `building-systems/<int:pk>/flag-maintenance/` -> `asset_building_system_flag_maintenance` (`assets:asset_building_system_flag_maintenance`, `@require_POST`)
- `building-systems/<int:pk>/restore-operational/` -> `asset_building_system_restore_operational` (`assets:asset_building_system_restore_operational`, `@require_POST`)
- `building-systems/<int:pk>/decommission/` -> `asset_building_system_decommission` (`assets:asset_building_system_decommission`, `@require_POST`, `@tenant_admin_required`)
- `infrastructure-board/` -> `asset_infrastructure_board` (`assets:asset_infrastructure_board`)
- **Context keys**:
  - List: `systems`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `operational_count`, `comfort_alert_count`, `overdue_inspection_count`, `domain_choices`, `subsystem_choices`, `comfort_choices`, `condition_choices`, `status_choices`, `spaces`, `search_query`
  - Infrastructure Board: `systems`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `critical_life_safety_count`, `poor_critical_condition_count`, `overdue_inspection_count`, `total_replacement_exposure`, `domain_choices`, `condition_choices`, `criticality_choices`, `status_choices`, `spaces`, `search_query`, `today`
  - Detail: `system`, `linked_chargebacks`, `can_edit`, `can_delete`
  - Form: `form`, `system`, `is_edit`, `title`

### 3.3 `AssetFurnitureFixtures.py`
- `furniture-fixtures/` -> `asset_furniture_fixture_list` (`assets:asset_furniture_fixture_list`)
- `furniture-fixtures/create/` -> `asset_furniture_fixture_create` (`assets:asset_furniture_fixture_create`)
- `furniture-fixtures/export-csv/` -> `asset_furniture_fixture_export_csv` (`assets:asset_furniture_fixture_export_csv`)
- `furniture-fixtures/<int:pk>/` -> `asset_furniture_fixture_detail` (`assets:asset_furniture_fixture_detail`)
- `furniture-fixtures/<int:pk>/edit/` -> `asset_furniture_fixture_edit` (`assets:asset_furniture_fixture_edit`)
- `furniture-fixtures/<int:pk>/delete/` -> `asset_furniture_fixture_delete` (`assets:asset_furniture_fixture_delete`, `@require_POST`)
- `furniture-fixtures/<int:pk>/request-move/` -> `asset_furniture_fixture_request_move` (`assets:asset_furniture_fixture_request_move`, `@require_POST`)
- `furniture-fixtures/<int:pk>/schedule-reconfig/` -> `asset_furniture_fixture_schedule_reconfig` (`assets:asset_furniture_fixture_schedule_reconfig`, `@require_POST`)
- `furniture-fixtures/<int:pk>/complete-move/` -> `asset_furniture_fixture_complete_move` (`assets:asset_furniture_fixture_complete_move`, `@require_POST`)
- `furniture-fixtures/<int:pk>/retire/` -> `asset_furniture_fixture_retire` (`assets:asset_furniture_fixture_retire`, `@require_POST`, `@tenant_admin_required`)
- **Context keys**:
  - List: `fixtures`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `pending_move_count`, `in_place_count`, `total_quantity`, `category_choices`, `condition_choices`, `move_status_choices`, `spaces`, `org_units`, `search_query`
  - Detail: `fixture`, `can_edit`, `can_delete`, `can_complete_move`
  - Form: `form`, `fixture`, `is_edit`, `title`

### 3.4 `AssetSpaceChargebacks.py`
- `space-chargebacks/` -> `asset_space_chargeback_list` (`assets:asset_space_chargeback_list`)
- `space-chargebacks/create/` -> `asset_space_chargeback_create` (`assets:asset_space_chargeback_create`)
- `space-chargebacks/export-csv/` -> `asset_space_chargeback_export_csv` (`assets:asset_space_chargeback_export_csv`)
- `space-chargebacks/<int:pk>/` -> `asset_space_chargeback_detail` (`assets:asset_space_chargeback_detail`)
- `space-chargebacks/<int:pk>/edit/` -> `asset_space_chargeback_edit` (`assets:asset_space_chargeback_edit`)
- `space-chargebacks/<int:pk>/delete/` -> `asset_space_chargeback_delete` (`assets:asset_space_chargeback_delete`, `@require_POST`)
- `space-chargebacks/<int:pk>/submit-approval/` -> `asset_space_chargeback_submit_approval` (`assets:asset_space_chargeback_submit_approval`, `@require_POST`)
- `space-chargebacks/<int:pk>/approve/` -> `asset_space_chargeback_approve` (`assets:asset_space_chargeback_approve`, `@require_POST`, `@tenant_admin_required`)
- `space-chargebacks/<int:pk>/post-gl/` -> `asset_space_chargeback_post_gl` (`assets:asset_space_chargeback_post_gl`, `@require_POST`, `@tenant_admin_required`)
- `space-chargebacks/<int:pk>/dispute/` -> `asset_space_chargeback_dispute` (`assets:asset_space_chargeback_dispute`, `@require_POST`)
- `space-chargebacks/<int:pk>/close/` -> `asset_space_chargeback_close` (`assets:asset_space_chargeback_close`, `@require_POST`, `@tenant_admin_required`)
- **Context keys**:
  - List: `chargebacks`, `paginator`, `page_obj`, `is_paginated`, `total_count`, `approved_count`, `posted_count`, `total_net_chargeback`, `coordination_type_choices`, `basis_choices`, `status_choices`, `spaces`, `org_units`, `search_query`
  - Detail: `chargeback`, `can_edit`, `can_delete`, `can_approve`, `can_post_gl`
  - Form: `form`, `chargeback`, `is_edit`, `title`

---

## 4. Navigation & Overview Contract

```python
    "11.17": {
        "Floor Plan & Space Mapping": "assets:asset_facility_space_list",
        "HVAC & Building Systems": "assets:asset_building_system_list",
        "Furniture & Fixture Tracking": "assets:asset_furniture_fixture_list",
        "Infrastructure Asset Management": "assets:asset_infrastructure_board",
        "Tenant & Occupancy Coordination": "assets:asset_space_chargeback_list",
    },
```
Overview KPI keys added to `apps/assets/views/overview.py` (`kpis` dict):
- `total_facility_spaces`, `active_facility_spaces`, `total_building_systems`, `comfort_alert_systems`, `total_furniture_fixtures`, `pending_ffe_moves`, `total_space_chargebacks`, `posted_space_chargebacks`.

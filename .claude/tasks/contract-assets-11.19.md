# Module 11.19 Pre-Build Contract — Fleet & Vehicle Management (`apps/assets/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["11.19"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.assets` (existing app; NO scaffold; NO `config/settings.py` or `config/urls.py` edit)
- **Migration**: Incremental (run `makemigrations assets` in Phase 3.4 Integrate; claims `0026_...`)
- **Package Directories**:
  - `apps/assets/models/FleetVehicleManagement/`
  - `apps/assets/forms/FleetVehicleManagement/`
  - `apps/assets/views/FleetVehicleManagement/`
  - `apps/assets/urls/FleetVehicleManagement/`
  - `templates/assets/fleetvehiclemanagement/{fleet_vehicle,vehicle_fuel_log,vehicle_driver_assignment,vehicle_service_schedule}/{list,detail,form}.html` + `templates/assets/fleetvehiclemanagement/fleet_telematics_board.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, changes=..., tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"activate"`, `"in_shop"`, `"loaner"`, `"out_serv"`, `"decomm"`, `"ping_gps"`, `"complete"`, `"revoke"`, `"incident"`, `"schedule"`, `"in_serv"`, `"pause"` (every verb `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `csv_export_response` using `csv_safe(...)` formula neutralization + `X-Content-Type-Options: nosniff`.
- **Global `accounting.Currency` Rule (L39)**:
  - `accounting.Currency` is global (NO `tenant` FK). Filter ONLY `Currency.objects.filter(is_active=True)` in form `__init__`, and NEVER pass `"currency"` to `reject_foreign(...)` or `_TENANT_FK_FIELDS`.

---

## 1. Models & Choices Contract (`apps/assets/models/FleetVehicleManagement/`)

All 4 models inherit `apps.assets.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `FleetVehicle` (`FleetVehicles.py`)
- **`NUMBER_PREFIX`**: `"FLT"`
- **`Meta.ordering`**: `["name", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Fleet Vehicle"` / `"Fleet Vehicles"`
- **Choices & Badge Maps**:
  - `VEHICLE_TYPE_CHOICES` (`max_length=28`):
    - `("passenger_car", "Passenger Car / Sedan")`
    - `("suv_crossover", "SUV / Crossover")`
    - `("pickup_truck", "Pickup Truck")`
    - `("cargo_van", "Cargo / Delivery Van")`
    - `("box_truck", "Box Truck / Straight Truck")`
    - `("semi_tractor", "Semi-Tractor / Class 8")`
    - `("flatbed_truck", "Flatbed Truck")`
    - `("trailer", "Trailer / Semi-Trailer")`
    - `("forklift_yard", "Forklift / Yard Spotter")`
    - `("bus_shuttle", "Bus / Passenger Shuttle")`
    - `("specialty_equipment", "Specialty Utility Vehicle")`
  - `FUEL_TYPE_CHOICES` (`max_length=24`):
    - `("gasoline", "Gasoline (Petrol)")`
    - `("diesel", "Diesel")`
    - `("electric_ev", "Battery Electric (BEV)")`
    - `("hybrid_electric", "Hybrid Electric (HEV)")`
    - `("plug_in_hybrid", "Plug-in Hybrid (PHEV)")`
    - `("cng_lpg", "CNG / LPG / Autogas")`
  - `OWNERSHIP_TYPE_CHOICES` (`max_length=24`):
    - `("owned", "Company Owned")`
    - `("leased", "Leased")`
    - `("rented", "Short-Term Rental")`
    - `("customer_managed", "Customer / Contractor Managed")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("staged_available", "Staged / Available")`
    - `("active_in_service", "Active In Service")`
    - `("in_shop_maintenance", "In Shop / Maintenance")`
    - `("loaner_out", "Loaner / Temporary Assignment")`
    - `("out_of_service", "Out of Service")`
    - `("pending_disposal", "Pending Disposal")`
    - `("decommissioned", "Decommissioned / Retired")`
  - `COMPLIANCE_STATUS_CHOICES` (`max_length=28`):
    - `("compliant", "Compliant")`
    - `("renewal_due_soon", "Renewal Due Soon")`
    - `("expired_non_compliant", "Expired / Non-Compliant")`
    - `("exempt", "Exempt")`
  - `ENGINE_STATE_CHOICES` (`max_length=24`):
    - `("engine_off", "Engine Off")`
    - `("idling", "Idling")`
    - `("moving_normal", "Moving / In Transit")`
    - `("speeding_alert", "Speeding Alert")`
    - `("towed_unauthorized", "Unauthorized Movement / Towed")`
  - `GEOFENCE_STATUS_CHOICES` (`max_length=28`):
    - `("inside_zone", "Inside Authorized Zone")`
    - `("outside_zone", "Outside Operating Zone")`
    - `("geofence_breach_alert", "Geofence Breach Alert")`
  - `STATUS_CSS`:
    - `"staged_available": "badge-info"`, `"active_in_service": "badge-green"`, `"in_shop_maintenance": "badge-amber"`, `"loaner_out": "badge-info"`, `"out_of_service": "badge-red"`, `"pending_disposal": "badge-slate"`, `"decommissioned": "badge-muted"`
  - `COMPLIANCE_CSS`:
    - `"compliant": "badge-green"`, `"renewal_due_soon": "badge-amber"`, `"expired_non_compliant": "badge-red"`, `"exempt": "badge-slate"`
  - `ENGINE_STATE_CSS`:
    - `"engine_off": "badge-slate"`, `"idling": "badge-amber"`, `"moving_normal": "badge-green"`, `"speeding_alert": "badge-red"`, `"towed_unauthorized": "badge-red"`
  - `GEOFENCE_CSS`:
    - `"inside_zone": "badge-green"`, `"outside_zone": "badge-amber"`, `"geofence_breach_alert": "badge-red"`
  - `LOCKED_STATUSES = {"decommissioned"}`
- **Fields**:
  - `name`: `CharField(max_length=150)`
  - `vin`: `CharField(max_length=24, blank=True)`
  - `license_plate`: `CharField(max_length=32)`
  - `registration_state`: `CharField(max_length=32, blank=True)`
  - `make`: `CharField(max_length=60)`
  - `model`: `CharField(max_length=60)`
  - `year`: `PositiveSmallIntegerField()`
  - `vehicle_type`: `CharField(max_length=28, choices=VEHICLE_TYPE_CHOICES, default="cargo_van")`
  - `fuel_type`: `CharField(max_length=24, choices=FUEL_TYPE_CHOICES, default="gasoline")`
  - `ownership_type`: `CharField(max_length=24, choices=OWNERSHIP_TYPE_CHOICES, default="owned")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="staged_available")`
  - `compliance_status`: `CharField(max_length=28, choices=COMPLIANCE_STATUS_CHOICES, default="compliant")`
  - `title_number`: `CharField(max_length=64, blank=True)`
  - `registration_expiration_date`: `DateField(null=True, blank=True)`
  - `safety_inspection_due_date`: `DateField(null=True, blank=True)`
  - `emissions_inspection_due_date`: `DateField(null=True, blank=True)`
  - `current_odometer`: `PositiveIntegerField(default=0)`
  - `engine_hours`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))`
  - `gross_vehicle_weight_rating_lbs`: `PositiveIntegerField(null=True, blank=True)`
  - `fuel_tank_capacity_gallons`: `DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)`
  - `battery_capacity_kwh`: `DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)`
  - `is_telematics_enabled`: `BooleanField(default=False)`
  - `telematics_device_id`: `CharField(max_length=80, blank=True)`
  - `current_latitude`: `DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)`
  - `current_longitude`: `DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)`
  - `current_location_name`: `CharField(max_length=255, blank=True)`
  - `current_speed_mph`: `DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)`
  - `current_heading`: `PositiveSmallIntegerField(null=True, blank=True)`
  - `last_telemetry_at`: `DateTimeField(null=True, blank=True, editable=False)`
  - `engine_state`: `CharField(max_length=24, choices=ENGINE_STATE_CHOICES, default="engine_off")`
  - `geofence_status`: `CharField(max_length=28, choices=GEOFENCE_STATUS_CHOICES, default="inside_zone")`
  - Verified FKs:
    - `operational_asset`: `ForeignKey("scm.Asset", on_delete=SET_NULL, null=True, blank=True, related_name="fleet_vehicles")`
    - `fixed_asset`: `ForeignKey("accounting.FixedAsset", on_delete=SET_NULL, null=True, blank=True, related_name="fleet_vehicles")`
    - `asset_category`: `ForeignKey("assets.AssetCategory", on_delete=SET_NULL, null=True, blank=True, related_name="fleet_vehicles")`
    - `asset_model`: `ForeignKey("assets.AssetModel", on_delete=SET_NULL, null=True, blank=True, related_name="fleet_vehicles")`
    - `org_unit`: `ForeignKey("core.OrgUnit", on_delete=SET_NULL, null=True, blank=True, related_name="fleet_vehicles")`
    - `primary_driver`: `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True, related_name="assigned_fleet_vehicles")`
    - `custodian_party`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="custody_fleet_vehicles")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_flt_ten_num_uniq")`
  - `Index(fields=["tenant", "status"], name="idx_flt_ten_stat")`
  - `Index(fields=["tenant", "vehicle_type"], name="idx_flt_ten_vtype")`
  - `Index(fields=["tenant", "license_plate"], name="idx_flt_ten_plate")`
  - `Index(fields=["tenant", "registration_expiration_date"], name="idx_flt_ten_regexp")`
- **Properties & Helper Methods**:
  - `is_registration_expired`: bool (returns True if registration_expiration_date < today)
  - `is_registration_due_soon`: bool (returns True if registration_expiration_date within 30 days)
  - `status_badge_class`: str
  - `compliance_badge_class`: str
  - `engine_state_badge_class`: str
  - `geofence_badge_class`: str
  - `is_locked`: bool (`status in LOCKED_STATUSES`)

---

### 1.2 `VehicleFuelLog` (`VehicleFuelLogs.py`)
- **`NUMBER_PREFIX`**: `"VFUL"`
- **`Meta.ordering`**: `["-fuel_date", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Vehicle Fuel Log"` / `"Vehicle Fuel Logs"`
- **Choices & Badge Maps**:
  - `FUEL_TYPE_CHOICES` (`max_length=28`):
    - `("regular_gasoline", "Regular Gasoline (87 Octane)")`
    - `("premium_gasoline", "Premium Gasoline (91+ Octane)")`
    - `("diesel_ultra_low_sulfur", "Ultra-Low Sulfur Diesel (ULSD)")`
    - `("biodiesel", "Biodiesel Blend (B20)")`
    - `("ev_kwh_charging", "EV kWh Fast Charging")`
    - `("def_exhaust_fluid", "Diesel Exhaust Fluid (DEF)")`
    - `("cng", "Compressed Natural Gas (CNG)")`
  - `ROUTE_CATEGORY_CHOICES` (`max_length=24`):
    - `("city_local", "Urban / City Local")`
    - `("highway_longhaul", "Highway / Long Haul")`
    - `("mixed_delivery", "Mixed Route / Delivery")`
    - `("job_site_idle", "Job Site / Heavy Idle")`
  - `EFFICIENCY_RATING_CHOICES` (`max_length=28`):
    - `("optimal", "Optimal / High Efficiency")`
    - `("acceptable", "Acceptable / Normal")`
    - `("excessive_consumption", "Excessive Consumption")`
    - `("anomalous", "Anomalous / Investigation Needed")`
  - `EFFICIENCY_CSS`:
    - `"optimal": "badge-green"`, `"acceptable": "badge-info"`, `"excessive_consumption": "badge-amber"`, `"anomalous": "badge-red"`
- **Fields**:
  - `vehicle`: `ForeignKey("assets.FleetVehicle", on_delete=CASCADE, related_name="fuel_logs")`
  - `driver`: `ForeignKey("hrm.EmployeeProfile", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_fuel_logs")`
  - `fuel_vendor`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_fuel_sales")`
  - `fuel_date`: `DateTimeField()`
  - `odometer_at_fueling`: `PositiveIntegerField()`
  - `fuel_type`: `CharField(max_length=28, choices=FUEL_TYPE_CHOICES, default="regular_gasoline")`
  - `quantity_gallons`: `DecimalField(max_digits=9, decimal_places=3)`
  - `unit_price`: `DecimalField(max_digits=10, decimal_places=3, default=Decimal("0.000"))`
  - `total_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_fuel_logs")` (GLOBAL)
  - `is_full_tank`: `BooleanField(default=True)`
  - `fuel_card_token`: `CharField(max_length=64, blank=True)`
  - `fuel_station_name`: `CharField(max_length=120, blank=True)`
  - `station_city_state`: `CharField(max_length=120, blank=True)`
  - `distance_since_last_fuel`: `PositiveIntegerField(null=True, blank=True)`
  - `calculated_mpg`: `DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)`
  - `route_category`: `CharField(max_length=24, choices=ROUTE_CATEGORY_CHOICES, default="mixed_delivery")`
  - `efficiency_rating`: `CharField(max_length=28, choices=EFFICIENCY_RATING_CHOICES, default="optimal")`
  - `receipt_reference`: `CharField(max_length=80, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_vful_ten_num_uniq")`
  - `Index(fields=["tenant", "vehicle", "fuel_date"], name="idx_vful_ten_veh_date")`
  - `Index(fields=["tenant", "fuel_date"], name="idx_vful_ten_fdate")`
- **Properties**:
  - `efficiency_badge_class`: str
  - `cost_per_mile`: Decimal (derived property)

---

### 1.3 `VehicleDriverAssignment` (`VehicleDriverAssignments.py`)
- **`NUMBER_PREFIX`**: `"VDRV"`
- **`Meta.ordering`**: `["-start_datetime", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Vehicle Driver Assignment"` / `"Vehicle Driver Assignments"`
- **Choices & Badge Maps**:
  - `ASSIGNMENT_ROLE_CHOICES` (`max_length=24`):
    - `("primary_assigned", "Primary Assigned Driver")`
    - `("secondary_relief", "Secondary / Relief Driver")`
    - `("temporary_loaner", "Temporary Loaner Driver")`
    - `("pool_driver", "Motor Pool Dispatch Driver")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("active", "Active Assignment")`
    - `("completed", "Completed / Returned")`
    - `("revoked_safety", "Revoked for Safety")`
    - `("transferred", "Transferred")`
  - `LICENSE_CLASS_CHOICES` (`max_length=24`):
    - `("class_a_cdl", "Class A Commercial (CDL-A)")`
    - `("class_b_cdl", "Class B Commercial (CDL-B)")`
    - `("class_c_cdl", "Class C Commercial (CDL-C)")`
    - `("standard_non_cdl", "Standard Driver License (Class D/Non-CDL)")`
  - `QUALIFICATION_STATUS_CHOICES` (`max_length=28`):
    - `("qualified", "Qualified & Cleared")`
    - `("expiring_soon", "License / Medical Expiring Soon")`
    - `("expired_disqualified", "Disqualified / Expired Credentials")`
    - `("suspended", "Suspended Safety Standing")`
  - `DUTY_STATUS_CHOICES` (`max_length=24`):
    - `("off_duty", "Off Duty")`
    - `("sleeper_berth", "Sleeper Berth")`
    - `("driving", "Driving")`
    - `("on_duty_not_driving", "On Duty (Not Driving)")`
  - `SAFETY_TIER_CHOICES` (`max_length=20`):
    - `("exemplary", "Exemplary (90-100)")`
    - `("good", "Good (80-89)")`
    - `("needs_coaching", "Needs Coaching (65-79)")`
    - `("high_risk", "High Risk (<65)")`
  - `STATUS_CSS`:
    - `"active": "badge-green"`, `"completed": "badge-slate"`, `"revoked_safety": "badge-red"`, `"transferred": "badge-info"`
  - `QUALIFICATION_CSS`:
    - `"qualified": "badge-green"`, `"expiring_soon": "badge-amber"`, `"expired_disqualified": "badge-red"`, `"suspended": "badge-red"`
  - `SAFETY_TIER_CSS`:
    - `"exemplary": "badge-green"`, `"good": "badge-info"`, `"needs_coaching": "badge-amber"`, `"high_risk": "badge-red"`
  - `DUTY_STATUS_CSS`:
    - `"off_duty": "badge-slate"`, `"sleeper_berth": "badge-info"`, `"driving": "badge-green"`, `"on_duty_not_driving": "badge-amber"`
- **Fields**:
  - `vehicle`: `ForeignKey("assets.FleetVehicle", on_delete=CASCADE, related_name="driver_assignments")`
  - `driver`: `ForeignKey("hrm.EmployeeProfile", on_delete=CASCADE, related_name="vehicle_driver_assignments")`
  - `user`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name="assigned_vehicle_records")`
  - `assignment_role`: `CharField(max_length=24, choices=ASSIGNMENT_ROLE_CHOICES, default="primary_assigned")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active")`
  - `start_datetime`: `DateTimeField()`
  - `end_datetime`: `DateTimeField(null=True, blank=True)`
  - `start_odometer`: `PositiveIntegerField(default=0)`
  - `end_odometer`: `PositiveIntegerField(null=True, blank=True)`
  - `driver_license_number`: `CharField(max_length=48, blank=True)`
  - `driver_license_state`: `CharField(max_length=32, blank=True)`
  - `license_class`: `CharField(max_length=24, choices=LICENSE_CLASS_CHOICES, default="standard_non_cdl")`
  - `license_expiration_date`: `DateField(null=True, blank=True)`
  - `medical_card_expiration_date`: `DateField(null=True, blank=True)`
  - `hazmat_endorsed`: `BooleanField(default=False)`
  - `qualification_status`: `CharField(max_length=28, choices=QUALIFICATION_STATUS_CHOICES, default="qualified")`
  - `safety_score`: `PositiveSmallIntegerField(default=100)`
  - `speeding_event_count`: `PositiveIntegerField(default=0)`
  - `harsh_braking_count`: `PositiveIntegerField(default=0)`
  - `harsh_acceleration_count`: `PositiveIntegerField(default=0)`
  - `incident_count`: `PositiveIntegerField(default=0)`
  - `duty_status`: `CharField(max_length=24, choices=DUTY_STATUS_CHOICES, default="off_duty")`
  - `safety_tier`: `CharField(max_length=20, choices=SAFETY_TIER_CHOICES, default="exemplary")`
  - `supervisor_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_vdrv_ten_num_uniq")`
  - `Index(fields=["tenant", "vehicle", "status"], name="idx_vdrv_ten_veh_stat")`
  - `Index(fields=["tenant", "driver", "status"], name="idx_vdrv_ten_drv_stat")`
  - `Index(fields=["tenant", "safety_tier"], name="idx_vdrv_ten_stier")`
- **Properties**:
  - `is_license_expired`: bool
  - `is_license_expiring_soon`: bool
  - `is_medical_expired`: bool
  - `status_badge_class`: str
  - `qualification_badge_class`: str
  - `safety_tier_badge_class`: str
  - `duty_status_badge_class`: str

---

### 1.4 `VehicleServiceSchedule` (`VehicleServiceSchedules.py`)
- **`NUMBER_PREFIX`**: `"VSRV"`
- **`Meta.ordering`**: `["next_due_date", "-number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Vehicle Service Schedule"` / `"Vehicle Service Schedules"`
- **Choices & Badge Maps**:
  - `SERVICE_TYPE_CHOICES` (`max_length=32`):
    - `("engine_oil_filter", "Engine Oil & Filter Change")`
    - `("tire_rotation_balance", "Tire Rotation & Balance")`
    - `("brake_pad_rotor_service", "Brake Pad & Rotor Service")`
    - `("transmission_fluid_service", "Transmission Fluid Service")`
    - `("coolant_flush", "Cooling System / Antifreeze Flush")`
    - `("air_cabin_filter", "Engine & Cabin Air Filter Replacement")`
    - `("annual_dot_inspection", "Annual DOT / Commercial Safety Inspection")`
    - `("emissions_test", "State Emissions Test / Smog Check")`
    - `("spark_plug_replacement", "Spark Plug & Ignition Service")`
    - `("battery_electrical_check", "12V / High-Voltage Battery Diagnostic")`
    - `("wheel_alignment", "Four-Wheel Alignment")`
    - `("general_preventive_pm", "General Preventive Maintenance (PM A/B/C)")`
  - `PRIORITY_CHOICES` (`max_length=20`):
    - `("emergency_safety", "Emergency Safety Concern")`
    - `("high_priority", "High Priority")`
    - `("normal_routine", "Normal / Routine")`
    - `("scheduled_pm", "Scheduled Preventive")`
  - `STATUS_CHOICES` (`max_length=24`):
    - `("active_tracking", "Active Tracking")`
    - `("due_soon", "Service Due Soon")`
    - `("overdue", "Service Overdue")`
    - `("in_service", "In Service / At Shop")`
    - `("paused", "Paused / On Hold")`
    - `("completed", "Completed & Logged")`
  - `STATUS_CSS`:
    - `"active_tracking": "badge-info"`, `"due_soon": "badge-amber"`, `"overdue": "badge-red"`, `"in_service": "badge-purple"`, `"paused": "badge-slate"`, `"completed": "badge-green"`
  - `PRIORITY_CSS`:
    - `"emergency_safety": "badge-red"`, `"high_priority": "badge-amber"`, `"normal_routine": "badge-info"`, `"scheduled_pm": "badge-slate"`
- **Fields**:
  - `vehicle`: `ForeignKey("assets.FleetVehicle", on_delete=CASCADE, related_name="service_schedules")`
  - `service_title`: `CharField(max_length=150)`
  - `service_type`: `CharField(max_length=32, choices=SERVICE_TYPE_CHOICES, default="engine_oil_filter")`
  - `service_vendor`: `ForeignKey("core.Party", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_service_contracts")`
  - `warranty`: `ForeignKey("assets.AssetWarranty", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_services")`
  - `maintenance_schedule`: `ForeignKey("assets.AssetMaintenanceSchedule", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_service_schedules")`
  - `interval_mileage`: `PositiveIntegerField(default=5000)`
  - `interval_months`: `PositiveSmallIntegerField(default=6)`
  - `last_service_date`: `DateField(null=True, blank=True)`
  - `last_service_odometer`: `PositiveIntegerField(null=True, blank=True)`
  - `next_due_date`: `DateField(null=True, blank=True)`
  - `next_due_odometer`: `PositiveIntegerField(null=True, blank=True)`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default="scheduled_pm")`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default="active_tracking")`
  - `estimated_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `actual_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `currency`: `ForeignKey("accounting.Currency", on_delete=SET_NULL, null=True, blank=True, related_name="vehicle_service_schedules")` (GLOBAL)
  - `is_warranty_covered`: `BooleanField(default=False)`
  - `work_order_invoice_ref`: `CharField(max_length=80, blank=True)`
  - `technician_resolution_notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="assets_vsrv_ten_num_uniq")`
  - `Index(fields=["tenant", "vehicle", "status"], name="idx_vsrv_ten_veh_stat")`
  - `Index(fields=["tenant", "status"], name="idx_vsrv_ten_stat")`
  - `Index(fields=["tenant", "next_due_date"], name="idx_vsrv_ten_ndate")`
  - `Index(fields=["tenant", "next_due_odometer"], name="idx_vsrv_ten_nodom")`
- **Properties**:
  - `is_overdue`: bool
  - `is_due_soon`: bool
  - `status_badge_class`: str
  - `priority_badge_class`: str

---

## 2. Forms Contract (`apps/assets/forms/FleetVehicleManagement/`)

All ModelForms inherit `forms.ModelForm`.
- `__init__(self, *args, tenant=None, **kwargs)`: saves `self.tenant = tenant`.
- Populate all tenant-scoped FK fields with `Model.objects.filter(tenant=self.tenant)`.
- Global FK `currency` populated with `Currency.objects.filter(is_active=True)`.
- `clean()` enforces `reject_foreign(self, tenant, _TENANT_FK_FIELDS)`.

### 2.1 `FleetVehicleForm` (`FleetVehicles.py`)
- **Model**: `FleetVehicle`
- **Excluded**: `["tenant", "number", "status", "compliance_status", "last_telemetry_at", "created_at", "updated_at"]`
- **Tenant FKs to validate**: `["operational_asset", "fixed_asset", "asset_category", "asset_model", "org_unit", "primary_driver", "custodian_party"]`

### 2.2 `VehicleFuelLogForm` (`VehicleFuelLogs.py`)
- **Model**: `VehicleFuelLog`
- **Excluded**: `["tenant", "number", "distance_since_last_fuel", "calculated_mpg", "efficiency_rating", "created_at", "updated_at"]`
- **Tenant FKs to validate**: `["vehicle", "driver", "fuel_vendor"]` (Note: `currency` is GLOBAL)

### 2.3 `VehicleDriverAssignmentForm` (`VehicleDriverAssignments.py`)
- **Model**: `VehicleDriverAssignment`
- **Excluded**: `["tenant", "number", "status", "qualification_status", "safety_tier", "created_at", "updated_at"]`
- **Tenant FKs to validate**: `["vehicle", "driver", "user"]`

### 2.4 `VehicleServiceScheduleForm` (`VehicleServiceSchedules.py`)
- **Model**: `VehicleServiceSchedule`
- **Excluded**: `["tenant", "number", "status", "actual_cost", "created_at", "updated_at"]`
- **Tenant FKs to validate**: `["vehicle", "service_vendor", "warranty", "maintenance_schedule"]` (Note: `currency` is GLOBAL)

---

## 3. URLs Contract (`apps/assets/urls/FleetVehicleManagement/`)

All URL paths under `apps/assets/urls/`:
- **`FleetVehicles.py`**:
  - `fleet-vehicles/` -> `name="fleet_vehicle_list"`
  - `fleet-vehicles/export/` -> `name="fleet_vehicle_export"`
  - `fleet-vehicles/create/` -> `name="fleet_vehicle_create"`
  - `fleet-vehicles/<int:pk>/` -> `name="fleet_vehicle_detail"`
  - `fleet-vehicles/<int:pk>/edit/` -> `name="fleet_vehicle_edit"`
  - `fleet-vehicles/<int:pk>/delete/` -> `name="fleet_vehicle_delete"`
  - `fleet-vehicles/<int:pk>/activate/` -> `name="fleet_vehicle_activate"`
  - `fleet-vehicles/<int:pk>/in-shop/` -> `name="fleet_vehicle_mark_in_shop"`
  - `fleet-vehicles/<int:pk>/loaner/` -> `name="fleet_vehicle_mark_loaner"`
  - `fleet-vehicles/<int:pk>/out-of-service/` -> `name="fleet_vehicle_mark_out_of_service"`
  - `fleet-vehicles/<int:pk>/decommission/` -> `name="fleet_vehicle_decommission"`
  - `fleet-vehicles/<int:pk>/ping-telemetry/` -> `name="fleet_vehicle_ping_telemetry"`
- **`VehicleFuelLogs.py`**:
  - `vehicle-fuel-logs/` -> `name="vehicle_fuel_log_list"`
  - `vehicle-fuel-logs/export/` -> `name="vehicle_fuel_log_export"`
  - `vehicle-fuel-logs/create/` -> `name="vehicle_fuel_log_create"`
  - `vehicle-fuel-logs/<int:pk>/` -> `name="vehicle_fuel_log_detail"`
  - `vehicle-fuel-logs/<int:pk>/edit/` -> `name="vehicle_fuel_log_edit"`
  - `vehicle-fuel-logs/<int:pk>/delete/` -> `name="vehicle_fuel_log_delete"`
- **`VehicleDriverAssignments.py`**:
  - `vehicle-driver-assignments/` -> `name="vehicle_driver_assignment_list"`
  - `vehicle-driver-assignments/export/` -> `name="vehicle_driver_assignment_export"`
  - `vehicle-driver-assignments/create/` -> `name="vehicle_driver_assignment_create"`
  - `vehicle-driver-assignments/<int:pk>/` -> `name="vehicle_driver_assignment_detail"`
  - `vehicle-driver-assignments/<int:pk>/edit/` -> `name="vehicle_driver_assignment_edit"`
  - `vehicle-driver-assignments/<int:pk>/delete/` -> `name="vehicle_driver_assignment_delete"`
  - `vehicle-driver-assignments/<int:pk>/complete/` -> `name="vehicle_driver_assignment_complete"`
  - `vehicle-driver-assignments/<int:pk>/revoke/` -> `name="vehicle_driver_assignment_revoke"`
  - `vehicle-driver-assignments/<int:pk>/incident/` -> `name="vehicle_driver_assignment_record_incident"`
- **`VehicleServiceSchedules.py`**:
  - `vehicle-service-schedules/` -> `name="vehicle_service_schedule_list"`
  - `vehicle-service-schedules/export/` -> `name="vehicle_service_schedule_export"`
  - `vehicle-service-schedules/create/` -> `name="vehicle_service_schedule_create"`
  - `vehicle-service-schedules/<int:pk>/` -> `name="vehicle_service_schedule_detail"`
  - `vehicle-service-schedules/<int:pk>/edit/` -> `name="vehicle_service_schedule_edit"`
  - `vehicle-service-schedules/<int:pk>/delete/` -> `name="vehicle_service_schedule_delete"`
  - `vehicle-service-schedules/<int:pk>/complete/` -> `name="vehicle_service_schedule_complete"`
  - `vehicle-service-schedules/<int:pk>/in-service/` -> `name="vehicle_service_schedule_mark_in_service"`
  - `vehicle-service-schedules/<int:pk>/pause/` -> `name="vehicle_service_schedule_pause"`
- **`FleetTelematicsBoards.py`**:
  - `fleet-telematics/board/` -> `name="fleet_telematics_board"`

---

## 4. Views & Context Variables Contract (`apps/assets/views/FleetVehicleManagement/`)

All views tenant-filtered with `tenant=request.tenant`. All mutations write audit logs via `write_audit_log`.

### 4.1 `FleetVehicles.py`
- `fleet_vehicle_list`:
  - `page_obj`: paginated `FleetVehicle` queryset
  - `status_choices`: `FleetVehicle.STATUS_CHOICES`
  - `vehicle_type_choices`: `FleetVehicle.VEHICLE_TYPE_CHOICES`
  - `fuel_type_choices`: `FleetVehicle.FUEL_TYPE_CHOICES`
  - `compliance_choices`: `FleetVehicle.COMPLIANCE_STATUS_CHOICES`
  - `org_units`: `OrgUnit.objects.filter(tenant=request.tenant)`
  - `total_count`, `active_count`, `in_shop_count`, `expired_compliance_count`
- `fleet_vehicle_detail`:
  - `vehicle`: target `FleetVehicle`
  - `fuel_logs`: recent `VehicleFuelLog` rows for this vehicle
  - `assignments`: recent `VehicleDriverAssignment` rows for this vehicle
  - `service_schedules`: recent `VehicleServiceSchedule` rows for this vehicle
  - `recent_audits`: audit logs for this vehicle
- `fleet_vehicle_create` / `fleet_vehicle_edit`:
  - `form`: `FleetVehicleForm`
  - `vehicle`: target object on edit, None on create
  - `is_edit`: bool

### 4.2 `VehicleFuelLogs.py`
- `vehicle_fuel_log_list`:
  - `page_obj`: paginated `VehicleFuelLog` queryset
  - `vehicles`: `FleetVehicle.objects.filter(tenant=request.tenant)`
  - `fuel_type_choices`: `VehicleFuelLog.FUEL_TYPE_CHOICES`
  - `efficiency_choices`: `VehicleFuelLog.EFFICIENCY_RATING_CHOICES`
  - `total_cost_sum`, `total_gallons_sum`, `avg_mpg`
- `vehicle_fuel_log_detail`:
  - `fuel_log`: target `VehicleFuelLog`
- `vehicle_fuel_log_create` / `vehicle_fuel_log_edit`:
  - `form`: `VehicleFuelLogForm`
  - `fuel_log`: target object on edit, None on create
  - `is_edit`: bool

### 4.3 `VehicleDriverAssignments.py`
- `vehicle_driver_assignment_list`:
  - `page_obj`: paginated `VehicleDriverAssignment` queryset
  - `vehicles`: `FleetVehicle.objects.filter(tenant=request.tenant)`
  - `drivers`: `EmployeeProfile.objects.filter(tenant=request.tenant)`
  - `status_choices`: `VehicleDriverAssignment.STATUS_CHOICES`
  - `safety_tier_choices`: `VehicleDriverAssignment.SAFETY_TIER_CHOICES`
  - `active_count`, `high_risk_count`
- `vehicle_driver_assignment_detail`:
  - `assignment`: target `VehicleDriverAssignment`
- `vehicle_driver_assignment_create` / `vehicle_driver_assignment_edit`:
  - `form`: `VehicleDriverAssignmentForm`
  - `assignment`: target object on edit, None on create
  - `is_edit`: bool

### 4.4 `VehicleServiceSchedules.py`
- `vehicle_service_schedule_list`:
  - `page_obj`: paginated `VehicleServiceSchedule` queryset
  - `vehicles`: `FleetVehicle.objects.filter(tenant=request.tenant)`
  - `service_type_choices`: `VehicleServiceSchedule.SERVICE_TYPE_CHOICES`
  - `status_choices`: `VehicleServiceSchedule.STATUS_CHOICES`
  - `priority_choices`: `VehicleServiceSchedule.PRIORITY_CHOICES`
  - `overdue_count`, `due_soon_count`
- `vehicle_service_schedule_detail`:
  - `schedule`: target `VehicleServiceSchedule`
- `vehicle_service_schedule_create` / `vehicle_service_schedule_edit`:
  - `form`: `VehicleServiceScheduleForm`
  - `schedule`: target object on edit, None on create
  - `is_edit`: bool

### 4.5 `FleetTelematicsBoards.py`
- `fleet_telematics_board`:
  - `total_vehicles`, `active_in_service`, `in_shop`, `moving_count`, `idling_count`, `geofence_breach_count`, `overdue_service_count`, `expired_compliance_count`
  - `recent_vehicles`: 10 latest active vehicles with telematics info
  - `high_risk_drivers`: driver assignments with `safety_tier in ("high_risk", "needs_coaching")`
  - `recent_fuel_logs`: 5 latest fuel logs
  - `upcoming_services`: upcoming/overdue service schedules

---

## 5. Sidebar Wiring Contract (`apps/core/navigation.py`)

`LIVE_LINKS["11.19"]`:
```python
"11.19": {
    "Vehicle Registration & Compliance": "assets:fleet_vehicle_list",
    "Fuel & Mileage Tracking": "assets:vehicle_fuel_log_list",
    "Driver Assignment & Safety": "assets:vehicle_driver_assignment_list",
    "Maintenance & Service Scheduling": "assets:vehicle_service_schedule_list",
    "Telematics & GPS Monitoring": "assets:fleet_telematics_board",
},
```

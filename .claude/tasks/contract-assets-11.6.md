# Contract — Sub-module 11.6: Asset Performance & Utilization (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.6 Asset Performance & Utilization • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-09 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0009_...`.
- **Package Layout:** `AssetPerformance/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_performance/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetDowntimeLog` (`apps/assets/models/AssetPerformance/AssetDowntimeLogs.py`)
- **Table:** `assets_assetdowntimelog`
- **Number Prefix:** `ADWN` (format: `ADWN-YYYYMM-XXXX`)
- **CHOICES:**
  - `DOWNTIME_CATEGORY_CHOICES = [('unplanned_breakdown', 'Unplanned Breakdown'), ('planned_maintenance', 'Planned Maintenance / PM'), ('setup_changeover', 'Setup & Changeover'), ('tooling_adjustment', 'Tooling & Adjustment'), ('process_interruption', 'Process Interruption / Starvation'), ('utility_outage', 'Utility / Power Failure'), ('operator_unavailable', 'Operator / Staff Shortage'), ('cleaning_sanitation', 'Cleaning & Sanitation')]`
  - `IMPACT_LEVEL_CHOICES = [('full_shutdown', 'Full Machine Shutdown'), ('partial_derate', 'Partial Derate / Speed Loss'), ('cell_idle', 'Cell / Line Idle'), ('minor_stop', 'Minor Stoppage (<5 min)')]`
  - `STATUS_CHOICES = [('active', 'Active Stoppage'), ('resolved', 'Resolved / Resumed'), ('under_investigation', 'Under Root Cause Analysis'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'active': 'badge-red', 'resolved': 'badge-green', 'under_investigation': 'badge-amber', 'cancelled': 'badge-muted'}`
  - `CATEGORY_CSS = {'unplanned_breakdown': 'badge-red', 'planned_maintenance': 'badge-info', 'setup_changeover': 'badge-purple', 'tooling_adjustment': 'badge-slate', 'process_interruption': 'badge-amber', 'utility_outage': 'badge-red', 'operator_unavailable': 'badge-amber', 'cleaning_sanitation': 'badge-slate'}`
  - `IMPACT_CSS = {'full_shutdown': 'badge-red', 'partial_derate': 'badge-amber', 'cell_idle': 'badge-info', 'minor_stop': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_downtime_logs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='downtime_logs', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='downtime_logs', help_text='Operational equipment record')`
  - `maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='downtime_logs', help_text='Associated breakdown ticket')`
  - `work_order`: `ForeignKey('scm.MaintenanceWorkOrder', on_delete=SET_NULL, null=True, blank=True, related_name='asset_downtime_logs', help_text='Linked maintenance work order')`
  - `downtime_category`: `CharField(max_length=30, choices=DOWNTIME_CATEGORY_CHOICES, default='unplanned_breakdown')`
  - `impact_level`: `CharField(max_length=20, choices=IMPACT_LEVEL_CHOICES, default='full_shutdown')`
  - `root_cause_code`: `CharField(max_length=50, blank=True, help_text='ISO 14224 / FMEA failure code or description')`
  - `failure_description`: `TextField(help_text='Detailed symptom, alarm, or cause of stoppage')`
  - `started_at`: `DateTimeField(help_text='Exact timestamp when downtime started')`
  - `ended_at`: `DateTimeField(null=True, blank=True, help_text='Exact timestamp when machine resumed operation')`
  - `duration_minutes`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text='Calculated duration in minutes')`
  - `hourly_cost_rate`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Standard production/labor loss cost per hour')`
  - `total_downtime_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Calculated downtime financial loss')`
  - `is_mtbf_failure`: `BooleanField(default=True, help_text='Counted as random failure for MTBF calculations')`
  - `logged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='logged_asset_downtimes')`
  - `department`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_downtime_logs', help_text='Department or plant workshop')`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default='active')`
  - `resolution_notes`: `TextField(blank=True, help_text='Corrective action, repair notes, and restart procedure')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_adwn_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_adwn_ten_stat')`
  - `Index(fields=['tenant', 'downtime_category'], name='idx_adwn_ten_cat')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_adwn_ten_fa')`
- **Actions / State Machine:**
  - `asset_downtime_log_resolve`: records `ended_at`, calculates `duration_minutes` and `total_downtime_cost`, transitions `active -> resolved`.
  - `asset_downtime_log_investigate`: sets `status = 'under_investigation'`.
  - `asset_downtime_log_cancel`: sets `status = 'cancelled'`.
- **Form exclusions:** `tenant`, `number`, `duration_minutes`, `total_downtime_cost`, `created_at`, `updated_at`.

---

### 1.2 `AssetOeeRecord` (`apps/assets/models/AssetPerformance/AssetOeeRecords.py`)
- **Table:** `assets_assetoeerecord`
- **Number Prefix:** `AOEE` (format: `AOEE-YYYYMM-XXXX`)
- **CHOICES:**
  - `BENCHMARK_TIER_CHOICES = [('world_class', 'World-Class (>=85%)'), ('acceptable', 'Typical / Acceptable (60-84%)'), ('low', 'Low / High Loss (<60%)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Entry'), ('finalized', 'Finalized / Verified'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'finalized': 'badge-green', 'cancelled': 'badge-muted'}`
  - `TIER_CSS = {'world_class': 'badge-green', 'acceptable': 'badge-info', 'low': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_oee_records')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='oee_records', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='oee_records', help_text='Operational equipment record')`
  - `record_date`: `DateField(help_text='Production date')`
  - `shift_name`: `CharField(max_length=50, default='Shift 1')`
  - `planned_production_time_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('480.00'), help_text='Scheduled operational minutes')`
  - `operating_time_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Actual run time minutes')`
  - `ideal_cycle_time_seconds`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('10.00'), help_text='Minimum theoretical time per piece in seconds')`
  - `total_units_produced`: `IntegerField(default=0, help_text='Total count of units produced')`
  - `good_units_produced`: `IntegerField(default=0, help_text='Count of first-pass defect-free units')`
  - `defect_units_count`: `IntegerField(default=0, help_text='Rejected scrap units count')`
  - `rework_units_count`: `IntegerField(default=0, help_text='Reworked units count')`
  - `breakdown_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Unplanned stoppage minutes')`
  - `setup_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Setup and adjustment loss minutes')`
  - `small_stops_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Minor idling and brief stop minutes')`
  - `reduced_speed_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Loss from operating below design speed')`
  - `defect_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Time lost manufacturing rejected product')`
  - `startup_loss_minutes`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Warmup and ramp-up yield loss minutes')`
  - `availability_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Operating Time / Planned Production Time * 100')`
  - `performance_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='(Ideal Cycle Time * Total Units) / Operating Time * 100')`
  - `quality_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Good Units / Total Units * 100')`
  - `oee_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Availability * Performance * Quality / 10000')`
  - `benchmark_tier`: `CharField(max_length=20, choices=BENCHMARK_TIER_CHOICES, default='acceptable')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `notes`: `TextField(blank=True)`
  - `recorded_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='recorded_oee_entries')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aoee_ten_num_uniq')`
  - `Index(fields=['tenant', 'record_date'], name='idx_aoee_ten_date')`
  - `Index(fields=['tenant', 'benchmark_tier'], name='idx_aoee_ten_tier')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_aoee_ten_fa')`
- **Actions / State Machine:**
  - `asset_oee_record_finalize`: calculates Availability, Performance, Quality, OEE %, assigns benchmark tier, transitions `draft -> finalized`.
- **Form exclusions:** `tenant`, `number`, `availability_percentage`, `performance_percentage`, `quality_percentage`, `oee_percentage`, `benchmark_tier`, `created_at`, `updated_at`.

---

### 1.3 `AssetEnergyReading` (`apps/assets/models/AssetPerformance/AssetEnergyReadings.py`)
- **Table:** `assets_assetenergyreading`
- **Number Prefix:** `AENG` (format: `AENG-YYYYMM-XXXX`)
- **CHOICES:**
  - `UTILITY_TYPE_CHOICES = [('electricity', 'Electricity (kWh)'), ('natural_gas', 'Natural Gas (m3 / MMBtu)'), ('diesel', 'Diesel Fuel (Liters)'), ('heavy_fuel_oil', 'Heavy Fuel Oil (Liters)'), ('steam', 'Steam (Tons)'), ('compressed_air', 'Compressed Air (Nm3)'), ('industrial_water', 'Industrial Water (m3)')]`
  - `GHG_SCOPE_CHOICES = [('scope_1', 'Scope 1: Direct Combustion'), ('scope_2', 'Scope 2: Purchased Electricity/Steam'), ('scope_3', 'Scope 3: Indirect Value Chain')]`
  - `STATUS_CHOICES = [('pending', 'Pending Review'), ('validated', 'Validated'), ('flagged_anomaly', 'Flagged Anomaly / Peak Spike'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'pending': 'badge-slate', 'validated': 'badge-green', 'flagged_anomaly': 'badge-red', 'cancelled': 'badge-muted'}`
  - `UTILITY_CSS = {'electricity': 'badge-info', 'natural_gas': 'badge-purple', 'diesel': 'badge-amber', 'heavy_fuel_oil': 'badge-slate', 'steam': 'badge-slate', 'compressed_air': 'badge-info', 'industrial_water': 'badge-info'}`
  - `GHG_SCOPE_CSS = {'scope_1': 'badge-amber', 'scope_2': 'badge-info', 'scope_3': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_energy_readings')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='energy_readings', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='energy_readings', help_text='Operational equipment record')`
  - `reading_timestamp`: `DateTimeField(help_text='Timestamp of energy meter reading')`
  - `utility_type`: `CharField(max_length=25, choices=UTILITY_TYPE_CHOICES, default='electricity')`
  - `meter_serial_number`: `CharField(max_length=64, blank=True)`
  - `consumption_value`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), help_text='Metered consumption quantity')`
  - `unit_of_measure`: `CharField(max_length=20, default='kWh')`
  - `peak_demand_kw`: `DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Peak electrical demand load')`
  - `power_factor`: `DecimalField(max_digits=4, decimal_places=3, null=True, blank=True, help_text='Power factor cos phi (0.000 to 1.000)')`
  - `operating_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Run hours during reading window')`
  - `units_produced`: `IntegerField(default=0, help_text='Production units output during window')`
  - `energy_intensity_per_hour`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text='Consumption / operating hours')`
  - `energy_intensity_per_unit`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text='Consumption / units produced')`
  - `emission_factor`: `DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.4500'), help_text='kg CO2e per unit of utility consumption')`
  - `carbon_emissions_kg_co2e`: `DecimalField(max_digits=14, decimal_places=4, default=Decimal('0.0000'), help_text='Calculated Scope 1/2 GHG footprint')`
  - `ghg_scope`: `CharField(max_length=15, choices=GHG_SCOPE_CHOICES, default='scope_2')`
  - `cost_per_unit`: `DecimalField(max_digits=10, decimal_places=4, default=Decimal('0.0000'), help_text='Energy tariff rate per unit')`
  - `total_energy_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text='Total energy cost')`
  - `utility_provider`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='energy_readings', help_text='Utility vendor or electricity provider')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='pending')`
  - `notes`: `TextField(blank=True)`
  - `recorded_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='recorded_energy_readings')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aeng_ten_num_uniq')`
  - `Index(fields=['tenant', 'reading_timestamp'], name='idx_aeng_ten_time')`
  - `Index(fields=['tenant', 'utility_type'], name='idx_aeng_ten_util')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_aeng_ten_fa')`
- **Actions / State Machine:**
  - `asset_energy_reading_validate`: calculates intensity rates, carbon footprint, energy cost, transitions `pending -> validated`.
  - `asset_energy_reading_flag_anomaly`: flags peak surge or power factor degradation, sets `status = 'flagged_anomaly'`.
- **Form exclusions:** `tenant`, `number`, `energy_intensity_per_hour`, `energy_intensity_per_unit`, `carbon_emissions_kg_co2e`, `total_energy_cost`, `created_at`, `updated_at`.

---

### 1.4 `AssetPerformanceScorecard` (`apps/assets/models/AssetPerformance/AssetPerformanceScorecards.py`)
- **Table:** `assets_assetperformancescorecard`
- **Number Prefix:** `APSC` (format: `APSC-YYYYMM-XXXX`)
- **CHOICES:**
  - `PERIOD_TYPE_CHOICES = [('daily', 'Daily Rollup'), ('weekly', 'Weekly Rollup'), ('monthly', 'Monthly Scorecard'), ('quarterly', 'Quarterly Scorecard'), ('annual', 'Annual Scorecard')]`
  - `BENCHMARK_GRADE_CHOICES = [('grade_a', 'Grade A - Benchmark Leader (90-100)'), ('grade_b', 'Grade B - Reliable & Sound (75-89)'), ('grade_c', 'Grade C - Needs Optimization (55-74)'), ('grade_d', 'Grade D - Critical Performance Risk (<55)')]`
  - `STATUS_CHOICES = [('draft', 'Draft Scorecard'), ('published', 'Published / Certified'), ('archived', 'Archived')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'published': 'badge-green', 'archived': 'badge-muted'}`
  - `PERIOD_CSS = {'daily': 'badge-slate', 'weekly': 'badge-info', 'monthly': 'badge-purple', 'quarterly': 'badge-amber', 'annual': 'badge-green'}`
  - `GRADE_CSS = {'grade_a': 'badge-green', 'grade_b': 'badge-info', 'grade_c': 'badge-amber', 'grade_d': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_performance_scorecards')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='performance_scorecards', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='performance_scorecards', help_text='Operational equipment record')`
  - `period_type`: `CharField(max_length=20, choices=PERIOD_TYPE_CHOICES, default='monthly')`
  - `period_start`: `DateField()`
  - `period_end`: `DateField()`
  - `total_calendar_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('720.00'))`
  - `planned_operating_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('480.00'))`
  - `actual_operating_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `unplanned_downtime_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `planned_downtime_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `idle_capacity_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))`
  - `capacity_utilization_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Actual operating / Planned operating * 100')`
  - `availability_rate`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='(Operating / (Operating + Unplanned Downtime)) * 100')`
  - `failure_event_count`: `IntegerField(default=0, help_text='Count of unplanned breakdown events in period')`
  - `mtbf_hours`: `DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), help_text='Operating hours / failure event count')`
  - `mttr_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Unplanned downtime hours / failure event count')`
  - `average_oee_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))`
  - `total_energy_consumption_kwh`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
  - `total_carbon_emissions_kg`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
  - `total_downtime_cost`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))`
  - `performance_index_score`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text='Weighted composite score (0-100)')`
  - `benchmark_grade`: `CharField(max_length=15, choices=BENCHMARK_GRADE_CHOICES, default='grade_b')`
  - `peer_category_ranking`: `IntegerField(default=1, help_text='Rank relative to same asset category peers')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `executive_summary`: `TextField(blank=True)`
  - `evaluated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='evaluated_asset_scorecards')`
  - `department`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_performance_scorecards', help_text='Department or operating site')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_apsc_ten_num_uniq')`
  - `Index(fields=['tenant', 'period_type'], name='idx_apsc_ten_per')`
  - `Index(fields=['tenant', 'benchmark_grade'], name='idx_apsc_ten_grd')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_apsc_ten_fa')`
- **Actions / State Machine:**
  - `asset_performance_scorecard_publish`: computes MTBF, MTTR, utilization %, API composite score, assigns letter grade, transitions `draft -> published`.
- **Form exclusions:** `tenant`, `number`, `capacity_utilization_rate`, `availability_rate`, `mtbf_hours`, `mttr_hours`, `performance_index_score`, `benchmark_grade`, `peer_category_ranking`, `created_at`, `updated_at`.

---

## 2. Forms Contract

All forms inherit from `django.forms.ModelForm`. Standard Tailwind styling via `apps.assets.forms._common.py` helpers.

### 2.1 `AssetDowntimeLogForm` (`apps/assets/forms/AssetPerformance/AssetDowntimeLogs.py`)
- Excludes: `tenant`, `number`, `duration_minutes`, `total_downtime_cost`, `created_at`, `updated_at`.
- Date/Time widgets: `forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})` for `started_at` and `ended_at`.

### 2.2 `AssetOeeRecordForm` (`apps/assets/forms/AssetPerformance/AssetOeeRecords.py`)
- Excludes: `tenant`, `number`, `availability_percentage`, `performance_percentage`, `quality_percentage`, `oee_percentage`, `benchmark_tier`, `created_at`, `updated_at`.
- Date widget: `forms.DateInput(attrs={'type': 'date', 'class': 'form-input'})` for `record_date`.

### 2.3 `AssetEnergyReadingForm` (`apps/assets/forms/AssetPerformance/AssetEnergyReadings.py`)
- Excludes: `tenant`, `number`, `energy_intensity_per_hour`, `energy_intensity_per_unit`, `carbon_emissions_kg_co2e`, `total_energy_cost`, `created_at`, `updated_at`.
- Date/Time widget: `forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})` for `reading_timestamp`.

### 2.4 `AssetPerformanceScorecardForm` (`apps/assets/forms/AssetPerformance/AssetPerformanceScorecards.py`)
- Excludes: `tenant`, `number`, `capacity_utilization_rate`, `availability_rate`, `mtbf_hours`, `mttr_hours`, `performance_index_score`, `benchmark_grade`, `peer_category_ranking`, `created_at`, `updated_at`.
- Date widgets: `forms.DateInput(attrs={'type': 'date', 'class': 'form-input'})` for `period_start` and `period_end`.

---

## 3. URLs Contract (`apps/assets/urls/AssetPerformance/`)

Namespace: `assets`

### 3.1 `AssetDowntimeLogs.py`
- `downtime/` -> `assets:asset_downtime_log_list`
- `downtime/create/` -> `assets:asset_downtime_log_create`
- `downtime/<int:pk>/` -> `assets:asset_downtime_log_detail`
- `downtime/<int:pk>/edit/` -> `assets:asset_downtime_log_edit`
- `downtime/<int:pk>/delete/` -> `assets:asset_downtime_log_delete`
- `downtime/<int:pk>/resolve/` -> `assets:asset_downtime_log_resolve`

### 3.2 `AssetOeeRecords.py`
- `oee/` -> `assets:asset_oee_record_list`
- `oee/create/` -> `assets:asset_oee_record_create`
- `oee/<int:pk>/` -> `assets:asset_oee_record_detail`
- `oee/<int:pk>/edit/` -> `assets:asset_oee_record_edit`
- `oee/<int:pk>/delete/` -> `assets:asset_oee_record_delete`
- `oee/<int:pk>/finalize/` -> `assets:asset_oee_record_finalize`

### 3.3 `AssetEnergyReadings.py`
- `energy/` -> `assets:asset_energy_reading_list`
- `energy/create/` -> `assets:asset_energy_reading_create`
- `energy/<int:pk>/` -> `assets:asset_energy_reading_detail`
- `energy/<int:pk>/edit/` -> `assets:asset_energy_reading_edit`
- `energy/<int:pk>/delete/` -> `assets:asset_energy_reading_delete`
- `energy/<int:pk>/validate/` -> `assets:asset_energy_reading_validate`

### 3.4 `AssetPerformanceScorecards.py`
- `scorecards/` -> `assets:asset_performance_scorecard_list`
- `scorecards/create/` -> `assets:asset_performance_scorecard_create`
- `scorecards/<int:pk>/` -> `assets:asset_performance_scorecard_detail`
- `scorecards/<int:pk>/edit/` -> `assets:asset_performance_scorecard_edit`
- `scorecards/<int:pk>/delete/` -> `assets:asset_performance_scorecard_delete`
- `scorecards/<int:pk>/publish/` -> `assets:asset_performance_scorecard_publish`

---

## 4. View Context Keys Contract

### 4.1 `asset_downtime_log_list`
- `page_obj`: paginated Page of `AssetDowntimeLog` records
- `paginator`: Paginator instance
- `q`: search string from GET
- `status`: status filter string from GET
- `category`: category filter string from GET
- `impact`: impact filter string from GET
- `status_choices`: `AssetDowntimeLog.STATUS_CHOICES`
- `category_choices`: `AssetDowntimeLog.DOWNTIME_CATEGORY_CHOICES`
- `impact_choices`: `AssetDowntimeLog.IMPACT_LEVEL_CHOICES`
- `fixed_assets`: queryset of `accounting.FixedAsset` for tenant
- `status_css`: `AssetDowntimeLog.STATUS_CSS`
- `category_css`: `AssetDowntimeLog.CATEGORY_CSS`

### 4.2 `asset_downtime_log_detail`
- `log`: single `AssetDowntimeLog` instance
- `status_css`: `AssetDowntimeLog.STATUS_CSS`
- `category_css`: `AssetDowntimeLog.CATEGORY_CSS`
- `impact_css`: `AssetDowntimeLog.IMPACT_CSS`

### 4.3 `asset_downtime_log_form` (create / edit)
- `form`: ModelForm instance
- `log`: object instance or None
- `is_edit`: boolean

### 4.4 `asset_oee_record_list`
- `page_obj`: paginated Page of `AssetOeeRecord` records
- `paginator`: Paginator instance
- `q`: search string from GET
- `status`: status filter string from GET
- `tier`: benchmark tier filter string from GET
- `status_choices`: `AssetOeeRecord.STATUS_CHOICES`
- `tier_choices`: `AssetOeeRecord.BENCHMARK_TIER_CHOICES`
- `fixed_assets`: queryset of `accounting.FixedAsset` for tenant
- `status_css`: `AssetOeeRecord.STATUS_CSS`
- `tier_css`: `AssetOeeRecord.TIER_CSS`

### 4.5 `asset_oee_record_detail`
- `record`: single `AssetOeeRecord` instance
- `status_css`: `AssetOeeRecord.STATUS_CSS`
- `tier_css`: `AssetOeeRecord.TIER_CSS`

### 4.6 `asset_oee_record_form` (create / edit)
- `form`: ModelForm instance
- `record`: object instance or None
- `is_edit`: boolean

### 4.7 `asset_energy_reading_list`
- `page_obj`: paginated Page of `AssetEnergyReading` records
- `paginator`: Paginator instance
- `q`: search string from GET
- `status`: status filter string from GET
- `utility_type`: utility filter string from GET
- `scope`: ghg scope filter string from GET
- `status_choices`: `AssetEnergyReading.STATUS_CHOICES`
- `utility_choices`: `AssetEnergyReading.UTILITY_TYPE_CHOICES`
- `scope_choices`: `AssetEnergyReading.GHG_SCOPE_CHOICES`
- `fixed_assets`: queryset of `accounting.FixedAsset` for tenant
- `status_css`: `AssetEnergyReading.STATUS_CSS`
- `utility_css`: `AssetEnergyReading.UTILITY_CSS`

### 4.8 `asset_energy_reading_detail`
- `reading`: single `AssetEnergyReading` instance
- `status_css`: `AssetEnergyReading.STATUS_CSS`
- `utility_css`: `AssetEnergyReading.UTILITY_CSS`
- `scope_css`: `AssetEnergyReading.GHG_SCOPE_CSS`

### 4.9 `asset_energy_reading_form` (create / edit)
- `form`: ModelForm instance
- `reading`: object instance or None
- `is_edit`: boolean

### 4.10 `asset_performance_scorecard_list`
- `page_obj`: paginated Page of `AssetPerformanceScorecard` records
- `paginator`: Paginator instance
- `q`: search string from GET
- `status`: status filter string from GET
- `period_type`: period filter string from GET
- `grade`: grade filter string from GET
- `status_choices`: `AssetPerformanceScorecard.STATUS_CHOICES`
- `period_choices`: `AssetPerformanceScorecard.PERIOD_TYPE_CHOICES`
- `grade_choices`: `AssetPerformanceScorecard.BENCHMARK_GRADE_CHOICES`
- `fixed_assets`: queryset of `accounting.FixedAsset` for tenant
- `status_css`: `AssetPerformanceScorecard.STATUS_CSS`
- `grade_css`: `AssetPerformanceScorecard.GRADE_CSS`

### 4.11 `asset_performance_scorecard_detail`
- `scorecard`: single `AssetPerformanceScorecard` instance
- `status_css`: `AssetPerformanceScorecard.STATUS_CSS`
- `grade_css`: `AssetPerformanceScorecard.GRADE_CSS`
- `period_css`: `AssetPerformanceScorecard.PERIOD_CSS`

### 4.12 `asset_performance_scorecard_form` (create / edit)
- `form`: ModelForm instance
- `scorecard`: object instance or None
- `is_edit`: boolean

---

## 5. Navigation LIVE_LINKS Contract

In `apps/core/navigation.py`:
```python
"11.6": {
    "Uptime & Downtime Tracking": "assets:asset_downtime_log_list",
    "OEE & Productivity Metrics": "assets:asset_oee_record_list",
    "Utilization Rate Monitoring": "assets:asset_performance_scorecard_list",
    "Energy Consumption Tracking": "assets:asset_energy_reading_list",
    "Performance Benchmarking & KPIs": "assets:asset_performance_scorecard_list",
},
```
Aliases for robust catalog mapping:
```python
"Downtime Logs": "assets:asset_downtime_log_list",
"OEE Records": "assets:asset_oee_record_list",
"Energy Readings": "assets:asset_energy_reading_list",
"Performance Scorecards": "assets:asset_performance_scorecard_list",
```

---

## 6. Templates Contract

Paths under `templates/assets/asset_performance/`:
1. `asset_downtime_log/list.html`
2. `asset_downtime_log/detail.html`
3. `asset_downtime_log/form.html`
4. `asset_oee_record/list.html`
5. `asset_oee_record/detail.html`
6. `asset_oee_record/form.html`
7. `asset_energy_reading/list.html`
8. `asset_energy_reading/detail.html`
9. `asset_energy_reading/form.html`
10. `asset_performance_scorecard/list.html`
11. `asset_performance_scorecard/detail.html`
12. `asset_performance_scorecard/form.html`

All templates extend `templates/base.html` and use color-named CSS badges (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`).

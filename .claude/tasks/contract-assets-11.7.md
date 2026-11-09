# Contract — Sub-module 11.7: Asset Reliability & Condition Monitoring (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.7 Asset Reliability & Condition Monitoring • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-09 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0009_...`.
- **Package Layout:** `AssetReliability/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetreliability/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetConditionAssessment` (`apps/assets/models/AssetReliability/AssetConditionAssessments.py`)
- **Table:** `assets_assetconditionassessment`
- **Number Prefix:** `ACAS` (format: `ACAS-YYYYMM-XXXX`)
- **CHOICES:**
  - `ASSESSMENT_TYPE_CHOICES = [('visual_inspection', 'Visual Inspection'), ('ndt_ultrasonic', 'NDT - Ultrasonic Thickness'), ('ndt_thermography', 'NDT - Infrared Thermography'), ('ndt_vibration_pen', 'NDT - Vibration Screening Pen'), ('ndt_dye_penetrant', 'NDT - Dye Penetrant Testing'), ('ndt_magnetic_particle', 'NDT - Magnetic Particle Inspection'), ('oil_analysis', 'Lube Oil & Fluid Lab Analysis'), ('diagnostic_checklist', 'Comprehensive Diagnostic Checklist')]`
  - `CONDITION_GRADE_CHOICES = [('grade_1_excellent', 'Grade 1 - Excellent (As New)'), ('grade_2_good', 'Grade 2 - Good (Minor Wear)'), ('grade_3_fair', 'Grade 3 - Fair (Noticeable Wear)'), ('grade_4_poor', 'Grade 4 - Poor (Impaired Function)'), ('grade_5_critical', 'Grade 5 - Critical (Severe Failure Hazard)')]`
  - `OPERATING_STATUS_CHOICES = [('normal_operation', 'Normal Operation'), ('operational_with_defects', 'Operational with Minor Defects'), ('reduced_capacity', 'Derated / Reduced Capacity'), ('quarantined_unsafe', 'Quarantined / Unsafe to Operate'), ('decommission_recommended', 'Decommissioning Recommended')]`
  - `STATUS_CHOICES = [('draft', 'Draft (In Progress)'), ('completed', 'Completed'), ('reviewed', 'Reviewed & Approved'), ('archived', 'Archived')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'completed': 'badge-info', 'reviewed': 'badge-green', 'archived': 'badge-muted'}`
  - `CONDITION_GRADE_CSS = {'grade_1_excellent': 'badge-green', 'grade_2_good': 'badge-info', 'grade_3_fair': 'badge-amber', 'grade_4_poor': 'badge-red', 'grade_5_critical': 'badge-red'}`
  - `OPERATING_STATUS_CSS = {'normal_operation': 'badge-green', 'operational_with_defects': 'badge-amber', 'reduced_capacity': 'badge-amber', 'quarantined_unsafe': 'badge-red', 'decommission_recommended': 'badge-red'}`
  - `ASSESSMENT_TYPE_CSS = {'visual_inspection': 'badge-slate', 'ndt_ultrasonic': 'badge-info', 'ndt_thermography': 'badge-amber', 'ndt_vibration_pen': 'badge-info', 'ndt_dye_penetrant': 'badge-amber', 'ndt_magnetic_particle': 'badge-amber', 'oil_analysis': 'badge-info', 'diagnostic_checklist': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_condition_assessments')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Assessment summary or inspection scope title')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='condition_assessments', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='condition_assessments', help_text='Operational machinery or equipment record')`
  - `asset_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='condition_assessments', help_text='Asset category taxonomy')`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='conducted_asset_condition_assessments', help_text='Internal technician or reliability examiner')`
  - `external_inspector`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='contracted_asset_condition_assessments', help_text='External accredited NDT agency or testing laboratory')`
  - `assessment_date`: `DateField(default=timezone.now, help_text='Date inspection was conducted')`
  - `assessment_type`: `CharField(max_length=32, choices=ASSESSMENT_TYPE_CHOICES, default='visual_inspection')`
  - `condition_grade`: `CharField(max_length=24, choices=CONDITION_GRADE_CHOICES, default='grade_2_good')`
  - `health_score`: `PositiveIntegerField(default=85, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Asset Health Index (0-100 score)')`
  - `operating_status`: `CharField(max_length=32, choices=OPERATING_STATUS_CHOICES, default='normal_operation')`
  - `checklist_summary`: `TextField(blank=True, help_text='Summary checklist inspection criteria evaluated')`
  - `findings`: `TextField(help_text='Detailed physical observations, wear patterns, or defect findings')`
  - `recommendations`: `TextField(blank=True, help_text='Recommended corrective actions, servicing, or operating restrictions')`
  - `followup_required`: `BooleanField(default=False, help_text='Flags that immediate corrective maintenance is required')`
  - `triggered_maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='triggering_condition_assessments', help_text='Corrective maintenance request generated from this assessment')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='completed')`
  - `reviewed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='reviewed_asset_condition_assessments')`
  - `reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acas_ten_num_uniq')`
  - `Index(fields=['tenant', 'assessment_date'], name='idx_acas_ten_date')`
  - `Index(fields=['tenant', 'condition_grade'], name='idx_acas_ten_grade')`
  - `Index(fields=['tenant', 'status'], name='idx_acas_ten_stat')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_acas_ten_fa')`
- **Actions / State Machine:**
  - `asset_condition_assessment_complete`: transitions `draft -> completed`.
  - `asset_condition_assessment_review`: transitions `completed -> reviewed` upon supervisory sign-off.
  - `asset_condition_assessment_trigger_request`: spawns linked `AssetMaintenanceRequest` [AMRQ-] and binds `triggered_maintenance_request`.
- **Form exclusions:** `tenant`, `number`, `status`, `triggered_maintenance_request`, `reviewed_by`, `reviewed_at`, `created_at`, `updated_at`.

---

### 1.2 `AssetTelemetryReading` (`apps/assets/models/AssetReliability/AssetTelemetryReadings.py`)
- **Table:** `assets_assettelemetryreading`
- **Number Prefix:** `ATEL` (format: `ATEL-YYYYMM-XXXX`)
- **CHOICES:**
  - `SOURCE_CHOICES = [('iot_sensor', 'IoT Edge Sensor'), ('scada_historian', 'SCADA / Historian Ingestion'), ('manual_gauge', 'Manual Dial / Gauge Reading'), ('handheld_tester', 'Handheld Condition Tester'), ('analyst_entry', 'Reliability Analyst Entry')]`
  - `METRIC_TYPE_CHOICES = [('vibration_velocity_rms', 'Vibration Velocity RMS (mm/s)'), ('vibration_peak_accel', 'Vibration Peak Acceleration (g)'), ('bearing_temperature', 'Bearing Operating Temperature (°C)'), ('acoustic_ultrasound', 'Acoustic Ultrasound (dBµV)'), ('operating_pressure', 'Hydraulic / Line Pressure (bar)'), ('oil_dielectric_viscosity', 'Oil Dielectric / Kinematic Viscosity (cSt)'), ('motor_current_amperage', 'Motor Current Amperage (A)'), ('ambient_temperature', 'Ambient Temperature (°C)')]`
  - `METRIC_UNIT_CHOICES = [('mm_per_s', 'mm/s'), ('g_force', 'g'), ('celsius', '°C'), ('fahrenheit', '°F'), ('decibel_uv', 'dBµV'), ('bar', 'bar'), ('psi', 'psi'), ('amperes', 'A'), ('viscosity_cst', 'cSt')]`
  - `THRESHOLD_STATUS_CHOICES = [('normal', 'Normal (In Specification)'), ('warning', 'Warning (Elevated Alarm)'), ('critical', 'Critical (Exceeds Safety Threshold)'), ('anomaly_detected', 'Statistical Anomaly Detected')]`
  - `THRESHOLD_STATUS_CSS = {'normal': 'badge-green', 'warning': 'badge-amber', 'critical': 'badge-red', 'anomaly_detected': 'badge-red'}`
  - `SOURCE_CSS = {'iot_sensor': 'badge-info', 'scada_historian': 'badge-slate', 'manual_gauge': 'badge-muted', 'handheld_tester': 'badge-info', 'analyst_entry': 'badge-slate'}`
  - `METRIC_TYPE_CSS = {'vibration_velocity_rms': 'badge-amber', 'vibration_peak_accel': 'badge-amber', 'bearing_temperature': 'badge-red', 'acoustic_ultrasound': 'badge-info', 'operating_pressure': 'badge-info', 'oil_dielectric_viscosity': 'badge-slate', 'motor_current_amperage': 'badge-amber', 'ambient_temperature': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_telemetry_readings')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `sensor_identifier`: `CharField(max_length=100, blank=True, help_text='Unique hardware sensor tag or transmitter serial')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='telemetry_readings', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='telemetry_readings', help_text='Operational equipment record')`
  - `recorded_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='recorded_asset_telemetry_readings', help_text='User who recorded or ingested telemetry')`
  - `recorded_at`: `DateTimeField(default=timezone.now, help_text='Timestamp of sensor capture')`
  - `source`: `CharField(max_length=24, choices=SOURCE_CHOICES, default='iot_sensor')`
  - `metric_type`: `CharField(max_length=32, choices=METRIC_TYPE_CHOICES, default='vibration_velocity_rms')`
  - `metric_unit`: `CharField(max_length=20, choices=METRIC_UNIT_CHOICES, default='mm_per_s')`
  - `reading_value`: `DecimalField(max_digits=14, decimal_places=4, help_text='Measured physical reading value')`
  - `baseline_value`: `DecimalField(max_digits=14, decimal_places=4, null=True, blank=True, help_text='Expected baseline operating value')`
  - `deviation_percentage`: `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text='Calculated percentage deviation from baseline')`
  - `threshold_status`: `CharField(max_length=20, choices=THRESHOLD_STATUS_CHOICES, default='normal')`
  - `is_anomaly`: `BooleanField(default=False, help_text='Flags reading as a recognized pattern anomaly')`
  - `anomaly_confidence`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)], help_text='Anomaly classification confidence percentage (0-100)')`
  - `alert_notes`: `TextField(blank=True, help_text='Diagnostic commentary or anomaly alarm text')`
  - `triggered_maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='triggering_telemetry_readings', help_text='Corrective maintenance request generated from this reading')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_atel_ten_num_uniq')`
  - `Index(fields=['tenant', 'recorded_at'], name='idx_atel_ten_time')`
  - `Index(fields=['tenant', 'threshold_status'], name='idx_atel_ten_stat')`
  - `Index(fields=['tenant', 'metric_type'], name='idx_atel_ten_type')`
  - `Index(fields=['tenant', 'is_anomaly'], name='idx_atel_ten_anom')`
- **Actions / Calculations:**
  - `calculate_deviation_and_thresholds`: auto-computes deviation from baseline, evaluates threshold status.
  - `asset_telemetry_reading_trigger_request`: spawns linked `AssetMaintenanceRequest` [AMRQ-] and binds `triggered_maintenance_request`.
  - `asset_telemetry_reading_flag_anomaly`: manually or automatically flags anomaly with confidence.
- **Form exclusions:** `tenant`, `number`, `deviation_percentage`, `threshold_status`, `triggered_maintenance_request`, `created_at`, `updated_at`.

---

### 1.3 `AssetFailureMode` (`apps/assets/models/AssetReliability/AssetFailureModes.py`)
- **Table:** `assets_assetfailuremode`
- **Number Prefix:** `AFMA` (format: `AFMA-YYYYMM-XXXX`)
- **CHOICES:**
  - `RISK_LEVEL_CHOICES = [('low', 'Low Risk (RPN < 100)'), ('medium', 'Medium Risk (RPN 100 - 250)'), ('high', 'High Risk (RPN 251 - 500)'), ('extreme', 'Extreme Risk (RPN > 500)')]`
  - `RCM_STRATEGY_CHOICES = [('condition_based', 'Condition-Based Maintenance (CBM / PdM)'), ('time_based_pm', 'Time-Based Preventive Maintenance (PM)'), ('meter_based_pm', 'Meter / Run-Hours Based PM'), ('failure_finding', 'Failure-Finding Task (Hidden Failure Inspection)'), ('run_to_failure', 'Run-to-Failure (Corrective Only)'), ('redesign_required', 'Engineering Redesign / Modification Required')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Under Study)'), ('active', 'Active (Mitigation Enforced)'), ('superseded', 'Superseded (Obsolete)'), ('archived', 'Archived')]`
  - `RISK_LEVEL_CSS = {'low': 'badge-green', 'medium': 'badge-info', 'high': 'badge-amber', 'extreme': 'badge-red'}`
  - `RCM_STRATEGY_CSS = {'condition_based': 'badge-info', 'time_based_pm': 'badge-slate', 'meter_based_pm': 'badge-slate', 'failure_finding': 'badge-amber', 'run_to_failure': 'badge-muted', 'redesign_required': 'badge-red'}`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'superseded': 'badge-amber', 'archived': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_failure_modes')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='failure_modes', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='failure_modes', help_text='Operational equipment record')`
  - `asset_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='failure_modes', help_text='Asset category taxonomy')`
  - `component_subsystem`: `CharField(max_length=200, help_text='Component, assembly, or subsystem (e.g. Impeller, Bearing, Hydraulic Seal)')`
  - `function_description`: `TextField(help_text='Primary engineering function of the component in service')`
  - `functional_failure`: `CharField(max_length=255, help_text='Description of functional failure (inability to meet performance standard)')`
  - `failure_mode`: `CharField(max_length=255, help_text='Physical mechanism of failure (e.g. Fatigue Spalling, Cavitation Erosion, Seal Degradation)')`
  - `failure_cause`: `TextField(help_text='Root or proximate cause leading to the failure mode')`
  - `failure_effect`: `TextField(help_text='Local and plant-wide consequences on operations, safety, and environment')`
  - `severity_score`: `PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], help_text='Failure Severity ranking (1=Negligible to 10=Catastrophic/Hazardous)')`
  - `occurrence_score`: `PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], help_text='Failure Frequency / Occurrence ranking (1=Extremely Unlikely to 10=Frequent)')`
  - `detection_score`: `PositiveIntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)], help_text='Failure Detection ranking (1=Almost Certain to 10=Undetectable prior to failure)')`
  - `rpn`: `PositiveIntegerField(default=125, editable=False, help_text='Risk Priority Number: Severity × Occurrence × Detection (1 - 1000)')`
  - `risk_level`: `CharField(max_length=16, choices=RISK_LEVEL_CHOICES, default='medium', editable=False)`
  - `rcm_strategy`: `CharField(max_length=32, choices=RCM_STRATEGY_CHOICES, default='condition_based')`
  - `strategy_rationale`: `TextField(blank=True, help_text='Engineering justification for selected maintenance policy')`
  - `mitigation_task`: `TextField(blank=True, help_text='Specific proactive task description or inspection SOP')`
  - `linked_maintenance_schedule`: `ForeignKey('assets.AssetMaintenanceSchedule', on_delete=SET_NULL, null=True, blank=True, related_name='failure_modes', help_text='Preventive maintenance schedule enforcing this mitigation')`
  - `assessed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='assessed_asset_failure_modes')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_afma_ten_num_uniq')`
  - `Index(fields=['tenant', 'rpn'], name='idx_afma_ten_rpn')`
  - `Index(fields=['tenant', 'risk_level'], name='idx_afma_ten_risk')`
  - `Index(fields=['tenant', 'rcm_strategy'], name='idx_afma_ten_strat')`
  - `Index(fields=['tenant', 'status'], name='idx_afma_ten_stat')`
- **Actions / Calculations:**
  - `calculate_rpn`: sets `rpn = severity * occurrence * detection` and determines `risk_level`.
  - `asset_failure_mode_activate`: transitions `draft -> active`.
  - `asset_failure_mode_archive`: transitions `active -> archived`.
- **Form exclusions:** `tenant`, `number`, `rpn`, `risk_level`, `created_at`, `updated_at`.

---

### 1.4 `AssetCalibrationRecord` (`apps/assets/models/AssetReliability/AssetCalibrationRecords.py`)
- **Table:** `assets_assetcalibrationrecord`
- **Number Prefix:** `ACAL` (format: `ACAL-YYYYMM-XXXX`)
- **CHOICES:**
  - `TOLERANCE_UNIT_CHOICES = [('percent_span', '% of Span'), ('engineering_units', 'Direct Engineering Units'), ('celsius', '°C'), ('psi', 'psi'), ('bar', 'bar'), ('volts', 'V'), ('milliamps', 'mA')]`
  - `CALIBRATION_RESULT_CHOICES = [('pass', 'Pass (Within Tolerance)'), ('pass_with_adjustment', 'Pass with Adjustment (Re-zeroed / Aligned)'), ('fail_out_of_tolerance', 'Fail (Out of Tolerance)'), ('quarantined', 'Quarantined (Unusable / Out of Service)')]`
  - `STATUS_CHOICES = [('valid', 'Valid / Active'), ('expiring_soon', 'Expiring Within 30 Days'), ('expired', 'Expired (Overdue for Recalibration)'), ('voided', 'Voided')]`
  - `CALIBRATION_RESULT_CSS = {'pass': 'badge-green', 'pass_with_adjustment': 'badge-info', 'fail_out_of_tolerance': 'badge-red', 'quarantined': 'badge-red'}`
  - `STATUS_CSS = {'valid': 'badge-green', 'expiring_soon': 'badge-amber', 'expired': 'badge-red', 'voided': 'badge-muted'}`
  - `TOLERANCE_UNIT_CSS = {'percent_span': 'badge-info', 'engineering_units': 'badge-slate', 'celsius': 'badge-amber', 'psi': 'badge-info', 'bar': 'badge-info', 'volts': 'badge-amber', 'milliamps': 'badge-amber'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_calibration_records')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `instrument_tag`: `CharField(max_length=100, help_text='Gauge tag or instrument loop identifier')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='calibration_records', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='calibration_records', help_text='Operational equipment record')`
  - `calibrated_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='performed_asset_calibrations', help_text='Internal metrologist or instrument technician')`
  - `service_vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='vendor_asset_calibrations', help_text='External ISO 17025 accredited calibration lab / OEM')`
  - `calibration_date`: `DateField(default=timezone.now, help_text='Date calibration was completed')`
  - `calibration_frequency_days`: `PositiveIntegerField(default=365, help_text='Calibration recurrence cycle in days')`
  - `next_due_date`: `DateField(help_text='Next scheduled calibration deadline')`
  - `reference_standard_used`: `CharField(max_length=255, help_text='Traceable standard instrument, serial number, and cert ID')`
  - `traceability_certificate_no`: `CharField(max_length=100, blank=True, help_text='National metrology traceability standard certificate number')`
  - `setpoint_nominal`: `DecimalField(max_digits=12, decimal_places=4, help_text='Nominal calibration setpoint / target reference standard')`
  - `allowable_tolerance`: `DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.5000'), help_text='Maximum permissible error (+/- threshold)')`
  - `tolerance_unit`: `CharField(max_length=20, choices=TOLERANCE_UNIT_CHOICES, default='percent_span')`
  - `as_found_reading`: `DecimalField(max_digits=12, decimal_places=4, help_text='Initial measured value prior to any adjustment')`
  - `as_left_reading`: `DecimalField(max_digits=12, decimal_places=4, help_text='Final measured value following calibration / adjustment')`
  - `as_found_error`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text='Calculated error: As-Found - Setpoint')`
  - `as_left_error`: `DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, help_text='Calculated error: As-Left - Setpoint')`
  - `calibration_result`: `CharField(max_length=24, choices=CALIBRATION_RESULT_CHOICES, default='pass')`
  - `certificate_number`: `CharField(max_length=100, blank=True, help_text='Calibration report or certificate document identifier')`
  - `certificate_expiry`: `DateField(null=True, blank=True)`
  - `certificate_document`: `ForeignKey('core.Document', on_delete=SET_NULL, null=True, blank=True, related_name='asset_calibration_records', help_text='Digital calibration certificate scan / PDF')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='valid')`
  - `notes`: `TextField(blank=True, help_text='Calibration procedure, ambient conditions, or repair notes')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acal_ten_num_uniq')`
  - `Index(fields=['tenant', 'next_due_date'], name='idx_acal_ten_ndue')`
  - `Index(fields=['tenant', 'calibration_result'], name='idx_acal_ten_res')`
  - `Index(fields=['tenant', 'status'], name='idx_acal_ten_stat')`
  - `Index(fields=['tenant', 'instrument_tag'], name='idx_acal_ten_tag')`
- **Actions / Calculations:**
  - `calculate_errors`: auto-computes `as_found_error` and `as_left_error`, evaluates tolerance compliance, computes `next_due_date` if blank.
  - `asset_calibration_record_record_adjustment`: updates As-Left reading and recalculates error.
  - `asset_calibration_record_quarantine`: flags instrument as `quarantined` and triggers repair ticket.
- **Form exclusions:** `tenant`, `number`, `as_found_error`, `as_left_error`, `status`, `created_at`, `updated_at`.

---

## 2. Forms Contract

Located in `apps/assets/forms/AssetReliability/`:

### 2.1 `AssetConditionAssessmentForm`
- **Class:** `class AssetConditionAssessmentForm(forms.ModelForm)`
- **Model:** `AssetConditionAssessment`
- **Fields included:** `title`, `fixed_asset`, `operational_asset`, `asset_category`, `inspector`, `external_inspector`, `assessment_date`, `assessment_type`, `condition_grade`, `health_score`, `operating_status`, `checklist_summary`, `findings`, `recommendations`, `followup_required`
- **Excluded:** `tenant`, `number`, `status`, `triggered_maintenance_request`, `reviewed_by`, `reviewed_at`, `created_at`, `updated_at`
- **Widgets:** Tailwind standard classes (`form-input`, `form-select`, `form-textarea`). `assessment_date` widget `forms.DateInput(attrs={'type': 'date', 'class': 'form-input'})`.
- **Tenant scoping in `__init__`**: filter `fixed_asset`, `operational_asset`, `asset_category`, `external_inspector` (vendor role) by `tenant`.

### 2.2 `AssetTelemetryReadingForm`
- **Class:** `class AssetTelemetryReadingForm(forms.ModelForm)`
- **Model:** `AssetTelemetryReading`
- **Fields included:** `sensor_identifier`, `fixed_asset`, `operational_asset`, `recorded_by`, `recorded_at`, `source`, `metric_type`, `metric_unit`, `reading_value`, `baseline_value`, `is_anomaly`, `anomaly_confidence`, `alert_notes`
- **Excluded:** `tenant`, `number`, `deviation_percentage`, `threshold_status`, `triggered_maintenance_request`, `created_at`, `updated_at`
- **Widgets:** `recorded_at` widget `forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})`.
- **Tenant scoping in `__init__`**: filter `fixed_asset`, `operational_asset` by `tenant`.

### 2.3 `AssetFailureModeForm`
- **Class:** `class AssetFailureModeForm(forms.ModelForm)`
- **Model:** `AssetFailureMode`
- **Fields included:** `fixed_asset`, `operational_asset`, `asset_category`, `component_subsystem`, `function_description`, `functional_failure`, `failure_mode`, `failure_cause`, `failure_effect`, `severity_score`, `occurrence_score`, `detection_score`, `rcm_strategy`, `strategy_rationale`, `mitigation_task`, `linked_maintenance_schedule`, `assessed_by`, `status`
- **Excluded:** `tenant`, `number`, `rpn`, `risk_level`, `created_at`, `updated_at`
- **Tenant scoping in `__init__`**: filter `fixed_asset`, `operational_asset`, `asset_category`, `linked_maintenance_schedule` by `tenant`.

### 2.4 `AssetCalibrationRecordForm`
- **Class:** `class AssetCalibrationRecordForm(forms.ModelForm)`
- **Model:** `AssetCalibrationRecord`
- **Fields included:** `instrument_tag`, `fixed_asset`, `operational_asset`, `calibrated_by`, `service_vendor`, `calibration_date`, `calibration_frequency_days`, `next_due_date`, `reference_standard_used`, `traceability_certificate_no`, `setpoint_nominal`, `allowable_tolerance`, `tolerance_unit`, `as_found_reading`, `as_left_reading`, `calibration_result`, `certificate_number`, `certificate_expiry`, `certificate_document`, `notes`
- **Excluded:** `tenant`, `number`, `as_found_error`, `as_left_error`, `status`, `created_at`, `updated_at`
- **Widgets:** `calibration_date`, `next_due_date`, `certificate_expiry` date inputs.
- **Tenant scoping in `__init__`**: filter `fixed_asset`, `operational_asset`, `service_vendor`, `certificate_document` by `tenant`.

---

## 3. URLs Contract

App name is `assets`. Concatenated in `apps/assets/urls/__init__.py`.

```python
# apps/assets/urls/AssetReliability/AssetConditionAssessments.py
urlpatterns = [
    path('reliability/assessments/', views.asset_condition_assessment_list, name='asset_condition_assessment_list'),
    path('reliability/assessments/create/', views.asset_condition_assessment_create, name='asset_condition_assessment_create'),
    path('reliability/assessments/<int:pk>/', views.asset_condition_assessment_detail, name='asset_condition_assessment_detail'),
    path('reliability/assessments/<int:pk>/edit/', views.asset_condition_assessment_edit, name='asset_condition_assessment_edit'),
    path('reliability/assessments/<int:pk>/delete/', views.asset_condition_assessment_delete, name='asset_condition_assessment_delete'),
    path('reliability/assessments/<int:pk>/complete/', views.asset_condition_assessment_complete, name='asset_condition_assessment_complete'),
    path('reliability/assessments/<int:pk>/review/', views.asset_condition_assessment_review, name='asset_condition_assessment_review'),
    path('reliability/assessments/<int:pk>/trigger-request/', views.asset_condition_assessment_trigger_request, name='asset_condition_assessment_trigger_request'),
]

# apps/assets/urls/AssetReliability/AssetTelemetryReadings.py
urlpatterns = [
    path('reliability/telemetry/', views.asset_telemetry_reading_list, name='asset_telemetry_reading_list'),
    path('reliability/telemetry/create/', views.asset_telemetry_reading_create, name='asset_telemetry_reading_create'),
    path('reliability/telemetry/<int:pk>/', views.asset_telemetry_reading_detail, name='asset_telemetry_reading_detail'),
    path('reliability/telemetry/<int:pk>/edit/', views.asset_telemetry_reading_edit, name='asset_telemetry_reading_edit'),
    path('reliability/telemetry/<int:pk>/delete/', views.asset_telemetry_reading_delete, name='asset_telemetry_reading_delete'),
    path('reliability/telemetry/<int:pk>/trigger-request/', views.asset_telemetry_reading_trigger_request, name='asset_telemetry_reading_trigger_request'),
    path('reliability/telemetry/<int:pk>/flag-anomaly/', views.asset_telemetry_reading_flag_anomaly, name='asset_telemetry_reading_flag_anomaly'),
]

# apps/assets/urls/AssetReliability/AssetFailureModes.py
urlpatterns = [
    path('reliability/failure-modes/', views.asset_failure_mode_list, name='asset_failure_mode_list'),
    path('reliability/failure-modes/create/', views.asset_failure_mode_create, name='asset_failure_mode_create'),
    path('reliability/failure-modes/<int:pk>/', views.asset_failure_mode_detail, name='asset_failure_mode_detail'),
    path('reliability/failure-modes/<int:pk>/edit/', views.asset_failure_mode_edit, name='asset_failure_mode_edit'),
    path('reliability/failure-modes/<int:pk>/delete/', views.asset_failure_mode_delete, name='asset_failure_mode_delete'),
    path('reliability/failure-modes/<int:pk>/activate/', views.asset_failure_mode_activate, name='asset_failure_mode_activate'),
    path('reliability/failure-modes/<int:pk>/archive/', views.asset_failure_mode_archive, name='asset_failure_mode_archive'),
]

# apps/assets/urls/AssetReliability/AssetCalibrationRecords.py
urlpatterns = [
    path('reliability/calibrations/', views.asset_calibration_record_list, name='asset_calibration_record_list'),
    path('reliability/calibrations/create/', views.asset_calibration_record_create, name='asset_calibration_record_create'),
    path('reliability/calibrations/<int:pk>/', views.asset_calibration_record_detail, name='asset_calibration_record_detail'),
    path('reliability/calibrations/<int:pk>/edit/', views.asset_calibration_record_edit, name='asset_calibration_record_edit'),
    path('reliability/calibrations/<int:pk>/delete/', views.asset_calibration_record_delete, name='asset_calibration_record_delete'),
    path('reliability/calibrations/<int:pk>/quarantine/', views.asset_calibration_record_quarantine, name='asset_calibration_record_quarantine'),
]
```

---

## 4. Views & Context Contract

All views require `@login_required` (actions and deletes `@tenant_admin_required`). Tenant isolation: `tenant=request.tenant`.

### 4.1 `AssetConditionAssessment` Views
- **List View (`asset_condition_assessment_list`):**
  - **Context Keys:**
    - `condition_assessments`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `status_choices`: `AssetConditionAssessment.STATUS_CHOICES`
    - `condition_grade_choices`: `AssetConditionAssessment.CONDITION_GRADE_CHOICES`
    - `assessment_type_choices`: `AssetConditionAssessment.ASSESSMENT_TYPE_CHOICES`
    - `operating_status_choices`: `AssetConditionAssessment.OPERATING_STATUS_CHOICES`
    - `category_list`: `AssetCategory.objects.filter(tenant=request.tenant)`
    - `total_assessments`: Total count for tenant
    - `critical_defect_count`: Count with `condition_grade__in=['grade_4_poor', 'grade_5_critical']`
    - `average_health_score`: Avg of `health_score` (rounded to 1 decimal place)
    - `followup_count`: Count with `followup_required=True`
- **Detail View (`asset_condition_assessment_detail`):**
  - **Context Keys:**
    - `assessment`: `AssetConditionAssessment` instance
- **Form View (`asset_condition_assessment_create` / `asset_condition_assessment_edit`):**
  - **Context Keys:**
    - `form`: `AssetConditionAssessmentForm`
    - `assessment`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.2 `AssetTelemetryReading` Views
- **List View (`asset_telemetry_reading_list`):**
  - **Context Keys:**
    - `telemetry_readings`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `source_choices`: `AssetTelemetryReading.SOURCE_CHOICES`
    - `metric_type_choices`: `AssetTelemetryReading.METRIC_TYPE_CHOICES`
    - `threshold_status_choices`: `AssetTelemetryReading.THRESHOLD_STATUS_CHOICES`
    - `total_readings`: Total count for tenant
    - `critical_reading_count`: Count with `threshold_status='critical'`
    - `anomaly_reading_count`: Count with `is_anomaly=True` or `threshold_status='anomaly_detected'`
    - `normal_reading_count`: Count with `threshold_status='normal'`
- **Detail View (`asset_telemetry_reading_detail`):**
  - **Context Keys:**
    - `reading`: `AssetTelemetryReading` instance
- **Form View (`asset_telemetry_reading_create` / `asset_telemetry_reading_edit`):**
  - **Context Keys:**
    - `form`: `AssetTelemetryReadingForm`
    - `reading`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.3 `AssetFailureMode` Views
- **List View (`asset_failure_mode_list`):**
  - **Context Keys:**
    - `failure_modes`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `risk_level_choices`: `AssetFailureMode.RISK_LEVEL_CHOICES`
    - `rcm_strategy_choices`: `AssetFailureMode.RCM_STRATEGY_CHOICES`
    - `status_choices`: `AssetFailureMode.STATUS_CHOICES`
    - `category_list`: `AssetCategory.objects.filter(tenant=request.tenant)`
    - `total_failure_modes`: Total count for tenant
    - `extreme_risk_count`: Count with `risk_level='extreme'`
    - `high_risk_count`: Count with `risk_level='high'`
    - `cbm_strategy_count`: Count with `rcm_strategy='condition_based'`
- **Detail View (`asset_failure_mode_detail`):**
  - **Context Keys:**
    - `failure_mode`: `AssetFailureMode` instance
- **Form View (`asset_failure_mode_create` / `asset_failure_mode_edit`):**
  - **Context Keys:**
    - `form`: `AssetFailureModeForm`
    - `failure_mode`: Instance when editing, None when creating
    - `is_edit`: Boolean

### 4.4 `AssetCalibrationRecord` Views
- **List View (`asset_calibration_record_list`):**
  - **Context Keys:**
    - `calibration_records`: Page object / queryset
    - `page_obj`: Django pagination object
    - `paginator`: Paginator instance
    - `is_paginated`: Boolean
    - `calibration_result_choices`: `AssetCalibrationRecord.CALIBRATION_RESULT_CHOICES`
    - `status_choices`: `AssetCalibrationRecord.STATUS_CHOICES`
    - `tolerance_unit_choices`: `AssetCalibrationRecord.TOLERANCE_UNIT_CHOICES`
    - `vendor_list`: `Party.objects.filter(tenant=request.tenant, party_roles__role='vendor').distinct()`
    - `total_calibrations`: Total count for tenant
    - `passed_count`: Count with `calibration_result__in=['pass', 'pass_with_adjustment']`
    - `failed_count`: Count with `calibration_result='fail_out_of_tolerance'`
    - `overdue_count`: Count with `status='expired'` or `next_due_date__lt=timezone.now().date()`
- **Detail View (`asset_calibration_record_detail`):**
  - **Context Keys:**
    - `calibration`: `AssetCalibrationRecord` instance
- **Form View (`asset_calibration_record_create` / `asset_calibration_record_edit`):**
  - **Context Keys:**
    - `form`: `AssetCalibrationRecordForm`
    - `calibration`: Instance when editing, None when creating
    - `is_edit`: Boolean

---

## 5. Templates Contract

Template paths:
- `templates/assets/assetreliability/asset_condition_assessment/{list,detail,form}.html`
- `templates/assets/assetreliability/asset_telemetry_reading/{list,detail,form}.html`
- `templates/assets/assetreliability/asset_failure_mode/{list,detail,form}.html`
- `templates/assets/assetreliability/asset_calibration_record/{list,detail,form}.html`

All templates:
- Extend `base.html`
- Include breadcrumbs and `.page-header`
- List pages have 4 stat cards with icons (`blue`, `green`, `orange`, `purple`, `slate`)
- List filter form parses `request.GET` and maintains query params
- Table has Actions column (view, edit, delete with confirm modal/CSRF)
- Action buttons on detail page for business state transitions (e.g. Complete, Review, Trigger Maintenance Request)
- Badges use color-named classes ONLY (`badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`)
- Empty state `.empty-state` with Lucide icon and clear call-to-action button

---

## 6. Navigation Contract (`LIVE_LINKS["11.7"]`)

In `apps/core/navigation.py`:
```python
    "11.7": {
        "Condition Assessment & Inspections": "assets:asset_condition_assessment_list",
        "Predictive Maintenance & IoT Integration": "assets:asset_telemetry_reading_list",
        "Failure Mode Analysis (FMEA)": "assets:asset_failure_mode_list",
        "Lubrication & Calibration Management": "assets:asset_calibration_record_list",
        "Reliability-Centered Maintenance (RCM)": "assets:asset_failure_mode_list",
        # Plural and convenience aliases
        "Condition Assessments": "assets:asset_condition_assessment_list",
        "Asset Condition Assessments": "assets:asset_condition_assessment_list",
        "Telemetry Readings": "assets:asset_telemetry_reading_list",
        "Asset Telemetry Readings": "assets:asset_telemetry_reading_list",
        "Failure Modes (FMEA)": "assets:asset_failure_mode_list",
        "Asset Failure Modes": "assets:asset_failure_mode_list",
        "FMEA Registry": "assets:asset_failure_mode_list",
        "Calibration Records": "assets:asset_calibration_record_list",
        "Asset Calibration Records": "assets:asset_calibration_record_list",
        "RCM Strategy": "assets:asset_failure_mode_list",
        "Asset Reliability & Condition Monitoring": "assets:asset_condition_assessment_list",
    },
```

---

## 7. Seeder Contract (`seed_assets.py`)

Function `_seed_tenant_11_7(self, tenant)`:
- Idempotent: checks `if AssetConditionAssessment.objects.filter(tenant=tenant).exists(): return`
- Seeds for Acme Corporation:
  - 3 Condition Assessments (1 ultrasonic NDT on CNC Lathe [Grade 2 Good], 1 thermography inspection on Main Transformer [Grade 4 Poor with followup request], 1 vibration pen check on Air Compressor [Grade 1 Excellent])
  - 4 Telemetry Readings (Vibration velocity RMS on Centrifugal Pump [Normal], Bearing temp on Extruder Motor [Warning], Acoustic ultrasound on Steam Valve [Anomaly Detected with triggered request], Vibration peak accel on Chiller [Normal])
  - 3 Failure Modes (Centrifugal Pump Impeller Cavitation [RPN 280 High, Condition-Based], Hydraulic Cylinder Seal Degradation [RPN 160 Medium, Time-Based PM], Electrical Motor Stator Insulation Breakdown [RPN 560 Extreme, Redesign / CBM])
  - 3 Calibration Records (Digital Pressure Transmitter [Pass, 365d cycle], Precision Digital Caliper [Pass with Adjustment], Resistance Temperature Detector [Pass])
- Seeds for Globex Corporation:
  - 2 Condition Assessments
  - 2 Telemetry Readings
  - 2 Failure Modes
  - 2 Calibration Records

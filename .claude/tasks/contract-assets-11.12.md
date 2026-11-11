# Contract — Sub-module 11.12: Asset Risk Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.12 Asset Risk Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-11 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0015_...`.
- **Package Layout:** `AssetRisk/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/assetrisk/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetRiskRegister` (`apps/assets/models/AssetRisk/AssetRiskRegisters.py`)
- **Table:** `assets_assetriskregister`
- **Number Prefix:** `ARK` (format: `ARK-YYYYMM-XXXX`)
- **CHOICES:**
  - `RISK_CATEGORY_CHOICES = [('operational', 'Operational & Reliability Risk'), ('financial', 'Financial & Capital Asset Loss'), ('safety_health', 'Occupational Safety & Health (EHS)'), ('environmental', 'Environmental Release / Contamination'), ('cybersecurity', 'OT / IoT / SCADA Cybersecurity'), ('regulatory', 'Regulatory & Statutory Non-Compliance'), ('geopolitical_supply_chain', 'Geopolitical & Supply Chain Disruption'), ('reputational', 'Reputational & Brand Damage')]`
  - `THREAT_SOURCE_CHOICES = [('equipment_wear', 'Mechanical / Component Wear & Aging'), ('operator_error', 'Human / Operator Procedure Error'), ('cyber_attack', 'Cyber Attack / Ransomware / Malware'), ('extreme_weather', 'Extreme Weather / Natural Disaster'), ('supply_chain_disruption', 'Supply Chain / Sole-Source Disruption'), ('vendor_insolvency', 'Vendor Bankruptcy / Contract Default'), ('regulatory_mandate', 'Statutory / Regulatory Rule Change'), ('utility_grid_failure', 'Utility / Power Grid Outage')]`
  - `TREATMENT_STRATEGY_CHOICES = [('mitigate', 'Mitigate (Engineering Controls & PM)'), ('transfer', 'Transfer (Insurance / Contractual)'), ('avoid', 'Avoid (Decommission / Process Change)'), ('accept', 'Accept (Documented Residual Risk)')]`
  - `STATUS_CHOICES = [('identified', 'Risk Identified'), ('assessed', 'Risk Assessed & Scored'), ('treating', 'Active Treatment / Remediation'), ('monitored', 'Monitored / Stable'), ('closed', 'Risk Retired / Closed')]`
  - `RISK_LEVEL_CHOICES = [('low', 'Low Risk (1-4)'), ('medium', 'Medium Risk (5-9)'), ('high', 'High Risk (10-14)'), ('critical', 'Critical Risk (15-25)')]`
  - `REVIEW_FREQUENCY_CHOICES = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('semi_annually', 'Semi-Annually'), ('annually', 'Annually')]`
  - `STATUS_CSS = {'identified': 'badge-slate', 'assessed': 'badge-info', 'treating': 'badge-amber', 'monitored': 'badge-purple', 'closed': 'badge-green'}`
  - `RISK_LEVEL_CSS = {'low': 'badge-green', 'medium': 'badge-info', 'high': 'badge-amber', 'critical': 'badge-red'}`
  - `RISK_CATEGORY_CSS = {'operational': 'badge-info', 'financial': 'badge-purple', 'safety_health': 'badge-red', 'environmental': 'badge-green', 'cybersecurity': 'badge-amber', 'regulatory': 'badge-slate', 'geopolitical_supply_chain': 'badge-amber', 'reputational': 'badge-muted'}`
  - `TREATMENT_STRATEGY_CSS = {'mitigate': 'badge-info', 'transfer': 'badge-purple', 'avoid': 'badge-amber', 'accept': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_risks')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Descriptive title of operational or infrastructure risk')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='registered_risks', help_text='Specific physical plant equipment or facility asset')`
  - `category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='registered_risks', help_text='Asset taxonomy category for fleet-wide risk profiles')`
  - `risk_category`: `CharField(max_length=30, choices=RISK_CATEGORY_CHOICES, default='operational')`
  - `threat_source`: `CharField(max_length=30, choices=THREAT_SOURCE_CHOICES, default='equipment_wear')`
  - `failure_mode`: `CharField(max_length=255, blank=True, help_text='FMEA failure mode, trigger condition, or failure scenario')`
  - `description`: `TextField(blank=True, help_text='Comprehensive technical description and operational consequence')`
  - `inherent_likelihood`: `PositiveSmallIntegerField(default=3, help_text='Inherent Likelihood (1=Rare to 5=Almost Certain)')`
  - `inherent_impact`: `PositiveSmallIntegerField(default=3, help_text='Inherent Impact (1=Insignificant to 5=Catastrophic)')`
  - `inherent_risk_score`: `PositiveIntegerField(default=9, editable=False, help_text='Inherent Risk Score (Likelihood x Impact, 1-25)')`
  - `inherent_risk_level`: `CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default='medium', editable=False)`
  - `residual_likelihood`: `PositiveSmallIntegerField(default=2, help_text='Residual Likelihood post-mitigation (1-5)')`
  - `residual_impact`: `PositiveSmallIntegerField(default=2, help_text='Residual Impact post-mitigation (1-5)')`
  - `residual_risk_score`: `PositiveIntegerField(default=4, editable=False, help_text='Residual Risk Score (Likelihood x Impact, 1-25)')`
  - `residual_risk_level`: `CharField(max_length=20, choices=RISK_LEVEL_CHOICES, default='low', editable=False)`
  - `risk_owner`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='owned_asset_risks', help_text='Assigned risk manager or engineer')`
  - `treatment_strategy`: `CharField(max_length=20, choices=TREATMENT_STRATEGY_CHOICES, default='mitigate')`
  - `financial_exposure_amount`: `DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'), help_text='Estimated financial loss or replacement impact')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='identified')`
  - `review_frequency`: `CharField(max_length=20, choices=REVIEW_FREQUENCY_CHOICES, default='quarterly')`
  - `next_review_date`: `DateField(null=True, blank=True, help_text='Next scheduled risk reassessment date')`
  - `last_reviewed_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ark_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ark_ten_stat')`
  - `Index(fields=['tenant', 'risk_category'], name='idx_ark_ten_cat')`
  - `Index(fields=['tenant', 'inherent_risk_level'], name='idx_ark_ten_in_lvl')`
  - `Index(fields=['tenant', 'residual_risk_level'], name='idx_ark_ten_res_lvl')`
  - `Index(fields=['tenant', 'asset'], name='idx_ark_ten_ast')`
- **Business Logic & Actions:**
  - `calculate_scores()`: auto-calculates inherent & residual scores and levels
  - `asset_risk_register_assess`: updates status to `assessed`
  - `asset_risk_register_close`: marks status as `closed`

---

### 1.2 `AssetBusinessContinuityPlan` (`apps/assets/models/AssetRisk/AssetBusinessContinuityPlans.py`)
- **Table:** `assets_assetbusinesscontinuityplan`
- **Number Prefix:** `ABC` (format: `ABC-YYYYMM-XXXX`)
- **CHOICES:**
  - `REDUNDANCY_TYPE_CHOICES = [('hot_standby', 'Hot Standby (Instant Automatic Failover)'), ('warm_standby', 'Warm Standby (Rapid Manual Spin-Up < 2 hrs)'), ('cold_standby', 'Cold Standby (Offsite / Warehoused Spare)'), ('n_plus_one_cluster', 'N+1 Resilient Active Cluster'), ('reciprocal_agreement', 'Reciprocal Agreement / Partner Capacity'), ('mobile_replacement', 'Mobile Replacement / Rental Unit'), ('none_single_point_of_failure', 'Single Point of Failure (SPOF - No Redundancy)')]`
  - `DISASTER_SCENARIO_CHOICES = [('power_grid_outage', 'Total Power Grid / Substation Outage'), ('fire_explosion', 'Facility Fire / Industrial Explosion'), ('flood_natural_disaster', 'Flood / Hurricane / Severe Weather'), ('cyber_attack_ransomware', 'Cyber Attack / Ransomware Lockout'), ('critical_hardware_loss', 'Catastrophic Mechanical / Hardware Loss'), ('hazmat_contamination', 'Hazmat Release / Chemical Contamination')]`
  - `DRILL_FREQUENCY_CHOICES = [('quarterly', 'Quarterly'), ('semi_annually', 'Semi-Annually'), ('annually', 'Annually')]`
  - `DRILL_RESULT_CHOICES = [('not_tested', 'Not Tested / Planned'), ('passed', 'Drill Passed (Met RTO/RPO)'), ('passed_with_deficiencies', 'Passed with Deficiencies'), ('failed', 'Drill Failed (Exceeded RTO/RPO)')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Pending Validation)'), ('active', 'Active & Approved BCP'), ('under_review', 'Under Periodic Review'), ('deprecated', 'Deprecated / Retired')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'under_review': 'badge-amber', 'deprecated': 'badge-muted'}`
  - `REDUNDANCY_TYPE_CSS = {'hot_standby': 'badge-green', 'warm_standby': 'badge-info', 'cold_standby': 'badge-slate', 'n_plus_one_cluster': 'badge-purple', 'reciprocal_agreement': 'badge-info', 'mobile_replacement': 'badge-slate', 'none_single_point_of_failure': 'badge-red'}`
  - `DRILL_RESULT_CSS = {'not_tested': 'badge-slate', 'passed': 'badge-green', 'passed_with_deficiencies': 'badge-amber', 'failed': 'badge-red'}`
  - `DISASTER_SCENARIO_CSS = {'power_grid_outage': 'badge-amber', 'fire_explosion': 'badge-red', 'flood_natural_disaster': 'badge-info', 'cyber_attack_ransomware': 'badge-red', 'critical_hardware_loss': 'badge-purple', 'hazmat_contamination': 'badge-amber'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_continuity_plans')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='BCP Title, e.g. Primary Turbine Redundancy & Recovery Plan')`
  - `primary_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='continuity_plans', help_text='Primary operational asset requiring continuity coverage')`
  - `backup_redundant_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='redundant_for_continuity_plans', help_text='Designated redundant or backup asset')`
  - `redundancy_type`: `CharField(max_length=32, choices=REDUNDANCY_TYPE_CHOICES, default='none_single_point_of_failure')`
  - `recovery_time_objective_hours`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal('4.00'), help_text='Recovery Time Objective (RTO in hours)')`
  - `recovery_point_objective_hours`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal('1.00'), help_text='Recovery Point Objective (RPO in hours)')`
  - `maximum_tolerable_downtime_hours`: `DecimalField(max_digits=6, decimal_places=2, default=Decimal('24.00'), help_text='Maximum Tolerable Downtime (MTD in hours)')`
  - `disaster_scenario`: `CharField(max_length=30, choices=DISASTER_SCENARIO_CHOICES, default='critical_hardware_loss')`
  - `failover_procedure`: `TextField(blank=True, help_text='Step-by-step procedures to activate backup asset')`
  - `failback_procedure`: `TextField(blank=True, help_text='Step-by-step procedures to restore primary operations')`
  - `alternate_facility_site`: `CharField(max_length=255, blank=True, help_text='Secondary facility or backup plant site')`
  - `critical_spares_required`: `TextField(blank=True, help_text='Essential spare components and vendor SLA lead times')`
  - `emergency_lead`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='led_asset_continuity_plans', help_text='Designated incident commander or plant resilience engineer')`
  - `drill_frequency`: `CharField(max_length=20, choices=DRILL_FREQUENCY_CHOICES, default='annually')`
  - `last_drill_date`: `DateField(null=True, blank=True)`
  - `next_drill_date`: `DateField(null=True, blank=True)`
  - `drill_result`: `CharField(max_length=30, choices=DRILL_RESULT_CHOICES, default='not_tested')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_abc_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_abc_ten_stat')`
  - `Index(fields=['tenant', 'redundancy_type'], name='idx_abc_ten_red')`
  - `Index(fields=['tenant', 'primary_asset'], name='idx_abc_ten_past')`
  - `Index(fields=['tenant', 'drill_result'], name='idx_abc_ten_dres')`
- **Actions / State Machine:**
  - `asset_business_continuity_plan_activate`: sets `status = 'active'`
  - `asset_business_continuity_plan_record_drill`: updates `last_drill_date`, `drill_result`

---

### 1.3 `AssetCyberSecurityProfile` (`apps/assets/models/AssetRisk/AssetCyberSecurityProfiles.py`)
- **Table:** `assets_assetcybersecurityprofile`
- **Number Prefix:** `ACS` (format: `ACS-YYYYMM-XXXX`)
- **CHOICES:**
  - `DEVICE_TYPE_CHOICES = [('plc_controller', 'Programmable Logic Controller (PLC)'), ('scada_server', 'SCADA / DCS Central Server'), ('rtu_remote_terminal', 'Remote Terminal Unit (RTU)'), ('iot_sensor', 'IoT Edge Sensor / Telemetry Node'), ('hmi_touchscreen', 'Human-Machine Interface (HMI)'), ('network_switch_gateway', 'Industrial Switch / Security Gateway'), ('vfd_drive', 'Variable Frequency Drive (VFD)'), ('smart_meter', 'Smart Power / Flow Meter'), ('robotic_cell', 'Robotic Arm / Automated Cell')]`
  - `NETWORK_ZONE_CHOICES = [('enterprise_it', 'Purdue Level 4: Enterprise IT Network'), ('dmz', 'Purdue Level 3.5: Industrial DMZ'), ('supervisory_scada', 'Purdue Level 3: Plant Operations & SCADA'), ('control_plc', 'Purdue Level 2: Area Supervisory Control & PLC'), ('process_io', 'Purdue Level 1: Basic Process I/O & Drives'), ('isolated_airgap', 'Purdue Level 0: Physically Air-Gapped')]`
  - `PROTOCOL_CHOICES = [('modbus_tcp', 'Modbus TCP / RTU'), ('opc_ua', 'OPC UA / DA'), ('ethernet_ip', 'EtherNet / IP (CIP)'), ('profinet', 'PROFINET / PROFIBUS'), ('bacnet', 'BACnet IP (Building Automation)'), ('dnp3', 'DNP3 (Electric Utilities)'), ('mqtt', 'MQTT / Sparkplug B'), ('https_rest', 'HTTPS / REST API'), ('proprietary', 'Vendor Proprietary Protocol')]`
  - `FIRMWARE_STATUS_CHOICES = [('up_to_date', 'Up-to-Date (Current Baseline)'), ('update_available', 'Update Available (Non-Critical)'), ('critical_patch_pending', 'Critical Security Patch Pending'), ('end_of_life_unsupported', 'End-of-Life / Unsupported Firmware')]`
  - `EXPOSURE_LEVEL_CHOICES = [('air_gapped', 'Physically Air-Gapped'), ('isolated_vlan', 'Isolated Micro-Segmented VLAN'), ('monitored_dmz', 'Monitored DMZ Gateway'), ('internet_facing', 'Directly Internet / Cloud-Facing')]`
  - `POSTURE_STATUS_CHOICES = [('secure', 'Secure (Compliant Baseline)'), ('attention_required', 'Attention Required (Minor Findings)'), ('vulnerable', 'Vulnerable (Active CVE / Unpatched)'), ('compromised', 'Compromised / Incident Investigated')]`
  - `POSTURE_STATUS_CSS = {'secure': 'badge-green', 'attention_required': 'badge-amber', 'vulnerable': 'badge-red', 'compromised': 'badge-red'}`
  - `FIRMWARE_STATUS_CSS = {'up_to_date': 'badge-green', 'update_available': 'badge-info', 'critical_patch_pending': 'badge-amber', 'end_of_life_unsupported': 'badge-red'}`
  - `NETWORK_ZONE_CSS = {'enterprise_it': 'badge-slate', 'dmz': 'badge-amber', 'supervisory_scada': 'badge-info', 'control_plc': 'badge-purple', 'process_io': 'badge-slate', 'isolated_airgap': 'badge-green'}`
  - `EXPOSURE_LEVEL_CSS = {'air_gapped': 'badge-green', 'isolated_vlan': 'badge-info', 'monitored_dmz': 'badge-amber', 'internet_facing': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_cyber_profiles')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='cybersecurity_profiles', help_text='Physical equipment or connected controller')`
  - `device_type`: `CharField(max_length=30, choices=DEVICE_TYPE_CHOICES, default='plc_controller')`
  - `ip_address`: `GenericIPAddressField(null=True, blank=True, help_text='Static or industrial network IPv4/IPv6 address')`
  - `mac_address`: `CharField(max_length=50, blank=True, help_text='Hardware MAC address')`
  - `network_zone`: `CharField(max_length=30, choices=NETWORK_ZONE_CHOICES, default='control_plc')`
  - `firmware_version`: `CharField(max_length=100, default='1.0.0', help_text='Active firmware revision running on device')`
  - `latest_available_firmware`: `CharField(max_length=100, blank=True, help_text='Latest vendor release firmware version')`
  - `firmware_update_status`: `CharField(max_length=30, choices=FIRMWARE_STATUS_CHOICES, default='up_to_date')`
  - `protocol_used`: `CharField(max_length=30, choices=PROTOCOL_CHOICES, default='modbus_tcp')`
  - `exposure_level`: `CharField(max_length=30, choices=EXPOSURE_LEVEL_CHOICES, default='isolated_vlan')`
  - `known_vulnerabilities_cve`: `TextField(blank=True, help_text='Common Vulnerabilities and Exposures (CVE) IDs and advisory details')`
  - `cve_risk_score`: `DecimalField(max_digits=4, decimal_places=1, default=Decimal('0.0'), help_text='Base CVSS score (0.0 to 10.0)')`
  - `compensating_controls`: `TextField(blank=True, help_text='Compensating security controls (firewall isolation, physical interlocks)')`
  - `last_vulnerability_scan_date`: `DateField(null=True, blank=True)`
  - `security_posture_status`: `CharField(max_length=30, choices=POSTURE_STATUS_CHOICES, default='secure')`
  - `patch_freeze_until`: `DateField(null=True, blank=True, help_text='Production blackout window blocking firmware updates')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acs_ten_num_uniq')`
  - `Index(fields=['tenant', 'security_posture_status'], name='idx_acs_ten_post')`
  - `Index(fields=['tenant', 'firmware_update_status'], name='idx_acs_ten_fw')`
  - `Index(fields=['tenant', 'network_zone'], name='idx_acs_ten_zone')`
  - `Index(fields=['tenant', 'asset'], name='idx_acs_ten_ast')`
- **Actions / State Machine:**
  - `asset_cybersecurity_scan`: updates scan date and security posture

---

### 1.4 `AssetRiskMitigationAction` (`apps/assets/models/AssetRisk/AssetRiskMitigationActions.py`)
- **Table:** `assets_assetriskmitigationaction`
- **Number Prefix:** `ARMA` (format: `ARMA-YYYYMM-XXXX`)
- **CHOICES:**
  - `ACTION_TYPE_CHOICES = [('engineering_control', 'Engineering Design & Safeguard Control'), ('redundancy_addition', 'Redundancy & Backup System Addition'), ('firmware_security_patch', 'Firmware Patch / OT Cyber Hardening'), ('insurance_transfer', 'Insurance Coverage & Risk Transfer'), ('supplier_diversification', 'Alternative Supplier / Dual Sourcing'), ('spare_parts_buffer', 'Critical Spare Parts Buffer Inventory'), ('procedure_training', 'Standard Operating Procedure & Training'), ('preventive_inspection', 'Enhanced PM & Predictive Telemetry')]`
  - `PRIORITY_CHOICES = [('critical', 'Critical (Immediate Action)'), ('high', 'High Priority'), ('medium', 'Medium Priority'), ('low', 'Low Priority')]`
  - `STATUS_CHOICES = [('planned', 'Action Planned'), ('in_progress', 'Implementation In Progress'), ('completed', 'Completed (Pending Validation)'), ('verified_effective', 'Verified Effective (Closed)'), ('deferred', 'Deferred / Rescheduled'), ('cancelled', 'Cancelled')]`
  - `EFFECTIVENESS_CHOICES = [('pending_evaluation', 'Pending Evaluation'), ('highly_effective', 'Highly Effective (Residual Risk Reduced)'), ('partially_effective', 'Partially Effective (Minor Residual Risk)'), ('ineffective', 'Ineffective (Requires Further Action)')]`
  - `STATUS_CSS = {'planned': 'badge-slate', 'in_progress': 'badge-amber', 'completed': 'badge-info', 'verified_effective': 'badge-green', 'deferred': 'badge-muted', 'cancelled': 'badge-red'}`
  - `PRIORITY_CSS = {'critical': 'badge-red', 'high': 'badge-amber', 'medium': 'badge-info', 'low': 'badge-slate'}`
  - `ACTION_TYPE_CSS = {'engineering_control': 'badge-info', 'redundancy_addition': 'badge-purple', 'firmware_security_patch': 'badge-amber', 'insurance_transfer': 'badge-slate', 'supplier_diversification': 'badge-green', 'spare_parts_buffer': 'badge-info', 'procedure_training': 'badge-slate', 'preventive_inspection': 'badge-info'}`
  - `EFFECTIVENESS_CSS = {'pending_evaluation': 'badge-slate', 'highly_effective': 'badge-green', 'partially_effective': 'badge-amber', 'ineffective': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_mitigation_actions')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Remediation task title')`
  - `risk`: `ForeignKey('assets.AssetRiskRegister', on_delete=CASCADE, related_name='mitigation_actions', help_text='Parent asset risk being mitigated')`
  - `action_type`: `CharField(max_length=30, choices=ACTION_TYPE_CHOICES, default='engineering_control')`
  - `description`: `TextField(blank=True, help_text='Detailed implementation scope and technical deliverables')`
  - `assigned_to`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='assigned_asset_mitigations', help_text='Assigned engineer or specialist')`
  - `alternative_supplier`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='risk_alternative_suppliers', help_text='Alternative vendor for dual-sourcing / supply resilience')`
  - `target_completion_date`: `DateField(help_text='Required remediation deadline')`
  - `actual_completion_date`: `DateField(null=True, blank=True)`
  - `estimated_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `actual_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='planned')`
  - `verification_notes`: `TextField(blank=True, help_text='Post-implementation verification observations')`
  - `effectiveness_rating`: `CharField(max_length=24, choices=EFFECTIVENESS_CHOICES, default='pending_evaluation')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_arma_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_arma_ten_stat')`
  - `Index(fields=['tenant', 'priority'], name='idx_arma_ten_prio')`
  - `Index(fields=['tenant', 'action_type'], name='idx_arma_ten_type')`
  - `Index(fields=['tenant', 'risk'], name='idx_arma_ten_rsk')`
- **Actions / State Machine:**
  - `asset_risk_mitigation_complete`: sets `actual_completion_date = timezone.now().date()`, status to `completed`
  - `asset_risk_mitigation_verify`: sets status to `verified_effective`

---

## 2. Forms Contract & Exclusions

All forms live under `apps/assets/forms/AssetRisk/<Entity>.py`. Forms exclude tenant, auto-number, auto-timestamps, and derived calculation fields.

| Entity | Form Class | Excluded Fields | Required Fields & Widgets |
|---|---|---|---|
| `AssetRiskRegister` | `AssetRiskRegisterForm` | `tenant`, `number`, `inherent_risk_score`, `inherent_risk_level`, `residual_risk_score`, `residual_risk_level`, `last_reviewed_at`, `created_at`, `updated_at` | `title`, `risk_category`, `threat_source`, `inherent_likelihood`, `inherent_impact`, `residual_likelihood`, `residual_impact`, `status`. DateInput for `next_review_date`. Textarea for `description`. |
| `AssetBusinessContinuityPlan` | `AssetBusinessContinuityPlanForm` | `tenant`, `number`, `created_at`, `updated_at` | `title`, `redundancy_type`, `disaster_scenario`, `recovery_time_objective_hours`, `recovery_point_objective_hours`, `maximum_tolerable_downtime_hours`, `status`. DateInput for `last_drill_date`, `next_drill_date`. Textarea for `failover_procedure`, `failback_procedure`, `critical_spares_required`. |
| `AssetCyberSecurityProfile` | `AssetCyberSecurityProfileForm` | `tenant`, `number`, `created_at`, `updated_at` | `asset`, `device_type`, `network_zone`, `firmware_version`, `protocol_used`, `exposure_level`, `security_posture_status`. DateInput for `last_vulnerability_scan_date`, `patch_freeze_until`. Textarea for `known_vulnerabilities_cve`, `compensating_controls`. |
| `AssetRiskMitigationAction` | `AssetRiskMitigationActionForm` | `tenant`, `number`, `actual_completion_date`, `created_at`, `updated_at` | `title`, `risk`, `action_type`, `priority`, `target_completion_date`, `status`. DateInput for `target_completion_date`. Textarea for `description`, `verification_notes`. |

---

## 3. URLs Contract

App name is `assets`. All routes registered in `apps/assets/urls/AssetRisk/<Entity>.py` and re-exported in `apps/assets/urls/__init__.py`.

### 3.1 `AssetRiskRegister`
- `assets:asset_risk_register_list` -> `/assets/risk/registers/`
- `assets:asset_risk_register_create` -> `/assets/risk/registers/create/`
- `assets:asset_risk_register_detail` -> `/assets/risk/registers/<int:pk>/`
- `assets:asset_risk_register_edit` -> `/assets/risk/registers/<int:pk>/edit/`
- `assets:asset_risk_register_delete` -> `/assets/risk/registers/<int:pk>/delete/`
- `assets:asset_risk_register_assess` -> `/assets/risk/registers/<int:pk>/assess/` (POST)
- `assets:asset_risk_register_close` -> `/assets/risk/registers/<int:pk>/close/` (POST)

### 3.2 `AssetBusinessContinuityPlan`
- `assets:asset_business_continuity_plan_list` -> `/assets/risk/continuity-plans/`
- `assets:asset_business_continuity_plan_create` -> `/assets/risk/continuity-plans/create/`
- `assets:asset_business_continuity_plan_detail` -> `/assets/risk/continuity-plans/<int:pk>/`
- `assets:asset_business_continuity_plan_edit` -> `/assets/risk/continuity-plans/<int:pk>/edit/`
- `assets:asset_business_continuity_plan_delete` -> `/assets/risk/continuity-plans/<int:pk>/delete/`
- `assets:asset_business_continuity_plan_activate` -> `/assets/risk/continuity-plans/<int:pk>/activate/` (POST)
- `assets:asset_business_continuity_plan_drill` -> `/assets/risk/continuity-plans/<int:pk>/drill/` (POST)

### 3.3 `AssetCyberSecurityProfile`
- `assets:asset_cybersecurity_profile_list` -> `/assets/risk/cybersecurity/`
- `assets:asset_cybersecurity_profile_create` -> `/assets/risk/cybersecurity/create/`
- `assets:asset_cybersecurity_profile_detail` -> `/assets/risk/cybersecurity/<int:pk>/`
- `assets:asset_cybersecurity_profile_edit` -> `/assets/risk/cybersecurity/<int:pk>/edit/`
- `assets:asset_cybersecurity_profile_delete` -> `/assets/risk/cybersecurity/<int:pk>/delete/`
- `assets:asset_cybersecurity_profile_scan` -> `/assets/risk/cybersecurity/<int:pk>/scan/` (POST)

### 3.4 `AssetRiskMitigationAction`
- `assets:asset_risk_mitigation_action_list` -> `/assets/risk/mitigations/`
- `assets:asset_risk_mitigation_action_create` -> `/assets/risk/mitigations/create/`
- `assets:asset_risk_mitigation_action_detail` -> `/assets/risk/mitigations/<int:pk>/`
- `assets:asset_risk_mitigation_action_edit` -> `/assets/risk/mitigations/<int:pk>/edit/`
- `assets:asset_risk_mitigation_action_delete` -> `/assets/risk/mitigations/<int:pk>/delete/`
- `assets:asset_risk_mitigation_action_complete` -> `/assets/risk/mitigations/<int:pk>/complete/` (POST)
- `assets:asset_risk_mitigation_action_verify` -> `/assets/risk/mitigations/<int:pk>/verify/` (POST)

---

## 4. View Context Keys Contract (L7 Pinned)

### 4.1 `AssetRiskRegister`
- **List View (`asset_risk_register_list`):**
  - `risks`: Page object / queryset of `AssetRiskRegister` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `category_choices`: `AssetRiskRegister.RISK_CATEGORY_CHOICES`
  - `level_choices`: `AssetRiskRegister.RISK_LEVEL_CHOICES`
  - `status_choices`: `AssetRiskRegister.STATUS_CHOICES`
  - `strategy_choices`: `AssetRiskRegister.TREATMENT_STRATEGY_CHOICES`
  - `total_risks`: Integer total count
  - `critical_risks_count`: Integer count where `inherent_risk_level='critical'`
  - `high_risks_count`: Integer count where `inherent_risk_level='high'`
  - `active_treatment_count`: Integer count where `status='treating'`
  - `total_financial_exposure`: Decimal sum of `financial_exposure_amount`
- **Detail View (`asset_risk_register_detail`):**
  - `risk`: Subject `AssetRiskRegister` instance
  - `mitigation_actions`: Related mitigation actions queryset
- **Form Views (Create/Edit):**
  - `form`: `AssetRiskRegisterForm`
  - `risk`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.2 `AssetBusinessContinuityPlan`
- **List View (`asset_business_continuity_plan_list`):**
  - `plans`: Page object / queryset of `AssetBusinessContinuityPlan` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `redundancy_choices`: `AssetBusinessContinuityPlan.REDUNDANCY_TYPE_CHOICES`
  - `scenario_choices`: `AssetBusinessContinuityPlan.DISASTER_SCENARIO_CHOICES`
  - `status_choices`: `AssetBusinessContinuityPlan.STATUS_CHOICES`
  - `total_plans`: Integer total count
  - `active_plans_count`: Integer count where `status='active'`
  - `spof_count`: Integer count where `redundancy_type='none_single_point_of_failure'`
  - `avg_rto_hours`: Float average RTO hours
- **Detail View (`asset_business_continuity_plan_detail`):**
  - `plan`: Subject `AssetBusinessContinuityPlan` instance
- **Form Views (Create/Edit):**
  - `form`: `AssetBusinessContinuityPlanForm`
  - `plan`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.3 `AssetCyberSecurityProfile`
- **List View (`asset_cybersecurity_profile_list`):**
  - `profiles`: Page object / queryset of `AssetCyberSecurityProfile` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `device_choices`: `AssetCyberSecurityProfile.DEVICE_TYPE_CHOICES`
  - `zone_choices`: `AssetCyberSecurityProfile.NETWORK_ZONE_CHOICES`
  - `posture_choices`: `AssetCyberSecurityProfile.POSTURE_STATUS_CHOICES`
  - `firmware_choices`: `AssetCyberSecurityProfile.FIRMWARE_STATUS_CHOICES`
  - `total_profiles`: Integer total count
  - `secure_count`: Integer count where `security_posture_status='secure'`
  - `vulnerable_count`: Integer count where `security_posture_status in ['vulnerable', 'compromised']`
  - `critical_patches_count`: Integer count where `firmware_update_status='critical_patch_pending'`
- **Detail View (`asset_cybersecurity_profile_detail`):**
  - `profile`: Subject `AssetCyberSecurityProfile` instance
- **Form Views (Create/Edit):**
  - `form`: `AssetCyberSecurityProfileForm`
  - `profile`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

### 4.4 `AssetRiskMitigationAction`
- **List View (`asset_risk_mitigation_action_list`):**
  - `actions`: Page object / queryset of `AssetRiskMitigationAction` records
  - `page_obj`: Django Paginator Page
  - `paginator`: Paginator instance
  - `is_paginated`: Boolean flag
  - `type_choices`: `AssetRiskMitigationAction.ACTION_TYPE_CHOICES`
  - `priority_choices`: `AssetRiskMitigationAction.PRIORITY_CHOICES`
  - `status_choices`: `AssetRiskMitigationAction.STATUS_CHOICES`
  - `effectiveness_choices`: `AssetRiskMitigationAction.EFFECTIVENESS_CHOICES`
  - `total_actions`: Integer total count
  - `in_progress_count`: Integer count where `status='in_progress'`
  - `verified_count`: Integer count where `status='verified_effective'`
  - `total_estimated_cost`: Decimal sum of `estimated_cost`
  - `total_actual_cost`: Decimal sum of `actual_cost`
- **Detail View (`asset_risk_mitigation_action_detail`):**
  - `action`: Subject `AssetRiskMitigationAction` instance
- **Form Views (Create/Edit):**
  - `form`: `AssetRiskMitigationActionForm`
  - `action`: Subject instance (or `None` in create)
  - `is_edit`: Boolean

---

## 5. Navigation & Sidebar Wiring

Mapping to exact NavERP.md feature bullets for `LIVE_LINKS["11.12"]` in `apps/core/navigation.py`:
- `"Risk Identification & Assessment"` -> `"assets:asset_risk_register_list"`
- `"Business Continuity Planning"` -> `"assets:asset_business_continuity_plan_list"`
- `"Cybersecurity for Connected Assets"` -> `"assets:asset_cybersecurity_profile_list"`
- `"Geopolitical & Supply Chain Risk"` -> `"assets:asset_risk_mitigation_action_list"`
- `"Risk Mitigation & Contingency"` -> `"assets:asset_risk_mitigation_action_list"`

---

## 6. Seed Data Specifications (Idempotent)

`apps/assets/management/commands/seed_assets.py` will be extended with:
- `seed_asset_risk_management(tenant, assets_dict, categories_dict, users_dict, parties_dict)`
- ACME Tenant:
  - 4 `AssetRiskRegister` rows (`ARK-`):
    - Critical: Main Turbine Bearing Catastrophic Failure Risk (Operational, Likelihood 4, Impact 5 -> Inherent Score 20, Critical; Residual Likelihood 2, Impact 3 -> Score 6, Medium, Treating, $450,000 exposure)
    - High: SCADA Network Ransomware Exposure (Cybersecurity, Likelihood 3, Impact 4 -> Inherent Score 12, High; Residual Likelihood 1, Impact 4 -> Score 4, Low, Treating, $250,000 exposure)
    - High: Sole-Source German Precision Bearing Disruption (Geopolitical/Supply Chain, Likelihood 3, Impact 4 -> Inherent Score 12, High; Residual Likelihood 2, Impact 3 -> Score 6, Medium, Assessed, $180,000 exposure)
    - Medium: Hydraulic Press Seal Fluid Leakage Hazard (Environmental/Safety, Likelihood 2, Impact 3 -> Inherent Score 6, Medium; Residual Likelihood 1, Impact 2 -> Score 2, Low, Monitored, $35,000 exposure)
  - 3 `AssetBusinessContinuityPlan` rows (`ABC-`):
    - Active Hot-Standby: Primary Power Generator BCP (Hot Standby, RTO 0.5h, RPO 0.1h, MTD 8.0h, Drill Result: Passed)
    - Active Warm-Standby: CNC Milling Cell Redundancy Plan (Warm Standby, RTO 2.0h, RPO 1.0h, MTD 24.0h, Drill Result: Passed with Deficiencies)
    - Draft SPOF: Main Boiler BCP (Single Point of Failure, RTO 48.0h, RPO 12.0h, MTD 72.0h, Drill Result: Not Tested)
  - 3 `AssetCyberSecurityProfile` rows (`ACS-`):
    - Secure: Line 1 Siemens S7-1500 PLC Controller (Control PLC Level 2, Modbus/Profinet, Firmware 2.9.4 Up-to-date, Isolated VLAN, Secure Posture)
    - Vulnerable: Central SCADA Supervisory Server (Supervisory SCADA Level 3, OPC UA, Firmware 4.2.1 Update Available, CVE-2026-1192 CVSS 7.8, Attention Required Posture)
    - Critical Patch: Edge IoT Vibration Sensor Hub (Process I/O Level 1, MQTT, Firmware 1.0.8 Critical Patch Pending, CVE-2026-3044 CVSS 9.1, Vulnerable Posture)
  - 4 `AssetRiskMitigationAction` rows (`ARMA-`):
    - Redundancy Addition: Install Automated Transfer Switch for Generator (Completed, $12,500)
    - Supplier Diversification: Qualify Secondary Domestic Bearing Supplier (In Progress, $8,000)
    - Firmware Patch: Deploy Hardened Firmware for Siemens PLC (Verified Effective, Highly Effective, $3,500)
    - Engineering Control: Implement Secondary Containment Berm for Press (Planned, $15,000)
- Globex Tenant:
  - Scaled parallel demo dataset ensuring multi-tenant isolation and 404 verification.

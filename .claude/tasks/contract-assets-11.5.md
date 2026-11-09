# Contract — Sub-module 11.5: Maintenance & Repair Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.5 Maintenance & Repair Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-09 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0008_...`.
- **Package Layout:** `AssetMaintenance/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_maintenance/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetMaintenanceRequest` (`apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py`)
- **Table:** `assets_maintenance_request`
- **Number Prefix:** `AMRQ` (format: `AMRQ-YYYYMM-XXXX`)
- **CHOICES:**
  - `REQUEST_TYPE_CHOICES = [('breakdown_repair', 'Breakdown Repair'), ('preventive_inspection', 'Preventive Inspection'), ('safety_hazard', 'Safety / Environmental Hazard'), ('calibration', 'Calibration / Alignment'), ('facility_upkeep', 'Facility Upkeep')]`
  - `URGENCY_CHOICES = [('low', 'Low (Non-urgent)'), ('medium', 'Medium (Standard)'), ('high', 'High (Production Impact)'), ('critical', 'Critical (Total Shutdown / Safety)')]`
  - `STATUS_CHOICES = [('submitted', 'Submitted'), ('triaged', 'Triaged / Accepted'), ('assigned', 'Assigned / Dispatched'), ('in_progress', 'Work in Progress'), ('resolved', 'Resolved / Repaired'), ('rejected', 'Rejected'), ('closed', 'Closed / Verified')]`
  - `STATUS_CSS = {'submitted': 'badge-info', 'triaged': 'badge-slate', 'assigned': 'badge-amber', 'in_progress': 'badge-amber', 'resolved': 'badge-green', 'rejected': 'badge-red', 'closed': 'badge-muted'}`
  - `URGENCY_CSS = {'critical': 'badge-red', 'high': 'badge-amber', 'medium': 'badge-info', 'low': 'badge-slate'}`
  - `REQUEST_TYPE_CSS = {'breakdown_repair': 'badge-red', 'preventive_inspection': 'badge-info', 'safety_hazard': 'badge-amber', 'calibration': 'badge-slate', 'facility_upkeep': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_maintenance_requests')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=255, help_text='Brief title / symptom summary of the issue')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_requests', help_text='Financial Fixed Asset in accounting register')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_requests', help_text='Operational equipment record')`
  - `requester`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='submitted_asset_maintenance_requests')`
  - `department`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_maintenance_requests', help_text='Requesting department or location cost center')`
  - `request_type`: `CharField(max_length=32, choices=REQUEST_TYPE_CHOICES, default='breakdown_repair')`
  - `urgency`: `CharField(max_length=20, choices=URGENCY_CHOICES, default='medium')`
  - `is_breakdown`: `BooleanField(default=False, help_text='Flags equipment complete stoppage / production line down')`
  - `downtime_started_at`: `DateTimeField(null=True, blank=True, help_text='Timestamp when equipment stopped operating')`
  - `symptom_description`: `TextField(help_text='Detailed description of malfunction, noises, visual leaks, or alarms')`
  - `triage_notes`: `TextField(blank=True, help_text='Maintenance supervisor assessment and prioritization notes')`
  - `assigned_technician`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='assigned_asset_maintenance_requests')`
  - `assigned_vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='assigned_asset_maintenance_requests', help_text='External contractor / OEM service provider')`
  - `service_contract`: `ForeignKey('assets.AssetServiceContract', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_requests', help_text='Applicable service contract / AMC')`
  - `dispatched_work_order`: `ForeignKey('scm.MaintenanceWorkOrder', on_delete=SET_NULL, null=True, blank=True, related_name='asset_maintenance_requests', help_text='Linked shopfloor maintenance work order')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')`
  - `resolution_summary`: `TextField(blank=True, help_text='Summary of corrective action taken and parts replaced')`
  - `resolved_at`: `DateTimeField(null=True, blank=True)`
  - `resolved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='resolved_asset_maintenance_requests')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_amrq_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_amrq_ten_stat')`
  - `Index(fields=['tenant', 'urgency'], name='idx_amrq_ten_urg')`
  - `Index(fields=['tenant', 'is_breakdown'], name='idx_amrq_ten_bkdn')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_amrq_ten_fa')`
- **Actions / State Machine:**
  - `asset_maintenance_request_triage`: supervisor updates urgency and triage_notes, transitions `submitted -> triaged`.
  - `asset_maintenance_request_dispatch`: assigns technician or vendor, transitions `triaged -> assigned`.
  - `asset_maintenance_request_start`: begins repair, transitions `assigned -> in_progress`.
  - `asset_maintenance_request_resolve`: records resolution summary, sets `resolved_at` and `resolved_by`, transitions `in_progress/assigned -> resolved`.
  - `asset_maintenance_request_close`: supervisor accepts resolution, transitions `resolved -> closed`.
  - `asset_maintenance_request_reject`: rejects ticket with reason, transitions `submitted/triaged -> rejected`.
- **Form exclusions:** `tenant`, `number`, `status`, `triage_notes`, `assigned_technician`, `assigned_vendor`, `service_contract`, `dispatched_work_order`, `resolution_summary`, `resolved_at`, `resolved_by`, `created_at`, `updated_at`.

---

### 1.2 `AssetMaintenanceSchedule` (`apps/assets/models/AssetMaintenance/AssetMaintenanceSchedules.py`)
- **Table:** `assets_maintenance_schedule`
- **Number Prefix:** `AMSC` (format: `AMSC-YYYYMM-XXXX`)
- **CHOICES:**
  - `SCHEDULE_TYPE_CHOICES = [('time_based', 'Time-Based (Calendar Recurring)'), ('meter_based', 'Meter / Runtime Hours Based'), ('condition_based', 'Condition / Anomaly Triggered'), ('seasonal_shutdown', 'Seasonal / Annual Turnaround')]`
  - `FREQUENCY_UNIT_CHOICES = [('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years'), ('runtime_hours', 'Runtime Hours'), ('cycles_count', 'Operating Cycles')]`
  - `STATUS_CHOICES = [('active', 'Active'), ('overdue', 'Overdue for Service'), ('paused', 'Paused / Standby'), ('completed', 'Completed'), ('retired', 'Retired')]`
  - `STATUS_CSS = {'active': 'badge-green', 'overdue': 'badge-red', 'paused': 'badge-amber', 'completed': 'badge-info', 'retired': 'badge-muted'}`
  - `SCHEDULE_TYPE_CSS = {'time_based': 'badge-info', 'meter_based': 'badge-purple', 'condition_based': 'badge-amber', 'seasonal_shutdown': 'badge-slate'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_maintenance_schedules')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `name`: `CharField(max_length=255, help_text='Preventive maintenance plan title (e.g. Monthly Hydraulic Filter Check)')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `asset_category`: `ForeignKey('assets.AssetCategory', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `schedule_type`: `CharField(max_length=32, choices=SCHEDULE_TYPE_CHOICES, default='time_based')`
  - `frequency_interval`: `PositiveIntegerField(default=30, help_text='Recurrence interval count (e.g. 30 for 30 days, 250 for 250 hours)')`
  - `frequency_unit`: `CharField(max_length=20, choices=FREQUENCY_UNIT_CHOICES, default='days')`
  - `meter_trigger_threshold`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text='Meter threshold delta for runtime trigger')`
  - `lead_time_days`: `PositiveIntegerField(default=7, help_text='Advance notice warning days before service due')`
  - `last_service_date`: `DateField(null=True, blank=True)`
  - `last_service_meter`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)`
  - `next_due_date`: `DateField(null=True, blank=True)`
  - `next_due_meter`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)`
  - `assigned_technician`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `preferred_vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `service_contract`: `ForeignKey('assets.AssetServiceContract', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_schedules')`
  - `service_checklist`: `TextField(blank=True, help_text='Standard operating procedure / safety checklist tasks (one per line)')`
  - `is_mandatory`: `BooleanField(default=True, help_text='Mandatory compliance/statutory requirement')`
  - `is_active`: `BooleanField(default=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='active')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_amsc_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_amsc_ten_stat')`
  - `Index(fields=['tenant', 'next_due_date'], name='idx_amsc_ten_due')`
  - `Index(fields=['tenant', 'schedule_type'], name='idx_amsc_ten_type')`
  - `Index(fields=['tenant', 'is_active'], name='idx_amsc_ten_act')`
- **Actions / State Machine:**
  - `asset_maintenance_schedule_activate`: sets `is_active=True`, status `active`.
  - `asset_maintenance_schedule_pause`: sets `is_active=False`, status `paused`.
  - `asset_maintenance_schedule_generate_request`: creates linked `AssetMaintenanceRequest` for upcoming schedule window.
  - `asset_maintenance_schedule_record_completion`: accepts completion date/meter, recalculates `next_due_date` and `next_due_meter`.
- **Form exclusions:** `tenant`, `number`, `status`, `last_service_date`, `last_service_meter`, `next_due_date`, `next_due_meter`, `created_at`, `updated_at`.

---

### 1.3 `AssetServiceContract` (`apps/assets/models/AssetMaintenance/AssetServiceContracts.py`)
- **Table:** `assets_service_contract`
- **Number Prefix:** `ASVC` (format: `ASVC-YYYYMM-XXXX`)
- **CHOICES:**
  - `CONTRACT_TYPE_CHOICES = [('comprehensive_amc', 'Comprehensive Annual Maintenance (Parts & Labor)'), ('labor_only', 'Labor-Only Maintenance Agreement'), ('parts_and_labor', 'Standard Parts & Labor Agreement'), ('on_call_support', 'On-Call Emergency Support Agreement'), ('oem_warranty_extension', 'OEM Extended Warranty Contract')]`
  - `BILLING_FREQUENCY_CHOICES = [('monthly', 'Monthly Retainer'), ('quarterly', 'Quarterly In Advance'), ('semi_annual', 'Semi-Annual'), ('annual', 'Annual Lump Sum'), ('per_visit', 'Per-Visit Invoiced')]`
  - `STATUS_CHOICES = [('draft', 'Draft Agreement'), ('active', 'Active Contract'), ('expiring_soon', 'Expiring Within 30 Days'), ('expired', 'Contract Expired'), ('terminated', 'Terminated Early')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'active': 'badge-green', 'expiring_soon': 'badge-amber', 'expired': 'badge-red', 'terminated': 'badge-muted'}`
  - `CONTRACT_TYPE_CSS = {'comprehensive_amc': 'badge-green', 'labor_only': 'badge-info', 'parts_and_labor': 'badge-blue', 'on_call_support': 'badge-amber', 'oem_warranty_extension': 'badge-purple'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_service_contracts')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `contract_number`: `CharField(max_length=100, help_text='External vendor contract or SLA agreement number')`
  - `title`: `CharField(max_length=255, help_text='Agreement title / scope description')`
  - `vendor`: `ForeignKey('core.Party', on_delete=PROTECT, related_name='asset_service_contracts', help_text='Service provider / vendor Party')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='service_contracts')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='service_contracts')`
  - `contract_type`: `CharField(max_length=32, choices=CONTRACT_TYPE_CHOICES, default='comprehensive_amc')`
  - `start_date`: `DateField(help_text='Effective start date of contract coverage')`
  - `end_date`: `DateField(help_text='Contract expiration date')`
  - `contract_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), help_text='Total contractual value')`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_service_contracts')`
  - `billing_frequency`: `CharField(max_length=20, choices=BILLING_FREQUENCY_CHOICES, default='annual')`
  - `sla_response_hours`: `PositiveIntegerField(default=4, help_text='Target first response / arrival SLA in hours')`
  - `sla_resolution_hours`: `PositiveIntegerField(default=24, help_text='Target full fault resolution SLA in hours')`
  - `pm_visits_included`: `PositiveIntegerField(default=4, help_text='Routine preventive maintenance visits included in agreement')`
  - `pm_visits_completed`: `PositiveIntegerField(default=0, help_text='Actual visits logged against quota')`
  - `coverage_terms`: `TextField(blank=True, help_text='Specific inclusion/exclusion clauses, parts warranty coverage, and emergency rates')`
  - `auto_renew`: `BooleanField(default=False, help_text='Contract automatically rolls over unless cancelled')`
  - `contact_person`: `CharField(max_length=150, blank=True, help_text='Vendor primary account manager / technical rep')`
  - `contact_phone`: `CharField(max_length=50, blank=True)`
  - `contact_email`: `EmailField(blank=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_asvc_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_asvc_ten_stat')`
  - `Index(fields=['tenant', 'vendor'], name='idx_asvc_ten_vend')`
  - `Index(fields=['tenant', 'end_date'], name='idx_asvc_ten_end')`
  - `Index(fields=['tenant', 'contract_type'], name='idx_asvc_ten_type')`
- **Actions / State Machine:**
  - `asset_service_contract_activate`: transitions `draft -> active`.
  - `asset_service_contract_record_visit`: increments `pm_visits_completed`.
  - `asset_service_contract_renew`: extends `end_date` by contract period, resets visit counter, transitions to `active`.
  - `asset_service_contract_terminate`: terminates agreement early with notes, transitions to `terminated`.
- **Form exclusions:** `tenant`, `number`, `status`, `pm_visits_completed`, `created_at`, `updated_at`.

---

### 1.4 `AssetMaintenanceLog` (`apps/assets/models/AssetMaintenance/AssetMaintenanceLogs.py`)
- **Table:** `assets_maintenance_log`
- **Number Prefix:** `AMLG` (format: `AMLG-YYYYMM-XXXX`)
- **CHOICES:**
  - `MAINTENANCE_TYPE_CHOICES = [('corrective_repair', 'Corrective Repair / Breakdown Fix'), ('preventive_service', 'Scheduled Preventive Service'), ('emergency_breakdown', 'Emergency Breakdown Response'), ('calibration', 'Precision Calibration / Alignment'), ('inspection', 'Safety & Statutory Inspection'), ('overhaul', 'Major Overhaul / Component Rebuild')]`
  - `FAILURE_CODE_CHOICES = [('mechanical_wear', 'Mechanical Wear / Fatigue'), ('electrical_short', 'Electrical Short / Fault'), ('hydraulic_leak', 'Hydraulic / Pneumatic Leak'), ('software_fault', 'Software / Sensor Glitch'), ('operator_error', 'Operator Error / Mishandling'), ('corrosion', 'Corrosion / Chemical Damage'), ('thermal_overload', 'Thermal Overload / Overheating'), ('lubrication_failure', 'Lubrication / Fluid Starvation'), ('normal_wear', 'Normal Operational Wear'), ('other', 'Other / Unclassified')]`
  - `STATUS_CHOICES = [('draft', 'Draft Service Log'), ('in_review', 'Under Supervisory Review'), ('approved', 'Approved / Verified'), ('posted', 'Posted to General Ledger')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'in_review': 'badge-amber', 'approved': 'badge-info', 'posted': 'badge-green'}`
  - `MAINTENANCE_TYPE_CSS = {'corrective_repair': 'badge-amber', 'preventive_service': 'badge-info', 'emergency_breakdown': 'badge-red', 'calibration': 'badge-slate', 'inspection': 'badge-green', 'overhaul': 'badge-purple'}`
  - `FAILURE_CODE_CSS = {'mechanical_wear': 'badge-amber', 'electrical_short': 'badge-red', 'hydraulic_leak': 'badge-blue', 'software_fault': 'badge-slate', 'operator_error': 'badge-muted', 'corrosion': 'badge-amber', 'thermal_overload': 'badge-red', 'lubrication_failure': 'badge-amber', 'normal_wear': 'badge-slate', 'other': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_maintenance_logs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `maintenance_schedule`: `ForeignKey('assets.AssetMaintenanceSchedule', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `service_contract`: `ForeignKey('assets.AssetServiceContract', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `work_order`: `ForeignKey('scm.MaintenanceWorkOrder', on_delete=SET_NULL, null=True, blank=True, related_name='asset_maintenance_logs')`
  - `service_date`: `DateField(default=timezone.now, help_text='Date maintenance work was executed')`
  - `completion_date`: `DateTimeField(null=True, blank=True, help_text='Timestamp work was finalized and signed off')`
  - `maintenance_type`: `CharField(max_length=32, choices=MAINTENANCE_TYPE_CHOICES, default='corrective_repair')`
  - `failure_code`: `CharField(max_length=32, choices=FAILURE_CODE_CHOICES, default='normal_wear')`
  - `downtime_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Actual equipment downtime hours caused by failure')`
  - `meter_reading`: `DecimalField(max_digits=16, decimal_places=2, null=True, blank=True, help_text='Asset meter / runtime counter at time of service')`
  - `lead_technician`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs')`
  - `service_vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='maintenance_logs', help_text='External service contractor')`
  - `labor_hours`: `DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), help_text='Total technician wrench hours spent')`
  - `labor_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `parts_consumed_summary`: `TextField(blank=True, help_text='Itemized spare parts, quantities, part numbers used (e.g. 2x Filter #FL-90, 5L Oil 15W-40)')`
  - `parts_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `vendor_invoice_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `total_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'), editable=False, help_text='Auto-computed total repair cost (labor + parts + vendor)')`
  - `expense_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_maintenance_expenses', help_text='Debit: Repair & Maintenance Expense GL Account')`
  - `root_cause_analysis`: `TextField(blank=True, help_text='FMEA / 5-Why root cause explanation')`
  - `action_taken`: `TextField(help_text='Technical narrative of corrective steps, adjustments, and test runs')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='draft')`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_asset_maintenance_logs')`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_amlg_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_amlg_ten_stat')`
  - `Index(fields=['tenant', 'service_date'], name='idx_amlg_ten_date')`
  - `Index(fields=['tenant', 'maintenance_type'], name='idx_amlg_ten_type')`
  - `Index(fields=['tenant', 'failure_code'], name='idx_amlg_ten_fail')`
  - `Index(fields=['tenant', 'fixed_asset'], name='idx_amlg_ten_fa')`
- **Actions / State Machine:**
  - `asset_maintenance_log_submit_review`: transitions `draft -> in_review`.
  - `asset_maintenance_log_approve`: sets `approved_by` and `approved_at`, transitions `in_review -> approved`.
  - `asset_maintenance_log_post_gl`: creates balanced `accounting.JournalEntry` (Dr Expense / Cr Payable/Cash), marks status `posted`, updates schedule if linked.
- **Form exclusions:** `tenant`, `number`, `status`, `total_cost`, `approved_by`, `approved_at`, `created_at`, `updated_at`.

---

## 2. Forms Contract

Located at `apps/assets/forms/AssetMaintenance/`:
1. `AssetMaintenanceRequests.py`:
   - `AssetMaintenanceRequestForm(forms.ModelForm)`:
     - `Meta.model = AssetMaintenanceRequest`
     - `Meta.fields`: `['title', 'fixed_asset', 'operational_asset', 'requester', 'department', 'request_type', 'urgency', 'is_breakdown', 'downtime_started_at', 'symptom_description']`
   - `AssetMaintenanceRequestTriageForm(forms.Form)`:
     - `urgency`, `triage_notes`
   - `AssetMaintenanceRequestDispatchForm(forms.Form)`:
     - `assigned_technician`, `assigned_vendor`, `service_contract`, `dispatched_work_order`
   - `AssetMaintenanceRequestResolveForm(forms.Form)`:
     - `resolution_summary`
2. `AssetMaintenanceSchedules.py`:
   - `AssetMaintenanceScheduleForm(forms.ModelForm)`:
     - `Meta.model = AssetMaintenanceSchedule`
     - `Meta.fields`: `['name', 'fixed_asset', 'operational_asset', 'asset_category', 'schedule_type', 'frequency_interval', 'frequency_unit', 'meter_trigger_threshold', 'lead_time_days', 'assigned_technician', 'preferred_vendor', 'service_contract', 'service_checklist', 'is_mandatory', 'is_active', 'notes']`
   - `AssetMaintenanceScheduleCompletionForm(forms.Form)`:
     - `completion_date`, `completion_meter`, `notes`
3. `AssetServiceContracts.py`:
   - `AssetServiceContractForm(forms.ModelForm)`:
     - `Meta.model = AssetServiceContract`
     - `Meta.fields`: `['contract_number', 'title', 'vendor', 'fixed_asset', 'operational_asset', 'contract_type', 'start_date', 'end_date', 'contract_value', 'currency', 'billing_frequency', 'sla_response_hours', 'sla_resolution_hours', 'pm_visits_included', 'coverage_terms', 'auto_renew', 'contact_person', 'contact_phone', 'contact_email', 'notes']`
   - `AssetServiceContractRenewForm(forms.Form)`:
     - `new_end_date`, `new_contract_value`, `notes`
4. `AssetMaintenanceLogs.py`:
   - `AssetMaintenanceLogForm(forms.ModelForm)`:
     - `Meta.model = AssetMaintenanceLog`
     - `Meta.fields`: `['fixed_asset', 'operational_asset', 'maintenance_request', 'maintenance_schedule', 'service_contract', 'work_order', 'service_date', 'completion_date', 'maintenance_type', 'failure_code', 'downtime_hours', 'meter_reading', 'lead_technician', 'service_vendor', 'labor_hours', 'labor_cost', 'parts_consumed_summary', 'parts_cost', 'vendor_invoice_cost', 'expense_account', 'root_cause_analysis', 'action_taken']`

---

## 3. URLs Contract

All routes under `apps/assets/urls/AssetMaintenance/` wired into `apps/assets/urls/__init__.py`:

### 3.1 `AssetMaintenanceRequests.py`
- `asset_maintenance_request_list` -> `requests/`
- `asset_maintenance_request_create` -> `requests/create/`
- `asset_maintenance_request_detail` -> `requests/<int:pk>/`
- `asset_maintenance_request_edit` -> `requests/<int:pk>/edit/`
- `asset_maintenance_request_delete` -> `requests/<int:pk>/delete/`
- `asset_maintenance_request_triage` -> `requests/<int:pk>/triage/`
- `asset_maintenance_request_dispatch` -> `requests/<int:pk>/dispatch/`
- `asset_maintenance_request_start` -> `requests/<int:pk>/start/`
- `asset_maintenance_request_resolve` -> `requests/<int:pk>/resolve/`
- `asset_maintenance_request_close` -> `requests/<int:pk>/close/`
- `asset_maintenance_request_reject` -> `requests/<int:pk>/reject/`

### 3.2 `AssetMaintenanceSchedules.py`
- `asset_maintenance_schedule_list` -> `schedules/`
- `asset_maintenance_schedule_create` -> `schedules/create/`
- `asset_maintenance_schedule_detail` -> `schedules/<int:pk>/`
- `asset_maintenance_schedule_edit` -> `schedules/<int:pk>/edit/`
- `asset_maintenance_schedule_delete` -> `schedules/<int:pk>/delete/`
- `asset_maintenance_schedule_activate` -> `schedules/<int:pk>/activate/`
- `asset_maintenance_schedule_pause` -> `schedules/<int:pk>/pause/`
- `asset_maintenance_schedule_generate_request` -> `schedules/<int:pk>/generate-request/`
- `asset_maintenance_schedule_record_completion` -> `schedules/<int:pk>/record-completion/`

### 3.3 `AssetServiceContracts.py`
- `asset_service_contract_list` -> `service-contracts/`
- `asset_service_contract_create` -> `service-contracts/create/`
- `asset_service_contract_detail` -> `service-contracts/<int:pk>/`
- `asset_service_contract_edit` -> `service-contracts/<int:pk>/edit/`
- `asset_service_contract_delete` -> `service-contracts/<int:pk>/delete/`
- `asset_service_contract_activate` -> `service-contracts/<int:pk>/activate/`
- `asset_service_contract_record_visit` -> `service-contracts/<int:pk>/record-visit/`
- `asset_service_contract_renew` -> `service-contracts/<int:pk>/renew/`
- `asset_service_contract_terminate` -> `service-contracts/<int:pk>/terminate/`

### 3.4 `AssetMaintenanceLogs.py`
- `asset_maintenance_log_list` -> `logs/`
- `asset_maintenance_log_create` -> `logs/create/`
- `asset_maintenance_log_detail` -> `logs/<int:pk>/`
- `asset_maintenance_log_edit` -> `logs/<int:pk>/edit/`
- `asset_maintenance_log_delete` -> `logs/<int:pk>/delete/`
- `asset_maintenance_log_submit_review` -> `logs/<int:pk>/submit-review/`
- `asset_maintenance_log_approve` -> `logs/<int:pk>/approve/`
- `asset_maintenance_log_post_gl` -> `logs/<int:pk>/post-gl/`

---

## 4. View Context Keys Contract (Mandatory Pinned Names)

### 4.1 `AssetMaintenanceRequest` Views
- `list.html`:
  - `maintenance_requests`: paginated queryset
  - `page_obj`, `paginator`, `is_paginated`: standard pagination
  - `status_choices`: `AssetMaintenanceRequest.STATUS_CHOICES`
  - `urgency_choices`: `AssetMaintenanceRequest.URGENCY_CHOICES`
  - `request_type_choices`: `AssetMaintenanceRequest.REQUEST_TYPE_CHOICES`
  - `total_requests`: total count
  - `breakdown_count`: count where `is_breakdown=True`
  - `critical_count`: count where `urgency='critical'`
  - `open_count`: count where `status` in `('submitted', 'triaged', 'assigned', 'in_progress')`
- `detail.html`:
  - `maintenance_request`: the `AssetMaintenanceRequest` instance
  - `linked_logs`: queryset of `AssetMaintenanceLog` for this request
  - `status_choices`: `AssetMaintenanceRequest.STATUS_CHOICES`
- `form.html`:
  - `form`: form instance
  - `maintenance_request`: instance if edit mode else `None`
  - `is_edit`: boolean

### 4.2 `AssetMaintenanceSchedule` Views
- `list.html`:
  - `maintenance_schedules`: paginated queryset
  - `page_obj`, `paginator`, `is_paginated`: standard pagination
  - `status_choices`: `AssetMaintenanceSchedule.STATUS_CHOICES`
  - `schedule_type_choices`: `AssetMaintenanceSchedule.SCHEDULE_TYPE_CHOICES`
  - `frequency_unit_choices`: `AssetMaintenanceSchedule.FREQUENCY_UNIT_CHOICES`
  - `total_schedules`: total count
  - `active_count`: count where `status='active'`
  - `overdue_count`: count where `status='overdue'` or `(next_due_date < today and is_active=True)`
  - `paused_count`: count where `status='paused'`
- `detail.html`:
  - `maintenance_schedule`: instance
  - `service_checklist_items`: checklist split lines
  - `linked_logs`: linked `AssetMaintenanceLog` queryset
  - `linked_requests`: linked `AssetMaintenanceRequest` queryset
- `form.html`:
  - `form`: form instance
  - `maintenance_schedule`: instance if edit mode else `None`
  - `is_edit`: boolean

### 4.3 `AssetServiceContract` Views
- `list.html`:
  - `service_contracts`: paginated queryset
  - `page_obj`, `paginator`, `is_paginated`: standard pagination
  - `status_choices`: `AssetServiceContract.STATUS_CHOICES`
  - `contract_type_choices`: `AssetServiceContract.CONTRACT_TYPE_CHOICES`
  - `billing_frequency_choices`: `AssetServiceContract.BILLING_FREQUENCY_CHOICES`
  - `total_contracts`: total count
  - `active_count`: count where `status='active'`
  - `expiring_soon_count`: count where `status='expiring_soon'`
  - `total_contract_value`: sum of `contract_value` for active contracts
- `detail.html`:
  - `service_contract`: instance
  - `linked_requests`: linked `AssetMaintenanceRequest` queryset
  - `linked_logs`: linked `AssetMaintenanceLog` queryset
- `form.html`:
  - `form`: form instance
  - `service_contract`: instance if edit mode else `None`
  - `is_edit`: boolean

### 4.4 `AssetMaintenanceLog` Views
- `list.html`:
  - `maintenance_logs`: paginated queryset
  - `page_obj`, `paginator`, `is_paginated`: standard pagination
  - `status_choices`: `AssetMaintenanceLog.STATUS_CHOICES`
  - `maintenance_type_choices`: `AssetMaintenanceLog.MAINTENANCE_TYPE_CHOICES`
  - `failure_code_choices`: `AssetMaintenanceLog.FAILURE_CODE_CHOICES`
  - `total_logs`: total count
  - `posted_count`: count where `status='posted'`
  - `total_downtime_hours`: sum of `downtime_hours`
  - `total_maintenance_cost`: sum of `total_cost`
- `detail.html`:
  - `maintenance_log`: instance
- `form.html`:
  - `form`: form instance
  - `maintenance_log`: instance if edit mode else `None`
  - `is_edit`: boolean

---

## 5. Templates Path Hierarchy

All templates live under:
- `templates/assets/asset_maintenance/asset_maintenance_request/{list,detail,form}.html`
- `templates/assets/asset_maintenance/asset_maintenance_schedule/{list,detail,form}.html`
- `templates/assets/asset_maintenance/asset_service_contract/{list,detail,form}.html`
- `templates/assets/asset_maintenance/asset_maintenance_log/{list,detail,form}.html`

---

## 6. Audit & Navigation Wiring

- Every mutation calls `write_audit_log(request.user, instance, "create"|"update"|"delete", tenant=request.tenant)` (L66).
- `apps/core/navigation.py`:
  ```python
  LIVE_LINKS["11.5"] = {
      "Preventive Maintenance (PM) Scheduling": "assets:asset_maintenance_schedule_list",
      "Work Order Creation & Dispatch": "assets:asset_maintenance_request_list",
      "Spare Parts & Inventory Control": "assets:asset_maintenance_log_list",
      "Maintenance History & Logs": "assets:asset_maintenance_log_list",
      "Vendor & Contract Maintenance": "assets:asset_service_contract_list",
      # Aliases
      "Maintenance Requests": "assets:asset_maintenance_request_list",
      "PM Schedules": "assets:asset_maintenance_schedule_list",
      "Service Contracts": "assets:asset_service_contract_list",
      "Maintenance Logs": "assets:asset_maintenance_log_list",
  }
  ```

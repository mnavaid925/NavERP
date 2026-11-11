# Contract — Sub-module 11.13: Mobile Asset Management (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.13 Mobile Asset Management • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-11 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0015_...`.
- **Package Layout:** `MobileAssetManagement/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/mobileassetmanagement/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `MobileAssetInspection` (`apps/assets/models/MobileAssetManagement/MobileAssetInspections.py`)
- **Table:** `assets_mobileassetinspection`
- **Number Prefix:** `MINS` (format: `MINS-YYYYMM-XXXX`)
- **CHOICES:**
  - `INSPECTION_TYPE_CHOICES = [('safety_audit', 'Safety & Statutory Walkaround'), ('pre_trip', 'Pre-Trip / Pre-Shift Checklist'), ('condition_assessment', 'Condition & Wear Assessment'), ('routine_pm', 'Routine PM Inspection'), ('breakdown_triage', 'Emergency Breakdown Triage')]`
  - `OVERALL_RESULT_CHOICES = [('pass', 'Pass (Satisfactory)'), ('conditional_pass', 'Conditional Pass (Action Item Open)'), ('fail', 'Fail (Needs Repair)'), ('critical_hazard', 'Critical Hazard / Out of Service')]`
  - `STATUS_CHOICES = [('draft', 'Draft (Incomplete)'), ('submitted', 'Submitted from Field'), ('under_review', 'Under Supervisory Review'), ('approved', 'Approved & Closed'), ('rejected', 'Rejected (Re-inspection Required)')]`
  - `CONDITION_RATING_CHOICES = [(5, '5 - Excellent (Like New)'), (4, '4 - Good (Normal Operational)'), (3, '3 - Fair (Minor Wear / Servicing Due)'), (2, '2 - Poor (Degraded / Urgent Repair)'), (1, '1 - Critical / Scrap Hazard')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'submitted': 'badge-info', 'under_review': 'badge-amber', 'approved': 'badge-green', 'rejected': 'badge-red'}`
  - `OVERALL_RESULT_CSS = {'pass': 'badge-green', 'conditional_pass': 'badge-amber', 'fail': 'badge-red', 'critical_hazard': 'badge-red'}`
  - `INSPECTION_TYPE_CSS = {'safety_audit': 'badge-amber', 'pre_trip': 'badge-info', 'condition_assessment': 'badge-slate', 'routine_pm': 'badge-green', 'breakdown_triage': 'badge-red'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='mobile_inspections')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200, help_text='Short descriptive title of the mobile inspection')`
  - `inspection_type`: `CharField(max_length=32, choices=INSPECTION_TYPE_CHOICES, default='routine_pm')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='mobile_inspections', help_text='Subject operational asset inspected')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='mobile_inspections', help_text='Financial asset record (if linked)')`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name='mobile_inspections', help_text='Field technician / inspector who completed the audit')`
  - `inspection_date`: `DateTimeField(default=timezone.now, help_text='Timestamp when inspection was completed')`
  - `scheduled_date`: `DateField(null=True, blank=True, help_text='Target scheduled date for routine inspection')`
  - `overall_result`: `CharField(max_length=24, choices=OVERALL_RESULT_CHOICES, default='pass')`
  - `condition_rating`: `PositiveSmallIntegerField(default=5, choices=CONDITION_RATING_CHOICES)`
  - `meter_reading`: `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text='Odometer or runtime hours captured on-site')`
  - `checklist_summary`: `TextField(blank=True, help_text='Checklist questions evaluated and itemized pass/fail results')`
  - `photo_url`: `URLField(max_length=500, blank=True, help_text='URL or document path to primary inspection photograph')`
  - `photo_caption`: `CharField(max_length=200, blank=True, help_text='Photo evidence description / defect caption')`
  - `voice_notes_transcription`: `TextField(blank=True, help_text='Speech-to-text transcription of inspector voice memos')`
  - `corrective_action_required`: `BooleanField(default=False, help_text='Whether follow-up maintenance or work order is needed')`
  - `findings_summary`: `TextField(blank=True, help_text='Executive summary of defects, leaks, wear, or abnormal vibrations')`
  - `gps_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `gps_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `location_accuracy_m`: `FloatField(null=True, blank=True, help_text='GPS fix accuracy in meters')`
  - `client_sync_id`: `CharField(max_length=64, blank=True, help_text='Client-side UUID for offline reconciliation')`
  - `is_offline_captured`: `BooleanField(default=False, help_text='Captured without internet and synced on reconnect')`
  - `synced_at`: `DateTimeField(null=True, blank=True, help_text='Timestamp of server synchronization')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_mins_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_mins_ten_stat')`
  - `Index(fields=['tenant', 'overall_result'], name='idx_mins_ten_res')`
  - `Index(fields=['tenant', 'inspection_type'], name='idx_mins_ten_type')`
  - `Index(fields=['tenant', 'inspection_date'], name='idx_mins_ten_date')`

---

### 1.2 `FieldWorkOrder` (`apps/assets/models/MobileAssetManagement/FieldWorkOrders.py`)
- **Table:** `assets_fieldworkorder`
- **Number Prefix:** `MFWO` (format: `MFWO-YYYYMM-XXXX`)
- **CHOICES:**
  - `WORK_ORDER_TYPE_CHOICES = [('emergency_repair', 'Emergency Breakdown Repair'), ('scheduled_pm', 'Scheduled Preventive Service'), ('inspection_followup', 'Inspection Defect Remediation'), ('calibration', 'On-Site Precision Calibration'), ('installation', 'Equipment Installation / Commissioning')]`
  - `PRIORITY_CHOICES = [('low', 'Low Priority'), ('medium', 'Medium Priority'), ('high', 'High Priority'), ('urgent', 'Urgent / Critical Outage')]`
  - `STATUS_CHOICES = [('dispatched', 'Dispatched / In Queue'), ('en_route', 'Technician En Route'), ('on_site', 'Technician On Site'), ('in_progress', 'Work In Progress'), ('paused', 'Paused / Waiting Parts'), ('completed', 'Work Completed'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'dispatched': 'badge-slate', 'en_route': 'badge-info', 'on_site': 'badge-amber', 'in_progress': 'badge-amber', 'paused': 'badge-muted', 'completed': 'badge-green', 'cancelled': 'badge-red'}`
  - `PRIORITY_CSS = {'low': 'badge-slate', 'medium': 'badge-info', 'high': 'badge-amber', 'urgent': 'badge-red'}`
  - `WORK_ORDER_TYPE_CSS = {'emergency_repair': 'badge-red', 'scheduled_pm': 'badge-green', 'inspection_followup': 'badge-info', 'calibration': 'badge-slate', 'installation': 'badge-purple'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='field_work_orders')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200, help_text='Brief title of the field service task')`
  - `work_order_type`: `CharField(max_length=32, choices=WORK_ORDER_TYPE_CHOICES, default='scheduled_pm')`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default='dispatched')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='field_work_orders', help_text='Subject operational equipment serviced')`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='field_work_orders')`
  - `assigned_technician`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name='assigned_field_work_orders')`
  - `maintenance_request`: `ForeignKey('assets.AssetMaintenanceRequest', on_delete=SET_NULL, null=True, blank=True, related_name='field_work_orders')`
  - `scheduled_start`: `DateTimeField(default=timezone.now)`
  - `scheduled_end`: `DateTimeField(null=True, blank=True)`
  - `actual_arrival`: `DateTimeField(null=True, blank=True, help_text='Recorded when technician clocks on-site')`
  - `completed_at`: `DateTimeField(null=True, blank=True, help_text='Timestamp of job wrap-up')`
  - `labor_wrench_minutes`: `PositiveIntegerField(default=0, help_text='Actual wrench time logged in minutes')`
  - `safety_lockout_confirmed`: `BooleanField(default=False, help_text='LOTO safety protocol verified before repair')`
  - `parts_requisition_notes`: `TextField(blank=True, help_text='Parts, gaskets, fluids, or filters requisitioned')`
  - `estimated_parts_cost`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))`
  - `work_performed_notes`: `TextField(blank=True, help_text='Technical writeup of diagnosis and root cause remedy')`
  - `signature_name`: `CharField(max_length=150, blank=True, help_text='Supervisor or customer contact signee')`
  - `signature_designation`: `CharField(max_length=100, blank=True, help_text='Title of person signing verification')`
  - `signed_at`: `DateTimeField(null=True, blank=True)`
  - `dispatch_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `dispatch_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `completion_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `completion_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `client_sync_id`: `CharField(max_length=64, blank=True)`
  - `is_offline_captured`: `BooleanField(default=False)`
  - `synced_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_mfwo_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_mfwo_ten_stat')`
  - `Index(fields=['tenant', 'priority'], name='idx_mfwo_ten_prio')`
  - `Index(fields=['tenant', 'work_order_type'], name='idx_mfwo_ten_type')`
  - `Index(fields=['tenant', 'scheduled_start'], name='idx_mfwo_ten_sched')`

---

### 1.3 `AssetScanLog` (`apps/assets/models/MobileAssetManagement/AssetScanLogs.py`)
- **Table:** `assets_assetscanlog`
- **Number Prefix:** `ASCN` (format: `ASCN-YYYYMM-XXXX`)
- **CHOICES:**
  - `SCAN_CONTEXT_CHOICES = [('field_audit', 'Field Cycle Count / Physical Audit'), ('checkout_verification', 'Tool & Equipment Custody Check-out'), ('work_order_init', 'Work Order Asset Identification'), ('receiving', 'Dock Receiving & Tag Ingestion'), ('location_reconciliation', 'Location / Yard Move Verification')]`
  - `SCAN_METHOD_CHOICES = [('camera_barcode', 'Device Camera 1D Barcode'), ('camera_qr', 'Device Camera 2D QR Code'), ('bluetooth_rfid', 'Bluetooth RFID / NFC Reader'), ('handheld_laser', 'Rugged Handheld Laser Scanner'), ('manual_entry', 'Manual Fallback Entry')]`
  - `MATCH_STATUS_CHOICES = [('matched', 'Asset Verified & Matched'), ('not_found', 'Tag Not In Registry'), ('mismatched', 'Location / Serial Mismatch'), ('unassigned', 'Blank Tag Ingested')]`
  - `MATCH_STATUS_CSS = {'matched': 'badge-green', 'not_found': 'badge-red', 'mismatched': 'badge-amber', 'unassigned': 'badge-slate'}`
  - `SCAN_METHOD_CSS = {'camera_barcode': 'badge-info', 'camera_qr': 'badge-green', 'bluetooth_rfid': 'badge-purple', 'handheld_laser': 'badge-slate', 'manual_entry': 'badge-muted'}`
  - `SCAN_CONTEXT_CSS = {'field_audit': 'badge-info', 'checkout_verification': 'badge-slate', 'work_order_init': 'badge-amber', 'receiving': 'badge-green', 'location_reconciliation': 'badge-purple'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_scans')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `scanned_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=PROTECT, related_name='asset_scans')`
  - `scanned_at`: `DateTimeField(default=timezone.now)`
  - `scan_context`: `CharField(max_length=32, choices=SCAN_CONTEXT_CHOICES, default='field_audit')`
  - `scan_method`: `CharField(max_length=24, choices=SCAN_METHOD_CHOICES, default='camera_qr')`
  - `raw_payload`: `CharField(max_length=255, help_text='Raw scanned barcode string, QR payload, or RFID EPC')`
  - `asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='scan_logs')`
  - `match_status`: `CharField(max_length=20, choices=MATCH_STATUS_CHOICES, default='matched')`
  - `gps_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `gps_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `gps_accuracy_m`: `FloatField(null=True, blank=True)`
  - `device_info`: `CharField(max_length=150, blank=True, help_text='Mobile hardware & browser agent info')`
  - `notes`: `CharField(max_length=255, blank=True)`
  - `client_sync_id`: `CharField(max_length=64, blank=True)`
  - `is_offline_captured`: `BooleanField(default=False)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ascn_ten_num_uniq')`
  - `Index(fields=['tenant', 'match_status'], name='idx_ascn_ten_stat')`
  - `Index(fields=['tenant', 'scan_context'], name='idx_ascn_ten_ctxt')`
  - `Index(fields=['tenant', 'scan_method'], name='idx_ascn_ten_meth')`
  - `Index(fields=['tenant', 'scanned_at'], name='idx_ascn_ten_date')`

---

### 1.4 `AssetGeofenceEvent` (`apps/assets/models/MobileAssetManagement/AssetGeofenceEvents.py`)
- **Table:** `assets_assetgeofenceevent`
- **Number Prefix:** `AGEO` (format: `AGEO-YYYYMM-XXXX`)
- **CHOICES:**
  - `EVENT_TYPE_CHOICES = [('inside_perimeter', 'Verified Inside Perimeter'), ('boundary_warning', 'Proximity Boundary Warning'), ('perimeter_exit', 'Unauthorized Perimeter Exit (Breach)'), ('perimeter_entry', 'Perimeter Entry Detected'), ('unauthorized_movement', 'Motion Outside Operating Hours')]`
  - `SEVERITY_CHOICES = [('info', 'Informational'), ('low', 'Low Risk'), ('medium', 'Medium Warning'), ('high', 'High Security Alert'), ('critical', 'Critical Theft / Emergency')]`
  - `STATUS_CHOICES = [('open_alert', 'Open Security Alert'), ('under_investigation', 'Under Field Investigation'), ('resolved', 'Resolved & Cleared'), ('false_alarm', 'False Alarm / Sensor Glitch')]`
  - `EVENT_TYPE_CSS = {'inside_perimeter': 'badge-green', 'boundary_warning': 'badge-amber', 'perimeter_exit': 'badge-red', 'perimeter_entry': 'badge-info', 'unauthorized_movement': 'badge-red'}`
  - `SEVERITY_CSS = {'info': 'badge-slate', 'low': 'badge-info', 'medium': 'badge-amber', 'high': 'badge-red', 'critical': 'badge-red'}`
  - `STATUS_CSS = {'open_alert': 'badge-red', 'under_investigation': 'badge-amber', 'resolved': 'badge-green', 'false_alarm': 'badge-muted'}`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='geofence_events')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='geofence_events', help_text='Subject mobile or plant asset tracked')`
  - `fence_name`: `CharField(max_length=150, help_text='Name of designated yard or facility boundary')`
  - `center_latitude`: `DecimalField(max_digits=9, decimal_places=6, help_text='Yard center latitude')`
  - `center_longitude`: `DecimalField(max_digits=9, decimal_places=6, help_text='Yard center longitude')`
  - `radius_meters`: `PositiveIntegerField(default=100, help_text='Authorized perimeter radius in meters')`
  - `recorded_latitude`: `DecimalField(max_digits=9, decimal_places=6, help_text='Actual asset latitude fix')`
  - `recorded_longitude`: `DecimalField(max_digits=9, decimal_places=6, help_text='Actual asset longitude fix')`
  - `recorded_accuracy_m`: `FloatField(null=True, blank=True)`
  - `distance_from_center_m`: `FloatField(default=0.0, help_text='Calculated distance from center in meters')`
  - `event_type`: `CharField(max_length=28, choices=EVENT_TYPE_CHOICES, default='inside_perimeter')`
  - `severity`: `CharField(max_length=16, choices=SEVERITY_CHOICES, default='info')`
  - `status`: `CharField(max_length=24, choices=STATUS_CHOICES, default='open_alert')`
  - `detected_at`: `DateTimeField(default=timezone.now)`
  - `acknowledged_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='acknowledged_geofence_events')`
  - `acknowledged_at`: `DateTimeField(null=True, blank=True)`
  - `resolution_notes`: `TextField(blank=True, help_text='Security investigation or clearing notes')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes (L65 compliant <= 30 chars):**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ageo_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ageo_ten_stat')`
  - `Index(fields=['tenant', 'event_type'], name='idx_ageo_ten_type')`
  - `Index(fields=['tenant', 'severity'], name='idx_ageo_ten_sev')`
  - `Index(fields=['tenant', 'detected_at'], name='idx_ageo_ten_date')`

---

## 2. Forms Contract

ModelForms live in `apps/assets/forms/MobileAssetManagement/<Entity>.py`.
All forms exclude `tenant`, `number`, system timestamps, and backend-computed audit fields.

1. `MobileAssetInspectionForm`:
   - Excludes: `['tenant', 'number', 'created_at', 'updated_at', 'synced_at']`
   - Scopes `asset`, `fixed_asset`, and `inspector` strictly to `request.tenant`.
   - Widgets: styled with `.form-input`, `.form-select`, `.form-textarea`.

2. `FieldWorkOrderForm`:
   - Excludes: `['tenant', 'number', 'created_at', 'updated_at', 'actual_arrival', 'completed_at', 'signed_at', 'synced_at']`
   - Scopes `asset`, `fixed_asset`, `assigned_technician`, and `maintenance_request` to `request.tenant`.

3. `AssetScanLogForm`:
   - Excludes: `['tenant', 'number', 'created_at', 'updated_at', 'scanned_at']`
   - Scopes `scanned_by` and `asset` to `request.tenant`.

4. `AssetGeofenceEventForm`:
   - Excludes: `['tenant', 'number', 'created_at', 'updated_at', 'detected_at', 'acknowledged_at']`
   - Scopes `asset` and `acknowledged_by` to `request.tenant`.

---

## 3. Views & URLconf Contract

### 3.1 `MobileAssetInspection` Views & Routes
- `mobile_asset_inspection_list` (`mobile/inspections/`):
  - View context keys: `inspections`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `result_choices`, `type_choices`, `total_inspections`, `passed_count`, `failed_count`, `offline_captured_count`.
  - Filters: `q`, `status`, `overall_result`, `inspection_type`.
- `mobile_asset_inspection_create` (`mobile/inspections/new/`) -> template `templates/assets/mobileassetmanagement/mobile_asset_inspection/form.html`
- `mobile_asset_inspection_detail` (`mobile/inspections/<int:pk>/`) -> context `inspection`
- `mobile_asset_inspection_edit` (`mobile/inspections/<int:pk>/edit/`) -> context `form`, `inspection`
- `mobile_asset_inspection_delete` (`mobile/inspections/<int:pk>/delete/`) -> POST-only

### 3.2 `FieldWorkOrder` Views & Routes
- `field_work_order_list` (`mobile/work-orders/`):
  - View context keys: `work_orders`, `page_obj`, `paginator`, `is_paginated`, `status_choices`, `priority_choices`, `type_choices`, `total_work_orders`, `active_count`, `completed_count`, `urgent_count`, `total_wrench_hours`.
  - Filters: `q`, `status`, `priority`, `work_order_type`.
- `field_work_order_create` (`mobile/work-orders/new/`) -> template `templates/assets/mobileassetmanagement/field_work_order/form.html`
- `field_work_order_detail` (`mobile/work-orders/<int:pk>/`) -> context `work_order`
- `field_work_order_edit` (`mobile/work-orders/<int:pk>/edit/`) -> context `form`, `work_order`
- `field_work_order_delete` (`mobile/work-orders/<int:pk>/delete/`) -> POST-only

### 3.3 `AssetScanLog` Views & Routes
- `asset_scan_log_list` (`mobile/scans/`):
  - View context keys: `scans`, `page_obj`, `paginator`, `is_paginated`, `match_choices`, `method_choices`, `context_choices`, `total_scans`, `matched_count`, `not_found_count`, `rfid_count`.
  - Filters: `q`, `match_status`, `scan_method`, `scan_context`.
- `asset_scan_log_create` (`mobile/scans/new/`) -> template `templates/assets/mobileassetmanagement/asset_scan_log/form.html`
- `asset_scan_log_detail` (`mobile/scans/<int:pk>/`) -> context `scan`
- `asset_scan_log_edit` (`mobile/scans/<int:pk>/edit/`) -> context `form`, `scan`
- `asset_scan_log_delete` (`mobile/scans/<int:pk>/delete/`) -> POST-only

### 3.4 `AssetGeofenceEvent` Views & Routes
- `asset_geofence_event_list` (`mobile/geofence/`):
  - View context keys: `events`, `page_obj`, `paginator`, `is_paginated`, `event_type_choices`, `severity_choices`, `status_choices`, `total_events`, `open_alerts_count`, `critical_breaches_count`, `resolved_count`.
  - Filters: `q`, `status`, `event_type`, `severity`.
- `asset_geofence_event_create` (`mobile/geofence/new/`) -> template `templates/assets/mobileassetmanagement/asset_geofence_event/form.html`
- `asset_geofence_event_detail` (`mobile/geofence/<int:pk>/`) -> context `event`
- `asset_geofence_event_edit` (`mobile/geofence/<int:pk>/edit/`) -> context `form`, `event`
- `asset_geofence_event_delete` (`mobile/geofence/<int:pk>/delete/`) -> POST-only

---

## 4. Templates Contract

Paths follow the strict package standard: `templates/assets/mobileassetmanagement/<entity>/{list,detail,form}.html`:
1. `templates/assets/mobileassetmanagement/mobile_asset_inspection/{list,detail,form}.html`
2. `templates/assets/mobileassetmanagement/field_work_order/{list,detail,form}.html`
3. `templates/assets/mobileassetmanagement/asset_scan_log/{list,detail,form}.html`
4. `templates/assets/mobileassetmanagement/asset_geofence_event/{list,detail,form}.html`

All templates extend `templates/base.html`, use standard theme.css classes, include colour-named badges, full filter bars, pagination guards, and delete confirmations.

---

## 5. Navigation Wiring Contract (`LIVE_LINKS["11.13"]`)

In `apps/core/navigation.py`:
```python
    "11.13": {
        "Mobile Inspection & Data Capture": "assets:mobile_asset_inspection_list",
        "Field Technician Work Orders": "assets:field_work_order_list",
        "Barcode/RFID Scanning": "assets:asset_scan_log_list",
        "GPS & Geofencing": "assets:asset_geofence_event_list",
        "Offline Synchronization": "assets:mobile_asset_inspection_list",
        # Plural and convenience aliases
        "Mobile Inspections": "assets:mobile_asset_inspection_list",
        "Field Work Orders": "assets:field_work_order_list",
        "Asset Scans": "assets:asset_scan_log_list",
        "Scan Logs": "assets:asset_scan_log_list",
        "Barcode Scanning": "assets:asset_scan_log_list",
        "RFID Scanning": "assets:asset_scan_log_list",
        "Geofence Alerts": "assets:asset_geofence_event_list",
        "GPS Geofencing": "assets:asset_geofence_event_list",
        "Mobile Asset Management": "assets:mobile_asset_inspection_list",
    },
```

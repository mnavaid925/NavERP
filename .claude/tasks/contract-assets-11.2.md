# Contract — Sub-module 11.2: Asset Inventory & Tracking (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.2 Asset Inventory & Tracking • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-08 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Extending live `apps/assets/`. Incremental migration: `0002_...`.
- **Package Layout:** `AssetInventoryTracking/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_inventory_tracking/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetAudit` (`apps/assets/models/AssetInventoryTracking/AssetAudits.py`)
- **Table:** `assets_audit`
- **Number Prefix:** `AAUD` (format: `AAUD-00001`)
- **CHOICES:**
  - `AUDIT_TYPE_CHOICES = [('wall_to_wall', 'Wall-to-Wall Physical Audit'), ('cycle_count', 'Cyclical Sample Count'), ('spot_check', 'Ad-Hoc Spot Check'), ('custodian_verification', 'Custodian Ownership Verification')]`
  - `STATUS_CHOICES = [('draft', 'Draft Scheduled'), ('scheduled', 'Scheduled'), ('in_progress', 'In Progress'), ('completed', 'Count Completed'), ('reconciled', 'Reconciled & Closed'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'scheduled': 'badge-info', 'in_progress': 'badge-amber', 'completed': 'badge-info', 'reconciled': 'badge-green', 'cancelled': 'badge-red'}`
  - `RECONCILIATION_ACTION_CHOICES = [('pending_review', 'Pending Supervisor Review'), ('no_action_needed', 'No Discrepancy / Closed'), ('location_updated', 'Asset Location Updated'), ('incident_initiated', 'Missing Incident Initiated'), ('custodian_reassigned', 'Custodian Reassigned')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_audits')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `audit_type`: `CharField(max_length=30, choices=AUDIT_TYPE_CHOICES, default='cycle_count')`
  - `target_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='asset_audits')`
  - `target_org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='asset_audits')`
  - `asset_category`: `CharField(max_length=100, blank=True, help_text='Optional asset category filter in scope')`
  - `lead_auditor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='lead_asset_audits')`
  - `supervisor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='supervised_asset_audits')`
  - `scheduled_date`: `DateField(default=timezone.now)`
  - `started_at`: `DateTimeField(null=True, blank=True)`
  - `completed_at`: `DateTimeField(null=True, blank=True)`
  - `is_blind_count`: `BooleanField(default=False, help_text='Hide expected asset lists from field counters to prevent confirmation bias')`
  - `expected_asset_count`: `PositiveIntegerField(default=0)`
  - `scanned_asset_count`: `PositiveIntegerField(default=0)`
  - `matched_asset_count`: `PositiveIntegerField(default=0)`
  - `missing_asset_count`: `PositiveIntegerField(default=0)`
  - `discrepancy_count`: `PositiveIntegerField(default=0)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='draft')`
  - `discrepancy_notes`: `TextField(blank=True)`
  - `reconciliation_action`: `CharField(max_length=30, choices=RECONCILIATION_ACTION_CHOICES, default='pending_review')`
  - `reconciled_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='reconciled_asset_audits')`
  - `reconciled_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_aaud_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_aaud_ten_stat')`
  - `Index(fields=['tenant', 'audit_type'], name='idx_aaud_ten_type')`
  - `Index(fields=['tenant', 'scheduled_date'], name='idx_aaud_ten_date')`
  - `Index(fields=['tenant', 'created_at'], name='idx_aaud_ten_created')`

---

### 1.2 `AssetMovementLog` (`apps/assets/models/AssetInventoryTracking/AssetMovementLogs.py`)
- **Table:** `assets_movement_log`
- **Number Prefix:** `AMOV` (format: `AMOV-00001`)
- **CHOICES:**
  - `MOVEMENT_TYPE_CHOICES = [('relocation', 'Internal Relocation'), ('inter_facility_transfer', 'Inter-Facility Transfer'), ('room_reassignment', 'Room / Bin Reassignment'), ('department_transfer', 'Department Transfer'), ('repair_dispatch', 'Offsite Repair Dispatch'), ('temporary_deployment', 'Temporary Field Deployment')]`
  - `STATUS_CHOICES = [('draft', 'Draft Request'), ('requested', 'Transfer Requested'), ('dispatched', 'Dispatched / In Transit'), ('in_transit', 'In Transit'), ('received', 'Received & Verified'), ('rejected', 'Rejected at Destination'), ('cancelled', 'Cancelled')]`
  - `STATUS_CSS = {'draft': 'badge-slate', 'requested': 'badge-info', 'dispatched': 'badge-amber', 'in_transit': 'badge-amber', 'received': 'badge-green', 'rejected': 'badge-red', 'cancelled': 'badge-muted'}`
  - `CONDITION_CHOICES = [('good', 'Good / Undamaged'), ('fair', 'Fair / Minor Transit Wear'), ('damaged', 'Damaged in Transit')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_movement_logs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='movement_logs')`
  - `movement_type`: `CharField(max_length=30, choices=MOVEMENT_TYPE_CHOICES, default='relocation')`
  - `from_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='outgoing_asset_movements')`
  - `from_org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='outgoing_asset_movements')`
  - `from_room_bin`: `CharField(max_length=100, blank=True, help_text='Specific source building, floor, room, or bin')`
  - `to_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='incoming_asset_movements')`
  - `to_org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='incoming_asset_movements')`
  - `to_room_bin`: `CharField(max_length=100, blank=True, help_text='Specific destination building, floor, room, or bin')`
  - `from_custodian`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='relinquished_asset_movements')`
  - `to_custodian`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='accepted_asset_movements')`
  - `gps_latitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `gps_longitude`: `DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)`
  - `gps_address`: `CharField(max_length=255, blank=True)`
  - `carrier_name`: `CharField(max_length=100, blank=True)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `dispatch_date`: `DateTimeField(null=True, blank=True)`
  - `received_date`: `DateTimeField(null=True, blank=True)`
  - `dispatched_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='dispatched_asset_movements')`
  - `received_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='received_asset_movements')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='draft')`
  - `condition_on_receipt`: `CharField(max_length=20, choices=CONDITION_CHOICES, default='good')`
  - `reason`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_amov_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_amov_ten_stat')`
  - `Index(fields=['tenant', 'movement_type'], name='idx_amov_ten_type')`
  - `Index(fields=['tenant', 'asset'], name='idx_amov_ten_asset')`
  - `Index(fields=['tenant', 'created_at'], name='idx_amov_ten_created')`

---

### 1.3 `AssetCustodyLog` (`apps/assets/models/AssetInventoryTracking/AssetCustodyLogs.py`)
- **Table:** `assets_custody_log`
- **Number Prefix:** `ACHK` (format: `ACHK-00001`)
- **CHOICES:**
  - `ACTION_TYPE_CHOICES = [('checkout', 'Equipment Checkout'), ('checkin', 'Equipment Return (Checkin)'), ('custody_transfer', 'Peer-to-Peer Transfer'), ('extension', 'Loan Extension')]`
  - `STATUS_CHOICES = [('active_loan', 'Active Loan'), ('returned', 'Returned & Checked In'), ('overdue', 'Overdue for Return'), ('damaged_returned', 'Returned Damaged'), ('unreturned_lost', 'Unreturned / Presumed Lost')]`
  - `STATUS_CSS = {'active_loan': 'badge-amber', 'returned': 'badge-green', 'overdue': 'badge-red', 'damaged_returned': 'badge-red', 'unreturned_lost': 'badge-muted'}`
  - `CHECKOUT_CONDITION_CHOICES = [('excellent', 'Excellent (Like New)'), ('good', 'Good (Standard Wear)'), ('fair', 'Fair (Operational Wear)')]`
  - `RETURN_CONDITION_CHOICES = [('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('damaged', 'Damaged'), ('inoperable', 'Inoperable / Broken')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_custody_logs')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='custody_logs')`
  - `action_type`: `CharField(max_length=30, choices=ACTION_TYPE_CHOICES, default='checkout')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='active_loan')`
  - `borrower`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='asset_custody_loans')`
  - `borrower_name`: `CharField(max_length=120, blank=True, help_text='Name of individual borrower or contractor')`
  - `crib_attendant`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='managed_asset_loans')`
  - `purpose`: `CharField(max_length=200, blank=True)`
  - `work_order_reference`: `CharField(max_length=64, blank=True, help_text='Optional Maintenance Work Order number or task reference')`
  - `project_reference`: `CharField(max_length=100, blank=True)`
  - `checkout_date`: `DateTimeField(default=timezone.now)`
  - `expected_return_date`: `DateField(null=True, blank=True)`
  - `actual_return_date`: `DateTimeField(null=True, blank=True)`
  - `checkout_condition`: `CharField(max_length=20, choices=CHECKOUT_CONDITION_CHOICES, default='good')`
  - `return_condition`: `CharField(max_length=20, choices=RETURN_CONDITION_CHOICES, blank=True)`
  - `condition_notes`: `TextField(blank=True)`
  - `borrower_signature_acknowledged`: `BooleanField(default=True, help_text='Borrower electronically acknowledged custody and liability')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_achk_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_achk_ten_stat')`
  - `Index(fields=['tenant', 'action_type'], name='idx_achk_ten_act')`
  - `Index(fields=['tenant', 'asset'], name='idx_achk_ten_asset')`
  - `Index(fields=['tenant', 'expected_return_date'], name='idx_achk_ten_expdate')`
  - `Index(fields=['tenant', 'created_at'], name='idx_achk_ten_created')`

---

### 1.4 `AssetIncidentReport` (`apps/assets/models/AssetInventoryTracking/AssetIncidentReports.py`)
- **Table:** `assets_incident_report`
- **Number Prefix:** `AINC` (format: `AINC-00001`)
- **CHOICES:**
  - `INCIDENT_TYPE_CHOICES = [('lost', 'Lost / Misplaced in Field'), ('stolen', 'Stolen / Burglary'), ('missing_in_audit', 'Missing During Physical Audit'), ('damaged_beyond_repair', 'Damaged Beyond Economical Repair'), ('vandalism', 'Vandalism / Sabotage')]`
  - `SEVERITY_CHOICES = [('low', 'Low (Non-critical / Low Value)'), ('medium', 'Medium (Standard Asset)'), ('high', 'High (Production Impact)'), ('critical', 'Critical (Core Infrastructure / Safety)')]`
  - `STATUS_CHOICES = [('reported', 'Reported / Under Review'), ('under_investigation', 'Under Active Investigation'), ('confirmed_lost', 'Confirmed Lost / Missing'), ('recovered', 'Recovered & Returned'), ('write_off_pending', 'Pending Write-Off Approval'), ('written_off', 'Written Off / Decommissioned'), ('closed', 'Closed Without Recovery')]`
  - `STATUS_CSS = {'reported': 'badge-slate', 'under_investigation': 'badge-amber', 'confirmed_lost': 'badge-red', 'recovered': 'badge-green', 'write_off_pending': 'badge-amber', 'written_off': 'badge-muted', 'closed': 'badge-muted'}`
  - `RESOLUTION_ACTION_CHOICES = [('pending', 'Pending Investigation'), ('recovered', 'Asset Recovered'), ('replacement_sourced', 'Replacement Asset Sourced'), ('written_off', 'Approved for Write-Off'), ('unresolved_closed', 'Closed Unresolved')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_incident_reports')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `asset`: `ForeignKey('scm.Asset', on_delete=CASCADE, related_name='incident_reports')`
  - `incident_type`: `CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES, default='lost')`
  - `severity`: `CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='reported')`
  - `resolution_action`: `CharField(max_length=30, choices=RESOLUTION_ACTION_CHOICES, default='pending')`
  - `incident_date`: `DateField(default=timezone.now)`
  - `last_known_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='asset_incidents')`
  - `location_details`: `CharField(max_length=255, blank=True)`
  - `reported_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='reported_asset_incidents')`
  - `custodian_at_loss`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='custodian_asset_incidents')`
  - `investigator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='investigated_asset_incidents')`
  - `police_report_filed`: `BooleanField(default=False)`
  - `police_report_number`: `CharField(max_length=100, blank=True)`
  - `police_precinct`: `CharField(max_length=120, blank=True)`
  - `police_filing_date`: `DateField(null=True, blank=True)`
  - `insurance_claim_filed`: `BooleanField(default=False)`
  - `insurance_carrier`: `CharField(max_length=120, blank=True)`
  - `insurance_claim_number`: `CharField(max_length=100, blank=True)`
  - `estimated_loss_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `insurance_claimed_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `insurance_settled_amount`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `incident_description`: `TextField()`
  - `investigation_findings`: `TextField(blank=True)`
  - `write_off_authorized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='authorized_asset_write_offs')`
  - `write_off_date`: `DateField(null=True, blank=True)`
  - `write_off_notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_ainc_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_ainc_ten_stat')`
  - `Index(fields=['tenant', 'incident_type'], name='idx_ainc_ten_type')`
  - `Index(fields=['tenant', 'severity'], name='idx_ainc_ten_sev')`
  - `Index(fields=['tenant', 'asset'], name='idx_ainc_ten_asset')`
  - `Index(fields=['tenant', 'created_at'], name='idx_ainc_ten_created')`

---

## 2. Forms Contract

All forms inherit from `forms.ModelForm`. Forms accept `tenant` in `__init__` and scope dropdowns (`target_location`, `target_org_unit`, `asset`, `borrower`, etc.) to `request.tenant`.

### 2.1 `AssetAuditForm` (`apps/assets/forms/AssetInventoryTracking/AssetAudits.py`)
- **Model:** `AssetAudit`
- **Fields:** `['title', 'audit_type', 'target_location', 'target_org_unit', 'asset_category', 'lead_auditor', 'supervisor', 'scheduled_date', 'is_blind_count', 'expected_asset_count', 'scanned_asset_count', 'matched_asset_count', 'missing_asset_count', 'discrepancy_count', 'discrepancy_notes', 'reconciliation_action', 'notes']`
- **Exclude:** `['tenant', 'number', 'status', 'created_at', 'updated_at', 'started_at', 'completed_at', 'reconciled_by', 'reconciled_at']`
- **Widgets:** `scheduled_date` -> `DateInput(attrs={'type': 'date', 'class': 'form-input'})`

### 2.2 `AssetMovementLogForm` (`apps/assets/forms/AssetInventoryTracking/AssetMovementLogs.py`)
- **Model:** `AssetMovementLog`
- **Fields:** `['title', 'asset', 'movement_type', 'from_location', 'from_org_unit', 'from_room_bin', 'to_location', 'to_org_unit', 'to_room_bin', 'from_custodian', 'to_custodian', 'gps_latitude', 'gps_longitude', 'gps_address', 'carrier_name', 'tracking_number', 'condition_on_receipt', 'reason', 'notes']`
- **Exclude:** `['tenant', 'number', 'status', 'created_at', 'updated_at', 'dispatch_date', 'dispatched_by', 'received_date', 'received_by']`

### 2.3 `AssetCustodyLogForm` (`apps/assets/forms/AssetInventoryTracking/AssetCustodyLogs.py`)
- **Model:** `AssetCustodyLog`
- **Fields:** `['asset', 'action_type', 'borrower', 'borrower_name', 'crib_attendant', 'purpose', 'work_order_reference', 'project_reference', 'checkout_date', 'expected_return_date', 'checkout_condition', 'condition_notes', 'borrower_signature_acknowledged', 'notes']`
- **Exclude:** `['tenant', 'number', 'status', 'created_at', 'updated_at', 'actual_return_date', 'return_condition']`
- **Widgets:** `expected_return_date` -> `DateInput(attrs={'type': 'date', 'class': 'form-input'})`, `checkout_date` -> `DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'})`

### 2.4 `AssetIncidentReportForm` (`apps/assets/forms/AssetInventoryTracking/AssetIncidentReports.py`)
- **Model:** `AssetIncidentReport`
- **Fields:** `['title', 'asset', 'incident_type', 'severity', 'incident_date', 'last_known_location', 'location_details', 'custodian_at_loss', 'investigator', 'police_report_filed', 'police_report_number', 'police_precinct', 'police_filing_date', 'insurance_claim_filed', 'insurance_carrier', 'insurance_claim_number', 'estimated_loss_value', 'insurance_claimed_amount', 'insurance_settled_amount', 'incident_description', 'investigation_findings', 'resolution_action', 'write_off_notes']`
- **Exclude:** `['tenant', 'number', 'status', 'created_at', 'updated_at', 'reported_by', 'write_off_authorized_by', 'write_off_date']`
- **Widgets:** `incident_date` -> `DateInput(attrs={'type': 'date', 'class': 'form-input'})`, `police_filing_date` -> `DateInput(attrs={'type': 'date', 'class': 'form-input'})`

---

## 3. URLs & Routing Contract (`app_name = 'assets'`)

### 3.1 `AssetAudit`
- `asset_audit_list`: `GET /assets/inventory-tracking/audits/`
- `asset_audit_create`: `GET/POST /assets/inventory-tracking/audits/new/`
- `asset_audit_detail`: `GET /assets/inventory-tracking/audits/<int:pk>/`
- `asset_audit_edit`: `GET/POST /assets/inventory-tracking/audits/<int:pk>/edit/`
- `asset_audit_delete`: `POST /assets/inventory-tracking/audits/<int:pk>/delete/`
- `asset_audit_start`: `POST /assets/inventory-tracking/audits/<int:pk>/start/`
- `asset_audit_complete`: `POST /assets/inventory-tracking/audits/<int:pk>/complete/`
- `asset_audit_reconcile`: `POST /assets/inventory-tracking/audits/<int:pk>/reconcile/`
- `asset_audit_cancel`: `POST /assets/inventory-tracking/audits/<int:pk>/cancel/`

### 3.2 `AssetMovementLog`
- `asset_movement_log_list`: `GET /assets/inventory-tracking/movements/`
- `asset_movement_log_create`: `GET/POST /assets/inventory-tracking/movements/new/`
- `asset_movement_log_detail`: `GET /assets/inventory-tracking/movements/<int:pk>/`
- `asset_movement_log_edit`: `GET/POST /assets/inventory-tracking/movements/<int:pk>/edit/`
- `asset_movement_log_delete`: `POST /assets/inventory-tracking/movements/<int:pk>/delete/`
- `asset_movement_log_dispatch`: `POST /assets/inventory-tracking/movements/<int:pk>/dispatch/`
- `asset_movement_log_receive`: `POST /assets/inventory-tracking/movements/<int:pk>/receive/`
- `asset_movement_log_cancel`: `POST /assets/inventory-tracking/movements/<int:pk>/cancel/`

### 3.3 `AssetCustodyLog`
- `asset_custody_log_list`: `GET /assets/inventory-tracking/custody/`
- `asset_custody_log_create`: `GET/POST /assets/inventory-tracking/custody/new/`
- `asset_custody_log_detail`: `GET /assets/inventory-tracking/custody/<int:pk>/`
- `asset_custody_log_edit`: `GET/POST /assets/inventory-tracking/custody/<int:pk>/edit/`
- `asset_custody_log_delete`: `POST /assets/inventory-tracking/custody/<int:pk>/delete/`
- `asset_custody_log_checkin`: `POST /assets/inventory-tracking/custody/<int:pk>/checkin/`
- `asset_custody_log_extend`: `POST /assets/inventory-tracking/custody/<int:pk>/extend/`
- `asset_custody_log_mark_lost`: `POST /assets/inventory-tracking/custody/<int:pk>/mark-lost/`

### 3.4 `AssetIncidentReport`
- `asset_incident_report_list`: `GET /assets/inventory-tracking/incidents/`
- `asset_incident_report_create`: `GET/POST /assets/inventory-tracking/incidents/new/`
- `asset_incident_report_detail`: `GET /assets/inventory-tracking/incidents/<int:pk>/`
- `asset_incident_report_edit`: `GET/POST /assets/inventory-tracking/incidents/<int:pk>/edit/`
- `asset_incident_report_delete`: `POST /assets/inventory-tracking/incidents/<int:pk>/delete/`
- `asset_incident_report_investigate`: `POST /assets/inventory-tracking/incidents/<int:pk>/investigate/`
- `asset_incident_report_resolve_recovered`: `POST /assets/inventory-tracking/incidents/<int:pk>/resolve-recovered/`
- `asset_incident_report_authorize_write_off`: `POST /assets/inventory-tracking/incidents/<int:pk>/authorize-write-off/`
- `asset_incident_report_close`: `POST /assets/inventory-tracking/incidents/<int:pk>/close/`

---

## 4. View Context Keys Contract (CRITICAL — L7)

### 4.1 `AssetAudit`
- **List View (`asset_audit_list`):**
  - List variable: `audits` (and `page_obj`, `paginator`, `is_paginated`)
  - Filter dropdown querysets: `locations` (`scm.Location.objects.filter(tenant=request.tenant)`), `org_units` (`core.OrgUnit.objects.filter(tenant=request.tenant)`)
  - Filter choice lists: `type_choices` (`AssetAudit.AUDIT_TYPE_CHOICES`), `status_choices` (`AssetAudit.STATUS_CHOICES`), `action_choices` (`AssetAudit.RECONCILIATION_ACTION_CHOICES`)
  - Search param: `q` (`request.GET.get('q', '')`)
  - Summary stats: `total_count`, `scheduled_count`, `in_progress_count`, `completed_count`, `reconciled_count`
- **Detail View (`asset_audit_detail`):**
  - Object variable: `audit`
- **Form View (`asset_audit_create` / `asset_audit_edit`):**
  - Form variable: `form`
  - Edit-mode object variable: `audit` (None on create)
  - Mode flag: `is_edit` (Boolean)

### 4.2 `AssetMovementLog`
- **List View (`asset_movement_log_list`):**
  - List variable: `movements` (and `page_obj`, `paginator`, `is_paginated`)
  - Filter dropdown querysets: `locations` (`scm.Location.objects.filter(tenant=request.tenant)`), `org_units` (`core.OrgUnit.objects.filter(tenant=request.tenant)`), `assets` (`scm.Asset.objects.filter(tenant=request.tenant)`)
  - Filter choice lists: `type_choices` (`AssetMovementLog.MOVEMENT_TYPE_CHOICES`), `status_choices` (`AssetMovementLog.STATUS_CHOICES`), `condition_choices` (`AssetMovementLog.CONDITION_CHOICES`)
  - Search param: `q`
  - Summary stats: `total_count`, `in_transit_count`, `received_count`, `requested_count`
- **Detail View (`asset_movement_log_detail`):**
  - Object variable: `movement`
- **Form View (`asset_movement_log_create` / `asset_movement_log_edit`):**
  - Form variable: `form`
  - Edit-mode object variable: `movement` (None on create)
  - Mode flag: `is_edit`

### 4.3 `AssetCustodyLog`
- **List View (`asset_custody_log_list`):**
  - List variable: `custody_logs` (and `page_obj`, `paginator`, `is_paginated`)
  - Filter dropdown querysets: `borrowers` (`core.Party.objects.filter(tenant=request.tenant)`), `assets` (`scm.Asset.objects.filter(tenant=request.tenant)`)
  - Filter choice lists: `action_choices` (`AssetCustodyLog.ACTION_TYPE_CHOICES`), `status_choices` (`AssetCustodyLog.STATUS_CHOICES`), `condition_choices` (`AssetCustodyLog.CHECKOUT_CONDITION_CHOICES`)
  - Search param: `q`
  - Summary stats: `total_count`, `active_loans_count`, `overdue_count`, `returned_count`
- **Detail View (`asset_custody_log_detail`):**
  - Object variable: `custody_log`
- **Form View (`asset_custody_log_create` / `asset_custody_log_edit`):**
  - Form variable: `form`
  - Edit-mode object variable: `custody_log` (None on create)
  - Mode flag: `is_edit`

### 4.4 `AssetIncidentReport`
- **List View (`asset_incident_report_list`):**
  - List variable: `incidents` (and `page_obj`, `paginator`, `is_paginated`)
  - Filter dropdown querysets: `locations` (`scm.Location.objects.filter(tenant=request.tenant)`), `assets` (`scm.Asset.objects.filter(tenant=request.tenant)`)
  - Filter choice lists: `type_choices` (`AssetIncidentReport.INCIDENT_TYPE_CHOICES`), `severity_choices` (`AssetIncidentReport.SEVERITY_CHOICES`), `status_choices` (`AssetIncidentReport.STATUS_CHOICES`), `resolution_choices` (`AssetIncidentReport.RESOLUTION_ACTION_CHOICES`)
  - Search param: `q`
  - Summary stats: `total_count`, `reported_count`, `investigating_count`, `confirmed_lost_count`, `write_off_pending_count`
- **Detail View (`asset_incident_report_detail`):**
  - Object variable: `incident`
- **Form View (`asset_incident_report_create` / `asset_incident_report_edit`):**
  - Form variable: `form`
  - Edit-mode object variable: `incident` (None on create)
  - Mode flag: `is_edit`

---

## 5. Templates Contract

Template paths:
- `templates/assets/asset_inventory_tracking/asset_audit/list.html`
- `templates/assets/asset_inventory_tracking/asset_audit/detail.html`
- `templates/assets/asset_inventory_tracking/asset_audit/form.html`
- `templates/assets/asset_inventory_tracking/asset_movement_log/list.html`
- `templates/assets/asset_inventory_tracking/asset_movement_log/detail.html`
- `templates/assets/asset_inventory_tracking/asset_movement_log/form.html`
- `templates/assets/asset_inventory_tracking/asset_custody_log/list.html`
- `templates/assets/asset_inventory_tracking/asset_custody_log/detail.html`
- `templates/assets/asset_inventory_tracking/asset_custody_log/form.html`
- `templates/assets/asset_inventory_tracking/asset_incident_report/list.html`
- `templates/assets/asset_inventory_tracking/asset_incident_report/detail.html`
- `templates/assets/asset_inventory_tracking/asset_incident_report/form.html`

All templates extend `base.html` and use standard `theme.css` classes:
- Badges: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` (L33).
- Buttons: `.btn .btn-primary .btn-outline .btn-danger .btn-icon`.
- Filter comparisons: `|stringformat:"d"` for integers/FK IDs.
- Pagination: safe `has_previous`/`has_next` checks (L9) preserving all GET filter parameters.

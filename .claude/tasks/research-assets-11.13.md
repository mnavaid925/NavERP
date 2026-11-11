# Research — Sub-module 11.13: Mobile Asset Management (Module 11 — Asset Management System, `assets`)

## Repo state checked first
- **LIVE_LINKS built so far in module 11**: `11.1` (Asset Procurement & Acquisition), `11.2` (Asset Inventory & Tracking), `11.3` (Asset Classification & Categorization), `11.4` (Depreciation & Financial Management), `11.5` (Maintenance & Repair Management), `11.6` (Asset Performance & Utilization), `11.7` (Asset Reliability & Condition Monitoring), `11.8` (Warranty & Insurance Management), `11.9` (Asset Disposal & Retirement), `11.10` (Lease & Rental Management), `11.11` (Compliance & Regulatory Management).
- **Sub-module chosen**: `11.13 Mobile Asset Management` (explicitly requested by user; out-of-order execution before `11.12 Asset Risk Management`).
- **Verified existing models available to FK**:
  - `scm.Asset` (primary operational asset register with tag, serial number, model, location)
  - `accounting.FixedAsset` (financial asset ledger entity)
  - `assets.AssetMaintenanceRequest` (maintenance intake requests)
  - `assets.AssetTag` (physical RFID/barcode tags)
  - `core.Tenant` (multi-tenant boundary)
  - `core.User` (technicians, inspectors, dispatchers)
- **Spine entities verified to exist / NOT exist**:
  - `scm.Asset` exists (`apps/scm/models/EnterpriseAssetManagement/Asset.py`).
  - `accounting.FixedAsset` exists (`apps/accounting/models/FixedAssets/FixedAssets.py`).
  - `assets.AssetMaintenanceRequest` exists (`apps/assets/models/AssetMaintenance/AssetMaintenanceRequests.py`).
  - Standalone mobile native app binary is out of scope; field interface is responsive Tailwind + HTMX mobile web with camera/file inputs, GPS geolocation API, barcode lookup, and offline sync transaction journal.

---

## Leaders surveyed (with source links)
1. **IBM Maximo Mobile (IBM Application Suite)** — Enterprise mobile EAM providing technician execution, guided inspections, barcode/NFC scanning, and offline data sync.
   *Source: https://www.ibm.com/products/maximo/mobile*
2. **MaintainX** — Mobile-first frontline work execution platform featuring digital inspection checklists, voice-to-text, in-app camera capture, and offline mode.
   *Source: https://www.getmaintainx.com*
3. **UpKeep Mobile CMMS** — Field technician maintenance app with mobile work orders, barcode/QR asset lookup, parts requisition from the field, and offline sync.
   *Source: https://www.onupkeep.com*
4. **Asset Panda Mobile** — Highly configurable mobile asset tracking platform with native camera barcode/QR scanning, GPS audit stamping, and offline sync queues.
   *Source: https://www.assetpanda.com*
5. **SAP Service and Asset Manager** — Enterprise mobile solution for field technicians supporting offline work order execution, GIS map integration, and digital signatures.
   *Source: https://www.sap.com/products/scm/service-asset-manager.html*
6. **HxGN EAM Mobile (Hexagon)** — Mobile EAM with GIS/geofencing map visualization, mobile inspections, and linear asset tracking for utilities and heavy industry.
   *Source: https://hexagon.com/products/hxgn-eam*
7. **Fiix Mobile CMMS (Rockwell Automation)** — Mobile maintenance app with QR scanning, photo attachments, offline synchronization, and rapid technician dispatch.
   *Source: https://www.fiixsoftware.com*
8. **IFS Cloud Mobile Work Order & Inspections** — Field Service and EAM mobile suite for field technicians with GPS verification, parts capture, and dynamic forms.
   *Source: https://www.ifs.com/solutions/capabilities/field-service-management*

---

## Feature catalog (this sub-module only)

### Mobile Inspection & Data Capture
- **Digital Inspection Checklists** — Configurable inspection templates (daily walkaround, safety checklist, pre-trip audit) with pass/fail and scoring.
  *Seen in: MaintainX, UpKeep, IBM Maximo Mobile* · *Priority: table-stakes* · *Spine: new table `MobileAssetInspection` referencing `scm.Asset`* · *Buildable now*
- **Photo & Evidence Capture** — Mobile photo attachments and document URLs documenting asset condition, leaks, and damage.
  *Seen in: MaintainX, Fiix, Asset Panda* · *Priority: table-stakes* · *Spine: fields on `MobileAssetInspection`* · *Buildable now*
- **Voice Notes & Dictation Transcription** — Field technician audio transcription notes recorded during hands-busy inspections.
  *Seen in: MaintainX, IBM Maximo Mobile* · *Priority: differentiator* · *Spine: text field on `MobileAssetInspection`* · *Buildable now*
- **Condition Scoring & Severity Grading** — Quantitative condition ratings (1-5 or Critical/Degraded/Operational) triggering follow-up maintenance.
  *Seen in: IBM Maximo Mobile, SAP SAM* · *Priority: common* · *Spine: choice fields on `MobileAssetInspection`* · *Buildable now*

### Field Technician Work Orders
- **Mobile Job Dispatch & Queue** — Technician work order queue with priority ranking, scheduled arrival window, and SLA deadlines.
  *Seen in: UpKeep, SAP SAM, IFS Cloud* · *Priority: table-stakes* · *Spine: new table `FieldWorkOrder` referencing `scm.Asset` and `core.User`* · *Buildable now*
- **Real-Time Job Status Workflow** — Step-by-step progress tracking: Dispatched -> En Route -> On-Site -> In Progress -> Completed / Paused.
  *Seen in: MaintainX, UpKeep, IFS Cloud* · *Priority: table-stakes* · *Spine: status lifecycle on `FieldWorkOrder`* · *Buildable now*
- **Field Parts & Materials Requisition** — On-site requisition of replacement parts, filters, belts, and lubricants with estimated costs.
  *Seen in: UpKeep, IBM Maximo Mobile, Fiix* · *Priority: common* · *Spine: requisition items and cost fields on `FieldWorkOrder`* · *Buildable now*
- **Digital Sign-Off & Customer/Supervisor Signature** — Verification signature capture (signee name, designation, timestamp) on completion.
  *Seen in: UpKeep, SAP SAM, MaintainX* · *Priority: common* · *Spine: signature fields on `FieldWorkOrder`* · *Buildable now*

### Barcode/RFID Scanning
- **Barcode & QR Code Lookup** — Rapid barcode/QR asset identification via device camera or scanner gun to instantly pull up history and specifications.
  *Seen in: Asset Panda, UpKeep, Fiix, MaintainX* · *Priority: table-stakes* · *Spine: new table `AssetScanLog` referencing `scm.Asset`* · *Buildable now*
- **RFID & Bluetooth Tag Ingestion** — Support for RFID EPC identifiers and Bluetooth beacon RSSI signal readings for proximity asset discovery.
  *Seen in: IBM Maximo Mobile, Asset Panda* · *Priority: differentiator* · *Spine: scanner type and payload fields on `AssetScanLog`* · *Buildable now*
- **Scan Verification & Audit Trail** — Timestamped log of every physical scan event, location fix, reader hardware, and match status (Matched, Not Found, Mismatched).
  *Seen in: Asset Panda, IBM Maximo Mobile* · *Priority: common* · *Spine: fields on `AssetScanLog`* · *Buildable now*

### GPS & Geofencing
- **Geofence Boundary Definitions** — Virtual perimeter definition (latitude, longitude, radius in meters, designated facility/yard) for high-value mobile equipment.
  *Seen in: HxGN EAM, IFS Cloud* · *Priority: common* · *Spine: new table `AssetGeofenceEvent` referencing `scm.Asset`* · *Buildable now*
- **GPS Coordinates Stamping** — Automatic geolocation capture (latitude, longitude, altitude, accuracy meters) on inspection submission and barcode scan.
  *Seen in: MaintainX, UpKeep, Asset Panda* · *Priority: table-stakes* · *Spine: GPS fields across all mobile entities* · *Buildable now*
- **Unauthorized Movement & Breach Alerts** — Automatic detection of asset exiting designated yard/perimeter, raising high-priority security alerts.
  *Seen in: HxGN EAM, IBM Maximo Mobile* · *Priority: differentiator* · *Spine: breach alert fields on `AssetGeofenceEvent`* · *Buildable now*

### Offline Synchronization
- **Client Sync UUID & Transaction Logging** — Unique client UUID generated offline, recording exact local capture timestamp before transmission.
  *Seen in: SAP SAM, IBM Maximo Mobile, MaintainX* · *Priority: table-stakes* · *Spine: offline sync metadata fields on all mobile entities* · *Buildable now*
- **Conflict Resolution & Sync Status** — Explicit sync states (`clean`, `pending_sync`, `synced_clean`, `conflict_resolved`) ensuring reliable bi-directional reconciliation.
  *Seen in: SAP SAM, MaintainX* · *Priority: common* · *Spine: choice field on all mobile entities* · *Buildable now*

---

## Recommended build scope (this pass — 4 models)

1. **`MobileAssetInspection` [MINS-]**
   - **Purpose**: Mobile digital inspection checklists, safety walkarounds, photographic proof, condition ratings, and voice-to-text notes from field personnel.
   - **Key Fields**:
     - `tenant` (FK core.Tenant), `number` (MINS-#####)
     - `title` (CharField), `inspection_type` (safety_audit, pre_trip, condition_assessment, routine_pm, breakdown_triage)
     - `asset` (FK scm.Asset), `fixed_asset` (FK accounting.FixedAsset, optional)
     - `inspector` (FK settings.AUTH_USER_MODEL)
     - `inspection_date` (DateTimeField), `scheduled_date` (DateField, optional)
     - `overall_result` (pass, conditional_pass, fail, critical_hazard)
     - `condition_rating` (1 to 5 integer or choice: excellent, good, fair, poor, scrap)
     - `checklist_data` (JSONField / structured text for checklist items & answers)
     - `meter_reading` (DecimalField, optional)
     - `photo_url` (URLField / CharField), `photo_caption` (CharField)
     - `voice_notes_transcription` (TextField)
     - `findings_summary` (TextField), `corrective_action_required` (BooleanField)
     - `gps_latitude` (DecimalField), `gps_longitude` (DecimalField), `location_accuracy_m` (FloatField)
     - `client_sync_id` (CharField/UUID), `is_offline_captured` (BooleanField), `synced_at` (DateTimeField)
     - `status` (draft, submitted, under_review, approved, rejected)
   - **Prefix**: `MINS`

2. **`FieldWorkOrder` [MFWO-]**
   - **Purpose**: Mobile field technician job dispatch, en-route / on-site status tracking, wrench-time logging, parts requisition, and customer/supervisor signoff.
   - **Key Fields**:
     - `tenant` (FK core.Tenant), `number` (MFWO-#####)
     - `title` (CharField), `work_order_type` (emergency_repair, scheduled_pm, inspection_followup, calibration, installation)
     - `priority` (low, medium, high, urgent_emergency)
     - `status` (dispatched, en_route, on_site, in_progress, paused, completed, cancelled)
     - `asset` (FK scm.Asset), `fixed_asset` (FK accounting.FixedAsset, optional)
     - `assigned_technician` (FK settings.AUTH_USER_MODEL)
     - `maintenance_request` (FK assets.AssetMaintenanceRequest, optional)
     - `scheduled_start` (DateTimeField), `scheduled_end` (DateTimeField)
     - `actual_arrival` (DateTimeField, optional), `completed_at` (DateTimeField, optional)
     - `labor_wrench_minutes` (PositiveIntegerField, default=0)
     - `parts_requisition_notes` (TextField)
     - `estimated_parts_cost` (DecimalField, default=0.00)
     - `work_performed_notes` (TextField)
     - `safety_lockout_confirmed` (BooleanField, default=False)
     - `signature_name` (CharField), `signature_designation` (CharField), `signed_at` (DateTimeField)
     - `dispatch_latitude` (DecimalField), `dispatch_longitude` (DecimalField)
     - `completion_latitude` (DecimalField), `completion_longitude` (DecimalField)
     - `client_sync_id` (CharField), `is_offline_captured` (BooleanField), `synced_at` (DateTimeField)
   - **Prefix**: `MFWO`

3. **`AssetScanLog` [ASCN-]**
   - **Purpose**: Timestamped audit trail of barcode, QR code, and RFID scans executed on mobile devices in yards, warehouses, and client sites.
   - **Key Fields**:
     - `tenant` (FK core.Tenant), `number` (ASCN-#####)
     - `scanned_by` (FK settings.AUTH_USER_MODEL)
     - `scanned_at` (DateTimeField)
     - `scan_context` (field_audit, checkout_verification, work_order_init, receiving, location_reconciliation)
     - `scan_method` (camera_barcode, camera_qr, bluetooth_rfid, handheld_laser, manual_entry)
     - `raw_payload` (CharField, e.g. barcode string or EPC hex)
     - `asset` (FK scm.Asset, null=True, blank=True)
     - `match_status` (matched, not_found, mismatched, tag_unassigned)
     - `gps_latitude` (DecimalField), `gps_longitude` (DecimalField), `gps_accuracy_m` (FloatField)
     - `device_info` (CharField, e.g. "Samsung Galaxy Tab Active / Zebra TC57")
     - `notes` (CharField)
     - `client_sync_id` (CharField), `is_offline_captured` (BooleanField)
   - **Prefix**: `ASCN`

4. **`AssetGeofenceEvent` [AGEO-]**
   - **Purpose**: Geofencing monitoring, perimeter breach tracking, and unauthorized movement alerts for mobile and yard assets.
   - **Key Fields**:
     - `tenant` (FK core.Tenant), `number` (AGEO-#####)
     - `asset` (FK scm.Asset)
     - `fence_name` (CharField, e.g. "Main Yard Perimeter", "Plant 2 Construction Zone")
     - `center_latitude` (DecimalField), `center_longitude` (DecimalField), `radius_meters` (PositiveIntegerField)
     - `recorded_latitude` (DecimalField), `recorded_longitude` (DecimalField), `recorded_accuracy_m` (FloatField)
     - `distance_from_center_m` (FloatField)
     - `event_type` (inside_perimeter, boundary_warning, perimeter_exit, perimeter_entry, unauthorized_movement)
     - `severity` (info, low, medium, high, critical)
     - `status` (open_alert, under_investigation, resolved, false_alarm)
     - `detected_at` (DateTimeField)
     - `acknowledged_by` (FK settings.AUTH_USER_MODEL, null=True, blank=True)
     - `acknowledged_at` (DateTimeField, null=True, blank=True)
     - `resolution_notes` (TextField)
   - **Prefix**: `AGEO`

---

## Belongs to sibling sub-modules (parked, not scoped here)
- **Asset Risk Assessments & Disaster Recovery Planning** -> Sub-module 11.12 Asset Risk Management
- **Total Cost of Ownership & End-of-Life Forecasting** -> Sub-module 11.14 Asset Analytics & BI
- **SCADA / IoT Telemetry Ingestion API** -> Sub-module 11.15 Integration & API Hub
- **Schematics, CAD Drawings & Manuals Repository** -> Sub-module 11.16 Document & Knowledge Management
- **Vehicle Telematics & Fuel Cards** -> Sub-module 11.19 Fleet & Vehicle Management

---

## Deferred (later passes / native integrations)
- Native iOS/Android compiled SDK wrappers (CoreBluetooth, Zebra DataWedge SDK) — web APIs (MediaDevices, Geolocation, FileReader) provide browser-native field operation today.
- Real-time WebRTC live video streaming between technician and remote expert — deferred to future communications module.

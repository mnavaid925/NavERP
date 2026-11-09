---
name: assets
description: Work on the Asset Management System (AMS / EAM) module (Module 11 — asset procurement & acquisition, physical inventory audits & cycle counts, location & spatial movement tracking, tool crib & equipment custody lending, asset loss/theft incident reporting and loss write-offs, hierarchical taxonomy classification, OEM equipment model specs, multi-criteria risk/criticality assessments, and technical specification templates). Use when the user asks to add/change/debug anything under apps/assets or templates/assets, extend the assets seeder, touch assets sidebar wiring (LIVE_LINKS 11.1, 11.2, 11.3), or invokes /assets.
---

# Asset Management System (AMS / EAM) Module (Module 11)

Comprehensive enterprise physical asset lifecycle and Enterprise Asset Management (EAM), spanning capital acquisition, physical intake inspection, balance sheet capitalization, barcode/RFID tracking, physical cycle count verification, room/bin/facility spatial movements, tool crib custody check-in/out lending, and loss/theft incident reporting with write-off authorization. Reuses the core spine (`accounting.FixedAsset`, `accounting.GLAccount`, `accounting.Currency`, `scm.PurchaseOrder`, `scm.Location`, `scm.Asset`, `core.Party`, `core.OrgUnit`).

- **App path:** `apps/assets/`
- **Templates:** `templates/assets/`
- **URL prefix:** `/assets/` (`app_name="assets"`)
- Mounted in `config/urls.py`; registered in `config/settings.py` `INSTALLED_APPS` as `apps.assets`.

---

## Sub-modules Overview

- **11.1 Asset Procurement & Acquisition**: Capital expenditure requisitions, dock intake inspection receipts, asset capitalization & CIP clearing, physical asset tagging & thermal barcode printing.
- **11.2 Asset Inventory & Tracking**: Scheduled cycle counts, wall-to-wall physical audits, discrepancy reconciliation, facility/room/bin spatial relocations, tool crib equipment check-in/out lending with electronic signatures, and lost/stolen incident reporting with loss write-offs.
- **11.3 Asset Classification & Categorization**: Hierarchies, UNSPSC taxonomy, manufacturer model specs, criticality scoring.
- **11.4 Asset Depreciation & Accounting**: Depreciation runs, revaluations, impairment testing, salvage adjustments (interconnected with Module 2 ledger).
- **11.5 Asset Maintenance & Repair**: Work orders, preventive maintenance calendars, meter readings, spare parts allocation.
- **11.6 Asset Disposal & Decommissioning**: Asset retirement, scrap, auctions, trade-ins, write-offs, gain/loss calculation.

---

## App Layout & Architecture

Backend layers follow the mandatory NavERP package structure (`models/`, `forms/`, `views/`, `urls/`):

```
apps/assets/
  models/
    _base.py                                  <- TenantOwned, TenantNumbered abstract base models
    AssetProcurement/                         <- Sub-module 11.1 models
      AssetRequisitions.py                    <- AssetRequisition [AREQ-]
      AssetAcquisitionReceipts.py             <- AssetAcquisitionReceipt [ARCV-]
      AssetCapitalizations.py                 <- AssetCapitalization [ACAP-]
      AssetTags.py                            <- AssetTag [ATAG-]
    AssetInventoryTracking/                   <- Sub-module 11.2 models
      AssetAudits.py                          <- AssetAudit [AAUD-]
      AssetMovementLogs.py                    <- AssetMovementLog [AMOV-]
      AssetCustodyLogs.py                     <- AssetCustodyLog [ACHK-]
      AssetIncidentReports.py                 <- AssetIncidentReport [AINC-]
    AssetClassification/                      <- Sub-module 11.3 models
      AssetCategories.py                      <- AssetCategory [ACAT-]
      AssetModels.py                          <- AssetModel [AMOD-]
      AssetCriticalityAssessments.py          <- AssetCriticalityAssessment [ACRT-]
      AssetSpecificationTemplates.py          <- AssetSpecificationTemplate [ASPC-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base forms, TenantUniqueMixin, reject_foreign
    AssetProcurement/                         <- Sub-module 11.1 forms
      AssetRequisitions.py                    <- AssetRequisitionForm
      AssetAcquisitionReceipts.py             <- AssetAcquisitionReceiptForm
      AssetCapitalizations.py                 <- AssetCapitalizationForm
      AssetTags.py                            <- AssetTagForm
    AssetInventoryTracking/                   <- Sub-module 11.2 forms
      AssetAudits.py                          <- AssetAuditForm
      AssetMovementLogs.py                    <- AssetMovementLogForm
      AssetCustodyLogs.py                     <- AssetCustodyLogForm
      AssetIncidentReports.py                 <- AssetIncidentReportForm
    AssetClassification/                      <- Sub-module 11.3 forms
      AssetCategories.py                      <- AssetCategoryForm
      AssetModels.py                          <- AssetModelForm
      AssetCriticalityAssessments.py          <- AssetCriticalityAssessmentForm
      AssetSpecificationTemplates.py          <- AssetSpecificationTemplateForm
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Shared helpers (assets_scope, assets_object, assets_paginate)
    overview.py                               <- Asset Management Hub overview dashboard
    AssetProcurement/                         <- Sub-module 11.1 views
      AssetRequisitions.py                    <- Requisition CRUD + submit, approve, reject
      AssetAcquisitionReceipts.py             <- Receipt CRUD + inspect, quarantine
      AssetCapitalizations.py                 <- Capitalization CRUD + execute, reverse
      AssetTags.py                            <- Tag CRUD + mark_printed, affix, verify, print_label
    AssetInventoryTracking/                   <- Sub-module 11.2 views
      AssetAudits.py                          <- Audit CRUD + start, complete, reconcile, cancel
      AssetMovementLogs.py                    <- Movement CRUD + dispatch, receive, cancel
      AssetCustodyLogs.py                     <- Custody CRUD + checkin, extend, mark_lost
      AssetIncidentReports.py                 <- Incident CRUD + investigate, resolve_recovered, authorize_write_off, close
    AssetClassification/                      <- Sub-module 11.3 views
      AssetCategories.py                      <- Category CRUD
      AssetModels.py                          <- Model CRUD
      AssetCriticalityAssessments.py          <- Criticality CRUD + approve & sync to scm.Asset
      AssetSpecificationTemplates.py          <- Spec Template CRUD
    __init__.py                               <- Re-exports all views
  urls/
    AssetProcurement/                         <- Sub-module 11.1 URL route definitions
      AssetRequisitions.py
      AssetAcquisitionReceipts.py
      AssetCapitalizations.py
      AssetTags.py
    AssetInventoryTracking/                   <- Sub-module 11.2 URL route definitions
      AssetAudits.py
      AssetMovementLogs.py
      AssetCustodyLogs.py
      AssetIncidentReports.py
    AssetClassification/                      <- Sub-module 11.3 URL route definitions
      AssetCategories.py
      AssetModels.py
      AssetCriticalityAssessments.py
      AssetSpecificationTemplates.py
    __init__.py                               <- Root URL router concatenating all packages
  management/commands/
    seed_assets.py                            <- Idempotent demonstration data seeder (11.1, 11.2 & 11.3)
  tests/
    conftest.py                               <- Shared fixtures (tenants, GL accounts, POs, locations, assets)
    test_assetprocurement_models.py           <- 11.1 Model invariants, methods, auto-numbering, constraints
    test_assetprocurement_forms.py            <- 11.1 Form validation, clean rules, mass-assignment exclusion
    test_assetprocurement_views.py            <- 11.1 View responses, filtering, guards, actions, execution
    test_assetprocurement_security.py         <- 11.1 IDOR (404), RBAC (403), method restriction (405)
    test_assetinventorytracking_models.py     <- 11.2 Model invariants, sequences, status badges, constraints
    test_assetinventorytracking_forms.py      <- 11.2 Form validation, system field exclusion, reject_foreign
    test_assetinventorytracking_views.py      <- 11.2 View context contracts, filters, lifecycle actions
    test_assetinventorytracking_security.py   <- 11.2 IDOR (404), RBAC admin gates (403), method safety (405)
    test_assetclassification_models.py        <- 11.3 Model invariants, hierarchy cycles, composite scoring
    test_assetclassification_forms.py         <- 11.3 Form validation, mass-assignment exclusions, reject_foreign
    test_assetclassification_views.py         <- 11.3 View context contracts, filters, status guards, sync
    test_assetclassification_security.py      <- 11.3 IDOR (404), RBAC gates (403), method safety (405)
```

---

## Models & Data Dictionary (11.1, 11.2, 11.3)

### 11.1 Asset Procurement
1. **`AssetRequisition`** (`AREQ-`): CapEx purchase requests with budget codes, segregation of duties approval, and PO conversion.
2. **`AssetAcquisitionReceipt`** (`ARCV-`): Dock receiving and condition inspection logging.
3. **`AssetCapitalization`** (`ACAP-`): CapEx capitalization event allocating purchase/freight/install costs into accounting FixedAsset.
4. **`AssetTag`** (`ATAG-`): Barcode/RFID physical asset tags with verification scanners.

### 11.2 Asset Inventory & Tracking
1. **`AssetAudit`** (`AAUD-`):
   - **Fields:** `number`, `title`, `audit_type` (`wall_to_wall`, `cycle_count`, `spot_check`, `annual`), `target_location` (FK `scm.Location`), `target_org_unit` (FK `core.OrgUnit`), `asset_category`, `lead_auditor` / `supervisor` (FK `User`), `scheduled_date`, `is_blind_count` (Bool), `expected_asset_count`, `scanned_asset_count`, `matched_asset_count`, `missing_asset_count`, `discrepancy_count`, `discrepancy_notes`, `reconciliation_action` (`pending_review`, `no_action_needed`, `location_updated`, `incident_initiated`, `custodian_reassigned`), `status` (`scheduled`, `in_progress`, `completed`, `reconciled`, `cancelled`).
   - **Invariants:** Discrepancy reconciliation requires `@tenant_admin_required`. Deletion restricted to uncommitted audits.
2. **`AssetMovementLog`** (`AMOV-`):
   - **Fields:** `number`, `title`, `asset` (FK `scm.Asset`), `movement_type` (`inter_facility_transfer`, `room_relocation`, `department_transfer`, `offsite_maintenance`), `from_location` / `to_location` (FK `scm.Location`), `from_org_unit` / `to_org_unit` (FK `core.OrgUnit`), `from_room_bin` / `to_room_bin`, `from_custodian` / `to_custodian` (FK `core.Party`), `gps_latitude`, `gps_longitude`, `gps_address`, `carrier_name`, `tracking_number`, `status` (`draft`, `requested`, `dispatched`, `received`, `cancelled`), `dispatch_date` / `dispatched_by`, `received_date` / `received_by`, `condition_on_receipt`.
   - **Invariants:** Receiving updates operational `scm.Asset.location` atomically. Editing restricted to `draft` and `requested` status.
3. **`AssetCustodyLog`** (`ACHK-`):
   - **Fields:** `number`, `asset` (FK `scm.Asset`), `action_type` (`checkout`, `checkin`, `permanent_assignment`, `reassignment`), `borrower` (FK `core.Party`), `borrower_name`, `crib_attendant` (FK `User`), `purpose`, `work_order_reference`, `project_reference`, `checkout_date`, `expected_return_date`, `actual_return_date`, `checkout_condition`, `return_condition`, `condition_notes`, `borrower_signature_acknowledged` (Bool), `status` (`active_loan`, `returned`, `overdue`, `damaged_returned`, `unreturned_lost`).
   - **Invariants:** View-level delete guard blocks deletion of active loans. Overdue loans auto-detected on list view with `.exists()` check.
4. **`AssetIncidentReport`** (`AINC-`):
   - **Fields:** `number`, `title`, `asset` (FK `scm.Asset`), `incident_type` (`lost`, `stolen`, `damaged_beyond_repair`, `missing_in_audit`, `vandalism`, `natural_disaster`), `severity` (`low`, `medium`, `high`, `critical`), `status` (`reported`, `under_investigation`, `confirmed_lost`, `recovered`, `write_off_pending`, `written_off`, `closed`), `resolution_action` (`pending`, `recovered`, `replacement_sourced`, `written_off`, `unresolved_closed`), `incident_date`, `last_known_location` (FK `scm.Location`), `custodian_at_loss` (FK `core.Party`), `investigator` (FK `User`), `police_report_filed`, `police_report_number`, `police_precinct`, `police_filing_date`, `insurance_claim_filed`, `insurance_carrier`, `insurance_claim_number`, `estimated_loss_value`, `insurance_claimed_amount`, `insurance_settled_amount`, `incident_description`, `investigation_findings`, `write_off_authorized_by`, `write_off_date`, `write_off_notes`.
   - **Invariants:** Write-off authorization requires `@tenant_admin_required`, sets operational `scm.Asset.status = 'disposed'`, and is guarded in UI via `request.user.is_tenant_admin`.

### 11.3 Asset Classification & Categorization
1. **`AssetCategory`** (`ACAT-`):
   - **Fields:** `code`, `name`, `parent` (FK `self`), `category_type` (`machinery`, `facility`, `vehicle`, `it_hardware`, `tooling`, `office`), `default_depreciation_method` (`straight_line`, `reducing_balance`, `units_of_production`), `default_useful_life_months`, `unspsc_code`, `iso_55000_class`, `is_active`, `description`.
   - **Invariants:** Cycle detection in `clean()` (prevents self-parenting and recursive loops), tenant isolation enforcement in hierarchy traversal, uppercase `code`.
2. **`AssetModel`** (`AMOD-`):
   - **Fields:** `model_number`, `name`, `category` (FK `AssetCategory`), `manufacturer` (FK `core.Party`), `manufacturer_name_fallback`, `estimated_replacement_cost` (non-negative `MinValueValidator`), `expected_life_years`, `warranty_duration_months`, `metering_type` (`none`, `hours`, `odometer_km`, `cycles`), `model_status` (`active`, `phase_out`, `obsolete`).
   - **Properties:** `display_manufacturer` with Party name and fallback text resolution.
3. **`AssetCriticalityAssessment`** (`ACRT-`):
   - **Fields:** `number`, `asset` (FK `scm.Asset`), `assessor` (FK `core.Party`), `assessment_date`, `production_impact`, `safety_impact`, `environmental_impact`, `regulatory_impact`, `maintenance_cost_impact` (scores 1-5), `single_point_of_failure` (Bool), `composite_score`, `abc_rating` (`A`, `B`, `C`), `assessment_status` (`draft`, `approved`, `superseded`), `approved_by` (FK `User`), `approved_at`, `notes`.
   - **Invariants:** Composite scoring with +5 SPOF bonus and auto-tier derivation. Approval requires `@tenant_admin_required`, supersedes prior approved assessments for the asset, and syncs operational `scm.Asset.criticality` (`critical`, `high`, `medium`, `low`) inside an atomic transaction. Status guards prevent edit/delete of `approved`/`superseded` records.
4. **`AssetSpecificationTemplate`** (`ASPC-`):
   - **Fields:** `number`, `category` (FK `AssetCategory`), `model` (FK `AssetModel`), `attribute_name`, `attribute_key` (snake_case slug), `data_type` (`text`, `numeric`, `boolean`, `date`, `select`), `unit_of_measure`, `min_numeric_value`, `max_numeric_value`, `validation_regex`, `select_choices`, `is_required`, `is_searchable`, `is_filterable`.
   - **Invariants:** Must attach to either Category or Model. Validates regex syntax with `re.compile()` in `clean()`. Numeric bound validation (`min <= max`).

---

## Key URLs & Routes (11.2 & 11.3)

### 11.3 Asset Classification & Categorization
Namespace: `assets:`
- **Categories:**
  - `assets:asset_category_list`: `/assets/classification/categories/`
  - `assets:asset_category_create`: `/assets/classification/categories/create/`
  - `assets:asset_category_detail`: `/assets/classification/categories/<pk>/`
  - `assets:asset_category_edit`: `/assets/classification/categories/<pk>/edit/`
  - `assets:asset_category_delete`: `/assets/classification/categories/<pk>/delete/` [POST, Admin]
- **Models:**
  - `assets:asset_model_list`: `/assets/classification/models/`
  - `assets:asset_model_create`: `/assets/classification/models/create/`
  - `assets:asset_model_detail`: `/assets/classification/models/<pk>/`
  - `assets:asset_model_edit`: `/assets/classification/models/<pk>/edit/`
  - `assets:asset_model_delete`: `/assets/classification/models/<pk>/delete/` [POST, Admin]
- **Criticality Assessments:**
  - `assets:asset_criticality_assessment_list`: `/assets/classification/criticality-assessments/`
  - `assets:asset_criticality_assessment_create`: `/assets/classification/criticality-assessments/create/`
  - `assets:asset_criticality_assessment_detail`: `/assets/classification/criticality-assessments/<pk>/`
  - `assets:asset_criticality_assessment_edit`: `/assets/classification/criticality-assessments/<pk>/edit/` [Draft only]
  - `assets:asset_criticality_assessment_delete`: `/assets/classification/criticality-assessments/<pk>/delete/` [POST, Admin, Draft only]
  - `assets:asset_criticality_assessment_approve`: `/assets/classification/criticality-assessments/<pk>/approve/` [POST, Admin]
- **Specification Templates:**
  - `assets:asset_specification_template_list`: `/assets/classification/spec-templates/`
  - `assets:asset_specification_template_create`: `/assets/classification/spec-templates/create/`
  - `assets:asset_specification_template_detail`: `/assets/classification/spec-templates/<pk>/`
  - `assets:asset_specification_template_edit`: `/assets/classification/spec-templates/<pk>/edit/`
  - `assets:asset_specification_template_delete`: `/assets/classification/spec-templates/<pk>/delete/` [POST, Admin]

---

## Key URLs & Routes (11.2)

Namespace: `assets:`
- **Audits:**
  - `assets:asset_audit_list`: `/assets/inventory-tracking/audits/`
  - `assets:asset_audit_create`: `/assets/inventory-tracking/audits/create/`
  - `assets:asset_audit_detail`: `/assets/inventory-tracking/audits/<pk>/`
  - `assets:asset_audit_edit`: `/assets/inventory-tracking/audits/<pk>/edit/`
  - `assets:asset_audit_delete`: `/assets/inventory-tracking/audits/<pk>/delete/` [POST]
  - `assets:asset_audit_start`: `/assets/inventory-tracking/audits/<pk>/start/` [POST]
  - `assets:asset_audit_complete`: `/assets/inventory-tracking/audits/<pk>/complete/` [POST]
  - `assets:asset_audit_reconcile`: `/assets/inventory-tracking/audits/<pk>/reconcile/` [POST, Admin]
  - `assets:asset_audit_cancel`: `/assets/inventory-tracking/audits/<pk>/cancel/` [POST]
- **Movements:**
  - `assets:asset_movement_log_list`: `/assets/inventory-tracking/movements/`
  - `assets:asset_movement_log_create`: `/assets/inventory-tracking/movements/create/`
  - `assets:asset_movement_log_detail`: `/assets/inventory-tracking/movements/<pk>/`
  - `assets:asset_movement_log_edit`: `/assets/inventory-tracking/movements/<pk>/edit/`
  - `assets:asset_movement_log_delete`: `/assets/inventory-tracking/movements/<pk>/delete/` [POST]
  - `assets:asset_movement_log_dispatch`: `/assets/inventory-tracking/movements/<pk>/dispatch/` [POST]
  - `assets:asset_movement_log_receive`: `/assets/inventory-tracking/movements/<pk>/receive/` [POST]
  - `assets:asset_movement_log_cancel`: `/assets/inventory-tracking/movements/<pk>/cancel/` [POST]
- **Custody Lending:**
  - `assets:asset_custody_log_list`: `/assets/inventory-tracking/custody/`
  - `assets:asset_custody_log_create`: `/assets/inventory-tracking/custody/create/`
  - `assets:asset_custody_log_detail`: `/assets/inventory-tracking/custody/<pk>/`
  - `assets:asset_custody_log_edit`: `/assets/inventory-tracking/custody/<pk>/edit/`
  - `assets:asset_custody_log_delete`: `/assets/inventory-tracking/custody/<pk>/delete/` [POST]
  - `assets:asset_custody_log_checkin`: `/assets/inventory-tracking/custody/<pk>/checkin/` [POST]
  - `assets:asset_custody_log_extend`: `/assets/inventory-tracking/custody/<pk>/extend/` [POST]
  - `assets:asset_custody_log_mark_lost`: `/assets/inventory-tracking/custody/<pk>/mark-lost/` [POST]
- **Incident Reports:**
  - `assets:asset_incident_report_list`: `/assets/inventory-tracking/incidents/`
  - `assets:asset_incident_report_create`: `/assets/inventory-tracking/incidents/create/`
  - `assets:asset_incident_report_detail`: `/assets/inventory-tracking/incidents/<pk>/`
  - `assets:asset_incident_report_edit`: `/assets/inventory-tracking/incidents/<pk>/edit/`
  - `assets:asset_incident_report_delete`: `/assets/inventory-tracking/incidents/<pk>/delete/` [POST]
  - `assets:asset_incident_report_investigate`: `/assets/inventory-tracking/incidents/<pk>/investigate/` [POST]
  - `assets:asset_incident_report_resolve_recovered`: `/assets/inventory-tracking/incidents/<pk>/resolve-recovered/` [POST]
  - `assets:asset_incident_report_authorize_write_off`: `/assets/inventory-tracking/incidents/<pk>/authorize-write-off/` [POST, Admin]
  - `assets:asset_incident_report_close`: `/assets/inventory-tracking/incidents/<pk>/close/` [POST]

---

## Conventions & Gotchas

1. **Multi-Tenancy**:
   - All models inherit from `TenantNumbered` (`TenantOwned`).
   - Every view must filter `tenant=request.tenant`.
   - Every ModelForm uses `reject_foreign(self, cleaned_data, [...])` including user ForeignKeys.
2. **Audit Logging Signature**:
   - `write_audit_log(request.user, instance, action, changes={...}, tenant=request.tenant)`.
3. **Operational Spine**:
   - Assets are tracked on `scm.Asset`. Movement receipts update `asset.location`. Loss write-offs update `asset.status = 'disposed'`. Do not create redundant asset tables.
4. **Theme CSS Classes**:
   - Badges: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`.
   - Component classes: `.table-wrap`, `.text-brand`, `.empty-state`, `.pagination`.
5. **RBAC & Privilege Separation**:
   - Audit variance reconciliation and write-off authorizations require `@tenant_admin_required`. Guard UI buttons with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
6. **Filter-Preserving Pagination**:
   - All filter parameters (`?q=`, `?status=`, `?type=`, `?location=`, `?asset=`) are strictly preserved in pagination links.

---

## Common Development Tasks

### Running Seeder
```powershell
venv\Scripts\python.exe manage.py seed_assets
```
Idempotent across all tenants. Demo login: `admin_acme` / `password`.

### Running Tests
```powershell
venv\Scripts\python.exe -m pytest apps/assets/tests/
```
Unfiltered run on SQLite in-memory test database (432 passing tests across 11.1, 11.2, and 11.3).

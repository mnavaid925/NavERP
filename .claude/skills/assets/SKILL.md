---
name: assets
description: Work on the Asset Management System (AMS / EAM) module (Module 11 — asset procurement & acquisition, requisitions, intake receipts, capitalization & depreciation setup, asset tagging & barcode registration). Use when the user asks to add/change/debug anything under apps/assets or templates/assets, extend the assets seeder, touch assets sidebar wiring (LIVE_LINKS 11.1+), or invokes /assets.
---

# Asset Management System (AMS / EAM) Module (Module 11)

Comprehensive enterprise physical asset lifecycle and Enterprise Asset Management (EAM), spanning capital acquisition, physical intake inspection, balance sheet capitalization, barcode/RFID tracking, and depreciation setup. Reuses the core spine (`accounting.FixedAsset`, `accounting.GLAccount`, `accounting.Currency`, `scm.PurchaseOrder`, `scm.Location`, `scm.Asset`, `core.Party`, `core.OrgUnit`).

- **App path:** `apps/assets/`
- **Templates:** `templates/assets/`
- **URL prefix:** `/assets/` (`app_name="assets"`)
- Mounted in `config/urls.py`; registered in `config/settings.py` `INSTALLED_APPS` as `apps.assets`.

---

## Sub-modules Overview

- **11.1 Asset Procurement & Acquisition**: Capital expenditure requisitions, dock intake inspection receipts, asset capitalization & CIP clearing, physical asset tagging & thermal barcode printing.
- **11.2 Asset Inventory & Tracking**: Physical inventory counts, audits & reconciliations, location & movement tracking, check-in/check-out custody logs, and lost/stolen incident reports.
- **11.3 Asset Operations & Maintenance**: Work orders, preventive maintenance schedules, meter readings, spare parts allocation.
- **11.4 Asset Depreciation & Accounting**: Depreciation runs, revaluations, impairment testing, salvage adjustments (interconnected with Module 2 ledger).
- **11.5 Asset Disposal & Decommissioning**: Asset retirement, scrap, auctions, trade-ins, write-offs, gain/loss calculation.

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
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base forms, TenantUniqueMixin, reject_foreign
    AssetProcurement/                         <- Sub-module 11.1 forms
      AssetRequisitions.py                    <- AssetRequisitionForm
      AssetAcquisitionReceipts.py             <- AssetAcquisitionReceiptForm
      AssetCapitalizations.py                 <- AssetCapitalizationForm
      AssetTags.py                            <- AssetTagForm
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Shared helpers (assets_scope, assets_object, assets_paginate)
    overview.py                               <- Asset Management Hub overview dashboard
    AssetProcurement/                         <- Sub-module 11.1 views
      AssetRequisitions.py                    <- Requisition CRUD + submit, approve, reject
      AssetAcquisitionReceipts.py             <- Receipt CRUD + inspect, quarantine
      AssetCapitalizations.py                 <- Capitalization CRUD + execute, reverse
      AssetTags.py                            <- Tag CRUD + mark_printed, affix, verify, print_label
    __init__.py                               <- Re-exports all views
  urls/
    AssetProcurement/                         <- Sub-module 11.1 URL route definitions
      AssetRequisitions.py
      AssetAcquisitionReceipts.py
      AssetCapitalizations.py
      AssetTags.py
    __init__.py                               <- Root URL router concatenating all packages
  management/commands/
    seed_assets.py                            <- Idempotent demonstration data seeder
  tests/
    conftest.py                               <- Shared fixtures (tenants, GL accounts, POs, locations)
    test_assetprocurement_models.py           <- Model invariants, methods, auto-numbering, constraints
    test_assetprocurement_forms.py            <- Form validation, clean rules, mass-assignment exclusion
    test_assetprocurement_views.py            <- View responses, filtering, guards, actions, execution
    test_assetprocurement_security.py         <- IDOR (404), RBAC (403), method restriction (405)
```

---

## Models & Data Dictionary (11.1)

### 1. `AssetRequisition` (`assets_requisition`)
- **Prefix:** `AREQ-YYYYMM-XXXX`
- **Fields:** `number`, `title`, `description`, `business_justification`, `asset_category` (`machinery`, `vehicle`, `it_hardware`, `office_equipment`, `facility`, `tooling`), `priority` (`low`, `medium`, `high`, `urgent`), `estimated_cost`, `currency` (FK `accounting.Currency`), `budget_code`, `proposed_vendor` (FK `core.Party`), `proposed_manufacturer`, `proposed_model`, `required_delivery_date`, `target_org_unit` (FK `core.OrgUnit`), `target_location` (FK `scm.Location`), `status` (`draft`, `pending_approval`, `approved`, `rejected`, `ordered`, `received`, `cancelled`), `submitted_by` / `submitted_at`, `approved_by` / `approved_at`, `rejection_reason`, `purchase_order` (FK `scm.PurchaseOrder`).
- **Invariants:** Submitter cannot approve their own requisition (Segregation of Duties). Edits and deletes are blocked once in `approved`, `ordered`, or `received` status.

### 2. `AssetAcquisitionReceipt` (`assets_acquisition_receipt`)
- **Prefix:** `ARCV-YYYYMM-XXXX`
- **Fields:** `number`, `title`, `requisition` (FK `assets.AssetRequisition`), `purchase_order` (FK `scm.PurchaseOrder`), `vendor` (FK `core.Party`), `manufacturer`, `model_number`, `serial_number`, `quantity_received`, `received_date`, `carrier_name`, `tracking_number`, `bill_of_lading`, `receiving_location` (FK `scm.Location`), `condition_on_arrival` (`intact`, `damaged_outer`, `damaged_internal`, `wrong_item`, `shortage`), `inspection_notes`, `status` (`pending_inspection`, `accepted`, `quarantined`, `capitalized`, `rejected`).
- **Invariants:** Delete blocked if `accepted` or `capitalized`. Edit blocked if `capitalized`.

### 3. `AssetCapitalization` (`assets_capitalization`)
- **Prefix:** `ACAP-YYYYMM-XXXX`
- **Fields:** `number`, `asset_name`, `receipt` (FK `assets.AssetAcquisitionReceipt`), `asset_category`, `purchase_cost`, `freight_cost`, `installation_cost`, `customs_duties_cost`, `other_initial_costs`, `total_cost_basis` (auto-computed sum), `salvage_value`, `useful_life_months`, `depreciation_method` (`straight_line`, `declining_balance`, `double_declining`, `units_of_production`, `sum_of_years`), `in_service_date`, `cip_gl_account` (FK `accounting.GLAccount`), `asset_gl_account` (FK `accounting.GLAccount`), `fixed_asset` (FK `accounting.FixedAsset`), `status` (`draft`, `pending_review`, `capitalized`, `reversed`), `capitalized_by` / `capitalized_at`.
- **Invariants:** Execution requires `@tenant_admin_required`, acquires row lock with `select_for_update()`, creates financial ledger `FixedAsset` record in `apps.accounting`, sets upstream receipt status to `capitalized`. Delete blocked when `capitalized`. Edit blocked when `capitalized`.

### 4. `AssetTag` (`assets_tag`)
- **Prefix:** `ATAG-YYYYMM-XXXX`
- **Fields:** `number`, `tag_code` (unique per tenant), `tag_format` (`qr_code`, `barcode_128`, `datamatrix`, `rfid_epc`, `nfc_ntag`), `operational_asset` (FK `scm.Asset`), `capitalization` (FK `assets.AssetCapitalization`), `physical_placement`, `is_verified` (Boolean), `scanner_device_id`, `status` (`pending_print`, `printed`, `affixed`, `verified`, `damaged_reissued`).
- **Invariants:** Tag code unique per tenant. Delete blocked once `affixed` or `verified`.

---

## Key URLs & Routes

Namespace: `assets:`
- **Overview:** `assets:overview` (`/assets/`)
- **Requisitions:**
  - `assets:asset_requisition_list` (`/assets/requisitions/`)
  - `assets:asset_requisition_create` (`/assets/requisitions/create/`)
  - `assets:asset_requisition_detail` (`/assets/requisitions/<pk>/`)
  - `assets:asset_requisition_edit` (`/assets/requisitions/<pk>/edit/`)
  - `assets:asset_requisition_delete` (`/assets/requisitions/<pk>/delete/`) [POST]
  - `assets:asset_requisition_submit` (`/assets/requisitions/<pk>/submit/`) [POST]
  - `assets:asset_requisition_approve` (`/assets/requisitions/<pk>/approve/`) [POST]
  - `assets:asset_requisition_reject` (`/assets/requisitions/<pk>/reject/`) [POST]
- **Receipts:**
  - `assets:asset_acquisition_receipt_list` (`/assets/receipts/`)
  - `assets:asset_acquisition_receipt_create` (`/assets/receipts/create/`)
  - `assets:asset_acquisition_receipt_detail` (`/assets/receipts/<pk>/`)
  - `assets:asset_acquisition_receipt_edit` (`/assets/receipts/<pk>/edit/`)
  - `assets:asset_acquisition_receipt_delete` (`/assets/receipts/<pk>/delete/`) [POST]
  - `assets:asset_acquisition_receipt_inspect` (`/assets/receipts/<pk>/inspect/`) [POST]
  - `assets:asset_acquisition_receipt_quarantine` (`/assets/receipts/<pk>/quarantine/`) [POST]
- **Capitalizations:**
  - `assets:asset_capitalization_list` (`/assets/capitalizations/`)
  - `assets:asset_capitalization_create` (`/assets/capitalizations/create/`)
  - `assets:asset_capitalization_detail` (`/assets/capitalizations/<pk>/`)
  - `assets:asset_capitalization_edit` (`/assets/capitalizations/<pk>/edit/`)
  - `assets:asset_capitalization_delete` (`/assets/capitalizations/<pk>/delete/`) [POST]
  - `assets:asset_capitalization_execute` (`/assets/capitalizations/<pk>/execute/`) [POST, Admin]
  - `assets:asset_capitalization_reverse` (`/assets/capitalizations/<pk>/reverse/`) [POST, Admin]
- **Tags:**
  - `assets:asset_tag_list` (`/assets/tags/`)
  - `assets:asset_tag_create` (`/assets/tags/create/`)
  - `assets:asset_tag_detail` (`/assets/tags/<pk>/`)
  - `assets:asset_tag_edit` (`/assets/tags/<pk>/edit/`)
  - `assets:asset_tag_delete` (`/assets/tags/<pk>/delete/`) [POST]
  - `assets:asset_tag_mark_printed` (`/assets/tags/<pk>/mark-printed/`) [POST]
  - `assets:asset_tag_affix` (`/assets/tags/<pk>/affix/`) [POST]
  - `assets:asset_tag_verify` (`/assets/tags/<pk>/verify/`) [POST]
  - `assets:asset_tag_print_label` (`/assets/tags/<pk>/print/`) [GET]

---

## Conventions & Gotchas

1. **Multi-Tenancy**:
   - All models inherit from `TenantNumbered` (`TenantOwned`).
   - Every view must use `assets_scope(queryset, request)` and `assets_object(Model, pk, request)`.
   - Every ModelForm uses `reject_foreign(self, cleaned_data, [...])`.
2. **Audit Logging Signature**:
   - `write_audit_log` from `apps.core.utils` takes:
     `write_audit_log(request.user, instance, action, changes={...}, tenant=request.tenant)`
   - `action` is <= 10 characters (`"create"`, `"update"`, `"delete"`). Never pass `request=request`.
3. **Segregation of Duties (SoD)**:
   - Self-approval on CapEx requisitions is prohibited at the view layer: `requisition.submitted_by_id == request.user.pk` raises a user-facing error.
4. **Financial Ledger Guard & Row Lock**:
   - Capitalization execution creates a permanent `FixedAsset` in Module 2 `accounting`.
   - Must use `select_for_update()` inside `transaction.atomic()` to prevent concurrent double-capitalizations.
   - Guarded with `@tenant_admin_required`.
5. **Theme CSS Classes**:
   - Colour-named badges only: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`. Semantic variants (`badge-success`, etc.) DO NOT EXIST.
   - Stat-icons: `blue`, `green`, `orange`, `purple`, `slate`.
6. **Form Fields Exclusion**:
   - Never expose `status`, `number`, `tenant`, `is_verified`, `scanner_device_id`, or `rejection_reason` in ModelForm inputs.
7. **Filter Preserving Pagination**:
   - All filter parameters (`?q=`, `?status=`, `?category=`, `?location=`, `?method=`, `?format=`) must be preserved across pagination links.

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
Unfiltered run on SQLite in-memory test database.

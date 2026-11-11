# Sub-module 11.13 Consolidated Review Findings — Mobile Asset Management

- **Base SHA:** `675081c875a082e71e461d2caede11963fca22c6`
- **Scope:** NavERP Sub-module 11.13 (`apps/assets/` and `templates/assets/mobileassetmanagement/`)
- **Models:** `MobileAssetInspection`, `FieldWorkOrder`, `AssetScanLog`, `AssetGeofenceEvent`
- **Review Passes:** 6 serial passes completed (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`)

---

## Action Item Register

### Critical
*None.*

---

### Important

- [ ] **I1: View/Template Context Mismatch on `work_performed_notes` in Field Work Order Detail (L7/L8)**
  - **Files**: `templates/assets/mobileassetmanagement/field_work_order/detail.html:98`
  - **Issue**: Inside `{% if work_order.work_performed_notes %}`, line 98 renders `{{ work_performed_notes }}` instead of `{{ work_order.work_performed_notes }}`, causing the technician diagnostic & remedy log to render completely blank.
  - **Fix**: Update line 98 to `{{ work_order.work_performed_notes }}`.

- [ ] **I2: User Foreign Keys Omitted from `reject_foreign` Defense-in-Depth Across All 4 Forms**
  - **Files**:
    - `apps/assets/forms/MobileAssetManagement/MobileAssetInspections.py:85` (`inspector`)
    - `apps/assets/forms/MobileAssetManagement/FieldWorkOrders.py:89` (`assigned_technician`)
    - `apps/assets/forms/MobileAssetManagement/AssetScanLogs.py:60` (`scanned_by`)
    - `apps/assets/forms/MobileAssetManagement/AssetGeofenceEvents.py:58` (`acknowledged_by`)
  - **Issue**: `reject_foreign` checks Asset, FixedAsset, and maintenance request, but omits User foreign keys.
  - **Fix**: Add `"inspector"` to `MobileAssetInspectionForm.clean`, `"assigned_technician"` to `FieldWorkOrderForm.clean`, `"scanned_by"` to `AssetScanLogForm.clean`, and `"acknowledged_by"` to `AssetGeofenceEventForm.clean`.

- [ ] **I3: Design System Violation: Undefined `badge-purple` Palette Class in Models & Templates (L33)**
  - **Files**:
    - `apps/assets/models/MobileAssetManagement/FieldWorkOrders.py:65` (`"installation": "badge-info"`)
    - `apps/assets/models/MobileAssetManagement/AssetScanLogs.py:49` (`"bluetooth_rfid": "badge-info"`)
    - `apps/assets/models/MobileAssetManagement/AssetScanLogs.py:59` (`"location_reconciliation": "badge-info"`)
    - `templates/assets/mobileassetmanagement/mobile_asset_inspection/list.html:167`
    - `templates/assets/mobileassetmanagement/mobile_asset_inspection/detail.html:165`
    - `templates/assets/mobileassetmanagement/field_work_order/detail.html:179`
    - `templates/assets/mobileassetmanagement/asset_scan_log/detail.html:154`
  - **Issue**: `badge-purple` does not exist in `static/css/theme.css` (only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate` exist).
  - **Fix**: Replace `badge-purple` with `badge-info` across model CSS dicts and templates.

- [ ] **I4: Sub-module 11.13 Models Omitted from `seed_assets --flush` Wipe Sequence**
  - **Files**: `apps/assets/management/commands/seed_assets.py:84-124`
  - **Issue**: `--flush` deletes 11.1-11.12 models but does not purge 11.13 models (`AssetGeofenceEvent`, `AssetScanLog`, `FieldWorkOrder`, `MobileAssetInspection`).
  - **Fix**: Add deletion calls for all 4 models in reverse dependency order to the flush block in `seed_assets.py`.

- [ ] **I5: Sub-module Views Package `__init__.py` Re-exports Modules Instead of View Functions**
  - **Files**:
    - `apps/assets/views/MobileAssetManagement/__init__.py:1-13`
    - `apps/assets/views/__init__.py`
  - **Issue**: Package `__init__.py` re-exported module objects instead of individual view functions.
  - **Fix**: Re-export the 20 individual view functions in `apps/assets/views/MobileAssetManagement/__init__.py` and import them cleanly in `apps/assets/views/__init__.py`.

- [ ] **I6: Missing `ProtectedError` Handling and `transaction.atomic()` in Delete Views**
  - **Files**:
    - `apps/assets/views/MobileAssetManagement/MobileAssetInspections.py:141-147`
    - `apps/assets/views/MobileAssetManagement/FieldWorkOrders.py:146-152`
    - `apps/assets/views/MobileAssetManagement/AssetScanLogs.py:142-148`
    - `apps/assets/views/MobileAssetManagement/AssetGeofenceEvents.py:141-147`
  - **Issue**: Delete views call `write_audit_log` before `delete()` without `transaction.atomic()` and lack `try...except ProtectedError` wrapping.
  - **Fix**: Wrap delete operations in `with transaction.atomic():`, catch `ProtectedError`, and set friendly error message.

- [ ] **I7: Missing Composite Indexes on `(tenant, asset)`**
  - **Files**:
    - `apps/assets/models/MobileAssetManagement/AssetScanLogs.py`
    - `apps/assets/models/MobileAssetManagement/MobileAssetInspections.py`
    - `apps/assets/models/MobileAssetManagement/FieldWorkOrders.py`
    - `apps/assets/models/MobileAssetManagement/AssetGeofenceEvents.py`
  - **Issue**: Operational asset management queries filter on `tenant` + `asset`.
  - **Fix**: Add composite indexes with names <= 30 chars (`idx_ascn_ten_asset`, `idx_mins_ten_asset`, `idx_mfwo_ten_asset`, `idx_mfwo_ten_tech`, `idx_ageo_ten_asset`).

- [ ] **I8: List Views Page Size Exceeds App-Wide Standard (25 vs 15)**
  - **Files**:
    - `apps/assets/views/MobileAssetManagement/AssetScanLogs.py:58`
    - `apps/assets/views/MobileAssetManagement/MobileAssetInspections.py:57`
    - `apps/assets/views/MobileAssetManagement/FieldWorkOrders.py:61`
    - `apps/assets/views/MobileAssetManagement/AssetGeofenceEvents.py:55`
  - **Issue**: List views specify `Paginator(qs, 25)` instead of project standard `Paginator(qs, 15)`.
  - **Fix**: Change page size to 15.

- [ ] **I9: Lifecycle Timestamps Not Set in `FieldWorkOrders` Views**
  - **Files**: `apps/assets/views/MobileAssetManagement/FieldWorkOrders.py:89-95, 129-133`
  - **Issue**: When status advances (`on_site`, `in_progress`, `completed`) or signature is provided, `actual_arrival`, `completed_at`, and `signed_at` remain null.
  - **Fix**: Auto-populate timestamps when relevant status or signature name is submitted.

---

### Minor

- [ ] **M1: Template Calls `.name` on CharField `scan.asset.category`**
  - **Files**: `templates/assets/mobileassetmanagement/asset_scan_log/detail.html:64`
  - **Fix**: Change `scan.asset.category.name` to `scan.asset.category`.

- [ ] **M2: Unused Initial Dictionary Keys in Create Views**
  - **Files**: `apps/assets/views/MobileAssetManagement/AssetGeofenceEvents.py:90`, `AssetScanLogs.py:95`
  - **Fix**: Remove unused keys (`detected_at`, `scanned_at`) from create GET initial dicts.

- [ ] **M3: Offline Records Missing Server-Side `synced_at` Stamp on Creation**
  - **Files**: `apps/assets/views/MobileAssetManagement/MobileAssetInspections.py:85-89`, `FieldWorkOrders.py:90-94`
  - **Fix**: If `is_offline_captured` is True and `synced_at` is null, set `synced_at = timezone.now()`.

- [ ] **M4: Non-Atomic Seeding in `_seed_tenant_11_13`**
  - **Files**: `apps/assets/management/commands/seed_assets.py:2738-3011`
  - **Fix**: Wrap record creation in `with transaction.atomic():`.

- [ ] **M5: Defer Heavy Unused TextFields in List View Querysets**
  - **Files**: `apps/assets/views/MobileAssetManagement/MobileAssetInspections.py:17-20`, `FieldWorkOrders.py:19-22`
  - **Fix**: Add `.defer(...)` for large TextFields not rendered in list views.

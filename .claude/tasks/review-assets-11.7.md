# Review Findings — Sub-module 11.7: Asset Reliability & Condition Monitoring (`assets`)

- **Base SHA:** `1db222f9a77b24592c4bea504c1b0bb3280f3bb0`
- **Head SHA:** `f820419b`
- **Date:** 2026-11-09
- **Status:** Consolidated & Deduplicated Findings from 6 Review Passes (Code, Explorer, Frontend, Performance, QA Smoke, Security)

---

## Critical

- [x] **C1: Nullable User ForeignKeys in template filter arguments crash with 500 when None (Lesson L10)**
  - **Location:**
    - `templates/assets/assetreliability/asset_condition_assessment/detail.html:222` (`inspector`)
    - `templates/assets/assetreliability/asset_telemetry_reading/detail.html:205` (`recorded_by`)
    - `templates/assets/assetreliability/asset_failure_mode/detail.html:224` (`assessed_by`)
    - `templates/assets/assetreliability/asset_calibration_record/detail.html:218` (`calibrated_by`)
  - **Issue:** Accessing `{{ fk.get_full_name|default:fk.username }}` raises `VariableDoesNotExist` inside the filter argument evaluation when `fk` is `None`.
  - **Fix:** Guard with `{% if fk %}{{ fk.get_full_name|default:fk.username }}{% else %}—{% endif %}` across all 4 detail templates.
  - **Status:** [x] fixed — commits `160e33ef`, `6f33e2b9`, `4f4fd79e`, `537f66c2`

- [x] **C2: Cross-Tenant Information Disclosure & IDOR: Unscoped User ForeignKeys in Forms**
  - **Location:**
    - `apps/assets/forms/AssetReliability/AssetConditionAssessments.py:19, 51-58, 62` (`inspector`)
    - `apps/assets/forms/AssetReliability/AssetTelemetryReadings.py:16, 45-47, 51` (`recorded_by`)
    - `apps/assets/forms/AssetReliability/AssetFailureModes.py:30, 56-60, 67` (`assessed_by`)
    - `apps/assets/forms/AssetReliability/AssetCalibrationRecords.py:17, 60-67, 74` (`calibrated_by`)
  - **Issue:** User foreign keys are neither filtered by `tenant=self.tenant, is_active=True` in `__init__` nor included in `reject_foreign`, leaking cross-tenant usernames in dropdowns and permitting arbitrary user assignment.
  - **Fix:** Filter User field queryset by `tenant=self.tenant, is_active=True` in `__init__` and add the field to `reject_foreign` in `clean()` across all 4 forms.
  - **Status:** [x] fixed — commits `691d19e1`, `26fe5db0`, `bb3561d4`, `7735d728`

---

## Important

- [x] **I1: Broken Access Control: Missing `@tenant_admin_required` on `asset_calibration_record_quarantine`**
  - **Location:** `apps/assets/views/AssetReliability/AssetCalibrationRecords.py:167-175`
  - **Issue:** Quarantine view is visually gated in the template with `request.user.is_tenant_admin`, but backend view only has `@login_required` and `@require_POST`. Non-admin users can directly POST and void calibration records.
  - **Fix:** Add `@tenant_admin_required` to `asset_calibration_record_quarantine`.
  - **Status:** [x] fixed — commit `afa6ed47`

- [x] **I2: Missing Authorization Gate: Delete Endpoints Lack `@tenant_admin_required`**
  - **Location:**
    - `apps/assets/views/AssetReliability/AssetConditionAssessments.py:162-169`
    - `apps/assets/views/AssetReliability/AssetTelemetryReadings.py:152-160`
    - `apps/assets/views/AssetReliability/AssetFailureModes.py:154-162`
    - `apps/assets/views/AssetReliability/AssetCalibrationRecords.py:156-164`
  - **Issue:** Destructive deletion across all 4 entities is only gated by `@login_required` and `@require_POST`, allowing any authenticated tenant employee to delete audit/reliability records.
  - **Fix:** Add `@tenant_admin_required` to all 4 delete view functions.
  - **Status:** [x] fixed — commits `8760a994`, `e18a2245`, `d890147a`, `0f7030da`

- [x] **I3: Mass Assignment: `status` Exposed in `AssetFailureModeForm`**
  - **Location:** `apps/assets/forms/AssetReliability/AssetFailureModes.py:31, 51`
  - **Issue:** `status` is in `Meta.fields`, allowing users to bypass the `@tenant_admin_required` archive transition view by submitting `status="archived"` in standard edit POSTs.
  - **Fix:** Remove `"status"` from `AssetFailureModeForm.Meta.fields` and remove its field rendering from `templates/assets/assetreliability/asset_failure_mode/form.html`.
  - **Status:** [x] fixed — commits `7a3111df`, `60eb135b`

- [x] **I4: `Party.legal_name` attribute does not exist on `core.Party` (renders blank in templates)**
  - **Location:**
    - `templates/assets/assetreliability/asset_calibration_record/list.html:78` (`{{ v.legal_name }}`)
    - `templates/assets/assetreliability/asset_calibration_record/detail.html:61` (`{{ calibration.service_vendor.legal_name }}`)
    - `templates/assets/assetreliability/asset_condition_assessment/detail.html:132` (`{{ assessment.external_inspector.legal_name }}`)
  - **Issue:** `apps.core.models.Party` uses `name`, not `legal_name`.
  - **Fix:** Replace `.legal_name` with `.name`.
  - **Status:** [x] fixed — commits `b10147c0`, `6d5c36fe`, `be138520`

- [x] **I5: `FixedAsset.asset_number` attribute does not exist on `accounting.FixedAsset` (renders blank in templates)**
  - **Location:**
    - `templates/assets/assetreliability/asset_condition_assessment/list.html:137`
    - `templates/assets/assetreliability/asset_condition_assessment/detail.html:118`
    - `templates/assets/assetreliability/asset_telemetry_reading/list.html:134`
    - `templates/assets/assetreliability/asset_telemetry_reading/detail.html:120`
    - `templates/assets/assetreliability/asset_failure_mode/detail.html:116`
    - `templates/assets/assetreliability/asset_calibration_record/detail.html:112`
  - **Issue:** `accounting.FixedAsset` inherits `TenantNumbered` where the identifier is `.number`, not `.asset_number`.
  - **Fix:** Replace `.fixed_asset.asset_number` with `.fixed_asset.number`.
  - **Status:** [x] fixed — commits `a7f416a4`, `4f6ec267`, `7b1ce019`, `ff757597`, `202f3abd`, `c4d7d5f1`

- [x] **I6: `operational_asset.asset_tag` attribute does not exist on `scm.Asset` (renders blank in templates)**
  - **Location:**
    - `templates/assets/assetreliability/asset_condition_assessment/list.html:139`
    - `templates/assets/assetreliability/asset_condition_assessment/detail.html:125`
    - `templates/assets/assetreliability/asset_telemetry_reading/list.html:136`
    - `templates/assets/assetreliability/asset_telemetry_reading/detail.html:127`
    - `templates/assets/assetreliability/asset_failure_mode/detail.html:123`
    - `templates/assets/assetreliability/asset_calibration_record/detail.html:119`
  - **Issue:** `scm.Asset` defines `tag_code` (and `number`), not `asset_tag`.
  - **Fix:** Replace `.operational_asset.asset_tag` with `.operational_asset.tag_code|default:operational_asset.number`.
  - **Status:** [x] fixed — commits `636b371c`, `9178188d`, `cf67f689`, `8d2fb21e`, `f21bf707`, `38aa477b`

- [x] **I7: Non-existent theme.css badge class `badge-purple` used for anomaly indicator (Lesson L33)**
  - **Location:**
    - `templates/assets/assetreliability/asset_telemetry_reading/list.html:174`
    - `templates/assets/assetreliability/asset_telemetry_reading/detail.html:20, 139`
  - **Issue:** `badge-purple` does not exist in `theme.css`. Renders unstyled.
  - **Fix:** Replace `badge-purple` with `badge-amber`.
  - **Status:** [x] fixed — commits `e7d69277`, `5f0e4e97`

- [x] **I8: Non-atomic multi-model mutations in trigger request workflows**
  - **Location:**
    - `apps/assets/views/AssetReliability/AssetConditionAssessments.py:218-233`
    - `apps/assets/views/AssetReliability/AssetTelemetryReadings.py:173-195`
  - **Issue:** `AssetMaintenanceRequest` creation and source model updates are not wrapped in database transactions, risking partial state and orphaned tickets.
  - **Fix:** Wrap mutations in `with transaction.atomic():`.
  - **Status:** [x] fixed — commits `e5db4070`, `95c81ef1`

- [x] **I9: Uncombined KPI queries across list views (4 roundtrips per list view instead of 1 aggregate query)**
  - **Location:** All 4 list views (`AssetConditionAssessments.py:65-70`, `AssetTelemetryReadings.py:61-65`, `AssetFailureModes.py:62-66`, `AssetCalibrationRecords.py:58-62`).
  - **Issue:** Multiple sequential `.count()` and `.filter().count()` calls per list load.
  - **Fix:** Combine into single `.aggregate(...)` queries with conditional filters.
  - **Status:** [x] fixed — commits `f76052f9`, `5139635a`, `2910c9e6`, `e66b2b4a`

- [x] **I10: Missing composite database indexes on hot filter columns and default orderings**
  - **Location:**
    - `apps/assets/models/AssetReliability/AssetConditionAssessments.py:202-207` (`idx_acas_ten_type`, `idx_acas_ten_opstat`)
    - `apps/assets/models/AssetReliability/AssetTelemetryReadings.py:189-194` (`idx_atel_ten_src`)
    - `apps/assets/models/AssetReliability/AssetCalibrationRecords.py:204-209` (`idx_acal_ten_cdate`)
  - **Issue:** Hot filter queries perform tenant-wide sequential scans or filesorts.
  - **Fix:** Add composite indexes to `Meta.indexes` (all <= 30 chars per L65) and run `makemigrations` and `migrate`.
  - **Status:** [x] fixed — commits `6a9a108a`, `a7095c98`, `6dc2694c`, `3c047369`

---

## Minor

- [x] **M1: Missing filter query parameters in pagination links across list templates**
  - **Location:**
    - `templates/assets/assetreliability/asset_condition_assessment/list.html:217, 220` (`assessment_type`, `category`, `operating_status`)
    - `templates/assets/assetreliability/asset_telemetry_reading/list.html:226, 229` (`metric_type`, `source`, `is_anomaly`)
    - `templates/assets/assetreliability/asset_failure_mode/list.html:217, 220` (`category`, `status`)
    - `templates/assets/assetreliability/asset_calibration_record/list.html:217, 220` (`vendor`, `calibration_result`)
  - **Fix:** Preserve active GET filter parameters in pagination links.
  - **Status:** [x] fixed — commits `88b114ba`, `66670b47`, `b7a025b2`, `09fc7489`

- [x] **M2: Float literal `95.0` assigned to `anomaly_confidence` DecimalField**
  - **Location:** `apps/assets/views/AssetReliability/AssetTelemetryReadings.py:208`
  - **Fix:** Use `Decimal("95.00")`.
  - **Status:** [x] fixed — commit `c170cdd8`

- [x] **M3: Unnecessary `select_related` joins in list views**
  - **Location:** `AssetFailureModes.py:23-24`, `AssetConditionAssessments.py:24-26`, `AssetTelemetryReadings.py:22-23`, `AssetCalibrationRecords.py:22-24`.
  - **Fix:** Remove unused FKs from list view `select_related`.
  - **Status:** [x] fixed — commits `8a9d0849`, `171e3e5c`, `a274d468`, `6564180d`

- [x] **M4: Divergent pagination page size (20 vs app-wide default 15)**
  - **Location:** All 4 list views in `apps/assets/views/AssetReliability/*.py`.
  - **Fix:** Change `Paginator(qs, 20)` to `Paginator(qs, 15)`.
  - **Status:** [x] fixed — commits `6de2e3d1`, `87316a27`, `0a9872c8`, `3e0d395a`

- [x] **M5: Defer unused large `TextField`s in list views**
  - **Location:** All 4 list views in `apps/assets/views/AssetReliability/*.py`.
  - **Fix:** Add `.defer(...)` to list queries for large text fields not displayed in table columns.
  - **Status:** [x] fixed — commits `97f1770b`, `78f63030`, `67303cad`, `10784a1d`

- [x] **M6: Conflicting verification text for quarantined calibration record in detail template**
  - **Location:** `templates/assets/assetreliability/asset_calibration_record/detail.html:91`
  - **Fix:** Include `quarantined` alongside `fail_out_of_tolerance` in condition.
  - **Status:** [x] fixed — commit `231e6905`

- [x] **M7: Null `deviation_percentage` gets colored green in telemetry detail**
  - **Location:** `templates/assets/assetreliability/asset_telemetry_reading/detail.html:105`
  - **Fix:** Add `is None` guard.
  - **Status:** [x] fixed — commit `64fb5bf0`

- [x] **M8: Non-directional spacing classes `ml-*` and missing `aria-label` on icon buttons**
  - **Location:** Detail, form, and list templates across `templates/assets/assetreliability/`.
  - **Fix:** Replace `ml-*` with `ms-*` and add `aria-label` to table icon buttons.
  - **Status:** [x] fixed — commits `eb62e71f`, `fe068281`, `806628ec`, `ae6aa1fa`, `0bb87a5e`, `58c15bc3`, `33ac486c`, `5a7d2420`

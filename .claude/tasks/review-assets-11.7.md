# Review Findings — Sub-module 11.7: Asset Reliability & Condition Monitoring (`assets`)

- **Base SHA:** `1db222f9a77b24592c4bea504c1b0bb3280f3bb0`
- **Head SHA:** `5d743d63c9ab340012e82ec9d9386a83b492a596`
- **Date:** 2026-11-09

---

## Pass 1: Code Reviewer Findings

### Critical
None.

### Important
- `templates/assets/assetreliability/asset_calibration_record/list.html:78` — Vendor filter dropdown displays blank option text because it references `v.legal_name` instead of `v.name` on `core.Party`. Fix: change `{{ v.legal_name }}` to `{{ v.name }}`.
- `templates/assets/assetreliability/asset_condition_assessment/list.html:137` — Template accesses `assessment.fixed_asset.asset_number` and line 139 accesses `assessment.operational_asset.asset_tag`, but `FixedAsset` uses `.number` and `scm.Asset` uses `.tag_code`. Fix: replace `.asset_number` with `.number` and `.asset_tag` with `.tag_code` (applies also to `detail.html:176,186`).
- `templates/assets/assetreliability/asset_telemetry_reading/list.html:137` — Template accesses `r.fixed_asset.asset_number` and line 139 accesses `r.operational_asset.asset_tag` which do not exist on the target models. Fix: replace `.asset_number` with `.number` and `.asset_tag` with `.tag_code` (applies also to `detail.html:181,191`).
- `templates/assets/assetreliability/asset_failure_mode/detail.html:205` — Template accesses `failure_mode.fixed_asset.asset_number` and line 215 accesses `failure_mode.operational_asset.asset_tag`. Fix: replace `.asset_number` with `.number` and `.asset_tag` with `.tag_code`.
- `templates/assets/assetreliability/asset_calibration_record/detail.html:199` — Template accesses `calibration.fixed_asset.asset_number`, line 209 accesses `calibration.operational_asset.asset_tag`, and line 225 accesses `calibration.service_vendor.legal_name`. Fix: replace `.asset_number` with `.number`, `.asset_tag` with `.tag_code`, and `.legal_name` with `.name`.
- `apps/assets/views/AssetReliability/AssetConditionAssessments.py:218` — `asset_condition_assessment_trigger_request` creates an `AssetMaintenanceRequest` and modifies the assessment record without wrapping the multi-model write in a transaction. Fix: wrap the creation and foreign key binding within `with transaction.atomic():`.
- `apps/assets/views/AssetReliability/AssetTelemetryReadings.py:173` — `asset_telemetry_reading_trigger_request` creates an `AssetMaintenanceRequest` and updates `reading.triggered_maintenance_request` without a transaction wrapper. Fix: wrap the multi-write in `with transaction.atomic():`.
- `templates/assets/assetreliability/asset_condition_assessment/detail.html:222` — Dereferencing `assessment.inspector.username` inside `default:` filter argument without an outer `{% if assessment.inspector %}` guard raises a template error when inspector is None (L10). Fix: wrap in `{% if assessment.inspector %}{{ assessment.inspector.get_full_name|default:assessment.inspector.username }}{% else %}—{% endif %}` (applies also to `telemetry_reading/detail.html:205`, `failure_mode/detail.html:224`, and `calibration_record/detail.html:218`).

### Minor
- `templates/assets/assetreliability/asset_telemetry_reading/list.html:174` — Unsupported CSS class `badge-purple` used for anomaly indicator; theme.css defines only `badge-green/red/amber/info/muted/slate`. Fix: replace `badge-purple` with `badge-info` or `badge-red` (applies also to `telemetry_reading/detail.html:20,139`).
- `apps/assets/views/AssetReliability/AssetTelemetryReadings.py:208` — Assigning float literal `95.0` to `anomaly_confidence` DecimalField. Fix: use `Decimal("95.00")`.

---

## Pass 2: Explorer Findings (Contract & Attribute Compliance)

### Critical
None.

### Important
- `templates/assets/assetreliability/asset_calibration_record/list.html:78`, `detail.html:61`, and `asset_condition_assessment/detail.html:132` — Accessing `.legal_name` on `core.Party` instead of `.name` causes blank rendering in filter options and vendor/external inspector detail fields. Fix: replace `.legal_name` with `.name`.
- `FixedAsset.asset_number` does not exist on `accounting.FixedAsset` (field is `.number`). Affects `condition_assessment/list.html:137`, `detail.html:118`, `telemetry_reading/list.html:134`, `detail.html:120`, `failure_mode/detail.html:116`, and `calibration_record/detail.html:112`. Fix: replace `.fixed_asset.asset_number` with `.fixed_asset.number`.
- `operational_asset.asset_tag` does not exist on `scm.Asset` (field is `.tag_code`). Affects `condition_assessment/list.html:139`, `detail.html:125`, `telemetry_reading/list.html:136`, `detail.html:127`, `failure_mode/detail.html:123`, and `calibration_record/detail.html:119`. Fix: replace `.operational_asset.asset_tag` with `.operational_asset.tag_code|default:assessment.operational_asset.number`.

### Minor
- `templates/assets/assetreliability/asset_condition_assessment/list.html:217,220` — Pagination query parameters omit `category`, `assessment_type`, and `operating_status`. Fix: preserve all query filters in pagination links.
- `asset_telemetry_reading/list.html`, `asset_failure_mode/list.html`, and `asset_calibration_record/list.html` — Secondary filter parameters dropped in pagination links. Fix: preserve all GET parameters in pagination links.


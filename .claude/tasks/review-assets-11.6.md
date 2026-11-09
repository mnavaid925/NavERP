# Module 11.6: Asset Performance & Utilization — Code & Architecture Review

**Target**: NavERP Sub-module 11.6: Asset Performance & Utilization (`apps/assets`)  
**Base Commit**: `1db222f9a77b24592c4bea504c1b0bb3280f3bb0`  
**Head Commit**: `82acab33d6301c8a7ec23f9dddada1eb5074e048`  

---

## 1. Code Reviewer Findings

### Critical
- **CR-C1**: `templates/assets/asset_performance/asset_downtime_log/detail.html:196` — Lesson L10 violation: `{{ log.logged_by.get_full_name|default:log.logged_by.username|default:"System" }}` raises `VariableDoesNotExist` and 500s when `log.logged_by` is `None`. Wrap with `{% if log.logged_by %}`.
- **CR-C2**: `templates/assets/asset_performance/asset_energy_reading/detail.html:199` — Lesson L10 violation: `{{ reading.recorded_by.get_full_name|default:reading.recorded_by.username|default:"System Ingestion" }}` raises `VariableDoesNotExist` and 500s when `reading.recorded_by` is `None`. Wrap with `{% if reading.recorded_by %}`.
- **CR-C3**: `templates/assets/asset_performance/asset_oee_record/detail.html:222` — Lesson L10 violation: `{{ record.recorded_by.get_full_name|default:record.recorded_by.username|default:"System" }}` raises `VariableDoesNotExist` and 500s when `record.recorded_by` is `None`. Wrap with `{% if record.recorded_by %}`.
- **CR-C4**: `templates/assets/asset_performance/asset_performance_scorecard/detail.html:224` — Lesson L10 violation: `{{ scorecard.evaluated_by.get_full_name|default:scorecard.evaluated_by.username|default:"System Evaluator" }}` raises `VariableDoesNotExist` and 500s when `scorecard.evaluated_by` is `None`. Wrap with `{% if scorecard.evaluated_by %}`.
- **CR-C5**: `templates/assets/asset_performance/asset_downtime_log/resolve.html:28` — Lesson L10 violation: `{{ log.fixed_asset.name|default:log.operational_asset.name|default:"Unassigned" }}` causes `VariableDoesNotExist` and 500s when `fixed_asset` is `None`. Use `{% if log.fixed_asset %}{{ log.fixed_asset.name }}{% elif log.operational_asset %}{{ log.operational_asset.name }}{% else %}Unassigned{% endif %}`.

### Important
- **CR-I1**: `templates/assets/asset_performance/asset_energy_reading/detail.html:148` — `reading.utility_provider.legal_name` accessed on `core.Party` where field is `name`. Utility provider renders blank. Change to `reading.utility_provider.name`.
- **CR-I2**: `apps/assets/models/AssetPerformance/AssetOeeRecords.py:230, 238` — Unhandled `None` in `calculate_oee()` during arithmetic/comparison (`operating_time_minutes`, `total_units_produced`). Coalesce to `0` before calculating.
- **CR-I3**: `apps/assets/models/AssetPerformance/AssetPerformanceScorecards.py:255, 277, 291` — Unhandled `None` in `calculate_scorecard()` during arithmetic (`actual_operating_hours`, `unplanned_downtime_hours`, `planned_downtime_hours`, `failure_event_count`, `average_oee_percentage`). Coalesce to `0`.
- **CR-I4**: `apps/assets/models/AssetPerformance/AssetDowntimeLogs.py:220` — In `calculate_duration_and_cost()`, missing `else: self.total_downtime_cost = Decimal("0.00")` leaving stale cost if hourly rate is reset to 0.
- **CR-I5**: `apps/assets/views/AssetPerformance/AssetOeeRecords.py:161-167` — Missing view status check in `asset_oee_record_finalize` (must reject if not `draft`).
- **CR-I6**: `apps/assets/views/AssetPerformance/AssetEnergyReadings.py:170-175` — Missing view status check in `asset_energy_reading_validate` (must reject if not `pending`).
- **CR-I7**: `apps/assets/views/AssetPerformance/AssetPerformanceScorecards.py:172-177` — Missing view status check in `asset_performance_scorecard_publish` (must reject if not `draft`).
- **CR-I8**: `apps/assets/forms/AssetPerformance/` — Defense-in-depth: add `"logged_by"`, `"recorded_by"`, `"evaluated_by"` to `reject_foreign` in respective forms.

### Minor
- **CR-M1**: `templates/assets/asset_performance/asset_downtime_log/list.html:59-101` — `impact_choices` passed in context and parsed in view GET filter, but dropdown missing in template filter bar.
- **CR-M2**: `apps/assets/models/AssetPerformance/` — Float casting in Decimal rounding calculations. Use `Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.
- **CR-M3**: `apps/assets/forms/AssetPerformance/AssetPerformanceScorecards.py:34` — Contract drift: `peer_category_ranking` was in contract exclusions but included in form fields.

---

## 2. Explorer / Contract Verification Findings

### Important
- **EX-I1**: `templates/assets/asset_performance/asset_energy_reading/list.html:59-103` — Contract drift: View passes `status_choices` and parses `request.GET.get("status")`, but filter bar omits `<select name="status">`. Add status dropdown to template.
- **EX-I2**: `templates/assets/asset_performance/asset_performance_scorecard/list.html:59-103` — Contract drift: View passes `status_choices` and parses `request.GET.get("status")`, but filter bar omits `<select name="status">`. Add status dropdown to template.
- **EX-I3**: `templates/assets/asset_performance/asset_energy_reading/detail.html:148` — `reading.utility_provider.legal_name` accessed on `core.Party` where field is `name`. Utility vendor name renders blank. Change to `reading.utility_provider.name`.

### Minor
- **EX-M1**: `templates/assets/asset_performance/asset_downtime_log/list.html:59-101` — Missing impact level dropdown in list filter bar and clear button.
- **EX-M2**: `apps/assets/forms/AssetPerformance/AssetPerformanceScorecards.py:34, 40-52` — Contract drift: `peer_category_ranking` was specified in form exclusions (Contract 1.4 & 2.4) but was included in `fields`. Remove from `fields` and add to `exclude`.

---

## 3. Frontend / UI Reviewer Findings

### Critical
- **FE-C1**: `templates/assets/asset_performance/asset_downtime_log/resolve.html:28` — Lesson L10 violation: `{{ log.fixed_asset.name|default:log.operational_asset.name|default:"Unassigned" }}` causes `VariableDoesNotExist` and 500 when `fixed_asset` is `None`. Use `{% if log.fixed_asset %}{{ log.fixed_asset.name }}{% elif log.operational_asset %}{{ log.operational_asset.name }}{% else %}Unassigned{% endif %}`.
- **FE-C2**: `templates/assets/asset_performance/` detail templates (`downtime:196`, `oee:222`, `energy:199`, `scorecard:224`) — Lesson L10 violation: chained user FK lookup inside `default:` filter argument (`log.logged_by.get_full_name|default:log.logged_by.username|default:"System"`). When user is `None`, raises `VariableDoesNotExist` and 500s. Wrap in explicit `{% if user %}` blocks.

### Important
- **FE-I1**: `apps/assets/models/AssetPerformance/` (`AssetDowntimeLogs:54`, `AssetEnergyReadings:50`, `AssetPerformanceScorecards:48`) — Lesson L33 / Design System violation: Non-existent badge class `badge-purple` used for `setup_changeover`, `natural_gas`, and `monthly`. `theme.css` defines only green, red, amber, info, muted, slate. Replace `badge-purple` with `badge-info`.
- **FE-I2**: `templates/assets/asset_performance/asset_energy_reading/list.html:166`, `asset_performance_scorecard/list.html:132,156` — Lesson L13: Invented utility class `text-2xs` not in theme.css or Tailwind CDN. Replace with `text-xs` or `text-[10px]`.

### Minor
- **FE-M1**: Filter clear "X" buttons in all 4 list templates lack accessibility attributes (`title="Clear filters" aria-label="Clear filters"`).
- **FE-M2**: Filter bar `<label>` elements lack `for` attributes and matching `<input>`/`<select>` `id` attributes.

---

## 4. Performance & Query Reviewer Findings

### Important
- **PR-I1**: `apps/assets/models/AssetPerformance/` (`AssetOeeRecords.py:199`, `AssetEnergyReadings.py:207`, `AssetPerformanceScorecards.py:227`) — Missing standard `(tenant, status)` compound indexes on operational models. Add `idx_aoee_ten_stat`, `idx_aeng_ten_stat`, `idx_apsc_ten_stat` to `Meta.indexes`.
- **PR-I2**: `apps/assets/models/AssetPerformance/` (`AssetDowntimeLogs.py:179`, `AssetPerformanceScorecards.py:220`) — Missing ordering compound indexes on `(tenant, -started_at)` (`idx_adwn_ten_start`) and `(tenant, -period_end)` (`idx_apsc_ten_pend`) causing filesorts on list queries.
- **PR-I3**: `apps/assets/views/AssetPerformance/AssetDowntimeLogs.py:169` — Missing `select_related=["fixed_asset", "operational_asset"]` on `assets_object` in `asset_downtime_log_resolve` view, causing lazy FK lookups when rendering `resolve.html:28`.
- **PR-I4**: `apps/assets/views/AssetPerformance/` (all 4 list views) — Unused relation joins in list querysets (`department`, `logged_by`, `recorded_by`, `utility_provider`, `work_order`, `maintenance_request`). Prune list view `select_related` to only the FKs rendered in list tables (`fixed_asset`, `operational_asset`).

### Minor
- **PR-M1**: `apps/assets/views/AssetPerformance/` (all 4 list views) — Unprojected `FixedAsset` dropdown queries loading 16 columns including TextFields. Add `.only("id", "name")` to `FixedAsset.objects.filter(...)` in list views.
- **PR-M2**: `apps/assets/views/AssetPerformance/` — `write_audit_log` triggers `str(obj)` lazy lookups in transition views without `select_related`. Specify `select_related=["fixed_asset", "operational_asset"]` in `assets_object` calls.
- **PR-M3**: `apps/assets/models/AssetPerformance/` — Missing compound indexes on `(tenant, operational_asset)` on all 4 models.

---

## 5. QA Smoke Tester Findings

### Verified Passing Runs
- All 4 list routes return HTTP 200 with valid HTML structure, no comment leaks (`{#`), and correct card KPI aggregations.
- All 4 detail routes return HTTP 200 with seeded record numbers and identifiers present.
- All 4 create views and 4 edit views return HTTP 200 with form controls properly rendered.
- Resolution view `asset_downtime_log_resolve` returns HTTP 200.
- Empty states and junk parameter filters (`?q=nonexistent&status=invalid`) return HTTP 200 without unhandled 500 exceptions.
- Cross-tenant IDOR defense: requests by Acme admin to Globex primary keys return HTTP 404 across all entities.

### Critical
- **QA-C1**: Detail templates crash with HTTP 500 when user FK fields (`logged_by`, `recorded_by`, `evaluated_by`) are `None` due to filter argument evaluation in `default:user.username` (Lesson L10).
- **QA-C2**: `asset_downtime_log/resolve.html:28` crashes with HTTP 500 if both `fixed_asset` and `operational_asset` are `None` (or when `fixed_asset` is None and `operational_asset.name` is looked up inside `default:`).

### Important
- **QA-I1**: `asset_energy_reading/detail.html:148` renders blank text for utility provider due to invalid `reading.utility_provider.legal_name` attribute lookup (should be `.name`).
- **QA-I2**: Action views (`finalize`, `validate`, `publish`) allow transitioning cancelled/archived records if accessed via direct POST due to missing view-level status preconditions.

### Minor
- **QA-M1**: Filter forms omit `status` dropdown in energy reading and performance scorecard list templates, preventing quick lifecycle status filtering.

---

## 6. Security & Multi-Tenancy Reviewer Findings

### Critical / High
- **SEC-C1**: `apps/assets/views/AssetPerformance/` (`AssetDowntimeLogs.py:168`, `AssetOeeRecords.py:161`, `AssetEnergyReadings.py:169`, `AssetPerformanceScorecards.py:171`) — Missing view-level status precondition guards on state transitions (`resolve`, `finalize`, `validate`, `publish`), allowing direct POST to transition records in cancelled/archived states. Add status validation and redirect with error.

### Important
- **SEC-I1**: `apps/assets/forms/AssetPerformance/` (`AssetDowntimeLogs.py:76`, `AssetOeeRecords.py:82`, `AssetEnergyReadings.py:81`, `AssetPerformanceScorecards.py:88`) — Cross-tenant defense-in-depth omission: user foreign key fields (`logged_by`, `recorded_by`, `evaluated_by`) are omitted from `reject_foreign`. Add them to `reject_foreign` in all 4 forms.
- **SEC-I2**: `apps/assets/forms/AssetPerformance/` (all 4 forms) — Workflow bypass via form `status` mass assignment: remove `status` from form `fields` or exclude it where appropriate to ensure state changes occur through dedicated transition views.

### Minor
- **SEC-M1**: `apps/assets/forms/AssetPerformance/AssetPerformanceScorecards.py:34` — Contract drift: `peer_category_ranking` included in `fields` instead of `exclude`.
- **SEC-M2**: `apps/assets/models/AssetPerformance/` (`AssetOeeRecords.py:230`, `AssetPerformanceScorecards.py:255`) — Unhandled `None` in arithmetic calculations can trigger `TypeError` and 500 error on save.

---

## Consolidated & Prioritized Findings Register

### Critical Findings (Must Fix Before Release)
- [x] **C1**: `templates/assets/asset_performance/asset_downtime_log/resolve.html:28` — Lesson L10: `{{ log.fixed_asset.name|default:log.operational_asset.name|default:"Unassigned" }}` causes `VariableDoesNotExist` and 500 when `fixed_asset` is None. Replace with `{% if log.fixed_asset %}{{ log.fixed_asset.name }}{% elif log.operational_asset %}{{ log.operational_asset.name }}{% else %}Unassigned{% endif %}`. (fixed: bec43879)
- [x] **C2**: `templates/assets/asset_performance/asset_downtime_log/detail.html:196` — Lesson L10: `{{ log.logged_by.get_full_name|default:log.logged_by.username|default:"System" }}` raises `VariableDoesNotExist` and 500s when `log.logged_by` is None. Wrap in `{% if log.logged_by %}{{ log.logged_by.get_full_name|default:log.logged_by.username }}{% else %}System{% endif %}`. (fixed: acfb9e33)
- [x] **C3**: `templates/assets/asset_performance/asset_oee_record/detail.html:222` — Lesson L10: `{{ record.recorded_by.get_full_name|default:record.recorded_by.username|default:"System" }}` raises `VariableDoesNotExist` and 500s when `record.recorded_by` is None. Wrap in `{% if record.recorded_by %}{{ record.recorded_by.get_full_name|default:record.recorded_by.username }}{% else %}System{% endif %}`. (fixed: 20d5d9af)
- [x] **C4**: `templates/assets/asset_performance/asset_energy_reading/detail.html:199` — Lesson L10: `{{ reading.recorded_by.get_full_name|default:reading.recorded_by.username|default:"System Ingestion" }}` raises `VariableDoesNotExist` and 500s when `reading.recorded_by` is None. Wrap in `{% if reading.recorded_by %}{{ reading.recorded_by.get_full_name|default:reading.recorded_by.username }}{% else %}System Ingestion{% endif %}`. (fixed: 9ec054a3)
- [x] **C5**: `templates/assets/asset_performance/asset_performance_scorecard/detail.html:224` — Lesson L10: `{{ scorecard.evaluated_by.get_full_name|default:scorecard.evaluated_by.username|default:"System Evaluator" }}` raises `VariableDoesNotExist` and 500s when `scorecard.evaluated_by` is None. Wrap in `{% if scorecard.evaluated_by %}{{ scorecard.evaluated_by.get_full_name|default:scorecard.evaluated_by.username }}{% else %}System Evaluator{% endif %}`. (fixed: 5ff4cf27)
- [x] **C6**: `apps/assets/views/AssetPerformance/` (`AssetDowntimeLogs.py:168`, `AssetOeeRecords.py:161`, `AssetEnergyReadings.py:169`, `AssetPerformanceScorecards.py:171`) — Missing view-level status precondition guards in state transition views (`resolve` must require `active`, `finalize` must require `draft`, `validate` must require `pending` or `flagged_anomaly`, `publish` must require `draft`). Reject with error message + redirect otherwise. (fixed: 4cc39e7e, e96c425f, 5dd77049, b4556774)

### Important Findings (High Priority)
- [x] **I1**: `templates/assets/asset_performance/asset_energy_reading/detail.html:148` — `reading.utility_provider.legal_name` accessed on `core.Party` where actual field is `name`. Utility provider renders blank. Change to `reading.utility_provider.name`. (fixed: 651697b0)
- [x] **I2**: `apps/assets/models/AssetPerformance/` (`AssetDowntimeLogs:54`, `AssetEnergyReadings:50`, `AssetPerformanceScorecards:48`) — Lesson L33: Non-existent badge class `badge-purple` used in model CSS dictionaries for `setup_changeover`, `natural_gas`, and `monthly`. `theme.css` has only green, red, amber, info, muted, slate. Replace `badge-purple` with `badge-info`. (fixed: bd6a2f30, f53af24f, 830e2765)
- [x] **I3**: `apps/assets/forms/AssetPerformance/` (`AssetDowntimeLogs.py:76`, `AssetOeeRecords.py:82`, `AssetEnergyReadings.py:81`, `AssetPerformanceScorecards.py:88`) — Defense-in-depth: add `"logged_by"`, `"recorded_by"`, `"evaluated_by"` to `reject_foreign(self, cleaned, [...])` in each form. (fixed: c1e19eb3, 790f1f55, 1b2fe6fb, 52c6e176)
- [x] **I4**: `apps/assets/models/AssetPerformance/AssetOeeRecords.py:230,238` & `AssetPerformanceScorecards.py:255,277,289` — Unhandled `None` arithmetic in `calculate_oee()` and `calculate_scorecard()`. Coalesce nullable numeric inputs with `(val or Decimal("0"))` before math. (fixed: 061ffb14, 70ed96c4)
- [x] **I5**: `apps/assets/models/AssetPerformance/AssetDowntimeLogs.py:220` — Missing `else: self.total_downtime_cost = Decimal("0.00")` when hourly cost rate is 0/None. (fixed: 4856cdfc)
- [x] **I6**: `templates/assets/asset_performance/` list templates (`asset_energy_reading/list.html`, `asset_performance_scorecard/list.html`) — Filter bar contract drift: missing `<select name="status">` dropdown for lifecycle status filtering. Add status dropdown to both templates. (fixed: 26457e2f, 52e2702a)
- [x] **I7**: `apps/assets/models/AssetPerformance/` — Missing compound indexes: add standard `(tenant, status)` (`idx_aoee_ten_stat`, `idx_aeng_ten_stat`, `idx_apsc_ten_stat`) to OEE, Energy, and Scorecard models, plus ordering indexes `(tenant, -started_at)` (`idx_adwn_ten_start`) on DowntimeLog and `(tenant, -period_end)` (`idx_apsc_ten_pend`) on Scorecard. (fixed: 9a683f1e, d7eff1a5, 188569c8, c1795b35, 20fba3fc)
- [x] **I8**: `apps/assets/views/AssetPerformance/` (all 4 list views) & `AssetDowntimeLogs.py:169` — ORM optimization: add `select_related=["fixed_asset", "operational_asset"]` to `assets_object` in `asset_downtime_log_resolve` view; prune list view `select_related` to only the FKs rendered in the list tables (`fixed_asset`, `operational_asset`). (fixed: 95e6fcf8, 5f50f026, 52ecccd5, 63358d0a)
- [x] **I9**: `templates/assets/asset_performance/asset_energy_reading/list.html:166`, `asset_performance_scorecard/list.html:132,156` — Lesson L13: Invented utility class `text-2xs` not in theme.css or Tailwind CDN. Replace with `text-xs`. (fixed: 7b4375a9, 818db534)

### Minor Findings (Quality Polish)
- [ ] **M1**: `templates/assets/asset_performance/asset_downtime_log/list.html:59-101` — Missing `impact` level dropdown in filter bar and clear filter condition.
- [ ] **M2**: `apps/assets/forms/AssetPerformance/AssetPerformanceScorecards.py:34, 40-52` — Contract drift: `peer_category_ranking` was specified in form exclusions (Contract 1.4 & 2.4). Remove from `fields` and add to `exclude`.
- [ ] **M3**: `apps/assets/views/AssetPerformance/` (all 4 list views) — Add `.only("id", "name")` to `FixedAsset.objects.filter(tenant=request.tenant)` dropdown queries in list views.
- [ ] **M4**: `templates/assets/asset_performance/` (all 4 list templates) — Filter clear "X" buttons lack accessibility attributes (`title="Clear filters" aria-label="Clear filters"`).
- [ ] **M5**: `templates/assets/asset_performance/` (all 4 list templates) — Filter bar `<label>` elements lack `for` attributes and matching `<input>`/`<select>` `id` attributes.
- [ ] **M6**: `apps/assets/models/AssetPerformance/` — Float casting in Decimal rounding calculations. Use `Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`.


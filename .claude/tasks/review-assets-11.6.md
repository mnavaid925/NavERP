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

*(Pending review pass)*

---

## 5. QA Smoke Tester Findings

*(Pending review pass)*

---

## 6. Security & Multi-Tenancy Reviewer Findings

*(Pending review pass)*

---

## Consolidated & Prioritized Findings Register

*(To be compiled after all 6 passes complete)*

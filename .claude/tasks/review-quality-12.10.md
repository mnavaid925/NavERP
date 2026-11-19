# Review Findings: Sub-module 12.10 (Calibration & Measurement System Analysis)
**Commit Range**: `e58ed9e5cac450ee54d13b851d396e1d0eed24f7...HEAD`
**Target**: Module 12.10 backend (`models/`, `forms/`, `views/`, `urls/`), admin, navigation, seeder, and templates.
**Review Passes Completed**:
1. `code-reviewer` — Pass
2. `explorer` — Pass
3. `frontend-reviewer` — Pass
4. `performance-reviewer` — Pass
5. `qa-smoke-tester` — Pass (275 checks passed, 0 runtime exceptions)
6. `security-reviewer` — Pass

---

## Consolidated & Prioritized Action Items for Phase 5 (`code-fixer`)

### Critical (0)
*None.*

---

### Important (11)

- [x] **[I1] CSV Formula Injection Neutralization**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/{CalibrationGages,CalibrationRecords,OutOfToleranceInvestigations,MeasurementSystemAnalyses}.py` and `apps/quality/views/_common.py`
  - **Issue**: User-controlled text fields exported to CSV lack formula injection neutralization (`_csv_safe`).
  - **Fix**: Define `_csv_safe(val)` in `apps/quality/views/_common.py` (prefix with `'` if starting with `=`, `+`, `-`, `@`, `\t`, `\r`) and wrap all text cells across the 4 export views. (fixed — 1615c765, 2df06fc8, 84327980, e3b3280f, ca2ceee4)

- [x] **[I2] Premature Gage State Synchronization on Draft Calibration Records**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:109-121`
  - **Issue**: `calibration_record_create` sets `gage.status = "active_in_service"`, updates `last_calibration_date`, and advances `next_calibration_due` regardless of whether `record.status` is `"completed"`.
  - **Fix**: Gate status advancement and next due date updates strictly on `record.status == "completed"`. If `overall_result == "fail_out_of_tolerance"`, set `gage.status = "quarantined_oot"`. Mirror logic in `calibration_record_edit`. (fixed — fadef000)

- [x] **[I3] Cross-Record Consistency Check in OutOfToleranceInvestigationForm**:
  - **Location**: `apps/quality/forms/CalibrationAnalysis/OutOfToleranceInvestigations.py:59-69`
  - **Issue**: Form accepts `calibration_record` and `gage` independently without verifying `calibration_record.gage_id == gage.pk`. Also misses validating `suspect_window_start <= suspect_window_end`.
  - **Fix**: In `clean()`, validate that `cal_rec.gage_id == gage.pk`, and validate `suspect_window_start <= suspect_window_end`. (fixed — bc8eb10d)

- [x] **[I4] Future Date Validation Omission in CalibrationRecordForm**:
  - **Location**: `apps/quality/forms/CalibrationAnalysis/CalibrationRecords.py:52-58`
  - **Issue**: `clean()` does not validate that `calibration_date` cannot be in the future, violating contract Section 2.2.
  - **Fix**: In `clean()`, add `if cal_date and cal_date > timezone.now().date(): self.add_error("calibration_date", "Calibration date cannot be in the future.")`. (fixed — 01e9ca78)

- [x] **[I5] Metrological Circular Dependency (Instrument Self-Parenting & Self-Calibration)**:
  - **Location**: `apps/quality/forms/CalibrationAnalysis/CalibrationGages.py:50-53, 60-69` and `apps/quality/forms/CalibrationAnalysis/CalibrationRecords.py:46-48, 52-58`
  - **Issue**: Gages can select themselves as their own `reference_standard_parent` causing infinite recursion loops, and calibrations allow selecting the gage being calibrated inside `standards_used`.
  - **Fix**: Exclude `self.instance` from `reference_standard_parent` queryset and validate in `clean()`. In `CalibrationRecordForm.clean()`, reject if `gage in standards_used`. (fixed — 83057b61, d559ee50)

- [x] **[I6] Seed Quality `--flush` Sequence Omits 12.10 Models**:
  - **Location**: `apps/quality/management/commands/seed_quality.py:99-137`
  - **Issue**: `--flush` does not delete `MeasurementSystemAnalysis`, `OutOfToleranceInvestigation`, `CalibrationRecord`, and `CalibrationGage`.
  - **Fix**: Add the 4 models to the `--flush` deletion block in reverse foreign key order. (fixed — aa8beaa6)

- [x] **[I7] Missing Subpackage `__init__.py` Files in `CalibrationAnalysis/` Folders**:
  - **Location**: `apps/quality/{models,forms,views,urls}/CalibrationAnalysis/__init__.py`
  - **Issue**: Subpackage directories lack `__init__.py` files with standard explicit `__all__` re-exports.
  - **Fix**: Create `__init__.py` in each of the 4 directories re-exporting all sub-module entities and routes. (fixed — 9a312c4d, 9344f3ec, 9950cb7d, e3da49e8)

- [x] **[I8] Chained N+1 Query via `CalibrationRecord.__str__` in `OutOfToleranceInvestigationForm`**:
  - **Location**: `apps/quality/forms/CalibrationAnalysis/OutOfToleranceInvestigations.py:50-52` and `apps/quality/models/CalibrationAnalysis/CalibrationRecords.py:153-154`
  - **Issue**: Rendering `calibration_record` dropdown stringifies each record via `self.gage.gage_id`, triggering N+1 queries.
  - **Fix**: Add `.select_related("gage")` to `calibration_record` form queryset, and add cached check in `CalibrationRecord.__str__`. (fixed — 29ec6dac, e8308a10)

- [x] **[I9] Prefetch Cache Bypass in `calibration_record_detail`**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:77-84`
  - **Issue**: Calling `.filter(tenant=request.tenant).first()` on prefetched `record.oot_investigations` issues an extra SQL query.
  - **Fix**: Retrieve from prefetched collection: `next(iter(record.oot_investigations.all()), None)`. (fixed — 2cbe1624)

- [x] **[I10] Missing `limit_choices_to={"is_reference_standard": True}` on `CalibrationRecord.standards_used`**:
  - **Location**: `apps/quality/models/CalibrationAnalysis/CalibrationRecords.py:117-119`
  - **Issue**: Model-level constraint missing on ManyToManyField for standards used.
  - **Fix**: Add `limit_choices_to={"is_reference_standard": True}` to `standards_used`. (fixed — a599eddd, a322ade4)

- [x] **[I11] Raw Unparsed LaTeX Math Delimiters in UI Markup**:
  - **Location**: `templates/quality/calibrationanalysis/measurement_system_analysis/detail.html:100, 140, 240` and `templates/quality/calibrationanalysis/calibration_record/detail.html:101, 113`
  - **Issue**: Unparsed LaTeX math delimiters (`$\sigma$`, `$6\sigma$`, `$TV^2 = GRR^2 + PV^2$`, `$R^2$`, `$U$`) render raw in templates.
  - **Fix**: Replace with semantic HTML entities (`&sigma;`, `6&sigma;`, `TV&sup2; = GRR&sup2; + PV&sup2;`, `R&sup2;`, `(U, k=2)`). (fixed — a061a22a, 187825cb)

---

### Minor (12)

- [x] **[M1] `calibration_record_list` Search Omits `service_vendor__name`**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:28-36`
  - **Fix**: Add `| Q(service_vendor__name__icontains=search_query)`. (fixed — be4c6840)

- [x] **[M2] `calibration_gage_list` Search Omits System Number (`number__icontains`)**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationGages.py:27-34`
  - **Fix**: Add `| Q(number__icontains=search_query)`. (fixed — bc072ef1)

- [x] **[M3] OOT `suspect_window_start` Initial Value Uses Failed Date Instead of Last Pass**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/OutOfToleranceInvestigations.py:101-105`
  - **Fix**: Query last passing calibration date before the failure event to set initial suspect window start. (fixed — a6528663)

- [x] **[M4] Phantom Attribute `v.legal_name` in `calibration_vendor_directory.html`**:
  - **Location**: `templates/quality/calibrationanalysis/calibration_vendor_directory.html:82-84`
  - **Fix**: Remove dead conditional check for `v.legal_name`. (fixed — 324e4f5c)

- [ ] **[M5] `CalibrationRecordAdmin` Missing `filter_horizontal` for `standards_used`**:
  - **Location**: `apps/quality/admin.py:734-750`
  - **Fix**: Add `filter_horizontal = ("standards_used",)`.

- [ ] **[M6] Missing `select_related("asset_link")` on `calibration_gage_list`**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationGages.py:23-25`
  - **Fix**: Add `"asset_link"` to `select_related`.

- [ ] **[M7] Extra Query in `out_of_tolerance_investigation_create` Initial Lookup**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/OutOfToleranceInvestigations.py:95-103`
  - **Fix**: Add `select_related("gage")` to `record` lookup.

- [ ] **[M8] Duplicate `COUNT(*)` Queries on List Views**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/{CalibrationGages,CalibrationRecords,OutOfToleranceInvestigations,MeasurementSystemAnalyses,CalibrationVendors}.py`
  - **Fix**: Evaluate `page_obj.paginator.count` instead of pre-calling `qs.count()`.

- [ ] **[M9] Separate KPI Count Queries in `calibration_gage_list` and `out_of_tolerance_investigation_list`**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/{CalibrationGages,OutOfToleranceInvestigations}.py`
  - **Fix**: Combine into a single conditional aggregate query.

- [ ] **[M10] Vendor Directory Count Scoping & Role Filter Optimization**:
  - **Location**: `apps/quality/views/CalibrationAnalysis/CalibrationVendors.py:18-23`
  - **Fix**: Simplify `Q(roles__role__in=["vendor", "supplier"])` and add explicit `filter=Q(calibrations_performed__tenant=request.tenant)` to `Count`.

- [ ] **[M11] Unrestricted Mass Assignment of `test_points_data` in `CalibrationRecordForm`**:
  - **Location**: `apps/quality/forms/CalibrationAnalysis/CalibrationRecords.py:15-18`
  - **Fix**: Add `"test_points_data"` to `Meta.exclude`.

- [ ] **[M12] Detail List Grid Responsiveness on Small Screens**:
  - **Location**: `templates/quality/calibrationanalysis/{calibration_gage,calibration_record,out_of_tolerance_investigation,measurement_system_analysis}/detail.html`
  - **Fix**: Change `<dl class="grid grid-cols-2 ...">` to `<dl class="grid grid-cols-1 sm:grid-cols-2 ...">`.

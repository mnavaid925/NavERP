# Review Findings: Sub-module 12.10 (Calibration & Measurement System Analysis)
**Commit Range**: `e58ed9e5cac450ee54d13b851d396e1d0eed24f7...HEAD`
**Target**: Module 12.10 backend (`models/`, `forms/`, `views/`, `urls/`), admin, navigation, seeder, and templates.

---

## 1. Code Reviewer Pass
- **Reviewer**: `code-reviewer`
- **Status**: Completed

### Findings
- **[CR-I1] Important**: `apps/quality/{models,forms,views,urls}/CalibrationAnalysis/__init__.py` missing explicit re-exports.
- **[CR-I2] Important**: `apps/quality/management/commands/seed_quality.py:99-137` `--flush` sequence omits 12.10 models (`CalibrationGage`, `CalibrationRecord`, `OutOfToleranceInvestigation`, `MeasurementSystemAnalysis`).
- **[CR-I3] Important**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:28-36` `calibration_record_list` search does not query `service_vendor__name`, breaking vendor directory deep link.
- **[CR-I4] Important**: CSV export views lack formula injection neutralization (`_csv_safe`).
- **[CR-I5] Important**: `apps/quality/forms/CalibrationAnalysis/CalibrationRecords.py:52-58` `CalibrationRecordForm` fails to validate that `calibration_date` cannot be in the future.
- **[CR-M1] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:109-121` Gage calibration synchronization occurs prematurely on draft/in-progress calibration records.
- **[CR-M2] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationGages.py:27-34` `calibration_gage_list` search filter omits `number__icontains`.
- **[CR-M3] Minor**: `apps/quality/forms/CalibrationAnalysis/OutOfToleranceInvestigations.py:59-69` `OutOfToleranceInvestigationForm` does not validate that `calibration_record.gage == gage`.
- **[CR-M4] Minor**: `apps/quality/views/CalibrationAnalysis/OutOfToleranceInvestigations.py:101-105` Initial `suspect_window_start` uses failed calibration date instead of the last passing in-spec calibration date.
- **[CR-M5] Minor**: `templates/quality/calibrationanalysis/calibration_vendor_directory.html:82-84` Template checks non-existent attribute `v.legal_name` on `core.Party` model.

---

## 2. Explorer Reviewer Pass
- **Reviewer**: `explorer`
- **Status**: Completed

### Findings
- **[EX-I1] Important**: `apps/quality/models/CalibrationAnalysis/CalibrationRecords.py:117-119` Missing `limit_choices_to={"is_reference_standard": True}` on `CalibrationRecord.standards_used`.
- **[EX-I2] Important**: `apps/quality/forms/CalibrationAnalysis/CalibrationRecords.py:53-58` `CalibrationRecordForm` omits future date validation.
- **[EX-I3] Important**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:109-121` Premature gage status/due-date synchronization on draft records.
- **[EX-I4] Important**: `apps/quality/management/commands/seed_quality.py:98-137` `seed_quality --flush` misses 12.10 calibration entities.
- **[EX-I5] Important**: `apps/quality/{models,forms,views,urls}/CalibrationAnalysis/` Missing subpackage `__init__.py` files.
- **[EX-M1] Minor**: `apps/quality/forms/CalibrationAnalysis/OutOfToleranceInvestigations.py:59-69` `OutOfToleranceInvestigationForm` missing cross-FK consistency check.
- **[EX-M2] Minor**: `apps/quality/views/CalibrationAnalysis/OutOfToleranceInvestigations.py:101-105` Initial `suspect_window_start` uses failed calibration date instead of last valid pass.
- **[EX-M3] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:28-36` `calibration_record_list` search omits `service_vendor__name`.
- **[EX-M4] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationGages.py:27-35` `calibration_gage_list` search omits `number__icontains`.
- **[EX-M5] Minor**: `apps/quality/views/CalibrationAnalysis/*.py` CSV export views lack formula neutralization.
- **[EX-M6] Minor**: `templates/quality/calibrationanalysis/calibration_vendor_directory.html:82-84` Dead template attribute `v.legal_name` reference on `core.Party`.
- **[EX-M7] Minor**: `apps/quality/admin.py:734-750` `CalibrationRecordAdmin` missing `filter_horizontal = ("standards_used",)`.

---

## 3. Frontend Reviewer Pass
- **Reviewer**: `frontend-reviewer`
- **Status**: Completed

### Findings
- **[FR-I1] Important**: `templates/quality/calibrationanalysis/measurement_system_analysis/detail.html:100, 140, 240` and `calibration_record/detail.html:101, 113` Raw unparsed LaTeX math syntax (`$\sigma$`, `$6\sigma$`, `$TV^2 = GRR^2 + PV^2$`, `$R^2$`, `$U$`) rendered literally in UI instead of semantic HTML entities (`&sigma;`, `6&sigma;`, `&sup2;`).
- **[FR-M1] Minor**: `templates/quality/calibrationanalysis/calibration_gage/detail.html:62`, `calibration_record/detail.html:75`, `out_of_tolerance_investigation/detail.html:68`, `measurement_system_analysis/detail.html:155` Definition lists use hardcoded `grid-cols-2` without mobile breakpoint instead of `.detail-grid` or `sm:grid-cols-2`.
- **[FR-M2] Minor**: `templates/quality/calibrationanalysis/calibration_vendor_directory.html:103` Vendor card action button `?q={{ v.name|urlencode }}` relies on backend `CalibrationRecord` search including `service_vendor__name`.

---

## 4. Performance Reviewer Pass
- **Reviewer**: `performance-reviewer`
- **Status**: Completed

### Findings
- **[PR-I1] Important**: `apps/quality/forms/CalibrationAnalysis/OutOfToleranceInvestigations.py:50-52` and `apps/quality/models/CalibrationAnalysis/CalibrationRecords.py:153-154` Chained N+1 query via `CalibrationRecord.__str__` accessing `self.gage.gage_id` during form choice rendering. Fix: add `.select_related("gage")` to form queryset and defensive check in `__str__`.
- **[PR-I2] Important**: `apps/quality/views/CalibrationAnalysis/CalibrationRecords.py:77-84` Prefetch cache bypass via `.filter(tenant=request.tenant).first()` in `calibration_record_detail`. Fix: iterate over prefetched cache `next(iter(record.oot_investigations.all()), None)`.
- **[PR-M1] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationGages.py:23-25` Missing `select_related("asset_link")` on `calibration_gage_list`.
- **[PR-M2] Minor**: `apps/quality/views/CalibrationAnalysis/OutOfToleranceInvestigations.py:95-103` Extra query in `out_of_tolerance_investigation_create` initial lookup. Fix: add `select_related("gage")`.
- **[PR-M3] Minor**: `apps/quality/views/CalibrationAnalysis/{CalibrationGages,CalibrationRecords,OutOfToleranceInvestigations,MeasurementSystemAnalyses,CalibrationVendors}.py` Duplicate `COUNT(*)` queries on list views. Fix: evaluate `page_obj.paginator.count`.
- **[PR-M4] Minor**: `apps/quality/views/CalibrationAnalysis/{CalibrationGages,OutOfToleranceInvestigations}.py` Separate KPI count queries in list views. Fix: combine into single aggregate query.
- **[PR-M5] Minor**: `apps/quality/views/CalibrationAnalysis/CalibrationVendors.py:18-23` Role filter simplification (`role__in=["vendor", "supplier"]`) and explicit tenant filter on count annotation.

---

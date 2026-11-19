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

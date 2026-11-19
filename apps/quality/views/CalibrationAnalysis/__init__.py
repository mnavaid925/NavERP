from apps.quality.views.CalibrationAnalysis.CalibrationGages import (
    calibration_gage_create,
    calibration_gage_delete,
    calibration_gage_detail,
    calibration_gage_edit,
    calibration_gage_export_csv,
    calibration_gage_list,
)
from apps.quality.views.CalibrationAnalysis.CalibrationRecords import (
    calibration_record_create,
    calibration_record_delete,
    calibration_record_detail,
    calibration_record_edit,
    calibration_record_export_csv,
    calibration_record_list,
)
from apps.quality.views.CalibrationAnalysis.CalibrationVendors import (
    calibration_vendor_directory,
)
from apps.quality.views.CalibrationAnalysis.MeasurementSystemAnalyses import (
    measurement_system_analysis_create,
    measurement_system_analysis_delete,
    measurement_system_analysis_detail,
    measurement_system_analysis_edit,
    measurement_system_analysis_export_csv,
    measurement_system_analysis_list,
)
from apps.quality.views.CalibrationAnalysis.OutOfToleranceInvestigations import (
    out_of_tolerance_investigation_create,
    out_of_tolerance_investigation_delete,
    out_of_tolerance_investigation_detail,
    out_of_tolerance_investigation_edit,
    out_of_tolerance_investigation_export_csv,
    out_of_tolerance_investigation_list,
)

__all__ = [
    "calibration_gage_list",
    "calibration_gage_detail",
    "calibration_gage_create",
    "calibration_gage_edit",
    "calibration_gage_delete",
    "calibration_gage_export_csv",
    "calibration_record_list",
    "calibration_record_detail",
    "calibration_record_create",
    "calibration_record_edit",
    "calibration_record_delete",
    "calibration_record_export_csv",
    "out_of_tolerance_investigation_list",
    "out_of_tolerance_investigation_detail",
    "out_of_tolerance_investigation_create",
    "out_of_tolerance_investigation_edit",
    "out_of_tolerance_investigation_delete",
    "out_of_tolerance_investigation_export_csv",
    "measurement_system_analysis_list",
    "measurement_system_analysis_detail",
    "measurement_system_analysis_create",
    "measurement_system_analysis_edit",
    "measurement_system_analysis_delete",
    "measurement_system_analysis_export_csv",
    "calibration_vendor_directory",
]

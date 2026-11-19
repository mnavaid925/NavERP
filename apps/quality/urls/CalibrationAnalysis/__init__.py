from apps.quality.urls.CalibrationAnalysis.CalibrationGages import (
    urlpatterns as calibration_gages_urls,
)
from apps.quality.urls.CalibrationAnalysis.CalibrationRecords import (
    urlpatterns as calibration_records_urls,
)
from apps.quality.urls.CalibrationAnalysis.CalibrationVendors import (
    urlpatterns as calibration_vendors_urls,
)
from apps.quality.urls.CalibrationAnalysis.MeasurementSystemAnalyses import (
    urlpatterns as msa_studies_urls,
)
from apps.quality.urls.CalibrationAnalysis.OutOfToleranceInvestigations import (
    urlpatterns as oot_investigations_urls,
)

urlpatterns = (
    calibration_gages_urls
    + calibration_records_urls
    + oot_investigations_urls
    + msa_studies_urls
    + calibration_vendors_urls
)

__all__ = ["urlpatterns"]

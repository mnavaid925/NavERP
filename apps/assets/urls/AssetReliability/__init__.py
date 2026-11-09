from apps.assets.urls.AssetReliability.AssetCalibrationRecords import urlpatterns as cal_patterns
from apps.assets.urls.AssetReliability.AssetConditionAssessments import urlpatterns as acas_patterns
from apps.assets.urls.AssetReliability.AssetFailureModes import urlpatterns as afma_patterns
from apps.assets.urls.AssetReliability.AssetTelemetryReadings import urlpatterns as atel_patterns

urlpatterns = acas_patterns + atel_patterns + afma_patterns + cal_patterns

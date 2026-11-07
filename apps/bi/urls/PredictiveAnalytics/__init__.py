from apps.bi.urls.PredictiveAnalytics.ForecastExecutions import (
    urlpatterns as forecast_urls,
)
from apps.bi.urls.PredictiveAnalytics.OptimizationScenarios import (
    urlpatterns as optimization_urls,
)
from apps.bi.urls.PredictiveAnalytics.PredictiveModels import (
    urlpatterns as model_urls,
)
from apps.bi.urls.PredictiveAnalytics.StatisticalAnomalies import (
    urlpatterns as anomaly_urls,
)

urlpatterns = model_urls + forecast_urls + anomaly_urls + optimization_urls

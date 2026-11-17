from apps.quality.urls.RiskManagement.FmeaMatrix import (
    urlpatterns as fmea_matrix_urls,
)
from apps.quality.urls.RiskManagement.RiskAssessments import (
    urlpatterns as risk_assessments_urls,
)
from apps.quality.urls.RiskManagement.RiskControlMeasures import (
    urlpatterns as risk_control_measures_urls,
)
from apps.quality.urls.RiskManagement.RiskManagementPlans import (
    urlpatterns as risk_management_plans_urls,
)
from apps.quality.urls.RiskManagement.RiskReviewRecords import (
    urlpatterns as risk_review_records_urls,
)

urlpatterns = (
    risk_management_plans_urls
    + risk_assessments_urls
    + risk_control_measures_urls
    + risk_review_records_urls
    + fmea_matrix_urls
)

__all__ = [
    "fmea_matrix_urls",
    "risk_assessments_urls",
    "risk_control_measures_urls",
    "risk_management_plans_urls",
    "risk_review_records_urls",
    "urlpatterns",
]

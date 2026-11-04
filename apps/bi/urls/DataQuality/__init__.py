from apps.bi.urls.DataQuality.DataQualityExceptionUrls import (
    urlpatterns as exception_urlpatterns,
)
from apps.bi.urls.DataQuality.DataQualityProfileUrls import (
    urlpatterns as profile_urlpatterns,
)
from apps.bi.urls.DataQuality.DataQualityRuleUrls import (
    urlpatterns as rule_urlpatterns,
)
from apps.bi.urls.DataQuality.DataQualityScorecardUrls import (
    urlpatterns as scorecard_urlpatterns,
)
from apps.bi.urls.DataQuality.QualityOverviewUrls import (
    urlpatterns as overview_urlpatterns,
)

urlpatterns = (
    overview_urlpatterns
    + profile_urlpatterns
    + rule_urlpatterns
    + exception_urlpatterns
    + scorecard_urlpatterns
)

__all__ = ["urlpatterns"]

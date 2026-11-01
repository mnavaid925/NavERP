from apps.ecommerce.urls.AnalyticsBi.AnalyticsCockpit import (
    urlpatterns as cockpit_patterns,
)
from apps.ecommerce.urls.AnalyticsBi.AttributionTouchpoints import (
    urlpatterns as attribution_patterns,
)
from apps.ecommerce.urls.AnalyticsBi.CustomerCohortMetrics import (
    urlpatterns as cohort_patterns,
)
from apps.ecommerce.urls.AnalyticsBi.DailySalesSnapshots import (
    urlpatterns as snapshot_patterns,
)
from apps.ecommerce.urls.AnalyticsBi.ProductMerchandisingMetrics import (
    urlpatterns as merchandising_patterns,
)

urlpatterns = (
    cockpit_patterns
    + snapshot_patterns
    + cohort_patterns
    + merchandising_patterns
    + attribution_patterns
)

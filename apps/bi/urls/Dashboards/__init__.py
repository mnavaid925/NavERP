from apps.bi.urls.Dashboards.BiDashboardBookmarkUrls import (
    urlpatterns as bookmark_urls,
)
from apps.bi.urls.Dashboards.BiDashboardCanvasUrls import (
    urlpatterns as canvas_urls,
)
from apps.bi.urls.Dashboards.BiDashboardFilterUrls import (
    urlpatterns as filter_urls,
)
from apps.bi.urls.Dashboards.BiDashboardUrls import (
    urlpatterns as dashboard_urls,
)
from apps.bi.urls.Dashboards.BiDashboardWidgetUrls import (
    urlpatterns as widget_urls,
)

urlpatterns = (
    canvas_urls
    + widget_urls
    + bookmark_urls
    + filter_urls
    + dashboard_urls
)

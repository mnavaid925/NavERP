from apps.bi.urls.SelfServiceAnalytics.AdHocCalculatedFields import (
    urlpatterns as calculated_field_urls,
)
from apps.bi.urls.SelfServiceAnalytics.AdHocQueries import (
    urlpatterns as query_urls,
)
from apps.bi.urls.SelfServiceAnalytics.DataBlendDefinitions import (
    urlpatterns as blend_urls,
)
from apps.bi.urls.SelfServiceAnalytics.SavedAnalysisViews import (
    urlpatterns as saved_view_urls,
)

urlpatterns = query_urls + calculated_field_urls + blend_urls + saved_view_urls

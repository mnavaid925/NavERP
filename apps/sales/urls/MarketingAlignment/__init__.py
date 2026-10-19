"""Sales 8.13 — MarketingAlignment URLs package re-exports."""
from apps.sales.urls.MarketingAlignment.AttributionTouchpoints import (
    urlpatterns as touchpoint_urls,
)
from apps.sales.urls.MarketingAlignment.CampaignAttributions import (
    urlpatterns as attribution_urls,
)
from apps.sales.urls.MarketingAlignment.ContentEngagements import (
    urlpatterns as engagement_urls,
)
from apps.sales.urls.MarketingAlignment.MqlHandoffs import (
    urlpatterns as handoff_urls,
)

urlpatterns = [
    *touchpoint_urls,
    *attribution_urls,
    *handoff_urls,
    *engagement_urls,
]

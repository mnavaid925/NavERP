"""Sales 8.13 — MarketingAlignment URLs package re-exports."""
from apps.sales.urls.MarketingAlignment.AttributionTouchpoints import (
    urlpatterns as touchpoint_urls,
)

urlpatterns = [
    *touchpoint_urls,
]

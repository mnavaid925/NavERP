from apps.quality.urls.RegulatorySubmissions.PostMarketSurveillanceReports import (
    urlpatterns as post_market_surveillance_reports_urls,
)
from apps.quality.urls.RegulatorySubmissions.ProductRegistrations import (
    urlpatterns as product_registrations_urls,
)
from apps.quality.urls.RegulatorySubmissions.RegulatoryCommitments import (
    urlpatterns as regulatory_commitments_urls,
)
from apps.quality.urls.RegulatorySubmissions.RegulatoryDashboard import (
    urlpatterns as regulatory_dashboard_urls,
)
from apps.quality.urls.RegulatorySubmissions.RegulatorySubmissions import (
    urlpatterns as regulatory_submissions_urls,
)

urlpatterns = (
    regulatory_dashboard_urls
    + regulatory_submissions_urls
    + product_registrations_urls
    + regulatory_commitments_urls
    + post_market_surveillance_reports_urls
)

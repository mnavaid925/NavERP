"""Sales 8.11 — CustomerSuccess URLs package re-exports."""
from apps.sales.urls.CustomerSuccess.CustomerBusinessReviews import urlpatterns as qbr_urls
from apps.sales.urls.CustomerSuccess.CustomerHealthScores import urlpatterns as health_urls
from apps.sales.urls.CustomerSuccess.CustomerOnboardings import urlpatterns as onboarding_urls
from apps.sales.urls.CustomerSuccess.CustomerRenewals import urlpatterns as renewal_urls

urlpatterns = [
    *health_urls,
    *renewal_urls,
    *onboarding_urls,
    *qbr_urls,
]

from django.urls import path

from apps.ecommerce.views.MarketingCampaign import MarketingDashboards as views

urlpatterns = [
    path("marketing/", views.marketing_dashboard, name="marketing_dashboard"),
    path("marketing/feed/social-catalog/", views.social_commerce_feed, name="social_commerce_feed"),
]

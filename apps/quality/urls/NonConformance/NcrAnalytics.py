from django.urls import path

from apps.quality.views.NonConformance import NcrAnalytics as views

urlpatterns = [
    path("analytics/", views.ncr_analytics_dashboard, name="ncr_analytics_dashboard"),
]

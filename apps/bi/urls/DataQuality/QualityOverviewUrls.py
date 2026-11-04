from django.urls import path

from apps.bi.views.DataQuality import QualityOverviewViews as views

urlpatterns = [
    path("data-quality/overview/", views.quality_overview, name="quality_overview"),
]

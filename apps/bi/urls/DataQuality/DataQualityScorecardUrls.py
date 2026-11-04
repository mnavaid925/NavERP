from django.urls import path

from apps.bi.views.DataQuality import DataQualityScorecards as views

urlpatterns = [
    path("data-quality/scorecards/", views.data_quality_scorecard_list, name="data_quality_scorecard_list"),
    path("data-quality/scorecards/create/", views.data_quality_scorecard_create, name="data_quality_scorecard_create"),
    path("data-quality/scorecards/<int:pk>/", views.data_quality_scorecard_detail, name="data_quality_scorecard_detail"),
    path("data-quality/scorecards/<int:pk>/edit/", views.data_quality_scorecard_edit, name="data_quality_scorecard_edit"),
    path("data-quality/scorecards/<int:pk>/delete/", views.data_quality_scorecard_delete, name="data_quality_scorecard_delete"),
    path("data-quality/scorecards/<int:pk>/recalculate/", views.data_quality_scorecard_recalculate, name="data_quality_scorecard_recalculate"),
]

from django.urls import path

from apps.assets.views.AssetPerformance import AssetPerformanceScorecards as views

urlpatterns = [
    path("scorecards/", views.asset_performance_scorecard_list, name="asset_performance_scorecard_list"),
    path("scorecards/create/", views.asset_performance_scorecard_create, name="asset_performance_scorecard_create"),
    path("scorecards/<int:pk>/", views.asset_performance_scorecard_detail, name="asset_performance_scorecard_detail"),
    path("scorecards/<int:pk>/edit/", views.asset_performance_scorecard_edit, name="asset_performance_scorecard_edit"),
    path("scorecards/<int:pk>/delete/", views.asset_performance_scorecard_delete, name="asset_performance_scorecard_delete"),
    path("scorecards/<int:pk>/publish/", views.asset_performance_scorecard_publish, name="asset_performance_scorecard_publish"),
]

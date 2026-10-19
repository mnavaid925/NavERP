"""Sales 8.12 — URLs for `RepPerformanceScorecard`."""
from django.urls import path

from apps.sales.views.SalesAnalytics import RepPerformanceScorecards as views

urlpatterns = [
    path("sales-analytics/scorecards/", views.rep_performance_scorecard_list, name="rep_performance_scorecard_list"),
    path("sales-analytics/scorecards/create/", views.rep_performance_scorecard_create, name="rep_performance_scorecard_create"),
    path("sales-analytics/scorecards/<int:pk>/", views.rep_performance_scorecard_detail, name="rep_performance_scorecard_detail"),
    path("sales-analytics/scorecards/<int:pk>/edit/", views.rep_performance_scorecard_edit, name="rep_performance_scorecard_edit"),
    path("sales-analytics/scorecards/<int:pk>/delete/", views.rep_performance_scorecard_delete, name="rep_performance_scorecard_delete"),
]

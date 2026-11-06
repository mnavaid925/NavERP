from django.urls import path

from apps.bi.views.PerformanceScorecards import PerformanceScorecards as views

urlpatterns = [
    path("scorecards/", views.performance_scorecard_list, name="performance_scorecard_list"),
    path("scorecards/create/", views.performance_scorecard_create, name="performance_scorecard_create"),
    path("scorecards/<int:pk>/", views.performance_scorecard_detail, name="performance_scorecard_detail"),
    path("scorecards/<int:pk>/edit/", views.performance_scorecard_edit, name="performance_scorecard_edit"),
    path("scorecards/<int:pk>/delete/", views.performance_scorecard_delete, name="performance_scorecard_delete"),
    path("scorecards/<int:pk>/recalculate/", views.performance_scorecard_recalculate, name="performance_scorecard_recalculate"),
    path("scorecards/<int:pk>/strategy-map/", views.performance_scorecard_strategy_map, name="performance_scorecard_strategy_map"),
]

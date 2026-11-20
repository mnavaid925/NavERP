from django.urls import path

from apps.quality.views.ManagementReview import QualityPlanningDashboard as views

urlpatterns = [
    path("quality-planning/", views.quality_planning_dashboard, name="quality_planning_dashboard"),
]

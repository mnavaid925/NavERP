"""Sales 8.12 — URLs for `StageVelocityAnalysis`."""
from django.urls import path

from apps.sales.views.SalesAnalytics import StageVelocityAnalyses as views

urlpatterns = [
    path("sales-analytics/stage-velocity/", views.stage_velocity_analysis_list, name="stage_velocity_analysis_list"),
    path("sales-analytics/stage-velocity/create/", views.stage_velocity_analysis_create, name="stage_velocity_analysis_create"),
    path("sales-analytics/stage-velocity/<int:pk>/", views.stage_velocity_analysis_detail, name="stage_velocity_analysis_detail"),
    path("sales-analytics/stage-velocity/<int:pk>/edit/", views.stage_velocity_analysis_edit, name="stage_velocity_analysis_edit"),
    path("sales-analytics/stage-velocity/<int:pk>/delete/", views.stage_velocity_analysis_delete, name="stage_velocity_analysis_delete"),
]

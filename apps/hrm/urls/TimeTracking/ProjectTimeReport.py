"""HRM 3.11 Time Tracking — ProjectTimeReport URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/project-time/", views.project_time_report, name="project_time_report"),
]

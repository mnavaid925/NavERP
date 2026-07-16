"""HRM 3.11 Time Tracking — UtilizationReport URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Time Tracking reports (3.11)
    path("reports/utilization/", views.timesheet_utilization_report, name="timesheet_utilization_report"),
]

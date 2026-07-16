"""HRM 3.30 Leave Reports — LeaveTrend URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/leave/trend/", views.leave_trend_report, name="leave_trend_report"),
]

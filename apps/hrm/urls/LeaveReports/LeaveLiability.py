"""HRM 3.30 Leave Reports — LeaveLiability URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/leave/liability/", views.leave_liability_report, name="leave_liability_report"),
]

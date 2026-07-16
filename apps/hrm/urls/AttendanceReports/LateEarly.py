"""HRM 3.29 Attendance Reports — LateEarly URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/attendance/late-early/", views.late_early_report, name="late_early_report"),
]

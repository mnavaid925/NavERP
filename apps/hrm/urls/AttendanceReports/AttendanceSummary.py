"""HRM 3.29 Attendance Reports — AttendanceSummary URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/attendance/summary/", views.attendance_summary_report, name="attendance_summary_report"),
]

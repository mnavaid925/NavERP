"""HRM 3.29 Attendance Reports — AttendanceIndex URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.29 Attendance Reports (derived, read-only, admin-only)
    path("reports/attendance/", views.attendance_reports_index, name="attendance_reports_index"),
]

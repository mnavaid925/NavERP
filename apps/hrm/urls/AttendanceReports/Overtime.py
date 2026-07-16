"""HRM 3.29 Attendance Reports — Overtime URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/attendance/overtime/", views.overtime_report, name="overtime_report"),
]

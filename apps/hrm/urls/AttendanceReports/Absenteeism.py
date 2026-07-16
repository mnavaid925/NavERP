"""HRM 3.29 Attendance Reports — Absenteeism URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/attendance/absenteeism/", views.absenteeism_report, name="absenteeism_report"),
]

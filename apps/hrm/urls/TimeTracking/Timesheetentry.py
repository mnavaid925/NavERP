"""HRM 3.11 Time Tracking — Timesheetentry URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("timesheet-entries/<int:pk>/edit/", views.timesheetentry_edit, name="timesheetentry_edit"),
    path("timesheet-entries/<int:pk>/delete/", views.timesheetentry_delete, name="timesheetentry_delete"),
]

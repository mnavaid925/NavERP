"""HRM 3.11 Time Tracking — Timesheet URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Timesheets (3.11) — CRUD + workflow + inline entries
    path("timesheets/", views.timesheet_list, name="timesheet_list"),
    path("timesheets/add/", views.timesheet_create, name="timesheet_create"),
    path("timesheets/<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("timesheets/<int:pk>/edit/", views.timesheet_edit, name="timesheet_edit"),
    path("timesheets/<int:pk>/delete/", views.timesheet_delete, name="timesheet_delete"),
    path("timesheets/<int:pk>/submit/", views.timesheet_submit, name="timesheet_submit"),
    path("timesheets/<int:pk>/approve/", views.timesheet_approve, name="timesheet_approve"),
    path("timesheets/<int:pk>/reject/", views.timesheet_reject, name="timesheet_reject"),
    path("timesheets/<int:pk>/cancel/", views.timesheet_cancel, name="timesheet_cancel"),
    path("timesheets/<int:ts_pk>/entries/add/", views.timesheetentry_add, name="timesheetentry_add"),
]

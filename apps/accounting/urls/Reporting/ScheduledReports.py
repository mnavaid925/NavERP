"""Accounting 2.12 Reporting & Compliance — ScheduledReports URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("scheduled-reports/", views.scheduled_report_list, name="scheduled_report_list"),
    path("scheduled-reports/add/", views.scheduled_report_create, name="scheduled_report_create"),
    path("scheduled-reports/<int:pk>/", views.scheduled_report_detail, name="scheduled_report_detail"),
    path("scheduled-reports/<int:pk>/edit/", views.scheduled_report_edit, name="scheduled_report_edit"),
    path("scheduled-reports/<int:pk>/delete/", views.scheduled_report_delete, name="scheduled_report_delete"),
]

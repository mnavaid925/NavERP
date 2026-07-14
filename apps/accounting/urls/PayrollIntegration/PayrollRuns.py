"""Accounting 2.8 Payroll Integration — PayrollRuns URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.8 Payroll
    path("payroll-runs/", views.payroll_run_list, name="payroll_run_list"),
    path("payroll-runs/add/", views.payroll_run_create, name="payroll_run_create"),
    path("payroll-runs/<int:pk>/", views.payroll_run_detail, name="payroll_run_detail"),
    path("payroll-runs/<int:pk>/edit/", views.payroll_run_edit, name="payroll_run_edit"),
    path("payroll-runs/<int:pk>/delete/", views.payroll_run_delete, name="payroll_run_delete"),
    path("payroll-runs/<int:pk>/post/", views.payroll_run_post, name="payroll_run_post"),
]

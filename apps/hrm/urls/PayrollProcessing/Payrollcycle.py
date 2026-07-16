"""HRM 3.14 Payroll Processing — Payrollcycle URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Payroll Cycles (3.14 Payroll Processing)
    path("payroll-cycles/", views.payrollcycle_list, name="payrollcycle_list"),
    path("payroll-cycles/add/", views.payrollcycle_create, name="payrollcycle_create"),
    path("payroll-cycles/<int:pk>/", views.payrollcycle_detail, name="payrollcycle_detail"),
    path("payroll-cycles/<int:pk>/edit/", views.payrollcycle_edit, name="payrollcycle_edit"),
    path("payroll-cycles/<int:pk>/delete/", views.payrollcycle_delete, name="payrollcycle_delete"),
    path("payroll-cycles/<int:pk>/generate/", views.payrollcycle_generate, name="payrollcycle_generate"),
    path("payroll-cycles/<int:pk>/submit/", views.payrollcycle_submit, name="payrollcycle_submit"),
    path("payroll-cycles/<int:pk>/approve/", views.payrollcycle_approve, name="payrollcycle_approve"),
    path("payroll-cycles/<int:pk>/reject/", views.payrollcycle_reject, name="payrollcycle_reject"),
    path("payroll-cycles/<int:pk>/lock/", views.payrollcycle_lock, name="payrollcycle_lock"),
]

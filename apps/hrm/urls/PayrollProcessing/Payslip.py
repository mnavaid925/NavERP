"""HRM 3.14 Payroll Processing — Payslip URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Payslips (3.14)
    path("payslips/", views.payslip_list, name="payslip_list"),
    path("payslips/<int:pk>/", views.payslip_detail, name="payslip_detail"),
    path("payslips/<int:pk>/edit/", views.payslip_edit, name="payslip_edit"),
    path("payslips/<int:pk>/hold/", views.payslip_hold, name="payslip_hold"),
    path("payslips/<int:pk>/release/", views.payslip_release, name="payslip_release"),
]

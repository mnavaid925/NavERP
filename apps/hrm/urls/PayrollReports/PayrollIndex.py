"""HRM 3.31 Payroll Reports — PayrollIndex URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.31 Payroll Reports (derived, read-only, admin-only)
    path("reports/payroll/", views.payroll_reports_index, name="payroll_reports_index"),
]

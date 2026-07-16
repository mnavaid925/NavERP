"""HRM 3.31 Payroll Reports — Tax URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/payroll/tax/", views.tax_report, name="tax_report"),
]

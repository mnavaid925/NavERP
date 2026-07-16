"""HRM 3.31 Payroll Reports — Statutory URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/payroll/statutory/", views.statutory_report, name="statutory_report"),
]

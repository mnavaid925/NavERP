"""HRM 3.31 Payroll Reports — Ctc URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/payroll/ctc/", views.ctc_report, name="ctc_report"),
]

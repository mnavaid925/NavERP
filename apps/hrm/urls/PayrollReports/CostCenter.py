"""HRM 3.31 Payroll Reports — CostCenter URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/payroll/cost-center/", views.cost_center_report, name="cost_center_report"),
]

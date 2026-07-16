"""HRM 3.31 Payroll Reports — SalaryRegister URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("reports/payroll/salary-register/", views.salary_register_report, name="salary_register_report"),
]

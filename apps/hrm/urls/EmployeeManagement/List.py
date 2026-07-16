"""HRM 3.1 Employee Management — List URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Employees (3.1)
    path("employees/", views.employee_list, name="employee_list"),
]

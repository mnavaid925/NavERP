"""HRM 3.13 Salary Structure — Employeesalarystructure URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Employee Salary Structures (3.13)
    path("employee-salary/", views.employeesalarystructure_list, name="employeesalarystructure_list"),
    path("employee-salary/add/", views.employeesalarystructure_create, name="employeesalarystructure_create"),
    path("employee-salary/<int:pk>/", views.employeesalarystructure_detail, name="employeesalarystructure_detail"),
    path("employee-salary/<int:pk>/edit/", views.employeesalarystructure_edit, name="employeesalarystructure_edit"),
    path("employee-salary/<int:pk>/delete/", views.employeesalarystructure_delete, name="employeesalarystructure_delete"),
]

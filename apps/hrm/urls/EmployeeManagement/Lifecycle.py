"""HRM 3.1 Employee Management — Lifecycle URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Employee Lifecycle Events (3.1 — dated job-history timeline) — CRUD
    path("lifecycle-events/", views.employee_lifecycle_list, name="employee_lifecycle_list"),
    path("lifecycle-events/add/", views.employee_lifecycle_create, name="employee_lifecycle_create"),
    path("lifecycle-events/<int:pk>/", views.employee_lifecycle_detail, name="employee_lifecycle_detail"),
    path("lifecycle-events/<int:pk>/edit/", views.employee_lifecycle_edit, name="employee_lifecycle_edit"),
    path("lifecycle-events/<int:pk>/delete/", views.employee_lifecycle_delete, name="employee_lifecycle_delete"),
]

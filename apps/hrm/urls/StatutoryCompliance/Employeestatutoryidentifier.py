"""HRM 3.15 Statutory Compliance — Employeestatutoryidentifier URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Per-employee statutory identifiers (UAN / PF / ESI) — CRUD
    path("statutory-identifiers/", views.employeestatutoryidentifier_list, name="employeestatutoryidentifier_list"),
    path("statutory-identifiers/add/", views.employeestatutoryidentifier_create, name="employeestatutoryidentifier_create"),
    path("statutory-identifiers/<int:pk>/", views.employeestatutoryidentifier_detail, name="employeestatutoryidentifier_detail"),
    path("statutory-identifiers/<int:pk>/edit/", views.employeestatutoryidentifier_edit, name="employeestatutoryidentifier_edit"),
    path("statutory-identifiers/<int:pk>/delete/", views.employeestatutoryidentifier_delete, name="employeestatutoryidentifier_delete"),
]

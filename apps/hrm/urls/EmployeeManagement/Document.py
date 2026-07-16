"""HRM 3.1 Employee Management — Document URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Employee Documents (3.1 — personnel-file vault) — CRUD + verify/reject
    path("employee-documents/", views.employee_document_list, name="employee_document_list"),
    path("employee-documents/add/", views.employee_document_create, name="employee_document_create"),
    path("employee-documents/<int:pk>/", views.employee_document_detail, name="employee_document_detail"),
    path("employee-documents/<int:pk>/edit/", views.employee_document_edit, name="employee_document_edit"),
    path("employee-documents/<int:pk>/delete/", views.employee_document_delete, name="employee_document_delete"),
    path("employee-documents/<int:pk>/verify/", views.employee_document_mark_verified, name="employee_document_mark_verified"),
    path("employee-documents/<int:pk>/reject/", views.employee_document_reject, name="employee_document_reject"),
]

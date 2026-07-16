"""HRM 3.2 Organizational Structure — Designation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Designations (3.2)
    path("designations/", views.designation_list, name="designation_list"),
    path("designations/add/", views.designation_create, name="designation_create"),
    path("designations/<int:pk>/", views.designation_detail, name="designation_detail"),
    path("designations/<int:pk>/edit/", views.designation_edit, name="designation_edit"),
    path("designations/<int:pk>/delete/", views.designation_delete, name="designation_delete"),
]

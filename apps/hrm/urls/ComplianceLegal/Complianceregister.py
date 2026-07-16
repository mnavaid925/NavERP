"""HRM 3.39 Compliance & Legal — Complianceregister URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compliance/registers/", views.complianceregister_list, name="complianceregister_list"),
    path("compliance/registers/add/", views.complianceregister_create, name="complianceregister_create"),
    path("compliance/registers/<int:pk>/", views.complianceregister_detail, name="complianceregister_detail"),
    path("compliance/registers/<int:pk>/edit/", views.complianceregister_edit, name="complianceregister_edit"),
    path("compliance/registers/<int:pk>/delete/", views.complianceregister_delete, name="complianceregister_delete"),
]

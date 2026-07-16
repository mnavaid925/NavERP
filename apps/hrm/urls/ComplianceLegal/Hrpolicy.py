"""HRM 3.39 Compliance & Legal — Hrpolicy URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compliance/policies/", views.hrpolicy_list, name="hrpolicy_list"),
    path("compliance/policies/add/", views.hrpolicy_create, name="hrpolicy_create"),
    path("compliance/policies/<int:pk>/", views.hrpolicy_detail, name="hrpolicy_detail"),
    path("compliance/policies/<int:pk>/edit/", views.hrpolicy_edit, name="hrpolicy_edit"),
    path("compliance/policies/<int:pk>/delete/", views.hrpolicy_delete, name="hrpolicy_delete"),
    path("compliance/policies/<int:pk>/publish/", views.hrpolicy_publish, name="hrpolicy_publish"),
]

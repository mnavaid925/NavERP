"""HRM 3.39 Compliance & Legal — Employmentcontract URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # 3.39 Compliance & Legal (Disciplinary Actions reuses the 3.21 warningletter_* routes)
    path("compliance/contracts/", views.employmentcontract_list, name="employmentcontract_list"),
    path("compliance/contracts/add/", views.employmentcontract_create, name="employmentcontract_create"),
    path("compliance/contracts/<int:pk>/", views.employmentcontract_detail, name="employmentcontract_detail"),
    path("compliance/contracts/<int:pk>/edit/", views.employmentcontract_edit, name="employmentcontract_edit"),
    path("compliance/contracts/<int:pk>/delete/", views.employmentcontract_delete, name="employmentcontract_delete"),
]

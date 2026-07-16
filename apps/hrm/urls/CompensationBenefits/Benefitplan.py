"""HRM 3.37 Compensation & Benefits — Benefitplan URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compensation/benefit-plans/", views.benefitplan_list, name="benefitplan_list"),
    path("compensation/benefit-plans/add/", views.benefitplan_create, name="benefitplan_create"),
    path("compensation/benefit-plans/<int:pk>/", views.benefitplan_detail, name="benefitplan_detail"),
    path("compensation/benefit-plans/<int:pk>/edit/", views.benefitplan_edit, name="benefitplan_edit"),
    path("compensation/benefit-plans/<int:pk>/delete/", views.benefitplan_delete, name="benefitplan_delete"),
]

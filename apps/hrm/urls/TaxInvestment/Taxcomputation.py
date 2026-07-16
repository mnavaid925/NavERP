"""HRM 3.16 Tax & Investment — Taxcomputation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Tax computations — CRUD + recompute engine + Form 16 tie-in + Part B report
    path("tax-computations/", views.taxcomputation_list, name="taxcomputation_list"),
    path("tax-computations/add/", views.taxcomputation_create, name="taxcomputation_create"),
    path("tax-computations/<int:pk>/", views.taxcomputation_detail, name="taxcomputation_detail"),
    path("tax-computations/<int:pk>/edit/", views.taxcomputation_edit, name="taxcomputation_edit"),
    path("tax-computations/<int:pk>/delete/", views.taxcomputation_delete, name="taxcomputation_delete"),
    path("tax-computations/<int:pk>/generate/", views.taxcomputation_generate, name="taxcomputation_generate"),
    path("tax-computations/<int:pk>/link-form16/", views.taxcomputation_link_form16, name="taxcomputation_link_form16"),
]

"""HRM 3.8 Offer Management — Backgroundverification URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Background Verification (3.8) — CRUD + lifecycle actions
    path("background-checks/", views.backgroundverification_list, name="backgroundverification_list"),
    path("background-checks/add/", views.backgroundverification_create, name="backgroundverification_create"),
    path("background-checks/<int:pk>/", views.backgroundverification_detail, name="backgroundverification_detail"),
    path("background-checks/<int:pk>/edit/", views.backgroundverification_edit, name="backgroundverification_edit"),
    path("background-checks/<int:pk>/delete/", views.backgroundverification_delete, name="backgroundverification_delete"),
    path("background-checks/<int:pk>/initiate/", views.backgroundverification_initiate, name="backgroundverification_initiate"),
    path("background-checks/<int:pk>/mark-status/", views.backgroundverification_mark_status, name="backgroundverification_mark_status"),
    path("background-checks/<int:pk>/complete/", views.backgroundverification_complete, name="backgroundverification_complete"),
]

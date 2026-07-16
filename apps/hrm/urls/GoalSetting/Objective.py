"""HRM 3.18 Goal Setting — Objective URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Objectives (the "O") — CRUD + the cascade/alignment tree view
    path("objectives/", views.objective_list, name="objective_list"),
    path("objectives/tree/", views.objective_tree, name="objective_tree"),
    path("objectives/add/", views.objective_create, name="objective_create"),
    path("objectives/<int:pk>/", views.objective_detail, name="objective_detail"),
    path("objectives/<int:pk>/edit/", views.objective_edit, name="objective_edit"),
    path("objectives/<int:pk>/delete/", views.objective_delete, name="objective_delete"),
]

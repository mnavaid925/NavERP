"""HRM 3.4 Employee Offboarding — Exitinterview URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Exit Interviews (3.4) — CRUD + workflow
    path("exit-interviews/", views.exitinterview_list, name="exitinterview_list"),
    path("exit-interviews/add/", views.exitinterview_create, name="exitinterview_create"),
    path("exit-interviews/<int:pk>/", views.exitinterview_detail, name="exitinterview_detail"),
    path("exit-interviews/<int:pk>/edit/", views.exitinterview_edit, name="exitinterview_edit"),
    path("exit-interviews/<int:pk>/delete/", views.exitinterview_delete, name="exitinterview_delete"),
    path("exit-interviews/<int:pk>/complete/", views.exitinterview_complete, name="exitinterview_complete"),
    path("exit-interviews/<int:pk>/skip/", views.exitinterview_skip, name="exitinterview_skip"),
]

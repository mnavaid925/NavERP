"""HRM 3.3 Employee Onboarding — Orientationsession URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Orientation Sessions (3.3) — CRUD + attendance
    path("orientation/", views.orientationsession_list, name="orientationsession_list"),
    path("orientation/add/", views.orientationsession_create, name="orientationsession_create"),
    path("orientation/<int:pk>/", views.orientationsession_detail, name="orientationsession_detail"),
    path("orientation/<int:pk>/edit/", views.orientationsession_edit, name="orientationsession_edit"),
    path("orientation/<int:pk>/delete/", views.orientationsession_delete, name="orientationsession_delete"),
    path("orientation/<int:pk>/mark-attended/", views.orientationsession_mark_attended, name="orientationsession_mark_attended"),
    path("orientation/<int:pk>/mark-missed/", views.orientationsession_mark_missed, name="orientationsession_mark_missed"),
]

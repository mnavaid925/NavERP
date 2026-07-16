"""HRM 3.4 Employee Offboarding — Separationcase URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Separation Cases (3.4) — CRUD + workflow + letters
    path("separations/", views.separationcase_list, name="separationcase_list"),
    path("separations/add/", views.separationcase_create, name="separationcase_create"),
    path("separations/<int:pk>/", views.separationcase_detail, name="separationcase_detail"),
    path("separations/<int:pk>/edit/", views.separationcase_edit, name="separationcase_edit"),
    path("separations/<int:pk>/delete/", views.separationcase_delete, name="separationcase_delete"),
    path("separations/<int:pk>/submit/", views.separationcase_submit, name="separationcase_submit"),
    path("separations/<int:pk>/approve/", views.separationcase_approve, name="separationcase_approve"),
    path("separations/<int:pk>/reject/", views.separationcase_reject, name="separationcase_reject"),
    path("separations/<int:pk>/withdraw/", views.separationcase_withdraw, name="separationcase_withdraw"),
    path("separations/<int:pk>/mark-cleared/", views.separationcase_mark_cleared, name="separationcase_mark_cleared"),
    path("separations/<int:pk>/complete/", views.separationcase_complete, name="separationcase_complete"),
]

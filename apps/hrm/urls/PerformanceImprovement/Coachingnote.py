"""HRM 3.21 Performance Improvement — Coachingnote URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Coaching notes (coach/admin only — no employee-facing view)
    path("coaching-notes/", views.coachingnote_list, name="coachingnote_list"),
    path("coaching-notes/add/", views.coachingnote_create, name="coachingnote_create"),
    path("coaching-notes/<int:pk>/", views.coachingnote_detail, name="coachingnote_detail"),
    path("coaching-notes/<int:pk>/edit/", views.coachingnote_edit, name="coachingnote_edit"),
    path("coaching-notes/<int:pk>/delete/", views.coachingnote_delete, name="coachingnote_delete"),
]

"""HRM 3.27 Communication Hub — Suggestion URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Suggestions (idea box — employee submits, admin reviews)
    path("suggestions/", views.suggestion_list, name="suggestion_list"),
    path("suggestions/add/", views.suggestion_create, name="suggestion_create"),
    path("suggestions/<int:pk>/", views.suggestion_detail, name="suggestion_detail"),
    path("suggestions/<int:pk>/edit/", views.suggestion_edit, name="suggestion_edit"),
]

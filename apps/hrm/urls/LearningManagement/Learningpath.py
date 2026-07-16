"""HRM 3.23 Learning Management (LMS) — Learningpath URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Learning paths (role-based journeys) + nested-create path items
    path("learning-paths/", views.learningpath_list, name="learningpath_list"),
    path("learning-paths/add/", views.learningpath_create, name="learningpath_create"),
    path("learning-paths/<int:pk>/", views.learningpath_detail, name="learningpath_detail"),
    path("learning-paths/<int:pk>/edit/", views.learningpath_edit, name="learningpath_edit"),
    path("learning-paths/<int:pk>/delete/", views.learningpath_delete, name="learningpath_delete"),
]

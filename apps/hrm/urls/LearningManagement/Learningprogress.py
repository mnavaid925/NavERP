"""HRM 3.23 Learning Management (LMS) — Learningprogress URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Learning progress (per-employee completion tracking)
    path("learning-progress/", views.learningprogress_list, name="learningprogress_list"),
    path("learning-progress/add/", views.learningprogress_create, name="learningprogress_create"),
    path("learning-progress/<int:pk>/", views.learningprogress_detail, name="learningprogress_detail"),
    path("learning-progress/<int:pk>/edit/", views.learningprogress_edit, name="learningprogress_edit"),
    path("learning-progress/<int:pk>/delete/", views.learningprogress_delete, name="learningprogress_delete"),
]

"""HRM 3.23 Learning Management (LMS) — TeamProgress URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("learning-team-progress/", views.learning_team_progress, name="learning_team_progress"),
]

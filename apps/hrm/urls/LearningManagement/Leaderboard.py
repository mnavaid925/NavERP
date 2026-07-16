"""HRM 3.23 Learning Management (LMS) — Leaderboard URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Gamification leaderboard + manager team-progress rollup (computed views)
    path("learning-leaderboard/", views.learning_leaderboard, name="learning_leaderboard"),
]

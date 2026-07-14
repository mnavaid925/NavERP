"""CRM 1.11 Customer Success & Retention — HealthScores URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Health scores (1.11)
    path("health-scores/", views.healthscore_list, name="healthscore_list"),
    path("health-scores/add/", views.healthscore_create, name="healthscore_create"),
    path("health-scores/config/", views.health_config_edit, name="health_config_edit"),
    path("health-scores/recompute-all/", views.recompute_all_health_scores, name="recompute_all_health_scores"),
    path("health-scores/<int:pk>/", views.healthscore_detail, name="healthscore_detail"),
    path("health-scores/<int:pk>/edit/", views.healthscore_edit, name="healthscore_edit"),
    path("health-scores/<int:pk>/delete/", views.healthscore_delete, name="healthscore_delete"),
    path("health-scores/<int:pk>/recompute/", views.recompute_health_score, name="recompute_health_score"),
]

"""Projects 7.18 — ProjectSyncRun URL patterns (append-only: no create/edit/delete)."""
from django.urls import path

from apps.projects.views.IntegrationApiHub import SyncRuns as views

urlpatterns = [
    path("integration/runs/", views.syr_list, name="syr_list"),
    path("integration/runs/<int:pk>/", views.syr_detail, name="syr_detail"),
    path("integration/runs/<int:pk>/retry/", views.syr_retry, name="syr_retry"),
]

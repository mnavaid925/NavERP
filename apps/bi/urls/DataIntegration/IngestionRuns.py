from django.urls import path

from apps.bi.views.DataIntegration import IngestionRuns as views

urlpatterns = [
    path("runs/", views.ingestion_run_list, name="ingestion_run_list"),
    path("runs/<int:pk>/", views.ingestion_run_detail, name="ingestion_run_detail"),
    path("runs/<int:pk>/delete/", views.ingestion_run_delete, name="ingestion_run_delete"),
    path("runs/<int:pk>/retry/", views.ingestion_run_retry, name="ingestion_run_retry"),
]

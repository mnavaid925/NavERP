from django.urls import path

from apps.bi.views.DataIntegration import IngestionPipelines as views

urlpatterns = [
    path("pipelines/", views.ingestion_pipeline_list, name="ingestion_pipeline_list"),
    path("pipelines/create/", views.ingestion_pipeline_create, name="ingestion_pipeline_create"),
    path("pipelines/<int:pk>/", views.ingestion_pipeline_detail, name="ingestion_pipeline_detail"),
    path("pipelines/<int:pk>/edit/", views.ingestion_pipeline_edit, name="ingestion_pipeline_edit"),
    path("pipelines/<int:pk>/delete/", views.ingestion_pipeline_delete, name="ingestion_pipeline_delete"),
    path("pipelines/<int:pk>/trigger/", views.ingestion_pipeline_trigger, name="ingestion_pipeline_trigger"),
]

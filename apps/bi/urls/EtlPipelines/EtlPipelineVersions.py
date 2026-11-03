from django.urls import path

from apps.bi.views.EtlPipelines import EtlPipelineVersions as views

urlpatterns = [
    path("pipeline-versions/", views.etl_pipeline_version_list, name="etl_pipeline_version_list"),
    path("pipeline-versions/create/", views.etl_pipeline_version_create, name="etl_pipeline_version_create"),
    path("pipeline-versions/<int:pk>/", views.etl_pipeline_version_detail, name="etl_pipeline_version_detail"),
    path("pipeline-versions/<int:pk>/edit/", views.etl_pipeline_version_edit, name="etl_pipeline_version_edit"),
    path("pipeline-versions/<int:pk>/delete/", views.etl_pipeline_version_delete, name="etl_pipeline_version_delete"),
    path("pipeline-versions/<int:pk>/promote/", views.etl_pipeline_version_promote, name="etl_pipeline_version_promote"),
]

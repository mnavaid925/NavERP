from django.urls import path

from apps.bi.views.EtlPipelines import EtlPipelines as views

urlpatterns = [
    path("etl-pipelines/", views.etl_pipeline_list, name="etl_pipeline_list"),
    path("etl-pipelines/create/", views.etl_pipeline_create, name="etl_pipeline_create"),
    path("etl-pipelines/<int:pk>/", views.etl_pipeline_detail, name="etl_pipeline_detail"),
    path("etl-pipelines/<int:pk>/edit/", views.etl_pipeline_edit, name="etl_pipeline_edit"),
    path("etl-pipelines/<int:pk>/delete/", views.etl_pipeline_delete, name="etl_pipeline_delete"),
    path("etl-pipelines/<int:pk>/canvas/", views.etl_pipeline_canvas, name="etl_pipeline_canvas"),
    path("etl-pipelines/<int:pk>/trigger/", views.etl_pipeline_trigger, name="etl_pipeline_trigger"),
]

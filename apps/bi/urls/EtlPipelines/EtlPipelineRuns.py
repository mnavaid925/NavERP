from django.urls import path

from apps.bi.views.EtlPipelines import EtlPipelineRuns as views

urlpatterns = [
    path("etl-runs/", views.etl_pipeline_run_list, name="etl_pipeline_run_list"),
    path("etl-runs/<int:pk>/", views.etl_pipeline_run_detail, name="etl_pipeline_run_detail"),
]

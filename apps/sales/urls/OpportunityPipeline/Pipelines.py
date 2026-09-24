from django.urls import path

from apps.sales.views.OpportunityPipeline.Pipelines import (
    opportunity_pipeline_board,
    opportunity_pipeline_create,
    opportunity_pipeline_delete,
    opportunity_pipeline_detail,
    opportunity_pipeline_edit,
    opportunity_pipeline_list,
    opportunity_pipeline_set_default,
    opportunity_pipeline_stage_create,
    opportunity_pipeline_stage_delete,
    opportunity_pipeline_stage_edit,
    opportunity_pipeline_stage_reorder,
    opportunity_pipeline_stages,
    opportunity_pipeline_visibility,
)


urlpatterns = [
    path("opportunity/board/", opportunity_pipeline_board, name="opportunity_pipeline_board"),
    path("opportunity/visibility/", opportunity_pipeline_visibility, name="opportunity_pipeline_visibility"),
    path("opportunity/pipelines/add/", opportunity_pipeline_create, name="opportunity_pipeline_create"),
    path("opportunity/pipelines/<int:pk>/stages/reorder/", opportunity_pipeline_stage_reorder, name="opportunity_pipeline_stage_reorder"),
    path("opportunity/pipelines/<int:pk>/stages/add/", opportunity_pipeline_stage_create, name="opportunity_pipeline_stage_create"),
    path("opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/edit/", opportunity_pipeline_stage_edit, name="opportunity_pipeline_stage_edit"),
    path("opportunity/pipelines/<int:pk>/stages/<int:stage_pk>/delete/", opportunity_pipeline_stage_delete, name="opportunity_pipeline_stage_delete"),
    path("opportunity/pipelines/<int:pk>/set-default/", opportunity_pipeline_set_default, name="opportunity_pipeline_set_default"),
    path("opportunity/pipelines/<int:pk>/edit/", opportunity_pipeline_edit, name="opportunity_pipeline_edit"),
    path("opportunity/pipelines/<int:pk>/delete/", opportunity_pipeline_delete, name="opportunity_pipeline_delete"),
    path("opportunity/pipelines/<int:pk>/stages/", opportunity_pipeline_stages, name="opportunity_pipeline_stages"),
    path("opportunity/pipelines/<int:pk>/", opportunity_pipeline_detail, name="opportunity_pipeline_detail"),
]

from django.urls import path

from apps.bi.views.EtlPipelines import TransformationSteps as views

urlpatterns = [
    path("transformation-steps/", views.transformation_step_list, name="transformation_step_list"),
    path("transformation-steps/create/", views.transformation_step_create, name="transformation_step_create"),
    path("transformation-steps/<int:pk>/", views.transformation_step_detail, name="transformation_step_detail"),
    path("transformation-steps/<int:pk>/edit/", views.transformation_step_edit, name="transformation_step_edit"),
    path("transformation-steps/<int:pk>/delete/", views.transformation_step_delete, name="transformation_step_delete"),
]

from django.urls import path

from apps.bi.views.SelfServiceAnalytics import DataBlendDefinitions as views

urlpatterns = [
    path("data-blends/", views.data_blend_definition_list, name="data_blend_definition_list"),
    path("data-blends/create/", views.data_blend_definition_create, name="data_blend_definition_create"),
    path("data-blends/<int:pk>/", views.data_blend_definition_detail, name="data_blend_definition_detail"),
    path("data-blends/<int:pk>/edit/", views.data_blend_definition_edit, name="data_blend_definition_edit"),
    path("data-blends/<int:pk>/delete/", views.data_blend_definition_delete, name="data_blend_definition_delete"),
    path("data-blends/<int:pk>/preview/", views.data_blend_definition_preview, name="data_blend_definition_preview"),
]

from django.urls import path

from apps.bi.views.SemanticLayer import SemanticModels as views

urlpatterns = [
    path("semantic/models/", views.semantic_model_list, name="semantic_model_list"),
    path("semantic/models/create/", views.semantic_model_create, name="semantic_model_create"),
    path("semantic/models/<int:pk>/", views.semantic_model_detail, name="semantic_model_detail"),
    path("semantic/models/<int:pk>/edit/", views.semantic_model_edit, name="semantic_model_edit"),
    path("semantic/models/<int:pk>/delete/", views.semantic_model_delete, name="semantic_model_delete"),
    path("semantic/models/<int:pk>/certify/", views.semantic_model_certify, name="semantic_model_certify"),
    path("semantic/models/<int:pk>/introspect/", views.semantic_model_introspect, name="semantic_model_introspect"),
]

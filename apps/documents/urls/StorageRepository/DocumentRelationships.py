from django.urls import path

from apps.documents.views.StorageRepository import DocumentRelationships as views

urlpatterns = [
    path("storage/relationships/", views.relationship_list, name="relationship_list"),
    path("storage/relationships/graph/", views.relationship_graph, name="relationship_graph"),
    path("storage/relationships/create/", views.relationship_create, name="relationship_create"),
    path("storage/relationships/<int:pk>/", views.relationship_detail, name="relationship_detail"),
    path("storage/relationships/<int:pk>/edit/", views.relationship_edit, name="relationship_edit"),
    path("storage/relationships/<int:pk>/delete/", views.relationship_delete, name="relationship_delete"),
]

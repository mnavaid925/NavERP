from django.urls import path

from apps.documents.views.VersionControl import DocumentVersions as views

urlpatterns = [
    path("versions/", views.document_version_list, name="document_version_list"),
    path("versions/create/", views.document_version_create, name="document_version_create"),
    path("versions/compare/", views.document_version_compare, name="document_version_compare"),
    path("versions/<int:pk>/", views.document_version_detail, name="document_version_detail"),
    path("versions/<int:pk>/edit/", views.document_version_edit, name="document_version_edit"),
    path("versions/<int:pk>/delete/", views.document_version_delete, name="document_version_delete"),
    path("versions/<int:pk>/rollback/", views.document_version_rollback, name="document_version_rollback"),
]

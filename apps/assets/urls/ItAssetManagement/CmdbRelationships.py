"""URL patterns for CMDB Dependency Relationships (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement.CmdbRelationships import (
    cmdb_relationship_create,
    cmdb_relationship_delete,
    cmdb_relationship_deprecate,
    cmdb_relationship_detail,
    cmdb_relationship_edit,
    cmdb_relationship_export_csv,
    cmdb_relationship_list,
    cmdb_relationship_sever,
    cmdb_relationship_verify,
)

urlpatterns = [
    path("cmdb/", cmdb_relationship_list, name="cmdb_relationship_list"),
    path("cmdb/create/", cmdb_relationship_create, name="cmdb_relationship_create"),
    path("cmdb/export-csv/", cmdb_relationship_export_csv, name="cmdb_relationship_export_csv"),
    path("cmdb/<int:pk>/", cmdb_relationship_detail, name="cmdb_relationship_detail"),
    path("cmdb/<int:pk>/edit/", cmdb_relationship_edit, name="cmdb_relationship_edit"),
    path("cmdb/<int:pk>/delete/", cmdb_relationship_delete, name="cmdb_relationship_delete"),
    path("cmdb/<int:pk>/verify/", cmdb_relationship_verify, name="cmdb_relationship_verify"),
    path("cmdb/<int:pk>/deprecate/", cmdb_relationship_deprecate, name="cmdb_relationship_deprecate"),
    path("cmdb/<int:pk>/sever/", cmdb_relationship_sever, name="cmdb_relationship_sever"),
]

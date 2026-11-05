from django.urls import path

from apps.bi.views.DataCatalog.CatalogLineageEdges import (
    catalog_lineage_edge_list,
    catalog_lineage_edge_create,
    catalog_lineage_edge_detail,
    catalog_lineage_edge_edit,
    catalog_lineage_edge_delete,
)

urlpatterns = [
    path("catalog/lineage/", catalog_lineage_edge_list, name="catalog_lineage_edge_list"),
    path("catalog/lineage/create/", catalog_lineage_edge_create, name="catalog_lineage_edge_create"),
    path("catalog/lineage/<int:pk>/", catalog_lineage_edge_detail, name="catalog_lineage_edge_detail"),
    path("catalog/lineage/<int:pk>/edit/", catalog_lineage_edge_edit, name="catalog_lineage_edge_edit"),
    path("catalog/lineage/<int:pk>/delete/", catalog_lineage_edge_delete, name="catalog_lineage_edge_delete"),
]

"""Procurement 6.9 Catalog Management — CatalogItem URL patterns.

``catalog-items/`` is this entity's first segment for every route; the literal routes
precede the ``<int:pk>`` ones — Django is first-match-wins.
"""
from django.urls import path

from apps.procurement.views.CatalogManagement.CatalogItems import (
    catalog_item_approve,
    catalog_item_block,
    catalog_item_create,
    catalog_item_delete,
    catalog_item_detail,
    catalog_item_edit,
    catalog_item_list,
    catalog_item_reject,
    catalog_item_submit,
)

urlpatterns = [
    path("catalog-items/", catalog_item_list, name="catalog_item_list"),
    path("catalog-items/add/", catalog_item_create, name="catalog_item_create"),
    path("catalog-items/<int:pk>/", catalog_item_detail, name="catalog_item_detail"),
    path("catalog-items/<int:pk>/edit/", catalog_item_edit, name="catalog_item_edit"),
    path("catalog-items/<int:pk>/delete/", catalog_item_delete, name="catalog_item_delete"),
    path("catalog-items/<int:pk>/submit/", catalog_item_submit, name="catalog_item_submit"),
    path("catalog-items/<int:pk>/approve/", catalog_item_approve, name="catalog_item_approve"),
    path("catalog-items/<int:pk>/reject/", catalog_item_reject, name="catalog_item_reject"),
    path("catalog-items/<int:pk>/block/", catalog_item_block, name="catalog_item_block"),
]
